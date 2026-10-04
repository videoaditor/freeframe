# Hand in by link (Google Drive · Ad Mixer) — Spec   ·   Size: M (two PRs)

Status: spec only, nothing built. Base: `feat/platform-v2` @ `7ba5bfd` (what prod runs).
Plan: [`../plans/2026-10-04-handin-link-ingest.md`](../plans/2026-10-04-handin-link-ingest.md).
Decisions by Alan, 2026-10-04 (one round): folder link means all its videos. Drive access goes through the aditor-agent service account. Cap is 2 GB per file. Fetches run on their own small worker.

## Why

On 2026-10-04 Sandra (Veda Naturals) spent 30 min failing to hand in 4 × ~120 MB on `/handin`.
Per-part retry (#53) fixed the failures, but at her ~1.6 Mbit/s uplink one 2-min video still takes ~10 min.
Her file usually already sits in Google Drive, or Ad Mixer rendered it. If the server pulls it from there (server → bucket), her uplink no longer matters.

## What

On `/handin` the editor can paste a link where they would otherwise drop a file:

- `drive.google.com/file/d/<id>/…`, `…/open?id=<id>`, `…/uc?id=<id>`, `docs.google.com/…` with an id, `drive.usercontent.google.com/download?id=<id>` gives **one** video.
- `drive.google.com/drive/folders/<id>` gives **every video at the folder's top level** (max 20, non-videos skipped and counted).
- `https://mix.aditor.ai/api/downloads/<token>` (an Ad Mixer download grant) gives **one** video.

On paste the link is **resolved**: name, size and count appear as chips, like picked files. On submit the server creates the asset and version exactly like `/upload/initiate`, then a Celery task streams the bytes into `raw/{project}/{asset}/{version}/original{ext}` with S3 multipart. After that the version goes `uploading → processing` and the **existing** `process_asset` runs. Everything after that point (share link, Auto Review, Trello delivery) does not change.

## Boundaries

- **Must:** Fetch only through allowlisted hosts. Drive goes through the Drive v3 API, never a user-supplied URL. Mixer goes to `INGEST_MIXER_HOSTS`, and redirects are followed only to `*.r2.cloudflarestorage.com`. That closes the SSRF door.
- **Must:** Keep the same permission checks as `/upload/initiate`: project editor role, folder belongs to project and is not deleted, and `upload_guard_error` against the storage cap.
- **Must:** Write the durable state to Postgres first. The UI only ever reads what the DB says.
- **Must not:** Add new Python or JS dependencies. Use `httpx` (already pinned) for HTTP and `python-jose[cryptography]` (already pinned) to sign the service-account JWT. No `google-api-python-client`.
- **Must not:** Touch the n8n views, Codex's branch `codex/handin-components`, or the transcode pipeline.
- **Out of scope (YAGNI):** Frame.io, Dropbox, WeTransfer and arbitrary URLs. Sub-folders. Drive shortcuts. Unzipping an Ad Mixer ZIP. Polling an unfinished render until it is done. Link-ingest on the parts hand-in (#46) or on "new version" uploads elsewhere in the app. Resumable fetch after a crash, since the restart is from byte 0. A per-file picker in a folder.

## Starting point (files touched)

| Area | Today | Pattern to follow |
|---|---|---|
| Asset/version creation | `apps/api/routers/upload.py:initiate_upload` | Copy its validation + Asset/AssetVersion/MediaFile creation into a shared helper rather than duplicating it |
| Multipart to bucket | `apps/api/services/s3_service.py` `create_multipart_upload` / `complete_multipart_upload` / `abort_multipart_upload` | Server-side `upload_part` via `get_s3_client()` |
| Processing kickoff | `upload.py:_trigger_processing` → `send_task_safe(process_asset, …)` | Same call at the end of the ingest task |
| Queues | `apps/api/tasks/celery_app.py` (`transcoding`, `default`); prod worker `-Q transcoding,default -c 2` (`docker-compose.prod.yml:181`) | New queue `ingest`, new compose service `ingest-worker` (`-Q ingest -c 2`, `cpus: "1.0"`, `mem_limit: 1g`) |
| Stuck uploads | `cleanup_tasks._reap_stale_uploads` reaps `uploading`/`failed` older than 4 h and aborts stale multiparts | Reused as is: a crashed ingest is reclaimed by the same reaper |
| Web upload state | `apps/web/stores/upload-store.ts` (`UploadFile`, `startUpload`, `refreshProcessingItems`) | New action `startLinkIngest` that creates normal `UploadFile` entries, so `waitForUpload` in the page and #46's `stageFor` work unchanged |
| Hand-in page | `apps/web/app/(dashboard)/handin/page.tsx` (`files`, `UploadZone`, `handleSubmit` step 3) | Keep the diff small; see "Composition with #46" |
| Drive SA auth prior art | `Asset Agent (Python)/tools/resolve_drive.py:_make_drive_service`: SA JSON, scope `…/auth/drive`, domain-wide delegation `subject=DRIVE_DELEGATED_USER` | Same SA, scope and subject. Token via JWT-bearer grant signed with `jose.jwt.encode(…, algorithm="RS256")` |
| Drive gotchas | feedback-agent `src/resolve.ts:14-32` (URL regexes), `docs/superpowers/specs/2026-07-01-link-resolution.md:47` (`confirm=t` fails on the >100 MB virus-scan page) | Reuse the regexes. The API `alt=media` path has no interstitial, which is why we use it |

### Data contract (v1)

- **Migration** (one Alembic revision, single head): add nullable columns on `media_files`: `source_url TEXT`, `ingest_bytes_done BIGINT`, `ingest_error VARCHAR(40)`. A NULL `source_url` means a browser upload. No new enum value: an ingest in flight is `processing_status = uploading`.
- `POST /upload/link/resolve` `{url}` → `200 {kind: "drive_file"|"drive_folder"|"mixer", files: [{name, size_bytes, mime_type}], skipped: int}` | `4xx {detail: {code, message}}`. Read-only, creates nothing.
- `POST /upload/link` `{url, project_id, folder_id}` → `200 {items: [{asset_id, version_id, name, size_bytes}]}`. Re-resolves server-side (the client's resolve result is never trusted), creates one asset+version per file and enqueues `ingest_from_link(version_id)` for each on queue `ingest`.
- `GET /upload/link/{version_id}` → `{status, bytes_done, bytes_total, error_code, error_message}`. Only the creator can read it.
- Error `code`s are the keys of the table below. They are stable, and the UI switches on them.

### Error taxonomy (on {error} → {action})

| code | When | Action |
|---|---|---|
| `link_unsupported` | Host/shape not in the list above | Resolve 400. Nothing created. "Only Google Drive or Ad Mixer links." |
| `drive_unconfigured` | `GOOGLE_DRIVE_SA_JSON` unset | Resolve 503. "Drive links aren't set up on this server." |
| `drive_private` | Drive API 404 / 403 `insufficientFilePermissions` | Resolve 422. "Can't open this file. Set it to *Anyone with the link* or share it with {GOOGLE_DRIVE_DELEGATED_USER}." |
| `drive_quota` | 403 `downloadQuotaExceeded` (file downloaded too often, Google locks it ~24 h) | Task fails, no retry. "Google is blocking downloads of this file right now. Upload it directly." |
| `drive_flagged` | 403 `cannotDownloadAbusiveFile` | Task fails, no retry. "Google flagged this file. Upload it directly." |
| *(virus-scan page)* | n/a | Never happens: the API `alt=media` has no interstitial. If a Drive response is ever `text/html`, treat it as `drive_private`. |
| `folder_empty` | Folder has 0 top-level videos | Resolve 422. "No videos in this folder (sub-folders aren't searched)." |
| `folder_too_many` | > 20 top-level videos | Resolve 422. "More than 20 videos: split the folder or paste file links." |
| `not_video` | Drive mime or Mixer `content-type` not `video/*` | Resolve 422. "That's not a video." |
| `mixer_archive` | Mixer link serves `application/zip` (the "download all" / mail link) | Resolve 422. "That's the ZIP of all versions. Copy the link of one video." |
| `too_large` | `size` / `Content-Length` > `INGEST_MAX_BYTES` (2 GB), or streamed bytes pass the cap | Resolve 422. Mid-stream: abort multipart, task fails. "Bigger than 2 GB." |
| `link_expired` | Mixer 410 `download_expired`, 404 `output_expired`, or the R2 presign answers 403 | Resolve 422. Same in the task (no retry). "Link expired. Copy it again in Ad Mixer." |
| `render_not_finished` | Mixer 409 `output_not_ready` | Resolve 422. "Ad Mixer is still rendering. Paste the link when it's done." No server-side waiting. |
| `fetch_failed` | Network error, 5xx, 429, 403 `rateLimitExceeded`/`userRateLimitExceeded`, S3 part failure | Celery retry ×3 (30 s, 2 min, 5 min), each restarting from byte 0 on a fresh multipart upload. Then the task fails. "Couldn't fetch the file. Try again or upload it directly." |
| `storage_full` | `upload_guard_error` | Same 400 as `/upload/initiate`. |
| *(worker killed)* | Container restart mid-fetch | `acks_late=True` causes redelivery. The task restarts only if the version is still `uploading`. Otherwise the 4 h reaper reclaims it. |

On a task failure: `processing_status = failed`, `ingest_error = code`, abort the multipart. The reaper then reclaims storage as it does for failed browser uploads.

### Composition with #46 (Codex, `codex/handin-components`, draft)

- #46 wraps today's page body into `CompleteHandinPage` and adds `PartsHandin` behind `NEXT_PUBLIC_HANDIN_COMPONENTS_ENABLED`. Link-ingest goes **only** into the complete hand-in form. The page diff stays at roughly 15 lines: one `<LinkInput>` under `<UploadZone>`, one `links` state, and one extra map in `handleSubmit` step 3. Whoever merges second resolves that small conflict by hand.
- #46's `stageFor(assetId)` reads `useUploadStore.files`. Ingest entries live there with `status: "uploading"`, so the stage strip shows "Upload" during the server fetch with no #46 change.
- #46 adds `require_unmanaged_destination(db, folder_id)` to `/upload/initiate`. If `apps/api/services/iteration_requests.py` exists at build time, the shared create helper calls it too. If not, skip it, and #46's author adds it when rebasing. Note this in the PR body.
- Do not commit to `codex/handin-components`. Both PRs target `feat/platform-v2`.

### Ad Mixer link contract (coordinate with the parallel Ad Mixer share-link spec)

There is no Ad Mixer share-link spec on any branch yet; this was checked. The only server-fetchable, session-free URL today is `GET https://mix.aditor.ai/api/downloads/<token>`, which 302s to an R2 presign. Per-video grants live 900 s. The mail grant on `feat/2026-10-04-mail-when-done` lives 30 days but is the **ZIP**.
**v1 accepts `/api/downloads/<token>` for one video.** Proposal to the Ad Mixer session, so we don't invent two formats: the share page `https://mix.aditor.ai/s/<code>` also answers `Accept: application/json` with `{state: "complete"|"running"|…, files: [{name, url: "/api/downloads/<token>", content_type, size_bytes}]}`, with grant TTL = render retention. FreeFrame then treats it like a Drive folder: one resolver branch, one task unchanged. That branch is **not** built until that JSON exists. See Stop & Escalation.

## Tasks

See the plan for steps. Each task is one reviewable commit; PR A = T1–T3 (API + worker), PR B = T4 (web), T5 rides with B.

- **T1** — Pure link parsing + error codes · `apps/api/services/link_ingest.py`, `tests/test_link_ingest_parse.py` · **Verified:** `python -m pytest apps/api/tests/test_link_ingest_parse.py -v`
- **T2** — Drive + Mixer fetchers (SA token, metadata, folder list, streaming body) · `apps/api/services/link_sources.py`, `tests/test_link_sources.py` (with `httpx.MockTransport`) · **Verified:** that test file green
- **T3** — Migration, endpoints, Celery `ingest_from_link`, queue + compose service, config · `models/asset.py`, `alembic/versions/*`, `routers/upload.py`, `tasks/ingest_tasks.py`, `tasks/celery_app.py`, `config.py`, `.env.example`, `docker-compose.prod.yml`, `tests/test_link_ingest_api.py` · **Verified:** full `python -m pytest apps/api/tests/ -v` green; `alembic heads` prints one head
- **T4** — Web: `startLinkIngest` + polling in the store, `<LinkInput>`, page wiring · `stores/upload-store.ts`, `components/handin/link-input.tsx`, `handin/page.tsx`, one vitest · **Verified:** `pnpm --filter web exec tsc --noEmit && pnpm --filter web lint && pnpm --filter web test && pnpm --filter web build`; screenshot of resolved chips + one error state in light and dark
- **T5** — CHANGELOG `[Unreleased] → Added`, `docs/deployment.md` (secret + ingest worker) · **Verified:** files present in diff

## Done (machine-checkable)

- `python -m pytest apps/api/tests/ -v` green, with ≥ 3 new test files. That covers parse, sources and API, including every error `code` in the table at least once.
- `cd apps/api && alembic heads` prints exactly one head.
- `pnpm --filter web exec tsc --noEmit`, `lint`, `test` and `build` all pass.
- `docker compose -f docker-compose.prod.yml config --services` lists `ingest-worker`.
- `grep -rn "googleapiclient\|google-api-python-client" apps/api` finds nothing (no new dependency).
- Screenshots in the PR B body: resolved folder (chips), `drive_private` error, in light and dark.

## Stop & Escalation

- `GOOGLE_DRIVE_SA_JSON` / `GOOGLE_DRIVE_DELEGATED_USER` are not available for a live check. Build and test with mocks, and **do not** fetch real Drive files. The live smoke test is Alan's step after deploy.
- The Ad Mixer `/api/downloads/<token>` turns out to be **single-use**, so the resolve GET burns it. Stop. Resolve must then skip the probe for Mixer, and that is a product call.
- The Ad Mixer share-page JSON lands with a different shape than proposed. Do not adapt silently; note it in the PR as "Offene Entscheidung für Alan".
- #46 has merged and `handin/page.tsx` structure differs from what's described here. Rebase, keep link-ingest out of `PartsHandin`, and if that is not clean, stop.
- The same test fails twice after a fix attempt, or a CI floor guard trips. Stop and report.
- Deploying, writing prod `.env`, or touching the Hetzner box is never done by the night run.

## Doctrine-Gate  (see aditor-ops/docs/superpowers/DEVELOPMENT-DOCTRINE.md)

- [x] **M1** Spec-first: the purpose (editor uplink no longer matters) and YAGNI list are explicit. Altitude: contract and error codes pinned, implementation left to the plan.
- [x] **M2** Start simple: a plain Celery task plus httpx. No new deps, no new status enum, no resumable fetch, no render polling. The extra worker container has a stated reason: it keeps the 2 transcode slots free.
- [x] **M3** Loop-first: `Done` is commands only. `Stop & Escalation` names the missing secrets, the Mixer single-use question, the #46 drift and repeat failures.
- [x] **1 State:** Postgres `asset_versions.processing_status` + `media_files.ingest_*` are the single source. The DB row is written before the task is enqueued; the UI polls the DB.
- [x] **2 Separation of concerns:** URL parsing and error classification are pure (`link_ingest.py`). HTTP to Drive and Mixer lives in `link_sources.py`, orchestration in the task, HTTP surface in the router.
- [x] **3 Idempotency:** The task no-ops unless the version is `uploading`. A retry restarts on the same S3 key with a fresh multipart, and the old one is reaped. Dedup key for a resubmit: none on purpose, because re-handing-in the same card is a new version by design. Double-click is guarded by the disabled submit button (as today).
- [x] **4 Coupling:** The contracts are the three endpoints, the error-code list, and the Mixer URL shape plus proposed JSON. The web side uses only `UploadFile` fields that already exist.
- [x] **5 Context window:** Two PRs, five commits. Each task names its files.
- [x] **6 Error taxonomy:** The table above maps each code to retry, fail or 4xx.
- [x] **7 Defensive design:** Expected failure modes are classified; no catch-all. A failed fetch fails one version; the other videos of the hand-in continue. Partial retry = only that file.
- [x] **F1 Right lever:** No model or prompt involved. The lever is "fetch where the file already is".
- [x] **Tests:** Pure parse tests and `httpx.MockTransport` source tests. API tests use the existing `mock_db` / `client` fixtures (`tests/conftest.py`), with no real Drive, R2 or Postgres.
