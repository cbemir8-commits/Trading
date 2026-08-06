"""Wie sieht die Gegend um einen Kandidaten aus - Plateau oder Grat?

Wozu
----
Das Gate ``Parameter-Plateau`` prueft genau zwei Nachbarn, plus und minus
20 %. Beim Spitzenkandidaten faellt einer davon durch, und damit steht das
Gate auf 1 von 2. Was es **nicht** sagt: ob der Kandidat auf einer
Nadelspitze sitzt oder am Rand einer breiten Hochebene.

Das sind zwei sehr verschiedene Lagen, und sie fuehren zu verschiedenen
Entscheidungen:

* Nur 50 funktioniert, 40 und 60 nicht - dann war der Treffer Zufall, und
  die ganze Regelfamilie ist erledigt.
* 30 bis 55 funktionieren, ab 60 nicht mehr - dann gibt es einen echten
  Bereich, und die 50 sitzt nur unguenstig an dessen Kante.

Zwei Messpunkte koennen das nicht unterscheiden. Diese Karte tastet die
Periode systematisch ab und zeigt die Form.

Was diese Karte **nicht** ist
-----------------------------
Kein Optimierer. Wer sie liest und daraufhin den besten Punkt zum neuen
Kandidaten erklaert, hat genau die Ueberanpassung begangen, gegen die das
Plateau-Gate gebaut wurde - nur mit mehr Stellen hinter dem Komma.

Sie beantwortet eine andere Frage: **Traegt diese Regelfamilie ueberhaupt?**
Eine Landschaft aus lauter Zacken sagt "nein" und erspart weitere Arbeit an
dieser Richtung. Das ist ihr Wert.

Zum Versuchszaehler
-------------------
Jeder abgetastete Punkt ist ein gerechneter Kandidat und zaehlt. Der
Deflated Sharpe korrigiert dafuer, dass man bei genug Versuchen irgendwann
etwas findet, das im Rueckblick gut aussieht - und wer eine Landschaft
kartiert, hat sie gesehen, ob er den besten Punkt nimmt oder nicht. Der
Aufrufer ist dafuer verantwortlich, ``len(punkte)`` auf den Zaehler zu
addieren; ``cli landschaft`` tut das.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd
import structlog

from backtest.engine import BacktestConfig, Backtester
from research.gates import skaliere_perioden
from strategy.compiler import compile_genome
from strategy.genome import Genome

log = structlog.get_logger(__name__)

#: Faktoren, mit denen abgetastet wird. Symmetrisch um 1,0 in Logarithmen,
#: damit "halb so schnell" und "doppelt so schnell" gleich weit vom
#: Ausgangspunkt entfernt liegen - in linearen Schritten waere die
#: langsamere Seite systematisch feiner abgetastet.
FAKTOREN = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4, 1.6, 1.8, 2.0)


@dataclass(frozen=True, slots=True)
class Punkt:
    """Ein abgetasteter Parametersatz."""

    faktor: float
    leitperiode: int
    """Die laengste Indikatorperiode - als Kurzbeschreibung des Punktes.
    Beim Spitzenkandidaten ist das der 200-Tage-Schnitt der Konfluenz."""

    gewinn: float
    """Summiert ueber alle Maerkte, jeder mit gleichem Gewicht - so, wie der
    Korb gehandelt wuerde."""

    trades: int
    je_markt: dict[str, float] = field(default_factory=dict)

    @property
    def profitabel(self) -> bool:
        return self.gewinn > 0


@dataclass(slots=True)
class Landschaft:
    """Die abgetastete Gegend um einen Kandidaten."""

    punkte: list[Punkt] = field(default_factory=list)
    mitte: float = 1.0

    @property
    def profitabel(self) -> list[Punkt]:
        return [p for p in self.punkte if p.profitabel]

    @property
    def quote(self) -> float:
        return len(self.profitabel) / len(self.punkte) if self.punkte else 0.0

    @property
    def zusammenhaengend(self) -> int:
        """Laengste ununterbrochene Kette profitabler Punkte.

        Die Zahl, auf die es ankommt. Sechs profitable Punkte, die alle
        nebeneinanderliegen, sind ein Plateau; dieselben sechs verstreut sind
        Rauschen, das zufaellig oft genug positiv ausgefallen ist.
        """
        laengste = laufend = 0
        for p in self.punkte:
            laufend = laufend + 1 if p.profitabel else 0
            laengste = max(laengste, laufend)
        return laengste

    @property
    def mitte_liegt_im_plateau(self) -> bool:
        """Sitzt der Kandidat selbst in der laengsten Kette?

        Sitzt er daneben, ist sein Ergebnis nicht durch die Nachbarschaft
        gestuetzt - egal wie breit die anderswo ist.
        """
        kette: list[Punkt] = []
        beste: list[Punkt] = []
        for p in self.punkte:
            kette = [*kette, p] if p.profitabel else []
            if len(kette) > len(beste):
                beste = kette
        return any(abs(p.faktor - self.mitte) < 1e-9 for p in beste)

    def urteil(self) -> str:
        if not self.punkte:
            return "Nichts abgetastet."
        if self.zusammenhaengend <= 1:
            return (
                f"Grat: Nur {self.zusammenhaengend} zusammenhaengender Punkt von "
                f"{len(self.punkte)}. Der Treffer haengt an der Parameterwahl."
            )
        if not self.mitte_liegt_im_plateau:
            return (
                f"Der Kandidat liegt **neben** dem Plateau. Laengste Kette "
                f"{self.zusammenhaengend} Punkte, er gehoert nicht dazu."
            )
        return (
            f"Plateau: {self.zusammenhaengend} zusammenhaengende Punkte von "
            f"{len(self.punkte)}, der Kandidat mittendrin."
        )

    def tabelle(self) -> str:
        zeilen = [f"{'Faktor':>7} {'Leitperiode':>12} {'Trades':>7} {'Gewinn':>11}  "]
        for p in self.punkte:
            marke = "  <== Kandidat" if abs(p.faktor - self.mitte) < 1e-9 else ""
            zeichen = "+" if p.profitabel else "-"
            zeilen.append(
                f"{p.faktor:>7.2f} {p.leitperiode:>12} {p.trades:>7} "
                f"{p.gewinn:>11.2f} {zeichen}{marke}"
            )
        return "\n".join(zeilen)


def leitperiode(genome: Genome) -> int:
    """Die laengste Indikatorperiode - als Kurzname fuer einen Parametersatz.

    Sie identifiziert den Punkt eindeutiger als der Faktor: Zwei Faktoren
    koennen nach dem Runden auf dieselben Perioden fuehren.
    """
    werte = [
        wert
        for abschnitt in (
            "entry_long", "entry_short", "exit_long", "exit_short",
            "filters", "konfluenz",
        )
        for bedingung in getattr(genome, abschnitt, [])
        for seite in (bedingung.left, bedingung.right)
        if seite.kind == "indicator"
        for wert in seite.params.values()
    ]
    return max(werte) if werte else 0


def kartieren(
    genome: Genome,
    frames: dict[str, pd.DataFrame],
    configs: dict[str, BacktestConfig],
    *,
    faktoren: tuple[float, ...] = FAKTOREN,
) -> Landschaft:
    """Die Gegend um ``genome`` abtasten.

    Gerechnet wird auf **allen** uebergebenen Maerkten und gleich gewichtet
    zusammengezaehlt - so, wie der Korb gehandelt wuerde. Das Plateau-Gate
    rechnet dagegen nur auf einem Markt; wer die beiden vergleicht, muss das
    wissen.

    Bewusst ein einfacher Backtest je Punkt und kein Walk-Forward: Gefragt
    ist die **Form** der Landschaft, nicht die Zulassungsfaehigkeit jedes
    Punktes. Ein Walk-Forward ueber zwoelf Punkte und zwei Maerkte dauerte
    Minuten und aenderte an der Form wenig.
    """
    landschaft = Landschaft()
    gesehen: dict[int, Punkt] = {}

    for faktor in faktoren:
        variante = genome if faktor == 1.0 else skaliere_perioden(genome, faktor)
        if variante is None:
            continue

        leit = leitperiode(variante)
        if leit in gesehen and faktor != 1.0:
            # Zwei Faktoren, dieselben gerundeten Perioden - kein neuer Punkt.
            continue

        je_markt: dict[str, float] = {}
        trades = 0
        for name, frame in frames.items():
            ergebnis = Backtester(configs[name]).run(frame, compile_genome(variante))
            je_markt[name] = float(ergebnis.net_profit)
            trades += len(ergebnis.trades)

        punkt = Punkt(
            faktor=faktor,
            leitperiode=leit,
            gewinn=sum(je_markt.values()) / len(je_markt),
            trades=trades,
            je_markt=je_markt,
        )
        gesehen[leit] = punkt
        landschaft.punkte.append(punkt)

    landschaft.punkte.sort(key=lambda p: p.faktor)
    log.info(
        "landschaft.kartiert",
        punkte=len(landschaft.punkte),
        profitabel=len(landschaft.profitabel),
        zusammenhaengend=landschaft.zusammenhaengend,
    )
    return landschaft


def standard_configs(
    frames: dict[str, pd.DataFrame], vorlage: BacktestConfig, instrumente: dict
) -> dict[str, BacktestConfig]:
    """Je Markt eine Konfiguration mit demselben Startkapital."""
    return {
        name: BacktestConfig(
            instrument=instrumente[name],
            risk=vorlage.risk,
            initial_equity=Decimal(vorlage.initial_equity),
            enforce_risk_limits=vorlage.enforce_risk_limits,
        )
        for name in frames
    }
