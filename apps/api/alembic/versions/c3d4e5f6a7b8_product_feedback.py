"""Durable product feedback and daily digest checkpoints."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c3d4e5f6a7b8'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('feedback_digests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('digest_date', sa.Date(), nullable=False, unique=True),
        sa.Column('channel_id', sa.String(64), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('slack_ts', sa.String(64)),
        sa.Column('last_error', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
    )
    op.create_table('product_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('suite_account_id', sa.String(255)),
        sa.Column('campaign_id', sa.String(100)),
        sa.Column('tool', sa.String(32), nullable=False),
        sa.Column('kind', sa.String(8), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('page_path', sa.String(100)),
        sa.Column('triage_status', sa.String(16), nullable=False),
        sa.Column('digest_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('feedback_digests.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('author_id', 'submission_id', name='uq_feedback_author_submission'),
        sa.CheckConstraint("kind IN ('bug', 'idea')", name='ck_feedback_kind'),
    )
    op.create_index('ix_product_feedback_digest_id', 'product_feedback', ['digest_id'])
    op.create_index('ix_product_feedback_created_at', 'product_feedback', ['created_at'])


def downgrade():
    op.drop_table('product_feedback')
    op.drop_table('feedback_digests')
