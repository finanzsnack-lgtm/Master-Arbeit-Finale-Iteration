"""Tests für die Galerie "Inspiration" der Web-Oberfläche (static/img/galerie/, static/index.html).

Geprüft wird, dass Herkunftsliste (QUELLEN.md), Bilddateien und die Bildliste im Skript
(`GALERIE_BILDER`) übereinstimmen, dass jede Datei eine vollständige Herkunftsangabe hat und dass die
Seite keine externen Bild-, Schrift- oder Stylesheet-Quellen einbindet. Das Überblenden selbst ist
Browserverhalten und wird hier nicht geprüft."""
import re
from pathlib import Path

_STATIC = Path(__file__).resolve().parent.parent / "static"
_GALERIE = _STATIC / "img" / "galerie"
_QUELLEN = _GALERIE / "QUELLEN.md"
_INDEX_HTML = _STATIC / "index.html"
_MAX_BYTES = 300 * 1024


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
