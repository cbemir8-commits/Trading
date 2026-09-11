"""Die Frage direkt stellen, statt ueber einen gesetzten Faktor.

**Befund 254.** ``Kostenfrage`` kann die Gebuehr zurueckrechnen, die Slippage
aber nicht - sie steckt im Ausfuehrungspreis und damit schon in ``gross_pnl``.
Deshalb stand die Frage seit Befund 78 in der Form *"wie gross muesste die
Reibung sein, damit sie die Kopplung traegt?"*, und ``ERREICHBAR = 5.0``
entschied als **gesetzte** Grenze, ab wann die Antwort "nein" lautet.

Auf Tageskerzen war das folgenlos: Kippfaktor 29, weit jenseits jeder Wahl der
Grenze. Auf Viertelstunden kam Faktor 2 heraus - und dort entscheidet seitdem
eine Konvention ueber einen Befund.

Das muss sie nicht. ``CostModel.scaled(0)`` setzt Gebuehr **und** Slippage auf
null; die Engine nimmt beide als Parameter. Dieselben Regeln zweimal, einmal
mit und einmal ohne jede Reibung - dann steht die Kopplung ohne Faktorargument
da.

Was hier gehalten wird
----------------------
Nicht die Zahlen des Laufs, sondern der Vergleich: dass beide Laeufe **dieselbe
Regelmenge** tragen muessen, dass der Anteil als Weg zur Null gerechnet wird,
und dass das Urteil zwischen "traegt sie", "teils" und "traegt sie nicht"
unterscheidet, statt einen davon als Gesetz einzubauen (der Fehler aus Befund
187).
"""

from __future__ import annotations

import pytest

from research.kostenanteil import Kostenfrage, Reibungsprobe, Taktpunkt


def _punkt(name: str, trades: int, sharpe: float, anteil: float = 0.0) -> Taktpunkt:
    return Taktpunkt(
        name=name, trades=trades, sharpe_je_trade=sharpe,
        haltedauer_tage=1.0, kostenanteil=anteil,
    )


def _lauf(*paare: tuple[str, int, float], anteil: float = 0.0) -> Kostenfrage:
    return Kostenfrage(
        punkte=[_punkt(n, t, s, anteil) for n, t, s in paare]
    )


#: Vier Regeln mit fallender Qualitaet bei steigender Trade-Zahl.
MIT = (("a", 10, 0.30), ("b", 50, 0.10), ("c", 100, 0.00), ("d", 200, -0.10))


class TestBeideLaeufeMuessenDieselbenRegelnTragen:
    """Ohne Reibung fallen Fuellungen anders aus, Risikogrenzen greifen
    anders - eine Regel kann im einen Lauf genug Trades haben und im anderen
    nicht. Verglichen wuerden dann zwei Populationen."""

    def test_gleiche_namen_sind_vergleichbar(self) -> None:
        probe = Reibungsprobe(mit=_lauf(*MIT), ohne=_lauf(*MIT))

        assert probe.gleiche_regeln and probe.belastbar

    def test_eine_zusaetzliche_regel_macht_unvergleichbar(self) -> None:
        probe = Reibungsprobe(
            mit=_lauf(*MIT),
            ohne=_lauf(*MIT, ("e", 300, -0.20)),
        )

        assert not probe.gleiche_regeln
        assert not probe.belastbar
        assert "Nicht vergleichbar" in probe.urteil()
        assert "zwei" in probe.urteil() and "Populationen" in probe.urteil()

    def test_eine_fehlende_regel_ebenso(self) -> None:
        probe = Reibungsprobe(mit=_lauf(*MIT), ohne=_lauf(*MIT[:3]))

        assert not probe.gleiche_regeln

    def test_die_reihenfolge_spielt_keine_rolle(self) -> None:
        probe = Reibungsprobe(mit=_lauf(*MIT), ohne=_lauf(*reversed(MIT)))

        assert probe.gleiche_regeln

    def test_unter_vier_regeln_gibt_es_keine_korrelation(self) -> None:
        wenig = MIT[:3]
        probe = Reibungsprobe(mit=_lauf(*wenig), ohne=_lauf(*wenig))

        assert probe.gleiche_regeln
        assert not probe.belastbar
        assert "Zu wenige Punkte" in probe.urteil()


class TestDerAnteilIstDerWegZurNull:
    def test_unveraendert_heisst_null(self) -> None:
        probe = Reibungsprobe(mit=_lauf(*MIT), ohne=_lauf(*MIT))

        assert probe.anteil_der_reibung == pytest.approx(0.0)

    def test_aufgehoben_heisst_eins(self) -> None:
        """Ohne Reibung keine Kopplung mehr - dann traegt sie die ganze."""
        flach = (("a", 10, 0.1), ("b", 50, 0.1), ("c", 100, 0.1), ("d", 200, 0.1))
        probe = Reibungsprobe(mit=_lauf(*MIT), ohne=Kostenfrage(
            punkte=[_punkt(n, t, s) for n, t, s in flach]
        ))

        assert probe.anteil_der_reibung is None or probe.anteil_der_reibung >= 0.99

    def test_ohne_vergleichbarkeit_gibt_es_keinen_anteil(self) -> None:
        probe = Reibungsprobe(mit=_lauf(*MIT), ohne=_lauf(*MIT[:3]))

        assert probe.anteil_der_reibung is None

    def test_ohne_negative_kopplung_gibt_es_nichts_aufzuheben(self) -> None:
        steigend = (("a", 10, -0.1), ("b", 50, 0.0), ("c", 100, 0.1), ("d", 200, 0.2))
        probe = Reibungsprobe(mit=_lauf(*steigend), ohne=_lauf(*steigend))

        assert probe.anteil_der_reibung is None


