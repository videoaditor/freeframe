"""Opt-in isolated-schema checks for actual concurrent campaign writes."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(not os.getenv('ITERATIONS_TEST_DATABASE_URL'), reason='opt-in local PostgreSQL check')


def test_two_concurrent_brand_creations_allow_exactly_one_and_usage_deduplicates():
    from apps.api.database import Base
    from apps.api.models import User, Project, Asset
    from apps.api.models.asset import AssetType
    from apps.api.models.campaign_review import CampaignReview
    from apps.api.routers.projects import create_project
    from apps.api.schemas.project import ProjectCreate
    from apps.api.services.campaign_access import TELEHEALTH
    from apps.api.services.campaign_usage import record_successes
    admin = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'])
    schema = 'campaign_test_' + uuid.uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'], connect_args={'options': f'-csearch_path={schema}'})
    Session = sessionmaker(bind=engine)
    try:
        Base.metadata.create_all(engine)
        with Session() as db:
            user = User(email='preview@example.test', name='Preview', is_staff=False,
                        suite_campaign={**TELEHEALTH, 'state': 'active', 'previewOnly': True})
            db.add(user); db.commit(); user_id = user.id
        start = Barrier(2)
        def create(name):
            with Session() as db:
                user = db.get(User, user_id)
                start.wait(timeout=10)
                try:
                    create_project(ProjectCreate(name=name), db, user)
                    return 'created'
                except HTTPException as exc:
                    db.rollback()
                    return exc.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, ['Brand A', 'Brand B']))
        assert results.count('created') == 1 and results.count(409) == 1
        with Session() as db:
            assert db.query(Project).count() == 1
            project = db.query(Project).one()
            asset = Asset(project_id=project.id, name='Ad', asset_type=AssetType.video, created_by=user_id)
            db.add(asset); db.commit(); asset_id = asset.id
            user = db.get(User, user_id)
            record_successes(db, user, {str(asset_id)})
            record_successes(db, user, {str(asset_id)})
            assert db.query(CampaignReview).count() == 1
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()
