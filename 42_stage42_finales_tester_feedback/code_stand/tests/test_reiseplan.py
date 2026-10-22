"""Tests für die Reiseplan-Ausgabe (src/ausgabe/reiseplan.py)."""
import csv

from src.api.typen import POI, ReiseAlternative, Teilstrecke
from src.ausgabe.reiseplan import Reiseplan, als_html, als_kartendaten, als_text, routen_link, speichere_poi_uebersicht
from src.optimierung.toptw import Besuch, Tagesroute
from src.optimierung.verkehrsmittelwahl import BewerteteAlternative

_BAHN = BewerteteAlternative(
    alternative=ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=300, kosten_euro=80, distanz_km=500),
    co2_kg=9.5, score=0.1,
)
_LANGE_ANREISE = BewerteteAlternative(
    alternative=ReiseAlternative(verkehrsmittel="Bahn", dauer_minuten=1119, kosten_euro=200, distanz_km=3000),
    co2_kg=21.3, score=0.5,
)
_POI = POI(id=1, name="Kletterroute XY", kategorie="klettern", x=0.0, y=0.0, score=3.0, required_time=180, opening=0, closing=600)


def _basis_plan(**zusatz) -> Reiseplan:
    parameter = {"hinreise": _BAHN, "tagesrouten": [], "rueckreise": _BAHN}
    parameter.update(zusatz)
    return Reiseplan(**parameter)


def test_als_text_ohne_kandidaten_und_hinweis_zeigt_nichts_zusaetzliches():
    text = als_text(_basis_plan())
    assert "Weitere gefundene Unterkunfts-Empfehlungen" not in text
    assert "Sicherheit" not in text


def test_als_text_zeigt_unterkunft_mit_link():
    text = als_text(_basis_plan(unterkunft_name="Hotel Zentral", unterkunft_place_id="abc123"))
    assert "Unterkunft: Hotel Zentral" in text
    assert "query_place_id=abc123" in text


def test_als_text_zeigt_sicherheitshinweis_nur_wenn_gesetzt():
    text = als_text(_basis_plan(sicherheitshinweis="Sicherheit war dir wichtig – ..."))
    assert "Sicherheit war dir wichtig" in text


def test_als_html_zeigt_unterkunft_und_sicherheitshinweis():
    html_text = als_html(_basis_plan(unterkunft_name="Hotel Zentral", sicherheitshinweis="Bitte Hinweise prüfen"))
    assert "Hotel Zentral" in html_text
    assert "Bitte Hinweise prüfen" in html_text


def test_als_text_zeigt_fahrzeit_von_unterkunft_und_zwischen_pois():
    # Regression (Anforderung des Product Owners: Fahrzeit zwischen den POIs in der
    # Tagesansicht zeigen) – Fahrzeit steckt bereits exakt in
    # ankunft/abfahrt (siehe toptw.py), keine neue Berechnung nötig, nur die Anzeige.
    zweiter_poi = POI(id=2, name="Trajansmärkte", kategorie="museum", x=0.0, y=0.0, score=2.0,
                       required_time=90, opening=0, closing=600)
    tag1 = Tagesroute(besuche=[
        Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195),
        Besuch(poi=zweiter_poi, ankunft=210, wartezeit=0, abfahrt=300),
    ])
    text = als_text(_basis_plan(tagesrouten=[tag1]))
    assert "→ 15 Min. von Unterkunft" in text
    assert "→ 15 Min. von Kletterroute XY" in text  # 210 (ankunft) - 195 (vorherige abfahrt)


def test_als_html_zeigt_fahrzeit_von_unterkunft_und_zwischen_pois():
    zweiter_poi = POI(id=2, name="Trajansmärkte", kategorie="museum", x=0.0, y=0.0, score=2.0,
                       required_time=90, opening=0, closing=600)
    tag1 = Tagesroute(besuche=[
        Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195),
        Besuch(poi=zweiter_poi, ankunft=210, wartezeit=0, abfahrt=300),
    ])
    html_text = als_html(_basis_plan(tagesrouten=[tag1]))
    assert "→ 15 min von Unterkunft" in html_text
    assert "→ 15 min von Kletterroute XY" in html_text


def test_als_text_tag1_nennt_ankunft_und_check_in():
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    plan = _basis_plan(hinreise=_LANGE_ANREISE, tagesrouten=[tag1])
    text = als_text(plan)
    assert "Tag 1 (Ankunft)" in text
    assert "Ankunft mit Bahn nach 18h 39min – danach Check-in in der Unterkunft." in text
    assert "Ab Ankunft:" in text
    # Rückmeldung des Product Owners nach echtem Browser-Test (Phase 57/58, siehe
    # doku/30_stage30_zeit_fotos_verleih_layout_avatar/README.md): weder eine nackte relative Dauer
    # ("nach 15min", missverständlich als Aufenthaltsdauer lesbar) noch eine erfundene/angenommene
    # Uhrzeit ("ca. 09:15 Uhr") – stattdessen eine relative Dauer MIT Ankerwort direkt am Wert
    # ("15min nach Ankunft"), dadurch eindeutig als Zeitpunkt seit Ankunft erkennbar, keine
    # erfundene Uhrzeit (Grundprinzip 1 bleibt gewahrt).
    assert "15min nach Ankunft: Kletterroute XY (bis 3h 15min nach Ankunft, Score 3.0)" in text


def test_als_text_ohne_tagesstart_minuten_zeigt_anker_auch_ab_tag2():
    # Ohne F20-Antwort ist an KEINEM Tag eine echte Uhrzeit bekannt – ab Tag 2 lautet der Anker
    # "Tagesbeginn" statt "Ankunft" (siehe test_als_text_tag1_nennt_ankunft_und_check_in).
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    tag2 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=30, wartezeit=0, abfahrt=210)])
    text = als_text(_basis_plan(tagesrouten=[tag1, tag2]))
    assert "30min nach Tagesbeginn" in text
    assert "bis 3h 30min nach Tagesbeginn" in text
    assert "nicht als Aufenthaltsdauer" in text  # einmaliger Hinweis, siehe _uhrzeit_hinweis_text
    assert "ca." not in text  # keine angenommene Uhrzeit mehr (verworfen, siehe Phase 58)


def test_als_text_mit_tagesstart_minuten_zeigt_echte_uhrzeit_ab_tag2_nicht_tag1():
    # Ab Tag 2 mit F20-Antwort: ECHTE Uhrzeit. Tag 1 bleibt IMMER relativ zur Ankunft, weil die
    # tatsächliche Ankunftsuhrzeit der Hinreise nirgends bekannt ist (Grundprinzip 1) – siehe
    # reiseplan.py `_zeitpunkt_text`.
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    tag2 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=30, wartezeit=0, abfahrt=210)])
    text = als_text(_basis_plan(tagesrouten=[tag1, tag2], tagesstart_minuten=9 * 60))

    zeilen = text.splitlines()
    tag1_index = next(i for i, z in enumerate(zeilen) if z.startswith("Tag 1"))
    tag2_index = next(i for i, z in enumerate(zeilen) if z.startswith("Tag 2"))
    tag1_zeilen = zeilen[tag1_index:tag2_index]
    tag2_zeilen = zeilen[tag2_index:]
    assert any("nach Ankunft" in z and "15min" in z for z in tag1_zeilen)
    assert not any("nach Ankunft" in z or "nach Tagesbeginn" in z for z in tag2_zeilen)
    assert any("09:30" in z for z in tag2_zeilen)  # 09:00 + 30 Min., echte Uhrzeit
    assert any("12:30" in z for z in tag2_zeilen)  # 09:00 + 210 Min.


