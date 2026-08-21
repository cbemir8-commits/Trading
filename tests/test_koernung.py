"""Ein bestandenes Gate, das am Kontostand haengt.

Drei Tests tragen diese Datei:

``test_der_rueckgang_haengt_am_konto`` - Der Kern. Dieselbe Strategie, dieselben
Daten, nur ein anderes Startkapital: 9,92 % Rueckgang bei 300 EUR, 12,95 % bei
100.000. Das Gate haelt unterhalb von rund 1.150 EUR und reisst darueber.

``test_beide_gegenproben_treffen_einander`` - Der Beleg fuer die Ursache. Feiner
Mengenschritt bei kleinem Konto und grober Schritt bei grossem sind zwei voellig
verschiedene Eingriffe. Sie landen 0,02 Punkte auseinander und beide 2,3 Punkte
von der Ausgangsmessung entfernt.

``test_die_rendite_wandert_kaum`` - Die Gegenprobe zur bequemen Lesart. Waeren
einfach alle Zahlen kleiner, gaebe es nichts zu erklaeren; die Rendite bewegt
sich aber nur um ein Drittel dessen, was der Rueckgang wandert.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.koernung import (
    FEINMESSUNG,
    GEMESSEN,
    SCHRITTE,
    UNERHEBLICH,
    Koernung,
    Kontostufe,
    baue_gemessen,
    umsetzung,
)


def leiter(**abweichung) -> Koernung:
    daten = {
        "stufen": list(GEMESSEN),
        "grenze_pct": 12.0,
        "feinmessung": FEINMESSUNG,
    }
    daten.update(abweichung)
    return Koernung(**daten)


class TestAbhaengigkeit:
    def test_der_rueckgang_haengt_am_konto(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Der Kandidat ist in jeder Sprosse derselbe. Bewegt sich die Zahl
        trotzdem um drei Punkte, misst das Gate zu einem Teil den Kontostand
        und nicht die Strategie.
        """
        k = leiter()

        assert k.genug
        assert k.spanne == pytest.approx(12.95 - 9.92, abs=0.01)
        assert k.steigt_durchgehend, "kein Rauschen, sondern ein Verlauf"
        assert k.grenzkapital == pytest.approx(1154, abs=25)
        urteil = k.urteil()
        assert "haengt am Kontostand" in urteil
        assert "reisst es" in urteil

    def test_das_gate_kippt_zwischen_zwei_gemessenen_sprossen(self) -> None:
        """1.000 EUR haelt mit 11,84 %, 1.500 EUR reisst mit 12,36 %."""
        k = leiter()
        gehalten = [s for s in k.geordnet if s.haelt(12.0)]
        gerissen = [s for s in k.geordnet if not s.haelt(12.0)]

        assert gehalten[-1].kapital == 1000.0
        assert gerissen[0].kapital == 1500.0
        assert gehalten[-1].kapital < k.grenzkapital < gerissen[0].kapital

    def test_die_rendite_wandert_kaum(self) -> None:
        """**Die Gegenprobe zur bequemen Lesart.**

        "Kleines Konto, kleine Zahlen" waere die naheliegende Erklaerung und
        haette nichts zu bedeuten. Sie stimmt nicht: Der Rueckgang wandert
        3,03 Punkte, die Rendite 1,28.
        """
        k = leiter()

        assert k.renditespanne == pytest.approx(1.28, abs=0.02)
        assert k.spanne > 2 * k.renditespanne
        assert "nicht einfach kleinere Positionen" in k.urteil()

    def test_ein_unbeeinflusstes_gate_wird_nicht_angeschwaerzt(self) -> None:
        """Gegenprobe: Bewegt sich der Rueckgang nicht, behauptet das Urteil
        auch keine Abhaengigkeit."""
        flach = leiter(
            stufen=[
                Kontostufe(k, 13.5, 10.6, 152)
                for k in (500.0, 5000.0, 50000.0)
            ],
            feinmessung=None,
        )

        assert flach.spanne < UNERHEBLICH
        assert "haengt nicht am Konto" in flach.urteil()
        assert "reisst" not in flach.urteil()


