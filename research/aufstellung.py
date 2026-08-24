"""Bringen weitere Maerkte Evidenz? - die Nachpruefung von Befund 27.

Die Frage
---------
Befund 132 hat die Luecke zum ersten Mal in Tagen ausgedrueckt: 30 fehlende
unabhaengige Beobachtungen, rund 1,8 Jahre, und sie koennen nur aus der
Zukunft kommen - **weil die Vergangenheit ausgeschoepft ist.** Das galt fuer
die Historie. Fuer die Breite galt es nicht automatisch.

Im Register steht dazu *"Mehr Maerkte - effektive Stichprobe bleibt bei 150"*
(Befund 27), 105 Befunde alt und einer der 28, die Befund 131 als ungeprueft
ausgewiesen hat. Der Anlass zum Nachmessen kam aus Befund 132 selbst: Dort war
die effektive Stichprobe an **jedem** Fenster gleich der rohen Trade-Zahl
(152/152, 103/103, 72/72). Die Korrelationsstrafe biss gar nicht - und genau
auf ihr beruhte Befund 27.

Gemessen
--------
Derselbe Kandidat, Spot-Punkt, 198 Versuche, Tageskerzen. LTC und XRP liegen
im Speicher und reichen weiter zurueck als ETH, der gemeinsame Bereich bleibt
deshalb bei 3277 Tagen: Zusatzmaerkte kosten hier **keine** Historie.

    Aufstellung             Trades   eff    Guete     DSR   Gates
    BTC + ETH (Referenz)       152   152   0,2765  0,8640    9/11
    BTC + ETH + LTC            258   214   0,2225  0,7882    7/11
    BTC + ETH + XRP            260   220   0,2171  0,7758    9/11
    BTC + ETH + LTC + XRP      366   229   0,1928  0,5956    9/11

**Die Stichprobe waechst sehr wohl** - 152 auf 229. Befund 27s Zahl
*"bleibt bei 150"* ist mit dem heutigen Code nicht zu reproduzieren.

**Und trotzdem faellt der Deflated Sharpe** - 0,8640 auf 0,5956. Der Grund ist
die Kopplung aus Befund 54, an einer neuen Stelle: Die Guete faellt schneller,
als ``sqrt(n)`` steigt. Auf der Groesse, auf die es ankommt:

    Aufstellung             Guete x sqrt(eff)
    BTC + ETH                        3,409
    BTC + ETH + LTC                  3,255
    BTC + ETH + XRP                  3,220
    BTC + ETH + LTC + XRP            2,917

Monoton fallend. Jeder zusaetzliche Markt bringt Beobachtungen und nimmt mehr
Qualitaet mit, als er an Wurzel-n zurueckgibt.

Ein Nebenbefund
---------------
Die Korrelationsstrafe **arbeitet** - sie setzt nur spaeter ein, als Befund 27
annahm: Bei zwei Maerkten kuerzt sie nichts (152 von 152), bei vier kuerzt sie
37 % (229 von 366). Das ist kein Fehler, sondern die Bauart aus
``research/unabhaengigkeit.py``: Gekuerzt wird nur bei **nachgewiesener**
Abhaengigkeit, und der Nachweis braucht selbst Beobachtungen.

Was das fuer Befund 132 heisst
------------------------------
Die 30 fehlenden Beobachtungen sind aus der Breite nicht zu holen. Vier
Maerkte liefern 77 zusaetzliche unabhaengige Beobachtungen - mehr als
gebraucht - und stehen am Ende trotzdem 0,2684 schlechter da. Der Schluss aus
Befund 132 haelt, und er haelt jetzt gegen eine gemessene Alternative statt
gegen eine angenommene.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

__all__ = ["Aufstellungsreihe", "Marktsatz"]


@dataclass(frozen=True, slots=True)
class Marktsatz:
    """Eine Aufstellung von Maerkten und was der Kandidat darauf leistet."""

    name: str
    maerkte: int
    tage: int
    trades: int
    effektiv: int
    guete: float
    dsr: float
    bestanden: int
    gesamt: int

    def __post_init__(self) -> None:
        if self.maerkte < 1:
            raise ValueError(f"'{self.name}' ohne Markt ist keine Aufstellung.")
        if self.effektiv > self.trades:
            raise ValueError(
                f"'{self.name}': {self.effektiv} unabhaengige Beobachtungen aus "
                f"{self.trades} Trades - die effektive Stichprobe kann die rohe "
                f"nicht uebersteigen."
            )

    @property
    def evidenz(self) -> float:
        """``Guete x sqrt(effektiv)`` - die Groesse, an der die Zulassung haengt.

        Trades und Qualitaet einzeln anzusehen fuehrt in die Irre: Eine
        Aufstellung kann beide Male schlechter aussehen und trotzdem mehr
        Evidenz tragen, oder umgekehrt. Diese Groesse ist die, die der
        Deflated Sharpe belohnt.
        """
        return self.guete * sqrt(max(self.effektiv, 0))

    @property
    def kuerzung(self) -> float:
        """Wie viel die Abhaengigkeitspruefung von den Trades abzieht (0 bis 1)."""
        return 1.0 - self.effektiv / self.trades if self.trades else 0.0

    def als_zeile(self) -> str:
        return (
            f"{self.name:<24} {self.trades:>6} {self.effektiv:>5} "
            f"{self.guete:>7.4f} {self.dsr:>7.4f} "
            f"{self.bestanden:>3}/{self.gesamt}"
        )


@dataclass(frozen=True, slots=True)
class Aufstellungsreihe:
    """Mehrere Marktaufstellungen, mit der ersten als erklaerter Referenz.

    **Referenz ist der erste Satz, nicht der beste.** Das ist dieselbe Sperre
    wie in ``decke.Fensterlage`` und ``historie.Historienkurve``: Die
    Aufstellung nach den Ergebnissen auszusuchen ist ein gelockertes Gate mit
    anderem Namen. BTC + ETH steht seit Befund 27 fest, und jede Zahl dieses
    Projekts steht darauf.
    """

    saetze: tuple[Marktsatz, ...] = ()

    @property
    def referenz(self) -> Marktsatz | None:
        return self.saetze[0] if self.saetze else None

    @property
    def weitere(self) -> tuple[Marktsatz, ...]:
        return self.saetze[1:]

    def stichprobe_waechst(self) -> bool | None:
        """Bringt die Breite ueberhaupt zusaetzliche Beobachtungen?

        Genau die Frage, die Befund 27 mit *"bleibt bei 150"* verneint hat.
        """
        ref = self.referenz
        if ref is None or not self.weitere:
            return None
        return max(s.effektiv for s in self.weitere) > ref.effektiv

    def evidenz_waechst(self) -> bool | None:
        """Waechst ``Guete x sqrt(n)`` - die Groesse, auf die es ankommt?"""
        ref = self.referenz
        if ref is None or not self.weitere:
            return None
        return max(s.evidenz for s in self.weitere) > ref.evidenz

    def schlaegt_referenz(self) -> tuple[Marktsatz, ...]:
        """Aufstellungen, die die Referenz in **jeder** Hinsicht schlagen.

        Kein Gate weniger, kein kleinerer Deflated Sharpe, keine kleinere
        Evidenz - und mindestens eines echt besser. Ein Tausch zaehlt nicht.
        """
        ref = self.referenz
        if ref is None:
            return ()
        aus = []
        for s in self.weitere:
            nicht_schlechter = (
                s.bestanden >= ref.bestanden
                and s.dsr >= ref.dsr
                and s.evidenz >= ref.evidenz
            )
            echt_besser = (
                s.bestanden > ref.bestanden
                or s.dsr > ref.dsr
                or s.evidenz > ref.evidenz
            )
            if nicht_schlechter and echt_besser:
                aus.append(s)
        return tuple(aus)

    def urteil(self) -> str:
        ref = self.referenz
        if ref is None:
            return "Keine Aufstellung gemessen - dazu ist nichts zu sagen."
        if not self.weitere:
            return f"Nur '{ref.name}' gemessen - ein Vergleich braucht zwei."
        besser = self.schlaegt_referenz()
        if besser:
            namen = ", ".join(s.name for s in besser)
            return (
                f"**Die Breite traegt**: {namen} schlaegt '{ref.name}' in jeder "
                f"Hinsicht. Das ist zu pruefen und nicht zu glauben - eine "
                f"Aufstellung, die besser dasteht, ist noch kein Kandidat."
            )
        schlechtester = min(self.weitere, key=lambda s: s.dsr)
        teile = [
            f"**Die Breite traegt nicht.** Keine Aufstellung schlaegt "
            f"'{ref.name}' in jeder Hinsicht; der Deflated Sharpe faellt bis "
            f"{schlechtester.dsr:.4f}."
        ]
        if self.stichprobe_waechst():
            groesster = max(self.weitere, key=lambda s: s.effektiv)
            teile.append(
                f"Und zwar **nicht** aus Mangel an Beobachtungen: Die effektive "
                f"Stichprobe waechst von {ref.effektiv} auf "
                f"{groesster.effektiv}. Die Guete faellt schneller, als "
                f"sqrt(n) steigt - {ref.evidenz:.3f} gegen "
                f"{max(s.evidenz for s in self.weitere):.3f} auf der Groesse, "
                f"die zaehlt."
            )
        else:
            teile.append(
                f"Die effektive Stichprobe waechst dabei nicht ueber "
                f"{ref.effektiv} hinaus."
            )
        return " ".join(teile)
