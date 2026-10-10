"""The actual call sites: POST /upload/complete and POST /share/{token}/comment announce to the
hub. test_hub_events.py covers the service's own logic in isolation; these pin that the two
routers actually reach it, with a faked webhook sink standing in for the hub.
"""
import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import BackgroundTasks

from apps.api.config import settings
from apps.api.models.asset import Asset, AssetVersion, MediaFile, ProcessingStatus
from apps.api.models.project import Project
from apps.api.models.upload_request import UploadRequest
from apps.api.models.share import SharePermission


def test_complete_upload_announces_revision_submitted_for_a_handin(monkeypatch):
    import apps.api.routers.upload as upload_module
    from apps.api.services import hub_events

    settings.hub_events_webhook_url = "https://hub.aditor.ai/api/revision/freeframe-webhook"
    try:
        user_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        version_id = uuid.uuid4()
        folder_id = uuid.uuid4()

        version = SimpleNamespace(id=version_id, asset_id=asset_id, created_by=user_id,
                                  processing_status=ProcessingStatus.uploading)
        media = SimpleNamespace(version_id=version_id, s3_key_raw="raw/key")
        asset = SimpleNamespace(id=asset_id, folder_id=folder_id, project_id=uuid.uuid4())
        req = SimpleNamespace(folder_id=folder_id, last_uploader_email="editor@aditor.ai",
                              iteration_state={"internal_handin": {"card_url": "https://trello.com/c/abc12345"}})

        def fake_query(model):
            q = MagicMock()
            table = {AssetVersion: version, MediaFile: media, Asset: asset, UploadRequest: req}
            q.filter.return_value.first.return_value = table.get(model)
            return q

        db = MagicMock()
        db.query = MagicMock(side_effect=fake_query)
        db.get = MagicMock(side_effect=lambda model, _id: asset if model is Asset else None)

        monkeypatch.setattr(upload_module, "_campaign_upload_access", lambda db, version: None)
        monkeypatch.setattr(upload_module, "require_unmanaged", lambda asset: None)
        monkeypatch.setattr(upload_module, "complete_multipart_upload", lambda *a, **k: None)

        sent = {}
        monkeypatch.setattr(hub_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())

        body = upload_module.CompleteUploadRequest(
            s3_key="raw/key", upload_id="up1", asset_id=asset_id, version_id=version_id, parts=[],
        )
        current_user = SimpleNamespace(id=user_id)
        response = upload_module.complete_upload(body, BackgroundTasks(), db, current_user)

        assert response.status == "processing"
        assert sent == {
            "event": "revision_submitted",
            "card_url": "https://trello.com/c/abc12345",
            "editor_email": "editor@aditor.ai",
            "version_id": str(version_id),
        }
    finally:
        settings.hub_events_webhook_url = ""


def test_complete_upload_announces_nothing_for_a_plain_upload(monkeypatch):
    """No hand-in behind the asset (an ordinary project upload) - the webhook stays silent."""
    import apps.api.routers.upload as upload_module
    from apps.api.services import hub_events

    settings.hub_events_webhook_url = "https://example.invalid/hook"
    try:
        user_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        version_id = uuid.uuid4()

        version = SimpleNamespace(id=version_id, asset_id=asset_id, created_by=user_id,
                                  processing_status=ProcessingStatus.uploading)
        media = SimpleNamespace(version_id=version_id, s3_key_raw="raw/key")
        asset = SimpleNamespace(id=asset_id, folder_id=None, project_id=uuid.uuid4())

        def fake_query(model):
            q = MagicMock()
            table = {AssetVersion: version, MediaFile: media, Asset: asset, UploadRequest: None}
            q.filter.return_value.first.return_value = table.get(model)
            return q

        db = MagicMock()
        db.query = MagicMock(side_effect=fake_query)
        db.get = MagicMock(side_effect=lambda model, _id: asset if model is Asset else None)

        monkeypatch.setattr(upload_module, "_campaign_upload_access", lambda db, version: None)
        monkeypatch.setattr(upload_module, "require_unmanaged", lambda asset: None)
        monkeypatch.setattr(upload_module, "complete_multipart_upload", lambda *a, **k: None)

        post = MagicMock()
        monkeypatch.setattr(hub_events.httpx, "post", post)

        body = upload_module.CompleteUploadRequest(
            s3_key="raw/key", upload_id="up1", asset_id=asset_id, version_id=version_id, parts=[],
        )
        current_user = SimpleNamespace(id=user_id)
        upload_module.complete_upload(body, BackgroundTasks(), db, current_user)

        post.assert_not_called()
    finally:
        settings.hub_events_webhook_url = ""


