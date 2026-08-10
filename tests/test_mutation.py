"""Varianten aus den besten Kandidaten - und ob sie ueberhaupt handelbar sind.

Zwei Tests tragen die Datei:

* ``test_einstieg_und_ausstieg_bleiben_beieinander`` - der Fehler, um den es
  geht. Die Haelfte aller Varianten des Spitzenkandidaten war eine Regel, die
  bei 40 einsteigt und bei 50 aussteigt.
* ``test_unterschiedliche_perioden_bleiben_unterschiedlich`` - der Gegenpol.
  Wo Einstieg und Ausstieg verschiedene Groessen meinen, ist die Asymmetrie
  Absicht und darf nicht eingeebnet werden.
"""

from __future__ import annotations

from research.gates import _feldgrenzen
from research.mutation import mutate


class TestKohaerenteVarianten:
    """**Die Haelfte aller Varianten war eine Regel, die niemand handeln wuerde.**

    Beim Spitzenkandidaten stehen Einstieg und Ausstieg auf demselben SMA(50).
    Wurde nur einer variiert, entstand Einstieg bei 40 und Ausstieg bei 50 -
    150 von 300 Varianten sahen so aus. Jede hat einen Versuch gekostet und die
    Zulassungshuerde fuer alle gehoben.

    Derselbe Fehler steckte einmal in den Nachbarn des Plateau-Gates und war
    dort laengst behoben. Hier stand er noch.
    """

    def test_einstieg_und_ausstieg_bleiben_beieinander(self) -> None:
        import random

        from research.seeds import spitzenkandidat

        vorlage = spitzenkandidat()

        def periode(genome, feld: str):
            bedingungen = getattr(genome, feld)
            if not bedingungen or bedingungen[0].right.kind != "indicator":
                return None
            return bedingungen[0].right.params.get("period")

        assert periode(vorlage, "entry_long") == periode(vorlage, "exit_long")

        rng = random.Random(42)
        geprueft = 0
        for _ in range(200):
            variante = mutate(vorlage, rng)
            if variante is None:
                continue
            ein, aus = periode(variante, "entry_long"), periode(variante, "exit_long")
            if ein is None or aus is None:
                continue
            geprueft += 1
            assert ein == aus, (
                f"Widerspruch: Einstieg SMA({ein}), Ausstieg SMA({aus}) - "
                f"{variante.name}"
            )

        assert geprueft > 50, "zu wenige Varianten geprueft"

    def test_unterschiedliche_perioden_bleiben_unterschiedlich(self) -> None:
        """**Die Gegenprobe.** Wo Einstieg und Ausstieg verschiedene Groessen
        meinen, darf die Korrektur sie nicht zusammenziehen - die Asymmetrie
        ist dort Absicht."""
        import random

        from strategy.genome import (
            Condition,
            Genome,
            Operand,
            Operator,
            StopSpec,
            TargetSpec,
        )

        asymmetrisch = Genome(
            name="Schnell rein, langsam raus",
            rationale="Einstieg auf dem 20er, Ausstieg erst unter dem 100er.",
            entry_long=[
                Condition(
                    left=Operand(kind="price", name="close"),
                    op=Operator.CROSS_ABOVE,
                    right=Operand(kind="indicator", name="sma", params={"period": 20}),
                )
            ],
            exit_long=[
                Condition(
                    left=Operand(kind="price", name="close"),
                    op=Operator.LT,
                    right=Operand(kind="indicator", name="sma", params={"period": 100}),
                )
            ],
            stop=StopSpec(kind="percent", percent=4.0),
            targets=[TargetSpec(rr=10.0, portion=1.0)],
        )

        rng = random.Random(7)
        gesehen = set()
        for _ in range(120):
            variante = mutate(asymmetrisch, rng)
            if variante is None:
                continue
            ein = variante.entry_long[0].right.params.get("period")
            aus = variante.exit_long[0].right.params.get("period")
            gesehen.add((ein, aus))

        assert any(a != b for a, b in gesehen), (
            "Die Asymmetrie wurde eingeebnet - die Korrektur greift zu weit"
        )

    def test_konfluenz_wird_variiert(self) -> None:
        """**Die dritte Stelle mit demselben Muster.**

        Die Konfluenz kam spaeter dazu und wurde nirgends nachgetragen - vorher
        in der Aufwaermphase und in den Nachbarn des Plateau-Gates. Beim
        Spitzenkandidaten steuert sie die Positionsgroesse und war ueber die
        gesamte Suche eingefroren.
        """
        import random

        from research.mutation import SCHRAUBEN
        from research.seeds import spitzenkandidat

        assert "konfluenz" in SCHRAUBEN

        vorlage = spitzenkandidat()
        rng = random.Random(3)
        gefunden = False
        for _ in range(300):
            variante = mutate(vorlage, rng)
            if variante is not None and variante.konfluenz != vorlage.konfluenz:
                gefunden = True
                break

        assert gefunden, "Die Konfluenz wird nie abgewandelt"

    def test_variante_bleibt_gueltig(self) -> None:
        """Jede Abwandlung muss das Schema weiterhin bestehen - sonst faellt
        sie erst im Backtest auf, und dann als Ausnahme."""
        import random

        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        vorlage = spitzenkandidat()
        rng = random.Random(11)
        for _ in range(60):
            variante = mutate(vorlage, rng)
            if variante is not None:
                compile_genome(variante)


class TestZielGrenzen:
    def test_die_mutation_folgt_dem_schema(self) -> None:
        """**Hier stand ``0.3, 20.0`` - dieselben Zahlen wie im Schema.**

        Als die Obergrenze dort stieg, haette die Mutation weiter bei 20
        abgeschnitten und still eine andere Regel befolgt als die Validierung.
        Der Test prueft es an einem Ziel oberhalb der alten Grenze: Es darf
        wachsen, solange das Schema es zulaesst.
        """
        import random

        from research.mutation import _vary_targets
        from strategy.genome import TargetSpec

        _, oben = _feldgrenzen(TargetSpec.model_fields["rr"], standard=(0.3, 20.0))
        hoch = [TargetSpec(rr=oben * 0.5, portion=1.0)]

        gewachsen = []
        for saat in range(40):
            neu = _vary_targets(hoch, random.Random(saat))
            if neu and neu[0].rr > hoch[0].rr:
                gewachsen.append(neu[0].rr)

        assert gewachsen, "Kein Ziel ist gewachsen - die Mutation deckelt zu frueh"
        assert max(gewachsen) <= oben

    def test_die_untere_schranke_wird_nicht_abgerundet(self) -> None:
        """0,3 darf nicht zu 0 werden - ein Ziel bei null waere keins, und das
        Schema lehnt es ab."""
        import random

        from research.mutation import _vary_targets
        from strategy.genome import TargetSpec

        winzig = [TargetSpec(rr=0.3, portion=1.0)]
        for saat in range(40):
            neu = _vary_targets(winzig, random.Random(saat))
            if neu:
                assert neu[0].rr >= 0.3
