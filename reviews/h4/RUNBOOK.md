# H4 — isolated repeat and release ownership

07.10.2026: scoped candidate qualification passed. See [the integrated report](../2026-10-07-h4-integrated-release.md), which supersedes the historical pending matrix. The full client-facing system is not yet accepted: Whop, internal/legacy entry routes, Parts, producer binding and natural timing calibration remain open.

The original coordinator already holds Alan's go-live authorization and is the sole production operator. H4 never mutates production. Do not ask for the same authorization again. Current validated runtime heads: FreeFrame a6cf68c, Worker6e2dd47; integrated PR66/85. One Alembic head c4d7e10b2026 joins both additive siblings.

## Repeat only in H4's own stack

All values below are synthetic. The compose project is autoreview-h4, with isolated persistent Postgres/Redis/S3 volumes and loopback published ports. S3 uses pinned SeaweedFS3.97 because MinIO registry/binary endpoints were inaccessible during this session. These storage fixtures do not certify production storage behavior. Never prune or delete another stack's data.

```bash
export PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH"
export H4_RUNTIME_ROOT="/Users/alansimon/.codex/worktrees/autoreview-h4-integrated-check/freeframe"
export H4_API_IMAGE="freeframe-h4-candidate:a6cf68c"
docker build -t "$H4_API_IMAGE" -f "$H4_RUNTIME_ROOT/apps/api/Dockerfile" "$H4_RUNTIME_ROOT"
docker compose -f "/Users/alansimon/.codex/worktrees/autoreview-h4-editor-routes/freeframe/reviews/h4/compose.json" config --quiet
docker compose -f "/Users/alansimon/.codex/worktrees/autoreview-h4-editor-routes/freeframe/reviews/h4/compose.json" up -d
docker compose -f "/Users/alansimon/.codex/worktrees/autoreview-h4-editor-routes/freeframe/reviews/h4/compose.json" exec -T api python < "/Users/alansimon/.codex/worktrees/autoreview-h4-editor-routes/freeframe/reviews/h4/seed-local.py"
```

The seeder asserts the exact isolated h4 database URL and uses sanitized local copies of existing authorized identity IDs; it does not create or alter live identities. Its local project ownership is synthetic. Password login is enabled locally; no production-equivalent magic-code/mail flow is claimed. Existing production passwordlogin=false and staff instance-wide access must remain as verified by the coordinator.

API18044, web13044, bridge18744, Postgres55444, Redis16344, S3 19044. Candidate migration runs when API starts. The worker must listen on transcoding,default for checklist preparation. The active local candidate override also runs an isolated Beat; generated candidate-compose.json is intentionally untracked because it contains machine-specific absolute paths.

Start the controlled bridge in another terminal:

```bash
export PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH"
cd "/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H4/worker-release-candidate"
H4_BRIDGE=1 H4_EVIDENCE="/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H4/bridge-release-state.json" npx vitest run test/h4-standalone.integration.test.ts --maxWorkers=1 --minWorkers=1
```

This opt-in harness lives in supporting WorkerPR81 (also copied locally into the candidate). It injects provider/Trello answers, rejects external I/O, and uses volatile KV. It is not durable Cloudflare-KV evidence. Request registration and production code run normally. /__h4/tick and /__h4/drain execute/drain the real scheduled logic; /__h4/provider/fail, /ok and /clear control only injected answers. A provider finding is a synthetic acceptance input, not a measured model-quality result.

Build/start the frontend in a third terminal:

```bash
export PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH"
cd "/Users/alansimon/.codex/worktrees/autoreview-h4-integrated-check/freeframe"
NEXT_PUBLIC_API_URL="http://localhost:18044" NEXT_PUBLIC_REVIEW_GATE_URL="http://localhost:18744" NEXT_PUBLIC_PASSWORD_LOGIN_ENABLED=false pnpm --filter web build
pnpm --filter web exec next start -H 127.0.0.1 -p 13044
```

The last lines keep running until Ctrl-C. Do not start a second listener on an occupied port. Actual Owner-created hrefs must be captured from the real RequestSheet/API rather than guessed. Existing fixture browser session used normal local password auth; preserving its JWT is not proof of Whop or magic-code login.

## Tests and evidence

The final API suite ran558 tests with zero skips on separately created h4_h2_test migrated to c4, isolated Redis14, ITERATIONS_TEST_DATABASE_URL, FREEFRAME_RUN_COMMENT_SOURCE_POSTGRES_TESTS=1 plus FREEFRAME_COMMENT_SOURCE_TEST_DATABASE=h4_h2_test, and FREEFRAME_RUN_N8N_POSTGRES_TESTS=1 plus FREEFRAME_N8N_TEST_DATABASE=h4_h2_test. H2 safety guard requires h2 in the dedicated database name. Never point these DDL/cleanup tests at production or the browser fixture database. Repeated login tests need a fresh isolated Redis index to avoid carrying rate-limit state across runs.

Screenshots, sanitized version binding and route inventory are committed under evidence/. Signed media URLs and live account screenshots remain outside Git. The older matrix/journeys record first-pass pending status; the integrated report and route-matrix.json contain the current scoped result. No blanket rewrite between /s,/share,/r is authorized by a matching-looking token.

## Production sequence and rollback

Root alone pauses the FreeFrame push hook before merge, verifies no active/reserved Celery tasks, and uses its checked backup, immutable images and reviewed e4→c4 migration. Worker main-push uses the existing GitHub deployment Action; do not run a parallel CLI deployment. API/web/worker/Beat must share the chosen release. Recheck actual domains and authorized journeys after the serving switch before claiming live_verified.

For rollback use root's captured previous image digests and Cloudflare version through existing operations. Additive schema can remain while previous compatible code resumes; no blind Alembic downgrade, request/comment deletion, release tags or stable/latest pointer changes. Preserve application data and inspect uncertain upload outcomes before replay.

Stop only H4's own processes: bridge POST http://localhost:18744/__h4/stop, web Ctrl-C, exact autoreview-h4 compose stop if needed. Preserve its volumes/workspaces/evidence for review. No down-v/prune or foreign service restart.
