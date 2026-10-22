"""
Fasst die Ergebnisse aus Optimierung 1, Optimierung 2 und dem
Monte-Carlo-Härtetest zu einer Rundreise nach UNWTO-Definition zusammen
(Hinreise -> Aufenthalt mit POIs -> Rückreise, siehe ARCHITEKTUR.md, Architektur-
Grundprinzip 4) und stellt die Ausgabe bereit (Text, HTML-Mail, Datei/JSON).
"""
from __future__ import annotations

import csv
import html
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from src.api.typen import POI, ReiseAlternative
from src.config import EINSTELLUNGEN
from src.fragekatalog.schema import FesterWunschort
from src.optimierung.monte_carlo import RobustheitsErgebnis
from src.optimierung.toptw import Besuch, Tagesroute
from src.optimierung.verkehrsmittelwahl import BewerteteAlternative

# Places API `place_id` -> klickbarer Google-Maps-Link. Funktioniert auch
# ohne Places-Details-Aufruf, siehe https://developers.google.com/maps/
# documentation/urls/get-started#search-place-id.
_MAPS_LINK_VORLAGE = "https://www.google.com/maps/search/?api=1&query=Google&query_place_id={place_id}"

# Echte, offizielle Quelle (verifiziert, Abstimmung mit dem Product Owner) – KEIN
# länderspezifischer Deep-Link, da sich Auswärtiges-Amt-URLs pro Land nicht
# zuverlässig aus dem Ländernamen ableiten lassen (Grundprinzip 1: keine
# geratenen URLs). Nutzer:innen navigieren von hier zu ihrem Reiseland.
SICHERHEITSHINWEISE_URL = "https://www.auswaertiges-amt.de/de/reiseundsicherheit/reise-und-sicherheitshinweise"


def maps_link(place_id: str | None) -> str | None:
    return _MAPS_LINK_VORLAGE.format(place_id=place_id) if place_id else None


# Rückmeldung des Product Owners nach echtem Browser-Test (siehe
# doku/30_stage30_zeit_fotos_verleih_layout_avatar/README.md, Punkt Standardbild Bahn/Auto): für
# Hin-/Rückreise gibt es keinen einzelnen "Ort" mit einem echten Google-Foto – statt die Karte ohne
# Bild zu lassen, zeigt sie ein Standardbild je Verkehrsmittel. Erkennung per Teilstring-Suche im
# gelieferten Verkehrsmittel-Text (z.B. "Bahn (ICE)"), NICHT über eine feste Liste exakter Werte –
# robuster gegenüber leicht variierenden Bezeichnungen aus google_maps.py/mock_data.py. Kein
# Treffer (z.B. unbekanntes/neues Verkehrsmittel) liefert bewusst `None` statt ein irreführendes
# Bild zu erzwingen.
#
# NACHTRAG (Rückmeldung des Product Owners mit konkreten Referenzfotos, siehe
# doku/32_stage32_echte_reisefotos_eingabe_ausblenden/README.md): die ursprünglichen, selbst
# gezeichneten SVG-Icons (Stage 30) wirkten zu abstrakt/comichaft – der Nutzer wollte echte,
# stimmungsvolle Reisefotos wie bei einer realen Foto-App. `static/img/bahn.jpg`/`auto.jpg`/
# `bus.jpg` sind echte Fotos von Unsplash, alle unter der Unsplash-Lizenz (kostenlos für
# kommerzielle/private Nutzung, keine Genehmigung nötig, Namensnennung nicht Pflicht aber üblich –
# siehe unsplash.com/license): bahn.jpg von Markus Winkler ("Silver and red bullet train",
# Stuttgart Hbf), auto.jpg von Averie Woodard ("The way to the cabin"), bus.jpg von "C"
# (@thecurlyone, Stirling/UK). Einzeln per Websuche gefunden UND VISUELL GEPRÜFT (mehrere erste
# automatische Treffer passten trotz treffend klingender Beschreibung nicht zum Motiv oder waren
# kostenpflichtige Unsplash+-Bilder) – nicht blind aus einer Text-Trefferliste übernommen.
_STANDARDBILD_JE_VERKEHRSMITTEL = (
    ("bahn", "/static/img/bahn.jpg"),
    ("zug", "/static/img/bahn.jpg"),
    ("fernbus", "/static/img/bus.jpg"),
    ("bus", "/static/img/bus.jpg"),
    ("auto", "/static/img/auto.jpg"),
    ("pkw", "/static/img/auto.jpg"),
)


def _standardbild_url(verkehrsmittel: str) -> str | None:
    verkehrsmittel_klein = verkehrsmittel.lower()
    for suchbegriff, bild_url in _STANDARDBILD_JE_VERKEHRSMITTEL:
        if suchbegriff in verkehrsmittel_klein:
            return bild_url
    return None


# Deutsche Anzeige-Labels für Googles Distance-Matrix-`mode`-Werte (siehe `Besuch.anfahrt_modus`,
# aufbereitung.py `ergaenze_anfahrt_modus_je_etappe`) – NUR für die Anzeige, keine eigene Logik.
_VERKEHRSMITTEL_LABEL_JE_MODUS = {
    "walking": "zu Fuß", "bicycling": "mit dem Fahrrad",
    "transit": "mit öffentlichen Verkehrsmitteln", "driving": "mit dem Auto",
}


def _verkehrsmittel_label(modus: str | None) -> str:
    """Leerstring statt einer erfundenen Angabe, wenn `modus` (noch) nicht gesetzt ist (Grundprinzip 1)."""
    return _VERKEHRSMITTEL_LABEL_JE_MODUS.get(modus, "") if modus else ""


def _hinreise_ziel_fuer_link(plan: "Reiseplan") -> tuple[float, float] | str | None:
    """
    Präziser Hin-/Rückreise-Endpunkt für `routen_link`: die genaue Unterkunft (Koordinaten), sobald
    bestätigt – NUR wenn sie (noch) fehlt, Rückfall auf den groben Zielort-Namen, statt gar keinen
    Link zu zeigen (siehe Rückmeldung des Product Owners: der bisherige Link zur Zielstadt allein war "nur halbwegs
    gut", eine echte Adresse zeigt die tatsächlich gebuchte Route in Google Maps).
    """
    return plan.unterkunft_koordinaten or plan.zielort


# "Bahn"/"Fernbus"/"Auto" (siehe ReiseAlternative.verkehrsmittel, google_maps.py `reisealternativen`)
# -> Googles Directions-URL-`travelmode` (siehe `routen_link` unten). "Bahn"/"Fernbus" werden beide
# über Googles `mode=transit` abgefragt (kein eigener Fernbus-Modus, siehe google_maps.py) – für den
# Link reicht "transit" bei beiden.
_TRAVELMODE_JE_VERKEHRSMITTEL = {"Bahn": "transit", "Fernbus": "transit", "Auto": "driving"}


def routen_link(ursprung: tuple[float, float] | str | None, ziel: tuple[float, float] | str | None, travelmode: str | None) -> str | None:
    """
    Google-Maps-Directions-Link (https://developers.google.com/maps/documentation/urls/get-started
    #directions-action) – öffnet die Route direkt mit Start-/Zielpunkt UND (falls bekannt) dem
    tatsächlich geplanten Verkehrsmittel vorausgewählt, statt wie `maps_link` nur einen einzelnen
    Ort zu zeigen. `ursprung`/`ziel` als Koordinaten-Tupel (POI-zu-POI-Etappen, exakt) ODER als
    Orts-/Adressname-String (An-/Abreise, wo keine Koordinaten vorliegen – Google löst Ortsnamen
    selbst auf). None, wenn `ursprung` oder `ziel` fehlt (z.B. Unterkunft-Koordinaten unbekannt) –
    kein Link mit geratenen Punkten (Grundprinzip 1).
    """
    if ursprung is None or ziel is None:
        return None

    def formatiere(punkt: tuple[float, float] | str) -> str:
        return f"{punkt[0]},{punkt[1]}" if isinstance(punkt, tuple) else punkt

    parameter = {"api": "1", "origin": formatiere(ursprung), "destination": formatiere(ziel)}
    if travelmode:
        parameter["travelmode"] = travelmode
    return f"https://www.google.com/maps/dir/?{urlencode(parameter)}"


def _format_dauer(minuten: int) -> str:
    """"Xh Ymin" statt roher Minutenzahl (Anforderung des Product Owners: erzählter statt tabellarischer
    Tagesplan) – bewusst KEINE Uhrzeit (z.B. "09:15"): ein reales Abfahrts-/Ankunftsdatum mit fester
    Uhrzeit liegt nirgends vor, eine erfundene Uhrzeit wäre ein Verstoß gegen Grundprinzip 1. Alle
    Zeitangaben bleiben deshalb relativ (Tag 1: seit Ankunft, weitere Tage: seit Tagesbeginn)."""
    stunden, rest_minuten = divmod(minuten, 60)
    if stunden == 0:
        return f"{rest_minuten}min"
    if rest_minuten == 0:
        return f"{stunden}h"
    return f"{stunden}h {rest_minuten}min"


def _format_uhrzeit(minuten_seit_mitternacht: int) -> str:
    """"HH:MM", auf einen 24h-Tag umgebrochen (ein Besuch nach Mitternacht bleibt dadurch lesbar)."""
    minuten_seit_mitternacht %= 24 * 60
    stunden, rest_minuten = divmod(minuten_seit_mitternacht, 60)
    return f"{stunden:02d}:{rest_minuten:02d}"


def _fahrzeit_vor_besuch(besuche: list[Besuch], index: int) -> int:
    """
    Reine Fahrzeit (Minuten) unmittelbar VOR `besuche[index]` – von der Unterkunft (erster Besuch
    des Tages) bzw. vom vorherigen Besuch. Keine Schätzung nötig: `toptw.py::simuliere_route` setzt
    `ankunft = uhrzeit_vorher + fahrzeit` (Tagesbeginn `uhrzeit=0`), die Fahrzeit steckt also bereits
    exakt in der Differenz zwischen dieser Ankunft und der vorherigen Abfahrt (bzw. für den ersten
    Besuch direkt in `ankunft` selbst, da `uhrzeit_vorher` zu Tagesbeginn 0 ist).
    """
    if index == 0:
        return besuche[0].ankunft
    return besuche[index].ankunft - besuche[index - 1].abfahrt


