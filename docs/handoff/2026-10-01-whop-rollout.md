# Whop launch rollout — 2026-10-01

Status: Phase 1 verified locally; **STOP 1, no merge or production mutation performed**.
The user explicitly confirms there is no test server. All new processes below run on the
existing live host and database. Whop stays on `https://review.aditor.ai/o` until STOP 2.

## Read-only live baseline

- Host: `root@46.224.96.47` (`aditor-platform`); clean checkout `/opt/freeframe`.
- Checkout: `ea29772f22b350776785e962d853bb653c4de49a`; database head: `3b8e1d6c9f20`.
- Compose: `docker-compose.prod.yml` + `docker-compose.aditor.yml`, env `.env.prod`.
- Ingress: Cloudflare → nginx vhost `/etc/nginx/sites-enabled/feedback.aditor.ai`.
  `/api/` strips the prefix to localhost:3091; all other paths, including `/whop/session`,
  reach Next on localhost:3090. Traefik is disabled by the Aditor override.
- API image: `sha256:9dc9a00b6868058218e7c757b959fe36a7289ed64613ca1239cfbec63ca33035`.
- Web image: `sha256:8dfee7a283c398af28e0b031f974f9e1c003a6005aa44ea4acc6e7ab85fcb4f4`.
  The web container predates the current checkout, so a Git SHA alone is insufficient rollback evidence.
- API `SUITE_URL`, `WHOP_APP_ID`, `REVIEW_BRIDGE_URL`, `REVIEW_BRIDGE_SECRET`: all empty.
- GitHub push hook `664631355` is active. `/opt/webhook-receiver.js` deploys only `main`
  with `git stash -u`, `git pull origin main`, then Compose `up -d --build`.
  GitHub Actions is CI only; it is not the production deploy mechanism.

## Phase 1 evidence

Backend: **321 passed, 45 skipped** (no local transactional Postgres); frontend: **412 passed**.
Preview fixture contracts: **4 passed**. Node 20 production build, TypeScript and lint pass;
lint retains the existing hook warnings. Targeted legacy flows: **111 passed / 4 skipped** API,
**64 passed** frontend, covering staff auth, shares, hand-in and Trello project descriptions.
Rebase retains n8n #33, the four-hour reaper #30 and AI-review proxy #32.

Migration chain is `3b8e1d6c9f20 → b7c8d9e0f1a2 → c9d0e1f2a3b4`, with exactly one head.
Offline SQL from the live head adds `is_staff DEFAULT true`, request tables/indexes,
and two nullable unique Suite identity columns. It does not drop objects, rewrite existing
application rows or alter existing column types. `ALTER TABLE ... ADD` is additive DDL;
only Alembic's own version row is updated. No downgrade is part of rollout or rollback.

Independent review found and regression-tested fixes for customer public-project list access,
cross-account retries after delayed 401s, and truncated request/asset review-status batches.
The later ready-first Kanban handoff explicitly directs folder navigation even for waiting
requests; that existing direction is retained instead of restoring the earlier T8 title restriction.
Engine outages retain the explicitly specified fail-open behavior.

## Frame and header evidence

The actual nginx vhost and global/conf.d settings contain no blocking `X-Frame-Options` or
CSP `frame-ancestors`, and no request-header stripping. The current live HTTPS response and
new local production `/whop` response likewise contain neither blocking header. Next has no
configured frame restriction. No policy was relaxed and no wildcard was added.
Nginx forwards ordinary request headers; `/whop/session` goes to Next, whose unit test verifies
that only `x-whop-user-token` is sent to internal `/auth/whop`. The production Compose sets
`API_INTERNAL_URL=http://api:8000`. Local `/whop` returns 200; missing-header POST returns 401
with a readable instruction and `Cache-Control: no-store`. The recovery screen was inspected
in the browser. Actual Whop injection, proxy cookies and phone reload remain Phase 4 acceptance.

## Phase 2 — execute only after Alan's go

The automatic webhook must be paused before merging. Build and migrate while the old API/web
continue serving; bring up two candidate containers on unused loopback ports, then switch nginx
only after their checks pass. Old workers and HTTP containers stay running for immediate rollback;
Postgres/Redis and ongoing transcoding are not restarted. This avoids replacing serving containers
with an unverified build. The same additive schema is compatible with the retained old images.

1. On the local machine pause the existing hook (not its credential), then connect to the host:

```bash
gh api --method PATCH repos/videoaditor/freeframe/hooks/664631355 -F active=false --silent
ssh root@46.224.96.47
```

2. On the host save the database and runtime rollback evidence **before merge**:

```bash
set -e
umask 077
cd /opt/freeframe
test -z "$(git status --porcelain)"
whop_stamp=$(date -u +%Y%m%dT%H%M%SZ)
whop_backup_dir=/var/backups/freeframe/whop-$whop_stamp
mkdir -p "$whop_backup_dir"
git rev-parse HEAD > "$whop_backup_dir/checkout.txt"
cp /etc/nginx/sites-enabled/feedback.aditor.ai "$whop_backup_dir/nginx.before"
for whop_service in api worker email_worker beat web; do
  whop_image=$(docker inspect "freeframe-$whop_service-1" --format '{{.Image}}')
  docker tag "$whop_image" "freeframe-$whop_service:before-whop-$whop_stamp"
  printf '%s %s\n' "$whop_service" "$whop_image" >> "$whop_backup_dir/images.txt"
done
docker exec freeframe-postgres-1 sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$whop_backup_dir/postgres.dump"
test -s "$whop_backup_dir/postgres.dump"
docker exec -i freeframe-postgres-1 pg_restore --list < "$whop_backup_dir/postgres.dump" > /dev/null
stat -c '%n %s bytes' "$whop_backup_dir/postgres.dump"
```

