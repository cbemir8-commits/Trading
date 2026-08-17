"""Nadelspitze, Flanke oder Plateau - was das Gate nicht unterscheiden kann.

Drei Tests tragen diese Datei:

``test_eine_flanke_ist_keine_nadelspitze`` - Der Kern. Das Gate meldet beim
Bestand "Nadelspitze"; gemessen ist es eine ueber 45 Prozentpunkte breite,
monoton fallende Flanke mit einer Kante bei +20 %. Beides ergibt denselben
Gate-Wert von 0,5.

``test_ein_besserer_punkt_schlaegt_die_eigene_auswahl_nicht`` - Die
Gegenprobe zur bequemen Lesart. Bei zwoelf gemessenen Punkten liegt das
Maximum ohnehin ueber dem Trend; wer daraus einen Parameter abliest, liest
ein Rauschen.

``test_wirkungslose_stellgroessen_zaehlen_nicht_als_robustheit`` - Vier der
sechs Stellgroessen des Bestands bewegen nichts. Sie mitzurechnen hiesse,
Flachheit fuer Robustheit zu halten.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.plateaubild import (
    MINDESTPUNKTE,
    WIRKUNGSLOS,
    Achse,
    Landschaft,
    baue,
)

FAKTOREN = (0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30)

#: Die gemessene Landschaft des Bestands auf BTC + ETH, Gewinn je Faktor.
#: Nachzurechnen mit ``cli plateaubild``.
GEMESSEN: dict[str, tuple[float, ...]] = {
    "alle gemeinsam": (1216, 1226, 1093, 1638, 799, 1041, 591, 445, 229, -104, -90, -100),
    "sma(period=50)": (1070, 961, 868, 1473, 788, 989, 575, 422, 260, -104, -94, -103),
    "sma(period=200)": (933, 932, 932, 932, 936, 955, 956, 956, 939, 939, 955, 955),
    "roc(period=90)": (963, 948, 957, 926, 953, 955, 962, 958, 957, 957, 957, 957),
    "rsi(period=14)": (964, 964, 964, 964, 962, 962, 1028, 1028, 1028, 1025, 1026, 1026),
    "Vola-Fenster": (772, 796, 802, 877, 681, 1094, 1020, 1034, 991, 964, 1023, 1025),
}
BASIS = 957.87


def landschaft() -> Landschaft:
    return baue(
        {n: list(zip(FAKTOREN, w, strict=True)) for n, w in GEMESSEN.items()},
        basis=BASIS,
    )


def achse(gewinne, *, name: str = "x", basis: float = 1000.0) -> Achse:
    return Achse(
        name=name, faktoren=FAKTOREN[: len(gewinne)],
        gewinne=tuple(float(g) for g in gewinne), basis=basis,
    )


class TestForm:
    def test_eine_flanke_ist_keine_nadelspitze(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Das Gate meldet 0,500 und "Nadelspitze". Gemessen ist die Strategie
        von Faktor 0,70 bis 1,15 durchgehend profitabel - 45 Prozentpunkte
        breit - und faellt monoton. Was das Gate trifft, ist die Kante bei
        +20 %, nicht eine Nadel neben dem Kandidaten.
        """
        eng = landschaft().engste

        assert eng is not None
        assert eng.name == "alle gemeinsam"
        assert eng.form == "Flanke"
        assert eng.tragfaehig == (0.70, 1.15)
        assert eng.breite == pytest.approx(0.45)

    def test_eine_echte_nadelspitze_wird_auch_so_erkannt(self) -> None:
        """Gegenprobe: Nur bei 1,00 profitabel, ringsum negativ."""
        nadel = achse(
            (-500, -400, -300, -200, -100, 50, -100, -200, -300, -400, -450, -500)
        )

        # 1,05 ist bereits negativ - der zusammenhaengende Bereich
        # endet damit bei 1,00 und nicht beim naechsten Messpunkt.
        assert nadel.tragfaehig == (0.95, 1.00)
        assert nadel.breite <= 0.15
        assert nadel.form == "Nadelspitze"

    def test_ein_echtes_plateau_auch(self) -> None:
        """Flach und breit profitabel - und nicht monoton, sonst waere es
        eine Flanke."""
        flach = achse((900, 1100, 950, 1050, 980, 1020, 1010, 970, 1030, 990, 1040, 960))

        assert flach.form == "Plateau"
        assert flach.breite > 0.5

    def test_wirkungslose_stellgroessen_zaehlen_nicht_als_robustheit(self) -> None:
        """**Vier der sechs Stellgroessen bewegen nichts.**

        ``rsi(14)`` schwankt zwischen 962 und 1028 - sieben Prozent der Basis.
        Dass die Strategie dagegen unempfindlich ist, sagt nichts ueber ihre
        Robustheit; es heisst nur, dass dieser Regler nicht angeschlossen ist.
        """
        bild = landschaft()
        wirksam = {a.name for a in bild.wirksame}

        assert "sma(period=50)" in wirksam
        assert "rsi(period=14)" not in wirksam
        assert "roc(period=90)" not in wirksam
        assert "sma(period=200)" not in wirksam
        assert all(a.spannweite < WIRKUNGSLOS for a in bild.achsen if not a.wirkt)
        assert "sagt nichts ueber ihre Robustheit" in bild.urteil()


