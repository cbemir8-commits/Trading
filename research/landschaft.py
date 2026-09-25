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
from research.freigabe import stillgelegt
from research.gates import _operand_kennung, skaliere_perioden
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

    wert: int = 0
    """Der Wert der **abgetasteten** Stellgroesse an diesem Punkt.

    Bei der gemeinsamen Verschiebung ist das die Leitperiode. Wird eine
    einzelne Stellgroesse abgetastet, steht hier ihr Wert - die Leitperiode
    bliebe dort konstant und taugte nicht als Beschriftung.
    """

    gesperrt: int = 0
    """Einstiege, die an diesem Punkt eine **dauerhafte** Sperre verhindert
    hat - Befund 314.

    Diese Karte tastet mit durchgehenden Backtests ab, einem Risk-Officer
    ueber die ganze Reihe. Not-Aus und Wochenlimit sind Zustaende und keine
    Uhren: Greift einer, handelt der Punkt bis zum letzten Balken nicht mehr.
    Ein ``-`` in der Tabelle heisst dann nicht "hier endet das Gebiet",
    sondern "hier griff die Sperre".
    """

    @property
    def profitabel(self) -> bool:
        return self.gewinn > 0

    @property
    def zu_ende_gemessen(self) -> bool:
        return self.gesperrt == 0


@dataclass(slots=True)
class Landschaft:
    """Die abgetastete Gegend um einen Kandidaten."""

    punkte: list[Punkt] = field(default_factory=list)
    mitte: float = 1.0
    regler: str = "alle gemeinsam"
    """Welche Stellgroesse abgetastet wurde."""

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

    @property
    def gesperrte_punkte(self) -> int:
        return sum(1 for p in self.punkte if p.gesperrt)

    @property
    def verhinderte_einstiege(self) -> int:
        return sum(p.gesperrt for p in self.punkte)

    def _vorbehalt(self) -> str:
        """Was die Karte ueber sich selbst sagen muss - Befund 314.

        Steht **vor** dem Urteil und nicht dahinter: Wer "Grat" liest und
        aufhoert, soll nicht erst darunter erfahren, dass die Punkte gar
        nicht zu Ende gemessen wurden.
        """
        if not self.gesperrte_punkte:
            return ""
        return (
            f"**{self.gesperrte_punkte} von {len(self.punkte)} Punkten "
            f"wurden nicht zu Ende gemessen** - eine dauerhafte Sperre hat "
            f"dort {self.verhinderte_einstiege} Einstiege verhindert und "
            f"laeuft bis zur manuellen Freigabe, die ein durchgehender Lauf "
            f"nie bekommt. Ein '-' kann damit der Zeitpunkt der Sperre sein "
            f"statt das Ende des Gebiets ('cli freigabe' misst es). "
        )

    @property
    def zu_ende_gemessen(self) -> bool:
        """Wurde **jeder** Punkt bis zum letzten Balken gehandelt?"""
        return self.gesperrte_punkte == 0

    def urteil(self) -> str:
        if not self.punkte:
            return "Nichts abgetastet."
        vorbehalt = self._vorbehalt()
        # **Befund 330.** Befund 314 hat den Vorbehalt davorgestellt und das
        # Urteil stehen gelassen - und das Urteil behauptete danach weiter
        # eine Form ("Plateau: 12 zusammenhaengende Punkte von 12"), obwohl
        # kein einziger Punkt zu Ende gemessen war. Gemessen an
        # 'rsi(period=14)': 12 von 12 stillgelegt, 900 verhinderte Einstiege,
        # und darunter stand die guenstigste Lesart, die es gibt.
        #
        # Die Zahlen bleiben alle stehen. Was wegfaellt, ist der **Name** der
        # Form, denn den hat diese Karte nicht gemessen.
        if self.gesperrte_punkte == len(self.punkte):
            return (
                f"{vorbehalt}**Eine Form ist damit nicht gemessen.** "
                f"{len(self.profitabel)} von {len(self.punkte)} Punkten "
                f"stehen am Ende im Plus, {self.zusammenhaengend} davon "
                f"zusammenhaengend - aber jeder dieser Punkte endet an seiner "
                f"Sperre und nicht am Rand des Gebiets. Ob hier ein Plateau "
                f"oder ein Grat liegt, sagt diese Karte nicht."
            )
        if self.zusammenhaengend <= 1:
            return (
                f"{vorbehalt}Grat: Nur {self.zusammenhaengend} "
                f"zusammenhaengender Punkt von {len(self.punkte)}. Der "
                f"Treffer haengt an der Parameterwahl."
            )
        if not self.mitte_liegt_im_plateau:
            return (
                f"{vorbehalt}Der Kandidat liegt **neben** dem Plateau. "
                f"Laengste Kette {self.zusammenhaengend} Punkte, er gehoert "
                f"nicht dazu."
            )
        return (
            f"{vorbehalt}Plateau: {self.zusammenhaengend} zusammenhaengende "
            f"Punkte von {len(self.punkte)}, der Kandidat mittendrin."
        )

    def tabelle(self) -> str:
        spalte = "Leitperiode" if self.regler == "alle gemeinsam" else self.regler[:12]
        zeilen = [
            f"{'Faktor':>7} {spalte:>12} {'Trades':>7} {'Gewinn':>11} "
            f"{'gesperrt':>9}  "
        ]
        for p in self.punkte:
            marke = "  <== Kandidat" if abs(p.faktor - self.mitte) < 1e-9 else ""
            zeichen = "+" if p.profitabel else "-"
            zeilen.append(
                f"{p.faktor:>7.2f} {p.wert or p.leitperiode:>12} {p.trades:>7} "
                f"{p.gewinn:>11.2f} {p.gesperrt:>9} {zeichen}{marke}"
            )
        return "\n".join(zeilen)


