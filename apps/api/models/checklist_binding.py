"""One durable preparation intent per authorized assignment, shared by all versions."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
try:
    from ..database import Base
except ImportError:
    from database import Base


class ChecklistBinding(Base):
    __tablename__ = 'checklist_bindings'
    __table_args__ = (
        UniqueConstraint('project_id', 'source_key', name='uq_checklist_project_source'),
        UniqueConstraint('request_id', name='uq_checklist_request'),
        UniqueConstraint('folder_id', name='uq_checklist_folder'),
        CheckConstraint("status IN ('queued','preparing','running','ready','failed')", name='ck_checklist_status'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('projects.id'), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    trello_card_id: Mapped[Optional[str]] = mapped_column(String(24))
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('upload_requests.id'))
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('folders.id'))
    intent: Mapped[dict] = mapped_column(JSONB, nullable=False)
    intent_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    context_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    plan_id: Mapped[Optional[str]] = mapped_column(String(255))
    content_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    plan: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='queued', server_default='queued')
    error_code: Mapped[Optional[str]] = mapped_column(String(80))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_share_token: Mapped[Optional[str]] = mapped_column(String(64))
    registered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
