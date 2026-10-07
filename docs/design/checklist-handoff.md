# Design Handoff — saved review checklist

## 1. Job
Alan's correction, 2026-10-07: the share screen has one job — copy/share a link with the editor. It contains no checklist or checklist disclosure. Staff see the fixed checks in Handin after selecting a Trello card/workspace. Mobile/desktop web. Success: sharing stays focused, while the existing Handin checklist remains available.

## 2. Screen inventory & navigation
| State | Reached from | Presentation | Exit |
|---|---|---|---|
| Share link | Request sheet / owner request card | Existing LinkCard only; no review checks | Existing Done / Close |
| Internal checklist | Card paste + existing workspace choice | Inline disclosure below workspace | Collapse or change card |
Top-level navigation remains the existing sidebar; no additional modal.

## 3. Content hierarchy
Share dialogs show their title, link/actions and existing completion/close controls. No checklist loading/error/status or logo editing appears there. Logo editing remains in the existing Brand rules screen. Handin keeps upload first, quiet checklist status second, and source/applicability within its disclosure. No replacement checklist entry point is added.

## 4. Components
| Element | Convention | Role / copy | Notes |
|---|---|---|---|
| Status line | Loading/progress guidance | “Preparing review checklist…” | Text only, no fabricated progress |
| Disclosure | Native details/summary | “N review checks” | 44px summary; Enter/Space keyboard access |
| Sources | Secondary text | Basics · Brand · Briefing | No source quoted or invented |
| Failure | Inline text + button | “Checklist unavailable. You can still upload.” / “Try again” | 44px retry, visible focus/press state |

## 5. States
Empty: paste/select workspace or create request using existing control. Loading: stable status line and working link/upload. Error: concrete safe reason, retry. Ready: nonempty saved checks; “Same checks for every version.” Variant/submission scope explicitly labeled. Missing source/scope visibly “Source unavailable”/“Scope unclear.” Offline/permission: unavailable, no guest fallback.

## 6. Tokens
Existing OKLCH semantic tokens: bg-secondary, border, text-primary, text-secondary, accent. No new palette/font. Body 1rem/1.5, secondary .875rem; 4/8px grid, 16px padding, 8/12px gaps. No new animation; reduced motion remains static. UI/UX search’s generic lead-magnet/font/palette suggestions rejected because this extends the existing app design.

## 7. Accessibility
44px summary/retry, >=4.5:1 body contrast in light/dark, text state independent of color. Native disclosure, focus-visible ring. Wrapping source labels and requirement text; no fixed height; verify 200% zoom and 390px. aria-live polite for loading/failure.

## 8. Open decisions
Alan's direct correction supersedes the original H1 placement in the share dialog. Saved preparation/data contracts continue; both checklist render sites and the new-link logo editor are removed from sharing.

## 9. Review checklist
Current share correction: built desktop screenshots show the new-link/reopened dialogs with no checklist or logo editor. Title/link/actions/Done fit the viewport; 44px controls remain, keyboard/close controls are unchanged. Copy success and the live local guest upload page were verified. No new animation, typography, colors or breakpoint rules were introduced. The earlier mobile/zoom/motion evidence and limits below apply to the original H1 pass, not a fresh full matrix for this removal. Screenshots: reviews/assets/h1-share-{created,reopened}-focused.png.

Browser evidence recorded for desktop/390px, light/dark, preparing/ready/failed, reload, scrolling to the final criterion, working guest upload and visible focus. Inspection found zero animation/transition duration on the new checklist. 200% zoom shortcuts had no effect and reduced-motion emulation is unavailable in the exposed browser API; these two checks remain unverified. The new request-sheet content exposed an inherited scroll-position/header clipping issue; resetting scroll after creation and constraining desktop height corrected it. Evidence recorded in reviews/2026-10-07-h1.md. HIG source pages read locally: loading.md, disclosure-controls.md. Web styling/microinteraction choices are not HIG-backed.
