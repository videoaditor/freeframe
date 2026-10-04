# Mobile share review — 2026-10-04

## Job
Alan and clients need to pause portrait video and write a comment attached to the visible second on iPhone. Success: video preview, transport and composer simultaneously visible and reachable at390×700, smaller390×500 keyboard-like viewport and desktop1024×768. Existing access, comment privacy, API/session and original comment identity are preserved.

## Navigation
Existing share gallery → existing asset review. Back returns to gallery. Existing toggle shows/hides comments; keep its collapsed-on-mobile initial preference. Add accessible Show comments / Hide comments labels and44px touch target. No modal or new authentication.

## Hierarchy and layout
Mobile: toolbar48px; media preview top; comments panel bottom (48% of available height). Both panes remain in normal flex-column document flow with min-height0; comments list scrolls internally and composer remains visible. Desktop >=768px preserves right360px sidebar. Dynamic viewport height replaces fixed h-screen where share review root uses it. No sliding animation from the side on compact layout. Existing semantic colors/type and4/8px grid retained; comment input remains16px on mobile to prevent iOS autofocus zoom.

## States
Empty comments retain existing text, loading retain spinner, errors retain existing UI, denied permissions retain view-only. Toggle never covers video. No changes to sends, identity prompt, annotations or credentials. Fields uses same lower panel; list scrolls as needed.

## Accessibility
44px touch toggle with label and aria-expanded. Preserve keyboard focus and established controls. Small preview retains native aspect via object-fit contain and transport. Horizontal scrolling forbidden. Dynamic viewport/200% zoom checked by actual browser screenshots; real Safari keyboard remains a manual check if not simulated.

## Review
Before390×700: video rect390×592 at(0,48), video center hit DIV from comments overlay; composer visible but preview obscured. Screenshots: autoreview-mobile-overlay-before.jpg. After screenshots and DOM hit tests must show visible video + composer with non-overlapping rectangles. Direct shares and collection asset viewers both use in-flow lower comment pane; desktop geometry unchanged.

## Scope/status
Minimal front-end layout patch built from exact deployedb503417 source in an isolated existing-repo remote worktree. No DB/API/worker changes. Preview/test first; rollout only after checks and visual verification. Parent user explicitly identified broken mobile feedback and desired simultaneous preview/comments during commissioned review.
