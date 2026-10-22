"""
Tests für die LLM-Werkzeuge der agentischen Dialogsteuerung (src/fragekatalog/agent_tools.py) –
deterministisch, OHNE echten LLM-Aufruf. Ruft die rohen `handler`-Coroutinen der `SdkMcpTool`-
Objekte direkt auf (kein SDK-Server/keine echte Session nötig).
"""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.api.google_maps import GoogleMapsClient, MockGoogleMapsClient
from src.api.typen import POI, GefundenerOrt, ReiseAlternative, Unterkunft
from src.ausgabe.debug import PlanungsDebugSammlung
from src.ausgabe.reiseplan import Reiseplan
from src.fragekatalog.agent_tools import AgentSessionState, ERLAUBTE_TOOLS, erstelle_tools, fehlende_pflichtfelder
from src.fragekatalog.schema import FesterWunschort, ReiseAnfrage
from src.fragekatalog.wunschorte import (
    SCHWELLE_WEITER_WUNSCHORT_MINUTEN,
    STANDARD_BESUCHSDAUER_WUNSCHORT_MINUTEN,
    pruefe_anfahrten,
)
from src.optimierung.toptw import Besuch, Tagesroute
from src.optimierung.verkehrsmittelwahl import BewerteteAlternative
from src.protokoll import Protokollierer


def _rufe(tools, name, **args):
    tool = next(t for t in tools if t.name == name)
    return asyncio.run(tool.handler(args))


def _basis_state(**zusatz) -> AgentSessionState:
    parameter = {"anfrage": ReiseAnfrage(), "maps_client": _FakeClient()}
    parameter.update(zusatz)
    return AgentSessionState(**parameter)


class _FakeClient:
    def __init__(self, unterkuenfte=None, barrierefrei_je_place_id=None):
        self.letzte_kategorien: list[str] | None = None
        self._unterkuenfte = unterkuenfte or []
        self._barrierefrei_je_place_id = barrierefrei_je_place_id or {}

    def geocode(self, ort):
        return (48.0, 11.0)

    def suche_pois(self, ort, kategorien, radius_meter=3000, ernaehrung_einschraenkungen=None):
        self.letzte_kategorien = list(kategorien)
        return []

    def suche_unterkuenfte(self, ort, praeferenz_text=None):
        return list(self._unterkuenfte)

    def reisealternativen(self, von, nach):
        return [ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500)]

    def anfahrtszeiten_minuten(self, ursprung, ziele, modus="walking"):
        return [-1 for _ in ziele]

    def ist_barrierefrei(self, place_id):
        return self._barrierefrei_je_place_id.get(place_id)


def test_erlaubte_tools_stimmt_mit_erstellten_tools_ueberein():
    state = _basis_state()
    tools = erstelle_tools(state)
    erzeugte_namen = {f"mcp__reisebot__{t.name}" for t in tools}
    assert erzeugte_namen == set(ERLAUBTE_TOOLS)


def test_fehlende_pflichtfelder_ohne_angaben_listet_alle_pflichtfelder():
    anfrage = ReiseAnfrage()
    fehlend = fehlende_pflichtfelder(anfrage)
    assert "budget_gesamt" in fehlend
    assert "wohnort" in fehlend
    assert "name" in fehlend


def test_fehlende_pflichtfelder_ignoriert_optionale_felder():
    anfrage = ReiseAnfrage()
    fehlend = fehlende_pflichtfelder(anfrage)
    # F09/F10/F11/F14/F17 sind pflichtfeld=False (siehe katalog.py) -> dürfen NIE auftauchen
    assert "gesundheitliche_einschraenkungen" not in fehlend
    assert "lokaler_transport_praeferenz" not in fehlend
    assert "sicherheitsbeduerfnis" not in fehlend


def test_speichere_feld_speichert_gueltigen_string():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "speichere_feld", feld="wohnort", wert="Hannover")
    assert state.anfrage.wohnort == "Hannover"
    assert not ergebnis.get("is_error")


def test_speichere_feld_speichert_gueltiges_array():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="zielregionen", wert=["Italien", "Frankreich"])
    assert state.anfrage.zielregionen == ["Italien", "Frankreich"]


def test_speichere_feld_lehnt_falschen_typ_ab():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "speichere_feld", feld="budget_gesamt", wert="viel Geld")
    assert ergebnis.get("is_error") is True
    assert state.anfrage.budget_gesamt is None  # nicht gespeichert


def test_speichere_feld_lehnt_unbekanntes_feld_ab():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "speichere_feld", feld="lieblingsfarbe", wert="blau")
    assert ergebnis.get("is_error") is True


def test_speichere_feld_meldet_verbleibende_pflichtfelder():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "speichere_feld", feld="wohnort", wert="Hannover")
    text = ergebnis["content"][0]["text"]
    assert "Noch fehlende Pflichtfelder" in text
    assert "budget_gesamt" in text


def test_speichere_feld_uebernimmt_zuvor_gefundene_unterkunft():
    # Simuliert den echten Ablauf: hole_api_daten (siehe eigener Test unten) füllt
    # state.zuletzt_gefundene_unterkunft, speichere_feld übernimmt sie erst bei Bestätigung.
    state = _basis_state()
    state.zuletzt_gefundene_unterkunft = Unterkunft(
        id=1, name="Hotel Zentral", x=48.13, y=11.57, preisniveau=2, zertifiziert_nachhaltig=True, place_id="hz1",
    )
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="unterkunft_anforderungen", wert="zentral gelegen")
    assert state.anfrage.unterkunft_name == "Hotel Zentral"
    assert state.anfrage.unterkunft_koordinaten == (48.13, 11.57)
    assert state.anfrage.unterkunft_place_id == "hz1"
    assert state.anfrage.unterkunft_preisniveau == 2


def test_speichere_feld_ohne_zuvor_gefundene_unterkunft_laesst_felder_leer():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="unterkunft_anforderungen", wert="zentral gelegen")
    assert state.anfrage.unterkunft_name is None


def test_speichere_feld_aktivitaeten_persistiert_spezialrecherche_und_gewichtung():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(
        tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Klettern", "Shopping"],
        aktivitaeten_mit_spezialrecherche=["Klettern"], aktivitaeten_gewichtung={"Klettern": 2.0},
    )
    assert state.anfrage.aktivitaeten_mit_spezialrecherche == ["Klettern"]
    assert state.anfrage.aktivitaeten_gewichtung == {"Klettern": 2.0}


def test_speichere_feld_tagesstart_persistiert_ki_interpretierte_minuten():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(
        tools, "speichere_feld", feld="tagesstart_praeferenz", wert="ab neun bis abends um neun",
        tagesstart_minuten=540, tagesende_minuten=1260,
    )
    assert state.anfrage.tagesstart_minuten == 540
    assert state.anfrage.tagesende_minuten == 1260


