"""Voice feedback must survive transcription failures and stay private."""
import base64
import hashlib
import io
import uuid
import wave
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def recording_dependencies(mock_db):
    mock_db.with_for_update.return_value = mock_db
    with patch('apps.api.middleware.rate_limit.check_rate_limit', return_value=(True, 0)):
        yield


def wav(seconds=0.1):
    out = io.BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\0\0' * int(16000 * seconds))
    return out.getvalue()


def recording(user, **changes):
    return SimpleNamespace(id=uuid.uuid4(), author_id=user.id, s3_key='product-feedback/audio/test.wav',
                           content_sha256=hashlib.sha256(wav()).hexdigest(), transcript=None, **changes)


def upload(client, headers, content=None, mime='audio/wav', id=None):
    return client.post('/product-feedback/recordings', headers=headers,
                       data={'recording_id': str(id or uuid.uuid4())},
                       files={'file': ('untrusted.html', wav() if content is None else content, mime)})


def test_recording_requires_authentication(client):
    assert upload(client, {}).status_code == 401


def test_upload_saves_original_before_receipt(client, auth_headers, test_user, mock_db):
    with patch('apps.api.services.s3_service.put_object') as put:
        response = upload(client, auth_headers)
    assert response.status_code == 201
    row = mock_db.add.call_args.args[0]
    assert response.json() == {'id': str(row.id), 'status': 'saved'}
    assert row.author_id == test_user.id
    assert row.s3_key.startswith('product-feedback/audio/')
    assert 'untrusted' not in row.s3_key
    assert put.call_args.args[1] == wav()
    mock_db.commit.assert_called_once()


@pytest.mark.parametrize('mime,content,code', [('text/html', b'<html>', 415), ('audio/wav', b'fake', 415), ('audio/wav', b'x'* (8*1024*1024+1), 413), ('audio/wav', wav(120.1), 422)], ids=['mime', 'signature', 'size', 'duration'])
def test_upload_rejects_invalid_audio(client, auth_headers, mock_db, mime, content, code):
    with patch('apps.api.services.s3_service.put_object') as put:
        assert upload(client, auth_headers, content, mime).status_code == code
    put.assert_not_called()
    mock_db.commit.assert_not_called()


def test_upload_retry_returns_same_receipt_without_rewriting(client, auth_headers, test_user, mock_db):
    row = recording(test_user)
    mock_db.first.return_value = row
    with patch('apps.api.services.s3_service.put_object') as put:
        response = upload(client, auth_headers, id=row.id)
    assert response.json() == {'id': str(row.id), 'status': 'saved'}
    put.assert_not_called()
    assert upload(client, auth_headers, wav(.2), id=row.id).status_code == 409


@pytest.mark.parametrize('method,path', [('get', ''), ('post', '/transcribe')])
def test_other_owner_cannot_access_recording(client, auth_headers, test_user, mock_db, method, path):
    row = recording(SimpleNamespace(id=uuid.uuid4()))
    mock_db.first.return_value = row
    test_user.is_staff = False
    assert getattr(client, method)(f'/product-feedback/recordings/{row.id}{path}', headers=auth_headers).status_code == 404


def test_playback_owner_and_staff_get_private_link(client, auth_headers, test_user, mock_db):
    row = recording(test_user)
    mock_db.first.return_value = row
    with patch('apps.api.services.s3_service.generate_presigned_get_url', return_value='https://private/signed') as presign:
        assert client.get(f'/product-feedback/recordings/{row.id}', headers=auth_headers).json() == {'id': str(row.id), 'url': 'https://private/signed', 'transcript': None}
        assert presign.call_args.kwargs['expires_in'] <= 300
        row.author_id = uuid.uuid4()
        test_user.is_staff = True
        assert client.get(f'/product-feedback/recordings/{row.id}', headers=auth_headers).status_code == 200