def test_als_text_uhrzeit_hinweis_nur_wenn_tagesstart_minuten_gesetzt():
    ohne = als_text(_basis_plan())
    assert "basieren auf deiner angegebenen Tagesstart" not in ohne
    mit = als_text(_basis_plan(tagesstart_minuten=9 * 60))
    assert "basieren auf deiner angegebenen Tagesstart" in mit
    assert "09:00" in mit


def test_als_html_mit_tagesstart_minuten_zeigt_echte_uhrzeit_ab_tag2():
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    tag2 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=30, wartezeit=0, abfahrt=210)])
    html_text = als_html(_basis_plan(tagesrouten=[tag1, tag2], tagesstart_minuten=9 * 60))
    assert "09:30" in html_text
    assert "12:30" in html_text


def test_als_text_zwischentag_hat_rueckweg_hinweis_letzter_tag_nicht():
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    tag2 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=10, wartezeit=0, abfahrt=190)])
    text = als_text(_basis_plan(tagesrouten=[tag1, tag2]))
    zeilen = text.splitlines()
    tag1_index = next(i for i, z in enumerate(zeilen) if z.startswith("Tag 1"))
    tag2_index = next(i for i, z in enumerate(zeilen) if z.startswith("Tag 2"))
    assert any("Rückweg zur Unterkunft" in z for z in zeilen[tag1_index:tag2_index])
    assert not any("Rückweg zur Unterkunft" in z for z in zeilen[tag2_index:])


def test_als_text_leerer_tag_zeigt_kein_programm():
    text = als_text(_basis_plan(tagesrouten=[Tagesroute(besuche=[])]))
    assert "(kein Programm eingeplant)" in text
    assert "Ab Ankunft:" not in text


def test_als_html_tag1_nennt_ankunft_und_check_in():
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    html_text = als_html(_basis_plan(hinreise=_LANGE_ANREISE, tagesrouten=[tag1]))
    assert "Tag 1 (Ankunft)" in html_text
    assert "Check-in in der Unterkunft" in html_text
    assert "Ab Ankunft" in html_text


def test_als_text_zeigt_einleitung_grobe_struktur_statt_fertiger_plan():
    # Regression (Entscheidung des Product Owners): der Plan ist eine grobe Struktur als
    # Vorschlag, keine fertig festgelegte Reise; der Nutzer entscheidet selbst.
    text = als_text(_basis_plan())
    assert "grobe Struktur" in text
    assert "kein fertig gebuchter Plan" in text


def test_als_text_tagesueberschrift_ist_als_vorschlag_gekennzeichnet():
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    text = als_text(_basis_plan(tagesrouten=[tag1]))
    assert "unser Vorschlag" in text


def test_als_text_ohne_weitere_empfehlungen_zeigt_nichts_zusaetzliches():
    text = als_text(_basis_plan())
    assert "Weitere Empfehlungen in der Nähe" not in text


def test_als_text_zeigt_weitere_aktivitaeten_empfehlungen_mit_link():
    # POIs, die Optimierung 1 NICHT in die Tagesroute übernommen hat (Zeitfenster/Budget), werden
    # nicht verworfen, sondern als frei kombinierbare Empfehlung gezeigt (Entscheidung des Product Owners).
    weitere = [POI(id=2, name="Trajansmärkte", kategorie="museum", x=0.0, y=0.0, score=2.0,
                    required_time=90, opening=0, closing=600, place_id="poi-2")]
    text = als_text(_basis_plan(weitere_aktivitaeten_empfehlungen=weitere))
    assert "Weitere Empfehlungen in der Nähe" in text
    assert "Trajansmärkte" in text
    assert "query_place_id=poi-2" in text


def test_als_text_zeigt_einschraenkungshinweise():
    text = als_text(_basis_plan(einschraenkungshinweise=["Hinweis: 'Fischerhütte' ist laut Namen ..."]))
    assert "Hinweis: 'Fischerhütte'" in text


def test_als_text_ohne_leihwunsch_zeigt_nichts_zum_verleih():
    text = als_text(_basis_plan())
    assert "geliehenen" not in text
    assert "Verleih" not in text


def test_als_text_zeigt_gefundenen_verleih_mit_link():
    poi = POI(id=13, name="Autoverleih City", kategorie="car_rental", x=0.0, y=0.0, score=1.0,
              required_time=15, opening=0, closing=600, place_id="mock-poi-13")
    text = als_text(_basis_plan(lokales_leihfahrzeug_gewuenscht="Auto", lokaler_verleih_poi=poi))
    assert "Auto" in text
    assert "Autoverleih City" in text
    assert "query_place_id=mock-poi-13" in text


def test_als_text_leihwunsch_ohne_treffer_zeigt_ehrliche_fehlanzeige():
    # Regression: KEIN erfundener Verleih, wenn nichts gefunden wurde (Grundprinzip 1).
    text = als_text(_basis_plan(lokales_leihfahrzeug_gewuenscht="Fahrrad", lokaler_verleih_poi=None))
    assert "Fahrrad" in text
    assert "konnten wir aber keinen Verleih finden" in text


def test_als_html_zeigt_weitere_empfehlungen_und_einschraenkungshinweise():
    weitere = [POI(id=2, name="Trajansmärkte", kategorie="museum", x=0.0, y=0.0, score=2.0,
                    required_time=90, opening=0, closing=600, place_id="poi-2")]
    html_text = als_html(_basis_plan(
        weitere_aktivitaeten_empfehlungen=weitere, einschraenkungshinweise=["Hinweis: Konflikt gefunden"],
    ))
    assert "Weitere Empfehlungen in der Nähe" in html_text
    assert "Trajansmärkte" in html_text
    assert "Hinweis: Konflikt gefunden" in html_text


def test_als_text_leerer_tag_zeigt_beispiele_aus_weiteren_empfehlungen():
    # Anforderung des Product Owners: ein Tag ohne Programm zeigt zwei bis drei Beispiele statt
    # leer zu bleiben (ursprünglich zu geführten Touren, generisch für JEDEN nicht eingeplanten
    # Kandidaten umgesetzt).
    tour = POI(id=2, name="Stadtführung Altstadt", kategorie="travel_agency", x=0.0, y=0.0, score=2.0,
               required_time=120, opening=0, closing=600, place_id="poi-tour")
    text = als_text(_basis_plan(tagesrouten=[Tagesroute(besuche=[])], weitere_aktivitaeten_empfehlungen=[tour]))
    assert "(kein Programm eingeplant)" not in text
    assert "mögliche Beispiele für diesen Tag" in text
    assert "Stadtführung Altstadt" in text


def test_als_text_leerer_tag_beispiel_verschwindet_aus_weiteren_empfehlungen():
    # Kein Duplikat: ein POI, der schon als Tages-Beispiel gezeigt wird, taucht nicht zusätzlich
    # noch einmal in der allgemeinen "Weitere Empfehlungen"-Liste auf.
    tour = POI(id=2, name="Stadtführung Altstadt", kategorie="travel_agency", x=0.0, y=0.0, score=2.0,
               required_time=120, opening=0, closing=600, place_id="poi-tour")
    text = als_text(_basis_plan(tagesrouten=[Tagesroute(besuche=[])], weitere_aktivitaeten_empfehlungen=[tour]))
    assert text.count("Stadtführung Altstadt") == 1


