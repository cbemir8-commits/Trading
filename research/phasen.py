"""Traegt eine Regel dort, wo der Bestand nicht traegt?

Die Frage, die aus Befund 84 offen blieb
----------------------------------------
Dort wurde gemessen: Je aehnlicher eine Regel dem Trendfolge-Signal des
Bestands, desto besser ihre Qualitaet (r = +0,480). Und dazu stand ein
Vorbehalt: Das koennte eine Eigenschaft des **Zeitraums** sein statt der
Regeln, weil der Markt ueber diese Jahre stark gestiegen ist.

Im selben Befund stand auch, ein Zeitraum mit anderer Marktrichtung wuerde es
entscheiden, "den gibt es in diesen Daten nicht". **Das war falsch.** Die
Jahresrenditen von BTC in den Daten:

    2018  -73,4 %      2022  -64,2 %
    2019  +94,1 %      2023 +155,7 %
    2020 +304,5 %      2024 +121,0 %
    2021  +59,4 %      2025   -6,3 %
                       2026  -26,5 %

Vier fallende Jahre von neun. Die Frage ist also entscheidbar, und ich haette
nachsehen muessen, statt sie fuer unentscheidbar zu erklaeren.

Was die Trennung ergibt
-----------------------
Ueber 22 Regeln, Trades nach dem Jahr des Ausstiegs getrennt:

    rho <-> Sharpe in Aufwaertsjahren   +0,404   (t = 1,93)
    rho <-> Sharpe in Abwaertsjahren    +0,075   (t = 0,33)

Der Zusammenhang **faellt auf ein Fuenftel und ist im Abwaertsmarkt nicht
mehr nachweisbar** - er kehrt sich aber auch nicht um. Das spricht eher fuer
die Zeitraum-Deutung als fuer die Regel-Deutung, entscheidet es bei 22
Punkten aber nicht.

Warum die bisherige Partnersuche daran vorbeisieht
--------------------------------------------------
Das ist gemessen, nicht vermutet. Ueber dieselben Regeln korreliert die
Fensterkorrelation rho mit dem Phasenunterschied zu

    rho <-> (Sharpe auf - Sharpe ab)   +0,097   (t = 0,43)

also praktisch mit null. Die Fensterkorrelation misst, ob zwei Regeln
**gleichzeitig** verdienen; sie sagt nichts darueber, ob die eine gerade dann
verdient, wenn die andere verliert. Zwei Regeln koennen bei rho = 0 beide in
denselben Jahren schwach sein. Wer nach kleinem rho siebt - und das tut die
Partnersuche seit Befund 73 -, siebt an dieser Eigenschaft vorbei.

Der Fehler in der ersten eigenen Messung
----------------------------------------
Der erste Durchlauf sah 14 Regeln und fand **eine** gegenlaeufige. Er kam zu
diesen 14, indem er den Katalog nach Namen filterte: Trend, Momentum,
Donchian. Damit waren genau die Regeln ausgeschlossen, die die Frage
beantworten - die short-faehigen. Ueber den vollen Katalog sind es **sechs
von 22**, und alle sechs sind short oder beidseitig.

Eine Auswahl nach Namen ist eine Auswahl. Dass sie hier ausgerechnet die
Antwort weggeschnitten hat, ist der zweite Fall in diesem Projekt, in dem
eine Vorfilterung das Ergebnis erzeugt hat statt es zu finden.

Was die sechs kosten
--------------------
Sie verdienen im Abwaertsmarkt - und bezahlen dafuer im Aufwaertsmarkt. Ueber
alle Trades gerechnet bleibt von den sechs nur eine mit brauchbarer
Qualitaet:

    Regel                          SR auf    SR ab   insgesamt
    VWAP-Rueckkehr short          -0,2261  +0,3188    -0,1230
    Luecke wird geschlossen       -0,1820  +0,2593    -0,0434
    Bollinger-Ruecksetzer short   -0,2452  +0,2062    +0,0432
    Abfolge-Modell short          -0,0915  +0,3332    +0,0796
    Grosse Kerze m. Volumen short -0,1561  +0,3685    +0,1216
    Trend beide Richtungen        +0,1794  +0,3430    +0,2335

Die Verbund-Guete rechnet ueber die **ganze** Stichprobe. Eine Regel, die nur
in einer Phase verdient, zieht den Schnitt genau so weit herunter, wie sie
ihn in der anderen hebt. Die staerkste Gegenlaeufigkeit (VWAP-Rueckkehr
short, Unterschied 0,54) ist zugleich die schlechteste Regel des Feldes.

Was das nicht ist
-----------------
Kein Freibrief. Die Auswahl erfolgt **nach** dem Blick auf 22 Ergebnisse -
wer eine davon als Verbund-Partner prueft, hat eine Auswahl ueber 22
Hypothesen getroffen und muss sie zaehlen.

Und die Trade-Zahlen je Phase sind klein. Von den 106 Trades von 'Trend beide
Richtungen' fallen 35 in die Abwaertsjahre - das Messrauschen dort betraegt
0,17, und der Unterschied von 0,16 zwischen den Phasen liegt **darunter**.
Bei 'VWAP-Rueckkehr short' liegt er mit 0,54 darueber, aber dort ist die
Gegenlaeufigkeit ohnehin nur die andere Seite einer verlierenden Regel.

Was offen bleibt
----------------
Ob ein Verbund aus zwei phasenkomplementaeren Beinen mehr ist als der
gewichtete Schnitt ihrer Sharpes. ``verbund_guete`` nimmt genau das an - die
Unabhaengigkeit verkleinert dort nur die effektive Stichprobe, sie senkt
nicht die Streuung. Bei wirklich gegenlaeufigen Beinen tut sie das aber. Ob
das Modell damit den Wert eines solchen Partners **unterschaetzt**, ist
messbar und nicht gemessen.

Kostet keinen Versuch: Zerlegt werden Trades, die schon gerechnet sind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Jahre mit negativer BTC-Jahresrendite im Datenzeitraum. Aus den Kursdaten
#: abgelesen, nicht gewaehlt - wer sie aendert, aendert eine Messung.
ABWAERTSJAHRE: frozenset[int] = frozenset({2018, 2022, 2025, 2026})

#: Unter so vielen Regeln traegt keine Korrelation ueber Phasen hinweg.
MINDESTFELD = 6


@dataclass(frozen=True, slots=True)
class Phasenbild:
    """Eine Regel, getrennt nach Marktrichtung."""

    name: str
    sharpe_auf: float
    sharpe_ab: float
    trades_auf: int
    trades_ab: int
    rho: float | None = None

    @property
    def trades(self) -> int:
        return self.trades_auf + self.trades_ab

    @property
    def unterschied(self) -> float:
        return self.sharpe_auf - self.sharpe_ab

    @property
    def gesamt_sharpe(self) -> float:
        """Qualitaet ueber alle Trades - die Groesse, die der Verbund braucht.

        Ohne sie sieht jede gegenlaeufige Regel wie ein Fund aus. Fuenf der
        sechs gefundenen verdienen im Abwaertsmarkt und verlieren im
        Aufwaertsmarkt mehr, als sie dort gewinnen; die Verbund-Guete rechnet
        aber ueber die ganze Stichprobe und sieht nur den Schnitt.
        """
        if self.trades == 0:
            return 0.0
        return (
            self.sharpe_auf * self.trades_auf + self.sharpe_ab * self.trades_ab
        ) / self.trades

    @property
    def traegt_gegenlaeufig(self) -> bool:
        """Ist die Regel im Abwaertsmarkt **besser** als im Aufwaertsmarkt?

        Das ist die Eigenschaft, die ein Verbund-Partner braucht und die die
        Fensterkorrelation nicht misst: Sie sagt, ob zwei Regeln gleichzeitig
        verdienen - nicht, ob die eine traegt, wenn die andere verliert.
        """
        return self.sharpe_ab > self.sharpe_auf

    @property
    def rauschen_ab(self) -> float:
        """Messrauschen des Sharpe in der Abwaertsphase."""
        from research.aussagekraft import messrauschen

        return messrauschen(self.trades_ab)

    @property
    def unterschied_traegt(self) -> bool:
        """Liegt der Phasenunterschied ueber dem Messrauschen?

        Bei 35 Trades in der Abwaertsphase betraegt es 0,17 - ein Unterschied
        darunter ist keine Aussage, sondern eine Ablesung.
        """
        return abs(self.unterschied) > self.rauschen_ab


@dataclass(slots=True)
class Phasenvergleich:
    """Alle Regeln nach Marktrichtung getrennt - und was daraus folgt."""

    bilder: list[Phasenbild] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return len(self.bilder) >= MINDESTFELD

    def _mit_rho(self) -> list[Phasenbild]:
        return [b for b in self.bilder if b.rho is not None]

    def _korrelation(self, werte: list[float]) -> float | None:
        mit = self._mit_rho()
        if len(mit) < MINDESTFELD:
            return None
        rho = np.array([abs(b.rho) for b in mit])
        andere = np.array(werte)
        if rho.std() == 0 or andere.std() == 0:
            return None
        return float(np.corrcoef(rho, andere)[0, 1])

    @property
    def aehnlichkeit_aufwaerts(self) -> float | None:
        return self._korrelation([b.sharpe_auf for b in self._mit_rho()])

    @property
    def aehnlichkeit_abwaerts(self) -> float | None:
        return self._korrelation([b.sharpe_ab for b in self._mit_rho()])

    @property
    def kopplung_sagt_die_phase(self) -> float | None:
        """Sagt die Fensterkorrelation etwas ueber den Phasenunterschied?

        Das ist die tragende Messung dieses Moduls. Die Partnersuche siebt
        seit Befund 73 nach kleinem rho. Wenn rho mit dem Phasenunterschied
        korrelierte, faende sie gegenlaeufige Regeln nebenbei mit - wenn
        nicht, sucht sie an dieser Eigenschaft systematisch vorbei.

        Gemessen: +0,097 ueber 21 Regeln. Praktisch null.
        """
        return self._korrelation([b.unterschied for b in self._mit_rho()])

    @property
    def gegenlaeufige(self) -> list[Phasenbild]:
        """Regeln, die im Abwaertsmarkt besser sind - beste Qualitaet zuerst.

        Sortiert nach Gesamtqualitaet und nicht nach Gegenlaeufigkeit: Die am
        staerksten gegenlaeufige Regel ist in diesen Daten die schlechteste
        ueberhaupt, und wer die Liste von oben liest, soll die brauchbare
        zuerst sehen.
        """
        return sorted(
            (b for b in self.bilder if b.traegt_gegenlaeufig),
            key=lambda b: b.gesamt_sharpe,
            reverse=True,
        )

    def tabelle(self) -> str:
        zeilen = [
            f"{'Regel':<34} {'rho':>7} {'SR auf':>8} {'SR ab':>8} "
            f"{'Diff':>8} {'gesamt':>8}",
            "-" * 77,
        ]
        for b in sorted(self.bilder, key=lambda x: x.unterschied):
            zeilen.append(
                f"{b.name[:34]:<34} "
                f"{b.rho if b.rho is not None else float('nan'):>+7.3f} "
                f"{b.sharpe_auf:>8.4f} {b.sharpe_ab:>8.4f} "
                f"{b.unterschied:>+8.4f} {b.gesamt_sharpe:>+8.4f}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return "Zu wenige Regeln - ueber die Marktphasen laesst sich nichts sagen."

        auf, ab = self.aehnlichkeit_aufwaerts, self.aehnlichkeit_abwaerts
        teil = ""
        if auf is not None and ab is not None:
            richtung = (
                "faellt und ist im Abwaertsmarkt nicht mehr nachweisbar"
                if abs(ab) < abs(auf) / 1.5
                else "haelt in beiden Phasen"
            )
            teil = (
                f"Die Kopplung aus Befund 84 - Aehnlichkeit zum Bestand gegen "
                f"Qualitaet - {richtung}: {auf:+.3f} aufwaerts gegen "
                f"{ab:+.3f} abwaerts. Das spricht eher fuer die "
                f"Zeitraum-Deutung als fuer die Regel-Deutung, entscheidet es "
                f"bei {len(self._mit_rho())} Punkten aber nicht.\n\n"
            )

        blind = self.kopplung_sagt_die_phase
        schluss = ""
        if blind is not None:
            schluss = (
                f"\n\nUnd die bisherige Partnersuche kann das nicht finden: Die "
                f"Fensterkorrelation sagt ueber den Phasenunterschied nichts "
                f"({blind:+.3f} ueber {len(self._mit_rho())} Regeln). Sie misst, "
                f"ob zwei Regeln **gleichzeitig** verdienen - nicht, ob die eine "
                f"traegt, wenn die andere verliert. Wer nach kleinem rho siebt, "
                f"siebt an dieser Eigenschaft vorbei."
            )

        gegen = self.gegenlaeufige
        if not gegen:
            return (
                f"{teil}**Keine einzige Regel traegt im Abwaertsmarkt besser "
                f"als im Aufwaertsmarkt.** Damit fehlt allen dieselbe "
                f"Eigenschaft, und ein Verbund kann sie nicht herstellen."
                f"{schluss}"
            )

        beste = gegen[0]
        staerkste = min(gegen, key=lambda b: b.unterschied)
        preis = ""
        if staerkste is not beste:
            preis = (
                f" Die **staerkste** Gegenlaeufigkeit hat dagegen "
                f"'{staerkste.name}' mit {staerkste.unterschied:+.4f} - und "
                f"insgesamt nur {staerkste.gesamt_sharpe:+.4f}. Gegenlaeufig "
                f"ist dort bloss die andere Seite einer verlierenden Regel."
            )
        belastbar = (
            ""
            if beste.unterschied_traegt
            else (
                f" Ihr Phasenunterschied liegt allerdings **unter** dem "
                f"Messrauschen von {beste.rauschen_ab:.2f} bei "
                f"{beste.trades_ab} Trades in der Abwaertsphase - eine "
                f"Ablesung, keine Aussage."
            )
        )
        return (
            f"{teil}**{len(gegen)} von {len(self.bilder)} Regeln tragen im "
            f"Abwaertsmarkt besser.** Die beste davon ueber alle Trades ist "
            f"'{beste.name}': {beste.sharpe_ab:.4f} abwaerts gegen "
            f"{beste.sharpe_auf:.4f} aufwaerts, insgesamt "
            f"{beste.gesamt_sharpe:+.4f}.{belastbar}{preis}"
            f"{schluss}"
        )
