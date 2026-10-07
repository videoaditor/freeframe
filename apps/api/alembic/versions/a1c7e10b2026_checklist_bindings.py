"""Persist authorized checklist intent independently of upload/folder creation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = 'a1c7e10b2026'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('checklist_bindings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('source_key', sa.String(160), nullable=False),
        sa.Column('trello_card_id', sa.String(24)),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('upload_requests.id')),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('folders.id')),
        sa.Column('intent', postgresql.JSONB(), nullable=False),
        sa.Column('intent_sha256', sa.String(64), nullable=False),
        sa.Column('snapshot', postgresql.JSONB()),
        sa.Column('context_sha256', sa.String(64)),
        sa.Column('plan_id', sa.String(255)),
        sa.Column('content_sha256', sa.String(64)),
        sa.Column('plan', postgresql.JSONB()),
        sa.Column('status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('error_code', sa.String(80)),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True)),
        sa.Column('review_share_token', sa.String(64)),
        sa.Column('registration_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('registration_error', sa.String(80)),
        sa.Column('next_registration_at', sa.DateTime(timezone=True)),
        sa.Column('registered_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('project_id', 'source_key', name='uq_checklist_project_source'),
        sa.UniqueConstraint('request_id', name='uq_checklist_request'),
        sa.UniqueConstraint('folder_id', name='uq_checklist_folder'),
        sa.CheckConstraint("status IN ('queued','preparing','running','ready','failed')", name='ck_checklist_status'),
    )
    op.create_index('ix_checklist_bindings_project_id', 'checklist_bindings', ['project_id'])


def downgrade():
    op.drop_index('ix_checklist_bindings_project_id', table_name='checklist_bindings')
    op.drop_table('checklist_bindings')
