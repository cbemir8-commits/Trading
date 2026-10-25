"""Wo der gemeldete Wert in seiner eigenen Spanne steht - Befund 419.

Befund 400 bis 402 haben die Streuung ueber Aufteilungen gemessen und daraus
die Urteile 'entschieden' und 'offen' gebaut. Was die Spanne nicht sagt: ob
gerade die **strenge** oder die **guenstige** Aufteilung berichtet wird. Zwei
Gates mit derselben Spanne stehen verschieden da.

Befund 418 hat das nebenbei fuer die wirksame Stichprobe gesehen - der
gemeldete Punkt liegt mit 115 am unteren Rand von 115 bis 119. Hier steht es
fuer jedes Gate.
"""

from __future__ import annotations

import inspect

import pytest

from research.aufteilung import (
    hoeher_ist_besser,
    rang_des_gemeldeten,
    rangzeile,
)


class TestDieRichtungKommtAusDemUrteil:
    """Keine gepflegte Liste der Richtungen - die waere die naechste Zahl,
    die wegdriftet (Befund 408)."""

    def test_ein_bestandenes_gate_ueber_seiner_schwelle(self) -> None:
        assert hoeher_ist_besser(-9.61, -10.0, bestanden=True)

    def test_ein_bestandenes_gate_unter_seiner_schwelle(self) -> None:
        """Drawdown besteht mit 9,87 unter 12 - klein ist gut."""
        assert not hoeher_ist_besser(9.87, 12.0, bestanden=True)

    def test_ein_gefallenes_gate_unter_seiner_schwelle(self) -> None:
        """Der Deflated Sharpe faellt mit 0,5826 unter 0,95 - gross ist gut."""
        assert hoeher_ist_besser(0.5826, 0.95, bestanden=False)

    def test_und_die_messlatte_genauso(self) -> None:
        assert hoeher_ist_besser(14.339, 15.0, bestanden=False)

    def test_an_allen_elf_gates_des_punktes(self) -> None:
        """Die Gegenprobe ueber den ganzen Satz: Die Ableitung muss fuer
        jedes Gate dasselbe sagen, was ein Mensch sagen wuerde."""
        erwartet = {
            ("Stichprobengroesse", 2250.0, 250.0, True): True,
            ("Messlatte", 14.339, 15.0, False): True,
            ("Out-of-Sample-Sharpe", 1.5762, 1.0, True): True,
            ("Drawdown", 9.8687, 12.0, True): False,
            ("Schlechtestes Jahr", -9.61, -10.0, True): True,
            ("Bestaendigkeit", 0.5806, 0.5, True): True,
            ("Monte-Carlo", 8.3265, 15.0, True): False,
            ("Regime-Aufteilung", 5.2751, 0.9, True): True,
            ("Deflated Sharpe", 0.5826, 0.95, False): True,
            ("Kosten-Stress", 1863.72, 0.0, True): True,
            ("Parameter-Plateau", 1.0, 0.6, True): True,
        }
        for (name, wert, schwelle, bestanden), soll in erwartet.items():
            assert hoeher_ist_besser(wert, schwelle, bestanden) is soll, name


class TestDerRang:
    def test_der_strengste_ist_rang_eins(self) -> None:
        assert rang_des_gemeldeten([1.0, 2.0, 3.0], gross_ist_gut=True) == (
            1,
            1,
            3,
        )

    def test_der_guenstigste_ist_der_letzte(self) -> None:
        assert rang_des_gemeldeten([3.0, 2.0, 1.0], gross_ist_gut=True) == (
            3,
            3,
            3,
        )

    def test_bei_klein_ist_gut_dreht_sich_die_richtung(self) -> None:
        assert rang_des_gemeldeten([3.0, 2.0, 1.0], gross_ist_gut=False) == (
            1,
            1,
            3,
        )

    def test_ohne_werte_ist_es_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="keinen Rang"):
            rang_des_gemeldeten([], gross_ist_gut=True)


