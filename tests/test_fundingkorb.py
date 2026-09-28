"""Ein Bein ohne Funding-Raten handelt nicht - Befund 359.

``cli funding`` lud genau **ein** Symbol, ``settings.bybit.symbol``, und kein
Schalter aenderte das - dieselbe Luecke wie beim Backfill in Befund 357, einen
Befehl weiter. Die Folge ist leiser:

``attach_funding`` schreibt einem Bein ohne Raten ueberall ``NaN``, die
Funding-Indikatoren geben dort ``NaN`` zurueck, und die Regel handelt auf diesem
Bein **nicht**. Gemessen mit ``Carry-Beteiligung`` aus Generation 5 auf
BTC + ETH und Raten nur fuer BTC:

    BTCUSD_BITSTAMP   3301 Kerzen mit Rate   ->  54 Trades
    ETHUSD_BITSTAMP   3301 Kerzen NaN        ->   0 Trades
    gesamt                                       54

**Der Lauf nennt trotzdem zwei Maerkte.** Ein Ergebnis, das nach dem Korb
aussieht und eines ist, was Befund 264/318 als etwas anderes gemessen hat: 9 von
11 auf dem Korb, 8 von 11 auf ein Bein gekuerzt.

Das ist schlimmer versteckt als fehlende Kerzen. Ohne Kerzen bricht der Lauf ab
oder nennt einen Markt weniger; ohne Raten laeuft er durch und sieht vollstaendig
aus.

Zwei Messungen, die dazugehoeren
--------------------------------
Der Bestand handelt auch **ohne** Raten weiter (160 Trades auf beiden Beinen) -
er liest das Funding nicht. Die Luecke trifft also nicht jede Regel, sondern
genau die, deren Idee am Funding haengt. Und der erste Anlauf dieser Messung hat
nichts gezeigt, weil die synthetische Rate genau auf der Schwelle der Regel lag
(0,0001 = 0,01 %, die Bedingung lautet ``< 0,01``): 0 Trades auf beiden Beinen.
Erst eine Rate darunter trennt die Faelle.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cli import ZULASSUNGSKORB

#: Eine Rate **unter** der Schwelle der Carry-Regel (0,01 %).
#:
#: Der Wert entscheidet, ob der Test etwas zeigt: Auf der Schwelle handelt auch
#: das Bein mit Raten nicht, und dann sehen beide Beine gleich aus.
RATE = Decimal("0.00005")

#: Wie viele Raten geschrieben werden - acht Stunden Abstand, gut neun Jahre.
PERIODEN = 9500


def _carry_regel():
    from research.seeds import GENERATIONS

    for eintrag in GENERATIONS[5]:
        genome = eintrag() if callable(eintrag) else eintrag
        if "arry" in genome.name:
            return genome
    pytest.skip("keine Carry-Regel in Generation 5")


@pytest.fixture(scope="module")
def einseitig(tmp_path_factory):
    """Ein Korb, in dem nur BTC Funding-Raten hat - und was er handelt."""
    import cli
    from backtest.engine import BacktestConfig
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )
    from core.models import Interval
    from data.funding import FundingRate, FundingStore, attach_funding
    from data.store import CandleStore
    from strategy.compiler import compile_genome

    wurzel = tmp_path_factory.mktemp("store")
    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    for symbol in symbole:
        quelle = Path("data_store") / "candles" / symbol / "D"
        if not quelle.exists():
            pytest.skip("keine Tageskerzen im Speicher")
        ziel = wurzel / "candles" / symbol / "D"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(quelle, ziel)

    # Nur fuer BTCUSDT Raten - genau das, was 'cli funding' ohne '-m' liefert.
    speicher = FundingStore(wurzel)
    beginn = datetime(2017, 8, 16, tzinfo=UTC)
    speicher.write(
        "BTCUSDT",
        [
            FundingRate(
                symbol="BTCUSDT",
                funding_time=beginn + timedelta(hours=8 * i),
                funding_rate=RATE,
            )
            for i in range(PERIODEN)
        ],
    )

    store = CandleStore(wurzel)
    frames = common_range({x: store.read(x, Interval("D")) for x in symbole})
    je_markt = {m: speicher.read(cli._bybit_kontrakt(m)) for m in symbole}
    mit_raten = {m: attach_funding(frames[m], je_markt[m]) for m in symbole}

    from core.config import get_settings

    configs = {
        m: BacktestConfig(
            instrument=cli._fallback_instrument(cli._bybit_kontrakt(m)),
            risk=get_settings().risk,
            initial_equity=Decimal("500"),
            enforce_risk_limits=True,
        )
        for m in symbole
    }

    def fahre(genome):
        bericht = run_portfolio_walkforward(
            mit_raten, lambda: compile_genome(genome), configs
        )
        return {
            m: sum(
                1
                for t in bericht.all_trades
                if t.symbol in (m, cli._bybit_kontrakt(m))
            )
            for m in symbole
        }

    return fahre, mit_raten, symbole


@pytest.mark.langsam
class TestDasBeinOhneRatenHandeltNicht:
    """**Die Messung**, und sie ist der ganze Fund."""

    def test_die_spalte_ist_auf_einem_bein_leer(self, einseitig) -> None:
        _, mit_raten, symbole = einseitig
        btc, eth = (mit_raten[s]["funding_rate"] for s in symbole)

        assert btc.notna().all(), "BTC sollte durchgehend Raten haben"
        assert eth.isna().all(), "ETH sollte gar keine haben"

    def test_und_die_carry_regel_handelt_nur_dort(self, einseitig) -> None:
        fahre, _, symbole = einseitig

        trades = fahre(_carry_regel())

        assert trades[symbole[0]] > 0, "das Bein mit Raten muss handeln"
        assert trades[symbole[1]] == 0, "das Bein ohne Raten darf nicht handeln"

    def test_der_bestand_merkt_davon_nichts(self, einseitig) -> None:
        """Die Abgrenzung: Der Bestand liest das Funding nicht, also handelt er
        auf beiden Beinen weiter. Die Luecke trifft die Regeln, deren Idee am
        Funding haengt - nicht jede."""
        from research.seeds import spitzenkandidat

        fahre, _, symbole = einseitig

        trades = fahre(spitzenkandidat())

        assert all(trades[s] > 0 for s in symbole)


class TestDieLadebefehleKennenDenKorb:
    def test_funding_nimmt_mehrere_maerkte(self) -> None:
        import click
        import typer

        from cli import app

        gruppe = typer.main.get_command(app)
        befehl = gruppe.get_command(click.Context(gruppe), "funding")
        namen = {name for p in befehl.params for name in p.opts}

        assert "-m" in namen or "--maerkte" in namen

    def test_die_warnung_steht_an_einer_stelle(self) -> None:
        """Zwei Meldungen mit demselben Inhalt waeren die naechste Stelle, an
        der zwei Fassungen auseinanderlaufen (Befund 168)."""
        import ast

        quelle = Path("cli.py").read_text(encoding="utf-8")
        baum = ast.parse(quelle)
        rufer = [
            k.name
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and "_korbwarnung(" in ast.unparse(k)
        ]

        assert {"backfill", "funding"} <= set(rufer)

    def test_und_nennt_den_vollstaendigen_befehl(self) -> None:
        from cli import _korbwarnung, console

        with console.capture() as aufnahme:
            _korbwarnung(["BTCUSDT"], "funding", "--von 2020-03-30")
        text = " ".join(aufnahme.get().split())

        assert "ETHUSDT" in text
        assert f"funding -m {','.join(ZULASSUNGSKORB)} --von 2020-03-30" in text

    def test_auf_dem_vollen_korb_schweigt_sie(self) -> None:
        from cli import _korbwarnung, console

        with console.capture() as aufnahme:
            _korbwarnung(list(ZULASSUNGSKORB), "funding")

        assert aufnahme.get().strip() == ""


class TestDerWettbewerbMeldetDieUngleicheAbdeckung:
    """Die Zahlen standen schon da - als Inventur in grauer Schrift."""

    @staticmethod
    def _quelle() -> str:
        import ast

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "wettbewerb":
                return ast.unparse(knoten)
        raise AssertionError("'wettbewerb' steht nicht mehr in cli.py")

    def test_ungleiche_abdeckung_wird_gewarnt(self) -> None:
        quelle = self._quelle()

        assert "Ungleiche Funding-Abdeckung" in quelle

    def test_und_die_warnung_nennt_die_gemessene_folge(self) -> None:
        quelle = self._quelle()
        stelle = quelle.index("Ungleiche Funding-Abdeckung")
        meldung = quelle[stelle : stelle + 600]

        assert "54 Trades gegen 0" in meldung
        assert "handelt auf einem " in meldung

    def test_bei_gleicher_abdeckung_bleibt_es_bei_der_inventur(self) -> None:
        """Eine Warnung, die immer kommt, ist Grundrauschen."""
        quelle = self._quelle()
        stelle = quelle.index("ohne = [m for m, n in geladen.items() if not n]")

        assert "if ohne and len(geladen) > 1" in quelle[stelle : stelle + 200]


class TestDasRegisterHaeltDenFund:
    def test_er_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 359)

        assert "54" in eintrag.ergebnis
        assert "NaN" in eintrag.ergebnis

    def test_die_nutzerzeile_nennt_beide_maerkte(self) -> None:
        from research.stand import BEIM_NUTZER

        zeilen = [b for b, _ in BEIM_NUTZER if " funding " in f" {b} "]

        assert zeilen, "keine Funding-Zeile unter den Befehlen"
        for zeile in zeilen:
            for symbol in ZULASSUNGSKORB:
                assert symbol in zeile, zeile
