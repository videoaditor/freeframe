# Whop proxy session transport

Whop sign-in uses the injected `x-whop-user-token` only at `/whop/session`.
The API still verifies identity through Suite and checks the `autoreview` entitlement.
The public `/o` compatibility route redirects to `/whop`, including older app entry settings.

After sign-in, the browser sends its FreeFrame access JWT in both `Authorization: Bearer …`
and `X-FreeFrame-Token`. Whop's app proxy removes `Authorization` before forwarding requests.
Required and optional API authentication accept the alternate header only when the standard
header is absent. Both transports use the existing JWT validation, account lookup and customer
entitlement checks. Neither cookies nor the injected Whop token authorize ordinary API requests.
Rate limiting derives the same user identity for both transports. No nginx header mapping is needed.

Production must keep `SUITE_URL`, the exact `WHOP_APP_ID` (case-sensitive), and the Review bridge
settings in its private env file; ad-hoc container overrides do not survive a regular deployment.
Whop's app base URL should point at the FreeFrame domain, with `/whop` as its entry path.

Acceptance: open the app in Whop, confirm the profile and workspace load, reload it, and confirm
brand rules and projects still load. A direct session exchange without the Whop header must return
401. Signature failures, deactivated accounts and revoked entitlements must remain denied.
