"""Append each event's folder and Trello card to n8n_feedback_events.

Revision ID: 3b8e1d6c9f20
Revises: a1c3e5f7b9d2
Create Date: 2026-09-29

A folder usually stands for one Trello card: its name is the card title and its
description often carries the card link. An n8n consumer that follows up on
review comments needs that identity to tell "a new round was delivered for this
card" - often as new assets in another project with the same file names - from
"nothing happened". Matching by file name alone confuses cards whose videos
share generic names such as "Hook 1".

The three columns are appended after the freeframe-feedback.v1 columns, which
stay untouched (AGENTS.md: compatibility contract). The v1 SELECT is reused from
the migration that owns it, so the two can never drift apart.
"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = "3b8e1d6c9f20"
down_revision: Union[str, Sequence[str], None] = "a1c3e5f7b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_v1():
    path = next(Path(__file__).parent.glob("*_version_n8n_feedback_events.py"))
    spec = importlib.util.spec_from_file_location("n8n_feedback_events_v1", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


V1 = _load_v1()

CARD_COLUMNS = ("folder_id", "folder_name", "trello_card_id")
FEEDBACK_EVENT_COLUMNS = V1.FEEDBACK_EVENT_COLUMNS + CARD_COLUMNS

# Everything after the v1 header "CREATE OR REPLACE VIEW ... (<columns>) AS".
V1_SELECT_SQL = V1.N8N_FEEDBACK_EVENTS_VIEW_SQL.split(") AS\n", 1)[1]

# The folder is read without a deleted_at filter, like the tombstone rows'
# parents: an event must keep its card when the folder is deleted later.
N8N_FEEDBACK_EVENTS_VIEW_SQL = f"""
CREATE OR REPLACE VIEW n8n_feedback_events ({", ".join(FEEDBACK_EVENT_COLUMNS)}) AS
SELECT
    e.*,
    f.id AS folder_id,
    f.name::text AS folder_name,
    substring(f.description FROM 'trello\\.com/c/([A-Za-z0-9]+)') AS trello_card_id
FROM (
{V1_SELECT_SQL}
) AS e
LEFT JOIN assets fa ON fa.id = e.asset_id
LEFT JOIN folders f ON f.id = fa.folder_id
"""

UPGRADE_SQL = (
    N8N_FEEDBACK_EVENTS_VIEW_SQL,
    V1.CONDITIONAL_GRANTS_SQL,
)

# A view cannot drop columns in place; recreate the v1 view and its read grant.
DOWNGRADE_SQL = (
    "DROP VIEW IF EXISTS n8n_feedback_events",
    V1.N8N_FEEDBACK_EVENTS_VIEW_SQL,
    V1.CONDITIONAL_GRANTS_SQL,
)


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_SQL:
        op.execute(statement)
