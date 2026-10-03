# "Continue with Google" on feedback.aditor.ai/login — Spec · Größe: M

## Warum
Brand owners (Gmail / Google Workspace) should get into the Aditor Review workspace in one click. A
magic code that lands in spam loses a first customer. Alan, 2026-10-03: "bau google". Apple: no
(relay emails break the email identity, extra yearly key upkeep).

## Was
A "Continue with Google" button above the email field on `/login`. Google returns a verified email;
that email signs in exactly like a verified magic code: existing account → that account; unknown
email → new customer account **only if `SELF_SIGNUP_ENABLED`** (same switch as email signup, Alan's
decision). Button only shows when Google is configured.

Identity rule: **the verified email is the person.** Google and the magic code resolve to the same
user row. Tracking across Aditor tools stays email-keyed (Suite spine already dedupes on normalized
email); no spine call in this spec (Alan's decision).

## Grenzen
- **Muss:** state/CSRF check, `aud`/`iss`/`email_verified` check, client secret server-side only,
  inert until configured, same deactivated/no-enumeration behaviour as magic code.
- **Darf nicht:** new dependency for JWT verification (id_token comes straight from Google's token
  endpoint over TLS → decode + claim check is enough, per Google's OIDC docs); store Google tokens;
  touch the Whop flow or `ff_auth_provider=whop` semantics; create staff accounts.
- **Out of Scope (YAGNI):** Apple, account linking UI, Google avatar/name sync, spine sync,
  `/admin`, review.aditor.ai Worker.

## Ausgangslage
- `apps/api/routers/auth.py`: `send_magic_code` (self-signup via `_create_customer`, gated by
  `settings.self_signup_enabled`), `verify_magic_code` (activate + `TokenResponse`), `whop_session`
  (external identity → `TokenResponse`). Follow `whop_session` for the token response.
- `apps/api/config.py`: env-driven settings — add `google_client_id`, `google_client_secret` (default "").
- `apps/web/components/auth/login-form.tsx`: email → code flow. `apps/web/lib/auth.ts:setTokens`.
- `apps/web/app/(auth)/whop/page.tsx`: pattern for a page that trades an external identity for tokens.

## Tasks
- **T1 API** — `GET /auth/google/config` → `{enabled}`; `POST /auth/google` `{code, redirect_uri}` →
  exchange at `https://oauth2.googleapis.com/token`, check claims in a pure helper
  (`services/google_auth.py`), then `get_user_by_email` → else `_create_customer` iff
  `self_signup_enabled` → deactivated/none = 401 generic; set `email_verified`, activate pending;
  return `TokenResponse(needs_password=False)`. Rate-limited like `/whop`. Settings + `.env.example`.
  · **Verifiziert:** `python -m pytest apps/api/tests/ -v` incl. new `test_google_auth.py`
  (mocked token endpoint): existing user, new user with flag on, new user with flag off → 401,
  deactivated → 401, wrong aud / bad iss / unverified email → 401, unconfigured → 404/disabled.
- **T2 Web** — button in `login-form.tsx` (hidden unless `/auth/google/config` says enabled) →
  `/login/google` route builds the Google authorize URL (`openid email`, `prompt=select_account`,
  random `state` in a short-lived SameSite=Lax cookie) → `/login/google/callback` page checks state,
  POSTs code to the API, `setTokens(..., 'email')`, routes like a successful magic code. Errors →
  back to `/login` with one readable message. Google brand guidelines for the button (white, "G" logo,
  "Continue with Google"). · **Verifiziert:** `pnpm --filter web build`, `test`, `tsc --noEmit`,
  `lint`; component test: button hidden when disabled, state mismatch → error message.

## Done
All CI commands from AGENTS.md green; new API tests and web test as listed pass; screenshot of the
login screen with the button (dark) in `docs/design/` . Live acceptance is Alan's: after the two env
values are set, one real Google login lands in the workspace.

## Stop & Eskalation
- Needs the Google OAuth client (Alan, Google Cloud Console) — code ships inert without it, no stop.
- Any change to Whop sign-in behaviour or the token/refresh contract → stop.
- An email already used by a staff account signing in via Google is fine (same person); anything
  that would create or elevate staff → stop.

## Doctrine-Gate
- [x] **M1** Purpose, non-goals (Apple, spine sync, linking UI) explicit.
- [x] **M2** No new dependency; reuses user model, self-signup switch, TokenResponse.
- [x] **M3** Done = CI commands + listed tests; stops explicit.
- [x] **1 State:** `users` table is the source of truth; identity = verified email; nothing stored from Google.
- [x] **2 SoC:** claim validation pure in `services/google_auth.py`; router only wires.
- [x] **3 Idempotenz:** repeat logins hit the same user (unique email); `_create_customer` IntegrityError path reused.
- [x] **4 Coupling:** additive endpoints; `TokenResponse` unchanged.
- [x] **5 Context Window:** two tasks, ~6 files.
- [x] **6 Error-Taxonomie:** state mismatch / Google error / unverified / wrong aud → `/login` + message, API 401 generic; unconfigured → button hidden.
- [x] **7 Defensive:** CSRF state, server-side secret, claim checks, self-signup switch respected.