class TestGleichstaendeWarenEinFehlerDerErstenFassung:
    """Die erste Fassung gab fuer ein Gate mit Spanne null 'Rang 1 von 11'
    zurueck - es stand da, als werde der strengste von elf Werten berichtet,
    obwohl alle elf gleich sind. Die falsche Richtung: Der Eindruck war
    konservativer als die Lage."""

    def test_alle_gleich_wird_als_solches_gemeldet(self) -> None:
        assert rangzeile([7.0] * 11, gross_ist_gut=True) == "alle 11 gleich"

    def test_und_nicht_mehr_als_rang_eins(self) -> None:
        assert rangzeile([7.0] * 11, gross_ist_gut=True) != "1/11"

    def test_teilweise_gleich_wird_ein_bereich(self) -> None:
        assert rangzeile(
            [2.0, 2.0, 1.0, 3.0], gross_ist_gut=True
        ) == "2-3/4"

    def test_eindeutig_bleibt_eine_zahl(self) -> None:
        assert rangzeile([1.0, 2.0, 3.0], gross_ist_gut=True) == "1/3"

    def test_der_kopf_nennt_den_fehler(self) -> None:
        text = rang_des_gemeldeten.__doc__ or ""

        assert "war ein Fehler der\n    ersten Fassung" in text
        assert "konservativer als die Lage" in text


class TestDerBefehlZeigtDieSpalte:
    def _quelle(self) -> str:
        import cli

        return inspect.getsource(cli.aufteilung)

    def test_die_spalte_heisst_rang(self) -> None:
        assert 'urteilstafel.add_column("Rang"' in self._quelle()

    def test_und_wird_aus_dem_urteil_abgeleitet(self) -> None:
        quelle = self._quelle()

        assert "hoeher_ist_besser(wert, schwelle," in quelle
        assert "rangzeile(jegate[name]" in quelle

    def test_die_zwei_groessen_zeile_hat_keinen_rang(self) -> None:
        """Die Messlatte traegt zwei Groessen (395) - ein Rang ueber zwei
        verschiedene Groessen waere keine Auskunft."""
        quelle = self._quelle()
        stelle = quelle.index('if spruch == "zwei Groessen"')

        assert '"-", "-", "-", farbe, "-"' in quelle[stelle : stelle + 400]


class TestWasGemessenIst:
    def test_alle_elf_gates_haben_einen_rang(self) -> None:
        from research.aufteilung import RANG_JE_GATE

        assert len(RANG_JE_GATE) == 11

    def test_der_deflated_sharpe_steht_in_der_mitte(self) -> None:
        """Der Ausfall, der das Projekt traegt, ist nicht schoengerechnet."""
        from research.aufteilung import RANG_JE_GATE

        assert RANG_JE_GATE["Deflated Sharpe"] == "5/11"

    def test_das_schlechteste_jahr_steht_guenstig(self) -> None:
        """Und das schaerft die offene Richtung 395: Das Guthaben von 0,39
        Punkten ist am guenstigen Rand gemessen."""
        from research.aufteilung import RANG_JE_GATE

        assert RANG_JE_GATE["Schlechtestes Jahr"] == "9/11"

    def test_out_of_sample_steht_streng(self) -> None:
        from research.aufteilung import RANG_JE_GATE

        assert RANG_JE_GATE["Out-of-Sample-Sharpe"] == "2/11"

    def test_kein_systematischer_vorteil(self) -> None:
        """Waere der massgebliche Lauf die guenstige Aufteilung, stuenden
        hier ueberall hohe Zahlen."""
        from research.aufteilung import RANG_JE_GATE

        eindeutig = [
            int(r.split("/")[0])
            for r in RANG_JE_GATE.values()
            if "/" in r and "-" not in r
        ]

        assert min(eindeutig) <= 2
        assert max(eindeutig) >= 9
        assert sum(eindeutig) / len(eindeutig) < 7

    def test_der_eintrag_nennt_den_eigenen_fehler(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 419)

        assert "Rang 1 von 11" in eintrag.ergebnis
        assert "konservativer war als die Lage" in eintrag.ergebnis
        assert "von scheinbar 4 auf 4-9" in eintrag.ergebnis

    def test_und_418_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 418).zuletzt == 419
