"""Explicit AutoReview brand slug per project (Brand Loop). Nullable, no backfill."""
from alembic import op
import sqlalchemy as sa

revision = 'c9e1a2b3d4f5'
down_revision = 'b8d8a10b2026'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('autoreview_brand_slug', sa.String(length=120), nullable=True))
    op.create_index('ix_projects_autoreview_brand_slug', 'projects', ['autoreview_brand_slug'])


def downgrade():
    op.drop_index('ix_projects_autoreview_brand_slug', table_name='projects')
    op.drop_column('projects', 'autoreview_brand_slug')