class TestGegenproben:
    def test_beide_gegenproben_treffen_einander(self) -> None:
        """**Der Beleg fuer die Ursache.**

        Ein feiner Mengenschritt bei 500 EUR und Bybits grober Schritt bei
        100.000 EUR haben nichts miteinander gemein ausser dem, was sie
        beseitigen. Landen sie auf derselben Zahl, ist die Rundung nicht
        eine Erklaerung unter mehreren.
        """
        k = leiter()

        assert abs(FEINMESSUNG.rueckgang - k.grenzwert) < UNERHEBLICH
        assert k.koernung_erklaert_es
        assert k.anteil_erklaert == pytest.approx(1.0, abs=0.05)
        assert "ist die Ursache" in k.urteil()

    def test_die_feinmessung_wird_gegen_ihr_eigenes_konto_gerechnet(self) -> None:
        """Gegen die kleinste Sprosse stuende im Zaehler zusaetzlich der
        Kontounterschied - und der Anteil waere eine andere Groesse."""
        k = leiter()

        assert k.gegenstueck is not None
        assert k.gegenstueck.kapital == FEINMESSUNG.kapital
        assert k.gegenstueck.rueckgang == pytest.approx(10.64)

    def test_ohne_treffer_wird_nichts_behauptet(self) -> None:
        """Landen die beiden Eingriffe woanders, wirkt noch etwas anderes
        mit - und dann sagt das Urteil genau das."""
        daneben = leiter(feinmessung=Kontostufe(500.0, 13.5, 11.20, 152))

        assert not daneben.koernung_erklaert_es
        assert "treffen einander nicht" in daneben.urteil()
        assert "ist die Ursache" not in daneben.urteil()

    def test_ohne_gegenprobe_bleibt_der_absatz_weg(self) -> None:
        ohne = leiter(feinmessung=None)

        assert ohne.anteil_erklaert is None
        assert not ohne.koernung_erklaert_es
        assert "feinen" not in ohne.urteil()
        assert "haengt am Kontostand" in ohne.urteil()


class TestUmsetzung:
    def test_grosse_positionen_verlieren_nichts(self) -> None:
        """Bei 50.000 EUR ist ein Mengenschritt ein Tausendstel der Position."""
        preise = np.full(200, 60000.0)
        anteile = np.full(200, 0.38)

        assert umsetzung(
            anteile, preise, kapital=50000.0, schritt=SCHRITTE["BTCUSDT"]
        ) > 0.995

    def test_kleine_positionen_verlieren_spuerbar(self) -> None:
        """**Die Zahl hinter dem ganzen Befund.** 0,38 mal 500 durch 60.000
        sind 0,00317 BTC; abgerundet auf 0,003 bleiben 94,7 %."""
        preise = np.full(200, 60000.0)
        anteile = np.full(200, 0.38)

        assert umsetzung(
            anteile, preise, kapital=500.0, schritt=SCHRITTE["BTCUSDT"]
        ) == pytest.approx(0.003 / 0.0031667, abs=0.002)

    def test_ein_kleinerer_anteil_wird_staerker_verstuemmelt(self) -> None:
        """Und genau das passiert im Sturm: Das Vola-Ziel senkt den Anteil,
        und kleine Positionen trifft das Abrunden am haertesten."""
        preise = np.full(200, 60000.0)
        ruhig = umsetzung(
            np.full(200, 0.50), preise, kapital=500.0, schritt=SCHRITTE["BTCUSDT"]
        )
        sturm = umsetzung(
            np.full(200, 0.20), preise, kapital=500.0, schritt=SCHRITTE["BTCUSDT"]
        )

        assert sturm < ruhig

    def test_unsinnige_eingaben_kippen_nicht(self) -> None:
        assert umsetzung([], [], kapital=500.0, schritt=0.001) == 0.0
        assert umsetzung([0.3], [1.0, 2.0], kapital=500.0, schritt=0.001) == 0.0
        assert umsetzung([0.3], [60000.0], kapital=500.0, schritt=0.0) == 0.0
        assert umsetzung([0.3], [60000.0], kapital=0.0, schritt=0.001) == 0.0


class TestRand:
    def test_zu_wenige_sprossen_sagen_nichts(self) -> None:
        duenn = Koernung(stufen=list(GEMESSEN[:2]))

        assert not duenn.genug
        assert "nichts sagen" in duenn.urteil()
        assert duenn.grenzkapital is None

    def test_eine_leiter_ohne_uebergang_behauptet_keinen(self) -> None:
        """Alle Sprossen halten - dann ist der Uebergang nicht gemessen."""
        klein = Koernung(
            stufen=[Kontostufe(k, 13.0, 9.0 + i * 0.1, 152)
                    for i, k in enumerate((300.0, 400.0, 500.0))]
        )

        assert klein.grenzkapital is None
        assert "haelt nur unterhalb" not in klein.urteil()

    def test_die_gemessene_leiter_ist_die_aus_dem_bericht(self) -> None:
        gebaut = baue_gemessen()

        assert len(gebaut.stufen) == len(GEMESSEN)
        assert gebaut.feinmessung == FEINMESSUNG
        assert gebaut.grenze_pct == 12.0

    def test_die_grenze_stimmt_mit_dem_gate_ueberein(self) -> None:
        """Eine andere Schwelle einzuordnen als die, die geprueft wird, hiesse
        etwas anderes zu beantworten."""
        from research.gates import GateThresholds

        assert baue_gemessen().grenze_pct == GateThresholds().max_oos_drawdown_pct

    def test_die_tabelle_nennt_beide_urteile(self) -> None:
        text = leiter().tabelle()

        assert "haelt" in text and "reisst" in text
        assert "feiner Schritt" in text
        assert "10.64" in text and "12.95" in text
