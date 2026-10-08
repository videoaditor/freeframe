# H3 durable admission before dispatch — focused local follow-up

Root's 2026-10-08 pre-dispatch decision supersedes the historical rule that review proceeds during an authority outage. A potentially natural physical version now starts new media/provider/comment work only after exact-version admission or permanent negative proof has committed. This closes the previously reproduced local outage-plus-lost/stale-negative-observation dispatch path without weakening absolute no-promotion. Root owns combined integration, genuine customer attestation and rollout; live timing accuracy remains unqualified.

This focused follow-up preserves Worker base `1d3b6353ee95bf23bf09137c6e9dfea833719043` (full integration parent `1419482a7360d471002a03eb6fe2cde7d4a9b388`) and FreeFrame base `10c236b507653a7bfccfc807294b0b81fc55a369` (parent `671fa0d8db521e2c1a4a57231f2dea3e01cc4859`). Exact new local commits and source ownership are recorded in `/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3.json` and `H3-CURRENT-FOLLOWUP.md`. Apply each base and its focused follow-up once; do not replay superseded KV-only packages. Both worktrees retain `codex/autoreview-h3-postgres-attestation`.

## Behavior and storage

The existing sweep obtains metadata, validates current admission, then starts actual scoring counters and clocks. Unknown/unavailable/old/malformed authority waits in the existing asset record and scheduler, with 30/60/120/240/300-second bounded backoff. The additive `admissionWait` KV JSON member is scheduling state, separate from actual attempt IDs, retry counts and timing observations. Waiting consumes no scoring attempt, no media/provider/comment dispatch, no invented analysis clock or ETA. A prior actual scoring attempt retains its count. Missing current version metadata waits for new work. Completed reviews with unchanged listed version count remain completed during metadata loss and do not rescore on recovery; a confirmed newer version still waits for its own authority. Real scoring errors after recovery persist the current failure stage and retain visible retries/terminal failure.

The narrow bridge-only `POST /internal/review/timing-legacy-exclusion` reuses `autoreview.timing-admission.v1` and existing `AssetVersion.timing_exclusion`. It locks exact live V, verifies live project/asset/folder/share scope, and commits before responding. Allowed negative proof is an existing permanent exclusion, one valid immutable unclassified RequestUpload source, or a ready legacy version with no RequestUpload source. The latter receives unknown exclusion with truthful null request/submission fields before media work; later adoption cannot promote those bytes. A natural, pending, corrupt or ambiguous source without an existing negative returns409 and waits. Missing private metadata alone is never negative proof. The V-only path takes no U lock, avoiding U/V lock inversion with existing U->V submission/admission. No DB columns, migration, queue, provider, role or secret were added.

Legacy proxy calls now include admitted exact V and require the response to echo it. Missing/mismatched proxy identity falls back to the already pinned original. Actual worker/pickup clocks start after admission acknowledgement; earlier waiting phases are not fabricated. Terminal admission loss still leaves completed feedback readable while withholding eligible completed timing. Existing fresh eligibility filtering, canonical partial quiet/provenance JSONB flags and native workerd manual-redirect/no-store transport remain intact at compatibility date2024-09-23. New Engine remains OFF and unchanged.

## RED/GREEN and actual integration evidence

Evidence directory: `/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3/`.

| Contract | Evidence |
| --- | --- |
| Actual baseline producer dispatched during admission outage | `predispatch-red-worker.log`; current focused producer gate GREEN in `predispatch-green-worker.log` |
| Narrow legacy authority did not exist | `predispatch-red-api.log` route404; eight true PostgreSQL cases GREEN in `predispatch-green-api.log` |
| Legacy adapter and pinned proxy identity | `predispatch-red-legacy-worker.log`; current full/focused Worker suite |
| Waiting must not borrow prior analysis/failure clocks | `predispatch-red-wait-projection.log`; `predispatch-green-wait-projection.log` |
| Actual Worker1d3b6353 over HTTP/FastAPI/PostgreSQL dispatched during PG disconnect | `predispatch-red-real-http-pg.log` craft.calls expected0, actual1; current integration GREEN in `predispatch-green-real-http-pg.log` and final API log |
| Completed review regressed to pending on stream503/missing V | `predispatch-red-completed-metadata.log` two expected assertion failures; `predispatch-green-review-fixes.log` |
| Recovered provider error stayed waiting | `predispatch-red-recovery-failure.log`; current producer test reaches visible retry then failed after3 actual attempts |

`test_actual_worker_producer_http_pg_disconnect_recovery_and_sticky_exclusion` runs the actual Worker cron through Node/Vitest against a local FastAPI server with the actual private authority router and a disposable PostgreSQL16 database. Outage executes `pg_terminate_backend(pg_backend_pid())`; this is real connection loss, not an admission response stub. Metadata is produced with the real private source helper; only public media/comment fixtures and the paid craft boundary are synthetic/local. The test proves zero media/provider/comments during outage with quiet=true, loss of wait state plus stale normal watch, retained older negative/one actual prior attempt, eleven additional authority failures without scoring charge, bounded retry, useful recovery, committed sticky test exclusion after cache/history loss, independent natural V2, and terminal PG disconnect suppression. Advancing the test clock400ms at the first successful HTTP admission ACK proves actual clocks start afterward. No production/provider endpoint or real media is used.

The former helper characterization that accepted the combined-failure gap was replaced by this actual producer regression; other resolver restart/stale-cache/partial-purpose coverage remains.

## Independent review

