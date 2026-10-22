"""
Tests für den Zugriffsschutz der Web-Oberfläche (webapp.py) bei der Freigabe an Tester über einen
öffentlichen Tunnel (starte_extern.py). Geprüft wird über den FastAPI-TestClient, ohne echten
Server, ohne LLM und ohne API-Aufrufe: `hauptablauf` wird durch eine Attrappe ersetzt, die nur
festhält, ob eine Sitzung gestartet wurde.

Der TestClient läuft mit https-Basisadresse, weil das Zugangs-Cookie als Secure gesetzt wird und
sonst vom Client nicht zurückgeschickt würde (wie in einem echten Browser über HTTP).
"""
import dataclasses
import logging

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import webapp

TOKEN = "richtiges-token-123"


class _FakeMapsClient:
    def lade_foto(self, foto_referenz: str, ziel_pfad: str, max_breite: int = 640) -> bool:
        return False


@pytest.fixture
def gestartete_sitzungen(monkeypatch):
    """Ersetzt hauptablauf durch eine Attrappe: sendet eine Begrüßung und endet ohne Reiseplan.
    Die Liste hält die Aufrufparameter fest, um zu prüfen, ob (und wie) eine Sitzung startete."""
    aufrufe: list[dict] = []

    async def fake_hauptablauf(io_kanal, protokoll_praefix, ausgabe_basisname):
        aufrufe.append({"protokoll_praefix": protokoll_praefix, "ausgabe_basisname": ausgabe_basisname})
        await io_kanal.bot_sagt("Hallo")
        return None

    monkeypatch.setattr(webapp, "hauptablauf", fake_hauptablauf)
    monkeypatch.setattr(webapp, "erzeuge_client", lambda: _FakeMapsClient())
    return aufrufe


def _setze_token(monkeypatch, token):
    monkeypatch.setattr(webapp, "EINSTELLUNGEN", dataclasses.replace(webapp.EINSTELLUNGEN, zugangstoken=token))


@pytest.fixture
def client():
    return TestClient(webapp.app, base_url="https://testserver")


# --- Ohne konfiguriertes Token: Verhalten wie bisher -------------------------------------------

def test_ohne_token_ist_startseite_frei(monkeypatch, client):
    _setze_token(monkeypatch, None)

    antwort = client.get("/")

    assert antwort.status_code == 200
    assert "<html" in antwort.text.lower()
    assert webapp.ZUGANG_COOKIE not in antwort.cookies


def test_ohne_token_verbindet_websocket_ohne_cookie(monkeypatch, client, gestartete_sitzungen):
    _setze_token(monkeypatch, None)

    with client.websocket_connect("/ws/chat") as verbindung:
        assert verbindung.receive_json() == {"typ": "bot", "text": "Hallo"}

    assert len(gestartete_sitzungen) == 1


# --- Mit Token: HTTP ------------------------------------------------------------------------------

def test_mit_token_ohne_cookie_wird_startseite_abgewiesen(monkeypatch, client):
    _setze_token(monkeypatch, TOKEN)

    antwort = client.get("/")

    assert antwort.status_code == 403
    assert "Kein Zugang" in antwort.text
    assert "vollständigen Link" in antwort.text


def test_mit_falschem_token_im_link_wird_abgewiesen(monkeypatch, client):
    _setze_token(monkeypatch, TOKEN)

    antwort = client.get("/?zugang=falsch", follow_redirects=False)

    assert antwort.status_code == 403
    assert webapp.ZUGANG_COOKIE not in antwort.cookies


def test_mit_richtigem_token_im_link_setzt_cookie_und_leitet_ohne_query_um(monkeypatch, client):
    _setze_token(monkeypatch, TOKEN)

    antwort = client.get(f"/?zugang={TOKEN}", follow_redirects=False)

    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"
    cookie_kopf = antwort.headers["set-cookie"].lower()
    assert cookie_kopf.startswith(f"{webapp.ZUGANG_COOKIE}=")
    assert "httponly" in cookie_kopf
    assert "secure" in cookie_kopf
    assert "samesite=lax" in cookie_kopf


def test_nach_redirect_ist_startseite_mit_cookie_erreichbar(monkeypatch, client):
    _setze_token(monkeypatch, TOKEN)

    antwort = client.get(f"/?zugang={TOKEN}")  # folgt der Umleitung, Cookie bleibt im Client

    assert antwort.status_code == 200
    assert str(antwort.url) == "https://testserver/"
    assert "<html" in antwort.text.lower()


def test_falsches_cookie_wird_abgewiesen(monkeypatch, client):
    _setze_token(monkeypatch, TOKEN)
    client.cookies.set(webapp.ZUGANG_COOKIE, "falsch")

    assert client.get("/").status_code == 403


