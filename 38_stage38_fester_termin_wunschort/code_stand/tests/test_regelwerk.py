"""Tests für den Regelwerk-/Systemprompt-Text (src/fragekatalog/regelwerk.py): prüft, dass die
Iteration-2-Regeln zu Formatierung, Schnellantworten-Zeile und Quellenlisten im erzeugten Prompt
enthalten sind. Ob das LLM sie befolgt, lässt sich nur im Live-Test beobachten."""
from src.fragekatalog.regelwerk import baue_regelwerk_text


def test_regelwerk_enthaelt_formatierungsregel():
    text = baue_regelwerk_text()
    assert "FORMATIERUNG" in text
    assert "nur **fett** und einfache - Aufzählungen, keine Überschriften (#), keine Tabellen" in text


def test_regelwerk_schnellantworten_zeile_ist_immer_die_letzte_zeile():
    text = baue_regelwerk_text()
    assert "Die Schnellantworten-Zeile ist IMMER die allerletzte Zeile" in text
    assert "danach folgt NICHTS mehr" in text


def test_regelwerk_verbietet_quellenliste_und_behaelt_kennzeichnungspflicht():
    text = baue_regelwerk_text()
    assert "KEINE Quellenliste" in text
    assert '"Sources:"' in text
    assert "keine Linkliste" in text
    # Die bestehende Pflicht, Websuch-Ergebnisse als Recherche zu kennzeichnen, bleibt erhalten.
    assert "Kennzeichne Websuch-Ergebnisse im Gespräch erkennbar" in text
    assert "IM FLIESSTEXT" in text
