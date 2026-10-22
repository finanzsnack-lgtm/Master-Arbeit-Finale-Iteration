"""Tests für die Eckdaten-Chips im Titelbereich des Reiseplans (static/index.html, Block zwischen
"ECKDATEN-CHIPS ANFANG" und "ENDE"). Der Block wird aus der HTML-Datei ausgeschnitten und mit
Node.js ausgeführt; ist Node.js nicht installiert, werden die Tests übersprungen. Die Darstellung
der Chips im Browser ersetzt dieser Test nicht."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"
_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(_NODE is None, reason="Node.js nicht verfügbar")


def _chips(eckdaten: dict | None) -> list[dict]:
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    treffer = re.search(r"// ECKDATEN-CHIPS ANFANG(.*?)// ECKDATEN-CHIPS ENDE", quelltext, re.DOTALL)
    assert treffer, "Eckdaten-Block in static/index.html nicht gefunden"
    skript = (
        treffer.group(1)
        + "\nprocess.stdout.write(JSON.stringify(eckdatenChips(JSON.parse(process.argv[1]))));\n"
    )
    ergebnis = subprocess.run(
        [_NODE, "-e", skript, json.dumps(eckdaten)], capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(ergebnis.stdout)


def _texte(eckdaten: dict | None) -> list[str]:
    return [chip["text"] for chip in _chips(eckdaten)]


_VOLL = {
    "zielort": "Lissabon", "zeitraum": "12.05.2026 – 18.05.2026", "tage": 7,
    "verkehrsmittel_hinreise": "Bahn", "verkehrsmittel_rueckreise": "Bahn",
    "co2_an_abreise_kg": 19.5, "kosten_pro_person": 1234.4, "kosten_unvollstaendig": False,
}


def test_alle_werte_ergeben_alle_chips_und_gleiches_verkehrsmittel_nur_einmal():
    assert _texte(_VOLL) == [
        "12.05.2026 – 18.05.2026", "7 Tage", "Bahn", "CO₂ An-/Abreise: 19,5 kg", "ca. 1.234 € p. P.",
    ]


def test_unterschiedliche_verkehrsmittel_werden_getrennt_genannt():
    texte = _texte({**_VOLL, "verkehrsmittel_rueckreise": "Auto"})
    assert "Hin: Bahn · Zurück: Auto" in texte


def test_fehlende_werte_lassen_chip_entfallen():
    eckdaten = {**_VOLL, "zeitraum": None, "tage": None, "kosten_pro_person": None}
    assert _texte(eckdaten) == ["Bahn", "CO₂ An-/Abreise: 19,5 kg"]
    assert _texte(None) == []


def test_ein_tag_steht_im_singular():
    assert "1 Tag" in _texte({**_VOLL, "tage": 1})


def test_unvollstaendige_kosten_sind_gekennzeichnet():
    [kosten_chip] = [chip for chip in _chips({**_VOLL, "kosten_unvollstaendig": True}) if "€" in chip["text"]]
    assert kosten_chip["text"] == "ca. 1.234 € p. P. (ohne Unterkunft)"
    assert "Unterkunft" in kosten_chip["titel"]


# -- CO2-Einordnung am CO2-Wert (Demo-Feedback, Station 42) --

_EINSTUFUNG = {"stufe": "mittel", "bezeichnung": "mittel", "hinweis": "Grobe Schätzung, nur An- und Abreise. ..."}


def test_co2_einstufung_wird_als_ampel_mit_text_und_tooltip_am_co2_wert_gezeigt():
    [co2_chip] = [chip for chip in _chips({**_VOLL, "co2_einstufung": _EINSTUFUNG}) if "CO₂" in chip["text"]]
    assert co2_chip["text"] == "CO₂ An-/Abreise: 19,5 kg"
    # Stufe als Wort (nicht nur Farbe) und Schlüssel für die Farbklasse.
    assert co2_chip["ampel"] == {"stufe": "mittel", "text": "mittel"}
    assert co2_chip["titel"] == _EINSTUFUNG["hinweis"]


def test_ohne_co2_einstufung_bleibt_es_bei_der_reinen_mengenangabe():
    [co2_chip] = [chip for chip in _chips({**_VOLL, "co2_einstufung": None}) if "CO₂" in chip["text"]]
    assert "ampel" not in co2_chip
    assert "titel" not in co2_chip


def test_ohne_co2_wert_keine_ampel_und_keine_co2_angabe():
    chips = _chips({**_VOLL, "co2_an_abreise_kg": None, "co2_einstufung": _EINSTUFUNG})
    assert not any("CO₂" in chip["text"] or "ampel" in chip for chip in chips)
