"""Exercise real SQL scope and soft-delete filters; all synthetic writes roll back."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

import pytest

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.main import app
from apps.api.models.asset import Asset, AssetType, AssetVersion
from apps.api.models.checklist_binding import ChecklistBinding
from apps.api.models.folder import Folder
from apps.api.models.project import Project
from apps.api.models.share import ShareLink
from apps.api.models.upload_request import UploadRequest
from apps.api.models.user import User


@pytest.fixture
def assignment(real_db, client, monkeypatch):
    db = real_db
    owner = User(email=f'snapshot-{uuid.uuid4()}@example.invalid', name='Synthetic owner')
    db.add(owner); db.flush()
    project = Project(name='Synthetic snapshot', created_by=owner.id)
    db.add(project); db.flush()
    folder = Folder(project_id=project.id, name='Assignment', created_by=owner.id)
    other_folder = Folder(project_id=project.id, name='Other assignment', created_by=owner.id)
    db.add_all([folder, other_folder]); db.flush()
    asset = Asset(project_id=project.id, folder_id=folder.id, name='Cut', asset_type=AssetType.video, created_by=owner.id)
    other_asset = Asset(project_id=project.id, folder_id=other_folder.id, name='Other cut', asset_type=AssetType.video, created_by=owner.id)
    db.add_all([asset, other_asset]); db.flush()
    versions = [AssetVersion(asset_id=asset.id, version_number=n, created_by=owner.id) for n in (1, 2)]
    other_version = AssetVersion(asset_id=other_asset.id, version_number=1, created_by=owner.id)
    db.add_all([*versions, other_version]); db.flush()
    share = ShareLink(folder_id=folder.id, token=f'snapshot-{uuid.uuid4()}', created_by=owner.id)
    db.add(share); db.flush()
    request = UploadRequest(project_id=project.id, folder_id=folder.id, created_by=owner.id,
        token=f'upload-{uuid.uuid4()}', title='Synthetic request', review_share_token=share.token)
    db.add(request); db.flush()
    binding_id = uuid.uuid4()
    snapshot = {'schema_version': 'autoreview.plan-request.v1', 'tenant_id': str(project.id),
        'request_id': str(binding_id), 'idempotency_key': f'checklist:{project.id}:{binding_id}',
        'briefing': {'text': 'Original private brief', 'version': 'v1', 'sources': []},
        'rules': [], 'brand_context': {'brand': 'synthetic', 'text': 'Original note', 'sources': []}, 'limitations': []}
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    binding = ChecklistBinding(id=binding_id, project_id=project.id, folder_id=folder.id, request_id=request.id,
        created_by=owner.id, source_key=f'request:{request.id}', intent={}, intent_sha256='0' * 64,
        snapshot=snapshot, context_sha256=digest, review_share_token=share.token,
        status='failed', error_code='plan-api-unavailable')
    db.add(binding); db.flush()
    monkeypatch.setattr(settings, 'review_bridge_secret', 'synthetic-bridge-secret')
    app.dependency_overrides[get_db] = lambda: db
    return dict(project=project, folder=folder, asset=asset, version=versions[0], later=versions[1],
        other_asset=other_asset, other_version=other_version, share=share, request=request,
        binding=binding, snapshot=snapshot, digest=digest, db=db)


def read(client, assignment, **overrides):
    a = assignment
    return client.get('/internal/review/checklist-snapshot', params={
        'share_token': a['share'].token, 'project_id': str(a['project'].id),
        'asset_id': str(a['asset'].id), 'version_id': str(a['version'].id), **overrides,
    }, headers={'Authorization': 'Bearer synthetic-bridge-secret'})


def test_real_sql_returns_same_frozen_context_for_two_media_versions(client, assignment):
    first = read(client, assignment)
    second = read(client, assignment, version_id=str(assignment['later'].id))
    assert first.status_code == second.status_code == 200
    assert first.json()['snapshot'] == second.json()['snapshot'] == assignment['snapshot']
    assert first.json()['context_sha256'] == second.json()['context_sha256'] == assignment['digest']
    assert first.json()['version_id'] != second.json()['version_id']
    assert first.json()['version_number'] == 1
    assert second.json()['version_number'] == 2


@pytest.mark.parametrize('scope', ['tenant', 'share', 'asset', 'version', 'missing-version'])
def test_real_sql_rejects_other_assignment_or_version(client, assignment, scope):
    changes = {
        'tenant': {'project_id': str(uuid.uuid4())},
        'share': {'share_token': 'another-token'},
        'asset': {'asset_id': str(assignment['other_asset'].id), 'version_id': str(assignment['other_version'].id)},
        'version': {'version_id': str(assignment['other_version'].id)},
        'missing-version': {'version_id': str(uuid.uuid4())},
    }
    response = read(client, assignment, **changes[scope])
    assert response.status_code == 404
    assert 'Original private' not in response.text


@pytest.mark.parametrize('entity', ['project', 'folder', 'asset', 'version', 'share', 'binding', 'request'])
def test_real_sql_rejects_soft_deleted_or_revoked_parents(client, assignment, entity):
    setattr(assignment[entity], 'revoked_at' if entity == 'request' else 'deleted_at', datetime.now(timezone.utc))
    assignment['db'].flush()
    response = read(client, assignment)
    assert response.status_code == 404
    assert 'Original private' not in response.text
