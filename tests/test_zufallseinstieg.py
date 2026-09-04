"""Schlaegt das Timing der Regel den Zufall mit gleicher Haltedauer?

Befund 174 hat gemessen, dass der Holdout 41 % des Vorteils haelt, und
ausdruecklich offengelassen, ob das Koennen ist oder Marktrichtung. Diese
Probe trennt es.

Die Ziehung wird hier an Reihen geprueft, deren Antwort **vorher feststeht**:
eine Reihe mit konstantem Wachstum kann kein Timing belohnen, und eine mit
einem einzigen Sprung schon.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.zufallseinstieg import (
    MINDEST_Z,
    Marktprobe,
    Zufallsbild,
    zufallsverteilung,
    zufallsverteilung_mit_deckeln,
)


def probe(symbol: str, echt: float, null: float, streuung: float) -> Marktprobe:
    return Marktprobe(
        symbol=symbol, rolle="Entwicklung", trades=50,
        echt=echt, null=null, streuung=streuung, perzentil=0.9,
    )


class TestDieZiehung:
    def test_auf_konstantem_wachstum_ist_jeder_einstieg_gleich(self) -> None:
        """**Der Fall, dessen Antwort feststeht.** Waechst die Reihe jeden
        Balken um denselben Faktor, haengt die Rendite nur an der Dauer - alle
        Ziehungen muessen dasselbe liefern."""
        schluss = 100.0 * 1.01 ** np.arange(500)
        dauern = np.full(20, 10)

        werte = zufallsverteilung(
            schluss, dauern, von=0, bis=400, ziehungen=200,
            rng=np.random.default_rng(1),
        )

        assert werte.std() == pytest.approx(0.0, abs=1e-12)
        assert werte.mean() == pytest.approx(1.01**10 - 1.0, rel=1e-9)

    def test_laengere_haltedauer_bringt_mehr_bei_aufwaertsdrift(self) -> None:
        schluss = 100.0 * 1.01 ** np.arange(500)
        kurz = zufallsverteilung(
            schluss, np.full(20, 5), von=0, bis=400, ziehungen=50,
            rng=np.random.default_rng(2),
        )
        lang = zufallsverteilung(
            schluss, np.full(20, 40), von=0, bis=400, ziehungen=50,
            rng=np.random.default_rng(2),
        )

        assert lang.mean() > kurz.mean()

    def test_gezogen_wird_nur_aus_dem_angegebenen_zeitraum(self) -> None:
        """**Sonst verglichen sich verschiedene Marktphasen.**

        Die Reihe steigt in der zweiten Haelfte steil; wer aus der ganzen
        Reihe zieht, bekommt einen anderen Erwartungswert als wer nur aus der
        ersten zieht. Ein Markt, der sich verhundertfacht hat, entscheidet
        darueber alles.
        """
        schluss = np.concatenate(
            [np.full(300, 100.0), 100.0 * 1.02 ** np.arange(200)]
        )
        frueh = zufallsverteilung(
            schluss, np.full(10, 5), von=0, bis=250, ziehungen=100,
            rng=np.random.default_rng(3),
        )
        spaet = zufallsverteilung(
            schluss, np.full(10, 5), von=310, bis=490, ziehungen=100,
            rng=np.random.default_rng(3),
        )

        assert frueh.mean() == pytest.approx(0.0, abs=1e-12)
        assert spaet.mean() > 0.05

    def test_ohne_haltedauern_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="nichts zu ziehen"):
            zufallsverteilung(
                np.ones(10), np.array([]), von=0, bis=5, ziehungen=10,
                rng=np.random.default_rng(4),
            )

    def test_ein_leerer_zeitraum_wird_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="Leerer Zeitraum"):
            zufallsverteilung(
                np.ones(10), np.array([2]), von=5, bis=5, ziehungen=10,
                rng=np.random.default_rng(5),
            )

    def test_eine_haltedauer_unter_einem_balken_ist_keine(self) -> None:
        with pytest.raises(ValueError, match="unter einem Balken"):
            zufallsverteilung(
                np.ones(10), np.array([1, 0]), von=0, bis=8, ziehungen=10,
                rng=np.random.default_rng(6),
            )


class TestDieEinordnung:
    def test_z_ist_der_abstand_in_streuungen(self) -> None:
        assert probe("BTC", 0.09, 0.064, 0.041).z == pytest.approx(0.634, abs=0.001)

    def test_ohne_streuung_gibt_es_kein_z(self) -> None:
        """Auf einer Reihe ohne Struktur ist die Null ein Punkt, kein Band -
        ein Abstand in Streuungen waere dann eine Division durch nichts."""
        p = probe("BTC", 0.09, 0.064, 0.0)

        assert p.z is None
        assert not p.belegt
        assert p.darueber

    def test_belegt_verlangt_die_schwelle(self) -> None:
        assert probe("ETH", 0.136, 0.042, 0.033).belegt
        assert not probe("LTC", 0.039, 0.012, 0.018).belegt
        assert MINDEST_Z == 2.0


class TestDasUrteil:
    #: Der gemessene Fall aus Befund 175.
    GEMESSEN = (
        probe("BTC", 0.08989, 0.06406, 0.04104),
        probe("ETH", 0.13592, 0.04179, 0.03334),
        probe("LTC", 0.03869, 0.01187, 0.01762),
        probe("XRP", 0.03642, 0.01697, 0.02409),
    )

    def test_vier_von_vier_heisst_nicht_bloss_marktrichtung(self) -> None:
        text = Zufallsbild(self.GEMESSEN, korrelation=0.695).urteil()

        assert "4 von 4" in text
        assert "nicht bloss Marktrichtung" in text

    def test_die_schwache_deckung_steht_dabei(self) -> None:
        """**Ohne diesen Satz liest sich "4 von 4" als Beleg.**"""
        text = Zufallsbild(self.GEMESSEN, korrelation=0.695).urteil()

        assert "nur 1 von 4" in text
        assert "die Richtung, nicht der Beleg" in text

    def test_es_wird_kein_gemeinsames_z_gerechnet(self) -> None:
        """**Der Kern der Sache.**

        Vier korrelierte Proben zu einem z zusammenzuziehen gaebe eine Zahl,
        die um einen unbekannten Betrag zu gross ist - und sie saehe
        ueberzeugend aus. Das Modul zaehlt stattdessen.
        """
        text = Zufallsbild(self.GEMESSEN, korrelation=0.695).urteil()

        assert "nicht zu einer zusammenziehen" in text
        assert "0.695" in text

    def test_die_fehlenden_stops_stehen_immer_dabei(self) -> None:
        for korrelation in (None, 0.1, 0.9):
            text = Zufallsbild(self.GEMESSEN, korrelation=korrelation).urteil()

            assert "Obergrenze" in text

    def test_ohne_proben_wird_nichts_behauptet(self) -> None:
        assert "Keine Probe" in Zufallsbild(()).urteil()


def test_die_beiden_nullproben_sind_verschiedene_tests() -> None:
    """**Ich habe sie selbst verwechselt** (Befund 175).

    ``research/nullprobe.py`` mischt die Renditen und prueft die Maschine;
    dieses Modul zieht Einstiege und prueft die Regel. Beim Bauen habe ich das
    erste ueberschrieben und aus dem Index zurueckgeholt. Dieser Test haelt
    fest, dass es beide gibt und dass sie verschiedene Fragen stellen.
    """
    import research.nullprobe as maschine
    import research.zufallseinstieg as regel

    assert hasattr(maschine, "mische_renditen")
    assert hasattr(regel, "zufallsverteilung")
    assert not hasattr(maschine, "zufallsverteilung")
    assert "Maschine" in maschine.__doc__
    assert "Haltedauer" in regel.__doc__


class TestDieNullBekommtDieselbenDeckel:
    """**Befund 200.** Die Huerde war zu niedrig, und der Modulkopf sagte es.

    ``zufallsverteilung`` haelt bis zum Ende der Dauer und steigt zum
    Schlusskurs aus. Die Regel schneidet bei -4 % ab und nimmt bei +80 % mit;
    **42 % ihrer Trades enden am Stop**. Die Null faehrt jeden Einbruch bis
    zum Schluss mit und sieht dadurch schlechter aus, als sie ist.

    Die Tests hier pruefen an Reihen, deren Antwort **vorher feststeht**.
    """

    def reihe(self, werte: list[float]) -> np.ndarray:
        return np.array(werte, dtype=float)

    def test_ein_stop_wird_genommen_wenn_das_tief_ihn_reisst(self) -> None:
        """Schluss steigt, aber das Tief unterschreitet den Stop."""
        schluss = self.reihe([100.0, 101.0, 102.0, 103.0])
        tief = self.reihe([100.0, 95.0, 102.0, 103.0])
        hoch = schluss

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.04, ziel=0.80,
        )

        assert werte[0] == pytest.approx(-0.04)

    def test_ohne_treffer_gilt_der_schlusskurs(self) -> None:
        schluss = self.reihe([100.0, 101.0, 102.0, 103.0])
        tief = self.reihe([100.0, 99.0, 101.0, 102.0])
        hoch = self.reihe([100.0, 102.0, 103.0, 104.0])

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.04, ziel=0.80,
        )

        assert werte[0] == pytest.approx(0.03)

    def test_das_ziel_wird_genommen_wenn_das_hoch_es_erreicht(self) -> None:
        schluss = self.reihe([100.0, 120.0, 150.0, 190.0])
        tief = self.reihe([100.0, 119.0, 149.0, 189.0])
        hoch = self.reihe([100.0, 121.0, 151.0, 191.0])

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.04, ziel=0.80,
        )

        assert werte[0] == pytest.approx(0.80)

    def test_im_gleichen_balken_gilt_der_stop(self) -> None:
        """Die vorsichtige Auslegung - und die des Backtests."""
        schluss = self.reihe([100.0, 150.0])
        tief = self.reihe([100.0, 90.0])
        hoch = self.reihe([100.0, 190.0])

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([1]), von=0, bis=1,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.04, ziel=0.80,
        )

        assert werte[0] == pytest.approx(-0.04)

    def test_der_deckel_hebt_die_null_in_einer_fallenden_reihe(self) -> None:
        """**Der tragende Test.**

        Genau darum geht es: In einer fallenden Reihe verliert die Null ohne
        Stop den vollen Weg, mit Stop nur 4 %. Wer sie ohne Stop misst,
        vergleicht die Regel mit einem Gegner, der schlechter spielt als
        erlaubt.
        """
        n = 400
        schluss = self.reihe([100.0 * (0.99**i) for i in range(n)])
        tief = schluss * 0.995
        hoch = schluss * 1.005
        args = dict(von=0, bis=n - 1, ziehungen=200)

        ohne = zufallsverteilung(
            schluss, np.array([30] * 5), rng=np.random.default_rng(1), **args
        )
        mit = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([30] * 5),
            rng=np.random.default_rng(1), stop=0.04, ziel=0.80, **args
        )

        assert ohne.mean() < -0.20, f"die Reihe muss deutlich fallen: {ohne.mean()}"
        assert mit.mean() == pytest.approx(-0.04, abs=1e-9), (
            "mit Stop darf nichts unter -4 % durchkommen"
        )

    def test_leere_und_unsinnige_eingaben_werden_abgewiesen(self) -> None:
        schluss = self.reihe([100.0, 101.0])
        args = dict(
            von=0, bis=1, ziehungen=1, rng=np.random.default_rng(0),
            stop=0.04, ziel=0.80,
        )

        with pytest.raises(ValueError, match="nichts zu ziehen"):
            zufallsverteilung_mit_deckeln(
                schluss, schluss, schluss, np.array([]), **args
            )
        with pytest.raises(ValueError, match="Abstand"):
            zufallsverteilung_mit_deckeln(
                schluss, schluss, schluss, np.array([1]),
                **{**args, "stop": 0.0}
            )


class TestDerStopIstDerRegler:
    """**Befund 201.** Haengt die Umkehr aus Befund 200 am genauen Abstand?

    Nein: Ueber Stops von 2 % bis 8 % raeumen alle vier Maerkte die Schwelle.
    Auf den echten Reihen faellt das z dabei monoton - **das ist aber eine
    Beobachtung und kein Gesetz**, und mein erster Test hat es als Gesetz
    behauptet und ist an einer gebauten Reihe durchgefallen.

    Der Grund: Ein weiterer Stop wird zwar seltener gerissen, kostet aber
    jedes Mal mehr. Was davon ueberwiegt, haengt an der Reihe.

    Garantiert ist nur die Haelfte davon, und die steht hier.
    """

    def test_ein_weiterer_stop_wird_seltener_gerissen(self) -> None:
        """Die Mechanik, die **immer** gilt - und auf der Befund 200 steht.

        Wird der Stop nie gerissen, steht am Ende der Schlusskurs; wird er
        gerissen, steht dort der Abstand. Ein Ergebnis von genau ``-stop``
        ist also die Spur eines Treffers, und die wird mit dem Abstand
        seltener.
        """
        n = 300
        i = np.arange(n, dtype=float)
        schluss = 100.0 * (1.0 + 0.002 * i) * (1.0 + 0.05 * np.sin(i / 3.0))
        tief = schluss * 0.97
        hoch = schluss * 1.03

        anteile = []
        for s in (0.02, 0.04, 0.08, 0.16):
            werte = zufallsverteilung_mit_deckeln(
                schluss, tief, hoch, np.array([20]),
                von=0, bis=n - 1, ziehungen=400,
                rng=np.random.default_rng(7), stop=s, ziel=0.80,
            )
            anteile.append(float(np.isclose(werte, -s).mean()))

        assert anteile == sorted(anteile, reverse=True), (
            f"ein weiterer Stop muss seltener greifen: {anteile}"
        )
        assert anteile[0] > anteile[-1], "sonst zeigt der Test nichts"

    def test_der_befehl_kennt_den_regler(self) -> None:
        """Sonst waere die Gegenprobe ein Wegwerfskript."""
        from pathlib import Path

        quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()

        assert '"--stop"' in quelle
        assert "eigener if stop <= 0 else stop" in quelle


class TestDieProbeGiltNichtNurDemBestand:
    """**Befund 202.** Warum die sieben Partner im Holdout durchgefallen sind.

    Befund 186 hat gemessen, dass keiner der sieben mehr haelt als der
    Bestand allein - ohne sagen zu koennen, woran es lag. Diese Probe trennt
    Koennen von Marktrichtung, und mit ``--regel`` laesst sie sich auf einen
    Partner anwenden.

    Die beiden Fehler, die dabei herauskamen, stehen hier ebenfalls: Beide
    haetten still falsche Zahlen geliefert.
    """

    def test_der_befehl_kennt_die_regel(self) -> None:
        from pathlib import Path

        quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()

        assert '"--regel"' in quelle
        assert "_katalogregel(regel).model_copy(" in quelle, (
            "ohne die Groessenlogik des Bestands waere es eine andere Regel"
        )

    def test_der_parameter_wird_nicht_ueberschrieben(self) -> None:
        """**Der erste Fehler.**

        Der Entwurf schrieb den gemessenen Abstand in ``stop`` zurueck - den
        Parameter der Befehlszeile. Nach dem ersten Markt war er nicht mehr
        null, und jeder folgende bekam dessen Abstand statt seinen eigenen.
        Bei Regeln mit volatilitaetsskalierten Stops (gemessen: 4,6 % bis
        6,8 % ueber vier Maerkte) ist das keine Kleinigkeit.
        """
        from pathlib import Path

        quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()

        assert "deckel = eigener if stop <= 0 else stop" in quelle
        assert "stop = eigener if stop <= 0 else stop" not in quelle

    def test_die_zusammenfassung_erfindet_keinen_deckel(self) -> None:
        """**Der zweite Fehler.**

        Wo keine Trades am Ziel endeten, gibt es kein Ziel - und die
        Schlusszeile hat es trotzdem formatiert: ``TypeError: unsupported
        format string passed to NoneType.__format__``, nach einem vollen
        Lauf. Jetzt zaehlt sie auf, was gebraucht wurde.
        """
        from pathlib import Path

        quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()

        assert "if s is not None" in quelle
        assert "ohne Ziel" in quelle, "ein fehlendes Ziel wird benannt"
        assert "(Stop {stop:.1%}, Ziel {ziel:.0%})" not in quelle


class TestOhneZielGehtEsAuch:
    """**Befund 203.** Ein fehlendes Ziel darf keinen Markt kosten.

    ``_deckel_der_regel`` liest das Ziel aus den Trades, die am Ziel endeten.
    Wo keiner das tat, gab es kein Ziel - und die ganze Zelle fiel aus. Vier
    von 32 Zellen der Partnertabelle blieben so leer, obwohl das Ziel bei
    +17 % bis +119 % liegt und ohnehin fast nie greift.
    """

    def test_der_stop_allein_genuegt(self) -> None:
        schluss = np.array([100.0, 101.0, 102.0, 103.0])
        tief = np.array([100.0, 95.0, 102.0, 103.0])
        hoch = schluss

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.04,
        )

        assert werte[0] == pytest.approx(-0.04)

    def test_ohne_ziel_wird_kein_gewinn_gedeckelt(self) -> None:
        """Der Lauf muss bis zum Schlusskurs durchlaufen."""
        schluss = np.array([100.0, 150.0, 200.0, 300.0])
        tief = schluss * 0.999
        hoch = schluss * 1.001

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.04,
        )

        assert werte[0] == pytest.approx(2.0)

    def test_ein_negatives_ziel_bleibt_ein_fehler(self) -> None:
        schluss = np.array([100.0, 101.0])
        with pytest.raises(ValueError, match="Ziel"):
            zufallsverteilung_mit_deckeln(
                schluss, schluss, schluss, np.array([1]), von=0, bis=1,
                ziehungen=1, rng=np.random.default_rng(0),
                stop=0.04, ziel=-0.1,
            )


class TestShortRegelnWerdenJetztGemessen:
    """**Befund 204.** Was Befund 203 abweisen musste, wird jetzt gerechnet.

    Befund 203 hat zwei Zeilen zurueckgezogen, weil die Ziehung immer eine
    Long-Rendite rechnete und zwei Regeln short handeln. Die Abweisung war
    richtig und der halbe Schritt: Eine Short-Ziehung spiegelt beides - der
    Stop liegt ueber dem Einstieg und wird vom **Hoch** gerissen, das Ziel
    darunter und vom **Tief** erreicht, und die Rendite dreht das Vorzeichen.
    """

    def test_der_helfer_liest_den_short_stop_richtig(self) -> None:
        """Bei einem Short liegt der Stop ueber dem Einstieg."""
        from cli import _deckel_der_regel

        class FakeShort:
            side = "Sell"
            entry_price = 100.0
            stop_loss = 104.0
            exit_price = 80.0
            exit_reason = "take_profit"

        stop, ziel = _deckel_der_regel([FakeShort()])

        assert stop == pytest.approx(0.04)
        assert ziel == pytest.approx(0.20)

    def test_long_regeln_bleiben_wie_sie_waren(self) -> None:
        from cli import _deckel_der_regel

        class FakeLong:
            side = "Buy"
            entry_price = 100.0
            stop_loss = 96.0
            exit_price = 180.0
            exit_reason = "take_profit"

        stop, ziel = _deckel_der_regel([FakeLong()])

        assert stop == pytest.approx(0.04)
        assert ziel == pytest.approx(0.80)

    def test_ein_short_verdient_am_fallenden_kurs(self) -> None:
        """Ohne Vorzeichen stuende hier das Gegenteil."""
        schluss = np.array([100.0, 90.0, 80.0, 70.0])
        tief = schluss * 0.999
        hoch = schluss * 1.001

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.50,
            seiten=np.array([-1.0]),
        )

        assert werte[0] == pytest.approx(0.30)

    def test_der_short_stop_wird_vom_hoch_gerissen(self) -> None:
        schluss = np.array([100.0, 99.0, 98.0, 97.0])
        tief = schluss * 0.99
        hoch = np.array([100.0, 105.0, 98.0, 97.0])

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.04,
            seiten=np.array([-1.0]),
        )

        assert werte[0] == pytest.approx(-0.04)

    def test_das_short_ziel_wird_vom_tief_erreicht(self) -> None:
        schluss = np.array([100.0, 99.0, 98.0, 97.0])
        tief = np.array([100.0, 79.0, 98.0, 97.0])
        hoch = schluss * 1.001

        werte = zufallsverteilung_mit_deckeln(
            schluss, tief, hoch, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0), stop=0.30, ziel=0.20,
            seiten=np.array([-1.0]),
        )

        assert werte[0] == pytest.approx(0.20)

    def test_die_ungedeckelte_ziehung_spiegelt_ebenfalls(self) -> None:
        """Sonst stuenden die beiden Spalten des Berichts gegeneinander."""
        schluss = np.array([100.0, 90.0, 80.0, 70.0])

        long = zufallsverteilung(
            schluss, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0),
        )
        short = zufallsverteilung(
            schluss, np.array([3]), von=0, bis=3,
            ziehungen=1, rng=np.random.default_rng(0),
            seiten=np.array([-1.0]),
        )

        assert short[0] == pytest.approx(-long[0])

    def test_eine_unsinnige_seite_wird_abgewiesen(self) -> None:
        schluss = np.array([100.0, 101.0])
        with pytest.raises(ValueError, match="\\+1 \\(long\\)"):
            zufallsverteilung(
                schluss, np.array([1]), von=0, bis=1, ziehungen=1,
                rng=np.random.default_rng(0), seiten=np.array([0.0]),
            )

    def test_je_trade_eine_seite(self) -> None:
        schluss = np.array([100.0, 101.0, 102.0])
        with pytest.raises(ValueError, match="je Trade"):
            zufallsverteilung(
                schluss, np.array([1, 1]), von=0, bis=2, ziehungen=1,
                rng=np.random.default_rng(0), seiten=np.array([1.0]),
            )

    def test_der_bericht_reicht_die_seiten_durch(self) -> None:
        from pathlib import Path

        quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()

        assert quelle.count("seiten=np.array(seiten)") == 2, (
            "beide Ziehungen brauchen die Seiten"
        )
        assert "richtung * (float(t.exit_price)" in quelle, (
            "die echte Rendite muss die Seite ebenfalls tragen"
        )