def _teilstrecken_zeilen(alternative: ReiseAlternative, praefix: str = "  ") -> list[str]:
    """
    Zeilen für die einzelnen Umstiege/Linien einer Bahn-/Fernbus-Alternative
    (siehe `Teilstrecke` in typen.py) – ersetzt die reine Gesamtdauer durch
    die echte Fahrt-Kette (Anforderung des Product Owners: Teilstrecken mit Umstiegen
    und Wartezeiten statt nur einer Gesamtdauer). Leer, wenn Google keine Schritt-Details geliefert hat (z.B.
    Auto, oder Mock-Modus) – dann bleibt es bei der Gesamtdauer.
    """
    zeilen = []
    for teilstrecke in alternative.teilstrecken:
        if teilstrecke.wartezeit_minuten is not None:
            wartezeit_text = (
                "sofortiger Anschluss" if teilstrecke.wartezeit_minuten == 0 else f"{teilstrecke.wartezeit_minuten} min Wartezeit"
            )
            zeilen.append(f"{praefix}Umstieg in {teilstrecke.von} ({wartezeit_text})")
        if teilstrecke.modus == "TRANSIT":
            linie_text = f"{teilstrecke.linie}: " if teilstrecke.linie else ""
            zeilen.append(f"{praefix}{linie_text}{teilstrecke.von} → {teilstrecke.nach} ({teilstrecke.dauer_minuten} min)")
        else:
            zeilen.append(f"{praefix}Fußweg ({teilstrecke.dauer_minuten} min)")
    return zeilen


def _zeitpunkt_text(plan: "Reiseplan", tag_nr: int, minuten_seit_tagesbeginn: int, praefix: str) -> str:
    """Baut eine Zeitangabe, entweder als ECHTE Uhrzeit oder als eindeutig verankerte relative
    Angabe – NIE eine unverankerte, nackte Dauer wie "1h" (siehe Verlaufskommentar unten, das war
    zweimal live missverständlich).

    - Ab Tag 2, wenn der Nutzer F20 (tagesstart_praeferenz) tatsächlich beantwortet hat (siehe
      `Reiseplan.tagesstart_minuten`): echte, vom Nutzer stammende Uhrzeit ("14:00 Uhr").
    - Tag 1 (IMMER) und jeder Tag ohne F20-Antwort: es gibt keine echte Uhrzeit (kein reales Ticket
      für die Hinreise, keine genannte Präferenz) – eine erfundene Uhrzeit wäre ein Verstoß gegen
      Grundprinzip 1. VERLAUF: bis Iteration 1 stand hier eine nackte relative Dauer ("ab 1h – bis
      2h") – Betreuer-Feedback aus der Iteration-1-Demo: liest sich wie eine AUFENTHALTSDAUER von
      1 bis 2 Stunden, gemeint war aber ein Zeit*punkt*. Kurzzeitig (Iteration 2, Phase 56) stattdessen
      eine "ca."-markierte ANGENOMMENE Uhrzeit (fiktiver Standard-Tagesbeginn) – nach echtem
      Browser-Test wieder verworfen (Phase 57/58, Entscheidung des Product Owners: keine Uhrzeit, sondern eine
      relative Angabe wie "nach Ankunft"). JETZT: eine relative Dauer, aber mit einem
      Ankerwort DIREKT AN JEDEM Zeitwert ("nach Ankunft"/"nach Tagesbeginn") statt einer isolierten
      Zahl – dadurch bleibt sie ohne erfundene Uhrzeit UND ohne die alte Verwechslungsgefahr mit
      einer Aufenthaltsdauer, weil jeder Wert klar als "so lange nach [Referenzpunkt]" erkennbar ist.
    """
    if tag_nr == 1 or plan.tagesstart_minuten is None:
        anker = "Ankunft" if tag_nr == 1 else "Tagesbeginn"
        dauer = _format_dauer(minuten_seit_tagesbeginn)
        if praefix == "bis":
            return f"bis {dauer} nach {anker}"
        return f"{dauer} nach {anker}"
    return f"{praefix} {_format_uhrzeit(plan.tagesstart_minuten + minuten_seit_tagesbeginn)} Uhr"


def _verleih_hinweis_text(plan: "Reiseplan") -> str | None:
    """Formuliert `lokales_leihfahrzeug_gewuenscht`/`lokaler_verleih_poi` (siehe Reiseplan-Doku) als
    fertigen Satz: echter Fund mit Link, oder ehrliche Fehlanzeige – nie ein erfundener Verleih."""
    fahrzeug = plan.lokales_leihfahrzeug_gewuenscht
    if fahrzeug is None:
        return None
    if plan.lokaler_verleih_poi is None:
        return (
            f"Du möchtest dich vor Ort mit einem geliehenen {fahrzeug} fortbewegen – in der Nähe "
            "konnten wir aber keinen Verleih finden. Bitte recherchiere selbst vor Ort."
        )
    poi = plan.lokaler_verleih_poi
    zusatz = " (laut Google als Fahrradgeschäft gelistet, keine Verleih-Garantie)" if fahrzeug == "Fahrrad" else ""
    satz = f"Für deine gewünschte lokale Fortbewegung mit geliehenem {fahrzeug} haben wir in der Nähe gefunden: {poi.name}{zusatz}"
    link = maps_link(poi.place_id)
    if link:
        satz += f" — {link}"
    return satz + " (bitte Verfügbarkeit/Konditionen vor Ort prüfen)."


@dataclass
class FesterTermin:
    """
    Ein fest eingeplanter Wunschort (siehe schema.py `FesterWunschort`, pipeline.py
    `_plane_feste_termine`): läuft NICHT durch Optimierung 1, sondern ist direkt einem Tag
    zugeordnet. Optimierung 1 plant an diesem Tag nur die um den Termin gekürzte Restzeit.

    Zeitpunkt: mit vom Nutzer genannter Uhrzeit schließt der Termin den Tag zu dieser Uhrzeit ab;
    ohne Uhrzeit liegt er am Ende des Tages nach der optimierten Route (Rückkehr zur Unterkunft,
    dann Anfahrt zum Termin). Eine Uhrzeit wird dafür nicht erfunden.
    """

    tag_nr: int  # 1-basiert wie in der Ausgabe
    wunschort: FesterWunschort

    @property
    def am_tagesende(self) -> bool:
        """True, wenn keine Uhrzeit genannt wurde und der Termin daher am Tagesende liegt."""
        return self.wunschort.uhrzeit_minuten is None


