"""Betriebspunkt: was jede Hebelstufe bringt und was sie kostet.

Warum es diese Datei gibt
-------------------------
Hebel ist die einzige Stellschraube, die ein kleines Konto wirklich spuerbar
veraendert - und die einzige, bei der die Werbung fuer sich selbst spricht und
die Rechnung nicht. Vier Zahlen aus **derselben** Rechnung entscheiden:

    Rendite p.a.        was es bringt
    Rueckgang           was es kostet
    aus 500 wird        dasselbe in Geld
    Kill-Switch         wie oft der Handel nach eigener Regel gestoppt haette

Die letzte ist die entscheidende und fehlt ueberall sonst. Eine Rendite, die
nur zustande kommt, wenn man die eigene Abbruchregel ignoriert, ist keine
Rendite - sie ist ein Backtest-Artefakt. Wer bei 15 % Rueckgang aufhoert, hat
den Kursanstieg danach nicht mitgenommen, egal was die Kurve zeigt.

Der Regler ist das Vola-Ziel, nicht der Deckel
----------------------------------------------
``SizingSpec.fraction`` ist eine **Obergrenze**. Bei einem Vola-Ziel von 50 %
liegt der gewuenschte Anteil fast immer darunter, der Deckel greift also gar
nicht - ob er bei 1,0, 2,0 oder 3,0 steht, aendert nichts. Beim ersten Messen
sahen deshalb alle Hebelstufen gleich aus, und das Ergebnis waere ein
falsches "Hebel bringt nichts" gewesen. Gedreht wird an ``target_vol_pct``.

Gemeinsamer Zeitraum, sonst nichts
-----------------------------------
Mehrere Maerkte werden auf den Zeitraum zugeschnitten, den **alle** abdecken,
bevor irgendetwas gerechnet wird. BTC reicht bis 2012 zurueck, ETH erst bis
2017; ungeschnitten entstehen zwei verschieden lange Kapitalkurven, und die
punktweise uebereinanderzulegen hiesse, BTCs 2013 neben ETHs 2018 zu stellen.
Genau dieser Fehler hat hier einmal einen Rueckgang von 4,93 % erzeugt, der
nach Streuungsgewinn aussah und keiner war.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

import numpy as np
import pandas as pd
import structlog

from backtest.engine import BacktestConfig
from backtest.walkforward import WalkForwardSplitter, chained_curve, run_walkforward
from research.portfolio import combine_curves
from strategy.compiler import compile_genome
from strategy.genome import Genome

log = structlog.get_logger(__name__)

#: Die Stufen, zwischen denen gewaehlt wird - Vola-Ziel in Prozent p.a.
#: Eng genug, dass zwischen zwei Stufen keine andere Welt liegt.
DEFAULT_STUFEN = (30.0, 40.0, 50.0, 60.0, 75.0, 90.0, 100.0, 125.0, 150.0)


@dataclass(frozen=True, slots=True)
class Stufe:
    """Eine Hebelstufe mit allem, was sie kostet."""

    vola_ziel: float
    hebel: float
    cagr_pct: float
    drawdown_pct: float
    sharpe: float
    endwert: float
    kill_switch: int
    curve: np.ndarray

    def describe(self) -> str:
        return (
            f"Ziel {self.vola_ziel:5.0f} %  Hebel {self.hebel:.2f}x  "
            f"{self.cagr_pct:6.2f} % p.a.  Rueckgang {self.drawdown_pct:5.2f} %  "
            f"Sharpe {self.sharpe:.2f}  -> {self.endwert:.0f}  "
            f"Kill-Switch {self.kill_switch}x"
        )


def common_range(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Alle Maerkte auf den Zeitraum zuschneiden, den jeder abdeckt.

    Muss vor jeder Portfoliorechnung passieren - siehe Modulkopf.
    """
    if not frames:
        return {}
    von = max(f["open_time"].iloc[0] for f in frames.values())
    bis = min(f["open_time"].iloc[-1] for f in frames.values())
    return {
        name: f[(f["open_time"] >= von) & (f["open_time"] <= bis)].reset_index(drop=True)
        for name, f in frames.items()
    }


