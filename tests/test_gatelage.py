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
        """**Der zweite tragende Test.** Die Einsicht aus Befund 91 steht
        unveraendert: Der Abstand in der Tabelle sagt nichts ueber die Art des
        Hindernisses.

        **Drei Arten bis Befund 460, vier seit 461.** Die beiden Gates, die
        hier als "nie untersucht" standen, sind gemessen: 'Schlechtestes
        Jahr' faellt nur am Perpetual-Punkt (336/386/420), beim
        'Parameter-Plateau' hat 92/163 die Form berichtigt und 313 gemessen,
        dass die Nachbarn auf stillgelegten Laeufen standen. Was bei beiden
        bleibt, ist eine Entscheidung ueber den Messaufbau.

        Diese Zeile hat mich ueber fuenf Arbeitsgaenge an zwei Gates
        geschickt, an denen keine Messung offen ist.
        """
        lage = ordne(GEMESSEN)

        assert len(lage.hindernisse) == 4, "bestandene zaehlen nicht mit"
        assert [h.name for h in lage.beim_nutzer] == ["Messlatte"]
        assert [h.name for h in lage.abgeschlossen] == ["Deflated Sharpe"]
        assert [h.name for h in lage.entschieden_werden] == [
            "Schlechtestes Jahr", "Parameter-Plateau"
        ]
        assert lage.offen == [], "heute haengt an keinem Gate eine offene Frage"

    def test_das_urteil_trennt_die_vier_arten(self) -> None:
        urteil = ordne(GEMESSEN).urteil()

        assert "nicht 4 Aufgaben" in urteil
        assert "Geschaeftsentscheidung" in urteil
        assert "durchgemessen" in urteil
        assert "eine **Entscheidung** ueber den Messaufbau" in urteil
        assert "Hier liegt die Arbeit" not in urteil

    def test_und_sagt_dass_dabei_nichts_gelockert_wird(self) -> None:
        """**Die Zusicherung gegen den naheliegenden Verdacht** (Befund 461):
        Ein Gate zur Entscheidungssache zu erklaeren sieht aus wie eine
        Aufwertung. Es ist keine - es faellt weiter durch, und das Urteil sagt
        es."""
        lage = ordne(GEMESSEN)
        urteil = lage.urteil()

        assert "das Gate bleibt bis dahin durchgefallen" in urteil
        assert "lockert das Gate" in urteil
        # Und mechanisch: eingeordnet wird, nicht geurteilt.
        for h in lage.entschieden_werden:
            quelle = next(r for r in GEMESSEN if r.name == h.name)
            assert not quelle.passed
            assert (h.wert, h.schwelle) == (
                float(quelle.value), float(quelle.threshold)
            )

    def test_ein_unbekanntes_gate_bleibt_offen(self) -> None:
        """Die Gegenprobe: Die vierte Art ist eine **Liste**, keine Regel.
        Was in keiner steht, ist weiterhin Arbeit."""
        fremd = FakeErgebnis("Irgendein neues Gate", 1.0, 2.0, "", passed=False)
        lage = ordne([fremd])

        assert [h.art for h in lage.hindernisse] == [Art.OFFEN]
        assert "Hier liegt die Arbeit: Irgendein neues Gate" in lage.urteil()

    def test_die_fundstelle_wird_mitgenannt(self) -> None:
        """Ein Gate fuer durchgemessen zu erklaeren, ohne zu sagen wo, waere
        eine Behauptung."""
        lage = ordne(GEMESSEN)
        dsr = next(h for h in lage.abgeschlossen)
        zuerst, zuletzt = DURCHGEMESSENE_GATES["Deflated Sharpe"]

        assert (dsr.zuerst, dsr.fundstelle) == (zuerst, zuletzt)
        assert f"Nr. {dsr.fundstelle}" in lage.urteil()
        assert f"Nr. {dsr.fundstelle}" in dsr.als_zeile()

    def test_und_zwar_die_letzte_zuerst(self) -> None:
        """**Befund 293.** Hier stand nur die erste Messung - Befund 89, rund
        zweihundert Befunde alt. Ein Leser schlaegt nach, was der Bericht
        nennt, und findet damit den Stand von damals.

        Dieselbe Falle wie in Befund 130, und ``Richtung`` sagt es seit
        damals: *"Wer eine Fundstelle nennt, muss die letzte nennen."*
        """
        lage = ordne(GEMESSEN)
        dsr = next(h for h in lage.abgeschlossen)

        assert dsr.fundstelle > dsr.zuerst, "die massgebliche ist die spaetere"
        assert dsr.stelle == f"Nr. {dsr.fundstelle}, zuerst {dsr.zuerst}"
        assert dsr.stelle in dsr.als_zeile()
        assert dsr.stelle in lage.urteil()

    def test_ohne_nachmessung_steht_dort_eine_zahl(self) -> None:
        """Wo erste und letzte Messung dieselbe sind, waere "(zuerst X)" nur
        Laerm."""
        from research.gatelage import Art, Hindernis

        einzeln = Hindernis(
            name="X", wert=1.0, schwelle=2.0, botschaft="",
            art=Art.DURCHGEMESSEN, fundstelle=89, zuerst=89,
        )

        assert einzeln.stelle == "Nr. 89"
        assert "zuerst" not in einzeln.als_zeile()

    def test_offene_gates_haben_keine_stelle(self) -> None:
        from research.gatelage import Art, Hindernis

        offen = Hindernis(
            name="X", wert=1.0, schwelle=2.0, botschaft="", art=Art.OFFEN
        )

        assert offen.stelle == ""

    def test_weitere_laeufe_heisst_an_diesem_gate(self) -> None:
        """**Die zweite Haelfte von Befund 293.**

        Hier stand "Weitere Laeufe daran kosten Zeit ohne offene Frage", und
        das las sich als "hier ist nichts mehr zu holen". Gemeint waren Laeufe
        **am Gate** - Empfindlichkeits- und Eichungsrechnungen. Was offen
        bleibt, ist ein Kandidat: Befund 291 hat gemessen, dass die noetige
        Qualitaet je Trade innerhalb dessen liegt, was der Katalog gezeigt hat
        - nur nie bei einer grossen Stichprobe.
        """
        urteil = ordne(GEMESSEN).urteil()

        assert "an diesem Gate" in urteil
        assert "ein Kandidat und keine" in urteil

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
        assert "Kein Gate, an dem eine offene Frage haengt" in lage.urteil()
        assert "aendern den Zustand nicht" in lage.urteil()


