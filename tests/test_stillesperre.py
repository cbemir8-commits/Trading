"""Zwei Sperren hielten den Handel an, ohne es zu sagen - Befund 381.

Gefunden beim Lesen des Dashboards - der einen Oberflaeche, die in dieser
Sitzung noch niemand kritisch gelesen hatte. Die Vermutung kam aus Befund 376:
Dort fiel beim Messen auf, dass die **Tagesgrenze nur ``paused_until`` setzt**
und ``trading_state`` auf "active" laesst (die Wochengrenze setzt dagegen
PAUSED, der Rueckgang KILLED).

Gemessen am echten Pfad - Konto von 500 auf 484, also -3,2 % am Tag:

    Offizier      trading_state = active, paused_until gesetzt
    blockade()    daily_loss_limit - "Tageslimit erreicht, Pause noch 24.0 h"
    Momentaufnahme  trading_state "active", kill_reason "", paused_until FEHLT
    Dashboard     kein Banner, Kopfzeile "laeuft"

Der Roboter nimmt bis zu **24 Stunden** keinen Einstieg, und auf dem
Bildschirm steht, dass alles laeuft. Das ist dieselbe Verwechslung wie in
Befund 360 - "kein Signal" gegen "keine Eingabe" -, nur eine Ebene weiter
aussen: diesmal nicht im Protokoll, sondern auf der Seite, die der Nutzer
waehrend des Betriebs offen hat.

Dasselbe gilt fuer die **Terminsperre** (``news_blackout_until``): Sie lehnt
jeden Einstieg ab und stand ebenfalls nicht in der Momentaufnahme. Sie greift
selten - der Kalender sperrt in acht Jahren sechs Einstiege (Befund 271) -,
aber genau deshalb waere sie auf dem Bildschirm am schwersten zu erraten.

Warum nicht ``blockade()`` in die Momentaufnahme
-----------------------------------------------
Weil sie auch 'position_already_open' meldet, und das ist kein Alarm, sondern
der Normalfall. Ein Banner, der bei jeder offenen Position aufleuchtet, ist
nach drei Tagen unsichtbar. Aufgenommen sind die **zeitlichen** Sperren, die
``trading_state`` nicht anfassen - die lauten Zustaende hat die Kopfzeile
schon.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from execution.risk import TradingState, VetoReason

HTML = Path("web/static/index.html")


@pytest.fixture
def rig(tmp_path, btcusdt, risk, bybit_settings):
    from tests.test_live import build_rig

    return build_rig(tmp_path, btcusdt, risk, bybit_settings)


def _momentaufnahme(tmp_path: Path) -> dict:
    daten = json.loads((tmp_path / "state" / "live.json").read_text())
    return daten.get("snapshot", daten)


class TestDieTagesgrenzeStandNichtAufDemBildschirm:
    """**Der Befund.** Erst der Nachweis, dass der Handel wirklich steht."""

    def test_sie_laesst_den_zustand_auf_active(self, rig) -> None:
        rig.trader.officer.observe_equity(Decimal("500"))
        rig.trader.officer.observe_equity(Decimal("484"))

        zustand = rig.trader.officer.state

        assert zustand.trading_state is TradingState.ACTIVE
        assert zustand.paused_until is not None

    def test_und_der_handel_steht_trotzdem(self, rig) -> None:
        rig.trader.officer.observe_equity(Decimal("500"))
        rig.trader.officer.observe_equity(Decimal("484"))

        sperre = rig.trader.officer.blockade()

        assert sperre is not None
        assert sperre.reason is VetoReason.DAILY_LOSS_LIMIT
        assert "Tageslimit erreicht" in sperre.detail

    @pytest.mark.asyncio
    async def test_jetzt_steht_sie_in_der_momentaufnahme(
        self, rig, tmp_path
    ) -> None:
        rig.trader.officer.observe_equity(Decimal("500"))
        rig.trader.officer.observe_equity(Decimal("484"))

        await rig.feed()

        s = _momentaufnahme(tmp_path)
        assert s["trading_state"] == "active"
        assert s["paused_until"] is not None
        assert datetime.fromisoformat(s["paused_until"]) > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_ohne_sperre_steht_dort_nichts(self, rig, tmp_path) -> None:
        """Die Gegenprobe: Ein Feld, das immer gefuellt ist, meldet nichts."""
        rig.trader.officer.observe_equity(Decimal("500"))

        await rig.feed()

        s = _momentaufnahme(tmp_path)
        assert s["paused_until"] is None
        assert s["news_blackout_until"] is None


class TestDieTerminsperreAuch:
    @pytest.mark.asyncio
    async def test_sie_steht_jetzt_drin(self, rig, tmp_path) -> None:
        """Selten und deshalb am schwersten zu erraten: sechs gesperrte
        Einstiege in acht Jahren (Befund 271)."""
        rig.trader.officer.state.news_blackout_until = datetime.now(UTC) + timedelta(
            hours=2
        )

        await rig.feed()

        s = _momentaufnahme(tmp_path)
        assert s["news_blackout_until"] is not None
        assert s["trading_state"] == "active"


class TestDerBannerZeigtBeide:
    """Die Oberflaeche ist JavaScript - geprueft wird der Quelltext.

    Keine Attrappe eines Browsers: Dieser Test faellt, wenn der Zweig
    verschwindet, und das ist genau, was er soll. Was er **nicht** kann, ist
    pruefen, wie es aussieht.
    """

    @staticmethod
    def _quelle() -> str:
        return HTML.read_text(encoding="utf-8")

    def test_die_tagespause_hat_einen_zweig(self) -> None:
        quelle = self._quelle()

        assert "s.paused_until" in quelle
        assert "Tagesverlustgrenze erreicht" in quelle

    def test_die_terminsperre_auch(self) -> None:
        quelle = self._quelle()

        assert "s.news_blackout_until" in quelle
        assert "Terminsperre" in quelle

    def test_eine_abgelaufene_sperre_ist_keine(self) -> None:
        """``bis`` gibt ``null`` zurueck, wenn die Sperre vorbei ist - und der
        Banner haengt daran. Ein Banner ueber eine Sperre von gestern waere
        schlimmer als keiner."""
        quelle = self._quelle()

        assert "function bis(iso)" in quelle
        assert "|| seconds <= 0) return null;" in quelle
        assert "bis(s.paused_until) !== null" in quelle

    def test_der_kill_switch_steht_weiter_oben(self) -> None:
        """Die Reihenfolge ist die Botschaft: Ein Not-Aus ist wichtiger als
        eine Tagespause, und ein toter Prozess wichtiger als beide."""
        quelle = self._quelle()
        stelle = lambda text: quelle.index(text)  # noqa: E731

        assert stelle("KILL-SWITCH AKTIV") < stelle("antwortet nicht")
        assert stelle("antwortet nicht") < stelle("Tagesverlustgrenze erreicht")
        assert stelle("Tagesverlustgrenze erreicht") < stelle("Terminsperre")


class TestWarumNichtDieGanzeBlockade:
    def test_eine_offene_position_ist_kein_alarm(self, rig) -> None:
        """``blockade`` meldet auch 'position_already_open'. Das in die
        Momentaufnahme zu heben hiesse, bei jeder offenen Position einen
        Banner zu zeigen - nach drei Tagen sieht den niemand mehr.
        """
        sperre = rig.trader.officer.blockade(open_positions=1)

        assert sperre is not None
        assert sperre.reason is VetoReason.POSITION_ALREADY_OPEN

    @pytest.mark.asyncio
    async def test_darum_stehen_nur_die_zeitlichen_sperren_drin(
        self, rig, tmp_path
    ) -> None:
        await rig.feed()

        s = _momentaufnahme(tmp_path)
        zeitlich = {"paused_until", "news_blackout_until"}

        assert zeitlich <= set(s)
        assert "blockade" not in s
        assert not any("position_already_open" in str(v) for v in s.values())


# ---------------------------------------------------------------------------
#  Befund 382: die dritte Sperre - und eine Meldung, die niemand zeigte
# ---------------------------------------------------------------------------
def _immer_fehler(symbol: str) -> int:
    from data.bybit.errors import BybitTransportError

    raise BybitTransportError("dauerhaft weg")


async def _storno_scheitert(rig):
    """Eine Position eroeffnen, schliessen lassen, und das Storno brechen.

    Dieselbe Technik wie in ``test_ausfuehrung_robustheit.py`` - dort ist
    gezeigt, **dass** gebremst wird; hier geht es darum, ob man es sieht.

    Gibt das echte ``cancel_all`` zurueck, damit der Aufrufer die Boerse
    wieder heil machen kann. Erst stand hier ein
    ``__class__.cancel_all.__get__(...)`` auf der Rueckseite - das ist
    dasselbe, nur unlesbar, und die Nachbardatei macht es seit langem so.
    """
    from tests.test_live import long_below_market

    rig.strategy.emit(long_below_market())
    await rig.feed()
    rig.fill_entry()
    await rig.feed()
    rig.exchange.position = None
    original = rig.exchange.cancel_all
    rig.exchange.cancel_all = _immer_fehler  # type: ignore[method-assign]
    await rig.feed()
    return original


def _ereignisse(tmp_path: Path) -> list[dict]:
    datei = tmp_path / "state" / "events.jsonl"
    if not datei.exists():
        return []
    return [json.loads(z) for z in datei.read_text().splitlines() if z.strip()]


class TestDasOffeneAufraeumenStandNirgends:
    """**Der Befund.** Ein Fehlerzustand, der jeden Einstieg sperrt."""

    @pytest.mark.asyncio
    async def test_es_sperrt_wirklich(self, rig) -> None:
        from tests.test_live import long_below_market

        await _storno_scheitert(rig)
        assert rig.trader._aufraeumen_offen is not None

        vorher = len(rig.entry_orders)
        for _ in range(3):
            rig.strategy.emit(long_below_market())
            await rig.feed()

        assert len(rig.entry_orders) == vorher

    @pytest.mark.asyncio
    async def test_und_steht_jetzt_in_der_momentaufnahme(
        self, rig, tmp_path
    ) -> None:
        await _storno_scheitert(rig)

        s = _momentaufnahme(tmp_path)

        assert s["aufraeumen_offen"] == rig.trader._aufraeumen_offen
        assert s["trading_state"] == "active", (
            "der Zustand bleibt aktiv - genau deshalb braucht es das Feld"
        )

    @pytest.mark.asyncio
    async def test_ohne_fehler_steht_dort_nichts(self, rig, tmp_path) -> None:
        await rig.feed()

        assert _momentaufnahme(tmp_path)["aufraeumen_offen"] is None


class TestGemeldetWirdEinmalJeUebergang:
    @pytest.mark.asyncio
    async def test_nicht_bei_jeder_kerze(self, rig, tmp_path) -> None:
        """'_nacharbeit_erledigt' laeuft je Balken. Eine Zeile alle fuenfzehn
        Minuten ist so gut wie keine - dieselbe Sperre wie bei der
        Funding-Warnung (373) und der fehlenden Vorgeschichte (376)."""
        from tests.test_live import long_below_market

        await _storno_scheitert(rig)
        for _ in range(4):
            rig.strategy.emit(long_below_market())
            await rig.feed()

        offen = [e for e in _ereignisse(tmp_path) if "Aufraeumen offen" in e["message"]]

        assert len(offen) == 1
        assert offen[0]["kind"] == "warning"
        assert "Keine neuen Einstiege" in offen[0]["message"]

    @pytest.mark.asyncio
    async def test_und_das_ende_wird_auch_gemeldet(self, rig, tmp_path) -> None:
        """Sonst bleibt die Warnung in der Liste stehen, und wer sie spaeter
        liest, sieht nur das Problem."""
        from tests.test_live import long_below_market

        original = await _storno_scheitert(rig)
        rig.exchange.cancel_all = original  # type: ignore[method-assign]
        rig.strategy.emit(long_below_market())
        await rig.feed()

        assert rig.trader._aufraeumen_offen is None
        entspannt = [e for e in _ereignisse(tmp_path) if "nachgeholt" in e["message"]]
        assert len(entspannt) == 1
        assert entspannt[0]["kind"] == "info"

    @pytest.mark.asyncio
    async def test_eine_zweite_stoerung_meldet_sich_wieder(
        self, rig, tmp_path
    ) -> None:
        """Die Sperre gilt dem Uebergang, nicht dem Lauf."""
        from tests.test_live import long_below_market

        original = await _storno_scheitert(rig)
        rig.exchange.cancel_all = original  # type: ignore[method-assign]
        rig.strategy.emit(long_below_market())
        await rig.feed()

        await _storno_scheitert(rig)

        offen = [e for e in _ereignisse(tmp_path) if "Aufraeumen offen" in e["message"]]
        assert len(offen) == 2


class TestDieVerletzungWurdeVeroeffentlichtUndFallenGelassen:
    """``invariant_breaches`` stand im Schnappschuss und nirgends auf dem
    Bildschirm - obwohl es die lauteste Meldung des Systems ist."""

    @pytest.mark.asyncio
    async def test_sie_steht_in_der_momentaufnahme(self, rig, tmp_path) -> None:
        await _storno_scheitert(rig)

        stats = _momentaufnahme(tmp_path)["stats"]

        assert stats["invariant_breaches"] > 0
        assert "Reduce-Only" in stats["last_breach"]

    def test_und_jetzt_auch_im_banner(self) -> None:
        quelle = HTML.read_text(encoding="utf-8")

        assert "s.stats.invariant_breaches" in quelle
        assert "Invariante verletzt" in quelle

    def test_und_in_der_betriebstabelle(self) -> None:
        """Der Banner zeigt die laufende Lage, die Tabelle den Stand. Beides:
        Ein Banner verschwindet, wenn sich der Zustand entspannt - die Zahl
        bleibt."""
        quelle = HTML.read_text(encoding="utf-8")

        assert "st.invariant_breaches" in quelle
        assert "st.candle_errors" in quelle

    def test_das_aufraeumen_hat_auch_einen_banner(self) -> None:
        quelle = HTML.read_text(encoding="utf-8")

        assert "s.aufraeumen_offen" in quelle
        assert "Aufräumen offen" in quelle

    def test_die_reihenfolge_bleibt_eine_rangfolge(self) -> None:
        """Not-Aus, dann toter Prozess, dann die strukturellen Fehler, dann
        die gewollten Zustaende, dann die zeitlichen Pausen.

        Die strukturellen stehen **vor** 'pausiert': Eine Pause hat der Nutzer
        selbst gesetzt und kennt sie, eine verletzte Invariante nicht.
        """
        quelle = HTML.read_text(encoding="utf-8")
        stelle = quelle.index

        assert stelle("KILL-SWITCH AKTIV") < stelle("antwortet nicht")
        assert stelle("antwortet nicht") < stelle("Invariante verletzt")
        assert stelle("Invariante verletzt") < stelle("Aufräumen offen")
        assert stelle("Aufräumen offen") < stelle("Pausiert —")
        assert stelle("Pausiert —") < stelle("Tagesverlustgrenze erreicht")