def test_als_html_leerer_tag_zeigt_beispiele_statt_kein_programm():
    tour = POI(id=2, name="Stadtführung Altstadt", kategorie="travel_agency", x=0.0, y=0.0, score=2.0,
               required_time=120, opening=0, closing=600, place_id="poi-tour")
    html_text = als_html(_basis_plan(tagesrouten=[Tagesroute(besuche=[])], weitere_aktivitaeten_empfehlungen=[tour]))
    assert "(kein Programm eingeplant)" not in html_text
    assert "Stadtführung Altstadt" in html_text


def test_als_text_zeigt_beispielrestaurants_je_tag():
    # "einfach Beispielrestaurants in der Nähe von der Unterkunft" – Restaurants laufen NICHT durch
    # Optimierung 1 (siehe pipeline.py), werden aber trotzdem angezeigt, auch an einem Tag MIT
    # normalem Programm.
    restaurant = POI(id=3, name="Trattoria da Nino", kategorie="restaurant", x=0.0, y=0.0, score=1.0,
                      required_time=60, opening=0, closing=600, place_id="poi-restaurant")
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    text = als_text(_basis_plan(tagesrouten=[tag1], beispielrestaurants=[restaurant]))
    assert "Beispielrestaurants in der Nähe der Unterkunft" in text
    assert "Trattoria da Nino" in text


def test_als_text_ohne_beispielrestaurants_zeigt_nichts_zusaetzliches():
    text = als_text(_basis_plan())
    assert "Beispielrestaurants" not in text


def test_als_html_zeigt_beispielrestaurants_je_tag():
    restaurant = POI(id=3, name="Trattoria da Nino", kategorie="restaurant", x=0.0, y=0.0, score=1.0,
                      required_time=60, opening=0, closing=600, place_id="poi-restaurant")
    html_text = als_html(_basis_plan(tagesrouten=[Tagesroute(besuche=[])], beispielrestaurants=[restaurant]))
    assert "Beispielrestaurants in der Nähe der Unterkunft" in html_text
    assert "Trattoria da Nino" in html_text


def test_als_text_letzter_tag_mit_tour_beispielen_zeigt_touren_statt_kein_programm():
    # Reservierter Tag für geführte Touren (siehe pipeline.py `_trenne_tour_beispiele_ab`) – KEIN
    # optimiertes Programm, aber auch NICHT "kein Programm eingeplant", sondern die echten Touren.
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    tour = POI(id=5, name="Stadtführung Altstadt", kategorie="travel_agency", x=0.0, y=0.0, score=1.0,
               required_time=120, opening=0, closing=600, place_id="poi-tour")
    text = als_text(_basis_plan(tagesrouten=[tag1, Tagesroute(besuche=[])], tour_tag_beispiele=[tour]))
    assert "(kein Programm eingeplant)" not in text
    assert "geführte Tour" in text
    assert "Stadtführung Altstadt" in text


def test_als_text_tour_tag_beispiele_nicht_doppelt_in_weiteren_empfehlungen():
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    tour = POI(id=5, name="Stadtführung Altstadt", kategorie="travel_agency", x=0.0, y=0.0, score=1.0,
               required_time=120, opening=0, closing=600, place_id="poi-tour")
    weiteres = POI(id=6, name="Anderer Fund", kategorie="museum", x=0.0, y=0.0, score=1.0,
                   required_time=60, opening=0, closing=600, place_id="poi-anderer")
    text = als_text(_basis_plan(
        tagesrouten=[tag1, Tagesroute(besuche=[])], tour_tag_beispiele=[tour],
        weitere_aktivitaeten_empfehlungen=[weiteres],
    ))
    assert text.count("Stadtführung Altstadt") == 1
    assert "Anderer Fund" in text  # der reservierte Tag verbraucht NICHT den generischen Vorrat


def test_als_html_letzter_tag_mit_tour_beispielen_zeigt_touren():
    tour = POI(id=5, name="Stadtführung Altstadt", kategorie="travel_agency", x=0.0, y=0.0, score=1.0,
               required_time=120, opening=0, closing=600, place_id="poi-tour")
    html_text = als_html(_basis_plan(tagesrouten=[Tagesroute(besuche=[])], tour_tag_beispiele=[tour]))
    assert "(kein Programm eingeplant)" not in html_text
    assert "Stadtführung Altstadt" in html_text


def test_als_text_letzter_tag_mit_lernaktivitaet_zeigt_kurs_statt_kein_programm():
    # Genau wie geführte Touren behandelt (Entscheidung des Product Owners): ein ausdrücklicher
    # Lernwunsch darf nie vom Optimierungsalgorithmus aussortiert werden können.
    kochkurs = POI(id=7, name="Kochkurs Wiener Küche", kategorie="point_of_interest", x=0.0, y=0.0,
                    score=1.0, required_time=180, opening=0, closing=600, place_id="poi-kochkurs")
    text = als_text(_basis_plan(tagesrouten=[Tagesroute(besuche=[])], lernaktivitaet_tag_beispiele=[kochkurs]))
    assert "(kein Programm eingeplant)" not in text
    assert "Lernaktivität" in text
    assert "Kochkurs Wiener Küche" in text


def test_als_text_tour_und_lernaktivitaet_bekommen_getrennte_tage():
    # Beide Sonderkategorien gleichzeitig gefunden -> ZWEI getrennte reservierte Tage (Rückfrage-
    # Ergebnis), nicht ein gemeinsamer.
    tag1 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    tour = POI(id=5, name="Stadtführung Altstadt", kategorie="travel_agency", x=0.0, y=0.0, score=1.0,
               required_time=120, opening=0, closing=600, place_id="poi-tour")
    kochkurs = POI(id=7, name="Kochkurs Wiener Küche", kategorie="point_of_interest", x=0.0, y=0.0,
                    score=1.0, required_time=180, opening=0, closing=600, place_id="poi-kochkurs")
    text = als_text(_basis_plan(
        tagesrouten=[tag1, Tagesroute(besuche=[]), Tagesroute(besuche=[])],
        tour_tag_beispiele=[tour], lernaktivitaet_tag_beispiele=[kochkurs],
    ))
    zeilen = text.splitlines()
    tag2_index = next(i for i, z in enumerate(zeilen) if z.startswith("Tag 2"))
    tag3_index = next(i for i, z in enumerate(zeilen) if z.startswith("Tag 3"))
    tag2_block = "\n".join(zeilen[tag2_index:tag3_index])
    tag3_block = "\n".join(zeilen[tag3_index:])
    assert "Stadtführung Altstadt" in tag2_block and "Kochkurs Wiener Küche" not in tag2_block
    assert "Kochkurs Wiener Küche" in tag3_block and "Stadtführung Altstadt" not in tag3_block


def test_als_text_zeigt_umstiege_und_wartezeit_statt_nur_gesamtdauer():
    # Regression (Anforderung des Product Owners: Teilstrecken mit Umstiegen und Wartezeiten
    # statt nur einer Gesamtdauer).
    bahn_mit_umstieg = BewerteteAlternative(
        alternative=ReiseAlternative(
            verkehrsmittel="Bahn", dauer_minuten=60, kosten_euro=40, distanz_km=100,
            teilstrecken=[
                Teilstrecke(modus="TRANSIT", linie="ICE 123", von="Berlin Hbf", nach="Fulda", dauer_minuten=30),
                Teilstrecke(modus="TRANSIT", linie="RE 456", von="Fulda", nach="München Hbf", dauer_minuten=25, wartezeit_minuten=5),
            ],
        ),
        co2_kg=9.5, score=0.1,
    )
    text = als_text(_basis_plan(hinreise=bahn_mit_umstieg))

    assert "ICE 123: Berlin Hbf → Fulda (30 min)" in text
    assert "Umstieg in Fulda (5 min Wartezeit)" in text
    assert "RE 456: Fulda → München Hbf (25 min)" in text


