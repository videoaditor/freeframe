"""Card directives: what the person said about one job, filed with an agent request (replace-all list)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'ap15_request_directives'
down_revision = 'ap14_round_claim'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('upload_requests', sa.Column('directives', postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column('upload_requests', 'directives')
