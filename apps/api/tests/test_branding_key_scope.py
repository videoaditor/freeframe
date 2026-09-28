"""A project editor cannot turn a branding key into a read of someone else's object."""
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from apps.api.routers import branding
from apps.api.schemas.branding import BrandingUpdate


@pytest.mark.parametrize('key', ['raw/private.mp4', f'branding/{uuid.uuid4()}/logo/{uuid.uuid4()}.webp'])
def test_logo_cannot_reference_another_project_or_raw_object(mock_db, monkeypatch, key):
    monkeypatch.setattr(branding, 'require_project_role', lambda *args: None)
    with pytest.raises(HTTPException) as exc:
        branding.upsert_branding(uuid.uuid4(), BrandingUpdate(logo_s3_key=key), mock_db, MagicMock())
    assert exc.value.status_code == 400
    mock_db.commit.assert_not_called()


def test_own_presigned_logo_key_is_accepted(mock_db, monkeypatch):
    project = uuid.uuid4()
    key = f'branding/{project}/logo/{uuid.uuid4()}.webp'
    row = MagicMock()
    monkeypatch.setattr(branding, 'require_project_role', lambda *args: None)
    monkeypatch.setattr(branding, '_get_or_create_branding', lambda *args: row)
    monkeypatch.setattr(branding, '_branding_to_response', lambda row: row)
    result = branding.upsert_branding(project, BrandingUpdate(logo_s3_key=key), mock_db, MagicMock())
    assert result.logo_s3_key == key