def test_guest_comment_on_a_handin_version_announces_client_comment(monkeypatch):
    import apps.api.routers.comments as comments_module
    from apps.api.services import hub_events

    settings.hub_events_webhook_url = "https://hub.aditor.ai/api/revision/freeframe-webhook"
    try:
        folder_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        version_id = uuid.uuid4()

        link = SimpleNamespace(id=uuid.uuid4(), asset_id=asset_id, permission=SharePermission.comment)
        asset = SimpleNamespace(id=asset_id, folder_id=folder_id, name="cut.mp4")
        req = SimpleNamespace(folder_id=folder_id, last_uploader_email="editor@aditor.ai",
                              iteration_state={"internal_handin": {"card_url": "https://trello.com/c/abc12345"}})

        monkeypatch.setattr(comments_module, "validate_share_link_with_session", lambda *a, **k: link)
        monkeypatch.setattr(comments_module, "_get_asset", lambda db, asset_id_: asset)
        monkeypatch.setattr(comments_module, "validate_asset_in_share", lambda *a, **k: None)
        monkeypatch.setattr(comments_module, "validate_comment_version", lambda *a, **k: None)
        monkeypatch.setattr(comments_module, "_build_comment_response", lambda comment, db: {"id": str(comment.id)})

        existing_guest = SimpleNamespace(id=uuid.uuid4(), email="client@brand.com", name="A Client")

        def fake_query(model):
            q = MagicMock()
            if model is UploadRequest:
                q.filter.return_value.first.return_value = req
            elif model is comments_module.GuestUser:
                # An existing guest, so the code takes the "seen before" branch rather than
                # constructing a new GuestUser whose id would only be assigned by a real flush.
                q.filter.return_value.first.return_value = existing_guest
            else:
                q.filter.return_value.first.return_value = None
            return q

        db = MagicMock()
        db.query = MagicMock(side_effect=fake_query)

        sent = {}
        monkeypatch.setattr(hub_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())

        from apps.api.schemas.comment import GuestCommentCreate
        body = GuestCommentCreate(version_id=version_id, body="Make the logo bigger",
                                  guest_email="client@brand.com", guest_name="A Client")
        comments_module.guest_comment(token="tok", body=body, share_session=None, db=db,
                                      current_user=None, authorization=None)

        assert sent == {
            "event": "client_comment",
            "card_url": "https://trello.com/c/abc12345",
            "editor_email": "editor@aditor.ai",
            "comment": {"id": sent["comment"]["id"], "body": "Make the logo bigger", "author_name": "A Client"},
            "version_id": str(version_id),
        }
    finally:
        settings.hub_events_webhook_url = ""


def test_guest_comment_from_the_automation_reviewer_announces_nothing(monkeypatch):
    """The craft reviewer posts as a guest too, but its comments are stored visibility="internal" -
    never a client ask, so the webhook must stay silent even though guest_author_id is set."""
    import apps.api.routers.comments as comments_module
    from apps.api.services import hub_events

    settings.hub_events_webhook_url = "https://example.invalid/hook"
    original_automation_guest_emails = settings.automation_guest_emails
    settings.automation_guest_emails = "review@aditor.ai"
    try:
        folder_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        version_id = uuid.uuid4()

        link = SimpleNamespace(id=uuid.uuid4(), asset_id=asset_id, permission=SharePermission.comment)
        asset = SimpleNamespace(id=asset_id, folder_id=folder_id, name="cut.mp4")

        monkeypatch.setattr(comments_module, "validate_share_link_with_session", lambda *a, **k: link)
        monkeypatch.setattr(comments_module, "_get_asset", lambda db, asset_id_: asset)
        monkeypatch.setattr(comments_module, "validate_asset_in_share", lambda *a, **k: None)
        monkeypatch.setattr(comments_module, "validate_comment_version", lambda *a, **k: None)
        monkeypatch.setattr(comments_module, "_build_comment_response", lambda comment, db: {"id": str(comment.id)})

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        post = MagicMock()
        monkeypatch.setattr(hub_events.httpx, "post", post)

        from apps.api.schemas.comment import GuestCommentCreate
        body = GuestCommentCreate(version_id=version_id, body="Must fix - color is off",
                                  guest_email="review@aditor.ai", guest_name="Auto Review")
        comments_module.guest_comment(token="tok", body=body, share_session=None, db=db,
                                      current_user=None, authorization=None)

        post.assert_not_called()
    finally:
        settings.hub_events_webhook_url = ""
        settings.automation_guest_emails = original_automation_guest_emails
