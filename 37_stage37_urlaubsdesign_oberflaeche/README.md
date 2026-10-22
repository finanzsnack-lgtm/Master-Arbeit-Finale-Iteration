# Station 37 — Gesamtdesign der Web-Oberfläche („Urlaubsgefühl")

**Zeitraum:** 29.09.2026 (ENTSCHEIDUNGSLOG.md Phase 66)
**Code-Duplikat:** `code_stand/` enthält den Stand **vor** dieser Station (`src/ausgabe/reiseplan.py`,
`src/pipeline.py`, `static/index.html`, `tests/test_reiseplan.py`, `webapp.py`). `webapp.py` wurde
vorsorglich gesichert und ist unverändert geblieben.

## Auslöser

Demo-Feedback aus der Demo von Iteration 2 (`Program/Iteration 2/Feedback Demo Iteration 2.txt`):

- „Gestaltung des Reiseplans": Das Seitenkonzept soll überarbeitet werden. Die gesamte Oberfläche soll
  während des Gesprächs und bei der Ausgabe des fertigen Plans ansprechender wirken und ein
  Urlaubsgefühl vermitteln, z. B. durch wechselnde Bilder von Urlaubszielen neben dem Chat. Der Chat
  könnte nach Abschluss der Planung ausblendbar sein.
- „Chat-Bereich": Der Chat soll größer dargestellt werden.

Präzisierung des Product Owners: Vorbilder bei etablierten Reiseportalen suchen und übertragbare
Elemente übernehmen.

## Herkunft der Gestaltungselemente

Recherche vom 29.09.2026. Jedes neue Gestaltungselement ist einem Vorbild und einer Quelle zugeordnet.

| Element im Prototyp | Vorbild | Quelle |
|---|---|---|
| Viel Weißraum, große Foto-Karten mit Rundung, Schatten und Hover-Effekt | Airbnb (klare, elegante Startseite, zentrales Suchfeld, große Fotos) | https://mediaboom.com/news/travel-website-design/ |
| Eckdaten-Chips direkt unter dem Titel | Booking.com (Fakten und Vertrauenssignale nahe am Entscheidungspunkt) | https://mediaboom.com/news/travel-website-design/ ; https://econsultancy.com/excellent-examples-content-design-ux-travel-websites/ |
| Galerie „Inspiration" neben dem Chat | Mindtrip (Fotos, Karten und Bewertungen in einer Ansicht neben dem Chat) | https://www.travelanywhere.blog/blog/best-agentic-ai-travel-apps-2026-mindtrip-layla-stippl-stardrift-wanderlog-tested |
| Tage als vertikale Zeitleiste | Wanderlog (Programm nach Tagen gruppiert) | https://www.travelanywhere.blog/blog/best-agentic-ai-travel-apps-2026-mindtrip-layla-stippl-stardrift-wanderlog-tested |
| Titelbild und großflächige Galerie | Trend zu immersiven, großflächigen Bildern | https://mediaboom.com/news/travel-website-design/ ; https://www.designmonks.co/blog/travel-website-design-examples |

**Einschränkung:** Die gefundenen Vergleichsartikel beschreiben die Portale überwiegend funktional,
Designdetails nur knapp. Die Übertragung auf den Prototyp ist eine eigene Gestaltungsentscheidung auf
Basis dieser Beschreibungen, keine Nachbildung einzelner Portale.

## Umsetzung

**Daten für den Titelbereich (`src/ausgabe/reiseplan.py`, `src/pipeline.py`).**

- `Reiseplan` erhält die Felder `reisezeitraum_rohtext`, `reise_start_datum` und `reise_end_datum`.
  `pipeline.py` übernimmt sie nach demselben Muster wie `budget_gesamt` unverändert aus der
  `ReiseAnfrage`; die Tagesberechnung bleibt in `aufbereitung.py`.
