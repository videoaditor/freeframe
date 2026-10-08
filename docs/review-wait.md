# Editor review waiting time

The existing request workspace retains the submitted frame and shows a genuine review phase with indeterminate activity. It does not show a completion percentage. The introductory scan runs once for 3.6 seconds per version and then parks. Pause and reduced-motion rules are retained; an offline or failed status stops activity and keeps recovery available.

Elapsed time comes from the server's committed request submission, so reloads retain queue and preparation time. Unknown elapsed time stays unknown. A newly submitted version has its own clock.

Time labels state their scope: “Analysis usually …” excludes preparation, queue and feedback publication; “Feedback usually … after upload” covers submission to acknowledged publication. “About … remaining” is shown only when the Worker supplies a validated conditional range. The browser never counts that range down. With too little matching history it displays “Measuring typical wait time”.

The additive `autoreview.timing.v1` bridge contract carries server timestamps in epoch milliseconds and scoped ranges in seconds. The Worker requires 30 matching complete runs for total wait, and 30 training survivors plus 10 later holdout survivors for remaining time. Remaining is hidden above 20% upper-bound exceedance. Existing analysis-only integrations remain supported. Timing never changes approval or exact-version completion rules.

The share-stream response includes `timing_context` only for the authenticated configured service principal with the matching API key. It binds the share token, project, asset and exact live version to an existing RequestUpload submission. Guests receive no tenant/submission metadata. This reuses existing fields and requires no database migration.

See [H3 verification and screenshots](reviews/h3/README.md). Natural timing accuracy and live Engine integration remain open.


New analysis work requires committed admission for its exact file version, or a committed permanent negative proving it cannot calibrate natural timing. Missing authority or metadata stays in the existing waiting state with bounded automatic retry; it spends no analysis attempt and supplies no invented ETA or analysis start. A completed review remains completed during metadata outages when no newer version is listed. Recovery preserves normal analysis retries and failures, and a confirmed newer version requires its own admission. If the final authority check fails after review completes, feedback remains available while eligible terminal timing is withheld.

The private bridge-only legacy exclusion endpoint reuses existing version exclusion storage. Missing private context alone cannot disqualify a natural, pending, corrupt or ambiguous source. See [pre-dispatch verification](reviews/2026-10-08-h3-predispatch-guard.md). No new screen, queue or database migration is added by this follow-up.
