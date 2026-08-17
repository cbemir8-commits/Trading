"""Nadelspitze, Flanke oder Plateau - was das Gate nicht unterscheiden kann.

Warum die Frage gestellt gehoert
--------------------------------
``gate_parameter_plateau`` variiert jede Stellgroesse um plus/minus 20 % und
wertet das **Minimum** ueber alle Richtungen. Beim Bestand ergibt das 0,500
gegen eine Schwelle von 0,600, und die Botschaft lautet: "in dieser Richtung
steht die Strategie auf einer Nadelspitze, nicht auf einem Plateau."

Bei zwei Nachbarn je Richtung kann das Minimum aber nur 0, 0,5 oder 1,0
annehmen. Die Schwelle 0,6 heisst damit faktisch: **alle zwoelf Nachbarn
muessen tragen.** Es gibt keine Zwischenstufe, und aus einem einzelnen
Fehlschlag laesst sich nicht ablesen, ob dort eine Nadel steht oder eine
Kante.

Was die feinere Messung zeigt
-----------------------------
Zwoelf Faktoren von 0,70 bis 1,30 auf BTC + ETH, Gewinn in Konto-Einheiten:

    Faktor            0,70  0,75  0,80  0,85  0,90  0,95  1,05  1,10  1,15  1,20
    alle gemeinsam    1216  1226  1093  1638   799  1041   591   445   229  -104
    sma(period=50)    1070   961   868  1473   788   989   575   422   260  -104
    sma(period=200)    933   932   932   932   936   955   956   956   939   939
    roc(period=90)     963   948   957   926   953   955   962   958   957   957
    rsi(period=14)     964   964   964   964   962   962  1028  1028  1028  1025
    Vola-Fenster       772   796   802   877   681  1094  1020  1034   991   964

Basis bei Faktor 1,00: 958.

**Es ist keine Nadelspitze.** Die Strategie ist ueber den ganzen Bereich von
0,70 bis 1,15 profitabel - das sind Perioden von 35 bis 57 Tagen. Was das Gate
trifft, ist eine **Kante bei +20 %**, und dahinter faellt es ins Negative.

Und nur eine Stellgroesse wirkt ueberhaupt: ``sma(period=50)``. "Alle
gemeinsam" hat praktisch denselben Verlauf, die uebrigen vier sind flach.
Genau das steht auch im Docstring des Gates - vier wirkungslose Regler
koennten die eine Dimension niederstimmen, an der die Strategie haengt.
Deshalb wertet es das Minimum, und das ist richtig so.

Die unangenehme Haelfte
-----------------------
Der Bestand sitzt nicht auf dem Gipfel, sondern auf der abfallenden Flanke:
Bei Faktor 0,85 steht der Gewinn bei 1638 gegen 958 bei 1,00.

**Daraus folgt nicht, den Parameter zu verstellen.** Zwei Gruende:

Erstens schlaegt der Punkt die eigene Auswahl nicht. Gegen die Trendlinie
gerechnet liegt er +2,39 Reststreuungen darueber; bei zwoelf gemessenen
Punkten erwartet man ohnehin 1,67, und der Abstand entspricht z = 1,21. Das
ist dieselbe Lage wie das beste Paar in Befund 86 (3,585 gegen 3,549) - ein
Maximum knapp ueber dem Erwartungswert ist der Normalfall, kein Fund.

Zweitens waere es Rosinenpickerei: Zwoelf Werte durchprobieren und den besten
nehmen ist genau die Ueberanpassung, gegen die dieses Gate schuetzt. Es
kostete ausserdem Versuche.

Was daraus folgt
----------------
Das Gate scheitert zu Recht - bei +20 % kippt der Kandidat ins Negative, und
Robustheit in **beide** Richtungen ist die Anforderung. Aber die Botschaft
"Nadelspitze" beschreibt etwas anderes als das, was dort steht, und fuehrt
damit in dieselbe Richtung wie die Messlatte-Zeile aus Befund 91: Sie klingt
nach einer Diagnose und ist eine Fehldeutung.

Kostet keinen Versuch: Variiert werden die Parameter eines vorhandenen
Kandidaten - dasselbe, was das Gate ohnehin tut, nur feiner aufgeloest. Es
wird nichts ausgewaehlt und nichts verstellt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Ab so vielen gemessenen Faktoren traegt eine Aussage ueber die Form.
MINDESTPUNKTE = 6

#: Eine Stellgroesse gilt als wirkungslos, wenn ihr Gewinn ueber den ganzen
#: Bereich um weniger als das schwankt - gemessen am Betrag der Basis.
#: Vier der sechs Stellgroessen des Bestands liegen darunter.
WIRKUNGSLOS = 0.15


@dataclass(frozen=True, slots=True)
class Achse:
    """Eine Stellgroesse und ihr Gewinnverlauf ueber die Faktoren."""

    name: str
    faktoren: tuple[float, ...]
    gewinne: tuple[float, ...]
    basis: float
    """Der Gewinn bei Faktor 1,00 - der Punkt, an dem der Kandidat steht."""

    @property
    def spannweite(self) -> float:
        """Wie stark der Gewinn ueber den Bereich schwankt, relativ zur Basis."""
        if not self.gewinne or self.basis == 0:
            return 0.0
        return (max(self.gewinne) - min(self.gewinne)) / abs(self.basis)

    @property
    def wirkt(self) -> bool:
        """Bewegt diese Stellgroesse ueberhaupt etwas?

        Vier der sechs Stellgroessen des Bestands tun es nicht. Sie in eine
        Formaussage einzurechnen hiesse, Flachheit fuer Robustheit zu halten.
        """
        return self.spannweite >= WIRKUNGSLOS

    @property
    def tragfaehig(self) -> tuple[float, float] | None:
        """Der **zusammenhaengende** Bereich um 1,00, in dem es profitabel ist.

        Zusammenhaengend und nicht bloss "alle profitablen Punkte": Ein
        isolierter Gewinn jenseits einer Verlustzone sagt nichts ueber die
        Umgebung des Kandidaten aus.
        """
        if not self.faktoren or self.basis <= 0:
            return None
        paare = sorted(zip(self.faktoren, self.gewinne, strict=True))
        unten = oben = 1.0
        for f, g in reversed([p for p in paare if p[0] < 1.0]):
            if g <= 0:
                break
            unten = f
        for f, g in [p for p in paare if p[0] > 1.0]:
            if g <= 0:
                break
            oben = f
        return unten, oben

    @property
    def breite(self) -> float:
        bereich = self.tragfaehig
        return 0.0 if bereich is None else bereich[1] - bereich[0]

    @property
    def rauschen(self) -> float:
        """Wie stark benachbarte Faktoren voneinander abweichen.

        Die Groesse, an der sich entscheidet, ob ein "besserer" Punkt in der
        Landschaft etwas bedeutet. Beim Bestand liegt sie ueber dem Abstand
        zum vermeintlichen Optimum.
        """
        if len(self.gewinne) < 2:
            return 0.0
        paare = sorted(zip(self.faktoren, self.gewinne, strict=True))
        werte = np.array([g for _, g in paare], dtype=float)
        return float(np.mean(np.abs(np.diff(werte))))

    @property
    def bestes_faktor(self) -> float:
        paare = sorted(
            zip(self.faktoren, self.gewinne, strict=True), key=lambda p: -p[1]
        )
        return paare[0][0] if paare else 1.0

    @property
    def besser_als_die_basis(self) -> float:
        return max(self.gewinne, default=self.basis) - self.basis

    def _gerade(self) -> tuple[float, float, float] | None:
        """Steigung, Abschnitt und Reststreuung der Trendlinie.

        Der Trend ist die belastbare Haelfte einer verrauschten Landschaft.
        Einzelne Punkte streuen darum herum, und genau diese Streuung ist der
        Massstab dafuer, ob ein "besserer" Punkt etwas bedeutet.
        """
        if len(self.faktoren) < 4:
            return None
        f = np.array(self.faktoren, dtype=float)
        g = np.array(self.gewinne, dtype=float)
        if f.std() == 0:
            return None
        steigung, abschnitt = (float(x) for x in np.polyfit(f, g, 1))
        rest = g - (steigung * f + abschnitt)
        streuung = float(rest.std(ddof=2))
        return steigung, abschnitt, streuung

    @property
    def optimum_ist_belegt(self) -> bool:
        """Liegt der beste Punkt weiter ueber dem Trend, als Auswahl erklaert?

        **Nicht gegen den Nachbarsprung geprueft** - das war der erste Anlauf
        und ist zu schwach. Der beste von zwoelf verrauschten Punkten liegt
        systematisch ueber dem Trend, auch wenn nichts dahintersteckt; das ist
        derselbe Winner's Curse wie in Befund 71 und 86.

        Geprueft wird gegen die Extremwertschranke ueber die Zahl der
        gemessenen Punkte - und weil die der **Erwartungswert** des Maximums
        ist, zaehlt der Abstand in Einheiten seiner eigenen Streuung. Fuer das
        Maximum von n Normalen betraegt die rund ``1/c(n)``.

        Beim Bestand: Residuum +2,39 gegen eine Schranke von 1,67, also
        z = 1,21. **Kein Beleg** - dieselbe Lage wie das beste Paar in
        Befund 86, wo 3,585 gegen 3,549 stand.
        """
        return self.auffaelligkeit() is not None and self.auffaelligkeit() >= 2.0

    def auffaelligkeit(self) -> float | None:
        """Wie weit der beste Punkt ueber dem liegt, was Auswahl erklaert.

        In Einheiten der Streuung des Maximums, also als z-Wert. Ab 2,0 gilt
        er als belegt; darunter ist er das, was best-of-n ohnehin liefert.
        """
        gerade = self._gerade()
        if gerade is None:
            return None
        from research.wettrennen import extremwert

        steigung, abschnitt, streuung = gerade
        if streuung <= 0:
            return None
        f = np.array(self.faktoren, dtype=float)
        g = np.array(self.gewinne, dtype=float)
        rest = (g - (steigung * f + abschnitt)) / streuung
        schranke = extremwert(len(f))
        if schranke <= 0:
            return None
        return float((rest.max() - schranke) * schranke)

    @property
    def form(self) -> str:
        """Nadelspitze, Flanke, Plateau oder wirkungslos."""
        if not self.wirkt:
            return "wirkungslos"
        if self.breite <= 0.15:
            return "Nadelspitze"
        paare = sorted(zip(self.faktoren, self.gewinne, strict=True))
        f = np.array([p[0] for p in paare])
        g = np.array([p[1] for p in paare])
        if f.std() == 0 or g.std() == 0:
            return "Plateau"
        steigung = float(np.corrcoef(f, g)[0, 1])
        return "Flanke" if abs(steigung) >= 0.6 else "Plateau"


@dataclass(slots=True)
class Landschaft:
    """Alle Stellgroessen eines Kandidaten, feiner als das Gate sie misst."""

    achsen: list[Achse] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return bool(self.achsen) and all(
            len(a.faktoren) >= MINDESTPUNKTE for a in self.achsen
        )

    @property
    def wirksame(self) -> list[Achse]:
        return [a for a in self.achsen if a.wirkt]

    @property
    def engste(self) -> Achse | None:
        """Die Achse mit dem schmalsten tragfaehigen Bereich - das ist die,
        an der das Gate haengt."""
        wirksam = self.wirksame
        return min(wirksam, key=lambda a: a.breite) if wirksam else None

    def tabelle(self) -> str:
        if not self.achsen:
            return "Keine Achsen gemessen."
        zeilen = [
            f"{'Stellgroesse':<22} {'Form':<12} {'traegt von..bis':>16} "
            f"{'Rauschen':>9} {'Spanne':>8}",
            "-" * 72,
        ]
        for a in sorted(self.achsen, key=lambda x: x.breite):
            bereich = a.tragfaehig
            spanne = (
                f"{bereich[0]:.2f}..{bereich[1]:.2f}" if bereich else "keiner"
            )
            zeilen.append(
                f"{a.name[:22]:<22} {a.form:<12} {spanne:>16} "
                f"{a.rauschen:>9.0f} {a.spannweite:>7.0%}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return (
                "Zu wenige Faktoren gemessen - ueber die Form der Landschaft "
                "laesst sich nichts sagen."
            )
        wirksam = self.wirksame
        if not wirksam:
            return (
                f"**Keine der {len(self.achsen)} Stellgroessen bewegt etwas.** "
                f"Das ist kein Plateau, sondern ein Kandidat, dessen Parameter "
                f"nichts tun - die Robustheit waere hier keine Eigenschaft, "
                f"sondern eine Folge von Wirkungslosigkeit."
            )

        eng = self.engste
        teile = [
            f"**{len(wirksam)} von {len(self.achsen)} Stellgroessen wirken "
            f"ueberhaupt.** Die uebrigen aendern den Gewinn um weniger als "
            f"{WIRKUNGSLOS:.0%} - dass die Strategie gegen sie unempfindlich "
            f"ist, sagt nichts ueber ihre Robustheit."
        ]
        if eng is not None:
            bereich = eng.tragfaehig
            spanne = f"{bereich[0]:.2f} bis {bereich[1]:.2f}" if bereich else "keinen"
            teile.append(
                f"Am engsten ist '{eng.name}': **{eng.form}**, profitabel von "
                f"{spanne}. Das Gate prueft bei 0,80 und 1,20 - liegt eine "
                f"Kante dazwischen, sieht es einen Fehlschlag und kann "
                f"Nadelspitze und Kante nicht auseinanderhalten."
            )
            if eng.form == "Flanke":
                teile.append(
                    "**Eine Flanke ist keine Nadelspitze.** Der Gewinn faellt "
                    "ueber den Bereich monoton, statt neben dem Kandidaten "
                    "einzubrechen. Der Kandidat steht damit nicht auf einem "
                    "Zufallstreffer, sondern am Rand eines breiten Gebiets."
                )
            if not eng.optimum_ist_belegt and eng.besser_als_die_basis > 0:
                teile.append(
                    f"Der beste gemessene Punkt liegt bei Faktor "
                    f"{eng.bestes_faktor:.2f} und {eng.besser_als_die_basis:.0f} "
                    f"ueber der Basis - **er schlaegt aber die eigene Auswahl "
                    f"nicht** (z = {eng.auffaelligkeit():.2f}). Bei "
                    f"{len(eng.faktoren)} gemessenen Punkten liegt das Maximum "
                    f"ohnehin ueber dem Trend. Wer den Parameter dorthin "
                    f"stellt, liest ein Rauschen und zahlt dafuer Versuche."
                )
        return "\n\n".join(teile)


def baue(kurven: dict[str, list[tuple[float, float | None]]], *, basis: float):
    """Aus gemessenen Gewinnkurven eine Landschaft bauen.

    ``kurven`` bildet Stellgroessennamen auf ``(Faktor, Gewinn)``-Paare ab;
    ``None`` als Gewinn heisst "dieser Nachbar ist mit dem Kandidaten
    identisch" und faellt heraus.
    """
    achsen = []
    for name, punkte in kurven.items():
        gefiltert = [(f, g) for f, g in punkte if g is not None]
        if not gefiltert:
            continue
        achsen.append(
            Achse(
                name=name,
                faktoren=tuple(f for f, _ in gefiltert),
                gewinne=tuple(float(g) for _, g in gefiltert),
                basis=basis,
            )
        )
    return Landschaft(achsen=achsen)


__all__ = ["MINDESTPUNKTE", "WIRKUNGSLOS", "Achse", "Landschaft", "baue"]
