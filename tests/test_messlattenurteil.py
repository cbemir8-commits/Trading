""""Deutlich ruhiger" war nicht gemessen - Befund 444.

``Benchmark.verdict_for`` vergleicht eine Strategie mit Kaufen und Halten.
Einer seiner Saetze lautete:

    Weniger Rendite, aber **deutlich ruhiger** - fuer ein Konto mit
    15 %-Kill-Switch der bessere Handel.

Die Bedingung dazu verlangte einen **irgendwie** kleineren Rueckgang und 0,6
der Rendite. Gemessen hiess das: Eine Strategie mit 74,9 % Rueckgang gegen
eine Messlatte von 75,0 % - ein Zehntel Prozentpunkt, das Fuenffache des
Kill-Switch - bekam das Urteil "deutlich ruhiger" und eine Empfehlung fuer
ein Konto, das bei 15 % abschaltet. Beide waeren laengst liquidiert gewesen.

**Der Massstab stand im Kopf desselben Moduls**:

    Eine Strategie, die zwei Drittel der Rendite bei einem Drittel des
    Drawdowns liefert, ist der Messlatte ueberlegen, obwohl sie weniger
    verdient.

Wer einen Massstab aufschreibt und einen anderen rechnet, hat zwei
Massstaebe, und einer davon ist falsch. Jetzt wird der aufgeschriebene
gerechnet.

**Zur Tragweite, damit sie nicht groesser klingt als sie ist**: ``verdict_for``
hat ausser Tests keinen Aufrufer. Die Falschaussage war real, aber latent -
sie stand bereit, nicht auf einem Bildschirm.
"""

from __future__ import annotations

import dataclasses

import pytest

from backtest.metrics import Metrics
from research.benchmark import RENDITEANTEIL, RUECKGANGSANTEIL, Benchmark

#: Halten, wie der Modulkopf es beschreibt: vervielfacht, aber mit 75 %
#: Rueckgang zwischendurch.
LATTE_RENDITE, LATTE_RUECKGANG = 400.0, 75.0

#: Der Kill-Switch des Kontos - ``settings.risk.max_drawdown_pct``.
SCHALTER = 15.0


def _metrics(rendite: float, rueckgang: float) -> Metrics:
    felder = dict.fromkeys((f.name for f in dataclasses.fields(Metrics)), 0.0)
    felder["total_return_pct"] = rendite
    felder["max_drawdown_pct"] = rueckgang
    return Metrics(**felder)


def _latte(rendite: float = LATTE_RENDITE, rueckgang: float = LATTE_RUECKGANG):
    return Benchmark(
        metrics=_metrics(rendite, rueckgang), start_price=1.0, end_price=5.0
    )


class TestDerFallAusBefund444:
    """74,9 % gegen 75,0 % - der Fall, der das Urteil erschlichen hat."""

    def test_er_heisst_nicht_mehr_deutlich_ruhiger(self) -> None:
        satz = _latte().verdict_for(_metrics(244.0, 74.9))

        assert "deutlich ruhiger" not in satz
        assert "etwas ruhiger" in satz

    def test_und_bekommt_keine_empfehlung_fuer_das_konto(self) -> None:
        satz = _latte().verdict_for(
            _metrics(244.0, 74.9), kill_switch_pct=SCHALTER
        )

        assert "der bessere Handel" not in satz
        assert "haette ausgeloest" in satz

    def test_der_satz_nennt_die_zahlen_statt_sie_zu_behaupten(self) -> None:
        satz = _latte().verdict_for(_metrics(244.0, 74.9))

        assert "61% der Rendite" in satz
        assert "100% des Rueckgangs" in satz

    def test_und_sagt_welcher_massstab_verfehlt_ist(self) -> None:
        satz = _latte().verdict_for(_metrics(244.0, 74.9))

        assert "zwei Drittel der Rendite bei einem Drittel des Rueckgangs" in satz
        assert "nicht erreicht" in satz


class TestDerMassstabDesModulkopfs:
    def test_ueber_dem_massstab_heisst_es_deutlich_ruhiger(self) -> None:
        """Siebzig Prozent der Rendite bei dreissig des Rueckgangs - der
        Massstab des Modulkopfs ist uebertroffen."""
        satz = _latte().verdict_for(_metrics(LATTE_RENDITE * 0.70, LATTE_RUECKGANG * 0.30))

        assert "deutlich ruhiger" in satz
        assert "nicht erreicht" not in satz

    def test_die_schneide_wird_nicht_zugesichert(self) -> None:
        """**Gemessen und bewusst nicht gepinnt.**

        Genau *auf* dem Massstab entscheidet ein Gleitkomma-Ulp:
        ``400 * (2/3) / 400`` ergibt 0,6666666666666665 und liegt damit
        unter ``2/3``. Welche Seite der Kandidat dort bekommt, ist keine
        Aussage ueber die Strategie - sie zuzusichern waere eine erfundene
        Genauigkeit, und eine Toleranz dafuer einzufuehren waere eine
        ungemessene Konstante. Festgehalten wird deshalb nur, **dass** die
        Schneide eine ist.
        """
        knapp = _latte().verdict_for(
            _metrics(LATTE_RENDITE * RENDITEANTEIL, LATTE_RUECKGANG * RUECKGANGSANTEIL)
        )

        assert "ruhiger" in knapp
        assert "67% der Rendite bei 33% des Rueckgangs" in knapp

    def test_knapp_darunter_in_der_rendite_reicht_nicht(self) -> None:
        satz = _latte().verdict_for(
            _metrics(
                LATTE_RENDITE * RENDITEANTEIL - 1.0,
                LATTE_RUECKGANG * RUECKGANGSANTEIL,
            )
        )

        assert "etwas ruhiger" in satz

    def test_knapp_darueber_im_rueckgang_reicht_auch_nicht(self) -> None:
        satz = _latte().verdict_for(
            _metrics(
                LATTE_RENDITE * RENDITEANTEIL,
                LATTE_RUECKGANG * RUECKGANGSANTEIL + 1.0,
            )
        )

        assert "etwas ruhiger" in satz

    def test_die_anteile_stehen_als_konstanten_da(self) -> None:
        """Nicht als 0,6 im Rumpf - der Kopf nennt zwei Drittel."""
        rendite, rueckgang = RENDITEANTEIL, RUECKGANGSANTEIL

        assert rendite == pytest.approx(2 / 3)
        assert rueckgang == pytest.approx(1 / 3)


