"""Woran ein Gate wirklich scheitert - und wer es beheben kann.

Zwei Tests tragen diese Datei:

``test_ein_wert_ueber_der_schwelle_kann_trotzdem_durchfallen`` - Der Anlass.
Die Messlatte liegt um das 3,8-fache **ueber** ihrer Schwelle und faellt
durch, weil sie eine zweite Bedingung hat. Ohne diesen Fall ist die Tabelle
nicht bloss unvollstaendig, sondern zeigt in die falsche Richtung.

``test_vier_offene_gates_sind_nicht_vier_aufgaben`` - Die zweite Sache, die
dabei auffiel: Ein Gate liegt beim Nutzer, eines ist durchgemessen, zwei sind
nie untersucht worden. Der Abstand allein sagt darueber nichts.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.gatelage import (
    DURCHGEMESSENE_GATES,
    WIRTSCHAFTLICHE_GATES,
    Art,
    Gatelage,
    Hindernis,
    ordne,
)


@dataclass
class FakeErgebnis:
    name: str
    value: float
    threshold: float
    message: str
    passed: bool


#: Die vier offenen Gates des Bestands, wie sie am 17.08.2026 gemessen wurden.
GEMESSEN: tuple[FakeErgebnis, ...] = (
    FakeErgebnis(
        "Messlatte", 166.143, 43.639,
        "Strategie +166.1 % bei 10.6 % Rueckgang (+13.5 % p.a.) - "
        "risikobereinigt besser, aber nur 13.5 % im Jahr. Unter 15 % lohnt "
        "der Betrieb nicht.",
        False,
    ),
    FakeErgebnis(
        "Schlechtestes Jahr", -10.320, -10.000,
        "Wer zum unguenstigsten Zeitpunkt eingestiegen waere, stuende nach "
        "zwoelf Monaten bei -10.3 %.",
        False,
    ),
    FakeErgebnis(
        "Deflated Sharpe", 0.783, 0.950,
        "Nach 177 getesteten Hypothesen ist der Vorteil nur zu 78.3% echt.",
        False,
    ),
    FakeErgebnis(
        "Parameter-Plateau", 0.500, 0.600,
        "alle gemeinsam traegt nur 50% - in dieser Richtung steht die "
        "Strategie auf einer Nadelspitze.",
        False,
    ),
    FakeErgebnis("Drawdown", 10.640, 12.000, "", True),
    FakeErgebnis("Out-of-Sample-Sharpe", 1.473, 1.000, "", True),
)


class TestIrrefuehrung:
    def test_ein_wert_ueber_der_schwelle_kann_trotzdem_durchfallen(self) -> None:
        """**Der Test, der diese Datei traegt.**

        166,1 gegen 43,6 liest sich als "um das 3,8-fache verfehlt". Es ist
        das Gegenteil: risikobereinigt um das 3,8-fache uebererfuellt. Das
        Gate faellt an einer zweiten Bedingung durch, die im Zahlenpaar nicht
        vorkommt - 13,5 % Jahresrendite gegen geforderte 15 %.
        """
        lage = ordne(GEMESSEN)
        messlatte = next(h for h in lage.hindernisse if h.name == "Messlatte")

        assert messlatte.wert > messlatte.schwelle
        assert not messlatte.zahlen_erklaeren_es
        assert lage.irrefuehrende == [messlatte]
        assert "in die falsche Richtung" in lage.urteil()

    def test_ein_normales_gate_erklaert_sich_durch_die_zahlen(self) -> None:
        """Gegenprobe: Beim Deflated Sharpe sagt das Zahlenpaar genau, woran
        es liegt - 0,783 unter 0,950. Dort ist die Warnung fehl am Platz."""
        lage = ordne(GEMESSEN)
        dsr = next(h for h in lage.hindernisse if h.name == "Deflated Sharpe")

        assert dsr.wert < dsr.schwelle
        assert dsr.zahlen_erklaeren_es

    def test_nur_wirtschaftliche_gates_koennen_irrefuehren(self) -> None:
        """Ein gemessenes Gate ueber seiner Schwelle waere ein Fehler in der
        Auswertung, keine zweite Bedingung - und wird nicht wegerklaert."""
        seltsam = Hindernis(
            name="Irgendwas", wert=5.0, schwelle=1.0,
            botschaft="", art=Art.OFFEN,
        )

        assert seltsam.zahlen_erklaeren_es


class TestEinordnung:
    def test_vier_offene_gates_sind_nicht_vier_aufgaben(self) -> None:
        """**Der zweite tragende Test.**

        Fuenfzehn Laeufe gingen an den Deflated Sharpe. Zwei Gates daneben
        sind in dieser Zeit nie angesehen worden, und eines liegt ueberhaupt
        nicht in meiner Hand. Der Abstand in der Tabelle sagt darueber nichts.
        """
        lage = ordne(GEMESSEN)

        assert len(lage.hindernisse) == 4, "bestandene zaehlen nicht mit"
        assert [h.name for h in lage.offen] == [
            "Schlechtestes Jahr", "Parameter-Plateau"
        ]
        assert [h.name for h in lage.beim_nutzer] == ["Messlatte"]
        assert [h.name for h in lage.abgeschlossen] == ["Deflated Sharpe"]

    def test_das_urteil_trennt_die_drei_arten(self) -> None:
        urteil = ordne(GEMESSEN).urteil()

        assert "nicht 4 Aufgaben" in urteil
        assert "Geschaeftsentscheidung" in urteil
        assert "durchgemessen" in urteil
        assert "Hier liegt die Arbeit: Schlechtestes Jahr, Parameter-Plateau" in urteil

    def test_die_fundstelle_wird_mitgenannt(self) -> None:
        """Ein Gate fuer durchgemessen zu erklaeren, ohne zu sagen wo, waere
        eine Behauptung."""
        lage = ordne(GEMESSEN)
        dsr = next(h for h in lage.abgeschlossen)

        assert dsr.fundstelle == DURCHGEMESSENE_GATES["Deflated Sharpe"]
        assert f"Nr. {dsr.fundstelle}" in lage.urteil()
        assert f"Nr. {dsr.fundstelle}" in dsr.als_zeile()

    def test_unbekannte_gates_gelten_als_offen(self) -> None:
        """**Die sichere Richtung.** Ein Gate, das weder als wirtschaftlich
        noch als durchgemessen gefuehrt wird, ist Arbeit - nicht erledigt.
        Andersherum verschwaende ein neues Gate stillschweigend."""
        neu = ordne([FakeErgebnis("Ganz neues Gate", 1.0, 2.0, "faellt", False)])

        assert neu.offen[0].art is Art.OFFEN
        assert "Ganz neues Gate" not in str(WIRTSCHAFTLICHE_GATES)

    def test_ohne_hindernisse_ist_alles_bestanden(self) -> None:
        leer = ordne([FakeErgebnis("Drawdown", 10.0, 12.0, "", True)])

        assert leer.hindernisse == []
        assert leer.urteil() == "Alle Gates bestanden."
        assert leer.tabelle() == "Alle Gates bestanden."

    def test_wenn_nur_noch_fremdes_offen_ist_steht_es_da(self) -> None:
        """Bleiben nur Gates uebrig, die beim Nutzer liegen oder gemessen
        sind, ist das eine eigene Lage - und sie gehoert benannt, statt als
        'noch offen' weitergefuehrt zu werden."""
        lage = Gatelage(
            hindernisse=[
                Hindernis("Messlatte", 166.0, 43.0, "", Art.WIRTSCHAFTLICH),
                Hindernis("Deflated Sharpe", 0.78, 0.95, "", Art.DURCHGEMESSEN, 89),
            ]
        )

        assert lage.offen == []
        assert "Kein Gate mehr, an dem eine offene Frage haengt" in lage.urteil()


class TestTabelle:
    def test_die_botschaft_steht_unter_jeder_zeile(self) -> None:
        text = ordne(GEMESSEN).tabelle()

        assert "Unter 15 % lohnt der Betrieb nicht" in text
        assert "Nadelspitze" in text

    def test_bestandene_gates_stehen_nicht_darin(self) -> None:
        text = ordne(GEMESSEN).tabelle()

        assert "Drawdown" not in text
        assert "Out-of-Sample-Sharpe" not in text
