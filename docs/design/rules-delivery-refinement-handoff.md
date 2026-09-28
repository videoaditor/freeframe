# Rules and finished deliveries — September 28

## 1. Job
Owners add short QA rules, inspect what reviews check, and preview/share finished ads on mobile and desktop.
## 2. Navigation
Existing sidebar/tabs stay. Rule details and sharing use dismissible sheets. Ready cards link directly to their delivery folder.
## 3. Hierarchy
Rules: quick composer, suggestions, two columns (Must follow then Guidance), alphabetically sorted compact entries. Full definition opens on the entry, with no promotional View rule CTA. Ready card: title, status, Preview and Share.
## 4. Components
Reuse RuleLibrary, LinkCard, ProjectKanban and native appearance settings. Upload links say Open upload page. Delivery links use the backend review_share_token at /share/token and permit downloads under existing server permissions.
## 5. States
Search retains a no-match reset. Empty categories are explicit. Missing delivery token displays a recovery message, never falls back to an upload link. Existing rule saving has no owner API contract; definitions remain honestly read-only until backend adds it.
## 6. Tokens
Existing semantic OKLCH palette and 4/8 spacing. Compact 14–16px rule titles, 13px excerpt. No new motion. Portrait option is 9:16 with fit thumbnails; narrower asset columns.
## 7. Accessibility
44px actions, labeled controls, Escape sheets. Quick composer uses one subtle border focus indicator instead of nested blue outlines. Browser comment-selection outlines are external and cannot be styled by the app. Group headings expose meaning without color.
## 8. Backend dependency
Owner rule update must validate brand ownership and rule scope, persist definition, and return the saved row. No secret-bearing direct Worker calls from the browser. No fake save action.
## 9. Review
Verify desktop/mobile rules, focus state, ready Preview vs Share files, upload page labels and portrait video layout. Regression check prevents upload links for ready deliveries.

Browser evidence: desktop and 375px dark rule groups checked; delivery sharing resolves to /share/delivery3 with four files and Download controls in the local fixture. Download action reached the fixture MP4. Portrait thumbnails fit 9:16 without cropping; grid width follows available space with optional side panels. Existing saved appearance choices are preserved. Live storage downloads and rule-update persistence are not claimed. Screenshots in `screenshots/`: rules-compact-grid, rules-compact-mobile, delivery-share, portrait-deliveries.

| Before | After | Why |
|---|---|---|
| Repeated View rule links in tall rows | Compact category columns and click-to-inspect entries | Transparency without a competing CTA |
| Ready share opened upload form | Existing backend download-share token | Recipient sees the finished files |
| Landscape default and viewport-sized grid | 9:16 default and available-width grid | Vertical ads fit without clipping |

Checks: 409 frontend tests pass, TypeScript and lint pass (existing warnings), isolated production build passes; four synthetic API route-contract checks pass.
