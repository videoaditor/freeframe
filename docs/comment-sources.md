# Verified AutoReview comment sources

Comments may carry nullable `review_source` v1 metadata: `schema_version`, `requirement_id`, optional `plan_id` and up to eight unique `{layer, reference_id, source_version}` references. The source layer is Basics, Brand or Briefing and does not set severity. Existing comments remain unlabeled. No source inference or backfill uses names, email, body text or legacy `from` values.

The review bridge alone can publish these fields through `POST /review-bridge/share/{token}/comments`, using `Authorization: Bearer <review_bridge_secret>`. An unset secret fails closed. The automation email must also be configured in `automation_guest_emails`; email is an identity selector after authentication, never proof of provenance. Existing share password/session, permission, scope and enabled/expiry checks apply. `asset_id`, an explicit ready `version_id`, a stable UUID `publication_id`, automation `guest_email` and `body` are required; timestamps and `review_source` are optional. The endpoint accepts only top-level comments and retains existing internal automation visibility.

The bridge producer must bind references to the authorized project's frozen H1 snapshot before model planning. Unknown model IDs cannot create a trusted source. `quote` and arbitrary fields are rejected, and only the bounded public reference projection reaches comment/request responses or CSV. Owner/team source prose drilldown is outside this change.

Normal member/guest create, reply and update payloads cannot set service provenance. Changing text clears `review_source` server-side. Resolve, reactions and replies keep the original text's source. A no-op text update preserves it.

Comment, provenance, publication identity and share activity commit together. Retries use the same publication ID and normalized payload; they return the existing row. A changed payload or deleted publication returns 409. Human edits are never overwritten or relabeled by replay. Readback may show null provenance after such an edit. The original payload digest stays internal and is never a guest response field.

Migration `a7b2c3d4e5f6` adds three nullable columns and a unique publication constraint. It does not modify the n8n views, triggers or column order. CSV appends one optional JSON `review_source` column; the original columns and NLE marker formats retain their semantics.

Local verification and current integration limits: [H2 review](../reviews/H2.md). Production integration requires H1 snapshot binding and verified source-bearing Engine reports; this PR does not deploy, infer missing sources or alter the reserved Engine adapter.
