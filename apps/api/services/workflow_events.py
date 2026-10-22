"""Outbound editor-workflow events to the owned company-DB store (`app.log_workflow_event`), so a
hand-in or revision step in FreeFrame joins the cross-tool journey the hub/portal already track.

Sibling of `hub_events.py`: FreeFrame stays "dumb" here too - it only reports what happened, after
`db.commit()`, best effort, and never fails or delays the request that triggered it. Unlike
hub_events there is no HMAC: the credential is a scoped JWT bearer (`COMPANYDB_WORKFLOW_JWT`, role
`workflow_writer`), the same app-JWT-over-PostgREST pattern every other company-DB writer uses.

Card/brand resolution reuses `hub_events._review_url` for the request's own editor link and the
request's own `brand_slug` (set at creation, see routers/requests.py `project_brand`) rather than
re-deriving either - this emitter never needs write access beyond the one RPC, so it must not call
into anything that could raise (`project_brand` can 409) or require a read grant this role doesn't
have (the company directory is deliberately not queried here: the RPC resolves `person_id` from
`email` on its own, least-privilege for FreeFrame).
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models.upload_request import RequestUpload, UploadRequest
from . import hub_events

logger = logging.getLogger(__name__)

TOOL = "freeframe"


def is_enabled() -> bool:
    return bool((getattr(settings, "companydb_workflow_jwt", "") or "").strip())


def _card_ref(req: UploadRequest) -> Optional[str]:
    """The request's internal hand-in card when it has one (a real Trello/portal card), else the
    request's own editor-facing /r/<token> link - the stable id another tool correlates this
    request's journey on, exactly like the portal's own `handin_url` bookkeeping."""
    state = req.iteration_state if isinstance(req.iteration_state, dict) else {}
    internal = state.get("internal_handin")
    if isinstance(internal, dict):
        card = (internal.get("card_url") or "").strip()
        if card:
            return card
    return hub_events._review_url(req)


def _submission_time(db: Session, req: UploadRequest, asset_id, version) -> datetime:
    """The version's own submitted_at when a request-lane record exists, else the moment of
    commit - a plain `/upload/complete` hand-in never gets a RequestUpload row of its own."""
    record = db.query(RequestUpload).filter(RequestUpload.request_id == req.id,
        RequestUpload.asset_id == asset_id, RequestUpload.version_number == version.version_number).first()
    if record and record.submitted_at:
        return record.submitted_at
    return datetime.now(timezone.utc)


def _post_event(req: UploadRequest, event: str, props: dict, occurred_at: datetime,
                 email: Optional[str] = None) -> None:
    email = (email or getattr(req, "last_uploader_email", None) or "").strip() or None
    brand_slug = (getattr(req, "brand_slug", None) or "").strip() or None
    card_ref = _card_ref(req)
    if not email or not brand_slug or not card_ref:
        return
    body = {
        "event_id": str(uuid.uuid4()),
        "action": event,
        "tool": TOOL,
        "card_ref": card_ref,
        "brand_slug": brand_slug,
        "occurred_at": occurred_at.isoformat(),
        "email": email,  # the RPC resolves person_id from this (least-privilege for FreeFrame)
        "props": props,
        "source_event_id": props.get("version_id") or props.get("asset_id"),
    }
    _deliver(body)


def _deliver(body: dict) -> None:
    url = f"{(settings.companydb_url or '').strip().rstrip('/')}/rpc/log_workflow_event"
    # The RPC takes a single jsonb parameter `p`; PostgREST maps top-level JSON
    # keys to named params, so the event object must be wrapped under "p".
    content = json.dumps({"p": body}).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {settings.companydb_workflow_jwt}",
    }
    try:
        httpx.post(url, content=content, headers=headers, timeout=10)
    except Exception:  # noqa: BLE001 - a company-DB hiccup must never fail the hand-in it reports
        logger.warning("workflow event %r failed to reach the company DB", body.get("action"), exc_info=True)


def announce_handin_uploaded(db: Session, req: Optional[UploadRequest], asset, version) -> None:
    """`handin.uploaded` for a completed version, plus `version.resubmitted` when it is not the
    asset's first version (an editor answering feedback, not the initial hand-in). `req` is passed
    directly by the request-lane caller (it already holds one); the plain `/upload/complete` lane
    resolves it from the asset's folder, the only way that lane can ever be linked to a request
    (a staff hand-in folder converted via `routers/requests.py` `folder_editor_request`). That staff
    lane never records a `last_uploader_email` on the request (only the guest hand-in flow does), so
    the email falls back to whoever uploaded this version, the same resolution `hub_events` uses for
    its own non-guest editor lookups."""
    if not is_enabled():
        return
    if req is None:
        req = hub_events._handin_request_for_asset(db, asset)
    if req is None:
        return
    email = (getattr(req, "last_uploader_email", None) or "").strip() or None
    if not email:
        email = hub_events._user_email(db, getattr(version, "created_by", None))
    occurred_at = _submission_time(db, req, asset.id, version)
    props = {"version_no": version.version_number, "version_id": str(version.id)}
    _post_event(req, "handin.uploaded", props, occurred_at, email=email)
    if version.version_number > 1:
        _post_event(req, "version.resubmitted", props, occurred_at, email=email)


def announce_handin_finished(db: Session, req: UploadRequest) -> None:
    """`handin.finished` - the request's gate cleared and every submitted version was accepted."""
    if not is_enabled():
        return
    _post_event(req, "handin.finished", {}, req.completed_at or datetime.now(timezone.utc))


def announce_revision_responded(db: Session, req: UploadRequest, asset, comment_id: str = "") -> None:
    """`revision.responded` - the editor answered an open client note (`routers/requests.py`
    `guest_object`), whether Auto Review withdrew it or left it standing."""
    if not is_enabled():
        return
    props = {"asset_id": str(asset.id)}
    if comment_id:
        props["comment_id"] = comment_id
    _post_event(req, "revision.responded", props, datetime.now(timezone.utc))
