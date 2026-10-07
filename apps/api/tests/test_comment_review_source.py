"""H2 trust boundary: a guest identity or model prose never proves provenance."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.api.config import settings
from apps.api.models.asset import Asset, AssetVersion, ProcessingStatus
from apps.api.models.comment import Comment
from apps.api.models.share import SharePermission
from apps.api.models.user import GuestUser


SOURCE = dict(schema_version="autoreview.comment-source.v1", requirement_id="req-1",
              plan_id="plan-1", sources=[dict(layer="briefing", reference_id="brief-1", source_version="v1")])


@pytest.fixture
def service(client, mock_db, monkeypatch):
    monkeypatch.setattr(settings, "review_bridge_secret", "test-bridge-secret")
    monkeypatch.setattr(settings, "automation_guest_emails", "review@example.test")
    aid, vid = uuid.uuid4(), uuid.uuid4()
    link = SimpleNamespace(id=uuid.uuid4(), asset_id=aid, permission=SharePermission.comment)
    asset = SimpleNamespace(id=aid, project_id=uuid.uuid4(), name="Synthetic cut")
    version = SimpleNamespace(id=vid, asset_id=aid, processing_status=ProcessingStatus.ready)
    guest = SimpleNamespace(id=uuid.uuid4(), email="review@example.test", name="Auto Review")
    queries = {m: MagicMock() for m in (Asset, AssetVersion, GuestUser, Comment)}
    for q in queries.values():
        q.filter.return_value = q
        q.with_for_update.return_value = q
    queries[Asset].first.return_value = asset
    queries[AssetVersion].first.return_value = version
    queries[GuestUser].first.return_value = guest
    queries[Comment].first.return_value = None
    mock_db.query.side_effect = lambda model: queries.get(model, MagicMock())
    def flush():
        for call in mock_db.add.call_args_list:
            c = call.args[0]
            if isinstance(c, Comment):
                c.id = c.id or uuid.uuid4()
                c.created_at = c.updated_at = datetime.now(timezone.utc)
                c.resolved = False
    mock_db.flush.side_effect = flush
    def response(c, *args, **kwargs):
        from apps.api.schemas.comment import CommentResponse
        return CommentResponse.model_validate(c)
    payload = dict(asset_id=str(aid), version_id=str(vid), publication_id=str(uuid.uuid4()),
                   guest_email=guest.email, body="Keep the CTA visible.", timecode_start=2.5,
                   review_source=SOURCE)
    with patch("apps.api.routers.comments.validate_share_link_with_session", return_value=link), \
         patch("apps.api.routers.comments.validate_asset_in_share") as scope, \
         patch("apps.api.routers.comments._build_comment_response", side_effect=response):
        yield SimpleNamespace(client=client, db=mock_db, link=link, asset=asset, version=version,
                              queries=queries, scope=scope, payload=payload)


def post(s, payload=None, headers=None):
    return s.client.post("/review-bridge/share/test-token/comments", json=payload or s.payload,
                         headers=headers if headers is not None else {"Authorization": "Bearer test-bridge-secret"})


def test_service_persists_source_with_comment_atomically(service):
    response = post(service)
    assert response.status_code == 201, response.text
    c = next(c.args[0] for c in service.db.add.call_args_list if isinstance(c.args[0], Comment))
    assert c.review_source == SOURCE
    assert c.version_id == service.version.id and c.timecode_start == 2.5
    assert c.visibility == "internal"
    assert response.json()["review_source"] == SOURCE
    service.scope.assert_called_once_with(service.db, service.link, service.asset)
    service.db.commit.assert_called_once()


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
def test_service_rejects_missing_or_wrong_secret(service, headers):
    assert post(service, headers=headers).status_code == 401
    service.db.add.assert_not_called()


def test_unconfigured_secret_fails_closed(service, monkeypatch):
    monkeypatch.setattr(settings, "review_bridge_secret", "")
    assert post(service).status_code == 503
    service.db.add.assert_not_called()


def test_only_configured_automation_is_allowed(service):
    assert post(service, dict(service.payload, guest_email="client@example.test")).status_code == 403
    service.db.add.assert_not_called()


def test_foreign_asset_share_is_rejected(service):
    from fastapi import HTTPException
    service.scope.side_effect = HTTPException(403, "foreign asset")
    assert post(service).status_code == 403
    service.db.add.assert_not_called()


def test_foreign_or_deleted_version_is_rejected(service):
    service.queries[AssetVersion].first.return_value = None
    assert post(service).status_code == 404
    service.db.add.assert_not_called()


def test_view_share_cannot_publish(service):
    service.link.permission = SharePermission.view
    assert post(service).status_code == 403


def test_replay_returns_same_row_without_restoring_human_edit(service):
    first = post(service)
    assert first.status_code == 201, first.text
    c = next(c.args[0] for c in service.db.add.call_args_list if isinstance(c.args[0], Comment))
    service.queries[Comment].first.return_value = c
    c.body, c.review_source = "Human correction", None
    service.db.reset_mock()
    second = post(service)
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["body"] == "Human correction"
    assert second.json()["review_source"] is None
    service.db.add.assert_not_called()


def test_changed_payload_cannot_reuse_publication_id(service):
    assert post(service).status_code == 201
    service.queries[Comment].first.return_value = next(
        c.args[0] for c in service.db.add.call_args_list if isinstance(c.args[0], Comment))
    assert post(service, dict(service.payload, body="Different requirement")).status_code == 409


@pytest.mark.parametrize("field", ["review_source", "review_publication_id"])
@pytest.mark.parametrize("schema", ["CommentCreate", "GuestCommentCreate", "CommentUpdate"])
def test_humans_cannot_supply_service_fields(field, schema):
    from pydantic import ValidationError
    from apps.api.schemas import comment
    payload = dict(body="I am AutoReview", version_id=str(uuid.uuid4()))
    payload[field] = SOURCE if field == "review_source" else str(uuid.uuid4())
    if schema == "CommentUpdate":
        payload.pop("version_id")
    with pytest.raises(ValidationError):
        getattr(comment, schema).model_validate(payload)


def test_source_validation_bounds_deduplicates_and_rejects_quotes():
    from pydantic import ValidationError
    from apps.api.schemas.comment import ReviewSource
    source = dict(SOURCE, sources=SOURCE["sources"] * 2)
    assert len(ReviewSource.model_validate(source).sources) == 1
    for bad in [dict(SOURCE, sources=[]), dict(SOURCE, sources=SOURCE["sources"] * 9),
                dict(SOURCE, sources=[dict(SOURCE["sources"][0], layer="measured")]),
                dict(SOURCE, sources=[dict(SOURCE["sources"][0], quote="private briefing")])]:
        with pytest.raises(ValidationError):
            ReviewSource.model_validate(bad)


def test_response_omits_unknown_or_private_source_fields():
    from apps.api.schemas.comment import CommentResponse
    now = datetime.now(timezone.utc)
    values = dict(id=uuid.uuid4(), asset_id=uuid.uuid4(), version_id=uuid.uuid4(), parent_id=None,
                  author_id=None, guest_author_id=None, timecode_start=None, timecode_end=None,
                  body="Text", resolved=False, created_at=now, updated_at=now)
    assert CommentResponse(**values).model_dump()["review_source"] is None
    bad = dict(SOURCE, sources=[dict(SOURCE["sources"][0], quote="private briefing")])
    serialized = CommentResponse(**values, review_source=bad).model_dump_json()
    assert "private briefing" not in serialized
    assert CommentResponse(**values, review_source=dict(SOURCE, schema_version="v0")).review_source is None


def test_human_text_edit_clears_source_but_resolve_does_not(client, mock_db, auth_headers, test_user):
    from apps.api.schemas.comment import CommentResponse
    now = datetime.now(timezone.utc)
    c = Comment(id=uuid.uuid4(), asset_id=uuid.uuid4(), version_id=uuid.uuid4(), parent_id=None,
                author_id=test_user.id, guest_author_id=None, body="Original", resolved=False, visibility="public",
                created_at=now, updated_at=now, review_source=SOURCE)
    mock_db.first.return_value = c
    with patch("apps.api.routers.comments.require_asset_access"), \
         patch("apps.api.routers.comments._get_asset", return_value=SimpleNamespace(project_id=uuid.uuid4())), \
         patch("apps.api.routers.comments._build_comment_response", side_effect=lambda c, *a, **k: CommentResponse.model_validate(c)):
        resolved = client.post(f"/comments/{c.id}/resolve", headers=auth_headers)
        assert resolved.status_code == 200, resolved.text
        assert c.review_source == SOURCE
        edited = client.patch(f"/comments/{c.id}", json={"body": "Human edit"}, headers=auth_headers)
        assert edited.status_code == 200, edited.text
        assert c.review_source is None
