"""Version and own the FreeFrame-to-n8n feedback event surface.

Revision ID: f4e9c2a1b7d3
Revises: a9ee0209151a
Create Date: 2026-09-10

The first 21 feedback columns and all share-link columns reproduce the live,
previously host-managed contract. New feedback columns are appended so
CREATE OR REPLACE VIEW remains compatible with existing consumers.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f4e9c2a1b7d3"
down_revision: Union[str, Sequence[str], None] = "a9ee0209151a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE_CONTRACT_VERSION = "freeframe-feedback.v1"

# Do not reorder or rename the live prefix. PostgreSQL permits a replacement
# view to append columns, but not to alter its established column contract.
FEEDBACK_EVENT_COLUMNS = (
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

N8N_FEEDBACK_EVENTS_VIEW_SQL = f"""
CREATE OR REPLACE VIEW n8n_feedback_events ({", ".join(FEEDBACK_EVENT_COLUMNS)}) AS
-- A comment ID is stable across edits and soft deletion. The historical
-- created_at column remains the original creation time for existing queries;
-- event_occurred_at is the cursor for consumers that ingest revisions.
SELECT
    c.id AS event_id,
    'comment'::text AS event_type,
    c.created_at AS created_at,
    a.project_id AS project_id,
    p.name AS project_name,
    a.id AS asset_id,
    a.name AS asset_name,
    c.version_id AS version_id,
    av.version_number AS version_number,
    CASE WHEN c.author_id IS NOT NULL THEN 'editor' ELSE 'client' END AS author_kind,
    COALESCE(u.email, g.email) AS author_email,
    COALESCE(u.name, g.name) AS author_name,
    c.body AS body,
    NULL::text AS status,
    c.timecode_start AS timecode_start,
    c.timecode_end AS timecode_end,
    c.resolved AS resolved,
    c.visibility AS visibility,
    c.parent_id AS parent_id,
    COALESCE(asg.email, cre.email) AS owner_email,
    COALESCE(asg.name, cre.name) AS owner_name,
    c.id AS comment_id,
    CASE WHEN c.updated_at > c.created_at THEN 'updated' ELSE 'created' END::text AS source_event_kind,
    c.updated_at AS event_occurred_at,
    c.updated_at AS source_updated_at,
    NULL::timestamp with time zone AS source_deleted_at,
    '{SOURCE_CONTRACT_VERSION}'::text AS source_contract_version
FROM comments c
JOIN assets a ON a.id = c.asset_id
JOIN projects p ON p.id = a.project_id
LEFT JOIN asset_versions av ON av.id = c.version_id
LEFT JOIN users u ON u.id = c.author_id
LEFT JOIN guest_users g ON g.id = c.guest_author_id
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE c.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND p.deleted_at IS NULL

UNION ALL

-- A separate non-public event type keeps every legacy comment query's row set
-- unchanged while giving revision-aware consumers an explicit tombstone.
SELECT
    c.id AS event_id,
    'comment_deleted'::text AS event_type,
    c.deleted_at AS created_at,
    a.project_id AS project_id,
    p.name AS project_name,
    a.id AS asset_id,
    a.name AS asset_name,
    c.version_id AS version_id,
    av.version_number AS version_number,
    CASE WHEN c.author_id IS NOT NULL THEN 'editor' ELSE 'client' END AS author_kind,
    COALESCE(u.email, g.email) AS author_email,
    COALESCE(u.name, g.name) AS author_name,
    NULL::text AS body,
    NULL::text AS status,
    c.timecode_start AS timecode_start,
    c.timecode_end AS timecode_end,
    c.resolved AS resolved,
    'tombstone' AS visibility,
    c.parent_id AS parent_id,
    COALESCE(asg.email, cre.email) AS owner_email,
    COALESCE(asg.name, cre.name) AS owner_name,
    c.id AS comment_id,
    'deleted'::text AS source_event_kind,
    c.deleted_at AS event_occurred_at,
    c.updated_at AS source_updated_at,
    c.deleted_at AS source_deleted_at,
    '{SOURCE_CONTRACT_VERSION}'::text AS source_contract_version
FROM comments c
JOIN assets a ON a.id = c.asset_id
JOIN projects p ON p.id = a.project_id
LEFT JOIN asset_versions av ON av.id = c.version_id
LEFT JOIN users u ON u.id = c.author_id
LEFT JOIN guest_users g ON g.id = c.guest_author_id
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE c.deleted_at IS NOT NULL
  AND a.deleted_at IS NULL
  AND p.deleted_at IS NULL

UNION ALL

