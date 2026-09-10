# Delivery-first share view

Alan, CX call 2026-09-10: every client delivery is about to route through FreeFrame's
share view. The page currently reads as Frame.io — a review tool — and that shapes
behaviour before a client watches a single second of the video:

> "wenn wir es jetzt so lassen, wie es ist und wir es abgeben, dann wird die Revision
> Rate hochgehen, weil die Kunden denken, ah, es ist Frameio, ich muss jetzt was
> kommentieren."

He wants the page to feel like a finished delivery (Google Drive: "let me download and
test this") rather than an invitation to critique (Frame.io: "I am here to pick this
apart"). Five concrete asks came out of that call. This doc is the honest breakdown of
which are safe, config-gated changes and which are real redesigns, file by file, plus
one slice actually implemented.

Relevant files:
- `apps/web/app/share/[token]/page.tsx` — the single-asset share view: `ShareTopBar`
  (download button, panel toggle), `ShareViewer` (owns `sidebarOpen` state),
  `ShareRightPanel` / `GuestCommentList` (the comment column).
- `apps/web/components/share/folder-share-viewer.tsx` — the multi-asset/folder share
  view, a separate layout with its own comment affordances.
- `apps/web/components/review/guest-comment-input.tsx` — where a guest identifies
  themselves and posts a comment.
- `apps/web/hooks/use-drawing.ts` — existing Fabric.js annotation tool: pen, rectangle,
  arrow, line. No point/pin tool.
- `apps/web/types/index.ts` (`Comment` interface) and `apps/api/routers/comments.py` —
  comment schema. Has `timecode_start` / `timecode_end` (time on the timeline). No
  `position_x` / `position_y` or any spatial field — a comment cannot be anchored to a
  point in the frame today.
- `apps/web/tailwind.config.ts` + `apps/web/app/globals.css` — accent colour tokens
  (`--accent`, `--accent-hover`, `--accent-muted`). These are already blue
  (`#5b8def` dark / `#4a7de8` light) at the token level. The orange Alan is reacting to
  is NOT the global accent — it's hardcoded per-component: `bg-orange-500` avatar
  colour in `comment-panel.tsx`, `#FF9500` in the colour picker in
  `comment-input.tsx`, and a `bg-orange-500` swatch in `folder-share-viewer.tsx`'s
  avatar-colour list. Confirmed by reading `globals.css` and grepping for `orange`
  across `apps/web`.
- `docker-compose.aditor.yml` / `apps/web/Dockerfile.prod` — where instance-level UI
  behaviour is switched by `NEXT_PUBLIC_*` build args, per Aditor's own convention
  (see the `PASSWORD_LOGIN_ENABLED` block already in that file, and the
  `INSTANCE_WIDE_PROJECT_ACCESS` / `AUTOMATION_SHARE_WEBHOOK_URL` block on `api`).

## The five asks, honestly sorted

### 1. Prominent "Download all" — SMALL, but only for a single asset today
`ShareTopBar` already has a per-asset download button (`handleDownload`, streams
through `/share/{token}/stream/{assetId}?download=true`). It is not especially
prominent (purple pill, same visual weight as the panel toggle) and there is no
"download all" for a multi-asset share — `folder-share-viewer.tsx` would need a
zip-all endpoint that does not exist in `apps/api/routers/share.py` today. Making the
existing single-asset button visually prominent is a small CSS/layout change. Adding
real "download all" for folders is a real feature (new API endpoint to zip and stream
N assets, progress UI, storage/bandwidth consideration) — do not build this without
sizing the API work first.

### 2. Share-with-someone-else next to it — SMALL UI, uses an existing feature
A share-link-creation flow already exists for internal users
(`components/projects/share-create-dialog.tsx`), but nothing lets a *guest viewing a
share link* mint or forward a link themselves — the guest-facing surface has no such
action at all. The safe version is a "Copy link" / "Forward" button next to Download
that just copies `window.location.href` (or a `mailto:` prefill) — no new backend
permission. Actually letting a guest create a *new, scoped* share link is a real
feature (who can mint links, does it inherit the parent's permission/expiry, is it
logged) and needs a product decision on scope before writing API code.

### 3. Comment column not prominent until first comment — SMALL, config-gated
This is the one implemented in this branch. `ShareViewer` already tracks
`sidebarOpen` as component state, defaulting to "open on desktop, closed on mobile"
via `matchMedia`. The change: behind `NEXT_PUBLIC_SHARE_COMMENTS_COLLAPSED` (default
`false`, i.e. unchanged), the panel now defaults to closed and a one-shot fetch to
the existing `/share/{token}/comments` endpoint reveals it only if the asset already
has at least one comment. No schema change, no new endpoint, purely additive and
off unless an instance opts in.

How to know it worked: with the flag off (default), behaviour is byte-for-byte the
same as before — `git diff` shows the change is gated behind a `false`-defaulting
constant, and `matchMedia`-driven default remains the only path when unset. With the
flag on and zero comments, the panel starts closed regardless of viewport width; once
`/share/{token}/comments` returns a non-empty array the panel opens itself. Manual
verification: `NEXT_PUBLIC_SHARE_COMMENTS_COLLAPSED=true pnpm dev`, open a share link
with no comments (panel closed), post one as a guest, reload (panel opens).

### 4. Pin / speech-bubble tool — REAL REDESIGN, needs a decision first
There is no spatial anchor on a comment today (confirmed: `Comment` has
`timecode_start`/`timecode_end` only). `use-drawing.ts` has pen/rectangle/arrow/line
tools but those are freehand annotations layered on the video, not a comment-linked
pin. Building this needs: a DB migration adding `position_x`/`position_y` (or a JSON
`anchor` field) to comments, a new click-to-place UI state in the media viewer, a
marker-rendering layer synced to comment list, and a decision on whether pins persist
per-frame (video) vs per-image. This is a multi-day feature, not a slice. Do not
start it without Saskia and Alan agreeing on the interaction (does a pin require a
comment immediately, or can it be dropped and filled in later; does it work on video
scrubbing or only static frames first).

### 5. Blue over orange — NOT a code decision
The global `--accent` token is already blue. The oranges Alan is seeing are
hardcoded per-component (avatar colour, a drawing-tool colour swatch, an
avatar-colour cycling list) — three different files, three different purposes (some
of those oranges are decorative variety, e.g. cycling avatar colours, not "the accent
colour"). Swapping them requires knowing which oranges are "the aggressive review
colour" Alan means vs. which are incidental avatar variety that should probably stay
multi-coloured. Per the task's hard limit, this branch does not touch colour. Needs a
one-round design pass with Alan pointing at the actual screen.

## What shipped in this branch

Only item 3, behind `NEXT_PUBLIC_SHARE_COMMENTS_COLLAPSED` (default off):
- `apps/web/app/share/[token]/page.tsx` — flag constant, gated default state, one-shot
  comment-count fetch.
- `apps/web/Dockerfile.prod` — new build `ARG`/`ENV`, default `false`.
- `docker-compose.aditor.yml` — turns it on for Aditor's own deploy, with the
  reasoning written inline per house convention.

## Left for a design/product decision

- Item 1's multi-asset "download all" (needs a zip endpoint).
- Item 2's real share-link-minting-by-a-guest (needs a permission model).
- Item 4 in full (needs a migration and an interaction decision).
- Item 5 in full (needs Alan to point at which oranges he means).
