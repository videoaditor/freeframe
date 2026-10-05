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

## October 5 integration verification

The campaign candidate incorporates main through `d2b0228`, preserving deferred editor identity, measured review progress, the early 360p review proxy and resilient multipart uploads. The guest completion merge retains the campaign cutoff check and main's persisted uploader record. Its two main-branch fixtures now patch the recovery-aware request lookup and lock.

Fresh checks on the integrated source: backend **442 passed, 51 optional integration checks skipped**; separate isolated PostgreSQL concurrency/upload journey **3 passed**; frontend **512 tests in 74 files passed**; production build, explicit TypeScript check and lint passed (existing image/hooks warnings). Backend used the existing local Python 3.14 environment; frontend used Node 22.22.3. Both additive campaign/feedback migration functions were also applied to an isolated PostgreSQL schema representing the preceding schema; an existing paid user retained its identity and null campaign context.

This evidence covers local integration, not a deployed signup or media-review acceptance. Before rollout, record the actual running API and web images separately: other concurrent work may be deployed beyond the server checkout. Never replace a newer live web image merely because the server checkout is older. The new schema is additive: `d0e1f2a3b4c5` → `c3d4e5f6a7b8` → `e4f5a6b7c8d9`.


### Preserving the deployed mobile fixes and paid revalidation

The release candidate also incorporates the exact clean live web source `0d1bf46808e6843a495af1d9d3c2eb362da3f245`, including mobile preview/comments and touch timeline fixes. The combined frontend passes **519 tests in 76 files**, production build, TypeScript and lint. The final backend passes **446 tests, 51 optional skips**.

A saved paid override is now revalidated against Suite for guest access after the cutoff. Revoked paid access, unavailable entitlement service and missing campaign attestation fail closed; valid paid access remains available. Four new regression cases failed before the fix and pass after it. This read-only check neither mutates user campaign context nor commits the caller's transaction, preserving upload locks. An expired preview still requires the owner to reopen Whop after upgrading before guest links resume.

GitHub CI additionally caught the production Alembic entrypoint importing new models as top-level modules. Both new models now follow the existing dual-import convention. A subprocess regression exercises the actual `alembic upgrade d0e1f2a3b4c5:head --sql` command; it failed before the import fix. The corrected full backend suite passes **447 tests, 51 optional skips**. A fresh isolated PostgreSQL database also runs the complete Alembic upgrade chain successfully.
