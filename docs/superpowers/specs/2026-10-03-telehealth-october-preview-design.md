# Telehealth October preview: AutoReview

Status: product decisions validated by Alan on October 3, 2026; implementation pending. No campaign has been created or deployed. No new-customer end-to-end acceptance has been completed.

## Outcome and agreed offer

Telehealth teams arriving from Alan's email can claim free AutoReview access, add their own brand guidelines, submit ads and report bugs or ideas. All free campaign access ends at one fixed November 1 cutoff. Alan explicitly selected this over 30 days per signup on October 3, 2026.

Confirmed precise cutoff: **2026-11-01 00:00 America/New_York**, equivalent to **2026-11-01T04:00:00Z** and **13:00 Asia/Tokyo**. New York is still on EDT at midnight before that night's clock change. State Eastern Time beside the date in the offer. The campaign must never advertise 30 full days. Someone joining late October gets only the remaining time.

The free claim has no card requirement, recurring price or automatic paid conversion. After expiration the customer chooses a paid offer. AutoReview alone is the entry product. Masterclass/training is not an onboarding prerequisite. Existing paid customers keep their broader rights.

## Doctrine-Gate

- [x] M1 Spec-first: outcome, copy, acceptance and non-goals defined here; Alan validated the five product decisions in chat; scope below incorporates them.
- [x] M2 Start simple: retain Whop identity, existing Suite permissions, FreeFrame workspace and review engine. No second signup system or custom billing service.
- [x] M3 Loop-first: acceptance scenarios and stop conditions below distinguish local checks from actual new-member success.
- [x] 1 State: Whop owns membership; Suite owns effective tool access and campaign cutoff; FreeFrame owns customer content and durable feedback records. No browser-only grant.
- [x] 2 Separation: campaign policy and offer selection are pure functions; routes authenticate, validate and persist.
- [x] 3 Idempotency: campaign identity + verified Whop user identifies enrollment; repeat claims and logins do not reset time or duplicate workspace. Feedback deduplicates by authenticated author + submission ID.
- [x] 4 Coupling: additive campaign metadata in the Suite response, consumed server-side by FreeFrame; existing token audiences and secrets preserved.
- [x] 5 Context: separate changes for Suite access, FreeFrame trial experience, Pages offer; each has a recorded base revision and tests.
- [x] 6 Error taxonomy: named failure behavior below; no success message without durable storage.
- [x] 7 Defensive design: access expires by server time even if a reminder or webhook is delayed. Preserve drafts on recoverable failure and existing paid grants.
- [x] F1 Correct lever: permission and onboarding contracts first; no change to review-model prompts to solve signup issues.
- [x] Tests: pure cutoff/selection tests, real route tests with existing mock-DB conventions, transactional tests where necessary, browser and real-provider acceptance.

## Verified foundation, October 3

| Surface | Evidence | What it proves |
| --- | --- | --- |
| Suite source | `videoaditor/aditor-suite` origin/main `fddd5aaf016ffb6695a0594daf889379996b781b` | `review_solo` already scopes owner access to `autoreview`; two editor seats. A separate product is possible. |
| Whop dashboard | Existing company `biz_vI5cI4OuiQZ6ek`, Products > Create product | Free access, Hide from store page, Auto-expire access and Custom days exist. Inspected an unsaved form only. This proves relative expiry is configurable, NOT a fixed calendar cutoff. |
| New app | FreeFrame origin/main `49cd634936779aaf7ba2d42697c7425576001aab` | Whop session exchange, customer workspaces, guideline import, suggestion approval, request/upload/review flows exist. |
| Review engine | feedback-agent origin/main `dfd86e722bd73be45fe1edb0c57d7393b061a9c9` | Current engine includes per-project sweep lock and upload-priority fixes. Preserve these changes. |
| Marketing | Pages origin/main `38bbf5351bc1b14ab2ba93de06f75e5e708e29a9` and live `/suite/autoreview/` inspected in browser | Public page currently sells Masterclass + Tools; it is not the October campaign. |
| Production | Read-only SSH: `/opt/freeframe` checkout `2c2c09f`; API and web containers healthy | Reachable runtime, not proof that the newly fetched main or every worker fix is deployed. Record image revisions before any rollout. |
| Existing sign-in evidence | `docs/handoff/2026-10-02-whop-desktop-verification.md` and recent “AutoReview Launch-Lücken umsetzen” chat | Alan's Whop owner login and reload worked; this does not substitute for fresh customer or expiration acceptance. |
| Suite health | GET `https://aditor-suite.onrender.com/health` returned 200 | Service responds; no entitlement proof. |

