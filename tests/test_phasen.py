"""Traegt eine Regel dort, wo der Bestand nicht traegt?

Drei Tests tragen diese Datei:

``test_die_kopplung_sagt_nichts_ueber_die_phase`` - Die eigentliche Nachricht.
Die Partnersuche siebt seit Befund 73 nach kleiner Fensterkorrelation, und die
traegt ueber den Phasenunterschied keine Information.

``test_gegenlaeufig_wird_im_aufwaertsmarkt_bezahlt`` - Die Gegenprobe zur
eigenen guten Nachricht. Ohne sie waeren sechs gegenlaeufige Regeln ein Fund;
mit ihr sind fuenf davon einfach schlechte Regeln.

``test_die_kopplung_faellt_im_abwaertsmarkt`` - Die offene Frage aus Befund 84:
Regel-Eigenschaft oder Zeitraum-Eigenschaft?
"""

from __future__ import annotations

import pytest

from research.phasen import ABWAERTSJAHRE, Phasenbild, Phasenvergleich

#: 22 Regeln auf Tageskerzen ueber BTC und ETH, Trades nach dem Jahr des
#: Ausstiegs getrennt, Groessenlogik des Bestands. Gemessen, nicht gesetzt -
#: wer sie aendert, aendert eine Messung. Nachzurechnen mit ``cli phasen``.
#: Reihenfolge: name, rho, SR aufwaerts, SR abwaerts, n auf, n ab.
GEMESSEN: list[tuple[str, float | None, float, float, int, int]] = [
    ("VWAP-Rueckkehr short", -0.536, -0.226085, 0.318848, 150, 35),
    ("Grosse Kerze mit Volumen short", -0.080, -0.156125, 0.368450, 24, 27),
    ("Bollinger-Ruecksetzer short", None, -0.245248, 0.206234, 13, 23),
    ("Luecke wird geschlossen", -0.597, -0.181995, 0.259306, 177, 81),
    ("Abfolge-Modell short", -0.407, -0.091476, 0.333201, 40, 27),
    ("Trend beide Richtungen", 0.473, 0.179430, 0.343017, 71, 35),
    ("Trend-Beteiligung (fair gerechnet)", 0.555, 0.359894, 0.231298, 36, 17),
    ("Abgriff des Vortagestiefs", 0.129, -0.004241, -0.249536, 214, 192),
    ("Abfolge-Modell (Abgriff, Bruch)", 0.391, 0.190835, -0.071988, 36, 20),
    ("Trend-Beteiligung 100 Tage", 0.787, 0.288264, 0.011578, 70, 39),
    ("Abfolge ohne Strukturbruch", 0.456, 0.110603, -0.241382, 66, 58),
    ("Trend 50 Tage mit Konfluenz", 1.000, 0.347273, -0.045043, 101, 53),
    ("Momentum-Beteiligung 90 Tage", 0.712, 0.213402, -0.181494, 74, 27),
    ("Trend-Beteiligung 50 Tage", 0.813, 0.257774, -0.156582, 102, 54),
    ("Rueckkehr zum Volumenschwerpunkt", 0.063, 0.123060, -0.316615, 40, 52),
    ("Volumenschock mit Fortsetzung", 0.396, 0.263038, -0.208405, 73, 41),
    ("Ueberverkauft ohne Trendfilter", 0.375, 0.068682, -0.419028, 55, 78),
    ("Rueckkehr zum Volumenschwerpunkt breit", 0.311, 0.092585, -0.400290, 60, 70),
    ("Abfolge ohne Luecke", 0.499, 0.340155, -0.217132, 30, 20),
    ("Donchian-Ausbruch 55/20", 0.534, 0.390084, -0.175933, 42, 16),
    ("Volumenschock breit", 0.587, 0.323400, -0.498391, 87, 58),
    ("Enge vor Bewegung breit", 0.437, 0.506991, -1.377159, 36, 25),
]

#: Der Bestand - die Regel, gegen die der Verbund-Partner antreten muesste.
BESTAND = "Trend 50 Tage mit Konfluenz"


def vergleich() -> Phasenvergleich:
    return Phasenvergleich(
        bilder=[
            Phasenbild(
                name=n, rho=r, sharpe_auf=sa, sharpe_ab=sb,
                trades_auf=na, trades_ab=nb,
            )
            for n, r, sa, sb, na, nb in GEMESSEN
        ]
    )


