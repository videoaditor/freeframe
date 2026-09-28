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
