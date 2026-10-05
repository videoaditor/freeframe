# Hub → Handin card handoff

Hub sends `https://feedback.aditor.ai/handin?card=` with an encoded canonical HTTPS Trello card URL. Only `trello.com/c/<8-character short id>` is accepted; credentials, other hosts and insecure URLs leave the form blank. Slugs and tracking parameters are removed.

Handin prefills the editable card field and loads its title/brand through the existing gate. No upload or delivery starts automatically. Editing or pasting another card invalidates pending lookup results. Sign-in redirects retain the query string, including when a Handin session expires.

Release the receiver together with the Hub sender on branch `codex/compact-editor-dashboard`. No production deployment is part of this change. Unit/component tests cover invalid links, prefill, stale lookups, replacement paste, ordinary and Whop redirect targets. Actual hosted Whop callback continuation still requires a signed-in staging smoke test.
