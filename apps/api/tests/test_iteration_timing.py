"""Parts project confirmed exact-version state without inventing Engine phase events."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.api.models.asset import AssetVersion, MediaFile, ProcessingStatus
from apps.api.models.upload_request import RequestUpload
from apps.api.services.iteration_flow import current_recipes
from apps.api.services.iteration_requests import snapshot


NOW = datetime(2026, 10, 7, 0, 4, 1, tzinfo=timezone.utc)


@pytest.fixture
def timing_case(monkeypatch):
    from apps.api.services import review_timing
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(review_timing, 'datetime', Clock, raising=False)
    asset, version = uuid.uuid4(), uuid.uuid4()
    entry = {'asset_id':str(asset), 'version_id':str(version), 'version_number':1,
             'status':'ready', 'findings':[], 'bytes_stored':True}
    req = SimpleNamespace(id=uuid.uuid4(), project_id=uuid.uuid4(), receive_iterations=True,
        iteration_mode='components', iteration_ratio='9:16',
        iteration_manifest={'slots':[{'id':'h','role':'hook','label':'Hook'}], 'recipes':[]},
        iteration_state={'submitted':True, 'slots':{'h':entry}})
    current = SimpleNamespace(id=version, asset_id=asset, version_number=1, processing_status=ProcessingStatus.ready)
    uploaded = SimpleNamespace(submitted_at=datetime(2026,10,7,tzinfo=timezone.utc))
    queries = {model:MagicMock() for model in (AssetVersion, MediaFile, RequestUpload)}
    for query in queries.values():
        query.join.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
    queries[AssetVersion].first.return_value = current
    queries[AssetVersion].all.return_value = [current]
    queries[MediaFile].first.return_value = None
    queries[RequestUpload].first.return_value = uploaded
    db = MagicMock()
    db.query.side_effect = lambda model:queries[model]
    return req, db, entry, current, uploaded, queries


def test_part_wait_survives_reload_and_does_not_claim_analysis(timing_case):
    req, db, entry, _, _, queries = timing_case
    first = snapshot(req, db)['slots'][0]
    assert first['processing'] == 'ready'
    assert first['review_progress'] == {'stage':'waiting', 'version_id':entry['version_id'],
        'queued_at':'2026-10-07T00:00:00+00:00', 'elapsedSeconds':241}
    assert snapshot(req, db)['slots'][0]['review_progress'] == first['review_progress']
    upload_filter = queries[RequestUpload].filter.call_args.args
    params = {k:v for clause in upload_filter for k,v in clause.compile().params.items()}
    assert params['request_id_1'] == req.id
    assert params['asset_id_1'] == uuid.UUID(entry['asset_id'])
    assert params['version_number_1'] == 1
    sql = ' '.join(str(clause) for call in queries[AssetVersion].filter.call_args_list for clause in call.args)
    assert 'asset_versions.id' in sql and 'asset_versions.deleted_at IS NULL' in sql
    assert 'assets.project_id' in sql and 'assets.deleted_at IS NULL' in sql


def test_replacement_clock_uses_exact_version_submission(timing_case):
    req, db, entry, version, uploaded, _ = timing_case
    entry['version_id'] = str(uuid.uuid4())
    version.id = uuid.UUID(entry['version_id']); version.version_number = 2
    uploaded.submitted_at = datetime(2026,10,7,0,3,57,tzinfo=timezone.utc)
    out = snapshot(req, db)['slots'][0]
    assert out['version_number'] == 2
    assert out['review_progress']['version_id'] == entry['version_id']
    assert out['review_progress']['elapsedSeconds'] == 4


def test_missing_submission_never_uses_updated_at_lease_or_backoff(timing_case):
    req, db, entry, _, uploaded, _ = timing_case
    uploaded.submitted_at = None
    entry.update(updated_at=1, processing_queued_at=1, next_attempt_at=1)
    req.iteration_lease_until = NOW
    out = snapshot(req, db)['slots'][0]['review_progress']
    assert out == {'stage':'waiting', 'version_id':entry['version_id']}


@pytest.mark.parametrize('status,processing', [('error','ready'), ('processing','failed')])
def test_confirmed_failure_stops_review_activity(timing_case, status, processing):
    req, db, entry, version, _, _ = timing_case
    entry['status'] = status
    version.processing_status = ProcessingStatus(processing)
    assert snapshot(req, db)['slots'][0]['review_progress']['stage'] == 'failed'


def test_deleted_or_missing_exact_version_has_no_live_clock(timing_case):
    req, db, _, _, _, queries = timing_case
    queries[AssetVersion].first.return_value = None
    out = snapshot(req, db)['slots'][0]
    assert out['review_progress']['stage'] == 'failed'
    assert 'elapsedSeconds' not in out['review_progress']
    queries[RequestUpload].first.assert_not_called()


@pytest.mark.parametrize('status', ['held','clear'])
def test_source_feedback_remains_viewable_when_early_review_readiness_is_confirmed(timing_case, status):
    req, db, entry, version, _, _ = timing_case
    entry['status'] = status
    version.processing_status = ProcessingStatus.processing
    version.iteration_review_ready = True
    out = snapshot(req, db)['slots'][0]
    assert out['processing'] == 'ready'
    assert out['review_progress']['stage'] == 'done'


@pytest.mark.parametrize('status', ['reviewing','held','delivered'])
def test_current_output_is_selectable_without_borrowing_source_clock_or_releasing_download(timing_case, monkeypatch, status):
    req, db, entry, _, _, queries = timing_case
    entry['status'] = 'clear'
    req.iteration_manifest['recipes'] = [{'id':'ad', 'slots':['h'], 'label':'Final ad'}]
    _, key = next(current_recipes(str(req.id),req.iteration_manifest,req.iteration_state,'9:16'))
    output = {'asset_id':str(uuid.uuid4()), 'version_id':str(uuid.uuid4()), 'status':status, 's3_key':'final.mp4'}
    req.iteration_state['outputs'] = {key:output, 'stale':{'asset_id':'stale','status':'delivered','s3_key':'old'}}
    source_version = queries[AssetVersion].first.return_value
    queries[AssetVersion].first.side_effect = [source_version, SimpleNamespace(id=uuid.UUID(output['version_id']),
        asset_id=uuid.UUID(output['asset_id']), version_number=1, processing_status=ProcessingStatus.ready)]
    monkeypatch.setattr('apps.api.services.iteration_requests.s3_service.generate_presigned_get_url', lambda key,**kw:'https://media.test/'+key)
    result = snapshot(req, db)
    assert len(result['outputs']) == 1
    out = result['outputs'][0]
    assert out['asset_id'] == output['asset_id'] and out['version_id'] == output['version_id']
    assert out['processing'] == 'ready'
    assert out['review_progress'] == {'stage':'waiting' if status=='reviewing' else 'done', 'version_id':output['version_id']}
    assert ('media_url' in out) == (status in ('held','delivered'))
    assert ('download_url' in out) == (status == 'delivered')
    assert queries[RequestUpload].first.call_count == 1
