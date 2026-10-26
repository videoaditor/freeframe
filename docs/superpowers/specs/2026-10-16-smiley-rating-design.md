# Smiley-Bewertung nach dem Video — Design-Spec

**Repo:** freeframe (feedback.aditor.ai) · **Stand:** 2026-10-17 · **Status:** ready für Nachtschicht
**Ready-Item:** ROADMAP.md → „Smiley-Bewertung nach dem Video"

## Purpose

Nachdem ein Kunde eine Lieferung angeschaut hat, tippt er mit **einem Tap** einen von vier Smileys
(😀 🙂 🙁 😠), optional mit einem kurzen Grund. Das ist für Aditor sehr wichtig — und muss für den
Kunden **reibungslos** sein: ein Tap, kein Formular, nie blockierend.

Die Bewertung ist **rein intern**. Der Editor sieht keine einzelne Bewertung. Sie existiert, um eine
bessere Datenbank aufzubauen: jede Bewertung landet in einem Log, korreliert mit Lieferung, Editor,
Kunden-Account, Brand und Trello-Card, abfragbar pro Editor, pro Brand, pro Lieferung.

## Non-Goals / YAGNI

- Kein Dashboard, keine Charts. Ein Admin-Export (JSON/CSV) reicht — Auswertung macht Ops.
- Keine Anzeige für Editoren, auch nicht aggregiert. Kein Feld in Asset-, Share-, Kommentar- oder
  `/insights/editors`-Antworten.
- Kein Versand an Hub-Events, Brand Loop (review.aditor.ai), Trust Battery, Slack oder n8n. (Später
  möglich, eigenes Item.)
- Kein Pflichtfeld, kein Identitäts-Formular, kein Modal, kein `beforeunload`-Dialog.
- Keine neue Editor-, Brand- oder Card-Zuordnung — alles wird aus bestehenden Tabellen gelesen.

## Kunden-Erlebnis (die Taste-Regeln)

1. **Wann:** Der Kunde verlässt ein Video *innerhalb der App*, nachdem er es **≥ 10 s tatsächlich
   abgespielt** hat (Summe der Wiedergabezeit, nicht Position). „Verlassen" = Viewer schließen
   (`folder-share-viewer` → `setSelectedAsset(null)`), zu anderem Asset/anderer Version wechseln,
   Zurück auf der Asset-Seite, oder Video läuft bis zum Ende (`ended`). Nie beim Tab-Schließen.
2. **Wie:** Eine schmale, nicht-modale Leiste unten (Toast-Stil), Text „Wie gefällt dir das Video?"
   + vier Smileys als Buttons (≥ 44 × 44 px, Abstand ≥ 8 px). Kein Overlay, kein Fokus-Trap, die
   Seite bleibt voll bedienbar.
3. **Ein Tap = gespeichert.** Optimistisch: sofort „Danke!" in der Leiste; darunter klappt ein
   einzeiliges Feld „Magst du kurz sagen, warum? (optional)" auf. Enter/Senden ergänzt den Grund,
   Ignorieren ist völlig okay.
4. **Verschwindet von selbst:** ohne Tap nach 8 s; nach Tap 8 s nach der letzten Eingabe. Ein ✕ zum
   sofortigen Schließen. Weggeklickt/ignoriert = für diese Version nicht nochmal fragen.
5. **1× pro Version** und Rater. Neue Version (v2) = neue Frage.
6. **Nie fragen:** Aditor-Staff (siehe unten), Bilder/Audio/Carousels, Videos < 10 s Wiedergabe,
   bereits beantwortete oder weggeklickte Version.
7. **Fehler sind unsichtbar:** API down → einmal still im Hintergrund wiederholen, dann verwerfen.
   Nie ein Fehler-Toast, nie blockiert Wiedergabe, Kommentar, Freigabe oder Download.