class TestDasUrteilBautKeinenAusgangAlsGesetzEin:
    """Der Fehler aus Befund 187: Das Urteil sprach die Antwort aus, die
    woanders gemessen worden war, auch wenn die Zahlen daneben widersprachen.
    Hier verzweigt es an dem, was gemessen wurde."""

    @staticmethod
    def _ohne(*werte: float) -> Kostenfrage:
        return Kostenfrage(
            punkte=[
                _punkt(n, t, w)
                for (n, t, _), w in zip([*MIT], werte, strict=True)
            ]
        )

    def test_kopplung_bleibt_negativ_traegt_die_reibung_nicht(self) -> None:
        probe = Reibungsprobe(
            mit=_lauf(*MIT), ohne=self._ohne(0.31, 0.12, 0.03, -0.06)
        )
        text = probe.urteil()

        assert not probe.traegt_die_reibung
        assert "traegt sie nicht" in text
        assert "Eigenschaft der **Signale**" in text
        assert "ohne Faktorargument" in text

    def test_kopplung_kehrt_sich_um_dann_traegt_sie(self) -> None:
        probe = Reibungsprobe(
            mit=_lauf(*MIT), ohne=self._ohne(-0.10, 0.00, 0.10, 0.30)
        )
        text = probe.urteil()

        assert probe.traegt_die_reibung
        assert "Die Reibung traegt sie." in text
        assert "verhandelbar" in text

    def test_dazwischen_sagt_das_urteil_teils(self) -> None:
        probe = Reibungsprobe(
            mit=_lauf(*MIT), ohne=self._ohne(0.15, 0.05, 0.20, 0.05)
        )
        text = probe.urteil()

        assert not probe.traegt_die_reibung
        anteil = probe.anteil_der_reibung
        assert anteil is not None and 0.25 < anteil < 1.0
        assert text.startswith("**Teils.**")
        assert "bleibt die Kopplung negativ" in text

    def test_alle_drei_urteile_sind_verschieden(self) -> None:
        """Sonst waere die Verzweigung Zierde."""
        texte = {
            Reibungsprobe(mit=_lauf(*MIT), ohne=self._ohne(*w)).urteil()
            for w in (
                (0.31, 0.12, 0.03, -0.06),
                (-0.10, 0.00, 0.10, 0.30),
                (0.15, 0.05, 0.20, 0.05),
            )
        }

        assert len(texte) == 3


class TestDieTabelle:
    def test_sie_nennt_beide_laeufe(self) -> None:
        text = Reibungsprobe(mit=_lauf(*MIT), ohne=_lauf(*MIT)).tabelle()

        assert "mit Reibung" in text and "ohne" in text

    def test_die_trennlinie_passt_zur_ueberschrift(self) -> None:
        zeilen = Reibungsprobe(mit=_lauf(*MIT), ohne=_lauf(*MIT)).tabelle().splitlines()

        assert len(zeilen[1]) == len(zeilen[0])

    def test_ein_fehlender_kippfaktor_bricht_sie_nicht(self) -> None:
        steigend = (("a", 10, -0.1), ("b", 50, 0.0), ("c", 100, 0.1), ("d", 200, 0.2))
        text = Reibungsprobe(mit=_lauf(*steigend), ohne=_lauf(*steigend)).tabelle()

        assert "-" in text


class TestDerBefehlLaesstBeideLaeufeDurchDieselbeStelle:
    """Zwei Konfigurationen, ein Regelsatz: Der zweite Lauf muss dasselbe
    Genom und dieselbe Randbehandlung nehmen, sonst vergleicht er zwei
    Populationen - genau das, wovor 'gleiche_regeln' schuetzt."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "vorratsdecke"
        )
        return ast.unparse(knoten)

    def test_die_nullkosten_kommen_aus_scaled_null(self) -> None:
        assert "costs.scaled(Decimal(0))" in self._quelle()

    def test_beide_laeufe_nehmen_dasselbe_genom(self) -> None:
        quelle = self._quelle()

        assert quelle.count("compile_genome(g)") == 2

    def test_beide_laeufe_schneiden_den_rand_gleich(self) -> None:
        """``ohne_zensierte`` haelt die am Datenrand abgeschnittenen Trades
        heraus (Befund 152). Nur in einem Lauf angewandt, waere der
        Unterschied der beiden Zahlen teils dieser Schnitt."""
        quelle = self._quelle()

        assert quelle.count("ohne_zensierte(") == 2

    def test_der_zweite_lauf_ist_abschaltbar(self) -> None:
        """Er verdoppelt die Laufzeit - auf Viertelstunden sind das Stunden."""
        quelle = self._quelle()

        assert "if reibungslos:" in quelle
