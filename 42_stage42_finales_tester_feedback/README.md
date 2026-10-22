# Station 42 — Finales Demo-Feedback

**Zeitraum:** 13.10.2026 (ENTSCHEIDUNGSLOG.md Phasen 71–80)
**Code-Duplikat:** ja, `code_stand/` enthält den Stand **vor** dieser Station:

- vor Beginn der Umsetzung gesichert: `chat.py`, `static/index.html`, `src/ausgabe/reiseplan.py`,
  `src/fragekatalog/agent_tools.py`, `src/fragekatalog/katalog.py`,
  `src/optimierung/emissionsfaktoren.py`, `tests/test_agent_tools.py`,
  `tests/test_emissionsfaktoren.py`, `tests/test_reiseplan.py`, `tests/test_webapp.py`;
- vor den Paketen zu Lageprüfung und POI-ids gesichert, nach der Umbenennung der Feedbackquelle
  (Phase 80): `src/api/google_maps.py`, `src/api/typen.py`, `src/api/overpass.py`,
  `src/fragekatalog/vorschlaege.py`, `src/datenaufbereitung/poi_sammlung.py`, `src/pipeline.py`,
  `tests/test_google_maps.py`, `tests/test_poi_sammlung.py`, `tests/test_vorschlaege.py`. Diese
  Kopien enthalten in Kommentaren bereits den Begriff „HULLS-Feedback" (seit Phase 81
  „Demo-Feedback", siehe Station 43). `overpass.py` und
  `pipeline.py` wurden vorsorglich gesichert und sind unverändert geblieben;
- `src/api/mock_data.py` wurde erst nach der Änderung gesichert. Die Kopie ist aus dem aktuellen
  Stand rekonstruiert, indem die rein additive Änderung (Import von `ZielGebiet`, Adressen der
  Beispielunterkünfte, `BEISPIEL_ZIELGEBIET`) zurückgerechnet wurde.

Nicht im Duplikat liegen `tests/conftest.py` (Testübersicht ergänzt), `tests/test_eckdaten_chips.py`
(drei Tests ergänzt) und `tests/test_pipeline.py` (ein Test ergänzt) sowie die neuen Dateien
`src/datenaufbereitung/lagepruefung.py`, `tests/test_lagepruefung.py`, `tests/test_begruessung.py`
und `tests/test_titelzeile.py`.

## Auslöser

Finales Demo-Feedback aus der abschließenden Testrunde (`Program/Finales Feedback/Feedback.docx`)
mit acht Punkten. Zwei Punkte (4 und 6) führten bei der Analyse zu je einem Folgebefund, der
ebenfalls behoben wurde.

| Punkt im Feedback | Umgang | Phase |
|---|---|---|
| 1 Begrüßung und kurze Erklärung zu Beginn | feste Begrüßung | 74 |
| 2 Namensangabe wird erzwungen | Name freiwillig | 73 |
| 3 Einordnung der CO₂-Menge fehlt (Vorschlag: Ampel) | drei Stufen mit vorläufigen Schwellen | 76 |
| 4 CO₂-Berechnung prüfen | geprüft, kein Rechenfehler | 75 |
| ↳ Folgebefund: Unterkunft außerhalb des Ziels | Lagefilter und Lageangabe | 77 |
| 5 LLM überarbeitet bereits eingetragene Werte | bewusst beibehalten | 79 |
| 6 Wiederholungen unter „Weitere Empfehlungen" | Abgleich in der Ausgabe | 72 |
| ↳ Folgebefund: doppelte POI-ids aus Places und Overpass | eindeutige Neunummerierung | 78 |
| 7 Bilder passend zum gewählten Reiseziel | aus Kostengründen nicht umgesetzt | 79 |
| 8 Titelzeile nur „Masterarbeit Prototyp Nick Poeppler" | umgesetzt | 71 |

## Umsetzung

### Titelzeile (Punkt 8, Phase 71)

