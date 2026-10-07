# H1 checklist implementation plan

> Execute inline with superpowers:executing-plans. Product scope is already authorized by Alan; do not ask for a new design approval.

**Goal:** Freeze complete source-bearing inputs once and prepare a stable checklist before media arrives.
**Architecture:** FreeFrame owns authorization and a durable binding/outbox. Worker resolves inputs and stores an immutable snapshot before calling the optional Engine plan API. Engine remains the plan owner.
**Tech:** FastAPI/SQLAlchemy/Postgres, TypeScript Worker/KV, existing Next.js components.
**Spec:** H1 and H1A/B/C in the supplied 2026-10-05 handoff.

## Global constraints
No Engine changes, paid calls, deployment, merge, production KV writes or customer messaging. Preserve source scope and all active rules. Missing evidence is unavailable, never passed. Snapshots include provenance. Project ID is tenant ID. Upload and link remain usable. No folder on paste.

## Review focus
Cross-tenant reads/writes; retried accepted-but-timed-out requests; concurrent paste/folder attachment; partial or oversized brief/rules; stale A response after B selection.

### Task 1: H1A shared contract
- [ ] Add tests for canonical JSON/hash fixtures, sources/dedup/max-eight, global/brand/trainee and context limits; run RED.
- [ ] Implement src/briefing-checklist.ts pure exports; run focused tests GREEN; commit and publish export path/fixtures in H1.json.
Produces RequirementSource, ChecklistSnapshot, canonicalJson, snapshotDigest, buildSnapshot.

### Task 2: H1A bridge
Consumes Task 1. Produces authenticated /api/v1/checklists prepare/status, frozen snapshot and optional engine plan reference.
- [ ] Tests first for duplicate events, timeout after acceptance, restart, unreadable briefing, tenant isolation and disabled Engine API.
- [ ] Persist original intent before resolving. Persist full snapshot before submit; retry from durable state via the existing poll/worker mechanisms. Engine dedup required; never claim KV exactly-once.
- [ ] npm test; compare TypeScript diagnostics with base. Commit and Draft PR against main.

### Task 3: H1B platform binding
Consumes H1A wire schema. Produces persistent authorization-bound binding, source intent, plan status, folder/request linkage.
- [ ] Tests first; model/schema/migration with unique constraints. Customer request and intent commit together. Internal staff POST before folder exists.
- [ ] Existing Celery machinery resumes intent and polls plans; endpoint reads are authorized and read-only. Folder creation atomically adopts same binding.
- [ ] Run API suite and isolated Postgres upgrade/downgrade/concurrent insert/rollback/reconnect checks; commit.

### Task 4: H1C interface
Consumes H1B. Produces shared private checklist disclosure on request workspace and handin.
- [ ] Read design skills and fill handoff. Component tests before behavior; paste/blur dedup, stale A/B, retry and ready/failed poll termination.
- [ ] Wire existing creation/paste/workspace selection; preserve working link and upload.
- [ ] Frontend build/test/types/lint and desktop/mobile light/dark/zoom/reduced motion browser evidence. Commit and Draft PR.

### Task 5: Review and handoff
- [ ] Review full ranges for auth/idempotency/privacy and missing coverage; fix verified issues with regression tests.
- [ ] Record code_verified separately from real Engine integration/live evidence. Update own reviews and H1.json; no other session state writes.

## Interface audit / rulings
H1A → H1B → H1C use versioned payloads; H2 consumes only RequirementSource exports. Disabled Engine API is an explicit integration blocker, not a reason to skip platform work. The already authorized execution overrides skill requests for another plan/design approval.

## Execution ledger
Task 1 complete: 7fd1e43, shared source/hash contract 5/5 tests RED→GREEN, published in H1.json.
Task 2 ruling: durable state stays in FreeFrame’s existing Postgres/Celery path. Worker resolves snapshot; FreeFrame commits it; Worker forwards only that frozen payload. This avoids a second mutable KV outbox/single-writer problem. Cost if wrong: adapter boundary can change without Engine/compiler changes.
Task 2: Worker suite 1403/1403, TypeScript base/head 161/161 with no new diagnostics (before trusted-reference addition); final full run still required.
Task 3: 9 focused binding tests pass. Existing migration head assertion extended with the new additive successor rather than removing the floor guard.

Task 2 complete: 7334e0d, authenticated snapshot/plan adapter and additive trusted share reference; 15 focused tests pass. Decimal correction b8c8757 adds cross-language decimal/numeric-key fixture.
Task 3 complete: e0ac6b7; API 470 passed, 51 skipped. Real disposable Postgres verifies concurrent reservation/customer creation, conflict/rollback/reconnect, migration downgrade/reupgrade.
Task 4 complete: 620057f; two additional UI regressions observed RED then GREEN (new assignment after reopen, caught failed retry). Unique workspace matching regression observed RED then GREEN. Browser confirms persisted reload and no folder/request from paste, synthetic data only.
Task 4 ruling: screenshots use a synthetic bridge harness because the Engine API is not available/confirmed. They establish UI behavior only; cost if wrong: integration must still fail closed and pass real Engine evidence before live activation.
Browser limitation: browser zoom shortcuts have no effect and no reduced-motion emulation API is exposed. No false 200%/reduced-motion verification claim. Native disclosure adds no animation.
