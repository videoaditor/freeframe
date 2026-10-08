"""Confirm staff workspace identity without backfilling or rewriting assignments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a8d8a10b2026'
down_revision = 'd5d7e10b2026'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('review_brand_binding', postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column('projects', 'review_brand_binding')
