# Confirm a staff workspace brand

An existing active staff owner can confirm one workspace's brand from a Trello card.
The private review bridge verifies the card's actual board ID against the existing
board-to-brand registry and its exact active brand entry. Workspace names, similar
brand names, and cards in other projects do not establish ownership or brand authority.
Caller-supplied expected values are comparison evidence only, never authority.
There is no automatic backfill.

This requires the additive review-bridge card response fields `board_id` and
`brand_slug`. An older bridge or unavailable registry leaves identity unconfirmed;
ordinary card lookups remain usable. Deploy the compatible bridge before confirming
any workspace. Apply the normal Alembic migrations before starting the updated API.

## Owner API

Use the existing owner's authenticated session:

```http
POST /projects/{project_id}/review-brand
Authorization: Bearer <existing staff owner access token>
Content-Type: application/json

{"trello_url":"https://trello.com/c/<exact-card-id>","apply":false}
```

`apply` defaults to `false`. A successful dry run returns `project_id`, the verified
`card_id`, `brand_slug` and `board_id`, `applied:false`, and `requires_new_assignment`. It writes
nothing. The source card must be accessible to the configured Trello integration.
The response does not itself approve the business assignment: an owner must confirm
that the selected board belongs to this workspace.

After reviewing that exact proposal, repeat with `apply:true` and the exact returned
canonical identity:

```json
{"trello_url":"https://trello.com/c/<card_id>","apply":true,"expected":{"card_id":"<card_id>","board_id":"<board_id>","brand_slug":"<brand_slug>"}}
```

The server re-attests the card, board and active brand and compares all three to
`expected` before any write. Missing expected identity or changed card/board/brand
returns 409 and requires a fresh proposal. Expected values cannot assign a brand.
The database records
the stable brand, board, source card, confirming owner's ID, and confirmation time.
Repeating the same assignment returns the original evidence without rewriting it.
Members, customers, read-only service keys, and inactive users cannot confirm a
brand. Existing instance-wide staff-owner access follows the configured role policy;
this endpoint grants no roles or quota changes.

## Conflicts and existing work

The API inspects active card references in this workspace. Unknown or inaccessible
sources block confirmation. Multiple board identities return 409 and require
separate workspaces. A different identity on an already confirmed workspace also
returns 409; create a separate workspace rather than changing its existing identity.

New requests, native hand-ins, checklist preparation, and folder adoption serialize
against brand confirmation. Workspace renaming cannot change a confirmed brand.
New Trello sources must belong to the confirmed board and brand.

Existing UploadRequests and ChecklistBindings retain their original brand and frozen
brief. `requires_new_assignment:true` reports this situation; confirmation does not
repair or rewrite old requests. Reusing an incompatible checklist or adopting its
folder returns 409 with a new-request instruction. Create a new request with a new
idempotency key and its own folder, and leave the old assignment unchanged.
Existing editor capabilities continue to attest their saved assignment identity.
Complete-ad Handin validates the folder's editor assignment before starting file
uploads, including when optional checklist preparation is unavailable. An unknown
or conflicting assignment stops upload; completed review reads remain available.

Customer projects remain in `cust-<project-id>` namespaces. This feature does not
change customer shares, activate a review engine, retry reviews, or migrate `/u`
and `/d` links. Legacy migration still needs an exact matching assignment and
independent authorization after confirmation; the same card alone is insufficient.
