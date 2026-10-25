"""Drei Erklaerungen, alle drei widerlegt - Befund 412.

Befund 411 hat gemessen, dass die Quartalskuerzung am Fensterschnitt haengt,
und offen gelassen, **wie** er sie erzeugt. Drei Erklaerungen lagen nahe:
ueberlappende Abschnitte, doppelt gezaehlte Trades, geballte Einstiege.
Gemessen traegt keine.

Damit kehrt sich die Lesart von 411 um, und das ist eine Berichtigung an einem
eigenen Eintrag: Der Fensterschnitt erzeugt die Abhaengigkeit nicht, er aendert
nur, ob das Waehrungsmass sie sieht.
"""

from __future__ import annotations

from research.grenzgedaechtnis import (
    ABSCHNITT_MITTEL,
    ABSCHNITT_TAGE,
    ABSCHNITT_UEBERLAPPUNGEN,
    ABSCHNITTE,
    FENSTERPROBEN,
    QUARTALSPROBE,
    traegt_eine_erklaerung,
)


def _probe(teil: str):
    return next(p for p in FENSTERPROBEN if teil in p.name)


class TestKeineErklaerungTraegt:
    def test_es_sind_drei(self) -> None:
        assert len(FENSTERPROBEN) == 3

    def test_und_keine_traegt(self) -> None:
        assert not traegt_eine_erklaerung()
        assert all(not p.traegt for p in FENSTERPROBEN)

    def test_jede_nennt_vermutung_und_messung(self) -> None:
        """Eine Widerlegung ohne die Vermutung daneben sagt nicht, was
        widerlegt ist."""
        for p in FENSTERPROBEN:
            assert len(p.vermutung) > 40, p.name
            assert len(p.gemessen) > 40, p.name


class TestDieAbschnitte:
    def test_sie_ueberlappen_nicht(self) -> None:
        assert ABSCHNITT_UEBERLAPPUNGEN == 0
        assert "null** ueberlappende Paare" in _probe("Ueberlappende").gemessen

    def test_und_sind_fast_ein_quartal(self) -> None:
        """Der Grund, warum Fenster- und Quartalseinteilung einander so
        nahe sind - und damit, warum ihr ICC-Unterschied eine Frage der
        Trennschaerfe ist und nicht eine zweite Abhaengigkeit."""
        assert ABSCHNITTE == 32
        assert ABSCHNITT_TAGE == (89, 92)
        assert abs(ABSCHNITT_MITTEL - 91.3) < 1e-9
        assert ABSCHNITT_TAGE[0] <= ABSCHNITT_MITTEL <= ABSCHNITT_TAGE[1]

    def test_gemessen_am_fenster_nicht_an_den_trades(self) -> None:
        text = _probe("Ueberlappende").gemessen

        assert "kein Trade liegt ausserhalb" in text


class TestDieKennung:
    def test_das_mehrfachvorkommen_ist_ein_namensartefakt(self) -> None:
        text = _probe("Doppelt").gemessen

        assert "Namensartefakt" in text
        assert "entry_index" in text

    def test_und_nichts_verschluesselt_darauf(self) -> None:
        text = _probe("Doppelt").gemessen

        assert "Nichts" in text and "verschluesselt" in text

    def test_die_warnung_steht_am_feld(self) -> None:
        """Dort sieht sie, wer die Kennung benutzen will."""
        import core.models

        quelle = core.models.__dict__.get("__file__")
        assert quelle
        from pathlib import Path

        text = Path(quelle).read_text(encoding="utf-8")

        assert "im Walk-Forward nicht eindeutig" in text
        assert "Aus 156 wuerden 73" in text

    def test_und_nennt_was_daran_haengt(self) -> None:
        from pathlib import Path

        import core.models

        text = Path(core.models.__file__).read_text(encoding="utf-8")

        assert "strategy_id-entry_index" in text
        assert "45 der 156" in text


class TestDieEinstiegeSindGleichmaessig:
    def test_die_messung_sagt_es(self) -> None:
        text = _probe("Einstiege").gemessen

        assert "0,5262" in text
        assert "40/66/50" in text

    def test_und_die_erste_fassung_war_verzerrt(self) -> None:
        """Der eigene Fehler gehoert dazu: Auf die Trade-Zeiten normiert
        liegt der erste Einstieg je Fenster per Definition auf 0."""
        text = _probe("Einstiege").gemessen

        assert "0,3205" in text
        assert "per Definition" in text
        assert "test_start/test_end" in text


class TestDieLesartKehrtSichUm:
    def test_der_kopf_sagt_dass_411_berichtigt_ist(self) -> None:
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "erzeugt** die" in text or "**erzeugt** die" in text
        assert "Berichtigung an" in text

    def test_und_stuetzt_sich_auf_die_r_messung_aus_411(self) -> None:
        """Die Umkehrung steht nicht fuer sich: Sie folgt aus den drei
        Widerlegungen **und** daraus, dass das R-Mass in beiden Modi
        dasselbe zeigt."""
        geschnitten = next(
            z for z in QUARTALSPROBE if not z.durchgehend and z.limits
        )
        konto = next(
            z for z in QUARTALSPROBE if z.durchgehend and not z.limits
        )

        assert abs(geschnitten.icc_r - konto.icc_r) < 0.01
        assert geschnitten.kuerzt_im_r_mass and konto.kuerzt_im_r_mass

    def test_was_jetzt_noch_offen_ist(self) -> None:
        import inspect

        import research.grenzgedaechtnis as g
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(g))

        assert "blind wird" in text
        assert "nicht gemessen" in text


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_alle_drei(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 412)

        assert "keine ueberlappenden Abschnitte" in eintrag.ergebnis
        assert "keine Doppelzaehlung" in eintrag.ergebnis
        assert "keine Einstiegsballung" in eintrag.ergebnis

    def test_und_die_umkehrung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 412)

        assert "kehrt sich die Lesart von 411 um" in eintrag.ergebnis

    def test_und_den_eigenen_fehler(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 412)

        assert "0,3205" in eintrag.ergebnis
        assert "bevor die Zahl irgendwo stand" in eintrag.ergebnis

    def test_und_411_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 411).zuletzt == 412