#: Die Abschnitte, in denen Perioden stehen.
ABSCHNITTE = (
    "entry_long", "entry_short", "exit_long", "exit_short", "filters", "konfluenz",
)


def leitperiode(genome: Genome) -> int:
    """Die laengste Indikatorperiode - als Kurzname fuer einen Parametersatz.

    Sie identifiziert den Punkt eindeutiger als der Faktor: Zwei Faktoren
    koennen nach dem Runden auf dieselben Perioden fuehren.
    """
    werte = [
        wert
        for abschnitt in ABSCHNITTE
        for bedingung in getattr(genome, abschnitt, [])
        for seite in (bedingung.left, bedingung.right)
        if seite.kind == "indicator"
        for wert in seite.params.values()
    ]
    return max(werte) if werte else 0


def stellwert(original: Genome, variante: Genome, kennung: str | None) -> int:
    """Der Wert der abgetasteten Stellgroesse - die Beschriftung eines Punktes.

    Ohne ``kennung`` ist das die Leitperiode. Mit ``kennung`` waere sie
    nutzlos: Wer nur ``sma(50)`` verschiebt, laesst die 200 stehen, und alle
    Punkte truegen dieselbe Zahl.

    **Gesucht wird im Original, abgelesen in der Variante.** Der erste Anlauf
    suchte die Kennung in der Variante - dort heisst der Operand aber laengst
    ``sma(period=25)`` und passt auf nichts mehr. Die Tabelle zeigte deshalb
    fuer jeden Punkt ausser dem Kandidaten die Leitperiode 200, als waere
    nichts verschoben worden.
    """
    if kennung is None:
        return leitperiode(variante)
    if kennung == "stop":
        return int(variante.stop.model_dump().get("atr_period") or 0)
    if kennung == "sizing":
        return int(variante.sizing.vol_period or 0)

    alt = original.model_dump(mode="json")
    neu = variante.model_dump(mode="json")
    for abschnitt in ABSCHNITTE:
        for i, bedingung in enumerate(alt.get(abschnitt, [])):
            for seite in ("left", "right"):
                operand = bedingung[seite]
                if operand["kind"] != "indicator" or not operand["params"]:
                    continue
                if _operand_kennung(operand) != kennung:
                    continue
                # Dieselbe Stelle in der Variante ablesen - die Struktur ist
                # identisch, nur die Zahlen sind andere.
                params = neu[abschnitt][i][seite]["params"]
                return int(next(iter(params.values())))
    return 0


def kartieren(
    genome: Genome,
    frames: dict[str, pd.DataFrame],
    configs: dict[str, BacktestConfig],
    *,
    faktoren: tuple[float, ...] = FAKTOREN,
    nur: str | None = None,
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

    **``nur`` tastet eine einzelne Stellgroesse ab.** Ohne das verschiebt sich
    immer alles zugleich, und die Karte kann nicht sagen, *welche* Periode den
    Ausschlag gibt. Beim Spitzenkandidaten ist genau das die offene Frage: Das
    Plateau-Gate hat gezeigt, dass vier seiner fuenf Perioden nichts bewirken
    und alles an der 50 haengt.
    """
    landschaft = Landschaft(regler=nur or "alle gemeinsam")
    gesehen: set[str] = set()

    for faktor in faktoren:
        variante = (
            genome if faktor == 1.0 else skaliere_perioden(genome, faktor, nur=nur)
        )
        if variante is None:
            continue

        # **Nach dem Genom unterscheiden, nicht nach der Leitperiode.**
        #
        # Frueher stand hier die Leitperiode als Schluessel. Beim Abtasten
        # einer einzelnen Stellgroesse bleibt sie konstant - der zweite Punkt
        # haette wie ein Duplikat ausgesehen, und die Karte haette aus einem
        # einzigen Punkt bestanden, ohne dass es aufgefallen waere.
        if variante.genome_id in gesehen:
            continue
        gesehen.add(variante.genome_id)

        je_markt: dict[str, float] = {}
        trades = 0
        gesperrt = 0
        for name, frame in frames.items():
            ergebnis = Backtester(configs[name]).run(frame, compile_genome(variante))
            je_markt[name] = float(ergebnis.net_profit)
            trades += len(ergebnis.trades)
            gesperrt += stillgelegt(ergebnis.veto_reasons)

        punkt = Punkt(
            faktor=faktor,
            leitperiode=leitperiode(variante),
            gewinn=sum(je_markt.values()) / len(je_markt),
            trades=trades,
            je_markt=je_markt,
            wert=stellwert(genome, variante, nur),
            gesperrt=gesperrt,
        )
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
