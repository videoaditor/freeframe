# AutoReview acceptance audit

This is an offline acceptance evaluator, not a second review engine. It scores saved evidence; it never calls a provider, changes a default, activates an allowlist or retries an old customer job. A passing local test suite is not an engine-quality verdict.

## Operator flow

1. Freeze a private prospective manifest **before** execution. Name the exact engine revision, model and config hash. Every case needs source-group and brand, media/context SHA256 hashes with matching absolute evidence files, independently reviewed ground truth and the expected defects. Keep labels and human comments out of provider inputs. Use a source-disjoint holdout; examples already used to improve the engine are regressions.
2. Validate using `python3 scripts/autoreview_acceptance.py validate --manifest /absolute/private/manifest.json`. Validation prints the canonical manifest digest. Make one planned run per case × engine; use three or more fresh executions for repeated cases. Do not omit failed/unavailable attempts.
3. Execute through the existing AutoReview comparison lab and its reserved-before-call budget ledger. The old October 4 ledger remains exhausted and immutable. Start no new generation without the newly authorized cap and a new private ledger. Preserve provider execution IDs, raw outputs, timings, costs and version identity. **A generic prospective runner/import adapter is not supplied by this offline evaluator**: audit its mapping against raw responses before use.
4. Independently adjudicate each actionable finding against exact source frames and the frozen brief. Score with `python3 scripts/autoreview_acceptance.py score --manifest /absolute/private/manifest.json --runs /absolute/private/runs.json --adjudications /absolute/private/adjudications.json --journeys /absolute/private/journeys.json --output /absolute/private/report.json`. Output creation is exclusive: previous reports cannot be overwritten. Exit 2 means valid evidence but blocked acceptance; exit 1 means invalid input; exit 0 means no automatic blocker, **manual acceptance still required**.
5. Inspect raw evidence and results before signing off. Missing or manually asserted journey evidence cannot establish end-to-end operation. The highest machine status is `PILOT_CANDIDATE_REQUIRES_MANUAL_ACCEPTANCE`, never production READY. Do not activate a customer default from this status.

## Private JSON contract

All inputs are JSON; private source clips, signed URLs, credentials and customer findings must not enter Git. The manifest has `schema: autoreview.acceptance.v1`, `mode: prospective|retrospective`, timezone-aware `frozen_at`, `engines`, `cases` and `plan`. Engines map names to `revision`, `model`, `config_sha256`. Cases contain:

```json
{
  "id": "endcard-code",
  "source_group": "independent-source-ad-01",
  "brand": "brand-a",
  "split": "holdout",
  "clean_control": false,
  "media_sha256": "<64 lowercase hex characters>",
  "context_sha256": "<64 lowercase hex characters>",
  "evidence": [{"path": "/absolute/source.mp4", "sha256": "<hash>"}, {"path": "/absolute/context.json", "sha256": "<hash>"}],
  "ground_truth": {"reviewer": "independent-editor", "reviewer_type": "human", "evidence": [{"path": "/absolute/labels.json", "sha256": "<hash>"}]},
  "defects": [{"id": "wrong-code", "category": "promo_code", "expected": "SAVE20", "observed": "SAVE10", "placement": "endcard", "start": 22, "end": 25, "severity": "critical"}]
}
```

Plan rows: `run_id`, `case_id`, `engine`, integer `repeat` beginning at 1. Every case×engine pair is mandatory. Repeated subsets have at least three runs. Run rows: `run_id`, `execution_id` (fresh, unique), `manifest_sha256`, `media_sha256`, `context_sha256`, `started_at`, `expected_version_id`, `reviewed_version_id`, `status` (`completed|failed|timeout|interrupted|unavailable`), `verdict` (`clear|held|unavailable`), `evidence` (raw output references), `findings` (`id`, `time` in seconds, `text`, `severity`). Use the real asset-version ID for production journeys; local fixture identifiers are historical evidence only.

Adjudications: `run_id`, `finding_id`, nullable `defect_id`, `judgment` (`valid|invalid|unresolved`), `reviewer`, `reviewer_type` (`human|agent`), `rationale`. Valid findings not in the original ground truth may have a null defect ID: they affect precision but cannot count as detecting a prelabelled defect. Missing labels stay unresolved. Agent reviews remain visible and block human qualification.

## Acceptance gates

Pilot target: 12 independent ads, 3 brands, 6 independent clean controls, every critical defect found, no false clears/false blockers/stale versions, ≥90% conservative actionable precision, no unresolved findings, all required runs usable, repeated subsets agree, independent human ground truth and finding adjudication, unseen holdout and full delivery/recovery evidence. These are pilot gates, not proof of production reliability. Larger launch qualification needs a separately frozen representative sample and manual acceptance; the script does not issue broad-launch approval.

Recall keeps unavailable and missing runs in its denominator. Duplicate findings never increase recall and reduce precision. Localization tolerance is the defect interval ±2 seconds. Primary metrics use repeat 1; all repeats affect safety gates. Critical source recall counts a source successful only if every critical primary variant succeeded. Confidence intervals are two-sided exact 95% Clopper-Pearson and descriptive for a nonrandom sample. Precision bounds count unresolved findings as all false/all valid respectively. `false_clear_runs` means clear despite a known critical defect; unavailable is an abstention, not a safe pass. Repeated failure is not agreement success.

## Delivery and recovery evidence

Journey records require engine, actual `asset_id`/`v1_asset_id`, `required_version`/`reviewed_version`/`finished_version`, uploaded/downloaded SHA256 equality, `evidence_level: real_provider_http_db`, and `steps` mapping every `JOURNEY` constant in the script to status/evidence. Include real owner and separate guest browser traces, durable DB/API identities, V1 history, no-kit onboarding, inaccessible brief rejection and contrary brand expectations. A ready dashboard label is not enough.

`recovery` maps every `RECOVERY` constant to status/evidence with `evidence_level: isolated_http_db`. Inject failures only in an isolated equivalent stack. Cover provider failures, missing media, upload/review interruption, duplicate requests, restart, mismatched context, stale results, tenant isolation, revoked links and expiry. Do not fault-inject production or alter existing customer entitlements. Local DB mocks do not establish these gates.

Hashes verify bytes, not whether their contents substantiate a claim. Verify raw response/DB traces against the normalized run and journey mapping. This semantic review is mandatory until a separately verified trace importer exists. Keep model recognition, report availability and delivery completion as separate conclusions.

## Tests

The evaluator uses Python standard library only. Its regression tests are included in the backend suite: `python -m pytest apps/api/tests/ -v`. For a dependency-free focused run: `python3 -m unittest discover -s apps/api/tests -p test_acceptance_audit.py`. Tests protect missing-case denominators, critical repeat misses, cached repeats, source/context mismatches, unresolved precision, duplicate findings, temporal misses, stale-version clearance and delivery hash mismatches. They test the evaluator, not Gemini quality.
