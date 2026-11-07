# Bild im Kommentar + Marken-Referenz

Stand 2026-11-07 · Status: Spec, nichts gebaut · Owner: AutoReview-Agent-Mode-Session

Alan, 07.11.: „die Möglichkeit, ein Bild anzuhängen oder einen Screenshot … dass man den quasi droppt und der dann auch im gleichen Kommentar landet … und eine Art und Weise, das dann in der BrandMD zu cachen und einzupflegen, falls es wichtig für die weiterführende Arbeit an der Brand ist.“

## Zweck

Wer ein Video reviewt, legt ein Referenzbild (Screenshot, Beispiel) direkt in denselben Kommentar: per Drop, Einfügen (⌘V) oder Büroklammer. Editor und Agent bekommen das Bild mit genau diesem Kommentar, dieser Version und diesem Zeitpunkt. Ist das Bild für die Marke dauerhaft wichtig, merkt der Owner es mit einem Klick als Marken-Referenz. Spätere Jobs dieser Marke sehen sie.

## Nicht-Ziele (YAGNI)

- Kein zweiter Speicher. Bilder liegen im bestehenden S3/MinIO-Bucket, Einträge in `comment_attachments`.
- Ein Referenzbild ist Beleg, keine neue Version und kein Liefer-Asset.
- Keine Videos oder PDFs als Anhang. Nur Bilder: png, jpeg, webp und gif, je höchstens 10 MB und höchstens 4 pro Kommentar.
- Kein automatisches Hochstufen. Ein einzelnes Bild bleibt beim Kommentar. Marken-Referenz wird es nur durch den Owner oder durch einen Vorschlag, den er annimmt.
- Keine eigene Wissensdatenbank. Marken-Referenzen sind Regeln im bestehenden Regel-Store des Workers (Brand rules).

## Stand auf `main` (geprüft 07.11.)

| Teil | Befund |
|---|---|
| API | `POST /comments/{id}/attachments` (`routers/comments.py:568`) erzeugt eine presigned PUT-URL und speichert den Eintrag **vor** dem Upload. Es gibt keine Typ- oder Größenprüfung und keine Prüfung, ob der Aufrufer Autor des Kommentars ist. Nur für eingeloggte Nutzer, keine Route für Share-Links oder Gäste. |
| Lesen | Kommentar-Antworten liefern `attachments` mit 1 h gültiger GET-URL (`_build_attachment_response`). |
| Web | `comment-panel.tsx:320`: Büroklammer ohne Handler. `GuestCommentInput` (Share-Seite, auch die Talk+Draw-`FlowView`) kennt keine Anhänge. |
| Agent | `feedback_rounds.feedback_v1` (`services/feedback_rounds.py:155`) gibt Text und Zeichnung aus, keine Anhänge. |
| Marke | Regeln und Vorschläge liegen im Worker (Airtable, `src/store.ts`: `Rule`, `RuleSuggestion`). FreeFrame spricht sie über `review_bridge` an (`/insights/rules*`, `/agent/rules/suggestion`). |

## Entwurf

### P1 – Speichern sicher machen (API)

1. Neue Spalte `comment_attachments.uploaded_at` (Migration `ap05`). Ein Anhang zählt erst, wenn er hochgeladen und bestätigt ist.
2. `POST /comments/{id}/attachments`:
   - lässt nur erlaubte Typen und Größen zu;
   - nur der Autor des Kommentars darf anhängen, oder jemand mit Projektrolle `editor` oder höher;
   - höchstens 4 Anhänge pro Kommentar.
3. `POST /comments/{id}/attachments/{aid}/complete` prüft per `head_object`, ob Größe und Typ stimmen, und setzt dann `uploaded_at`. Ein zweiter Aufruf ändert nichts mehr.
4. Für Gäste gibt es dasselbe unter `POST /share/{token}/comments/{id}/attachments` und `…/complete`. Voraussetzungen:
   - Share-Link mit Kommentarrecht, geprüft wie in `guest_comment` (`validate_share_link_with_session` und `validate_asset_in_share`);
   - nur am eigenen Gastkommentar (`guest_author_id` aus der Session).
