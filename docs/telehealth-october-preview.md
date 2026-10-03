# Telehealth October preview — integration and release

Campaign `telehealth_october_2026` offers AutoReview for one brand through October 31, 2026. The absolute cutoff is **2026-11-01T04:00:00Z**, November 1 at midnight in America/New_York, 13:00 in Japan. Late signups receive only remaining campaign time. No card, automatic charge or rolling 30-day extension is promised.

## Implemented contract

Suite is authoritative for membership. FreeFrame accepts campaign metadata only through its existing HTTPS exchange/entitlement calls and stores it in `users.suite_campaign`, separate from editable preferences. The local fixed cutoff also defeats a cached positive decision. Only confirmed campaign expiry allows identity/profile, plan recommendation and feedback access; revocation, invalid identity and provider outages remain denied.

The expired screen replaces tool content while keeping both Masterclass + Tools and Team visible. Team is recommended at 20 distinct successful ads; this is not a usage limit. Unique ledger rows survive version retries and normal asset changes. Only transferred campaign-window ads with a matching successful engine verdict count; unavailable, pending and failed reviews do not. Requests created by invited editors count toward the project owner. On upgrading, reopen AutoReview from Whop to persist the verified paid grant and reopen guest links.

Preview owners serialize workspace creation using a database row lock. Many requests fit inside one active brand workspace. Existing paid AutoReview customers are exempt from the preview limit and cutoff. Anonymous request/share links and authenticated project/asset/upload actions enforce the project owner's cutoff. Upload aborts and acknowledgement of already accepted uploads remain possible; no new multipart completion/review is allowed after expiry.

Feedback is persisted before its receipt; author and campaign come from trusted server fields. See [product-feedback.md](product-feedback.md) for daily scheduler, Slack scopes, idempotency and uncertain-delivery recovery. Feedback text never authorizes automated code changes or deployment.

## Release order

1. Back up the existing Suite SQLite and FreeFrame PostgreSQL databases. Record deployed revisions and preserve every current environment value.
2. Integrate latest main in each isolated candidate, run its checks, and deploy additive Suite/FreeFrame migrations and code together. No current customer cohort exists until its dedicated Whop product is mapped.
3. Create a hidden free Whop product with only the existing Review experience. Verify no card/charge and correct entry destination. Add its **product** ID to live `WHOP_PLAN_TIERS` as `review_preview`, preserving all paid mappings; set the verified `TELEHEALTH_PREVIEW_CHECKOUT_URL`.
4. Configure `PRODUCT_FEEDBACK_SLACK_TOKEN` using an existing authorized Slack app in #automations (`C07UL6BAG1Z`); verify posting and history scopes. Keep one Celery beat scheduler. Empty days are silent; default delivery is 00:00 UTC / 09:00 Japan.
5. Deploy the Pages candidate and perform fresh-customer acceptance before sending the campaign email. Final intended URL: `https://pages.aditor.ai/suite/autoreview/telehealth/`.

## Acceptance still required

The code and local fixtures are not evidence of a live signup. Test a fresh Whop claim, private customer identity, brand rules import, real synthetic video upload/review, second-account isolation, feedback persistence and one actual digest. Confirm checkout's return destination. Controlled local clocks test expiry; never move the production clock or expire a real paid account for testing.

Current provider blockers (October 3): Whop requires explicit acceptance of updated legal terms before product administration; confirmation is pending. No verified free preview product/checkout has been created. The documented local Slack token is revoked and production has no feedback Slack token configured. Suite's Render SSH identity is unavailable, so obtain the current SQLite backup through its authenticated dashboard Shell before deployment. No trial campaign has been deployed or announced.

Paid checkout destinations were inspected read-only on October 3. Masterclass checkout `plan_tWfZVey4GvWhl` offers 14 days followed by $99.75 per four weeks, excluding tax. Team checkout `plan_lm63pw8rtX7uk` offers 14 days followed by $525 per month, excluding tax. The interface deliberately leaves actual pricing and agreement to Whop. The free campaign uses its own product, not these paid checkouts. No purchase was made.

The November 1 reminder is an audit backstop at 13:15 Japan time; server enforcement owns expiry. No campaign emails were sent.