class TestAuswahl:
    def test_ein_besserer_punkt_schlaegt_die_eigene_auswahl_nicht(self) -> None:
        """**Die Gegenprobe zur bequemen Lesart.**

        Bei Faktor 0,85 steht der Gewinn 680 ueber der Basis - das sieht nach
        einem besseren Parameter aus. Gegen die Trendlinie sind es +2,39
        Reststreuungen, und bei zwoelf Punkten erwartet man 1,67. Der Abstand
        entspricht z = 1,21, also kein Beleg.

        Der erste Anlauf prueft gegen den mittleren Nachbarsprung und war
        damit zu schwach; der zweite addierte einen erfundenen
        Sicherheitsabstand. Beides ersetzt durch die Streuung des Maximums,
        die sich rechnen laesst.
        """
        eng = landschaft().engste

        assert eng is not None
        assert eng.bestes_faktor == 0.85
        assert eng.besser_als_die_basis == pytest.approx(680, abs=1)
        z = eng.auffaelligkeit()
        assert z is not None
        assert z == pytest.approx(1.21, abs=0.05)
        assert not eng.optimum_ist_belegt
        assert "schlaegt aber die eigene Auswahl nicht" in landschaft().urteil()

    def test_ein_wirklicher_ausreisser_wuerde_durchkommen(self) -> None:
        """Gegenprobe: Die Schranke blockiert nicht alles. Ein Punkt weit
        ueber einem sonst glatten Trend gilt als belegt."""
        glatt = [1000 - 500 * (f - 0.7) for f in FAKTOREN]
        glatt[3] += 900
        auffaellig = achse(glatt)

        z = auffaellig.auffaelligkeit()
        assert z is not None and z > 2.0
        assert auffaellig.optimum_ist_belegt

    def test_ohne_genug_punkte_wird_nichts_behauptet(self) -> None:
        duenn = achse((1000, 900, 800))

        assert duenn.auffaelligkeit() is None
        assert not duenn.optimum_ist_belegt


class TestLandschaft:
    def test_die_engste_achse_bestimmt_das_urteil(self) -> None:
        """Das Gate wertet das Minimum ueber die Stellgroessen - ein Plateau
        ist man in jeder Richtung oder gar nicht. Der Bericht muss derselben
        Logik folgen."""
        bild = landschaft()

        assert bild.engste is not None
        assert bild.engste.breite == min(a.breite for a in bild.wirksame)

    def test_zu_wenige_punkte_liefern_nichts(self) -> None:
        duenn = Landschaft(
            achsen=[achse((1000, 900, 800, 700)[:MINDESTPUNKTE - 3])]
        )

        assert not duenn.genug
        assert "nichts sagen" in duenn.urteil()

    def test_wenn_nichts_wirkt_ist_das_kein_plateau(self) -> None:
        """**Die gefaehrliche Verwechslung.** Ein Kandidat, dessen Parameter
        alle wirkungslos sind, sieht in jedem Robustheitstest gut aus - und
        ist es nicht, sondern bloss taub."""
        taub = Landschaft(
            achsen=[
                achse([1000 + i for i in range(12)], name=f"r{k}")
                for k in range(4)
            ]
        )

        assert taub.wirksame == []
        assert "Keine der 4 Stellgroessen bewegt etwas" in taub.urteil()
        assert "Folge von Wirkungslosigkeit" in taub.urteil()

    def test_null_gewinne_kippen_nicht(self) -> None:
        leer = baue({}, basis=0.0)

        assert leer.achsen == []
        assert not leer.genug
        assert leer.tabelle() == "Keine Achsen gemessen."

    def test_identische_nachbarn_fallen_heraus(self) -> None:
        """``None`` heisst "dieser Nachbar ist der Kandidat selbst" - ein
        solcher Punkt gehoert nicht in die Kurve."""
        gebaut = baue(
            {"x": [(0.8, 100.0), (0.9, None), (1.1, 200.0)]}, basis=150.0
        )

        assert gebaut.achsen[0].faktoren == (0.8, 1.1)
        assert len(gebaut.achsen[0].gewinne) == 2


class TestTragfaehig:
    def test_nur_der_zusammenhaengende_bereich_zaehlt(self) -> None:
        """Ein isolierter Gewinn jenseits einer Verlustzone sagt nichts ueber
        die Umgebung des Kandidaten."""
        loch = achse((900, -100, 800, 950, 1000, 1050, 1000, 950, 900, -50, 700, 650))

        assert loch.tragfaehig == (0.80, 1.15)

    def test_ein_verlierender_kandidat_hat_keinen_bereich(self) -> None:
        verlierer = achse([-100] * 12, basis=-100.0)

        assert verlierer.tragfaehig is None
        assert verlierer.breite == 0.0

    def test_die_rauschgroesse_ist_der_mittlere_nachbarsprung(self) -> None:
        gleichmaessig = achse(tuple(np.arange(12) * 100.0))

        assert gleichmaessig.rauschen == pytest.approx(100.0)
