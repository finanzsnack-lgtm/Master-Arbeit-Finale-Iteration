# Entscheidungslog — Reisebot-Prototyp

Dieses Dokument hält die Entwicklung des Prototyps nachvollziehbar fest: **was** wann gebaut oder
geändert wurde und **warum**, einschließlich verworfener Alternativen. Es ergänzt
[`ARCHITEKTUR.md`](ARCHITEKTUR.md), die den jeweils aktuellen Stand beschreibt, um die Entscheidungen,
die während der Implementierung anfielen. Die meisten wurden durch Live-Tests ausgelöst, in denen
sich Annahmen aus der Konzeption als lückenhaft erwiesen.

Die Entwicklung folgt Design Science Research nach Peffers et al. (2007). **Product Owner**
bezeichnet den Autor der Arbeit in seiner Rolle als fachlich Verantwortlicher, **Betreuer** die
Betreuenden der Arbeit, **Nutzer** die Endnutzer des Reisebots. **Demo-Feedback** bezeichnet die
Rückmeldungen der beiden Testpersonen, die den Prototyp in den Demonstrationen der Iterationen
getestet haben: einer im HULLS-Projekt forschenden Person und des Betreuers der Arbeit. Einträge sind chronologisch; spätere
Phasen können frühere Entscheidungen revidieren und verweisen dann darauf. Dieselben Entscheidungen
sind in [`doku/`](doku/README.md) nach Entwicklungsstationen sortiert.

---

## Phase 0 — Konzeption (vor 03.08.2026)

Die grundlegenden Architekturentscheidungen stammen aus der Konzeptionsphase und sind in
`ARCHITEKTUR.md` beschrieben: Design Science Research (Peffers et al. 2007), Stufenlogik des
Fragekatalogs (Jeng & Fesenmaier 2002; Choi et al. 2012), TOPTW/ILS (Vansteenwegen et al. 2009,
2011; Gavalas et al. 2014).

## Phase 1 — Grundgerüst und Erstimplementierung (03.–06.08.2026)

- **Modulstruktur nach Architekturschichten** (`src/api`, `src/fragekatalog`,
  `src/datenaufbereitung`, `src/optimierung`, `src/ausgabe`, `src/audio`). *Warum:* spiegelt die
  Lanes des Prozessmodells; API-Zugriff, regelbasierte Anwendung und Optimierung bleiben einzeln
  testbar und austauschbar (Mock- und Echt-Client je Schicht).
- **Fragekatalog (`katalog.py`) aus dem Rohmaterial konsolidiert**, Korrekturen transparent
  dokumentiert: F08 (`wohnort`) ergänzt, weil Optimierung 2 einen Startort braucht, den das
  Rohmaterial nicht erfasste; die Frage „Welches Reiseerlebnis streben Sie an?" entfernt, weil sie
  sich mit dem freien Einstieg überschnitt und Nutzer dieselbe Antwort zweimal gaben. *Warum
  dokumentiert:* Nachvollziehbarkeit der Herleitung des finalen Fragekatalogs.
- **Zwei Interpreter** (`RegelbasierterInterpreter` für Tests, `ClaudeAntwortInterpreter` über das
  Claude Agent SDK für den echten Dialog). *Warum:* automatisierte Tests dürfen nicht von einem
  externen LLM-Aufruf abhängen (Kosten, Nichtdeterminismus, Netzabhängigkeit).
- **Claude Agent SDK statt eigenem `ANTHROPIC_API_KEY`.** *Warum:* nutzt die bestehende
  Claude-Code-Anmeldung, kein zusätzlich abzurechnender Schlüssel.
- **TOPTW/ILS als eigenständige Python-3-Implementierung**, kein Direkt-Port von
  `github.com/Constantino/TOPTW`. *Warum:* die Referenzdatei lag nicht vor; die Umsetzung folgt deren
  dokumentierter Struktur (Greedy-Start, ILS mit `NoImprovementCounter`, `shake(R,S)`). *Offen:*
  Abgleich mit der Referenzimplementierung.
- **Monte-Carlo-Härtetest** mit vorläufigen Defaults: 20 % Lognormal-Streuung, 1000 Läufe,
  95 %-Schwelle. *Warum vorläufig:* begründeter erster Vorschlag, noch nicht mit dem Product Owner
  abgestimmt.
- **CO₂-Faktoren als feste Tabelle (`emissionsfaktoren.py`) statt Live-API** (z. B. Climatiq).
  *Warum:* stabile, zitierfähige Werte sind wichtiger als Aktualität; eine Live-API wäre ein
  weiterer Ausfallpunkt. *Offen:* Faustwerte (Bahn 19 g/Pkm u. a.) nicht amtlich verifiziert.
- **Ein-/Ausgabe als Protokoll-Abstraktion** (`IOKanal`, Text- und Audio-Implementierung, Anbieter
  `google_cloud` oder `lokal` über Whisper und pyttsx3). *Warum:* der Dialogablauf muss den
  Unterschied zwischen Tastatur und Sprache nicht kennen; die lokale Variante kommt ohne weiteren
  Schlüssel aus.
- **Protokollierung (`protokoll.py`):** jeder LLM-Aufruf und jeder Sitzungsmeilenstein wird je
  Sitzung als JSONL unter `protokolle/` geschrieben, nicht eingecheckt. *Warum:* Reproduzierbarkeit
  für die Fehleranalyse; die Dateien enthalten personenbezogene Testdaten.
- **Amadeus-Anbindung als eng begrenzte Ausnahme** vom Flugausschluss: Flugsuche nur, wenn der Nutzer
  nach einem Alternativziel-Vorschlag ausdrücklich auf einem mit Bahn oder Auto nicht sinnvoll
  erreichbaren Ziel besteht; zusätzlich All-Inclusive-Hotelsuche nur auf ausdrücklichen Wunsch.
  Flughafencodes und Hotelausstattung werden über Referenzdaten bzw. Abfragen bestimmt, nicht
  erfunden. *Status:* nie live getestet; im Zeitraum von Phase 4 durch FlightAPI.io und Hotelbeds
  ersetzt, Flug- und All-Inclusive-Suche in Phase 32 vollständig entfernt.

## Phase 2 — Nachbesserungen nach dem ersten Live-Test (05.08.2026)

Auslöser: das erste Testgespräch mit echtem Google-Maps-Schlüssel.

- **POI-Suche fand nur „Attraktionen".** *Ursache:* `suche_pois` fragte je Aufruf nur einen Place
  Type ab, unbekannte Formulierungen fielen auf `tourist_attraction` zurück. *Fix:* Schlüsselwort-
  Teilstringsuche (`_KATEGORIE_ALIASE`), die mehrere Kategorien treffen kann; Restaurant, Bar und
  Spa werden zusätzlich immer gesucht. (In Phase 15 durch Freitextsuche ersetzt.)
- **Mailversand war nur Platzhalter.** *Fix:* Anbindung an die Mailjet Send API v3.1 mit HTML-Mail
  und klickbaren Google-Maps-Links; dafür wird `place_id` bis in `Unterkunft`, `POI` und `Reiseplan`
  durchgereicht. *Warum HTML:* Anforderung des Product Owners, Vorschläge direkt anklicken zu können.
- **Ortsnamen in fremder Sprache** (Litauisch, Arabisch, Russisch). *Fix:* `language=de` bei jeder
  Places-Anfrage.
