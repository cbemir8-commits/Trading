"""Tests fuer ``research.randschnitt`` - Befund 151 und 152."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from research.randschnitt import (
    Randbefund,
    beurteile,
    fertige,
    ohne_zensierte,
    randtrades,
)


def _trade(pnl: float, *, grund: str = "signal_exit"):
    return SimpleNamespace(net_pnl=pnl, exit_reason=grund)


class TestRandtrades:
    def test_findet_die_am_datenende_beendeten(self) -> None:
        trades = [_trade(1.0), _trade(2.0, grund="end_of_data"), _trade(-1.0)]

        assert [t.net_pnl for t in randtrades(trades)] == [2.0]

    def test_ohne_randtrades_ist_die_liste_leer(self) -> None:
        assert randtrades([_trade(1.0), _trade(-1.0)]) == []

    def test_ein_stop_ist_kein_randtrade(self) -> None:
        """Ein Stop ist ein Ausstieg nach Regel - der zaehlt."""
        assert randtrades([_trade(-1.0, grund="stop_loss")]) == []


class TestRandbefund:
    def test_mehr_randtrades_als_trades_geht_nicht(self) -> None:
        with pytest.raises(ValueError, match="das geht nicht"):
            Randbefund(gesamt=3, am_rand=4, guete_mit=0.1, guete_ohne=0.1)

    def test_ohne_randtrades_ist_es_sauber(self) -> None:
        b = Randbefund(gesamt=10, am_rand=0, guete_mit=0.25, guete_ohne=0.25)

        assert b.sauber
        assert b.hub == pytest.approx(0.0)
        assert "nach Regel ausgestiegen" in b.urteil()

    def test_der_hub_wird_beziffert(self) -> None:
        """**Der Kern.** Befund 22 hat so ein Sechstel der Trades entlarvt."""
        b = Randbefund(gesamt=158, am_rand=2, guete_mit=0.2848, guete_ohne=0.2506)

        assert not b.sauber
        assert b.hub == pytest.approx(0.0342, abs=1e-4)
        assert b.anteil == pytest.approx(2 / 158)
        assert "freundlicher" in b.urteil()

    def test_ein_ungunstiger_rand_wird_nicht_als_geschenk_gelesen(self) -> None:
        """Zoege der Rand die Zahl nach unten, waere der Hinweis falsch."""
        b = Randbefund(gesamt=100, am_rand=1, guete_mit=0.20, guete_ohne=0.25)

        assert b.hub < 0
        assert "freundlicher" not in b.urteil()


class TestBeurteile:
    def test_der_gemessene_fall(self) -> None:
        """Zwei Randtrades von +26,19 und +25,48 unter lauter kleineren.

        Genau die Lage aus Befund 151: Die beiden groessten Gewinner des Laufs
        sind die, die nicht zu Ende gehandelt wurden.
        """
        trades = [_trade(-2.0) for _ in range(80)]
        trades += [_trade(3.0) for _ in range(76)]
        trades += [
            _trade(26.19, grund="end_of_data"),
            _trade(25.48, grund="end_of_data"),
        ]

        b = beurteile(trades)

        assert b is not None
        assert b.am_rand == 2
        assert b.gesamt == 158
        assert b.hub > 0, "die Randtrades machen die Zahl freundlicher"

    def test_ohne_rand_stimmen_beide_gueten_ueberein(self) -> None:
        trades = [_trade(1.0), _trade(-1.0), _trade(2.0), _trade(0.5), _trade(-0.5)]

        b = beurteile(trades)

        assert b is not None and b.sauber
        assert b.guete_mit == pytest.approx(b.guete_ohne)

    def test_zu_wenige_trades_geben_keine_auskunft(self) -> None:
        """Unter fuenf ist eine Streuung keine Auskunft."""
        assert beurteile([_trade(1.0), _trade(2.0)]) is None

    def test_ohne_streuung_wird_nichts_geteilt(self) -> None:
        gleich = [_trade(1.0) for _ in range(6)]

        b = beurteile(gleich)

        assert b is not None
        assert b.guete_mit == 0.0


class TestFertige:
    """Die Gegenmenge zu ``randtrades`` - **die Stichprobe, die zaehlt.**"""

    def test_behaelt_die_nach_regel_beendeten(self) -> None:
        trades = [_trade(1.0), _trade(2.0, grund="end_of_data"), _trade(-1.0)]

        assert [t.net_pnl for t in fertige(trades)] == [1.0, -1.0]

    def test_zusammen_ergeben_beide_das_ganze(self) -> None:
        """Kein Trade faellt zwischen die Mengen, keiner zaehlt doppelt."""
        trades = [
            _trade(1.0),
            _trade(2.0, grund="end_of_data"),
            _trade(-1.0, grund="stop_loss"),
            _trade(0.5, grund="take_profit"),
        ]

        assert len(fertige(trades)) + len(randtrades(trades)) == len(trades)

    def test_ohne_zensierte_bleibt_alles_stehen(self) -> None:
        trades = [_trade(1.0), _trade(-1.0)]

        assert fertige(trades) == trades


class TestOhneZensierte:
    """Der Bericht in zwei Sichten - **ohne das Original anzufassen.**"""

    @staticmethod
    def _bericht():
        fenster = [
            SimpleNamespace(trades=[_trade(1.0), _trade(9.0, grund="end_of_data")]),
            SimpleNamespace(trades=[_trade(-1.0)]),
        ]
        return SimpleNamespace(
            all_trades=[t for w in fenster for t in w.trades],
            windows=fenster,
            equity_curve="unberuehrt",
        )

    def test_filtert_flache_liste_und_fenster(self) -> None:
        gefiltert = ohne_zensierte(self._bericht())

        assert [t.net_pnl for t in gefiltert.all_trades] == [1.0, -1.0]
        assert [t.net_pnl for t in gefiltert.windows[0].trades] == [1.0]
        assert [t.net_pnl for t in gefiltert.windows[1].trades] == [-1.0]

    def test_das_original_bleibt_vollstaendig(self) -> None:
        """**Der Aufrufer braucht beide Sichten.** Rendite und Rueckgang
        rechnen mit der offenen Position, die Statistik nicht."""
        original = self._bericht()

        ohne_zensierte(original)

        assert len(original.all_trades) == 3
        assert len(original.windows[0].trades) == 2

    def test_die_kapitalkurve_wird_nicht_angefasst(self) -> None:
        """Dort gehoert die offene Position hin - sie ist zum letzten Kurs
        bewertet und damit der Kontostand."""
        gefiltert = ohne_zensierte(self._bericht())

        assert gefiltert.equity_curve == "unberuehrt"


class TestAlarmUndNichtErgebnis:
    """**Der Lesefehler, der in Befund 151 einmal passiert ist.**

    Aus ``guete_ohne`` unter null wurde "die Regel ist negativ" gelesen. Das
    ist die falsche Gegenprobe: Die Trades wegzulassen misst, wie viel an
    ihnen haengt; was ohne den Fehler herauskaeme, sagt erst ein neuer Lauf
    mit laengerem Nachlauf. Er sagte 0,2952 - positiv.
    """

    def test_der_kopf_nennt_beide_gegenproben(self) -> None:
        import research.randschnitt as modul

        kopf = modul.__doc__ or ""
        assert "-0,3874" in kopf, "was Weglassen ergibt"
        assert "0,2952" in kopf, "was Zuendehandeln ergibt"
        assert "die falsche Frage" in kopf
        assert "die richtige" in kopf
        assert "Alarm" in kopf

    def test_die_funktion_warnt_vor_der_verwechslung(self) -> None:
        """Wer nur die Docstring liest, muss es auch dort finden."""
        assert "Alarm" in (beurteile.__doc__ or "")

    def test_am_fensterende_ist_der_nachlauf_das_mittel(self) -> None:
        """Zwei Raender, zwei Antworten - und das Urteil nennt beide.

        Am Fensterende hilft ein laengerer Nachlauf, am Serienende zaehlen
        die Trades in der Statistik nicht mit. Wer nur eine der beiden
        Antworten kennt, wendet sie auf den falschen Rand an - genau das ist
        in Befund 151 passiert.
        """
        b = Randbefund(gesamt=53, am_rand=10, guete_mit=0.3185, guete_ohne=-0.3874)
        satz = b.urteil()

        assert "Nachlauf" in satz
        assert "Serienende" in satz

    def test_der_verlaengerte_nachlauf_haelt(self) -> None:
        """Faellt das um, ist der Fehler aus Befund 151 zurueck."""
        from backtest.walkforward import NACHLAUF_FENSTER

        assert NACHLAUF_FENSTER >= 3


class TestDerModulkopf:
    def test_der_kopf_traegt_die_gemessene_leiter(self) -> None:
        import research.randschnitt as modul

        kopf = modul.__doc__ or ""
        assert "Befund 151" in kopf
        assert "0,7255" in kopf, "der Wert mit Randtrades"
        assert "0,6026" in kopf, "und der ohne"
        assert "Befund 22" in kopf, "die Fundstelle des Fensterrand-Fehlers"

    def test_der_kopf_zeigt_alle_drei_behandlungen(self) -> None:
        """**Befund 152.** Die Wahl zwischen ihnen ist der ganze Punkt - ohne
        die Tabelle sieht "zensierte weglassen" wie eine Geschmacksfrage aus.
        """
        import research.randschnitt as modul

        kopf = modul.__doc__ or ""
        for zahl in ("0,5868", "0,4707", "0,4452"):
            assert zahl in kopf, f"{zahl} fehlt - eine der drei Behandlungen"
        assert "vier fertig gehandelte Trades" in kopf, (
            "warum das Kuerzen ausgeschieden ist"
        )

    def test_es_gibt_keinen_puffer_mehr(self) -> None:
        """Faellt das um, ist eine gewaehlte Zahl zurueck, wo keine hingehoert."""
        import research.randschnitt as modul

        assert not hasattr(modul, "RANDPUFFER_TAGE")
