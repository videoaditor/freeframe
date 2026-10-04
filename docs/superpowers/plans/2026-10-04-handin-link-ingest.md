# Hand in by link — Implementation plan

Spec: [`../specs/2026-10-04-handin-link-ingest-design.md`](../specs/2026-10-04-handin-link-ingest-design.md). The spec wins wherever the two disagree.
Base branch: `feat/platform-v2`. Two PRs, both `--repo videoaditor/freeframe --base feat/platform-v2`:
**PR A** `feat/link-ingest-api` (T1–T3) and then **PR B** `feat/link-ingest-web` (T4–T5, stacked on A).
TDD: write the failing test first in each task, then the code.

## Context the engineer needs

- Tests have **no real DB** (`apps/api/tests/conftest.py` gives a `MagicMock` session). Patch the source/S3 layer and drive the routes through the `client` + `mock_db` fixtures. Pattern: `tests/test_share_session.py`.
- CI floors: ≥ 5 test files, ≥ 40 passing tests, ≥ 30 routes, critical files present. We only add.
- Soft delete: every query filters `deleted_at.is_(None)`.
- Drive SA: a JSON key with domain-wide delegation, scope `https://www.googleapis.com/auth/drive` (the only scope authorized in the Workspace admin console; `drive.readonly` would 403), and `sub = GOOGLE_DRIVE_DELEGATED_USER`. Token exchange: POST `https://oauth2.googleapis.com/token`, `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`, `assertion=jose.jwt.encode({iss, sub, scope, aud, iat, exp}, private_key, algorithm="RS256")`. Cache the token in-process until `exp - 60s`.
- Drive REST (always pass `supportsAllDrives=true`):
  - Metadata: `GET https://www.googleapis.com/drive/v3/files/{id}?fields=id,name,mimeType,size`
  - Folder: `GET …/files?q='{id}' in parents and trashed=false&fields=files(id,name,mimeType,size)&pageSize=100`
  - Bytes: `GET …/files/{id}?alt=media`
  - A `resourcekey=` in the pasted URL goes along as header `X-Goog-Drive-Resource-Keys: {id}/{key}`.
  - Error reason is in `error.errors[0].reason`.
- Ad Mixer: `GET https://mix.aditor.ai/api/downloads/<token>` gives a 302 to `https://<acct>.r2.cloudflarestorage.com/…` (presign, 300 s). Error bodies: 410 `download_expired`, 404 `output_expired`, 409 `output_not_ready`. Filename comes from `Content-Disposition`, with fallback `admixer-<token[:8]>.mp4`.

## T1 — Pure parsing + codes (PR A, commit 1)

Files: `apps/api/services/link_ingest.py`, `apps/api/tests/test_link_ingest_parse.py`

1. `LinkRef = NamedTuple(kind: Literal["drive_id","drive_folder","mixer"], id: str, resource_key: str | None, url: str)`.
2. `parse_link(url, mixer_hosts) -> LinkRef`. It raises `IngestError("link_unsupported")`.
   - Google hosts: `drive.google.com`, `docs.google.com`, `drive.usercontent.google.com`. Check `/folders/<id>` first, then `/file/d/<id>`, then `?id=`.
   - `https` only.
   - Mixer is `host in mixer_hosts and path matches ^/api/downloads/[A-Za-z0-9_-]{20,}$`. Anything else is unsupported.
   - Regexes are ported from feedback-agent `src/resolve.ts:14-32`.
3. `class IngestError(Exception)` with `.code`, and `MESSAGES: dict[code, str]`, which is exactly the spec table's English messages. The `{email}` placeholder is filled by the caller.
4. `classify_drive_error(status:int, reason:str|None) -> code`, `classify_mixer_error(status:int, body_error:str|None) -> code`, and `is_retryable(code) -> bool` (only `fetch_failed`).
5. Tests:
   - Parse each URL shape from the spec plus its negatives (`http://`, `evil.com/file/d/x`, `mix.aditor.ai/other`, `drive.google.com.evil.com`).
   - One assertion per row of the error table for both classifiers.

## T2 — Sources (PR A, commit 2)

Files: `apps/api/services/link_sources.py`, `apps/api/tests/test_link_sources.py`

