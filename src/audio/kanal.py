"""
Ein-/Ausgabe-Abstraktion für chat.py: Text (Tastatur/Konsole, Standard),
gesprochene Sprache (Mikrofon/Lautsprecher, wenn AUDIO_MODUS=true) oder ein
Browser-Chat über WebSocket (webapp.py, siehe WebIOKanal dort). Der Rest der
Dialogsteuerung (Fragekatalog, Gateways, LLM-Interpretation) muss den
Unterschied nicht kennen – chat.py ruft ausschließlich `bot_sagt`/
`nutzer_antwortet` auf, unabhängig vom aktiven Kanal.

Für den Sprachkanal gibt es zwei Anbieter (siehe config.py: AUDIO_ANBIETER):
"google_cloud" (Google Cloud Speech-APIs, natürlicher, braucht API-Key,
siehe google_speech.py) oder "lokal" (Whisper + pyttsx3, kein Key nötig,
aber schlechtere Qualität – siehe spracheingabe.py/sprachausgabe.py).

`IOKanal` ist bewusst ASYNC (`async def`), obwohl Text-/Audio-Ein-/Ausgabe
selbst rein synchron/blockierend sind (Konsolen-`input()`, Mikrofonaufnahme):
der Browser-Chat (WebIOKanal, webapp.py) muss auf eine WebSocket-Nachricht
warten können, ohne die laufende Event-Loop zu blockieren – das geht nur mit
einem echten `await`. TextKanal/AudioKanal bleiben innerhalb ihrer async-
Methoden weiterhin synchron blockierend (unproblematisch: chat.py läuft als
einzelner Konsolen-Prozess ohne Nebenläufigkeit, die dabei verpasst würde).
"""
from __future__ import annotations

import re
from typing import Protocol

from src.api.typen import Unterkunft

# Iteration 2 (Demo-Feedback: Quick Replies im Chat, siehe
# doku/28_stage28_iteration2_ux_feedback_konzepte/README.md): das LLM selbst entscheidet, ob und
# welche Kurzantworten es einer Nachricht anbietet (Grundprinzip 1 – KEIN fest verdrahteter
# Fragenkatalog-Trigger, siehe regelwerk.py "SCHNELLANTWORTEN"). Es hängt dafür optional GENAU EINE
# letzte Zeile im Format "[SCHNELLANTWORTEN: Option 1 | Option 2]" an seine Nachricht an. Dieses
# Modul parst/entfernt diese Zeile zentral, damit kein Kanal (Konsole, Browser) sie ungefiltert als
# rohen Text zeigt – nur `WebIOKanal` (webapp.py) nutzt die extrahierten Optionen tatsächlich für
# klickbare Chips, TextKanal/AudioKanal verwerfen sie einfach.
_SCHNELLANTWORTEN_MUSTER = re.compile(r"\n?\[SCHNELLANTWORTEN:\s*(.+?)\]\s*$", re.IGNORECASE)
_MAX_SCHNELLANTWORTEN = 4


def zerlege_schnellantworten(text: str) -> tuple[str, list[str] | None]:
    """Trennt eine optionale, vom LLM angehängte Schnellantworten-Zeile vom eigentlichen
    Nachrichtentext. Gibt `(bereinigter_text, optionen)` zurück, `optionen` ist `None`, wenn keine
    solche Zeile gefunden wurde (der Normalfall – die meisten Fragen bekommen keine Chips)."""
    treffer = _SCHNELLANTWORTEN_MUSTER.search(text)
    if not treffer:
        return text, None
    bereinigt = text[: treffer.start()].rstrip()
    optionen = [teil.strip() for teil in treffer.group(1).split("|") if teil.strip()]
    if not optionen:
        return bereinigt, None
    return bereinigt, optionen[:_MAX_SCHNELLANTWORTEN]


# Iteration 2 (Demo-Feedback: Formatierung im Bot-Text): das LLM darf laut Regelwerk
# (regelwerk.py, Absatz "FORMATIERUNG") genau zwei einfache Auszeichnungen verwenden, **fett** und
# "- "-Aufzählungen. Der Browser stellt sie dar (static/index.html, formatiereBotText); Konsole und
# Sprachausgabe können das nicht und sollen die Sternchen weder drucken noch vorlesen. Das Muster
# verlangt Nicht-Leerzeichen direkt innerhalb der Sternchen und bleibt innerhalb einer Zeile, damit
# einzelne "*" oder ein ungeschlossenes "**" unverändert als Text stehen bleiben.
_FETT_MUSTER = re.compile(r"\*\*(?=\S)([^\n]*?\S)\*\*")
# Markdown-Links nur mit http/https-Adresse (dieselbe Einschränkung wie im Browser-Renderer).
_LINK_MUSTER = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)", re.IGNORECASE)


def entferne_markdown(text: str, links_mit_adresse: bool = False) -> str:
    """Entfernt die vom Regelwerk erlaubten Auszeichnungen aus einem Bot-Text für Kanäle ohne
    Formatierung. `**x**` wird zu `x`; ein Link `[Text](URL)` wird zu `Text` (Sprachausgabe: eine
    vorgelesene Adresse wäre unverständlich) bzw. zu `Text (URL)`, wenn `links_mit_adresse` gesetzt
    ist (Konsole: dort bleibt die Adresse nutzbar). "- "-Aufzählungszeilen bleiben unverändert, da
    sie als reiner Text lesbar sind."""
    ersatz = r"\1 (\2)" if links_mit_adresse else r"\1"
    ohne_links = _LINK_MUSTER.sub(ersatz, text)
    return _FETT_MUSTER.sub(r"\1", ohne_links)


class _SprachausgabeProtokoll(Protocol):
    def sage(self, text: str) -> None: ...


