# Design handoff — AutoReview feedback bubble

## 1. Job
Authenticated AutoReview customers can report a product bug or request a feature without leaving their work. Mobile and desktop web. Success is a server-confirmed receipt, not a simulated chatbot reply.

## 2. Navigation
One persistent bottom-right Feedback pill opens one Radix dialog: compact corner panel on desktop, bottom sheet on mobile. Close, Escape, or outside click return to the current page and retain drafts. Existing staff inbox remains /feedback. Available for ordinary, paid, active-preview and expired-preview accounts; no public guest data route added.

## 3. Hierarchy
Header “Help shape AutoReview” + short invitation; Bug / Feature request choice; one message field; Send feedback. Success confirms saved message. No fake live-agent avatar, typing dots, unread badge, automatic opening or response-time promise.

## 4. Components
- Labelled Feedback pill, message icon, 48px touch target, restrained orange accent.
- Compact panel with close button, two selectable cards using native radio inputs.
- Labelled textarea, context copy, count, inline retry error, one primary send button.
- Existing receipt and server-owned attribution preserved. No upload attachment scope in this iteration.

## 5. States
Empty: useful prompt per type, disabled Send. Sending: disabled input + Saving feedback. Failure/offline: draft stays, retry same request identity. Success: confirmation and Done; reopen starts a new message. Dismiss/reopen retains unsent draft and kind.

## 6. Tokens
Reuse existing app font/semantic colors; local accent uses OKLCH. 4/8 spacing, 16px input, 22px title, 14px supporting text. 200ms opacity/translate entrance, reduce-motion disables movement. Desktop max width 400px; mobile max height 90dvh and safe-area bottom padding. Bubble elevated 88px on asset viewer to avoid bottom playback/composer controls. z40 launcher, z50 dialog above launcher; existing global overlays win.

## 7. Accessibility
44px+ touch targets, visible focus, radio keyboard behavior, Radix focus trap/return, labelled dialog, status/alert announcements. 200% zoom and 375px layout must remain scrollable. Light/dark contrast uses existing semantic tokens; widget secondary text avoids tertiary low contrast.

## 8. Decisions
User already requested chat-like easily accessible feedback + feature wishes, durable storage + daily #automations delivery. Reuse existing API/digest; no separate chatbot service or new scheduler. Keep clinical content out of product feedback reminder already present.

## 9. Review
Verify one launcher for each account state, draft retention, retry identity, feature kind persistence, receipt only after response; screenshot desktop/mobile light/dark. HIG adaptation: desktop corner dialog rather than native centered sheet, because user explicitly requested chat-like access. No draggable grabber since not resizable.

## Verification — 2026-10-07
- Desktop 1280×720 and mobile 375×812 inspected in light and dark via CUA screenshots; no clipped fields or horizontal scroll observed.
- Native radio selection, closing/reopening draft, and focus return checked in browser; server confirmation/retry states exercised by existing integration tests.
- Frontend: 537 tests pass under Node 22.22.3, production build and typecheck pass. Lint exits 0 with existing repository warnings. Initial Node 25 run failed because its global localStorage conflicts with jsdom; unchanged suite passes under supported Node 22.
- Backend unchanged: 461 pass, 51 skip (existing environment-dependent checks).
- Live read-only config: beat is running; PRODUCT_FEEDBACK_SLACK_TOKEN is absent. Daily posting is not active and no live Slack digest has been claimed.
- Screenshots: [before](feedback-bubble/before.png), [desktop light](feedback-bubble/desktop-light.png), [mobile dark](feedback-bubble/mobile-dark.png). Full four-mode captures are in the Downloads run folder.
- Local preview route was temporary and removed before production build; screenshots show the real component in an isolated preview shell, not a deployed dashboard.
