"""Findet die Zulassungsstrecke einen Vorteil, wo garantiert keiner ist?

**Die Frage, die unter allen anderen liegt.** Neun Richtungen sind inzwischen
gemessen und widerlegt, der Deflated Sharpe haengt bei 0,80, und alle diese
Zahlen kommen aus derselben Maschine. Wenn die Maschine selbst einen Vorteil
erzeugt - durch Lookahead, durch einen Fehler in der Fensterlogik, durch eine
Kerze zu frueh -, dann ist jede Messung der letzten Wochen wertlos, und zwar
ohne dass irgendetwas nach einem Fehler aussieht.

**Das Verfahren: Renditen mischen.** Aus den echten Tagesrenditen wird eine
neue Preisreihe gebaut, in der die Reihenfolge zerstoert ist. Damit bleibt
alles erhalten, was nichts mit Vorhersagbarkeit zu tun hat - Verteilung,
Schwankungsbreite, Groessenordnung, sogar der Aufwaertsdrift -, aber jede
Struktur, auf die eine Trendfolge angewiesen ist, ist weg.

Auf so einer Reihe **muss** eine Trendfolge scheitern. Tut sie es nicht, liegt
es an der Maschine.

**Ein Haken, in den ich zuerst hineingelaufen bin.** Der erste Anlauf verglich
den Ertrag mit Kaufen-und-Halten auf derselben gemischten Reihe - und meldete
prompt einen Maschinenfehler. Der Fehler lag in der Kennzahl: Das Mischen
erhaelt die Gesamtrendite **exakt**, denn das Produkt der Renditen haengt nicht
von ihrer Reihenfolge ab. Kaufen-und-Halten ist auf jeder gemischten Reihe
dieselbe Zahl - eine Konstante, keine Verteilung. Ein Abstand dazu misst nur
noch, wie viel Zeit die Strategie im Markt verbringt.

Verglichen wird deshalb der **Ertrag der Strategie selbst**: echte Reihe gegen
gemischte Reihen. Das ist die saubere Frage, weil die Strategie das einzige
ist, was sich zwischen den Laeufen aendert.

Zwei Dinge muessen dabei herauskommen, und beide sind noetig:

* Auf gemischten Reihen darf die Strategie **nicht verdienen**. Tut sie es,
  erzeugt die Maschine Vorteile, wo keine sind.
* Die echte Reihe muss sich von den gemischten **abheben**. Tut sie es nicht,
  leistet die Strategie nichts, was der Zufall nicht auch leistet.

Das kostet keinen Versuch: Geprueft wird die Maschine, keine Regel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class Nullergebnis:
    """Was die Strategie auf einer Reihe ohne Struktur erreicht hat."""

    trades: int
    erwartung_r: float
    ertrag_pct: float
    kaufen_halten_pct: float

    @property
    def ueberschuss_pct(self) -> float:
        """Ertrag ueber Kaufen-und-Halten.

        Nur zur Einordnung. **Nicht** als Vergleichsgroesse zwischen Laeufen
        geeignet: Kaufen-und-Halten ist auf jeder gemischten Reihe dieselbe
        Zahl, weil das Mischen die Gesamtrendite erhaelt.
        """
        return self.ertrag_pct - self.kaufen_halten_pct


@dataclass(slots=True)
class Nullverteilung:
    """Die Ergebnisse vieler gemischter Reihen - und wo die echte liegt."""

    echt: Nullergebnis
    gemischt: list[Nullergebnis] = field(default_factory=list)

    def _anteil(self, wert: float, werte: list[float]) -> float:
        if not werte:
            return 1.0
        return float(np.mean([x >= wert for x in werte]))

    @property
    def p_ertrag(self) -> float:
        return self._anteil(
            self.echt.ertrag_pct, [g.ertrag_pct for g in self.gemischt]
        )

    @property
    def maschine_sauber(self) -> bool:
        """Verdient die Strategie auf strukturlosen Daten?

        Eine Trendfolge auf gemischten Renditen **muss** verlieren: Es gibt
        keinen Trend mehr, nur noch Gebuehren und Stops. Steht der Median im
        Plus, findet die Zulassungsstrecke Vorteile, wo keine sind - und dann
        sagt keine andere Messung des Projekts etwas aus.
        """
        if not self.gemischt:
            return False
        return float(np.median([g.ertrag_pct for g in self.gemischt])) <= 0.0

    @property
    def hebt_sich_ab(self) -> bool:
        """Liegt die echte Reihe ausserhalb dessen, was Zufall erzeugt?"""
        return bool(self.gemischt) and self.p_ertrag <= 0.05

    def bericht(self) -> str:
        if not self.gemischt:
            return "Keine gemischten Laeufe - nichts zu vergleichen."
        ertraege = [g.ertrag_pct for g in self.gemischt]
        zeilen = [
            f"Echte Reihe:  {self.echt.trades} Trades, "
            f"{self.echt.ertrag_pct:+.1f} % Ertrag",
            f"{len(self.gemischt)} gemischte Reihen: Ertrag im Median "
            f"{np.median(ertraege):+.1f} %, Spanne {min(ertraege):+.1f} bis "
            f"{max(ertraege):+.1f} %, Trades im Mittel "
            f"{np.mean([g.trades for g in self.gemischt]):.0f}",
            f"Anteil der gemischten Laeufe mindestens so gut: {self.p_ertrag:.1%}",
        ]
        if not self.maschine_sauber:
            zeilen.append(
                "WARNUNG: Auf strukturlosen Daten verdient die Strategie im "
                "Median. Das deutet auf einen Fehler in der Maschine - "
                "Lookahead oder Fensterlogik. Bis das geklaert ist, sagt "
                "keine andere Messung etwas aus."
            )
        elif not self.hebt_sich_ab:
            zeilen.append(
                "Die echte Reihe hebt sich nicht ab: Was die Strategie "
                "leistet, leistet der Zufall auch."
            )
        else:
            zeilen.append(
                "Die Maschine findet auf strukturlosen Daten nichts, und die "
                "echte Reihe hebt sich ab. Beides noetig, beides erfuellt."
            )
        zeilen.append(
            f"(Kaufen-und-Halten: {self.echt.kaufen_halten_pct:+.1f} % - auf "
            f"jeder gemischten Reihe dieselbe Zahl, weil Mischen die "
            f"Gesamtrendite erhaelt.)"
        )
        return "\n".join(zeilen)


def mische_renditen(frame: pd.DataFrame, saat: int) -> pd.DataFrame:
    """Eine Preisreihe aus denselben Renditen in anderer Reihenfolge.

    Erhalten bleiben Verteilung, Schwankungsbreite und Drift; zerstoert wird
    jede zeitliche Struktur. Hoch, tief und Eroeffnung werden aus dem neuen
    Schluss im urspruenglichen Verhaeltnis rekonstruiert - sonst waeren die
    Dochte zu Preisen aus einer anderen Zeit, und Stops griffen an Stellen,
    die es nie gab.
    """
    werte = frame.copy().reset_index(drop=True)
    close = werte["close"].to_numpy(dtype=float)
    if len(close) < 3:
        return werte

    log_renditen = np.diff(np.log(close))
    return baue_reihe(werte, np.random.default_rng(saat).permutation(log_renditen))


def baue_reihe(frame: pd.DataFrame, log_renditen: np.ndarray) -> pd.DataFrame:
    """Eine Kerzenreihe aus vorgegebenen Log-Renditen, Dochte inklusive.

    **Warum die Dochte mitmuessen.** Hoch, tief und Eroeffnung werden aus dem
    neuen Schluss im urspruenglichen Verhaeltnis rekonstruiert. Ohne das waeren
    sie Preise aus einer anderen Zeit, und Stops griffen an Stellen, die es nie
    gab - der Backtest liefe weiter und meldete nichts.

    Getrennt von ``mische_renditen``, weil inzwischen zwei Verfahren eine
    Reihe umbauen: das Mischen zerstoert Struktur, das Pflanzen in
    ``research/teststaerke.py`` legt welche hinein. Beide brauchen dieselbe
    Rekonstruktion, und zwei Umsetzungen davon waeren zwei Gelegenheiten, sie
    verschieden falsch zu machen.
    """
    werte = frame.copy().reset_index(drop=True)
    close = werte["close"].to_numpy(dtype=float)
    neu = np.empty_like(close)
    neu[0] = close[0]
    neu[1:] = close[0] * np.exp(np.cumsum(log_renditen))

    for spalte in ("open", "high", "low"):
        verhaeltnis = werte[spalte].to_numpy(dtype=float) / close
        werte[spalte] = neu * verhaeltnis
    werte["close"] = neu
    # Hoch und tief muessen den Bereich weiterhin umschliessen.
    werte["high"] = werte[["open", "high", "close"]].max(axis=1)
    werte["low"] = werte[["open", "low", "close"]].min(axis=1)
    return werte


def kaufen_und_halten_pct(frame: pd.DataFrame) -> float:
    close = frame["close"].to_numpy(dtype=float)
    if len(close) < 2 or close[0] <= 0:
        return 0.0
    return float((close[-1] / close[0] - 1) * 100)
