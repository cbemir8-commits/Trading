"""Was im Berichtsordner schon liegt - Befund 319.

Der Anlass
----------
Befund 318: Ich wollte wissen, was BTC allein auf seiner **ganzen** Reihe
leistet, habe das Register gefragt, dort nichts gefunden und gemessen. Die
Antwort lag seit einer Woche in
``reports/marktkombinationen/2026-09-13_010559.json``:

    BTC   117 Trades   DSR 0,4620   5/11

Dasselbe Ergebnis, dieselben sechs offenen Gates.

Das ist der zweite Fall dieser Art. Der erste war Befund 302 - 106 Minuten
fuer eine Frage, deren Antwort im Register stand -, und die Lehre daraus war
``research/vorwissen.py``: vor einem langen Lauf die passenden
Registereintraege heraussuchen und hinschreiben.

**Nur sucht ``vorwissen`` im Register und nicht im Berichtsordner.** Genau
die Luecke ist 318 gewesen. Der Ablauf nennt beide Quellen ausdruecklich -
*"Was ist der Stand? (state/leaderboard.json, reports/, letzter Commit)"* -,
und die eine davon war nirgends abgefragt.

Was dieses Modul tut
--------------------
Es sieht nach, welche Berichtsarten es gibt, wie viele Berichte je Art
vorliegen, wann der neueste entstanden ist und was er als Urteil traegt.
Mehr nicht.

Was es **nicht** tut
--------------------
**Es urteilt nicht ueber die Treffer.** Ob ein Bericht die Frage wirklich
beantwortet, steht in seinem Inhalt und ist mit einem Dateinamen nicht zu
haben - dieselbe Regel wie in ``vorwissen`` und ``nachmessung``: Eine Suche,
die Verdachtsfaelle liefert, ist nuetzlich; eine Suche, deren Treffer man
ungeprueft uebernimmt, ist schlimmer als keine.

**Es haelt nichts auf.** Eine Messung zu wiederholen ist oft richtig. Falsch
war in 318 nicht der Lauf, falsch war, ihn zu starten, ohne die Antwort zu
kennen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

__all__ = ["WURZEL", "Berichtsart", "auskunft", "berichtslage"]

#: Wo die Berichte liegen - relativ zum Arbeitsverzeichnis, wie ueberall
#: sonst in diesem Projekt (``cli.py`` schreibt nach ``Path.cwd()/reports``).
WURZEL = Path("reports")

#: Die Endungen, die als Bericht zaehlen. ``.jsonl`` sind die Protokolle aus
#: Befund 299 - ihr Kopf steht in der ersten Zeile.
ENDUNGEN = (".json", ".jsonl")


@dataclass(frozen=True, slots=True)
class Berichtsart:
    """Eine Berichtsart und was zuletzt darin steht."""

    art: str
    anzahl: int
    neuester: str
    """Der Dateiname des neuesten Berichts ohne Endung - bei allen
    Schreibern ein Zeitstempel, deshalb sortiert er wie ein Datum."""

    urteil: str = ""
    """Das Urteilsfeld des neuesten Berichts, falls er eines traegt.

    Leer heisst "kein Urteilsfeld" und nicht "kein Urteil": Die Protokolle
    aus Befund 299 tragen einen Kopf mit Bedingungen, aber keinen Satz.
    """

    def passt_zu(self, begriffe: tuple[str, ...]) -> bool:
        """Beruehrt einer der Begriffe diese Art - im Namen oder im Urteil?"""
        heu = f"{self.art} {self.urteil}".casefold()
        return any(b.casefold() in heu for b in begriffe if b)

    def kopfzeile(self) -> str:
        wort = "Bericht" if self.anzahl == 1 else "Berichte"
        return f"{self.art:22} {self.anzahl:3} {wort}, neuester {self.neuester}"


def _urteil(datei: Path) -> str:
    """Das Urteilsfeld einer Berichtsdatei - leer, wenn keines dasteht.

    Faengt breit ab: Eine unlesbare Datei ist ein Grund hinzusehen und kein
    Grund, den Befehl abzubrechen, der sie nur nebenbei liest.
    """
    try:
        roh = datei.read_text(encoding="utf-8")
        kopf = json.loads(roh if datei.suffix == ".json" else roh.splitlines()[0])
    except (OSError, ValueError, IndexError):
        return ""
    return str(kopf.get("urteil", "")) if isinstance(kopf, dict) else ""


def berichtslage(wurzel: Path | None = None) -> tuple[Berichtsart, ...]:
    """Was im Berichtsordner liegt, je Art - nach Name sortiert."""
    ordner = WURZEL if wurzel is None else wurzel
    if not ordner.is_dir():
        return ()

    arten = []
    for unter in sorted(p for p in ordner.iterdir() if p.is_dir()):
        dateien = sorted(
            p for p in unter.iterdir() if p.suffix in ENDUNGEN and p.is_file()
        )
        if not dateien:
            continue
        arten.append(
            Berichtsart(
                art=unter.name,
                anzahl=len(dateien),
                neuester=dateien[-1].stem,
                urteil=_urteil(dateien[-1]),
            )
        )
    return tuple(arten)


def auskunft(*begriffe: str, wurzel: Path | None = None, breite: int = 100) -> str:
    """Was der Berichtsordner zu diesen Begriffen schon hergibt.

    Jede Art bekommt eine Zeile. Wo ein Begriff anschlaegt, steht das Urteil
    des neuesten Berichts darunter - das ist der Satz, der in Befund 318
    gereicht haette, um die Datei aufzuschlagen.

    Ohne Begriffe stehen nur die Kopfzeilen da. Das ist Absicht: Sieben
    Urteile vor jedem Lauf liest niemand, und was niemand liest, wirkt nicht.
    """
    arten = berichtslage(wurzel)
    if not arten:
        return ""

    zeilen = ["Und was im Berichtsordner schon liegt:"]
    getroffen = 0
    for a in arten:
        zeilen.append(f"  {a.kopfzeile()}")
        if a.urteil and a.passt_zu(begriffe):
            getroffen += 1
            kurz = a.urteil if len(a.urteil) <= breite else a.urteil[:breite] + " ..."
            zeilen.append(f"      {kurz}")

    gesamt = sum(a.anzahl for a in arten)
    if getroffen:
        wort = "beruehrt" if getroffen == 1 else "beruehren"
        zeilen.append(
            f"**{getroffen} von {len(arten)} Arten {wort} diese Frage.** "
            f"Aufschlagen kostet eine Minute."
        )
    else:
        zeilen.append(
            f"{gesamt} Berichte, keiner davon beruehrt die Begriffe dieses "
            f"Laufs - das heisst nicht, dass keiner die Antwort traegt."
        )
    return "\n".join(zeilen)
