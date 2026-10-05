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

## 11. Clear signposting iteration — 2026-10-05

Alan requested restarting the preview with a clearly signposted layout. Reuse the existing project, request machinery and approved visual tokens. No new wizard, sequential upload constraint, briefing parser or backend state.

Job/platform/navigation remain sections1–2: editors complete their assigned upload on a mobile/desktop task page; internal editors retain team navigation and owners retain their own account controls. Destination brand is read-only on customer links. AdMixer remains invisible background machinery.

Content hierarchy: task identity/title/brief, persistent three-stage orientation (`Upload parts`, `Check parts`, `Final ads`), actionable handoff status, Hooks/Bodies with one plain explanation each, editor details and explicit submit action, final-ad section with a useful empty state. Guidance states that one shared body is reused for every selected hook. Optional bridge/CTA descriptions explain which exports belong there. Final ad rows use `View final review` to distinguish them from source feedback.

| Component | Before | After | Why |
|---|---|---|---|
| Orientation | Status card only after files exist | Three labeled stages, explicit editor/automatic responsibility | Make the complete workflow visible at entry |
| Stage headings | Hooks/Bodies without explanation | Alternative openings / main section plus ending; shared body uploaded once | Make export placement obvious |
| Empty final area | Hidden | `Final ads` with pending guidance | Make the output destination visible before uploading |
| Error status icon | Editor-done tick even during infrastructure error | Error/attention icon when held or failed | Text and icon agree |
| Final review action | `Review` | `View final review` | Separate source checks from finished-ad feedback |

States: empty stage1current with upload guidance; live transfers keep tab-open copy; the parts-passed count reflects only declared exact backend slots; sealed uploads complete stage1; stage2 completes only when every declared source is clear; finalstage completion requires delivered==total, state delivered and no local transfer. Held/error states show action/retry, not a success icon. Previously saved batches and mode switching remain available. Denied/offline behavior is unchanged.

Tokens/accessibility: existing light/dark OKLCH and system fonts; body16/24, secondary14/20, sections20/26, 4/8spacinggrid; stage row stacks below640px, controls≥44px, no animated step transitions or percentage estimate. Ordered list has `aria-label=Submission progress`, current step uses `aria-current=step`, decorative symbols aria-hidden; state text supplies meaning without color. File inputs keep their existing accessible names and real transfer progress. Keyboard/phone/200% width checks are acceptance evidence, not asserted in advance.

Apple HIG writing/progress-indicator references informed labels and truthful state. A custom three-stage orientation strip and file zones are web patterns, not claimed native HIG components. UI/UX Pro Max design-system search suggested a lead-magnet landing/Trust-and-Authority treatment; rejected as irrelevant to the existing task UI. Emil principles retained: clear hierarchy, immediate keyboard behavior, restrained existing press states.

Acceptance: actual public HTTPS staging inspected at 1280px in dark mode, both a fresh empty request and the preserved 2/2 delivered batch. Upload areas align at the same top edge; no horizontal overflow. Self-critique corrected the initial unequal upload-area alignment caused by the longer body explanation. Keyboard Tab moves from Separate parts to Complete ads. Full frontend suite: 513 passed; build, explicit TypeScript and lint passed (existing warnings). Independent review added 10 meaningful regressions, including a stale delivered snapshot during replacement transfer. The default pnpm invocation selected Node25 and collided with native WebStorage; the final complete suite passed with the configured Node22 PATH, without application changes.

| Before | Empty after | Delivered after |
|---|---|---|
| [Previous handoff](handin-evidence/after-handoff.jpg) | [Clearly labeled entry](handin-evidence/oct5-signposted-empty.jpg) | [Completed stages](handin-evidence/oct5-signposted-delivered.jpg) |

Light mode, narrow viewport, full keyboard traversal, VoiceOver and manual 200% zoom were not revalidated for this iteration. Earlier screenshots do not establish acceptance of the new orientation strip. Automatic video review cannot validate this software layout; browser/manual inspection is required, and prior media-review evidence must not be relabeled as layout acceptance. Project tracking reuses one Aditor card and one briefed Alan/Aditor session; no media or model-review verdict was created for this layout.

