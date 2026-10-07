# H1 saved-snapshot producer addendum

Base: `c184fcb6bf71af4e4caeb97711675daa1659e904`. Separate branch: `codex/autoreview-snapshot-read`. This addendum is separate from the immediate H4 client release and leaves the simplified Share UI unchanged. No migration, Worker/Engine change, deployment or provider call.

## Contract and authorization

`GET /internal/review/checklist-snapshot` requires the existing bridge Bearer secret plus `share_token`, `project_id`, `asset_id`, `version_id`. It returns `autoreview.saved-snapshot.v1` with full unchanged snapshot, canonical context digest, binding/request identity and exact media version evidence. The nested snapshot request ID remains the binding ID. User JWT, public share and read-only API key alone cannot read private source text. Private successful responses are not cached.

The database binding, exact standing folder share, active project/folder/asset/version and non-revoked request association must match. V1 is deliberately limited to assets directly in the assignment folder. No context is returned for another folder, even a nested one; this is a safe label-free fallback, not inferred scope. Disabled, expired, secure or passworded shares are unavailable. Stored identity/hash corruption returns no context.

A frozen snapshot is readable when optional plan preparation failed, including `plan-api-unavailable`. The route never compiles a plan, fetches current rules/source URLs, changes retries or claims review readiness. H2 owns the Legacy consumer and safe native-comment attribution. That integration is still unverified. The producer contract is documented in `docs/autoreview-checklists.md` and the shared handoff `sessions/H1-SNAPSHOT-READ.md` under the existing Downloads handoff folder. H2's requested `H2-SNAPSHOT-INPUT.md` was not present at verification time; the wire is producer-defined pending consumer confirmation.

## Verification

- Regression RED: before the route, 11 expected failures /22 passes in 33 route cases. GREEN: route and original binding suites 48 passed. Identity-corruption cases use an independently recomputed digest so identity validation is exercised separately from hash mismatch.
- Real dedicated local PostgreSQL: 13 transactional tests passed, covering V1/V2 reuse, wrong tenant/share/asset/version and each soft-deleted/revoked parent. No synthetic rows persist.
- Full API against local PostgreSQL: **568 passed, 8 skipped, 3 existing dependency warnings**. Skips are existing opt-in n8n tests.
- Web on Node 22.22.3: **546 passed /81 files**; build, TypeScript and lint passed with existing warnings. The first run used local Node 25.4.0 and failed 44 tests because its native `localStorage` conflicted with jsdom. Reproduced with `auth.test.ts`; using Node 22 passed all 25 auth cases and the complete suite without source changes. Initial failures also affected `api-session`, `handin-redirect`, `header`, `request-journey`, `request-workspace`, `share-mobile-review`, `share-no-internal-toggle`, `share-review-mount`, `share-view-only-notice`.
- `git diff --check` passed. Local disposable PostgreSQL was stopped after verification. No browser rerun is needed for this server-only addendum; the Share UI remains at its visually verified base.

Logs are in `/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H1/snapshot-read-*.log`. Release compatibility and H1/H2 merge-migration guidance are recorded separately in `sessions/H1/release-compatibility.md` and `sessions/H1.json`. Only the release coordinator deploys after combined customer-flow acceptance.
