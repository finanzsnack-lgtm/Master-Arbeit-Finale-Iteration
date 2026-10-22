"""Tests für src/pipeline.py – die reinen, clientlosen Hilfsfunktionen sowie (für feste
Wunschorte) plane_reise() als Ganzes mit dem MockGoogleMapsClient (Beispieldaten, ohne Netz)."""
import pytest

from src.api.google_maps import (
    MockGoogleMapsClient,
    ist_lernaktivitaet_bezogenes_interesse,
    ist_markt_bezogenes_interesse,
    ist_tour_bezogenes_interesse,
)
from src.api.typen import POI, GefundenerOrt, ReiseAlternative
from src.ausgabe.reiseplan import _reservierte_sondertage
from src.fragekatalog.schema import FesterWunschort, ReiseAnfrage, WunschortAnfahrt
from src.fragekatalog.wunschorte import loese_wunschorte_auf
from src.optimierung.kostenschaetzung import schaetze_gesamtkosten
from src.optimierung.verkehrsmittelwahl import BewerteteAlternative
from src.pipeline import (
    _budget_nach_termin,
    _nur_bestaetigte_verkehrsmittel,
    _plane_feste_termine,
    _trenne_beispielrestaurants_ab,
    _trenne_markt_beispiele_ab,
    _trenne_sonderkategorie_ab,
    _volle_optimierungstage,
    plane_reise,
)

# `_trenne_sonderkategorie_ab` prüft ein Prädikat gegen den GANZEN POI (siehe pipeline.py) – die
# Erkennungsfunktionen selbst prüfen nur den `nutzerinteresse`-Text, hier entsprechend gekapselt.
def _ist_tour(poi: POI) -> bool:
    return bool(poi.nutzerinteresse) and ist_tour_bezogenes_interesse(poi.nutzerinteresse)


def _ist_lernaktivitaet(poi: POI) -> bool:
    return bool(poi.nutzerinteresse) and ist_lernaktivitaet_bezogenes_interesse(poi.nutzerinteresse)

_BAHN = BewerteteAlternative(
    alternative=ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500),
    co2_kg=9.5, score=0.1,
)
_AUTO = BewerteteAlternative(
    alternative=ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=250, kosten_euro=120, distanz_km=500),
    co2_kg=25.0, score=0.5,
)
_FERNBUS = BewerteteAlternative(
    alternative=ReiseAlternative(verkehrsmittel="Fernbus", dauer_minuten=450, kosten_euro=45, distanz_km=500),
    co2_kg=12.0, score=0.3,
)
_ALLE = [_BAHN, _AUTO, _FERNBUS]  # bewerte_alternativen sortiert nach Score, Bahn hier "objektiv beste"


def test_nur_bestaetigte_verkehrsmittel_respektiert_explizite_wahl():
    # Regression (Befund: trotz bestätigtem "Auto" wurde im Plan die Bahn ausgewiesen): obwohl Bahn den besten Score hat, muss bei bestätigtem "Auto" NUR
    # Auto übrig bleiben.
    ergebnis = _nur_bestaetigte_verkehrsmittel(_ALLE, ["Auto"])
    assert [b.alternative.verkehrsmittel for b in ergebnis] == ["Auto"]


def test_nur_bestaetigte_verkehrsmittel_erkennt_freitext():
    ergebnis = _nur_bestaetigte_verkehrsmittel(_ALLE, ["am liebsten mit dem Fernbus"])
    assert [b.alternative.verkehrsmittel for b in ergebnis] == ["Fernbus"]


def test_nur_bestaetigte_verkehrsmittel_ohne_treffer_faellt_auf_alle_zurueck():
    # Kein Absturz/keine leere Auswahl bei unklarem Freitext – lieber die volle (weiterhin
    # objektiv bewertete) Liste behalten als eine erfundene Einschränkung.
    ergebnis = _nur_bestaetigte_verkehrsmittel(_ALLE, ["bin mir noch unsicher"])
    assert ergebnis == _ALLE


def test_nur_bestaetigte_verkehrsmittel_mehrere_genannte_bleiben_erhalten():
    ergebnis = _nur_bestaetigte_verkehrsmittel(_ALLE, ["Auto oder Fernbus, beides ok"])
    assert {b.alternative.verkehrsmittel for b in ergebnis} == {"Auto", "Fernbus"}


def _poi(id: int, name: str, x: float, y: float, besuchsklasse: str | None) -> POI:
    return POI(
        id=id, name=name, kategorie="restaurant" if besuchsklasse == "mahlzeit" else "museum",
        x=x, y=y, score=1.0, required_time=60, opening=0, closing=600, besuchsklasse=besuchsklasse,
    )