class TestDerKillSwitchWirdNichtGeraten:
    def test_ohne_schwelle_keine_aussage_ueber_ein_konto(self) -> None:
        """Eine hier gepflegte 15 waere die zweite Quelle - vier Befunde
        dieses Projekts handeln davon (158, 159, 165)."""
        satz = _latte().verdict_for(_metrics(267.0, 12.0))

        assert "Kill-Switch" not in satz
        assert "der bessere Handel" not in satz

    def test_unter_der_schwelle_wird_es_empfohlen(self) -> None:
        satz = _latte().verdict_for(_metrics(267.0, 12.0), kill_switch_pct=SCHALTER)

        assert "bleibt er unter dem Kill-Switch von 15 %" in satz
        assert "der bessere Handel" in satz

    def test_darueber_wird_gewarnt_auch_wenn_der_massstab_haelt(self) -> None:
        """**Der Kern des Befundes**: Ruhiger *und* am Massstab heisst nicht
        tragbar. 25 % Rueckgang erfuellt zwei Drittel bei einem Drittel - und
        loest den Schalter trotzdem aus."""
        satz = _latte().verdict_for(_metrics(267.0, 25.0), kill_switch_pct=SCHALTER)

        assert "deutlich ruhiger" in satz
        assert "liegt er aber ueber dem Kill-Switch" in satz
        assert "der bessere Handel" not in satz

    def test_die_schwelle_kommt_aus_den_einstellungen(self) -> None:
        """Gegenprobe gegen eine erfundene Zahl: Was das Projekt als
        Kill-Switch fuehrt, steht in ``settings.risk``."""
        from core.config import get_settings

        assert float(get_settings().risk.max_drawdown_pct) == SCHALTER


class TestDieUebrigenZweige:
    def test_in_beidem_besser(self) -> None:
        satz = _latte().verdict_for(_metrics(500.0, 20.0))

        assert "in beidem" in satz

    def test_mehr_rendite_aber_nicht_ruhiger(self) -> None:
        satz = _latte().verdict_for(_metrics(500.0, 80.0))

        assert satz == "Mehr Rendite, aber nicht ruhiger."

    def test_schlechter_als_nichtstun(self) -> None:
        satz = _latte().verdict_for(_metrics(100.0, 80.0))

        assert "Schlechter als Nichtstun" in satz

    def test_eine_messlatte_ohne_gewinn_gibt_keinen_anteil(self) -> None:
        """Entartungsfall: Hat Halten nichts verdient, hat "zwei Drittel der
        Rendite" keinen Bezugspunkt - und ein Anteil waere eine Zahl ohne
        Bedeutung."""
        satz = _latte(rendite=-10.0).verdict_for(_metrics(-20.0, 40.0))

        assert "sagt nichts" in satz
        assert "%" not in satz.split("Kill-Switch")[0]

    def test_eine_messlatte_ohne_rueckgang_auch_nicht(self) -> None:
        satz = _latte(rueckgang=0.0).verdict_for(_metrics(100.0, -5.0))

        assert "sagt nichts" in satz

    def test_und_der_schalter_gilt_auch_dort(self) -> None:
        """Ohne Bezugspunkt fuer den Anteil bleibt die Kontofrage
        beantwortbar - der Rueckgang steht ja da."""
        satz = _latte(rendite=-10.0).verdict_for(
            _metrics(-20.0, 40.0), kill_switch_pct=SCHALTER
        )

        assert "haette ausgeloest" in satz


class TestDerAlteSatzIstWeg:
    def test_keine_behauptung_ohne_zahl(self) -> None:
        """Er war nicht nur ungemessen, er war falsch - und ein ungemessener
        Satz, der zufaellig stimmt, bliebe trotzdem ungemessen.

        Geprueft wird der **Code**, nicht die Datei: Der alte Satz steht
        oben in diesem Modul und im Docstring von ``verdict_for``, und dort
        gehoert er hin - als Aufzeichnung dessen, was dastand. Eine Suche
        ueber die ganze Quelle wuerde die Aufzeichnung mit der Behauptung
        verwechseln.
        """
        import ast
        import inspect

        from research import benchmark

        baum = ast.parse(inspect.getsource(benchmark))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Module | ast.ClassDef | ast.FunctionDef):
                doc = ast.get_docstring(knoten, clean=False)
                if doc is not None and knoten.body:
                    knoten.body = knoten.body[1:] or [ast.Pass()]
        ohne_doku = ast.unparse(ast.fix_missing_locations(baum))

        assert "15 %-Kill-Switch der bessere Handel" not in ohne_doku
        assert "self.return_pct * 0.6" not in ohne_doku
