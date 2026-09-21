"""Was Gebuehren in R kosten - und was die Tabelle davon zeigte.

``research/costfloor.py`` war bis Befund 325 das einzige Forschungsmodul
**ohne einen einzigen Test**. Sein Kopf sagt, warum das schlecht ist:

    Weil es eine pruefbare Zahl ist und keine Meinung.

Gefunden hat den Fehler nicht die Rechnung, sondern die Beschriftung.
``cli kosten`` zeigte unter "Gebuehren je Trade":

    cost_win_r + cost_loss_r

Das ist, was ein Gewinner **und** ein Verlierer zusammen kosten. Ein Trade
ist aber das eine oder das andere - die Summe beschreibt ein **Paar**. Bei
1 % Stop standen dort 0,165 R statt 0,088 R, also das 1,9-fache; bei 0,15 %
Stop 1,100 R statt 0,495 R, das 2,2-fache.

Die richtige Zahl war die ganze Zeit da: ``floor_table`` gibt sie als
vierten Wert zurueck, und die Schleife hat ihn mit ``_`` weggeworfen.
Dieselbe Bauart wie in den Befunden 152, 154, 155 und 160 - gebaut,
gerechnet, nicht angeschlossen.
"""

from __future__ import annotations

import pytest

from backtest.costs import CostModel
from research.costfloor import CostFloor, cost_floor, floor_table


class TestDieUmrechnungInR:
    """Der Gedanke des Moduls: Gebuehren zaehlen als Anteil am **Risiko**,
    und der Umrechnungsfaktor ist die Stop-Distanz."""

    def test_der_enge_stop_ist_teurer(self) -> None:
        eng, weit = cost_floor(0.2), cost_floor(1.0)

        assert eng.cost_loss_r > weit.cost_loss_r

    def test_und_zwar_umgekehrt_proportional(self) -> None:
        """Fuenfmal engerer Stop, fuenfmal teurer - das ist die Aussage aus
        dem Modulkopf, als Rechnung."""
        eng, weit = cost_floor(0.2), cost_floor(1.0)

        assert eng.cost_loss_r == pytest.approx(weit.cost_loss_r * 5.0)
        assert eng.cost_win_r == pytest.approx(weit.cost_win_r * 5.0)

    def test_der_verlierer_ist_die_teure_seite(self) -> None:
        """Einstieg als Maker, Stop als Taker - und der Stop rutscht."""
        boden = cost_floor(1.0)

        assert boden.cost_loss_r > boden.cost_win_r

    def test_ohne_stop_gibt_es_keine_umrechnung(self) -> None:
        with pytest.raises(ValueError, match="groesser als null"):
            cost_floor(0.0)

    def test_die_saetze_kommen_aus_dem_kostenmodell(self) -> None:
        """Nicht aus einer zweiten Tabelle, die danebenlaufen koennte."""
        kosten = CostModel()
        boden = cost_floor(1.0, kosten)
        maker = float(kosten.maker_fee_rate) * 100.0

        assert boden.cost_win_r == pytest.approx(2 * maker / 1.0)


class TestDieNoetigeTrefferquote:
    def test_ohne_kosten_waere_es_die_lehrbuchformel(self) -> None:
        """``1 / (rr + 1)`` - bei 1,5:1 also 40 %."""
        frei = CostFloor(stop_pct=1.0, cost_win_r=0.0, cost_loss_r=0.0)

        assert frei.required_win_rate(1.5) == pytest.approx(0.4)

    def test_gebuehren_heben_sie(self) -> None:
        assert cost_floor(1.0).required_win_rate(1.5) > 0.4

    def test_ein_engerer_stop_hebt_sie_weiter(self) -> None:
        assert cost_floor(0.2).required_win_rate(1.5) > cost_floor(
            1.0
        ).required_win_rate(1.5)

    def test_bei_unmoeglichen_kosten_bleibt_sie_bei_eins(self) -> None:
        """Ein Nenner unter null waere eine Trefferquote ueber 100 % - die
        Aussage ist "geht nicht" und keine Zahl."""
        absurd = CostFloor(stop_pct=0.01, cost_win_r=99.0, cost_loss_r=0.0)

        assert absurd.required_win_rate(1.5) == 1.0


class TestDerRohvorteilIstDerErwartungswert:
    """**Der Kern von Befund 325.**

    ``edge_needed_r`` ist nicht irgendeine Groesse neben den Kosten - es
    **ist** der erwartete Gebuehrenbetrag je Trade bei der noetigen
    Trefferquote. Das folgt aus der Nullbedingung und laesst sich
    nachrechnen.
    """

    @pytest.mark.parametrize("stop", [0.15, 0.2, 0.5, 1.0, 3.0])
    def test_er_gleicht_den_erwarteten_gebuehren(self, stop: float) -> None:
        boden = cost_floor(stop)
        p = boden.required_win_rate(1.5)
        erwartet = p * boden.cost_win_r + (1.0 - p) * boden.cost_loss_r

        assert boden.edge_needed_r(1.5) == pytest.approx(erwartet)

    def test_und_liegt_zwischen_den_beiden_faellen(self) -> None:
        """Ein Erwartungswert kann nicht ausserhalb liegen - die Summe
        dagegen liegt **ueber** beiden."""
        boden = cost_floor(1.0)
        je_trade = boden.edge_needed_r(1.5)

        assert boden.cost_win_r < je_trade < boden.cost_loss_r
        assert boden.cost_win_r + boden.cost_loss_r > boden.cost_loss_r

    @pytest.mark.parametrize("stop", [0.15, 1.0])
    def test_die_summe_ueberschaetzt_um_fast_das_doppelte(
        self, stop: float
    ) -> None:
        """Die Zahl, die bis Befund 325 als 'Gebuehren je Trade' dastand."""
        boden = cost_floor(stop)
        summe = boden.cost_win_r + boden.cost_loss_r

        assert summe / boden.edge_needed_r(1.5) > 1.8


class TestDieTabelle:
    def test_sie_gibt_vier_werte_je_zeile(self) -> None:
        zeilen = floor_table(rr=1.5)

        assert zeilen
        for zeile in zeilen:
            assert len(zeile) == 4

    def test_der_vierte_ist_der_erwartungswert(self) -> None:
        """Der Wert, den ``cli kosten`` bis Befund 325 weggeworfen hat."""
        for stop, _quote, _summe, je_trade in floor_table(rr=1.5):
            assert je_trade == pytest.approx(cost_floor(stop).edge_needed_r(1.5))

    def test_die_trefferquote_faellt_mit_weiterem_stop(self) -> None:
        quoten = [q for _s, q, _x, _y in floor_table(rr=1.5)]

        assert quoten == sorted(quoten, reverse=True)


class TestDerBefehlZeigtDenErwartungswert:
    """**Die Verdrahtung** - die Rechnung war richtig, die Anzeige nicht."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "kosten"
        )

    def test_die_summe_wird_nicht_mehr_angezeigt(self) -> None:
        quelle = self._quelle()

        assert "_summe" in quelle, "sie wird entpackt und nicht benutzt"
        assert "je_trade" in quelle

    def test_beide_faelle_stehen_daneben(self) -> None:
        """Damit die Zahl einzuordnen ist: Ein Trade zahlt entweder den
        einen oder den anderen Preis."""
        quelle = self._quelle()

        assert "Gewinner" in quelle
        assert "Verlierer" in quelle
        assert "nie beide" in quelle
