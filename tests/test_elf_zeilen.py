"""Die elf Zeilen hinter "9 von 11" standen in keiner Ausgabe - Befund 394.

Die Zahl steht im ganzen Projekt: im Register, im Statusschirm, in jedem
Bericht. **Welche** neun und mit welchem Abstand, stand nirgends.

- ``cli stand`` hat einen Abschnitt "DIE GATES IM EINZELNEN" mit allen elf
  Zeilen - aber fuer den **berichteten** Punkt, also Perpetual auf dem
  Speicher. Mein erster Entwurf hat behauptet, es gebe die Tafel nirgends, und
  eine zweite daneben gebaut; ein Test dieser Datei hat die Stelle gefunden.
- ``cli anatomie`` zeigt eine Wert/Schwelle-Tafel, aber nur fuer die Gates, die
  zwischen zwei Fassungen **kippen** - die neun, die auf beiden Seiten halten,
  kommen dort nie mit ihren Werten vor.

Gemessen am Spot-Punkt auf der Zulassungsreihe:

    Gate                      Wert    Schwelle   Abstand
    Stichprobengroesse   2250,0000    250,0000   2000,0000 Reserve
    Messlatte              14,3390     15,0000      0,6610 fehlt
    Out-of-Sample-Sharpe    1,5762      1,0000      0,5762 Reserve
    Drawdown                9,8687     12,0000      2,1313 Reserve
    Schlechtestes Jahr     -9,6100    -10,0000      0,3900 Reserve
    Bestaendigkeit          0,5806      0,5000      0,0806 Reserve
    Monte-Carlo             8,3265     15,0000      6,6735 Reserve
    Regime-Aufteilung       5,2751      0,9000      4,3751 Reserve
    Deflated Sharpe         0,5826      0,9500      0,3674 fehlt
    Kosten-Stress        1863,7259      0,0000   1863,7259 Reserve
    Parameter-Plateau       1,0000      0,6000      0,4000 Reserve

**Die Zahl ist ehrlich**: kein Gate uebersprungen, alle neun mit Status PASS.
Das war nicht selbstverstaendlich - ``GateResult.passed`` zaehlt einen SKIP als
bestanden (Befunde 321/322).
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.gates import GateStatus
from research.referenz import SPOTPUNKT


class TestDerSpotpunktStehtAufDerReihe:
    """Er ist der Punkt aus ``referenz.py`` - gerechnet wurde er auf allem,
    was da ist (157 Trades, Guete 0,2781, DSR 0,7237 gegen 156, 0,2708 und
    0,5826). Die Gate-Zahl war beidesmal 9 von 11, deshalb fiel es nicht auf.
    """

    def test_der_statusschirm_schneidet_fuer_ihn(self) -> None:
        quelle = inspect.getsource(cli.stand)

        assert "spotrahmen = alle_geschnitten(frames)" in quelle
        assert "spotrahmen, symbole, genome, trials, settings" in quelle

    def test_und_nennt_die_reihe_ueber_der_tafel(self) -> None:
        quelle = inspect.getsource(cli.stand)

        assert "reihenzeile(spotrahmen)" in quelle

    def test_der_kopf_bleibt_auf_allem_was_da_ist(self) -> None:
        """Befund 370 hat das entschieden, und es gilt weiter: 'Auf allem zu
        rechnen, was da ist, ist richtig; es muss nur dastehen.' Geschnitten
        wird nur fuer den Punkt, der neben 'referenz.py' steht."""
        quelle = inspect.getsource(cli.stand)

        assert "frames = common_range(roh)" in quelle
        assert "Perpetual auf dem Speicher" in quelle
        assert "reihenzeile(frames)" in quelle


class TestDieTafel:
    """**Keine zweite Tafel.** Die vorhandenen Zeilen tragen den Spot-Abstand
    daneben - zwei Renderings derselben Sache waeren genau das, was dieses
    Projekt sonst abstellt."""

    def test_die_vorhandenen_zeilen_tragen_den_spot_abstand(self) -> None:
        quelle = inspect.getsource(cli.stand)

        assert "DIE GATES IM EINZELNEN" in quelle
        assert "spoturteil = {r.name: r for r in spotgates or ()}" in quelle
        assert "Spot {weite:.3f} Reserve" in quelle

    def test_und_jede_spalte_nennt_ihre_reihe(self) -> None:
        """Zwei Reihen in einer Tafel sind sonst das, wovor Befund 387 warnt."""
        quelle = inspect.getsource(cli.stand)

        assert "Perpetual auf dem Speicher" in quelle
        assert "Spot auf der Zulassungsreihe" in quelle

    def test_der_abstand_traegt_kein_vorzeichen(self) -> None:
        """Die Richtung der Schwelle steht nicht im ``GateResult``: Beim
        Rueckgang ist weniger besser, beim Sharpe mehr, und ein '-2,13' hiesse
        dort Reserve und hier Fehlbetrag."""
        quelle = inspect.getsource(cli.stand)

        assert "weite = abs(s.value - s.threshold)" in quelle
        assert "Reserve" in quelle
        assert "fehlt" in quelle
        assert "{s.value - s.threshold:+" not in quelle

    def test_und_ein_uebersprungenes_gate_bekommt_keinen(self) -> None:
        """Es ist nicht geurteilt, und ``passed`` waere dort True (321/322)."""
        quelle = inspect.getsource(cli.stand)

        assert "GateStatus.PASS" in quelle
        assert "GateStatus.FAIL" in quelle
        assert "Spot {s.status.value}" in quelle

    def test_der_spot_teil_urteilt_am_status_nicht_an_passed(self) -> None:
        """Die Perpetual-Spalte benutzt weiter ``passed`` - sie ist nicht Teil
        dieses Befundes. Der **neue** Teil urteilt am Status, denn ein
        uebersprungenes Gate zaehlt in ``passed`` als bestanden (321/322)."""
        quelle = inspect.getsource(cli.stand)
        spotteil = quelle.split("spoturteil = ")[1]

        assert "s.status" in spotteil
        assert "if s.passed" not in spotteil


class TestDieHilfsfunktionGibtDieGatesHeraus:
    def test_sie_liefert_ein_paar(self) -> None:
        quelle = inspect.getsource(cli._spotpunkt)

        assert "return gates.results, Betriebspunkt(" in quelle
        assert "return None, None" in quelle

    def test_und_sagt_warum(self) -> None:
        text = cli._spotpunkt.__doc__ or ""

        assert "Zulassungsreihe" in text
        assert "0,2781" in text, "die Zahl des Speichers bleibt als Vermerk"
        assert "0,5826" in text
        assert "elf Zeilen" in text


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    """Die Tafel aus dem Kopf, am Lauf nachgeprueft."""

    @staticmethod
    def _gates():
        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten
        from research.gates import evaluate_gates
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        e = get_settings()
        store = CandleStore(e.paths.data_store)
        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        frames = common_range(
            alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        )
        genom = cli._ohne_hebel(spitzenkandidat())
        configs = cli._spotconfigs(symbole, e)
        bericht = run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), configs
        )
        return evaluate_gates(
            genom, bericht, next(iter(frames.values())), configs[symbole[0]],
            trials_so_far=SPOTPUNKT.versuche, frames=frames, configs=configs,
        )

    def test_kein_gate_ist_uebersprungen(self) -> None:
        """Der Kern der Gegenprobe: Die Neun ist keine Neun aus Aussetzern."""
        gates = self._gates()

        assert not [r for r in gates.results if r.status is GateStatus.SKIP]

    def test_neun_tragen_status_pass(self) -> None:
        gates = self._gates()
        echte = [r for r in gates.results if r.status is GateStatus.PASS]

        assert len(gates.results) == SPOTPUNKT.gesamt
        assert len(echte) == SPOTPUNKT.bestanden

    def test_und_es_sind_diese_beiden_offen(self) -> None:
        gates = self._gates()
        offen = {r.name for r in gates.results if r.status is GateStatus.FAIL}

        assert offen == {"Messlatte", "Deflated Sharpe"}

    @pytest.mark.parametrize(
        ("name", "wert", "schwelle"),
        [
            ("Messlatte", 14.3390, 15.0),
            ("Deflated Sharpe", 0.5826, 0.95),
            ("Drawdown", 9.8687, 12.0),
            ("Schlechtestes Jahr", -9.6100, -10.0),
            ("Stichprobengroesse", 2250.0, 250.0),
            ("Kosten-Stress", 1863.7259, 0.0),
        ],
    )
    def test_die_zeilen_der_tafel(
        self, name: str, wert: float, schwelle: float
    ) -> None:
        gates = self._gates()
        r = next(x for x in gates.results if x.name == name)

        assert r.value == pytest.approx(wert, abs=0.001)
        assert r.threshold == pytest.approx(schwelle, abs=0.001)

    def test_die_stichprobengroesse_zaehlt_tage_im_markt(self) -> None:
        """2250 gegen 250 sind **Tage**, nicht Trades: Der Kandidat
        dimensioniert nach Kapitalanteil und faellt in den zweiten Zweig des
        Gates. Bei 2922 Tagen Reihe sind das 77 % der Zeit im Markt."""
        gates = self._gates()
        r = next(x for x in gates.results if x.name == "Stichprobengroesse")

        assert "Tage im Markt" in r.message
        assert r.value / 2922 == pytest.approx(0.77, abs=0.01)

    def test_und_der_kostenstress_den_gewinn(self) -> None:
        gates = self._gates()
        r = next(x for x in gates.results if x.name == "Kosten-Stress")

        assert "fachen Kosten" in r.message
        assert r.threshold == 0.0
        assert r.value > 0


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_gegenprobe(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 394)

        assert "Kein Gate ist uebersprungen" in eintrag.ergebnis
        assert "321/322" in eintrag.ergebnis

    def test_und_die_beiden_geprueften_paare(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 394)

        assert "2250" in eintrag.ergebnis
        assert "Tage im Markt" in eintrag.ergebnis
        assert "1863,7259" in eintrag.ergebnis

    def test_und_die_luecke(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 394)

        assert "schmaler, als ich zuerst geschrieben habe" in eintrag.ergebnis
        assert "kippen" in eintrag.ergebnis
        assert "zwei Tafeln fuer eine Sache" in eintrag.ergebnis

    def test_und_393_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 393).zuletzt == 394
