"""Dieselben 160 Trades, nur anders gross - Befund 413.

Befund 412 liess offen, warum das Waehrungsmass im durchgehenden Modus die
Quartalsabhaengigkeit nicht sieht, und benannte es mit einem **ungemessenen**
Satz: "die Betraege streuen auf einem durchverzinsten Konto zu weit".

Die kontrollierte Gegenprobe lag schon in der Messung: Ohne Beingrenzen sind
beide Zellen derselbe Trade-Satz. Damit ist die Frage gemessen - und der Satz
berichtigt.
"""

from __future__ import annotations

import pytest

from research.grenzgedaechtnis import QUARTALSPROBE, R_PROBE, SKALENPROBE


def _zelle(durchgehend: bool, limits: bool):
    return next(
        z
        for z in QUARTALSPROBE
        if z.durchgehend is durchgehend and z.limits is limits
    )


class TestDieKontrollierteGegenprobe:
    def test_es_sind_dieselben_trades(self) -> None:
        geschnitten = _zelle(durchgehend=False, limits=False)
        durch = _zelle(durchgehend=True, limits=False)

        assert geschnitten.roh == durch.roh == 160
        assert SKALENPROBE["gemeinsame_trades"] == 160

    def test_und_die_r_werte_stimmen_bis_auf_rundung(self) -> None:
        """Das ist der Beleg dafuer, dass nur die Groesse sich aendert: R
        kuerzt den Kapitalpfad exakt heraus."""
        assert SKALENPROBE["r_abweichung"] < 1e-12

    def test_nur_der_waehrungsgewinn_unterscheidet_sich(self) -> None:
        assert SKALENPROBE["faktor_min"] < 1.0 < SKALENPROBE["faktor_max"]
        assert SKALENPROBE["faktor_median"] == pytest.approx(2.774)
        assert SKALENPROBE["faktor_max"] == pytest.approx(6.0)

    def test_und_der_icc_halbiert_sich_trotzdem(self) -> None:
        """Der Fund: Bei festem Trade-Satz, Kalender und Quartalen bewegt
        allein die Groesse das Urteil."""
        geschnitten = _zelle(durchgehend=False, limits=False)
        durch = _zelle(durchgehend=True, limits=False)

        assert geschnitten.kuerzt_in_waehrung
        assert not durch.kuerzt_in_waehrung
        assert durch.icc_waehrung < geschnitten.icc_waehrung / 2

    def test_das_r_mass_sieht_in_beiden_dasselbe(self) -> None:
        geschnitten = _zelle(durchgehend=False, limits=False)
        durch = _zelle(durchgehend=True, limits=False)

        assert geschnitten.icc_r == pytest.approx(durch.icc_r)


