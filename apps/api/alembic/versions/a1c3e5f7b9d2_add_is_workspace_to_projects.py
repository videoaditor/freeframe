"""add is_workspace flag to projects

A brand workspace is the one project editors file hand-ins into. Marking it with a real flag - not
a name convention - lets the hand-in dropdown show only workspaces and hide the per-card junk
projects that piled up, without renaming or merging anything.

Backfills the clear case: every existing project whose name ends "- Workspace" (the 13 brand
projects renamed 2026-09-13) is a workspace. Brand projects without that suffix, and the dedup of
leftover duplicates, are flagged by hand afterwards - the flag makes that reversible and
non-destructive (no rename, no data movement).

Revision ID: a1c3e5f7b9d2
Revises: b2c3d4e5f6a7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f7b9d2"
# Chain onto the real single head (the migration the prod DB is at), NOT c8d9e2f1a3b4 - that is an
# ancestor on a since-merged branch, and pointing at it forked the tree into two heads, which crashed
# `alembic upgrade head` on deploy.
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_workspace", sa.Boolean(), nullable=False, server_default="false"),
    )
    # The 13 brand projects already carry the "- Workspace" suffix; flag them so the hand-in dropdown
    # works the moment this ships. Everything else stays false until marked by hand.
    op.execute(
        "UPDATE projects SET is_workspace = true "
        "WHERE name ILIKE '%% - workspace' AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("projects", "is_workspace")
