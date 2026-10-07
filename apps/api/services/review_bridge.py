"""Auto Review's /api/v1/* contract, called from this server (platform v2).

Spec: feedback-agent docs/superpowers/specs/2026-09-28-jev-decision-engine-design.md. The secret
lives here and never reaches a browser.

FAIL OPEN, everywhere. A review service that is down, slow or unconfigured must never stop an
owner creating a request or an editor handing in: every call returns None on any failure, and
callers treat None as "not reviewed" - which the owner sees as unavailable while files remain accessible.
"""
import logging
import re
from typing import Any, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.review_bridge_url.strip() and settings.review_bridge_secret.strip())


def _call(method: str, path: str, *, json: Any = None, params: Optional[dict] = None, timeout: float = 20) -> Optional[dict]:
    if not is_configured():
        return None
    try:
        r = httpx.request(
            method,
            settings.review_bridge_url.rstrip("/") + path,
            json=json,
            params=params,
            headers={"authorization": f"Bearer {settings.review_bridge_secret}"},
            timeout=timeout,
        )
        if r.status_code >= 400:
            logger.warning("review bridge %s %s -> %s", method, path, r.status_code)
            return None
        return r.json()
    except Exception:  # noqa: BLE001 - fail open by design, see module docstring
        logger.warning("review bridge %s %s failed", method, path, exc_info=True)
        return None


def brand_slug(name: str) -> str:
    """The Worker's brand keys are lower-case kebab slugs ("mynd-organics")."""
    s = re.sub(r"\b(gmbh|ug|kg|ltd|inc|b\.?v\.?)\b", "", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:120]


def register_request(share_token: str, brand: str, title: str, brief_text: str = "",
                     brief_url: str = "", brief_pdf_base64: str = "", receive_iterations: bool = False,
                     brief_source_token: str = "", *, checklist: Optional[dict] = None) -> Optional[dict]:
    return _call("POST", "/api/v1/requests", json={
        "share_token": share_token, "brand": brand, "title": title, "receive_iterations": receive_iterations,
        "brief_text": brief_text, "brief_url": brief_url, "brief_pdf_base64": brief_pdf_base64,
        **({"checklist": checklist} if checklist else {}),
        **({"brief_source_token":brief_source_token} if brief_source_token else {}),
    }, timeout=60)


def request_status(share_tokens: list[str]) -> dict[str, dict]:
    if not share_tokens:
        return {}
    statuses = {}
    for start in range(0, len(share_tokens), 50):
        r = _call("GET", "/api/v1/requests/status", params={"tokens": ",".join(share_tokens[start:start + 50])})
        values = r.get("status") if isinstance(r, dict) else None
        if isinstance(values, dict):
            statuses.update({key: value for key, value in values.items() if key in share_tokens and isinstance(value, dict)})
    return statuses


def time_saved(days: int, brands: Optional[list[str]]) -> Optional[dict]:
    params: dict = {"days": days}
    if brands is not None:
        params["brands"] = ",".join(brands)
    return _call("GET", "/api/v1/time-saved", params=params, timeout=30)


def rules(brand: str) -> Optional[dict]:
    return _call("GET", "/api/v1/rules", params={"brand": brand})


def import_rules(brand: str, text: str = "", url: str = "", pdf_base64: str = "") -> Optional[dict]:
    return _call("POST", "/api/v1/rules/import", json={
        "brand": brand, "text": text, "url": url, "pdf_base64": pdf_base64,
    }, timeout=90)


def decide_suggestion(brand: str, suggestion_id: str, action: str, by: str) -> Optional[dict]:
    return _call("POST", "/api/v1/rules/suggestion", json={
        "brand": brand, "id": suggestion_id, "action": action, "by": by,
    })


def object_to_note(share_token: str, asset_id: str, comment_id: str, body: str, text: str, who: str, version_id: Optional[str] = None) -> Optional[dict]:
    return _call("POST", "/api/v1/objection", json={
        "share_token": share_token, "asset_id": asset_id, "comment_id": comment_id,
        "body": body, "text": text, "who": who, "version_id": version_id,
    }, timeout=45)


def asset_stats(asset_ids: list[str], *, request_token: Optional[str] = None) -> dict[str, dict]:
    if not asset_ids:
        return {}
    assets = {}
    for start in range(0, len(asset_ids), 200):
        params = {"ids": ",".join(asset_ids[start:start + 200])}
        if request_token:
            params["request_token"] = request_token
        r = _call("GET", "/api/v1/assets", params=params)
        values = r.get("assets") if isinstance(r, dict) else None
        if isinstance(values, dict):
            assets.update({key: value for key, value in values.items() if key in asset_ids and isinstance(value, dict)})
    return assets


def checklist_card(url: str) -> Optional[dict]:
    return _call("POST", "/api/v1/checklists/card", json={"url": url})


def checklist_snapshot(intent: dict) -> Optional[dict]:
    return _call("POST", "/api/v1/checklists/snapshot", json=intent, timeout=90)


def checklist_plan(snapshot: dict, context_sha256: str, plan_id: Optional[str] = None) -> Optional[dict]:
    # Preserve a bounded, safe error code for durable retry and the private checklist UI.
    if not is_configured():
        return {"error": "review-unconfigured"}
    try:
        response = httpx.request("POST", settings.review_bridge_url.rstrip("/") + "/api/v1/checklists/plan",
            json={"snapshot": snapshot, "context_sha256": context_sha256, **({"plan_id": plan_id} if plan_id else {})},
            headers={"authorization": f"Bearer {settings.review_bridge_secret}"}, timeout=30)
        data = response.json()
        if not isinstance(data, dict):
            return None
        if response.status_code >= 400:
            allowed = {"plan-api-unavailable", "plan-busy", "plan-conflict", "plan-not-found", "snapshot-conflict", "plan-contract-invalid"}
            return {"error": data.get("error") if data.get("error") in allowed else "plan-unavailable"}
        return data
    except (httpx.HTTPError, ValueError):
        return None


def plan_iterations(**brief):
    return _call("POST", "/api/v1/iterations/plan", json=brief, timeout=120)


def review_iteration(payload):
    return _call("POST", "/api/v1/iterations/review", json=payload, timeout=240)


def deliver_iterations(payload):
    """Keep policy/version conflicts distinct from retryable provider failures."""
    if not is_configured():return None
    try:
        response=httpx.post(settings.review_bridge_url.rstrip('/')+'/api/v1/iterations/deliver',
            headers={'authorization':f'Bearer {settings.review_bridge_secret}'},json=payload,timeout=90,follow_redirects=False)
        if response.status_code==409:return {'review_conflict':True}
        response.raise_for_status()
        return response.json()
    except Exception:
        return None
