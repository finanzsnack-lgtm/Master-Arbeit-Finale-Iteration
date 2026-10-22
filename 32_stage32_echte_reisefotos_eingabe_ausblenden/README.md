# Station 32 — Echte Fotos für An- und Abreise, Eingabezeile nach Abschluss ausgeblendet

**Zeitraum:** 21.09.2026 (ENTSCHEIDUNGSLOG.md Phase 60)
**Code-Duplikat:** [`code_stand/`](code_stand/) mit `src/ausgabe/reiseplan.py`, `static/index.html` und
`tests/test_reiseplan.py` vor der Änderung.

## Auslöser

1. Der Product Owner lieferte zwei Referenzfotos (ein ICE in Fahrt, eine Person mit Sonnenhut am
   offenen Autofenster) und wünschte echte Fotos in diesem Stil statt der Illustrationen aus
   Station 30.
2. Im Abschlusszustand war die Eingabezeile noch sichtbar, obwohl keine weitere Eingabe möglich ist.

## 1. Echte Fotos statt Illustrationen

**Entscheidung:** lizenzfreie Fotos mit gesicherter freier Lizenz statt eigener Vektorgrafik. Quelle ist
Unsplash (Unsplash-Lizenz: kostenlose kommerzielle und private Nutzung ohne Genehmigung).

**Vorgehen:** Suchbeschreibungen passten mehrfach nicht zum Bildinhalt (ein als Roadtrip-Motiv
beschriebenes Bild zeigte einen Hut auf einem parkenden Auto; ein Zugmotiv zeigte nur ein
Bahnhofsschild). Jeder Kandidat wurde deshalb heruntergeladen und visuell geprüft. Ein
kostenpflichtiges Unsplash+-Bild wurde anhand der Lizenzangabe erkannt und verworfen.

**Bildquellen** (in `static/img/`):

| Datei | Motiv | Urheber |
|---|---|---|
| `bahn.jpg` | „Silver and red bullet train", Stuttgart Hbf | Markus Winkler |
| `auto.jpg` | „The way to the cabin" | Averie Woodard |
| `bus.jpg` | weißer Fernbus auf Landstraße, Stirling (UK) | C (@thecurlyone) |

Das Busfoto wurde ergänzt, damit alle drei Karten stilistisch zusammenpassen.
`_STANDARDBILD_JE_VERKEHRSMITTEL` verweist auf die `.jpg`-Dateien; die alten Illustrationen wurden
entfernt, `avatar.svg` bleibt.

## 2. Eingabezeile ausgeblendet

Beim Eintreffen des fertigen Plans wird `form.hidden = true` gesetzt. Zusätzlich nötig war die Regel
`form#eingabeform[hidden] { display: none; }`, weil die spezifischere `display: flex`-Deklaration das
native `hidden` sonst überschreibt.

## 3. Nebenfund: pytest sammelte Tests aus `code_stand/`

Nach Punkt 1 schlugen zwei Tests fehl, und zwar die eingefrorene Kopie in `code_stand/tests/`, die noch
die alten Pfade erwartet. `pytest.ini` schloss `doku/` nicht aus; das fiel erst auf, als zum ersten Mal
eine Testdatei in einen Snapshot kopiert wurde. Behoben über `norecursedirs = … doku`. Snapshots
dürfen damit auch Testdateien enthalten, ohne die Suite zu verfälschen.

## Verifikation

Suite 335/335 grün, JavaScript-Syntax mit Node.js geprüft.

## Offene Punkte

- Der Bus ist im Bildausschnitt eher klein; ob er in der Kartengröße 220×130 px gut erkennbar bleibt,
  ist nicht im Browser geprüft.