## 12. Match current AutoReview / Hand-in — 2026-10-05

**Job and approved direction:** Alan clarified that the final parts interface should look like the current Hand-in/AutoReview. This bounded visual iteration implements that already requested direction; the staging environment is a temporary acceptance preview, not a separate product or final design approval. Apple HIG, Emil and UI/UX Pro Max apply. The live reference at review.aditor.ai was inspected in the browser: compact branded header, system type, dark warm neutrals, coral/orange folder upload, quiet halo, rounded dashed targets. Reuse existing FreeFrame FolderArt rather than draw another upload symbol. This supersedes section6's restriction on reusing the upload artwork, following Alan's explicit correction.

**Screens/navigation:** preserve all existing routes and states. Internal Hand-in retains its role-filtered real dashboard sidebar and existing authorized workspace selector; external request retains the focused task view with read-only destination brand and no management links. No fake sidebar or login requirement on a customer task link. Active feedback retains the current player/list layout.

**Hierarchy/components:** guest header shows actual AutoReview identity and actual destination; title and brief are centered in the existing front-door style at a smaller task scale. Keep the three clearly named responsibility stages. Below them, matched Hooks/Bodies upload zones use the exact existing FolderArt with HOOKS/BODY labels, unchanged accessible file inputs, limits, drag/drop and bulk behavior. Optional parts/details/submit/final ads stay in the existing sequence. Internal setup receives the existing bordered surface and task typography; it does not gain customer management controls.

| Before | After | Why |
|---|---|---|
| Generic upload arrows | Existing coral FolderArt in each role target | Same recognizable upload language as live AutoReview |
| Unbranded destination-only header | AutoReview identity plus read-only destination | Preserve product identity and account clarity |
| Flat left-aligned guest introduction | Centered task introduction, restrained existing halo | Match current entry experience without a marketing pitch |
| Bare internal setup fields | Existing rounded bordered Hand-in surface | Match the current form and team shell |

**States:** empty has two targets and a single disabled submit action until saved; upload/review/revision/held/error/final completion remain unchanged and truthful. Existing retry and closed-link behavior remain. No media/model rerun or account permission changes are needed to validate styling.

**Tokens:** existing handin OKLCH palette and system typography; title34/38 on narrow and40/44 on wide, body16/24, secondary14/22; 4/8grid, 24/32section gaps, 20px corner upload radius, >=44px controls. Quiet background halo derived from existing accent with no animation. Existing 150–200ms hover/press feedback and reduced-motion rules; no entrance delays. Generic UI/UX search suggested ecommerce rating structure and blue/rose colors; rejected because Alan specified the existing orange product identity. Accessibility guidance retained.

**Accessibility/review:** keep ARIA roles, text descriptions and keyboard-focusable native picker; FolderArt is decorative/aria-hidden. Task page has no color-only meanings. Browser screenshot empty and delivered after implementation; check actual dimensions and overflow, then run frontend test/build/tsc/lint. Full VoiceOver, physical touch and manual200%zoom are not implied by screenshots. No open design decision needed: match the existing product, as requested. Automatic video review does not assess software layout.

Section12 implementation evidence: the live reference was visually inspected, then the actual public stage was checked at verified375px and1280px, no horizontal overflow. Self-critique caught owner-workspace blue folder variables; the handin scope now explicitly supplies coral OKLCH folder tones. Phone stage rows were compacted without hiding counts/responsibility. Normal login with the existing isolated editor account reached Hand-in, showing exactly Hand in/Submissions/Projects and no management navigation. Final checks:513tests, build, explicittsc, lint allpassed (existingwarnings). Independent source review:17/17focused regressions, no blocking findings. New light-mode/VoiceOver/manual200% acceptance remains outstanding; unchanged underlying light tokens are not a substitute for browser acceptance. The same project card/session was updated, not recreated. No model/media/production actions.