def test_unconfigured_transcription_preserves_saved_audio(client, auth_headers, test_user, mock_db, monkeypatch):
    from apps.api.config import settings
    monkeypatch.setattr(settings, 'wispr_api_key', '')
    row = recording(test_user)
    mock_db.first.return_value = row
    response = client.post(f'/product-feedback/recordings/{row.id}/transcribe', headers=auth_headers)
    assert response.json() == {'status': 'unavailable', 'text': None}
    assert row.s3_key == 'product-feedback/audio/test.wav'
    mock_db.commit.assert_not_called()


def test_provider_failure_preserves_audio_then_retry_caches_text(client, auth_headers, test_user, mock_db, monkeypatch):
    from apps.api.config import settings
    monkeypatch.setattr(settings, 'wispr_api_key', 'test-key')
    row = recording(test_user)
    mock_db.first.return_value = row
    with patch('apps.api.services.s3_service.get_s3_client') as s3, patch('apps.api.services.feedback_recordings.httpx.post') as post:
        s3.return_value.get_object.return_value = {'Body': io.BytesIO(wav())}
        post.side_effect = httpx.ReadTimeout('timed out')
        endpoint = f'/product-feedback/recordings/{row.id}/transcribe'
        assert client.post(endpoint, headers=auth_headers).json() == {'status': 'failed', 'text': None}
        assert row.transcript is None
        assert row.s3_key == 'product-feedback/audio/test.wav'
        s3.return_value.get_object.return_value = {'Body': io.BytesIO(wav())}
        post.side_effect = None
        post.return_value = httpx.Response(200, json={'text': 'Upload does not work.'}, request=httpx.Request('POST', settings.wispr_api_url))
        assert client.post(endpoint, headers=auth_headers).json() == {'status': 'transcribed', 'text': 'Upload does not work.'}
        assert post.call_args.kwargs['headers'] == {'Authorization': 'Bearer test-key'}
        converted = base64.b64decode(post.call_args.kwargs['json']['audio'])
        with wave.open(io.BytesIO(converted)) as audio:
            assert audio.getframerate() == 16000
        assert client.post(endpoint, headers=auth_headers).json()['text'] == 'Upload does not work.'
        assert post.call_count == 2


def test_audio_only_feedback_attaches_owned_recording(client, auth_headers, test_user, mock_db):
    row = recording(test_user)
    mock_db.first.side_effect = [None, row]
    response = client.post('/product-feedback', headers=auth_headers, json={'submission_id': str(uuid.uuid4()), 'kind': 'idea', 'message': '', 'recording_id': str(row.id)})
    assert response.status_code == 201
    saved = mock_db.add.call_args.args[0]
    assert saved.recording_id == row.id
    assert saved.message == ''


def test_feedback_cannot_attach_other_users_audio(client, auth_headers, test_user, mock_db):
    row = recording(SimpleNamespace(id=uuid.uuid4()))
    mock_db.first.side_effect = [None, row]
    response = client.post('/product-feedback', headers=auth_headers, json={'submission_id': str(uuid.uuid4()), 'kind': 'bug', 'message': 'Bug', 'recording_id': str(row.id)})
    assert response.status_code == 404
    mock_db.add.assert_not_called()


@pytest.mark.parametrize('operation', ['upload', 'transcribe', 'playback'])
def test_unknown_recording_and_other_owner_never_authorize(client, auth_headers, test_user, mock_db, operation):
    row = recording(SimpleNamespace(id=uuid.uuid4()))
    mock_db.first.return_value = row
    test_user.is_staff = False
    if operation == 'upload':
        response = upload(client, auth_headers, id=row.id)
    elif operation == 'transcribe':
        # Even staff cannot spend transcription requests on another user's audio.
        test_user.is_staff = True
        response = client.post(f'/product-feedback/recordings/{row.id}/transcribe', headers=auth_headers)
    else:
        mock_db.first.return_value = None
        response = client.get(f'/product-feedback/recordings/{row.id}', headers=auth_headers)
    assert response.status_code == 404


