import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException


def test_automation_comment_key_is_authenticated_and_scoped(monkeypatch):
    from apps.api.routers.comments import automation_comment_id
    from apps.api.config import settings
    monkeypatch.setattr(settings,'review_bridge_secret','secret')
    asset,version=uuid.uuid4(),uuid.uuid4()
    with pytest.raises(HTTPException): automation_comment_id('t',asset,version,'finding-1',None)
    a=automation_comment_id('t',asset,version,'finding-1','Bearer secret')
    assert a==automation_comment_id('t',asset,version,'finding-1','Bearer secret')
    assert a!=automation_comment_id('t',asset,uuid.uuid4(),'finding-1','Bearer secret')


def test_version_comment_rejects_version_of_another_asset():
    from apps.api.routers.comments import validate_comment_version
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=None
    with pytest.raises(HTTPException) as exc: validate_comment_version(db,uuid.uuid4(),uuid.uuid4())
    assert exc.value.status_code==409
