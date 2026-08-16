"""Wer die Streuung einer Ideenquelle misst, misst zuerst sein eigenes Rauschen.

Drei Tests tragen diese Datei:

``test_die_analyst_vorschlaege_zeigen_keine_ideenstreuung`` - Die fuenf
Vorschlaege streuen mit 0,1031 und sahen damit besser aus als der Zufall
(0,0808). Das erwartete Messrauschen liegt aber bei 0,1928. Es ist nichts
nachgewiesen.

``test_ein_kandidat_mit_acht_trades_kann_nichts_zeigen`` - Sein Sharpe je
Trade traegt ein Rauschen von 0,378, sein Gate wird uebersprungen, und der
Versuchszaehler geht trotzdem hoch.

``test_nicht_nachweisbar_heisst_nicht_nicht_vorhanden`` - Dieselbe
Unterscheidung wie im Vorteilsscan und in ``haelften``: "nichts gefunden" und
"konnte nichts finden" sind zwei verschiedene Aussagen.
"""

from __future__ import annotations

import pytest

from research.aussagekraft import (
    MINDESTTRADES,
    Beleg,
    Ideenquelle,
    chi2_quantil,
    messrauschen,
    zerlege,
)

#: Die fuenf Analyst-Vorschlaege - die einzigen Versuche dieses Projekts mit
#: belegtem Sharpe je Trade.
VORSCHLAEGE = [
    ("Neues Hoch im Takt", 0.2137, 123),
    ("Ausbruch mit Beteiligung", 0.2482, 68),
    ("Donchian-Ausbruch 50/25", 0.2136, 89),
    ("Rueckkehr vom unteren Band", 0.0483, 118),
    ("Rueckschlag im Aufwaertstrend", 0.0300, 8),
]


def analyst(*, ohne_kleine: bool = False) -> Ideenquelle:
    belege = [
        Beleg(kennung=n, sharpe_je_trade=s, trades=t)
        for n, s, t in VORSCHLAEGE
        if not ohne_kleine or t >= MINDESTTRADES
    ]
    return Ideenquelle(name="Analyst", belege=belege)


class TestMessrauschen:
    def test_wenige_trades_bedeuten_viel_rauschen(self) -> None:
        assert messrauschen(8) > messrauschen(123) > messrauschen(1000)

    def test_es_ist_dieselbe_groesse_wie_die_nullstreuung(self) -> None:
        """Kein Zufall: Das Gate fragt, ob ein Vorteil groesser ist als das,
        was diese Ungenauigkeit bei so vielen Versuchen hergibt."""
        assert messrauschen(154) == pytest.approx((1 / 153) ** 0.5)

    def test_ein_einzelner_trade_sagt_nichts(self) -> None:
        assert messrauschen(1) == float("inf")


class TestChiQuadrat:
    def test_die_naeherung_trifft_die_tabelle(self) -> None:
        """Ohne ``scipy`` gerechnet - also wird die Genauigkeit gemessen und
        nicht angenommen."""
        for p, k, tabelle in (
            (0.95, 4, 9.488),
            (0.05, 4, 0.711),
            (0.95, 19, 30.144),
            (0.95, 49, 66.339),
        ):
            assert chi2_quantil(p, k) == pytest.approx(tabelle, rel=0.03)

    def test_mehr_freiheitsgrade_heben_das_quantil(self) -> None:
        assert chi2_quantil(0.95, 50) > chi2_quantil(0.95, 5)


class TestBeleg:
    def test_ein_kandidat_mit_acht_trades_kann_nichts_zeigen(self) -> None:
        """**Der zweite tragende Test.**

        Unter 30 Trades ueberspringt ``gate_deflated_sharpe`` die Korrektur.
        Der Kandidat kann weder bestehen noch durchfallen - und der
        Versuchszaehler geht trotzdem hoch. Er hebt damit die Huerde fuer
        jeden anderen, ohne selbst je eine Chance gehabt zu haben.
        """
        klein = Beleg(kennung="Rueckschlag", sharpe_je_trade=0.03, trades=8)

        assert not klein.beurteilbar
        assert klein.rauschen > 0.37
        assert klein.rauschen > 4 * messrauschen(154), "Vielfaches der Huerde"

    def test_genug_trades_sind_beurteilbar(self) -> None:
        assert Beleg(kennung="x", sharpe_je_trade=0.2, trades=MINDESTTRADES).beurteilbar


