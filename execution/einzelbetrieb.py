"""Nur ein Handelslauf je Konto - Befund 353.

``cli trade`` legt seinen Risikozustand in **einer** Datei ab:
``state/risk.json``, der Pfad haengt nicht am Symbol. Zwei Laeufe teilen sie
sich also, und jeder haelt seinen eigenen Zustand im Speicher. Gemessen mit
zwei ``RiskOfficer`` auf einem Pfad:

    BTC-Bein sieht 500 -> 400 EUR   Kill-Switch springt, Datei: killed
    ETH-Bein hat 'active' gelesen   und speichert als naechstes
    Datei danach                    active, kill_reason leer

**Der Kill-Switch ist weg**, und nach einem Neustart liest ``load_risk_state``
wieder ``active``: Ein abgeschaltetes System steht auf. Das ist die eine
Sperre, die laut ihrer eigenen Meldung "nur manuell zurueckholbar" ist.

Zwei Wege fuehren dorthin, und keiner ist abwegig:

* Der Nutzer startet ``cli trade`` zweimal - in zwei Fenstern, oder weil der
  erste Lauf vergessen wurde.
* Der Nutzer handelt den **Korb** als zwei Beine. Genau dazu laedt die offene
  Frage aus Befund 263/318 ein: Zugelassen ist der Korb aus BTC und ETH,
  ``LiveTrader`` handelt ein Symbol, und ``unterdeckung`` sagt es auch. Zwei
  Laeufe sind die naheliegende Antwort.

Warum eine Sperre des Betriebssystems und keine PID-Pruefung
------------------------------------------------------------
``LiveTrader`` ist darauf gebaut, dass der Prozess jederzeit sterben und neu
starten darf - das steht in seinem Docstring als Unterschied zwischen Spielzeug
und Betrieb. Eine Sperre, die einen Absturz ueberlebt, wuerde genau diese
Eigenschaft nehmen: Nach einem Stromausfall liesse sich nicht mehr starten.

Eine gespeicherte PID zu pruefen hat zwei Fehler. ``os.kill(pid, 0)`` **beendet
den Prozess** unter Windows - dieses Projekt hat ein ``start.bat``, Windows ist
kein Randfall. Und PIDs werden wiederverwendet: Irgendein fremder Prozess mit
derselben Nummer laesst die Sperre ewig stehen.

Deshalb kommt die Aussage vom Kern: eine nicht blockierende Dateisperre
(``core.dateisperre.sperre_versuchen``, also ``flock`` beziehungsweise
``msvcrt.locking``). Sie haelt, solange der Prozess lebt, und der Kern gibt sie
frei, wenn er stirbt - bei jedem Ende, auch bei ``kill -9``. Derselbe Baustein
sichert seit Befund 354 den Versuchszaehler; dort wird allerdings **gewartet**
statt abgelehnt, weil zwei Forschungslaeufe nebeneinander laufen duerfen. Die PID in der Datei ist **Auskunft fuer die Meldung**, nicht die
Grundlage der Entscheidung.

Was diese Sperre nicht ist
--------------------------
Kein Schutz vor zwei Rechnern am selben Konto: Eine Dateisperre gilt auf einer
Maschine.

Und keine Sperre gegen das Dashboard. Das braucht auch keine: Es schreibt den
Zustand nicht, sondern legt einen Befehl ab (``web.journal.send_command``), den
die laufende Schleife liest. Ein Eingriff geht damit durch den Prozess, der die
Datei haelt - genau richtig, und der Grund, warum diese Sperre ihm nicht in den
Weg kommt.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

import structlog

from core.dateisperre import sperre_versuchen

log = structlog.get_logger(__name__)

__all__ = [
    "SCHWANZ",
    "BereitsInBetrieb",
    "Betrieb",
    "belege",
    "belegung",
]

#: Was an den Namen des Zustands gehaengt wird: ``risk.json.betrieb``.
#:
#: Neben den Zustand und nicht in ihn: Der Zustand wird beim Speichern ueber
#: eine Nebendatei ersetzt (``.tmp`` und ``replace``), und eine Sperre in einer
#: Datei, die durch eine andere ersetzt wird, haelt nichts.
SCHWANZ = ".betrieb"


@dataclass(frozen=True, slots=True)
class Belegung:
    """Wer den Zustand haelt - Auskunft, nicht Entscheidungsgrundlage."""

    pid: int
    symbol: str
    seit: datetime | None = None

    def satz(self) -> str:
        teile = [f"{self.symbol or 'unbekanntes Symbol'}", f"PID {self.pid}"]
        if self.seit is not None:
            teile.append(f"seit {self.seit:%Y-%m-%d %H:%M} UTC")
        return ", ".join(teile)

    def als_json(self) -> dict:
        return {
            "pid": self.pid,
            "symbol": self.symbol,
            "seit": self.seit.isoformat() if self.seit else None,
        }

    @classmethod
    def aus_json(cls, daten: dict) -> Belegung:
        seit = daten.get("seit")
        return cls(
            pid=int(daten.get("pid", 0)),
            symbol=str(daten.get("symbol", "")),
            seit=datetime.fromisoformat(seit) if seit else None,
        )


class BereitsInBetrieb(RuntimeError):  # noqa: N818 - deutsche Namen, wie ueberall hier
    """Ein zweiter Handelslauf auf demselben Zustand.

    Die Meldung nennt **die gemessene Folge**, nicht nur das Verbot: Ein Satz
    wie "laeuft schon" laedt dazu ein, die Sperre zu umgehen. Wer weiss, dass
    der Kill-Switch dabei verschwindet, tut es nicht.
    """

    def __init__(self, zustand: Path, gehalten: Belegung | None) -> None:
        self.zustand = zustand
        self.gehalten = gehalten
        wer = gehalten.satz() if gehalten else "unbekannt, die Auskunft fehlt"
        super().__init__(
            f"Auf {zustand} laeuft schon ein Handelslauf ({wer}).\n"
            "  Zwei Laeufe teilen sich diese Datei, und jeder haelt seinen "
            "eigenen Zustand im Speicher. Gemessen: Der Kill-Switch des einen "
            "wird vom naechsten Speichern des anderen ueberschrieben - das "
            "abgeschaltete System stand danach wieder auf 'active' "
            "(Befund 353).\n"
            "  Entweder den laufenden beenden - oder dem zweiten Bein eine "
            "eigene Ablage geben (PATHS__STATE). Das kostet: Die Verlustgrenzen "
            "gelten dann **je Bein** und nicht je Konto, also zweimal die "
            "Tagesgrenze auf einem Konto."
        )


def sperrpfad(zustand: Path | str) -> Path:
    """Die Sperrdatei zu einem Risikozustand."""
    pfad = Path(zustand)
    return pfad.with_name(pfad.name + SCHWANZ)


def belegung(zustand: Path | str) -> Belegung | None:
    """Was in der Sperrdatei steht - ohne zu sperren.

    Fuer Meldungen und das Dashboard. **Sagt nicht, ob der Lauf lebt**: Das
    weiss nur der Kern, und der sagt es beim Sperren. Eine Datei, deren Inhalt
    noch steht, waehrend der Prozess tot ist, ist der Normalfall nach einem
    Absturz.
    """
    datei = sperrpfad(zustand)
    if not datei.exists():
        return None
    try:
        return Belegung.aus_json(json.loads(datei.read_text() or "{}"))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


#: Alle Sperren, die dieser Prozess haelt.
#:
#: **Gemessen, und es war ein Fund** (Befund 353): Ohne dieses Verzeichnis
#: haengt die Sperre daran, dass der Aufrufer das Ergebnis von ``belege``
#: festhaelt. Wer es wegwirft, verliert sie beim naechsten Aufraeumen - das
#: Dateiobjekt wird geschlossen, und der Kern loest mit dem letzten
#: Dateideskriptor auch die Sperre. Gemessen mit zwei echten Prozessen: Der
#: zweite Lauf kam durch, waehrend der erste noch lief.
#:
#: Die Sperre gehoert dem **Prozess** und nicht der Variablen, also haelt der
#: Prozess sie fest. ``gib_frei`` traegt sie wieder aus.
_GEHALTEN: set[Betrieb] = set()


@dataclass(eq=False)
class Betrieb:
    """Eine gehaltene Sperre. Wird beim Prozessende vom Kern freigegeben.

    Kein ``slots`` und kein ``eq``: Der Prozess haelt seine Sperren in einer
    Menge, und dafuer muss das Objekt nach seiner Identitaet hashbar sein.
    """

    zustand: Path
    eigen: Belegung
    _datei: IO[str] | None = None

    def gib_frei(self) -> None:
        """Sperre loesen und die Auskunft entfernen.

        Mehrfach aufrufbar: Ein ``finally`` neben einem ``with`` soll nicht
        davon abhaengen, wer zuerst dran war.
        """
        _GEHALTEN.discard(self)
        if self._datei is None:
            return
        datei, self._datei = self._datei, None
        try:
            datei.close()
        finally:
            # Der Inhalt ist Auskunft ueber einen Lauf, den es nicht mehr gibt.
            # Fehlt die Datei schon, ist nichts zu tun - nicht zu scheitern.
            sperrpfad(self.zustand).unlink(missing_ok=True)

    def __enter__(self) -> Betrieb:
        return self

    def __exit__(self, *_ausnahme: object) -> None:
        self.gib_frei()


def belege(
    zustand: Path | str,
    *,
    symbol: str,
    pid: int | None = None,
    jetzt: datetime | None = None,
) -> Betrieb:
    """Den Zustand fuer **diesen** Lauf belegen.

    Wirft ``BereitsInBetrieb``, wenn schon ein Lauf darauf sitzt.

    Die Reihenfolge ist wichtig: erst oeffnen **ohne** zu leeren, dann sperren,
    dann schreiben. Wer zuerst leert, hat die Auskunft des anderen geloescht,
    bevor er merkt, dass er nicht darf - und die Meldung koennte nicht sagen,
    wer laeuft.
    """
    pfad = Path(zustand)
    datei_pfad = sperrpfad(pfad)
    datei_pfad.parent.mkdir(parents=True, exist_ok=True)
    datei = datei_pfad.open("a+")
    if not sperre_versuchen(datei):
        datei.close()
        fremd = belegung(pfad)
        log.error(
            "einzelbetrieb.belegt",
            zustand=str(pfad),
            fremde_pid=fremd.pid if fremd else None,
            fremdes_symbol=fremd.symbol if fremd else None,
        )
        raise BereitsInBetrieb(pfad, fremd)

    eigen = Belegung(
        pid=pid if pid is not None else os.getpid(),
        symbol=symbol,
        seit=jetzt or datetime.now(UTC),
    )
    datei.seek(0)
    datei.truncate()
    datei.write(json.dumps(eigen.als_json(), indent=2))
    datei.flush()
    log.info("einzelbetrieb.belegt_von_mir", zustand=str(pfad), symbol=symbol)
    laufend = Betrieb(zustand=pfad, eigen=eigen, _datei=datei)
    _GEHALTEN.add(laufend)
    return laufend
