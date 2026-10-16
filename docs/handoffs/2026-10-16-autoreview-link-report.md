# Handoff — AutoReview link + comment hook (Brand Loop, Lane F) — 2026-10-16

Pairs with the feedback-agent Brand Loop PR. Contract:
feedback-agent `docs/superpowers/specs/2026-10-16-brand-loop-CONTRACT.md` (branch `spec/brand-loop`).

## What shipped
| Task | Commit | What |
|---|---|---|
| F1 | 53f7ac4 | `projects.autoreview_brand_slug` (nullable, indexed, no backfill) + superadmin-only `PUT /admin/projects/{id}/autoreview-brand` `{slug}` (kebab regex, null unlinks) |
| F2 | 4bde856 | `services/brand_loop.py`: after create / reply / share comment commit, a background task POSTs the contract payload to `AUTOREVIEW_URL/api/brand-loop/comment` (Bearer `BRAND_LOOP_SECRET`, 3 s, never raises) |
| F3 | b9ff48f | `GET /autoreview/brands`, `GET /autoreview/link?brand=` (HS256, iss freeframe, aud review:brand, 60 s) + sidebar entry `components/layout/autoreview-nav.tsx` |
| review fixes | see PR | token `brands` = only the requested slug; hook runs before hub_events; staff-on-share test |

## Tests
- API: 732 passed / 196 skipped before → 756 passed / 197 skipped after (`python -m pytest apps/api/tests/`).
- New opt-in Postgres test `test_autoreview_brands_postgres.py` passed against a local scratch Postgres; migration upgrade → downgrade → upgrade also ran clean there.
- Web: 702 tests / 102 files before → 707 / 103 after; `tsc --noEmit` and `lint` clean.
- Sidebar screenshot-checked (expanded, collapsed, menu) via a throwaway preview page with a mocked API.

## Decisions
- Slug lives on **project**, not workspace: FreeFrame has no workspace table; brand workspaces are projects (`is_workspace`).
- Admin = superadmin (`require_admin`), via a dedicated endpoint; not part of the normal project PATCH.
- `authorIsClient` = guest, or account with `is_staff = false` (`services/permissions.is_staff`). Caveat: invited accounts default to `is_staff = true`, so a client who holds a real FreeFrame account is counted as staff unless flagged.
- Comments by `AUTOMATION_GUEST_EMAILS` (the AutoReview bot itself) are not sent: AutoReview must not learn from its own findings. Internal-visibility staff comments are sent (contract: W decides).
- Brand access = explicit `ProjectMember` row or project creator; superadmins get every linked brand. The instance-wide implicit staff role does not count (it would give every account every brand).
- `/autoreview/brands` is an addition to the contract so the sidebar knows whether to render; returns `[]` when the env is unset.
- `background_tasks` is a trailing `= None` parameter so existing direct-call tests stay untouched; FastAPI still injects it (pinned by a test).
- `test_whop_migration.py` head pin extended with the new head (same as every earlier migration).
- Mobile bottom bar unchanged (page links only).
- Reviewer agents (superpowers:code-reviewer) never delivered reports; one general-purpose reviewer did (no criticals).

## At deploy (not done here)
1. Env on the API: `AUTOREVIEW_URL=https://review.aditor.ai` and `BRAND_LOOP_SECRET=<same value as the Worker>`.
2. Run the migration (`alembic upgrade head`).
3. As superadmin: `PUT /admin/projects/<audibene-workspace project id>/autoreview-brand` `{"slug":"audibene-gmbh"}`.
