"""Explicit staff workspace identity. The private Worker attests Trello IDs; owners assign them."""
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from ..models.checklist_binding import ChecklistBinding
from ..models.folder import Folder
from ..models.upload_request import UploadRequest
from . import review_bridge

CARD_URL = re.compile(r'https://(?:www\.)?trello\.com/c/([A-Za-z0-9]{8}|[a-f0-9]{24})(?:/[^?#\s]*)?/?')


def confirmed_brand(project):
    value = getattr(project, 'review_brand_binding', None)
    if value is None:
        return None
    invalid = HTTPException(409, 'Workspace brand identity is invalid')
    if not isinstance(value, dict) or not all(isinstance(value.get(key), str)
        for key in ('brand_slug','board_id','card_id','confirmed_by','confirmed_at')):
        raise invalid
    if (not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value['brand_slug'])
        or value['brand_slug'].startswith('cust-')
        or not re.fullmatch(r'[a-f0-9]{24}', value['board_id'])
        or not re.fullmatch(r'[a-f0-9]{24}', value['card_id'])):
        raise invalid
    try:
        uuid.UUID(value['confirmed_by'])
        confirmed_at = datetime.fromisoformat(value['confirmed_at'])
    except ValueError:
        raise invalid
    if confirmed_at.utcoffset() is None:
        raise invalid
    return value


def attest_card(url):
    match = CARD_URL.fullmatch((url or '').strip())
    if not match:
        raise HTTPException(409, 'An exact Trello card link is required')
    card = review_bridge.checklist_card(f'https://trello.com/c/{match[1]}')
    if not isinstance(card, dict):
        raise HTTPException(503, 'Card identity could not be verified')
    if (not re.fullmatch(r'[a-f0-9]{24}', str(card.get('card_id', '')))
        or not re.fullmatch(r'[A-Za-z0-9]{8}', str(card.get('short_link', '')))
        or match[1] != card.get('card_id' if len(match[1]) == 24 else 'short_link')
        or not re.fullmatch(r'[a-f0-9]{24}', str(card.get('board_id', '')))
        or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', str(card.get('brand_slug', '')))
        or str(card.get('brand_slug', '')).startswith('cust-')):
        raise HTTPException(409, 'Card has no confirmed active board brand')
    return card


def require_project_card(project, card):
    bound = confirmed_brand(project)
    if bound and (card.get('board_id') != bound['board_id'] or card.get('brand_slug') != bound['brand_slug']):
        raise HTTPException(409, 'Card belongs to a different workspace brand')


def require_card_reference(project, reference):
    if 'trello.com/c/' in (reference or '') and confirmed_brand(project):
        require_project_card(project, attest_card(reference))


def propose_brand(db, project, user, source_url, apply):
    """Caller already checked active staff ownership and locks this one project row."""
    source = attest_card(source_url)
    prior = confirmed_brand(project)
    if prior and (prior['brand_slug'] != source['brand_slug'] or prior['board_id'] != source['board_id']):
        raise HTTPException(409, 'Workspace already has a confirmed brand; use a new workspace')
    # A card in another project proves no membership here. Only inspect this authorized workspace.
    references = {f.description.strip() for f in db.query(Folder).filter(
        Folder.project_id == project.id, Folder.deleted_at.is_(None)).all()
        if 'trello.com/c/' in (f.description or '')}
    bindings = db.query(ChecklistBinding).filter(ChecklistBinding.project_id == project.id,
        ChecklistBinding.deleted_at.is_(None)).all()
    references.update(f'https://trello.com/c/{b.trello_card_id}' for b in bindings if b.trello_card_id)
    for ref in sorted(references):
        card = source if ref.rstrip('/') in {source_url.rstrip('/'), f"https://trello.com/c/{source['card_id']}"} else attest_card(ref)
        if card['board_id'] != source['board_id'] or card['brand_slug'] != source['brand_slug']:
            raise HTTPException(409, 'Workspace contains multiple board identities; choose a separate workspace')
    requests = db.query(UploadRequest).filter(UploadRequest.project_id == project.id).all()
    requires_new = any(r.brand_slug != source['brand_slug'] for r in requests) or any(
        (b.intent or {}).get('brand') != source['brand_slug'] for b in bindings)
    value = prior or {'brand_slug': source['brand_slug'], 'board_id': source['board_id'],
        'card_id': source['card_id'], 'confirmed_by': str(user.id), 'confirmed_at': datetime.now(timezone.utc).isoformat()}
    if apply and prior is None:
        project.review_brand_binding = value
        db.commit()
    return {'project_id': str(project.id), 'brand_slug': source['brand_slug'], 'board_id': source['board_id'],
        'applied': bool(apply), 'binding': value if apply or prior else None,
        'requires_new_assignment': requires_new}