def test_speichere_feld_tagesstart_ohne_interpretierbare_uhrzeit_bleibt_leer():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="tagesstart_praeferenz", wert="mal schauen")
    assert state.anfrage.tagesstart_minuten is None
    assert state.anfrage.tagesende_minuten is None


def test_speichere_feld_sicherheitsbeduerfnis_setzt_bedenklich_flag():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="sicherheitsbeduerfnis", wert="sehr wichtig", sicherheit_bedenklich=True)
    assert state.anfrage.sicherheit_bedenklich is True


def test_speichere_feld_mobilitaetseinschraenkung_stufe_wirkt_bei_beliebigem_feld():
    # NICHT auf ein Feld beschränkt (anders als sicherheit_bedenklich, siehe agent_tools.py
    # Tool-Beschreibung) – kann z.B. bei F10 (altersgerechte_beduerfnisse) genauso gesetzt werden
    # wie bei F09/F15.
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(
        tools, "speichere_feld", feld="altersgerechte_beduerfnisse",
        wert="wegen der Kinder lieber gemütlich, nicht hetzen", mobilitaetseinschraenkung_stufe="leicht",
    )
    assert state.anfrage.mobilitaetseinschraenkung_stufe == "leicht"


def test_speichere_feld_mobilitaetseinschraenkung_stufe_kann_verfeinert_werden():
    # Anders als das frühere, einmal gesetzte Bool: die Stufe kann im Gesprächsverlauf korrigiert
    # werden (z.B. "leicht" -> "stark", wenn sich ein Rollstuhlbedarf erst später herausstellt).
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="altersgerechte_beduerfnisse", wert="etwas langsam", mobilitaetseinschraenkung_stufe="leicht")
    _rufe(tools, "speichere_feld", feld="gesundheitliche_einschraenkungen", wert="Rollstuhl", mobilitaetseinschraenkung_stufe="stark")
    assert state.anfrage.mobilitaetseinschraenkung_stufe == "stark"


def test_speichere_feld_ohne_mobilitaetseinschraenkung_stufe_bleibt_none():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="altersgerechte_beduerfnisse", wert="keine besonderen Bedürfnisse")
    assert state.anfrage.mobilitaetseinschraenkung_stufe is None


def test_speichere_feld_ungueltige_mobilitaetseinschraenkung_stufe_wird_ignoriert():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(
        tools, "speichere_feld", feld="altersgerechte_beduerfnisse", wert="x",
        mobilitaetseinschraenkung_stufe="mittelschwer",  # kein gültiger Wert
    )
    assert state.anfrage.mobilitaetseinschraenkung_stufe is None


def test_speichere_feld_persistiert_ki_interpretierte_reisedaten():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(
        tools, "speichere_feld", feld="reisezeitraum_rohtext", wert="15.09. - 18.09.2026",
        reise_start_datum="2026-09-15", reise_end_datum="2026-09-18",
    )
    assert state.anfrage.reise_start_datum == "2026-09-15"
    assert state.anfrage.reise_end_datum == "2026-09-18"


def test_speichere_feld_ungueltiges_iso_datum_wird_ignoriert():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(
        tools, "speichere_feld", feld="reisezeitraum_rohtext", wert="im Sommer",
        reise_start_datum="15.09.2026", reise_end_datum="2026-09-18",  # erstes Datum nicht ISO
    )
    assert state.anfrage.reise_start_datum is None
    assert state.anfrage.reise_end_datum == "2026-09-18"


def test_speichere_feld_ohne_reisedaten_bleibt_none():
    state = _basis_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="reisezeitraum_rohtext", wert="im Sommer, unklar wie lange")
    assert state.anfrage.reise_start_datum is None
    assert state.anfrage.reise_end_datum is None


def test_hole_api_daten_liefert_text_fuer_typ_c_feld():
    state = _basis_state()
    state.anfrage.zielregionen = ["Italien"]
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "hole_api_daten", feld="verkehrsmittel_praeferenz")
    text = ergebnis["content"][0]["text"]
    assert "Bahn" in text


def test_hole_api_daten_gibt_aktivitaeten_aktuell_an_die_suche_weiter():
    # Regression: ohne dieses Argument fiel die Suche auf das beim ersten Durchlauf noch leere
    # anfrage.aktivitaeten_interessen zurück und suchte de facto nach GAR NICHTS.
    state = _basis_state()
    state.anfrage.zielregionen = ["Italien"]
    tools = erstelle_tools(state)

    _rufe(tools, "hole_api_daten", feld="aktivitaeten_interessen", aktivitaeten_aktuell=["Restaurants", "Kultur"])

    assert state.maps_client.letzte_kategorien == ["Restaurants", "Kultur"]


def test_hole_api_daten_unterkunft_ohne_treffer_meldet_ehrlich_und_cached_nichts():
    state = _basis_state()
    state.anfrage.zielregionen = ["Italien"]
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "hole_api_daten", feld="unterkunft_anforderungen", aktueller_wert="ruhige Lage")
    assert not ergebnis.get("is_error")
    assert state.zuletzt_gefundene_unterkunft is None


def test_hole_api_daten_unterkunft_cached_gefundene_unterkunft():
    hotel = Unterkunft(id=1, name="Hotel Zentral", x=48.13, y=11.57, preisniveau=2, zertifiziert_nachhaltig=True, place_id="hz1")
    state = _basis_state(maps_client=_FakeClient(unterkuenfte=[hotel]))
    state.anfrage.zielregionen = ["Italien"]
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "hole_api_daten", feld="unterkunft_anforderungen", aktueller_wert="zentral")
    text = ergebnis["content"][0]["text"]
    assert "Hotel Zentral" in text
    assert state.zuletzt_gefundene_unterkunft is hotel


def test_hole_api_daten_lokaler_transport_ohne_bestaetigte_unterkunft_wartet():
    state = _basis_state()
    state.anfrage.lokaler_transport_praeferenz = "ich möchte vor Ort ein Fahrrad ausleihen"
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "hole_api_daten", feld="lokaler_transport_praeferenz")
    text = ergebnis["content"][0]["text"]
    assert "noch nicht bestätigt" in text
    assert state.anfrage.lokaler_verleih_gewaehlt is None


def test_hole_api_daten_lehnt_nicht_typ_c_feld_ab():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "hole_api_daten", feld="wohnort")
    assert ergebnis.get("is_error") is True


def test_hole_api_daten_lehnt_unbekanntes_feld_ab():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "hole_api_daten", feld="lieblingsfarbe")
    assert ergebnis.get("is_error") is True


def _vollstaendige_anfrage(**zusatz) -> ReiseAnfrage:
    parameter = dict(
        name="Max", email="max@example.com", reisebegleitung=["allein"], reiseleitung_gewuenscht=False,
        reisezeitraum_rohtext="3 Tage", zielregionen=["Italien"],
        wohnort="Hannover", budget_gesamt=1000.0, verkehrsmittel_praeferenz=["Bahn"],
        unterkunft_anforderungen="zentral", aktivitaeten_interessen=["Kultur"],
    )
    parameter.update(zusatz)
    anfrage = ReiseAnfrage(**parameter)
    for frage_feld in fehlende_pflichtfelder(anfrage):
        pytest.fail(f"Testvorbereitung unvollständig, Feld fehlt noch: {frage_feld}")
    return anfrage


