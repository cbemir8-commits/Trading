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

import pytest

from research.engstelle import (
    AUFTEILUNGEN,
    FELD_JE_GATE,
    Stelle,
    aus_gates,
    ausfaelle_je_gate,
    bericht,
    engste,
    herkunft_je_gate,
)

#: Der Spot-Punkt, **aus einem Lauf gemessen** (Befund 442).
#:
#: Bis 442 standen hier zurueckgerechnete Werte: Schwelle und Abstand aus der
#: Tafel von ``cli stand`` abgelesen, der Wert daraus wiederhergestellt
#: (Schwelle plus/minus Abstand, Richtung aus dem Status). Neun der elf Zeilen
#: hat das getroffen, zwei nicht - und die Abweichungen waren von zwei
#: verschiedenen Arten:
#:
#: * ``Bestaendigkeit`` stand auf 0,581 und liegt bei 0,580645 (= 18/31). Die
#:   Rueckrechnung aus einem auf drei Stellen gerundeten Abstand gibt die
#:   Stelle nicht her; der Anteil wurde dadurch 16,2 % statt **16,1 %**.
#: * ``Kosten-Stress`` stand auf 942,865 und liegt bei 1863,726. Das war kein
#:   Rundungsfehler, sondern der **Betriebspunkt-Fehler aus Befund 428**:
#:   942,865 ist derselbe Gate-Wert am **Perpetual**-Punkt, und 'cli stand'
#:   meldet ihn dort so. Ich hatte die berichtete Spalte in eine Tafel
#:   geschrieben, die am Spot-Punkt steht. Aufgefallen ist es nirgends, weil
#:   eine Schwelle von null keinen Anteil hat - die Zeile steht in keiner
#:   Rangfolge.
#:
#:   **Und meine Erklaerung dazu war ebenfalls falsch** (Befund 447). In 443
#:   stand hier, 942,8654 sei ein Endkapital in EUR aus Befund 365
#:   ("955,7552 / 942,8654 / 625,8040"), abgeschrieben aus der falschen Zeile.
#:   Die Ziffern stimmen zufaellig ueberein, und die Geschichte klang
#:   praeziser als die Wahrheit. Gemessen ist es der Perpetual-Wert.
#:
#: Die Tabelle bleibt, weil die Tests darunter ohne Speicher laufen muessen.
#: Sie ist jetzt aber ein **nachgeprueftes Abbild** und keine Abschrift:
#: ``TestDieRangfolgeAmEchtenLauf`` vergleicht sie in der Datenauswahl Zeile
#: fuer Zeile gegen den Lauf.
SPOT: tuple[tuple[str, float, float, bool, str], ...] = (
    ("Schlechtestes Jahr", -9.61, -10.0, True, ""),
    ("Bestaendigkeit", 0.5806451612903226, 0.5, True, ""),
    ("Drawdown", 9.868736145650873, 12.0, True, ""),
    ("Monte-Carlo", 8.326469445606186, 15.0, True, ""),
    ("Out-of-Sample-Sharpe", 1.576216469796038, 1.0, True, ""),
    ("Parameter-Plateau", 1.0, 0.6, True, ""),
    ("Regime-Aufteilung", 5.275072895909707, 0.9, True, ""),
    ("Kosten-Stress", 1863.7258550703123, 0.0, True, ""),
    ("Stichprobengroesse", 2250.0, 250.0, True, "Tage im Markt"),
    ("Messlatte", 14.339, 15.0, False, "Jahresrendite gegen Betriebsschwelle"),
    ("Deflated Sharpe", 0.5825843258003591, 0.95, False, ""),
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
        aussieht - Kosten-Stress meldet 1863,726 gegen 0,000."""
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
        ohne = sorted(n for n, h in herkunft_je_gate().items() if h != "abgeleitet")

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
        assert set(ausfaelle_je_gate()) == {
            "Deflated Sharpe",
            "Schlechtestes Jahr",
            "Messlatte",
        }
        assert AUFTEILUNGEN == 11


class TestNichtsIstGepflegt:
    """**Mein Fehlgriff aus 438, am Tag danach behoben.** Dort standen
    'HERKUNFT' und 'BELASTBARKEIT' als handgeschriebene Listen - gegen meinen
    eigenen Satz aus Befund 435: *Wer hier eine Liste pflegt, hat zwei
    Listen, und eine davon ist irgendwann falsch.*"""

    def test_die_herkunft_kommt_aus_den_docstrings(self) -> None:
        """Wer eine Ableitung nachtraegt, aendert den Satz - und die
        Einordnung wandert mit, ohne zweite Pflege."""
        import inspect

        from research import engstelle

        quelle = inspect.getsource(engstelle.herkunft_je_gate)

        assert "_felddocs()" in quelle
        assert "MARKEN" in quelle

    def test_die_ausfaelle_kommen_aus_aufteilung(self) -> None:
        """'AUSFALL_JE_AUFTEILUNG' fuehrt die Versaetze selbst, nicht nur
        ihre Zahl - eine Dublette davon waere die schlechtere Quelle."""
        from research.aufteilung import AUSFALL_JE_AUFTEILUNG

        assert ausfaelle_je_gate() == {
            gate: len(wo) for gate, wo in AUSFALL_JE_AUFTEILUNG.items()
        }

    def test_und_das_schlechteste_jahr_faellt_in_fuenf(self) -> None:
        """Die Zahl, auf die Befund 438 sich beruft - jetzt aus der Quelle."""
        assert ausfaelle_je_gate()["Schlechtestes Jahr"] == 5


class TestDieEinzigeHandgepflegteZuordnung:
    """Gate-Name zu Schwellenfeld laesst sich statisch nicht ableiten - die
    Zuordnung entsteht erst im Rumpf der Gate-Funktionen. Also bewacht."""

    def test_jedes_feld_gibt_es_wirklich(self) -> None:
        import dataclasses

        from research.gates import GateThresholds

        felder = {f.name for f in dataclasses.fields(GateThresholds)}

        for gate, feld in FELD_JE_GATE.items():
            assert feld in felder, (gate, feld)

    def test_kein_feld_wird_zweimal_benutzt(self) -> None:
        """Zwei Gates auf demselben Feld waere ein Tippfehler, der die
        Herkunft stillschweigend falsch einordnet."""
        felder = list(FELD_JE_GATE.values())

        assert len(felder) == len(set(felder)), felder

    def test_alle_elf_gates_kommen_vor(self) -> None:
        assert len(FELD_JE_GATE) == 11

    def test_und_jedes_gate_der_tafel_ist_zugeordnet(self) -> None:
        """Gegenprobe gegen eine Zuordnung, die am gemessenen Lauf
        vorbeigeht."""
        for name, *_ in SPOT:
            assert name in FELD_JE_GATE, name


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


# **Die Fixture auf Modulebene, nicht in der Klasse** (Befund 426/428/429/431):
# Eine Fixture mit eigenem Scope als Instanzmethode ist ein Fehler, und der
# Waechter aus 429 faengt sie - aber erst, nachdem sie geschrieben war.
@pytest.fixture(scope="module")
def spotgates():
    """Die elf Gates am Spot-Punkt, aus einem echten Lauf.

    Dasselbe Rezept wie 'cli stand': Zulassungsreihe schneiden, Spitzenkandidat
    laden, '_spotpunkt' fahren. Kostet keinen Versuch - dieselbe Regel,
    dieselben Daten, andere Handelsbedingungen.
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import common_range
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.admission import load_trials
    from research.datenstand import alle_geschnitten
    from research.seeds import spitzenkandidat

    einstellungen = get_settings()
    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    speicher = CandleStore(einstellungen.paths.data_store)
    roh = {s: speicher.read(s, Interval.D1) for s in symbole}
    if any(r is None or r.empty for r in roh.values()):
        pytest.skip("keine Tageskerzen im Speicher")
    rahmen = alle_geschnitten(common_range(roh))
    gates, _, _ = cli._spotpunkt(
        rahmen, symbole, spitzenkandidat(),
        load_trials(Path(einstellungen.paths.state) / "trials.json"),
        einstellungen,
    )
    return gates


@pytest.mark.daten
@pytest.mark.langsam
class TestDieRangfolgeAmEchtenLauf:
    """**Die Luecke, die ich mir in 438 gelassen habe** (Befund 442).

    Dort stand die Rangfolge gegen eine **handeingetragene** Tabelle - meine
    Abschrift einer Terminalausgabe. Befund 408 hat gezeigt, was das kostet:
    vierzehn Zyklen rote Datenauswahl, die niemand sah, weil die Zahlen
    nirgends gegen einen Lauf standen.

    Geprueft wird deshalb nicht die Abschrift, sondern die **Behauptung**.
    """

    def test_die_engste_bestandene_stelle_ist_das_schlechteste_jahr(
        self, spotgates
    ) -> None:
        eng = engste(aus_gates(spotgates))

        assert eng is not None
        assert eng.name == "Schlechtestes Jahr"

    def test_und_sie_liegt_bei_knapp_vier_prozent(self, spotgates) -> None:
        eng = engste(aus_gates(spotgates))

        assert 0.035 < eng.anteil < 0.045, eng.anteil

    def test_sie_ist_duenner_als_der_messlatte_fehlt(self, spotgates) -> None:
        """**Die Aussage von Befund 438**, jetzt gegen einen Lauf: Der
        Kandidat ist einem zehnten Durchfaller naeher als dem Bestehen seines
        naechsten offenen Gates."""
        stellen = aus_gates(spotgates)
        eng = engste(stellen)
        latte = next(s for s in stellen if s.name == "Messlatte")

        assert not latte.bestanden
        assert eng.anteil < latte.anteil

    def test_offen_sind_messlatte_und_deflated_sharpe(self, spotgates) -> None:
        offen = {s.name for s in aus_gates(spotgates) if not s.bestanden}

        assert offen == {"Messlatte", "Deflated Sharpe"}

    def test_der_kosten_stress_hat_keinen_anteil(self, spotgates) -> None:
        """Schwelle null - 'unendlich viel Reserve' waere eine Zahl, die nach
        einer Messung aussieht."""
        kosten = next(s for s in aus_gates(spotgates) if s.name == "Kosten-Stress")

        assert kosten.schwelle == 0.0
        assert kosten.anteil is None

    def test_mein_vorbehalt_aus_437_bleibt_gegenstandslos(self, spotgates) -> None:
        """Das Regime-Gate haelt weit ueber 1,0 - die Ungereimtheit zwischen
        Schwelle 0,9 und der Begruendung des Gates kostet diesen Kandidaten
        nichts (Befund 438)."""
        regime = next(
            s for s in aus_gates(spotgates) if s.name == "Regime-Aufteilung"
        )

        assert regime.wert > 1.0
        assert regime.anteil > 4.0

    def test_die_tabelle_oben_ist_das_abbild_dieses_laufs(
        self, spotgates
    ) -> None:
        """**Und die Gegenprobe**, die die Tabelle vom Hoerensagen befreit.

        Elf Zeilen, Zeile fuer Zeile: Wert, Schwelle, Ausgang und Bedingung.
        Damit ist ``SPOT`` keine zweite Quelle mehr (Befund 439), sondern ein
        Abbild, dessen Abweichung auffaellt - in **beide** Richtungen: Eine
        Datendrift wird hier genauso rot wie eine falsche Abschrift.
        """
        gemessen = {s.name: s for s in aus_gates(spotgates)}
        erwartet = {s.name: s for s in _stellen()}

        assert set(gemessen) == set(erwartet)
        for name, soll in erwartet.items():
            ist = gemessen[name]
            assert ist.wert == pytest.approx(soll.wert, abs=1e-9), name
            assert ist.schwelle == pytest.approx(soll.schwelle, abs=1e-9), name
            assert ist.bestanden is soll.bestanden, name
            assert ist.bedingung == soll.bedingung, name

    def test_die_zwei_zeilen_aus_442_stehen_richtig(self, spotgates) -> None:
        """Die beiden, die vorher falsch waren - **mit** ihrer Art von
        Fehler, damit nicht wieder jemand zurueckrechnet.

        'Bestaendigkeit' war eine Rueckrechnung aus einer Rundung (0,581
        statt 0,580645; 16,2 % statt 16,1 %). 'Kosten-Stress' war der Wert
        **des anderen Betriebspunkts**: 942,865 ist derselbe Gate-Wert am
        Perpetual-Punkt, und genau so meldet 'cli stand' ihn. Dass das
        nichts verschoben hat, lag allein an der Schwelle null - ohne Anteil
        steht die Zeile in keiner Rangfolge.

        **Befund 443 hat das falsch erklaert** (richtiggestellt in 447): Dort
        stand, die Zahl sei ein Endkapital aus Befund 365. Die Ziffern
        stimmen zufaellig ueberein.
        """
        gemessen = {s.name: s for s in aus_gates(spotgates)}

        bestand = gemessen["Bestaendigkeit"]
        assert bestand.wert == pytest.approx(18 / 31, abs=1e-12)
        assert round(bestand.anteil * 100, 1) == 16.1

        kosten = gemessen["Kosten-Stress"]
        assert kosten.wert > 1800.0
        assert kosten.wert != pytest.approx(942.8654, abs=1.0)
