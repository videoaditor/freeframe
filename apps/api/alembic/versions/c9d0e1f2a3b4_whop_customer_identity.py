"""Bind Whop customer accounts to immutable Suite identity; preserve existing users.

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
"""
from alembic import op
import sqlalchemy as sa

revision = 'c9d0e1f2a3b4'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('suite_account_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('suite_brand_id', sa.String(255), nullable=True))
    op.create_unique_constraint('uq_users_suite_account_id', 'users', ['suite_account_id'])
    op.create_unique_constraint('uq_users_suite_brand_id', 'users', ['suite_brand_id'])


def downgrade():
    op.drop_constraint('uq_users_suite_brand_id', 'users', type_='unique')
    op.drop_constraint('uq_users_suite_account_id', 'users', type_='unique')
    op.drop_column('users', 'suite_brand_id')
    op.drop_column('users', 'suite_account_id')
