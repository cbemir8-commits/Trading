"""Drei Familien, eine Schwelle.

**Befund 274.** Befund 272 hat die Preisrueckblick-Familie gemessen - leer -
und ausdruecklich offengelassen, ob Volumen oder Spanne etwas tragen. Beide
sind jetzt dabei.

Was hier gehalten wird
----------------------
**Die Schwelle gilt ueber alle Familien zusammen.** Wer drei Familien scannt
und die Latte je Familie rechnet, hat dreimal so viele Gelegenheiten bei
unveraenderter Huerde - genau das Datenbaggern, gegen das dieser Scan gebaut
ist. Deshalb gibt es auch kein Flag, das eine Familie allein laufen laesst:
Es waere die bequemste Art, die Latte zu senken.

Und die Trennung von Vorher und Nachher: Die Kennzahl wird **bis** zum
Entscheidungsbalken gelesen, die Rendite **danach**. Ohne diese Trennung
misst man die Gegenwart mit sich selbst.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from research.vorteilsscan import (
    MIND_BEOBACHTUNGEN,
    schwelle_fuer,
    spanne_nach_kennzahl,
    zweiteilung,
)


def _scan_quelle() -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == "scan"
    )
    return ast.unparse(knoten)


class TestDieZweiteilungIstDieForm:
    """Ob der Teiler eine Rendite ist oder ein Volumen, aendert nichts."""

    def test_zwei_zustaende_ergeben_eine_spanne(self) -> None:
        vorwaerts = np.array([1.0] * 40 + [0.0] * 40)
        teiler = np.array([1.0] * 40 + [-1.0] * 40)

        z = zweiteilung(vorwaerts, teiler, rueckblick=4, halten=2)

        assert z is not None
        assert z.spanne_pct == pytest.approx(100.0)

    def test_ohne_genug_beobachtungen_gibt_es_nichts(self) -> None:
        n = MIND_BEOBACHTUNGEN - 1
        z = zweiteilung(
            np.array([1.0] * n + [0.0] * 40),
            np.array([1.0] * n + [-1.0] * 40),
            rueckblick=4,
            halten=2,
        )

        assert z is None

    def test_ungleiche_laengen_sind_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="genau ein Teiler"):
            zweiteilung(np.zeros(80), np.zeros(79), rueckblick=4, halten=2)

    def test_die_alte_spanne_geht_denselben_weg(self) -> None:
        """Keine zweite Rechnung - ``spanne`` ruft ``zweiteilung`` auf."""
        import inspect

        from research import vorteilsscan

        assert "zweiteilung(" in inspect.getsource(vorteilsscan.spanne)


class TestDieKennzahlWirdVorherGelesen:
    def _reihe(self, n: int = 400) -> np.ndarray:
        schritte = np.sin(np.arange(n) / 7.0) * 0.01
        return np.cumsum(schritte)

    def test_eine_kennzahl_liefert_eine_zelle(self) -> None:
        log_close = self._reihe()
        kennzahl = np.abs(np.sin(np.arange(len(log_close)) / 3.0))

        z = spanne_nach_kennzahl(log_close, kennzahl, 8, 4)

        assert z is not None
        assert z.rueckblick == 8
        assert z.halten == 4

    def test_ungleiche_laengen_sind_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="gleich lang"):
            spanne_nach_kennzahl(self._reihe(), np.zeros(10), 8, 4)

    def test_zu_wenig_daten_geben_nichts(self) -> None:
        kurz = self._reihe(10)

        assert spanne_nach_kennzahl(kurz, kurz, 8, 4) is None

    def test_der_gleitende_median_blickt_nicht_nach_vorn(self) -> None:
        """Am Anfang steht der Median des bisher Bekannten, nicht der des
        ganzen Zeitraums - sonst steckte die Zukunft im Teiler."""
        from research.vorteilsscan import _gleitender_median

        werte = np.array([1.0, 2.0, 3.0, 100.0, 100.0])

        med = _gleitender_median(werte, 3)

        assert med[0] == 1.0
        assert med[1] == 1.5
        assert med[2] == 2.0
        # Der Ausreisser wirkt erst ab seiner eigenen Stelle.
        assert med[3] == 3.0
        # Und erst wenn das Fenster ganz in den Ausreissern liegt, zieht er
        # den Median mit.
        assert med[4] == 100.0


class TestDieSchwelleGiltUeberAlle:
    """Der Kern der Integritaet dieses Befunds."""

    def test_mehr_zellen_heben_die_latte(self) -> None:
        assert schwelle_fuer(105) > schwelle_fuer(35)

    def test_der_befehl_zaehlt_alle_familien_zusammen(self) -> None:
        """Geankert auf der **Anforderung**: Die Zahl, die ins Urteil geht,
        entsteht aus der Hauptfamilie **und** den Nebenfamilien. Auf den
        Wortlaut zu ankern hat in dieser Reihe schon viermal gerissen."""
        quelle = _scan_quelle()
        zeile = next(
            z for z in quelle.splitlines() if z.strip().startswith("gesamt =")
        )

        assert "len(zellen)" in zeile
        assert "nebenfamilien" in zeile

    def test_und_uebergibt_die_summe_an_das_urteil(self) -> None:
        """Wuerde hier ``len(zellen)`` stehen, waere die Latte die der ersten
        Familie allein - bei dreifacher Gelegenheit."""
        quelle = _scan_quelle()

        assert "gepruefte_zellen=gesamt" in quelle
        assert "gepruefte_zellen=len(zellen)" not in quelle

    def test_es_gibt_kein_flag_das_die_familien_trennt(self) -> None:
        """Eine Familie allein zu scannen waere die bequemste Art, die Latte
        zu senken. Deshalb laufen sie immer zusammen."""
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "scan"
        )
        namen = {a.arg for a in knoten.args.args}

        assert "familie" not in namen
        assert "familien" not in namen


class TestBeideFamilienWerdenGerechnet:
    def test_volumen_und_spanne_stehen_da(self) -> None:
        quelle = _scan_quelle()

        assert "'Volumen'" in quelle
        assert "'Spanne'" in quelle

    def test_und_werden_gemeldet(self) -> None:
        quelle = _scan_quelle()

        assert "ueber der Schwelle" in quelle

    def test_die_spanne_kommt_aus_hoch_und_tief(self) -> None:
        quelle = _scan_quelle()

        assert "high" in quelle
        assert "low" in quelle
