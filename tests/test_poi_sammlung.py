"""Tests für src/datenaufbereitung/poi_sammlung.py (Google Places + optionale Overpass-Spezialrecherche)."""
from src.api.overpass import MockOverpassClient
from src.api.typen import POI
from src.datenaufbereitung.poi_sammlung import sammle_pois


class _FakeMapsClient:
    """Minimaler Stub: nur die von sammle_pois genutzten Methoden."""

    def __init__(self, pois: list[POI]):
        self._pois = pois

    def suche_pois(self, ort: str, kategorien: list[str], radius_meter: int = 3000, ernaehrung_einschraenkungen: list[str] | None = None) -> list[POI]:
        return list(self._pois)

    def geocode(self, adresse: str) -> tuple[float, float]:
        return (48.0, 11.0)


def test_sammle_pois_ruft_overpass_nicht_auf_ohne_spezialrecherche():
    client = _FakeMapsClient([POI(id=1, name="Museum", kategorie="museum", x=1, y=1, score=1.0,
                                   required_time=60, opening=0, closing=600)])
    ergebnis = sammle_pois("Rom", ["Kultur"], [], client)
    assert [poi.name for poi in ergebnis] == ["Museum"]


def test_sammle_pois_ergaenzt_overpass_treffer_bei_spezialrecherche():
    client = _FakeMapsClient([POI(id=1, name="Museum", kategorie="museum", x=1, y=1, score=1.0,
                                   required_time=60, opening=0, closing=600)])
    ergebnis = sammle_pois("Rom", ["Kultur", "Klettern"], ["Klettern"], client, overpass_client=MockOverpassClient())
    namen = [poi.name for poi in ergebnis]
    assert "Museum" in namen
    assert "Klettergarten Musterfelsen" in namen
    treffer = next(poi for poi in ergebnis if poi.name == "Klettergarten Musterfelsen")
    assert treffer.quelle == "osm_overpass"
    assert treffer.schwierigkeitsgrad == "6a"


def test_sammle_pois_dedupliziert_gleichnamige_treffer():
    # Places und Overpass könnten denselben Ort liefern (z.B. Kletterhalle als "gym").
    client = _FakeMapsClient([POI(id=1, name="Klettergarten Musterfelsen", kategorie="gym", x=1, y=1,
                                   score=1.0, required_time=60, opening=0, closing=600)])
    ergebnis = sammle_pois("Rom", ["Klettern"], ["Klettern"], client, overpass_client=MockOverpassClient())
    namen = [poi.name for poi in ergebnis]
    assert namen.count("Klettergarten Musterfelsen") == 1


# Eindeutige ids (Station 42): Places- und Overpass-Treffer werden von ihren Clients jeweils ab 1
# nummeriert. Die folgenden Tests bilden genau diese Überschneidung nach (beide Quellen liefern id=1).

class _FakeOverpassClient:
    """Liefert einen Overpass-Treffer mit derselben id wie der Places-Treffer aus `_places_poi`."""

    def suche_spezial_pois(self, koordinaten: tuple[float, float], aktivitaet: str) -> list[POI]:
        return [POI(id=1, name="Kletterfels Testwand", kategorie="klettern", x=48.01, y=11.01, score=1.0,
                    required_time=60, opening=0, closing=1440, quelle="osm_overpass", nutzerinteresse=aktivitaet)]


def _places_poi() -> POI:
    return POI(id=1, name="Museum", kategorie="museum", x=48.0, y=11.0, score=1.0,
               required_time=60, opening=0, closing=1440, place_id="pid-museum", nutzerinteresse="Kultur")


def _gesammelt_mit_gleicher_ursprungs_id() -> list[POI]:
    return sammle_pois("Rom", ["Kultur", "Klettern"], ["Klettern"], _FakeMapsClient([_places_poi()]),
                       overpass_client=_FakeOverpassClient())


def test_sammle_pois_vergibt_eindeutige_ids_bei_gleicher_ursprungs_id():
    ergebnis = _gesammelt_mit_gleicher_ursprungs_id()
    # Reihenfolge und Inhalte bleiben erhalten, nur die id wird fortlaufend neu vergeben.
    assert [(poi.name, poi.quelle) for poi in ergebnis] == [("Museum", "google_places"), ("Kletterfels Testwand", "osm_overpass")]
    assert [poi.id for poi in ergebnis] == [1, 2]
    assert ergebnis[0].place_id == "pid-museum" and ergebnis[1].nutzerinteresse == "Klettern"
    assert 0 not in {poi.id for poi in ergebnis}  # id 0 bleibt dem Depot (Unterkunft) vorbehalten


def test_sammle_pois_eindeutige_ids_trennen_matrixeintraege():
    from src.datenaufbereitung.aufbereitung import hole_reisezeitmatrix

    class _MatrixClient:
        def distanzmatrix(self, orte, modus="walking"):
            # Jede Zelle eindeutig (Zeile*10 + Spalte), damit sich Vermischungen zeigen würden.
            return [[i * 10 + j for j in range(len(orte))] for i in range(len(orte))]

    museum, kletterfels = _gesammelt_mit_gleicher_ursprungs_id()
    depot = POI(id=0, name="Unterkunft", kategorie="depot", x=48.0, y=11.0, score=0.0,
                required_time=0, opening=0, closing=1440)
    matrix = hole_reisezeitmatrix(_MatrixClient(), depot, [museum, kletterfels], ["walking"])
    assert matrix[(depot.id, museum.id)] == 1
    assert matrix[(depot.id, kletterfels.id)] == 2
    assert matrix[(museum.id, kletterfels.id)] == 12
    assert matrix[(kletterfels.id, museum.id)] == 21


def test_sammle_pois_eindeutige_ids_einplanen_entfernt_anderen_poi_nicht():
    from src.optimierung.toptw import TOPTWInstanz, plane_gesamte_reise

    pois = _gesammelt_mit_gleicher_ursprungs_id()
    depot = POI(id=0, name="Unterkunft", kategorie="depot", x=48.0, y=11.0, score=0.0,
                required_time=0, opening=0, closing=1440)
    # Ein POI pro Tag, zwei Tage: der am ersten Tag eingeplante POI darf den anderen nicht verdrängen.
    instanz = TOPTWInstanz(pois=pois, tagesbudget_minuten=600, anzahl_tage=2, depot=depot, max_pois_pro_tag=1)
    tagesrouten = plane_gesamte_reise(instanz)
    eingeplant = [besuch.poi.name for route in tagesrouten for besuch in route.besuche]
    assert sorted(eingeplant) == ["Kletterfels Testwand", "Museum"]
