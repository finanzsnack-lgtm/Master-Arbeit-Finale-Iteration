# Station 43 — Feedbackquelle: beide Testpersonen

**Zeitraum:** 18.10.2026 (ENTSCHEIDUNGSLOG.md Phase 81)
**Code-Duplikat:** nein (transparent vermerkt): reine Begriffsänderung in Kommentaren, Docstrings, einer
Herkunftsangabe im Prompt-Text und in der Dokumentation, ohne Logikänderung.

## Auslöser

Hinweis des Product Owners: Das Feedback aus allen drei Demonstrationsrunden stammt von zwei
Testpersonen, einer im HULLS-Projekt forschenden Person und dem Betreuer der Arbeit. Die Festlegung in
Phase 80 ([Station 42](../42_stage42_finales_tester_feedback/README.md)), die Rückmeldungen stammten
nicht von den Betreuenden der Arbeit, traf nicht zu.

## Umsetzung

- Begriff „Demo-Feedback" statt „HULLS-Feedback" in 36 Markdown-, Python- und HTML-Dateien außerhalb
  der `code_stand/`-Ordner. Betroffen sind Kommentare und Docstrings in `src/`, `tests/`, `chat.py`,
  `webapp.py` und `static/index.html`, die Stations-READMEs 28, 35–38 und 42, `doku/README.md`,
  `ARCHITEKTUR.md` und `ENTSCHEIDUNGSLOG.md`.
- In `regelwerk.py` ändert sich in `_TOOL_ANLEITUNG` (Abschnitt SCHNELLANTWORTEN) nur die
  Herkunftsangabe in Klammern; die Anweisungen an das LLM sind inhaltlich unverändert.
- Definition im Kopf von `ENTSCHEIDUNGSLOG.md` und in `ARCHITEKTUR.md`: **Demo-Feedback** bezeichnet die
  Rückmeldungen der beiden Testpersonen aus den Demonstrationen, einer im HULLS-Projekt forschenden
  Person und des Betreuers der Arbeit.
- Überschrift von Phase 56 und Station 28: „Demo-Feedback zur Web-Oberfläche" statt „Web-Feedback aus
  dem HULLS-Projekt".
- Bewusst unverändert: der Wortlaut von Phase 80 als historischer Eintrag (in Station 42 um einen
  Revisionsvermerk ergänzt), die `code_stand/`-Kopien und die Angabe in Phase 79, dass der Testfall zu
  Punkt 5 des finalen Feedbacks von der Person aus dem HULLS-Projekt stammt.

## Verifikation

- Alle geänderten Python-Dateien kompilieren.
- Komplette Suite grün (559/559), ausgeführt auf einer Kopie des aktuellen Stands mit den geänderten
  Dateien.
- Außerhalb von Phase 80, dem Revisionsvermerk in Station 42, dem Index-Eintrag zu Station 42 und den
  `code_stand/`-Kopien kommt der Begriff „HULLS-Feedback" nicht mehr vor.

## Offene Punkte

- Die Quellenangabe in `Program/Finales Feedback/Feedback.docx` nennt nur die Person aus dem
  HULLS-Projekt.
