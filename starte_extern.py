"""
Gibt die Web-Oberfläche des Reisebots für Tester in anderen Netzwerken frei.

Ablauf: Zugangstoken bestimmen, Webapp lokal starten (Uvicorn, 127.0.0.1:8000, wie im
Normalbetrieb), einen Cloudflare Quick Tunnel dorthin öffnen, die öffentliche
trycloudflare.com-Adresse aus der Ausgabe von cloudflared auslesen und den fertigen Link
`https://….trycloudflare.com/?zugang=TOKEN` ausgeben. Tester öffnen nur diesen Link im Browser; es
ist weder eine Installation noch eine Passworteingabe nötig. Der Server läuft weiterhin
ausschließlich auf dem lokalen Rechner, der Tunnel leitet die Anfragen lediglich weiter.

Warum Cloudflare Quick Tunnel: kostenlos, kein Konto nötig, liefert HTTPS (Voraussetzung dafür,
dass Browser Mikrofon und Web Speech API freigeben) und unterstützt WebSockets. Der Router muss
nicht geöffnet werden, weil cloudflared die Verbindung von innen nach außen aufbaut.

Warum ein Zugangstoken: Jede Sitzung startet einen LLM-Dialog und echte API-Anfragen. Ohne Token
könnte jeder, der die öffentliche Adresse kennt, Kosten verursachen. Ist in der `.env` kein
`ZUGANGSTOKEN` eingetragen, wird pro Start ein zufälliges Token erzeugt, das nur für diesen Lauf
gilt (Weitergabe an die Webapp per Umgebungsvariable). Die Prüfung selbst erfolgt in webapp.py.

Aufruf: Doppelklick auf `starte_extern.bat` oder `python starte_extern.py`. Strg+C beendet Tunnel
und Webapp.
"""
from __future__ import annotations

import os
import queue
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

HOST = "127.0.0.1"
PORT = 8000
# Muss mit webapp.ZUGANG_PARAMETER übereinstimmen (per Test abgesichert). Bewusst nicht von dort
# importiert: webapp.py lädt beim Import den kompletten Dialog-Stack, der hier nicht gebraucht wird.
ZUGANG_PARAMETER = "zugang"

_PROJEKT_VERZEICHNIS = Path(__file__).resolve().parent

# Öffentliche Adresse eines Quick Tunnels, z. B. https://fancy-words-here.trycloudflare.com.
# "api.trycloudflare.com" ist der Dienst, bei dem cloudflared den Tunnel anfordert, nicht die
# Adresse für Tester, und wird deshalb ausgeschlossen.
_TUNNEL_URL_MUSTER = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)

# Übliche Installationsorte, falls cloudflared nach `winget install` zwar installiert ist, die
# PATH-Änderung im laufenden Fenster aber noch nicht wirkt.
_CLOUDFLARED_KANDIDATEN = [
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "cloudflared" / "cloudflared.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "cloudflared" / "cloudflared.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "cloudflared.exe",
]

_ANLEITUNG_CLOUDFLARED = """
cloudflared wurde nicht gefunden. Einmalige Installation (PowerShell oder Eingabeaufforderung):

    winget install Cloudflare.cloudflared

Danach dieses Fenster schließen und starte_extern.bat erneut per Doppelklick starten.
"""


def finde_cloudflared() -> str | None:
    """Pfad zu cloudflared oder None, wenn es weder im PATH noch an einem üblichen Ort liegt."""
    gefunden = shutil.which("cloudflared")
    if gefunden:
        return gefunden
    for kandidat in _CLOUDFLARED_KANDIDATEN:
        if kandidat.is_file():
            return str(kandidat)
    return None


def bestimme_token(konfiguriertes_token: str | None) -> tuple[str, bool]:
    """Liefert (Token, stammt_aus_konfiguration). Ohne Eintrag in der .env wird ein zufälliges,
    URL-taugliches Token mit 24 Byte Zufall erzeugt (secrets.token_urlsafe)."""
    if konfiguriertes_token:
        return konfiguriertes_token, True
    return secrets.token_urlsafe(24), False


def lies_tunnel_url(zeile: str) -> str | None:
    """Sucht in einer Ausgabezeile von cloudflared die öffentliche Tunnel-Adresse."""
    treffer = _TUNNEL_URL_MUSTER.search(zeile)
    return treffer.group(0) if treffer else None