def _leerer_plan(**zusatz) -> Reiseplan:
    bahn = BewerteteAlternative(
        alternative=ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500), co2_kg=9.5, score=0.1,
    )
    parameter = {"hinreise": bahn, "tagesrouten": [], "rueckreise": bahn}
    parameter.update(zusatz)
    return Reiseplan(**parameter)


def test_plane_reise_und_abschliessen_blockiert_bei_fehlenden_pflichtfeldern():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "plane_reise_und_abschliessen")
    assert ergebnis.get("is_error") is True
    assert state.abgeschlossen is False


def test_plane_reise_und_abschliessen_erfolgreich_bei_vollstaendigen_pflichtfeldern(tmp_path):
    anfrage = _vollstaendige_anfrage()
    plan = _leerer_plan()
    state = _basis_state(anfrage=anfrage, ausgabe_basisname=str(tmp_path / "reiseplan_test"))
    tools = erstelle_tools(state)

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(plan, None, PlanungsDebugSammlung())), \
         patch("src.fragekatalog.agent_tools.speichere_datei") as m_datei, \
         patch("src.fragekatalog.agent_tools.speichere_json") as m_json, \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht") as m_poi_uebersicht, \
         patch("src.fragekatalog.agent_tools.sende_mail") as m_mail:
        ergebnis = _rufe(tools, "plane_reise_und_abschliessen")

    assert not ergebnis.get("is_error")
    assert state.abgeschlossen is True
    assert state.reiseplan is plan
    m_datei.assert_called_once()
    m_json.assert_called_once()
    m_mail.assert_called_once()
    m_poi_uebersicht.assert_called_once()
    poi_uebersicht_pfad = m_poi_uebersicht.call_args.args[1]
    assert poi_uebersicht_pfad.name == "reiseplan_test_pois.csv"


def test_plane_reise_und_abschliessen_zeigt_nachhaltigkeits_nudge_nicht_mehr_im_ergebnis(tmp_path):
    # Nach Abschluss ist die Verkehrsmittelwahl bereits getroffen: der Nudge gehört nur in den
    # F13-Dialog, nicht in das Werkzeugergebnis mit dem fertigen Reiseplan. Für das
    # Sitzungsprotokoll bleibt er im State erhalten.
    anfrage = _vollstaendige_anfrage()
    state = _basis_state(anfrage=anfrage, ausgabe_basisname=str(tmp_path / "reiseplan_test"))
    tools = erstelle_tools(state)
    nudge = "Die Bahn braucht nur 60 Minuten länger, spart aber 74.5 kg CO2 gegenüber der bestbewerteten Alternative (Auto)."

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(_leerer_plan(), nudge, PlanungsDebugSammlung())),          patch("src.fragekatalog.agent_tools.speichere_datei"),          patch("src.fragekatalog.agent_tools.speichere_json"),          patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"),          patch("src.fragekatalog.agent_tools.sende_mail"):
        ergebnis = _rufe(tools, "plane_reise_und_abschliessen")

    assert not ergebnis.get("is_error")
    assert nudge not in ergebnis["content"][0]["text"]
    assert state.nachhaltigkeits_nudge == nudge


def test_plane_reise_und_abschliessen_meldet_status_wenn_kanal_vorhanden(tmp_path):
    # Iteration 2 (Betreuer-Feedback: Ladeindikator, siehe
    # doku/28_stage28_iteration2_ux_feedback_konzepte/README.md): kurz vor dem potenziell lange
    # dauernden Planungsschritt wird `io_kanal.zeige_status("plant_reise")` aufgerufen – NUR, wenn
    # überhaupt ein Kanal übergeben wurde (Standard bleibt `None`, siehe AgentSessionState).
    anfrage = _vollstaendige_anfrage()
    plan = _leerer_plan()
    fake_kanal = AsyncMock()
    state = _basis_state(anfrage=anfrage, ausgabe_basisname=str(tmp_path / "reiseplan_test"), io_kanal=fake_kanal)
    tools = erstelle_tools(state)

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(plan, None, PlanungsDebugSammlung())), \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        _rufe(tools, "plane_reise_und_abschliessen")

    fake_kanal.zeige_status.assert_called_once_with("plant_reise")


def test_plane_reise_und_abschliessen_ohne_kanal_wirft_nicht(tmp_path):
    # Standardfall in bestehenden Tests (kein io_kanal übergeben) – darf nicht scheitern, das
    # Status-Signal wird dann einfach übersprungen (siehe agent_tools.py).
    anfrage = _vollstaendige_anfrage()
    plan = _leerer_plan()
    state = _basis_state(anfrage=anfrage, ausgabe_basisname=str(tmp_path / "reiseplan_test"))
    assert state.io_kanal is None
    tools = erstelle_tools(state)

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(plan, None, PlanungsDebugSammlung())), \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        ergebnis = _rufe(tools, "plane_reise_und_abschliessen")

    assert not ergebnis.get("is_error")


def test_plane_reise_und_abschliessen_schreibt_debug_datei_neben_dem_protokoll(tmp_path):
    # Entscheidung des Product Owners: die Debug-Ausgabe (rohe/gefilterte/weitergegebene POIs, Optimierung-1-/
    # Härtetest-Eingabe/-Ergebnis) soll bei JEDEM echten Test entstehen (chat.py/webapp.py), nicht
    # nur über pruefe_planung.py – landet neben dem Sitzungsprotokoll (Protokollierer.pfad).
    anfrage = _vollstaendige_anfrage()
    plan = _leerer_plan()
    protokollierer = Protokollierer(pfad=tmp_path / "chat_2026-01-01_120000.jsonl")
    state = _basis_state(
        anfrage=anfrage, ausgabe_basisname=str(tmp_path / "reiseplan_test"), protokollierer=protokollierer,
    )
    tools = erstelle_tools(state)
    debug_sammlung = PlanungsDebugSammlung(rohe_pois=[
        POI(id=1, name="Museum A", kategorie="museum", x=0, y=0, score=3.0, required_time=60, opening=0, closing=600),
    ])

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(plan, None, debug_sammlung)), \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        _rufe(tools, "plane_reise_und_abschliessen")

    debug_pfad = tmp_path / "chat_2026-01-01_120000_debug.txt"
    assert debug_pfad.exists()
    inhalt = debug_pfad.read_text(encoding="utf-8")
    assert "PLANUNGS-DEBUG" in inhalt
    assert "Museum A" in inhalt


