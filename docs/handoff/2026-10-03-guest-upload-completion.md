# Guest upload completion regression

Production at 2026-10-03 12:36 UTC failed in `guest_complete` with
`sqlalchemy.exc.NoResultFound` after multipart finalization. The editor page defers
name/email until submission. `_record_uploader` adds the new request-upload row,
but production `SessionLocal` uses `autoflush=False`. A subsequent `.one()` query
cannot see that pending row, so completion fails before processing is scheduled.

The helper now returns the created or existing row. Completion marks that same
object submitted and commits it with the processing state, preserving the size
check, identity validation, retry behavior and one processing task.

The focused mock regression fails for deferred identity before the fix, and passes
for deferred and previously supplied identities after it. The existing real
PostgreSQL editor journey now uses production's `autoflush=False`; it reproduced
the same exception before the fix and passes after it, including revision history,
serialized completion, finish locking and cancellation. Storage and review calls
are mocked; this evidence does not claim a successful live AI review.

No schema, task payload, frontend, account or authentication change. Deploy the
reviewed API change through the existing production process, then retry the failed
demo upload and verify review starts. The current live upload has not been retried
by this change preparation.

Verification on the candidate: 423 backend tests passed (5 skipped), including
the opt-in real PostgreSQL editor checks; 492 frontend tests passed. Frontend
typecheck, lint (existing warnings) and production build succeeded. Tests ran
against an isolated disposable local database, never production storage.
