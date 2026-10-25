"""Die Stichprobe ist stabil, und mein Rauschen war geschlossen - Befund 418.

Befund 417 hat aus dreizehn Beobachtungen Unterschied zwischen drei
Haltedeckeln geschlossen, die Stichprobenkorrektur habe "ihr eigenes Rauschen".
Geschlossen, nicht gemessen - und gemessen ist es falsch.

Die Oberflaeche dafuer gab es schon: ``cli aufteilung`` aus Befund 400 misst
jede Gate-Groesse ueber elf Aufteilungen mit einem Balken Versatz. Sie fuehrte
ausgerechnet die wirksame Stichprobe nicht mit.
"""

from __future__ import annotations

import inspect

import pytest

from research.aufteilung import (
    BINDENDE_EINTEILUNG_JE_AUFTEILUNG,
    STICHPROBE_JE_AUFTEILUNG,
    VERSATZ,
)


class TestDieGemesseneStreuung:
    def test_ueber_elf_aufteilungen(self) -> None:
        assert STICHPROBE_JE_AUFTEILUNG["aufteilungen"] == len(VERSATZ) == 11

    def test_sie_bewegt_sich_um_vier(self) -> None:
        s = STICHPROBE_JE_AUFTEILUNG

        assert (s["unten"], s["oben"]) == (115, 119)
        assert s["oben"] - s["unten"] == s["spanne"] == 4
        assert s["streuung"] == pytest.approx(1.33)

    def test_der_gemeldete_punkt_liegt_am_unteren_rand(self) -> None:
        """Der Versatz 0 ist der massgebliche Punkt - und er ist der
        **strengste** der elf, nicht der mittlere."""
        from research.referenz import SPOTPUNKT

        assert STICHPROBE_JE_AUFTEILUNG["unten"] == SPOTPUNKT.effektiv

    def test_die_bindende_einteilung_haelt_ueber_alle(self) -> None:
        """Nebenbefund zu Befund 410: Auch **woran** die Kuerzung haengt, ist
        keine Frage der Aufteilung."""
        assert BINDENDE_EINTEILUNG_JE_AUFTEILUNG == "Kalenderquartal"


class TestDasWiderlegtDenSatzAusVierhundertsiebzehn:
    def test_die_deckelspanne_ist_ein_mehrfaches_der_messstreuung(self) -> None:
        from research.haltedeckel import stichprobenspanne

        unten, oben = stichprobenspanne()
        deckel = oben - unten

        assert deckel == 13
        assert deckel > 3 * STICHPROBE_JE_AUFTEILUNG["spanne"] - 1
        assert deckel / STICHPROBE_JE_AUFTEILUNG["streuung"] > 9

    def test_also_ist_es_eine_echte_wirkung(self) -> None:
        """Der Punkt des Befundes in einem Satz."""
        from research.haltedeckel import stichprobenspanne

        unten, oben = stichprobenspanne()

        assert (oben - unten) > STICHPROBE_JE_AUFTEILUNG["spanne"] * 3

    def test_der_kopf_von_haltedeckel_nimmt_es_zurueck(self) -> None:
        import research.haltedeckel as h

        kopf = h.__doc__ or ""

        assert "Das ist gemessen und falsch" in kopf
        assert "in der bequemen Richtung falsch" in kopf

    def test_und_haelt_den_schluss_fest(self) -> None:
        """Zurueckgenommen ist das Argument, nicht das Ergebnis."""
        import research.haltedeckel as h

        kopf = h.__doc__ or ""

        assert "Der Schluss oben bleibt" in kopf
        assert "Das tragende Argument ist" in kopf

    def test_der_kopf_von_aufteilung_sagt_es_auch(self) -> None:
        import research.aufteilung as a
        from tests.quelltext import nur_prosa

        text = nur_prosa(inspect.getsource(a))

        assert "widerlegt eine Behauptung aus Befund 417" in text
        assert "kein Rauschen" in text


class TestDerBefehlFuehrtDieGroesseMit:
    """Der Einbau: Die Groesse, deren Streuung 417 behauptet hat, fehlte auf
    genau der Oberflaeche, die fuer Streuungen gebaut ist."""

    def _quelle(self) -> str:
        import cli

        return inspect.getsource(cli.aufteilung)

    def test_sie_wird_gesammelt(self) -> None:
        quelle = self._quelle()

        assert 'gesammelt["wirksame Stichprobe"]' in quelle
        assert "stichprobe_wie_im_gate(" in quelle

    def test_und_steht_in_der_tafel(self) -> None:
        assert 'tafel.add_column("n_eff"' in self._quelle()

    def test_und_wird_mit_spanne_und_streuung_berichtet(self) -> None:
        quelle = self._quelle()

        assert "Wirksame Stichprobe:" in quelle
        assert "stichprobe_streuung" in quelle

    def test_und_nennt_die_bindende_einteilung(self) -> None:
        """Gesammelt und nicht gedruckt waere genau die stille Sammlung, die
        dieses Projekt wiederholt gefunden hat (394, 405, 415)."""
        quelle = self._quelle()

        assert "einteilungen.add(" in quelle
        assert "gebunden am" in quelle

    def test_die_einteilungen_werden_auch_benutzt(self) -> None:
        """Die Gegenprobe zum Satz darueber: Eine Menge, die gefuellt und
        nie gelesen wird, ist keine Auskunft."""
        quelle = self._quelle()

        assert quelle.count("einteilungen") >= 3


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_zahlen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 418)

        assert "**115 bis " in eintrag.ergebnis
        assert "**1,33**" in eintrag.ergebnis

    def test_und_nennt_den_eigenen_fehler_als_solchen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 418)

        assert "Gemessen ist das **falsch**" in eintrag.ergebnis
        assert "in der bequemen Richtung falsch" in eintrag.ergebnis

    def test_und_was_417_nicht_verliert(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 418)

        assert "Was 417 nicht verliert" in eintrag.ergebnis
        assert "eingebaut wird nichts" in eintrag.ergebnis

    def test_und_417_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 417).zuletzt == 418
