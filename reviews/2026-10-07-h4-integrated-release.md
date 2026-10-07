# H4 integrated first-release qualification — 2026-10-07

**Scoped candidate passed; production deployment remains owned by the original coordinator. This is not a claim that all client-facing AutoReview routes, Parts or source production are finished.**

## Frozen inputs

| Repository | Integrated runtime / validation head | Inputs |
| --- | --- | --- |
| FreeFrame | `a6cf68c6b53a6648e5be1bc95975c98f85c65bff` | H1 `c184fcb6bf71af4e4caeb97711675daa1659e904`, H2 `750388c63bf666cf55e40123cf6200ad68577dbf`, H3 `394ddbf6633b8953eb9c2d41d4cc657e3397636c` |
| Worker | `6e2dd47` | H1 `4d0383d09ab98fcbddd88bf6d9e0438677581bcd`, H2 `ed2ac06bc82a8bb09a4e90e2830c1f56e6ca03fc`, H3 `910827d702528d45deff2c85288c4dc82e4fb4d5` |

FreeFrame joins H1/H2 migrations through **c4d7e10b2026**, down revisions `(a1c7e10b2026, a7b2c3d4e5f6)`, both retaining original parent e4f5a6b7c8d9. Never merge/deploy the sibling migrations as unresolved heads. Upgrade from an empty dedicated database through both heads passed. The a6cf68c successor to c16daa8 changes only a lifecycle test fixture: the synthetic project owner now has the owner membership that the real create_project endpoint creates. No application permissions changed.

Worker conflicts were resolved by retaining H1's latest RFC8785 decimal-capable canonical implementation/fixture, then combining H2's postPlannedComment with H3's publicationFailed tracking. The plan API remains disabled, existing Engine/default variables unchanged. Private snapshot consumption/new source producer, second Engine and Parts are separate follow-ups.

## Verification

| Check | Evidence |
| --- | --- |
| Complete API suite including opt-in H2/n8n PostgreSQL | **558 passed, zero skipped**, isolated PostgreSQL16 `h4_h2_test` at c4, isolated Redis14; strict named-database opt-ins enabled. Earlier ordinary run:549 passed/9 skipped. |
| Web suite | **84 files / 564 tests passed**, Node22.22.3, two workers. |
| Web build, tsc, lint | All exit0; existing image lint warnings remain. |
| Combined Worker suite | **130 files /1437 tests passed**. |
| Worker types | Same **161 baseline diagnostics**, zero added or removed after normalizing locations ([comparison](h4/evidence/worker-types-comparison.json)). |
| Real local stack | Real Postgres, Redis, S3-compatible storage, FFmpeg/Celery, candidate API, production Next build, actual Worker logic with in-memory KV. Only provider/Trello responses injected. External I/O rejected; no paid calls, customer messages or production writes. |
| H1 unavailable Engine fallback | Real Celery default queue registered request200, persisted snapshot200, received plan503, re-registered200. Upload/review proceeded; no ready plan claimed. |
| Browser-generated href | Actual Owner RequestSheet/API returned `/r/nJsHKv-SKYbxwXjSiKYU-2MCop5i5xxz`, opened without editor account. This is a local capability, not a live customer link. |
| V1 feedback and timeline | Synthetic five-second upload stored actual DB comment at2.0s on exact V1. Browser timestamp currentTime2.0; ArrowRight timeline2.1. Reload retained comment. |
| Renamed V2 and outage | Browser uploaded synthetic-renamed-v2.mp4 to same asset; old V1 note absent from V2, available through V1 History. Injected provider outage left current version reviewing; finish returned409. |
| Recovery/completion | Provider restored with injected clear response; same V2 finished, robot completion displayed. One active asset/two versions; completion_versions binds V2, only V1 contains its original comment ([DB](h4/evidence/candidate-version-binding-db.json), [API](h4/evidence/candidate-v2-completed.json)). |
| Customer share | Actual completed `/share` opens FolderShareViewer and full VideoPlayer with latestV2, no editor upload-v2/finish controls. Public/internal visibility is exercised by real PostgreSQL source tests. |
| Independent review | Fresh read-only review found no blocking integration/security regression for plan-API-disabled first release. One P3: ready-plan registration_error is not surfaced/retryable in ChecklistPanel. Must address before enabling plan API. |

Initial red runs are retained locally: old e4 fixture DB lacked H1/H2 schema; a fresh migration invocation omitted JWT_SECRET; synthetic owner lacked real project membership; repeated login checks shared a Redis limiter. After correcting those test conditions, all558 passed. Tests were not skipped to hide failures. Host Python lacking pinned rfc8785 was replaced by the candidate Docker runtime.

## Actual routes and qualification

