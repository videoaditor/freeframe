"""Persist exact-version editor handoff and successful transfer evidence."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('upload_requests', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('upload_requests', sa.Column('completion_versions', postgresql.JSONB(), nullable=True))
    op.add_column('request_uploads', sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True))
    # Only processing/ready prove that a historical multipart transfer completed.
    op.execute("""UPDATE request_uploads AS u SET submitted_at = u.created_at
        FROM asset_versions AS v WHERE v.asset_id = u.asset_id
        AND v.version_number = u.version_number AND v.deleted_at IS NULL
        AND v.processing_status IN ('processing', 'ready')""")


def downgrade():
    op.drop_column('request_uploads', 'submitted_at')
    op.drop_column('upload_requests', 'completion_versions')
    op.drop_column('upload_requests', 'completed_at')
