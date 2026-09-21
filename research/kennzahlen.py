"""Kennzahlen, die es auf dieser Reihe gar nicht gibt - Befund 326.

Der Anlass
----------
Befund 322 hat 33 Regeln gefunden, die **null Mal gehandelt** haben und
trotzdem je fuenf von elf Gates gutgeschrieben bekamen. Befund 323 hat die
Zahl auf 14 berichtigt: neunzehn davon waren Viertelstundenregeln, die die
Wache aus Befund 217 heute ueberspringt. Der Rest stand als offene Frage im
Register:

    zwoelf davon aus Generationen ohne vermerkte Kerzenlaenge (1, 2, 4)

Das klang nach **einer** Frage - einer fehlenden Zeile in ``VORGESEHEN``.
Gemessen sind es zwei, und nur eine davon hat mit Kerzenlaengen zu tun:

    Gen  vorg  auf D: Kandidaten/Regeln  Trades   auf 15: Kand/Regeln  Trades
      1  None            1/5                  6          5/5             670
      2  None            0/5                  0          5/5            1444
      4  None            0/3                  0          0/3               0

Generation 2 schweigt auf Tageskerzen und handelt auf Viertelstunden - der
Fingerabdruck von Generation 8 aus Befund 170. **Generation 4 schweigt auf
beiden.** Eine Kerzenlaenge kann das nicht erklaeren, und keine Zeile in
``VORGESEHEN`` kann es heilen.

Woran es liegt
--------------
Alle drei Regeln der Generation 4 stuetzen sich auf die Finanzierungsrate:

    Ausbruch ohne Long-Ueberhitzung    Filter  funding_zscore(90) < 1,5
    Funding-Carry Long                 Einstieg funding_avg(21)   < 0
    Gegen die ueberhitzte Long-Seite   Einstieg funding_zscore(90) > 2

Gemessen wird auf ``BTCUSD_BITSTAMP`` und ``ETHUSD_BITSTAMP`` - **Kassamarkt**,
und dort gibt es keine Finanzierungsrate. Beide Kennzahlen sind auf allen 5355
Tagesbalken leer. Jeder Vergleich mit ``NaN`` ist falsch, also loest nichts
aus.

Am schaerfsten ist der erste Fall. Sein Einstieg ist ein schlichter
Donchian-50-Ausbruch, derselbe wie in Generation 2, und der handelt
nachweislich. Null Trades kommen allein aus dem **Filter**: Geschrieben ist
er, um eine *ungewoehnliche* Lage auszuschliessen - "nur wenn die Longs nicht
ueberhitzt sind". Wo die Zahl fehlt, schliesst er **jeden** Balken aus. Eine
fehlende Angabe liest sich als Ablehnung; genau davor warnt schon
``passt_zum_intervall`` seit Befund 184, nur eben fuer Kerzenlaengen.

Warum das den Deflated Sharpe angeht
------------------------------------
Aus Befund 170, ueber dieselbe Bauart: *"jede gewertete Regel ist ein
Versuch"*. Eine Regel, die auf dieser Reihe nichts ausloesen **kann**, kostet
trotzdem einen Versuch, und Versuche heben die Huerde des Deflated Sharpe fuer
alle anderen. Das ist das Gate, an dem das Projekt steht.

Was dieses Modul tut
--------------------
Es fragt vor dem Lauf, welche Kennzahlen ein Genom braucht und welche davon
auf dieser Reihe durchweg leer sind. Gerechnet wird mit
``compile_genome(...).prepare(frame)`` - **derselbe** Aufruf, den der Backtest
macht. Befund 170 hat sich einmal daran verhoben, die Pruefung anders zu
rechnen als die Messung; dann prueft sie eine andere Frage.

Was es **nicht** tut
--------------------
**Es urteilt nicht ueber Regeln.** Leer heisst "auf dieser Reihe nicht zu
haben" und nicht "schlecht". Dieselben drei Regeln der Generation 4 sind am
Perpetual-Betriebspunkt mit echten Finanzierungsdaten eine offene Frage - und
zwar eine, die sich messen laesst, sobald die Daten da sind.

**Es misst keine Anlaufzeit.** Jede Kennzahl ist am Anfang ihrer Reihe leer,
solange ihr Fenster nicht voll ist. Gefragt ist ``durchweg`` leer: kein
einziger Wert auf der ganzen Reihe. Alles andere waere eine Warnung, die immer
angeht - und die ist keine (Befund 324).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy.compiler import compile_genome
from strategy.genome import Genome

__all__ = ["Lage", "gebrauchte_kennzahlen", "lage", "stumme"]


@dataclass(frozen=True, slots=True)
class Lage:
    """Welche Kennzahlen ein Genom braucht - und welche die Reihe nicht hat."""

    genom: str
    gebraucht: tuple[str, ...]
    leer: tuple[str, ...]

    @property
    def stumm(self) -> bool:
        """Kann dieses Genom auf dieser Reihe ueberhaupt ausloesen?

        **Nein heisst hier "nachweislich nicht"** und nicht "wahrscheinlich
        nicht": Fehlt auch nur eine gebrauchte Kennzahl vollstaendig, ist
        jeder Vergleich mit ihr falsch. Ob eine *vorhandene* Kennzahl je die
        Schwelle reisst, ist eine andere Frage - die beantwortet nur ein Lauf.
        """
        return bool(self.leer)

    def satz(self) -> str:
        if self.leer:
            return (
                f"{self.genom}: {', '.join(self.leer)} "
                f"{'ist' if len(self.leer) == 1 else 'sind'} auf dieser Reihe "
                f"durchweg leer - die Regel kann hier nicht ausloesen"
            )
        if not self.gebraucht:
            return f"{self.genom}: braucht keine Kennzahl, nur den Kurs"
        if len(self.gebraucht) == 1:
            return f"{self.genom}: die eine gebrauchte Kennzahl liegt vor"
        return f"{self.genom}: alle {len(self.gebraucht)} Kennzahlen liegen vor"


def gebrauchte_kennzahlen(genom: Genome) -> tuple[str, ...]:
    """Die Kennzahl-Schluessel, auf die sich dieses Genom stuetzt.

    Preisoperanden und Konstanten bleiben draussen: ``close`` ist auf jeder
    Kerzenreihe da, und eine Konstante ist keine Messung.
    """
    schluessel = {
        operand.key
        for bedingung in genom.all_conditions
        for operand in (bedingung.left, bedingung.right)
        if operand.kind == "indicator"
    }
    return tuple(sorted(schluessel))


def lage(genom: Genome, daten: pd.DataFrame) -> Lage:
    """Welche Kennzahlen dieses Genom auf dieser Reihe nicht bekommt."""
    gebraucht = gebrauchte_kennzahlen(genom)
    if not gebraucht:
        return Lage(genom=genom.name, gebraucht=(), leer=())

    # **Derselbe Aufruf wie im Backtest.** ``prepare`` legt zusaetzlich den
    # ATR fuer den Stop an; der bleibt hier draussen, weil ``gebraucht`` nur
    # die Kennzahlen der Bedingungen nennt - wonach gefragt ist, ist, ob eine
    # Regel ausloesen kann.
    reihen = compile_genome(genom).prepare(daten)
    leer = tuple(k for k in gebraucht if _durchweg_leer(reihen.get(k)))
    return Lage(genom=genom.name, gebraucht=gebraucht, leer=leer)


def _durchweg_leer(reihe: np.ndarray | None) -> bool:
    """Kein einziger Wert auf der ganzen Reihe.

    ``None`` heisst, ``prepare`` hat den Schluessel nicht angelegt - dann ist
    er auch nicht zu haben.
    """
    if reihe is None:
        return True
    werte = np.asarray(reihe, dtype=float)
    return werte.size == 0 or bool(np.isnan(werte).all())


def stumme(genome: list[Genome], daten: pd.DataFrame) -> tuple[Lage, ...]:
    """Die Genome, die auf dieser Reihe nachweislich nicht ausloesen koennen.

    In der Reihenfolge, in der sie hereinkommen - das ist die Reihenfolge des
    Katalogs, und wer sie liest, sucht dort nach.
    """
    return tuple(x for x in map(lambda g: lage(g, daten), genome) if x.stumm)
