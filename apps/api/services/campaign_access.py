"""FreeFrame enforcement for Suite-attested promotional access.

Never read permissions from user preferences or campaign query parameters.
The fixed local cutoff also applies while a positive Suite response is cached.
"""
import time

from fastapi import HTTPException
from sqlalchemy.orm import object_session
from ..models.user import User
from ..models.project import Project

TELEHEALTH = {'id': 'telehealth_october_2026', 'tool': 'autoreview', 'endsAt': '2026-11-01T04:00:00Z'}
ENDS_AT_TIMESTAMP = 1793505600


def validate_context(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or any(value.get(k) != v for k, v in TELEHEALTH.items())
            or type(value.get('previewOnly')) is not bool or value.get('state') not in ('active', 'expired')):
        raise HTTPException(503, 'Trial access could not be verified. Try again shortly.')
    return {**TELEHEALTH, 'previewOnly': value['previewOnly'],
            'state': 'expired' if time.time() >= ENDS_AT_TIMESTAMP else 'active'}


def context(user):
    value = getattr(user, 'suite_campaign', None)
    return validate_context(value) if isinstance(value, dict) else None


def preview_expired(user):
    value = context(user)
    return bool(value and value['previewOnly'] and value['state'] == 'expired')


def expired_error():
    return HTTPException(403, {'code': 'campaign_expired',
        'message': 'The Telehealth preview has ended. Choose a plan to keep reviewing.',
        'endsAt': TELEHEALTH['endsAt']})


def save_context(user, value):
    value = validate_context(value)
    # A known cohort disappearing is a broken upstream contract, not a free upgrade.
    if context(user) is not None and value is None:
        raise HTTPException(503, 'Trial access could not be verified. Try again shortly.')
    if getattr(user, 'suite_campaign', None) != value:
        user.suite_campaign = value
        session = object_session(user)
        if session is not None:
            session.commit()


def require_brand_slot(db, user):
    value = context(user)
    if not value or not value['previewOnly']:
        return
    # Serialize brand creation for this owner; the lock remains until create_project commits.
    db.query(User).filter(User.id == user.id).with_for_update().one()
    if db.query(Project).filter(Project.created_by == user.id, Project.deleted_at.is_(None)).first():
        raise HTTPException(409, 'Your preview includes one brand. Add another request inside your existing brand.')


def require_project_access(db, owner_id):
    """Apply the cutoff to anonymous request/share links owned by a preview customer."""
    if owner_id is None:
        return
    owner = db.get(User, owner_id)
    if not owner:
        return
    campaign = context(owner)
    if not campaign or campaign['state'] != 'expired':
        return
    # Owner sign-in/refresh records a paid upgrade before links resume. A saved
    # upgrade is not permanent: verify its current paid grant without committing
    # inside guest upload transactions that hold row locks.
    if campaign['previewOnly']:
        raise expired_error()
    from .whop_auth import require_current_campaign_paid_access
    require_current_campaign_paid_access(owner)
