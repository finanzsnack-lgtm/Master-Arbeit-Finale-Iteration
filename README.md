# Reisebot-Prototyp

Software-Prototyp zur Masterarbeit „Reiseplanung mit generativer KI: Entwicklung eines
Software-Prototyps unter besonderer Berücksichtigung der Anbindung von Simulations- und
Optimierungsmodellen" (Nick Pöppler, Wirtschaftsinformatik, Universität Hildesheim).

Ein Sprachmodell führt den Dialog mit dem Nutzer, alle Fakten stammen aus realen Schnittstellen,
und die eigentliche Reise wird deterministisch über Optimierungsverfahren und einen
Monte-Carlo-Härtetest erstellt.

| Dokument | Inhalt |
|---|---|
| [`ARCHITEKTUR.md`](ARCHITEKTUR.md) | Aktueller Stand der Architektur: Grundprinzipien, Dialogsteuerung, Fragekatalog, Optimierung, Simulation, Oberfläche, Schnittstellen. |
| [`ENTSCHEIDUNGSLOG.md`](ENTSCHEIDUNGSLOG.md) | Chronologisches Was und Warum jeder Design-Entscheidung, am Ende die offenen Punkte. |
| [`doku/`](doku/README.md) | Dieselben Entscheidungen nach Entwicklungsstationen sortiert, teils mit eingefrorenem Code-Stand. |
| [`evaluierung/`](evaluierung/README.md) | Unabhängige Korrektheitsprüfung von Optimierung 1 gegen Google OR-Tools und Brute-Force. |

## Installation

Voraussetzungen:

- Python 3.10 oder neuer (entwickelt mit Python 3.12 unter Windows).
- Claude Code, installiert und mit einem Claude-Konto angemeldet (Installation:
  https://docs.claude.com/en/docs/claude-code/setup, danach einmal `claude` im Terminal starten und
  anmelden). Das Claude Agent SDK nutzt diese Anmeldung, ein eigener `ANTHROPIC_API_KEY` ist nicht
  nötig. Das in `LLM_MODELL` eingetragene Modell muss im Abonnement verfügbar sein.
