# Compact leaderboard — 2026-09-28

## 1. Job
Owner scans accuracy quickly on mobile/desktop. Four editors should fit in ~240px of rows.

## 2. Navigation
Overview retains existing sidebar/bottom tabs. Native inline disclosures open/close row details; invite opens the existing request sheet; guidelines link opens /rules.

## 3. Hierarchy
Header + compact Invite action; first-try accuracy subtitle; single-line rows with rank, initials avatar, name, accuracy and chevron; methodology disclosure. A compact blue book reminder follows.

## 4. Components
| Element | Pattern | Label | Behavior |
|---|---|---|---|
| Editor row | List + disclosure | Name, accuracy | Whole row toggles details, minimum 56px high |
| Invite | Button | Invite editor | Existing request sheet; full accessible label retained |
| Guidelines | Link | Never say the same thing twice | Small tilted book icon on blue inset surface, no loop |

## 5. States
Keep existing loading, empty, error/retry. Unknown accuracy remains unranked, not 0%; small samples keep a visible marker with accessible explanation. Initials use the existing Avatar component; no email-to-image lookup or fabricated portraits. Current API has no image field.

## 6. Tokens
Existing typography and semantic light/dark colors. 4/8 grid; 14px names, 16px score, 12px details. 32px avatars, subtle accent for first place with crown. OKLCH color mix for book reminder. No entrance or ambient animation; existing press feedback only. Search recommendations were evaluated; existing product tokens take precedence over new fonts or marketing layouts.

## 7. Accessibility
Entire summary is keyboard-focusable with focus ring and visible chevron; 56px+ touch target. Break long names; details preserve all values. Rank/crown do not replace text. Avatar decorative next to name. Contrast uses existing semantic tokens. Responsive/200% text should wrap, not clip.

## 8. Decisions
User requested compact + playful; implement directly. Profile images need a backend-supported source before displaying real photos.

## 9. Review
Inspect 697px and 375px, light and dark, disclosure, invitation sheet and rules link. Record screenshots and checks after implementation.

| Before | After | Why |
|---|---|---|
| ~124px rows with repeated View details | ~56px clickable disclosure rows | Accuracy is the one scanning metric |
| Paragraph + invite takes two lines | Header invite; instructions in methodology | Keep list first |
| Plain guidelines strip | Blue miniature playbook with bookmark | More character without a large promo panel |

## Verification
404 frontend tests passed, including compact disclosure content coverage (failed before, passed after). Production build, TypeScript and lint passed; lint retains existing warnings. Browser: 697px light/dark and 375px dark inspected; row height 56px, phone document width 375px. Details expose the right email/counts, Invite opens request sheet and Escape closes it. Screenshots: `screenshots/compact-ranking-light.png`, `screenshots/compact-ranking-mobile-dark.png`. No new network/avatar service, dependency, or backend change. Physical screen reader and 200% zoom not verified.
