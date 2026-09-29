"""Pure contracts for the card columns appended to n8n_feedback_events."""

import importlib.util
from pathlib import Path


VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
CARD_MIGRATION_PATHS = list(VERSIONS_DIR.glob("*_append_card_to_n8n_feedback_events.py"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_card_migration():
    assert len(CARD_MIGRATION_PATHS) == 1, "expected exactly one card migration"
    return _load(CARD_MIGRATION_PATHS[0], "n8n_feedback_card_migration")


def test_card_columns_are_appended_after_the_untouched_v1_contract():
    migration = _load_card_migration()
    v1 = migration.V1

    assert migration.down_revision == "a1c3e5f7b9d2"
    assert migration.FEEDBACK_EVENT_COLUMNS[: len(v1.FEEDBACK_EVENT_COLUMNS)] == v1.FEEDBACK_EVENT_COLUMNS
    assert migration.FEEDBACK_EVENT_COLUMNS[len(v1.FEEDBACK_EVENT_COLUMNS):] == (
        "folder_id",
        "folder_name",
        "trello_card_id",
    )
    assert v1.SOURCE_CONTRACT_VERSION == "freeframe-feedback.v1"


def test_view_wraps_the_v1_select_verbatim_and_joins_the_folder():
    migration = _load_card_migration()
    sql = migration.N8N_FEEDBACK_EVENTS_VIEW_SQL

    assert sql.lstrip().startswith("CREATE OR REPLACE VIEW n8n_feedback_events")
    assert migration.V1_SELECT_SQL in sql
    assert migration.V1_SELECT_SQL.lstrip().startswith("-- A comment ID is stable")
    assert "LEFT JOIN assets fa ON fa.id = e.asset_id" in sql
    assert "LEFT JOIN folders f ON f.id = fa.folder_id" in sql
    # The card id is the Trello short link in the folder description.
    assert "trello\\.com/c/([A-Za-z0-9]+)" in sql
    # A deleted folder keeps its events' card, like tombstones keep their parents.
    assert "f.deleted_at" not in sql


def test_grants_stay_view_only_and_downgrade_restores_v1():
    migration = _load_card_migration()
    v1 = migration.V1
    upgrade_sql = "\n".join(migration.UPGRADE_SQL)
    downgrade_sql = "\n".join(migration.DOWNGRADE_SQL)

    assert "GRANT SELECT ON n8n_feedback_events, n8n_share_links TO n8n_read" in upgrade_sql
    for table in ("folders", "assets", "comments", "projects"):
        assert f"GRANT SELECT ON {table}" not in upgrade_sql

    assert migration.DOWNGRADE_SQL[0] == "DROP VIEW IF EXISTS n8n_feedback_events"
    assert v1.N8N_FEEDBACK_EVENTS_VIEW_SQL in migration.DOWNGRADE_SQL
    assert v1.CONDITIONAL_GRANTS_SQL in migration.DOWNGRADE_SQL
    for forbidden in ("DROP TABLE", "DELETE FROM", "TRUNCATE", "UPDATE ", "INSERT INTO"):
        assert forbidden not in downgrade_sql
