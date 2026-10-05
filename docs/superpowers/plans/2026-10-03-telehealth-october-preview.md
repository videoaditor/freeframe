# Telehealth October preview implementation plan

> For agentic workers: execute the scoped tasks below against the validated design. Independent Suite, feedback and landing work may be delegated under the dispatching-parallel-agents skill; integrate through the interfaces below. No production deployment until the candidate passes its acceptance checks.

Goal: deliver a working free AutoReview campaign, with one brand, an absolute November 1 Eastern cutoff, durable feedback and one daily Slack digest.

Spec: `../specs/2026-10-03-telehealth-october-preview-design.md`.

Architecture: Whop grants a separate free product. Suite owns the campaign and computes effective permissions; FreeFrame consumes attested access, stores workspace/feedback/usage, and handles the paywall. Pages hosts the offer using Suite's public campaign configuration. Existing paid access remains intact.

Global constraints: campaign ID `telehealth_october_2026`; tier `review_preview`; cutoff `2026-11-01T04:00:00Z`; primary tool `autoreview`; one brand workspace for preview-only owners; two editor seats; recommendation threshold 20 distinct successfully reviewed ads; no card or automatic conversion. Slack target `C07UL6BAG1Z`, daily 00:00 UTC, silent when empty. No campaign emails sent by this build.

Review focus: paid and preview memberships in any order; cutoff under cached/long-lived sessions; guest upload bypass; concurrent brand creation; persisted feedback followed by Slack timeout.

## 1. Suite campaign and access policy

Workspace `/Users/alansimon/Downloads/telehealth-october-suite`.

- [ ] Add failing tests for cutoff boundary, owner/editor scopes, paid coexistence, repeated enrollment and durable cohort attribution.
- [ ] Add a small campaign module and additive enrollment storage; add `review_preview` tool/seat policy. Whop product ID comes from existing `WHOP_PLAN_TIERS` configuration, never a public query flag. Preserve unrelated identity fixes on current main.
- [ ] Owner and editor entitlement responses include optional `campaign: {id, tool, endsAt, state: 'active'|'expired', previewOnly: boolean}`. Retain attribution after paid upgrade; `previewOnly=false` means paid rights govern access. Denial for cutoff is HTTP 200 with `reason:'campaign_expired'`.
- [ ] Include the same optional campaign object in owner exchange response. Expose `GET /v1/campaigns/telehealth_october_2026` with public `id, tool, endsAt, state, checkoutUrl` only. Checkout comes from `TELEHEALTH_PREVIEW_CHECKOUT_URL`; before configuration or after cutoff it is null. No account data on this route.
- [ ] Test and build; record changed files and deploy configuration. Do not deploy from this task.

## 2. FreeFrame durable feedback and daily delivery

Shared workspace `/Users/alansimon/.codex/worktrees/telehealth-october-preview/freeframe`. Own new feedback modules, migration, task registration, app route registration and feedback UI component. Coordinate `config.py` additions with integrator.

- [ ] Write regressions for validated authenticated input, tenant attribution, idempotency, empty digest, failed Slack delivery and successful checkpoint.
- [ ] New soft-deletable feedback model and Alembic migration; `POST /product-feedback` accepts `{submission_id: UUID, kind:'bug'|'idea', message: string <= 4000, page_path?: string}` and returns persisted `{id,status:'received'}`. Derive user/campaign context server-side, never trust browser author IDs. Authenticated staff list endpoint supports pagination.
- [ ] Daily Celery task at 00:00 UTC posts one consolidated digest to configured Slack channel. Durable batching, single writer, explicit failures/retry. Never execute user feedback as instructions. No new bot credentials generated; env configuration only.
- [ ] Build `ProductFeedback` sheet component with a visible trigger, real loading/error/success states and tests. Integration into dashboard layout is done by integrator to avoid shared edits.
- [ ] Run applicable tests; provide remaining live Slack configuration/acceptance needs. Do not send live messages or deploy from this task.

## 3. FreeFrame campaign experience and enforcement

Integrator owns Whop auth, projects, requests, auth response, campaign modules and dashboard integration.

- [ ] Add failing route tests for one-brand concurrency and cutoff guards, paid bypass, old owner sessions, direct requests and guest links.
- [ ] Persist server-attested campaign context at owner exchange/entitlement refresh; expose safe campaign state. Preserve identity on expired campaign so the paywall is reachable without looping sign-in. Do not turn generic authorization failures into paid offers.
- [ ] Enforce one brand atomically on creation. Allow many requests within the brand. Guest request links may not initiate new uploads/reviews after campaign cutoff; preserve existing stored assets.
- [ ] Show first-brand setup, campaign expiry and Give feedback in the owner experience. At expiry recommend Team at >=20 distinct successfully reviewed campaign assets; otherwise Masterclass + Tools. Keep both choices visible, verify actual checkout values, and preserve paid access.
- [ ] Run complete backend and frontend CI checks; browser-inspect all changed states.

## 4. Telehealth landing

Workspace `/Users/alansimon/Downloads/telehealth-october-pages`, preserve current tracking and Suite changes.

- [ ] Write routing/configuration tests for `/suite/autoreview/telehealth/`, both slash variants, HEAD, disabled checkout and expired offer.
- [ ] Build focused responsive page using validated spec copy, real AutoReview assets and existing design tokens. Server reads Suite campaign config; absent/failed config cannot lead to a wrong paid checkout. No placeholder checkout or fake video button. Loom is optional until supplied.
- [ ] Use absolute assets; add route ahead of generic slug/static match. Include clear end date Eastern Time, one-brand terms and AI-assistance scope. After expiry show paid offer links only when verified.
- [ ] Browser-inspect 320/393/1440 px; record screenshots and test outcomes. Do not deploy from this task.

## 5. Provider configuration, integration and release

- [ ] Create the dedicated hidden Whop free product including only the existing Review experience; configure the verified product ID to `review_preview` and the public checkout URL. Verify no payment/card requirement and intended return destination. Never change existing prices or products.
- [ ] Configure existing Slack bot access if already authorized and available. If app access to the private channel is missing, prepare the exact final user action instead of inventing a webhook or exposing credentials.
- [ ] Deploy candidates from tested revisions with recoverable runtime backups. Recheck current main before merge; preserve ongoing code changes.
- [ ] Fresh real customer: claim -> correct private account -> brand rules -> real synthetic upload -> persisted review -> feedback receipt -> digest. A second owner proves tenant separation. Test expiration using controlled fixtures, without changing the production clock or terminating real customers.
- [ ] Only then mark the email URL ready. If provider signup/terms require user interaction, hand off the exact prepared step and clearly state that acceptance remains incomplete.

Reminder already updated to November 1, 13:15 Asia/Tokyo. Backend scheduler, not this reminder, enforces cutoff and daily feedback delivery.