def test_concurrent_upload_returns_committed_receipt(client, auth_headers, test_user, mock_db):
    from sqlalchemy.exc import IntegrityError
    row = recording(test_user)
    mock_db.first.side_effect = [None, row]
    mock_db.commit.side_effect = IntegrityError('insert', {}, Exception())
    with patch('apps.api.services.s3_service.put_object'):
        response = upload(client, auth_headers, id=row.id)
    assert response.status_code == 201
    assert response.json()['id'] == str(row.id)
    mock_db.rollback.assert_called_once()


def test_storage_failure_never_claims_recording_saved(client, auth_headers, mock_db):
    with patch('apps.api.services.s3_service.put_object', side_effect=RuntimeError('storage down')):
        assert upload(client, auth_headers).status_code == 500
    mock_db.commit.assert_not_called()


def test_feedback_retry_with_recording_returns_original_receipt(client, auth_headers, test_user, mock_db):
    existing = SimpleNamespace(id=uuid.uuid4())
    mock_db.first.return_value = existing
    response = client.post('/product-feedback', headers=auth_headers, json={
        'submission_id': str(uuid.uuid4()), 'kind': 'idea', 'recording_id': str(uuid.uuid4()),
    })
    assert response.status_code == 201
    assert response.json()['id'] == str(existing.id)
    mock_db.add.assert_not_called()


@pytest.mark.parametrize('container,codec,mime', [('webm', 'libopus', 'audio/webm;codecs=opus'), ('ogg', 'libopus', 'audio/ogg'), ('mp4', 'aac', 'audio/mp4')])
def test_browser_audio_containers_are_saved_and_normalized(client, auth_headers, mock_db, tmp_path, container, codec, mime):
    import subprocess
    source, target = tmp_path / 'source.wav', tmp_path / f'browser.{container}'
    source.write_bytes(wav())
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source), '-c:a', codec, str(target)], check=True, timeout=10)
    original = target.read_bytes()
    with patch('apps.api.services.s3_service.put_object') as put:
        assert upload(client, auth_headers, original, mime).status_code == 201
    assert put.call_args.args[1] == original


def test_conversion_timeout_is_bounded_and_does_not_save_invalid_audio(client, auth_headers, mock_db):
    import subprocess
    with patch('apps.api.services.feedback_recordings.subprocess.run', side_effect=subprocess.TimeoutExpired('ffmpeg', 30)):
        assert upload(client, auth_headers).status_code == 422
    mock_db.commit.assert_not_called()


def test_audio_only_digest_tells_staff_to_play_saved_recording():
    from apps.api.services.product_feedback import format_digest
    row = SimpleNamespace(kind='bug', message='', tool='autoreview', campaign_id=None, recording_id=uuid.uuid4())
    text = format_digest([row], 'https://review.example.com')
    assert 'Voice recording' in text
    assert 'https://review.example.com/feedback' in text


@pytest.mark.parametrize('operation', ['upload', 'transcribe'])
def test_expensive_recording_routes_are_rate_limited(client, auth_headers, operation):
    with patch('apps.api.middleware.rate_limit.check_rate_limit', return_value=(False, 42)), patch('apps.api.services.s3_service.put_object') as put:
        if operation == 'upload':
            response = upload(client, auth_headers)
        else:
            response = client.post(f'/product-feedback/recordings/{uuid.uuid4()}/transcribe', headers=auth_headers)
    assert response.status_code == 429
    assert response.headers['Retry-After'] == '42'
    put.assert_not_called()


def test_transcription_locks_recording_before_using_cached_result(client, auth_headers, test_user, mock_db):
    row = recording(test_user)
    row.transcript = 'Already transcribed.'
    mock_db.first.return_value = row
    mock_db.with_for_update.return_value = mock_db
    with patch('apps.api.services.feedback_recordings.transcribe_audio') as provider:
        response = client.post(f'/product-feedback/recordings/{row.id}/transcribe', headers=auth_headers)
    assert response.json() == {'status': 'transcribed', 'text': 'Already transcribed.'}
    mock_db.with_for_update.assert_called_once()
    provider.assert_not_called()
