# Timeline scrubbing — 2026-10-04

## 1. Job
Alan needs to drag backward/forward to a video second and comment while the preview stays visible. Mobile web plus desktop. Success: dragging the timeline changes the actual video and timestamp composer continuously, including backwards; releasing outside the track does not leave it stuck.

## 2. Navigation
Existing share → asset review. No new route/dialog. Timeline sits between video and transport. Existing show/hide comments navigation retained.

## 3. Hierarchy
Video → large scrubber → spaced second labels → existing transport → comments composer. No new primary action or explanatory technical copy.

## 4. Components
Use a real native range input labeled "Video timeline" rather than mouse-only div.48px hit band,8px drawn track,20px always-visible native thumb. Browser handles touch, pointer drag and keyboard. Live onChange seeks;0.1s keyboard steps. Existing buffered and comment ranges/markers retained. Six evenly spaced seconds labels, no hover dependency for mobile. Keep desktop frame previews on hover.

## 5. States
Duration unknown/zero: disabled slider, no misleading seek. Normal: clamped current value, elapsed scale. Loading/error/permissions keep existing player behavior. Slider itself needs no network or authentication.

## 6. Tokens
Existing semantic background/border/accent/text tokens and font family retained.4/8px spacing grid,16px side padding, labels12px tabular. No seeking animation, focus ring visible. No new colors, palettes or font downloads.

## 7. Accessibility
Native slider semantics; aria value text in seconds; native Home/End/arrows.48px hit target and visible20px thumb, no touch hover requirement. Track respects disabled state. Screen reader/real Safari touch/keyboard are manual device checks; actual browser drag/keyboard and mobile/desktop screenshots verified before rollout.

## 8. Decisions
Alan explicitly asks for an easier, more spaced timeline. Minimal native slider fixes the4px mouse-only cause; no timeline zoom engine or new editor features.

## 9. Review
Red regression before code, full frontend tests/typecheck/lint/build, actual browser drag both directions, release outside, keyboard seeking, seconds composer sync. Mobile390×700/390×500 and desktop1024×768 screenshots must retain preview+composer. Original code/image rollback preserved, Web-only rollout. No comments sent.

## Verified before rollout
Regression4/4 failed before and4/4 passed after. Full frontend500tests/73files passed;TypeScript passed after correcting a test-only nullable mock-call expression;lint passes with baseline warnings;production build passes. Browser: native drag23.883333→43.667886→8.338327, outside release→0; End→47.766667 and ArrowLeft→47.666667; video currentTime and composer follow.48px slider atCSS390×700 and390×500;desktop1024×769. Actual device touch/VoiceOver remain manual checks. Screenshots in the run, no comment sent. Runtime progress-bar source was frozen for build and browser proof; only test typing was repaired afterward.
