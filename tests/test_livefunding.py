"""Der Livepuffer bekommt seine Funding-Spalte - Befund 361.

Die offene Folge aus Befund 360, im Register so festgehalten:

    Offen bleibt die Folge: Der Livebetrieb hat weiter keine Funding-Spalte,
    also kann eine Carry-Regel dort nicht handeln - der Abgleich sagt es jetzt,
    behoben ist es nicht.

Gemessen auf derselben Reihe von 500 Balken, mit der Carry-Regel aus
Generation 5 (``Carry-Beteiligung``):

    Backtest-Signale:        470
    Betrieb VOR Befund 361:    0
    Betrieb NACH Befund 361: 470

Null gegen 470 ist der ganze Befund. Eine Regel, die die Zulassung bestanden
hat, haette live keinen einzigen Einstieg genommen.

Worauf es beim Bauen ankam
--------------------------
Der Vorlauf allein genuegt **nicht**. ``_append`` haengt jede neue Kerze als
eigene Zeile an, und ``concat`` gibt einer Zeile ohne die Spalte stillschweigend
NaN. Der letzte Balken ist aber genau der, den die Regel auswertet - die Spalte
nur beim Laden zu fuellen haette also nichts geaendert, bloss eine Spalte voller
Zahlen ueber einem NaN erzeugt. Dieser Test haelt beide Stellen fest.

Und die Frist: ``attach_funding`` schreibt die zuletzt bekannte Rate vorwaerts
fort. Im Backtest sind das hoechstens acht Stunden, im Betrieb notfalls Wochen,
wenn niemand ``cli funding`` laufen laesst. Lieber NaN als eine Rate von vor
drei Wochen - auf NaN handelt die Strategie nicht, auf eine veraltete Zahl
haette sie gehandelt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from core.models import FundingRate
from data.funding import SPALTE
from execution.live import FUNDINGFRIST
from tests.test_live import build_rig

#: Eine Rate unter der Schwelle der Carry-Regel (0,01 %) - derselbe Wert wie in
#: ``test_abgleichluecke.py``, aus demselben Grund (Befund 359).
RATE = Decimal("0.00005")

#: Der Verlauf im Rig beginnt hier; die Raten muessen davor einsetzen.
BEGINN = datetime(2026, 1, 1, tzinfo=UTC)


def _raten(*, anzahl: int = 200, ab: datetime | None = None) -> list[FundingRate]:
    beginn = (ab or BEGINN) - timedelta(days=2)
    return [
        FundingRate(
            symbol="BTCUSDT",
            funding_time=beginn + timedelta(hours=8 * i),
            funding_rate=RATE,
        )
        for i in range(anzahl)
    ]


class TestDerVorlaufTraegtDieSpalte:
    def test_mit_speicher_steht_sie_im_puffer(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )

        assert SPALTE in rig.trader._frame.columns

    def test_und_traegt_echte_zahlen(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Eine Spalte voller NaN waere keine Eingabe, sondern ihre Attrappe."""
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )

        werte = rig.trader._frame[SPALTE]

        assert werte.notna().all()
        assert float(werte.iloc[-1]) == pytest.approx(float(RATE))

    def test_ohne_speicher_bleibt_es_wie_vorher(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Keine Spalte, nicht eine Spalte voller NaN.

        Der Unterschied ist nicht kosmetisch: Eine fehlende Spalte ist eine
        fehlende Eingabe, eine Spalte voller NaN waere eine gelieferte Eingabe
        ohne Inhalt. Der Abgleich muss beides auseinanderhalten koennen.
        """
        rig = build_rig(tmp_path, btcusdt, risk, bybit_settings)

        assert SPALTE not in rig.trader._frame.columns

    def test_speicher_ohne_raten_gibt_nan(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        rig = build_rig(tmp_path, btcusdt, risk, bybit_settings, funding_raten=[])

        assert SPALTE in rig.trader._frame.columns
        assert rig.trader._frame[SPALTE].isna().all()


class TestJedeNeueKerzeBekommtIhreRate:
    """**Die Stelle, auf die es ankommt.**"""

    @pytest.mark.asyncio
    async def test_der_letzte_balken_ist_keine_luecke(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Ohne diesen Schritt haette die Regel weiter nie gehandelt: Der
        letzte Balken ist der, den sie auswertet."""
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )

        await rig.feed(close=Decimal("100500"))

        letzte = rig.trader._frame[SPALTE].iloc[-1]
        assert not pd.isna(letzte)
        assert float(letzte) == pytest.approx(float(RATE))

    @pytest.mark.asyncio
    async def test_auch_nach_vielen_kerzen(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )

        for _ in range(5):
            await rig.feed()

        assert rig.trader._frame[SPALTE].notna().all()

    @pytest.mark.asyncio
    async def test_ohne_speicher_kommt_auch_keine_spalte_dazu(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        rig = build_rig(tmp_path, btcusdt, risk, bybit_settings)

        await rig.feed()

        assert SPALTE not in rig.trader._frame.columns


class TestEineVeralteteRateIstKeineRate:
    @pytest.mark.asyncio
    async def test_jenseits_der_frist_steht_nan(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Die Raten enden lange vor dem Verlauf - fortgeschrieben wird nicht
        beliebig weit."""
        alt = BEGINN - FUNDINGFRIST - timedelta(days=30)
        rig = build_rig(
            tmp_path,
            btcusdt,
            risk,
            bybit_settings,
            funding_raten=_raten(anzahl=3, ab=alt),
        )

        assert rig.trader._frame[SPALTE].isna().all()

    @pytest.mark.asyncio
    async def test_innerhalb_der_frist_steht_die_zahl(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Die Gegenprobe - sonst koennte die Frist alles verwerfen und der
        Test darueber waere trotzdem gruen."""
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )

        assert rig.trader._frame[SPALTE].notna().all()

    def test_die_frist_liegt_zwischen_einer_periode_und_einer_woche(self) -> None:
        """Keine Wiederholung der Definition, sondern ihre zwei Grenzen.

        **Mehr als eine Periode**, sonst blendet eine einzige verpasste
        Zahlung die Regel aus - Bybit zahlt alle acht Stunden, und ein Abruf
        kurz davor waere sofort "veraltet". **Deutlich unter einer Woche**,
        sonst faengt die Frist den Fall nicht mehr, um den es geht: einen
        Speicher, in den seit Tagen nichts geschrieben wurde.
        """
        from data.funding import FUNDING_INTERVAL

        assert FUNDINGFRIST > FUNDING_INTERVAL
        assert timedelta(days=7) > FUNDINGFRIST
        assert FUNDINGFRIST / FUNDING_INTERVAL == 3

    @pytest.mark.asyncio
    async def test_die_grenze_liegt_an_der_kerzenzeit_nicht_an_heute(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Zwei verschiedene Fragen, bewusst getrennt.

        Die Frist gilt je Kerze: Ein Backtest ueber 2017 darf die Raten von
        2017 benutzen, auch wenn sie heute Jahre alt sind. Nur **ob gewarnt
        wird**, haengt am Kalender - der Vorlauf im Rig ist von 2026 und damit
        selbst schon lange her.
        """
        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )
        letzte_kerze = rig.trader._frame["open_time"].iloc[-1]

        assert pd.Timestamp(letzte_kerze) < pd.Timestamp(datetime.now(UTC))
        assert rig.trader._frame[SPALTE].notna().all(), (
            "die Raten liegen bei den Kerzen, nicht bei heute"
        )


class TestDerStartSagtEsWennDieRatenFehlen:
    """Sonst laeuft der Roboter still und handelt nie - und das sieht auf dem
    Bildschirm aus wie "kein Signal" statt wie "keine Eingabe"."""

    @staticmethod
    def _carry_rig(tmp_path, btcusdt, risk, bybit_settings, **kwargs):
        from strategy.compiler import compile_genome
        from tests.test_abgleichluecke import _carry_regel

        rig = build_rig(tmp_path, btcusdt, risk, bybit_settings, **kwargs)
        rig.trader.strategy = compile_genome(_carry_regel())
        rig.trader._load_history()
        return rig

    def test_ohne_speicher_wird_gewarnt(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        rig = self._carry_rig(tmp_path, btcusdt, risk, bybit_settings)

        warnungen = [e for e in self._ereignisse(rig) if "Funding-Rate" in e]

        assert warnungen, "eine Carry-Regel ohne Raten muss beim Start auffallen"

    def test_die_warnung_nennt_den_befehl(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Eine Warnung ohne Abhilfe schickt den Leser auf die Suche."""
        rig = self._carry_rig(tmp_path, btcusdt, risk, bybit_settings)

        assert any("cli funding" in e for e in self._ereignisse(rig))

    def test_veraltete_raten_werden_auch_genannt(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Der Vorlauf im Rig ist von 2026 - die Raten dazu sind heute aelter
        als die Frist, und das ist der haeufigere Fall als "gar keine Raten"."""
        rig = self._carry_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )

        assert any("alt" in e for e in self._ereignisse(rig))

    def test_eine_regel_ohne_funding_wird_nicht_behelligt(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Eine Warnung, die bei jedem Start steht, liest nach der dritten
        Woche niemand mehr."""
        rig = build_rig(tmp_path, btcusdt, risk, bybit_settings)
        rig.trader._load_history()

        assert not [e for e in self._ereignisse(rig) if "Funding-Rate" in e]

    def test_eine_handgeschriebene_strategie_behauptet_nichts(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Ohne Genom ist die Frage nicht beantwortbar. Dann wird nichts
        behauptet - eine Warnung ohne Beleg waere so wenig wert wie ihr
        Ausbleiben.
        """
        rig = build_rig(tmp_path, btcusdt, risk, bybit_settings)

        assert not hasattr(rig.trader.strategy, "genome")
        assert rig.trader._liest_funding() is False

    @staticmethod
    def _ereignisse(rig) -> list[str]:
        from web.journal import read_view

        blick = read_view(rig.state_dir)
        return [str(e.get("message", "")) for e in blick.events]


class TestDieCarryRegelHandeltJetztAuchImBetrieb:
    """Der Fund selbst, gemessen auf der Reihe aus ``test_abgleichluecke``."""

    @pytest.mark.langsam
    def test_null_gegen_vierhundertsiebzig(self) -> None:
        from backtest.replay import NICHTS, entscheidungen_livebetrieb
        from strategy.compiler import compile_genome
        from tests.test_abgleichluecke import _carry_regel, _mit_funding

        genome = _carry_regel()
        frame = _mit_funding(500)

        def bauen():
            return compile_genome(genome)

        def signale(entscheidungen) -> int:
            return sum(1 for e in entscheidungen if e.signal != NICHTS.signal)

        nachher = signale(entscheidungen_livebetrieb(frame, bauen, buffer_bars=200))
        vorher = signale(
            entscheidungen_livebetrieb(
                frame.drop(columns=[SPALTE]), bauen, buffer_bars=200
            )
        )

        assert vorher == 0, "ohne Spalte handelt die Regel nie - Befund 360"
        assert nachher == 470, "mit Spalte handelt sie wie der Backtest"


class TestDerBefehlReichtDenSpeicherDurch:
    """Alles davor waere umsonst, wenn ``cli trade`` ihn nicht uebergibt."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "trade":
                return ast.unparse(knoten)
        raise AssertionError("'trade' steht nicht mehr in cli.py")

    def test_ein_funding_speicher_wird_gebaut(self) -> None:
        assert "FundingStore(settings.paths.data_store)" in self._quelle()

    def test_und_dem_roboter_uebergeben(self) -> None:
        assert "funding=fundingspeicher" in self._quelle()


class TestDerAbgleichStelltDenNeuenPufferNach:
    """Die Kuerzung aus Befund 360 waere jetzt dieselbe Luege mit umgekehrtem
    Vorzeichen: Der Vergleich wuerde eine Abweichung melden, die es nicht mehr
    gibt, und vor Carry-Regeln warnen, die live handeln.
    """

    def test_die_funding_spalte_bleibt_stehen(self) -> None:
        from backtest.replay import _wie_der_puffer
        from tests.test_abgleichluecke import _mit_funding

        gekuerzt = _wie_der_puffer(_mit_funding(60))

        assert SPALTE in gekuerzt.columns

    def test_fremde_spalten_fallen_weiter_weg(self) -> None:
        from backtest.replay import _wie_der_puffer
        from tests.test_abgleichluecke import _mit_funding

        frame = _mit_funding(60)
        frame["etwas_erfundenes"] = 1.0

        gekuerzt = _wie_der_puffer(frame)

        assert "etwas_erfundenes" not in gekuerzt.columns

    def test_der_puffer_des_betriebs_hat_genau_diese_spalten(
        self, tmp_path, btcusdt, risk, bybit_settings
    ) -> None:
        """Die Probe, die beide Seiten zusammenhaelt: gemessen am echten
        Puffer, nicht an zwei Listen, die zufaellig uebereinstimmen."""
        from backtest.replay import _wie_der_puffer
        from tests.test_abgleichluecke import _mit_funding

        rig = build_rig(
            tmp_path, btcusdt, risk, bybit_settings, funding_raten=_raten()
        )
        gekuerzt = _wie_der_puffer(_mit_funding(60))

        assert set(rig.trader._frame.columns) == set(gekuerzt.columns)


class TestDasRegisterHaeltDenFund:
    def test_er_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 361)

        assert "470" in eintrag.ergebnis

    def test_die_offene_folge_aus_360_ist_abgeraeumt(self) -> None:
        """Sie stand dort als offene Folge; was offen bleibt, ist etwas
        anderes - die laufende Rate von der Boerse."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 361)

        assert "360" in eintrag.ergebnis


def test_die_spalte_steht_an_einer_stelle() -> None:
    """Drei Zeichenketten an drei Orten waren der Riss, durch den Befund 360
    gefallen ist."""
    from strategy import indicators

    frame = pd.DataFrame({SPALTE: [0.0001, 0.0002]})
    reihe = indicators._funding_column(frame)

    assert not reihe.isna().any()
    assert np.isnan(indicators._funding_column(pd.DataFrame({"andere": [1.0]}))).all()
