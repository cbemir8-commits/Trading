"""Alle Paare aus dem Katalog - **gemessen**, nicht vorhergesagt.

Warum es das neben ``partnerkarte`` gibt
----------------------------------------
``partnerkarte`` sagt *voraus*, was ein Partner koennen muesste - ueber die
Formel aus Befund 74, mit einem angenommenen Unabhaengigkeitsgrad. ``cli
anwaerter`` laesst dafuer jedes Katalog-Genom laufen, behaelt aber nur
Trade-Zahl, Guete und Fensterkorrelation. **Der Verbund selbst wurde nie
gerechnet.**

Er kostet nichts: Die Beine laufen ohnehin, und der Verbund ist die
Vereinigung ihrer Trades. Genau das macht dieses Modul.

Was dabei herauskam (Befund 141)
--------------------------------
Vierzehn entdoppelte Kandidaten gegen den Bestand, Spot, 198 Versuche:

    Partner                        P_n   P_sr    n  halt  Guete  noetig  fehlt
    Trend-Beteiligung (fair)        53  0,318  124  0,60  3,073   3,625  0,552
    Abfolge-Modell short            67  0,083  191  0,86  3,032   3,725  0,692
    Grosse Kerze mit Vol. short     51  0,134  154  0,75  2,888   3,674  0,786
    Abfolge-Modell (Abgriff)        56  0,107  162  0,77  2,895   3,686  0,791
    ...
    Abfolge ohne Strukturbruch     124 -0,047  153  0,55  2,082   3,673  1,591

**Keines der vierzehn erreicht die Latte.** Der kleinste Abstand ist 0,552 -
und das ist der Partner, der seit Befund 73 bekannt ist. Sieben der vierzehn
stehen besser da als der Bestand allein, sieben schlechter.

Drei Dinge, die dabei auffielen
-------------------------------
**1. Die Fensterkorrelation ordnet die Partner nicht.** Rangkorrelation gegen
die gemessene Verbundguete: **+0,04**; gegen die Luecke: -0,10. Also nichts.
Der beste Partner hat rho = +0,56, der zweitbeste -0,41. Die Einzelguete des
Partners traegt als Einziges Signal (-0,53 gegen die Luecke), und auch das
schwach.

**2. Die Behaltequote sagt ebenfalls nichts** (+0,00 gegen die Luecke). Das
korrigiert die Erzaehlung aus Befund 140: Dort war beschrieben, *warum* der
eine gemessene Partner half - er verteilt die Trades ueber mehr Quartale. Ueber
vierzehn Partner hinweg sagt dieser Mechanismus das Ergebnis **nicht** vorher.
Die Erklaerung stimmt fuer den Einzelfall und traegt nicht als Auswahlregel.

**3. Die Latte steigt mit der Stichprobe.** Von 3,591 bei n = 106 auf 3,896
bei n = 412. Der Grund steht in der Formel: Die Schiefe senkt die Huerde ueber
den Nenner ``sqrt(1 - g3*SR + ...)``, und zwar **proportional zum noetigen SR
je Trade**. Wer dieselbe Kante auf mehr Trades verteilt, braucht je Trade
weniger - und verliert damit einen Teil des Schiefe-Bonus:

    n = 106   noetiger SR 0,3488   Nenner 0,501
    n = 412   noetiger SR 0,1919   Nenner 0,692

Deshalb wird hier nach der **Luecke** geordnet und nicht nach der Guete. Eine
hoehere Guete bei groesserem n kann der schlechtere Fund sein, weil sie gegen
eine hoehere Latte antritt - 'Abfolge-Modell short' zeigt genau das.

Was dieses Modul nicht tut
--------------------------
**Es benennt keinen Sieger.** Wer eines von N geprueften Paaren als Kandidaten
uebernimmt, hat eine Auswahl ueber N getroffen und schuldet N Versuche - so
steht es seit Befund 73 im Kopf von ``verbund.py``, und dort hat genau diese
Auswahl schon einmal ein bestandenes Gate vorgetaeuscht. Diese Karte ist eine
Landkarte, keine Auswahl. ``kosten_einer_auswahl`` sagt, was das Uebernehmen
kosten wuerde.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Paar", "Paarfeld"]


@dataclass(frozen=True, slots=True)
class Paar:
    """Ein gemessener Verbund aus Bestand und einem Partner."""

    name: str
    partner_trades: int
    partner_sharpe: float
    roh: int
    effektiv: int
    guete: float
    noetig: float

    schiefe: float | None = None
    woelbung: float | None = None
    """Die Verteilungsform **dieses Verbunds** - fuer seine eigene Latte.

    Bis Befund 193 stand in ``noetig`` die Latte des Bestands. Mit der des
    Paares wechselt die Spitze der Rangfolge (Befund 193), und ``bis``
    unten haengt ebenfalls daran.
    """

    def __post_init__(self) -> None:
        if self.effektiv > self.roh:
            raise ValueError(
                f"{self.name}: {self.effektiv} unabhaengige Beobachtungen aus "
                f"{self.roh} Trades - das geht nicht."
            )

    @property
    def luecke(self) -> float:
        """Was zur Latte fehlt - **das** Mass, nicht die Guete.

        Die Latte haengt an ``n``; zwei Paare mit verschiedenem ``n`` treten
        gegen verschiedene Latten an. Nur die Differenz ist vergleichbar.
        """
        return self.noetig - self.guete

    @property
    def behaltequote(self) -> float:
        """Anteil der rohen Trades, den die Einteilung uebrig laesst."""
        return self.effektiv / self.roh if self.roh else 0.0

    @property
    def reicht(self) -> bool:
        return self.guete >= self.noetig

    def bis(self, *, hoechstens: int | None = None) -> int | None:
        """Bis zu welchem Versuchsstand dieses Paar bestanden haette.

        Die Frage aus Befund 189, auf den Verbundweg angewandt. Sie trennt
        auch hier zwei Lagen: an der Breite der Suche gescheitert - oder an
        sich selbst.

        **Und hier faellt sie anders aus als im Katalog** (Befund 194). Die
        beste Einzelregel raeumt bis 8 Versuche, der Bestand allein bis 21;
        das beste Paar kommt in dieselbe Groessenordnung wie der Zaehler.
        Der Verbundweg ist damit der einzige gemessene, der ueberhaupt in
        die Naehe kam.
        """
        from research.verbund import hoechster_versuchsstand

        zusatz = {} if hoechstens is None else {"hoechstens": hoechstens}
        return hoechster_versuchsstand(
            self.guete,
            self.effektiv,
            schiefe=self.schiefe,
            woelbung=self.woelbung,
            **zusatz,
        )


@dataclass(frozen=True, slots=True)
class Paarfeld:
    """Alle gemessenen Paare zu einem Bestand - und was sie zusammen sagen."""

    bestand: str
    allein_guete: float
    allein_noetig: float
    paare: tuple[Paar, ...]

    @property
    def geordnet(self) -> tuple[Paar, ...]:
        """Nach **Luecke** geordnet, nicht nach Guete - siehe Modulkopf."""
        return tuple(sorted(self.paare, key=lambda p: p.luecke))

    @property
    def erreichen(self) -> tuple[Paar, ...]:
        return tuple(p for p in self.paare if p.reicht)

    @property
    def besser_als_allein(self) -> tuple[Paar, ...]:
        """Paare, deren Luecke kleiner ist als die des Bestands allein."""
        eigene = self.allein_noetig - self.allein_guete
        return tuple(p for p in self.paare if p.luecke < eigene)

    @property
    def kosten_einer_auswahl(self) -> int:
        """Wie viele Versuche es kostet, **eines** dieser Paare zu uebernehmen.

        Nicht eins. Wer aus N geprueften das beste nimmt, hat N Hypothesen
        getestet, und der Deflated Sharpe rechnet mit N.
        """
        return len(self.paare)

    def urteil(self) -> str:
        if not self.paare:
            return "Keine Paare gemessen - kein Urteil."

        beste = self.geordnet[0]
        eigene = self.allein_noetig - self.allein_guete
        teile = [
            f"{len(self.paare)} Paare gemessen, {len(self.erreichen)} ueber der "
            f"Latte."
        ]
        if not self.erreichen:
            teile.append(
                f"Am naechsten kam '{beste.name}': Guete {beste.guete:.3f} "
                f"gegen {beste.noetig:.3f} bei n = {beste.effektiv}, es fehlen "
                f"{beste.luecke:.3f}."
            )
        teile.append(
            f"{len(self.besser_als_allein)} von {len(self.paare)} stehen besser "
            f"da als der Bestand allein (Luecke {eigene:.3f})."
        )
        teile.append(
            f"**Eines davon zu uebernehmen kostet "
            f"{self.kosten_einer_auswahl} Versuche**, nicht einen: Die Auswahl "
            f"lief ueber alle."
        )
        # **Wie frueh haette es gereicht?** (Befund 189, hier auf den
        # Verbundweg angewandt.) Die Antwort faellt anders aus als im
        # Katalog, und das gehoert in dasselbe Urteil - sonst liest sich
        # "0 ueber der Latte" ueberall gleich.
        stand = beste.bis()
        if stand is not None:
            teile.append(
                f"Bis zu einem Versuchsstand von **{stand}** haette dieses "
                f"Paar die Schwelle geraeumt."
            )
        return " ".join(teile)
