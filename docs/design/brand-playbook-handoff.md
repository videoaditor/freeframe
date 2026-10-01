# Brand playbook — design handoff

## 1. Job
Brand owners need to recognize their standards at a glance and read complete guidance when needed. Existing rules page, desktop and mobile web. Success: distinguish active brand rules from pending suggestions and general practice, find a rule, inspect its full text, and import guidance using the existing API.

## 2. Screens and navigation
Brand rules remains the sidebar/tab destination. Brand selector changes the playbook. Rule details and importing guidance use separate Radix sheets with Close/Escape. Existing logo upload remains available alongside the playbook. Changing brands resets that brand's transient search, detail, import and decision state.

## 3. Hierarchy
Brand rules heading and brand selector → compact blue playbook cover with actual active-rule count and Add guidelines → collapsed suggestion approval area → active rule cards with search/severity filters → best-practice disclosure. Importing new suggestions opens approval automatically. Logo in a secondary desktop column; after rules on phones.

## 4. Components
| Element | Pattern | Label | Purpose |
|---|---|---|---|
| Cover | Summary surface | Brand name + Playbook | Characteristic blue book treatment; real counts |
| Rule | Button card | Rule title, Must follow / Guidance | Numbered, readable excerpt; opens full text |
| Details | Sheet | Rule title | Complete text, preserved line breaks and long words |
| Search/filter | Field + buttons | Find a rule / All / Must follow / Guidance | Flexible without inventing backend categories |
| Suggestions | Approval list | For your approval / Use rule / Dismiss | Drafts stay distinct from live rules |
| Import | Sheet | Add guidelines | Existing PDF/text/link import; returns suggestions |

## 5. States
Loading: skeletons and unknown count. Empty: illustrated playbook placeholder and Add guidelines action, no fabricated active rules. Search empty: Clear filters. Error: plain explanation and Retry, never a false empty library. Import and decision pending: disabled actions and clear pending labels; errors retain input or suggestion for retry. Brand switch isolates in-flight state. No unsupported direct rule editing or deletion controls.

## 6. Tokens
Blue + neutrals, reusing owner-workspace OKLCH tokens. 34px page title, 24–28px playbook brand, 16px rule headings, 14px excerpts, 12–13px labels. 4/8px grid; 16–24px card padding, 16px gaps. Subtle highlights, book-spine detail and inset edges. Existing shared sheet/press motion with reduced-motion fallback. Card numbering and cover styling are product choices, not HIG requirements.

## 7. Accessibility
44px controls, native labeled select/search, full title accessible names, severity conveyed in words and icon, focus containment and Escape for sheets. Full text available without hover. Excerpts can clamp only because the whole card opens complete guidance. Phone cards stack; long brand names and rule text wrap.

## 8. Decisions
Use existing rules/import/suggestion and branding endpoints. Preserve arbitrary prose; avoid inferred categories or invented examples posing as rules. Keep the briefing > brand > best-practice hierarchy in a compact explanatory line. No engine changes.

## 9. Review checklist
Empty and populated layouts inspected in the browser. Full rule text, search/no-match/clear, severity filtering, Escape and focus return verified. Local fixture journey: accept suggestion → active card appears → import text → draft appears in approval area → dismiss → switch brand → correct empty playbook. Phone layout at 375px has no document overflow; reading sheet is within the viewport. Unit tests cover errors, input retention, inactive rule exclusion and late import isolation after brand changes. No production AI import during verification.

| Before | After | Why |
|---|---|---|
| Compact rows with clipped guidance | Numbered cards and full-text sheets | Strong identity without losing longer instructions |
| Import area dominates the page | Blue playbook cover; importing in a sheet | Makes active rules the main content |
| Red dot indicates severity | Blue spine and explicit Must follow label | Accessible meaning within the two-color direction |
| Suggested rule disappears before save | Pending state until confirmed success | Failed approvals remain visible for retry |

Full check results and screenshots are recorded in `owner-overview-verification.md`. Physical screen-reader and 200% text-zoom checks remain unverified.

Sources: Apple HIG disclosure controls, sheets and existing local skill numbers; Emil design engineering motion/press guidance; UI UX Pro Max accessibility, contrast and responsive guidance.

## Quick-input refinement — September 28
The Add guidelines sheet opens directly to a labeled, three-row text field (autofocus) for a short instruction or link. Example: “Don’t show that guy with a beard anymore.” Primary action: Suggest rules. A compact PDF drop target remains below; no mode switch or Back button. Preserve draft text on errors/close; successful import still opens the approval area, never silently activates a rule. Reuse existing controls and semantic tokens; minimum 44px buttons, responsive sheet scroll, disabled inputs while importing. Browser check at 697px and 375px plus existing failed-import, URL and brand-isolation tests.

Quick-input verification: 405 frontend tests pass; production build, TypeScript and lint pass (existing warnings). Browser: initial autofocus, one-line text → pending suggestion, unchanged active-rule count, reopening with empty successful draft, 697px light/dark and 375px dark. Mobile sheet fits x=16..359 and y=65..572; no document overflow. Synthetic API only; no live rule activation or AI-compilation claim. Screenshots: `screenshots/quick-guideline-light.png`, `screenshots/quick-guideline-mobile.png`.

## Text-first correction — September 28
Supersedes the modal-first quick-input refinement. Quick rules are an always-visible, compact text composer on the rules page; no modal and no automatic keyboard on page load. The large book cover is replaced by this useful action. A small Import guidelines link opens PDF import only. Empty-library action focuses the composer. Text/link submissions use the existing suggestions API, preserve failures, reset successful input and retain owner approval. All actions have 44px targets, existing tokens and no new animation.

Text-first verification: 406 frontend tests pass; build, TypeScript and lint pass (existing warnings). Browser verified inline text submission → cleared composer + suggestion below; import modal opens/closes; 697px light and 375px dark inspected. No backend/AI changes; local fixture only. Screenshots: `screenshots/text-first-rules-light.png`, `screenshots/text-first-rules-mobile.png`.

## Book + Autoreview identity — September 28
Restore the existing CSS book to the left of the inline composer on desktop and in a small header above it on phones. Keep the composer directly accessible; remove its helper sentence. Placeholder example: “Always show the [brand] logo on the end card.” Brand name derives from current selection. Reuse book artwork/tokens; no new animation. App identity becomes Autoreview with the original review icon from Aditor’s Google Drive; Aditor moves to a subtle sidebar footer. Preserve custom instance branding and migrate only the previous default. Validate desktop/mobile, book placement, input, sidebar and persisted default naming.

Identity verification: 408 frontend tests, TypeScript, lint and isolated production build pass (existing lint warnings). Browser checked at 910px desktop and 375px phone in dark mode: restored book placement, visible brand-specific example, no helper sentence, Autoreview icon/name and subdued Aditor footer. The preview notification fetch failed transiently during development; reload with the fixture API available cleared it. Original icon downloaded unchanged from [Internal Graphics → aditor suite apps → review icon.png](https://drive.google.com/file/d/18CtknPD3zDpU4GJb4bJ_hQTYMdtLRP2k/view), 344686 bytes. It replaces the provisional local review-agent icon. Screenshots: `screenshots/autoreview-book-desktop.png`, `screenshots/autoreview-book-mobile.png`.
