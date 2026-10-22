"""
Feste Wunschorte: Auflösung ausdrücklich genannter Orte über echte API-Daten (Demo-Feedback
Iteration 2: "Berücksichtigung dedizierter Standorte").

Sagt ein Nutzer ausdrücklich, dass er einen bestimmten Ort "unbedingt"/"unter allen Umständen"
sehen möchte, beurteilt das LLM diese Aussage aus dem Gesprächskontext und übergibt den Ort als
Tool-Argument `feste_wunschorte` bei speichere_feld (siehe agent_tools.py). Dieses Modul übernimmt
den deterministischen Teil (Grundprinzip 3):

- Validierung der vom LLM übergebenen Einträge (Name, optionale Dauer, optionale Uhrzeit),
- Auflösung jedes Namens zu einem echten Ort über `MapsClient.finde_ort` (Grundprinzip 2) –
  ein nicht gefundener Ort wird nicht gespeichert und nicht erfunden (Grundprinzip 1),
- bei Mobilitätseinschränkung "mittel"/"stark" die Barrierefreiheitsabfrage je Ort,
- die Anfahrt ab der bestätigten Unterkunft samt Nachhaltigkeitshinweis bei weit entfernten Orten
  (`pruefe_anfahrten`),
- Rückmeldetexte für das LLM (Bestätigung beim Nutzer, ehrliche Fehlermeldung).

Eine Schlüsselwort-Erkennung von "unbedingt" o. ä. im Python-Code gibt es bewusst nicht: die
Beurteilung, ob eine Aussage einen festen Termin begründet, liegt analog zu
`mobilitaetseinschraenkung_stufe` und `tour_tage_anzahl` beim LLM. Der eigentliche Planungseffekt
(fester Slot außerhalb von Optimierung 1) entsteht erst in pipeline.py.
"""
from __future__ import annotations

from typing import Any

import requests

from src.api.google_maps import MapsClient
from src.ausgabe.reiseplan import _verkehrsmittel_label
from src.datenaufbereitung.aufbereitung import modi_fuer_lokalen_transport
from src.fragekatalog.schema import FesterWunschort, ReiseAnfrage, WunschortAnfahrt
from src.optimierung.verkehrsmittelwahl import bewerte_alternativen, nur_bestaetigte_verkehrsmittel

# Besuchsdauer eines festen Wunschorts, wenn der Nutzer auf die Nachfrage keine Dauer nennt. Zwei
# Stunden liegen über den typischen Place-Type-Dauern in google_maps.py (`_BESUCHSDAUER_JE_TYP_
# MINUTEN`, meist 30–90 Minuten), weil ein ausdrücklich gewünschter Ort in der Regel ausführlicher
# besucht wird als ein beliebiger Kandidat der Optimierung.
STANDARD_BESUCHSDAUER_WUNSCHORT_MINUTEN = 120

# Stufen, bei denen die Barrierefreiheit eines Ortes überhaupt ausschlaggebend ist (siehe schema.py
# `mobilitaetseinschraenkung_stufe`); bei "leicht" bleibt jeder Ort nutzbar.
_STUFEN_MIT_BARRIEREFREIHEITSPRUEFUNG = ("mittel", "stark")

_MINUTEN_JE_TAG = 24 * 60

# Grenze (Minuten, einfache Strecke Unterkunft -> Wunschort), ab der ein fester Wunschort als "weit
# entfernt" gilt (Entscheidung des Product Owners). Bis zu dieser Dauer genügt das lokale
# Verkehrsmittel aus F14; darüber wird die Anfahrt wie eine kleine An-/Abreise über Bahn, Fernbus
# oder Auto berechnet, und der Nutzer erhält einen Nachhaltigkeitshinweis mit Zusatzstrecke und
# grob geschätztem CO₂.
SCHWELLE_WEITER_WUNSCHORT_MINUTEN = 60