class TestDieZerlegung:
    """Warum ein Groesseneffekt den ICC bewegt, obwohl ein gleichmaessiger
    sich herauskuerzt."""

    def test_das_innere_waechst_schneller_als_das_zwischen(self) -> None:
        msw = SKALENPROBE["msw_durchgehend"] / SKALENPROBE["msw_geschnitten"]
        msb = SKALENPROBE["msb_durchgehend"] / SKALENPROBE["msb_geschnitten"]

        assert msw == pytest.approx(5.18, abs=0.01)
        assert msb == pytest.approx(2.92, abs=0.01)
        assert msw > msb

    def test_und_damit_faellt_das_verhaeltnis(self) -> None:
        """Der ICC ist eine monotone Funktion von MSB/MSW."""
        vorher = (
            SKALENPROBE["msb_geschnitten"] / SKALENPROBE["msw_geschnitten"]
        )
        nachher = (
            SKALENPROBE["msb_durchgehend"] / SKALENPROBE["msw_durchgehend"]
        )

        assert vorher == pytest.approx(2.622, abs=0.001)
        assert nachher == pytest.approx(1.480, abs=0.001)

    def test_ein_gleichmaessiger_faktor_kuerzt_sich_heraus(self) -> None:
        """Die Rechnung dahinter, an der eigenen Funktion geprueft - sonst
        waere 'reiner Groesseneffekt' eine Behauptung ueber eine Formel, die
        niemand nachgesehen hat."""
        from research.unabhaengigkeit import designeffekt

        # Zehn Bloecke, weil 'designeffekt' unter MIND_BLOECKE = 8 nichts
        # zurueckgibt - mein erster Entwurf hatte vier und bekam None.
        bloecke = [
            [1.0, 2.0, 1.5],
            [3.0, 3.5, 2.8],
            [0.5, 0.2, 0.9],
            [2.0, 2.4, 1.9],
            [4.0, 4.6, 3.7],
            [1.2, 0.8, 1.6],
            [2.6, 3.1, 2.2],
            [0.3, 0.7, 0.1],
            [3.3, 2.9, 3.8],
            [1.8, 1.4, 2.1],
        ]
        gross = [[v * 7.0 for v in b] for b in bloecke]

        a = designeffekt(bloecke)
        b = designeffekt(gross)

        assert a is not None and b is not None
        assert a.icc == pytest.approx(b.icc)

    def test_ein_wachsender_faktor_nicht(self) -> None:
        """Und die Gegenprobe dazu: Waechst der Faktor von Block zu Block,
        aendert sich der ICC - genau der gemessene Fall."""
        from research.unabhaengigkeit import designeffekt

        # Zehn Bloecke, weil 'designeffekt' unter MIND_BLOECKE = 8 nichts
        # zurueckgibt - mein erster Entwurf hatte vier und bekam None.
        bloecke = [
            [1.0, 2.0, 1.5],
            [3.0, 3.5, 2.8],
            [0.5, 0.2, 0.9],
            [2.0, 2.4, 1.9],
            [4.0, 4.6, 3.7],
            [1.2, 0.8, 1.6],
            [2.6, 3.1, 2.2],
            [0.3, 0.7, 0.1],
            [3.3, 2.9, 3.8],
            [1.8, 1.4, 2.1],
        ]
        wachsend = [
            [v * (1 + i) for v in b] for i, b in enumerate(bloecke)
        ]

        a = designeffekt(bloecke)
        b = designeffekt(wachsend)

        assert a is not None and b is not None
        assert a.icc != pytest.approx(b.icc)

    def test_die_ungleichen_blockvarianzen_erklaeren_es_nicht(self) -> None:
        """Die schaerfere Vermutung, und sie ist widerlegt: Die log-Streuung
        der Blockvarianzen ordnet nicht mit dem ICC."""
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "ordnet nicht mit dem ICC" in text
        assert "3,775 bei" in text


class TestDasRMassIstBelastbar:
    def test_die_verteilung_ist_die_eines_trendfolgers(self) -> None:
        assert R_PROBE["min"] == pytest.approx(-1.030)
        assert R_PROBE["median"] == pytest.approx(-0.555)
        assert R_PROBE["p95"] == pytest.approx(19.986)

    def test_die_abhaengigkeit_ueberlebt_das_trimmen(self) -> None:
        """Worauf 411 und 412 sich stuetzen - geprueft, nicht angenommen."""
        assert R_PROBE["ueber_zehn"] == 13
        assert R_PROBE["icc_getrimmt"] < R_PROBE["icc_voll"]
        assert R_PROBE["p_getrimmt"] < 0.05

    def test_die_absurde_varianzspanne_ist_harmlos(self) -> None:
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "lauter\n#: ausgestoppten Trades" in text or (
            "ausgestoppten Trades" in text
        )
        assert "Harmlos" in text

    def test_und_erklaert_die_gepflegten_momente(self) -> None:
        """Der Nebenfund: Woher Schiefe 3,46 und Woelbung 15,92 kommen."""
        from research.referenz import SPOTPUNKT

        assert SPOTPUNKT.schiefe > 3.0
        assert SPOTPUNKT.woelbung > 10.0
        assert R_PROBE["p95"] / abs(R_PROBE["min"]) > 15


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_gegenprobe(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 413)

        assert "dieselben 160 Trades" in eintrag.ergebnis
        assert "3,55e-15" in eintrag.ergebnis

    def test_und_die_zerlegung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 413)

        assert "**5,18**" in eintrag.ergebnis
        assert "**2,92**" in eintrag.ergebnis

    def test_und_die_eigene_unpraezise_formulierung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 413)

        assert "Formulierung in 412 war unpraezise" in eintrag.ergebnis

    def test_und_412_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 412).zuletzt == 413