def test_plane_reise_und_abschliessen_ohne_protokollierer_schreibt_keine_debug_datei(tmp_path):
    anfrage = _vollstaendige_anfrage()
    plan = _leerer_plan()
    state = _basis_state(anfrage=anfrage, ausgabe_basisname=str(tmp_path / "reiseplan_test"))  # kein protokollierer
    tools = erstelle_tools(state)

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(plan, None, PlanungsDebugSammlung())), \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        ergebnis = _rufe(tools, "plane_reise_und_abschliessen")

    assert not ergebnis.get("is_error")  # kein Absturz ohne Protokollierer
    assert list(tmp_path.glob("*_debug.txt")) == []


def test_plane_reise_und_abschliessen_blockiert_bei_barrierefreiheits_konflikt_und_erlaubt_retry(tmp_path):
    anfrage = _vollstaendige_anfrage(altersgerechte_beduerfnisse="bitte barrierefrei", mobilitaetseinschraenkung_stufe="mittel")
    besuch_ohne_zugang = Besuch(poi=POI(
        id=1, name="Konfliktort", kategorie="museum", x=0, y=0, score=1.0, required_time=60,
        opening=0, closing=600, place_id="schlecht",
    ))
    plan_mit_konflikt = _leerer_plan(tagesrouten=[Tagesroute(besuche=[besuch_ohne_zugang])])
    plan_nach_neuplanung = _leerer_plan()

    client = _FakeClient(barrierefrei_je_place_id={"schlecht": False})
    state = _basis_state(anfrage=anfrage, maps_client=client, ausgabe_basisname=str(tmp_path / "reiseplan_test"))
    tools = erstelle_tools(state)

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(plan_mit_konflikt, None, PlanungsDebugSammlung())):
        erster_versuch = _rufe(tools, "plane_reise_und_abschliessen")
    assert erster_versuch.get("is_error") is True
    assert state.abgeschlossen is False

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(plan_nach_neuplanung, None, PlanungsDebugSammlung())) as m_plane_reise, \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        zweiter_versuch = _rufe(tools, "plane_reise_und_abschliessen", barrierefreiheit_bereits_gepruft=True)

    assert not zweiter_versuch.get("is_error")
    assert state.abgeschlossen is True
    assert m_plane_reise.call_args.kwargs.get("barrierefreiheit_strikt") is True


def test_breche_planung_ab_setzt_flag():
    state = _basis_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "breche_planung_ab", grund="keine Lust mehr")
    assert state.abgebrochen is True
    assert not ergebnis.get("is_error")


# -- Feste Wunschorte (Betreuer-Feedback Iteration 2: Berücksichtigung dedizierter Standorte) --------


class _FakeWunschortClient(_FakeClient):
    """Fake mit `finde_ort`: kennt nur die Orte aus `orte_je_name`, zählt Aufrufe und merkt sich den
    übergebenen Ortsbezug."""

    def __init__(self, orte_je_name=None, **kwargs):
        super().__init__(**kwargs)
        self._orte_je_name = orte_je_name or {}
        self.finde_ort_aufrufe: list[tuple[str, tuple[float, float] | None]] = []

    def finde_ort(self, suchtext, nahe_bei=None):
        self.finde_ort_aufrufe.append((suchtext, nahe_bei))
        return self._orte_je_name.get(suchtext)


_MUSEUM = GefundenerOrt(
    name="Deutsches Museum", adresse="Museumsinsel 1, 80538 München", x=48.1299, y=11.5834,
    place_id="pid-museum", kategorie="museum", preisniveau=2,
)
_SCHLOSS = GefundenerOrt(
    name="Schloss Nymphenburg", adresse="Schloß Nymphenburg 1, 80638 München", x=48.1583, y=11.5033,
    place_id="pid-schloss",
)


def _wunschort_state(**client_kwargs) -> AgentSessionState:
    client = _FakeWunschortClient(
        orte_je_name={"Deutsches Museum": _MUSEUM, "Schloss Nymphenburg": _SCHLOSS}, **client_kwargs
    )
    state = _basis_state(maps_client=client)
    state.anfrage.zielregionen = ["München"]
    return state


def _ergebnis_text(ergebnis) -> str:
    return ergebnis["content"][0]["text"]


def test_speichere_feld_feste_wunschorte_gesetzt_mit_dauer_und_uhrzeit():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(
        tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
        feste_wunschorte=[{"name": "Deutsches Museum", "dauer_minuten": 180, "uhrzeit_minuten": 900}],
    )
    assert not ergebnis.get("is_error")
    [wunschort] = state.anfrage.feste_wunschorte
    assert wunschort.rohname == "Deutsches Museum"
    assert wunschort.ort is _MUSEUM
    assert wunschort.dauer_minuten == 180
    assert wunschort.uhrzeit_minuten == 900
    text = _ergebnis_text(ergebnis)
    # Name und Adresse stehen im Ergebnis, damit das LLM sie beim Nutzer bestätigen lassen kann.
    assert "Deutsches Museum" in text and "Museumsinsel 1, 80538 München" in text
    assert "15:00" in text
    assert "bestätigen" in text
    # Ohne bestätigte Unterkunft wird das geokodierte Reiseziel als Ortsbezug verwendet.
    assert state.maps_client.finde_ort_aufrufe == [("Deutsches Museum", (48.0, 11.0))]


def test_speichere_feld_feste_wunschorte_ohne_dauer_nutzt_standardwert_ohne_uhrzeit():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(
        tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
        feste_wunschorte=[{"name": "Deutsches Museum"}],
    )
    [wunschort] = state.anfrage.feste_wunschorte
    assert wunschort.dauer_minuten == STANDARD_BESUCHSDAUER_WUNSCHORT_MINUTEN == 120
    assert wunschort.uhrzeit_minuten is None
    text = _ergebnis_text(ergebnis)
    assert "Standardwert" in text
    assert "Ende des Tages" in text


def test_speichere_feld_feste_wunschorte_bevorzugt_bestaetigte_unterkunft_als_ortsbezug():
    state = _wunschort_state()
    state.anfrage.unterkunft_koordinaten = (48.14, 11.57)
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
          feste_wunschorte=[{"name": "Deutsches Museum"}])
    assert state.maps_client.finde_ort_aufrufe == [("Deutsches Museum", (48.14, 11.57))]


def test_speichere_feld_feste_wunschorte_ueberschreibt_vollstaendige_liste():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
          feste_wunschorte=[{"name": "Deutsches Museum"}, {"name": "Schloss Nymphenburg"}])
    assert [w.ort.name for w in state.anfrage.feste_wunschorte] == ["Deutsches Museum", "Schloss Nymphenburg"]

    # Verzicht auf das Museum: die neue, vollständige Liste ersetzt die alte. Der unveränderte
    # Eintrag wird wiederverwendet statt erneut gesucht, die neue Dauer wird übernommen.
    _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
          feste_wunschorte=[{"name": "Schloss Nymphenburg", "dauer_minuten": 90}])
    [wunschort] = state.anfrage.feste_wunschorte
    assert wunschort.ort is _SCHLOSS
    assert wunschort.dauer_minuten == 90
    assert [aufruf[0] for aufruf in state.maps_client.finde_ort_aufrufe] == ["Deutsches Museum", "Schloss Nymphenburg"]