8. Copy auf Deutsch, wenn die Share-Seite Deutsch ist; sonst Englisch („How did you like this
   video?" / „Want to say why? (optional)" / „Thanks!").

**Wer ist Kunde?**
- Share-Seite (`/share/[token]`, Gast): immer anzeigen. Der Server verwirft still, wenn die
  gespeicherte Gast-E-Mail Staff ist.
- App-Asset-Seite (`/projects/[id]/assets/[assetId]`, eingeloggt): nur anzeigen, wenn die eigene
  `ProjectMember.role` auf dem Projekt `reviewer` oder `viewer` ist und die E-Mail nicht auf
  `@aditor.ai` endet. Owner/Editor (= unsere Editoren) sehen die Leiste nie.
- Server-seitig zusätzlich immer `brand_loop.is_aditor_staff(email)` → bei Staff `204` ohne Zeile.

## Datenmodell — eine neue Tabelle, alles andere wird gelesen

**Warum keine bestehende Tabelle:** `product_feedback` ist Feedback über das *Tool* (bug/idea),
`activity_logs` ist der Nutzer-Feed (kein Gast, keine Version, nicht pro Editor indexierbar),
`request_uploads` ist der Hand-in-Fakt. Eine Bewertung ist ein eigener Fakt — aber jede
Korrelations-Spalte kommt aus diesen bestehenden Tabellen, es gibt keine Parallel-Zuordnung.

Tabelle **`delivery_ratings`** (Model `apps/api/models/delivery_rating.py`, Alembic-Migration mit
up/down; `down_revision` = aktueller `alembic heads`):

| Spalte | Typ | Quelle |
|---|---|---|
| `id` | UUID PK | |
| `asset_id` | UUID FK `assets.id`, not null, index | Lieferung |
| `asset_version_id` | UUID FK `asset_versions.id`, not null | Lieferung (Version) |
| `version_number` | int, not null | `asset_versions.version_number` (Snapshot) |
| `asset_name` | varchar(255) | `assets.name` (Snapshot, für lesbaren Export) |
| `project_id` | UUID FK `projects.id`, not null | Workspace des Kunden |
| `brand_slug` | varchar(120), nullable, index | `projects.autoreview_brand_slug` (Snapshot) |
| `folder_id` | UUID FK `folders.id`, nullable | `assets.folder_id` |
| `upload_request_id` | UUID FK `upload_requests.id`, nullable | Hand-in-Request des Folders |
| `trello_card_id` | varchar(24), nullable, index | siehe Auflösung unten |
| `editor_email` | varchar(255), nullable, index | siehe Auflösung unten |
| `editor_name` | varchar(255), nullable | siehe Auflösung unten |
| `editor_source` | varchar(20), nullable | `request_upload` · `handin` · `version_creator` |
| `rater_key` | varchar(80), not null | `user:<id>` · `guest:<id>` · `anon:<uuid>` |
| `rater_user_id` | UUID FK `users.id`, nullable | eingeloggter Kunde |
| `rater_guest_id` | UUID FK `guest_users.id`, nullable | Gast mit bekannter E-Mail |
| `rater_email` | varchar(255), nullable | Snapshot der E-Mail |
| `share_link_id` | UUID FK `share_links.id`, nullable | über welchen Link geschaut |
| `surface` | varchar(8), not null | `share` · `app` |
| `score` | smallint, not null, CHECK 1–4 | 😠=1 · 🙁=2 · 🙂=3 · 😀=4 |
| `reason` | text, nullable, ≤ 500 Zeichen | optionaler Grund |
| `watched_seconds` | int, not null | gemessene Wiedergabezeit |
| `created_at` / `updated_at` | timestamptz | `created_at` = Zeitstempel der Bewertung |

- **Dedup:** `UNIQUE (asset_version_id, rater_key)`. Zweiter POST = Upsert (Smiley ändern, Grund
  ergänzen), `created_at` bleibt, `updated_at` wandert.
- **Indizes:** `(editor_email, created_at)`, `(brand_slug, created_at)`, `asset_id`, `trello_card_id`.
- **Snapshots, bewusst:** Editor, Brand und Card werden beim Schreiben eingefroren. Wird ein Folder
  später umgehängt, bleibt wahr, wem die Lieferung *zum Zeitpunkt der Bewertung* gehörte.

### Auflösung (pure Funktionen in `apps/api/services/delivery_ratings.py`)

**Editor** (`resolve_delivery_owner(db, asset, version)`), erster Treffer gewinnt:
1. `request_uploads` mit `asset_id = asset.id AND version_number = version.version_number` →
   `uploader_email`/`uploader_name`, Source `request_upload` (genauester Fakt: wer genau diese
   Version eingereicht hat).
2. Hand-in-Request des Folders (`hub_events._handin_request_for_asset`) → `last_uploader_email`/
   `last_uploader_name`, Source `handin`.
3. `asset_versions.created_by` → `users.email`/`name` (wie `hub_events._responsible_editor_email`),
   Source `version_creator`.
4. Sonst alles `null` — die Bewertung wird trotzdem gespeichert.

Die hub_events-Helfer importieren, nicht kopieren. hub_events selbst bleibt unverändert.

**Trello-Card** (`resolve_trello_card_id(db, asset, request)`), erster Treffer gewinnt:
1. `checklist_bindings.trello_card_id` per `request_id`, sonst per `folder_id`.
2. Regex `trello\.com/c/([A-Za-z0-9]+)` auf `folders.description` (dieselbe Regex wie der
   View `n8n_feedback_events`).
3. Dieselbe Regex auf `upload_requests.iteration_state.internal_handin.card_url`.
4. Sonst `null`.

**Rater:** eingeloggt → `user:<users.id>`. Gast mit gespeicherter Identität
(`localStorage.ff_guest_identity`, E-Mail passt auf `guest_users.email`) → `guest:<guest_users.id>`.
Gast ohne Identität → `anon:<uuid>` (Client erzeugt einmal, `localStorage.ff_rater_key`). Nie ein
Identitäts-Formular nur für die Bewertung.

## API

| Methode + Pfad | Auth | Body / Query | Antwort |
|---|---|---|---|
| `POST /share/{token}/rating` | Share-Token (muss das Asset freigeben, wie `/share/{token}/comment`) | `asset_id, version_id, score, reason?, watched_seconds, rater_key?, guest_email?` | `204` |
| `POST /assets/{asset_id}/versions/{version_id}/rating` | eingeloggt + View-Zugriff aufs Asset | `score, reason?, watched_seconds` | `204` |
| `GET /admin/delivery-ratings` | **nur `is_superadmin`**, sonst `403` | `editor_email?, brand_slug?, asset_id?, asset_version_id?, trello_card_id?, project_id?, since?, until?, format=json\|csv, limit≤10000` (default 1000), sortiert `created_at desc` | JSON-Liste oder CSV mit allen Spalten oben |

- POST-Antworten tragen nie Daten (kein Score, kein Schnitt). Validierung: `score ∈ 1..4`,
  `watched_seconds ≥ 10`, Version gehört zum Asset, Asset ist ein Video — sonst `422`.
- Staff (`is_aditor_staff`) → `204` ohne Zeile. Rate-Limit wie bei Gast-Kommentaren.
- Der Admin-Export liegt in `routers/admin.py` neben den anderen Superadmin-Routen.

**Auswertungs-Queries** (für Ops, so im Export-Docstring dokumentieren):

```sql
-- pro Editor
SELECT editor_email, count(*), round(avg(score),2), count(*) FILTER (WHERE score<=2) AS schlecht
FROM delivery_ratings GROUP BY editor_email ORDER BY 3;
-- pro Brand
SELECT brand_slug, count(*), round(avg(score),2) FROM delivery_ratings GROUP BY brand_slug;
-- pro Lieferung
SELECT asset_id, version_number, trello_card_id, score, reason, rater_email, created_at
FROM delivery_ratings WHERE asset_id = :asset_id ORDER BY version_number, created_at;
```

## Frontend

- Eine Komponente `components/review/rating-prompt.tsx` (Leiste + Logik), ein Hook
  `useWatchedSeconds(videoEl)` (summiert echte Wiedergabe über `timeupdate`/`play`/`pause`).
- Eingebaut in `components/share/folder-share-viewer.tsx` (Gast) und
  `app/(dashboard)/projects/[id]/assets/[assetId]/page.tsx` (eingeloggt), am bestehenden
  `VideoPlayer` aus `components/review/video-player.tsx`.
- „Schon gefragt"-Merker: `localStorage.ff_rated:<version_id>` (gesetzt bei Tap *und* bei
  Wegklicken/Ignorieren). Alle `localStorage`-Zugriffe in try/catch — leer/blockiert = einfach fragen.
