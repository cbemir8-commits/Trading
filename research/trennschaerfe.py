"""Trennt irgendetwas die guten Trades von den schlechten?

Warum diese Frage jetzt dran ist
--------------------------------
Der Kandidat scheitert an vier Gates, und drei davon verlangen dasselbe:
**mehr Qualitaet je Trade.** Mehr Trades hilft dem Deflated Sharpe nur, wenn
sie unabhaengig sind - und alle Wege dorthin sind gemessen und geschlossen
(mehr Maerkte, mehr Historie, feinere Kerzen, Perioden-Ensemble).

Bleibt der andere Weg: dieselben Trades, besser gewichtet. Genau dafuer ist
die Konviktions-Groessenlogik gebaut - und genau die ist gemessen wirkungslos.
``cli konfluenz`` zeigt, warum: Die Reihenfolge, nach der sie den Einsatz
verteilt, gilt nicht.

    0 Bedingungen   14 Trades   +0,194 R
    1 Bedingung     60 Trades   +1,534 R
    2 Bedingungen   27 Trades   -0,427 R
    3 Bedingungen   51 Trades   +2,688 R      rho +0,150, p = 0,062

Nicht der Reihe nach, und nicht belegt. Der Mechanismus ist da, er ist nur an
die falschen Bedingungen gehaengt.

Was hier gemessen wird
----------------------
Fuer jedes Merkmal aus einem **vorab festgelegten** Katalog: Wie steht es bei
den Einstiegen, und unterscheiden sich die Ergebnisse? Verglichen wird ueber
Raenge (Wilcoxon-Rangsumme), nicht ueber Mittelwerte - bei R-Verteilungen mit
einzelnen +20-R-Treffern sagt ein Mittelwertvergleich mehr ueber den groessten
Gewinner als ueber die Trennung.

Der Punkt, auf den es ankommt: die Null
---------------------------------------
Wer zwoelf Merkmale prueft, findet mit Sicherheit eines, das trennt. Deshalb
wird nicht gegen die Null "dieses Merkmal trennt nicht" geprueft, sondern
gegen **"das beste von zwoelf trennt nicht"**. Je Ziehung wird gemischt, jedes
Merkmal neu bewertet, und gemerkt wird das Maximum ueber alle. Die Schranke
ist das 95. Perzentil dieser Maxima.

Und zwar blockweise
-------------------
Die Merkmale sind nicht gleichmaessig ueber die Zeit verteilt. Beim
Spitzenkandidaten faellt "Bollinger-Breite hoch" 2021 auf 18 von 21 Trades und
2025 auf 2 von 17. Ein Merkmal, das nur **schlechte Jahre markiert**, saehe in
einer freien Permutation wie eine Trennung aus, ohne eine zu sein.

Gemischt wird deshalb **innerhalb der Jahre**: Die Zusammensetzung jedes
Jahres bleibt, nur die Zuordnung Ergebnis-zu-Trade faellt weg. Wer damit noch
trennt, trennt innerhalb der Jahre und nicht zwischen ihnen. Die freie Null
wird zum Vergleich mitgerechnet; verbindlich ist die blockweise.

Die Merkmale sind untereinander korreliert; in der Null sind sie es nicht.
Das macht die Schranke **zu hoch**, nicht zu niedrig - die Richtung, in der
ein Fehler hier verzeihlich ist.

Was daraus nicht folgt
----------------------
Ein Merkmal, das die Schranke reisst, ist ein *Befund*, keine Strategie. Wer
es einbaut, hat einen neuen Kandidaten gebaut, und der zaehlt als Versuch und
muss durch dieselben elf Gates wie jeder andere. Diese Messung selbst rechnet
keinen einzigen Backtest und erhoeht den Zaehler deshalb nicht: Sie teilt die
Trades, die ohnehin schon gelaufen sind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategy.genome import Condition, Operand, Operator

#: Ab wie vielen Trades je Seite eine Aufteilung ueberhaupt etwas sagt.
#: Darunter wird sie gezeigt, aber nicht gedeutet - und sie zaehlt nicht zur
#: Familie, gegen die korrigiert wird.
MIND_TRADES = 20

#: Ziehungen fuer die Permutationsnull.
PERMUTATIONEN = 2000

#: Anteil, ab dem ein Ergebnis als belegt gilt.
SIGNIFIKANZ = 0.05


def _ind(name: str, **params: int) -> Operand:
    return Operand(kind="indicator", name=name, params=params)


def _preis(name: str) -> Operand:
    return Operand(kind="price", name=name)


def _zahl(wert: float) -> Operand:
    return Operand(kind="constant", value=wert)


@dataclass(frozen=True, slots=True)
class Merkmal:
    """Eine vorab festgelegte Eigenschaft des Einstiegsbalkens.

    Zwei Bauformen, und beide vermeiden eine frei gewaehlte Schwelle:

    * ``bedingung`` - eine feste, inhaltlich begruendete Schwelle (ADX ueber
      25 ist die uebliche Trend-Marke, RSI ueber 50 die Mitte).
    * ``operand`` - kein Schwellenwert, sondern die Teilung am **Median** der
      eigenen Reihe. Wo es keine natuerliche Marke gibt, ist das die einzige
      Wahl, die nichts auswaehlt.
    """

    name: str
    bedingung: Condition | None = None
    operand: Operand | None = None

    def __post_init__(self) -> None:
        if (self.bedingung is None) == (self.operand is None):
            raise ValueError(
                f"'{self.name}': entweder feste Schwelle oder Median-Teilung"
            )


#: Der Katalog. **Vorab festgelegt und im Code sichtbar** - ein Katalog, der
#: sich nach jeder Messung aendert, waere eine Suche mit unbekannt vielen
#: Versuchen und die Korrektur wertlos.
#:
#: Die ersten drei sind Kontrollen: Sie stehen bereits in der Konfluenz des
#: Kandidaten. Trennen sie hier auch nicht, ist das der Gegencheck zu
#: ``cli konfluenz`` ueber einen anderen Weg.
KATALOG: tuple[Merkmal, ...] = (
    Merkmal(
        "Ueber SMA(200)",
        bedingung=Condition(
            left=_preis("close"), op=Operator.GT, right=_ind("sma", period=200)
        ),
    ),
    Merkmal(
        "ROC(90) positiv",
        bedingung=Condition(
            left=_ind("roc", period=90), op=Operator.GT, right=_zahl(0.0)
        ),
    ),
    Merkmal(
        "RSI(14) ueber 50",
        bedingung=Condition(
            left=_ind("rsi", period=14), op=Operator.GT, right=_zahl(50.0)
        ),
    ),
    Merkmal(
        "ADX(14) ueber 25",
        bedingung=Condition(
            left=_ind("adx", period=14), op=Operator.GT, right=_zahl(25.0)
        ),
    ),
    Merkmal(
        "MACD ueber Signal",
        bedingung=Condition(
            left=_ind("macd", fast=12, slow=26),
            op=Operator.GT,
            right=_ind("macd_signal", fast=12, slow=26, signal=9),
        ),
    ),
    Merkmal(
        "Stochastik ueber 50",
        bedingung=Condition(
            left=_ind("stochastic", period=14), op=Operator.GT, right=_zahl(50.0)
        ),
    ),
    Merkmal("Volatilitaet hoch", operand=_ind("atr_pct", period=14)),
    Merkmal("Realisierte Vola hoch", operand=_ind("realized_vol", period=30)),
    Merkmal("Bollinger-Breite hoch", operand=_ind("bollinger_width", period=20)),
    Merkmal("Umsatz hoch", operand=_ind("volume_zscore", period=30)),
    Merkmal("Weit ueber EMA(50)", operand=_ind("distance_to_ema_pct", period=50)),
    Merkmal("Weit ueber VWAP", operand=_ind("vwap_distance_pct", period=30)),
)


def reihen_je_markt(strategie, frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Jedes Merkmal des Katalogs als Ja/Nein-Reihe ueber die Kerzen.

    Ausgewertet ueber ``CompiledStrategy`` - dieselbe Umsetzung, die auch der
    Backtest benutzt. Eine zweite waere die naechste Stelle, an der zwei
    Zahlen auseinanderlaufen; in diesem Projekt ist das schon viermal
    passiert.
    """
    index = pd.to_datetime(frame["open_time"])
    ergebnis: dict[str, pd.Series] = {}
    for merkmal in KATALOG:
        if merkmal.bedingung is not None:
            werte = strategie._condition_series(frame, merkmal.bedingung).astype(bool)
        else:
            roh = np.asarray(
                strategie._operand_series(frame, merkmal.operand), dtype=float
            )
            gueltig = roh[np.isfinite(roh)]
            if len(gueltig) == 0:
                werte = np.zeros(len(frame), dtype=bool)
            else:
                werte = np.nan_to_num(roh, nan=-np.inf) > float(np.median(gueltig))
        ergebnis[merkmal.name] = pd.Series(werte, index=index)
    return ergebnis


