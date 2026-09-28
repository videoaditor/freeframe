# Project Kanban — design handoff

## 1. Job
Brand owners scan where deliveries are, without opening projects. Existing overview on desktop and mobile web. Success: see every live request in its actual stage and notice review/correction transitions.

## 2. Screens and navigation
Board replaces the overview request list in place. Project links and share sheets retain their existing behavior. Closed/expired requests remain available in a disclosure below the board. Existing sidebar and phone tabs stay unchanged.

## 3. Hierarchy
Overview metrics → Projects heading and search → four stage columns → editor performance and brand rules. Board uses full available width. On narrow screens it scrolls horizontally within its own region, with a visible next-column edge and keyboard access. Ready metric retains its existing filter; a clear action returns to all stages.

## 4. Components
| Element | Pattern | Label | Behavior |
|---|---|---|---|
| Board | Named sections and lists | With editor / In review / Corrections / Ready to go | Status from API; no manual status override |
| Card | Project link + share button | Actual title, brand, files, editor | Real content; no drag affordance |
| Search | Search field | Find a project | Filters all stages |
| Motion | Toggle button | Pause motion / Resume motion | Stops ambient and transition motion |
| Closed history | Disclosure | Closed requests | Retains closed and expired states |

## 5. States
No requests: existing request-files action. No matches: Clear filters. Loading: four reserved lane skeletons. Error: Retry and honest stale-data warning. Empty lane: quiet “No projects here”. Ready means existing API availability, not a new claim of manual approval. Zero-file requests stay With editor regardless of gate status. Closed requests never enter live lanes.

## 6. Tokens
Reuse blue + neutral OKLCH glass palette and 4/8px grid. 16px card titles, 13px metadata, 14px lane labels. 16px lane gaps, 12px card gaps, 16px card padding. Real lane changes glide for 280ms using transform/opacity and ease-out; reviewing scanner and correction pencil use small decorative loops. Ready check appears once. No fake progress or timer. Reduced motion removes movement; pause available. Timing and board pattern are product decisions, not HIG requirements.

## 7. Accessibility
44px controls, labeled share and motion buttons, visible keyboard focus, named stage lists, text states in addition to icons/color, polite status-change announcement. Horizontal board scroll is focusable. Card titles wrap. Reduced-motion preference checked for CSS and JavaScript animation. No new dependencies.

## 8. Decisions
Automated board, not manual drag-and-drop: backend owns review states. Existing closed history retained. Mobile lanes maintain readable card widths rather than compressing four columns.

## 9. Verification
Stage classification, closed/expired separation, sharing, status changes, paused movement and reduced motion are covered by component tests. Browser checks used the controlled local API for the overview and a temporary isolated React harness for real component transitions (removed after verification).

| Before | After | Why |
|---|---|---|
| Flat request list | Four named stages with individual counts | Shows the delivery pipeline at a glance |
| Instant relocation | 280ms transform/opacity travel on real stage changes | Keeps the changed project visually traceable |
| Static activity | Small scanner/pencil loops with Pause motion | Makes ongoing work visible without invented progress |
| Ready filter can be offscreen on phones | Ready metric also reveals its lane | Keeps the requested action visible |

Browser evidence: review → corrections → ready changed the actual rendered lane and polite announcement. During the ready transition, computed transform was `matrix(1, 0, 0, 1, -265.059, 0)` and settled to `none`. Paused updates were instant and scanner animation-play-state was `paused`. No production review was submitted.

Search/no-match/clear, share-sheet opening and Escape, pause/resume, ready metric lane reveal, and keyboard access to offscreen cards checked. No document overflow at 375, 689 (user's viewport), or 1280px. The board itself scrolls horizontally on smaller screens. Light and dark screenshots inspected. Saved screenshots: `/Users/alansimon/Downloads/aditor-overview/kanban-light.png` and `kanban-mobile-dark.png`. Temporary viewport reset.

Build, typecheck, full test suite and lint results are recorded in owner-overview-verification.md. Physical screen-reader and 200% text zoom remain unverified.

Sources: Apple HIG local motion mirror and existing overview handoff; Emil design engineering transform/opacity and WAAPI guidance.

## Ready-first correction (2026-09-28)
Owner priority is finished deliveries: Ready to go → Corrections → In review → With editor.
The ready metric opens a single ready-only lane. Request titles navigate to the request's own
folder (`folder_id` from the existing backend contract); legacy responses without it fall back
to the project. No extra navigation or controls. Validate card → correct folder → playable demo
file, as well as each empty/waiting folder, in the local preview. Preview fixtures must return
real API collection shapes and 404 for unsupported reads instead of success-shaped empty objects.
