> FOLLOW-UP: Root rejected the per-run test exception; see 2026-10-08-h3-durable-test-exclusion.md for the durable negative fix and its current verification. This source-freeze report is historical.

# H3 PostgreSQL submission provenance — local review handoff

Supersedes rejected KV-authority commits 220e3bd/a95ea7d. Integration bases: Worker 1419482a7360d471002a03eb6fe2cde7d4a9b388 and FreeFrame 671fa0d8db521e2c1a4a57231f2dea3e01cc4859. Final full commit IDs are in the external sessions/H3.json manifest, avoiding a report self-hash. Existing H3 worktrees, project card https://trello.com/c/HaBvLzZK and briefed AutoReview session 9ca4990a-3262-4e26-a26c-57f2d38f3929 are reused. Root alone integrates, attests and deploys.

**Status:** implementation and local verification complete for immutable submission origin. Independent review found no verified Critical/Important/Minor defect within that scoped contract. **The older prior-test-observation exclusion remains an unresolved acceptance gate; this is not unconditional merge or live natural-traffic approval.** No deployment, push, live attestation, customer write or provider run occurred.

## What changed

Root reproduced same-version unclassified-to-natural promotion using successfully stale-negative KV reads. Cloudflare documents cached negative lookups at https://developers.cloudflare.com/kv/concepts/how-kv-works/#consistency. KV cannot prove absence of earlier evidence. Worker now ignores KV intent/history when determining submission origin.

FreeFrame has two nullable server-owned JSONB columns: UploadRequest.timing_natural_intent and RequestUpload.timing_provenance. The existing UploadRequest lock serializes operator attestation against accepted submission; an AssetVersion lock protects competing requests for one physical version. Both timestamps use PostgreSQL clock_timestamp() after locking. First completion freezes exact P/U/share/A/V/version_number/submitted_at/provenance in the submission transaction. Retry preserves them. Database triggers reject changing committed identity, time or provenance, and reject rewriting an existing intent. A committed historical NULL stays unknown. Internal adoption records unknown. Ambiguous RequestUpload sources yield no private timing context.

GET/POST /internal/review/timing-intent/{U} reuses existing write-capable bridge bearer auth. The separate GET-only X-API-Key remains read-only; normal owner JWTs and guest links cannot attest. No secret, account, role or permission is created or widened. GET is read-only. Explicit verified POST accepts only project/share/verified=true and assigns server time; caller timestamps/backdating are forbidden. Matching retries preserve intent; conflicts refuse. Exact active project/folder/public standing share/request scope is checked; only complete-ad requests qualify. Responses are private, no-store.

Private timing_context carries autoreview.submission-provenance.v1 frozen source evidence. Worker validates P/U/share/A/V/clock/version_number/schema/hash before creating a TimingRun. Missing, old, corrupt or unavailable authority creates no TimingRun while media review continues when media is available. Frozen unclassified/unknown source may produce non-calibrating diagnostics. Recovery records current attempt phases; it never reconstructs omitted earlier clocks. Public timing omits origin/U/hash. Cohort gates, provider requests, Engine selection and review content are unchanged.

## Compatibility gate: test-purpose exclusions

Current quiet/operator-test/synthetic flags exclude the attempt in which they are observed. A PG-natural version reviewed quietly may be operator-test on attempt 1 and natural on attempt 2 after quiet is removed. Frozen PostgreSQL submission origin does not change, but run classification can change. KV watch flags also lack linearizable freshness.

The older docs/superpowers/specs/2026-10-08-h3-natural-attestation.md explicitly prohibited retrospective promotion after prior unknown/test observations. The PG architecture replacement did not explicitly revoke that test-observation invariant. H3 therefore does not represent per-run exclusions as a coordinator-approved narrowing. Coordinator Root must decide whether per-run purpose satisfies the intended requirement, or request a durable purpose/exclusion authority before live natural qualification. No speculative additional authority platform or schema was added here. A local “previous state” check alone would not solve stale KV negatives.

This gate does not weaken the fixed source guarantee: a historical unclassified/unknown submission cannot become natural after later attestation, cache recovery or API recovery. Missing authority emits no earlier evidence to reclassify. The scoped reviewer verdict does not prove the stronger “ever tested means permanently excluded” behavior.

## Verification

