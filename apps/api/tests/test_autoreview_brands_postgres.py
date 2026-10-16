"""Real Postgres: which AutoReview brands a user may open (explicit membership, creator, superadmin)."""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(not os.getenv('ITERATIONS_TEST_DATABASE_URL'), reason='opt-in local PostgreSQL check')


@pytest.fixture
def db():
    from apps.api.database import Base
    from apps.api import models  # noqa: F401 - register every table
    admin = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'])
    schema = 'autoreview_' + uuid.uuid4().hex
    with admin.begin() as c:
        c.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'], connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def test_user_brands(db):
    from datetime import datetime, timedelta, timezone
    from apps.api.models import User, Project
    from apps.api.models.project import ProjectMember, ProjectRole
    from apps.api.routers.autoreview import user_brands
    now = datetime.now(timezone.utc)

    def user(email, **kw):
        u = User(email=email, name=email, **kw)
        db.add(u)
        db.flush()
        return u

    owner, client, gone, admin = user('o@aditor.ai'), user('k@audibene.de', is_staff=False), user('x@y.de'), user('a@aditor.ai', is_superadmin=True)

    def project(name, slug, age_days, **kw):
        p = Project(name=name, created_by=owner.id, autoreview_brand_slug=slug, is_workspace=True,
                    created_at=now - timedelta(days=age_days), **kw)
        db.add(p)
        db.flush()
        return p

    newer = project('audibene-regs', 'audibene-gmbh', 1)
    oldest = project('audibene-workspace', 'audibene-gmbh', 30)
    mynd = project('Mynd', 'mynd-organics', 5)
    deleted = project('Gone', 'gone-brand', 5, deleted_at=now)
    unlinked = project('Unlinked', None, 5)
    for p in (newer, oldest, unlinked, deleted):
        db.add(ProjectMember(project_id=p.id, user_id=client.id, role=ProjectRole.reviewer))
    db.add(ProjectMember(project_id=mynd.id, user_id=gone.id, role=ProjectRole.viewer, deleted_at=now))
    db.commit()

    # Several workspaces share one slug; the label is the oldest one's name.
    assert user_brands(db, client) == [{'slug': 'audibene-gmbh', 'name': 'audibene-workspace'}]
    assert user_brands(db, gone) == [], 'soft-deleted membership grants nothing'
    assert user_brands(db, owner) == [], 'creating a project without membership grants nothing'
    assert [b['slug'] for b in user_brands(db, admin)] == ['audibene-gmbh', 'mynd-organics']
