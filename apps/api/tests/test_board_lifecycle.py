"""The self-managing board: lanes, Done rules, agent silence. Pure functions, no database."""
from datetime import datetime, timedelta, timezone

from apps.api.services.board_lifecycle import gen_card_key, lane_of, lifecycle

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def life(**over):
    base = dict(last_activity=NOW - timedelta(hours=1), last_agent_activity=NOW - timedelta(hours=1), approved=False,
                delivered=False, stage="editor", is_agent=True)
    return lifecycle(NOW, **{**base, **over})


def test_lanes_follow_the_board():
    assert lane_of("live", 0, "reviewing", None) == "editor"
    assert lane_of("live", 1, "reviewing", None) == "review"
    assert lane_of("live", 1, "held", None) == "corrections"
    assert lane_of("live", 1, "clear", None) == "ready"
    assert lane_of("live", 1, "clear", "self_review") == "review"
    assert lane_of("live", 1, "held", "agent_stuck") == "corrections"
    assert lane_of("revoked", 1, "clear", None) == "closed"


def test_approved_and_delivered_are_done_at_once():
    assert life(approved=True)["done_reason"] == "approved"
    assert life(delivered=True, approved=True)["done_reason"] == "delivered"


def test_stale_after_14_days_and_reopens_on_new_activity():
    old = NOW - timedelta(days=14, minutes=1)
    assert life(last_activity=old, last_agent_activity=old)["done_reason"] == "stale"
    assert life(last_activity=NOW - timedelta(days=13, hours=23))["done_reason"] is None
    # a new upload/comment moves last_activity: nothing is stored, so the card is back
    assert life(last_activity=NOW - timedelta(minutes=5))["done_reason"] is None


def test_silent_agent_after_24h_in_agent_lanes_only():
    quiet = NOW - timedelta(hours=25)
    for stage in ("editor", "corrections"):
        r = life(stage=stage, last_agent_activity=quiet)
        assert r["stale_agent"] is True and r["agent_silent_since"] == quiet.isoformat()
    assert life(stage="editor", last_agent_activity=NOW - timedelta(hours=23))["stale_agent"] is False
    assert life(stage="ready", last_agent_activity=quiet)["stale_agent"] is False
    assert life(stage="review", last_agent_activity=quiet)["stale_agent"] is False


def test_humans_and_done_cards_are_never_flagged_silent():
    quiet = NOW - timedelta(hours=30)
    assert life(is_agent=False, last_agent_activity=quiet)["stale_agent"] is False
    assert life(approved=True, last_agent_activity=quiet)["stale_agent"] is False


def test_agent_activity_clears_the_flag():
    assert life(last_agent_activity=NOW - timedelta(minutes=1))["stale_agent"] is False


def test_gen_card_key_from_external_ref():
    assert gen_card_key("gen:card_abc-12") == "card_abc-12"
    assert gen_card_key("gen:") is None and gen_card_key("ref-9") is None and gen_card_key(None) is None
    assert gen_card_key("gen:bad key") is None
