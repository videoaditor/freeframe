#!/usr/bin/env python3
"""Offline, evidence-bound AutoReview acceptance scoring. Never calls a model.

Provider execution stays in the existing comparison lab and its cost ledger.
Expected answers and adjudications must never be sent as provider input.
"""
import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

SCHEMA = 'autoreview.acceptance.v1'
JOURNEY = ('owner_setup', 'brief_ready', 'guest_link_opened', 'v1_uploaded',
           'v1_reviewed', 'v2_uploaded_same_asset', 'v2_reviewed', 'finish_accepted',
           'owner_reload', 'share_reload', 'download_verified', 'v1_history_preserved',
           'no_brand_kit', 'private_brief_rejected', 'contradictory_brand_rules')
RECOVERY = ('provider_401', 'provider_429', 'provider_5xx', 'provider_timeout',
            'bad_media', 'missing_object', 'hash_mismatch', 'interrupted_upload',
            'lost_response', 'duplicate_request', 'worker_restart', 'context_mismatch',
            'stale_result', 'foreign_tenant', 'revoked_link', 'expired_entitlement')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def evidence(refs):
    if not refs:
        raise ValueError('missing evidence')
    for ref in refs:
        p = Path(ref['path'])
        if not p.is_absolute() or not p.is_file():
            raise ValueError('evidence must be an existing absolute file path')
        h = hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        if h.hexdigest() != ref['sha256']:
            raise ValueError('evidence hash mismatch')


def unique(rows, key):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            raise ValueError(f'duplicate identity: {identity}')
        result[identity] = row
    return result


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamps must include timezone')
    return parsed


def validate(manifest):
    if manifest.get('schema') != SCHEMA or manifest.get('mode') not in ('prospective', 'retrospective'):
        raise ValueError('unsupported manifest schema/mode')
    timestamp(manifest['frozen_at'])
    cases = unique(manifest['cases'], lambda c: c['id'])
    if not cases or not manifest['engines'] or not manifest['plan']:
        raise ValueError('empty evaluation')
    for engine in manifest['engines'].values():
        if not all(engine.get(k) for k in ('revision', 'model', 'config_sha256')):
            raise ValueError('engine provenance incomplete')
    source_splits, media_sources = {}, {}
    for case in cases.values():
        if not case['source_group'] or not case['brand'] or case['split'] not in ('regression', 'holdout'):
            raise ValueError('invalid source/brand/split')
        if type(case['clean_control']) is not bool or case['clean_control'] and case['defects']:
            raise ValueError('invalid clean control')
        for field in ('media_sha256', 'context_sha256'):
            value = case.get(field, '')
            if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('missing media/context identity')
        source, split = case['source_group'], case['split']
        if source in source_splits and source_splits[source] != split:
            raise ValueError('source split leakage')
        source_splits[source] = split
        media = case['media_sha256']
        if media in media_sources and media_sources[media] != source:
            raise ValueError('identical media cannot count as independent sources')
        media_sources[media] = source
        unique(case['defects'], lambda d: d['id'])
        evidence(case['evidence'])
        hashes = {ref['sha256'] for ref in case['evidence']}
        if case['media_sha256'] not in hashes or case['context_sha256'] not in hashes:
            raise ValueError('media/context identities lack matching evidence files')
        ground = case.get('ground_truth', {})
        if not ground.get('reviewer') or ground.get('reviewer_type') not in ('agent', 'human'):
            raise ValueError('ground truth provenance missing')
        evidence(ground.get('evidence'))
        for d in case['defects']:
            if not all(d.get(k) for k in ('category', 'expected', 'observed', 'placement')):
                raise ValueError('incomplete defect ground truth')
            if d['severity'] not in ('critical', 'noncritical') or not 0 <= d['start'] <= d['end'] < math.inf:
                raise ValueError('invalid defect severity/interval')
    unique(manifest['plan'], lambda p: p['run_id'])
    unique(manifest['plan'], lambda p: (p['case_id'], p['engine'], p['repeat']))
    for p in manifest['plan']:
        if p['case_id'] not in cases or p['engine'] not in manifest['engines'] or type(p['repeat']) is not int or p['repeat'] < 1:
            raise ValueError('invalid planned run')
    groups = defaultdict(set)
    for p in manifest['plan']:
        groups[p['case_id'], p['engine']].add(p['repeat'])
    if set(groups) != {(c, e) for c in cases for e in manifest['engines']}:
        raise ValueError('incomplete case x engine plan coverage')
    if any(len(v) == 2 for v in groups.values()):
        raise ValueError('repeat subsets require at least three executions')
    if any(v != set(range(1, max(v)+1)) for v in groups.values()):
        raise ValueError('repeats must begin at one and be consecutive')
    return cases