1. `ResolvedFile = NamedTuple(name, size_bytes: int | None, mime_type, fetch_ref)`.
2. `resolve(ref, client: httpx.Client) -> tuple[list[ResolvedFile], skipped:int]`:
   - **Drive file**: metadata. Not `video/*` → `not_video`. `text/html` anywhere → `drive_private`.
   - **Drive folder**: list. Keep `video/*`, and `skipped` is the rest. 0 → `folder_empty`, > 20 → `folder_too_many`.
   - **Mixer**: `GET` with `Range: bytes=0-0`. Follow redirects only if the target host ends with `.r2.cloudflarestorage.com` (custom `event_hooks` or a manual loop, max 3 hops). Size comes from `Content-Range` total. `application/zip` → `mixer_archive`, otherwise non-video → `not_video`.
   - Any size > `settings.ingest_max_bytes` → `too_large`.
3. `open_stream(file, client) -> ContextManager[Iterator[bytes]]` streams `alt=media` or the Mixer URL. It counts bytes and raises `too_large` past the cap.
4. `drive_token()` is the SA JWT exchange described above. Missing settings → `drive_unconfigured`.
5. Tests use `httpx.MockTransport` and a throwaway RSA key generated in the test via `cryptography`, which comes with python-jose. Cover:
   - happy path for each kind
   - each error code reachable from a source
   - redirect to a non-R2 host refused
   - the mid-stream cap

## T3 — Model, endpoints, task, worker (PR A, commit 3)

Files: `models/asset.py`, `alembic/versions/<rev>_media_file_link_ingest.py`, `routers/upload.py`, `schemas/upload.py`, `tasks/ingest_tasks.py`, `tasks/celery_app.py`, `config.py`, `.env.example`, `docker-compose.prod.yml`, `docker-compose.aditor.yml`, `tests/test_link_ingest_api.py`

1. **Model + migration.** Add `MediaFile.source_url` (Text), `ingest_bytes_done` (BigInteger) and `ingest_error` (String(40)), all nullable. Write it with `alembic revision --autogenerate`, then **hand-review** it:
   - only those 3 `add_column`s
   - `down_revision` = the current single head
   - n8n views untouched
2. **Config** in `config.py` + `.env.example`, all with safe defaults:
   - `ingest_max_bytes: int = 2 * 1024**3`
   - `ingest_mixer_hosts: str = "mix.aditor.ai,mixer.aditor.ai"`
   - `google_drive_sa_json: str = ""`: either a path to the key file or the raw JSON (starts with `{`)
   - `google_drive_delegated_user: str = ""`
3. **Shared create helper.** Extract from `initiate_upload` a `_create_pending_version(db, user, project_id, folder_id, name, mime, size, filename) -> (asset, version, media_file, s3_key)`.
   - `initiate_upload` calls it, so its behavior is unchanged and existing tests still pass.
   - If `services/iteration_requests.py` exists, call `require_unmanaged_destination` inside it (spec, "Composition with #46").
4. **Routes** (same router, prefix `/upload`):
   - `POST /link/resolve`
   - `POST /link`: re-resolve; check the guard per file **and** for the sum; create one version per file with `source_url=url` and status `uploading`; commit; **then** `send_task_safe(ingest_from_link, version_id)`.
   - `GET /link/{version_id}`: creator only, else 403.
   - Map `IngestError` to `HTTPException(status, detail={"code","message"})`: 400 for `link_unsupported`, 503 for `drive_unconfigured`, 422 for the rest.
5. **Task** `ingest_from_link(version_id)`: `bind=True, acks_late=True, max_retries=3, soft_time_limit=1800`, routed to queue `ingest`.
   1. Load the version. If the status is not `uploading`, return.
   2. Re-parse `source_url`, `create_multipart_upload`, then stream in 16 MiB parts (`upload_part`) and update `ingest_bytes_done` after each part.
   3. `complete_multipart_upload`, then `processing_status = processing`, `file_size_bytes = bytes_done`, commit, `send_task_safe(process_asset, …)`.
   4. On `IngestError`: abort the multipart. If the code is retryable and retries remain, `self.retry(countdown=[30,120,300][n])`. Otherwise set `failed` + `ingest_error = code`.
   5. Anything else unexpected: abort the multipart and re-raise. Let it crash, so it is logged and the reaper cleans up.