SELECT
    ap.id AS event_id,
    'approval'::text AS event_type,
    ap.created_at AS created_at,
    a.project_id AS project_id,
    p.name AS project_name,
    a.id AS asset_id,
    a.name AS asset_name,
    ap.version_id AS version_id,
    av.version_number AS version_number,
    'editor'::text AS author_kind,
    u.email AS author_email,
    u.name AS author_name,
    ap.note AS body,
    ap.status::text AS status,
    NULL::double precision AS timecode_start,
    NULL::double precision AS timecode_end,
    NULL::boolean AS resolved,
    'public' AS visibility,
    NULL::uuid AS parent_id,
    COALESCE(asg.email, cre.email) AS owner_email,
    COALESCE(asg.name, cre.name) AS owner_name,
    NULL::uuid AS comment_id,
    'snapshot'::text AS source_event_kind,
    ap.created_at AS event_occurred_at,
    NULL::timestamp with time zone AS source_updated_at,
    NULL::timestamp with time zone AS source_deleted_at,
    '{SOURCE_CONTRACT_VERSION}'::text AS source_contract_version
FROM approvals ap
JOIN assets a ON a.id = ap.asset_id
JOIN projects p ON p.id = a.project_id
LEFT JOIN asset_versions av ON av.id = ap.version_id
LEFT JOIN users u ON u.id = ap.user_id
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE ap.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND p.deleted_at IS NULL

UNION ALL

SELECT
    av.id AS event_id,
    'version'::text AS event_type,
    av.created_at AS created_at,
    a.project_id AS project_id,
    p.name AS project_name,
    a.id AS asset_id,
    a.name AS asset_name,
    av.id AS version_id,
    av.version_number AS version_number,
    'editor'::text AS author_kind,
    vu.email AS author_email,
    vu.name AS author_name,
    NULL::text AS body,
    NULL::text AS status,
    NULL::double precision AS timecode_start,
    NULL::double precision AS timecode_end,
    NULL::boolean AS resolved,
    'public' AS visibility,
    NULL::uuid AS parent_id,
    COALESCE(asg.email, cre.email) AS owner_email,
    COALESCE(asg.name, cre.name) AS owner_name,
    NULL::uuid AS comment_id,
    'created'::text AS source_event_kind,
    av.created_at AS event_occurred_at,
    NULL::timestamp with time zone AS source_updated_at,
    NULL::timestamp with time zone AS source_deleted_at,
    '{SOURCE_CONTRACT_VERSION}'::text AS source_contract_version
FROM asset_versions av
JOIN assets a ON a.id = av.asset_id
JOIN projects p ON p.id = a.project_id
LEFT JOIN users vu ON vu.id = av.created_by
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE av.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND p.deleted_at IS NULL

UNION ALL

SELECT
    a.id AS event_id,
    'asset_deleted'::text AS event_type,
    a.deleted_at AS created_at,
    a.project_id AS project_id,
    p.name AS project_name,
    a.id AS asset_id,
    a.name AS asset_name,
    NULL::uuid AS version_id,
    NULL::integer AS version_number,
    'editor'::text AS author_kind,
    COALESCE(asg.email, cre.email) AS author_email,
    COALESCE(asg.name, cre.name) AS author_name,
    NULL::text AS body,
    NULL::text AS status,
    NULL::double precision AS timecode_start,
    NULL::double precision AS timecode_end,
    NULL::boolean AS resolved,
    'public' AS visibility,
    NULL::uuid AS parent_id,
    COALESCE(asg.email, cre.email) AS owner_email,
    COALESCE(asg.name, cre.name) AS owner_name,
    NULL::uuid AS comment_id,
    'deleted'::text AS source_event_kind,
    a.deleted_at AS event_occurred_at,
    a.updated_at AS source_updated_at,
    a.deleted_at AS source_deleted_at,
    '{SOURCE_CONTRACT_VERSION}'::text AS source_contract_version
FROM assets a
JOIN projects p ON p.id = a.project_id
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE a.deleted_at IS NOT NULL
  AND p.deleted_at IS NULL
"""

N8N_SHARE_LINKS_VIEW_SQL = f"""
CREATE OR REPLACE VIEW n8n_share_links ({", ".join(SHARE_LINK_COLUMNS)}) AS
SELECT
    s.token AS token,
    a.id AS asset_id,
    a.project_id AS project_id,
    s.created_by AS created_by,
    s.created_at AS created_at,
    s.is_enabled AS is_enabled,
    s.permission::text AS permission,
    'asset'::text AS scope
FROM share_links s
JOIN assets a ON a.id = s.asset_id
WHERE s.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND s.asset_id IS NOT NULL

UNION ALL

SELECT
    s.token AS token,
    a.id AS asset_id,
    a.project_id AS project_id,
    s.created_by AS created_by,
    s.created_at AS created_at,
    s.is_enabled AS is_enabled,
    s.permission::text AS permission,
    'folder'::text AS scope
