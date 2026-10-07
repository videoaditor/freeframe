# Design Handoff — dismissible trial notice

## 1. Job
Preview customers can read the fixed trial deadline once, then dismiss the notice to focus on work or record a clean product demo. Mobile and desktop web. Success: calm blue notice closes immediately and remains hidden for this user/campaign/end-date in this browser.

## 2. Screen inventory & navigation
| State | Reached from | Presentation | Exit |
|---|---|---|---|
| Active preview notice | Existing authenticated app | Inline notice | Dismiss preview notice button |
| Dismissed | Close button or saved preference | App content + existing feedback trigger | Campaign identity/date change shows a new notice |
| Expired preview | Existing server state or deadline | Existing plan-selection screen | Existing plan links |
Navigation is unchanged. Dismissal changes presentation only, never access or expiry.

## 3. Content hierarchy
Trial title and existing deadline terms; close icon. The existing feedback button remains at bottom right throughout the active preview, including after dismissal.

## 4. Components
| Element | HIG | Role | Copy | Notes |
|---|---|---|---|---|
| Notice | Informational surface | Secondary | Existing preview text | Calm blue, not a warning |
| Close | Button | Normal | Dismiss preview notice | X icon, 44px target, focus outline |
| Feedback | Existing button/dialog | Secondary | Give feedback | Remains accessible after dismissal |

## 5. States
Non-preview users: unchanged. Preference loading: no banner flash. Storage denied: show notice and allow in-memory dismissal. Dismissed: saved locally. Expired: existing paygate always wins; no dismiss control on gate. No network operation added.

## 6. Tokens
Existing app font, 14/20px copy; 16px horizontal padding mobile, 32px desktop; 12px gaps. Blue OKLCH light background .96/.02/250, dark .25/.05/250; foreground light .32/.10/255, dark .90/.04/250. Instant close; button press only, respects reduced motion.

## 7. Accessibility
44px close target; accessible name and tooltip; visible focus outline; wrap text at narrow widths and 200% zoom. Text contrast checked in light and dark; icon is decorative inside the named button.

## 8. Open decisions
None. User explicitly requested blue and dismissible; persistence scoped to account/campaign/end-date is the implementation choice.

## 9. Review checklist
Verified in the local browser at desktop and 375px mobile, in light and dark themes; dismissal persisted after reload and feedback remained accessible. All 608 frontend tests, production build, typecheck and lint passed (existing image warnings only). Screenshots saved in Downloads/autoreview-demo-2026-10-07/banner-qa. Native HIG has no exact web trial-banner contract; this is a normal button and responsive informational surface.
