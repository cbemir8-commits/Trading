"""Der Livebetrieb laedt seine Funding-Raten nach - Befund 373.

Die offene Folge aus Befund 361, dort selbst so hinterlassen: Der Livepuffer
bekam seine Funding-Spalte, gelesen wurde der Speicher aber genau **einmal**,
beim Start (``_load_history``). ``_frist_anwenden`` setzt die Spalte nach drei
Zahlungsperioden auf NaN, und ``_funding_pruefen`` lief nur beim Start. Ein
Roboter, der gesund startet, handelt also nach 24 Stunden nicht mehr - und sagt
dazu nichts.

Gemessen auf 72 Stunden M15-Kerzen, Carry-Regel aus Generation 5, Raten im
Speicher bis zum Start, Boerse zahlt weiter:

    OHNE Auffrischung    97/288 Kerzen mit Rate   31 Raten    0 Anfragen    97 Einstiege
    MIT  Auffrischung   288/288 Kerzen mit Rate   39 Raten    8 Anfragen   288 Einstiege

97 Kerzen sind 24,25 Stunden. Der erste Tag sieht gesund aus, danach ist Ruhe:
zwei von drei Handelstagen verloren, ohne einen Fehler im Protokoll. Acht
Anfragen auf 72 Stunden sind eine je neun Stunden - das ist der Preis.

Warum nicht die Rate aus dem Ticker
-----------------------------------
Weil es eine andere Groesse ist. Der Ticker fuehrt die Rate der **naechsten**
Zahlung; der Backtest rechnet auf den **festgestellten**. Geholt wird deshalb
ueber ``get_funding_history`` und ueber dieselbe Funktion, die ``cli funding``
benutzt - eine Quelle, ein Schreibpfad, ein Entprellen.

Die Uhr
-------
Diese Tests stellen die Uhr selbst (``clock``). Der erste Messversuch tat das
nicht, und er log: Die Frist rechnet in **Kerzenzeit**, das Nachladen in
**Wanduhrzeit**, und wenn 48 Stunden Kerzen in einer Sekunde eintreffen, laeuft
nur die eine Zeit. Im Betrieb laufen beide zusammen - also muessen sie das im
Test auch.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest
import structlog
from structlog.testing import capture_logs

from core.models import FundingRate, Interval
from data.funding import FUNDING_INTERVAL, SPALTE
from execution.live import FUNDINGFRIST, NACHLADEABSTAND, NACHLADESEITEN
from tests.test_live import HISTORY_BARS, build_rig

#: Dieselbe Rate wie in ``test_livefunding.py``, aus demselben Grund (Befund
#: 359): unter der Schwelle der Carry-Regel.
RATE = Decimal("0.00005")

#: Ein fester Startpunkt. Fest und nicht ``now``, weil die Uhr hier gestellt
#: wird - ein Test, der von der echten Uhrzeit abhaengt, ist keiner.
BEGINN = datetime(2026, 6, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _alle_stufen():
    """Die Stufe fuer die Dauer des Tests auf 'debug' und danach zurueck.

    Dieselbe Vorsichtsmassnahme wie in ``test_simulationsmeldung.py``:
    ``structlog`` filtert nach Stufe, **bevor** ``capture_logs`` etwas sieht,
    und ``cli._configure_logging`` stellt die Stufe global. Ohne das haengt das
    Ergebnis an der Reihenfolge der Tests - und ein Ergebnis, das von der
    Reihenfolge abhaengt, ist keins (Befund 362).
    """
    vorher = structlog.get_config()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
    )
    yield
    structlog.configure(**vorher)


class Uhr:
    """Die Wanduhr, die mit den Kerzen laeuft - wie im Betrieb."""

    def __init__(self, jetzt: datetime) -> None:
        self.jetzt = jetzt

    def __call__(self) -> datetime:
        return self.jetzt


class BoerseFaellt:
    """Eine Boerse, deren Funding-Abruf scheitert. Alles andere wie gehabt."""

    def __init__(self, echt) -> None:
        self._echt = echt
        self.versuche = 0

    def __getattr__(self, name):
        return getattr(self._echt, name)

    def get_funding_history(self, *args, **kwargs):
        self.versuche += 1
        raise ConnectionError("Boerse nicht erreichbar")


def _raten(von: datetime, bis: datetime) -> list[FundingRate]:
    """Alle acht Stunden eine Rate, von ``von`` bis einschliesslich ``bis``."""
    out: list[FundingRate] = []
    t = von
    while t <= bis:
        out.append(
            FundingRate(symbol="BTCUSDT", funding_time=t, funding_rate=RATE)
        )
        t += FUNDING_INTERVAL
    return out


def _carry_regel():
    """Die Carry-Regel aus Generation 5 - dieselbe wie in Befund 360/361."""
    from research.seeds import GENERATIONS

    for eintrag in GENERATIONS[5]:
        genome = eintrag() if callable(eintrag) else eintrag
        if "arry" in genome.name:
            return genome
    pytest.skip("keine Carry-Regel in Generation 5")


def _rig(
    tmp_path,
    btcusdt,
    risk,
    bybit_settings,
    *,
    stunden: int = 72,
    im_speicher_bis: datetime | None = None,
    an_der_boerse_bis: datetime | None = None,
    mit_speicher: bool = True,
    carry: bool = True,
):
    """Ein Roboter, dessen Uhr gestellt werden kann.

    ``im_speicher_bis`` ist der Stand, den ``cli funding`` hinterlassen hat;
    ``an_der_boerse_bis``, wie weit die Boerse inzwischen gezahlt hat. Genau
    dieser Abstand ist der Befund.
    """
    from strategy.compiler import compile_genome

    uhr = Uhr(BEGINN)
    speicher_bis = BEGINN if im_speicher_bis is None else im_speicher_bis
    boerse_bis = (
        BEGINN + timedelta(hours=stunden + 8)
        if an_der_boerse_bis is None
        else an_der_boerse_bis
    )
    rig = build_rig(
        tmp_path,
        btcusdt,
        risk,
        bybit_settings,
        strategy=compile_genome(_carry_regel()) if carry else None,
        funding_raten=(
            _raten(BEGINN - timedelta(days=10), speicher_bis)
            if mit_speicher
            else None
        ),
        markt_raten=_raten(BEGINN - timedelta(days=10), boerse_bis),
        verlauf_ab=BEGINN - HISTORY_BARS * Interval.M15.duration,
        clock=uhr,
    )
    return rig, uhr


async def _laufen_lassen(rig, uhr, *, stunden: int) -> int:
    """Kerzen zustellen und die Uhr mitnehmen. Gibt die Kerzen **mit** Rate."""
    mit_zahl = 0
    for _ in range(stunden * 4):
        uhr.jetzt = rig.next_open + Interval.M15.duration
        await rig.feed()
        if not pd.isna(rig.trader._frame[SPALTE].iloc[-1]):
            mit_zahl += 1
    return mit_zahl


class TestNachDreiTagenStehtDieRateNoch:
    """**Die Aussage des Befundes.**"""

    @pytest.mark.asyncio
    async def test_jede_kerze_traegt_eine_rate(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)

        mit_rate = await _laufen_lassen(rig, uhr, stunden=72)

        assert mit_rate == 288

    @pytest.mark.asyncio
    async def test_ohne_das_nachladen_ist_nach_einem_tag_schluss(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Die Gegenprobe. Ohne sie koennte der Test darueber gruen sein, weil
        die Frist gar nicht greift - dann waere nichts gezeigt."""
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)
        rig.trader._funding_auffrischen = lambda: None  # type: ignore[method-assign]
        rig.trader._load_history()

        mit_rate = await _laufen_lassen(rig, uhr, stunden=72)

        # 97 und nicht 96: Die Kerze genau auf der Frist zaehlt noch mit.
        assert mit_rate == 97
        assert mit_rate / 288 < 0.4

    @pytest.mark.asyncio
    async def test_die_regel_handelt_auch_am_dritten_tag(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Nicht die Spalte ist der Zweck, sondern der Einstieg.

        Eine Spalte voller Zahlen, auf die niemand handelt, waere kein
        Fortschritt - deshalb steht hier der Zaehler aus dem Orderbuch.
        """
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)

        await _laufen_lassen(rig, uhr, stunden=72)

        assert len(rig.entry_orders) == 288


class TestDieRatenLandenAufDerPlatte:
    @pytest.mark.asyncio
    async def test_der_speicher_waechst_mit(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Nicht nur ``_raten`` im Arbeitsspeicher.

        Sonst haetten Livelauf und ``cli funding`` zwei verschiedene
        Wahrheiten, und die naechste Zulassung rechnete auf der aelteren.
        """
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)
        vorher = len(rig.trader.funding.read("BTCUSDT"))

        await _laufen_lassen(rig, uhr, stunden=72)

        nachher = len(rig.trader.funding.read("BTCUSDT"))
        assert nachher - vorher == 8  # 72 Stunden, alle acht eine Zahlung
        assert len(rig.trader._raten) == nachher

    @pytest.mark.asyncio
    async def test_die_werte_sind_die_der_boerse(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Festgestellte Raten, keine erfundenen."""
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)

        await _laufen_lassen(rig, uhr, stunden=72)

        werte = rig.trader.funding.read("BTCUSDT")[SPALTE]
        assert len(werte) > 0
        assert list(werte) == pytest.approx([float(RATE)] * len(werte))

    @pytest.mark.asyncio
    async def test_zwischen_speicher_und_fenster_bleibt_kein_loch(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Angesetzt wird am juengsten bekannten Eintrag.

        Ein Fenster "von jetzt minus X" waere bequemer und liesse bei einer
        Pause im Speicher eine Luecke - ueber die ``attach_funding`` spaeter
        stillschweigend hinwegschreibt, weil sie die letzte bekannte Rate
        vorwaerts fortfuehrt. Hier steht der Speicher zwei Tage still, und
        danach muessen alle Zahlungen dazwischen da sein.
        """
        rig, uhr = _rig(
            tmp_path,
            btcusdt,
            risk,
            bybit_settings,
            im_speicher_bis=BEGINN - timedelta(days=2),
        )

        await _laufen_lassen(rig, uhr, stunden=24)

        zeiten = pd.to_datetime(
            rig.trader.funding.read("BTCUSDT")["time"], utc=True
        ).sort_values()
        abstaende = zeiten.diff().dropna().unique()
        assert list(abstaende) == [pd.Timedelta(FUNDING_INTERVAL)]


class TestGefragtWirdMitMass:
    @pytest.mark.asyncio
    async def test_nicht_bei_jeder_kerze(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """288 Kerzen, aber nicht 288 Anfragen.

        Die Rate entsteht dreimal am Tag; auf 15-Minuten-Kerzen waeren 96
        Anfragen taeglich fuer dieselbe Zahl.
        """
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)

        await _laufen_lassen(rig, uhr, stunden=72)

        anfragen = len(rig.trader.market.funding_calls)
        assert anfragen == 8
        assert anfragen < 288 / 10

    @pytest.mark.asyncio
    async def test_eine_noch_frische_rate_wird_nicht_nachgefragt(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Der Speicher ist aktuell - dann gibt es nichts zu holen."""
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)
        vorher = len(rig.trader.market.funding_calls)

        uhr.jetzt = BEGINN + timedelta(hours=1)
        await rig.feed()

        assert len(rig.trader.market.funding_calls) == vorher

    @pytest.mark.asyncio
    async def test_ohne_speicher_wird_die_boerse_nicht_gefragt(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Kein Speicher heisst: Dieser Lauf rechnet nicht mit Funding."""
        rig, uhr = _rig(
            tmp_path, btcusdt, risk, bybit_settings, mit_speicher=False
        )

        # Ohne Speicher gibt es die Spalte nicht, also kann sie hier auch
        # nicht gezaehlt werden - genau das ist die Aussage.
        for _ in range(96):
            uhr.jetzt = rig.next_open + Interval.M15.duration
            await rig.feed()

        assert rig.trader.market.funding_calls == []
        assert SPALTE not in rig.trader._frame.columns


class TestEinNetzfehlerKostetKeineKerze:
    @pytest.mark.asyncio
    async def test_die_kerze_wird_trotzdem_verarbeitet(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Die Entscheidung auf diesem Balken ist mehr wert als die frische
        Rate - und ``_on_candle`` zaehlt jeden Fehler, der nach aussen kommt.
        """
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)
        rig.trader.market = BoerseFaellt(rig.trader.market)

        mit_rate = await _laufen_lassen(rig, uhr, stunden=12)

        assert rig.trader.stats.candle_errors == 0
        assert rig.trader.stats.candles_seen == 48
        # Innerhalb der Frist traegt die alte Rate noch, und sie bleibt da.
        assert mit_rate == 48
        assert not rig.trader._raten.empty

    @pytest.mark.asyncio
    async def test_der_fehlschlag_wird_gemeldet(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)
        rig.trader.market = BoerseFaellt(rig.trader.market)

        with capture_logs() as zeilen:
            # Eine Kerze **hinter** der faelligen Zahlung, nicht genau darauf:
            # Genau auf der Grenze ist das Fenster leer (``cursor >= end``),
            # dann bricht ``backfill_funding`` ab, ohne zu fragen - richtig so,
            # aber hier soll gefragt werden.
            uhr.jetzt = BEGINN + FUNDING_INTERVAL + Interval.M15.duration
            await rig.feed()

        ereignisse = [z["event"] for z in zeilen]
        assert "live.funding_nachladen_fehlgeschlagen" in ereignisse

    @pytest.mark.asyncio
    async def test_eine_kaputte_boerse_wird_nicht_bestuermt(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Der Abstand gilt auch dann, wenn die Anfrage gescheitert ist.

        Sonst haengt an jeder Kerze ein Verbindungsversuch mit Timeout - und
        der Kerzen-Handler wartet darauf.

        Gemessen: vier Versuche auf 48 Kerzen. Nicht zwoelf, wie zuerst
        erwartet - in den ersten acht Stunden ist gar keine Rate faellig, also
        wird auch nicht gefragt. Der Stundentakt beginnt erst, wenn etwas
        aussteht, und das ist die richtige Reihenfolge: Erst die Faelligkeit,
        dann der Abstand.
        """
        rig, uhr = _rig(tmp_path, btcusdt, risk, bybit_settings)
        boerse = BoerseFaellt(rig.trader.market)
        rig.trader.market = boerse

        await _laufen_lassen(rig, uhr, stunden=12)

        assert boerse.versuche == 4
        assert boerse.versuche < 48  # Kerzen


class TestDieWarnungKommtEinmalJeUebergang:
    @pytest.mark.asyncio
    async def test_nicht_bei_jeder_kerze(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Eine Warnung alle 15 Minuten ist so gut wie keine.

        Die Boerse hat hier nichts Neues (sie zahlt nur bis zum Start), also
        veraltet der Speicher im Lauf - genau der Fall, den ``_funding_pruefen``
        beim Start schon konnte und im Lauf nicht.
        """
        rig, uhr = _rig(
            tmp_path, btcusdt, risk, bybit_settings, an_der_boerse_bis=BEGINN
        )

        with capture_logs() as zeilen:
            await _laufen_lassen(rig, uhr, stunden=72)

        veraltet = [z for z in zeilen if z["event"] == "live.funding_veraltet"]
        assert len(veraltet) == 1

    @pytest.mark.asyncio
    async def test_und_erst_jenseits_der_frist(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Die Gegenprobe: Innerhalb der Frist ist nichts zu melden."""
        rig, uhr = _rig(
            tmp_path, btcusdt, risk, bybit_settings, an_der_boerse_bis=BEGINN
        )

        with capture_logs() as zeilen:
            await _laufen_lassen(rig, uhr, stunden=12)

        assert [z for z in zeilen if z["event"] == "live.funding_veraltet"] == []

    @pytest.mark.asyncio
    async def test_nach_frischen_raten_wird_wieder_gewarnt(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Die Sperre gilt dem Uebergang, nicht dem Lauf.

        Erst eine Durststrecke, dann zahlt die Boerse wieder, dann die
        naechste - die zweite muss sich wieder melden, sonst waere die erste
        Warnung eine Einmalnachricht fuer die ganze Laufzeit.
        """
        rig, uhr = _rig(
            tmp_path, btcusdt, risk, bybit_settings, an_der_boerse_bis=BEGINN
        )

        with capture_logs() as erste:
            await _laufen_lassen(rig, uhr, stunden=36)
        assert len([z for z in erste if z["event"] == "live.funding_veraltet"]) == 1

        # Die Boerse zahlt nach: alles bis zum jetzigen Stand.
        rig.trader.market.funding = _raten(
            BEGINN - timedelta(days=10), uhr.jetzt
        )
        with capture_logs() as zweite:
            await _laufen_lassen(rig, uhr, stunden=48)

        assert [z["event"] for z in zweite].count("live.funding_nachgeladen") >= 1
        assert len([z for z in zweite if z["event"] == "live.funding_veraltet"]) == 1


class TestDieBeidenGrenzen:
    def test_der_abstand_liegt_zwischen_einer_kerze_und_einer_periode(self) -> None:
        """Keine Wiederholung der Definition, sondern ihre zwei Grenzen.

        **Mehr als ein Kerzenabstand**, sonst haengt an jeder Kerze eine
        Anfrage. **Nicht mehr als eine Zahlungsperiode**, sonst kann eine
        faellige Rate eine ganze Periode lang unbemerkt bleiben - und bis zur
        Frist bleiben dann zu wenige Versuche.
        """
        assert Interval.M15.duration < NACHLADEABSTAND
        assert NACHLADEABSTAND <= FUNDING_INTERVAL
        assert FUNDINGFRIST / NACHLADEABSTAND >= 24

    def test_die_seitenzahl_ist_eine_harte_grenze(self) -> None:
        """Eine Seite deckt ``8h * 200`` ab - ueber zwei Monate.

        Im Kerzen-Handler zaehlt Aktualitaet, nicht Vollstaendigkeit; die
        Historie holt ``cli funding`` mit seinen 200 Seiten.
        """
        from data.funding import PAGE_SIZE

        assert NACHLADESEITEN >= 1
        assert NACHLADESEITEN <= 10
        assert timedelta(days=60) < FUNDING_INTERVAL * PAGE_SIZE