@dataclass(frozen=True, slots=True)
class Trennung:
    """Was ein Merkmal bei diesen Trades geleistet hat."""

    name: str
    wahr: tuple[float, ...]
    falsch: tuple[float, ...]
    z: float = 0.0

    @property
    def deutbar(self) -> bool:
        return min(len(self.wahr), len(self.falsch)) >= MIND_TRADES

    @property
    def mittel_wahr(self) -> float:
        return float(np.mean(self.wahr)) if self.wahr else 0.0

    @property
    def mittel_falsch(self) -> float:
        return float(np.mean(self.falsch)) if self.falsch else 0.0

    @property
    def unterschied(self) -> float:
        return self.mittel_wahr - self.mittel_falsch


def rangsumme(wahr: np.ndarray, falsch: np.ndarray) -> float:
    """Wilcoxon-Rangsumme als z-Wert - robust gegen einzelne Ausreisser.

    Ein Mittelwertvergleich haengt bei R-Verteilungen am groessten Gewinner:
    Ein einziger +20-R-Trade auf der einen Seite entscheidet ihn. Die
    Rangsumme fragt stattdessen, ob die *Reihenfolge* der Ergebnisse etwas
    ueber die Zugehoerigkeit verraet.
    """
    n1, n2 = len(wahr), len(falsch)
    if n1 == 0 or n2 == 0:
        return 0.0
    alle = np.concatenate([wahr, falsch])
    raenge = pd.Series(alle).rank().to_numpy()
    summe = float(raenge[:n1].sum())
    erwartung = n1 * (n1 + n2 + 1) / 2.0
    streuung = float(np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0))
    return (summe - erwartung) / streuung if streuung > 0 else 0.0


