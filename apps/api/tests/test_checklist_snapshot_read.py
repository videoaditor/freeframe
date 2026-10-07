"""Private frozen context cannot cross a request, tenant, asset or version boundary."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.api.config import settings
from apps.api.models.asset import Asset, AssetVersion
from apps.api.models.checklist_binding import ChecklistBinding
from apps.api.models.folder import Folder
from apps.api.models.project import Project
from apps.api.models.share import ShareLink
from apps.api.models.upload_request import UploadRequest


@pytest.fixture
def saved_context(client, mock_db, monkeypatch):
    ids = {name: uuid.uuid4() for name in ('project', 'folder', 'binding', 'request', 'asset', 'version')}
    snapshot = {
        'schema_version': 'autoreview.plan-request.v1',
        'tenant_id': str(ids['project']), 'request_id': str(ids['binding']),
        'idempotency_key': f"checklist:{ids['project']}:{ids['binding']}",
        'briefing': {'text': 'Full frozen brief. 音楽', 'version': 'brief-v1', 'sources': []},
        'rules': [{'id': 'rule-original', 'what': 'Show the product', 'sources': [
            {'layer': 'brand', 'reference_id': 'rule-original', 'source_version': 'rule-v1'}]}],
        'brand_context': {'brand': 'synthetic', 'text': 'Private frozen brand note', 'sources': []},
        'limitations': [],
    }
    # Independent serialization: this fixture has only strings, arrays and ASCII keys.
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    rows = {
        ChecklistBinding: SimpleNamespace(id=ids['binding'], project_id=ids['project'], folder_id=ids['folder'],
            request_id=ids['request'], review_share_token='standing-token', snapshot=snapshot,
            context_sha256=digest, status='failed', error_code='plan-api-unavailable', deleted_at=None),
        Project: SimpleNamespace(id=ids['project'], created_by=uuid.uuid4(), deleted_at=None),
        Folder: SimpleNamespace(id=ids['folder'], project_id=ids['project'], deleted_at=None),
        ShareLink: SimpleNamespace(token='standing-token', folder_id=ids['folder'], project_id=None,
            asset_id=None, is_enabled=True, expires_at=None, password_hash=None, visibility='public', deleted_at=None),
        Asset: SimpleNamespace(id=ids['asset'], project_id=ids['project'], folder_id=ids['folder'], deleted_at=None),
        AssetVersion: SimpleNamespace(id=ids['version'], asset_id=ids['asset'], version_number=2, deleted_at=None),
        UploadRequest: SimpleNamespace(id=ids['request'], project_id=ids['project'], folder_id=ids['folder'],
            review_share_token='standing-token', revoked_at=None),
    }

    def query(model):
        result = MagicMock()
        result.filter.return_value.first.side_effect = lambda: rows[model]
        return result

    mock_db.query.side_effect = query
    mock_db.get.side_effect = lambda model, key: rows.get(model) if rows.get(model) and rows[model].id == key else None
    monkeypatch.setattr(settings, 'review_bridge_secret', 'synthetic-bridge-secret')
    monkeypatch.setattr('apps.api.services.campaign_access.require_project_access', lambda *_: None)

    def provider_call(*args, **kwargs):
        pytest.fail('Reading saved context must not contact a provider or review bridge')

    monkeypatch.setattr('apps.api.services.review_bridge.checklist_snapshot', provider_call)
    monkeypatch.setattr('apps.api.services.review_bridge.checklist_plan', provider_call)
    return SimpleNamespace(rows=rows, snapshot=snapshot, digest=digest, params={
        'share_token': 'standing-token', 'project_id': str(ids['project']),
        'asset_id': str(ids['asset']), 'version_id': str(ids['version']),
    }, headers={'Authorization': 'Bearer synthetic-bridge-secret'})


def read(client, context, **overrides):
    return client.get('/internal/review/checklist-snapshot', params={**context.params, **overrides}, headers=context.headers)


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer normal-user-jwt'},
    {'X-API-Key': 'synthetic-service-key'}, {'Authorization': 'Bearer wrong-secret'}])
def test_only_the_bridge_service_secret_can_read_private_context(client, mock_db, saved_context, headers):
    mock_db.query.side_effect = AssertionError('Unauthorized request touched private storage')
    response = client.get('/internal/review/checklist-snapshot', params=saved_context.params, headers=headers)
    assert response.status_code == 401
    assert 'Private frozen' not in response.text


def test_unconfigured_bridge_cannot_authorize_an_empty_secret(client, mock_db, saved_context, monkeypatch):
    monkeypatch.setattr(settings, 'review_bridge_secret', '')
    mock_db.query.side_effect = AssertionError('Disabled bridge touched private storage')
    response = read(client, saved_context)
    assert response.status_code == 503


def test_failed_plan_still_returns_full_frozen_snapshot_for_exact_version(client, saved_context):
    response = read(client, saved_context)
    assert response.status_code == 200
    body = response.json()
    assert body == {
        'schema_version': 'autoreview.saved-snapshot.v1',
        'tenant_id': saved_context.params['project_id'],
        'binding_id': str(saved_context.rows[ChecklistBinding].id),
        'upload_request_id': str(saved_context.rows[UploadRequest].id),
        'asset_id': saved_context.params['asset_id'], 'version_id': saved_context.params['version_id'],
        'version_number': 2, 'context_sha256': saved_context.digest, 'snapshot': saved_context.snapshot,
    }
    assert response.headers['cache-control'] == 'private, no-store'
    assert 'authorization' in response.headers['vary'].lower()


def test_direct_staff_folder_binding_does_not_need_an_upload_request(client, saved_context):
    saved_context.rows[ChecklistBinding].request_id = None
    response = read(client, saved_context)
    assert response.status_code == 200
    assert response.json()['upload_request_id'] is None


def test_foreign_tenant_cannot_use_a_known_standing_token(client, saved_context):
    response = read(client, saved_context, project_id=str(uuid.uuid4()))
    assert response.status_code == 404
    assert 'Private frozen' not in response.text


@pytest.mark.parametrize(('model', 'field'), [
    (Asset, 'project_id'), (Asset, 'folder_id'), (AssetVersion, 'asset_id'),
    (Folder, 'project_id'), (ShareLink, 'folder_id'),
    (UploadRequest, 'project_id'), (UploadRequest, 'folder_id'),
])
def test_scope_mismatch_never_returns_private_rules(client, saved_context, model, field):
    setattr(saved_context.rows[model], field, uuid.uuid4())
    response = read(client, saved_context)
    assert response.status_code == 404
    assert 'rule-original' not in response.text


@pytest.mark.parametrize('model', [ChecklistBinding, Project, Folder, Asset, AssetVersion, UploadRequest, ShareLink])
def test_missing_or_soft_deleted_scope_is_unavailable(client, saved_context, model):
    saved_context.rows[model] = None  # active-row query excludes soft-deleted records
    response = read(client, saved_context)
    assert response.status_code == 404


@pytest.mark.parametrize(('model', 'field', 'value'), [
    (UploadRequest, 'revoked_at', datetime.now(timezone.utc)),
    (UploadRequest, 'review_share_token', 'another-standing-token'),
    (ShareLink, 'is_enabled', False),
    (ShareLink, 'expires_at', datetime.now(timezone.utc) - timedelta(seconds=1)),
    (ShareLink, 'password_hash', 'password-required'),
    (ShareLink, 'visibility', 'secure'),
])
def test_revoked_or_restricted_share_cannot_expose_saved_context(client, saved_context, model, field, value):
    setattr(saved_context.rows[model], field, value)
    response = read(client, saved_context)
    assert response.status_code in (403, 404, 410)
    assert 'Private frozen' not in response.text


def test_missing_snapshot_does_not_prepare_or_invent_context(client, saved_context):
    saved_context.rows[ChecklistBinding].snapshot = None
    response = read(client, saved_context)
    assert response.status_code == 404


@pytest.mark.parametrize('mutation', ['hash', 'tenant', 'binding'])
def test_corrupt_stored_snapshot_never_gets_source_labels(client, saved_context, mutation):
    if mutation == 'hash':
        saved_context.rows[ChecklistBinding].context_sha256 = '0' * 64
    else:
        saved_context.snapshot['tenant_id' if mutation == 'tenant' else 'request_id'] = str(uuid.uuid4())
        saved_context.rows[ChecklistBinding].context_sha256 = hashlib.sha256(json.dumps(
            saved_context.snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    response = read(client, saved_context)
    assert response.status_code == 409
    assert 'Private frozen' not in response.text


def test_a_later_media_version_reads_the_same_saved_context(client, saved_context):
    first = read(client, saved_context).json()
    version = saved_context.rows[AssetVersion]
    version.id = uuid.uuid4()
    version.version_number = 3
    later = read(client, saved_context, version_id=str(version.id))
    assert later.status_code == 200
    assert later.json()['context_sha256'] == first['context_sha256']
    assert later.json()['snapshot'] == first['snapshot']
    assert later.json()['version_number'] == 3
