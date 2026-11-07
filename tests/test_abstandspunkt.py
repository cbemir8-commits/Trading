"""Zwei Laeufe, zeichengleicher Kopf, verschiedene Zahlen (Befund 465).

Was dastand
-----------
``cli abstand`` beantwortet die Frage, die alles steuert: *Was fehlt zum
Deflated Sharpe, und was kostet Weitersuchen?* Er kennt den Schalter
``--spot``, rechnet also auf **beiden** Betriebspunkten - und seine Kopfzeile
lautete in beiden Faellen Zeichen fuer Zeichen gleich:

    Abstand zum Gate BTCUSD_BITSTAMP + ETHUSD_BITSTAMP 1d

Dieselbe Reihe, dieselbe Kerzenlaenge, dieselben 156 rohen und 115 wirksamen
Trades, dieselben 203 Versuche. Gemessen:

    Vorgabe (Perpetual)   DSR 0,458   Guete je Trade 0,254   noetig 221
    --spot                DSR 0,583   Guete je Trade 0,271   noetig 191

**Die 191 ist die Zahl, die das Projekt fuehrt** - ``datenbedarf`` nennt sie
im Modulkopf, ``erreichbarkeit.noetige_trades`` liefert sie, und
``referenz.SPOTPUNKT.noetiges_n()`` gibt 190, was nach Befund 409 dieselbe
Antwort mit einer Rundung ist.

Wer also die Vorgabe fuhr und das Ergebnis mit einer zitierten Projektzahl
verglich, las ueber zwei Betriebspunkte hinweg. Das ist der Fehler, den Befund
242 mit *"elf Mal vorgekommen"* beziffert - hier an der Zahl, die die
Reihenfolge der ganzen Arbeit bestimmt. Und "es fehlen 106" gegen "es fehlen
76" ist kein Rundungsunterschied, sondern vierzig Prozent.

Warum die Wache aus Befund 242 es nicht gefunden hat
----------------------------------------------------
``test_berichte_betriebspunkt`` prueft vier Berichtsarten - und zwar die, die
eine **Datei** ablegen. ``cli abstand`` legt keine ab, er druckt. Die Regel war
richtig, ihre Reichweite endete am Dateisystem. Dieselbe Klasse wie die drei
Faelle aus Befund 463 und die Frage, die Befund 464 ueber die Suite gemessen
hat.

Was hier gehalten wird
----------------------
Nicht der Wert - der haengt am Lauf. Sondern dass der Punkt **in der Ausgabe**
steht, und dass die beiden Laeufe sich daran unterscheiden lassen.

Geprueft wird auf zwei Ebenen, und beide sind noetig:

* im Quelltext, mit ``rumpf`` statt einer nackten Textsuche - der Kommentar
  oberhalb nennt ``_betriebspunkt`` selbst, eine Suche ueber den Rohtext waere
  also schon durch ihn gruen (Befund 399);
* an der **Ausgabe** eines echten Laufs, weil ein Quelltext-Treffer nicht
  heisst, dass etwas gedruckt wird. Genau das war Befund 394: elf Zeilen, die
  es in keiner Ausgabe gab.
"""
from __future__ import annotations

import pytest

from tests.quelltext import rumpf


class TestDerQuelltextLiestDenPunktAusDenObjekten:
    @staticmethod
    def _rumpf() -> str:
        import cli

        return rumpf(cli.abstand)

    def test_er_fragt_betriebspunkt(self) -> None:
        """**Aus Genom und Konfigurationen, nicht aus dem Schalter.** Eine
        zweite Herleitung desselben Umstands waere die naechste Stelle, an der
        beide auseinanderlaufen (Befund 415)."""
        assert "_betriebspunkt(" in self._rumpf()

    def test_und_der_kopf_traegt_ihn(self) -> None:
        quelle = self._rumpf()
        kopf = quelle[quelle.index("Abstand zum Gate") :][:400]

        assert "punkt" in kopf, "die Kopfzeile nennt den Betriebspunkt nicht"

    def test_die_nackte_textsuche_haette_nicht_gereicht(self) -> None:
        """Die Gegenprobe zu Befund 399: Der Begruendungskommentar nennt
        ``_betriebspunkt`` ebenfalls, also ist eine Suche ueber den Rohtext
        auch ohne Code gruen. Diese Datei prueft deshalb den Rumpf."""
        import inspect

        import cli
        from tests.quelltext import nur_prosa

        assert "_betriebspunkt" in nur_prosa(inspect.getsource(cli.abstand))