5. Gelesen werden nur Anhänge mit `uploaded_at`. Wird der Kommentar soft-gelöscht, verschwinden auch seine Anhänge.

### P2 – Oberfläche (eine Logik, zwei Eingabefelder)

- Ein Hook `useImageAttachments` übernimmt Drop, ⌘V und Auswahl über die Büroklammer, die Vorschau mit Entfernen, den Upload-Fortschritt und die Fehleranzeige pro Bild. Er wird an zwei Stellen eingesetzt:
  - im Eingabefeld der Kommentarleiste (`comment-panel.tsx`), dort bekommt die vorhandene Büroklammer ihren Handler;
  - in `GuestCommentInput` (Share-Seite inklusive Talk+Draw). Dort wird zuerst gebaut, weil Alan dort reviewt.
- Ablauf beim Senden:
  1. Der Kommentar wird mit dem vorhandenen `Idempotency-Key` gespeichert. Ein Retry legt also keinen zweiten an.
  2. Danach werden die Bilder hochgeladen und bestätigt (`complete`).
  3. Der Kommentar zeigt „Sendet…“, bis alle Bilder bestätigt sind. Scheitert ein Bild, steht an diesem Bild „Nicht hochgeladen · Erneut versuchen“. Der Text bleibt erhalten.
- Im Kommentar erscheinen die Bilder als Vorschaubilder. Ein Tipp öffnet sie groß.
- Design: apple-hig, ux-laws, DS v2. Die Drop-Zone bekommt nie eine orange Umrandung. Fokus und Drag-Over erscheinen als neutraler grauer Rand.

### P3 – Zum Editor und zum Agent

- `feedback_v1` bekommt pro Kommentar zusätzlich `attachments: [{attachment_id, file_name, content_type, url}]`.
  - `url` ist 7 Tage gültig, wie `frame_url`. Ein erneuter `get_feedback`-Aufruf liefert eine neue URL. Agents speichern die URL nicht dauerhaft, sondern nur die `attachment_id`.
  - Die Schema-Version bleibt `v1`, weil nur ein Feld dazukommt.
- Der Worker reicht das Feld in `get_feedback` (MCP) unverändert durch. Die Anleitung `docs/agent-playbook.md` bekommt eine Zeile: „`attachments` are reference images for that comment: look at them before you fix.“
- Die bisherige Regel gilt weiter: `ack_feedback` erst, wenn der Fix hochgeladen ist.

### P4 – Für diese Marke merken

- An jedem Bild gibt es für den Owner der Marke die Aktion „Für diese Marke merken“ mit einem optionalen Satz dazu, was das Bild zeigt.
  - FreeFrame kopiert das Bild nach `brand-references/{project_id}/{uuid}`. Löscht jemand den Kommentar, bleibt die Referenz damit erhalten.
  - FreeFrame ruft `POST /insights/rules/reference` auf. `review_bridge` legt im Worker eine aktive Regel an:
    - `kind: "reference"`, `scope: brand`;
    - `ref: <reference-id>`, `what: <Satz>`;
    - `source: {origin: "owner-comment", ref: <comment_id>}` plus `version_id`.
  - Weil der Owner selbst „merken“ gewählt hat, braucht es keine zweite Freigabe.
- Gäste, Editoren und Agents können nur vorschlagen: `suggest_rule` mit `attachment_id`. Der Vorschlag landet unter Brand rules bei „For your approval“.
- So kommen die Referenzen an:
  - In der Liste von Brand rules erscheint die Referenz als Karte mit Bild, Satz und Link zum Kommentar. Entfernen darf nur der Owner.
  - Agents bekommen sie mit Key in `/agent.md` im Abschnitt Markenregeln, mit frischer URL über `GET /agent/references/{id}`. Diese Route prüft, ob die Referenz zum Projekt des Keys gehört. Fremde Marken liefern 404.

