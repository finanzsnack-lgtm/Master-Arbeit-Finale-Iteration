"""Tests für die Karte "Fester Termin" in der Tages-Zeitleiste (static/index.html, Block zwischen
"FESTER-TERMIN-KARTE ANFANG" und "ENDE"). Der Block wird aus der HTML-Datei ausgeschnitten und mit
Node.js ausgeführt; ist Node.js nicht installiert, werden die Tests übersprungen. `escapeHtml`
nutzt im Browser das DOM und wird hier durch eine gleichwertige Zeichenersetzung nachgebildet. Die
Darstellung im Browser ersetzt dieser Test nicht."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"
_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(_NODE is None, reason="Node.js nicht verfügbar")

# Nachbildung von escapeHtml (index.html): textContent -> innerHTML maskiert &, < und >.
_ESCAPE_HTML_ERSATZ = (
    'function escapeHtml(text) { return String(text ?? "").replace(/&/g, "&amp;")'
    '.replace(/</g, "&lt;").replace(/>/g, "&gt;"); }\n'
)


def _karte(termin: dict) -> str:
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    treffer = re.search(r"// FESTER-TERMIN-KARTE ANFANG(.*?)// FESTER-TERMIN-KARTE ENDE", quelltext, re.DOTALL)
    assert treffer, "Block FESTER-TERMIN-KARTE in static/index.html nicht gefunden"
    skript = (
        _ESCAPE_HTML_ERSATZ + treffer.group(1)
        + "\nprocess.stdout.write(festerTerminKarteHtml(JSON.parse(process.argv[1])));\n"
    )
    ergebnis = subprocess.run(
        [_NODE, "-e", skript, json.dumps(termin)], capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return ergebnis.stdout


_TERMIN = {
    "name": "Deutsches Museum", "adresse": "Museumsinsel 1, München", "foto_url": "/fotos/s1/pid.jpg",
    "maps_link": "https://www.google.com/maps/search/?api=1&query=Google&query_place_id=pid",
    "routen_link": "https://www.google.com/maps/dir/?api=1&origin=48.1%2C11.5&destination=48.2%2C11.6&travelmode=walking",
    "zeitpunkt": "am Ende des Tages, nach der Rückkehr zur Unterkunft", "am_tagesende": True, "dauer": "2h",
    "anfahrt": "Anfahrt ab Unterkunft: zu Fuß, ca. 20min je Richtung",
}


def test_karte_ist_als_fester_termin_und_nicht_als_vorschlag_gekennzeichnet():
    html = _karte(_TERMIN)
    assert 'class="karte fester-termin"' in html
    assert "vorschlag" not in html
    assert '<span class="termin-badge">Fester Termin – dein ausdrücklicher Wunsch</span>' in html


def test_karte_zeigt_name_zeitpunkt_dauer_anfahrt_und_links():
    html = _karte(_TERMIN)
    assert "<strong>Deutsches Museum</strong>" in html
    assert "<span>Museumsinsel 1, München</span>" in html
    assert "<span>am Ende des Tages, nach der Rückkehr zur Unterkunft · Dauer ca. 2h</span>" in html
    assert "<span>Anfahrt ab Unterkunft: zu Fuß, ca. 20min je Richtung</span>" in html
    assert 'src="/fotos/s1/pid.jpg"' in html
    assert "Auf Google Maps ansehen" in html and "query_place_id=pid" in html
    assert "Route ab Unterkunft ansehen" in html and "travelmode=walking" in html


def test_karte_ohne_foto_adresse_und_links_zeigt_nur_vorhandene_angaben():
    html = _karte({**_TERMIN, "foto_url": None, "adresse": None, "maps_link": None, "routen_link": None, "anfahrt": ""})
    assert "Kein Foto verfügbar" in html
    assert "<img" not in html and "<a " not in html
    assert "Museumsinsel" not in html and "Anfahrt" not in html


def test_karte_maskiert_texte_und_attributwerte():
    html = _karte({**_TERMIN, "name": '<script>alert(1)</script>', "foto_url": '/x" onerror="alert(1)'})
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert 'onerror="alert' not in html
