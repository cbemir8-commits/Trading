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

#: Mittlere Regimedauer in Kerzen.
#:
#: Hier stand "der Kandidat haelt eine Position rund 40 Tage". Gemessen
#: (Befund 177) sind es **im Median 3 Tage und im Mittel 14,2** - die 40 war
#: eher die Obergrenze als der Regelfall. Die Begruendung traegt trotzdem, und
#: zwar deutlicher: Ein Regime von 60 Kerzen ist um ein Vielfaches laenger als
#: der Haltezeitraum, also ein Trend und nicht Rauschen mit anderem Namen.
DAUER = 60

#: Ab welcher Steigung die Guete als "waechst mit dem Vorteil" gilt.
#:
#: **Vor der Messung festgelegt, und zwar aus der Sache heraus**: Die Guete
#: des Kandidaten liegt bei 3,19, noetig waeren rund 3,6. Wer ueber die volle
#: Reglerspanne nicht wenigstens diesen halben Punkt gutmacht, hat keinen Weg
#: zum Ziel gefunden, sondern Rauschen. Eine nachtraeglich gewaehlte Schranke
#: waere hier wertlos - man findet immer eine, unter der etwas gut aussieht.
MINDESTSTEIGUNG = 0.5


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

    schiefe: float | None = None
    woelbung: float | None = None
    """Die Verteilungsform dieser Sprosse - fuer ihre eigene Latte.

    Ein gepflanzter Trend verschiebt die Form, und die Latte haengt daran.
    Ohne diese Felder stand auf jeder Sprosse die Latte des Bestands, obwohl
    die Leiter die Form absichtlich veraendert (Befund 193).
    """

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

    tage_im_markt: int | None = None
    """Summe der Haltedauern - die Groesse, die den Verfall wirklich erklaert.

    Befund 176 hat den Verfall der Stichprobe der **Haltedauer** zugeschrieben
    ("haelt laenger, handelt seltener"). Befund 177 hat nachgemessen: Die
    Haltedauer bleibt flach (Median 3 -> 4 -> 4 -> 2 Tage), was einbricht,
    sind die **Einstiege** - 158 auf 16, und die Zeit im Markt von 34,1 % auf
    2,8 %.

    Ohne diese Spalte liest man aus fallenden Trades das Falsche heraus, und
    ich habe genau das getan.
    """

    effektiv: int | None = None
    """Die **effektive** Stichprobe - die Zahl, gegen die das Gate urteilt.

    Bis Befund 176 gab es dieses Feld nicht, und ``guete`` rechnete mit der
    rohen Trade-Zahl. Das ist genau der Fehler, den Befund 139 an fuenf von
    sechs Stellen behoben hat; diese sechste ist durchgerutscht, ausgerechnet
    in dem Modul, das die folgenreichste Frage des Projekts beantwortet.

    Der Betrag: Bei 160 rohen und 107 effektiven Trades ist die rohe Guete um
    den Faktor ``sqrt(160/107) = 1,22`` zu gross - 22 % zu freundlich.
    """

    @property
    def guete(self) -> float:
        """Qualitaet **und** Menge in einer Zahl: ``SR je Trade * sqrt(n_eff)``.

        Das ist die Groesse, gegen die der Deflated Sharpe seine Huerde legt -
        er fragt nicht nach dem Vorteil je Trade, sondern nach dem Vorteil
        ueber die ganze Stichprobe, **und zwar ueber die effektive**.

        Sie steht hier, weil die Leiter sonst leicht falsch gelesen wird: Eine
        Sprosse mit fuenffachem Vorteil je Trade sieht nach einem grossen
        Fortschritt aus, und wenn sie dafuer nur ein Achtel so oft handelt,
        ist es keiner.
        """
        if self.effektiv is None:
            raise ValueError(
                "Ohne effektive Stichprobe gibt es keine Guete. Die rohe "
                "Trade-Zahl einzusetzen macht sie zu gross - siehe Befund "
                "139 und 176."
            )
        return self.sharpe_je_trade * (self.effektiv**0.5)

    def noetig(self, versuche: int) -> float | None:
        """Welche Guete die Schwelle bei dieser Stichprobe verlangt.

        **Der bewegliche Teil der Leiter.** Ein gepflanzter Trend hebt den
        Vorteil je Trade und senkt zugleich die Trade-Zahl - und mit ihr
        steigt die Latte. Ohne diese Spalte liest sich die Leiter, als muesse
        nur die Guete wachsen.
        """
        from research.verbund import noetige_guete

        if self.effektiv is None:
            return None
        # Mit den Momenten **dieser** Sprosse (Befund 193). Ein gepflanzter
        # Trend aendert die Verteilungsform, und die Latte haengt daran -
        # gerade auf einer Leiter, die die Form absichtlich verschiebt, waere
        # eine feste Vorgabe die falsche Wahl.
        return noetige_guete(
            self.effektiv, versuche, schiefe=self.schiefe, woelbung=self.woelbung
        )


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
    def steigung(self) -> float | None:
        """Wie stark die Guete waechst, wenn man Vorteil hinzupflanzt.

        Ausgedrueckt als Zuwachs je voll gepflanzter Varianz, also ueber die
        ganze Spanne des Reglers. Eine Leiter, auf der ein echter Vorteil
        ankommt, hat hier eine klar positive Zahl - eine, auf der Qualitaet
        und Menge sich gegenseitig auffressen, eine Zahl um Null.
        """
        geordnet = self.geordnet
        if len(geordnet) < 2:
            return None
        x = np.array([s.anteil for s in geordnet], dtype=float)
        y = np.array([s.guete for s in geordnet], dtype=float)
        if float(np.ptp(x)) == 0.0:
            return None
        return float(np.polyfit(x, y, 1)[0])

    @property
    def entkoppelt(self) -> bool:
        """Ist die Kopplung aus Befund 54 hier gebrochen?

        **Das Kriterium steht vor der Messung fest**, und es hat zwei Teile,
        weil eines allein sich immer erfuellen laesst:

        * Die Guete muss mit der gepflanzten Staerke **steigen** - und zwar
          spuerbar, nicht im Rauschen.
        * Die Stichprobe darf dabei nicht wegbrechen: Wer den Vorteil mit der
          Haelfte der Trades erkauft, hat nichts entkoppelt, sondern nur die
          Kopplung anders herum durchlaufen.
        """
        steig = self.steigung
        duenn = self.verduennung
        return (
            steig is not None
            and steig >= MINDESTSTEIGUNG
            and duenn is not None
            and duenn >= 0.5
        )

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
            f"{'gepflanzt':>10} {'Trades':>7} {'im Markt':>9} {'n_eff':>6} "
            f"{'je Trade':>9} {'Guete':>7} {'noetig':>7} {'DSR':>7} "
            f"{'Gates':>7}  offen"
        ]
        for s in self.geordnet:
            dsr = f"{s.dsr:.3f}" if s.dsr is not None else "   -"
            noetig = s.noetig(self.versuche)
            zeilen.append(
                f"{s.anteil:>9.0%} {s.trades:>7} "
                f"{'-' if s.tage_im_markt is None else s.tage_im_markt:>9} "
                f"{'-' if s.effektiv is None else s.effektiv:>6} "
                f"{s.sharpe_je_trade:>9.4f} {s.guete:>7.2f} "
                f"{'-' if noetig is None else f'{noetig:.2f}':>7} {dsr:>7} "
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


@dataclass(slots=True)
class Vergleich:
    """Mehrere Varianten auf **derselben** gepflanzten Reihe.

    Warum das eine eigene Klasse ist: Der Vergleich lebt davon, dass alle
    Varianten dieselbe Regime-Folge sehen. Wer sie nacheinander mit
    verschiedenen Ziehungen misst, vergleicht Ziehungen und haelt den
    Unterschied fuer Wirkung.
    """

    leitern: dict[str, Leiter] = field(default_factory=dict)

    def matrix(self) -> str:
        """Die Guete je Variante und Stufe - die Zahl, um die es geht."""
        if not self.leitern:
            return "Nichts zu vergleichen."
        namen = list(self.leitern)
        anteile = sorted({s.anteil for lt in self.leitern.values() for s in lt.stufen})
        # **Gekuerzt wird nur die Ueberschrift, nicht der Name.** Bis Befund
        # 178 schnitt der Aufrufer (``cli._familie``) auf 14 Zeichen, damit es
        # in die Spalte passte - und die gekuerzte Fassung war danach der
        # Schluessel, unter dem das Urteil die Variante nannte
        # ("**Neues Hoch im ** raeumt die Latte"). Wer hier kuerzt, kuerzt
        # eine Beschriftung; wer dort kuerzte, kuerzte eine Identitaet.
        breite = 20
        kurz = {n: n if len(n) <= breite - 2 else n[: breite - 4] + ".." for n in namen}

        kopf = f"{'gepflanzt':>10}" + "".join(f"{kurz[n]:>{breite}}" for n in namen)
        zeilen = [kopf, "-" * len(kopf)]
        for anteil in anteile:
            # Zehn wie im Kopf und in der Steigungszeile. Bis Befund 178
            # standen hier neun, und die Zahlenspalten lagen um ein Zeichen
            # gegen ihre Ueberschrift versetzt.
            zeile = f"{anteil:>10.0%}"
            for name in namen:
                treffer = next(
                    (s for s in self.leitern[name].stufen if s.anteil == anteil), None
                )
                if treffer is None:
                    zeile += f"{'-':>{breite}}"
                    continue
                noetig = treffer.noetig(self.leitern[name].versuche)
                marke = "*" if noetig is not None and treffer.guete >= noetig else " "
                zelle = (
                    f"{treffer.guete:>7.2f}/"
                    + ("    -" if noetig is None else f"{noetig:>5.2f}")
                    + f"{marke}({treffer.trades:>3})"
                )
                zeile += f"{zelle:>{breite}}"
            zeilen.append(zeile)

        zeilen.append("-" * len(kopf))
        steig = f"{'Steigung':>10}"
        for name in namen:
            wert = self.leitern[name].steigung
            steig += (
                f"{wert:>{breite}.2f}" if wert is not None else f"{'-':>{breite}}"
            )
        zeilen.append(steig)
        zeilen.append("[Guete/noetig, * = geraeumt, in Klammern die Trades]")
        gekuerzt = [n for n in namen if kurz[n] != n]
        if gekuerzt:
            zeilen.append(
                "[Spalten: " + "; ".join(f"{kurz[n]} = {n}" for n in gekuerzt) + "]"
            )
        return "\n".join(zeilen)

    @property
    def raeumen(self) -> dict[str, list[float]]:
        """Welche Variante ihre Latte **erreicht** - und auf welchen Sprossen.

        Die Matrix zeigte bis Befund 178 nur die Guete. Damit laesst sich
        ablesen, welche Variante die groesste hat, aber nicht, ob sie
        genuegt - und genau das ist die Frage. Die Latte bewegt sich mit der
        Stichprobe (Befund 176); eine groessere Guete bei kleinerer
        Stichprobe kann weiter von ihr weg sein als eine kleinere bei
        grosser.
        """
        gefunden: dict[str, list[float]] = {}
        for name, leiter in self.leitern.items():
            treffer = [
                s.anteil
                for s in leiter.stufen
                if s.effektiv is not None
                and (n := s.noetig(leiter.versuche)) is not None
                and s.guete >= n
            ]
            if treffer:
                gefunden[name] = sorted(treffer)
        return gefunden

    def urteil(self) -> str:
        if not self.leitern:
            return "Nichts zu vergleichen."
        geraeumt = self.raeumen
        gebrochen = [n for n, lt in self.leitern.items() if lt.entkoppelt]
        if geraeumt:
            teile = [
                f"**{name}** raeumt die Latte bei "
                + ", ".join(f"{a:.0%}" for a in sprossen)
                for name, sprossen in geraeumt.items()
            ]
            kopf = (
                "**Eine Variante erreicht ihre Latte.**"
                if len(geraeumt) == 1
                else f"**{len(geraeumt)} Varianten erreichen ihre Latte.**"
            )
            return (
                f"{kopf} "
                + "; ".join(teile)
                + ". Das ist mehr als eine gebrochene Kopplung: Die Guete "
                "genuegt dort, statt nur zu wachsen. Gemessen ist das auf "
                "gepflanzten Reihen; auf echten Daten kostet es Versuche, und "
                "erst dort entscheidet sich, ob davon etwas uebrig bleibt."
            )
        if gebrochen:
            return (
                f"**Die Kopplung bricht bei: {', '.join(gebrochen)}.** Dort "
                f"steigt die Guete mit dem gepflanzten Vorteil um mindestens "
                f"{MINDESTSTEIGUNG:.1f} ueber die Reglerspanne, ohne dass die "
                f"Stichprobe wegbricht. Das ist eine Richtung, die zu pruefen "
                f"sich lohnt - und zwar auf echten Daten, wo sie Versuche "
                f"kostet."
            )
        name, beste = max(
            self.leitern.items(),
            key=lambda kv: kv[1].steigung if kv[1].steigung is not None else -99,
        )
        wert = beste.steigung
        duenn = beste.verduennung

        # **Welche Haelfte des Kriteriums gerissen ist, gehoert in den Satz.**
        # Der erste Anlauf meldete "Steigung 1,15 gegen die geforderten 0,5"
        # und im selben Atemzug "keine Variante entkoppelt" - das liest sich
        # wie ein Widerspruch und verschweigt den eigentlichen Grund: Die
        # Steigung war erfuellt, die Stichprobe war weggebrochen.
        if wert is not None and wert >= MINDESTSTEIGUNG:
            rest = (
                f"bei {duenn:.0%} der Trades der untersten Sprosse"
                if duenn is not None
                else "bei wegbrechender Stichprobe"
            )
            return (
                f"**Keine Variante entkoppelt.** '{name}' erreicht zwar eine "
                f"Steigung von {wert:.2f} und damit die geforderten "
                f"{MINDESTSTEIGUNG:.1f} - aber {rest}. Der Vorteil ist also "
                f"nicht hinzugekommen, sondern nur anders verteilt: dieselbe "
                f"Kopplung, von der anderen Seite durchlaufen."
            )
        return (
            f"**Keine Variante entkoppelt.** Die beste ist '{name}' mit einer "
            f"Steigung von {wert:.2f} gegen die geforderten "
            f"{MINDESTSTEIGUNG:.1f}. Ein gedeckelter Ausstieg loest die "
            f"Kopplung also nicht: Der gepflanzte Vorteil kommt auch dann "
            f"nicht in der Groesse an, gegen die der Deflated Sharpe prueft."
        )