def formatiere_uhrzeit(minuten: int) -> str:
    """Minuten seit Mitternacht als "HH:MM" (900 -> "15:00")."""
    return f"{minuten // 60:02d}:{minuten % 60:02d}"


def _normalisiere(name: str) -> str:
    return " ".join(name.lower().split())


def _bezugspunkt(anfrage: ReiseAnfrage, maps_client: MapsClient) -> tuple[tuple[float, float] | None, str]:
    """
    Ortsbezug für die Suche: bevorzugt die bestätigte Unterkunft (F15), sonst das geokodierte
    primäre Reiseziel (F07). Ist beides nicht verfügbar, wird ohne Ortsbezug gesucht; das wird dem
    LLM gemeldet, damit es den gefundenen Ort besonders sorgfältig bestätigen lässt.
    """
    if anfrage.unterkunft_koordinaten is not None:
        return anfrage.unterkunft_koordinaten, "bestätigte Unterkunft"
    ziel = anfrage.primaeres_reiseziel()
    if ziel:
        try:
            return maps_client.geocode(ziel), f"Reiseziel {ziel}"
        except (ValueError, RuntimeError, requests.RequestException):
            pass
    return None, "ohne Ortsbezug (weder Unterkunft noch Reiseziel bekannt)"


def _ganzzahl(wert: Any) -> int | None:
    """Ganze Zahl aus einem Tool-Argument; bool (in Python eine int-Unterklasse) zählt nicht."""
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, float) and wert.is_integer():
        return int(wert)
    return None


