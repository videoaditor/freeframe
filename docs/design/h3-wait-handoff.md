# H3 wait display — design handoff

## 1. Job
Editors on desktop/mobile web understand what happens to their submitted video, including four-minute ads. Exact-version feedback replaces waiting.
## 2. Screens and navigation
Existing /r/token workspace; no navigation changes. Preparing, queued, reading, finishing, retry, unavailable, done.
## 3. Hierarchy
Existing still frame → genuine phase → indeterminate activity → scoped time expectation → elapsed → recovery.
## 4. Components
Existing ReviewAnalysis only. Text: “Measuring typical wait time”, “Analysis usually … min”, “Feedback usually … min”, “About … min remaining”. Source and scope below. No invented percentage or time carousel. Buttons “Check again”, “Retry preview”, “Pause animation” use existing 44px controls.
## 5. States
Empty/upload unchanged; loading scans once 3.6s then parks; missing samples shows calibration without fallback number; overrun keeps honest running text; offline/failure freezes motion and preserves preview; done requires actual exact-version feedback. New version resets local scan only, elapsed follows server.
## 6. Tokens
Retain current semantic OKLCH light/dark palette and system font. 4/8px grid, 18px heading /16px phase /14px supporting. Phase changes150ms. Status activity linear; Reduce Motion static. Generated UI UX recommendations for landing-page heroes are inapplicable; existing product design wins.
## 7. Accessibility
44px targets, focus ring, live phase only (timer outside live region), no color-only status. 200% zoom and375px wrapping; text4.5:1 in both themes.
## 8. Decisions
Approved in handoff; no open product decisions. No second progress component.
## 9. Review
Browser evidence is in [the verification report](../reviews/h3/README.md). Desktop1440px and mobile375px checked in light/dark; no horizontal overflow, including CSS zoom200%. Minimum measured text contrast6.27:1 light and6.62:1 dark. Scan parked and pause stopped activity in the actual component. Reduced-motion rules are present in browser CSS; actual system preference activation is unverified because the browser provides no media emulation. HIG indeterminate loading guidance applies;3.6s duration is approved product decision, not a HIG number.


| Before → after | Reason | Evidence |
| --- | --- | --- |
| Fixed phase-width fill → indeterminate activity | Avoid a false completion percentage | before/after desktop screenshots |
| Local pickup clock → committed submission clock | Reload retains total elapsed time | 4:17 before reload, 4:18 afterward |
| Broad analysis copy → explicit scope/calibration | No claim of total or remaining time without evidence | cold/total/remaining mobile screenshots |
| Activity during uncertain status → stopped activity with frame | Honest offline/failure recovery | offline/error mobile screenshots |

Self-critique: retained the existing hierarchy and tokens; removed the solid fill that could imply completion. Support text wraps at375px. The fixture is synthetic and proves layout/state handling, not a real four-minute review duration. CSS zoom200% is a reflow stress test, not browser zoom emulation. Runtime Reduce Motion still needs a manual preference check.

## Parts adapter addendum
The existing PartsWorkspace opens the same RequestWorkspace for a source part or current generated ad. No new player, controls, styling, navigation or motion is added. Its poll error now reaches the existing unavailable state. Exact AssetVersion processing and the runner's durable source-only `iteration_review_ready` flag determine viewer readiness; a raw URL alone cannot override a supplied processing state. Existing held/clear feedback stays viewable during early source readiness.

Source elapsed uses only the matching request/asset/version-number RequestUpload.submitted_at. A generated ad has its own exact identity but no invented upload clock. Pending output identity allows opening the wait view; preview remains limited to held/delivered, downloads to delivered. Missing phase clocks use the existing waiting/calibrating/unknown-time copy and do not block review. Natural ETA calibration remains separate from release acceptance.
