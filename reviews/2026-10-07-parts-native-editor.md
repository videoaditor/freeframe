# Parts and native editor integration qualification

The candidate combines Parts PR46, the H3 Parts timing adapter, current released H1/H2 source/timing/campaign behavior, and staff Trello snapshot PR68 at `0e973cd`. Matching reviewer code integrates Worker PR73; Mixer is the unchanged PR57 head `b0e4e653`. These are coordinated integration candidates, not a production rollout.

Internal complete-ad Handin now returns the customer share plus a native `/r` editor for the existing folder and exact versions. Parts retain their resumable internal Handin workspace and native `/r` review. The API owns canonical link origins. Explicit legacy migration binds exact live scope and durable PostgreSQL identity; cache loss cannot reopen revoked assignments. Native source/final reviews consume one saved briefing, brand context and checklist through the private current-version/recipe attester. Ambiguous Handin retries retain their UUID and frozen title, even after card rename/outage. Original MOV/WebM downloads retain their actual name/container. Celery receives shutdown signals directly and has bounded drain grace periods.

## Verification

| Gate | Result |
| --- | --- |
| API, all PostgreSQL opt-ins enabled | **733 passed**, zero skips; two existing deprecation warnings; dedicated `h4_next_h2_test` DB at forward merge migration `d5d7e10b2026` |
| Web | **604 passed / 92 files**; production build, TypeScript and lint passed; existing image lint warnings |
| Worker | **1,559 passed / 138 files**, zero skips, including six actual HTTP saved-context tests; isolated bridge-server fixture excluded |
| Worker static/build | Wrangler dry-run passed; TypeScript reports exactly the same **161 existing diagnostics** as main `2d60c5e`, no added diagnostics; full typecheck is not claimed green |
| Mixer PR57 | **180 tests passed**, including actual FFmpeg ordered media and private original contracts |

The independent reviewer found no remaining P0/P1/P2 issues after verifying frozen source/rubric propagation, exact live legacy scope, DB claim/read authority, metadata preservation, stable retry identity, and the cache/registration races. It independently passed 86 targeted Worker tests and 1,553 full-suite tests with seven optional/fixture skips; the parent separately enabled the six HTTP checks above. Both code diffs passed `git diff --check`.

## Runtime evidence and boundaries

The isolated stack used real PostgreSQL, Redis, Celery, multipart S3 transfer/storage, private Mixer TLS/SQLite, FFmpeg render/import/transcoding and browser playback. Deterministic model answers, synthetic Trello metadata and explicit fixture media DNS were the only remote substitutions. Production SSRF/authentication guards were preserved. No real provider calls, paid account acceptance or external Trello/Slack/email writes were performed.

1. Three uploaded source videos produced two distinct final files. A fresh native `/handins` request reused its exact ID/token on HTTP replay and rejected a changed card under the same UUID with 409. All three source audits and both full audits required saved context and shared identical frozen binding metadata.
2. A controlled provider outage preserved the uploaded originals and recovered without reupload. A separate controlled failure left one output usable while Hook 1 was replaced with V2; only its dependent combination changed. Browser retry after a Mixer outage restored both outputs, preserving Hook 2's output identity/version. Reload, old-version reference and keyboard seeking worked.
3. The final production bundle showed two delivered files, playable 5.038-second media, correct yellow-hook → blue-body order and version history. The mobile fixture at 384 px had no horizontal overflow. Internal Handin opened its real resumable upload workspace; complete-ad Handin exposed the customer share and native review action.
4. Actual Celery PID1 SIGTERM checks passed for worker and beat. An in-flight task on the production `email_high,email_low` queue configuration finished during warm shutdown with exit 0. Mixer restarted with six persisted jobs and returned the same 99,203-byte output and SHA-256 through certificate-verified TLS.
5. The fresh internal Parts batch retained both checked final files but correctly reported **delivery unavailable** because the fixture denies external Trello writes. Live Trello delivery, real model quality/latency, paid Whop/customer acceptance and production deployment remain unverified. No false live media review pass is asserted. The existing project review session/card remain coordinator-owned.

Private raw logs and synthetic capability URLs remain in the local H4 evidence folder. Only synthetic screenshots and this sanitized report are committed.

## Screenshots

Before: [existing Handin](../docs/design/handin-evidence/before-handin.jpg). After: [complete Handin result](evidence/h4-next/internal-handin-result.png), [built Parts result](evidence/h4-next/parts-final-built-desktop.png), [built final player](evidence/h4-next/parts-final-built-player.png), [internal Parts start](evidence/h4-next/parts-internal-built-start.png), [mobile](evidence/h4-next/parts-mobile.png), [recoverable outage](evidence/h4-next/parts-outage-desktop.png), [previous version reference](evidence/h4-next/parts-player-v1-history.png).

## Coordinator rollout

Keep Parts API and frontend flags off until compatible adapters, durable Mixer storage and private secrets/host allowlist are configured. Deploy the additive FreeFrame read/claim endpoints before enabling the Worker legacy mapping reader; deploy compatible Mixer and Worker adapters before enabling Parts orchestration. Apply forward migration `d5d7e10b2026`; do not rerun historical host DDL or move release pointers. Rebuild the web bundle with `NEXT_PUBLIC_HANDIN_COMPONENTS_ENABLED=true` only for the controlled activation.

Only the coordinator merges/deploys. This candidate already incorporates PR46 and PR68 code; its matching Worker incorporates PR73. Avoid a second independent Parts deployment from the superseded input branches. Retain the deployed first release as the rollback baseline, and complete the outstanding real external/provider/customer acceptance before broad activation.
