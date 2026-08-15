"""Katalog und Kerzenlaenge - die Zuordnung, die nur in Kommentaren stand.

Der Nutzer nennt sie in jedem Auftrag: *"Generation 5 gehoert auf Tageskerzen,
Generation 6/7 auf 15-Minuten-Kerzen."* Im Code stand sie nirgends. Generation
6 heisst im Katalog "schnelles Handeln auf 15-Minuten-Kerzen", Generation 7 ist
der "Katalog der bekannten Scalp-Setups" - und nichts hinderte daran, sie auf
Tageskerzen zu fahren.

Dieselben Periodenzahlen bedeuten dort sechsundneunzigmal laengere Zeitraeume:
eine voellig andere Regel unter demselben Namen. Und ein solcher Lauf ist nicht
nur sinnlos, er ist **teuer** - jeder Versuch hebt die Huerde des Deflated
Sharpe dauerhaft fuer alle folgenden.

Der zweite Teil ist stiller und schlimmer: Die Bestenliste ist nach
``genome_id`` geschluesselt, und dieselbe Regel hat auf Tageskerzen und auf
Viertelstunden dieselbe ID. Zwei solche Ergebnisse konkurrierten um denselben
Platz - ``test_zwei_kerzenlaengen_kollidieren_nicht_mehr`` ist der Test dazu.
"""

from __future__ import annotations

import pytest
import typer

from research.leaderboard import Entry
from research.seeds import VORGESEHEN, passt_zum_intervall


class TestZuordnung:
    def test_die_scalp_kataloge_gehoeren_auf_viertelstunden(self) -> None:
        """Genau die Zuordnung, die der Nutzer seit jeher nennt."""
        assert VORGESEHEN[5] == "D"
        assert VORGESEHEN[6] == "15"
        assert VORGESEHEN[7] == "15"

    def test_eine_falsche_paarung_wird_erkannt(self) -> None:
        assert not passt_zum_intervall(6, "D")
        assert not passt_zum_intervall(5, "15")
        assert passt_zum_intervall(6, "15")
        assert passt_zum_intervall(5, "D")

    def test_ohne_festlegung_laeuft_alles(self) -> None:
        """Eine fehlende Angabe ist keine Ablehnung - die fruehen
        Generationen sind nirgends auf eine Kerzenlaenge festgelegt."""
        assert VORGESEHEN[1] is None
        assert passt_zum_intervall(1, "D")
        assert passt_zum_intervall(1, "15")

    def test_jede_generation_ist_eingetragen(self) -> None:
        """Eine neue Generation ohne Eintrag liefe stillschweigend ueberall -
        und genau diese Stille war der Fehler."""
        from research.seeds import GENERATIONS

        assert set(VORGESEHEN) == set(GENERATIONS)


class TestSperre:
    def test_eine_falsche_paarung_bricht_ab(self) -> None:
        """**Abgebrochen und nicht nur gewarnt.**

        Ein solcher Lauf kostet Versuche, und die Huerde des Deflated Sharpe
        steigt dauerhaft - fuer eine Messung, die nichts bedeutet. Eine
        Warnung, die man ueberliest, waere hier zu wenig.
        """
        from cli import _pruefe_generation
        from core.models import Interval

        with pytest.raises(typer.Exit):
            _pruefe_generation(6, Interval("D"))

    def test_die_richtige_paarung_laeuft_durch(self) -> None:
        from cli import _pruefe_generation
        from core.models import Interval

        _pruefe_generation(6, Interval("15"))
        _pruefe_generation(5, Interval("D"))
        _pruefe_generation(1, Interval("D"))


class TestKollision:
    def eintrag(self, *, intervall: str, dsr: float) -> Entry:
        return Entry(
            genome_id="gleiche-id",
            name="Trend 50",
            generation=5,
            intervall=intervall,
            deflated_sharpe=dsr,
            gates_bestanden=7,
            gates_gesamt=11,
        )

    def test_zwei_kerzenlaengen_kollidieren_nicht_mehr(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Dieselbe Regel hat auf Tageskerzen und auf Viertelstunden dieselbe
        ``genome_id``. Ohne das Intervall haette das bessere Ergebnis das
        andere verdraengt - obwohl beide gar nicht dasselbe gemessen haben.
        """
        tag = self.eintrag(intervall="D", dsr=0.79)
        viertelstunde = self.eintrag(intervall="15", dsr=0.95)

        assert not viertelstunde.vergleichbar_mit(tag)
        assert not viertelstunde.besser_als(tag), (
            "Ein besserer Wert auf anderer Kerzenlaenge darf nicht verdraengen"
        )
        assert not tag.besser_als(viertelstunde)

    def test_auf_derselben_kerzenlaenge_gilt_der_rang(self) -> None:
        schwach = self.eintrag(intervall="D", dsr=0.60)
        stark = self.eintrag(intervall="D", dsr=0.90)

        assert stark.vergleichbar_mit(schwach)
        assert stark.besser_als(schwach)
        assert not schwach.besser_als(stark)

    def test_alte_eintraege_frieren_die_liste_nicht_ein(self) -> None:
        """Ein leeres Intervall stammt aus einem Lauf vor dieser
        Unterscheidung. Es als unvergleichbar zu behandeln hiesse, dass es nie
        mehr abgeloest wird - und die Liste an dieser Stelle einfriert.
        """
        alt = self.eintrag(intervall="", dsr=0.60)
        neu = self.eintrag(intervall="D", dsr=0.90)

        assert neu.vergleichbar_mit(alt)
        assert neu.besser_als(alt)


class TestAufzeichnung:
    def test_das_intervall_landet_im_eintrag(self, tmp_path) -> None:
        from cli import _kandidat_aus_lauf
        from research.gates import GateReport
        from research.leaderboard import Leaderboard
        from research.seeds import spitzenkandidat

        class FakeMetrics:
            sharpe = 1.0
            expectancy_r = 0.3
            total_return_pct = 50.0
            max_drawdown_pct = 10.0

        class FakeReport:
            def __init__(self) -> None:
                self.all_trades: list = []
                self.combined = FakeMetrics()
                self.consistency = 0.5

        genome = spitzenkandidat()
        board = Leaderboard(tmp_path / "board.json")
        board.record(
            [
                _kandidat_aus_lauf(
                    genome,
                    FakeReport(),
                    GateReport(genome_id=genome.genome_id, results=[]),
                )
            ],
            generation=5,
            intervall="D",
        )

        assert board.entries[genome.genome_id].intervall == "D"

    def test_ohne_angabe_bleibt_es_leer(self, tmp_path) -> None:
        """Kein erfundener Standard: Wer es nicht mitgibt, bekommt kein
        Intervall angedichtet."""
        from research.leaderboard import Leaderboard

        board = Leaderboard(tmp_path / "board.json")
        assert Entry(genome_id="x", name="y", generation=1).intervall == ""
        assert board.entries == {}
