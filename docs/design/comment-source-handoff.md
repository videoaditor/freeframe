# Comment source labels — H2 design handoff

## 1. Job
Editors reading an AutoReview comment need to see which saved requirements support it. Web, desktop and mobile. Success: the correct small text labels survive an API read and reload; unproven comments have none.

## 2. Screen inventory & navigation
| State | Reached from | Presentation | Exit |
| --- | --- | --- | --- |
| Comment with source | Existing asset/share review | Existing comment row | Existing navigation |
| Old/human/unknown source | Same | Existing row, no source labels | Same |

No navigation changes or extra controls.

## 3. Content hierarchy
Existing author/automation marker and time anchor; compact source row above the body; existing body, replies, resolve and reactions.

## 4. Components
| Element | HIG component | Role | Copy | Notes |
| --- | --- | --- | --- | --- |
| Source label | Static text | Supporting metadata | Basics / Brand / Briefing | Distinct layers, this order; no tooltip dependency |

## 5. States
Empty, loading, errors and offline retain the existing comment panel behavior. Null/unknown metadata is omitted. Success shows only verified layers. Permission denial retains the existing share/team restrictions. No quotes, IDs or source prose rendered.

## 6. Tokens
System font, 0.6875rem/1rem medium (existing small badge scale). 4px gaps, 8px horizontal padding, 4px top/bottom row spacing. Neutral OKLCH tokens: light foreground oklch(0.37 0 0), background oklch(0.95 0 0); dark foreground oklch(0.88 0 0), background oklch(0.28 0 0). No animation. Stable wrapping; no fixed heights or ellipsis.

UI/UX Pro Max's generated marketing/hero recommendation is inappropriate for this existing product comment surface; retain the approved interface and use its accessibility checks. Apple HIG typography/accessibility references checked. Badge layout is a web decision, not a prescribed HIG component.

## 7. Accessibility
Static labels require no hit target. No new interactive controls or keyboard stops. Text identifies sources without relying on color; neutral contrast exceeds 7:1 in both themes. Labels wrap at 390px. CSS zoom 200% was inspected separately; it is not native browser zoom and exposes an existing panel minimum-width limit at effective 195px. Source labels remain unclipped. Reduced Motion adds no motion; no OS preference emulation was available.

## 8. Open decisions
None. H1's verified source commit remains the dependency for Worker integration.

## 9. Review checklist
- [x] Before/after desktop and 390px screenshots, light/dark; before uses the same data with nullable provenance omitted.
- [x] Labels match data, stable order, no duplicates or private prose.
- [x] Seek/reply/reload retain labels; the unchanged time button seeks to 2.75s. Opening Reply retains the existing row seek behavior.
- [ ] Native 200% browser zoom and OS Reduced Motion emulation unavailable. CSS zoom and stationary computed styles inspected; see reviews/H2.md.
- [x] Existing mobile video/comments implementation retained; local harness shows separate video and comments, without overlap at 390px.
