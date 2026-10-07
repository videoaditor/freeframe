# Staff request Trello snapshot fix

Base: `01654a20e35dcce6d9f32d392f4cdce51a5834d4`; branch `codex/fix-request-trello-snapshot`. Independent of PR67; the saved-snapshot producer route/head is unchanged.

Read-only production inspection found a registered staff request with a nonempty text briefing and Trello URL but no canonical card ID, no frozen snapshot and three failed preparation attempts. Matching worker logs contain three snapshot HTTP403 responses and zero transport failures. The official `/requests` path reserves an immutable intent without verifying Trello metadata; the Worker requires that canonical card ID before private Trello access. The generic bridge hides the rejection as `briefing-unavailable`. This is a source-authorization plumbing defect, not evidence of an empty brief. No private text, token or secret was printed, and no live endpoint/retry/provider/PDF/review was invoked.

The fix verifies an unresolved request card during asynchronous preparation only after loading its active, non-deleted staff creator. It uses the existing service-authenticated card verifier and checks canonical/short ID shapes. The verified ID is saved separately from the immutable intent and survives a snapshot outage. Customers, deactivated/missing creators and unbound assignments fail before private source calls. The Worker authorization check is unchanged. Already frozen snapshots never re-read source data. No schema or UI changes.

Verification:

- TDD RED: all 10 new regression cases failed before the fix. GREEN: new and existing binding cases **25 passed**.
- Dedicated loopback PostgreSQL proof: actual official request creation and real task execution commit canonical metadata, full synthetic frozen rules/briefing and the registered context hash; a subsequent retry reuses identical intent/snapshot. Only remote bridge IO is stubbed. Synthetic rows were removed.
- Full API **556 passed, 12 existing opt-in skips, 3 existing warnings**. This branch excludes PR67's separate 46 tests; no coverage was removed.
- Node 22.22.3 Web **564 passed /84 files**; build, TypeScript and lint passed with existing warnings. Dependencies installed from local cache; no lockfile changes. `git diff --check` passed.

Evidence: `request-trello-{red,green,postgres,api-full,web-build,web-test,web-types,web-lint}.log` and `verify-request-trello-postgres.py` in the existing H1 Downloads handoff folder. Production diagnosis and exact request identity remain in local H1.json. No production mutation or model/PDF cost was incurred.

After the root-owned release, an authorized retry of the same failed binding is required; automatic retries are exhausted. Do not replace the request, rewrite its intent, reset review records, or claim a media pass. With the plan adapter off, expected preparation may still report `failed/plan-api-unavailable` while the snapshot/hash are durably present and registered. Acceptance must inspect the actual snapshot/hash/source versions and registered context, then qualify the H2 consumer on the exact media version. The live freeze and any further provider/source issue remain unverified here.
