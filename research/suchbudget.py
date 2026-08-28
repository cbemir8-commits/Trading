"""Was muesste ein neuer Einfall koennen - und ist je etwas so weit gekommen?

Die Lage, aus der das entsteht
------------------------------
Alle Groessenregler sind ausgemessen und bewegen das haerteste Gate nicht
(Nummer dreissig). Was bleibt, sind neue **Regeln** - und jede kostet einen
Versuch, der die Huerde fuer alle hebt. Bevor man so etwas budgetiert, gehoert
ausgerechnet, worauf man eigentlich zielt.

Die Grenzlinie
--------------
Der Deflated Sharpe haengt an zwei Groessen: der Zahl unabhaengiger Trades und
der Qualitaet je Trade. Zu jeder Trade-Zahl gehoert deshalb ein **noetiger
Sharpe je Trade**, und diese Linie ist der eigentliche Massstab - nicht eine
der beiden Zahlen allein.

Gemessen an den besten des Katalogs zeigt sich, warum keiner besteht:

    Kandidat                            Trades   Sharpe je Trade
    Trend-Beteiligung (fair gerechnet)      46            0,3583
    Trend mit Vola-Ziel 22 %                51            0,3559
    Vola-Ziel, kurzes Messfenster           51            0,3535
    Trend 50 Tage mit Konfluenz            152            0,2597   <- Kandidat

**Der Spitzenkandidat hat die schlechteste Qualitaet je Trade der
Spitzengruppe** - und kommt trotzdem am weitesten, weil er dreimal so oft
handelt. Die anderen sind je Trade deutlich besser und scheitern an der
Stichprobe. Keiner von beiden Wegen reicht.

Was das Werkzeug beantwortet
----------------------------
Zu einer Trade-Zahl den noetigen Sharpe, zu einem Kandidaten den Abstand zur
Linie, und - weil jeder Versuch die Linie hebt - wie sich das mit weiterem
Suchen verschiebt.

Was es **nicht** beantwortet: ob es eine Regel gibt, die dort hinkommt. Es sagt
nur, wohin sie muesste, und wie weit alles Bisherige davon entfernt war.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from research.erreichbarkeit import MAX_SHARPE, noetiger_sharpe
from research.gates import GateThresholds, deflated_sharpe_ratio

#: Die Schwelle, gegen die geloest wird - aus der Gate-Definition geholt und
#: nicht danebengeschrieben. Wer sie dort aendert, aendert sie hier mit.
ZIEL = GateThresholds().min_deflated_sharpe

#: Schiefe und Woelbung, mit denen die Linie gerechnet wird. Voreingestellt
#: sind die des Spitzenkandidaten: Beide gehen in den Deflated Sharpe ein, und
#: eine Normalverteilung anzunehmen waere hier deutlich zu freundlich.
SCHIEFE = 3.473
WOELBUNG = 15.951


@dataclass(frozen=True, slots=True)
class Hebel:
    """Ein Eingang der Formel und der Wert, den er haben muesste."""

    name: str
    jetzt: float
    noetig: float | None
    kleiner_ist_besser: bool = False
    unmoeglich_weil: str = ""
    """Warum der gefundene Zielwert keiner ist.

    Die Rechnung loest je Groesse einzeln, *alles andere unveraendert*. Bei
    Schiefe und Woelbung geht das nicht: Sie sind durch
    ``Woelbung >= Schiefe^2 + 1`` gekoppelt, und die Zerlegung hat deshalb
    monatelang einen Zielpunkt ausgewiesen, den keine Verteilung hat
    (Befund 70). Ein Weg, den es nicht gibt, muss als solcher dastehen -
    sonst sucht jemand danach.
    """

    @property
    def moeglich(self) -> bool:
        """Gibt es ueberhaupt einen Wert, bei dem das Gate allein daran haelt?"""
        return self.noetig is not None and not self.unmoeglich_weil

    @property
    def veraenderung(self) -> float | None:
        if self.noetig is None or self.jetzt == 0:
            return None
        return self.noetig / self.jetzt - 1.0

    def __str__(self) -> str:
        if self.noetig is None:
            return f"{self.name:22} {self.jetzt:>9.3f}   unerreichbar"
        if self.unmoeglich_weil:
            return (
                f"{self.name:22} {self.jetzt:>9.3f} -> {self.noetig:>9.3f}   "
                f"{self.unmoeglich_weil}"
            )
        pfeil = "->"
        anteil = self.veraenderung
        zusatz = f"   ({anteil:+.0%})" if anteil is not None else ""
        return f"{self.name:22} {self.jetzt:>9.3f} {pfeil} {self.noetig:>9.3f}{zusatz}"


def _schiefe_hebel(schiefe: float, woelbung: float, noetig: float | None) -> Hebel:
    """Der Schiefe-Hebel - und die Pruefung, ob sein Ziel existiert.

    ``loese`` haelt die Woelbung fest, weil die Zerlegung jede Groesse einzeln
    fragt. Bei diesen beiden geht das nicht: Fuer jede Verteilung gilt
    ``Woelbung >= Schiefe^2 + 1``. Der so gefundene Zielpunkt hat deshalb oft
    gar keine Verteilung - und stand trotzdem monatelang als letzter offener
    Weg in ``cli stand`` (Befund 70).
    """
    from research.formgrenze import mindestwoelbung

    if noetig is None or woelbung >= mindestwoelbung(noetig):
        return Hebel("Schiefe", schiefe, noetig)
    return Hebel(
        "Schiefe",
        schiefe,
        noetig,
        unmoeglich_weil=(
            f"braucht Woelbung >= {mindestwoelbung(noetig):.1f}, "
            f"hier {woelbung:.1f}"
        ),
    )


@dataclass(frozen=True, slots=True)
class Kandidat:
    """Ein gemessener Einfall - Trade-Zahl und Qualitaet je Trade."""

    name: str
    trades: int
    sharpe_je_trade: float

    schiefe: float | None = None
    woelbung: float | None = None
    """Die **eigene** Verteilungsform dieses Kandidaten.

    Beide gehen in den Deflated Sharpe ein, und zwar kraeftig: Beim
    Spitzenkandidaten steht im Nenner der Formel 0,597 statt der 1,016 einer
    Normalverteilung - seine schiefe Verteilung mit dem langen rechten Ende
    senkt die Huerde um dreissig Prozent.

    Ohne diese Felder wurde **jeder** Kandidat an der Form des
    Spitzenkandidaten gemessen. Fuer eine Regel mit anderer Form - etwa eine,
    die haeufiger und kleiner gewinnt - war die genannte Anforderung damit
    schlicht die eines anderen Genoms. Fehlen sie, gelten weiter die
    Voreinstellungen unten; das ist eine Naeherung und keine Messung.
    """

    effektiv: int | None = None
    """Die **effektive** Stichprobe, wenn sie gemessen wurde.

    ``trades`` ist die rohe Zahl. Das Gate rechnet seit Befund 135 mit der
    effektiven, und die ist kleiner: beim Kandidaten 112 statt 152. Fehlt
    dieses Feld, wird die Latte mit der rohen Zahl gerechnet - dann ist sie
    eine **Untergrenze** und wird auch so ausgewiesen (Befund 139).
    """

    @property
    def stichprobe(self) -> int:
        """Die Zahl, mit der die Latte gerechnet wird."""
        return self.trades if self.effektiv is None else self.effektiv

    @property
    def gemessen(self) -> bool:
        """Ist die Stichprobe gemessen - oder nur die rohe Trade-Zahl?"""
        return self.effektiv is not None

    @classmethod
    def aus_trades(cls, name: str, trades) -> Kandidat | None:
        """Alle vier Groessen aus einer Trade-Liste - an **einer** Stelle.

        Sie standen an dreien: zweimal in ``cli.py`` und einmal als
        ``_sharpe_je_trade``. Drei Umsetzungen derselben Groesse laufen
        frueher oder spaeter auseinander; in diesem Projekt ist das schon
        viermal passiert, und jedes Mal war der Fehler erst zu sehen, als zwei
        Berichte verschiedene Zahlen fuer denselben Kandidaten zeigten.

        ``None``, wenn die Liste fuer eine Aussage zu duenn ist.
        """
        import numpy as np

        werte = np.array([float(t.net_pnl) for t in trades], dtype=float)
        if len(werte) < 5:
            return None
        streuung = float(werte.std(ddof=1))
        if streuung == 0:
            return None

        mittig = (werte - werte.mean()) / streuung
        return cls(
            name=name,
            trades=len(werte),
            sharpe_je_trade=float(werte.mean() / streuung),
            schiefe=float(np.mean(mittig**3)),
            woelbung=float(np.mean(mittig**4)),
        )


@dataclass(frozen=True, slots=True)
class Abstand:
    """Wie weit ein Kandidat unter der Grenzlinie liegt."""

    kandidat: Kandidat
    noetig: float | None

    @property
    def untergrenze(self) -> bool:
        """Ist ``noetig`` nur eine Untergrenze der Latte?

        Ja, wenn die effektive Stichprobe des Kandidaten nicht gemessen ist
        und die Latte deshalb mit der rohen Trade-Zahl gerechnet wurde. Die
        wirkliche Latte liegt dann hoeher, denn die effektive Stichprobe ist
        hoechstens so gross wie die rohe (Befund 139).
        """
        return not self.kandidat.gemessen

    @property
    def erreichbar(self) -> bool:
        """Genuegt bei dieser Stichprobe ueberhaupt irgendein Sharpe?

        Bei sehr kleinen Stichproben nicht: Die Wurzel aus ``n-1`` erstickt
        jeden noch so hohen Wert.
        """
        return self.noetig is not None

    @property
    def luecke(self) -> float | None:
        if self.noetig is None:
            return None
        return self.noetig - self.kandidat.sharpe_je_trade

    @property
    def faktor(self) -> float | None:
        """Um welchen Faktor die Qualitaet steigen muesste."""
        if self.noetig is None or self.kandidat.sharpe_je_trade <= 0:
            return None
        return self.noetig / self.kandidat.sharpe_je_trade

    def als_satz(self) -> str:
        """Der Abstand in Worten - mit der Lesart, die er zulaesst."""
        if self.noetig is None:
            return (
                f"'{self.kandidat.name}': Bei {self.kandidat.stichprobe} "
                f"Beobachtungen genuegt kein Sharpe."
            )
        wie = "mindestens " if self.untergrenze else ""
        satz = (
            f"'{self.kandidat.name}': {self.kandidat.sharpe_je_trade:.4f} je "
            f"Trade, noetig waeren {wie}{self.noetig:.4f} bei "
            f"{self.kandidat.stichprobe} Beobachtungen"
        )
        if self.faktor is not None:
            satz += f" (Faktor {self.faktor:.2f})"
        if self.untergrenze:
            satz += (
                " - gerechnet auf der rohen Trade-Zahl, weil die effektive "
                "Stichprobe nicht gemessen ist; die Latte liegt hoeher"
            )
        return satz + "."


@dataclass(slots=True)
class Budget:
    """Die Grenzlinie, die Kandidaten daran, und was Weitersuchen kostet."""

    versuche: int
    kandidaten: list[Kandidat] = field(default_factory=list)
    schiefe: float = SCHIEFE
    woelbung: float = WOELBUNG

    spotguete: float | None = None
    """Die Guete desselben Bestands unter Kassa-Bedingungen (Befund 126).

    Die Kandidaten stammen aus der Bestenliste und tragen Perpetual-Zahlen.
    Ohne diesen Wert steht im Urteil ein Faktor, der eine Kostenannahme
    mittraegt, die im Spot-Handel entfaellt - Faktor 1,15 statt 1,08.

    ``None`` heisst "nicht gemessen" und nicht "kein Unterschied": Dann bleibt
    das Urteil wie zuvor, statt einen zweiten Punkt zu erfinden.
    """

    def noetig_bei(
        self,
        effektiv: int,
        *,
        versuche: int | None = None,
        schiefe: float | None = None,
        woelbung: float | None = None,
    ) -> float | None:
        """Die Latte bei dieser **effektiven** Stichprobe.

        Wer die rohe Trade-Zahl uebergibt, bekommt eine Untergrenze - siehe
        ``noetiger_sharpe`` und Befund 139.
        """
        return noetiger_sharpe(
            effektiv=effektiv,
            trials=self.versuche if versuche is None else versuche,
            skew=self.schiefe if schiefe is None else schiefe,
            kurtosis=self.woelbung if woelbung is None else woelbung,
        )

    def abstaende(self, *, versuche: int | None = None) -> list[Abstand]:
        """Jeder Kandidat an der Linie - mit seiner **eigenen** Stichprobe.

        ``Kandidat.stichprobe`` liefert die effektive Zahl, wo sie gemessen
        ist, sonst die rohe. Welche es war, steht danach in
        ``Abstand.untergrenze`` - und wird nicht verschwiegen.
        """
        return [
            Abstand(
                kandidat=k,
                noetig=self.noetig_bei(
                    k.stichprobe,
                    versuche=versuche,
                    schiefe=k.schiefe,
                    woelbung=k.woelbung,
                ),
            )
            for k in self.kandidaten
        ]

    @property
    def naechster(self) -> Abstand | None:
        """Der Kandidat, der der Linie am naechsten kam.

        Verglichen wird der **Faktor**, nicht die Differenz: Eine Luecke von
        0,05 wiegt bei einem Sharpe von 0,25 schwerer als bei 0,8.
        """
        gueltig = [a for a in self.abstaende() if a.faktor is not None]
        if not gueltig:
            return None
        return min(gueltig, key=lambda a: a.faktor or float("inf"))

    def linie(self, stichproben: tuple[int, ...]) -> list[tuple[int, float | None]]:
        """Die Grenzlinie ueber mehrere **effektive** Stichprobengroessen."""
        return [(n, self.noetig_bei(n)) for n in stichproben]

    def kosten_je_versuch(self, effektiv: int, *, schritte: int = 10) -> float | None:
        """Um wie viel die Linie steigt, wenn ``schritte`` Versuche dazukommen.

        Geteilt durch ``schritte`` - also der Preis eines einzelnen Einfalls,
        ausgedrueckt in dem, was er von allen kuenftigen verlangt.
        """
        jetzt = self.noetig_bei(effektiv)
        spaeter = self.noetig_bei(effektiv, versuche=self.versuche + schritte)
        if jetzt is None or spaeter is None:
            return None
        return (spaeter - jetzt) / schritte

    def hebel(self, kandidat: Kandidat) -> list[Hebel]:
        """Woran es liegt - je Eingang der Formel einzeln.

        Der Deflated Sharpe haengt an vier **gemessenen** Groessen: Qualitaet
        je Trade, Zahl der unabhaengigen Trades, Schiefe und Woelbung. Die
        Grenzlinie zeigt nur die erste. Diese Zerlegung fragt fuer jede
        einzeln: Wo muesste sie stehen, damit das Gate haelt - alles andere
        unveraendert?

        Das entscheidet, ob Weitersuchen ueberhaupt Sinn hat. Eine Groesse,
        die auf einen unmoeglichen Wert muesste, schliesst ihren Weg; eine,
        die um zehn Prozent muesste, benennt ihn.

        **Vier von fuenf.** Die Formel hat einen fuenften Eingang - die
        Streuung der Sharpe-Schaetzer ueber die Versuche -, und der wird nicht
        gemessen, sondern durch ``1/(n-1)`` ersetzt. Er steht hier nicht
        dazwischen, weil er kein Weg ist: Ihn zu bewegen hiesse, die Huerde zu
        verstellen statt den Kandidaten. Was an ihm haengt, rechnet
        ``research/streuung.py`` aus - beim Spitzenkandidaten kippt das Urteil
        23 % unter der Annahme.
        """
        schiefe = kandidat.schiefe if kandidat.schiefe is not None else self.schiefe
        woelbung = (
            kandidat.woelbung if kandidat.woelbung is not None else self.woelbung
        )

        def dsr(**abweichung) -> float:
            werte = {
                "observed_sharpe": kandidat.sharpe_je_trade,
                "trials": max(self.versuche, 1),
                "sample_size": kandidat.stichprobe,
                "skew": schiefe,
                "kurtosis": woelbung,
            }
            werte.update(abweichung)
            return deflated_sharpe_ratio(**werte)

        def loese(schluessel: str, tief: float, hoch: float) -> float | None:
            """Der kleinste Wert, bei dem das Gate haelt - oder ``None``."""
            if dsr(**{schluessel: hoch}) < ZIEL:
                return None
            for _ in range(80):
                mitte = (tief + hoch) / 2
                if dsr(**{schluessel: mitte}) < ZIEL:
                    tief = mitte
                else:
                    hoch = mitte
            return hoch

        gefunden = [
            Hebel(
                "Qualitaet je Trade",
                kandidat.sharpe_je_trade,
                loese("observed_sharpe", kandidat.sharpe_je_trade, MAX_SHARPE),
            ),
            Hebel(
                # Der Hebel heisst "unabhaengige Trades" und bekam bis
                # Befund 139 die **rohe** Trade-Zahl. Der Name stand also
                # gegen den Wert.
                "unabhaengige Trades",
                float(kandidat.stichprobe),
                loese(
                    "sample_size",
                    float(kandidat.stichprobe),
                    kandidat.stichprobe * 50.0,
                ),
            ),
            _schiefe_hebel(
                schiefe, woelbung, loese("skew", schiefe, schiefe + 50.0)
            ),
        ]

        # Die Woelbung wirkt andersherum: Weniger ist besser, und unter 1 kann
        # keine Verteilung liegen. Deshalb von oben gesucht.
        tief, hoch = 1.0, woelbung
        ziel_woelbung = None if dsr(kurtosis=1.0) < ZIEL else 1.0
        if ziel_woelbung is not None:
            for _ in range(80):
                mitte = (tief + hoch) / 2
                if dsr(kurtosis=mitte) >= ZIEL:
                    tief = mitte
                else:
                    hoch = mitte
            ziel_woelbung = tief
        gefunden.append(
            Hebel("Woelbung", woelbung, ziel_woelbung, kleiner_ist_besser=True)
        )
        return gefunden

    @staticmethod
    def hebelerklaerung(hebel: list[Hebel]) -> str:
        """Was die Zerlegung bedeutet - **aus ihr abgeleitet**.

        Hier stand der Text bis Befund 109 fest verdrahtet in ``cli.py``:

            *"Die Woelbung kann nicht unter 1 fallen. Damit bleibt von den
            vier Wegen einer: die Qualitaet je Trade."*

        Das galt fuer den Perpetual-Lauf, und es hat aufgehoert zu gelten, als
        Befund 108 das Funding wegnahm: Unter Spot ist die Woelbung erreichbar
        (5,79 statt unter 1), und die Zahl der offenen Wege ist zwei, nicht
        einer. Der Satz stand trotzdem weiter da, weil er neben der Rechnung
        stand statt aus ihr zu kommen.

        Dieselbe Sorte Drift wie beim Standardintervall in Befund 103 und beim
        Gate-Docstring in Befund 101: ein fester Satz neben einer gerechneten
        Zahl.
        """
        offen = [h for h in hebel if h.moeglich]
        zu = [h for h in hebel if not h.moeglich]

        if not hebel:
            return "Keine Zerlegung - nichts zu erklaeren."

        if not offen:
            return (
                "**Keiner der vier Wege ist offen.** Jede Groesse muesste auf "
                "einen Wert, den es nicht gibt - das Gate ist entlang dieser "
                "Zerlegung nicht erreichbar."
            )

        namen = ", ".join(h.name for h in offen)
        teile = [
            f"**{len(offen)} von {len(hebel)} Wegen sind offen:** {namen}."
        ]

        leichteste = min(
            (h for h in offen if h.veraenderung is not None),
            key=lambda h: abs(h.veraenderung or 0.0),
            default=None,
        )
        if leichteste is not None:
            teile.append(
                f"Am wenigsten verlangt {leichteste.name}: "
                f"{leichteste.veraenderung:+.0%}."
            )

        for h in zu:
            grund = h.unmoeglich_weil or (
                "kein Wert dieser Groesse laesst das Gate halten"
            )
            teile.append(f"{h.name}: {grund}.")

        teile.append(
            "Und es sind vier von fuenf: Die Streuung der Sharpe-Schaetzer "
            "ueber die Versuche steht hier nicht, weil sie nicht gemessen, "
            "sondern angenommen wird. Sie zu bewegen hiesse, die Huerde zu "
            "verstellen statt den Kandidaten - 'cli streuung' rechnet nach, "
            "wie viel daran haengt."
        )
        return " ".join(teile)

    def tabelle(self, trades: tuple[int, ...] = (50, 100, 152, 200, 300, 500)) -> str:
        zeilen = [
            f"{'Trades':>8} {'noetiger Sharpe je Trade':>26}",
            "-" * 36,
        ]
        for n, wert in self.linie(trades):
            text = f"{wert:.4f}" if wert is not None else "unerreichbar"
            zeilen.append(f"{n:>8} {text:>26}")
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.kandidaten:
            return "Keine Kandidaten - kein Urteil."

        nah = self.naechster
        if nah is None:
            return (
                "Kein Kandidat hat eine Trade-Zahl, bei der das Gate ueberhaupt "
                "erreichbar waere."
            )

        # **Die Lesart gehoert in den Satz.** Steht die Latte auf der rohen
        # Trade-Zahl, ist sie eine Untergrenze - und ein Faktor, der aus einer
        # Untergrenze kommt, ist selbst einer (Befund 139).
        wie = "mindestens " if nah.untergrenze else ""
        teile = [
            f"Am naechsten kam '{nah.kandidat.name}': {nah.kandidat.trades} "
            f"Trades zu je {nah.kandidat.sharpe_je_trade:.4f}, noetig waeren "
            f"{wie}{nah.noetig:.4f} bei {nah.kandidat.stichprobe} "
            f"Beobachtungen - Faktor {wie}{nah.faktor:.2f}."
        ]
        if nah.untergrenze:
            teile.append(
                "Die effektive Stichprobe dieses Kandidaten ist nicht "
                "gemessen; gerechnet ist auf der rohen Trade-Zahl. Das Gate "
                "rechnet seit Befund 135 mit der effektiven, und die ist "
                "kleiner - die wirkliche Latte liegt also hoeher."
            )

        # **Der zweite Betriebspunkt** (Befund 126). Die Kandidaten kommen aus
        # der Bestenliste und tragen Perpetual-Zahlen. Seit Befund 108 ist Spot
        # der bessere gemessene Punkt; ohne diesen Zusatz steht hier ein
        # Faktor, der um die Kostenannahme zu hoch ist.
        if self.spotguete and self.spotguete > nah.kandidat.sharpe_je_trade:
            spotfaktor = nah.noetig / self.spotguete
            # Kommt die Latte aus einer rohen Trade-Zahl, ist auch dieser
            # Faktor eine Untergrenze - er teilt durch dieselbe Latte.
            teile.append(
                f"Unter Spot-Bedingungen ({self.spotguete:.4f} statt "
                f"{nah.kandidat.sharpe_je_trade:.4f}, kein Funding) ist es "
                f"Faktor {wie}{spotfaktor:.2f} - die Zahl oben traegt eine "
                f"Kostenannahme mit, die dort entfaellt."
            )

        unerreichbar = [a for a in self.abstaende() if not a.erreichbar]
        if unerreichbar:
            teile.append(
                f"{len(unerreichbar)} von {len(self.kandidaten)} Kandidaten "
                f"handeln so selten, dass **kein** Sharpe genuegen wuerde."
            )

        preis = self.kosten_je_versuch(nah.kandidat.stichprobe)
        if preis is not None:
            teile.append(
                f"Jeder weitere Einfall hebt die Linie um {preis:.5f} - "
                f"gesucht wird also gegen ein Ziel, das sich beim Suchen "
                f"entfernt."
            )
        return " ".join(teile)
