# AutoReview launch-gap candidate — 2026-10-01

**Decision: local integration candidate; broad launch NOT accepted.** No production deployment, Whop Base URL change, landing publication or automatic rollout re-enable occurred in this session. The original chat **Rebase and verify FreeFrame PR 31** owns production and STOP 2. Its last read status was runtime rollback after a Gunicorn appuser-home permission startup failure; additive schema retained. Re-read that chat before planning activation; this is historical session evidence, not a new live inspection.

Drafts: [FreeFrame #34](https://github.com/videoaditor/freeframe/pull/34), [Review Worker #72](https://github.com/videoaditor/feedback-agent/pull/72), [Pages #483](https://github.com/videoaditor/aditor-ops/pull/483). All are review candidates held behind the remaining gates.

## Candidate provenance

| Repository | Accepted source base | Candidate branch / implementation |
| --- | --- | --- |
| FreeFrame | `828812f` (merged PR31, not currently accepted production runtime) | `codex/autoreview-launch-gaps`, implementation through `cb13c06`; later commits contain acceptance/docs and migration-backfill check |
| Review Worker | `1f88887` | `codex/autoreview-version-evidence`, `53ee292` |
| Pages | `ba3c2b9` | `codex/autoreview-member-entry`, `c2d314b`; export from previously approved landing source `d20fca6` |

Ordinary editor behavior was selected from FreeFrame `0910256` and Worker `9fb6c09`, then adapted and reviewed. Iterations, browser review preparation, email project-history and timing/performance modules were excluded. No new dependencies. Own worktrees are under `/Users/alansimon/.codex/worktrees/autoreview-launch-gaps/`; foreign working changes were preserved. No production image IDs exist for these candidates; the rollout owner must record actual built image digests before switching ingress.

## Automated verification

| Check | Actual result |
| --- | --- |
| API including true PostgreSQL | **400 passed, zero skipped** on a dedicated loopback PostgreSQL 16 database; notification DDL opt-in enabled |
| Request concurrency | Two real sessions: complete/finish serialize; finish/initiate serialize; exact completion map persists; new uploads rejected with 409 |
| Failed current delivery | Submitted failed V2 remains unavailable after stale-upload reaper; old V1 clearance cannot finish |
| Cancellation | Empty canceled asset soft-deleted; actual share listing omits it; canceled revision retains delivered asset; unique version numbers never reused |
| Migration | One head `d0e1f2a3b4c5`, parent `c9d0e1f2a3b4`; local upgrade applied. Real PostgreSQL seeded backfill includes processing/ready, excludes uploading/failed |
| FreeFrame frontend | **432 tests passed**, isolated production build and typecheck passed; lint passed with existing warnings and imported raw-image advisory warnings. Dependencies installed frozen in the own checkout after borrowed rollout modules disappeared |
| Review Worker | **1,204 tests passed**; typecheck FAILS with **158 existing diagnostics** on both base and candidate. Sorted diagnostic messages match exactly. This is an unresolved rollout gate, not a green check |
| Pages | **1,526 tests passed**, typecheck passed, candidate export built, member/team entry contract passed |

Meaningful red/green regressions include missing editor endpoints, V2 identity despite a renamed file, missing/malformed/stale version evidence, unverified object size, Whop HTTP recovery, aborted share phantom, failed-video replacement and stale reaper fallback. Fresh independent review found the final three cases; all were fixed and their regressions rerun. The existing n8n notification test assigned autocommit to SQLAlchemy's pool proxy instead of the driver connection; it now uses the driver and restores its original mode. Application notification behavior was unchanged.

## Browser evidence and its limits

All screenshots below use **synthetic local data**, a real native video player and simulated review HTTP responses. They prove presentation and local interaction only. Date: 2026-10-01, synthetic anonymous Editor role, FreeFrame implementation through `fcc72a1`, plus failed-processing replacement viewed at `cb13c06`. Browser widths 1280px and 390px (phone height844px); Light/Dark viewed. The fixture is ignored and excluded from production builds.

| URL / case | Expected and observed | Evidence |
| --- | --- | --- |
| `http://localhost:3146/r/launch-check?state=held&theme=light` | Video + exact current feedback, explicit revision action, readable mobile layout | [desktop light](images/autoreview-launch-20261001/editor-desktop-light.jpg), [desktop dark / corrected contrast](images/autoreview-launch-20261001/editor-desktop-dark.jpg), [phone light](images/autoreview-launch-20261001/editor-mobile-light.jpg), [phone dark](images/autoreview-launch-20261001/editor-mobile-dark.jpg) |
| `?state=board&theme=light` | Unavailable stays in In review; correct folder URL retained; Ready and human approval explained | [owner board](images/autoreview-launch-20261001/owner-unavailable-desktop-light.jpg) |
| Same fixture, v1 history selected | Historic media/notes identified as reference; current v2 notes do not appear | [history](images/autoreview-launch-20261001/editor-history-desktop.jpg) |
| Revision action | Opens uploader for selected asset despite changed filename; returns to prior feedback | [revision + corrected dark accent contrast](images/autoreview-launch-20261001/revision-mobile-dark.jpg) |
| `?state=unavailable&theme=dark` | File-safe unavailable copy + Check again; no completion claim | [unavailable](images/autoreview-launch-20261001/review-unavailable-desktop-dark.jpg) |
| `?state=clear&theme=light` | Persisted synthetic finish response precedes celebration; reload returns completed; animation can pause | [completed / paused](images/autoreview-launch-20261001/completed-motion-paused.jpg) |
| Base `828812f`, `http://localhost:3147/r/launch-check?state=401` | Original generic retry | [before](images/autoreview-launch-20261001/whop-before-desktop-light.jpg) |
| Candidate missing-header `/whop` and `?state=409&theme=light` | Correct Open in Whop link; team sign-in and explicit no automatic account linking | [missing context](images/autoreview-launch-20261001/whop-missing-desktop-dark.jpg), [conflict mobile](images/autoreview-launch-20261001/whop-conflict-mobile-light.jpg) |
| `http://localhost:3148/suite/autoreview/` | Whop member action and separate Team sign-in; existing design preserved | [candidate footer](images/autoreview-launch-20261001/landing-footer-mobile.jpg) |

Self-critique: mobile filename truncation is intentional and leaves version selection accessible; no page-level horizontal overflow was observed. Imported dark accent buttons initially used white text; changed to existing theme inverse token. Required actions use 44px minimum targets. Animation pause was exercised; reduced-motion CSS remains present, but a native reduced-motion preference was **not** browser-emulated or device-tested. Failed-processing replacement is covered by component + page tests and was then viewed on the restarted local server: [failed V2 / replacement action](images/autoreview-launch-20261001/failed-replacement-mobile-dark.jpg). The action opens the selected asset uploader. Browser retries initially failed while borrowed dependencies had disappeared; dependencies are now installed in the own checkout.

## Real acceptance still required — original rollout owner

These are **pending**, not failed or passed by local fixtures. Use only designated synthetic pilot data and record each role, URL, build digest, date, expectation, observed result and screenshot privately. Do not place account PII/tokens in public PRs.

| Real case | Required evidence |
| --- | --- |
| Whop Owner A / repeated entry | Experience injects valid header, `/whop/session` succeeds, same Suite identity survives reload; actual pilot email conflict either absent or safely excluded |
| Owner A → Editor → delivery | Choose brand/rules; create real text/PDF/link briefing; copy `/r/{token}`; separate editor browser uploads V1, sees real must-fix, uploads renamed V2 to same asset; current V2 reviewed and finish persists V2 |
| Owner folder / share / download | Ready applies to exact current evidence; Preview opens `/projects/{project_id}?folder={folder_id}`; Share opens `/share/{review_share_token}`; viewer/download bytes match confirmed version. Human Brand approval stays separate |
| Whop Owner B / telephone | A's brands/rules/requests invisible to B, direct foreign IDs denied; account switch and delayed 401 preserve correct identity; real phone reload, native reduced-motion preference |
| Interruptions / backward compatibility | Expired/revoked editor link410, membership revocation denies Owner, bridge outage keeps files and unavailable/no finish; staff/login/share/handin/Trello/n8n smokechecks; unresolved409 owners excluded |

Broad launch needs all cases green plus resolution of the Worker typecheck gate. A limited pilot requires named accepted accounts and an explicit rollout decision. This integration does not authorize either outcome.

## Deployment order and rollback contract

1. Original rollout owner reads current runtime, backup and paused automation status. Resolve candidate startup/appuser-home failure before ingress. Keep existing deployment automation paused until convergence and smokes pass.
2. Deploy compatible Review Worker **first**: `/api/v1/assets` must return reviewed byte `version_id`; request aggregate outage must return unavailable. Reuse existing bridge credentials privately.
3. Apply additive FreeFrame migration to `d0e1f2a3b4c5` before the new API. Deploy API and Celery on the same candidate at a safe task boundary; never interrupt active transcoding. Existing tasks continue passing immutable asset/version IDs. No task protocol change or performance feature is required.
4. Deploy compatible Web after API/Worker; record image digests, health and existing staff/share/handin smokes. STOP 2 Whop Base URL is `https://feedback.aditor.ai/whop`; the original rollout chat owns approval and switching. Perform the real sequence above before releasing the Pages member-entry candidate.
5. After successful real acceptance, publish existing Pages candidate and verify links. If any gate fails, roll ingress/runtime back to recorded compatible images. Keep additive schema and all newer customer writes; no Alembic downgrade or database restore over writes. Do not move stable/latest or cut tags.

Required configuration names: `SUITE_URL`, `WHOP_APP_ID`, `API_INTERNAL_URL`, `NEXT_PUBLIC_API_URL`, `REVIEW_BRIDGE_URL`, `REVIEW_BRIDGE_SECRET`; retain existing `INSTANCE_WIDE_PROJECT_ACCESS` staff-only semantics and current customer controls. Use approved rollout values, not historical empty values in older docs. No secret values are recorded here.

## Integration decisions and consequences

| Decision | Reason / limit if wrong |
| --- | --- |
| Target accepted merged source `828812f`, not rolled-back runtime | Matches reviewed launch source; live qualification still needs the actual runtime comparison |
| Port ordinary editor only; omit iterations/history-verification/timing | Avoids new launch dependencies; optional cross-project history is absent |
| Repair preexisting retention FK cleanup | True PostgreSQL exposed request rows blocking purge; deletion remains retention-owned, application soft delete preserved |
| Keep existing Worker type errors as a visible gate | Candidate adds no diagnostic messages; unrelated baseline defects can still hide runtime issues, so broad launch remains blocked |
| Export from accepted landing `d20fca6` on Pages main | No design rebuild or publication; regenerate if approved landing source changes before acceptance |
