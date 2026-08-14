"""Liesse die Zulassungsstrecke ueberhaupt etwas durch?

Die Frage, die der Nullprobe fehlt
----------------------------------
``research/nullprobe.py`` beantwortet eine Haelfte: *Findet die Maschine einen
Vorteil, wo garantiert keiner ist?* Die Antwort war nein - die Maschine ist
sauber. Das ist die Frage nach dem **falschen Alarm**.

Die andere Haelfte stand nie da: *Erkennt die Maschine einen Vorteil, der
wirklich da ist?* Nach 161 Versuchen, sechzehn geschlossenen Richtungen und
einem Deflated Sharpe, der bei 0,80 klebt, ist das keine akademische Frage
mehr. Zwei Erklaerungen passen bisher gleich gut auf alles Gemessene:

1. Diese Regelfamilie traegt nicht.
2. Die Huerde ist bei 161 Versuchen so hoch, dass **nichts** mehr durchkaeme.

Beide sehen von innen identisch aus. Sie zu trennen entscheidet, ob die
restlichen 69 Versuche des Suchbudgets sinnvoll ausgegeben werden koennen -
und das ist die einzige Frage, die dieses Projekt gerade wirklich hat.

Wie hier ein Vorteil entsteht
-----------------------------
Nicht durch eine erfundene Preisreihe. Gepflanzt wird **in die echte**: Zu
jeder Tagesrendite kommt ein Regime-Anteil, der ueber Wochen dasselbe
Vorzeichen behaelt. Eine Trendfolge muss daran verdienen - genau dafuer ist
sie gebaut.

Zwei Eigenschaften machen den Vergleich erst gueltig:

* **Die Gesamtstreuung bleibt gleich.** Der Rauschanteil wird um genau so viel
  heruntergefahren, wie der Regime-Anteil hinzukommt. Sonst waere jede
  gepflanzte Stufe zugleich eine ruhigere Reihe, und Rueckgangs- und
  Monte-Carlo-Gate faenden es leichter, ohne dass die Strategie irgendetwas
  besser getroffen haette.
* **Die unterste Stufe ist die Wirklichkeit.** Bei Anteil 0 bleibt die Reihe
  unveraendert; dort muss das bekannte Ergebnis herauskommen. Eine Leiter, die
  nicht bei der gemessenen Realitaet beginnt, misst ihre eigene Erzeugung.

Was dabei ehrlich bleiben muss
------------------------------
**Diese Pruefung ist zur Strecke freundlich, nicht streng.** Das Regime ist
sauberer, als ein Markt je ist: kein Uebergangsrauschen, keine Faehrten, kein
Wechsel mitten in der Kerze. Wer hier durchkommt, koennte an einem echten
Markt derselben Staerke trotzdem scheitern.

Daraus folgt, welche Richtung dieser Test beweisen kann und welche nicht:

* Kommt **nichts** durch, ist das belastbar: Wenn schon der freundliche Fall
  scheitert, scheitert der unfreundliche erst recht.
* Kommt etwas durch, heisst das nur: *an den Gates liegt es nicht*. Es heisst
  nicht, dass ein solcher Vorteil existiert.

Und ein Vorbehalt, der beim Messen auffiel und nicht wegzurechnen ist: Das
Gate **Messlatte** vergleicht mit Kaufen-und-Halten ueber die Testfenster, und
die sind drei Monate lang. Ein Regime von 60 Kerzen liegt in derselben
Groessenordnung - dann faellt ein ganzes Fenster in ein einziges Regime, und
der Vergleichsmassstab schwankt staerker als das, was gemessen werden soll
(gesehen: Halten zwischen +1195 % und +5346 % ueber dieselben Fenster). Die
Messlatte-Zeilen dieser Leiter taugen deshalb nicht als Befund. **Die
DSR-Spalte ist davon unberuehrt** - sie kennt keinen Vergleichsmassstab,
sondern nur die Trades der Strategie selbst.

Und das Regime ist fuer alle Beine **dasselbe**. Getrennte Regimes je Markt
waeren geschenkte Unabhaengigkeit - der Deflated Sharpe lebt von genau dieser
Groesse, und Krypto laeuft nun einmal im Gleichschritt.

Das kostet keinen Versuch: Geprueft wird die Strecke, keine Regel. Nichts
davon waehlt einen Kandidaten fuer den Livebetrieb aus.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from research.nullprobe import baue_reihe

#: Mittlere Regimedauer in Kerzen. Der Kandidat haelt eine Position rund
#: 40 Tage; ein Regime, das kuerzer ist als der Haltezeitraum, waere kein
#: Trend, sondern Rauschen mit anderem Namen.
DAUER = 60


def regimefolge(laenge: int, *, dauer: int = DAUER, saat: int = 0) -> np.ndarray:
    """Eine Folge aus +1 und -1, die im Mittel ``dauer`` Kerzen durchhaelt.

    Mittelwertfrei gemacht, und zwar auf der gezogenen Folge selbst: Sonst
    brachte eine Ziehung, die zufaellig mehr Aufwaerts- als Abwaertsregimes
    enthaelt, zusaetzlich einen Drift mit - und der waere ein zweiter, nicht
    beabsichtigter Vorteil. Gepflanzt werden soll **Vorhersagbarkeit**, nicht
    Rendite.
    """
    if laenge <= 0:
        return np.zeros(0)
    rng = np.random.default_rng(saat)
    wechsel = rng.random(laenge) < (1.0 / max(dauer, 1))
    vorzeichen = np.where(rng.random(laenge) < 0.5, -1.0, 1.0)
    folge = np.empty(laenge)
    aktuell = vorzeichen[0]
    for i in range(laenge):
        if wechsel[i]:
            aktuell = -aktuell
        folge[i] = aktuell
    return folge - folge.mean()


def pflanze_trend(
    frame: pd.DataFrame, *, anteil: float, regime: np.ndarray
) -> pd.DataFrame:
    """Einen vorhersagbaren Anteil in die echte Reihe legen.

    ``anteil`` ist der Anteil der **Varianz** der Tagesrenditen, der zum
    Regime gehoert. 0 laesst die Reihe unveraendert, 0,2 heisst: ein Fuenftel
    der taeglichen Schwankung ist ab jetzt ein Trend, der ueber Wochen haelt.

    Die Rechnung in einer Zeile - und der Mittelwert steht mit Absicht
    ausserhalb der Klammer::

        r' = m + sqrt(1-a) * (r - m) + sqrt(a) * sigma * regime

    Damit bleibt **beides** erhalten: die Streuung, weil sich die Varianzen zu
    genau der urspruenglichen addieren, und der Drift, weil nur die
    Abweichungen vom Mittel skaliert werden.

    **Der zweite Teil war im ersten Anlauf falsch.** Dort stand
    ``sqrt(1-a) * r``, also ohne den Mittelwert herauszunehmen - und das
    daempfte den Drift gleich mit: Kaufen-und-Halten fiel bei Anteil 0,5 von
    +1195 % auf +110 %. Jede gepflanzte Stufe war damit zugleich ein
    schwaecherer Markt. Am staerksten traf das ausgerechnet das Gate, das eine
    Mindestrendite verlangt - der gepflanzte Vorteil sah aus, als koste er
    Rendite, obwohl ihn nur meine eigene Rechnung wegskaliert hatte.
    """
    if not 0.0 <= anteil < 1.0:
        raise ValueError(f"Anteil {anteil} liegt nicht in [0, 1).")
    werte = frame.copy().reset_index(drop=True)
    close = werte["close"].to_numpy(dtype=float)
    if len(close) < 3 or anteil == 0.0:
        return werte

    roh = np.diff(np.log(close))
    streuung = float(np.std(roh))
    mittel = float(np.mean(roh))
    schnitt = regime[: len(roh)]
    if len(schnitt) < len(roh) or streuung == 0.0:
        raise ValueError("Regimefolge zu kurz fuer diese Reihe.")

    # **Erst zentrieren, dann normieren - und zwar auf dem Schnitt.**
    # ``regimefolge`` liefert eine mittelwertfreie Folge, der hier benutzte
    # Ausschnitt daraus ist es aber nicht mehr: Eine Reihe mit n Kerzen hat
    # n-1 Renditen, und schon dieses eine fehlende Element verschiebt den
    # Mittelwert. Was blieb, war ein kleiner Drift, den keine Stufe haben
    # sollte - und er faellt genau dort an, wo gemessen wird, ob der Markt
    # unveraendert geblieben ist.
    schnitt = schnitt - schnitt.mean()
    norm = float(np.std(schnitt))
    if norm == 0.0:
        return werte
    schnitt = schnitt / norm

    neu = (
        mittel
        + np.sqrt(1.0 - anteil) * (roh - mittel)
        + np.sqrt(anteil) * streuung * schnitt
    )
    return baue_reihe(werte, neu)


@dataclass(frozen=True, slots=True)
class Stufe:
    """Eine Sprosse der Leiter: gepflanzte Staerke gegen Gate-Ergebnis."""

    anteil: float
    trades: int
    sharpe: float
    sharpe_je_trade: float
    dsr: float | None
    bestanden: int
    gesamt: int
    offen: tuple[str, ...] = ()
    cagr_pct: float = 0.0
    rueckgang_pct: float = 0.0
    meldungen: tuple[tuple[str, str], ...] = ()
    """Die Begruendung je gescheitertem Gate - im Klartext, wie es sie meldet.

    Ohne sie sagt eine Sprosse nur *dass* ein Gate haelt. Bei 'Messlatte' ist
    das zu wenig: Sie prueft zwei Dinge auf einmal - risikobereinigt besser
    als Halten, **und** mindestens 15 % im Jahr. Welche der beiden Haelften
    haelt, aendert die Schlussfolgerung vollstaendig.
    """

    @property
    def voll(self) -> bool:
        return self.gesamt > 0 and self.bestanden == self.gesamt

    @property
    def guete(self) -> float:
        """Qualitaet **und** Menge in einer Zahl: ``SR je Trade * sqrt(Trades)``.

        Das ist im Kern die Groesse, gegen die der Deflated Sharpe seine
        Huerde legt - er fragt nicht nach dem Vorteil je Trade, sondern nach
        dem Vorteil ueber die ganze Stichprobe.

        Sie steht hier, weil die Leiter sonst leicht falsch gelesen wird: Eine
        Sprosse mit fuenffachem Vorteil je Trade sieht nach einem grossen
        Fortschritt aus, und wenn sie dafuer nur ein Achtel so oft handelt,
        ist es keiner.
        """
        return self.sharpe_je_trade * (self.trades**0.5)


@dataclass(slots=True)
class Leiter:
    """Die Stufen und was sie zusammen ueber die Strecke sagen."""

    stufen: list[Stufe] = field(default_factory=list)
    versuche: int = 0

    @property
    def geordnet(self) -> list[Stufe]:
        return sorted(self.stufen, key=lambda s: s.anteil)

    @property
    def erste_volle(self) -> Stufe | None:
        """Die schwaechste gepflanzte Staerke, die alle Gates besteht."""
        return next((s for s in self.geordnet if s.voll), None)

    @property
    def verduennung(self) -> float | None:
        """Wie viel von der Trade-Zahl der untersten Sprosse oben uebrig ist.

        **Der Haken dieses Versuchsaufbaus, und er gehoert nach vorn.** Ein
        gepflanzter Trend, der ueber Wochen haelt, laesst eine Trendfolge
        *weniger* handeln: Sie steigt ein und bleibt drin, statt in Seitwaerts-
        phasen hin- und hergeworfen zu werden. Die Leiter tauscht damit
        Vorteil gegen Stichprobe - und beides geht in den Deflated Sharpe ein,
        in entgegengesetzter Richtung.

        Faellt diese Zahl weit unter 1, misst die Leiter nicht mehr, was sie
        soll, und das muss im Urteil stehen statt in einer Fussnote.
        """
        geordnet = self.geordnet
        if len(geordnet) < 2 or geordnet[0].trades == 0:
            return None
        return geordnet[-1].trades / geordnet[0].trades

    @property
    def hartnaeckigstes(self) -> tuple[str, int] | None:
        """Welches Gate haelt ueber die meisten Stufen stand?

        Die eigentlich brauchbare Zahl dieses Moduls. Sie sagt nicht "es
        klappt nicht", sondern **woran** es nicht klappt - und zwar an einer
        Stelle, an der die Antwort nicht mehr von der Regelfamilie abhaengt.
        """
        zaehler: dict[str, int] = {}
        for stufe in self.stufen:
            for name in stufe.offen:
                zaehler[name] = zaehler.get(name, 0) + 1
        if not zaehler:
            return None
        name = max(zaehler, key=lambda k: (zaehler[k], k))
        return name, zaehler[name]

    def tabelle(self) -> str:
        """Alle Stufen, und die offenen Gates **ungekuerzt**.

        Der erste Anlauf schnitt die Liste bei 46 Zeichen ab. Genau die
        abgeschnittenen Namen waren die Auskunft, um die es hier geht - eine
        Sprosse, die "7 von 11" meldet und drei Gates nennt, verschweigt das
        vierte.
        """
        zeilen = [
            f"{'gepflanzt':>10} {'Trades':>7} {'je Trade':>9} {'Guete':>7} "
            f"{'DSR':>7} {'Gates':>7}  offen"
        ]
        for s in self.geordnet:
            dsr = f"{s.dsr:.3f}" if s.dsr is not None else "   -"
            zeilen.append(
                f"{s.anteil:>9.0%} {s.trades:>7} {s.sharpe_je_trade:>9.4f} "
                f"{s.guete:>7.2f} {dsr:>7} "
                f"{s.bestanden:>3}/{s.gesamt:<3}  {', '.join(s.offen) or '-'}"
            )
        return "\n".join(zeilen)

    def urteil(self) -> str:
        if not self.stufen:
            return "Keine Stufen gemessen - nichts zu sagen."

        voll = self.erste_volle
        if voll is not None:
            return (
                f"**Die Strecke laesst etwas durch.** Bei einem gepflanzten "
                f"Anteil von {voll.anteil:.0%} der Tagesvarianz besteht der "
                f"Kandidat alle {voll.gesamt} Gates - bei {self.versuche} "
                f"gezaehlten Versuchen, also mit der heutigen Huerde. Damit "
                f"ist die Frage beantwortet: An den Gates liegt es nicht. Was "
                f"fehlt, ist ein Vorteil dieser Groesse - nicht eine mildere "
                f"Schwelle."
            )

        staerkste = self.geordnet[-1]
        hart = self.hartnaeckigstes
        woran = ""
        if hart is not None:
            name, wie_oft = hart
            woran = (
                f" Am hartnaeckigsten ist '{name}' - offen auf {wie_oft} von "
                f"{len(self.stufen)} Stufen."
            )
        kopf = (
            f"**Keine Stufe besteht alle Gates**, auch nicht bei "
            f"{staerkste.anteil:.0%} gepflanzter Varianz ({staerkste.bestanden} "
            f"von {staerkste.gesamt}).{woran}"
        )

        # Der Vorbehalt steht **vor** der Schlussfolgerung, nicht dahinter.
        # Wer ihn hinten anhaengt, hat die Aussage schon getroffen.
        duenn = self.verduennung
        if duenn is not None and duenn < 0.5:
            anker = self.geordnet[0]
            return (
                f"{kopf} **Ueber die Strecke sagt das aber nichts - ueber die "
                f"Regelfamilie umso mehr.** Die staerkste Sprosse handelt nur "
                f"noch {duenn:.0%} so oft wie die unterste "
                f"({staerkste.trades} gegen {anker.trades} Trades): Ein Trend, "
                f"der ueber Wochen haelt, laesst eine Trendfolge seltener "
                f"handeln. Der Vorteil je Trade steigt dabei von "
                f"{anker.sharpe_je_trade:.4f} auf "
                f"{staerkste.sharpe_je_trade:.4f} - die Guete, auf die es "
                f"ankommt, aber nur von {anker.guete:.2f} auf "
                f"{staerkste.guete:.2f}. Qualitaet und Menge sind hier "
                f"gekoppelt, und der Deflated Sharpe braucht beide. Das ist "
                f"keine Eigenschaft der geprueften Regeln, sondern der Lage: "
                f"In dieser Historie ist kein Trend so haeufig, dass er "
                f"gleichzeitig gross und oft waere."
            )
        return (
            f"{kopf} Das ist ein Befund ueber die Strecke, nicht ueber die "
            f"Regelfamilie: Wenn schon ein kuenstlich sauberer Trend nicht "
            f"durchkommt, kann kein echter es."
        )
