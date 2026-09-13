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

**Vier Huerden, alle vier noetig.** Eine Zelle zaehlt erst als Fund, wenn sie

1. statistisch auffaellt - und zwar gegen die Zahl der **geprueften** Zellen
   gerechnet, nicht gegen eine einzelne (``schwelle_fuer``),
2. diesen t-Wert auch dann behaelt, wenn man ihn gegen die Traegheit ihres
   eigenen Teilers haelt (``rotationsprobe``),
3. in **beiden Haelften** des Zeitraums dasselbe Vorzeichen hat, und
4. nach Gebuehren etwas uebrig laesst.

Die dritte Huerde ist die, an der in diesem Projekt der erste 15-Minuten-Fund
gescheitert ist: eine Gegenbewegung ueber vier Stunden, marktuebergreifend
bestaetigt (BTC t = -4,11, ETH t = -2,75) - und in der zweiten Haelfte des
Zeitraums vollstaendig verschwunden (t = 0,29). Ohne diese Pruefung waere das
als Fund durchgegangen.

Die zweite kam spaeter dazu (Befund 276) und aus demselben Grund: Die
Marktbreite lieferte die erste Zelle, die alle damaligen Huerden nahm - t =
-3,74 ueber einer Latte von 3,62, in beiden Haelften, netto +0,90 % je Trade.
Sie stand auf 585 Beobachtungen, deren Zustand fuenfzehnmal wechselt. Gegen
verschobene Teiler gehalten erreichen 2 von 584 Verschiebungen denselben Wert;
gefordert waren 0,029 %. **Die Latte selbst war zu niedrig**, nicht die Zelle
zu schwach: Die Normalverteilung hinter ``schwelle_fuer`` unterstellt, dass
jede Beobachtung neu gewuerfelt wird, und keine dieser Familien tut das.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
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


def zweiteilung(
    vorwaerts: np.ndarray,
    teiler: np.ndarray,
    *,
    rueckblick: int,
    halten: int,
) -> Zelle | None:
    """Die Spanne zwischen zwei Zustaenden - fuer **jeden** Teiler.

    ``teiler > 0`` ist der eine Zustand, der Rest der andere; gemessen wird
    die Differenz der Folgerenditen. Ob der Teiler eine vergangene Rendite
    ist, ein Volumen ueber seinem Median oder eine Tagesspanne, aendert an
    der Rechnung nichts (Befund 274).

    **Die Form ist der Kern der Messung**, nicht die Kennzahl: Eine Differenz
    zwischen zwei Zustaenden enthaelt den Grundtrend nicht - eine bedingte
    Rendite schon, und bei einem Markt, der sich vervielfacht hat, ist das
    ueberwiegend Trend und kein Vorteil.
    """
    if len(vorwaerts) != len(teiler):
        raise ValueError("Zu jedem Vorwaertswert gehoert genau ein Teiler.")

    auf, ab = vorwaerts[teiler > 0], vorwaerts[teiler <= 0]
    if len(auf) < MIND_BEOBACHTUNGEN or len(ab) < MIND_BEOBACHTUNGEN:
        return None

    differenz = (float(np.mean(auf)) - float(np.mean(ab))) * 100
    fehler = (
        np.sqrt(np.var(auf, ddof=1) / len(auf) + np.var(ab, ddof=1) / len(ab)) * 100
    )
    return Zelle(
        rueckblick=rueckblick,
        halten=halten,
        beobachtungen=len(vorwaerts),
        spanne_pct=differenz,
        t_wert=float(differenz / fehler) if fehler > 0 else 0.0,
    )


def paar(
    log_close: np.ndarray, rueckblick: int, halten: int
) -> tuple[np.ndarray, np.ndarray] | None:
    """Folgerendite und Teiler einer Zelle - ausgeduennt, aber ungerechnet.

    Dasselbe Zwischenergebnis, das ``spanne`` an ``zweiteilung`` weitergibt.
    Es steht hier offen, weil die Rotationsprobe (Befund 276) genau diese
    beiden Reihen braucht: Sie rechnet die Zelle hunderte Male neu, mit
    verschobenem Teiler. Wuerde sie sich das Paar selbst zusammenbauen,
    pruefte sie am Ende eine andere Zelle als die, ueber die geurteilt wird.

    Beobachtet wird nur alle ``halten`` Balken einmal - ueberlappende Fenster
    waeren nicht unabhaengig, und der t-Wert daraus waere um den Faktor
    Wurzel(halten) zu gross. Das ist der haeufigste Weg, sich einen Vorteil
    herbeizurechnen.
    """
    if rueckblick < 1 or halten < 1 or rueckblick + halten >= len(log_close):
        return None

    vergangen = log_close[rueckblick:-halten] - log_close[: -rueckblick - halten]
    vorwaerts = log_close[rueckblick + halten :] - log_close[rueckblick:-halten]
    return vorwaerts[::halten], vergangen[::halten]


