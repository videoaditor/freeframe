# FreeFrame (feedback.aditor.ai) — Roadmap

Arbeitsliste, kein Dokument. Oberstes Item in `## Ready` ist das nächste.

## Ready

- **Smiley-Bewertung nach dem Video.** Verlässt ein Kunde ein Video (ab 10 s Wiedergabe, 1× pro
  Version), tippt er mit einem Tap 😀 🙂 🙁 😠, optional mit Grund — nicht-modal, verschwindet von
  selbst, blockiert nie. Rein intern: Editoren sehen nichts. Jede Bewertung landet in
  `delivery_ratings` (Lieferung + Version, Editor, Kunden-Account, Workspace, Brand-Slug,
  Trello-Card, Zeitstempel, Score, Grund), Export `GET /admin/delivery-ratings` nur für Superadmins.
  Spec: [`2026-10-16-smiley-rating-design.md`](docs/superpowers/specs/2026-10-16-smiley-rating-design.md).
  Fertig = Spec-Abschnitt „Done": pytest + web build/test/tsc/lint grün, Migration up/down/up lokal,
  Screenshots in `reviews/assets/`, PR offen (nicht gemergt). #ready

## In Review

## Done
