# Parts review timing

`GET /r/{token}/iterations` adds optional `processing` and `review_progress` to source parts and current generated ads. PartsWorkspace passes them to the existing RequestWorkspace; failed status polls stop its activity while retaining its current frame. Older responses without progress remain usable and display waiting with an unknown clock.

Source progress is bound to the live exact AssetVersion in the request's project. Elapsed time uses only the committed RequestUpload.submitted_at for this request, asset and exact version number. Reopening a link preserves that clock; replacing a version selects the new submission. Source-only early readiness follows the runner's durable `iteration_review_ready` flag, so existing feedback remains viewable before HLS finishes.

The Parts runner currently supplies durable statuses, not durable analysis/publication phase timestamps. Pending reviews therefore say waiting rather than asserting that analysis has started. Generated ads expose their current asset/version identity before feedback arrives, but retain existing preview and download gates. They do not borrow source-upload times, recovery lease times, backoff times or updated_at.

No ETA is required to release this adapter. Future calibrated ranges need an authoritative per-attempt job ID, exact version, Engine/pipeline/model-policy/environment/cache/retry scope, source submission or a separately defined derived-output origin, and durable analysis/publishing/published-or-failed events. The existing Engine remains default. No producer, scheduler, review result or feature activation is changed by this adapter.
