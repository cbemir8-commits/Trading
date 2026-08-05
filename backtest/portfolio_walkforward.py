"""Mehrere Maerkte als **ein** Kandidat durch den Walk-Forward.

Warum das der wirksamste Schritt war
------------------------------------
Die Zulassung kannte bisher nur einen Markt. Gemessen wurde deshalb immer
BTC allein oder ETH allein - und beide scheiterten unter anderem am
Rueckgang-Gate. Das Doppel aus beiden liegt bei 11,0 % Rueckgang und waere
damit **unter** der Schwelle von 12 %, war aber nie durch die Gates gelaufen,
weil es die Maschinerie dafuer nicht gab.

Das ist keine Lockerung. Gehandelt wuerde ohnehin das Doppel - die Zulassung
prueft jetzt endlich das, was tatsaechlich laufen soll, statt einer Haelfte
davon. Die Schwellen bleiben, wo sie sind.

Wie zusammengelegt wird
-----------------------
Alle Maerkte laufen ueber **dieselben** Fenster - moeglich, weil sie vorher
auf den gemeinsamen Zeitraum zugeschnitten werden. Je Fenster entsteht dann
ein gemeinsames Ergebnis:

    Kapitalkurve   gewichtete Summe der Einzelkurven, auf der Zeitachse
                   ausgerichtet und vorwaerts gefuellt
    Trades         Vereinigung; jeder Trade traegt sein Symbol
    Kennzahlen     aus beidem, wie bei einem Markt

Danach ist das Ergebnis ein ganz normaler ``WalkForwardReport``. Alle elf
Gates laufen unveraendert darauf - kein Gate musste angefasst werden, um das
Portfolio bewerten zu koennen.

Mehr Maerkte sind nicht besser - gemessen
-----------------------------------------
Die naheliegende Fortsetzung war, weitere Maerkte dazuzunehmen, um Rueckgang
und Monte-Carlo zu entspannen. Das Gegenteil trat ein. Dieselbe Regel, alle
auf 11,4 % Rueckgang gebracht, 2017-08 bis 2026-08:

    BTC+ETH       +117,0 %   Sharpe 1,29   Monte-Carlo 19,7 %
    +LTC           +74,6 %   Sharpe 0,97   Monte-Carlo 34,3 %
    +XRP           +81,3 %   Sharpe 0,92   Monte-Carlo 46,0 %

Streuung senkt den Rueckgang nur, wenn die dazugenommenen Maerkte fuer sich
genommen etwas taugen. LTC und XRP tun das unter dieser Regel nicht - sie
bringen Trades mit, aber schlechtere, und die Monte-Carlo-Simulation findet
entsprechend mehr Spielraum fuer eine unguenstige Reihenfolge.

Wer diese Richtung erneut probiert, sollte zuerst jeden Markt **einzeln**
messen. Ein Markt, der allein nichts taugt, rettet kein Portfolio.

Was dabei ehrlich bleiben muss
------------------------------
Zwei Trades auf zwei Maerkten zur selben Zeit sind **nicht** zwei unabhaengige
Beobachtungen. Faellt der Markt, fallen beide. Jede Kennzahl, die Trades als
unabhaengig behandelt, wird dadurch zu optimistisch - allen voran die
Monte-Carlo-Simulation, die die Reihenfolge vertauscht und dabei gleichzeitige
Verluste auseinanderzieht. Deshalb bekommt sie fuer Portfolios eine
Blockvariante (siehe ``research.gates.gate_monte_carlo``), die zeitgleiche
Trades zusammenhaelt.

Die Zahl der Trades verdoppelt sich hier also, die Zahl der **unabhaengigen**
Beobachtungen nicht.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import structlog

from backtest.engine import BacktestConfig
from backtest.metrics import compute_metrics
from backtest.walkforward import (
    WalkForwardReport,
    WalkForwardSplitter,
    WindowResult,
    _combine,
    run_walkforward,
)
from core.models import Trade

log = structlog.get_logger(__name__)


def common_range(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Alle Maerkte auf den Zeitraum zuschneiden, den jeder abdeckt.

    Ohne den Schnitt erzeugt der Splitter je Markt andere Fenster, und die
    Zusammenlegung legt Fenster verschiedener Jahre uebereinander.
    """
    if not frames:
        return {}
    von = max(f["open_time"].iloc[0] for f in frames.values() if not f.empty)
    bis = min(f["open_time"].iloc[-1] for f in frames.values() if not f.empty)
    return {
        name: f[(f["open_time"] >= von) & (f["open_time"] <= bis)].reset_index(drop=True)
        for name, f in frames.items()
    }


