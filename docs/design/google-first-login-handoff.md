# Google-first AutoReview sign-in

## Job / success
Existing staff and customers reach their existing account with one obvious action. Web mobile/desktop. Google is primary; email code remains accessible for anyone without Google. Do not change existing account rights, brand bindings or customer trial access.

## Navigation / content
AutoReview identity → “Sign in to AutoReview” → Continue with Google → underlined Use email instead. The email form is disclosed on request, when Google is unavailable, or with an explicit prefilled email link. Code verification and return-to paths stay intact. Remove the additional Aditor Gate button from this screen; the existing SSO routes remain supported.

## Components / states
Existing GoogleButton, Input, Button; status text while provider config loads. Google disabled or failed: show email form. Errors stay visible. Disclosure has aria-expanded/controls. Email input is focused on explicit disclosure. Existing password-enabled self-hosted mode stays supported. Email-code path never requires a Google account.

## Tokens / accessibility
Existing semantic colors and system font. 44px buttons; 4/8 spacing, 16px body text, no new animation. Keep keyboard focus indicators, accessible email labels and light/dark support. Do not hide error messages inside collapsed content.

## Account routing
Google callback already resolves verified email through the configured staff directory and existing account. Reuse that path. No domain-only privilege escalation and no conversion of existing customer/test accounts into staff. Active non-Gmail/non-Aditor addresses exist; their hosting provider is unknown.

## Verification
Test Google primary/disclosure, provider disabled/failure fallback, prefilled email, code submission, existing Google callback/state tests. Inspect real UI in light/dark and mobile. Full CI before deploy. No new signup or customer email is sent for visual checks.

## Evidence
Desktop and 390px mobile checked in the browser; email disclosure focuses the input. Preview uses a local read-only provider-config fixture, not a completed Google sign-in. Existing live Google configuration is enabled. Before/after: [before](google-first-login/before.png), [after](google-first-login/after.png). Build, typecheck and 649 frontend tests pass; lint has existing warnings only. Account-policy question remains separate: preserve directory-based access unless Alan opts into a wider verified-domain policy.