class TestTabelle:
    def test_die_botschaft_steht_unter_jeder_zeile(self) -> None:
        text = ordne(GEMESSEN).tabelle()

        assert "Unter 15 % lohnt der Betrieb nicht" in text
        assert "Nadelspitze" in text

    def test_bestandene_gates_stehen_nicht_darin(self) -> None:
        text = ordne(GEMESSEN).tabelle()

        assert "Drawdown" not in text
        assert "Out-of-Sample-Sharpe" not in text


class TestArbeitAmBetriebspunkt:
    """Wieviel der genannten Arbeit an einer offenen Frage haengt.

    Gemessen am 01.09.2026 mit ``cli stand``, beide Punkte, alle elf Gates:

        Perpetual  7/11   offen: Messlatte, Schlechtestes Jahr,
                                 Deflated Sharpe, Parameter-Plateau
        Spot       9/11   offen: Messlatte, Deflated Sharpe

    Berichtet wird Perpetual, weil die Voraussetzung offen ist. Die
    Aufgabenliste kam bis Befund 164 allein daraus - und nannte genau die
    zwei Gates, die unter Spot bestehen.
    """

    def test_offene_gates_des_anderen_punktes_werden_markiert(self) -> None:
        lage = ordne(
            GEMESSEN,
            zweitpunkt="Spot",
            dort_offen=("Messlatte", "Deflated Sharpe"),
        )

        assert [h.name for h in lage.am_punkt] == [
            "Schlechtestes Jahr", "Parameter-Plateau",
        ]

    def test_das_urteil_sagt_es_dazu(self) -> None:
        """**Der Kern der Sache.** Wer eine Aufgabe genannt bekommt, muss
        erfahren, dass sie sich mit einer Antwort erledigt.

        Seit Befund 461 stehen diese zwei Gates als Entscheidungssache da und
        nicht mehr unter 'Hier liegt die Arbeit' - der Absatz zum
        Betriebspunkt gilt unveraendert und rechnet deshalb ueber
        ``anstehend`` statt ueber ``offen``."""
        text = ordne(
            GEMESSEN,
            zweitpunkt="Spot",
            dort_offen=("Messlatte", "Deflated Sharpe"),
        ).urteil()

        assert "eine **Entscheidung** ueber den Messaufbau" in text
        assert "Die ganze Arbeit haengt am Betriebspunkt." in text
        assert "Spot" in text

    def test_ohne_zweiten_punkt_bleibt_alles_wie_vorher(self) -> None:
        """Die Markierung darf nicht aus dem Nichts entstehen: Ohne gemessenen
        Zweitpunkt steht kein Wort davon da."""
        text = ordne(GEMESSEN).urteil()

        assert "Schlechtestes Jahr" in text
        assert "Parameter-Plateau" in text
        assert "Betriebspunkt" not in text
        assert ordne(GEMESSEN).am_punkt == []

    def test_ein_name_ohne_gemessene_liste_wird_abgewiesen(self) -> None:
        """**Sonst waere die Auskunft frei erfunden.**

        Ein Zweitpunkt ohne ``dort_offen`` liesse jedes Gate als
        punktabhaengig durchgehen, weil die Menge leer ist - eine Aussage
        ueber eine Messung, die es nicht gab.
        """
        import pytest

        with pytest.raises(ValueError, match="gehoeren zusammen"):
            ordne(GEMESSEN, zweitpunkt="Spot")
        with pytest.raises(ValueError, match="gehoeren zusammen"):
            ordne(GEMESSEN, dort_offen=("Messlatte",))

    def test_gates_die_an_beiden_punkten_fallen_sind_keine_folge_der_wahl(
        self,
    ) -> None:
        """Faellt ein offenes Gate auch am anderen Punkt durch, bleibt es
        Arbeit - und darf nicht mitmarkiert werden."""
        lage = ordne(
            GEMESSEN,
            zweitpunkt="Spot",
            dort_offen=(
                "Messlatte", "Deflated Sharpe", "Schlechtestes Jahr",
            ),
        )

        assert [h.name for h in lage.am_punkt] == ["Parameter-Plateau"]
        text = lage.urteil()
        assert "1 davon haengen am Betriebspunkt." in text
        assert "Die ganze Arbeit" not in text

    def test_haengt_nichts_am_punkt_steht_auch_nichts_da(self) -> None:
        lage = ordne(
            GEMESSEN,
            zweitpunkt="Spot",
            dort_offen=tuple(g.name for g in GEMESSEN if not g.passed),
        )

        assert lage.am_punkt == []
        assert "Betriebspunkt" not in lage.urteil()


