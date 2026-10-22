"""
Optimierung 2 – An-/Abreise (nachhaltige Verkehrsmittelwahl).

Kleiner Alternativenraum -> gewichtete Bewertung aller Alternativen über
Zeit, Kosten und CO2 (siehe ARCHITEKTUR.md, Abschnitt 5). Enthält
außerdem den Nachhaltigkeits-Nudge für den F13-Dialog ("Die Bahn braucht nur
Δt länger, spart aber X kg CO2 ...").
"""
from __future__ import annotations

from dataclasses import dataclass

from src.api.typen import ReiseAlternative
from src.optimierung.emissionsfaktoren import co2_kg


@dataclass(frozen=True)
class Gewichtung:
    zeit: float = 1 / 3
    kosten: float = 1 / 3
    co2: float = 1 / 3

    def __post_init__(self):
        gesamt = self.zeit + self.kosten + self.co2
        if not (0.99 <= gesamt <= 1.01):
            raise ValueError("Die drei Gewichte müssen in Summe 1 ergeben.")


@dataclass
class BewerteteAlternative:
    alternative: ReiseAlternative
    co2_kg: float
    score: float  # niedriger = besser (normalisierte, gewichtete Summe)


def _normalisieren(werte: list[float]) -> list[float]:
    """Min-Max-Normalisierung auf [0, 1]; bei identischen Werten -> 0 für alle."""
    minimum, maximum = min(werte), max(werte)
    spanne = maximum - minimum
    if spanne == 0:
        return [0.0 for _ in werte]
    return [(wert - minimum) / spanne for wert in werte]


def bewerte_alternativen(
    alternativen: list[ReiseAlternative],
    gewichtung: Gewichtung = Gewichtung(),
) -> list[BewerteteAlternative]:
    """Bewertet alle Alternativen gewichtet nach Zeit/Kosten/CO2; sortiert aufsteigend (beste zuerst)."""
    if not alternativen:
        return []

    co2_werte = [co2_kg(a.verkehrsmittel, a.distanz_km) for a in alternativen]
    zeit_norm = _normalisieren([a.dauer_minuten for a in alternativen])
    kosten_norm = _normalisieren([a.kosten_euro for a in alternativen])
    co2_norm = _normalisieren(co2_werte)

    bewertete = [
        BewerteteAlternative(
            alternative=alt,
            co2_kg=co2_wert,
            score=gewichtung.zeit * z + gewichtung.kosten * k + gewichtung.co2 * c,
        )
        for alt, co2_wert, z, k, c in zip(alternativen, co2_werte, zeit_norm, kosten_norm, co2_norm)
    ]
    return sorted(bewertete, key=lambda bewertung: bewertung.score)


def nur_bestaetigte_verkehrsmittel(
    bewertete: list[BewerteteAlternative], verkehrsmittel_praeferenz: list[str]
) -> list[BewerteteAlternative]:
    """
    Schränkt die bewerteten Alternativen auf die ein, die der Nutzer im Dialog (F13,
    verkehrsmittel_praeferenz) tatsächlich bestätigt hat – `bewerte_alternativen` würde sonst eine
    bereits bestätigte, konkrete Entscheidung überstimmen (CO2-Gewichtung begünstigt strukturell die
    Bahn). Genutzt für die An-/Abreise (pipeline.py) und für die Anfahrt zu weit entfernten festen
    Wunschorten (fragekatalog/wunschorte.py).

    Ohne erkennbare Übereinstimmung (z.B. wenn `verkehrsmittel_praeferenz` unklarer Freitext ist,
    der keinen der echten Alternativen-Namen enthält) bleibt die volle Liste als Fallback erhalten,
    statt mit einer leeren Auswahl abzustürzen oder eine Wahl zu erfinden.
    """
    praeferenz_text = " ".join(verkehrsmittel_praeferenz).lower()
    passende = [b for b in bewertete if b.alternative.verkehrsmittel.lower() in praeferenz_text]
    return passende or bewertete


def nachhaltigkeits_nudge(alternativen: list[BewerteteAlternative]) -> str | None:
    """
    Erzeugt die Nudge-Botschaft (ARCHITEKTUR.md, Abschnitt 5): "Die Bahn braucht nur Δt länger,
    spart aber X kg CO2 ...". Vergleicht die Bahn-Option mit der insgesamt bestbewerteten
    Alternative (niedrigster gewichteter Score aus Zeit, Kosten und CO2), sofern diese nicht bereits
    die Bahn ist und die Bahn tatsächlich weniger CO2 verursacht.

    Die bestbewertete Alternative ist nicht zwingend die schnellste: ist die Bahn gleich schnell
    oder schneller (und liegt nur wegen höherer Kosten hinten), wäre "braucht nur Δt länger" mit
    Δt ≤ 0 widersprüchlich. Für diese Fälle gibt es eigene Formulierungen. Die Vergleichsgröße wird
    im Text mit ihrem Verkehrsmittel benannt, damit der Bezug eindeutig ist.
    """
    if len(alternativen) < 2:
        return None

    beste = alternativen[0]
    bahn = next((b for b in alternativen if b.alternative.verkehrsmittel.lower() == "bahn"), None)
    if bahn is None or bahn is beste:
        return None

    delta_minuten = bahn.alternative.dauer_minuten - beste.alternative.dauer_minuten
    ersparnis_kg = beste.co2_kg - bahn.co2_kg
    if ersparnis_kg <= 0:
        return None

    if delta_minuten > 0:
        zeitvergleich = f"Die Bahn braucht nur {delta_minuten} Minuten länger, spart aber"
    elif delta_minuten == 0:
        zeitvergleich = "Die Bahn ist gleich schnell und spart"
    else:
        zeitvergleich = f"Die Bahn ist sogar {-delta_minuten} Minuten schneller und spart"
    return (
        f"{zeitvergleich} {ersparnis_kg:.1f} kg CO2 gegenüber der bestbewerteten Alternative "
        f"({beste.alternative.verkehrsmittel})."
    )
