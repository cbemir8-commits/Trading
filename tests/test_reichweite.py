"""Wie weit das Urteil am Reihenanfang haengt - Befund 345.

Der einzige offene Auftrag beim Nutzer ist, Bybit-Tageskerzen zu laden. Bybit ist
spaeter gestartet als Bitstamp, die Reihe wird also kuerzer - und eine kuerzere
Reihe zeigt hier **mehr** Gates:

    ab            Tage  Trades  n_eff   Guete     CAGR  Rueckg.     DSR  Gates
    2017-08-16    3300     156    115  0,2708   14,34%    9,87%  0,5826   9/11
    2018-01-01    3162     147    109  0,2878   17,54%   10,07%  0,6490  10/11
    2019-01-01    2797     127    108  0,2941   18,81%   10,07%  0,6841  10/11
    2020-01-01    2432     109    109  0,2478   10,55%   10,07%  0,3766   9/11
    2021-01-01    2066      88     88  0,2320   11,81%   10,07%  0,1684   9/11
    2022-01-01    1701      68     68  0,2926   16,72%   10,07%  0,2703  10/11

138 Tage weniger am Anfang, und die Jahresrendite steigt von 14,34 % auf 17,54 %
- ueber die Betriebsschwelle von 15 %. Die Messlatte haelt dann.

**Das ist kein Weg**, sondern die Anpassung, gegen die die Zulassungsstrecke
gebaut ist. **Und das Bindende bleibt bindend**: Der Deflated Sharpe kommt auf
keiner Sprosse ueber 0,6841.
"""

from __future__ import annotations

import pytest

from research.reichweite import Leiter, Sprosse

#: Die gemessene Leiter (Befund 345, Spot-Punkt, 203 Versuche).
GEMESSEN: tuple[tuple[str, int, int, int, float, float, float, float, int], ...] = (
    # ab, Tage, Trades, n_eff, Guete, CAGR, Rueckgang, DSR, bestanden
    ("2017-08-16", 3300, 156, 115, 0.2708, 14.34, 9.87, 0.5826, 9),
    ("2018-01-01", 3162, 147, 109, 0.2878, 17.54, 10.07, 0.6490, 10),
    ("2019-01-01", 2797, 127, 108, 0.2941, 18.81, 10.07, 0.6841, 10),
    ("2020-01-01", 2432, 109, 109, 0.2478, 10.55, 10.07, 0.3766, 9),
    ("2021-01-01", 2066, 88, 88, 0.2320, 11.81, 10.07, 0.1684, 9),
    ("2022-01-01", 1701, 68, 68, 0.2926, 16.72, 10.07, 0.2703, 10),
)


def _sprosse(zeile) -> Sprosse:
    ab, tage, trades, eff, guete, cagr, rueck, dsr, bestanden = zeile
    return Sprosse(
        ab=ab, tage=tage, trades=trades, effektiv=eff, guete=guete,
        cagr=cagr, rueckgang=rueck, dsr=dsr, bestanden=bestanden, gesamt=11,
    )


def _leiter() -> Leiter:
    return Leiter(sprossen=tuple(_sprosse(z) for z in GEMESSEN))


class TestDieLeiterFindetDieFlatterstelle:
    def test_die_volle_reihe_ist_die_laengste(self) -> None:
        assert _leiter().voll.ab == "2017-08-16"
        assert _leiter().voll.tage == 3300

    def test_bei_gleichstand_gewinnt_die_laengere(self) -> None:
        """**Sonst waere die kuerzeste Sprosse automatisch die 'beste'** - und
        genau diese Lesart soll der Bericht verhindern."""
        leiter = _leiter()

        assert leiter.beste.ab == "2018-01-01"
        assert leiter.beste.bestanden == 10

    def test_der_gewinn_ist_ein_gate(self) -> None:
        assert _leiter().gewinn == 1
        assert _leiter().flattert

    def test_ohne_flatterstelle_meldet_sie_nichts(self) -> None:
        """Die Gegenprobe: Wenn die volle Reihe die meisten Gates haelt, ist
        die Leiter eine Beruhigung und keine Warnung."""
        leiter = Leiter(
            sprossen=(
                _sprosse(("2017-08-16", 3300, 156, 115, 0.27, 14.3, 9.9, 0.58, 10)),
                _sprosse(("2019-01-01", 2797, 127, 108, 0.29, 18.8, 10.1, 0.68, 9)),
            )
        )

        assert not leiter.flattert
        assert leiter.gewinn == 0
        assert "haengt nicht am Reihenanfang" in leiter.urteil()

    def test_eine_laengere_mit_mehr_gates_ist_keine_flatterstelle(self) -> None:
        """``flattert`` fragt nach **kuerzer** und mehr - nicht nur nach
        mehr."""
        leiter = Leiter(
            sprossen=(
                _sprosse(("2017-08-16", 3300, 156, 115, 0.27, 14.3, 9.9, 0.58, 11)),
                _sprosse(("2019-01-01", 2797, 127, 108, 0.29, 18.8, 10.1, 0.68, 9)),
            )
        )

        assert not leiter.flattert


