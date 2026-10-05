"""Durable product feedback and immutable daily Slack delivery batches."""
import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
try:
    from ..database import Base
except ImportError:
    from database import Base


class FeedbackDigest(Base):
    __tablename__ = 'feedback_digests'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    digest_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    slack_ts: Mapped[Optional[str]] = mapped_column(String(64))
    last_error: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ProductFeedback(Base):
    __tablename__ = 'product_feedback'
    __table_args__ = (
        UniqueConstraint('author_id', 'submission_id', name='uq_feedback_author_submission'),
        CheckConstraint("kind IN ('bug', 'idea')", name='ck_feedback_kind'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    suite_account_id: Mapped[Optional[str]] = mapped_column(String(255))
    campaign_id: Mapped[Optional[str]] = mapped_column(String(100))
    tool: Mapped[str] = mapped_column(String(32), nullable=False, default='autoreview')
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    page_path: Mapped[Optional[str]] = mapped_column(String(100))
    triage_status: Mapped[str] = mapped_column(String(16), nullable=False, default='received')
    digest_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('feedback_digests.id'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