Das `<h1>` in `static/index.html` lautet nur noch „Masterarbeit Prototyp Nick Poeppler"; Untertitel
und CSS-Regel `header p` entfallen. Weil der Titel länger ist als der frühere Schriftzug „Reisebot",
bricht er auf schmalen Fenstern zwischen den Wörtern um; `overflow-wrap: break-word` verhindert, dass
ein einzelnes Wort über den Rand ragt. Der Tab-Titel bleibt „Reisebot", das Feedback betrifft nur die
sichtbare Titelzeile.

*Verworfen:* eine kleinere Schrift auf schmalen Bildschirmen (der Umbruch genügt); eine Änderung des
Tab-Titels.

### Keine Wiederholungen unter „Weitere Empfehlungen" (Punkt 6, Phase 72)

**Ursache.** `_verteile_beispiele_auf_leere_tage` (`src/ausgabe/reiseplan.py`) verteilt nicht
eingeplante Kandidaten als Beispiele auf Tage ohne Programm und liefert die übrigen als Restliste.
`als_text` und `als_html` nutzten diese Restliste, `als_kartendaten` dagegen die vollständige Liste.
Die Wiederholungen traten deshalb nur in der Web-Oberfläche auf. Weitere Ursachen doppelter Orte: Der
Mock-Client lieferte einen Beispielort für jedes passende Interesse erneut, die internen ids von
Places und Overpass überschnitten sich, und der gewählte Verleih wurde nicht abgeglichen.

**Lösung.** `_ort_schluessel` identifiziert einen Ort über die `place_id`, sonst über den Namen.
`_nicht_anderweitig_gezeigte_kandidaten` entfernt aus den nicht eingeplanten Kandidaten jeden Ort,
der bereits als Tagespunkt, Tour- oder Lernaktivitätsbeispiel, Markt-, Café- oder Restaurantbeispiel,
Verleih oder fester Termin im Plan steht, und lässt jeden Ort höchstens einmal zu. Alle drei
Ausgaben (Text, Mail, Web) verwenden diese bereinigte Liste und die daraus entstehende Restliste.

**Warum so.** Ein Abgleich an einer Stelle hält die drei Ausgaben deckungsgleich. Der Ort selbst ist
der Schlüssel, weil Verleih und feste Termine aus eigenen Suchen ohne gemeinsame `id` stammen.

*Verworfen:* Abgleich über die interne `id`; Bereinigung in `pipeline.py` (würde die CSV-Übersicht
aller POI-Kandidaten verfälschen); eine reine Einzeilenkorrektur in `als_kartendaten`.

### Eindeutige POI-ids (Folgebefund zu Punkt 6, Phase 78)

Places- und Overpass-Client nummerieren ihre Treffer unabhängig ab 1. Weil die `id` nachgelagert als
Identität dient, vermischte die Reisezeitmatrix (Schlüssel `(von.id, nach.id)`) die Einträge zweier
Orte, `toptw.py::plane_gesamte_reise` entfernte über die besuchten ids einen fremden POI, und
`pipeline.py::plane_reise` ließ Overpass-Kandidaten still verschwinden.

`sammle_pois` (`src/datenaufbereitung/poi_sammlung.py`) vergibt die ids am Ende fortlaufend ab 1 neu;
`id` 0 bleibt der Unterkunft als Depot. Es ist die einzige Stelle, an der beide Quellen
zusammenkommen. `MockGoogleMapsClient.suche_pois` liefert jeden Beispielort nur einmal, damit ein Ort
nach der Neunummerierung nicht mehrere ids erhält. Optimierung 1 und 2 sind algorithmisch
unverändert.

*Verworfen:* ein Versatz nur für Overpass-ids; eine Abstimmung der Nummerierung zwischen den Clients;
die Umstellung aller Schlüssel auf `place_id` bzw. Name; das Belassen der Mock-Duplikate.

### Name als freiwillige Angabe (Punkt 2, Phase 73)

