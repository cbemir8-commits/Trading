"""Die Kerzenlaenge wurde aufgezeichnet und nie verglichen.

**Befund 263.** ``Zulassungsbedingungen`` traegt seit Befund 106 auf, unter
welchen Bedingungen ein Champion bestanden hat, und ``cli trade`` prueft davon
genau eines: das Instrument (``passt_zu``). Bei einer Abweichung bricht es ab,
mit der Begruendung *"Die Gates gelten fuer das gepruefte Instrument, nicht
fuer ein anderes."*

``intervall`` steht im selben Nachweis. ``_bedingungen`` schreibt es bei jedem
Lauf mit. Verglichen hat es niemand - ``bedingungen.intervall`` kam in ``cli
trade`` kein einziges Mal vor.

Dabei gilt der Satz wortgleich: Die elf Gates sind auf **einer** Kerzenlaenge
gemessen. Auf Tageskerzen stehen alle elf (Befund 213); auf Viertelstunden
raeumt der beste Fund 0,188 seiner Latte (Befund 190). ``cli trade --intervall
15`` mit einem auf Tageskerzen zugelassenen Champion haette gehandelt, ohne
ein Wort zu sagen.

Was hier gehalten wird
----------------------
Dass beide Geschwister gleich behandelt werden - und der Unterschied zwischen
``cli trade`` (bricht ab, Geld) und ``cli abgleich`` (warnt, prueft die
Engine).
"""

from __future__ import annotations

import ast
from pathlib import Path

from research.admission import Zulassungsbedingungen


def _quelle(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == name
    )
    return ast.unparse(knoten)


class TestDasGeschwisterZuPasstZu:
    def test_gleiche_kerzenlaenge_passt(self) -> None:
        assert Zulassungsbedingungen(intervall="D").passt_zur_kerzenlaenge("D")

    def test_andere_kerzenlaenge_passt_nicht(self) -> None:
        assert not Zulassungsbedingungen(intervall="D").passt_zur_kerzenlaenge("15")

    def test_ohne_aufzeichnung_heisst_es_unbekannt_und_nicht_passt_schon(
        self,
    ) -> None:
        """Dieselbe Regel wie bei ``passt_zu``: Ein leeres Feld ist keine
        Freigabe."""
        leer = Zulassungsbedingungen()

        assert not leer.passt_zur_kerzenlaenge("D")
        assert not leer.passt_zu("spot")

    def test_beide_pruefungen_liegen_nebeneinander(self) -> None:
        quelle = Path("research/admission.py").read_text(encoding="utf-8")

        assert "def passt_zu(" in quelle
        assert "def passt_zur_kerzenlaenge(" in quelle


class TestDerLivebetriebBrichtAb:
    """Dort laeuft Geld - dieselbe Haerte wie beim Instrument."""

    def test_trade_vergleicht_die_kerzenlaenge(self) -> None:
        assert "passt_zur_kerzenlaenge(" in _quelle("trade")

    def test_es_bricht_ab_und_warnt_nicht_nur(self) -> None:
        quelle = _quelle("trade")
        stelle = quelle.index("passt_zur_kerzenlaenge(")
        danach = quelle[stelle : stelle + 700]

        assert "raise typer.Exit(2)" in danach

    def test_eine_fehlende_aufzeichnung_sperrt_nicht(self) -> None:
        """Alte Dateien tragen keine Kerzenlaenge - die duerfen nicht
        stillschweigend unbrauchbar werden."""
        quelle = _quelle("trade")

        # ``ast.unparse`` klammert das ``not`` ein - geankert wird deshalb
        # auf die Wache selbst, nicht auf ihre Schreibweise.
        assert "bedingungen.intervall and" in quelle

    def test_die_meldung_sagt_wie_es_weitergeht(self) -> None:
        quelle = _quelle("trade")

        assert "--intervall" in quelle
        assert "Zulassung auf der gewuenschten Kerzenlaenge wiederholen" in quelle


class TestDerAbgleichWarntNur:
    """Er prueft die Engine, nicht das Konto - ein Abbruch waere hier zu
    hart, ein Schweigen zu weich."""

    def test_abgleich_vergleicht_die_kerzenlaenge(self) -> None:
        assert "passt_zur_kerzenlaenge(" in _quelle("abgleich")

    def test_er_bricht_dabei_nicht_ab(self) -> None:
        quelle = _quelle("abgleich")
        stelle = quelle.index("passt_zur_kerzenlaenge(")
        danach = quelle[stelle : stelle + 600]

        assert "typer.Exit" not in danach
        assert "yellow" in danach

    def test_er_sagt_was_der_livebetrieb_taete(self) -> None:
        """Damit die Warnung nicht wie eine Nebensaechlichkeit klingt."""
        assert "'cli trade' wuerde hier abbrechen" in _quelle("abgleich")

    def test_ohne_champion_wird_nicht_verglichen(self) -> None:
        """Der Saatkandidat traegt keinen Nachweis - dort gibt es nichts zu
        vergleichen, und die Warnung waere Unsinn."""
        quelle = _quelle("abgleich")
        stelle = quelle.index("passt_zur_kerzenlaenge(")
        davor = quelle[:stelle]

        assert "if not champion_pfad.exists():" in davor


class TestWasWeiterhinNichtAufgezeichnetIst:
    """Ehrlich benannt statt stillschweigend uebergangen."""

    def test_der_nachweis_kennt_kein_symbol(self) -> None:
        """Perpetual oder Spot steht drin, die Kerzenlaenge auch - **welcher
        Markt** nicht. Ein auf BTC+ETH zugelassener Champion liesse sich auf
        XRP handeln, und nichts im Nachweis widerspraeche."""
        felder = set(Zulassungsbedingungen().__dataclass_fields__)

        assert "markt" in felder and "intervall" in felder
        assert "symbol" not in felder and "symbole" not in felder
