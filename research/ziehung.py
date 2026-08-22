"""Eine Leiter aus je einer Ziehung sagt nichts ueber Unterschiede.

Wozu
----
``research/teststaerke.py`` pflanzt einen Trend in die echte Reihe und faehrt
den Anteil hoch. Befund 54 hat daraus die Aussage gezogen, die dieses Projekt
seither traegt:

    *"Qualitaet und Menge sind gekoppelt. Ein groesserer Trend heisst
    laengeres Halten heisst weniger Trades. Auf rund 3300 Tagen je Bein gibt
    es keine Einstellung, bei der beides zugleich reicht."*

Und er nennt sie selbst *"die belastbarste Aussage, die dieses Projekt bisher
ueber sich selbst hat"*. Aus ihr folgte die Absage an die Regelfamilie.

Sie steht auf **einer einzigen gepflanzten Reihe** - ``saat=11``, eine
Ziehung je Sprosse. Ein Regime ist eine Zufallsfolge; eine andere Saat gibt
andere Trades, andere Guete, anderen Deflated Sharpe. Wie viel der Leiter das
gepflanzte Signal ist und wie viel die eine Ziehung, stand nirgends.

Dieses Modul zwingt die Frage in die Rechnung: Eine Sprosse aus einer
einzelnen Ziehung liefert **keinen** Unterschied, sondern ``None``. Nicht als
Vorsicht, sondern weil es die richtige Antwort ist - ohne Streuung gibt es
keinen Massstab, an dem ein Abstand gross oder klein waere.

Die Regel
---------
Verglichen werden Sprossen ueber die Saaten hinweg, mit demselben Massstab
wie ueberall in diesem Projekt: |t| >= 2, und bei mehreren Vergleichen die
Bonferroni-Schranke aus ``research/rangprobe.py``. Ein Unterschied darunter
ist kein kleiner Unterschied, sondern keiner.

Warum gepaart gerechnet wird
----------------------------
Jede Saat trifft alle Sprossen. Der Vergleich zweier Sprossen laeuft deshalb
ueber die **Differenzen je Saat**, nicht ueber zwei unabhaengige Stichproben:
Eine Ziehung, die zufaellig viele Trades hergibt, hebt beide Sprossen
zugleich, und dieser gemeinsame Anteil gehoert herausgerechnet. Ungepaart
gerechnet waere die Streuung groesser als noetig - der Test verloere Schaerfe,
und zwar unnoetig.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import fmean, stdev

from research.rangprobe import schranke


@dataclass(frozen=True, slots=True)
class Ziehung:
    """Ein Lauf einer Sprosse unter einer Saat."""

    saat: int
    anteil: float
    trades: int
    guete: float
    dsr: float
    bestanden: int
    gesamt: int
    cagr_pct: float = 0.0


@dataclass(slots=True)
class Sprosse:
    """Alle Ziehungen zu einem gepflanzten Anteil."""

    anteil: float
    ziehungen: list[Ziehung] = field(default_factory=list)

    @property
    def anzahl(self) -> int:
        return len(self.ziehungen)

    @property
    def einzeln(self) -> bool:
        """Nur eine Ziehung - dann gibt es keine Streuung zu messen."""
        return self.anzahl < 2

    def werte(self, groesse: str) -> list[float]:
        return [float(getattr(z, groesse)) for z in self.ziehungen]

    def mittel(self, groesse: str) -> float | None:
        werte = self.werte(groesse)
        return fmean(werte) if werte else None

    def streuung(self, groesse: str) -> float | None:
        """Standardabweichung ueber die Ziehungen. ``None`` bei einer einzigen."""
        if self.einzeln:
            return None
        return stdev(self.werte(groesse))

    def spanne(self, groesse: str) -> tuple[float, float] | None:
        werte = self.werte(groesse)
        if not werte:
            return None
        return (min(werte), max(werte))


@dataclass(slots=True)
class Leiter:
    """Mehrere Sprossen, jede mit mehreren Ziehungen.

    ``vergleich`` ist die einzige Stelle, an der aus dieser Sammlung eine
    Aussage wird - und sie gibt ``None`` zurueck, wo keine moeglich ist.
    """

    sprossen: list[Sprosse] = field(default_factory=list)

    @property
    def saaten(self) -> tuple[int, ...]:
        """Die Saaten, die in **jeder** Sprosse vorkommen.

        Nur sie taugen fuer den gepaarten Vergleich: Eine Saat, die auf einer
        Sprosse fehlt, hat dort keine Differenz.
        """
        if not self.sprossen:
            return ()
        gemeinsam = {z.saat for z in self.sprossen[0].ziehungen}
        for s in self.sprossen[1:]:
            gemeinsam &= {z.saat for z in s.ziehungen}
        return tuple(sorted(gemeinsam))

    @property
    def aus_einer_ziehung(self) -> bool:
        """Steht die ganze Leiter auf je einer Ziehung?

        Genau die Lage von Befund 54. Sie ist kein Fehler - aber sie traegt
        keine Aussage ueber Unterschiede, und das soll man sehen koennen.
        """
        return bool(self.sprossen) and all(s.einzeln for s in self.sprossen)

    def sprosse(self, anteil: float) -> Sprosse | None:
        for s in self.sprossen:
            if math.isclose(s.anteil, anteil):
                return s
        return None

    def vergleich(
        self, von: float, nach: float, groesse: str = "guete"
    ) -> Unterschied | None:
        """Gepaarter Vergleich zweier Sprossen ueber die gemeinsamen Saaten.

        ``None``, wenn eine der Sprossen fehlt oder weniger als zwei
        gemeinsame Saaten uebrigbleiben. Das ist die Antwort und kein
        Ausweichen: Aus einer Differenz laesst sich keine Streuung schaetzen.
        """
        a, b = self.sprosse(von), self.sprosse(nach)
        if a is None or b is None:
            return None

        gemeinsam = sorted({z.saat for z in a.ziehungen} & {z.saat for z in b.ziehungen})
        if len(gemeinsam) < 2:
            return None

        vorher = {z.saat: float(getattr(z, groesse)) for z in a.ziehungen}
        nachher = {z.saat: float(getattr(z, groesse)) for z in b.ziehungen}
        differenzen = [nachher[s] - vorher[s] for s in gemeinsam]

        mittel = fmean(differenzen)
        streuung = stdev(differenzen)
        fehler = streuung / math.sqrt(len(differenzen))

        # **Eine Streuung im Bereich der Rechengenauigkeit ist keine.**
        #
        # Beim Testen aufgefallen: Drei Saaten mit derselben Differenz 0,10
        # ergaben ``streuung = 3,2e-17`` statt null - 0,30 - 0,20 und
        # 0,40 - 0,30 sind in doppelter Genauigkeit nicht dieselbe Zahl.
        # Daraus wurde ``t = 5,4e15``, und das sieht aus wie ein
        # ueberwaeltigender Beleg, obwohl es Rundungsrest ist.
        #
        # Die Falle ist ernst: Ein t-Wert aus Fliesskommaresten waere in jeder
        # Tabelle die groesste Zahl und in jedem Urteil das staerkste
        # Argument. Deshalb wird die Streuung an der Groessenordnung der
        # Differenzen gemessen und nicht an der Null.
        skala = max(abs(mittel), max((abs(d) for d in differenzen), default=0.0))
        aufloesbar = streuung > 1e-12 * max(skala, 1.0)
        if aufloesbar:
            t = mittel / fehler
        elif mittel:
            # Jede Saat dieselbe Differenz - genau das, was ein belegter
            # Unterschied heisst. Bei ganzzahligen Groessen wie der Gate-Zahl
            # kommt das vor.
            t = math.inf
        else:
            # Beide Sprossen ununterscheidbar.
            t = 0.0
        return Unterschied(
            groesse=groesse,
            von=von,
            nach=nach,
            saaten=len(differenzen),
            mittel=mittel,
            streuung=streuung,
            t=t,
        )


@dataclass(frozen=True, slots=True)
class Unterschied:
    """Ein gepaarter Vergleich zweier Sprossen."""

    groesse: str
    von: float
    nach: float
    saaten: int
    mittel: float
    streuung: float
    t: float

    def belegt(self, hypothesen: int = 1) -> bool:
        """Traegt der Unterschied die uebliche Schranke?

        ``hypothesen`` ist die Zahl der Vergleiche, die zugleich angestellt
        werden - eine Leiter mit fuenf Sprossen ueber der Null stellt fuenf,
        und dann ist |t| >= 2 zu milde.
        """
        return abs(self.t) >= schranke(hypothesen)

    def als_text(self, hypothesen: int = 1) -> str:
        grenze = schranke(hypothesen)
        urteil = "belegt" if self.belegt(hypothesen) else "nicht belegt"
        return (
            f"{self.groesse} von {self.von:.0%} auf {self.nach:.0%}: "
            f"{self.mittel:+.4f} (Streuung {self.streuung:.4f} ueber "
            f"{self.saaten} Saaten), |t| = {abs(self.t):.2f} gegen {grenze:.2f} "
            f"- {urteil}."
        )


@dataclass(frozen=True, slots=True)
class Nachpruefung:
    """Was eine Leiter aus mehreren Ziehungen ueber eine alte Aussage sagt.

    Gedacht fuer den Fall, der hier vorliegt: Eine Aussage steht seit langem
    und stuetzt sich auf eine einzelne Ziehung. Nachgeprueft wird nicht, ob
    sie angenehm ist, sondern ob sie den Massstab traegt, den das Projekt
    ueberall sonst anlegt.
    """

    aussage: str
    befund: int
    unterschiede: tuple[Unterschied, ...]

    @property
    def hypothesen(self) -> int:
        return max(1, len(self.unterschiede))

    def belegte(self) -> tuple[Unterschied, ...]:
        return tuple(u for u in self.unterschiede if u.belegt(self.hypothesen))

    def haelt(self) -> bool:
        """Mindestens ein Unterschied ueber der Schranke."""
        return bool(self.belegte())

    def urteil(self) -> str:
        if not self.unterschiede:
            return (
                f"Zu Befund {self.befund} liegt kein Vergleich vor - die "
                "Aussage ist damit weder bestaetigt noch widerlegt."
            )
        grenze = schranke(self.hypothesen)
        belegt = self.belegte()
        if belegt:
            namen = ", ".join(
                f"{u.von:.0%}->{u.nach:.0%}" for u in belegt
            )
            return (
                f"Befund {self.befund} haelt: {len(belegt)} von "
                f"{len(self.unterschiede)} Vergleichen ueber der Schranke "
                f"{grenze:.2f} ({namen})."
            )
        groesster = max(self.unterschiede, key=lambda u: abs(u.t))
        return (
            f"Befund {self.befund} traegt den eigenen Massstab nicht: kein "
            f"Vergleich erreicht |t| = {grenze:.2f}, der groesste liegt bei "
            f"{abs(groesster.t):.2f} ({groesster.von:.0%}->{groesster.nach:.0%}). "
            "Die Aussage stand auf einer Ziehung."
        )