class TestZeitraum:
    def test_die_abwaertsjahre_stehen_fest(self) -> None:
        """Vier fallende Jahre von neun - abgelesen aus den Kursdaten:
        2018 -73,4 %, 2022 -64,2 %, 2025 -6,3 %, 2026 -26,5 %. In Befund 84
        stand, es gebe sie nicht; das war falsch."""
        assert set(ABWAERTSJAHRE) == {2018, 2022, 2025, 2026}

    def test_die_kopplung_faellt_im_abwaertsmarkt(self) -> None:
        """**Die offene Frage aus Befund 84.**

        Dort korrelierte Aehnlichkeit zum Bestand mit Qualitaet zu +0,48, mit
        dem Vorbehalt, das koenne am steigenden Markt liegen. Getrennt nach
        Marktrichtung: +0,404 aufwaerts (t = 1,93), +0,075 abwaerts
        (t = 0,33). Der Zusammenhang kehrt sich nicht um, ist im
        Abwaertsmarkt aber nicht mehr nachweisbar - das spricht eher fuer die
        Zeitraum-Deutung, entscheidet bei 21 Punkten aber nichts.
        """
        v = vergleich()

        auf, ab = v.aehnlichkeit_aufwaerts, v.aehnlichkeit_abwaerts
        assert auf == pytest.approx(0.404, abs=0.01)
        assert ab == pytest.approx(0.075, abs=0.01)
        assert abs(ab) < abs(auf) / 1.5, "sonst haelt sie in beiden Phasen"
        assert ab > 0, "sie kehrt sich nicht um - das waere ein anderer Befund"
        assert "Zeitraum-Deutung" in v.urteil()

    def test_der_bestand_verliert_im_abwaertsmarkt(self) -> None:
        """0,3473 aufwaerts gegen -0,0450 abwaerts. Die Zahl, die den ganzen
        Verbund-Auftrag begruendet: Der Bestand hat dort nichts."""
        bestand = next(b for b in vergleich().bilder if b.name == BESTAND)

        assert bestand.sharpe_auf > 0.3
        assert bestand.sharpe_ab < 0
        assert not bestand.traegt_gegenlaeufig
        assert bestand.gesamt_sharpe == pytest.approx(0.2123, abs=0.001)