def loese_wunschorte_auf(
    eintraege: list[Any], anfrage: ReiseAnfrage, maps_client: MapsClient
) -> tuple[list[FesterWunschort], list[str]]:
    """
    Wandelt die vom LLM übergebene, VOLLSTÄNDIGE Liste `[{name, dauer_minuten?, uhrzeit_minuten?}]`
    in gespeicherte `FesterWunschort`-Einträge um. Rückgabe: (neue Liste, Meldungen für das LLM).

    - Die Liste ersetzt die bisherige vollständig; eine leere Liste entfernt alle Wunschorte.
    - Ein bereits zuvor aufgelöster Eintrag mit gleichem Namen wird übernommen statt erneut
      gesucht: das LLM schickt bei jeder Änderung (z. B. Verzicht auf einen Ort) die ganze Liste,
      ohne diese Wiederverwendung entstünde für unveränderte Einträge je Aufruf ein weiterer
      kostenpflichtiger Places-Aufruf. Dauer und Uhrzeit werden dabei aus dem neuen Aufruf übernommen.
    - Nicht gefundene Orte und ungültige Einträge werden nicht gespeichert und ehrlich gemeldet.
    """
    meldungen: list[str] = []
    bisherige = {_normalisiere(w.rohname): w for w in anfrage.feste_wunschorte}
    neue_liste: list[FesterWunschort] = []
    gesehene_place_ids: set[str] = set()
    bezug: tuple[tuple[float, float] | None, str] | None = None  # erst bei Bedarf ermittelt

    if not eintraege:
        if bisherige:
            meldungen.append("Alle festen Wunschorte wurden entfernt.")
        return [], meldungen

    for eintrag in eintraege:
        name = eintrag.get("name") if isinstance(eintrag, dict) else None
        if not isinstance(name, str) or not name.strip():
            meldungen.append(f"Ungültiger Eintrag ohne Namen ignoriert: {eintrag!r}.")
            continue
        name = name.strip()

        dauer_roh = eintrag.get("dauer_minuten")
        dauer = _ganzzahl(dauer_roh)
        dauer_ist_standard = False
        if dauer is None or not 0 < dauer <= _MINUTEN_JE_TAG:
            if dauer_roh is not None:
                meldungen.append(f"'{name}': ungültige Besuchsdauer {dauer_roh!r} ignoriert, Standardwert verwendet.")
            dauer = STANDARD_BESUCHSDAUER_WUNSCHORT_MINUTEN
            dauer_ist_standard = True

        uhrzeit_roh = eintrag.get("uhrzeit_minuten")
        uhrzeit = _ganzzahl(uhrzeit_roh)
        if uhrzeit_roh is not None and (uhrzeit is None or not 0 <= uhrzeit < _MINUTEN_JE_TAG):
            # Keine Uhrzeit raten: ein ungültiger Wert wird verworfen, der Termin gilt als ohne Uhrzeit.
            meldungen.append(f"'{name}': ungültige Uhrzeit {uhrzeit_roh!r} ignoriert.")
            uhrzeit = None

        vorher = bisherige.get(_normalisiere(name))
        if vorher is not None:
            ort = vorher.ort
            barrierefrei, geprueft = vorher.barrierefrei, vorher.barrierefreiheit_geprueft
        else:
            if bezug is None:
                bezug = _bezugspunkt(anfrage, maps_client)
            try:
                ort = maps_client.finde_ort(name, nahe_bei=bezug[0])
            except (RuntimeError, requests.RequestException) as fehler:
                meldungen.append(
                    f"'{name}': Die Ortssuche ist technisch fehlgeschlagen ({fehler}); der Ort wurde NICHT "
                    "gespeichert. Erfinde keine Angaben dazu, sondern versuche es später erneut."
                )
                continue
            if ort is None:
                meldungen.append(
                    f"'{name}' wurde über Google Places NICHT gefunden und daher NICHT gespeichert. Erfinde "
                    "keinen Ort und keine Adresse; bitte den Nutzer um eine genauere Angabe (z. B. "
                    "vollständiger Name mit Ort) und speichere die Liste danach erneut."
                )
                continue
            barrierefrei, geprueft = None, False

        if ort.place_id and ort.place_id in gesehene_place_ids:
            meldungen.append(f"'{name}' verweist auf denselben Ort wie ein anderer Eintrag und wurde nur einmal gespeichert.")
            continue
        if ort.place_id:
            gesehene_place_ids.add(ort.place_id)

        neuer_eintrag = FesterWunschort(
            rohname=name, ort=ort, dauer_minuten=dauer, uhrzeit_minuten=uhrzeit,
            barrierefrei=barrierefrei, barrierefreiheit_geprueft=geprueft,
        )
        if vorher is not None:
            # Eine bereits geprüfte Anfahrt bleibt gültig (gleicher Ort); sie wird nur bei einer
            # geänderten Unterkunft neu berechnet (siehe `pruefe_anfahrten`).
            neuer_eintrag.anfahrt = vorher.anfahrt
            neuer_eintrag.anfahrt_geprueft_ab = vorher.anfahrt_geprueft_ab
        neue_liste.append(neuer_eintrag)
        dauer_text = f"{dauer} Min." + (" (Standardwert, der Nutzer hat keine Dauer genannt)" if dauer_ist_standard else "")
        uhrzeit_text = formatiere_uhrzeit(uhrzeit) if uhrzeit is not None else "keine genannt (Termin am Ende des Tages)"
        herkunft = "bereits zuvor gefunden" if vorher is not None else f"gefunden, Suche mit Bezug: {bezug[1]}"
        meldungen.append(
            f"Fester Wunschort '{name}' {herkunft}: {ort.name}, {ort.adresse or 'Adresse nicht bekannt'}. "
            f"Besuchsdauer: {dauer_text}. Uhrzeit: {uhrzeit_text}."
        )

    if neue_liste:
        meldungen.append(
            "Lass Name und Adresse jedes neu gefundenen Wunschorts kurz vom Nutzer bestätigen. Ist es nicht der "
            "gemeinte Ort, speichere die vollständige Liste erneut mit einem genaueren Namen oder ohne diesen "
            "Eintrag."
        )
    return neue_liste, meldungen


