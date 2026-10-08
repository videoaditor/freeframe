"""Freeze private timing provenance at confirmed version submission; no backfill.

Revision ID: e1d8a10b2026
Revises: d5d7e10b2026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e1d8a10b2026'
down_revision = 'd5d7e10b2026'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('upload_requests', sa.Column('timing_natural_intent', postgresql.JSONB(), nullable=True))
    op.add_column('request_uploads', sa.Column('timing_provenance', postgresql.JSONB(), nullable=True))
    # NULL on a committed legacy row is itself immutable unknown evidence.
    op.execute("""
        CREATE FUNCTION protect_submission_timing() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.submitted_at IS NOT NULL AND (
            NEW.submitted_at IS DISTINCT FROM OLD.submitted_at OR
            NEW.timing_provenance IS DISTINCT FROM OLD.timing_provenance OR
            NEW.request_id IS DISTINCT FROM OLD.request_id OR
            NEW.asset_id IS DISTINCT FROM OLD.asset_id OR
            NEW.version_number IS DISTINCT FROM OLD.version_number) THEN
            RAISE EXCEPTION 'Committed submission timing is immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER protect_submission_timing BEFORE UPDATE ON request_uploads
        FOR EACH ROW EXECUTE FUNCTION protect_submission_timing();
        CREATE FUNCTION protect_timing_intent() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.timing_natural_intent IS NOT NULL AND
             NEW.timing_natural_intent IS DISTINCT FROM OLD.timing_natural_intent THEN
            RAISE EXCEPTION 'Timing intent is immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER protect_timing_intent BEFORE UPDATE ON upload_requests
        FOR EACH ROW EXECUTE FUNCTION protect_timing_intent();
    """)


def downgrade():
    op.execute('DROP TRIGGER protect_submission_timing ON request_uploads; DROP FUNCTION protect_submission_timing(); DROP TRIGGER protect_timing_intent ON upload_requests; DROP FUNCTION protect_timing_intent();')
    op.drop_column('request_uploads', 'timing_provenance')
    op.drop_column('upload_requests', 'timing_natural_intent')