def kill_switch_hits(curve: np.ndarray, limit_pct: float) -> int:
    """Wie oft der Rueckgang die Abbruchgrenze reisst.

    Nach jedem Treffer beginnt die Zaehlung von vorn, weil dort der Handel
    gestoppt und spaeter mit dem verbliebenen Kapital neu begonnen wuerde.
    Ohne diesen Neustart zaehlt **ein** tiefer Rueckgang hundert Tage lang
    mit, und die Zahl waere Unsinn statt Information.
    """
    if len(curve) < 2:
        return 0
    hoch = float(curve[0])
    treffer = 0
    for wert in curve[1:]:
        wert = float(wert)
        hoch = max(hoch, wert)
        if hoch > 0 and (1.0 - wert / hoch) * 100.0 >= limit_pct:
            treffer += 1
            hoch = wert
    return treffer


def average_leverage(frame: pd.DataFrame, genome: Genome) -> float:
    """Durchschnittlich eingesetzter Anteil am Kapital.

    Ueber alle Kerzen, bei denen ueberhaupt ein Einsatz vorgesehen ist. Werte
    ueber 1,0 heissen Hebel; 1,67 heisst, dass im Mittel das 1,67-fache des
    Kontos im Markt stand.
    """
    strategie = compile_genome(genome)
    strategie.prepare(frame)
    werte = [strategie.fraction_at(i) for i in range(len(frame))]
    brauchbar = [float(w) for w in werte if w is not None and w > 0]
    return float(np.mean(brauchbar)) if brauchbar else 0.0


#: Ablehnungsgruende, die ein Ergebnis unbrauchbar machen, statt es nur zu
#: praegen. Wer wegen zu kleinem Konto nicht handeln kann, hat ein echtes
#: Ergebnis - wer an einer erfundenen Obergrenze scheitert, hat keins.
STILLE_KILLER = frozenset({"qty_above_maximum", "notional_too_small"})


def _rejection_check(name: str, ziel: float, report) -> None:
    """Warnen, wenn Trades an Kontraktgrenzen gescheitert sind.

    Das ist keine Kosmetik. Beim Bauen dieses Moduls lief ETH mit den
    Kontraktdaten von BTCUSDT, deren ``max_order_qty`` bei 100 lag. ETH kostete
    Ende 2018 rund 80 USD - bei hohem Hebel ergab das ueber 100 Stueck, die
    Order wurde **stillschweigend abgelehnt**, und die betroffenen Stufen sahen
    danach schlechter aus. Ich haette diese Zahlen fast als "ab hier lohnt sich
    Hebel nicht mehr" berichtet. Der Befund war ein falsch gesetztes Limit.
    """
    getroffen: dict[str, int] = {}
    for fenster in report.windows:
        for grund, anzahl in fenster.result.rejections.items():
            if grund in STILLE_KILLER:
                getroffen[grund] = getroffen.get(grund, 0) + anzahl
    if getroffen:
        log.warning(
            "betriebspunkt.orders_abgelehnt",
            markt=name, ziel=ziel, gruende=getroffen,
            hinweis="Kontraktgrenzen pruefen - die Zahlen dieser Stufe sind zu niedrig",
        )


def measure(
    frames: dict[str, pd.DataFrame],
    build_genome,
    config: BacktestConfig | dict[str, BacktestConfig],
    *,
    stufen=DEFAULT_STUFEN,
    splitter: WalkForwardSplitter | None = None,
    kill_switch_pct: float = 15.0,
    start_capital: float = 500.0,
) -> list[Stufe]:
    """Jede Stufe ueber alle Maerkte rechnen und zusammenlegen.

    ``build_genome(vola_ziel)`` liefert das Genome fuer eine Stufe. Es darf
    sich zwischen den Stufen **nur** im Vola-Ziel unterscheiden - sonst laesst
    sich der Unterschied nicht dem Hebel zuschreiben, sondern nur der Summe
    aus Hebel und einer zweiten Aenderung.

    ``config`` darf eine Zuordnung Markt -> Konfiguration sein. Das ist bei
    mehreren Maerkten der Normalfall und keine Feinheit: Ein ETH-Kontrakt hat
    andere Schrittweiten und Obergrenzen als ein BTC-Kontrakt, und wer BTCs
    Werte auf ETH anwendet, bekommt abgelehnte Orders statt Ergebnisse.
    """
    if not frames:
        raise ValueError("Ohne Maerkte gibt es keinen Betriebspunkt")

    zugeschnitten = common_range(frames)
    splitter = splitter or WalkForwardSplitter(train_months=12, test_months=3)

    def config_fuer(name: str) -> BacktestConfig:
        if isinstance(config, dict):
            if name not in config:
                raise KeyError(f"Keine Backtest-Konfiguration fuer {name}")
            return config[name]
        return config

    ergebnis: list[Stufe] = []
    for ziel in stufen:
        genome = build_genome(ziel)
        kurven: dict[str, np.ndarray] = {}
        hebel: list[float] = []

        for name, frame in zugeschnitten.items():
            report = run_walkforward(
                frame, lambda g=genome: compile_genome(g), config_fuer(name), splitter
            )
            if not report.windows:
                log.warning("betriebspunkt.kein_fenster", markt=name, ziel=ziel)
                continue
            _rejection_check(name, ziel, report)
            kurven[name] = chained_curve(report)
            hebel.append(average_leverage(frame, genome))

        if not kurven:
            continue

        jahre = min(len(k) for k in kurven.values()) / 365.0
        port = combine_curves(kurven, years=jahre)
        ergebnis.append(
            Stufe(
                vola_ziel=ziel,
                hebel=float(np.mean(hebel)) if hebel else 0.0,
                cagr_pct=port.cagr_pct,
                drawdown_pct=port.max_drawdown_pct,
                sharpe=port.sharpe,
                endwert=start_capital * float(port.curve[-1]),
                kill_switch=kill_switch_hits(port.curve, kill_switch_pct),
                curve=port.curve * start_capital,
            )
        )
        log.info("betriebspunkt.stufe", ergebnis=ergebnis[-1].describe())

    return ergebnis


