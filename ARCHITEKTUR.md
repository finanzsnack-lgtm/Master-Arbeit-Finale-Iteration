# Architektur des Reisebot-Prototyps

Dieses Dokument beschreibt den aktuellen Stand der Architektur des Prototyps zur Masterarbeit
„Reiseplanung mit generativer KI: Entwicklung eines Software-Prototyps unter besonderer
Berücksichtigung der Anbindung von Simulations- und Optimierungsmodellen" (Wirtschaftsinformatik,
Universität Hildesheim). Die Entwicklung folgt Design Science Research nach Peffers et al. (2007).
Die Begründung jeder einzelnen Design-Entscheidung steht chronologisch in
[`ENTSCHEIDUNGSLOG.md`](ENTSCHEIDUNGSLOG.md) und nach Entwicklungsstationen sortiert in
[`doku/`](doku/README.md).

Begriffe: **Product Owner** bezeichnet den Autor der Arbeit in seiner Rolle als fachlich
Verantwortlicher für den Prototyp. **Nutzer** bezeichnet die Endnutzer des Reisebots.
**Demo-Feedback** bezeichnet die Rückmeldungen der beiden Testpersonen aus den Demonstrationen:
einer im HULLS-Projekt forschenden Person und des Betreuers der Arbeit.

## 1. Grundprinzipien

1. **Trennung von Dialog und Fakten.** Ein Large Language Model (LLM) führt den Dialog
   eigenverantwortlich und entscheidet selbst, welche Frage wann nötig ist. Es erstellt aber nie
   selbst die Reise oder Route und erfindet keine Fakten.
2. **Fakten nur aus realen APIs.** Points of Interest (POIs), Unterkünfte, Fahrzeiten und Preise
   stammen aus realen Schnittstellen.
3. **Deterministischer, regelbasierter Layer.** Alles objektiv Prüfbare bleibt regelbasiert: Werte
   werden gegen den erwarteten Typ validiert, echte Daten kommen ausschließlich aus den API-Modulen,
   und die Reiseplanung (Optimierung 1 und 2, Monte-Carlo-Härtetest) läuft deterministisch. Der
   Abschluss ist gesperrt, bis alle Pflichtfelder gesetzt sind.
4. **Rundreise nach UNWTO-Definition.** Hinreise, Aufenthalt mit POIs, Rückreise, mit genau einer
   Unterkunft.
5. **Keine Flüge.** Flüge sind im Sinne von Nachhaltigkeit und Slow Tourism vollständig
   ausgeschlossen. Nachhaltigkeit ist Querschnittsprinzip: Bahn-Nudging, CO₂ in der Zielfunktion,
   bevorzugt zertifizierte Unterkünfte.

## 2. Dialogsteuerung

Das LLM läuft in einer durchgehenden Agenten-Session (Claude Agent SDK, In-Process-MCP-Tools). Es
erhält den vollständigen Fragekatalog mit Kontexthinweisen und fünf Werkzeuge
(`src/fragekatalog/agent_tools.py`). Eine feste Fragereihenfolge von außen gibt es nicht. Die Regel
im Regelwerk-Text (`src/fragekatalog/regelwerk.py`) lautet: grundsätzlich jede Frage stellen und nur
überspringen, wenn aus dem Gespräch sicher hervorgeht, dass sie beantwortet oder gegenstandslos ist.

Das Gespräch beginnt mit einer festen Begrüßung (`BEGRUESSUNG` in `chat.py`, für Web und Konsole
gleich), die den Prototyp in Aussagen beschreibt, die im Code gedeckt sind, und mit der offenen
Frage nach dem Reisewunsch endet. Bereits gespeicherte Werte überschreibt das LLM durch einen
erneuten Aufruf von `speichere_feld`, wenn der Nutzer eine Angabe korrigiert. Das ist bewusst so
angelegt, damit Tippfehler im Chat korrigierbar bleiben; ungewollte Überarbeitungen sind dadurch
nicht deterministisch ausgeschlossen.