- Anfrage fire-and-forget, nie `await` vor UI-Feedback.

## Done (maschinell prüfbar)

1. `pytest` grün, inkl. neuer Tests:
   - Resolver: jede Editor-Stufe (request_upload → handin → version_creator → null) und jede
     Card-Stufe (binding → folder-description → card_url → null) als pure Tests.
   - Share-POST speichert Zeile mit allen Korrelationsspalten (asset, version, project, brand_slug,
     folder, request, trello_card_id, editor_email/name/source, rater, share_link, score, reason,
     watched_seconds, created_at).
   - Zweiter POST derselben Version + Rater → genau 1 Zeile, Score/Grund aktualisiert.
   - Staff-E-Mail → `204`, 0 Zeilen. `score=5`, `watched_seconds=5`, fremdes Asset → `422`/`404`.
   - `GET /admin/delivery-ratings`: Superadmin → Daten, Filter `editor_email`, `brand_slug`,
     `asset_id` wirken, `format=csv` liefert Header + Zeilen; Nicht-Superadmin (auch Projekt-Owner/
     Editor) → `403`.
   - Internal-only: Asset-, Share- und `/insights/editors`-Antworten enthalten kein Rating-Feld;
     `hub_events._post` und `brand_loop.post_comment` werden beim Rating nie aufgerufen.
