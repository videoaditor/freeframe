# Whop launch rollout — 2026-10-01

Status: **Phase 4 first login failed; app-ID typo corrected in runtime; real-account acceptance pending.**
PR #31 and startup fix #35 are merged. Production ingress serves the configured candidates.
Whop was switched; corrected candidates now serve ingress on API 3195 / web 3196. Real-account acceptance and canonical convergence are pending.
The user explicitly confirms there is no test server. All new processes below run on the
existing live host and database. Whop stays on `https://review.aditor.ai/o` until STOP 2.

## Phase 4 correction

The initial configured `WHOP_APP_ID=app_xSpqlhgkn1AX2J` was wrong: Whop's actual
Review dashboard links to `app_xSpqIhgkn1AX2J` (capital I). A real iframe diagnostic
proved header present, unexpired token, Suite exchange 200 and entitlement success;
only the mismatched FreeFrame audience preflight denied login. Ingress was first
rolled back to disabled 3190/3191. Corrected candidates were created with the exact
dashboard ID and the existing bridge credential, without rebuilding or changing auth code.

Current serving pair: `freeframe-whop-api-corrected` (3195) and
`freeframe-whop-web-corrected` (3196). Staff magic-code login, refresh, me, projects,
existing share API/page: 200. Public health/login/handin/whop: 200. Missing header: 401.
Ten-minute API/web error markers: zero. Correct audience preflight passes; the typo
is denied. Diagnostic route removed. Actual browser completion pending: Mac locked.
Whop Base URL/app path must be `https://feedback.aditor.ai` and `/whop`; the current
`/o/` app path redirects via middleware. Alan owns the Whop settings switch.
The Phase 3 rollback remains the saved `nginx.phase2` file below; DB is never downgraded.

## Actual Phase 2 outcome

### Worker secret confirmed; STOP 2

Alan reported `Success! Uploaded secret FREEFRAME_BRIDGE_SECRET`.
Read-only verification from the serving FreeFrame API confirmed the authenticated Worker
`GET /api/v1/requests/status` returns **200** with the expected `status` object. An initial
wrong-key request still saw **503** during propagation; the follow-up on one HTTP client
confirmed **200 / 401 unauthorised / 200** for correct/wrong/correct credentials.
No existing credentials were rotated and no secret value was printed or saved in source files.
The bridge is now configured on both sides; no request/upload/review acceptance is claimed yet.
STOP 2 instructions given to Alan: switch Whop Review app URL from `https://review.aditor.ai/o`
to `https://feedback.aditor.ai/whop`, inspect desktop and phone. Reverting to `/o` is immediate
Whop-side rollback. Keep the automatic deploy hook paused and retained baseline containers
until real-account acceptance and canonical convergence are complete.

### Successful retry and Phase 3 configuration, 12:09–12:13 UTC

Alan explicitly resumed the rollout. Fresh verified backup:
`/var/backups/freeframe/whop-retry-20261001T120921Z/postgres.dump`, **1,607,511 bytes**.
The fixed production-image startup check passed. Corrected public baseline and candidate
checks passed before switching; public candidate checks then passed after switching:
existing-staff magic-code login, refresh, `/auth/me`, `/projects`, existing share API/page,
health, login, hand-in and Whop page **200**; missing-header Whop session **401** with readable
message; synthetic header **503** while Suite disabled. API/web ten-minute logs had **zero
error markers**. Frame headers remain non-blocking. Screenshots: `phase2-live-whop.jpg`,
`phase2-live-login.jpg` in the Downloads evidence directory.

Render service `srv-d9fliddaeets73cb2qd0` Review app key was verified present and masked.
FreeFrame API is now configured with `SUITE_URL=https://aditor-suite.onrender.com`,
`WHOP_APP_ID=app_xSpqlhgkn1AX2J`, `REVIEW_BRIDGE_URL=https://review.aditor.ai`.
The Worker first returned `503 bridge-disabled`, confirming no existing bridge key to rotate.
One new 32-byte hex bridge secret was generated with OpenSSL and passed directly into the new
API container's environment. No value was printed or written to a source/config/temporary file.

Serving containers: `freeframe-whop-api-enabled` (localhost **3192**) and
`freeframe-whop-web-enabled` (localhost **3193**, internal API points to the enabled API).
Their images are the already tested API `97f88a070a01cf90b62b0c49a64e213b6436ae184b68bc16db64995333f43bcf`
and web `be4f5fab48b6292df2cb1aa68afc2013a593e4fcffff4aec63d157bd3dbdbc00`.
Candidates were started and checked before nginx switched, preserving active editor traffic.
Configured internal AND public staff login/refresh/me/projects and existing share API/page
returned **200**; public missing-header Whop **401**; API/web logs **zero error markers**.
A structurally valid synthetic Whop token with an invalid signature reached configured Suite
and was denied **401**. This is not a real-owner login acceptance claim.

