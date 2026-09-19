"""Der Auftragspunkt kennt jetzt eine Nachmessung - Befund 304.

``Richtung`` hat diese Lehre in Befund 130 gezogen: Wer eine Fundstelle
nennt, muss die **letzte** nennen, sonst schlaegt jemand eine ueberholte
Tabelle nach und erklaert sich den Unterschied falsch.

``Auftragspunkt`` hatte sie 174 Befunde spaeter immer noch nicht - und das in
dem einen Register, das die Punkte des Auftraggebers beantwortet. Der Punkt
"Generation 6/7 auf 15-Minuten" zeigte auf Befund 29 mit 14 Regeln, waehrend
297 denselben Vorrat mit 36 gemessen hatte.

Die Klasse gibt es ueberhaupt nur wegen dieses Fehlers: Ihr eigener
Docstring haelt fest, dass zwei Punkte des Auftrags laengst abgearbeitet
waren, weiter als offen gelesen wurden und beinahe vierzehn Versuche
gekostet haetten.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.nachmessung import abschnitte
from research.stand import AUFTRAG, Auftragspunkt

BEFUND = Path("strategies/BEFUND.md")


@pytest.fixture(scope="module")
def laborbuch() -> str:
    return BEFUND.read_text(encoding="utf-8")


class TestDieNachmessungIstMoeglich:
    def test_ohne_nachmessung_gilt_die_erstmessung(self) -> None:
        punkt = Auftragspunkt(frage="F", stand="S", befund=42)
        assert punkt.massgeblich == 42
        assert "Nr. 42" in str(punkt)

    def test_mit_nachmessung_gilt_die_spaetere(self) -> None:
        punkt = Auftragspunkt(frage="F", stand="S", befund=29, zuletzt=297)
        assert punkt.massgeblich == 297

    def test_die_marke_nennt_beide_ohne_zweite_klammer(self) -> None:
        """'Nr. 297 (zuerst 29)' stuende in einer Klammer und ergaebe eine
        geschachtelte - Befund 293 hat genau das an derselben Stelle
        abgestellt."""
        punkt = Auftragspunkt(frage="F", stand="S", befund=29, zuletzt=297)
        assert "(Nr. 297, zuerst 29)" in str(punkt)
        assert "((" not in str(punkt)

    def test_eine_nachmessung_muss_spaeter_liegen(self) -> None:
        with pytest.raises(ValueError, match="keine Nachmessung"):
            Auftragspunkt(frage="F", stand="S", befund=100, zuletzt=99)

    def test_auch_nicht_dieselbe_stelle(self) -> None:
        with pytest.raises(ValueError, match="keine Nachmessung"):
            Auftragspunkt(frage="F", stand="S", befund=100, zuletzt=100)

    def test_erledigt_ohne_fundstelle_bleibt_verboten(self) -> None:
        """Die aeltere Wache darf die neue nicht verlieren."""
        with pytest.raises(ValueError, match="Behauptung"):
            Auftragspunkt(frage="F", stand="S", befund=0, erledigt=True)

    def test_ein_offener_punkt_braucht_keine_fundstelle(self) -> None:
        punkt = Auftragspunkt(frage="F", stand="S", befund=0, erledigt=False)
        assert "offen" in str(punkt)
        assert punkt.massgeblich == 0


class TestDasEchteRegister:
    def test_jede_massgebliche_fundstelle_gibt_es_im_laborbuch(
        self, laborbuch: str
    ) -> None:
        """Dieselbe Wache, die ``GESCHLOSSEN`` seit Befund 130 hat - fuer das
        Register, das dem Auftraggeber antwortet."""
        vorhanden = {a.nummer for a in abschnitte(laborbuch)}
        fehlend = [
            p.frage for p in AUFTRAG if p.befund and p.massgeblich not in vorhanden
        ]
        assert not fehlend, f"Fundstelle zeigt ins Leere: {fehlend}"

    def test_die_nachgezogenen_stehen_fest(self) -> None:
        """Ausgeschrieben, damit jedes weitere Nachziehen eine bewusste
        Entscheidung ist - wie bei ``GESCHLOSSEN`` in ``test_nachmessung``.

        Wer eine Zeile hinzufuegt, hat den Befund gelesen. 'Generation 5 auf
        Tageskerzen' steht bewusst **nicht** hier: Dass es dazu eine spaetere
        Messung gibt, ist plausibel und war in Befund 304 nicht geprueft.
        """
        nachgezogen = {p.frage: p.zuletzt for p in AUFTRAG if p.zuletzt}
        assert nachgezogen == {
            # 297 hat den ganzen 15-Minuten-Vorrat gemessen, 36 Regeln statt
            # der 14 aus Befund 29.
            "Generation 6/7 auf 15-Minuten": 297,
            # 292 hat dem Auftrag an die KI gesagt, worin der Unterschied
            # bestehen muss - wer sie neu laufen laesst, bekommt einen
            # anderen Auftrag als bei 196.
            "Research-KI im Wettbewerb nutzen": 292,
        }

    def test_der_stand_nennt_seine_fundstelle_auch_im_text(self) -> None:
        """Ein Stand, der eine Zahl nennt, soll sagen, woher sie kommt -
        sonst steht die Zahl da und die Marke daneben, und niemand weiss, ob
        sie zusammengehoeren."""
        for p in AUFTRAG:
            if p.zuletzt:
                assert str(p.zuletzt) in p.stand, p.frage

    def test_kein_punkt_behauptet_etwas_ohne_stelle(self) -> None:
        for p in AUFTRAG:
            assert p.stand.strip(), p.frage
            if p.erledigt:
                assert p.befund > 0, p.frage
