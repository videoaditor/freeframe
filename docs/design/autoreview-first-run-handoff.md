# AutoReview first-run handoff · 2026-10-08

## Job
A new AutoReview customer starts useful work: optional brand guide → first briefing → real editor upload link → existing dashboard. Mobile/desktop web, including the Whop iframe. User requested this exact flow; implementation is authorized. Reuse the current Aurora Suite setup: cool OKLCH dark stage, silver primary buttons, blue AutoReview icon, compact system type. Source: telehealth-october-suite/docs/design/setup-aurora and live pages.aditor.ai/suite/setup; the older July orange-card wizard is not the active reference. Existing software review: https://feedback.aditor.ai/r/6-gspYpSgakJAGRnAGeWi9ZZxoJXTplj; tracking https://trello.com/c/dzLcYXZF.

## Navigation and hierarchy
Whop checkout leads into Whop; its AutoReview experience opens the same Next web app (/whop → /home). Standalone email/Google also reaches /home. New customer owners without requests enter /start. Editors/staff/existing work and deep-linked uploads stay in their existing flow. /start uses the existing campaign boundary; no change to access rights or expiry.

1. Welcome: AutoReview icon; short animated illustration of brief → review → delivery; one sentence on existing Aditor best practices; Get started. No fake training/load counts or timed delay.
2. Brand: existing owned brand selector or brand name; optional PDF/Markdown/text guide dropzone, paste field, Read my brand kit. Returned suggestions require explicit Use rule; never auto-activate. Skip brand kit remains available. Existing projects/rules are server truth.
3. Briefing: title, real file/link/text input; Create upload link. Complete ads default for first onboarding assignment. Error retains inputs and idempotency key.
4. Link: real returned URL, copy with truthful failure fallback, Upload an ad yourself alternative, Open dashboard. Existing request begins in Awaiting upload/Waiting for files.

## State
Progress stored using existing authenticated user preferences (project/request IDs and step only). No migration, no new auth or upload API. Reload resumes saved progress; successful request is persisted regardless of clipboard state. Failed data load never means empty account. Finished/later flag stops automatic redirects; empty dashboard provides setup entry. Existing users can explicitly reopen /start. Request creation retains idempotency across retries. Recover project creation by re-reading owned brands before retry. No rights inferred from client preferences.

## Tokens/components
Existing owner-workspace semantic tokens with OKLCH local surface accents; system font. 34/41 heading,17/24 body,13/18 footnote; 4/8px grid; minimum44px controls; focus rings; max1 primary CTA per step. Desktop content max568px; no sidebar during setup. Silver primary actions; cool-blue rules/progress; no decorative paragraphs. Animate opacity/translate 220ms; first welcome stagger only. Reduce Motion removes transforms/delays. No sound, autoplay, or video player.

## States and accessibility
Loading: named status and real retry on fetch errors. Empty: action to add brand/brief. Import unavailable/invalid: visible alert, retain file/text, offer skip. Suggestions missing after import: no invented success, refresh retry. Save failure: stay on same screen. Clipboard denial: selectable URL retained. Screen heading focused on step changes; inputs labeled; status announced politely; keyboard drag-drop alternative. 320/393/1440px inspected. Native 200% zoom and OS Reduce Motion are not yet manually exercised; CSS includes a reduced-motion override. Light/dark semantic colors.

## Verification checklist
- [x] signup destinations and ownership gates covered; checkout configuration created/read back with direct AutoReview experience return
- [x] brand skip, import approval, failed API/retry and resume tests
- [x] briefing payload and idempotent request creation tests
- [x] real API payload/returned link wired; successful browser copy in local fixture; API failure retains link
- [x] local-fixture mobile/desktop screenshots and file chooser; reduced-motion CSS inspected (OS setting/zoom still untested)
- [x] backend 754 passed/11 skipped; frontend 621 passed plus one new redirect regression (5-file tests passed); production build passed. No live media/engine acceptance claimed.

## Boundaries
This software flow does not repair the separate review-engine detection or earlier ad-upload acceptance defects. Real engine acceptance still required before marketing readiness. No medical/legal assurance. No fake invitations or other Suite tool setup.

## Evidence and checkout
Screenshots: `docs/design/images/autoreview-first-run/`. They are explicitly labelled local visual fixtures; the fixture API is not shipped. Before: new customers opened the empty dashboard, with no guided brand/brief/link sequence. After: `/home` gates eligible new customers into `/start`.

Prepared Whop checkout configuration `ch_AIFt0L34X8j5HzK` uses existing `plan_azKoPwtp2CPfM` ($0 one-time, $0 renewal), redirects to `https://whop.com/aditor-wisdom/exp_kLsfFtlUrXJejl/app/`. Purchase URL: `https://whop.com/checkout/ch_AIFt0L34X8j5HzK/`. Activation requires updating only the Suite `TELEHEALTH_PREVIEW_CHECKOUT_URL` after deploying this web build; no plan/entitlement changes. A fresh completed checkout after activation remains an explicit acceptance check.

## Briefing input revision · 8 October
User-approved: link-first drop field with explicit Paste link action; denied clipboard access reveals a URL input. Text collapses behind underlined “Paste text instead”; keeps its value when collapsed. No nested buttons. Autofill project titles from selected file names, Markdown headings, public Google Docs titles or readable link slugs. Private/unavailable titles keep the editable name; never guess a document ID as a title or overwrite manual edits. Shared title suggestion used in onboarding and Request files. Title lookup accepts only a canonical fixed Google Docs destination, authenticated, no redirects/credentials forwarded, bounded bytes/time. Layout retains 44px actions, semantic labels, Aurora tokens and no sound.
