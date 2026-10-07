"""Nullable trusted comment provenance and replay identity (H2).

Revision ID: a7b2c3d4e5f6
Revises: e4f5a6b7c8d9
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7b2c3d4e5f6"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("comments", sa.Column("review_source", postgresql.JSONB(), nullable=True))
    op.add_column("comments", sa.Column("review_publication_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("comments", sa.Column("review_publication_sha256", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_comments_review_publication_id", "comments", ["review_publication_id"])


def downgrade():
    op.drop_constraint("uq_comments_review_publication_id", "comments", type_="unique")
    op.drop_column("comments", "review_publication_sha256")
    op.drop_column("comments", "review_publication_id")
    op.drop_column("comments", "review_source")
