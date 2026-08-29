"""Walk-Forward-Auswertung.

Ein einzelner Backtest ueber sechs Jahre sagt wenig: Er zeigt, ob eine
Strategie *irgendwann* funktioniert hat, nicht ob sie *durchgehend*
funktioniert. Der Walk-Forward zerlegt den Zeitraum in aufeinanderfolgende
Fenster und wertet jedes einzeln aus. Eine Strategie, die in zwei von acht
Fenstern glaenzt und in sechs verliert, faellt hier auf - im Gesamtergebnis
wuerde sie moeglicherweise profitabel aussehen.

Zwei Feinheiten, die ueber die Aussagekraft entscheiden:

**Aufwaermdaten aus der Vergangenheit.** Jedes Testfenster braucht Kerzen
*vor* seinem Beginn, damit die Indikatoren eingeschwungen sind. Ohne sie waeren
die ersten 50 bis 600 Kerzen jedes Fensters signallos - die Strategie wuerde
systematisch zu wenige Trades machen, und zwar genau am Fensteranfang. Die
Aufwaermdaten kommen aus dem Zeitraum davor, aber es werden **nur Trades
gezaehlt, die im Testfenster eroeffnet wurden**.

**Sperrzone (Embargo).** Zwischen Trainings- und Testzeitraum bleibt eine
Luecke. Ein Trade, der kurz vor dem Schnitt eroeffnet wurde, laeuft sonst in
den Testzeitraum hinein und verbindet beide - genau die Vermischung, die der
Walk-Forward verhindern soll.

**Nachlauf am Fensterende.** Eine dritte, und sie ist teuer erkauft. Der
Backtest lief frueher exakt bis ``test_end``; eine dort noch offene Position
wurde zwangsweise glattgestellt (``END_OF_DATA``). Beim Spitzenkandidaten traf
das **25 von 154 Trades**, und diese 25 trugen den gesamten Vorteil:

    am Kalender beendet   25 Trades   +19,62 EUR im Mittel   26 Tage gehalten
    nach Regel beendet   129 Trades    -0,59 bis -2,11 EUR    6 Tage gehalten

Der Ausstieg der Gewinner kam also vom **Kalender**, nicht von der Regel - und
im Betrieb gibt es keinen Kalender, der eine Position schliesst. Gemessen
wurde etwas, das so nie gehandelt wuerde.

Deshalb bekommt jedes Fenster einen Nachlauf: Der Backtest laeuft ueber
``test_end`` hinaus, bis die im Fenster eroeffneten Trades ihren Ausstieg nach
Regel gefunden haben. **Gezaehlt werden weiterhin nur Trades, die im
Testfenster eroeffnet wurden** - der Nachlauf verschiebt keinen einzigen
Einstieg, er laesst nur zu Ende laufen, was begonnen hat.

Kein Blick in die Zukunft: Die Regel entscheidet auf jeder Kerze nur aus der
Vergangenheit, und der Nachlauf liegt **hinter** dem Testfenster, also erst
recht hinter dem Training. Was er kostet, ist nichts; was er aendert, ist die
Ehrlichkeit der Ausstiege.

Die **Kapitalkurve** bleibt auf das Fenster begrenzt. Sonst ueberlappten sich
die Kurven benachbarter Fenster, und die Verkettung zaehlte dieselbe Bewegung
zweimal. Am Fensterende steht dort also weiterhin der Marktwert einer
womoeglich offenen Position - genau das, was ein Kontoauszug an dem Tag zeigte.

**Durchgehender Lauf.** Der Nachlauf hat das eine Fensterende geheilt; am
anderen blieb ein groesserer Schaden. Jedes Fenster ist ein eigener Backtest
und beginnt deshalb **flach**, ohne Position. Fuer eine Trendfolge ist das
ruinoes, weil ihr Einstieg ein *Kreuzen* verlangt: Wer beim Fensterstart schon
im Trend ist, bekommt kein Signal mehr und muss warten, bis der Kurs unter den
Schnitt faellt und wieder darueber. Gemessen auf BTC + ETH, 62 Fenster:

    Fenster mit Start ueber dem 50-Tage-Schnitt      31 von 62   (50 %)
    Wartezeit bis zum naechsten Kreuzen              Median 44 von 89 Tagen
    Fenster, die dabei komplett aussetzen             4
    Anteil aller Testtage ohne Position, obwohl
    die Regel investiert waere                       26,3 %

Ein Viertel der Marktzeit wurde nie gemessen - und zwar bevorzugt die Zeit
*innerhalb* bestehender Trends, also genau die, in der eine Trendfolge
verdient.

``durchgehend=True`` laeuft deshalb **einen** Backtest ueber die ganze
Teststrecke. Die Fenster ordnen dann nur noch zu, welcher Trade zu welchem
Abschnitt gehoert; eine Position darf ueber die Grenze hinweg bestehen
bleiben, so wie im Betrieb. Vor dem ersten Testfenster wird nicht gehandelt -
dort beginnt das Konto zu Recht flach.

Das geht nur bei einer **festen** Regel: Wer ``strategie_je_fenster`` benutzt,
laesst die Regel je Fenster neu bestimmen, und eine Position ueber die Grenze
zu tragen hiesse, sie unter einer Regel zu eroeffnen und unter einer anderen
zu schliessen. Der Aufruf wird deshalb abgelehnt statt still umgangen.
"""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import structlog

