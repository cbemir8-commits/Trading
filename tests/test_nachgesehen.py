"""Findet die Suche, was die Handsuche nicht gefunden hat? - Befund 425.

Abgenommen wird nicht gegen erfundene Fragen, sondern gegen die Faelle, in
denen von Hand gesucht und nichts gefunden wurde. Vier von fuenf werden
gefunden, einer nicht - und der bleibt stehen.
"""

from __future__ import annotations

import inspect

import pytest

from research.nachgesehen import (
    GRENZE,
    PROBEFAELLE,
    VORBEHALT,
    abnahme,
    bericht,
    bestand,
    durchsuche,
    flach,
    quote,
    rang,
    suchworte,
)


class TestDieAbnahmeAnDenEigenenFehlgriffen:
    """Der Kern: Das Werkzeug wird an den Fehlgriffen gemessen, die es
    verhindern soll - nicht an Fragen, die dazu erfunden wurden."""

    @pytest.mark.parametrize("fall", PROBEFAELLE, ids=lambda f: f.erwartet)
    def test_jeder_fall_verhaelt_sich_wie_verzeichnet(self, fall) -> None:
        platz = rang(fall)

        assert (platz is not None) == fall.gefunden_erwartet, (
            f"{fall.erwartet}: erwartet "
            f"{'gefunden' if fall.gefunden_erwartet else 'nicht gefunden'}, "
            f"gemessen {platz}"
        )

    def test_die_quote_ist_vier_von_fuenf(self) -> None:
        assert quote() == (4, 5)

    def test_die_beiden_teuren_faelle_sind_dabei(self) -> None:
        """423 und 424 haben je einen Arbeitsgang gekostet. Wenn das Werkzeug
        die nicht findet, loest es das Problem nicht, das es loesen soll."""
        nach_befund = {f.befund: f for f in PROBEFAELLE}

        assert rang(nach_befund[423]) is not None
        assert rang(nach_befund[424]) is not None

    def test_der_fehlschlag_steht_als_fehlschlag_da(self) -> None:
        """Eine Abnahme, aus der man die Fehlschlaege entfernt, misst nichts."""
        offen = [f for f in PROBEFAELLE if not f.gefunden_erwartet]

        assert len(offen) == 1
        assert offen[0].erwartet == "gates.py:stichprobe_wie_im_gate"

    def test_und_der_kopf_nennt_ihn_mit_grund(self) -> None:
        import research.nachgesehen as n

        kopf = n.__doc__ or ""

        assert "Der fuenfte wird **nicht** gefunden" in kopf
        assert "haeufigsten Woertern des" in kopf
        assert "Grenze des Verfahrens" in kopf

    def test_die_abnahme_ist_gerechnet(self) -> None:
        """Die Raenge stehen nirgends als Zahl - sonst waere es die siebte
        gepflegte Zahl, die Befund 408 verzeichnen muesste."""
        quelle = inspect.getsource(abnahme)

        assert "rang(fall" in quelle
        for ziffer in ("Rang 3", "= 3", "= 5"):
            assert ziffer not in quelle


class TestDerBestandDeckBeidesAb:
    def test_er_umfasst_forschung_und_befehle(self) -> None:
        """Der Fehlgriff aus 418 lag in ``cli aufteilung`` - ohne ``cli.py``
        im Bestand waere er nicht zu finden."""
        dateien = {stelle.datei for stelle, _ in bestand()}

        assert "cli.py" in dateien
        assert "erreichbarkeit.py" in dateien
        assert "verbund.py" in dateien

    def test_er_ist_so_gross_wie_der_kopf_sagt(self) -> None:
        """Gegen stilles Veralten der Zahlen im Modulkopf (Befund 408)."""
        import research.nachgesehen as n

        kopf = n.__doc__ or ""
        module = {d for stelle, _ in bestand() if (d := stelle.datei) != "cli.py"}

        assert "104 Forschungsmodule" in kopf
        assert abs(len(module) - 104) <= 3, f"gemessen {len(module)} Module"
        assert 1300 <= len(bestand()) <= 1700, f"gemessen {len(bestand())}"

    def test_gelesen_wird_der_quelltext_nicht_der_importstand(self) -> None:
        """``test_wachenaudit`` haengt genau daran (Vermerk aus Befund 409):
        Ein Modul, das niemand importiert hat, loest dort nicht auf. Hier
        waere das ein stiller Ausfall."""
        quelle = inspect.getsource(bestand)

        assert "ast.parse" in quelle
        assert "read_text" in quelle
        assert "import_module" not in quelle


