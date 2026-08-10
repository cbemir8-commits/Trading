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

    @property
    def moeglich(self) -> bool:
        """Gibt es ueberhaupt einen Wert, bei dem das Gate allein daran haelt?"""
        return self.noetig is not None

    @property
    def veraenderung(self) -> float | None:
        if self.noetig is None or self.jetzt == 0:
            return None
        return self.noetig / self.jetzt - 1.0

    def __str__(self) -> str:
        if self.noetig is None:
            return f"{self.name:22} {self.jetzt:>9.3f}   unerreichbar"
        pfeil = "->"
        anteil = self.veraenderung
        zusatz = f"   ({anteil:+.0%})" if anteil is not None else ""
        return f"{self.name:22} {self.jetzt:>9.3f} {pfeil} {self.noetig:>9.3f}{zusatz}"


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
    def erreichbar(self) -> bool:
        """Genuegt bei dieser Trade-Zahl ueberhaupt irgendein Sharpe?

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


@dataclass(slots=True)
class Budget:
    """Die Grenzlinie, die Kandidaten daran, und was Weitersuchen kostet."""

    versuche: int
    kandidaten: list[Kandidat] = field(default_factory=list)
    schiefe: float = SCHIEFE
    woelbung: float = WOELBUNG

    def noetig_bei(
        self,
        trades: int,
        *,
        versuche: int | None = None,
        schiefe: float | None = None,
        woelbung: float | None = None,
    ) -> float | None:
        return noetiger_sharpe(
            trades=trades,
            trials=self.versuche if versuche is None else versuche,
            skew=self.schiefe if schiefe is None else schiefe,
            kurtosis=self.woelbung if woelbung is None else woelbung,
        )

    def abstaende(self, *, versuche: int | None = None) -> list[Abstand]:
        return [
            Abstand(
                kandidat=k,
                noetig=self.noetig_bei(
                    k.trades,
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

    def linie(self, trades: tuple[int, ...]) -> list[tuple[int, float | None]]:
        return [(n, self.noetig_bei(n)) for n in trades]

    def kosten_je_versuch(self, trades: int, *, schritte: int = 10) -> float | None:
        """Um wie viel die Linie steigt, wenn ``schritte`` Versuche dazukommen.

        Geteilt durch ``schritte`` - also der Preis eines einzelnen Einfalls,
        ausgedrueckt in dem, was er von allen kuenftigen verlangt.
        """
        jetzt = self.noetig_bei(trades)
        spaeter = self.noetig_bei(trades, versuche=self.versuche + schritte)
        if jetzt is None or spaeter is None:
            return None
        return (spaeter - jetzt) / schritte

    def hebel(self, kandidat: Kandidat) -> list[Hebel]:
        """Woran es liegt - je Eingang der Formel einzeln.

        Der Deflated Sharpe haengt an vier gemessenen Groessen: Qualitaet je
        Trade, Zahl der **unabhaengigen** Trades, Schiefe und Woelbung. Die
        Grenzlinie zeigt nur die erste. Diese Zerlegung fragt fuer jede
        einzeln: Wo muesste sie stehen, damit das Gate haelt - alles andere
        unveraendert?

        Das entscheidet, ob Weitersuchen ueberhaupt Sinn hat. Eine Groesse,
        die auf einen unmoeglichen Wert muesste, schliesst ihren Weg; eine,
        die um zehn Prozent muesste, benennt ihn.
        """
        schiefe = kandidat.schiefe if kandidat.schiefe is not None else self.schiefe
        woelbung = (
            kandidat.woelbung if kandidat.woelbung is not None else self.woelbung
        )

        def dsr(**abweichung) -> float:
            werte = {
                "observed_sharpe": kandidat.sharpe_je_trade,
                "trials": max(self.versuche, 1),
                "sample_size": kandidat.trades,
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
                "unabhaengige Trades",
                float(kandidat.trades),
                loese("sample_size", float(kandidat.trades), kandidat.trades * 50.0),
            ),
            Hebel("Schiefe", schiefe, loese("skew", schiefe, schiefe + 50.0)),
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

        teile = [
            f"Am naechsten kam '{nah.kandidat.name}': {nah.kandidat.trades} "
            f"Trades zu je {nah.kandidat.sharpe_je_trade:.4f}, noetig waeren "
            f"{nah.noetig:.4f} - Faktor {nah.faktor:.2f}."
        ]

        unerreichbar = [a for a in self.abstaende() if not a.erreichbar]
        if unerreichbar:
            teile.append(
                f"{len(unerreichbar)} von {len(self.kandidaten)} Kandidaten "
                f"handeln so selten, dass **kein** Sharpe genuegen wuerde."
            )

        preis = self.kosten_je_versuch(nah.kandidat.trades)
        if preis is not None:
            teile.append(
                f"Jeder weitere Einfall hebt die Linie um {preis:.5f} - "
                f"gesucht wird also gegen ein Ziel, das sich beim Suchen "
                f"entfernt."
            )
        return " ".join(teile)