def pruefe_barrierefreiheit_offener_wunschorte(anfrage: ReiseAnfrage, maps_client: MapsClient) -> list[str]:
    """
    Holt bei Mobilitätseinschränkung "mittel"/"stark" die Barrierefreiheitsangabe für alle noch
    nicht geprüften Wunschorte ein (ein Places-Details-Aufruf je Ort, nur einmal je Ort) und gibt
    Hinweise für das LLM zurück. Ein fester Wunschort wird dabei bewusst NICHT ausgeschlossen (anders
    als gewöhnliche POI-Kandidaten in vertraeglichkeit.py): der Nutzer hat ihn ausdrücklich
    gewünscht, er soll über die Einschränkung informiert werden und selbst entscheiden.

    Wird bei jedem speichere_feld-Aufruf ausgeführt, damit auch eine erst nach dem Wunschort genannte
    Einschränkung die Prüfung nachholt.
    """
    if anfrage.mobilitaetseinschraenkung_stufe not in _STUFEN_MIT_BARRIEREFREIHEITSPRUEFUNG:
        return []
    hinweise: list[str] = []
    for wunschort in anfrage.feste_wunschorte:
        if wunschort.barrierefreiheit_geprueft:
            continue
        try:
            wunschort.barrierefrei = maps_client.ist_barrierefrei(wunschort.ort.place_id)
        except (RuntimeError, requests.RequestException):
            wunschort.barrierefrei = None
        wunschort.barrierefreiheit_geprueft = True
        if wunschort.barrierefrei is True:
            continue
        befund = (
            "ist laut Google Places NICHT barrierefrei zugänglich (kein rollstuhlgerechter Eingang)"
            if wunschort.barrierefrei is False
            else "hat bei Google Places keine Angabe zur Barrierefreiheit"
        )
        hinweise.append(
            f"Hinweis Barrierefreiheit: Der feste Wunschort '{wunschort.ort.name}' {befund}. Er bleibt eingeplant "
            "(ausdrücklicher Nutzerwunsch); weise den Nutzer darauf hin und frage, ob er ihn trotzdem behalten möchte."
        )
    return hinweise


def _lokale_anfahrt(
    anfrage: ReiseAnfrage, ziel: tuple[float, float], maps_client: MapsClient
) -> WunschortAnfahrt | None:
    """
    Schnellste Anfahrt mit einem der in F14 genannten lokalen Verkehrsmittel (echte Distance
    Matrix, derselbe Aufruf wie für die Anfahrtsempfehlungen in vorschlaege.py). Ohne F14-Antwort
    None: dann entscheidet direkt die F13-Präferenz (siehe `_fernanfahrt`). Ein Modus ohne
    Ergebnis (-1) oder mit technischem Fehler wird übergangen, nicht geschätzt.
    """
    if not anfrage.lokaler_transport_praeferenz or anfrage.unterkunft_koordinaten is None:
        return None
    beste: WunschortAnfahrt | None = None
    for modus in modi_fuer_lokalen_transport(anfrage.lokaler_transport_praeferenz):
        try:
            dauern = maps_client.anfahrtszeiten_minuten(anfrage.unterkunft_koordinaten, [ziel], modus)
        except (RuntimeError, requests.RequestException):
            continue
        if not dauern or dauern[0] < 0:
            continue
        if beste is None or dauern[0] < beste.dauer_minuten:
            beste = WunschortAnfahrt(
                verkehrsmittel=_verkehrsmittel_label(modus) or modus, dauer_minuten=dauern[0],
                quelle="distance_matrix", modus=modus,
            )
    return beste


