"""
Feste CO2-Emissionsfaktoren je Verkehrsmittel (siehe ARCHITEKTUR.md,
Abschnitt 5). Die hinterlegten Werte sind gängige Faustwerte und nicht gegen
eine amtliche Quelle (z.B. Umweltbundesamt) verifiziert; der Product Owner
hat entschieden, sie beizubehalten (ENTSCHEIDUNGSLOG.md, Offene Punkte). Climatiq wurde bewusst NICHT angebunden (Projektentscheidung:
feste, zitierfähige Tabelle statt Live-API für die CO2-Faktoren).
"""
from __future__ import annotations

# Gramm CO2-Äquivalent pro Personenkilometer (Pkm).
EMISSIONSFAKTOREN_G_PRO_PKM: dict[str, float] = {
    "bahn": 19.0,  # Faustwert Bahn-Fernverkehr (~19 g/Pkm), nicht amtlich verifiziert
    "auto": 168.0,  # Faustwert (durchschnittlicher PKW, 1 Person), nicht amtlich verifiziert
    "fernbus": 32.0,  # Faustwert, nicht amtlich verifiziert
}


def co2_kg(verkehrsmittel: str, distanz_km: float) -> float:
    """Berechnet die CO2-Emission einer Strecke: Distanz × Emissionsfaktor."""
    faktor = EMISSIONSFAKTOREN_G_PRO_PKM.get(verkehrsmittel.lower())
    if faktor is None:
        raise ValueError(f"Kein Emissionsfaktor für Verkehrsmittel '{verkehrsmittel}' hinterlegt.")
    return distanz_km * faktor / 1000  # g -> kg
