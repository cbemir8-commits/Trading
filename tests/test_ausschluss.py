"""Was der Analyst nicht weiss - und deshalb immer wieder vorschlaegt.

Drei Tests tragen diese Datei:

``test_ohne_bestandene_permutation_wird_nichts_ausgeschlossen`` - Der
wichtigste. Eine Gruppierung, die dem Zufall nicht standhaelt, darf keine
Vorschlaege verhindern. Ein falscher Ausschluss ist teurer als ein fehlender:
Er schliesst einen Weg zu, den niemand mehr prueft.

``test_eine_familie_mit_einer_guten_regel_bleibt_offen`` - Massgeblich ist
die **beste** Regel einer Familie, nicht ihr Mittel. Sonst schliesst ein
Ausreisser nach unten eine Familie, in der etwas Brauchbares steht.

``test_die_automatische_zuordnung_trifft_die_handgeschriebene`` - Die
Familienzuordnung lebte nur im Test. Jetzt steht sie im Produktivcode und
muss dieselbe sein, sonst haben Auftrag und Befund verschiedene Wahrheiten.
"""

from __future__ import annotations

import pytest

from research.ausschluss import (
    GEMESSENE_REGELN,
    GESCHEITERTE_EIGENBAUTEN,
    Ausschluesse,
    Sackgasse,
    aus_familienbild,
)
from research.familien import Familienbild, Regel, familie_von
from tests.test_familien import GEMESSEN


def bild_aus(regeln: list[Regel]) -> Familienbild:
    return Familienbild(regeln=regeln)


def echtes_bild() -> Familienbild:
    return bild_aus(
        [
            Regel(
                name=n, trades=t, sharpe_je_trade=s,
                familie=familie_von(n) or "?", rho=r,
            )
            for n, t, s, r in GEMESSENE_REGELN
        ]
    )


class TestZuordnung:
    def test_die_automatische_zuordnung_trifft_die_handgeschriebene(self) -> None:
        """**Eine Wahrheit, nicht zwei.**

        Die Familienzuordnung stand bisher nur in ``tests/test_familien.py``.
        Der Auftrag an den Analysten braucht sie aber im Produktivcode - und
        wenn die beiden auseinanderlaufen, sagt der Befund etwas anderes als
        der Auftrag.
        """
        falsch = [
            (name, familie_von(name), familie)
            for name, _, _, familie, _ in GEMESSEN
            if familie_von(name) != familie
        ]

        assert falsch == [], f"Fehlzuordnungen: {falsch}"

    def test_die_reihenfolge_der_schluessel_traegt(self) -> None:
        """'Rueckkehr zum Volumenschwerpunkt' enthaelt beide Schluesselwoerter.
        Wer die Liste umsortiert, aendert eine Zuordnung."""
        assert familie_von("Rueckkehr zum Volumenschwerpunkt") == "Rueckkehr"
        assert familie_von("Volumenschock mit Fortsetzung") == "Volumen"

    def test_unbekanntes_faellt_heraus_statt_in_einen_topf(self) -> None:
        """``None`` statt 'Sonstige': Ein Sammeltopf waere eine Familie, die
        keine ist - und ueber die dann eine Spannweite gerechnet wuerde."""
        assert familie_von("Carry-Beteiligung") is None
        assert familie_von("Beteiligt, ausser es ist ueberhitzt") is None


