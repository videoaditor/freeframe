"""Real Word XML extraction through the request and rule import boundaries."""
import base64
import io
import uuid
from unittest.mock import MagicMock
from types import SimpleNamespace
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from fastapi import HTTPException

from apps.api.models.project import Project
from apps.api.models.upload_request import UploadRequest
from apps.api.routers import requests as routes


def docx(xml=None, entry='word/document.xml'):
    payload = io.BytesIO()
    with ZipFile(payload, 'w', ZIP_DEFLATED) as archive:
        archive.writestr(entry, xml or '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Launch brief</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Hook</w:t><w:tab/><w:t>Keep logo</w:t><w:br/><w:t>visible.</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
    return base64.b64encode(payload.getvalue()).decode()


def setup_request(mock_db, monkeypatch):
    project = Project(id=uuid.uuid4(), name='Fortea', created_by=uuid.uuid4())
    mock_db.first.return_value = project
    mock_db.populate_existing.return_value = mock_db
    mock_db.with_for_update.return_value = mock_db
    monkeypatch.setattr(routes, 'require_project_role', lambda *a: None)
    monkeypatch.setattr(routes, 'project_brand', lambda *a: 'cust-owned')
    monkeypatch.setattr(routes, '_request_out', lambda req, project, **kwargs: {'excerpt': req.brief_excerpt})
    bridge = MagicMock(return_value=SimpleNamespace(id=uuid.uuid4(), request_id=None))
    monkeypatch.setattr(routes, 'reserve_binding', bridge)
    monkeypatch.setattr(routes, 'dispatch_binding', lambda *a: None)
    return project, bridge


def test_word_brief_reaches_review_as_text_before_request_is_saved(mock_db, monkeypatch):
    project, bridge = setup_request(mock_db, monkeypatch)
    result = routes.create_request(routes.RequestCreate(project_id=project.id, title='Launch', brief_docx_base64=docx(), brief_text='Extra note'), mock_db, MagicMock())
    assert bridge.call_args.args[4]['brief_text'] == 'Launch brief\nHook\tKeep logo\nvisible.\n\nExtra note'
    assert result['excerpt'].startswith('Launch brief')


@pytest.mark.parametrize('payload', ['invalid base64!', base64.b64encode(b'not a docx').decode(), docx(entry='random.xml'), docx('<broken>'), docx('<document/>'), docx('<!DOCTYPE a [<!ENTITY x "hello">]><document>&x;</document>')])
def test_bad_word_brief_is_rejected_without_creating_a_link(payload, mock_db, monkeypatch):
    project, bridge = setup_request(mock_db, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        routes.create_request(routes.RequestCreate(project_id=project.id, title='Launch', brief_docx_base64=payload), mock_db, MagicMock())
    assert exc.value.status_code == 400
    mock_db.add.assert_not_called()
    bridge.assert_not_called()


def test_word_zip_bomb_is_rejected_before_xml_expansion(mock_db, monkeypatch):
    project, bridge = setup_request(mock_db, monkeypatch)
    payload = docx('a' * (10 * 1024 * 1024 + 1))
    with pytest.raises(HTTPException) as exc:
        routes.create_request(routes.RequestCreate(project_id=project.id, title='Launch', brief_docx_base64=payload), mock_db, MagicMock())
    assert exc.value.status_code == 400
    mock_db.add.assert_not_called()


def test_word_rules_use_the_same_extractor(mock_db, monkeypatch):
    monkeypatch.setattr(routes, '_project_brand', lambda *a: 'cust-owned')
    bridge = MagicMock(return_value={'drafted': 1})
    monkeypatch.setattr(routes.review_bridge, 'import_rules', bridge)
    routes.import_rules(routes.RulesImport(project_id=uuid.uuid4(), docx_base64=docx()), mock_db, MagicMock())
    assert bridge.call_args.args[1] == 'Launch brief\nHook\tKeep logo\nvisible.'


def test_word_doctype_is_rejected_in_utf16_too():
    from apps.api.services.briefing import docx_text
    xml = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE w:document [<!ENTITY x "injected">]><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:document>'
    with pytest.raises(HTTPException):
        docx_text(docx(xml.encode('utf-16')))


@pytest.mark.parametrize('text', ['x' * 20001, 'Bad\x00text'], ids=['oversized', 'nul'])
def test_unreadable_or_oversized_request_text_is_rejected_before_writes(text, mock_db, monkeypatch):
    project, bridge = setup_request(mock_db, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        routes.create_request(routes.RequestCreate(project_id=project.id, title='Launch', brief_text=text), mock_db, MagicMock())
    assert exc.value.status_code == 400
    mock_db.add.assert_not_called()
    bridge.assert_not_called()


def test_combined_word_and_pasted_text_must_fit_request_limit(mock_db, monkeypatch):
    project, bridge = setup_request(mock_db, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        routes.create_request(routes.RequestCreate(project_id=project.id, title='Launch', brief_docx_base64=docx(), brief_text='x' * 19999), mock_db, MagicMock())
    assert exc.value.status_code == 400
    mock_db.add.assert_not_called()
    bridge.assert_not_called()


def test_word_rules_must_fit_complete_guideline_budget(mock_db, monkeypatch):
    monkeypatch.setattr(routes, '_project_brand', lambda *a: 'cust-owned')
    bridge = MagicMock(return_value={'drafted': 1})
    monkeypatch.setattr(routes.review_bridge, 'import_rules', bridge)
    with pytest.raises(HTTPException) as exc:
        routes.import_rules(routes.RulesImport(project_id=uuid.uuid4(), docx_base64=docx(), text='x' * 11999), mock_db, MagicMock())
    assert exc.value.status_code == 400
    bridge.assert_not_called()


@pytest.mark.parametrize('code, message', [('guide-limit', '12,000'), ('briefing-unavailable', 'anyone with the link')])
def test_guideline_input_errors_reach_owner_as_actionable_400(code, message, mock_db, monkeypatch):
    import httpx
    monkeypatch.setattr(routes, '_project_brand', lambda *a: 'cust-owned')
    monkeypatch.setattr(routes.review_bridge, 'is_configured', lambda: True)
    monkeypatch.setattr(routes.review_bridge.httpx, 'request', lambda *a, **kw: httpx.Response(400, json={'error': code, 'internal': 'must not leak'}))
    with pytest.raises(HTTPException) as exc:
        routes.import_rules(routes.RulesImport(project_id=uuid.uuid4(), url='https://docs.google.com/document/d/test/edit'), mock_db, MagicMock())
    assert exc.value.status_code == 400
    assert message in exc.value.detail
    assert 'must not leak' not in exc.value.detail


def test_unrecognized_guide_errors_do_not_cross_the_bridge(monkeypatch):
    import httpx
    monkeypatch.setattr(routes.review_bridge, 'is_configured', lambda: True)
    monkeypatch.setattr(routes.review_bridge.httpx, 'request', lambda *a, **kw: httpx.Response(400, json={'error': 'internal-secret'}))
    assert routes.review_bridge.import_rules('cust-owned', url='https://docs.google.com/document/d/test/edit') is None