| Werkzeug | Aufgabe |
|---|---|
| `speichere_feld(feld, wert, ...)` | Validiert den Wert gegen den erwarteten Rückgabetyp und speichert ihn. Feldspezifische Argumente steuern deterministische Zusatzeffekte (siehe Abschnitt 3). |
| `hole_api_daten(feld, ...)` | Holt echte Daten für dialoggestützte Felder (Unterkunft, lokaler Fahrzeugverleih, Aktivitäten, Verkehrsmittel). |
| `fehlende_pflichtfelder()` | Deterministische Vollständigkeitsprüfung. |
| `plane_reise_und_abschliessen(barrierefreiheit_bereits_gepruft=False)` | Plant und versendet die Reise. Gesperrt, solange Pflichtfelder fehlen. Prüft den fertigen Plan gegen eine genannte Mobilitätsanforderung und plant nach Rückfrage beim Nutzer strenger neu. |
| `breche_planung_ab(grund)` | Beendet die Planung bei erkennbarem Abbruchwunsch. |

Zusätzlich steht dem LLM eine Websuche zur Verfügung. Sie ist eine bewusste, dokumentierte Ausnahme
von Grundprinzip 2 und dient nur der allgemeinen Hintergrundrecherche, etwa zu einer Region. Ein
Suchergebnis erreicht die Reiseplanung nie. POIs, Unterkünfte, Preise, Reisezeiten und
Verkehrsmittel kommen ausschließlich aus den API-Modulen.

## 3. Fragekatalog

Der Katalog umfasst sieben Stufen und 19 Fragen (F01–F20 ohne F18, davon zwei Metafragen) mit
bedingten Folgefragen. Das Rohmaterial enthielt 18 Fragen; im Projekt entfielen zwei als eigene
Frage („Reiseerlebnis", Phase 1; F18 in F09 integriert, Phase 55), drei kamen hinzu (F08 Wohnort,
F10 altersgerechte Bedürfnisse, F20 Tagesablauf; Begründung in Phase 82 des Entscheidungslogs). Die
Reihenfolge folgt der Planungshierarchie, Kern- vor Sekundärentscheidungen (Jeng & Fesenmaier 2002;
Choi et al. 2012). Der Katalog dient als Validierungsgrundlage mit Feldname, Rückgabetyp,
Pflichtstatus und Kontexthinweis, nicht als starre Sequenz.

Drei Fragetypen:
- **A, Kontextfrage:** wird nur aus dem Gesprächskontext beantwortet.
- **B, Wertfrage:** ein Wert wird extrahiert, validiert und gespeichert.
- **C, Dialogfrage:** API-gestützte Vorschläge in einer Schleife bis zur Zustimmung des Nutzers.
  Typ-C-Felder sind:
  - Unterkunft (F15): genau eine echte Unterkunft wird vorgeschlagen und bestätigt. Treffer
    außerhalb des Zielgebiets werden vorher deterministisch verworfen
    (`src/datenaufbereitung/lagepruefung.py`): Maßstab ist der Viewport aus dem Geocoding plus 5 km,
    mindestens 10 km um den Mittelpunkt, ohne Viewport 30 km. Bleibt nichts übrig, wird einmal ohne
    den Anforderungstext gesucht. Das LLM erhält Adresse und Luftlinien-Entfernung und nennt die Lage
    beim Vorschlag.
  - Lokaler Fahrzeugverleih (F14): nur bei erkanntem Leihwunsch, möglichst nah an der bestätigten
    Unterkunft.
  - Aktivitäten (F16): volle Kandidatenvorschau mit Vertiefungsfragen bei unklaren Aktivitäten.
  - Verkehrsmittel (F13): echte Alternativen mit Nachhaltigkeits-Nudge im Dialog.

Vom LLM beurteilte Felder (keine Schlüsselwort-Heuristik, Beurteilung aus dem gesamten
Gesprächskontext):
- **Sicherheit (F11):** Das Argument `sicherheit_bedenklich` steuert einen Sicherheitshinweis im
  Reiseplan. Bei erkennbar problematischem Ziel schlägt das LLM eine sicherere Alternativregion vor.
- **Mobilitätseinschränkung:** Das Argument `mobilitaetseinschraenkung_stufe` kennt drei Stufen.
  „leicht" passt nur Tempo, Pausen und Nähe in Optimierung 1 an. „mittel" schließt zusätzlich Orte
  aus, die explizit als nicht barrierefrei bestätigt sind. „stark" verlangt eine eindeutig bestätigte
  Barrierefreiheit. Datenquelle ist Googles Rollstuhl-Feld; Steigungs- oder Stufendaten gibt es nicht.
