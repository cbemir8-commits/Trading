"""Haengt das Ergebnis an einer Annahme, die die Engine mangels Daten trifft?

Die Annahme
-----------
``backtest/engine.py`` sagt es im eigenen Docstring:

    *"Beruehrt eine Kerze sowohl Stop als auch Take-Profit, verraet OHLC
    nicht, was zuerst kam. Mit 1-Minuten-Daten wird die Reihenfolge exakt
    aufgeloest. Ohne sie gilt die pessimistische Annahme: erst Liquidation,
    dann Stop, dann Take-Profit."*

``cli wettbewerb`` sucht nach Minutenkerzen. Die gibt es in diesem Projekt
nicht - vorhanden sind **Fuenfzehnminutenkerzen ab 2020-03-30**. Damit ist
jede Zahl dieses Projekts unter der pessimistischen Annahme entstanden, und
was sie kostet, war nie gemessen.

Das Ergebnis
------------
Der Bestand, zweimal gerechnet, sonst alles gleich:

    pessimistisch   152 Trades   13,47 % p.a.   Rueckgang 10,64 %   7/11
    aufgeloest      152 Trades   13,47 % p.a.   Rueckgang 10,64 %   7/11

**Bitgleich.** Die Annahme kostet nichts.

Warum das kein Messfehler ist
-----------------------------
Genau hier liegt die Falle, und die Engine warnt selbst davor: Passen die
Zeitstempel nicht zusammen, findet ``searchsorted`` nichts, die Engine faellt
**still** auf die pessimistische Annahme zurueck, und "kein Unterschied"
bedeutet dann "die Feinkerzen sind nie angekommen".

Nachgezaehlt wurde deshalb, wie oft die Engine wirklich fein aufgeloest hat:
**9.128 von 11.300 Segmentaufrufen, also 80,8 %.** Die uebrigen 19,2 % sind
Balken vor 2020-03-30, fuer die es keine Feinkerzen gibt. Ein fein
aufgeloester Balken zerfaellt in 96 Abschnitte statt in einen.

Und es gab auch etwas zu ordnen - die Ausstiege verteilen sich auf:

    signal_exit    74
    stop_loss      68
    take_profit    10

Beide Arten kommen vor. Haette der Bestand nur Stops und keine Take-Profits,
gaebe es nichts zu ordnen, und Gleichheit waere trivial statt informativ.

Was daraus folgt - und was nicht
--------------------------------
**Es folgt:** In neun Jahren hat keine einzige Tageskerze zugleich Stop und
Take-Profit beruehrt, waehrend eine Position offen war. Die pessimistische
Annahme ist beim Bestand ohne Wirkung, und die 10,64 % Rueckgang sind nicht
dadurch geschoent oder verschlechtert.

**Es folgt nicht**, dass die Annahme allgemein folgenlos ist. Ein Kandidat mit
engem Stop und nahem Ziel wuerde beides oft in derselben Kerze beruehren.
Deshalb ist das hier eine **Probe** und keine einmalige Feststellung: Wer
einen neuen Kandidaten ernst nimmt, faehrt sie fuer ihn.

Warum der Standard trotzdem pessimistisch bleibt
------------------------------------------------
Die Verlockung waere, die Feinkerzen kuenftig immer zu nutzen - genauer ist
genauer. Zwei Gruende dagegen:

1. **Vergleichbarkeit.** Alle 45 Eintraege der Bestenliste sind pessimistisch
   gerechnet. Den Fuellmodus mitten im Projekt zu wechseln erzeugt genau die
   Kollision, die Befund 97 fuer den Kontostand behoben hat - nur waere sie
   diesmal nicht einmal an einem Feld ablesbar.
2. **Richtung.** Die pessimistische Annahme kann ein Ergebnis nur
   schlechter aussehen lassen, nie besser. Ein Haus, das lieber keine
   Strategie hat als eine, die nur im Backtest funktioniert, laesst die
   konservative Annahme stehen, solange sie nichts kostet.

Kostet keinen Versuch: Derselbe Kandidat, dieselben Daten, zweimal gerechnet.
Es wird nichts ausgewaehlt und keine Schwelle angefasst.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Ab welchem Anteil fein aufgeloester Balken die Probe ueberhaupt etwas sagt.
#:
#: Eine gesetzte Grenze und keine hergeleitete - sie steht hier, damit die
#: Willkuer sichtbar ist statt im Code zu verschwinden. Unter der Haelfte
#: sagt "kein Unterschied" mehr ueber die fehlenden Daten aus als ueber die
#: Strategie.
MINDESTQUOTE = 0.5

#: Ausstiegsarten, deren Reihenfolge innerhalb einer Kerze mehrdeutig ist.
#: Kommen nicht mindestens zwei davon vor, gibt es nichts zu ordnen.
MEHRDEUTIG = ("stop_loss", "take_profit", "liquidation")


@dataclass(frozen=True, slots=True)
class Messung:
    """Ein Lauf, in den Zahlen, an denen sich ein Unterschied zeigen wuerde."""

    name: str
    trades: int
    cagr: float
    rueckgang: float
    sharpe: float
    bestanden: int = 0
    gesamt: int = 0


@dataclass(slots=True)
class Aufloesung:
    """Zwei Laeufe desselben Kandidaten - mit und ohne feine Kerzen."""

    pessimistisch: Messung
    aufgeloest: Messung
    feine_balken: int = 0
    balken: int = 0
    ausstiegsgruende: dict[str, int] = field(default_factory=dict)

    @property
    def feinquote(self) -> float:
        """Anteil der Balken, die wirklich in Abschnitte zerlegt wurden."""
        return self.feine_balken / self.balken if self.balken else 0.0

    @property
    def abdeckung_reicht(self) -> bool:
        """**Die Wache gegen den stillen Fehlschlag.**

        Passen die Zeitstempel nicht zusammen, faellt die Engine lautlos auf
        die pessimistische Annahme zurueck. "Kein Unterschied" hiesse dann
        "die Feinkerzen sind nie angekommen" - eine Aussage ueber die
        Datenpipeline, verkleidet als Aussage ueber die Strategie.
        """
        return self.feinquote >= MINDESTQUOTE

    @property
    def gibt_es_zu_ordnen(self) -> bool:
        """Kommen ueberhaupt zwei mehrdeutige Ausstiegsarten vor?

        Ohne Take-Profits gibt es keine Reihenfolge, ueber die man streiten
        koennte, und Gleichheit waere trivial statt informativ.
        """
        vorhanden = [
            art for art in MEHRDEUTIG if self.ausstiegsgruende.get(art, 0) > 0
        ]
        return len(vorhanden) >= 2

    @property
    def unterschiede(self) -> dict[str, float]:
        """Aufgeloest minus pessimistisch, je Kennzahl."""
        a, b = self.pessimistisch, self.aufgeloest
        return {
            "Trades": float(b.trades - a.trades),
            "Rendite": b.cagr - a.cagr,
            "Rueckgang": b.rueckgang - a.rueckgang,
            "Sharpe": b.sharpe - a.sharpe,
            "Gates": float(b.bestanden - a.bestanden),
        }

    @property
    def groesster_unterschied(self) -> float:
        return max((abs(w) for w in self.unterschiede.values()), default=0.0)

    @property
    def haengt_an_der_annahme(self) -> bool:
        """Aendert sich etwas, wenn die Reihenfolge bekannt ist?

        Streng: Jeder Unterschied zaehlt. Eine Toleranz waere hier falsch -
        die Frage ist nicht, ob der Unterschied gross ist, sondern ob es
        einen gibt.
        """
        return self.groesster_unterschied > 0.0

    @property
    def belastbar(self) -> bool:
        """Darf aus dieser Probe ueberhaupt ein Schluss gezogen werden?"""
        return self.abdeckung_reicht and self.gibt_es_zu_ordnen

    def tabelle(self) -> str:
        zeilen = [
            f"{'Lauf':<16}{'Trades':>8}{'Rendite':>10}{'Rueckgang':>11}"
            f"{'Sharpe':>9}{'Gates':>8}",
            "-" * 62,
        ]
        for m in (self.pessimistisch, self.aufgeloest):
            zeilen.append(
                f"{m.name[:15]:<16}{m.trades:>8}{m.cagr:>9.2f} %"
                f"{m.rueckgang:>10.2f} %{m.sharpe:>9.3f}"
                f"{f'{m.bestanden}/{m.gesamt}':>8}"
            )
        zeilen.append("-" * 62)
        zeilen.append(
            f"{'fein aufgeloest':<16}{self.feine_balken:>8} von {self.balken} "
            f"Balken ({self.feinquote:.1%})"
        )
        if self.ausstiegsgruende:
            zeilen.append(
                "Ausstiege: "
                + ", ".join(
                    f"{grund} {n}"
                    for grund, n in sorted(
                        self.ausstiegsgruende.items(), key=lambda x: -x[1]
                    )
                )
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.abdeckung_reicht:
            return (
                f"**Die Probe traegt nicht.** Nur {self.feinquote:.1%} der "
                f"Balken wurden wirklich fein aufgeloest; verlangt sind "
                f"{MINDESTQUOTE:.0%}. Ein Ergebnis hiesse hier mehr ueber die "
                f"fehlenden Feinkerzen als ueber die Strategie - genau der "
                f"stille Fehlschlag, vor dem die Engine im eigenen Docstring "
                f"warnt."
            )

        if not self.gibt_es_zu_ordnen:
            arten = ", ".join(sorted(self.ausstiegsgruende)) or "keine"
            return (
                f"**Es gibt nichts zu ordnen.** Von den mehrdeutigen "
                f"Ausstiegsarten kommt hoechstens eine vor ({arten}). Ohne "
                f"zwei davon kann keine Kerze beide zugleich beruehren, und "
                f"Gleichheit waere trivial statt informativ."
            )

        if not self.haengt_an_der_annahme:
            return (
                f"**Das Ergebnis haengt nicht an der Annahme.** Bei "
                f"{self.feinquote:.1%} fein aufgeloesten Balken aendert sich "
                f"keine der Kennzahlen - in der ganzen Historie hat keine "
                f"Kerze zugleich Stop und Take-Profit beruehrt, waehrend eine "
                f"Position offen war.\n\n"
                f"Das gilt fuer diesen Kandidaten. Einer mit engem Stop und "
                f"nahem Ziel wuerde beides oft in derselben Kerze beruehren - "
                f"deshalb ist das eine Probe und keine einmalige Feststellung."
            )

        teile = [
            "**Das Ergebnis haengt an der Annahme.** Mit bekannter "
            "Reihenfolge aendern sich:"
        ]
        for name, wert in self.unterschiede.items():
            if wert:
                teile.append(f"  {name}: {wert:+.3f}")
        teile.append(
            "Die pessimistische Annahme kann ein Ergebnis nur schlechter "
            "aussehen lassen, nie besser. Der Unterschied ist damit der "
            "Betrag, um den dieser Kandidat bisher unterschaetzt wurde - "
            "und keine Verbesserung, die man ihm gutschreiben darf, ohne "
            "die uebrigen Kandidaten gleich zu behandeln."
        )
        return "\n".join(teile)


__all__ = ["MEHRDEUTIG", "MINDESTQUOTE", "Aufloesung", "Messung"]
