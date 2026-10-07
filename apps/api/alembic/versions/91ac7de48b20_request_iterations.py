"""Version-bound component requests and durable assembly state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '91ac7de48b20'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assets", sa.Column("iteration_derived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("asset_versions", sa.Column("iteration_review_ready", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("upload_requests", sa.Column("iteration_owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("assets", sa.Column("iteration_source", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('assets', sa.Column('iteration_pending', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('upload_requests', sa.Column('receive_iterations', sa.Boolean(), nullable=False, server_default=sa.false()))
    for name in ('iteration_manifest', 'iteration_state'):
        op.add_column('upload_requests', sa.Column(name, postgresql.JSONB(), nullable=True))
    op.add_column('upload_requests', sa.Column('iteration_mode', sa.String(20), nullable=False, server_default='components'))
    op.add_column('upload_requests', sa.Column('iteration_ratio', sa.String(5), nullable=False, server_default='9:16'))
    op.add_column('upload_requests', sa.Column('iteration_brief', sa.Text(), nullable=True))
    op.add_column('upload_requests', sa.Column('iteration_lease_token', sa.String(64), nullable=True))
    op.add_column('upload_requests', sa.Column('iteration_lease_until', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("assets", "iteration_derived")
    op.drop_column("asset_versions", "iteration_review_ready")
    op.drop_column("assets", "iteration_source")
    op.drop_column("upload_requests", "iteration_owner_id")
    for name in ('iteration_lease_until', 'iteration_lease_token', 'iteration_brief', 'iteration_ratio',
                 'iteration_mode', 'iteration_state', 'iteration_manifest', 'receive_iterations'):
        op.drop_column('upload_requests', name)
    op.drop_column('assets', 'iteration_pending')
