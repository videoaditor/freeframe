# Design Handoff — Hand-in revision view (two-pass review, Lane C)

Spec: feedback-agent `docs/superpowers/specs/2026-10-17-two-pass-review-design.md` (contract C5, Lane C).
Built on #95 (Must-fix vs Guidance) and #96 (pending line).

## C1 finding — do bridge comments reach an open asset page over SSE?

**No.** Nothing in the API publishes `new_comment` (or any comment event):

```
$ grep -rn -E "event_service|\bpublish\(" apps/api | grep -v /tests/ | grep -v "def publish"
routers/events.py:13:      from ..services.event_service import event_stream
tasks/transcode_tasks.py:  r.publish(f"project:{project_id}", message)
tasks/watermark_tasks.py:  r.publish(f"project:{project_id}", message)
services/event_service.py: await r.publish(...)   # the helper itself, never called
```

`POST /review-bridge/share/{token}/comments` (`apps/api/routers/comments.py`, `publish_review_comment`)
writes the comment and returns; it publishes nothing. Neither do human comments. The web side
listens (`apps/web/hooks/use-sse.ts` `new_comment`, tested in `hooks/__tests__/use-sse.test.ts`), but
no page passes `onNewComment`, and the asset page loads comments once (`hooks/use-comments.ts`, SWR,
`revalidateOnFocus: false`).

Consequence for C4: the asset page uses a **bounded poll** instead of SSE — it refetches its comment
list every 5 s while the viewed version is younger than 10 minutes (pass 2 lands ~85–100 s after
upload; p90 of today's single pass is 208 s). The list is replaced wholesale from the server, so a
comment can never appear twice. Publishing `new_comment` from the API is a separate (API) change.

## 1. Job
- **Who:** an editor who just handed in a cut and is still on `/handin`. **One thing:** start fixing the
  Must-fix the moment pass 1 decides it, without waiting for the taste read.
- **Platform:** web, desktop + phone (375 px).
- **Success:** the held panel is in view with the Must-fix on top and one primary button, "Open revision",
  which opens the asset's review page where the comments sit on the timeline.

## 2. States
| State | Reached from | Presentation | Exit |
|---|---|---|---|
| Held, pass 2 running | `deliver-status` → `held`, `guidancePending` | held panel scrolls into view once | "Open revision" (same tab) |
| Held, pass 2 done | next 5 s poll | same panel, pending line gone, Guidance filled in | same |
| Held, no `revisionUrl` (older worker) | — | button points at the hand-in folder | same |

## 3. Content hierarchy (held panel, top → bottom)
1. "Not delivered yet." + the V2 rule (one line)
2. Per video: Must fix (full contrast) → **Open revision** right under it (primary; secondary for the
   2nd+ video) → Guidance (secondary text) → pending line (quiet)
3. "A note is wrong?" (tertiary)

The "Open folder in FreeFrame" link below the share link is hidden while held: the panel's button
already goes there (or one level deeper), and two look-alike links would compete (Von Restorff).

## 4. Components
| Element | Component | Style | Label | Notes |
|---|---|---|---|---|
| Revision link | `Button asChild` + `<a>` | primary, md (h-9; h-11 on coarse pointers) | "Open revision" | icon `PlayCircle`; with several videos the name above says which |
| Pending line | text, `role="status"` | text-xs, tertiary, spinner respects Reduce Motion | "More guidance is coming. Start on the Must-fix." | unchanged from #96 |

## 5. States detail
- **Loading:** pending line while pass 2 runs (ETA implied: the page updates by itself).
- **Error:** a fetch failure reads as `reviewing`, never `held` (unchanged).
- **Done:** "Delivered to the Trello card" (unchanged).

## 6. Tokens
Existing tokens only (amber held panel, accent primary). No new colours, no new motion.

## 7. Accessibility
Real `<a>` with visible text; 44 px tall on touch; focus ring from `Button`. Contrast from the existing
tokens, checked in light + dark screenshots.

## 8. Decisions
- Decision: a button, not an automatic redirect, because the spec says "one primary action" and yanking
  the editor off the page while they read would lose the share link and the list.
- Decision: `revisionUrl` is followed only when it is same-origin or a root-relative path, because the
  page must never send an editor to a host it does not know; otherwise the folder link is used.
- Decision: Guidance goes to every editor (DECISIONS: "Alle Editoren"); the panel never filters by role.
