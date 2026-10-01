# AutoReview launch handoff

## 1. Job
An invited editor uploads, inspects the exact reviewed version, deliberately uploads V2, and reopens a durable completion. An owner sees the truthful review state. Members recover the Whop entry. Mobile and desktop web; reuse the approved editor-journey handoff.

## 2. Screen inventory and navigation
| State | Entry | Presentation | Exit |
| --- | --- | --- | --- |
| Upload/identity | /r/token | focused page | submission enters review |
| Review and history | same page / reload | split workspace; stacked below 768px | explicit V2 / back to feedback |
| Unavailable | review failure | same workspace; media retained | Check again |
| Submitted | persisted finish | durable completion | readable on reload |
| Whop recovery | /whop HTTP error | focused page | Whop / team login / retry |
Keep existing owner navigation and four-column board.

## 3. Hierarchy
Brand/project, current version/player, findings and one correction action. Whop recovery: reason, primary recovery, separate staff login only on account collision.

## 4. Components
| Element | Convention | Label | Behavior |
| --- | --- | --- | --- |
| File picker | native input plus dropzone | Drop your files to begin | bytes transfer before identity |
| Revision | primary button | Feedback done, back to upload v2 | explicit asset target |
| Failure | status text / button | Review unavailable / Check again | never green or completed |
| Whop recovery | link / button | Open in Whop / Team sign-in / Try again | status-specific recovery |

## 5. States
Empty: file picker. Loading: real byte progress, then indeterminate review. Error: preserve files and version, recovery in place. Success: only persisted exact-version completion; brand approval separate. Permission: 410 closed request, 403 membership denial; no private content.

## 6. Tokens
Existing blue/neutral OKLCH semantic tokens and system typography. 4/8px grid, body 16px, secondary 13–14px, 44px touch controls. Reuse existing CSS mascot/scanning motion; transform/opacity, reduced-motion static pose, pause control. No new animation dependency.

## 7. Accessibility
44px controls, visible labels and focus, live review status, contrast >=4.5:1 in light/dark. Stack player/feedback at 390px, verify no overflow and 200% zoom. No color-only verdict.

## 8. Decisions
Reuse approved editor implementation without iterations, project-history verification or performance pilots. Whop collision never auto-links identities. Ready means agent review passed; Approved means human brand approval.

## 9. Review checklist
Screens and results are recorded in the launch acceptance handoff. Native phone/Whop acceptance remains pending STOP2; local browser simulation is labeled explicitly.
