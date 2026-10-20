"""Das Zielfenster stand ohne seine Empfindlichkeit da - Befund 388.

Befund 387 hat gemessen, dass **21 Versuche** bleiben. Darunter stand im Befehl
der richtige Satz:

    Die Latte haengt an der effektiven Stichprobe - mehr Trades bei gleichem
    Ertrag je Trade schieben die Grenze hinaus, mehr Suche nicht.

Ohne Zahl. Und die Zahl ist der ganze Punkt. Gemessen am echten Handelsbuch der
Zulassungsreihe, nur ``effektiv`` wandert:

    n_eff   DSR des verbessernden Wegs   Fenster
      113                       0,9498   kein Weg traegt
      114                       0,9531   verschwindend
      115                       0,9561   224      <- heute
      120                       0,9688   286
      130                       0,9849   469
      150                       0,9969   ueber 1000

**Die Zulassung steht auf einem wirksamen Trade Rand.** Und die 21
verbleibenden Versuche sind keine Budgetgrenze, sondern eine Stichprobengrenze
im Budgetmantel: Ab n_eff 130 bindet das Budget gar nicht mehr.

Der Rand zeigt in die **sichere** Richtung. Die 115 sind die strengste Stufe
der ganzen Zeitskala (Befund 154); jede lockerere Einteilung gibt mehr wirksame
Trades und damit ein weiteres Fenster. Knapp heisst hier konservativ, nicht
unzuverlaessig.
"""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

import cli
from research.gates import GateThresholds
from research.referenz import SPOTPUNKT
from research.zielfenster import Handelsbuch, Stichprobenrand, vermesse

#: Das gemessene Handelsbuch der Zulassungsreihe (Spot-Punkt, Befund 387/388).
#:
#: **Gemessen, nicht nachgebaut.** Mein erster Anlauf hat es aus den Groessen
#: des Referenzpunkts zusammengesetzt, die Summe in der falschen Einheit
#: angenommen und einen noetigen Hebefaktor von 10,7 statt 1,2553 bekommen.
#: Aufgefallen ist das nur, weil der Unsinn gross genug war.
BUCH = Handelsbuch(
    trades_gesamt=158,
    effektiv=115,
    mittel=4.912407361154881,
    streuung=18.141776194941365,
    summe=820.1067187827996,
    rueckgang_pct=9.868736145650873,
    jahre=8.0,
)

#: Die Momente der gehandelten Trades auf der Reihe - dieselben wie in
#: ``referenz.SPOTPUNKT``, und ein Test haelt das aneinander.
SCHIEFE = 3.4646
WOELBUNG = 15.9173


def _fenster(buch: Handelsbuch, *, versuche: int = 203):
    t = GateThresholds()
    return vermesse(
        buch, versuche=versuche, schwelle_pct=t.min_cagr_pct, dsr_ziel=0.95,
        drawdown_grenze=t.max_oos_drawdown_pct,
        schiefe=SCHIEFE, woelbung=WOELBUNG,
    )


class TestDasBuchIstDasGemessene:
    def test_es_traegt_die_momente_des_referenzpunkts(self) -> None:
        assert pytest.approx(SPOTPUNKT.schiefe, abs=0.0001) == SCHIEFE
        assert pytest.approx(SPOTPUNKT.woelbung, abs=0.0001) == WOELBUNG

    def test_und_die_stichprobe(self) -> None:
        assert BUCH.effektiv == SPOTPUNKT.effektiv

    def test_der_noetige_faktor_ist_der_gemessene(self) -> None:
        """1,2553 - und nicht 10,7, wie mein nachgebautes Buch behauptet hat."""
        weg = next(w for w in _fenster(BUCH).wege if w.name == "verbessern")

        assert weg.faktor == pytest.approx(1.2553, abs=0.0005)
        assert weg.dsr_danach == pytest.approx(0.9561, abs=0.0005)
        assert weg.traegt


