"""Misst die Nachpruefung jede Generation auf ihrer eigenen Kerzenlaenge?

**Befund 217.** Die Fortsetzung von Befund 214, ein Befehl weiter.

``_pruefe_generation`` bewacht seit Befund 64, dass Generation und
Kerzenlaenge zusammenpassen. Befund 214 fand den Zweig, der daran vorbeiging.
Die Frage danach - **und wo noch?** - hat einen ganzen Befehl gefunden:
``cli nachpruefung`` nimmt ``--generation`` und ``--intervall`` und rief
keine der beiden Wachen.

Ohne Argumente nimmt er **alle** Generationen und ``-i D``. Dreiundzwanzig
der 53 Genome gehoeren zu Viertelstunden-Generationen; auf Tageskerzen
bedeuten ihre Periodenzahlen sechsundneunzigmal laengere Zeitraeume.

Er kostet zwar keinen Versuch - aber er faellt ein **Urteil**, das ein altes
ersetzen soll ("Aendert sich das Geraet, ist das Urteil neu zu faellen").
Ein Urteil auf der falschen Kerzenlaenge ist schlechter als keines.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import typer.main

import cli
from research.referenz import SPOTPUNKT
from research.seeds import GENERATIONS, VORGESEHEN


def _befehl(name: str):
    return typer.main.get_command(cli.app).commands[name]


class TestDerBefundSelbst:
    """Die Zahlen, auf denen der Befund steht - gemessen, nicht behauptet."""

    def test_ohne_argumente_nimmt_er_alle_generationen_auf_tageskerzen(self) -> None:
        params = {
            o: p.default for p in _befehl("nachpruefung").params
            for o in getattr(p, "opts", [])
        }

        assert params["--intervall"] == "D"
        assert params["--generation"] == "", "leer heisst: alle"

    def test_dreiundzwanzig_von_dreiundfuenfzig_gehoeren_nicht_auf_tageskerzen(
        self,
    ) -> None:
        gesamt = sum(len(v) for v in GENERATIONS.values())
        fremd = sum(
            len(GENERATIONS[g])
            for g in GENERATIONS
            if VORGESEHEN.get(g) not in (None, "D")
        )

        assert gesamt == 53
        assert fremd == 23


class TestFremdeGenerationenWerdenUebersprungen:
    @staticmethod
    def _quelle() -> str:
        baum = ast.parse(Path("cli.py").read_text())
        fn = next(
            n for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "nachpruefung"
        )
        return ast.unparse(fn)

    def test_sie_fragt_ob_die_generation_passt(self) -> None:
        assert "passt_zum_intervall" in self._quelle()

    def test_uebersprungen_und_nicht_abgebrochen(self) -> None:
        """Die uebrigen Generationen sind richtig gemessen; ein Abbruch naehme
        sie mit. Das unterscheidet diesen Befehl vom Wettbewerb, wo ein
        falscher Lauf Versuche kostet und deshalb abbricht."""
        quelle = self._quelle()

        assert "uebersprungen" in quelle
        assert "Uebersprungen auf" in quelle

    def test_es_wird_gesagt_und_nicht_still_gemacht(self) -> None:
        """Stilles Ueberspringen waere eine andere Art derselben Luege: Die
        Tabelle saehe vollstaendig aus und waere es nicht."""
        quelle = self._quelle()
        i = quelle.index("uebersprungen.append")
        rest = quelle[i:]

        assert "console.print" in rest

    def test_der_hinweis_nennt_die_richtige_kerzenlaenge(self) -> None:
        quelle = self._quelle()

        assert "VORGESEHEN.get(uebersprungen[0])" in quelle


class TestDerSpitzenkandidatHaengtAmReferenzpunkt:
    """``VORGESEHEN`` kennt die 0 nicht - dort steht ``None``, und das liesse
    jede Kerzenlaenge durch. Der Bestand steht auf der, auf der er gemessen
    wurde."""

    def test_vorgesehen_wuerde_ihn_durchlassen(self) -> None:
        """Der Grund, warum er eine eigene Regel braucht."""
        from research.seeds import passt_zum_intervall

        assert VORGESEHEN.get(0) is None
        assert passt_zum_intervall(0, "15")

    def test_er_wird_am_spotpunkt_geprueft(self) -> None:
        quelle = TestFremdeGenerationenWerdenUebersprungen._quelle()

        assert "SPOTPUNKT.intervall" in quelle

    def test_die_kerzenlaenge_ist_nicht_hingeschrieben(self) -> None:
        quelle = TestFremdeGenerationenWerdenUebersprungen._quelle()
        i = quelle.index("SPOTPUNKT.intervall")

        assert SPOTPUNKT.intervall == "D"
        assert "'D'" not in quelle[i - 200 : i + 200]


class TestJederBefehlMitBeidemHatEineWache:
    """**Die allgemeine Frage** - und wo noch?

    Ein Befehl, der Generation und Kerzenlaenge zugleich annimmt, kann sie
    falsch paaren. Diese Wache zaehlt sie auf, damit der naechste nicht
    wieder durchrutscht.
    """

    @staticmethod
    def _ohne_wache() -> list[str]:
        baum = ast.parse(Path("cli.py").read_text())
        aus = []
        for name, k in typer.main.get_command(cli.app).commands.items():
            opts = {o for p in k.params for o in getattr(p, "opts", [])}
            if not ({"--generation", "--intervall"} <= opts):
                continue
            fn = next(
                (
                    n for n in ast.walk(baum)
                    if isinstance(n, ast.FunctionDef)
                    and n.name == name.replace("-", "_")
                ),
                None,
            )
            quelle = ast.unparse(fn) if fn else ""
            if not any(
                w in quelle
                for w in ("_pruefe_generation", "_pruefe_spitze", "passt_zum_intervall")
            ):
                aus.append(name)
        return aus

    def test_keiner_ist_ohne(self) -> None:
        assert self._ohne_wache() == []

    def test_es_gibt_ueberhaupt_solche_befehle(self) -> None:
        """Sonst prueft der Test darueber eine leere Menge."""
        opts_je_befehl = [
            {o for p in k.params for o in getattr(p, "opts", [])}
            for k in typer.main.get_command(cli.app).commands.values()
        ]
        beide = [o for o in opts_je_befehl if {"--generation", "--intervall"} <= o]

        assert len(beide) >= 5

    def test_die_wache_haette_nachpruefung_gefunden(self) -> None:
        """Gegenprobe: derselbe Test gegen eine Fassung ohne die Pruefung."""
        ohne = "def nachpruefung(generation, intervall):\n    return 1"

        assert not any(
            w in ohne
            for w in ("_pruefe_generation", "_pruefe_spitze", "passt_zum_intervall")
        )


def test_die_wache_aus_befund_64_gibt_es_noch() -> None:
    quelle = inspect.getsource(cli._pruefe_generation)

    assert "passt_zum_intervall" in quelle
