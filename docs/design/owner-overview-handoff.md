# Owner overview — design handoff

## 1. Job
Brand owners need to see what is ready, what editors are fixing, first-try delivery quality, and estimated review time avoided. Desktop and mobile web. Success: find a delivery, understand its state, create/copy a request, inspect editor quality without opening individual videos.

## 2. Screens and navigation
| Screen | Entry | Presentation | Exit |
|---|---|---|---|
| Overview | Home | Page | Sidebar / mobile tabs |
| Filtered requests | Search / state filter | In place | All / clear search |
| Request files | Primary button | Radix dialog / mobile sheet | Close / Escape / Done |
| Share request | Row share button | Radix dialog | Close / Escape |
| Review waiting | File uploaded | Inline status | Real completion or error |
Desktop: labeled collapsible sidebar. Mobile: four labeled bottom navigation tabs, account in header. Existing project and rules screens retained.

## 3. Hierarchy
1. Overview heading and Request files action.
2. Estimated time saved (30 days), first-try quality (available history), ready count.
3. Requests with search and state filter; editor performance alongside, brand rules below it.

## 4. Components
| Element | Pattern | Label | Notes |
|---|---|---|---|
| Primary button | Button | Request files | One prominent action |
| Metric cards | Linked summary | Ready to go / Time saved / First-try pass rate | Explicit period and sample count |
| Request queue | List | Projects | Status words and icons, closed links remain distinguishable |
| Share | Sheet | Share request | Anyone with this link can upload; no imaginary permission selector |
| Waiting | Indeterminate progress | Reviewing your file | CSS paper-frame stop-motion; no invented stages or percentages |

## 5. States
Empty: Request your first files, one action. Filter empty: No matching requests, clear filters.
Loading: reserved skeleton cards/rows. Error: inline unavailable message and Retry; never zero or empty as a substitute for failure.
Success: ready status and copy confirmation only after clipboard success. Unauthorized/offline: existing API authentication plus honest unavailable state. First-try unknown: em dash, no reviewed first versions yet.

## 6. Tokens
System sans, 0.8125rem captions, 0.9375–1rem body, 1.25rem section title, 2.125rem page title, 3rem metric. 4/8px spacing with 12/24px control groups. Refinement: blue and neutral only on the owner overview. Frosted blue glass with inset highlights and soft contact shadows; Ready to go is the dominant right-hand card on desktop and first on mobile. Time and quality cards use quieter neutral glass. Blue primary action, folders and status treatments; status wording preserves meaning. Contrasting ink in both themes. Generous 20–24px cards, subtle borders, no decorative chart using made-up values.
Motion: 160–240ms interactions; 2.4s stepped paper-frame loop, decorative only, pause control; reduced motion shows static scene. Upload progress follows transferred bytes.

## 7. Accessibility
44px touch controls, visible focus ring, labels on icons, status not color-only. Radix focus containment and Escape dismissal. Responsive wrapping and 200% zoom. Text contrast >=4.5:1. Sparkline is redundant to linked numeric metric. Performance bars include numbers and sample sizes.

## 8. Decisions
Use existing /insights/editors and /insights/time-saved. No email invites because request links grant upload access and no matching invitation backend exists in this flow. First-try shown per editor to avoid double-counting videos attributed to multiple uploaders. Timing is an estimate from recorded viewing duration and feedback words. No engine model/prompt changes without measured evidence.

## 9. Review checklist
- [x] Browser inspect desktop and mobile, light and dark.
- [x] Request creation, sharing, filters, unknown/error/loading states verified (browser + component tests).
- [x] Focus, Escape and overflow checked; reduced motion verified in CSS. 200% text zoom and physical assistive technology remain unverified.
- [x] Build, frontend tests, typecheck, lint and backend tests run.
- [x] Screenshots and verification limitations recorded in owner-overview-verification.md.

HIG sources: local sidebars, sheets, loading, progress-indicators, writing mirrors. Upload artwork, exact motion timing and blue glass treatments are design choices, not HIG requirements.
