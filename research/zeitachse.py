"""Kuerzt das Gate genug - oder nur dort, wo es ohnehin nicht wehtut?

Woher die Frage kommt
---------------------
Befund 86 hat gemessen, dass die Trade-Achse systematisch zu optimistisch ist.
Das betraf dort Verbuende. Es betrifft aber genauso einzelne Kandidaten - und
**das Zulassungs-Gate rechnet auf der Trade-Achse.**

Das Gate kuerzt die Stichprobe schon: ``effektive_stichprobe`` misst die
Korrelation zwischen Walk-Forward-Fenstern und fasst gleichzeitig offene
Positionen zusammen. Die Frage ist, ob das reicht.

Was gemessen wurde
------------------
Ueber den **entdoppelten** Katalog - 15 Regeln, davon 12 mit positivem t-Wert
und damit beurteilbar - je drei t-Werte fuer dieselbe Regel:

    mittlere Luecke zwischen Zeit- und Gate-Kuerzung   11,7 %
    davon deckt die Blockkuerzung ab                     32 %

Die erste Fassung dieses Moduls rechnete ueber 21 Genome und kam auf 20,2 %
Luecke bei 15 % Deckung. Sechs dieser Genome liefern identische Trades; die
siebenfach gezaehlte Regel ist ausgerechnet die mit 37 % Zeit-Luecke und ohne
jede Gate-Kuerzung. Sie hat den Befund nicht verstaerkt, sondern erzeugt.
Siehe ``research/entdopplung.py``.

Warum die Wochenachse der ehrlichere Massstab ist
-------------------------------------------------
``SR/Trade * sqrt(n)`` und ``SR/Woche * sqrt(Wochen)`` sind derselbe t-Wert,
solange die Trades zeitlich unabhaengig liegen (Befund 86). Weichen sie ab,
liegt es an der Zeitstruktur - und die Wochenachse sieht sie, die Trade-Achse
nicht.

Dass es wirklich Zeitstruktur ist und kein Rechenartefakt, sagt die Nullprobe:
Dieselben Trade-Ergebnisse zufaellig ueber dieselben Wochen verteilt. Dabei
bleibt die Zahl der Trades gleich, ihre Werte bleiben gleich, nur **wann** sie
anfallen wird zerwuerfelt.

    Regel                         t Woche   Nullprobe   Anteil
    Trend 50 Tage m. Konfluenz      3,102       3,164   -0,062
    Trend-Beteiligung (fair ger.)   1,776       2,241   -0,465
    Trend beide Richtungen          1,756       2,201   -0,445
    Trend-Beteiligung 100 Tage      2,108       2,299   -0,191

Die Nullprobe landet jeweils dicht an der Trade-Achse - genau wie es sein
muss. Der echte Wert liegt darunter.

Woran das liegt, ist praeziser als "die Trades klumpen": Klumpung allein
kostet **nichts**. Drei unabhaengige Trades in derselben Woche aufsummiert
ergeben einen Wert mit dreifachem Mittel und wurzel-dreifacher Streuung - der
t-Wert bleibt erhalten. Das ist an gebauten Trades nachgeprueft und war der
Punkt, an dem der erste Testentwurf zu Recht scheiterte.

Es kostet erst, wenn die Trades **innerhalb** eines Klumpens gemeinsam
gewinnen oder verlieren. Genau das misst die Wochenachse: nicht Haeufung,
sondern Haeufung plus Gleichlauf.

Wo das wehtut
-------------
Am staerksten trifft es die Regeln mit **wenigen, guten** Trades - also genau
die Hoffnungstraeger der Verbundsuche aus Befund 73. Fuenf von zwoelf
beurteilbaren Regeln liegen ueber der Schwelle:

    'Trend-Beteiligung (fair gerechnet)': 53 Trades, nach Zeitachse noch 33.
    Das Gate kuerzt dort **null**.

In Befund 73 stand, der Verbund aus Spitze und dieser Regel hebe die Guete auf
3,368 und den Deflated Sharpe auf 0,8602 - "der groesste Sprung, den in diesem
Projekt je etwas gebracht hat". Diese Zahl beruht fuer dieses Bein auf einer
Achse, die es um ein Fuenftel zu gut bewertet.

**Und sie ist inzwischen aus einem zweiten Grund ueberholt** (Befund 140):
Die Einteilung kannte die Quartale nicht. Richtig gerechnet steht der Verbund
bei Guete 3,073 und DSR 0,6893 - siehe den Kopf von ``research/verbund.py``.
Beide Korrekturen zeigen in dieselbe Richtung.

Der Bestand selbst ist kaum betroffen: 154 Trades, nach Zeitachse 148, das
sind vier Prozent. Sein t-Wert faellt von 3,216 auf 3,102 - noetig sind 3,629,
der Abstand waechst also von 0,41 auf 0,53.

Was das ist und was nicht
-------------------------
Das ist **keine Lockerung und kein neues Gate**. Es ist eine Messung, die
zeigt, dass eine vorhandene Kuerzung weniger tut als gedacht - und in welche
Richtung der Fehler zeigt: zugunsten des Kandidaten. Wer daraus ein Gate
machen will, muss zuerst pruefen, ob die Wochenlaenge der richtige Massstab
ist; hier steht nur, dass Trade- und Zeitachse auseinanderlaufen und um
wieviel.

Bei Kandidaten mit negativem t-Wert dreht sich das Vorzeichen der Deutung um -
dort ist ein kleinerer Betrag eine Verbesserung. Die Aussagen dieses Moduls
beschraenken sich deshalb auf Kandidaten, deren Nullprobe positiv ausfaellt.

Kostet keinen Versuch: Neu aggregiert werden Trades, die schon gerechnet sind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Unter so vielen Regeln traegt keine Aussage ueber die Kuerzung.
MINDESTREGELN = 6

#: Ab diesem Anteil gilt eine Luecke zwischen Gate und Zeitachse als gross
#: genug, um am Ergebnis etwas zu aendern. Zehn Prozent der Stichprobe
#: verschieben den t-Wert um rund fuenf Prozent.
SPUERBAR = 0.10


@dataclass(frozen=True, slots=True)
class Zeitbild:
    """Eine Regel auf drei Achsen - und was die Nullprobe dazu sagt."""

    name: str
    trades: int
    t_roh: float
    """SR/Trade mal Wurzel aus allen Trades."""
    t_gate: float
    """Dasselbe nach der Kuerzung, die das Zulassungs-Gate rechnet."""
    t_woche: float
    """Der t-Wert der Wochenreihe - die Achse, die Gleichzeitigkeit sieht."""
    t_null: float
    """Derselbe Wert, wenn dieselben Trades zufaellig ueber die Wochen
    verteilt werden. Muss dicht an ``t_roh`` liegen; tut er das nicht, misst
    der Vergleich die Aggregation und nicht die Zeitstruktur."""

    @property
    def beurteilbar(self) -> bool:
        """Nur bei positiver Nullprobe ist die Richtung eindeutig.

        Bei einer verlierenden Regel ist ein kleinerer Betrag eine
        Verbesserung, und "zu optimistisch" hiesse dort das Gegenteil.
        """
        return self.t_null > 0

    @property
    def kuerzung_gate(self) -> float:
        """Welchen Anteil der Stichprobe die Gate-Kuerzung wegnimmt."""
        if self.t_roh == 0:
            return 0.0
        return max(0.0, 1.0 - (self.t_gate / self.t_roh) ** 2)

    @property
    def kuerzung_zeit(self) -> float:
        """Welchen Anteil die Zeitachse wegnehmen wuerde.

        Ueber ``t = SR * sqrt(n)`` entspricht ein Verhaeltnis der t-Werte dem
        Quadrat davon in der Stichprobe - deshalb laesst sich die Zeitstruktur
        ueberhaupt mit der Blockkuerzung vergleichen.
        """
        if self.t_null == 0:
            return 0.0
        return max(0.0, 1.0 - (self.t_woche / self.t_null) ** 2)

    @property
    def luecke(self) -> float:
        """Was die Zeitachse verlangt und das Gate nicht liefert."""
        return self.kuerzung_zeit - self.kuerzung_gate

    @property
    def effektiv_nach_zeit(self) -> int:
        return round(self.trades * (1.0 - self.kuerzung_zeit))

    @property
    def nullprobe_traegt(self) -> bool:
        """Landet die Nullprobe dort, wo die Trade-Achse steht?

        Die Kontrolle je Regel. Weicht sie ab, ist der Vergleich fuer diese
        Regel wertlos - dann misst er die Aggregation.
        """
        if self.t_roh == 0:
            return False
        return abs(self.t_null - self.t_roh) < 0.25 * abs(self.t_roh)


@dataclass(slots=True)
class Zeitpruefung:
    """Alle Regeln auf beiden Achsen - und ob die Kuerzung mithaelt."""

    bilder: list[Zeitbild] = field(default_factory=list)

    @property
    def genug(self) -> bool:
        return len(self.beurteilbare) >= MINDESTREGELN

    @property
    def beurteilbare(self) -> list[Zeitbild]:
        return [b for b in self.bilder if b.beurteilbar]

    @property
    def nullprobe_traegt(self) -> bool:
        """Die Kontrolle ueber alle Regeln zugleich."""
        pruefbar = self.beurteilbare
        return bool(pruefbar) and all(b.nullprobe_traegt for b in pruefbar)

    @property
    def mittlere_luecke(self) -> float | None:
        pruefbar = self.beurteilbare
        if not pruefbar:
            return None
        return float(np.mean([b.luecke for b in pruefbar]))

    @property
    def deckung(self) -> float | None:
        """Welchen Anteil der noetigen Kuerzung das Gate tatsaechlich leistet.

        Gemessen 0,05: Von dem, was die Zeitachse verlangt, holt die
        Blockkuerzung ein Zwanzigstel.
        """
        pruefbar = self.beurteilbare
        if not pruefbar:
            return None
        noetig = float(np.sum([b.kuerzung_zeit for b in pruefbar]))
        if noetig <= 0:
            return None
        return float(np.sum([b.kuerzung_gate for b in pruefbar])) / noetig

    @property
    def kuerzt_an_der_richtigen_stelle(self) -> float | None:
        """Kuerzt das Gate dort, wo die Zeitachse es verlangt?

        Die schaerfere Frage hinter "kuerzt zu wenig". Waeren beide Groessen
        positiv gekoppelt, waere die Blockkuerzung bloss zu schwach kalibriert
        und liesse sich hochskalieren. Sind sie es nicht, misst sie etwas
        anderes.

        Auf dem entdoppelten Katalog -0,261 ueber 12 Regeln. Das ist ein
        t-Wert von -0,86 und damit **nicht nachweisbar** - siehe
        ``stelle_ist_belegt``. Der erste Anlauf mass -0,470 und schloss
        daraus, das Gate kuerze gegenlaeufig; die Zahl kam aber daher, dass
        eine Regel siebenfach im Katalog stand.
        """
        pruefbar = self.beurteilbare
        if len(pruefbar) < MINDESTREGELN:
            return None
        gate = np.array([b.kuerzung_gate for b in pruefbar])
        zeit = np.array([b.kuerzung_zeit for b in pruefbar])
        if gate.std() == 0 or zeit.std() == 0:
            return None
        return float(np.corrcoef(gate, zeit)[0, 1])

    @property
    def stelle_ist_belegt(self) -> bool:
        """Traegt die Stellenfrage einen Schluss - oder ist sie Rauschen?

        Dieselbe Schranke wie in ``partnerkarte.urteil`` seit Befund 75:
        unter |t| = 2 wird nichts geschlossen. Dort war es eine Korrelation
        aus fuenf Punkten, hier eine aus zwoelf - und beide Male sah die Zahl
        nach einer Aussage aus.
        """
        r = self.kuerzt_an_der_richtigen_stelle
        n = len(self.beurteilbare)
        if r is None or n < 4:
            return False
        # Ein perfekter Zusammenhang ist der staerkste Beleg, nicht der
        # schwaechste - die Abfrage steht hier nur, weil der t-Wert bei
        # |r| = 1 durch null teilt.
        if abs(r) >= 1.0:
            return True
        return abs(r * ((n - 2) / (1 - r * r)) ** 0.5) >= 2.0

    @property
    def spuerbar_betroffene(self) -> list[Zeitbild]:
        """Regeln mit grosser Luecke - die groesste zuerst."""
        return sorted(
            (b for b in self.beurteilbare if b.luecke > SPUERBAR),
            key=lambda b: -b.luecke,
        )

    @property
    def gate_kuerzt_genug(self) -> bool:
        """Bleibt die mittlere Luecke unter der Schwelle?

        Die Toleranz ist kein Spielraum, sondern Fliesskomma: Ein Wert, der
        rechnerisch genau auf ``SPUERBAR`` liegt, faellt sonst je nach
        Rundung auf die eine oder andere Seite.
        """
        luecke = self.mittlere_luecke
        return luecke is not None and luecke <= SPUERBAR + 1e-9

    def tabelle(self) -> str:
        zeilen = [
            f"{'Regel':<30} {'n':>5} {'t roh':>7} {'Gate':>6} {'Zeit':>6} "
            f"{'Luecke':>7}",
            "-" * 65,
        ]
        for b in sorted(self.bilder, key=lambda x: -x.luecke):
            # Verlierende Regeln stehen mit in der Tabelle, aber gezeichnet:
            # Bei negativem t-Wert ist ein kleinerer Betrag eine Verbesserung,
            # und "Luecke" bedeutet dort das Gegenteil.
            marke = " " if b.beurteilbar else "*"
            zeilen.append(
                f"{marke}{b.name[:29]:<29} {b.trades:>5} {b.t_roh:>7.3f} "
                f"{b.kuerzung_gate:>6.1%} {b.kuerzung_zeit:>6.1%} "
                f"{b.luecke:>+7.1%}"
            )
        if any(not b.beurteilbar for b in self.bilder):
            zeilen.append(
                "* verlierende Regel - dort ist die Richtung umgekehrt zu lesen "
                "und sie zaehlt nicht mit."
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.genug:
            return "Zu wenige Regeln - ueber die Kuerzung laesst sich nichts sagen."
        if not self.nullprobe_traegt:
            daneben = [b.name for b in self.beurteilbare if not b.nullprobe_traegt]
            return (
                f"**Die Kontrolle faellt durch.** Bei {len(daneben)} Regeln "
                f"landet die Nullprobe nicht dort, wo die Trade-Achse steht "
                f"(zuerst '{daneben[0]}'). Damit misst der Vergleich die "
                f"Aggregation und nicht die Zeitstruktur - hier ist nichts zu "
                f"schliessen."
            )

        luecke, deckung = self.mittlere_luecke, self.deckung
        pruefbar = self.beurteilbare
        stelle = self.kuerzt_an_der_richtigen_stelle
        if self.gate_kuerzt_genug:
            teil = (
                f"**Die Kuerzung des Gates haelt im Schnitt mit.** Ueber "
                f"{len(pruefbar)} Regeln bleibt eine mittlere Luecke von "
                f"{luecke:.1%} - unter der Schwelle, ab der sich am Ergebnis "
                f"etwas aendert."
            )
            # Ein Mittelwert kann stimmen, waehrend jede einzelne Zeile
            # danebenliegt - der gefaehrlichere Fall, weil er wie Ordnung
            # aussieht. Deshalb steht die Stellenfrage auch hier.
            if stelle is not None and stelle < 0.2 and self.stelle_ist_belegt:
                teil += (
                    f"\n\n**Im Schnitt heisst aber nicht an der richtigen "
                    f"Stelle.** Was das Gate kuerzt, haengt mit dem, was die "
                    f"Zeitachse verlangt, nur zu {stelle:+.3f} zusammen. Der "
                    f"Mittelwert stimmt, die einzelnen Zeilen nicht."
                )
            betroffen = self.spuerbar_betroffene
            if betroffen:
                teil += (
                    f" Bei {len(betroffen)} von {len(pruefbar)} Regeln bleibt "
                    f"trotzdem eine Luecke ueber {SPUERBAR:.0%}, am groessten "
                    f"'{betroffen[0].name}' mit {betroffen[0].luecke:.1%}."
                )
            return teil

        teil = (
            f"**Das Gate kuerzt zu wenig.** Ueber {len(pruefbar)} Regeln "
            f"verlangt die Zeitachse im Schnitt {luecke:.1%} mehr Kuerzung, "
            f"als die Blockrechnung leistet"
        )
        if deckung is not None:
            teil += f" - sie deckt {deckung:.0%} des Noetigen ab"
        teil += (
            ".\n\nDas ist keine Lockerung und kein neues Gate, sondern eine "
            "Messung: Eine vorhandene Kuerzung tut weniger als gedacht, und "
            "der Fehler zeigt zugunsten des Kandidaten."
        )

        betroffen = self.spuerbar_betroffene
        if betroffen:
            schlimm = betroffen[0]
            teil += (
                f"\n\n**Es trifft die Regeln mit wenigen, guten Trades** - "
                f"also genau die Verbund-Anwaerter. Am staerksten "
                f"'{schlimm.name}': von {schlimm.trades} Trades blieben nach "
                f"der Zeitachse {schlimm.effektiv_nach_zeit}, das Gate kuerzt "
                f"dort {schlimm.kuerzung_gate:.0%}. Betroffen sind "
                f"{len(betroffen)} von {len(pruefbar)} Regeln."
            )

        if stelle is not None and stelle < 0.2:
            if self.stelle_ist_belegt:
                richtung = (
                    "sogar gegenlaeufig" if stelle < 0 else "praktisch gar nicht"
                )
                teil += (
                    f"\n\n**Und es ist nicht bloss eine Frage der Staerke.** "
                    f"Was das Gate kuerzt, haengt mit dem, was die Zeitachse "
                    f"verlangt, {richtung} zusammen (r = {stelle:+.3f}). Eine "
                    f"zu schwach eingestellte Kuerzung liesse sich "
                    f"hochskalieren; diese nicht - sie misst die Korrelation "
                    f"zwischen Walk-Forward-Fenstern, also Jahresskala, und "
                    f"die Klumpung sitzt auf Wochenskala."
                )
            else:
                teil += (
                    f"\n\n**Ob es an der richtigen Stelle kuerzt, bleibt "
                    f"offen.** Der Zusammenhang zwischen Gate- und "
                    f"Zeit-Kuerzung liegt bei {stelle:+.3f}, ist bei "
                    f"{len(pruefbar)} Regeln aber nicht nachweisbar. Ein "
                    f"frueherer Anlauf hat daraus einen Schluss gezogen - die "
                    f"Zahl kam von einer Regel, die siebenfach im Katalog "
                    f"stand."
                )
        return teil


def messe(
    laeufe: dict[str, list],
    gate_t: dict[str, float],
    *,
    durchlaeufe: int = 600,
    saat: int = 20260817,
    tage: int = 7,
) -> Zeitpruefung:
    """Drei Achsen je Regel, plus Nullprobe.

    ``gate_t`` gibt je Regel den t-Wert nach der Kuerzung an, die das
    Zulassungs-Gate rechnet - er wird uebergeben und nicht hier nachgebaut,
    damit es keine zweite Umsetzung derselben Groesse gibt.
    """
    from research.suchbudget import Kandidat
    from research.verbundmodell import periodenkanten, periodenreihe, t_wert

    alle = [t for trades in laeufe.values() for t in trades]
    kanten = periodenkanten(alle, tage=tage)
    wochen = len(kanten)
    wuerfel = np.random.default_rng(saat)

    bilder: list[Zeitbild] = []
    for name, trades in laeufe.items():
        kandidat = Kandidat.aus_trades(name, trades)
        auf_woche = t_wert(periodenreihe(trades, kanten))
        if kandidat is None or auf_woche is None or wochen < 10:
            continue
        werte = np.array([float(t.net_pnl) for t in trades], dtype=float)
        null = []
        for _ in range(durchlaeufe):
            reihe = np.zeros(wochen)
            np.add.at(reihe, wuerfel.integers(0, wochen, len(werte)), werte)
            gewuerfelt = t_wert(reihe)
            if gewuerfelt is not None:
                null.append(gewuerfelt)
        if not null:
            continue
        bilder.append(
            Zeitbild(
                name=name,
                trades=len(trades),
                t_roh=kandidat.sharpe_je_trade * len(trades) ** 0.5,
                t_gate=gate_t.get(
                    name, kandidat.sharpe_je_trade * len(trades) ** 0.5
                ),
                t_woche=auf_woche,
                t_null=float(np.median(null)),
            )
        )
    return Zeitpruefung(bilder=bilder)


__all__ = [
    "MINDESTREGELN",
    "SPUERBAR",
    "Zeitbild",
    "Zeitpruefung",
    "messe",
]
