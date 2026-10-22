# Station 36 — Umweltfreundlichste Auto-Route für An- und Abreise

**Zeitraum:** 29.09.2026 (ENTSCHEIDUNGSLOG.md Phase 65)
**Code-Duplikat:** `code_stand/` enthält den Stand **vor** dieser Station (`src/api/google_maps.py`,
`src/api/typen.py`, `src/api/mock_data.py`, `tests/test_google_maps.py`).

## Auslöser

Demo-Feedback aus der Demo von Iteration 2 (`Program/Iteration 2/Feedback Demo Iteration 2.txt`,
Punkt „Routenwahl"): Bei der An- und Abreise mit dem Auto soll stets die Route gewählt werden, die
Google Maps als umweltfreundlichste (kraftstoffsparendste) kennzeichnet. Präzisierung des Product
Owners: gemeint ist die in Google Maps mit grünem Blatt markierte Route.

Bis zu dieser Station kam die Auto-Alternative aus der Legacy Directions API (`mode=driving`). Diese
kennt keine Umwelt-Kennzeichnung; Eco-Routing bietet nur die Routes API
(https://developers.google.com/maps/documentation/routes/eco-routes).

## Umsetzung

**Anfrage.** `GoogleMapsClient._hole_auto_route_umweltfreundlich` in `src/api/google_maps.py` sendet
`POST https://routes.googleapis.com/directions/v2:computeRoutes`:

- Header `X-Goog-Api-Key` (Schlüssel nicht in der URL) und `X-Goog-FieldMask` = `routes.duration`,
  `routes.distanceMeters`, `routes.routeLabels`, `geocodingResults`;
- Body: Start und Ziel als Adresstext, `travelMode` DRIVE, `routingPreference` TRAFFIC_AWARE_OPTIMAL
  (Voraussetzung für Eco-Routing, abgerechnet über die SKU „Compute Routes Pro"),
  `requestedReferenceRoutes` ["FUEL_EFFICIENT"], `languageCode` de. Ohne `vehicleInfo` legt Google
  den Standard-Motortyp Benzin zugrunde.

**Routenwahl.** `_waehle_umweltfreundlichste_route` nimmt die Route mit dem Label FUEL_EFFICIENT,
unabhängig von ihrer Position im Array. Fehlt sie, fällt die Wahl auf die Route mit DEFAULT_ROUTE,
ohne Labels auf die erste Route. Der Rückfall ist über das neue Feld
`ReiseAlternative.umweltfreundlichste_route` in `src/api/typen.py` erkennbar (True/False, `None` bei
Bahn und Fernbus) und wird zusätzlich per `logging.warning` gemeldet. Damit nutzt `src/` erstmals das
Modul `logging`.

**Umrechnung.** `_dauer_in_minuten` wandelt die Dauerangabe der API (Sekunden mit Suffix „s",
z. B. „1234s") in Minuten um. Die Kosten bleiben `distanz_km × _KOSTEN_JE_KM_SCHAETZUNG_EURO["driving"]`, `teilstrecken` bleibt
leer (durchgehende Fahrt ohne Umstiege, daher kein Monte-Carlo-Härtetest).

**Fehlerverhalten.**

- Leeres `routes`-Array ergibt wie bisher bei ZERO_RESULTS/NOT_FOUND `None`, die Auto-Alternative
  entfällt. Das gilt auch für einen nicht auflösbaren Ort, den die Routes API laut Dokumentation mit
  HTTP 200 und `geocoderStatus` ungleich OK meldet; `_nicht_aufgeloeste_orte` liest diese Angabe für
  eine Warnung aus.
- HTTP ≥ 400 führt zu einem `RuntimeError` mit verständlicher Meldung aus
  `_routes_api_fehlermeldung`, bei 401/403 mit dem Hinweis, die Routes API zu aktivieren und die
  Key-Einschränkungen zu prüfen. Es gibt keinen Rückfall auf die Legacy-API.

**Einbindung.** Bahn und Fernbus kommen unverändert aus der Legacy Directions API. Die Schnittstelle
`reisealternativen` ist gleich geblieben, Reihenfolge Bahn, Fernbus, Auto. `pipeline.py` und der
F13-Dialog (`vorschlaege.py`) nutzen die neue Route daher ohne Änderung. Die Auto-Alternative der Mock-Daten
in `src/api/mock_data.py` trägt `umweltfreundlichste_route=True` und bildet damit den Regelfall ab.

**Betriebsvoraussetzung.** Die Routes API muss im Google-Cloud-Projekt aktiviert und gegebenenfalls in
die Einschränkungen des API-Schlüssels aufgenommen sein.

**Verworfene Alternativen.**

- Legacy Directions API mit `alternatives=true`: liefert mehrere Routen, aber keine
  Umwelt-Kennzeichnung.
- Automatischer Rückfall auf die Legacy-API bei Fehlern: Es bliebe unsichtbar, dass die
  umweltfreundlichste Route gar nicht ermittelt wurde (Grundprinzip 1).
- Fahrzeugtyp beim Nutzer erfragen bzw. `vehicleInfo` setzen: vom Product Owner ausgeschlossen.
- `routeToken` anfordern: laut Google-Dokumentation nur für das Navigation SDK nötig.
- Auswahl nach Array-Position statt nach Label: die Reihenfolge der Routen ist nicht garantiert.

## Verifikation

`tests/test_google_maps.py` (38 Tests) mit neuen Fällen: FUEL_EFFICIENT an zweiter Stelle, Rückfall
auf DEFAULT_ROUTE, Antwort ohne Labels, leere Antwort, nicht auflösbarer Ort, HTTP 403,
Anfrageinhalt (URL, Header, Body), Dauer-Parser, Mock-Modus ohne Netzzugriff. Komplette Suite grün
(364/364).

Nicht geprüft: Aufruf der echten Routes API. Die Antwortformate sind nur gegen die
Google-Dokumentation abgeglichen.

## Offene Punkte

- Der Routenlink in `src/ausgabe/reiseplan.py` öffnet Google Maps mit dessen Standardwahl, nicht
  zwingend die Route mit grünem Blatt.
- Es wird keine Abfahrtszeit übergeben; die Route berücksichtigt die Verkehrslage zum
  Planungszeitpunkt.
- `umweltfreundlichste_route` wird weder im Reiseplan noch in der Debug-Ausgabe angezeigt.
- Eco-Routing gibt es nur bei Startorten in von Google unterstützten Ländern (u. a. DE, AT, CH, IT,
  FR, ES) und laut Google im Status Preview. Außerhalb davon ist ein Abbruch der Planung zu erwarten
  (HTTP-Fehler ohne Rückfall); fehlt lediglich die Kennzeichnung, greift der Rückfall auf die
  Standardroute. Beides ist nicht live geprüft. Für die Zielgruppe mit Wohnort in Deutschland
  unkritisch, vom Product Owner als Limitation akzeptiert.
- Antwortformate der Routes API live bestätigt (04.10.2026). Behobener Fehler: Koordinatenpaare "lat,lng" (Unterkunft) wurden im Feld `address` übergeben und von der Routes API mit HTTP 400 abgelehnt; seither Übergabe als `location.latLng` (`_routes_api_wegpunkt`).
