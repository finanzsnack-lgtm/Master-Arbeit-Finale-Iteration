"""Tests für die CO2-Emissionsfaktoren (src/optimierung/emissionsfaktoren.py)."""
import pytest

from src.optimierung.emissionsfaktoren import co2_kg


def test_auto_hat_deutlich_hoeheren_faktor_als_bahn():
    # Kernaussage des Nachhaltigkeits-Nudges (ARCHITEKTUR.md, Grundprinzip 5): Auto muss bei gleicher
    # Distanz klar mehr CO2 verursachen als Bahn.
    distanz_km = 1000
    assert co2_kg("auto", distanz_km) > co2_kg("bahn", distanz_km)


def test_unbekanntes_verkehrsmittel_wirft_fehler_statt_zu_erfinden():
    with pytest.raises(ValueError):
        co2_kg("rakete", 100)


# -- Einordnung der CO2-Menge von Hin- und Rückreise (Demo-Feedback, Station 42) --

from src.optimierung.emissionsfaktoren import (  # noqa: E402
    CO2_GRENZE_GENUEGSAM_KG,
    CO2_GRENZE_MITTEL_KG,
    co2_einstufung,
)


@pytest.mark.parametrize(
    ("co2_kg_gesamt", "stufe", "bezeichnung"),
    [
        (0.0, "genuegsam", "genügsam"),
        (50.0, "genuegsam", "genügsam"),  # Grenzwert gehört zur niedrigeren Stufe
        (50.1, "mittel", "mittel"),
        (150.0, "mittel", "mittel"),  # Grenzwert gehört zur niedrigeren Stufe
        (150.1, "co2_lastig", "CO₂-lastig"),
    ],
)
def test_co2_einstufung_grenzwerte(co2_kg_gesamt, stufe, bezeichnung):
    einstufung = co2_einstufung(co2_kg_gesamt)
    assert einstufung.stufe == stufe
    assert einstufung.bezeichnung == bezeichnung


def test_co2_einstufung_ohne_wert_ergibt_keine_ampel():
    assert co2_einstufung(None) is None


def test_co2_einstufung_hinweis_nennt_schwellen_und_einschraenkungen():
    assert (CO2_GRENZE_GENUEGSAM_KG, CO2_GRENZE_MITTEL_KG) == (50.0, 150.0)
    hinweis = co2_einstufung(10.0).hinweis
    assert "nur An- und Abreise" in hinweis
    assert "grobe schätzung" in hinweis.lower()
    assert "genügsam bis 50 kg" in hinweis
    assert "mittel über 50 bis 150 kg" in hinweis
    assert "CO₂-lastig über 150 kg" in hinweis