`autoreview.ai` resolves, but ownership and routing to Aditor were not established. Use the existing Pages domain for this campaign; do not buy or repoint a domain without a separate need.

## Recommended route and alternatives

Use a focused page at **`https://pages.aditor.ai/suite/autoreview/telehealth/`**, then a hidden, free Whop product that includes the existing Aditor Review experience. This is a proposed URL, not a published deliverable. Direct the successful claim to the existing Review experience, not the general community or Masterclass.

The existing Masterclass checkout has the wrong offer and implies paid subscription terms. A new standalone authentication system would duplicate working infrastructure and require account migration. Neither is needed for this campaign.

Whop's Custom days option alone is insufficient: a single 30-day plan allows late joiners to run into November. The common cutoff must be enforced in Suite on every applicable access decision, with page enrollment closure using the same timestamp.

## Access contract and gaps to fix

Create the campaign key `telehealth_october_2026`, primary tool `autoreview`, and a distinct mapped preview tier. Keep campaign identity separate from the paid `review_solo` tier so paid standalone users cannot be expired by mistake. Never place keys or access tokens in a marketing URL.

Suite returns additive server-derived campaign information: `id`, `tool`, `endsAt`, `state` (`active` or `expired`). The durable cohort tag remains available after expiry and upgrade. Use verified Whop identity for enrollment; do not use a typed email address or query parameter as proof of access.

Use the same tool restrictions for owners and invited editors. Current `entitlement-routes.ts` passes `plan_tier` into owner decisions but not into `decide()` for editor decisions. Add a regression test before repairing this gap.

Choose effective access across all valid paid and campaign memberships. Joining a free campaign must never downgrade a paid Suite member. Expiry of the campaign must not deactivate an unrelated paid grant. Current membership selection ranks only by seat cap; course and solo tiers tie. Explicitly test membership ordering and equal-cap combinations.

Use server time for cutoff. A long-lived session, saved browser state, fresh login, repeated claim or delayed webhook must not extend free access. Return a named `campaign_expired` denial, preserving account identity and a route to paid options. Paid grants take precedence over expired campaign grants.

Check issued guest request links as well as owner requests: `_live_request()` currently checks link expiry and parent deletion, not the creator's subscription. Free campaign links must not keep creating uploads or review work after cutoff. Allow a clearly defined recovery path for already-stored files; don't destroy customer content. Decide and test in-flight upload completion versus new work so a cutoff cannot silently corrupt a finished upload.

Stop accepting new campaign enrollments at cutoff. Even if someone retains the raw Whop claim link, membership alone must not bypass the expired campaign policy.

## Brand onboarding and review

Each free campaign owner may create **one brand workspace**, enforced server-side and safe against concurrent creates. Additional requests/folders under that brand are allowed; the cap does not limit ads to one. Paid customers keep their existing allowance. The first customer view should offer one clear action: **Set up your brand**. Persist the brand, then import text, URL or PDF guidelines through the existing scoped routes. Show drafted rules for explicit approval. A logo alone is not proof that brand instructions reached the engine.

Test with synthetic brand guidance containing a distinctive non-medical instruction, and two small synthetic ad files that comply/violate it. Verify that approved guidance is used for the correct customer's review and cannot be read or changed by the second owner. Never use real patient data as a fixture.

