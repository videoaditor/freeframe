"""Pure contract tests for the migration-owned n8n database surface."""

import importlib.util
from pathlib import Path
from unittest.mock import call, patch


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


def _normalized(sql: str) -> str:
    return " ".join(sql.lower().split())


def test_migration_extends_the_exact_live_view_contract_without_reordering_columns():
    migration = _load_migration()

    assert migration.down_revision == "a9ee0209151a"
    assert migration.FEEDBACK_EVENT_COLUMNS == FEEDBACK_COLUMNS
    assert migration.FEEDBACK_EVENT_COLUMNS[: len(LEGACY_FEEDBACK_COLUMNS)] == LEGACY_FEEDBACK_COLUMNS
    assert migration.SHARE_LINK_COLUMNS == SHARE_LINK_COLUMNS
    assert "union all" in _normalized(migration.N8N_FEEDBACK_EVENTS_VIEW_SQL)
    assert "'comment'::text" in migration.N8N_FEEDBACK_EVENTS_VIEW_SQL
    assert "'comment_deleted'::text" in migration.N8N_FEEDBACK_EVENTS_VIEW_SQL
    assert "'approval'::text" in migration.N8N_FEEDBACK_EVENTS_VIEW_SQL
    assert "'version'::text" in migration.N8N_FEEDBACK_EVENTS_VIEW_SQL
    assert "'asset_deleted'::text" in migration.N8N_FEEDBACK_EVENTS_VIEW_SQL


def test_comment_rows_have_stable_ids_and_explicit_create_update_delete_semantics():
    migration = _load_migration()
    sql = _normalized(migration.N8N_FEEDBACK_EVENTS_VIEW_SQL)
    active_branch, tombstone_branch, *_ = sql.split("union all")

    assert "c.id as event_id" in active_branch
    assert "c.id as comment_id" in active_branch
    assert "when c.updated_at > c.created_at then 'updated' else 'created'" in active_branch
    assert "c.updated_at as event_occurred_at" in active_branch
    assert "where c.deleted_at is null" in active_branch

    assert "c.id as event_id" in tombstone_branch
    assert "c.id as comment_id" in tombstone_branch
    assert "'comment_deleted'::text as event_type" in tombstone_branch
    assert "null::text as body" in tombstone_branch
    assert "'tombstone' as visibility" in tombstone_branch
    assert "'deleted'::text as source_event_kind" in tombstone_branch
    assert "c.deleted_at as event_occurred_at" in tombstone_branch
    assert "c.deleted_at as source_deleted_at" in tombstone_branch
    assert "where c.deleted_at is not null" in tombstone_branch


def test_share_link_view_keeps_all_live_scopes_and_excludes_soft_deleted_sources():
    migration = _load_migration()
    sql = _normalized(migration.N8N_SHARE_LINKS_VIEW_SQL)

    assert sql.count("union all") == 2
    for scope in ("asset", "folder", "project"):
        assert f"'{scope}'::text as scope" in sql
    assert sql.count("s.deleted_at is null") == 3
    assert sql.count("a.deleted_at is null") == 3


def test_notifications_preserve_existing_payload_keys_and_cover_changes_and_tombstones():
    migration = _load_migration()
    function_sql = _normalized(migration.NOTIFY_FUNCTION_SQL)
    trigger_sql = _normalized("\n".join(migration.TRIGGER_SQL))

    assert "pg_notify( 'feedback_event'" in function_sql
    assert "'id', new.id" in function_sql
    assert "'type', tg_argv[0]" in function_sql
    assert "'event_kind'" in function_sql
    assert "after insert on comments" in trigger_sql
    assert "after update of body, resolved, visibility, deleted_at on comments" in trigger_sql
    assert "after insert on approvals" in trigger_sql
    assert "after update of status, note on approvals" not in trigger_sql
    assert "old.body is distinct from new.body" in trigger_sql
    assert "after insert on asset_versions" in trigger_sql
    assert "after update of deleted_at on asset_versions" not in trigger_sql
    assert "after update of deleted_at on assets" in trigger_sql


def test_upgrade_is_deterministic_and_grants_only_view_reads_when_role_exists():
    migration = _load_migration()

    with patch.object(migration.op, "execute") as execute:
        migration.upgrade()
        first_calls = list(execute.call_args_list)
        execute.reset_mock()
        migration.upgrade()
        second_calls = list(execute.call_args_list)

    assert first_calls == second_calls
    assert first_calls == [call(statement) for statement in migration.UPGRADE_SQL]

    sql = _normalized("\n".join(migration.UPGRADE_SQL))
    grant_sql = _normalized(migration.CONDITIONAL_GRANTS_SQL)
    assert "from pg_roles where rolname = 'n8n_read'" in grant_sql
    assert "grant select on n8n_feedback_events, n8n_share_links to n8n_read" in grant_sql
    assert "grant" not in sql.replace(grant_sql, "")
    assert "grant select on comments" not in sql
    assert "grant select on assets" not in sql
    assert "grant insert" not in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql


def test_downgrade_restores_the_captured_contract_and_never_touches_source_data():
    migration = _load_migration()

    with patch.object(migration.op, "execute") as execute:
        migration.downgrade()

    assert execute.call_args_list == [call(statement) for statement in migration.DOWNGRADE_SQL]
    sql = _normalized("\n".join(migration.DOWNGRADE_SQL))
    legacy_view_sql = _normalized(migration.LEGACY_N8N_FEEDBACK_EVENTS_VIEW_SQL)
    legacy_notify_sql = _normalized(migration.LEGACY_NOTIFY_FUNCTION_SQL)
    assert "drop view if exists n8n_feedback_events" in sql
    assert "create view n8n_feedback_events as" in legacy_view_sql
    assert "comment_id" not in legacy_view_sql
    assert "'event_kind'" not in legacy_notify_sql
    assert "create trigger trg_notify_comment after insert on comments" in sql
    assert "create trigger trg_notify_approval after insert on approvals" in sql
    for destructive_source_operation in ("drop table", "truncate", "delete from", "alter table"):
        assert destructive_source_operation not in sql