Im Sitzungsprotokoll vom 13.10.2026 (`web_5417ce01_2026-10-13_130631.jsonl`) verweigerte die
Testperson ihren Namen; das LLM bestand auf einer Angabe und speicherte „Herr". Das Feld `name`
(F01) wird nirgends ausgewertet, weder im Reiseplan noch beim Mailversand (Empfänger ist F02) noch in
den Kartendaten. Der bisherige Hinweis, der Name werde für den Versand benötigt, war sachlich falsch.

F01 (`src/fragekatalog/katalog.py`) ist jetzt kein Pflichtfeld mehr. Der Kontexthinweis beschreibt
die Angabe als freiwillig und nur für die persönliche Ansprache gedacht; bei Verweigerung soll das LLM
nicht nachhaken und keinen Platzhalternamen wie „Herr", „Gast" oder „Anonym" speichern. Die Frage
wird weiterhin gestellt. Der Abschluss ist ohne Namen möglich, ohne E-Mail-Adresse weiterhin
gesperrt. Grund ist die Datensparsamkeit: Für die Pflichtangabe gab es keinen fachlichen Zweck.

*Verworfen:* F01 überspringbar machen oder entfernen (die Frage soll gestellt, nur nicht erzwungen
werden); nur den Kontexthinweis ändern (der Pflichtstatus hätte den Abschluss weiter blockiert).

### Feste Begrüßung mit Erklärung (Punkt 1, Phase 74)

Die erste Nachricht lautete bisher „Schön, dass Sie da sind! …" und stand noch in der Sie-Form. Die
neue Konstante `BEGRUESSUNG` in `chat.py` wird von `a1_reisewunsch_aeussern` ausgegeben, in Web und
Konsole identisch:

> Hallo und herzlich willkommen!
>
> Ich helfe dir, eine Reise mit Hin- und Rückreise ohne Flugzeug und einer Unterkunft vor Ort zu
> planen. Dazu stelle ich dir ein paar Fragen; Orte und Unterkünfte kommen aus echten Kartendaten, vor
> allem von Google Maps. Am Ende bekommst du einen Tag-für-Tag-Plan mit grober Kostenschätzung und dem
> CO₂-Ausstoß der An- und Abreise. Deine Angaben kannst du jederzeit im Chat korrigieren.
>
> Erzähl mir zuerst in eigenen Worten: Was schwebt dir für eine Reise vor?

Jede Aussage ist im Prototyp belegt: keine Flüge (Grundprinzip 5), genau eine Unterkunft
(Grundprinzip 4), Google Maps als Hauptquelle, Tagesplan mit Kostenschätzung und CO₂ der An- und
Abreise, Korrektur über ein erneutes `speichere_feld`. Ein fester Text stellt sicher, dass die
Erklärung nichts verspricht, was der Prototyp nicht leistet (Grundprinzip 1).

*Verworfen:* ein vom LLM formulierter Einstieg (Grundprinzip 1); ein Willkommens-Overlay (die
Begrüßung bleibt Teil des Gesprächs, für Web und Konsole gleich); der Begriff „Rundreise" (legt
wechselnde Unterkünfte nahe); die Erwähnung des Mailversands (nur mit Mailjet-Zugangsdaten aktiv);
ein Hinweis auf den freiwilligen Namen (Länge).

### Prüfung der CO₂-Berechnung (Punkt 4, Phase 75)

Die Berechnung (`co2_kg`: Distanz in km × g/Pkm / 1000, Meter korrekt in km umgerechnet, Hin- und
Rückreise getrennt, Summe ungerundet gebildet und dann gerundet) enthält keinen Rechenfehler. Die
Rückrechnung gegen drei Sitzungsprotokolle vom 10. und 13.10.2026 ergab plausible Strecken für
Resse → München (Bahn, 12,6 kg ≈ 663 km) und Hannover → Göteborg (Bahn, 19,4/19,9 kg ≈ 1021/1047 km).
Im Venedig-Fall entsprachen 141,2/141,5 kg mit dem Auto rund 840 km statt der erwarteten rund 1115 km:
Die Strecke führte zur Unterkunft in Südtirol (Folgebefund, Phase 77).

