"""Haette das **Konto** ausgeloest - oder nur ein einzelnes Bein?

Der Befund, der dieses Modul ausgeloest hat, gemessen am Spitzenkandidaten,
durchgehend, je Bein 500 EUR:

    Bein                    Trades   Rueckgang des Beins
    BTC                         18            12,78 %
    ETH                         68            15,50 %   <- Kill-Switch
    beide als ein Konto          --           11,14 %   <- nie ausgeloest

Das ETH-Bein loest den Not-Aus aus, obwohl das Konto ihn nie gesehen haette.
Gemessen wurde damit nicht das Risiko des Kontos, sondern das zweier
getrennter Konten.

Zwei Tests tragen die Datei:

* ``test_gegenlaeufige_beine_loesen_einzeln_aus_das_konto_nicht`` - der Fall
  selbst, in Reinform.
* ``test_luecken_werden_fortgeschrieben_nicht_genullt`` - der Fehler, in den
  man beim Addieren zweier Kurven laeuft. Ein Bein ohne Punkt an einem Tag hat
  sein Kapital nicht verloren; mit Nullen entstuende ein Rueckgang, den es nie
  gab, und der Officer loeste auf einem Artefakt aus.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from core.config import MarginMode, RiskSettings
from core.models import Instrument
from execution.risk import TradingState
from research.kontorisiko import kontokurve, pruefe

T0 = datetime(2021, 1, 1, tzinfo=UTC)


def _instrument() -> Instrument:
    return Instrument(
        symbol="BTCUSDT", category="linear", base_coin="BTC", quote_coin="USDT",
        tick_size=Decimal("0.01"), qty_step=Decimal("0.001"),
        min_order_qty=Decimal("0.001"), max_order_qty=Decimal("100000"),
        min_notional=Decimal("5"), max_leverage=Decimal("100"),
        maintenance_margin_rate=Decimal("0.005"),
    )


def _risk() -> RiskSettings:
    return RiskSettings(
        risk_per_trade_pct=Decimal("0.75"),
        max_leverage=Decimal("3"),
        margin_mode=MarginMode.ISOLATED,
        daily_loss_limit_pct=Decimal("3.0"),
        weekly_loss_limit_pct=Decimal("7.0"),
        max_drawdown_pct=Decimal("15.0"),
    )


def _kurve(werte: list[float], *, start: datetime = T0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [start + timedelta(days=i) for i in range(len(werte))],
            "equity": werte,
        }
    )


class TestKontokurve:
    def test_beine_werden_addiert(self) -> None:
        kurve = kontokurve(
            {"a": _kurve([500.0, 510.0, 520.0]), "b": _kurve([500.0, 490.0, 480.0])}
        )

        assert list(kurve["equity"]) == [1000.0, 1000.0, 1000.0]

    def test_luecken_werden_fortgeschrieben_nicht_genullt(self) -> None:
        """**Der Fehler beim Addieren zweier Kurven.**

        Bein ``b`` meldet am zweiten Tag nichts. Mit Nullen faellt das Konto
        dort um die Haelfte, und der Officer loeste auf einem Artefakt aus.
        Fortgeschrieben bleibt es, was es ist: unveraendert.
        """
        b = _kurve([500.0, 500.0])
        b = b.drop(index=1).reset_index(drop=True)  # zweiter Tag fehlt
        b.loc[1] = {"time": T0 + timedelta(days=2), "equity": 500.0}

        kurve = kontokurve({"a": _kurve([500.0, 500.0, 500.0]), "b": b})

        assert list(kurve["equity"]) == [1000.0, 1000.0, 1000.0]

    def test_ein_bein_beginnt_spaeter(self) -> None:
        """Vor seinem ersten Punkt zaehlt ein Bein nicht mit - sonst begaenne
        das Konto mit Kapital, das noch gar nicht im Markt war."""
        spaet = _kurve([500.0, 500.0], start=T0 + timedelta(days=2))

        kurve = kontokurve({"a": _kurve([500.0] * 4), "b": spaet})

        assert list(kurve["equity"]) == [500.0, 500.0, 1000.0, 1000.0]

    def test_leere_eingabe(self) -> None:
        assert kontokurve({}).empty
        assert kontokurve({"a": pd.DataFrame()}).empty


class TestPruefung:
    def test_ruhige_kurve_loest_nichts_aus(self) -> None:
        lauf = pruefe(
            _kurve([1000.0 + i for i in range(60)]),
            risk=_risk(), instrument=_instrument(),
        )

        assert not lauf.haette_ausgeloest
        assert lauf.endzustand == TradingState.ACTIVE.value
        assert "nichts" in lauf.bericht()

    def test_kill_switch_bei_fuenfzehn_prozent(self) -> None:
        werte = [1000.0] * 5 + [1000.0 * (1 - 0.02 * i) for i in range(1, 10)]

        lauf = pruefe(_kurve(werte), risk=_risk(), instrument=_instrument())

        assert lauf.haette_ausgeloest
        assert lauf.endzustand == TradingState.KILLED.value
        assert lauf.hoechster_rueckgang_pct >= 15.0

    def test_gegenlaeufige_beine_loesen_einzeln_aus_das_konto_nicht(self) -> None:
        """**Der Fall selbst, in Reinform.**

        Bein ``a`` faellt um 20 %, Bein ``b`` steigt um 20 %. Einzeln geprueft
        reisst ``a`` den Kill-Switch; das Konto steht die ganze Zeit still.
        """
        faellt = _kurve([500.0 * (1 - 0.01 * i) for i in range(21)])
        steigt = _kurve([500.0 * (1 + 0.01 * i) for i in range(21)])

        allein = pruefe(faellt, risk=_risk(), instrument=_instrument())
        konto = pruefe(
            kontokurve({"a": faellt, "b": steigt}),
            risk=_risk(), instrument=_instrument(),
        )

        assert allein.endzustand == TradingState.KILLED.value
        assert not konto.haette_ausgeloest
        assert konto.hoechster_rueckgang_pct == pytest.approx(0.0, abs=1e-9)

    def test_wochenlimit_pausiert(self) -> None:
        """-7 % in einer Woche pausieren bis zur manuellen Freigabe.

        Der Start liegt bewusst auf einem **Montag**: Der Officer setzt den
        Wochenbezug jeden Montag neu. Der erste Anlauf begann an einem Freitag,
        die Woche brach nach drei Tagen um, und aus -8 % wurden -5,2 % - der
        Test war rot, ohne dass am Code etwas falsch war.
        """
        montag = datetime(2021, 1, 4, tzinfo=UTC)
        assert montag.weekday() == 0
        werte = [1000.0, 995.0, 985.0, 970.0, 950.0, 925.0, 920.0]

        lauf = pruefe(
            _kurve(werte, start=montag), risk=_risk(), instrument=_instrument()
        )

        assert lauf.haette_ausgeloest
        assert lauf.erstes is not None
        assert lauf.erstes.art in (
            TradingState.PAUSED.value,
            TradingState.KILLED.value,
        )

    def test_leere_kurve(self) -> None:
        lauf = pruefe(pd.DataFrame(), risk=_risk(), instrument=_instrument())

        assert lauf.punkte == 0
        assert not lauf.haette_ausgeloest
        assert "Keine Kontokurve" in lauf.bericht()

    def test_bericht_nennt_die_ereignisse(self) -> None:
        werte = [1000.0] * 5 + [1000.0 * (1 - 0.02 * i) for i in range(1, 10)]

        text = pruefe(_kurve(werte), risk=_risk(), instrument=_instrument()).bericht()

        assert "Ereignis" in text
        assert "Endzustand" in text

    def test_der_echte_officer_wird_benutzt(self) -> None:
        """Keine Nachbildung der Regeln - zwei Umsetzungen derselben Sache
        laufen auseinander, und genau das ist hier schon fuenfmal passiert."""
        import inspect

        from research import kontorisiko

        quelle = inspect.getsource(kontorisiko)

        assert "RiskOfficer(" in quelle
        assert "observe_equity" in quelle


class TestWarnungImPortfolio:
    def test_mehrere_beine_mit_limits_werden_gemeldet(self, caplog) -> None:
        """**Damit diese Zahlen nie wieder als Kontozahlen gelesen werden.**

        Der Portfolio-Lauf erzwingt die Grenzen je Bein. Solange das so ist,
        muss es im Protokoll stehen - ein Kommentar im Quelltext hat es
        offenbar nicht verhindert.
        """
        import logging

        import numpy as np
        import structlog

        from backtest.engine import BacktestConfig
        from backtest.portfolio_walkforward import run_portfolio_walkforward

        structlog.configure(
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
        )

        zeiten = pd.date_range("2020-01-01", periods=40, freq="1D", tz="UTC")
        rahmen = {
            name: pd.DataFrame(
                {
                    "open_time": zeiten,
                    "open": np.full(40, 100.0),
                    "high": np.full(40, 101.0),
                    "low": np.full(40, 99.0),
                    "close": np.full(40, 100.0),
                    "volume": np.full(40, 10.0),
                    "turnover": np.full(40, 1000.0),
                }
            )
            for name in ("A", "B")
        }
        config = BacktestConfig(
            instrument=_instrument(), risk=_risk(),
            initial_equity=Decimal("500"), enforce_risk_limits=True,
        )

        with caplog.at_level(logging.WARNING):
            run_portfolio_walkforward(rahmen, lambda: None, config)

        assert "portfolio.risiko_je_bein" in caplog.text

    def test_ein_einziges_bein_wird_nicht_gemeldet(self, caplog) -> None:
        """Bei einem Bein ist Bein gleich Konto - da gibt es nichts zu warnen."""
        import logging

        import numpy as np
        import structlog

        from backtest.engine import BacktestConfig
        from backtest.portfolio_walkforward import run_portfolio_walkforward

        structlog.configure(
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
        )

        zeiten = pd.date_range("2020-01-01", periods=40, freq="1D", tz="UTC")
        rahmen = {
            "A": pd.DataFrame(
                {
                    "open_time": zeiten,
                    "open": np.full(40, 100.0),
                    "high": np.full(40, 101.0),
                    "low": np.full(40, 99.0),
                    "close": np.full(40, 100.0),
                    "volume": np.full(40, 10.0),
                    "turnover": np.full(40, 1000.0),
                }
            )
        }
        config = BacktestConfig(
            instrument=_instrument(), risk=_risk(),
            initial_equity=Decimal("500"), enforce_risk_limits=True,
        )

        with caplog.at_level(logging.WARNING):
            run_portfolio_walkforward(rahmen, lambda: None, config)

        assert "portfolio.risiko_je_bein" not in caplog.text
