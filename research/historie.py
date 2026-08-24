"""Waechst die Evidenz mit der Historie - und wie schnell?

Warum das die Frage ist
-----------------------
Von den vier Familien, aus denen noch Evidenz kommen koennte, sind drei
gemessen erschoepft (Befund 111): Kosten, Fenster, Regler. Die vierte ist die
**Zahl unabhaengiger Beobachtungen**, und sie ist die einzige, die den
Deflated Sharpe ohne Suche hebt - Evidenz sammeln ist kein Versuch.

Genau davor steht ein geschlossener Weg: *"Mehr Historie - Sharpe je Trade
faellt, Huerde steigt"* (Befund 14). Das war 117 Befunde her, am
Perpetual-Punkt und bei einem viel niedrigeren Zaehlerstand.

Was gemessen ist
----------------
Derselbe Kandidat, Spot-Punkt, 198 Versuche, alle Fenster enden am selben
Tag; nur der Anfang wandert (BTC + ETH, Tageskerzen):

        ab       Tage  Trades   eff    Guete     DSR   Gates
    2017-08-16   3277     152   152   0,2765  0,8640    9/11   <- Referenz
    2018-08-16   2912     137   136   0,2734  0,7659    9/11
    2019-08-16   2547     111   103   0,2705  0,4792    9/11
    2020-03-30   2320     103   103   0,2396  0,2969    8/11
    2021-08-16   1816      72    72   0,2711  0,2209    9/11
    2022-08-16   1451      52    52   0,2903  0,1347    9/11

Zwei Dinge stehen darin, und beide sind wichtig.

**Erstens: die Guete haengt nicht an der Historienlaenge.** 0,2765 / 0,2734 /
0,2705 / 0,2396 / 0,2711 / 0,2903 - kein Trend, nur Streuung um 0,27. Wer die
Historie kuerzt, bekommt keine bessere Regel, sondern weniger Evidenz.

Das ist **keine Widerlegung von Befund 14.** Der hat in die andere Richtung
gemessen - mehr Historie, weiter zurueck - und diese Richtung gibt es hier
nicht mehr: Der gemeinsame Bereich beginnt am 16.08.2017, weil dort die
ETH-Reihe beginnt. Gemessen ist die Richtung, die fuer die naechste
Entscheidung zaehlt.

**Zweitens: der Deflated Sharpe haengt fast nur an n.** Bei gleichbleibender
Guete faellt er von 0,8640 auf 0,1347, wenn die Historie von 3277 auf 1451
Tage schrumpft. Er misst Evidenz, nicht Vorteilsgroesse (siehe
``decke.Stichprobenbedarf``).

Was daraus folgt
----------------
Die Sammelrate ueber die vier laengsten Fenster ist **44,7 unabhaengige
Beobachtungen je 1000 Tage** (46,4 / 46,7 / 40,4 / 44,4). Die kurzen Fenster
liegen darunter (39,6 / 35,8) - dort frisst die Aufwaermphase des Walk-Forward
einen groesseren Anteil, weshalb sie in der Rate nichts zu suchen haben.

Gezaehlt wird die **effektive** Stichprobe und nicht die rohe Trade-Zahl. Der
Unterschied ist klein, aber er war der erste Fehler in diesem Befund: Auf
rohen Trades gerechnet kaeme 45,5 heraus, und ein Test hat es gefunden.

Bei Guete 0,2765, Schiefe 3,47 und Woelbung 15,96 traegt die Schwelle ab
**n = 181**. Es fehlen 29 Beobachtungen, und das sind **649 Tage - rund 1,8
Jahre**.

Diese Tage koennen nicht aus der Vergangenheit kommen; die ist ausgeschoepft.
Sie koennen nur aus der Zukunft kommen.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Historienkurve", "Historienstufe"]


@dataclass(frozen=True, slots=True)
class Historienstufe:
    """Ein Startdatum und was der Kandidat von dort bis zum Ende zusammenbringt."""

    von: str
    tage: int
    trades: int
    effektiv: int
    guete: float
    dsr: float
    bestanden: int
    gesamt: int

    def __post_init__(self) -> None:
        if self.tage <= 0:
            raise ValueError(f"Fenster ab {self.von} hat keine Tage.")
        if self.effektiv > self.trades:
            raise ValueError(
                f"Fenster ab {self.von}: {self.effektiv} unabhaengige "
                f"Beobachtungen aus {self.trades} Trades - die effektive "
                f"Stichprobe kann die rohe nicht uebersteigen."
            )

    @property
    def je_tausend_tage(self) -> float:
        """Sammelrate: unabhaengige Beobachtungen je 1000 Tage Historie."""
        return 1000.0 * self.effektiv / self.tage

    def als_zeile(self) -> str:
        return (
            f"{self.von:>10} {self.tage:>5} {self.trades:>6} {self.effektiv:>5} "
            f"{self.guete:>7.4f} {self.dsr:>7.4f} {self.bestanden:>3}/{self.gesamt}"
        )


@dataclass(frozen=True, slots=True)
class Historienkurve:
    """Mehrere Startdaten, alle mit demselben Ende.

    **Absichtlich ohne eine Methode, die das beste Fenster zurueckgibt** -
    dieselbe Sperre wie in ``decke.Fensterlage``. Referenz ist immer das
    **laengste** Fenster, weil ein kuerzeres nie mehr weiss.
    """

    stufen: tuple[Historienstufe, ...] = ()
    ziel: int | None = None

    @property
    def sortiert(self) -> tuple[Historienstufe, ...]:
        """Vom laengsten zum kuerzesten Fenster."""
        return tuple(sorted(self.stufen, key=lambda s: -s.tage))

    @property
    def referenz(self) -> Historienstufe | None:
        """Das laengste Fenster - der Stand, gegen den alles andere zaehlt."""
        return self.sortiert[0] if self.stufen else None

    def guete_haengt_an_der_laenge(self, spielraum: float = 0.05) -> bool | None:
        """Faellt die Guete systematisch, wenn die Historie waechst?

        Geprueft wird die Aussage aus Befund 14 in der Richtung, die hier
        gemessen werden kann. ``True`` heisst: Das laengste Fenster hat eine
        merklich schlechtere Guete als das kuerzeste - dann kostet Historie
        Qualitaet. ``False`` heisst: Der Unterschied bleibt im Spielraum.
        """
        geordnet = self.sortiert
        if len(geordnet) < 2:
            return None
        laengstes, kuerzestes = geordnet[0], geordnet[-1]
        if kuerzestes.guete <= 0:
            return None
        return laengstes.guete < kuerzestes.guete * (1.0 - spielraum)

    def sammelrate(self, mindesttage: int = 2000) -> float | None:
        """Unabhaengige Beobachtungen je 1000 Tage, ueber die langen Fenster.

        ``mindesttage`` schliesst die kurzen Fenster aus, und das ist kein
        Zurechtlegen: Der Walk-Forward braucht eine Aufwaermphase, die bei
        einem kurzen Fenster einen groesseren Anteil frisst. Gemessen liegen
        die kurzen Fenster deshalb systematisch unter den langen (39,6 und
        35,8 gegen 43,6 bis 47,0) - sie messen die Aufwaermphase mit.
        """
        lang = [s for s in self.stufen if s.tage >= mindesttage]
        if not lang:
            return None
        return 1000.0 * sum(s.effektiv for s in lang) / sum(s.tage for s in lang)

    def fehlende_beobachtungen(self) -> int | None:
        """Wie viele unabhaengige Beobachtungen zum Ziel fehlen."""
        ref = self.referenz
        if ref is None or self.ziel is None:
            return None
        return max(self.ziel - ref.effektiv, 0)

    def fehlende_tage(self, mindesttage: int = 2000) -> int | None:
        """Wie viele Tage das bei der gemessenen Rate waeren.

        **Das ist eine Hochrechnung, keine Messung.** Die Rate ist gemessen;
        dass sie so weiterlaeuft, ist angenommen. Befund 124 hat gezeigt, was
        ein Punktschaetzer aus einer solchen Rechnung wert ist - dort spannte
        der Fehlerbalken von "nie" bis 199 Versuche. Die Zahl hier taugt fuer
        die Groessenordnung und nicht fuer einen Termin.
        """
        fehlt, rate = self.fehlende_beobachtungen(), self.sammelrate(mindesttage)
        if fehlt is None or not rate:
            return None
        return round(1000.0 * fehlt / rate)

    def urteil(self) -> str:
        ref = self.referenz
        if ref is None:
            return "Keine Fenster gemessen - dazu ist nichts zu sagen."
        if len(self.stufen) < 2:
            return (
                f"Nur ein Fenster ({ref.von}, {ref.tage} Tage) - eine Kurve "
                f"braucht zwei."
            )
        teile = []
        haengt = self.guete_haengt_an_der_laenge()
        kuerzestes = self.sortiert[-1]
        if haengt:
            teile.append(
                f"**Historie kostet Qualitaet**: Guete {ref.guete:.4f} auf "
                f"{ref.tage} Tagen gegen {kuerzestes.guete:.4f} auf "
                f"{kuerzestes.tage} - Befund 14 zeigt sich auch hier."
            )
        elif haengt is False:
            teile.append(
                f"**Die Guete haengt nicht an der Laenge**: {ref.guete:.4f} auf "
                f"{ref.tage} Tagen gegen {kuerzestes.guete:.4f} auf "
                f"{kuerzestes.tage}. Kuerzen bringt keine bessere Regel, nur "
                f"weniger Evidenz."
            )
        teile.append(
            f"Der Deflated Sharpe faellt dabei von {ref.dsr:.4f} auf "
            f"{kuerzestes.dsr:.4f} - er misst Evidenz, nicht Vorteilsgroesse."
        )
        tage = self.fehlende_tage()
        if tage is not None:
            fehlt = self.fehlende_beobachtungen()
            rate = self.sammelrate()
            teile.append(
                f"Bis zur Schwelle fehlen {fehlt} Beobachtungen; bei "
                f"{rate:.1f} je 1000 Tagen sind das rund {tage} Tage "
                f"({tage / 365.25:.1f} Jahre) - hochgerechnet, nicht gemessen."
            )
        return " ".join(teile)