Die auffälligen Werte erklären sich aus Modellannahmen, nicht aus Rechenfehlern: Platzhalterfaktoren
(Entscheidung des Product Owners vom 24.08.2026), ein Faktor für die gesamte Transit-Strecke
einschließlich Fußwegen, Transit-Routen von Google, die deutlich länger sein können als die
Straßenroute (Venedig: Bahn 1483 km, Auto rund 1115 km), eine mögliche Abweichung der summierten
CO₂-Angabe um 0,1 kg von der Summe der angezeigten Einzelwerte und centgenau angezeigte Kosten aus
einer km-Pauschale. Die Bezugsgröße des Auto-Faktors (Pkw mit einer Person, Mitreisende nicht
berücksichtigt) verfolgt der Product Owner bewusst nicht weiter. Keine Dateiänderung.

### Einordnung der CO₂-Menge (Punkt 3, Phase 76)

`co2_einstufung` (`src/optimierung/emissionsfaktoren.py`) ordnet die Summe aus Hin- und Rückreise
ein: genügsam bis einschließlich 50 kg, mittel bis einschließlich 150 kg, darüber CO₂-lastig. Die
Schwellen stehen als Konstanten an einer Stelle; der Hinweistext wird daraus erzeugt. Eingestuft wird
der angezeigte, auf eine Nachkommastelle gerundete Wert (`_co2_an_abreise_kg` in `reiseplan.py`).
`_eckdaten` liefert die Einstufung an die Web-Oberfläche; Text und Mail nennen nach der Rückreise eine
Zeile mit Menge, Stufe und Schwellen. In der Eckdatenzeile folgt auf die CO₂-Angabe die Stufe als
Wort mit kleinem Farbpunkt und einem Tooltip zu Schwellen und Einschränkungen, ohne Rahmen,
Hintergrund oder Hover-Effekt; der CO₂-Wert selbst bleibt ungefärbt.

**Schwellen.** Platzhalter und eigene, vorläufige Setzung des Product Owners. Die gesichtete Literatur
in `Quellen/` belegt keine konkreten Schwellen: Ruiz-Meza & Montoya-Torres (2021) stützen nur die
Berechnung als Distanz × Faktor je Personenkilometer, Klarin et al. (2023) nur die qualitative
Reihenfolge der Verkehrsmittel.

**Teilweise Revision von Station 39 (Phase 68).** Dort war die farbige Hervorhebung des CO₂-Werts
entfernt worden, weil sie wie eine getroffene Auswahl wirkte. Die Farbe kehrt nur an der
Stufenbezeichnung zurück, nicht-interaktiv und ohne Vergleich mit anderen Verkehrsmitteln.

**Warum so.** Die Einstufung ist deterministisch und gehört in den regelbasierten Layer
(Grundprinzip 3), damit alle Ausgaben dieselbe Stufe zeigen. Absolute Schwellen statt eines
Vergleichs mit den Alternativen, weil ein solcher Vergleich im fertigen Plan einem Nudge entspräche.

*Verworfen:* eine relative Ampel gegenüber den Alternativen; die Umsetzung erst nach Fund einer
Quelle für die Schwellen; die Einstufung durch das LLM oder nur im Skript der Oberfläche; Farbe als
einziger Bedeutungsträger und eine Pillen-Optik; ein Vergleichssatz.

### Lageprüfung der Unterkunft (Folgebefund zu Punkt 4, Phase 77)

**Befund.** Im Venedig-Gespräch lag die bestätigte Unterkunft rund 136 km entfernt in Südtirol, der
erste Vorschlag war „Kleines Hotel Kärnten". Bei der Nearby Search mit Freitext-`keyword` ist der
Radius nur eine Bevorzugung; `suche_unterkunft` übernahm den ersten Treffer ohne Lageprüfung, und das
LLM erhielt keine Lageangabe. Optimierung 1 plante deshalb keinen einzigen Besuch (Depot in Südtirol,
POIs in Venedig), An- und Abreise sowie CO₂ wurden nach Südtirol berechnet.

