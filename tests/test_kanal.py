"""Tests für die IOKanal-Implementierungen (src/audio/kanal.py) – nur die reinen, ohne echtes
Mikrofon/Konsole testbaren Teile: `TextKanal`/`AudioKanal.zeige_karte` sind No-Ops (Fotos lassen
sich in der Konsole ohnehin nicht darstellen, siehe Moduldoku)."""
import asyncio

from src.api.typen import Unterkunft
from src.audio.kanal import AudioKanal, TextKanal, entferne_markdown, zerlege_schnellantworten


def test_textkanal_zeige_karte_ist_no_op_und_wirft_nicht():
    kanal = TextKanal()
    unterkunft = Unterkunft(id=1, name="Hotel Zentral", x=0.0, y=0.0, preisniveau=2, zertifiziert_nachhaltig=False)
    asyncio.run(kanal.zeige_karte(unterkunft))  # darf nicht werfen


def test_textkanal_zeige_status_ist_no_op_und_wirft_nicht():
    asyncio.run(TextKanal().zeige_status("plant_reise"))  # darf nicht werfen, kein Ausgabe-Zwang


# Iteration 2 (Demo-Feedback: Quick Replies, siehe
# doku/28_stage28_iteration2_ux_feedback_konzepte/README.md): `zerlege_schnellantworten` trennt die
# vom LLM optional angehängte "[SCHNELLANTWORTEN: ...]"-Zeile vom eigentlichen Nachrichtentext.

def test_zerlege_schnellantworten_ohne_marker_liefert_text_unveraendert():
    text, optionen = zerlege_schnellantworten("Wie ist Ihr Name?")
    assert text == "Wie ist Ihr Name?"
    assert optionen is None


def test_zerlege_schnellantworten_trennt_marker_und_optionen():
    text, optionen = zerlege_schnellantworten(
        "Möchten Sie ein Auto mieten?\n[SCHNELLANTWORTEN: Ja | Nein]"
    )
    assert text == "Möchten Sie ein Auto mieten?"
    assert optionen == ["Ja", "Nein"]


def test_zerlege_schnellantworten_kappt_bei_vier_optionen():
    text, optionen = zerlege_schnellantworten(
        "Welches Verkehrsmittel?\n[SCHNELLANTWORTEN: Bahn | Auto | Fahrrad | Bus | Fernbus]"
    )
    assert text == "Welches Verkehrsmittel?"
    assert optionen == ["Bahn", "Auto", "Fahrrad", "Bus"]


def test_zerlege_schnellantworten_leere_klammer_liefert_keine_optionen():
    text, optionen = zerlege_schnellantworten("Alles klar?\n[SCHNELLANTWORTEN: ]")
    assert text == "Alles klar?"
    assert optionen is None


# Iteration 2 (Demo-Feedback: Formatierung im Bot-Text): Konsole und Sprachausgabe stellen
# **fett** nicht dar und sollen die Sternchen weder drucken noch vorlesen.

class _FakeSprachausgabe:
    """Ersatz für die echte Sprachausgabe: merkt sich nur, was vorgelesen würde."""

    def __init__(self):
        self.gesagt: list[str] = []

    def sage(self, text: str) -> None:
        self.gesagt.append(text)


class _KeineSpracheingabe:
    def hoere_zu(self) -> str:  # pragma: no cover - in diesen Tests nie aufgerufen
        return ""


def test_textkanal_druckt_fettdruck_ohne_sternchen(capsys):
    asyncio.run(TextKanal().bot_sagt("Ziel: **Sylt**"))
    ausgabe = capsys.readouterr().out
    assert "Bot: Ziel: Sylt" in ausgabe
    assert "**" not in ausgabe


def test_audiokanal_liest_ohne_sternchen_und_links_nur_als_linktext(capsys):
    sprachausgabe = _FakeSprachausgabe()
    kanal = AudioKanal(_KeineSpracheingabe(), sprachausgabe)
    asyncio.run(kanal.bot_sagt("Ziel: **Sylt / Nordsee**, mehr [hier](https://example.org/sylt)."))
    assert sprachausgabe.gesagt == ["Ziel: Sylt / Nordsee, mehr hier."]
    ausgabe = capsys.readouterr().out
    assert "**" not in ausgabe
    # Das Konsolen-Transkript behält die Adresse, damit sie nutzbar bleibt.
    assert "hier (https://example.org/sylt)" in ausgabe


def test_audiokanal_entfernt_fettdruck_und_schnellantworten_zeile_gemeinsam(capsys):
    sprachausgabe = _FakeSprachausgabe()
    kanal = AudioKanal(_KeineSpracheingabe(), sprachausgabe)
    asyncio.run(kanal.bot_sagt("Passt **Sylt** für dich?\n[SCHNELLANTWORTEN: Ja | Nein]"))
    assert sprachausgabe.gesagt == ["Passt Sylt für dich?"]
    ausgabe = capsys.readouterr().out
    assert "**" not in ausgabe
    assert "SCHNELLANTWORTEN" not in ausgabe


def test_textkanal_entfernt_fettdruck_und_schnellantworten_zeile_gemeinsam(capsys):
    asyncio.run(TextKanal().bot_sagt("Passt **Sylt** für dich?\n[SCHNELLANTWORTEN: Ja | Nein]"))
    ausgabe = capsys.readouterr().out
    assert ausgabe.strip() == "Bot: Passt Sylt für dich?"


def test_zerlege_schnellantworten_laesst_fettdruck_im_text_unveraendert():
    # Der Parser selbst bleibt unverändert: er entfernt nur die Schnellantworten-Zeile.
    text, optionen = zerlege_schnellantworten("Passt **Sylt**?\n[SCHNELLANTWORTEN: Ja | Nein]")
    assert text == "Passt **Sylt**?"
    assert optionen == ["Ja", "Nein"]


def test_entferne_markdown_laesst_einzelne_und_ungeschlossene_sternchen_stehen():
    assert entferne_markdown("5 * 3 Sterne") == "5 * 3 Sterne"
    assert entferne_markdown("nur **offen") == "nur **offen"
    assert entferne_markdown("- **Sylt**\n- Rügen") == "- Sylt\n- Rügen"


def test_entferne_markdown_wandelt_nur_http_links_um():
    assert entferne_markdown("[x](javascript:alert(1))") == "[x](javascript:alert(1))"
    assert entferne_markdown("[Info](http://example.org)") == "Info"