class TestDerRand:
    def test_er_liegt_bei_114(self) -> None:
        rand = _fenster(BUCH).stichprobenrand(schiefe=SCHIEFE, woelbung=WOELBUNG)

        assert rand is not None
        assert rand.mindestens == 114
        assert not rand.traegt_bis_unten

    def test_heute_ist_ein_trade_luft(self) -> None:
        rand = _fenster(BUCH).stichprobenrand(schiefe=SCHIEFE, woelbung=WOELBUNG)

        assert rand.rand(BUCH.effektiv) == 1

    @pytest.mark.parametrize(
        ("effektiv", "traegt"),
        [(113, False), (114, True), (115, True)],
    )
    def test_die_kante_einzeln_nachgerechnet(
        self, effektiv: int, traegt: bool
    ) -> None:
        """Nicht nur die Bisektion - jede Sprosse der Kante einzeln."""
        weg = next(
            w for w in _fenster(replace(BUCH, effektiv=effektiv)).wege
            if w.name == "verbessern"
        )

        assert weg.traegt is traegt

    def test_unter_dem_rand_gibt_es_gar_keinen_rand_mehr(self) -> None:
        """``None`` heisst eins: Es traegt schon heute kein Weg. Das von
        'traegt_bis_unten' zu unterscheiden ist der Grund, warum es beide
        Felder gibt - genau wie bei ``Budgetgrenze``."""
        rand = _fenster(replace(BUCH, effektiv=113)).stichprobenrand(
            schiefe=SCHIEFE, woelbung=WOELBUNG
        )

        assert rand is None

    def test_und_bei_viel_stichprobe_traegt_es_bis_unten(self) -> None:
        rand = _fenster(replace(BUCH, effektiv=400)).stichprobenrand(
            tiefstens=200, schiefe=SCHIEFE, woelbung=WOELBUNG
        )

        assert rand is not None
        assert rand.traegt_bis_unten
        assert rand.mindestens == 200

    def test_die_beschriftung_unterscheidet_die_beiden_faelle(self) -> None:
        eng = Stichprobenrand(mindestens=114, traegt_bis_unten=False)
        weit = Stichprobenrand(mindestens=200, traegt_bis_unten=True)

        assert str(eng) == "114"
        assert "bis 200 hinunter" in str(weit)


class TestDasFensterGegenDieStichprobe:
    """Die Tabelle aus dem Kopf - die Groessenordnung, die gefehlt hat."""

    @pytest.mark.parametrize(
        ("effektiv", "erwartet"),
        [(115, 224), (120, 286), (130, 469)],
    )
    def test_fuenf_trades_sind_zweiundsechzig_versuche(
        self, effektiv: int, erwartet: int
    ) -> None:
        grenze = _fenster(replace(BUCH, effektiv=effektiv)).budgetgrenze(
            schiefe=SCHIEFE, woelbung=WOELBUNG
        )

        assert grenze is not None
        assert not grenze.gedeckelt
        assert grenze.versuche == erwartet

    def test_ab_hundertdreissig_bindet_das_budget_nicht_mehr(self) -> None:
        """Der Satz, der aus der Tabelle folgt: Das ist keine Budgetgrenze."""
        from research.stand import BUDGET

        grenze = _fenster(replace(BUCH, effektiv=130)).budgetgrenze(
            schiefe=SCHIEFE, woelbung=WOELBUNG
        )

        assert grenze.versuche > BUDGET.grenze

    def test_bei_der_heutigen_stichprobe_bindet_es(self) -> None:
        from research.stand import BUDGET

        grenze = _fenster(BUCH).budgetgrenze(schiefe=SCHIEFE, woelbung=WOELBUNG)

        assert grenze.versuche < BUDGET.grenze


class TestDerBefehlSagtEsAuch:
    """Die Lehre aus Befund 351: Eine Messung, die nur im Modul existiert,
    erreicht niemanden. Drei Durchgaenge hintereinander war das der Fund."""

    def test_abstand_ruft_den_rand(self) -> None:
        quelle = inspect.getsource(cli.abstand)

        assert "stichprobenrand(" in quelle

    def test_und_nennt_beide_zahlen(self) -> None:
        quelle = inspect.getsource(cli.abstand)

        assert "Der Rand liegt bei" in quelle
        assert "Luft" in quelle

    def test_und_unterscheidet_die_drei_faelle(self) -> None:
        """Kein Weg heute, traegt bis unten, und der Normalfall - genau wie
        bei der Budgetgrenze daneben."""
        quelle = inspect.getsource(cli.abstand)

        assert "Schon bei der heutigen Stichprobe traegt kein Weg" in quelle
        assert "traegt_bis_unten" in quelle


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_die_tabelle(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 388)

        for zahl in ("113", "114", "224", "286", "469"):
            assert zahl in eintrag.ergebnis, zahl

    def test_er_nennt_die_richtung_des_randes(self) -> None:
        """Ohne diesen Satz liest sich 'ein Trade Rand' als Unzuverlaessigkeit,
        und das waere falsch."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 388)

        assert "sichere" in eintrag.ergebnis
        assert "konservativ" in eintrag.ergebnis

    def test_und_387_zeigt_nach_vorn(self) -> None:
        """Die Vorrichtung aus Befund 130: Wer die Zahlen nachschlaegt, soll
        die **letzte** Messung finden."""
        from research.stand import BEHOBEN

        vorher = next(r for r in BEHOBEN if r.befund == 387)

        assert vorher.zuletzt == 388

    def test_der_modulkopf_nennt_die_schaerfere_richtung(self) -> None:
        import research.zielfenster as zf

        text = zf.__doc__ or ""

        assert "224" in text
        assert "231" in text, "die ueberholte Zahl bleibt als Vermerk stehen"
        assert "schaerfere Richtung" in text