FROM share_links s
JOIN assets a ON a.folder_id = s.folder_id
WHERE s.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND s.folder_id IS NOT NULL

UNION ALL

SELECT
    s.token AS token,
    a.id AS asset_id,
    a.project_id AS project_id,
    s.created_by AS created_by,
    s.created_at AS created_at,
    s.is_enabled AS is_enabled,
    s.permission::text AS permission,
    'project'::text AS scope
FROM share_links s
JOIN assets a ON a.project_id = s.project_id
WHERE s.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND s.project_id IS NOT NULL
"""

LEGACY_N8N_FEEDBACK_EVENTS_VIEW_SQL = """
CREATE VIEW n8n_feedback_events AS
SELECT
    c.id AS event_id,
    'comment'::text AS event_type,
    c.created_at AS created_at,
    a.project_id AS project_id,
    p.name AS project_name,
    a.id AS asset_id,
    a.name AS asset_name,
    c.version_id AS version_id,
    av.version_number AS version_number,
    CASE WHEN c.author_id IS NOT NULL THEN 'editor' ELSE 'client' END AS author_kind,
    COALESCE(u.email, g.email) AS author_email,
    COALESCE(u.name, g.name) AS author_name,
    c.body AS body,
    NULL::text AS status,
    c.timecode_start AS timecode_start,
    c.timecode_end AS timecode_end,
    c.resolved AS resolved,
    c.visibility AS visibility,
    c.parent_id AS parent_id,
    COALESCE(asg.email, cre.email) AS owner_email,
    COALESCE(asg.name, cre.name) AS owner_name
FROM comments c
JOIN assets a ON a.id = c.asset_id
JOIN projects p ON p.id = a.project_id
LEFT JOIN asset_versions av ON av.id = c.version_id
LEFT JOIN users u ON u.id = c.author_id
LEFT JOIN guest_users g ON g.id = c.guest_author_id
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE c.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND p.deleted_at IS NULL

UNION ALL

SELECT
    ap.id, 'approval', ap.created_at,
    a.project_id, p.name, a.id, a.name,
    ap.version_id, av.version_number,
    'editor', u.email, u.name,
    ap.note, ap.status::text,
    NULL::double precision, NULL::double precision, NULL::boolean, 'public', NULL::uuid,
    COALESCE(asg.email, cre.email),
    COALESCE(asg.name, cre.name)
FROM approvals ap
JOIN assets a ON a.id = ap.asset_id
JOIN projects p ON p.id = a.project_id
LEFT JOIN asset_versions av ON av.id = ap.version_id
LEFT JOIN users u ON u.id = ap.user_id
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE ap.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND p.deleted_at IS NULL

UNION ALL

SELECT
    av.id, 'version', av.created_at,
    a.project_id, p.name, a.id, a.name,
    av.id, av.version_number,
    'editor', vu.email, vu.name,
    NULL::text, NULL::text,
    NULL::double precision, NULL::double precision, NULL::boolean, 'public', NULL::uuid,
    COALESCE(asg.email, cre.email),
    COALESCE(asg.name, cre.name)
FROM asset_versions av
JOIN assets a ON a.id = av.asset_id
JOIN projects p ON p.id = a.project_id
LEFT JOIN users vu ON vu.id = av.created_by
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE av.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND p.deleted_at IS NULL

UNION ALL

SELECT
    a.id, 'asset_deleted', a.deleted_at,
    a.project_id, p.name, a.id, a.name,
    NULL::uuid, NULL::integer,
    'editor', COALESCE(asg.email, cre.email), COALESCE(asg.name, cre.name),
    NULL::text, NULL::text,
    NULL::double precision, NULL::double precision, NULL::boolean, 'public', NULL::uuid,
    COALESCE(asg.email, cre.email),
    COALESCE(asg.name, cre.name)
FROM assets a
JOIN projects p ON p.id = a.project_id
LEFT JOIN users asg ON asg.id = a.assignee_id
LEFT JOIN users cre ON cre.id = a.created_by
WHERE a.deleted_at IS NOT NULL
  AND p.deleted_at IS NULL