Reviewer `/root/h3_predispatch_review` read both diffs and independently ran219 focused Worker tests. It reproduced two Important status regressions in the actual cron/public status: completed reviews became pending during metadata outage, and recovered failures inherited waiting. Both received narrow author RED/GREEN fixes. The same reviewer independently re-reviewed those fixes and reran223 tests across five files: both findings closed, no residual verified finding in those deltas, ready for scoped local handoff. Full reviewer record: `predispatch-independent-review.md`.

The reviewer found no V/U inversion, no negative legacy grant from missing metadata alone, no scoring charge during authority waiting, no V1-to-V2 contamination or moving proxy bytes, and no regression in terminal/transport/canonical-flag behavior. This does not attest production/customer purpose, actual provider quality, Engine integration or live ETA accuracy.

## Final verification

| Check | Result / evidence |
| --- | --- |
| Full Worker, final source after both review fixes |1764 passed /7 optional HTTP skipped;147 files pass/2skip; exit0; `predispatch-worker-final-serial.log` |
| Full API with opt-in true PG and actual Worker HTTP |723 passed /101 opt-in skipped /2 existing warnings; includes54 true PG cases; exit0; `predispatch-api-final-rerun.log` |
| Focused actual PG |54 passed before final two Worker status fixes; `predispatch-api-pg-focused.log`; all54 rerun in final full API including actual Worker producer |
| Native workerd real transport |12 tests pass, all four actual adapters at2024-09-23; included in final Worker suite |
| Independent focused re-review |223 tests/5files pass; both Important findings closed; `predispatch-independent-review.md` |
| Worker TypeScript |exit2 existing161 baseline/current diagnostics, zero added/removed file-code-message entries; `predispatch-tsc-final.log`, `predispatch-tsc-final-comparison.json` |
| Web tests/build/types/lint |608 tests/92files; all four commands exit0, existing warnings; `predispatch-web-test.log`, `predispatch-web-build.log`, `predispatch-web-tsc.log`, `predispatch-web-lint.log` |
| Final production-config Worker bundle |dry-run exit0; `predispatch-dry-bundle-final.log`; no deployment |
| Diff hygiene |both worktree `git diff --check` exit0 |

The first post-review full Worker run had one5-second timeout in existing `bound-sweep.test.ts`128-finding publication. An isolated unchanged-file rerun passed17tests. A four-worker rerun during local VM startup had that timeout plus a native admission timeout and a following legacy request-count mismatch after the timed-out request completed. The final entire suite ran serially with a30-second per-test ceiling and passed1764; no assertion or source timeout configuration was relaxed. All unsuccessful logs remain (`predispatch-worker-final.log`, `predispatch-worker-final-rerun.log`, `predispatch-bound-recheck.log`).

The first final API rerun found the local OrbStack daemon/database unavailable:669 passed/101 skipped/54 setup connection-refused errors (`predispatch-api-final.log`). Reopened the existing local OrbStack app and recreated only the owned disposable PostgreSQL container, then reran the entire API successfully against its new loopback port. Other containers were not edited or removed. The owned PG and baseline scratch were removed after final verification. The first dry-bundle wrapper could not source the historical credential file; a later explicit local dry-run succeeded without credentials and performed no deployment.

The final verification retry record is preserved, including any environmental/timeout run, rather than hidden by the successful rerun. TypeScript retains the existing161 diagnostics with zero added/removed file-code-message entries; it is not claimed clean. No frontend source/style/component changed, so no new visual acceptance is claimed.

## Reproduce locally

Docker/OrbStack must already be available. This creates/removes only its named disposable PostgreSQL; local synthetic credentials, no prompts, paid model calls or production operations. Existing dependencies and the recorded Python venv/Node22 paths are used.

```bash
set -e
H3_TEST_CONTAINER="freeframe-h3-predispatch-verify-$(date +%s)"
docker run -d --rm --name "$H3_TEST_CONTAINER" --tmpfs /var/lib/postgresql/data -e POSTGRES_USER=h3 -e POSTGRES_PASSWORD=local-test-only -e POSTGRES_DB=freeframe_h3_test -p 127.0.0.1::5432 postgres:16
trap 'docker rm -f "$H3_TEST_CONTAINER" >/dev/null 2>&1 || true' EXIT
until docker exec "$H3_TEST_CONTAINER" pg_isready -U h3 >/dev/null 2>&1; do sleep 1; done
H3_TEST_BIND="$(docker port "$H3_TEST_CONTAINER" 5432/tcp)"
H3_TEST_PORT="${H3_TEST_BIND##*:}"
cd /Users/alansimon/.codex/worktrees/autoreview-h3-parts/freeframe
TIMING_TEST_DATABASE_URL="postgresql://h3:local-test-only@127.0.0.1:$H3_TEST_PORT/freeframe_h3_test" TIMING_WORKER_PATH=/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3/feedback-agent PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH" /Users/alansimon/Downloads/autoreview-continuity-overnight-2026-10-04/freeframe-venv/bin/python -m pytest apps/api/tests/ -v
cd /Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H3/feedback-agent
PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH" npm test -- --maxWorkers=1 --minWorkers=1 --testTimeout=30000
```

Root integrates/reviews the full combined branch and chooses deployment/attestation. This follow-up performs no push, merge, release/tag, deployment, live attestation, customer/role/quota write, paid provider call, Engine change or outgoing app-chat message. Natural cohort thresholds5/30/30+10/20% remain unchanged. Genuine eligible completed production runs are still required before any live ETA accuracy claim.