def spanne(log_close: np.ndarray, rueckblick: int, halten: int) -> Zelle | None:
    """Aufwaerts-minus-Abwaerts-Spanne fuer ein Rueckblick-Halten-Paar.

    ``None``, wenn zu wenig Daten.
    """
    reihen = paar(log_close, rueckblick, halten)
    if reihen is None:
        return None
    return zweiteilung(*reihen, rueckblick=rueckblick, halten=halten)


def paar_nach_kennzahl(
    log_close: np.ndarray,
    kennzahl: np.ndarray,
    rueckblick: int,
    halten: int,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Das Paar der Kennzahl-Familie - siehe ``paar``."""
    if rueckblick < 1 or halten < 1 or rueckblick + halten >= len(log_close):
        return None
    if len(kennzahl) != len(log_close):
        raise ValueError("Kennzahl und Kurse muessen gleich lang sein.")

    vorwaerts = log_close[rueckblick + halten :] - log_close[rueckblick:-halten]
    gleitend = _gleitender_median(kennzahl, rueckblick)
    # ``[rueckblick:-halten]`` wie bei der Rendite: derselbe Entscheidungs-
    # balken, nur ein anderer Teiler.
    lage = (kennzahl - gleitend)[rueckblick:-halten]
    return vorwaerts[::halten], lage[::halten]


def spanne_nach_kennzahl(
    log_close: np.ndarray,
    kennzahl: np.ndarray,
    rueckblick: int,
    halten: int,
) -> Zelle | None:
    """Dasselbe, aber geteilt nach einer **anderen** Kennzahl (Befund 274).

    ``kennzahl`` steht je Balken und wird gegen ihren gleitenden Median ueber
    ``rueckblick`` Balken gehalten: darueber ist der eine Zustand, darunter
    der andere. Der Median statt eines festen Werts, weil die Groesse ueber
    Jahre waechst - ein fester Schwellwert waere in der zweiten Haelfte des
    Zeitraums ein anderer Zustand als in der ersten.

    Gelesen wird die Kennzahl **bis** zum Entscheidungsbalken, die Rendite
    danach. Ohne diese Trennung misst man die Gegenwart mit sich selbst.
    """
    reihen = paar_nach_kennzahl(log_close, kennzahl, rueckblick, halten)
    if reihen is None:
        return None
    return zweiteilung(*reihen, rueckblick=rueckblick, halten=halten)


#: Wie viele **andere** Maerkte eine Marktbreite mindestens braucht.
#:
#: Mit einem einzigen Partner ist es keine Breite, sondern ein Paarvergleich:
#: Die Kennzahl kennt dann genau zwei Zustaende, und sie sagt nichts anderes
#: als der Rueckblick dieses einen Marktes. Die offene Frage aus Befund 274
#: heisst ausdruecklich *"Marktbreite ueber mehr als zwei Maerkte"* - der
#: gehandelte und mindestens zwei weitere.
MIND_ANDERE = 2


def spanne_nach_breite(
    log_close: np.ndarray,
    andere: Sequence[np.ndarray],
    rueckblick: int,
    halten: int,
) -> Zelle | None:
    """Die Spanne, geteilt nach der Breite der **uebrigen** Maerkte.

    Der Zustand ist der Anteil der anderen Maerkte, die ueber denselben
    Rueckblick gestiegen sind: mehrheitlich aufwaerts gegen mehrheitlich
    abwaerts. Die klassische Marktbreite, und die letzte Familie, die Befund
    274 offengelassen hat.

    **Ohne den gehandelten Markt selbst.** Die uebliche Definition zaehlt ihn
    mit; hier waere das ein Fehler. Ein Teil dieser Kennzahl waere dann der
    eigene Rueckblick, den die erste Familie schon misst - und ein Fund liesse
    sich nicht mehr zuordnen: eigener Trend oder fremde Bestaetigung. Getrennt
    gefragt gibt die Familie eine eigene Antwort.

    **Der unentschiedene Zustand faellt heraus.** Bei einer geraden Zahl
    anderer Maerkte gibt es das genaue Patt, und es ist keiner der beiden
    Zustaende. Es einer Seite zuzuschlagen, mischte einen dritten Zustand in
    einen der beiden - der Unterschied waere dann kleiner, als er ist, und
    zwar aus einer Entscheidung heraus, nicht aus den Daten. Gezaehlt wird in
    ``Zelle.beobachtungen`` daher nur, was uebrig bleibt.

    Ausgeduennt wird **vor** dem Aussortieren: Die Unabhaengigkeit der
    Beobachtungen haengt am gleichen Abstand von ``halten`` Balken, und der
    entstuende nicht mehr, wenn erst die Patts aus der vollen Reihe fielen.
    """
    reihen = paar_nach_breite(log_close, andere, rueckblick, halten)
    if reihen is None:
        return None
    return zweiteilung(*reihen, rueckblick=rueckblick, halten=halten)


def paar_nach_breite(
    log_close: np.ndarray,
    andere: Sequence[np.ndarray],
    rueckblick: int,
    halten: int,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Das Paar der Breiten-Familie - siehe ``paar``."""
    if rueckblick < 1 or halten < 1 or rueckblick + halten >= len(log_close):
        return None
    if len(andere) < MIND_ANDERE:
        return None
    if any(len(m) != len(log_close) for m in andere):
        raise ValueError("Alle Maerkte muessen auf denselben Zeitstempeln stehen.")

    def vergangen(reihe: np.ndarray) -> np.ndarray:
        return reihe[rueckblick:-halten] - reihe[: -rueckblick - halten]

    anteil = np.mean([vergangen(m) > 0 for m in andere], axis=0)
    vorwaerts = log_close[rueckblick + halten :] - log_close[rueckblick:-halten]

    breite = anteil[::halten] - 0.5
    entschieden = breite != 0
    return vorwaerts[::halten][entschieden], breite[entschieden]


def _gleitender_median(werte: np.ndarray, fenster: int) -> np.ndarray:
    """Median der letzten ``fenster`` Werte **einschliesslich** des aktuellen.

    Am Anfang, wo das Fenster noch nicht voll ist, steht der Median des
    bisher Bekannten - kein Blick nach vorn.
    """
    werte = np.asarray(werte, dtype=float)
    aus = np.empty_like(werte)
    for i in range(len(werte)):
        von = max(0, i - fenster + 1)
        aus[i] = np.median(werte[von : i + 1])
    return aus


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


def haelften(
    zelle_aus: Callable[[int, int], Zelle | None], laenge: int
) -> Stabilitaet:
    """Dieselbe Rechnung zweimal: vordere und hintere Haelfte des Zeitraums.

    **Die Teilung steht einmal da** (Befund 276). Jede Familie bringt ihren
    eigenen Teiler mit, aber nicht ihre eigene Vorstellung davon, wo die Mitte
    liegt - sonst pruefte die eine Familie auf halber Strecke und die naechste
    ein paar Balken daneben, und der Vergleich ihrer Urteile waere keiner.
    """
    mitte = laenge // 2
    return Stabilitaet(erste=zelle_aus(0, mitte), zweite=zelle_aus(mitte, laenge))


def pruefe_stabilitaet(
    close: np.ndarray, rueckblick: int, halten: int
) -> Stabilitaet:
    """Dieselbe Zelle in erster und zweiter Haelfte des Zeitraums."""
    werte = np.asarray(close, dtype=float)
    return haelften(
        lambda a, b: spanne(np.log(werte[a:b]), rueckblick, halten), len(werte)
    )


def stabilitaet_nach_kennzahl(
    log_close: np.ndarray, kennzahl: np.ndarray, rueckblick: int, halten: int
) -> Stabilitaet:
    """Hurde 2 fuer eine Kennzahl-Familie (Volumen, Spanne).

    Bis Befund 276 gab es das nicht: Gerechnet wurde die Stabilitaet nur fuer
    die Preisrueckblick-Familie, und die Nebenfamilien meldeten bloss, wie
    viele Zellen ueber der Schwelle liegen. Solange dort keine lag, ist das
    nicht aufgefallen - es war trotzdem eine halbe Pruefung.
    """
    return haelften(
        lambda a, b: spanne_nach_kennzahl(
            log_close[a:b], kennzahl[a:b], rueckblick, halten
        ),
        len(log_close),
    )


def stabilitaet_nach_breite(
    log_close: np.ndarray,
    andere: Sequence[np.ndarray],
    rueckblick: int,
    halten: int,
) -> Stabilitaet:
    """Hurde 2 fuer die Marktbreite - die Nachbarn werden mitgeschnitten.

    Wuerden die Nachbarmaerkte ungeschnitten bleiben, stuende in der zweiten
    Haelfte eine Breite aus der ersten neben einer Rendite aus der zweiten.
    """
    return haelften(
        lambda a, b: spanne_nach_breite(
            log_close[a:b], [m[a:b] for m in andere], rueckblick, halten
        ),
        len(log_close),
    )


@dataclass(frozen=True, slots=True)
class Rotationsprobe:
    """Wie oft erzeugt der Teiler diesen t-Wert, ohne etwas vorherzusagen?

    Der t-Wert von ``zweiteilung`` wird gegen eine Normalverteilung gehalten
    (``schwelle_fuer``). Das setzt voraus, dass die Zuordnung zu den beiden
    Zustaenden von Beobachtung zu Beobachtung neu gewuerfelt wird. Genau das
    tut sie nicht: Ein Rueckblick ueber 960 Balken haelt seinen Zustand
    jahrelang. Dann stehen zwar 585 Renditen da, aber nur sechzehn Bloecke -
    und die Latte, die fuer 585 Wuerfe gedacht ist, wird zur Formsache.

    **Warum die Latte so weit danebenliegt** - berichtigt in Befund 277.
    Zuerst stand hier, es sei "die Form der Renditen selbst". Zerlegt man es
    auf der Preisrueckblick-Spitze von Befund 272 (BTC, Tageskerzen), sagen
    die Zahlen etwas anderes:

        Teiler      Renditen     99. Perzentil der Null
        verschoben  echt                           4,14
        gewuerfelt  echt                           2,80
        verschoben  gemischt                       2,33
        gewuerfelt  gemischt                       2,47

    Keiner der beiden Anteile allein tut es. Es ist die **Bauart**: Teiler
    und Folgerendite stammen aus derselben wandernden Reihe, und ein traeger
    Teiler schiebt sich beim Verschieben durch die Phasen dieser Wanderung.
    Ein reiner Irrweg ohne dicke Raender, ohne Regimewechsel und ohne Trend
    reicht dafuer aus - nachgebaut in ``tests/test_vorzeichenprobe``.

    **Sie verwirft nicht pauschal.** Auf Viertelstunden wechselt derselbe
    Teiler 7720-mal auf 14.120 Beobachtungen, und keine einzige von 1764
    Verschiebungen erreicht seinen Wert. Dort scheitert die Zelle an der
    naechsten Huerde, wie sie es vorher schon tat.
    """

    beobachtet: float
    """Der |t| der gemessenen Zelle."""

    haeufiger: int
    """Wie viele Verschiebungen ihn erreichen oder uebertreffen."""

    rotationen: int
    bloecke: int
    """Wie oft der Teiler ueberhaupt den Zustand wechselt, plus eins."""

    perzentil_99: float
    """Das 99. Perzentil der verschobenen |t| - die **Eichung der Latte**.

    ``schwelle_fuer`` rechnet mit einer Normalverteilung, deren 99. Perzentil
    bei 2,576 liegt. Steht diese Zahl weit darueber, ist die Latte zu
    niedrig - und genau das war sie hier (Befund 276). Sie wird seit 277 in
    jedem Lauf berichtet und nicht erst, wenn eine Zelle anschlaegt: Wer die
    Eichung nur bei einem Treffer rechnet, erfaehrt nie, ob die Latte
    ueberhaupt richtig steht.
    """

    @property
    def anteil(self) -> float:
        return self.haeufiger / self.rotationen if self.rotationen else 1.0

    @property
    def aufloesung(self) -> float:
        """Das Feinste, was diese Probe sagen kann.

        Bei 584 Verschiebungen heisst das beste Ergebnis "keine einzige" -
        und das ist eine Aussage ueber 1 von 585, nicht ueber weniger.
        """
        return 1 / (self.rotationen + 1) if self.rotationen else 1.0

    def traegt(self, noetig: float) -> bool:
        return self.anteil <= noetig

    def beschreibe(self, noetig: float) -> str:
        """Der Satz zur Probe - mit dem Vorbehalt an der richtigen Stelle.

        Der Vorbehalt gehoert an den **bestandenen** Fall: "keine einzige von
        584" heisst hoechstens 1 von 585, und wer 0,029 % verlangt, hat das
        damit nicht belegt. Am gerissenen Fall waere er sinnlos - dort ist
        der gemessene Anteil schon groesser als das Geforderte, und feiner
        messen zu koennen aenderte daran nichts.
        """
        kern = (
            f"{self.haeufiger} von {self.rotationen} Verschiebungen erreichen "
            f"ihn ({self.anteil:.2%}), noetig waeren {noetig:.3%} - der "
            f"Teiler wechselt seinen Zustand {self.bloecke - 1}-mal auf "
            f"diesen Beobachtungen"
        )
        if not self.traegt(noetig):
            return kern
        if self.aufloesung <= noetig:
            return kern
        return kern + (
            f". Feiner als {self.aufloesung:.3%} kann diese Probe nicht "
            f"werden, verlangt sind {noetig:.3%}: 'nicht belegbar' ist auf "
            f"dieser Stichprobe nicht von 'nicht da' zu trennen"
        )


def rotationsprobe(
    vorwaerts: np.ndarray,
    teiler: np.ndarray,
    *,
    rueckblick: int,
    halten: int,
    hoechstens: int = 2000,
) -> Rotationsprobe | None:
    """Dieselbe Zelle mit zeitlich verschobenem Teiler - alle Verschiebungen.

    **Warum verschieben und nicht mischen.** Mischen zerstoert die Traegheit
    des Teilers, und gerade sie ist die Frage: Ein Zustand, der jahrelang
    steht, erzeugt den Unterschied zweier Mittelwerte schon von allein.
    Verschieben laesst beide Reihen vollstaendig in ihrer eigenen Ordnung -
    Traegheit hier, Streuung dort - und loest nur, was zusammengehoert.

    **Warum keine Bloecke.** Ein Block-Bootstrap braeuchte eine Blocklaenge,
    und die waere ein Regler: kurz gewaehlt faellt die Probe milde aus, lang
    gewaehlt streng. Die Verschiebung hat keinen.

    Was die Probe nicht kann, steht in ``Rotationsprobe.aufloesung``.
    """
    if len(vorwaerts) != len(teiler):
        raise ValueError("Zu jedem Vorwaertswert gehoert genau ein Teiler.")
    gemessen = zweiteilung(vorwaerts, teiler, rueckblick=rueckblick, halten=halten)
    if gemessen is None:
        return None

    vorzeichen = teiler > 0
    bloecke = int(np.sum(vorzeichen[1:] != vorzeichen[:-1])) + 1
    # Aufgerundet, damit ``hoechstens`` eine Obergrenze ist und keine
    # ungefaehre: Abgerundet lieferte ein Deckel von 200 schon einmal 210.
    schritt = max(1, -(-(len(teiler) - 1) // hoechstens))
    beobachtet = abs(gemessen.t_wert)
    werte: list[float] = []
    for k in range(schritt, len(teiler), schritt):
        verschoben = zweiteilung(
            vorwaerts, np.roll(teiler, k), rueckblick=rueckblick, halten=halten
        )
        if verschoben is not None:
            werte.append(abs(verschoben.t_wert))
    if not werte:
        return None
    return Rotationsprobe(
        beobachtet=beobachtet,
        haeufiger=int(sum(1 for w in werte if w >= beobachtet)),
        rotationen=len(werte),
        bloecke=bloecke,
        perzentil_99=float(np.percentile(werte, 99)),
    )


def urteil(
    zelle: Zelle,
    stabilitaet: Stabilitaet,
    kosten: float = KOSTEN_MAKER_MAKER,
    *,
    gepruefte_zellen: int = 1,
    probe: Rotationsprobe | None = None,
) -> str:
    """Ein Satz, der sagt, ob sich Versuche lohnen.

    ``gepruefte_zellen`` ist die Zahl der Zellen, aus denen diese ausgewaehlt
    wurde. Ohne sie beurteilt man den Gewinner eines Wettbewerbs, als waere er
    der einzige Teilnehmer gewesen.

    ``probe`` prueft dieselbe Zahl noch einmal gegen die Traegheit des
    Teilers (Befund 276). Sie steht direkt hinter der Schwelle, weil sie
    dieselbe Groesse in Frage stellt: Haelt sie nicht, war schon der
    Schwellenvergleich keiner.
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
    noetig = 0.05 / gepruefte_zellen
    if probe is not None and not probe.traegt(noetig):
        return (
            f"Ueber der Schwelle (t = {zelle.t_wert:+.2f}), aber die "
            f"Verschiebungsprobe traegt ihn nicht: "
            f"{probe.beschreibe(noetig)}."
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
    geprueft = (
        f", {probe.beschreibe(noetig)}" if probe is not None else ""
    )
    return (
        f"Fund: t = {zelle.t_wert:+.2f}, in beiden Haelften{geprueft}, netto "
        f"{netto:+.4f} % je Trade nach Kosten. Hier lohnen sich Versuche."
    )
