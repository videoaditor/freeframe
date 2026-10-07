# Bound-review producer implementation

Root-approved2026-10-08. Base main3ae5d6a9; private branch only, no rollout.
Server-owned project allowlist, empty default, chooses continuity-v1 only on fresh
ChecklistBinding insert. intent.review_engine is frozen/hash-bound; old omission
is legacy. Retry compares exact business intent excluding only server selector,
verifies stored full hash and preserves insertion winner. No model/migration/UI.

Implement existing service helper for frozen registration options (rawP/BindingB,
notU), extend current bridge keyword arguments without losing iteration/checklist
fields, share helper across outbox/mode/derived registration. Strip selector from
snapshot source payload. Selected new folder/share skips generic legacy announce;
existing authenticated outbox must establish watcher; asset-ready unchanged.
Selected binding adoption of any preexisting share fails before mutation; no
secondshare/rotation/promotion. Existing same-binding folder retry remains stable.

TDD: selection freeze/hash/retries + body/durable helper; real localPG isolated
schema insert/lock races; folder conflict/newannounce; mode/derived and oldflow.
Run focused tests, whole backend, applicable CI guard checks; no frontend source
or new frontend tests. Final fresh independent review, fix, privatecommit/evidence.
Root alone owns release/config/Worker integration. Durable log at sessions/
ENGINE-BOUND-FREEFRAME-PLAN.md; update decisions/tests/remainingwork there.

## Doctrine gate
Purpose: persist an explicitly selected review engine with the original assignment,
then transport its exact P/B identity through existing registration and recovery.
Non-goals: UI, migration, old-share adoption, engine compiler changes, rollout.
Spec-first and simplest architecture: existing JSON intent, row uniqueness/locks,
existing authenticated outbox and share helper. No new state machine/table/queue.
State/recovery: intent and hash commit before registration; outbox retains retries.
Contracts: raw project UUID P, binding UUID B; U is never review identity.
Failure taxonomy: altered business intent/corrupt stored intent/adoption409;
unsupported selector fails closed; bridge unavailable uses existing outbox retries.
Context: omit selector from source request; immutable snapshot is unchanged.
Done: focused producer tests, committed local PostgreSQL race/lock coverage,
complete backend suite and independent review. Stop/escalate: missing database
constraint or transport watcher guarantee, never compensate with another share.
No external/provider costs; only synthetic local rows in dedicated disposable DB.

## Verification evidence (2026-10-08)
- Initial red: producer regressions5 failed/3 passed (missing frozen selector helpers
  and transport). Additional red proved lost-selector downgrade and true/1 identity
  ambiguity; both now fail closed. Share helper opt-in red proved missing keyword.
- Fresh independent read-only review: one P2 downstream hash finding fixed;
  second complete diff review returned no remaining concrete findings.
- Python3.11 cached image freeframe-h4-candidate:c16daa8, own mounted worktree,
  own DB bound_producer_h2_test, generated per-test schemas dropped afterward.
  No H4 app/container/source or other existing database mutated.
- Full backend:751 passed,11 skipped,2 upstream deprecation warnings,18.30s.
  Includes real localPG insert winner/config race in both directions and fresh
  selected internal folder→new exact folder share→restart/outbox registration.
  External socket connections blocked by autoreview_plan_offline plugin; PG uses
  explicitly fixed local endpoint. No media/provider/network external calls.
- CI backend: Alembic upgrade head in own disposable DB;148 OpenAPI paths,
 75 test files, all critical backend files present; git diff --check clean.
- Frontend unchanged: no UI/build assets/TypeScript touched; no new frontend tests.
  Existing entire backend includes legacy registration, iteration, folder and
  asset-ready wakeup regressions. No model change/migration required.

Reproduce backend from a fresh terminal (local disposable runtime already exists):
```sh
python3 /Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/run-bound-producer-tests.py /app/apps/api/tests/ -q
python3 /Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/run-bound-producer-tests.py --ci-checks
```
The runner passes local DB credentials directly without logging them, mounts the
existing socket guard read-only, uses a new disposable container, never replaces
H4's running API, and addresses only our own database. No Redis writes required.

Root relay confirmed Worker authenticated POST /api/v1/requests creates enabled
watcher via=request independently of legacy project webhook; exact-registration
and retry tests pass. Asset-ready reads/rearms same watcher. Worker implementer
owns final cron/ready interoperability proof; FreeFrame asset-ready unchanged.
Remaining: Root-controlled Worker interoperability/release/configuration and
opt-in pilot acceptance. Default allowlist remains empty; no runtime config,
production writes, provider calls, push, PR, deployment or automatic adoption.