"""

NOTIFY_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION notify_feedback_event() RETURNS trigger AS $$
DECLARE
    event_kind text;
BEGIN
    event_kind := CASE
        WHEN TG_OP = 'INSERT' THEN 'created'
        WHEN NEW.deleted_at IS NOT NULL
             AND (OLD.deleted_at IS NULL OR OLD.deleted_at IS DISTINCT FROM NEW.deleted_at)
            THEN 'deleted'
        ELSE 'updated'
    END;

    -- Keep the established id/type keys and append metadata only. Never place
    -- comment text, share tokens, or user details in the notification payload.
    PERFORM pg_notify(
        'feedback_event',
        json_build_object(
            'id', NEW.id,
            'type', CASE
                WHEN TG_ARGV[0] = 'comment' AND event_kind = 'deleted'
                    THEN 'comment_deleted'
                ELSE TG_ARGV[0]
            END,
            'event_kind', event_kind
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

REVOKE_NOTIFY_EXECUTE_SQL = "REVOKE EXECUTE ON FUNCTION notify_feedback_event() FROM PUBLIC"

TRIGGER_SQL = (
    """DROP TRIGGER IF EXISTS trg_notify_comment ON comments;
CREATE TRIGGER trg_notify_comment AFTER INSERT ON comments
    FOR EACH ROW EXECUTE FUNCTION notify_feedback_event('comment')""",
    """DROP TRIGGER IF EXISTS trg_notify_comment_changed ON comments;
CREATE TRIGGER trg_notify_comment_changed
    AFTER UPDATE OF body, resolved, visibility, deleted_at ON comments
    FOR EACH ROW
    WHEN (OLD.body IS DISTINCT FROM NEW.body
       OR OLD.resolved IS DISTINCT FROM NEW.resolved
       OR OLD.visibility IS DISTINCT FROM NEW.visibility
       OR OLD.deleted_at IS DISTINCT FROM NEW.deleted_at)
    EXECUTE FUNCTION notify_feedback_event('comment')""",
    """DROP TRIGGER IF EXISTS trg_notify_approval ON approvals;
CREATE TRIGGER trg_notify_approval AFTER INSERT ON approvals
    FOR EACH ROW EXECUTE FUNCTION notify_feedback_event('approval')""",
    """DROP TRIGGER IF EXISTS trg_notify_version ON asset_versions;
CREATE TRIGGER trg_notify_version AFTER INSERT ON asset_versions
    FOR EACH ROW EXECUTE FUNCTION notify_feedback_event('version')""",
    """DROP TRIGGER IF EXISTS trg_notify_asset_deleted ON assets;
CREATE TRIGGER trg_notify_asset_deleted
    AFTER UPDATE OF deleted_at ON assets
    FOR EACH ROW
    WHEN (OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL)
    EXECUTE FUNCTION notify_feedback_event('asset_deleted')""",
)

CONDITIONAL_GRANTS_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'n8n_read') THEN
        EXECUTE 'GRANT SELECT ON n8n_feedback_events, n8n_share_links TO n8n_read';
    END IF;
END
$$
"""

UPGRADE_SQL = (
    N8N_FEEDBACK_EVENTS_VIEW_SQL,
    N8N_SHARE_LINKS_VIEW_SQL,
    NOTIFY_FUNCTION_SQL,
    REVOKE_NOTIFY_EXECUTE_SQL,
    *TRIGGER_SQL,
    CONDITIONAL_GRANTS_SQL,
)

LEGACY_NOTIFY_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION notify_feedback_event() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify(
        'feedback_event',
        json_build_object('id', NEW.id, 'type', TG_ARGV[0])::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

LEGACY_TRIGGER_SQL = (
    """CREATE TRIGGER trg_notify_comment AFTER INSERT ON comments
    FOR EACH ROW EXECUTE FUNCTION notify_feedback_event('comment')""",
    """CREATE TRIGGER trg_notify_approval AFTER INSERT ON approvals
    FOR EACH ROW EXECUTE FUNCTION notify_feedback_event('approval')""",
)

# This migration adopts objects that already exist on deployed installations.
# Downgrade therefore restores that captured contract instead of removing it.
DOWNGRADE_SQL = (
    "DROP TRIGGER IF EXISTS trg_notify_asset_deleted ON assets",
    "DROP TRIGGER IF EXISTS trg_notify_version ON asset_versions",
    "DROP TRIGGER IF EXISTS trg_notify_approval_changed ON approvals",
    "DROP TRIGGER IF EXISTS trg_notify_approval ON approvals",
    "DROP TRIGGER IF EXISTS trg_notify_comment_changed ON comments",
    "DROP TRIGGER IF EXISTS trg_notify_comment ON comments",
    "DROP VIEW IF EXISTS n8n_feedback_events",
    LEGACY_N8N_FEEDBACK_EVENTS_VIEW_SQL,
    N8N_SHARE_LINKS_VIEW_SQL,
    LEGACY_NOTIFY_FUNCTION_SQL,
    *LEGACY_TRIGGER_SQL,
    CONDITIONAL_GRANTS_SQL,
)


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    # Restore the captured host-managed contract. No application table or
    # source row is changed or removed.
    for statement in DOWNGRADE_SQL:
        op.execute(statement)