def test_trenne_beispielrestaurants_ab_entfernt_mahlzeit_pois_aus_der_kandidatenliste():
    # Entscheidung des Product Owners (revidiert): Restaurants sind keine eigenen POIs der Tagesroute.
    # Restaurants dürfen NICHT mehr in der Liste landen, die an Optimierung 1 geht.
    museum = _poi(1, "Museum", 0.0, 0.0, None)
    restaurant = _poi(2, "Restaurant", 0.0, 0.001, "mahlzeit")
    uebrige, beispielrestaurants = _trenne_beispielrestaurants_ab([museum, restaurant], depot_koordinaten=(0.0, 0.0))
    assert uebrige == [museum]
    assert [p.name for p in beispielrestaurants] == ["Restaurant"]


def test_trenne_beispielrestaurants_ab_laesst_cafe_unangetastet():
    cafe = _poi(1, "Café", 0.0, 0.0, "kaffee")
    uebrige, beispielrestaurants = _trenne_beispielrestaurants_ab([cafe], depot_koordinaten=(0.0, 0.0))
    assert uebrige == [cafe]
    assert beispielrestaurants == []


def test_trenne_beispielrestaurants_ab_erfasst_auch_bars():
    # Ergänzt für lokalen Kontakt (F19, Entscheidung des Product Owners): eine "urige Kneipe" landet bei Google
    # häufig unter dem Typ "bar", nicht "restaurant" – ohne diese Ergänzung würden genau die dafür
    # typischen Treffer nicht erscheinen.
    bar = _poi(2, "Kneipe", 0.0, 0.0, "bar")
    uebrige, beispielrestaurants = _trenne_beispielrestaurants_ab([bar], depot_koordinaten=(0.0, 0.0))
    assert uebrige == []
    assert [p.name for p in beispielrestaurants] == ["Kneipe"]


def test_trenne_beispielrestaurants_ab_sortiert_nach_entfernung_zur_unterkunft():
    nah = _poi(1, "Nahes Restaurant", 0.0, 0.001, "mahlzeit")
    fern = _poi(2, "Fernes Restaurant", 0.0, 0.05, "mahlzeit")
    _, beispielrestaurants = _trenne_beispielrestaurants_ab([fern, nah], depot_koordinaten=(0.0, 0.0))
    assert [p.name for p in beispielrestaurants] == ["Nahes Restaurant", "Fernes Restaurant"]


class _FakeClient:
    """Minimaler Fake für `client.ist_barrierefrei(place_id)` (siehe vertraeglichkeit.py-Tests für
    dasselbe Muster)."""

    def __init__(self, status_je_place_id: dict[str, bool | None]):
        self._status = status_je_place_id

    def ist_barrierefrei(self, place_id):
        return self._status.get(place_id)


def _sonder_poi(id: int, name: str, x: float, y: float, nutzerinteresse: str, place_id: str | None = None) -> POI:
    return POI(
        id=id, name=name, kategorie="travel_agency", x=x, y=y, score=1.0, required_time=120,
        opening=0, closing=600, nutzerinteresse=nutzerinteresse, place_id=place_id,
    )


def _tour_poi(id: int, name: str, x: float, y: float, place_id: str | None = None) -> POI:
    return _sonder_poi(id, name, x, y, "geführte Tour", place_id)


def test_trenne_sonderkategorie_ab_entfernt_passende_pois_aus_der_kandidatenliste():
    museum = _poi(1, "Museum", 0.0, 0.0, None)
    tour = _tour_poi(2, "Stadtführung", 0.0, 0.001)
    uebrige, tour_beispiele = _trenne_sonderkategorie_ab(
        [museum, tour], depot_koordinaten=(0.0, 0.0), mobilitaetseinschraenkung_stufe=None,
        client=_FakeClient({}), gehoert_zur_kategorie=_ist_tour,
    )
    assert uebrige == [museum]
    assert [p.name for p in tour_beispiele] == ["Stadtführung"]


def test_trenne_sonderkategorie_ab_ohne_treffer_leer():
    museum = _poi(1, "Museum", 0.0, 0.0, None)
    uebrige, tour_beispiele = _trenne_sonderkategorie_ab(
        [museum], depot_koordinaten=(0.0, 0.0), mobilitaetseinschraenkung_stufe=None,
        client=_FakeClient({}), gehoert_zur_kategorie=_ist_tour,
    )
    assert uebrige == [museum]
    assert tour_beispiele == []