def test_speichere_feld_feste_wunschorte_leere_liste_entfernt_alle():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
          feste_wunschorte=[{"name": "Deutsches Museum"}])
    ergebnis = _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"], feste_wunschorte=[])
    assert state.anfrage.feste_wunschorte == []
    assert "entfernt" in _ergebnis_text(ergebnis)


def test_speichere_feld_ohne_argument_feste_wunschorte_laesst_liste_unveraendert():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
          feste_wunschorte=[{"name": "Deutsches Museum"}])
    _rufe(tools, "speichere_feld", feld="budget_gesamt", wert=1500)
    assert [w.ort.name for w in state.anfrage.feste_wunschorte] == ["Deutsches Museum"]


def test_speichere_feld_feste_wunschorte_nicht_gefunden_speichert_nichts():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(
        tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
        feste_wunschorte=[{"name": "Erfundenes Phantasiemuseum"}],
    )
    assert state.anfrage.feste_wunschorte == []
    text = _ergebnis_text(ergebnis)
    assert "NICHT gefunden" in text
    assert "NICHT gespeichert" in text
    # Das eigentliche Feld bleibt davon unberührt gespeichert.
    assert state.anfrage.aktivitaeten_interessen == ["Kultur"]


def test_speichere_feld_feste_wunschorte_teilweise_gefunden_speichert_nur_gefundene():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(
        tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
        feste_wunschorte=[{"name": "Deutsches Museum"}, {"name": "Erfundenes Phantasiemuseum"}],
    )
    assert [w.ort.name for w in state.anfrage.feste_wunschorte] == ["Deutsches Museum"]
    assert "'Erfundenes Phantasiemuseum' wurde über Google Places NICHT gefunden" in _ergebnis_text(ergebnis)


def test_speichere_feld_ohne_argument_keine_schluesselwort_heuristik():
    # Die Beurteilung "unbedingt sehen" liegt allein beim LLM: auch ein eindeutiger Wortlaut im
    # gespeicherten Wert erzeugt ohne das Tool-Argument keinen festen Wunschort und keine Suche.
    state = _wunschort_state()
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen",
          wert=["unbedingt das Deutsche Museum", "unter allen Umständen Schloss Nymphenburg"])
    assert state.anfrage.feste_wunschorte == []
    assert state.maps_client.finde_ort_aufrufe == []


def test_speichere_feld_feste_wunschorte_ungueltige_uhrzeit_wird_nicht_geraten():
    state = _wunschort_state()
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
                     feste_wunschorte=[{"name": "Deutsches Museum", "uhrzeit_minuten": 2000}])
    [wunschort] = state.anfrage.feste_wunschorte
    assert wunschort.uhrzeit_minuten is None
    assert "ungültige Uhrzeit" in _ergebnis_text(ergebnis)


def test_speichere_feld_feste_wunschorte_gleicher_ort_nur_einmal():
    client = _FakeWunschortClient(orte_je_name={"Deutsches Museum": _MUSEUM, "Technikmuseum München": _MUSEUM})
    state = _basis_state(maps_client=client)
    tools = erstelle_tools(state)
    _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
          feste_wunschorte=[{"name": "Deutsches Museum"}, {"name": "Technikmuseum München"}])
    assert len(state.anfrage.feste_wunschorte) == 1


def test_speichere_feld_feste_wunschorte_barrierefreiheit_hinweis_ohne_ausschluss():
    state = _wunschort_state(barrierefrei_je_place_id={"pid-museum": False})
    tools = erstelle_tools(state)
    ergebnis = _rufe(
        tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
        mobilitaetseinschraenkung_stufe="mittel",
        feste_wunschorte=[{"name": "Deutsches Museum"}, {"name": "Schloss Nymphenburg"}],
    )
    # Beide bleiben gespeichert (ausdrücklicher Nutzerwunsch), der Befund geht als Hinweis ans LLM.
    museum, schloss = state.anfrage.feste_wunschorte
    assert museum.barrierefrei is False and museum.barrierefreiheit_geprueft
    assert schloss.barrierefrei is None and schloss.barrierefreiheit_geprueft
    text = _ergebnis_text(ergebnis)
    assert "'Deutsches Museum' ist laut Google Places NICHT barrierefrei" in text
    assert "'Schloss Nymphenburg' hat bei Google Places keine Angabe zur Barrierefreiheit" in text


def test_speichere_feld_feste_wunschorte_barrierefreiheit_wird_bei_spaeterer_einschraenkung_nachgeholt():
    state = _wunschort_state(barrierefrei_je_place_id={"pid-museum": False})
    tools = erstelle_tools(state)
    ohne_einschraenkung = _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
                                feste_wunschorte=[{"name": "Deutsches Museum"}])
    assert "Barrierefreiheit" not in _ergebnis_text(ohne_einschraenkung)
    assert state.anfrage.feste_wunschorte[0].barrierefreiheit_geprueft is False

    spaeter = _rufe(tools, "speichere_feld", feld="gesundheitliche_einschraenkungen", wert="Rollstuhl",
                    mobilitaetseinschraenkung_stufe="stark")
    assert "NICHT barrierefrei" in _ergebnis_text(spaeter)
    assert state.anfrage.feste_wunschorte[0].barrierefreiheit_geprueft is True
    # Nur einmal je Ort gemeldet, nicht bei jedem weiteren Aufruf erneut.
    danach = _rufe(tools, "speichere_feld", feld="budget_gesamt", wert=1500)
    assert "Barrierefreiheit" not in _ergebnis_text(danach)


def test_speichere_feld_leichte_einschraenkung_prueft_barrierefreiheit_nicht():
    state = _wunschort_state(barrierefrei_je_place_id={"pid-museum": False})
    tools = erstelle_tools(state)
    ergebnis = _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
                     mobilitaetseinschraenkung_stufe="leicht", feste_wunschorte=[{"name": "Deutsches Museum"}])
    assert "Barrierefreiheit" not in _ergebnis_text(ergebnis)
    assert state.anfrage.feste_wunschorte[0].barrierefreiheit_geprueft is False


# -- Feste Wunschorte: Anfahrt und Nachhaltigkeitshinweis ---------------------------------------