class TestDasBindendeGate:
    def test_der_dsr_bleibt_auf_jeder_sprosse_offen(self) -> None:
        leiter = _leiter()

        assert leiter.dsr_bleibt_offen
        assert leiter.hoechster_dsr == pytest.approx(0.6841)

    def test_das_urteil_sagt_es(self) -> None:
        urteil = _leiter().urteil()

        assert "Das bindende Gate bleibt bindend" in urteil
        assert "0.6841" in urteil

    def test_eine_haltende_sprosse_wird_als_warnung_gemeldet(self) -> None:
        """Waere der Deflated Sharpe auf einer kuerzeren Reihe bestanden, waere
        das keine Zulassung - und der Bericht darf es nicht so aussehen
        lassen."""
        leiter = Leiter(
            sprossen=(
                _sprosse(("2017-08-16", 3300, 156, 115, 0.27, 14.3, 9.9, 0.58, 9)),
                _sprosse(("2019-01-01", 2797, 127, 108, 0.29, 18.8, 10.1, 0.96, 11)),
            )
        )

        assert not leiter.dsr_bleibt_offen
        assert "Achtung" in leiter.urteil()
        assert "und keine" in leiter.urteil()


class TestDasUrteilNenntDenGrund:
    def test_die_warnung_steht_da(self) -> None:
        urteil = _leiter().urteil()

        assert "kein Weg, sondern eine Warnung" in urteil
        assert "14.34 % auf 17.54 %" in urteil
        assert "138 Tage kuerzer" in urteil

    def test_der_auftrag_wird_genannt(self) -> None:
        urteil = _leiter().urteil()

        assert "Bybit ist spaeter gestartet" in urteil
        assert "zwei Zeitraeume und nicht zwei Boersen" in urteil

    def test_die_tabelle_steht_nach_datum(self) -> None:
        zeilen = _leiter().tabelle().splitlines()[2:]

        assert [z.split()[0] for z in zeilen] == [z[0] for z in GEMESSEN]


class TestUnsinnWirdAbgewiesen:
    def test_eine_leiter_ohne_sprossen(self) -> None:
        with pytest.raises(ValueError, match="keine Leiter"):
            Leiter(sprossen=())

    def test_mehr_bestandene_als_gates(self) -> None:
        with pytest.raises(ValueError, match="keine Bilanz"):
            Sprosse(
                ab="x", tage=1, trades=1, effektiv=1, guete=0.0, cagr=0.0,
                rueckgang=0.0, dsr=0.0, bestanden=12, gesamt=11,
            )

    def test_keine_gates(self) -> None:
        with pytest.raises(ValueError, match="keine Messung"):
            Sprosse(
                ab="x", tage=1, trades=1, effektiv=1, guete=0.0, cagr=0.0,
                rueckgang=0.0, dsr=0.0, bestanden=0, gesamt=0,
            )

    def test_mehr_wirksame_als_rohe_trades(self) -> None:
        with pytest.raises(ValueError, match="hoechstens roh"):
            Sprosse(
                ab="x", tage=1, trades=10, effektiv=11, guete=0.0, cagr=0.0,
                rueckgang=0.0, dsr=0.0, bestanden=1, gesamt=11,
            )


class TestDerBefehlRechnetSie:
    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "abstand"
        )

    def test_der_schalter_ist_da(self) -> None:
        quelle = self._quelle()

        assert "reichweite: bool" in quelle
        assert "from research.reichweite import Leiter, Sprosse" in quelle

    def test_kurze_reihen_werden_uebersprungen(self) -> None:
        """Der Walk-Forward braucht 450 Tage - eine Sprosse darunter waere
        keine Messung, sondern ein Absturz."""
        quelle = self._quelle()

        assert "if tage < 450:" in quelle

    def test_die_gates_werden_voll_gerechnet(self) -> None:
        """Nicht '--schnell': Eine Leiter aus teils geprueften Bilanzen waere
        nicht vergleichbar."""
        quelle = self._quelle()

        assert "teil_gates = evaluate_gates(" in quelle


