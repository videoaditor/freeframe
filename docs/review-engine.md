# Review engine selection

The existing file-request flow supports a server-only `REVIEW_ENGINE` setting:
`legacy` (default) or `continuity-v1`. Configure `REVIEW_BRIDGE_URL` and
`REVIEW_BRIDGE_SECRET` for the authenticated review service. Keep legacy until
the selected engine and its Worker adapter have been validated together.

After authorization and database commit, the server registers the request with
`tenant_id=freeframe:project:<project UUID>` and the committed request UUID.
The project scope isolates review caches; it does not identify a billing account.
The browser cannot choose either identity or the engine.

Selection applies to newly registered requests. Changing `REVIEW_ENGINE` to
`legacy` rolls back future requests and preserves existing request selections,
in-flight jobs and version-specific review history. Invalid values do not fall
back to another engine: the request link still works and review is unavailable.
Unavailable registration or briefing extraction never claims a completed review.

For shared provider credentials, keep the review Worker's concurrency at one
and configure the Python engine with `AUTOREVIEW_WORKERS=1` until dedicated quota
has demonstrated capacity. The Worker continues accepted jobs across bounded
polling visits; it does not cancel an accepted job when its local wait expires.