@dataclass
class Reiseplan:
    hinreise: BewerteteAlternative
    tagesrouten: list[Tagesroute]
    rueckreise: BewerteteAlternative
    # Monte-Carlo-Härtetest AUSSCHLIESSLICH für die An-/Abreise (siehe monte_carlo.py
    # `haertetest_teilstrecken`, ENTSCHEIDUNGSLOG.md) – None, wenn keine Teilstrecken-Daten
    # vorlagen (Auto, oder Mock-Modus ohne Schritt-Details). Der frühere POI-vor-Ort-Härtetest
    # wurde abgeschafft (siehe dort für die Begründung).
    hinreise_robustheit: RobustheitsErgebnis | None = None
    rueckreise_robustheit: RobustheitsErgebnis | None = None
    # Die im Dialog (F15) gesuchte und vom Nutzer bestätigte Unterkunft (siehe schema.py
    # `ReiseAnfrage.unterkunft_name`) – None, wenn keine Unterkunft gefunden wurde.
    unterkunft_name: str | None = None
    # place_id derselben Unterkunft, für einen klickbaren Google-Maps-Link in der
    # Mail-/Textausgabe (siehe maps_link unten). None im Mock-Modus.
    unterkunft_place_id: str | None = None
    # Places-Foto-Referenz derselben Unterkunft (siehe schema.py `unterkunft_foto_referenz`) – für
    # die Bild-Karte im fertigen Reiseplan der Web-UI (webapp.py/src/ausgabe/fotos.py). None im
    # Mock-Modus oder wenn Places kein Foto zu dieser Unterkunft hat.
    unterkunft_foto_referenz: str | None = None
    # Grobe, informative Gesamtkostenschätzung PRO PERSON (Aktivitäten+Unterkunft+Fahrt+
    # Verpflegungspauschale, siehe src/optimierung/kostenschaetzung.py) – None nur, wenn keine
    # Hinreise berechnet werden konnte (praktisch nie, plane_reise bricht in dem Fall vorher ab).
    # Rein informativ, beeinflusst NICHT die Auswahl in Optimierung 1.
    geschaetzte_kosten_euro: float | None = None
    # True, wenn die Unterkunft kein Places-Preisniveau hatte und daher nicht in
    # `geschaetzte_kosten_euro` eingerechnet werden konnte (siehe kostenschaetzung.py) – macht die
    # Schätzung erkennbar unvollständig statt fälschlich vollständig wirkend.
    kosten_unvollstaendig: bool = False
    # Direkt aus `ReiseAnfrage.budget_gesamt` übernommen, NUR für den Vergleichstext in
    # als_text/als_html – Reiseplan bleibt sonst frei von ReiseAnfrage-Abhängigkeiten.
    budget_gesamt: float | None = None
    # Koordinaten derselben Unterkunft (siehe `ReiseAnfrage.unterkunft_koordinaten`) – NUR für die
    # Google-Maps-ROUTEN-Links der ersten Etappe jedes Tages (siehe `routen_link`/`als_text`), die
    # tatsächliche Optimierung nutzt weiterhin `anfrage.unterkunft_koordinaten` direkt (pipeline.py).
    # None, wenn keine Unterkunft bestätigt wurde – dann bleibt der Routen-Link für diese eine
    # Etappe schlicht weg, statt einen geratenen Startpunkt zu erfinden (Grundprinzip 1).
    unterkunft_koordinaten: tuple[float, float] | None = None
    # Wohnort (F08) und geplanter Zielort, NUR für den Hin-/Rückreise-Routen-Link (siehe `als_text`)
    # – Reiseplan speichert sonst bewusst keine rohen Ortsnamen, hier aber nötig, weil für die
    # An-/Abreise (anders als POI-zu-POI) keine Koordinaten vorliegen.
    wohnort: str | None = None
    zielort: str | None = None
    # Nur gesetzt, wenn das LLM aus dem Gesprächskontext eine echte Sicherheitssorge erkannt hat
    # (siehe schema.py `sicherheit_bedenklich`) – Verweis auf eine ECHTE, offizielle Quelle statt
    # einer selbst erfundenen Sicherheitseinschätzung (Grundprinzip 1).
    sicherheitshinweis: str | None = None
    # POIs, die als Kandidaten gefunden, aber NICHT in die von Optimierung 1
    # gewählte Tagesroute übernommen wurden (Zeitfenster/Budget hat nicht für
    # alle gereicht, siehe pipeline.py) – werden NICHT verworfen, sondern als
    # frei kombinierbare Zusatz-Empfehlungen mitgegeben (Entscheidung des
    # Product Owners: eine grobe Struktur, über die der Nutzer selbst entscheidet,
    # statt einer vollkommen fertig geplanten Reise).
    weitere_aktivitaeten_empfehlungen: list[POI] = field(default_factory=list)
    # Hinweise zu Kandidaten, die einer genannten harten Einschränkung
    # (Ernährung F18, Barrierefreiheit F09/F10/F15) widersprechen könnten,
    # aber NICHT ausgefiltert werden konnten, weil keine unbedenkliche
    # Alternative gefunden wurde (siehe src/datenaufbereitung/
    # vertraeglichkeit.py – kein Verschweigen des Konflikts, aber auch kein
    # Erfinden einer nicht existierenden Alternative, Grundprinzip 1).
    einschraenkungshinweise: list[str] = field(default_factory=list)
    # "Fahrrad"/"Auto", NUR gesetzt, wenn F14 (lokaler_transport_praeferenz) erkennbar einen Wunsch
    # nach einem vor Ort GELIEHENEN Fahrzeug ausdrückt (siehe aufbereitung.py `erkenne_leihwunsch`,
    # z.B. Anreise mit Bahn, vor Ort aber Fahrrad gewünscht -> im Dialog nachgefragt, ob eigenes
    # Fahrzeug dabei ist oder ein Verleih gesucht werden soll). None = kein solcher Wunsch erkannt.
    lokales_leihfahrzeug_gewuenscht: str | None = None
    # Der real gefundene Verleih-Kandidat (siehe pipeline.py), falls einer existiert – None sowohl
    # wenn kein Leihwunsch vorliegt ALS AUCH wenn einer vorliegt, aber nichts gefunden wurde (siehe
    # `lokales_leihfahrzeug_gewuenscht`, um die beiden Fälle zu unterscheiden). Nie erfunden
    # (Grundprinzip 1) – für Fahrräder liefert Google nur "bicycle_store" (Laden, keine Verleih-
    # Garantie, siehe google_maps.py), daher der Formulierungs-Hinweis in der Ausgabe.
    lokaler_verleih_poi: POI | None = None
    # Echte Restaurants (besuchsklasse "mahlzeit") in der Nähe der Unterkunft, sortiert nach
    # Entfernung – NICHT in Optimierung 1 eingeplant (siehe pipeline.py: essensbezogene Interessen
    # werden dort bewusst aus der ILS-Kandidatenliste rausgehalten, damit ein Essenswunsch (z.B. "abends
    # essen gehen") nicht mit den Sehenswürdigkeiten um Zeitfenster/Score konkurriert und dabei ggf.
    # verliert). Werden stattdessen separat als Beispiele je Tag angezeigt (siehe als_text/als_html)
    # – rein informativ, keine feste Uhrzeit/Reservierung. Leer, wenn kein essensbezogenes Interesse
    # geäußert wurde.
    beispielrestaurants: list[POI] = field(default_factory=list)
    # Echte geführte Touren (POI.nutzerinteresse passt auf "Tour"/"Führung"/..., siehe pipeline.py
    # `_trenne_sonderkategorie_ab`) – laufen NIE durch Optimierung 1 (keine Score-Auswahl), sondern
    # bekommen bei Fund einen KOMPLETT aus der Optimierung herausgenommenen eigenen Tag (siehe
    # `_reservierte_sondertage` unten für die Zuordnung, WELCHER Tag das ist – bei gleichzeitig
    # gefundenen Lernaktivitäten zwei GETRENNTE Tage). Leer, wenn kein Tour-Interesse geäußert oder
    # keine echten Treffer gefunden wurden.
    tour_tag_beispiele: list[POI] = field(default_factory=list)
    # Anzahl der für die Tour reservierten Tage (siehe pipeline.py `plane_reise` – NUR bei explizit
    # geäußertem Mehrtages-Wunsch, `anfrage.tour_tage_anzahl`, mehr als 1; Entscheidung des Product Owners: ohne
    # ausdrückliche Aussage bleibt es bei einer Eintagestour). 0, wenn `tour_tag_beispiele` leer ist.
    # `_reservierte_sondertage` unten braucht die tatsächliche Anzahl, nicht nur ob überhaupt Treffer
    # vorliegen, um MEHRERE aufeinanderfolgende Tage derselben Kategorie zuzuordnen.
    tour_tage_anzahl: int = 0
    # Wie `tour_tag_beispiele`, nur für konkrete, ortsgebundene Lernaktivitäten (Kochkurs, Sprachkurs
    # etc., siehe katalog.py F17/F16) – bewusst GENAUSO behandelt wie geführte Touren (Entscheidung
    # des Product Owners: ein ausdrücklicher Lernwunsch darf NIE vom Optimierungsalgorithmus
    # aussortiert werden können). Leer, wenn kein konkretes Lernaktivitäts-Interesse geäußert oder
    # keine echten Treffer gefunden wurden.
    lernaktivitaet_tag_beispiele: list[POI] = field(default_factory=list)
    # Markt-/Café-Beispiele für einen Mittags-Zeitblock bei gewünschtem lokalem Kontakt (F19, siehe
    # pipeline.py `_trenne_markt_beispiele_ab`) – NUR bei `anfrage.lokaler_kontakt_wichtig` befüllt,
    # NICHT in Optimierung 1 eingeplant (der Algorithmus bekommt dafür 120 Min. weniger Tagesbudget
    # an "vollen" Tagen, siehe pipeline.py). Rein informativ, wie `beispielrestaurants` – keine feste
    # Uhrzeit, keine Bindung an einen bestimmten Tag. Leer, wenn kein lokaler Kontakt gewünscht oder
    # keine echten Treffer gefunden wurden.
    markt_beispiele: list[POI] = field(default_factory=list)
    # Startuhrzeit (Minuten seit Mitternacht) NUR gesetzt, wenn F20 (tagesstart_praeferenz) vom LLM
    # tatsächlich in `ReiseAnfrage.tagesstart_minuten` interpretiert wurde (siehe pipeline.py).
    # Ermöglicht ECHTE Uhrzeiten ab Tag 2 in der Ausgabe (siehe `_zeitpunkt_text`). Tag 1 bleibt
    # IMMER ohne echte Uhrzeit (kein reales Fahrplan-Ticket für die Hinreise vorhanden), ebenso jeder
    # Tag ohne diese Präferenz – dort verwendet `_zeitpunkt_text` eine relative Dauer MIT Ankerwort
    # ("1h nach Ankunft"/"nach Tagesbeginn") statt einer echten oder angenommenen Uhrzeit (Befund
    # aus einem Browser-Test, Phase 57/58 – siehe
    # doku/30_stage30_zeit_fotos_verleih_layout_avatar/README.md für die volle Herleitung inkl. der
    # zwischenzeitlich verworfenen "ca."-Uhrzeit-Variante aus Iteration 2/Phase 56).
    tagesstart_minuten: int | None = None
    # Reisezeitraum aus F06 (siehe schema.py `reisezeitraum_rohtext`/`reise_start_datum`/
    # `reise_end_datum`), NUR für die Eckdaten-Anzeige im Titelbereich der Web-UI (siehe
    # `_eckdaten`). Nach demselben Muster wie `budget_gesamt` additiv aus der ReiseAnfrage
    # durchgereicht; die Tagesberechnung selbst läuft weiterhin in aufbereitung.py. None, wenn der
    # jeweilige Wert im Gespräch nicht ermittelt wurde.
    reisezeitraum_rohtext: str | None = None
    reise_start_datum: str | None = None
    reise_end_datum: str | None = None
    # Fest eingeplante Wunschorte (siehe `FesterTermin`, pipeline.py `_plane_feste_termine`). Leer,
    # wenn der Nutzer keinen Ort ausdrücklich "unbedingt" sehen wollte.
    feste_termine: list[FesterTermin] = field(default_factory=list)
    # Ehrliche Hinweise zu festen Wunschorten, die NICHT eingeplant werden konnten (keine
    # Landverbindung, keine bestätigte Unterkunft, kein passender Tag) – nicht still verworfen.
    feste_termine_hinweise: list[str] = field(default_factory=list)


# Platzhalter, den pipeline.py als Suchbegriff einsetzt, wenn keine Zielregion vorliegt. Er ist kein
# echter Ortsname und darf deshalb nicht als Reiseziel im Titel erscheinen (siehe `_eckdaten`).
ZIELORT_PLATZHALTER = "Zielregion"


def _iso_als_deutsches_datum(iso_datum: str | None) -> str | None:
    """"2026-05-12" -> "12.05.2026"; None bei fehlendem oder nicht lesbarem Wert (dann greift in
    `_zeitraum_text` der Rohtext als Rückfall, statt ein Datum zu raten)."""
    if not iso_datum:
        return None
    try:
        return date.fromisoformat(iso_datum).strftime("%d.%m.%Y")
    except ValueError:
        return None


def _zeitraum_text(plan: Reiseplan) -> str | None:
    """Anzeigetext des Reisezeitraums: bevorzugt das vom LLM normalisierte Start- und Enddatum,
    sonst die wörtliche Antwort auf F06, sonst None (kein erfundener Zeitraum, Grundprinzip 1)."""
    start = _iso_als_deutsches_datum(plan.reise_start_datum)
    ende = _iso_als_deutsches_datum(plan.reise_end_datum)
    if start and ende:
        return f"{start} – {ende}"
    rohtext = (plan.reisezeitraum_rohtext or "").strip()
    return rohtext or None


def _eckdaten(plan: Reiseplan) -> dict[str, Any]:
    """
    Eckdaten der Reise für den Titelbereich der Web-UI (Iteration 2, Gesamtdesign der Oberfläche):
    wenige Kernfakten gebündelt am Anfang des Reiseplans, jeweils ausschließlich aus bereits
    berechneten Werten des Reiseplans. Fehlt ein Wert, bleibt er None; die Web-UI blendet den
    zugehörigen Chip dann aus, statt einen Wert zu schätzen.

    `co2_an_abreise_kg` umfasst bewusst nur Hin- und Rückreise (Optimierung 2). Für die Wege vor
    Ort liegt keine CO₂-Berechnung vor, die Bezeichnung in der Web-UI benennt diese Einschränkung.
    """
    zielort = plan.zielort if plan.zielort and plan.zielort != ZIELORT_PLATZHALTER else None
    return {
        "zielort": zielort,
        "zeitraum": _zeitraum_text(plan),
        "tage": len(plan.tagesrouten) or None,
        "verkehrsmittel_hinreise": plan.hinreise.alternative.verkehrsmittel,
        "verkehrsmittel_rueckreise": plan.rueckreise.alternative.verkehrsmittel,
        "co2_an_abreise_kg": round(plan.hinreise.co2_kg + plan.rueckreise.co2_kg, 1),
        "kosten_pro_person": plan.geschaetzte_kosten_euro,
        "kosten_unvollstaendig": plan.kosten_unvollstaendig,
    }


