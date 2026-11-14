"""Der Melder auf die Versuchsbuchungen, selbst geprueft - Befund 479.

Er stand zweimal im Baum. ``test_versuchszaehler_wer`` kannte beide
Buchungswege (Lehre aus Befund 282), ``test_rauchtest`` nur ``save_trials`` -
und seit kein Befehl mehr so bucht, fand diese Fassung die **leere Menge**
und verglich sie gegen alles:

    assert zaehlend <= set(WIRKT_NACH_AUSSEN)

Leer ist Teilmenge von allem. Die Wache auf die teuerste Ecke des Projekts -
jeder gebuchte Versuch hebt die Huerde dauerhaft - prueft seit der
Umstellung nichts.

Diese Datei prueft den Melder selbst. Ohne sie waere er der dritte
ungepruefte Zaehler in dieser Sitzung.
"""

from __future__ import annotations

from tests.zaehlerwege import BUCHUNGSWEGE, zaehlende_befehle


class TestBeideWegeWerdenGesehen:
    def test_der_alte_weg(self) -> None:
        quelle = """
def wettbewerb():
    save_trials(pfad, zahl)
"""

        assert zaehlende_befehle(quelle) == {"wettbewerb"}

    def test_der_heutige_weg(self) -> None:
        quelle = """
def landschaft():
    _verzeichne(kennung, guete)
"""

        assert zaehlende_befehle(quelle) == {"landschaft"}

    def test_und_wer_keinen_nimmt_wird_nicht_gemeldet(self) -> None:
        """Die Gegenprobe zur Nichtleere-Zusicherung im Rauchtest: Faende der
        Melder immer etwas, saegte sie nichts."""
        quelle = """
def stand():
    console.print(bericht)
"""

        assert zaehlende_befehle(quelle) == set()

    def test_hilfsfunktionen_zaehlen_nicht_als_befehl(self) -> None:
        """``_verzeichne`` selbst bucht - es ist aber kein Befehl."""
        quelle = """
def _verzeichne(kennung, guete):
    save_trials(pfad, zahl)
"""

        assert zaehlende_befehle(quelle) == set()

    def test_beide_wege_stehen_in_der_liste(self) -> None:
        assert set(BUCHUNGSWEGE) == {"save_trials", "_verzeichne("}


class TestAmEchtenQuelltext:
    def test_es_sind_welche(self) -> None:
        """Die Zusicherung, die bis 479 fehlte."""
        assert zaehlende_befehle()

    def test_und_zwar_die_sieben_aus_dem_register(self) -> None:
        """Die gepflegte Liste steht in ``test_versuchszaehler_wer`` - hier
        wird nur geprueft, dass der gemeinsame Melder dieselbe Menge findet.
        Zwei Listen waeren wieder zwei Wahrheiten (Befund 234)."""
        from tests.test_versuchszaehler_wer import ZAEHLER

        assert zaehlende_befehle() == set(ZAEHLER)

    def test_save_trials_kommt_in_keinem_befehl_mehr_vor(self) -> None:
        """Der Grund, warum die alte Fassung verstummt ist - als Messung.

        Geht das wieder auf null zurueck, ist dieser Test rot und jemand
        sieht hin, statt dass eine Wache leer laeuft.
        """
        nur_alt = [
            name
            for name in zaehlende_befehle()
            if "save_trials" in _rumpf(name) and "_verzeichne(" not in _rumpf(name)
        ]

        assert nur_alt == [], nur_alt


def _rumpf(name: str) -> str:
    import ast
    from pathlib import Path

    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == name:
            return ast.unparse(knoten)
    raise AssertionError(name)
