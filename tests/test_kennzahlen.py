"""Regeln, die auf dieser Reihe nichts ausloesen koennen - Befund 326.

Die offene Frage aus Befund 322/323 lautete: zwoelf Regeln handeln null Mal
und stammen aus "Generationen ohne vermerkte Kerzenlaenge (1, 2, 4)". Das
klang nach einer Frage. Gemessen sind es zwei:

    Gen  auf D: Kandidaten/Regeln  Trades   auf 15: Kand/Regeln  Trades
      1            1/5                  6          5/5             670
      2            0/5                  0          5/5            1444
      4            0/3                  0          0/3               0

Neun davon (vier aus 1, fuenf aus 2) sind eine Frage der Kerzenlaenge. Die
drei aus Generation 4 sind es nicht - sie brauchen die Finanzierungsrate, und
der Kassamarkt hat keine. Dazu kommen zwei aus Generation 5, der Generation
des Spitzenkandidaten, die niemand auf dieser Liste vermutet haette.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import get_settings
from core.models import Interval
from data.store import CandleStore
from research.kennzahlen import Lage, gebrauchte_kennzahlen, lage, stumme
from research.seeds import GENERATIONS, VORGESEHEN


@pytest.fixture(scope="module")
def tageskerzen() -> pd.DataFrame:
    einstellungen = get_settings()
    return CandleStore(einstellungen.paths.data_store).read(
        "BTCUSD_BITSTAMP", Interval("D")
    )


class TestWasEineRegelBraucht:
    def test_nur_kennzahlen_zaehlen(self) -> None:
        """Der Kurs ist auf jeder Kerzenreihe da, eine Konstante ist keine
        Messung - gefragt ist, was von den Daten abhaengt."""
        genom = GENERATIONS[4][1]()  # Funding-Carry Long

        gebraucht = gebrauchte_kennzahlen(genom)

        assert gebraucht == ("indicator:funding_avg(period=21)",)

    def test_derselbe_operand_zaehlt_einmal(self) -> None:
        """'Gegen die ueberhitzte Long-Seite' fragt ``funding_zscore(90)`` in
        Ein- und Ausstieg ab; gebraucht ist er trotzdem einmal."""
        genom = GENERATIONS[4][2]()

        gebraucht = gebrauchte_kennzahlen(genom)

        assert len(gebraucht) == len(set(gebraucht))


class TestWasDieReiheNichtHat:
    """**Der Kern von Befund 326.**"""

    @pytest.mark.daten
    def test_die_finanzierungsrate_fehlt_auf_dem_kassamarkt(
        self, tageskerzen
    ) -> None:
        """Nicht "manchmal leer" - auf allen Balken leer.

        Bitstamp ist ein Kassamarkt. Es gibt dort keine Finanzierungsrate,
        also auch keinen Mittelwert und keinen z-Wert davon.
        """
        import strategy.indicators as ind

        for name, periode in (("funding_avg", 21), ("funding_zscore", 90)):
            reihe = pd.Series(getattr(ind, name)(tageskerzen, period=periode))

            assert reihe.isna().all(), name

    @pytest.mark.daten
    def test_generation_4_ist_vollstaendig_stumm(self, tageskerzen) -> None:
        """Alle drei Regeln, aus demselben Grund."""
        genome = [bauen() for bauen in GENERATIONS[4]]

        verstummt = stumme(genome, tageskerzen)

        assert len(verstummt) == 3
        for x in verstummt:
            assert any("funding" in k for k in x.leer), x.leer

    @pytest.mark.daten
    def test_auch_zwei_regeln_der_spitzengeneration(self, tageskerzen) -> None:
        """**Der unerwartete Teil.**

        Generation 5 ist die Generation des Spitzenkandidaten und steht auf
        "D". Zwei ihrer drei Regeln stuetzen sich auf die Finanzierungsrate
        und koennen am Kassa-Betriebspunkt nie ausloesen - das erklaert die
        Messung "1 von 3 Kandidaten, 6 Trades" ohne jede Vermutung.
        """
        genome = [bauen() for bauen in GENERATIONS[5]]

        verstummt = stumme(genome, tageskerzen)

        assert {x.genom for x in verstummt} == {
            "Beteiligt, ausser es ist ueberhitzt",
            "Carry-Beteiligung",
        }

    @pytest.mark.daten
    def test_der_filter_sperrt_einen_einstieg_der_sonst_handelt(
        self, tageskerzen
    ) -> None:
        """**Der schaerfste der fuenf Faelle.**

        'Ausbruch ohne Long-Ueberhitzung' steigt auf einem
        Donchian-50-Ausbruch ein - demselben wie Generation 2, und der
        handelt nachweislich. Null Trades kommen allein aus dem Filter
        ``funding_zscore < 1,5``, der eine *ungewoehnliche* Lage ausschliessen
        soll und ohne Zahl **jeden** Balken ausschliesst.
        """
        genom = GENERATIONS[4][0]()

        befund = lage(genom, tageskerzen)

        assert befund.stumm
        assert befund.leer == ("indicator:funding_zscore(period=90)",)
        # Der Einstieg selbst braucht nur den Kurs und den Donchian-Kanal.
        assert any("donchian" in k for k in befund.gebraucht)

    @pytest.mark.daten
    def test_nur_die_finanzierungsregeln_sind_betroffen(
        self, tageskerzen
    ) -> None:
        """Fuenf von 53 - und keine davon aus einem anderen Grund.

        Waere die Pruefung zu streng, traefe sie auch Regeln, die
        nachweislich handeln. Sie tut es nicht.
        """
        genome = [bauen() for gen in sorted(GENERATIONS) for bauen in GENERATIONS[gen]]

        verstummt = stumme(genome, tageskerzen)

        assert len(verstummt) == 5
        for x in verstummt:
            assert all("funding" in k for k in x.leer), x.leer


class TestDieAnlaufzeitZaehltNicht:
    """Jede Kennzahl ist am Anfang leer, solange ihr Fenster nicht voll ist.
    Wer das als "fehlt" liest, baut eine Warnung, die immer angeht."""

    @pytest.mark.daten
    def test_ein_langes_fenster_gilt_als_vorhanden(self, tageskerzen) -> None:
        """``funding_zscore`` hat Periode 90 und ist trotzdem *vollstaendig*
        leer; ein EMA(200) ist es nur auf den ersten 199 Balken."""
        genom = GENERATIONS[3][0]()  # Trendbeteiligung EMA200

        befund = lage(genom, tageskerzen)

        assert not befund.stumm
        assert befund.gebraucht

    def test_eine_reihe_mit_einem_einzigen_wert_gilt_als_vorhanden(self) -> None:
        from research.kennzahlen import _durchweg_leer

        assert not _durchweg_leer(np.array([np.nan, np.nan, 1.0]))
        assert _durchweg_leer(np.array([np.nan, np.nan]))
        assert _durchweg_leer(np.array([]))
        assert _durchweg_leer(None)


class TestDerSatz:
    def test_er_nennt_die_fehlende_kennzahl(self) -> None:
        befund = Lage(genom="X", gebraucht=("a", "b"), leer=("b",))

        satz = befund.satz()

        assert "b" in satz
        assert "kann hier nicht ausloesen" in satz

    def test_und_urteilt_nicht_ueber_die_regel(self) -> None:
        """Leer heisst "auf dieser Reihe nicht zu haben" und nicht
        "schlecht" - dieselben Regeln sind am Perpetual-Betriebspunkt eine
        offene Frage."""
        satz = Lage(genom="X", gebraucht=("a",), leer=("a",)).satz()

        for wort in ("schlecht", "taugt", "unbrauchbar"):
            assert wort not in satz.casefold()

    @pytest.mark.parametrize(
        ("gebraucht", "erwartet"),
        [
            ((), "braucht keine Kennzahl"),
            (("a",), "die eine gebrauchte Kennzahl liegt vor"),
            (("a", "b"), "alle 2 Kennzahlen liegen vor"),
        ],
    )
    def test_ohne_luecke_sagt_er_das(self, gebraucht, erwartet) -> None:
        assert erwartet in Lage(genom="X", gebraucht=gebraucht, leer=()).satz()


class TestDieZuordnungAusBefund326:
    def test_generation_2_steht_auf_viertelstunden(self) -> None:
        """Gemessen: null Trades auf Tageskerzen ueber alle fuenf Regeln,
        1444 auf Viertelstunden."""
        assert VORGESEHEN[2] == "15"

    def test_generation_1_bleibt_unbestimmt(self) -> None:
        """**Absicht, kein Rest.**

        Vier von fuenf Regeln schweigen auf Tageskerzen, die fuenfte handelt
        sechs Mal - und sechs Trades reichen ``Kandidat.aus_trades``. Nach dem
        Mass, das dieses Projekt schon hat, ist Generation 1 dort zu Hause.
        Wer sie trotzdem umbucht, uebergeht das Mass fuer ein Bauchgefuehl.
        """
        assert VORGESEHEN[1] is None

    def test_generation_4_bleibt_unbestimmt(self) -> None:
        """Ihr Schweigen ist keine Frage der Kerzenlaenge - keine Zeile in
        ``VORGESEHEN`` kann eine fehlende Datenspalte heilen."""
        assert VORGESEHEN[4] is None


def _befehl(name: str) -> str:
    import ast
    from pathlib import Path

    baum = ast.parse(
        (Path(__file__).resolve().parents[1] / "cli.py").read_text(encoding="utf-8")
    )
    return next(
        ast.unparse(n)
        for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef) and n.name == name
    )


@pytest.mark.parametrize("befehl", ["wettbewerb", "rangprobe"])
def test_wer_den_katalog_wertet_laesst_stumme_regeln_draussen(befehl) -> None:
    """**Die Verdrahtung.** Befund 152, 154, 155, 160 und 325 waren alle
    dieselbe Bauart: gebaut, gerechnet, nicht angeschlossen.

    Beide Befehle werten den Katalog und buchen dafuer Versuche - also
    brauchen beide die Wache. Die erste Fassung hat nur ``rangprobe``
    angeschlossen, weil dort der Filter stand, nach dem ich gesucht habe.
    """
    quelle = _befehl(befehl)

    assert "kennzahlen.stumme" in quelle


@pytest.mark.parametrize(
    ("befehl", "wache"),
    [("wettbewerb", "_pruefe_generation"), ("rangprobe", "passt_zum_intervall")],
)
def test_die_wache_fuer_die_kerzenlaenge_bleibt(befehl, wache) -> None:
    """Die neue Pruefung tritt **neben** die alte und nicht an ihre Stelle:
    Sie beantwortet eine andere Frage. Die beiden Befehle sichern die
    Kerzenlaenge unterschiedlich ab - das ist vorgefunden, nicht gewaehlt."""
    assert wache in _befehl(befehl)