Alan selected own rules plus editing quality (1A), not a supplied Telehealth regulatory rulebook. Review describes potential issues against the customer's supplied rules. It does not provide a legal compliance certification or guarantee ad-platform approval. Missing processing/review evidence must remain visibly pending or unavailable, never Ready.

The requested “Brandkit … blocken” is interpreted as persisted and tenant-isolated, not permanently uneditable. Do not add an irreversible brand lock without clarification.

## Feedback and usage

Show a persistent **Give feedback** action in the campaign app shell. It opens a small sheet with **Report a bug** / **Suggest an improvement**, one message field and Send feedback. Prefill tool/campaign context server-side. Do not force an email field when a verified contact is already available; Whop's synthetic `user_…@whop.user` address is not a usable mailbox.

Persist feedback before showing success. Store stable submission ID, authenticated author, campaign, tool, kind, message, creation time and triage status. Any optional page path is allowlisted and stripped of tokens/query strings. Attachments are out of scope initially. Provide an authenticated staff queue and a retryable delivery adapter for the eventual task agent; customer text must remain untrusted input, never an instruction to deploy code automatically.

Alan selected a backend plus one daily consolidated post to Slack **#automations**, rather than autonomous implementation of customer requests. Channel verified through the Slack connector: **C07UL6BAG1Z**, private, active, created by Alan. This is explicit authorization to send the daily product-feedback digest to this channel. No immediate per-report posting and no automatic code execution or deployment from feedback.

Persist each report in the application database, then send one daily digest of previously unreported entries. Default schedule: **09:00 Asia/Tokyo** (00:00 UTC), adjustable configuration. Stay silent if there are no new reports. Include tool, campaign, bug/idea, concise message and staff-only source link; omit secrets and unrelated customer media. Mark a batch delivered only after Slack confirms success. Use a durable batch ID/checkpoint and prevent concurrent senders; retries must not lose entries. Report Slack delivery failure separately from successful customer submission. The backend scheduler runs independently of Alan's computer.

Track campaign enrollment, first brand setup, first completed review, successful review totals, active days and distinct submitters. Use successful stored results, not attempts, retries or partial telemetry. Preserve enrollment attribution through paid upgrades. Prefer existing event/usage data to a second analytics stack; reconcile with the ongoing “Tracking und Funnel-Drop-offs überra” work before touching shared tracking files.

At expiry show both paid routes. Alan selected **Team highlighted at 20 successfully reviewed ads during the campaign**, Masterclass + Tools below 20 (3B). Count unique successfully reviewed assets, not failed attempts, repeated polling, repeated analysis, or new versions of the same ad. The threshold is an offer recommendation, not a free-use cap. No automatic charge. Do not advertise unsupported plan usage limits. Actual plan entitlements and checkout totals must be verified immediately before publishing paid copy.

No automatic outbound campaign or follow-up email is authorized in this build. Alan sends the initial invitation; prepare cohort data and drafts as needed. No automatic charge is allowed.

## Landing copy to implement

Hero eyebrow: **EXCLUSIVE TELEHEALTH PREVIEW**

Headline: **Your ad's first review. On us.**

Subhead: **Bring your telehealth brand rules. Catch potential issues in your ads before your team signs them off.**

Offer: **Free until November 1, 2026. No card. No automatic subscription.** Include the precise timezone in the offer terms.

Primary button: **Get free AutoReview access**

Loom: show Alan's supplied video when available. Until then use an existing real product screenshot and concise workflow text; no fake play button or empty video frame.

Workflow: **Add your brand rules. Send an ad. Get timestamped feedback.** Support copy explains that users approve imported rules before those rules apply.

Feedback invitation: **Help shape the launch. Found a bug or have an idea? Tell us inside AutoReview.**

Qualification: **AI-assisted feedback against your guidelines. Your team makes the final compliance and publishing decisions.** No claims of FDA/HIPAA certification or guaranteed ad approval.

FAQ covers the fixed end date, free access with no card, AutoReview-only access, saved brand rules and paid options after the preview. An optional On Demand link comes after the core workflow, not between signup and first review. Do not promise same-day implementation of every idea.