from backtest.engine import BacktestConfig, Backtester, BacktestResult
from backtest.metrics import Metrics, compute_metrics
from core.models import Trade
from strategy.base import Strategy

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Window:
    """Ein Walk-Forward-Fenster."""

    index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime

    def describe(self) -> str:
        return (
            f"Fenster {self.index}: Training {self.train_start:%Y-%m} bis "
            f"{self.train_end:%Y-%m}, Test {self.test_start:%Y-%m-%d} bis "
            f"{self.test_end:%Y-%m-%d}"
        )


@dataclass(slots=True)
class WindowResult:
    window: Window
    metrics: Metrics
    trades: list[Trade]
    result: BacktestResult

    @property
    def is_profitable(self) -> bool:
        return self.metrics.net_profit > 0


@dataclass(slots=True)
class WalkForwardReport:
    """Gesamtergebnis ueber alle Fenster."""

    windows: list[WindowResult] = field(default_factory=list)
    combined: Metrics | None = None
    all_trades: list[Trade] = field(default_factory=list)

    beine: dict[str, list[float]] = field(default_factory=dict)
    """Fenstergewinne je Bein - noetig, um die **effektive** Stichprobe zu
    bestimmen.

    Das Deflated-Sharpe-Gate zaehlte rohe Trades. Wer dieselbe Regel mit drei
    Perioden gleichzeitig handelt, verdreifacht die Zahl, ohne dreimal so viel
    zu wissen: Auf ETH korrelierten die Fenstergewinne zweier Perioden mit
    0,884. Ohne diese Aufschluesselung laesst sich das haerteste Gate des
    Systems umgehen, indem man eine Position in drei fast gleiche Teile
    zerlegt. Siehe ``research/unabhaengigkeit.py``.

    Leer bei einem einzelnen Bein - dann gibt es nichts zu korrigieren."""

    @property
    def window_count(self) -> int:
        return len(self.windows)

    @property
    def profitable_windows(self) -> int:
        return sum(1 for w in self.windows if w.is_profitable)

    @property
    def active_windows(self) -> int:
        """Fenster, in denen ueberhaupt gehandelt wurde."""
        return sum(1 for w in self.windows if w.trades)

    @property
    def consistency(self) -> float:
        """Anteil profitabler Fenster - gemessen an denen, in denen gehandelt wurde.

        Aussagekraeftiger als die Gesamtrendite: Eine Strategie mit 60 %
        profitablen Fenstern ist belastbarer als eine, die ihren gesamten
        Gewinn aus einem einzigen Ausreisser zieht.

        **Fenster ohne Trade zaehlen nicht mit**, und das ist eine Korrektur,
        keine Milderung. Frueher gingen sie als "nicht profitabel" ein. Damit
        wurde genau das bestraft, was eine Halte-Strategie tun soll: In den
        vier Baerenmarkt-Quartalen 2022 stand ein Kandidat korrekt an der
        Seitenlinie - und bekam dafuer vier Verlustfenster angerechnet.

        Ein Fenster ohne Handel ist weder Erfolg noch Misserfolg. Es sagt
        nichts darueber aus, ob die Strategie funktioniert, und darf deshalb
        in keine Richtung zaehlen.

        Dass daraus kein Schlupfloch wird - "einmal handeln, gewinnen, 100 %
        Bestaendigkeit" -, sichert das Gate ab: Es verlangt eine Mindestzahl
        aktiver Fenster.
        """
        aktiv = self.active_windows
        if not aktiv:
            return 0.0
        return self.profitable_windows / aktiv

    @property
    def worst_window(self) -> WindowResult | None:
        if not self.windows:
            return None
        return min(self.windows, key=lambda w: w.metrics.net_profit)

    @property
    def kalender_ausstiege(self) -> int:
        """Trades, die nicht die Regel beendet hat, sondern das Datenende.

        **Steht hier etwas, ist die Messung in diesem Umfang unbrauchbar.** Der
        Ausstieg entscheidet bei einer Trendfolge ueber das Ergebnis; wer ihn
        vom Kalender setzen laesst, misst den Kalender mit. Beim
        Spitzenkandidaten waren es einmal 25 von 154, und diese 25 trugen den
        gesamten Vorteil.

        Der Nachlauf soll das auf null bringen. Dass es dabei bleibt, wird
        nicht angenommen, sondern hier gezaehlt - eine Annahme haette genau
        den Fehler wieder eingebaut, den der Nachlauf behebt. Ein Rest bleibt
        legitim, wo die Daten selbst enden.
        """
        return sum(1 for t in self.all_trades if t.exit_reason == "end_of_data")

    def summary(self) -> str:
        if not self.windows or self.combined is None:
            return "Walk-Forward ohne Ergebnis"
        kalender = self.kalender_ausstiege
        zusatz = (
            f" | {kalender} Trades am Datenende beendet, nicht nach Regel"
            if kalender
            else ""
        )
        return (
            f"{self.window_count} Fenster, davon {self.profitable_windows} profitabel "
            f"({self.consistency:.0%}) | {self.combined.summary()}{zusatz}"
        )


