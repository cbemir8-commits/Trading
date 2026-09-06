"""Was ein Versuch kostet - und dass es keine Konstante ist.

**Befund 221.** Das Projekt hat an vier Stellen "0,00021 je Versuch"
zitiert. Die Zahl stammt aus Befund 31, gemessen bei 152 Trades und ueber die
Spanne 112 bis 502 Versuche, als der Zaehler bei 130 stand.

Der Anstieg faellt aber mit dem Zaehler: Die Extremwertkorrektur waechst wie
die Wurzel des Logarithmus, nicht linear. Heute, bei 198 Versuchen und n_eff
115, sind es 0,000135 - wer mit 0,00021 rechnet, ueberschaetzt den Preis um
gut die Haelfte, und zwar in der Richtung, die vom Suchen abhaelt.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from research.referenz import SPOTPUNKT as S
from research.verbund import noetige_guete, versuchskosten


def _preis(versuche: int, weitere: int = 1) -> float:
    wert = versuchskosten(
        S.effektiv, versuche, schiefe=S.schiefe, woelbung=S.woelbung, weitere=weitere
    )
    assert wert is not None
    return wert


class TestDerPreisFaelltMitDemZaehler:
    def test_die_zitierte_zahl_gilt_bei_hundertdreissig(self) -> None:
        """**Der Befund.** 0,00021 ist nicht falsch - es ist der Wert von
        damals, und damals ist der Zaehlerstand 130 aus dem Plan."""
        assert _preis(130) == pytest.approx(0.00021, abs=5e-6)

    def test_heute_ist_er_deutlich_niedriger(self) -> None:
        assert _preis(S.versuche) == pytest.approx(0.000135, abs=5e-6)

    def test_er_faellt_durchweg(self) -> None:
        staende = [130, 198, 230, 500, 1000]
        preise = [_preis(v) for v in staende]

        assert preise == sorted(preise, reverse=True)

    def test_die_alte_zahl_ueberschaetzt_um_die_haelfte(self) -> None:
        assert 0.00021 / _preis(S.versuche) > 1.5


class TestDieGroessenordnung:
    """Die Zahl, auf die es bei der Entscheidung ankommt."""

    def test_der_rest_des_budgets_kostet_gut_ein_prozent(self) -> None:
        from research.stand import BUDGET

        latte = noetige_guete(
            S.effektiv, S.versuche, schiefe=S.schiefe, woelbung=S.woelbung
        )
        spaeter = noetige_guete(
            S.effektiv, BUDGET.grenze, schiefe=S.schiefe, woelbung=S.woelbung
        )
        assert latte is not None and spaeter is not None

        assert (spaeter - latte) / latte == pytest.approx(0.0118, abs=5e-4)

    def test_und_die_luecke_ist_zwanzigmal_so_gross(self) -> None:
        """Der Preis des Suchens ist nicht das, was die Suche schwer macht."""
        latte = noetige_guete(
            S.effektiv, S.versuche, schiefe=S.schiefe, woelbung=S.woelbung
        )
        assert latte is not None
        noetig_je_trade = latte / math.sqrt(S.effektiv)
        luecke = noetig_je_trade / S.guete - 1

        assert luecke == pytest.approx(0.243, abs=5e-3)
        assert luecke > 20 * 0.0118

    def test_befund_31_laesst_sich_nachrechnen(self) -> None:
        """*"Hundert weitere Versuche kosten rund 5 % mehr geforderte
        Qualitaet"* - gemessen von 130 aus, und dort stimmt es."""
        latte = noetige_guete(
            S.effektiv, 130, schiefe=S.schiefe, woelbung=S.woelbung
        )
        spaeter = noetige_guete(
            S.effektiv, 230, schiefe=S.schiefe, woelbung=S.woelbung
        )
        assert latte is not None and spaeter is not None

        assert (spaeter - latte) / latte == pytest.approx(0.0475, abs=2e-3)


class TestDieZahlWirdGerechnetUndNichtGepflegt:
    @staticmethod
    def _im_code(datei: str) -> list[str]:
        """Vorkommen der alten Zahl **ausserhalb** von Text und Kommentar.

        Erlaubt bleibt, ueber sie zu reden; nicht erlaubt ist, mit ihr zu
        rechnen. Der Unterschied ist derselbe wie bei der Gatezahl in Befund
        210, nur laesst er sich hier genauer ziehen: Ein Tokenizer weiss, was
        Text ist und was Code.
        """
        import io
        import token
        import tokenize

        aus = []
        quelle = Path(datei).read_text()
        for tok in tokenize.generate_tokens(io.StringIO(quelle).readline):
            if tok.type in (token.STRING, tokenize.COMMENT):
                continue
            if "0.00021" in tok.string or "0,00021" in tok.string:
                aus.append(f"{datei}:{tok.start[0]} {tok.string[:40]}")
        return aus

    def test_keine_feste_zahl_mehr_im_code(self) -> None:
        treffer = [
            x
            for datei in ("cli.py", "research/stand.py", "research/verbund.py")
            for x in self._im_code(datei)
        ]

        assert treffer == [], treffer

    def test_die_regel_faende_eine_gerechnete_zahl(self) -> None:
        """Gegenprobe: eine Datei, in der die Zahl im Code steht."""
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write('x = 0.00021  # Kommentar mit 0.00021\ny = "Text 0,00021"\n')
            pfad = f.name

        assert self._im_code(pfad) != []

    def test_ueber_sie_reden_bleibt_erlaubt(self) -> None:
        """Sonst loescht die Wache die Erinnerung mit der Zahl."""
        quelle = Path("research/verbund.py").read_text()

        assert "0,00021" in quelle
        assert "Befund 31" in quelle

    def test_der_cli_helfer_rechnet(self) -> None:
        import cli

        assert cli._versuchspreis() == f"{_preis(S.versuche):.6f}"

    def test_er_haengt_am_referenzpunkt(self) -> None:
        """Wandert der Betriebspunkt, wandert der Preis mit."""
        import inspect

        import cli

        quelle = inspect.getsource(cli._versuchspreis)

        assert "SPOTPUNKT" in quelle
        assert "0.00021" not in quelle


def test_ohne_latte_kein_preis() -> None:
    assert versuchskosten(0, 198) is None
