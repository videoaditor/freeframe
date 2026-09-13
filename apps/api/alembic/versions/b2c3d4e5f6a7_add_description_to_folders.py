"""add description to folders

A folder needs somewhere to name the Trello card it belongs to.

Aditor is moving from one project per card to one project per BRAND, with a folder per card
inside it. The card link is not decoration: it is what tells Auto Review which brand's rules to
judge against, which script to check, and which editor cut it. Projects already carry it in
`description`; folders had nowhere to put it at all.

Nullable and unused by upstream, so an instance that does not run the automation sees no change.

Revision ID: b2c3d4e5f6a7
Revises: f4e9c2a1b7d3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "f4e9c2a1b7d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("folders", sa.Column("description", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column("folders", "description")