class WalkForwardSplitter:
    """Erzeugt rollierende Trainings-/Testfenster.

    Beispiel bei 12 Monaten Training, 3 Monaten Test und 3 Tagen Sperrzone
    ueber den Zeitraum 2020-2026: rund 21 Fenster, die jeweils drei Monate
    weiterruecken.
    """

    def __init__(
        self,
        *,
        train_months: int = 12,
        test_months: int = 3,
        embargo: timedelta = timedelta(days=3),
        anchored: bool = False,
    ) -> None:
        self.train_months = train_months
        self.test_months = test_months
        self.embargo = embargo
        self.anchored = anchored
        """``True`` laesst den Trainingsbeginn fest und verlaengert das Fenster
        nur nach vorn. Realistischer, wenn die Strategie im Betrieb auf der
        gesamten Historie neu bewertet wird; ``False`` (rollierend) prueft
        haerter auf Anpassungsfaehigkeit."""

    def split(self, start: datetime, end: datetime) -> list[Window]:
        windows: list[Window] = []
        train_start = start
        train_end = _add_months(start, self.train_months)

        index = 0
        while True:
            test_start = train_end + self.embargo
            test_end = _add_months(test_start, self.test_months)
            if test_end > end:
                break

            windows.append(
                Window(
                    index=index,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
            index += 1
            train_end = _add_months(train_end, self.test_months)
            if not self.anchored:
                train_start = _add_months(train_start, self.test_months)

        return windows


def chained_curve(report: WalkForwardReport) -> np.ndarray:
    """Die Kapitalkurve ueber alle Testfenster, multiplikativ verkettet.

    Startwert 1,0. Verkettet wird wie im Bericht selbst: Zwei Fenster mit je
    +10 % ergeben +21 %, nicht +20 %. Additiv zu rechnen hat hier schon einmal
    einen Rueckgang von 1005 % erzeugt.

    Gebraucht von allem, was den **Verlauf** beurteilt statt einzelner Trades -
    etwa die schlechteste Zwoelfmonatsperiode. Trades taugen dafuer nicht: Eine
    Strategie, die drei Mal im Jahr handelt, hat davon zu wenige.
    """
    punkte: list[float] = []
    faktor = 1.0

    for fenster in report.windows:
        kurve = getattr(fenster.result, "equity_curve", None)
        if kurve is None or kurve.empty:
            continue
        werte = kurve["equity"].to_numpy(dtype=float)
        if len(werte) < 2 or werte[0] <= 0:
            continue
        punkte.extend(faktor * werte / werte[0])
        faktor = punkte[-1]

    return np.asarray(punkte, dtype=float)


def worst_rolling_return(curve: np.ndarray, months: int, total_months: float) -> float:
    """Schlechteste Rendite ueber ein rollierendes Fenster, in Prozent.

    Beantwortet die Frage, die der maximale Rueckgang offenlaesst: Wer zum
    denkbar unguenstigsten Zeitpunkt eingestiegen waere - wie stuende er nach
    einem Jahr da?

    Ein kurzer, tiefer Einbruch und eine lange Duerre koennen denselben
    maximalen Rueckgang haben. Auszuhalten sind sie voellig verschieden.

    ``nan``, wenn der Zeitraum fuer das Fenster zu kurz ist. Eine Zahl waere
    dort geraten.
    """
    if len(curve) < 3 or total_months <= months:
        return float("nan")

    spanne = int(len(curve) * months / total_months)
    if spanne < 2 or spanne >= len(curve):
        return float("nan")

    renditen = curve[spanne:] / curve[:-spanne] - 1.0
    return float(np.min(renditen) * 100.0)


#: Wie viele Testfensterlaengen der Nachlauf betraegt. Gemessen, siehe
#: ``nachlauf_fuer``. Stand Befund 151 - vorher stand hier eine 1.
NACHLAUF_FENSTER = 4


def nachlauf_fuer(window: Window) -> timedelta:
    """Wie lange ein Fenster ueber sein Ende hinaus laufen darf.

    **Vier Testfensterlaengen**, und diese Zahl ist gemessen, nicht gewaehlt.

    Die Messung, die eine Fensterlaenge ergab (Befund 22)
    -----------------------------------------------------
    Auf dem Spitzenkandidaten (BTC + ETH, Tageskerzen, Testfenster drei Monate)
    verschwinden die kalenderbeendeten Trades genau bei einer Fensterlaenge:

        Nachlauf     Trades   SR/Trade   Ergebnis   am Kalender beendet
             0 Tage     154     0,2444    1034 EUR    25 (16,2 %)
            30 Tage     154     0,2495    1232 EUR    12 ( 7,8 %)
            90 Tage     154     0,2584    1388 EUR     0 ( 0,0 %)
           180 Tage     154     0,2584    1388 EUR     0 ( 0,0 %)
           365 Tage     154     0,2584    1388 EUR     0 ( 0,0 %)

    Warum das zu kurz war (Befund 151)
    ----------------------------------
    **Diese Leiter lief ueber eine einzige Regel** - und die haelt sechs Tage
    im Mittel. Ueber den ganzen Tageskerzen-Katalog gemessen (24 Genome, BTC +
    ETH, Serienende um den Randpuffer gekuerzt) sieht es anders aus:

        Nachlauf   Regeln mit Kalenderausstiegen   betroffene Trades
            1 x            12 von 24                     103
            2 x             8 von 24                      20
            3 x             1 von 24                       3
            4 x             1 von 24                       2
            5 x             1 von 24                       2
            6 x             1 von 24                       2

    **Die Haelfte des Katalogs wurde am Kalender gemessen, nicht nach Regel.**
    Am schwersten traf es ``Trend-Beteiligung 200 Tage`` mit 10 von 53 Trades
    - und das ist der Partner, auf dem der groesste je gemessene Sprung des
    Projekts steht (Befund 73/140).

    Gewaehlt wird die **kleinste** Stufe, auf der es nicht mehr weniger wird -
    genau das Kriterium aus Befund 22, nur auf den Katalog angewandt statt auf
    eine Regel. Das ist 4x. Die Verbundzahlen sind ab 3x identisch; die 4 ist
    also nicht die guenstigste Stufe, sondern die erste ohne Bewegung.

    Der Boden von 2 ist kein Rest, der noch wegginge
    ------------------------------------------------
    Zwei Trades in ``Trend beide Richtungen`` bleiben bei jeder Laenge. Sie
    liegen am **Serienende**, und dort gibt es nichts mehr, wohin nachgelaufen
    werden koennte. Dagegen hilft kein Nachlauf: Solche Trades sind keine
    fertigen Beobachtungen und zaehlen in der Statistik nicht mit
    (``research.randschnitt.fertige``, Befund 152). In der Kapitalkurve
    bleiben sie stehen - dort ist die offene Position der Kontostand.

    Was passen muss, ist die **Haltedauer**, nicht die Fensterlaenge; die
    Fensterlaenge war ein Stellvertreter, der fuer eine kurz haltende Regel
    zufaellig genuegte. Wer eine Regel aufnimmt, die laenger haelt als viermal
    ein Testfenster, misst wieder am Kalender - der Bericht zeigt es in
    ``kalender_ausstiege``, und ``research.randschnitt`` beziffert, was daran
    haengt.

    An die Fensterlaenge gebunden statt an eine feste Zahl Tage, damit es auf
    15-Minuten-Kerzen nicht ploetzlich ein Jahr Daten je Fenster sind.
    """
    return (window.test_end - window.test_start) * NACHLAUF_FENSTER


def run_walkforward(
    frame: pd.DataFrame,
    build_strategy,
    config: BacktestConfig,
    splitter: WalkForwardSplitter,
    *,
    sub_frame: pd.DataFrame | None = None,
    strategie_je_fenster=None,
    durchgehend: bool = False,
) -> WalkForwardReport:
    """Strategie ueber alle Testfenster auswerten.

    ``durchgehend=True`` laeuft **einen** Backtest ueber die ganze Teststrecke
    statt eines je Fenster. Positionen ueberleben die Fenstergrenze, so wie im
    Betrieb; die Fenster ordnen nur noch zu. Nicht kombinierbar mit
    ``strategie_je_fenster``.

    ``build_strategy`` erzeugt fuer jedes Fenster eine **frische** Instanz.
    Das ist notwendig, weil eine Strategie internen Zustand halten darf
    (Sperrfrist, letzter Einstieg) - eine wiederverwendete Instanz wuerde
    Zustand ueber Fenstergrenzen hinweg schleppen.

    ``strategie_je_fenster`` erlaubt eine Strategie, die sich **aus dem
    Trainingsfenster** bestimmt: Statt ``build_strategy()`` wird dann
    ``strategie_je_fenster(window)`` gerufen, und der Aufrufer darf die
    Trainingsdaten dieses Fensters ansehen.

    Das ist die einzige Stelle, an der ein Parameter aus Daten gewaehlt
    werden darf, ohne dass es Ueberanpassung ist - die Wahl kennt das
    Testfenster nicht. Wer hier **Testdaten** hereinreicht, hebelt den
    ganzen Walk-Forward aus; siehe ``research/adaptiv.py``.
    """
    if frame.empty:
        return WalkForwardReport()

    if durchgehend and strategie_je_fenster is not None:
        raise ValueError(
            "durchgehend=True vertraegt sich nicht mit strategie_je_fenster: "
            "Eine Position ueber die Fenstergrenze zu tragen hiesse, sie unter "
            "einer Regel zu eroeffnen und unter einer anderen zu schliessen."
        )

    start = frame["open_time"].iloc[0].to_pydatetime()
    end = frame["open_time"].iloc[-1].to_pydatetime()
    windows = splitter.split(start, end)

    if not windows:
        log.warning(
            "walkforward.zu_wenig_daten",
            von=start.isoformat(),
            bis=end.isoformat(),
            benoetigt_monate=splitter.train_months + splitter.test_months,
        )
        return WalkForwardReport()

    if durchgehend:
        report = _run_durchgehend(frame, build_strategy, config, windows, sub_frame)
        log.info("walkforward.fertig", zusammenfassung=report.summary())
        return report

    report = WalkForwardReport()

    for window in windows:
        strategy: Strategy = (
            strategie_je_fenster(window)
            if strategie_je_fenster is not None
            else build_strategy()
        )
        window_result = _run_window(
            frame, strategy, config, window, sub_frame,
            nachlauf=nachlauf_fuer(window),
        )
        if window_result is not None:
            report.windows.append(window_result)
            report.all_trades.extend(window_result.trades)

    if report.windows:
        report.combined = _combine(report.windows, config.initial_equity)

    log.info("walkforward.fertig", zusammenfassung=report.summary())
    return report


def _run_durchgehend(
    frame: pd.DataFrame,
    build_strategy,
    config: BacktestConfig,
    windows: list[Window],
    sub_frame: pd.DataFrame | None,
) -> WalkForwardReport:
    """Ein Backtest ueber die ganze Teststrecke, Fenster nur zur Zuordnung.

    Der Unterschied zum fensterweisen Lauf ist genau einer: Die Position
    ueberlebt die Fenstergrenze. Alles andere bleibt - Aufwaermphase vor dem
    ersten Testfenster, Nachlauf hinter dem letzten, Zuordnung der Trades nach
    ihrem Einstiegszeitpunkt.

    Vor dem ersten Testfenster wird nicht gehandelt: Der Lauf beginnt genau
    eine Aufwaermphase davor, und in der gibt es mangels eingeschwungener
    Indikatoren keine Signale. Das erste Fenster startet also flach, und das
    ist richtig - vor dem Testzeitraum hat das Konto keine Geschichte.
    """
    strategy: Strategy = build_strategy()
    warmup_bars = getattr(strategy, "warmup_bars", 30)
    bar_step = _infer_step(frame)

    lauf_start = windows[0].test_start - bar_step * warmup_bars
    lauf_ende = pd.Timestamp(windows[-1].test_end) + nachlauf_fuer(windows[-1])

    def schneiden(daten: pd.DataFrame | None) -> pd.DataFrame | None:
        if daten is None:
            return None
        maske = (daten["open_time"] >= pd.Timestamp(lauf_start)) & (
            daten["open_time"] < lauf_ende
        )
        return daten.loc[maske].reset_index(drop=True)

    lauf = schneiden(frame)
    if lauf is None or len(lauf) <= warmup_bars + 10:
        return WalkForwardReport()

    ergebnis = Backtester(config).run(lauf, strategy, sub_frame=schneiden(sub_frame))

    report = WalkForwardReport()
    for window in windows:
        trades = [
            t
            for t in ergebnis.trades
            if window.test_start <= t.entry_time < window.test_end
        ]
        kurve = ergebnis.equity_curve
        if not kurve.empty:
            kurve = kurve.loc[
                (kurve["time"] >= pd.Timestamp(window.test_start))
                & (kurve["time"] < pd.Timestamp(window.test_end))
            ].reset_index(drop=True)
        if kurve.empty:
            continue

        # **Der Anfangswert ist der Kontostand bei Fensterbeginn, nicht das
        # Startkapital.** ``compute_metrics`` bildet den Gewinn aus der
        # Kapitalkurve; mit dem Startkapital als Bezug rechnete jedes Fenster
        # den gesamten bisherigen Gewinn noch einmal als seinen eigenen.
        anfang = Decimal(str(kurve["equity"].iloc[0]))
        teil = copy(ergebnis)
        teil.equity_curve = kurve
        teil.trades = trades

        report.windows.append(
            WindowResult(
                window=window,
                metrics=compute_metrics(
                    trades, kurve,
                    initial_equity=anfang,
                    total_fees=sum((t.fees for t in trades), Decimal(0)),
                    total_funding=sum((t.funding for t in trades), Decimal(0)),
                ),
                trades=trades,
                result=teil,
            )
        )
        report.all_trades.extend(trades)

    if not report.windows:
        return report

    # Die Gesamtsicht kommt aus der **durchgehenden** Kurve, nicht aus einer
    # Verkettung. ``_combine`` normiert jedes Fenster auf das Startkapital -
    # was hier doppelt aufzinsen wuerde, weil ein Fenster nicht mehr dort
    # beginnt, wo das Konto einmal angefangen hat.
    gesamt = ergebnis.equity_curve
    gesamt = gesamt.loc[
        (gesamt["time"] >= pd.Timestamp(windows[0].test_start))
        & (gesamt["time"] < pd.Timestamp(windows[-1].test_end))
    ].reset_index(drop=True)
    report.combined = compute_metrics(
        report.all_trades,
        gesamt,
        initial_equity=(
            Decimal(str(gesamt["equity"].iloc[0]))
            if not gesamt.empty
            else config.initial_equity
        ),
        total_fees=sum((t.fees for t in report.all_trades), Decimal(0)),
        total_funding=sum((t.funding for t in report.all_trades), Decimal(0)),
    )
    return report


def _run_window(
    frame: pd.DataFrame,
    strategy: Strategy,
    config: BacktestConfig,
    window: Window,
    sub_frame: pd.DataFrame | None,
    nachlauf: timedelta = timedelta(0),
) -> WindowResult | None:
    """Ein Fenster auswerten.

    Der Backtest laeuft ueber [Testbeginn - Aufwaermphase, Testende +
    Nachlauf], gezaehlt werden aber nur Trades, die **im Testfenster**
    eroeffnet wurden. Ohne die Aufwaermdaten waere der Anfang jedes Fensters
    signallos; ohne den Nachlauf beendete der Kalender die offenen Positionen
    statt der Regel.
    """
    warmup_bars = getattr(strategy, "warmup_bars", 30)
    bar_step = _infer_step(frame)
    run_start = window.test_start - bar_step * warmup_bars
    lauf_ende = pd.Timestamp(window.test_end) + nachlauf

    mask = (frame["open_time"] >= pd.Timestamp(run_start)) & (
        frame["open_time"] < lauf_ende
    )
    window_frame = frame.loc[mask].reset_index(drop=True)

    if len(window_frame) <= warmup_bars + 10:
        return None

    window_subs = None
    if sub_frame is not None:
        sub_mask = (sub_frame["open_time"] >= pd.Timestamp(run_start)) & (
            sub_frame["open_time"] < lauf_ende
        )
        window_subs = sub_frame.loc[sub_mask].reset_index(drop=True)

    result = Backtester(config).run(window_frame, strategy, sub_frame=window_subs)

    # Nur Trades zaehlen, die im eigentlichen Testfenster eroeffnet wurden.
    #
    # **Die obere Grenze ist neu und notwendig.** Ohne Nachlauf endeten die
    # Daten am Fensterende, und ein Einstieg danach war unmoeglich; mit
    # Nachlauf waere er es nicht. Fehlte die Schranke, wanderten Trades aus
    # dem Nachlauf in die Zaehlung - und benachbarte Fenster zaehlten
    # dieselben Trades doppelt.
    in_window = [
        t
        for t in result.trades
        if window.test_start <= t.entry_time < window.test_end
    ]

    # Die Kapitalkurve bleibt auf das Fenster begrenzt, damit sich die Kurven
    # benachbarter Fenster nicht ueberlappen. Beschnitten wird an der Quelle:
    # ``_combine`` und ``chained_curve`` lesen beide ``result.equity_curve``,
    # und zwei Stellen mit derselben Regel sind eine Stelle zu viel.
    if not result.equity_curve.empty:
        result.equity_curve = result.equity_curve.loc[
            result.equity_curve["time"] < pd.Timestamp(window.test_end)
        ].reset_index(drop=True)

    equity = result.equity_curve
    if not equity.empty:
        equity = equity.loc[equity["time"] >= pd.Timestamp(window.test_start)].reset_index(
            drop=True
        )

    metrics = compute_metrics(
        in_window,
        equity,
        initial_equity=config.initial_equity,
        total_fees=sum((t.fees for t in in_window), Decimal(0)),
        total_funding=sum((t.funding for t in in_window), Decimal(0)),
    )
    return WindowResult(window=window, metrics=metrics, trades=in_window, result=result)


def _combine(windows: list[WindowResult], initial_equity: Decimal) -> Metrics:
    """Alle Fenster zu einer Gesamtsicht zusammenfassen.

    Die Kapitalkurven werden aneinandergehaengt und auf einen durchgehenden
    Verlauf normiert. So ergibt sich ein Drawdown ueber alle Fenster hinweg -
    also die Zahl, die der Kill-Switch im Livebetrieb sehen wuerde.
    """
    trades: list[Trade] = []
    pieces: list[pd.DataFrame] = []
    offset = float(initial_equity)

    for window in windows:
        trades.extend(window.trades)
        curve = window.result.equity_curve
        if curve.empty:
            continue
        curve = curve.loc[
            curve["time"] >= pd.Timestamp(window.window.test_start)
        ].reset_index(drop=True)
        if curve.empty:
            continue
        # **Multiplikativ verketten, nicht addieren.**
        #
        # Jedes Fenster startet im Backtest mit dem vollen Anfangskapital und
        # bemisst seine Positionen daran. Wer die absoluten Ergebnisse
        # aneinanderhaengt, addiert Verluste, die sich auf jeweils 500 EUR
        # bezogen - auch dann noch, wenn das verkettete Konto laengst leer
        # waere. Nach 21 Fenstern stand so ein Drawdown von 1005 % in der
        # Tabelle: eine Zahl, die es nicht geben kann.
        #
        # Richtig ist die Verkettung der Renditen: Jedes Fenster wirkt als
        # Faktor auf das, was vom Vorgaenger uebrig blieb. Ein Konto, das auf
        # null faellt, bleibt danach bei null - so wie in der Wirklichkeit.
        factor = curve["equity"] / float(initial_equity)
        shifted = curve.copy()
        shifted["equity"] = (offset * factor).clip(lower=0.0)
        pieces.append(shifted)
        offset = float(shifted["equity"].iloc[-1])

    combined_curve = (
        pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame({"time": [], "equity": []})
    )

    return compute_metrics(
        trades,
        combined_curve,
        initial_equity=initial_equity,
        total_fees=sum((t.fees for t in trades), Decimal(0)),
        total_funding=sum((t.funding for t in trades), Decimal(0)),
    )


def _infer_step(frame: pd.DataFrame) -> timedelta:
    """Kerzenabstand aus den Daten ableiten - robust gegen einzelne Luecken."""
    if len(frame) < 3:
        return timedelta(minutes=15)
    deltas = frame["open_time"].diff().dropna()
    return pd.Timedelta(deltas.median()).to_pytimedelta()


def _add_months(moment: datetime, months: int) -> datetime:
    """Monate addieren, ohne externe Abhaengigkeit.

    Ueberlaufende Tage werden auf den Monatsletzten begrenzt - der 31. Januar
    plus einen Monat ist der 28. bzw. 29. Februar.
    """
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, _days_in_month(year, month))
    return moment.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    import calendar

    return calendar.monthrange(year, month)[1]