def highest_safe(stufen: list[Stufe]) -> Stufe | None:
    """Die hoechste Stufe, bei der der Kill-Switch nie ausgeloest haette.

    Das ist die einzige Empfehlung, die sich aus den Zahlen allein ableiten
    laesst: mehr Hebel als das ist nach der eigenen Abbruchregel nicht
    erreichbar, weniger verschenkt Ertrag ohne Gegenwert.
    """
    sicher = [s for s in stufen if s.kill_switch == 0]
    return max(sicher, key=lambda s: s.vola_ziel) if sicher else None


def turning_point(stufen: list[Stufe]) -> Stufe | None:
    """Die Stufe, ab der mehr Hebel weniger Geld bringt.

    Gibt es diesen Punkt, ist er der harte Beweis dafuer, dass Hebel kein
    Verstaerker ohne Preis ist: Der Weg zurueck aus einem Verlust waechst
    schneller als der Verlust selbst, und irgendwann frisst er den Vorsprung.
    Gibt es ihn im gemessenen Bereich nicht, ist das Ergebnis ``None`` - dann
    liegt der Wendepunkt jenseits der geprueften Stufen.
    """
    for vorher, nachher in pairwise(stufen):
        if nachher.endwert < vorher.endwert:
            return nachher
    return None


def as_payload(
    stufen: list[Stufe], *, markets: list[str], kill_switch_pct: float,
    start_capital: float, punkte: int = 90,
) -> dict:
    """Fuer Bericht und Website - Kurven ausgeduennt, Zahlen gerundet."""
    return {
        "maerkte": markets,
        "kill_switch_pct": kill_switch_pct,
        "startkapital": start_capital,
        "stufen": [
            {
                "vola_ziel": s.vola_ziel,
                "hebel": round(s.hebel, 2),
                "cagr": round(s.cagr_pct, 2),
                "rueckgang": round(s.drawdown_pct, 2),
                "sharpe": round(s.sharpe, 2),
                "endwert_500": round(s.endwert),
                "kill_switch": s.kill_switch,
                "kurve": _ausduennen(s.curve, punkte),
            }
            for s in stufen
        ],
    }


def _ausduennen(curve: np.ndarray, punkte: int) -> list[int]:
    """Kurve auf rund ``punkte`` Stuetzstellen reduzieren.

    Der letzte Wert kommt immer mit - ohne ihn endet die Grafik an einer
    beliebigen Stelle und stimmt nicht mehr mit dem Endwert daneben ueberein.
    """
    if len(curve) <= punkte:
        return [round(float(v)) for v in curve]
    # Aufrunden, nicht abrunden: Bei 501 Werten und Ziel 90 ergibt Abrunden
    # eine Schrittweite von 5 und damit 101 Stuetzstellen - mehr als bestellt.
    schritt = max(1, -(-len(curve) // punkte))
    gekuerzt = [round(float(v)) for v in curve[::schritt]]
    letzter = round(float(curve[-1]))
    if gekuerzt[-1] != letzter:
        gekuerzt.append(letzter)
    return gekuerzt


def make_config(config: BacktestConfig, equity: Decimal) -> BacktestConfig:
    """Kopie mit anderem Startkapital - der Rest bleibt gleich."""
    from dataclasses import replace

    return replace(config, initial_equity=equity)
