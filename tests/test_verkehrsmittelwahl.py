"""Tests für Optimierung 2 (gewichtete Verkehrsmittelwahl) und den Nachhaltigkeits-Nudge."""
from src.api.typen import ReiseAlternative
from src.optimierung.verkehrsmittelwahl import bewerte_alternativen, nachhaltigkeits_nudge, nur_bestaetigte_verkehrsmittel


def test_bahn_wird_bei_gleicher_zeit_und_kosten_wegen_co2_bevorzugt():
    alternativen = [
        ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=300, kosten_euro=80, distanz_km=500),
    ]
    bewertete = bewerte_alternativen(alternativen)
    assert bewertete[0].alternative.verkehrsmittel == "Bahn"


def test_nudge_wird_erzeugt_wenn_bahn_langsamer_aber_sauberer_ist():
    alternativen = [
        ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=240, kosten_euro=60, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500),
    ]
    bewertete = bewerte_alternativen(alternativen)
    nudge = nachhaltigkeits_nudge(bewertete)
    assert nudge is not None
    assert "Bahn" in nudge


def test_kein_nudge_wenn_bahn_bereits_die_beste_option_ist():
    alternativen = [
        ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=200, kosten_euro=50, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=300, kosten_euro=80, distanz_km=500),
    ]
    bewertete = bewerte_alternativen(alternativen)
    assert nachhaltigkeits_nudge(bewertete) is None


def test_nur_bestaetigte_verkehrsmittel_ist_gemeinsame_regel_fuer_pipeline_und_wunschorte():
    # Die F13-Auswahl liegt an einer Stelle; pipeline.py leitet nur weiter (siehe dort).
    from src.pipeline import _nur_bestaetigte_verkehrsmittel

    alternativen = [
        ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=250, kosten_euro=120, distanz_km=500),
    ]
    bewertete = bewerte_alternativen(alternativen)
    assert [b.alternative.verkehrsmittel for b in nur_bestaetigte_verkehrsmittel(bewertete, ["Auto"])] == ["Auto"]
    assert nur_bestaetigte_verkehrsmittel(bewertete, ["unklar"]) == bewertete
    assert _nur_bestaetigte_verkehrsmittel(bewertete, ["Auto"]) == nur_bestaetigte_verkehrsmittel(bewertete, ["Auto"])


def test_nudge_nennt_bestbewertete_alternative_als_bezugsgroesse():
    alternativen = [
        ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=240, kosten_euro=60, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500),
    ]
    nudge = nachhaltigkeits_nudge(bewerte_alternativen(alternativen))
    assert nudge.startswith("Die Bahn braucht nur 60 Minuten länger, spart aber ")
    assert "gegenüber der bestbewerteten Alternative (Auto)" in nudge
    assert "schnellsten" not in nudge


def test_nudge_ohne_negative_minuten_wenn_bahn_schneller_als_bestbewertete_ist():
    # Bahn ist schneller als der Fernbus, liegt aber wegen der deutlich höheren Kosten hinter ihm
    # (Auto ist am schnellsten, aber wegen CO2 und Kosten am schlechtesten bewertet). Vorher entstand
    # hier "Die Bahn braucht nur -60 Minuten länger".
    alternativen = [
        ReiseAlternative(verkehrsmittel="Fernbus", dauer_minuten=300, kosten_euro=15, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=240, kosten_euro=400, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=200, kosten_euro=300, distanz_km=500),
    ]
    bewertete = bewerte_alternativen(alternativen)
    assert bewertete[0].alternative.verkehrsmittel == "Fernbus"
    nudge = nachhaltigkeits_nudge(bewertete)
    assert nudge.startswith("Die Bahn ist sogar 60 Minuten schneller und spart ")
    assert "-" not in nudge
    assert "(Fernbus)" in nudge


def test_nudge_bei_gleicher_fahrzeit():
    alternativen = [
        ReiseAlternative(verkehrsmittel="Fernbus", dauer_minuten=300, kosten_euro=20, distanz_km=500),
        ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=150, distanz_km=500),
    ]
    nudge = nachhaltigkeits_nudge(bewerte_alternativen(alternativen))
    assert nudge.startswith("Die Bahn ist gleich schnell und spart ")
