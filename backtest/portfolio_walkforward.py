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

from dataclasses import replace
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
    strategie_je_fenster=None,
    kapital_teilen: bool = False,
) -> WalkForwardReport:
    """Mehrere Beine zu einem Walk-Forward-Ergebnis zusammenlegen.

    Ein **Bein** ist ein Datensatz mit einer Regel darauf. Meist ist das ein
    Markt, es muss aber keiner sein: ``build_strategy`` darf eine Zuordnung
    Bein -> Bauplan sein, und dann kann derselbe Markt mehrfach vorkommen,
    einmal je Regelvariante.

    Das ist kein Kunstgriff, sondern der Zweck: Wer eine Trendfolge mit 30,
    50 und 80 Tagen gleichzeitig zu je einem Drittel handelt, bekommt drei
    leicht verschobene Einstiegszeitpunkte statt eines einzigen. Genau daran
    haengt, wie stark das Gesamtergebnis von wenigen Trades abhaengt.

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

    def bauplan_fuer(name: str):
        if isinstance(build_strategy, dict):
            if name not in build_strategy:
                raise KeyError(f"Kein Bauplan fuer Bein {name}")
            return build_strategy[name]
        return build_strategy

    einzeln: dict[str, WalkForwardReport] = {}
    for name, frame in zugeschnitten.items():
        konfiguration = config_fuer(name)
        if kapital_teilen:
            # **Jedes Bein bekommt seinen Anteil am Kapital, nicht alles.**
            #
            # Sonst rechnet die Groessenlogik mit Geld, das dem Bein gar nicht
            # zur Verfuegung steht. Fuer Gewinne faellt das nicht auf - die
            # werden hinterher gewichtet und kuerzen sich heraus. Fuer die
            # **Mindestmenge der Boerse** faellt es sehr wohl auf, denn die
            # laesst sich nicht halbieren.
            #
            # Gemessen am Spitzenkandidaten, 500 EUR auf zwei Maerkte:
            #
            #     je Bein 500 EUR   154 Trades,  18 auf der Mindestmenge
            #     je Bein 250 EUR   136 Trades,  45 auf der Mindestmenge,
            #                                    18 gar nicht handelbar
            #
            # Der Unterschied ist kein Strategieproblem, sondern ein
            # Kontogroessenproblem - aber er gehoert gemessen, bevor echtes
            # Geld darauf gesetzt wird.
            anteil = gewichte.get(name, 0.0) / summe
            konfiguration = replace(
                konfiguration,
                initial_equity=konfiguration.initial_equity * Decimal(str(anteil)),
            )
        bericht = run_walkforward(
            frame, bauplan_fuer(name), konfiguration, splitter,
            strategie_je_fenster=strategie_je_fenster,
        )
        if bericht.windows:
            einzeln[name] = bericht
        else:
            log.warning("portfolio.bein_ohne_fenster", bein=name)

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
    # Die Fenstergewinne je Bein mitgeben. Ohne sie kann das
    # Deflated-Sharpe-Gate nicht erkennen, dass drei fast gleiche Regeln keine
    # drei unabhaengigen Beobachtungsreihen sind.
    report.beine = {
        name: [float(_fenster(b, i).metrics.net_profit) for i in gemeinsame]
        for name, b in einzeln.items()
    }
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

    # Trades auf das Gewicht des Beins bringen.
    #
    # Jedes Bein laeuft im Backtest mit dem **vollen** Startkapital, im
    # Portfolio hat es aber nur seinen Anteil. Ungeskaliert tragen die Trades
    # damit ein Vielfaches ihres wirklichen Gewichts - bei zwei Beinen das
    # Doppelte, bei sechs das Sechsfache.
    #
    # Aufgefallen ist es an einer Zahl, die nicht sein konnte: Die
    # Kapitalkurve meldete 8,5 % Rueckgang, die Monte-Carlo-Simulation aus
    # denselben Trades 62 %. Die Kurve war richtig gewichtet, die Trades
    # nicht - und die Simulation liest die Trades.
    #
    # Menge und Gewinn werden mit demselben Faktor skaliert. Das R-Vielfache
    # bleibt dadurch unveraendert, denn es ist Gewinn geteilt durch
    # (Stopabstand mal Menge) - genau die Probe, dass die Skalierung sauber
    # ist und keine Kennzahl verschiebt, die sie nicht verschieben darf.
    trades: list[Trade] = []
    for name, teil in teile.items():
        anteil = gewichte.get(name, 0.0) / summe
        trades.extend(_trade_skalieren(t, anteil) for t in teil.trades)
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


def _trade_skalieren(trade: Trade, anteil: float) -> Trade:
    """Einen Trade auf den Kapitalanteil seines Beins bringen.

    Preise und Zeiten bleiben, Menge und Geldbetraege werden skaliert. Ein
    Anteil von 1,0 gibt den Trade unveraendert zurueck - der Einzelmarktfall
    aendert sich dadurch nicht.
    """
    if anteil == 1.0:
        return trade
    faktor = Decimal(str(anteil))
    return trade.model_copy(
        update={
            "qty": trade.qty * faktor,
            "gross_pnl": trade.gross_pnl * faktor,
            "fees": trade.fees * faktor,
            "funding": trade.funding * faktor,
        }
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
