"""Eine Generation muss auf ihrer Kerzenlaenge ueberhaupt handeln koennen.

``VORGESEHEN`` haelt fest, fuer welche Kerzenlaenge eine Generation gedacht
ist, und ``passt_zum_intervall`` sperrt Fehlpaarungen. Der Grund steht im
Modulkopf von ``research/seeds.py``: Ein Scalp-Katalog auf Tageskerzen kostet
Versuche und hebt die Huerde des Deflated Sharpe fuer alle folgenden - fuer
eine Messung, die nichts bedeutet.

Was die Zuordnung bis Befund 170 nicht hatte, ist eine **Pruefung**. Sie war
eine gepflegte Tabelle, und Generation 8 stand darin auf ``"D"``, obwohl
keines ihrer neun Genome auf Tageskerzen einen einzigen brauchbaren Kandidaten
liefert:

    Gen  vorgesehen  max_hold  cooldown  Perioden-Median
      6        15         32         8         17
      7        15         32         8         20
      8         D         32         8         14     <- Fingerabdruck von 6/7
      9         D          0         0        150
     10         D          0         0        200

Dazu ihr Vokabular: ``fvg_up_pct`` (Kursluecke), VWAP, New Yorker Eroeffnung,
``bars_since_bos``. Kryptomaerkte handeln rund um die Uhr - auf einer
Tageskerze gibt es keine Eroeffnungsluecke und keinen Sitzungsbeginn.

Der Test misst das, statt es zu behaupten: Er faehrt jedes Genom einer
Generation auf der zugeordneten Kerzenlaenge und verlangt, dass **wenigstens
eines** genug handelt, um daraus einen ``Kandidat`` zu bilden. Die Schwelle
ist nicht erfunden - ``Kandidat.aus_trades`` liefert ``None``, wo die Liste
"fuer eine Aussage zu duenn" ist.
"""

from __future__ import annotations

import pytest

from core.config import get_settings
from core.models import Interval
from data.store import CandleStore
from research.seeds import GENERATIONS, VORGESEHEN
from research.suchbudget import Kandidat
from strategy.compiler import compile_genome

SYMBOL = "BTCUSD_BITSTAMP"


@pytest.fixture(scope="module")
def tageslauf():
    """Der **gleiche Weg wie die Messung**, nicht ein einfacherer.

    Der erste Anlauf fuhr einen schlichten Backtest ueber die ganze BTC-Reihe
    und meldete prompt auch Generation 5 als stumm - die Generation, aus der
    der Spitzenkandidat stammt. Sie handelt sehr wohl, nur eben im
    Portfolio-Walk-Forward ueber beide Maerkte am Spot-Punkt, so wie
    ``cli vorratsdecke`` und die Zulassung es rechnen.

    Ein Test, der eine andere Methode benutzt als die Messung, prueft eine
    andere Frage.
    """
    import cli
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )

    einstellungen = get_settings()
    speicher = CandleStore(einstellungen.paths.data_store)
    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    rahmen = common_range({x: speicher.read(x, Interval("D")) for x in symbole})
    configs = cli._spotconfigs(symbole, einstellungen)

    def lauf(genom):
        genom = cli._ohne_hebel(genom)
        return run_portfolio_walkforward(
            rahmen, lambda g=genom: compile_genome(g), configs
        )

    return lauf


def kandidaten(generation: int, tageslauf) -> list[Kandidat]:
    gefunden = []
    for bauen in GENERATIONS[generation]:
        genom = bauen()
        bericht = tageslauf(genom)
        kandidat = Kandidat.aus_trades(genom.name, bericht.all_trades)
        if kandidat is not None:
            gefunden.append(kandidat)
    return gefunden


TAGESGENERATIONEN = sorted(g for g, i in VORGESEHEN.items() if i == "D")


@pytest.mark.daten
@pytest.mark.langsam
@pytest.mark.parametrize("generation", TAGESGENERATIONEN)
def test_jede_tagesgeneration_handelt_auf_tageskerzen(generation, tageslauf) -> None:
    """**Die Pruefung, die Generation 8 an die falsche Stelle gelassen hat.**

    Eine Generation, die auf ihrer eigenen Kerzenlaenge keinen einzigen
    Kandidaten hervorbringt, ist dort nicht zu Hause. Sie kostet dann bei
    jedem Wettbewerb Rechenzeit und - schlimmer - sie fehlt auf der
    Kerzenlaenge, auf der sie hingehoert.
    """
    gefunden = kandidaten(generation, tageslauf)

    assert gefunden, (
        f"Generation {generation} ist auf 'D' zugeordnet, liefert dort aber "
        f"keinen einzigen Kandidaten - siehe Befund 170."
    )


@pytest.mark.daten
@pytest.mark.langsam
def test_die_pruefung_haette_generation_8_gefunden(tageslauf) -> None:
    """Ohne diesen Test prueft der obige nur, dass nichts kaputt ist.

    Generation 8 steht seit Befund 170 auf ``"15"`` und ist damit oben nicht
    mehr dabei. Dass sie auf Tageskerzen tatsaechlich nichts liefert, bleibt
    trotzdem gemessen - sonst waere die Umbuchung eine Behauptung.
    """
    assert VORGESEHEN[8] == "15"
    assert kandidaten(8, tageslauf) == [], (
        "Generation 8 handelt auf Tageskerzen doch - dann war die Umbuchung "
        "in Befund 170 falsch und gehoert zurueckgenommen."
    )


class TestDieZuordnungSelbst:
    def test_jede_generation_ist_zugeordnet(self) -> None:
        """Eine fehlende Zeile heisst ``None`` und damit "laeuft ueberall" -
        das soll eine Entscheidung sein, keine Luecke."""
        assert set(VORGESEHEN) == set(GENERATIONS)

    def test_die_scalp_generationen_stehen_auf_15(self) -> None:
        """6, 7 und 8 teilen den Fingerabdruck: max_hold 32, cooldown 8,
        Perioden um 15. Alle drei gehoeren auf Viertelstunden."""
        assert VORGESEHEN[6] == "15"
        assert VORGESEHEN[7] == "15"
        assert VORGESEHEN[8] == "15"

    def test_generation_8_traegt_die_periodenlaengen_von_6_und_7(self) -> None:
        """**Der strukturelle Beleg neben der Messung.**

        Gemessen wird der Median der Haltedauer. Bei 6, 7 und 8 sind es 32
        Balken, bei den Tagesgenerationen 0 (kein Deckel). Auf Tageskerzen
        waeren 32 Balken ein Monat Haltedauer fuer ein Setup, das auf sechs
        Stunden gedacht ist.
        """
        import statistics

        def haltedauer(gen: int) -> float:
            werte = [b().max_hold_bars for b in GENERATIONS[gen]]
            return statistics.median(werte)

        assert haltedauer(8) == haltedauer(6) == haltedauer(7) == 32
        for tagesgeneration in (5, 9, 10):
            assert haltedauer(tagesgeneration) == 0, tagesgeneration
