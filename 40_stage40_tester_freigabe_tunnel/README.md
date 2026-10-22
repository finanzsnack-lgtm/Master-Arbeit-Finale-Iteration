# Station 40 — Freigabe für externe Tester über einen Cloudflare-Tunnel

**Zeitraum:** 04.10.2026 (ENTSCHEIDUNGSLOG.md Phase 69)
**Kein Code-Duplikat** (kein `code_stand`-Snapshot vorgesehen, transparent vermerkt).

## Auslöser

Für Demonstration und Evaluation im Sinne von Design Science Research sollen externe Testpersonen
den Prototyp nutzen können. Der Prototyp läuft auf dem Rechner des Product Owners. Vorgaben des
Product Owners:

- Zugang von anderen Rechnern und aus anderen Netzwerken über einen einzigen Link.
- Keine Installation bei den Testpersonen und keine Weitergabe des Codes.
- Keine separate Passworteingabe.

Jedes Gespräch verursacht LLM- und API-Kosten. Ein öffentlich erreichbarer Server muss daher vor
der Nutzung durch Unbefugte geschützt sein.

## Umsetzung

**Tunnel und Startskript (`starte_extern.bat`, `starte_extern.py`).** Die Batch-Datei ruft das
Python-Skript auf. Es läuft in folgenden Schritten:

1. Prüfen, ob `cloudflared` verfügbar ist (auch an üblichen Installationsorten); andernfalls
   Hinweis auf `winget install Cloudflare.cloudflared`. Prüfen, ob Port 8000 frei ist.
2. Token bestimmen (`bestimme_token`): `ZUGANGSTOKEN` aus der `.env`, sonst je Start ein
   zufälliges Token über `secrets.token_urlsafe(24)`.
3. Uvicorn auf `127.0.0.1:8000` starten; das Token wird nur diesem Serverlauf als Umgebungsvariable
   übergeben.
4. Einen Cloudflare Quick Tunnel öffnen (`cloudflared tunnel --no-autoupdate --url
   http://127.0.0.1:8000`), die `trycloudflare.com`-Adresse aus der Ausgabe lesen und den Link
   `https://….trycloudflare.com/?zugang=TOKEN` ausgeben (`baue_link`), zusätzlich in die
   Zwischenablage.
5. Beim Beenden die eigenen Kindprozesse schließen, unter Windows mit `taskkill /T`.

Der Quick Tunnel ist kostenlos, braucht kein Konto, liefert HTTPS und leitet WebSockets weiter.
HTTPS ist zugleich Voraussetzung dafür, dass der Browser das Mikrofon für die Web Speech API
freigibt.

**Zugriffsschutz (`webapp.py`).** Ohne konfiguriertes Token bleibt der lokale Betrieb unverändert.
Mit Token gilt:

- `/?zugang=TOKEN` mit gültigem Token setzt das Cookie `reisebot_zugang` (HttpOnly, Secure,
  SameSite=Lax, ohne Ablaufdatum) und leitet per 303 auf `/` ohne Token in der Adresse um.
- Die HTTP-Middleware `zugriffsschutz` lässt danach nur Anfragen mit gültigem Cookie durch, sonst
  folgt die Seite „Kein Zugang" (HTTP 403). Geschützt sind `/`, `/fotos/` (je Sitzung
  heruntergeladene Google-Fotos), `/static/index.html`, `/docs` und `/openapi.json`.
- Frei bleibt nur `/static/img/`: mitgelieferte Avatar-, Galerie- und Verkehrsmittelbilder ohne
  Personenbezug und ohne API-Kosten.
- Der WebSocket `/ws/chat` läuft nicht über die Middleware. `websocket_chat` prüft Cookie oder
  Query-Parameter selbst und schließt die Verbindung ohne gültiges Token mit Code 1008, bevor eine
  Sitzung oder ein LLM-Aufruf entsteht.
- `token_gueltig` vergleicht mit `secrets.compare_digest` in konstanter Laufzeit.
- Der Logfilter `TokenMaskierer` an `uvicorn.access` und `uvicorn.error` ersetzt das Token in den
  Logzeilen durch `zugang=***`.

Konfiguration: `zugangstoken` in `src/config.py`, `ZUGANGSTOKEN` in `.env.example`. Ein dort
eingetragenes Token gilt dauerhaft und schützt dann auch den lokalen Aufruf. `requirements.txt`
nennt zusätzlich `httpx` für den FastAPI-Testclient.

