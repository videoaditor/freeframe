# Design Handoff — Sidebar "AutoReview" entry (Brand Loop B3)

## 1. Job
- **Who:** a client or staff member who belongs to a project linked to an AutoReview brand. **One thing:** open their brand page on review.aditor.ai without a second login.
- **Platform:** web, desktop sidebar (`md:` and up).
- **Success:** one click → the brand page loads in the same tab, signed in.

## 2. Screen inventory & navigation
| State | Reached from | Presentation | Exit |
|---|---|---|---|
| Entry, one brand | sidebar | nav row (button) | navigates same tab |
| Entry, several brands | sidebar | nav row opens a dropdown menu (right side) | pick a brand → same tab; Esc / click outside closes |

Sidebar stays the top-level pattern (`sidebars.md`). The entry sits directly under the page links, above Notifications/Uploads (utilities), so destinations stay together (serial position).

## 3. Content hierarchy
1. Page links (unchanged) → 2. AutoReview → 3. Notifications, Uploads (unchanged).

## 4. Components
| Element | HIG component | Style | Label | Notes |
|---|---|---|---|---|
| Entry | sidebar row | identical to existing nav rows (h-11, 13px, 18px icon, 1.5 stroke) | "AutoReview" | icon `ScanEye`; tooltip when collapsed |
| Brand menu | menu | same as the account menu (bg-elevated, 13px items) | project name per brand | only with ≥2 brands |

## 5. States
- **Empty:** no linked brand, or AutoReview unconfigured → entry not rendered.
- **Loading:** after click the icon becomes a spinner, row `aria-busy` (< 400 ms feedback); repeated clicks ignored.
- **Error:** toast "Couldn't open AutoReview. Try again." — row returns to idle.
- **Success:** browser navigates.

## 6. Tokens
Existing sidebar tokens only (bg-hover, text-secondary/primary, bg-elevated, border). No new colors, no motion beyond the existing spinner (`animate-spin`).

## 7. Accessibility
Row 44 px tall (h-11). Real `<button>`, accessible name "AutoReview" (also when collapsed). Radix menu gives keyboard + Esc.

## 8. Open decisions
- Mobile bottom bar left unchanged (it carries page links only); add later if clients ask.

## 9. Deviations
None.
