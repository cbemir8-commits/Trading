"""Eine Zahl ohne Huerde und ein Kandidat ohne Regeln sind nicht dasselbe.

**Befund 257.** Die Bestenliste kennt seit Befund 96 ``vergleichbar``: Fehlt
der Versuchsstand, gehoert die Zahl nicht in denselben Vergleich, und ein
``?`` sagt das. Die teurere Luecke hatte kein Zeichen.

``genom`` haelt seit Befund 74 die Regeln mit, weil genau das einmal
schiefgegangen ist: 'Neues Hoch im Takt' ist die einzige gemessene Regel, die
die Kopplung zwischen Trade-Zahl und Qualitaet bricht - und sie stammt aus
``sieger.json``, einer Vorschlagsdatei, die nie versioniert wurde. Die Liste
hielt damals ``genome_id``, Namen und Kennzahlen. Der Kandidat ist weg.

Seit Befund 256 ist das teurer als damals: Die Kopplung ist als Eigenschaft
der **Signale** gemessen und nicht wegzuverhandeln - ein struktureller Bruch
ist der einzige bekannte Weg heraus, und die eine Regel, die einen vorgemacht
hat, laesst sich nicht mehr rechnen.

Was hier gehalten wird
----------------------
Dass die beiden Luecken auseinandergehalten werden - im Datentyp, in der
Tabelle und im Text -, und dass die zweite nicht stillschweigend als die
erste durchgeht.
"""

from __future__ import annotations

import ast
from pathlib import Path

from research.leaderboard import Entry, Leaderboard


def _eintrag(name: str, **rest) -> Entry:
    daten = {
        "genome_id": name.lower().replace(" ", "_"),
        "name": name,
        "generation": 9,
    }
    daten.update(rest)
    return Entry(**daten)


def _liste(*eintraege: Entry) -> Leaderboard:
    board = Leaderboard.__new__(Leaderboard)
    board.entries = {e.genome_id: e for e in eintraege}
    return board


class TestRechenbarHaengtAnDenRegeln:
    def test_ohne_genom_nicht_rechenbar(self) -> None:
        assert not _eintrag("Neues Hoch im Takt").rechenbar

    def test_mit_genom_rechenbar(self) -> None:
        assert _eintrag("Mit Regeln", genom={"name": "x"}).rechenbar

    def test_ein_leeres_genom_ist_kein_fehlendes(self) -> None:
        """``None`` heisst "nie gespeichert". Ein leeres Objekt ist etwas
        anderes und soll nicht als dasselbe gelten - wer es findet, hat ein
        anderes Problem."""
        assert _eintrag("Leer", genom={}).rechenbar


class TestDieBeidenLueckenSindVerschieden:
    def test_vergleichbar_und_rechenbar_haengen_an_verschiedenem(self) -> None:
        nur_zahlen = _eintrag(
            "alte Zahl", versuche=100, sharpe_je_trade=0.25, trades=150
        )
        nur_regeln = _eintrag("nur Regeln", genom={"name": "x"})

        assert nur_zahlen.vergleichbar and not nur_zahlen.rechenbar
        assert nur_regeln.rechenbar and not nur_regeln.vergleichbar

    def test_die_liste_zaehlt_sie_getrennt(self) -> None:
        board = _liste(
            _eintrag("a", versuche=100, sharpe_je_trade=0.25, trades=150),
            _eintrag("b", genom={"name": "x"}),
            _eintrag(
                "c", versuche=100, sharpe_je_trade=0.25, trades=150,
                genom={"name": "y"},
            ),
        )

        assert [e.name for e in board.unrechenbar] == ["a"]
        assert sorted(e.name for e in board.unvergleichbar) == ["b"]

    def test_eine_vollstaendige_liste_meldet_keine_luecke(self) -> None:
        board = _liste(
            _eintrag(
                "voll", versuche=100, sharpe_je_trade=0.25, trades=150,
                genom={"name": "x"},
            )
        )

        assert board.unrechenbar == []
        assert board.unvergleichbar == []


class TestDieTabelleSagtWelcheLueckeEsIst:
    @staticmethod
    def _quelle() -> str:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "_zeige_bestenliste"
        )
        return ast.unparse(knoten)

    def test_es_gibt_zwei_verschiedene_zeichen(self) -> None:
        quelle = self._quelle()

        assert "' ?'" in quelle or '" ?"' in quelle
        assert "' *'" in quelle or '" *"' in quelle

    def test_das_zeichen_fuer_fehlende_regeln_haengt_an_rechenbar(self) -> None:
        assert "eintrag.rechenbar" in self._quelle()

    def test_die_erklaerung_nennt_den_verlorenen_kandidaten(self) -> None:
        """Ohne ihn liest sich die Zeile wie Buchhaltung. Mit ihm steht da,
        was sie gekostet hat."""
        quelle = self._quelle()

        assert "Neues Hoch im Takt" in quelle
        assert "nicht mehr rechenbar" in quelle

    def test_die_teurere_luecke_steht_nicht_in_dim(self) -> None:
        """Die Huerdenluecke ist eine Fussnote, diese nicht."""
        quelle = self._quelle()
        stelle = quelle.index("nicht mehr rechenbar")
        absatz = quelle[max(0, stelle - 400):stelle]

        assert "[yellow]" in absatz