def test_als_text_ohne_teilstrecken_zeigt_nur_gesamtdauer():
    text = als_text(_basis_plan())  # _BAHN hat keine teilstrecken (Default leer)
    assert "Umstieg" not in text


def test_als_html_zeigt_umstiege_und_wartezeit():
    bahn_mit_umstieg = BewerteteAlternative(
        alternative=ReiseAlternative(
            verkehrsmittel="Bahn", dauer_minuten=60, kosten_euro=40, distanz_km=100,
            teilstrecken=[
                Teilstrecke(modus="TRANSIT", linie="ICE 123", von="Berlin Hbf", nach="Fulda", dauer_minuten=30),
                Teilstrecke(modus="TRANSIT", linie="RE 456", von="Fulda", nach="München Hbf", dauer_minuten=25, wartezeit_minuten=5),
            ],
        ),
        co2_kg=9.5, score=0.1,
    )
    html_text = als_html(_basis_plan(hinreise=bahn_mit_umstieg))

    assert "ICE 123: Berlin Hbf → Fulda (30 min)" in html_text
    assert "Umstieg in Fulda (5 min Wartezeit)" in html_text


def test_speichere_poi_uebersicht_listet_eingeplante_und_nicht_eingeplante_pois(tmp_path):
    # Regression (Anforderung des Product Owners: alle Kandidaten sichtbar machen, um die
    # Funktionsweise von Optimierung 1 nachprüfen zu können).
    eingeplant = POI(id=1, name="Kletterroute XY", kategorie="klettern", x=0.0, y=0.0, score=3.0,
                      required_time=180, opening=0, closing=600, place_id="poi-1")
    nicht_eingeplant = POI(id=2, name="Trajansmärkte", kategorie="museum", x=0.0, y=0.0, score=2.0,
                            required_time=90, opening=0, closing=600)
    tag1 = Tagesroute(besuche=[Besuch(poi=eingeplant, ankunft=15, wartezeit=0, abfahrt=195)])
    plan = _basis_plan(tagesrouten=[tag1], weitere_aktivitaeten_empfehlungen=[nicht_eingeplant])

    pfad = tmp_path / "pois.csv"
    speichere_poi_uebersicht(plan, pfad)

    with pfad.open(encoding="utf-8-sig", newline="") as datei:
        zeilen = list(csv.DictReader(datei, delimiter=";"))

    assert len(zeilen) == 2
    eingeplante_zeile = next(z for z in zeilen if z["name"] == "Kletterroute XY")
    assert eingeplante_zeile["status"] == "eingeplant"
    assert eingeplante_zeile["tag"] == "1"
    assert eingeplante_zeile["score"] == "3.00"
    assert eingeplante_zeile["ankunft"] == "15"

    nicht_eingeplante_zeile = next(z for z in zeilen if z["name"] == "Trajansmärkte")
    assert nicht_eingeplante_zeile["status"] == "nicht eingeplant (Kandidat)"
    assert nicht_eingeplante_zeile["tag"] == "-"
    assert nicht_eingeplante_zeile["ankunft"] == "-"


def test_routen_link_baut_directions_url_mit_koordinaten():
    link = routen_link((48.1, 11.5), (48.2, 11.6), "bicycling")
    assert link == "https://www.google.com/maps/dir/?api=1&origin=48.1%2C11.5&destination=48.2%2C11.6&travelmode=bicycling"


def test_routen_link_akzeptiert_ortsnamen_statt_koordinaten():
    link = routen_link("Hildesheim", "Hannover", "transit")
    assert link == "https://www.google.com/maps/dir/?api=1&origin=Hildesheim&destination=Hannover&travelmode=transit"


def test_routen_link_ohne_travelmode_laesst_parameter_weg():
    link = routen_link("Hildesheim", "Hannover", None)
    assert "travelmode" not in link


def test_routen_link_ohne_ursprung_oder_ziel_ist_none():
    assert routen_link(None, "Hannover", "driving") is None
    assert routen_link("Hildesheim", None, "driving") is None


def test_als_text_zeigt_etappen_routen_link():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195, anfahrt_modus="bicycling")
    text = als_text(_basis_plan(
        tagesrouten=[Tagesroute(besuche=[besuch])], unterkunft_koordinaten=(48.0, 11.0),
    ))
    assert "maps/dir/?api=1&origin=48.0%2C11.0&destination=0.0%2C0.0&travelmode=bicycling" in text


def test_als_text_ohne_unterkunft_koordinaten_zeigt_keinen_etappen_link():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195, anfahrt_modus="bicycling")
    text = als_text(_basis_plan(tagesrouten=[Tagesroute(besuche=[besuch])]))
    assert "maps/dir" not in text


def test_als_text_zeigt_hin_und_rueckreise_routen_link():
    text = als_text(_basis_plan(wohnort="Hildesheim", zielort="Hannover"))
    assert "maps/dir/?api=1&origin=Hildesheim&destination=Hannover&travelmode=transit" in text
    assert "maps/dir/?api=1&origin=Hannover&destination=Hildesheim&travelmode=transit" in text


def test_als_text_bevorzugt_praezise_unterkunft_fuer_hinreise_und_rueckreise_link():
    # Regression (Rückmeldung des Product Owners: der Link zur groben Zielstadt allein war "nur halbwegs gut") –
    # sobald eine Unterkunft bestätigt ist, zeigt der Link auf deren GENAUE Koordinaten statt nur
    # auf die Stadt, damit die tatsächlich gebuchte Route in Google Maps sichtbar wird.
    text = als_text(_basis_plan(wohnort="Hildesheim", zielort="Hannover", unterkunft_koordinaten=(52.37, 9.72)))
    assert "maps/dir/?api=1&origin=Hildesheim&destination=52.37%2C9.72&travelmode=transit" in text
    assert "maps/dir/?api=1&origin=52.37%2C9.72&destination=Hildesheim&travelmode=transit" in text
    assert "destination=Hannover" not in text
    assert "origin=Hannover" not in text


def test_als_text_ohne_wohnort_oder_zielort_zeigt_keinen_hinreise_link():
    text = als_text(_basis_plan())
    assert "maps/dir" not in text


def test_als_html_zeigt_etappen_und_hinreise_routen_link():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195, anfahrt_modus="walking")
    html_text = als_html(_basis_plan(
        tagesrouten=[Tagesroute(besuche=[besuch])], unterkunft_koordinaten=(48.0, 11.0),
        wohnort="Hildesheim", zielort="Hannover",
    ))
    assert "Route in Google Maps ansehen" in html_text
    # Hinreise-Link zeigt auf die GENAUE Unterkunft (Koordinaten), nicht mehr nur den groben
    # Zielort-Namen, siehe test_als_text_bevorzugt_praezise_unterkunft_fuer_hinreise_link.
    assert "maps/dir/?api=1&amp;origin=Hildesheim&amp;destination=48.0%2C11.0&amp;travelmode=transit" in html_text


