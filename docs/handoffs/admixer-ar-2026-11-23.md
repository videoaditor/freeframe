# AdMixer × AutoReview · Handoff 2026-11-23

Quelle: `~/Downloads/admixer-autoreview-handoff-2026-11-19.md` (Weg A: Mixer nur über AutoReview, kein `mixer_push`).
Entscheidungen E1–E5 (Alan): `admixer-ar-decisions-2026-11-19.md` daneben.
Spec-Reihenfolge laut Handoff: E5 → S2 → S0 → S1 → S3 → S4, fertig erst mit Probelauf §7 grün.

## Stand

- **S2 Download erst nach Freigabe: LIVE** (#210, 8c7cc0f, deployt 19.11.). Spec `docs/superpowers/specs/2026-11-19-download-after-approval-design.md`.
  Live geprüft: unfreigegeben `?download=true` → 403 `not_released` (Review-Link, Parts-Request, frische Datei),
  Abspielen 200, freigegeben (Agentic Workflows EN_Body) liefert Original, Engine reviewt weiter
  (Test-Request `test(ignore) · S2 Download-Gate Check`, Projekt Aditor).
- **S0 Runbook, teilweise:** Coolify `feedback2` hat Flags/Secrets für Iterations. Mixer (Render `srv-d4hlbdn5r7bs73bv128g`):
  `MIXER_ITERATIONS_MEDIA_HOSTS` = R2-Host von FreeFrame, `MIXER_ITERATIONS_SECRET` gesetzt.

## Offen (Owner: nächste AdMixer-AR-Session)

1. S0 fertig: Alembic-Stand prod, Frontend-Flag im Build, Staging-Abnahme (`handin-components.md` §Acceptance: 2 Hooks + 1 Body,
   Hook tauschen, Retry ohne Doppel-Render, fremder Account sieht nichts, Recovery). Spec schreiben.
2. S1 Agent-Weg in den Parts-Hand-in (feedback-agent MCP + freeframe agent API + gen `ar_*`): `create_request` mit
   `receive_iterations`, Upload mit `role`, Parts-Events in `wait_feedback`, EIN Abgabe-Link pro Request mit Iterations-Outputs
   auf `/d/<token>`, Render erst nach menschlicher Freigabe (E5a), „Rendert…“-Auto-Download, Agent-Approve legt nie Delivery an.
   Hinweis: `upload_version` in einen bestehenden Parts-Request ohne Rolle antwortet 400 „Choose the matching part“.
3. S3 Marken-Library/Remix + Purge nach E3 (`RENDER_RETENTION_DAYS`), S4 gen-aditor #865 umschreiben (`mixer_push` raus, PM1 entfällt). Dann §7.

Beobachtung: „Taste Reel 1“ v5 ging während des Deploys von `reviewing` auf `unavailable`, vermutlich Neustart, nicht belegt.

## Alan wörtlich (19.11.)

> „der kunde bekommt den share link in unserer share link view … kunden facing links nutzen die gleiche feedback engine aber sehen
> cleaner aus. ja abgabe halt. mixer seiten sind für leute dei autoreview mit ihren agents nutzen (extern, nicht intern)
> interne deliveries sind abgabe seite externe sind mixer share“
