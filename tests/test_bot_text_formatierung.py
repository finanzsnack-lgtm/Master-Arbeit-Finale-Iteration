"""Tests für die Formatierung des Bot-Texts im Browser (static/index.html, Block zwischen
"BOT-TEXT-FORMATIERUNG ANFANG" und "ENDE"). Der Block wird aus der HTML-Datei ausgeschnitten und
mit Node.js ausgeführt; `escapeHtml` wird dabei durch eine DOM-freie Variante mit derselben
Wirkung ersetzt (Escapen von &, < und >, wie die Serialisierung über textContent/innerHTML im
Browser). Ist Node.js nicht installiert, werden die Tests übersprungen. Die tatsächliche Darstellung
im Browser (Abstände, Listenoptik) ersetzt dieser Test nicht."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"
_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(_NODE is None, reason="Node.js nicht verfügbar")

_ESCAPE_ERSATZ = """
function escapeHtml(text) {
  return String(text ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
"""


def _formatierungsblock() -> str:
    quelltext = _INDEX_HTML.read_text(encoding="utf-8")
    treffer = re.search(
        r"// BOT-TEXT-FORMATIERUNG ANFANG(.*?)// BOT-TEXT-FORMATIERUNG ENDE", quelltext, re.DOTALL
    )
    assert treffer, "Formatierungsblock in static/index.html nicht gefunden"
    return treffer.group(1)


def _rufe_js(funktion: str, text: str) -> str:
    skript = (
        _ESCAPE_ERSATZ
        + _formatierungsblock()
        + f"\nprocess.stdout.write(JSON.stringify({funktion}(JSON.parse(process.argv[1]))));\n"
    )
    ergebnis = subprocess.run(
        [_NODE, "-e", skript, json.dumps(text)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ergebnis.stdout)


def formatiere(text: str) -> str:
    return _rufe_js("formatiereBotText", text)


def klartext(text: str) -> str:
    return _rufe_js("botTextAlsKlartext", text)


def test_fettdruck_wird_strong_ohne_sternchen():
    assert formatiere("Ziel: **Sylt / Nordsee**") == "Ziel: <strong>Sylt / Nordsee</strong>"


def test_aufzaehlungszeilen_werden_liste_ohne_zusaetzliche_leerzeilen():
    html = formatiere("Vorschläge:\n\n- **Sylt**\n- Rügen\n\nPasst das?")
    assert html == "Vorschläge:<ul><li><strong>Sylt</strong></li><li>Rügen</li></ul>Passt das?"


def test_normale_zeilenumbrueche_bleiben_erhalten():
    assert formatiere("Zeile 1\nZeile 2\n\nZeile 4") == "Zeile 1\nZeile 2\n\nZeile 4"


def test_html_im_bottext_erscheint_als_reiner_text():
    html = formatiere('<script>alert(1)</script> <b>x</b> <img src=x onerror="alert(1)">')
    assert "<script" not in html and "<b>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html


def test_javascript_link_wird_kein_link():
    html = formatiere("[x](javascript:alert(1))")
    assert "<a" not in html
    assert html == "[x](javascript:alert(1))"


def test_http_link_wird_sicherer_link():
    html = formatiere("Mehr [Infos](https://example.org/a?b=1&c=2)")
    assert html == (
        'Mehr <a href="https://example.org/a?b=1&amp;c=2" target="_blank" '
        'rel="noopener noreferrer">Infos</a>'
    )


def test_link_adresse_kann_nicht_aus_dem_attribut_ausbrechen():
    html = formatiere('[x](https://a.org/"onmouseover="alert(1))')
    assert 'onmouseover="' not in html


def test_einzelne_und_ungeschlossene_sternchen_bleiben_text():
    assert formatiere("5 * 3 Sterne") == "5 * 3 Sterne"
    assert formatiere("nur **offen") == "nur **offen"
    assert formatiere("** Leerzeichen **") == "** Leerzeichen **"


def test_vorlesetext_ohne_sternchen_und_links_nur_als_linktext():
    text = "Ziel: **Sylt**\n- Strand\nMehr [hier](https://example.org)."
    assert klartext(text) == "Ziel: Sylt\nStrand\nMehr hier."
