"""Sagt die Uhrzeit etwas - die eine Quelle, die Tageskerzen nicht kennen.

Warum diese Frage jetzt kommt
-----------------------------
Befund 62 hat gerechnet, dass Fuenfzehnminutenkerzen den Deflated Sharpe
arithmetisch tragen koennen: Bei 10 000 Trades genuegen 0,094 % je Trade. Was
dort fehlt, ist ein Vorteil dieser Groesse.

``cli scan`` hat auf denselben Kerzen gesucht und nichts Stabiles gefunden -
aber er prueft **eine** Art von Signal: Sagt die Richtung der letzten N Kerzen
etwas ueber die naechsten M? Das ist Momentum, in beide Richtungen gelesen.

Die Uhrzeit ist eine andere Quelle, und sie hat eine Eigenschaft, die keine
andere hat: **Auf Tageskerzen ist sie prinzipiell unsichtbar.** Jede
Tageskerze ist ein Tag; es gibt nichts, woran man eine Stunde ablesen koennte.
Wer nur Tageskerzen ausgemessen hat, hat diese Frage nicht beantwortet,
sondern nie gestellt.

Krypto handelt rund um die Uhr, die Liquiditaet nicht: Sie folgt den
Arbeitszeiten in Asien, Europa und Nordamerika.

Warum feste Fenster und nicht alle
----------------------------------
Bei 96 Viertelstunden gaebe es rund 4600 moegliche Zeitfenster. Wer die alle
prueft und das beste nimmt, hat die Zahl seiner Versuche gemessen und sonst
nichts - genau der Fehler, gegen den ``schwelle_fuer`` im Vorteilsscan gebaut
ist, nur eine Ebene tiefer.

Geprueft werden deshalb **vorab festgelegte** Fenster, und sie kommen nicht
aus den Daten, sondern aus der Marktstruktur: die drei Handelssitzungen und
ihre Ueberschneidungen. Dazu die 96 einzelnen Viertelstunden als Landkarte -
mit der Schwelle, die zu 96 Zellen gehoert, nicht mit der fuer eine.

Vier Huerden wie im Vorteilsscan
-------------------------------
1. Auffaellig gegen die Zahl der **geprueften** Zellen, nicht gegen eine.
2. Denselben t-Wert auch gegen eine empirische Nullverteilung
   (``vorzeichenprobe``).
3. In **beiden Haelften** des Zeitraums dasselbe Vorzeichen.
4. Nach Gebuehren etwas uebrig.

Die zweite kam mit Befund 277 dazu, als Antwort auf Befund 276: Dort hat sich
die Latte aus ``schwelle_fuer`` als zu niedrig erwiesen, weil sie eine
Normalverteilung unterstellt, die die Daten nicht haben. Dieselbe Latte steht
hier - also gehoert sie hier genauso geprueft.

**Aber nicht mit derselben Probe.** Im Vorteilsscan wird der Teiler zeitlich
verschoben; das setzt einen Teiler voraus, der stehenbleiben kann. Hier gibt
es keinen: ``messe`` vergleicht **gepaart je Tag**, innen gegen aussen am
selben Tag, und beide Zustaende stehen jeden Tag nebeneinander. Was hier
zufaellig sein soll, ist nicht die Zuordnung, sondern die **Richtung** - also
wird sie gewuerfelt. Die Betraege bleiben unangetastet, mit ihren dicken
Raendern und allem, was sonst in ihnen steckt.

Gemessen (277): Die Latte haelt hier. Die empirische Nullverteilung legt ihr
99. Perzentil auf 2,56 bis 2,59, die Normalverteilung auf 2,576 - und die
Tagesunterschiede haengen kaum zusammen (Autokorrelation -0,12 bis +0,01).
Der Unterschied zum Vorteilsscan ist die Bauart, nicht das Glueck: 2350
gepaarte Tagesunterschiede statt 585 Beobachtungen in sechzehn Bloecken.

Kostet keinen Versuch: Geprueft wird die Struktur der Daten, keine handelbare
Regel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.vorteilsscan import KOSTEN_MAKER_MAKER, schwelle_fuer

#: Wie viele Tage ein Fenster mindestens abdecken muss.
MIND_TAGE = 200

#: Die Handelssitzungen in UTC - **aus der Marktstruktur, nicht aus den Daten**.
#:
#: Tokio 00-06, London 07-16, New York 13-21 (Sommerzeit gemittelt). Dazu die
#: beiden Ueberschneidungen, an denen erfahrungsgemaess das meiste Volumen
#: liegt, und die ruhige Spanne dazwischen. Sieben Fenster, festgelegt bevor
#: eine Zahl gerechnet wurde.
SITZUNGEN: tuple[tuple[str, int, int], ...] = (
    ("Asien", 0, 6),
    ("Europa", 7, 16),
    ("Nordamerika", 13, 21),
    ("Asien/Europa", 6, 8),
    ("Europa/Amerika", 13, 16),
    ("Abend", 21, 24),
    ("Nacht", 22, 2),
)


@dataclass(frozen=True, slots=True)
class Fenster:
    """Ein Zeitfenster und was es im Mittel gebracht hat."""

    name: str
    von: int
    bis: int
    tage: int
    spanne_pct: float
    """Rendite im Fenster minus Rendite ausserhalb, in Prozent je Tag."""

    t_wert: float

    def netto_pct(self, kosten: float = KOSTEN_MAKER_MAKER) -> float:
        """Was nach Gebuehren bleibt.

        **Anders als beim Momentum-Scan die ganze Spanne, nicht die halbe.**
        Dort ist die Spanne der Unterschied zwischen zwei Zustaenden, von
        denen eine Regel nur einen handelt. Hier ist sie der Unterschied
        zwischen "im Fenster investiert" und "nicht investiert" - und genau
        das laesst sich handeln.
        """
        return abs(self.spanne_pct) - kosten

    def ueber_schwelle(self, schwelle: float) -> bool:
        return abs(self.t_wert) >= schwelle

    @property
    def stunden(self) -> float:
        laenge = (self.bis - self.von) % 24
        return float(laenge or 24)


def _im_fenster(stunden: np.ndarray, von: int, bis: int) -> np.ndarray:
    """Maske fuer ein Fenster - auch wenn es ueber Mitternacht laeuft."""
    if von <= bis:
        return (stunden >= von) & (stunden < bis)
    return (stunden >= von) | (stunden < bis)


@dataclass(frozen=True, slots=True)
class Tagesreihe:
    """Je Tag ein Unterschied - das Zwischenergebnis hinter jedem Fenster.

    ``messe`` rechnet daraus den t-Wert, ``vorzeichenprobe`` wuerfelt darauf
    die Richtungen neu. Beide arbeiten auf **derselben** Reihe; wuerde die
    Probe sie sich selbst zusammenbauen, pruefte sie am Ende ein anderes
    Fenster als das, ueber das geurteilt wird (dieselbe Trennung wie ``paar``
    im Vorteilsscan, Befund 276).
    """

    unterschied: np.ndarray
    """Rendite je Kerze innen minus aussen, je Tag ein Wert."""

    kerzen_im_fenster: float

    @property
    def autokorrelation(self) -> float:
        """Wie stark ein Tag dem naechsten aehnelt - Verzoegerung eins.

        Die Vorzeichenprobe setzt voraus, dass die Tage austauschbar sind.
        Diese Zahl sagt, wie weit davon entfernt sie stehen, und sie wird
        **berichtet und nicht verrechnet**: Eine AR(1)-Korrektur waere ein
        Modell, und dieses Projekt misst lieber.
        """
        werte = self.unterschied - np.mean(self.unterschied)
        nenner = float(np.dot(werte, werte))
        if nenner == 0 or len(werte) < 2:
            return 0.0
        return float(np.dot(werte[:-1], werte[1:]) / nenner)


def tagesreihe(frame: pd.DataFrame, von: int, bis: int) -> Tagesreihe | None:
    """Die gepaarten Tagesunterschiede eines Fensters - siehe ``Tagesreihe``."""
    if len(frame) < 2:
        return None
    zeiten = pd.to_datetime(frame["open_time"])
    close = frame["close"].to_numpy(dtype=float)
    rendite = np.diff(np.log(close)) * 100
    stunden = zeiten.dt.hour.to_numpy()[1:]
    tage = zeiten.dt.floor("D").to_numpy()[1:]

    drin = _im_fenster(stunden, von, bis)
    if not drin.any() or drin.all():
        return None

    tabelle = pd.DataFrame({"tag": tage, "rendite": rendite, "drin": drin})
    je_tag = tabelle.groupby(["tag", "drin"])["rendite"].mean().unstack()
    je_tag = je_tag.dropna()
    if True not in je_tag or False not in je_tag or len(je_tag) < MIND_TAGE:
        return None

    innen = je_tag[True].to_numpy(dtype=float)
    aussen = je_tag[False].to_numpy(dtype=float)
    return Tagesreihe(
        unterschied=innen - aussen,
        kerzen_im_fenster=float(tabelle.groupby("tag")["drin"].sum().mean()),
    )


def messe(frame: pd.DataFrame, *, name: str, von: int, bis: int) -> Fenster | None:
    """Rendite **je Kerze** im Fenster gegen die ausserhalb, je Tag verglichen.

    Zwei Fallen stecken hier, und in beide bin ich zuerst hineingelaufen.

    **Je Kerze und nicht als Summe.** Der erste Anlauf verglich die Summe im
    Fenster mit der Summe ausserhalb - also eine Stunde gegen dreiundzwanzig.
    Die Differenz misst dann ueberwiegend die Fensterlaenge; ein gepflanzter
    Effekt bei 14 Uhr wurde prompt nicht gefunden, dafuer ein erfundener bei
    21 Uhr. Verglichen wird deshalb der Durchschnitt je Kerze.

    **Gegen das Aussen und nicht gegen null.** Wer die Fensterrendite gegen
    null prueft, misst bei einem Markt, der sich vervielfacht hat, vor allem
    den Grundtrend. Genau davor warnt der Kopf von ``vorteilsscan``. Beide
    Seiten tragen ihn, also faellt er in der Differenz heraus.

    Und je Tag ein Wertepaar: Innerhalb eines Tages sind die Viertelstunden
    nicht unabhaengig; wer sie einzeln zaehlt, bekommt einen t-Wert, der um
    rund Wurzel(96) zu gross ist.
    """
    reihe = tagesreihe(frame, von, bis)
    if reihe is None:
        return None

    # Je Tag gepaart: Derselbe Tag traegt denselben Marktzustand, und ein
    # gepaarter Vergleich raeumt ihn heraus statt ihn als Streuung mitzunehmen.
    je_kerze = float(np.mean(reihe.unterschied))
    return Fenster(
        name=name,
        von=von,
        bis=bis,
        tage=len(reihe.unterschied),
        spanne_pct=je_kerze * reihe.kerzen_im_fenster,
        t_wert=t_wert(reihe.unterschied),
    )


def t_wert(unterschied: np.ndarray) -> float:
    """Der gepaarte t-Wert einer Tagesreihe - an **einer** Stelle.

    Die Vorzeichenprobe rechnet ihn zwanzigtausendmal nach. Stuende die
    Formel zweimal da, koennten die beiden auseinanderlaufen, und die Probe
    pruefte dann etwas anderes als das Urteil.
    """
    fehler = float(np.std(unterschied, ddof=1) / np.sqrt(len(unterschied)))
    return float(np.mean(unterschied)) / fehler if fehler > 0 else 0.0


def scanne_sitzungen(frame: pd.DataFrame) -> list[Fenster]:
    gefunden = [
        messe(frame, name=name, von=von, bis=bis) for name, von, bis in SITZUNGEN
    ]
    return sorted(
        (f for f in gefunden if f is not None), key=lambda f: -abs(f.t_wert)
    )


def scanne_stunden(frame: pd.DataFrame) -> list[Fenster]:
    """Die 24 Einzelstunden als Landkarte - mit der Schwelle fuer 24 Zellen."""
    gefunden = [
        messe(frame, name=f"{stunde:02d} Uhr", von=stunde, bis=(stunde + 1) % 24)
        for stunde in range(24)
    ]
    return sorted(
        (f for f in gefunden if f is not None), key=lambda f: -abs(f.t_wert)
    )


@dataclass(frozen=True, slots=True)
class Stabilitaet:
    """Haelt ein Fenster in beiden Haelften des Zeitraums?"""

    erste: Fenster | None
    zweite: Fenster | None

    @property
    def haelt(self) -> bool:
        if self.erste is None or self.zweite is None:
            return False
        gleich = (self.erste.spanne_pct > 0) == (self.zweite.spanne_pct > 0)
        return gleich and abs(self.erste.t_wert) >= 2 and abs(self.zweite.t_wert) >= 2

    def beschreibe(self) -> str:
        if self.erste is None or self.zweite is None:
            return "Zu wenig Daten fuer eine Haelfte."
        lage = "stabil" if self.haelt else "nicht stabil"
        return (
            f"{lage}: erste Haelfte t = {self.erste.t_wert:+.2f}, "
            f"zweite t = {self.zweite.t_wert:+.2f}"
        )


def pruefe_stabilitaet(frame: pd.DataFrame, fenster: Fenster) -> Stabilitaet:
    mitte = len(frame) // 2
    return Stabilitaet(
        erste=messe(
            frame.iloc[:mitte], name=fenster.name, von=fenster.von, bis=fenster.bis
        ),
        zweite=messe(
            frame.iloc[mitte:], name=fenster.name, von=fenster.von, bis=fenster.bis
        ),
    )


#: Wie viele Vorzeichenmuster gewuerfelt werden.
#:
#: **Gemessen und nicht gegriffen** (Befund 277): Bei 5.000 Zuegen schwankte
#: der Anteil desselben Fensters ueber fuenf Saaten zwischen 0,16 % und
#: 0,42 % - die geforderte Schranke lag bei 0,161 %, eine Saat haette das
#: Urteil also gedreht. Bei 20.000 liegen dieselben fuenf Saaten zwischen
#: 0,245 % und 0,335 %, alle auf derselben Seite.
ZUEGE = 20_000

#: Feste Saat. Eine Probe, deren Ergebnis vom Tag abhaengt, ist keine.
SAAT = 277


def normal_99() -> float:
    """Das 99. Perzentil von |t| unter der Normalverteilung - 2,576.

    Gerechnet statt hingeschrieben: Es ist genau die Verteilung, mit der
    ``schwelle_fuer`` arbeitet, und der Vergleichswert fuer
    ``Vorzeichenprobe.perzentil_99``. Zwei Stellen, an denen dieselbe Zahl
    steht, laufen frueher oder spaeter auseinander.
    """
    from statistics import NormalDist

    return float(NormalDist().inv_cdf(0.995))


@dataclass(frozen=True, slots=True)
class Vorzeichenprobe:
    """Wie oft erzeugt die blosse Streuung der Tage diesen t-Wert?

    Das gepaarte Gegenstueck zur ``rotationsprobe`` des Vorteilsscans. Dort
    wird der Teiler verschoben, hier wird die **Richtung** jedes
    Tagesunterschieds neu gewuerfelt: Unter der Nullhypothese ist sie
    beliebig, der Betrag nicht. Die Betraege bleiben deshalb, wie sie sind -
    mit ihren dicken Raendern, die genau das sind, was eine Normalverteilung
    nicht kennt.
    """

    beobachtet: float
    haeufiger: int
    zuege: int
    autokorrelation: float

    perzentil_99: float
    """Das 99. Perzentil der gewuerfelten |t| - die **Eichung der Latte**.

    Die Zahl, an der Befund 277 haengt: ``schwelle_fuer`` rechnet mit einer
    Normalverteilung, deren 99. Perzentil bei 2,576 liegt. Steht die
    gewuerfelte daneben, ist die Latte richtig geeicht; steht sie darueber,
    ist sie zu niedrig - so wie im Vorteilsscan (Befund 276).
    """

    @property
    def anteil(self) -> float:
        return self.haeufiger / self.zuege if self.zuege else 1.0

    @property
    def streuung(self) -> float:
        """Wie genau der Anteil ueberhaupt bestimmt ist.

        Gewuerfelt heisst geschaetzt, und eine Schaetzung ohne ihren
        Fehlerbalken sieht genauer aus, als sie ist.
        """
        p = self.anteil
        return float(np.sqrt(p * (1 - p) / self.zuege)) if self.zuege else 1.0

    def traegt(self, noetig: float) -> bool:
        return self.anteil <= noetig

    def knapp(self, noetig: float) -> bool:
        """Liegt das Urteil innerhalb von zwei Fehlerbalken an der Kante?

        Dann haette eine andere Saat es drehen koennen, und das gehoert
        dazugesagt statt verschwiegen.
        """
        return abs(self.anteil - noetig) < 2 * self.streuung

    def beschreibe(self, noetig: float) -> str:
        satz = (
            f"{self.haeufiger} von {self.zuege} gewuerfelten Richtungen "
            f"erreichen ihn ({self.anteil:.3%} +/- {self.streuung:.3%}), "
            f"noetig waeren {noetig:.3%}; die Tagesunterschiede haengen mit "
            f"{self.autokorrelation:+.3f} zusammen"
        )
        if self.knapp(noetig):
            satz += (
                ". **Knapp**: Der Abstand zur Schranke ist kleiner als zwei "
                "Fehlerbalken, eine andere Saat koennte das Urteil drehen"
            )
        return satz


def vorzeichenprobe(
    reihe: Tagesreihe, *, zuege: int = ZUEGE, saat: int = SAAT
) -> Vorzeichenprobe:
    """Dieselbe Reihe mit gewuerfelten Richtungen - ``zuege`` mal.

    Anders als die Verschiebungsprobe im Vorteilsscan ist diese hier nicht
    erschoepfend: Bei 2350 Tagen gibt es 2^2350 Vorzeichenmuster. Dafuer ist
    sie fein genug - die Aufloesung haengt an ``zuege`` und nicht an der Zahl
    der Beobachtungen, und damit reicht sie bis unter die Schranke, was die
    Verschiebungsprobe auf ihren Stichproben nicht schafft.
    """
    unterschied = np.asarray(reihe.unterschied, dtype=float)
    n = len(unterschied)
    beobachtet = abs(t_wert(unterschied))
    rng = np.random.default_rng(saat)

    # In Stuecken, damit der Speicher nicht an der Zahl der Zuege haengt:
    # 20.000 mal 2350 Werte waeren 376 MB auf einmal. Die Grenze ist ein
    # Speicherbudget von rund zwei Millionen Zahlen, kein gegriffener Wert.
    stueck = max(1, 2_000_000 // max(1, n))
    gewuerfelt = np.empty(zuege)
    gezogen = 0
    while gezogen < zuege:
        jetzt = min(stueck, zuege - gezogen)
        gespiegelt = rng.choice([-1.0, 1.0], size=(jetzt, n)) * unterschied
        mittel = gespiegelt.mean(axis=1)
        fehler = gespiegelt.std(axis=1, ddof=1) / np.sqrt(n)
        werte = np.zeros(jetzt)
        np.divide(np.abs(mittel), fehler, out=werte, where=fehler > 0)
        gewuerfelt[gezogen : gezogen + jetzt] = werte
        gezogen += jetzt

    return Vorzeichenprobe(
        beobachtet=beobachtet,
        haeufiger=int(np.sum(gewuerfelt >= beobachtet)),
        zuege=zuege,
        autokorrelation=reihe.autokorrelation,
        perzentil_99=float(np.percentile(gewuerfelt, 99)),
    )


def urteil(
    bestes: Fenster | None,
    stabil: Stabilitaet | None,
    *,
    geprueft: int,
    kosten: float = KOSTEN_MAKER_MAKER,
    probe: Vorzeichenprobe | None = None,
) -> str:
    """Alle vier Huerden in einem Satz - und die gerissene zuerst.

    ``probe`` steht direkt hinter der Schwelle, weil sie dieselbe Zahl in
    Frage stellt: Haelt sie nicht, war schon der Schwellenvergleich keiner
    (Befund 276/277).
    """
    if bestes is None:
        return "Kein Fenster mit genug Tagen - nichts zu beurteilen."

    schwelle = schwelle_fuer(geprueft)
    if not bestes.ueber_schwelle(schwelle):
        return (
            f"Nicht auffaellig genug (t = {bestes.t_wert:+.2f}). Bei "
            f"{geprueft} geprueften Fenstern liegt die Schwelle bei "
            f"{schwelle:.2f}, nicht bei 2.00. Hier Versuche auszugeben, hiesse "
            f"die Huerde zu heben, ohne etwas zu holen."
        )
    noetig = 0.05 / geprueft
    if probe is not None and not probe.traegt(noetig):
        return (
            f"Ueber der Schwelle (t = {bestes.t_wert:+.2f}), aber die "
            f"Vorzeichenprobe traegt ihn nicht: {probe.beschreibe(noetig)}."
        )
    if stabil is not None and not stabil.haelt:
        return (
            f"Auffaellig (t = {bestes.t_wert:+.2f}), aber {stabil.beschreibe()}. "
            f"Ein Vorteil, den es nur in einer Haelfte gab, steht morgen nicht "
            f"zur Verfuegung."
        )
    netto = bestes.netto_pct(kosten)
    if netto <= 0:
        return (
            f"Auffaellig und stabil, aber nach Gebuehren bleibt nichts: "
            f"{abs(bestes.spanne_pct):.4f} % je Tag gegen {kosten:.2f} % "
            f"Kosten je Roundtrip."
        )
    gehalten = "vier" if probe is not None else "drei"
    geprueft_satz = f" {probe.beschreibe(noetig)}." if probe is not None else ""
    return (
        f"**Fund: '{bestes.name}' ({bestes.von:02d}-{bestes.bis:02d} UTC).** "
        f"t = {bestes.t_wert:+.2f} ueber {bestes.tage} Tage, "
        f"{bestes.spanne_pct:+.4f} % je Tag, nach Gebuehren {netto:+.4f} %."
        f"{geprueft_satz} "
        f"Alle {gehalten} Huerden gehalten - das ist der Punkt, an dem sich "
        f"Versuche lohnen."
    )