def test_trenne_sonderkategorie_ab_stufe_leicht_prueft_nicht_und_nimmt_naechste_drei():
    touren = [_tour_poi(i, f"Tour {i}", 0.0, i * 0.001) for i in range(1, 6)]  # 5 Kandidaten
    _, tour_beispiele = _trenne_sonderkategorie_ab(
        touren, depot_koordinaten=(0.0, 0.0), mobilitaetseinschraenkung_stufe="leicht",
        client=_FakeClient({}), gehoert_zur_kategorie=_ist_tour,
    )
    assert [p.name for p in tour_beispiele] == ["Tour 1", "Tour 2", "Tour 3"]  # nächste drei, ungeprüft


def test_trenne_sonderkategorie_ab_stufe_stark_verlangt_alle_bestaetigt_barrierefrei():
    touren = [_tour_poi(i, f"Tour {i}", 0.0, i * 0.001, place_id=f"p{i}") for i in range(1, 6)]
    # Nur Tour 2 und Tour 4 sind eindeutig bestätigt barrierefrei, der Rest unbekannt/nicht bestätigt.
    client = _FakeClient({"p2": True, "p4": True})
    _, tour_beispiele = _trenne_sonderkategorie_ab(
        touren, depot_koordinaten=(0.0, 0.0), mobilitaetseinschraenkung_stufe="stark",
        client=client, gehoert_zur_kategorie=_ist_tour,
    )
    # Weniger als 3 werden gezeigt, statt eine nicht bestätigte Tour zu erfinden (Grundprinzip 1).
    assert {p.name for p in tour_beispiele} == {"Tour 2", "Tour 4"}


def test_trenne_sonderkategorie_ab_stufe_mittel_verlangt_mindestens_haelfte_barrierefrei():
    touren = [_tour_poi(i, f"Tour {i}", 0.0, i * 0.001, place_id=f"p{i}") for i in range(1, 6)]
    client = _FakeClient({"p1": True})  # nur die nächste ist bestätigt barrierefrei
    _, tour_beispiele = _trenne_sonderkategorie_ab(
        touren, depot_koordinaten=(0.0, 0.0), mobilitaetseinschraenkung_stufe="mittel",
        client=client, gehoert_zur_kategorie=_ist_tour,
    )
    assert len(tour_beispiele) == 3
    barrierefreie = [p for p in tour_beispiele if p.name == "Tour 1"]
    assert len(barrierefreie) == 1  # die eine bestätigte ist dabei, Rest zur Auffüllung erlaubt


def test_trenne_sonderkategorie_ab_pool_begrenzt_barrierefreiheits_abfragen():
    # Eingeführt nach einem Vorfall im Live-Test (Chat blieb hängen): NICHT jeder Roh-Treffer wird einzeln geprüft, nur der
    # nächstgelegene, begrenzte Pool.
    touren = [_tour_poi(i, f"Tour {i}", 0.0, i * 0.001, place_id=f"p{i}") for i in range(1, 21)]  # 20 Treffer
    abgefragte_ids: list[str] = []

    class _ZaehlenderClient:
        def ist_barrierefrei(self, place_id):
            abgefragte_ids.append(place_id)
            return True

    _trenne_sonderkategorie_ab(
        touren, depot_koordinaten=(0.0, 0.0), mobilitaetseinschraenkung_stufe="stark",
        client=_ZaehlenderClient(), gehoert_zur_kategorie=_ist_tour,
    )
    assert len(abgefragte_ids) <= 8  # _SONDERKATEGORIE_KANDIDATEN_POOL, NICHT alle 20 Roh-Treffer


def test_trenne_sonderkategorie_ab_erkennt_lernaktivitaeten_getrennt_von_touren():
    kochkurs = _sonder_poi(1, "Kochkurs Wien", 0.0, 0.0, "Kochkurs")
    tour = _tour_poi(2, "Stadtführung", 0.0, 0.001)
    uebrige, lernaktivitaet_beispiele = _trenne_sonderkategorie_ab(
        [kochkurs, tour], depot_koordinaten=(0.0, 0.0), mobilitaetseinschraenkung_stufe=None,
        client=_FakeClient({}), gehoert_zur_kategorie=_ist_lernaktivitaet,
    )
    # Die Tour bleibt übrig – sie gehört NICHT zur Lernaktivitäts-Kategorie, wird hier also nicht abgetrennt.
    assert [p.name for p in uebrige] == ["Stadtführung"]
    assert [p.name for p in lernaktivitaet_beispiele] == ["Kochkurs Wien"]


