"""Customers need membership even when a staff project is public."""
import uuid
from unittest.mock import MagicMock

import pytest

from apps.api.main import app
from apps.api.middleware.auth import get_current_user
from apps.api.models.project import Project, ProjectRole


@pytest.mark.parametrize("route", ["assets", "folders", "folder-tree"])
@pytest.mark.parametrize("staff,member,expected", [(False, False, 403), (True, False, 200), (False, True, 200)])
def test_public_project_lists_respect_customer_membership(client, mock_db, test_user, monkeypatch, route, staff, member, expected):
    monkeypatch.setattr("apps.api.config.settings.instance_wide_project_access", False)
    test_user.is_staff = staff
    app.dependency_overrides[get_current_user] = lambda: test_user
    public_query = MagicMock()
    public_query.filter.return_value.first.return_value = Project(is_public=True)
    mock_db.first.return_value = MagicMock(role=ProjectRole.viewer) if member else None
    mock_db.order_by.return_value = mock_db
    mock_db.query.side_effect = lambda model, *args: public_query if model is Project else mock_db
    response = client.get(f"/projects/{uuid.uuid4()}/{route}")
    assert response.status_code == expected
    assert response.json() == ([] if expected == 200 else {"detail": "Not a project member"})
