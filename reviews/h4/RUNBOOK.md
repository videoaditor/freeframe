# H4 — Wiederholung, Bereitstellung und Backout

Status 07.10.2026, Asia/Tokyo: **Integrationsabnahme ausstehend. Nicht ausgeführt.**
H4 ändert keine Produktionsdatei. Seine Evidenz-/Test-PRs benötigen keinen Produktivdeploy.
Die folgende Bereitstellung betrifft erst ein späteres, konkret freigegebenes Paket aus
H1/H2/H3 und der separat abgenommenen Engine.

## 1. Voraussetzungen und Identität

| Voraussetzung | Erforderlicher Beleg |
| --- | --- |
| Lokale Infrastruktur | Docker wieder erreichbar, ausreichend freier Speicher; Wiederherstellung durch zuständigen Operator, keine fremden Volumes/Stacks löschen |
| Tatsächlicher Live-Stand | FreeFrame API/Web/Transcoder-Image-Digests und Quell-SHAs; Worker Deployment-/Version-ID samt Trafficanteilen; Konfiguration nur Namen/Präsenz, keine Secretwerte |
| Bestehende Konten | Freigegebene minimale, bereinigte Identitäts-/Rollen-Fixture bestehender Owner/Team- und zweiter Tenant-Identität; keine neuen Live-Konten, Rollen oder Quotas |
| Neue Features | Verifizierte PR-Head-SHAs für H1/H2/H3; H1A-Vertrag durch Owner integriert; keine fremden Dateien oder Worktrees übernehmen |
| Engine | Owner bestätigt Plan-/Review-/Publikationsvertrag und die separate Qualifikation von PR150/79/51; keine Modellqualität aus injizierter Antwort ableiten |

Den dokumentierten Credential-Pfad `~/.config/aditor/deploy.env` gab es beim H4-Lauf nicht.
Keinen Ersatzaccount anlegen, keine Secrets rotieren und keine Rolle erweitern, um diesen
Inventarblocker zu umgehen. Bestehenden Ops-Zugangsweg bestätigen lassen.

## 2. Eigenen lokalen Stack bereitstellen

Der Operator führt die folgenden Befehle aus; die Datei ist eine **Anleitung, kein Deploy-Beleg**.
Root unten bei einem anderen Checkout einmal auf dessen absoluten Pfad setzen.

```bash
H4_ROOT="/Users/alansimon/.codex/worktrees/autoreview-h4-acceptance/freeframe"
H4_WORKER="/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H4/feedback-agent"
export PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH"
docker info
docker compose -f "$H4_ROOT/reviews/h4/compose.json" config --quiet
docker build -t freeframe-h4-api:20261007 -f "$H4_ROOT/apps/api/Dockerfile" "$H4_ROOT"
docker compose -f "$H4_ROOT/reviews/h4/compose.json" up -d
docker compose -f "$H4_ROOT/reviews/h4/compose.json" ps
```

Projektname `autoreview-h4`; eigene Postgres-/MinIO-Volumes. API 18044, Web 13044,
Testbrücke 18744, Postgres 55444, Redis 16344, MinIO 19044. Alle veröffentlichten Dockerports
sind an 127.0.0.1 gebunden. Keine vorhandene Compose-Datei überlagern, kein globales prune/down.
`compose.json` wurde offline validiert; Image-Build und Startup sind noch nicht bestätigt.
Der API-Start führt die **bestehenden** Alembic-Migrationen aus. H4 enthält keine Migration.

Die existierenden autorisierten Identitäten nur als bereinigte lokale Fixture herstellen;
echte Secrets, Medien und Kundentexte bleiben draußen. Login-Konfiguration ausdrücklich
dokumentieren: diese minimale Stackdatei hat Passwortlogin an und keinen Mailworker.
Sie beweist daher **keinen** produktionsgleichen Magic-Code-Login. Für dessen Abnahme einen
eigenen lokalen Mail-Sink + Email-Worker über den bestehenden Auth-Weg ergänzen, ohne externen
Mailversand oder Passwort-/Rollenänderung. Diese zusätzliche Konfiguration ist noch offen.

Die Testbrücke aus dem H4-Worker-Branch in einem separaten Terminal starten:

```bash
cd "/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H4/feedback-agent"
H4_BRIDGE=1 H4_EVIDENCE="/Users/alansimon/Downloads/autoreview-handoffs-2026-10-05/sessions/H4/bridge-state.json" \
  npx vitest run test/h4-standalone.integration.test.ts --maxWorkers=1 --minWorkers=1
```

Sie meldet `H4_BRIDGE_SMOKE_PASSED`, bleibt dann bis zum lokalen Stop stehen. Das Modell und
Trello sind injiziert, API/Storage dürfen ausschließlich die lokalen H4-Ports erreichen.
Die Brücke hält KV im Speicher; ihr Neustart ist **kein** dauerhafter Worker-KV-Nachweis.
Produktions-CORS wird nur am lokalen Testserver auf den H4-Web-Origin projiziert.

Frontend mit den lokalen URLs **bauen**, dann starten (Build-Variablen sind eingebrannt):

```bash
cd "/Users/alansimon/.codex/worktrees/autoreview-h4-acceptance/freeframe"
export PATH="/Users/alansimon/.nvm/versions/node/v22.22.3/bin:$PATH"
NEXT_PUBLIC_API_URL="http://localhost:18044" NEXT_PUBLIC_REVIEW_GATE_URL="http://localhost:18744" pnpm --filter web build
pnpm --filter web start --hostname 127.0.0.1 --port 13044
```