def _markt_poi(id: int, name: str, x: float, y: float) -> POI:
    return _sonder_poi(id, name, x, y, "Wochenmarkt")


def _cafe_poi(id: int, name: str, x: float, y: float) -> POI:
    return POI(
        id=id, name=name, kategorie="cafe", x=x, y=y, score=1.0, required_time=45,
        opening=0, closing=600, besuchsklasse="kaffee",
    )


def test_trenne_markt_beispiele_ab_erfasst_maerkte_und_cafes():
    museum = _poi(1, "Museum", 0.0, 0.0, None)
    markt = _markt_poi(2, "Wochenmarkt Zentrum", 0.0, 0.001)
    cafe = _cafe_poi(3, "Café Central", 0.0, 0.002)
    uebrige, markt_beispiele = _trenne_markt_beispiele_ab([museum, markt, cafe], depot_koordinaten=(0.0, 0.0))
    assert uebrige == [museum]
    assert {p.name for p in markt_beispiele} == {"Wochenmarkt Zentrum", "Café Central"}


def test_trenne_markt_beispiele_ab_sortiert_nach_entfernung():
    fern = _markt_poi(1, "Ferner Markt", 0.0, 0.05)
    nah = _markt_poi(2, "Naher Markt", 0.0, 0.001)
    _, markt_beispiele = _trenne_markt_beispiele_ab([fern, nah], depot_koordinaten=(0.0, 0.0))
    assert [p.name for p in markt_beispiele] == ["Naher Markt", "Ferner Markt"]


def test_ist_markt_bezogenes_interesse_erkennt_wochenmarkt():
    assert ist_markt_bezogenes_interesse("Wochenmarkt") is True
    assert ist_markt_bezogenes_interesse("Flohmarkt") is True
    assert ist_markt_bezogenes_interesse("Museum") is False


# -- Feste Wunschorte: Tagwahl, Budgetkürzung, Planung (außerhalb von Optimierung 1) ----------------


def _wunschort(name="Wunschort", dauer=120, uhrzeit=None, weg=30, place_id="pid-wunsch", preisniveau=None):
    return FesterWunschort(
        rohname=name,
        ort=GefundenerOrt(name=name, adresse="Adresse 1", x=48.14, y=11.58, place_id=place_id, preisniveau=preisniveau),
        dauer_minuten=dauer, uhrzeit_minuten=uhrzeit,
        anfahrt=WunschortAnfahrt(verkehrsmittel="zu Fuß", dauer_minuten=weg, quelle="distance_matrix", modus="walking"),
        anfahrt_geprueft_ab=(48.1370, 11.5760),
    )


def test_volle_optimierungstage_gleiche_definition_wie_lokaler_kontakt():
    # 5 Optimierungstage ohne Sondertag: Tag 1 (Anreise) und Tag 5 (Abreise) sind nicht voll.
    assert _volle_optimierungstage(5, reservierte_tage=0) == [1, 2, 3]
    # Mit Sondertag dahinter ist der Abreisetag der Sondertag -> alle außer Tag 1 voll.
    assert _volle_optimierungstage(3, reservierte_tage=2) == [1, 2]
    assert _volle_optimierungstage(2, reservierte_tage=0) == []
    assert _volle_optimierungstage(1, reservierte_tage=0) == []


def test_budget_nach_termin_ohne_uhrzeit_kuerzt_dauer_und_beide_wege():
    assert _budget_nach_termin(600, _wunschort(dauer=120, weg=30), 1, 540, 0) == 600 - 180
    # Untergrenze 0: der Tag enthält dann nur den Termin.
    assert _budget_nach_termin(100, _wunschort(dauer=120, weg=30), 1, 540, 0) == 0


def test_budget_nach_termin_mit_uhrzeit_rechenbeispiel():
    # 15:00, Hinweg 30 Min., Tagesstart 9:00 -> (900 − 30) − 540 = 330 Min.
    assert _budget_nach_termin(600, _wunschort(uhrzeit=900, weg=30), 1, 540, 0) == 330
    # Zusätzlich lokaler Kontakt (Budget vorher schon um 120 gekürzt): 330 − 120 = 210.
    assert _budget_nach_termin(480, _wunschort(uhrzeit=900, weg=30), 1, 540, 120) == 210
    # Nie mehr als das bisherige Budget, nie unter 0.
    assert _budget_nach_termin(200, _wunschort(uhrzeit=1200, weg=30), 1, 540, 0) == 200
    assert _budget_nach_termin(600, _wunschort(uhrzeit=540, weg=30), 1, 540, 0) == 0