def run_portfolio_walkforward(
    frames: dict[str, pd.DataFrame],
    build_strategy,
    configs: dict[str, BacktestConfig] | BacktestConfig,
    splitter: WalkForwardSplitter | None = None,
    *,
    weights: dict[str, float] | None = None,
    initial_equity: Decimal | None = None,
) -> WalkForwardReport:
    """Mehrere Maerkte zu einem Walk-Forward-Ergebnis zusammenlegen.

    Das Ergebnis ist von einem einzelnen Markt nicht zu unterscheiden und
    laeuft durch dieselben Gates.
    """
    if not frames:
        return WalkForwardReport()

    zugeschnitten = common_range(frames)
    splitter = splitter or WalkForwardSplitter()

    def config_fuer(name: str) -> BacktestConfig:
        return configs[name] if isinstance(configs, dict) else configs

    gewichte = weights or {name: 1.0 for name in zugeschnitten}
    summe = sum(gewichte.get(name, 0.0) for name in zugeschnitten)
    if summe <= 0:
        raise ValueError("Die Gewichte summieren sich auf null")

    einzeln: dict[str, WalkForwardReport] = {}
    for name, frame in zugeschnitten.items():
        bericht = run_walkforward(
            frame, build_strategy, config_fuer(name), splitter
        )
        if bericht.windows:
            einzeln[name] = bericht
        else:
            log.warning("portfolio.markt_ohne_fenster", markt=name)

    if not einzeln:
        return WalkForwardReport()

    start = (
        initial_equity
        if initial_equity is not None
        else config_fuer(next(iter(einzeln))).initial_equity
    )

    # Fenster nach Index zusammenfuehren. Nur Fenster, die **jeder** Markt
    # geliefert hat - ein Fenster mit nur der Haelfte der Maerkte waere ein
    # anderes Portfolio und wuerde den Rueckgang dort kuenstlich erhoehen.
    gemeinsame = sorted(
        set.intersection(
            *({w.window.index for w in b.windows} for b in einzeln.values())
        )
    )
    if not gemeinsame:
        log.warning("portfolio.keine_gemeinsamen_fenster")
        return WalkForwardReport()

    report = WalkForwardReport()
    for index in gemeinsame:
        zusammengelegt = _fenster_zusammenlegen(
            {name: _fenster(b, index) for name, b in einzeln.items()},
            gewichte=gewichte,
            summe=summe,
            initial_equity=start,
        )
        report.windows.append(zusammengelegt)
        report.all_trades.extend(zusammengelegt.trades)

    report.combined = _combine(report.windows, start)
    log.info(
        "portfolio.fertig",
        maerkte=sorted(einzeln),
        zusammenfassung=report.summary(),
    )
    return report


def _fenster(report: WalkForwardReport, index: int) -> WindowResult:
    for w in report.windows:
        if w.window.index == index:
            return w
    raise KeyError(f"Fenster {index} fehlt")


def _fenster_zusammenlegen(
    teile: dict[str, WindowResult],
    *,
    gewichte: dict[str, float],
    summe: float,
    initial_equity: Decimal,
) -> WindowResult:
    """Ein Fenster ueber alle Maerkte zu einem Ergebnis machen."""
    erster = next(iter(teile.values()))

    trades: list[Trade] = []
    for teil in teile.values():
        trades.extend(teil.trades)
    trades.sort(key=lambda t: t.exit_time)

    kurve = _kurven_summieren(
        {name: teil.result.equity_curve for name, teil in teile.items()},
        gewichte=gewichte,
        summe=summe,
        initial_equity=initial_equity,
    )

    metrics = compute_metrics(
        trades,
        kurve,
        initial_equity=initial_equity,
        total_fees=sum((t.fees for t in trades), Decimal(0)),
        total_funding=sum((t.funding for t in trades), Decimal(0)),
    )

    return WindowResult(
        window=erster.window,
        metrics=metrics,
        trades=trades,
        result=_result_zusammenlegen(teile, kurve, trades),
    )


