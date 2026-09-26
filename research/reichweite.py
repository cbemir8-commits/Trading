"""Wie weit haengt das Urteil daran, wo die Reihe anfaengt?

Der einzige offene Auftrag beim Nutzer lautet: Bybit-Tageskerzen laden, weil
jede Zahl dieses Projekts auf Bitstamp-Kassakursen steht (Befund 171/213). Die
Zeile dafuer nennt ``--von 2017-08-16`` - den Anfang der Bitstamp-Reihe. Ob
Bybit so weit zurueckreicht, weiss dieses Projekt nicht, und geraten wird es
hier nicht.

Gemessen ist stattdessen, was eine **kuerzere** Reihe am Urteil aendert:
derselbe Kandidat, dieselben Daten, nur spaeter angefangen. Das kostet keinen
Versuch - es ist dieselbe Hypothese.

**Und es aendert das Urteil** (Befund 345, Spot-Punkt, 203 Versuche):

    ab            Tage  Trades  n_eff   Guete     CAGR  Rueckg.     DSR  Gates
    2017-08-16    3300     156    115  0,2708   14,34%    9,87%  0,5826   9/11
    2018-01-01    3162     147    109  0,2878   17,54%   10,07%  0,6490  10/11
    2019-01-01    2797     127    108  0,2941   18,81%   10,07%  0,6841  10/11
    2020-01-01    2432     109    109  0,2478   10,55%   10,07%  0,3766   9/11
    2021-01-01    2066      88     88  0,2320   11,81%   10,07%  0,1684   9/11
    2022-01-01    1701      68     68  0,2926   16,72%   10,07%  0,2703  10/11

Vier Monate spaeter angefangen, und die Jahresrendite steigt von 14,34 % auf
17,54 % - ueber die Betriebsschwelle von 15 %. Die **Messlatte** haelt dann, und
aus 9 von 11 werden 10.

Was das heisst und was nicht
----------------------------
**Die 0,66 Punkte, die dem Bestand zur Messlatte fehlen, sind keine Eigenschaft
der Strategie.** Sie sind eine Eigenschaft des Zeitraums, und zwar eine, die
sich durch Weglassen von 138 Tagen am Anfang aufloest. Das ist die Definition
einer angepassten Stichprobe, und deshalb ist diese Leiter **kein Weg** - sie
ist eine Warnung.

**Das bindende Gate bleibt bindend.** Der Deflated Sharpe steht auf keiner
Sprosse ueber 0,6841 und damit nirgends in der Naehe von 0,95. Kein
Reihenanfang holt ihn, und das ist die beruhigende Haelfte des Befunds: Was die
Zulassung wirklich blockiert, laesst sich so nicht wegschneiden.

**Fuer den offenen Auftrag ist es eine Warnung.** Bybit ist spaeter gestartet als
Bitstamp. Ein Bericht auf Bybit-Kerzen wird also eine kuerzere Reihe haben - und
dann womoeglich **10 von 11** zeigen. Wer das neben die heutigen 9 legt, liest
einen Fortschritt, wo nur der Anfang verschoben ist. Deshalb gehoert die
Reichweite neben jede Gate-Bilanz.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Leiter", "Sprosse"]


@dataclass(frozen=True, slots=True)
class Sprosse:
    """Ein Reihenanfang und was die Zulassungsstrecke dort sagt."""

    ab: str
    tage: int
    trades: int
    effektiv: int
    guete: float
    cagr: float
    rueckgang: float
    dsr: float
    bestanden: int
    gesamt: int

    uebersprungen: int = 0
    """Gates, die auf dieser Sprosse gar nicht geurteilt haben - Befund 332.

    Der Name ist der des Projekts: ``finanzierung.Stufe.uebersprungen`` fuehrt
    dieselbe **Zahl**, ``koernung.Gatelauf.ausgesetzt`` die Namensliste. Ein
    drittes Wort fuer dieselbe Sache waere die Sorte Abweichung, die Befund 333
    an einem Stellvertreter gefunden hat.

    ``GateResult.passed`` ist wahr, solange ein Gate nicht durchgefallen ist,
    und ein **uebersprungenes** Gate ist nicht durchgefallen. Ohne dieses Feld
    sieht eine Sprosse mit acht Urteilen und drei Aussetzern wie eine mit elf
    Urteilen aus - und kuerzere Reihen sind genau der Fall, in dem Gates
    aussetzen: Monte-Carlo braucht 20 Trades, Regime-Aufteilung und Deflated
    Sharpe je 30.
    """

    def __post_init__(self) -> None:
        if self.gesamt <= 0:
            raise ValueError("Eine Sprosse ohne Gates ist keine Messung.")
        if not 0 <= self.bestanden <= self.gesamt:
            raise ValueError(
                f"{self.bestanden} von {self.gesamt} bestandenen Gates ist "
                f"keine Bilanz."
            )
        if self.effektiv > self.trades:
            raise ValueError(
                f"{self.ab}: {self.effektiv} wirksame von {self.trades} rohen "
                f"Trades - wirksam ist hoechstens roh."
            )
        if not 0 <= self.uebersprungen <= self.gesamt:
            raise ValueError(
                f"{self.ab}: {self.uebersprungen} uebersprungene von "
                f"{self.gesamt} "
                f"Gates ist keine Bilanz."
            )


@dataclass(frozen=True, slots=True)
class Leiter:
    """Dieselbe Regel auf mehreren Reihenanfaengen."""

    sprossen: tuple[Sprosse, ...]
    ziel_dsr: float = 0.95

    def __post_init__(self) -> None:
        if not self.sprossen:
            raise ValueError("Eine Leiter ohne Sprossen ist keine Leiter.")

    @property
    def mit_aussetzern(self) -> tuple[Sprosse, ...]:
        """Sprossen, auf denen nicht jedes Gate geurteilt hat - Befund 332."""
        return tuple(s for s in self.sprossen if s.uebersprungen)

    @property
    def voll(self) -> Sprosse:
        """Die laengste Reihe - der Stand, auf dem die Zahlen des Projekts
        stehen."""
        return max(self.sprossen, key=lambda s: s.tage)

    @property
    def beste(self) -> Sprosse:
        """Die Sprosse mit den meisten bestandenen Gates.

        Bei Gleichstand die **laengste**: Sonst waere die kuerzeste Reihe
        automatisch die "beste", und genau diese Lesart soll der Bericht
        verhindern.
        """
        return max(self.sprossen, key=lambda s: (s.bestanden, s.tage))

    @property
    def gewinn(self) -> int:
        """Wie viele Gates eine kuerzere Reihe zusaetzlich zeigt."""
        return max(0, self.beste.bestanden - self.voll.bestanden)

    @property
    def flattert(self) -> bool:
        """Zeigt eine kuerzere Reihe mehr Gates als die volle?

        ``True`` ist keine Gelegenheit, sondern der Grund, die Reichweite
        neben jede Gate-Bilanz zu schreiben.
        """
        return self.gewinn > 0 and self.beste.tage < self.voll.tage

    @property
    def dsr_bleibt_offen(self) -> bool:
        """Verfehlt der Deflated Sharpe auf **jeder** Sprosse sein Ziel?"""
        return all(s.dsr < self.ziel_dsr for s in self.sprossen)

    @property
    def hoechster_dsr(self) -> float:
        return max(s.dsr for s in self.sprossen)

    def tabelle(self) -> str:
        zeilen = [
            f"{'ab':<12} {'Tage':>5} {'Trades':>7} {'n_eff':>6} {'Guete':>7} "
            f"{'CAGR':>8} {'Rueckg.':>8} {'DSR':>7} {'Gates':>7}",
            "-" * 72,
        ]
        for s in sorted(self.sprossen, key=lambda x: x.ab):
            zeilen.append(
                f"{s.ab:<12} {s.tage:>5} {s.trades:>7} {s.effektiv:>6} "
                f"{s.guete:>7.4f} {s.cagr:>7.2f}% {s.rueckgang:>7.2f}% "
                f"{s.dsr:>7.4f} {s.bestanden:>4}/{s.gesamt}"
                + (f" ({s.uebersprungen} ausgesetzt)" if s.uebersprungen else "")
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        teile = []
        if self.flattert:
            teile.append(
                f"**Eine kuerzere Reihe zeigt mehr Gates.** Auf der vollen "
                f"Reihe ({self.voll.tage} Tage, ab {self.voll.ab}) halten "
                f"{self.voll.bestanden} von {self.voll.gesamt}; ab "
                f"{self.beste.ab} - {self.voll.tage - self.beste.tage} Tage "
                f"kuerzer - sind es {self.beste.bestanden}. Die Jahresrendite "
                f"steigt dabei von {self.voll.cagr:.2f} % auf "
                f"{self.beste.cagr:.2f} %."
            )
            teile.append(
                "**Das ist kein Weg, sondern eine Warnung.** Eine Bilanz, die "
                "sich durch einen spaeteren Anfang verbessert, sagt etwas "
                "ueber den Zeitraum und nichts ueber die Strategie. Den "
                "Anfang zu verschieben, weil dort mehr Gates halten, ist "
                "genau die Anpassung, gegen die die Zulassungsstrecke gebaut "
                "ist."
            )
        else:
            teile.append(
                f"**Die Bilanz haengt nicht am Reihenanfang.** Die volle Reihe "
                f"({self.voll.tage} Tage) zeigt {self.voll.bestanden} von "
                f"{self.voll.gesamt}, und keine kuerzere zeigt mehr."
            )
        if self.dsr_bleibt_offen:
            teile.append(
                f"**Das bindende Gate bleibt bindend.** Der Deflated Sharpe "
                f"kommt auf keiner Sprosse ueber {self.hoechster_dsr:.4f} und "
                f"damit nirgends an {self.ziel_dsr:.2f}. Was die Zulassung "
                f"blockiert, laesst sich durch einen anderen Reihenanfang "
                f"nicht wegschneiden."
            )
        else:
            teile.append(
                f"**Achtung: Auf einer Sprosse haelt auch der Deflated "
                f"Sharpe** ({self.hoechster_dsr:.4f} gegen "
                f"{self.ziel_dsr:.2f}). Das waere eine Zulassung, die am "
                f"Reihenanfang haengt - und keine."
            )
        teile.append(
            "Fuer den offenen Auftrag heisst das: Bybit ist spaeter gestartet "
            "als Bitstamp, ein Bericht auf Bybit-Kerzen hat also eine "
            "kuerzere Reihe. Wer seine Gate-Bilanz neben die heutige legt, "
            "vergleicht zwei Zeitraeume und nicht zwei Boersen. Die "
            "Reichweite gehoert deshalb neben jede Bilanz."
        )
        return "\n\n".join(teile)
