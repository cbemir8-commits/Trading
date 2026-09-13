"""Wo sitzt der Ertrag - und traegt die Verlustseite den noetigen Zuwachs?

**Befund 270.** Befund 269 hat die Richtung beziffert: Ertrag je Trade bei
gleicher Streuung. Die Anschlussfrage ist, wo dieser Ertrag herkaeme.

``research.exits`` beantwortet die halbe Frage seit langem aus MAE und MFE -
und lief dabei **nur in ``cli review``**, also auf Live-Trades, die es nicht
gibt. Dieselbe Bauart wie in 262 und 265: ein richtig gebautes Werkzeug an
einer leeren Quelle.

Was hier gehalten wird
----------------------
Die Zerlegung ist **strukturell**: nach Ausstiegsgrund, nicht nach Haltezeit
oder Jahr. Die Haltezeit ist ein Ergebnis und kein Einstiegskriterium - wer
danach filtert, hat nichts gelernt, sondern ueberangepasst.

Und die Frage, die vor jeder Arbeit an Stops steht: Reichte es, **jeden**
Verlust auf null zu setzen? Am Bestand ist die Antwort nein - der noetige
Zuwachs ist groesser als die gesamte Verlustsumme.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from research.exits import ertragsquelle


@dataclass
class _Trade:
    net_pnl: Decimal
    exit_reason: str


def _buch(*paare: tuple[str, float]) -> list[_Trade]:
    return [_Trade(Decimal(str(wert)), grund) for grund, wert in paare]


BESTAND = _buch(
    *[("take_profit", 61.99)] * 10,
    *[("signal_exit", 3.70)] * 78,
    *[("stop_loss", -2.09)] * 68,
)


class TestDieZerlegungNachAusstieg:
    def test_jede_sorte_bekommt_eine_zeile(self) -> None:
        q = ertragsquelle(BESTAND)

        assert {g.grund for g in q.gruppen} == {
            "take_profit", "signal_exit", "stop_loss"
        }

    def test_geordnet_nach_beitrag(self) -> None:
        """Die tragende Sorte zuerst - sonst sucht man sie."""
        q = ertragsquelle(BESTAND)

        assert next(g.grund for g in q.gruppen) == "take_profit"
        assert [g.summe for g in q.gruppen] == sorted(
            (g.summe for g in q.gruppen), reverse=True
        )

    def test_wenige_trades_tragen_den_ertrag(self) -> None:
        """Zehn von 156 Trades tragen vier Fuenftel - die Eigenschaft, die
        eine Trendfolge ausmacht und die jede Verbesserung beruecksichtigen
        muss."""
        q = ertragsquelle(BESTAND)
        gross = next(g for g in q.gruppen if g.grund == "take_profit")

        assert gross.anzahl == 10
        assert gross.anteil(q.gesamt) > 75

    def test_die_stops_sind_billig_und_gleichfoermig(self) -> None:
        """Streuung nahe null heisst: Sie greifen, wo sie sollen."""
        q = ertragsquelle(BESTAND)
        stops = next(g for g in q.gruppen if g.grund == "stop_loss")

        assert stops.mittel < 0
        assert stops.streuung < abs(stops.mittel)

    def test_ohne_grund_steht_unbekannt(self) -> None:
        @dataclass
        class _Ohne:
            net_pnl: Decimal

        q = ertragsquelle([_Ohne(Decimal("1"))])

        assert q.gruppen[0].grund == "unbekannt"

    def test_ein_leeres_buch_bricht_nicht(self) -> None:
        q = ertragsquelle([])

        assert q.gruppen == ()
        assert q.gesamt == 0.0
        assert q.trefferquote == 0.0


class TestTraegtDieVerlustseite:
    """Die Frage, die vor jeder Arbeit an Stops und Filtern steht."""

    def test_am_bestand_traegt_sie_nicht(self) -> None:
        q = ertragsquelle(BESTAND)

        assert not q.traegt_die_verlustseite(abs(q.verlustsumme) * 1.05)

    def test_ein_kleiner_zuwachs_ginge(self) -> None:
        q = ertragsquelle(BESTAND)

        assert q.traegt_die_verlustseite(abs(q.verlustsumme) * 0.5)

    def test_das_urteil_sagt_beides(self) -> None:
        q = ertragsquelle(BESTAND)

        urteil = q.urteil(abs(q.verlustsumme) * 1.05)

        assert "traegt ihn **nicht**" in urteil
        assert "%" in urteil

    def test_und_im_guenstigen_fall_das_gegenteil(self) -> None:
        q = ertragsquelle(BESTAND)

        assert "koennte ihn tragen" in q.urteil(abs(q.verlustsumme) * 0.5)


class TestGewinnerUndVerlierer:
    def test_die_trefferquote_kommt_aus_dem_buch(self) -> None:
        q = ertragsquelle(BESTAND)

        assert q.gewinner == 88
        assert q.verlierer == 68
        assert q.trefferquote == pytest.approx(88 / 156 * 100)

    def test_null_zaehlt_als_verlierer(self) -> None:
        """Ein Trade ohne Ergebnis hat Gebuehren gekostet - er ist keiner der
        Gewinner, an denen etwas zu holen waere."""
        q = ertragsquelle(_buch(("signal_exit", 0.0)))

        assert q.verlierer == 1
        assert q.gewinner == 0

    def test_die_summen_ergeben_das_ganze(self) -> None:
        q = ertragsquelle(BESTAND)

        assert q.gesamt == pytest.approx(sum(g.summe for g in q.gruppen))
