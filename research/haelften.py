"""Haelt der Spitzenkandidat in der zweiten Haelfte des Zeitraums?

Die Ungleichbehandlung, die dabei auffiel
-----------------------------------------
``research/vorteilsscan.py`` verlangt von **jedem neuen Fund** drei Dinge, und
das zweite lautet: *in beiden Haelften des Zeitraums dasselbe Vorzeichen*. Der
Kopf dort begruendet es scharf:

    "Ein Vorteil, den es nur in der ersten Haelfte gab, ist entweder
    wegarbitriert oder war nie da. Beides heisst, dass er morgen nicht zur
    Verfuegung steht."

An dieser Huerde ist der erste 15-Minuten-Fund gescheitert, und in Befund 63
die Tageszeit. **Der Spitzenkandidat selbst ist nie daran gemessen worden.**

Wir verlangen von jedem Vorschlag mehr als vom Bestand - und das ist die
gefaehrlichere Richtung: Ein neuer Fund, der die Huerde reisst, wird verworfen
und kostet nichts weiter. Ein Bestand, der sie reissen wuerde, steht seit
Wochen im Mittelpunkt jeder Messung.

Was das aendern wuerde
---------------------
Befund 61 hat den Stand zugespitzt: genau ein ungeloestes Problem, und es
heisst Deflated Sharpe. Diese Diagnose gilt aber nur, wenn ueberhaupt ein
Vorteil da ist, der zu klein ist. Ist er in der zweiten Haelfte verschwunden,
ist die Lage eine andere und die Diagnose falsch: Dann fehlt nicht Groesse,
sondern Gegenwart.

Warum auf Trade-Ebene und nicht auf Fensterebene
------------------------------------------------
Der Walk-Forward hat 31 Fenster - halbiert sind das fuenfzehn, und daraus
laesst sich kaum etwas ablesen. Die 154 Trades geben 77 je Haelfte, und der
Sharpe je Trade ist ohnehin die Groesse, an der der Deflated Sharpe haengt.

Die Falle, die der Vorteilsscan schon kennt
-------------------------------------------
"Nicht stabil" heisst zweierlei: **der Vorteil ist weg** oder **ich haette ihn
hier gar nicht sehen koennen**. Bei 77 Trades je Haelfte ist das keine
Spitzfindigkeit, sondern der wahrscheinlichere Fall. Deshalb wird - wie dort -
mitgerechnet, welcher Unterschied in der zweiten Haelfte ueberhaupt haette
auffallen koennen. Ohne diese Zahl ist ein gescheiterter Test kein Befund.

Kostet keinen Versuch: Zerlegt wird ein Ergebnis, das schon vorliegt.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

#: Mit welcher Wahrscheinlichkeit ein vorhandener Effekt auffallen soll.
#: Dieselbe Zahl wie im Vorteilsscan - eine zweite waere eine zweite Meinung
#: darueber, was "haette man sehen koennen" heisst.
TRENNSCHAERFE = 0.8


@dataclass(frozen=True, slots=True)
class Haelfte:
    """Eine Haelfte des Zeitraums, an ihren Trades gemessen."""

    name: str
    trades: int
    mittel_r: float
    streuung_r: float

    @property
    def sharpe_je_trade(self) -> float:
        return self.mittel_r / self.streuung_r if self.streuung_r > 0 else 0.0

    @property
    def standardfehler(self) -> float:
        return (
            self.streuung_r / np.sqrt(self.trades) if self.trades > 0 else float("inf")
        )

    @property
    def t_wert(self) -> float:
        fehler = self.standardfehler
        return self.mittel_r / fehler if fehler > 0 else 0.0


def teile(trades: list) -> tuple[Haelfte, Haelfte] | None:
    """Die Trades chronologisch halbieren und beide Haelften vermessen.

    **Chronologisch und nicht zufaellig.** Die Frage ist, ob der Vorteil
    *spaeter* noch da war; eine zufaellige Teilung wuerde genau das
    verwischen, was gemessen werden soll.
    """
    if len(trades) < 20:
        return None

    def schluessel(trade) -> object:
        return getattr(trade, "exit_time", None) or getattr(trade, "entry_time", 0)

    geordnet = sorted(trades, key=schluessel)
    mitte = len(geordnet) // 2
    return (
        _vermesse("erste", geordnet[:mitte]),
        _vermesse("zweite", geordnet[mitte:]),
    )


def _vermesse(name: str, trades: list) -> Haelfte:
    werte = np.array([float(getattr(t, "r_multiple", 0.0)) for t in trades])
    return Haelfte(
        name=name,
        trades=len(werte),
        mittel_r=float(np.mean(werte)) if len(werte) else 0.0,
        streuung_r=float(np.std(werte, ddof=1)) if len(werte) > 1 else 0.0,
    )


def erkennbarer_unterschied(
    zweite: Haelfte, *, trennschaerfe: float = TRENNSCHAERFE, irrtum: float = 0.05
) -> float:
    """Welches mittlere R haette in der zweiten Haelfte auffallen koennen?

    Dieselbe Rechnung wie ``vorteilsscan.erkennbare_spanne``, aus demselben
    Grund: Ohne sie heisst ein gescheiterter Stabilitaetstest zweierlei, und
    der Unterschied entscheidet, ob man weitersucht oder aufhoert.
    """
    fehler = zweite.standardfehler
    if not np.isfinite(fehler):
        return float("inf")
    normal = NormalDist()
    return fehler * (normal.inv_cdf(1 - irrtum / 2) + normal.inv_cdf(trennschaerfe))


@dataclass(slots=True)
class Halbierung:
    """Beide Haelften nebeneinander - und was daraus folgt."""

    erste: Haelfte
    zweite: Haelfte

    @property
    def gleiches_vorzeichen(self) -> bool:
        return (self.erste.mittel_r > 0) == (self.zweite.mittel_r > 0)

    @property
    def zweite_traegt(self) -> bool:
        """Ist die zweite Haelfte fuer sich genommen auffaellig positiv?"""
        return self.zweite.mittel_r > 0 and self.zweite.t_wert >= 2.0

    @property
    def aussagekraeftig(self) -> bool:
        """Haette die zweite Haelfte den Effekt der ersten gesehen?

        ``False`` heisst: Der Test hat nichts gefunden, aber er konnte auch
        nichts finden. Dann ist "nicht stabil" **kein Befund**, sondern eine
        fehlende Messung - und diese Unterscheidung ist bei 77 Trades je
        Haelfte der wahrscheinlichere Fall, nicht die Ausnahme.
        """
        return self.erste.mittel_r >= erkennbarer_unterschied(self.zweite)

    @property
    def haelt(self) -> bool:
        return self.gleiches_vorzeichen and self.zweite_traegt

    def tabelle(self) -> str:
        zeilen = [
            f"{'Haelfte':<10} {'Trades':>7} {'Mittel R':>10} {'Streuung':>10} "
            f"{'SR/Trade':>10} {'t':>7}",
            "-" * 58,
        ]
        for h in (self.erste, self.zweite):
            zeilen.append(
                f"{h.name:<10} {h.trades:>7} {h.mittel_r:>10.4f} "
                f"{h.streuung_r:>10.4f} {h.sharpe_je_trade:>10.4f} "
                f"{h.t_wert:>7.2f}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        erkennbar = erkennbarer_unterschied(self.zweite)
        grundlage = (
            f"In der zweiten Haelfte waere ein mittleres R ab {erkennbar:+.4f} "
            f"aufgefallen; die erste hatte {self.erste.mittel_r:+.4f}."
        )

        if self.haelt:
            return (
                f"**Der Vorteil haelt.** Beide Haelften positiv, die zweite "
                f"mit t = {self.zweite.t_wert:+.2f} fuer sich genommen "
                f"auffaellig. Damit besteht der Kandidat dieselbe Huerde, die "
                f"der Vorteilsscan von jedem neuen Fund verlangt."
            )

        if not self.aussagekraeftig:
            return (
                f"**Unentschieden - und das ist die ehrliche Antwort.** Die "
                f"zweite Haelfte zeigt {self.zweite.mittel_r:+.4f} R bei "
                f"t = {self.zweite.t_wert:+.2f}, aber sie ist zu klein, um "
                f"einen Effekt der ersten Haelfte sicher zu sehen. "
                f"{grundlage} Ein gescheiterter Test ohne diese Auskunft waere "
                f"ein Scheinbefund gewesen."
            )

        if not self.gleiches_vorzeichen:
            return (
                f"**Das Vorzeichen dreht.** Erste Haelfte {self.erste.mittel_r:+.4f} R, "
                f"zweite {self.zweite.mittel_r:+.4f} R - und die zweite haette "
                f"einen Effekt dieser Groesse gesehen. {grundlage} Nach dem "
                f"Massstab, den der Vorteilsscan an jeden neuen Fund anlegt, "
                f"waere das kein Fund."
            )

        return (
            f"**Gleiches Vorzeichen, aber die zweite Haelfte traegt nicht "
            f"allein.** {self.zweite.mittel_r:+.4f} R bei t = "
            f"{self.zweite.t_wert:+.2f} - positiv, aber nicht auffaellig. "
            f"{grundlage} Das ist schwaecher als das, was der Vorteilsscan "
            f"von einem neuen Fund verlangt, und staerker als ein Vorzeichen"
            f"wechsel."
        )
