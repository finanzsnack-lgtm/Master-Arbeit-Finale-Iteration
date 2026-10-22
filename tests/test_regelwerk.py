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


def test_regelwerk_enthaelt_regel_fuer_feste_wunschorte():
    text = baue_regelwerk_text()
    assert "FESTE WUNSCHORTE" in text
    assert "`feste_wunschorte`" in text
    # Nur bei ausdrücklicher Aussage, nicht proaktiv erfragt.
    assert "AUSDRÜCKLICH" in text
    assert "Frage NICHT proaktiv nach solchen Orten" in text
    # Kurze Nachfrage zur Dauer mit Standardwert aus derselben Konstante wie im Code.
    assert "dann gelten 120 Minuten" in text
    assert "Lege NIE selbst eine Uhrzeit fest" in text
    assert "VOLLSTÄNDIGE Liste" in text
    # Bestätigung des gefundenen Ortes und ehrliche Meldung bei "nicht gefunden".
    assert "Name und Adresse des gefundenen Ortes" in text
    assert "erfinde weder" in text


def test_regelwerk_f16_hinweis_verweist_auf_feste_wunschorte():
    text = baue_regelwerk_text()
    assert "gib ihn zusätzlich im Argument feste_wunschorte mit" in text


def test_regelwerk_wunschorte_nachhaltigkeitshinweis_und_verzicht():
    text = baue_regelwerk_text()
    # Schwelle aus derselben Konstante wie im Code.
    assert "mehr als\n    60 Minuten (einfache Strecke)" in text
    assert "frage ausdrücklich, ob der Ort trotzdem bleiben soll" in text
    assert "Verzichtet er, speichere feste_wunschorte ohne diesen Ort erneut" in text
    assert "CO₂ nur als grobe\n    Schätzung" in text
    assert "Flüge sind\n    ausgeschlossen" in text
