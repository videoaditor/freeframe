"""Durable order test purpose and monotone physical-version exclusion.
Revision ID: f1d8a10b2026
Revises: e1d8a10b2026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = 'f1d8a10b2026'
down_revision = 'e1d8a10b2026'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('upload_requests', sa.Column('timing_run_purpose', postgresql.JSONB(), nullable=True))
    op.create_check_constraint('ck_timing_run_purpose', 'upload_requests', """timing_run_purpose IS NULL OR (
      jsonb_typeof(timing_run_purpose) = 'object' AND
      timing_run_purpose ? 'quiet' AND timing_run_purpose ? 'provenance' AND
      timing_run_purpose - 'quiet' - 'provenance' = '{}'::jsonb AND
      timing_run_purpose->'quiet' IN ('true'::jsonb, 'false'::jsonb) AND
      (timing_run_purpose->>'provenance' IN ('operator-test', 'synthetic') OR timing_run_purpose->'provenance' = 'null'::jsonb) AND
      (timing_run_purpose->'quiet' = 'true'::jsonb OR timing_run_purpose->>'provenance' IN ('operator-test', 'synthetic'))
    )""")
    op.add_column('asset_versions', sa.Column('timing_exclusion', postgresql.JSONB(), nullable=True))
    # A rollback loses negative evidence. On every installation, older committed
    # versions are explicitly unknown under this authority, never silently re-admitted.
    op.execute("""
        UPDATE asset_versions v SET timing_exclusion = jsonb_build_object(
          'schema_version', 'autoreview.timing-exclusion.v1', 'tenant_id', r.project_id::text,
          'upload_request_id', r.id::text, 'share_token', r.review_share_token,
          'asset_id', v.asset_id::text, 'version_id', v.id::text,
          'version_number', v.version_number, 'submitted_at', u.submitted_at,
          'provenance', 'unknown', 'reason', 'pre-exclusion-authority',
          'excluded_at', clock_timestamp())
        FROM request_uploads u JOIN upload_requests r ON r.id = u.request_id
        WHERE u.asset_id = v.asset_id AND u.version_number = v.version_number
          AND u.submitted_at IS NOT NULL
    """)
    op.execute("""
        CREATE FUNCTION protect_timing_exclusion() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.timing_exclusion IS NOT NULL AND (
            NEW.timing_exclusion IS DISTINCT FROM OLD.timing_exclusion OR
            NEW.id IS DISTINCT FROM OLD.id OR
            NEW.asset_id IS DISTINCT FROM OLD.asset_id OR
            NEW.version_number IS DISTINCT FROM OLD.version_number) THEN
            RAISE EXCEPTION 'Timing exclusion is immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER protect_timing_exclusion BEFORE UPDATE ON asset_versions
        FOR EACH ROW EXECUTE FUNCTION protect_timing_exclusion();
    """)


def downgrade():
    op.execute('DROP TRIGGER protect_timing_exclusion ON asset_versions; DROP FUNCTION protect_timing_exclusion();')
    op.drop_column('asset_versions', 'timing_exclusion')
    op.drop_constraint('ck_timing_run_purpose', 'upload_requests', type_='check')
    op.drop_column('upload_requests', 'timing_run_purpose')