- Die neue Konstante `ZIELORT_PLATZHALTER` („Zielregion") ersetzt das bisherige Literal in
  `pipeline.py`. In den Eckdaten gilt der Platzhalter als „kein Zielort"; ein Titel „Deine Reise nach
  Zielregion" kann so nicht entstehen.
- `_zeitraum_text` zeigt „TT.MM.JJJJ – TT.MM.JJJJ" nur, wenn beide ISO-Daten lesbar sind
  (`_iso_als_deutsches_datum`), sonst die wörtliche F06-Antwort, sonst `None`. Ein Datum wird nie
  geraten.
- `als_kartendaten` liefert zusätzlich `eckdaten` (aus `_eckdaten`: Zielort, Zeitraum, Anzahl Tage,
  Verkehrsmittel für Hin- und Rückreise, `co2_an_abreise_kg` als Summe von Hin- und Rückreise auf eine
  Nachkommastelle, Kosten pro Person, `kosten_unvollstaendig`) und `titelbild_url` (aus
  `_titelbild_url`: Foto der Unterkunft, sonst das erste vorhandene POI-Foto in Tagesreihenfolge,
  sonst `None`).
- Alle Werte stammen aus bereits berechneten Planwerten und bereits geladenen Fotos; es entstehen keine
  zusätzlichen API- oder Foto-Anfragen. Fehlt ein Wert, bleibt er `None` (Grundprinzip 1).

**Gesprächsansicht (`static/index.html`).**

- Ab 980 px Breite ein Grid mit dem Chat als Hauptelement (ca. 60 % der Breite, `3fr`/`2fr`) in fast
  voller Fensterhöhe. Die Eingabezeile steht unten, nur der Verlauf scrollt; `overflow-x: hidden`
  (Phase 61) bleibt erhalten.
- Rechts die Galerie-Spalte, sichtbar beschriftet mit „Inspiration · Stimmungsbilder, kein
  Reisevorschlag", mit Bildnachweis je Bild. Zwei übereinanderliegende `img`-Ebenen blenden alle 7 s
  über 1,4 s über. Das nächste Bild wird erst nach vollständigem Laden eingeblendet; das Startbild ist
  zufällig. Bei `prefers-reduced-motion: reduce` bleibt ein Standbild stehen.
- Unter 980 px steht ein 96 px hohes Bildband über dem Chat; der Chat nutzt `100dvh`.
- Mit dem Eintreffen des Plans blendet `main.abgeschlossen` die Galerie aus, `stoppeGalerie` beendet
  den Bildwechsel.

**Galeriebilder (`static/img/galerie/`).** Zehn Unsplash-Fotos (157–283 KB): Lago di Toblino,
Manarola, ein Lavendelfeld, eine Bergbahn in der Schweiz, ein Viadukt bei Filisur, Luzern, Bled, die
Toskana, ein norwegischer Fjord und Santorini. Auswahlkriterien: keine Personen im Vordergrund, nur
als „Free" gekennzeichnete Fotos, kein Unsplash+. `static/img/galerie/QUELLEN.md` führt je Datei
Motiv, Fotograf, Unsplash-Seite und Lizenz (Unsplash License). Fotograf und Lizenzhinweis wurden aus
Internet-Archive-Kopien der Fotoseiten gelesen, weil unsplash.com automatisierte Abrufe mit einer
Bot-Prüfung blockiert. Die Bilder wurden einmalig in reduzierter Auflösung vom Unsplash-CDN geladen
und werden lokal ausgeliefert.

**Farbwelt und Schrift.** Sandton `#f7f1e6` als Hintergrund, Meerblau `#1f5f7a` als zweiter Akzent,
Grün `#2f6f4f` bleibt der Nachhaltigkeitsakzent. Überschriften nutzen einen System-Serif-Stack (Iowan
Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia), ohne externe Schriftquelle.

**Ergebnisansicht.**

- Titelbereich „Deine Reise nach {Zielort}" bzw. „Deine Reise" mit Titelbild. Ohne Foto erscheint ein
  Farbverlauf von Meerblau zu Grün; ein dunkler Verlauf über dem Bild sichert den Textkontrast.
- Eckdaten-Chips (Block ECKDATEN-CHIPS ANFANG/ENDE): Zeitraum; „n Tage" bzw. „1 Tag"; das
  Verkehrsmittel einmal oder „Hin: X · Zurück: Y"; „CO₂ An-/Abreise: x kg"; „ca. x € p. P.", bei
  unvollständiger Schätzung mit dem Zusatz „(ohne Unterkunft)". Fehlt ein Wert, entfällt der Chip.
- Darunter der Nudge, dann die Tage als vertikale Zeitleiste (`ol.zeitleiste`) unter „Tag für Tag".
  (Chip-Optik und Nudge in Station 39 revidiert.)
- Die Reihenfolge bleibt: Hinreise, Unterkunft, Verleih, Tage, Weitere Empfehlungen, Rückreise,
  Volltext. Der Vorschläge-Rahmen steht weiterhin direkt nach den POI-Karten eines Tages.
- Karten mit 180 px hohem Foto, Eckradius 18 px, Schatten und Hover-Effekt.

**Chat nach Abschluss.** Standardmäßig eingeklappt. Ein schwebender Knopf „Chat"/„Chat schließen"
(`aria-expanded`, Escape schließt) öffnet ein überlagerndes Panel mit dem vollständigen Verlauf. Die
Eingabezeile bleibt ausgeblendet (Phase 60). (In Station 39 revidiert: Gesprächsverlauf
standardmäßig sichtbar.)

**Unverändert funktionsfähig:** Schnellantwort-Chips, Mikrofon und Vorlesen, Hotel-Vorschaukarte
(F15), Status-Sprechblase, Tipp-Animation, Avatar, Verleihkarte, Links und Volltext. Der Block
BOT-TEXT-FORMATIERUNG aus Station 35 ist byte-identisch.

**Revision früherer Entscheidungen.** Station 29 (Phase 57) hatte festgelegt, dass der Chat während
des Gesprächs groß und zentriert bleibt, ohne Andeutung des Planbereichs. Jetzt teilt er sich die
Breite mit der Galerie. Das bleibt mit dem Anliegen von Phase 57 vereinbar, weil die Galerie
ausdrücklich als Inspiration gekennzeichnet ist und nicht als Planbereich wirkt. Das Abschlusslayout
aus Station 30 (Phase 58: schmaler Chat links, sticky) ist durch das einklappbare Panel ersetzt.

**Verworfene Alternativen.**

- Interaktive Karte nach dem Vorbild von Wanderlog: erfordert den Google-Schlüssel im Browser und
  verletzt das Grundprinzip, dass der Schlüssel den Browser nie erreicht.
- Externe Schriftquelle (Font-CDN) und direktes Einbinden der Bilder von Unsplash (Hotlinking): keine
  externen Anfragen zur Laufzeit.
- Symbolbild als Rückfall für das Titelbild: würde fälschlich wie der Zielort wirken; stattdessen
  Farbverlauf.
- Harter Bildwechsel bei reduzierter Bewegung: stattdessen ein Standbild.

## Verifikation

- `tests/test_reiseplan.py`: 9 neue Tests zu Eckdaten und Titelbild.
- `tests/test_galerie.py` (neu, 5 Tests): `QUELLEN.md` und Bilddateien stimmen 1:1 überein, Angaben
  vollständig, jede Datei unter 300 KB, `GALERIE_BILDER` im Skript passt zu den Dateien, keine
  externen Einbindungen.
- `tests/test_eckdaten_chips.py` (neu, 5 Tests): führt den Block ECKDATEN-CHIPS per Node.js aus.
- Komplette Suite grün (383/383). JavaScript-Syntax mit `node --check` geprüft.
- Sichtprüfung im Headless-Chrome mit einem Beispielplan bei 1280, 500 und 390 px Breite: kein
  horizontales Scrollen bei 390 px, Chat-Panel öffnet und schließt, Reihenfolge korrekt.

Nicht geprüft: ein echtes Gespräch mit dem LLM und echten Google-Fotos, das Überblenden in Echtzeit,
reduzierte Bewegung in einem echten Browser, Safari, Firefox und Mobilgeräte. Kontraste wurden nur
rechnerisch ermittelt.

## Offene Punkte

- Der CO₂-Chip umfasst nur An- und Abreise; für die Wege vor Ort liegt keine CO₂-Berechnung vor.
- Bildmetadaten stammen aus Internet-Archive-Kopien; eine manuelle Stichprobe auf den
  Unsplash-Originalseiten steht aus.
- Der Sicherheitshinweis erscheint in der Web-Oberfläche weiterhin nur im Volltext (schon vorher so).
- Sichtprüfung nur headless mit Beispieldaten.
- Der Punkt der Zeitleiste sitzt optisch sehr dicht am Tagestitel (kosmetisch).