- **Aktivitäten wurden nicht vertieft** („Klettern" galt ohne Schwierigkeitsgrad als vollständig).
  *Fix:* erweiterter `kontext_hinweis` für F16; das LLM hakt bei Aktivitäten wie Klettern,
  Wassersport oder Ski gezielt nach, ohne neue Ablauflogik.
- **OpenStreetMap Overpass als Zusatzquelle** für Aktivitäten, die Places nicht abdeckt (Klettern,
  Wandern mit `sac_scale`, Ski mit `piste:difficulty`, Tauchen). *Warum Overpass:* eine kostenlose,
  schlüsselfreie Quelle, die genau diese Aktivitäten strukturiert taggt, statt vieler kommerzieller
  Einzelanbindungen. *Leitplanke:* OB Overpass befragt wird, entscheidet das LLM im Dialog; der Abruf
  selbst ist deterministischer Code (Grundprinzip 1). Behoben: Overpass lehnt den Standard-User-Agent
  ab (eigener gesetzt); Schwierigkeitsgrad-Tags sind uneinheitlich benannt (mehrere Kandidaten
  werden geprüft).
- **POI-Scoring traf nie.** `berechne_poi_score` verglich deutsche Präferenzen („Kultur") per
  Teilstring mit englischen Place Types („museum"); alle POIs erhielten denselben Score. *Fix:*
  zentrale Alias-Auflösung (`alias_place_types_fuer`); live verifiziert.
- **Vergleichende Präferenzfrage statt Einzelbewertung.** Bei zu vielen Treffern fragt das LLM
  „eher X oder eher Y?" über die genannten Kategorien. *Verworfen:* eine Bewertungsfrage je POI
  (skaliert nicht bei bis zu 30 POIs, im Sprachmodus unzumutbar). *Warum:* geringer Dialogaufwand,
  nur bei tatsächlich zu vielen Treffern.

## Phase 3 — Konfigurationsabgleich (08.08.2026)

- **`.env` unvollständig gegenüber `.env.example`** (`LLM_MODELL`, `AUDIO_ANBIETER`, Speech- und
  Amadeus-Schlüssel fehlten und liefen unbemerkt über Code-Defaults). *Fix:* `.env` angeglichen,
  damit alle Werte sichtbar und einstellbar sind. Tests grün (122/122).

## Phase 4 — Zeitraum 08.–10.08.2026 (nicht einzeln dokumentiert)

Mehrere Entscheidungen aus diesem Zeitraum sind nicht als eigene Einträge festgehalten; ihre
Begründung steht in den Docstrings der betroffenen Module: Korrekturschleife für nachträglich
geänderte Antworten, Anfahrtsempfehlung je Aktivität, Tagesbudget an Tag 1 ab tatsächlicher
Ankunftszeit, vom lokalen Verkehrsmittel abhängiger Suchradius und Geschwindigkeit, Migration der
Flug- und Hotelsuche von Amadeus (Self-Service-Portal am 17.07.2026 eingestellt) auf FlightAPI.io und
Hotelbeds, Score-Fix gegen branchenfremde Zufallstreffer (Fitnessstudio, Spa, Physiotherapeut).

## Phase 5 — Grobe Struktur statt fertiger Plan, harte Einschränkungsprüfung (10.08.2026)

- **Ausgabe als „grobe Struktur mit Empfehlungen".** Optimierung 1 bleibt unverändert und liefert je
  Tag genau eine realisierbare Route. Neu: nicht eingeplante Kandidaten erscheinen als
  `Reiseplan.weitere_aktivitaeten_empfehlungen`; Formulierungen wechseln zu „Tag X – unser
  Vorschlag". *Warum:* Entscheidung des Product Owners, dass Nutzer aus Empfehlungen selbst wählen
  statt eine starre Buchung zu erhalten. *Verworfen:* reine Tagesgruppierung ohne feste Reihenfolge,
  weil sie Optimierung 1 als Kernbeitrag der Arbeit abgeschwächt hätte.
- **Neues Modul `vertraeglichkeit.py`: harte Ausschlüsse getrennt von der weichen Gewichtung.**
  Kandidaten werden nach der Suche und vor dem Scoring gegen zwei harte Einschränkungen geprüft:
  Ernährung/Allergien (Schlüsselwort-Heuristik gegen den Namen, da keine API Zutaten liefert) und
  Barrierefreiheit (`ReiseAnfrage.barrierefreiheit_wichtig()`, geprüft über Googles
  `wheelchair_accessible_entrance` per Place Details, nur bei genanntem Bedarf). Ausgeschlossen wird
  nur, wenn eine unbedenkliche Alternative derselben Kategorie bleibt; sonst bleibt der Treffer mit
  Warnhinweis (`Reiseplan.einschraenkungshinweise`). *Warum:* Anforderung des Product Owners, dass
  etwa eine Fischallergie ein Fischrestaurant tatsächlich ausschließt, ebenso für Barrierefreiheit.
  Vorher floss die Ernährungsangabe nur als Suchbegriff ein.

## Phase 6 — Wiederverwendbare Testfälle für main.py (10.08.2026)

- **`testfaelle/*.json` statt einer fest programmierten Antwortliste.** Jede Datei ordnet
  Katalog-Feldnamen Rohantworten zu; `python main.py <name>` lädt sie und speichert die Ausgabe
  unter dem Testfallnamen. *Warum:* verschiedene Antwortkombinationen ohne erneute Eingabe aller
  Fragen durchspielen. Feldname statt Position, damit eine Umsortierung des Katalogs Testfälle nicht
  unbemerkt verfälscht.
- **main.py nutzt immer den Mock-Client.** *Warum:* mit echtem Schlüssel in der `.env` hätte main.py
  seine Rolle als schneller, kostenloser Testfall-Runner verloren. (In Phase 9 revidiert.)

## Phase 7 — Lokaler Fahrzeugwechsel und Verleihsuche (10.08.2026)

- **F14 hakt gezielt nach, wenn vor Ort ein anderes Fahrzeug als bei der Anreise gewünscht ist**
  (z. B. Anreise mit Bahn, vor Ort Auto oder Fahrrad), und sucht bei bestätigtem Leihwunsch einen
  echten Verleih. Die Suche ist deterministisch (`erkenne_leihwunsch`, Place Types `car_rental` und
  `bicycle_store`); Fund oder ehrliche Fehlanzeige landen im Reiseplan. *Warum:* Anforderung des
  Product Owners, einen Fahrzeugwechsel nur dann zu erfragen und einen Leihwunsch real zu prüfen.
  *Einschränkung:* Places kennt keinen Typ „Fahrradverleih", nur „bicycle_store"; die Ausgabe
  benennt das ehrlich.

## Reflektierte, nicht umgesetzte Idee (10.08.2026)

- Verkehrsmittelempfehlung je Etappe auch innerhalb von Optimierung 1. Zwei Bausteine wären
  vorhanden, aber nicht verbunden: `_anfahrtsempfehlung_je_poi` berechnet echte Zeiten je
  Verkehrsmittel, erscheint aber nur im Chat; `TOPTWInstanz.geschwindigkeit_kmh` ist eine globale
  Geschwindigkeit statt einer Zeit je Etappe. Der zweite Punkt wäre ein größerer Eingriff in toptw.py.
  Nur als Idee festgehalten (teilweise umgesetzt in Phase 36).

## Phase 8 — Diagnose leerer Tagesrouten in main.py (10.08.2026)

Der Testfall `standard` lieferte an jedem Tag „kein Programm eingeplant". Zwei Ursachen:
1. Der Mock-Interpreter trennt Mehrfachantworten nur an Kommas; eine Antwort ohne Kommas wurde ein
   einziger Präferenzstring. *Fix:* Testfall in kommagetrennte Form gebracht. Der echte Dialog nutzt
   das LLM zur Extraktion und ist nicht betroffen.
2. Mock-POIs tragen deutsche Sammelkategorien („kultur", „natur", „kulinarik"), die
   Alias-Auflösung erwartet englische Place Types. Klettern und Wandern erscheinen im Mock-Pfad nie,
   weil die Overpass-Aktivierung dem LLM vorbehalten ist. *Fix:* Testfall auf die vom Mock-Modus
   verstandenen Begriffe umgestellt. *Verworfen:* Umbenennung der Mock-Kategorien, weil mehrere
   bestehende Tests genau diese Namen prüfen.

## Phase 9 — main.py mit echtem, skriptgesteuertem Ablauf (10.08.2026)

- **Revidiert Phase 6:** Entscheidung des Product Owners, dass main.py als Demo- und
  Testfall-Runner realistische Ergebnisse liefern soll statt Mock-Daten. Die pytest-Suite bleibt
  bewusst gemockt (schnell, kostenlos, deterministisch).
- **Umsetzung:** main.py dupliziert die Dialoglogik nicht mehr, sondern ruft
  `chat.py::hauptablauf()` mit einem neuen `SkriptKanal` auf, der vorbereitete Antworten der Reihe
  nach liefert. Der Ablauf ist damit identisch zu einer echten Sitzung (echtes LLM, echte Clients).
  *Warum:* keine zweite, potenziell abweichende Implementierung des Dialogablaufs pflegen.
- **Testfall-Format:** geordnete Antwortliste statt Feld-zu-Text-Zuordnung. *Warum:* der
  LLM-geführte Dialog stellt Rückfragen, überspringt kontextabhängig Fragen und braucht bei Typ-C-
  Fragen Zustimmungsrunden. *Kompromiss:* die Zuordnung Antwort zu Frage ist nicht mehr garantiert;
  läuft das Skript vorzeitig aus, bricht `SkriptKanal` mit klarer Fehlermeldung ab.

## Phase 10 — Architekturwechsel: LLM-autonome Dialogsteuerung (11.08.2026)

- **Was:** Die feste Python-Zustandsmaschine (`zustandsmaschine.py`), die den Katalog strikt der
  Reihe nach abarbeitete und das LLM je Schritt mit erzwungenem JSON-Schema aufrief, wurde entfernt.
  An ihre Stelle trat eine durchgehende Agenten-Session: das LLM erhält den vollständigen
  Fragekatalog und fünf Werkzeuge (`speichere_feld`, `hole_api_daten`, `fehlende_pflichtfelder`,
  `plane_reise_und_abschliessen`, `breche_planung_ab`; neues Modul `agent_tools.py`,
  In-Process-MCP-Tools des Claude Agent SDK) und entscheidet selbst, welche Frage wann gestellt oder
  übersprungen wird. `zustandsmaschine.py` und `llm_interpreter.py` wurden gelöscht; die Fachlogik
  (API-Aufrufe, Optimierung, Sonderfälle) blieb unverändert in `vorschlaege.py`, `pipeline.py` und
  `reiseplan.py`, ersetzt wurde nur die Orchestrierung. Auch der regelbasierte Mock-Interpreter
  entfiel, da Ablaufentscheidungen jetzt Aufgabe des LLM sind. Deterministisch bleibt, was sich
  objektiv prüfen lässt: Typvalidierung, Vollständigkeitsprüfung und die harte Abschlusssperre
  (neue `tests/test_agent_tools.py`, 17 Tests).
- **Warum:** Entscheidung des Product Owners: das LLM erhält alle Werkzeuge, Fragen und Regeln und
  führt das Gespräch ohne Zwischeninstanz im Code; im Zweifel wird gefragt, bei sicherem Ausschluss
  nicht. Vor der Umsetzung wurde festgehalten, dass dies den bis dahin geltenden Grundprinzipien 1
  und 3 sowie der kostenlosen, deterministischen Ende-zu-Ende-Testbarkeit widerspricht. *Verworfene
  Alternative:* nur die bestehende Überspring-Logik verallgemeinern, Kontrollfluss bleibt
  regelbasiert. *Akzeptierter Kompromiss:* Gesprächsverhalten ist nicht mehr per pytest testbar,
  Testfälle laufen gegen die kostenpflichtige LLM-Session. Die Grundprinzipien wurden entsprechend
  präzisiert (Ablaufsteuerung beim LLM, Fakten- und Routenerzeugung nie).
- **Verifikation:** zwei vollständige Live-Läufe (echtes LLM, echte Google-Maps-API, rund 25–30
  Gesprächsrunden) zeigten echte Werkzeugaufrufe mit echten Daten, Ablehnung unpassender
  Sehenswürdigkeiten als Kletter- oder Wandertreffer, Nachhaken bei zu vielen Treffern statt stillem
  Kappen und eine korrekt ausgelöste F14-Fahrzeugwechsel-Nachfrage (Phase 7). Ein dritter, kurzer
  Lauf bestätigte `plane_reise_und_abschliessen` mit Optimierung 1 und 2 und Härtetest; ein fehlender
  Mailjet-Schlüssel wurde ehrlich als Fehlschlag gemeldet. Kein `speichere_feld`-Aufruf scheiterte an
  der Typvalidierung.
- **Nebenbefund:** Der Warnhinweis bei zu vielen Rohtreffern kann „30 von 15" anzeigen, wenn die
  Obergrenze größer als die Trefferzahl ist. Reine Formulierung, keine Datenauswirkung (siehe Offene
  Punkte).

## Phase 11 — Nachbesserungen nach dem ersten Live-Test der neuen Architektur (11.08.2026)

Auslöser: ein Testlauf mit einer hypothetischen Reise nach Innsbruck direkt nach Phase 10.

- **Fehler behoben: Restaurants und Cafés wurden nie gesucht.** Die POI-Vorschau las
  `anfrage.aktivitaeten_interessen`, das beim ersten Durchlauf einer Typ-C-Frage noch leer ist; die
  Suche fiel auf „tourist_attraction" zurück. *Fix:* neuer Parameter `aktivitaeten_aktuell`, über den
  das LLM die vollständige, noch unbestätigte Interessenliste übergibt.
- **Fehler behoben: ein bestätigtes Verkehrsmittel wurde von Optimierung 2 überstimmt.** Optimierung
  2 wählte immer die objektiv beste Alternative und begünstigte durch die CO₂-Gewichtung strukturell
  die Bahn, auch wenn der Nutzer „Auto" bestätigt hatte. *Fix:* `_nur_bestaetigte_verkehrsmittel`,
  bewertet wird nur noch innerhalb der bestätigten Auswahl (Fallback auf alle bei unklarem Freitext).
- **Aufräumen nach dem Architekturwechsel:** verwaiste Strukturen entfernt (`FrageZustand`,
  `Protokollierer.llm_aufruf`, toter Zweig in `baue_regelwerk_text`), Verweise auf gelöschte Module
  korrigiert. Dabei zwei echte Lücken gefunden: `aktivitaeten_mit_spezialrecherche` und
  `aktivitaeten_gewichtung` wurden nie gespeichert und erreichten die finale Planung nicht; beide
  sind jetzt Argumente von `speichere_feld`.
- **Neu: F20 `tagesstart_praeferenz`** (nicht aus dem Rohmaterial, analog F08/F10): grobe Start- und
  Enduhrzeit eines Reisetags. (1) `wende_tageszeitfenster_an` hebt die Öffnungszeit je Place Type auf
  eine Mindest-Tageszeit relativ zum Tagesbeginn an, z. B. Bar erst ab acht Stunden nach Tagesbeginn;
  eine dokumentierte Modellannahme, keine erfundene Tatsache. (2) Ab Tag 2 werden echte Uhrzeiten
  gezeigt, aber nur, wenn F20 beantwortet wurde; Tag 1 bleibt relativ, weil die Ankunftszeit nicht
  real feststeht.
- **Neu: POI-Übersicht als CSV** (`speichere_poi_uebersicht`): eine Zeile je Kandidat mit Score,
  Zeitfenster, Besuchsdauer, Quelle und Einplanungsstatus. *Warum:* Anforderung des Product Owners,
  die Funktionsweise von Optimierung 1 an allen Kandidaten nachprüfen zu können.

## Phase 12 — Aufräumen des Projektverzeichnisses (11.08.2026)

- **Was:** Erzeugte Reisepläne liegen gesammelt in `ergebnisse/` statt lose im Wurzelverzeichnis
  (`_ERGEBNISSE_VERZEICHNIS` in `agent_tools.py`); `.gitignore` vereinfacht; neue `README.md` mit
  Verzeichnisübersicht. *Warum:* Laufzeitausgaben neben dem Quellcode erschwerten die
  Nachvollziehbarkeit; `src/` selbst war bereits nach Schichten gegliedert.

## Phase 13 — Echte Bahn-Umstiegsdaten statt nur Gesamtdauer (12.08.2026)

- **Was:** `_hole_route` las nur Gesamtdauer und -distanz; die Einzelschritte der Directions-Antwort
  (Linie, Umstiegshalte, Zeitstempel) wurden verworfen. Neuer Typ `Teilstrecke` und
  `_teilstrecken_aus_steps` werten sie jetzt aus. Die Wartezeit beim Umstieg ergibt sich aus den
  Zeitstempeln zweier aufeinanderfolgender Transit-Schritte, nur wenn Google beide liefert (sonst
  `None`, Grundprinzip 1). Text und HTML-Mail zeigen die Umstiegskette. *Während der Umsetzung
  gefunden:* bei `mode=driving` liefert Google Abbiegeschritte statt Umstiege; Teilstrecken werden
  daher nur für `mode=transit` gebaut.
- **Warum:** Anforderung des Product Owners, statt einer Gesamtdauer die einzelnen Teilstrecken mit
  Umstiegen und Wartezeiten zu zeigen, damit eine Bahnverbindung bewertbar wird.
- **Verifikation:** live gegen die Directions-API (Berlin Hbf → München Hbf; simulierte
  Fernbusroute mit drei Umstiegen). 4 neue Tests, Suite 186/186 grün. Station
  [05](doku/05_stage5_bahn_teilstrecken/README.md) mit Code-Duplikat.

## Phase 14 — `doku/`-Ordner: Entwicklungsstationen rückwirkend aufbereitet (12.08.2026)

- **Was:** Neuer Ordner `doku/` mit einem Unterordner je Entwicklungsstation (zunächst Stationen
  1–5). Jede Station beschreibt Was, Warum und verworfene Alternativen; wo der Code noch existiert,
  liegt ein 1:1-Duplikat des damaligen Stands bei (`code_stand/`). Für Station 1 (Code seit Phase 10
  gelöscht) gibt es bewusst nur eine Textbeschreibung, keine Rekonstruktion.
- **Warum:** Anforderung des Product Owners, einzelne Architekturstationen getrennt vom
  chronologischen Log nachschlagen zu können, als Grundlage für die DSR-Darstellung.
- **Konventionen ab hier:** Vor jeder nicht-trivialen Architekturänderung werden die betroffenen
  Dateien zuerst in einen neuen `doku/`-Unterordner kopiert, weil das Projekt zu diesem Zeitpunkt
  keine Versionskontrolle nutzte (Entscheidung des Product Owners; Git kam am 09.09.2026 hinzu). Die
  Begründung einer Architekturänderung wird vor der Umsetzung beim Product Owner eingeholt.

## Phase 15 — POI-Suche: Freitext statt fester Place-Type-Zuordnung (12.08.2026)

- **Was:** `suche_pois` presste Interessen über eine Schlüsselwort-Tabelle (`_KATEGORIE_ALIASE`,
  entfernt) auf einen von Googles rund 100 festen Place Types, z. B. „Klettern" auf „gym". Ersetzt
  durch Google Places **Text Search**: je Interesse ein Aufruf mit dem Interesse wörtlich als Query.
  Jeder Treffer trägt in `POI.nutzerinteresse` das Interesse, für das er gefunden wurde;
  `berechne_poi_score` gleicht strukturell dagegen ab. Die gesamte Alias- und Namensprüfungslogik
  entfällt. `overpass.py` behält seine feste Tag-Tabelle, weil OSM keine Textsuche bietet, setzt aber
  ebenfalls `nutzerinteresse`. Station [06](doku/06_stage6_freitext_poi_suche/README.md) mit
  Code-Duplikat.
- **Warum:** Befund, dass der Wunsch „Klettern" Fitnessstudios statt Kletterorte lieferte; Anforderung
  des Product Owners, die API direkt nach dem genannten Interesse suchen zu lassen. *Verifikation:*
  „Klettern" liefert echte Kletterorte (KI-Kletterzentrum, Boulderanlage Amras, Höttinger
  Steinbruch); Interessen ohne feste Kategorie („eine Runde laufen gehen", „über Brücken spazieren")
  liefern erstmals passende Treffer.
- **Nebeneffekt:** Die Verleihsuche lief ebenfalls über die Tabelle und funktioniert unter Text
  Search unverändert; Mock-Fixtures wurden angepasst.
- Suite 178/178 grün (9 veraltete Tests entfernt, 5 neue). Live über `pruefe_planung.py` mit
  gemischten Interessen bis einschließlich Optimierung 1 verifiziert.

## Phase 16 — Mindestabstand zwischen Mahlzeiten in Optimierung 1 (12.08.2026)

- **Was:** Neue harte Nebenbedingung in `toptw.py::simuliere_route`. POIs erhalten über
  `POI.besuchsklasse` eine grobe Einordnung („mahlzeit", „kaffee", „bar"), abgeleitet aus Googles
  Typangabe. `TOPTWInstanz.mindestabstand_je_klassenpaar` legt je Klassenpaar einen Mindestabstand am
  selben Tag fest: zwei Mahlzeiten vier Stunden, Café und Bar eine Stunde; alle anderen Kombinationen,
  insbesondere Restaurant und Café, sind uneingeschränkt. Da `plane_gesamte_reise` verplante POIs
  tageweise aus dem Pool entfernt, verteilen sich mehrere Restaurantbesuche automatisch auf mehrere
  Tage. Cafés erhalten zusätzlich eine Mindest-Tageszeit von zwei Stunden nach Tagesbeginn.
- **Dabei gefundener Fehler:** `haupttyp = types[0]` nahm den ersten Eintrag aus Googles
  `types`-Liste, die nicht nach Spezifität sortiert ist („establishment" steht oft vor „restaurant").
  Besuchsdauer, Tageszeitregel und Besuchsklasse liefen dadurch ins Leere. *Fix:* `_waehle_haupttyp`
  wählt den ersten Eintrag, der in einer der eigenen Typtabellen vorkommt.
- **Warum:** Anforderung des Product Owners, keine zwei Mahlzeiten kurz hintereinander einzuplanen
  und Essen eher mittags oder abends vorzusehen. *Verworfene Alternative:* das LLM vergibt selbst
  Tage je Restaurant; abgelehnt, weil es zum Dialogzeitpunkt weder Geografie noch Reisezeiten noch die
  Tagesroute kennt (Grundprinzipien 1 und 3). Die konkreten Abstandsregeln hat der Product Owner
  bestätigt. Mehrere Unterkünfte je Reise („morgens Checkout, abends nächstes Hotel") wurden bewusst
  nicht mit umgesetzt, weil das mehrere Depots erfordern würde.
- **Verifikation:** live (Innsbruck, drei Tage, Restaurants, Cafés, Bars, Klettern): vorher drei
  Restaurants direkt hintereinander, danach auf Tage verteilt. 5 neue Tests, Suite 183/183 grün.
  Station [07](doku/07_stage7_mahlzeiten_mindestabstand/README.md) mit Code-Duplikat.

## Phase 17 — Fahrzeit zwischen POIs in der Tagesansicht (12.08.2026)

- **Was:** Text und HTML zeigen vor jedem Besuch „→ X Min. von <vorheriger Ort>"
  (`_fahrzeit_vor_besuch`). Reine Anzeige: die Fahrzeit ergibt sich bereits aus Ankunfts- und
  Abfahrtszeiten der Route; Optimierung 1 bleibt unverändert.
- **Warum:** Anforderung des Product Owners, die Fahrzeit zwischen den POIs in der Tagesansicht zu
  sehen. Live verifiziert, 2 neue Tests, Suite 185/185 grün.

## Phase 18 — Ernährungspräferenz in der Restaurantsuche, eingeschränkte Gehfähigkeit (12.08.2026)

- **Ernährung, Was:** `suche_pois` erhält `ernaehrung_einschraenkungen`. Bei essensbezogenen
  Interessen (`_ist_essen_bezogenes_interesse`) wird die Präferenz vor den Suchtext gesetzt
  („vegetarisch Restaurants in Innsbruck"); genutzt wird Googles eigene Suchrelevanz. Die harte
  Nachprüfung in `vertraeglichkeit.py` bleibt als Sicherheitsnetz. *Warum:* Anforderung des Product
  Owners, dass vorgeschlagene Restaurants zu einer genannten Ernährungspräferenz passen. Live
  verifiziert („One green table" unter den Top-Treffern für vegetarisch).
- **Gehfähigkeit, Was:** neue Methode `ReiseAnfrage.eingeschraenkte_gehfaehigkeit()`, eigenständig
  neben `barrierefreiheit_wichtig()`, weil sie die Planung anpasst statt Orte zu filtern. Drei
  Anpassungen in `erstelle_toptw_instanz`:
  1. Gehgeschwindigkeit 2,0 statt 4,5 km/h, nur wenn ohnehin zu Fuß unterwegs.
  2. Pausen: nach 120 Minuten kumulierter Fahr- und Aktivitätszeit wird vor dem nächsten Besuch eine
     20-Minuten-Pause eingeplant (`pause_intervall_minuten`, `pause_dauer_minuten`), in der Ausgabe
     sichtbar.
  3. `gewichte_nach_naehe_zum_depot`: POIs näher an der Unterkunft erhalten relativ höhere Scores
     (glatt abfallender Faktor, Referenzdistanz 1,5 km).
  *Warum:* Anforderung des Product Owners, bei Gehschwierigkeiten Gehzeiten anzupassen, Pausen
  einzuplanen und nahe POIs höher zu gewichten. Alle Werte sind dokumentierte Modellannahmen.
- **Verifikation:** live (Innsbruck, Museen und Restaurants, Gehschwierigkeiten, zu Fuß):
  differenzierte Scores (2,7/2,3/2,0), eine 20-Minuten-Pause vor dem dritten Museum. 13 neue Tests,
  Suite 200/200 grün. Station [08](doku/08_stage8_ernaehrung_und_gehfaehigkeit/README.md) mit
  Code-Duplikat.

## Phase 19 — Echte Distance Matrix statt Luftlinie in Optimierung 1 (12.08.2026)

- **Was:** Umsetzung der in der Konzeption vorgesehenen Anpassung: echte Reisezeiten aus der Google
  Distance Matrix statt Luftlinie. `hole_reisezeitmatrix` ruft die Matrix einmal je
  Unterkunftskandidat für Unterkunft und alle POIs ab; `TOPTWInstanz.reisezeiten_minuten` bevorzugt
  diese Werte und fällt nur bei fehlendem Paar auf die Luftlinienschätzung zurück.
  `erstelle_toptw_instanz` erhält dafür einen optionalen `client`-Parameter. Die Moduserkennung für
  das lokale Verkehrsmittel wurde in `modus_fuer_lokalen_transport` zusammengeführt.
- **Notwendiges Kacheln:** ein einzelner Aufruf mit allen Orten überschritt live Googles
  Elementgrenze (`MAX_ELEMENTS_EXCEEDED`) ab etwa zehn POIs. `distanzmatrix` teilt jetzt selbst in
  10×10-Kacheln auf, für Aufrufer transparent.
- **Warum:** Befund aus einem Live-Test: angezeigte Fahrzeiten von ein bis drei Minuten zwischen
  real weit entfernten Orten. Die Luftlinienschätzung ignoriert das Straßennetz; mit dem Auto
  (40 km/h) wirkten Kilometer wie Minuten. *Verifikation:* derselbe Testfall zeigt 3–9 Minuten reale
  Fahrzeit. 8 neue Tests, Suite 200/200 grün.
- **Bewusst nicht umgesetzt:** ein Cache der POI-Distanzen über mehrere Unterkunftskandidaten
  (bei höchstens fünf Kandidaten nicht nötig; seit Phase 32 gegenstandslos).

## Phase 20 — Nähegewichtung vor der Kandidatenkappung (12.08.2026)

- **Was:** `gewichte_nach_naehe_zum_depot` (Phase 18) lief erst in `erstelle_toptw_instanz`, als
  `waehle_top_pois` die Kandidaten bereits ohne Distanzbezug gekappt hatte. Beide Aufrufer wenden die
  Gewichtung jetzt zusätzlich vor der Kappung an, mit dem geokodierten Zielort als Näherung für die
  noch nicht feststehende Unterkunft.
- **Warum:** Hinweis des Product Owners auf die Abstände der POIs untereinander. Die Routenbildung
  berücksichtigt diese bereits über die echten Reisezeiten (Phase 19); die Lücke betraf nur die
  Vorauswahl bei eingeschränkter Gehfähigkeit. Live erneut verifiziert, keine Regression, Suite
  200/200 grün.

## Phase 21 — Unabhängige Prüfung von Optimierung 1 gegen Google OR-Tools (12.08.2026)

- **Was:** Neuer Ordner `evaluierung/`. Ein kleiner, von Hand nachvollziehbarer Datensatz (6 POIs und
  Depot, knappes Tagesbudget, sodass eine echte Auswahl nötig ist) wird mit drei unabhängigen
  Methoden gelöst: eigener `iterated_local_search`, Google OR-Tools (als TOPTW über den
  „Prize-Collecting"-Ansatz modelliert) und Brute-Force über alle 64 Teilmengen und Reihenfolgen.
  Alle drei erhalten dieselbe Reisezeitmatrix.
- **Warum:** `tests/test_toptw.py` prüft mit demselben Code, der die Lösung erzeugt; ein
  systematischer Fehler in der ILS-Logik fiele dort nicht auf. Werkzeugwahl (OR-Tools) und kleine
  Datensatzgröße wurden mit dem Product Owner abgestimmt.
- **Ergebnis:** alle drei erreichen denselben Score 31,0 (von 35,0 bei Besuch aller POIs); der am
  niedrigsten bewertete „Markt" wird korrekt ausgelassen. Eigener Code und Brute-Force liefern dieselbe
  Reihenfolge, OR-Tools eine gleichwertige andere. Einschränkungen und Aufruf siehe
  [`evaluierung/README.md`](evaluierung/README.md). Eigene Abhängigkeit `requirements-evaluierung.txt`.

## Phase 22 — Kontextbasierte Interessengewichtung (12.08.2026)

- **Prompt, Was:** `aktivitaeten_gewichtung` durfte bisher nur nach einer vergleichenden Rückfrage
  bei zu vielen Treffern gesetzt werden. Jetzt leitet das LLM die Gewichtung aus dem gesamten
  Gesprächskontext ab (Betonung, Wiederholung, genannter Grund, erkennbare Rangfolge); bei
  gleichrangigen Interessen wird kein Gewicht erfunden. *Warum:* Anforderung des Product Owners, nicht
  nur auf das Wort „wichtig" zu reagieren.
- **Scoring, Was:** `berechne_poi_score` von additiv (`1.0 + gewichtung*2.0`) auf multiplikativ
  (`_BASIS_SCORE * gewichtung`, Basis 3,0). Neutral unverändert, doppeltes Gewicht verdoppelt jetzt
  den Score. *Warum:* die additive Formel differenzierte zu schwach, um sich gegen viele neutrale
  Treffer durchzusetzen.
- **Verworfen:** stark gewichtete Interessen zwangsweise über Tage zu verteilen. Anders als bei
  Mahlzeiten gibt es keinen sachlichen Grund gegen zwei gewichtete Aktivitäten am selben Tag.
- 1 neuer Test, Suite 201/201 grün.

## Phase 23 — Fragereihenfolge: Lernaktivität, Ernährung, lokaler Kontakt vor Aktivitäten (12.08.2026)

- **Was:** F17, F18 und F19 stehen in `FRAGEKATALOG` jetzt vor F16, alle weiterhin in Stufe 7. Die
  F-Nummern bleiben für die Rückführbarkeit auf das Originaldokument unverändert; das LLM orientiert
  sich an der Listenreihenfolge.
- **Warum:** Entscheidung des Product Owners, dass diese Fragen thematisch zu den Aktivitäten
  gehören. Technischer Zusatznutzen: die Ernährungsangabe (F18) fließt seit Phase 18 in die
  Restaurantsuche ein und liegt so bereits bei der ersten Suche vor.
- Das Stufenmodell (Choi et al. 2012; Gavalas et al. 2014) definiert Stufen, keine Reihenfolge
  innerhalb einer Stufe. Suite 201/201 grün.

## Phase 24 — main.py: zweites Testfall-Format (12.08.2026)

- **Was:** `lade_testfall` akzeptiert neben der Antwortliste auch ein Objekt Feldname zu Antwort und
  wandelt es in eine geordnete Liste um. *Warum:* drei neue Testfälle (Personas Annegret, Jakob,
  Thomas) lagen in diesem, beim Schreiben übersichtlicheren Format vor. Sie decken eingeschränkte
  Gehfähigkeit und All-Inclusive, Klettern mit Freitextsuche sowie Familie mit Ernährungs- und
  Kulturfokus ab. Suite 201/201 grün.

## Phase 25 — main.py robuster, zwei API-Robustheitsfehler behoben (12.08.2026)

- **Testfall-Format:** beim Objektformat wird ein konsolidierter Block aller Felder als erste
  Nachricht übergeben, danach generische Zustimmungen und Einzelwerte. *Warum:* `SkriptKanal` liefert
  strikt die nächste Antwort, unabhängig von der tatsächlichen Frage; eine unerwartete Rückfrage
  verschob alles. Ein umfassender Freitextblock lässt das LLM selbst extrahieren. Live verifiziert
  (Testfall Jakob, vollständiger Durchlauf mit Mailversand).
- **Teststrategie:** für schnelles Testen der Planung dient `pruefe_planung.py` (ohne LLM, Sekunden
  statt Minuten); der echte Dialog wird nur noch gezielt für das Gesprächsverhalten genutzt.
- **Fehler 1:** eine zu vage Zielangabe („Mittelmeerraum") führte zu einem ungefangenen
  `RuntimeError` (Directions-Status `NOT_FOUND`). *Fix:* `NOT_FOUND` wird wie `ZERO_RESULTS` als
  „keine Route für diese Alternative" behandelt; andere Fehler werden weiter durchgereicht.
- **Fehler 2 (Folgefehler):** ohne jede Route stürzte `plane_reise` mit `IndexError` ab. *Fix:*
  verständliche `ValueError`-Meldung („Ortsangabe zu ungenau").
- Planungstestfälle Annegret, Jakob, Thomas für `pruefe_planung.py` angelegt, mit konkreteren
  Zielorten (Mallorca, Innsbruck, München), weil Länder- oder Regionsebene für eine lokale POI-Suche
  zu grob ist. Suite 201/201 grün.

## Phase 26 — Eine Frage pro Nachricht (12.08.2026)

- **Was:** Der Regelwerk-Prompt (`_TOOL_ANLEITUNG`) verlangt genau eine Frage pro Nachricht. Eine
  kurze, zugehörige Zusatzangabe innerhalb einer Frage bleibt erlaubt (z. B. das Alter der Kinder bei
  der Frage nach der Reisebegleitung).
- **Warum:** Im Test mit der Persona Thomas stellte das LLM drei nummerierte Katalogfragen in einer
  Nachricht; der Prompt enthielt dazu keine Regel. Reine Prompt-Änderung, wirksam ab der nächsten
  Sitzung. Suite 201/201 grün.

## Phase 27 — main.py, Testfälle und SkriptKanal entfernt (12.08.2026)

- **Was:** `main.py`, der Ordner `testfaelle/` und `SkriptKanal` wurden entfernt, Verweise
  korrigiert. Die pytest-Suite und `pruefe_planung.py` mit `planungs_testfaelle/` bleiben.
- **Warum:** Die Dialogsimulation blieb trotz der Nachbesserungen strukturell fragil: `SkriptKanal`
  liefert stur die nächste vorbereitete Antwort, unerwartete Rückfragen führen zu kaskadierenden
  Fehlzuordnungen. Entscheidung des Product Owners: Dialogverhalten wird manuell über `chat.py`
  getestet. Die pytest-Suite ist davon unabhängig (deterministisch, ohne LLM). Suite 201/201 grün.

## Phase 28 — Flexibilitätspräferenz begrenzt POIs pro Tag (12.08.2026)

- **Was:** F05 (`flexibilitaet_praeferenz`) wurde erfragt, aber nirgends ausgewertet.
  `max_pois_pro_tag_fuer_flexibilitaet` leitet per Schlüsselwortzählung eine Tagesobergrenze für die
  Anzahl Besuche ab (flexibel 2, durchgeplant 6); bei fehlender oder widersprüchlicher Angabe gibt es
  keine Begrenzung, statt eine Präferenz zu erfinden. `TOPTWInstanz.max_pois_pro_tag` setzt das als
  harte Nebenbedingung durch. (In Phase 43 durch eine LLM-beurteilte Skala ersetzt.)
- **Warum:** Anforderung des Product Owners: je flexibler, desto weniger POIs pro Tag. Live
  verifiziert (Persona Jakob, „eher flexibel": 2 statt 5–6 POIs pro Tag). 6 neue Tests, Suite 207/207.

## Phase 29 — Keine Hotel- und POI-Auswahl mehr im Chat (12.08.2026)

- **Was:** F15 (Unterkunft) und F16 (Aktivitäten) wurden von Typ C zu Typ B: das LLM erfragt nur die
  Anforderung und speichert sie, ohne Kandidaten zu zeigen. `hole_api_daten` akzeptierte danach nur
  noch F13. Die eigentliche Auswahl war bereits deterministisch (`_plane_bestes_depot` testete mehrere
  Unterkünfte per vollständiger Optimierung, `waehle_top_pois` wählte nach Score) und blieb
  unverändert; sichtbar wurde sie erst im fertigen Plan.
- **Warum:** Entscheidung des Product Owners: das System wählt selbst ein Hotel nach den genannten
  Anforderungen und nennt es in der Mail, nicht im Chat; ebenso bei POIs. Da die finale Auswahl ohnehin
  automatisch geschah, war die Chat-Vorschau die überflüssige Zwischenstufe.
- **Nicht umgesetzt:** ein Hotel früh nach F15 festzulegen, um der Nähegewichtung eine echte statt
  einer groben Koordinate zu geben (in Phase 32 in anderer Form umgesetzt).
- 17 Tests der entfernten Vorschauzweige entfernt, einer ersetzt. Suite 190/190 grün.

## Phase 30 — Aktivitäten (F16) wieder Typ C, Unterkunft (F15) bleibt vereinfacht (12.08.2026)

- **Was:** Teilrücknahme von Phase 29: F16 ist wieder eine Dialogfrage mit Kandidatenvorschau,
  Vertiefungsfragen, Warnschwelle bei zu vielen Treffern und Anfahrtsempfehlung, wiederhergestellt
  aus dem Code-Stand der Station 10. F15 bleibt vereinfacht.
- **Warum:** Rückmeldung des Product Owners nach einem Live-Test: das Nachfragen bei Aktivitäten
  hatte sich bewährt, bei Unterkünften wurde es nicht vermisst. 10 Tests wiederhergestellt oder
  angepasst, Suite 200/200 grün.
- **Vorgemerkt:** (1) die Chat-Übersicht am Ende soll alle Tage zeigen; (2) Essen soll aus der
  Aktivitätenplanung herausgenommen werden (umgesetzt in Phase 41); (3) die Tagesausgabe als
  geordnete Aktivitätenkette statt Zeitplan.

## Phase 31 — Unterkunft (F15) ruft die API weiterhin auf, nur ohne Anzeige (12.08.2026)

- **Was:** F15 erhält wieder `api_abruf_noetig=True`; `hole_api_daten` holt echte
  Unterkunftskandidaten wie vor Phase 29. Neu: liefert die Suche nichts, gibt es einen ehrlichen
  Hinweistext. Laut Regelwerk nennt das LLM keine Hotelnamen und holt keine Zustimmung ein, sondern
  speichert die Anforderung.
- **Warum:** Präzisierung des Product Owners: der API-Abruf sollte nie entfallen, nur die Anzeige im
  Chat. Ohne Abruf wäre Grundprinzip 1 für dieses Feld faktisch aufgehoben. Der stille Abruf dient als
  Realitätscheck während des Dialogs. 9 Tests wiederhergestellt, einer neu, einer ersetzt; Suite
  209/209 grün.

## Phase 32 — Code-Review: sieben strukturelle Änderungen (12.08.2026)

Grundlage war ein Code-Review des Product Owners mit elf Punkten. Die Absicht jedes Punkts wurde vor
der Umsetzung bestätigt, zwei Widersprüche zwischen Punkten wurden dabei aufgelöst.

- **All-Inclusive und Flug vollständig entfernt** (`hotelbeds.py`, `flightapi.py` und Tests gelöscht,
  ohne Code-Stand-Snapshot; nur textlich dokumentiert). Zugehörige Felder, Sonderpfade und der
  Flug-Emissionsfaktor entfielen. Grundprinzip 5 gilt damit ohne Ausnahme.
- **Barrierefreiheit und eingeschränkte Gehfähigkeit zusammengelegt** zu
  `barrierefreiheit_oder_eingeschraenkt()`, das beide Effekte (Ausschluss sowie Tempo, Pausen, Nähe)
  gemeinsam auslöst. (In Phase 41/42 wieder differenziert.)
- **Sicherheit durch das LLM erkannt statt per Schlüsselwort:** `sicherheit_ist_wichtig()` entfällt,
  das LLM setzt `sicherheit_bedenklich` aus dem Gesamtkontext und schlägt bei erkennbar
  problematischem Ziel eine sicherere Alternativregion vor.
- **Unterkunftswahl umgebaut:** `_plane_bestes_depot` entfällt. `suche_unterkunft` sucht bei F15 genau
  eine Unterkunft, das LLM schlägt sie vor und holt eine Bestätigung ein (F15 wieder Typ C); die
  Planung nutzt genau deren Koordinaten als Depot.
- **Verleihsuche im Dialog:** `suche_verleih_nahe_unterkunft` sucht bei erkanntem Leihwunsch einen
  Verleih und wählt den nächstgelegenen zur bereits bestätigten Unterkunft; F15 muss daher
  abgeschlossen sein. Die Übernahme ist deterministisch, weil die Auswahl nur auf Distanz beruht.
- **Nachhaltigkeits-Nudge vorgezogen:** die Bewertung nach Zeit, Kosten und CO₂ läuft zusätzlich
  bereits in der F13-Vorschau, sodass der Nudge den Nutzer vor seiner Entscheidung erreicht. Ein
  bestätigtes Verkehrsmittel wird weiterhin respektiert (Phase 11).
- **Nachprüfung der Barrierefreiheit am fertigen Plan:** `pruefe_barrierefreiheit_des_plans` prüft
  den tatsächlich geplanten Reiseplan gegen echte Google-Daten. Erfüllt er die Anforderung nicht,
  schlägt `plane_reise_und_abschliessen` fehl und das LLM fragt, ob strenger neu geplant werden darf;
  erst der Aufruf mit `barrierefreiheit_bereits_gepruft=true` schließt ab.

Zurückgestellt und später umgesetzt: LLM-Interpretation des Tagesablaufs (Phase 33) und eine
Web-Oberfläche mit Bildvorschau (Phase 34). Tests umfangreich angepasst; Kommentare in den
betroffenen Dateien auf gegenwartsbezogene Beschreibungen umgestellt. Suite 191/191 grün.

## Phase 33 — Tagesablauf (F20) vom LLM interpretiert statt per Regex (12.08.2026)

- **Was:** Der Regex-Parser `parameter_fuer_tagesablauf` entfällt. Das LLM interpretiert die
  F20-Antwort und übergibt `tagesstart_minuten` und `tagesende_minuten` als Argumente von
  `speichere_feld`. `plane_reise` nutzt die Differenz jetzt als Basis-Tagesbudget für Optimierung 1;
  vorher wirkte nur der Startwert auf die Anzeige, der Endwert wurde verworfen.
- **Warum:** Anforderung des Product Owners, die Interpretation dem LLM zu überlassen. Ein Regex
  erkennt nur exakte Uhrzeiten, nicht Formulierungen wie „eher früh los, nicht so spät zurück". 2
  Tests entfernt, 2 neue; Suite 191/191 grün.

## Phase 34 — Web-Oberfläche mit Foto-Karten (13.08.2026)

- **Was:** Zweiter Einstiegspunkt `webapp.py` (FastAPI mit WebSocket `/ws/chat`), der denselben
  Dialog (`chat.py::hauptablauf`) im Browser führt. `IOKanal` wurde dafür asynchron; ein neuer
  `WebIOKanal` bindet WebSocket-Nachrichten an. `hauptablauf` gibt den finalen Sitzungszustand
  zurück. Der fertige Reiseplan zeigt Karten mit Foto, Kurzbeschreibung und Google-Maps-Link je
  Unterkunft und POI (`als_kartendaten`). Die Fotoreferenz stammt aus der ohnehin laufenden
  Places-Suche; als Kurzbeschreibung dient `POI.kategorie`, statt kostenpflichtiger Detailabfragen.
  Fotos werden erst nach Planungsabschluss serverseitig heruntergeladen (`lade_fotos_fuer_plan`) und
  von FastAPI ausgeliefert; `chat.py` und `pruefe_planung.py` laden keine Fotos. Frontend ist eine
  einzelne, abhängigkeitsfreie `static/index.html`.
- **Warum:** Anforderung des Product Owners nach einer Browser-Oberfläche mit kleiner Vorschau (Foto,
  Kurzbeschreibung) für Hotels und POIs. Rahmenentscheidungen vor der Umsetzung: FastAPI (asynchron,
  passt zum bestehenden asyncio-Code), WebSocket statt Polling, Karten nur im fertigen Plan, Fotos
  serverseitig statt über einen clientseitigen Schlüssel-Proxy, weil der API-Schlüssel nie im Browser
  sichtbar werden darf.
- Vorher-Stand in [Station 15](doku/15_stage15_web_ui/README.md) gesichert. 12 neue Tests, Suite
  203/203 grün. Gesprächsverhalten im Browser wird manuell verifiziert.

## Phase 35 — Erster Live-Test der Web-Oberfläche: Kostenschätzung, Hotelkarte, Websuche, Zielregionen (13.08.2026)

Fünf Rückmeldungen nach dem ersten Testlauf von `webapp.py`. Vier wurden vor der Umsetzung mit dem
Product Owner entschieden, zwei davon widersprachen bestehenden Festlegungen (Grundprinzip 2 bei der
Websuche, „Karten nur am Ende" bei der Hotelkarte).

- **Kostenschätzung:** Neues Modul `kostenschaetzung.py` schätzt die Gesamtkosten pro Person
  (An- und Abreise, Unterkunft, eingeplante Aktivitäten, jeweils aus Googles `price_level` 0–4 grob in
  Euro umgerechnet, dazu 35 € Verpflegung pro Tag) und vergleicht sie mit dem genannten Budget. POIs
  ohne Preisniveau zählen als kostenlos; fehlt es bei der Unterkunft, wird das gekennzeichnet.
  *Entscheidung des Product Owners:* rein informativ, ohne Einfluss auf Optimierung 1.
- **Hotelkarte im Chat:** `IOKanal.zeige_karte(unterkunft)` (in der Konsole wirkungslos).
  `hauptablauf` ruft sie auf, sobald `hole_api_daten` für F15 einen neuen Kandidaten gefunden hat;
  `WebIOKanal` lädt das Foto sofort und sendet Name, Foto, geschätzten Preis pro Nacht und Maps-Link als
  eigene Nachricht. *Entscheidung:* bewusste, eng begrenzte Ausnahme von „Karten nur am Ende", nur für
  die Unterkunft.
- **Websuche für den Agenten:** `chat.py` erlaubt zusätzlich zu den fünf Werkzeugen das
  `WebSearch`-Werkzeug. Der Regelwerk-Abschnitt WEBSEARCH beschränkt sie auf Kontext- und
  Hintergrundrecherche; POIs, Unterkünfte, Preise und Reisezeiten kommen weiterhin nur aus den
  API-Werkzeugen und sind die einzige Quelle für Optimierung 1 und 2. *Entscheidung des Product Owners*
  nach Hinweis auf den Konflikt: dokumentierte Ausnahme von Grundprinzip 2.
- **Zielregionen:** Vorschau und Planung verwenden nur `primaeres_reiseziel()`, die erste genannte
  Region. Im Test hatte das LLM fälschlich behauptet, später würden alle drei genannten Städte
  durchsucht. *Entscheidung:* keine Mehrstädte-Unterstützung, stattdessen klarer Hinweis. Der
  F07-Kontexthinweis weist das LLM an, auf die Ein-Ziel-Grenze hinzuweisen; zusätzlich wiederholt
  `_mehrere_zielregionen_hinweis` diese Grenze bei jedem betroffenen Werkzeugaufruf.
- **Mikrofon und Vorlesen im Browser:** Mikrofon- und Vorlese-Knopf über die Web Speech API, rein
  clientseitig. *Warum clientseitig:* der serverseitige Audiomodus bräuchte Mikrofon und Lautsprecher
  am Server und wäre für entfernte Nutzer nutzlos. Spracheingaben laufen über denselben Pfad wie
  getippter Text. Firefox unterstützt die Spracherkennung nicht; der Knopf deaktiviert sich dort.
  *Nachbesserungen nach dem ersten Ausprobieren:* der Knopf zeigt den Aufnahmezustand erst nach dem
  tatsächlichen Start, ein zweiter Klick beendet die Erkennung sauber, Fehler werden sichtbar
  gemeldet, und die Vorlesefunktion wählt eine natürlicher klingende deutsche Stimme. Ein
  wiederkehrender `network`-Fehler erwies sich als Eigenschaft der Web Speech API (Chromium-Browser
  ohne Googles Schlüssel oder mit blockierenden Filtern); die Fehlermeldung nennt nun die
  wahrscheinlichen Ursachen und Alternativen. Der Knopf bleibt als Rückfalloption erhalten.
- 21 neue Tests, Suite 224/224 grün. Mikrofon und Vorlesen manuell verifiziert. Vorher-Stand in
  [Station 16](doku/16_stage16_testfeedback_kosten_karten_suche/README.md).

## Phase 36 — Verkehrsmittel je Etappe, Planungs-Debug-Ausgabe (13.08.2026)

- **Verkehrsmittel je Etappe:** Die Fahrzeiten zwischen POIs kamen bereits real von Google; es fehlte
  die Angabe, welches Verkehrsmittel gemeint ist, und die Reise nutzte nur ein global festgelegtes.
  *Entscheidung („Variante B"):* erst optimieren, dann nur die gewählten Etappen erneut abfragen,
  statt vorab alle Kandidatenpaare für jedes Verkehrsmittel. *Warum:* weniger API-Aufrufe, Anzeige
  konsistent mit den berechneten Zeiten.
  - `modi_fuer_lokalen_transport` erkennt alle in F14 genannten Verkehrsmittel, sortiert nach der
    Position im Text. Bei mehreren fragt `hole_reisezeitmatrix` je Modus ab und nimmt je Paar die
    schnellere Zeit.
  - `ergaenze_anfahrt_modus_je_etappe` läuft nach Optimierung 1 nur für besuchte Etappen und setzt
    `Besuch.anfahrt_modus`, rein für die Anzeige („→ 15 Min. (mit dem Fahrrad) von Unterkunft").
  - Pro Etappe wird genau ein Verkehrsmittel genannt, kein Alternativenvergleich.
  - *Dabei behoben:* `_instanz_mit_gestoerten_fahrzeiten` stürzte bei einer Reisezeit von 0 Minuten
    mit `math domain error` ab; jetzt mindestens eine Minute vor dem Logarithmus.
- **Planungs-Debug-Ausgabe:** Neues Modul `debug.py` (`PlanungsDebugSammlung`,
  `schreibe_debug_datei`) hält rohe Treffer, gefilterte Kandidaten, die an Optimierung 1 übergebenen
  Kandidaten sowie Eingabe und Ergebnis von Optimierung 1 und Härtetest fest, zunächst nur über
  `pruefe_planung.py`, als strukturierte Textdatei. *Warum:* Anforderung des Product Owners,
  nachvollziehen zu können, mit welchen Daten die Algorithmen arbeiten.
- **Gefundene Lücke:** Die in README und `pruefe_planung.py` genannten Testfälle (u. a.
  `klettern_essen`) existierten nicht mehr. Für den Smoke-Test wurde `smoketest_etappen.json`
  angelegt; die ursprünglichen wurden mangels Grundlage nicht rekonstruiert (siehe Offene Punkte).
- 13 neue, 6 angepasste Tests, Suite 239/239 grün; zusätzlich ein Live-Lauf gegen die Google-API.

## Phase 37 — Google-Maps-Routenlinks für jede Etappe sowie An- und Abreise (13.08.2026)

- **Was:** Jede Streckenzeile erhält einen Directions-Link, der Google Maps mit Start, Ziel und dem
  geplanten Verkehrsmittel öffnet (`routen_link(ursprung, ziel, travelmode)`, dokumentiertes
  URL-Schema, kein API-Aufruf). Vor-Ort-Etappen nutzen Koordinaten und `Besuch.anfahrt_modus`; An- und
  Abreise nutzen Ortsnamen und die Zuordnung `_TRAVELMODE_JE_VERKEHRSMITTEL` (Bahn und Fernbus zu
  transit, Auto zu driving). Fehlt ein Punkt, entfällt der Link, statt einen Startpunkt zu raten.
- **Warum:** Anforderung des Product Owners, jede Route direkt in Google Maps öffnen zu können, bei
  sonst unveränderter Darstellung. Live verifiziert. 10 neue Tests, Suite 249/249 grün.

## Phase 38 — Präzisere An- und Abreiselinks; Bahnhofsausschluss zurückgenommen (13.08.2026)

- **Was:** Die Links für Hin- und Rückreise führten nur zur Zielstadt. `_hinreise_ziel_fuer_link`
  bevorzugt jetzt die Koordinaten der bestätigten Unterkunft und fällt nur ohne Unterkunft auf den
  Zielort zurück; die Rückreise beginnt an der Unterkunft und endet am Wohnort.
- **Zurückgenommen:** Auf die Beobachtung hin, dass am An- und Abreisetag Bahnhöfe als POI-Karten
  erschienen, wurde zunächst eine Ausschlussliste für Verkehrs-Place-Types eingeführt. Der Product
  Owner lehnte einen pauschalen Ausschluss ab, weil Bahnhöfe als Ziel grundsätzlich möglich bleiben
  sollen; die Liste wurde vollständig entfernt. Das ursprüngliche Symptom bleibt ein offener Punkt.
- Live verifiziert. 1 neuer, 1 angepasster Test, Suite 250/250 grün.

## Phase 39 — Debug-Ausgabe bei jeder Planung, Ablage in `protokolle/` (13.08.2026)

- **Was:** `plane_reise` erzeugt immer eine `PlanungsDebugSammlung` und gibt sie als drittes Element
  zurück (kaum Mehraufwand, nur Referenzen auf ohnehin berechnete Daten).
  `plane_reise_und_abschliessen` schreibt sie bei jedem Planungsversuch, auch einem gescheiterten, als
  `<protokoll>_debug.txt` neben das Sitzungsprotokoll in `protokolle/`. Auch `pruefe_planung.py`
  schreibt dorthin.
- **Warum:** Entscheidung des Product Owners, dass die Nachvollziehbarkeit auch im echten Dialog
  entsteht und als bleibender Teil der Anwendung in `protokolle/` liegt, weil Testwerkzeuge wie
  `pruefe_planung.py` für die Abgabe eher entfallen. Live verifiziert. 2 neue Tests, Suite 252/252.

## Phase 40 — Monte-Carlo-Härtetest auf die Umstiege der An- und Abreise umgestellt (16.08.2026)

Auslöser: `pruefe_algorithmus.py` zeigt an einem von Hand nachrechenbaren Beispiel jedes Datenfeld,
das Optimierung 1 und Härtetest erhalten. Beim Durchsehen fiel auf, dass der Härtetest auf den
POI-Bewegungen vor Ort lief, wo die Verpassgefahr durch wenige Minuten Fußweg praktisch irrelevant
ist. Riskant sind reale Bus- und Bahnumstiege bei der An- und Abreise (etwa: erreicht man die Bahn
noch, wenn der Bus fünf Minuten Verspätung hat?).

- **Was:** Der POI-basierte Härtetest (`haertetest`, `_instanz_mit_gestoerten_fahrzeiten`) wurde
  entfernt, nicht parallel weitergeführt. `haertetest_teilstrecken(teilstrecken, ...)` simuliert die
  `Teilstrecke`-Kette aus den ohnehin abgerufenen Directions-Schritten (kein zusätzlicher API-Aufruf).
  Jede Teilstreckendauer wird log-normal gestreut (Verfahren und Parameter unverändert); an jedem
  Umstieg mit bekanntem Puffer (`wartezeit_minuten`) wird geprüft, ob die aufgelaufene Verspätung noch
  hineinpasst. Reicht er nicht, gilt der ganze Lauf als gescheitert. `plane_reise` ruft den Test nur für
  Hin- und Rückreise auf und nur mit vorhandenen Teilstrecken; bei Auto bleibt das Ergebnis `None`
  statt eines erfundenen Werts. `Reiseplan.robustheit` wurde durch `hinreise_robustheit` und
  `rueckreise_robustheit` ersetzt. Die Debug-Datei zeigt die Teilstreckenkette beider Richtungen;
  `pruefe_algorithmus.py` demonstriert den Test an einem eigenen Beispiel (Bus, Regionalbahn, ICE).
- **Warum:** Entscheidung des Product Owners, den POI-Test zu ersetzen statt zu ergänzen, und ihn nur
  bei Bahn und Fernbus auszuführen. *Verworfen:* bei verpasstem Anschluss eine spätere Verbindung zu
  prüfen, weil dafür Fahrplanalternativen fehlen, die der Test nicht erhält, und weitere Abfragen
  vermieden werden sollten. Ergebnis ist ein einfaches binäres Modell.
- **Nebenbefund (nicht behoben):** Der ILS-Reparaturschritt hängt nach `_shake()` reparierte POIs
  immer hinter den unveränderten Präfix an und versucht keine Position davor. Im
  `pruefe_algorithmus.py`-Beispiel (4 POIs, 240 Minuten) findet der Algorithmus dadurch Score 13,
  obwohl eine gültige Route mit Score 15 existiert (per `simuliere_route()` verifiziert). Offener Punkt.
- **Verifikation:** live (`smoketest_etappen`): Hin- und Rückreise mit je einem S-Bahn-Umstieg zu
  100 % robust. `test_monte_carlo.py` neu (5 Tests, u. a. Puffer 0 erkennt tatsächlich
  Verletzungen), weitere Tests angepasst. Suite 254/254 grün.

## Phase 41 — Barrierefreiheit vom LLM beurteilt, geführte Touren, Restaurants außerhalb von Optimierung 1 (17.08.2026)

Auslöser: ein Live-Test (Berlin, Familie mit zwei Kindern, Reiseleitung gewünscht, Interessen
„Sehenswürdigkeiten" und „Restaurants"). Tag 3 blieb trotz gewünschter Führung leer, ein gewünschtes
Abendessen wurde von Optimierung 1 aussortiert, und die Barrierefreiheitserkennung stützte sich auf
eine Wortliste, die das LLM nicht kannte.

- **Barrierefreiheit (F09/F10/F15):** `barrierefreiheit_oder_eingeschraenkt()` durchsuchte drei
  Freitextfelder nach rund 13 festen Wörtern; eine sinngemäße Antwort („wegen der Kinder lieber
  gemütlich") blieb unerkannt. Ersetzt analog zu F11 durch `barrierefreiheit_bedenklich`, vom LLM aus
  dem gesamten Gesprächskontext gesetzt, bei jedem `speichere_feld`-Aufruf möglich. Alle Folgeeffekte
  bleiben deterministisch (Grundprinzip 3). (In Phase 42 zu drei Stufen erweitert.)
- **Geführte Touren:** Eine deterministische Kopplung an F04 lehnte der Product Owner ab; das LLM soll
  bei erkanntem Tourwunsch selbst eine Tourensuche anstoßen. Umgesetzt als Kontexthinweis bei F04 und
  F16: das LLM nimmt einen Suchbegriff wie „geführte Tour" in `aktivitaeten_interessen` auf, gesucht
  wird über die bestehende Freitextsuche. Zusätzlich zeigt ein Tag ohne Programm zwei bis drei nicht
  eingeplante Kandidaten als Beispiele statt „kein Programm eingeplant"
  (`_verteile_beispiele_auf_leere_tage`, ohne Wiederholung und ohne Dopplung mit „Weitere
  Empfehlungen").
- **Restaurants außerhalb von Optimierung 1:** Entscheidung des Product Owners, Restaurants nicht als
  eigene POIs der Tagesroute zu behandeln, sondern Beispielrestaurants nahe der Unterkunft zu zeigen.
  `_trenne_beispielrestaurants_ab` entfernt Treffer mit `besuchsklasse == "mahlzeit"` vor Optimierung 1
  und gibt sie nach Entfernung sortiert als `Reiseplan.beispielrestaurants` zurück; je Tag werden drei
  rotierend angezeigt. Cafés und Bars bleiben zunächst normale Kandidaten. *Verworfen:* ein Restaurant
  fest ans Tagesende zu hängen.
- **Verifikation:** live (Museum, Restaurants, geführte Tour): echte Tourenanbieter gefunden und
  eingeplant, unterschiedliche Beispielrestaurants je Tag, keine Dopplungen. Suite 264/264 grün.
- **Nebenfrage, nicht umgesetzt:** echte Hotelpreise bräuchten eine gesonderte Preis-API; die in
  Google Maps sichtbaren Preise stammen aus Google Hotel Ads und sind über den Maps-Schlüssel nicht
  erreichbar. (Am 24.08.2026 entschieden: Preisniveau-Schätzung bleibt.)

## Phase 42 — Barrierefreiheit in drei Stufen (17.08.2026)

Anforderung des Product Owners: langsameres Gehen und Rollstuhlnutzung erfordern unterschiedliche
Konsequenzen. Vorab wurde geprüft, welche Stufen sich mit echten Daten unterscheiden lassen: einzige
strukturierte Quelle ist `wheelchair_accessible_entrance` (Google Places); Steigungs- oder
Terraindaten gibt es nicht.

- **Was:** `barrierefreiheit_bedenklich` wird durch `mobilitaetseinschraenkung_stufe` ersetzt, vom LLM
  gesetzt und im Gespräch überschreibbar:
  - `"leicht"` (z. B. altersbedingt langsamer): kein Ausschluss, nur Tempo, Pausen und Nähe.
  - `"mittel"` (z. B. Gehhilfe): zusätzlich Ausschluss explizit als nicht barrierefrei bestätigter Orte;
    unbekannte bleiben.
  - `"stark"` (z. B. Rollstuhl): nur eindeutig bestätigt barrierefreie Orte; unbekannt gilt als
    Ausschlussgrund.
  Umgesetzt in `_barrierefreiheits_kriterium` für POI-Filter, Unterkunftsfilter und die Nachprüfung
  des fertigen Plans.
- **Verifikation:** live (Rollstuhl, Stufe „stark"): ein Museum mit unbekanntem Status wurde korrekt
  als nicht bestätigt erkannt (Warnhinweis als einziger Treffer der Kategorie); 20-Minuten-Pausen
  sichtbar. Tests je Stufe, Suite 271/271 grün.

## Phase 43 — Flexibilität als vom LLM beurteilte Skala (17.08.2026)

F05 wirkte bisher nur über eine Schlüsselwortzählung auf die Anzahl POIs pro Tag, nicht auf die
Verteilung innerhalb des Tages. Anforderung des Product Owners: ein flexibler Tag soll auch zwischendurch
Freiraum bieten, etwa für einen spontanen Kaffee.

- **Was:** neues Feld `flexibilitaet_stufe` (1–5), vom LLM aus dem Gesprächsverlauf gesetzt, ohne
  direkt nach einer Zahl zu fragen (Entscheidung des Product Owners); überschreibbar. Ersetzt die
  Schlüsselwortzählung. Zwei Hebel je Stufe, mit dem Product Owner abgestimmt:

  | Stufe | POIs pro Tag höchstens | Pufferpause |
  |---|---|---|
  | 1 (durchgeplant) | kein Deckel | keine |
  | 2 | 6 | keine |
  | 3 | 5 | alle 3 h, 15 Min. |
  | 4 | 3 | alle 2,5 h, 20 Min. |
  | 5 (sehr flexibel) | 2 | alle 1,5 h, 30 Min. |

  Die Pufferpause nutzt denselben Mechanismus wie die Barrierefreiheitspause; bei beiden gilt das
  kürzere Intervall. (In Phase 53 auf drei Stufen verkleinert.)
- Kein Code-Stand-Snapshot vor der Umsetzung (transparent vermerkt). Live verifiziert (Stufe 5: genau
  2 POIs pro Tag). Suite 273/273 grün.

## Phase 44 — Geführte Touren auf eigenem reservierten Tag, Performance (17.08.2026)

Vorfall im Live-Test: der Web-Chat blieb bei einer Anfrage mit Rollstuhl und den Interessen „geführte
Tour", „Restaurants" und „Sehenswürdigkeiten" hängen. Das Sitzungsprotokoll zeigte als letzten
Eintrag `hole_api_daten(aktivitaeten_interessen)`. Ursache: Stufe „stark" löst für jeden Rohtreffer
eine eigene Place-Details-Abfrage aus; mit der Tourensuche stieg die Zahl auf rund 60 sequenzielle
Aufrufe.

- **Was:** Entscheidung des Product Owners: geführte Touren laufen nie durch Optimierung 1 und werden
  vor jeder teuren Prüfung auf einen kleinen Pool begrenzt.
  - `ist_tour_bezogenes_interesse` erkennt Tourinteressen über Schlüsselwörter im `nutzerinteresse`,
    da Google keinen eigenen Place Type dafür hat.
  - `_trenne_tour_beispiele_ab` trennt Tourtreffer vor `filtere_pois_hart` ab, begrenzt sie auf die
    acht nächstgelegenen zur Unterkunft und wählt drei ohne Score oder Ranking aus.
  - Barrierefreiheit der drei Touren gestaffelt nach derselben Stufe wie überall: „leicht" keine
    Prüfung, „mittel" mindestens die Hälfte bestätigt, „stark" alle bestätigt. Reicht der Pool nicht,
    werden ehrlich weniger gezeigt.
  - Bei Fund wird der letzte Tag vollständig aus Optimierung 1 herausgenommen
    (`anzahl_tage_override`) und erhält die Touren direkt (`Reiseplan.tour_tag_beispiele`).
- Kein Code-Stand-Snapshot vor der Umsetzung (transparent vermerkt).
- **Verifikation:** live mit derselben Kombination: Laufzeit von „hängt" auf rund 37 Sekunden; Tag 3
  zeigt zwei bestätigt barrierefreie Touren. Die Restlaufzeit stammt von der unveränderten Prüfung
  der normalen Kandidaten (Offener Punkt). Suite 284/284 grün.

## Phase 45 — Härtetest-Schwelle von 95 % auf 80 % gesenkt (17.08.2026)

- **Was:** Default `schwelle` in `haertetest_teilstrecken` von 0,95 auf 0,80; `pruefe_algorithmus.py`
  entsprechend angepasst. `plane_reise` übernimmt den Default.
- **Warum:** Entscheidung des Product Owners, dass 95 % zu streng war. Tests unberührt, Suite grün.

## Phase 46 — Lernaktivitäten (F17): konkrete Kurse wie Touren, unkonkrete Wünsche mit Empfehlung (17.08.2026)

Befund: `lernaktivitaeten_interesse` (F17) wurde erfragt und gespeichert, aber nirgends ausgewertet,
wie zuvor `reiseleitung_gewuenscht`. Auf Wunsch des Product Owners wurde zuerst ein Konzept für
mögliche Antwortkategorien erarbeitet und abgestimmt.

- **Konkrete, ortsgebundene Aktivität (z. B. „Kochkurs"):** Behandlung wie geführte Touren.
  *Entscheidung des Product Owners:* ein ausdrücklicher Lernwunsch darf nie vom Optimierungsalgorithmus
  aussortiert werden. `_trenne_tour_beispiele_ab` wurde zu `_trenne_sonderkategorie_ab`
  verallgemeinert (Kategorie als Prädikat); Pool von acht, drei Beispiele ohne Ranking und die
  Barrierefreiheitsstaffelung gelten für beide Kategorien. Neue Erkennung
  `ist_lernaktivitaet_bezogenes_interesse` („kurs", „workshop", „seminar", „unterricht"); das LLM
  nimmt bei konkreter Aktivität selbst einen Suchbegriff auf. Werden Tour und Lernaktivität gefunden,
  erhalten sie zwei getrennte Tage (`_reservierte_sondertage`), neues Feld
  `Reiseplan.lernaktivitaet_tag_beispiele`.
- **Unkonkrete Aussage (z. B. „offen sein und dazulernen"):** keine Suche (Grundprinzip 1), aber eine
  kurze allgemeine Empfehlung im Gespräch. *Entscheidung:* bekannte, real existierende Angebote wie
  Duolingo dürfen genannt werden, keine unsicheren Fakten über den Zielort.
- **Dokumentation:** Der Product Owner wollte kein zusätzliches Dokument für Konzepte je Frage. Die
  Architekturbeschreibung hält den aktuellen Stand, dieses Log das chronologische Warum.
- **Verifikation:** live (Museum, geführte Tour, Kochkurs, vier Tage): Tag 1 und 2 optimiert, Tag 3
  mit drei echten Touranbietern, Tag 4 mit drei echten Kochschulen. Suite 287/287 grün.

## Phase 47 — Lokaler Kontakt (F19): Mittagsblock für Markt und Café (17.08.2026)

Befund: auch `lokaler_kontakt_wichtig` (F19) wurde nicht ausgewertet. Nach Beispielen möglicher
Angebote entstand ein eigenes Konzept; *Entscheidung des Product Owners:* nicht alles nach demselben
Muster umsetzen.

- **Was:** ein drittes Strukturmuster, weder eigener Tag (Touren, Lernaktivitäten) noch ganz ohne
  Tagesbindung (Restaurants):
  - An vollen Tagen (nicht An-, nicht Abreisetag) erhält Optimierung 1 120 Minuten weniger
    Tagesbudget, sodass ein Mittagsblock von selbst frei bleibt. Liegt der Abreisetag außerhalb der
    optimierten Tage, weil ein Sondertag folgt, gilt jeder Tag außer Tag 1 als voll.
  - Welcher Markt oder welches Café passt, entscheidet nicht der Algorithmus.
    `_trenne_markt_beispiele_ab` sammelt POIs mit `besuchsklasse == "kaffee"` oder Markt-Interesse
    (`ist_markt_bezogenes_interesse`); je vollem Tag werden drei nahe Beispiele rotierend gezeigt.
  - Die Beispielrestaurants (Phase 41) erfassen jetzt zusätzlich `besuchsklasse == "bar"`, weil
    Google eine „urige Kneipe" oft als Bar führt; das LLM nimmt bei gewünschtem lokalem Kontakt einen
    Kneipen-Suchbegriff auf.
  - `_trenne_sonderkategorie_ab` prüft das Prädikat jetzt am ganzen POI, weil die Café-Erkennung über
    `besuchsklasse` läuft.
  - Erkennung nur aus der Antwort auf F19, nicht aus dem ganzen Gespräch. Touren oder Kochkurse mit
    Einheimischen laufen weiter über F04 und F17; Vereine und Gemeinschaftszentren wurden bewusst
    nicht aufgenommen.
- Kein Code-Stand-Snapshot vor der Umsetzung.
- **Verifikation:** live (vier Tage): Tag 1 und 4 ohne Marktbeispiele, Tag 2 und 3 mit je drei
  echten Wochenmärkten; Beispielrestaurants enthalten echte Kneipen; Tage mit reduziertem Budget
  planten sichtbar weniger. Suite 291/291 grün.

## Phase 48 — Korrekturen aus einer 15-Tage-Testreise (17.08.2026)

Auslöser: eine Testreise über 15 Tage, angegeben als Datumsbereich. Jeder gemeldete Punkt wurde mit
Codefundstelle belegt und vor der Umsetzung mit dem Product Owner abgestimmt.

- **Tagesanzahl:** `schaetze_reisedauer_tage()` erkannte nur „X Tage"; ein Datumsbereich fiel auf den
  Standardwert 5 zurück. `_tage_aus_datumsbereich` erkennt nun Bereiche wie „21.8. bis 1.9." auch ohne
  Jahr (neutrales Ankerjahr; Ende vor Start gilt als Jahreswechsel). `max_pois_fuer_reise()` war
  dadurch mitbetroffen und ist mitbehoben.
- **Rückreise:** `rueckreise` war dasselbe Objekt wie `hinreise`. Jetzt erfolgt ein eigener Aufruf
  `reisealternativen(ziel, wohnort)` mit eigener Bewertung, eigenem Verkehrsmittelfilter und eigenem
  Härtetest; die Kostenschätzung nutzt die echten Rückreisekosten.
- **Route bis zum Hotel:** die berechnete Verbindung endete an der Zielstadt („Berlin-Spandau"),
  obwohl der Maps-Link bereits die Unterkunft zeigte. `ziel_fuer_route` nutzt die Unterkunfts-
  koordinaten, sobald F15 bestätigt ist, für beide Richtungen.
- **Web-Darstellung:** Anforderung des Product Owners, alle Reiseelemente anzuzeigen. `als_kartendaten`
  liefert Hin- und Rückreisekarten sowie je Tag ein Feld `vorschlaege` mit Label als reiner Vorschlag.
  Reihenfolge: Hinreise, Unterkunft, Tageskarten mit umrahmtem Vorschlagsblock, Weitere Empfehlungen,
  Rückreise.
- **Kulinarik an Sondertagen:** Beispielrestaurants und Marktvorschläge erschienen auch an reservierten
  Tour- oder Lerntagen; jetzt ausgeschlossen.
- **Mehrtägige Touren:** neues Feld `tour_tage_anzahl`, vom LLM nur bei ausdrücklicher
  Mehrtagesaussage gesetzt und nicht aktiv erfragt. Es werden entsprechend viele Tage reserviert, alle
  mit derselben Beispielauswahl; die Lernaktivität bleibt der letzte Tag, die Tourtage liegen davor.
- **Verifikation:** live mit drei neuen Planungstestfällen: 15 statt 5 Tage; unterschiedliche Hin- und
  Rückreise bis zur Unterkunft; zwei Tourtage ohne Beispielrestaurants. Suite 306/306 grün.

## Phase 49 — Datumsbereich: fehlendes Jahr auf einer Seite (17.08.2026)

Erster Live-Test der Datumserkennung: „15.09. - 18.09.2026" ergab rund 700 statt 4 Tage.

- **Was:** `_tage_aus_datumsbereich` setzte für eine Seite ohne Jahr immer das Ankerjahr, auch wenn die
  andere Seite ein Jahr nannte. Jetzt wird ein gemeinsames Jahr ermittelt und auf beide Seiten
  angewendet; ein echter Jahreswechsel mit zwei genannten Jahren bleibt unberührt. Verifiziert am
  gemeldeten Text (Ergebnis 4).
- Ein nicht eingeplanter Wunsch-Fischmarkt wurde auf Entscheidung des Product Owners nicht untersucht
  (vermutlich Zeitfensterkollision mit einem Tagesstart um 19 Uhr).
- 2 neue Regressionstests, Suite 308/308 grün.

## Phase 50 — Reisedauer: das LLM normalisiert das Datum, der Code rechnet (24.08.2026)

Nach zwei Fehlern im Freitext-Parser (Phasen 48/49) *Entscheidung des Product Owners:* das LLM klärt
Mehrdeutigkeiten im Dialog und liefert eindeutige Daten, die Tagesberechnung bleibt deterministisch
(Grundprinzip 3).

- **Was:** neue Felder `reise_start_datum` und `reise_end_datum` (ISO-Format), als Argumente von
  `speichere_feld` nur bei `reisezeitraum_rohtext`; ungültige Werte werden verworfen. F06 weist das
  LLM an, bei Unsicherheit nachzufragen. `_tage_aus_iso_daten` rechnet die Dauer rein arithmetisch;
  `schaetze_reisedauer_tage` prüft die ISO-Daten zuerst und nutzt den alten Parser nur noch als
  Fallback (dialogfreie Testfälle, kein eindeutiges Datum). Alle drei Aufrufer reichen die Daten durch.
  Die POI-Obergrenze (`max_pois_fuer_reise`) ist bereits die gemeinsame Quelle für Vorschau und
  Planung und profitiert automatisch.
- **Weitere Entscheidungen des Product Owners (24.08.2026):** keine echten Hotelpreise, keine weitere
  Verifizierung der CO₂- und Preistabellen, keine Obergrenze für Café-Zeitfenster, keine mehreren
  Unterkünfte. Eine erzwungene Einplanung ausdrücklich genannter Orte wurde diskutiert (Pflicht-POI
  in Optimierung 1; *verworfen:* zweites Depot) und zurückgestellt.
- **Verifikation:** der Fall aus Phase 49 ergibt 4 Tage und 16 POI-Kandidaten. Suite 315/315 grün.

## Phase 51 — Prozessmodell neu gezeichnet: Grundkonzept und Datenfluss je Feld (24.08.2026)

Das Prozessmodell `Modell_1_Reisebot_Prototyp.drawio` bildete noch den festen Ablauf vor Phase 10 ab.
Anforderung des Product Owners: sichtbar machen, was das LLM tatsächlich tut und was der
deterministische Bereich tut, mit einem Grundkonzept und einer Seite je Frage.

- **Was:** Die Datei liegt in `Fortschritte/`, nicht im Code-Repository; die alte Fassung wurde als
  `Modell_1_Reisebot_Prototyp.alt-vor-2026-08-24.drawio` gesichert. Neu sind 21 Seiten: ein
  Grundkonzept (Nutzer, LLM-Agent mit fünf Werkzeugen, `ReiseAnfrage`, Grenze zum deterministischen
  Layer, POI-Suche, Filter, Sondermechanismen, Optimierung 1 und 2, Härtetest, Reiseplan, Ausgabe) und
  je Fragekatalog-Feld (F01–F20) eine Seite mit dem konkreten Datenfluss. Felder ohne deterministische
  Verwendung (z. B. Name, E-Mail, Reisebegleitung) sind als solche gekennzeichnet. Eine Farblegende
  unterscheidet LLM, Rohfeld, deterministische Filter, Kernoptimierung, externe API und reine Anzeige.
  (Später in zwei Dateien aufgeteilt: Gesamtbild und Datenfluss, siehe Phase 55.)
- **Methodik:** jeder Datenfluss wurde vor dem Zeichnen per Suche nach jedem `anfrage.<feld>`-Zugriff
  in `src/` verifiziert, nicht aus Kommentaren übernommen. Die Datei wurde über ein kleines
  Generator-Skript erzeugt (bei 21 Seiten weniger fehleranfällig als handgeschriebenes XML).
- **Verifikation:** XML wohlgeformt, keine doppelten IDs, keine Kanten ohne Knoten, Umlaute korrekt.
  Nicht in einem diagrams.net-Client visuell geprüft; Layout-Feinschliff ggf. von Hand.

## Phase 52 — POI-Obergrenze nach einem Kostenvorfall von 30 auf 15 gesenkt (24.08.2026)

Auslöser: eine Google-Cloud-Rechnung über rund 100 €, davon 40 € an einem Tag. Analyse:
`hole_reisezeitmatrix` holt je Planungslauf eine vollständige Distanzmatrix über Unterkunft und POIs,
einmal je genanntem Verkehrsmittel. Bei 30 POIs und zwei Verkehrsmitteln ergeben sich rund 1.900
abgerechnete Elemente für einen einzigen Plan; die Kosten wachsen quadratisch mit der POI-Zahl und sind
der dominante Kostentreiber. Ein Teil der Kosten entstand durch Live-Testläufe während der Entwicklung;
für reine Strukturprüfungen wird seither der Mock-Modus bevorzugt.

- **Was:** `_MAX_POIS_FUER_OPTIMIERUNG` von 30 auf 15. *Entscheidung des Product Owners:* ein solcher
  Vorfall darf sich nicht wiederholen. *Akzeptierter Kompromiss:* weniger Kandidaten bei langen Reisen.
- **Empfehlung, nicht umgesetzt:** Budget-Alarm in der Google Cloud Console und ein Distanzmatrix-Cache
  für wiederholte Testläufe.
- 2 Tests aktualisiert, Suite 315/315 grün.

## Phase 53 — POI-Obergrenze auf 10, Flexibilitätsskala auf 1–3 (24.08.2026)

Fortsetzung von Phase 52: 15 war dem Product Owner noch zu hoch. Bei der Herleitung zeigte sich, dass
Flexibilitätsstufe 1 bisher keinen Deckel hatte.

- **Flexibilitätsskala:** von 1–5 auf 1–3 verkleinert. Jede Stufe hat jetzt einen festen Deckel:
  Stufe 1 (durchgeplant) 3 POIs pro Tag, Stufe 2 zwei, Stufe 3 (sehr flexibel) einen
  (`_MAX_POIS_PRO_TAG_JE_FLEXIBILITAETSSTUFE = {1:3, 2:2, 3:1}`). Pufferpausen: Stufe 2 alle 150 Minuten
  20 Minuten, Stufe 3 alle 90 Minuten 30 Minuten, Stufe 1 keine; diese Zuordnung übernimmt die Werte der
  bisherigen Stufen 4 und 5 und ist nicht vom Product Owner vorgegeben. Ohne Signal bleibt es
  unbegrenzt. Werkzeugschema, Kontexthinweis F05 und Schema angepasst.
- **POI-Obergrenze:** von 15 auf 10, hergeleitet aus der strengsten Stufe (3 POIs pro Tag) über drei
  Tage plus ein Kandidat als Reserve für „Weitere Empfehlungen" (Vorgabe des Product Owners). Mit dem
  unveränderten Minimum von 8 liegt der wirksame Bereich bei 8–10; die Tagesskalierung wirkt dadurch
  kaum noch, die Obergrenze ist die maßgebliche Schutzgrenze gegen Kostenausreißer.
- **Abgrenzung:** die Pool-Obergrenze (Kandidaten für die ganze Reise) und der Flexibilitätsdeckel
  (eingeplante POIs pro Tag) sind verschiedene Mechanismen; der Pool muss größer bleiben, damit
  Optimierung 1 eine echte Auswahl hat.
- Tests auf die neue Skala umgestellt, bewusst ohne Live-Test. Suite 315/315 grün.

## Phase 54 — Flexibilitätseinstufung: einfaches „flexibel" gehört zu Stufe 3 (26.08.2026)

Erster Live-Test der neuen Skala: auf „gerne flexibel" speicherte das LLM Stufe 2 statt 3 (Protokoll:
„flexibel, kein straffes Programm", Stufe 2). Ursache: die frühere Formulierung verlangte für die
oberste Stufe eine gesteigerte Aussage („extrem flexibel"), was bei drei Stufen nicht mehr passt.

- **Was:** Kontexthinweis F05 und Werkzeugbeschreibung ergänzt: ein einfaches „flexibel" oder „spontan"
  reicht für Stufe 3, ein einfaches „durchgeplant" oder „fest" für Stufe 1; Stufe 2 nur bei erkennbar
  gemischter Aussage. Der beobachtete Fall steht als Negativbeispiel im Prompt.
- Reine Prompt-Änderung, Suite 315/315 grün. Die Wirkung ist nur im Live-Test prüfbar; eine
  zusätzliche Protokollierung der rohen Nutzernachricht lehnte der Product Owner ab.

## Phase 55 — Fragekatalog: F18 in F09 integriert, F04 verschoben (07.09.2026)

Reine Reihenfolge- und Zuschnittsänderung auf Entscheidung des Product Owners, ohne neues Feld.

- **F18 in F09:** Die eigene Frage nach Ernährungsbedürfnissen und Allergien entfällt; F09
  (gesundheitliche Einschränkungen) fragt Unverträglichkeiten mit ab. Das LLM hakt nur nach, wenn eine
  genannt wird. Befüllt wird `ernaehrung_einschraenkungen` über ein gleichnamiges Argument von
  `speichere_feld(feld="gesundheitliche_einschraenkungen")`; das Schemafeld bleibt für Restaurantsuche
  und Verträglichkeitsprüfung bestehen. *Warum:* beide Fragen betreffen gesundheitsbezogene
  Einschränkungen und sollen nicht nacheinander getrennt gestellt werden.
- **F04 verschoben:** die Frage nach einer Reiseleitung steht nun direkt vor F17 (Lernaktivität);
  `id`, `stufe` und `cluster` bleiben für die Rückführbarkeit unverändert. *Warum:* beide fragen im
  Kern, ob man sich vor Ort etwas zeigen oder vermitteln lassen möchte.
- Suite 315/315 grün, betroffene Kommentare angepasst.
- **Offen:** die beiden Prozessmodell-Dateien (`..._Gesamtbild.drawio`, `..._Datenfluss.drawio`) zeigen
  F04 und F18 noch am alten Ort.
- **Diskutiert, nicht geändert:** F20 (Tagesablauf) bleibt, weil es das tatsächliche Tagesbudget von
  Optimierung 1 bestimmt und als optionales Feld mit Fallback wenig Gesprächslast erzeugt.

---

**Iteration 1 abgeschlossen am 07.09.2026.** Ab Phase 56 beginnt Iteration 2 mit dem Demo-Feedback
aus der Demo von Iteration 1.

---

## Phase 56 — Iteration 2 beginnt: Demo-Feedback zur Web-Oberfläche (09.09.2026)

Fünf Rückmeldungen aus der Demo von Iteration 1; Konzepte mit dem Product Owner abgestimmt. Ausführliche
Begründung in [Station 28](doku/28_stage28_iteration2_ux_feedback_konzepte/README.md).

- **Layout:** Ab 980 px Breite steht der Reiseplan in einer zweiten Spalte neben dem Chat (CSS Grid).
  *Warum:* Wunsch aus dem Demo-Feedback. (In Phase 57 präzisiert.)
- **Zeitanzeige:** An Tag 1 und an Tagen ohne F20-Antwort zeigte der Plan eine relative Dauer
  („ab 1h – bis 2h"), die im Demo-Feedback als Aufenthaltsdauer gelesen wurde. Neu: ein angenommener
  Standard-Tagesbeginn (09:00) mit „ca."-Präfix und erklärendem Hinweis. *Warum:* die relative
  Darstellung war ursprünglich gewählt, um keine erfundene Uhrzeit zu zeigen; sie erwies sich aber als
  missverständlich. „ca." sollte die Annahme kenntlich machen. (In Phase 58 revidiert.)
- **Schnellantworten:** reine, vom LLM gesteuerte Konvention statt deterministischer Verdrahtung
  (Grundprinzip 1). Das Regelwerk erlaubt eine letzte Nachrichtenzeile
  `[SCHNELLANTWORTEN: Option 1 | Option 2]` (höchstens vier). `zerlege_schnellantworten` trennt sie
  ab, `WebIOKanal.bot_sagt` sendet die Optionen mit, die Oberfläche zeigt Klick-Chips. Kein sechstes
  Werkzeug. *Entscheidung des Product Owners:* Chips schränken die Eingabe nie ein, und ihr Inhalt
  bleibt beim LLM statt fest im Code.
- **Ladeindikator:** (a) eine animierte Tipp-Blase nach jedem Senden, (b) `IOKanal.zeige_status(phase)`
  mit eigenem WebSocket-Signal, das `plane_reise_und_abschliessen` kurz vor der blockierenden Planung
  auslöst (neues optionales Feld `AgentSessionState.io_kanal`). *Warum:* die bekannte lange Laufzeit
  bei Barrierefreiheitsprüfungen (Phase 44) sollte von einer normalen Denkpause unterscheidbar sein.
- **Bot-Avatar:** kleines Icon neben jeder Bot-Nachricht, bewusst schlicht. (In Phase 58 ersetzt.)
- Code-Duplikat gesichert. Neue und angepasste Tests, Suite 325/325 grün. Layout und Avatar noch nicht
  im Browser geprüft; das Schnellantwortverhalten hängt vom LLM ab.

## Phase 57 — Chat bleibt bis zum Abschluss zentriert (17.09.2026)

- **Was:** Der erste Browser-Test zeigte das Zweispalten-Layout bereits während des Gesprächs. Das Grid
  gilt jetzt nur für `main.abgeschlossen`, eine Klasse, die `zeigeErgebnis()` erst beim Eintreffen des
  fertigen Plans setzt. Vorher bleibt der Chat groß und zentriert, ohne Andeutung des Planbereichs. Der
  Platzhalter entfällt; der Planungshinweis erscheint als eigene Nachricht im Chat. (Layout während
  des Gesprächs in Phase 66 revidiert.)
- **Warum:** Entscheidung des Product Owners. Phase 56 hatte „genug Platz für zwei Spalten" mit „Plan
  soll sichtbar sein" gleichgesetzt; beide Bedingungen müssen erfüllt sein. Ohne Browser-Test wäre das
  nicht aufgefallen.
- [Station 29](doku/29_stage29_layout_chat_bis_abschluss_zentriert/README.md) mit Code-Duplikat. Suite
  325/325 grün, JavaScript-Syntax geprüft; der Übergang selbst noch nicht im Browser beobachtet.

## Phase 58 — Zeitanzeige, Fotos, Standardbilder, Verleihkarte, Layout, Avatar (17.09.2026)

Sechs Rückmeldungen des Product Owners nach Nutzung der Web-Oberfläche, vor der Umsetzung als Aufgaben
gefasst und abgestimmt. Details in [Station 30](doku/30_stage30_zeit_fotos_verleih_layout_avatar/README.md).

- **Zeitanzeige:** statt einer angenommenen Uhrzeit eine relative Dauer mit Ankerwort am Wert
  („15min nach Ankunft", „… nach Tagesbeginn") für alle Tage ohne bekannte Zeit. Die Konstante für den
  Standard-Tagesbeginn entfällt. *Warum:* Entscheidung des Product Owners, keine, auch keine markierte,
  Uhrzeit zu behaupten; das Ankerwort an jedem Wert verhindert die Fehllesung als Aufenthaltsdauer.
- **Fotos (Fehler):** `lade_fotos_fuer_plan` lud nur Fotos für Unterkunft und eingeplante POIs; alle
  Vorschlags- und Empfehlungskarten blieben ohne Foto. Jetzt alle Karten inklusive Verleih. Neuer
  Fallback `hole_foto_referenz` (Place Details) für Orte ohne Foto in der Suchantwort, nur für die
  Karten des fertigen Plans.
- **Standardbilder für An- und Abreise:** eigene Illustrationen für Bahn, Auto und Fernbus, zugeordnet
  über `_standardbild_url`; unbekannte Verkehrsmittel ohne Bild. (In Phase 60 durch Fotos ersetzt.)
- **Verleihkarte:** `als_kartendaten` liefert ein Feld `verleih`, angezeigt direkt unter der Unterkunft
  (Entscheidung des Product Owners), ohne Vorschlagslabel, weil im Dialog bestätigt. Eine Fehlanzeige
  bleibt Text.
- **Layout:** im Abschlusszustand sitzt der Chat vertikal mittig und sticky, schmaler, mit mehr Abstand
  zum Reiseplan, der damit der dominante Bereich ist. (In Phase 66 durch ein einklappbares Chat-Panel
  ersetzt.)
- **Avatar:** zunächst Gesichts-Emoji, dann nach einer Stilvorgabe des Product Owners ein eigener,
  neu gezeichneter Bot-Charakter mit Kopf und Oberkörper (`static/img/avatar.svg`, eigenes Original).
  Eine sichtbare Naht zwischen zwei Formen wurde durch eine durchgehende Pfad-Silhouette behoben und per
  Headless-Browser-Screenshot geprüft.
- Code-Duplikat für die ersten fünf Punkte. Suite 335/335 grün. Offen: Layout nicht pixelgenau
  abgestimmt; Foto-Fallback nicht gegen die echte API geprüft.

## Phase 59 — Schnellantworten-Anweisung nachgeschärft (21.09.2026)

- **Befund:** Im ersten beobachteten Chat bot das LLM bei einer Frage mit vier selbst genannten
  Optionen (Reisebegleitung) keine Chips an, obwohl die Anweisung das erlaubte.
- **Was:** Abschnitt SCHNELLANTWORTEN in `regelwerk.py`: Chips sind der Regelfall; nennt das LLM im
  Fragetext Beispielantworten, muss es dieselben als Chips anhängen; konkrete Katalogbeispiele und eine
  Liste echt offener Fragen ohne Chips ergänzt.
- **Warum:** Die Technik war fertig, die Lücke lag im Prompt. Grundprinzip 1 bleibt gewahrt.
- [Station 31](doku/31_stage31_schnellantworten_nachgeschaerft/README.md) mit Code-Duplikat. Suite
  335/335 grün; Wirkung nur im Live-Test prüfbar.

## Phase 60 — Echte Fotos für An- und Abreise, Eingabezeile nach Abschluss ausgeblendet (21.09.2026)

Details in [Station 32](doku/32_stage32_echte_reisefotos_eingabe_ausblenden/README.md).

- **Fotos:** Auf Wunsch des Product Owners, der zwei Referenzfotos als Stilvorgabe lieferte, ersetzen
  lizenzfreie Unsplash-Fotos die Illustrationen: `bahn.jpg` (Markus Winkler), `auto.jpg` (Averie
  Woodard), `bus.jpg` (C/@thecurlyone, zur Stilkonsistenz ergänzt). Jeder Kandidat wurde visuell
  geprüft, weil Suchbeschreibungen mehrfach nicht zum Bildinhalt passten; ein kostenpflichtiges
  Unsplash+-Bild wurde verworfen.
- **Eingabezeile:** im Abschlusszustand ist keine Eingabe mehr möglich; die Zeile wird jetzt
  ausgeblendet (`form.hidden`, mit CSS-Regel gegen das überschreibende `display: flex`).
- **Nebenfund:** `pytest.ini` schloss `doku/` nicht von der Testsammlung aus, sodass eine in
  `code_stand/` kopierte Testdatei mitlief und fehlschlug. Behoben über `norecursedirs`. *Warum dort:*
  Snapshots sollen auch Testdateien enthalten dürfen, ohne die Suite zu verfälschen.
- Code-Duplikat gesichert. Suite 335/335 grün. Offen: Erkennbarkeit des kleinen Busses im
  Kartenausschnitt nicht im Browser geprüft.

## Phase 61 — Chatverlauf ohne horizontales Scrollen (21.09.2026)

- **Befund:** horizontaler Scrollbalken im Chat trotz umbrochenem Text.
- **Was:** drei Ursachen in `static/index.html`: `#verlauf` setzte nur `overflow-y`, wodurch laut
  CSS-Spezifikation auch `overflow-x` auf „auto" stieg (jetzt explizit `hidden`); `.nachricht` fehlte
  `overflow-wrap`; `.hotel-karte-wrapper` hatte eine feste Breite von 220 px (jetzt `width: 100%` mit
  `max-width: 220px`); zusätzlich `min-width: 0` für `.nachricht-zeile`.
- **Warum:** jede Ursache allein konnte den Überlauf erzeugen.
- Verifiziert mit einer Testseite (Original-CSS, extrem langes Wort und langer Link) im
  Headless-Browser: nur noch vertikales Scrollen. Suite 335/335 grün. Kein Code-Duplikat.

## Phase 62 — Verleihkarte mit Route ab der Unterkunft (21.09.2026)

- **Was:** `als_kartendaten` berechnet für die Verleihkarte einen `routen_link` über die bestehende
  Funktion `routen_link()`, von der Unterkunft zum Verleih, zu Fuß; ohne Unterkunftskoordinaten `None`.
  Keine Frontend-Änderung nötig, `karteHtml()` rendert das Feld generisch.
- **Warum:** Wunsch des Product Owners nach Konsistenz mit den übrigen Kartenarten.
- 1 neuer Test, Suite 336/336 grün. Kein Code-Duplikat. Nicht im Browser geprüft.

## Phase 63 — Dokumentation für Leser der Arbeit aufbereitet (29.09.2026)

- **Was:** Entscheidungslog, Stationsbeschreibungen in `doku/`, README, Docstrings und Kommentare
  sachlich für Leser der Masterarbeit formuliert und auf Auslöser, Entscheidung, Begründung,
  Alternativen und Verifikation reduziert. Neue [`ARCHITEKTUR.md`](ARCHITEKTUR.md) beschreibt den
  aktuellen Stand im Repository. Die Testübersicht in `tests/conftest.py` wurde durch eine aktuelle
  Zuordnung Testdatei zu Modul ersetzt. Keine Änderung am Programmverhalten; Prompt-Texte an das LLM
  bleiben unverändert. Die `code_stand/`-Ordner bleiben als unveränderte Belege erhalten.
- **Warum:** Entscheidung des Product Owners, dass die Code-Dokumentation direkt als Grundlage für die
  Arbeit dienen soll. Die vorherige, ausführlichere Fassung ist in der Git-Historie erhalten.
- Suite 336/336 grün.

## Phase 64 — Formatierter Bot-Text, keine Quellenliste nach den Schnellantworten (29.09.2026)

Demo-Feedback aus der Demo von Iteration 2 (`Program/Iteration 2/Feedback Demo Iteration 2.txt`,
Punkte „Textformatierung" und „Zusatzelemente"): Fett gemeinte Stellen erschienen im Browser mit
Sternchen (Beleg: `protokolle/web_2026-09-21_120230.jsonl`, Zeilen 15–17 und 28). Außerdem stand in
einzelnen Nachrichten die Zeile „[SCHNELLANTWORTEN: …]" roh im Text, gefolgt von einer
„Sources:"-Liste. Präzisierung des Product Owners: Die Klick-Chips bleiben erhalten, zu vermeiden ist
nur diese rohe Zeile samt Quellenliste. Ursache: Nach einer Websuche hängt das LLM die Quellenliste
hinter die Schnellantworten-Zeile; `_SCHNELLANTWORTEN_MUSTER` greift wegen des `$`-Ankers nur am
Nachrichtenende und erkennt die Zeile dann nicht.

- **Was (Oberfläche):** eigener kleiner Renderer in `static/index.html` (Block
  BOT-TEXT-FORMATIERUNG: `formatiereBotText`, `formatiereZeile`, `botTextAlsKlartext`). Der gesamte
  Text wird zuerst HTML-escaped, einschließlich `"` und `'`; erst danach werden gezielt `<strong>`,
  `<ul><li>` für „- "-Zeilen und `<a target="_blank" rel="noopener noreferrer">` eingesetzt, Links
  nur mit http/https-Adresse. Nur Bot-Nachrichten werden formatiert; Nutzer-, System- und
  Statusnachrichten bleiben reiner Text. Vorgelesen wird der Text ohne Markdown-Zeichen, bei Links
  nur der Linktext.
- **Was (Konsole/Audio):** neue Funktion `entferne_markdown(text, links_mit_adresse=False)` in
  `src/audio/kanal.py`. `TextKanal` zeigt Links als „Text (URL)", `AudioKanal` spricht nur den
  Linktext. `zerlege_schnellantworten` bleibt unverändert und läuft vor der Markdown-Entfernung.
- **Was (Regelwerk):** `_TOOL_ANLEITUNG` in `regelwerk.py` erhält einen Absatz FORMATIERUNG (nur
  **fett** und einfache „- "-Aufzählungen, keine Überschriften oder Tabellen, Fettdruck sparsam). Im
  Abschnitt SCHNELLANTWORTEN ist die Zeile immer die allerletzte, danach folgt nichts. Im Abschnitt
  WEBSEARCH ist eine Quellen-, „Sources:"- oder Linkliste untersagt; die Kennzeichnung als Recherche
  im Fließtext bleibt.
- **Warum:** Die Auszeichnung soll dargestellt statt roh angezeigt werden, ohne dass vom LLM
  gelieferte Tags ausgeführt werden. Die Quellenliste wird nach Entscheidung des Product Owners nur
  per Prompt-Anweisung unterbunden, ohne Änderung am Parser.
- *Verworfen:* eine externe Markdown-Bibliothek (Umfang, zusätzliche XSS-Angriffsfläche); eine
  serverseitige HTML-Umwandlung; ein vollständiger Markdown-Parser; das Herausfiltern der
  Quellenliste per Code (bewusst nur Prompt); das Ausblenden der Chips (Missverständnis des
  Feedbacks, siehe Präzisierung).
- Neue Tests `tests/test_regelwerk.py` und `tests/test_bot_text_formatierung.py` (führt den JS-Block
  per Node.js aus, ohne Node.js übersprungen), Erweiterungen in `tests/test_kanal.py`, Übersicht in
  `tests/conftest.py` ergänzt. Komplette Suite grün (355/355).
- [Station 35](doku/35_stage35_bot_text_formatierung/README.md). Kein `code_stand`-Snapshot
  (transparent vermerkt).
- **Offen:** Wirksamkeit der Prompt-Regel gegen die Quellenliste erst im nächsten Live-Test prüfbar;
  Darstellung im Browser nicht manuell geprüft; der JS-Test nutzt eine DOM-freie `escapeHtml`-Variante
  gleicher Wirkung.

## Phase 65 — Umweltfreundlichste Auto-Route für An- und Abreise (29.09.2026)

Demo-Feedback aus der Demo von Iteration 2 (Punkt „Routenwahl"): Bei der An- und Abreise mit dem
Auto soll stets die Route gewählt werden, die Google Maps als umweltfreundlichste (kraftstoffsparendste,
mit grünem Blatt) kennzeichnet. Eco-Routing bietet nur die Routes API, nicht die bisher genutzte Legacy
Directions API (Google-Dokumentation „eco-routes").

- **Was:** Die Auto-Alternative in `GoogleMapsClient.reisealternativen` kommt aus
  `_hole_auto_route_umweltfreundlich`: `POST https://routes.googleapis.com/directions/v2:computeRoutes`
  mit `X-Goog-FieldMask` = `routes.duration`, `routes.distanceMeters`, `routes.routeLabels`,
  `geocodingResults`; Body `travelMode` DRIVE, `routingPreference` TRAFFIC_AWARE_OPTIMAL,
  `requestedReferenceRoutes` ["FUEL_EFFICIENT"], `languageCode` de, ohne `vehicleInfo` (Google-Standard
  Benzin). `_waehle_umweltfreundlichste_route` nimmt die Route mit Label FUEL_EFFICIENT unabhängig von
  ihrer Position, sonst DEFAULT_ROUTE, sonst die erste. Das neue Feld
  `ReiseAlternative.umweltfreundlichste_route` (True/False, None bei Bahn und Fernbus) macht den
  Rückfall erkennbar, zusätzlich eine `logging.warning` (erstmals `logging` in `src/`).
- **Fehlerverhalten:** Leere `routes`, auch bei nicht auflösbarem Ort (HTTP 200 mit `geocoderStatus`
  ungleich OK, `_nicht_aufgeloeste_orte`), ergeben wie bisher `None`. HTTP ≥ 400 führt zu einem
  `RuntimeError` mit verständlicher Meldung (`_routes_api_fehlermeldung`, bei 401/403 Hinweis auf
  Aktivierung der Routes API und Key-Einschränkungen), ohne Rückfall auf die Legacy-API.
- Kosten weiter `distanz_km × _KOSTEN_JE_KM_SCHAETZUNG_EURO["driving"]`, `teilstrecken` leer. Bahn und
  Fernbus unverändert über die Legacy Directions API. Die Schnittstelle `reisealternativen` bleibt
  gleich, daher nutzen `pipeline.py` und der F13-Dialog (`vorschlaege.py`) die Route ohne Änderung.
  Die Auto-Alternative der Mock-Daten (`mock_data.py`) trägt `umweltfreundlichste_route=True`.
- **Warum:** Präzisierung des Product Owners zum Feedback: bei der Auto-Route der An- und Abreise
  immer die von Google Maps als umweltfreundlichste gekennzeichnete Route.
- *Verworfen:* Legacy Directions mit `alternatives=true` (keine Umwelt-Kennzeichnung); automatischer
  Rückfall auf die Legacy-API bei Fehlern (eine nicht ermittelte Eco-Route bliebe unsichtbar);
  Fahrzeugtyp beim Nutzer erfragen bzw. `vehicleInfo` setzen (vom Product Owner ausgeschlossen);
  `routeToken` anfordern (laut Google nur für das Navigation SDK nötig); Auswahl nach Array-Position
  statt nach Label (Reihenfolge nicht garantiert).
- Neue Tests in `tests/test_google_maps.py` (38 Tests): FUEL_EFFICIENT an zweiter Stelle, Rückfall,
  fehlende Labels, leere Antwort, nicht auflösbarer Ort, HTTP 403, Anfrageinhalt, Dauer-Parser,
  Mock ohne Netz. Komplette Suite grün (364/364). Nicht gegen die echte Routes API geprüft. (Live
  bestätigt und Wegpunkt-Format korrigiert in Phase 68.)
- **Betriebsvoraussetzung:** Routes API im Google-Cloud-Projekt aktivieren und ggf. in die
  Key-Einschränkungen aufnehmen. Abrechnung über die SKU „Compute Routes Pro".
- [Station 36](doku/36_stage36_umweltfreundliche_autoroute/README.md) mit Code-Duplikat.
- **Offen:** siehe Offene Punkte (Routenlink, Abfahrtszeit, Anzeige des Flags, Länderabdeckung,
  Antwortformate).

## Phase 66 — Gesamtdesign der Web-Oberfläche mit Urlaubsgefühl (29.09.2026)

Demo-Feedback aus der Demo von Iteration 2 (`Program/Iteration 2/Feedback Demo Iteration 2.txt`,
Punkte „Gestaltung des Reiseplans" und „Chat-Bereich"): Das Seitenkonzept soll überarbeitet werden;
die gesamte Oberfläche soll während des Gesprächs und bei der Ausgabe des Plans ansprechender wirken
und ein Urlaubsgefühl vermitteln, etwa durch wechselnde Urlaubsbilder neben dem Chat. Der Chat soll
größer sein und sich nach Abschluss der Planung ausblenden lassen. Präzisierung des Product Owners:
Vorbilder bei etablierten Reiseportalen suchen und übertragbare Elemente übernehmen.

**Herkunft der Gestaltungselemente** (Recherche vom 29.09.2026):

| Element im Prototyp | Vorbild | Quelle |
|---|---|---|
| Viel Weißraum, große Foto-Karten mit Rundung, Schatten und Hover-Effekt | Airbnb (klare, elegante Startseite, zentrales Suchfeld, große Fotos) | https://mediaboom.com/news/travel-website-design/ |
| Eckdaten-Chips direkt unter dem Titel | Booking.com (Fakten und Vertrauenssignale nahe am Entscheidungspunkt) | https://mediaboom.com/news/travel-website-design/ ; https://econsultancy.com/excellent-examples-content-design-ux-travel-websites/ |
| Galerie „Inspiration" neben dem Chat | Mindtrip (Fotos, Karten und Bewertungen in einer Ansicht neben dem Chat) | https://www.travelanywhere.blog/blog/best-agentic-ai-travel-apps-2026-mindtrip-layla-stippl-stardrift-wanderlog-tested |
| Tage als vertikale Zeitleiste | Wanderlog (Programm nach Tagen gruppiert) | https://www.travelanywhere.blog/blog/best-agentic-ai-travel-apps-2026-mindtrip-layla-stippl-stardrift-wanderlog-tested |
| Titelbild und großflächige Galerie | Trend zu immersiven, großflächigen Bildern | https://mediaboom.com/news/travel-website-design/ ; https://www.designmonks.co/blog/travel-website-design-examples |

Die Vergleichsartikel beschreiben die Portale überwiegend funktional und Designdetails nur knapp. Die
Übertragung auf den Prototyp ist daher eine eigene Gestaltungsentscheidung auf Basis dieser
Beschreibungen, keine Nachbildung einzelner Portale.

- **Was (Daten für den Titelbereich):** `Reiseplan` in `src/ausgabe/reiseplan.py` erhält die Felder
  `reisezeitraum_rohtext`, `reise_start_datum` und `reise_end_datum`, die `src/pipeline.py` wie
  `budget_gesamt` unverändert aus der Anfrage übernimmt. Neue Konstante `ZIELORT_PLATZHALTER`
  („Zielregion", jetzt auch in `pipeline.py` verwendet); der Platzhalter gilt in den Eckdaten als
  „kein Zielort". `_zeitraum_text` zeigt „TT.MM.JJJJ – TT.MM.JJJJ" nur, wenn beide ISO-Daten lesbar
  sind (`_iso_als_deutsches_datum`), sonst den Rohtext der F06-Antwort, sonst nichts. `als_kartendaten`
  liefert zusätzlich `eckdaten` (`_eckdaten`: Zielort, Zeitraum, Anzahl Tage, Verkehrsmittel hin und
  zurück, `co2_an_abreise_kg` als Summe von Hin- und Rückreise auf eine Nachkommastelle, Kosten pro
  Person, `kosten_unvollstaendig`) und `titelbild_url` (`_titelbild_url`: Foto der Unterkunft, sonst
  erstes POI-Foto in Tagesreihenfolge, sonst `None`). Es entstehen keine zusätzlichen API- oder
  Foto-Anfragen.
- **Was (Gesprächsansicht, `static/index.html`):** Ab 980 px Breite ein Grid mit dem Chat als
  Hauptelement (ca. 60 %, `3fr`/`2fr`) in fast voller Fensterhöhe; die Eingabezeile steht unten, nur
  der Verlauf scrollt, `overflow-x: hidden` bleibt. Rechts eine Galerie-Spalte, sichtbar beschriftet
  mit „Inspiration · Stimmungsbilder, kein Reisevorschlag" und mit Bildnachweis je Bild (Kennzeichnung
  in Phase 70 durch eine Beschriftung je Bild ersetzt). Zwei `img`-Ebenen blenden alle 7 s über
  1,4 s über; das nächste Bild erscheint erst nach vollständigem Laden, das Startbild ist zufällig. Bei `prefers-reduced-motion` bleibt ein Standbild. Unter 980 px
  steht ein 96 px hohes Bildband über dem Chat, der Chat nutzt `100dvh`. Mit dem Abschluss wird die
  Galerie ausgeblendet und der Wechsel gestoppt (`stoppeGalerie`).
- **Was (Bilder):** zehn Unsplash-Fotos in `static/img/galerie/` (157–283 KB; Landschaften, Seen,
  Küsten und Bergbahnen in Europa, keine Personen im Vordergrund, nur als „Free" gekennzeichnete
  Fotos, kein Unsplash+). Herkunft je Datei (Motiv, Fotograf, Unsplash-Seite, Unsplash License) in
  `static/img/galerie/QUELLEN.md`. Fotograf und Lizenzhinweis wurden aus Internet-Archive-Kopien der
  Fotoseiten gelesen, weil unsplash.com automatisierte Abrufe mit einer Bot-Prüfung blockiert. Die
  Bilder wurden einmalig vom Unsplash-CDN geladen und werden lokal ausgeliefert.
- **Was (Farbwelt und Schrift):** Sandton `#f7f1e6` als Hintergrund, Meerblau `#1f5f7a` als zweiter
  Akzent; Grün `#2f6f4f` bleibt der Nachhaltigkeitsakzent. Überschriften in einem System-Serif-Stack
  (Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia), ohne externe Schriftquelle.
- **Was (Ergebnisansicht):** Titelbereich „Deine Reise nach {Zielort}" bzw. „Deine Reise" mit
  Titelbild, ohne Foto ein Farbverlauf von Meerblau zu Grün, dunkler Verlauf für den Textkontrast.
  Darunter Eckdaten-Chips (Block ECKDATEN-CHIPS): Zeitraum, „n Tage"/„1 Tag", Verkehrsmittel einmal
  oder „Hin: X · Zurück: Y", „CO₂ An-/Abreise: x kg", „ca. x € p. P." bzw. mit „(ohne Unterkunft)" bei
  unvollständiger Schätzung; fehlt ein Wert, entfällt der Chip. Danach der Nudge, dann die Tage als
  vertikale Zeitleiste (`ol.zeitleiste`) unter „Tag für Tag". (Chip-Optik und Nudge in Phase 68
  revidiert.) Die Reihenfolge bleibt unverändert
  (Hinreise, Unterkunft, Verleih, Tage, Weitere Empfehlungen, Rückreise, Volltext), ebenso der
  Vorschläge-Rahmen direkt nach den POI-Karten eines Tages. Karten mit 180 px hohem Foto, Radius
  18 px, Schatten und Hover-Effekt.
- **Was (Chat nach Abschluss):** standardmäßig eingeklappt. Ein schwebender Knopf „Chat"/„Chat
  schließen" (`aria-expanded`, Escape schließt) öffnet ein überlagerndes Panel mit dem vollständigen
  Verlauf; die Eingabezeile bleibt ausgeblendet (Phase 60). (In Phase 68 revidiert: Gesprächsverlauf
  standardmäßig sichtbar.)
- Unverändert funktionsfähig: Schnellantwort-Chips, Mikrofon und Vorlesen, Hotel-Vorschaukarte (F15),
  Status-Sprechblase, Tipp-Animation, Avatar, Verleihkarte, Links und Volltext. Der Block
  BOT-TEXT-FORMATIERUNG aus Phase 64 ist byte-identisch.
- **Revision früherer Entscheidungen:** Phase 57 hatte festgelegt, dass der Chat während des Gesprächs
  groß und zentriert bleibt, ohne Andeutung des Planbereichs. Jetzt teilt er sich die Breite mit der
  Galerie. Das bleibt mit dem Anliegen von Phase 57 vereinbar, weil die Galerie ausdrücklich als
  Inspiration gekennzeichnet ist und nicht als Planbereich wirkt (Kennzeichnung in Phase 70
  entfernt). Das Abschlusslayout aus Phase 58
  (schmaler Chat links, sticky) ist durch das einklappbare Panel ersetzt.
- **Warum:** Demo-Feedback (Urlaubsgefühl, wechselnde Bilder neben dem Chat, größerer und
  ausblendbarer Chat) und Präzisierung des Product Owners, Vorbilder aus etablierten Reiseportalen zu
  übernehmen (siehe Tabelle). Eckdaten und Titelbild werden ausschließlich aus bereits berechneten
  Werten abgeleitet; fehlt ein Wert, wird nichts geschätzt (Grundprinzip 1).
- *Verworfen:* eine interaktive Karte nach dem Vorbild von Wanderlog (erfordert den Google-Schlüssel
  im Browser, verletzt das Grundprinzip, dass der Schlüssel den Browser nie erreicht); eine externe
  Schriftquelle (Font-CDN) und das direkte Einbinden der Unsplash-Bilder (keine externen Anfragen zur
  Laufzeit); ein Symbolbild als Titelbild-Rückfall (würde fälschlich wie der Zielort wirken, daher
  Farbverlauf); ein harter Bildwechsel bei reduzierter Bewegung (stattdessen Standbild).
- Neue Tests: 9 Eckdaten- und Titelbild-Tests in `tests/test_reiseplan.py`; `tests/test_galerie.py`
  (5 Tests: `QUELLEN.md` und Dateien 1:1, Vollständigkeit der Angaben, Dateigröße unter 300 KB,
  `GALERIE_BILDER` im Skript passend zu den Dateien, keine externen Einbindungen);
  `tests/test_eckdaten_chips.py` (5 Tests, führt den Chip-Block per Node.js aus). Komplette Suite grün
  (383/383). JavaScript-Syntax mit `node --check` geprüft. Sichtprüfung im Headless-Chrome mit einem
  Beispielplan bei 1280, 500 und 390 px Breite: kein horizontales Scrollen bei 390 px, Chat-Panel
  öffnet und schließt, Reihenfolge korrekt.
- Nicht geprüft: ein echtes Gespräch mit dem LLM und echten Google-Fotos, das Überblenden in
  Echtzeit, reduzierte Bewegung im echten Browser, Safari, Firefox und Mobilgeräte. Kontraste nur
  rechnerisch ermittelt.
- [Station 37](doku/37_stage37_urlaubsdesign_oberflaeche/README.md) mit Code-Duplikat.
- **Offen:** siehe Offene Punkte (CO₂-Chip nur An- und Abreise, Bildmetadaten, Sicherheitshinweis,
  Sichtprüfung, Zeitleisten-Punkt).

## Phase 67 — Fester Termin für ausdrücklich gewünschte Orte (29.09.2026)

Demo-Feedback aus der Demo von Iteration 2 (`Program/Iteration 2/Feedback Demo Iteration 2.txt`,
Punkt „Berücksichtigung dedizierter Standorte"): Nennt der Nutzer ausdrücklich einen Ort, den er unter
allen Umständen sehen möchte, wird an einem Tag ein fester Zeitslot freigehalten und der Ort direkt
dort eingetragen, ohne ihn an den Optimierungsalgorithmus zu übergeben. Liegt der Ort sehr weit
entfernt, soll auf die Auswirkungen auf die Nachhaltigkeit hingewiesen werden. Präzisierung des
Product Owners: Der Wunschort darf nie aussortiert werden; bei großer Entfernung entscheidet der
Nutzer nach dem Hinweis selbst. Das Muster folgt den Touren und Lernaktivitäten, die ebenfalls
außerhalb von Optimierung 1 eingetragen werden (Phasen 44 und 46). Die Umsetzung gliedert sich in vier
Teile.

### D1 — Wunschort erkennen und finden

- **Was (Datentypen):** Neuer Typ `GefundenerOrt` in `src/api/typen.py` (Name, Adresse, x/y,
  `place_id`, `kategorie`, `foto_referenz`, `preisniveau`). In `src/fragekatalog/schema.py` die
  Dataclass `FesterWunschort` (`rohname`, `ort`, `dauer_minuten`, `uhrzeit_minuten`, `barrierefrei`,
  `barrierefreiheit_geprueft`, `anfahrt`, `anfahrt_geprueft_ab`) und das Feld
  `ReiseAnfrage.feste_wunschorte`.
- **Was (Suche):** `MapsClient.finde_ort(suchtext, nahe_bei)` in `src/api/google_maps.py` nutzt die
  Places Text Search (`place/textsearch/json`). Der Suchtext enthält bewusst kein „in {Ziel}", weil
  ein Wunschort außerhalb der Zielregion liegen darf. Der Ortsbezug wird über `location`/`radius`
  hergestellt (`_FINDE_ORT_BEZUG_RADIUS_METER` = 50 000); die Text Search gewichtet damit nur und
  schließt nichts aus. Aus mehreren Treffern wird der nächstgelegene gewählt (`_naechster_treffer`).
  ZERO_RESULTS ergibt `None`, ein API-Fehler einen `RuntimeError`. Der Mock-Modus nutzt
  `BEISPIEL_WUNSCHORTE` in `mock_data.py`.
- **Was (Dialog):** Neues Modul `src/fragekatalog/wunschorte.py` (u. a.
  `STANDARD_BESUCHSDAUER_WUNSCHORT_MINUTEN` = 120, `loese_wunschorte_auf`,
  `pruefe_barrierefreiheit_offener_wunschorte`, `formatiere_uhrzeit`). `speichere_feld` in
  `agent_tools.py` erhält das Argument `feste_wunschorte` als Liste `{name, dauer_minuten?,
  uhrzeit_minuten?}`. Laut Regelwerk-Block `_FESTE_WUNSCHORTE_REGEL` (`regelwerk.py`) setzt das LLM es
  nur bei einer ausdrücklichen „unbedingt"-Aussage, nie proaktiv, und übergibt immer die vollständige
  Liste; eine leere Liste entfernt alle Wunschorte. Der F16-Kontexthinweis in `katalog.py` verweist
  auf die Regel. Gleichnamige Einträge werden wiederverwendet, was erneute Places-Aufrufe spart. Nicht
  gefundene, ungültige oder doppelte Einträge werden nicht gespeichert und dem LLM ehrlich gemeldet.
  Bei Mobilitätseinschränkung „mittel" oder „stark" wird die Barrierefreiheit geprüft und ein Hinweis
  ausgegeben, ohne den Ort auszuschließen.
- **Warum:** Ein ausdrücklich gewünschter Ort ist ein Nutzerwunsch, kein Kandidat; ein Ausschluss
  wegen fehlender Barrierefreiheit würde diesen Wunsch übergehen. Die Adresse im Typ dient der
  Bestätigung des gefundenen Orts beim Nutzer; Score und Zeitfenster entfallen, weil der Ort
  Optimierung 1 nicht durchläuft. Die Erkennung liegt beim LLM wie bei Sicherheit und
  Mobilitätseinschränkung (keine Schlüsselwort-Heuristik).
- *Verworfen:* ein Pflicht-POI-Merkmal im TOPTW/ILS, das der Algorithmus zuerst einfügt (bisher im
  offenen Punkt „Explizit genannte Orte" erwogen; widerspricht der Vorgabe, den Ort nicht an den
  Algorithmus zu übergeben); eine Schlüsselwort-Erkennung im Code; der Typ `POI` für den Wunschort;
  ein Ausschluss bei fehlender Barrierefreiheit.

### D2 — Anfahrt und Nachhaltigkeitshinweis

- **Was:** Ab der bestätigten Unterkunft wird zuerst das lokale Verkehrsmittel aus F14 über die
  Distance Matrix geprüft. Liegt die einfache Strecke über `SCHWELLE_WEITER_WUNSCHORT_MINUTEN` (60)
  oder gibt es kein Ergebnis, wird `reisealternativen(Unterkunft, Wunschort)` passend zur
  F13-Präferenz verwendet; das Auto nutzt damit automatisch die FUEL_EFFICIENT-Route aus Phase 65.
  Die F13-Regel liegt jetzt zentral in `verkehrsmittelwahl.nur_bestaetigte_verkehrsmittel`;
  `pipeline._nur_bestaetigte_verkehrsmittel` leitet nur noch weiter. Das Ergebnis steht in der
  Dataclass `WunschortAnfahrt` (`verkehrsmittel`, `dauer_minuten`, `quelle`, `modus`, `distanz_km`,
  `co2_kg_hin_und_zurueck`, `kosten_euro_einfach`, `umweltfreundlichste_route`).
- Über 60 Minuten entsteht ein Hinweis mit Entfernung in km, Dauer und grob geschätztem CO₂ für Hin-
  und Rückweg (Emissionsfaktoren nicht amtlich verifiziert). Das LLM fragt ausdrücklich, ob der Ort
  bleiben soll; ein Verzicht erfolgt durch erneutes Speichern der Liste ohne diesen Ort. Maßgeblich
  ist die Dauer der tatsächlich gewählten Anfahrt (Bestätigung des Product Owners).
- Die Prüfung läuft je Unterkunft einmal und bei einem Unterkunftswechsel erneut. Ohne Unterkunft wird
  sie zurückgestellt und bei F15 nachgeholt. `plane_reise_und_abschliessen` schlägt einmalig fehl,
  wenn dabei ein neuer Hinweis entsteht. Ohne Landverbindung erfolgt eine ehrliche Meldung; Flüge
  werden nicht angeboten (Grundprinzip 5).
- **Warum:** Entscheidung des Product Owners für Variante (b): lokal, solange die Strecke kurz ist,
  sonst die Reisealternativen gemäß F13-Präferenz. Der Nutzer entscheidet nach dem Hinweis selbst.
- *Verworfen:* Variante (a), nur das lokale Verkehrsmittel; Variante (c), immer das nachhaltigste
  Verkehrsmittel unabhängig von F13; eine Schwelle nach km oder Luftlinie; ein eigenes
  Bestätigungs-Argument beim Abschluss; eine separate Abfrage des Rückwegs; eine Neusuche des Orts
  nach Bestätigung der Unterkunft.

### D3 — Einplanung in der Pipeline

- **Was:** `_volle_optimierungstage` in `src/pipeline.py` ist die gemeinsame Definition voller Tage
  für die Mittagsblock-Kürzung bei lokalem Kontakt (F19) und für die Tagwahl der Termine.
  `_einplanbare_wunschorte` holt ausstehende Prüfungen nach; ein Ort ohne Anfahrt oder ohne
  Unterkunftskoordinaten wird nicht eingeplant, sondern als Hinweis in
  `Reiseplan.feste_termine_hinweise` ausgewiesen (Bestätigung des Product Owners).
- `_budget_nach_termin`: Ohne Uhrzeit sinkt das Tagesbudget um Besuchsdauer plus zweimal den Weg, der
  Termin liegt am Tagesende. Mit Uhrzeit, bekanntem Tagesstart (F20) und außerhalb des Anreisetags
  gilt min(Budget, Uhrzeit − Hinweg − Tagesstart − Mittagsblock-Kürzung); der Termin schließt den Tag
  ab (Beispiel 15:00 Uhr, 30 Min. Hinweg, Tagesstart 9:00 Uhr: 330 Min.). Untergrenze jeweils 0.
- `_plane_feste_termine`: volle Tage der Reihe nach, danach reihum mit sich addierenden Kürzungen. Ohne
  vollen Tag der Abreisetag, dann Tag 1, sofern das Budget für Besuch samt Hin- und Rückweg reicht;
  sonst ein Hinweis. POIs mit derselben `place_id` werden vor `filtere_pois_hart` entfernt (kein
  Doppelbesuch, nicht unter den weiteren Empfehlungen). TOPTW/ILS erhalten den Termin nie; es ändert
  sich nur `tagesbudget_je_tag`.
- Ein negativer oder fehlender Barrierefreiheits-Befund erscheint nur bei aktueller Stufe „mittel"
  oder „stark" unter den Einschränkungshinweisen. Die Kostenschätzung (`kostenschaetzung.py`) zählt
  das Preisniveau des Termins und die Anfahrt mit 2 × `kosten_euro_einfach` (wie bei An- und Abreise:
  Fahrpreis oder km-Pauschale; Entscheidung des Product Owners, kein Zusatzfeld im API-Layer). Die
  Debug-Ausgabe (`debug.py`) erhält den Abschnitt „6. FESTE WUNSCHORTE" mit Tag und Budget vorher und
  nachher. `FesterTermin(tag_nr, wunschort, am_tagesende)` in `reiseplan.py`.
- `pruefe_planung.py` löst Wunschorte aus der Testdatei wie im Dialog auf; neuer Testfall
  `planungs_testfaelle/smoketest_feste_wunschorte.json` (München, Deutsches Museum mit 180 Min.,
  Schloss Neuschwanstein um 15:00 Uhr).
- **Warum:** Vorgabe aus dem Feedback, den Ort nicht an den Algorithmus zu übergeben; Optimierung 1
  plant nur die verbleibende Zeit. Ohne echte Wegzeit wäre die Budgetkürzung falsch, daher keine
  Einplanung mit geschätzter Anfahrt (Grundprinzip 1).
- *Verworfen:* die Aufteilung eines Tages in zwei Routen vor und nach dem Termin; eine Einplanung mit
  geschätzter Anfahrt; eine erfundene Uhrzeit ohne F20-Angabe.

### D4 — Ausgabe

- **Was:** `als_text`, `als_html` und `als_kartendaten` zeigen den Termin als eigenen Eintrag
  „Fester Termin" nach der optimierten Route und vor den Vorschlägen des Tages: Name, Adresse,
  Zeitpunkt, Dauer und Anfahrt; km und CO₂ nur, wenn vorhanden, CO₂ als grobe Schätzung
  gekennzeichnet; Google-Maps-Link und Routenlink ab der Unterkunft. Die Uhrzeit erscheint nur, wenn
  sie das Budget bestimmt hat, sonst „am Ende des Tages" mit einem Vermerk zur genannten Uhrzeit. Nicht
  einplanbare Orte erscheinen als Hinweis. Tage mit Termin zeigen keine generischen Beispiele. Bei
  unvollständiger Kostenschätzung steht ein neutraler Text. `fotos.py` lädt Fotos auch für Termine.
- `static/index.html`, Block FESTER-TERMIN-KARTE: eigene Kartenart ohne `label`, durchgehender blauer
  Rahmen und gefülltes Badge „Fester Termin – dein ausdrücklicher Wunsch". Hinweise zu nicht
  einplanbaren Orten stehen in `#termin-hinweise` und werden per `textContent` gesetzt.
- **Zusätzlich:** Die Anrede der gesamten Text- und Mail-Ausgabe ist auf „du" vereinheitlicht
  (14 Stellen in `reiseplan.py`, im Sicherheitshinweis in `pipeline.py` und im Ernährungshinweis in
  `datenaufbereitung/vertraeglichkeit.py`), passend zu Chat und Web-Oberfläche.
- **Warum:** Der Termin ist ein bestätigter Nutzerwunsch und kein Vorschlag; er soll sich daher von
  den gestrichelt umrahmten Vorschlägen unterscheiden.
- *Verworfen:* eine Darstellung des Termins im Vorschlagsstil (gestrichelter Rahmen).

### Verifikation

- Komplette Suite grün (455/455; 383 vor dieser Phase, D1 +22, D2 +15, D3 +20, D4 +15 Tests), u. a.
  in `test_agent_tools.py`, `test_google_maps.py`, `test_regelwerk.py`, `test_verkehrsmittelwahl.py`,
  `test_pipeline.py`, `test_debug.py`, `test_reiseplan.py`, `test_fotos.py` und dem neuen
  `test_fester_termin_karte.py`.
- Regression: Ohne Wunschorte entsteht ein identischer Plan (Abgleich gegen den Vorher-Stand in vier
  Fällen).
- Sichtprüfung im Headless-Browser mit einem Beispielplan. In einem echten 390, 360 und 320 px breiten
  Rahmen kein Überlauf; eine zuvor beobachtete Abschneidung der Karten war ein Messfehler, weil
  Headless-Chrome nicht schmaler als 500 px rendert.
- Nicht geprüft: die echten Google-APIs (Text Search, Distance Matrix, Routes für die Anfahrt), das
  Live-Verhalten des LLM bei der Erkennung ausdrücklicher Wunschorte und ein Live-Lauf von
  `pruefe_planung.py` (API-Kosten).
- [Station 38](doku/38_stage38_fester_termin_wunschort/README.md) mit Code-Duplikat.
- **Offen:** siehe Offene Punkte (Anreisetag, mehrere Uhrzeiten an einem Tag, Tagesende, Rückweg,
  Härtetest, Barrierefreiheits-Nachprüfung, Eckdaten-Chip, Emissionsfaktoren, Neusuche).

## Phase 68 — Ergebnisansicht nach dem Live-Test: Eckdatenzeile, Nudge, Gesprächsverlauf (04.10.2026)

Live-Test des Product Owners am 04.10.2026 mit echtem Dialog und echten APIs (Ergebnisansicht
„Deine Reise nach Hamburg"). Drei Beobachtungen: Die Eckdaten-Chips unter dem Titel wirkten wie
anklickbare Knöpfe, der grün hervorgehobene CO₂-Chip wie eine getroffene Auswahl. Der
Nachhaltigkeits-Nudge im fertigen Plan lautete „braucht nur -60 Minuten länger". Der nach Abschluss
standardmäßig eingeklappte Chat wurde übersehen.

- **Was (Eckdatenzeile):** Die Eckdaten erscheinen als nicht-interaktive Infozeile (`<ul
  id="eckdaten">` mit `li.eckdaten-angabe`), getrennt durch dezente Mittelpunkte, ohne Rahmen,
  Hintergrund, Hover-Effekt und ohne farbige Hervorhebung des CO₂-Werts. Der Tooltip zur
  Kostenschätzung bleibt. Die Auswahl der Werte ist unverändert (Block ECKDATEN-CHIPS, Funktion
  `eckdatenChips` beibehalten).
- **Was (Nudge):** Der Nudge steht nicht mehr im fertigen Plan. `webapp.py` baut die
  Abschlussnachricht in der neuen Hilfsfunktion `ergebnis_nachricht` ohne Nudge, `chat.py` gibt ihn
  nicht mehr auf der Konsole aus, `plane_reise_und_abschliessen` (`agent_tools.py`) nimmt ihn nicht
  mehr ins Werkzeugergebnis auf. Er wird weiter berechnet (`pipeline.py`), in
  `state.nachhaltigkeits_nudge` gehalten und im Sitzungsprotokoll (`reiseplan_erstellt`)
  festgehalten. Im F13-Dialog (`vorschlaege.py`) bleibt er unverändert.
- **Was (Nudge-Korrektur):** `nachhaltigkeits_nudge` in `src/optimierung/verkehrsmittelwahl.py`
  vergleicht die Bahn mit der bestbewerteten Alternative (bester Gesamtwert aus Zeit, Kosten und
  CO₂), nicht mit der schnellsten. Ist die Bahn schneller, lautet der Text jetzt „Die Bahn ist sogar
  X Minuten schneller und spart …", bei gleicher Fahrzeit „Die Bahn ist gleich schnell und spart …".
  Der Bezug wird als „gegenüber der bestbewerteten Alternative (Verkehrsmittel)" benannt.
- **Was (Gesprächsverlauf nach Abschluss):** standardmäßig sichtbar und kompakt. Ab 980 px läuft er
  als schmale Spalte (280–340 px, `position: sticky`) neben dem Plan mit; darunter steht er unter dem
  Plan. Ein Kopf „Gesprächsverlauf" mit dem Knopf „Einklappen" blendet ihn aus, ein schwebender Knopf
  „Chat anzeigen" holt ihn zurück (jeweils `aria-expanded`). Kleinere Schrift, keine
  Schnellantworten; die Eingabezeile bleibt ausgeblendet (Phase 60). Escape klappt nicht mehr ein.
- **Revision:** Das in Phase 66 eingeführte, standardmäßig eingeklappte Überlagerungs-Panel ist
  ersetzt, ebenso der Nudge zwischen Eckdaten und Zeitleiste.
- **Warum:** Eine Angabe in Knopf-Optik suggeriert Interaktion bzw. eine Auswahl, die es nicht gibt.
  Nach Abschluss ist die Verkehrsmittelwahl getroffen; der Nudge kommt dort zu spät und war im
  Live-Test zudem fehlerhaft formuliert. Der Nutzer soll seine Angaben im Gesprächsverlauf nachlesen
  können, ohne ihn erst suchen zu müssen (Entscheidung des Product Owners).
- *Verworfen:* den Chat weiter als eingeklapptes Überlagerungsfenster belassen; den Nudge im Plan nur
  korrigieren statt entfernen; die Nudge-Berechnung aus der Pipeline löschen (sie bleibt für das
  Sitzungsprotokoll).
- **Nachtrag Routes API (Phase 65):** Im selben Live-Test wurde die FUEL_EFFICIENT-Route für
  Hannover → Unterkunft Hamburg gewählt; die Antwortformate sind damit bestätigt. Dabei fiel auf,
  dass die Routes API das von der Pipeline übergebene Koordinatenpaar „lat,lng" im Feld `address`
  mit HTTP 400 INVALID_ARGUMENT ablehnt. Koordinatenpaare werden seither als `location.latLng`
  übergeben (`_routes_api_wegpunkt` in `src/api/google_maps.py`), alle übrigen Angaben bleiben
  Adresstext. Regressionstest `test_auto_route_koordinaten_als_latlng_statt_adresse`.
- Neue Tests: drei Nudge-Tests in `tests/test_verkehrsmittelwahl.py` (Bezugsgröße, schnellere Bahn,
  gleiche Fahrzeit), je ein Test in `tests/test_agent_tools.py` (Nudge nicht im Werkzeugergebnis,
  aber im Zustand) und `tests/test_webapp.py` (`ergebnis_nachricht` und `index.html` ohne Nudge),
  dazu der Regressionstest in `tests/test_google_maps.py`. Komplette Suite grün (461/461; 455 nach
  Phase 67). JavaScript-Syntax mit `node --check` geprüft. Sichtprüfung im Headless-Chrome mit
  Mock-Daten bei 1280 und 1000 px sowie per iframe bei 390 und 320 px: kein horizontales Scrollen.
- Nicht geprüft: ein echtes Mobilgerät und ein erneuter Live-Dialog mit diesen Änderungen.
- [Station 39](doku/39_stage39_ergebnisansicht_live_test/README.md). Kein `code_stand`-Snapshot
  (transparent vermerkt).
- **Offen:** siehe Offene Punkte (doppelte Tagesangabe in der Eckdatenzeile).

## Phase 69 — Freigabe für externe Tester über einen Cloudflare-Tunnel (04.10.2026)

Für Demonstration und Evaluation mit externen Testpersonen soll der lokal betriebene Prototyp auch
von anderen Rechnern und aus anderen Netzwerken erreichbar sein: über einen einzigen Link, ohne
Installation bei den Testpersonen, ohne Weitergabe des Codes und ohne separate Passworteingabe
(Entscheidung des Product Owners). Da jedes Gespräch LLM- und API-Kosten verursacht, darf der
öffentlich erreichbare Server nicht für beliebige Dritte nutzbar sein.

- **Was (Tunnel und Startskript):** `starte_extern.bat` ruft `starte_extern.py` auf. Das Skript
  prüft, ob `cloudflared` verfügbar ist (sonst Hinweis auf `winget install Cloudflare.cloudflared`)
  und ob Port 8000 frei ist, bestimmt das Zugangstoken (`ZUGANGSTOKEN` aus der `.env`, sonst je
  Start zufällig über `secrets.token_urlsafe(24)`), startet Uvicorn auf `127.0.0.1:8000` mit dem
  Token als Umgebungsvariable und öffnet einen Cloudflare Quick Tunnel. Aus der Ausgabe von
  `cloudflared` liest es die `trycloudflare.com`-Adresse und gibt den Link
  `https://….trycloudflare.com/?zugang=TOKEN` aus. Beim Beenden werden die eigenen Kindprozesse
  geschlossen (unter Windows `taskkill /T`). Der Quick Tunnel ist kostenlos, braucht kein Konto,
  liefert HTTPS und leitet WebSockets weiter; HTTPS ist zugleich Voraussetzung für den
  Mikrofonzugriff der Web Speech API im Browser.
- **Was (Zugriffsschutz, `webapp.py`):** Ohne konfiguriertes Token bleibt das Verhalten unverändert
  (lokaler Betrieb). Mit Token setzt `/?zugang=TOKEN` ein Cookie `reisebot_zugang` (HttpOnly,
  Secure, SameSite=Lax, Sitzungs-Cookie) und leitet per 303 auf `/` ohne Token in der Adresse um.
  Die HTTP-Middleware `zugriffsschutz` lässt danach nur Anfragen mit gültigem Cookie durch, sonst
  folgt die Seite „Kein Zugang" (HTTP 403). Das betrifft `/`, `/fotos/`, `/static/index.html`,
  `/docs` und `/openapi.json`; frei bleibt nur `/static/img/` (mitgelieferte Bilder ohne
  Personenbezug und ohne API-Kosten). Der WebSocket `/ws/chat` prüft Cookie oder Query-Parameter
  gesondert und wird ohne gültiges Token mit Code 1008 geschlossen, bevor eine Sitzung oder ein
  LLM-Aufruf entsteht. Der Vergleich erfolgt mit `secrets.compare_digest`. Der Logfilter
  `TokenMaskierer` ersetzt das Token in den Uvicorn-Logs durch `zugang=***`. Konfiguration über
  `zugangstoken` in `src/config.py` und `ZUGANGSTOKEN` in `.env.example`; `httpx` in
  `requirements.txt` für den FastAPI-Testclient.
- **Was (Nebenläufigkeit, `agent_tools.py`):** Alle Sitzungen teilen sich eine Event-Loop. Die
  Werkzeuge `speichere_feld` und `hole_api_daten` laufen deshalb über den Dekorator
  `im_hintergrund` per `asyncio.to_thread`, ebenso Vorprüfung und Planung in
  `plane_reise_und_abschliessen`. Das Statussignal `zeige_status("plant_reise")` bleibt auf der
  Event-Loop, weil der WebSocket nur dort bedient werden darf. Die Foto-Downloads in `webapp.py`
  (Vorschaukarte der Unterkunft in `zeige_karte`, Fotos nach Abschluss) laufen ebenfalls per
  `asyncio.to_thread`. Eine `asyncio.Lock` `werkzeug_sperre` in `AgentSessionState` führt die
  Werkzeuge einer Sitzung nacheinander aus; verschiedene Sitzungen laufen parallel. Jede Sitzung hat
  bereits eigenen Zustand, eigenen Maps-Client und eigenes Protokoll. Protokolldateien heißen jetzt
  `web_<sitzung_id>_…` statt `web_…`, damit gleichzeitig gestartete Sitzungen nicht dieselbe Datei
  erzeugen.
- **Was (Dokumentation):** Abschnitt „Reisebot für Tester freigeben" in `README.md`.
- **Warum:** Ein Link ohne Installation und ohne Passworteingabe hält die Hürde für die
  Testpersonen niedrig. Das Token schützt vor Kosten durch Unbefugte, das Cookie erspart die
  Passworteingabe, die Umleitung hält das Token aus Adresszeile und Verlauf. Ohne
  Hintergrund-Threads stünden während einer Planung oder eines API-Aufrufs alle anderen Sitzungen
  still.
- *Verworfen:* Tailscale (Installation und Konto bei den Testpersonen); Portfreigabe im Router
  (Sicherheitsrisiko, dynamische IP, kein HTTPS); ngrok (Warnseite vor dem ersten Aufruf, Konto
  nötig); Passwortformular (es soll bei einem einzigen Link bleiben); Betrieb ohne Zugriffsschutz
  (Kostenrisiko).
- Neue Tests: 17 in `tests/test_zugriffsschutz.py` (Umleitung, Cookie, 403, freie Pfade,
  WebSocket-Ablehnung, eigene Sitzung je Verbindung, Logmaskierung, unveränderter Betrieb ohne
  Token), 10 in `tests/test_starte_extern.py` (Token, Link, URL-Erkennung, cloudflared-Suche,
  belegter Port) und zwei in
  `tests/test_agent_tools.py` (zweite Sitzung antwortet, während die erste plant; Werkzeuge einer
  Sitzung nacheinander, verschiedener Sitzungen parallel). Komplette Suite grün (490/490). Zusätzlich
  ein echter Uvicorn-Lauf mit `curl`: 403 ohne Cookie, 303 mit Token, 200 mit Cookie, WebSocket ohne
  Cookie abgelehnt, Token im Log maskiert.
- Nicht geprüft: `cloudflared` selbst (auf dem Entwicklungsrechner nicht installiert), ein echter
  Browser über den Tunnel, das Mikrofon über HTTPS und der Betrieb mit mehreren echten
  Testpersonen.
- [Station 40](doku/40_stage40_tester_freigabe_tunnel/README.md). Kein `code_stand`-Snapshot
  (transparent vermerkt).
- **Offen:** siehe Offene Punkte (wechselnder Link, geteilte CPU und Kontingente, Tunnel-Betrieb
  ungetestet).

## Phase 70 — Galerie: Beschriftung je Bild (06.10.2026)

Rückmeldung des Product Owners zur Galerie neben dem Chat (Phase 66) anhand eines Live-Screenshots:
Bei den Stimmungsbildern war nicht erkennbar, wo ein Foto aufgenommen wurde und was darauf zu sehen
ist. Die Kennzeichnung „Inspiration · Stimmungsbilder, kein Reisevorschlag" wurde als überflüssig
bewertet.

- **Was (Kennzeichnung entfernt, `static/index.html`):** Die Pille „Inspiration · Stimmungsbilder,
  kein Reisevorschlag" entfällt; das `aria-label` der Galerie lautet „Galerie mit Stimmungsbildern".
- **Was (Beschriftung je Bild, `static/index.html`):** Jedes Stimmungsbild trägt unten auf einem
  dunklen Verlauf zwei Zeilen: das Motiv, darunter „Foto: Fotograf / Unsplash" (z. B. „Blaue
  Kirchenkuppel mit Bougainvillea, Oia, Santorini (Griechenland)" und „Foto: Xuan Nguyen /
  Unsplash"). `GALERIE_BILDER` erhält dafür je Bild das Feld `motiv`, wörtlich aus der Spalte „Motiv"
  in `static/img/galerie/QUELLEN.md`. Die Funktion `galerieBeschriftung` im neuen Block
  GALERIE-BESCHRIFTUNG bildet die beiden Zeilen; dargestellt wird per `textContent`. Die Beschriftung
  wechselt erst mit dem sichtbaren Bild. Ab 980 px darf das Motiv zweizeilig umbrechen, darunter
  wird es einzeilig mit Auslassungspunkten gekürzt. Die Einleitung von `QUELLEN.md` beschreibt die
  Beschriftung und verweist auf die Prüfung in `tests/test_galerie.py`.
- **Revision:** Die Kennzeichnung aus Phase 66 entfällt. Phase 66 hatte die Vereinbarkeit der
  Galerie mit Phase 57 (kein angedeuteter Planbereich während des Gesprächs) unter anderem mit dieser
  Kennzeichnung begründet. Die Bilder bleiben lokale Stimmungsbilder ohne Bezug zum geplanten
  Reiseziel.
- **Warum:** Ort und Motiv sollen für den Nutzer erkennbar sein (Rückmeldung des Product Owners);
  die Kennzeichnung trug dazu nichts bei. Die Beschriftung übernimmt nur Angaben, die in
  `QUELLEN.md` belegt sind (Grundprinzip 1).
- *Verworfen:* Fotos vom tatsächlichen Reiseziel über Google Places nach der Zielwahl. Diese
  Variante wurde prototypisch umgesetzt und mit einem echten Abruf für Hamburg geprüft, auf
  Entscheidung des Product Owners aber wegen der laufenden API-Kosten (eine Text Search und bis zu
  acht Place-Photo-Abrufe je Ziel und Gespräch) vollständig zurückgebaut; davon ist kein Code mehr
  vorhanden. Ebenfalls verworfen: die Aufteilung des Motivs in getrennte Angaben zu Motiv und Ort
  (hätte Ortsangaben ergänzt, die in `QUELLEN.md` nicht stehen).
- Neue Tests: vier in `tests/test_galerie.py` (Motiv und Fotograf im Skript stimmen mit `QUELLEN.md`
  überein, Pille entfernt, Beschriftung aller Stimmungsbilder per Node.js, Beispiel Lavendelfeld).
  Komplette Suite grün (494/494; 490 nach Phase 69). JavaScript-Syntax mit `node --check` geprüft.
  Sichtprüfung im Headless-Browser: Stimmungsbild Santorini mit Motiv und Bildnachweis.
- Nicht geprüft: ein echtes Mobilgerät.
- [Station 41](doku/41_stage41_galerie_beschriftung/README.md) mit Code-Duplikat (`static/index.html`,
  `static/img/galerie/QUELLEN.md`, `tests/test_galerie.py`).
- **Offen:** siehe Offene Punkte (Beschriftung im schmalen Bildband).

## Phase 71 — Titelzeile der Web-Oberfläche (13.10.2026)

Finales Demo-Feedback aus der abschließenden Testrunde (`Program/Finales Feedback/Feedback.docx`,
acht Punkte). Die Phasen 71–79 behandeln die Punkte in der Reihenfolge der Umsetzung, Phase 80 die
dabei vorgenommene Präzisierung der Bezeichnung der Feedbackquelle:

| Punkt im Feedback | Phase |
|---|---|
| 1 Begrüßung und Erklärung zu Beginn | 74 |
| 2 Namensangabe wird erzwungen | 73 |
| 3 Einordnung der CO₂-Menge fehlt | 76 |
| 4 CO₂-Berechnung prüfen | 75, Folgebefund in Phase 77 |
| 5 LLM überarbeitet bereits eingetragene Werte | 79 (bewusst beibehalten) |
| 6 Wiederholungen unter „Weitere Empfehlungen" | 72, Folgebefund in Phase 78 |
| 7 Bilder passend zum gewählten Reiseziel | 79 (nicht umgesetzt) |
| 8 Titelzeile anpassen | 71 |

Punkt 8: Die Titelzeile soll nur noch „Masterarbeit Prototyp Nick Poeppler" lauten, der übrige Text
entfallen.

- **Was:** Das `<h1>` in `static/index.html` lautet „Masterarbeit Prototyp Nick Poeppler". Der
  Untertitel („Reiseplanungs-Prototyp (Masterarbeit) – erzähl mir, was dir für eine Reise
  vorschwebt.") und die CSS-Regel `header p` entfallen. `header h1` erhält `overflow-wrap:
  break-word`: Der Titel ist länger als der frühere Schriftzug „Reisebot" und bricht auf schmalen
  Fenstern zwischen den Wörtern um; die Regel verhindert, dass ein einzelnes Wort über den Rand ragt.
  Der Tab-Titel (`<title>Reisebot</title>`) bleibt unverändert, das Feedback betrifft nur die
  sichtbare Titelzeile.
- **Warum:** Vorgabe des Demo-Feedbacks.
- *Verworfen:* eine kleinere Schrift auf schmalen Bildschirmen (der Umbruch genügt); eine Änderung
  des Tab-Titels.
- Neue Tests in `tests/test_titelzeile.py` (3: Titelzeile enthält nur den Masterarbeitstitel,
  Tab-Titel bleibt „Reisebot", keine verwaiste CSS-Regel für den Untertitel); Übersicht in
  `tests/conftest.py` ergänzt. Komplette Suite am Ende der Station grün (559/559).
- Nicht geprüft: die Darstellung im Browser bei 320, 390 und 980 px Breite.
- [Station 42](doku/42_stage42_finales_tester_feedback/README.md) mit Code-Duplikat
  (`static/index.html`).
- **Offen:** siehe Offene Punkte (Browserprüfung).

## Phase 72 — Keine Wiederholungen unter „Weitere Empfehlungen" (13.10.2026)

Finales Demo-Feedback, Punkt 6: Unter „Weitere Empfehlungen" erschienen Orte, die zuvor bereits als
Vorschlag für einzelne Tage gezeigt worden waren.

- **Ursache:** `_verteile_beispiele_auf_leere_tage` in `src/ausgabe/reiseplan.py` verteilt nicht
  eingeplante Kandidaten als Beispiele auf Tage ohne Programm und liefert die übrigen als Restliste.
  `als_text` und `als_html` nutzten diese Restliste, `als_kartendaten` verwarf sie und zeigte unter
  „Weitere Empfehlungen" die vollständige Liste `weitere_aktivitaeten_empfehlungen`. Deshalb traten
  die Wiederholungen nur in der Web-Oberfläche auf. Bei der Analyse fielen drei weitere Ursachen
  doppelter Orte auf: Der Mock-Client lieferte denselben Beispielort für jedes passende Interesse
  erneut, die internen ids von Places- und Overpass-Treffern überschnitten sich (Phase 78), und der
  gewählte Verleih wurde nicht mit den Empfehlungen abgeglichen.
- **Was:** Zwei neue Hilfsfunktionen in `src/ausgabe/reiseplan.py`. `_ort_schluessel(poi)` liefert
  die Google-`place_id`, sonst den Namen (Overpass-Treffer haben keine `place_id`).
  `_nicht_anderweitig_gezeigte_kandidaten(plan)` entfernt aus `weitere_aktivitaeten_empfehlungen`
  jeden Ort, der im Plan bereits als eingeplanter Tagespunkt, als Tour- oder
  Lernaktivitätsbeispiel, als Markt-, Café- oder Restaurantbeispiel, als Verleih oder als fester
  Termin steht, und lässt jeden Ort höchstens einmal zu. `als_text`, `als_html` und
  `als_kartendaten` übergeben diese bereinigte Liste an `_verteile_beispiele_auf_leere_tage`;
  `als_kartendaten` verwendet für „Weitere Empfehlungen" nun ebenfalls die Restliste. Es werden keine
  Orte ergänzt, Grundlage bleiben ausschließlich die realen Kandidaten.
- **Warum:** Der Abgleich an einer Stelle stellt sicher, dass Text-, Mail- und Web-Ausgabe dieselbe
  Liste zeigen. Er erfolgt über den Ort selbst, weil Verleih und feste Termine aus eigenen Suchen mit
  eigener Nummerierung bzw. ganz ohne `id` stammen.
- *Verworfen:* der Abgleich über die interne `id` (deckt Verleih und feste Termine nicht ab und war
  zwischen Places und Overpass nicht eindeutig); eine Bereinigung in `pipeline.py` (würde die
  CSV-Übersicht aller POI-Kandidaten verfälschen); eine reine Einzeilenkorrektur in
  `als_kartendaten` (hätte die weiteren Ursachen nicht erfasst).
- Neue Tests: vier in `tests/test_reiseplan.py` (Web-Ausgabe ohne die Beispiele eines leeren Tages,
  ohne bereits eingeplanten Tagespunkt, jeder Ort nur einmal, ohne Verleih, Tourbeispiel und festen
  Termin). Gegenprobe: Mit dem Vorher-Stand von `reiseplan.py` schlagen alle vier fehl. Komplette
  Suite am Ende der Station grün (559/559).
- [Station 42](doku/42_stage42_finales_tester_feedback/README.md) mit Code-Duplikat
  (`src/ausgabe/reiseplan.py`, `tests/test_reiseplan.py`).

## Phase 73 — Name als freiwillige Angabe (13.10.2026)

Finales Demo-Feedback, Punkt 2: Der Nutzer wird zur Angabe seines Namens gezwungen; die Angabe soll
verweigert werden können. Im Sitzungsprotokoll `protokolle/web_5417ce01_2026-10-13_130631.jsonl`
verweigerte die Testperson den Namen, das LLM bestand auf einer Angabe und speicherte „Herr".

- **Befund:** Das Feld `name` (F01) wird nirgends ausgewertet: weder im Reiseplan noch beim
  Mailversand (Empfänger ist F02 `email`) noch in den Kartendaten. Der bisherige Kontexthinweis
  „Wird für die persönliche Ansprache und den Versand des Reisevorschlags benötigt" war für den
  Versand sachlich falsch.
- **Was:** F01 in `src/fragekatalog/katalog.py` erhält `pflichtfeld=False` und einen neuen
  Kontexthinweis: freiwillige Angabe, nur für die persönliche Ansprache im Gespräch; bei Verweigerung
  nicht nachhaken, nicht erneut fragen und keinen Ersatz- oder Platzhalternamen speichern (z. B.
  „Herr", „Gast", „Anonym"), die Ansprache erfolgt dann neutral. Die Frage wird weiterhin gestellt
  (`ueberspringbar` bleibt False). `fehlende_pflichtfelder` meldet `name` nicht mehr,
  `plane_reise_und_abschliessen` plant auch ohne Namen; ohne E-Mail-Adresse bleibt der Abschluss
  gesperrt.
- **Warum:** Datensparsamkeit: Eine Pflichtangabe ohne fachlichen Zweck ist nicht zu rechtfertigen,
  und die erzwungene Angabe führte im Test zu einem gespeicherten Platzhalter.
- *Verworfen:* F01 als überspringbar markieren oder ganz entfernen (die Frage soll gestellt, nur
  nicht erzwungen werden); nur den Kontexthinweis ändern (der Pflichtstatus hätte den Abschluss
  weiterhin blockiert).
- Neue Tests: drei in `tests/test_agent_tools.py` (Name nicht unter den fehlenden Pflichtfeldern,
  Planung ohne Namen erfolgreich, ohne E-Mail weiterhin gesperrt). Komplette Suite am Ende der
  Station grün (559/559).
- Nicht geprüft: ob das LLM eine Verweigerung im Live-Dialog respektiert.
- [Station 42](doku/42_stage42_finales_tester_feedback/README.md) mit Code-Duplikat
  (`src/fragekatalog/katalog.py`, `tests/test_agent_tools.py`).
- **Offen:** siehe Offene Punkte (Live-Test, Prozessmodell F01).

## Phase 74 — Feste Begrüßung mit Erklärung (13.10.2026)

Finales Demo-Feedback, Punkt 1: Zu Beginn soll der Reisebot begrüßen und kurz erklären, was er
macht. Bisher lautete die erste Nachricht „Schön, dass Sie da sind! Erzählen Sie mir kurz in eigenen
Worten: Was schwebt Ihnen für eine Reise vor?", zudem noch in der Sie-Form, obwohl die Anrede in
Phase 67 auf „du" vereinheitlicht worden war.

- **Was:** Neue Konstante `BEGRUESSUNG` in `chat.py`; `a1_reisewunsch_aeussern` gibt sie aus und
  liefert die Antwort unverändert als Reisewunsch zurück. Web-Oberfläche und Konsole zeigen
  denselben Text, weil beide über `a1_reisewunsch_aeussern` laufen. Wortlaut (Leerzeilen trennen
  Begrüßung, Erklärung und Einstiegsfrage, ohne Markdown-Auszeichnung):

  > Hallo und herzlich willkommen!
  >
  > Ich helfe dir, eine Reise mit Hin- und Rückreise ohne Flugzeug und einer Unterkunft vor Ort zu
  > planen. Dazu stelle ich dir ein paar Fragen; Orte und Unterkünfte kommen aus echten Kartendaten,
  > vor allem von Google Maps. Am Ende bekommst du einen Tag-für-Tag-Plan mit grober Kostenschätzung
  > und dem CO₂-Ausstoß der An- und Abreise. Deine Angaben kannst du jederzeit im Chat korrigieren.
  >
  > Erzähl mir zuerst in eigenen Worten: Was schwebt dir für eine Reise vor?

- **Warum:** Die Erklärung beschreibt den Prototyp selbst und darf nichts versprechen, was er nicht
  leistet (Grundprinzip 1). Jede Aussage ist im Code gedeckt: „ohne Flugzeug" (Grundprinzip 5),
  „einer Unterkunft vor Ort" (Grundprinzip 4), „vor allem von Google Maps" (Hauptquelle,
  OpenStreetMap nur als Zusatzquelle), Tag-für-Tag-Plan, Kostenschätzung und CO₂ der An- und Abreise
  (`reiseplan.py`, `kostenschaetzung.py`), Korrektur im Chat (`speichere_feld` überschreibt bereits
  gesetzte Felder, siehe Phase 79). Deshalb ein fester Text statt einer Formulierung durch das LLM.
- *Verworfen:* ein vom LLM formulierter Einstieg (Grundprinzip 1); ein Willkommens-Overlay in der
  Web-Oberfläche (die Begrüßung bleibt Teil des Gesprächs, für Web und Konsole gleich); der Begriff
  „Rundreise" (bezeichnet alltagssprachlich eine Reise mit wechselnden Unterkünften); die Erwähnung
  des Mailversands (findet nur mit hinterlegten Mailjet-Zugangsdaten statt); ein Hinweis, dass der
  Name freiwillig ist (Länge der Begrüßung).
- Neue Tests: `tests/test_begruessung.py` (9: einzige erste Nachricht und unveränderte Rückgabe,
  drei Teile, Kernaussagen, keine Zusagen außerhalb des Prototyps, durchgängig du-Form, ohne
  Markdown und Schnellantworten, Konsole, Web-Kanal, gleicher Einstieg in Webapp und Konsole);
  Übersicht in `tests/conftest.py` ergänzt. Komplette Suite am Ende der Station grün (559/559).
- Nicht geprüft: die Darstellung der Absätze im Browser.
- [Station 42](doku/42_stage42_finales_tester_feedback/README.md) mit Code-Duplikat (`chat.py`).
- **Offen:** siehe Offene Punkte (Begrüßung nicht im Verlauf der Agenten-Session, Browserprüfung).

## Phase 75 — Prüfung der CO₂-Berechnung (13.10.2026)

Finales Demo-Feedback, Punkt 4: Manche CO₂-Werte wirkten ungewöhnlich. Vor einer Fehlersuche war
zu klären, ob die Auffälligkeit aus den bewusst nicht validierten Emissionsfaktoren stammt oder ein
eigenständiger Rechenfehler vorliegt.

- **Ergebnis: kein Rechenfehler.** `co2_kg` in `src/optimierung/emissionsfaktoren.py` rechnet
  Distanz in km × Faktor in g/Pkm / 1000. Die Distanzen der Directions API und der Routes API werden
  korrekt von Metern in Kilometer umgerechnet. Hin- und Rückreise werden getrennt berechnet; die
  Eckdatenzeile summiert die ungerundeten Werte und rundet erst die Summe.
- **Rückrechnung gegen Sitzungsprotokolle** (Faktoren Bahn 19 g/Pkm, Auto 168 g/Pkm):

  | Fall | Protokoll | CO₂ hin / zurück | entspricht | Einordnung |
  |---|---|---|---|---|
  | Resse → München, Bahn | `web_d10edabf_2026-10-10_133740.jsonl` | 12,6 kg | ca. 663 km | plausibel (Kostenschätzung ca. 665 km) |
  | Hannover → Göteborg, Bahn | `web_d9f714e2_2026-10-13_123002.jsonl` | 19,4 / 19,9 kg | ca. 1021 / 1047 km | plausibel |
  | Venedig, Auto | `web_5417ce01_2026-10-13_130631.jsonl` | 141,2 / 141,5 kg | ca. 840 km | Strecke führte zur Unterkunft in Südtirol, Folgebefund in Phase 77 |

- **Einordnung der Auffälligkeiten:** Die Emissionsfaktoren sind Platzhalter (Entscheidung des
  Product Owners vom 24.08.2026). Für die gesamte Transit-Strecke gilt ein einziger Faktor,
  einschließlich der Fußwege (Modellvereinfachung). Von Google gelieferte Transit-Routen können
  deutlich länger sein als die Straßenroute (Venedig: Bahn 1483 km, Auto rund 1115 km). Die
  CO₂-Angabe der Eckdatenzeile kann um 0,1 kg von der Summe der angezeigten Einzelwerte abweichen,
  weil sie die ungerundeten Werte summiert. Kosten aus der km-Pauschale werden centgenau angezeigt,
  was eine nicht vorhandene Genauigkeit suggeriert.
- **Entscheidung:** Dass sich der Auto-Faktor auf einen Pkw mit einer Person bezieht und Mitreisende
  nicht berücksichtigt werden, verfolgt der Product Owner bewusst nicht weiter.
- Keine Dateiänderung. Die Analyse ist in der
  [Station 42](doku/42_stage42_finales_tester_feedback/README.md) beschrieben.
- **Offen:** siehe Offene Punkte (Transit-Faktor, Routenlängen, Rundungsabweichung,
  Scheingenauigkeit der Kosten).

## Phase 76 — Einordnung der CO₂-Menge in drei Stufen (13.10.2026)

Finales Demo-Feedback, Punkt 3: Bei der CO₂-Menge für An- und Abreise fehlt eine Einordnung, ob
sie für eine Reise viel oder wenig ist. Vorgeschlagen wurde eine Art Ampel mit den Stufen
CO₂-lastig, mittel und genügsam.

- **Was (Einstufung, `src/optimierung/emissionsfaktoren.py`):** Konstanten
  `CO2_GRENZE_GENUEGSAM_KG = 50.0` und `CO2_GRENZE_MITTEL_KG = 150.0`, Dataclass `CO2Einstufung`
  (`stufe`, `bezeichnung`, `hinweis`), `CO2_EINSTUFUNG_HINWEIS` (aus den Konstanten erzeugt: grobe
  Schätzung, nur An- und Abreise, vorläufige Schwellen) und `co2_einstufung(kg)`. Eingeordnet wird
  die Summe aus Hin- und Rückreise: genügsam bis einschließlich 50 kg, mittel über 50 bis
  einschließlich 150 kg, CO₂-lastig über 150 kg. Die Grenzwerte gehören zur niedrigeren Stufe. Ohne
  Wert gibt es keine Einstufung.
- **Was (Ausgabe, `src/ausgabe/reiseplan.py`):** `_co2_an_abreise_kg` bildet die Summe und rundet
  sie auf eine Nachkommastelle; eingestuft wird dieser angezeigte Wert, damit Zahl und Stufe
  zusammenpassen. `_eckdaten` liefert zusätzlich `co2_einstufung`. `als_text` und `als_html` nennen
  nach der Rückreise eine Zeile „CO2 für An- und Abreise zusammen: X kg – Einordnung: Stufe." mit dem
  Hinweis auf die Schwellen; die Mail zeigt die Stufe als Text ohne Farbe.
- **Was (Web-Oberfläche, `static/index.html`):** In der Eckdatenzeile folgt auf die CO₂-Angabe
  „ – " und ein `span.co2-ampel` mit der Stufenbezeichnung, davor ein kleiner Farbpunkt
  (`::before`). Der Tooltip (`title`) nennt Schwellen und Einschränkungen. Die Stufe kommt fertig aus
  Python, das Skript berechnet nichts. Kein Rahmen, kein Hintergrund, kein Hover-Effekt; der
  CO₂-Wert selbst bleibt ungefärbt. Textfarben genügsam `#2f6f4f`, mittel `#7d5200`, CO₂-lastig
  `#a32a1f`, rechnerisch mit WCAG-AA-Kontrast auf dem Sandton (5,3:1, 6,1:1, 6,4:1). Die Farbe ist
  nie alleiniger Bedeutungsträger, die Stufe steht immer als Wort dabei.
- **Schwellen:** Beide Werte sind Platzhalter und eine eigene, vorläufige Setzung des Product
  Owners. Die Literaturprüfung in `Quellen/` ergab keinen Beleg für konkrete Schwellen.
  Ruiz-Meza & Montoya-Torres (2021, Annals of Operations Research 305, 227–249) stützen nur die
  Berechnung als Distanz × Faktor je Personenkilometer, Klarin et al. (2023, Tourism Management
  Perspectives 46, 101100) nur die qualitative Reihenfolge (Bahn und Bus emissionsärmer als Auto
  und Flug).
- **Teilweise Revision von Phase 68:** Dort war die farbige Hervorhebung des CO₂-Werts entfernt
  worden, weil sie wie eine getroffene Auswahl wirkte. Farbe erscheint jetzt wieder, aber nur an der
  Stufenbezeichnung, nicht-interaktiv und ohne Vergleich mit anderen Verkehrsmitteln.
- **Warum:** Die Einordnung ist deterministisch und gehört in den regelbasierten Layer
  (Grundprinzip 3), damit Web-, Text- und Mail-Ausgabe dieselbe Stufe zeigen. Absolute Schwellen
  statt eines Vergleichs mit den Alternativen, weil ein Vergleich im fertigen Plan einem Nudge
  entspräche, der dort nach Phase 68 nicht mehr steht.
- *Verworfen:* eine relative Ampel im Vergleich zu den Alternativen (Nudge im fertigen Plan,
  Phase 68); die Umsetzung erst nach Fund einer Quelle für die Schwellen (hätte die Umsetzung
  blockiert); die Einstufung durch das LLM oder nur im Skript der Web-Oberfläche (Grundprinzip 3,
  Text und Mail ohne Stufe); Farbe als einziger Träger der Information und eine Pillen-Optik
  (Befund aus Phase 68); ein Vergleichssatz zu anderen Verkehrsmitteln.
- Neue Tests (14): sieben in `tests/test_emissionsfaktoren.py` (fünf Grenzwertfälle, ohne Wert keine
  Einstufung, Hinweistext), drei in `tests/test_reiseplan.py` (Summe aus Hin- und Rückreise,
  Einstufung des gerundeten Werts, Text- und Mail-Zeile ohne Vergleich), drei in
  `tests/test_eckdaten_chips.py` (per Node.js: Stufe mit Text und Tooltip, ohne Einstufung nur die
  Menge, ohne Wert keine Angabe), einer in `tests/test_webapp.py` (CSS ohne Rahmen, Hintergrund,
  Hover und Zeiger). Komplette Suite am Ende der Station grün (559/559).
- Nicht geprüft: die Darstellung im Browser und auf Mobilgeräten.
- [Station 42](doku/42_stage42_finales_tester_feedback/README.md) mit Code-Duplikat
  (`src/optimierung/emissionsfaktoren.py`, `src/ausgabe/reiseplan.py`, `static/index.html`,
  `tests/test_emissionsfaktoren.py`, `tests/test_reiseplan.py`, `tests/test_webapp.py`; nicht
  `tests/test_eckdaten_chips.py`).
- **Offen:** siehe Offene Punkte (Schwellen ohne Literaturbeleg, Tooltip auf Touch-Geräten,
  Browserprüfung).

## Phase 77 — Lageprüfung der vorgeschlagenen Unterkunft (13.10.2026)

Folgebefund der CO₂-Prüfung (Phase 75): Im Gespräch mit dem Ziel Venedig
(`protokolle/web_5417ce01_2026-10-13_130631.jsonl`) lag die bestätigte Unterkunft rund 136 km
entfernt in Südtirol; der erste Vorschlag war „Kleines Hotel Kärnten". Ursache: Bei der Places
Nearby Search mit `keyword` (Freitext der Antwort auf F15) ist `radius` nur eine Bevorzugung, kein
Ausschluss. `suche_unterkunft` in `src/fragekatalog/vorschlaege.py` übernahm den ersten Treffer ohne
Lageprüfung, und das LLM erhielt keine Lageangabe. Folgen: Optimierung 1 plante null Besuche (Depot
in Südtirol, POIs in Venedig), An- und Abreise sowie CO₂ wurden nach Südtirol berechnet. Entscheidung
des Product Owners: Lagefilter und Transparenz, Maßstab ist das Gebiet des Ziels.

- **Was (Datentypen, `src/api/typen.py`):** neuer Typ `ZielGebiet` (Mittelpunkt `x`/`y`,
  `suedwest`/`nordost` des Gebiets, Eigenschaft `punkt`); `Unterkunft` erhält das Feld `adresse`.
- **Was (Google-Client, `src/api/google_maps.py`):** `geocode_gebiet(adresse)` im Protokoll
  `MapsClient` und in `GoogleMapsClient`: liest `geometry.viewport`, nur ersatzweise
  `geometry.bounds` (kann weit entfernte Teilgebiete einschließen). Ergebnisse werden je Adresse für
  die Lebensdauer der Client-Instanz (eine Sitzung) zwischengespeichert, Fehler nicht. `geocode()`
  liefert `geocode_gebiet().punkt`. `suche_unterkuenfte` übernimmt `vicinity`, sonst
  `formatted_address`, als Adresse. Der Mock-Client bildet jedes Ziel auf `BEISPIEL_ZIELGEBIET` ab
  (neu in `mock_data.py`, rund 20 × 27 km um „Zielregion", umschließt alle Beispielorte; dazu
  Adressen der Beispielunterkünfte), damit der Prototyp ohne API-Schlüssel durchspielbar bleibt; sein
  `geocode` bleibt unverändert.
- **Was (Lageprüfung, neues Modul `src/datenaufbereitung/lagepruefung.py`):** `luftlinie_km`
  (Haversine), `liegt_im_zielgebiet` und `filtere_unterkuenfte_nach_lage` (teilt in behaltene und
  verworfene Treffer, die Reihenfolge der Google-Relevanz bleibt). Ein Treffer liegt am Ziel, wenn er
  höchstens `LAGE_MINDESTRADIUS_KM` = 10 km vom Mittelpunkt entfernt ist oder im Viewport zuzüglich
  `LAGE_PUFFER_KM` = 5 km liegt. Fehlt der Viewport, gilt nur `LAGE_FALLBACK_RADIUS_KM` = 30 km um den
  Mittelpunkt.
- **Was (Ablauf in `suche_unterkunft`):** Gebiet holen, suchen, Lagefilter anwenden. Bleibt nichts
  übrig und liegt ein Anforderungstext vor, wird einmal ohne `keyword` neu gesucht und ebenso
  gefiltert; das Ergebnis an das LLM vermerkt dann, dass die Unterkunft die Anforderung
  möglicherweise nicht erfüllt. Danach folgt wie bisher der Barrierefreiheitsfilter. Ohne Treffer
  meldet das Ergebnis ehrlich, dass in oder um das Ziel keine Unterkunft gefunden wurde; wurden
  Treffer wegen der Lage verworfen, nennt es deren Anzahl und weist das LLM an, keine Unterkunft aus
  eigenem Wissen zu nennen. Das Ergebnis enthält die Zeile „Lage: Adresse, ca. N km Luftlinie vom
  Mittelpunkt" (ohne Adresse „keine Adressangabe"). Der Kontexthinweis von F15 in `katalog.py`
  verlangt, die Unterkunft samt Lage zu nennen.
- Im Normalfall entsteht kein zusätzlicher API-Aufruf, weil die Unterkunftssuche dasselbe Ziel
  ohnehin geocodiert; nur im Leerfall mit Anforderungstext folgt eine zweite Nearby Search.
- **Warum:** Ob ein Treffer am Ziel liegt, ist objektiv berechenbar und bleibt deshalb im
  regelbasierten Layer (Grundprinzip 3). Eine falsch gelegene Unterkunft wirkt sich auf die gesamte
  Planung aus, weil sie Depot von Optimierung 1 und Ziel der An- und Abreise ist. Das Gebiet aus dem
  Geocoding dient als Maßstab, weil ein fester Kilometerwert Städte und Regionen (etwa „Costa del
  Sol") gleich behandeln würde. Die Werte: 5 km Puffer für Stadtrand und angrenzende Ortsteile; 10 km
  Mindestradius für kleine Orte mit kleinem Viewport, deren Unterkünfte oft im Nachbarort liegen;
  30 km ohne Viewport für eine Stadt mit Umland, deutlich unter den 136 km des Befunds. Die Lageangabe
  macht die Wahl für den Nutzer nachvollziehbar.
- *Verworfen:* ein fester Kilometerwert als alleiniges Kriterium (beschneidet Regionsziele; nur als
  Rückfall ohne Viewport); eine Text Search „Anforderung in Ziel" allein (der Ortsbezug wirkt dort
  ebenfalls nur gewichtend); nur Transparenz ohne Filter (die falsch gelegene Unterkunft bliebe
  Grundlage der Planung).
- Neue Tests: `tests/test_lagepruefung.py` (12: Luftlinie, Südtirol nicht und Mestre im Gebiet
  Venedig, Regionsziel, kleiner Viewport mit Mindestradius, Puffer, Rückfallschwelle, Reihenfolge,
  Mock-Zielgebiet), zehn in `tests/test_vorschlaege.py` (nahe statt entfernte Unterkunft, Neusuche
  ohne `keyword`, ehrliche Leermeldung, keine Neusuche ohne Anforderungstext, Regionsziel,
  Rückfallschwelle, Ort und Entfernung im Ergebnis, keine erfundene Adresse, Mock-Modus mit realem
  Zielnamen, kein zusätzlicher API-Aufruf), fünf in `tests/test_google_maps.py` (Viewport, Bounds,
  ohne Rechteck, Zwischenspeicher, `vicinity`); Stubs in `tests/test_agent_tools.py` um
  `geocode_gebiet` ergänzt. Komplette Suite am Ende der Station grün (559/559).
- Nicht geprüft: das Verhalten mit echten Viewports der Geocoding API und ein Live-Dialog.
- [Station 42](doku/42_stage42_finales_tester_feedback/README.md) mit Code-Duplikat
  (`src/api/typen.py`, `src/api/google_maps.py`, `src/api/mock_data.py` rekonstruiert,
  `src/fragekatalog/vorschlaege.py`, `src/fragekatalog/katalog.py` und die betroffenen Tests).
- **Offen:** siehe Offene Punkte (Kalibrierung der Schwellen, Live-Test, Adresse in Vorschaukarte
  und Reiseplan, Mock-Geocoding, 180. Längengrad).

## Phase 78 — Eindeutige POI-ids über Places und Overpass (13.10.2026)

Folgebefund aus Phase 72: Places- und Overpass-Client nummerieren ihre Treffer unabhängig
voneinander ab 1. Nachgelagerte Schritte verwenden die `id` jedoch als Identität eines Kandidaten.
Die Reisezeitmatrix (Schlüssel `(von.id, nach.id)` in `aufbereitung.py::hole_reisezeitmatrix`)
vermischte dadurch Einträge zweier Orte, `toptw.py::plane_gesamte_reise` entfernte über die bereits
besuchten ids einen fremden POI, und `pipeline.py::plane_reise` ließ über die eingeplanten ids
Overpass-Kandidaten still verschwinden.

- **Was:** `sammle_pois` in `src/datenaufbereitung/poi_sammlung.py` vergibt die ids am Ende
  fortlaufend ab 1 neu (`dataclasses.replace`); Reihenfolge und übrige Felder bleiben, die `id` 0
  bleibt der Unterkunft als Depot vorbehalten. `MockGoogleMapsClient.suche_pois` liefert einen
  Beispielort, der zu mehreren Interessen passt, nur noch einmal; sonst erhielte derselbe Ort nach
  der Neunummerierung mehrere ids und könnte mehrfach eingeplant werden. In `reiseplan.py` wurde nur
  der Docstring von `_ort_schluessel` angepasst. Optimierung 1 und 2 sind algorithmisch unverändert.
- **Warum:** `sammle_pois` ist die einzige Stelle, an der beide Quellen zusammenkommen.
- *Verworfen:* nur die Overpass-ids um einen Versatz verschieben; die Nummerierung zwischen den
  Clients abstimmen; alle Schlüssel auf `place_id` bzw. Name umstellen; die Mock-Duplikate belassen.
- Neue Tests: drei in `tests/test_poi_sammlung.py` (eindeutige ids bei gleicher Ursprungs-id,
  getrennte Matrixeinträge, Einplanen entfernt keinen anderen POI), einer in `tests/test_pipeline.py`
  (Overpass-Kandidat mit gleicher Ursprungs-id bleibt erhalten), einer in `tests/test_google_maps.py`
  (Mock liefert jeden Beispielort nur einmal). Gegenprobe: Ohne die Neunummerierung schlagen die vier
  neuen Tests in `test_poi_sammlung.py` und `test_pipeline.py` fehl. Komplette Suite grün (559/559;
  494 nach Phase 70).
- [Station 42](doku/42_stage42_finales_tester_feedback/README.md) mit Code-Duplikat
  (`src/datenaufbereitung/poi_sammlung.py`, `src/api/google_maps.py`, `src/ausgabe/reiseplan.py`,
  `tests/test_poi_sammlung.py`, `tests/test_google_maps.py`; `tests/test_pipeline.py` nicht im
  Duplikat).

## Phase 79 — Bewusst beibehaltenes und nicht umgesetztes Verhalten (13.10.2026)

Zwei Punkte des finalen Demo-Feedbacks werden auf Entscheidung des Product Owners nicht durch
Code-Änderungen umgesetzt. Keine Dateiänderung.

### Korrektur bereits gespeicherter Werte durch das LLM (Punkt 5)

- **Beobachtung:** In einem Testfall der testenden Person aus dem HULLS-Projekt führte eine
  bestimmte Formulierung dazu, dass das LLM einen bereits eingetragenen Wert des Nutzers vor dem
  Absenden überarbeitete. Der konkrete Testfall und das betroffene Feld sind nicht protokolliert.
- **Entscheidung:** kein Fehler, sondern bewusst beibehaltenes Verhalten.
- **Warum:** Vertippt sich ein Nutzer, muss er den Wert im Nachgang per Chat korrigieren können.
- **Bestehende Grundlage:** Das Regelwerk (`regelwerk.py`, Beschreibung von `speichere_feld`) weist
  das LLM an, das Werkzeug erneut aufzurufen, wenn der Nutzer eine frühere Angabe revidiert, ohne
  Sondermechanismus. Die Korrekturschleife besteht seit Phase 4; die Begrüßung kündigt die
  Korrekturmöglichkeit an (Phase 74).
- **Abgrenzung zu den Grundprinzipien 1 und 3:** Das LLM ändert Werte auf Grundlage von
  Nutzeraussagen und erfindet keine; `speichere_feld` validiert jeden Wert weiterhin gegen den
  erwarteten Rückgabetyp. Ein Spannungsfeld besteht zur Rollenbeschreibung `_ROLLENBESCHREIBUNG` in
  `chat.py`, die eine großzügige Interpretation von Antworten verlangt, aber keine erfundenen Werte
  zulässt: Wo Interpretation in eine ungewollte Überarbeitung übergeht, entscheidet das LLM.
- *Verworfen:* gespeicherte Werte sperren oder nur nach ausdrücklicher Bestätigung ändern lassen.
- **Limitation:** Ungewollte Überarbeitungen sind möglich und nicht deterministisch ausgeschlossen.

### Bilder vom gewählten Reiseziel (Punkt 7)

- Das finale Demo-Feedback wünscht erneut, nach Festlegung des Ziels in der Galerie vorrangig
  Bilder dieses Ziels zu zeigen.
- **Entscheidung:** aus Kostengründen nicht umgesetzt. Das bestätigt Phase 70: Fotos vom Reiseziel
  über Google Places waren prototypisch umgesetzt und wegen der laufenden API-Kosten je Gespräch
  zurückgebaut worden.
- Die Galerie zeigt weiterhin lokale Stimmungsbilder ohne Bezug zum Reiseziel.

## Phase 80 — Bezeichnung der Feedbackquelle präzisiert (13.10.2026)

- **Was:** Die Rückmeldungen aus den Demonstrationen heißen in der gesamten Dokumentation und im Code
  „HULLS-Feedback" statt „Betreuer-Feedback". Die Ersetzung betrifft 28 Markdown-, Python-, HTML- und
  Textdateien außerhalb der `code_stand/`-Ordner, darunter Kommentare, Docstrings und eine
  Herkunftsangabe im Prompt-Text `_TOOL_ANLEITUNG` (`regelwerk.py`, Abschnitt SCHNELLANTWORTEN); die
  Anweisungen an das LLM sind inhaltlich unverändert. Der Kopf dieses Dokuments definiert den
  Begriff. „Betreuer" bleibt nur dort, wo die Betreuenden der Arbeit gemeint sind.
- **Warum:** Die Rückmeldungen stammen von einer im HULLS-Projekt forschenden Person, nicht von den
  Betreuenden der Arbeit (Festlegung des Product Owners).
- Die `code_stand/`-Kopien bleiben als unverändertes Archiv mit dem damaligen Wortlaut erhalten.
  Einige erst während Station 42 gesicherte Kopien enthalten den neuen Begriff bereits (siehe
  [Station 42](doku/42_stage42_finales_tester_feedback/README.md)).
- Keine Verhaltensänderung. Komplette Suite grün (559/559).

## Phase 81 — Feedbackquelle: Rückmeldungen beider Testpersonen (18.10.2026)

Korrektur der Begriffsfestlegung aus Phase 80 auf Hinweis des Product Owners. Keine
Verhaltensänderung.

- **Was:** Die Rückmeldungen aus den Demonstrationen heißen in Dokumentation und Code
  „Demo-Feedback" statt „HULLS-Feedback". Die Ersetzung betrifft 36 Markdown-, Python- und
  HTML-Dateien außerhalb der `code_stand/`-Ordner, darunter Kommentare, Docstrings und eine
  Herkunftsangabe im Prompt-Text `_TOOL_ANLEITUNG` (`regelwerk.py`, Abschnitt SCHNELLANTWORTEN); die
  Anweisungen an das LLM sind inhaltlich unverändert. Die Begriffsdefinition im Kopf dieses Dokuments
  und in `ARCHITEKTUR.md` ist angepasst, die Überschrift von Phase 56 bzw. Station 28 lautet jetzt
  „Demo-Feedback zur Web-Oberfläche".
- **Warum:** Das Feedback aller drei Demonstrationsrunden stammt von zwei Testpersonen: einer im
  HULLS-Projekt forschenden Person und dem Betreuer der Arbeit. Die Festlegung in Phase 80, die
  Rückmeldungen stammten nicht von den Betreuenden der Arbeit, traf nicht zu. **Revidiert Phase 80.**
- Bewusst unverändert: der Wortlaut von Phase 80 als historischer Eintrag, die `code_stand/`-Kopien
  sowie die Angabe in Phase 79, dass der Testfall zu Punkt 5 von der Person aus dem HULLS-Projekt
  stammt.
- Kein `code_stand`-Snapshot (transparent vermerkt): reine Begriffsänderung ohne Logikänderung.
- Komplette Suite grün (559/559). Weitere Angaben in
  [Station 43](doku/43_stage43_feedbackquelle_beide_testpersonen/README.md).

## Phase 82 — Nachträge zur Dokumentation: Hands-on-Test, Begriffe, Verfahrensauswahl, Fragekatalog (22.10.2026)

Reine Dokumentationsänderung; Code und Verhalten des Prototyps bleiben unverändert.

- **Hands-on-Test:** Die dritte Demonstrationsrunde (finales Demo-Feedback, Phasen 71–80) fand als
  Hands-on-Test statt: Die im HULLS-Projekt forschende Person und der Betreuer haben den Prototyp über
  die Freigabe aus Phase 69 selbst bedient. Der offene Punkt „Tunnel-Betrieb ungetestet" ist damit
  erledigt; die Quellenangabe in `Program/Finales Feedback/Feedback.docx` nennt beide Testpersonen.
- **Begriff Live-Test:** Phase 35 und Station 16 hießen „Erster Nutzertest". Weil kein Test mit der
  Zielgruppe stattgefunden hat, heißen sie jetzt „Erster Live-Test", wie bereits Phase 68.
- **Verfahrensauswahl Optimierung 1:** `ARCHITEKTUR.md` nannte eine Nutzwertanalyse als Begründung der
  Iterated Local Search. Entschieden wurde anhand von zwei Kriterien: der Komplexität der Integration
  in den bestehenden Prototyp, die stark gewichtet wurde, weil der Product Owner keine Vorerfahrung mit
  Optimierungsverfahren hatte, und dem Nutzen zur Laufzeit (Lösungsqualität bei kurzer Rechenzeit).
  Die Bewertung wird nachträglich als Nutzwertanalyse mit genau diesen Kriterien dokumentiert;
  `ARCHITEKTUR.md` ist angepasst.
- **Robustheits-Gateway:** Begründung ergänzt, warum die Rückkopplung bei „nicht robust" nicht gebaut
  wurde (siehe Offene Punkte).
- **Fragekatalog-Zählung:** `ARCHITEKTUR.md` und `Program/CLAUDE.md` nannten „18 Kernfragen". Der
  Katalog umfasst 19 Fragen (F01–F20 ohne F18), davon zwei Metafragen. Herleitung aus den 18 Fragen
  des Rohmaterials: entfallen sind „Reiseerlebnis" (Phase 1, wird aus dem freien Einstieg befüllt)
  und F18 als eigene Frage (Phase 55, in F09 integriert); ergänzt wurden F08 Wohnort (Phase 1), F10
  altersgerechte Bedürfnisse und F20 Tagesablauf (Phase 11). F10 hatte bisher keinen eigenen Eintrag
  und ist in Phase 11 bereits vorhanden; die Begründung steht in `katalog.py`: „Altersgerechter &
  inklusiver Tourismus" ist ein vom Betreuer der Arbeit empfohlenes Kernfeld
  (`Fortschritte/Fragekatalog/Kategorien.pdf`, Feld 02), F09 deckte davon nur gesundheitliche
  Einschränkungen ab. Nach dem Kodierleitfaden gehört F10 zur Kategorie K3 (Altersgerechtigkeit);
  die Angabe `cluster="K6"` in `katalog.py` bleibt wegen des Code-Freeze unverändert. Ebenso
  behalten F04 (`stufe=1`, seit Phase 55 direkt vor F17 gefragt) und F20 (`stufe=5`, am Ende des
  Katalogs) ihre Stufenangabe.
- **README, Abschnitt Installation:** ergänzt um Python-Version, Einrichtung der virtuellen
  Umgebung, `.env` aus `.env.example`, Anmeldung bei Claude Code, `MOCK_MODE=false` für echte Daten
  und die benötigten Google-APIs. Places, Directions und Distance Matrix werden in der klassischen
  Variante genutzt, die Google seit dem 1. März 2025 als Legacy führt und in neuen Cloud-Projekten
  nicht mehr anbietet. Die Anleitung wurde in einer frischen Umgebung nachvollzogen: `python -m
  pytest` lief ohne Schlüssel durch, `pruefe_planung.py` erzeugte im Mock-Modus einen Plan.
- Kein `code_stand`-Snapshot und keine neue Station: keine Änderung an Code oder Verhalten.

## Offene Punkte

Bekannte Einschränkungen und nicht umgesetzte Punkte des aktuellen Stands.

- **Performance der Barrierefreiheitsprüfung:** `ist_barrierefrei()` fragt für die normalen
  POI-Kandidaten (außerhalb von Touren und Restaurants) weiterhin sequenziell je Kandidat Place Details
  ab. Bei vielen Rohtreffern und Stufe „mittel" oder „stark" bleibt das langsam (rund 37 Sekunden im
  Live-Test, Phase 44). Denkbar wäre eine Parallelisierung.
- **Bahnhöfe als POI-Karten am An- und Abreisetag** (Phase 38): das beobachtete Symptom ist nicht
  behoben, die pauschale Ausschlussliste wurde zurückgenommen. Zu klären ist, ob die Beschriftung, die
  Häufung an diesen Tagen oder etwas anderes stört.
- **Ursprüngliche Planungstestfälle fehlen** (Phase 36): `klettern_essen` (Voreinstellung in
  `pruefe_planung.py`) sowie die Personas Annegret, Jakob und Thomas sind nicht mehr vorhanden. Aktuell
  liegen vier Smoke-Tests in `planungs_testfaelle/`.
- **Prozessmodell:** keine visuelle Prüfung in diagrams.net; F04 und F18 noch am alten Ort (Phase 55).
- **Warnhinweis „30 von 15"** in `hole_echte_daten_fuer_vorschlag`, wenn die Obergrenze größer als die
  Trefferzahl ist. Reine Formulierung ohne Datenauswirkung (Phase 10).
- **Geografische Vorclusterung** der POIs vor dem tageweisen ILS-Lauf (erst Nahes gruppieren, dann auf
  Tage verteilen): Idee des Product Owners, ein eigener, größerer Eingriff in den ILS-Kern.
- **Monte-Carlo-Parameter** (Verteilung, Läufe, Schwelle) sind ein begründeter Vorschlag, nicht
  empirisch kalibriert; die Schwelle von 80 % hat der Product Owner festgelegt (Phase 45).
- **Robustheits-Gateway ohne Rückkopplung:** Das Konzept sieht vor, bei „nicht robust" mit
  Sicherheitspuffern neu zu optimieren. Umgesetzt ist nur die Anzeige „robust" oder „NICHT robust" im
  Reiseplan. Bewusst nicht gebaut: Nicht für jede Strecke existiert eine Verbindung, die das Kriterium
  erfüllt; eine automatische Neuplanung hätte ohne Abbruchkriterium eine unbegrenzte Folge
  kostenpflichtiger Verbindungsabfragen auslösen können (vgl. Kostenvorfall, Phase 52). Eine
  Rückkopplung mit Versuchsobergrenze und Kostenbudget bleibt Ausblick (Phase 82).
- **Abgleich mit der Referenzimplementierung:** die TOPTW/ILS-Umsetzung ist nicht gegen
  Constantino/TOPTW abgeglichen. Eine unabhängige Prüfung gegen OR-Tools und Brute-Force liegt vor
  (Phase 21) und ergänzt diesen Abgleich, ersetzt ihn aber nicht.
- **ILS-Reparaturschritt:** nach `_shake()` werden reparierte POIs immer hinten angehängt, nie an
  früheren Positionen versucht; nachgewiesen am Beispiel in `pruefe_algorithmus.py` (Score 13 statt 15,
  Phase 40). Nicht behoben.
- **Öffnungszeiten:** POIs gelten als ganztägig geöffnet, weil die Nearby Search keine vollständigen
  Öffnungszeiten ohne zusätzliche Detailabfrage je Ort liefert.
- **Sprachfunktionen im Browser** (Mikrofon, Vorlesen) wurden nicht systematisch in echten Browsern
  getestet.
- **Quellenliste nach Websuche** (Phase 64): Das Websuch-Werkzeug regt selbst eine Quellenliste an.
  Ob die Prompt-Regel wirkt, zeigt erst der nächste Live-Test. Folgt trotzdem eine Liste nach der
  Schnellantworten-Zeile, bleibt diese roh sichtbar; eine deterministische Kürzung wäre eine eigene,
  neue Entscheidung.
- **Formatierter Bot-Text im Browser** (Phase 64): Listenabstände, Linkfarbe und Öffnen im neuen Tab
  nicht manuell geprüft. Der JS-Test nutzt eine DOM-freie `escapeHtml`-Variante gleicher Wirkung,
  der DOM-Weg ist nur indirekt abgedeckt.
- **Umweltfreundlichste Auto-Route** (Phase 65):
  - Der Routenlink in `reiseplan.py` öffnet Google Maps mit dessen Standardwahl, nicht zwingend die
    Route mit grünem Blatt.
  - Es wird keine Abfahrtszeit übergeben; die Route berücksichtigt die Verkehrslage zum
    Planungszeitpunkt.
  - Das Feld `umweltfreundlichste_route` wird weder im Reiseplan noch in der Debug-Ausgabe angezeigt.
  - Eco-Routing gibt es nur bei Startorten in von Google unterstützten Ländern (u. a. DE, AT, CH, IT,
    FR, ES) und laut Google im Status Preview. Außerhalb davon ist ein Abbruch der Planung zu erwarten
    (HTTP-Fehler ohne Rückfall); fehlt lediglich die Kennzeichnung, greift der Rückfall auf die
    Standardroute. Beides ist nicht live geprüft. Für die Zielgruppe mit Wohnort in Deutschland
    unkritisch, vom Product Owner als Limitation akzeptiert.
- **Gesamtdesign der Web-Oberfläche** (Phase 66):
  - Die CO₂-Angabe im Titelbereich umfasst nur An- und Abreise; für die Wege vor Ort gibt es keine
    CO₂-Berechnung. Die Beschriftung „CO₂ An-/Abreise" benennt diese Einschränkung.
  - Fotograf und Lizenzhinweis der Galeriebilder stammen aus Internet-Archive-Kopien der
    Unsplash-Fotoseiten; eine manuelle Stichprobe auf den Originalseiten steht aus.
  - Der Sicherheitshinweis erscheint in der Web-Oberfläche weiterhin nur im Volltext des Plans (schon
    vor Phase 66 so).
  - Sichtprüfung nur im Headless-Browser mit Beispieldaten; kein echtes Gespräch, keine echten
    Google-Fotos, kein Test in Safari, Firefox oder auf Mobilgeräten; Überblenden und reduzierte
    Bewegung nicht im echten Browser beobachtet; Kontraste nur rechnerisch geprüft.
  - Der Punkt der Zeitleiste sitzt optisch sehr dicht am Tagestitel (kosmetisch).
- **Feste Wunschorte** (Phase 67):
  - Am Anreisetag wird die Uhrzeit-Regel nicht angewendet, auch wenn die Ankunftszeit bekannt ist; der
    Termin liegt dort am Tagesende (Entscheidung des Product Owners, zurückgestellt).
  - Mehrere Termine mit Uhrzeit am selben Tag werden ohne genaue Abfolge eingeplant.
  - Ein Termin mit Uhrzeit wird nicht gegen `tagesende_minuten` geprüft.
  - Der Rückweg wird symmetrisch zum Hinweg angenommen.
  - Der Monte-Carlo-Härtetest prüft die Anfahrt zum Wunschort nicht.
  - Die Barrierefreiheits-Nachprüfung des fertigen Plans in `plane_reise_und_abschliessen` umfasst die
    Termine nicht; für sie gibt es nur einen Hinweis, keine Neuplanungsschleife.
  - Die Eckdatenzeile nennt bei unvollständigen Kosten weiterhin „(ohne Unterkunft)", während der
    Text der Kostenschätzung inzwischen neutral formuliert ist.
  - Die CO₂-Angabe zur Anfahrt beruht auf den nicht amtlich verifizierten Emissionsfaktoren.
  - Ein vor der Unterkunftsbestätigung aufgelöster Ort wird danach nicht mit dem genaueren Ortsbezug
    neu gesucht.
  - Nicht gegen die echten Google-APIs und nicht mit dem Live-Verhalten des LLM geprüft.
- **Ergebnisansicht nach dem Live-Test** (Phase 68):
  - Besteht der Reisezeitraum nur aus einer Dauer ohne Datum (Rohtext „5 Tage"), zeigt die
    Eckdatenzeile „5 Tage · 5 Tage": Zeitraum und Tagesanzahl erscheinen doppelt.
  - Nicht auf einem echten Mobilgerät und nicht in einem erneuten Live-Dialog geprüft.
- **Beschriftung der Galerie** (Phase 70):
  - Im 96 px hohen Bildband schmaler Fenster (unter 980 px) verdeckt die zweizeilige Beschriftung
    mit ihrem Verlauf einen großen Teil des Bildes; lange Motive werden dort einzeilig gekürzt.
  - Nicht auf einem echten Mobilgerät geprüft.
- **Freigabe für externe Tester** (Phase 69):
  - Tunnel-Adresse und (ohne Eintrag in der `.env`) Token ändern sich bei jedem Start; eine feste
    Adresse erfordert ein Cloudflare-Konto mit eigener Domain.
  - Die Planung ist eine Python-Rechnung und teilt sich die CPU-Zeit: Während einer Planung werden
    andere Sitzungen langsamer, aber nicht angehalten.
  - Alle Testpersonen nutzen dasselbe Claude- und Google-Kontingent.
  - Der Rechner des Product Owners muss während der Tests laufen.
  - Der Tunnel wurde im Hands-on-Test der dritten Demonstrationsrunde genutzt: Beide Testpersonen
    haben den Prototyp über den Link selbst bedient (Phase 82). Mikrofon über HTTPS und gleichzeitige
    Nutzung durch mehrere Personen sind nicht gesondert dokumentiert.
- **Finales Demo-Feedback, Oberfläche und Dialog** (Phasen 71, 73, 74):
  - Titelzeile und Absätze der Begrüßung sind nicht im Browser geprüft (320, 390 und 980 px).
  - Ob das LLM eine Verweigerung des Namens im Live-Dialog respektiert, ist nicht geprüft.
  - Im Prozessmodell (`Modell_1_Reisebot_Prototyp_Datenfluss.drawio`, Seite F01) ist der Name noch
    nicht als freiwillige Angabe markiert.
  - Die Begrüßung wird über den Ein-/Ausgabekanal ausgegeben und ist nicht Teil des Verlaufs der
    Agenten-Session; das LLM sieht sie nicht und könnte den Nutzer erneut begrüßen.
- **CO₂-Berechnung und -Einordnung** (Phasen 75 und 76):
  - Für die gesamte Transit-Strecke gilt ein einziger Emissionsfaktor, einschließlich der Fußwege.
  - Von Google gelieferte Transit-Routen können deutlich länger sein als die Straßenroute (Venedig:
    Bahn 1483 km, Auto rund 1115 km) und belasten die Bahn dann rechnerisch.
  - Die CO₂-Angabe der Eckdatenzeile summiert ungerundete Werte und kann um 0,1 kg von der Summe der
    angezeigten Einzelwerte abweichen.
  - Kosten aus der km-Pauschale werden centgenau angezeigt, was eine nicht vorhandene Genauigkeit
    suggeriert.
  - Die Schwellen der CO₂-Einordnung (50 und 150 kg) sind eine vorläufige Setzung des Product Owners
    ohne Literaturbeleg.
  - Der Tooltip mit den Schwellen ist auf Touch-Geräten nicht erreichbar; Browser und Mobilgeräte
    sind nicht geprüft.
- **Lageprüfung der Unterkunft** (Phase 77):
  - Puffer (5 km), Mindestradius (10 km) und Rückfallschwelle (30 km) sind begründet gesetzt, aber
    nicht empirisch kalibriert.
  - Kein Live-Test mit echten Viewports der Geocoding API.
  - Die Adresse erscheint nur im Werkzeugergebnis an das LLM, nicht in der F15-Vorschaukarte und nicht
    im Reiseplan.
  - Im Mock-Modus liefern `geocode` und `geocode_gebiet` bewusst unterschiedliche Punkte.
  - Viewports, die den 180. Längengrad überschreiten, werden nicht gesondert behandelt.
- **Korrektur gespeicherter Werte durch das LLM** (Phase 79): Ungewollte Überarbeitungen bereits
  gespeicherter Werte sind möglich und nicht deterministisch ausgeschlossen.

### Entschieden oder erledigt

- Echte Hotelpreise statt Preisniveau-Schätzung: nicht vorgesehen (Product Owner, 24.08.2026).
- CO₂-Emissionsfaktoren und Preistabellen der Kostenschätzung: bleiben bei den aktuellen Faustwerten,
  keine weitere Verifizierung (Product Owner, 24.08.2026). Die Werte sind nicht amtlich verifiziert.
- Obergrenze für das Café-Zeitfenster: nicht vorgesehen (Product Owner, 24.08.2026).
- Mehrere Unterkünfte je Reise: nicht vorgesehen; es wird eine Reise mit einer Unterkunft geplant
  (Product Owner, 24.08.2026).
- Mailversand über Mailjet: eingerichtet und mit echter Zustellung getestet (12.08.2026).
- FlightAPI.io und Hotelbeds: gegenstandslos, in Phase 32 entfernt.
- Distanzmatrix-Cache über mehrere Unterkunftskandidaten: gegenstandslos seit Phase 32 (nur eine
  Unterkunft).
- Tagesablauf durch das LLM interpretiert: erledigt in Phase 33.
- Web-Oberfläche mit Bild- und Kurzinfo-Vorschau: erledigt in Phase 34.
- Browser-Test von `webapp.py` mit echtem Schlüssel: mehrfach durchgeführt, u. a. die 15-Tage-Testreise
  (Phasen 48/49).
- Prozessmodell auf die werkzeugbasierte Dialogsteuerung umgestellt: erledigt in Phase 51.
- `ist_barrierefrei()` gegen die echte Places-API: in den Live-Tests der Phasen 42 und 44 genutzt.
- Quellenliste nach Websuche: wird nur per Prompt-Anweisung unterbunden, keine Parser-Änderung
  (Product Owner, Phase 64). Die Schnellantworten-Chips bleiben erhalten.
- Fahrzeugtyp für die Auto-Route: wird nicht erfragt, es gilt Googles Standard Benzin (Product Owner,
  Phase 65).
- Interaktive Karte im Reiseplan: verworfen, weil sie den Google-Schlüssel im Browser erfordern würde
  (Phase 66).
- Chat nach Abschluss ausblendbar und größer während des Gesprächs (Demo-Feedback Iteration 2):
  erledigt in Phase 66.
- Explizit genannte Orte garantiert einplanen: abgelöst durch Phase 67. Ausdrücklich gewünschte Orte
  werden als fester Termin außerhalb von Optimierung 1 eingetragen; das erwogene Pflicht-POI-Merkmal
  im ILS ist verworfen, die Erkennung erfolgt über das Werkzeugargument `feste_wunschorte`.
- Antwortformate der Routes API: live bestätigt am 04.10.2026 (Hannover → Unterkunft Hamburg,
  FUEL_EFFICIENT-Route gewählt). Der dabei aufgedeckte Fehler bei Koordinatenpaaren im Feld `address`
  ist behoben (Phase 68, `_routes_api_wegpunkt`).
- Nachhaltigkeits-Nudge im fertigen Reiseplan: entfernt, er erscheint nur noch im F13-Dialog und im
  Sitzungsprotokoll (Phase 68).
- Chat nach Abschluss standardmäßig eingeklappt: revidiert in Phase 68, der Gesprächsverlauf bleibt
  standardmäßig sichtbar.
- Galerie-Kennzeichnung „Inspiration · Stimmungsbilder, kein Reisevorschlag": entfernt und durch eine
  Beschriftung je Bild mit Motiv und Bildnachweis ersetzt (Phase 70).
- Fotos vom Reiseziel in der Galerie über Google Places: prototypisch umgesetzt und wegen der
  laufenden API-Kosten je Gespräch zurückgebaut (Product Owner, Phase 70). Im finalen
  Demo-Feedback erneut gewünscht, aus Kostengründen weiterhin nicht umgesetzt (Phase 79).
- Titelzeile „Masterarbeit Prototyp Nick Poeppler" ohne Untertitel: erledigt in Phase 71.
- Wiederholungen unter „Weitere Empfehlungen": behoben in Phase 72; die Ursache überschneidender
  POI-ids von Places und Overpass ist in Phase 78 behoben.
- Name als Pflichtangabe: aufgehoben, F01 ist freiwillig (Phase 73).
- Begrüßung und Erklärung zu Beginn des Gesprächs: erledigt in Phase 74 (fester Text).
- CO₂-Berechnung: geprüft, kein Rechenfehler (Phase 75). Die Bezugsgröße des Auto-Faktors (Pkw mit
  einer Person, Mitreisende nicht berücksichtigt) verfolgt der Product Owner bewusst nicht weiter.
- Einordnung der CO₂-Menge: drei Stufen mit vorläufigen absoluten Schwellen (Phase 76).
- Unterkunft außerhalb des Reiseziels: Lagefilter mit Lageangabe für das LLM (Phase 77).
- Überarbeitung bereits gespeicherter Werte durch das LLM: bewusst beibehalten, damit Nutzer Angaben
  im Chat korrigieren können (Product Owner, Phase 79).
- Bezeichnung der Feedbackquelle: „Demo-Feedback", Rückmeldungen beider Testpersonen (Phase 81,
  revidiert Phase 80).
- Verfahrensauswahl Optimierung 1: Die Nutzwertanalyse wird nachträglich erstellt; sie dokumentiert
  die tatsächlich verwendeten Kriterien (Phase 82).
