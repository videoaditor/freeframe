# H3 durable PostgreSQL test exclusion — final local handoff, acceptance gate open

The independent review has finished and its two Important findings received one author RED/GREEN fix pass. Root's additional native-Workers transport blocker is fixed in the same pass. This is a testable local source handoff, **not unconditional integration/release approval**: the stronger absolute no-promotion invariant still has the combined-failure gap described first below. No coordinator waiver is assumed.

Full integration bases: Worker `1419482a7360d471002a03eb6fe2cde7d4a9b388`, FreeFrame `671fa0d8db521e2c1a4a57231f2dea3e01cc4859`. Reviewed pre-fix snapshots: Worker `38e3b246ee6a420423bc98df1a4261e6aa4fdea2`, FreeFrame `79626cb4fae346f7cf137580e00de083a74e98f4`. Final complete local package IDs are in sessions/H3.json and H3-CURRENT-FOLLOWUP.md; integrate those packages once, not superseded KV/source-only snapshots separately. Root alone integrates/deploys.

## Remaining acceptance gate — actual local reproduction

Confirmed canonical quiet/synthetic switches commit current physical-version exclusions and future-submission mode in PostgreSQL before any successful admin acknowledgement. Clearing mode never clears exclusions. These paths survive restart, missing previous KV, and stale normal watch flags.

However, consider: canonical test mode is enabled then explicitly cleared; a later natural version is submitted; a stale-positive quiet watch reaches review while the admission write is unavailable. Media review is expressly allowed to continue. The Worker retains a negative observation outside TimingRun, and recovery with that observation permanently excludes the version. **If that observation is also lost or returned stale-negative before recovery, no durable negative record exists.** The natural frozen source can then be admitted. Preserving a KV pending marker cannot prove absence of this combined failure.

The real Node resolver/HTTP adapter/FastAPI/PostgreSQL test emits this exact unresolved result in `review-node-pg-evidence.log`:

```json
{"remainingGate":"authority-outage-plus-lost-negative","first":{"authoritative":false,"provenance":"operator-test"},"lost":{"authoritative":true,"provenance":"natural"},"absoluteNoPromotion":false,"providers":0}
```

The same test then replays the retained observation through real HTTP, persists operator-test exclusion, and proves that a subsequent process with no previous state still gets operator-test. This contrast identifies the precise missing evidence; a passing characterization of the gap is not proof of the requested invariant. No actual provider run or production data is involved. Root must resolve this before live natural qualification. Closing it absolutely would require durable attempt/dispatch evidence before the media work or changing the requirement that review continues without authority; neither is silently introduced here.

## Final authority and behavior

Two additive fields: `UploadRequest.timing_run_purpose` is bounded JSONB containing canonical `quiet` and `provenance` flags (SQL NULL when inactive); `AssetVersion.timing_exclusion` is immutable first-negative exact P/U/share/A/V/version/source/server-clock evidence. Existing immutable submission origin and submitted_at remain untouched. Physical-version exclusion prevents cross-order laundering; active request mode protects future submissions despite stale KV flags.

Bridge-only timing-purpose locks sorted U then sorted V, merges partial flags against PostgreSQL, commits purpose and already-submitted exclusions atomically, and returns canonical flags for the persisted watch. Omitted flags cannot clear an independently active mode. `{quiet:false,provenance:null}` explicitly resets both future-mode flags. The private full `{purpose:...}` replacement remains supported. Ambiguous multi-order canonical states, malformed flags, missing authority or failure are rejected; successful test changes are never KV-only. Direct Admin-KV manipulation is outside the supported public contract.

Admission locks exact U then V, validates live exact source/parents and unique RequestUpload, and applies active durable purpose or observed same-version negative evidence. `timingObservation` retains purpose even without TimingRun, both before media work and on final admission failure. Legacy same-version attemptVersionId without timing is conservatively unknown. New physical V2 ignores V1 observations and must satisfy its own frozen source/admission. Unavailable authority creates no TimingRun; recovery uses actual retry clocks rather than fabricated earlier phases. Terminal authority failure suppresses completed eligible timing while media review remains available.

Fresh bounded runtime timing-status rechecks natural history and target against current PostgreSQL P/A/V/source hash, exclusions and mode. A later committed test switch disqualifies earlier cached natural history. Outage/malformed status withholds numeric calibration; source clocks may remain. A concurrent response linearizes at its DB read and is not retroactively retractable after a later switch. Offline raw exports are diagnostic and cannot establish current database eligibility.

Private stream wire is submission-provenance.v2; frozen stored source remains v1. Old5484 Worker rejects v2, new Worker rejects old API v1. GET-only service principal/key boundaries remain unchanged. New internal POSTs reuse the existing write-capable bridge bearer; no secret, account, role, Engine or UI change. Natural thresholds, cohorts and review content are unchanged.

