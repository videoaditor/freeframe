# Whop launch: implementation and acceptance

Status: implemented locally, **not deployed and not announcement-ready**. Alan authorized Codex
("übernimm") to take over the missing backend integration. The current Whop app still opens
`review.aditor.ai/o`, the older Worker owner page, not the new FreeFrame workspace.

## Implemented path

Whop → `/whop` → same-origin `POST /whop/session` (Next) → internal `POST /auth/whop`
(FastAPI) → Suite `/v1/auth/owner` with `x-suite-app: review` → Suite entitlement for `autoreview`.
Only the injected `x-whop-user-token` is forwarded. Next returns only ordinary FreeFrame tokens.
The Next route deliberately lives outside `/api/*`: production nginx/Traefik routes that entire
prefix directly to FastAPI. `API_INTERNAL_URL=http://api:8000` is set in production compose.

Source contract audited: `videoaditor/aditor-suite` main at
`8146c32e65c4656fada90805b6416069b7eec1be` (auth-routes.ts, whop.ts, jwt.ts,
entitlement-routes.ts, entitlement.ts, server.ts, CONTRACT.md). The old aditor-ops path was removed
in August and must not be used as current documentation.

The raw Whop token is preflighted for app audience and expiry; Suite verifies its signature and
membership with the Review app client. The owner token comes only from the configured Suite over
HTTPS. Its signature is checked by Suite's entitlement endpoint, not by trusting a browser-supplied
JWT. No Suite signing secret is copied into FreeFrame. Owner audience/expiry/identity/email are
required. Suite sometimes supplies `user_…@whop.user`; it is an identity address, not a verified
mailbox (email_verified remains false).

Customers bind uniquely to both Suite account ID and brand ID. Matching emails do not claim
existing accounts, staff or otherwise. Deleted/disabled/conflicting identities are refused.
Uniqueness violations return a retryable conflict rather than creating another identity.
New accounts are explicitly active, nonstaff, nonsuperadmin, and gain no project membership until
they create a brand. Their normal project membership rules still apply.

Redis holds the Suite owner token privately, no longer than its expiry. Every authenticated customer
request and refresh checks continuing entitlement, with a maximum 60-second positive cache;
open event streams recheck before delivering each event and close on refusal. Cache expiry/outage
fails closed for this owner access path. The Suite editor-tool degraded-open contract is not used
to grant new customer identity or management access. Ordinary accounts keep existing authentication.
A 90-day FreeFrame refresh token cannot outlive the Suite identity session; reopen Whop to renew.

Successful ordinary logins reset the sign-in provider; refresh preserves it. An in-flight refresh
cannot restore an old identity or provide a new owner token for retrying an old mutation.
At entry, the frontend discards old tokens and persisted customer upload/branding state. A full
navigation after success clears in-memory stores. Expired sessions return to `/whop` rather than
the email login. Missing context, storage denial, account conflict, denied access and service errors
show recoverable states. Whop proxy-domain cookie/reload behavior still needs live acceptance.

Two related launch blockers were fixed: customer brands bypass the internal staff Trello-link
requirement; branding saves accept only the current project's presigned logo key format (previously
a caller could point their own logo at another project's storage object).

## Configuration to apply only with an approved test deployment

| Service | Setting | Value / requirement |
| --- | --- | --- |
| FreeFrame API | `SUITE_URL` | `https://aditor-suite.onrender.com` |
| FreeFrame API | `WHOP_APP_ID` | `app_xSpqlhgkn1AX2J` (Review app, verified from Worker handshake spec) |
| FreeFrame Next | `API_INTERNAL_URL` | `http://api:8000` in production compose; absolute API URL outside Docker |
| Suite | `WHOP_ADITOR_REVIEW_APP_API_KEY` | Existing Review app key must be configured; do not generate/rotate or print it |
| Whop app | application target | Approved FreeFrame test deployment origin + `/whop`; keep old `/o` until acceptance |

Deploy migration `c9d0e1f2a3b4` after `b7c8d9e0f1a2` (two nullable unique columns; existing rows
unchanged). Keep `NEXT_PUBLIC_API_URL=/api` in the production build. Preserve the Whop header through
its proxy and nginx. Check the actual frame policy and storage CORS for the Whop proxy origin;
do not add wildcard CORS or remove protections speculatively. Configure the existing Review bridge
and deploy the matching Worker platform-v2 contract before claiming review/insights work live.

Rollback before launch: keep Whop on its existing target. Disable both Whop API settings to refuse
new/existing Whop sessions without affecting ordinary staff accounts. The additive columns can stay;
rolling back application code does not require dropping identities or customer data.

## Verification and remaining acceptance

- Backend: 302 passed, 45 skipped, including Whop auth/refresh/revocation/SSE, identity collision,
  immutable binding, account races, nonstaff isolation, initial brand creation, logo key scoping.
- Frontend: full suite 401 passed. TypeScript, lint (existing hook warnings only), production build passed. Build used an isolated copy
  with its own dependencies to avoid interfering with the running preview.
- Migration: one expected head; offline PostgreSQL upgrade SQL generated and reviewed. No live DB
  migration was run. API tests use the repository's mocked database contract.
- Browser: actual local `/whop` missing-header state and Retry inspected at desktop and 375px;
  correct Aditor brand, readable error, 44px action. Screenshot in `docs/design/screenshots/`.
  This does **not** establish successful Whop identity, production storage or real review processing.
- Still required: fresh entitled member + existing member, two real independent owners with reload
  and direct cross-project denial, expired access, phone/desktop in the actual Whop app, then
  request → guest upload → review → leaderboard and persistent logo. Existing email/account conflicts
  deliberately require a verified support linking process; no automatic migration is claimed.

The project spec requires a PR only: “Auf main mergen” is prohibited until Alan/Saskia's acceptance
(`docs/superpowers/specs/2026-09-28-review-platform-v2-design.md`, Grenzen). Keep the PR draft while
these live checks and the Worker dependency are outstanding. No announcement was sent.

Independent focused code review completed. Its SSE event-loop and sticky sign-in-provider findings,
and the subsequent stale-request replay finding, were fixed and rechecked with no remaining findings.
