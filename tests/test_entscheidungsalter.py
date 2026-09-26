"""Wie alt die Zahlen sind, auf denen eine Entscheidung steht - Befund 334.

Zwei der elf Gates sind am Spot-Punkt offen, und beide liegen als
Geschaeftsentscheidung beim Nutzer. Die eine - die Mindestrendite von 15 % -
haengt an einer gemessenen Tabelle, die ``cli vereinbar --spot`` ausgibt:

     Stellung    Rendite  Rueckgang  Urteil
         19.3     14.34%      9.87%  Rendite fehlt   <- der Bestand
           21     15.30%     11.66%  alle erfuellt
         21.5     15.65%     11.87%  alle erfuellt
           22     16.17%     11.85%  alle erfuellt

Diese Tabelle liest **gespeicherte Berichte**, keine frischen Laeufe. Der
juengste Machbarkeitsbericht ist vom 14.09.; ``backtest/walkforward._combine``
hat sich am 20.09. geaendert (Befund 315) - die Funktion, aus deren verketteter
Kapitalkurve Rendite und Rueckgang gelesen werden.

Befund 315 hat gegengerechnet, dass **keine Zahl sich bewegt**: "Rendite, CAGR,
Rueckgang, Sharpe, Nettogewinn und alle elf Gatewerte sind vorher wie nachher
bitgleich." Die Tabelle ist also gueltig.

**Nur konnte man ihr das nicht ansehen.** Um es festzustellen, waren vier
Schritte von Hand noetig: Berichtsdatum nachsehen, Befund-315-Datum nachsehen,
pruefen was 315 angefasst hat, und dessen Gegenrechnung lesen. Befund 324 hat
genau dafuer das Alter in ``berichtslage`` nachgetragen - mit der Begruendung,
ein Datum unter sieben anderen lese sich nicht wie eine Warnung, "30 Tage alt"
schon. Die Entscheidungstabelle trug nicht einmal das Datum.

Der Satz behauptet nicht, dass die Zahlen falsch sind. Er sagt, wie weit der
Schluss traegt.
"""

from __future__ import annotations

from datetime import date

import pytest

from research.vereinbar import Messpunkt, Vorrat


def _punkt(stellung: float, gemessen: str = "2026-09-14_005951") -> Messpunkt:
    return Messpunkt(
        stellung=stellung,
        werte={"cagr": 15.3, "rueckgang": 11.66},
        betriebspunkt="Spot (kein Hebel, kein Funding)",
        gemessen=gemessen,
    )


class TestDasAlterEinesPunktes:
    def test_es_kommt_aus_dem_dateinamen(self) -> None:
        punkt = _punkt(21.0, "2026-09-14_005951")

        assert punkt.alter(date(2026, 9, 26)) == 12

    def test_ohne_datum_gibt_es_kein_alter(self) -> None:
        """Eine geratene Angabe waere schlimmer als keine - dieselbe Regel wie
        in ``berichtslage`` (Befund 324)."""
        assert _punkt(21.0, "").alter(date(2026, 9, 26)) is None
        assert _punkt(21.0, "von-hand").alter(date(2026, 9, 26)) is None

    def test_am_messtag_ist_es_null(self) -> None:
        assert _punkt(21.0, "2026-09-14_005951").alter(date(2026, 9, 14)) == 0


class TestDerSatzUeberDasAlter:
    def test_bei_einem_datum_nennt_er_eine_zahl(self) -> None:
        vorrat = Vorrat(punkte=[_punkt(21.0), _punkt(21.5)])

        satz = vorrat.altersatz(date(2026, 9, 26))

        assert "12 Tage alt" in satz
        assert "bis" not in satz.split("Jede")[0]

    def test_bei_mehreren_nennt_er_die_spanne(self) -> None:
        vorrat = Vorrat(
            punkte=[
                _punkt(21.0, "2026-09-14_005951"),
                _punkt(21.5, "2026-08-22_070452"),
            ]
        )

        satz = vorrat.altersatz(date(2026, 9, 26))

        assert "12 bis 35 Tage alt" in satz

    def test_er_nennt_die_kapitalkurve_als_das_bewegliche_teil(self) -> None:
        """Nicht irgendein "koennte veraltet sein": Rendite und Rueckgang
        kommen aus der verketteten Kurve, und genau die hat Befund 315
        angefasst."""
        satz = Vorrat(punkte=[_punkt(21.0)]).altersatz(date(2026, 9, 26))

        assert "Kapitalkurve" in satz
        assert "315" in satz

    def test_er_behauptet_nicht_dass_die_zahlen_falsch_sind(self) -> None:
        """Befund 315 hat gegengerechnet, dass keine Zahl sich bewegt. Ein Satz,
        der mehr behauptet, waere selbst eine ungemessene Aussage."""
        satz = Vorrat(punkte=[_punkt(21.0)]).altersatz(date(2026, 9, 26)).casefold()

        for wort in ("falsch", "ungueltig", "veraltet", "nicht zu benutzen"):
            assert wort not in satz

    def test_ohne_datierte_punkte_steht_nichts(self) -> None:
        """Eine Warnung, die immer angeht, ist keine (Befund 324)."""
        assert Vorrat(punkte=[_punkt(21.0, "")]).altersatz(date(2026, 9, 26)) == ""

    def test_und_ohne_punkte_auch_nicht(self) -> None:
        assert Vorrat().altersatz(date(2026, 9, 26)) == ""


class TestDerBefehlZeigtIhn:
    """Befund 160 und 208 waren dieselbe Bauart: eine gepflegte Angabe, die an
    keiner Stelle angezeigt wurde."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "vereinbar"
        )

    def test_vereinbar_gibt_das_alter_aus(self) -> None:
        assert "altersatz" in self._quelle()

    def test_und_zwar_nach_dem_urteil(self) -> None:
        """Vor dem Urteil stuende es im Weg; danach ist es die Einordnung."""
        quelle = self._quelle()

        assert quelle.index("lage.urteil()") < quelle.index("altersatz")


@pytest.mark.daten
def test_die_echten_berichte_tragen_ein_datum() -> None:
    """Am Bestand gemessen und nicht nur an Attrappen: Wenn die Schreiber ihren
    Zeitstempel aendern, faellt das hier auf und nicht in einer Entscheidung."""
    from pathlib import Path

    from research.vereinbar import lade

    vorrat = lade(
        Path("reports") / "machbarkeit", regler="Vola-Ziel", betriebspunkt="Spot"
    )
    if not vorrat.punkte:
        pytest.skip("keine Spot-Stellungen im Berichtsordner")

    datiert = [p for p in vorrat.punkte if p.alter() is not None]

    assert datiert == vorrat.punkte
    assert vorrat.altersatz() != ""
