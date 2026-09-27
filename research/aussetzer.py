"""Hat irgendwo ein Gate gar nicht geurteilt? - Befund 346.

``GateResult.passed`` ist wahr, solange ein Gate nicht **durchgefallen** ist,
und ein uebersprungenes Gate ist nicht durchgefallen. Eine Bilanz "9 von 11"
kann damit zwei Dinge heissen: neun Urteile und zwei Durchfaller, oder acht
Urteile, ein Durchfaller und zwei Aussetzer. Befund 321/322 hat das an zwei
Stellen behoben, 332 hat sechzehn weitere Typen aufgelistet, bei denen die
Frage offen blieb, und ausdruecklich nicht gemessen, ob es heute etwas trifft.

Hier wird es gemessen, und zwar an der einzigen Stelle, die es rueckwirkend
hergibt: **den geschriebenen Berichten.** Jeder Reglerpunkt in ``reports/``
traegt seine Gates mit einem Feld ``uebersprungen`` - dieselbe Quelle, aus der
``gatemuster.lade`` seit Befund 333 die ausgesetzten Gates herausnimmt.

Gemessen (346) ueber 13 Dateien und 83 Messpunkte aus zehn Reglern: **kein
einziger Aussetzer**, jeder Punkt mit elf Gates, kleinste Trade-Zahl 75 gegen
Aussetzschwellen von 30 (Regime-Aufteilung, Deflated Sharpe) und 20
(Monte-Carlo).

Das ist kein Freispruch fuer die Zukunft. Es ist die Auskunft, die den offenen
Faellen aus Befund 332 gefehlt hat: nicht "koennte falsch sein", sondern "ist
es auf allem, was geschrieben wurde, nicht".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Berichtslage", "Punktlage", "lese"]


@dataclass(frozen=True, slots=True)
class Punktlage:
    """Ein Messpunkt aus einem Bericht und seine Gate-Auskunft."""

    datei: str
    stellung: float
    trades: int
    gates: int
    uebersprungen: int

    @property
    def geurteilt(self) -> int:
        return self.gates - self.uebersprungen

    @property
    def vollstaendig(self) -> bool:
        return self.uebersprungen == 0 and self.gates > 0

    @property
    def nah_an_der_schwelle(self) -> bool:
        """Liegt die Trade-Zahl so tief, dass ein Aussetzen droht?

        Die Schwellen stehen in ``gates.py``: 30 fuer Regime-Aufteilung und
        Deflated Sharpe, 20 fuer Monte-Carlo. "Nah" heisst hier das Doppelte
        der hoechsten - darunter ist die Frage keine theoretische mehr.
        """
        return self.trades < 60


@dataclass(frozen=True, slots=True)
class Berichtslage:
    """Alle Messpunkte, die auf der Platte liegen."""

    punkte: tuple[Punktlage, ...]

    @property
    def dateien(self) -> int:
        return len({p.datei for p in self.punkte})

    @property
    def mit_aussetzern(self) -> tuple[Punktlage, ...]:
        return tuple(p for p in self.punkte if p.uebersprungen)

    @property
    def knappe(self) -> tuple[Punktlage, ...]:
        return tuple(p for p in self.punkte if p.nah_an_der_schwelle)

    @property
    def kleinste_trade_zahl(self) -> int | None:
        return min((p.trades for p in self.punkte), default=None)

    def urteil(self) -> str:
        if not self.punkte:
            return (
                "Keine Berichte mit Messpunkten - ueber Aussetzer laesst sich "
                "so nichts sagen."
            )
        kopf = (
            f"{len(self.punkte)} Messpunkte aus {self.dateien} Berichten "
            f"angesehen."
        )
        if self.mit_aussetzern:
            namen = ", ".join(
                f"{p.datei} Stellung {p.stellung:g} ({p.uebersprungen} von "
                f"{p.gates})"
                for p in self.mit_aussetzern[:5]
            )
            return (
                f"{kopf} **{len(self.mit_aussetzern)} davon tragen ein Gate "
                f"ohne Urteil** - dort ist die rohe Bilanz zu gut: {namen}. "
                f"Wer sie liest, zaehlt ein uebersprungenes Gate als "
                f"bestanden (Befund 321/322/332)."
            )
        return (
            f"{kopf} **Kein einziger Aussetzer**, und die kleinste Trade-Zahl "
            f"ist {self.kleinste_trade_zahl} gegen Aussetzschwellen von 30 und "
            f"20. Die rohen Bilanzen dieser Punkte sind damit richtig."
            + (
                f" {len(self.knappe)} Punkte liegen unter 60 Trades und waeren "
                f"die ersten, bei denen es kippt."
                if self.knappe
                else " Kein Punkt liegt unter 60 Trades."
            )
        )


def _punkte_der_datei(datei: Path) -> list[Punktlage]:
    try:
        daten = json.loads(datei.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(daten, dict):
        return []
    rohe = daten.get("punkte") or (daten.get("analyse") or {}).get("punkte") or []
    gefunden = []
    for punkt in rohe:
        gates = punkt.get("gates")
        if not isinstance(gates, dict) or not gates:
            continue
        gefunden.append(
            Punktlage(
                datei=datei.stem,
                stellung=float(punkt.get("stellung", 0.0)),
                trades=int((punkt.get("kennzahlen") or {}).get("trades") or 0),
                gates=len(gates),
                uebersprungen=sum(
                    1
                    for stand in gates.values()
                    if isinstance(stand, dict) and stand.get("uebersprungen")
                ),
            )
        )
    return gefunden


def lese(ordner: Path | str) -> Berichtslage:
    """Jeden Messpunkt unter ``ordner`` einsammeln - rekursiv.

    Die Berichtsarten liegen in Unterordnern, und welche davon Punkte
    enthaelt, soll hier nicht noch einmal aufgezaehlt werden muessen (dieselbe
    Begruendung wie in ``streuung.aus_berichten``).
    """
    wurzel = Path(ordner)
    if not wurzel.exists():
        return Berichtslage(punkte=())
    gefunden: list[Punktlage] = []
    for datei in sorted(wurzel.rglob("*.json")):
        gefunden.extend(_punkte_der_datei(datei))
    return Berichtslage(punkte=tuple(gefunden))
