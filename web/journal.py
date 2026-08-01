"""Was der Handelsprozess der Website erzaehlt - und wie sie zurueckredet.

Handel und Dashboard laufen als **zwei getrennte Prozesse**. Das ist die
wichtigste Entscheidung an dieser Stelle, und sie hat einen Grund:

Liefe die Website im selben Prozess wie der Handel, waere sie genau dann weg,
wenn man sie am dringendsten braucht - naemlich wenn der Handelsprozess
abgestuerzt ist. Getrennt zeigt das Dashboard stattdessen "Bot laeuft nicht
mehr, letztes Lebenszeichen vor 14 Minuten". Das ist die Information, um die
es geht.

Der Austausch laeuft ueber Dateien:

* ``live.json``     - Momentaufnahme, vom Handel geschrieben (Herzschlag,
                      Position, Kennzahlen). Atomar ersetzt, nie halb gelesen.
* ``events.jsonl``  - Ereignisstrom, zeilenweise angehaengt. Was die KI tut,
                      in Klartext.
* ``command.json``  - der Rueckkanal: Was das Dashboard vom Handel will.

Dateien statt Netzwerk oder Datenbank, weil beide Prozesse auf derselben
Maschine laufen und ein Neustart auf beiden Seiten folgenlos bleiben muss.
Ein abgestuerztes Dashboard darf den Handel nicht beruehren, und umgekehrt.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

#: Aelter als das, gilt der Handelsprozess als nicht mehr am Leben. Grosszuegig
#: bemessen: Auf einem 15-Minuten-Intervall schreibt er nur alle 15 Minuten -
#: haeufiger nur, wenn tatsaechlich etwas passiert.
HEARTBEAT_TIMEOUT = timedelta(minutes=20)

#: So viele Ereignisse haelt die Datei. Danach wird vorn abgeschnitten -
#: sonst waechst sie unbegrenzt und das Dashboard wird mit der Zeit langsam.
MAX_EVENTS = 2000


class EventKind(StrEnum):
    """Ereignisarten - bestimmen Farbe und Symbol im Dashboard."""

    START = "start"
    CANDLE = "candle"
    SIGNAL = "signal"
    VETO = "veto"
    ENTRY = "entry"
    TARGET = "target"
    EXIT = "exit"
    STOP_MOVED = "stop_moved"
    WARNING = "warning"
    KILL = "kill"
    COMMAND = "command"


@dataclass(slots=True)
class Event:
    """Ein Eintrag im Ereignisstrom - das, was die Website als 'was die KI
    gerade macht' anzeigt."""

    kind: EventKind
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