class TestBlindeSuche:
    def test_die_kopplung_sagt_nichts_ueber_die_phase(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Die Partnersuche siebt seit Befund 73 nach kleiner
        Fensterkorrelation. Ueber dieselben Regeln korreliert rho mit dem
        Phasenunterschied zu +0,097 (t = 0,43) - praktisch null. Kleines rho
        findet also keine Regel, die im Abwaertsmarkt traegt; die beiden
        Eigenschaften haben in diesen Daten nichts miteinander zu tun.
        """
        wert = vergleich().kopplung_sagt_die_phase

        assert wert is not None
        assert wert == pytest.approx(0.097, abs=0.02)
        assert abs(wert) < 0.2, "sonst faende die bisherige Suche es nebenbei mit"
        assert "siebt an dieser Eigenschaft vorbei" in vergleich().urteil()

    def test_sechzehn_von_zweiundzwanzig_sind_abwaerts_schlechter(self) -> None:
        """Der Erstdurchlauf sah 14 Regeln und fand **eine** gegenlaeufige -
        weil er den Katalog nach Namen filterte (Trend, Momentum, Donchian)
        und damit genau die short-faehigen Regeln ausschloss, die die Frage
        beantworten. Ueber den vollen Katalog sind es sechs."""
        v = vergleich()

        assert len(v.bilder) == 22
        assert len([b for b in v.bilder if b.unterschied > 0]) == 16
        assert len(v.gegenlaeufige) == 6


class TestPreis:
    def test_gegenlaeufig_wird_im_aufwaertsmarkt_bezahlt(self) -> None:
        """**Die Gegenprobe zur eigenen guten Nachricht.**

        Sechs Regeln verdienen im Abwaertsmarkt. Fuenf davon verlieren im
        Aufwaertsmarkt so viel, dass ueber alle Trades fast nichts bleibt -
        und die Verbund-Guete rechnet ueber die ganze Stichprobe. Ohne diesen
        Test waeren sechs Partner gefunden; mit ihm ist es einer.
        """
        gegen = vergleich().gegenlaeufige

        assert [b.gesamt_sharpe for b in gegen] == sorted(
            (b.gesamt_sharpe for b in gegen), reverse=True
        ), "beste Gesamtqualitaet zuerst"
        assert gegen[0].name == "Trend beide Richtungen"
        assert gegen[0].gesamt_sharpe == pytest.approx(0.2334, abs=0.001)
        assert all(b.gesamt_sharpe < 0.13 for b in gegen[1:])

    def test_die_staerkste_gegenlaeufigkeit_ist_die_schlechteste_regel(self) -> None:
        """'VWAP-Rueckkehr short' hat den groessten Phasenunterschied (0,54)
        und insgesamt -0,1230. Wer nur nach Gegenlaeufigkeit siebt, findet
        zuerst die Regeln, die im Aufwaertsmarkt am meisten verlieren."""
        v = vergleich()
        staerkste = min(v.bilder, key=lambda b: b.unterschied)

        assert staerkste.name == "VWAP-Rueckkehr short"
        assert staerkste.unterschied == pytest.approx(-0.5449, abs=0.001)
        assert staerkste.gesamt_sharpe == pytest.approx(-0.1230, abs=0.001)
        assert "andere Seite einer verlierenden Regel" in v.urteil()

    def test_der_beste_phasenunterschied_liegt_unter_dem_rauschen(self) -> None:
        """Von den 106 Trades von 'Trend beide Richtungen' fallen 35 in die
        Abwaertsjahre - Messrauschen 0,17 gegen einen Unterschied von 0,16.
        Dazu kommt: Ausgewaehlt wurde sie **nach** dem Blick auf 22
        Ergebnisse."""
        beste = vergleich().gegenlaeufige[0]

        assert beste.trades == 106
        assert beste.rauschen_ab == pytest.approx(0.1715, abs=0.001)
        assert abs(beste.unterschied) == pytest.approx(0.1636, abs=0.001)
        assert not beste.unterschied_traegt
        assert "keine Aussage" in vergleich().urteil()

    def test_ein_klarer_unterschied_wuerde_tragen(self) -> None:
        """Gegenprobe zur Gegenprobe: Der Test verwirft nicht alles."""
        klar = Phasenbild(
            name="hypothetisch", sharpe_auf=0.10, sharpe_ab=0.60,
            trades_auf=100, trades_ab=100,
        )

        assert klar.traegt_gegenlaeufig
        assert klar.unterschied_traegt
        assert klar.gesamt_sharpe == pytest.approx(0.35)


class TestGrenzen:
    def test_zu_wenige_regeln_liefern_nichts(self) -> None:
        duenn = Phasenvergleich(
            bilder=[
                Phasenbild(
                    name="a", sharpe_auf=0.2, sharpe_ab=0.1,
                    trades_auf=50, trades_ab=50, rho=0.3,
                )
            ]
        )

        assert not duenn.genug
        assert duenn.aehnlichkeit_aufwaerts is None
        assert duenn.kopplung_sagt_die_phase is None
        assert "nichts sagen" in duenn.urteil()

    def test_ohne_gemessene_aehnlichkeit_bleibt_die_phasenfrage(self) -> None:
        """Die Trennung nach Marktrichtung braucht kein rho - nur der
        Vergleich mit Befund 84 braucht es."""
        ohne = Phasenvergleich(
            bilder=[
                Phasenbild(
                    name=n, sharpe_auf=sa, sharpe_ab=sb,
                    trades_auf=na, trades_ab=nb,
                )
                for n, _, sa, sb, na, nb in GEMESSEN
            ]
        )

        assert ohne.genug
        assert ohne.aehnlichkeit_aufwaerts is None
        assert ohne.kopplung_sagt_die_phase is None
        assert len(ohne.gegenlaeufige) == 6
        assert "Befund 84" not in ohne.urteil()

    def test_eine_regel_ohne_rho_verdirbt_die_korrelation_nicht(self) -> None:
        """'Bollinger-Ruecksetzer short' hat keine Fenster und damit kein rho.
        Sie steht in der Tabelle, zaehlt bei den Gegenlaeufigen mit und
        bleibt aus jeder Korrelation heraus - 21 statt 22 Punkte."""
        v = vergleich()

        assert len(v._mit_rho()) == 21
        assert any(b.rho is None for b in v.bilder)
        assert v.kopplung_sagt_die_phase is not None
        assert "ueber 21 Regeln" in v.urteil()

    def test_die_tabelle_sortiert_die_gegenlaeufigen_nach_oben(self) -> None:
        zeilen = vergleich().tabelle().splitlines()

        assert "VWAP-Rueckkehr short" in zeilen[2]
        assert "Enge vor Bewegung breit" in zeilen[-1]
        assert "gesamt" in zeilen[0]
