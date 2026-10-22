# Station 33 — Chatverlauf ohne horizontales Scrollen

**Zeitraum:** 21.09.2026 (ENTSCHEIDUNGSLOG.md Phase 61)
**Kein Code-Duplikat.**

## Auslöser

Im Chatverlauf erschien trotz umbrochenem Text ein horizontaler Scrollbalken. Anforderung: der Chat
passt in der Breite immer; vertikales Scrollen ist in Ordnung.

## Ursachen

1. **Hauptursache:** `#verlauf` setzte nur `overflow-y: auto`. Laut CSS-Spezifikation wird eine auf
   „visible" stehende Achse auf „auto" hochgestuft, sobald die andere Achse einen anderen Wert hat;
   `overflow-x` war dadurch effektiv „auto".
2. `.nachricht` fehlte `overflow-wrap`; ein langes Wort oder ein langer Link hätte die Blase verbreitert.
3. `.hotel-karte-wrapper` hatte eine feste Breite von 220 px, die im schmalen Abschluss-Chat nicht immer
   passte.

## Umsetzung

- `#verlauf`: `overflow-x: hidden`.
- `.nachricht`: `overflow-wrap: break-word; word-break: break-word;`.
- `.nachricht-zeile`: `min-width: 0` als zusätzliche Absicherung für Flex-Elemente.
- `.hotel-karte-wrapper`: `width: 100%` mit `max-width: 220px`.

## Verifikation

Eine Testseite mit dem Original-CSS, einem extrem langen Wort und einem langen Link im schmalen
Abschluss-Layout wurde im Headless-Browser gerendert: nur noch vertikales Scrollen. Python-Suite
unverändert 335/335 grün. Nicht mit echten, langen LLM-Antworten geprüft.