def _result_zusammenlegen(
    teile: dict[str, WindowResult], kurve: pd.DataFrame, trades: list[Trade]
):
    """Ein BacktestResult, das das Fenster ueber alle Maerkte beschreibt.

    ``_combine`` liest die Kapitalkurve aus ``window.result``, nicht aus den
    Kennzahlen. Ohne diesen Austausch verkettete es die Kurve des **ersten**
    Marktes und das Gesamtergebnis waere das eines Einzelmarktes - mit den
    Trades beider. Genau die Art Fehler, die niemandem auffaellt, weil das
    Ergebnis plausibel aussieht.

    Die Ablehnungszaehler werden aufaddiert. Sonst verschwaende eine an einer
    Kontraktgrenze gescheiterte ETH-Order in der Statistik, weil nur BTCs
    Zaehler durchgereicht wuerde.
    """
    from copy import copy

    erster = next(iter(teile.values()))
    kopie = copy(erster.result)
    kopie.equity_curve = kurve
    kopie.trades = list(trades)

    gruende: dict[str, int] = {}
    for teil in teile.values():
        for grund, anzahl in teil.result.rejections.items():
            gruende[grund] = gruende.get(grund, 0) + anzahl
    kopie.rejections = gruende
    kopie.signals_generated = sum(t.result.signals_generated for t in teile.values())
    kopie.entries_filled = sum(t.result.entries_filled for t in teile.values())
    kopie.entries_expired = sum(t.result.entries_expired for t in teile.values())
    return kopie


def _kurven_summieren(
    kurven: dict[str, pd.DataFrame],
    *,
    gewichte: dict[str, float],
    summe: float,
    initial_equity: Decimal,
) -> pd.DataFrame:
    """Kapitalkurven mehrerer Maerkte gewichtet zu einer machen.

    Jede Kurve wird auf ihren eigenen Startwert normiert - sonst bekaeme ein
    Markt, dessen Kurve zufaellig hoeher beginnt, mehr Gewicht als ihm
    zusteht. Ausgerichtet wird auf die Vereinigung aller Zeitpunkte, Luecken
    werden vorwaerts gefuellt: Ein Markt ohne neue Kerze hat nicht null
    Kapital, sondern unveraendertes.
    """
    brauchbar = {n: k for n, k in kurven.items() if not k.empty}
    if not brauchbar:
        return pd.DataFrame({"time": [], "equity": []})

    start = float(initial_equity)
    reihen = []
    for name, kurve in brauchbar.items():
        anteil = gewichte.get(name, 0.0) / summe
        basis = float(kurve["equity"].iloc[0])
        if basis <= 0:
            continue
        reihe = pd.Series(
            kurve["equity"].to_numpy(dtype=float) / basis * anteil,
            index=pd.DatetimeIndex(kurve["time"]),
            name=name,
        )
        # Doppelte Zeitstempel koennen entstehen, wenn mehrere Ereignisse auf
        # dieselbe Kerze fallen. Der letzte Stand gilt.
        reihen.append(reihe[~reihe.index.duplicated(keep="last")])

    if not reihen:
        return pd.DataFrame({"time": [], "equity": []})

    # ``sort`` ausdruecklich setzen: Ohne Angabe warnt pandas, dass sich das
    # Standardverhalten aendert - und unter den Testeinstellungen ist eine
    # Warnung ein Fehler. Sortiert wird hier ohnehin nach Zeit.
    tabelle = pd.concat(reihen, axis=1, sort=True).sort_index().ffill().bfill()
    gesamt = tabelle.sum(axis=1) * start

    return pd.DataFrame({"time": gesamt.index, "equity": gesamt.to_numpy()})