Record the path/size in the launch notes. Never display dump contents, environment values or
full Docker inspections. Recheck the hook is paused and the receiver has no deploy in progress.
From the local machine, after green CI and the completed backup:

```bash
gh pr ready 31 --repo videoaditor/freeframe
gh pr merge 31 --repo videoaditor/freeframe --merge
```

3. In the same host shell, build candidates and perform the bounded additive migration:

```bash
cd /opt/freeframe
git pull --ff-only origin main
docker compose --env-file /opt/freeframe/.env.prod -f /opt/freeframe/docker-compose.prod.yml -f /opt/freeframe/docker-compose.aditor.yml build api web
docker run --rm --network freeframe_default --env-file /opt/freeframe/.env.prod -e SUITE_URL= -e WHOP_APP_ID= -e 'PGOPTIONS=-c lock_timeout=2s -c statement_timeout=30s' freeframe-api sh -c 'cd /workspace/apps/api && alembic upgrade head'
docker run -d --name freeframe-whop-api --restart unless-stopped --network freeframe_default --env-file /opt/freeframe/.env.prod -p 127.0.0.1:3191:8000 -e SUITE_URL= -e WHOP_APP_ID= -e DISABLE_DOCS=true -e INSTANCE_WIDE_PROJECT_ACCESS=true -e SHARE_COMMENT_DELETABLE_GUEST_EMAILS=review@aditor.ai -e AUTOMATION_SHARE_WEBHOOK_URL=https://review.aditor.ai/api/freeframe/project-registered freeframe-api sh -c 'exec gunicorn apps.api.main:app -w ${API_WORKERS:-4} -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120 --graceful-timeout 30'
docker run -d --name freeframe-whop-web --restart unless-stopped --network freeframe_default --env-file /opt/freeframe/.env.prod -p 127.0.0.1:3190:3000 -e API_INTERNAL_URL=http://freeframe-whop-api:8000 freeframe-web
```

Use bounded health retries (maximum 60 seconds), inspect candidate logs without credentials,
and require `/health`, `/login`, `/handin`, a real existing share, `/whop` and missing-header
POST `/whop/session` to pass before switching. A nonsecret header probe must return 503 while
Suite is disabled, proving Next reached the disabled backend; no header must return 401.
If the migration times out or any precheck fails, keep old ingress and stop, rather than widening
lock timeouts or silently retrying deployment.

4. Switch only the two FreeFrame upstream ports, syntax-check, then reload nginx:

```bash
python3 - <<'PY_SWITCH'
from pathlib import Path
p = Path('/etc/nginx/sites-enabled/feedback.aditor.ai')
s = p.read_text()
assert '127.0.0.1:3090' in s and '127.0.0.1:3091' in s
p.write_text(s.replace('127.0.0.1:3090', '127.0.0.1:3190').replace('127.0.0.1:3091', '127.0.0.1:3191'))
PY_SWITCH
nginx -t && systemctl reload nginx
```

After switching, verify through `https://feedback.aditor.ai`: staff login/session, a real
hand-in/share, the readable `/whop` state, missing-header 401, and ten minutes of logs without
new errors. Capture screenshots and curl statuses. Do not mutate an editor's work to test it.
Keep the webhook paused and old containers intact through STOP 2 and real-account acceptance.

## Immediate rollback

In the same host shell, restore nginx before stopping any candidate:

```bash
cp "$whop_backup_dir/nginx.before" /etc/nginx/sites-enabled/feedback.aditor.ai
nginx -t && systemctl reload nginx
curl -fsS http://127.0.0.1:3091/health
```

This immediately serves the retained prelaunch images on 3090/3091; the saved image tags and
checkout SHA identify the exact baseline. Leave the additive columns/tables in place; do not
restore a database dump over editor writes and do not downgrade. Keep the webhook paused,
report the failed check and stop. If an old container unexpectedly disappears, recover it from
its `before-whop-$whop_stamp` image tag with a temporary Compose image override and `--no-build`.
No remote branch pointer, release tag or unrelated checkout is reset.

## Phase 3/4 and final convergence

After Phase 2 smoke checks, enable Suite/Whop only on the serving candidate API and recreate
that container with the same arguments plus the approved settings. Check the existing Render
Review app key only for presence. The bridge also needs `REVIEW_BRIDGE_URL=https://review.aditor.ai`
(in addition to the secret); it is currently empty. Generate the new bridge credential only
at that stage, never print it or save it in this runbook. Coordinate the Worker secret entry
with Alan, then prove the authenticated bridge no longer returns 503.

STOP 2: Alan alone switches the Whop app URL and checks desktop/phone. Complete the full real
owner, reload, request/upload/review, isolation and expired-membership checklist from the user
request. Restore `/o` and disable Whop on any acceptance failure.

Only after acceptance, persist the approved nonsecret settings and configured credentials in
the existing deployment secret mechanism, converge canonical API/web onto the tested images
while candidate ingress serves traffic, health-check canonical 3090/3091, switch nginx back,
and retire the candidates. Upgrade workers only at a safe task boundary if required (the task
implementation is unchanged by this PR). Re-enable hook 664631355 only after Compose/env and
canonical ingress match the accepted deployment. Record the runtime image IDs, hook state,
backup evidence and rollback path; update the original launch handoff to live at that point.
