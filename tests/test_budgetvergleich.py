"""Abmachung und Rechnung standen nie nebeneinander - Befund 389.

Zwei Zahlen fuer dieselbe Frage, je eine pro Befehl:

    cli stand     "73 von 100 verbraucht, 27 bleiben (Abbruch bei 230)"
    cli abstand   "Das Fenster schliesst sich bei 224 Versuchen, es bleiben 21"

Keiner der beiden nannte die Gegenzahl. Und wer nur den Statusschirm ansah -
den Befehl fuer genau diese Frage - hatte die **groessere** der beiden Zahlen.

``Suchbudget.gegen`` rechnet jetzt, welche Grenze bindet. Auf dem Statusschirm
steht dabei **keine Zahl**, sondern wo sie gerechnet wird: ``cli stand``
verspricht in seinem eigenen Docstring *"Die Zahlen werden gemessen, nicht
gepflegt ... Nichts davon kann veralten, ohne dass es auffaellt"*, und die 224
haengt an der wirksamen Stichprobe (Befund 388), also an einem Lauf.
"""

from __future__ import annotations

import inspect

import pytest

import cli
from research.stand import BUDGET, Suchbudget


class TestDieVierFaelle:
    """Vier, nicht drei - und der vierte war mein Fehler in diesem Durchgang."""

    def test_die_rechnung_ist_strenger(self) -> None:
        satz = BUDGET.gegen(203, 224)

        assert "Rechnung ist strenger" in satz
        assert "224" in satz
        assert "230" in satz
        assert "21 statt 27" in satz
        assert "letzten 6" in satz

    def test_die_abmachung_ist_strenger(self) -> None:
        """Der Fall auf dem ungeschnittenen Speicher (Befund 387: 349)."""
        satz = BUDGET.gegen(203, 349)

        assert "Abmachung ist strenger" in satz
        assert "nicht erhoeht" in satz, (
            "eine vorab genannte Zahl, die sich nachtraeglich nachgeben "
            "laesst, ist keine"
        )

    def test_beide_sagen_dasselbe(self) -> None:
        satz = BUDGET.gegen(203, BUDGET.grenze)

        assert "dasselbe" in satz

    def test_ohne_rechnung_gilt_die_abmachung_und_sagt_es(self) -> None:
        """``None`` heisst 'nicht gerechnet' - **nicht** 'Fenster zu'. Eine
        fehlende Rechnung ist kein Grund, stillschweigend die groessere Zahl
        zu nehmen."""
        satz = BUDGET.gegen(203, None)

        assert "liegt hier nicht vor" in satz
        assert "cli abstand" in satz


class TestDerBefehlVergleichtNurMitFenster:
    """Mein Fehler: Der erste Einbau rief ``gegen`` auch dann, wenn schon
    heute kein Weg traegt - und haette dort den **lockersten** Satz gedruckt
    ('die Rechnung liegt nicht vor, es gilt die Abmachung'), also 27
    verbleibende Versuche, wo das Fenster zu ist.
    """

    def test_der_vergleich_haengt_am_vorhandenen_fenster(self) -> None:
        quelle = inspect.getsource(cli.abstand)

        assert "if grenze is not None:" in quelle
        assert "BUDGET.gegen(trials, grenze.versuche)" in quelle

    def test_und_der_grund_steht_daneben(self) -> None:
        quelle = inspect.getsource(cli.abstand)

        assert "Dann ist das Fenster zu und nicht weiter als der Plan" in quelle


class TestDerStatusschirmTraegtKeineZahl:
    """Sonst waere es wieder eine gepflegte Zahl - genau der Mangel aus 387."""

    def test_der_hinweis_nennt_den_rechnenden_befehl(self) -> None:
        assert "cli abstand" in Suchbudget.HINWEIS
        assert "zielfenster" in Suchbudget.HINWEIS

    def test_und_keine_fensterzahl(self) -> None:
        for zahl in ("224", "21", "349", "286"):
            assert zahl not in Suchbudget.HINWEIS, zahl

    def test_die_lage_druckt_ihn(self) -> None:
        from research.stand import Lage

        quelle = inspect.getsource(Lage)

        assert "BUDGET.HINWEIS" in quelle

    def test_cli_stand_verspricht_gemessene_zahlen(self) -> None:
        """Der Satz, auf dem die Entscheidung beruht, keine 224 dort
        hinzuschreiben."""
        text = cli.stand.__doc__ or ""

        assert "gemessen" in text
        assert "nicht gepflegt" in text
        assert "veralten" in text


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_beide_zahlen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 389)

        for zahl in ("224", "230", "27", "21"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_die_messlatte_gegenprobe(self) -> None:
        """Das geprueftes Nicht-Ergebnis gehoert dazu: Der knappe Fehlschlag
        ist echt, der Zeitraum ist nicht die Ursache."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 389)

        assert "2922" in eintrag.ergebnis
        assert "14,3339" in eintrag.ergebnis
        assert "14,3391" in eintrag.ergebnis

    def test_und_388_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        vorher = next(r for r in BEHOBEN if r.befund == 388)

        assert vorher.zuletzt == 389


@pytest.mark.daten
@pytest.mark.langsam
class TestDieMesslatteRechnetDenRichtigenZeitraum:
    """Die Gegenprobe zum knappen Fehlschlag (14,339 gegen 15).

    Bei 0,66 Punkten Abstand entscheidet der Zeitraum mit: ``compute_metrics``
    nimmt die Spanne der **Kapitalkurve**. Beide anderen vertretbaren Spannen
    sind auf den Tag gleich lang, und die Jahresrendite daraus weicht um 0,005
    Punkte ab. Der Fehlschlag ist echt.
    """

    @staticmethod
    def _lauf():
        from backtest.portfolio_walkforward import (
            common_range,
            run_portfolio_walkforward,
        )
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        e = get_settings()
        store = CandleStore(e.paths.data_store)
        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        frames = common_range(
            alle_geschnitten({s: store.read(s, Interval.D1) for s in symbole})
        )
        genom = cli._ohne_hebel(spitzenkandidat())
        return run_portfolio_walkforward(
            frames, lambda: compile_genome(genom), cli._spotconfigs(symbole, e)
        )

    def test_beide_spannen_sind_gleich_lang(self) -> None:
        report = self._lauf()
        fenster = [w for w in report.windows if w.window is not None]
        tage_fenster = (
            fenster[-1].window.test_end - fenster[0].window.test_start
        ).days
        ein = min(t.entry_time for t in report.all_trades)
        aus = max(t.exit_time for t in report.all_trades)

        assert tage_fenster == 2922
        assert (aus - ein).days == 2922

    def test_und_die_jahresrendite_stimmt_auf_fuenf_tausendstel(self) -> None:
        report = self._lauf()
        k = report.combined
        jahre = 2922 / 365.25
        nachgerechnet = ((1 + k.total_return_pct / 100) ** (1 / jahre) - 1) * 100

        assert k.cagr_pct == pytest.approx(14.3391, abs=0.001)
        assert nachgerechnet == pytest.approx(14.3339, abs=0.001)
        assert abs(k.cagr_pct - nachgerechnet) < 0.01

    def test_der_fehlschlag_ist_echt(self) -> None:
        """Nicht 'knapp daneben wegen der Rechnung' - knapp daneben."""
        from research.gates import GateThresholds

        report = self._lauf()
        fehlt = GateThresholds().min_cagr_pct - report.combined.cagr_pct

        assert fehlt == pytest.approx(0.66, abs=0.01)
