"""Store server-attested Suite campaign context independently of preferences."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e4f5a6b7c8d9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('suite_campaign', sa.JSON(), nullable=True))
    op.create_table('campaign_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('campaign_id', sa.String(80), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('user_id', 'campaign_id', 'asset_id', name='uq_campaign_review_asset'))


def downgrade():
    op.drop_table('campaign_reviews')
    op.drop_column('users', 'suite_campaign')
