""""Entfaellt diese Arbeit" sagte nichts ueber die Marge - Befund 441.

``cli stand`` schliesst mit dem Abschnitt, der dem naechsten Leser sagt, woran
zu arbeiten ist. Er ist genau und gut begruendet, und er endet so:

    Berichtet wird weiter der schlechtere Punkt, weil die Voraussetzung offen
    ist - klaert sie sich zu 'Spot', **entfaellt diese Arbeit.**

Fuer die Gate-**Zahl** stimmt das. Ueber die **Marge** sagt es nichts - und
Befund 438 hat gemessen, dass eines dieser zwei Gates am Spot-Punkt mit
**3,9 %** haelt, der duennsten Reserve aller elf, und in 5 von 11
Fensteraufteilungen faellt (Befund 420). Das andere haelt mit 66,7 %.

Zwei Aufgaben, die beide "entfallen", und eine davon nur auf dem Papier.

**Gelockert ist nichts**: Dieser Befund schreibt eine gemessene Zahl neben
einen Satz, der ohne sie zu bequem liest.
"""

from __future__ import annotations

from research.gatelage import ordne
from research.gates import GateResult, GateStatus


def _lage(reserve: dict[str, float] | None = None):
    ergebnisse = [
        GateResult("Schlechtestes Jahr", GateStatus.FAIL, -10.32, -10.0, ""),
        GateResult("Parameter-Plateau", GateStatus.FAIL, 0.5, 0.6, ""),
        GateResult("Deflated Sharpe", GateStatus.FAIL, 0.458, 0.95, ""),
    ]
    return ordne(
        ergebnisse,
        zweitpunkt="Spot",
        dort_offen=["Deflated Sharpe"],
        dort_reserve=reserve,
    )


class TestDieMargeStehtJetztDaneben:
    def test_der_absatz_nennt_beide_reserven(self) -> None:
        text = _lage({"Schlechtestes Jahr": 0.039, "Parameter-Plateau": 0.667}).urteil()

        assert "Schlechtestes Jahr 3.9%" in text
        assert "Parameter-Plateau 66.7%" in text

    def test_und_die_duennste_wird_benannt(self) -> None:
        """Eine Liste von Prozenten laesst den Leser rechnen; die Aussage
        gehoert dazu."""
        text = _lage({"Schlechtestes Jahr": 0.039, "Parameter-Plateau": 0.667}).urteil()

        assert "duennste davon ist Schlechtestes Jahr" in text
        assert "besteht knapp" in text

    def test_sie_stehen_aufsteigend(self) -> None:
        """Die knappste zuerst - sonst liest man die bequemste als erste."""
        text = _lage({"Parameter-Plateau": 0.667, "Schlechtestes Jahr": 0.039}).urteil()

        assert text.index("Schlechtestes Jahr 3.9%") < text.index(
            "Parameter-Plateau 66.7%"
        )


class TestOhneMessungBleibtDerAbsatzWieVorher:
    def test_keine_reserve_heisst_kein_zusatz(self) -> None:
        """Nicht gemessen ist etwas anderes als komfortabel - ohne Zahlen
        wird keine behauptet."""
        text = _lage().urteil()

        assert "entfaellt diese Arbeit" in text
        assert "Wie knapp es dort haelt" not in text

    def test_der_alte_satz_bleibt_stehen(self) -> None:
        """Der Zusatz ergaenzt ihn und ersetzt ihn nicht: Die Aussage ueber
        die Gate-Zahl ist richtig."""
        text = _lage({"Schlechtestes Jahr": 0.039}).urteil()

        assert "entfaellt diese Arbeit" in text
        assert "Wie knapp es dort haelt" in text

    def test_ein_unbekanntes_gate_wird_nicht_erfunden(self) -> None:
        """Eine Reserve zu einem Gate, das hier nicht offen ist, gehoert
        nicht in diesen Absatz."""
        text = _lage({"Drawdown": 0.178}).urteil()

        assert "Drawdown" not in text
        assert "Wie knapp es dort haelt" not in text


class TestKeineBequemeLesung:
    def test_bei_dicker_reserve_steht_kein_warnsatz(self) -> None:
        """Gegenprobe: Haelt es dort mit Luft, ist 'entfaellt' richtig und
        der Zusatz nennt nur die Zahlen."""
        text = _lage({"Schlechtestes Jahr": 0.4, "Parameter-Plateau": 0.667}).urteil()

        assert "Wie knapp es dort haelt" in text
        assert "besteht knapp" not in text

    def test_die_grenze_liegt_bei_fuenf_prozent(self) -> None:
        knapp = _lage({"Schlechtestes Jahr": 0.049}).urteil()
        reichlich = _lage({"Schlechtestes Jahr": 0.051}).urteil()

        assert "besteht knapp" in knapp
        assert "besteht knapp" not in reichlich


class TestDieZahlenKommenAusEinerQuelle:
    """Keine zweite Liste - die Lehre aus Befund 439."""

    def test_cli_rechnet_sie_aus_den_gate_ergebnissen(self) -> None:
        import inspect

        import cli

        quelle = inspect.getsource(cli.stand)

        assert "_stellen_aus(spotgates)" in quelle
        assert "dort_reserve=dort_reserve" in quelle

    def test_und_nur_bestandene_mit_anteil(self) -> None:
        """Ein offenes Gate hat keine Reserve, und eine Schwelle null keinen
        Anteil (Befund 438)."""
        import inspect

        import cli

        quelle = inspect.getsource(cli.stand)

        assert "s.bestanden and s.anteil is not None" in quelle

    def test_leer_heisst_nicht_gemessen(self) -> None:
        from research.gatelage import Gatelage

        assert Gatelage().dort_reserve == {}
