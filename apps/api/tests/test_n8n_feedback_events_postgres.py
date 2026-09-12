"""Production-shape PostgreSQL checks for the n8n integration migration.

Every source row is synthetic and is rolled back or explicitly cleaned up.
"""

import importlib.util
import json
import os
import select
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from apps.api.database import engine


# These tests execute DDL and synthetic writes. They are never allowed to run
# merely because an arbitrary DATABASE_URL happens to be reachable.
pytestmark = pytest.mark.skipif(
    os.environ.get("FREEFRAME_RUN_N8N_POSTGRES_TESTS") != "1",
    reason="explicit n8n Postgres integration-test opt-in is required",
)


VERSIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
MIGRATION_PATH = next(VERSIONS_DIR.glob("*_version_n8n_feedback_events.py"))


@pytest.fixture(autouse=True)
def _require_dedicated_test_database():
    """Fail closed unless the caller names the database as a test database."""
    expected = os.environ.get("FREEFRAME_N8N_TEST_DATABASE")
    if not expected:
        pytest.skip("FREEFRAME_N8N_TEST_DATABASE is required for DDL tests")

    with engine.connect() as connection:
        actual = connection.execute(text("SELECT current_database()")).scalar_one()
    if actual != expected:
        pytest.skip(f"connected database is {actual!r}, not the named test database")


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
                SELECT t.tgname, pg_get_triggerdef(t.oid)
                FROM pg_trigger AS t
                JOIN pg_class AS c ON c.oid = t.tgrelid
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE NOT t.tgisinternal
                  AND t.tgname LIKE 'trg_notify_%'
                  AND n.nspname = 'public'
                  AND c.relname IN ('comments', 'approvals', 'asset_versions', 'assets')
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
    synthetic_user_id = str(uuid.uuid4())
    real_db.execute(
        text(
            """
            INSERT INTO users (id, email, name, status, email_verified, is_superadmin)
            VALUES (:id, :email, 'Migration Check', 'active', false, false)
            """
        ),
        {
            "id": synthetic_user_id,
            "email": f"migration-{synthetic_user_id}@example.invalid",
        },
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
            SELECT t.tgname
            FROM pg_trigger AS t
            JOIN pg_class AS c ON c.oid = t.tgrelid
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE NOT t.tgisinternal
              AND t.tgname LIKE 'trg_notify_%'
              AND n.nspname = 'public'
              AND c.relname IN ('comments', 'approvals', 'asset_versions', 'assets')
            ORDER BY t.tgname
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

    # Parent soft-deletes must not erase the already-observed comment
    # tombstone before a rolling poll can fetch it.
    real_db.execute(
        text("UPDATE assets SET deleted_at = '2026-01-01T00:03:00Z' WHERE id = :asset"),
        ids,
    )
    real_db.execute(
        text("UPDATE projects SET deleted_at = '2026-01-01T00:04:00Z' WHERE id = :project"),
        ids,
    )
    after_parent_delete = real_db.execute(
        text(
            """
            SELECT event_type, source_event_kind, source_deleted_at, visibility
            FROM n8n_feedback_events
            WHERE comment_id = :comment
            """
        ),
        ids,
    ).one()
    assert after_parent_delete.event_type == "comment_deleted"
    assert after_parent_delete.source_event_kind == "deleted"
    assert after_parent_delete.source_deleted_at.isoformat() == "2026-01-01T00:02:00+00:00"
    assert after_parent_delete.visibility == "tombstone"


def _next_notification(connection, timeout=1.0):
    connection.poll()
    if not connection.notifies:
        select.select([connection], [], [], timeout)
        connection.poll()
    if not connection.notifies:
        return None
    return connection.notifies.pop(0)


def test_postgres_notifies_fetchable_comment_events_without_no_op_noise():
    ids = {name: str(uuid.uuid4()) for name in ("user", "guest", "project", "asset", "version", "comment")}
    listener = engine.raw_connection()
    listener.autocommit = True
    listener.cursor().execute("LISTEN feedback_event")

    try:
        with engine.begin() as writer:
            writer.execute(
                text(
                    """
                    INSERT INTO users (id, email, name, status, email_verified, is_superadmin)
                    VALUES (:user, :email, 'Notification Owner', 'active', false, false);
                    INSERT INTO guest_users (id, email, name)
                    VALUES (:guest, :guest_email, 'Notification Reviewer');
                    INSERT INTO projects (id, name, project_type, created_by, is_public)
                    VALUES (:project, 'Notification Project', 'personal', :user, false);
                    INSERT INTO assets (id, project_id, name, asset_type, status, created_by)
                    VALUES (:asset, :project, 'Notification Asset', 'video', 'in_review', :user);
                    INSERT INTO asset_versions (
                        id, asset_id, version_number, processing_status, created_by
                    ) VALUES (:version, :asset, 1, 'ready', :user);
                    INSERT INTO comments (
                        id, asset_id, version_id, guest_author_id, body, resolved, visibility
                    ) VALUES (
                        :comment, :asset, :version, :guest, 'Initial feedback', false, 'public'
                    )
                    """
                ),
                {
                    **ids,
                    "email": f"notification-{ids['user']}@example.invalid",
                    "guest_email": f"notification-{ids['guest']}@example.invalid",
                },
            )

        initial_notifications = [
            json.loads(_next_notification(listener).payload),
            json.loads(_next_notification(listener).payload),
        ]
        created = next(payload for payload in initial_notifications if payload["id"] == ids["comment"])
        assert created == {"id": ids["comment"], "type": "comment", "event_kind": "created"}

        with engine.begin() as writer:
            writer.execute(
                text("UPDATE comments SET body = body WHERE id = :comment"),
                ids,
            )
        assert _next_notification(listener, timeout=0.2) is None

        with engine.begin() as writer:
            writer.execute(
                text(
                    "UPDATE comments SET body = 'Revised feedback', updated_at = now() "
                    "WHERE id = :comment"
                ),
                ids,
            )
        updated = json.loads(_next_notification(listener).payload)
        assert updated == {"id": ids["comment"], "type": "comment", "event_kind": "updated"}

        with engine.begin() as writer:
            writer.execute(
                text("UPDATE comments SET deleted_at = now() WHERE id = :comment"),
                ids,
            )
            tombstone = writer.execute(
                text(
                    """
                    SELECT event_type, source_event_kind
                    FROM n8n_feedback_events
                    WHERE event_id = :comment
                    """
                ),
                ids,
            ).one()
        deleted = json.loads(_next_notification(listener).payload)
        assert deleted == {
            "id": ids["comment"],
            "type": tombstone.event_type,
            "event_kind": tombstone.source_event_kind,
        }
        assert deleted["type"] == "comment_deleted"
    finally:
        listener.cursor().execute("UNLISTEN *")
        listener.close()
        with engine.begin() as writer:
            writer.execute(text("DELETE FROM comments WHERE id = :comment"), ids)
            writer.execute(text("DELETE FROM asset_versions WHERE id = :version"), ids)
            writer.execute(text("DELETE FROM assets WHERE id = :asset"), ids)
            writer.execute(text("DELETE FROM projects WHERE id = :project"), ids)
            writer.execute(text("DELETE FROM guest_users WHERE id = :guest"), ids)
            writer.execute(text("DELETE FROM users WHERE id = :user"), ids)


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
              AND table_name IN ('n8n_feedback_events', 'n8n_share_links')
            ORDER BY table_name, privilege_type
            """
        )
    ).all()

    assert privileges == [
        ("n8n_feedback_events", "SELECT"),
        ("n8n_share_links", "SELECT"),
    ]
    for table_name in ('comments', 'assets', 'projects', 'share_links'):
        assert not real_db.execute(
            text("SELECT has_table_privilege('n8n_read', :table_name, 'SELECT')"),
            {"table_name": f"public.{table_name}"},
        ).scalar_one()