def test_als_kartendaten_zeigt_routen_link_je_besuch():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195, anfahrt_modus="driving")
    daten = als_kartendaten(_basis_plan(
        tagesrouten=[Tagesroute(besuche=[besuch])], unterkunft_koordinaten=(48.0, 11.0),
    ), lambda _pid: None)
    link = daten["tage"][0]["besuche"][0]["routen_link"]
    assert "travelmode=driving" in link


def test_als_text_zeigt_verkehrsmittel_je_etappe():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195, anfahrt_modus="bicycling")
    text = als_text(_basis_plan(tagesrouten=[Tagesroute(besuche=[besuch])]))
    assert "→ 15 Min. (mit dem Fahrrad) von Unterkunft" in text


def test_als_text_ohne_anfahrt_modus_zeigt_keine_klammer():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)  # anfahrt_modus bleibt None
    text = als_text(_basis_plan(tagesrouten=[Tagesroute(besuche=[besuch])]))
    assert "→ 15 Min. von Unterkunft" in text
    assert "(" not in text.split("→ 15 Min.")[1].split("von Unterkunft")[0]


def test_als_html_zeigt_verkehrsmittel_je_etappe():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195, anfahrt_modus="transit")
    html_text = als_html(_basis_plan(tagesrouten=[Tagesroute(besuche=[besuch])]))
    assert "mit öffentlichen Verkehrsmitteln" in html_text


def test_als_kartendaten_zeigt_verkehrsmittel_je_besuch():
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195, anfahrt_modus="driving")
    daten = als_kartendaten(_basis_plan(tagesrouten=[Tagesroute(besuche=[besuch])]), lambda _pid: None)
    assert daten["tage"][0]["besuche"][0]["verkehrsmittel"] == "mit dem Auto"


def test_als_text_ohne_kostenschaetzung_zeigt_nichts():
    text = als_text(_basis_plan())
    assert "Geschätzte Gesamtkosten" not in text


def test_als_text_zeigt_kostenschaetzung_im_rahmen_des_budgets():
    text = als_text(_basis_plan(geschaetzte_kosten_euro=500.0, budget_gesamt=800.0))
    assert "ca. 500 €" in text
    assert "im Rahmen deines angegebenen Budgets von 800 €" in text
    assert "300 € Puffer" in text


def test_als_text_zeigt_kostenschaetzung_ueber_dem_budget():
    text = als_text(_basis_plan(geschaetzte_kosten_euro=900.0, budget_gesamt=800.0))
    assert "übersteigt dein angegebenes Budget von 800 €" in text
    assert "100 €" in text


def test_als_text_ohne_budget_zeigt_nur_die_schaetzung():
    text = als_text(_basis_plan(geschaetzte_kosten_euro=500.0))
    assert "ca. 500 €" in text
    assert "Budget" not in text


def test_als_text_kennzeichnet_unvollstaendige_kostenschaetzung():
    text = als_text(_basis_plan(geschaetzte_kosten_euro=500.0, kosten_unvollstaendig=True))
    assert "unvollständig" in text


def test_als_html_zeigt_kostenschaetzung():
    html_text = als_html(_basis_plan(geschaetzte_kosten_euro=500.0, budget_gesamt=800.0))
    assert "ca. 500 €" in html_text
    assert "im Rahmen deines angegebenen Budgets" in html_text


def test_als_kartendaten_baut_unterkunft_und_tageskarten_mit_foto_url():
    poi_mit_foto = POI(id=1, name="Kletterroute XY", kategorie="klettern", x=0.0, y=0.0, score=3.0,
                        required_time=180, opening=0, closing=600, place_id="poi-1")
    tag1 = Tagesroute(besuche=[Besuch(poi=poi_mit_foto, ankunft=15, wartezeit=0, abfahrt=195)])
    plan = _basis_plan(tagesrouten=[tag1], unterkunft_name="Hotel Zentral", unterkunft_place_id="hotel-1")

    daten = als_kartendaten(plan, lambda place_id: f"/fotos/{place_id}.jpg" if place_id else None)

    assert daten["unterkunft"]["name"] == "Hotel Zentral"
    assert daten["unterkunft"]["foto_url"] == "/fotos/hotel-1.jpg"
    assert len(daten["tage"]) == 1
    assert daten["tage"][0]["tag"] == 1
    assert daten["tage"][0]["ankunftstag"] is True
    besuch_karte = daten["tage"][0]["besuche"][0]
    assert besuch_karte["name"] == "Kletterroute XY"
    assert besuch_karte["kategorie"] == "klettern"
    assert besuch_karte["foto_url"] == "/fotos/poi-1.jpg"
    assert "query_place_id=poi-1" in besuch_karte["maps_link"]


def test_als_kartendaten_ohne_unterkunft_liefert_none():
    daten = als_kartendaten(_basis_plan(), lambda _place_id: None)
    assert daten["unterkunft"] is None
    assert daten["tage"] == []


def test_als_kartendaten_ohne_foto_liefert_keine_foto_url():
    daten = als_kartendaten(_basis_plan(unterkunft_name="Hotel Zentral"), lambda _place_id: None)
    assert daten["unterkunft"]["foto_url"] is None


def test_als_kartendaten_zeigt_hinreise_und_rueckreise_getrennt():
    # Regression (Befund aus einem Live-Test): die Rückreise war früher literal dieselbe
    # `BewerteteAlternative` wie die Hinreise (siehe pipeline.py-Fix) – hier wird geprüft, dass die
    # Web-Kartendaten beide unabhängig voneinander abbilden, statt eine Seite zu duplizieren.
    rueck = BewerteteAlternative(
        alternative=ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=280, kosten_euro=90, distanz_km=500),
        co2_kg=20.0, score=0.4,
    )
    daten = als_kartendaten(_basis_plan(hinreise=_BAHN, rueckreise=rueck), lambda _pid: None)
    assert daten["hinreise"]["name"] == "Hinreise: Bahn"
    assert daten["rueckreise"]["name"] == "Rückreise: Auto"


def test_als_kartendaten_zeigt_standardbild_je_verkehrsmittel():
    # Iteration 2, Stage 30/32 (Rückmeldung des Product Owners): Hin-/Rückreise haben kein echtes Google-Foto (kein
    # einzelner "Ort"), bekommen stattdessen ein echtes Standardfoto je Verkehrsmittel (seit Stage 32
    # lizenzfreie Unsplash-Fotos statt der anfänglichen selbst gezeichneten SVG-Icons).
    rueck = BewerteteAlternative(
        alternative=ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=280, kosten_euro=90, distanz_km=500),
        co2_kg=20.0, score=0.4,
    )
    daten = als_kartendaten(_basis_plan(hinreise=_BAHN, rueckreise=rueck), lambda _pid: None)
    assert daten["hinreise"]["foto_url"] == "/static/img/bahn.jpg"
    assert daten["rueckreise"]["foto_url"] == "/static/img/auto.jpg"


def test_als_kartendaten_standardbild_fuer_fernbus_und_unbekanntes_verkehrsmittel():
    fernbus = BewerteteAlternative(
        alternative=ReiseAlternative(verkehrsmittel="Fernbus", dauer_minuten=400, kosten_euro=40, distanz_km=500),
        co2_kg=15.0, score=0.3,
    )
    unbekannt = BewerteteAlternative(
        alternative=ReiseAlternative(verkehrsmittel="Zeppelin", dauer_minuten=400, kosten_euro=40, distanz_km=500),
        co2_kg=15.0, score=0.3,
    )
    daten = als_kartendaten(_basis_plan(hinreise=fernbus, rueckreise=unbekannt), lambda _pid: None)
    assert daten["hinreise"]["foto_url"] == "/static/img/bus.jpg"
    assert daten["rueckreise"]["foto_url"] is None  # kein erzwungenes, irreführendes Bild