class _FakeAnfahrtClient(_FakeWunschortClient):
    """Fake mit steuerbarer lokaler Anfahrtsdauer je Distance-Matrix-Modus und festen
    Fernalternativen (Bahn/Fernbus/Auto) für `reisealternativen`."""

    def __init__(self, lokal_je_modus=None, alternativen=None, alternativen_fehler=None, **kwargs):
        super().__init__(
            orte_je_name={"Deutsches Museum": _MUSEUM, "Schloss Nymphenburg": _SCHLOSS}, **kwargs
        )
        self._lokal_je_modus = lokal_je_modus or {}
        self._alternativen = alternativen or []
        self._alternativen_fehler = alternativen_fehler
        self.anfahrt_aufrufe: list[str] = []
        self.alternativen_aufrufe: list[tuple[str, str]] = []

    def anfahrtszeiten_minuten(self, ursprung, ziele, modus="walking"):
        self.anfahrt_aufrufe.append(modus)
        return [self._lokal_je_modus.get(modus, -1) for _ in ziele]

    def reisealternativen(self, von, nach):
        self.alternativen_aufrufe.append((von, nach))
        if self._alternativen_fehler:
            raise RuntimeError(self._alternativen_fehler)
        return list(self._alternativen)


_FERN_BAHN = ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=75, kosten_euro=20.0, distanz_km=80)
_FERN_AUTO = ReiseAlternative(
    verkehrsmittel="Auto", dauer_minuten=50, kosten_euro=16.0, distanz_km=60, umweltfreundlichste_route=True
)


def _anfahrt_state(client, lokaler_transport="zu Fuß", verkehrsmittel=("Bahn",), mit_unterkunft=True):
    state = _basis_state(maps_client=client)
    state.anfrage.zielregionen = ["München"]
    state.anfrage.lokaler_transport_praeferenz = lokaler_transport
    state.anfrage.verkehrsmittel_praeferenz = list(verkehrsmittel)
    if mit_unterkunft:
        state.anfrage.unterkunft_koordinaten = (48.14, 11.57)
    return state


def _speichere_museum(tools, **zusatz):
    return _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
                 feste_wunschorte=[{"name": "Deutsches Museum"}], **zusatz)


def test_anfahrt_45_minuten_lokal_ohne_hinweis():
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 45}, alternativen=[_FERN_BAHN])
    state = _anfahrt_state(client)
    ergebnis = _speichere_museum(erstelle_tools(state))

    anfahrt = state.anfrage.feste_wunschorte[0].anfahrt
    assert anfahrt.verkehrsmittel == "zu Fuß"
    assert anfahrt.dauer_minuten == 45
    assert anfahrt.quelle == "distance_matrix" and anfahrt.modus == "walking"
    # Aus der Distance Matrix ist keine Distanz bekannt -> weder km noch CO₂ erfunden.
    assert anfahrt.distanz_km is None and anfahrt.co2_kg_hin_und_zurueck is None
    assert "Hinweis Nachhaltigkeit" not in _ergebnis_text(ergebnis)
    # Unter der Schwelle wird die Fernverbindung gar nicht erst abgefragt.
    assert client.alternativen_aufrufe == []


def test_anfahrt_90_minuten_nutzt_fernverbindung_passend_zu_f13_mit_km_und_co2():
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 90}, alternativen=[_FERN_AUTO, _FERN_BAHN])
    state = _anfahrt_state(client, verkehrsmittel=("Bahn",))
    ergebnis = _speichere_museum(erstelle_tools(state))

    anfahrt = state.anfrage.feste_wunschorte[0].anfahrt
    # Auto wäre schneller, bestätigt ist aber die Bahn (F13) -> Bahn.
    assert anfahrt.verkehrsmittel == "Bahn"
    assert anfahrt.quelle == "reisealternativen"
    assert anfahrt.dauer_minuten == 75 and anfahrt.distanz_km == 80
    # CO₂ hin und zurück aus emissionsfaktoren.py: 2 × 80 km × 19 g/Pkm = 3,04 kg.
    assert anfahrt.co2_kg_hin_und_zurueck == pytest.approx(3.04)
    assert anfahrt.kosten_euro_einfach == 20.0
    # Anfrage von der Unterkunft zum Wunschort als "lat,lng".
    assert client.alternativen_aufrufe == [("48.14,11.57", f"{_MUSEUM.x},{_MUSEUM.y}")]
    text = _ergebnis_text(ergebnis)
    assert "Hinweis Nachhaltigkeit" in text
    assert "ca. 75 Min." in text and "ca. 80 km" in text
    assert "3.0 kg CO₂" in text
    assert "grob geschätzt" in text and "keine amtlich verifizierten Emissionsfaktoren" in text
    assert "ob der Ort trotzdem bleiben soll" in text


def test_anfahrt_lokal_zu_lang_aber_fernverbindung_kurz_ohne_hinweis():
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 90}, alternativen=[_FERN_BAHN, _FERN_AUTO])
    state = _anfahrt_state(client, verkehrsmittel=("Auto",))
    ergebnis = _speichere_museum(erstelle_tools(state))

    anfahrt = state.anfrage.feste_wunschorte[0].anfahrt
    assert anfahrt.verkehrsmittel == "Auto" and anfahrt.dauer_minuten == 50
    assert anfahrt.umweltfreundlichste_route is True
    assert "Hinweis Nachhaltigkeit" not in _ergebnis_text(ergebnis)


def test_anfahrt_ohne_f14_nutzt_direkt_f13_logik():
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 5}, alternativen=[_FERN_BAHN])
    state = _anfahrt_state(client, lokaler_transport=None)
    _speichere_museum(erstelle_tools(state))

    assert client.anfahrt_aufrufe == []
    assert state.anfrage.feste_wunschorte[0].anfahrt.verkehrsmittel == "Bahn"


def test_anfahrt_ohne_unterkunft_wird_verzoegert_und_bei_f15_nachgeholt():
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 90}, alternativen=[_FERN_BAHN])
    state = _anfahrt_state(client, mit_unterkunft=False)
    tools = erstelle_tools(state)

    vorher = _speichere_museum(tools)
    assert "sobald die Unterkunft bestätigt ist" in _ergebnis_text(vorher)
    assert state.anfrage.feste_wunschorte[0].anfahrt is None
    assert client.anfahrt_aufrufe == [] and client.alternativen_aufrufe == []

    # Bestätigung der Unterkunft (F15) holt die Prüfung nach, ohne den Ort neu zu suchen.
    state.zuletzt_gefundene_unterkunft = Unterkunft(
        id=1, name="Hotel Test", x=48.14, y=11.57, preisniveau=2, zertifiziert_nachhaltig=False, place_id="u1"
    )
    nachher = _rufe(tools, "speichere_feld", feld="unterkunft_anforderungen", wert="zentral")
    assert "Hinweis Nachhaltigkeit" in _ergebnis_text(nachher)
    assert state.anfrage.feste_wunschorte[0].anfahrt.verkehrsmittel == "Bahn"
    assert [aufruf[0] for aufruf in client.finde_ort_aufrufe] == ["Deutsches Museum"]


