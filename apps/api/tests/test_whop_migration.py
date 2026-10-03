"""The Whop launch upgrades the current live schema through one additive chain."""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_whop_migrations_follow_live_n8n_head_without_branching():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["91ac7de48b20"]
    assert scripts.get_revision("91ac7de48b20").down_revision == "d0e1f2a3b4c5"
    assert scripts.get_revision("d0e1f2a3b4c5").down_revision == "c9d0e1f2a3b4"
    assert scripts.get_revision("c9d0e1f2a3b4").down_revision == "b7c8d9e0f1a2"
    assert scripts.get_revision("b7c8d9e0f1a2").down_revision == "3b8e1d6c9f20"
