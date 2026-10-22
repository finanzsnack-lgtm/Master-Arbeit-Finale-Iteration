# Station 35 — Formatierter Bot-Text, keine Quellenliste nach den Schnellantworten

**Zeitraum:** 29.09.2026 (ENTSCHEIDUNGSLOG.md Phase 64)
**Kein Code-Duplikat** (kein `code_stand`-Snapshot vorgesehen, transparent vermerkt).

## Auslöser

Demo-Feedback aus der Demo von Iteration 2 (`Program/Iteration 2/Feedback Demo Iteration 2.txt`)
mit zwei Punkten:

- **Textformatierung:** Fett gemeinte Textstellen erschienen im Browser mit Sternchen statt im
  Fettdruck. Belegt im Protokoll `protokolle/web_2026-09-21_120230.jsonl`, Zeilen 15–17 und 28.
- **Zusatzelemente:** Die Schnellantworten als Klick-Optionen bleiben erhalten. Zu vermeiden ist, dass
  das LLM die Zeile „[SCHNELLANTWORTEN: …]" als Text in die Nachricht schreibt und darunter eine Liste
  der Quellen („Sources:") anhängt. Der Product Owner hat präzisiert, dass damit nicht das Ausblenden
  der Chips gemeint ist.

Ursache des zweiten Punkts: Nach einer Websuche hängt das LLM die Quellenliste hinter die
Schnellantworten-Zeile. `_SCHNELLANTWORTEN_MUSTER` in `src/audio/kanal.py` ist mit `$` am
Nachrichtenende verankert und erkennt die Zeile in diesem Fall nicht, sodass sie roh sichtbar bleibt.

## Umsetzung

**Browser.** `static/index.html` erhält einen eigenen, kleinen Renderer (Block
BOT-TEXT-FORMATIERUNG):

- `formatiereBotText` escaped zuerst den gesamten Text als HTML, einschließlich `"` und `'`, damit
  eine Link-Adresse nicht aus dem `href`-Attribut ausbrechen kann. Erst danach werden gezielt eigene
  Tags eingesetzt: `<ul><li>` für Zeilen mit „- ", über `formatiereZeile` `<strong>` für `**…**` und
  `<a target="_blank" rel="noopener noreferrer">` für Markdown-Links. Links werden nur mit
  http/https-Adresse umgewandelt, andere Schemata bleiben Text. Vom LLM gelieferte HTML-Tags
  erscheinen dadurch immer als reiner Text.
- Formatiert werden nur Bot-Nachrichten. Nutzer-, System- und Statusnachrichten werden weiter als
  reiner Text gesetzt.
- `botTextAlsKlartext` liefert für das Vorlesen denselben Text ohne Markdown-Zeichen, bei Links nur
  den Linktext.

**Konsole und Sprachausgabe.** Neue Funktion `entferne_markdown(text, links_mit_adresse=False)` in
`src/audio/kanal.py` mit denselben Mustern wie im Browser. `TextKanal` gibt Links als „Text (URL)"
aus, weil die Adresse in der Konsole nutzbar bleibt; `AudioKanal` spricht nur den Linktext, weil eine
vorgelesene Adresse unverständlich wäre. „- "-Aufzählungen bleiben als Text lesbar und werden nicht
verändert. `zerlege_schnellantworten` und `_SCHNELLANTWORTEN_MUSTER` bleiben unverändert und laufen vor
der Markdown-Entfernung.

**Regelwerk.** In `_TOOL_ANLEITUNG` (`src/fragekatalog/regelwerk.py`):

- neuer Absatz FORMATIERUNG: nur **fett** und einfache „- "-Aufzählungen, keine Überschriften, keine
  Tabellen und keine sonstige Markdown-Syntax, Fettdruck sparsam;
- SCHNELLANTWORTEN: die Zeile ist immer die allerletzte der Nachricht, danach folgen keine
  Quellenangaben, keine „Sources"-Liste, keine Links und kein Nachsatz;
- WEBSEARCH: keine Quellen-, „Sources:"- oder Linkliste, auch wenn das Suchwerkzeug dies anregt; die
  Kennzeichnung als Recherche im Fließtext bleibt.

**Warum so.** Die Auszeichnung soll dargestellt statt roh angezeigt werden, ohne dass vom LLM
gelieferte Tags ausgeführt werden. Die Quellenliste wird nach Entscheidung des Product
Owners nur über die Prompt-Anweisung unterbunden, ohne Änderung am Parser.

**Verworfene Alternativen.**

- Externe Markdown-Bibliothek: unverhältnismäßiger Umfang für zwei Auszeichnungen und zusätzliche
  XSS-Angriffsfläche.
- Serverseitige Umwandlung in HTML.
- Vollständiger Markdown-Parser.
- Quellenliste per Code herausfiltern: bewusst nicht umgesetzt, Entscheidung für eine reine
  Prompt-Anweisung.
- Schnellantwort-Chips ausblenden: beruhte auf einem Missverständnis des Feedbacks.

## Verifikation

- `tests/test_regelwerk.py` (neu, 3 Tests): Formatierungsregel, Schnellantworten-Zeile als letzte
  Zeile, Verbot der Quellenliste bei erhaltener Kennzeichnungspflicht.
- `tests/test_bot_text_formatierung.py` (neu, 9 Tests): führt den JavaScript-Block per Node.js aus
  und prüft Fettdruck, Aufzählungen, Zeilenumbrüche, HTML als reinen Text, `javascript:`-Links,
  http-Links, Ausbruch aus dem `href`-Attribut, einzelne Sternchen und den Vorlesetext; ohne Node.js
  wird der Test übersprungen.
- `tests/test_kanal.py`: Erweiterungen zu `entferne_markdown`, `TextKanal` und `AudioKanal`.
- `tests/conftest.py`: Übersicht der Testdateien ergänzt.
- Komplette Suite grün (355/355).

Nicht geprüft: die Darstellung im echten Browser (Listenabstände, Linkfarbe, Öffnen im neuen Tab) und
die Wirkung der Prompt-Regel im Live-Gespräch mit Websuche.

## Offene Punkte

- Das Websuch-Werkzeug regt selbst eine Quellenliste an. Ob die Prompt-Regel wirkt, zeigt erst der
  nächste Live-Test. Folgt trotzdem eine Liste nach der Schnellantworten-Zeile, bleibt diese roh
  sichtbar; eine deterministische Kürzung wäre eine eigene, neue Entscheidung.
- Browser-Darstellung (Listenabstände, Linkfarbe, neuer Tab) nicht manuell geprüft.
- Der JavaScript-Test nutzt eine DOM-freie `escapeHtml`-Variante gleicher Wirkung; der DOM-Weg im
  Browser ist nur indirekt abgedeckt.