def _titelbild_url(plan: Reiseplan, foto_url_fuer_place_id: Callable[[str | None], str | None]) -> str | None:
    """
    Titelbild des Reiseplans aus bereits heruntergeladenen Fotos (keine zusätzliche Foto-Anfrage):
    zuerst das Foto der bestätigten Unterkunft, sonst das erste vorhandene Foto eines eingeplanten
    POI in Reihenfolge der Tage. None, wenn keines vorliegt; die Web-UI zeigt dann einen
    Farbverlauf statt eines fremden Symbolbilds, das fälschlich wie der Zielort wirken könnte.
    """
    if plan.unterkunft_name:
        unterkunft_foto = foto_url_fuer_place_id(plan.unterkunft_place_id)
        if unterkunft_foto:
            return unterkunft_foto
    for tagesroute in plan.tagesrouten:
        for besuch in tagesroute.besuche:
            poi_foto = foto_url_fuer_place_id(besuch.poi.place_id)
            if poi_foto:
                return poi_foto
    return None


_EINLEITUNG = (
    "Das Folgende ist eine grobe Struktur auf Basis deiner Angaben – kein fertig gebuchter Plan. Unterkunft "
    "und Aktivitäten sind Empfehlungen, die zu deinen Präferenzen passen; die Tagesrouten zeigen EIN Beispiel, "
    "wie sich deine gewünschten Aktivitäten zeitlich realistisch kombinieren lassen. Schau dir in Ruhe "
    "an, was dir gefällt, und stell dir deine Reise daraus selbst zusammen."
)


def _uhrzeit_hinweis_text(plan: "Reiseplan") -> str:
    """Einmaliger Hinweis, wie die Zeitangaben zu lesen sind: Tag 1 IMMER relativ zur Ankunft (keine
    reale Ankunftsuhrzeit der Hinreise bekannt), weitere Tage NUR dann mit echter Uhrzeit, wenn der
    Nutzer F20 tatsächlich beantwortet hat – sonst ebenfalls relativ, zum Tagesbeginn."""
    if plan.tagesstart_minuten is None:
        return (
            "Zeitangaben ohne feste Uhrzeit (z.B. \"1h nach Ankunft\"/\"nach Tagesbeginn\") sind "
            "relativ zum jeweiligen Bezugspunkt zu lesen, nicht als Aufenthaltsdauer – du hast "
            "keine eigene Tagesablauf-Präferenz genannt, daher keine erfundene Uhrzeit."
        )
    return (
        f"Die Uhrzeiten ab Tag 2 basieren auf deiner angegebenen Tagesstart-Präferenz (ca. "
        f"{_format_uhrzeit(plan.tagesstart_minuten)} Uhr). Tag 1 bleibt relativ zur Ankunft (z.B. "
        "\"1h nach Ankunft\"), da die tatsächliche Ankunftszeit der Hinreise nirgends real feststeht."
    )


def _kosten_text(plan: "Reiseplan") -> str | None:
    """Formuliert `geschaetzte_kosten_euro`/`budget_gesamt` (siehe kostenschaetzung.py) als Satz –
    None nur, wenn keine Schätzung berechnet wurde (praktisch nie, siehe Reiseplan-Doku)."""
    if plan.geschaetzte_kosten_euro is None:
        return None
    text = (
        "Geschätzte Gesamtkosten pro Person (grobe Schätzung auf Basis von Googles Preisniveau-"
        f"Einstufung, keine echten Einzelpreise): ca. {plan.geschaetzte_kosten_euro:.0f} € "
        "(Unterkunft, Aktivitäten, An-/Abreise, Verpflegungspauschale)"
        # Neutral formuliert: das Kennzeichen entsteht bei fehlendem Preisniveau der Unterkunft und
        # grundsätzlich auch bei einem festen Termin ohne Anfahrt (siehe kostenschaetzung.py).
        + (", unvollständig – nicht für alle Bestandteile lag eine Preisangabe vor" if plan.kosten_unvollstaendig else "")
        + "."
    )
    if plan.budget_gesamt is not None:
        differenz = plan.budget_gesamt - plan.geschaetzte_kosten_euro
        if differenz >= 0:
            text += f" Das liegt im Rahmen deines angegebenen Budgets von {plan.budget_gesamt:.0f} € (ca. {differenz:.0f} € Puffer)."
        else:
            text += f" Das übersteigt dein angegebenes Budget von {plan.budget_gesamt:.0f} € um ca. {abs(differenz):.0f} €."
    return text


# -- Feste Termine (fest eingeplante Wunschorte, siehe `FesterTermin`) --------------------------
# Gemeinsame Formulierungen für Text, HTML-Mail und Web-UI-Karten, damit alle drei Ausgaben dieselben
# Angaben zeigen.


def _termin_uhrzeit_gilt(plan: "Reiseplan", termin: FesterTermin) -> bool:
    """True, wenn die vom Nutzer genannte Uhrzeit das Tagesbudget tatsächlich bestimmt hat. Das ist
    nach pipeline.py `_budget_nach_termin` nur ab Tag 2 und mit bekanntem Tagesstart (F20) der Fall;
    nur dann wird der Termin als fester Zeitpunkt gezeigt."""
    return termin.wunschort.uhrzeit_minuten is not None and plan.tagesstart_minuten is not None and termin.tag_nr != 1


def _termin_zeitpunkt_text(plan: "Reiseplan", termin: FesterTermin) -> str:
    """Zeitpunkt des Termins: die genannte Uhrzeit, sonst "am Ende des Tages". Eine Uhrzeit wird
    nie erfunden (Grundprinzip 1)."""
    uhrzeit = termin.wunschort.uhrzeit_minuten
    if _termin_uhrzeit_gilt(plan, termin):
        return f"um {_format_uhrzeit(uhrzeit)} Uhr (deine Angabe, schließt den Tag ab)"
    text = "am Ende des Tages, nach der Rückkehr zur Unterkunft"
    if uhrzeit is not None:
        text += (
            f" (deine genannte Uhrzeit {_format_uhrzeit(uhrzeit)} Uhr ließ sich an diesem Tag nicht mit der "
            "Tagesroute abstimmen)"
        )
    return text


def _termin_anfahrt_text(termin: FesterTermin) -> str:
    """Anfahrt ab der Unterkunft; Kilometer und CO₂ nur, wenn die API-Antwort sie hergibt (siehe
    schema.py `WunschortAnfahrt`). CO₂ ausdrücklich als grobe Schätzung."""
    anfahrt = termin.wunschort.anfahrt
    if anfahrt is None:
        return ""
    teile = [f"{anfahrt.verkehrsmittel}, ca. {_format_dauer(anfahrt.dauer_minuten)} je Richtung"]
    if anfahrt.distanz_km is not None:
        teile.append(f"ca. {anfahrt.distanz_km:.0f} km")
    if anfahrt.co2_kg_hin_und_zurueck is not None:
        teile.append(f"ca. {anfahrt.co2_kg_hin_und_zurueck:.1f} kg CO2 hin und zurück (grobe Schätzung)")
    return "Anfahrt ab Unterkunft: " + ", ".join(teile)


def _termin_routen_link(plan: "Reiseplan", termin: FesterTermin) -> str | None:
    """Route von der Unterkunft zum Termin mit dem Verkehrsmittel der ermittelten Anfahrt: der
    Distance-Matrix-Modus ist bereits ein gültiger Google-Maps-`travelmode`, Bahn/Fernbus/Auto
    werden wie bei der An-/Abreise übersetzt."""
    anfahrt = termin.wunschort.anfahrt
    travelmode = None
    if anfahrt is not None:
        travelmode = anfahrt.modus or _TRAVELMODE_JE_VERKEHRSMITTEL.get(anfahrt.verkehrsmittel)
    ort = termin.wunschort.ort
    return routen_link(plan.unterkunft_koordinaten, (ort.x, ort.y), travelmode)


def _feste_termine_fuer_tag(plan: "Reiseplan", tag_nr: int) -> list[FesterTermin]:
    """Termine eines Tages in Anzeige-Reihenfolge. Jeder Termin liegt am Ende des Tages (mit
    Uhrzeit schließt er den Tag ab, ohne Uhrzeit folgt er auf die optimierte Route); Termine mit
    geltender Uhrzeit stehen nach ihrer Uhrzeit sortiert vor den Tagesende-Terminen."""
    termine = [termin for termin in plan.feste_termine if termin.tag_nr == tag_nr]
    return sorted(
        termine,
        key=lambda termin: (not _termin_uhrzeit_gilt(plan, termin), termin.wunschort.uhrzeit_minuten or 0),
    )


def _termin_tage(plan: "Reiseplan") -> frozenset[int]:
    """Tage mit festem Termin: sie gelten nicht als "leer" und bekommen deshalb keine generischen
    Beispiel-Vorschläge (siehe `_verteile_beispiele_auf_leere_tage`)."""
    return frozenset(termin.tag_nr for termin in plan.feste_termine)


def _reservierte_sondertage(plan: "Reiseplan") -> dict[int, tuple[str, list[POI]]]:
    """
    Ordnet reservierte Sonder-Tage (geführte Tour, Lernaktivität – siehe pipeline.py
    `_trenne_sonderkategorie_ab`) den LETZTEN Tagen der Reise zu: der Lernaktivitäts-Tag (falls
    vorhanden) ist IMMER der allerletzte Tag der Reise, die Tour-Tage (falls vorhanden) liegen
    direkt davor – bei explizit gewünschten MEHREREN Tour-Tagen (`plan.tour_tage_anzahl` > 1, siehe
    Entscheidung des Product Owners) entsprechend mehrere aufeinanderfolgende Tage, alle mit DERSELBEN
    Beispiel-Auswahl (keine künstlich vervielfältigte Auswahl). Beide Kategorien können gleichzeitig
    zutreffen (dann getrennte Tage-Blöcke) oder einzeln. Gibt {tag_nr: (Bezeichnung, Beispiele)}
    zurück.
    """
    ergebnis: dict[int, tuple[str, list[POI]]] = {}
    naechster_tag = len(plan.tagesrouten)
    if plan.lernaktivitaet_tag_beispiele:
        ergebnis[naechster_tag] = ("eine Lernaktivität", plan.lernaktivitaet_tag_beispiele)
        naechster_tag -= 1
    if plan.tour_tag_beispiele:
        for _ in range(max(1, plan.tour_tage_anzahl)):
            ergebnis[naechster_tag] = ("eine geführte Tour", plan.tour_tag_beispiele)
            naechster_tag -= 1
    return ergebnis


