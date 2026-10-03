# Telehealth preview verification — October 3, 2026

## Candidate evidence

- FreeFrame backend: 419 passed, 51 optional integration tests skipped in the standard mock-based run.
- Separate isolated PostgreSQL run: 3 passed, covering concurrent brand creation, unique usage persistence, and the existing staged request upload/version/finish journey.
- Frontend: 499 tests in 73 files passed under Node 22.22.3. Production build passed; explicit typecheck and lint run. Lint reports pre-existing image/hooks warnings.
- Independent code reviews identified and corrected authenticated-editor cutoff bypasses, unsafe upload recovery, transaction lock release during usage recording, request-owner attribution, mismatched-version campaign counting and edited-feedback retry loss.

## Visual checks

Actual React components were rendered in a temporary local fixture and inspected through the in-app browser. The fixture route was deleted before the final build. Its sample usage count is synthetic, not a production customer claim.

| State | Evidence |
| --- | --- |
| Active desktop preview | [Screenshot](design/screenshots/telehealth/active-desktop.png) |
| Expired mobile, light | [Screenshot](design/screenshots/telehealth/expired-mobile-light.png) |
| Expired desktop, dark | [Screenshot](design/screenshots/telehealth/expired-desktop.png) |
| Feedback connection failure, draft retained | [Screenshot](design/screenshots/telehealth/feedback-error-desktop.png) |
| Mobile 200% text, no horizontal overflow | [Screenshot](design/screenshots/telehealth/expired-mobile-text200.png) |

Feedback sheet opens with focus on its close control; Escape returns focus to Give feedback. Plan links were inspected read-only at their real Whop checkouts. No purchase, live feedback post or customer email was made.

## Not established by these checks

No new free Whop product exists yet, and production has not received these candidates. Fresh signup, live rule import/review, tenant isolation across two real new accounts and a real daily #automations digest remain release gates. The documented existing Slack token is revoked. Whop legal-terms approval is pending. See [release notes](telehealth-october-preview.md) for configuration and rollback prerequisites.

Related draft PRs: [Suite #26](https://github.com/videoaditor/aditor-suite/pull/26) and [Pages #521](https://github.com/videoaditor/aditor-ops/pull/521). Their isolated checks report 248 Suite tests and 2040 Pages tests, respectively; both remain undeployed drafts.