def _fernanfahrt(
    anfrage: ReiseAnfrage, ziel: tuple[float, float], maps_client: MapsClient
) -> tuple[WunschortAnfahrt | None, str | None]:
    """
    Anfahrt über dieselben Alternativen wie die An-/Abreise (`reisealternativen`: Bahn, Fernbus und
    Auto, beim Auto automatisch die kraftstoffsparendste Route der Routes API). Ausgewählt wird wie
    bei der An-/Abreise die bestbewertete Alternative unter den in F13 bestätigten Verkehrsmitteln
    (`nur_bestaetigte_verkehrsmittel`). Distanz, Dauer und Kosten stammen aus der API-Antwort, das
    CO₂ (Hin- und Rückweg) aus Distanz × Emissionsfaktor (verkehrsmittelwahl.py/emissionsfaktoren.py).
    Rückgabe: (Anfahrt oder None, technische Fehlermeldung oder None).
    """
    unterkunft = anfrage.unterkunft_koordinaten
    try:
        # Koordinaten als "lat,lng" wie bei der An-/Abreise bis zur Unterkunft (pipeline.py).
        alternativen = maps_client.reisealternativen(f"{unterkunft[0]},{unterkunft[1]}", f"{ziel[0]},{ziel[1]}")
    except (RuntimeError, requests.RequestException) as fehler:
        return None, str(fehler)
    if not alternativen:
        return None, None
    gewaehlt = nur_bestaetigte_verkehrsmittel(bewerte_alternativen(alternativen), anfrage.verkehrsmittel_praeferenz)[0]
    alternative = gewaehlt.alternative
    return WunschortAnfahrt(
        verkehrsmittel=alternative.verkehrsmittel,
        dauer_minuten=alternative.dauer_minuten,
        quelle="reisealternativen",
        distanz_km=alternative.distanz_km,
        co2_kg_hin_und_zurueck=2 * gewaehlt.co2_kg,
        kosten_euro_einfach=alternative.kosten_euro,
        umweltfreundlichste_route=alternative.umweltfreundlichste_route,
    ), None


def _ermittle_anfahrt(
    wunschort: FesterWunschort, anfrage: ReiseAnfrage, maps_client: MapsClient
) -> tuple[WunschortAnfahrt | None, str | None]:
    """
    Variante (b) nach Entscheidung des Product Owners: zuerst das lokale Verkehrsmittel aus F14;
    liegt dessen einfache Strecke über `SCHWELLE_WEITER_WUNSCHORT_MINUTEN` oder gibt es kein
    Ergebnis, die Fernanfahrt über Bahn/Fernbus/Auto passend zu F13. Liefert auch die Fernanfahrt
    nichts, bleibt die (lange) lokale Anfahrt als einzige echte Angabe erhalten.
    """
    ziel = (wunschort.ort.x, wunschort.ort.y)
    lokal = _lokale_anfahrt(anfrage, ziel, maps_client)
    if lokal is not None and lokal.dauer_minuten <= SCHWELLE_WEITER_WUNSCHORT_MINUTEN:
        return lokal, None
    fern, fehler = _fernanfahrt(anfrage, ziel, maps_client)
    return (fern or lokal), fehler


def _hinweis_weit_entfernt(wunschort: FesterWunschort, anfahrt: WunschortAnfahrt) -> str:
    teile = [f"Einfache Strecke: ca. {anfahrt.dauer_minuten} Min., Verkehrsmittel: {anfahrt.verkehrsmittel}"]
    if anfahrt.umweltfreundlichste_route:
        teile.append(" (kraftstoffsparendste Route laut Google)")
    if anfahrt.distanz_km is not None:
        teile.append(f", ca. {anfahrt.distanz_km:.0f} km")
    teile.append(". ")
    if anfahrt.co2_kg_hin_und_zurueck is not None:
        teile.append(
            f"Hin- und Rückweg verursachen grob geschätzt zusätzlich {anfahrt.co2_kg_hin_und_zurueck:.1f} kg CO₂ "
            "(Schätzung über Faustwerte je Verkehrsmittel, keine amtlich verifizierten Emissionsfaktoren; "
            "nicht als exakten Wert darstellen). "
        )
    else:
        teile.append("Eine Entfernung in km liefert diese Abfrage nicht, daher ist keine CO₂-Schätzung möglich. ")
    return (
        f"Hinweis Nachhaltigkeit: Der feste Wunschort '{wunschort.ort.name}' liegt weit von der Unterkunft "
        f"entfernt (mehr als {SCHWELLE_WEITER_WUNSCHORT_MINUTEN} Min. einfache Strecke). " + "".join(teile)
        + "Weise den Nutzer auf diese Zusatzstrecke und ihre Nachhaltigkeitsfolgen hin und frage ausdrücklich, "
        "ob der Ort trotzdem bleiben soll. Verzichtet er, speichere feste_wunschorte ohne diesen Ort erneut."
    )


