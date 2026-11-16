# Review: fix and delete your own notes after they are saved — design

Status: spec for Alan's go · Size: M · Alan 2026-11-17 ("Kommentare, die falsch sind, umtippen … oder ein Wort, das falsch geschrieben ist … löschen, wenn ich hovere, oder ein Müll-Emoji in der unteren rechten Ecke")

## Why

A note is saved the moment it has its words (optimistic save). From then on it is read-only in the review: no edit, no delete. A misheard word or a wrong note stays on the client's timeline. Today only the short window before the save shows a textarea and an ×.

## What

1. **Edit**: click the text of one of your own saved notes → it turns into the same textarea as today, prefilled. Enter or blur saves, Esc cancels. While it saves the check mark shows the spinner, then the check again. The old text is never lost on a failed save (the textarea stays with Retry).
2. **Delete**: hover a note (desktop) → a trash icon in its bottom-right corner. Phone: always visible, small. One tap deletes, a 5 s "Deleted · Undo" line replaces the note (no confirm dialog). After 5 s the delete is sent.
3. **Only your own notes** in this browser: other people's comments and Auto Review's never show edit or trash.
4. Edited notes get no "edited" tag (it is a draft fix, not a discussion).

## How (ownership)

- **Logged-in reviewer**: existing `PATCH /comments/{id}` and `DELETE /comments/{id}` (author check already there).
- **Guest on a share link** (has no account): on create the server returns a random `edit_key` once; it stores only its hash on the comment. The browser keeps `commentId → edit_key` in localStorage. New `PATCH` / `DELETE /share/{token}/comments/{id}` require the share link to allow commenting, the comment to be on an asset in that share, and the `edit_key`. Without the key: 403. Soft delete like the owner path.
- The outbox entry records the server comment id when the save lands, so the note knows what to patch.
- Editing the body clears `review_source` like the owner path already does (so the agent sees the human version).

## Not in scope

Editing other people's comments, editing drawings or images of a saved note, edit history.

## Scope

- API: `apps/api/routers/comments.py` (guest create returns `edit_key`; guest PATCH/DELETE), migration for `comments.edit_key_hash` (nullable), tests in `apps/api/tests/`.
- Web: `lib/note-outbox.ts` (keep comment id + key), `lib/share-flow.ts`, `components/review/flow-view.tsx` (edit + trash + undo), tests.

## Done

- Pytest: guest with key edits and deletes; wrong/missing key 403; view-only link 403; comment on an asset outside the share 403; account comment never reachable via the guest route.
- Vitest: click saved text → textarea → Enter sends PATCH; trash → Undo within 5 s sends nothing; after 5 s DELETE; no edit/trash on a note without a key.
- `pnpm test` + backend tests green; screenshots of hover-trash and edit at 1440, opened for Alan before merge.

## Stop & escalate

- If the agent feedback loop (AutoReview `get_feedback`) already took a round containing the note: the edit still saves, but say in the PR whether the agent sees the change; never rewrite a closed round silently.

## Doctrine gate

- [x] Seen by Alan live (2026-11-17 share review).
- [x] Preserves work: undo instead of confirm, failed save keeps the text (UX law 15).
- [x] Deny by default: no key, no edit; account comments untouched.
- [x] Reversible: soft delete, nullable column.
