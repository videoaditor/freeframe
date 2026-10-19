"""Link the existing client workspaces to their AutoReview brand (Alan, 2026-10-19).

Exact workspace names only, never fuzzy, and only where no slug is set yet - a slug set
by hand always wins. Without it the Brand Loop and the comment export see no brand.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1a2b3c4e5f6'
down_revision = 'c9e1a2b3d4f5'
branch_labels = None
depends_on = None

LINKS = {
    "Glow25 - Workspace": "glow25-dailyrituals",
    "Audibene - Workspace": "audibene-gmbh",
    "Forward Health - Workspace": "forward-health-gmbh",
    "Freiheit Media - Workspace": "freiheit-media",
    "mammaly - Workspace": "mammaly-peturo-gmbh",
    "Keller Gesundheit - Workspace": "keller-gesundheitspflege-gmbh",
    "AgelessRX - Workspace": "agelessrx",
    "Liebscher & Bracht Schmerzfrei GmbH - Workspace": "liebscher-bracht",
    "MYND - Workspace": "mynd-organics",
    "Buchmann - Workspace": "buchmann",
    "Futter Vergleich - Workspace": "futter-vergleich",
    "Vital Growth - Workspace": "vital-growth-ug",
}


def upgrade():
    # op.execute (not get_bind) so `alembic upgrade --sql` renders it too.
    for name, slug in LINKS.items():
        op.execute(sa.text("UPDATE projects SET autoreview_brand_slug = :slug "
                           "WHERE name = :name AND is_workspace AND autoreview_brand_slug IS NULL")
                   .bindparams(name=name, slug=slug))


def downgrade():
    # ponytail: no-op - a rollback must not wipe a slug someone set by hand since.
    pass