- **Flexibilität (F05):** Eine Skala von 1 (durchgeplant) bis 3 (sehr flexibel) steuert die Anzahl
  POIs pro Tag (3, 2 oder 1) und ab Stufe 2 Pufferpausen zwischen Besuchen. Bei gleichzeitiger
  Barrierefreiheitspause gilt das kürzere Intervall.
- **Reisezeitraum (F06):** Das LLM interpretiert die Antwort zu einem Start- und Enddatum im
  ISO-Format und fragt bei Mehrdeutigkeit nach. Die Tagesberechnung selbst ist reine
  Datumsarithmetik im regelbasierten Layer. Die Reisedauer bestimmt die Zahl der POI-Kandidaten
  (höchstens 10 für Optimierung 1).

Sonderbehandlung einzelner Interessen außerhalb von Optimierung 1:
- **Essen und Trinken:** Restaurants und Bars werden nicht als POI-Kandidaten eingeplant, sondern
  je Tag als Beispiele nahe der Unterkunft gezeigt, ohne feste Uhrzeit.
- **Geführte Touren und konkrete Lernaktivitäten (F04, F17):** Sie erhalten einen reservierten Tag
  mit drei Beispielen aus den acht nächstgelegenen Treffern, gestaffelt nach Barrierefreiheit. Eine
  Tour kann mehrere Tage umfassen, aber nur bei ausdrücklicher Aussage des Nutzers. Unkonkrete
  Lernwünsche erhalten eine allgemeine Empfehlung im Gespräch.
- **Lokaler Kontakt (F19):** An vollen Tagen erhält Optimierung 1 120 Minuten weniger Tagesbudget,
  damit ein Mittagsblock frei bleibt. Drei nahe Markt- oder Café-Beispiele werden je Tag angezeigt.
- **Feste Wunschorte:** Sagt der Nutzer ausdrücklich, dass er einen Ort unbedingt sehen möchte, setzt
  das LLM das Argument `feste_wunschorte` bei `speichere_feld` (nie proaktiv, immer die vollständige
  Liste). Der Ort wird über die Places Text Search aufgelöst (`finde_ort`), nicht gefundene Orte
  werden ehrlich gemeldet. Die Anfahrt ab der Unterkunft läuft zuerst über das lokale Verkehrsmittel
  (F14); über 60 Minuten einfache Strecke über die Reisealternativen gemäß F13-Präferenz, verbunden
  mit einem Hinweis auf Entfernung und geschätztes CO₂, nach dem der Nutzer über den Ort entscheidet.
  Der Ort wird als fester Termin einem vollen Tag zugeordnet und durchläuft Optimierung 1 nicht;
  diese plant nur das um Besuch und Wege gekürzte Tagesbudget. Mit genannter Uhrzeit schließt der
  Termin den Tag ab, sonst liegt er am Tagesende. Bei fehlender Barrierefreiheit erfolgt nur ein
  Hinweis, kein Ausschluss.

Weitere Festlegungen:
- Der Name (F01) ist eine freiwillige Angabe nur für die persönliche Ansprache; er wird gefragt,
  aber nicht erzwungen, und bei Verweigerung wird kein Platzhalter gespeichert.
- F09 fragt seit Phase 55 auch nach Unverträglichkeiten; die frühere Frage F18 ist darin
  aufgegangen. F04 (Reiseleitung) steht im Gespräch direkt vor F17.
- Mehrere genannte Zielregionen (F07) sind zulässig, geplant wird aber immer nur die erste. Das LLM
  weist darauf hin.

## 4. Optimierung 1: Vor-Ort-Planung

- **Problemklasse:** Team Orienteering Problem with Time Windows (TOPTW) als formale Modellierung des
  Tourist Trip Design Problem (Gavalas et al. 2014; Vansteenwegen et al. 2011).
