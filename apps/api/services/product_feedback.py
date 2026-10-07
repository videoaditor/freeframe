"""Plain-text feedback delivery; customer content is data, never agent instructions.

A network timeout cannot prove Slack rejected a post. Keep those batches in
`sending` and reconcile history; never risk a duplicate by blindly posting again.
"""
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from ..models.product_feedback import ProductFeedback, FeedbackDigest


class SlackRejected(RuntimeError):
    """Slack explicitly rejected the request; safe to retry."""


class DeliveryUncertain(RuntimeError):
    """Potentially accepted: reconcile or require operator intervention."""


def safe_excerpt(message):
    text = re.sub(r'https?://\S+', '[link omitted]', message)
    text = re.sub(r'(?i)\b(authorization|password|secret|token|api[_-]?key)\s*[:=]\s*\S+', r'\1=[redacted]', text)
    text = re.sub(r'\b(?:xox[baprs]-[\w-]+|sk-[\w-]{12,}|eyJ[\w-]+\.[\w-]+\.[\w-]+)\b', '[redacted]', text)
    text = ' '.join(text.split())[:240]
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def format_digest(rows, frontend_url):
    bugs = sum(row.kind == 'bug' for row in rows)
    lines = [f'AutoReview feedback: {len(rows)} new reports ({bugs} bugs, {len(rows) - bugs} ideas)',
             'Customer reports for human triage; no automatic actions.']
    for row in rows[:40]:
        excerpt = safe_excerpt(row.message) if row.message else 'Voice recording — listen in the staff queue'
        lines.append(f'• {row.tool} · {row.campaign_id or "no campaign"} · {row.kind}: {excerpt}')
    if len(rows) > 40:
        lines.append(f'{len(rows) - 40} additional reports are in the staff queue.')
    parsed = urlsplit(frontend_url)
    # Configured origin only: never echo a credential, query or fragment into Slack.
    if parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username:
        lines.append(f'Staff queue: {parsed.scheme}://{parsed.netloc}/feedback')
    return '\n'.join(lines)


def prepare_batch(db, now, channel_id, frontend_url):
    # One confirmed digest per UTC calendar day, including a retried older batch.
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if db.query(FeedbackDigest).filter(
        FeedbackDigest.delivered_at >= midnight, FeedbackDigest.deleted_at.is_(None),
    ).first():
        return None
    pending = db.query(FeedbackDigest).filter(
        FeedbackDigest.status != 'delivered', FeedbackDigest.deleted_at.is_(None),
    ).order_by(FeedbackDigest.created_at).first()
    if pending:
        return pending
    if db.query(FeedbackDigest).filter(
        FeedbackDigest.digest_date == now.date(), FeedbackDigest.deleted_at.is_(None),
    ).first():
        return None
    rows = db.query(ProductFeedback).filter(
        ProductFeedback.digest_id.is_(None), ProductFeedback.deleted_at.is_(None),
        ProductFeedback.created_at <= now,
    ).order_by(ProductFeedback.created_at, ProductFeedback.id).all()
    if not rows:
        return None
    batch = FeedbackDigest(id=uuid.uuid4(), digest_date=now.date(), channel_id=channel_id,
                           text=format_digest(rows, frontend_url), status='pending')
    db.add(batch)
    db.flush()
    for row in rows:
        row.digest_id = batch.id
    db.commit()  # Immutable membership and payload survive any subsequent failure.
    return batch


def deliver_batch(db, batch, slack):
    if batch is None:
        return 'empty'
    if batch.status == 'delivered':
        return 'delivered'
    if batch.status == 'sending':
        ts = slack.find(batch)
        if not ts:
            batch.last_error = 'Uncertain delivery: inspect Slack before retrying the post'
            db.commit()
            raise DeliveryUncertain(batch.last_error)
    else:
        batch.status = 'sending'
        batch.last_error = None
        db.commit()  # Persist BEFORE contacting Slack, including on worker death.
        try:
            ts = slack.post(batch)
        except SlackRejected as exc:
            batch.status = 'pending'
            batch.last_error = str(exc)[:255]
            db.commit()
            raise
        except Exception as exc:
            batch.last_error = 'Uncertain Slack response; reconciliation required'
            db.commit()
            raise DeliveryUncertain(batch.last_error) from exc
    batch.status = 'delivered'
    batch.slack_ts = ts
    batch.delivered_at = datetime.now(timezone.utc)
    batch.last_error = None
    db.commit()
    return 'delivered'


class SlackFeedbackClient:
    def __init__(self, token):
        self.token = token

    def request(self, method, payload):
        response = httpx.post(f'https://slack.com/api/{method}', json=payload,
                              headers={'Authorization': f'Bearer {self.token}'}, timeout=20)
        if response.status_code == 429:
            raise SlackRejected('ratelimited')
        response.raise_for_status()  # 5xx may have accepted the post: ambiguous.
        data = response.json()
        if not data.get('ok'):
            error = str(data.get('error', 'slack_rejected'))[:100]
            # Slack documents these as partial/unknown outcomes, so never resend.
            if error in {'internal_error', 'fatal_error', 'request_timeout', 'service_unavailable'}:
                raise DeliveryUncertain(error)
            raise SlackRejected(error)
        return data

    def post(self, batch):
        data = self.request('chat.postMessage', {
            'channel': batch.channel_id, 'text': batch.text,
            'mrkdwn': False, 'parse': 'none', 'unfurl_links': False, 'unfurl_media': False,
            'metadata': {'event_type': 'freeframe_feedback_digest', 'event_payload': {'batch_id': str(batch.id)}},
        })
        if not data.get('ts'):
            raise DeliveryUncertain('Slack receipt missing')
        return data['ts']

    def find(self, batch):
        cursor = None
        # Bounded reconciliation; if history is inaccessible or too long, fail closed.
        for _ in range(20):
            payload = {'channel': batch.channel_id, 'oldest': str(batch.created_at.timestamp()),
                       'limit': 100, 'include_all_metadata': True}
            if cursor:
                payload['cursor'] = cursor
            data = self.request('conversations.history', payload)
            for message in data.get('messages', []):
                metadata = message.get('metadata', {})
                if (metadata.get('event_type') == 'freeframe_feedback_digest'
                        and metadata.get('event_payload', {}).get('batch_id') == str(batch.id)):
                    return message['ts']
            cursor = data.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                return None
        raise DeliveryUncertain('Slack history reconciliation incomplete')
