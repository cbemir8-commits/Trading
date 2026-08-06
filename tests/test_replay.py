"""Erzeugt der Livebetrieb dieselben Signale wie der Backtest?

Der Backtest sieht die ganze Historie und einen wachsenden Index, der
Livebetrieb nur die letzten ``BUFFER_BARS`` Kerzen und einen Index, der bei
vollem Puffer stehenbleibt. Wo sich Zustand an einem dieser beiden Dinge
festmacht, laufen sie auseinander - still.

``TestSperrfristUeberlebtDenRahmenwechsel`` haelt den Fall fest, an dem das
schon einmal passiert ist.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

from backtest.replay import (
    signale_backtest,
    signale_livebetrieb,
    vergleiche,
)
from research.seeds import spitzenkandidat
from strategy.compiler import compile_genome


def kerzen(n: int, *, seed: int = 3) -> pd.DataFrame:
    """Kerzen mit echten Kreuzungen des gleitenden Schnitts.

    Ein reiner Aufwaertstrend erzeugte **null** Signale, und der Test wuerde
    dann bestehen, ohne etwas geprueft zu haben - ein Fehler, der mir hier
    schon einmal unterlaufen ist. Deshalb eine Reihe, die um ihren Schnitt
    pendelt und ihn oft genug kreuzt.
    """
    rng = np.random.default_rng(seed)
    schritte = rng.normal(0.0, 0.02, n)
    welle = np.sin(np.arange(n) / 45.0) * 0.12
    kurs = 100.0 * np.exp(np.cumsum(schritte) + welle)
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2015-01-01", periods=n, freq="1D", tz="UTC"),
            "open": kurs,
            "high": kurs * 1.02,
            "low": kurs * 0.98,
            "close": kurs,
            "volume": np.full(n, 100.0),
            "turnover": kurs * 100.0,
        }
    )


def einfaches_genom(**aenderungen):
    """Der Spitzenkandidat, gegebenenfalls veraendert - mit kurzen Perioden.

    Kurze Perioden, damit die Testreihe nicht 1000 Kerzen lang sein muss.
    """
    from strategy.genome import Condition, Operand, Operator

    def _ind(name, **p):
        return Operand(kind="indicator", name=name, params=p)

    basis = spitzenkandidat().model_copy(
        update={
            "entry_long": [
                Condition(left=Operand(kind="price", name="close"),
                          op=Operator.CROSS_ABOVE, right=_ind("sma", period=20))
            ],
            "exit_long": [
                Condition(left=Operand(kind="price", name="close"),
                          op=Operator.LT, right=_ind("sma", period=20))
            ],
            "konfluenz": [],
        }
    )
    return basis.model_copy(update=aenderungen) if aenderungen else basis


class TestBeideLaeufeStimmenUeberein:
    def test_ohne_zustand_sind_sie_gleich(self):
        frame = kerzen(600)
        genome = einfaches_genom()

        ergebnis = vergleiche(frame, lambda: compile_genome(genome), buffer_bars=200)

        assert ergebnis.einig, ergebnis.bericht()
        assert ergebnis.signale_backtest > 5, (
            "Ohne Signale prueft der Vergleich nichts - die Testreihe muss "
            "den Schnitt oft genug kreuzen"
        )

    def test_der_spitzenkandidat_stimmt_ueberein(self):
        """Der Kandidat, auf den es ankommt - mit seinen echten Perioden."""
        frame = kerzen(1200)
        genome = spitzenkandidat()

        ergebnis = vergleiche(frame, lambda: compile_genome(genome), buffer_bars=600)

        assert ergebnis.einig, ergebnis.bericht()


class TestSperrfristUeberlebtDenRahmenwechsel:
    """Der Fehler, wegen dem es dieses Modul gibt.

    Die Sperrfrist rechnete mit dem Index im aktuellen Rahmen. Im Backtest
    waechst der; im Livebetrieb steht er bei vollem Puffer fest. Ab dem
    ersten Trade galt dort immer "null Kerzen vergangen", und die Sperrfrist
    lief nie ab - der Roboter haette aufgehoert zu handeln.
    """

    def test_sperrfrist_verhaelt_sich_in_beiden_gleich(self):
        frame = kerzen(600)
        genome = einfaches_genom(cooldown_bars=5)

        # Puffer deutlich kleiner als die Reihe, damit er ueberlaeuft - genau
        # die Lage, die im Betrieb nach BUFFER_BARS Kerzen eintritt.
        ergebnis = vergleiche(frame, lambda: compile_genome(genome), buffer_bars=150)

        assert ergebnis.einig, ergebnis.bericht()

    def test_die_sperrfrist_wirkt_ueberhaupt(self):
        """Sonst waere der Test oben auch dann gruen, wenn sie nie greift."""
        frame = kerzen(600)

        ohne = signale_backtest(frame, lambda: compile_genome(einfaches_genom()))
        mit = signale_backtest(
            frame, lambda: compile_genome(einfaches_genom(cooldown_bars=10))
        )

        assert sum(1 for s in mit if s) < sum(1 for s in ohne if s)

    def test_livebetrieb_verliert_die_signale_nicht_mehr(self):
        """Die Zahl, die den Fehler sichtbar gemacht hat.

        Vorher: Backtest 113 Signale, Livebetrieb 4. Wer nur den Backtest
        ansieht, merkt davon nichts.
        """
        frame = kerzen(600)
        genome = einfaches_genom(cooldown_bars=5)

        a = signale_backtest(frame, lambda: compile_genome(genome))
        b = signale_livebetrieb(frame, lambda: compile_genome(genome), buffer_bars=150)

        anzahl_a = sum(1 for s in a if s is not None)
        anzahl_b = sum(1 for s in b if s is not None)
        assert anzahl_a == anzahl_b
        assert anzahl_b > 5

    def test_sperrfrist_greift_auch_nach_dem_rollen(self):
        """Nicht nur gleich viele Signale - auch an denselben Stellen.

        Ein Lauf, der die Sperrfrist ganz ignoriert, haette ebenfalls in
        beiden Rahmen dieselbe Zahl. Erst der Abgleich der Zeitpunkte
        unterscheidet "richtig" von "gleich falsch".
        """
        frame = kerzen(600)
        mit_sperre = einfaches_genom(cooldown_bars=10)

        gesperrt = signale_livebetrieb(
            frame, lambda: compile_genome(mit_sperre), buffer_bars=150
        )
        frei = signale_livebetrieb(
            frame, lambda: compile_genome(einfaches_genom()), buffer_bars=150
        )

        assert sum(1 for s in gesperrt if s) < sum(1 for s in frei if s)

        # Und zwischen zwei Einstiegen liegen wirklich mindestens 10 Kerzen.
        stellen = [i for i, s in enumerate(gesperrt) if s is not None]
        abstaende = [b - a for a, b in pairwise(stellen)]
        assert all(d >= 10 for d in abstaende), f"zu dicht: {abstaende}"


class TestVergleichMeldetWasErFindet:
    def test_abweichungen_werden_benannt(self):
        """Ein Vergleich, der Unterschiede verschweigt, waere wertlos."""
        frame = kerzen(400)
        genome = einfaches_genom()

        echte = signale_backtest(frame, lambda: compile_genome(genome))
        stellen = [i for i, s in enumerate(echte) if s is not None]
        assert stellen, "Die Testreihe muss Signale erzeugen"

        ergebnis = vergleiche(frame, lambda: compile_genome(genome), buffer_bars=200)
        assert ergebnis.einig
        assert "identisch" in ergebnis.bericht()

    def test_bericht_nennt_die_stellen(self):
        from backtest.replay import Abweichung, Vergleich

        v = Vergleich(balken=100, signale_backtest=5, signale_livebetrieb=2)
        v.abweichungen.append(
            Abweichung(index=7, zeit=pd.Timestamp("2020-01-08", tz="UTC"),
                       backtest="long", livebetrieb="-")
        )

        text = v.bericht()
        assert not v.einig
        assert "2020-01-08" in text
        assert "long" in text

    def test_ungleiche_laengen_fallen_auf(self):
        """``strict=True`` beim Reissverschluss - sonst wuerde stillschweigend
        der kuerzere Lauf gewinnen und der Rest ungeprueft bleiben."""
        frame = kerzen(200)
        genome = einfaches_genom()

        a = signale_backtest(frame, lambda: compile_genome(genome))
        b = signale_livebetrieb(frame, lambda: compile_genome(genome), buffer_bars=100)

        assert len(a) == len(b) == len(frame)
        with pytest.raises(ValueError):
            list(zip(a, b[:-1], strict=True))


class TestDerVergleichFaengtAlleDreiFehlerarten:
    """Ein Signalvergleich allein haette zwei von drei Fehlern durchgelassen.

    Deshalb vergleicht ``Entscheidung`` die ganze Flaeche: Einstiegssignal,
    Ausstiegsbedingung, Kapitalanteil. Dieser Test weist nach, dass jede der
    drei Spalten wirklich anschlaegt - sonst waere die Erweiterung nur
    Dekoration.
    """

    class Fest:
        """Eine Strategie, deren drei Antworten sich einzeln verstellen lassen."""

        strategy_id = "fest"
        warmup_bars = 5

        def __init__(self, *, anteil=None, raus=False, signal=False) -> None:
            self._anteil = anteil
            self._raus = raus
            self._signal = signal
            self.equity_fraction = anteil

        def prepare(self, frame):
            return {}

        def fraction_at(self, index):
            return self._anteil

        def should_exit(self, ctx, side) -> bool:
            return self._raus

        def on_bar(self, ctx):
            from core.models import Side, Signal

            if not self._signal:
                return None
            return Signal(
                timestamp=ctx.time, symbol="X", side=Side.BUY,
                entry_price=Decimal("100"), stop_loss=Decimal("99"),
                strategy_id="fest", reason="Test",
            )

    def _vergleich_zwischen(self, links, rechts):
        """Zwei verschiedene Strategien gegeneinander - stellt eine Abweichung nach."""
        from backtest.replay import entscheidungen_backtest

        frame = kerzen(60)
        a = entscheidungen_backtest(frame, lambda: links)
        b = entscheidungen_backtest(frame, lambda: rechts)
        return [x for x, y in zip(a, b, strict=True) if x != y]

    def test_unterschiedliches_signal_faellt_auf(self):
        unterschiede = self._vergleich_zwischen(
            self.Fest(signal=True), self.Fest(signal=False)
        )
        assert unterschiede

    def test_unterschiedliche_ausstiegsbedingung_faellt_auf(self):
        """Der Fehler, der im Livebetrieb fehlte."""
        unterschiede = self._vergleich_zwischen(
            self.Fest(raus=True), self.Fest(raus=False)
        )
        assert unterschiede, (
            "Die Ausstiegsbedingung wird nicht verglichen - genau dieser "
            "Fehler ist im Livebetrieb monatelang unbemerkt geblieben"
        )

    def test_unterschiedlicher_kapitalanteil_faellt_auf(self):
        """Der teuerste Fehler: 3,0 statt 0,26 - zehnfache Positionen."""
        unterschiede = self._vergleich_zwischen(
            self.Fest(anteil=Decimal("3.0")), self.Fest(anteil=Decimal("0.26"))
        )
        assert unterschiede, (
            "Der Kapitalanteil wird nicht verglichen - so blieb die "
            "zehnfache Positionsgroesse unentdeckt"
        )

    def test_kein_anteil_und_null_sind_nicht_dasselbe(self):
        """``None`` heisst "nicht handeln", 0,0 heisst "Groesse null".

        Als Zahl gespeichert waeren beide 0,0 und der Vergleich blind fuer
        den Unterschied.
        """
        unterschiede = self._vergleich_zwischen(
            self.Fest(anteil=None), self.Fest(anteil=Decimal("0"))
        )
        assert unterschiede
