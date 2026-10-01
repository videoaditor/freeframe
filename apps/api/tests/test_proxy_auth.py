"""Whop strips Authorization; the alternate header must retain normal JWT checks."""
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from apps.api.database import get_db
from apps.api.middleware.auth import get_current_user, get_optional_user
from apps.api.services.auth_service import create_access_token


@pytest.fixture
def proxy_client(mock_db, test_user):
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: mock_db

    @app.get('/required')
    def required(user=Depends(get_current_user)):
        return {'id': str(user.id)}

    @app.get('/optional')
    def optional(user=Depends(get_optional_user)):
        return {'id': str(user.id) if user else None}

    with patch('apps.api.middleware.auth.get_user_by_id', return_value=test_user), \
         patch('apps.api.middleware.auth.require_customer_entitlement'):
        yield TestClient(app)


def test_proxy_token_authenticates_required_and_optional_routes(proxy_client, test_user):
    headers = {'X-FreeFrame-Token': create_access_token(str(test_user.id))}
    for path in ('/required', '/optional'):
        response = proxy_client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.json() == {'id': str(test_user.id)}


@pytest.mark.parametrize('headers', [
    {'X-FreeFrame-Token': 'forged-token'},
    {},
])
def test_proxy_token_does_not_bypass_validation(proxy_client, headers):
    assert proxy_client.get('/required', headers=headers).status_code == 401
    assert proxy_client.get('/optional', headers=headers).json() == {'id': None}


def test_standard_authorization_takes_precedence(proxy_client, test_user):
    headers = {'Authorization': 'Bearer invalid',
               'X-FreeFrame-Token': create_access_token(str(test_user.id))}
    assert proxy_client.get('/required', headers=headers).status_code == 401


def test_proxy_token_still_requires_entitlement(proxy_client, test_user):
    headers = {'X-FreeFrame-Token': create_access_token(str(test_user.id))}
    with patch('apps.api.middleware.auth.require_customer_entitlement',
               side_effect=HTTPException(status_code=403, detail='Access revoked')):
        assert proxy_client.get('/required', headers=headers).status_code == 403
        assert proxy_client.get('/optional', headers=headers).json() == {'id': None}
