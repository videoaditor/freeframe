# Design Handoff — saved review checklist

## 1. Job
Owners see the fixed checks while sharing an upload link; staff see them after selecting a Trello card/workspace. Mobile/desktop web. Success: the saved checklist appears after reload without delaying link copying/upload.

## 2. Screen inventory & navigation
| State | Reached from | Presentation | Exit |
|---|---|---|---|
| Customer checklist | Request sheet / owner request card | Inline disclosure beneath link | Existing Done / collapse |
| Internal checklist | Card paste + existing workspace choice | Inline disclosure below workspace | Collapse or change card |
Top-level navigation remains the existing sidebar; no additional modal.

## 3. Content hierarchy
Upload/share action first; quiet checklist status second; source identities and applicability within disclosure. One existing primary action per view. Private authenticated surfaces only; guest request workspace receives no checklist payload.

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
None; product decisions approved in H1 handoff.

## 9. Review checklist
Pending actual browser evidence: desktop/390px; light/dark; preparing/ready/failed; reduced motion; 200% zoom; no horizontal overflow; link usable while preparing; reopen disclosure; keyboard focus. Evidence recorded in reviews/2026-10-07-h1.md. HIG source pages read locally: loading.md, disclosure-controls.md. Web styling/microinteraction choices are not HIG-backed.
