# Handoff — AutoReview link + comment hook (Brand Loop, Lane F) — 2026-10-16

Pairs with the feedback-agent Brand Loop PR. Contract:
feedback-agent `docs/superpowers/specs/2026-10-16-brand-loop-CONTRACT.md` (branch `spec/brand-loop`).

## What shipped
| Task | Commit | What |
|---|---|---|
| F1 | 53f7ac4 | `projects.autoreview_brand_slug` (nullable, indexed, no backfill) + superadmin-only `PUT /admin/projects/{id}/autoreview-brand` `{slug}` (kebab regex, null unlinks) |
| F2 | 4bde856 | `services/brand_loop.py`: after create / reply / share comment commit, a background task POSTs the contract payload to `AUTOREVIEW_URL/api/brand-loop/comment` (Bearer `BRAND_LOOP_SECRET`, 3 s, never raises) |
| F3 | b9ff48f | `GET /autoreview/brands`, `GET /autoreview/link?brand=` (HS256, iss freeframe, aud review:brand, 60 s) + sidebar entry `components/layout/autoreview-nav.tsx` |
| review fixes | 9a39ff8 + follow-up | orchestrator decisions: token `brands` = requested slug only; hook before hub_events; workspaces only; members only; non-public comments skipped |

## Tests
- API: 732 passed / 196 skipped before → 766 passed / 197 skipped after (`python -m pytest apps/api/tests/`).
- New opt-in Postgres test `test_autoreview_brands_postgres.py` passed against a local scratch Postgres; migration upgrade → downgrade → upgrade also ran clean there.
- Web: 702 tests / 102 files before → 707 / 103 after; `tsc --noEmit` and `lint` clean.
- Sidebar screenshot-checked (expanded, collapsed, menu) via a throwaway preview page with a mocked API.

## Decisions
- Slug lives on the **project** and only on brand workspaces (`is_workspace`); FreeFrame has no workspace table. Several workspaces may share one slug on purpose (orchestrator).
- Admin = superadmin (`require_admin`), dedicated endpoint; `{"slug": null}` unlinks, empty string is rejected.
- `authorIsClient` = not Aditor staff, where staff = `@aditor.ai` address or listed in the people directory (`DIRECTORY_LOOKUP_URL`, the roster OIDC sign-in uses; lookup runs in the background task, directory down → domain rule only). `User.is_staff` is never used: invited client accounts default to true.
- Only `visibility == "public"` comments are sent (orchestrator): internal staff notes stay in FreeFrame. The AutoReview bot's comments are stored internal, so in practice they are not sent either; if one ever were public it goes out with `authorIsClient:false`.
- Hook is queued before `hub_events.announce_client_comment`, so a failing hub call can't swallow it. No retry: W backfills idempotently by commentId.
- Brand access = a live `ProjectMember` row on a live project with that slug, or superadmin (all linked brands). Creator and the instance-wide staff role grant nothing. Label = oldest such project's name.
- `/autoreview/brands` is an addition to the contract so the sidebar knows whether to render; `[]` when the env is unset. `ProjectResponse` unchanged (sidebar doesn't need the slug).
- `background_tasks` is a trailing `= None` parameter so existing direct-call tests stay untouched; FastAPI still injects it (pinned by a test).
- `test_whop_migration.py` head pin extended with the new head (as every earlier migration did).
- Mobile bottom bar unchanged.
- `superpowers:code-reviewer` agents mostly failed to hand back reports; findings arrived late via messages and a general-purpose reviewer. No criticals.

## At deploy (not done here)
1. Env on the API: `AUTOREVIEW_URL=https://review.aditor.ai` and `BRAND_LOOP_SECRET=<same value as the Worker>`.
2. Run the migration (`alembic upgrade head`).
3. As superadmin: `PUT /admin/projects/<id>/autoreview-brand` `{"slug":"audibene-gmbh"}` for every audibene workspace (audibene-workspace and the other audibene-gmbh workspaces). Clients only see the entry if they are members of one of them.
