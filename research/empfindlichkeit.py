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

Nachgemessen am heutigen Punkt (Befund 156)
-------------------------------------------
Die Zahlen oben stammen aus Befund 134 und rechnen mit **n = 152** und einem
Deflated Sharpe von 0,8640. Seither haben Befund 135, 151, 152, 153 und 154
die Rezeptur veraendert - aus zwei Einteilungen sind acht geworden. Dieselbe
Frage, heute gestellt:

    Bestand allein, 158 Trades, 198 Versuche
      Kalibrierung                n    Guete      DSR    fehlt
      Median                     78    2,225   0,1824    1,311
      75. Perzentil              90    2,390   0,2633    1,169
      90. Perzentil             103    2,557   0,3603    1,028
      95. Perzentil (Regel)     114    2,690   0,4452    0,916
      99. Perzentil             140    2,981   0,6340    0,671

    Bestand + Trend-Beteiligung 200 Tage, 211 Trades
      Median                     92    2,456   0,2840    1,107
      75. Perzentil             106    2,636   0,4023    0,955
      90. Perzentil             126    2,874   0,5712    0,754
      95. Perzentil (Regel)     136    2,986   0,6480    0,659
      99. Perzentil             156    3,198   0,7763    0,479

Auf **denselben Sprossen wie Befund 134** (Median bis 95. Perzentil):

    Punkt                Spanne   Luecke   Verhaeltnis
    Befund 134           0,3247   0,0860        3,78 x
    Bestand heute        0,2628   0,5048        0,52 x
    Paar heute           0,3640   0,3020        1,21 x

**Das Verhaeltnis hat sich umgekehrt** - und zwar nicht, weil die Spanne
kleiner geworden waere, sondern weil die **Luecke gewachsen ist**. Die
Korrekturen aus 151 bis 154 haben den Deflated Sharpe gedrueckt; der Abstand
zur Schwelle ist dadurch groesser als die Unsicherheit ueber ihn.

Fuer den Bestand allein laesst sich die Aussage *"er reicht nicht"* damit
erstmals treffen, ohne dass eine Modellwahl sie kippen koennte. **Fuer das
veroeffentlichte Paar noch nicht:** Dort ist die Spanne weiter 1,21 mal die
Luecke.

Die Saat ist keine Modellwahl (Befund 156)
-------------------------------------------
Befund 134 hat sie nicht geprueft. Ueber fuenf Saaten des Zufallsgenerators:

    Bestand   n zwischen 113 und 115, DSR-Spanne 0,0154
    Paar      n zwischen 135 und 137, DSR-Spanne 0,0146

Die Zahl ist also auf etwa **±0,015 im Deflated Sharpe** wiederholbar -
verschwindend gegen die Kalibrierungsspanne, aber nicht null. Wer zwei Laeufe
auf der vierten Stelle vergleicht, vergleicht Rauschen.

Zum Stand
---------
Die Messungen aus Befund 134 bleiben richtig - sie sind an ihrem Tag so
entstanden. Der massgebliche Stand steht in ``research/referenz.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

__all__ = ["Empfindlichkeit", "Kalibrierung", "Klippenprobe", "Sprosse"]


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


@dataclass(frozen=True, slots=True)
class Sprosse:
    """Eine Reglerstellung mit dem, was die Abhaengigkeitspruefung dort tut."""

    wert: float
    trades: int
    icc: float
    p_wert: float
    effektiv: int
    dsr: float

    def __post_init__(self) -> None:
        if self.trades <= 0:
            raise ValueError(f"Stellung {self.wert} ohne Trades ist keine Messung.")
        if self.effektiv > self.trades:
            raise ValueError(
                f"Stellung {self.wert}: {self.effektiv} unabhaengige aus "
                f"{self.trades} Trades - das geht nicht."
            )

    @property
    def anteil(self) -> float:
        """Wie viel von der Stichprobe uebrig bleibt (0 bis 1)."""
        return self.effektiv / self.trades


