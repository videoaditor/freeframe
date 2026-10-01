# Design Handoff — Owner logo and editor accuracy

## 1. Job
Owners brand their public request pages and compare editors by first-version accuracy.
Web, mobile and desktop. Success: saved project logo appears in preview and public requests;
ranking shows API order and honest sample sizes.

## 2. Screen inventory & navigation
| Screen / state | Reached from | Presentation | Exit |
| --- | --- | --- | --- |
| Brand logo | Brand rules, selected brand | Inline card | Existing navigation |
| Brand logo | Request created | Existing request sheet | Done / Escape |
| Editor ranking | Overview / First-try pass rate metric | Existing sidebar card | Existing navigation |
No new top-level destination; reuse the existing sidebar and mobile tabs.

## 3. Content hierarchy
1. Existing page job remains primary: request link, rules or incoming requests.
2. Logo preview, brand name, Upload logo / Change logo, save status.
3. Ranking: ordered editor identity and rate, sample, average versions, open must-fixes; measurement explanation.

## 4. Components
| Element | HIG component | Role | Label | Notes |
| --- | --- | --- | --- | --- |
| Logo input | Button + native file picker | Secondary | Upload logo / Change logo | 44px; raster image, <=5MB |
| Logo preview | Image | Informational | Brand-name logo | Contain; preserve transparency |
| Recovery | Button | Secondary | Retry | Inline load error |
| Ranking | Ordered list | Informational | First time right | Backend order; unknown gets no numeric rank |
| Explanation | Disclosure | Secondary | How this is measured | 44px target |

## 5. States
Empty logo: brand initial, Upload logo, public-page explanation. Loading: Loading logo….
Upload: Saving logo…, picker disabled. Saved: server URL preview, Logo saved.
Load failure: error and Retry, never imply no logo. Upload failure: retain old preview and allow retry.
Permission denied: show API error, retain existing brand state.
Rank loading/error/empty: preserve existing skeleton, retry and first-upload message.
Unknown rate: Not reviewed yet, no 0% or rank. Partial: N of M reviewed. Small sample: fewer than
5 reviewed videos marked Small sample (UI convention, not statistical confidence).

## 6. Tokens
Existing semantic theme tokens, no new palette or font. Existing OKLCH metric accents retained.
Type: 0.75rem metadata, 0.875rem names, 1.0625rem heading, 1.125rem rates.
Spacing: 4/8px grid; 12px between controls. Existing press transition, no added decorative motion;
existing reduced-motion override applies.

## 7. Accessibility
44px buttons, meaningful image alt, file input label, status/alert announcements, visible focus.
Text-primary and text-secondary for readable copy in both themes. No reliance on color.
Names/emails wrap; flexible rows at 375px and zoom. Sheet retains Radix keyboard/Escape behavior.

## 8. Open decisions
None: implement within the supplied backend contract and existing product design.

## 9. Review checklist
Reviewed with the local synthetic API at :8100 and browser at :3200:
- Desktop 1280px and mobile 375px, light and dark: inspected logo card and ranking.
- Real browser PNG -> WebP -> signed PUT -> branding save -> preview -> public request logo verified.
- Brand switch preserves separate logos; API failure shows Retry, and Retry recovers.
- Request creation shows the logo control beside the generated link; existing sheet dismissal works.
- Unknown accuracy has no percentage or rank; partial sample and versions/must-fixes are visible.
- Screenshots: `/Users/alansimon/Downloads/freeframe-owner-ui-checks/`.
- 368 frontend tests pass; TypeScript passes; lint passes with existing warnings. Production build
  passes from an isolated source copy (to avoid interfering with the shared development server).
- Backend regression suite: 271 pass, 45 skip via isolated uv/Python 3.12 environment.

No live backend/storage end-to-end run was performed; browser acceptance uses the contract-shaped
local API. No backend files were changed. Existing mixed working-tree changes were preserved. File-size cap and small-sample wording are product choices,
not HIG requirements. No new dependencies or backend modifications.


## Follow-up: average and outlier notification (2026-09-28)
Owner request: one average instead of a range, with a notification bubble for unusually high/low editors.
Keep the existing metric link and ranking destination. Show the unweighted arithmetic mean of known
editor rates, rounded once to a whole percent. Unknown rates stay excluded; zero remains a real value.
A small count bubble next to the number links with the entire card to the ranking, where textual
Above average / Below average badges identify the editors. No new modal, workflow or personnel action.
Product heuristic: at least three editors with >=5 reviewed videos; only those editors can be flagged,
at >=20 percentage points from the average. Explain this in How this is measured. This is a comparison
hint, not statistical significance. Existing semantic tokens, no new animation, full-card keyboard/touch
link, accessible bubble label; verify desktop/mobile and no-data/error/small-sample cases.

