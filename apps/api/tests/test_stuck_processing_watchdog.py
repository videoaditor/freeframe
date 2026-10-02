"""The watchdog for versions stuck in `processing`: pure logic, no database needed.

Seen live on 2026-10-02: an editor's V2 sat in "Processing" for about 4 hours. A worker killed
mid-encode loses its job, and a dispatch that never reaches the broker is only logged; nothing
ever moved such a version out of `processing`. The watchdog asks the queue and the workers
whether a job still exists, and fails the version if not - without ever touching a slow one.
"""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import apps.api.tasks.cleanup_tasks as ct
from apps.api.config import settings
from apps.api.models.asset import ProcessingStatus

ASSET = "11111111-1111-1111-1111-111111111111"
VERSION = "22222222-2222-2222-2222-222222222222"


class FakeStrikes:
    def __init__(self): self.flags = set()
    def flagged(self, v): return v in self.flags
    def flag(self, v): self.flags.add(v)
    def clear(self, v): self.flags.discard(v)


def _version(minutes_old, vid=VERSION):
    return SimpleNamespace(
        id=vid, asset_id=ASSET, processing_status=ProcessingStatus.processing,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_old),
    )


def _db_returning(*versions):
    db = MagicMock()
    db.query.return_value.join.return_value.filter.return_value.all.return_value = [(v, "proj-1") for v in versions]
    return db


# --- the decision ----------------------------------------------------------------------------

def test_past_the_absolute_limit_it_is_failed_whatever_else_is_known():
    v = _version(settings.stuck_processing_timeout_minutes + 30)
    failed = ct._fail_stuck_processing(_db_returning(v), known_ids={VERSION}, strikes=FakeStrikes())
    assert v.processing_status == ProcessingStatus.failed
    assert failed == [("proj-1", ASSET, VERSION, f"no result after {settings.stuck_processing_timeout_minutes} minutes")]


def test_absolute_limit_applies_even_when_the_broker_cannot_be_asked():
    v = _version(settings.stuck_processing_timeout_minutes + 1)
    ct._fail_stuck_processing(_db_returning(v), known_ids=None, strikes=None)
    assert v.processing_status == ProcessingStatus.failed


def test_a_job_the_queue_or_a_worker_still_has_is_left_alone():
    v, strikes = _version(30), FakeStrikes()
    strikes.flag(VERSION)  # an earlier suspicion is dropped once the job turns up
    assert ct._fail_stuck_processing(_db_returning(v), known_ids={VERSION}, strikes=strikes) == []
    assert v.processing_status == ProcessingStatus.processing
    assert not strikes.flagged(VERSION)


def test_a_lost_job_is_failed_on_the_second_sighting_not_the_first():
    """The first sighting proves nothing: an upload that just finished is `processing` for a
    moment before its job reaches the queue."""
    v, strikes = _version(30), FakeStrikes()
    assert ct._fail_stuck_processing(_db_returning(v), known_ids=set(), strikes=strikes) == []
    assert v.processing_status == ProcessingStatus.processing and strikes.flagged(VERSION)

    failed = ct._fail_stuck_processing(_db_returning(v), known_ids=set(), strikes=strikes)
    assert v.processing_status == ProcessingStatus.failed
    assert failed[0][3] == "no worker or queue has this job any more"


def test_when_nobody_can_say_it_waits_for_the_absolute_limit():
    v = _version(30)
    assert ct._fail_stuck_processing(_db_returning(v), known_ids=None, strikes=FakeStrikes()) == []
    assert v.processing_status == ProcessingStatus.processing


def test_disabled_when_timeout_is_zero(monkeypatch):
    monkeypatch.setattr(settings, "stuck_processing_timeout_minutes", 0)
    db = MagicMock()
    assert ct._fail_stuck_processing(db) == []
    db.query.assert_not_called()


def test_defaults_leave_the_failure_visible_before_the_reaper_reclaims_it():
    assert 0 < settings.stuck_processing_lost_minutes < settings.stuck_processing_timeout_minutes
    assert settings.stuck_processing_timeout_minutes < settings.stale_upload_timeout_hours * 60


# --- asking the broker -----------------------------------------------------------------------

def _queued_message():
    """A transcode job exactly as Celery serialises it: the ids sit in the headers as plain text."""
    return json.dumps({"body": "W1tdLCB7fSwge31d", "headers": {
        "task": "process_asset", "id": "33333333-3333-3333-3333-333333333333",
        "argsrepr": f"['{ASSET}', '{VERSION}']",
    }})


def _fake_broker(monkeypatch, queued=(), active=None, reserved=None, scheduled=None, redis_fails=False):
    import redis
    r = MagicMock()
    r.lrange.return_value = list(queued)
    monkeypatch.setattr(redis, "from_url", MagicMock(side_effect=OSError("down")) if redis_fails else lambda *a, **k: r)
    inspector = SimpleNamespace(active=lambda: active, reserved=lambda: reserved, scheduled=lambda: scheduled)
    monkeypatch.setattr(ct.celery_app.control, "inspect", lambda timeout=None: inspector)


def test_a_job_waiting_in_the_queue_counts_as_known(monkeypatch):
    _fake_broker(monkeypatch, queued=[_queued_message()], active={"w1": []})
    assert VERSION in ct._known_job_version_ids()


def test_a_job_a_worker_is_running_counts_as_known(monkeypatch):
    running = [{"name": "process_asset", "args": [ASSET, VERSION]}]
    _fake_broker(monkeypatch, active={"w1": running})
    assert VERSION in ct._known_job_version_ids()


def test_a_job_waiting_out_a_retry_delay_counts_as_known(monkeypatch):
    _fake_broker(monkeypatch, active={"w1": []}, scheduled={"w1": [{"request": {"args": [ASSET, VERSION]}}]})
    assert VERSION in ct._known_job_version_ids()


def test_an_idle_but_answering_worker_means_the_job_is_not_known(monkeypatch):
    _fake_broker(monkeypatch, active={"w1": []}, reserved={"w1": []}, scheduled={"w1": []})
    assert ct._known_job_version_ids() == set()


def test_no_worker_answering_means_unknown_not_lost(monkeypatch):
    _fake_broker(monkeypatch)  # every inspect call returns None
    assert ct._known_job_version_ids() is None


def test_an_unreachable_broker_means_unknown_not_lost(monkeypatch):
    _fake_broker(monkeypatch, redis_fails=True)
    assert ct._known_job_version_ids() is None


# --- scheduling ------------------------------------------------------------------------------

def test_the_watchdog_is_scheduled_every_five_minutes():
    entry = ct.celery_app.conf.beat_schedule["fail-stuck-processing"]
    assert entry["task"] == "fail_stuck_processing"
    assert "*/5" in str(entry["schedule"])
    assert ct.fail_stuck_processing.name == "fail_stuck_processing"
