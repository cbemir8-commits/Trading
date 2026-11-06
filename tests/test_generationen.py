"""Welche Generationen es gibt - Befund 459.

``cli wettbewerb --generation`` sagte: *"Startkatalog. 7 = Scalp-Setups, 8 =
Abfolge-Modell und Short-Seite."* Zehn Generationen gibt es, zwei nannte
dieser Satz, und die beiden neuesten (9 und 10) sind fuer **Tageskerzen**
gedacht - die Kerzenlaenge, auf der der Spitzenkandidat steht. Wer eine
daily-Runde fahren wollte, musste ``seeds.py`` lesen.

Diese Tests halten fest, dass die Uebersicht **abgeleitet** ist: Sie kann
nicht veralten, weil sie nicht gepflegt wird.
"""

from __future__ import annotations

import pytest

from research.generationen import Generationsbild, bericht, uebersicht
from research.seeds import GENERATIONS, VORGESEHEN, load_seeds, passt_zum_intervall

#: Gemessen (Befund 459): Die Finanzierungsabhaengigkeit sitzt in zwei
#: Generationen - 4 (alle drei) und 5 (zwei von drei).
FINANZIERUNG_JE_GENERATION = {4: 3, 5: 2}

#: Die Summen je Kerzenlaenge - und sie sind gegengeprueft: 25 ist die Zahl,
#: die ``vorratsdecke -i D`` gefahren hat (456), 39 die der 15m-Laeufe (450).
SUMMEN = {"D": 25, "15": 39}


class TestDieUebersichtIstAbgeleitet:
    def test_sie_deckt_genau_die_vorhandenen_generationen(self) -> None:
        nummern = [b.nummer for b in uebersicht()]

        assert nummern == sorted(GENERATIONS)

    def test_jede_kerzenlaenge_kommt_aus_vorgesehen(self) -> None:
        for b in uebersicht():
            assert b.intervall == VORGESEHEN.get(b.nummer)

    def test_jede_genomzahl_kommt_aus_dem_katalog(self) -> None:
        for b in uebersicht():
            assert b.namen == tuple(g.name for g in load_seeds(b.nummer))
            assert b.genome == len(b.namen)

    def test_die_namen_sind_nicht_leer(self) -> None:
        for b in uebersicht():
            assert b.genome > 0, b.nummer
            assert all(n.strip() for n in b.namen), b.nummer


class TestWasGemessenIst:
    def test_die_finanzierung_sitzt_in_zwei_generationen(self) -> None:
        """Und die, die man heute faehrt, brauchen keine - 8 auf
        Viertelstunden, 9 und 10 auf Tageskerzen."""
        gezaehlt = {
            b.nummer: len(b.finanzierung) for b in uebersicht() if b.finanzierung
        }

        assert gezaehlt == FINANZIERUNG_JE_GENERATION
        for nummer in (8, 9, 10):
            b = next(x for x in uebersicht() if x.nummer == nummer)
            assert b.finanzierung == (), nummer

    @pytest.mark.parametrize(("intervall", "summe"), sorted(SUMMEN.items()))
    def test_die_summe_je_kerzenlaenge_stimmt_mit_den_laeufen(
        self, intervall: str, summe: int
    ) -> None:
        """**Die Gegenprobe.** 25 auf Tageskerzen ist die Zahl, die Befund 456
        gefahren hat, 39 auf Viertelstunden die der Stuecke aus 450. Weicht
        das ab, ist eine der beiden Seiten falsch."""
        passend = [
            b for b in uebersicht() if passt_zum_intervall(b.nummer, intervall)
        ]

        assert sum(b.genome for b in passend) == summe

    def test_die_zahl_steht_auch_im_bericht(self) -> None:
        text = " ".join(bericht(intervall="D").split())

        assert f"{SUMMEN['D']} Genomen zusammen" in text
        assert "kostet keinen Versuch" in text


