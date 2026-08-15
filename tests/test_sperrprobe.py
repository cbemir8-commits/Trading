"""Die Kontrolle zu Befund 58 - und warum sie streng bleiben muss.

Das Schock-Overlay hat 13 von 165 Einstiegen entfernt und zwei Gates gekippt.
Es gibt eine zweite Erklaerung fuer dieselben Zahlen: **Weniger Trades sind
manchmal einfach besser.** Diese Datei prueft, dass die Kontrolle den
Unterschied auch wirklich findet.

Der Test, der sie traegt, ist ``test_ein_zufallstreffer_besteht_nicht``: Eine
Kontrolle, die alles durchwinkt, ist keine.
"""

from __future__ import annotations

import numpy as np

from research.sperrprobe import Ergebnis, Sperrprobe, ziehe_signale


def ergebnis(
    *, bestanden: int = 7, rueckgang: float = 10.6, jahr: float = -10.3,
    qualitaet: float = 0.2569,
) -> Ergebnis:
    return Ergebnis(
        trades=150, rueckgang_pct=rueckgang, schlechtestes_jahr_pct=jahr,
        sharpe_je_trade=qualitaet, dsr=0.79, bestanden=bestanden, gesamt=11,
    )


class TestZiehen:
    def test_je_bein_die_vorgegebene_anzahl(self) -> None:
        """Das Overlay trifft ungleich - 6 in BTC, 7 in ETH. Eine Null, die
        anders verteilt ist, misst die Verteilung mit."""
        signale = {
            "BTC": np.zeros(100, dtype=bool),
            "ETH": np.zeros(100, dtype=bool),
        }
        signale["BTC"][::4] = True
        signale["ETH"][::5] = True

        gezogen = ziehe_signale(signale, {"BTC": 6, "ETH": 7}, saat=1)

        assert gezogen["BTC"].sum() == 6
        assert gezogen["ETH"].sum() == 7

    def test_es_werden_nur_signalkerzen_gesperrt(self) -> None:
        """Eine Kerze ohne Signal zu sperren kostet nichts und verwaesserte
        die Null - sie waere dann milder als die Messung."""
        treffer = np.zeros(50, dtype=bool)
        treffer[[3, 10, 22, 41]] = True

        gezogen = ziehe_signale({"a": treffer}, {"a": 3}, saat=5)

        assert set(np.flatnonzero(gezogen["a"])) <= {3, 10, 22, 41}

    def test_mehr_als_vorhanden_geht_nicht_schief(self) -> None:
        treffer = np.zeros(20, dtype=bool)
        treffer[[1, 2]] = True

        assert ziehe_signale({"a": treffer}, {"a": 9}, saat=0)["a"].sum() == 2

    def test_dieselbe_saat_zieht_dasselbe(self) -> None:
        treffer = np.zeros(100, dtype=bool)
        treffer[::3] = True

        a = ziehe_signale({"x": treffer}, {"x": 8}, saat=42)["x"]
        b = ziehe_signale({"x": treffer}, {"x": 8}, saat=42)["x"]

        assert np.array_equal(a, b)


class TestUrteil:
    def test_ein_echter_effekt_besteht(self) -> None:
        probe = Sperrprobe(
            echt=ergebnis(bestanden=9),
            zufall=[ergebnis(bestanden=7) for _ in range(100)],
        )

        assert probe.p_gates == 0.0
        assert probe.besteht
        assert "mehr als blosses Streichen" in probe.urteil()

    def test_ein_zufallstreffer_besteht_nicht(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Wenn ein Drittel der zufaelligen Sperren dieselbe Zahl Gates haelt,
        war es nicht die Auswahl, sondern das Streichen. Eine Kontrolle, die
        das durchwinkt, ist keine.
        """
        zufall = [ergebnis(bestanden=9) for _ in range(33)]
        zufall += [ergebnis(bestanden=7) for _ in range(67)]
        probe = Sperrprobe(echt=ergebnis(bestanden=9), zufall=zufall)

        assert probe.p_gates == 0.33
        assert not probe.besteht
        assert "haelt der Kontrolle nicht stand" in probe.urteil()

    def test_knapp_ueber_der_schwelle_reicht_nicht(self) -> None:
        zufall = [ergebnis(bestanden=9) for _ in range(6)]
        zufall += [ergebnis(bestanden=7) for _ in range(94)]

        assert not Sperrprobe(echt=ergebnis(bestanden=9), zufall=zufall).besteht

    def test_das_urteil_haengt_nur_an_den_gates(self) -> None:
        """Wer vier Kennzahlen prueft und die beste nimmt, findet fast immer
        eine. Entschieden wird deshalb an einer, und sie steht vorher fest."""
        zufall = [
            ergebnis(bestanden=9, rueckgang=99.0, jahr=-99.0, qualitaet=0.0)
            for _ in range(50)
        ]
        zufall += [ergebnis(bestanden=7) for _ in range(50)]
        probe = Sperrprobe(echt=ergebnis(bestanden=9), zufall=zufall)

        assert probe.p_rueckgang == 0.5, "Beim Rueckgang saehe es gut aus"
        assert probe.p_qualitaet == 0.5
        assert not probe.besteht, "Entschieden wird trotzdem an den Gates"

    def test_ohne_ziehungen_wird_nichts_behauptet(self) -> None:
        probe = Sperrprobe(echt=ergebnis())

        assert not probe.besteht
        assert "nichts zu sagen" in probe.urteil()
        assert "nichts zu vergleichen" in probe.bericht()


class TestBericht:
    def test_er_zeigt_gemessen_und_zufall_nebeneinander(self) -> None:
        probe = Sperrprobe(
            echt=ergebnis(bestanden=9, rueckgang=9.66),
            zufall=[ergebnis(bestanden=7, rueckgang=10.5) for _ in range(20)],
        )
        text = probe.bericht()

        assert "9/11" in text
        assert "9.66" in text
        assert "Schlechtestes Jahr" in text
        assert "Sharpe je Trade" in text

    def test_kleiner_rueckgang_gilt_als_besser(self) -> None:
        """Bei allen anderen Kennzahlen ist gross besser, hier klein - wer das
        verwechselt, bekommt das Vorzeichen des Urteils falsch."""
        probe = Sperrprobe(
            echt=ergebnis(rueckgang=9.0),
            zufall=[ergebnis(rueckgang=12.0) for _ in range(10)],
        )

        assert probe.p_rueckgang == 0.0
