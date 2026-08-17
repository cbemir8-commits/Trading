"""Liegen ganze Regelfamilien anders - und was das kostet.

Zwei Tests tragen diese Datei:

``test_die_trennung_haelt_der_permutation_stand`` - Die Familien wurden
zugeordnet, **nachdem** die Werte bekannt waren. Ohne Gegenprobe waere das der
klassische Weg, ein Muster in Rauschen zu finden.

``test_qualitaet_faehrt_auf_aehnlichkeit`` - Die unangenehme Haelfte: Je
naeher eine Regel am Trendfolge-Signal des Bestands liegt, desto besser ihre
Qualitaet. Der Auftrag verlangt beides, und die Daten sagen, dass sich das
widerspricht.
"""

from __future__ import annotations

import pytest

from research.familien import Familienbild, Regel

#: Die 22 gemessenen Regeln aus Befund 75, 77 und 83, nach Regellogik
#: gruppiert - nicht nach ihren Zahlen.
GEMESSEN: list[tuple[str, int, float, str, float | None]] = [
    ("Luecke", 258, -0.0368, "Struktur", None),
    ("VWAP-short", 185, -0.1113, "Rueckkehr", -0.536),
    ("Trend 50", 156, 0.1894, "Trend", 0.813),
    ("Abfolge o.Str", 124, -0.0469, "Struktur", 0.456),
    ("Trend 100", 109, 0.2231, "Trend", 0.787),
    ("Trend beide", 106, 0.2160, "Trend", 0.473),
    ("Momentum 90", 101, 0.1649, "Trend", 0.712),
    ("Abfolge short", 67, 0.0833, "Struktur", -0.407),
    ("Donchian 55", 58, 0.3074, "Ausbruch", 0.534),
    ("Abfolge-Modell", 56, 0.1067, "Struktur", 0.391),
    ("Vola-Ziel lang", 53, 0.3185, "Trend", 0.555),
    ("Gr.Kerze short", 51, 0.1342, "Volumen", -0.080),
    ("Abfolge o.Lue", 50, 0.1377, "Struktur", 0.499),
    ("Bollinger short", 36, 0.0576, "Rueckkehr", None),
    ("Enge", 18, 0.340522, "Ausbruch", 0.417),
    ("Volumenschock", 114, 0.158416, "Volumen", 0.396),
    ("Rueckkehr VWAP", 92, -0.120133, "Rueckkehr", 0.063),
    ("Abgriff", 406, -0.120146, "Struktur", 0.129),
    ("Volumenschock breit", 145, 0.138702, "Volumen", 0.587),
    ("Rueckkehr VWAP breit", 130, -0.170385, "Rueckkehr", 0.311),
    ("Ueberverkauft", 133, -0.191948, "Rueckkehr", 0.375),
    ("Enge breit", 61, 0.223766, "Ausbruch", 0.437),
]


def bild() -> Familienbild:
    return Familienbild(
        regeln=[
            Regel(name=n, trades=t, sharpe_je_trade=s, familie=f, rho=r)
            for n, t, s, f, r in GEMESSEN
        ]
    )


class TestTrennung:
    def test_die_trennung_haelt_der_permutation_stand(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Spannweite 2,34 gegen ein 95. Perzentil der Zufallszuordnung von 1,79.
        Ohne diesen Vergleich waere die Gruppierung wertlos: Bei fuenf Familien
        und 22 Punkten faellt eine Spannweite von 1,1 rein zufaellig an.
        """
        b = bild()

        assert b.spannweite == pytest.approx(2.34, abs=0.05)
        mittel, perzentil = b.nullprobe(durchlaeufe=5_000)
        assert 0.9 < mittel < 1.4, f"gemessen {mittel:.2f}"
        assert b.spannweite > perzentil
        assert b.trennt_echt

    def test_rueckkehr_liegt_geschlossen_unter_der_geraden(self) -> None:
        """Alle fuenf, ohne Ausnahme - und alle acht aus Trend und Ausbruch
        darueber. Kein Ueberschneidungsfall."""
        je = bild().je_familie()

        assert je["Rueckkehr"][3] < 0, "Auch die beste liegt darunter"
        assert je["Trend"][2] > 0, "Auch die schlechteste liegt darueber"
        assert je["Ausbruch"][2] > 0

    def test_eine_zufaellige_gruppierung_traegt_nicht(self) -> None:
        """Gegenprobe: Labels durchgemischt, dieselben Zahlen."""
        regeln = bild().regeln
        gemischt = Familienbild(
            regeln=[
                Regel(
                    name=r.name, trades=r.trades, sharpe_je_trade=r.sharpe_je_trade,
                    familie=["A", "B", "C", "D", "E"][i % 5], rho=r.rho,
                )
                for i, r in enumerate(regeln)
            ]
        )

        assert not gemischt.trennt_echt
        assert "trennen nicht" in gemischt.urteil()

    def test_zu_wenige_regeln_liefern_nichts(self) -> None:
        duenn = Familienbild(
            regeln=[Regel(name="a", trades=100, sharpe_je_trade=0.2, familie="x")]
        )

        assert not duenn.genug
        assert duenn.spannweite is None
        assert "nichts sagen" in duenn.urteil()


class TestPreis:
    def test_qualitaet_faehrt_auf_aehnlichkeit(self) -> None:
        """**Der zweite tragende Test - die unangenehme Haelfte.**

        Der Auftrag aus Befund 76 verlangt Qualitaet **und** Unabhaengigkeit
        vom Trendfolge-Signal. Ueber zwanzig Regeln korreliert das Residuum
        mit +0,48 mit der Aehnlichkeit zum Bestand: Beides zugleich gab es in
        den Daten bisher nicht.
        """
        wert = bild().guete_faehrt_auf_aehnlichkeit

        assert wert is not None
        assert wert == pytest.approx(0.48, abs=0.05)
        assert wert > 0.3, "Sonst waere der Widerspruch keiner"

    def test_die_alternativerklaerung_steht_im_urteil(self) -> None:
        """Der Markt ist ueber den Zeitraum stark gestiegen - dann misst rho
        nur, wie long-lastig eine Regel war. Beide Deutungen fuehren praktisch
        zum selben Schluss, aber sie sind nicht dasselbe."""
        urteil = bild().urteil()

        assert "widerspricht" in urteil
        assert "Zeitraum" in urteil
        assert "nicht entschieden" in urteil

    def test_ohne_gemessene_aehnlichkeit_gibt_es_keine_zahl(self) -> None:
        ohne = Familienbild(
            regeln=[
                Regel(name=n, trades=t, sharpe_je_trade=s, familie=f)
                for n, t, s, f, _ in GEMESSEN
            ]
        )

        assert ohne.guete_faehrt_auf_aehnlichkeit is None
        assert "Preis" not in ohne.urteil()