def test_anfahrt_wird_nur_einmal_je_unterkunft_geprueft_und_bei_wechsel_neu():
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 90}, alternativen=[_FERN_BAHN])
    state = _anfahrt_state(client)
    tools = erstelle_tools(state)
    _speichere_museum(tools)
    assert len(client.alternativen_aufrufe) == 1

    # Erneutes Speichern (gleiche Liste, anderes Feld): kein neuer API-Aufruf, kein erneuter Hinweis.
    erneut = _speichere_museum(tools)
    danach = _rufe(tools, "speichere_feld", feld="budget_gesamt", wert=1500)
    assert len(client.alternativen_aufrufe) == 1
    assert "Hinweis Nachhaltigkeit" not in _ergebnis_text(erneut)
    assert "Hinweis Nachhaltigkeit" not in _ergebnis_text(danach)

    # Andere Unterkunft bestätigt -> Anfahrt wird für die neue Unterkunft neu berechnet.
    state.zuletzt_gefundene_unterkunft = Unterkunft(
        id=2, name="Hotel Neu", x=48.20, y=11.60, preisniveau=2, zertifiziert_nachhaltig=False
    )
    _rufe(tools, "speichere_feld", feld="unterkunft_anforderungen", wert="anderes Hotel")
    assert len(client.alternativen_aufrufe) == 2
    assert state.anfrage.feste_wunschorte[0].anfahrt_geprueft_ab == (48.20, 11.60)


def test_anfahrt_ohne_landverbindung_meldet_ehrlich_und_nennt_keine_fluege():
    client = _FakeAnfahrtClient(lokal_je_modus={}, alternativen=[])
    state = _anfahrt_state(client)
    ergebnis = _speichere_museum(erstelle_tools(state))

    wunschort = state.anfrage.feste_wunschorte[0]
    assert wunschort.anfahrt is None
    assert wunschort.anfahrt_geprueft_ab == (48.14, 11.57)
    text = _ergebnis_text(ergebnis)
    assert "keine Landverbindung" in text
    assert "Flüge sind ausgeschlossen" in text


def test_anfahrt_technischer_fehler_wird_ehrlich_gemeldet():
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 90}, alternativen_fehler="Google-Routes-API-Fehler (HTTP 403)")
    state = _anfahrt_state(client)
    ergebnis = _speichere_museum(erstelle_tools(state))

    # Die lange, aber echte lokale Anfahrt bleibt als einzige Angabe erhalten (mit Hinweis ohne CO₂).
    anfahrt = state.anfrage.feste_wunschorte[0].anfahrt
    assert anfahrt.quelle == "distance_matrix" and anfahrt.dauer_minuten == 90
    text = _ergebnis_text(ergebnis)
    assert "Hinweis Nachhaltigkeit" in text
    assert "keine CO₂-Schätzung möglich" in text
    assert "technisch fehlgeschlagen" in text


def test_anfahrt_technischer_fehler_ohne_lokale_anfahrt():
    client = _FakeAnfahrtClient(alternativen_fehler="Google-Routes-API-Fehler (HTTP 403)")
    state = _anfahrt_state(client)
    ergebnis = _speichere_museum(erstelle_tools(state))

    assert state.anfrage.feste_wunschorte[0].anfahrt is None
    assert "technisch fehlgeschlagen" in _ergebnis_text(ergebnis)


def test_plane_reise_meldet_neuen_anfahrt_hinweis_einmalig_vor_der_planung(tmp_path):
    client = _FakeAnfahrtClient(lokal_je_modus={"walking": 90}, alternativen=[_FERN_BAHN])
    anfrage = _vollstaendige_anfrage(lokaler_transport_praeferenz="zu Fuß")
    state = _basis_state(anfrage=anfrage, maps_client=client, ausgabe_basisname=str(tmp_path / "reiseplan_test"))
    tools = erstelle_tools(state)
    _speichere_museum(tools)  # ohne Unterkunft -> Prüfung nur angekündigt
    # Unterkunftskoordinaten ohne speichere_feld gesetzt: die Prüfung muss vor der Planung greifen.
    state.anfrage.unterkunft_koordinaten = (48.14, 11.57)

    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(_leerer_plan(), None, PlanungsDebugSammlung())) as m_plane, \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        erster_versuch = _rufe(tools, "plane_reise_und_abschliessen")
        assert erster_versuch.get("is_error") is True
        assert "Hinweis Nachhaltigkeit" in _ergebnis_text(erster_versuch)
        m_plane.assert_not_called()

        # Nutzer behält den Ort -> erneuter Aufruf ohne weiteres Argument läuft durch.
        zweiter_versuch = _rufe(tools, "plane_reise_und_abschliessen")

    assert not zweiter_versuch.get("is_error")
    assert state.abgeschlossen is True
    m_plane.assert_called_once()


def test_plane_reise_ohne_feste_wunschorte_unveraendert(tmp_path):
    client = _FakeAnfahrtClient(alternativen=[_FERN_BAHN])
    anfrage = _vollstaendige_anfrage(unterkunft_koordinaten=(48.14, 11.57))
    state = _basis_state(anfrage=anfrage, maps_client=client, ausgabe_basisname=str(tmp_path / "reiseplan_test"))
    tools = erstelle_tools(state)
    with patch("src.fragekatalog.agent_tools.plane_reise", return_value=(_leerer_plan(), None, PlanungsDebugSammlung())), \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        ergebnis = _rufe(tools, "plane_reise_und_abschliessen")
    assert not ergebnis.get("is_error")
    assert client.alternativen_aufrufe == []


def _http_antwort(json_daten: dict, status_code: int = 200) -> Mock:
    antwort = Mock()
    antwort.status_code = status_code
    antwort.json.return_value = json_daten
    antwort.raise_for_status.return_value = None
    return antwort


@patch("src.api.google_maps.requests.post")
@patch("src.api.google_maps.requests.get")
def test_anfahrt_mit_auto_praeferenz_nutzt_routes_api_fuel_efficient(mock_get, mock_post):
    # Echter GoogleMapsClient mit simulierten HTTP-Antworten: lokale Anfahrt (Distance Matrix) 120 Min.,
    # keine Bahn-/Fernbusverbindung (Directions ZERO_RESULTS), Auto über die Routes API.
    def antwort_je_url(url, params=None, timeout=None):
        if "distancematrix" in url:
            return _http_antwort({"status": "OK", "rows": [{"elements": [{"duration": {"value": 7200}}]}]})
        return _http_antwort({"status": "ZERO_RESULTS", "routes": []})

    mock_get.side_effect = antwort_je_url
    mock_post.return_value = _http_antwort({"routes": [
        {"duration": "4000s", "distanceMeters": 70000, "routeLabels": ["DEFAULT_ROUTE"]},
        {"duration": "4200s", "distanceMeters": 65000, "routeLabels": ["FUEL_EFFICIENT"]},
    ]})
    client = GoogleMapsClient(api_key="dummy-key")
    state = _basis_state(maps_client=client)
    state.anfrage.unterkunft_koordinaten = (48.14, 11.57)
    state.anfrage.lokaler_transport_praeferenz = "mit dem Auto"
    state.anfrage.verkehrsmittel_praeferenz = ["Auto"]
    state.anfrage.feste_wunschorte = [FesterWunschort(rohname="Deutsches Museum", ort=_SCHLOSS, dauer_minuten=120)]

    hinweise = pruefe_anfahrten(state.anfrage, client)

    anfahrt = state.anfrage.feste_wunschorte[0].anfahrt
    assert anfahrt.verkehrsmittel == "Auto"
    assert anfahrt.umweltfreundlichste_route is True
    assert anfahrt.dauer_minuten == 70 and anfahrt.distanz_km == 65
    # CO₂: 2 × 65 km × 168 g/Pkm = 21,84 kg.
    assert anfahrt.co2_kg_hin_und_zurueck == pytest.approx(21.84)
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"]["requestedReferenceRoutes"] == ["FUEL_EFFICIENT"]
    [hinweis] = hinweise
    assert "kraftstoffsparendste Route laut Google" in hinweis
    assert "21.8 kg CO₂" in hinweis