class TestDerAuftragTraegtDieWarnung:
    @staticmethod
    def _punkt():
        from research.stand import AUFTRAG

        return next(p for p in AUFTRAG if p.frage.startswith("backfill Bybit"))

    def test_die_warnung_steht_im_auftrag(self) -> None:
        stand = self._punkt().stand
        assert "kuerzere Reihe zeigt hier **mehr** Gates" in stand
        assert "14,34 auf 17,54 %" in stand

    def test_das_bindende_gate_steht_dabei(self) -> None:
        """Ohne diesen Satz laese sich der Eintrag wie "es fehlt nur noch
        eins"."""
        stand = self._punkt().stand

        assert "0,6841 gegen 0,95" in stand

    def test_der_auftrag_bleibt_offen(self) -> None:
        punkt = self._punkt()

        assert not punkt.erledigt
        assert punkt.befund == 171
        assert punkt.massgeblich == 345

    def test_die_befehlszeile_warnt_auch(self) -> None:
        """Wer die Zeile kopiert, liest womoeglich nur sie."""
        from research.stand import BEIM_NUTZER

        text = next(
            warum for befehl, warum in BEIM_NUTZER if "backfill" in befehl
        )

        assert "spaeter gestartet als Bitstamp" in text
        assert "cli abstand --reichweite" in text


@pytest.mark.daten
@pytest.mark.langsam
def test_die_leiter_stimmt() -> None:
    """**Die Bindung.** Dass die Messlatte an 138 Tagen am Anfang haengt, war
    nicht zu sehen, solange niemand die Reihe verkuerzt hat.
    """
    from pathlib import Path

    import pandas as pd

    import cli
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.admission import load_trials
    from research.erreichbarkeit import kennzahlen_aus_pnl
    from research.gates import (
        GateThresholds,
        evaluate_gates,
        stichprobe_wie_im_gate,
    )
    from research.randschnitt import ohne_zensierte
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    versuche = load_trials(Path(e.paths.state) / "trials.json")
    store = CandleStore(e.paths.data_store)
    ganz = {s: store.read(s, Interval("D")) for s in symbole}
    configs = cli._spotconfigs(symbole, e)
    genom = cli._ohne_hebel(spitzenkandidat())

    for ab, tage, trades, eff, guete, cagr, rueck, dsr, bestanden in GEMESSEN:
        grenze = pd.Timestamp(ab, tz="UTC")
        teil = common_range(
            {
                name: f[f["open_time"] >= grenze].reset_index(drop=True)
                for name, f in ganz.items()
            }
        )
        erster = next(iter(teil.values()))
        bericht = run_portfolio_walkforward(
            teil, lambda g=genom: compile_genome(g), configs
        )
        gehandelt = ohne_zensierte(bericht)
        _, gemessene_guete, _, _ = kennzahlen_aus_pnl(
            [x.net_pnl for x in gehandelt.all_trades]
        )
        stichprobe = stichprobe_wie_im_gate(
            gehandelt.all_trades,
            beine=getattr(bericht, "beine", None),
            bloecke=[
                [float(x.net_pnl) for x in w.trades] for w in gehandelt.windows
            ],
        )
        gates = evaluate_gates(
            genom, bericht, teil[symbole[0]], configs[symbole[0]],
            trials_so_far=versuche, thresholds=GateThresholds(),
            frames=teil, configs=configs,
        )

        assert (
            erster["open_time"].max() - erster["open_time"].min()
        ).days == tage, ab
        assert stichprobe.roh == trades, ab
        assert stichprobe.effektiv == eff, ab
        assert gemessene_guete == pytest.approx(guete, abs=0.0005), ab
        assert bericht.combined.cagr_pct == pytest.approx(cagr, abs=0.01), ab
        assert bericht.combined.max_drawdown_pct == pytest.approx(rueck, abs=0.01), ab
        assert next(
            r.value for r in gates.results if r.name == "Deflated Sharpe"
        ) == pytest.approx(dsr, abs=0.0005), ab
        assert sum(1 for r in gates.results if r.passed) == bestanden, ab

    # Und der Punkt, um den es geht: Die Messlatte haelt ab 2018 und nicht
    # vorher - 138 Tage machen den Unterschied.
    leiter = _leiter()

    assert leiter.flattert
    assert leiter.voll.cagr < 15.0 <= leiter.beste.cagr
    assert leiter.dsr_bleibt_offen
