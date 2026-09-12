"""Die geladenen Raten gingen an die Kerzen, nie in die Rechnung.

**Befund 265.** Der Bericht sagt dem Nutzer: *"'cli funding --von 2020-03-30'
laedt die echten Funding-Raten. Bisher rechnet jede Zahl mit dem Vorgabewert,
und der ist der groesste Kostenblock des Systems - das 8,9-fache der
Handelsgebuehren."*

Zwei Dinge standen dem im Weg, und beide lautlos.

**Erstens der Schluessel.** ``cli funding`` schreibt unter
``settings.bybit.symbol`` (``BTCUSDT``); ``cli wettbewerb`` las unter
``handelssymbol`` (``BTCUSD_BITSTAMP``). Gelesen wurde eine Datei, die niemand
schreibt - null Zeilen, und ``attach_funding`` setzt daraufhin ueberall NaN.
``cli research`` las an derselben Stelle richtig.

**Zweitens die Rechnung.** ``attach_funding`` schreibt die Raten an die Kerzen;
dort sind sie ein **Indikator**. Was der Backtest *berechnet*, kommt aus
``BacktestConfig.funding`` - und in der ganzen Anwendung gab es keine einzige
Stelle, die ``rates=`` gesetzt hat. ``rates=`` kam genau einmal vor: in
``tests/test_costs.py``.

Wer also ``cli funding`` laufen liess, aenderte, was die Strategie **sieht**,
nicht, was sie **zahlt**.

Was hier gehalten wird
----------------------
Beide Enden, und die Strecke dazwischen am Stueck: ueber den Parquet-Speicher
hinein, als Kostenmodell heraus, und die Zahlung am Ende hoeher als der
Vorgabewert.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import FundingRate, Side
from data.funding import FundingStore, attach_funding, schedule_from_frame

ECHT = Decimal("0.00075")
VORGABE = Decimal("0.0001")
ZEITEN = [datetime(2024, 1, 1, h, tzinfo=UTC) for h in (0, 8, 16)]


def _quelle(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == name
    )
    return ast.unparse(knoten)


@pytest.fixture
def gespeichert(tmp_path: Path):
    """Raten, wie ``cli funding`` sie ablegt - ueber Parquet und zurueck."""
    store = FundingStore(tmp_path)
    store.write(
        "BTCUSDT",
        [
            FundingRate(symbol="BTCUSDT", funding_time=t, funding_rate=ECHT)
            for t in ZEITEN
        ],
    )
    return store


class TestDerSchluesselIstDerKontrakt:
    def test_geschrieben_wird_unter_dem_kontrakt(self, gespeichert) -> None:
        assert len(gespeichert.read("BTCUSDT")) == 3

    def test_unter_dem_kursdatensymbol_steht_nichts(self, gespeichert) -> None:
        """Der Fehler, der im Wettbewerb stand - und er faellt nicht auf,
        weil ein leerer Rahmen kein Fehler ist."""
        assert gespeichert.read("BTCUSD_BITSTAMP").empty

    def test_der_wettbewerb_liest_nie_mit_einem_kerzenschluessel(self) -> None:
        """Die Wache steht auf der Anforderung, nicht auf ihrer Schreibweise:
        **jeder** Zugriff auf den Funding-Speicher geht durch die Umrechnung.

        Auf den Wortlaut zu ankern hat in dieser Reihe schon dreimal gerissen
        (244, 261, 263); hier kaeme dazu, dass der Fehler gerade darin bestand,
        eine Variable an die falsche Stelle zu schreiben - und Variablennamen
        aendern sich."""
        zugriffe = [
            k
            for k in ast.walk(ast.parse(_quelle("wettbewerb")))
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Attribute)
            and k.func.attr == "read"
            and "funding" in ast.unparse(k.func.value)
        ]

        assert zugriffe, "Kein Zugriff auf den Funding-Speicher gefunden."
        for zugriff in zugriffe:
            argument = zugriff.args[0]
            assert (
                isinstance(argument, ast.Call)
                and getattr(argument.func, "id", "") == "_bybit_kontrakt"
            ), f"Ungerechneter Schluessel: {ast.unparse(zugriff)}"

    def test_und_je_bein_im_korb(self) -> None:
        """Ein Bein mit den Raten des anderen zu belasten waere schlimmer als
        der Vorgabewert - also je Markt gelesen und je Markt gerechnet."""
        quelle = _quelle("wettbewerb")

        assert "_bybit_kontrakt(markt)" in quelle
        assert "schedule_from_frame(funding_je_markt[markt])" in quelle


class TestDieRatenGehenInDieRechnung:
    def test_der_zeitplan_traegt_sie(self, gespeichert) -> None:
        plan = schedule_from_frame(gespeichert.read("BTCUSDT"))

        assert len(plan.rates) == 3

    def test_der_schluessel_trifft_was_die_engine_sucht(self, gespeichert) -> None:
        """Die Engine fragt mit schlichten ``datetime`` auf die volle Stunde.
        Ein Schluessel, der nicht trifft, faellt still auf den Vorgabewert -
        und genau das waere hier nicht zu bemerken."""
        plan = schedule_from_frame(gespeichert.read("BTCUSDT"))

        assert plan.rate_at(datetime(2024, 1, 1, 8, tzinfo=UTC)) == ECHT

    def test_eine_luecke_behaelt_den_vorgabewert(self, gespeichert) -> None:
        """Eine fehlende Rate ist nicht null."""
        plan = schedule_from_frame(gespeichert.read("BTCUSDT"))

        assert plan.rate_at(datetime(2024, 1, 2, 8, tzinfo=UTC)) == plan.default_rate

    def test_und_es_wird_wirklich_berechnet(self, gespeichert) -> None:
        """Der Punkt des ganzen Befunds."""
        plan = schedule_from_frame(gespeichert.read("BTCUSDT"))
        leer = schedule_from_frame(gespeichert.read("BTCUSD_BITSTAMP"))
        spanne = (
            datetime(2023, 12, 31, 23, tzinfo=UTC),
            datetime(2024, 1, 1, 20, tzinfo=UTC),
        )

        mit = plan.payments_between(*spanne, position_value=Decimal("1000"), side=Side.BUY)
        ohne = leer.payments_between(*spanne, position_value=Decimal("1000"), side=Side.BUY)

        assert mit > ohne
        assert mit / ohne == pytest.approx(float(ECHT / VORGABE), rel=1e-6)

    def test_ein_leerer_rahmen_gibt_den_vorgabewert(self, tmp_path: Path) -> None:
        plan = schedule_from_frame(FundingStore(tmp_path).read("gibtsnicht"))

        assert plan.rates == {}
        assert plan.default_rate == VORGABE


class TestBeideBefehleRechnenDamit:
    def test_der_wettbewerb(self) -> None:
        assert "schedule_from_frame(" in _quelle("wettbewerb")

    def test_die_forschung(self) -> None:
        assert "schedule_from_frame(" in _quelle("research")

    def test_der_wettbewerb_sagt_was_geladen_wurde(self) -> None:
        """Eine stille Ladung ist von einer leeren nicht zu unterscheiden -
        dieselbe Ueberlegung wie bei der Ausschlussliste in Befund 258."""
        quelle = _quelle("wettbewerb")

        assert "Funding-Raten aus dem Speicher" in quelle
        assert "Keine Funding-Raten im Speicher" in quelle

    def test_und_zwar_auch_auf_einem_einzelnen_markt(self) -> None:
        """Die Auskunft haengt nicht am Korb.

        Zuerst stand sie im Zweig fuer mehrere Maerkte - dort, wo die
        Konfigurationen je Bein gebaut werden. Ein Lauf ohne '--maerkte' waere
        damit genau so still geblieben wie vorher, und das ist der Zustand,
        den dieser Befund behebt."""
        zweige = [
            k
            for k in ast.walk(ast.parse(_quelle("wettbewerb")))
            if isinstance(k, ast.If) and "symbole" in ast.unparse(k.test)
        ]

        assert zweige, "Der Zweig fuer mehrere Maerkte ist nicht zu finden."
        for zweig in zweige:
            rumpf = "\n".join(ast.unparse(x) for x in zweig.body)
            assert "Funding-Raten" not in rumpf


class TestDieKerzenBleibenWieSieWaren:
    """``attach_funding`` ist der Indikatorweg und bleibt unveraendert - die
    beiden Wege stehen nebeneinander, nicht einer statt des anderen."""

    def test_die_rate_steht_weiter_an_der_kerze(self, gespeichert) -> None:
        import pandas as pd

        kerzen = pd.DataFrame(
            {
                "open_time": pd.to_datetime(
                    [datetime(2024, 1, 1, 12, tzinfo=UTC)], utc=True
                ),
                "close": [42000.0],
            }
        )

        ergebnis = attach_funding(kerzen, gespeichert.read("BTCUSDT"))

        assert "funding_rate" in ergebnis
        assert ergebnis["funding_rate"].iloc[0] == pytest.approx(float(ECHT))


class TestDerNachweisSagtObEsGalt:
    def test_echte_raten_stehen_im_text(self) -> None:
        from research.admission import Zulassungsbedingungen

        text = Zulassungsbedingungen(markt="spot", gesamt=11, funding_raten=6540).als_text()

        assert "6540 echte Funding-Raten" in text

    def test_ohne_sie_steht_nichts_davon_da(self) -> None:
        """Alle bisherigen Eintraege stehen auf null - durchgehend mit dem
        Vorgabewert gerechnet, und das ist richtig so."""
        from research.admission import Zulassungsbedingungen

        assert "Funding-Raten" not in Zulassungsbedingungen(
            markt="spot", gesamt=11
        ).als_text()

    def test_der_lauf_schreibt_die_zahl_mit(self) -> None:
        assert "funding_raten=" in _quelle("_bedingungen")