class TestAusschluss:
    def test_die_rueckkehr_familie_ist_geschlossen(self) -> None:
        """Auf den echten Messwerten ist genau eine Familie zu: Fuenf Regeln,
        und auch die beste liegt unter der Geraden."""
        aus = aus_familienbild(echtes_bild())

        geschlossen = {s.familie for s in aus.geschlossene}
        assert geschlossen == {"Rueckkehr"}
        assert aus.permutation_haelt
        assert aus.traegt

    def test_eine_familie_mit_einer_guten_regel_bleibt_offen(self) -> None:
        """**Massgeblich ist die beste Regel, nicht das Mittel.**

        Sonst schliesst ein Ausreisser nach unten eine Familie, in der etwas
        Brauchbares steht - und der Analyst darf sie nie wieder vorschlagen.
        """
        gemischt = Sackgasse(familie="x", regeln=6, bestes_residuum=0.12)
        durchgehend = Sackgasse(familie="y", regeln=6, bestes_residuum=-0.4)

        assert not gemischt.geschlossen
        assert durchgehend.geschlossen

    def test_zu_wenige_regeln_schliessen_keine_familie(self) -> None:
        """Zwei schlechte Regeln sind kein Urteil ueber eine Regelart."""
        duenn = Sackgasse(familie="x", regeln=3, bestes_residuum=-0.9)

        assert not duenn.geschlossen

    def test_ohne_bestandene_permutation_wird_nichts_ausgeschlossen(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Ein falscher Ausschluss ist teurer als ein fehlender: Er schliesst
        einen Weg zu, den danach niemand mehr prueft. Haelt die Gruppierung
        der Zufallsprobe nicht stand, darf sie nichts verhindern - auch wenn
        einzelne Familien geschlossen aussehen.
        """
        aus = Ausschluesse(
            sackgassen=[Sackgasse(familie="x", regeln=8, bestes_residuum=-0.9)],
            permutation_haelt=False,
        )

        assert aus.geschlossene, "die Familie sieht geschlossen aus"
        assert not aus.traegt, "darf aber nichts ausschliessen"
        assert "gemessen und geschlossen" not in aus.als_auftrag()


class TestAuftragstext:
    def test_der_zielkonflikt_steht_drin_und_ist_kein_verbot(self) -> None:
        """Qualitaet und Unabhaengigkeit laufen mit +0,48 gegeneinander. Das
        gehoert in den Auftrag - aber als Begruendung, warum es schwer ist,
        nicht als Verbot."""
        text = aus_familienbild(echtes_bild()).als_auftrag()

        assert "Zielkonflikt" in text
        assert "+0.480" in text
        assert "kein Verbot" in text
        assert "Ausnahme von einem gemessenen Muster" in text

    def test_die_eigenbauten_stehen_im_auftrag(self) -> None:
        """Sie stehen nicht im Journal, weil sie ausserhalb des
        Research-Loops entstanden sind - genau deshalb fehlten sie.

        Die Ueberschrift heisst seit Befund 122 nicht mehr "gescheitert":
        Seit die Liste aus dem Versuchsverzeichnis kommt, stehen auch die
        Verbuende darin, und deren Guete liegt auf Hoehe des Bestands. Sie
        sind nicht schlecht - sie haben nicht gereicht.
        """
        text = aus_familienbild(
            echtes_bild(), gescheiterte=GESCHEITERTE_EIGENBAUTEN
        ).als_auftrag()

        assert "Bereits gemessen" in text
        assert "nicht gereicht" in text
        assert len(GESCHEITERTE_EIGENBAUTEN) == 8
        for name, _, _ in GESCHEITERTE_EIGENBAUTEN:
            assert name in text

    def test_ohne_belege_bleibt_der_auftrag_leer(self) -> None:
        """Kein Text ist besser als ein Abschnitt, der nichts sagt - er
        verbraucht Kontext und suggeriert Wissen."""
        leer = Ausschluesse()

        assert leer.als_auftrag() == ""

    def test_ein_schwacher_widerspruch_wird_nicht_erwaehnt(self) -> None:
        schwach = Ausschluesse(widerspruch=0.1, permutation_haelt=True)

        assert "Zielkonflikt" not in schwach.als_auftrag()

    def test_zu_duennes_familienbild_liefert_nichts(self) -> None:
        duenn = aus_familienbild(
            bild_aus([Regel(name="a", trades=99, sharpe_je_trade=0.2, familie="x")])
        )

        assert duenn.sackgassen == []
        assert not duenn.traegt
        assert duenn.als_auftrag() == ""


class TestPrompt:
    def test_die_ausschluesse_stehen_zwischen_auftrag_und_aufgabe(self) -> None:
        """Erst was gebraucht wird, dann was dafuer ausscheidet, dann die
        Aufgabe. Umgekehrt liest sich der Prompt als Verbotsliste."""
        from research.analyst import build_prompt
        from research.gates import GateThresholds

        aus = aus_familienbild(echtes_bild(), gescheiterte=GESCHEITERTE_EIGENBAUTEN)
        prompt = build_prompt(
            journal=[], thresholds=GateThresholds(), ausschluesse=aus
        )

        assert "Was gemessen und geschlossen ist" in prompt
        assert prompt.index("Was gemessen und geschlossen") < prompt.index("## Auftrag")

    def test_ohne_ausschluesse_bleibt_der_prompt_wie_er_war(self) -> None:
        from research.analyst import build_prompt
        from research.gates import GateThresholds

        vorher = build_prompt(journal=[], thresholds=GateThresholds())
        leer = build_prompt(
            journal=[], thresholds=GateThresholds(), ausschluesse=Ausschluesse()
        )

        assert vorher == leer

    def test_der_prompt_waechst_messbar(self) -> None:
        """Rund 1,5 kB - genug, um etwas zu sagen, klein genug, um den
        Auftrag nicht zu ertraenken."""
        from research.analyst import build_prompt
        from research.gates import GateThresholds

        aus = aus_familienbild(echtes_bild(), gescheiterte=GESCHEITERTE_EIGENBAUTEN)
        ohne = build_prompt(journal=[], thresholds=GateThresholds())
        mit = build_prompt(
            journal=[], thresholds=GateThresholds(), ausschluesse=aus
        )

        assert len(mit) - len(ohne) == pytest.approx(1570, abs=250)


class TestAusDemVersuchsverzeichnis:
    """Befund 122 - die Liste war eine Abschrift und hatte drei zu wenig.

    ``GESCHEITERTE_EIGENBAUTEN`` trug acht Regeln, ``state/trials.json`` elf.
    Die drei fehlenden waren die **Verbuende** - und der Auftrag lenkt den
    Analysten ausdruecklich auf ein *"zweites, unabhaengiges Signal, das
    parallel gehandelt wird"*, also auf einen Verbund.

    Die unguenstigste Auslassung, die denkbar war.
    """

    def test_alle_eintraege_mit_guete_kommen_mit(self, tmp_path) -> None:
        import json

        from research.ausschluss import aus_versuchsverzeichnis

        datei = tmp_path / "trials.json"
        datei.write_text(
            json.dumps(
                {
                    "format": 2,
                    "trials": 20,
                    "grundstock": 17,
                    "versuche": [
                        {"kennung": "A", "trades": 100, "sharpe_je_trade": 0.25},
                        {"kennung": "B", "trades": 200, "sharpe_je_trade": -0.1},
                        {"kennung": "C", "trades": 50, "sharpe_je_trade": 0.3},
                    ],
                }
            )
        )

        gefunden = aus_versuchsverzeichnis(datei)

        assert gefunden == (("A", 100, 0.25), ("B", 200, -0.1), ("C", 50, 0.3))

    def test_eintraege_ohne_guete_fallen_heraus(self, tmp_path) -> None:
        """``None`` heisst "nicht erhoben", nicht "kein Vorteil" - ein solcher
        Eintrag traegt nichts zum Auftrag bei."""
        import json

        from research.ausschluss import aus_versuchsverzeichnis

        datei = tmp_path / "trials.json"
        datei.write_text(
            json.dumps(
                {
                    "format": 2,
                    "trials": 2,
                    "grundstock": 0,
                    "versuche": [
                        {"kennung": "mit", "trades": 100, "sharpe_je_trade": 0.25},
                        {"kennung": "ohne", "trades": 100},
                    ],
                }
            )
        )

        assert [n for n, _, _ in aus_versuchsverzeichnis(datei)] == ["mit"]

    def test_ohne_datei_kein_absturz(self, tmp_path) -> None:
        """Dann greift die alte Liste als Rueckfall - ein leerer Auftrag waere
        schlechter als ein veralteter."""
        from research.ausschluss import aus_versuchsverzeichnis

        assert aus_versuchsverzeichnis(tmp_path / "gibtsnicht.json") == ()

    def test_das_echte_verzeichnis_hat_mehr_als_die_liste(self) -> None:
        """Der Fund selbst, als Test.

        Faende diese Pruefung eines Tages Gleichstand, waere die Abschrift
        nachgepflegt worden - und dann gehoert sie erst recht weg.
        """
        from pathlib import Path

        from research.ausschluss import (
            GESCHEITERTE_EIGENBAUTEN,
            aus_versuchsverzeichnis,
        )

        echt = aus_versuchsverzeichnis(Path("state/trials.json"))
        if not echt:  # ohne Zustandsdatei nichts zu vergleichen
            return
        assert len(echt) > len(GESCHEITERTE_EIGENBAUTEN)

    def test_die_verbuende_sind_dabei(self) -> None:
        """Sie fehlten, und sie sind die wichtigsten."""
        from pathlib import Path

        from research.ausschluss import aus_versuchsverzeichnis

        echt = aus_versuchsverzeichnis(Path("state/trials.json"))
        if not echt:
            return
        verbuende = [n for n, _, _ in echt if n.startswith("Verbund")]
        assert len(verbuende) == 3