- Für echte Daten ein Schlüssel der Google Maps Platform mit aktivierter Abrechnung. Im Projekt des
  Schlüssels müssen Places API, Directions API, Distance Matrix API, Geocoding API und Routes API
  aktiviert sein (für den optionalen Sprachmodus zusätzlich Cloud Text-to-Speech und
  Speech-to-Text). Places, Directions und Distance Matrix nutzt der Prototyp in der klassischen
  Variante; Google führt diese seit dem 1. März 2025 als Legacy, sie sind in neu angelegten
  Cloud-Projekten nicht verfügbar, in bestehenden Projekten aber weiter nutzbar
  (https://developers.google.com/maps/legacy).
- Optional: ein Mailjet-Konto für den Versand des Reiseplans per Mail und `cloudflared` für die
  Freigabe an Tester (siehe unten).

Einrichtung im Projektordner (Windows; unter macOS und Linux wird die Umgebung mit
`source .venv/bin/activate` aktiviert und `.env.example` mit `cp` kopiert):

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

In der `.env` den Schlüssel bei `GOOGLE_MAPS_API_KEY` eintragen und `MOCK_MODE=false` setzen.
Solange `MOCK_MODE=true` gilt, arbeitet der Prototyp mit den Beispieldaten aus
`src/api/mock_data.py`; das Gespräch führt auch dann Claude. Ohne Mailjet-Werte wird der Reiseplan
nur als Datei in `ergebnisse/` gespeichert. Alle Befehle werden im Projektordner ausgeführt, weil die
Module als `src.…` importiert werden. `python -m pytest` prüft die Installation ohne Schlüssel und
ohne LLM-Kosten.

## Ausführen

```
python chat.py                        # Dialog in der Konsole (Tastatur oder Mikrofon, siehe .env)
uvicorn webapp:app                    # derselbe Dialog als Browser-Oberfläche (ohne --reload, siehe unten)
python pruefe_planung.py <name>       # nur die Planung testen, ohne Dialog und ohne LLM;
                                      # <name> = Dateiname aus planungs_testfaelle/ ohne .json
python -m pytest                      # automatisierte Tests, deterministisch und ohne LLM-Kosten
```

Voraussetzungen und Einrichtung siehe Abschnitt Installation.

### Browser-Oberfläche

`uvicorn webapp:app` startet einen lokalen Server unter http://127.0.0.1:8000/ mit demselben
Dialog wie `chat.py`, angebunden über WebSocket. Während des Gesprächs steht neben dem Chat
eine Galerie mit wechselnden Stimmungsbildern; mit dem fertigen Plan füllt der Reiseplan die Seite,
und der Chat lässt sich über einen Knopf als Panel ein- und ausblenden. Der Reiseplan besteht aus Karten mit Foto, Kurzbeschreibung und
Google-Maps-Link. Fotos werden serverseitig geladen, der API-Schlüssel erreicht den Browser nie. Im
Mock-Modus erscheinen die Karten ohne Foto. Details siehe `ARCHITEKTUR.md`, Abschnitt 8.

Der Server wird bewusst ohne `--reload` gestartet. Unter Windows wechselt Uvicorns Reload-Modus die
Event-Loop auf eine Variante, die keine Subprozesse starten kann. Das Claude Agent SDK startet beim
Verbindungsaufbau aber die Claude-Code-CLI als Subprozess und bräche mit `NotImplementedError` ab.
Nach Codeänderungen wird der Server daher manuell neu gestartet.

### Reisebot für Tester freigeben

Tester in anderen Netzwerken können die Browser-Oberfläche über einen einzigen Link nutzen, ohne
Installation und ohne Passworteingabe. Der Reisebot läuft dabei weiterhin auf dem eigenen Rechner;
ein Cloudflare Quick Tunnel (kostenlos, ohne Konto, mit HTTPS) leitet die Anfragen nur weiter.

1. Einmalig `cloudflared` installieren: `winget install Cloudflare.cloudflared`.
2. `starte_extern.bat` per Doppelklick starten. Das Skript startet die Webapp, öffnet den Tunnel
   und zeigt den fertigen Link `https://….trycloudflare.com/?zugang=…` an (zusätzlich in der
   Zwischenablage).
3. Den Link an die Tester weitergeben. Beim ersten Aufruf merkt sich der Browser den Zugang in
   einem Cookie, der Code verschwindet aus der Adresszeile.
4. Das Fenster während der Tests offen lassen; `Strg+C` beendet Tunnel und Webapp.

Hinweise:
- Der Rechner muss eingeschaltet bleiben und mit dem Internet verbunden sein.
- Adresse und Zugangscode ändern sich bei jedem Start; alte Links funktionieren danach nicht mehr.
  Ein in der `.env` eingetragenes `ZUGANGSTOKEN` hält den Code fest, die Adresse ändert sich
  trotzdem (und der lokale Aufruf über `uvicorn` erfordert dann ebenfalls `/?zugang=…`).
- Ohne gültigen Link erscheint nur „Kein Zugang“; es startet keine Sitzung.
- Jedes Gespräch verursacht Kosten (Claude-Kontingent sowie Google-Maps-Anfragen, sofern nicht im
  Mock-Modus). Den Link nur an Tester weitergeben.
- Mehrere Tester können gleichzeitig arbeiten, jede Verbindung erhält eine eigene Sitzung.
  API-Abrufe, Planung und Foto-Download laufen im Hintergrund, eine laufende Planung hält die
  Gespräche anderer Tester nicht an. Alle Sitzungen nutzen dasselbe Claude-Kontingent.

## Verzeichnisstruktur

| Pfad | Inhalt |
|---|---|
| `chat.py` | Einstiegspunkt für den Dialog in der Konsole. |
| `webapp.py` | Einstiegspunkt für die Browser-Oberfläche (FastAPI und WebSocket). |
| `starte_extern.bat`, `starte_extern.py` | Freigabe der Browser-Oberfläche für Tester über einen Cloudflare Quick Tunnel mit Zugangstoken. |
| `static/index.html` | Chat-Oberfläche und Reiseplan-Karten als eine abhängigkeitsfreie HTML-Datei. |
| `static/img/` | Bot-Avatar (`avatar.svg`, eigene Grafik) und lizenzfreie Unsplash-Fotos für Hin- und Rückreise (`bahn.jpg`, `auto.jpg`, `bus.jpg`). |
| `src/fragekatalog/` | Fragekatalog, Datenmodell, Regelwerk-Prompt und Werkzeuge des LLM-Agenten. |
| `src/api/` | Anbindung von Google Maps Platform und OpenStreetMap Overpass, jeweils mit Mock-Variante. |
| `src/datenaufbereitung/` | POI-Sammlung, Scoring, harte Ausschlüsse und Aufbereitung für die Optimierung. |
| `src/optimierung/` | Optimierung 1 (TOPTW/ILS), Optimierung 2 (Verkehrsmittelwahl), Emissionsfaktoren, Monte-Carlo-Härtetest, Kostenschätzung. |
| `src/ausgabe/` | Reiseplan als Text, HTML-Mail und Kartendaten, Foto-Download, Debug-Ausgabe. |
| `src/audio/` | Ein- und Ausgabekanäle für Konsole und Sprache; der Web-Kanal liegt in `webapp.py`. |
| `src/pipeline.py` | Gesamtablauf der Planung von der POI-Suche bis zum fertigen Plan. |
| `pruefe_planung.py` | Testet nur die deterministische Planung mit einer Anfrage aus `planungs_testfaelle/*.json`, ohne Dialog. |
| `pruefe_algorithmus.py` | Kleines, von Hand nachrechenbares Beispiel für Optimierung 1 mit Ausgabe aller Eingabedaten. |
| `planungs_testfaelle/` | Vorbereitete Anfragen für `pruefe_planung.py`. Aktuell liegen vier Smoke-Tests vor. Der im Skript voreingestellte Testfall `klettern_essen` ist nicht mehr vorhanden (siehe Offene Punkte im Entscheidungslog). |
| `tests/` | Automatisierte Tests; `tests/conftest.py` enthält die Übersicht, welche Datei welches Modul prüft. |
| `evaluierung/` | Unabhängige Prüfung von Optimierung 1, kein Teil des normalen Testlaufs. |
| `ergebnisse/` | Erzeugte Reisepläne (Text, JSON, POI-Übersicht als CSV) und heruntergeladene Fotos. Nicht eingecheckt. |
| `protokolle/` | Ein JSONL-Protokoll je Sitzung mit jedem Werkzeugaufruf sowie eine Debug-Datei je Planung. Enthält personenbezogene Testdaten und ist nicht eingecheckt. |
| `requirements*.txt` | Kern-Abhängigkeiten sowie optionale Abhängigkeiten für Sprachmodus und Evaluierung. |
| `.env.example` | Alle bekannten Konfigurationsvariablen. Die `.env` selbst ist nicht eingecheckt. |