def test_fotos_nur_mit_cookie(monkeypatch, client):
    # Sitzungsfotos (Google) sind geschützt. Mit Cookie erreicht die Anfrage die Dateiauslieferung
    # (404, weil die Datei nicht existiert), ohne Cookie endet sie vorher mit 403.
    _setze_token(monkeypatch, TOKEN)

    assert client.get("/fotos/sitzung/foto.jpg").status_code == 403
    client.cookies.set(webapp.ZUGANG_COOKIE, TOKEN)
    assert client.get("/fotos/sitzung/foto.jpg").status_code == 404


def test_mitgelieferte_bilder_bleiben_frei_index_html_nicht(monkeypatch, client):
    _setze_token(monkeypatch, TOKEN)

    assert client.get("/static/img/avatar.svg").status_code == 200
    assert client.get("/static/index.html").status_code == 403
    assert client.get("/docs").status_code == 403


# --- Mit Token: WebSocket -------------------------------------------------------------------------

def test_websocket_ohne_cookie_wird_vor_sitzungsstart_geschlossen(monkeypatch, client, gestartete_sitzungen):
    _setze_token(monkeypatch, TOKEN)

    with pytest.raises(WebSocketDisconnect) as abbruch:
        with client.websocket_connect("/ws/chat") as verbindung:
            verbindung.receive_json()

    assert abbruch.value.code == 1008
    assert gestartete_sitzungen == []


def test_websocket_mit_falschem_cookie_wird_geschlossen(monkeypatch, client, gestartete_sitzungen):
    _setze_token(monkeypatch, TOKEN)

    with pytest.raises(WebSocketDisconnect) as abbruch:
        with client.websocket_connect("/ws/chat", headers={"cookie": f"{webapp.ZUGANG_COOKIE}=falsch"}):
            pass

    assert abbruch.value.code == 1008
    assert gestartete_sitzungen == []


def test_websocket_mit_cookie_verbindet_und_startet_sitzung(monkeypatch, client, gestartete_sitzungen):
    _setze_token(monkeypatch, TOKEN)

    with client.websocket_connect("/ws/chat", headers={"cookie": f"{webapp.ZUGANG_COOKIE}={TOKEN}"}) as verbindung:
        assert verbindung.receive_json() == {"typ": "bot", "text": "Hallo"}

    assert len(gestartete_sitzungen) == 1


def test_websocket_mit_token_im_query_verbindet(monkeypatch, client, gestartete_sitzungen):
    _setze_token(monkeypatch, TOKEN)

    with client.websocket_connect(f"/ws/chat?zugang={TOKEN}") as verbindung:
        assert verbindung.receive_json()["typ"] == "bot"

    assert len(gestartete_sitzungen) == 1


def test_jede_websocket_verbindung_bekommt_eigene_sitzung(monkeypatch, client, gestartete_sitzungen):
    # Mehrere Tester gleichzeitig: Jede Verbindung startet einen eigenen hauptablauf mit eigener
    # Sitzungs-ID, die auch im Protokoll-Präfix steht (keine gemeinsame Protokolldatei).
    _setze_token(monkeypatch, None)

    for _ in range(2):
        with client.websocket_connect("/ws/chat") as verbindung:
            verbindung.receive_json()

    erste, zweite = gestartete_sitzungen
    assert erste["protokoll_praefix"] != zweite["protokoll_praefix"]
    for aufruf in gestartete_sitzungen:
        sitzung_id = aufruf["ausgabe_basisname"].removeprefix("reiseplan_web_")
        assert aufruf["protokoll_praefix"] == f"web_{sitzung_id}"


# --- Hilfsfunktionen und Logging --------------------------------------------------------------------

def test_token_gueltig_vergleicht_exakt():
    assert webapp.token_gueltig(TOKEN, TOKEN)
    assert not webapp.token_gueltig(TOKEN + "x", TOKEN)
    assert not webapp.token_gueltig("", TOKEN)
    assert not webapp.token_gueltig(None, TOKEN)
    assert not webapp.token_gueltig("äöü", TOKEN)  # Nicht-ASCII löst keinen Fehler aus


def test_token_wird_in_uvicorn_logzeilen_maskiert():
    datensatz = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4:5", "GET", f"/?zugang={TOKEN}&x=1", "1.1", 303), None,
    )

    assert webapp.TokenMaskierer().filter(datensatz) is True
    zeile = datensatz.getMessage()
    assert TOKEN not in zeile
    assert "/?zugang=***&x=1" in zeile


def test_maskierer_ist_an_uvicorn_loggern_angemeldet():
    for name in ("uvicorn.access", "uvicorn.error"):
        assert any(isinstance(f, webapp.TokenMaskierer) for f in logging.getLogger(name).filters)