def test_anfahrt_mock_schloss_fernblick_weit_entfernt_mit_hinweis():
    client = MockGoogleMapsClient()
    state = _basis_state(maps_client=client)
    state.anfrage.zielregionen = ["Zielregion"]
    state.anfrage.unterkunft_koordinaten = (48.1370, 11.5760)  # Mock-Unterkunft "Hotel Zentral"
    state.anfrage.lokaler_transport_praeferenz = "zu Fuß"
    state.anfrage.verkehrsmittel_praeferenz = ["Bahn"]
    tools = erstelle_tools(state)

    ergebnis = _rufe(tools, "speichere_feld", feld="aktivitaeten_interessen", wert=["Kultur"],
                     feste_wunschorte=[{"name": "Schloss Fernblick"}, {"name": "Altstadt-Museum"}])

    fern, nah = state.anfrage.feste_wunschorte
    assert fern.anfahrt.quelle == "reisealternativen" and fern.anfahrt.verkehrsmittel == "Bahn"
    assert nah.anfahrt.quelle == "distance_matrix"
    assert nah.anfahrt.dauer_minuten <= SCHWELLE_WEITER_WUNSCHORT_MINUTEN
    text = _ergebnis_text(ergebnis)
    assert "'Schloss Fernblick' liegt weit von der Unterkunft entfernt" in text
    assert "'Altstadt-Museum' liegt weit" not in text


# --- Parallele Sitzungen (Freigabe an mehrere Tester, starte_extern.py) ----------------------------
# Alle Web-Sitzungen teilen eine Event-Loop. Die Werkzeuge laufen deshalb im Hintergrund-Thread
# (agent_tools.py `im_hintergrund`), damit eine lange Planung andere Sitzungen nicht anhält.

def test_zweite_sitzung_antwortet_waehrend_erste_sitzung_plant(tmp_path):
    import threading

    planung_laeuft = threading.Event()
    zweite_sitzung_bedient = threading.Event()
    plan = _leerer_plan()

    def langsame_planung(anfrage, maps_client, barrierefreiheit_strikt=False):
        planung_laeuft.set()
        # Blockierte die Planung die Event-Loop, könnte die zweite Sitzung erst NACH dieser
        # Wartezeit bedient werden und das Ereignis wäre hier noch nicht gesetzt.
        assert zweite_sitzung_bedient.wait(timeout=5), "zweite Sitzung wurde während der Planung nicht bedient"
        return plan, None, PlanungsDebugSammlung()

    planende_sitzung = _basis_state(anfrage=_vollstaendige_anfrage(), ausgabe_basisname=str(tmp_path / "a"),
                                    io_kanal=AsyncMock())
    chattende_sitzung = _basis_state()
    plane = next(t for t in erstelle_tools(planende_sitzung) if t.name == "plane_reise_und_abschliessen")
    speichere = next(t for t in erstelle_tools(chattende_sitzung) if t.name == "speichere_feld")

    async def ablauf():
        planung = asyncio.create_task(plane.handler({}))
        assert await asyncio.to_thread(planung_laeuft.wait, 5)
        antwort = await speichere.handler({"feld": "name", "wert": "Bea"})
        zweite_sitzung_bedient.set()
        return await planung, antwort

    with patch("src.fragekatalog.agent_tools.plane_reise", side_effect=langsame_planung), \
         patch("src.fragekatalog.agent_tools.speichere_datei"), \
         patch("src.fragekatalog.agent_tools.speichere_json"), \
         patch("src.fragekatalog.agent_tools.speichere_poi_uebersicht"), \
         patch("src.fragekatalog.agent_tools.sende_mail"):
        ergebnis_planung, ergebnis_chat = asyncio.run(ablauf())

    assert "Gespeichert: name" in ergebnis_chat["content"][0]["text"]
    assert chattende_sitzung.anfrage.name == "Bea"
    assert not ergebnis_planung.get("is_error")
    assert planende_sitzung.abgeschlossen
    planende_sitzung.io_kanal.zeige_status.assert_awaited_once_with("plant_reise")


def test_werkzeuge_einer_sitzung_laufen_nacheinander_verschiedener_sitzungen_parallel():
    import threading
    import time

    gleichzeitig = {"aktuell": 0, "maximum": 0}
    zaehler_sperre = threading.Lock()

    def langsame_pruefung(anfrage, maps_client, liste_neu_gesetzt=False):
        with zaehler_sperre:
            gleichzeitig["aktuell"] += 1
            gleichzeitig["maximum"] = max(gleichzeitig["maximum"], gleichzeitig["aktuell"])
        time.sleep(0.2)
        with zaehler_sperre:
            gleichzeitig["aktuell"] -= 1
        return []

    def speichere_tool(state):
        return next(t for t in erstelle_tools(state) if t.name == "speichere_feld")

    async def zwei_aufrufe(erstes_tool, zweites_tool):
        await asyncio.gather(
            erstes_tool.handler({"feld": "name", "wert": "Ada"}),
            zweites_tool.handler({"feld": "wohnort", "wert": "Hildesheim"}),
        )

    with patch("src.fragekatalog.agent_tools.pruefe_anfahrten", side_effect=langsame_pruefung):
        eine_sitzung = speichere_tool(_basis_state())
        asyncio.run(zwei_aufrufe(eine_sitzung, eine_sitzung))
        maximum_eine_sitzung = gleichzeitig["maximum"]

        gleichzeitig["maximum"] = 0
        asyncio.run(zwei_aufrufe(speichere_tool(_basis_state()), speichere_tool(_basis_state())))
        maximum_zwei_sitzungen = gleichzeitig["maximum"]

    assert maximum_eine_sitzung == 1  # Sperre je Sitzung: kein gleichzeitiges Ändern der Anfrage
    assert maximum_zwei_sitzungen == 2  # verschiedene Sitzungen blockieren sich nicht gegenseitig
