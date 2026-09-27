"""A file request: Dropbox-style "request files", with the review built in (platform v2).

An owner creates one per hand-in they want: it gets its own folder and its own public token. The
editor who opens /r/<token> uploads without an account - the token is the permission, exactly as a
share link is for viewing. Every upload lands in the request's folder, so a second upload of the
same file name is the next VERSION of that asset, never a stray copy.

`review_share_token` is the standing comment+download link Auto Review reads the folder through.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

try:
    from ..database import Base
except ImportError:
    from database import Base


class UploadRequest(Base):
    __tablename__ = "upload_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    folder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("folders.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_slug: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    review_share_token: Mapped[str] = mapped_column(String(64), nullable=False)
    brief_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_uploader_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_uploader_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