**Lösung (Entscheidung des Product Owners: Lagefilter und Transparenz).**

- `geocode_gebiet` (`src/api/google_maps.py`) liefert neben dem Mittelpunkt das Gebiet des Ziels
  (`ZielGebiet` in `typen.py`): bevorzugt `viewport`, ersatzweise `bounds`. Das Ergebnis wird je
  Client-Instanz zwischengespeichert; `geocode` nutzt denselben Weg. Dadurch verursacht die Prüfung
  im Normalfall keinen zusätzlichen API-Aufruf.
- Das neue Modul `src/datenaufbereitung/lagepruefung.py` entscheidet, ob ein Treffer am Ziel liegt:
  innerhalb von 10 km um den Mittelpunkt oder im Viewport zuzüglich 5 km; ohne Viewport nur innerhalb
  von 30 km. Die Reihenfolge der Google-Relevanz bleibt erhalten.
- `suche_unterkunft` (`vorschlaege.py`) filtert die Treffer nach Lage. Bleibt nichts übrig, wird
  einmal ohne Freitext gesucht und dies dem LLM offen mitgeteilt. Ohne Ergebnis meldet das Werkzeug
  ehrlich, dass in oder um das Ziel nichts gefunden wurde, und untersagt eine Unterkunft aus eigenem
  Wissen. Das Werkzeugergebnis nennt Adresse (`vicinity`) und Luftlinien-Entfernung; der F15-Hinweis
  in `katalog.py` verlangt, die Lage beim Vorschlag zu nennen.
- Der Mock-Modus bildet jedes Ziel auf ein Beispielgebiet ab, damit er ohne API-Schlüssel
  durchspielbar bleibt.

**Warum so.** Die Lage ist objektiv berechenbar (Grundprinzip 3) und bestimmt die gesamte Planung.
Das Gebiet aus dem Geocoding berücksichtigt, dass Städte und Regionen unterschiedlich groß sind; der
Puffer erfasst Stadtrand und angrenzende Ortsteile, der Mindestradius den Nachbarort kleiner Orte,
die Rückfallschwelle eine Stadt mit Umland.

*Verworfen:* ein fester Kilometerwert als alleiniges Kriterium; eine Text Search „Anforderung in
Ziel" allein (Ortsbezug ebenfalls nur gewichtend); Transparenz ohne Filter.

### Bewusst beibehalten bzw. nicht umgesetzt (Punkte 5 und 7, Phase 79)

**Korrektur gespeicherter Werte.** Eine bestimmte Formulierung der Testperson führte dazu, dass das
LLM einen bereits eingetragenen Wert vor dem Absenden überarbeitete (Testfall und Feld nicht
protokolliert). Der Product Owner behält dieses Verhalten bewusst bei: Vertippt sich ein Nutzer, muss
er den Wert per Chat korrigieren können. Grundlage ist die Regel in `regelwerk.py`, `speichere_feld`
bei einer revidierten Angabe erneut aufzurufen (Korrekturschleife seit Phase 4); die Begrüßung kündigt
die Korrekturmöglichkeit an. Das LLM ändert Werte auf Grundlage von Nutzeraussagen und erfindet keine,
`speichere_feld` validiert weiterhin. Das Spannungsfeld zur Rollenbeschreibung in `chat.py`
(großzügig interpretieren, aber keine Werte erfinden) bleibt bestehen. *Verworfen:* gespeicherte
Werte sperren oder nur nach ausdrücklicher Bestätigung ändern. Ungewollte Überarbeitungen sind damit
nicht deterministisch ausgeschlossen.

**Bilder vom Reiseziel.** Der Wunsch, nach der Zielwahl vorrangig Bilder des Ziels zu zeigen, wurde
erneut geäußert. Er bleibt aus Kostengründen unumgesetzt; die in Station 41 (Phase 70) erprobte
Variante mit Google-Places-Fotos war wegen der laufenden API-Kosten zurückgebaut worden.

### Bezeichnung der Feedbackquelle (Phase 80)

