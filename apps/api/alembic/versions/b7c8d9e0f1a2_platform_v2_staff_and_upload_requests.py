"""platform v2: users.is_staff and upload_requests

Every existing account becomes staff (server default true), so nothing changes for the team; only
self-signed-up customers are created with is_staff = false.

Revision ID: b7c8d9e0f1a2
Revises: a1c3e5f7b9d2
Create Date: 2026-09-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a1c3e5f7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_staff', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        'upload_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('folders.id'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('brand_slug', sa.String(120), nullable=False, server_default=''),
        sa.Column('review_share_token', sa.String(64), nullable=False),
        sa.Column('brief_excerpt', sa.Text(), nullable=True),
        sa.Column('last_uploader_name', sa.String(255), nullable=True),
        sa.Column('last_uploader_email', sa.String(255), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_upload_requests_token', 'upload_requests', ['token'], unique=True)
    op.create_index('ix_upload_requests_project_id', 'upload_requests', ['project_id'])
    op.create_table(
        'request_uploads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('upload_requests.id'), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('uploader_name', sa.String(255), nullable=False),
        sa.Column('uploader_email', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_request_uploads_request_id', 'request_uploads', ['request_id'])
    op.create_index('ix_request_uploads_asset_id', 'request_uploads', ['asset_id'])
    op.create_index('ix_request_uploads_uploader_email', 'request_uploads', ['uploader_email'])


def downgrade() -> None:
    op.drop_table('request_uploads')
    op.drop_index('ix_upload_requests_project_id', table_name='upload_requests')
    op.drop_index('ix_upload_requests_token', table_name='upload_requests')
    op.drop_table('upload_requests')
    op.drop_column('users', 'is_staff')
