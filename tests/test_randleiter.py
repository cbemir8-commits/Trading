"""Die Randprobe war auf eine Reihenlaenge geeicht - Befund 433.

Befund 431 hat ``pruefe_rand`` mit **absoluten** Stufen gebaut: 10_000 bis
50_000 Balken, gemessen auf der Feinreihe mit 229_728. Auf kuerzeren Reihen
wirft die Bedingung ``schritt * 2 >= len`` sie weg - auf Stundenkerzen sechs
von zehn, auf Vierstundenkerzen **alle**. Uebrig bleibt die Pruefung "voll",
und ``traegt()`` verlangt Einstimmigkeit: Eine Probe mit einer einzigen
Sprosse meldet dann "haelt in allen 1" und ist bestanden.

Das ist dieselbe Bauart, die Befund 430 an den erwarteten Ausfaellen
abgestellt hat - eine Pruefung, die immer durchlaesst, deckt jeden echten
Fall mit.

Hier wird geprueft, dass die Leiter mit der Reihe mitwaechst, dass eine zu
kurze Reihe keine stille Zustimmung erzeugt, und dass die Sprossen Namen
tragen, die man wiederfindet.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.vorteilsscan import (
    RANDANTEILE,
    RANDSCHRITTE,
    _randname,
    pruefe_rand,
    randschritte,
)


def _reihe(n: int) -> np.ndarray:
    schritt = np.random.default_rng(5).normal(0, 0.001, n)
    return np.exp(np.cumsum(schritt)) * 100


class TestDieLeiterWaechstMit:
    def test_sie_ist_anteilig_an_der_laenge(self) -> None:
        kurz = randschritte(10_000)
        lang = randschritte(100_000)

        assert len(kurz) == len(lang) == len(RANDANTEILE)
        assert all(
            k * 10 == pytest.approx(gross, rel=0.01)
            for k, gross in zip(kurz, lang, strict=True)
        )

    def test_auf_der_feinreihe_trifft_sie_die_stufen_von_431(self) -> None:
        """Die Anteile sind so gewaehlt, dass sie die gemessene Grundlage
        ungefaehr treffen - eine Verallgemeinerung, keine neue Wahl."""
        stufen = randschritte(229_728)

        for gewaehlt, damals in zip(stufen, RANDSCHRITTE, strict=True):
            assert abs(gewaehlt - damals) / damals < 0.12, (stufen, RANDSCHRITTE)

    def test_eine_sprosse_nimmt_nie_die_halbe_reihe(self) -> None:
        """Sonst prueft sie nichts: Was von der Reihe bleibt, ist kuerzer als
        die Haelfte, und 'haelften' hat keine zwei Haelften mehr."""
        for laenge in (200, 1_000, 14_358, 57_432, 229_728):
            assert all(s * 2 < laenge for s in randschritte(laenge)), laenge

    def test_null_sprossen_fallen_weg_statt_zu_zaehlen(self) -> None:
        """Bei sehr kurzen Reihen rundet ein Anteil auf null - eine Sprosse,
        die nichts wegnimmt, prueft zweimal dasselbe."""
        assert all(s >= 1 for s in randschritte(20))


class TestEineKurzeReiheGibtKeineStilleZustimmung:
    def test_vierstundenkerzen_haben_trotzdem_elf_sprossen(self) -> None:
        """Die Laenge, an der die absolute Leiter zusammenfiel: 14_358."""
        probe = pruefe_rand(_reihe(14_358), 16, 16)

        assert probe.geprueft == 11

    def test_mit_den_absoluten_stufen_faellt_sie_zusammen(self) -> None:
        """Die Gegenprobe, ohne die der Befund nichts behauptet - genau eine
        Pruefung bleibt uebrig, und das ist der Freibrief."""
        probe = pruefe_rand(_reihe(14_358), 16, 16, schritte=RANDSCHRITTE)

        assert probe.geprueft == 1

    def test_und_eine_einzige_sprosse_koennte_tragen(self) -> None:
        """Warum das gefaehrlich ist: Haelt die volle Reihe, meldet die
        entartete Probe 'haelt in allen 1' und ist bestanden."""
        from research.vorteilsscan import Randprobe

        entartet = Randprobe(haelt_bei=(("voll", True),))

        assert entartet.traegt()
        assert "allen 1" in entartet.beschreibe()

    def test_sehr_kurze_reihen_pruefen_wenigstens_voll(self) -> None:
        probe = pruefe_rand(_reihe(120), 16, 16)

        assert probe.geprueft >= 1
        assert probe.haelt_bei[0][0] == "voll"


class TestDieSprossenTragenEindeutigeNamen:
    def test_die_sprosse_heisst_nach_ihrer_balkenzahl(self) -> None:
        assert _randname(574) == "574"
        assert _randname(50_540) == "50540"

    def test_die_tausender_abkuerzung_war_zweideutig(self) -> None:
        """Der Fehlgriff, den der Test darunter gefangen hat: Auf 4h sind die
        Stufen 574, 1292, 1867, 2441, 3159 - und 1292 // 1000 ist dasselbe
        wie 1867 // 1000. Zwei Sprossen hiessen '1k'."""
        stufen = randschritte(14_358)
        abgekuerzt = [f"{s // 1000}k" for s in stufen]

        assert len(set(abgekuerzt)) < len(stufen), (stufen, abgekuerzt)
        assert len({_randname(s) for s in stufen}) == len(stufen)

    def test_keine_zwei_pruefungen_heissen_gleich(self) -> None:
        """Ein Bericht, in dem zwei verschiedene Pruefungen gleich heissen,
        laesst den Leser nicht nachsehen."""
        for laenge in (14_358, 57_432, 229_728):
            namen = [name for name, _ in pruefe_rand(_reihe(laenge), 16, 16).haelt_bei]

            assert len(set(namen)) == len(namen), (laenge, namen)


class TestDerScanFasstZusammen:
    """``--aus`` liest ein feineres Intervall und fasst es zusammen - der
    Speicher fuehrt 1h und 4h nicht, und hineinschreiben wuerde das Tor aus
    Befund 430 umwerfen."""

    def _quelle(self) -> str:
        import inspect

        import cli

        return inspect.getsource(cli.scan)

    def test_die_option_gibt_es(self) -> None:
        assert '"--aus"' in self._quelle()

    def test_sie_prueft_auf_ganze_vielfache(self) -> None:
        """Sonst haetten die Kerzen wechselnd viele Bausteine."""
        quelle = self._quelle()

        assert "teilbar(quell_obj, interval_obj)" in quelle

    def test_gelesen_wird_ueber_den_helfer(self) -> None:
        quelle = self._quelle()

        assert "frame = _lies(symbol)" in quelle
        assert "gelesen = _lies(s)" in quelle

    def test_und_in_den_speicher_wird_nichts_geschrieben(self) -> None:
        """Der Punkt, an dem das Tor aus 430 haengt."""
        quelle = self._quelle()

        assert "store.write" not in quelle
        assert "resample(rohe, quell_obj, interval_obj)" in quelle
