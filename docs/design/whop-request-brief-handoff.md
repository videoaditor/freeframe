# Design handoff — Whop request briefing

## Job
Whop members create a request link using their existing brand and an ordinary Word, PDF or text briefing. Web desktop and touch. Success is the copyable request link; existing branded projects stay intact.

## Screen and navigation
The existing Request files sheet remains over the owner dashboard, dismissed by Close or Escape. Brand guidelines use the existing import sheet. No navigation changes.

## Hierarchy and components
| Element | Component | Copy / behavior |
| --- | --- | --- |
| Brand context | Plain text when exactly one brand | “For Fortea”; no redundant choice |
| Multiple brands | Existing select | “Brand”; keep existing projects selectable |
| Project title | Existing labeled text input | “Project name”; receives initial focus |
| File attachment | Existing DropZone | “Drop a briefing”; “Word (.docx), PDF, Markdown or text · up to 10 MB” |
| Submit | One prominent button | “Create link”; “Creating…” while pending |

## States
Empty account: backend creates one isolated brand workspace for the verified Whop owner. Loading: retain the existing loading brand control. Invalid/empty/corrupt document: explain recovery and preserve title, file and entered text. Success: existing link card. Permission failures use API message; no cross-account fallback.

## Tokens and motion
Keep existing owner-sheet semantic OKLCH colors, light/dark tokens, system font ramp (22px title, 15px labels, 13px hints), existing 4/8px spacing and sheet/press animations. Reduced-motion rules already apply. No added effects or dependencies. Upload behavior is not HIG-specified; use shared app component.

## Accessibility
44px touch targets for controls changed here; named close/remove buttons; error role=alert. Keyboard focus begins on project title for a preselected brand. Preserve Radix focus trap and Escape. Primary brand/title text wraps at 200% zoom.

## Decisions
No open user decisions. Existing customer project identity, permissions and review-rule namespace are preserved. Brand display names never authorize binding.

## Review
Inspected the local preview at 1280×720 in dark/light and 375×812 in dark mode. Single-brand context is legible, title receives focus, the Word attachment remains visible and the primary action stays reachable. Mobile document width equals viewport width (375px); the changed remove control measures 44×44px. Form error preservation and stale brand selection have regression coverage. The desktop success state was exercised against a synthetic preview API; real DOCX extraction plus proxy-safe authentication is verified separately by the HTTP regression test. No production Whop session or paid AI review was used for these screenshots.

Evidence: [before](screenshots/whop-brief-20261010/before-word-rejected.png), [desktop dark](screenshots/whop-brief-20261010/word-attached-desktop-dark.png), [desktop light](screenshots/whop-brief-20261010/word-attached-desktop-light.png), [mobile dark](screenshots/whop-brief-20261010/word-attached-mobile-dark.png), [preview success](screenshots/whop-brief-20261010/word-link-success-desktop-dark.png). Existing app spacing, semantic colors and motion remain unchanged; the narrower mobile sheet wraps helper copy without clipping.

| Before | After | Why |
| --- | --- | --- |
| Word file rejected after choosing it | Word file encoded, validated and parsed server-side | Normal brief handoff works |
| Single Whop brand has a selector or asks for a new brand | Existing/provisioned brand shown as context | Remove an unnecessary decision |
