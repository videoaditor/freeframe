# AdMixer × AutoReview — Entscheidungen (Alan, 2026-11-19)

Quelle: Handoff ~/Downloads/admixer-autoreview-handoff-2026-11-19.md §6, Alans Antwort im Chat.

- **E5 = a.** Module (oder Versionen eines Videos) werden in AutoReview einzeln von einem Menschen freigegeben.
  Sobald alle Teile eines Requests frei sind: Abgabe-Link steht SOFORT fest, Mixer rendert die Matrix im Hintergrund,
  Link füllt sich. Download-Knopf ist sofort da; Klick vor Render-Ende zeigt „Rendert …“ und lädt automatisch,
  sobald die Datei fertig ist. Download blockiert nie auf Agent/Mensch.
- **E1 = Vorschlag (keine Gegenrede).** Vor Freigabe kein Download über Share/Embed/Kunde. Projekt-Owner in der
  Reviewer-Ansicht darf, markiert „Entwurf“.
- **E2 = Sweetspot existiert schon.** Volle Qualität einmal hochladen. AutoReview spielt HLS/`review_540` ab (leicht),
  der Mixer rendert aus `s3_key_raw` (Master, `iteration_runner.py:149`), Download liefert den Master/Render.
  Kein Proxy+Master-Umweg, #865 PM1 entfällt.
- **E3 = Vorschlag.** Freigegebene/ausgelieferte Teile und ausgelieferte Ads verfallen nie automatisch; nur
  nicht-freigegebene Teile nach 60 Tagen ohne Nutzung. Gewinner weiter per Tap.
- **E4.** Aditor-Kunden (intern geliefert) bekommen den AutoReview-Share-Link `/share/<token>` im Abgabe-Modus
  (gleiche Feedback-Engine, cleaner, Kommentare eingeklappt). `/d/<token>` = Download-Ziel dahinter.
  Mixer-Share `/s/<code>` = nur für externe AutoReview-Kunden, die mit eigenen Agents arbeiten.
