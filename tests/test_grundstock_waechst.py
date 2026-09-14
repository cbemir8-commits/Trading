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
#: Grundstock, **ohne Einzelnachweis**.
#:
#: Waren fuenf, sind drei (Befund 282): ``landschaft`` und ``machbarkeit``
#: schreiben jetzt Einzelnachweise. Die drei hier sind Suchlaeufe und keine
#: Sweeps am Bestand - bei ihnen war nie strittig, ob sie zaehlen, und sie
#: laufen in diesem Behaelter nicht (``wettbewerb`` braucht Boersenkerzen).
#: Die Luecke bleibt also, sie ist nur kleiner und genau benannt.
SCHREIBER = ("adaptiv", "research", "wettbewerb")

#: Befehle, die einen Eintrag **mit Herkunft** hinterlassen.
#:
#: ``landschaft`` und ``machbarkeit`` sind mit Befund 282 dazugekommen - die
#: beiden, die Befund 234 namentlich nennt: *"vermessen die Umgebung des
#: vorhandenen Kandidaten und schreiben dabei den Zaehler fort."* Ob das
#: zaehlen **soll**, ist weiter offen; dass man es sieht, ist entschieden.
BUCHFUEHRER = ("korb", "landschaft", "machbarkeit", "verbund")


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

    def test_jeder_erfasste_versuch_nennt_seine_herkunft(self) -> None:
        """**Hier stand eine Verbotsliste** (Befund 282).

        Sie hielt fest, dass kein Eintrag aus einem Sweep stammt - und das
        war nie eine Anforderung, sondern die Beschreibung eines Mangels:
        ``landschaft`` und ``machbarkeit`` buchten stumm in den Grundstock,
        also *konnte* kein Eintrag von ihnen kommen. Seit 282 koennen sie es,
        und die alte Zusicherung waere jetzt ein Verbot dessen, was gerade
        repariert wurde.

        Gehalten wird, was gemeint war: Wer einzeln verzeichnet ist, sagt
        auch, woher er kommt. Dass heute keine Sweep-Eintraege dastehen,
        heisst nicht, dass Sweeps nichts beigetragen haben - Befund 104
        zaehlt 21 davon, und Befund 281 hat fuenf weitere in den Grundstock
        gebucht, bevor diese Aenderung da war.
        """
        eintraege = self._zaehler()["versuche"]

        assert eintraege
        for v in eintraege:
            assert v["herkunft"], f"{v['kennung']}: Eintrag ohne Herkunft"


#: Der Stand, als diese Wache gebaut wurde. Sie haelt die **Richtung** fest,
#: nicht die Zahl: Der Zaehler darf steigen, wenn gemessen wurde - er darf nie
#: fallen.
STAND_BEI_BAU = 198


def test_hier_wird_nichts_umgebucht() -> None:
    """**Die Zusicherung, die dieser Befund gibt.**

    Wie Versuche gebucht werden, steuert die Haerte des einzigen noch offenen
    Gates. Ein Eingriff, der den Zaehler senkte, wuerde die Latte senken - und
    zwar ohne Messung.

    **Hier stand ``== 198``** (Befund 281). Das war die Zahl des Tages und
    nicht die Anforderung: Als 'cli machbarkeit --spot' fuenf Stellungen mass
    und ordnungsgemaess buchte, schlug die Wache an, obwohl genau der
    vorgesehene Weg gegangen worden war. Gehalten wird deshalb, was gemeint
    war - der Zaehler faellt nicht.
    """
    d = json.loads(Path("state/trials.json").read_text())

    assert d["trials"] >= STAND_BEI_BAU, "der Zaehler faellt nicht"
    assert d["grundstock"] + len(d["versuche"]) == d["trials"], (
        "nichts wird zwischen Grundstock und Einzelnachweisen umgebucht"
    )


class TestSweepsTragenJetztHerkunft:
    """**Befund 282.** Die Luecke aus 234, geschlossen fuer alles Neue.

    Befund 234 haelt fest: *"Was sie melden, bucht 'save_trials' in den
    Grundstock - 187 der 198 Versuche stehen dort ohne Herkunft, als waeren
    sie Vorgeschichte."* Die Begruendung, es nicht umzubauen, war: *"die
    fuenf Befehle laufen hier nicht (sie brauchen Kerzen)."*

    **Das stimmt nicht mehr.** In Befund 281 lief 'cli machbarkeit --spot'
    genau hier und buchte fuenf Stellungen in den Grundstock - 187 auf 192.
    Die Frage, ob ein Sweep als Versuch zaehlen sollte, bleibt offen; von
    hier an ist sie wenigstens **beantwortbar**, weil man die Sweeps sieht.
    """

    @staticmethod
    def _quelle(name: str) -> str:
        import ast

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == name
        )
        return ast.unparse(knoten)

    def test_machbarkeit_schreibt_einzelnachweise(self) -> None:
        quelle = self._quelle("machbarkeit")

        assert "_verzeichne(" in quelle
        assert "Versuch.jetzt(" in quelle
        assert "herkunft=" in quelle
        assert "save_trials(" not in quelle, (
            "die Summe allein laesst die Stellungen im Grundstock verschwinden"
        )

    def test_landschaft_auch(self) -> None:
        quelle = self._quelle("landschaft")

        assert "_verzeichne(" in quelle
        assert "Versuch.jetzt(" in quelle
        assert "save_trials(" not in quelle

    def test_die_herkunft_nennt_den_befehl(self) -> None:
        for name in ("machbarkeit", "landschaft"):
            assert f"cli {name}" in self._quelle(name)

    def test_anhaengen_hebt_die_summe_und_laesst_den_grundstock(
        self, tmp_path: Path
    ) -> None:
        """Der Kern der Buchung: Einzelnachweise **erhoehen** den Zaehler um
        ihre Zahl und ruehren den Grundstock nicht an. Waere es anders, waere
        das Eintragen eine Umbuchung - und eine Umbuchung nach unten machte
        die Mehrfachtest-Korrektur milder.
        """
        from research.versuche import Versuch, Verzeichnis, anhaengen, speichern

        ziel = tmp_path / "trials.json"
        speichern(ziel, Verzeichnis(grundstock=187, eintraege=[]))

        nachher = anhaengen(
            ziel,
            [
                Versuch.jetzt(
                    "Vola-Ziel 21 %",
                    herkunft="cli machbarkeit --regler vola (Spot)",
                    trades=158,
                    sharpe_je_trade=0.2708,
                )
            ],
        )

        assert nachher.anzahl == 188
        assert nachher.grundstock == 187
        assert nachher.eintraege[-1].herkunft.startswith("cli machbarkeit")

    def test_nicht_erhoben_ist_nicht_kein_vorteil(self, tmp_path: Path) -> None:
        """``landschaft`` fuehrt keine Guete je Trade. ``None`` heisst dort
        "nicht erhoben" - eine 0,0 waere die Behauptung, es gaebe keinen
        Vorteil, und sie ginge in die Streuungsschaetzung ein."""
        from research.versuche import Versuch, Verzeichnis, anhaengen, speichern

        ziel = tmp_path / "trials.json"
        speichern(ziel, Verzeichnis(grundstock=10, eintraege=[]))

        nachher = anhaengen(
            ziel, [Versuch.jetzt("Landschaft Faktor 1,2", trades=140)]
        )

        assert nachher.eintraege[-1].sharpe_je_trade is None
        assert nachher.sharpes() == []