Die Rückmeldungen aus den Demonstrationen stammen von einer im HULLS-Projekt forschenden Person, nicht
von den Betreuenden der Arbeit. Auf Festlegung des Product Owners heißen sie in Dokumentation und Code
„HULLS-Feedback" (28 Dateien außerhalb der `code_stand/`-Ordner, darunter eine Herkunftsangabe im
Prompt-Text `_TOOL_ANLEITUNG`, ohne inhaltliche Änderung der Anweisungen). Der Begriff ist im Kopf von
`ENTSCHEIDUNGSLOG.md` definiert. Die `code_stand/`-Kopien bleiben als Archiv unverändert.

Revidiert in Phase 81
([Station 43](../43_stage43_feedbackquelle_beide_testpersonen/README.md)): Das Feedback stammt von beiden Testpersonen,
der im HULLS-Projekt forschenden Person und dem Betreuer der Arbeit; der Begriff lautet seitdem
„Demo-Feedback".

## Verifikation

- Neue bzw. erweiterte Tests: `tests/test_titelzeile.py` (3), `tests/test_reiseplan.py` (4 zu den
  Empfehlungen, 3 zur CO₂-Einordnung), `tests/test_agent_tools.py` (3), `tests/test_begruessung.py`
  (9), `tests/test_emissionsfaktoren.py` (7), `tests/test_eckdaten_chips.py` (3, per Node.js),
  `tests/test_webapp.py` (1), `tests/test_lagepruefung.py` (12), `tests/test_vorschlaege.py` (10),
  `tests/test_google_maps.py` (5 zur Lageprüfung, 1 zum Mock), `tests/test_poi_sammlung.py` (3),
  `tests/test_pipeline.py` (1).
- Komplette Suite grün (559/559; 494 nach Station 41).
- Gegenproben gegen den Vorher-Stand: Die vier Empfehlungs-Tests schlagen mit dem gesicherten
  `reiseplan.py` fehl, die vier id-Tests in `test_poi_sammlung.py` und `test_pipeline.py` mit dem
  gesicherten `poi_sammlung.py`.
- Die CO₂-Prüfung (Phase 75) beruht auf einer Rückrechnung gegen die Sitzungsprotokolle
  `web_d10edabf_2026-10-10_133740.jsonl`, `web_d9f714e2_2026-10-13_123002.jsonl` und
  `web_5417ce01_2026-10-13_130631.jsonl`.
- Nicht geprüft: die Darstellung von Titelzeile, Begrüßung und CO₂-Einordnung im Browser und auf
  Mobilgeräten; das Live-Verhalten des LLM bei verweigertem Namen; die Lageprüfung mit echten
  Viewports der Geocoding API und in einem Live-Dialog.

## Offene Punkte

- Browserprüfung von Titelzeile (320, 390, 980 px), Begrüßungsabsätzen und CO₂-Einordnung; der
  Tooltip ist auf Touch-Geräten nicht erreichbar.
- Live-Test, ob das LLM eine Verweigerung des Namens respektiert; im Prozessmodell
  (`Modell_1_Reisebot_Prototyp_Datenfluss.drawio`, Seite F01) ist der Name noch nicht als freiwillig
  markiert.
- Die Begrüßung ist nicht Teil des Verlaufs der Agenten-Session; das LLM könnte erneut begrüßen.
- CO₂: ein Faktor für die gesamte Transit-Strecke; lange Transit-Routen; Rundungsabweichung von bis zu
  0,1 kg; centgenaue Kosten aus einer Pauschale; Schwellen der Einordnung ohne Literaturbeleg.
- Lageprüfung: Werte 5, 10 und 30 km nicht empirisch kalibriert; kein Live-Test; Adresse nicht in
  der F15-Vorschaukarte und im Reiseplan; Mock-`geocode` und Mock-`geocode_gebiet` liefern bewusst
  unterschiedliche Punkte; Viewports über den 180. Längengrad nicht behandelt.
- Ungewollte Überarbeitungen gespeicherter Werte durch das LLM sind nicht deterministisch
  ausgeschlossen.