Screenshots: [1280px empty](handin-evidence/oct5-autoreview-look-empty.jpg), [375px empty](handin-evidence/oct5-autoreview-look-mobile.jpg), [existing editor Hand-in](handin-evidence/oct5-autoreview-look-editor.jpg).

## 13. Match AdMixer upload areas — 2026-10-05

**Job / approved direction:** Alan explicitly requested that the upload areas look closer to AdMixer. This is a bounded styling revision to existing part targets. The actual authenticated live upload screen at mix.aditor.ai and source StageColumn.jsx/UploadZone.jsx/index.css were inspected read-only: compact140px targets,12px radius, subtle raised panel lighting,40px orange upload symbol with a rotated rim, short14px drop prompt, and small heading count badges. No production action was taken.

**Navigation / hierarchy:** retain current internal/customer roles, real destination brand, three responsibility stages, part explanations, optional stages and final ads. Only role headings/count presentation and drop-zone material/size change. The native picker and existing drag/drop are the same. AdMixer URL-import fields and library buttons are not displayed because this hand-in has no equivalent supported import/library action; adding those would require a separate functional task.

| Before | After | Why |
|---|---|---|
| Large240px targets with FolderArt | Compact140px raised dashed panels | Match AdMixer's actual working interface |
| Large folder illustration and bold prompt | 40px Upload symbol and short14px prompt | Same recognisable control as the Mixer |
| Count placed across the entire column | Small count badge beside role title | Match stage-heading grouping |

**States/components:** empty and drag-hot use the new target; file rows, exact transfer percentages, review/error/retry and delivered state are unchanged. Native file input keeps `Upload hooks` / `Upload bodies`, supports multiple video files, and exposes focus around the whole target. Upload-symbol layers are decorative and aria-hidden. No new setting, processing state or permission.

**Tokens/accessibility:** existing Hand-in dark/light OKLCH semantics;12px radius,24px padding,140px min target,40px icon container with20px icon,14px/22px secondary type, 4/8grid. Material lighting and accent follow existing appearance; no new font/assets/dependency. Hover on fine pointers only; keyboard has no motion, Reduce Motion removes decorative hover transforms. Touch target exceeds44px. Text and file limits remain visible, never only color.

**Review:** screenshot actual empty targets at desktop and375px after implementation; inspect focus and confirm no overflow. Run existing frontend tests/build/tsc/lint; independent review checks for truthful state preservation. No media/model reruns are required for visual styling. Existing light-mode/VoiceOver/manual200% acceptance limits remain explicit; final human design acceptance remains with Alan. Same trackingcard/session will be updated, no new project created.

Section13 acceptance: actual HTTPS staging inspected at1280px in both dark and light mode and at verified375px in dark mode, with no horizontal overflow. Compact panels remain aligned on desktop and stack clearly on the phone. Keyboard Tab moves from the native Hooks picker to Bodies, showing the full-target2px accent focus ring. The isolated editor's original dark appearance was restored and the temporary viewport override reset. No files were uploaded and no model reviews were invoked for this styling revision.

Fresh validation:17/17 independent focused regressions passed with no blocking finding; all76frontend test files and513tests passed with `--maxWorkers=2`; production build, explicit TypeScript and lint passed (existing warnings). The first unconstrained full run hit10unrelated5000ms timeouts under local load47; the successful bounded-concurrency rerun used unchanged tests and timeouts. No backend behavior changed. VoiceOver, physical touch and manual200%zoom were not tested; owner design acceptance and real Trello delivery remain pending. The existing Aditor card and Alan/Aditor briefed session were updated in place.

Screenshots: [desktop dark](handin-evidence/oct5-admixer-targets-dark.jpg), [desktop light](handin-evidence/oct5-admixer-targets-light.jpg), [375px phone](handin-evidence/oct5-admixer-targets-mobile.jpg). Section12's large FolderArt targets are the before reference; these compact AdMixer-style targets are the current parts-upload design.