- **Verfahren:** Iterated Local Search (ILS) nach Vansteenwegen et al. (2009) mit
  Greedy-Startlösung. Abbruch nach 70 Iterationen ohne Verbesserung. Ausgewählt wurde das Verfahren
  nach Komplexität der Integration und Nutzen zur Laufzeit; eine nachträglich erstellte
  Nutzwertanalyse dokumentiert die Bewertung. Die Umsetzung ist eine eigenständige
  Python-3-Implementierung, strukturell angelehnt an die Referenzimplementierung Constantino/TOPTW.
- **Eingabe je POI:** Koordinaten, Score, Besuchsdauer, Zeitfenster. Ort 0 ist die Unterkunft.
  Global: Zeitbudget je Tag und Tagesanzahl. Reservierte Tour- und Lernaktivitätstage, der
  Mittagsblock bei lokalem Kontakt und feste Wunschorte wirken nur über Tagesanzahl bzw. Zeitbudget;
  die zugehörigen Orte werden dem Verfahren nicht übergeben. Beim Zusammenführen der Places- und
  Overpass-Treffer erhalten alle Kandidaten fortlaufende, eindeutige ids (`sammle_pois`).
- **Reisezeiten:** echte Reisezeiten aus der Google Distance Matrix statt Luftlinie. Bei mehreren
  genannten Verkehrsmitteln gilt je Paar die schnellere Zeit. Das angezeigte Verkehrsmittel je
  Etappe wird erst nach der Optimierung und nur für tatsächlich besuchte Etappen abgefragt.
- **Scores:** Matching der POI-Kategorien gegen die Nutzerpräferenzen.
- **Nachvollziehbarkeit:** Jede Planung schreibt eine Debug-Datei mit Rohtreffern, gefilterten
  Kandidaten sowie Eingabe und Ergebnis von Optimierung 1 und Härtetest nach `protokolle/`.

## 5. Optimierung 2: An- und Abreise

- Kleiner Alternativenraum aus Bahn, Auto und Fernbus mit ihren Routen. Für das Auto wird die Route
  verwendet, die die Google Routes API als umweltfreundlichste kennzeichnet (FUEL_EFFICIENT, in
  Google Maps mit grünem Blatt); fehlt diese Kennzeichnung, die Standardroute mit sichtbarem Vermerk
  im Feld `umweltfreundlichste_route`.
- Gewichtete Bewertung über Zeit, Kosten und CO₂, standardmäßig zu gleichen Teilen.
- CO₂ = Distanz × Emissionsfaktor. Hinterlegt sind 19 g/Pkm für Bahn, 168 g/Pkm für Auto und
  32 g/Pkm für Fernbus. Diese Werte sind Faustwerte und nicht gegen eine amtliche Quelle
  verifiziert; der Product Owner hat entschieden, sie beizubehalten.
- Die Summe aus Hin- und Rückreise wird im Reiseplan in drei Stufen eingeordnet (`co2_einstufung`):
  genügsam bis 50 kg, mittel bis 150 kg, darüber CO₂-lastig. Die Schwellen sind eine vorläufige
  Setzung des Product Owners ohne Literaturbeleg; eingestuft wird der angezeigte, gerundete Wert.
- Nachhaltigkeits-Nudge nur im Dialog zur Verkehrsmittelwahl (F13), etwa: „Die Bahn braucht nur
  Δt länger, spart aber X kg CO₂ gegenüber der bestbewerteten Alternative (Auto)." Verglichen wird
  mit dem besten Gesamtwert aus Zeit, Kosten und CO₂; ist die Bahn gleich schnell oder schneller,
  lautet der Text entsprechend. Im fertigen Reiseplan erscheint der Nudge nicht, weil die Wahl dann
  bereits getroffen ist; er wird nur im Sitzungsprotokoll festgehalten.

## 6. Simulation: Monte-Carlo-Härtetest

- Geprüft werden die Umstiege der Hin- und Rückreise mit Bahn oder Fernbus, nicht die Vor-Ort-Route.
- Die Teilstrecken-Kette aus Google Directions wird 1000-mal mit log-normal gestreuten Fahrzeiten
  (20 % Streuung) simuliert. Verpasst ein Lauf an einem Umstieg den Puffer, gilt der ganze Lauf als
  gescheitert. Ersatzverbindungen werden nicht modelliert.
