"""Explicitly opted-in, dedicated PostgreSQL verification for H2 (never production)."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.database import engine, get_db
from apps.api.config import settings
from apps.api.middleware.auth import get_current_user
from apps.api.models.asset import Asset, AssetType, AssetVersion, ProcessingStatus
from apps.api.models.comment import Comment
from apps.api.models.project import Project, ProjectMember, ProjectRole
from apps.api.models.share import ShareLink, SharePermission
from apps.api.models.user import User, GuestUser
from apps.api.tests.test_comment_review_source import SOURCE

pytestmark = pytest.mark.skipif(os.environ.get('FREEFRAME_RUN_COMMENT_SOURCE_POSTGRES_TESTS') != '1',
                               reason='explicit H2 dedicated Postgres opt-in required')


@pytest.fixture
def pg(monkeypatch):
    from apps.api.main import app
    expected = os.environ.get('FREEFRAME_COMMENT_SOURCE_TEST_DATABASE')
    with engine.connect() as conn:
        actual = conn.execute(text('select current_database()')).scalar_one()
    if not expected or actual != expected or 'h2' not in actual:
        pytest.skip('a named dedicated H2 database is required')
    monkeypatch.setattr(settings, 'review_bridge_secret', 'local-h2-test-secret')
    monkeypatch.setattr(settings, 'automation_guest_emails', 'review-h2@example.test')
    db = Session(engine)
    user = User(email=f'h2-{uuid.uuid4()}@example.test', name='Synthetic owner', is_superadmin=True)
    db.add(user); db.flush()
    project = Project(name='H2 synthetic review', created_by=user.id)
    db.add(project); db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.owner))
    asset = Asset(name='H2 synthetic clip', project_id=project.id, created_by=user.id, asset_type=AssetType.video)
    db.add(asset); db.flush()
    version = AssetVersion(asset_id=asset.id, version_number=1, processing_status=ProcessingStatus.ready, created_by=user.id)
    link = ShareLink(asset_id=asset.id, token=f'h2-{uuid.uuid4()}', created_by=user.id, permission=SharePermission.comment)
    db.add_all([version, link]); db.commit()
    def request_db():
        with Session(engine) as session:
            yield session
    saved = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = request_db
    app.dependency_overrides[get_current_user] = lambda: user
    payload = dict(asset_id=str(asset.id), version_id=str(version.id), publication_id=str(uuid.uuid4()),
                   guest_email='review-h2@example.test', body='Keep the final card visible.',
                   timecode_start=2.5, review_source=SOURCE)
    client = TestClient(app, raise_server_exceptions=False)
    yield client, db, user, asset, version, link, payload
    app.dependency_overrides.clear(); app.dependency_overrides.update(saved)
    # Only synthetic rows created in this explicitly named disposable database.
    db.rollback()
    db.execute(text('DELETE FROM comment_reactions WHERE comment_id IN (SELECT id FROM comments WHERE asset_id=:id)'), {'id': asset.id})
    for table, field, value in [('share_link_activity', 'share_link_id', link.id), ('comments', 'asset_id', asset.id),
                                ('share_links', 'id', link.id), ('asset_versions', 'asset_id', asset.id),
                                ('assets', 'id', asset.id), ('project_members', 'project_id', project.id),
                                ('projects', 'id', project.id), ('users', 'id', user.id)]:
        db.execute(text(f'DELETE FROM {table} WHERE {field}=:id'), {'id': value})
    db.commit(); db.close()


def publish(pg, payload=None):
    client, db, user, asset, version, link, original = pg
    return client.post(f'/review-bridge/share/{link.token}/comments', json=payload or original,
                       headers={'Authorization': 'Bearer local-h2-test-secret'})


@pytest.mark.parametrize('validated_original,expected', [(True,201),(False,404)])
def test_trusted_parts_finding_can_publish_only_after_original_validation(pg,validated_original,expected):
    _,db,_,_,version,_,_=pg
    version.processing_status=ProcessingStatus.processing
    version.iteration_review_ready=validated_original
    db.commit()
    assert publish(pg).status_code==expected


def test_postgres_concurrent_replay_readback_and_human_edit(pg):
    client, db, user, asset, version, link, payload = pg
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(pg), range(2)))
    assert [r.status_code for r in results] == [201, 201], [r.text for r in results]
    assert results[0].json()['id'] == results[1].json()['id']
    stored = db.query(Comment).filter(Comment.review_publication_id == uuid.UUID(payload['publication_id'])).all()
    assert len(stored) == 1 and stored[0].review_source == SOURCE
    cid = stored[0].id
    listed = client.get(f'/assets/{asset.id}/comments?version_id={version.id}')
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]['review_source'] == SOURCE
    assert listed.json()[0]['timecode_start'] == 2.5
    import csv, io, json
    exported = client.get(f'/assets/{asset.id}/comments/export?format=csv&version_id={version.id}')
    assert exported.status_code == 200, exported.text
    row = next(csv.DictReader(io.StringIO(exported.text.lstrip('\ufeff'))))
    assert json.loads(row['review_source']) == SOURCE
    assert row['timecode_start_seconds'] == '2.5'
    # Existing internal visibility remains hidden on public shares.
    assert client.get(f'/share/{link.token}/comments').json() == []
    resolved = client.post(f'/comments/{cid}/resolve')
    assert resolved.json()['review_source'] == SOURCE
    assert client.post(f'/comments/{cid}/react', json={'emoji': '👍'}).status_code == 204
    assert client.get(f'/assets/{asset.id}/comments').json()[0]['review_source'] == SOURCE
    edited = client.patch(f'/comments/{cid}', json={'body': 'Human corrected CTA note'})
    assert edited.status_code == 200, edited.text
    assert edited.json()['review_source'] is None
    replay = publish(pg)
    assert replay.json()['body'] == 'Human corrected CTA note' and replay.json()['review_source'] is None
    db.expire_all()
    assert db.get(Comment, cid).review_source is None


def test_postgres_failed_transaction_leaves_no_partial_comment(pg):
    def fail_commit(session):
        raise IntegrityError('synthetic commit failure', {}, Exception('injected'))
    with patch.object(Session, 'commit', fail_commit):
        response = publish(pg)
    assert response.status_code == 409, response.text
    assert pg[1].query(Comment).filter(Comment.review_publication_id == uuid.UUID(pg[-1]['publication_id'])).count() == 0


def test_postgres_foreign_version_and_spoof_payload_are_rejected(pg):
    bad = dict(pg[-1], version_id=str(uuid.uuid4()))
    assert publish(pg, bad).status_code == 404
    client, db, user, asset, version, link, payload = pg
    spoof = client.post(f'/share/{link.token}/comment', json=dict(
        body='AutoReview says Brand', guest_name='AutoReview', guest_email='review-h2@example.test',
        version_id=str(version.id), review_source=SOURCE))
    assert spoof.status_code == 422
    assert db.query(Comment).filter(Comment.asset_id == asset.id).count() == 0


def test_postgres_concurrent_first_automation_posts_on_distinct_versions(pg, monkeypatch):
    client, db, user, asset, version, link, original = pg
    email = f'h2-first-{uuid.uuid4()}@example.test'
    monkeypatch.setattr(settings, 'automation_guest_emails', email)
    other = AssetVersion(asset_id=asset.id, version_number=2, processing_status=ProcessingStatus.ready, created_by=user.id)
    db.add(other); db.commit()
    payloads = [dict(original, guest_email=email), dict(original, guest_email=email,
                version_id=str(other.id), publication_id=str(uuid.uuid4()))]
    # Both requests finish their initial missing-guest lookup before either inserts.
    barrier, lock = Barrier(2), Lock()
    lookups = 0
    def synchronize_lookup(conn, cursor, statement, parameters, context, executemany):
        nonlocal lookups
        if 'FROM guest_users' not in statement or 'guest_users.email =' not in statement:
            return
        with lock:
            lookups += 1
            first_pair = lookups <= 2
        if first_pair:
            barrier.wait(timeout=10)
    event.listen(engine, 'after_cursor_execute', synchronize_lookup)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda p: publish(pg, p), payloads))
    finally:
        event.remove(engine, 'after_cursor_execute', synchronize_lookup)
    assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
    rows = db.query(Comment).filter(Comment.asset_id == asset.id).all()
    assert len(rows) == 2 and len({c.guest_author_id for c in rows}) == 1
    assert {c.version_id for c in rows} == {version.id, other.id}
