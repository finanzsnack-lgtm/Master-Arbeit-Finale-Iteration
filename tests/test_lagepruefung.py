"""Tests für die deterministische Lageprüfung der Unterkunftssuche (src/datenaufbereitung/lagepruefung.py)."""
import pytest

from src.api import mock_data
from src.api.google_maps import MockGoogleMapsClient
from src.api.typen import Unterkunft, ZielGebiet
from src.datenaufbereitung.lagepruefung import (
    LAGE_FALLBACK_RADIUS_KM,
    LAGE_MINDESTRADIUS_KM,
    filtere_unterkuenfte_nach_lage,
    liegt_im_zielgebiet,
    luftlinie_km,
)

# Näherungsweise reale Werte, nur als plausible Testgeometrie.
VENEDIG = ZielGebiet(x=45.4408, y=12.3155, suedwest=(45.38, 12.18), nordost=(45.58, 12.45))
COSTA_DEL_SOL = ZielGebiet(x=36.60, y=-4.60, suedwest=(36.15, -5.45), nordost=(36.80, -3.80))
# Kleiner Ort mit einem Viewport von nur rund 2 x 2 km.
KLEINSTADT = ZielGebiet(x=47.5622, y=13.6493, suedwest=(47.553, 13.636), nordost=(47.571, 13.662))


def _unterkunft(name: str, x: float, y: float) -> Unterkunft:
    return Unterkunft(id=1, name=name, x=x, y=y, preisniveau=2, zertifiziert_nachhaltig=False)


def test_luftlinie_entspricht_bekannter_entfernung():
    # München -> Berlin, rund 504 km Luftlinie.
    assert luftlinie_km((48.1372, 11.5755), (52.5200, 13.4050)) == pytest.approx(504, abs=5)


def test_unterkunft_in_suedtirol_liegt_nicht_im_gebiet_venedig():
    # Befund aus dem Demo-Feedback: Ziel Venedig, vorgeschlagen wurde ein Hotel in Südtirol.
    assert not liegt_im_zielgebiet((46.66, 11.16), VENEDIG)


def test_unterkunft_in_mestre_liegt_im_gebiet_venedig():
    assert liegt_im_zielgebiet((45.49, 12.24), VENEDIG)


def test_regionsziel_behaelt_treffer_weit_vom_mittelpunkt_aber_im_gebiet():
    # Estepona liegt rund 50 km vom Mittelpunkt entfernt, aber innerhalb der Region.
    estepona = (36.43, -5.15)
    assert luftlinie_km(estepona, COSTA_DEL_SOL.punkt) > LAGE_FALLBACK_RADIUS_KM
    assert liegt_im_zielgebiet(estepona, COSTA_DEL_SOL)


def test_regionsziel_verwirft_treffer_ausserhalb_des_gebiets():
    sevilla = (37.39, -5.98)
    assert not liegt_im_zielgebiet(sevilla, COSTA_DEL_SOL)


def test_kleiner_viewport_behaelt_unterkunft_im_nachbarort_ueber_mindestradius():
    # Rund 8 km vom Mittelpunkt, deutlich außerhalb des kleinen Viewports samt Puffer.
    nachbarort = (47.5622, 13.7555)
    assert luftlinie_km(nachbarort, KLEINSTADT.punkt) < LAGE_MINDESTRADIUS_KM
    assert liegt_im_zielgebiet(nachbarort, KLEINSTADT)


def test_kleiner_viewport_verwirft_unterkunft_ausserhalb_von_mindestradius_und_puffer():
    weiter_weg = (47.5622, 13.9150)  # rund 20 km östlich
    assert not liegt_im_zielgebiet(weiter_weg, KLEINSTADT)


def test_puffer_behaelt_unterkunft_knapp_ausserhalb_des_viewports():
    # Rund 3 km nördlich der Nordkante des Viewports von Venedig, aber über 10 km vom Mittelpunkt.
    knapp_ausserhalb = (45.607, 12.30)
    assert luftlinie_km(knapp_ausserhalb, VENEDIG.punkt) > LAGE_MINDESTRADIUS_KM
    assert liegt_im_zielgebiet(knapp_ausserhalb, VENEDIG)


def test_puffer_verwirft_unterkunft_deutlich_ausserhalb_des_viewports():
    # Rund 9 km nördlich der Nordkante.
    assert not liegt_im_zielgebiet((45.66, 12.30), VENEDIG)


def test_ohne_viewport_gilt_die_fallback_schwelle():
    ohne_viewport = ZielGebiet(x=45.4408, y=12.3155)
    assert liegt_im_zielgebiet((45.66, 12.30), ohne_viewport)  # rund 24 km
    assert not liegt_im_zielgebiet((45.80, 12.30), ohne_viewport)  # rund 40 km


def test_filter_behaelt_reihenfolge_und_trennt_verworfene():
    weit = _unterkunft("Hotel Südtirol", 46.66, 11.16)
    nah_a = _unterkunft("Hotel A", 45.44, 12.33)
    nah_b = _unterkunft("Hotel B", 45.43, 12.32)
    behalten, verworfen = filtere_unterkuenfte_nach_lage([nah_b, weit, nah_a], VENEDIG)
    assert [u.name for u in behalten] == ["Hotel B", "Hotel A"]
    assert verworfen == [weit]


def test_mock_zielgebiet_umschliesst_alle_beispiel_unterkuenfte_auch_bei_beliebigem_zielnamen():
    # Im Mock-Modus muss F15 für jeden Zielnamen weiterhin eine Unterkunft finden.
    gebiet = MockGoogleMapsClient().geocode_gebiet("Venedig")
    assert gebiet.suedwest is not None and gebiet.nordost is not None
    assert all(liegt_im_zielgebiet((u.x, u.y), gebiet) for u in mock_data.BEISPIEL_UNTERKUENFTE)
