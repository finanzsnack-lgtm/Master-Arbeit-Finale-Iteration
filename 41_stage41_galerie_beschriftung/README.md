# Station 41 — Galerie: Beschriftung je Bild

**Zeitraum:** 06.10.2026 (ENTSCHEIDUNGSLOG.md Phase 70)
**Code-Duplikat:** ja, `code_stand/` enthält den Vorher-Stand von `static/index.html`,
`static/img/galerie/QUELLEN.md` und `tests/test_galerie.py`.

## Auslöser

Rückmeldung des Product Owners zur Galerie neben dem Chat (Station 37) anhand eines
Live-Screenshots: Bei den Stimmungsbildern war nicht erkennbar, wo ein Foto aufgenommen wurde und
was darauf zu sehen ist. Die Kennzeichnung „Inspiration · Stimmungsbilder, kein Reisevorschlag"
wurde als überflüssig bewertet.

## Umsetzung

**Kennzeichnung entfernt (`static/index.html`).** Die Pille „Inspiration · Stimmungsbilder, kein
Reisevorschlag" entfällt. Das `aria-label` der Galerie lautet „Galerie mit Stimmungsbildern".

**Beschriftung je Bild (`static/index.html`).** Jedes Stimmungsbild trägt unten auf einem dunklen
Verlauf zwei Zeilen:

- Zeile 1: das Motiv, wörtlich aus der Spalte „Motiv" in `static/img/galerie/QUELLEN.md`, z. B.
  „Blaue Kirchenkuppel mit Bougainvillea, Oia, Santorini (Griechenland)".
- Zeile 2: der Bildnachweis „Foto: Fotograf / Unsplash", z. B. „Foto: Xuan Nguyen / Unsplash".

`GALERIE_BILDER` erhält dafür je Bild das Feld `motiv`. Die Funktion `galerieBeschriftung` im
abgegrenzten Block GALERIE-BESCHRIFTUNG bildet beide Zeilen; dargestellt wird per `textContent`,
nie als HTML. Die Beschriftung wechselt erst mit dem sichtbaren Bild, damit Bild und Text
zusammenpassen. Der Verlauf ist so gewählt, dass der Text auch über hellen Bildbereichen den
WCAG-AA-Kontrast einhält (rechnerisch etwa 6:1). Ab 980 px darf das Motiv zweizeilig umbrechen;
im schmalen Bildband wird es einzeilig mit Auslassungspunkten gekürzt. Der bisherige separate
Bildnachweis unten rechts geht in der Beschriftung auf.

**`QUELLEN.md`.** Die Einleitung spricht von der „Galerie neben dem Chat" statt der Spalte
„Inspiration", beschreibt die Beschriftung und verweist auf die Prüfung in `tests/test_galerie.py`.

**Revision von Station 37.** Dort war die Vereinbarkeit der Galerie mit Phase 57 (kein angedeuteter
Planbereich während des Gesprächs) unter anderem mit der Kennzeichnung als Inspiration begründet.
Die Kennzeichnung entfällt; die Bilder bleiben lokale Stimmungsbilder ohne Bezug zum geplanten
Reiseziel.

**Warum so.** Ort und Motiv sollen für den Nutzer erkennbar sein; die Kennzeichnung trug dazu nichts
bei (Rückmeldung des Product Owners). Die Beschriftung übernimmt nur Angaben, die in `QUELLEN.md`
belegt sind (Grundprinzip 1).

**Verworfene Alternativen.**

- Fotos vom tatsächlichen Reiseziel über Google Places, sobald das Ziel feststeht. Die Variante wurde
  prototypisch umgesetzt und mit einem echten Abruf für Hamburg geprüft. Auf Entscheidung des
  Product Owners wurde sie wegen der laufenden API-Kosten (eine Text Search und bis zu acht
  Place-Photo-Abrufe je Ziel und Gespräch) vollständig zurückgebaut; davon ist kein Code mehr
  vorhanden. Damit bleibt es bei der bisherigen Regel, dass Fotos von Google erst nach dem
  Planungsabschluss geladen werden (einzige Ausnahme weiterhin die Vorschaukarte der Unterkunft).
- Aufteilung des Motivs in getrennte Angaben zu Motiv und Ort: hätte Ortsangaben ergänzt, die in
  `QUELLEN.md` nicht stehen.

## Verifikation

- Neue Tests in `tests/test_galerie.py`: Motiv und Fotograf in `GALERIE_BILDER` stimmen mit
  `QUELLEN.md` überein; die Pille ist entfernt; die Beschriftung aller Stimmungsbilder wird per
  Node.js aus dem Block GALERIE-BESCHRIFTUNG erzeugt und geprüft (ohne Node.js übersprungen); ein
  Einzelbeispiel (Lavendelfeld).
- Komplette Suite grün (494/494; 490 nach Station 40).
- JavaScript-Syntax mit `node --check` geprüft.
- Sichtprüfung im Headless-Browser: Stimmungsbild Santorini mit Motiv und Bildnachweis.
- Eine Volltextsuche im Code findet keine Bestandteile der zurückgebauten Variante mit Fotos vom
  Reiseziel mehr.
- Nicht geprüft: ein echtes Mobilgerät.

## Offene Punkte

- Im 96 px hohen Bildband schmaler Fenster (unter 980 px) verdeckt die zweizeilige Beschriftung mit
  ihrem Verlauf einen großen Teil des Bildes; lange Motive werden dort einzeilig gekürzt.
