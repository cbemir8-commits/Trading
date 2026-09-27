"""Der Backfill lud ein Symbol - der Korb braucht zwei. Befund 357.

Jede Zulassungszahl dieses Projekts steht auf dem Korb aus BTC und ETH: 9 von
11 auf beiden, 8 von 11 auf ein Bein gekuerzt, 5 von 11 fuer BTC auf seiner
eigenen Reihe (Befunde 264/318). Der Korb zieht den Rueckgang unter den jedes
Beins, weil die zwei nicht gleichzeitig fallen.

``cli backfill`` hat genau **ein** Symbol geladen - ``settings.bybit.symbol`` -
und kein Schalter aenderte das. Auf Bybit-Kerzen konnte der Korb damit nie
entstehen, und die Zeile, die der Nutzer kopiert, sagte es nicht.

Was daran teuer ist
-------------------
``cli wettbewerb`` ohne ``-m`` sucht auf **einem** Markt und bucht seine
Versuche rundenweise. Ein gebuchter Versuch kommt nicht zurueck - ``save_trials``
laesst den Zaehler nie fallen, weil ein fallender Zaehler die
Mehrfachtest-Korrektur milder machte. Die Suche auf einem Bein kostet also
dieselbe Latte wie die auf dem Korb und kann sie nicht einholen.

Gefunden beim Durchfahren der Zeilen, die dem Nutzer gegeben werden - nicht
beim Lesen. Der Kopf des Laufs sagt es selbst:

    Wettbewerb BTCUSDT 1d
      Historie   2012-01-01 bis 2026-08-29

Ein Bein, und dazu die volle BTC-Reihe statt des gemeinsamen Zeitraums mit ETH:
``common_range`` hat bei einem Markt nichts zu schneiden.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from cli import ZULASSUNGSKORB, app
from core.models import Candle, Interval


class FakeMarkt:
    """Eine Boerse, die zu jedem Symbol Tageskerzen liefert.

    Die echte ist aus diesem Container nicht erreichbar (Regionssperre), und
    genau deshalb steht hier ein Doppel: Ob **jeder** genannte Markt geladen
    wird, ist eine Eigenschaft des Befehls und nicht der Boerse.
    """

    def __init__(self) -> None:
        self.gefragt: list[str] = []

    def get_klines(
        self, symbol: str, interval, *, start=None, end=None, limit: int = 1000
    ) -> list[Candle]:
        self.gefragt.append(symbol)
        beginn = start or datetime(2017, 8, 16, tzinfo=UTC)
        kerzen = []
        for tag in range(min(limit, 400)):
            zeit = beginn + timedelta(days=tag)
            if end is not None and zeit >= end:
                break
            kerzen.append(
                Candle(
                    symbol=symbol,
                    interval=Interval.D1
                    if hasattr(Interval, "D1")
                    else Interval("D"),
                    open_time=zeit,
                    open=100.0 + tag,
                    high=101.0 + tag,
                    low=99.0 + tag,
                    close=100.5 + tag,
                    volume=10.0,
                    turnover=1000.0,
                    confirmed=True,
                )
            )
        return kerzen


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    """Ein Backfill gegen die Doppel-Boerse, in einer Wegwerf-Ablage."""
    markt = FakeMarkt()
    monkeypatch.setenv("PATHS__DATA_STORE", str(tmp_path / "store"))
    monkeypatch.setattr("cli.BybitMarketData", lambda *a, **k: markt)
    from core.config import get_settings

    get_settings.cache_clear()
    yield CliRunner(), markt
    get_settings.cache_clear()


class TestJederGenannteMarktWirdGeladen:
    def test_zwei_maerkte_werden_beide_gefragt(self, lauf) -> None:
        runner, markt = lauf

        ergebnis = runner.invoke(
            app,
            [
                "backfill", "-m", "BTCUSDT,ETHUSDT", "--intervall", "D",
                "--von", "2017-08-16", "--bis", "2017-09-30",
            ],
        )

        assert ergebnis.exit_code == 0, ergebnis.output
        assert set(markt.gefragt) == {"BTCUSDT", "ETHUSDT"}

    def test_ohne_maerkte_bleibt_es_beim_konfigurierten(self, lauf) -> None:
        """Das alte Verhalten bleibt - geaendert ist, dass es sich aendern
        laesst."""
        runner, markt = lauf

        ergebnis = runner.invoke(
            app,
            [
                "backfill", "--intervall", "D",
                "--von", "2017-08-16", "--bis", "2017-09-30",
            ],
        )

        assert ergebnis.exit_code == 0, ergebnis.output
        assert set(markt.gefragt) == {"BTCUSDT"}

    def test_die_tabelle_nennt_den_markt(self, lauf) -> None:
        """Zwei Maerkte und eine Spalte, die nicht sagt welcher, waeren
        schlimmer als eine Zeile."""
        runner, _ = lauf

        ergebnis = runner.invoke(
            app,
            [
                "backfill", "-m", "BTCUSDT,ETHUSDT", "--intervall", "D",
                "--von", "2017-08-16", "--bis", "2017-09-30",
            ],
        )

        assert "Markt" in ergebnis.output
        assert "ETHUSDT" in ergebnis.output


class TestDerFehlendeKorbWirdGemeldet:
    """**Ein Verbot waere hier falsch** - ein Symbol nachzuladen ist ein
    gueltiger Wunsch. Gesagt wird es trotzdem, samt dem, was es kostet."""

    def test_die_warnung_nennt_das_fehlende_bein(self, lauf) -> None:
        runner, _ = lauf

        ergebnis = runner.invoke(
            app,
            [
                "backfill", "-m", "BTCUSDT", "--intervall", "D",
                "--von", "2017-08-16", "--bis", "2017-09-30",
            ],
        )

        assert "ETHUSDT" in ergebnis.output
        assert "Zulassungskorb" in ergebnis.output

    def test_und_was_das_eine_bein_wert_ist(self, lauf) -> None:
        """Die Zahl gehoert dazu: 5 von 11 gegen 9 von 11."""
        runner, _ = lauf

        ergebnis = runner.invoke(
            app,
            [
                "backfill", "--intervall", "D",
                "--von", "2017-08-16", "--bis", "2017-09-30",
            ],
        )

        # Leerraum eingezogen: 'rich' bricht die Zeile, und wo sie bricht,
        # ist Spaltenbreite und nicht Aussage.
        ausgabe = " ".join(ergebnis.output.split())

        assert "5 von 11" in ausgabe
        assert "9 von 11" in ausgabe

    def test_sie_nennt_den_vollstaendigen_befehl(self, lauf) -> None:
        """Eine Warnung, die nicht sagt, was zu tun ist, kostet nur Zeit."""
        runner, _ = lauf

        ergebnis = runner.invoke(
            app,
            [
                "backfill", "--intervall", "D",
                "--von", "2017-08-16", "--bis", "2017-09-30",
            ],
        )
        ausgabe = " ".join(ergebnis.output.split())

        assert "backfill -m BTCUSDT,ETHUSDT" in ausgabe

    def test_auf_dem_vollen_korb_schweigt_sie(self, lauf) -> None:
        runner, _ = lauf

        ergebnis = runner.invoke(
            app,
            [
                "backfill", "-m", "BTCUSDT,ETHUSDT", "--intervall", "D",
                "--von", "2017-08-16", "--bis", "2017-09-30",
            ],
        )

        assert "Zulassungskorb" not in ergebnis.output


class TestDerKorbStehtAnEinerStelle:
    def test_er_ist_btc_und_eth(self) -> None:
        assert ZULASSUNGSKORB == ("BTCUSDT", "ETHUSDT")

    def test_und_beide_haben_kontraktdaten(self) -> None:
        """Sonst bricht der Lauf mitten im Wettbewerb ab - nach dem Buchen der
        ersten Versuche (Befund 115 hat das Raten dort abgeschafft)."""
        import cli

        for symbol in ZULASSUNGSKORB:
            assert cli._fallback_instrument(symbol).symbol == symbol

    def test_der_registereintrag_steht(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 357)

        assert "5 von 11" in eintrag.ergebnis
        assert "Versuche" in eintrag.ergebnis