def test_budget_nach_termin_ohne_tagesstart_oder_am_anreisetag_ohne_uhrzeitregel():
    # Ohne F20-Tagesstart bzw. am Anreisetag (kein realer Tagesstart) wird keine Uhrzeit angenommen.
    assert _budget_nach_termin(600, _wunschort(uhrzeit=900, dauer=120, weg=30), 1, None, 0) == 420
    assert _budget_nach_termin(600, _wunschort(uhrzeit=900, dauer=120, weg=30), 0, 540, 0) == 420


def test_plane_feste_termine_verschiedene_volle_tage_dann_reihum():
    budgets = [240, 480, 480, 480]
    termine, hinweise, debug = _plane_feste_termine(
        [_wunschort("A", place_id="a"), _wunschort("B", place_id="b"), _wunschort("C", place_id="c")],
        budgets, volle_tage=[1, 2], abreise_index=3, tagesstart_minuten=None, lokaler_kontakt_tage=set(),
    )
    assert [(t.tag_nr, t.wunschort.rohname) for t in termine] == [(2, "A"), (3, "B"), (2, "C")]
    # Kumulative Kürzung am doppelt belegten Tag 2: 480 − 180 − 180.
    assert budgets == [240, 120, 300, 480]
    assert hinweise == []
    assert debug[2].begruendung == "voller Tag, reihum ein weiteres Mal belegt"
    assert (debug[0].budget_vorher_minuten, debug[0].budget_nachher_minuten) == (480, 300)


def test_plane_feste_termine_ohne_vollen_tag_abreisetag_dann_anreisetag_dann_hinweis():
    # 2-Tage-Reise: kein voller Tag -> Abreisetag, wenn das Budget reicht.
    budgets = [240, 480]
    termine, _, _ = _plane_feste_termine([_wunschort()], budgets, [], 1, None, set())
    assert termine[0].tag_nr == 2 and budgets == [240, 300]

    # Abreisetag reicht nicht, Tag 1 schon.
    budgets = [240, 100]
    termine, _, _ = _plane_feste_termine([_wunschort()], budgets, [], 1, None, set())
    assert termine[0].tag_nr == 1 and budgets == [60, 100]

    # Passt nirgends -> nicht eingeplant, ehrlicher Hinweis, Budgets unverändert.
    budgets = [100, 100]
    termine, hinweise, debug = _plane_feste_termine([_wunschort("Zu lang")], budgets, [], 1, None, set())
    assert termine == [] and budgets == [100, 100]
    assert "„Zu lang“ konnte nicht fest eingeplant werden" in hinweise[0]
    assert debug[0].tag_nr is None


def test_kostenschaetzung_beruecksichtigt_feste_termine():
    ohne, _ = schaetze_gesamtkosten(50.0, 50.0, 2, 2, [], 3)
    mit, unvollstaendig = schaetze_gesamtkosten(
        50.0, 50.0, 2, 2, [], 3, feste_termine_preisniveaus=[2, None], feste_termine_anfahrtskosten_euro=[40.0, 0.0],
    )
    assert mit == pytest.approx(ohne + 12.0 + 40.0)
    assert unvollstaendig is False
    _, unvollstaendig = schaetze_gesamtkosten(50.0, 50.0, 2, 2, [], 3, feste_termine_anfahrtskosten_euro=[None])
    assert unvollstaendig is True


# Integration mit MockGoogleMapsClient (Beispieldaten, ohne Netz/Kosten). Das ILS arbeitet mit
# festem Zufalls-Seed, die Ergebnisse sind daher reproduzierbar.

_UNTERKUNFT_MOCK = (48.1370, 11.5760)  # Mock-Unterkunft "Hotel Zentral"


def _mock_anfrage(**zusatz) -> ReiseAnfrage:
    werte = dict(
        name="Test", reisezeitraum_rohtext="5 Tage", zielregionen=["Zielregion"], wohnort="Wohnort",
        budget_gesamt=1500.0, verkehrsmittel_praeferenz=["Bahn"], lokaler_transport_praeferenz="zu Fuß",
        unterkunft_anforderungen="zentral", aktivitaeten_interessen=["Kultur", "Natur"],
        unterkunft_koordinaten=_UNTERKUNFT_MOCK, unterkunft_name="Hotel Zentral",
    )
    werte.update(zusatz)
    return ReiseAnfrage(**werte)


def _mit_wunschorten(anfrage: ReiseAnfrage, eintraege: list[dict], client) -> ReiseAnfrage:
    anfrage.feste_wunschorte, _ = loese_wunschorte_auf(eintraege, anfrage, client)
    assert len(anfrage.feste_wunschorte) == len(eintraege)
    return anfrage


