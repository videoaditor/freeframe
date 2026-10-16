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
    from datetime import datetime, timezone
    from apps.api.models import User, Project
    from apps.api.models.project import ProjectMember, ProjectRole
    from apps.api.routers.autoreview import user_brands

    def user(email, **kw):
        u = User(email=email, name=email, **kw)
        db.add(u)
        db.flush()
        return u

    owner, client, other, admin = user('o@aditor.ai'), user('k@audibene.de', is_staff=False), user('x@y.de'), user('a@aditor.ai', is_superadmin=True)

    def project(name, slug, **kw):
        p = Project(name=name, created_by=owner.id, autoreview_brand_slug=slug, **kw)
        db.add(p)
        db.flush()
        return p

    audibene = project('audibene-workspace', 'audibene-gmbh')
    project('audibene-workspace-old', 'audibene-gmbh')
    mynd = project('Mynd', 'mynd-organics')
    project('Gone', 'gone-brand', deleted_at=datetime.now(timezone.utc))
    project('Unlinked', None)
    db.add(ProjectMember(project_id=audibene.id, user_id=client.id, role=ProjectRole.reviewer))
    db.add(ProjectMember(project_id=mynd.id, user_id=other.id, role=ProjectRole.viewer, deleted_at=datetime.now(timezone.utc)))
    db.commit()

    assert user_brands(db, client) == [{'slug': 'audibene-gmbh', 'name': 'audibene-workspace'}]
    assert user_brands(db, other) == []
    assert [b['slug'] for b in user_brands(db, owner)] == ['audibene-gmbh', 'mynd-organics']
    assert [b['slug'] for b in user_brands(db, admin)] == ['audibene-gmbh', 'mynd-organics']
