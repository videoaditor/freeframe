"""Workspace rounds: every key of the workspace sees rounds and approvals; the first fetch claims a round."""
from datetime import datetime, timedelta, timezone
import uuid

from .agent_pg import env, needs_pg  # noqa: F401
from .test_feedback_rounds import comment, rounds, scene  # noqa: F401
from .test_round_close_left import done
from .test_share_approve import link

pytestmark = needs_pg


def foreign_key(e, name="Cutter"):
    """A key of another owner's workspace."""
    other = e.user("Other")
    proj = e.project(other, "Foreign")
    code = e.client.post(f"/projects/{proj.id}/agent-pairing-codes", headers=e.headers(other)).json()["code"]
    body = e.client.post("/agents/pair", json={"code": code, "agent_name": name, "program": "codex"}).json()
    return {"Authorization": f"Bearer {body['agent_key']}"}


def fetch(e, who):
    return e.client.get("/agent/feedback", headers=who.headers).json()


def closed_round(e):
    comment(e, e.scene.asset)
    done(e)
    return rounds(e)[0].id


def age_claim(e, rid, minutes=31):
    """Make the claim (and the hand-in that preceded it) `minutes` old, as if the agent had been silent since."""
    from apps.api.models.upload_request import RequestUpload
    ago = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    set_claim(e, rid, claimed_at=ago)
    with e.Session() as db:
        db.query(RequestUpload).update({"submitted_at": ago - timedelta(minutes=10)})
        db.commit()


def set_claim(e, rid, **kw):
    from apps.api.models.agent import FeedbackRound
    with e.Session() as db:
        r = db.get(FeedbackRound, rid)
        for k, v in kw.items():
            setattr(r, k, v)
        db.commit()


def test_a_sibling_key_sees_the_round_and_the_first_fetch_claims_it(scene):
    e = scene
    a = e.scene.agent                       # handed the version in
    b = e.pair_agent(e.project_a, "Second")
    closed_round(e)
    [rb] = fetch(e, b)["rounds"]            # B asks first
    assert rb["claimed_by_me"] is True and rb["claimed_by"] == {"id": b.user_id, "name": "Second (codex)"}
    [ra] = fetch(e, a)["rounds"]            # A still sees it, flagged
    assert ra["claimed_by_me"] is False and ra["claimed_by"]["id"] == b.user_id
    assert fetch(e, b)["rounds"][0]["claimed_by_me"] is True


def test_ack_by_either_key_closes_it_and_a_second_ack_is_a_no_op(scene):
    e = scene
    b = e.pair_agent(e.project_a, "Second")
    rid = closed_round(e)
    assert e.client.post(f"/agent/feedback/{rid}/ack", headers=b.headers).status_code == 204
    first = rounds(e)[0].acked_at
    assert first is not None
    assert e.client.post(f"/agent/feedback/{rid}/ack", headers=e.scene.agent.headers).status_code == 204
    assert rounds(e)[0].acked_at == first
    assert fetch(e, e.scene.agent)["rounds"] == [] and fetch(e, b)["rounds"] == []


def test_a_stale_claim_passes_on_unless_a_version_came_in_since(scene):
    e = scene
    a, b = e.scene.agent, e.pair_agent(e.project_a, "Second")
    rid = closed_round(e)
    fetch(e, a)                                                       # A claims
    age_claim(e, rid)
    # a version uploaded after the claim keeps A's claim alive
    from apps.api.models.upload_request import RequestUpload
    with e.Session() as db:
        db.add(RequestUpload(request_id=e.scene.req.id, asset_id=e.scene.asset.id, version_number=2, uploader_name="A",
                             uploader_email=a.who.email, submitted_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
        db.commit()
    assert fetch(e, b)["rounds"][0]["claimed_by_me"] is False
    with e.Session() as db:
        db.query(RequestUpload).filter(RequestUpload.version_number == 2).delete()
        db.commit()
    assert fetch(e, b)["rounds"][0]["claimed_by_me"] is True          # no upload since: B takes over
    assert fetch(e, a)["rounds"][0]["claimed_by_me"] is False


def test_a_key_in_another_workspace_sees_nothing(scene):
    e = scene
    closed_round(e)
    foreign = foreign_key(e)
    assert e.client.get("/agent/feedback", headers=foreign).json()["rounds"] == []
    assert e.client.post(f"/agent/feedback/{rounds(e)[0].id}/ack", headers=foreign).status_code == 404


def test_embed_says_working_only_while_a_claim_is_live(scene):
    e = scene
    b = e.pair_agent(e.project_a, "Second")
    rid = closed_round(e)
    tok = link(e, e.scene.req.folder_id, "comment")
    get = lambda: e.client.get(f"/share/{tok}/assets?page=1&per_page=50&embed=true").json()["assets"][0]
    assert (get()["sent_notes"], get()["working_notes"]) == (1, 0)    # waiting for Claude
    fetch(e, b)
    assert (get()["sent_notes"], get()["working_notes"]) == (1, 1)    # claimed: working
    age_claim(e, rid)
    assert (get()["sent_notes"], get()["working_notes"]) == (1, 0)    # stale: waiting again


def test_asking_for_one_request_never_claims_another_requests_round(scene):
    e = scene
    comment(e, e.scene.asset)
    done(e)
    other = uuid.uuid4()
    r = e.client.get(f"/agent/feedback?request_id={other}", headers=e.scene.agent.headers)
    assert r.status_code == 200 and r.json()["rounds"] == []
    [rnd] = rounds(e)
    assert rnd.claimed_by is None


def test_peek_reads_the_round_without_claiming_it(scene):
    e = scene
    comment(e, e.scene.asset)
    done(e)
    r = e.client.get("/agent/feedback?peek=true", headers=e.scene.agent.headers)
    assert r.status_code == 200 and len(r.json()["rounds"]) == 1
    [rnd] = rounds(e)
    assert rnd.claimed_by is None
