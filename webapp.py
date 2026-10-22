"""
Web-Oberfläche für den Reisebot: dieselbe Dialoglogik wie chat.py (siehe dort – `hauptablauf`
bleibt unverändert die zentrale Ablaufsteuerung), nur über einen Browser-Chat statt die Konsole
angesteuert.

Transport: WebSocket (`/ws/chat`), siehe `WebIOKanal` unten – implementiert dieselbe `IOKanal`-
Schnittstelle wie TextKanal/AudioKanal (src/audio/kanal.py), nur über Browser-Nachrichten statt
Konsole/Mikrofon. Der eigentliche Dialog (welche Frage wann, Werkzeuge, Validierung, Optimierung)
läuft dadurch UNVERÄNDERT über chat.py::hauptablauf – webapp.py fügt nur einen neuen Kanal sowie
eine abschließende Karten-Ansicht (Foto, Kurzbeschreibung, Maps-Link je Unterkunft/POI) hinzu, NUR
im fertigen Reiseplan am Ende, nicht live während des Gesprächs.

Fotos werden ERST NACH Abschluss der Planung serverseitig heruntergeladen (siehe
src/ausgabe/fotos.py) und als statische Dateien ausgeliefert – der Google-Maps-API-Key bleibt
dadurch ausschließlich serverseitig (siehe google_maps.py `lade_foto`), der Browser bekommt ihn
nie zu Gesicht.

Aufruf: uvicorn webapp:app  (siehe README.md)

Zugriffsschutz für die Freigabe an Tester (starte_extern.py): Ist ein Zugangstoken konfiguriert
(`ZUGANGSTOKEN`, siehe src/config.py), sind die Startseite, der WebSocket und die Fotos nur mit
gültigem Token erreichbar. Grund: Jede Sitzung startet einen LLM-Dialog und echte API-Anfragen und
verursacht damit Kosten; über den öffentlichen Tunnel-Link wäre der Server sonst für jeden
erreichbar, der die Adresse kennt. Ohne konfiguriertes Token (lokaler Normalbetrieb) bleibt das
Verhalten unverändert.

KEIN --reload unter Windows: Uvicorns Reload-Modus wechselt dort intern von der ProactorEventLoop
auf die SelectorEventLoop (uvicorn/loops/asyncio.py, `use_subprocess`-Zweig) – die
SelectorEventLoop kann unter Windows aber keine Subprozesse starten, und genau das braucht das
Claude Agent SDK beim Verbindungsaufbau (startet die Claude-Code-CLI als Subprozess). Ergebnis ohne
diesen Hinweis: `NotImplementedError` beim ersten Chat-Aufruf. Code-Änderungen erfordern mit dieser
Einstellung einen manuellen Neustart des Servers statt Auto-Reload.
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from chat import hauptablauf
from src.config import EINSTELLUNGEN
from src.api.google_maps import erzeuge_client
from src.api.typen import Unterkunft
from src.audio.kanal import IOKanal, zerlege_schnellantworten
from src.ausgabe.fotos import lade_fotos_fuer_plan
from src.ausgabe.reiseplan import als_kartendaten, als_text, maps_link
from src.optimierung.kostenschaetzung import schaetze_unterkunft_preis_pro_nacht

_WURZEL_VERZEICHNIS = Path(__file__).resolve().parent
# Eigenes fotos/-Unterverzeichnis in ergebnisse/ (nicht direkt darin), damit die pro Sitzung
# heruntergeladenen Bilder nicht mit den Text-/JSON-/CSV-Ausgaben von agent_tools.py kollidieren.
_FOTO_VERZEICHNIS = _WURZEL_VERZEICHNIS / "ergebnisse" / "fotos"
_FOTO_VERZEICHNIS.mkdir(parents=True, exist_ok=True)
_STATIC_VERZEICHNIS = _WURZEL_VERZEICHNIS / "static"

app = FastAPI(title="Reisebot")
app.mount("/fotos", StaticFiles(directory=str(_FOTO_VERZEICHNIS)), name="fotos")
app.mount("/static", StaticFiles(directory=str(_STATIC_VERZEICHNIS)), name="static")


# --- Zugriffsschutz per Zugangstoken (nur aktiv, wenn ein Token konfiguriert ist) ---------------

# Name des Query-Parameters im weitergegebenen Link (https://…/?zugang=TOKEN) und des Cookies, das
# nach dem ersten Aufruf das Token im Browser hält. Das Cookie ersetzt eine separate
# Passworteingabe: Tester öffnen nur den Link, die Webapp merkt sich den Zugang selbst.
ZUGANG_PARAMETER = "zugang"
ZUGANG_COOKIE = "reisebot_zugang"

# Frei zugängliche Pfade auch bei aktivem Schutz: nur die mitgelieferten Bilder (Avatar, lizenzfreie
# Galerie- und Verkehrsmittelfotos). Sie enthalten keine personenbezogenen Daten, verursachen keine
# API-Kosten und sind ohne die geschützte Startseite ohnehin nutzlos; ein Schutz brächte keinen
# Sicherheitsgewinn. Bewusst NICHT frei: /static/index.html (dieselbe Oberfläche wie "/"), /fotos/
# (je Sitzung heruntergeladene Google-Fotos, verraten z. B. die gewählte Unterkunft eines Testers)
# sowie die automatisch erzeugten FastAPI-Seiten /docs und /openapi.json.
_FREIE_PFAD_PRAEFIXE = ("/static/img/",)

_KEIN_ZUGANG_HTML = """<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reisebot – kein Zugang</title></head>
<body style="font-family: sans-serif; max-width: 34rem; margin: 4rem auto; padding: 0 1rem;
             color: #1f2d36; background: #f7f1e6; line-height: 1.5">
