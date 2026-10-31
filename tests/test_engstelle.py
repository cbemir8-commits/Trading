"""Welches Gate ist dem Durchfallen am naechsten? - Befund 438.

``cli stand`` zeigt je Gate den Abstand, aber **absolut** - und absolute
Abstaende sind nicht vergleichbar: 0,390 beim schlechtesten Jahr steht auf
einer Schwelle von 10, 0,081 bei der Bestaendigkeit auf einer von 0,5. Wer die
Spalte liest, haelt die groessere Zahl fuer die groessere Reserve.

Relativ gerechnet kehrt sich das um, und es faellt eine Aussage heraus, die
vorher nicht zu sehen war:

    Schlechtestes Jahr     3,9 % Reserve   <- engstes bestandenes Gate
    Messlatte              4,4 % fehlt     <- naechstes offenes Gate

**Der Kandidat ist einem zehnten Durchfaller naeher als dem Bestehen seines
nachsten offenen Gates** - und es ist dasselbe Gate, das Befund 420 als das
unbelastbarste gemessen hat (faellt in 5 von 11 Fensteraufteilungen).
"""

from __future__ import annotations

from research.engstelle import (
    AUFTEILUNGEN,
    BELASTBARKEIT,
    HERKUNFT,
    Stelle,
    aus_gates,
    bericht,
    engste,
)

#: Der Spot-Punkt, wie ``cli stand`` ihn meldet: Schwelle und Abstand sind
#: abgelesen, der Wert daraus zurueckgerechnet (Schwelle plus/minus Abstand,
#: Richtung aus dem Status). Gegengeprueft an Befund 416: -9,6100 und 9,869.
SPOT: tuple[tuple[str, float, float, bool, str], ...] = (
    ("Schlechtestes Jahr", -9.610, -10.0, True, ""),
    ("Bestaendigkeit", 0.581, 0.5, True, ""),
    ("Drawdown", 9.869, 12.0, True, ""),
    ("Monte-Carlo", 8.326, 15.0, True, ""),
    ("Out-of-Sample-Sharpe", 1.576, 1.0, True, ""),
    ("Parameter-Plateau", 1.000, 0.6, True, ""),
    ("Regime-Aufteilung", 5.275, 0.9, True, ""),
    ("Kosten-Stress", 942.865, 0.0, True, ""),
    ("Stichprobengroesse", 2250.0, 250.0, True, "Zeit im Markt"),
    ("Messlatte", 14.339, 15.0, False, "Jahresrendite"),
    ("Deflated Sharpe", 0.5826, 0.95, False, ""),
)


def _stellen() -> tuple[Stelle, ...]:
    rohe = [
        Stelle(name=n, wert=w, schwelle=s, bestanden=b, bedingung=c)
        for n, w, s, b, c in SPOT
    ]
    return tuple(sorted(rohe, key=lambda x: (x.anteil is None, x.anteil or 0.0)))


class TestDerAnteilMachtVergleichbar:
    def test_absolut_und_relativ_ordnen_verschieden(self) -> None:
        """Der Grund, warum es diesen Befund gibt: Absolut steht der
        Rueckgang mit 2,131 weit vor dem schlechtesten Jahr mit 0,390 -
        relativ ist es umgekehrt."""
        jahr = next(s for s in _stellen() if s.name == "Schlechtestes Jahr")
        rueckgang = next(s for s in _stellen() if s.name == "Drawdown")

        assert jahr.abstand < rueckgang.abstand
        assert jahr.anteil < rueckgang.anteil

    def test_der_abstand_ist_immer_positiv(self) -> None:
        """Die Richtung steht im Status, nicht in der Zahl (Befund 395)."""
        assert all(s.abstand >= 0 for s in _stellen())

    def test_eine_schwelle_null_gibt_keinen_anteil(self) -> None:
        """'Unendlich viel Reserve' waere eine Zahl, die nach einer Messung
        aussieht - Kosten-Stress meldet 942,865 gegen 0,000."""
        kosten = next(s for s in _stellen() if s.name == "Kosten-Stress")

        assert kosten.schwelle == 0.0
        assert kosten.anteil is None
        assert "kein Anteil" in kosten.beschreibe()

    def test_ohne_anteil_steht_hinten_und_nicht_vorn(self) -> None:
        """Sonst waere das Gate mit der unbestimmbaren Reserve das engste."""
        namen = [s.name for s in _stellen()]

        assert namen[-1] == "Kosten-Stress"


class TestDieEngsteStelle:
    def test_es_ist_das_schlechteste_jahr(self) -> None:
        eng = engste(_stellen())

        assert eng is not None
        assert eng.name == "Schlechtestes Jahr"
        assert 0.035 < eng.anteil < 0.045

    def test_und_es_ist_enger_als_die_messlatte_fehlt(self) -> None:
        """**Die Aussage des Befundes.** Der Kandidat ist einem zehnten
        Durchfaller naeher als dem Bestehen seines naechsten offenen Gates."""
        stellen = _stellen()
        jahr = next(s for s in stellen if s.name == "Schlechtestes Jahr")
        latte = next(s for s in stellen if s.name == "Messlatte")

        assert jahr.anteil < latte.anteil
        assert jahr.bestanden and not latte.bestanden

    def test_offene_gates_mischen_sich_nicht_in_die_rangliste(self) -> None:
        """Die offenen sind nicht 'eng', sie sind offen."""
        assert engste(_stellen()).bestanden
        assert engste(_stellen(), nur_bestandene=False).name == "Schlechtestes Jahr"

    def test_der_bericht_nennt_die_belastbarkeit_dazu(self) -> None:
        text = bericht(_stellen())

        assert "5 von 11" in text
        assert "Befund 420" in text