def check_delivery(trace):
    """Identity gate, in addition to independent inspection of real HTTP/DB evidence."""
    problems = []
    version = trace.get('required_version')
    if not version or trace.get('reviewed_version') != version or trace.get('finished_version') != version:
        problems.append('version_mismatch')
    uploaded = trace.get('uploaded_sha256', '')
    if len(uploaded) != 64 or uploaded != trace.get('downloaded_sha256'):
        problems.append('download_hash_mismatch')
    if not trace.get('asset_id') or trace.get('v1_asset_id') != trace.get('asset_id'):
        problems.append('asset_identity_missing_or_changed')
    if trace.get('evidence_level') != 'real_provider_http_db':
        problems.append('real_journey_not_verified')
    steps = trace.get('steps', {})
    for step in JOURNEY:
        row = steps.get(step, {})
        if row.get('status') != 'passed' or not row.get('evidence'):
            problems.append(f'not_tested:{step}')
        else:
            evidence(row['evidence'])
    return problems


def exact_interval(k, n):
    """Two-sided 95% Clopper-Pearson; descriptive only for nonrandom samples."""
    if not n:
        return None
    def cdf(x, p):
        return sum(math.comb(n, j)*p**j*(1-p)**(n-j) for j in range(x+1))
    def inverse(x, target):
        lo, hi = 0., 1.
        for _ in range(60):
            mid = (lo+hi)/2
            if cdf(x, mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo+hi)/2
    return [0. if not k else inverse(k-1, .975), 1. if k == n else inverse(k, .025)]


