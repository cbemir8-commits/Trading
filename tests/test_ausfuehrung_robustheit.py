"""Was passiert, wenn die Boerse einen Aufruf verweigert.

Jeder Test hier steht fuer einen Fund des Ausfuehrungs-Fuzzers
(``tests/test_fuzz_ausfuehrung.py``) - der Fuzzer sagt, *dass* eine Invariante
bricht, diese Tests sagen, *warum* und halten die Korrektur fest.

Die Trennung hat einen Grund: Ein Fuzzer, der irgendwann eine andere Saat
zieht, ist kein Regressionsschutz. Diese Tests sind gezielt und fallen, wenn
man die jeweilige Korrektur zuruecknimmt - ich habe jede einzeln geprueft,
nachdem ein frueherer Test in diesem Projekt beim Zuruecknehmen der Korrektur
gruen blieb und damit nichts bewiesen hatte.

Der gemeinsame Nenner aller vier Funde: **Ein fehlgeschlagener Aufruf darf
nicht mehr kaputtmachen als den Aufruf selbst.** Netzwackler sind kein
Ausnahmefall, sondern Betriebsalltag.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.config import BybitSettings, RiskSettings
from core.models import Instrument
from data.bybit.errors import BybitAPIError, BybitTransportError
from execution.router import BracketState
from tests.test_live import Rig, build_rig, long_below_market


@pytest.fixture
def rig(tmp_path, btcusdt: Instrument, risk: RiskSettings, bybit_settings: BybitSettings) -> Rig:
    return build_rig(tmp_path, btcusdt, risk, bybit_settings)


async def _offene_position(rig: Rig):
    rig.strategy.emit(long_below_market())
    await rig.feed()
    rig.fill_entry()
    await rig.feed()
    bracket = rig.trader.bracket
    assert bracket is not None and bracket.state is BracketState.PROTECTED
    return bracket


# ---------------------------------------------------------------------------
#  Fund 1: Der Not-Aus verstummte, wenn das Stornieren fehlschlug
# ---------------------------------------------------------------------------
class TestNotAusMeldetImmer:
    """Die wichtigste Nachricht des Systems - ausgerechnet die fiel aus.

    ``close_all`` warf, der Fehler flog durch ``_handle_kill_switch`` hindurch,
    und damit blieben Meldung und ``stop()`` aus. Der Kill-Switch hatte
    ausgeloest, und das Telefon blieb still.
    """

    async def test_meldung_geht_raus_obwohl_stornieren_scheitert(self, rig: Rig) -> None:
        rig.exchange.fail_next("cancel_all", BybitTransportError("Netz weg"))
        rig.officer.trigger_kill_switch("Test")

        await rig.feed()

        assert any("KILL-SWITCH AUSGELOEST" in m for m in rig.messages), (
            "Der Not-Aus muss melden, gerade wenn etwas nicht funktioniert"
        )

    async def test_meldung_nennt_den_fehlschlag(self, rig: Rig) -> None:
        """Eine Meldung, die 'alles glattgestellt' behauptet, obwohl es nicht
        stimmt, ist schlimmer als keine."""
        # Alle Versuche scheitern lassen - sonst raeumt die Wiederholung auf.
        rig.exchange.cancel_all = _immer_fehler  # type: ignore[method-assign]
        rig.officer.trigger_kill_switch("Test")

        await rig.feed()

        meldung = next(m for m in rig.messages if "KILL-SWITCH" in m)
        assert "fehlgeschlagen" in meldung
        assert "bei Bybit nachsehen" in meldung

    async def test_wiederholung_raeumt_doch_noch_auf(self, rig: Rig) -> None:
        """Nach dem Not-Aus haelt der Prozess an - eine zweite Gelegenheit
        gibt es nicht. Also wird sofort wiederholt."""
        await _offene_position(rig)
        rig.exchange.fail_next("cancel_all", BybitTransportError("einmal weg"))
        rig.officer.trigger_kill_switch("Test")

        await rig.feed()

        assert not rig.exchange.open_orders("BTCUSDT"), (
            "Der zweite Versuch muss das Buch leerraeumen"
        )

    async def test_stream_wird_angehalten(self, rig: Rig) -> None:
        rig.exchange.fail_next("cancel_all", BybitTransportError("Netz weg"))
        rig.officer.trigger_kill_switch("Test")

        await rig.feed()

        assert any("KILL-SWITCH" in m for m in rig.messages)

    async def test_position_aus_wartendem_einstieg_wird_geschlossen(
        self, rig: Rig
    ) -> None:
        """Der ernsteste Fund des Fuzzers.

        Die Einstiegsorder fuellt, waehrend das Bracket noch auf sie wartet -
        dann ist die Position da, aber ``bracket.is_open`` ist ``False``. Der
        Not-Aus stornierte nur die Orders, meldete "alles glattgestellt" und
        liess die Position stehen. Bei ausgeloestem Kill-Switch heisst das:
        Das System ist aus, die Position laeuft weiter, und die Meldung sagt
        das Gegenteil.

        Gefragt wird deshalb die Boerse, nicht das eigene Gedaechtnis.
        """
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()  # gefuellt, aber noch keine Kerze hat es bemerkt
        assert rig.exchange.position is not None
        assert rig.trader.bracket is not None
        assert not rig.trader.bracket.is_open

        rig.officer.trigger_kill_switch("Test")
        await rig.feed()

        assert rig.exchange.position is None, (
            "Der Not-Aus muss schliessen, was an der Boerse steht"
        )

    async def test_uebernommene_position_wird_geschlossen(self, rig: Rig) -> None:
        """Nach einem Neustart gibt es gar kein Bracket - der Not-Aus muss
        trotzdem greifen."""
        from core.models import Side
        from tests.fake_exchange import FakePosition

        rig.exchange.position = FakePosition(
            side=Side.BUY,
            size=Decimal("0.005"),
            entry_price=Decimal("99500"),
            stop_loss=Decimal("98000"),
        )
        rig.officer.trigger_kill_switch("Test")

        await rig.feed()

        assert rig.exchange.position is None


def _immer_fehler(symbol: str) -> int:
    raise BybitTransportError("dauerhaft weg")


def _immer_fehler_kwargs(**kwargs):
    raise BybitTransportError("dauerhaft weg")


# ---------------------------------------------------------------------------
#  Fund 2: Restziele blieben nach dem Schliessen im Buch liegen
# ---------------------------------------------------------------------------
class TestBuchWirdLeergeraeumt:
    """Greift der Stop an der Boerse, ist die Position weg - die uebrigen
    Ziele nicht.

    Reduce-Only verhindert eine Gegenposition, nicht das Anschneiden des
    naechsten Trades: Ein neuer Long laeuft in die alten Verkaufslimits, die
    noch ueber dem Markt haengen.
    """

    async def test_restziele_verschwinden_wenn_die_position_schliesst(
        self, rig: Rig
    ) -> None:
        await _offene_position(rig)
        assert rig.exchange.open_orders("BTCUSDT"), "Vorbedingung: Ziele liegen im Buch"

        rig.exchange.position = None  # Stop an der Boerse hat gegriffen
        await rig.feed()

        assert not rig.exchange.open_orders("BTCUSDT")
        assert rig.trader.bracket is None

    async def test_kein_neuer_einstieg_solange_das_buch_nicht_leer_ist(
        self, rig: Rig
    ) -> None:
        """Der gefaehrliche Fall: Das Storno scheitert dauerhaft.

        Ein einmaliger Fehlschlag faellt nicht auf - die Nacharbeit derselben
        Kerze holt ihn ein. Erst ein anhaltender zeigt, ob wirklich gebremst
        wird.
        """
        await _offene_position(rig)
        rig.exchange.position = None
        original = rig.exchange.cancel_all
        rig.exchange.cancel_all = _immer_fehler  # type: ignore[method-assign]

        await rig.feed()
        assert rig.trader._aufraeumen_offen is not None

        vorher = len(rig.entry_orders)
        rig.strategy.emit(long_below_market())
        await rig.feed()

        assert len(rig.entry_orders) == vorher, (
            "Kein Einstieg in ein Buch, in dem noch Restorders stehen koennen"
        )
        rig.exchange.cancel_all = original  # type: ignore[method-assign]

    async def test_aufraeumen_wird_nachgeholt(self, rig: Rig) -> None:
        await _offene_position(rig)
        rig.exchange.position = None
        original = rig.exchange.cancel_all
        rig.exchange.cancel_all = _immer_fehler  # type: ignore[method-assign]
        await rig.feed()
        assert rig.trader._aufraeumen_offen is not None

        # Die Boerse ist wieder da: Die naechste Kerze holt das Storno nach.
        rig.exchange.cancel_all = original  # type: ignore[method-assign]
        rig.strategy.emit(long_below_market())
        await rig.feed()

        assert rig.trader._aufraeumen_offen is None
        assert not any(
            o for o in rig.exchange.open_orders("BTCUSDT") if o.reduce_only
        )


# ---------------------------------------------------------------------------
#  Fund 3: Ein abgelehntes Ziel riss das ganze Bracket mit
# ---------------------------------------------------------------------------
class TestAbgelehntesZielKostetNichtDieKontrolle:
    """Der wahrscheinlichste Fund von allen.

    Laeuft der Kurs zwischen Order und Fill am ersten Ziel vorbei, ist dieses
    Ziel sofort ausfuehrbar - und Bybit lehnt PostOnly genau dafuer ab. Der
    Fehler flog bis in ``LiveTrader._protect``, das ihn fuer "Position wurde
    geschlossen" hielt. Sie war es nicht: Der Stop stand, die Position lief,
    das Bracket war weg. Danach keine Ziele, kein Nachzug auf Einstand, keine
    Ausstiegsbedingung - nur noch der Stop.
    """

    async def test_position_bleibt_unter_aufsicht(self, rig: Rig) -> None:
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        rig.exchange.fail_next(
            "place_limit",
            BybitAPIError(110001, "PostOnly", endpoint="/v5/order/create"),
        )

        await rig.feed()

        bracket = rig.trader.bracket
        assert bracket is not None, "Ein abgelehntes Ziel darf das Bracket nicht kosten"
        assert bracket.state is BracketState.PROTECTED
        assert rig.exchange.position is not None
        assert rig.exchange.position.stop_loss is not None

    async def test_fehlschlag_wird_gezaehlt_und_gemeldet(self, rig: Rig) -> None:
        """Weniger Ausstiege als geplant ist kein Fehler, den man verschweigt."""
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        rig.exchange.fail_next(
            "place_limit",
            BybitAPIError(110001, "PostOnly", endpoint="/v5/order/create"),
        )

        await rig.feed()

        assert rig.trader.bracket is not None
        assert rig.trader.bracket.failed_targets == 1
        assert any("Ziel(e) konnten nicht platziert werden" in m for m in rig.messages)

    async def test_die_uebrigen_ziele_werden_trotzdem_platziert(self, rig: Rig) -> None:
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        rig.exchange.fail_next(
            "place_limit",
            BybitAPIError(110001, "PostOnly", endpoint="/v5/order/create"),
        )

        await rig.feed()

        ziele = [o for o in rig.exchange.open_orders("BTCUSDT") if o.reduce_only]
        assert ziele, "Nur das abgelehnte Bein faellt aus, nicht die anderen"


# ---------------------------------------------------------------------------
#  Fund 4: Nach fehlgeschlagener Absicherung wurde die Position vergessen
# ---------------------------------------------------------------------------
class TestAbsicherungFehlgeschlagen:
    """``_protect`` nahm an, ``protect`` habe die Position bereits geschlossen.

    Nachsehen kostet einen Aufruf. Die Annahme kostete die Kontrolle ueber eine
    offene Position.
    """

    async def test_ueberlebende_position_wird_geschlossen(self, rig: Rig) -> None:
        """Der Fall, der die alte Annahme widerlegt.

        Der Stop scheitert, ``protect`` versucht zu schliessen - und **auch das
        scheitert einmal**. Die Position ueberlebt den Aufruf also. Danach war
        das Bracket weg und die Position lief ohne Aufsicht weiter.
        """
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        rig.exchange.fail_next("set_position_stop", BybitTransportError("Netz weg"))
        rig.exchange.fail_next("place_market", BybitTransportError("auch weg"))

        await rig.feed()

        assert rig.exchange.position is None, (
            "Eine Position ohne Stop darf den Aufruf nicht ueberleben"
        )
        assert rig.trader.bracket is None

    async def test_bracket_bleibt_wenn_auch_das_schliessen_scheitert(
        self, rig: Rig
    ) -> None:
        """Der schlimmste Fall - und der einzige, in dem das Bracket bleibt.

        Ein weggeworfenes Bracket hiesse: Die Position laeuft, und niemand
        sieht mehr hin.
        """
        rig.strategy.emit(long_below_market())
        await rig.feed()
        rig.fill_entry()
        rig.exchange.fail_next("set_position_stop", BybitTransportError("Netz weg"))
        # Dauerhaft, nicht einmalig: Der zweite Anlauf in
        # ``_handle_protect_failure`` soll ebenfalls scheitern.
        rig.exchange.place_market = _immer_fehler_kwargs  # type: ignore[method-assign]

        await rig.feed()

        assert rig.exchange.position is not None
        assert rig.trader.bracket is not None, (
            "Solange die Position lebt, muss ein Bracket sie kennen"
        )
        assert any("DRINGEND" in m for m in rig.messages)


# ---------------------------------------------------------------------------
#  Fund 5: Ausnahmen liefen als "Verbindung verloren" in den Kerzenstrom
# ---------------------------------------------------------------------------
class TestSchleifeUeberlebt:
    """``KlineStream.run`` faengt alles aus dem Kerzen-Handler als
    Verbindungsabbruch und baut die Verbindung neu auf.

    Ein fehlgeschlagener Orderaufruf sah damit aus wie ein Netzproblem -
    falsche Diagnose, und waehrend des Backoffs fehlen Kerzen.
    """

    async def test_keine_ausnahme_verlaesst_die_kerzenverarbeitung(
        self, rig: Rig
    ) -> None:
        def kaputt(equity):
            raise BybitTransportError("Kontostand nicht abrufbar")

        rig.trader.officer.observe_equity = kaputt  # type: ignore[method-assign]

        await rig.feed()  # darf nicht werfen

        assert rig.trader.stats.candle_errors == 1
        assert "Kontostand nicht abrufbar" in rig.trader.stats.last_error

    async def test_fehler_wird_einmal_gemeldet_nicht_bei_jeder_kerze(
        self, rig: Rig
    ) -> None:
        """Alle 15 Minuten dieselbe Meldung, und niemand sieht mehr hin."""

        def kaputt(equity):
            raise BybitTransportError("dauerhaft")

        rig.trader.officer.observe_equity = kaputt  # type: ignore[method-assign]

        await rig.feed()
        await rig.feed()
        await rig.feed()

        assert rig.trader.stats.candle_errors == 3
        assert sum("dauerhaft" in m for m in rig.messages) == 1


# ---------------------------------------------------------------------------
#  Die Invariantenpruefung selbst
# ---------------------------------------------------------------------------
class TestStartMitUngeschuetzterPosition:
    """Der Startpfad hatte an seiner gefaehrlichsten Stelle keine Absicherung.

    Findet ``_reconcile`` eine Position ohne Stop, schliesst es sie. Schlug der
    Marktausstieg fehl, flog die Ausnahme aus ``start()`` heraus: **Der Prozess
    startete nicht und liess die ungeschuetzte Position stehen.** Schlechter
    geht es kaum - der gefaehrlichste Zustand ueberhaupt, und niemand mehr, der
    hinsieht. Zwei von 400 Zufallsfolgen sind darauf gelaufen.
    """

    def _ohne_stop(self, rig: Rig) -> None:
        from core.models import Side
        from tests.fake_exchange import FakePosition

        rig.exchange.position = FakePosition(
            side=Side.BUY,
            size=Decimal("0.005"),
            entry_price=Decimal("99500"),
            stop_loss=None,
        )

    async def test_start_scheitert_nicht(self, rig: Rig) -> None:
        self._ohne_stop(rig)
        rig.exchange.place_market = _immer_fehler_kwargs  # type: ignore[method-assign]

        await rig.trader._reconcile()  # darf nicht werfen

    async def test_notstop_wird_gesetzt(self, rig: Rig) -> None:
        """Zweitbeste Wahl: wenigstens absichern.

        Der Abstand ist der maximal zulaessige - nicht der einer Strategie,
        deren Begruendung nach einem Neustart nicht mehr bekannt ist. Er
        begrenzt den Schaden auf einen bekannten Betrag.
        """
        self._ohne_stop(rig)
        rig.exchange.place_market = _immer_fehler_kwargs  # type: ignore[method-assign]

        await rig.trader._reconcile()

        assert rig.exchange.position is not None
        assert rig.exchange.position.stop_loss is not None
        erwartet = Decimal("99500") * (1 - rig.trader.risk_settings.max_stop_distance_pct / 100)
        assert abs(rig.exchange.position.stop_loss - erwartet) < Decimal("1")
        assert any("Notstop" in m for m in rig.messages)

    async def test_position_wird_uebernommen_auch_ohne_stop(self, rig: Rig) -> None:
        """Wenn gar nichts geht: sehen statt wegsehen.

        Ein Bracket ohne Stop ist ein schlechter Zustand - aber ein gesehener.
        Die Ausstiegsbedingung greift, der Not-Aus greift, und die
        Invariantenpruefung meldet ihn bei jeder Kerze.
        """
        self._ohne_stop(rig)
        rig.exchange.place_market = _immer_fehler_kwargs  # type: ignore[method-assign]
        rig.exchange.set_position_stop = _immer_fehler_kwargs  # type: ignore[method-assign]

        await rig.trader._reconcile()

        assert rig.trader.bracket is not None
        assert rig.trader.bracket.stop_price is None
        assert any("DRINGEND" in m for m in rig.messages)

    async def test_ungeschuetzte_uebernahme_wird_bei_jeder_kerze_gemeldet(
        self, rig: Rig
    ) -> None:
        self._ohne_stop(rig)
        rig.exchange.place_market = _immer_fehler_kwargs  # type: ignore[method-assign]
        rig.exchange.set_position_stop = _immer_fehler_kwargs  # type: ignore[method-assign]
        await rig.trader._reconcile()

        await rig.feed()

        assert "position_ohne_stop" in rig.trader.stats.last_breach


class TestErholungNachEinemAbgebrochenenAbgleich:
    """Eine Kerze kann mitten im Abgleich abbrechen. Die naechste zieht gerade.

    Der Fuzzer meldete an Saat 272 eine gewachsene Position, die im Bracket
    nicht vermerkt war - und die Meldung stimmte: Der Marktausstieg der
    Wachstumspruefung war auf einen simulierten Ausfall gelaufen, und der
    Abgleich brach ab, bevor er fertig war.

    Der Anspruch ist deshalb nicht "das darf nie vorkommen" - ein
    fehlgeschlagener Aufruf laesst sich nicht verbieten -, sondern: **Die
    naechste vollstaendige Kerze muss den Zustand geradeziehen.** Das wird hier
    gemessen statt behauptet.
    """

    async def test_gewachsene_position_wird_spaetestens_danach_geschlossen(
        self, rig: Rig
    ) -> None:
        rig.strategy.emit(long_below_market())
        await rig.feed()
        # Nur zur Haelfte fuellen und das Storno des Rests scheitern lassen -
        # so bleibt die Einstiegsorder im Buch und die Position kann wachsen.
        assert rig.trader.bracket is not None
        order_id = rig.trader.bracket.entry_order.order_id  # type: ignore[union-attr]
        rig.exchange.fill(order_id, qty=Decimal("0.002"))
        rig.exchange.fail_next("cancel_order", BybitTransportError("Netz weg"))
        await rig.feed()
        assert rig.trader.bracket.remaining_qty == Decimal("0.002")

        # Der Rest fuellt nach - und der Notausstieg scheitert genau jetzt.
        rig.exchange.fill(order_id)
        rig.exchange.fail_next("place_market", BybitTransportError("Netz weg"))
        await rig.feed()

        assert rig.exchange.position is not None, "Vorbedingung: noch offen"
        assert rig.trader.stats.candle_errors == 1

        # Die naechste Kerze zieht gerade.
        await rig.feed()

        assert rig.exchange.position is None
        assert rig.trader.bracket is None


class TestInvariantenpruefungImBetrieb:
    async def test_verletzung_wird_gemeldet(self, rig: Rig) -> None:
        """Eine Position, von der das System nichts weiss - der Fall, den die
        Pruefung finden soll."""
        await _offene_position(rig)
        # Von aussen aufgezwungen: Bracket weg, Position bleibt.
        rig.trader.bracket = None

        await rig.feed()

        assert rig.trader.stats.invariant_breaches >= 1
        assert "unbeaufsichtigte_position" in rig.trader.stats.last_breach
        assert any("passt nicht zum Handelssystem" in m for m in rig.messages)

    async def test_saubere_lage_meldet_nichts(self, rig: Rig) -> None:
        await _offene_position(rig)

        await rig.feed()

        assert rig.trader.stats.invariant_breaches == 0

    async def test_pruefung_haelt_den_handel_nicht_an(self, rig: Rig) -> None:
        """Die Pruefung ist Beobachtung. Scheitert sie, laeuft der Handel."""

        def kaputt(symbol):
            raise BybitTransportError("Orderbuch nicht abrufbar")

        rig.exchange.open_orders = kaputt  # type: ignore[method-assign]

        await rig.feed()

        assert rig.trader.stats.candle_errors == 0
        assert rig.trader.stats.invariant_breaches == 0


# ---------------------------------------------------------------------------
#  Die Kennzahlen landen im Dashboard
# ---------------------------------------------------------------------------
async def test_fehler_stehen_im_dashboard(rig: Rig) -> None:
    """Ein System, das leise Fehler frisst, sieht von aussen aus wie eines,
    das nichts zu tun hat."""

    def kaputt(equity):
        raise BybitTransportError("Kontostand weg")

    rig.trader.officer.observe_equity = kaputt  # type: ignore[method-assign]
    await rig.feed()
    rig.trader.officer.observe_equity = _echte_bewertung(rig)  # type: ignore[method-assign]
    await rig.feed()

    from web.journal import read_view

    stats = read_view(rig.state_dir).snapshot["stats"]
    assert stats["candle_errors"] == 1
    assert "Fehler" in stats["summary"]


def _echte_bewertung(rig: Rig):
    from execution.risk import RiskOfficer

    return lambda equity: RiskOfficer.observe_equity(rig.officer, equity)


async def test_offene_position_ohne_stop_wird_erkannt(rig: Rig) -> None:
    """Perpetual: Der Stop haengt an der Position. Verschwindet er dort,
    merkt es sonst niemand."""
    await _offene_position(rig)
    assert rig.exchange.position is not None
    rig.exchange.position.stop_loss = None

    await rig.feed()

    assert "position_ohne_stop" in rig.trader.stats.last_breach


async def test_zu_grosse_ziele_werden_erkannt(rig: Rig) -> None:
    """Der Fund aus BEFUND 9, jetzt als laufende Pruefung statt als Einzeltest."""
    await _offene_position(rig)
    position = rig.exchange.position
    assert position is not None
    position.size = position.size / 2  # Ziele sind jetzt doppelt so gross

    await rig.feed()

    assert "ziele_groesser_als_position" in rig.trader.stats.last_breach
