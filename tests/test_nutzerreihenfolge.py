"""Die Befehle fuer den Rechner des Nutzers stehen in ihrer Reihenfolge.

**Befund 249.** ``BEIM_NUTZER`` ist eine Liste von Befehlszeilen, und wer eine
Liste von Befehlen sieht, liest sie als Folge. Sie stand aber nicht in einer:

    1. healthcheck
    2. abgleich        <- "Vor jedem Livegang auszufuehren"
    3. backfill
    4. wettbewerb
    5. wettbewerb --ki
    6. funding         <- bis dahin rechnet jede Zahl mit dem Vorgabewert

``abgleich`` an zweiter Stelle und ``funding`` an letzter - beide Male sagt der
Eintrag selbst etwas anderes.

Das ist Befund 167 eine Stufe weiter. Dort war der zweite Schritt Prosa statt
Befehlszeile (*"', dann wettbewerb'"*), und wer ihn kopierte, bekam
``Got unexpected extra argument(s)``. Hier sind es saubere Befehlszeilen in
einer Ordnung, die keine ist.

Was hier gehalten wird
----------------------
Nicht die Liste - sie darf wachsen. Sondern die vier Bedingungen, die aus den
Eintraegen selbst folgen. Eine davon stand schon: ``test_wettbewerb_steht_als_
eigener_schritt`` prueft seit jeher *"Erst laden, dann suchen"*. Die anderen
drei fehlten.
"""

from __future__ import annotations

import pytest

from research.stand import BEIM_NUTZER


def _namen() -> list[str]:
    """Der Befehlsname je Zeile, ``--ki`` als eigener Schritt."""
    aus = []
    for befehl, _ in BEIM_NUTZER:
        teile = befehl.split()
        name = teile[3] if len(teile) > 3 else teile[-1]
        aus.append(f"{name} --ki" if befehl.endswith("--ki") else name)
    return aus


def _stelle(name: str) -> int:
    namen = _namen()
    assert name in namen, f"{name} steht nicht mehr in BEIM_NUTZER: {namen}"
    return namen.index(name)


class TestJedeBedingungKommtAusDemEintrag:
    def test_erst_laden_dann_suchen(self) -> None:
        """Die Bedingung, die es schon gab - hier zum zweiten Mal, weil sie
        zu derselben Frage gehoert wie die drei anderen."""
        assert _stelle("backfill") < _stelle("wettbewerb")

    def test_die_funding_raten_vor_der_suche(self) -> None:
        """Sein Eintrag: *"Bisher rechnet jede Zahl mit dem Vorgabewert, und
        der ist der groesste Kostenblock des Systems."*

        Wer erst sucht und dann die Raten laedt, hat mit dem Vorgabewert
        gesucht - und jeder gepruefte Kandidat hat einen Versuch gekostet.
        """
        assert _stelle("funding") < _stelle("wettbewerb")

    def test_der_abgleich_steht_am_ende(self) -> None:
        """Sein Eintrag sagt es woertlich: *"Vor jedem Livegang
        auszufuehren."* Ein Livegang kommt nach der Suche, nicht davor."""
        assert _stelle("abgleich") == len(_namen()) - 1

    def test_zuerst_wird_der_betriebspunkt_geklaert(self) -> None:
        """``healthcheck`` beantwortet, ob das Konto Perpetuals anbietet - und
        daran haengen zwei Gates. Alles Weitere misst auf einem Punkt, der
        dann feststeht."""
        assert _stelle("healthcheck") == 0

    def test_der_ki_weg_steht_neben_dem_gewoehnlichen(self) -> None:
        """Zwei Wege durch denselben Schritt, nicht zwei Schritte."""
        assert _stelle("wettbewerb --ki") == _stelle("wettbewerb") + 1


class TestWasDieBedingungenBelegt:
    """Die Saetze, aus denen die Ordnung folgt - damit sie nicht verschwinden."""

    @staticmethod
    def _warum(name: str) -> str:
        return next(w for b, w in BEIM_NUTZER if name in b)

    def test_der_abgleich_sagt_wann(self) -> None:
        assert "Vor jedem Livegang" in self._warum("abgleich")

    def test_funding_sagt_warum_es_vorher_gehoert(self) -> None:
        assert "Vorgabewert" in self._warum("funding")

    def test_backfill_sagt_dass_ohne_es_nichts_geht(self) -> None:
        assert "Ohne sie kann nichts zugelassen werden" in self._warum("backfill")


class TestKeineDoppelten:
    def test_jeder_befehl_steht_einmal(self) -> None:
        namen = _namen()

        assert len(namen) == len(set(namen)), namen

    @pytest.mark.parametrize(
        "name", ["healthcheck", "backfill", "funding", "wettbewerb", "abgleich"]
    )
    def test_die_erwarteten_schritte_sind_da(self, name: str) -> None:
        assert name in _namen()
