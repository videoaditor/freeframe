# Design handoff — Product feedback

## 1. Job
Authenticated AutoReview customers report a bug or suggest an improvement from their current page. Web on mobile and desktop. Success means a persisted receipt is visible; Slack delivery is independent.

## 2. Screen inventory and navigation
| State | Entry | Presentation | Exit |
| --- | --- | --- | --- |
| Feedback form | Persistent Give feedback trigger | Radix modal sheet | Close, Escape, outside click; draft retained |
| Saving / retry | Send feedback | Same sheet | Close remains available |
| Receipt | Server confirms persistence | Same sheet | Done, Escape |
| Staff queue | Daily digest source link | /feedback page | Existing dashboard navigation |

Reuse the dashboard sidebar. Feedback is a focused secondary task, with no new navigation hierarchy.

## 3. Content hierarchy
1. Give feedback title and short explanation.
2. Report a bug / Suggest an improvement, then labeled message.
3. Send feedback primary action; inline error or persisted receipt.

## 4. Components
| Element | HIG analogue | Role | Label | Notes |
| --- | --- | --- | --- | --- |
| Trigger | Button | Secondary | Give feedback | 44 px target |
| Sheet | Sheet | Focused task | Give feedback | Radix focus trap and return |
| Category | Radio group | Input | Feedback type | Native keyboard semantics |
| Message | Text view | Input | Your feedback | 4000-character maximum |
| Submit | Button | Primary | Send feedback | Disabled while saving |
| Dismiss | Button | Secondary | Close feedback / Done | Remains available |

## 5. States
Empty: prompt to describe the issue or idea. Loading: Saving feedback… with disabled submit. Error: “We couldn't save your feedback. Your message is still here. Try again.” Draft and submission ID survive retry. Success: “Feedback received” plus receipt ID. Offline follows the error state; staff authorization failures show “Staff access required.”

## 6. Tokens
Type: system stack, body 17/24 px, heading 22/28 px, footnote 13/18 px. Spacing: 4/8 grid, 24 px content padding, 12 px control gaps. Colors: existing semantic theme tokens; new sheet surface uses existing palette, represented by OKLCH fallback values (surface oklch(0.21 0.006 286), text oklch(0.97 0.003 286), accent oklch(0.68 0.21 34)). No new global palette or fonts. Motion: none needed for this low-frequency utility. Staff list reuses existing cards and buttons.

## 7. Accessibility
44 px minimum controls. Explicit labels, native radios, focus-visible ring, dialog title/description, polite saving/success and alert error. Escape dismisses; trigger receives focus. Scrollable sheet supports small viewports and 200% zoom. Text wraps without fixed-height truncation. Theme tokens carry current light/dark contrast; integrator verifies screenshots.

## 8. Open decisions
None; no attachments in this version. The existing design system overrides generated skill font/color alternatives to preserve the app identity.

## 9. Review checklist
- [ ] Integrator captures mobile and desktop initial/error/success states, checks 200% zoom and contrast.
- [ ] Keyboard focus and Escape checked in browser (component tests also exercise closing).
- [ ] Staff queue denied for customer account and available for staff.
- [x] Only one prominent action; drafts preserved on recoverable failure.
- [x] Copy and interaction match this handoff.

HIG deviation: web Radix sheet uses outside-click dismissal with retained draft instead of a native discard confirmation. No data is lost on dismissal.
