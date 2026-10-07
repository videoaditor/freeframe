"""Private durable voice recordings for product feedback."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('feedback_recordings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('s3_key', sa.String(512), nullable=False),
        sa.Column('content_sha256', sa.String(64), nullable=False),
        sa.Column('content_type', sa.String(64), nullable=False),
        sa.Column('transcript', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
    )
    op.add_column('product_feedback', sa.Column('recording_id', postgresql.UUID(as_uuid=True)))
    op.create_foreign_key('fk_product_feedback_recording_id', 'product_feedback', 'feedback_recordings', ['recording_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_product_feedback_recording_id', 'product_feedback', type_='foreignkey')
    op.drop_column('product_feedback', 'recording_id')
    op.drop_table('feedback_recordings')
