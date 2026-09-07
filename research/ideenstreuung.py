"""Die Ideenstreuung - zum zweiten Mal, und diesmal aus Ziehungen.

Worum es geht
-------------
Befund 71 hat die Frage des Projekts auf einen Vergleich zweier Vorfaktoren
reduziert: Huerde und bester Fund wachsen beide mit derselben
Extremwertkonstante, es entscheidet allein, ob die Streuung echter Regelideen
ueber der des reinen Zufalls liegt.

``wettrennen.py`` schaetzt diese Streuung, indem es sie aus **einem** Wert
zurueckrechnet - dem beobachteten Bestwert nach 198 Versuchen. Sein Kopf nennt
das als Grenze des Modells und sagt dazu: *"Mehr gibt es nicht: Der Bestwert
nach 166 Versuchen ist die einzige Beobachtung dieser Art, die vorliegt."*

**Das stimmt seit Befund 83 nicht mehr** (Befund 237). Im Versuchsverzeichnis
liegen acht Regeln, die gegen die Spezifikation **gebaut** wurden statt aus
einem Katalog ausgewaehlt - vier aus Befund 77, vier aus Befund 83 - und jede
von ihnen ist mit Trade-Zahl und Guete verzeichnet. Sie sind Ziehungen und
keine Ueberlebenden: Beide Laeufe haben gemessen, was sie vorgeschlagen
hatten, ohne vorher zu sieben.

Damit laesst sich die Streuung **direkt** schaetzen, statt sie
zurueckzurechnen.

Warum die Rohstreuung zu gross ist
----------------------------------
Jede einzelne Guete ist selbst geschaetzt, und zwar aus wenigen Trades. Der
Standardfehler eines Sharpe je Trade betraegt rund

    sqrt((1 + SR^2 / 2) / n)

und bei 18 Trades sind das 0,236 - mehr, als die ganze gesuchte Groesse
ausmacht. Was man beobachtet, ist deshalb nicht die Ideenstreuung, sondern

    beobachtet^2  =  echt^2  +  Schaetzrauschen^2

Dieses Modul zieht das Rauschen ab. Ohne diesen Schritt waere die Zahl
systematisch zu gross, und zwar am staerksten bei den seltensten Regeln -
genau denen, die in diesem Projekt die beste Guete zeigen (Befund 54).

Was die Zahl **nicht** hergibt
------------------------------
* **Acht Ziehungen sind wenig.** Die relative Unsicherheit einer Streuung aus
  acht Werten liegt bei rund 27 %, und unabhaengig sind sie nicht einmal alle:
  Drei der vier aus Befund 83 sind dieselben Ideen wie in Befund 77, nur mit
  anders kalibrierten Schwellen.
* **Es waren keine Sprachmodell-Vorschlaege.** Befund 77 sagt es ausdruecklich:
  *"In diesem Container ist kein Sprachmodell verdrahtet ... Also habe ich ihn
  beantwortet."* Gemessen ist die Streuung von Regeln, die **gegen die
  Spezifikation gebaut** wurden - nicht die von ``cli wettbewerb --ki``. Ueber
  die Research-KI sagt diese Zahl nichts.
* **Roh statt effektiv.** Verzeichnet sind Trade-Zahlen, nicht effektive
  Stichproben. Die Nullstreuung des Gates rechnet mit letzteren.
* **Keine taugte.** Eine breitere Streuung ist kein besserer Kandidat, sondern
  eine breitere Ziehung. Alle acht sind an der Qualitaet gescheitert.

Die Zahl ist damit ein **zweiter Messwert neben einem sehr unsicheren
ersten**, und nicht dessen Ersatz. Befund 236 steht direkt davor: Ein
Punktschaetzer im Ton eines Urteils ist der Fehler, den dieses Projekt zuletzt
gemacht hat.

Und sie gehoert **nicht** in das Wettrennen (Befund 238)
--------------------------------------------------------
Der naechstliegende Griff waere, diese Streuung in ``Rennen`` einzusetzen und
den Schnittpunkt neu zu rechnen. ``Rennen.erklaert_den_verlauf`` weist das
zurueck, und zwar deutlich:

    Streuung   Mittel    erwarteter Bestwert nach 198 Versuchen
    0,0918     0,0000    0,2535    <- beobachtet, per Konstruktion
    0,1654     0,0324    0,4892    <- diese Messung
    0,1019     0,1685    0,4500    <- der Ansatz, den der Modulkopf verwirft

Haette die Suche aus dieser Verteilung gezogen, stuende der Bestwert nach 198
Versuchen bei 0,49. Er steht bei 0,2535. **Es sind zwei Populationen:** Die
198 Versuche waren ueberwiegend Reglerscans in der Nachbarschaft des Bestands,
diese acht sind gegen die Spezifikation gebaute Regeln. Auf ihre **eigenen**
acht Ziehungen angewandt passt die Streuung dagegen ungefaehr (erwartet
0,2737, bester mit brauchbarer Trade-Zahl 0,2238).

Wer die eine Zahl in die andere Rechnung setzt, macht denselben Fehler wie an
elf anderen Stellen dieses Projekts - eine Groesse an Punkt A gemessen und an
Punkt B verwendet -, nur eine Ebene hoeher: nicht zwei Betriebspunkte, sondern
zwei Ideenquellen.

**Was daraus folgt und was nicht.** Die Aussage "die Suche holt nicht auf"
beschreibt die Reglerscans, nicht das Regelbauen; sie ist enger, als sie
klingt. Ein Beleg dafuer, dass Regelbauen ankommt, ist das nicht: Alle acht
sind gescheitert, und ihr bester Wert mit brauchbarer Trade-Zahl (0,2238)
liegt **unter** dem Bestand (0,2535). Eine breitere Ziehung um ein Mittel
nahe null ist kein besserer Kandidat.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

#: Herkuenfte, unter denen gebaute - nicht ausgewaehlte - Regeln liegen.
#:
#: ``verbund`` gehoert **nicht** dazu: Das sind Paarungen des Bestands mit
#: sich selbst, also Nachbarschaft und keine neue Idee. Die Herkunft trennt in
#: diesem Projekt nach Lauf und nicht nach Quelle (Befund 211) - deshalb steht
#: hier eine Liste und keine Mustersuche nach "KI".
GEBAUT: tuple[str, ...] = ("gen11 partnersuche", "gen12 kalibriert")


@dataclass(frozen=True, slots=True)
class Ziehung:
    """Eine gemessene Regel: was sie brachte und auf wievielen Trades."""

    kennung: str
    guete: float
    trades: int

    @property
    def standardfehler(self) -> float:
        """Wie genau diese eine Guete ueberhaupt bekannt ist."""
        if self.trades < 2:
            return float("inf")
        return math.sqrt((1.0 + self.guete**2 / 2.0) / self.trades)


@dataclass(frozen=True, slots=True)
class Schaetzung:
    """Die Streuung der Ideen - beobachtet, davon Rauschen, und der Rest."""

    ziehungen: tuple[Ziehung, ...]

    @property
    def anzahl(self) -> int:
        return len(self.ziehungen)

    @property
    def mittel(self) -> float:
        return sum(z.guete for z in self.ziehungen) / self.anzahl

    @property
    def beobachtet(self) -> float:
        """Die rohe Streuung der gemessenen Gueten."""
        m = self.mittel
        return math.sqrt(
            sum((z.guete - m) ** 2 for z in self.ziehungen) / (self.anzahl - 1)
        )

    @property
    def rauschen(self) -> float:
        """Wieviel Streuung allein daraus kommt, dass jede Guete geschaetzt ist."""
        return math.sqrt(
            sum(z.standardfehler**2 for z in self.ziehungen) / self.anzahl
        )

    @property
    def echt(self) -> float | None:
        """Was nach Abzug des Rauschens bleibt.

        ``None``, wenn nichts bleibt: Dann ist die beobachtete Streuung durch
        Schaetzfehler allein erklaerbar, und eine Wurzel aus einer negativen
        Zahl waere eine erfundene Zahl.
        """
        rest = self.beobachtet**2 - self.rauschen**2
        return math.sqrt(rest) if rest > 0 else None

    @property
    def unsicherheit(self) -> float:
        """Relative Unsicherheit einer Streuung aus ``anzahl`` Werten.

        Naeherung ``1 / sqrt(2 (k - 1))``. Bei acht Ziehungen sind das 27 %,
        bei vier 41 % - die Zahl ist ein Anhaltspunkt und keine Messung.
        """
        return 1.0 / math.sqrt(2.0 * (self.anzahl - 1))

    def als_zeilen(self) -> tuple[str, ...]:
        echt = self.echt
        return (
            f"Ziehungen            {self.anzahl}",
            f"Mittel               {self.mittel:+.4f}",
            f"beobachtete Streuung {self.beobachtet:.4f}",
            f"davon Schaetzfehler  {self.rauschen:.4f}",
            (
                f"bleibt               {echt:.4f}  (+/- rund "
                f"{self.unsicherheit:.0%})"
                if echt is not None
                else "bleibt               nichts - Schaetzfehler erklaeren alles"
            ),
        )


@dataclass(frozen=True, slots=True)
class Populationsvergleich:
    """Erklaert diese Streuung den Verlauf, an dem das Rennen kalibriert ist?

    **Der Grund, warum es diese Klasse gibt** (Befund 238): Zwei Zahlen fuer
    dieselbe Groesse laden dazu ein, die eine in die Rechnung der anderen zu
    setzen. Hier faellt auf, wenn das nicht geht.
    """

    erwartet: float
    """Welchen Bestwert diese Streuung nach ``versuche`` Ziehungen vorhersagt."""

    beobachtet: float
    """Welcher Bestwert tatsaechlich dasteht."""

    spielraum: float = 0.05

    @property
    def passt(self) -> bool:
        return abs(self.erwartet - self.beobachtet) <= self.spielraum

    @property
    def abweichung(self) -> float:
        return self.erwartet - self.beobachtet

    def urteil(self) -> str:
        if self.passt:
            return (
                f"erklaert den Verlauf: {self.erwartet:.4f} erwartet gegen "
                f"{self.beobachtet:.4f} beobachtet"
            )
        return (
            f"erklaert den Verlauf **nicht**: {self.erwartet:.4f} erwartet "
            f"gegen {self.beobachtet:.4f} beobachtet ({self.abweichung:+.4f}). "
            f"Zwei Populationen - diese Streuung gehoert nicht in eine "
            f"Rechnung, die an jenem Bestwert kalibriert ist."
        )


def vergleiche(
    schaetzung: Schaetzung, *, bester: float, versuche: int, spielraum: float = 0.05
) -> Populationsvergleich:
    """Die Schaetzung gegen einen beobachteten Bestwert halten.

    ``versuche`` ist die Zahl der Ziehungen, aus denen ``bester`` stammt - die
    198 des Projektverlaufs, oder die acht dieser Messung selbst. Beide
    Richtungen sind aufschlussreich, und sie fallen unterschiedlich aus.
    """
    from research.wettrennen import extremwert

    streuung = schaetzung.echt
    if streuung is None:
        streuung = 0.0
    return Populationsvergleich(
        erwartet=schaetzung.mittel + streuung * extremwert(versuche),
        beobachtet=bester,
        spielraum=spielraum,
    )


def ziehungen(pfad: Path | str, *, herkuenfte: tuple[str, ...] = GEBAUT) -> tuple[Ziehung, ...]:
    """Die gebauten Regeln aus dem Versuchsverzeichnis lesen.

    Ohne Guete verzeichnete Versuche bleiben draussen - sie tragen zur Frage
    nichts bei, und ein Ersatzwert waere eine erfundene Ziehung.
    """
    inhalt = json.loads(Path(pfad).read_text())
    return tuple(
        Ziehung(
            kennung=v["kennung"],
            guete=float(v["sharpe_je_trade"]),
            trades=int(v["trades"]),
        )
        for v in inhalt.get("versuche", ())
        if v.get("herkunft") in herkuenfte and v.get("sharpe_je_trade") is not None
    )


def schaetzen(pfad: Path | str, **kwargs) -> Schaetzung | None:
    """Die Streuung aus dem Verzeichnis schaetzen - ``None`` bei zu wenig.

    Unter zwei Ziehungen gibt es keine Streuung, und eine aus zwei waere eine
    Zahl ohne Aussage. Drei ist die Untergrenze, ab der hier ueberhaupt
    gerechnet wird.
    """
    gezogen = ziehungen(pfad, **kwargs)
    return Schaetzung(ziehungen=gezogen) if len(gezogen) >= 3 else None
