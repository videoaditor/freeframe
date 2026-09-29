"""Regression tests for the AI-review proxy endpoint.

GET /share/{token}/stream/{asset_id}/ai-proxy — a single small MP4 (the lowest HLS rendition,
remuxed at transcode time) for an automated frame-sampling reader, instead of the full original.
Additive and best-effort: 404 whenever no proxy exists, so an old client's fallback to
?download=1 behaves exactly as before this endpoint existed.
"""
import uuid
from unittest.mock import MagicMock, patch


@patch("apps.api.routers.share.object_exists")
@patch("apps.api.routers.share.generate_presigned_get_url")
@patch("apps.api.routers.share._get_latest_media_file")
@patch("apps.api.routers.share._get_asset")
@patch("apps.api.routers.share.validate_share_link_with_session")
def test_returns_presigned_url_when_proxy_exists(
    mock_validate, mock_get_asset, mock_get_latest_media_file, mock_presign, mock_exists,
    client, mock_db,
):
    from apps.api.models.asset import AssetType

    asset_id = uuid.uuid4()
    link = MagicMock()
    link.id = uuid.uuid4()
    link.folder_id = None
    link.asset_id = asset_id
    link.project_id = None
    mock_validate.return_value = link

    asset = MagicMock()
    asset.id = asset_id
    asset.asset_type = AssetType.video
    mock_get_asset.return_value = asset

    media_file = MagicMock()
    media_file.s3_key_processed = "processed/proj/version-abc"
    mock_get_latest_media_file.return_value = media_file

    mock_exists.return_value = True
    mock_presign.return_value = "https://s3.example/presigned"

    resp = client.get(f"/share/tok123/stream/{asset_id}/ai-proxy")

    assert resp.status_code == 200
    assert resp.json() == {"url": "https://s3.example/presigned"}
    mock_exists.assert_called_once_with("processed/proj/version-abc/ai_proxy.mp4")
    mock_presign.assert_called_once_with("processed/proj/version-abc/ai_proxy.mp4")


@patch("apps.api.routers.share.object_exists")
@patch("apps.api.routers.share._get_latest_media_file")
@patch("apps.api.routers.share._get_asset")
@patch("apps.api.routers.share.validate_share_link_with_session")
def test_404_when_proxy_was_never_made(
    mock_validate, mock_get_asset, mock_get_latest_media_file, mock_exists, client, mock_db,
):
    """The remux is best-effort at transcode time (see ffmpeg_transcoder.py step 4.5) - an
    older asset, or one where ffmpeg failed on just this step, must 404 cleanly so the caller
    falls back to the original rather than getting a broken URL."""
    from apps.api.models.asset import AssetType

    asset_id = uuid.uuid4()
    link = MagicMock()
    link.folder_id = None
    link.asset_id = asset_id
    link.project_id = None
    mock_validate.return_value = link

    asset = MagicMock()
    asset.id = asset_id
    asset.asset_type = AssetType.video
    mock_get_asset.return_value = asset

    media_file = MagicMock()
    media_file.s3_key_processed = "processed/proj/version-old"
    mock_get_latest_media_file.return_value = media_file

    mock_exists.return_value = False

    resp = client.get(f"/share/tok123/stream/{asset_id}/ai-proxy")

    assert resp.status_code == 404


@patch("apps.api.routers.share._get_asset")
@patch("apps.api.routers.share.validate_share_link_with_session")
def test_404_for_a_non_video_asset(mock_validate, mock_get_asset, client, mock_db):
    """An image or audio asset never gets a video proxy - fail clean, not a 500."""
    from apps.api.models.asset import AssetType

    asset_id = uuid.uuid4()
    link = MagicMock()
    link.folder_id = None
    link.asset_id = asset_id
    link.project_id = None
    mock_validate.return_value = link

    asset = MagicMock()
    asset.id = asset_id
    asset.asset_type = AssetType.image
    mock_get_asset.return_value = asset

    resp = client.get(f"/share/tok123/stream/{asset_id}/ai-proxy")

    assert resp.status_code == 404


@patch("apps.api.routers.share._get_latest_media_file")
@patch("apps.api.routers.share._get_asset")
@patch("apps.api.routers.share.validate_share_link_with_session")
def test_404_when_no_ready_media_file(mock_validate, mock_get_asset, mock_get_latest_media_file, client, mock_db):
    from apps.api.models.asset import AssetType

    asset_id = uuid.uuid4()
    link = MagicMock()
    link.folder_id = None
    link.asset_id = asset_id
    link.project_id = None
    mock_validate.return_value = link

    asset = MagicMock()
    asset.id = asset_id
    asset.asset_type = AssetType.video
    mock_get_asset.return_value = asset

    mock_get_latest_media_file.return_value = None

    resp = client.get(f"/share/tok123/stream/{asset_id}/ai-proxy")

    assert resp.status_code == 404
