"""Steckt in einer Zeitreihe ueberhaupt ein Vorteil - bevor eine Regel gebaut wird?

**Warum das der wichtigste Schritt vor jeder Suche ist.**

Jede gepruefte Hypothese hebt die Huerde des Deflated-Sharpe-Gates, und zwar
dauerhaft (siehe ``research/erreichbarkeit.py``). Beim aktuellen Stand kostet
jeder Versuch 0,0017 DSR-Punkte; zwanzig Einfaelle kosten mehr, als eine
Verbesserung um 3 % je Trade einbringt.

Dieser Scan kostet **keinen Versuch**, weil er keine handelbare Regel prueft,
sondern die Struktur des Marktes: Sagt die Vergangenheit etwas ueber die
Zukunft, und ist das mehr als die Gebuehren? Erst wenn hier etwas steht, lohnt
es, Versuche auszugeben.

**Benchmarkfrei.** Gemessen wird die Differenz zwischen "Rueckblick positiv"
und "Rueckblick negativ", nicht die bedingte Rendite selbst. Der erste Anlauf
mass Letzteres und fand ueberall grosse Zahlen - bei einem Markt, der sich
vervielfacht hat, ist das ueberwiegend der Grundtrend und kein Vorteil. Die
Spanne zwischen den beiden Zustaenden enthaelt ihn nicht.

**Drei Huerden, alle drei noetig.** Eine Zelle zaehlt erst als Fund, wenn sie

1. statistisch auffaellt - und zwar gegen die Zahl der **geprueften** Zellen
   gerechnet, nicht gegen eine einzelne (``schwelle_fuer``),
2. in **beiden Haelften** des Zeitraums dasselbe Vorzeichen hat, und
3. nach Gebuehren etwas uebrig laesst.

Die zweite Huerde ist die, an der in diesem Projekt der erste 15-Minuten-Fund
gescheitert ist: eine Gegenbewegung ueber vier Stunden, marktuebergreifend
bestaetigt (BTC t = -4,11, ETH t = -2,75) - und in der zweiten Haelfte des
Zeitraums vollstaendig verschwunden (t = 0,29). Ohne diese Pruefung waere das
als Fund durchgegangen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Ab welchem Betrag des t-Werts eine **einzelne** Zelle auffaellt.
MIND_T = 2.0

#: Wie viele unabhaengige Beobachtungen je Zustand mindestens noetig sind.
MIND_BEOBACHTUNGEN = 30

#: Roundtrip-Kosten in Prozent des Nominalwerts, beide Seiten als Limit-Order.
#: Der guenstigste Fall, den unsere Ausfuehrung erreichen kann.
KOSTEN_MAKER_MAKER = 0.04


def schwelle_fuer(zellen: int, irrtum: float = 0.05) -> float:
    """Die Schwelle, wenn nicht eine Zelle geprueft wird, sondern viele.

    Ein Scan ueber neun Rueckblicke und neun Haltedauern prueft 81 Zellen.
    Bei ``|t| >= 2`` sind darunter rein zufaellig **vier** auffaellige zu
    erwarten - je Markt. Wer die beste davon nimmt und fuer einen Fund haelt,
    hat nichts gemessen ausser der Zahl seiner Versuche.

    Das ist derselbe Fehler, gegen den das Deflated-Sharpe-Gate schuetzt, nur
    eine Ebene tiefer. Er waere hier besonders bitter: Der Scan wurde gebaut,
    um Versuche zu sparen - und wuerde dann selbst welche produzieren.

    Korrigiert wird nach Bonferroni: Die Irrtumswahrscheinlichkeit wird auf
    die Zahl der Zellen aufgeteilt. Konservativ, weil benachbarte Zellen
    nicht unabhaengig sind - und konservativ ist hier die richtige Richtung.
    """
    from statistics import NormalDist

    if zellen <= 1:
        return MIND_T
    return float(NormalDist().inv_cdf(1 - irrtum / (2 * zellen)))


@dataclass(frozen=True, slots=True)
class Zelle:
    """Ein Rueckblick-Halten-Paar und was es vorhersagt."""

    rueckblick: int
    halten: int
    beobachtungen: int
    spanne_pct: float
    """Aufwaerts minus abwaerts, in Prozent. Positiv heisst Trendfolge,
    negativ heisst Gegenbewegung."""

    t_wert: float

    def kosten_vielfaches(self, kosten: float = KOSTEN_MAKER_MAKER) -> float:
        return abs(self.spanne_pct) / kosten if kosten > 0 else 0.0

    def netto_pct(self, kosten: float = KOSTEN_MAKER_MAKER) -> float:
        """Was nach Gebuehren bleibt - **halbe Spanne**, nicht ganze.

        Die Spanne ist der Unterschied zwischen zwei Zustaenden. Eine Regel,
        die nur eine Seite handelt, erntet davon grob die Haelfte. Wer mit der
        ganzen Spanne rechnet, verdoppelt seinen Vorteil auf dem Papier.
        """
        return abs(self.spanne_pct) / 2 - kosten

    @property
    def auffaellig(self) -> bool:
        """Auffaellig als **einzelne** Zelle. Fuer einen Scan ueber viele
        Zellen ist ``ueber_schwelle`` das richtige Mass."""
        return abs(self.t_wert) >= MIND_T

    def ueber_schwelle(self, schwelle: float) -> bool:
        return abs(self.t_wert) >= schwelle


def spanne(log_close: np.ndarray, rueckblick: int, halten: int) -> Zelle | None:
    """Aufwaerts-minus-Abwaerts-Spanne fuer ein Rueckblick-Halten-Paar.

    ``None``, wenn zu wenig Daten. Beobachtet wird nur alle ``halten`` Balken
    einmal - ueberlappende Fenster waeren nicht unabhaengig, und der t-Wert
    daraus waere um den Faktor Wurzel(halten) zu gross. Das ist der
    haeufigste Weg, sich einen Vorteil herbeizurechnen.
    """
    if rueckblick < 1 or halten < 1 or rueckblick + halten >= len(log_close):
        return None

    vergangen = log_close[rueckblick:-halten] - log_close[: -rueckblick - halten]
    vorwaerts = log_close[rueckblick + halten :] - log_close[rueckblick:-halten]
    v, f = vergangen[::halten], vorwaerts[::halten]

    auf, ab = f[v > 0], f[v <= 0]
    if len(auf) < MIND_BEOBACHTUNGEN or len(ab) < MIND_BEOBACHTUNGEN:
        return None

    differenz = (float(np.mean(auf)) - float(np.mean(ab))) * 100
    fehler = (
        np.sqrt(np.var(auf, ddof=1) / len(auf) + np.var(ab, ddof=1) / len(ab)) * 100
    )
    return Zelle(
        rueckblick=rueckblick,
        halten=halten,
        beobachtungen=len(f),
        spanne_pct=differenz,
        t_wert=float(differenz / fehler) if fehler > 0 else 0.0,
    )


def scanne(
    close: np.ndarray, rueckblicke: list[int], halten: list[int]
) -> list[Zelle]:
    """Alle Paare durchrechnen, nach Auffaelligkeit sortiert."""
    log_close = np.log(np.asarray(close, dtype=float))
    zellen = [
        z
        for L in rueckblicke
        for H in halten
        if (z := spanne(log_close, L, H)) is not None
    ]
    return sorted(zellen, key=lambda z: -abs(z.t_wert))


#: Geforderte Trennschaerfe der Stabilitaetspruefung. Dieselbe Zahl wie in
#: ``research/live_evidenz.py`` - dort gilt sie fuer den Demobetrieb, hier fuer
#: die zweite Haelfte des Zeitraums. Die Frage ist beide Male dieselbe.
TRENNSCHAERFE = 0.8


def erkennbare_spanne(
    zelle: Zelle, *, trennschaerfe: float = TRENNSCHAERFE, irrtum: float = 0.05
) -> float:
    """Welche Spanne haette in dieser Haelfte ueberhaupt auffallen koennen?

    Die Zahl, die einem gescheiterten Stabilitaetstest erst seine Bedeutung
    gibt. Ohne sie heisst "nicht stabil" zweierlei: **Der Vorteil ist weg**
    oder **ich haette ihn hier gar nicht sehen koennen**. Der Unterschied
    entscheidet, ob man weitersucht oder aufhoert.

    Gerechnet aus dem beobachteten Standardfehler - der steckt in ``spanne``
    und ``t_wert`` bereits drin (``SE = spanne / t``), es braucht keine
    zusaetzliche Annahme ueber die Streuung.
    """
    from statistics import NormalDist

    if zelle.t_wert == 0:
        return float("inf")
    standardfehler = abs(zelle.spanne_pct / zelle.t_wert)
    normal = NormalDist()
    return standardfehler * (
        normal.inv_cdf(1 - irrtum / 2) + normal.inv_cdf(trennschaerfe)
    )


@dataclass(frozen=True, slots=True)
class Stabilitaet:
    """Haelt eine Zelle in beiden Haelften des Zeitraums?"""

    erste: Zelle | None
    zweite: Zelle | None

    @property
    def haelt(self) -> bool:
        """Beide Haelften, gleiches Vorzeichen, beide auffaellig.

        Streng, und mit Absicht: Ein Vorteil, den es nur in der ersten Haelfte
        gab, ist entweder wegarbitriert oder war nie da. Beides heisst, dass er
        morgen nicht zur Verfuegung steht.
        """
        if self.erste is None or self.zweite is None:
            return False
        gleiches_vorzeichen = (self.erste.spanne_pct > 0) == (
            self.zweite.spanne_pct > 0
        )
        return gleiches_vorzeichen and self.erste.auffaellig and self.zweite.auffaellig

    @property
    def aussagekraeftig(self) -> bool:
        """Haette die zweite Haelfte den Effekt der ersten sehen koennen?

        ``False`` heisst: Der Test hat nichts gefunden, aber er konnte auch
        nichts finden - die Haelfte ist zu kurz fuer einen Effekt dieser
        Groesse. Dann ist "nicht stabil" **kein Befund**, sondern eine
        fehlende Messung.

        Genau hier lag die Gefahr beim Abtasten der Intervalle: Auf 15 Minuten
        stehen je Haelfte 7.000 Beobachtungen, auf Tageskerzen nur 660. Beide
        Male stand "nicht stabil" da - und es bedeutete etwas voellig anderes.
        """
        if self.erste is None or self.zweite is None:
            return False
        return abs(self.erste.spanne_pct) >= erkennbare_spanne(self.zweite)

    def beschreibe(self) -> str:
        if self.erste is None or self.zweite is None:
            return "Zu wenig Daten fuer eine Haelfte."
        if self.haelt:
            return (
                f"stabil: erste Haelfte t = {self.erste.t_wert:+.2f}, "
                f"zweite t = {self.zweite.t_wert:+.2f}"
            )
        if not self.aussagekraeftig:
            return (
                f"nicht entscheidbar: Die zweite Haelfte haette erst eine "
                f"Spanne ab {erkennbare_spanne(self.zweite):.4f} % erkannt, "
                f"die erste zeigte {abs(self.erste.spanne_pct):.4f} %. Zu "
                f"wenig Beobachtungen, um 'verschwunden' von 'nie da' zu "
                f"trennen."
            )
        return (
            f"verschwunden: erste Haelfte t = {self.erste.t_wert:+.2f}, "
            f"zweite t = {self.zweite.t_wert:+.2f} - und die zweite haette "
            f"einen Effekt dieser Groesse gesehen "
            f"(Grenze {erkennbare_spanne(self.zweite):.4f} %)"
        )


def pruefe_stabilitaet(
    close: np.ndarray, rueckblick: int, halten: int
) -> Stabilitaet:
    """Dieselbe Zelle in erster und zweiter Haelfte des Zeitraums."""
    werte = np.asarray(close, dtype=float)
    mitte = len(werte) // 2
    return Stabilitaet(
        erste=spanne(np.log(werte[:mitte]), rueckblick, halten),
        zweite=spanne(np.log(werte[mitte:]), rueckblick, halten),
    )


def urteil(
    zelle: Zelle,
    stabilitaet: Stabilitaet,
    kosten: float = KOSTEN_MAKER_MAKER,
    *,
    gepruefte_zellen: int = 1,
) -> str:
    """Ein Satz, der sagt, ob sich Versuche lohnen.

    ``gepruefte_zellen`` ist die Zahl der Zellen, aus denen diese ausgewaehlt
    wurde. Ohne sie beurteilt man den Gewinner eines Wettbewerbs, als waere er
    der einzige Teilnehmer gewesen.
    """
    schwelle = schwelle_fuer(gepruefte_zellen)
    if not zelle.ueber_schwelle(schwelle):
        zusatz = (
            f" Bei {gepruefte_zellen} geprueften Zellen liegt die Schwelle bei "
            f"{schwelle:.2f}, nicht bei {MIND_T:.2f}."
            if gepruefte_zellen > 1
            else ""
        )
        return (
            f"Nicht auffaellig genug (t = {zelle.t_wert:+.2f}).{zusatz} Hier "
            f"Versuche auszugeben, hiesse die Huerde zu heben, ohne etwas zu "
            f"holen."
        )
    if not stabilitaet.haelt:
        return (
            f"Auffaellig (t = {zelle.t_wert:+.2f}), aber "
            f"{stabilitaet.beschreibe()}."
        )
    netto = zelle.netto_pct(kosten)
    if netto <= 0:
        return (
            f"Auffaellig und stabil, aber zu klein: halbe Spanne "
            f"{abs(zelle.spanne_pct) / 2:.4f} % gegen {kosten:.4f} % Kosten "
            f"= {netto:+.4f} %. Die Gebuehren fressen es."
        )
    return (
        f"Fund: t = {zelle.t_wert:+.2f}, in beiden Haelften, netto "
        f"{netto:+.4f} % je Trade nach Kosten. Hier lohnen sich Versuche."
    )