_BEISPIELE_JE_LEEREM_TAG = 3


def _verteile_beispiele_auf_leere_tage(
    tagesrouten: list[Tagesroute], weitere_empfehlungen: list[POI], reservierte_tage: frozenset[int] = frozenset()
) -> tuple[dict[int, list[POI]], list[POI]]:
    """
    Tage OHNE eingeplantes Programm (Anforderung des Product Owners: kein leerer Tag
    ohne Inhalt) zeigen bis zu `_BEISPIELE_JE_LEEREM_TAG` Kandidaten aus den nicht eingeplanten
    Empfehlungen statt nur "kein Programm eingeplant" – dieser Fallback ist bewusst generisch für
    JEDEN nicht eingeplanten Kandidaten (nicht tour-spezifisch). Verteilt OHNE Wiederholung über
    mehrere leere Tage, bis der Vorrat reicht. Gibt zusätzlich die verbleibende Liste zurück, damit
    die allgemeine "Weitere Empfehlungen"-Sektion die hier bereits gezeigten POIs nicht ein zweites
    Mal auflistet.

    `reservierte_tage` (siehe pipeline.py `_trenne_sonderkategorie_ab`/`_reservierte_sondertage`
    oben): die für Touren/Lernaktivitäten reservierten Tage werden hier NICHT mitbefüllt – die
    zeigen bereits die echten Beispiele der jeweiligen Kategorie, nicht generische Empfehlungen,
    sonst würde der Vorrat unnötig verbraucht.
    """
    beispiele_je_tag: dict[int, list[POI]] = {}
    rest = list(weitere_empfehlungen)
    for tag_nr, tagesroute in enumerate(tagesrouten, start=1):
        if tagesroute.besuche or not rest or tag_nr in reservierte_tage:
            continue
        beispiele_je_tag[tag_nr] = rest[:_BEISPIELE_JE_LEEREM_TAG]
        rest = rest[_BEISPIELE_JE_LEEREM_TAG:]
    return beispiele_je_tag, rest


_BEISPIELRESTAURANTS_JE_TAG = 3


def _restaurants_fuer_tag(beispielrestaurants: list[POI], tag_nr: int) -> list[POI]:
    """
    Bis zu `_BEISPIELRESTAURANTS_JE_TAG` Beispielrestaurants für EINEN Tag – rotierender Ausschnitt
    aus dem gemeinsamen, nach Entfernung zur Unterkunft sortierten Pool (siehe pipeline.py), damit
    nicht an jedem Tag exakt dieselben Namen stehen, sofern der Pool groß genug ist. Restaurants
    laufen bewusst NICHT durch Optimierung 1 (siehe pipeline.py) – diese Liste ist rein informativ,
    keine feste Uhrzeit/Einplanung.
    """
    if not beispielrestaurants:
        return []
    anzahl = len(beispielrestaurants)
    start = ((tag_nr - 1) * _BEISPIELRESTAURANTS_JE_TAG) % anzahl
    return [beispielrestaurants[(start + i) % anzahl] for i in range(min(_BEISPIELRESTAURANTS_JE_TAG, anzahl))]


_MARKT_BEISPIELE_JE_TAG = 3


def _markt_beispiele_fuer_tag(markt_beispiele: list[POI], tag_nr: int, letzter_tag: int) -> list[POI]:
    """
    Wie `_restaurants_fuer_tag`, nur für den Mittags-Zeitblock bei gewünschtem lokalem Kontakt
    (siehe pipeline.py `_trenne_markt_beispiele_ab`) – NUR an "vollen" Tagen (nicht Anreise-, nicht
    Abreisetag, Entscheidung des Product Owners zu F19), auch wenn `markt_beispiele` befüllt ist.
    """
    if not markt_beispiele or tag_nr in (1, letzter_tag):
        return []
    anzahl = len(markt_beispiele)
    start = ((tag_nr - 1) * _MARKT_BEISPIELE_JE_TAG) % anzahl
    return [markt_beispiele[(start + i) % anzahl] for i in range(min(_MARKT_BEISPIELE_JE_TAG, anzahl))]


def _robustheit_text(richtung: str, robustheit: "RobustheitsErgebnis | None") -> str | None:
    """Formuliert EIN Härtetest-Ergebnis (Hinreise ODER Rückreise, siehe monte_carlo.py
    `haertetest_teilstrecken`) als Satz – None, wenn kein Härtetest lief (z.B. Auto, kein
    Umstiegsrisiko)."""
    if robustheit is None:
        return None
    status = "robust" if robustheit.ist_robust else "NICHT robust – Anschluss-Risiko"
    return (
        f"Verbindungssicherheit {richtung}: {robustheit.quote_ohne_verletzung:.1%} der "
        f"{robustheit.laeufe} simulierten Läufe ohne verpassten Anschluss ({status})."
    )


def als_text(plan: Reiseplan) -> str:
    """Erzeugt eine lesbare Textzusammenfassung des Reiseplans."""
    zeilen = ["=== Reiseplan ===", "", _EINLEITUNG, ""]
    uhrzeit_hinweis = _uhrzeit_hinweis_text(plan)
    if uhrzeit_hinweis:
        zeilen.append(uhrzeit_hinweis)
        zeilen.append("")
    if plan.einschraenkungshinweise:
        for hinweis in plan.einschraenkungshinweise:
            zeilen.append(hinweis)
        zeilen.append("")
    if plan.feste_termine_hinweise:
        for hinweis in plan.feste_termine_hinweise:
            zeilen.append(hinweis)
        zeilen.append("")
    verleih_hinweis = _verleih_hinweis_text(plan)
    if verleih_hinweis:
        zeilen.append(verleih_hinweis)
        zeilen.append("")
    if plan.unterkunft_name:
        zeile = f"Unterkunft: {plan.unterkunft_name}"
        link = maps_link(plan.unterkunft_place_id)
        if link:
            zeile += f" — {link}"
        zeilen.append(zeile)
        zeilen.append("")
    kosten_text = _kosten_text(plan)
    if kosten_text:
        zeilen.append(kosten_text)
        zeilen.append("")
    if plan.sicherheitshinweis:
        zeilen.append(plan.sicherheitshinweis)
        zeilen.append("")
    zeilen.append(
        f"Hinreise: {plan.hinreise.alternative.verkehrsmittel} "
        f"({plan.hinreise.alternative.dauer_minuten} min, "
        f"{plan.hinreise.alternative.kosten_euro:.2f} €, "
        f"{plan.hinreise.co2_kg:.1f} kg CO2)"
    )
    zeilen.extend(_teilstrecken_zeilen(plan.hinreise.alternative))
    hinreise_link = routen_link(
        plan.wohnort, _hinreise_ziel_fuer_link(plan), _TRAVELMODE_JE_VERKEHRSMITTEL.get(plan.hinreise.alternative.verkehrsmittel)
    )
    if hinreise_link:
        zeilen.append(f"  Route: {hinreise_link}")
    zeilen.append("")

    letzter_tag = len(plan.tagesrouten)
    sondertage = _reservierte_sondertage(plan)
    beispiele_je_leerem_tag, weitere_empfehlungen_rest = _verteile_beispiele_auf_leere_tage(
        plan.tagesrouten, plan.weitere_aktivitaeten_empfehlungen,
        reservierte_tage=frozenset(sondertage) | _termin_tage(plan),
    )
    for tag_nr, tagesroute in enumerate(plan.tagesrouten, start=1):
        ist_ankunftstag = tag_nr == 1
        termine_heute = _feste_termine_fuer_tag(plan, tag_nr)
        zeilen.append(f"Tag {tag_nr}" + (" (Ankunft)" if ist_ankunftstag else "") + " – unser Vorschlag:")
        if ist_ankunftstag:
            zeilen.append(
                f"  Ankunft mit {plan.hinreise.alternative.verkehrsmittel} nach "
                f"{_format_dauer(plan.hinreise.alternative.dauer_minuten)} – danach Check-in in der Unterkunft."
            )
        if tag_nr in sondertage:
            # Reservierter Sonder-Tag (Tour oder Lernaktivität, siehe pipeline.py
            # `_trenne_sonderkategorie_ab`) – KEIN optimiertes Programm, die Beispiele wurden NICHT
            # von Optimierung 1 ausgewählt.
            bezeichnung, beispiele = sondertage[tag_nr]
            zeilen.append(f"  Für diesen Tag empfehlen wir {bezeichnung}, zur freien Auswahl:")
            for poi in beispiele:
                zeile = f"    - {poi.name} ({poi.kategorie})"
                link = maps_link(poi.place_id)
                if link:
                    zeile += f" — {link}"
                zeilen.append(zeile)
        elif not tagesroute.besuche:
            beispiele = beispiele_je_leerem_tag.get(tag_nr, [])
            if beispiele:
                zeilen.append("  Kein festes Programm eingeplant – mögliche Beispiele für diesen Tag:")
                for poi in beispiele:
                    zeile = f"    - {poi.name} ({poi.kategorie}, ca. {poi.required_time} Minuten)"
                    link = maps_link(poi.place_id)
                    if link:
                        zeile += f" — {link}"
                    zeilen.append(zeile)
            elif termine_heute:
                zeilen.append("  Außer dem festen Termin ist an diesem Tag kein weiteres Programm eingeplant.")
            else:
                zeilen.append("  (kein Programm eingeplant)")
        else:
            zeilen.append("  Ab Ankunft:" if ist_ankunftstag else "  Ab Tagesbeginn:")
            for index, besuch in enumerate(tagesroute.besuche):
                fahrzeit = _fahrzeit_vor_besuch(tagesroute.besuche, index)
                herkunft = "Unterkunft" if index == 0 else tagesroute.besuche[index - 1].poi.name
                herkunft_koordinaten = (
                    plan.unterkunft_koordinaten if index == 0
                    else (tagesroute.besuche[index - 1].poi.x, tagesroute.besuche[index - 1].poi.y)
                )
                verkehrsmittel = _verkehrsmittel_label(besuch.anfahrt_modus)
                zusatz = f" ({verkehrsmittel})" if verkehrsmittel else ""
                etappen_zeile = f"    → {fahrzeit} Min.{zusatz} von {herkunft}"
                etappen_link = routen_link(herkunft_koordinaten, (besuch.poi.x, besuch.poi.y), besuch.anfahrt_modus)
                if etappen_link:
                    etappen_zeile += f" — {etappen_link}"
                zeilen.append(etappen_zeile)
                pause_hinweis = f", davon {besuch.wartezeit} Min. Pause/Wartezeit" if besuch.wartezeit > 0 else ""
                zeile = (
                    f"    {_zeitpunkt_text(plan, tag_nr, besuch.ankunft, 'nach')}: {besuch.poi.name} "
                    f"({_zeitpunkt_text(plan, tag_nr, besuch.abfahrt, 'bis')}{pause_hinweis}, Score {besuch.poi.score:.1f})"
                )
                link = maps_link(besuch.poi.place_id)
                if link:
                    zeile += f" — {link}"
                zeilen.append(zeile)
            if tag_nr != letzter_tag:
                zeilen.append("  Rückweg zur Unterkunft, Zeit zum Umziehen.")
        # Feste Termine stehen nach der optimierten Route und vor den Vorschlägen: sie schließen den
        # Tag ab und sind, anders als die Vorschläge, fest eingeplant (siehe `FesterTermin`).
        for termin in termine_heute:
            ort = termin.wunschort.ort
            zeile = (
                f"  Fester Termin (dein ausdrücklicher Wunsch, nicht Teil der optimierten Route): {ort.name}"
                + (f", {ort.adresse}" if ort.adresse else "")
                + f" – {_termin_zeitpunkt_text(plan, termin)}, Dauer ca. {_format_dauer(termin.wunschort.dauer_minuten)}"
            )
            link = maps_link(ort.place_id)
            if link:
                zeile += f" — {link}"
            zeilen.append(zeile)
            anfahrt_text = _termin_anfahrt_text(termin)
            termin_link = _termin_routen_link(plan, termin)
            if anfahrt_text or termin_link:
                zeilen.append(f"    {anfahrt_text}" + (f" — Route: {termin_link}" if termin_link else ""))
        # Beispielrestaurants/Markt-Café-Vorschläge NUR an normalen Tagen (Regression, Rückmeldung des Product Owners
        # nach einer echten Testreise: an reservierten Tour-/Lernaktivitäts-Tagen wirkten sie wie
        # zusätzliches, unerwünschtes Programm neben der Tour/dem Kochkurs – "da ist nur Tour").
        if tag_nr not in sondertage:
            restaurants_heute = _restaurants_fuer_tag(plan.beispielrestaurants, tag_nr)
            if restaurants_heute:
                zeilen.append("  Beispielrestaurants in der Nähe der Unterkunft (nicht eingeplant, zur freien Wahl):")
                for poi in restaurants_heute:
                    zeile = f"    - {poi.name} ({poi.kategorie})"
                    link = maps_link(poi.place_id)
                    if link:
                        zeile += f" — {link}"
                    zeilen.append(zeile)
            markt_heute = _markt_beispiele_fuer_tag(plan.markt_beispiele, tag_nr, letzter_tag)
            if markt_heute:
                zeilen.append("  Beispiele für einen Markt-/Café-Besuch mittags (nicht eingeplant, zur freien Wahl):")
                for poi in markt_heute:
                    zeile = f"    - {poi.name} ({poi.kategorie})"
                    link = maps_link(poi.place_id)
                    if link:
                        zeile += f" — {link}"
                    zeilen.append(zeile)
        zeilen.append("")

    if weitere_empfehlungen_rest:
        zeilen.append("Weitere Empfehlungen in der Nähe (nicht im Vorschlag oben, zum selbst Ergänzen/Tauschen):")
        for poi in weitere_empfehlungen_rest:
            zeile = f"  - {poi.name} ({poi.kategorie}, ca. {poi.required_time} Minuten)"
            link = maps_link(poi.place_id)
            if link:
                zeile += f" — {link}"
            zeilen.append(zeile)
        zeilen.append("")

    zeilen.append(
        f"Rückreise: {plan.rueckreise.alternative.verkehrsmittel} "
        f"({plan.rueckreise.alternative.dauer_minuten} min, "
        f"{plan.rueckreise.alternative.kosten_euro:.2f} €, "
        f"{plan.rueckreise.co2_kg:.1f} kg CO2)"
    )
    zeilen.extend(_teilstrecken_zeilen(plan.rueckreise.alternative))
    rueckreise_link = routen_link(
        _hinreise_ziel_fuer_link(plan), plan.wohnort, _TRAVELMODE_JE_VERKEHRSMITTEL.get(plan.rueckreise.alternative.verkehrsmittel)
    )
    if rueckreise_link:
        zeilen.append(f"  Route: {rueckreise_link}")

    hinreise_robustheit_text = _robustheit_text("Hinreise", plan.hinreise_robustheit)
    rueckreise_robustheit_text = _robustheit_text("Rückreise", plan.rueckreise_robustheit)
    if hinreise_robustheit_text or rueckreise_robustheit_text:
        zeilen.append("")
        if hinreise_robustheit_text:
            zeilen.append(hinreise_robustheit_text)
        if rueckreise_robustheit_text:
            zeilen.append(rueckreise_robustheit_text)

    return "\n".join(zeilen)


