"""All listed requests retain their real review verdict, including later batches."""
from apps.api.services import review_bridge


def test_request_status_does_not_mark_later_batches_ready(monkeypatch):
    tokens = [f"request-{i}" for i in range(101)]
    def response(method, path, *, params):
        batch = params["tokens"].split(",")
        assert len(batch) <= 50
        return {"status": {token: {"status": "held", "open_must_fixes": 1} for token in batch}}
    monkeypatch.setattr(review_bridge, "_call", response)
    result = review_bridge.request_status(tokens)
    assert set(result) == set(tokens)
    assert result[tokens[-1]]["status"] == "held"


def test_editor_stats_include_assets_after_the_worker_batch_limit(monkeypatch):
    ids = [f"asset-{i}" for i in range(201)]
    def response(method, path, *, params):
        batch = params["ids"].split(",")
        assert len(batch) <= 200
        return {"assets": {asset: {"first_try": False} for asset in batch}}
    monkeypatch.setattr(review_bridge, "_call", response)
    result = review_bridge.asset_stats(ids)
    assert set(result) == set(ids)
    assert result[ids[-1]]["first_try"] is False


import pytest

@pytest.mark.parametrize('response', [[], 'bad', {'assets': 'bad', 'status': []}, {'assets': {'a': False}, 'status': {'s': None}}])
def test_malformed_bridge_response_is_unavailable_not_a_route_error(monkeypatch, response):
    monkeypatch.setattr(review_bridge, '_call', lambda *a, **kw: response)
    assert review_bridge.asset_stats(['a']) == {}
    assert review_bridge.request_status(['s']) == {}
