"""
Deterministische Lageprüfung für Unterkunftskandidaten (finales Demo-Feedback, Station 42).

Auslöser: Bei einem Tester-Gespräch mit dem Ziel "Venedig" schlug der Bot eine Unterkunft in
Südtirol vor, rund 136 km entfernt. Ursache ist die Google Places Nearby Search: Mit einem
Freitext-`keyword` (der Antwort auf F15) ist der Parameter `radius` nur eine Bevorzugung, kein
harter Ausschluss, sodass ein gut zum Freitext passender, aber weit entfernter Treffer an erster
Stelle stehen kann. Eine falsch gelegene Unterkunft wirkt sich auf die gesamte Planung aus:
Optimierung 1 nutzt sie als Depot, An- und Abreise sowie CO₂-Bilanz werden zu ihr berechnet.

Ob ein Treffer am Reiseziel liegt, lässt sich objektiv berechnen und bleibt deshalb im
regelbasierten Layer (Grundprinzip 3), statt dem LLM die Beurteilung zu überlassen. Maßstab ist
das von Google gelieferte Gebiet des Ziels (`ZielGebiet`, siehe src/api/typen.py): Ein fester
Kilometerwert würde Städte und Regionen gleich behandeln, obwohl ein Ziel wie "Costa del Sol"
deutlich größer ist als eine Kleinstadt.
"""
from __future__ import annotations

import math

from src.api.typen import Unterkunft, ZielGebiet

# Mittlerer Erdradius für die Haversine-Formel.
_ERDRADIUS_KM = 6371.0

# Näherung für die Umrechnung Breitengrad -> Kilometer (ein Breitengrad entspricht überall rund 111 km).
_KM_JE_BREITENGRAD = 111.0

# Puffer um das Gebiet des Ziels: Ein Viewport umfasst in der Regel das Stadtgebiet bzw. die
# Region selbst. Unterkünfte am Stadtrand oder in einem direkt angrenzenden Vorort sollen nicht
# wegfallen, eine Unterkunft in einer anderen Region (im Befund rund 136 km entfernt) dagegen
# schon. 5 km decken einen unmittelbar angrenzenden Ortsteil ab, ohne das Gebiet nennenswert
# aufzublähen.
LAGE_PUFFER_KM = 5.0

# Mindestradius um den Mittelpunkt: Für kleine Orte liefert Google teils einen Viewport von nur
# wenigen Kilometern Kantenlänge. Dort liegen passende Unterkünfte häufig im Nachbarort. Jeder
# Treffer innerhalb dieses Radius gilt daher unabhängig von der Viewport-Größe als "am Ziel".
# 10 km entsprechen etwa der Entfernung zum nächsten Nachbarort und sind mit Bus, Fahrrad oder
# Auto in kurzer Zeit erreichbar.
LAGE_MINDESTRADIUS_KM = 10.0

# Rückfallschwelle ohne Viewport: Fehlt das Gebiet in der Geocoding-Antwort, ist unbekannt, ob das
# Ziel eine Stadt oder eine Region ist. 30 km lassen eine Stadt mitsamt Umland zu und schließen
# dennoch Treffer in einer anderen Region aus (der Befund lag bei rund 136 km).
LAGE_FALLBACK_RADIUS_KM = 30.0


def luftlinie_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """
    Großkreisentfernung zwischen zwei Punkten (Breite, Länge) in Kilometern (Haversine-Formel).
    Genauer als die an anderen Stellen genutzte Näherung "Gradabstand x 111", weil die
    Entfernung hier dem Nutzer genannt wird und Längengrade in Mitteleuropa deutlich kürzer als
    111 km sind.
    """
    breite_a, laenge_a = map(math.radians, a)
    breite_b, laenge_b = map(math.radians, b)
    h = (
        math.sin((breite_b - breite_a) / 2) ** 2
        + math.cos(breite_a) * math.cos(breite_b) * math.sin((laenge_b - laenge_a) / 2) ** 2
    )
    return 2 * _ERDRADIUS_KM * math.asin(math.sqrt(h))


def liegt_im_zielgebiet(punkt: tuple[float, float], gebiet: ZielGebiet) -> bool:
    """
    True, wenn `punkt` (Breite, Länge) am Reiseziel liegt, d. h. innerhalb des Mindestradius um den
    Mittelpunkt ODER innerhalb des um den Puffer erweiterten Viewports. Ohne Viewport gilt
    ausschließlich die Rückfallschwelle um den Mittelpunkt.

    Vereinfachung: Ein Viewport, der den 180. Längengrad überschreitet, wird nicht gesondert
    behandelt. Für den Prototyp ist das unerheblich, da Ziele ohne Flug erreichbar sein müssen
    (Grundprinzip 5) und in Europa kein Ziel diese Linie berührt.
    """
    entfernung_km = luftlinie_km(punkt, gebiet.punkt)
    if gebiet.suedwest is None or gebiet.nordost is None:
        return entfernung_km <= LAGE_FALLBACK_RADIUS_KM
    if entfernung_km <= LAGE_MINDESTRADIUS_KM:
        return True

    # Puffer in Grad umrechnen: in Nord-Süd-Richtung konstant, in Ost-West-Richtung abhängig von
    # der geographischen Breite (Längengrade rücken zu den Polen hin zusammen).
    puffer_breite = LAGE_PUFFER_KM / _KM_JE_BREITENGRAD
    puffer_laenge = LAGE_PUFFER_KM / (_KM_JE_BREITENGRAD * max(math.cos(math.radians(gebiet.x)), 0.01))
    breite, laenge = punkt
    return (
        gebiet.suedwest[0] - puffer_breite <= breite <= gebiet.nordost[0] + puffer_breite
        and gebiet.suedwest[1] - puffer_laenge <= laenge <= gebiet.nordost[1] + puffer_laenge
    )


def filtere_unterkuenfte_nach_lage(
    unterkuenfte: list[Unterkunft], gebiet: ZielGebiet
) -> tuple[list[Unterkunft], list[Unterkunft]]:
    """
    Teilt die Kandidaten in (am Ziel, verworfen) auf. Die Reihenfolge der behaltenen Treffer bleibt
    erhalten, weil sie Googles Relevanz zur genannten Unterkunftsanforderung widerspiegelt; der
    Filter entfernt nur, er sortiert nicht nach Nähe um.
    """
    behalten: list[Unterkunft] = []
    verworfen: list[Unterkunft] = []
    for unterkunft in unterkuenfte:
        (behalten if liegt_im_zielgebiet((unterkunft.x, unterkunft.y), gebiet) else verworfen).append(unterkunft)
    return behalten, verworfen
