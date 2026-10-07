# H2 implementation and verification plan

Authoritative specification: feedback-agent handoff dated 2026-10-05, H2A/H2B and unchanged CONTRACTS.md. H1 owns RequirementSource/Snapshot; this change projects only the H2 comment subset and does not infer sources.

1. Add regression tests for a fail-closed bridge-only comment path, bounded source validation, spoofing, foreign share/version, replay, human edit invalidation and unchanged resolve/reactions.
2. Add nullable JSONB provenance and stable service publication identity/digest, one Alembic migration. Store comment and metadata in one transaction. Reuse share authorization and configured automation allowlist. Authenticate with existing review_bridge_secret. Reject malformed input (422), missing/wrong auth (503/401), unauthorized scope (403/404), changed replay (409); retry ambiguous HTTP results with the same publication ID. Do not resurrect edited/deleted rows.
3. Extend the existing Comment type/row with neutral static labels; test supported/unknown/null/multiple sources and API revalidation.
4. Run repository gates; migrate an isolated Postgres and test persistence, concurrency/readback/export and unchanged n8n columns. Capture a real local API and browser with synthetic media only.
5. Inspect H1.json at Worker integration; integrate only its verified contract commit. If absent, leave the exact dependency open. Write reviews/H2.md, H2.json and a draft PR; no deploy or merge.

Doctrine gate: M1 spec-first and machine-checkable Done/Stop supplied by the commissioned H2 specs; M2 existing API/models/components; M3 red/green and gates; State PostgreSQL first; Separation bounded pure validation/projection; Idempotency stored publication ID and original digest; Coupling nullable v1 schema; Context own worktree/status; Error taxonomy above; Defensive design no missing-secret fallback; F1 no engine/model changes; Tests boundary + real database + browser. Stop after three serious attempts of the same blocker and retain a repro.
