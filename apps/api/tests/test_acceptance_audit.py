"""Failures here prevent an evaluator from manufacturing a green result."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'autoreview_acceptance.py'


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'Acceptance evaluator has not been built')
        spec = importlib.util.spec_from_file_location('acceptance', SCRIPT)
        self.audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.audit)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        raw = self.root / 'raw.json'
        raw.write_text('{"raw":"test evidence only"}')
        evidence = {'path': str(raw), 'sha256': hashlib.sha256(raw.read_bytes()).hexdigest()}
        self.manifest = {
            'schema': 'autoreview.acceptance.v1', 'mode': 'retrospective',
            'frozen_at': '2026-10-08T00:00:00+00:00',
            'engines': {'candidate': {'revision': 'abc', 'model': 'model', 'config_sha256': 'a'*64}},
            'cases': [{'id': 'endcard', 'source_group': 'ad-1', 'brand': 'brand-1',
                       'split': 'regression', 'clean_control': False, 'evidence': [evidence],
                       'media_sha256': evidence['sha256'], 'context_sha256': evidence['sha256'],
                       'ground_truth': {'reviewer': 'editor-1', 'reviewer_type': 'human', 'evidence': [evidence]},
                       'defects': [{'id': 'code', 'category': 'promo_code', 'expected': 'SHINE70',
                                    'observed': 'SHINE50', 'placement': 'endcard', 'start': 22,
                                    'end': 25, 'severity': 'critical'}]}],
            'plan': [{'run_id': 'r1', 'case_id': 'endcard', 'engine': 'candidate', 'repeat': 1}]
        }
        self.run = {'run_id': 'r1', 'manifest_sha256': self.audit.digest(self.manifest),
                    'status': 'completed', 'verdict': 'held', 'started_at': '2026-10-07T00:00:00+00:00',
                    'expected_version_id': 'v1', 'reviewed_version_id': 'v1', 'evidence': [evidence],
                    'execution_id': 'exec-1', 'media_sha256': evidence['sha256'], 'context_sha256': evidence['sha256'],
                    'findings': [{'id': 'f1', 'time': 23, 'severity': 'blocker', 'text': 'Replace SHINE50 with SHINE70 on the endcard.'}]}
        self.label = {'run_id': 'r1', 'finding_id': 'f1', 'defect_id': 'code',
                      'judgment': 'valid', 'reviewer': 'editor-1', 'reviewer_type': 'human',
                      'rationale': 'Wrong endcard code visible in the source.'}

    def score(self, runs=None, labels=None):
        return self.audit.score(self.manifest, [self.run] if runs is None else runs,
                                [self.label] if labels is None else labels, [])['engines']['candidate']

    def test_missing_run_stays_in_recall_denominator(self):
        report = self.score([], [])
        self.assertEqual(report['critical_recall'], {'found': 0, 'expected': 1, 'rate': 0.0})
        self.assertEqual(report['not_completed'], 1)
        self.assertEqual(report['qualification'], 'BLOCKED')

    def test_duplicate_findings_do_not_inflate_recall_or_precision(self):
        self.run['findings'].append({'id': 'f2', 'time': 24, 'severity': 'blocker', 'text': 'Same code defect again.'})
        second = dict(self.label, finding_id='f2')
        report = self.score(labels=[self.label, second])
        self.assertEqual(report['critical_recall']['found'], 1)
        self.assertEqual(report['precision_lower_bound'], 0.5)

    def test_unrelated_hold_is_not_detection(self):
        self.label['defect_id'] = None
        report = self.score()
        self.assertEqual(report['critical_recall']['found'], 0)
        self.assertEqual(report['false_clear_runs'], 0)

    def test_false_clear_recorded_independent_of_findings(self):
        self.run['verdict'] = 'clear'
        self.assertEqual(self.score()['false_clear_runs'], 1)

    def test_stale_version_does_not_count_as_detection(self):
        self.run['reviewed_version_id'] = 'v0'
        report = self.score()
        self.assertEqual(report['critical_recall']['found'], 0)
        self.assertEqual(report['stale_version_runs'], 1)

    def test_unknown_findings_lower_precision_and_do_not_disappear(self):
        report = self.score(labels=[])
        self.assertEqual(report['precision_lower_bound'], 0.0)
        self.assertEqual(report['precision_upper_bound'], 1.0)
        self.assertEqual(report['unresolved_findings'], 1)

    def test_temporal_miss_does_not_count_as_usable_detection(self):
        self.run['findings'][0]['time'] = 3
        self.assertEqual(self.score()['critical_recall']['found'], 0)

    def test_completed_report_is_not_production_qualification(self):
        self.assertEqual(self.score()['qualification'], 'BLOCKED')

    def test_changed_source_bytes_rejected(self):
        Path(self.manifest['cases'][0]['evidence'][0]['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.score()

    def test_manifest_mismatch_rejected(self):
        self.run['manifest_sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'manifest'):
            self.score()

    def test_duplicate_run_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.score([self.run, self.run])

    def test_unplanned_run_rejected(self):
        self.run['run_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'unplanned'):
            self.score(labels=[])

    def test_prospective_plan_must_predate_execution(self):
        self.manifest['mode'] = 'prospective'
        self.run['manifest_sha256'] = self.audit.digest(self.manifest)
        with self.assertRaisesRegex(ValueError, 'frozen'):
            self.score()

    def test_correlated_variants_count_as_one_source(self):
        duplicate = copy.deepcopy(self.manifest['cases'][0])
        duplicate['id'] = 'endcard-variant'
        self.manifest['cases'].append(duplicate)
        self.manifest['plan'].append({'run_id': 'r2', 'case_id': 'endcard-variant', 'engine': 'candidate', 'repeat': 1})
        self.run['manifest_sha256'] = self.audit.digest(self.manifest)
        self.assertEqual(self.score()['independent_sources'], 1)

    def test_failed_repeats_are_not_consistency_success(self):
        self.manifest['plan'].extend(dict(self.manifest['plan'][0],run_id=f'r{i}',repeat=i) for i in (2,3))
        self.assertEqual(self.score([], [])['repeat_agreement'], {'usable_agreeing_groups': 0, 'planned_groups': 1})

    def test_finish_trace_with_wrong_download_hash_is_blocked(self):
        trace = {'required_version': 'v2', 'reviewed_version': 'v2', 'finished_version': 'v2',
                 'uploaded_sha256': 'a'*64, 'downloaded_sha256': 'b'*64}
        self.assertIn('download_hash_mismatch', self.audit.check_delivery(trace))

    def test_finish_trace_missing_evidence_is_not_pass(self):
        self.assertTrue(self.audit.check_delivery({}))

    def test_unplanned_manifest_case_rejected(self):
        case = copy.deepcopy(self.manifest['cases'][0])
        case['id'] = 'missing-from-plan'
        self.manifest['cases'].append(case)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.score([], [])

    def test_every_critical_repeat_miss_blocks(self):
        self.manifest['plan'].extend(dict(self.manifest['plan'][0], run_id=f'r{i}', repeat=i) for i in (2,3))
        self.run['manifest_sha256'] = self.audit.digest(self.manifest)
        runs = [self.run, dict(self.run, run_id='r2', execution_id='exec-2', findings=[]),
                dict(self.run, run_id='r3', execution_id='exec-3')]
        report = self.score(runs, [self.label, dict(self.label,run_id='r3')])
        self.assertIn('critical_repeat_missed', report['blockers'])

    def test_cached_repeat_rejected(self):
        self.manifest['plan'].extend(dict(self.manifest['plan'][0], run_id=f'r{i}', repeat=i) for i in (2,3))
        self.run['manifest_sha256'] = self.audit.digest(self.manifest)
        with self.assertRaisesRegex(ValueError, 'execution'):
            self.score([self.run, dict(self.run,run_id='r2')], [])

    def test_two_repeat_plan_is_incomplete(self):
        self.manifest['plan'].append(dict(self.manifest['plan'][0], run_id='r2',repeat=2))
        with self.assertRaisesRegex(ValueError, 'three'):
            self.score([], [])

    def test_media_or_context_mismatch_rejected(self):
        self.run['media_sha256'] = 'e'*64
        with self.assertRaisesRegex(ValueError, 'media/context'):
            self.score()

    def test_empty_finding_text_rejected(self):
        self.run['findings'][0]['text'] = ''
        with self.assertRaisesRegex(ValueError, 'finding text'):
            self.score()

    def test_source_cannot_leak_between_holdout_and_regression(self):
        case = copy.deepcopy(self.manifest['cases'][0])
        case.update(id='leaked', split='holdout')
        self.manifest['cases'].append(case)
        self.manifest['plan'].append(dict(self.manifest['plan'][0],run_id='r2',case_id='leaked'))
        with self.assertRaisesRegex(ValueError, 'split'):
            self.score([], [])

    def test_clean_control_requires_explicit_ground_truth_review(self):
        self.manifest['cases'][0]['ground_truth']['reviewer_type'] = 'agent'
        self.run['manifest_sha256'] = self.audit.digest(self.manifest)
        self.assertIn('human_ground_truth_missing', self.score()['blockers'])

    def test_duplicate_finding_order_does_not_change_recall(self):
        good = dict(self.run['findings'][0], id='f2')
        self.run['findings'][0]['time'] = 3
        self.run['findings'].append(good)
        labels = [self.label, dict(self.label, finding_id='f2')]
        first = self.score(labels=labels)
        self.run['findings'].reverse()
        second = self.score(labels=labels)
        self.assertEqual(first['critical_recall']['found'], 1)
        self.assertEqual(second['critical_recall']['found'], 1)
        self.assertEqual(first['precision_lower_bound'], .5)

    def test_recovery_failure_cannot_be_hidden_by_a_pass(self):
        good = {'engine': 'candidate', 'recovery': {'foreign_tenant': {
            'status': 'passed', 'evidence_level': 'isolated_http_db', 'evidence': self.run['evidence']}}}
        bad = {'engine': 'candidate', 'recovery': {'foreign_tenant': {'status': 'failed'}}}
        report = self.audit.score(self.manifest, [self.run], [self.label], [good,bad])['engines']['candidate']
        self.assertIn('recovery_failure', report['blockers'])
        self.assertIn('foreign_tenant', report['failed_recovery_checks'])

if __name__ == '__main__':
    unittest.main()