class TestDieKreuzeStimmen:
    def test_jedes_gate_hat_eine_herkunft(self) -> None:
        for s in _stellen():
            assert s.herkunft != "unbekannt", s.name

    def test_die_sieben_ohne_ableitung_sind_die_aus_437(self) -> None:
        ohne = sorted(n for n, h in HERKUNFT.items() if h != "abgeleitet")

        assert ohne == [
            "Bestaendigkeit",
            "Kosten-Stress",
            "Monte-Carlo",
            "Out-of-Sample-Sharpe",
            "Parameter-Plateau",
            "Regime-Aufteilung",
        ], ohne

    def test_die_zweitengste_steht_auf_einer_ohne_ableitung(self) -> None:
        bestandene = [s for s in _stellen() if s.bestanden and s.anteil is not None]

        assert bestandene[1].name == "Bestaendigkeit"
        assert bestandene[1].herkunft == "ohne"

    def test_ungemessene_belastbarkeit_bleibt_leer(self) -> None:
        """Eine Null einzutragen hiesse 'faellt nie' - gemessen ist das
        nicht."""
        drawdown = next(s for s in _stellen() if s.name == "Drawdown")

        assert drawdown.faellt_in is None
        assert set(BELASTBARKEIT) == {
            "Deflated Sharpe",
            "Schlechtestes Jahr",
            "Messlatte",
        }
        assert AUFTEILUNGEN == 11


class TestMeinVorbehaltAus437KostetNichts:
    def test_das_regime_gate_haelt_auch_bei_einer_schwelle_von_eins(self) -> None:
        """437 hat verzeichnet, dass 0,9 der eigenen Begruendung des Gates
        widerspricht. Gemessen steht der Kandidat bei 5,275 - er bestaende
        es bei 1,0 genauso. Die Ungereimtheit gilt fuer kuenftige
        Kandidaten, nicht fuer diesen."""
        regime = next(s for s in _stellen() if s.name == "Regime-Aufteilung")

        assert regime.wert > 1.0
        assert regime.anteil > 4.0
        assert regime.herkunft == "widersprechend"


class TestZweiGroessenInEinerSpalte:
    def test_gates_mit_bedingung_sind_als_unvergleichbar_markiert(self) -> None:
        """Befund 395 hat dort einen Faktor elf gemessen - wer solche Paare
        ueber Laeufe hinweg vergleicht, vergleicht Massstaebe."""
        stellen = _stellen()
        latte = next(s for s in stellen if s.name == "Messlatte")
        probe = next(s for s in stellen if s.name == "Stichprobengroesse")

        assert not latte.vergleichbar
        assert not probe.vergleichbar
        assert "Bedingung: Jahresrendite" in latte.beschreibe()

    def test_die_uebrigen_sind_vergleichbar(self) -> None:
        for s in _stellen():
            if s.name not in ("Messlatte", "Stichprobengroesse"):
                assert s.vergleichbar, s.name


class TestUebersprungeneGatesKommenNichtVor:
    def test_ein_ausgesetztes_gate_wird_nicht_als_reserve_gefuehrt(self) -> None:
        """Ein Gate, das nicht geurteilt hat, hat keinen Abstand (395) - es
        als Reserve zu fuehren waere der Freibrief aus Befund 430.

        **Gefahren wird der echte Typ** (Befund 438). Hier stand ein Doppel
        mit einem ``.passed``, das ``GateStatus`` nicht hat - der Test hat
        damit meine Annahme geprueft und nicht den Code, und der Fehler fiel
        erst am echten Lauf auf: Die Rangliste blieb leer, weil jedes Gate
        als nicht bestanden gelesen wurde.
        """
        from research.gates import GateResult, GateStatus

        ergebnisse = [
            GateResult("Monte-Carlo", GateStatus.SKIP, 8.3, 15.0, ""),
            GateResult("Drawdown", GateStatus.PASS, 9.9, 12.0, ""),
            GateResult("Messlatte", GateStatus.FAIL, 12.9, 15.0, ""),
        ]

        stellen = aus_gates(ergebnisse)

        # Der Punkt dieses Tests ist das **Fehlen** des uebersprungenen, nicht
        # die Reihenfolge: Nach Anteil liegt die Messlatte mit 14 % vor dem
        # Rueckgang mit 17,5 %, und das ist richtig so.
        assert {s.name for s in stellen} == {"Drawdown", "Messlatte"}
        assert "Monte-Carlo" not in {s.name for s in stellen}
        assert next(s for s in stellen if s.name == "Drawdown").bestanden
        assert not next(s for s in stellen if s.name == "Messlatte").bestanden

    def test_und_ein_bestandenes_gate_wird_als_bestanden_gelesen(self) -> None:
        """Die Gegenprobe zum Fehlgriff: Ohne sie war die Rangliste leer und
        kein Test hat es gemerkt."""
        from research.gates import GateResult, GateStatus

        stellen = aus_gates(
            [GateResult("Drawdown", GateStatus.PASS, 9.869, 12.0, "")]
        )

        assert engste(stellen) is not None
        assert engste(stellen).name == "Drawdown"
