"""Brand Loop F1: a project carries an explicit AutoReview brand slug, set by a superadmin only."""
import uuid
from types import SimpleNamespace


def _project():
    return SimpleNamespace(id=uuid.uuid4(), name="audibene-workspace", deleted_at=None, autoreview_brand_slug=None)


def test_model_has_nullable_slug_column():
    from apps.api.models.project import Project
    column = Project.__table__.c.autoreview_brand_slug
    assert column.nullable is True


def test_setting_slug_requires_superadmin(client, auth_headers, mock_db, test_user):
    test_user.is_superadmin = False
    mock_db.first.return_value = _project()
    resp = client.put(f"/admin/projects/{uuid.uuid4()}/autoreview-brand", json={"slug": "audibene-gmbh"}, headers=auth_headers)
    assert resp.status_code == 403


def test_superadmin_sets_and_clears_slug(client, auth_headers, mock_db, test_user):
    test_user.is_superadmin = True
    project = _project()
    mock_db.first.return_value = project
    resp = client.put(f"/admin/projects/{project.id}/autoreview-brand", json={"slug": "audibene-gmbh"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"project_id": str(project.id), "autoreview_brand_slug": "audibene-gmbh"}
    assert project.autoreview_brand_slug == "audibene-gmbh"
    mock_db.commit.assert_called()

    resp = client.put(f"/admin/projects/{project.id}/autoreview-brand", json={"slug": None}, headers=auth_headers)
    assert resp.status_code == 200
    assert project.autoreview_brand_slug is None


def test_slug_must_be_explicit_kebab(client, auth_headers, mock_db, test_user):
    test_user.is_superadmin = True
    mock_db.first.return_value = _project()
    for bad in ["Audibene GmbH", "audibene_gmbh", "-x", "", "a" * 121]:
        resp = client.put(f"/admin/projects/{uuid.uuid4()}/autoreview-brand", json={"slug": bad}, headers=auth_headers)
        assert resp.status_code == 422, bad


def test_unknown_project_is_404(client, auth_headers, mock_db, test_user):
    test_user.is_superadmin = True
    mock_db.first.return_value = None
    resp = client.put(f"/admin/projects/{uuid.uuid4()}/autoreview-brand", json={"slug": "audibene-gmbh"}, headers=auth_headers)
    assert resp.status_code == 404