class _SpracheingabeProtokoll(Protocol):
    def hoere_zu(self) -> str: ...


class IOKanal(Protocol):
    async def bot_sagt(self, text: str) -> None: ...
    async def nutzer_antwortet(self) -> str: ...
    async def zeige_karte(self, unterkunft: Unterkunft) -> None: ...
    async def zeige_status(self, phase: str) -> None: ...


class TextKanal:
    """Standard-Kanal: Konsolen-Ein-/Ausgabe."""

    async def bot_sagt(self, text: str) -> None:
        bereinigt, _optionen = zerlege_schnellantworten(text)
        # Optionen werden hier bewusst verworfen (kein Klick-UI in der Konsole) – wären sie sichtbar
        # geblieben, stünde die rohe "[SCHNELLANTWORTEN: ...]"-Zeile im Chat.
        # Erst danach die Auszeichnungen entfernen, damit der Schnellantworten-Parser unverändert
        # auf dem Originaltext arbeitet.
        print(f"Bot: {entferne_markdown(bereinigt, links_mit_adresse=True)}")

    async def nutzer_antwortet(self) -> str:
        return input("Du:  ").strip()

    async def zeige_karte(self, unterkunft: Unterkunft) -> None:
        # Kein Bildschirm für Fotos in der Konsole – Name/Preisniveau nennt das LLM ohnehin schon
        # im gesprochenen/gedruckten Vorschlagstext, siehe vorschlaege.py::suche_unterkunft.
        pass

    async def zeige_status(self, phase: str) -> None:
        # Iteration 2: eigener, deutlicherer Hinweis für den einen bekannten Sonderfall (finale
        # Reiseplanung kann bei "mittel"/"stark" Barrierefreiheit spürbar dauern, siehe
        # ENTSCHEIDUNGSLOG.md Phase 44) – in der Konsole reicht
        # dafür eine einfache Zeile, kein Ladebalken nötig.
        if phase == "plant_reise":
            print("Bot: (Reiseroute wird berechnet – kann bei vielen Kandidaten etwas dauern ...)")


class AudioKanal:
    """
    Sprachkanal: Bot-Text wird vorgelesen (Sprachausgabe), Nutzerantwort wird
    per Mikrofon aufgenommen und transkribiert (Spracheingabe) – unabhängig
    davon, ob lokal (Whisper/pyttsx3) oder über Google Cloud (siehe
    google_speech.py). Gibt zusätzlich alles als Text auf der Konsole aus –
    als Transkript für Protokoll (src/protokoll.py), Barrierefreiheit und
    Debugging.
    """

    def __init__(self, spracheingabe: _SpracheingabeProtokoll, sprachausgabe: _SprachausgabeProtokoll):
        self._spracheingabe = spracheingabe
        self._sprachausgabe = sprachausgabe

    async def bot_sagt(self, text: str) -> None:
        # Schnellantworten-Zeile auch hier entfernen – sonst würde die Sprachausgabe die rohe
        # "[SCHNELLANTWORTEN: ...]"-Syntax laut vorlesen (siehe zerlege_schnellantworten oben).
        bereinigt, _optionen = zerlege_schnellantworten(text)
        # Transkript und Sprachausgabe ohne Sternchen; die Sprachausgabe nennt bei Links nur den
        # Linktext, das Konsolen-Transkript behält die Adresse (siehe entferne_markdown).
        print(f"Bot: {entferne_markdown(bereinigt, links_mit_adresse=True)}")
        self._sprachausgabe.sage(entferne_markdown(bereinigt))

    async def nutzer_antwortet(self) -> str:
        print("Du:  (jetzt sprechen ...)")
        text = self._spracheingabe.hoere_zu()
        print(f"Du:  {text}")
        return text

    async def zeige_karte(self, unterkunft: Unterkunft) -> None:
        pass  # siehe TextKanal.zeige_karte

    async def zeige_status(self, phase: str) -> None:
        if phase == "plant_reise":
            hinweis = "Reiseroute wird berechnet – kann bei vielen Kandidaten etwas dauern ..."
            print(f"Bot: ({hinweis})")
            self._sprachausgabe.sage(hinweis)


def erzeuge_kanal(
    audio_modus: bool,
    audio_anbieter: str = "google_cloud",
    whisper_modellgroesse: str = "base",
    google_cloud_speech_api_key: str | None = None,
) -> IOKanal:
    """
    Wählt anhand der Konfiguration den Text- oder den Audio-Kanal (und bei
    Audio: welchen Anbieter). Die Audio-Abhängigkeiten (siehe
    requirements-audio.txt) werden bewusst erst HIER importiert, nicht auf
    Modulebene – wer AUDIO_MODUS=false lässt (Standard), braucht sie gar
    nicht installiert zu haben.
    """
    if not audio_modus:
        return TextKanal()

    if audio_anbieter == "google_cloud":
        from src.audio.google_speech import GoogleSpracheingabe, GoogleSprachausgabe

        if not google_cloud_speech_api_key:
            raise ValueError(
                "AUDIO_ANBIETER=google_cloud, aber kein API-Key gefunden "
                "(GOOGLE_CLOUD_SPEECH_API_KEY oder GOOGLE_MAPS_API_KEY in .env). "
                "Alternativ AUDIO_ANBIETER=lokal setzen (kein Key nötig, siehe .env.example)."
            )
        return AudioKanal(
            GoogleSpracheingabe(google_cloud_speech_api_key), GoogleSprachausgabe(google_cloud_speech_api_key)
        )

    from src.audio.spracheingabe import Spracheingabe
    from src.audio.sprachausgabe import Sprachausgabe

    return AudioKanal(Spracheingabe(modellgroesse=whisper_modellgroesse), Sprachausgabe())