def pruefe_anfahrten(
    anfrage: ReiseAnfrage, maps_client: MapsClient, liste_neu_gesetzt: bool = False
) -> list[str]:
    """
    Berechnet die Anfahrt für jeden festen Wunschort, der für die aktuell bestätigte Unterkunft
    noch nicht geprüft wurde, und gibt die daraus entstehenden Hinweise für das LLM zurück
    (weit entfernt, keine Landverbindung, technischer Fehler). Idempotent: ein bereits für dieselbe
    Unterkunft geprüfter Ort erzeugt weder einen neuen API-Aufruf noch erneut denselben Hinweis.

    Aufgerufen bei jedem speichere_feld-Aufruf (dadurch automatisch nachgeholt, sobald die
    Unterkunft mit F15 bestätigt wird) und noch einmal vor plane_reise_und_abschliessen, damit ein
    Hinweis den Nutzer in jedem Fall vor der Planung erreicht.

    Ohne bestätigte Unterkunft ist keine Prüfung möglich; wurde die Liste gerade gesetzt
    (`liste_neu_gesetzt`), wird dem LLM gemeldet, dass die Prüfung nachgeholt wird.
    """
    if not anfrage.feste_wunschorte:
        return []
    unterkunft = anfrage.unterkunft_koordinaten
    if unterkunft is None:
        if liste_neu_gesetzt:
            return [
                "Die Entfernung der festen Wunschorte zur Unterkunft wird geprüft, sobald die Unterkunft "
                "bestätigt ist (spätestens vor der Planung); ein Hinweis bei weit entfernten Orten folgt dann."
            ]
        return []

    hinweise: list[str] = []
    for wunschort in anfrage.feste_wunschorte:
        if wunschort.anfahrt_geprueft_ab == unterkunft:
            continue
        anfahrt, fehler = _ermittle_anfahrt(wunschort, anfrage, maps_client)
        wunschort.anfahrt = anfahrt
        wunschort.anfahrt_geprueft_ab = unterkunft
        if anfahrt is None:
            if fehler:
                hinweise.append(
                    f"Hinweis Anfahrt: Für den festen Wunschort '{wunschort.ort.name}' ist die Verbindungsabfrage "
                    f"technisch fehlgeschlagen ({fehler}); ob und wie weit der Ort erreichbar ist, ist unbekannt. "
                    "Sag das dem Nutzer ehrlich und erfinde keine Verbindung."
                )
            else:
                hinweise.append(
                    f"Hinweis Anfahrt: Für den festen Wunschort '{wunschort.ort.name}' wurde ab der Unterkunft keine "
                    "Landverbindung gefunden (weder mit dem lokalen Verkehrsmittel noch mit Bahn, Fernbus oder Auto). "
                    "Flüge sind ausgeschlossen, der Ort ist damit für diese Reise nicht erreichbar. Sag das dem "
                    "Nutzer ehrlich, erfinde keine Verbindung und frage, ob er auf den Ort verzichtet (dann "
                    "feste_wunschorte ohne diesen Ort erneut speichern)."
                )
        elif anfahrt.dauer_minuten > SCHWELLE_WEITER_WUNSCHORT_MINUTEN:
            hinweise.append(_hinweis_weit_entfernt(wunschort, anfahrt))
            if fehler:
                hinweise.append(
                    f"Die Abfrage von Bahn/Fernbus/Auto zu '{wunschort.ort.name}' ist technisch fehlgeschlagen "
                    f"({fehler}); die Angabe oben beruht nur auf dem lokalen Verkehrsmittel."
                )
    return hinweise