def als_html(plan: Reiseplan) -> str:
    """
    Erzeugt eine HTML-Fassung des Reiseplans mit klickbaren Google-Maps-
    Links zu Unterkunft und POIs (Anforderung des Product Owners: Nutzer möchte
    Unterkünfte/Aktivitäten in der Mail direkt anklicken können). Nutzt
    dieselben Daten wie als_text(), nur als <a href> statt Klartext-URL.
    """

    def esc(text: str) -> str:
        return html.escape(str(text))

    def link_html(name: str, place_id: str | None) -> str:
        link = maps_link(place_id)
        return f'<a href="{esc(link)}">{esc(name)}</a>' if link else esc(name)

    def routen_link_html(link: str | None) -> str:
        return f' <a href="{esc(link)}">Route in Google Maps ansehen</a>' if link else ""

    def teilstrecken_html(alternative: ReiseAlternative) -> str:
        zeilen = _teilstrecken_zeilen(alternative, praefix="")
        if not zeilen:
            return ""
        eintraege = "".join(f"<li>{esc(zeile)}</li>" for zeile in zeilen)
        return f"<ul>{eintraege}</ul>"

    teile = ["<h2>Reiseplan</h2>", f"<p>{esc(_EINLEITUNG)}</p>"]

    uhrzeit_hinweis = _uhrzeit_hinweis_text(plan)
    if uhrzeit_hinweis:
        teile.append(f"<p>{esc(uhrzeit_hinweis)}</p>")

    if plan.einschraenkungshinweise:
        for hinweis in plan.einschraenkungshinweise:
            teile.append(f"<p>{esc(hinweis)}</p>")

    for hinweis in plan.feste_termine_hinweise:
        teile.append(f"<p>{esc(hinweis)}</p>")

    verleih_hinweis = _verleih_hinweis_text(plan)
    if verleih_hinweis:
        teile.append(f"<p>{esc(verleih_hinweis)}</p>")

    if plan.unterkunft_name:
        teile.append(
            "<p><strong>Unterkunft:</strong> "
            f"{link_html(plan.unterkunft_name, plan.unterkunft_place_id)}</p>"
        )

    kosten_text = _kosten_text(plan)
    if kosten_text:
        teile.append(f"<p>{esc(kosten_text)}</p>")

    if plan.sicherheitshinweis:
        teile.append(f"<p>{esc(plan.sicherheitshinweis)}</p>")

    hinreise_link = routen_link(
        plan.wohnort, _hinreise_ziel_fuer_link(plan), _TRAVELMODE_JE_VERKEHRSMITTEL.get(plan.hinreise.alternative.verkehrsmittel)
    )
    teile.append(
        "<p><strong>Hinreise:</strong> "
        f"{esc(plan.hinreise.alternative.verkehrsmittel)} "
        f"({plan.hinreise.alternative.dauer_minuten} min, "
        f"{plan.hinreise.alternative.kosten_euro:.2f} €, "
        f"{plan.hinreise.co2_kg:.1f} kg CO2){routen_link_html(hinreise_link)}</p>"
    )
    teile.append(teilstrecken_html(plan.hinreise.alternative))

    letzter_tag = len(plan.tagesrouten)
    sondertage = _reservierte_sondertage(plan)
    beispiele_je_leerem_tag, weitere_empfehlungen_rest = _verteile_beispiele_auf_leere_tage(
        plan.tagesrouten, plan.weitere_aktivitaeten_empfehlungen,
        reservierte_tage=frozenset(sondertage) | _termin_tage(plan),
    )
    for tag_nr, tagesroute in enumerate(plan.tagesrouten, start=1):
        ist_ankunftstag = tag_nr == 1
        termine_heute = _feste_termine_fuer_tag(plan, tag_nr)
        teile.append(f"<h3>Tag {tag_nr}{' (Ankunft)' if ist_ankunftstag else ''} – unser Vorschlag</h3>")
        if ist_ankunftstag:
            teile.append(
                f"<p>Ankunft mit {esc(plan.hinreise.alternative.verkehrsmittel)} nach "
                f"{_format_dauer(plan.hinreise.alternative.dauer_minuten)} – danach Check-in in der Unterkunft.</p>"
            )
        if tag_nr in sondertage:
            bezeichnung, beispiele = sondertage[tag_nr]
            teile.append(f"<p>Für diesen Tag empfehlen wir {esc(bezeichnung)}, zur freien Auswahl:</p><ul>")
            for poi in beispiele:
                teile.append(f"<li>{link_html(poi.name, poi.place_id)} ({esc(poi.kategorie)})</li>")
            teile.append("</ul>")
        elif not tagesroute.besuche:
            beispiele = beispiele_je_leerem_tag.get(tag_nr, [])
            if beispiele:
                teile.append("<p>Kein festes Programm eingeplant – mögliche Beispiele für diesen Tag:</p><ul>")
                for poi in beispiele:
                    zusatz = f" ({esc(poi.kategorie)}, ca. {poi.required_time} Minuten)"
                    teile.append(f"<li>{link_html(poi.name, poi.place_id)}{zusatz}</li>")
                teile.append("</ul>")
            elif termine_heute:
                teile.append("<p>Außer dem festen Termin ist an diesem Tag kein weiteres Programm eingeplant.</p>")
            else:
                teile.append("<p>(kein Programm eingeplant)</p>")
        else:
            teile.append(f"<p>{'Ab Ankunft' if ist_ankunftstag else 'Ab Tagesbeginn'}:</p><ul>")
            for index, besuch in enumerate(tagesroute.besuche):
                fahrzeit = _fahrzeit_vor_besuch(tagesroute.besuche, index)
                herkunft = "Unterkunft" if index == 0 else tagesroute.besuche[index - 1].poi.name
                herkunft_koordinaten = (
                    plan.unterkunft_koordinaten if index == 0
                    else (tagesroute.besuche[index - 1].poi.x, tagesroute.besuche[index - 1].poi.y)
                )
                verkehrsmittel = _verkehrsmittel_label(besuch.anfahrt_modus)
                verkehrsmittel_zusatz = f" ({esc(verkehrsmittel)})" if verkehrsmittel else ""
                etappen_link = routen_link(herkunft_koordinaten, (besuch.poi.x, besuch.poi.y), besuch.anfahrt_modus)
                pause_hinweis = f", davon {besuch.wartezeit} min Pause/Wartezeit" if besuch.wartezeit > 0 else ""
                teile.append(
                    "<li>"
                    f"<span style=\"color:#666\">→ {fahrzeit} min{verkehrsmittel_zusatz} von {esc(herkunft)}"
                    f"{routen_link_html(etappen_link)}</span><br>"
                    f"{esc(_zeitpunkt_text(plan, tag_nr, besuch.ankunft, 'nach'))}: "
                    f"{link_html(besuch.poi.name, besuch.poi.place_id)} "
                    f"({esc(_zeitpunkt_text(plan, tag_nr, besuch.abfahrt, 'bis'))}{esc(pause_hinweis)}, Score {besuch.poi.score:.1f})"
                    "</li>"
                )
            teile.append("</ul>")
            if tag_nr != letzter_tag:
                teile.append("<p>Rückweg zur Unterkunft, Zeit zum Umziehen.</p>")
        # Feste Termine wie in als_text nach der Route und vor den Vorschlägen, als eigener, farbig
        # abgesetzter Block (Inline-Styles, da Mail-Programme kein eingebettetes CSS zuverlässig darstellen).
        for termin in termine_heute:
            ort = termin.wunschort.ort
            adresse = f", {esc(ort.adresse)}" if ort.adresse else ""
            anfahrt_text = _termin_anfahrt_text(termin)
            teile.append(
                '<div style="border-left:4px solid #1f5f7a;padding:6px 12px;margin:8px 0;background:#eef5f8">'
                "<strong>Fester Termin</strong> (dein ausdrücklicher Wunsch, nicht Teil der optimierten Route): "
                f"{link_html(ort.name, ort.place_id)}{adresse}<br>"
                f"{esc(_termin_zeitpunkt_text(plan, termin))}, Dauer ca. {esc(_format_dauer(termin.wunschort.dauer_minuten))}"
                + (f"<br>{esc(anfahrt_text)}" if anfahrt_text else "")
                + routen_link_html(_termin_routen_link(plan, termin))
                + "</div>"
            )
        # Beispielrestaurants/Markt-Café-Vorschläge NUR an normalen Tagen (siehe als_text – dieselbe
        # Regression: an reservierten Tour-/Lernaktivitäts-Tagen wirkten sie wie zusätzliches,
        # unerwünschtes Programm neben der Tour/dem Kochkurs).
        if tag_nr not in sondertage:
            restaurants_heute = _restaurants_fuer_tag(plan.beispielrestaurants, tag_nr)
            if restaurants_heute:
                teile.append("<p>Beispielrestaurants in der Nähe der Unterkunft (nicht eingeplant, zur freien Wahl):</p><ul>")
                for poi in restaurants_heute:
                    teile.append(f"<li>{link_html(poi.name, poi.place_id)} ({esc(poi.kategorie)})</li>")
                teile.append("</ul>")
            markt_heute = _markt_beispiele_fuer_tag(plan.markt_beispiele, tag_nr, letzter_tag)
            if markt_heute:
                teile.append("<p>Beispiele für einen Markt-/Café-Besuch mittags (nicht eingeplant, zur freien Wahl):</p><ul>")
                for poi in markt_heute:
                    teile.append(f"<li>{link_html(poi.name, poi.place_id)} ({esc(poi.kategorie)})</li>")
                teile.append("</ul>")

    if weitere_empfehlungen_rest:
        teile.append(
            "<p><strong>Weitere Empfehlungen in der Nähe</strong> "
            "(nicht im Vorschlag oben, zum selbst Ergänzen/Tauschen):</p><ul>"
        )
        for poi in weitere_empfehlungen_rest:
            zusatz = f" ({esc(poi.kategorie)}, ca. {poi.required_time} Minuten)"
            teile.append(f"<li>{link_html(poi.name, poi.place_id)}{zusatz}</li>")
        teile.append("</ul>")

    rueckreise_link = routen_link(
        _hinreise_ziel_fuer_link(plan), plan.wohnort, _TRAVELMODE_JE_VERKEHRSMITTEL.get(plan.rueckreise.alternative.verkehrsmittel)
    )
    teile.append(
        "<p><strong>Rückreise:</strong> "
        f"{esc(plan.rueckreise.alternative.verkehrsmittel)} "
        f"({plan.rueckreise.alternative.dauer_minuten} min, "
        f"{plan.rueckreise.alternative.kosten_euro:.2f} €, "
        f"{plan.rueckreise.co2_kg:.1f} kg CO2){routen_link_html(rueckreise_link)}</p>"
    )
    teile.append(teilstrecken_html(plan.rueckreise.alternative))

    for richtung, robustheit in [("Hinreise", plan.hinreise_robustheit), ("Rückreise", plan.rueckreise_robustheit)]:
        text = _robustheit_text(richtung, robustheit)
        if text:
            teile.append(f"<p>{esc(text)}</p>")

    return "\n".join(teile)