- Robust ist eine Verbindung, wenn mindestens 80 % der Läufe ohne verpassten Anschluss bleiben.
- Bei Auto gibt es keine Umstiege und daher keinen Härtetest.
- Das Ergebnis wird im Reiseplan angezeigt. Eine automatische Neuplanung mit Puffern bei „nicht
  robust" ist nicht umgesetzt (siehe Offene Punkte im Entscheidungslog).

## 7. Kostenschätzung

Die Gesamtkosten pro Person werden informativ geschätzt: An- und Abreise, Unterkunft und Aktivitäten
aus Googles Preisniveau 0 bis 4, dazu eine Verpflegungspauschale je Tag. Feste Termine gehen mit
ihrem Preisniveau und den Kosten für Hin- und Rückweg ein. Die Schätzung wird mit dem
genannten Budget verglichen, beeinflusst aber nicht die Auswahl in Optimierung 1.

## 8. Oberfläche

Es gibt zwei Einstiegspunkte mit derselben Dialoglogik: `chat.py` für die Konsole und `webapp.py`
(FastAPI mit WebSocket) für den Browser.

- **Titelzeile:** „Masterarbeit Prototyp Nick Poeppler" ohne Untertitel; der Tab-Titel lautet
  „Reisebot".
- **Layout während des Gesprächs:** Ab 980 px Breite nimmt der Chat etwa 60 % der Breite in fast
  voller Fensterhöhe ein; daneben steht eine Galerie mit wechselnden, lokal ausgelieferten
  Stimmungsbildern (`static/img/galerie/`, Herkunft in `QUELLEN.md`) ohne Bezug zum geplanten
  Reiseziel. Jedes Bild trägt unten das Motiv laut `QUELLEN.md` und den Bildnachweis. Bei reduzierter Bewegung bleibt ein Standbild. Auf schmalen
  Bildschirmen erscheint ein schmales Bildband über dem Chat.
- **Layout nach Abschluss:** Die Galerie verschwindet, der Reiseplan wird zum Hauptinhalt. Der
  Gesprächsverlauf bleibt standardmäßig sichtbar und kompakt, damit der Nutzer seine Angaben
  nachlesen kann: ab 980 px als schmale, mitlaufende Spalte neben dem Plan, darunter unter dem Plan.
  Er lässt sich einklappen und über einen schwebenden Knopf „Chat anzeigen" zurückholen; eine
  Eingabe ist nicht mehr möglich.
- **Titelbereich des Reiseplans:** „Deine Reise nach {Zielort}" mit Titelbild (Foto der Unterkunft
  oder des ersten POI, sonst ein Farbverlauf), darunter eine nicht-interaktive Eckdatenzeile ohne
  Knopf-Optik mit Zeitraum, Tagen, Verkehrsmittel, CO₂ der An- und Abreise und Kosten pro Person.
  Auf den CO₂-Wert folgt dessen Einordnung als Wort mit kleinem Farbpunkt und einem Tooltip zu den
  Schwellen; die Farbe ist nie alleiniger Bedeutungsträger. Die Werte stammen aus `als_kartendaten`
  (`eckdaten`, `titelbild_url`); fehlt ein Wert, entfällt die Angabe.
- **Reiseplan-Karten:** Hinreise, Unterkunft, Verleih, die Tage als vertikale Zeitleiste mit
  markierten Vorschlägen, weitere Empfehlungen und Rückreise, jeweils mit Foto, Kurzbeschreibung und
  Google-Maps-Link. Die Gestaltungselemente sind an etablierten Reiseportalen orientiert; die
  Zuordnung Element, Vorbild und Quelle steht in Phase 66 des Entscheidungslogs. Ein fester Termin
  erscheint als eigene, durchgehend blau gerahmte Karte „Fester Termin – dein ausdrücklicher Wunsch"
  nach der optimierten Route des Tages und ist damit von den Vorschlägen unterschieden. Unter
  „Weitere Empfehlungen" erscheint kein Ort, der im Plan bereits an anderer Stelle steht; Text-,
  Mail- und Web-Ausgabe nutzen dieselbe bereinigte Liste.
  Fotos werden erst nach Planungsabschluss serverseitig geladen; der API-Schlüssel erreicht den
  Browser nie. Einzige Karte während des Gesprächs ist die Vorschau der vorgeschlagenen Unterkunft.
