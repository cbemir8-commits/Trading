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

from research.erreichbarkeit import noetiger_sharpe

#: Schiefe und Woelbung, mit denen die Linie gerechnet wird. Voreingestellt
#: sind die des Spitzenkandidaten: Beide gehen in den Deflated Sharpe ein, und
#: eine Normalverteilung anzunehmen waere hier deutlich zu freundlich.
SCHIEFE = 3.473
WOELBUNG = 15.951


@dataclass(frozen=True, slots=True)
class Kandidat:
    """Ein gemessener Einfall - Trade-Zahl und Qualitaet je Trade."""

    name: str
    trades: int
    sharpe_je_trade: float


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

    def noetig_bei(self, trades: int, *, versuche: int | None = None) -> float | None:
        return noetiger_sharpe(
            trades=trades,
            trials=self.versuche if versuche is None else versuche,
            skew=self.schiefe,
            kurtosis=self.woelbung,
        )

    def abstaende(self, *, versuche: int | None = None) -> list[Abstand]:
        return [
            Abstand(kandidat=k, noetig=self.noetig_bei(k.trades, versuche=versuche))
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
