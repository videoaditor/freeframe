"""File requests: WeTransfer in reverse, with Auto Review built in (platform v2).

Spec: docs/superpowers/specs/2026-09-28-review-platform-v2-design.md.

  Owner (signed in)            Editor (no account, only the link)
  POST /requests      ──link──▶ GET  /r/{token}
  GET  /requests               POST /r/{token}/upload/{initiate,presign-part,complete,abort}
                               GET  /r/{token}/review

The token IS the permission, exactly like a share link is for viewing: whoever holds it may upload
into that one folder and read the review of what they uploaded - nothing else in the project.
Uploads reuse the normal multipart path (presigned S3 parts), so a big file behaves exactly as it
does for a signed-in editor. A file with the same name as one already handed in becomes its next
VERSION - that is how a V2 clears the gate.
"""
import base64
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..middleware.auth import get_current_user
from ..middleware.rate_limit import rate_limit
from ..models.asset import Asset, AssetType, AssetVersion, FileType, MediaFile, ProcessingStatus
from ..models.comment import Comment
from ..models.folder import Folder
from ..models.project import Project, ProjectMember, ProjectRole
from ..models.share import ShareLink, SharePermission
from ..models.upload_request import UploadRequest
from ..models.user import GuestUser, User
from ..schemas.upload import ALLOWED_MIME_TYPES, mime_to_asset_type
from ..services import review_bridge
from ..services.permissions import effective_project_role, require_project_role
from ..services.s3_service import (
    abort_multipart_upload, complete_multipart_upload, create_multipart_upload, presign_upload_part,
)
from ..services.storage import upload_guard_error

router = APIRouter(tags=["requests"])

# Auto Review comments as this guest (feedback-agent src/freeframe-agent.ts postGuestComment).
REVIEWER_EMAIL = "review@aditor.ai"


# ── Pure helpers (tested directly) ─────────────────────────────────────────────

def request_state(req: UploadRequest, now: datetime) -> str:
    """live | revoked | expired. Revoked wins: an owner who pulled a link meant it."""
    if req.revoked_at is not None:
        return "revoked"
    if req.expires_at is not None and req.expires_at <= now:
        return "expired"
    return "live"


def asset_name_for(filename: str) -> str:
    """The asset a file belongs to: its name without extension, so `Hook1.mp4` and `Hook1.mov`
    handed in twice are two versions of ONE asset, never two stray copies."""
    return os.path.splitext(os.path.basename(filename or ""))[0].strip()[:255] or "Untitled"


def owner_status(bridge: Optional[dict]) -> dict:
    """What the owner's list shows. No answer from the review = ready (fail open)."""
    if not bridge:
        return {"status": "clear", "open_must_fixes": 0}
    st = bridge.get("status")
    return {"status": st if st in ("reviewing", "held", "clear") else "clear",
            "open_must_fixes": int(bridge.get("openMustFixes") or 0)}


# ── Owner ──────────────────────────────────────────────────────────────────────

class RequestCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    brief_text: str = ""
    brief_url: str = ""
    brief_pdf_base64: str = ""
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


def _request_out(req: UploadRequest, project: Optional[Project], st: Optional[dict] = None, assets: int = 0) -> dict:
    base = (settings.frontend_url or "").rstrip("/")
    return {
        "id": str(req.id),
        "token": req.token,
        "url": f"{base}/r/{req.token}",
        "title": req.title,
        "project_id": str(req.project_id),
        "project_name": project.name if project else "",
        "folder_id": str(req.folder_id),
        "review_share_token": req.review_share_token,
        "brand_slug": req.brand_slug,
        "brief_excerpt": req.brief_excerpt,
        "last_uploader_name": req.last_uploader_name,
        "assets": assets,
        "state": request_state(req, datetime.now(timezone.utc)),
        "created_at": req.created_at.isoformat() if req.created_at else None,
        **owner_status(st),
    }


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_request(body: RequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == body.project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_role(db, body.project_id, current_user, ProjectRole.editor)

    folder = Folder(project_id=project.id, name=body.title.strip(),
                    description=(body.brief_url or "File request")[:2000], created_by=current_user.id)
    db.add(folder)
    db.flush()
    # The standing link Auto Review reads the folder through. Always created here (not gated on the
    # automation webhook): a request exists to be reviewed. Same two switches as automation_share.
    link = ShareLink(folder_id=folder.id, token=secrets.token_urlsafe(32), created_by=current_user.id,
                     title="Auto Review", description="Standing link so Auto Review can see this request.",
                     permission=SharePermission.comment, allow_download=True, visibility="public")
    db.add(link)
    db.flush()
    brand = review_bridge.brand_slug(project.name)
    excerpt = (body.brief_text or body.brief_url or ("PDF briefing" if body.brief_pdf_base64 else "")).strip()[:500] or None
    req = UploadRequest(
        token=secrets.token_urlsafe(24), project_id=project.id, folder_id=folder.id,
        created_by=current_user.id, title=body.title.strip(), brand_slug=brand,
        review_share_token=link.token, brief_excerpt=excerpt,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)) if body.expires_in_days else None,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    # After the commit, and fail-open: a request the review never heard of is still a working link.
    review_bridge.register_request(link.token, brand, req.title, body.brief_text, body.brief_url, body.brief_pdf_base64)
    return _request_out(req, project)


