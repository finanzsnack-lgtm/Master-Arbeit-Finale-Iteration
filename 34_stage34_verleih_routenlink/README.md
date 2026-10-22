# Station 34 — Verleihkarte mit Route ab der Unterkunft

**Zeitraum:** 21.09.2026 (ENTSCHEIDUNGSLOG.md Phase 62)
**Kein Code-Duplikat.**

## Auslöser

Wunsch des Product Owners: die Verleihkarte aus Station 30 behält ihren Google-Maps-Link und erhält
zusätzlich wie die Tageskarten einen Link „Route ansehen", immer von der Unterkunft zum Verleih.

## Umsetzung

`als_kartendaten` berechnet für die Verleihkarte einen `routen_link` über die bestehende Funktion
`routen_link()`, mit den Unterkunftskoordinaten als Ursprung, den Verleihkoordinaten als Ziel und
`travelmode="walking"`, weil der Verleih nah an der Unterkunft liegen soll. Ohne
Unterkunftskoordinaten ist der Link `None`, statt einen Startpunkt zu raten. Die Oberfläche brauchte
keine Änderung, weil `karteHtml()` das Feld für jede Kartenart rendert.

## Verifikation

Neuer Test `test_als_kartendaten_verleih_karte_zeigt_route_ab_unterkunft` und eine ergänzte Prüfung im
bestehenden Verleih-Test. Suite 336/336 grün. Nicht im Browser geprüft.
