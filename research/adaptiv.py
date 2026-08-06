"""Die Periode im Trainingsfenster waehlen, nicht am Schreibtisch.

Das Problem
-----------
Die Landschaftskarte (``research/landschaft.py``) hat gezeigt: Die
Regelfamilie traegt ueber einen breiten Bereich - Faktor 0,5 bis 1,1 sind
alle profitabel -, und die schnelleren Punkte liefern deutlich **mehr
Trades** bei hoeherem Gewinn: 168 gegen 93. Mehr Trades derselben Guete sind
genau das, was dem Deflated Sharpe fehlt.

Den besten Punkt aus dieser Karte zu nehmen waere Ueberanpassung: Die Karte
ist auf denselben Daten entstanden, an denen der Kandidat gemessen wird.

Der saubere Weg
---------------
Die Periode wird in **jedem Trainingsfenster neu bestimmt** und im
Testfenster verwendet. Damit kennt die Wahl die Testdaten nicht, und das
Ergebnis ist ausserhalb der Stichprobe entstanden - so, wie es auch im
Betrieb liefe: Man waehlt aus dem, was man weiss, und handelt damit weiter.

Zum Versuchszaehler: Das ist **eine** Hypothese, nicht eine je Faktor. Die
einzelnen Faktoren werden nur im Training angesehen und nie am Testergebnis
gemessen; die Auswahl ist Teil der Strategie geworden. Genau darin liegt der
methodische Vorteil gegenueber dem Ablesen aus der Karte.

Warum die Mitte und nicht der Beste
-----------------------------------
Die Auswahlregel steht **vor** der Messung fest, damit ich hinterher nicht
diejenige nehme, die am besten aussieht - das waere dieselbe
Ueberanpassung eine Ebene hoeher.

Gewaehlt wird die **Mitte des laengsten zusammenhaengenden profitablen
Bereichs**, nicht der Punkt mit dem hoechsten Gewinn. Begruendung, aus der
Landschaftskarte:

* Der Spitzenwert wandert. Im Trainingsfenster liegt er woanders als im
  Testfenster; ihn zu nehmen heisst, Rauschen zu folgen.
* Die Karte zeigt einen breiten Bereich mit aehnlichen Ergebnissen (0,60 bis
  0,90 liegen zwischen 539 und 844). Welcher davon der hoechste ist, ist
  fast Zufall - dass der ganze Bereich traegt, ist es nicht.
* Der bisherige Kandidat scheitert am Plateau-Gate, **weil** er am Rand
  sitzt. Eine Regel, die in die Mitte zielt, greift genau das an.

Ein einzelner profitabler Punkt ohne profitable Nachbarn wird verworfen: Das
ist ein Grat, kein Plateau, und dort zu handeln waere eine Wette auf die
Parameterwahl.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import structlog

from backtest.engine import BacktestConfig
from research.landschaft import FAKTOREN, Landschaft, kartieren
from strategy.genome import Genome

log = structlog.get_logger(__name__)

#: Wie viele profitable Punkte nebeneinanderliegen muessen, damit ein
#: Bereich als tragfaehig gilt. Zwei ist das Minimum, bei dem das Wort
#: "Bereich" ueberhaupt etwas bedeutet.
MINDESTBREITE = 2


@dataclass(frozen=True, slots=True)
class Wahl:
    """Was im Trainingsfenster herauskam."""

    genome: Genome
    faktor: float
    breite: int
    """Wie viele profitable Punkte der gewaehlte Bereich hatte."""

    begruendung: str

    @property
    def gefunden(self) -> bool:
        return self.breite >= MINDESTBREITE


def mitte_des_plateaus(karte: Landschaft) -> tuple[float, int] | None:
    """Der mittlere Faktor des laengsten zusammenhaengenden profitablen Bereichs.

    ``None``, wenn kein Bereich die Mindestbreite erreicht - dann gibt es
    nichts, worauf sich die Wahl stuetzen koennte.

    Bei gerader Breite wird der **langsamere** der beiden mittleren Punkte
    genommen. Willkuerlich, aber festgelegt: Ohne eine Regel entschiede die
    Rundung, und dieselbe Karte lieferte je nach Implementierung zwei
    verschiedene Antworten.
    """
    beste: list = []
    kette: list = []
    for punkt in karte.punkte:
        kette = [*kette, punkt] if punkt.profitabel else []
        if len(kette) > len(beste):
            beste = kette

    if len(beste) < MINDESTBREITE:
        return None
    return beste[(len(beste) - 1) // 2].faktor, len(beste)


def waehle(
    genome: Genome,
    train_frames: dict[str, pd.DataFrame],
    configs: dict[str, BacktestConfig],
    *,
    faktoren: tuple[float, ...] = FAKTOREN,
) -> Wahl:
    """Die Periode aus dem Trainingsfenster bestimmen.

    Faellt die Wahl aus - kein tragfaehiger Bereich im Training -, bleibt es
    beim uebergebenen Genom. Das ist die konservative Richtung: Wer im
    Training keinen Bereich findet, hat keinen Grund, etwas zu verstellen.
    """
    karte = kartieren(genome, train_frames, configs, faktoren=faktoren)
    ergebnis = mitte_des_plateaus(karte)

    if ergebnis is None:
        return Wahl(
            genome=genome,
            faktor=1.0,
            breite=karte.zusammenhaengend,
            begruendung=(
                f"Kein tragfaehiger Bereich im Training (laengste Kette "
                f"{karte.zusammenhaengend}) - Genom unveraendert."
            ),
        )

    faktor, breite = ergebnis
    from research.gates import skaliere_perioden

    gewaehlt = genome if faktor == 1.0 else skaliere_perioden(genome, faktor)
    if gewaehlt is None:
        gewaehlt = genome

    log.info("adaptiv.gewaehlt", faktor=faktor, breite=breite)
    return Wahl(
        genome=gewaehlt,
        faktor=faktor,
        breite=breite,
        begruendung=(
            f"Mitte eines Bereichs aus {breite} profitablen Punkten, "
            f"Faktor {faktor:.2f}."
        ),
    )


class FensterWahl:
    """Waehlt je Walk-Forward-Fenster **einmal** - fuer alle Maerkte gemeinsam.

    Gemeinsam, nicht je Markt: Waehlte jeder Markt seine eigene Periode,
    waeren es zwei verschiedene Strategien in einem Korb, und der Vergleich
    mit dem festen Kandidaten waere keiner mehr.

    Der Aufrufer bekommt eine Funktion, die ``run_walkforward`` je Fenster
    ruft. Weil dieselbe Funktion je Markt einmal gerufen wird, merkt sich
    diese Klasse die Wahl je Fensterindex - sonst wuerde die Karte je Markt
    neu gerechnet, und das dauerte das Vielfache.
    """

    def __init__(
        self,
        genome: Genome,
        frames: dict[str, pd.DataFrame],
        configs: dict[str, BacktestConfig],
        *,
        faktoren: tuple[float, ...] = FAKTOREN,
    ) -> None:
        self.genome = genome
        self.frames = frames
        self.configs = configs
        self.faktoren = faktoren
        self.wahlen: dict[int, Wahl] = {}

    def __call__(self, window):
        """Die Strategie fuer dieses Fenster - aus seinen Trainingsdaten."""
        from strategy.compiler import compile_genome

        if window.index not in self.wahlen:
            self.wahlen[window.index] = waehle(
                self.genome,
                self._trainingsdaten(window),
                self.configs,
                faktoren=self.faktoren,
            )
        return compile_genome(self.wahlen[window.index].genome)

    def _trainingsdaten(self, window) -> dict[str, pd.DataFrame]:
        """Nur Kerzen aus [train_start, train_end).

        Die obere Grenze ist **ausschliessend**. Eine einzige Kerze zu viel
        waere die erste des Testfensters - und damit genau der Lookahead,
        den der ganze Walk-Forward verhindern soll.
        """
        return {
            name: frame[
                (frame["open_time"] >= window.train_start)
                & (frame["open_time"] < window.train_end)
            ].reset_index(drop=True)
            for name, frame in self.frames.items()
        }

    def bericht(self) -> str:
        if not self.wahlen:
            return "Noch nichts gewaehlt."
        zeilen = [f"{'Fenster':>8} {'Faktor':>7} {'Breite':>7}  Begruendung"]
        for index in sorted(self.wahlen):
            w = self.wahlen[index]
            zeilen.append(
                f"{index:>8} {w.faktor:>7.2f} {w.breite:>7}  {w.begruendung[:46]}"
            )
        faktoren = [w.faktor for w in self.wahlen.values()]
        zeilen.append("")
        zeilen.append(
            f"  {len(set(faktoren))} verschiedene Faktoren ueber "
            f"{len(faktoren)} Fenster, Spanne "
            f"{min(faktoren):.2f} bis {max(faktoren):.2f}"
        )
        return "\n".join(zeilen)
