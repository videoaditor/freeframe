# AutoReview blue-check identity

## 1. Job
Recognize AutoReview in tabs, link previews and the app. Web, desktop and mobile. Success: one legible blue check, derived from Aditor's two-piece mark, at 16–512 px.

## 2. Screen inventory & navigation
Existing browser tab, login, setup and sidebar; no navigation changes. External link-preview caches may refresh independently.

## 3. Content hierarchy
A single blue mark. No lettering, shield, shadow or additional badge.

## 4. Components
Static favicon (ICO and PNG), transparent app logo, opaque Apple touch icon. Existing accessible product names retained.

## 5. States
Light/dark backgrounds share the same silhouette. Loading/error/offline behavior and fallbacks unchanged. No new interactive states.

## 6. Tokens
Solid blue #007AFF (approximately OKLCH 60% .22 257); two asymmetric rounded ribbons and a clear negative-space seam. Safe margins approximately 8%. No type or motion.

## 7. Accessibility
Identify the app, not a review pass or certification. Existing image alt text retained. Check contrast and silhouette on white and near-black at 16, 24, 32 and 48 px. No new touch targets or keyboard interactions.

## 8. Decisions
User requested a blue check resembling upside-down Aditor; follow-up: sharper, more iOS-like, slimmer with minimal corner rounding. Source generated with the built-in image tool from the real Aditor raster mark; exports only resize/encode the generated asset. Keep shared Aditor corporate logos untouched.

## 9. Review
Link-preview follow-up: explicitly expose the approved 512 px blue check through Open Graph and Twitter summary metadata, in addition to the existing favicon. Use only generic product text; never expose project titles, thumbnails or review comments to crawlers. Production Compose derives the absolute image origin from `FRONTEND_URL` at build time (`NEXT_PUBLIC_SITE_URL` for local builds). Existing third-party cached previews may require re-fetching; changing metadata cannot invalidate Trello's cache. No icon redesign or review access changes.

Inspected in the browser at 16, 24, 32, 48 and 128 px on light/dark backgrounds. Follow-up increased arm thickness by approximately 15%, retaining the split. Proof: `icon-proof.png` in the 2026-10-09 Downloads delivery folder. Metadata points to a versioned PNG; classic ICO contains 16/32/48/64/128/256 px images. No automated media-review pass claimed; software iteration uses the existing October preview tracking card/session.