6. **Queue + worker.** `celery_app.py` gets `Queue("ingest")`, the route `"apps.api.tasks.ingest_tasks.*": {"queue": "ingest"}`, and `ingest_tasks` in `include`. `docker-compose.prod.yml` gets an `ingest-worker` service copied from `worker`, with command `celery … worker -Q ingest -c ${INGEST_CONCURRENCY:-2}`, `cpus: "1.0"`, `mem_limit: 1g`, no FFmpeg env. The `.aditor` override needs nothing extra.
7. **Tests** (`mock_db` + patched `link_sources` + patched s3 functions):
   - resolve → 200 / each 4xx code
   - create → asset + version + MediaFile with `source_url`, and the task enqueued after commit
   - wrong role → 403
   - the storage guard
   - status route ownership
   - task: happy path flips to `processing` and calls `process_asset`; `drive_quota` → `failed` without retry; `fetch_failed` → retry; a non-`uploading` version is a no-op; the cap mid-stream aborts the multipart
8. Run the full `python -m pytest apps/api/tests/ -v`, then `cd apps/api && alembic heads`. Open **PR A**.

## T4 — Web (PR B, commit 4)

Files: `apps/web/stores/upload-store.ts`, `apps/web/components/handin/link-input.tsx`, `apps/web/app/(dashboard)/handin/page.tsx`, `apps/web/lib/__tests__/link-ingest.test.ts`

Before touching UI, load `ux-laws` → `apple-hig` → `emil-design-eng` (global CLAUDE.md). Reuse existing `Input` and chip styles; no new visual language.

1. **Store.** `startLinkIngest(url, projectId, projectName, folderId): Promise<string[]>`:
   - `POST /upload/link`, then push one `UploadFile` per item: `status:'uploading'`, `fileSize=size_bytes`, `assetId`, `versionId`, `fileType:'video/mp4'`.
   - Poll `GET /upload/link/{versionId}` every 3 s while `uploading`, setting `progress = bytes_done/bytes_total*100`.
   - On `processing` set `status:'processing'`; the existing SSE/poll takes over. On `failed` set `status:'failed'` with `error = error_message`.
2. **`<LinkInput onResolved onCleared>`.** One text input under `<UploadZone>`, labelled "…or paste a Google Drive / Ad Mixer link".
   - Resolve on paste/blur via `POST /upload/link/resolve`.
   - Show the resolved files as chips, the same as picked files (name + size, and "N other files skipped" if > 0).
   - Show `detail.message` inline under the input on error.
   - Submit is enabled when `files.length || link resolved`.
3. **Page.** Add `const [link, setLink] = useState<string|null>(null)`. In `handleSubmit` step 3, append `...(link ? (await startLinkIngest(link, projectId, projectName, folder.id)).map(id => waitForUpload(id).then(…)) : [])` to the `Promise.all`. The asset name comes from the store entry. `files[0].name` fallbacks must handle "no files, only link" by using the first resolved name.
4. **Test.** Vitest for the store mapping (server status → `UploadStatus`, progress math) with `api` mocked.
5. Verify:
   - `pnpm --filter web exec tsc --noEmit && pnpm --filter web lint && pnpm --filter web test && pnpm --filter web build`
   - Dev stack + preview: paste a link with the API patched/mocked, then screenshot the chips and the `drive_private` error in light and dark.

## T5 — Docs (PR B, commit 5)

- `CHANGELOG.md` `[Unreleased] → Added`: "Hand in by Google Drive or Ad Mixer link; the server fetches the file."
- `docs/deployment.md`:
  - the two `GOOGLE_DRIVE_*` env vars (key file mounted read-only, never committed)
  - the `ingest-worker` service
  - `INGEST_MAX_BYTES`
- Open **PR B** with screenshots, and note the #46 merge-order item under "Offene Entscheidung für Alan" only if it actually conflicts.

## After merge (Alan / ops, not the night run)

1. Put the aditor-agent SA key on the Hetzner box and set `GOOGLE_DRIVE_SA_JSON` + `GOOGLE_DRIVE_DELEGATED_USER` in `.env.prod`.
2. Deploy, and check that `ingest-worker` is up.
3. Live smoke test: hand in one Drive file link, one Drive folder, and one fresh Ad Mixer per-video link. All three should reach "processing" in under a minute for ~120 MB.