@router.get("/requests")
def list_requests(project_id: Optional[uuid.UUID] = Query(None), db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    q = db.query(UploadRequest)
    if project_id:
        require_project_role(db, project_id, current_user, ProjectRole.viewer)
        q = q.filter(UploadRequest.project_id == project_id)
    else:
        member_projects = [m.project_id for m in db.query(ProjectMember).filter(
            ProjectMember.user_id == current_user.id, ProjectMember.deleted_at.is_(None)).all()]
        q = q.filter((UploadRequest.created_by == current_user.id) | (UploadRequest.project_id.in_(member_projects or [uuid.uuid4()])))
    reqs = q.order_by(UploadRequest.created_at.desc()).limit(100).all()
    statuses = review_bridge.request_status([r.review_share_token for r in reqs])
    projects = {p.id: p for p in db.query(Project).filter(Project.id.in_({r.project_id for r in reqs} or {uuid.uuid4()})).all()}
    counts = {}
    for r in reqs:
        counts[r.id] = db.query(Asset).filter(Asset.folder_id == r.folder_id, Asset.deleted_at.is_(None)).count()
    return [_request_out(r, projects.get(r.project_id), statuses.get(r.review_share_token), counts.get(r.id, 0)) for r in reqs]


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_request(request_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(UploadRequest).filter(UploadRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.created_by != current_user.id:
        require_project_role(db, req.project_id, current_user, ProjectRole.owner)
    req.revoked_at = datetime.now(timezone.utc)
    db.commit()


# ── Owner: rules and time saved, proxied to Auto Review ────────────────────────

def _brands_for(db: Session, user: User) -> Optional[list[str]]:
    """Staff see every brand (None = unfiltered); a customer sees only brands of its own projects."""
    if getattr(user, "is_staff", True) is not False:
        return None
    ids = [m.project_id for m in db.query(ProjectMember).filter(
        ProjectMember.user_id == user.id, ProjectMember.deleted_at.is_(None)).all()]
    projects = db.query(Project).filter(Project.id.in_(ids or [uuid.uuid4()]), Project.deleted_at.is_(None)).all()
    return sorted({review_bridge.brand_slug(p.name) for p in projects})


@router.get("/insights/time-saved")
def time_saved(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brands = _brands_for(db, current_user)
    if brands == []:
        return {"days": days, "videos": 0, "watchSec": 0, "typeSec": 0, "totalSec": 0,
                "perDay": [], "perBrand": [], "assumptions": {"wpm": 40, "watches": 1}}
    r = review_bridge.time_saved(days, brands)
    if r is None:
        raise HTTPException(status_code=503, detail="Auto Review is not reachable right now.")
    return r


def _project_brand(db: Session, project_id: uuid.UUID, user: User, role: ProjectRole) -> str:
    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_role(db, project_id, user, role)
    return review_bridge.brand_slug(project.name)


@router.get("/insights/rules")
def list_rules(project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brand = _project_brand(db, project_id, current_user, ProjectRole.viewer)
    r = review_bridge.rules(brand)
    if r is None:
        raise HTTPException(status_code=503, detail="Auto Review is not reachable right now.")
    return {"brand": brand, **r}


class RulesImport(BaseModel):
    project_id: uuid.UUID
    text: str = ""
    url: str = ""
    pdf_base64: str = ""


@router.post("/insights/rules/import")
def import_rules(body: RulesImport, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brand = _project_brand(db, body.project_id, current_user, ProjectRole.editor)
    if not (body.text.strip() or body.url.strip() or body.pdf_base64):
        raise HTTPException(status_code=400, detail="Drop a PDF, paste text or a link.")
    r = review_bridge.import_rules(brand, body.text, body.url, body.pdf_base64)
    if r is None:
        raise HTTPException(status_code=503, detail="Auto Review could not read that right now.")
    return r


# ── Editor: the public side of a request ───────────────────────────────────────

def _live_request(db: Session, token: str) -> UploadRequest:
    req = db.query(UploadRequest).filter(UploadRequest.token == token).first()
    if not req:
        raise HTTPException(status_code=404, detail="This link does not exist.")
    state = request_state(req, datetime.now(timezone.utc))
    if state != "live":
        raise HTTPException(status_code=410, detail="This link was closed by its owner." if state == "revoked" else "This link has expired.")
    return req


@router.get("/r/{token}", dependencies=[Depends(rate_limit("request_view", 120, 600))])
def view_request(token: str, db: Session = Depends(get_db)):
    req = _live_request(db, token)
    project = db.query(Project).filter(Project.id == req.project_id).first()
    assets = db.query(Asset).filter(Asset.folder_id == req.folder_id, Asset.deleted_at.is_(None)).order_by(Asset.created_at).all()
    return {
        "title": req.title,
        "brand": project.name if project else "",
        "brief_excerpt": req.brief_excerpt,
        "review_share_token": req.review_share_token,
        "assets": [{"id": str(a.id), "name": a.name} for a in assets],
        "expires_at": req.expires_at.isoformat() if req.expires_at else None,
    }


class GuestInitiate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    original_filename: str = Field(min_length=1, max_length=500)
    mime_type: str
    file_size_bytes: int = Field(gt=0)


@router.post("/r/{token}/upload/initiate", dependencies=[Depends(rate_limit("request_upload", 60, 600))])
def guest_initiate(token: str, body: GuestInitiate, db: Session = Depends(get_db)):
    req = _live_request(db, token)
    if body.mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {body.mime_type}")
    guard = upload_guard_error(db, body.file_size_bytes)
    if guard:
        raise HTTPException(status_code=400, detail=guard)

    name = asset_name_for(body.original_filename)
    # Same name in this folder = the next version of that asset (a V2), never a second asset.
    asset = db.query(Asset).filter(Asset.folder_id == req.folder_id, Asset.name == name,
                                   Asset.deleted_at.is_(None)).first()
    if not asset:
        asset = Asset(project_id=req.project_id, name=name, asset_type=mime_to_asset_type(body.mime_type),
                      created_by=req.created_by, folder_id=req.folder_id)
        db.add(asset)
        db.flush()
    last = db.query(AssetVersion).filter(AssetVersion.asset_id == asset.id, AssetVersion.deleted_at.is_(None)) \
        .order_by(AssetVersion.version_number.desc()).first()
    # The guest has no account; the version is filed under the request's owner, who asked for it.
    version = AssetVersion(asset_id=asset.id, version_number=(last.version_number + 1) if last else 1,
                           processing_status=ProcessingStatus.uploading, created_by=req.created_by)
    db.add(version)
    db.flush()
    ext = os.path.splitext(body.original_filename)[1].lower()
    s3_key = f"raw/{req.project_id}/{asset.id}/{version.id}/original{ext}"
    upload_id = create_multipart_upload(s3_key, body.mime_type)
    file_type = {AssetType.image: FileType.image, AssetType.audio: FileType.audio}.get(asset.asset_type, FileType.video)
    db.add(MediaFile(version_id=version.id, file_type=file_type, original_filename=body.original_filename,
                     mime_type=body.mime_type, file_size_bytes=body.file_size_bytes, s3_key_raw=s3_key))
    req.last_uploader_name = body.name.strip()
    req.last_uploader_email = str(body.email).lower()
    db.commit()
    return {"upload_id": upload_id, "s3_key": s3_key, "asset_id": str(asset.id), "version_id": str(version.id),
            "version_number": version.version_number}


def _owned_media(db: Session, req: UploadRequest, s3_key: str) -> tuple[MediaFile, AssetVersion]:
    """The upload must belong to THIS request's folder - a token never reaches another folder."""
    media = db.query(MediaFile).filter(MediaFile.s3_key_raw == s3_key).first()
    version = db.query(AssetVersion).filter(AssetVersion.id == media.version_id).first() if media else None
    asset = db.query(Asset).filter(Asset.id == version.asset_id).first() if version else None
    if not media or not version or not asset or asset.folder_id != req.folder_id:
        raise HTTPException(status_code=403, detail="Not authorized for this upload")
    return media, version


class GuestPart(BaseModel):
    s3_key: str
    upload_id: str
    part_number: int = Field(ge=1, le=10000)


@router.post("/r/{token}/upload/presign-part", dependencies=[Depends(rate_limit("request_part", 3000, 600))])
def guest_presign(token: str, body: GuestPart, db: Session = Depends(get_db)):
    req = _live_request(db, token)
    _owned_media(db, req, body.s3_key)
    return {"presigned_url": presign_upload_part(body.s3_key, body.upload_id, body.part_number),
            "part_number": body.part_number}


class GuestComplete(BaseModel):
    s3_key: str
    upload_id: str
    parts: list[dict]


def _trigger_processing(asset_id: uuid.UUID, version_id: uuid.UUID):
    from ..tasks.transcode_tasks import process_asset
    from ..tasks.celery_app import send_task_safe
    send_task_safe(process_asset, str(asset_id), str(version_id))


@router.post("/r/{token}/upload/complete", dependencies=[Depends(rate_limit("request_upload", 60, 600))])
def guest_complete(token: str, body: GuestComplete, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    req = _live_request(db, token)
    _, version = _owned_media(db, req, body.s3_key)
    # Completing twice (a retried request) must not re-trigger processing on a finished version.
    if version.processing_status != ProcessingStatus.uploading:
        return {"status": "processing", "asset_id": str(version.asset_id), "version_id": str(version.id)}
    complete_multipart_upload(body.s3_key, body.upload_id, body.parts)
    version.processing_status = ProcessingStatus.processing
    db.commit()
    background_tasks.add_task(_trigger_processing, version.asset_id, version.id)
    return {"status": "processing", "asset_id": str(version.asset_id), "version_id": str(version.id)}


@router.post("/r/{token}/upload/abort", status_code=status.HTTP_204_NO_CONTENT)
def guest_abort(token: str, body: GuestPart, db: Session = Depends(get_db)):
    req = _live_request(db, token)
    _, version = _owned_media(db, req, body.s3_key)
    abort_multipart_upload(body.s3_key, body.upload_id)
    version.processing_status = ProcessingStatus.failed
    db.commit()


@router.get("/r/{token}/review", dependencies=[Depends(rate_limit("request_view", 120, 600))])
def guest_review(token: str, db: Session = Depends(get_db)):
    """The review of what was handed in: Auto Review's comments on the LATEST version of each file.

    These are the comments FreeFrame stores as internal (kept off client-facing shares); the token
    holder is the editor who handed the files in, so they see them. Plus the gate: held means a
    must-fix is open and a new version is the way through.
    """
    req = _live_request(db, token)
    reviewer = db.query(GuestUser).filter(GuestUser.email == REVIEWER_EMAIL).first()
    out = []
    for a in db.query(Asset).filter(Asset.folder_id == req.folder_id, Asset.deleted_at.is_(None)).order_by(Asset.created_at).all():
        v = db.query(AssetVersion).filter(AssetVersion.asset_id == a.id, AssetVersion.deleted_at.is_(None)) \
            .order_by(AssetVersion.version_number.desc()).first()
        comments = []
        if v and reviewer:
            rows = db.query(Comment).filter(Comment.asset_id == a.id, Comment.version_id == v.id,
                                            Comment.guest_author_id == reviewer.id, Comment.parent_id.is_(None),
                                            Comment.deleted_at.is_(None)).order_by(Comment.timecode_start.asc().nullsfirst()).all()
            comments = [{"t": c.timecode_start, "body": c.body.replace("Must fix — ", "", 1),
                         "must_fix": c.body.startswith("Must fix")} for c in rows]
        out.append({"asset_id": str(a.id), "name": a.name,
                    "version": v.version_number if v else 0,
                    "processing": (v.processing_status.value if v else "uploading"),
                    "comments": comments})
    gate = owner_status(review_bridge.request_status([req.review_share_token]).get(req.review_share_token))
    return {"assets": out, "gate": gate, "review_share_token": req.review_share_token}
