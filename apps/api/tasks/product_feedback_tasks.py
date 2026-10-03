"""One backend-scheduled daily digest. Never call from a customer request."""
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from .celery_app import celery_app
from ..config import settings
from ..database import engine
from ..services.product_feedback import prepare_batch, deliver_batch, SlackFeedbackClient

# Dedicated PostgreSQL session lock survives commits and releases on connection loss.
FEEDBACK_LOCK = 724019863


def run_feedback_digest():
    if not settings.product_feedback_slack_token:
        return 'unconfigured'
    with engine.connect() as connection:
        locked = connection.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': FEEDBACK_LOCK}).scalar()
        connection.commit()
        if not locked:
            return 'busy'
        try:
            with Session(bind=connection) as db:
                batch = prepare_batch(db, datetime.now(timezone.utc),
                                      settings.product_feedback_slack_channel, settings.frontend_url)
                return deliver_batch(db, batch, SlackFeedbackClient(settings.product_feedback_slack_token))
        finally:
            connection.rollback()
            connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': FEEDBACK_LOCK})
            connection.commit()


@celery_app.task(name='send_product_feedback_digest', bind=True, max_retries=3)
def send_product_feedback_digest(self):
    try:
        return run_feedback_digest()
    except Exception as exc:
        # Original feedback stays durable. Retry delivery/reconciliation, not intake.
        raise self.retry(exc=exc, countdown=900)