The actual bundled transport uses native-compatible `redirect:manual`, rejects all non-2xx, and sends `Cache-Control:no-store`; no unsupported RequestInit.cache or redirect:error, and no compatibility-date bump. Nine native workerd cases at the date read from wrangler.toml (2024-09-23) exercise all three real adapters, actual loopback HTTP, 2xx/307/401, bridge headers, absent read-only key, and no credential forwarding to the redirect target. [Cloudflare Request documentation](https://developers.cloudflare.com/workers/runtime-apis/request/) describes manual redirect handling; installed workerd evidence governs this project's date.

## Migration and rollout

f1d8a10b2026 follows e1d8a10b2026. It adds the two purpose/exclusion columns, bounded JSONB purpose constraint and immutable exclusion trigger. The f1 revision is an unreleased local candidate; its final purpose column is JSONB, superseding the reviewed snapshot's String16 candidate. No deployed revision was rewritten here.

Every installation/reinstallation conservatively marks already committed versions unknown with reason pre-exclusion-authority. Otherwise dropping/readding exclusion authority would resurrect a previously tested natural source. This records missing authority rather than inventing test history, at the cost of losing old sample eligibility. Trigger forbids clearing/replacing exclusion and changing excluded physical identity. Real-data downgrade/reupgrade regression and full production Alembic entrypoint upgrade/rollback/reupgrade pass. Final reupgrade schema confirms JSONB purpose and head f1.

Root must resolve the remaining gate, migrate, deploy compatible API/Worker and qualify the combined branch before real future-order attestation. Stop natural eligibility and roll back Worker/API before downgrade. Downgrade loses mode/negative authority; reupgrade excludes all committed versions. The source-only5484 candidate and reviewed38e3 transport candidate are not rollout approvals. No production migration, attestation or rollout occurred here.

## Independent review and fixes

Reviewer `/root/h3_durable_exclusion_review` inspected full packages at the stated snapshots: 0 Critical, 2 Important, 0 Minor; verdict ready with fixes. Independently reran39 actual PostgreSQL and138 focused Worker cases. It declined production rollout, customer-purpose verification, timing/provider accuracy, Engine/UI, and offline current eligibility. It reviewed the supplied full-check record rather than claiming every command independently rerun.

| Finding | Author's one fix pass and evidence |
| --- | --- |
| Prior same-version attempt without TimingRun became natural on recovery | Exact-version observations survive independently of timing; explicit negative diagnostic retained; matching legacy attempt without timing -> unknown. Actual producer admission-outage/retry and V2 isolation RED then GREEN. Final-admission-outage case independently RED then GREEN; final state retains negative without stale KV reread. |
| Partial flags cleared database purpose but retained another active watch flag | Canonical flags share the existing purpose JSONB field; DB-locked patch merge returns canonical state. Both partial directions and future submission/admission tested against real PostgreSQL; actual admin caller starts with stale normal KV. Initial regression2PG failures and2admin failures then GREEN. |
| Root: transport unavailable in deployed Workers runtime | Native real-adapter workerd regression9 RED before changing transport,9 GREEN afterward. manual/non-2xx rejection and no-store header preserve privacy without unsupported RequestInit options. |

No second independent review or independent approval of the final fix delta is claimed. Coordinator Root owns final combined integration review. Initial post-fix integration exposed SQL JSON-null versus SQL NULL and missing-version comparison errors; targeted tests caught both and fixes retained all assertions. These intermediate failures are preserved in review-pg-first-green.log/review-worker-first-green.log.

## Verification and reproducibility

Evidence directory: `/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3/durable-test-exclusion/`.

| Check | Final result / evidence |
| --- | --- |
| Full Worker suite | 1751 passed /6 optional HTTP skipped;147 files passed/1skip; review-worker-final.log |
| Full API with opt-in real PG and actual Node HTTP | 714 passed /101 opt-in skipped /2 existing warnings; includes45 actual PG cases (28exclusion +17preserved source); review-api-full.log |
| Targeted true PG |45pass; both actual lock orders, restart/new connections, monotonic exclusion, V2/other orders, source immutability, auth/scope/privacy, partial canonical flags and future submission; review-pg-green.log |
| Actual Node/API/PG | Restart/stale KV and retained-outage exclusion proof, partial flag adapter, plus explicit combined-failure gap; review-node-pg-evidence.log |
| Native workerd |9pass after9RED; bundled real postTimingAdmission/setTimingPurpose/filterTimingEligibility; review-workerd-green.log (also in full suite) |
| Worker TypeScript |exit2 existing debt;161baseline/161current, zero added/removed file-code-message diagnostics; review-tsc-final-comparison.json |
| Frontend unchanged by this follow-up |608 tests/92files, production build/types/lint exit0 (existing warnings), web-tests.log/web-build.log/web-types.log/web-lint.log |
| Production Worker bundle |Dry-run exit0; review-final-dry-build.log; no deployment |
| Migration |Full entrypoint chain verified; final f1 rollback/reupgrade and JSONB schema verified; migration-full-chain.log/review-migration-down.log/review-migration-up.log/review-migration-schema.log |

Full API, Worker, native runtime and types were rerun after the relevant source changes. Frontend checks from the reviewed checkpoint apply to unchanged frontend source. Initial17PG missing-feature RED,6resolver/adapter RED, admin ordering/malformedquiet RED, migration-reinstall RED, and final-review RED logs remain available.

The first legacy projection test run lacked a stub for the new read-only status POST and may have attempted the default service domain with synthetic auth. No real credential was used, route was absent at the stated live base, and no accepted live operation/customer write is claimed. Fixtures now use local.invalid/wired boundaries before accepted verification. Do not describe that first run as wholly network-free.

Reproduce in the recorded checkouts with installed dependencies. The block creates its own disposable PostgreSQL and removes it on exit; all credentials are local synthetic test values. Docker Desktop must be running. No prompt or provider/live operation is expected.

```bash
set -e
H3_TEST_CONTAINER="freeframe-h3-verify-$(date +%s)"
docker run -d --name "$H3_TEST_CONTAINER" --tmpfs /var/lib/postgresql/data -e POSTGRES_USER=h3 -e POSTGRES_PASSWORD=local-test-only -e POSTGRES_DB=freeframe_h3_test -p 127.0.0.1::5432 postgres:16
trap 'docker rm -f "$H3_TEST_CONTAINER" >/dev/null' EXIT
until docker exec "$H3_TEST_CONTAINER" pg_isready -U h3 >/dev/null 2>&1; do sleep 1; done
H3_TEST_BIND="$(docker port "$H3_TEST_CONTAINER" 5432/tcp)"
H3_TEST_PORT="${H3_TEST_BIND##*:}"
cd /Users/alansimon/.codex/worktrees/autoreview-h3-parts/freeframe
TIMING_TEST_DATABASE_URL="postgresql://h3:local-test-only@127.0.0.1:${H3_TEST_PORT}/freeframe_h3_test" TIMING_WORKER_PATH=/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3/feedback-agent /Users/alansimon/Downloads/autoreview-continuity-overnight-2026-10-04/freeframe-venv/bin/python -m pytest apps/api/tests/ -q
cd /Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3/feedback-agent
PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH" npm test
```

## Rulings and limits

| Ruling | Reason / cost |
| --- | --- |
| Root plan-then-implement mandate authorizes inline local fixes | No repeated approval pause; cost is local rework, never external release. |
| Two additive fields, purpose now bounded canonical JSONB | Active future mode plus physical sticky exclusion; separate flags must not collapse on partial updates. Cost: migration and coordinated API/Worker contract. |
| Historical/reinstalled committed versions become unknown | Lost negatives cannot safely be assumed absent; cost: fewer samples, no retroactive qualification. |
| Visible unknown/test observations replay as durable negatives | Preserves available evidence without inventing clocks; cost: failed-authority attempts remain ineligible. |
| Combined authority outage plus lost observation remains an explicit gate | Cannot truthfully prove an event that reached no durable authority. No silent per-run waiver; Root must decide next design/requirement. |
| Fresh runtime eligibility is mandatory; offline export diagnostic | Later DB negatives invalidate positives; cost: bounded authority request and no numeric range during outage. |
| Native runtime governs transport at configured date | Node mocks missed unsupported options. Cost: local workerd regression, no date bump or new platform. |
| Existing bridge write auth only; GET-only key remains readonly | No new account/role/secret; operator without existing write authority cannot attest. |
| Genuine customer-purpose verification remains operator/Root-owned | Wrong attestation could contaminate future samples; no customer authenticity or live accuracy claim. |
| Privileged DB tampering outside app boundary | Administrator forgery invalidates authority; no new trust role introduced. |
| No production timing/load/provider/Engine/UI acceptance | New Engine remains OFF; no paid calls/deploy/merge/push/live attestation. |

Existing Trello card https://trello.com/c/HaBvLzZK and AutoReview session9ca4990a-3262-4e26-a26c-57f2d38f3929 remain coordinator-owned. Software automatic media acceptance is unsupported; no false pass or new card/session. Own disposable test resources are cleaned after final evidence; other sessions' resources/worktrees remain untouched.
