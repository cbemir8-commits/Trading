"""Wie stark haengt die wichtigste Zahl des Projekts an einer Modellwahl?

Die Frage
---------
Befund 133 endete mit einem Satz, den ich selbst hingeschrieben und stehen
gelassen habe:

    "Offen und unbequem: ob die 152 des Referenzlaufs einer strengeren
     Abhaengigkeitspruefung standhielten."

Auf dieser 152 steht alles: der Deflated Sharpe 0,8640, die Luecke von 0,0860,
die 30 fehlenden Beobachtungen aus Befund 132, die 1,8 Jahre.

``unabhaengigkeit.designeffekt`` kuerzt gegen das **95. Perzentil** der
Permutationsnull. Der Modulkopf dort begruendet diese Wahl ausfuehrlich und
gut - am Median wuerde *"die Haelfte aller sauberen Messungen bestraft"*, und
gegen bekannte Null bleiben 95 % ungekuerzt. **Was die Wahl fuer diesen
Kandidaten wert ist, stand nirgends.**

Gemessen
--------
Spot-Punkt, 198 Versuche, 152 Trades, 31 Kalenderfenster. Gemessener
Designeffekt **1,4422** bei einem ICC von **0,109** - das liegt am **92,5.
Perzentil** der Null, p = 0,0750.

    Kalibrierung              Schranke    n      DSR    Jahre bis zur Schwelle
    95. Perzentil (Regel)       1,5262   152   0,8640                     1,8
    93. Perzentil               1,4552   152   0,8640                     1,8
    90. Perzentil               1,3701   144   0,8266                     2,4
    Median                      1,0000   105   0,5393                     6,6
    roher Designeffekt               -   105   0,5393                     6,6

Die zweite Einteilung - nach Gleichzeitigkeit - zeigt gar keine Abhaengigkeit
(ICC 0,000). Es entscheidet also allein die Einteilung nach Kalenderfenstern,
und dort haengt alles an der Kalibrierung.

Was daraus folgt
----------------
**Die Spanne ist 0,3247. Die Luecke zur Schwelle ist 0,0860.** Die
Unsicherheit aus einer einzigen Modellwahl ist damit fast das Vierfache des
Abstands, den das Projekt seit Dutzenden von Befunden vermisst.

Anders gesagt: Zwischen *"0,086 zu wenig"* und *"0,41 zu wenig"* kann dieses
Projekt derzeit nicht unterscheiden. Befund 132s 1,8 Jahre sind das
**optimistische Ende einer Spanne von 1,8 bis 6,6 Jahren**.

Was das **nicht** heisst
------------------------
Dass die Regel falsch waere. Sie ist begruendet, gegengeprueft und bewusst
konservativ in die Richtung gebaut, in die eine Unsicherheit fallen darf: Sie
straft nicht, wo die Abhaengigkeit nicht von Zufall zu unterscheiden ist.

Und die Abhaengigkeit **ist** hier nicht von Zufall zu unterscheiden - p =
0,0750 gegen die Grenze 0,05. Die Regel tut genau das, wofuer sie gebaut ist.

Dieses Modul wechselt die Kalibrierung deshalb **nicht**. Es misst, was an ihr
haengt, und schreibt es hin.

Zum Stand
---------
Die Zahlen oben rechnen mit **n = 152** und einem Deflated Sharpe von 0,8640.
Beides ist seit **Befund 135** ueberholt: Das Gate teilt seither zusaetzlich
nach Kalenderquartalen, die effektive Stichprobe faellt auf 112 und der
Deflated Sharpe auf 0,6026. Die Messungen hier bleiben richtig - sie sind an
ihrem Tag so entstanden. Der massgebliche Stand steht in
``research/referenz.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Empfindlichkeit", "Kalibrierung"]


@dataclass(frozen=True, slots=True)
class Kalibrierung:
    """Ein Perzentil der Permutationsnull und was daraus folgt."""

    name: str
    quantil: float
    schranke: float
    effektiv: int
    dsr: float
    jahre: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.quantil <= 1.0:
            raise ValueError(
                f"'{self.name}': {self.quantil} ist kein Perzentil in (0, 1]."
            )

    def als_zeile(self) -> str:
        return (
            f"{self.name:<28} {self.schranke:>8.4f} {self.effektiv:>5} "
            f"{self.dsr:>8.4f}"
            + (f" {self.jahre:>8.1f}" if self.jahre is not None else "")
        )


@dataclass(frozen=True, slots=True)
class Empfindlichkeit:
    """Wie stark der Deflated Sharpe an der Kalibrierung haengt.

    **Es gibt hier absichtlich keine Methode, die eine Kalibrierung
    auswaehlt.** Dieselbe Sperre wie in ``decke.Fensterlage``,
    ``historie.Historienkurve`` und ``aufstellung.Aufstellungsreihe``: Sich
    nach den Zahlen eine Modellwahl auszusuchen ist ein gelockertes Gate mit
    anderem Namen - hier waere es sogar das wirksamste, weil es unter allen
    Gates zugleich liegt.

    Die Referenz ist die Regel, die im Code steht. Sie bleibt es.
    """

    roh: int
    icc: float
    designeffekt: float
    p_wert: float
    kalibrierungen: tuple[Kalibrierung, ...] = ()
    referenz_quantil: float = 0.95
    schwelle: float = 0.95

    @property
    def referenz(self) -> Kalibrierung | None:
        """Die Kalibrierung, die im Code steht - nicht die guenstigste."""
        for k in self.kalibrierungen:
            if abs(k.quantil - self.referenz_quantil) < 1e-9:
                return k
        return None

    @property
    def spanne(self) -> float | None:
        """Wie weit der Deflated Sharpe ueber die Kalibrierungen wandert."""
        if len(self.kalibrierungen) < 2:
            return None
        werte = [k.dsr for k in self.kalibrierungen]
        return max(werte) - min(werte)

    @property
    def luecke(self) -> float | None:
        """Was der Referenzkalibrierung zur Schwelle fehlt."""
        ref = self.referenz
        return None if ref is None else self.schwelle - ref.dsr

    def uebersteigt_die_luecke(self) -> bool | None:
        """Ist die Modellunsicherheit groesser als der gemessene Abstand?

        Wenn ja, ist der Abstand keine belastbare Groesse mehr: Das Projekt
        kann dann nicht unterscheiden, ob es knapp oder weit daneben liegt.
        """
        spanne, luecke = self.spanne, self.luecke
        if spanne is None or luecke is None:
            return None
        return spanne > luecke

    def knapp(self, rand: float = 0.03) -> bool:
        """Liegt der p-Wert nahe an der Grenze, ab der gekuerzt wuerde?

        ``Effektivwert.knapp`` stellt dieselbe Frage fuer einen einzelnen Lauf.
        Hier geht es um die Referenzkalibrierung: Ein p-Wert dicht ueber 0,05
        heisst, dass die volle Stichprobe nicht mit Abstand steht, sondern
        knapp.
        """
        return 0.05 < self.p_wert <= 0.05 + rand

    def urteil(self) -> str:
        ref = self.referenz
        if ref is None or len(self.kalibrierungen) < 2:
            return "Zu wenig gemessen - dazu ist nichts zu sagen."
        spanne, luecke = self.spanne, self.luecke
        teile = [
            f"Der Deflated Sharpe wandert ueber die Kalibrierungen um "
            f"**{spanne:.4f}** ({min(k.dsr for k in self.kalibrierungen):.4f} "
            f"bis {max(k.dsr for k in self.kalibrierungen):.4f}); zur Schwelle "
            f"fehlen {luecke:.4f}."
        ]
        if self.uebersteigt_die_luecke():
            teile.append(
                f"**Die Modellwahl waehlt mehr aus als der gemessene Abstand.** "
                f"Zwischen '{luecke:.3f} zu wenig' und "
                f"'{self.schwelle - min(k.dsr for k in self.kalibrierungen):.3f} "
                f"zu wenig' laesst sich hier nicht unterscheiden."
            )
        else:
            teile.append(
                "Die Modellwahl bleibt unter dem gemessenen Abstand - der "
                "Abstand traegt."
            )
        if self.knapp():
            teile.append(
                f"Dazu steht die volle Stichprobe knapp: p = {self.p_wert:.4f} "
                f"gegen die Grenze 0,05, ICC {self.icc:.3f}. Die Regel straft "
                f"zu Recht nicht - aber sie straft auch nicht mit Abstand."
            )
        return " ".join(teile)
