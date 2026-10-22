"""Tests für die Titelzeile der Web-Oberfläche (static/index.html, <header> über dem Chat).

Nach dem finalen Demo-Feedback (Station 42) zeigt die Titelzeile nur noch "Masterarbeit Prototyp Nick
Poeppler"; der frühere Untertitel entfällt. Der Browser-Tab-Titel bleibt "Reisebot". Geprüft wird
der statische HTML-Text; die Darstellung auf schmalen Fenstern (Umbruch ohne horizontales Scrollen)
ist nur im Browser beobachtbar.
"""
import re
from pathlib import Path

_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"


def _html() -> str:
    return _INDEX_HTML.read_text(encoding="utf-8")


def _kopfbereich() -> str:
    """Liefert den Inhalt des einzigen <header>-Elements der Seite."""
    treffer = re.findall(r"<header>(.*?)</header>", _html(), re.DOTALL)
    assert len(treffer) == 1, "Genau ein <header> in static/index.html erwartet"
    return treffer[0]


def test_titelzeile_zeigt_nur_masterarbeit_titel():
    kopf = _kopfbereich()
    assert re.search(r"<h1>\s*Masterarbeit Prototyp Nick Poeppler\s*</h1>", kopf)
    # Der frühere Untertitel ist entfernt, im Kopfbereich steht nur noch die Überschrift.
    assert "<p" not in kopf
    assert "Reiseplanungs-Prototyp" not in _html()


def test_browser_tab_titel_bleibt_reisebot():
    assert "<title>Reisebot</title>" in _html()


def test_keine_verwaiste_css_regel_fuer_untertitel():
    # Ohne <p> im Kopfbereich wäre eine Regel "header p" toter Code.
    assert not re.search(r"\bheader\s+p\s*\{", _html())