def als_kartendaten(plan: Reiseplan, foto_url_fuer_place_id: Callable[[str | None], str | None]) -> dict[str, Any]:
    """
    Strukturierte Kartendaten (Hinreise, Unterkunft, eingeplante POIs je Tag, Rückreise) für die
    Web-UI (webapp.py) – Foto, kurze Beschreibung, ungefährer Preis, Google-Maps-Link, analog zur
    kleinen Vorschau, die Google Maps beim Anklicken eines Ortes zeigt (siehe Entscheidung des Product Owners). Als
    Beschreibung dient `POI.kategorie` (bereits vorhandene Daten) statt einer zusätzlichen,
    kostenpflichtigen Place-Details-Anfrage für einen redaktionellen Text – kein neuer API-Aufruf
    nur für diese Kartenansicht (Grundprinzip 1: keine erfundenen/zusätzlich erkauften Fakten ohne
    Not).

    `foto_url_fuer_place_id` bildet eine `place_id` auf eine bereits heruntergeladene, ausgelieferte
    Bild-URL ab (siehe src/ausgabe/fotos.py `lade_fotos_fuer_plan` + webapp.py) – None, wenn kein
    Foto vorliegt. Diese Funktion selbst kennt keine URLs/Dateipfade, nur die Struktur der Daten.

    Entscheidung des Product Owners (Rückmeldung des Product Owners nach einer echten 15-Tage-Testreise, "alle Reiseelemente
    sollen hier aufgeführt werden"): NEBEN den optimierten POI-Karten bekommt jeder Tag zusätzlich
    ein `vorschlaege`-Feld – Kandidaten, die bewusst NICHT durch Optimierung 1 gelaufen sind
    (geführte Tour/Lernaktivität an reservierten Tagen, Markt-/Café- und Restaurant-/Kneipen-
    Beispiele am Mittags-/Abend-Block bei lokalem Kontakt, generische Beispiele an leeren Tagen –
    siehe `_reservierte_sondertage`/`_markt_beispiele_fuer_tag`/`_restaurants_fuer_tag`/
    `_verteile_beispiele_auf_leere_tage`, dieselbe Logik wie in `als_text`). Jede dieser Karten trägt
    ein `label`, damit die Web-UI sie sichtbar als "nur Vorschlag, nicht Teil der optimierten Route"
    markieren kann statt sie wie eine echte Tagesplan-Karte aussehen zu lassen.
    """

    def poi_karte(
        poi: POI, ankunft_text: str = "", abfahrt_text: str = "", verkehrsmittel: str = "",
        routen_link_wert: str | None = None, label: str | None = None,
    ) -> dict[str, Any]:
        return {
            "name": poi.name,
            "kategorie": poi.kategorie,
            "foto_url": foto_url_fuer_place_id(poi.place_id),
            "maps_link": maps_link(poi.place_id),
            "routen_link": routen_link_wert,
            "score": poi.score,
            "ankunft": ankunft_text,
            "abfahrt": abfahrt_text,
            "verkehrsmittel": verkehrsmittel,
            "label": label,
        }

    sondertage = _reservierte_sondertage(plan)
    letzter_tag = len(plan.tagesrouten)
    beispiele_je_leerem_tag, _ = _verteile_beispiele_auf_leere_tage(
        plan.tagesrouten, plan.weitere_aktivitaeten_empfehlungen,
        reservierte_tage=frozenset(sondertage) | _termin_tage(plan),
    )

    def termin_karte(termin: FesterTermin) -> dict[str, Any]:
        """Eigene Kartenart "Fester Termin" (kein `label`, damit die Web-UI sie nicht als
        gestrichelten Vorschlag, sondern als fest eingeplanten Termin darstellt)."""
        ort = termin.wunschort.ort
        return {
            "name": ort.name,
            "adresse": ort.adresse,
            "foto_url": foto_url_fuer_place_id(ort.place_id),
            "maps_link": maps_link(ort.place_id),
            "routen_link": _termin_routen_link(plan, termin),
            "zeitpunkt": _termin_zeitpunkt_text(plan, termin),
            "am_tagesende": not _termin_uhrzeit_gilt(plan, termin),
            "dauer": _format_dauer(termin.wunschort.dauer_minuten),
            "anfahrt": _termin_anfahrt_text(termin),
        }

    tage = []
    for tag_nr, tagesroute in enumerate(plan.tagesrouten, start=1):
        besuche = []
        for index, besuch in enumerate(tagesroute.besuche):
            herkunft_koordinaten = (
                plan.unterkunft_koordinaten if index == 0
                else (tagesroute.besuche[index - 1].poi.x, tagesroute.besuche[index - 1].poi.y)
            )
            besuche.append(poi_karte(
                besuch.poi,
                _zeitpunkt_text(plan, tag_nr, besuch.ankunft, "ab").strip(),
                _zeitpunkt_text(plan, tag_nr, besuch.abfahrt, "bis").strip(),
                _verkehrsmittel_label(besuch.anfahrt_modus),
                routen_link(herkunft_koordinaten, (besuch.poi.x, besuch.poi.y), besuch.anfahrt_modus),
            ))

        vorschlaege = []
        if tag_nr in sondertage:
            bezeichnung, beispiele = sondertage[tag_nr]
            vorschlaege = [poi_karte(poi, label=f"Vorschlag: {bezeichnung} (kein fester Ablauf)") for poi in beispiele]
        else:
            if not besuche:
                vorschlaege += [
                    poi_karte(poi, label="Vorschlag (nicht eingeplant)")
                    for poi in beispiele_je_leerem_tag.get(tag_nr, [])
                ]
            vorschlaege += [
                poi_karte(poi, label="Vorschlag: mittags Markt/Café")
                for poi in _markt_beispiele_fuer_tag(plan.markt_beispiele, tag_nr, letzter_tag)
            ]
            vorschlaege += [
                poi_karte(poi, label="Vorschlag: abends essen gehen")
                for poi in _restaurants_fuer_tag(plan.beispielrestaurants, tag_nr)
            ]

        tage.append({
            "tag": tag_nr, "ankunftstag": tag_nr == 1, "besuche": besuche, "vorschlaege": vorschlaege,
            "feste_termine": [termin_karte(termin) for termin in _feste_termine_fuer_tag(plan, tag_nr)],
        })

    unterkunft = None
    if plan.unterkunft_name:
        unterkunft = {
            "name": plan.unterkunft_name,
            "foto_url": foto_url_fuer_place_id(plan.unterkunft_place_id),
            "maps_link": maps_link(plan.unterkunft_place_id),
        }

    # Rückmeldung des Product Owners nach echtem Browser-Test (siehe
    # doku/30_stage30_zeit_fotos_verleih_layout_avatar/README.md, Punkt Verleih-Karte): der lokale
    # Verleih (F14, `lokaler_verleih_poi`) stand bisher NUR als Textsatz im fertigen Reiseplan
    # (`_verleih_hinweis_text`), nicht als eigene Karte in der Web-UI. `None`, wenn kein Verleih
    # gewünscht ODER trotz Wunsch keiner gefunden wurde (die ehrliche Fehlanzeige bleibt weiterhin
    # NUR als Text erhalten, siehe `_verleih_hinweis_text` – hier keine "Verleih nicht gefunden"-
    # Karte, analog zu `unterkunft` oben, das ebenfalls einfach entfällt statt leer angezeigt zu
    # werden). KEIN "Vorschlag"-Label (kein `label` übergeben) – anders als die Markt-/Restaurant-
    # Beispiele ist das ein bereits im Dialog bestätigter, konkreter Fund, keine lose Anregung.
    verleih = None
    if plan.lokaler_verleih_poi is not None:
        # Rückmeldung des Product Owners (siehe doku/34_.../README.md): zusätzlich ein "Route ansehen"-Link wie bei
        # den Tages-POI-Karten, hier IMMER von der Unterkunft zum Verleih (nicht von der jeweils
        # vorherigen Station wie bei den Tagesrouten-Etappen – der Verleih ist kein Teil einer
        # optimierten Route, sondern ein einzelner, eigenständiger Weg ab der Unterkunft). `None`,
        # wenn keine Unterkunfts-Koordinaten bekannt sind (Grundprinzip 1: kein geratener Startpunkt).
        verleih_routen_link = routen_link(
            plan.unterkunft_koordinaten, (plan.lokaler_verleih_poi.x, plan.lokaler_verleih_poi.y), "walking"
        )
        verleih = poi_karte(plan.lokaler_verleih_poi, routen_link_wert=verleih_routen_link)
        if plan.lokales_leihfahrzeug_gewuenscht:
            verleih["kategorie"] = f"Verleih: {plan.lokales_leihfahrzeug_gewuenscht}"

    def reise_karte(
        name_praefix: str, richtung: BewerteteAlternative,
        ursprung: tuple[float, float] | str | None, ziel: tuple[float, float] | str | None,
        robustheit: RobustheitsErgebnis | None,
    ) -> dict[str, Any]:
        beschreibung = (
            f"{richtung.alternative.dauer_minuten} min · {richtung.alternative.kosten_euro:.2f} € · "
            f"{richtung.co2_kg:.1f} kg CO2"
        )
        if robustheit is not None:
            beschreibung += f" · Verbindungssicherheit {robustheit.quote_ohne_verletzung:.1%}"
        return {
            "name": f"{name_praefix}: {richtung.alternative.verkehrsmittel}",
            "beschreibung": beschreibung,
            "foto_url": _standardbild_url(richtung.alternative.verkehrsmittel),
            "maps_link": None,
            "routen_link": routen_link(ursprung, ziel, _TRAVELMODE_JE_VERKEHRSMITTEL.get(richtung.alternative.verkehrsmittel)),
        }

    hinreise_ziel = _hinreise_ziel_fuer_link(plan)

    return {
        # Titelbereich der Web-UI (Iteration 2, Gesamtdesign): Eckdaten und Titelbild, siehe
        # `_eckdaten`/`_titelbild_url`.
        "eckdaten": _eckdaten(plan),
        "titelbild_url": _titelbild_url(plan, foto_url_fuer_place_id),
        "hinreise": reise_karte("Hinreise", plan.hinreise, plan.wohnort, hinreise_ziel, plan.hinreise_robustheit),
        "unterkunft": unterkunft,
        "verleih": verleih,
        "tage": tage,
        "rueckreise": reise_karte("Rückreise", plan.rueckreise, hinreise_ziel, plan.wohnort, plan.rueckreise_robustheit),
        "sicherheitshinweis": plan.sicherheitshinweis,
        # Nicht einplanbare feste Wunschorte (keine Landverbindung o. Ä.), sichtbar statt still verworfen.
        "feste_termine_hinweise": list(plan.feste_termine_hinweise),
        "weitere_empfehlungen": [
            {
                "name": poi.name,
                "kategorie": poi.kategorie,
                "foto_url": foto_url_fuer_place_id(poi.place_id),
                "maps_link": maps_link(poi.place_id),
            }
            for poi in plan.weitere_aktivitaeten_empfehlungen
        ],
    }


