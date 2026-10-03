# Hand-in: parts, early feedback, background delivery

Date: 2026-10-03 (Asia/Tokyo). Status: implemented in isolated branches; local UI verified; production activation remains off.

## 1. Job

An internal or customer-invited editor uploads each unique rendered part once, gets actionable feedback as early as possible, and leaves assembly and delivery to the service. AdMixer is the background engine. The customer receives final ads and reusable parts in the correct account. Success separates **editor work complete** from **final files delivered**.

This captures the approved product direction, including the existing AdMixer interaction, Apple HIG, distinct team/customer/editor access, and minimal waiting. It does not promise an unmeasured review time. Integration evidence and endpoints: [technical handoff](../integrations/handin-components.md).

## 2. Screen inventory and navigation

| Audience/state | Entry and presentation | Main action / exit |
|---|---|---|
| Internal editor | Hand-in in team workspace; Trello card and authorized brand resolved above bulk upload | Upload parts; return to submissions |
| Customer owner | Existing owner workspace and file request | Configure request, inspect delivered ads and reusable parts |
| Customer editor | Customer's request link; compact branded task page, no global admin sidebar | Upload/revise this request; reopen the same link later |
| Review/changes | Same page; compact part rows with player and timecoded feedback | Replace only the affected part |
| Background handoff/delivered | Same durable page; distinct completion states | Close after confirmed handoff, or open finished ads |

Desktop internal-editor navigation: Hand in, My submissions, Projects; notifications and profile are secondary. Hide Brand rules and owner analytics from editors in desktop sidebar, mobile navigation, command palette and direct-route UI. APIs independently enforce management permissions. A customer owner may manage their own rules; a customer-invited editor may not. Do not equate every non-superadmin with an editor or use staff status as customer-account authorization.

Customer editors need no separate AdMixer account. Their request link grants access only to that task and its versions. Internal authorized staff can select permitted brands; customer editors see the destination brand read-only. Account ownership and uploader attribution are separate.

On narrow screens use labeled task navigation, with upload stages stacked vertically and no horizontal file carousel. Internal top-level navigation may use a compact tab bar. The external single-task page needs no dashboard tab bar.

## 3. Content hierarchy

1. AutoReview/customer identity, task title, destination brand and compact brief disclosure.
2. Submission choice: “Separate parts” / “Complete ads”; preserve the existing complete-ad path.
3. Two bulk zones, **Hooks** and **Bodies**. Progressive optional stages use the existing mixer sequence: Hook → Bridge/Lead → Body → CTA. No one-card-per-required-clip grid. Existing requests retain their explicitly planned grouping and body-with-CTA convention.
4. Compact uploaded-file rows and real status per file; summary such as “8 hooks · 1 body → 8 ads”. Changes to selection update the output count. Existing angle restrictions remain encoded in recipes.
5. One primary action, “Submit for review”, which seals the intended batch. Upload starts on drop, not on this action. After handoff replace it with the actual status and a secondary “View submission”.

Default simple submissions use AdMixer's Cartesian product of the selected stages. Structure comes from explicit upload roles; briefing parsing is not a prerequisite for opening or uploading. Already planned requests preserve their exact recipe relationships. Never silently discard a known restriction on compatible hooks/leads/bodies.

## 4. Components

| Element | Convention | Real copy | Behavior |
|---|---|---|---|
| Bulk stage | Accessible web file input; not an HIG-specific component | “Drop hooks here or choose files” | Multiple files, keyboard picker, compact thumbnail/name rows |
| Optional stages | Disclosure/button | “Add bridges” / “Add separate CTAs” | Progressive reveal; no forced empty fields |
| Part row | List row plus determinate transfer progress | “Uploading · 42%”, then “Checking” | Bytes and analysis never share a fabricated percentage |
| Findings | Inline list linked to player | “Needs a change” / “Suggestion” | Required versus optional; source-local timestamps |
| Handoff | Persistent status, not a toast | “Your part is done. We’re creating and delivering 8 ads.” | Only after uploads, exact-version checks and durable handoff qualify |

## 5. States

| State | Visible behavior and recovery |
|---|---|
| Empty | Two clear upload zones, short guidance that shared bodies are uploaded once |
| Uploading/checking | A completed hook can be checked while the body uploads. “Hook 1 checked · Body uploading”. Keep tab-open guidance while any required local bytes remain |
| Changes/service failure | A specific finding gives Replace part; service failure gives retry/status and never masquerades as a creative failure or approval |
| Editor complete / delivered | “Your part is done” means no present editor action; “8 ads delivered” requires final accepted outputs. A later final-check finding explicitly reopens only affected work |
| Offline/denied | Completed server uploads persist; incomplete browser uploads need recovery. Invalid/expired request has its own message, no other account's data |

Early feedback is provisional until the exact source version and required checks are complete. An unchecked preview never authorizes final release. A finished source-review step is not human customer approval. Partial success reads “6 of 8 delivered” with the remaining state, not batch success.

## 6. Tokens and visual direction

Use the actual approved AutoReview landing identity: original blue icon, restrained orange action accent, warm neutral surfaces, system typography and generous spacing. The previous editor-journey draft's blue-accent proposal is not the current landing source. Carry the brand into a compact working interface; do not copy its marketing hero, artwork or raised promotional buttons.

Proposed semantic values, derived from `apps/web/app/landing.module.css`:

