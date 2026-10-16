"""Brand Loop F3: one-click AutoReview access. GET /autoreview/link mints a 60 s HS256 token per
contract (feedback-agent 2026-10-16-brand-loop-CONTRACT.md); GET /autoreview/brands feeds the sidebar.
"""
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from jose import jwt

from apps.api.config import settings

BRANDS = [{"slug": "audibene-gmbh", "name": "audibene-workspace"}, {"slug": "mynd-organics", "name": "Mynd"}]


@pytest.fixture
def enabled():
    settings.autoreview_url, settings.brand_loop_secret = "https://review.aditor.ai/", "s3cret"
    yield
    settings.autoreview_url, settings.brand_loop_secret = "", ""


def test_link_mints_contract_token(client, auth_headers, test_user, enabled):
    test_user.email = "kunde@audibene.de"
    with patch("apps.api.routers.autoreview.user_brands", return_value=BRANDS):
        resp = client.get("/autoreview/link?brand=audibene-gmbh", headers=auth_headers)
    assert resp.status_code == 200
    url = urlparse(resp.json()["url"])
    assert (url.scheme, url.netloc, url.path) == ("https", "review.aditor.ai", "/brand/audibene-gmbh")
    token = parse_qs(url.query)["t"][0]
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    claims = jwt.decode(token, "s3cret", algorithms=["HS256"], audience="review:brand")
    assert claims["v"] == 1 and claims["iss"] == "freeframe" and claims["sub"] == "kunde@audibene.de"
    assert claims["brands"] == ["audibene-gmbh"]
    assert 55 <= claims["exp"] - time.time() <= 60


def test_link_403_for_brand_the_user_is_not_in(client, auth_headers, enabled):
    with patch("apps.api.routers.autoreview.user_brands", return_value=BRANDS):
        resp = client.get("/autoreview/link?brand=forward-health", headers=auth_headers)
    assert resp.status_code == 403


def test_link_503_when_not_configured(client, auth_headers):
    with patch("apps.api.routers.autoreview.user_brands", return_value=BRANDS):
        resp = client.get("/autoreview/link?brand=audibene-gmbh", headers=auth_headers)
    assert resp.status_code == 503


def test_link_requires_login(client):
    assert client.get("/autoreview/link?brand=audibene-gmbh").status_code == 401


def test_brands_lists_user_brands(client, auth_headers, enabled):
    with patch("apps.api.routers.autoreview.user_brands", return_value=BRANDS):
        resp = client.get("/autoreview/brands", headers=auth_headers)
    assert resp.json() == {"brands": BRANDS}


def test_brands_empty_when_not_configured(client, auth_headers):
    with patch("apps.api.routers.autoreview.user_brands", return_value=BRANDS) as lookup:
        resp = client.get("/autoreview/brands", headers=auth_headers)
    assert resp.json() == {"brands": []}
    lookup.assert_not_called()
