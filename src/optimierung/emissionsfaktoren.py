"""
Feste CO2-Emissionsfaktoren je Verkehrsmittel (siehe ARCHITEKTUR.md,
Abschnitt 5). Die hinterlegten Werte sind gängige Faustwerte und nicht gegen
eine amtliche Quelle (z.B. Umweltbundesamt) verifiziert; der Product Owner
hat entschieden, sie beizubehalten (ENTSCHEIDUNGSLOG.md, Offene Punkte). Climatiq wurde bewusst NICHT angebunden (Projektentscheidung:
feste, zitierfähige Tabelle statt Live-API für die CO2-Faktoren).
Zusätzlich enthält das Modul die Einordnung der CO2-Menge von Hin- und Rückreise in drei Stufen
(genügsam/mittel/CO₂-lastig) mit vorläufigen Schwellen (siehe `co2_einstufung`).
"""
from __future__ import annotations

from dataclasses import dataclass

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


# -- Einordnung der CO2-Menge von Hin- und Rückreise ("CO2-Ampel", Demo-Feedback, Station 42) --
# Die reine Kilogramm-Angabe lässt offen, ob die An- und Abreise viel oder wenig CO2 verursacht.
# Die Einordnung in drei Stufen geschieht deterministisch hier im regelbasierten Layer
# (Grundprinzip 3), nicht im LLM und nicht erst in der Web-UI, damit Web-UI, Text- und Mail-Ausgabe
# dieselbe Stufe zeigen.
#
# PLATZHALTER: Beide Schwellen sind eine eigene, vorläufige Setzung des Product Owners und KEIN
# Literaturbeleg. Die gesichtete Literatur stützt nur die Berechnung (Distanz × Faktor je Pkm,
# Ruiz-Meza & Montoya-Torres 2021) und die qualitative Reihenfolge Bahn/Bus < Auto/Flug (Klarin et
# al. 2023), nicht konkrete Grenzwerte. Die Schwellen gelten absolut für die Summe aus Hin- und
# Rückreise (`co2_an_abreise_kg`); Wege vor Ort sind nicht enthalten. Wie die Emissionsfaktoren
# oben vor einer Verwendung über den Prototyp hinaus an einer belastbaren Quelle zu prüfen.
CO2_GRENZE_GENUEGSAM_KG = 50.0  # bis einschließlich dieses Werts: "genügsam"
CO2_GRENZE_MITTEL_KG = 150.0  # über "genügsam" bis einschließlich dieses Werts: "mittel", darüber "CO₂-lastig"


@dataclass(frozen=True)
class CO2Einstufung:
    """Ergebnis der Einordnung: technischer Schlüssel (für die Farbe in der Web-UI), sichtbare
    Bezeichnung und Erläuterung der Schwellen. Die Farbe ist nie alleiniger Bedeutungsträger, die
    Bezeichnung steht immer als Text daneben."""

    stufe: str  # "genuegsam" | "mittel" | "co2_lastig"
    bezeichnung: str  # "genügsam" | "mittel" | "CO₂-lastig"
    hinweis: str


def _kg_text(wert: float) -> str:
    """Schwellenwert im deutschen Zahlenformat ohne überflüssige Nachkommastellen (50 -> "50")."""
    return f"{wert:g}".replace(".", ",")


# Erläuterung für Tooltip (Web-UI) und Text-/Mail-Ausgabe. Aus den Konstanten erzeugt, damit die
# Schwellen nur an einer Stelle stehen. Nennt ausdrücklich die Einschränkungen (nur An- und
# Abreise, grobe Schätzung, vorläufige Schwellen).
CO2_EINSTUFUNG_HINWEIS = (
    "Grobe Schätzung, nur An- und Abreise. Vorläufige Schwellen: "
    f"genügsam bis {_kg_text(CO2_GRENZE_GENUEGSAM_KG)} kg, "
    f"mittel über {_kg_text(CO2_GRENZE_GENUEGSAM_KG)} bis {_kg_text(CO2_GRENZE_MITTEL_KG)} kg, "
    f"CO₂-lastig über {_kg_text(CO2_GRENZE_MITTEL_KG)} kg."
)


def co2_einstufung(co2_an_abreise_kg: float | None) -> CO2Einstufung | None:
    """
    Ordnet die CO2-Menge von Hin- und Rückreise zusammen einer von drei Stufen zu. Die Grenzwerte
    selbst gehören zur niedrigeren Stufe (50 kg ist "genügsam", 150 kg "mittel"). Ohne Wert gibt es
    keine Einstufung (None), statt eine Stufe zu raten (Grundprinzip 1).
    """
    if co2_an_abreise_kg is None:
        return None
    if co2_an_abreise_kg <= CO2_GRENZE_GENUEGSAM_KG:
        return CO2Einstufung("genuegsam", "genügsam", CO2_EINSTUFUNG_HINWEIS)
    if co2_an_abreise_kg <= CO2_GRENZE_MITTEL_KG:
        return CO2Einstufung("mittel", "mittel", CO2_EINSTUFUNG_HINWEIS)
    return CO2Einstufung("co2_lastig", "CO₂-lastig", CO2_EINSTUFUNG_HINWEIS)
