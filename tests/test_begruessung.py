"""Tests für die feste Begrüßung zu Beginn jeder Sitzung (chat.py::BEGRUESSUNG, a1_reisewunsch_aeussern).

Auslöser ist das Demo-Feedback zu Station 42, Punkt 1: Der Bot soll zu Beginn begrüßen und kurz
erklären, was er tut. Geprüft werden der Aufbau (Begrüßung, kurze Erklärung, offene Einstiegsfrage),
die du-Anrede (Phase 67), die Darstellbarkeit ohne Markdown (Phase 64) und dass Web- und
Konsolenkanal denselben Text zeigen. Ob jede Aussage fachlich zutrifft, ist am Kommentar zu
`BEGRUESSUNG` mit Codeverweisen begründet; hier wird nur abgesichert, dass die vereinbarten
Kernaussagen enthalten sind und keine nicht eingelösten Versprechen hinzukommen.
"""
import asyncio
import re

import chat
import webapp
from chat import BEGRUESSUNG, a1_reisewunsch_aeussern
from src.audio.kanal import TextKanal, entferne_markdown, zerlege_schnellantworten


def _absaetze() -> list[str]:
    return BEGRUESSUNG.split("\n\n")


class _FakeKanal:
    """Zeichnet Bot-Nachrichten auf und liefert eine vorgegebene Nutzerantwort."""

    def __init__(self, antwort: str):
        self.bot_nachrichten: list[str] = []
        self._antwort = antwort

    async def bot_sagt(self, text: str) -> None:
        self.bot_nachrichten.append(text)

    async def nutzer_antwortet(self) -> str:
        return self._antwort


class _FakeWebSocket:
    def __init__(self):
        self.gesendete_nachrichten: list[dict] = []

    async def send_json(self, daten: dict) -> None:
        self.gesendete_nachrichten.append(daten)


def test_a1_sendet_begruessung_als_einzige_erste_nachricht_und_gibt_reisewunsch_unveraendert_zurueck():
    kanal = _FakeKanal("Ein paar ruhige Tage an der Ostsee mit Radtouren")

    reisewunsch = asyncio.run(a1_reisewunsch_aeussern(kanal))

    assert kanal.bot_nachrichten == [BEGRUESSUNG]
    # Der Reisewunsch fließt unverändert in baue_regelwerk_text ein, a1 bereitet ihn nicht auf.
    assert reisewunsch == "Ein paar ruhige Tage an der Ostsee mit Radtouren"


def test_begruessung_hat_drei_teile_begruessung_erklaerung_einstiegsfrage():
    begruessung, erklaerung, frage = _absaetze()
    assert "willkommen" in begruessung.lower()
    # Kurze Erklärung: zwei bis vier Sätze.
    saetze = [s for s in re.split(r"(?<=[.!?])\s+", erklaerung.strip()) if s]
    assert 2 <= len(saetze) <= 4
    # Die offene Einstiegsfrage nach dem Reisewunsch bleibt der Abschluss der Nachricht.
    assert frage.endswith("Was schwebt dir für eine Reise vor?")


def test_erklaerung_nennt_die_vereinbarten_kernaussagen():
    erklaerung = _absaetze()[1]
    for kernaussage in ("ohne Flugzeug", "einer Unterkunft", "Fragen", "Google Maps",
                        "Tag-für-Tag-Plan", "Kostenschätzung", "CO₂", "An- und Abreise", "korrigieren"):
        assert kernaussage in erklaerung, kernaussage


def test_begruessung_verspricht_nichts_ausserhalb_des_prototyps():
    # "Rundreise" legt alltagssprachlich wechselnde Unterkünfte nahe (Grundprinzip 4: eine Unterkunft);
    # der Mailversand hängt von hinterlegten Zugangsdaten ab und wird daher nicht zugesagt.
    assert "Rundreise" not in BEGRUESSUNG
    assert "Mail" not in BEGRUESSUNG


def test_begruessung_durchgaengig_in_du_form():
    assert not re.search(r"\b(Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer)\b", BEGRUESSUNG)
    assert re.search(r"\b(du|dir|dich|dein)\b", BEGRUESSUNG)


def test_begruessung_ohne_markdown_und_ohne_schnellantworten():
    assert "**" not in BEGRUESSUNG
    assert "[" not in BEGRUESSUNG and "#" not in BEGRUESSUNG
    assert not any(zeile.startswith("- ") for zeile in BEGRUESSUNG.splitlines())
    # Die Markdown-Bereinigung (Konsole/Sprachausgabe) und der Schnellantworten-Parser lassen den
    # Text unverändert, alle Kanäle zeigen also denselben Wortlaut.
    assert entferne_markdown(BEGRUESSUNG, links_mit_adresse=True) == BEGRUESSUNG
    assert zerlege_schnellantworten(BEGRUESSUNG) == (BEGRUESSUNG, None)


def test_konsole_zeigt_begruessung_unveraendert(capsys):
    asyncio.run(TextKanal().bot_sagt(BEGRUESSUNG))
    assert capsys.readouterr().out == f"Bot: {BEGRUESSUNG}\n"


def test_web_kanal_sendet_begruessung_unveraendert(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "erzeuge_client", lambda: object())
    websocket = _FakeWebSocket()
    kanal = webapp.WebIOKanal(websocket, tmp_path / "sitzung")

    asyncio.run(kanal.bot_sagt(BEGRUESSUNG))

    assert websocket.gesendete_nachrichten == [{"typ": "bot", "text": BEGRUESSUNG}]


def test_webapp_nutzt_denselben_einstieg_wie_die_konsole():
    # Die Weboberfläche ruft chat.hauptablauf auf, dessen Einstieg a1_reisewunsch_aeussern ist;
    # es gibt keine zweite, abweichende Begrüßung.
    assert webapp.hauptablauf is chat.hauptablauf
