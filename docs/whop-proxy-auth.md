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


## Customer brand and Word briefings

A verified Whop customer receives one private brand workspace on first sign-in. The display name
comes from Suite's server response (`brandName`), falling back to “My brand”. Existing workspaces,
project IDs, permissions and review rules are preserved; display names never link customer accounts.
Already signed-in customers without a workspace receive one on their next project-list load.
Concurrent sign-ins serialize on the customer row. Expired preview access does not provision a workspace.

The request form shows a sole brand as context (“For Fortea”) and keeps the picker for accounts with
several brands. Word (`.docx`), PDF, Markdown and text briefings up to 10 MB work in requests and brand
guidelines, including setup. The API extracts ordinary Word paragraphs and tables into review text
before saving the request; it rejects corrupt, empty or oversized documents. It does not execute
macros, embedded files or external links. Old binary `.doc` files need to be saved as `.docx` first.

Deployment needs both API and web rebuilt; no database migration or new dependency is required.
Suite should return `brandName` from `/v1/auth/owner` for the initial workspace label. Keep the existing
proxy-safe session headers and central-gate build configuration. Acceptance: a new Whop member sees
one brand, a repeated sign-in keeps that same workspace, and a Word briefing creates a request with
the extracted full text in its frozen checklist input (not just the 500-character display excerpt).
