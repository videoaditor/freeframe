"""Durable, unique successfully reviewed ads used for plan recommendations."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
try:
    from ..database import Base
except ImportError:
    from database import Base


class CampaignReview(Base):
    __tablename__ = 'campaign_reviews'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(80), nullable=False)
    # Immutable source identifier: retain recommendation evidence after media retention GC.
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint('user_id', 'campaign_id', 'asset_id', name='uq_campaign_review_asset'),)
