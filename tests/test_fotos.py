"""Tests für src/ausgabe/fotos.py (Foto-Download für die Web-UI, siehe webapp.py)."""
from src.api.typen import POI, ReiseAlternative
from src.ausgabe.fotos import lade_fotos_fuer_plan
from src.ausgabe.reiseplan import Reiseplan
from src.optimierung.toptw import Besuch, Tagesroute
from src.optimierung.verkehrsmittelwahl import BewerteteAlternative

_BAHN = BewerteteAlternative(
    alternative=ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500),
    co2_kg=9.5, score=0.1,
)


class _FakeClient:
    """Simuliert `MapsClient.lade_foto`/`hole_foto_referenz` – Erfolg NUR für place_ids in
    `funktionierende_ids` (Referenzen folgen im Test der Konvention "ref-<place_id>"), damit sowohl
    der Erfolgs- als auch der ehrliche Fehlschlagsfall getestet werden kann. `nachlade_ids` simuliert
    den Fallback (Iteration 2, Stage 30): fehlt `foto_referenz` bei einem POI, liefert
    `hole_foto_referenz` für genau diese place_ids nachträglich eine Referenz."""

    def __init__(self, funktionierende_ids: set[str], nachlade_ids: set[str] = frozenset()):
        self._funktionierende_referenzen = {f"ref-{place_id}" for place_id in funktionierende_ids}
        self._nachlade_ids = nachlade_ids
        self.aufrufe: list[tuple[str, str]] = []
        self.nachlade_aufrufe: list[str] = []

    def lade_foto(self, foto_referenz: str, ziel_pfad: str, max_breite: int = 640) -> bool:
        self.aufrufe.append((foto_referenz, ziel_pfad))
        erfolgreich = foto_referenz in self._funktionierende_referenzen
        if erfolgreich:
            with open(ziel_pfad, "w", encoding="utf-8") as datei:
                datei.write("fake")
        return erfolgreich

    def hole_foto_referenz(self, place_id: str | None) -> str | None:
        self.nachlade_aufrufe.append(place_id or "")
        return f"ref-{place_id}" if place_id in self._nachlade_ids else None


def _basis_plan(**zusatz) -> Reiseplan:
    parameter = {"hinreise": _BAHN, "tagesrouten": [], "rueckreise": _BAHN}
    parameter.update(zusatz)
    return Reiseplan(**parameter)


def _poi(place_id: str, foto_referenz: str | None = None, **zusatz) -> POI:
    basis = {
        "id": 1, "name": f"POI {place_id}", "kategorie": "museum", "x": 0.0, "y": 0.0, "score": 1.0,
        "required_time": 60, "opening": 0, "closing": 600, "place_id": place_id, "foto_referenz": foto_referenz,
    }
    basis.update(zusatz)
    return POI(**basis)


def test_laedt_foto_fuer_unterkunft_und_eingeplante_pois(tmp_path):
    poi = _poi("poi-1", foto_referenz="ref-poi-1")
    tag1 = Tagesroute(besuche=[Besuch(poi=poi, ankunft=15, wartezeit=0, abfahrt=195)])
    plan = _basis_plan(
        tagesrouten=[tag1], unterkunft_name="Hotel Zentral", unterkunft_place_id="hotel-1",
        unterkunft_foto_referenz="ref-hotel-1",
    )
    client = _FakeClient(funktionierende_ids={"hotel-1", "poi-1"})

    dateien = lade_fotos_fuer_plan(plan, client, tmp_path / "sitzung")

    assert dateien == {"hotel-1": "hotel-1.jpg", "poi-1": "poi-1.jpg"}
    assert (tmp_path / "sitzung" / "hotel-1.jpg").exists()
    assert (tmp_path / "sitzung" / "poi-1.jpg").exists()


def test_ueberspringt_pois_ohne_place_id(tmp_path):
    ohne_place_id = _poi(place_id=None, foto_referenz="ref-egal")
    tag1 = Tagesroute(besuche=[Besuch(poi=ohne_place_id, ankunft=15, wartezeit=0, abfahrt=75)])
    plan = _basis_plan(tagesrouten=[tag1])
    client = _FakeClient(funktionierende_ids={"egal"})

    dateien = lade_fotos_fuer_plan(plan, client, tmp_path / "sitzung")

    assert dateien == {}
    assert client.aufrufe == []  # ohne place_id kann kein Dateiname gebildet werden


def test_gescheiterter_download_landet_nicht_im_ergebnis(tmp_path):
    poi = _poi("poi-1", foto_referenz="ref-poi-1")
    tag1 = Tagesroute(besuche=[Besuch(poi=poi, ankunft=15, wartezeit=0, abfahrt=195)])
    plan = _basis_plan(tagesrouten=[tag1])
    client = _FakeClient(funktionierende_ids=set())  # jeder Download schlägt fehl

    dateien = lade_fotos_fuer_plan(plan, client, tmp_path / "sitzung")

    assert dateien == {}