- **Schnellantworten:** Das LLM kann Antwortoptionen als Klick-Chips anbieten. Das ist eine reine
  Konvention im Regelwerk, kein zusätzliches Werkzeug. Das Textfeld bleibt immer nutzbar. Die
  Schnellantworten-Zeile ist laut Regelwerk immer die letzte Zeile; eine Quellenliste nach einer
  Websuche ist untersagt, die Kennzeichnung als Recherche erfolgt im Fließtext.
- **Textformatierung:** Bot-Nachrichten dürfen nur **fett** und einfache „- "-Aufzählungen
  enthalten. Der Browser wandelt diese sowie http/https-Links nach vollständigem HTML-Escaping in
  eigene Tags um; Nutzer- und Statusnachrichten bleiben reiner Text. Konsole und Sprachausgabe
  entfernen die Auszeichnung (`entferne_markdown`).
- **Ladeindikator:** eine Tipp-Animation nach jeder Eingabe und ein eigener Hinweis während der
  Routenberechnung.
- **Zeitangaben:** Ohne bekannte Uhrzeit erscheinen relative Angaben wie „15min nach Ankunft" statt
  einer angenommenen Uhrzeit.
- Ein Bot-Avatar kennzeichnet die Nachrichten des Systems.
- **Mehrere Sitzungen gleichzeitig:** Jede WebSocket-Verbindung erhält eine eigene Sitzung mit
  eigenem Zustand, Maps-Client und Protokoll. Blockierende Werkzeuge, die Planung und die
  Foto-Downloads laufen per `asyncio.to_thread` in Hintergrund-Threads, damit eine Planung die
  übrigen Sitzungen nicht anhält. Eine Sperre je Sitzung führt deren Werkzeuge nacheinander aus.
- **Freigabe für externe Testpersonen:** `starte_extern.bat` startet die Webapp lokal und öffnet
  einen Cloudflare Quick Tunnel (HTTPS, ohne Konto). Testpersonen erhalten einen einzigen Link mit
  Zugangstoken (`/?zugang=…`); die Webapp merkt sich den Zugang in einem Cookie und entfernt das
  Token aus der Adresse. Ist ein Token konfiguriert, sind Startseite, WebSocket, Fotos und
  API-Dokumentation nur damit erreichbar, weil jedes Gespräch Kosten verursacht. Ohne Token bleibt
  der lokale Betrieb unverändert.

## 9. Schnittstellen und Dienste

| Dienst | Verwendung |
|---|---|
| Google Maps Platform | Places (inkl. Text Search für feste Wunschorte), Distance Matrix, Directions (Bahn und Fernbus), Routes API `computeRoutes` (Auto An- und Abreise, FUEL_EFFICIENT), Geocoding (inkl. Viewport für die Lageprüfung der Unterkunft, je Sitzung zwischengespeichert), Place Photos. Hauptquelle aller Fakten. |
| OpenStreetMap Overpass API | Nur für Aktivitäten, die Places nicht abdeckt (Klettern, Wandern mit Schwierigkeitsgrad, Ski, Tauchen, Mountainbike), und nur, wenn das LLM dies im Gespräch für nötig hält. |
| Mailjet Send API | Versand des Reiseplans als HTML-Mail. |
| Google Cloud Text-to-Speech / Speech-to-Text | Optionale Sprachein- und -ausgabe in der Konsole. |
| Claude Agent SDK | LLM für die Dialogsteuerung. |
| Cloudflare Quick Tunnel (`cloudflared`) | Optional: öffentlicher HTTPS-Link auf die lokal laufende Web-Oberfläche für externe Testpersonen (`starte_extern.py`). |

Schlüssel liegen in einer `.env`-Datei und nie im Code. Ohne Schlüssel läuft der Prototyp im
Mock-Modus mit Beispieldaten.

## 10. Bekannte Einschränkungen

Die vollständige, gepflegte Liste steht im Abschnitt „Offene Punkte" am Ende von
[`ENTSCHEIDUNGSLOG.md`](ENTSCHEIDUNGSLOG.md).