| Check | Result and evidence |
| --- | --- |
| Root stale-negative reproduction | Rejected pinned checkout remains RED. Import-only copy against current code GREEN: sameVersion=true, persistedUnknownRecords=1, first=unclassified, second=unclassified, violation=false. Original Root file untouched. root-repro-current.ts / root-repro-green.log. |
| Actual disposable PostgreSQL | 17 passed, including both real row-lock orders with observed lock waits, V1 unknown/V2 natural, retry, intent/submission rollback, immutable legacy NULL/time/evidence, same/other-request ambiguity, adoption, auth/backdating and guest privacy. ff-pg.log. |
| Full API | 686 passed / 101 opt-in skipped / 2 existing deprecation warnings. TIMING_TEST_DATABASE_URL enabled the 17 PG cases; other live-DB suites were not configured. ff-final-api.log. |
| Production migration entrypoint locally | Complete Alembic chain upgrade to e1d8a10b2026 passed in a separate disposable DB. Downgrade to d5d7e10b2026 and reupgrade passed, head and both columns checked. migration-full-chain.log / migration-rollback-reupgrade.log. |
| Worker | Authority/CLI RED 20 failed, 5 passed, then 96 targeted passed including the real sweep; full 1725 passed / 6 optional HTTP skipped, 144 files passed / 1 skipped. worker-red.log / worker-green.log / worker-full.log. |
| Worker TypeScript | 161 baseline and 161 current diagnostics, no added/removed file-code-message diagnostics; both exit 2 existing debt. tsc-comparison.json. |
| Frontend | 608 passed in 92 files; build, types and lint exit 0 with existing untouched warnings. web-tests.log / web-build.log / web-tsc.log / web-lint.log. No UI change. |
| Worker production bundle | npm run deploy -- --dry-run --env production completed locally, explicitly exited without deploying. worker-dry-build.log. |
| Independent review | h3_postgres_final_review independently ran 27 API checks including all 17 PG cases, plus 96 Worker checks: all passed. Reviewed full base-to-head patches 671fa0d..ac441fd and 1419482..3ef265b. Final cleanup after review affects docs, changelog placement, a trailing blank line and commit packaging only. |

Evidence directory: /Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3/postgres-attestation/. The initial PG RED had seven failures (HTTP 404 versus expected new endpoint, and missing helpers/schema); a synthetic invalid email was corrected before behavioral RED claims. Initial full API failures were four mocks lacking the new version-lock query plus the expected migration-head assertion; fixtures/head were corrected without weakening behavior assertions. Obsolete KV-authority tests were replaced by durable-authority tests. Migration environment setup initially lacked existing Redis/JWT configuration; corrected locally before accepted entrypoint verification. No live secret was loaded or real customer JSON fabricated. Automatic media review cannot validate a software patch; no media-review pass is claimed.

## Migration and operator rollout

Migration e1d8a10b2026 follows sole head d5d7e10b2026. Nullable additions have no backfill. Root must resolve the compatibility gate, then migrate, deploy compatible API, deploy compatible Worker, verify the full package, and only then consider attesting an actual checked order. Old API lacks authority so the new Worker omits timing. Old Worker 1419482 cannot establish natural origin automatically. New Engine stays OFF.

Rollback Worker/API before downgrade. Downgrade removes only these two timing fields and their protection functions/triggers, losing intent/evidence. Reupgrade leaves committed versions unknown. No production migration was performed.

The absolute dry-run-only operator command is in docs/review-timing.md. It requires existing FREEFRAME_BASE/FREEFRAME_BRIDGE_SECRET, never Cloudflare writes. Verified input contains only tenant_id/upload_request_id/share_token. Default is GET; apply additionally requires --apply --customer-order-verified. An uncertain POST is inspected using GET before retry. No dry-run or apply against live service was executed.

## Rulings made and their costs

| Ruling | Basis and cost if wrong |
| --- | --- |
| Proceed inline without another approval pause | Root explicitly authorized a precise plan then implementation. Cost: local rework; no external action authorized by this ruling. |
| Reuse existing bridge write auth, preserve GET-only key | Existing internal POST operations establish that boundary. If Root lacks existing operator authority, future attestation must be withheld; no rights are widened. |
| No authority means no timing; historical/adopted source stays unknown | Avoids later cache-based source promotion. Cost: fewer observations and eligible samples. |
| Separate spec/gate was extracted after first implementation | Architecture was written before code in the plan, but a separate pre-code spec was not present. Process deviation is recorded honestly; cost: weaker separation of design and execution. |
| Prior-test invariant remains open, not silently waived | Reviewer source-contract verdict does not establish sticky purpose exclusion. Coordinator Root has not accepted a narrowing. Cost if released without resolution: a later attempt of a previously tested PG-natural version could count as natural. |
| KV watch freshness is outside the proven source guarantee | Immutable PG origin does not make KV purpose flags linearizable. Cost: changed test flags may be observed late; live qualification must account for this gap. |
| Production accuracy/load/rollout were not judged | No live or paid runs were authorized here. Cost: no accurate live ETA or production qualification claim. |
| Real customer authenticity remains operator-owned | Code validates identity, credentials and time, not customer intent. Cost of an incorrect attestation: future samples may be mislabeled. |
| Privileged database forgery is outside this service boundary | Ordinary API forgery, mismatched evidence and protected committed updates were checked; a DB administrator can change the authority itself. Cost: trusted administrator compromise invalidates provenance. |

No deferred polish minors. The reviewer initially described the agent author's per-run interpretation as “Root explicitly retains”; this report corrects that attribution: coordinator Root has made no explicit acceptance ruling. The compatibility gate remains open. The required independent review is complete; no second review or repeated suites are claimed for documentation-only closure.

Canonical doctrine lesson is recorded in the scoped spec rather than editing another repository. Existing branches/worktrees are kept for Root's review. Only this plan's scratch ledger is archived and its own disposable PostgreSQL container removed. Root owns combined-branch tests, acceptance, integration and release; this local handoff does not enable numeric production ETA.