## Fertig heißt (maschinell prüfbar)

- [ ] pytest:
  - falscher Typ oder zu groß ergibt 422;
  - ohne `complete` ist der Anhang nicht sichtbar;
  - ein zweites `complete` ändert nichts;
  - ein Gast an einem fremden Kommentar oder mit einem Nur-Lesen-Link ergibt 403;
  - `feedback_v1` enthält `attachments`, und zwar nur hochgeladene;
  - `/agent/references/{id}` liefert für eine fremde Marke 404;
  - ein einzelnes Bild wird nie zur Regel, ohne dass jemand „merken“ wählt oder einen Vorschlag annimmt.
- [ ] vitest:
  - der Hook nimmt Drop, Einfügen und Auswahl an;
  - ein gescheiterter Upload zeigt „Erneut versuchen“, und der Text bleibt erhalten;
  - ein Retry sendet kein zweites POST auf den Kommentar.
- [ ] Playwright bei 390 px und auf dem Desktop:
  - Share-Seite: Screenshot einfügen, senden, neu laden, das Bild hängt am selben Kommentar;
  - Kommentarleiste: dasselbe;
  - Screenshots liegen in `reviews/`.
- [ ] Live nach dem Merge:
  - ein Agent mit Key bekommt das Bild in `get_feedback`;
  - eine gemerkte Referenz erscheint bei einem späteren Job in `/agent.md`.

## Stop & Eskalation

- `head_object` oder MinIO lehnen den CORS-PUT von der Share-Domain ab: Stopp, weil eine Infrastruktur-Änderung nötig ist. Die macht Alan.
- Der Regel-Store im Worker (Airtable) kann `kind: "reference"` nicht ablegen: Stopp, Schema-Entscheidung.
- Eine Share-Session lässt sich keinem Gastautor zuordnen: Gastanhänge bleiben gesperrt, eingeloggt geht es weiter.

## Offene Frage an Alan (eine)

Soll die **automatische Prüfung** gemerkte Referenzbilder beim Review mit ansehen, also das Video mit „so soll es aussehen“ vergleichen? Das kostet pro Review etwas mehr Vision-Tokens. Empfehlung: ja, nur für gemerkte Referenzen und höchstens 3 pro Marke.

## Doctrine-Gate

- [x] M1 Spec-first: Zweck und Nicht-Ziele explizit.
- [x] M2 Start simple: bestehende Tabelle, bestehender Bucket, bestehender Regel-Store; kein neuer Dienst.
- [x] M3 Loop-first: „Fertig“ als Tests, Stop-Fälle benannt.
- [x] 1 State: Wahrheit liegt in FreeFrame `comment_attachments` (Bild) und im Regel-Store des Workers (Referenz). Signierte URLs sind nur abgeleitet.
- [x] 2 SoC: Prüfungen von Typ und Größe und der Vertrag von `feedback_v1` als reine Funktionen.
- [x] 3 Idempotenz: `Idempotency-Key` am Kommentar, `complete` mehrfach ohne Schaden, `remember` wird über `(attachment_id)` dedupliziert.
- [x] 4 Coupling: `feedback.v1` erweitert sich nur additiv; die Referenz-ID ist stabil, URLs nie.
- [x] 6 Fehlerklassen: Upload gescheitert (Retry pro Bild), Typ oder Größe (422, kein Retry), Rechte (403, Stopp), Regel-Store nicht erreichbar (503, Anhang bleibt, merken später erneut).
- [x] 7 Defensive: Ein gescheitertes Bild verliert nie den Kommentar.
- [x] Tests: reine Funktionen plus pytest gegen ein Wegwerf-Postgres; kein voller Stack nötig.