| Route | Role / target | Current evidence | Boundary |
| --- | --- | --- | --- |
| `review.aditor.ai/o` | owner → login?from=/home | live302 →200 | Owner login target already correct |
| `review.aditor.ai/d/{brand}` | public brand-scoped legacy → legacy upload/check UI | live200 on /d/aditor | Not converted by frozen release; no blind privilege-changing redirect |
| `review.aditor.ai/u/{token}` | legacy scoped token → legacy upload/check UI | shell200 for invalid token only | Valid legacy token/session not qualified |
| `review.aditor.ai/review/{id}` | legacy saved report → legacy saved review | invalid ID404 | No actual valid report journey claimed |
| `review.aditor.ai/share/{token}` | none → 404 | live404 invalid token | Canonical customer shares use feedback domain |
| `feedback.aditor.ai/r/{token}` | public request capability, editor identity at upload → native editor upload, comments, revisions, completion | live existing player seek3s; candidate actual generated link + V1/V2 pass | Canonical newly generated Owner request href; H2 labels render only from persisted metadata |
| `feedback.aditor.ai/s/{token}` | not a supported public share route → login then no route | live307 to login; runtime manifest has no /s | Existing /s handoff link is invalid; never blanket redirect to editor |
| `feedback.aditor.ai/share/{token}` | share-scoped customer viewer/commenter → customer delivery/review | candidate actual completed share browser verified | No upload-v2/finish controls; internal automation comments hidden from public reads |
| `feedback.aditor.ai/handin` | authenticated staff / Whop → internal Trello intake produces /share delivery link | live307 to login unauthenticated | Internal editor /r checks path still open; no blanket /share→/r redirect |
| `feedback.aditor.ai/whop` | Whop identity + Suite grant → existing workspace + same RequestSheet | live shell200; app ID verified by coordinator | Actual customer Whop session/configured iframe href not observed |
| `feedback.aditor.ai/o` | owner → /whop | runtime route manifest | Different from review-domain /o; preserve intended auth contexts |
| `feedback.aditor.ai/parts` | flagged internal component flow → Hook→Bridge→Body→CTA | not in frozen candidate | Requires separate PR46 integration and build/server flags; H3 adapter42fa42c is follow-up |

See [machine-readable route matrix](h4/evidence/route-matrix.json) and [read-only HTTP chains](h4/evidence/routes-live.json). Shell200 on an invalid token is not a valid-token pass.

## Before / after and integration screenshots

H2's actual editor-route [before](https://github.com/videoaditor/freeframe/blob/a6cf68c6b53a6648e5be1bc95975c98f85c65bff/reviews/evidence/h2/editor-desktop-before.jpg) and [after](https://github.com/videoaditor/freeframe/blob/a6cf68c6b53a6648e5be1bc95975c98f85c65bff/reviews/evidence/h2/editor-desktop-after.jpg) live in the integrated candidate. Its earlier component-only screenshot was not accepted as the real player.

| Integrated real-stack state | Screenshot |
| --- | --- |
| Actual V1 player, timestamp and persisted note | [V1](h4/evidence/candidate-editor-v1.jpg) |
| V1 history while V2 is reviewed | [history](h4/evidence/candidate-v1-history.jpg) |
| V2 provider outage, no false ready state | [outage](h4/evidence/candidate-v2-provider-outage.jpg) |
| Successful exact-version completion | [robot](h4/evidence/candidate-completed-robot.jpg) |

All new screenshots contain synthetic footage/fixture data. Self-review confirms the existing native timeline/marker, right-side timestamp note, clear V1 history and completion state. H2's 390px layout has no horizontal overflow; earlier live-main mobile scrolling clips the video's top when reaching a lower comment. Full simultaneous video/comment visibility on every mobile viewport, native200% zoom and OS Reduced Motion remain unverified; no complete accessibility pass is claimed.

## Live inventory and release boundary

Read-only production evidence: feedback.aditor.ai nginx points to127.0.0.1:3090 web and3091 API. All181 running API Python files match main2e720a39. Running web build is P3Y4Yty2XQoEi5nRnSvr7; route manifest lacks /s. review.aditor.ai is Cloudflare service feedback-submission-production, current version857086a2-3adf-4788-8319-2d4bcd75b7f8. Existing live /r timestamp seeks3.0s and keyboard timeline3.1s; this does not prove this candidate deployed.

Root alone owns production backup, temporary hook pause, integrated PR merges, immutable images, migration and serving switch. Worker main-push deploys automatically through existing GitHub Action; avoid a parallel CLI deploy. Root's validated backup is /var/backups/freeframe/autoreview-20261007-client-facing/postgres.dump (2,003,540bytes). H4 performed no production mutation.

Remaining scope is explicit: actual Whop customer session/configured iframe link; legacy /d,/u conversion; internal /handin editor-request association (currently returns /share delivery); separate PR46 Parts plus H3 adapter42fa42c; saved snapshot consumption and truthful source-bearing producer; natural timing calibration; plan-ready registration recovery UI. Nullable legacy source remains null. Failed legacy guest-comment POST completion behavior predates this release; H3 excludes its timing sample but does not repair delivery reliability.

Existing Trello card: https://trello.com/c/HaBvLzZK. Software-only project session: https://feedback.aditor.ai/r/Q7JENfgm6yPkL2Q8Q_N9bKUkGU_bZPFT. Automatic video acceptance is unsupported for software; no video-review pass or human final acceptance is asserted.
