"""Wohin ein Sweep seine Versuche bucht.

**Befund 234.** Ich hatte das als "zwei Buecher ueber dieselbe Zahl"
aufgeschrieben - ein lokaler Zaehler und ein Verzeichnis, die auseinander
laufen koennen. Nachgemessen stimmt das nicht: Es gibt **eine** Datei und
**einen** Schreiber (``versuche.speichern``), und dessen Kopf sagt das auch
richtig. ``_verzeichne`` vergleicht nicht zwei Dateien, sondern die Datei mit
dem Schleifenzaehler eines Laufs.

Was wirklich passiert, steht in ``save_trials``::

    verzeichnis.grundstock = trials - len(verzeichnis.eintraege)

Der Ueberschuss geht in den **Grundstock**. Und der ist im eigenen Kopf so
beschrieben:

    "Versuche von vor der Einfuehrung des Verzeichnisses. Ohne Einzelnachweis,
     und das bleibt so."

Das Feld, das Vorgeschichte heissen soll, ist die Ablage fuer alles Neue der
fuenf Befehle, die den Zaehler fortschreiben (``wettbewerb``, ``research``,
``landschaft``, ``machbarkeit``, ``adaptiv``). Einen Eintrag mit Herkunft
hinterlassen nur ``korb`` und ``verbund``, und die beiden Mengen
ueberschneiden sich nicht.

Belegt ist das nicht nur am Code: Zwischen ``a2e6362`` und ``7120d27`` waechst
der Grundstock von 166 auf 187, waehrend die Eintraege bei 11 stehen bleiben.
Befund 104 benennt diese 21 - ein Rauchtest ueber 61 Befehle, keine einzige
gepruefte Hypothese. Sie liegen heute unter "Vorgeschichte".

Was daraus folgt
----------------
Die Frage aus Befund 233 - ob ein Sweep am Bestand als Versuch zaehlt - ist
aus der Akte **nicht** zu beantworten. Nicht, weil Eintraege fehlen, sondern
weil Sweeps als Vorgeschichte abgelegt werden.

Hier wird nichts umgebucht. Wie Versuche gebucht werden, steuert die Haerte
des einzigen noch offenen Gates, und die fuenf Befehle laufen in diesem
Behaelter nicht (sie brauchen Kerzen). Ein ungepruefter Eingriff dort waere
genau das, was dieses Projekt nicht tut.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from research import versuche as versuchsverzeichnis
from research.admission import save_trials

#: Befehle, die den Zaehler fortschreiben - ueber ``save_trials``, also in den
#: Grundstock.
SCHREIBER = ("adaptiv", "landschaft", "machbarkeit", "research", "wettbewerb")

#: Befehle, die einen Eintrag **mit Herkunft** hinterlassen.
BUCHFUEHRER = ("korb", "verbund")


def _befehle_mit(text: str) -> set[str]:
    baum = ast.parse(Path("cli.py").read_text())
    return {
        n.name
        for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef)
        and not n.name.startswith("_")
        and text in ast.unparse(n)
    }


class TestWerWohinBucht:
    def test_wer_den_zaehler_fortschreibt(self) -> None:
        assert _befehle_mit("save_trials") == set(SCHREIBER)

    def test_wer_herkunft_hinterlaesst(self) -> None:
        assert _befehle_mit("_verzeichne(") == set(BUCHFUEHRER)

    def test_die_beiden_mengen_ueberschneiden_sich_nicht(self) -> None:
        """Kein Befehl tut beides."""
        assert set(SCHREIBER) & set(BUCHFUEHRER) == set()


class TestDerGrundstockNimmtAlles:
    """**Der Befund in einer Messung**, auf einer Kopie, nicht am Bestand."""

    @staticmethod
    def _kopie(tmp_path: Path) -> Path:
        ziel = tmp_path / "trials.json"
        ziel.write_text(Path("state/trials.json").read_text())
        return ziel

    def test_gemeldete_versuche_landen_in_der_vorgeschichte(
        self, tmp_path: Path
    ) -> None:
        pfad = self._kopie(tmp_path)
        vorher = json.loads(pfad.read_text())

        save_trials(pfad, vorher["trials"] + 5)

        nachher = json.loads(pfad.read_text())
        assert nachher["grundstock"] == vorher["grundstock"] + 5
        assert len(nachher["versuche"]) == len(vorher["versuche"])

    def test_der_grundstock_verspricht_das_gegenteil(self) -> None:
        """Sein Kopf sagt "von vor der Einfuehrung" - und "das bleibt so"."""
        kopf = inspect.getdoc(versuchsverzeichnis.Verzeichnis) or ""
        quelle = inspect.getsource(versuchsverzeichnis.Verzeichnis)

        assert "vor der Einfuehrung des Verzeichnisses" in quelle
        assert "Ohne Einzelnachweis" in quelle
        assert kopf

    def test_es_ist_nur_ein_schreiber(self) -> None:
        """Die Korrektur an meiner eigenen Behauptung: keine zwei Buecher."""
        kopf = inspect.getdoc(versuchsverzeichnis.speichern) or ""

        assert "nur diese Funktion schreibt" in kopf


class TestWasDieAkteHergibt:
    @staticmethod
    def _zaehler() -> dict:
        return json.loads(Path("state/trials.json").read_text())

    def test_die_summe_stimmt(self) -> None:
        d = self._zaehler()

        assert d["grundstock"] + len(d["versuche"]) == d["trials"]

    def test_der_grosse_teil_traegt_keine_herkunft(self) -> None:
        """187 von 198 - deshalb ist die Frage aus 233 nicht zu beantworten."""
        d = self._zaehler()

        assert d["grundstock"] > 10 * len(d["versuche"])

    def test_kein_erfasster_versuch_stammt_aus_einem_sweep(self) -> None:
        """Was Herkunft traegt, kommt aus Korb- und Verbundlaeufen. Das ist
        kein Beleg, dass Sweeps nichts beigetragen haben - im Gegenteil,
        Befund 104 zaehlt 21 davon. Es heisst nur, dass man sie nicht sieht.
        """
        herkuenfte = {v["herkunft"] for v in self._zaehler()["versuche"]}

        assert herkuenfte
        for h in herkuenfte:
            assert "landschaft" not in h and "machbarkeit" not in h


def test_hier_wird_nichts_umgebucht() -> None:
    """**Die Zusicherung, die dieser Befund gibt.**

    Wie Versuche gebucht werden, steuert die Haerte des einzigen noch offenen
    Gates. Ein Eingriff, der den Zaehler senkte, wuerde die Latte senken - und
    zwar ohne Messung, weil die betroffenen Befehle hier nicht laufen.
    """
    d = json.loads(Path("state/trials.json").read_text())

    assert d["trials"] == 198, "der Zaehler bleibt, wo er ist"
