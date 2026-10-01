"""Editor completion requires the reviewed bytes, not an old green gate."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from apps.api.models.asset import Asset, AssetVersion, AssetType, ProcessingStatus
from apps.api.models.upload_request import UploadRequest, RequestUpload
from apps.api.routers import requests as rq


def request():
    return UploadRequest(id=uuid.uuid4(), token='t', project_id=uuid.uuid4(), folder_id=uuid.uuid4(),
                         created_by=uuid.uuid4(), title='Launch', review_share_token='s')


def test_transfer_can_start_without_identity_but_not_with_a_partial_identity():
    body = dict(original_filename='cut.mp4', mime_type='video/mp4', file_size_bytes=100)
    assert rq.GuestInitiate(**body).name is None
    with pytest.raises(ValueError):
        rq.GuestInitiate(**body, name='Editor')
    with pytest.raises(ValueError):
        rq.GuestInitiate(**body, name='   ', email='editor@example.com')


def test_exact_review_evidence_never_carries_v1_approval_into_v2():
    v = AssetVersion(id=uuid.uuid4(), version_number=2, processing_status=ProcessingStatus.ready)
    assert rq.editor_review_state(v, None) == 'unavailable'
    assert rq.editor_review_state(v, {'reviewed': True, 'versions': 2, 'openMustFix': 0}) == 'unavailable'
    evidence = {'reviewed': True, 'version_id': str(v.id), 'openMustFix': 0}
    assert rq.editor_review_state(v, evidence) == 'clear'
    assert rq.editor_review_state(v, {**evidence, 'version_id': str(uuid.uuid4())}) == 'reviewing'
    assert rq.editor_review_state(v, {**evidence, 'openMustFix': 1}) == 'held'
    v.processing_status = ProcessingStatus.processing
    assert rq.editor_review_state(v, evidence) == 'reviewing'


def test_complete_requires_identity_before_s3_finalization(monkeypatch):
    req = request()
    version = AssetVersion(id=uuid.uuid4(), asset_id=uuid.uuid4(), version_number=1, processing_status=ProcessingStatus.uploading)
    monkeypatch.setattr(rq, '_live_request', lambda *a: req)
    monkeypatch.setattr(rq, 'locked_request', lambda *a: req)
    monkeypatch.setattr(rq, '_owned_media', lambda *a: (MagicMock(), version))
    complete = MagicMock()
    monkeypatch.setattr(rq, 'complete_multipart_upload', complete)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as err:
        rq.guest_complete('t', rq.GuestComplete(s3_key='raw/a', upload_id='u', parts=[]), BackgroundTasks(), db)
    assert err.value.status_code == 422
    complete.assert_not_called()


def test_finished_request_rejects_new_upload_but_remains_live(monkeypatch):
    req = request()
    req.completed_at = datetime.now(timezone.utc)
    assert rq.request_state(req, datetime.now(timezone.utc)) == 'live'
    monkeypatch.setattr(rq, '_live_request', lambda *a: req)
    monkeypatch.setattr(rq, 'locked_request', lambda *a: req)
    with pytest.raises(HTTPException) as err:
        rq.guest_initiate('t', rq.GuestInitiate(original_filename='cut.mp4', mime_type='video/mp4', file_size_bytes=100), MagicMock())
    assert err.value.status_code == 409


def test_version_lookup_rejects_foreign_asset_before_any_media_lookup(monkeypatch):
    req = request()
    monkeypatch.setattr(rq, '_live_request', lambda *a: req)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as err:
        rq.guest_version('t', uuid.uuid4(), uuid.uuid4(), db)
    assert err.value.status_code == 404


def test_finish_requires_every_current_asset_and_persists_exact_versions(monkeypatch):
    req = request()
    monkeypatch.setattr(rq, '_live_request', lambda *a: req)
    monkeypatch.setattr(rq, 'locked_request', lambda *a: req)
    data = {'assets': [{'asset_id': 'a', 'version_id': 'v2', 'review_state': 'reviewing'}],
            'gate': {'status': 'clear', 'open_must_fixes': 0}}
    monkeypatch.setattr(rq, '_editor_review', lambda *a: data)
    db = MagicMock()
    with pytest.raises(HTTPException) as err:
        rq.finish_request('t', db)
    assert err.value.status_code == 409
    assert req.completed_at is None
    data['assets'][0]['review_state'] = 'clear'
    result = rq.finish_request('t', db)
    assert result['completed_at']
    assert result['completion_versions'] == {'a': 'v2'}
    assert rq.finish_request('t', db) == result
    db.commit.assert_called_once()


def test_completed_version_cannot_be_aborted_into_failed(monkeypatch):
    req = request()
    version = AssetVersion(id=uuid.uuid4(), processing_status=ProcessingStatus.ready)
    monkeypatch.setattr(rq, '_live_request', lambda *a: req)
    monkeypatch.setattr(rq, 'locked_request', lambda *a: req)
    monkeypatch.setattr(rq, '_owned_media', lambda *a: (None, version))
    abort = MagicMock()
    monkeypatch.setattr(rq, 'abort_multipart_upload', abort)
    rq.guest_abort('t', rq.GuestPart(s3_key='raw/a', upload_id='u', part_number=1), MagicMock())
    abort.assert_not_called()
    assert version.processing_status == ProcessingStatus.ready


def test_old_version_objection_is_rejected_before_engine_call(monkeypatch):
    req = request()
    asset = Asset(id=uuid.uuid4(), folder_id=req.folder_id, project_id=req.project_id, asset_type=AssetType.video)
    current = AssetVersion(id=uuid.uuid4(), asset_id=asset.id, version_number=2, processing_status=ProcessingStatus.ready)
    monkeypatch.setattr(rq, '_live_request', lambda *a: req)
    monkeypatch.setattr(rq, 'locked_request', lambda *a: req)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = asset
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = current
    engine = MagicMock()
    monkeypatch.setattr(rq.review_bridge, 'object_to_note', engine)
    with pytest.raises(HTTPException) as err:
        rq.guest_object('t', rq.GuestObjection(asset_id=asset.id, version_id=uuid.uuid4(), text='This was already fixed.'), db)
    assert err.value.status_code == 409
    engine.assert_not_called()


def test_request_rejects_media_the_automatic_reviewer_cannot_verify(monkeypatch):
    req = request()
    monkeypatch.setattr(rq, '_live_request', lambda *a: req)
    monkeypatch.setattr(rq, 'locked_request', lambda *a: req)
    start = MagicMock()
    monkeypatch.setattr(rq, 'upload_guard_error', lambda *a: None)
    monkeypatch.setattr(rq, 'create_multipart_upload', start)
    with pytest.raises(HTTPException) as err:
        rq.guest_initiate('t', rq.GuestInitiate(original_filename='photo.jpg', mime_type='image/jpeg', file_size_bytes=100), MagicMock())
    assert err.value.status_code == 400
    assert 'video' in err.value.detail.lower()
    start.assert_not_called()


def test_existing_thumbnails_are_exposed_but_audio_waveforms_are_not_images(monkeypatch):
    from apps.api.models.asset import MediaFile
    req = request()
    asset = Asset(id=uuid.uuid4(), name='Cut', asset_type=AssetType.video)
    version = AssetVersion(id=uuid.uuid4(), version_number=2, processing_status=ProcessingStatus.processing)
    media = MediaFile(version_id=version.id, s3_key_raw='v2/raw.mp4', s3_key_thumbnail='v2/thumb.jpg')
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = media
    monkeypatch.setattr(rq.s3_service, 'generate_presigned_get_url', lambda key: 'signed/' + key)
    result = rq._version_review(db, req, asset, version, None, None)
    assert result['thumbnail_url'] == 'signed/v2/thumb.jpg'
    assert result['media_url'] == 'signed/v2/raw.mp4'
    media.s3_key_thumbnail = None
    assert rq._version_review(db, req, asset, version, None, None)['thumbnail_url'] is None
    asset.asset_type = AssetType.audio
    media.s3_key_thumbnail = 'waveform.json'
    assert rq._version_review(db, req, asset, version, None, None)['thumbnail_url'] is None

