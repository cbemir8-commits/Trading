"""Der Not-Aus wird zwischen den Fenstern freigegeben - und wer gibt ihn in
einem durchgehenden Lauf frei?

Die Annahme steht in der Engine
-------------------------------
``Backtester._officer`` legt fuer jeden Lauf einen frischen ``RiskOfficer``
an und begruendet das selbst::

    Kein ``state_path``: Jeder Lauf beginnt frei. Im Walk-Forward heisst das,
    dass jedes Testfenster mit einem frischen Officer startet - was der
    Annahme entspricht, dass der Nutzer einen ausgeloesten Not-Aus zwischen
    den Fenstern manuell freigibt. **Ohne diese Annahme bliebe jedes Fenster
    nach dem ersten Not-Aus fuer immer stumm, und der Backtest waere in der
    anderen Richtung falsch.**

Ein Walk-Forward hat Fenstergrenzen, also Freigaben. Ein **durchgehender**
Lauf hat keine. Der Satz beschreibt damit genau das, was in einem
durchgehenden Lauf passiert - und nennt es falsch.

Warum das ein Gate trifft
-------------------------
Zwei der elf Gates messen nicht am Walk-Forward-Bericht, sondern rechnen
eigene Backtests: ``gate_parameter_plateau`` faehrt zwoelf Nachbarn, und
``gate_cost_stress`` faehrt den Kandidaten mit doppelten Kosten. Beide rufen
``Backtester.run`` **einmal ueber die ganze Reihe**, je Bein. Acht Jahre, ein
Officer, keine Freigabe.

Drei Sperren sind Zustaende und keine Uhren:

===================  ====================================================
``kill_switch``      ``TradingState.KILLED`` - nur ``reset_kill_switch``
``trading_paused``   ``TradingState.PAUSED`` - nur ``resume``
``close_only``       ``TradingState.CLOSE_ONLY`` - nur manuell
===================  ====================================================

Keine davon ruft ein Backtest je auf. ``daily_loss_limit`` (24 Stunden) und
``news_blackout`` laufen dagegen von selbst ab und legen nichts stumm.

Was daran haengt - und was nicht
--------------------------------
Dieses Modul **aendert kein Gate**. Es misst, ob die Nachbarn eines
Plateau-Laufs zu Ende gemessen wurden oder unterwegs abgeschaltet, und
stellt der durchgehenden Zahl die Walk-Forward-Zahl daneben - also die
Messart, aus der in diesem Projekt jede andere Zahl stammt.

Ob das Gate seine Nachbarn kuenftig so messen soll, ist damit **nicht**
entschieden. Diese Frage verschoebe ein Gate von "durchgefallen" auf
"bestanden", und sie entsteht, waehrend der eigene Kandidat dicht daneben
steht - dieselbe Lage wie in Befund 278, und dieselbe Antwort: messen,
hinschreiben, nicht selbst entscheiden.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

#: Sperrgruende, die ein Lauf aus eigener Kraft nicht wieder los wird.
#:
#: Die Namen sind die Werte von ``execution.risk.VetoReason`` - bewusst als
#: Zeichenketten, weil ``BacktestResult.veto_reasons`` sie so zaehlt. Wer hier
#: eine Uhr einsortiert (``daily_loss_limit``, ``news_blackout``), macht aus
#: einer Pause von Stunden eine Stilllegung von Jahren.
STILLLEGEND = frozenset({"kill_switch", "trading_paused", "close_only"})


def stillgelegt(vetos: Mapping[str, int]) -> int:
    """Wie viele Einstiege eine **dauerhafte** Sperre verhindert hat.

    Null heisst: Dieser Lauf ist bis zum letzten Balken gelaufen. Alles
    darueber heisst, dass ab irgendeinem Zeitpunkt nicht mehr gehandelt
    wurde und der Rest der Reihe ungemessen blieb.
    """
    return sum(n for grund, n in vetos.items() if grund in STILLLEGEND)


@dataclass(frozen=True, slots=True)
class Lauf:
    """Ein Nachbar, zweimal gemessen: durchgehend und im Walk-Forward."""

    stellgroesse: str
    kennung: str
    faktor: float
    durchgehend: float
    """Summe ueber die Beine, genau wie das Gate sie bildet."""

    walkforward: float
    """Dieselbe Regel durch ``run_portfolio_walkforward``, Summe der Trades.

    Verglichen wird nur das **Vorzeichen** - mehr benutzt das Gate auch
    nicht. Die beiden Zahlen sind deshalb nicht gegeneinander aufzurechnen:
    Der Walk-Forward handelt nur seine Testfenster, der durchgehende Lauf die
    ganze Reihe.
    """

    gesperrt: int
    """Einstiege, die eine dauerhafte Sperre verhindert hat."""

    trades: int
    letzter_trade: datetime | None = None

    @property
    def traegt(self) -> bool:
        return self.durchgehend > 0

    @property
    def traegt_im_walkforward(self) -> bool:
        return self.walkforward > 0

    @property
    def kippt(self) -> bool:
        """Sagen die beiden Messarten Verschiedenes?"""
        return self.traegt is not self.traegt_im_walkforward

    @property
    def zu_ende_gemessen(self) -> bool:
        return self.gesperrt == 0


@dataclass(frozen=True, slots=True)
class Freigabelage:
    """Die Nachbarschaft eines Kandidaten unter beiden Messarten.

    ``schwelle`` ist die des Plateau-Gates; die Quoten werden genauso
    gebildet wie dort - Minimum ueber die Stellgroessen, nicht Durchschnitt.
    """

    laeufe: tuple[Lauf, ...]
    schwelle: float = 0.6

    def quoten(self, *, walkforward: bool = False) -> dict[str, float]:
        """Je Stellgroesse der Anteil tragender Nachbarn."""
        return quoten_je_stellgroesse(self.laeufe, walkforward=walkforward)

    def quote(self, *, walkforward: bool = False) -> float:
        """Der Gate-Wert: die **schwaechste** Stellgroesse, wie im Gate."""
        quoten = self.quoten(walkforward=walkforward)
        return min(quoten.values()) if quoten else 0.0

    def schwaechste(self, *, walkforward: bool = False) -> str:
        quoten = self.quoten(walkforward=walkforward)
        if not quoten:
            return ""
        namen = {lauf.kennung: lauf.stellgroesse for lauf in self.laeufe}
        return namen[min(quoten, key=lambda k: (quoten[k], namen[k]))]

    @property
    def stillgelegte(self) -> tuple[Lauf, ...]:
        return tuple(x for x in self.laeufe if x.gesperrt)

    @property
    def kipper(self) -> tuple[Lauf, ...]:
        return tuple(x for x in self.laeufe if x.kippt)

    def tabelle(self) -> str:
        kopf = (
            f"  {'Nachbar':28} {'durchgehend':>12} {'Walk-Forward':>13} "
            f"{'gesperrt':>9}  Urteil"
        )
        zeilen = [kopf, "  " + "-" * 74]
        for x in self.laeufe:
            marke = "  <== verschieden" if x.kippt else ""
            zeilen.append(
                f"  {x.stellgroesse + f' x{x.faktor:g}':28} "
                f"{x.durchgehend:>+12.2f} {x.walkforward:>+13.2f} "
                f"{x.gesperrt:>9}  "
                f"{'+' if x.traegt else '-'} / "
                f"{'+' if x.traegt_im_walkforward else '-'}{marke}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        """Was gemessen wurde - und ausdruecklich, was daraus nicht folgt."""
        if not self.laeufe:
            return "Keine Nachbarn - keine Aussage."

        durch = self.quote()
        wf = self.quote(walkforward=True)
        teile = [
            f"Gate-Wert durchgehend (so misst das Gate heute) {durch:.3f}, "
            f"im Walk-Forward {wf:.3f} - Schwelle {self.schwelle:.3f}.",
        ]

        still = self.stillgelegte
        if not still:
            teile.append(
                "Kein Nachbar wurde unterwegs abgeschaltet: Beide Messarten "
                "messen hier dieselbe Reihe zu Ende, und der Unterschied "
                "zwischen ihnen ist keiner der Sperren."
            )
            return " ".join(teile)

        summe = sum(x.gesperrt for x in still)
        teile.append(
            f"{len(still)} von {len(self.laeufe)} Nachbarn wurden **nicht zu "
            f"Ende gemessen**: Eine dauerhafte Sperre - Not-Aus oder "
            f"Wochenlimit - hat zusammen {summe} Einstiege verhindert und "
            f"laeuft bis zur manuellen Freigabe, die in einem durchgehenden "
            f"Lauf nie kommt."
        )

        kipper = self.kipper
        if kipper:
            namen = ", ".join(f"{x.stellgroesse} x{x.faktor:g}" for x in kipper)
            teile.append(
                f"Bei {len(kipper)} davon entscheidet das ueber das "
                f"Vorzeichen: {namen}."
            )

        if (durch >= self.schwelle) == (wf >= self.schwelle):
            teile.append(
                "Am Urteil des Gates aendert das hier nichts - beide "
                "Messarten fallen auf dieselbe Seite der Schwelle."
            )
        else:
            teile.append(
                "**Damit haengt das Urteil des Gates an der Messart.** "
                "Geaendert wird deshalb nichts: Welche der beiden richtig "
                "ist, entscheidet sich nicht daran, dass die eine dem "
                "eigenen Kandidaten besser bekommt. Die Frage gehoert zum "
                "Nutzer, mit diesen Zahlen daneben."
            )
        return " ".join(teile)


def sperrsatz(gesperrt: int) -> str:
    """Was statt einer Randlage dasteht, wenn die Nachbarn abgeschaltet waren.

    Die Randlage liest aus zwei Punkten die Form eines Gebiets. Ein Punkt,
    an dem ab 2020 nicht mehr gehandelt wurde, ist aber keine Messung der
    Form - er sagt, wann die Sperre griff, und nichts darueber, wie die
    Strategie dort gelaufen waere. Denselben Fehler hat ``randlage`` schon
    einmal vermieden ("einseitig gemessen"); dies ist die zweite Art, auf
    die ein Punkt fehlen kann.
    """
    return (
        f"die gescheiterten Nachbarn wurden **nicht zu Ende gemessen** - eine "
        f"dauerhafte Sperre (Not-Aus oder Wochenlimit) hat dort {gesperrt} "
        f"Einstiege verhindert und laeuft bis zur manuellen Freigabe, die in "
        f"einem durchgehenden Lauf nie kommt. Welche Form das Gebiet hier "
        f"hat, sagt diese Messung nicht ('cli freigabe' misst es)"
    )


def bestandsatz(gesperrt_punkte: int, punkte: int, einstiege: int) -> str:
    """Was neben einem **bestandenen** Plateau stehen muss - Befund 330.

    ``sperrsatz`` gibt es seit Befund 313, und es haengt nur am
    Fehlschlag-Zweig des Gates. Gemessen am Spitzenkandidaten, Spot:

        Parameter-Plateau   PASS, Wert 1,0000 gegen Schwelle 0,60
        Nachbarn            12 von 12 profitabel
        davon stillgelegt   12 von 12
        verhinderte Einstiege 737

    Die volle Punktzahl steht also auf zwoelf Laeufen, von denen **keiner** zu
    Ende gemessen wurde - und die Botschaft schwieg dazu, weil der Satz nur im
    anderen Zweig stand. Dieselbe Bauart wie Befund 321/322: Was nicht gemessen
    wurde, zaehlte als bestanden.

    **Wert und Urteil des Gates bleiben unberuehrt.** Ob ein stillgelegter
    Nachbar ueberhaupt zaehlen darf, liegt als Entscheidung beim Nutzer (Befund
    313). Hier steht nur, was gemessen wurde - und was nicht.
    """
    if not gesperrt_punkte:
        return ""
    alle = gesperrt_punkte == punkte
    wer = (
        "**kein einziger Nachbar wurde zu Ende gemessen**"
        if alle
        else f"**{gesperrt_punkte} von {punkte} Nachbarn** wurden nicht zu "
        f"Ende gemessen"
    )
    return (
        f" {wer} - eine dauerhafte Sperre hat dort {einstiege} Einstiege "
        f"verhindert und laeuft bis zur manuellen Freigabe, die in einem "
        f"durchgehenden Lauf nie kommt. Die Quote oben sagt damit nicht, "
        f"welche Form das Gebiet hat ('cli freigabe' misst es)."
    )


def quoten_je_stellgroesse(
    laeufe: Sequence[Lauf], *, walkforward: bool = False
) -> dict[str, float]:
    """Je Stellgroesse der Anteil tragender Nachbarn - wie im Plateau-Gate.

    Als Funktion und nicht nur als Methode, weil das Gate sie in derselben
    Form braucht: Wuerde jede Seite ihre eigene Quote bilden, verglichen sie
    verschiedene Dinge - der Fehler, den ``nachbarschaft`` in ihrem eigenen
    Docstring schon fuer die Skalierung festhaelt.
    """
    je: dict[str, list[bool]] = {}
    for lauf in laeufe:
        traegt = lauf.traegt_im_walkforward if walkforward else lauf.traegt
        je.setdefault(lauf.kennung, []).append(traegt)
    return {k: sum(v) / len(v) for k, v in je.items()}
