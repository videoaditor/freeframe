"""Workspace rounds: feedback_rounds.claimed_by / claimed_at (which agent key is working on a closed round)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'ap14_round_claim'
down_revision = 'ap13_agent_readable_feedback'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('feedback_rounds', sa.Column('claimed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('feedback_rounds', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('feedback_rounds', 'claimed_at')
    op.drop_column('feedback_rounds', 'claimed_by')