def test_als_kartendaten_ohne_verleih_liefert_none():
    daten = als_kartendaten(_basis_plan(), lambda _pid: None)
    assert daten["verleih"] is None


def test_als_kartendaten_zeigt_verleih_karte_mit_fahrzeugtyp():
    verleih_poi = POI(id=1, name="Rad-Verleih Zentrum", kategorie="fahrradverleih", x=0.0, y=0.0, score=0.0,
                       required_time=0, opening=0, closing=1440, place_id="verleih-1")
    daten = als_kartendaten(
        _basis_plan(lokaler_verleih_poi=verleih_poi, lokales_leihfahrzeug_gewuenscht="Fahrrad"),
        lambda pid: f"/fotos/{pid}.jpg" if pid else None,
    )
    assert daten["verleih"]["name"] == "Rad-Verleih Zentrum"
    assert daten["verleih"]["kategorie"] == "Verleih: Fahrrad"
    assert daten["verleih"]["foto_url"] == "/fotos/verleih-1.jpg"
    assert "query_place_id=verleih-1" in daten["verleih"]["maps_link"]
    assert daten["verleih"]["label"] is None  # kein "Vorschlag"-Badge, ist ein bestätigter Fund
    # Ohne bekannte Unterkunfts-Koordinaten kein geratener Startpunkt (Grundprinzip 1).
    assert daten["verleih"]["routen_link"] is None


def test_als_kartendaten_verleih_karte_zeigt_route_ab_unterkunft():
    # Rückmeldung des Product Owners: "Route ansehen"-Link wie bei den Tages-POI-Karten, hier IMMER von der
    # Unterkunft zum Verleih (siehe doku/34_stage34_verleih_routenlink/README.md).
    verleih_poi = POI(id=1, name="Rad-Verleih Zentrum", kategorie="fahrradverleih", x=48.14, y=11.58, score=0.0,
                       required_time=0, opening=0, closing=1440, place_id="verleih-1")
    daten = als_kartendaten(
        _basis_plan(lokaler_verleih_poi=verleih_poi, unterkunft_koordinaten=(48.13, 11.57)),
        lambda _pid: None,
    )
    link = daten["verleih"]["routen_link"]
    assert link is not None
    assert "origin=48.13%2C11.57" in link
    assert "destination=48.14%2C11.58" in link
    assert "travelmode=walking" in link


def test_als_kartendaten_zeigt_vorschlaege_an_leerem_tag():
    empfehlung = POI(id=9, name="Aussichtspunkt Nord", kategorie="natur", x=0.0, y=0.0, score=1.0,
                      required_time=60, opening=0, closing=600)
    plan = _basis_plan(
        tagesrouten=[Tagesroute(besuche=[])], weitere_aktivitaeten_empfehlungen=[empfehlung],
    )
    daten = als_kartendaten(plan, lambda _pid: None)
    vorschlaege = daten["tage"][0]["vorschlaege"]
    assert daten["tage"][0]["besuche"] == []
    assert vorschlaege[0]["name"] == "Aussichtspunkt Nord"
    assert vorschlaege[0]["label"] == "Vorschlag (nicht eingeplant)"


def test_als_kartendaten_zeigt_markt_und_restaurant_vorschlaege_am_vollen_mittleren_tag():
    markt_poi = POI(id=10, name="Wochenmarkt Zentral", kategorie="markt", x=0.0, y=0.0, score=1.0,
                     required_time=30, opening=0, closing=600, besuchsklasse="kaffee")
    restaurant_poi = POI(id=11, name="Kneipe Ecke", kategorie="bar", x=0.0, y=0.0, score=1.0,
                          required_time=60, opening=0, closing=600, besuchsklasse="bar")
    besuch = Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)
    plan = _basis_plan(
        tagesrouten=[Tagesroute(besuche=[]), Tagesroute(besuche=[besuch]), Tagesroute(besuche=[])],
        markt_beispiele=[markt_poi], beispielrestaurants=[restaurant_poi],
    )
    daten = als_kartendaten(plan, lambda _pid: None)
    tag2_vorschlaege = {v["name"]: v["label"] for v in daten["tage"][1]["vorschlaege"]}
    assert tag2_vorschlaege["Wochenmarkt Zentral"] == "Vorschlag: mittags Markt/Café"
    assert tag2_vorschlaege["Kneipe Ecke"] == "Vorschlag: abends essen gehen"
    # Anreise- und Abreisetag bekommen KEINEN Markt-Vorschlag (siehe _markt_beispiele_fuer_tag).
    assert "Wochenmarkt Zentral" not in {v["name"] for v in daten["tage"][0]["vorschlaege"]}
    assert "Wochenmarkt Zentral" not in {v["name"] for v in daten["tage"][2]["vorschlaege"]}


def test_als_kartendaten_zeigt_sondertag_beispiele_als_vorschlag():
    tour_poi = POI(id=12, name="Stadtführung Altstadt", kategorie="tour", x=0.0, y=0.0, score=1.0,
                    required_time=120, opening=0, closing=600, nutzerinteresse="Tour")
    plan = _basis_plan(
        tagesrouten=[Tagesroute(besuche=[]), Tagesroute(besuche=[])],
        tour_tag_beispiele=[tour_poi], tour_tage_anzahl=1,
    )
    daten = als_kartendaten(plan, lambda _pid: None)
    sondertag = daten["tage"][1]
    assert sondertag["besuche"] == []
    assert sondertag["vorschlaege"][0]["name"] == "Stadtführung Altstadt"
    assert "geführte Tour" in sondertag["vorschlaege"][0]["label"]


def test_als_kartendaten_zeigt_keine_restaurant_vorschlaege_am_sondertag():
    # Regression (Rückmeldung des Product Owners nach Live-Test): an einem reservierten Tour-Tag sollen KEINE
    # Beispielrestaurants/Markt-Vorschläge auftauchen ("da ist nur Tour").
    tour_poi = POI(id=13, name="Bootstour Hafen", kategorie="tour", x=0.0, y=0.0, score=1.0,
                   required_time=120, opening=0, closing=600, nutzerinteresse="Tour")
    restaurant_poi = POI(id=14, name="Restaurant Ecke", kategorie="restaurant", x=0.0, y=0.0, score=1.0,
                          required_time=60, opening=0, closing=600, besuchsklasse="mahlzeit")
    plan = _basis_plan(
        tagesrouten=[Tagesroute(besuche=[]), Tagesroute(besuche=[])],
        tour_tag_beispiele=[tour_poi], tour_tage_anzahl=1, beispielrestaurants=[restaurant_poi],
    )
    daten = als_kartendaten(plan, lambda _pid: None)
    namen = {v["name"] for v in daten["tage"][1]["vorschlaege"]}
    assert namen == {"Bootstour Hafen"}


