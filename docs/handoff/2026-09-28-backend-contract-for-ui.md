# Platform v2: backend contract for the UI (handoff from Claude to Codex)

Written 2026-09-28. Alan's decision: **Claude owns the backend** (FreeFrame API + Auto Review
Worker); **Codex owns `apps/web`**. Claude does not edit `apps/web` any more.

Spec: `docs/superpowers/specs/2026-09-28-review-platform-v2-design.md`. Everything below is
committed on `feat/platform-v2` (API) and in `videoaditor/feedback-agent` `feat/jev-engine-platform-v2`
(Worker), with tests.

## 1. Uncommitted UI work Claude left in this tree

These are in the working tree, NOT committed, mixed with Codex's edits. Keep, change or drop
them - they are yours now. `apps/web` typechecks with all of them in place.

| What | Where |
|---|---|
| Higher surface contrast (cards #18181b, 12% hairlines, text-secondary #b3b3b8, tertiary #808086, glass 78%) | `app/globals.css` `:root` tokens |
| Route transition: every dashboard screen rises + un-blurs (300ms, Reduce Motion = fade) | `app/(dashboard)/template.tsx` (new), `.route-in` in `globals.css` |
| Real Aditor icons: favicon, app icon, apple-touch icon, sidebar default logo, 256px logo | `app/favicon.ico`, `app/icon.png`, `app/apple-icon.png`, `public/logo-icon*.png`, `public/aditor-logo.png` (from `Aditor Design System/uploads/aditor-logo-1.png`) |
| Product name "Aditor Review" instead of "FreeFrame" in titles/branding defaults | `stores/branding-store.ts`, `hooks/use-page-title.ts`, `components/share/folder-share-viewer.tsx`, `app/(auth)/layout.tsx`, `settings/branding/page.tsx` |
| Glossy coral folder illustration | `components/v2/folder-art.tsx` |
| Real first-frame thumbnail in the upload card | `components/v2/upload-card.tsx` (`Thumb`, new `file` prop; passed from `app/page.tsx` and `app/r/[token]/page.tsx`) |
| "Here's your link" card: whole card taps to copy, wash + icon morph, Open / Share | `components/v2/link-card.tsx` (new), used in `request-sheet.tsx`; `.link-fill` / `.icon-swap` in `globals.css` |
| White-label request page: brand logo (or brand name wordmark) in the header, no Aditor mark, no "X asks for" eyebrow | `app/r/[token]/page.tsx` `Shell` |
| Honest timing copy: "usually about a minute per video, one after another" | upload card, request page |
| Logo helpers `toWebp`, `uploadBrandLogo(projectId, file)`, `getBrandLogo(projectId)`; `RequestView.logo_url` | `lib/platform.ts` |

Not built yet (UI): the logo upload control for owners, and the editor ranking view.

## 2. FreeFrame API (this repo, `apps/api/routers/requests.py`)

All owner routes need the normal bearer token. Brand = `project_brand()`: a customer's project is
`cust-<id>` (never its typed name), a staff workspace its name slug.

| Route | Returns |
|---|---|
| `POST /requests` `{project_id, title, brief_text?, brief_url?, brief_pdf_base64?, expires_in_days?}` | a `FileRequest` (see `lib/platform.ts`), incl. `url` = `/r/<token>` |
| `GET /requests` | `FileRequest[]` with `status` `reviewing\|held\|clear`, `open_must_fixes`, `assets`, `last_uploader_name`, `state` `live\|revoked\|expired` |
| `DELETE /requests/{id}` | 204, closes the link (410 afterwards) |
| `GET /insights/time-saved?days=7..90` | `{days, videos, watchSec, typeSec, totalSec, perDay[{day,sec}], perBrand[{brand,sec,videos}], assumptions{wpm,watches}}` |
| **`GET /insights/editors`** | `{editors: [{email, name, videos, rated, first_try_rate (0..1 or null), avg_versions, open_must_fixes}], reviewed}` - **already sorted, most accurate first**. `first_try_rate` = share of their videos with no must-fix on v1; `null` = not reviewed yet (ranked last, never show as 0%). `rated` < `videos` means some are still unknown - show small samples as small. A V2 of the same video is not a second video. |
| `GET /insights/rules?project_id=` | `{brand, rules[], suggestions[]}` |
| `POST /insights/rules/import` `{project_id, text? \| url? \| pdf_base64?}` | `{drafted, found}` |
| `POST /insights/rules/suggestion` `{project_id, suggestion_id, action: accept\|dismiss}` | `{ok}` |

**Brand logo (white-label):** already in FreeFrame, no new route.
1. `POST /projects/{id}/branding/logo-upload` gives `{upload_url, key}` (a presigned PUT, **Content-Type `image/webp`**).
2. PUT the WebP bytes (`toWebp()` in `lib/platform.ts` converts any image and keeps transparency).
3. `PUT /projects/{id}/branding {logo_s3_key: key}` gives `{logo_url}`.
4. `GET /projects/{id}/branding` gives `{logo_url}`.

The public request page gets it as `logo_url` from `GET /r/{token}`.

### Public (the editor, no account; the token is the permission)

| Route | Notes |
|---|---|
| `GET /r/{token}` | `{title, brand, logo_url, brief_excerpt, review_share_token, assets[{id,name}], expires_at}`; 404 unknown, 410 closed/expired/deleted |
| `POST /r/{token}/upload/initiate` `{name, email, original_filename, mime_type, file_size_bytes}` | same file name (without extension) = next version of that asset |
| `POST /r/{token}/upload/presign-part` `{s3_key, upload_id, part_number}` | 10 MB parts |
| `POST /r/{token}/upload/complete` `{s3_key, upload_id, parts[{PartNumber,ETag}]}` | 413 if the real object is bigger than announced; idempotent |
| `POST /r/{token}/upload/abort` | |
| `GET /r/{token}/review` | `{assets[{asset_id, name, version, processing, comments[{id, t, body, must_fix}]}], gate{status, open_must_fixes}}` - comments from the newest READY version, withdrawn notes left out |
| `POST /r/{token}/object` `{asset_id, comment_id, body, text, name}` | `{withdrawn, why}` - the "Not right?" valve |

## 3. Things the UI must not assume

- Timing: the landing's anonymous try is reviewed directly (about a minute for a short ad).
  Request uploads queue: **one video per minute**, so 10 videos take ten minutes or more. Do not
  promise "a minute" for a batch.
- The share link is never gated; only what the OWNER sees waits for must-fixes.
- Every review failure is fail-open: the owner sees Ready, never an endless "reviewing".
