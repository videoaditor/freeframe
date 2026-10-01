# Owner UI follow-up: Whop launch and editable rules

Status: **not ready to announce as working for all Whop users**. UI refinements are local;
no production deployment, merge, customer invitation, or announcement was performed.

## Observed on 2026-09-28

- Local :3200 uses `apps/web/test/preview-api.py` on :8100. Browser interaction validates the UI
  and payload contract, not real membership, email delivery, storage, or review processing.
- `https://feedback.aditor.ai/home` in the browser redirects to `/login?from=%2Fhome` and shows
  the old “Sign in to FreeFrame” magic-code screen. Screenshot: production-login.png in
  `/Users/alansimon/Downloads/freeframe-owner-ui-checks/`. No login email was sent.
- The Suite `/health` responds 200, `{"ok":true,"service":"aditor-suite"}`. Health alone does
  not prove owner authentication or the autoreview entitlement. Direct scripted calls to Feedback
  and Review hit edge 403 / code 1010; those challenge-response frame headers are not evidence
  about application iframe support.
- FreeFrame uses its own bearer/refresh tokens (`lib/auth.ts`, `middleware.ts`, `routers/auth.py`).
  No Whop token exchange exists in FreeFrame. Cookies currently use SameSite=Lax; actual Whop
  proxy-domain/reload behavior must be tested, not fixed by simply weakening cookie settings.
- The Worker already has `/api/whop/session` and `/auth/whop-owner` in `src/index.ts`, backed by
  `src/suite.ts`. Those issue Worker owner sessions, not FreeFrame sessions. Copying a Worker or
  Suite token into ff_access_token cannot work. The skill's local Suite source path no longer
  exists, so the live Suite identity/entitlement implementation has not been audited here.

## Backend follow-up

Whop backend ownership was explicitly transferred to Codex by Alan ("übernimm").
The Whop addition is now implemented locally; see `2026-09-28-whop-launch.md`.
Rule editing/compilation below remain proposals, not existing routes.

1. **Whop session exchange:** establish the correct configured Review Whop app and same-origin
   server endpoint. Verify Whop token signature, expiry and app audience through the supported
   identity service; verify the allowed product/membership. Map immutable verified Whop identity
   to a customer (`is_staff=false`) and its own workspace, never a typed brand/email alone.
   Return normal FreeFrame tokens/user to the frontend. Do not reuse staff provisioning or a
   blanket instance-wide role. Specify new-member, existing-owner, expired-member, and outage states.
2. **Existing rule update:** e.g. authenticated `PATCH /insights/rules/{rule_id}` with project_id,
   human rule, and expected revision. Check project role and rule-brand ownership server-side;
   global rules are not customer-editable. Update the existing ID, don't import a duplicate as
   an “edit”. Persist the original customer wording separately from the generated review check.
3. **Rule compilation:** customer writes human guidance; engine proposes a precise check.
   Return human text + compiled check + revision/status; preserve the previous active rule when
   compilation or save fails. Explicit approval determines when the replacement becomes active.
   Existing `name` and `what` can be displayed as title + Review check, but don't establish the
   original customer wording or an editable, versioned contract.

Current UI therefore uses honest **View rule**, not a fake Edit/Save flow. It now renders compact
rule rows with the review-check label and opens complete text. True editing and automated
human-to-check translation remain unfinished pending the above contract.

## Required live acceptance before announcement

| Scenario | Evidence still required |
| --- | --- |
| Fresh entitled Whop member | Opens actual app, gets customer account/workspace, survives reload |
| Existing member | Reuses correct workspace; no duplicate or other customer's data |
| Two independent owners | Cannot read/write each other's logos, requests, rules, insights |
| No access / expired access / identity outage | Clear recovery state; no accidental staff access |
| Full workflow on desktop + phone | Request → guest name/email → upload → review → leaderboard; logo persists; rules save |

Whop entry URL located independently and opened in the authenticated Whop browser session: https://whop.com/aditor-wisdom/exp_kLsfFtlUrXJejl/app/ . Test inside the actual Whop desktop/mobile surface,
including dialogs, file chooser, clipboard/share, frame policy, storage and session refresh.
Production changes still require the existing deployment/acceptance workflow.

Official reference verified while investigating:
https://docs.whop.com/developer/guides/authentication
Whop sends `x-whop-user-token` on same-origin requests; identity verification and access checking
are distinct steps. Current docs warn the TypeScript verifyUserToken helper isn't available in the
current SDK, so don't blindly copy that snippet or install an SDK based on an older example.

## Whop entry located (follow-up)

- Community navigation: Tools → Aditor Review. Direct member link:
  https://whop.com/aditor-wisdom/exp_kLsfFtlUrXJejl/app/
- The visible iframe launch URL points to `https://6u351kq2ku1qwtjfmpye.apps.whop.com/o/`.
- The iframe renders the existing **Your AutoReview report** sign-in surface with email and
  Sign in with Whop. It does not render the new FreeFrame owner overview.
- Whop was already signed in as Alan and set to Preview as Admin. This proves the installed app
  and target surface, not new-member authentication or plan access. No membership, app settings,
  credentials, billing, or permissions were changed.
- The Worker spec `2026-09-03-review-iframe-handshake.md` identifies the Review app as
  `app_xSpqlhgkn1AX2J` and records its separate Suite owner-session handshake.

## Next action clarified after opening Whop

The current FreeFrame source was checked again: no Whop/Suite owner exchange route is present.
Clicking the visible Sign in with Whop action inside the current Whop Review iframe returned to
its existing AutoReview sign-in surface; no successful owner session was observed. No credentials,
email, consent, or app settings were submitted. This is a reproduction, not a root-cause diagnosis
of the existing Worker login.

Implementation and acceptance order:
1. Backend identity exchange, customer isolation and entitlement contract, with regression tests.
2. Frontend same-origin Whop entry, correct session/reload handling and recoverable errors.
3. Staging acceptance with two independent customer accounts, then production deployment through
   the existing approval process and actual Whop app target update. Only then announcement-ready.

Alan explicitly authorized Codex to take over the missing Whop backend addition.
Local implementation and validation are recorded in `2026-09-28-whop-launch.md`;
production membership acceptance and app target changes are still pending.
