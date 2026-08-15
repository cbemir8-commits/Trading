"""Dieselbe Huerde fuer den Bestand wie fuer jeden Vorschlag.

Zwei Tests tragen diese Datei:

``test_unentschieden_ist_kein_scheitern`` - "Nicht stabil" heisst zweierlei:
der Vorteil ist weg, oder man haette ihn hier gar nicht sehen koennen. Bei 77
Trades je Haelfte ist das Zweite der wahrscheinlichere Fall. Ein Urteil ohne
diese Unterscheidung waere ein Scheinbefund.

``test_chronologisch_und_nicht_zufaellig`` - Die Frage ist, ob der Vorteil
*spaeter* noch da war. Eine zufaellige Teilung verwischt genau das, was
gemessen werden soll.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from research.haelften import (
    Haelfte,
    Halbierung,
    erkennbarer_unterschied,
    teile,
)


@dataclass
class FakeTrade:
    r_multiple: float
    exit_time: datetime


def trades(werte: list[float], *, start: int = 0) -> list[FakeTrade]:
    anfang = datetime(2018, 1, 1, tzinfo=UTC)
    return [
        FakeTrade(r_multiple=w, exit_time=anfang + timedelta(days=start + i))
        for i, w in enumerate(werte)
    ]


class TestTeilen:
    def test_chronologisch_und_nicht_zufaellig(self) -> None:
        """**Der Test, der die Fragestellung traegt.**

        Alle Gewinner liegen vorn, alle Verlierer hinten. Eine zufaellige
        Teilung mischte beide Haelften und faende nichts - genau der Effekt,
        der hier gefunden werden soll.
        """
        werte = [2.0] * 30 + [-1.0] * 30
        geteilt = teile(trades(werte))

        assert geteilt is not None
        erste, zweite = geteilt
        assert erste.mittel_r == 2.0
        assert zweite.mittel_r == -1.0

    def test_unsortierte_eingaben_werden_geordnet(self) -> None:
        """Die Reihenfolge in der Liste ist nicht die Reihenfolge der Zeit -
        im Portfolio-Walk-Forward kommen die Beine nacheinander."""
        gemischt = trades([2.0] * 30, start=100) + trades([-1.0] * 30, start=0)
        geteilt = teile(gemischt)

        assert geteilt is not None
        assert geteilt[0].mittel_r == -1.0, "Die frueheren Trades gehoeren nach vorn"
        assert geteilt[1].mittel_r == 2.0

    def test_zu_wenige_trades_liefern_nichts(self) -> None:
        assert teile(trades([1.0] * 10)) is None


class TestHaelfte:
    def test_der_sharpe_je_trade_ist_mittel_durch_streuung(self) -> None:
        h = Haelfte(name="x", trades=100, mittel_r=0.5, streuung_r=2.0)

        assert h.sharpe_je_trade == 0.25
        assert h.t_wert == 2.5

    def test_ohne_streuung_kippt_nichts(self) -> None:
        h = Haelfte(name="x", trades=100, mittel_r=0.5, streuung_r=0.0)

        assert h.sharpe_je_trade == 0.0
        assert h.t_wert == 0.0


class TestUrteil:
    def haelfte(self, *, name: str, mittel: float, trades_n: int = 77) -> Haelfte:
        return Haelfte(name=name, trades=trades_n, mittel_r=mittel, streuung_r=4.0)

    def test_ein_haltender_vorteil_wird_als_solcher_gemeldet(self) -> None:
        h = Halbierung(
            erste=self.haelfte(name="erste", mittel=1.5),
            zweite=self.haelfte(name="zweite", mittel=1.5),
        )

        assert h.haelt
        assert "Der Vorteil haelt" in h.urteil()
        assert "dieselbe Huerde" in h.urteil()

    def test_unentschieden_ist_kein_scheitern(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Eine zweite Haelfte, die zu klein ist, um den Effekt der ersten zu
        sehen, liefert kein "der Vorteil ist weg" - sie liefert gar nichts.
        Das muss im Urteil stehen, sonst wird aus einer fehlenden Messung ein
        Befund.
        """
        h = Halbierung(
            erste=self.haelfte(name="erste", mittel=0.3),
            zweite=self.haelfte(name="zweite", mittel=0.1),
        )

        assert not h.aussagekraeftig
        urteil = h.urteil()
        assert "Unentschieden" in urteil
        assert "zu klein" in urteil
        assert "Scheinbefund" in urteil

    def test_ein_vorzeichenwechsel_wird_benannt(self) -> None:
        h = Halbierung(
            erste=self.haelfte(name="erste", mittel=2.0),
            zweite=self.haelfte(name="zweite", mittel=-0.5),
        )

        assert h.aussagekraeftig, "Sonst prueft der Test etwas anderes"
        assert not h.gleiches_vorzeichen
        urteil = h.urteil()
        assert "Vorzeichen dreht" in urteil
        assert "waere das kein Fund" in urteil

    def test_positiv_aber_nicht_auffaellig_ist_ein_eigener_fall(self) -> None:
        """Zwischen "haelt" und "gedreht" liegt ein dritter Zustand, und ihn
        mit einem der beiden zu verwechseln waere in beide Richtungen falsch."""
        h = Halbierung(
            erste=self.haelfte(name="erste", mittel=2.0),
            zweite=self.haelfte(name="zweite", mittel=0.4),
        )

        assert h.gleiches_vorzeichen
        assert not h.zweite_traegt
        assert h.aussagekraeftig
        urteil = h.urteil()
        assert "traegt nicht" in urteil
        assert "staerker als ein Vorzeichenwechsel" in urteil

    def test_die_erkennbarkeit_steht_immer_dabei(self) -> None:
        """In jedem Urteil - sonst liest sich eine Zahl je nach Ausgang
        anders, obwohl sie dieselbe Grundlage hat."""
        for zweite_mittel in (1.5, 0.1, -0.5, 0.4):
            h = Halbierung(
                erste=self.haelfte(name="erste", mittel=2.0),
                zweite=self.haelfte(name="zweite", mittel=zweite_mittel),
            )
            if h.haelt:
                continue
            assert "aufgefallen" in h.urteil(), zweite_mittel


class TestErkennbarkeit:
    def test_mehr_trades_machen_kleinere_effekte_sichtbar(self) -> None:
        klein = Haelfte(name="x", trades=20, mittel_r=0.0, streuung_r=4.0)
        gross = Haelfte(name="x", trades=2000, mittel_r=0.0, streuung_r=4.0)

        assert erkennbarer_unterschied(gross) < erkennbarer_unterschied(klein)

    def test_ohne_trades_ist_nichts_erkennbar(self) -> None:
        leer = Haelfte(name="x", trades=0, mittel_r=0.0, streuung_r=4.0)

        assert not np.isfinite(erkennbarer_unterschied(leer))
