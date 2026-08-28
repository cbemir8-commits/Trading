"""Welche Kerzenlaenge kann den Deflated Sharpe arithmetisch ueberhaupt tragen?

Die Rechnung, die nie gemacht wurde
-----------------------------------
Befund 61 hat den Stand zugespitzt: Von vier offenen Gates ist genau eines ein
ungeloestes Qualitaetsproblem, und es heisst Deflated Sharpe. Befund 54 hat
gezeigt, warum es auf Tageskerzen nicht loesbar ist - Qualitaet und Menge sind
dort gekoppelt, weil die Historie nur rund 3300 Tage hergibt.

Auf Fuenfzehnminutenkerzen liegen **222 700** Kerzen je Markt. Die
naheliegende Hoffnung: Der noetige Vorteil je Trade faellt mit ``1/sqrt(N)``,
also braucht es bei sehr vielen Trades nur noch einen winzigen. Zweitausend
Trades zu je 0,08 Sharpe ergeben dieselbe Guete wie hundertfuenfzig zu je 0,29.

**Die Hoffnung hat einen Haken, und der ist rechenbar.** Der noetige Vorteil
faellt mit der Wurzel - die **Gebuehr je Trade bleibt konstant**. Irgendwo
schneiden sich die beiden Linien, und ab dort kostet jeder zusaetzliche Trade
mehr, als er an Huerde spart.

Was hier gerechnet wird
-----------------------
Zu jeder Trade-Zahl gehoert ein noetiger Sharpe je Trade (``suchbudget``). Der
laesst sich in eine **Bruttobewegung** je Trade uebersetzen, sobald man weiss,
wie stark ein Trade dieser Laenge streut - und diese Streuung wird gemessen,
nicht angenommen: aus den echten Kerzen, ueber die tatsaechliche Haltedauer.

Dagegen steht die Gebuehr: 0,04 % vom Nominalwert je Roundtrip, beide Seiten
Limit. Sie haengt nicht daran, wie lange man haelt.

Die Frage lautet damit: **Bei welcher Trade-Zahl uebersteigt der noetige
Bruttovorteil das, was die Bewegung ueber diese Haltedauer ueberhaupt
hergibt?**

Was das nicht ist
-----------------
Keine Aussage darueber, ob auf Fuenfzehnminutenkerzen ein Vorteil existiert -
das misst ``cli scan``, und die Antwort war bisher nein. Hier wird nur
gerechnet, wie gross er sein **muesste**. Ein Weg, der arithmetisch nicht
traegt, braucht gar nicht erst gesucht zu werden; einer, der traegt, ist
deshalb noch lange nicht da.

Kostet keinen Versuch: Es wird kein Kandidat geprueft, sondern eine Huerde
umgerechnet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.suchbudget import noetiger_sharpe

#: Gebuehr je Roundtrip in Prozent vom Nominalwert - beide Seiten Limit.
#: Dieselbe Zahl wie in ``research/vorteilsscan.py``; sie steht dort seit
#: jeher und ist die Groesse, an der sich alles Kurzfristige entscheidet.
KOSTEN_PCT = 0.04


@dataclass(frozen=True, slots=True)
class Stufe:
    """Eine Trade-Zahl und was sie an Bruttovorteil verlangt."""

    trades: int
    noetiger_sharpe: float | None
    streuung_pct: float
    """Wie stark ein Trade dieser Haltedauer streut - **gemessen**, in Prozent."""

    @property
    def noetig_brutto_pct(self) -> float | None:
        """Der noetige Vorteil je Trade in Prozent, vor Kosten.

        ``Sharpe je Trade`` ist ein Vielfaches der Streuung. Wer 0,29 Sharpe
        je Trade braucht und dessen Trades um 3 % streuen, braucht 0,87 %
        Bruttobewegung - plus die Gebuehr.
        """
        if self.noetiger_sharpe is None:
            return None
        return self.noetiger_sharpe * self.streuung_pct

    @property
    def noetig_mit_kosten_pct(self) -> float | None:
        wert = self.noetig_brutto_pct
        return None if wert is None else wert + KOSTEN_PCT

    @property
    def kostenanteil(self) -> float | None:
        """Welcher Anteil des noetigen Vorteils allein an die Boerse geht."""
        gesamt = self.noetig_mit_kosten_pct
        if gesamt is None or gesamt <= 0:
            return None
        return KOSTEN_PCT / gesamt

    @property
    def traegt(self) -> bool:
        """Bleibt nach der Gebuehr ueberhaupt noch ein Vorteil zu suchen?

        **Das Kriterium steht vor der Rechnung fest**: Wenn die Gebuehr mehr
        als die Haelfte dessen frisst, was der Trade einbringen muss, ist die
        Suche eine Wette auf die Boerse und nicht auf den Markt.
        """
        anteil = self.kostenanteil
        return anteil is not None and anteil <= 0.5


def streuung_je_trade(frame: pd.DataFrame, *, kerzen: int) -> float:
    """Wie stark eine Bewegung ueber ``kerzen`` Kerzen streut, in Prozent.

    **Gemessen und nicht hochgerechnet.** Die uebliche Abkuerzung waere, die
    Tagesstreuung mit der Wurzel der Zeit zu skalieren - das setzt
    Unabhaengigkeit voraus, und genau die ist bei Kursen nicht gegeben. Wer
    sie annimmt, bekommt fuer kurze Haltedauern zu kleine Zahlen und damit
    eine zu optimistische Rechnung.
    """
    close = frame["close"].to_numpy(dtype=float)
    if len(close) <= kerzen or kerzen < 1:
        return 0.0
    bewegung = close[kerzen:] / close[:-kerzen] - 1.0
    return float(np.std(bewegung) * 100)


@dataclass(slots=True)
class Taktung:
    """Eine Kerzenlaenge, ihre Datenlage und was der DSR dort verlangt."""

    name: str
    kerzen_gesamt: int
    haltedauer: int
    """Haltedauer in Kerzen - bestimmt Streuung **und** moegliche Trade-Zahl."""

    streuung_pct: float
    versuche: int
    stufen: list[Stufe]

    @property
    def hoechstens_trades(self) -> int:
        """Wie viele Trades in die Reihe passen, wenn man durchgehend haelt.

        Eine Obergrenze und keine Erwartung: Sie unterstellt, dass immer eine
        Position offen ist, und ignoriert Aufwaermphase und Sperrzeiten.
        Wer daran scheitert, scheitert erst recht an der Wirklichkeit.
        """
        return self.kerzen_gesamt // max(self.haltedauer, 1)

    @property
    def machbar(self) -> list[Stufe]:
        return [s for s in self.stufen if s.trades <= self.hoechstens_trades]

    @property
    def bestes(self) -> Stufe | None:
        """Die **groesste** tragfaehige Trade-Zahl, die noch hineinpasst.

        **Der erste Anlauf nahm die mit dem kleinsten Kostenanteil** - und das
        ist immer die mit den wenigsten Trades, weil dort der noetige Vorteil
        am groessten ist und die feste Gebuehr am wenigsten ins Gewicht faellt.
        Damit meldete die Rechnung ausgerechnet den Punkt, um den es nicht
        geht: Der ganze Sinn ist zu pruefen, ob **viele** Trades tragen, denn
        dort ist der noetige Vorteil je Trade am kleinsten und die
        Erfolgsaussicht am groessten.
        """
        moeglich = [s for s in self.machbar if s.traegt]
        return max(moeglich, key=lambda s: s.trades) if moeglich else None

    def tabelle(self) -> str:
        zeilen = [
            f"{'Trades':>8} {'noetiger SR':>12} {'brutto %':>10} "
            f"{'mit Kosten %':>13} {'davon Gebuehr':>14}  passt",
            "-" * 72,
        ]
        for s in self.stufen:
            if s.noetiger_sharpe is None:
                zeilen.append(f"{s.trades:>8} {'unerreichbar':>12}")
                continue
            passt = "ja" if s.trades <= self.hoechstens_trades else "nein"
            zeilen.append(
                f"{s.trades:>8} {s.noetiger_sharpe:>12.4f} "
                f"{s.noetig_brutto_pct:>10.4f} {s.noetig_mit_kosten_pct:>13.4f} "
                f"{s.kostenanteil:>13.0%}  {passt}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.stufen:
            return "Keine Stufen gerechnet."
        beste = self.bestes
        kopf = (
            f"{self.name}: {self.kerzen_gesamt} Kerzen, Haltedauer "
            f"{self.haltedauer} Kerzen, gemessene Streuung je Trade "
            f"{self.streuung_pct:.2f} %. Hoechstens {self.hoechstens_trades} "
            f"Trades passen hinein."
        )
        # **Der Vorbehalt gehoert an den Kopf.** ``hoechstens_trades`` gilt
        # fuer *einen* Markt bei durchgehendem Halten. Ein Korb aus zwei
        # Beinen bringt rund das Doppelte mit, und keine Regel haelt
        # durchgehend - die Zahl ist eine Schranke, keine Erwartung.
        kopf += " (ein Markt, durchgehend gehalten - ein Korb bringt mehr mit.)"

        if beste is None:
            passende = self.machbar
            if not passende:
                return f"{kopf}\n\nKeine Stufe passt in die verfuegbare Historie."
            teuerste = min(
                (s for s in passende if s.kostenanteil is not None),
                key=lambda s: s.kostenanteil or 1.0,
                default=None,
            )
            zusatz = (
                f" Selbst an der guenstigsten passenden Stelle "
                f"({teuerste.trades} Trades) gehen {teuerste.kostenanteil:.0%} "
                f"an die Boerse."
                if teuerste is not None
                else ""
            )
            return (
                f"{kopf}\n\n**Die Gebuehr frisst den Vorteil.**{zusatz} Hier "
                f"zu suchen hiesse, auf die Boerse zu wetten statt auf den "
                f"Markt."
            )
        return (
            f"{kopf}\n\n**Arithmetisch tragfaehig bis {beste.trades} Trades.** "
            f"Dort genuegt ein Bruttovorteil von "
            f"{beste.noetig_mit_kosten_pct:.4f} % je Trade, wovon "
            f"{beste.kostenanteil:.0%} Gebuehr sind. Das heisst nicht, dass "
            f"dieser Vorteil existiert - nur, dass die Rechnung ihn nicht von "
            f"vornherein ausschliesst. Ob er da ist, misst `cli scan`."
        )


def rechne(
    frame: pd.DataFrame,
    *,
    name: str,
    haltedauer: int,
    versuche: int,
    trade_zahlen: tuple[int, ...] = (150, 500, 1000, 2000, 5000, 10000),
) -> Taktung:
    """Die Huerde in Bruttobewegung je Trade umrechnen - fuer eine Kerzenlaenge.

    **``trade_zahlen`` sind unabhaengige Beobachtungen, nicht rohe Trades.**
    Die Formel setzt Unabhaengigkeit voraus, und diese Rechnung gibt ihr die
    Zahlen ungeprueft.

    Wie teuer das ist, steht seit Befund 143 fest, und zwar **guenstiger als
    hier zuvor behauptet**. An dieser Stelle stand, bei kuerzeren Kerzen liege
    die Abhaengigkeit "eher groesser als kleiner" und ein Lauf auf
    Fuenfzehnminutenkerzen existiere noch nicht. Beides war falsch: Die Kerzen
    liegen seit jeher im Speicher, und gemessen bleibt von 1985 rohen Trades
    eine effektive Stichprobe von 1831 - **Quote 0,92 gegen 0,74 auf
    Tageskerzen**.

    Der Grund: Die Zeitskala der Abhaengigkeit haengt an der Handelsdichte,
    nicht an der Kerzenlaenge. Wer selten handelt, traegt sie ueber Monate;
    wer oft handelt, ueber Stunden - und dort bleibt bei vielen Trades
    entsprechend mehr uebrig.

    Ueber alle vierzehn Genome der Generationen 6 und 7 liegt die Quote
    zwischen 0,699 und 0,992, **Median 0,903**; nur eines liegt unter der
    Tageskerzen-Quote von 0,737.

    Die Zahlen dieser Tabelle sind damit **weiterhin Untergrenzen**, aber der
    Abschlag ist klein: Wer hier 2000 Trades liest, darf mit rund 1800
    unabhaengigen Beobachtungen rechnen.

    **Was die Tabelle weiter nicht zeigt:** Die Latte steigt mit der
    Stichprobe (Befund 141). Bei rund 2800 unabhaengigen Beobachtungen
    verlangt sie eine Guete von 4,18 - je Trade sind das 0,079, dreimal
    weniger als auf Tageskerzen, aber gegen Gebuehren, die je Trade gleich
    bleiben. Genau diese Kreuzung rechnet ``noetig_mit_kosten_pct``.
    """
    streuung = streuung_je_trade(frame, kerzen=haltedauer)
    stufen = [
        Stufe(
            trades=n,
            noetiger_sharpe=noetiger_sharpe(effektiv=n, trials=versuche),
            streuung_pct=streuung,
        )
        for n in trade_zahlen
    ]
    return Taktung(
        name=name,
        kerzen_gesamt=len(frame),
        haltedauer=haltedauer,
        streuung_pct=streuung,
        versuche=versuche,
        stufen=stufen,
    )
