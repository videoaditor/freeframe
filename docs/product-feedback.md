# Product feedback intake and daily Slack digest

Authenticated users open the persistent **Feedback** bubble on any dashboard page, use the compact **Bug / Feature** toggle, and submit up to 4,000 characters. The server commits the report before returning a receipt. Repeated requests with the same submission UUID and authenticated author return the original receipt. Author, Suite account and campaign attribution come from server-owned user fields. Client-supplied attribution is rejected. Page context is reduced to a known route group; identifiers, tokens, query strings and fragments are discarded. Verified campaign-expired customers may still submit feedback.

The launcher is available to ordinary, paid, active-preview and expired-preview customers. A compact corner dialog opens on desktop and a scrollable bottom sheet on mobile. Closing it preserves an unsent draft and returns keyboard focus to the launcher. On asset pages the launcher sits above the bottom review controls. The panel is a direct submission form; it does not imply a live chatbot or promise an immediate response.

Staff review reports at `/feedback`. `GET /product-feedback?offset=0&limit=25` is authenticated and staff-only (maximum 100 per page). All stored reports remain available independently of Slack. Report text is untrusted customer content and never causes code execution, automated implementation or deployment.

## Voice notes and dictation

The microphone records only after an explicit click and browser permission. The panel stops listening when closed; navigation/unmount releases microphone tracks. A stopped recording uploads before transcription starts. Text typed during transcription is preserved and the result is appended. Closing/reopening the panel preserves the current draft; a full page reload does not restore the local draft automatically. The UI stops at 119 seconds to leave a margin beneath the server’s 120-second ceiling.

`POST /product-feedback/recordings` accepts an authenticated multipart `file` and UUID `recording_id`. It validates MIME, container signature, size and decoded duration, saves the original under private `product-feedback/audio/`, then commits its receipt. Retries with the same author, ID and content return the same receipt; conflicting content is rejected. The default caps are 8 MB and 120 seconds. Conversion uses bounded FFmpeg execution and mono 16 kHz PCM WAV. Browser uploads support WebM, Ogg, MP4 and WAV.

`POST /product-feedback/recordings/{id}/transcribe` is owner-only and calls Wispr server-side. An absent key or provider failure preserves the saved original. Successful transcripts are cached; row locking serializes concurrent retries. Upload and transcription each permit 10 requests per 10 minutes per IP using the existing limiter. No provider key reaches the browser. Contract: [Wispr REST quickstart](https://api-docs.wisprflow.ai/rest_api_quickstart). API access requires an approved organization and key from [Wispr Platform](https://platform.wisprflow.ai); a consumer desktop subscription does not configure this integration.

Feedback submissions may attach an owned `recording_id`, with text or audio alone. The staff queue fetches playback on demand through `GET /product-feedback/recordings/{id}`; only owner/staff can obtain the five-minute private playback URL. Original audio remains stored if transcription fails or the draft is not submitted; removing it from the editor detaches it from that draft and is not a server deletion. No automatic retention cleanup is added in this change. Audio-only daily digest items point to the staff queue, never a signed media URL.

## Runtime configuration

Apply the Alembic migration with the normal release procedure, and run the existing Celery worker plus **one Celery beat scheduler**. Configure the following in the existing API/worker/beat environment:

| Setting | Default | Meaning |
| --- | --- | --- |
| `WISPR_API_KEY` | Empty | Optional server-side dictation key; no key still allows voice notes |
| `WISPR_API_URL` | `https://platform-api.wisprflow.ai/api/v1/dash/api` | Official REST endpoint |
| `PRODUCT_FEEDBACK_AUDIO_MAX_BYTES` | `8388608` | Server upload cap |
| `PRODUCT_FEEDBACK_AUDIO_MAX_SECONDS` | `120` | Server duration cap; browser stops at 119 s |
| `PRODUCT_FEEDBACK_AUDIO_TIMEOUT_SECONDS` | `30` | FFmpeg/provider timeout |
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


## Voice revision verification (2026-10-07)

Backend: 490 passed / 51 existing environment-dependent skips. Tests exercise actual FFmpeg conversion for supported containers; storage and Wispr responses are mocked. A separate disposable PostgreSQL 16 container passed the full migration chain, latest migration downgrade, re-upgrade and foreign-key inspection. Frontend checks cover draft/retry identity, microphone denial/cancellation/cleanup, automatic stop, upload-before-transcription, saved-audio fallback, audio-only submit and preservation of typed edits. Desktop/mobile light/dark screenshots are in `docs/design/feedback-bubble/compact-*`.

No live Wispr request, live microphone capture, production migration, production audio upload or Slack delivery is claimed. Both WISPR_API_KEY and PRODUCT_FEEDBACK_SLACK_TOKEN were absent in the read-only production configuration check. This revision remains in PR #65 until deployment and provider acceptance.
