"""
Testübersicht des Reisebot-Prototyps.

Diese Datei enthält keine gemeinsamen Fixtures, sondern dient als Übersicht, welches Modul durch
welche Testdatei abgedeckt ist. Alle Tests sind deterministisch und laufen ohne LLM und ohne echte
API-Aufrufe (Mock-Modus bzw. gemockte HTTP-Antworten). Ausführung aus dem Projektverzeichnis:
`python -m pytest -q` (Konfiguration in pytest.ini; `doku/` ist von der Testsammlung
ausgeschlossen, weil dort eingefrorene Code-Stände liegen).

Die Begründung einzelner Regressionstests steht als Kommentar direkt am Test und ausführlich im
ENTSCHEIDUNGSLOG.md (Phasennummer im Kommentar).

Testdatei                    Geprüftes Modul                           Schwerpunkt
---------------------------  ----------------------------------------  ---------------------------------
test_fragekatalog.py         fragekatalog/katalog.py, schema.py        Konsistenz von Katalog und Schema
test_agent_tools.py          fragekatalog/agent_tools.py               Werkzeuge des LLM-Agenten, Pflicht-
                                                                       feldsperre, Statussignal, Protokoll
test_vorschlaege.py          fragekatalog/vorschlaege.py               API-gestützte Vorschläge (Typ C),
                                                                       Verleihsuche, Distanz-Alternative
test_google_maps.py          api/google_maps.py                        Places/Directions/Distance Matrix,
                                                                       Teilstrecken, Foto-Fallback
test_overpass.py             api/overpass.py                           OSM-Spezialrecherche
test_poi_sammlung.py         datenaufbereitung/poi_sammlung.py         Zusammenführen der POI-Quellen
test_aufbereitung.py         datenaufbereitung/aufbereitung.py         Scoring, POI-Auswahl, Reisedauer,
                                                                       Tageszeitfenster, Leihwunsch
test_vertraeglichkeit.py     datenaufbereitung/vertraeglichkeit.py     harte Ausschlüsse (Allergien,
                                                                       Barrierefreiheitsstufen)
test_toptw.py                optimierung/toptw.py                      Optimierung 1 (Greedy + ILS),
                                                                       Zeitfenster, Mindestabstände
test_verkehrsmittelwahl.py   optimierung/verkehrsmittelwahl.py         Optimierung 2, Nachhaltigkeits-Nudge
test_emissionsfaktoren.py    optimierung/emissionsfaktoren.py          CO2-Berechnung
test_monte_carlo.py          optimierung/monte_carlo.py                Härtetest der Umstiege
test_kostenschaetzung.py     optimierung/kostenschaetzung.py           informative Kostenschätzung
test_pipeline.py             pipeline.py                               Gesamtablauf der Planung,
                                                                       Sondertage, Restaurants/Bars
test_reiseplan.py            ausgabe/reiseplan.py                      Text-/HTML-Ausgabe, Kartendaten,
                                                                       Zeitanzeige, Routen-Links
test_fotos.py                ausgabe/fotos.py                          serverseitiger Foto-Download
test_debug.py                ausgabe/debug.py                          Debug-Datei je Planung
test_kanal.py                audio/kanal.py                            Ein-/Ausgabekanäle, Schnellantworten,
                                                                       Markdown-Bereinigung
test_regelwerk.py            fragekatalog/regelwerk.py                 Regeln im Systemprompt
test_webapp.py               webapp.py                                 WebSocket-Kanal der Web-Oberfläche
test_zugriffsschutz.py       webapp.py                                 Zugangstoken, Cookie, WebSocket-
                                                                       Sperre, Log-Maskierung
test_starte_extern.py        starte_extern.py                          Tunnel-Adresse, Link, Token
test_bot_text_formatierung.py static/index.html (Node.js)              Formatierung des Bot-Texts,
                                                                       Escaping, Vorlesetext
test_titelzeile.py           static/index.html                         Titelzeile und Browser-Tab-Titel
test_begruessung.py          chat.py                                   feste Begrüßung zu Sitzungsbeginn

Nicht per pytest geprüft wird das Gesprächsverhalten des LLM (welche Frage wann gestellt oder
übersprungen wird). Das ist nur in echten Live-Läufen beobachtbar (ENTSCHEIDUNGSLOG.md, Phase 10).
"""