class TestDieVierteArtIstBelegt:
    """Befund 461. Ein Gate zur Entscheidungssache zu erklaeren entzieht es
    der Arbeit - deshalb steht es in einer **Liste** und nicht in einer Regel,
    und deshalb muss jeder Eintrag belegt sein.

    Dieselbe Pflicht wie bei ``DURCHGEMESSENE_GATES`` seit Befund 293: Wer
    eine Fundstelle nennt, muss die letzte nennen.
    """

    def test_jeder_eintrag_nennt_zwei_fundstellen(self) -> None:
        from research.gatelage import ENTSCHEIDUNGSGATES

        assert ENTSCHEIDUNGSGATES
        for name, (zuerst, zuletzt) in ENTSCHEIDUNGSGATES.items():
            assert zuerst > 0, name
            assert zuletzt >= zuerst, f"{name}: {zuletzt} vor {zuerst}"

    def test_und_die_gibt_es_im_laborbuch(self) -> None:
        """Eine Fundstelle, die nicht trifft, ist keine - und hier traegt sie
        die Aussage, dass gemessen wurde."""
        import re
        from pathlib import Path

        from research.gatelage import ENTSCHEIDUNGSGATES
        from research.stand import zahlwort

        text = Path("strategies/BEFUND.md").read_text(encoding="utf-8")
        nummern = {
            int(m.group(1))
            for m in re.finditer(r"^## (?:\w+)", text, re.M)
            if False
        } or None
        vorhanden = {
            z.lower() for z in re.findall(r"^## ([A-Za-zÄÖÜäöüß]+)\.", text, re.M)
        }

        for name, (zuerst, zuletzt) in ENTSCHEIDUNGSGATES.items():
            for nummer in (zuerst, zuletzt):
                assert zahlwort(nummer).lower() in vorhanden, f"{name}: {nummer}"
        assert nummern is None  # der erste Ausdruck ist Absicht leer

    def test_keine_ueberschneidung_mit_den_anderen_arten(self) -> None:
        """Ein Gate auf zwei Listen waere eine Einteilung, die nichts
        einteilt - und die Reihenfolge in ``ordne`` entschiede still."""
        from research.gatelage import (
            DURCHGEMESSENE_GATES,
            ENTSCHEIDUNGSGATES,
            WIRTSCHAFTLICHE_GATES,
        )

        mengen = [
            set(WIRTSCHAFTLICHE_GATES),
            set(DURCHGEMESSENE_GATES),
            set(ENTSCHEIDUNGSGATES),
        ]
        for i, a in enumerate(mengen):
            for b in mengen[i + 1 :]:
                assert a & b == set(), a & b

    def test_die_art_sagt_dass_sie_nichts_aufwertet(self) -> None:
        """Der Text unter der Art traegt hier die Aussage: Wer sie liest, soll
        nicht glauben, das Gate sei bestanden.

        **Am Quelltext geprueft und nicht an ``__doc__``**: Ein
        ``StrEnum``-Mitglied hat keinen eigenen Docstring - ``__doc__`` liefert
        den der Klasse, und die Zusicherung waere an der falschen
        Zeichenkette gruen geworden. Beim ersten Lauf genau so passiert.
        """
        import inspect

        from research import gatelage

        quelle = inspect.getsource(gatelage)
        nach_art = quelle.split('ENTSCHEIDUNG = "entscheidung"')[1].split(
            'OFFEN = "offen"'
        )[0]
        nach_offen = quelle.split('OFFEN = "offen"')[1].split("\n\n\n")[0]

        assert "Keine Aufwertung" in nach_art
        assert "bleibt durchgefallen" in nach_art
        assert "Nie untersucht" in nach_offen
