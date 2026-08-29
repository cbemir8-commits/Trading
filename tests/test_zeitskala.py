"""Tests fuer ``research.zeitskala`` - Befund 143."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from core.models import Trade
from research.zeitskala import STUFEN, Skalenleiter, Skalenstufe, nach_kalender


def _trade(zeit: datetime, pnl: float) -> Trade:
    return Trade(
        trade_id=f"t{zeit.isoformat()}", symbol="BTCUSDT", side="Buy",
        strategy_id="x", entry_time=zeit, entry_price=Decimal("100"),
        exit_time=zeit, exit_price=Decimal("101"), qty=Decimal("1"),
        gross_pnl=Decimal(str(pnl)), fees=Decimal("0"), funding=Decimal("0"),
        stop_loss=Decimal("90"), exit_reason="signal_exit",
    )


def _stufe(name: str, *, roh: int = 100, effektiv: int = 80,
           bloecke: int = 20, icc: float = 0.2) -> Skalenstufe:
    return Skalenstufe(name=name, bloecke=bloecke, roh=roh,
                       effektiv=effektiv, icc=icc)


class TestNachKalender:
    def test_buendelt_nach_dem_ausstieg(self) -> None:
        trades = [
            _trade(datetime(2024, 1, 15, tzinfo=UTC), 1.0),
            _trade(datetime(2024, 1, 20, tzinfo=UTC), 2.0),
            _trade(datetime(2024, 5, 3, tzinfo=UTC), 3.0),
        ]
        nach_monat = nach_kalender(trades, lambda z: (z.year, z.month))

        assert nach_monat == [[1.0, 2.0], [3.0]]

    def test_die_bloecke_stehen_in_zeitlicher_reihenfolge(self) -> None:
        trades = [
            _trade(datetime(2024, 9, 1, tzinfo=UTC), 3.0),
            _trade(datetime(2024, 1, 1, tzinfo=UTC), 1.0),
        ]
        assert nach_kalender(trades, lambda z: (z.year, z.month)) == [[1.0], [3.0]]

    def test_alle_trades_kommen_an(self) -> None:
        trades = [_trade(datetime(2024, 1, 1 + i, tzinfo=UTC), i) for i in range(9)]
        for _, schluessel in STUFEN:
            bloecke = nach_kalender(trades, schluessel)
            assert sum(len(b) for b in bloecke) == len(trades)

    def test_die_leiter_geht_von_fein_nach_grob(self) -> None:
        """Sonst waere ``am_rand`` sinnlos - es fragt nach den Enden."""
        trades = [
            _trade(datetime(2024, 1, 1, tzinfo=UTC) .replace(month=1 + i % 12,
                                                             day=1 + i % 28), i)
            for i in range(60)
        ]
        anzahl = [len(nach_kalender(trades, k)) for _, k in STUFEN]

        assert anzahl == sorted(anzahl, reverse=True), (
            f"feinere Skalen muessen mehr Bloecke geben: {anzahl}"
        )


class TestSkalenstufe:
    def test_quote_und_blockgroesse(self) -> None:
        s = _stufe("Monat", roh=200, effektiv=150, bloecke=25)

        assert s.quote == pytest.approx(0.75)
        assert s.je_block == pytest.approx(8.0)

    def test_mehr_unabhaengige_als_rohe_geht_nicht(self) -> None:
        with pytest.raises(ValueError, match="das geht nicht"):
            _stufe("kaputt", roh=100, effektiv=101)


class TestAmRand:
    """**Der Kern des Moduls.** Ist das Minimum eines, oder das Ende des Bands?"""

    def test_ein_minimum_in_der_mitte_ist_ein_minimum(self) -> None:
        """Der gemessene Fall der Tageskerzen: Quartal zwischen Monat und Halbjahr."""
        leiter = Skalenleiter((
            _stufe("Kalendermonat", roh=152, effektiv=124),
            _stufe("Kalenderquartal", roh=152, effektiv=112),
            _stufe("Halbjahr", roh=152, effektiv=140),
        ))

        assert leiter.strengste.name == "Kalenderquartal"
        assert leiter.am_rand is False
        assert "echtes Minimum" in leiter.urteil()

    def test_ein_minimum_am_ende_ist_keines(self) -> None:
        """Haette die Reihe beim Quartal aufgehoert, waere sie nicht ausgemessen."""
        leiter = Skalenleiter((
            _stufe("Kalendertag", roh=152, effektiv=152),
            _stufe("Kalendermonat", roh=152, effektiv=124),
            _stufe("Kalenderquartal", roh=152, effektiv=112),
        ))

        assert leiter.strengste.name == "Kalenderquartal"
        assert leiter.am_rand is True
        assert "Ende des Massbands" in leiter.urteil()

    def test_auch_das_feine_ende_zaehlt_als_rand(self) -> None:
        """Der gemessene Fall der 15-Minuten-Kerzen liegt am anderen Ende."""
        leiter = Skalenleiter((
            _stufe("Kalendertag", roh=1985, effektiv=1856),
            _stufe("Kalenderwoche", roh=1985, effektiv=1985),
            _stufe("Kalendermonat", roh=1985, effektiv=1985),
        ))

        assert leiter.strengste.name == "Kalendertag"
        assert leiter.am_rand is True

    def test_zwei_sprossen_geben_kein_urteil(self) -> None:
        """Mit zweien ist jede am Rand - eine Warnung ohne Inhalt."""
        leiter = Skalenleiter((
            _stufe("Kalendermonat", roh=152, effektiv=124),
            _stufe("Kalenderquartal", roh=152, effektiv=112),
        ))

        assert leiter.am_rand is None
        assert "Ende des Massbands" not in leiter.urteil()
        assert "echtes Minimum" not in leiter.urteil()

    def test_eine_leere_leiter_urteilt_nicht(self) -> None:
        assert "kein Urteil" in Skalenleiter(()).urteil()


class TestDerModulkopf:
    def test_der_kopf_traegt_beide_gemessenen_leitern(self) -> None:
        import research.zeitskala as modul

        kopf = modul.__doc__ or ""
        assert "Befund 143" in kopf
        assert "0,737" in kopf, "die Tageskerzen-Quote"
        assert "0,922" in kopf, "die 15-Minuten-Quote"
        assert "Handelsdichte" in kopf


class TestImGateVerdrahtet:
    """**Befund 154.** Die Leiter war gebaut, getestet - und an nichts
    angeschlossen.

    ``stichprobe_wie_im_gate`` rechnete mit **einer** Kalenderstufe, dem
    Quartal, hart verdrahtet seit Befund 135. Ueber den Katalog gemessen
    bindet das Quartal bei 2 von 15 Genomen; bei 6 von 15 rechnete das Gate
    deshalb eine zu grosse Stichprobe.
    """

    def test_das_gate_faehrt_die_ganze_leiter(self) -> None:
        import inspect

        from research.gates import stichprobe_wie_im_gate

        quelle = inspect.getsource(stichprobe_wie_im_gate)
        assert "STUFEN" in quelle and "nach_kalender" in quelle, (
            "das Gate rechnet wieder mit einer einzelnen Stufe"
        )

    def test_die_leiter_findet_was_das_quartal_verfehlt(self) -> None:
        """**Die eigentliche Zusicherung**, und sie hat Zaehne.

        Eine duenn handelnde Regel mit Niveaus, die ein halbes Jahr halten -
        genau die Lage von ``Trend-Beteiligung``, wo das Halbjahr bei 29
        bindet und das Quartal bei 39. Das Quartal mittelt die Abhaengigkeit
        zur Haelfte weg, weil beide Quartale eines Halbjahres dasselbe Niveau
        tragen.

        Ein erster Anlauf zu diesem Test benutzte eine dichte Reihe mit
        Monatsniveaus. Dort band das Quartal ohnehin, beide Seiten kamen auf
        27, und der Test waere auch ohne die Leiter gruen gewesen.
        """
        from datetime import UTC, datetime, timedelta
        from types import SimpleNamespace

        from research.gates import quartalsbloecke, stichprobe_wie_im_gate
        from research.unabhaengigkeit import effektive_stichprobe

        t0 = datetime(2016, 1, 1, tzinfo=UTC)
        trades = []
        for i in range(60):
            aus = t0 + timedelta(days=i * 55)
            halbjahr = (aus - t0).days // 183
            trades.append(
                SimpleNamespace(
                    net_pnl=float(
                        ((halbjahr % 3) - 1) * 4.0 + (0.4 if i % 2 else -0.4)
                    ),
                    entry_time=aus - timedelta(days=1),
                    exit_time=aus,
                    symbol="BTCUSDT",
                )
            )

        nur_quartal = effektive_stichprobe(
            len(trades), None, None, weitere=[quartalsbloecke(trades)]
        ).effektiv
        ganze_leiter = stichprobe_wie_im_gate(trades).effektiv

        assert nur_quartal == 44, "sonst misst der Test etwas anderes"
        assert ganze_leiter == 27, "das Halbjahr bindet"
        assert ganze_leiter < nur_quartal, (
            f"die Leiter ({ganze_leiter}) muss hier strenger sein als das "
            f"Quartal allein ({nur_quartal}) - sonst ist sie nicht verdrahtet"
        )

    def test_der_kopf_nennt_die_gemessene_verteilung(self) -> None:
        from research.gates import stichprobe_wie_im_gate

        kopf = stichprobe_wie_im_gate.__doc__ or ""
        assert "Befund 154" in kopf
        assert "2 von 15" in kopf, "wie oft das Quartal ueberhaupt bindet"
        assert "6 von 15" in kopf, "wie oft das Gate zu gross rechnete"
