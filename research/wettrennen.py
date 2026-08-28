"""Suchen hebt die Huerde. Holt der beste Fund sie je ein?

Warum die Frage jetzt dran ist
------------------------------
Nach Befund 70 sind drei der vier Wege zum haertesten Gate geschlossen:
Woelbung (unter 1 gibt es nichts), Schiefe (die Kopplung an die Woelbung),
Trade-Zahl (die Kopplung an die Qualitaet, Befund 54). Es bleibt einer -
**die Qualitaet je Trade, +13 %** -, und alle Regler, die daran drehen, sind
ausgemessen und geschlossen.

Bleibt also: weitersuchen. Und genau da sitzt ein Problem, das dieses Projekt
zwar seit langem kennt, aber nie ausgerechnet hat. Der Deflated Sharpe zieht
von jedem Fund ab, was Zufall bei so vielen Versuchen ohnehin hergibt. **Wer
sucht, hebt die Latte, ueber die er springen muss.**

Zwei Groessen, dieselbe Formel
------------------------------
Beide wachsen mit der Zahl der Versuche, und beide ueber dieselbe
Extremwertkonstante ``c(N)`` aus Bailey/Lopez de Prado:

    Huerde       ~ A + 1/sqrt(n-1) * c(N)     was Zufall hergibt
    bester Fund  ~ Mittel + Streuung * c(N)   was Suchen hergibt

Die Frage ist damit keine Frage des Fleisses, sondern ein Vergleich zweier
Vorfaktoren:

    **Die Suche gewinnt genau dann, wenn die Streuung echter Regelideen
    groesser ist als 1/sqrt(n-1) - die Streuung des reinen Zufalls.**

``n`` ist die **effektive** Stichprobe, nicht die rohe Trade-Zahl - das Gate
rechnet mit ihr, also auch dieser Vergleich.

**Und daran haengt hier alles** (Befund 142). Bei den 154 rohen Trades des
Kandidaten stuenden 0,0808; bei seinen 118 unabhaengigen Beobachtungen sind es
0,0925. Die Ideenstreuung, aus dem Verlauf zurueckgerechnet, liegt bei 0,0930:

    Stichprobe          Nullstreuung   Ideenstreuung   Vorsprung
    154 (roh)                 0,0808          0,0930      +15,1 %
    118 (effektiv)            0,0925          0,0930       +0,6 %

Der **Punktschaetzer** des Vorsprungs faellt damit von fuenfzehn Prozent auf
einen halben.

Mehr als der Punktschaetzer ist es nicht. Der 90-%-Bereich der Ideenstreuung
reicht von 0,0757 bis 0,1178 - er haengt an Bestwert und Versuchszahl, **nicht
an ``n``** -, und beide Nullstreuungen liegen darin:

    0,0757 |-------0,0808---------0,0925----------| 0,1178

Ob Suchen ueberhaupt besser ist als Wuerfeln, war aus diesem Verlauf also auch
vorher nicht zu entscheiden. Gefallen ist der beste Schaetzwert, nicht die
Bestimmtheit - die gab es nie.

Liegt die Ideenstreuung unter der Nullstreuung, wird der Abstand nie
geschlossen, egal wie lange gesucht wird. Das ist kein Mangel der Umsetzung,
sondern genau die Eigenschaft, fuer die das Gate gebaut wurde: Es
neutralisiert die Zufallssuche exakt.

Der Fehler, der beim Rechnen zuerst herauskam
---------------------------------------------
Der erste Anlauf schaetzte Mittel und Streuung aus den Kandidaten, die in der
Bestenliste stehen - sechs Regelfamilien, Mittel 0,1685, Streuung 0,1019. Das
ergab: schon zehn weitere Versuche bringen einen Fund von 0,329, die Huerde
liegt bei 0,293, also lohnt sich Suchen sofort.

Diese Schaetzung widerlegt sich selbst. Mit ihr waere der beste aus 166
Versuchen bei **0,4440** zu erwarten gewesen; tatsaechlich sind es 0,2569.
Die sechs sind die Ueberlebenden aus 166 Versuchen, nicht sechs Ziehungen -
ihre Streuung ist die der Elite, ihr Mittel viel zu hoch.

Deshalb wird hier andersherum gerechnet: **Die Streuung wird aus dem eigenen
Verlauf kalibriert.** Was muss sie gewesen sein, damit 166 Versuche genau den
Bestwert hervorbringen, den sie hervorgebracht haben? Und ein
Konsistenztest haelt fest, dass eine Schaetzung, die den eigenen Verlauf nicht
erklaert, verworfen wird.

Was das Modell nicht kann
-------------------------
* Es setzt **unabhaengige Ziehungen** voraus. Die meisten Versuche dieses
  Projekts waren Reglerscans - Varianten des Bestands, die in derselben
  Nachbarschaft nachsehen. Der echte Fortschritt ist also **langsamer** als
  hier gerechnet, nicht schneller.
* Es kalibriert an **einem** Punkt. Mehr gibt es nicht: Der Bestwert nach 166
  Versuchen ist die einzige Beobachtung dieser Art, die vorliegt.
* Das Mittel einer neuen Regelidee ist eine **Annahme**. Deshalb steht es als
  Parameter da und nicht als Zahl im Code, und ``spanne`` zeigt, wie stark das
  Ergebnis daran haengt.

Kostet keinen Versuch: Gerechnet wird ueber Versuche, nicht mit ihnen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

from research.gates import GateThresholds

#: Euler-Mascheroni, wie in ``gates.deflated_sharpe_ratio``. Dieselbe Konstante
#: aus demselben Grund - es ist dieselbe Extremwertrechnung.
EULER_MASCHERONI = 0.5772156649015329

ZIEL = GateThresholds().min_deflated_sharpe


def extremwert(versuche: int) -> float:
    """``c(N)``: das erwartete Maximum von N Standardnormal-Ziehungen.

    Waechst wie ``sqrt(2 ln N)`` - also **logarithmisch langsam**. Genau
    deshalb ist "mehr suchen" ein so schwacher Hebel: Eine Verdopplung der
    Versuche bringt immer weniger.
    """
    if versuche <= 1:
        return 0.0
    normal = NormalDist()
    return (1 - EULER_MASCHERONI) * normal.inv_cdf(1 - 1 / versuche) + (
        EULER_MASCHERONI * normal.inv_cdf(1 - 1 / (versuche * math.e))
    )


def nullstreuung(trades: int) -> float:
    """Die Rate, mit der die Huerde steigt: ``1/sqrt(n-1)``.

    Das ist die Streuung des Sharpe-Schaetzers unter der Nullhypothese - und
    damit der Massstab, den eine Ideenquelle schlagen muss, um ueberhaupt
    anzukommen.
    """
    return (1.0 / (trades - 1)) ** 0.5 if trades > 1 else float("inf")


def kalibriere(*, bester: float, versuche: int, mittel: float) -> float | None:
    """Welche Streuung erklaert diesen Verlauf?

    ``bester`` ist der hoechste Sharpe je Trade nach ``versuche`` Versuchen.
    Aus ``bester = mittel + streuung * c(versuche)`` folgt die Streuung.

    ``None``, wenn das angenommene Mittel bereits ueber dem Bestwert liegt -
    dann ist die Annahme mit dem Verlauf unvereinbar, und eine negative
    Streuung waere keine Antwort, sondern ein Rechenfehler mit Vorzeichen.
    """
    konstante = extremwert(versuche)
    if konstante <= 0 or bester <= mittel:
        return None
    return (bester - mittel) / konstante


@dataclass(frozen=True, slots=True)
class Rennen:
    """Huerde und erwarteter bester Fund, beide als Funktion der Versuche."""

    bester: float
    versuche: int
    trades: int
    mittel: float = 0.0
    """Der Sharpe je Trade einer **typischen** neuen Regelidee.

    Eine Annahme, keine Messung. 0 heisst: Eine zufaellig gewaehlte Regel hat
    keinen Vorteil. Negativ waere ebenso vertretbar - Gebuehren und Spread
    kosten, bevor irgendetwas verdient ist -, und **negativ ist die
    guenstigere Annahme**: Sie verlangt eine groessere Streuung, um denselben
    Bestwert zu erklaeren, und laesst die Suche schneller aufholen.
    """

    schub: float = 0.0
    """Ein Niveauschub, der **nicht** aus der Suche stammt.

    **Die Falle, gegen die dieses Feld gebaut ist.** Befund 108 hat gemessen,
    dass der Wegfall des Funding die Guete je Trade von 0,2597 auf 0,2765 hebt.
    Es liegt nahe, den besseren Wert einfach als ``bester`` einzusetzen - und
    genau das waere falsch: Dann kalibriert ``streuung`` die **Ideenstreuung
    der Suche** an einem Gewinn, den die Suche nicht erbracht hat.

    Der Unterschied ist nicht klein. Fuer den Spitzenkandidaten unter Spot:

        naiv (0,2765 als ``bester``)          holt auf bei   2.535 Versuchen
        richtig (0,2597 + Schub 0,0168)       holt auf bei   5.968 Versuchen

    Die naive Rechnung laesst die Suche **2,4-mal produktiver** aussehen, als
    sie ist. Deshalb gehoert in ``bester`` das, was die Suche hervorgebracht
    hat, und Kostenaenderungen kommen hierher.
    """

    @property
    def streuung(self) -> float | None:
        return kalibriere(
            bester=self.bester, versuche=self.versuche, mittel=self.mittel
        )

    @property
    def nullstreuung(self) -> float:
        return nullstreuung(self.trades)

    @property
    def schneller_als_die_huerde(self) -> bool:
        """Waechst der beste Fund schneller als das, was Zufall hergibt?

        Die ganze Frage in einer Zeile. Beide wachsen mit ``c(N)``; es
        entscheidet allein, welcher Vorfaktor groesser ist.
        """
        streuung = self.streuung
        return streuung is not None and streuung > self.nullstreuung

    def wo_holt_sie_auf(self, *, obergrenze: int = 10**9) -> str:
        """Die Stelle als Text - und "nie" nur, wenn es wirklich nie ist.

        Ein Schnittpunkt jenseits der durchsuchten Grenze ist etwas anderes
        als keiner: Liegt die Ideenstreuung ueber dem Zufall, kommt die Suche
        irgendwann an, nur eben spaeter als hier gerechnet. Das als "nie"
        auszugeben waere schaerfer als die Rechnung hergibt.
        """
        if not self.schneller_als_die_huerde:
            return "nie"
        schnitt = self.schnittpunkt(obergrenze=obergrenze)
        if schnitt is None:
            return f"jenseits von {obergrenze:.0e}"
        return f"{schnitt:,} Versuche".replace(",", ".")

    def unsicherheit(self, *, irrtum: float = 0.10) -> str:
        """Der Fehlerbalken an der Kalibrierung - Befund 124.

        **Ohne ihn suggeriert die Zahl eine Genauigkeit, die sie nicht hat.**
        Die Ideenstreuung wird aus einem einzigen Wert zurueckgerechnet, und
        der beobachtete Bestwert ist selbst eine Zufallsgroesse. Bei 198
        Versuchen betraegt die relative Streuung der Rueckrechnung 14,3 %,
        und ueber diesen Bereich springt der Schnittpunkt von "nie" bis
        "jetzt".

        Der Text nennt beides: die Spanne und, wenn sie das Urteil umwirft,
        dass sie es tut.
        """
        streuung = self.streuung
        if streuung is None:
            return ""
        unten, oben = kalibrierbereich(streuung, self.versuche, irrtum=irrtum)
        rel = kalibrierunsicherheit(self.versuche)

        satz = (
            f"\n\n**Diese Kalibrierung kommt aus einem einzigen Wert** - dem "
            f"beobachteten Bestwert - und der streut selbst. Bei "
            f"{self.versuche} Versuchen liegt die relative Streuung der "
            f"Rueckrechnung bei {rel:.1%}; der {1 - irrtum:.0%}-Bereich der "
            f"Ideenstreuung reicht von {unten:.4f} bis {oben:.4f}."
        )
        if unten <= self.nullstreuung <= oben:
            satz += (
                f" **Die Nullstreuung von {self.nullstreuung:.4f} liegt darin.** "
                f"Damit ist auch 'die Suche holt nie auf' mit dem Verlauf "
                f"vereinbar - und ebenso, dass sie schon fast angekommen "
                f"ist. Die Zahl unten ist ein Punktschaetzer, keine Prognose."
            )
        return satz

    def huerde(self, versuche: int) -> float | None:
        """Der noetige Sharpe je Trade bei diesem Versuchsstand."""
        from research.suchbudget import Budget

        return Budget(versuche=versuche).noetig_bei(self.trades)

    def erwartet(self, versuche: int) -> float | None:
        """Der beste Fund, der aus so vielen Versuchen zu erwarten waere.

        Der Niveauschub kommt **oben drauf** und geht nicht in die Streuung
        ein: Er hebt jeden Fund gleichermassen, macht die Suche aber nicht
        treffsicherer.
        """
        streuung = self.streuung
        if streuung is None:
            return None
        return self.mittel + streuung * extremwert(versuche) + self.schub

    def abstand(self, versuche: int) -> float | None:
        huerde, erwartet = self.huerde(versuche), self.erwartet(versuche)
        if huerde is None or erwartet is None:
            return None
        return erwartet - huerde

    def erklaert_den_verlauf(
        self, *, mittel: float, streuung: float, spielraum: float = 0.05
    ) -> bool:
        """Wuerde diese Schaetzung den bisherigen Bestwert hervorbringen?

        **Der Test, an dem die naheliegende Schaetzung scheitert.** Wer Mittel
        und Streuung aus den Kandidaten der Bestenliste nimmt, misst die
        Ueberlebenden aus 166 Versuchen und nicht 166 Ziehungen. Mit jenen
        Zahlen waere der Bestwert bei 0,444 zu erwarten gewesen statt bei
        0,257 - die Schaetzung erklaert den eigenen Verlauf nicht und ist
        damit erledigt.
        """
        erwartet = mittel + streuung * extremwert(self.versuche)
        return abs(erwartet - self.bester) <= spielraum

    def schnittpunkt(self, *, obergrenze: int = 10**9) -> int | None:
        """Bei wie vielen Versuchen der erwartete Fund die Huerde einholt.

        ``None``, wenn nie - dann waechst der beste Fund langsamer als das,
        was Zufall ohnehin hergibt, und laengeres Suchen ist nicht schwierig,
        sondern aussichtslos.
        """
        if not self.schneller_als_die_huerde:
            return None
        oben = self.abstand(obergrenze)
        if oben is None or oben < 0:
            return None
        tief, hoch = self.versuche, obergrenze
        while hoch - tief > 1:
            mitte = (tief + hoch) // 2
            wert = self.abstand(mitte)
            if wert is None or wert < 0:
                tief = mitte
            else:
                hoch = mitte
        return hoch

    def tabelle(self, staende: tuple[int, ...]) -> str:
        # Spaltenname ohne eckige Klammern: Die Ausgabe laeuft durch ``rich``,
        # und "E[bester]" wuerde dort als Markup verschwinden.
        zeilen = [
            f"{'weitere':>8} {'Stand':>8} {'Huerde':>9} {'erwartet':>11} "
            f"{'Abstand':>9}",
            "-" * 50,
        ]
        for weiter in staende:
            stand = self.versuche + weiter
            huerde, erwartet = self.huerde(stand), self.erwartet(stand)
            if huerde is None or erwartet is None:
                continue
            zeilen.append(
                f"{weiter:>8} {stand:>8} {huerde:>9.4f} {erwartet:>11.4f} "
                f"{erwartet - huerde:>+9.4f}"
            )
        return "\n".join(zeilen)

    def urteil(self, *, budget: int | None = None) -> str:
        streuung = self.streuung
        if streuung is None:
            return (
                f"Das angenommene Mittel von {self.mittel:+.3f} liegt ueber "
                f"dem Bestwert {self.bester:.4f} - mit dieser Annahme laesst "
                f"sich der Verlauf nicht erklaeren."
            )

        grundlage = (
            f"Aus dem eigenen Verlauf kalibriert: {self.versuche} Versuche "
            f"haben {self.bester:.4f} hervorgebracht, das entspricht einer "
            f"Ideenstreuung von {streuung:.4f}. Die Huerde steigt mit "
            f"{self.nullstreuung:.4f} - der Streuung des reinen Zufalls."
            f"{self.unsicherheit()}"
        )

        if not self.schneller_als_die_huerde:
            return (
                f"**Weitersuchen holt den Abstand nie ein.** {grundlage} Der "
                f"beste Fund waechst also langsamer als das, was Zufall "
                f"ohnehin hergibt. Das ist kein Mangel der Umsetzung, sondern "
                f"genau die Eigenschaft, fuer die das Gate gebaut ist - es "
                f"neutralisiert die Zufallssuche exakt."
            )

        wo = f"bei rund {self.wo_holt_sie_auf()}"
        preis = ""
        if budget is not None:
            offen = self.abstand(budget)
            if offen is not None:
                preis = (
                    f" Beim Abbruch des Suchbudgets bei {budget} Versuchen "
                    f"fehlen noch {abs(offen):.4f}."
                )
        return (
            f"**Weitersuchen holt auf - aber {wo}.** {grundlage} Die "
            f"Ideenstreuung liegt damit "
            f"{streuung / self.nullstreuung - 1:+.0%} ueber dem Zufall, und "
            f"weil beide mit ``sqrt(ln N)`` wachsen, dauert der Vorsprung "
            f"entsprechend lange.{preis}\n\n"
            f"Daraus folgt: **Mehr Versuche sind der schwache Hebel.** Der "
            f"Gewinn ist logarithmisch, der Preis linear. Was zaehlt, ist die "
            f"Guete der Ideen, nicht ihre Zahl."
        )


def spanne(
    *, bester: float, versuche: int, trades: int, mittelwerte: tuple[float, ...]
) -> str:
    """Wie stark das Ergebnis an der Annahme ueber das Mittel haengt.

    Die einzige freie Groesse im Modell bekommt eine eigene Tabelle, statt
    dass eine Zahl im Text so dasteht, als waere sie gemessen.
    """
    zeilen = [
        f"{'Mittel':>8} {'Streuung':>10} {'ueber Zufall':>13}  Suche holt auf",
        "-" * 58,
    ]
    for mittel in mittelwerte:
        rennen = Rennen(
            bester=bester, versuche=versuche, trades=trades, mittel=mittel
        )
        streuung = rennen.streuung
        if streuung is None:
            zeilen.append(f"{mittel:>+8.2f} {'-':>10} {'-':>13}  unvereinbar")
            continue
        zeilen.append(
            f"{mittel:>+8.2f} {streuung:>10.4f} "
            f"{streuung / rennen.nullstreuung - 1:>+12.0%}  "
            f"{rennen.wo_holt_sie_auf()}"
        )
    return "\n".join(zeilen)


def kalibrierunsicherheit(versuche: int) -> float:
    """Wie stark die zurueckgerechnete Ideenstreuung selbst streut - relativ.

    Woher die Frage kommt
    ---------------------
    Befund 124. Die ganze Suchprognose haengt an ``kalibriere``, und das
    rechnet aus **einem** Wert zurueck: dem beobachteten Bestwert. Der ist
    aber selbst eine Zufallsgroesse - das Maximum von N Ziehungen streut, und
    zwar erheblich.

    Die Rechnung
    ------------
    Fuer das Maximum von N normalverteilten Werten gilt naeherungsweise die
    Gumbel-Verteilung mit Skala ``beta = sigma / a_N`` und
    ``a_N = sqrt(2 ln N)``. Daraus folgt

        sigma(Maximum) = sigma * pi / (sqrt(6) * a_N)

    und weil ``kalibriere`` durch ``c(N) = extremwert(N)`` teilt, ist die
    relative Streuung der Rueckrechnung

        pi / (sqrt(6) * a_N * c(N))

    Bei 198 Versuchen sind das **14,3 %** - gegengeprueft an 20.000
    Simulationsziehungen, die 14,4 % ergaben.

    Was das bedeutet
    ----------------
    Die Rueckrechnung ist erwartungstreu (simuliert 0,0923 gegen wahr 0,0930),
    aber ihr Fehlerbalken ist gross genug, um das Urteil umzuwerfen: Bei einer
    wahren Streuung von 0,0930 liegt die Rueckrechnung in **20 % der
    Ziehungen** unter der Nullstreuung - dort saehe es aus, als hole die Suche
    nie auf, obwohl sie es taete.
    """
    if versuche < 2:
        return float("inf")
    a = math.sqrt(2 * math.log(versuche))
    c = extremwert(versuche)
    if a <= 0 or c <= 0:
        return float("inf")
    return math.pi / (math.sqrt(6) * a * c)


def kalibrierbereich(
    streuung: float, versuche: int, *, irrtum: float = 0.10
) -> tuple[float, float]:
    """Der Bereich, in dem die wahre Ideenstreuung plausibel liegt.

    Gerechnet mit den Gumbel-Quantilen statt einer Normalnaeherung: Die
    Verteilung des Maximums ist rechtsschief, und ein symmetrischer Bereich
    waere am unteren Ende zu eng - also genau dort, wo das Urteil kippt.

    **Die Naeherung bleibt am unteren Ende leicht optimistisch**: Simuliert
    ergab sich 0,0731, die Formel liefert 0,0757. Wer die Grenze braucht, um
    etwas auszuschliessen, sollte das wissen.
    """
    if versuche < 2 or streuung <= 0:
        return (0.0, float("inf"))

    a = math.sqrt(2 * math.log(versuche))
    c = extremwert(versuche)
    if a <= 0 or c <= 0:
        return (0.0, float("inf"))

    def rand(p: float) -> float:
        # Gumbel-Quantil, relativ zum Erwartungswert des Maximums.
        abweichung = -math.log(-math.log(p)) - EULER_MASCHERONI
        return streuung * (1.0 + abweichung / (a * c))

    unten, oben = rand(irrtum / 2), rand(1 - irrtum / 2)
    return (max(0.0, unten), oben)