After cutoff replace the free claim with **Choose your plan** and honest expired-offer copy. Close the enrollment route server-side too.

## Design handoff

Web at 320, 393 and 1440 px; preserve AutoReview identity, existing icon, real product imagery and dark visual language. Restrained movement (variance 4, motion 2, density 4). Native CSS/established components; no new design framework.

Use the existing SF/system type stack, body 17/24, footnote 13/18, responsive hero about 36–64 px, 4/8 spacing grid, 44 px touch targets, visible keyboard focus and explicit field labels. Reuse existing semantic OKLCH palette; one orange accent. `theme-factory` was not found in the listed skill roots; do not install an overlapping system just for color ramps.

Screen inventory: campaign landing → hosted Whop free claim → first brand setup → existing overview/review. Feedback opens a dismissible sheet and returns focus to its trigger. Expired access has a persistent plan-selection page; no modal trap. Existing paid sign-in remains a secondary link.

Empty: brand setup action. Loading: named status, never blank. Error: retain entered text, explain Retry. Feedback success: receipt ID only after persistence. Whop or Suite outage: no new access grant; retry sign-in. Loom failure: retain product explanation and CTA.

After build inspect actual screenshots at all three widths, keyboard flow, 200% zoom, contrast ≥4.5:1 for body, reduced motion and iframe reload. Dark-only is an intentional Aditor brand choice. Screenshots and their review findings must accompany the implementation.

## Acceptance and publication gate

1. A fresh external customer claims this exact $0 product without card details, arrives directly in AutoReview, retains the same private workspace after reload, and cannot access paid training or another customer's content.
2. Two independent customers set up guidelines; the first real upload produces a persisted review using approved rules. Retry, service outage, duplicate click, editor upload and a new version behave correctly.
3. Before/exactly-at/after-cutoff tests cover owners, invited seats, direct APIs, guest request links, repeated enrollment and expired tokens. A paid customer retains rights regardless of membership ordering or campaign expiration.
4. Feedback is durable, deduplicated and visible to the owned intake queue. Cohort/usage counts reconcile with stored successful work; simulated failure never shows a sent message.
5. Run Suite test/build, changed Pages tests/typecheck and FreeFrame CI commands (backend pytest, frontend build/test/tsc/lint). Use mock-DB fixtures for normal backend tests; do not mistake them for live storage/identity proof. Inspect mobile and desktop screenshots and perform real Whop membership acceptance before delivering the email URL as ready.

Capture candidate and live revisions/image IDs. Deploy only the focused campaign changes on top of current main; the original local checkouts are stale and contain unrelated changes. Preserve the recent upload/watchdog/engine fixes. Never mark an old handoff's unresolved acceptance as passed because a health endpoint responds.

Stop publication on failed fresh-member enrollment, incorrect pricing/card requirement, missing brand-rule evidence, cross-brand access, missing cutoff enforcement or an unavailable durable feedback destination. If a fresh account requires interactive identity verification or acceptance of terms, request that final human action with the prepared exact checkout link.

## November 1 follow-up

Created the one-time in-chat automation **Telehealth-Trial: Launch und Paywall prüfen**, ID `telehealth-trial-launch-und-paywall-pr-fen`, updated to November 1 at **13:15 Asia/Tokyo**, 15 minutes after the confirmed US-East cutoff. It audits access and enrollment closure, paid routes, existing paid access, and cohort follow-up. It sends no emails and makes no purchases. The automation is a verification backstop, not the expiry mechanism. Update its time and saved prompt if the cutoff timezone changes.

## Current deliverable status

Research and this design are prepared. The fixed-date campaign, cohort tracking, feedback UI, paywall and new landing URL are **not implemented or tested yet**. The Whop creation form was inspected without saving a product. Alan validated 1A, 2A, 3B, backend plus daily Slack #automations digest, and 5A. Proceed with the implementation plan against these decisions.