**Nebenläufigkeit für mehrere Testpersonen (`src/fragekatalog/agent_tools.py`, `webapp.py`).** Alle
Verbindungen teilen sich eine Event-Loop. Blockierende API-Aufrufe oder eine lange Planung hielten
sonst jede andere Sitzung an.

- Der Dekorator `im_hintergrund` führt `speichere_feld` und `hole_api_daten` per
  `asyncio.to_thread` aus. `plane_reise_und_abschliessen` führt Vorprüfung und Planung ebenfalls im
  Thread aus.
- Das Statussignal `zeige_status("plant_reise")` wird auf der Event-Loop gesendet, weil der
  WebSocket nur dort bedient werden darf.
- In `webapp.py` laufen die Foto-Downloads (Vorschaukarte der Unterkunft in `zeige_karte`, Fotos
  nach Planungsabschluss) per `asyncio.to_thread`.
- `AgentSessionState.werkzeug_sperre` (`asyncio.Lock`) führt die Werkzeuge einer Sitzung
  nacheinander aus, damit nicht zwei Threads gleichzeitig dieselbe `anfrage` verändern.
  Verschiedene Sitzungen haben eigene Sperren und laufen parallel.
- Eigener Zustand, eigener Maps-Client und eigenes Protokoll je Sitzung bestanden bereits. Neu
  heißen die Protokolldateien `web_<sitzung_id>_…` statt `web_…`, damit gleichzeitig gestartete
  Sitzungen nicht dieselbe Datei erzeugen.

**README.** Der Abschnitt „Reisebot für Tester freigeben" in `README.md` beschreibt Installation von
`cloudflared`, Start, Weitergabe des Links und Grenzen des Betriebs.

**Warum so.** Ein Link ohne Installation und ohne Passworteingabe hält die Hürde für die
Testpersonen niedrig. Das Token schützt vor Kosten durch Unbefugte. Das Cookie ersetzt die
Passworteingabe, die Umleitung hält das Token aus Adresszeile, Verlauf und Bildschirmfotos heraus.
Die Hintergrund-Threads erlauben mehrere Testpersonen gleichzeitig, ohne dass sie sich gegenseitig
blockieren.

**Verworfene Alternativen.**

- Tailscale: Installation und Konto bei den Testpersonen nötig.
- Portfreigabe im Router: Sicherheitsrisiko, dynamische IP, kein HTTPS.
- ngrok: Warnseite vor dem ersten Aufruf, Konto nötig.
- Passwortformular: widerspricht der Vorgabe eines einzigen Links.
- Betrieb ohne Zugriffsschutz: Kostenrisiko durch Unbefugte.

## Verifikation

- `tests/test_zugriffsschutz.py` (17 Tests): unveränderter Betrieb ohne Token, Abweisung ohne oder
  mit falschem Token bzw. Cookie, Umleitung mit Cookie, `/fotos/` nur mit Cookie, `/static/img/`
  frei und `/static/index.html` geschützt, WebSocket-Ablehnung vor Sitzungsstart, eigene Sitzung je
  WebSocket-Verbindung, Logmaskierung.
- `tests/test_starte_extern.py` (10 Tests): Erkennung der Tunnel-Adresse (ohne
  `api.trycloudflare.com`), Link mit kodiertem Token, Token aus Konfiguration oder zufällig,
  Suche nach `cloudflared`, belegter Port.
- `tests/test_agent_tools.py` (2 Tests): Eine zweite Sitzung antwortet, während die erste plant;
  Werkzeuge einer Sitzung laufen nacheinander, die verschiedener Sitzungen parallel.
- Komplette Suite grün (490/490).
- Echter Uvicorn-Lauf mit `curl`: 403 ohne Cookie, 303 mit Token im Link, 200 mit Cookie,
  WebSocket ohne Cookie abgelehnt, Token im Log maskiert.
- Nicht geprüft: `cloudflared` selbst (auf dem Entwicklungsrechner nicht installiert), ein echter
  Browser über den Tunnel, das Mikrofon über HTTPS und der Betrieb mit mehreren echten
  Testpersonen.

## Offene Punkte

- Tunnel-Adresse und (ohne Eintrag in der `.env`) Token ändern sich bei jedem Start; eine feste
  Adresse erfordert ein Cloudflare-Konto mit eigener Domain.
- Die Planung ist eine Python-Rechnung und teilt sich die CPU-Zeit: Während einer Planung werden
  andere Sitzungen langsamer, aber nicht angehalten.
- Alle Testpersonen nutzen dasselbe Claude- und Google-Kontingent.
- Der Rechner des Product Owners muss während der Tests laufen.
- Der Tunnel-Betrieb insgesamt ist ungetestet.
