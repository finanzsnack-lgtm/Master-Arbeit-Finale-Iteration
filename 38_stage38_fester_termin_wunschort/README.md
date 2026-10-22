# Station 38 — Fester Termin für ausdrücklich gewünschte Orte

**Zeitraum:** 29.09.2026 (ENTSCHEIDUNGSLOG.md Phase 67)
**Code-Duplikat:** `code_stand/` enthält den Stand **vor** dieser Station (`pruefe_planung.py`,
`src/pipeline.py`, `src/api/google_maps.py`, `src/api/mock_data.py`, `src/ausgabe/debug.py`,
`src/ausgabe/fotos.py`, `src/ausgabe/reiseplan.py`, `src/fragekatalog/agent_tools.py`,
`src/fragekatalog/katalog.py`, `src/fragekatalog/regelwerk.py`, `src/fragekatalog/schema.py`,
`src/optimierung/kostenschaetzung.py`, `static/index.html` sowie die betroffenen Tests). Nicht im
Duplikat liegen die rein additiv erweiterten Dateien `src/api/typen.py`,
`src/optimierung/verkehrsmittelwahl.py`, `src/datenaufbereitung/vertraeglichkeit.py`,
`tests/test_debug.py`, `tests/test_verkehrsmittelwahl.py` und die neuen Dateien
`src/fragekatalog/wunschorte.py`, `tests/test_fester_termin_karte.py` und
`planungs_testfaelle/smoketest_feste_wunschorte.json`. `tests/test_webapp.py` wurde vorsorglich
gesichert.

## Auslöser

Demo-Feedback aus der Demo von Iteration 2 (`Program/Iteration 2/Feedback Demo Iteration 2.txt`),
Punkt „Berücksichtigung dedizierter Standorte": Nennt der Nutzer ausdrücklich einen Ort, den er unter
allen Umständen sehen möchte, wird an einem Tag ein fester Zeitslot freigehalten und der Ort direkt
dort eingetragen, ohne ihn an den Optimierungsalgorithmus zu übergeben. Liegt der Ort sehr weit
entfernt, soll das System auf die Auswirkungen auf die Nachhaltigkeit hinweisen.

Präzisierung des Product Owners: Der Wunschort darf nie aussortiert werden. Bei großer Entfernung
wird auf die Nachhaltigkeitsfolgen hingewiesen, die Entscheidung trifft der Nutzer. Das Muster
entspricht den Touren und Lernaktivitäten, die bereits außerhalb von Optimierung 1 eingetragen werden
(Stationen 25 und 26).