def _alle_besuchten_place_ids(plan) -> set:
    return {besuch.poi.place_id for route in plan.tagesrouten for besuch in route.besuche}


def test_plane_reise_5_tage_tour_lernaktivitaet_und_zwei_termine():
    client = MockGoogleMapsClient()
    anfrage = _mit_wunschorten(
        _mock_anfrage(aktivitaeten_interessen=["Kultur-Tour", "Kulinarik-Kurs", "Natur"]),
        [{"name": "Altstadt-Museum", "dauer_minuten": 90}, {"name": "Biergarten"}], client,
    )
    plan, _, debug = plane_reise(anfrage, client)

    assert len(plan.tagesrouten) == 5
    sondertage = set(_reservierte_sondertage(plan))
    assert sondertage == {4, 5}  # Tour-Tag 4, Lernaktivitäts-Tag 5
    termin_tage = [t.tag_nr for t in plan.feste_termine]
    assert termin_tage == [2, 3]  # verschiedene volle Tage
    assert not set(termin_tage) & ({1, 5} | sondertage)
    # Budgetkürzung im Debug: Dauer + Hin- + Rückweg, TOPTW-Instanz enthält die Termine nicht.
    museum_debug, biergarten_debug = debug.feste_termine
    weg_museum = anfrage.feste_wunschorte[0].anfahrt.dauer_minuten
    assert museum_debug.budget_nachher_minuten == museum_debug.budget_vorher_minuten - (90 + 2 * weg_museum)
    assert biergarten_debug.tag_nr == 3
    assert not {"mock-poi-1", "mock-poi-8"} & {poi.place_id for poi in debug.toptw_instanz.pois}
    assert plan.feste_termine_hinweise == []


def test_plane_reise_termin_stapelt_mit_lokalem_kontakt():
    client = MockGoogleMapsClient()
    anfrage = _mit_wunschorten(_mock_anfrage(lokaler_kontakt_wichtig=True), [{"name": "Biergarten"}], client)
    plan, _, debug = plane_reise(anfrage, client)

    [eintrag] = debug.feste_termine
    basis = debug.toptw_instanz.tagesbudget_minuten
    weg = anfrage.feste_wunschorte[0].anfahrt.dauer_minuten
    assert eintrag.tag_nr == 2
    assert eintrag.budget_vorher_minuten == basis - 120  # Mittagsblock lokaler Kontakt
    assert eintrag.budget_nachher_minuten == basis - 120 - (120 + 2 * weg)


def test_plane_reise_termin_mit_uhrzeit_begrenzt_budget_des_tages():
    client = MockGoogleMapsClient()
    anfrage = _mit_wunschorten(
        _mock_anfrage(tagesstart_minuten=540, tagesende_minuten=1140),
        [{"name": "Biergarten", "uhrzeit_minuten": 900, "dauer_minuten": 60}], client,
    )
    plan, _, debug = plane_reise(anfrage, client)

    [eintrag] = debug.feste_termine
    weg = anfrage.feste_wunschorte[0].anfahrt.dauer_minuten
    assert eintrag.budget_vorher_minuten == 600
    assert eintrag.budget_nachher_minuten == 900 - weg - 540
    [termin] = plan.feste_termine
    assert termin.am_tagesende is False and termin.wunschort.uhrzeit_minuten == 900


def test_plane_reise_2_tage_ohne_vollen_tag_nutzt_abreisetag():
    client = MockGoogleMapsClient()
    anfrage = _mit_wunschorten(_mock_anfrage(reisezeitraum_rohtext="2 Tage"), [{"name": "Altstadt-Museum"}], client)
    plan, _, debug = plane_reise(anfrage, client)

    assert len(plan.tagesrouten) == 2
    assert [t.tag_nr for t in plan.feste_termine] == [2]
    assert debug.feste_termine[0].begruendung == "kein voller Tag: Abreisetag vor der Rückreise"
    assert plan.feste_termine[0].am_tagesende is True


def test_plane_reise_kein_doppelbesuch_des_wunschorts():
    client = MockGoogleMapsClient()
    # "Kultur" liefert das Altstadt-Museum (mock-poi-1) als gewöhnlichen Kandidaten.
    ohne_termin, _, debug_ohne = plane_reise(_mock_anfrage(), client)
    assert "mock-poi-1" in {poi.place_id for poi in debug_ohne.ausgewaehlte_pois}

    anfrage = _mit_wunschorten(_mock_anfrage(), [{"name": "Altstadt-Museum"}], client)
    plan, _, debug = plane_reise(anfrage, client)
    assert "mock-poi-1" not in {poi.place_id for poi in debug.ausgewaehlte_pois}
    assert "mock-poi-1" not in _alle_besuchten_place_ids(plan)
    assert "mock-poi-1" not in {poi.place_id for poi in plan.weitere_aktivitaeten_empfehlungen}
    assert [t.wunschort.ort.place_id for t in plan.feste_termine] == ["mock-poi-1"]