def _plain(value: Any) -> Any:
    """Decimal und datetime in etwas verwandeln, das JSON versteht.

    Decimal wird zu ``str``, nicht zu ``float``: Ein Kontostand, der ueber
    Fliesskomma laeuft, zeigt irgendwann 499.99999999998 an.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


class LiveJournal:
    """Schreibseite: Der Handelsprozess berichtet."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = self.directory / "live.json"
        self.events_path = self.directory / "events.jsonl"
        self.command_path = self.directory / "command.json"

    # -- Momentaufnahme ------------------------------------------------------
    def write_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Den aktuellen Stand ablegen - inklusive Herzschlag.

        Atomar (Nebendatei + Umbenennen), weil das Dashboard jederzeit liest.
        Ohne das laege irgendwann eine halb geschriebene Datei vor, und die
        Website zeigte einen Fehler statt eines Kontostands.
        """
        payload = _plain(dict(snapshot))
        payload["heartbeat"] = datetime.now(UTC).isoformat()
        payload["pid"] = os.getpid()

        temporary = self.snapshot_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2))
        temporary.replace(self.snapshot_path)

    # -- Ereignisse ----------------------------------------------------------
    def record(self, kind: EventKind, message: str, **data: Any) -> Event:
        """Ein Ereignis anhaengen."""
        event = Event(kind=kind, message=message, data=_plain(data))
        with self.events_path.open("a") as handle:
            handle.write(json.dumps(event.to_json()) + "\n")
        self._trim()
        return event

    def _trim(self) -> None:
        """Die Ereignisdatei beschneiden, wenn sie zu lang wird.

        Nur gelegentlich pruefen: Bei jedem Ereignis die ganze Datei zu lesen
        waere in einem Prozess, der monatelang laeuft, verschwendete Arbeit.
        """
        try:
            if self.events_path.stat().st_size < MAX_EVENTS * 200:
                return
            lines = self.events_path.read_text().splitlines()
            if len(lines) <= MAX_EVENTS:
                return
            keep = lines[-MAX_EVENTS:]
            temporary = self.events_path.with_suffix(".tmp")
            temporary.write_text("\n".join(keep) + "\n")
            temporary.replace(self.events_path)
        except OSError as exc:  # Protokollpflege darf nie den Handel stoeren
            log.warning("journal.kuerzen_fehlgeschlagen", fehler=str(exc))

    # -- Rueckkanal ----------------------------------------------------------
    def take_command(self) -> Command | None:
        """Einen wartenden Befehl abholen - und dabei entfernen.

        Abholen und Loeschen in einem Schritt: Bliebe der Befehl liegen,
        wuerde er bei jeder Kerze erneut ausgefuehrt. Ein "alles schliessen",
        das sich alle 15 Minuten wiederholt, waere unangenehm.
        """
        if not self.command_path.exists():
            return None
        try:
            raw = json.loads(self.command_path.read_text())
            command = Command(action=CommandAction(raw["action"]), reason=raw.get("reason", ""))
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            log.error("journal.befehl_unlesbar", fehler=str(exc))
            self.command_path.unlink(missing_ok=True)
            return None
        self.command_path.unlink(missing_ok=True)
        return command


class CommandAction(StrEnum):
    PAUSE = "pause"
    """Keine neuen Positionen. Bestehende laufen weiter."""

    RESUME = "resume"
    CLOSE_ALL = "close_all"
    """Alles glattstellen, danach pausiert."""

    KILL = "kill"
    """Not-Aus: schliessen und abschalten. Nur manuell zurueckholbar."""


@dataclass(slots=True)
class Command:
    action: CommandAction
    reason: str = ""


def send_command(directory: Path | str, action: CommandAction, reason: str = "") -> None:
    """Leseseite: Das Dashboard weist den Handel an.

    Ein einzelner wartender Befehl - ein neuer ersetzt einen noch nicht
    abgeholten. Das ist gewollt: Wer zweimal auf Not-Aus drueckt, meint nicht
    zweimal schliessen.
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    file = path / "command.json"
    temporary = file.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "action": action.value,
                "reason": reason,
                "issued_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
    )
    temporary.replace(file)
    log.warning("dashboard.befehl_gesendet", befehl=action.value, grund=reason)


# ---------------------------------------------------------------------------
#  Leseseite
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LiveView:
    """Was das Dashboard sieht."""

    snapshot: dict[str, Any]
    events: list[dict[str, Any]]
    alive: bool
    last_heartbeat: datetime | None
    stale_for: timedelta | None

    @property
    def status_text(self) -> str:
        if self.alive:
            return "laeuft"
        if self.last_heartbeat is None:
            return "nie gestartet"
        minutes = int((self.stale_for or timedelta()).total_seconds() / 60)
        return f"kein Lebenszeichen seit {minutes} min"


def read_view(directory: Path | str, *, event_limit: int = 100) -> LiveView:
    """Momentaufnahme und Ereignisse lesen.

    Fehlertolerant in jede Richtung: Fehlt der Handelsprozess, fehlen die
    Dateien - dann zeigt das Dashboard "nie gestartet" statt eines Fehlers.
    Genau dafuer ist es da.
    """
    path = Path(directory)
    snapshot: dict[str, Any] = {}
    snapshot_file = path / "live.json"
    if snapshot_file.exists():
        try:
            snapshot = json.loads(snapshot_file.read_text())
        except json.JSONDecodeError:
            snapshot = {}

    events: list[dict[str, Any]] = []
    events_file = path / "events.jsonl"
    if events_file.exists():
        try:
            lines = events_file.read_text().splitlines()[-event_limit:]
            for line in lines:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # eine abgeschnittene letzte Zeile ist normal
        except OSError:
            events = []

    heartbeat = None
    raw_heartbeat = snapshot.get("heartbeat")
    if raw_heartbeat:
        try:
            heartbeat = datetime.fromisoformat(raw_heartbeat)
        except ValueError:
            heartbeat = None

    stale_for = None
    alive = False
    if heartbeat is not None:
        stale_for = datetime.now(UTC) - heartbeat
        alive = stale_for < HEARTBEAT_TIMEOUT

    return LiveView(
        snapshot=snapshot,
        events=list(reversed(events)),  # neueste zuerst
        alive=alive,
        last_heartbeat=heartbeat,
        stale_for=stale_for,
    )
