"""Tests für die Fotogalerie der Web-Oberfläche (static/img/galerie/, static/index.html).

Geprüft wird, dass Herkunftsliste (QUELLEN.md), Bilddateien und die Bildliste im Skript
(`GALERIE_BILDER`) übereinstimmen, auch in Motiv und Fotograf der Bildbeschriftung, dass jede Datei
eine vollständige Herkunftsangabe hat und dass die Seite keine externen Bild-, Schrift- oder
Stylesheet-Quellen einbindet. Die Beschriftungslogik (Block zwischen "GALERIE-BESCHRIFTUNG ANFANG"
und "ENDE") wird mit Node.js ausgeführt; ohne Node.js werden diese Tests übersprungen. Überblenden
und Darstellung sind Browserverhalten und werden hier nicht geprüft."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parent.parent / "static"
_GALERIE = _STATIC / "img" / "galerie"
_QUELLEN = _GALERIE / "QUELLEN.md"
_INDEX_HTML = _STATIC / "index.html"
_MAX_BYTES = 300 * 1024
_NODE = shutil.which("node")


def _quellen_zeilen() -> list[list[str]]:
    """Tabellenzeilen aus QUELLEN.md (ohne Kopf- und Trennzeile) als Liste der Zellen."""
    zeilen = []
    for zeile in _QUELLEN.read_text(encoding="utf-8").splitlines():
        if not zeile.startswith("|") or zeile.startswith("| Datei") or zeile.startswith("|---"):
            continue
        zeilen.append([zelle.strip() for zelle in zeile.strip().strip("|").split("|")])
    return zeilen


def _bilddateien() -> set[str]:
    return {pfad.name for pfad in _GALERIE.iterdir() if pfad.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}}


def test_quellenliste_und_bilddateien_stimmen_ueberein():
    gelistet = [zellen[0] for zellen in _quellen_zeilen()]
    assert len(gelistet) == len(set(gelistet)), "Datei doppelt in QUELLEN.md"
    assert set(gelistet) == _bilddateien()
    assert len(gelistet) >= 1


def test_jede_quelle_ist_vollstaendig_angegeben():
    for datei, motiv, fotograf, seite, lizenz in _quellen_zeilen():
        assert motiv, datei
        assert fotograf, datei
        assert seite.startswith("https://unsplash.com/photos/"), datei
        assert lizenz == "Unsplash License", datei


def test_bilder_sind_komprimiert():
    for name in _bilddateien():
        assert (_GALERIE / name).stat().st_size < _MAX_BYTES, name


def test_bildliste_im_skript_entspricht_den_dateien():
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    block = re.search(r"const GALERIE_BILDER = \[(.*?)\];", quelltext, re.DOTALL)
    assert block, "GALERIE_BILDER in static/index.html nicht gefunden"
    im_skript = re.findall(r'datei:\s*"([^"]+)"', block.group(1))
    assert len(im_skript) == len(set(im_skript))
    assert set(im_skript) == _bilddateien()


def test_seite_bindet_keine_externen_bild_oder_schriftquellen_ein():
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    assert not re.search(r"<link\b", quelltext, re.IGNORECASE)
    assert "@import" not in quelltext
    assert not re.search(r"url\(\s*['\"]?https?:", quelltext, re.IGNORECASE)
    assert not re.search(r"src=[\"']https?:", quelltext, re.IGNORECASE)


def _galerie_bilder_im_skript() -> list[dict[str, str]]:
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    block = re.search(r"const GALERIE_BILDER = \[(.*?)\];", quelltext, re.DOTALL)
    assert block, "GALERIE_BILDER in static/index.html nicht gefunden"
    return [
        {"datei": datei, "motiv": motiv, "fotograf": fotograf}
        for datei, motiv, fotograf in re.findall(
            r'\{\s*datei:\s*"([^"]+)",\s*motiv:\s*"([^"]+)",\s*fotograf:\s*"([^"]+)"\s*\}', block.group(1)
        )
    ]


def test_beschriftung_im_skript_stimmt_mit_quellen_ueberein():
    # Motiv und Ort der Stimmungsbilder stammen wörtlich aus QUELLEN.md; im Skript darf keine
    # abweichende oder zusätzliche Ortsangabe stehen. Der Fotograf entspricht dem Namen aus der
    # Spalte "Fotograf" ohne den Unsplash-Benutzernamen in Klammern.
    im_skript = {bild["datei"]: bild for bild in _galerie_bilder_im_skript()}
    assert set(im_skript) == _bilddateien()
    for datei, motiv, fotograf, _seite, _lizenz in _quellen_zeilen():
        assert im_skript[datei]["motiv"] == motiv, datei
        assert im_skript[datei]["fotograf"] == re.sub(r"\s*\(@[^)]*\)$", "", fotograf), datei


def test_beschriftungspille_inspiration_ist_entfernt():
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    assert "galerie-label" not in quelltext
    assert "kein Reisevorschlag" not in quelltext
    assert "Inspiration" not in quelltext


def _beschriftung(bild: dict) -> dict:
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    treffer = re.search(r"// GALERIE-BESCHRIFTUNG ANFANG(.*?)// GALERIE-BESCHRIFTUNG ENDE", quelltext, re.DOTALL)
    assert treffer, "Beschriftungs-Block in static/index.html nicht gefunden"
    skript = (
        treffer.group(1)
        + "\nprocess.stdout.write(JSON.stringify(galerieBeschriftung(JSON.parse(process.argv[1]))));\n"
    )
    ergebnis = subprocess.run(
        [_NODE, "-e", skript, json.dumps(bild)], capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(ergebnis.stdout)


@pytest.mark.skipif(_NODE is None, reason="Node.js nicht verfügbar")
def test_jedes_stimmungsbild_zeigt_motiv_aus_quellen_und_unsplash_nachweis():
    for bild in _galerie_bilder_im_skript():
        beschriftung = _beschriftung(bild)
        assert beschriftung["titel"] == bild["motiv"], bild["datei"]
        assert beschriftung["nachweis"] == f"Foto: {bild['fotograf']} / Unsplash", bild["datei"]


@pytest.mark.skipif(_NODE is None, reason="Node.js nicht verfügbar")
def test_beschriftung_lavendelfeld():
    beschriftung = _beschriftung(
        {"datei": "lavendelfeld.jpg", "motiv": "Lavendelfeld bei Zetyovo (Bulgarien)", "fotograf": "Nikolay Hristov"}
    )
    assert beschriftung == {"titel": "Lavendelfeld bei Zetyovo (Bulgarien)", "nachweis": "Foto: Nikolay Hristov / Unsplash"}
