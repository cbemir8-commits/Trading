"""Ab wann geladen gehoert - und die sechs gemessenen Fenster als Daten.

**Befund 212.** Die Tabelle aus Befund 133 stand seit ihrer Messung nur im
Kopf von ``research/historie.py``. Wer die Sammelrate oder den Abstand zur
Schwelle nachrechnen wollte, musste sie abtippen - dieselbe Lage wie bei
``kostenanteil`` (Befund 187) und der Rangkorrelation (Befund 195).

Und die Vorgabe aller Ladebefehle war ``2020-03-30``, fuer Tageskerzen die
zweitschlechteste der sechs Stufen.
"""

from __future__ import annotations

import pytest

from research.historie import (
    AB_FEINKERZEN,
    AB_TAGESKERZEN,
    GEMESSEN,
    empfohlener_start,
)


class TestDieGemesseneKurve:
    """Die Zahlen aus dem Kopf des Moduls - jetzt nachrechenbar."""

    def test_die_referenz_ist_das_laengste_fenster(self) -> None:
        ref = GEMESSEN.referenz

        assert ref is not None
        assert ref.von == "2017-08-16"
        assert ref.tage == 3277

    def test_die_sammelrate_kommt_wieder_heraus(self) -> None:
        """Der Kopf nennt 44,7 unabhaengige Beobachtungen je 1000 Tage."""
        assert GEMESSEN.sammelrate() == pytest.approx(44.7, abs=0.05)

    def test_der_abstand_zur_schwelle_kommt_wieder_heraus(self) -> None:
        """29 Beobachtungen, rund 649 Tage - hochgerechnet, nicht gemessen."""
        assert GEMESSEN.fehlende_beobachtungen() == 29
        assert GEMESSEN.fehlende_tage() == 649

    def test_die_guete_haengt_nicht_an_der_laenge(self) -> None:
        """Die Kernaussage von Befund 133, jetzt aus den Daten statt aus Prosa."""
        assert GEMESSEN.guete_haengt_an_der_laenge() is False

    def test_der_deflated_sharpe_haengt_fast_nur_an_n(self) -> None:
        stufen = GEMESSEN.sortiert

        assert stufen[0].dsr == pytest.approx(0.8640)
        assert stufen[-1].dsr == pytest.approx(0.1347)
        # Die Guete streut dabei um 0,27 und faellt nicht mit.
        assert max(s.guete for s in stufen) - min(s.guete for s in stufen) < 0.06

    def test_die_rohen_trades_uebersteigen_nie_die_effektiven(self) -> None:
        """Der Datentyp erzwingt es - hier steht, dass es auch gilt."""
        for s in GEMESSEN.stufen:
            assert s.effektiv <= s.trades, s.von


class TestDerEmpfohleneStart:
    """**Der Fehler, den das behebt.** Ein Datum fuer alle Kerzenlaengen."""

    def test_tageskerzen_bekommen_das_laengste_fenster(self) -> None:
        assert empfohlener_start("D") == AB_TAGESKERZEN == "2017-08-16"

    def test_feinkerzen_behalten_ihr_datum(self) -> None:
        """Dort ist es keine Wahl, sondern die Reichweite der Reihe."""
        assert empfohlener_start("15") == AB_FEINKERZEN == "2020-03-30"
        assert empfohlener_start("60") == AB_FEINKERZEN

    def test_die_schreibweise_ist_egal(self) -> None:
        assert empfohlener_start("d") == AB_TAGESKERZEN

    def test_was_die_alte_vorgabe_gekostet_haette(self) -> None:
        """**Die Messung, die den Wechsel traegt.**

        Beide Startdaten stehen als gemessene Stufe da. Der Unterschied ist
        nicht Geschmack: Es sind 957 Tage, 49 unabhaengige Beobachtungen und
        ein Gate - und der Deflated Sharpe, das einzige noch offene Gate,
        faellt von 0,8640 auf 0,2969.
        """
        stufen = {s.von: s for s in GEMESSEN.stufen}
        gut, schlecht = stufen[AB_TAGESKERZEN], stufen[AB_FEINKERZEN]

        assert gut.tage - schlecht.tage == 957
        assert gut.effektiv - schlecht.effektiv == 49
        assert gut.bestanden == 9 and schlecht.bestanden == 8
        assert gut.dsr > schlecht.dsr * 2.9

    def test_die_referenz_ist_auch_der_empfohlene_start(self) -> None:
        """Sonst empfiehlt das Modul etwas anderes, als es selbst misst."""
        assert GEMESSEN.referenz is not None
        assert GEMESSEN.referenz.von == empfohlener_start("D")
