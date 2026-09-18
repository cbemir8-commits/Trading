"""Was ein Katalogdurchlauf kostet - Befund 296.

Zweimal hintereinander ist die Dauer eines Laufs **geschaetzt** worden. Die
erste Schaetzung war siebenmal zu hoch und hat zwei Laeufe lang verhindert,
dass der 15-Minuten-Katalog ueberhaupt angesehen wurde; die zweite war
sechsmal zu niedrig, weil sie nur den Walk-Forward zaehlte und die Gates
vergass.

Diese Tests halten fest, dass hier gemessene Zahlen stehen - und dass fuer
eine ungemessene Kerzenlaenge **keine** Zahl herauskommt.
"""

from __future__ import annotations

import pytest

from research.laufkosten import MESSUNGEN, auskunft, dauer


class TestDieGemessenenZahlen:
    def test_beide_kerzenlaengen_sind_gemessen(self) -> None:
        assert set(MESSUNGEN) == {"1d", "15m"}
        for kosten in MESSUNGEN.values():
            assert kosten.kerzen > 0
            assert kosten.je_genom > 0
            assert kosten.gemessen_in > 0, "ohne Fundstelle waere es eine Behauptung"

    def test_die_kurze_kerze_kostet_mehr(self) -> None:
        """Nicht selbstverstaendlich - und der Grund, warum die erste
        Schaetzung danebenlag: Sie rechnete mit dem Kerzenverhaeltnis."""
        assert MESSUNGEN["15m"].je_genom > MESSUNGEN["1d"].je_genom

    def test_aber_nicht_im_verhaeltnis_der_kerzen(self) -> None:
        """**Der eigentliche Fund.** 69-mal so viele Kerzen, 38-mal so viel
        Zeit - der teure Teil haengt an den Trades, nicht an den Kerzen.

        Wer die Kerzenzahl hochrechnet, kommt zu hoch heraus und laesst eine
        machbare Messung liegen. Genau das ist passiert.
        """
        kerzen = MESSUNGEN["15m"].kerzen / MESSUNGEN["1d"].kerzen
        zeit = MESSUNGEN["15m"].je_genom / MESSUNGEN["1d"].je_genom

        assert kerzen > 60
        assert zeit < kerzen, f"Kerzen x{kerzen:.0f}, Zeit x{zeit:.0f}"


class TestDieAuskunft:
    def test_sie_rechnet_mit_der_zahl_der_genome(self) -> None:
        assert dauer("1d", 30) == pytest.approx(30 * MESSUNGEN["1d"].je_genom)
        assert dauer("1d", 60) == 2 * dauer("1d", 30)

    def test_sie_nennt_die_einheit_nach_groesse(self) -> None:
        assert "Sekunden" in auskunft("1d", 3)
        assert "Minuten" in auskunft("1d", 30)
        assert "Stunden" in auskunft("15m", 39)

    def test_sie_nennt_die_fundstelle(self) -> None:
        text = auskunft("15m", 39)

        assert f"Befund {MESSUNGEN['15m'].gemessen_in}" in text
        assert "je Genom" in text

    def test_der_satz_bleibt_ein_satz(self) -> None:
        """Ein erster Anlauf setzte den Tausenderpunkt mit einem pauschalen
        ``replace(",", ".")`` auf den fertigen Satz - und machte aus dem Komma
        hinter "Genome" einen Punkt."""
        text = auskunft("15m", 39)

        assert "39 Genome, rund" in text
        assert "225.341 Kerzen" in text


class TestWasNichtGemessenIst:
    """**Die Verweigerung.** Zwei Punkte legen eine Gerade fest, und eine
    Gerade durch zwei Punkte ist in diesem Projekt seit Befund 285 kein
    Argument."""

    def test_eine_ungemessene_kerzenlaenge_bekommt_keine_zahl(self) -> None:
        assert dauer("1h", 20) is None
        assert dauer("4h", 20) is None

    def test_und_der_text_sagt_warum(self) -> None:
        text = auskunft("1h", 20)

        assert "nicht gemessen" in text
        assert "nichts hochgerechnet" in text
        assert "1d" in text and "15m" in text, "die bekannten werden genannt"

    def test_keine_zahl_heisst_auch_keine_stunden(self) -> None:
        """Sonst stuende dort eine Dauer ohne Grundlage."""
        text = auskunft("1h", 20)

        for wort in ("Sekunden", "Minuten", "Stunden"):
            assert wort not in text

    def test_negative_genome_sind_keine_auskunft(self) -> None:
        assert dauer("1d", -1) is None