@dataclass(frozen=True, slots=True)
class Klippenprobe:
    """Ist eine Abhaengigkeitspruefung eine Kurve oder ein Schalter?

    Der Fehler, den das findet, ist dem Projekt schon einmal passiert und
    steht im Kopf von ``unabhaengigkeit.py``:

        Faktor   roh   effektiv    ICC       p     Deflated Sharpe
           0,6   226        151  0,079   0,040               0,467
           0,8   175        115  0,109   0,049               0,344
           1,0   152        152  0,112   0,072               0,851
          1,25   132         81  0,187   0,040               0,071

    *"Der ICC - die eigentliche Abhaengigkeit - steigt dort glatt an. Nur der
    p-Wert wandert ueber die Schwelle, und wo er knapp darunter faellt,
    verschwindet ein Drittel der Stichprobe."*

    Das ist die Signatur: **Die Abhaengigkeit bleibt, die Strafe springt.**
    Genau danach wird hier gesucht - und zwar an einer Leiter, nicht an einem
    Punkt, denn an einem Punkt ist ein Schalter nicht von einer Kurve zu
    unterscheiden.

    Gebaut fuer die Selbstpruefung von Befund 135 (Befund 137): Wer ein Gate
    aendert, hat es an mehr als einem Kandidaten zu zeigen.
    """

    sprossen: tuple[Sprosse, ...] = ()

    @property
    def icc_spanne(self) -> float | None:
        if len(self.sprossen) < 2:
            return None
        werte = [s.icc for s in self.sprossen]
        return max(werte) - min(werte)

    @property
    def anteil_spanne(self) -> float | None:
        """Wie stark der uebrig bleibende Anteil ueber die Leiter schwankt."""
        if len(self.sprossen) < 2:
            return None
        werte = [s.anteil for s in self.sprossen]
        return max(werte) - min(werte)

    def knapp_an_der_grenze(self, grenze: float = 0.05, rand: float = 0.02):
        """Sprossen, deren p-Wert dicht an der Signifikanzgrenze liegt.

        Dort entscheidet Rauschen im Permutationstest ueber ein Drittel der
        Stichprobe - das ist die Stelle, an der die Klippe entsteht.
        """
        return tuple(
            s for s in self.sprossen if abs(s.p_wert - grenze) <= rand
        )

    def bruch_im_verlauf(self) -> float | None:
        """Der groesste Verstoss gegen "mehr Abhaengigkeit, mehr Strafe".

        Nach ICC sortiert sollte der uebrig bleibende Anteil **fallen**: Wo
        die Abhaengigkeit groesser ist, gehoert mehr gekuerzt. Steigt er
        stattdessen, folgt die Kuerzung nicht der Sache.

        Der erste Anlauf hier fragte nach einem *ruhigen* ICC bei springender
        Strafe - und haette den historischen Fall **nicht** gefunden, denn
        dort wandert der ICC von 0,079 auf 0,187. Der Modulkopf von
        ``unabhaengigkeit.py`` sagt es genauer: *"Der ICC steigt dort glatt
        an"*, und trotzdem springt die Strafe. Nicht Stillstand ist die
        Signatur, sondern **Bruch im Verlauf**.
        """
        if len(self.sprossen) < 2:
            return None
        geordnet = sorted(self.sprossen, key=lambda s: s.icc)
        return max(
            (b.anteil - a.anteil for a, b in pairwise(geordnet)),
            default=0.0,
        )

    def ist_schalter(self, spielraum: float = 0.05) -> bool | None:
        """Folgt die Kuerzung der Abhaengigkeit - oder springt sie?

        ``spielraum`` laesst kleine Gegenlaeufigkeiten zu; die Schaetzung des
        ICC rauscht selbst. Gemessen trennt das die beiden Faelle deutlich:
        Die Leiter aus Befund 137 kommt auf 0,028, der historische Fall aus
        dem Kopf von ``unabhaengigkeit.py`` auf 0,343.
        """
        bruch = self.bruch_im_verlauf()
        return None if bruch is None else bruch > spielraum

    def urteil(self) -> str:
        if len(self.sprossen) < 2:
            return "Weniger als zwei Sprossen - ein Schalter braucht eine Leiter."
        icc, anteil = self.icc_spanne, self.anteil_spanne
        knapp = self.knapp_an_der_grenze()
        dsr = [s.dsr for s in self.sprossen]
        kopf = (
            f"ICC schwankt um {icc:.3f}, der uebrige Anteil um {anteil:.1%}, "
            f"der Deflated Sharpe zwischen {min(dsr):.4f} und {max(dsr):.4f}."
        )
        if self.ist_schalter():
            return (
                f"**Ein Schalter.** {kopf} Die Kuerzung folgt der Abhaengigkeit "
                f"nicht: Nach ICC geordnet steigt der uebrige Anteil um "
                f"{self.bruch_im_verlauf():.3f}, wo er fallen muesste."
            )
        wenn_knapp = (
            f" {len(knapp)} von {len(self.sprossen)} Sprossen liegen dicht an "
            f"der Signifikanzgrenze - dort entscheidet Rauschen."
            if knapp
            else " Keine Sprosse liegt dicht an der Signifikanzgrenze."
        )
        return f"**Eine Kurve.** {kopf}{wenn_knapp}"