class TestDerBerichtUnterscheidetDieBeidenKataloge:
    """**Zwei Begriffe von "Katalog"**, und beide sind richtig. Ein Bericht,
    der sie nicht trennt, laedt zu der Verwechslung ein, die mich hierher
    gebracht hat: Ein Probelauf meldete *"Runde 1 - 1 Kandidaten (Katalog)"*,
    waehrend ``vorratsdecke -i D`` 25 misst."""

    def test_er_sagt_dass_wettbewerb_eine_generation_faehrt(self) -> None:
        text = " ".join(bericht().split())

        assert "faehrt genau **eine** Generation, nicht alle" in text
        assert "Wiederholungsversuch hebt die Huerde" in text

    def test_und_nennt_die_neueste(self) -> None:
        text = " ".join(bericht().split())
        neueste = uebersicht()[-1]

        assert f"Die neueste ist {neueste.nummer}" in text
        assert neueste.nummer == max(GENERATIONS)

    def test_ohne_intervall_keine_summe(self) -> None:
        """Eine Summe ohne Kerzenlaenge waere die Verwechslung selbst."""
        text = bericht()

        assert "Genomen zusammen" not in text

    def test_mit_intervall_werden_die_passenden_markiert(self) -> None:
        zeilen = bericht(intervall="D").splitlines()
        markiert = {
            int(z.split()[1]) for z in zeilen if z.startswith("->")
        }
        erwartet = {g for g in GENERATIONS if passt_zum_intervall(g, "D")}

        assert markiert == erwartet


class TestDerBefehl:
    def test_er_laeuft_und_zeigt_alle_generationen(self) -> None:
        from typer.testing import CliRunner

        from cli import app

        ergebnis = CliRunner().invoke(app, ["generationen"])

        assert ergebnis.exit_code == 0, ergebnis.output[-800:]
        for g in GENERATIONS:
            assert f" {g:>2} " in ergebnis.output or f" {g} " in ergebnis.output

    @staticmethod
    def _hilfe(befehl: str, option: str) -> str:
        """Der **erklaerte** Hilfetext einer Option, nicht der gedruckte.

        Am gedruckten zu pruefen ist hier falsch: 'rich' bricht bei 80 Spalten
        mitten in *'cli generationen'* um und setzt den Rahmenstrich dazwischen
        - aus "'cli generationen'" wird "'cli │ generationen'". Das ist die
        bruechige Zusicherung aus Befund 420/430, und ``" ".join(split())``
        hilft dagegen nicht, weil der Strich kein Leerraum ist.
        """
        import inspect

        import cli as modul

        angabe = inspect.signature(getattr(modul, befehl)).parameters[option]
        return str(angabe.default.help)

    def test_die_hilfe_zaehlt_keine_generationen_mehr_auf(self) -> None:
        """**Die Wache gegen den Rueckfall.** Hier stand eine Liste von Hand,
        und sie war drei Generationen alt. Ein Verweis kann nicht veralten."""
        hilfe = self._hilfe("wettbewerb", "generation")

        assert "cli generationen" in hilfe
        assert "Scalp-Setups" not in hilfe
        assert "Abfolge-Modell und Short-Seite" not in hilfe
        assert "eine** Generation, nicht alle" in hilfe

    def test_auch_korb_verweist_darauf(self) -> None:
        assert "cli generationen" in self._hilfe("korb", "generation")

    def test_und_der_verweis_kommt_auch_gedruckt_an(self) -> None:
        """Gegenprobe am gedruckten Text - mit dem einen Wort, das den
        Umbruch ueberlebt."""
        from typer.testing import CliRunner

        from cli import app

        for befehl in ("wettbewerb", "korb"):
            aus = CliRunner().invoke(app, [befehl, "--help"]).output

            assert "generationen" in aus, befehl


class TestDasBildSelbst:
    def test_ohne_festgelegte_kerzenlaenge_heisst_es_frei(self) -> None:
        bild = Generationsbild(nummer=1, intervall=None, namen=("a",), finanzierung=())

        assert "frei" in bild.zeile()

    def test_der_hinweis_steht_nur_wo_er_zutrifft(self) -> None:
        ohne = Generationsbild(nummer=1, intervall="D", namen=("a",), finanzierung=())
        mit = Generationsbild(
            nummer=4, intervall="D", namen=("a", "b"), finanzierung=("a",)
        )

        assert "Finanzierungsdaten" not in ohne.zeile()
        assert "1 brauchen Finanzierungsdaten" in mit.zeile()