class TestIdeenquelle:
    def test_die_analyst_vorschlaege_zeigen_keine_ideenstreuung(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Beobachtet 0,1031 gegen eine Nullstreuung von 0,0808 - das sah nach
        einer Quelle aus, die breiter streut als Zufall. Das erwartete
        Messrauschen liegt aber bei 0,1928, also **ueber** der beobachteten
        Streuung. Die fuenf sind vollstaendig damit vertraeglich, dass sie
        alle gleich gut sind.
        """
        quelle = analyst()

        assert quelle.beobachtet == pytest.approx(0.1031, abs=0.001)
        assert quelle.beobachtet > quelle.nullstreuung, "Sonst faellt niemand darauf herein"
        assert quelle.rauschen > quelle.beobachtet
        assert quelle.ideenstreuung is None
        assert not quelle.schlaegt_den_zufall

    def test_auch_ohne_den_kleinsten_bleibt_es_dabei(self) -> None:
        """Der 8-Trade-Fall ist nicht allein schuld - ohne ihn stehen 0,0899
        gegen 0,1037."""
        quelle = analyst(ohne_kleine=True)

        assert len(quelle.belege) == 4
        assert quelle.ideenstreuung is None

    def test_nicht_nachweisbar_heisst_nicht_nicht_vorhanden(self) -> None:
        """**Der dritte tragende Test.**

        Dieselbe Unterscheidung wie im Vorteilsscan: "nichts gefunden" und
        "konnte nichts finden" sind zwei Aussagen, und nur die zweite trifft
        hier zu. Das Urteil muss beides auseinanderhalten.
        """
        urteil = analyst().urteil()

        assert "keine Ideenstreuung nachweisbar" in urteil
        assert "nicht, dass die Quelle nichts taugt" in urteil
        assert "Punkte es nicht zeigen koennen" in urteil

    def test_eine_echte_streuung_wird_gefunden(self) -> None:
        """Gegenprobe: Bei weit auseinanderliegenden Werten und vielen Trades
        bleibt nach Abzug des Rauschens etwas uebrig."""
        breit = Ideenquelle(
            name="breit",
            belege=[
                Beleg(kennung=f"k{i}", sharpe_je_trade=s, trades=2000)
                for i, s in enumerate([-0.2, 0.0, 0.15, 0.3, 0.45])
            ],
        )

        assert breit.ideenstreuung is not None
        assert breit.schlaegt_den_zufall
        assert "Ideenstreuung" in breit.urteil()

    def test_der_vertrauensbereich_enthaelt_die_nullstreuung(self) -> None:
        """Mit fuenf Punkten ist die Frage nicht entschieden - der Bereich
        reicht von 0,067 bis 0,248."""
        quelle = analyst()
        bereich = quelle.vertrauensbereich()

        assert bereich is not None
        unten, oben = bereich
        assert unten < quelle.nullstreuung < oben

    def test_die_noetige_zahl_wird_beziffert(self) -> None:
        """Was es kosten wuerde, die Frage zu beantworten - in Versuchen."""
        noetig = analyst().noetige_belege()

        assert noetig is not None
        assert 15 <= noetig <= 30, f"gemessen {noetig}"

    def test_ohne_vorsprung_gibt_es_keine_zahl(self) -> None:
        """Liegt die beobachtete Streuung schon unter dem Zufall, ist es
        keine Frage der Zahl mehr."""
        eng = Ideenquelle(
            name="eng",
            belege=[
                Beleg(kennung=f"k{i}", sharpe_je_trade=s, trades=154)
                for i, s in enumerate([0.20, 0.21, 0.205])
            ],
        )

        assert eng.noetige_belege() is None

    def test_die_unbeurteilbaren_stehen_im_urteil(self) -> None:
        urteil = analyst().urteil()

        assert "Rueckschlag im Aufwaertstrend" in urteil
        assert "hebt aber die Huerde" in urteil
        assert "am Zaehler wird nicht gedreht" in urteil

    def test_die_tabelle_markiert_sie(self) -> None:
        assert "unbeurteilbar" in analyst().tabelle()

    def test_zu_wenige_belege_liefern_kein_urteil(self) -> None:
        einer = Ideenquelle(
            name="x", belege=[Beleg(kennung="a", sharpe_je_trade=0.2, trades=100)]
        )

        assert einer.beobachtet is None
        assert "zu wenige Belege" in einer.urteil()


class TestZerlegung:
    def test_die_kalibrierung_aus_befund_71_ist_zu_drei_vierteln_rauschen(
        self,
    ) -> None:
        """Befund 71 kalibrierte 0,0950 aus dem beobachteten Bestwert. Auch
        darin steckt das Messrauschen - 72 % der Varianz.

        Das widerspricht Befund 71 nicht: Die beobachtete Streuung liegt immer
        ueber dem Rauschen, solange ueberhaupt eine Ideenstreuung da ist. Aber
        die Zahl, die zaehlt, ist 0,0499 und nicht 0,0950.
        """
        rauschen = messrauschen(154)
        ideen = zerlege(0.0950, rauschen)

        assert ideen is not None
        assert ideen == pytest.approx(0.0499, abs=0.001)
        assert rauschen**2 / 0.0950**2 == pytest.approx(0.72, abs=0.01)

    def test_unter_dem_rauschen_gibt_es_nichts_zu_zerlegen(self) -> None:
        assert zerlege(0.05, 0.08) is None