| Token | Light | Dark |
|---|---|---|
| Background / surface | `oklch(99% .002 285)` / `oklch(96% .003 285)` | `oklch(14.6% .004 285)` / `oklch(18.5% .006 285)` |
| Primary / secondary text | `oklch(22% .006 285)` / `oklch(44% .008 285)` | `oklch(97% .003 285)` / `oklch(74% .006 285)` |
| Accent | `oklch(56% .195 33)` | `oklch(69% .205 33)` |
| Border | `oklch(20% .008 285 / .14)` | `oklch(100% 0 0 / .12)` |

Contrast is a build acceptance check, not established by listing tokens. Type: title 28/34px, section 20/26px, body 16/24px, secondary 14/20px, expressed in rem. Four/eight-pixel grid; 24/32px section gaps, 12px control spacing. Controls at least 44px for touch. Main workspace max approximately 1040px; reduce nested bordered boxes. File names remain readable with full-name access.

Use restrained 160–200ms opacity/color transitions and a clear pressed state. No long entrance animation or fake review progress. Reduced motion removes movement; keyboard actions remain immediate. The generic UX skill's video-hero recommendation is unsuitable for this task interface and is intentionally rejected.

| Before | After | Why |
|---|---|---|
| Long explanatory paragraph above a small nested form | Task title, one sentence, brief disclosure | Files and next action become immediately visible |
| One large generic upload target | Two bulk stage zones and compact file rows | Matches the editor's export task and existing mixer |
| Same management navigation for everyone | Role-appropriate navigation and server permissions | Customer editors see only their assignment |
| One ambiguous “processing” wait | Per-file upload/check state plus separate background delivery | People know whether they need to stay |

## 7. Accessibility

Visible labels, keyboard-operated inputs, focus rings, 44px touch targets, status live regions with restrained announcements, and actual byte-progress semantics. Errors reference the relevant part and preserve selection. Status always has text/icon meaning in addition to color. Support light/dark, 200% text zoom, 375/768/1440px widths and reduced motion. Do not move focus on each status poll; move it deliberately after submission or validation failure.

Apple HIG informed the handoff structure, sidebar and progress guidance. File-upload details and timing are web design decisions, not invented HIG requirements. Emil Design Engineering and UI UX Pro Max inform polish/accessibility.

## 8. Decisions and remaining evidence

The approved direction resolves the main product decisions: AdMixer stays in the background; editor waiting is minimized; customer parts belong to the customer account. Existing engine selection semantics provide the default combination behavior. No further question about basic hook/body grouping is needed.

Implemented against current main in all three repositories. Canonical private FreeFrame owner/project mapping is enforced; browser screenshots use synthetic fixtures. Production latency and a live cross-service trial remain activation checks, not established measurements.

## 9. Post-build review checklist

- [ ] Inspect screenshots for empty, uploading/checking, changes, background handoff and delivered states; light/dark and phone/desktop.
- [ ] Verify internal editor, customer owner and customer editor navigation and API access independently.
- [ ] Confirm tab close/reopen preserves accepted jobs; no close-tab claim while required bytes are local.
- [ ] Verify real copy, 200% zoom, contrast, keyboard, reduced motion and touch targets.
- [ ] Record screenshot paths and remaining deviations; do not call this design implemented or visually verified before that evidence exists.

## 10. Local visual acceptance (2026-10-03)

Screenshots use synthetic data. The before capture shows the retained complete-ad form with the new editor navigation. Screenshots: [before](handin-evidence/before-handin.jpg), [empty](handin-evidence/guest-empty-dark.jpg), [internal screen](handin-evidence/internal-light.jpg), [background handoff](handin-evidence/after-handoff.jpg), [mobile light](handin-evidence/handoff-light-mobile.jpg), [mobile dark](handin-evidence/handoff-mobile-dark.jpg), [feedback](handin-evidence/feedback-desktop.jpg), [delivered](handin-evidence/delivered-light.jpg).

The browser exercised a synthetic hook/body upload while identity was incomplete, completing identity, sealing the saved batch and reopening the same link. Required feedback opens the existing timecoded player. Internal editor navigation shows Hand in, Submissions and Projects; management routes render the editor workspace instead. Guest pages expose no dashboard tools. At a 375px viewport, measured document width equals client width (369px excluding the scrollbar), with no horizontal overflow. Layouts were visually inspected in light/dark on desktop/mobile. The theme initializer now respects the hydrated saved preference when reopening a request.

| Observed before correction | Implemented after inspection | Reason |
| --- | --- | --- |
| Empty status card pushed upload fields down | Empty screen leads with the fields; status appears with files | Less reading before first action |
| Reopened completed request asked for identity again | Details appear only for new/active transfers | No unnecessary editor step |
| Owner blue tokens reached Hand-in | Scoped orange/neutral OKLCH tokens in both themes | Matches public AutoReview identity |
| Three text actions competed in each file row | Remove uses labeled icon; feedback and replace remain text | Clear action hierarchy with 44px targets |
| Theme reset on fresh navigation | Read hydrated store at initialization | Reliable light/dark behavior |

A full screen-reader pass and manual 200% browser-zoom pass were not performed. Semantic labels, progress, minimum 44px controls, reduced-motion styles and wrapping file names are implemented; production acceptance should retain these checks. Screenshots and local mock state are UI evidence only, not evidence of live model speed or Trello delivery.