class TestWasDieSucheNichtTut:
    def test_eine_unsinnsfrage_findet_nichts(self) -> None:
        """Die Gegenprobe: Eine Suche, die immer etwas findet, sagt nichts."""
        assert durchsuche("zzzqqqxyz plumpudding klabautermann") == ()

    def test_zu_kurze_worte_zaehlen_nicht(self) -> None:
        assert suchworte("der je und im an") == ()
        assert durchsuche("der je und") == ()

    def test_sie_nennt_je_treffer_die_gefundenen_worte(self) -> None:
        """Ein Treffer ohne Begruendung ist nicht pruefbar - und pruefen ist
        hier ausdruecklich Pflicht (Befund 118)."""
        frage = "Deflated Sharpe Versuchsstand"
        gefragt = set(suchworte(frage))
        treffer = durchsuche(frage)

        assert treffer
        for t in treffer:
            assert t.worte, str(t.stelle)
            assert set(t.worte) <= gefragt, str(t.stelle)

    def test_der_bericht_traegt_den_vorbehalt(self) -> None:
        text = bericht("Deflated Sharpe Versuchsstand", grenze=3)

        assert VORBEHALT in text
        assert "Verdachtsfaelle, keine Antworten" in text

    def test_und_die_eigene_quote_dazu(self) -> None:
        """Ein Werkzeug, das seine Treffer zeigt und seine Trefferquote nicht,
        laedt dazu ein, es fuer vollstaendig zu halten."""
        text = bericht("Deflated Sharpe Versuchsstand")

        assert "Abnahme an den eigenen Fehlgriffen" in text
        assert f"4 von 5 in den ersten {GRENZE}" in text


class TestDieRangfolgeIstNichtNachgestellt:
    """Befund 418 noch einmal: 5 von 5 gibt es, aber nur bei genau einem
    Gewicht, mit schlechteren Nachbarn - das ist eine ausgewaehlte Spitze."""

    def test_der_kopf_nennt_die_spitze_und_verwirft_sie(self) -> None:
        import research.nachgesehen as n

        kopf = n.__doc__ or ""

        assert "erreicht 5 von 5" in kopf
        assert "nur bei genau dem Gewicht 1,5" in kopf
        assert "eingebaut wird es deshalb nicht" in kopf

    def test_und_im_code_steht_kein_kopfgewicht(self) -> None:
        """Die Gegenprobe zum Satz darueber."""
        import research.nachgesehen as n

        quelle = inspect.getsource(n)
        rechnung = quelle.split('"""', 2)[-1]

        assert "kopfgewicht" not in rechnung.lower()

    def test_das_gewicht_ist_allein_die_seltenheit(self) -> None:
        from research.nachgesehen import gewicht

        selten = gewicht(flach("woelbung"))
        haeufig = gewicht(flach("befund"))

        assert selten > haeufig


class TestDerBefehl:
    def test_es_gibt_ihn(self) -> None:
        import cli

        namen = {c.name or c.callback.__name__ for c in cli.app.registered_commands}

        assert "nachgesehen" in namen

    def test_er_steht_vor_dem_einsprungpunkt(self) -> None:
        """Ein Befehl nach ``if __name__ == '__main__'`` wird nie
        registriert - gemessen beim Bau, der erste Anlauf lief ins Leere."""
        from pathlib import Path

        text = Path(inspect.getsourcefile(__import__("cli"))).read_text()

        assert text.index("def nachgesehen(") < text.index('if __name__ == "__main__"')

    def test_sein_docstring_sagt_wann_man_ihn_braucht(self) -> None:
        import cli

        doc = cli.nachgesehen.__doc__ or ""

        assert "**Vor** dem Messen" in doc
        assert "Befund 118" in doc
        assert "Kostet keinen Versuch" in doc


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_acht_faelle(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 425)

        assert "acht" in eintrag.ergebnis
        assert "423" in eintrag.ergebnis and "424" in eintrag.ergebnis

    def test_und_die_gemessene_quote_samt_fehlschlag(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 425)

        assert "vier von fuenf" in eintrag.ergebnis
        assert "stichprobe_wie_im_gate" in eintrag.ergebnis

    def test_und_dass_die_spitze_nicht_eingebaut_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 425)

        assert "ausgewaehlte Spitze" in eintrag.ergebnis

    def test_und_424_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 424).zuletzt == 425
