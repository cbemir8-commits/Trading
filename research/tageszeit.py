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

Dieselben drei Huerden wie im Vorteilsscan
------------------------------------------
1. Auffaellig gegen die Zahl der **geprueften** Zellen, nicht gegen eine.
2. In **beiden Haelften** des Zeitraums dasselbe Vorzeichen.
3. Nach Gebuehren etwas uebrig.

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

    kerzen_im_fenster = float(tabelle.groupby("tag")["drin"].sum().mean())
    innen = je_tag[True].to_numpy(dtype=float)
    aussen = je_tag[False].to_numpy(dtype=float)

    # Je Tag gepaart: Derselbe Tag traegt denselben Marktzustand, und ein
    # gepaarter Vergleich raeumt ihn heraus statt ihn als Streuung mitzunehmen.
    unterschied = innen - aussen
    je_kerze = float(np.mean(unterschied))
    fehler = float(np.std(unterschied, ddof=1) / np.sqrt(len(unterschied)))
    return Fenster(
        name=name,
        von=von,
        bis=bis,
        tage=len(je_tag),
        spanne_pct=je_kerze * kerzen_im_fenster,
        t_wert=je_kerze / fehler if fehler > 0 else 0.0,
    )


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


def urteil(
    bestes: Fenster | None,
    stabil: Stabilitaet | None,
    *,
    geprueft: int,
    kosten: float = KOSTEN_MAKER_MAKER,
) -> str:
    """Alle drei Huerden in einem Satz - und die gerissene zuerst."""
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
    return (
        f"**Fund: '{bestes.name}' ({bestes.von:02d}-{bestes.bis:02d} UTC).** "
        f"t = {bestes.t_wert:+.2f} ueber {bestes.tage} Tage, "
        f"{bestes.spanne_pct:+.4f} % je Tag, nach Gebuehren {netto:+.4f} %. "
        f"Alle drei Huerden gehalten - das ist der Punkt, an dem sich Versuche "
        f"lohnen."
    )