def _lauf(*args: str) -> str:
    from typer.testing import CliRunner

    from cli import app

    ergebnis = CliRunner().invoke(app, ["abstand", *args])
    assert ergebnis.exit_code == 0, ergebnis.output[-1500:]
    return " ".join(ergebnis.output.split())


@pytest.fixture(scope="module")
def beide() -> tuple[str, str]:
    """Beide Laeufe einmal - zwei Walk-Forwards, nicht zehn.

    **Auf Modulebene, nicht als Methode der Klasse** (Befunde 426/429, und
    dieser Entwurf war der dritte Fall): Eine Fixture mit einem Gueltigkeits-
    bereich ueber die Funktion hinaus, die als Methode in einer Klasse steht,
    laesst pytest mit ``assert not self._finalizers`` abbrechen. Der erste
    Anlauf dieser Datei hat genau so gefehlt.
    """
    return _lauf(), _lauf("--spot")


@pytest.mark.daten
@pytest.mark.langsam
class TestDieAusgabeUnterscheidetDieBeidenLaeufe:
    """**Die tragende Wache**, und sie kostet zwei Walk-Forwards.

    Billiger ginge es nur im Quelltext, und davor warnt Befund 394.
    """

    def test_die_vorgabe_nennt_den_perpetual_punkt(
        self, beide: tuple[str, str]
    ) -> None:
        vorgabe, _ = beide

        assert "Abstand zum Gate" in vorgabe
        assert "Perpetual" in vorgabe

    def test_der_schalter_nennt_den_spot_punkt(
        self, beide: tuple[str, str]
    ) -> None:
        _, mit_spot = beide

        assert "Spot (kein Hebel, kein Funding)" in mit_spot

    def test_die_beiden_koepfe_sind_unterscheidbar(
        self, beide: tuple[str, str]
    ) -> None:
        """**Der Kern des Befundes.** Vorher waren sie zeichengleich."""
        vorgabe, mit_spot = beide

        def kopf(text: str) -> str:
            ab = text.index("Abstand zum Gate")
            return text[ab : ab + 120]

        assert kopf(vorgabe) != kopf(mit_spot)

    def test_jeder_lauf_nennt_den_anderen_punkt_mit_zahl(
        self, beide: tuple[str, str]
    ) -> None:
        """Sonst bleiben 221 und 191 zwei unerklaerte Zahlen fuer eine Frage -
        das, woran dieses Projekt wiederholt haengengeblieben ist (370)."""
        from research.referenz import PERPETUALPUNKT, SPOTPUNKT

        vorgabe, mit_spot = beide

        assert f"{SPOTPUNKT.dsr:.4f}" in vorgabe
        assert f"{PERPETUALPUNKT.dsr:.4f}" in mit_spot
        for text in beide:
            assert "Befund 428" in text, "der Verwechslungsfehler wird genannt"

    def test_die_zahlen_der_beiden_punkte_gehen_wirklich_auseinander(
        self, beide: tuple[str, str]
    ) -> None:
        """Die Voraussetzung des ganzen Befundes, gemessen statt behauptet:
        Waeren die Zahlen gleich, waere der fehlende Punkt gleichgueltig."""
        vorgabe, mit_spot = beide

        assert "221 Trades noetig" in vorgabe
        assert "191 Trades noetig" in mit_spot