def test_plane_reise_wunschort_ohne_landverbindung_wird_ehrlich_nicht_eingeplant():
    client = MockGoogleMapsClient()
    anfrage = _mock_anfrage()
    ohne_verbindung = _wunschort("Unerreichbar", place_id="pid-fern")
    ohne_verbindung.anfahrt = None  # geprüft (anfahrt_geprueft_ab gesetzt), aber keine Verbindung
    anfrage.feste_wunschorte = [ohne_verbindung]

    plan, _, debug = plane_reise(anfrage, client)
    referenz, _, _ = plane_reise(_mock_anfrage(), client)

    assert plan.feste_termine == []
    assert "„Unerreichbar“ konnte nicht fest eingeplant werden" in plan.feste_termine_hinweise[0]
    assert "Flüge sind ausgeschlossen" in plan.feste_termine_hinweise[0]
    assert debug.feste_termine[0].tag_nr is None
    # Keine Auswirkung auf die übrige Planung.
    assert plan.tagesrouten == referenz.tagesrouten


def test_plane_reise_wunschort_ohne_unterkunftskoordinaten_nicht_eingeplant():
    client = MockGoogleMapsClient()
    anfrage = _mock_anfrage(unterkunft_koordinaten=None)
    anfrage.feste_wunschorte = [_wunschort("Ohne Unterkunft")]
    plan, _, _ = plane_reise(anfrage, client)
    assert plan.feste_termine == []
    assert "ohne bestätigte Unterkunft" in plan.feste_termine_hinweise[0]


def test_plane_reise_ohne_feste_wunschorte_regression():
    client = MockGoogleMapsClient()
    plan, _, debug = plane_reise(_mock_anfrage(lokaler_kontakt_wichtig=True), client)
    assert plan.feste_termine == [] and plan.feste_termine_hinweise == []
    assert debug.feste_termine == []
    # Eine leere Liste fester Wunschorte ergibt exakt denselben Plan wie eine Anfrage ohne das Feld.
    anfrage_leer = _mock_anfrage(lokaler_kontakt_wichtig=True)
    anfrage_leer.feste_wunschorte = []
    plan_leer, _, _ = plane_reise(anfrage_leer, client)
    assert plan_leer == plan


def test_plane_reise_barrierefreiheit_des_termins_nur_bei_mittel_oder_stark():
    client = MockGoogleMapsClient()  # Mock: Biergarten (mock-poi-8) ist nicht barrierefrei
    anfrage = _mit_wunschorten(_mock_anfrage(mobilitaetseinschraenkung_stufe="mittel"), [{"name": "Biergarten"}], client)
    plan, _, _ = plane_reise(anfrage, client)
    assert [t.tag_nr for t in plan.feste_termine] == [2]  # nicht ausgeschlossen
    assert any("„Biergarten“ ist laut Google Places nicht barrierefrei" in h for h in plan.einschraenkungshinweise)

    anfrage = _mit_wunschorten(_mock_anfrage(mobilitaetseinschraenkung_stufe="leicht"), [{"name": "Biergarten"}], client)
    plan, _, _ = plane_reise(anfrage, client)
    assert not any("Biergarten" in h for h in plan.einschraenkungshinweise)


def test_plane_reise_kosten_enthalten_termin_und_anfahrt():
    client = MockGoogleMapsClient()
    # Schloss Fernblick liegt weit weg: Anfahrt über reisealternativen (Mock: Bahn 89 €).
    anfrage = _mit_wunschorten(_mock_anfrage(), [{"name": "Schloss Fernblick"}], client)
    plan, _, _ = plane_reise(anfrage, client)

    [termin] = plan.feste_termine
    anfahrt = termin.wunschort.anfahrt
    assert anfahrt.quelle == "reisealternativen" and anfahrt.kosten_euro_einfach == 89.0
    erwartet, _ = schaetze_gesamtkosten(
        plan.hinreise.alternative.kosten_euro, plan.rueckreise.alternative.kosten_euro, None, naechte=4,
        eingeplante_pois=[b.poi for r in plan.tagesrouten for b in r.besuche], tage=5,
        feste_termine_preisniveaus=[2], feste_termine_anfahrtskosten_euro=[178.0],
    )
    assert plan.geschaetzte_kosten_euro == pytest.approx(erwartet)


