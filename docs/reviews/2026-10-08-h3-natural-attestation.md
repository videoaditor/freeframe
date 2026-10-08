> SUPERSEDED: Root rejected this KV-authority implementation. Use [PostgreSQL authority](2026-10-08-h3-postgres-attestation.md); the following is historical only.

# H3 single-order natural intent — local integration handoff

Root authority decision implemented locally. Worker base1419482a7360d471002a03eb6fe2cde7d4a9b388;
FreeFrame base671fa0d8db521e2c1a4a57231f2dea3e01cc4859. Exact final commit IDs
and clean-state evidence are in the existing sessions/H3.json manifest.
Root alone checks real customer status, integrates, merges and deploys.

## Result and exact identity

FreeFrame's existing service-key/principal-only timing_context now returns
upload_request_id=U from the SAME RequestUpload query that supplies committed
submitted_at for the checked project/share/asset/version. It rejects multiple
source rows. Shares can legally be reused, so share alone is not an order ID.
ChecklistBinding B is a different identity; the existing saved snapshot's U alone
does not identify which RequestUpload supplied the timing clock. No new schema,
DB state, role, public permission, Engine or UI changes.

The Worker consumes ONE immutable operator-owned intent per U in existing
RULES_KV. It must match private U/project/share and predate committed submitted_at,
the earliest timing event. Missing U fails closed for rolling API integration.
Quiet/explicit test origin always overrides natural. Source mismatch, retained
unknown/test evidence, conflicting hash, failed cache/evidence reads, truncated
scan and submissions at/beyond90-day evidence retention suppress natural.
Provenance and private attestation hash freeze across phases; public timing omits
both. Existing V1 cannot be newly attested after submission; a future V2 can be
independently verified under the same single order. History is never rewritten.
Calibration thresholds and pre-run model policy are unchanged.

## Operator command

`timing:attest` defaults to GET-only dry run. Both direct installed vite-node and
actual npm entry are exercised. Input JSON accepts ONLY tenant_id,
upload_request_id and share_token. No supplied/backdated attested_at. Explicit
`--apply --customer-order-verified` is required to create only the absent exact
intent key; conflicting intent/quiet/test/unsupported engine refuses mutation.
Matching existing intent retains its original timestamp; apply checks readback.
The existing operator is the single writer; no KV CAS is claimed.

The absolute dry-run command and expected existing-credential/actual-order inputs
are documented in docs/review-timing.md in the Worker. No fictional customer file
was created, no credential file was assumed, and no live dry-run/apply/attestation
was executed. Local CLI tests use only an isolated fake Cloudflare transport.

## Evidence

- Worker baseline1685passed/6optionalHTTPskipped. Actual producer RED3failed/62passed; command missing-function RED7failed; installed-entry RED1failed. Final167 targeted and1733full passed/6optionalHTTPskipped (144files passed/1skipped). All requested classes covered: forged registration, cross project/share/U, late/equal attestation, quiet/test precedence, V2, real producer and public projection privacy.
- Worker TypeScript161baseline/161current, zero added/removed file-code-message diagnostics; both exit2 existing debt. Local production bundle exits successfully with --dry-run; no deploy.
- FreeFrame API missing-U/ambiguity regressions failed against original projection;10targeted passed and669full passed/101skipped. Initial test environment lacked already-declared rfc8785==0.1.4; installed it in the existing test venv. Mock DB/query contract checks, not live DB uniqueness or production permission proof.
- FreeFrame frontend608tests passed, build/typecheck/lint exit0. Lint/test/build emit existing warnings from untouched files. No frontend edits or visual-readiness claim.
- Evidence logs and saved execution ledger: sessions/H3/natural-attestation/. Both worktrees have diff-check verification. No new media upload/provider run, Engine activation, role/quota/account change, push or deploy. Automatic video review does not validate this software patch; no media-review pass is claimed.

## Independent review and one fix pass

Fresh reviewer h3_natural_final_review found0Critical,4Important,0Minor. All four
Important findings were reproduced together (RED6failed/98passed), fixed and
verified (GREEN167targeted; full1733/6). Fixes:90-day evidence-age boundary,
trusted-watch test precedence, preserving failed cache-read availability, npm
entry detection. The author's TDD closure is the evidence; no second independent
approval or rerun is claimed. Root reviews the combined integration.

## Remaining boundary and rulings

**Successful stale-negative KV reads remain an explicit limitation.** An empty
complete list/null cache can be stale and hide an earlier unclassified observation.
The bounded checks reject explicit errors, expiry and visible conflicts; they do
not prove absolute no-promotion under arbitrary cross-region staleness. A strict
first-writer guarantee requires authoritative serialized version provenance.
This patch does not invent a parallel storage platform. Root must judge this
remaining limitation before later live natural attestations. Cost if wrongly
accepted: hidden previous unknown evidence can allow a later natural attempt.

The strict attested_at < submitted_at rule intentionally qualifies only future
committed versions; cost if stricter than intended is reduced eligible traffic,
not fabricated natural evidence. Real customer authenticity and actual live
permission/source behavior remain Root's/operator verification; no production
access was exercised. Live ETA accuracy remains unqualified: zero new real timing
runs, unchanged5/30/30+10/20% gates. Author full-suite logs are not represented as
independently rerun by the reviewer. No deferred minor findings.

## Root integration sequence

Review this explicit KV limitation, then integrate the two focused local commits
onto the stated current mains and run the combined checks. API-first exposes U;
Worker-first stays unclassified until that private field arrives. Keep new Engine
OFF. Before any later apply, Root verifies one actual customer order and prepares
its project/U/share JSON through existing authorized access. Run only the default
dry run first, reconcile any uncertain write, and retain exact-version timing
proof. This handoff enables future admissible evidence; it does not claim an
accurate ETA or authorize an automatic production attestation.
