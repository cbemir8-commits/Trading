"""Effektive statt roher Stichprobe - und die Korrektur an der Korrektur.

Zwei Tests tragen diese Datei:

* ``test_drei_gleiche_beine_werden_gekuerzt`` - das Loch, um das es geht. Wer
  eine Position in drei fast gleiche Teile zerlegt, verdreifacht die
  Trade-Zahl und weiss keinen Deut mehr.
* ``test_unabhaengige_bloecke_werden_nicht_gekuerzt`` - der Gegenpol, und der
  Grund, warum die erste Fassung falsch war. Bei dreissig Bloecken ungleicher
  Groesse kuerzt jeder Schaetzer auch reines Rauschen; ohne Permutationsnull
  waere aus dem Zufall eine Strafe geworden.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from core.models import Side, Trade
from research.unabhaengigkeit import (
    MIND_BLOECKE,
    SIGNIFIKANZ,
    Effektivwert,
    designeffekt,
    effektive_stichprobe,
    mittlere_korrelation,
)


def reihe(n: int = 30, saat: int = 1) -> list[float]:
    return list(np.random.default_rng(saat).normal(5.0, 20.0, n))


def unabhaengige_bloecke(
    anzahl: int = 30, *, saat: int = 3, groessen: list[int] | None = None
) -> list[list[float]]:
    """Bloecke ohne jede Abhaengigkeit - aber mit ungleichen Groessen.

    Die ungleichen Groessen sind Absicht: Genau sie ziehen jeden Schaetzer
    nach unten, auch wenn nichts zusammenhaengt.
    """
    rng = np.random.default_rng(saat)
    gr = groessen or list(rng.integers(1, 12, anzahl))
    return [list(rng.normal(3.0, 12.0, int(g))) for g in gr]


def handelsreihe(anzahl: int, *, saat: int = 4) -> list[Trade]:
    rng = np.random.default_rng(saat)
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Trade(
            trade_id=f"t{i}",
            symbol="BTCUSDT",
            side=Side.BUY,
            strategy_id="test",
            entry_time=t0 + timedelta(hours=4 * i),
            entry_price=Decimal("100000"),
            exit_time=t0 + timedelta(hours=4 * i + 2),
            exit_price=Decimal("100000"),
            qty=Decimal("0.006"),
            gross_pnl=Decimal(str(round(float(rng.normal(3.0, 12.0)), 2))),
            fees=Decimal("0.24"),
            stop_loss=Decimal("99400"),
        )
        for i in range(anzahl)
    ]


class TestDesigneffekt:
    def test_unabhaengige_bloecke_werden_nicht_gekuerzt(self) -> None:
        """**Der Test, der die erste Fassung widerlegt hat.**

        Ungleiche Blockgroessen allein liessen den Bootstrap auf 78 von 154
        fallen - ohne dass irgendetwas zusammenhing. Ohne Permutationsnull
        waere daraus eine Strafe geworden.
        """
        e = designeffekt(unabhaengige_bloecke())

        assert e is not None
        assert not e.nachgewiesen
        assert e.effektiv == e.roh
        assert e.p_wert > SIGNIFIKANZ

    def test_drei_gleiche_beine_werden_gekuerzt(self) -> None:
        """**Das Loch, um das es geht.**

        Jeder Block besteht aus identischen Werten - drei Kopien derselben
        Beobachtung sind eine Beobachtung.
        """
        rng = np.random.default_rng(5)
        bloecke = [[float(w)] * 5 for w in rng.normal(3.0, 12.0, 30)]

        e = designeffekt(bloecke)

        assert e is not None
        assert e.nachgewiesen
        assert e.p_wert <= SIGNIFIKANZ
        assert e.effektiv < e.roh * 0.5, f"Erwartet rund 30, gemessen {e.effektiv}"

    def test_teilweise_abhaengig_liegt_dazwischen(self) -> None:
        """Schwacher gemeinsamer Anteil je Block - nachweisbar, aber nicht
        vernichtend."""
        rng = np.random.default_rng(8)
        bloecke = []
        for _ in range(40):
            gemeinsam = float(rng.normal(0, 4))
            bloecke.append([gemeinsam + float(rng.normal(0, 12)) for _ in range(5)])

        e = designeffekt(bloecke)

        assert e is not None
        assert e.nachgewiesen
        assert e.roh * 0.4 < e.effektiv < e.roh

    def test_zu_wenige_bloecke(self) -> None:
        assert designeffekt([[1.0, 2.0]] * 3) is None

    def test_ergebnis_ist_reproduzierbar(self) -> None:
        """Eine Groesse, die ueber Zulassung entscheidet, darf nicht bei jedem
        Aufruf anders ausfallen."""
        bloecke = unabhaengige_bloecke(saat=12)

        a, b = designeffekt(bloecke), designeffekt(bloecke)

        assert a is not None and b is not None
        assert a.effektiv == b.effektiv
        assert a.p_wert == b.p_wert

    def test_effektiv_nie_ueber_roh(self) -> None:
        for saat in range(6):
            e = designeffekt(unabhaengige_bloecke(saat=saat))
            assert e is not None and e.effektiv <= e.roh


class TestEffektiveStichprobe:
    def test_ohne_bloecke_bleibt_alles_wie_es_war(self) -> None:
        """Eine Korrektur ohne Messung waere genau der Fehler, den dieses
        Modul verhindern soll."""
        assert effektive_stichprobe(154).effektiv == 154
        assert effektive_stichprobe(154, {"a": reihe(31)}).effektiv == 154
        assert effektive_stichprobe(154, None, []).effektiv == 154

    def test_teilweise_bloecke_veraendern_die_zahl_nicht(self) -> None:
        """**Der Entwurfsfehler, den ein Test aufgedeckt hat.**

        Die Funktion ersetzte die Trade-Zahl durch die Summe der Bloecke.
        Decken die Bloecke nur einen Teil ab, schoebe das still eine ganz
        andere Stichprobengroesse ins Gate. Uebernommen wird deshalb der
        Faktor, nicht die Summe.
        """
        e = effektive_stichprobe(154, None, unabhaengige_bloecke(saat=21))

        assert e.roh == 154
        assert e.effektiv == 154

    def test_bericht_bei_nachweis(self) -> None:
        rng = np.random.default_rng(5)
        bloecke = [[float(w)] * 5 for w in rng.normal(3.0, 12.0, 30)]

        text = effektive_stichprobe(150, None, bloecke).bericht()

        assert "unabhaengigen" in text
        assert "ICC" in text

    def test_bericht_ohne_nachweis_nennt_die_grenze(self) -> None:
        """Kein Nachweis heisst nicht 'keine Abhaengigkeit'."""
        text = effektive_stichprobe(154, None, unabhaengige_bloecke()).bericht()

        assert "keine messbare Abhaengigkeit" in text
        assert "Das heisst nicht, dass keine da ist" in text


class TestKnappeEntscheidung:
    """**Die dritte Schwaeche dieses Moduls - und die unangenehmste.**

    Die Schwelle ist hart, die Groesse darunter stetig. Beim Abtasten des
    Vola-Reglers ergab derselbe Kandidat auf denselben Daten einen ICC von
    0,120 bis 0,128 - praktisch konstant - aber p-Werte von 0,030 bis 0,085.
    Bei der einen Stufe unter 0,05 fiel die Stichprobe von 153 auf 100 und der
    Deflated Sharpe von 0,87 auf 0,53.
    """

    def test_knapp_darunter_wird_angesagt(self) -> None:
        e = Effektivwert(roh=153, effektiv=100, icc=0.128, p_wert=0.030,
                         nachgewiesen=True, bloecke=31)

        assert e.knapp
        assert "Graubereich" in e.bericht()
        assert "nicht ueber die Strategie" in e.bericht()

    def test_knapp_darueber_ebenso(self) -> None:
        """Knapp verfehlt ist genauso wenig eine Messung wie knapp erreicht."""
        e = Effektivwert(roh=154, effektiv=154, icc=0.121, p_wert=0.060,
                         nachgewiesen=False, bloecke=31)

        assert e.knapp
        assert "Graubereich" in e.bericht()

    def test_eindeutig_wird_nicht_angesagt(self) -> None:
        for p in (0.001, 0.5, 0.9):
            e = Effektivwert(roh=150, effektiv=150, icc=0.05, p_wert=p, bloecke=31)
            assert not e.knapp, f"p={p} ist nicht knapp"
            assert "Graubereich" not in e.bericht()

    def test_ohne_genug_bloecke_keine_ansage(self) -> None:
        """Wo gar keine Aussage moeglich ist, ist auch keine knapp."""
        e = Effektivwert(roh=20, effektiv=20, p_wert=0.05, bloecke=3)

        assert not e.knapp

    def test_mehr_permutationen_gegen_das_rauschen(self) -> None:
        """200 Ziehungen geben nahe 5 % einen Standardfehler von rund 0,015 -
        die Schwelle liegt innerhalb eines einzigen davon."""
        from research.unabhaengigkeit import PERMUTATIONEN

        assert PERMUTATIONEN >= 2000


class TestMittlereKorrelation:
    def test_identische_beine_geben_eins(self) -> None:
        r = reihe()

        assert mittlere_korrelation({"a": r, "b": list(r)}) == pytest.approx(1.0)

    def test_negative_korrelation_wird_bei_null_gekappt(self) -> None:
        r = reihe(100)

        assert mittlere_korrelation({"a": r, "b": [-x for x in r]}) == 0.0

    def test_zu_kurze_reihen_werden_uebergangen(self) -> None:
        assert mittlere_korrelation({"a": [1.0, 2.0], "b": [1.0, 3.0]}) == 0.0


class TestGateNutzung:
    def test_gate_kuerzt_bei_nachgewiesener_abhaengigkeit(self) -> None:
        from research.gates import GateThresholds, gate_deflated_sharpe

        trades = handelsreihe(150)
        t = GateThresholds()
        rng = np.random.default_rng(5)
        abhaengig = [[float(w)] * 5 for w in rng.normal(3.0, 12.0, 30)]

        ohne = gate_deflated_sharpe(trades, 96, t, None, None)
        mit = gate_deflated_sharpe(trades, 96, t, None, abhaengig)

        assert mit.value < ohne.value

    def test_gate_kuerzt_nicht_ohne_nachweis(self) -> None:
        """Der Spitzenkandidat darf nicht fuer Rauschen bestraft werden."""
        from research.gates import GateThresholds, gate_deflated_sharpe

        trades = handelsreihe(150)
        t = GateThresholds()

        # Bloecke, die genau diese 150 Trades abdecken - unabhaengig verteilt.
        werte = [float(x.net_pnl) for x in trades]
        bloecke, i = [], 0
        for groesse in [3, 7, 2, 9, 5, 4, 11, 6, 8, 1] * 3:
            if i >= len(werte):
                break
            bloecke.append(werte[i : i + groesse])
            i += groesse

        ohne = gate_deflated_sharpe(trades, 96, t, None, None)
        mit = gate_deflated_sharpe(trades, 96, t, None, bloecke)

        assert mit.value == pytest.approx(ohne.value)

    def test_report_traegt_die_beine(self) -> None:
        from backtest.walkforward import WalkForwardReport

        assert isinstance(WalkForwardReport().beine, dict)


def test_schwellen_sind_festgehalten() -> None:
    assert MIND_BLOECKE == 8
    assert SIGNIFIKANZ == 0.05


class TestMehrBeineMehrTradesGleicheInformation:
    """**Die gemessene Form, um die es geht.**

    Auf echten Daten, derselbe Kandidat, nur mehr Maerkte:

        Kombination        roh   effektiv    ICC       p   SR/Trade
        BTC+ETH            152        152  0,112   0,072     0,2597
        BTC+ETH+XRP        260        146  0,105   0,021     0,2006
        BTC+ETH+LTC+XRP    366        151  0,132   0,001     0,1757

    Die rohe Zahl waechst um das Zweieinhalbfache, die **unabhaengige** bleibt
    bei rund 150. Genau dafuer ist dieses Modul da: Wer korrelierte Maerkte
    dazunimmt, bekommt mehr Trades und nicht mehr Information.
    """

    def test_doppelte_beine_verdoppeln_die_stichprobe_nicht(self) -> None:
        rng = np.random.default_rng(17)

        # Ein gemeinsamer Marktfaktor je Fenster, dazu etwas Eigenleben -
        # so sehen zwei Kryptomaerkte in denselben Fenstern aus.
        einzeln, doppelt = [], []
        for _ in range(31):
            gemeinsam = float(rng.normal(0, 9))
            a = [gemeinsam + float(rng.normal(0, 6)) for _ in range(5)]
            b = [gemeinsam + float(rng.normal(0, 6)) for _ in range(5)]
            einzeln.append(a)
            doppelt.append(a + b)

        ein_bein = effektive_stichprobe(sum(len(x) for x in einzeln), None, einzeln)
        zwei_beine = effektive_stichprobe(sum(len(x) for x in doppelt), None, doppelt)

        assert zwei_beine.roh == 2 * ein_bein.roh
        assert zwei_beine.effektiv < 1.5 * ein_bein.effektiv, (
            f"Rohe Zahl verdoppelt ({ein_bein.roh} -> {zwei_beine.roh}), "
            f"effektive von {ein_bein.effektiv} auf {zwei_beine.effektiv}"
        )

    def test_die_abhaengigkeit_wird_mit_mehr_beinen_deutlicher(self) -> None:
        """p faellt von 0,072 auf 0,001, wenn Beine dazukommen - kein
        Grenzfall mehr, sondern eindeutig."""
        rng = np.random.default_rng(23)
        bloecke = []
        for _ in range(31):
            gemeinsam = float(rng.normal(0, 9))
            bloecke.append([gemeinsam + float(rng.normal(0, 6)) for _ in range(15)])

        e = designeffekt(bloecke)

        assert e is not None
        assert e.nachgewiesen
        assert e.p_wert < 0.01


class TestStetigeKuerzung:
    """**Die Klippe ist weg - und das ist die Eigenschaft, die zaehlt.**

    Frueher entschied ``p <= 0,05`` binaer ueber die Kuerzung. Ueber einen
    ganzen Regler hinweg sah das so aus:

        Faktor   roh   effektiv    ICC       p    Deflated Sharpe
           0,6   226        151  0,079   0,040              0,467
           0,8   175        115  0,109   0,049              0,344
           1,0   152        152  0,112   0,072              0,851
          1,25   132         81  0,187   0,040              0,071

    Der ICC steigt glatt, der p-Wert wandert ueber die Schwelle, und die
    Stichprobe springt. Mit stetiger Kuerzung folgt sie dem ICC:

        ICC    0,053   0,079   0,112   0,187   0,375   0,629
        bleibt  100 %    98 %   100 %    97 %    80 %    68 %
    """

    def test_unabhaengige_daten_bleiben_fast_immer_ungekuerzt(self) -> None:
        """**Die Gegenprobe an bekannter Null.**

        Kalibriert wird am 95. Perzentil - also darf hoechstens jede zwanzigste
        saubere Messung ueberhaupt gekuerzt werden, und dann knapp. Am Median
        kalibriert waere es die Haelfte, und genau deshalb brauchte die alte
        Fassung eine Schwelle davor.
        """
        faktoren = []
        for saat in range(20):
            rng = np.random.default_rng(1000 + saat)
            groessen = rng.integers(1, 12, 30)
            bloecke = [list(rng.normal(3.0, 12.0, int(g))) for g in groessen]
            e = designeffekt(bloecke, permutationen=400)
            if e is not None:
                faktoren.append(e.faktor)

        werte = np.array(faktoren)

        assert len(werte) >= 15
        assert werte.mean() > 0.95, f"im Mittel bleiben nur {werte.mean():.1%}"
        assert werte.min() > 0.7, f"schlimmster Fall {werte.min():.1%}"

    def test_staerkere_abhaengigkeit_kuerzt_staerker(self) -> None:
        """Monoton statt sprunghaft: Mehr gemeinsamer Anteil, mehr Kuerzung."""
        faktoren = []
        for gemeinsam_sd in (1.0, 6.0, 14.0):
            rng = np.random.default_rng(77)
            bloecke = []
            for _ in range(30):
                gemeinsam = float(rng.normal(0, gemeinsam_sd))
                bloecke.append(
                    [gemeinsam + float(rng.normal(0, 10)) for _ in range(6)]
                )
            e = designeffekt(bloecke, permutationen=400)
            assert e is not None
            faktoren.append(e.faktor)

        assert faktoren[0] >= faktoren[1] >= faktoren[2], faktoren
        assert faktoren[0] > faktoren[2], "keine Wirkung ueber die ganze Spanne"

    def test_keine_schwelle_mehr_im_code(self) -> None:
        """**Umkehr-Nachweis.**

        Faellt dieser Test um, ist die Klippe zurueck - und mit ihr die
        Sprunghaftigkeit, die drei Berichte verdorben hat.
        """
        import inspect

        from research import unabhaengigkeit

        quelle = inspect.getsource(unabhaengigkeit.designeffekt)

        assert "quantile" in quelle
        assert "if nachgewiesen" not in quelle


class TestStrengsteEinteilung:
    """**Abhaengigkeit hat mehr als eine Gestalt, und keine ist die richtige.**

        nach Kalenderfenstern   Trades desselben Quartals aehneln sich
        nach Gleichzeitigkeit   Positionen, die zugleich offen waren

    Bis hierher entschied allein die erste, ohne dass irgendwo stuende, warum.
    Das Monte-Carlo-Gate haelt dagegen laengst die gleichzeitigen Trades
    zusammen - zwei Vorstellungen im selben Gate-System, und die schaerfere
    blieb ungenutzt.
    """

    def _abhaengig(self, *, bloecke: int = 20, je: int = 6) -> list[list[float]]:
        """Bloecke mit deutlichem gemeinsamem Anteil - Abhaengigkeit, die man
        finden **soll**."""
        rng = np.random.default_rng(4)
        return [
            list(rng.normal(rng.normal(0, 3.0), 0.3, je)) for _ in range(bloecke)
        ]

    def _unabhaengig(self, *, bloecke: int = 20, je: int = 6) -> list[list[float]]:
        rng = np.random.default_rng(9)
        return [list(rng.normal(0, 1.0, je)) for _ in range(bloecke)]

    def test_die_strengere_einteilung_gewinnt(self) -> None:
        locker = self._unabhaengig()
        streng = self._abhaengig()
        n = sum(len(b) for b in locker)

        nur_locker = effektive_stichprobe(n, None, locker)
        mit_streng = effektive_stichprobe(n, None, locker, weitere=[streng])

        assert nur_locker.effektiv == n, "Die lockere Einteilung kuerzt nicht"
        assert mit_streng.effektiv < nur_locker.effektiv

    def test_die_reihenfolge_ist_gleichgueltig(self) -> None:
        """Sonst haenge das Ergebnis daran, welche Einteilung zuerst genannt
        wird - und damit an nichts."""
        locker = self._unabhaengig()
        streng = self._abhaengig()
        n = sum(len(b) for b in locker)

        herum = effektive_stichprobe(n, None, streng, weitere=[locker])
        zurueck = effektive_stichprobe(n, None, locker, weitere=[streng])

        assert herum.effektiv == zurueck.effektiv

    def test_ohne_zusatz_bleibt_alles_wie_vorher(self) -> None:
        """Der alte Weg muss unveraendert bleiben - jede Zahl des Projekts
        haengt daran."""
        bloecke = self._abhaengig()
        n = sum(len(b) for b in bloecke)

        assert (
            effektive_stichprobe(n, None, bloecke).effektiv
            == effektive_stichprobe(n, None, bloecke, weitere=[]).effektiv
        )

    def test_leere_einteilungen_stoeren_nicht(self) -> None:
        bloecke = self._abhaengig()
        n = sum(len(b) for b in bloecke)

        assert (
            effektive_stichprobe(n, None, bloecke, weitere=[[], [[]]]).effektiv
            == effektive_stichprobe(n, None, bloecke).effektiv
        )

    def test_ohne_jede_einteilung_wird_nicht_gekuerzt(self) -> None:
        assert effektive_stichprobe(100, None, None, weitere=[]).effektiv == 100

    def test_verglichen_wird_der_faktor_nicht_die_summe(self) -> None:
        """Zwei Einteilungen koennen verschieden viele Trades abdecken. Dann
        waere die kleinere Summe kein Zeichen groesserer Strenge, sondern nur
        eine kuerzere Liste."""
        streng_klein = self._abhaengig(bloecke=10, je=4)
        locker_gross = self._unabhaengig(bloecke=30, je=6)
        n = sum(len(b) for b in locker_gross)

        ergebnis = effektive_stichprobe(n, None, locker_gross, weitere=[streng_klein])

        assert ergebnis.effektiv < n
