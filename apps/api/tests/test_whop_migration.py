"""The Whop launch upgrades the current live schema through one additive chain."""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_whop_migrations_follow_live_n8n_head_without_branching():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["a7b2c3d4e5f6"]
    assert scripts.get_revision("a7b2c3d4e5f6").down_revision == "e4f5a6b7c8d9"
    assert scripts.get_revision("e4f5a6b7c8d9").down_revision == "c3d4e5f6a7b8"
    assert scripts.get_revision("c3d4e5f6a7b8").down_revision == "d0e1f2a3b4c5"
    assert scripts.get_revision("d0e1f2a3b4c5").down_revision == "c9d0e1f2a3b4"
    assert scripts.get_revision("c9d0e1f2a3b4").down_revision == "b7c8d9e0f1a2"
    assert scripts.get_revision("b7c8d9e0f1a2").down_revision == "3b8e1d6c9f20"


def test_campaign_migrations_load_through_production_alembic_entrypoint():
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, '-m', 'alembic', 'upgrade', 'd0e1f2a3b4c5:head', '--sql'],
        cwd=Path(__file__).parents[1], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'CREATE TABLE product_feedback' in result.stdout
    assert 'ALTER TABLE users ADD COLUMN suite_campaign' in result.stdout
    assert 'CREATE TABLE campaign_reviews' in result.stdout