def test_als_text_reserviert_mehrere_tour_tage_bei_explizitem_wunsch():
    tour_poi = POI(id=15, name="Wanderung Bergtour", kategorie="tour", x=0.0, y=0.0, score=1.0,
                    required_time=180, opening=0, closing=600, nutzerinteresse="Tour")
    plan = _basis_plan(
        tagesrouten=[Tagesroute(besuche=[]) for _ in range(3)],
        tour_tag_beispiele=[tour_poi], tour_tage_anzahl=2,
    )
    text = als_text(plan)
    tag2 = text.split("Tag 2")[1].split("Tag 3")[0]
    tag3 = text.split("Tag 3")[1]
    assert "Für diesen Tag empfehlen wir eine geführte Tour" in tag2
    assert "Für diesen Tag empfehlen wir eine geführte Tour" in tag3


def test_als_text_zeigt_keine_beispielrestaurants_an_reserviertem_tour_tag():
    tour_poi = POI(id=16, name="Altstadtführung", kategorie="tour", x=0.0, y=0.0, score=1.0,
                    required_time=120, opening=0, closing=600, nutzerinteresse="Tour")
    restaurant_poi = POI(id=17, name="Trattoria Ecke", kategorie="restaurant", x=0.0, y=0.0, score=1.0,
                          required_time=60, opening=0, closing=600, besuchsklasse="mahlzeit")
    plan = _basis_plan(
        tagesrouten=[Tagesroute(besuche=[])],
        tour_tag_beispiele=[tour_poi], tour_tage_anzahl=1, beispielrestaurants=[restaurant_poi],
    )
    text = als_text(plan)
    assert "Altstadtführung" in text
    assert "Trattoria Ecke" not in text
    assert "Beispielrestaurants" not in text


def test_speichere_poi_uebersicht_ohne_kandidaten_schreibt_nur_kopfzeile(tmp_path):
    pfad = tmp_path / "pois.csv"
    speichere_poi_uebersicht(_basis_plan(), pfad)
    with pfad.open(encoding="utf-8-sig", newline="") as datei:
        zeilen = list(csv.reader(datei, delimiter=";"))
    assert len(zeilen) == 1  # nur die Kopfzeile
    assert zeilen[0][0] == "tag"


# -- Eckdaten und Titelbild für den Titelbereich der Web-UI (Iteration 2, Gesamtdesign) ----------

_AUTO = BewerteteAlternative(
    alternative=ReiseAlternative(verkehrsmittel="Auto", dauer_minuten=280, kosten_euro=90, distanz_km=500),
    co2_kg=84.04, score=0.4,
)


def _poi_mit_place_id(place_id: str | None, poi_id: int = 1) -> POI:
    return POI(id=poi_id, name=f"POI {poi_id}", kategorie="museum", x=0.0, y=0.0, score=1.0,
               required_time=60, opening=0, closing=600, place_id=place_id)


def test_eckdaten_mit_allen_werten():
    tage = [Tagesroute(), Tagesroute(), Tagesroute()]
    plan = _basis_plan(
        tagesrouten=tage, zielort="Lissabon", reise_start_datum="2026-05-12", reise_end_datum="2026-05-14",
        reisezeitraum_rohtext="Mitte Mai", geschaetzte_kosten_euro=640.0,
    )
    eckdaten = als_kartendaten(plan, lambda _pid: None)["eckdaten"]
    assert eckdaten == {
        "zielort": "Lissabon",
        "zeitraum": "12.05.2026 – 14.05.2026",
        "tage": 3,
        "verkehrsmittel_hinreise": "Bahn",
        "verkehrsmittel_rueckreise": "Bahn",
        "co2_an_abreise_kg": 19.0,
        "kosten_pro_person": 640.0,
        "kosten_unvollstaendig": False,
    }


def test_eckdaten_ohne_werte_bleiben_none_statt_erfunden():
    eckdaten = als_kartendaten(_basis_plan(), lambda _pid: None)["eckdaten"]
    assert eckdaten["zielort"] is None
    assert eckdaten["zeitraum"] is None
    assert eckdaten["tage"] is None
    assert eckdaten["kosten_pro_person"] is None


def test_eckdaten_platzhalter_zielregion_gilt_nicht_als_zielort():
    # pipeline.py setzt "Zielregion" nur als Suchbegriff ein, wenn keine Zielregion vorliegt.
    eckdaten = als_kartendaten(_basis_plan(zielort="Zielregion"), lambda _pid: None)["eckdaten"]
    assert eckdaten["zielort"] is None


def test_eckdaten_zeitraum_faellt_ohne_eindeutige_daten_auf_rohtext_zurueck():
    nur_start = _basis_plan(reise_start_datum="2026-05-12", reisezeitraum_rohtext="ab 12. Mai eine Woche")
    assert als_kartendaten(nur_start, lambda _pid: None)["eckdaten"]["zeitraum"] == "ab 12. Mai eine Woche"
    unlesbar = _basis_plan(reise_start_datum="12.05.", reise_end_datum="2026-05-14", reisezeitraum_rohtext="Mai")
    assert als_kartendaten(unlesbar, lambda _pid: None)["eckdaten"]["zeitraum"] == "Mai"
    leerer_rohtext = _basis_plan(reisezeitraum_rohtext="   ")
    assert als_kartendaten(leerer_rohtext, lambda _pid: None)["eckdaten"]["zeitraum"] is None


def test_eckdaten_co2_summiert_nur_hin_und_rueckreise_und_trennt_verkehrsmittel():
    eckdaten = als_kartendaten(_basis_plan(hinreise=_BAHN, rueckreise=_AUTO), lambda _pid: None)["eckdaten"]
    assert eckdaten["co2_an_abreise_kg"] == 93.5  # 9.5 + 84.04, auf eine Nachkommastelle gerundet
    assert eckdaten["verkehrsmittel_hinreise"] == "Bahn"
    assert eckdaten["verkehrsmittel_rueckreise"] == "Auto"


def test_eckdaten_kennzeichnet_unvollstaendige_kosten():
    plan = _basis_plan(geschaetzte_kosten_euro=300.0, kosten_unvollstaendig=True)
    eckdaten = als_kartendaten(plan, lambda _pid: None)["eckdaten"]
    assert eckdaten["kosten_pro_person"] == 300.0
    assert eckdaten["kosten_unvollstaendig"] is True


def test_titelbild_bevorzugt_foto_der_unterkunft():
    tag = Tagesroute(besuche=[Besuch(poi=_poi_mit_place_id("poi-1"), ankunft=10, abfahrt=70)])
    plan = _basis_plan(tagesrouten=[tag], unterkunft_name="Hotel Zentral", unterkunft_place_id="hotel-1")
    daten = als_kartendaten(plan, lambda pid: f"/fotos/{pid}.jpg" if pid else None)
    assert daten["titelbild_url"] == "/fotos/hotel-1.jpg"


def test_titelbild_faellt_auf_erstes_poi_foto_zurueck():
    tag1 = Tagesroute(besuche=[Besuch(poi=_poi_mit_place_id(None, 1), ankunft=10, abfahrt=70)])
    tag2 = Tagesroute(besuche=[
        Besuch(poi=_poi_mit_place_id("ohne-foto", 2), ankunft=10, abfahrt=70),
        Besuch(poi=_poi_mit_place_id("poi-3", 3), ankunft=80, abfahrt=140),
    ])
    plan = _basis_plan(tagesrouten=[tag1, tag2], unterkunft_name="Hotel ohne Foto", unterkunft_place_id="hotel-1")
    fotos = {"poi-3": "/fotos/poi-3.jpg"}
    daten = als_kartendaten(plan, lambda pid: fotos.get(pid) if pid else None)
    assert daten["titelbild_url"] == "/fotos/poi-3.jpg"


