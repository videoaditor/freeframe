# Product feedback intake and daily Slack digest

Authenticated users open the persistent **Feedback** bubble on any dashboard page, choose **Report a bug** or **Feature request**, and submit up to 4,000 characters. The server commits the report before returning a receipt. Repeated requests with the same submission UUID and authenticated author return the original receipt. Author, Suite account and campaign attribution come from server-owned user fields. Client-supplied attribution is rejected. Page context is reduced to a known route group; identifiers, tokens, query strings and fragments are discarded. Verified campaign-expired customers may still submit feedback.

The launcher is available to ordinary, paid, active-preview and expired-preview customers. A compact corner dialog opens on desktop and a scrollable bottom sheet on mobile. Closing it preserves an unsent draft and returns keyboard focus to the launcher. On asset pages the launcher sits above the bottom review controls. The panel is a direct submission form; it does not imply a live chatbot or promise an immediate response.

Staff review reports at `/feedback`. `GET /product-feedback?offset=0&limit=25` is authenticated and staff-only (maximum 100 per page). All stored reports remain available independently of Slack. Report text is untrusted customer content and never causes code execution, automated implementation or deployment.

## Runtime configuration

Apply the Alembic migration with the normal release procedure, and run the existing Celery worker plus **one Celery beat scheduler**. Configure the following in the existing API/worker/beat environment:

| Setting | Default | Meaning |
| --- | --- | --- |
| `PRODUCT_FEEDBACK_SLACK_TOKEN` | Empty | Existing Slack bot token; absent disables delivery, not intake |
| `PRODUCT_FEEDBACK_SLACK_CHANNEL` | `C07UL6BAG1Z` | Verified private #automations channel |
| `PRODUCT_FEEDBACK_DIGEST_HOUR_UTC` | `0` | Daily UTC hour, 0–23 |
| `PRODUCT_FEEDBACK_DIGEST_MINUTE_UTC` | `0` | Daily UTC minute, 0–59 |
| `FRONTEND_URL` | Existing config | Origin for the staff queue link |

00:00 UTC is 09:00 Asia/Tokyo. Never reuse a connector's temporary token. The configured existing Slack app must belong to #automations and have `chat:write` and `groups:history` so accepted messages can be reconciled after a timeout. No new bot or app is created by this implementation. Official provider contracts: [chat.postMessage](https://docs.slack.dev/reference/methods/chat.postMessage/) and [conversations.history](https://docs.slack.dev/reference/methods/conversations.history/).

## Delivery and recovery

Every daily report is first saved as a `feedback_digests` row with immutable payload and report membership. A dedicated PostgreSQL session advisory lock serializes workers across commits. There is at most one confirmed digest per UTC day. Empty input stays silent. A failed older digest is recovered before a new one is created; new reports remain in the intake queue.

The Slack message contains counts, up to 40 brief report previews and a staff-only queue link for all reports. It uses literal text, disables media/link unfurling, strips report links and obvious credential patterns, and does not include customer email or media. It does not promise a perfect secret detector; the form explicitly tells customers to omit passwords, patient information and private links.

State transitions:

- `pending` → `sending` is committed **before** contacting Slack.
- A confirmed Slack timestamp allows `delivered` and `delivered_at` to be committed.
- Explicit rejection (including rate limiting) returns to `pending`; Celery retries three times at 15-minute intervals, then the next daily run retries the durable batch.
- Timeout, server failure, or worker death after the send checkpoint leaves `sending`. A later run searches channel history for that batch ID in message metadata. A match checkpoints the existing post without another send.
- If no receipt can be proven, the task fails visibly in Celery and the batch stays `sending`. It is **never automatically resent**. This is deliberate: an absent history result is not proof that Slack never accepted the original request.

For a persistently uncertain batch, an operator inspects `feedback_digests.id`, `status`, `last_error`, and the matching Slack message metadata. If the message exists, restore history access and rerun the task so it reconciles. Only after independently establishing that no post was accepted may the operator reset that batch to `pending` using the normal authorized database maintenance process. Do not delete feedback rows or create a replacement batch. No automatic post can guarantee exactly-once delivery across an ambiguous network failure; this design preserves reports and stops instead of risking duplicates.

## Acceptance before enabling

Local mocks cover durable intake, author-scoped idempotency, customer rejection from the staff queue, single-writer lock behavior, empty days, explicit Slack failure, ambiguous timeout and receipt reconciliation. Provider acceptance still requires a migrated real database, the existing app's channel membership/scopes, a controlled report, and confirmation of one scheduled digest plus a working staff-only source link. No live Slack message is sent by the tests.
