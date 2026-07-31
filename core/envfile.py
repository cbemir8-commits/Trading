"""Schreibender Zugriff auf die ``.env`` - vorsichtig.

In dieser Datei stehen die API-Zugangsdaten. Beim Bearbeiten gelten deshalb
strengere Regeln als bei einer gewoehnlichen Konfigurationsdatei:

* **Kommentare und fremde Eintraege bleiben unangetastet.** Die ``.env`` ist
  auch Dokumentation - die Hinweise darin ("Withdrawal NIEMALS aktivieren")
  sind mehr wert als die Bequemlichkeit, sie neu zu generieren.
* **Auskommentiertes bleibt auskommentiert.** Ein ``# BYBIT__API_KEY=`` ist
  kein Eintrag, den man ueberschreibt, sondern ein Beispiel.
* **Atomar geschrieben.** Ein Absturz mitten im Schreiben darf keine halbe
  Datei hinterlassen - sonst ist beim naechsten Start die Konfiguration weg
  und der Prozess handelt mit Standardwerten.
* **Dateirechte 600.** Nur der Eigentuemer darf lesen. Auf einem Server mit
  mehreren Konten ist das der Unterschied zwischen 'geschuetzt' und 'oeffentlich'.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

#: Nur der Eigentuemer darf lesen und schreiben.
SECRET_FILE_MODE = 0o600


def update_env_file(path: Path | str, values: dict[str, str]) -> None:
    """Werte in einer ``.env`` setzen, ohne den Rest anzufassen.

    Vorhandene Schluessel werden an Ort und Stelle ersetzt, fehlende ans Ende
    angehaengt. Alles andere - Kommentare, Leerzeilen, Reihenfolge - bleibt,
    wie es war.
    """
    file = Path(path)
    original = file.read_text() if file.exists() else ""
    lines = original.splitlines()

    remaining = dict(values)
    for index, line in enumerate(lines):
        for key in list(remaining):
            # ``^\s*KEY\s*=`` - ein fuehrendes '#' passt bewusst nicht.
            if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                lines[index] = f"{key}={remaining.pop(key)}"
                break

    if remaining:
        if lines and lines[-1].strip():
            lines.append("")
        for key, value in remaining.items():
            lines.append(f"{key}={value}")

    content = "\n".join(lines) + "\n"

    # Erst in eine Nebendatei, dann umbenennen - und die Rechte setzen,
    # *bevor* der Inhalt darin steht.
    temporary = file.with_suffix(file.suffix + ".tmp")
    temporary.touch(mode=SECRET_FILE_MODE, exist_ok=True)
    os.chmod(temporary, SECRET_FILE_MODE)
    temporary.write_text(content)
    temporary.replace(file)
    os.chmod(file, SECRET_FILE_MODE)


def read_env_value(path: Path | str, key: str) -> str | None:
    """Einen Wert aus der ``.env`` lesen, ohne die Settings zu laden.

    Wird gebraucht, um zu pruefen, ob schon ein Schluessel hinterlegt ist -
    bevor gefragt wird, ob er ueberschrieben werden soll.
    """
    file = Path(path)
    if not file.exists():
        return None
    for line in file.read_text().splitlines():
        match = re.match(rf"^\s*{re.escape(key)}\s*=(.*)$", line)
        if match:
            return match.group(1).strip().strip("\"'")
    return None


def file_is_world_readable(path: Path | str) -> bool:
    """Duerfen andere Konten auf diesem Rechner die Datei lesen?"""
    file = Path(path)
    if not file.exists():
        return False
    mode = file.stat().st_mode
    return bool(mode & (stat.S_IRGRP | stat.S_IROTH))


def mask(secret: str, *, keep: int = 4) -> str:
    """Ein Geheimnis so anzeigen, dass man es wiedererkennt, aber nicht nutzen kann.

    Kurze Zeichenketten werden vollstaendig maskiert - bei einem achtstelligen
    Wert waeren vier sichtbare Zeichen bereits die halbe Miete.
    """
    if len(secret) <= keep * 2:
        return "*" * len(secret)
    return f"{secret[:keep]}{'*' * (len(secret) - keep * 2)}{secret[-keep:]}"
