# Design Handoff — dashboard copy cleanup

## 1. Job
Owners reviewing deliveries in Whop need clear page names and actions on mobile and desktop. Alan flagged duplicated Overview labels and decorative copy. Success: one content heading per page, with app identity in the root toolbar.

## 2. Screen inventory & navigation
| Screen/state | Reached from | Presentation | Exit |
|---|---|---|---|
| Overview, Brand rules, Time saved, Projects | Existing sidebar/tab bar | Existing page | Existing navigation |
| Project/folder details | Existing project list | Existing page with breadcrumbs | Parent breadcrumb |
Root pages show the existing configured app name in the toolbar. Detail breadcrumbs remain functional. Mobile tabs and desktop sidebar stay as the navigation pattern.

## 3. Content hierarchy
1. App toolbar with account/search actions.
2. One existing page heading and primary action.
3. Existing metrics and work content. Remove decorative overview/rules slogans; guidelines reminder names its destination directly.

## 4. Components
| Element | HIG component | Role | Copy | Notes |
|---|---|---|---|---|
| Root toolbar | Navigation bar | App identity | Configured app name | Reuse branding store |
| Page heading | Title | Page identity | Overview / Brand rules | Existing typography |
| Guidelines reminder | Link | Open guidelines | Brand guidelines | Keep /rules destination |
| Nested toolbar | Breadcrumbs | Navigate parents | Existing dynamic labels | Preserve links |

## 5. States
Empty, loading, errors, success and offline recovery retain existing behavior. This change only removes redundant presentation text.

## 6. Tokens
Reuse existing semantic OKLCH colors, 4/8 spacing grid and type ramp. No new colors or motion. Toolbar remains 64px; 44px touch actions remain.

## 7. Accessibility
Keep semantic h1, navigation links, icon labels and focus states. Preserve contrast in both themes. Root toolbar app name truncates if custom branding is long; full string remains accessible. Detail breadcrumbs retain their existing navigation.

## 8. Open decisions
None: apply Alan’s explicit preference for direct copy and remove the duplicate page label.

## 9. Review checklist
- [ ] Actual browser screenshots at mobile and desktop widths viewed.
- [ ] Root toolbar names the app, content names the page once.
- [ ] Account/search and primary actions remain accessible.
- [ ] Detail breadcrumbs still navigate parents.
- [ ] Existing functional empty/loading/error copy retained.
No new component or motion decisions. References: Apple HIG Writing and existing UI skills.
