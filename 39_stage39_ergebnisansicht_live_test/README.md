# Station 39 — Ergebnisansicht nach dem Live-Test: Eckdatenzeile, Nudge, Gesprächsverlauf

**Zeitraum:** 04.10.2026 (ENTSCHEIDUNGSLOG.md Phase 68)
**Kein Code-Duplikat** (kein `code_stand`-Snapshot vorgesehen, transparent vermerkt).

## Auslöser

Live-Test des Product Owners am 04.10.2026 mit echtem Dialog und echten APIs; geprüft wurde die
Ergebnisansicht „Deine Reise nach Hamburg" aus Station 37. Drei Beobachtungen:

- Die Eckdaten-Chips unter dem Titel wirkten wie anklickbare Knöpfe; der grün hervorgehobene
  CO₂-Chip wirkte wie eine getroffene Auswahl.
- Der Nachhaltigkeits-Nudge im fertigen Plan lautete „Die Bahn braucht nur -60 Minuten länger …".
  Ursache: Verglichen wird mit der bestbewerteten Alternative (bester Gesamtwert aus Zeit, Kosten
  und CO₂), nicht mit der schnellsten. Ist die Bahn schneller, aber wegen höherer Kosten schlechter
  bewertet, wird die Zeitdifferenz negativ.
- Der nach Abschluss standardmäßig eingeklappte Chat wurde übersehen.

## Umsetzung

**Eckdatenzeile (`static/index.html`).** Die Eckdaten stehen als nicht-interaktive Infozeile in
`<ul id="eckdaten">`, je Angabe ein `li.eckdaten-angabe`, getrennt durch dezente Mittelpunkte. Es
gibt keinen Rahmen, keinen Hintergrund, keinen Hover-Effekt und keine farbige Hervorhebung des
CO₂-Werts mehr. Der Trennpunkt hängt am Ende einer Angabe, damit bei einem Zeilenumbruch keine Zeile
mit einem Trennzeichen beginnt. Der Tooltip zur Kostenschätzung bleibt erhalten. Welche Werte
erscheinen, ist unverändert: Block ECKDATEN-CHIPS und Funktion `eckdatenChips` sind beibehalten.

**Nudge nur noch im Dialog.** Der Nudge erscheint nicht mehr im fertigen Plan:

- `webapp.py`: Die Abschlussnachricht an den Browser entsteht in der neuen Hilfsfunktion
  `ergebnis_nachricht` (Text, Abschlussmeldungen, Kartendaten) ohne Nudge; `index.html` enthält
  keinen Nudge-Bereich mehr.
- `chat.py`: keine Konsolenausgabe des Nudge nach Abschluss; im Sitzungsprotokoll
  (`reiseplan_erstellt`) bleibt er erhalten.
- `src/fragekatalog/agent_tools.py`: `plane_reise_und_abschliessen` nimmt den Nudge nicht mehr ins
  Werkzeugergebnis auf, damit das LLM ihn nach Abschluss nicht erneut aufgreift. Er bleibt in
  `state.nachhaltigkeits_nudge`.
- `src/pipeline.py`: Die Berechnung bleibt; nur der Kommentar beschreibt die neue Verwendung.

Im F13-Dialog (`vorschlaege.py`) erreicht der Nudge den Nutzer weiterhin vor seiner Entscheidung.

