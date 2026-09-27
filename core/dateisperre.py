"""Eine Dateisperre vom Kern - der Baustein unter zwei Befunden.

Zwei Stellen dieses Projekts teilen eine Datei zwischen Prozessen, und an
beiden hat das Messen einen stillen Verlust gezeigt:

* ``state/risk.json`` - zwei ``cli trade`` loeschen einander den Kill-Switch
  (Befund 353). Dort wird **nicht gewartet**: Ein zweiter Handelslauf soll
  nicht in eine Reihe, er soll gar nicht.
* ``state/trials.json`` - zwei Forschungslaeufe verlieren Versuche und
  Einzelnachweise (Befund 354). Dort wird **gewartet**: Der zweite Lauf darf
  seine Versuche eintragen, nur nicht gleichzeitig.

Deshalb steht der Baustein hier und nicht in einem der beiden Module: Er kennt
weder Handel noch Forschung, nur Dateien.

Warum der Kern und keine gespeicherte PID
-----------------------------------------
Eine Sperre, die einen Absturz ueberlebt, blockiert den Neustart - und
``LiveTrader`` ist darauf gebaut, jederzeit sterben und wiederkommen zu duerfen.
Der Kern gibt eine Dateisperre bei **jedem** Ende frei, auch bei ``kill -9``.

Eine PID zu pruefen hat dagegen zwei Fehler. ``os.kill(pid, 0)`` **beendet den
Prozess** unter Windows - CPython ruft dort ``TerminateProcess`` mit dem Signal
als Exitcode -, und dieses Projekt hat ein ``start.bat``. Und PIDs werden
wiederverwendet: Ein fremder Prozess mit derselben Nummer laesst die Sperre
ewig stehen.

Was sie nicht kann
------------------
Zwei Rechner an einem Konto faengt sie nicht: Eine Dateisperre gilt auf einer
Maschine.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

import structlog

log = structlog.get_logger(__name__)

__all__ = ["GEDULD", "NichtZuSperren", "gesperrt", "sperre_versuchen"]

#: Wie lange ``gesperrt`` auf eine belegte Datei wartet, in Sekunden.
#:
#: Grosszuegig gegen einen kurzen Schreibvorgang gerechnet: Was hier gesperrt
#: wird, ist ein Lesen, ein Verlaengern und ein Schreiben von wenigen Kilobyte.
#: Wer laenger als das wartet, wartet auf etwas anderes - dann ist Abbruch mit
#: Meldung besser als stilles Haengen.
GEDULD = 10.0

#: Wie oft je Sekunde nachgesehen wird, ob die Sperre frei ist.
_TAKT = 0.02


class NichtZuSperren(TimeoutError):  # noqa: N818 - deutsche Namen, wie ueberall hier
    """Die Datei blieb ueber die ganze Geduld hinweg belegt."""

    def __init__(self, pfad: Path, geduld: float) -> None:
        self.pfad = pfad
        self.geduld = geduld
        super().__init__(
            f"{pfad} war {geduld:.0f} Sekunden lang gesperrt. Laeuft noch ein "
            "Lauf, der daran schreibt?"
        )


def sperre_versuchen(datei: IO[str]) -> bool:
    """Nicht blockierend sperren. ``False`` heisst: jemand anders hat sie.

    Zwei Kerne, ein Zweck. ``fcntl`` fehlt unter Windows, ``msvcrt`` ueberall
    sonst - deshalb der Import in der Funktion und nicht oben.
    """
    try:
        import fcntl
    except ImportError:  # pragma: no cover - nur unter Windows
        import msvcrt

        try:
            msvcrt.locking(datei.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    try:
        fcntl.flock(datei.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


@contextmanager
def gesperrt(pfad: Path | str, *, geduld: float | None = None) -> Iterator[None]:
    """Wartend sperren - fuer ein Lesen-Aendern-Schreiben in einem Griff.

    **Der ganze Griff gehoert hinein, nicht nur das Schreiben.** Wer nur das
    Schreiben sperrt, hat zwei Laeufe, die beide den alten Stand gelesen haben
    und ihn beide ordentlich zurueckschreiben - der zweite ueberschreibt den
    ersten, nur eben ohne halbe Datei. Genau so gingen in Befund 354 fuenf
    Versuche und zwei Einzelnachweise verloren.

    Die Sperre liegt auf einer **Nebendatei** (``<name>.sperre``): Wer eine
    Datei ueber ``tmp`` und ``replace`` ersetzt - und so schreiben beide
    Zaehler dieses Projekts -, haette die Sperre sonst auf einer Datei, die es
    nach dem ersten Schreiben nicht mehr gibt.
    """
    # Die Geduld wird **hier** aufgeloest und nicht in der Signatur: So wirkt
    # ein geaendertes ``GEDULD`` auch auf Aufrufer, die keinen Wert mitgeben -
    # und die Tests kommen ohne einen Parameter aus, den sonst jeder Aufrufer
    # durchreichen muesste.
    geduld = GEDULD if geduld is None else geduld
    ziel = Path(pfad)
    sperrdatei = ziel.with_name(ziel.name + ".sperre")
    sperrdatei.parent.mkdir(parents=True, exist_ok=True)
    frist = time.monotonic() + geduld
    datei = sperrdatei.open("a+")
    try:
        while not sperre_versuchen(datei):
            if time.monotonic() >= frist:
                log.error(
                    "dateisperre.abgelaufen", pfad=str(ziel), geduld=geduld
                )
                raise NichtZuSperren(ziel, geduld)
            time.sleep(_TAKT)
        yield
    finally:
        # Schliessen gibt die Sperre frei. Die Nebendatei bleibt liegen: Sie zu
        # loeschen waere ein Wettlauf - ein anderer Lauf koennte sie schon
        # geoeffnet haben und wuerde dann eine Sperre auf einer Datei halten,
        # die keiner mehr findet.
        datei.close()