@dataclass(slots=True)
class Trennschaerfe:
    """Alle Merkmale und die Schranke, die der beste von ihnen reissen muss."""

    trennungen: list[Trennung] = field(default_factory=list)
    schranke: float = 0.0
    """Blockweise Schranke - die verbindliche."""

    schranke_frei: float = 0.0
    """Freie Permutation, nur zum Vergleich. Sie ignoriert, dass Merkmale
    ueber die Jahre ungleich verteilt sind, und faellt deshalb milder aus."""

    permutationen: int = 0
    trades: int = 0
    bloecke: int = 0

    @property
    def familie(self) -> list[Trennung]:
        """Die Merkmale, die ueberhaupt gedeutet werden - und nur die zaehlen
        bei der Korrektur mit."""
        return [t for t in self.trennungen if t.deutbar]

    @property
    def beste(self) -> Trennung | None:
        gedeutet = self.familie
        return max(gedeutet, key=lambda t: abs(t.z)) if gedeutet else None

    @property
    def belegt(self) -> bool:
        beste = self.beste
        return beste is not None and abs(beste.z) > self.schranke

    def tabelle(self) -> str:
        zeilen = [
            f"{'Merkmal':24} {'ja':>5} {'nein':>5} {'Mittel ja':>10} "
            f"{'Mittel nein':>12} {'z':>7}"
        ]
        for t in sorted(self.trennungen, key=lambda t: -abs(t.z)):
            marke = "" if t.deutbar else "  (zu wenige)"
            zeilen.append(
                f"{t.name:24} {len(t.wahr):>5} {len(t.falsch):>5} "
                f"{t.mittel_wahr:>10.3f} {t.mittel_falsch:>12.3f} "
                f"{t.z:>7.2f}{marke}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        beste = self.beste
        if beste is None:
            return (
                "Kein Merkmal teilt die Trades in zwei ausreichend grosse "
                "Haelften - aus dieser Messung folgt nichts."
            )
        kopf = (
            f"Bestes Merkmal '{beste.name}' mit z = {beste.z:+.2f}; die "
            f"Schranke fuer das Beste aus {len(self.familie)} liegt bei "
            f"{self.schranke:.2f} (blockweise ueber {self.bloecke} Jahre; "
            f"frei gemischt waeren es {self.schranke_frei:.2f})."
        )
        if not self.belegt:
            return (
                f"{kopf} **Nicht belegt.** Wer zwoelf Merkmale prueft, findet "
                f"immer eines, das trennt - dieses hier bleibt im Rahmen "
                f"dessen, was Zufall bei so vielen Versuchen liefert. Die "
                f"Groessenlogik hat damit weiter nichts, woran sie sich "
                f"halten koennte."
            )
        return (
            f"{kopf} **Belegt.** Das ist ein Befund, keine Strategie: Wer ihn "
            f"einbaut, hat einen neuen Kandidaten gebaut - ein Versuch mehr, "
            f"und durch alle elf Gates."
        )


def messe(
    trades,
    merkmale: dict[str, dict[str, pd.Series]],
    *,
    permutationen: int = PERMUTATIONEN,
    saat: int = 20260809,
) -> Trennschaerfe:
    """Die Trades nach jedem Merkmal aufteilen und familienweise korrigieren.

    ``merkmale`` bildet den Markt auf die Reihen seiner Merkmale ab. Zugeordnet
    wird ueber den Einstiegszeitpunkt - der Symbolname der Trades ist im
    Portfoliolauf fuer alle Beine derselbe und taugt dafuer nicht.
    """
    namen = [m.name for m in KATALOG]
    ergebnisse: list[float] = []
    bloecke: list[int] = []
    marken: dict[str, list[bool]] = {name: [] for name in namen}

    for trade in trades:
        ergebnis = trade.r_multiple
        if ergebnis is None:
            continue
        zeit = pd.Timestamp(trade.entry_time)
        for reihen in merkmale.values():
            erste = next(iter(reihen.values()), None)
            if erste is None or zeit not in erste.index:
                continue
            ergebnisse.append(float(ergebnis))
            bloecke.append(int(zeit.year))
            for name in namen:
                reihe = reihen.get(name)
                marken[name].append(bool(reihe.loc[zeit]) if reihe is not None else False)
            break

    werte = np.array(ergebnisse, dtype=float)
    block = np.array(bloecke, dtype=int)
    fahne = {name: np.array(marken[name], dtype=bool) for name in namen}

    bericht = Trennschaerfe(
        permutationen=permutationen,
        trades=len(werte),
        bloecke=len(np.unique(block)) if len(block) else 0,
    )
    for name in namen:
        ja = werte[fahne[name]]
        nein = werte[~fahne[name]]
        bericht.trennungen.append(
            Trennung(
                name=name,
                wahr=tuple(ja),
                falsch=tuple(nein),
                z=rangsumme(ja, nein),
            )
        )

    familie = bericht.familie
    if not familie or len(werte) < 2 * MIND_TRADES:
        return bericht

    # **Die Null ist "das Beste aus N", nicht "dieses eine".**
    #
    # Ohne diesen Schritt findet eine Suche ueber zwoelf Merkmale zuverlaessig
    # eines, das "signifikant" aussieht.
    fahnen = [fahne[t.name] for t in familie]
    rng = np.random.default_rng(saat)

    def maxima(mischen) -> float:
        werte_je_zug = np.empty(permutationen)
        for i in range(permutationen):
            gemischt = mischen()
            werte_je_zug[i] = max(
                abs(rangsumme(gemischt[f], gemischt[~f])) for f in fahnen
            )
        return float(np.quantile(werte_je_zug, 1.0 - SIGNIFIKANZ))

    def frei() -> np.ndarray:
        return rng.permutation(werte)

    # **Blockweise: innerhalb der Jahre mischen.** Die Zusammensetzung jedes
    # Jahres bleibt erhalten, nur die Zuordnung Ergebnis-zu-Trade faellt weg.
    # Ein Merkmal, das nur schlechte Jahre markiert, bekommt dafuer keinen
    # Kredit mehr.
    gruppen = [np.flatnonzero(block == b) for b in np.unique(block)]

    def blockweise() -> np.ndarray:
        gemischt = werte.copy()
        for stellen in gruppen:
            gemischt[stellen] = rng.permutation(werte[stellen])
        return gemischt

    bericht.schranke_frei = maxima(frei)
    bericht.schranke = maxima(blockweise)
    return bericht
