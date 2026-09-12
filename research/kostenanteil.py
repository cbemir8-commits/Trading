"""Ist die Kopplung eine Eigenschaft der Kosten oder der Signale?

Die Hypothese, die naheliegt
----------------------------
Befund 75 und 77 haben ueber 18 gemessene Regeln eine Kopplung gezeigt:
**r = -0,602 zwischen Trade-Zahl und Qualitaet je Trade** - wer oefter
handelt, handelt schlechter. Sie erklaert, warum die Partnerkarte leer
ausgeht, und sie ist der Grund, warum das haerteste Gate nicht faellt.

Dafuer gibt es eine mechanische Erklaerung, und sie klingt zwingend: Die
Gebuehr ist ein **fester Betrag je Trade**, aber die Streuung eines Trades
waechst mit seiner Haltedauer. Wer oefter handelt, haelt kuerzer, streut
weniger - und derselbe Gebuehrenbetrag frisst einen groesseren Anteil.

Waere das die Ursache, haette es eine Folge: Die Kopplung waere
**verhandelbar**. Bessere Konditionen, Maker-Rebates, ein groesseres Konto -
alles wuerde helfen.

Was gemessen wurde
------------------
Ueber zehn Regeln mit sehr verschiedener Taktung, vom Bestand (154 Trades,
14 Tage Haltedauer) bis zum 'Abgriff des Vortagestiefs' (406 Trades, 0,3
Tage):

    Trades <-> Kostenanteil    +0,831
    Kostenanteil <-> Qualitaet -0,738

Die Mechanik ist also **da**: Mehr Trades heissen kuerzer halten und hoeheren
Kostenanteil. Nur traegt sie nichts, denn der Anteil selbst ist winzig - er
reicht von 0,0013 bis 0,0170 der Trade-Streuung, waehrend die Qualitaeten von
+0,34 bis -0,12 spannen.

Rechnet man die Gebuehr zurueck, bleibt die Kopplung praktisch unveraendert:

    netto    r = -0,673
    brutto   r = -0,663

**Zehn Tausendstel.** Die Hypothese ist damit widerlegt.

Warum die Rechnung trotzdem unvollstaendig ist
----------------------------------------------
``net_pnl = gross_pnl - fees - funding``, und die **Slippage steckt im
Ausfuehrungspreis** - also schon in ``gross_pnl`` und nicht in ``fees``. Was
oben zurueckgerechnet wurde, ist die Gebuehr allein; die wahren Handelskosten
liegen hoeher, und um wie viel, laesst sich aus den Trades nicht trennen.

Deshalb wird die Frage andersherum gestellt, und das ist ihre ehrliche Form:
**Bei welchem Kostenfaktor wuerde die Kopplung kippen?**

    Faktor 1     r = -0,663     (die tatsaechliche Gebuehr, 0,04 %)
    Faktor 5     r = -0,618
    Faktor 10    r = -0,542
    Faktor 25    r = -0,144     (entspraeche 1 % je Trade)
    Faktor 50    r = +0,511

Erst bei rund **29-facher Gebuehr** verschwindet die Kopplung - das waeren
1,2 % je Roundtrip. Kein Handelsplatz verlangt das. Selbst wenn die Slippage die
Kosten verdoppelte oder verfuenffachte, bliebe die Kopplung stehen.

**Was dieser Faktor angibt - Befund 256.** Er ist die Reichweite der *Rechnung*
und nicht die der *Reibung*. ``brutto(f)`` beschreibt immer dieselbe
reibungslose Welt, behauptet ueber sie aber je nach f etwas anderes; die Welt
selbst bewegt sich nicht. Nachgemessen auf Tageskerzen (``scaled(0)``): Sie
steht bei **-0,370**. ``brutto(1)`` sagt -0,374 und trifft damit; ``brutto(56)``
sagt 0,000 und liegt 0,370 daneben.

Die Schlussfolgerung unten bleibt stehen und ist heute besser belegt als ueber
den Faktor - sie wird seit Befund 254/255 direkt gemessen, nicht erschlossen.
Der Faktor selbst gehoert nicht mehr als Beleg zitiert.

Was daraus folgt
----------------
Die Kopplung ist **keine Eigenschaft der Kosten, sondern der Signale**:
Haeufigere Ausloeser tragen tatsaechlich weniger Vorteil je Ausloesung. Das
ist nicht wegverhandelbar - keine Konditionen, kein groesseres Konto, keine
bessere Ausfuehrung aendert etwas daran.

Fuer die Suche heisst das: Wer eine Regel sucht, die **oft ausloest und dabei
Vorteil behaelt**, sucht gegen ein Muster, das nicht an einer Reibung liegt,
die sich beseitigen liesse.

Wofuer dieser Satz gilt - und wofuer nicht (Befund 187)
-------------------------------------------------------
Alles oben ist auf **Tageskerzen** gemessen, und dort ist der Kostenanteil
winzig. Auf dem nach Befund 182/184 berichtigten Katalog (18 statt 10 Regeln)
kommt dasselbe heraus, mit anderen Zahlen:

    Kostenanteil   0,0013 bis 0,0086     Mechanik  +0,554
    netto -0,378   brutto -0,374         Kippfaktor 56

**Auf kuerzeren Kerzen ist das ungemessen.** Wer oefter handelt, haelt
kuerzer und streut je Trade weniger - der Kostenanteil waechst also genau
dort, wo dieses Modul ihn fuer vernachlaessigbar erklaert hat.

``urteil`` hat den Satz bis Befund 187 **unbedingt** ausgesprochen, sobald
vier Punkte da waren - auch bei einem Kippfaktor von 2, unmittelbar gefolgt
von der Zahl, die ihm widerspricht. Ein Betriebspunkt war als Gesetz
eingebaut. Jetzt verzweigt es an ``ERREICHBAR``.

Kostet keinen Versuch: Zerlegt werden Trades, die schon gerechnet sind.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np

#: Bis zu welchem Kostenfaktor die Reibung als Ursache in Frage kommt.
#:
#: Die Gebuehr laesst sich abziehen, die Slippage nicht - sie steckt im
#: Ausfuehrungspreis und damit schon in ``gross_pnl``. Was sich fragen laesst,
#: ist deshalb nur: Wie gross muesste die *gesamte* Reibung sein, damit sie
#: die Kopplung traegt? Liegt dieser Faktor unter fuenf, waere er allein durch
#: eine Slippage in der Groessenordnung der Gebuehr erreichbar, und die
#: Ursache ist offen. Liegt er darueber, scheidet die Reibung aus.
#:
#: Fuenf ist eine gesetzte Grenze, keine gemessene. Sie steht hier, damit sie
#: **vor** der Messung feststeht - auf Tageskerzen kam Faktor 29 heraus, weit
#: jenseits jeder Wahl der Grenze.
ERREICHBAR: float = 5.0


@dataclass(frozen=True, slots=True)
class Taktpunkt:
    """Eine Regel mit ihrer Taktung und ihrem Kostenanteil."""

    name: str
    trades: int
    sharpe_je_trade: float
    haltedauer_tage: float
    kostenanteil: float
    """Mittlere Gebuehr je Trade, geteilt durch die Streuung der Trades.

    In denselben Einheiten wie der Sharpe je Trade - deshalb laesst sie sich
    direkt zurueckaddieren.
    """

    def brutto(self, faktor: float = 1.0) -> float:
        """Der Sharpe je Trade, wenn man die Kosten herausrechnet.

        ``faktor`` skaliert die Gebuehr. Er ist noetig, weil die Slippage im
        Ausfuehrungspreis steckt und sich nicht trennen laesst - statt sie zu
        schaetzen, wird gefragt, wie gross sie sein muesste, um etwas zu
        aendern.
        """
        return self.sharpe_je_trade + faktor * self.kostenanteil

    @classmethod
    def aus_trades(cls, name: str, trades) -> Taktpunkt | None:
        """Alle vier Groessen aus einer Trade-Liste - an **einer** Stelle.

        Die Zahlen im Kopf dieses Moduls stehen dort seit Befund 78 als
        Prosa, und die Testdatei haelt sie als Zahlenliste fest - einen Weg
        von Trades zu einem ``Taktpunkt`` gab es im Code nicht, und
        ``Kostenfrage`` hatte in ``cli.py`` keinen einzigen Aufrufer. Wer die
        Frage an einem anderen Vorrat stellen wollte, musste die Herleitung
        nachbauen - derselbe Anlass wie bei ``Kandidat.aus_trades``.

        ``None``, wenn die Liste fuer eine Aussage zu duenn ist. Die Schwelle
        ist dieselbe wie dort (fuenf Trades, Streuung ungleich null), damit
        beide Wege denselben Vorrat sehen.
        """
        import numpy as np

        netto = np.array([float(t.net_pnl) for t in trades], dtype=float)
        if len(netto) < 5:
            return None
        streuung = float(netto.std(ddof=1))
        if streuung == 0:
            return None

        gebuehr = float(np.mean([float(t.fees) for t in trades]))
        stunden = np.array(
            [t.duration.total_seconds() / 3600.0 for t in trades], dtype=float
        )
        return cls(
            name=name,
            trades=len(netto),
            sharpe_je_trade=float(netto.mean() / streuung),
            haltedauer_tage=float(stunden.mean()) / 24.0,
            # In Einheiten der Trade-Streuung - deshalb direkt auf den Sharpe
            # je Trade zurueckaddierbar.
            kostenanteil=gebuehr / streuung,
        )


@dataclass(slots=True)
class Kostenfrage:
    """Traegt die Gebuehr die gemessene Kopplung?"""

    punkte: list[Taktpunkt] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return len(self.punkte) >= 4

    def _korrelation(self, werte: list[float]) -> float | None:
        if not self.genug:
            return None
        trades = np.array([float(p.trades) for p in self.punkte])
        andere = np.array(werte)
        if np.std(trades) == 0 or np.std(andere) == 0:
            return None
        return float(np.corrcoef(trades, andere)[0, 1])

    @property
    def netto(self) -> float | None:
        return self._korrelation([p.sharpe_je_trade for p in self.punkte])

    def brutto(self, faktor: float = 1.0) -> float | None:
        return self._korrelation([p.brutto(faktor) for p in self.punkte])

    @property
    def mechanik(self) -> float | None:
        """Trades gegen Kostenanteil - ist der Mechanismus ueberhaupt da?"""
        return self._korrelation([p.kostenanteil for p in self.punkte])

    def kippfaktor(self, *, obergrenze: float = 1000.0) -> float | None:
        """Ab welchem Kostenfaktor die Kopplung verschwindet.

        "Verschwindet" heisst hier: Die Korrelation erreicht null. ``None``,
        wenn das im durchsuchten Bereich nicht passiert - dann traegt die
        Gebuehr die Kopplung unter keinen Umstaenden.
        """
        if not self.genug or (self.netto or 0) >= 0:
            return None
        if (self.brutto(obergrenze) or -1.0) < 0:
            return None
        tief, hoch = 1.0, obergrenze
        for _ in range(80):
            mitte = (tief + hoch) / 2
            if (self.brutto(mitte) or -1.0) < 0:
                tief = mitte
            else:
                hoch = mitte
        return hoch

    def tabelle(self, faktoren: tuple[float, ...] = (1, 5, 10, 25, 50)) -> str:
        zeilen = [f"{'Faktor':>8} {'r brutto':>10} {'Aenderung':>11}", "-" * 31]
        netto = self.netto or 0.0
        for f in faktoren:
            wert = self.brutto(f)
            if wert is None:
                continue
            zeilen.append(f"{f:>8g} {wert:>+10.3f} {wert - netto:>+11.3f}")
        return "\n".join(zeilen)

    def urteil(self) -> str:
        netto, brutto, mechanik = self.netto, self.brutto(1.0), self.mechanik
        if netto is None or brutto is None:
            return "Zu wenige Punkte - ueber die Ursache laesst sich nichts sagen."

        vorhanden = (
            f"Der Mechanismus ist da: Trades und Kostenanteil korrelieren mit "
            f"{mechanik:+.3f}. "
            if mechanik is not None and mechanik > 0.5
            else ""
        )
        gemessen = (
            f"{vorhanden}Rechnet man die Gebuehr zurueck, geht die "
            f"Korrelation von {netto:+.3f} auf {brutto:+.3f} - "
            f"{abs(brutto - netto):.3f} Unterschied. "
        )
        kipp = self.kippfaktor()
        if kipp is None:
            return (
                f"**Die Kopplung liegt nicht an den Kosten.** {gemessen}Auch "
                f"bei tausendfacher Gebuehr verschwindet sie nicht.\n\n"
                f"Sie ist damit eine Eigenschaft der **Signale**, nicht einer "
                f"Reibung: Haeufigere Ausloeser tragen weniger Vorteil je "
                f"Ausloesung. Das ist nicht wegverhandelbar - keine "
                f"Konditionen, kein groesseres Konto, keine bessere "
                f"Ausfuehrung aendert daran etwas."
            )

        wo = (
            f"Bei **{kipp:.0f}-facher Gebuehr** verschwindet sie - das waeren "
            f"rund {0.04 * kipp:.1f} % je Roundtrip."
        )
        if kipp > ERREICHBAR:
            return (
                f"**Die Kopplung liegt nicht an den Kosten.** {gemessen}{wo} "
                f"Das verlangt kein Handelsplatz, und selbst eine Slippage, "
                f"die die Kosten verfuenffachte, bliebe darunter.\n\n"
                f"Sie ist damit eine Eigenschaft der **Signale**, nicht einer "
                f"Reibung: Haeufigere Ausloeser tragen weniger Vorteil je "
                f"Ausloesung. Das ist nicht wegverhandelbar - keine "
                f"Konditionen, kein groesseres Konto, keine bessere "
                f"Ausfuehrung aendert daran etwas."
            )
        # **Hier stand bis Befund 187 derselbe Satz wie oben.** Das Urteil
        # sprach die Antwort aus, die auf Tageskerzen gemessen worden war,
        # und haette sie auch bei einem Kippfaktor von 1,5 gesprochen -
        # unmittelbar gefolgt von der Zahl, die ihr widerspricht. Ein
        # Betriebspunkt war als Gesetz eingebaut; dieselbe Sorte Fehler wie
        # in Befund 56/182/184.
        return (
            f"**Hier koennten es die Kosten sein.** {gemessen}{wo} Das liegt "
            f"in der Reichweite dessen, was allein die Slippage ausmachen "
            f"kann - und die steckt im Ausfuehrungspreis, laesst sich aus "
            f"den Trades also nicht abziehen.\n\n"
            f"Damit ist hier **nicht entschieden**, ob die Kopplung an den "
            f"Signalen oder an der Reibung haengt. Auf Tageskerzen war sie "
            f"es nicht (Kippfaktor 29); dieser Vorrat liegt anders, und das "
            f"Urteil von dort gilt hier nicht."
        )


# ---------------------------------------------------------------------------
# Die Frage direkt statt ueber einen Faktor
# ---------------------------------------------------------------------------
#
# ``Kostenfrage`` kann die Gebuehr zurueckrechnen, die Slippage aber nicht -
# sie steckt im Ausfuehrungspreis und damit schon in ``gross_pnl``. Deshalb
# musste die Frage als "wie gross muesste die Reibung sein?" gestellt werden,
# mit ``ERREICHBAR`` als gesetztem Schiedsrichter. Auf Tageskerzen kam Faktor
# 29 heraus und die Antwort war eindeutig; auf Viertelstunden kam Faktor 2,
# und dort entscheidet seit Befund 187 eine **gesetzte Grenze** ueber einen
# Befund.
#
# Das muss sie nicht. ``CostModel.scaled(0)`` setzt Gebuehr **und** Slippage
# auf null - die Engine nimmt beide als Parameter. Laesst man dieselben Regeln
# zweimal laufen, einmal mit und einmal ohne jede Reibung, steht die Kopplung
# ohne Faktorargument da (Befund 254).


@dataclass(frozen=True, slots=True)
class Reibungsprobe:
    """Dieselben Regeln, einmal mit und einmal ohne jede Reibung."""

    mit: Kostenfrage
    ohne: Kostenfrage

    @property
    def gleiche_regeln(self) -> bool:
        """Beide Laeufe muessen dieselbe Regelmenge tragen.

        Ohne Reibung fallen Fuellungen anders aus, Risikogrenzen greifen
        anders, und eine Regel kann im einen Lauf genug Trades haben und im
        anderen nicht. Waere die Menge verschieden, verglichen sich zwei
        Populationen - der Fehler, den dieses Projekt oefter gemacht hat als
        jeden anderen.
        """
        return {p.name for p in self.mit.punkte} == {
            p.name for p in self.ohne.punkte
        }

    @property
    def belastbar(self) -> bool:
        return self.mit.genug and self.ohne.genug and self.gleiche_regeln

    @property
    def anteil_der_reibung(self) -> float | None:
        """Wie viel der Kopplung verschwindet, wenn die Reibung verschwindet.

        0 heisst: Die Reibung traegt nichts davon. 1 heisst: ohne sie ist die
        Kopplung weg. Gerechnet als Weg zur Null, nicht als Verhaeltnis der
        beiden Zahlen - gefragt ist, wie weit die Reibung die Kopplung
        aufhebt.
        """
        if not self.belastbar:
            return None
        mit, ohne = self.mit.netto, self.ohne.netto
        if mit is None or ohne is None or mit >= 0:
            return None
        return (ohne - mit) / (0.0 - mit)

    @property
    def traegt_die_reibung(self) -> bool:
        """Ist die Kopplung ohne Reibung verschwunden?"""
        if not self.belastbar:
            return False
        ohne = self.ohne.netto
        return ohne is not None and ohne >= 0.0

    def tabelle(self) -> str:
        zeilen = [
            f"{'Lauf':<12}{'Regeln':>8}{'r netto':>10}{'Mechanik':>10}"
            f"{'Kippfaktor':>12}",
            "-" * 52,
        ]
        for name, frage in (("mit Reibung", self.mit), ("ohne", self.ohne)):
            # Ohne Reibung ist jeder Kostenanteil null, also hat 'mechanik'
            # keine Streuung und ist **nicht definiert**. Als '+0.000' sieht
            # das aus wie eine gemessene Null - es ist keine.
            zahlen = [
                f"{wert:+.3f}" if wert is not None else "-"
                for wert in (frage.netto, frage.mechanik)
            ]
            kipp = frage.kippfaktor()
            zeilen.append(
                f"{name:<12}{len(frage.punkte):>8}{zahlen[0]:>10}"
                f"{zahlen[1]:>10}{f'{kipp:.1f}' if kipp is not None else '-':>12}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.belastbar:
            if not self.gleiche_regeln:
                fehlt = {p.name for p in self.mit.punkte} ^ {
                    p.name for p in self.ohne.punkte
                }
                return (
                    f"**Nicht vergleichbar.** Die beiden Laeufe tragen "
                    f"verschiedene Regeln ({len(fehlt)} nur in einem von "
                    f"beiden). Ohne Reibung fallen Fuellungen anders aus, und "
                    f"eine Regel kann im einen Lauf genug Trades haben und im "
                    f"anderen nicht - verglichen wuerden dann zwei "
                    f"Populationen."
                )
            return (
                "**Zu wenige Punkte.** Fuer eine Korrelation braucht es vier "
                "Regeln je Lauf."
            )

        mit, ohne = self.mit.netto, self.ohne.netto
        anteil = self.anteil_der_reibung
        kopf = (
            f"Dieselben {len(self.mit.punkte)} Regeln, einmal mit und einmal "
            f"ohne jede Reibung: Die Kopplung steht bei {mit:+.3f} und "
            f"{ohne:+.3f}."
        )

        if self.traegt_die_reibung:
            return (
                f"**Die Reibung traegt sie.** {kopf} Ohne Gebuehr und ohne "
                f"Slippage ist die Kopplung nicht mehr negativ. Auf diesem "
                f"Vorrat ist sie damit **keine** Eigenschaft der Signale, "
                f"sondern der Handelskosten - und anders als eine Eigenschaft "
                f"der Signale ist sie verhandelbar: Konditionen, Maker statt "
                f"Taker, ein groesseres Konto."
            )

        if anteil is not None and anteil > 0.25:
            return (
                f"**Teils.** {kopf} Die Reibung hebt {anteil:.0%} des Weges "
                f"zur Null auf - sie traegt einen sichtbaren Teil, aber ohne "
                f"sie bleibt die Kopplung negativ. Was uebrig bleibt, haengt "
                f"an den Signalen."
            )

        return (
            f"**Die Reibung traegt sie nicht.** {kopf} Auch ganz ohne Gebuehr "
            f"und Slippage bleibt die Kopplung negativ"
            + (f" ({anteil:.0%} des Weges zur Null)" if anteil is not None else "")
            + ". Sie ist eine Eigenschaft der **Signale**: Haeufigere "
            "Ausloeser tragen weniger Vorteil je Ausloesung.\n\n"
            "Und das steht hier ohne Faktorargument da. 'Kostenfrage' musste "
            "fragen, wie gross die Reibung sein muesste, weil die Slippage "
            "im Ausfuehrungspreis steckt; hier ist sie auf null gesetzt, "
            "statt herausgerechnet zu werden."
        )


__all__ = [
    "ERREICHBAR",
    "Kostenfrage",
    "Reibungsleiter",
    "Reibungsprobe",
    "Reibungssprosse",
    "Taktpunkt",
]


# ---------------------------------------------------------------------------
# Der Kippfaktor, gemessen statt gerechnet
# ---------------------------------------------------------------------------
#
# ``Kostenfrage.kippfaktor`` sucht, ab welchem Faktor ``sharpe + f * anteil``
# die Null erreicht. Das haelt die **Trades fest**: Dieselben Ein- und
# Ausstiege, nur andere Zahlen darunter. Bei Faktor 1 ist das eine gute
# Naeherung - auf Tageskerzen sagt sie -0,374, gemessen sind es -0,370.
#
# Bei Faktor 56 ist es keine mehr. Eine Gebuehr von 2,2 % je Roundtrip
# aenderte nicht die Zahlen unter denselben Trades, sondern die Trades: Stops
# lieber, Risikogrenzen frueher, viele Einstiege gar nicht. Was ``kippfaktor``
# meldet, ist deshalb der Kippunkt **einer Rechnung**, nicht der einer
# Strategie (Befund 256).
#
# ``Reibungsleiter`` misst denselben Punkt durch Wiederholung: jede Sprosse
# ein ganzer Lauf bei ``CostModel.scaled(k)``.


@dataclass(frozen=True, slots=True)
class Reibungssprosse:
    """Ein ganzer Katalogdurchlauf bei einem Reibungsfaktor."""

    faktor: float
    frage: Kostenfrage

    @property
    def r(self) -> float | None:
        return self.frage.netto

    @property
    def regeln(self) -> frozenset[str]:
        return frozenset(p.name for p in self.frage.punkte)


@dataclass(frozen=True, slots=True)
class Reibungsleiter:
    """Mehrere Laeufe bei verschiedener Reibung - der Kippunkt als Messung."""

    sprossen: tuple[Reibungssprosse, ...] = ()

    @property
    def geordnet(self) -> list[Reibungssprosse]:
        return sorted(self.sprossen, key=lambda s: s.faktor)

    @property
    def gleiche_regeln(self) -> bool:
        """Alle Sprossen muessen dieselbe Regelmenge tragen.

        Mit mehr Reibung faellt eine Regel irgendwann unter die Schwelle fuer
        einen Taktpunkt. Dann verglichen sich verschiedene Populationen -
        derselbe Fehler, gegen den ``Reibungsprobe.gleiche_regeln`` steht.
        """
        mengen = {s.regeln for s in self.sprossen if s.frage.punkte}
        return len(mengen) <= 1

    @property
    def belastbar(self) -> bool:
        return (
            len(self.sprossen) >= 2
            and all(s.frage.genug for s in self.sprossen)
            and self.gleiche_regeln
        )

    def bei(self, faktor: float) -> Reibungssprosse | None:
        return next((s for s in self.sprossen if s.faktor == faktor), None)

    @property
    def probe(self) -> Reibungsprobe | None:
        """Die Null- und die Einssprosse als ``Reibungsprobe``.

        Damit steht die Zwei-Punkt-Frage aus Befund 254 nicht ein zweites Mal
        gerechnet da, sondern faellt aus denselben Sprossen.
        """
        null, eins = self.bei(0.0), self.bei(1.0)
        if null is None or eins is None:
            return None
        return Reibungsprobe(mit=eins.frage, ohne=null.frage)

    @property
    def reibungslos(self) -> float | None:
        """Die Kopplung in der reibungslosen Welt - **gemessen**.

        Der Bezugspunkt fuer alles Weitere: Es gibt genau **eine** solche
        Welt. Sie bewegt sich nicht, wenn man die Annahme darueber aendert,
        wie gross die Reibung ist.
        """
        null = self.bei(0.0)
        return null.r if null is not None else None

    def naeherungsfehler(self) -> list[tuple[float, float, float]]:
        """Was ``brutto(f)`` ueber die reibungslose Welt behauptet - und was
        dort steht.

        ``Kostenfrage.brutto(f)`` ist die Kopplung, **wenn** die wahre Reibung
        das f-fache der Gebuehr waere und man sie herausrechnete. Gemeint ist
        damit immer dieselbe reibungslose Welt; behauptet wird je nach f etwas
        anderes. Der Abstand zwischen Behauptung und Messung ist der Fehler
        der Naeherung, und er waechst mit f.

        Je Eintrag: ``(faktor, behauptet, abstand)``.
        """
        eins, ohne = self.bei(1.0), self.reibungslos
        if eins is None or ohne is None:
            return []
        aus = []
        for sprosse in self.geordnet:
            behauptet = eins.frage.brutto(sprosse.faktor)
            if behauptet is not None:
                aus.append((sprosse.faktor, behauptet, abs(behauptet - ohne)))
        return aus

    @property
    def kippt_unter_aufschlag(self) -> tuple[float, float] | None:
        """Zwischen welchen Faktoren **aufgeschlagene** Reibung die Kopplung
        zur Null bringt.

        Nicht zu verwechseln mit ``Kostenfrage.kippfaktor``: Der rechnet
        Reibung **heraus**, das hier schlaegt sie **auf**. Beides ist
        interessant und beides ist etwas anderes.

        Ein gemessenes Paar, keine interpolierte Zahl: Was dazwischen liegt,
        wurde nicht gerechnet.
        """
        if not self.belastbar:
            return None
        for links, rechts in pairwise(self.geordnet):
            a, b = links.r, rechts.r
            if a is None or b is None:
                continue
            if a < 0 <= b:
                return (links.faktor, rechts.faktor)
        return None

    @property
    def gerechneter_kipppunkt(self) -> float | None:
        """Was ``Kostenfrage.kippfaktor`` am Betriebspunkt dazu sagt."""
        eins = self.bei(1.0)
        return eins.frage.kippfaktor() if eins is not None else None

    def tabelle(self) -> str:
        if not self.sprossen:
            return "Keine Sprossen gemessen."
        zeilen = [f"{'Faktor':>8}{'Regeln':>9}{'r netto':>10}", "-" * 27]
        for s in self.geordnet:
            zeilen.append(
                f"{s.faktor:>8g}{len(s.frage.punkte):>9}"
                + (f"{s.r:>+10.3f}" if s.r is not None else f"{'-':>10}")
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.belastbar:
            if not self.gleiche_regeln:
                return (
                    "**Nicht vergleichbar.** Die Sprossen tragen verschiedene "
                    "Regelmengen - mit mehr Reibung faellt eine Regel unter "
                    "die Schwelle fuer einen Taktpunkt, und dann verglichen "
                    "sich zwei Populationen."
                )
            return (
                "**Zu wenig gemessen.** Es braucht mindestens zwei Sprossen "
                "mit je vier Regeln."
            )

        teile: list[str] = []
        kippt = self.kippt_unter_aufschlag
        hoechste = self.geordnet[-1]

        if kippt is None:
            richtung = ""
            werte = [s.r for s in self.geordnet if s.r is not None]
            if len(werte) >= 2 and werte[-1] < werte[0]:
                richtung = (
                    " Sie wird dabei nicht schwaecher, sondern **staerker** - "
                    "mehr Reibung trifft die haeufig handelnden Regeln haerter, "
                    "und genau das ist die Kopplung."
                )
            teile.append(
                f"**Aufgeschlagene Reibung bringt die Kopplung bis Faktor "
                f"{hoechste.faktor:g} nicht zur Null.** Dort steht sie bei "
                f"{hoechste.r:+.3f}.{richtung}"
            )
        else:
            unten, oben = kippt
            teile.append(
                f"**Aufgeschlagene Reibung bringt sie zwischen Faktor "
                f"{unten:g} und {oben:g} zur Null.** Jede Sprosse ist ein "
                f"ganzer Lauf: Fuellungen, Stops und Risikogrenzen reagieren "
                f"mit."
            )

        fehler = self.naeherungsfehler()
        ohne = self.reibungslos
        if fehler and ohne is not None:
            grenzfall = max(fehler, key=lambda x: x[2])
            teile.append(
                f"**Und die reibungslose Welt ist eine einzige.** Sie steht "
                f"gemessen bei {ohne:+.3f}. 'brutto(f)' behauptet ueber "
                f"**dieselbe** Welt je nach f etwas anderes: bei f = 1 "
                f"{fehler[min(1, len(fehler) - 1)][1]:+.3f}, bei f = "
                f"{grenzfall[0]:g} schon {grenzfall[1]:+.3f} - "
                f"{grenzfall[2]:.3f} daneben. Die Naeherung haelt die Trades "
                f"fest; je weiter hinaus sie rechnet, desto weniger traegt "
                f"das."
            )
            gerechnet = self.gerechneter_kipppunkt
            if gerechnet is not None:
                teile.append(
                    f"**Damit ist der Kippfaktor keine Messung.** "
                    f"'Kostenfrage' meldet {gerechnet:.1f} - den Punkt, an "
                    f"dem die Naeherung die Null erreicht. Die Welt, ueber "
                    f"die sie dort redet, ist nachgemessen worden und steht "
                    f"bei {ohne:+.3f}. Was der Faktor angibt, ist die "
                    f"Reichweite der Rechnung und nicht die der Reibung."
                )

        teile.append(
            f"{len(self.sprossen)} Sprossen, je ein voller Katalogdurchlauf. "
            f"Kostet keinen Versuch: derselbe Vorrat unter anderen "
            f"Handelsbedingungen."
        )
        return "\n\n".join(teile)