Follow-up verification: 379 frontend tests pass, TypeScript and production build pass; lint has only
existing warnings. A separate local fixture (:3201/:8101) verified a 60% average with two notification
markers, navigation to Above average / Below average editor rows, and 375px / desktop rendering.
The original preview (:3200) retains its data and now shows 74%, with no marker for its small sample.
Screenshots: `average-outliers-desktop.png` and `average-outliers-mobile.png` in the folder above.
Also corrected four invalid Testing Library `exact` role-query options in the concurrent Kanban tests;
string name matching is already exact. Those tests and TypeScript were rerun successfully.

## Follow-up: owner feedback and Whop launch check
Before implementation: leaderboard becomes one ordered row per editor with fixed rank/accuracy
alignment; expandable row details retain email, sample, versions and must-fixes. A visible Request
files action explains that editors identify themselves on the upload link and appear after upload.
Guidelines reminder becomes a compact inline note: “Never say the same thing twice”. Motion toggle
becomes a 44px icon control; decorative Kanban animations run once, no perpetual scan/pencil loops.
Request briefing always exposes a text/link input alongside the file picker. PDF, Markdown and text
supported with a 10MB client limit; text files map to the existing text contract. Existing Radix Select
provides a keyboard-operable brand menu, with 44px options and theme tokens. No new packages.
Rules become compact document rows: title plus clearly labeled Review check; full text in disclosure.
Existing APIs have no owner rule-update route, so do not promise a working Edit/Save action yet.
Whop account linkage is also absent in FreeFrame; existing Worker Whop sessions cannot authenticate
FreeFrame routes. Live Whop readiness must be proven independently from the fixture preview.

Follow-up verification completed 2026-09-28: 391 tests across 59 files pass; final source typecheck
and isolated production build pass. Lint passes with existing hook warnings. Screenshots inspected
at 375px, 697px and 1280px; keyboard brand selection and request creation, full rule text and compact
reminder verified against the local fixture. Saved screenshots: leaderboard-refined-mobile.png,
leaderboard-refined-desktop.png, request-brand-menu.png, rules-refined-mobile.png. No RAM/load-time
benchmark was performed; the concrete optimization is finite Kanban decoration instead of loops.

Build-environment incident: a repeated Next standalone build in a copy with node_modules symlinked
to this checkout cleaned the symlink target. Restored dependencies with the unchanged frozen lockfile
using the local package cache; reran the full 391-test suite, typecheck, and final build. Final build
used its own installed dependencies at `/private/tmp/freeframe-final-check-6blt0tnz`; do not reuse the
older symlinked build copies. The dev preview was reloaded and visually checked after recovery.
No package or lockfile changes. Whop/rule-edit gaps and live evidence are in
`docs/handoff/2026-09-28-whop-and-rule-edit-gaps.md`; these remain release blockers.

## Whop entry extension (2026-09-28, before implementation)
Job: an entitled member opens Review inside Whop and reaches only their own workspace.
`/whop` is a transient public sign-in screen, using the existing auth layout. It immediately
exchanges the same-origin injected header; no email field or second navigation choice.
States: “Opening your workspace…” (live status), access denied, missing Whop context,
account conflict, temporary outage (alert + Try again). Success replaces the location with
`/home` to reset all in-memory customer data. Clear persisted upload/branding data at entry.
Reuse existing semantic theme, 4/8 spacing, heading 20px/body 14px, 44px retry target,
visible keyboard focus, wrapping copy, no decorative or infinite animation. No success claim
until the backend returns complete FreeFrame tokens. Reload returns to Whop when needed.
Validation: missing context in a real browser; success/error/retry tests with controlled server
responses; live authenticated Whop acceptance remains separate from fixture evidence.

Whop entry inspected at desktop and 375px: Aditor mark corrected (legacy bitmap still said
FreeFrame), Retry uses the existing 44px Button, no overflow, readable alert. Missing-header and
retry flow verified locally. Successful real Whop access is a deployment acceptance item, not
proven by the UI fixture. See `docs/handoff/2026-09-28-whop-launch.md`.