Bis dahin wurden ausdrücklich genannte Orte nur über den Score priorisiert und nicht garantiert
eingeplant (früherer offener Punkt „Explizit genannte Orte").

## Umsetzung

### D1 — Wunschort erkennen und finden

- **Datentypen.** `GefundenerOrt` (`src/api/typen.py`) enthält Name, Adresse, Koordinaten, `place_id`,
  `kategorie`, `foto_referenz` und `preisniveau`. Er ist bewusst kein `POI`: Ein Wunschort durchläuft
  Optimierung 1 nicht und braucht weder Score noch Zeitfenster, wohl aber die Adresse, damit der
  gefundene Ort im Gespräch bestätigt werden kann. `FesterWunschort` (`schema.py`) hält Rohname,
  gefundenen Ort, Besuchsdauer, optionale Uhrzeit, Barrierefreiheits-Befund und Anfahrt;
  `ReiseAnfrage.feste_wunschorte` sammelt die Einträge.
- **Suche.** `finde_ort(suchtext, nahe_bei)` nutzt die Places Text Search ohne den Zusatz
  „in {Ziel}", weil ein Wunschort außerhalb der Zielregion liegen darf. Der Ortsbezug entsteht über
  `location`/`radius` (50 km, `_FINDE_ORT_BEZUG_RADIUS_METER`); die Text Search gewichtet damit nur.
  Gewählt wird der nächstgelegene Treffer (`_naechster_treffer`). Ohne Treffer liefert die Methode
  `None`, bei einem API-Fehler einen `RuntimeError`. Der Mock-Modus nutzt `BEISPIEL_WUNSCHORTE`.
- **Werkzeugargument.** `speichere_feld` erhält `feste_wunschorte` als Liste
  `{name, dauer_minuten?, uhrzeit_minuten?}`; ohne Angabe gilt eine Besuchsdauer von 120 Minuten
  (`STANDARD_BESUCHSDAUER_WUNSCHORT_MINUTEN` in `src/fragekatalog/wunschorte.py`). Der Regelwerk-Block
  `_FESTE_WUNSCHORTE_REGEL` legt fest: nur bei ausdrücklicher „unbedingt"-Aussage, nicht proaktiv,
  immer die vollständige Liste; eine leere Liste entfernt alle Einträge. Der F16-Kontexthinweis in
  `katalog.py` verweist darauf. Es gibt keine Schlüsselwort-Heuristik im Code; die Erkennung liegt
  wie bei Sicherheit und Mobilitätseinschränkung beim LLM.
- **Auflösung** (`loese_wunschorte_auf`). Gleichnamige Einträge werden wiederverwendet und sparen
  Places-Aufrufe. Nicht gefundene, ungültige oder doppelte Einträge werden nicht gespeichert und dem
  LLM ehrlich gemeldet. Bei Mobilitätseinschränkung „mittel" oder „stark" prüft
  `pruefe_barrierefreiheit_offener_wunschorte` die Barrierefreiheit und gibt einen Hinweis aus; der
  Ort wird nicht ausgeschlossen, weil der ausdrückliche Wunsch Vorrang hat.

### D2 — Anfahrt und Nachhaltigkeitshinweis

- **Verkehrsmittel (Variante b, Entscheidung des Product Owners).** Ab der bestätigten Unterkunft wird
  zuerst das lokale Verkehrsmittel aus F14 über die Distance Matrix geprüft. Ist die einfache Strecke
  länger als 60 Minuten (`SCHWELLE_WEITER_WUNSCHORT_MINUTEN`) oder gibt es kein Ergebnis, wird
  `reisealternativen(Unterkunft, Wunschort)` passend zur F13-Präferenz genutzt; für das Auto gilt damit
  automatisch die umweltfreundlichste Route aus Station 36. Die F13-Regel liegt dafür zentral in
  `verkehrsmittelwahl.nur_bestaetigte_verkehrsmittel`; `pipeline._nur_bestaetigte_verkehrsmittel`
  leitet nur noch weiter.
- **Ergebnis.** `WunschortAnfahrt` (`schema.py`) enthält Verkehrsmittel, Dauer, Quelle, Modus,
  Distanz, CO₂ für Hin- und Rückweg, Kosten der einfachen Strecke und das Kennzeichen der
  umweltfreundlichsten Route.
- **Hinweis.** Über 60 Minuten nennt der Hinweis Entfernung in km, Dauer und grob geschätztes CO₂ für
  Hin- und Rückweg (Emissionsfaktoren nicht amtlich verifiziert). Das LLM fragt ausdrücklich, ob der
  Ort bleiben soll; ein Verzicht erfolgt durch erneutes Speichern der Liste. Maßgeblich ist die Dauer
  der tatsächlich gewählten Anfahrt (Bestätigung des Product Owners).
- **Zeitpunkt der Prüfung.** Je Unterkunft einmal, bei einem Unterkunftswechsel erneut. Ohne
  Unterkunft wird die Prüfung zurückgestellt und bei F15 nachgeholt. `plane_reise_und_abschliessen`
  schlägt einmalig fehl, wenn dabei ein neuer Hinweis entsteht, damit der Nutzer vor der Planung
  entscheiden kann. Ohne Landverbindung erfolgt eine ehrliche Meldung; Flüge werden nicht angeboten
  (Grundprinzip 5).

### D3 — Einplanung in der Pipeline (`src/pipeline.py`)

- `_volle_optimierungstage` ist die gemeinsame Definition voller Tage (weder Anreise- noch Abreise-
  noch Sondertag) für die Mittagsblock-Kürzung bei lokalem Kontakt und für die Tagwahl der Termine.
- `_einplanbare_wunschorte` holt ausstehende Prüfungen nach. Ein Ort ohne Anfahrt oder ohne
  Unterkunftskoordinaten wird nicht eingeplant und erscheint als Hinweis in
  `Reiseplan.feste_termine_hinweise` (Bestätigung des Product Owners). Ohne echte Wegzeit wäre die
  Budgetkürzung falsch (Grundprinzip 1).
- `_budget_nach_termin`:
  - ohne Uhrzeit: Budget − (Besuchsdauer + 2 × Weg), der Termin liegt am Tagesende;
  - mit Uhrzeit, bekanntem Tagesstart (F20) und nicht am Anreisetag: min(Budget, Uhrzeit − Hinweg −
    Tagesstart − Mittagsblock-Kürzung), der Termin schließt den Tag ab. Beispiel: 15:00 Uhr, 30 Min.
    Hinweg, Tagesstart 9:00 Uhr ergibt 330 Minuten;
  - Untergrenze jeweils 0; der Tag enthält dann nur den Termin.
- `_plane_feste_termine` belegt volle Tage der Reihe nach und danach reihum mit sich addierenden
  Kürzungen. Ohne vollen Tag wird der Abreisetag, dann Tag 1 gewählt, sofern das Budget für Besuch
  samt Hin- und Rückweg reicht; sonst entsteht ein Hinweis.
- POIs mit derselben `place_id` wie ein Termin werden vor `filtere_pois_hart` entfernt, damit der Ort
  weder doppelt besucht noch unter den weiteren Empfehlungen erscheint.
- TOPTW/ILS erhalten den Termin nie; es ändert sich ausschließlich `tagesbudget_je_tag`.
- Ein negativer oder fehlender Barrierefreiheits-Befund erscheint nur bei aktueller Stufe „mittel" oder
  „stark" unter den Einschränkungshinweisen.
- Kostenschätzung (`kostenschaetzung.py`): Preisniveau des Termins sowie Anfahrtskosten mit
  2 × `kosten_euro_einfach`, berechnet wie bei An- und Abreise aus Fahrpreis oder km-Pauschale
  (Entscheidung des Product Owners, kein Zusatzfeld im API-Layer).
- Debug-Ausgabe (`debug.py`): Abschnitt „6. FESTE WUNSCHORTE" mit Tag sowie Budget vorher und nachher.
- `FesterTermin(tag_nr, wunschort, am_tagesende)` in `reiseplan.py`.
- `pruefe_planung.py` löst Wunschorte aus der Testdatei wie im Dialog auf. Neuer Testfall
  `planungs_testfaelle/smoketest_feste_wunschorte.json`: München, Deutsches Museum mit 180 Minuten,
  Schloss Neuschwanstein um 15:00 Uhr.

### D4 — Ausgabe

- `als_text`, `als_html` und `als_kartendaten` zeigen „Fester Termin" als eigenen Eintrag nach der
  optimierten Route und vor den Vorschlägen des Tages: Name, Adresse, Zeitpunkt, Dauer, Anfahrt; km
  und CO₂ nur, wenn vorhanden, CO₂ als grobe Schätzung; Google-Maps-Link und Routenlink ab der
  Unterkunft.
- Die Uhrzeit wird nur angezeigt, wenn sie das Budget bestimmt hat; sonst steht „am Ende des Tages"
  mit einem Vermerk zur genannten Uhrzeit.
- Nicht einplanbare Orte erscheinen als Hinweis. Tage mit Termin zeigen keine generischen Beispiele.
  Bei unvollständiger Kostenschätzung steht ein neutraler Text.
- `fotos.py` lädt Fotos auch für Termine.
- `static/index.html`, Block FESTER-TERMIN-KARTE: eigene Kartenart ohne `label`, durchgehender blauer
  Rahmen, gefülltes Badge „Fester Termin – dein ausdrücklicher Wunsch". Hinweise zu nicht
  einplanbaren Orten stehen in `#termin-hinweise` und werden per `textContent` gesetzt. Der Termin ist
  ein bestätigter Nutzerwunsch und unterscheidet sich deshalb sichtbar von den Vorschlägen.

**Zusätzlich:** Die Anrede der gesamten Text- und Mail-Ausgabe ist auf „du" vereinheitlicht
(14 Stellen in `reiseplan.py`, im Sicherheitshinweis in `pipeline.py` und im Ernährungshinweis in
`datenaufbereitung/vertraeglichkeit.py`), passend zu Chat und Web-Oberfläche.

### Verworfene Alternativen

- Pflicht-POI-Merkmal im TOPTW/ILS, das der Algorithmus zuerst einfügt: widerspricht der Vorgabe, den
  Ort nicht an den Algorithmus zu übergeben.
- Schlüsselwort-Erkennung im Code: die Beurteilung liegt beim LLM.
- `POI` als Typ für den Wunschort: Score und Zeitfenster wären ohne Bedeutung, die Adresse fehlte.
- Ausschluss bei fehlender Barrierefreiheit: stattdessen ein Hinweis.
- Variante (a), nur das lokale Verkehrsmittel, und Variante (c), immer das nachhaltigste
  Verkehrsmittel unabhängig von F13.
- Schwelle nach km oder Luftlinie statt nach Fahrzeit.
- Eigenes Bestätigungs-Argument beim Abschluss; separate Abfrage des Rückwegs; Neusuche des Orts nach
  Bestätigung der Unterkunft.
- Aufteilung eines Tages in zwei Routen vor und nach dem Termin.
- Einplanung mit geschätzter Anfahrt; eine erfundene Uhrzeit ohne F20-Angabe.
- Darstellung des Termins im Vorschlagsstil mit gestricheltem Rahmen.

## Verifikation

- Komplette Suite grün (455/455; 383 vor dieser Station, D1 +22, D2 +15, D3 +20, D4 +15 Tests) in
  `test_agent_tools.py`, `test_google_maps.py`, `test_regelwerk.py`, `test_verkehrsmittelwahl.py`,
  `test_pipeline.py`, `test_debug.py`, `test_reiseplan.py`, `test_fotos.py` und dem neuen
  `test_fester_termin_karte.py`.
- Regression: Ohne Wunschorte entsteht ein identischer Plan (Abgleich gegen den Stand in `code_stand/`
  in vier Fällen).
- Sichtprüfung im Headless-Browser mit einem Beispielplan. In einem echten 390, 360 und 320 px breiten
  Rahmen kein Überlauf. Eine zuvor beobachtete Abschneidung der Karten war ein Messfehler, weil
  Headless-Chrome nicht schmaler als 500 px rendert.

Nicht geprüft: die echten Google-APIs (Text Search, Distance Matrix und Routes für die Anfahrt), das
Live-Verhalten des LLM bei der Erkennung ausdrücklicher Wunschorte und ein Live-Lauf von
`pruefe_planung.py` mit dem neuen Testfall (API-Kosten).

## Offene Punkte

- Am Anreisetag wird die Uhrzeit-Regel nicht angewendet, auch bei bekannter Ankunftszeit
  (Entscheidung des Product Owners, zurückgestellt).
- Mehrere Termine mit Uhrzeit am selben Tag werden ohne genaue Abfolge eingeplant.
- Ein Termin mit Uhrzeit wird nicht gegen `tagesende_minuten` geprüft.
- Der Rückweg wird symmetrisch zum Hinweg angenommen.
- Der Monte-Carlo-Härtetest prüft die Anfahrt zum Wunschort nicht.
- Die Barrierefreiheits-Nachprüfung des fertigen Plans umfasst die Termine nicht; es gibt nur einen
  Hinweis, keine Neuplanungsschleife.
- Der Eckdaten-Chip nennt bei unvollständigen Kosten weiterhin „(ohne Unterkunft)".
- Die CO₂-Angabe beruht auf nicht amtlich verifizierten Emissionsfaktoren.
- Ein vor der Unterkunftsbestätigung aufgelöster Ort wird danach nicht mit dem genaueren Ortsbezug neu
  gesucht.
