"""Der fensterweise Vergleich - und der Fall, fuer den er gebaut wurde.

``test_aggregat_besser_fenster_schlechter`` benutzt die echten Zahlen aus der
Short-Messung: 12 Fenster besser, 18 schlechter, und trotzdem sah das
Gesamtergebnis auf jeder Achse besser aus. Genau dort greift das Werkzeug.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backtest.walkforward import WalkForwardReport, Window, WindowResult
from research.fenstervergleich import (
    SIGNIFIKANZ,
    Fenstervergleich,
    vergleiche,
    vorzeichentest,
)


class FakeMetrics:
    """Nur die beiden Felder, die der Vergleich anfasst."""

    def __init__(self, gewinn: float, drawdown: float = 10.0) -> None:
        self.net_profit = Decimal(str(gewinn))
        self.max_drawdown_pct = Decimal(str(drawdown))


def bericht(*gewinne: float, drawdowns: list[float] | None = None) -> WalkForwardReport:
    dd = drawdowns or [10.0] * len(gewinne)
    fenster = []
    for i, (gewinn, rueckgang) in enumerate(zip(gewinne, dd, strict=True)):
        w = Window(
            index=i,
            train_start=datetime(2020, 1, 1, tzinfo=UTC),
            train_end=datetime(2021, 1, 1, tzinfo=UTC),
            test_start=datetime(2021, 1, 1 + i, tzinfo=UTC),
            test_end=datetime(2021, 4, 1, tzinfo=UTC),
        )
        fenster.append(
            WindowResult(
                window=w,
                metrics=FakeMetrics(gewinn, rueckgang),  # type: ignore[arg-type]
                trades=[],
                result=None,  # type: ignore[arg-type]
            )
        )
    return WalkForwardReport(windows=fenster)


class TestVorzeichentest:
    def test_alles_besser_ist_unwahrscheinlich(self) -> None:
        assert vorzeichentest(10, 0) == pytest.approx(1 / 1024)

    def test_haelfte_haelfte_ist_unauffaellig(self) -> None:
        assert vorzeichentest(5, 5) > 0.5

    def test_mehrheit_schlechter_gibt_hohen_wert(self) -> None:
        """Ein hoher p-Wert heisst nicht 'schlecht', sondern 'kein Nachweis'."""
        assert vorzeichentest(12, 18) > 0.8

    def test_ohne_fenster(self) -> None:
        assert vorzeichentest(0, 0) == 1.0


class TestVergleich:
    def test_durchgehend_besser_ist_belastbar(self) -> None:
        a = bericht(*[1.0] * 12)
        b = bericht(*[2.0] * 12)

        v = vergleiche(a, b)

        assert v.besser == 12
        assert v.schlechter == 0
        assert v.p_wert <= SIGNIFIKANZ
        assert v.belastbar

    def test_aggregat_besser_fenster_schlechter(self) -> None:
        """**Der Fall, fuer den das Werkzeug gebaut wurde.**

        Nachgebaut aus der Short-Messung: Ein einziges starkes Fenster hebt das
        Gesamtergebnis, waehrend die Mehrzahl der Fenster schlechter wird. Wer
        nur die Summe ansieht, meldet einen Fortschritt, den es nicht gibt.
        """
        a = bericht(*([1.0] * 30 + [1.0]))
        # 12 besser, 18 schlechter - und ein Ausreisser, der alles ueberdeckt.
        werte = [2.0] * 11 + [0.5] * 18 + [1.0] + [500.0]
        b = bericht(*werte)

        v = vergleiche(a, b)

        assert v.besser == 12, "elf kleine Verbesserungen plus der Ausreisser"
        assert v.schlechter == 18
        assert v.mittlere_differenz > 0, "Im Aggregat sieht es besser aus"
        assert not v.belastbar
        assert v.mehrheit_schlechter
        assert "SCHLECHTER" in v.bericht()

    def test_unentschieden_ist_nicht_belastbar(self) -> None:
        a = bericht(*[1.0] * 10)
        b = bericht(*([2.0] * 5 + [0.5] * 5))

        v = vergleiche(a, b)

        assert not v.belastbar
        assert not v.mehrheit_schlechter
        assert "Zufall" in v.bericht()

    def test_identische_laeufe(self) -> None:
        a = bericht(*[1.0] * 5)

        v = vergleiche(a, bericht(*[1.0] * 5))

        assert v.unveraendert == 5
        assert not v.belastbar

    def test_rueckgang_wird_getrennt_gezaehlt(self) -> None:
        """Mehr Gewinn bei mehr Rueckgang ist kein reiner Fortschritt."""
        a = bericht(1.0, 1.0, drawdowns=[10.0, 10.0])
        b = bericht(2.0, 2.0, drawdowns=[15.0, 15.0])

        v = vergleiche(a, b)

        assert v.besser == 2
        assert v.rueckgang_besser == 0

    def test_verschiedene_fensterzahl_wird_abgelehnt(self) -> None:
        """Sonst vergleicht man verschiedene Zeitraeume miteinander."""
        with pytest.raises(ValueError, match="Fensterzahl"):
            vergleiche(bericht(1.0, 1.0), bericht(1.0))

    def test_verschobene_fenster_werden_abgelehnt(self) -> None:
        a = bericht(1.0, 1.0)
        b = bericht(1.0, 1.0)
        verschoben = Window(
            index=0,
            train_start=datetime(2020, 1, 1, tzinfo=UTC),
            train_end=datetime(2021, 1, 1, tzinfo=UTC),
            test_start=datetime(2022, 6, 1, tzinfo=UTC),
            test_end=datetime(2022, 9, 1, tzinfo=UTC),
        )
        b.windows[0].window = verschoben

        with pytest.raises(ValueError, match="passen nicht"):
            vergleiche(a, b)

    def test_leerer_bericht(self) -> None:
        v = vergleiche(WalkForwardReport(), WalkForwardReport())

        assert v.fenster == 0
        assert not v.belastbar


def test_bericht_nennt_alle_zahlen() -> None:
    v = Fenstervergleich(
        fenster=31, besser=12, schlechter=18, unveraendert=1,
        rueckgang_besser=5, mittlere_differenz=1.33, streuung=9.91, p_wert=0.9,
    )

    text = v.bericht()

    assert "31 Fenster" in text
    assert "12 besser" in text
    assert "18 schlechter" in text
    assert "p = 0.900" in text


class TestJeTradeVergleich:
    """**Befund 155.** Fuer einen Verbund taugt der Fenstergewinn nicht.

    Zwei Regeln parallel teilen das Kapital; der Gewinn haengt dann an der
    Positionsgroesse und nicht an der Guete. Verglichen wird deshalb der
    Mittelwert je Trade.
    """

    def test_besser_wenn_die_zweite_seite_hoeher_liegt(self) -> None:
        from research.fenstervergleich import vergleiche_je_trade

        a = [[1.0, 1.0], [1.0], [1.0, 1.0]]
        b = [[2.0, 2.0], [2.0], [2.0, 2.0]]

        v = vergleiche_je_trade(a, b)

        assert v.besser == 3
        assert v.schlechter == 0
        assert v.belastbar is False, "drei Fenster reichen fuer p <= 0,05 nicht"

    def test_die_mehrheit_entscheidet_nicht_die_summe(self) -> None:
        """**Der Kern der Datei, auf die Qualitaet uebertragen.**

        Ein Fenster mit einem grossen Gewinn, sechs mit kleinen Verlusten. Die
        Summe der Differenzen ist positiv, die Mehrzahl der Fenster trotzdem
        schlechter - und das Urteil sagt es.
        """
        from research.fenstervergleich import vergleiche_je_trade

        a = [[1.0] for _ in range(7)]
        b = [[30.0]] + [[0.5] for _ in range(6)]

        v = vergleiche_je_trade(a, b)

        assert v.besser == 1 and v.schlechter == 6
        assert v.mittlere_differenz > 0, "die Summe spricht fuer B"
        assert v.mehrheit_schlechter
        assert not v.belastbar
        assert "SCHLECHTER" in v.bericht()

    def test_fenster_ohne_trades_zaehlen_nicht_als_verbesserung(self) -> None:
        """Wo eine Seite nicht handelt, gibt es keine Auskunft - und ein
        leeres Fenster darf keine Stimme abgeben."""
        from research.fenstervergleich import vergleiche_je_trade

        v = vergleiche_je_trade([[1.0], [], [1.0]], [[2.0], [], []])

        assert v.besser == 1
        assert v.unveraendert == 2
        assert v.fenster == 3

    def test_ungleiche_fensterzahl_wird_abgewiesen(self) -> None:
        from research.fenstervergleich import vergleiche_je_trade

        with pytest.raises(ValueError, match="Verschiedene Fensterzahl"):
            vergleiche_je_trade([[1.0]], [[1.0], [2.0]])

    def test_der_kopf_nennt_die_grenze_des_tests(self) -> None:
        """Er sieht die effektive Stichprobe nicht - und beim Verbund steckt
        dort der groessere Teil des Gewinns."""
        from research.fenstervergleich import vergleiche_je_trade

        kopf = vergleiche_je_trade.__doc__ or ""
        assert "effektive Stichprobe" in kopf
        assert "Befund 155" in kopf
