"""The note on a hand-in: FreeFrame only carries it to the portal, which owns it.

The card's waiting note and whether it can still take one live in the portal, because the portal is
what sends the delivery. FreeFrame stores nothing, so the note can never reach a review: it is not on
the request, the folder or the brief.
"""
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from apps.api.config import settings

CARD = "https://trello.com/c/AbCd1234"


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body


@pytest.fixture
def portal(monkeypatch):
    from apps.api.services import hub_events
    settings.portal_events_webhook_url = "https://app.aditor.ai/api/freeframe/handin-webhook"
    settings.portal_events_webhook_secret = "s3cret"
    calls = []
    answer = {"value": FakeResponse(200, {"ok": True, "matched": True, "status": "open", "accepts": True, "window": "until_delivery", "note": None, "sentNote": None, "sentAt": None, "unsentNote": None})}

    def fake_post(url, content, headers, timeout):
        calls.append({"url": url, "body": content, "headers": headers})
        if isinstance(answer["value"], Exception):
            raise answer["value"]
        return answer["value"]

    monkeypatch.setattr(hub_events.httpx, "post", fake_post)
    yield SimpleNamespace(calls=calls, answer=answer)
    settings.portal_events_webhook_url = ""
    settings.portal_events_webhook_secret = ""


def _request(card=CARD):
    state = {"internal_handin": {"card_url": card}} if card else {}
    return SimpleNamespace(id="r1", iteration_state=state, iteration_brief="the brief", brief_excerpt="the excerpt")


def _routes(monkeypatch, req):
    from apps.api.routers import requests as rq
    monkeypatch.setattr(rq, "_live_request", lambda db, token, **kw: req)
    return rq


def test_a_save_is_signed_and_carries_the_note_as_written(portal, monkeypatch):
    rq = _routes(monkeypatch, _request())
    portal.answer["value"] = FakeResponse(200, {"ok": True, "matched": True, "status": "saved", "accepts": True, "window": "until_delivery", "note": "2 versions", "sentNote": None, "sentAt": None, "unsentNote": None})
    out = rq.save_delivery_note("tok", rq.DeliveryNoteBody(note="2 versions"), MagicMock())
    assert out["status"] == "saved"
    assert out["available"] is True
    assert out["accepts"] is True
    assert out["note"] == "2 versions"
    call = portal.calls[0]
    assert json.loads(call["body"]) == {"event": "delivery_note_save", "card_url": CARD, "note": "2 versions"}
    assert call["headers"]["X-Aditor-Signature"] == hmac.new(b"s3cret", call["body"], hashlib.sha256).hexdigest()


def test_too_late_comes_back_to_the_editor(portal, monkeypatch):
    rq = _routes(monkeypatch, _request())
    portal.answer["value"] = FakeResponse(200, {"ok": True, "matched": True, "status": "too_late", "accepts": False, "window": "closed", "note": None, "sentNote": "first", "sentAt": "2026-11-04T10:00:00Z", "unsentNote": None})
    out = rq.save_delivery_note("tok", rq.DeliveryNoteBody(note="more"), MagicMock())
    assert out["status"] == "too_late"
    assert out["accepts"] is False
    assert out["sent_note"] == "first"
    assert out["sent_at"] == "2026-11-04T10:00:00Z"


def test_a_note_over_the_limit_is_refused_here_and_never_sent(portal, monkeypatch):
    rq = _routes(monkeypatch, _request())
    with pytest.raises(HTTPException) as e:
        rq.save_delivery_note("tok", rq.DeliveryNoteBody(note="x" * 501), MagicMock())
    assert e.value.status_code == 422
    assert portal.calls == []


def test_a_request_with_no_card_has_no_note_field(portal, monkeypatch):
    rq = _routes(monkeypatch, _request(card=None))
    assert rq.read_delivery_note("tok", MagicMock())["available"] is False
    assert rq.save_delivery_note("tok", rq.DeliveryNoteBody(note="x"), MagicMock())["available"] is False
    assert portal.calls == []


def test_a_brand_the_portal_cannot_deliver_for_has_no_note_field(portal, monkeypatch):
    rq = _routes(monkeypatch, _request())
    portal.answer["value"] = FakeResponse(200, {"ok": True, "matched": False, "status": "unavailable", "accepts": False, "window": "closed", "note": None, "sentNote": None, "sentAt": None, "unsentNote": None})
    assert rq.read_delivery_note("tok", MagicMock())["available"] is False


def test_portal_down_or_old_says_so_and_never_claims_saved(portal, monkeypatch):
    rq = _routes(monkeypatch, _request())
    # An older portal acknowledges an unknown event with `ignored`: that is not a save. This keeps the
    # flow honest whichever side deploys first.
    for answer in (FakeResponse(200, {"ok": True, "ignored": True}), FakeResponse(500), Exception("boom")):
        portal.answer["value"] = answer
        with pytest.raises(HTTPException) as e:
            rq.save_delivery_note("tok", rq.DeliveryNoteBody(note="x"), MagicMock())
        assert e.value.status_code == 503
        read = rq.read_delivery_note("tok", MagicMock())
        assert read["available"] is True
        assert read["reachable"] is False


def test_not_configured_means_no_field(monkeypatch):
    settings.portal_events_webhook_url = ""
    rq = _routes(monkeypatch, _request())
    assert rq.read_delivery_note("tok", MagicMock())["available"] is False


def test_the_note_never_touches_the_request_so_a_review_cannot_read_it(portal, monkeypatch):
    req = _request()
    before = dict(vars(req))
    rq = _routes(monkeypatch, req)
    db = MagicMock()
    rq.save_delivery_note("tok", rq.DeliveryNoteBody(note="2 versions"), db)
    assert vars(req) == before
    db.commit.assert_not_called()
    db.add.assert_not_called()
