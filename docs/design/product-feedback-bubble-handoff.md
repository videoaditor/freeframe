# Design handoff — AutoReview feedback bubble

## 1. Job
Authenticated AutoReview customers can report a product bug or request a feature without leaving their work. Mobile and desktop web. Success is a server-confirmed receipt, not a simulated chatbot reply.

## 2. Navigation
One persistent bottom-right Feedback pill opens one Radix dialog: compact corner panel on desktop, bottom sheet on mobile. Close, Escape, or outside click return to the current page and retain drafts. Existing staff inbox remains /feedback. Available for ordinary, paid, active-preview and expired-preview accounts; no public guest data route added.

## 3. Hierarchy
Header “What can we build to make this the best it can be?”; helper “Our tech team is highly caffeinated and doesn’t take holidays.”; small Bug / Feature segmented toggle; one message field; microphone and Send. Success confirms saved message. No fake live-agent avatar, typing dots, unread badge, automatic opening or response-time promise.

## 4. Components
- Labelled Feedback pill, message icon, 48px touch target, restrained orange accent.
- Compact panel with close button, a compact segmented toggle using native radio inputs with 44px targets.
- Labelled textarea, context copy, count, inline retry error, one primary send button.
- Existing receipt and server-owned attribution preserved. Optional voice recording: save original privately on the server before Wispr transcription, retain it on provider failure, attach it to the final feedback. Show audio storage/transcription disclosure before recording. Maximum two minutes.

## 5. States
Empty: useful prompt per type, disabled Send. Sending: disabled input + Saving feedback. Failure/offline: draft stays, retry same request identity. Success: confirmation and Done; reopen starts a new message. Dismiss/reopen retains unsent draft and kind.

## 6. Tokens
Reuse existing app font/semantic colors; local accent uses OKLCH. 4/8 spacing, 16px input, 20px title, 14px supporting text. 200ms opacity/translate entrance, reduce-motion disables movement. Desktop max width 360px; mobile max height 90dvh and safe-area bottom padding. Bubble elevated 88px on asset viewer to avoid bottom playback/composer controls. z40 launcher, z50 dialog above launcher; existing global overlays win.

## 7. Accessibility
44px+ touch targets, visible focus, radio keyboard behavior, Radix focus trap/return, labelled dialog, status/alert announcements. 200% zoom and 375px layout must remain scrollable. Light/dark contrast uses existing semantic tokens; widget secondary text avoids tertiary low contrast.

## 8. Decisions
User already requested chat-like easily accessible feedback + feature wishes, durable storage + daily #automations delivery. Reuse existing API/digest; no separate chatbot service or new scheduler. Keep clinical content out of product feedback reminder already present.

## 9. Review
Verify one launcher for each account state, draft retention, retry identity, feature kind persistence, receipt only after response; screenshot desktop/mobile light/dark. HIG adaptation: desktop corner dialog rather than native centered sheet, because user explicitly requested chat-like access. No draggable grabber since not resizable.

## Prior iteration verification — 2026-10-07 (before voice/copy revision)
- Desktop 1280×720 and mobile 375×812 inspected in light and dark via CUA screenshots; no clipped fields or horizontal scroll observed.
- Native radio selection, closing/reopening draft, and focus return checked in browser; server confirmation/retry states exercised by existing integration tests.
- Frontend: 537 tests pass under Node 22.22.3, production build and typecheck pass. Lint exits 0 with existing repository warnings. Initial Node 25 run failed because its global localStorage conflicts with jsdom; unchanged suite passes under supported Node 22.
- Backend unchanged: 461 pass, 51 skip (existing environment-dependent checks).
- Live read-only config: beat is running; PRODUCT_FEEDBACK_SLACK_TOKEN is absent. Daily posting is not active and no live Slack digest has been claimed.
- Screenshots: [before](feedback-bubble/before.png), [desktop light](feedback-bubble/desktop-light.png), [mobile dark](feedback-bubble/mobile-dark.png). Full four-mode captures are in the Downloads run folder.
- Local preview route was temporary and removed before production build; screenshots show the real component in an isolated preview shell, not a deployed dashboard.

## Current revision verification plan
Capture revised desktop/mobile in both themes. Test microphone denial, stop/close/unmount cleanup, pending permission cancellation, failed upload retry preserving original UUID/blob, transcription failure preserving saved audio, and transcript append preserving typed edits. No live Wispr success claim without configured API access. Recordings are private; only owner/staff may fetch playback.

## Current revision review — 2026-10-07

| Before | After | Why |
| --- | --- | --- |
| Two large category cards, 400px panel | 44px Bug / Feature segments, 360px panel | Smaller footprint with native radio keyboard support |
| Corporate heading and receipt ID | User-approved caffeinated-team copy and short confirmation | Direct invitation without technical clutter |
| Text only | Explicit microphone, original recording and editable transcript | Fast input with recoverable audio on provider failure |

Desktop 1280×720 and mobile 375×812 screenshots inspected in both themes: title and footer wrap, no horizontal overflow, controls remain visible. Radio selection and draft preservation verified in browser. No ambient microphone captured during visual QA. A timing review found the strict two-minute limit edge; automatic stop now uses a one-second safety margin with regression coverage. Full PostgreSQL upgrade/downgrade/re-upgrade passed in an isolated disposable database. Wispr live acceptance still needs its key. Screenshots: [desktop](feedback-bubble/compact-desktop-light.png), [mobile](feedback-bubble/compact-mobile-light.png), [dark desktop](feedback-bubble/compact-desktop-dark.png), [dark mobile](feedback-bubble/compact-mobile-dark.png).

## Open-source dictation revision — 2026-10-07
User correction: OpenWhispr-style open-source dictation, minimal Codex-like waveform. Replace undeployed Wispr REST integration with configured local whisper.cpp CLI (the local engine used by OpenWhispr), using existing bounded mono16k WAV conversion. No new web dependency, SaaS key, desktop install for customers, or external audio transfer. Original audio remains private and saved first. Missing local model/binary returns existing voice-note fallback.

UI: seven small monochrome rounded bars in the existing Stop control, driven by the actual microphone RMS via Web Audio, no random animation. Silence stays quiet. 44px Stop target, visible elapsed time, same small panel. Reduced motion freezes the decorative wave while timer/Stop remain functional. Close/stop/unmount releases analyser/context along with microphone. No new color/type scale. Minimal bounded revision to existing component and transcription adapter; existing user-approved compact form/retention flow remains the implementation brief.

Open-source revision validation: waveform inspected in the real component at desktop/dark and 375px/light using a synthetic microphone stream (no ambient speech captured). RMS bars change with signal; Stop/timer fit without clipping. 549 frontend tests and493 backend tests pass (51 existing skips). Actual local whisper.cpp CPU2/base transcribed39s source audio in18.45s; minor word errors require editable text. Production binary/model, real microphone-to-storage and deployment remain unverified.