<h1 style="color: #1f5f7a">Kein Zugang</h1>
<p>Bitte den vollständigen Link verwenden.</p>
<p>Der Link enthält einen Zugangscode und ändert sich in der Regel bei jedem Neustart des Reisebots.</p>
</body>
</html>
"""


def konfiguriertes_zugangstoken() -> str | None:
    """Aktuell gültiges Zugangstoken oder None (kein Schutz, lokaler Normalbetrieb).

    Eigene Funktion statt direktem Zugriff auf EINSTELLUNGEN an jeder Prüfstelle, damit Tests den
    Wert gezielt setzen können, ohne Umgebungsvariablen vor dem Import verändern zu müssen."""
    return EINSTELLUNGEN.zugangstoken


def token_gueltig(kandidat: str | None, token: str) -> bool:
    """Vergleicht in konstanter Laufzeit (secrets.compare_digest), damit sich das Token nicht
    zeichenweise über Antwortzeiten erraten lässt. Vergleich auf Bytes-Ebene, weil compare_digest
    bei Zeichenketten mit Nicht-ASCII-Zeichen einen Fehler auslösen würde."""
    if not kandidat:
        return False
    return secrets.compare_digest(kandidat.encode("utf-8"), token.encode("utf-8"))


@app.middleware("http")
async def zugriffsschutz(request: Request, call_next: Callable) -> Response:
    """Prüft jede HTTP-Anfrage (einschließlich der /fotos-Dateien) auf ein gültiges Zugangstoken.

    Ablauf bei aktivem Schutz:
    1. `/?zugang=TOKEN` mit gültigem Token: Cookie setzen und auf `/` ohne Query umleiten, damit
       das Token nicht in der Adresszeile, im Verlauf oder auf einem Bildschirmfoto stehen bleibt.
    2. Gültiges Cookie: Anfrage normal bearbeiten.
    3. Sonst: schlichte Seite "Kein Zugang" (HTTP 403).
    Der WebSocket läuft nicht über diese Middleware (nur HTTP), er wird in `websocket_chat`
    gesondert geprüft."""
    token = konfiguriertes_zugangstoken()
    if token is None or request.url.path.startswith(_FREIE_PFAD_PRAEFIXE):
        return await call_next(request)

    if request.url.path == "/" and token_gueltig(request.query_params.get(ZUGANG_PARAMETER), token):
        antwort = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        # HttpOnly: kein Zugriff per JavaScript. Secure: nur über HTTPS (der Tunnel liefert HTTPS;
        # Browser akzeptieren Secure-Cookies zusätzlich auf http://127.0.0.1 bzw. localhost).
        # SameSite=Lax: fremde Webseiten können keine Anfragen mit diesem Cookie auslösen, das
        # Öffnen des Links aus einer Mail oder einem Messenger funktioniert dagegen normal.
        # Ohne Ablaufdatum (Sitzungs-Cookie): Nach dem Schließen des Browsers genügt erneut der Link.
        antwort.set_cookie(ZUGANG_COOKIE, token, httponly=True, secure=True, samesite="lax", path="/")
        return antwort

    if token_gueltig(request.cookies.get(ZUGANG_COOKIE), token):
        return await call_next(request)
    return HTMLResponse(_KEIN_ZUGANG_HTML, status_code=status.HTTP_403_FORBIDDEN)


class TokenMaskierer(logging.Filter):
    """Ersetzt den Wert von `zugang=` in Uvicorn-Logzeilen durch `***`.

    Uvicorn protokolliert jede Anfrage samt Query (z. B. `"GET /?zugang=… HTTP/1.1" 303`). Ohne
    diesen Filter stünde das Token im Konsolenfenster und in mitgeschnittenen Logs."""

    _MUSTER = re.compile(ZUGANG_PARAMETER + r'=[^&\s"]*')

    def _maskiere(self, wert: Any) -> Any:
        if isinstance(wert, str):
            return self._MUSTER.sub(ZUGANG_PARAMETER + "=***", wert)
        return wert

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._maskiere(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._maskiere(arg) for arg in record.args)
        return True


# Uvicorn schreibt HTTP-Anfragen in "uvicorn.access", WebSocket-Verbindungen in "uvicorn.error".
# Ein Logger-Filter bleibt bei Uvicorns Logging-Konfiguration (dictConfig) erhalten.
for _logger_name in ("uvicorn.access", "uvicorn.error"):
    logging.getLogger(_logger_name).addFilter(TokenMaskierer())


class WebIOKanal:
    """
    `IOKanal`-Implementierung für den Browser-Chat: `bot_sagt` schickt eine Nachricht über die
    WebSocket-Verbindung, `nutzer_antwortet` wartet (async, ohne die Event-Loop zu blockieren) auf
    die nächste Nachricht vom Browser. Ersetzt TextKanal/AudioKanal 1:1 für chat.py::hauptablauf –
    der Dialogablauf selbst weiß nichts von WebSockets.

    `zeige_karte` (Entscheidung des Product Owners: Hotel-Foto+Preis schon bei der F15-Bestätigungsfrage MITTEN im
    Gespräch, nicht erst im fertigen Reiseplan) lädt das Foto der vorgeschlagenen Unterkunft SOFORT
    herunter (eigener `MapsClient`, eigener Sitzungsordner – unabhängig vom Batch-Download am Ende
    in `websocket_chat`, da der Reiseplan zu diesem Zeitpunkt noch gar nicht existiert).
    """

    def __init__(self, websocket: WebSocket, foto_verzeichnis: Path):
        self._websocket = websocket
        self._foto_verzeichnis = foto_verzeichnis
        self._maps_client = erzeuge_client()

    async def bot_sagt(self, text: str) -> None:
        # Iteration 2 (Demo-Feedback: Quick Replies, siehe
        # doku/28_stage28_iteration2_ux_feedback_konzepte/README.md): eine vom LLM optional
        # angehängte "[SCHNELLANTWORTEN: ...]"-Zeile wird hier herausgelöst und separat als
        # `schnellantworten` mitgeschickt – der angezeigte Text bleibt sauber, die Web-UI rendert
        # die Optionen als zusätzliche Klick-Chips (Textfeld bleibt parallel nutzbar).
        bereinigt, optionen = zerlege_schnellantworten(text)
        nachricht: dict[str, Any] = {"typ": "bot", "text": bereinigt}
        if optionen:
            nachricht["schnellantworten"] = optionen
        await self._websocket.send_json(nachricht)

    async def nutzer_antwortet(self) -> str:
        nachricht = await self._websocket.receive_json()
        return str(nachricht.get("text", ""))

    async def zeige_karte(self, unterkunft: Unterkunft) -> None:
        foto_url = None
        if unterkunft.foto_referenz and unterkunft.place_id:
            self._foto_verzeichnis.mkdir(parents=True, exist_ok=True)
            dateiname = f"{unterkunft.place_id}.jpg"
            ziel_pfad = self._foto_verzeichnis / dateiname
            # Download im Hintergrund-Thread: ein blockierender HTTP-Aufruf auf der Event-Loop
            # hielte währenddessen alle anderen Sitzungen an (geteilte Event-Loop aller Tester).
            if await asyncio.to_thread(self._maps_client.lade_foto, unterkunft.foto_referenz, str(ziel_pfad)):
                foto_url = f"/fotos/{self._foto_verzeichnis.name}/{dateiname}"
        await self._websocket.send_json(
            {
                "typ": "hotel_karte",
                "name": unterkunft.name,
                "preis_pro_nacht_euro": schaetze_unterkunft_preis_pro_nacht(unterkunft.preisniveau),
                "foto_url": foto_url,
                "maps_link": maps_link(unterkunft.place_id),
            }
        )

    async def zeige_status(self, phase: str) -> None:
        # Iteration 2 (Demo-Feedback: Ladeindikator): eigenes, deutlicheres Signal NUR für den
        # einen bekannten Sonderfall (finale Planung kann bei "mittel"/"stark" Barrierefreiheit
        # spürbar dauern, siehe agent_tools.py `plane_reise_und_abschliessen`) – die Web-UI zeigt
        # dafür eine eigene Karte statt der normalen "Bot schreibt"-Animation, damit ein langes
        # Warten nicht wie ein Einfrieren wirkt.
        await self._websocket.send_json({"typ": "status", "phase": phase})


def ergebnis_nachricht(state: Any, foto_url: Callable[[str | None], str | None]) -> dict[str, Any]:
    """Abschlussnachricht an den Browser: Reiseplan als Text, Abschlussmeldungen, Kartendaten.

    Der Nachhaltigkeits-Nudge ist bewusst nicht enthalten: zum Zeitpunkt des fertigen Reiseplans
    ist die Verkehrsmittelwahl bereits getroffen, der Hinweis wirkt nur während des F13-Dialogs.
    """
    return {
        "typ": "ergebnis",
        "text": als_text(state.reiseplan),
        "meldungen": state.abschluss_meldungen,
        "karten": als_kartendaten(state.reiseplan, foto_url),
    }


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (_STATIC_VERZEICHNIS / "index.html").read_text(encoding="utf-8")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    # Zugriffsschutz VOR accept() und damit vor jeder Agenten-Session bzw. jedem LLM-Aufruf: Ohne
    # gültiges Cookie (oder Token im Query-Parameter) wird der Verbindungsaufbau mit dem
    # WebSocket-Code 1008 (Policy Violation) abgelehnt; Uvicorn beantwortet den Handshake mit 403.
    token = konfiguriertes_zugangstoken()
    if token is not None and not (
        token_gueltig(websocket.cookies.get(ZUGANG_COOKIE), token)
        or token_gueltig(websocket.query_params.get(ZUGANG_PARAMETER), token)
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    sitzung_id = uuid.uuid4().hex[:8]
    kanal: IOKanal = WebIOKanal(websocket, _FOTO_VERZEICHNIS / sitzung_id)

    try:
        # Sitzungs-ID im Protokoll-Präfix: Protokolldateien sind sekundengenau benannt
        # (src/protokoll.py). Beginnen zwei Tester in derselben Sekunde, schrieben sonst beide
        # Sitzungen in dieselbe Datei. Zugleich lässt sich das Protokoll so dem Reiseplan
        # `reiseplan_web_{sitzung_id}` zuordnen.
        state = await hauptablauf(
            io_kanal=kanal,
            protokoll_praefix=f"web_{sitzung_id}",
            ausgabe_basisname=f"reiseplan_web_{sitzung_id}",
        )
    except WebSocketDisconnect:
        return  # Browser-Tab/Verbindung wurde vom Nutzer geschlossen, nichts weiter zu tun.
    except RuntimeError as fehler:
        # uvicorn meldet einen mitten im Gespräch abgebrochenen Verbindung (Tab zu, Reload,
        # Netzwerkaussetzer) nicht immer als WebSocketDisconnect – manchmal erst beim NÄCHSTEN
        # Sendeversuch des Bots als roher RuntimeError ("Unexpected ASGI message 'websocket.send',
        # after sending 'websocket.close'"), siehe uvicorn/protocols/websockets/*. Nur DIESES
        # spezifische Muster abfangen (Verbindung ist weg, nichts mehr zu tun) – ein "echter"
        # RuntimeError (z.B. ein Google-Maps-API-Fehler mitten in der Planung) soll weiterhin als
        # Fehler sichtbar bleiben statt stillschweigend zu verschwinden.
        if "websocket" in str(fehler).lower():
            return
        raise

    if state is None or not (state.abgeschlossen and state.reiseplan is not None):
        # LLMVerbindungsFehler (state is None) ODER abgebrochen (breche_planung_ab) – hauptablauf
        # hat die passende Meldung bereits über den Kanal an den Browser geschickt.
        try:
            await websocket.close()
        except RuntimeError:
            pass
        return

    # Foto-Download (ein HTTP-Aufruf je Karte) im Hintergrund-Thread, damit parallele Sitzungen
    # anderer Tester währenddessen weiter bedient werden. Thread-sicher: eigener Sitzungsordner,
    # der Maps-Client dieser Sitzung wird zu diesem Zeitpunkt von nichts anderem mehr benutzt.
    fotos = await asyncio.to_thread(
        lade_fotos_fuer_plan, state.reiseplan, state.maps_client, _FOTO_VERZEICHNIS / sitzung_id
    )

    def foto_url(place_id: str | None) -> str | None:
        dateiname = fotos.get(place_id) if place_id else None
        return f"/fotos/{sitzung_id}/{dateiname}" if dateiname else None

    try:
        await websocket.send_json(ergebnis_nachricht(state, foto_url))
    except WebSocketDisconnect:
        return

    try:
        await websocket.close()
    except RuntimeError:
        pass


if __name__ == "__main__":
    import uvicorn

    # KEIN reload=True unter Windows – siehe Moduldoku oben (Subprozess-Konflikt mit dem Claude
    # Agent SDK).
    uvicorn.run("webapp:app", host="127.0.0.1", port=8000)
