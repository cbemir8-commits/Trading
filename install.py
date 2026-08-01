"""Einrichtung auf dem eigenen Rechner - ein Befehl, alle Systeme.

    python install.py

Legt die Arbeitsumgebung an, installiert die Abhaengigkeiten und sagt danach,
was als Naechstes zu tun ist.

Warum ein Python-Skript und keine Batch- oder Shell-Datei: Windows, macOS und
Linux brauchen sonst drei Fassungen, die alle einzeln kaputtgehen koennen.
Python ist ohnehin Voraussetzung - dann kann es auch die Einrichtung machen.

Bewusst gespraechig. Wer das hier ausfuehrt, richtet vielleicht zum ersten Mal
etwas auf der Kommandozeile ein; eine Fehlermeldung wie "subprocess returned
non-zero exit status 1" hilft dabei niemandem.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
VENV = ROOT / ".venv"

MIN_PYTHON = (3, 11)


def say(text: str = "") -> None:
    print(text, flush=True)


def headline(text: str) -> None:
    say()
    say(text)
    say("-" * len(text))


def python_in_venv() -> Path:
    """Wo liegt der Python-Interpreter in der Arbeitsumgebung?

    Unter Windows in ``Scripts``, sonst in ``bin`` - der einzige Unterschied,
    der hier wirklich zaehlt.
    """
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def check_python() -> None:
    headline("1. Python pruefen")
    version = sys.version_info
    say(f"Gefunden: Python {version.major}.{version.minor}.{version.micro}")

    if version < MIN_PYTHON:
        say()
        say(f"Zu alt. Gebraucht wird mindestens Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}.")
        say("Herunterladen auf python.org/downloads")
        if platform.system() == "Windows":
            say()
            say("Beim Installieren unter Windows unbedingt anhaken:")
            say('   [x] "Add python.exe to PATH"')
            say("Ohne das findet die Kommandozeile Python spaeter nicht.")
        sys.exit(1)

    say("Passt.")


def create_venv() -> None:
    headline("2. Arbeitsumgebung anlegen")
    say("Ein abgetrennter Ordner fuer die Zusatzpakete dieses Projekts.")
    say("So kommt sich nichts mit anderen Programmen auf dem Rechner ins Gehege.")
    say()

    if python_in_venv().exists():
        say("Ist schon da - wird weiterverwendet.")
        return

    say("Lege .venv an ...")
    venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    say("Fertig.")


def install_dependencies() -> None:
    headline("3. Bausteine installieren")
    say("Das dauert ein bis drei Minuten. Es laedt etwa 150 MB.")
    say()

    python = str(python_in_venv())
    steps = [
        ([python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"], "Paketwerkzeug"),
        ([python, "-m", "pip", "install", "-e", ".[dev,api,research]", "--quiet"], "Projekt"),
    ]

    for command, label in steps:
        say(f"  {label} ...")
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            say()
            say(f"Das hat nicht geklappt ({label}).")
            say()
            say("Die Fehlermeldung im Original:")
            say(result.stderr.strip()[-1500:] or result.stdout.strip()[-1500:])
            say()
            say("Schick mir diesen Text - daran laesst sich erkennen, woran es liegt.")
            sys.exit(1)

    say("Alles installiert.")


def create_folders() -> None:
    headline("4. Ordner anlegen")
    for name, purpose in [
        ("logs", "Protokolle"),
        ("state", "Betriebszustand - hier merkt sich das System, was war"),
        ("data_store", "Kursdaten"),
        ("strategies", "zugelassene Strategien"),
    ]:
        (ROOT / name).mkdir(exist_ok=True)
        say(f"  {name}/  ({purpose})")


def verify() -> None:
    headline("5. Probe")
    result = subprocess.run(
        [str(python_in_venv()), "-m", "cli", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        say("Das Programm laesst sich nicht starten:")
        say(result.stderr.strip()[-1000:])
        sys.exit(1)
    say("Das Programm laeuft.")


def next_steps() -> None:
    windows = platform.system() == "Windows"
    runner = "start.bat" if windows else "./start.sh"
    python = ".venv\\Scripts\\python" if windows else ".venv/bin/python"

    headline("Fertig. Und jetzt?")
    say("Drei Schritte, einer nach dem anderen. Nach jedem kurz schauen,")
    say("ob etwas Rotes dabei war.")
    say()
    say(f"  1.  {python} -m cli setup")
    say("      Fragt deinen Bybit-Schluessel ab und prueft sofort die Verbindung.")
    say()
    say(f"  2.  {python} -m cli backfill")
    say("      Laedt die Kurshistorie. Dauert rund 8 Minuten.")
    say()
    say(f"  3.  {python} -m cli research")
    say("      Prueft Strategien. Findet wahrscheinlich keine - das ist")
    say("      ein Ergebnis, kein Fehler.")
    say()
    say(f"Wenn eine gefunden wurde, startet {runner} den Handel und die Website.")
    say()
    say("Bei jedem Schritt gilt: Wenn etwas nicht klappt, schick mir den Text,")
    say("der im Fenster steht. Auch wenn er lang aussieht.")


def main() -> int:
    say("=" * 62)
    say("  Trading-System - Einrichtung")
    say(f"  {platform.system()} {platform.release()}")
    say("=" * 62)

    check_python()
    create_venv()
    install_dependencies()
    create_folders()
    verify()
    next_steps()
    return 0


if __name__ == "__main__":
    sys.exit(main())
