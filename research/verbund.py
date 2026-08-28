"""Zwei verschiedene Regeln zusammen - und was die Abhaengigkeit davon uebrig laesst.

Die Richtung, die noch offen war
--------------------------------
Nach Befund 70 fuehrt genau ein Weg zum haertesten Gate: mehr **Guete**, also
``SR/Trade * sqrt(n_eff)``. Alle Regler daran sind ausgemessen, und Befund 54
hat die Kopplung gezeigt: Wer denselben Kandidaten oefter handeln laesst,
verliert an Qualitaet, was er an Menge gewinnt.

Aber es gibt Kandidaten mit **hoeherer** Qualitaet je Trade, die nur zu selten
handeln:

    Spitzenkandidat                 0,2591 je Trade   154 Trades   Guete 3,22
    Trend-Beteiligung 200 Tage      0,3185 je Trade    53 Trades   Guete 2,32
    Donchian-Ausbruch 55/20         0,3074 je Trade    58 Trades   Guete 2,34

Ihre Qualitaet liegt 19 bis 23 % ueber dem Spitzenkandidaten - deutlich mehr
als die noetigen 13 %. Was fehlt, ist Menge. Sie **zusammen** zu handeln waere
also nicht dieselbe Kopplung: Die Trades kaemen aus verschiedenen Regeln, nicht
aus einer haeufiger ausgeloesten.

Warum das nicht das Ensemble-Loch von Befund 27 ist
----------------------------------------------------
Doch, es ist dieselbe Gefahr - und deshalb steht sie hier vorne. Dort brachte
dieselbe Regel mit drei Perioden 481 statt 154 Trades und einen Deflated Sharpe
von 0,999. Die Fenstergewinne korrelierten mit 0,884: dreimal dasselbe Signal,
dreimal gezaehlt.

Der Unterschied ist **nicht** die Absicht, sondern die gemessene Abhaengigkeit.
Deshalb wird hier nichts behauptet, sondern die effektive Stichprobe genauso
gerechnet wie im Gate - mit Fensterbloecken **und** gleichzeitig offenen
Positionen.

Der Fehler, der beim ersten Anlauf herauskam
--------------------------------------------
Die erste Probe liess die Fensterbloecke weg und legte nur die Trades
zusammen. Ergebnis: 207 Trades, keine Kuerzung, Guete 3,97 - **ueber der
noetigen Guete von 3,62.** Das Gate waere bestanden gewesen.

Mit Bloecken bleibt von den 207 Trades eine effektive Stichprobe von 149, und
die Guete faellt auf 3,368. Der Unterschied ist genau das Loch aus Befund 27,
nur eine Regel weiter: Wer zwei korrelierte Ertragsstroeme addiert, ohne die
Korrelation zu messen, zaehlt Information doppelt.

Was tatsaechlich uebrig bleibt
------------------------------
    Spitze allein                          Guete 3,216   DSR 0,7964
    + Trend-Beteiligung 200 Tage           Guete 3,368   DSR 0,8602
    + Donchian-Ausbruch 55/20              Guete 2,645   DSR 0,4490

Der erste Verbund ist der groesste Sprung, den in diesem Projekt je etwas
gebracht hat - die ganze Reglerlandschaft lag zwischen 0,42 und 0,86. Er
reicht trotzdem nicht: noetig sind 0,95.

Und der zweite zeigt, dass es nicht von selbst hilft. Beide Partner haben
praktisch dieselbe Einzelguete (2,32 und 2,34); der eine hebt den Verbund, der
andere halbiert ihn. Es entscheidet allein, wie unabhaengig die Ertraege sind.

Zur Positionsgroesse
--------------------
Zwei Regeln parallel zu handeln heisst, das Kapital zu teilen. Auf den
Deflated Sharpe wirkt sich das **nicht** aus: Er haengt an ``SR/Trade``,
Stichprobe und Verteilungsform, und alle drei sind gegen eine gleichmaessige
Skalierung unempfindlich (Befund 30). Auf Rendite und Rueckgang wirkt es sehr
wohl - fuer die uebrigen Gates ist ein Verbund also **nicht** gerechnet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from research.gates import deflated_sharpe_ratio
from research.suchbudget import ZIEL, Kandidat


def fensterbloecke(berichte: list) -> list[list[float]]:
    """Die Trades **je Fenster** ueber alle Beine zusammengelegt.

    Der Kern der ganzen Rechnung. Wer stattdessen alle Trades in einen Topf
    wirft, verliert die Blockstruktur - und damit das einzige Mittel, mit dem
    das Gate Abhaengigkeit ueberhaupt erkennt. Genau daran ist die erste Probe
    zu diesem Modul gescheitert: ohne Bloecke Guete 3,97, mit Bloecken 3,37.

    Fenster werden ueber ihre Reihenfolge gepaart, nicht ueber Zeitstempel:
    Der Walk-Forward teilt fuer alle Kandidaten identisch, weil er dieselben
    Kursreihen bekommt. Ungleich lange Laeufe werden auf die kuerzeste Zahl
    gestutzt - lieber weniger Bloecke als falsch gepaarte.
    """
    if not berichte:
        return []
    laenge = min(len(b.windows) for b in berichte)
    return [
        [float(t.net_pnl) for b in berichte for t in b.windows[i].trades]
        for i in range(laenge)
    ]


@dataclass(frozen=True, slots=True)
class Bein:
    """Ein Kandidat im Verbund, an seinen eigenen Trades gemessen."""

    name: str
    kandidat: Kandidat
    effektiv: int

    @property
    def guete(self) -> float:
        return self.kandidat.sharpe_je_trade * self.effektiv**0.5


@dataclass(slots=True)
class Verbund:
    """Mehrere Regeln als ein Ertragsstrom - mit gemessener Abhaengigkeit."""

    name: str
    trades: list = field(default_factory=list)
    bloecke: list[list[float]] = field(default_factory=list)
    versuche: int = 0
    beine: list[Bein] = field(default_factory=list)
    korrelation: float | None = None
    """Korrelation der Fenstergewinne. Beim Perioden-Ensemble waren es 0,884 -
    dort war die Trade-Vermehrung dreimal dasselbe Signal."""

    @property
    def kandidat(self) -> Kandidat | None:
        return Kandidat.aus_trades(self.name, self.trades)

    @property
    def stichprobe(self):
        # Dieselbe Rechnung wie im Gate - und zwar durch dieselbe Funktion.
        # Hier stand ein Nachbau ohne Quartalseinteilung, also die Fassung
        # von vor Befund 135. Ausgerechnet in dem Modul, dessen Kopf den
        # Fehler beschreibt, den ein zu grosszuegiges n anrichtet.
        from research.gates import stichprobe_wie_im_gate

        return stichprobe_wie_im_gate(self.trades, bloecke=self.bloecke or None)

    @property
    def guete(self) -> float | None:
        k = self.kandidat
        return (
            k.sharpe_je_trade * self.stichprobe.effektiv**0.5 if k is not None else None
        )

    @property
    def dsr(self) -> float | None:
        k = self.kandidat
        if k is None or k.schiefe is None or k.woelbung is None:
            return None
        return deflated_sharpe_ratio(
            observed_sharpe=k.sharpe_je_trade,
            trials=max(self.versuche, 1),
            sample_size=self.stichprobe.effektiv,
            skew=k.schiefe,
            kurtosis=k.woelbung,
        )

    @property
    def bestes_bein(self) -> Bein | None:
        return max(self.beine, key=lambda b: b.guete) if self.beine else None

    @property
    def hilft(self) -> bool:
        """Ist der Verbund besser als sein bestes Einzelbein?"""
        guete, bestes = self.guete, self.bestes_bein
        return guete is not None and bestes is not None and guete > bestes.guete

    def tabelle(self) -> str:
        zeilen = [
            f"{'':<30} {'SR/Trade':>9} {'roh':>6} {'n_eff':>6} {'Guete':>7}",
            "-" * 62,
        ]
        for bein in self.beine:
            zeilen.append(
                f"{bein.name[:30]:<30} {bein.kandidat.sharpe_je_trade:>9.4f} "
                f"{bein.kandidat.trades:>6} {bein.effektiv:>6} {bein.guete:>7.3f}"
            )
        k, guete = self.kandidat, self.guete
        if k is not None and guete is not None:
            st = self.stichprobe
            zeilen.append("-" * 62)
            zeilen.append(
                f"{'verbunden':<30} {k.sharpe_je_trade:>9.4f} {st.roh:>6} "
                f"{st.effektiv:>6} {guete:>7.3f}"
            )
        return "\n".join(zeilen)

    def urteil(self, *, noetige_guete: float | None = None) -> str:
        guete, dsr, bestes = self.guete, self.dsr, self.bestes_bein
        if guete is None or dsr is None or bestes is None:
            return "Zu wenige Trades - der Verbund laesst sich nicht einordnen."

        st = self.stichprobe
        kuerzung = (
            f"Von {st.roh} rohen Trades bleiben {st.effektiv} unabhaengige - "
            f"die Fensterbloecke kuerzen {1 - st.effektiv / st.roh:.0%}. "
            if st.effektiv < st.roh
            else f"Die {st.roh} Trades werden nicht gekuerzt. "
        )
        naehe = ""
        if noetige_guete is not None:
            naehe = (
                f" Noetig fuer die Schwelle waeren {noetige_guete:.3f}; "
                f"es fehlen {noetige_guete - guete:.3f}."
                if guete < noetige_guete
                else f" Damit ist die noetige Guete von {noetige_guete:.3f} "
                f"erreicht - was **ein** Gate von elf ist."
            )

        if not self.hilft:
            return (
                f"**Der Verbund ist schlechter als sein bestes Bein.** "
                f"{guete:.3f} gegen {bestes.guete:.3f} von "
                f"'{bestes.name}'. {kuerzung}Die beiden Ertraege sind sich zu "
                f"aehnlich; addierte Trades ohne unabhaengige Information "
                f"heben die Zahl und nicht die Aussage."
            )

        return (
            f"**Der Verbund hebt die Guete auf {guete:.3f}** - bestes "
            f"Einzelbein {bestes.guete:.3f} ('{bestes.name}'), Deflated Sharpe "
            f"{dsr:.4f}. {kuerzung}{naehe}\n\n"
            f"Gegengeprueft gehoert das an den uebrigen Gates: Zwei Regeln "
            f"parallel teilen das Kapital, und auf Rendite und Rueckgang "
            f"wirkt das sehr wohl - auf den Deflated Sharpe nicht."
        )


def fensterkorrelation(a, b) -> float | None:
    """Wie aehnlich sich zwei Kandidaten ueber die Fenster verhalten.

    Die Zahl, an der das Perioden-Ensemble aufgeflogen ist: 0,884 hiess dort
    dreimal dasselbe Signal. Sie erklaert, was die Blockkuerzung dann tut.
    """
    gewinne = []
    for bericht in (a, b):
        gewinne.append(
            np.array(
                [sum(float(t.net_pnl) for t in w.trades) for w in bericht.windows]
            )
        )
    if len(gewinne[0]) != len(gewinne[1]) or len(gewinne[0]) < 3:
        return None
    if np.std(gewinne[0]) == 0 or np.std(gewinne[1]) == 0:
        return None
    return float(np.corrcoef(gewinne[0], gewinne[1])[0, 1])


def baue(namen_und_berichte: list[tuple[str, object]], *, versuche: int) -> Verbund:
    """Aus fertigen Walk-Forward-Berichten einen Verbund bilden."""
    berichte = [b for _, b in namen_und_berichte]
    beine = []
    for name, bericht in namen_und_berichte:
        trades = list(bericht.all_trades)
        kandidat = Kandidat.aus_trades(name, trades)
        if kandidat is None:
            continue
        from research.gates import stichprobe_wie_im_gate

        eigene = [[float(t.net_pnl) for t in w.trades] for w in bericht.windows]
        st = stichprobe_wie_im_gate(trades, bloecke=eigene)
        beine.append(Bein(name=name, kandidat=kandidat, effektiv=st.effektiv))

    alle = [t for b in berichte for t in b.all_trades]
    korrelation = (
        fensterkorrelation(berichte[0], berichte[1]) if len(berichte) == 2 else None
    )
    return Verbund(
        name=" + ".join(n for n, _ in namen_und_berichte),
        trades=alle,
        bloecke=fensterbloecke(berichte),
        versuche=versuche,
        beine=beine,
        korrelation=korrelation,
    )


def noetige_guete(effektiv: int, versuche: int) -> float | None:
    """Welche Guete die Schwelle bei dieser **effektiven** Stichprobe verlangt.

    ``effektiv`` ist die effektive Stichprobe, nicht die rohe Trade-Zahl - und
    dieses Modul weiss besser als jedes andere, warum: Der erste Anlauf oben
    hat genau diesen Fehler gemacht und mit 207 rohen Trades eine Guete von
    3,97 gegen eine Latte von 3,62 gestellt. Das Gate waere bestanden gewesen.
    Mit Bloecken blieben 149 Beobachtungen und eine Guete von 3,368.

    Der Fehler sass danach nicht mehr in der Rechnung, sondern im Aufruf:
    Fuenf von sechs Stellen uebergaben weiter die rohe Zahl (Befund 139).
    """
    from research.suchbudget import Budget

    noetig = Budget(versuche=versuche).noetig_bei(effektiv)
    return noetig * effektiv**0.5 if noetig is not None else None


__all__ = [
    "ZIEL",
    "Bein",
    "Verbund",
    "baue",
    "fensterbloecke",
    "fensterkorrelation",
    "noetige_guete",
]
