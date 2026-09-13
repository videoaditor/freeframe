"""One project per BRAND, one folder per card.

Aditor files each hand-in as a folder now. That moves the thing the review depends on: the Trello
card link, which is what says which brand's rules to judge against, which script to check, and
which editor cut it. On a per-card project it lived in the project description; on a per-brand
project it has to live on the folder, and folders had no description at all until this.

The far side needs no change. Auto Review keys everything on a share TOKEN and never asks whether
that token shows a project or a folder, so a folder announces itself through the same endpoint
with the same field names.
"""
import uuid
from unittest.mock import MagicMock

import pytest


def test_no_standing_folder_link_when_no_webhook_is_configured():
    from apps.api.services import automation_share
    from apps.api.config import settings
    settings.automation_share_webhook_url = ""
    assert automation_share.create_standing_folder_link(
        MagicMock(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ) is None


def test_the_folder_link_is_scoped_to_the_folder_and_can_comment():
    # Scoped deliberately. A project-wide link would hand the review every other card's cuts for
    # the same brand, and it would read them all again on every new hand-in.
    from apps.api.services import automation_share
    from apps.api.config import settings
    from apps.api.models.share import SharePermission
    settings.automation_share_webhook_url = "https://example.invalid/hook"
    folder_id = uuid.uuid4()
    link = automation_share.create_standing_folder_link(
        MagicMock(), uuid.uuid4(), folder_id, uuid.uuid4()
    )
    assert link.folder_id == folder_id
    assert link.project_id is None          # exactly one of asset / folder / project, per the model
    assert link.permission == SharePermission.comment
    assert link.allow_download is True
    assert link.expires_at is None
    settings.automation_share_webhook_url = ""


def test_a_folder_announces_itself_like_a_project(monkeypatch):
    # Same endpoint, same field names: the folder's NAME arrives as project_name and the folder's
    # description as description, because that is where the card link now lives.
    from apps.api.services import automation_share
    from apps.api.config import settings
    settings.automation_share_webhook_url = "https://example.invalid/hook"
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return MagicMock(status_code=200)

    monkeypatch.setattr(automation_share.httpx, "post", fake_post)
    folder = MagicMock()
    folder.id = uuid.uuid4()
    folder.project_id = uuid.uuid4()
    folder.name = "UraVia 48"
    folder.description = "https://trello.com/c/abc123"
    link = MagicMock()
    link.token = "tok"
    automation_share.announce_folder(folder, link)
    assert sent["json"]["project_name"] == "UraVia 48"
    assert sent["json"]["description"] == "https://trello.com/c/abc123"
    assert sent["json"]["share_token"] == "tok"
    assert sent["json"]["folder_id"] == str(folder.id)
    settings.automation_share_webhook_url = ""


def test_a_failing_webhook_never_breaks_folder_creation(monkeypatch):
    # A folder the automation never hears about is an unreviewed hand-in. A folder that could not
    # be created is an editor who cannot work. Only one of those is acceptable.
    from apps.api.services import automation_share
    from apps.api.config import settings
    settings.automation_share_webhook_url = "https://example.invalid/hook"

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(automation_share.httpx, "post", boom)
    folder = MagicMock()
    folder.id = uuid.uuid4()
    folder.project_id = uuid.uuid4()
    folder.name = "n"
    folder.description = ""
    automation_share.announce_folder(folder, MagicMock())   # must not raise
    settings.automation_share_webhook_url = ""


def test_the_card_link_can_be_required_on_a_folder():
    # The same protection projects already have, one level down. Without it a hand-in is created,
    # reviewed against nothing, and nobody finds out until they ask why no review came.
    from apps.api.routers.folders import _check_folder_description_requirement
    from apps.api.config import settings
    from fastapi import HTTPException

    settings.require_folder_description_pattern = ""
    _check_folder_description_requirement(None)             # off by default: anything passes

    settings.require_folder_description_pattern = r"trello\.com/c/"
    settings.require_folder_description_hint = "Paste the Trello card link."
    _check_folder_description_requirement("https://trello.com/c/abc123")
    with pytest.raises(HTTPException) as e:
        _check_folder_description_requirement("no link here")
    assert e.value.status_code == 400
    assert "Trello" in e.value.detail
    settings.require_folder_description_pattern = ""
    settings.require_folder_description_hint = ""


def test_asset_ready_prefers_the_folder_link(monkeypatch):
    # An asset inside a hand-in belongs to that hand-in. Announcing the project-wide link instead
    # would point the review at every other card for the same brand.
    from apps.api.services import automation_share
    from apps.api.config import settings
    settings.automation_share_webhook_url = "https://example.invalid/hook"
    folder_link = MagicMock(); folder_link.token = "folder-token"
    monkeypatch.setattr(automation_share, "_folder_standing_link", lambda db, fid: folder_link)
    monkeypatch.setattr(automation_share, "_standing_link", lambda db, pid: MagicMock(token="project-token"))
    sent = {}
    monkeypatch.setattr(automation_share.httpx, "post",
                        lambda url, json=None, headers=None, timeout=None: sent.update(json or {}) or MagicMock())
    asset = MagicMock()
    asset.id = uuid.uuid4(); asset.project_id = uuid.uuid4(); asset.folder_id = uuid.uuid4(); asset.name = "cut.mp4"
    automation_share.announce_asset_ready(MagicMock(), asset, uuid.uuid4())
    assert sent["share_token"] == "folder-token"
    settings.automation_share_webhook_url = ""
