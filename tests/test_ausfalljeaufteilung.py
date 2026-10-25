"""Welches Gate faellt, haengt an der Aufteilung - Befund 420.

``cli aufteilung`` zaehlt seit Befund 400 die bestandenen Gates je Aufteilung,
und beim gemeldeten Stand stehen 9 von 11. Nie ausgesprochen war, dass es nicht
je Aufteilung dieselben zwei sind.
"""

from __future__ import annotations

import inspect

import pytest

from research.aufteilung import (
    AUSFALL_JE_AUFTEILUNG,
    DSR_JE_AUFTEILUNG,
    JAHRESRENDITE_JE_AUFTEILUNG,
    VERSATZ,
)


class TestDreiGatesFallenUeberhaupt:
    def test_und_nur_drei(self) -> None:
        assert set(AUSFALL_JE_AUFTEILUNG) == {
            "Deflated Sharpe",
            "Schlechtestes Jahr",
            "Messlatte",
        }

    def test_jede_liste_passt_in_die_versaetze(self) -> None:
        for gate, wo in AUSFALL_JE_AUFTEILUNG.items():
            assert set(wo) <= set(VERSATZ), gate
            assert len(set(wo)) == len(wo), gate


class TestDerDeflatedSharpeFaelltUeberall:
    def test_bei_allen_elf(self) -> None:
        assert AUSFALL_JE_AUFTEILUNG["Deflated Sharpe"] == tuple(VERSATZ)

    def test_und_keiner_der_werte_besteht(self) -> None:
        assert len(DSR_JE_AUFTEILUNG) == len(VERSATZ)
        assert max(DSR_JE_AUFTEILUNG) < 0.95

    def test_dem_besten_fehlen_fast_drei_zehntel(self) -> None:
        assert 0.95 - max(DSR_JE_AUFTEILUNG) == pytest.approx(0.2954, abs=5e-4)


class TestDieMesslatteFaelltNurImGemeldetenStand:
    def test_bei_genau_einem_versatz(self) -> None:
        assert AUSFALL_JE_AUFTEILUNG["Messlatte"] == (0,)

    def test_und_das_ist_der_gemeldete(self) -> None:
        assert 0 in AUSFALL_JE_AUFTEILUNG["Messlatte"]

    def test_weil_dort_die_jahresrendite_am_kleinsten_ist(self) -> None:
        """Der gemeldete Stand ist fuer dieses Gate der strengste von elf -
        was die Rangspalte aus 419 nicht zeigen konnte, weil die Messlatte
        zwei Groessen traegt (395)."""
        assert JAHRESRENDITE_JE_AUFTEILUNG[0] == min(
            JAHRESRENDITE_JE_AUFTEILUNG
        )
        assert JAHRESRENDITE_JE_AUFTEILUNG[0] < 15.0

    def test_und_alle_anderen_bestehen_sie(self) -> None:
        andere = JAHRESRENDITE_JE_AUFTEILUNG[1:]

        assert min(andere) > 15.0
        assert len(andere) == 10


class TestEinBestandenesGateFaelltOefter:
    """Der unbequemste Teil des Befundes."""

    def test_schlechtestes_jahr_faellt_bei_fuenf(self) -> None:
        assert AUSFALL_JE_AUFTEILUNG["Schlechtestes Jahr"] == (4, 6, 7, 8, 9)

    def test_also_oefter_als_die_messlatte(self) -> None:
        assert len(AUSFALL_JE_AUFTEILUNG["Schlechtestes Jahr"]) > len(
            AUSFALL_JE_AUFTEILUNG["Messlatte"]
        )

    def test_und_es_gilt_im_bericht_als_bestanden(self) -> None:
        """Geprueft an der Quelle, die es fuehrt: 'GATEKREUZ' nennt die
        gefallenen Gates je Messaufbau. Mein erster Entwurf fragte
        'SPOTPUNKT' nach einem Feld 'offen', das es dort nicht gibt - die
        Zusicherung war damit immer wahr."""
        from research.grenzgedaechtnis import GATEKREUZ

        gemeldet = GATEKREUZ[(False, True)]

        assert "Schlechtestes Jahr" not in gemeldet
        assert set(gemeldet) == {"Messlatte", "Deflated Sharpe"}
        assert 0 not in AUSFALL_JE_AUFTEILUNG["Schlechtestes Jahr"]

    def test_die_blocker_sind_geordnet(self) -> None:
        """DSR (11) > Schlechtestes Jahr (5) > Messlatte (1) - und die
        beiden gemeldeten offenen sind der erste und der letzte."""
        nach_zahl = sorted(
            AUSFALL_JE_AUFTEILUNG.items(), key=lambda p: -len(p[1])
        )

        assert [name for name, _ in nach_zahl] == [
            "Deflated Sharpe",
            "Schlechtestes Jahr",
            "Messlatte",
        ]


class TestWasNichtFolgt:
    def test_der_kopf_schliesst_die_versatzwahl_aus(self) -> None:
        import research.aufteilung as a
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(a))

        assert 'dass die Messlatte "eigentlich" besteht' in text
        assert "kein Versatz ist der richtige" in text

    def test_und_nennt_den_dritten_hinweis_zu_395(self) -> None:
        import research.aufteilung as a
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(a))

        assert "dritte Hinweis" in text


class TestDerBefehlSagtEsVonSelbst:
    def _quelle(self) -> str:
        import cli

        return inspect.getsource(cli.aufteilung)

    def test_er_sammelt_die_gefallenen_je_versatz(self) -> None:
        assert "gefallen_je_versatz[weg]" in self._quelle()

    def test_und_druckt_sie(self) -> None:
        quelle = self._quelle()

        assert "Welches Gate faellt wo?" in quelle
        assert "je_gate_gefallen" in quelle

    def test_und_nennt_die_lehre_dazu(self) -> None:
        quelle = self._quelle()

        assert "traegt weniger" in quelle
        assert "wer sich einen aussucht, lockert das Gate" in quelle


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_ordnung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 420)

        assert "11 von 11" in eintrag.ergebnis
        assert "der erste und der **letzte**" in eintrag.ergebnis

    def test_und_dass_der_gemeldete_stand_streng_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 420)

        assert "strengste " in eintrag.ergebnis
        assert "14,3391" in eintrag.ergebnis

    def test_und_419_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 419).zuletzt == 420