2. Migration up → down → up gegen lokale Postgres (Docker) ohne Fehler.
3. Web: `build`, `test`, `tsc`, `lint` grün. Komponententests: Leiste erscheint erst ab 10 s
   Wiedergabe beim Verlassen; 1 Tap feuert genau 1 POST und zeigt „Danke!"; Leiste verschwindet nach
   8 s; zweites Verlassen derselben Version zeigt nichts; Owner/Editor-Rolle zeigt nichts;
   fehlschlagender POST zeigt keinen Fehler.
4. Screenshots nach `reviews/assets/` (headless): Leiste Desktop + 390 px mobil, Zustand nach Tap
   mit Grund-Feld, hell + dunkel.
5. PR offen gegen main, **nicht gemergt**.

## Stop & Eskalation

- Alembic hat mehrere Heads → Merge-Migration nach Hausmuster (`*_merge_*.py`), nicht raten; geht
  das nicht sauber → stoppen, als Frage in den PR.
- `VideoPlayer` gibt kein Video-Element/keine Events nach außen → minimaler Callback-Prop
  (`onWatchedSeconds`), kein Umbau des Players. Größerer Umbau nötig → stoppen.
- Projekt-Rolle ist auf der Asset-Seite nicht verfügbar → Leiste dort weglassen, nur Share-Seite
  bauen, im PR melden.
- Keine Migration gegen eine nicht-lokale Datenbank, kein Deploy (NIGHTSHIFT §3).

## Doctrine-Gate

- [x] M1 Spec-first: Purpose + Non-Goals explizit.
- [x] M2 Start simple: eine Tabelle, zwei POSTs, ein Export. Kein Dashboard.
- [x] M3 Loop-first: Done maschinell prüfbar, Stop & Eskalation explizit.
- [x] 1 State: `delivery_ratings` ist Single Source; Korrelation aus bestehenden Tabellen gesnapshottet.
- [x] 2 Separation: Resolver als pure Funktionen in `services/delivery_ratings.py`, isoliert getestet.
- [x] 3 Idempotenz: `UNIQUE (asset_version_id, rater_key)`, POST = Upsert.
- [x] 4 Coupling: Export-Spalten = Tabellen-Spalten oben; keine externen Konsumenten.
- [x] 5 Context: ein Item, klein.
- [x] 6 Error-Taxonomie: Validierung → 422; Staff → 204 still; API down → Client verwirft still.
- [x] 7 Defensive: Bewertung blockiert nie Wiedergabe/Kommentar; fehlende Korrelation = `null`, nie Abbruch.
- [x] F1: Spec geschärft, kein Modell im Spiel.
- [x] Tests: Resolver + Endpunkte ohne vollen Stack.
