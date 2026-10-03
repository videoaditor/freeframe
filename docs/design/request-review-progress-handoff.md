# Design handoff — request review progress

## 1. Job
An invited video editor needs to know the upload is safe, what is happening, and roughly how long analysis takes. Mobile and desktop web. Success: genuine feedback replaces the waiting card automatically.

## 2. Screens and navigation
The existing /r/token workspace holds preparing, queued, analysing, retrying, unavailable and finished states. No navigation or modal changes. Final feedback uses the existing player.

## 3. Hierarchy
Submitted frame; actual process step; subtle phase bar; measured analysis expectation and elapsed; secondary pause/recovery action.

## 4. Components
Thumbnail preview with brief scan; status heading “Review in progress”; step text “Preparing video”, “Waiting for review”, “Reading the brief”, “Checking the video”, “Preparing feedback”; progress bar labelled “Review steps” with no fabricated percentage; “Check again” or “Retry preview”; animation pause control.

## 5. States
Empty: existing upload. Loading: scan runs one cycle (3.6s), parks; step text changes only with evidence, subtle active segment persists. Estimates label analysis time and exclude queue. Missing history: “Learning typical review time”. Overrun: “Taking longer than usual. Your review is still running.” Error/offline: preserve media, stop motion, show recovery. Done: waiting card exits only after actual exact-version verdict, existing feedback appears.

## 6. Tokens
Existing semantic OKLCH light/dark colors, 4/8px grid. Heading18px, body16px, supporting14px. Controls44px. Step transition150ms opacity/transform; active segment linear; scan3.6s one cycle. Reduce Motion: static scan/segment, no text animation. No new dependency.

## 7. Accessibility
44px controls, focus rings, status live region for steps only; elapsed timer not announced every second. No color-only states. Responsive wrapping at390px, no primary clipping at200% zoom. Existing text colors with4.5:1 body contrast.

## 8. Decisions
Alan approved this bounded change with expectation required and scan parking. No open design questions.

## 9. Review checklist
Pending actual screenshots: desktop/mobile, light/dark, parked loading, overrun and unavailable, reduced motion. Check labels, controls, navigation and no overflow. Evidence will be recorded after implementation.


## Acceptance evidence (2026-10-03)
Browser-verified actual RequestWorkspace at desktop and390px: dark/light loading, parked scan, time overrun, unavailable. Local fixtures drive status; uploaded demo supplies the frame. Screenshots in Alan's Downloads/autoreview-progress-proof. No horizontal overflow. Scan parks after3.6s; fault removes activity and retains preview. Secondary action remains44px. Self-critique caught a transparent alpha utility on the fill; fixed with semantic OKLCH color-mix before screenshots. Reduced-motion rules statically checked; no system preference was changed. Temporary preview route removed before build.

Public PR screenshots use only the repository's media regression fixture (assets/review-progress-before.jpg and assets/review-progress-after.jpg); customer footage stays in local Downloads evidence. The before image reproduces the old missing-version status, the after image renders the approved pending status.