Authenticated Worker bridge still returns expected **503 bridge-disabled**, pending Alan's
explicitly assigned secret entry. His command captures the FreeFrame container value through
SSH and pipes it directly into the installed Wrangler 3.114.17 `secret put` stdin, without
displaying it. Installed CLI source confirms protected stdin and no local-code upload for
this secret operation. Production target is `feedback-submission-production` on `review.aditor.ai`.
Then verify authenticated bridge **200** before giving STOP 2 Whop URL-switch instructions.

Canonical original containers on 3090/3091 remain running for immediate rollback; phase2
disabled candidates on 3190/3191 also remain available. Hook **664631355 is still paused**.
`.env.prod` is unchanged; runtime credential/config has not yet been converged into canonical
deployment. Rollback to prelaunch: restore `whop-20261001T071757Z/nginx.before`, nginx test/reload.
Rollback just Phase 3: restore `whop-retry-20261001T120921Z/nginx.phase2`, nginx test/reload.
Do not restore/downgrade DB or rotate the generated bridge credential on continuation.
Current screenshot: `phase3-live-login.jpg`. Original handoff is not marked accepted/live yet.

### Authorized retry, 11:34–11:44 UTC

The startup regression was reproduced against Gunicorn 26.2.0 with a real WSGI process:
HTTP succeeded but the log contained the same permission error. Removing `--no-create-home`
creates the appuser-owned home without changing the non-root runtime. The built-image check
then passed; backend **321 passed / 45 skipped**; independent review found no issues.
PR #35 merged at 11:36:56 UTC as `c62db661f6eda3e0ccf3efc6680f19accd4adf71`.
CI now runs `apps/api/tests/check_prod_image.py` against the production image.

Fresh verified backup: `/var/backups/freeframe/whop-retry-20261001T113730Z/postgres.dump`,
**1,606,475 bytes**. The backup-only restrictive umask was accidentally retained for the
subsequent root checkout, making the new smoke script unreadable in the image. Its host mode
was corrected to 644 and the rebuilt image passed. Future runbooks must scope `umask 077`
to the backup commands rather than subsequent source checkout/build commands.

Fixed candidates passed existing-staff login, refresh, `/auth/me`, `/projects`, existing share
API/page (**200**), missing-header Whop **401**, disabled Whop header forwarding **503**, and
API/web ten-minute logs (**zero error markers**). After switching ingress, the public Python
login probe returned **403**. The ERR trap immediately restored original ingress and stopped
the candidates. No Phase 3 configuration was performed.

Read-only diagnosis proved the same public probe against restored production also returns
Cloudflare **1010**, before reaching the API. A normal curl User-Agent reaches API validation
(422 for intentionally invalid input); the corrected probe then completed real staff login,
refresh, `/auth/me`, `/projects`, existing share API/page via public HTTPS with **200** on the
restored baseline. This is a probe incompatibility with the existing Cloudflare policy, not
a candidate application regression. No Cloudflare/security policy was changed.

Production again serves the original images below, health/login/hand-in **200**; hook remains
paused. Screenshot: `retry-rollback-login.jpg` in the same Downloads evidence directory.
Render Review app key was rechecked as present and masked; no credential was revealed or changed.
Awaiting explicit resume per the user's fail-and-stop rule. Use the corrected public probe on
candidates before switching ingress on the next retry.

- Backup: `/var/backups/freeframe/whop-20261001T071757Z/postgres.dump`, **1,589,518 bytes**;
  custom dump archive verified with `pg_restore --list` before merge.
- PR #31 merged at 07:18:06 UTC as `828812f2d624c255d849f1d9a841616df9bfc53f`.
  Build succeeded; bounded migration reached `c9d0e1f2a3b4`; all 27 existing accounts remain staff.
- Candidate existing-staff magic-code verification, `/auth/me`, `/projects`, existing share API/page:
  **200**. Public HTTPS health, login, hand-in and Whop page: **200**. Missing-header session POST:
  **401** with readable recovery text; synthetic header reached disabled API and returned **503**.
- Ten-minute log check found a new startup error at 07:21:20 UTC:
  `Control server error: [Errno 13] Permission denied: '/home/appuser'`.
  The image installs unpinned Gunicorn and creates `appuser` with `--no-create-home`.
  Per the requested fail-on-any-error rule, ingress was immediately restored from `nginx.before`;
  candidate API/web stopped. No further rollout or Phase 3 configuration performed.
- Rollback confirmed by 07:23:49 UTC: public health OK, login/hand-in **200**, original API/web
  running with the baseline image IDs below. Database was not restored or downgraded, preserving
  live editor writes; additive migration remains. Hook **664631355 remains paused** to prevent
  an automatic deployment of the failed build. Old workers remain running.

Screenshots are saved locally under `/Users/alansimon/Downloads/freeframe-whop-20261001/`:
`login.jpg`, `whop-recovery.jpg` (candidate checks), `rollback-login.jpg` (restored production).
Render's Suite environment page showed `WHOP_ADITOR_REVIEW_APP_API_KEY` configured and masked;
no value revealed or changed. Real Whop login and full owner acceptance remain untested.
Next: fix the startup root cause, verify the built container has no startup errors, then retry
Phase 2 only after Alan explicitly resumes the stopped rollout.

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
