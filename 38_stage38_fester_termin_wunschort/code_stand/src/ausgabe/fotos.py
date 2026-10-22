"""
Lädt Places-Fotos (Foto-Referenzen aus google_maps.py, siehe `POI.foto_referenz`/
`Unterkunft.foto_referenz`) für die Unterkunft und alle im fertigen Reiseplan gezeigten POIs
serverseitig herunter – NUR von der Web-UI (webapp.py) aufgerufen, NICHT von chat.py oder
pruefe_planung.py, damit im normalen Konsolen-Chat keine zusätzlichen, ungewollten API-Aufrufe/
Kosten entstehen. Der API-Key bleibt dabei serverseitig (siehe google_maps.py `lade_foto`); der
Browser bekommt nur die fertigen Bilddateien ausgeliefert, nie den Key selbst.

Befund aus einem Browser-Test (siehe
doku/30_stage30_zeit_fotos_verleih_layout_avatar/README.md, Punkt Fotos): bis Stage 29 wurden NUR
die tatsächlich in die Tagesrouten eingeplanten POIs + die Unterkunft mit Foto versorgt – alle
"Vorschlag"-Karten (Markt-/Café-Beispiele, Beispielrestaurants, Sondertage-Beispiele, generische
Beispiele an leeren Tagen) und "Weitere Empfehlungen" blieben dadurch IMMER ohne Foto, unabhängig
davon, ob Google eins geliefert hätte – der vom Nutzer beobachtete Fischmarkt-Brügge-Fall war genau
so eine Vorschlag-Karte. Jetzt deckt der Download ALLE POI-Kategorien ab, die `als_kartendaten`
(reiseplan.py) als eigene Karte zeigt.
"""
from __future__ import annotations

from pathlib import Path

from src.api.google_maps import MapsClient
from src.ausgabe.reiseplan import Reiseplan


def _lade_foto_fuer(client: MapsClient, foto_referenz: str | None, place_id: str | None,
                     zielordner: Path, dateiname_je_place_id: dict[str, str]) -> None:
    """Lädt EIN Foto herunter, falls noch nicht vorhanden. Fehlt `foto_referenz` (die ursprüngliche
    Suche lieferte kein `photos`-Feld für diesen Ort), wird zuerst der Nachlade-Fallback über
    `MapsClient.hole_foto_referenz` versucht (siehe google_maps.py – manche echten Orte liefern in
    der ursprünglichen Suche kein Foto, obwohl Google Details dazu hat), NUR für diese kleine,
    bereits feststehende Menge an Karten (Performance, siehe ENTSCHEIDUNGSLOG.md Phase 44 – kein Aufruf für rohe
    Suchtreffer)."""
    if not place_id or place_id in dateiname_je_place_id:
        return
    if foto_referenz is None:
        foto_referenz = client.hole_foto_referenz(place_id)
    if not foto_referenz:
        return
    dateiname = f"{place_id}.jpg"
    if client.lade_foto(foto_referenz, str(zielordner / dateiname)):
        dateiname_je_place_id[place_id] = dateiname


def lade_fotos_fuer_plan(plan: Reiseplan, client: MapsClient, zielordner: Path) -> dict[str, str]:
    """
    Lädt ein Foto für die Unterkunft, den lokalen Verleih (falls gefunden) sowie für JEDEN POI, der
    in der Web-UI als eigene Karte auftaucht – eingeplante Tagesroute-Besuche, "Weitere
    Empfehlungen" und alle "Vorschlag"-Kategorien (Markt/Café, Beispielrestaurants, Sondertage-/
    Touren-/Lernaktivitäts-Beispiele, generische Beispiele an leeren Tagen).

    Rückgabe: dict `place_id -> Dateiname` (relativ zu `zielordner`), NUR für Downloads, die
    tatsächlich geklappt haben (`MapsClient.lade_foto` liefert False statt zu werfen, siehe dort) –
    kein Eintrag für fehlgeschlagene oder fehlende Fotos, statt einen kaputten Bildverweis
    auszugeben (Grundprinzip 1: ehrliches Fehlen statt eines erfundenen Platzhalters).
    """
    zielordner.mkdir(parents=True, exist_ok=True)
    dateiname_je_place_id: dict[str, str] = {}

    if plan.unterkunft_place_id:
        _lade_foto_fuer(
            client, plan.unterkunft_foto_referenz, plan.unterkunft_place_id, zielordner, dateiname_je_place_id
        )

    if plan.lokaler_verleih_poi is not None:
        _lade_foto_fuer(
            client, plan.lokaler_verleih_poi.foto_referenz, plan.lokaler_verleih_poi.place_id,
            zielordner, dateiname_je_place_id,
        )

    for tagesroute in plan.tagesrouten:
        for besuch in tagesroute.besuche:
            _lade_foto_fuer(client, besuch.poi.foto_referenz, besuch.poi.place_id, zielordner, dateiname_je_place_id)

    for poi_liste in (
        plan.weitere_aktivitaeten_empfehlungen,
        plan.beispielrestaurants,
        plan.tour_tag_beispiele,
        plan.lernaktivitaet_tag_beispiele,
        plan.markt_beispiele,
    ):
        for poi in poi_liste:
            _lade_foto_fuer(client, poi.foto_referenz, poi.place_id, zielordner, dateiname_je_place_id)

    return dateiname_je_place_id
