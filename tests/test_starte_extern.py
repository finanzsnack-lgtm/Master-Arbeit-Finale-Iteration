"""
Tests für die deterministischen Hilfsfunktionen von starte_extern.py (Freigabe an Tester über
einen Cloudflare Quick Tunnel). Der eigentliche Start von Webapp und cloudflared wird nicht per
pytest geprüft, weil er echte Prozesse und eine Internetverbindung braucht.
"""
import socket

import starte_extern
import webapp

# Beispielhafte Ausgabe von `cloudflared tunnel --url …` (cloudflared schreibt sie auf stderr).
BEISPIEL_AUSGABE = """\
2026-10-04T09:12:01Z INF Thank you for trying Cloudflare Tunnel. Doing so, without a Cloudflare account, is a quick way to experiment and try it out.
2026-10-04T09:12:01Z INF Requesting new quick Tunnel on trycloudflare.com...
2026-10-04T09:12:03Z INF +--------------------------------------------------------------------------------------------+
2026-10-04T09:12:03Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-10-04T09:12:03Z INF |  https://sunny-river-maple-garden.trycloudflare.com                                        |
2026-10-04T09:12:03Z INF +--------------------------------------------------------------------------------------------+
2026-10-04T09:12:04Z INF Registered tunnel connection connIndex=0 location=fra08 protocol=quic
"""


def test_tunnel_url_wird_aus_cloudflared_ausgabe_gelesen():
    gefunden = [url for zeile in BEISPIEL_AUSGABE.splitlines() if (url := starte_extern.lies_tunnel_url(zeile))]

    assert gefunden == ["https://sunny-river-maple-garden.trycloudflare.com"]


def test_api_adresse_von_trycloudflare_ist_kein_tunnel_link():
    assert starte_extern.lies_tunnel_url("ERR failed to request quick Tunnel: https://api.trycloudflare.com/tunnel") is None
    assert starte_extern.lies_tunnel_url("INF Requesting new quick Tunnel on trycloudflare.com...") is None


def test_link_enthaelt_token_als_zugang_parameter():
    link = starte_extern.baue_link("https://sunny-river-maple-garden.trycloudflare.com", "abc_DEF-123")

    assert link == "https://sunny-river-maple-garden.trycloudflare.com/?zugang=abc_DEF-123"


def test_link_kodiert_sonderzeichen_im_token():
    link = starte_extern.baue_link("https://x.trycloudflare.com/", "a&b c")

    assert link == "https://x.trycloudflare.com/?zugang=a%26b%20c"


def test_parametername_stimmt_mit_webapp_ueberein():
    assert starte_extern.ZUGANG_PARAMETER == webapp.ZUGANG_PARAMETER


def test_konfiguriertes_token_wird_uebernommen():
    assert starte_extern.bestimme_token("fest") == ("fest", True)


def test_ohne_konfiguration_wird_je_start_zufaelliges_token_erzeugt():
    erstes, aus_konfiguration = starte_extern.bestimme_token(None)
    zweites, _ = starte_extern.bestimme_token(None)

    assert aus_konfiguration is False
    assert erstes != zweites
    assert len(erstes) >= 32  # 24 Byte Zufall, Base64-URL-kodiert


def test_cloudflared_fehlt(monkeypatch, tmp_path):
    monkeypatch.setattr(starte_extern.shutil, "which", lambda name: None)
    monkeypatch.setattr(starte_extern, "_CLOUDFLARED_KANDIDATEN", [tmp_path / "cloudflared.exe"])

    assert starte_extern.finde_cloudflared() is None


def test_cloudflared_an_ueblichem_ort_wird_gefunden(monkeypatch, tmp_path):
    programm = tmp_path / "cloudflared.exe"
    programm.write_bytes(b"")
    monkeypatch.setattr(starte_extern.shutil, "which", lambda name: None)
    monkeypatch.setattr(starte_extern, "_CLOUDFLARED_KANDIDATEN", [programm])

    assert starte_extern.finde_cloudflared() == str(programm)


def test_belegter_port_wird_erkannt():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as belegt:
        belegt.bind(("127.0.0.1", 0))
        belegt.listen()
        port = belegt.getsockname()[1]

        assert starte_extern.port_frei("127.0.0.1", port) is False