**Nudge-Formulierung (`src/optimierung/verkehrsmittelwahl.py`).** `nachhaltigkeits_nudge`
unterscheidet drei Fälle: Bahn langsamer („Die Bahn braucht nur X Minuten länger, spart aber …"),
gleich schnell („Die Bahn ist gleich schnell und spart …") und schneller („Die Bahn ist sogar X
Minuten schneller und spart …"). Der Bezug lautet „gegenüber der bestbewerteten Alternative
(Verkehrsmittel)", damit erkennbar ist, womit verglichen wird.

**Gesprächsverlauf nach Abschluss (`static/index.html`).** Der Verlauf bleibt standardmäßig
sichtbar und wird kompakt dargestellt (kleinere Schrift, kleinerer Avatar, keine Schnellantworten).
Ab 980 px Breite steht er als schmale Spalte (280–340 px, `position: sticky`) neben dem Plan und läuft
beim Scrollen mit; nur der Verlauf darin scrollt. Unter 980 px steht er unter dem Plan. Ein Kopf
„Gesprächsverlauf" enthält den Knopf „Einklappen"; eingeklappt holt ein schwebender Knopf „Chat
anzeigen" den Verlauf zurück (beide mit `aria-expanded`). Die Eingabezeile bleibt ausgeblendet
(Station 32). Escape klappt den Verlauf nicht mehr ein.

**Revision von Station 37.** Das dort eingeführte, standardmäßig eingeklappte Überlagerungs-Panel
mit dem Knopf „Chat"/„Chat schließen" ist ersetzt, ebenso die Chip-Optik der Eckdaten und der Nudge
zwischen Eckdaten und Zeitleiste.

**Nachtrag zu Station 36 (Routes API).** Im selben Live-Test wurde für Hannover → Unterkunft Hamburg
die FUEL_EFFICIENT-Route gewählt; die Antwortformate der Routes API sind damit bestätigt. Aufgedeckt
wurde dabei, dass die Routes API das Koordinatenpaar „lat,lng", mit dem die Pipeline die Unterkunft
übergibt, im Feld `address` mit HTTP 400 INVALID_ARGUMENT ablehnt. `_routes_api_wegpunkt` in
`src/api/google_maps.py` übergibt Koordinatenpaare seither als `location.latLng`, alle übrigen
Angaben weiter als Adresstext. Details in Station 36.

**Warum so.** Eine Angabe in Knopf-Optik suggeriert eine Interaktion oder Auswahl, die es nicht gibt.
Nach Abschluss ist die Verkehrsmittelwahl getroffen; ein Nudge an dieser Stelle kommt zu spät und war
im Live-Test zudem fehlerhaft formuliert. Der Nutzer soll seine Angaben im Gesprächsverlauf nachlesen
können, ohne ihn erst suchen zu müssen (Entscheidung des Product Owners).

**Verworfene Alternativen.**

- Den Chat weiter als eingeklapptes Überlagerungsfenster belassen.
- Den Nudge im Plan nur korrigieren statt entfernen.
- Die Nudge-Berechnung aus der Pipeline löschen; sie bleibt für das Sitzungsprotokoll.

## Verifikation

- Neue Tests: drei Nudge-Tests in `tests/test_verkehrsmittelwahl.py` (Bezugsgröße, schnellere Bahn
  ohne negative Minuten, gleiche Fahrzeit), je ein Test in `tests/test_agent_tools.py` (Nudge nicht
  im Werkzeugergebnis, aber im Zustand) und `tests/test_webapp.py` (`ergebnis_nachricht` und
  `index.html` ohne Nudge) sowie der Regressionstest
  `test_auto_route_koordinaten_als_latlng_statt_adresse` in `tests/test_google_maps.py`.
- Komplette Suite grün (461/461; 455 nach Station 38).
- JavaScript-Syntax mit `node --check` geprüft.
- Sichtprüfung im Headless-Chrome mit Mock-Daten bei 1280 und 1000 px sowie per iframe bei 390 und
  320 px: kein horizontales Scrollen.
- Nicht geprüft: ein echtes Mobilgerät und ein erneuter Live-Dialog mit diesen Änderungen.

## Offene Punkte

- Besteht der Reisezeitraum nur aus einer Dauer ohne Datum (Rohtext „5 Tage"), zeigt die
  Eckdatenzeile „5 Tage · 5 Tage": Zeitraum und Tagesanzahl erscheinen doppelt.
- Die Eckdatenzeile nennt bei unvollständigen Kosten weiterhin „(ohne Unterkunft)" (aus Station 38).