def speichere_datei(plan: Reiseplan, pfad: Path) -> None:
    """Schreibt den Reiseplan als lesbare Textdatei (Ersatz für Mailversand, siehe ARCHITEKTUR.md)."""
    pfad.write_text(als_text(plan), encoding="utf-8")


def speichere_json(plan: Reiseplan, pfad: Path) -> None:
    """Schreibt den Reiseplan zusätzlich als JSON, z.B. für eine spätere Weiterverarbeitung/Visualisierung."""
    pfad.write_text(json.dumps(asdict(plan), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def speichere_poi_uebersicht(plan: Reiseplan, pfad: Path) -> None:
    """
    Schreibt EINE CSV-Zeile pro POI-Kandidat, den Optimierung 1 gesehen hat – nicht nur die
    tatsächlich eingeplanten (Anforderung des Product Owners: alle Kandidaten sichtbar machen, um
    die Funktionsweise von Optimierung 1 nachprüfen zu können). Erlaubt einen direkten Soll/Ist-Abgleich: welche POIs standen mit welchem
    Score/Zeitfenster zur Auswahl, welche davon hat Optimierung 1 tatsächlich in die Tagesroute
    übernommen und welche nicht (siehe `Reiseplan.weitere_aktivitaeten_empfehlungen`) – ohne
    dafür extra die `TOPTWInstanz` durchreichen zu müssen, die Daten stecken schon vollständig in
    `Reiseplan`.

    Semikolon statt Komma als Trennzeichen + UTF-8-BOM (`utf-8-sig`): deutsches Excel interpretiert
    eine reine Komma-CSV sonst falsch (Komma ist dort das Dezimaltrennzeichen), das BOM sorgt
    dafür, dass Umlaute nicht als Mojibake erscheinen.
    """
    zeilen = [
        ["tag", "status", "name", "kategorie", "score", "besuchsdauer_minuten",
         "zeitfenster_oeffnung", "zeitfenster_schliessung", "ankunft", "abfahrt", "quelle", "maps_link"]
    ]
    for tag_nr, tagesroute in enumerate(plan.tagesrouten, start=1):
        for besuch in tagesroute.besuche:
            poi = besuch.poi
            zeilen.append([
                str(tag_nr), "eingeplant", poi.name, poi.kategorie, f"{poi.score:.2f}",
                str(poi.required_time), str(poi.opening), str(poi.closing),
                str(besuch.ankunft), str(besuch.abfahrt), poi.quelle, maps_link(poi.place_id) or "",
            ])
    for poi in plan.weitere_aktivitaeten_empfehlungen:
        zeilen.append([
            "-", "nicht eingeplant (Kandidat)", poi.name, poi.kategorie, f"{poi.score:.2f}",
            str(poi.required_time), str(poi.opening), str(poi.closing), "-", "-",
            poi.quelle, maps_link(poi.place_id) or "",
        ])
    with pfad.open("w", encoding="utf-8-sig", newline="") as datei:
        schreiber = csv.writer(datei, delimiter=";")
        schreiber.writerows(zeilen)


def sende_mail(plan: Reiseplan, empfaenger: str) -> None:
    """
    Verschickt den Reiseplan als HTML-Mail (klickbare Google-Maps-Links zu
    Unterkunft/POIs, siehe als_html()) über die Mailjet Send API v3.1
    (https://dev.mailjet.com/email/guides/send-api-v31/). Braucht
    MAILJET_API_KEY, MAILJET_SECRET_KEY und MAILJET_ABSENDER in der .env
    (siehe .env.example) sowie eine bei Mailjet verifizierte Absenderadresse.

    Wirft RuntimeError, wenn die Konfiguration fehlt oder Mailjet einen
    Fehler zurückgibt (bewusst KEIN stiller Fehlschlag: eine nicht
    zugestellte Mail soll sichtbar scheitern statt unbemerkt zu verschwinden).
    """
    if not EINSTELLUNGEN.mailjet_api_key or not EINSTELLUNGEN.mailjet_secret_key:
        raise RuntimeError(
            "MAILJET_API_KEY/MAILJET_SECRET_KEY fehlen in der .env. "
            "Nutze stattdessen speichere_datei() oder als_text(), oder trage die Keys ein."
        )
    if not EINSTELLUNGEN.mailjet_absender:
        raise RuntimeError(
            "MAILJET_ABSENDER fehlt in der .env (bei Mailjet verifizierte Absenderadresse nötig)."
        )

    nutzlast = {
        "Messages": [
            {
                "From": {"Email": EINSTELLUNGEN.mailjet_absender, "Name": "Reisebot"},
                "To": [{"Email": empfaenger}],
                "Subject": "Dein Reiseplan",
                "TextPart": als_text(plan),
                "HTMLPart": als_html(plan),
            }
        ]
    }
    antwort = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(EINSTELLUNGEN.mailjet_api_key, EINSTELLUNGEN.mailjet_secret_key),
        json=nutzlast,
        timeout=10,
    )
    if antwort.status_code >= 400:
        raise RuntimeError(f"Mailjet-Fehler ({antwort.status_code}): {antwort.text}")
