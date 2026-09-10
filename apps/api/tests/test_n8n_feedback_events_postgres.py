"""Production-shape PostgreSQL checks for the n8n integration migration.

Every source row is synthetic and runs inside the ``real_db`` rollback boundary.
"""

import importlib.util
from pathlib import Path

from sqlalchemy import text


VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
MIGRATION_PATH = next(VERSIONS_DIR.glob("*_version_n8n_feedback_events.py"))


def _load_migration():
    spec = importlib.util.spec_from_file_location("n8n_feedback_postgres_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_postgres_exposes_the_versioned_column_and_trigger_contract(real_db):
    migration = _load_migration()

    feedback_columns = real_db.execute(
        text(
            """
            SELECT attname
            FROM pg_attribute
            WHERE attrelid = 'n8n_feedback_events'::regclass
              AND attnum > 0
              AND NOT attisdropped
            ORDER BY attnum
            """
        )
    ).scalars().all()
    share_columns = real_db.execute(
        text(
            """
            SELECT attname
            FROM pg_attribute
            WHERE attrelid = 'n8n_share_links'::regclass
              AND attnum > 0
              AND NOT attisdropped
            ORDER BY attnum
            """
        )
    ).scalars().all()

    assert tuple(feedback_columns) == migration.FEEDBACK_EVENT_COLUMNS
    assert tuple(share_columns) == migration.SHARE_LINK_COLUMNS

    triggers = dict(
        real_db.execute(
            text(
                """
                SELECT tgname, pg_get_triggerdef(oid)
                FROM pg_trigger
                WHERE NOT tgisinternal
                  AND tgname LIKE 'trg_notify_%'
                """
            )
        ).all()
    )
    assert set(triggers) == {
        "trg_notify_comment",
        "trg_notify_comment_changed",
        "trg_notify_approval",
        "trg_notify_version",
        "trg_notify_asset_deleted",
    }
    assert "UPDATE OF body, resolved, visibility, deleted_at" in triggers["trg_notify_comment_changed"]


def test_postgres_adopts_and_restores_the_legacy_contract_idempotently(real_db):
    migration = _load_migration()
    synthetic_user_id = "20000000-0000-0000-0000-000000000001"
    real_db.execute(
        text(
            """
            INSERT INTO users (id, email, name, status, email_verified, is_superadmin)
            VALUES (:id, 'migration-check@example.invalid', 'Migration Check', 'active', false, false)
            """
        ),
        {"id": synthetic_user_id},
    )

    for statement in migration.DOWNGRADE_SQL:
        real_db.execute(text(statement))

    legacy_columns = real_db.execute(
        text(
            """
            SELECT attname
            FROM pg_attribute
            WHERE attrelid = 'n8n_feedback_events'::regclass
              AND attnum > 0
              AND NOT attisdropped
            ORDER BY attnum
            """
        )
    ).scalars().all()
    legacy_triggers = real_db.execute(
        text(
            """
            SELECT tgname
            FROM pg_trigger
            WHERE NOT tgisinternal AND tgname LIKE 'trg_notify_%'
            ORDER BY tgname
            """
        )
    ).scalars().all()
    assert tuple(legacy_columns) == migration.FEEDBACK_EVENT_COLUMNS[:21]
    assert legacy_triggers == ["trg_notify_approval", "trg_notify_comment"]

    for _ in range(2):
        for statement in migration.UPGRADE_SQL:
            real_db.execute(text(statement))

    adopted_columns = real_db.execute(
        text(
            """
            SELECT attname
            FROM pg_attribute
            WHERE attrelid = 'n8n_feedback_events'::regclass
              AND attnum > 0
              AND NOT attisdropped
            ORDER BY attnum
            """
        )
    ).scalars().all()
    assert tuple(adopted_columns) == migration.FEEDBACK_EVENT_COLUMNS

    for statement in migration.DOWNGRADE_SQL:
        real_db.execute(text(statement))
    assert real_db.execute(
        text("SELECT count(*) FROM users WHERE id = :id"),
        {"id": synthetic_user_id},
    ).scalar_one() == 1


def test_postgres_comment_revision_and_tombstone_rows_are_fetchable(real_db):
    ids = {
        "user": "10000000-0000-0000-0000-000000000001",
        "guest": "10000000-0000-0000-0000-000000000002",
        "project": "10000000-0000-0000-0000-000000000003",
        "asset": "10000000-0000-0000-0000-000000000004",
        "version": "10000000-0000-0000-0000-000000000005",
        "comment": "10000000-0000-0000-0000-000000000006",
    }
    real_db.execute(
        text(
            """
            INSERT INTO users (id, email, name, status, email_verified, is_superadmin)
            VALUES (:user, 'owner@example.invalid', 'Synthetic Owner', 'active', false, false);
            INSERT INTO guest_users (id, email, name)
            VALUES (:guest, 'reviewer@example.invalid', 'Synthetic Reviewer');
            INSERT INTO projects (id, name, project_type, created_by, is_public)
            VALUES (:project, 'Synthetic Project', 'personal', :user, false);
            INSERT INTO assets (id, project_id, name, asset_type, status, created_by)
            VALUES (:asset, :project, 'Synthetic Asset', 'video', 'in_review', :user);
            INSERT INTO asset_versions (
                id, asset_id, version_number, processing_status, created_by
            ) VALUES (:version, :asset, 1, 'ready', :user);
            INSERT INTO comments (
                id, asset_id, version_id, guest_author_id, body, resolved,
                visibility, created_at, updated_at
            ) VALUES (
                :comment, :asset, :version, :guest, 'Synthetic feedback', false,
                'public', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
            )
            """
        ),
        ids,
    )

    created = real_db.execute(
        text(
            """
            SELECT event_id, event_type, comment_id, source_event_kind, body
            FROM n8n_feedback_events
            WHERE comment_id = :comment
            """
        ),
        ids,
    ).one()
    assert str(created.event_id) == ids["comment"]
    assert str(created.comment_id) == ids["comment"]
    assert created.event_type == "comment"
    assert created.source_event_kind == "created"
    assert created.body == "Synthetic feedback"

    real_db.execute(
        text(
            """
            UPDATE comments
            SET body = 'Synthetic revision', updated_at = '2026-01-01T00:01:00Z'
            WHERE id = :comment
            """
        ),
        ids,
    )
    updated = real_db.execute(
        text(
            """
            SELECT event_type, source_event_kind, event_occurred_at, body
            FROM n8n_feedback_events
            WHERE comment_id = :comment
            """
        ),
        ids,
    ).one()
    assert updated.event_type == "comment"
    assert updated.source_event_kind == "updated"
    assert updated.event_occurred_at.isoformat() == "2026-01-01T00:01:00+00:00"
    assert updated.body == "Synthetic revision"

    real_db.execute(
        text(
            """
            UPDATE comments
            SET deleted_at = '2026-01-01T00:02:00Z'
            WHERE id = :comment
            """
        ),
        ids,
    )
    tombstone = real_db.execute(
        text(
            """
            SELECT event_id, event_type, comment_id, source_event_kind,
                   event_occurred_at, source_deleted_at, visibility, body
            FROM n8n_feedback_events
            WHERE comment_id = :comment
            """
        ),
        ids,
    ).one()
    assert str(tombstone.event_id) == ids["comment"]
    assert str(tombstone.comment_id) == ids["comment"]
    assert tombstone.event_type == "comment_deleted"
    assert tombstone.source_event_kind == "deleted"
    assert tombstone.event_occurred_at == tombstone.source_deleted_at
    assert tombstone.visibility == "tombstone"
    assert tombstone.body is None


def test_postgres_conditionally_grants_only_view_select(real_db):
    migration = _load_migration()
    role_exists = real_db.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'n8n_read')")
    ).scalar_one()
    if not role_exists:
        real_db.execute(text("CREATE ROLE n8n_read NOLOGIN"))

    real_db.execute(text(migration.CONDITIONAL_GRANTS_SQL))
    privileges = real_db.execute(
        text(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee = 'n8n_read'
              AND table_schema = 'public'
            ORDER BY table_name, privilege_type
            """
        )
    ).all()

    assert privileges == [
        ("n8n_feedback_events", "SELECT"),
        ("n8n_share_links", "SELECT"),
    ]