def test_titelbild_ohne_fotos_ist_none():
    tag = Tagesroute(besuche=[Besuch(poi=_poi_mit_place_id("poi-1"), ankunft=10, abfahrt=70)])
    plan = _basis_plan(tagesrouten=[tag], unterkunft_name="Hotel Zentral", unterkunft_place_id="hotel-1")
    assert als_kartendaten(plan, lambda _pid: None)["titelbild_url"] is None


# -- Feste Termine (fest eingeplante Wunschorte) ---------------------------------------------------

from src.api.typen import GefundenerOrt  # noqa: E402
from src.ausgabe.reiseplan import FesterTermin  # noqa: E402
from src.fragekatalog.schema import FesterWunschort, WunschortAnfahrt  # noqa: E402

_ORT_MUSEUM = GefundenerOrt(name="Deutsches Museum", adresse="Museumsinsel 1, München", x=48.13, y=11.58, place_id="pid-museum")


def _termin(tag_nr=2, uhrzeit=None, anfahrt=None, dauer=120, ort=_ORT_MUSEUM) -> FesterTermin:
    if anfahrt is None:
        anfahrt = WunschortAnfahrt(verkehrsmittel="zu Fuß", dauer_minuten=20, quelle="distance_matrix", modus="walking")
    return FesterTermin(tag_nr=tag_nr, wunschort=FesterWunschort(
        rohname=ort.name, ort=ort, dauer_minuten=dauer, uhrzeit_minuten=uhrzeit, anfahrt=anfahrt,
    ))


def _termin_plan(*termine, **zusatz) -> Reiseplan:
    tag2 = Tagesroute(besuche=[Besuch(poi=_POI, ankunft=15, wartezeit=0, abfahrt=195)])
    return _basis_plan(
        tagesrouten=[Tagesroute(), tag2, Tagesroute()], unterkunft_koordinaten=(48.14, 11.57),
        feste_termine=list(termine), **zusatz,
    )


def test_als_text_zeigt_festen_termin_am_tagesende_ohne_erfundene_uhrzeit():
    text = als_text(_termin_plan(_termin(), tagesstart_minuten=540))
    tag2 = text.split("\nTag 2 ")[1].split("\nTag 3 ")[0]
    assert "Fester Termin (dein ausdrücklicher Wunsch, nicht Teil der optimierten Route): Deutsches Museum, Museumsinsel 1, München" in tag2
    assert "am Ende des Tages, nach der Rückkehr zur Unterkunft, Dauer ca. 2h" in tag2
    assert "Uhr" not in tag2.split("Fester Termin")[1].split("\n")[0]
    assert "Anfahrt ab Unterkunft: zu Fuß, ca. 20min je Richtung" in tag2
    assert "travelmode=walking" in tag2
    assert "query_place_id=pid-museum" in tag2
    # Reihenfolge: eingeplanter Ort, dann der feste Termin.
    assert tag2.index("Kletterroute XY") < tag2.index("Fester Termin")


def test_als_text_zeigt_festen_termin_mit_uhrzeit():
    text = als_text(_termin_plan(_termin(uhrzeit=900), tagesstart_minuten=540))
    assert "um 15:00 Uhr (deine Angabe, schließt den Tag ab)" in text


def test_als_text_uhrzeit_ohne_tagesstart_bleibt_am_tagesende_mit_ehrlichem_vermerk():
    text = als_text(_termin_plan(_termin(uhrzeit=900)))
    assert "am Ende des Tages" in text
    assert "deine genannte Uhrzeit 15:00 Uhr ließ sich an diesem Tag nicht mit der Tagesroute abstimmen" in text


def test_als_text_termin_anfahrt_mit_km_und_co2_nur_wenn_vorhanden():
    fern = WunschortAnfahrt(
        verkehrsmittel="Bahn", dauer_minuten=95, quelle="reisealternativen", distanz_km=120.4, co2_kg_hin_und_zurueck=4.6,
    )
    text = als_text(_termin_plan(_termin(anfahrt=fern)))
    assert "Anfahrt ab Unterkunft: Bahn, ca. 1h 35min je Richtung, ca. 120 km, ca. 4.6 kg CO2 hin und zurück (grobe Schätzung)" in text
    assert "travelmode=transit" in text


def test_als_text_termin_an_leerem_tag_ersetzt_kein_programm_und_keine_beispiele():
    plan = _termin_plan(_termin(tag_nr=3), weitere_aktivitaeten_empfehlungen=[_POI])
    tag3 = als_text(plan).split("\nTag 3 ")[1]
    assert "Außer dem festen Termin ist an diesem Tag kein weiteres Programm eingeplant." in tag3
    assert "(kein Programm eingeplant)" not in tag3
    assert "mögliche Beispiele" not in tag3


def test_als_text_und_html_zeigen_hinweise_zu_nicht_einplanbaren_orten():
    hinweis = "Der Wunschort „Schloss Fern“ konnte nicht fest eingeplant werden: keine Verbindung über Land."
    plan = _basis_plan(feste_termine_hinweise=[hinweis])
    assert hinweis in als_text(plan)
    assert "Der Wunschort „Schloss Fern“ konnte nicht fest eingeplant werden" in als_html(plan)


def test_als_html_zeigt_festen_termin_als_eigenen_block_mit_links():
    html_text = als_html(_termin_plan(_termin(uhrzeit=900), tagesstart_minuten=540))
    assert "<strong>Fester Termin</strong>" in html_text
    assert 'query_place_id=pid-museum">Deutsches Museum</a>' in html_text
    assert "um 15:00 Uhr" in html_text
    assert "Route in Google Maps ansehen" in html_text


def test_ohne_feste_termine_keine_termin_ausgabe():
    plan = _termin_plan()
    assert "Fester Termin" not in als_text(plan)
    assert "Fester Termin" not in als_html(plan)
    karten = als_kartendaten(plan, lambda _pid: None)
    assert all(tag["feste_termine"] == [] for tag in karten["tage"])
    assert karten["feste_termine_hinweise"] == []


def test_als_kartendaten_termin_karte_am_richtigen_tag():
    plan = _termin_plan(_termin(), _termin(tag_nr=2, uhrzeit=900), tagesstart_minuten=540)
    karten = als_kartendaten(plan, lambda pid: f"/fotos/{pid}.jpg" if pid else None)
    tag2 = karten["tage"][1]
    assert [t["zeitpunkt"][:6] for t in tag2["feste_termine"]] == ["um 15:", "am End"]  # Uhrzeit vor Tagesende
    karte = tag2["feste_termine"][1]
    assert karte["name"] == "Deutsches Museum" and karte["adresse"] == "Museumsinsel 1, München"
    assert karte["foto_url"] == "/fotos/pid-museum.jpg"
    assert karte["am_tagesende"] is True and karte["dauer"] == "2h"
    assert karte["anfahrt"].startswith("Anfahrt ab Unterkunft: zu Fuß")
    assert "travelmode=walking" in karte["routen_link"]
    assert "label" not in karte  # kein Vorschlag
    assert karten["tage"][0]["feste_termine"] == [] and karten["tage"][2]["feste_termine"] == []


def test_kosten_unvollstaendig_neutral_formuliert():
    text = als_text(_basis_plan(geschaetzte_kosten_euro=500.0, kosten_unvollstaendig=True))
    assert "nicht für alle Bestandteile lag eine Preisangabe vor" in text
    assert "für die Unterkunft lag kein Preisniveau vor" not in text