def baue_link(tunnel_url: str, token: str) -> str:
    """Fertiger Link für Tester. Das Token wird URL-kodiert, falls ein selbst gewähltes Token aus
    der .env Sonderzeichen enthält (zufällige Tokens bestehen ohnehin nur aus URL-tauglichen
    Zeichen)."""
    return f"{tunnel_url.rstrip('/')}/?{ZUGANG_PARAMETER}={quote(token, safe='')}"


def port_frei(host: str = HOST, port: int = PORT) -> bool:
    """Prüft, ob der Port noch frei ist. Läuft dort bereits eine Webapp (z. B. ein vergessenes
    `uvicorn webapp:app` ohne Zugriffsschutz), würde der Tunnel sonst auf diese zeigen."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
        try:
            test_socket.bind((host, port))
        except OSError:
            return False
    return True


def _warte_auf_webapp(prozess: subprocess.Popen, zeitlimit_sekunden: float = 60.0) -> bool:
    """Wartet, bis die Webapp Anfragen beantwortet. Abgefragt wird ein frei zugängliches Bild,
    damit die Prüfung ohne Token funktioniert und keine Sitzung startet."""
    adresse = f"http://{HOST}:{PORT}/static/img/avatar.svg"
    ende = time.monotonic() + zeitlimit_sekunden
    while time.monotonic() < ende:
        if prozess.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(adresse, timeout=2) as antwort:
                if antwort.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def _lese_ausgabe(prozess: subprocess.Popen, zeilen: queue.Queue) -> None:
    """Liest die Ausgabe von cloudflared fortlaufend in eine Warteschlange. Muss auch nach dem
    Fund der Adresse weiterlaufen: Ein nicht geleerter Ausgabepuffer würde cloudflared sonst
    irgendwann blockieren."""
    assert prozess.stdout is not None
    for zeile in prozess.stdout:
        zeilen.put(zeile)
    zeilen.put(None)  # Ende der Ausgabe (Prozess beendet)


def _warte_auf_tunnel_url(
    prozess: subprocess.Popen, zeilen: queue.Queue, zeitlimit_sekunden: float = 90.0
) -> tuple[str | None, list[str]]:
    """Liest Zeilen, bis die Tunnel-Adresse erscheint. Gibt zusätzlich die gelesenen Zeilen zurück,
    um sie bei einem Fehlschlag anzeigen zu können."""
    gelesen: list[str] = []
    ende = time.monotonic() + zeitlimit_sekunden
    while time.monotonic() < ende:
        try:
            zeile = zeilen.get(timeout=0.5)
        except queue.Empty:
            continue
        if zeile is None:
            break
        gelesen.append(zeile.rstrip())
        url = lies_tunnel_url(zeile)
        if url:
            return url, gelesen
    return None, gelesen


def _beende(prozess: subprocess.Popen | None, name: str) -> None:
    """Beendet einen selbst gestarteten Kindprozess gezielt über seine Prozess-ID, nie über den
    Programmnamen (sonst träfe es auch fremde Uvicorn- oder cloudflared-Prozesse).

    Strg+C erreicht unter Windows alle Prozesse desselben Konsolenfensters; die Kindprozesse
    beenden sich dann meist selbst. Erst wenn das nicht binnen weniger Sekunden geschieht, wird
    hart beendet, unter Windows mit `taskkill /T`, damit auch von der Webapp gestartete
    Unterprozesse (Claude-Code-CLI des Agent SDK) nicht weiterlaufen."""
    if prozess is None or prozess.poll() is not None:
        return
    try:
        prozess.wait(timeout=8)
        return
    except subprocess.TimeoutExpired:
        pass
    print(f"{name} wird beendet ...")
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(prozess.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        prozess.terminate()
    try:
        prozess.wait(timeout=5)
    except subprocess.TimeoutExpired:
        prozess.kill()


def _in_zwischenablage(text: str) -> bool:
    """Kopiert den Link unter Windows in die Zwischenablage (Bordmittel `clip`)."""
    if sys.platform != "win32":
        return False
    try:
        return subprocess.run(["clip"], input=text.encode("ascii"), check=False).returncode == 0
    except (OSError, UnicodeEncodeError):
        return False


def _zeige_link(link: str, token_aus_konfiguration: bool, kopiert: bool) -> None:
    rahmen = "=" * max(60, len(link) + 4)
    print()
    print(rahmen)
    print("  REISEBOT FÜR TESTER FREIGEGEBEN – diesen Link weitergeben:")
    print()
    print(f"  {link}")
    print()
    print(rahmen)
    if kopiert:
        print("Der Link wurde in die Zwischenablage kopiert.")
    if token_aus_konfiguration:
        print("Zugangstoken aus der .env (ZUGANGSTOKEN). Die Adresse ändert sich trotzdem bei jedem Start.")
    else:
        print("Zugangstoken zufällig erzeugt; Link und Token gelten nur für diesen Start.")
    print("Falls der Link nicht sofort lädt: etwa eine halbe Minute warten und neu laden.")
    print("Jedes Gespräch verursacht LLM- und API-Kosten. Link nur an Tester weitergeben.")
    print()
    print("Fenster offen lassen; Strg+C beendet den Zugang.")
    print()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cloudflared = finde_cloudflared()
    if cloudflared is None:
        print(_ANLEITUNG_CLOUDFLARED)
        return 1
    if not port_frei():
        print(f"Port {PORT} ist bereits belegt. Läuft noch eine Webapp (uvicorn webapp:app)? "
              "Bitte diese zuerst beenden und dann erneut starten.")
        return 1

    # Import erst hier: lädt die .env, damit ein dort eingetragenes ZUGANGSTOKEN berücksichtigt wird.
    from src.config import EINSTELLUNGEN

    token, token_aus_konfiguration = bestimme_token(EINSTELLUNGEN.zugangstoken)
    # Das Token geht nur per Umgebungsvariable an den Kindprozess; python-dotenv überschreibt
    # bestehende Umgebungsvariablen nicht, die Webapp verwendet also genau dieses Token.
    umgebung = dict(os.environ, ZUGANGSTOKEN=token)

    webapp: subprocess.Popen | None = None
    tunnel: subprocess.Popen | None = None
    try:
        print(f"Starte Webapp auf http://{HOST}:{PORT}/ ...")
        webapp = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "webapp:app", "--host", HOST, "--port", str(PORT)],
            cwd=_PROJEKT_VERZEICHNIS, env=umgebung,
        )
        if not _warte_auf_webapp(webapp):
            print("Die Webapp ist nicht gestartet. Fehlermeldung siehe oben.")
            return 1

        print("Öffne Cloudflare-Tunnel ...")
        # 127.0.0.1 statt "localhost": cloudflared könnte "localhost" sonst zu ::1 (IPv6) auflösen,
        # Uvicorn lauscht aber nur auf IPv4. --no-autoupdate verhindert Neustarts während eines Tests.
        tunnel = subprocess.Popen(
            [cloudflared, "tunnel", "--no-autoupdate", "--url", f"http://{HOST}:{PORT}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        zeilen: queue.Queue = queue.Queue()
        threading.Thread(target=_lese_ausgabe, args=(tunnel, zeilen), daemon=True).start()

        tunnel_url, gelesen = _warte_auf_tunnel_url(tunnel, zeilen)
        if tunnel_url is None:
            print("Es konnte keine Tunnel-Adresse ermittelt werden. Letzte Ausgabe von cloudflared:")
            for zeile in gelesen[-15:]:
                print("  " + zeile)
            return 1

        link = baue_link(tunnel_url, token)
        _zeige_link(link, token_aus_konfiguration, _in_zwischenablage(link))

        # Solange beide Prozesse laufen, nur warten. Fehlerzeilen von cloudflared (Kennung "ERR")
        # werden durchgereicht, damit Verbindungsprobleme sichtbar sind; der Rest wird verworfen.
        while webapp.poll() is None and tunnel.poll() is None:
            try:
                zeile = zeilen.get(timeout=1)
            except queue.Empty:
                continue
            if zeile and " ERR " in zeile:
                print("[cloudflared] " + zeile.rstrip())
        print("Webapp oder Tunnel wurde beendet; der Zugang ist geschlossen.")
        return 1
    except KeyboardInterrupt:
        print("\nBeende Tunnel und Webapp ...")
        return 0
    finally:
        _beende(tunnel, "cloudflared")
        _beende(webapp, "Webapp")


if __name__ == "__main__":
    sys.exit(main())
