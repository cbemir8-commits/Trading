"""Dieselbe Strategie zweimal laufen lassen - wie im Backtest, wie im Betrieb.

Wozu
----
Alle Zahlen in ``strategies/BEFUND.md`` stammen aus dem Backtest. Gehandelt
wird aber vom Livebetrieb, und der sieht die Welt anders:

    Backtest    einmal ``prepare`` ueber die ganze Historie, dann Balken
                fuer Balken mit wachsendem Index
    Livebetrieb je Kerze ein ``prepare`` ueber die letzten ``BUFFER_BARS``,
                und der Index ist immer der letzte des Puffers

Solange beide dieselben Signale erzeugen, misst der Backtest, was passieren
wird. Tun sie es nicht, misst er etwas anderes - und keine noch so sorgfaeltige
Zulassung haette davon etwas gemerkt.

Warum das nicht durch Zuschauen auffaellt
-----------------------------------------
``research/live_evidenz.py`` hat es ausgerechnet: Bei 17 Trades im Jahr
bliebe selbst ein **vollstaendiger** Verlust des Vorteils drei Jahre lang
unentdeckt. Ein Unterschied zwischen Backtest und Betrieb wuerde im
Demobetrieb also nicht auffallen - er muss vorher gefunden werden, durch
Vergleich, nicht durch Beobachtung.

Was der Vergleich gefunden hat
------------------------------
Die Sperrfrist (``cooldown_bars``) rechnete mit dem Index **im aktuellen
Rahmen**. Im Backtest waechst der von 0 bis ans Ende, im Betrieb steht er bei
vollem Puffer fest auf ``BUFFER_BARS - 1``. Ab dem ersten Trade galt dort
also immer ``index - letzter_einstieg == 0``, und die Sperrfrist lief nie ab:
Der Roboter haette nach seinem ersten Trade **nie wieder** eingestiegen.

Der Spitzenkandidat handelt ohne Sperrfrist und war nicht betroffen. Das ist
Glueck, kein Verdienst - die Sperrfrist war eine der zehn gemessenen
Richtungen und haette ebenso gut gewinnen koennen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import structlog

from core.models import Side
from strategy.base import BarContext, frame_to_arrays

log = structlog.get_logger(__name__)

#: Muss dem Wert in ``execution/live.py`` entsprechen. Bewusst hier
#: gespiegelt statt importiert: Der Vergleich soll auch dann noch etwas
#: aussagen, wenn dort jemand die Zahl aendert - dann faellt es hier auf.
BUFFER_BARS = 2000


@dataclass(frozen=True, slots=True)
class Abweichung:
    """Ein Balken, an dem sich die beiden Laeufe uneinig sind."""

    index: int
    zeit: pd.Timestamp
    backtest: str
    livebetrieb: str

    def __str__(self) -> str:
        return (
            f"{self.zeit:%Y-%m-%d %H:%M}  Backtest {self.backtest:<8} "
            f"Betrieb {self.livebetrieb}"
        )


@dataclass(slots=True)
class Vergleich:
    """Was beim Nebeneinanderlegen herauskam."""

    balken: int = 0
    signale_backtest: int = 0
    signale_livebetrieb: int = 0
    abweichungen: list[Abweichung] = field(default_factory=list)

    @property
    def einig(self) -> bool:
        return not self.abweichungen

    def bericht(self) -> str:
        if self.einig:
            return (
                f"Einig ueber {self.balken} Balken - "
                f"{self.signale_backtest} Signale, identisch."
            )
        return (
            f"{len(self.abweichungen)} Abweichungen ueber {self.balken} Balken. "
            f"Backtest {self.signale_backtest} Signale, "
            f"Betrieb {self.signale_livebetrieb}.\n"
            + "\n".join(f"  {a}" for a in self.abweichungen[:10])
        )


def _beschreibe(signal) -> str:
    if signal is None:
        return "-"
    return "long" if signal.side is Side.BUY else "short"


def signale_backtest(frame: pd.DataFrame, build_strategy) -> list:
    """Signale so, wie der Backtest sie erzeugt.

    Ein ``prepare`` ueber alles, dann laufender Index. Das ist die Sicht, aus
    der alle Kennzahlen im BEFUND stammen.
    """
    strategy = build_strategy()
    arrays = frame_to_arrays(frame)
    indicators = strategy.prepare(frame)

    signale = []
    for i in range(len(frame)):
        if i <= strategy.warmup_bars:
            signale.append(None)
            continue
        signale.append(strategy.on_bar(BarContext(frame, arrays, indicators, i)))
    return signale


def signale_livebetrieb(
    frame: pd.DataFrame, build_strategy, *, buffer_bars: int = BUFFER_BARS
) -> list:
    """Signale so, wie der Livebetrieb sie erzeugt.

    Je Balken ein frischer Ausschnitt der letzten ``buffer_bars`` Kerzen, ein
    ``prepare`` darueber, und der Index am Ende des Ausschnitts - genau das,
    was ``LiveTrader._look_for_entry`` tut.

    Deutlich langsamer als der Backtest, weil die Indikatoren je Balken neu
    gerechnet werden. Das ist der Preis dafuer, den Betrieb nachzustellen
    statt ihn nachzuahmen.
    """
    strategy = build_strategy()

    signale = []
    for i in range(len(frame)):
        beginn = max(0, i - buffer_bars + 1)
        puffer = frame.iloc[beginn : i + 1].reset_index(drop=True)
        if len(puffer) <= strategy.warmup_bars:
            signale.append(None)
            continue
        arrays = frame_to_arrays(puffer)
        indicators = strategy.prepare(puffer)
        ctx = BarContext(puffer, arrays, indicators, len(puffer) - 1)
        signale.append(strategy.on_bar(ctx))
    return signale


def vergleiche(
    frame: pd.DataFrame,
    build_strategy,
    *,
    buffer_bars: int = BUFFER_BARS,
    max_abweichungen: int = 200,
) -> Vergleich:
    """Beide Laeufe nebeneinanderlegen.

    Gibt zurueck, an welchen Balken sie sich uneinig sind. Ein leeres
    Ergebnis ist die Aussage, auf die es ankommt: Der Backtest misst das, was
    im Betrieb passieren wird.
    """
    a = signale_backtest(frame, build_strategy)
    b = signale_livebetrieb(frame, build_strategy, buffer_bars=buffer_bars)

    ergebnis = Vergleich(balken=len(frame))
    ergebnis.signale_backtest = sum(1 for s in a if s is not None)
    ergebnis.signale_livebetrieb = sum(1 for s in b if s is not None)

    zeiten = frame["open_time"]
    for i, (links, rechts) in enumerate(zip(a, b, strict=True)):
        if _beschreibe(links) == _beschreibe(rechts):
            continue
        if len(ergebnis.abweichungen) < max_abweichungen:
            ergebnis.abweichungen.append(
                Abweichung(
                    index=i,
                    zeit=zeiten.iloc[i],
                    backtest=_beschreibe(links),
                    livebetrieb=_beschreibe(rechts),
                )
            )

    log.info(
        "replay.verglichen",
        balken=ergebnis.balken,
        abweichungen=len(ergebnis.abweichungen),
        einig=ergebnis.einig,
    )
    return ergebnis