Die letzte Zeile läuft bis Ctrl-C; kein Nutzerwert muss eingesetzt werden.

## 3. Abnahme durchführen und belegen

`journeys.json` enthält beide vollständigen API-Abfolgen plus Fehler-/Replay-/Tenant-Schritte.
`matrix.json` bleibt maßgeblich: Zeilen erst nach tatsächlicher Ausführung von pending ändern.
Je Übergang IDs, HTTP-Ergebnis, UTC-Zeit, Quell-Commit und Evidenzpfad sichern. Keine Tokens,
signierten Medien-URLs oder Secrets in öffentliche Logs schreiben.

| Teil | Pflichtbeleg |
| --- | --- |
| Kunde | Clean-Browser-Login ohne Whop, `/auth/me`, richtiger Workspace, Request + echter multipart PUT, `submitted_at`, reale FFmpeg-Ausgaben, ready-hook + Cron, gespeicherte exakte Kommentarversion |
| Intern | Synthetische Karte, autorisierte Workspace-Auswahl, kein Ordner durch Paste, richtige Folder-/Share-Bindung, member Upload, reales Transcoding und gespeichertes aktuelles Feedback |
| Unterbrechung | V2 behält Asset-ID; V1-Pass zählt nicht; Reload; nach Read-back bestätigter Retry; keine zweite Version/Publikation; Provider-/Netzwerkfehler sichtbar; Tenant B abgewehrt |
| Browser | Synthetischer Player, Kommentarzeit anklicken → tatsächlich seek, Video/Kommentare gleichzeitig mobil; Desktop/Mobile, Light/Dark, Reduced Motion, 200% Zoom als getrennte Belege |
| Neue Features | H1 gleicher Plan/Hash für V1/V2, H2 nach API-Reload korrekt und nicht spoofbar, H3 echte Phasen/Zeiten; Engine-/Modellqualität separat beim Owner |

Opt-in Postgres-Checks zusätzlich in **diesem** Stack ausführen:

```bash
H4_ROOT="/Users/alansimon/.codex/worktrees/autoreview-h4-acceptance/freeframe"
docker compose -f "$H4_ROOT/reviews/h4/compose.json" exec \
  -e ITERATIONS_TEST_DATABASE_URL="postgresql://h4:h4@postgres:5432/h4" \
  api python -m pytest apps/api/tests/test_request_editor_postgres.py -v
```

Diese Tests benutzen eigene kurzlebige Schemas, aber mocken Storage/Reviewer. Sie ersetzen
den tatsächlichen Medienlauf nicht. Für dauerhaften Worker-Restart-Nachweis zusätzlich
isoliertes persistentes KV bereitstellen; nicht die speicherbasierte Brücke als Pass zählen.
Nach höchstens drei ernsthaften Versuchen derselben Ursache kleinsten Repro speichern und stoppen.

## 4. Spätere Bereitstellung — erst nach konkreter Freigabe

| Reihenfolge | Aktion und Abbruchbedingung |
| --- | --- |
| Vorher | Autorisierte Zielumgebung, exakte kombinierte SHAs/Images und sämtliche passed-Integrationszeilen feststellen; aktuelle Images, Worker-Version/Traffic und DB-Sicherung auf Wiederherstellbarkeit prüfen |
| Rehearsal | Migrationen gegen isolierten DB-Restore; n8n-Spaltenvertrag und begrenzte Leserechte prüfen; neuen Stack vollständig durchlaufen |
| Freigabe | Konkretes geprüftes Paket an Alan geben; Ausführungsfreigabe separat einholen; keine Freigabe aus diesem Report ableiten |
| Ausrollen | Zuständiger Operator verwendet vorhandene Pipeline mit unveränderlichen Versionen; Worker-Merge auf main deployt automatisch — keinen Merge als harmlose Dokuaktion behandeln |
| Nachher | Genau einen autorisierten synthetischen Lauf je Weg mit aktuellen Asset-/Version-/Kommentar-IDs belegen; bei Auth-, Tenant-, Versions- oder Publikationsfehler Backout; erst diese Belege erlauben live_verified |

## 5. Backout und lokales Aufräumen

Bei späterer Produktionsstörung die **vorher erfassten** API/Web/Worker-Versionen über die
bestehende Ops-Pipeline zurückstellen; Worker-Traffic auf vorherige Version. Kein neues Tag,
kein stable/latest-Verschieben. Verbundene DB-/KV-Daten werden durch Code-Rollback nicht
zurückgerollt: keine blinde Alembic-Downgrade und kein Löschen neuer Requests/Kommentare.
Bei additiven Migrationen alten kompatiblen Code nutzen; inkompatible Fälle verlangen die
vorher geprobte Restore-/Recovery-Entscheidung des Owners. Keine automatische Wiederholung
unklarer Upload-/Publikationsausgänge. Danach Auth, beide Wege und exakte Versionen erneut lesen.

Nur die eigenen lokalen Prozesse stoppen. Brücke: `POST http://localhost:18744/__h4/stop`.
Webterminal: Ctrl-C. H4-Container bei Bedarf mit exakt dieser Compose-Datei `stop` stoppen;
Volumen behalten, bis Evidenz gesichert ist. Kein `down -v`, kein fremder Stack-Neustart.
Beim dokumentierten H4-Lauf startete der Docker-Stack nicht; es wurde kein fremder Dienst beendet.
