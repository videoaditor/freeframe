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
    assert migration.FEEDBACK_EVENT_COLUMNS == FEEDBACK_COLUMNS
    assert migration.FEEDBACK_EVENT_COLUMNS[: len(LEGACY_FEEDBACK_COLUMNS)] == LEGACY_FEEDBACK_COLUMNS
    assert migration.SHARE_LINK_COLUMNS == SHARE_LINK_COLUMNS
