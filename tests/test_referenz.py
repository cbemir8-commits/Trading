"""Tests fuer ``research.referenz`` - Befund 136.

Der eigentliche Test dieser Datei ist der letzte: Jedes Modul, das eine
ueberholte Kennzahl nennt, muss dazusagen, dass sie ueberholt ist. Ohne diese
Pruefung war der Stand nach Befund 135 an 21 Stellen falsch, und keine davon
war einem Leser anzusehen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.referenz import SPOTPUNKT, UEBERHOLT, Referenzpunkt, veraltet

MODULE = sorted(Path("research").glob("*.py"))


# --- Der Referenzpunkt selbst -----------------------------------------------


def test_der_massgebliche_punkt_stammt_aus_befund_135() -> None:
    assert SPOTPUNKT.befund == 135
    assert SPOTPUNKT.effektiv == 112
    assert SPOTPUNKT.dsr == pytest.approx(0.6026)


def test_die_luecke_folgt_aus_der_schwelle() -> None:
    assert SPOTPUNKT.luecke == pytest.approx(0.95 - 0.6026)
    assert SPOTPUNKT.luecke > 0.34, "die Luecke ist seit Befund 135 viermal so gross"


def test_effektive_stichprobe_kann_die_rohe_nicht_uebersteigen() -> None:
    with pytest.raises(ValueError, match="das geht nicht"):
        Referenzpunkt("kaputt", 135, 152, 153, 0.2765, 0.6026, 9, 11, 198)


def test_ein_punkt_ohne_fundstelle_ist_eine_behauptung() -> None:
    with pytest.raises(ValueError, match="Behauptung"):
        Referenzpunkt("kaputt", 0, 152, 112, 0.2765, 0.6026, 9, 11, 198)


def test_die_ueberholten_staende_sind_aelter_als_der_massgebliche() -> None:
    assert UEBERHOLT
    for punkt in UEBERHOLT:
        assert punkt.befund < SPOTPUNKT.befund, punkt.name


def test_zeile_nennt_die_fundstelle() -> None:
    assert "Befund 135" in SPOTPUNKT.als_zeile()
    assert "0.6026" in SPOTPUNKT.als_zeile()


# --- Der Fund, und was er nicht ist -----------------------------------------


def test_veraltet_findet_beide_schreibweisen() -> None:
    assert veraltet("hier steht 0.8640 im Text") == ("0.8640",)
    assert veraltet("hier steht 0,8640 im Text") == ("0,8640",)


def test_veraltet_findet_auch_den_perpetual_stand() -> None:
    assert "0.7641" in veraltet("Perpetual DSR 0.7641")


def test_veraltet_meldet_nichts_bei_aktuellen_zahlen() -> None:
    assert veraltet(f"Stand: DSR {SPOTPUNKT.dsr:.4f}") == ()


def test_veraltet_meldet_jede_zahl_nur_einmal() -> None:
    assert veraltet("0.8640 und nochmal 0.8640") == ("0.8640",)


# --- Die eigentliche Pruefung -----------------------------------------------


def test_es_gibt_module_die_ueberholte_zahlen_nennen() -> None:
    """Ohne diesen Test waere die naechste Pruefung leer und damit wertlos."""
    betroffen = [
        p.name for p in MODULE if veraltet(p.read_text(encoding="utf-8"))
    ]
    assert betroffen, "keine ueberholten Zahlen gefunden - die Pruefung liefe leer"


@pytest.mark.parametrize("pfad", MODULE, ids=lambda p: p.name)
def test_wer_eine_ueberholte_zahl_nennt_sagt_es_dazu(pfad: Path) -> None:
    """Ein Modulkopf wird als Stand gelesen, ein Laborbuch als Protokoll.

    Wer eine ueberholte Kennzahl stehen laesst, muss den Leser weiterschicken -
    zu ``research.referenz`` oder zu dem Befund, der sie ueberholt hat. Das ist
    die Lehre aus Befund 130, eine Ebene tiefer.
    """
    text = pfad.read_text(encoding="utf-8")
    gefunden = veraltet(text)
    if not gefunden or pfad.name == "referenz.py":
        return
    # **Der Hinweis muss ausdruecklich sein.** Der erste Anlauf hier suchte
    # nach dem Wort "Referenz" - und liess acht Module durch, weil sie
    # "Referenzfenster" oder "(Referenz)" aus ganz anderem Anlass enthielten.
    # Genau der Fehler aus Befund 118: eine Textsuche, deren Treffer man
    # ungeprueft nimmt.
    hinweis = (
        "research.referenz" in text
        or "research/referenz" in text
        or f"Befund {SPOTPUNKT.befund}" in text
    )
    assert hinweis, (
        f"{pfad.name} nennt {', '.join(gefunden)} ohne Hinweis darauf, dass der "
        f"Wert seit Befund {SPOTPUNKT.befund} ueberholt ist."
    )


# --- Die Angabe gegen den Lauf ----------------------------------------------


@pytest.mark.langsam
def test_der_referenzpunkt_stimmt_mit_dem_lauf_ueberein() -> None:
    """Der eigentliche Schutz: gepflegte Zahlen, die gegen die Messung laufen.

    ``referenz.py`` wird von Hand gepflegt, und gepflegte Zahlen veralten -
    genau das ist der Anlass fuer dieses Modul gewesen. Deshalb rechnet dieser
    Test den Kandidaten am massgeblichen Punkt einmal durch und vergleicht.

    Er dauert. Das ist der Preis dafuer, dass die Zahl nicht wieder still
    wegdriftet.
    """
    from decimal import Decimal

    import cli
    from backtest.costs import FundingSchedule
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.admission import load_trials
    from research.gates import evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    einstellungen = get_settings()
    intervall = Interval("D")
    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    speicher = CandleStore(einstellungen.paths.data_store)
    frames = common_range({x: speicher.read(x, intervall) for x in symbole})
    if any(f.empty for f in frames.values()):
        pytest.skip("keine Kerzen im Speicher")

    # **Abstand zum Serienende** (Befund 151). Ohne ihn haengt der
    # Referenzpunkt daran, wann zuletzt Kerzen geholt wurden: Bei einem Abzug
    # bis heute wurden zwei offene Positionen am Datenende glattgestellt - die
    # zwei groessten Gewinner des Laufs -, und der Deflated Sharpe stand bei
    # 0,7255 statt 0,6026. Dreissig Tage genuegen, und bis neunzig aendert sich
    # nichts mehr.
    import pandas as pd

    from research.randschnitt import RANDPUFFER_TAGE, randtrades

    ende = max(f["open_time"].max() for f in frames.values())
    grenze = ende - pd.Timedelta(days=RANDPUFFER_TAGE)
    frames = {
        k: v[v["open_time"] <= grenze].reset_index(drop=True)
        for k, v in frames.items()
    }

    versuche = load_trials(Path(einstellungen.paths.state) / "trials.json")
    assert versuche == SPOTPUNKT.versuche, (
        f"Der Versuchszaehler steht bei {versuche}, referenz.py nennt "
        f"{SPOTPUNKT.versuche} - der Deflated Sharpe haengt daran."
    )

    basis = spitzenkandidat()
    genom = basis.model_copy(
        update={"sizing": basis.sizing.model_copy(update={"fraction": 1.0})}
    )
    configs = {}
    for x in symbole:
        grund = BacktestConfig(
            instrument=cli._fallback_instrument(cli._bybit_kontrakt(x)),
            risk=einstellungen.risk, initial_equity=Decimal("500"),
            enforce_risk_limits=True,
            kalender=cli._terminkalender(einstellungen) or None,
        )
        configs[x] = BacktestConfig(
            instrument=grund.instrument, risk=grund.risk, costs=grund.costs,
            funding=FundingSchedule(default_rate=Decimal("0")),
            initial_equity=grund.initial_equity, enforce_risk_limits=True,
            allow_shorts=grund.allow_shorts,
            entry_expiry_bars=grund.entry_expiry_bars,
            max_hold_bars=grund.max_hold_bars, kalender=grund.kalender,
        )

    bericht = run_portfolio_walkforward(
        frames, lambda: compile_genome(genom), configs
    )
    ergebnisse = evaluate_gates(
        genom, bericht, next(iter(frames.values())), configs[symbole[0]],
        trials_so_far=versuche, frames=frames, configs=configs,
    )
    dsr = next(r for r in ergebnisse.results if r.name == "Deflated Sharpe")

    # Der Schnitt muss gewirkt haben - sonst prueft der Rest ein Artefakt.
    assert not randtrades(bericht.all_trades), (
        "Trades am Datenende beendet: Der Randpuffer greift nicht, und die "
        "Zahlen unten haengen daran, wann zuletzt Kerzen geholt wurden."
    )
    assert len(bericht.all_trades) == SPOTPUNKT.trades
    assert float(dsr.value) == pytest.approx(SPOTPUNKT.dsr, abs=5e-4)
    assert sum(1 for r in ergebnisse.results if r.passed) == SPOTPUNKT.bestanden
    assert len(ergebnisse.results) == SPOTPUNKT.gesamt

    # ``effektiv`` steht in keiner Gate-Meldung, waere also ungeprueft
    # geblieben. Statt die Gate-Logik nachzubauen, wird die Zahl ueber die
    # Formel an den beobachteten Wert gebunden: Nur das richtige n ergibt den
    # gemessenen Deflated Sharpe.
    import numpy as np

    from research.gates import deflated_sharpe_ratio

    pnls = np.array([float(t.net_pnl) for t in bericht.all_trades], dtype=float)
    streuung = pnls.std(ddof=1)
    zentriert = (pnls - pnls.mean()) / streuung
    aus_referenz = float(
        deflated_sharpe_ratio(
            observed_sharpe=float(pnls.mean() / streuung),
            trials=versuche,
            sample_size=SPOTPUNKT.effektiv,
            skew=float(np.mean(zentriert**3)),
            kurtosis=float(np.mean(zentriert**4)),
        )
    )
    assert aus_referenz == pytest.approx(float(dsr.value), abs=5e-4), (
        f"referenz.py nennt n = {SPOTPUNKT.effektiv}; damit ergaebe die Formel "
        f"{aus_referenz:.4f}, das Gate liefert aber {float(dsr.value):.4f}."
    )


# --- Die Aussicht (Befund 138) ----------------------------------------------


def test_die_aussicht_rechnet_mit_dem_heutigen_n() -> None:
    from research.referenz import AUSSICHT

    assert AUSSICHT.heute == SPOTPUNKT.effektiv
    assert AUSSICHT.fehlend == 182 - SPOTPUNKT.effektiv
    assert AUSSICHT.befund == 138


def test_die_aussicht_ist_deutlich_laenger_als_befund_132_sagte() -> None:
    """1,8 Jahre bei n = 152; nach Befund 135 sind es mindestens 5,6."""
    from research.referenz import AUSSICHT

    assert AUSSICHT.jahre > 5.0
    assert AUSSICHT.tage == pytest.approx(2047, abs=5)


def test_eine_aussicht_ohne_rate_laesst_sich_nicht_rechnen() -> None:
    from research.referenz import Aussicht

    with pytest.raises(ValueError, match="keine Zeit rechnen"):
        Aussicht(noetig=182, heute=112, rate_je_tausend_tage=0.0, befund=138)


def test_eine_aussicht_ohne_fundstelle_ist_eine_behauptung() -> None:
    from research.referenz import Aussicht

    with pytest.raises(ValueError, match="Behauptung"):
        Aussicht(noetig=182, heute=112, rate_je_tausend_tage=34.2, befund=0)


def test_ein_erreichtes_ziel_braucht_keine_zeit() -> None:
    from research.referenz import Aussicht

    erreicht = Aussicht(noetig=100, heute=112, rate_je_tausend_tage=34.2, befund=138)
    assert erreicht.fehlend == 0
    assert erreicht.tage == 0


def test_die_zeile_weist_die_zahl_als_untergrenze_aus() -> None:
    from research.referenz import AUSSICHT

    assert "mindestens" in AUSSICHT.als_zeile()
    assert "Befund 138" in AUSSICHT.als_zeile()
