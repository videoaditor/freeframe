# Whop desktop verification — 2026-10-02

Status: desktop automatic sign-in and full Whop-page reload verified. Full Phase 4 acceptance remains open.

The actual signed-in Alan session opened Aditor Review in Whop, passed through `/whop`, and landed on the actual Whop proxy `/home` with Owner profile, overview, and zero projects. Reloading the outer Whop page returned to the same Owner overview without an email login or recovery screen. This is live browser evidence, not a synthetic UI fixture.

Read-only production inspection found canonical nginx upstreams on API 3091 / web 3090, live checkout `a2e3100fe68b0578bb835e4609080f213d395941`, exact app ID `app_xSpqIhgkn1AX2J`, and Next internal API `http://api:8000`. Image digests:

- API: `sha256:2973c8dc2b51f16b07a649a5339848f0df8bf9bc0358e0323600c56276b75d2c`
- Web: `sha256:63fac21b4d0e54a3a68106f4f47cee020e00fd82e2499db8d3703d62088f9f15`

The nginx access evidence included `/whop/session` 200 and `/home` 200 at 04:52:38–39 UTC (13:52 JST). Credentials and source IPs were omitted. No production configuration was changed in this verification turn.

Local screenshots were saved in Alan's Downloads directory as `freeframe-whop-20261002/whop-home.jpg` and `whop-home-reload.jpg`. They include private Whop account context and were not uploaded to the public repository.

Still pending: actual phone, a second independent entitled Owner and direct cross-project denial, expired/revoked membership, and real briefing/request → guest upload → reviewed current bytes → Ready. Iframe inspection succeeded, but attempted request-button interactions were rejected by the browser automation tool; this is not evidence of an application button failure. No request/upload completion is claimed.

The earlier rollout status on `codex/whop-launch-status` describes the prior candidate deployment; current canonical runtime above supersedes those ports. Other acceptance/runbook text is historical until all real tests are reconciled.
