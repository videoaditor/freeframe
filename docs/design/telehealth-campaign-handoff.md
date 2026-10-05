# Design handoff — Telehealth campaign access

## 1. Job
Telehealth owners see how long their free preview lasts, submit feedback, and choose a paid plan when it ends. Responsive web, inside existing owner dashboard. Success: correct cutoff visible; expired customers see a useful paywall with preserved identity and two clear plan choices.

## 2. Screen inventory and navigation
| State | Entry | Presentation | Exit |
| --- | --- | --- | --- |
| Active preview | Whop sign-in / dashboard | In-flow banner above content | Use dashboard normally |
| Expired preview | Dashboard at/after cutoff | In-flow full content replacement | Open plan or give feedback |
| Paid cohort | Upgrade and re-entry | Regular dashboard | Existing navigation |
| Feedback | Give feedback | Existing ProductFeedback sheet | Escape / Close |

Keep existing sidebar on desktop. No new navigation layer. On mobile the campaign content uses the full available width.

## 3. Content hierarchy
1. Active: “Telehealth preview” and exact end date; Give feedback.
2. Expired: “Your preview has ended”, saved-work reassurance, recommended plan based on successful reviewed ads.
3. Both plans, no unverified pricing; optional feedback remains available.

## 4. Components
| Element | HIG pattern | Role | Label | Notes |
| --- | --- | --- | --- | --- |
| Preview notice | Inline status | Informational | Telehealth preview | No dismiss hiding the end date |
| Plan link | Button | Primary | Explore Team / Explore Masterclass + Tools | One recommendation prominent |
| Alternate plan | Button | Secondary | Explore alternative | Explicit actual plan name |
| Feedback trigger | Sheet | Secondary | Give feedback | Existing component |

## 5. States
Empty: zero reviewed ads recommends Masterclass. Loading: “Checking your usage…” while offers remain available. Error: usage unavailable; do not invent a review count. Success: recommendation and actual count. Offline: preserve server-attested local cutoff; paid permission is still enforced by API. Feedback has saved receipt, retry and retained input states.

## 6. Tokens
Reuse owner-workspace semantic OKLCH tokens, body 1rem/1.5, headline 2.125rem, 4/8 spacing grid. Buttons minimum44px. No new animation except existing press state. No gradient, decorative badge wall or fabricated urgency timer.

## 7. Accessibility
44px touch targets, visible focus outlines, meaningful headings, no color-only status, 200% text zoom wrap, no clipped dates. Feedback sheet keyboard behavior inherited from Radix. Contrast evaluated using existing light/dark semantic text tokens.

## 8. Open decisions
None for implementation. Published paid-plan links are verified during integration; pricing stays on checkout.

## 9. Review checklist
- [x] Inspected active and expired component fixtures at 393/1440 widths and light/dark; screenshot files in `screenshots/telehealth`. Paid bypass is component-tested.
- [x] Recommendation boundary at 20 distinct ads is backend-tested; real PostgreSQL proves duplicate asset observations count once.
- [x] Expired state shows both plan links and feedback; component test confirms protected children are not mounted.
- [x] Feedback retained its draft after a real local connection failure; Escape closed the sheet and focus returned to its trigger. 200% text at 393px had no horizontal overflow (content 387px).

| Before | After | Why |
| --- | --- | --- |
| Full-width feedback trigger wrapped on desktop | Inline trigger with a 44px target | Keep status and action on one line when space allows |
| Masterclass always first | Recommended plan first, other plan retained | Make the suggested next step visible on mobile |
| Fixed mobile sidebar margin | Desktop-only sidebar margin | Mobile content uses available width |

These are local component fixtures, not proof of a live customer signup. A temporary fixture route was removed before the release build. Feedback success/retry payloads are covered by component and backend tests; live Slack delivery remains unverified.

Web-specific status banner and pricing navigation are not direct HIG components; patterns follow hierarchy and interaction guidance.