def test_ohne_foto_referenz_greift_nachlade_fallback(tmp_path):
    # Iteration 2, Stage 30 (Rückmeldung des Product Owners nach echtem Browser-Test): fehlt `foto_referenz` (die
    # ursprüngliche Suche lieferte kein `photos`-Feld), wird VOR dem Aufgeben zusätzlich
    # `hole_foto_referenz` (Places Details) versucht.
    ohne_foto = _poi("poi-1")  # foto_referenz=None
    tag1 = Tagesroute(besuche=[Besuch(poi=ohne_foto, ankunft=15, wartezeit=0, abfahrt=75)])
    plan = _basis_plan(tagesrouten=[tag1])
    client = _FakeClient(funktionierende_ids={"poi-1"}, nachlade_ids={"poi-1"})

    dateien = lade_fotos_fuer_plan(plan, client, tmp_path / "sitzung")

    assert dateien == {"poi-1": "poi-1.jpg"}
    assert client.nachlade_aufrufe == ["poi-1"]


def test_nachlade_fallback_ohne_treffer_bleibt_ohne_foto(tmp_path):
    ohne_foto = _poi("poi-1")  # foto_referenz=None, auch Details liefert nichts
    tag1 = Tagesroute(besuche=[Besuch(poi=ohne_foto, ankunft=15, wartezeit=0, abfahrt=75)])
    plan = _basis_plan(tagesrouten=[tag1])
    client = _FakeClient(funktionierende_ids=set(), nachlade_ids=set())

    dateien = lade_fotos_fuer_plan(plan, client, tmp_path / "sitzung")

    assert dateien == {}
    assert client.aufrufe == []  # kein lade_foto-Versuch ohne jede Referenz


def test_weitere_empfehlungen_und_vorschlag_kategorien_werden_jetzt_heruntergeladen(tmp_path):
    # Korrektur nach Rückmeldung des Product Owners (Stage 30): bis Stage 29 blieben "Weitere Empfehlungen" und
    # alle "Vorschlag"-Kategorien IMMER ohne Foto (siehe Moduldoku). Jetzt werden sie genauso wie
    # eingeplante POIs behandelt.
    weitere_empfehlung = _poi("poi-empf", foto_referenz="ref-poi-empf")
    restaurant = _poi("poi-rest", foto_referenz="ref-poi-rest")
    tour = _poi("poi-tour", foto_referenz="ref-poi-tour")
    lernaktivitaet = _poi("poi-lern", foto_referenz="ref-poi-lern")
    markt = _poi("poi-markt", foto_referenz="ref-poi-markt")
    plan = _basis_plan(
        weitere_aktivitaeten_empfehlungen=[weitere_empfehlung],
        beispielrestaurants=[restaurant],
        tour_tag_beispiele=[tour],
        lernaktivitaet_tag_beispiele=[lernaktivitaet],
        markt_beispiele=[markt],
    )
    client = _FakeClient(funktionierende_ids={"poi-empf", "poi-rest", "poi-tour", "poi-lern", "poi-markt"})

    dateien = lade_fotos_fuer_plan(plan, client, tmp_path / "sitzung")

    assert dateien == {
        "poi-empf": "poi-empf.jpg", "poi-rest": "poi-rest.jpg", "poi-tour": "poi-tour.jpg",
        "poi-lern": "poi-lern.jpg", "poi-markt": "poi-markt.jpg",
    }


def test_lokaler_verleih_poi_wird_heruntergeladen(tmp_path):
    verleih = _poi("poi-verleih", foto_referenz="ref-poi-verleih", kategorie="autoverleih")
    plan = _basis_plan(lokaler_verleih_poi=verleih, lokales_leihfahrzeug_gewuenscht="Auto")
    client = _FakeClient(funktionierende_ids={"poi-verleih"})

    dateien = lade_fotos_fuer_plan(plan, client, tmp_path / "sitzung")

    assert dateien == {"poi-verleih": "poi-verleih.jpg"}


def test_feste_termine_werden_heruntergeladen_inklusive_nachlade_fallback(tmp_path):
    from src.api.typen import GefundenerOrt
    from src.ausgabe.reiseplan import FesterTermin
    from src.fragekatalog.schema import FesterWunschort

    mit_referenz = GefundenerOrt(name="Museum", adresse=None, x=0.0, y=0.0, place_id="termin-1", foto_referenz="ref-termin-1")
    ohne_referenz = GefundenerOrt(name="Schloss", adresse=None, x=0.0, y=0.0, place_id="termin-2")
    plan = _basis_plan(feste_termine=[
        FesterTermin(tag_nr=2, wunschort=FesterWunschort(rohname="Museum", ort=mit_referenz, dauer_minuten=120)),
        FesterTermin(tag_nr=3, wunschort=FesterWunschort(rohname="Schloss", ort=ohne_referenz, dauer_minuten=120)),
    ])
    client = _FakeClient(funktionierende_ids={"termin-1", "termin-2"}, nachlade_ids={"termin-2"})

    ergebnis = lade_fotos_fuer_plan(plan, client, tmp_path)

    assert ergebnis == {"termin-1": "termin-1.jpg", "termin-2": "termin-2.jpg"}
    assert client.nachlade_aufrufe == ["termin-2"]