def score(manifest, runs, adjudications, journeys):
    cases = validate(manifest)
    frozen_hash = digest(manifest)
    planned = {p['run_id']: p for p in manifest['plan']}
    saved = unique(runs, lambda r: r['run_id'])
    labels = unique(adjudications, lambda a: (a['run_id'], a['finding_id']))
    findings = {}
    execution_ids = set()
    for rid, run in saved.items():
        if rid not in planned:
            raise ValueError('unplanned run')
        if run['manifest_sha256'] != frozen_hash:
            raise ValueError('run manifest hash mismatch')
        if manifest['mode'] == 'prospective' and timestamp(run['started_at']) < timestamp(manifest['frozen_at']):
            raise ValueError('manifest frozen after execution')
        if run['status'] not in ('completed', 'failed', 'timeout', 'interrupted', 'unavailable') or run['verdict'] not in ('held', 'clear', 'unavailable'):
            raise ValueError('invalid run status/verdict')
        evidence(run['evidence'])
        case = cases[planned[rid]['case_id']]
        if any(run.get(k) != case[k] for k in ('media_sha256', 'context_sha256')):
            raise ValueError('run media/context mismatch')
        execution_id = run.get('execution_id')
        if not execution_id or execution_id in execution_ids:
            raise ValueError('missing or reused execution identity')
        execution_ids.add(execution_id)
        for f in run['findings']:
            if not isinstance(f.get('text'), str) or not f['text'].strip():
                raise ValueError('missing finding text')
        findings[rid] = unique(run['findings'], lambda f: f['id'])
    for (rid, fid), label in labels.items():
        if rid not in findings or fid not in findings[rid]:
            raise ValueError('adjudication points to unknown finding')
        if label['judgment'] not in ('valid', 'invalid', 'unresolved') or label['reviewer_type'] not in ('human', 'agent') or not label['reviewer'] or not label['rationale']:
            raise ValueError('invalid adjudication')
        defect = label.get('defect_id')
        if defect and defect not in {d['id'] for d in cases[planned[rid]['case_id']]['defects']}:
            raise ValueError('adjudication points to unknown defect')
    output = {'schema': SCHEMA, 'manifest_sha256': frozen_hash, 'mode': manifest['mode'],
              'scope': 'Offline evidence scoring; not a fresh provider or customer journey test. Hashes prove file integrity, not the truth of their labels. Independent raw-evidence review and manual acceptance are always required.', 'engines': {}}
    for engine in manifest['engines']:
        rows, repeated = [], defaultdict(list)
        for rid, p in planned.items():
            if p['engine'] != engine:
                continue
            c = cases[p['case_id']]
            r = saved.get(rid, {})
            stale = bool(r) and (not r.get('expected_version_id') or r.get('expected_version_id') != r.get('reviewed_version_id'))
            usable = r.get('status') == 'completed' and r.get('verdict') != 'unavailable' and not stale
            found, valid, unresolved, total, human = set(), 0, 0, 0, True
            assigned = set()
            for fid, f in findings.get(rid, {}).items():
                total += 1
                a = labels.get((rid, fid), {})
                if a.get('judgment', 'unresolved') == 'unresolved':
                    unresolved += 1
                    human = False
                    continue
                human &= a.get('reviewer_type') == 'human'
                if a.get('judgment') != 'valid':
                    continue
                did = a.get('defect_id')
                if not did or did not in assigned:
                    valid += 1  # one precision credit; any localized duplicate can establish recall
                if did:
                    assigned.add(did)
                    d = next(d for d in c['defects'] if d['id'] == did)
                    t = f.get('time')
                    if usable and isinstance(t, (int,float)) and d['start']-2 <= t <= d['end']+2:
                        found.add(did)
            critical = {d['id'] for d in c['defects'] if d['severity'] == 'critical'}
            row = {'run_id': rid, 'case_id': c['id'], 'source_group': c['source_group'],
                   'brand': c['brand'], 'split': c['split'], 'repeat': p['repeat'],
                   'usable': usable, 'stale': stale, 'verdict': r.get('verdict','not_tested'),
                   'critical_expected': len(critical), 'critical_found': len(critical & found),
                   'critical_missed': sorted(critical-found), 'defects_found': sorted(found),
                   'defects_expected': len(c['defects']), 'findings': total, 'valid_findings': valid,
                   'unresolved': unresolved, 'human_adjudicated': human and bool(r),
                   'clean_control': c['clean_control'],
                   'false_clear': r.get('verdict') == 'clear' and bool(critical),
                   'false_blocker': c['clean_control'] and (r.get('verdict') == 'held' or any(f.get('severity') == 'blocker' for f in findings.get(rid, {}).values()))}
            rows.append(row)
            repeated[c['id']].append(row)
        primary = [r for r in rows if r['repeat'] == 1]
        count = len(primary)
        denominator = sum(r['critical_expected'] for r in primary)
        numerator = sum(r['critical_found'] for r in primary)
        nfind = sum(r['findings'] for r in primary)
        nvalid = sum(r['valid_findings'] for r in primary)
        nunknown = sum(r['unresolved'] for r in primary)
        sources = {r['source_group'] for r in primary}
        critical_sources = {r['source_group'] for r in primary if r['critical_expected']}
        failed_sources = {r['source_group'] for r in primary if r['critical_missed']}
        clean_sources = {r['source_group'] for r in primary if r['clean_control']} - critical_sources
        repeat_groups = [g for g in repeated.values() if len(g) >= 3]
        agreement = sum(all(r['usable'] for r in g) and len({(r['verdict'],tuple(r['defects_found'])) for r in g}) == 1 for g in repeat_groups)
        blockers = []
        if manifest['mode'] != 'prospective': blockers.append('retrospective_evidence_only')
        if len(sources) < 12 or len({r['brand'] for r in primary}) < 3: blockers.append('pilot_sample_too_small')
        if len(clean_sources) < 6: blockers.append('insufficient_independent_clean_controls')
        if not denominator or numerator != denominator: blockers.append('critical_detection_not_demonstrated')
        if any(r['repeat'] > 1 and r['critical_missed'] for r in rows): blockers.append('critical_repeat_missed')
        if any(r['false_clear'] or r['false_blocker'] or r['stale'] for r in rows): blockers.append('unsafe_clear_blocker_or_version')
        if any(not r['usable'] for r in rows): blockers.append('incomplete_or_unusable_runs')
        if not nfind or nvalid/nfind < .9 or nunknown: blockers.append('precision_unqualified')
        if any(c['ground_truth']['reviewer_type'] != 'human' for c in cases.values()): blockers.append('human_ground_truth_missing')
        if any(not r['human_adjudicated'] for r in rows): blockers.append('independent_human_adjudication_missing')
        if not repeat_groups or agreement != len(repeat_groups): blockers.append('repeatability_unqualified')
        if not any(r['split'] == 'holdout' for r in primary): blockers.append('unseen_holdout_missing')
        engine_journeys = [j for j in journeys if j.get('engine') == engine]
        if not engine_journeys or any(check_delivery(j) for j in engine_journeys): blockers.append('real_customer_journey_unverified')
        verified_recovery, failed_recovery = set(), set()
        for j in engine_journeys:
            for name, check in j.get('recovery', {}).items():
                if name in RECOVERY and check.get('status') != 'passed':
                    failed_recovery.add(name)
                if check.get('status') == 'passed' and check.get('evidence_level') == 'isolated_http_db' and check.get('evidence'):
                    evidence(check['evidence'])
                    verified_recovery.add(name)
        if set(RECOVERY) - verified_recovery: blockers.append('recovery_matrix_incomplete')
        if failed_recovery: blockers.append('recovery_failure')
        output['engines'][engine] = {
            'qualification': 'BLOCKED' if blockers else 'PILOT_CANDIDATE_REQUIRES_MANUAL_ACCEPTANCE', 'blockers': blockers,
            'independent_sources': len(sources), 'independent_clean_sources': len(clean_sources),
            'critical_recall': {'found': numerator, 'expected': denominator, 'rate': numerator/denominator if denominator else None},
            'source_critical_recall': {'found': len(critical_sources-failed_sources), 'expected': len(critical_sources),
                'two_sided_exact_95_interval': exact_interval(len(critical_sources-failed_sources), len(critical_sources))},
            'precision_lower_bound': nvalid/nfind if nfind else None,
            'precision_upper_bound': (nvalid+nunknown)/nfind if nfind else None,
            'unresolved_findings': nunknown, 'not_completed': sum(not r['usable'] for r in primary),
            'false_clear_runs': sum(r['false_clear'] for r in rows),
            'false_blocker_runs': sum(r['false_blocker'] for r in rows),
            'stale_version_runs': sum(r['stale'] for r in rows),
            'repeat_agreement': {'usable_agreeing_groups': agreement, 'planned_groups': len(repeat_groups)},
            'missing_recovery_checks': sorted(set(RECOVERY)-verified_recovery),
            'failed_recovery_checks': sorted(failed_recovery), 'cases': rows}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'score'])
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--runs', type=Path)
    parser.add_argument('--adjudications', type=Path)
    parser.add_argument('--journeys', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    def read(path):
        return json.loads(path.read_text()) if path else []
    try:
        manifest = read(args.manifest)
        if args.command == 'validate':
            validate(manifest)
            result = {'valid': True, 'manifest_sha256': digest(manifest)}
        else:
            result = score(manifest, read(args.runs), read(args.adjudications), read(args.journeys))
        text = json.dumps(result, indent=2, allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x') as f: f.write(text)
        else:
            print(text, end='')
        return 0 if args.command == 'validate' or all(e['qualification'] != 'BLOCKED' for e in result['engines'].values()) else 2
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'Audit invalid: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
