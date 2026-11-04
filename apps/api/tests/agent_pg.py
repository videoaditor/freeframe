"""Shared fixture for the agent-review tests: a throwaway Postgres schema plus a TestClient bound to it.

Set AP_TEST_DATABASE_URL to a disposable database to run them; without it they skip (the suite's
mock-DB style cannot express the joins and locks these routes rely on).
"""
import os
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

PG_URL = os.getenv("AP_TEST_DATABASE_URL")
needs_pg = pytest.mark.skipif(not PG_URL, reason="set AP_TEST_DATABASE_URL to a disposable Postgres")


@pytest.fixture
def env():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from apps.api import models  # noqa: F401 - register every table
    from apps.api.database import Base, get_db
    from apps.api.main import app
    from apps.api.models.folder import Folder
    from apps.api.models.project import Project, ProjectMember, ProjectRole
    from apps.api.models.upload_request import UploadRequest
    from apps.api.models.user import User
    from apps.api.services.auth_service import create_access_token

    admin = create_engine(PG_URL)
    schema = "ap_" + uuid.uuid4().hex
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    e = SimpleNamespace(Session=Session)

    def user(name, **kw):
        with Session() as db:
            u = User(email=f"{name}-{uuid.uuid4().hex[:6]}@example.test", name=name, **kw)
            db.add(u)
            db.commit()
            return u

    def project(owner, name="Brand A"):
        with Session() as db:
            p = Project(name=name, created_by=owner.id)
            db.add(p)
            db.flush()
            db.add(ProjectMember(project_id=p.id, user_id=owner.id, role=ProjectRole.owner))
            db.commit()
            return p

    def request(proj, owner, title="Hook 1"):
        with Session() as db:
            f = Folder(project_id=proj.id, name=title, created_by=owner.id)
            db.add(f)
            db.flush()
            r = UploadRequest(token=uuid.uuid4().hex, project_id=proj.id, folder_id=f.id, created_by=owner.id,
                              title=title, review_share_token=uuid.uuid4().hex)
            db.add(r)
            db.commit()
            return r

    e.user, e.project, e.request = user, project, request
    e.headers = lambda u: {"Authorization": f"Bearer {create_access_token(str(u.id))}"}
    e.owner = user("Owner")
    e.project_a = project(e.owner, "Brand A")
    e.project_b = project(e.owner, "Brand B")

    with patch("apps.api.services.s3_service.ensure_bucket_exists"), \
         patch("apps.api.services.s3_service.get_s3_client", return_value=MagicMock()), \
         patch("apps.api.middleware.setup_guard._setup_complete", True):
        app.dependency_overrides[get_db] = override
        e.client = TestClient(app, raise_server_exceptions=False)
        yield e
        app.dependency_overrides.clear()
    engine.dispose()
    with admin.begin() as c:
        c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    admin.dispose()
