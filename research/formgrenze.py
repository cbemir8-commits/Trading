"""Schiefe und Woelbung sind nicht frei waehlbar - und das aendert das Urteil.

Der Weg, der seit Wochen ausgewiesen wird
-----------------------------------------
``cli stand`` zerlegt das Deflated-Sharpe-Gate in vier Groessen und fragt fuer
jede: *Wo muesste sie stehen, damit das Gate haelt - alles andere
unveraendert?* Die Antwort steht dort seit Wochen:

    Qualitaet je Trade         0.260 ->     0.294   (+13%)
    unabhaengige Trades      152.000 ->   202.334   (+33%)
    Schiefe                    3.473 ->     4.530   (+30%)
    Woelbung                  15.951   unerreichbar

Und darunter: *"Die Schiefe ist der einzige der vier Wege, den noch nie jemand
gemessen hat."* Sie ist damit der letzte offene Weg - Qualitaet und Trade-Zahl
sind durch die Kopplung aus Befund 54 blockiert, die Woelbung kann nicht unter
1 fallen.

Was an dieser Zerlegung falsch ist
----------------------------------
**"Alles andere unveraendert" geht bei diesen beiden nicht.** Fuer jede
Verteilung gilt

    Woelbung >= Schiefe^2 + 1

Das ist kein Erfahrungswert, sondern Cauchy-Schwarz auf ``Cov(X, X^2)`` einer
standardisierten Groesse; Gleichheit erreichen nur Zweipunktverteilungen. Wer
die Schiefe hebt, hebt die Woelbung zwangslaeufig mit - und die wirkt im Nenner
der DSR-Formel in die **Gegenrichtung**.

Der ausgewiesene Zielpunkt - Schiefe 4,53 bei einer festgehaltenen Woelbung von
15,95 - verlangt eine Woelbung von mindestens 20,5. **Es gibt keine Verteilung
dieser Form.** Die Zerlegung weist einen Punkt aus, den es nicht gibt.

Was stattdessen gilt
--------------------
Zwei Rechnungen, gestaffelt nach Sicherheit:

* **Entlang der harten Schranke** (das mathematische Optimum, praktisch nicht
  erreichbar): Es braucht Schiefe 5,54 statt 4,53 - **+60 % statt +30 %**.
* **Entlang der gemessenen Linie** (siehe unten): Das Gate wird ueber die
  Schiefe **nie** erreicht. Der hoechste erreichbare Wert liegt bei 0,872.

Die gemessene Linie
-------------------
Acht Kandidaten dieses Projekts tragen Schiefe **und** Woelbung mit, aus fuenf
verschiedenen Regelfamilien - von der Rueckkehr zum Mittel bis zum
Donchian-Ausbruch. Sie liegen auf einer Geraden in ``Schiefe^2``:

    Woelbung = 1,194 * Schiefe^2 + 1,691       (r = 0,996, n = 8)

Deutlich **ueber** der harten Schranke, und der Abstand waechst. Das ist eine
Beschreibung dessen, was hier vorkam, kein Naturgesetz - ein Kandidat koennte
darunter liegen. Die Schranke ist das Naturgesetz, und schon sie verdoppelt
die Anforderung.

Die Falle in der Rechnung selbst
--------------------------------
``DSR(Schiefe)`` ist **nicht monoton**. Der Nenner der Formel lautet entlang
der Schranke ``(1 - Schiefe*SR/2)^2 + Ueberschuss*SR^2/4`` und hat sein Minimum
bei ``Schiefe = 2/SR``; darueber wird das Gate wieder schwerer. Eine Bisektion,
die Monotonie voraussetzt, meldet hier "unerreichbar", wo in Wahrheit ein
Fenster liegt - dieser Fehler ist beim Bauen dieses Moduls tatsaechlich
passiert. Deshalb wird die Kurve abgetastet und ihr Maximum ausgewiesen.

Kostet keinen Versuch: Gerechnet wird mit Zahlen, die schon dastehen.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from research.gates import GateThresholds, deflated_sharpe_ratio

#: Aus der Gate-Definition geholt, nicht aus ``suchbudget`` - sonst haengt die
#: Formgrenze an einem Modul, das sie selbst braucht. Die Quelle ist beide
#: Male dieselbe, also gibt es keine zweite Wahrheit.
ZIEL = GateThresholds().min_deflated_sharpe


def mindestwoelbung(schiefe: float) -> float:
    """Die kleinste Woelbung, die zu dieser Schiefe gehoeren kann.

    ``Schiefe^2 + 1``, aus Cauchy-Schwarz. Fuer eine standardisierte Groesse
    ist ``Cov(X, X^2)`` die Schiefe und ``Var(X^2)`` die Woelbung minus eins;
    die Ungleichung folgt unmittelbar. Gleichheit nur bei
    Zweipunktverteilungen - jede stetige Verteilung liegt darueber.
    """
    return schiefe**2 + 1.0


def moeglich(schiefe: float, woelbung: float) -> bool:
    """Kann es eine Verteilung mit dieser Form ueberhaupt geben?"""
    return woelbung >= mindestwoelbung(schiefe)


def ueberschuss(schiefe: float, woelbung: float) -> float:
    """Wie weit die Form ueber der Schranke liegt. Negativ = unmoeglich."""
    return woelbung - mindestwoelbung(schiefe)


@dataclass(frozen=True, slots=True)
class Formpunkt:
    """Ein gemessener Kandidat mit beiden Formzahlen."""

    quelle: str
    kennung: str
    schiefe: float
    woelbung: float

    @property
    def ueberschuss(self) -> float:
        return ueberschuss(self.schiefe, self.woelbung)

    @property
    def moeglich(self) -> bool:
        return moeglich(self.schiefe, self.woelbung)


@dataclass(slots=True)
class Formlinie:
    """Der gemessene Zusammenhang zwischen Schiefe und Woelbung.

    Angepasst wird in ``Schiefe^2``, weil die Schranke dort linear ist. Eine
    Anpassung in der Schiefe selbst wuerde die Kruemmung als Rauschen
    behandeln und dabei genau die Groesse verlieren, um die es geht.
    """

    punkte: list[Formpunkt] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        """Reichen die Punkte fuer eine Gerade, die etwas aussagt?"""
        return len(self.punkte) >= 3

    def _anpassung(self) -> tuple[float, float]:
        x = np.array([p.schiefe**2 for p in self.punkte])
        y = np.array([p.woelbung for p in self.punkte])
        steigung, abschnitt = np.polyfit(x, y, 1)
        return float(steigung), float(abschnitt)

    @property
    def steigung(self) -> float | None:
        return self._anpassung()[0] if self.genug else None

    @property
    def abschnitt(self) -> float | None:
        return self._anpassung()[1] if self.genug else None

    @property
    def guete(self) -> float | None:
        """Korrelation in ``Schiefe^2`` - wie eng die Punkte liegen."""
        if not self.genug:
            return None
        x = np.array([p.schiefe**2 for p in self.punkte])
        y = np.array([p.woelbung for p in self.punkte])
        if np.std(x) == 0 or np.std(y) == 0:
            return None
        return float(np.corrcoef(x, y)[0, 1])

    def woelbung_bei(self, schiefe: float) -> float | None:
        """Welche Woelbung bei dieser Schiefe zu erwarten waere.

        Nie unter der Schranke: Eine angepasste Gerade kann rechnerisch
        darunter geraten, eine Verteilung nicht.
        """
        if not self.genug:
            return None
        steigung, abschnitt = self._anpassung()
        return max(steigung * schiefe**2 + abschnitt, mindestwoelbung(schiefe))

    def ueber_der_schranke(self) -> bool:
        """Liegen alle gemessenen Punkte ueber der Schranke?

        Muessen sie - sonst ist eine der beiden Zahlen falsch gerechnet, und
        das waere ein Fund ueber den Messcode und nicht ueber den Markt.
        """
        return all(p.moeglich for p in self.punkte)


@dataclass(frozen=True, slots=True)
class Formweg:
    """Das Gate als Funktion der Schiefe - entlang einer Kopplung.

    ``kopplung`` sagt, welche Woelbung zu einer Schiefe gehoert. Genau hier
    steckt der Unterschied zwischen der bisherigen Zerlegung (Woelbung
    festgehalten) und der Wirklichkeit.
    """

    sharpe: float
    stichprobe: int
    versuche: int
    kopplung: Callable[[float], float]
    name: str = ""
    ziel: float = ZIEL
    von: float = 0.0
    bis: float = 20.0
    schritte: int = 4000

    def dsr_bei(self, schiefe: float) -> float:
        return deflated_sharpe_ratio(
            observed_sharpe=self.sharpe,
            trials=max(self.versuche, 1),
            sample_size=self.stichprobe,
            skew=schiefe,
            kurtosis=self.kopplung(schiefe),
        )

    def _kurve(self) -> tuple[np.ndarray, np.ndarray]:
        xs = np.linspace(self.von, self.bis, self.schritte)
        return xs, np.array([self.dsr_bei(float(x)) for x in xs])

    @property
    def hoechstwert(self) -> tuple[float, float]:
        """Bester erreichbarer DSR auf diesem Weg und die Schiefe dazu.

        **Abgetastet und nicht bisiziert.** Die Kurve steigt bis
        ``Schiefe = 2/SR`` und faellt danach wieder; eine Bisektion, die
        Monotonie voraussetzt, meldet an dieser Stelle "unerreichbar".
        """
        xs, ys = self._kurve()
        i = int(np.argmax(ys))
        return float(xs[i]), float(ys[i])

    @property
    def wendepunkt(self) -> float:
        """Wo der Nenner sein Minimum hat: ``2 / Sharpe je Trade``."""
        return 2.0 / self.sharpe if self.sharpe > 0 else float("inf")

    @property
    def schwelle(self) -> float | None:
        """Ab welcher Schiefe das Gate haelt - oder ``None``."""
        xs, ys = self._kurve()
        treffer = xs[ys >= self.ziel]
        return float(treffer[0]) if len(treffer) else None

    def urteil(self, heute: float) -> str:
        schwelle = self.schwelle
        schiefe_max, dsr_max = self.hoechstwert
        if schwelle is None:
            return (
                f"**{self.name}: nicht erreichbar.** Der hoechste Wert auf "
                f"diesem Weg ist {dsr_max:.4f} bei Schiefe {schiefe_max:.2f} - "
                f"die Schwelle von {self.ziel:.2f} liegt darueber. Mehr "
                f"Schiefe hilft ab da nicht mehr, weil die Woelbung "
                f"schneller waechst als der Vorteil."
            )
        return (
            f"**{self.name}: ab Schiefe {schwelle:.2f}** "
            f"({schwelle / heute - 1:+.0%} gegenueber {heute:.3f})."
        )


def wege(
    *,
    sharpe: float,
    stichprobe: int,
    versuche: int,
    woelbung_heute: float,
    linie: Formlinie | None = None,
) -> list[Formweg]:
    """Dieselbe Frage auf drei Kopplungen - von falsch bis gemessen.

    Die erste ist die bisherige Zerlegung und steht nur da, um den Abstand zu
    den beiden anderen zu zeigen.
    """
    gefunden = [
        Formweg(
            sharpe=sharpe, stichprobe=stichprobe, versuche=versuche,
            kopplung=lambda _s, w=woelbung_heute: w,
            name="Woelbung festgehalten",
        ),
        Formweg(
            sharpe=sharpe, stichprobe=stichprobe, versuche=versuche,
            kopplung=mindestwoelbung,
            name="entlang der harten Schranke",
        ),
    ]
    if linie is not None and linie.genug:
        gefunden.append(
            Formweg(
                sharpe=sharpe, stichprobe=stichprobe, versuche=versuche,
                kopplung=lambda s, li=linie: li.woelbung_bei(s) or mindestwoelbung(s),
                name="entlang der gemessenen Linie",
            )
        )
    return gefunden


def tabelle(wege_liste: list[Formweg], heute: float) -> str:
    zeilen = [
        f"{'Weg':<30} {'Max DSR':>9} {'bei':>7}  Schwelle",
        "-" * 66,
    ]
    for weg in wege_liste:
        schiefe_max, dsr_max = weg.hoechstwert
        schwelle = weg.schwelle
        text = (
            f"ab {schwelle:.2f} ({schwelle / heute - 1:+.0%})"
            if schwelle is not None
            else "nie erreicht"
        )
        zeilen.append(
            f"{weg.name:<30} {dsr_max:>9.4f} {schiefe_max:>7.2f}  {text}"
        )
    return "\n".join(zeilen)