def test_pruefe_planung_szenario_feste_wunschorte_laedt_und_plant(tmp_path, monkeypatch, capsys):
    import json

    import pruefe_planung

    # Die mitgelieferte Szenario-Datei (echte Ortsnamen für einen Live-Lauf) ist gültig ...
    anfrage, rohe_wunschorte = pruefe_planung.lade_anfrage("smoketest_feste_wunschorte")
    assert anfrage.feste_wunschorte == []  # Auflösung erst nach der Unterkunftssuche in main()
    assert [e["name"] for e in rohe_wunschorte] == ["Deutsches Museum München", "Schloss Neuschwanstein"]

    # ... und der Ablauf in main() funktioniert im Mock-Modus mit Beispiel-Orten, ohne Netz und ohne
    # Dateien im Projekt anzulegen.
    testfall = dict(json.loads((pruefe_planung.TESTFAELLE_VERZEICHNIS / "smoketest_feste_wunschorte.json").read_text(encoding="utf-8")))
    testfall.update(zielregionen=["Zielregion"], wohnort="Wohnort", feste_wunschorte=[
        {"name": "Altstadt-Museum", "dauer_minuten": 90}, {"name": "Schloss Fernblick", "uhrzeit_minuten": 900},
    ])
    (tmp_path / "mock_wunschorte.json").write_text(json.dumps(testfall), encoding="utf-8")
    monkeypatch.setattr(pruefe_planung, "TESTFAELLE_VERZEICHNIS", tmp_path)
    monkeypatch.setattr(pruefe_planung, "_ERGEBNISSE_VERZEICHNIS", tmp_path / "ergebnisse")
    monkeypatch.setattr(pruefe_planung, "PROTOKOLL_VERZEICHNIS", tmp_path / "protokolle")
    monkeypatch.setattr(pruefe_planung, "erzeuge_client", MockGoogleMapsClient)
    monkeypatch.setattr("sys.argv", ["pruefe_planung.py", "mock_wunschorte"])

    pruefe_planung.main()

    ausgabe = capsys.readouterr().out
    assert "[Feste Wunschorte]" in ausgabe
    assert "'Schloss Fernblick' liegt weit von der Unterkunft entfernt" in ausgabe
    debug_text = (tmp_path / "protokolle" / "planung_mock_wunschorte_debug.txt").read_text(encoding="utf-8")
    assert "--- 6. FESTE WUNSCHORTE" in debug_text
    assert "Altstadt-Museum: Tag 2" in debug_text
    assert "Schloss Fernblick: Tag 3" in debug_text


def test_plane_reise_overpass_kandidat_mit_gleicher_ursprungs_id_bleibt_erhalten(monkeypatch):
    # Station 42: Der Overpass-Treffer trägt dieselbe Ursprungs-id wie der Mock-Places-POI
    # "Altstadt-Museum" (id=1). Jeder ausgewählte Kandidat muss danach entweder eingeplant sein oder
    # unter den weiteren Empfehlungen stehen, keiner darf über eine geteilte id verschwinden.
    class _FakeOverpassClient:
        def suche_spezial_pois(self, koordinaten, aktivitaet):
            return [POI(id=1, name="Kletterfels Testwand", kategorie="klettern", x=48.1380, y=11.5760,
                        score=1.0, required_time=60, opening=0, closing=1440, quelle="osm_overpass",
                        nutzerinteresse=aktivitaet)]

    monkeypatch.setattr("src.datenaufbereitung.poi_sammlung.erzeuge_overpass_client", _FakeOverpassClient)
    anfrage = _mock_anfrage(
        aktivitaeten_interessen=["Kultur", "Natur", "Klettern"], aktivitaeten_mit_spezialrecherche=["Klettern"],
    )
    plan, _, debug = plane_reise(anfrage, MockGoogleMapsClient())

    ausgewaehlt = debug.ausgewaehlte_pois
    assert "Kletterfels Testwand" in {poi.name for poi in ausgewaehlt}
    assert len({poi.id for poi in debug.rohe_pois}) == len(debug.rohe_pois)
    eingeplant = [besuch.poi.name for route in plan.tagesrouten for besuch in route.besuche]
    empfohlen = [poi.name for poi in plan.weitere_aktivitaeten_empfehlungen]
    assert sorted(eingeplant + empfohlen) == sorted(poi.name for poi in ausgewaehlt)
