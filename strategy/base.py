"""Strategie-Schnittstelle.

Eine Strategie bekommt pro Kerze einen :class:`BarContext` und gibt entweder
ein Signal zurueck oder nichts. Sie kennt weder Positionsgroessen noch das
Konto - das entscheidet allein der Risk-Officer.

**Schutz gegen Lookahead ist hier eingebaut.** Indikatoren werden einmal ueber
die gesamte Reihe vorberechnet (das ist zulaessig, solange sie kausal sind),
aber der Zugriff laeuft ausschliesslich ueber Methoden, die den aktuellen Index
nicht ueberschreiten koennen. Ein Versuch, in die Zukunft zu greifen, ist ein
Laufzeitfehler statt eines stillen Rechenfehlers, der monatelang unentdeckt
bleibt und die Ergebnisse schoenrechnet.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from core.models import Signal


class LookaheadError(RuntimeError):
    """Eine Strategie hat versucht, Daten aus der Zukunft zu lesen."""


class BarContext:
    """Sicht auf die Zeitreihe bis einschliesslich der aktuellen Kerze.

    ``offset`` zaehlt rueckwaerts: 0 ist die aktuelle (abgeschlossene) Kerze,
    1 die vorherige, und so weiter. Negative Werte gaebe es nicht - sie waeren
    genau der Lookahead, den wir verhindern.
    """

    __slots__ = ("_frame", "_indicators", "_index", "_times", "_arrays")

    def __init__(
        self,
        frame: pd.DataFrame,
        arrays: dict[str, np.ndarray],
        indicators: dict[str, np.ndarray],
        index: int,
    ) -> None:
        self._frame = frame
        self._arrays = arrays
        self._indicators = indicators
        self._index = index
        self._times = arrays["open_time"]

    @property
    def index(self) -> int:
        return self._index

    @property
    def time(self) -> pd.Timestamp:
        """Eroeffnungszeit der aktuellen Kerze."""
        return self._times[self._index]

    def _resolve(self, offset: int) -> int:
        if offset < 0:
            raise LookaheadError(
                f"Negativer Offset {offset} greift auf zukuenftige Kerzen zu. "
                "0 ist die aktuelle Kerze, groessere Werte gehen in die Vergangenheit."
            )
        position = self._index - offset
        if position < 0:
            raise IndexError(
                f"Offset {offset} liegt vor dem Beginn der Zeitreihe (Index {self._index}). "
                "warmup_bars der Strategie zu klein?"
            )
        return position

    # -- Preise --------------------------------------------------------------
    def open(self, offset: int = 0) -> float:
        return float(self._arrays["open"][self._resolve(offset)])

    def high(self, offset: int = 0) -> float:
        return float(self._arrays["high"][self._resolve(offset)])

    def low(self, offset: int = 0) -> float:
        return float(self._arrays["low"][self._resolve(offset)])

    def close(self, offset: int = 0) -> float:
        return float(self._arrays["close"][self._resolve(offset)])

    def volume(self, offset: int = 0) -> float:
        return float(self._arrays["volume"][self._resolve(offset)])

    # -- Indikatoren ---------------------------------------------------------
    def value(self, name: str, offset: int = 0) -> float:
        """Indikatorwert lesen.

        Gibt ``nan`` zurueck, solange der Indikator noch nicht eingeschwungen
        ist. Strategien muessen darauf pruefen - ``warmup_bars`` deckt den
        Regelfall ab, aber nicht jeden Indikator.
        """
        series = self._indicators.get(name)
        if series is None:
            raise KeyError(
                f"Indikator '{name}' nicht vorberechnet. "
                f"Verfuegbar: {sorted(self._indicators)}"
            )
        return float(series[self._resolve(offset)])

    def has(self, name: str) -> bool:
        return name in self._indicators

    def is_ready(self, *names: str) -> bool:
        """Sind alle genannten Indikatoren an dieser Stelle bereits definiert?"""
        return all(not np.isnan(self.value(name)) for name in names)

    def window(self, name: str, length: int) -> np.ndarray:
        """Die letzten ``length`` Werte, aelteste zuerst.

        Gibt bewusst eine Kopie zurueck: Ein versehentliches Schreiben in die
        Sicht wuerde sonst die Indikatorreihe fuer alle folgenden Kerzen
        veraendern - ein besonders schwer zu findender Fehler.
        """
        end = self._index + 1
        start = max(0, end - length)
        source = self._indicators.get(name)
        if source is None:
            source = self._arrays.get(name)
        if source is None:
            raise KeyError(f"Unbekannte Reihe '{name}'")
        return np.array(source[start:end], copy=True)


@runtime_checkable
class Strategy(Protocol):
    """Was eine Strategie koennen muss."""

    strategy_id: str
    warmup_bars: int

    def prepare(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        """Indikatoren einmal ueber die gesamte Reihe berechnen.

        Muss **kausal** sein: Der Wert an Position i darf nur von Kerzen bis
        einschliesslich i abhaengen. Zentrierte gleitende Durchschnitte,
        rueckwaerts gefuellte Werte oder ``shift(-1)`` sind hier verboten -
        sie erzeugen Lookahead, den der ``BarContext`` nicht abfangen kann,
        weil er bereits in den vorberechneten Daten steckt.
        """
        ...

    def on_bar(self, ctx: BarContext) -> Signal | None:
        """Entscheidung zur abgeschlossenen Kerze ``ctx.index``.

        Der zurueckgegebene Einstiegspreis ist ein *Wunsch*: Die Order wird als
        PostOnly-Limit platziert und fuellt nur, wenn der Markt sie erreicht.
        """
        ...


def frame_to_arrays(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    """Wandelt den DataFrame in numpy-Arrays um.

    Der Backtest greift millionenfach auf einzelne Werte zu; ueber
    ``frame.iloc[i]`` waere das um Groessenordnungen langsamer als ueber ein
    rohes Array.
    """
    return {
        "open_time": frame["open_time"].to_numpy(),
        "open": frame["open"].to_numpy(dtype=np.float64),
        "high": frame["high"].to_numpy(dtype=np.float64),
        "low": frame["low"].to_numpy(dtype=np.float64),
        "close": frame["close"].to_numpy(dtype=np.float64),
        "volume": frame["volume"].to_numpy(dtype=np.float64),
    }
