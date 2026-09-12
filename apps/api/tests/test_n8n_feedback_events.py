"""Pure contracts for the migration-owned n8n database surface."""

import importlib.util
from pathlib import Path


VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
MIGRATION_PATHS = list(VERSIONS_DIR.glob("*_version_n8n_feedback_events.py"))

LEGACY_FEEDBACK_COLUMNS = (
    "event_id",
    "event_type",
    "created_at",
    "project_id",
    "project_name",
    "asset_id",
    "asset_name",
    "version_id",
    "version_number",
    "author_kind",
    "author_email",
    "author_name",
    "body",
    "status",
    "timecode_start",
    "timecode_end",
    "resolved",
    "visibility",
    "parent_id",
    "owner_email",
    "owner_name",
)

FEEDBACK_COLUMNS = LEGACY_FEEDBACK_COLUMNS + (
    "comment_id",
    "source_event_kind",
    "event_occurred_at",
    "source_updated_at",
    "source_deleted_at",
    "source_contract_version",
)

SHARE_LINK_COLUMNS = (
    "token",
    "asset_id",
    "project_id",
    "created_by",
    "created_at",
    "is_enabled",
    "permission",
    "scope",
)


def _load_migration():
    assert len(MIGRATION_PATHS) == 1, "expected exactly one n8n feedback migration"
    spec = importlib.util.spec_from_file_location("n8n_feedback_migration", MIGRATION_PATHS[0])
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_exports_the_versioned_consumer_contract():
    migration = _load_migration()

    assert migration.down_revision == "a9ee0209151a"
    assert migration.SOURCE_CONTRACT_VERSION == "freeframe-feedback.v1"
    assert migration.LEGACY_FEEDBACK_EVENT_COLUMNS == LEGACY_FEEDBACK_COLUMNS
    assert migration.FEEDBACK_EVENT_COLUMNS == FEEDBACK_COLUMNS
    assert migration.FEEDBACK_EVENT_COLUMNS[: len(LEGACY_FEEDBACK_COLUMNS)] == LEGACY_FEEDBACK_COLUMNS
    assert migration.SHARE_LINK_COLUMNS == SHARE_LINK_COLUMNS


def test_captured_view_contract_is_preserved_before_appended_event_metadata():
    migration = _load_migration()
    feedback_sql = migration.N8N_FEEDBACK_EVENTS_VIEW_SQL
    share_sql = migration.N8N_SHARE_LINKS_VIEW_SQL

    assert feedback_sql.lstrip().startswith(
        "CREATE OR REPLACE VIEW n8n_feedback_events"
    )
    for column in LEGACY_FEEDBACK_COLUMNS:
        assert column in feedback_sql
    assert "c.id AS event_id" in feedback_sql
    assert "c.created_at AS created_at" in feedback_sql
    assert "c.id AS comment_id" in feedback_sql
    assert "source_event_kind" in feedback_sql
    assert "event_occurred_at" in feedback_sql
    assert "source_updated_at" in feedback_sql
    assert "source_deleted_at" in feedback_sql
    assert "source_contract_version" in feedback_sql

    assert share_sql.lstrip().startswith("CREATE OR REPLACE VIEW n8n_share_links")
    assert share_sql.count("UNION ALL") == 2
    for scope in ("asset", "folder", "project"):
        assert f"'{scope}'" in share_sql
    assert "s.token AS token" in share_sql
    assert "s.permission::text AS permission" in share_sql


def test_comment_revisions_and_tombstones_are_cursorable_without_parent_filter_loss():
    migration = _load_migration()
    feedback_sql = migration.N8N_FEEDBACK_EVENTS_VIEW_SQL

    assert "WHEN c.updated_at IS NOT NULL AND c.updated_at > c.created_at THEN 'updated'" in feedback_sql
    assert "WHEN c.updated_at IS NOT NULL AND c.updated_at > c.created_at THEN c.updated_at" in feedback_sql
    assert "'deleted'::text AS source_event_kind" in feedback_sql
    assert "c.deleted_at AS source_deleted_at" in feedback_sql

    tombstone_sql = feedback_sql.split(
        "-- A separate non-public event type keeps every legacy comment query's row set",
        1,
    )[1].split("UNION ALL", 1)[0]
    assert "WHERE c.deleted_at IS NOT NULL" in tombstone_sql
    assert "a.deleted_at IS NULL" not in tombstone_sql
    assert "p.deleted_at IS NULL" not in tombstone_sql
    assert "'tombstone' AS visibility" in tombstone_sql


def test_notifications_are_append_only_and_grants_are_conditional_view_reads():
    migration = _load_migration()
    notify_sql = migration.NOTIFY_FUNCTION_SQL
    trigger_sql = "\\n".join(migration.TRIGGER_SQL)
    grant_sql = migration.CONDITIONAL_GRANTS_SQL
    downgrade_sql = "\\n".join(migration.DOWNGRADE_SQL)

    assert "pg_catalog.pg_notify" in notify_sql
    assert "'feedback_event'" in notify_sql
    assert "'event_kind', event_kind" in notify_sql
    assert "body" not in notify_sql
    for trigger_name in (
        "trg_notify_comment",
        "trg_notify_comment_changed",
        "trg_notify_approval",
        "trg_notify_version",
        "trg_notify_asset_deleted",
    ):
        assert trigger_name in trigger_sql
    assert "UPDATE OF body, resolved, visibility, deleted_at" in trigger_sql

    assert "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'n8n_read')" in grant_sql
    assert "GRANT SELECT ON n8n_feedback_events, n8n_share_links TO n8n_read" in grant_sql
    assert "GRANT SELECT ON comments" not in grant_sql
    assert "GRANT SELECT ON assets" not in grant_sql
    assert "GRANT SELECT ON projects" not in grant_sql

    assert "DROP TABLE" not in downgrade_sql
    assert "DELETE FROM" not in downgrade_sql
    assert "TRUNCATE" not in downgrade_sql
    assert "UPDATE " not in downgrade_sql
    assert "INSERT INTO" not in downgrade_sql
    assert migration.LEGACY_N8N_FEEDBACK_EVENTS_VIEW_SQL in migration.DOWNGRADE_SQL
