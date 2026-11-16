"""Der Auftrag stand auf einer Datei, die es nicht gibt - Befund 497.

Was gemessen wurde
------------------
``analyst.build_prompt`` fuehrt einen Abschnitt "Was bereits versucht wurde",
und der Modulkopf nennt seinen Zweck: *"Enthaelt bewusst die Fehlschlaege mit
Zahlen, nicht nur die Namen der gescheiterten Kandidaten."* Gefuellt wird er
aus ``state/journal.json``, und die Datei **existiert nicht**. Der Abschnitt
sagte das selbst - und zog daraus den falschen Schluss:

    Das Research-Journal ist leer, aber **203 Versuche sind gezaehlt.** ...
    die Nachweise liegen in einem anderen Verzeichnis und stehen nicht
    vollstaendig hier.

Die Nachweise liegen in ``state/trials.json`` - derselben Datei, aus der der
Zaehler seine 203 nimmt:

    Zaehler       203
    mit Eintrag    11   (Kennung, Trades, Sharpe je Trade, Herkunft)
    Grundstock    192

Darunter vier negative Sharpes je Trade zwischen -0,12 und -0,19, auf Regeln
mit plausiblen Namen ("Ueberverkauft ohne Trendfilter", "Abgriff des
Vortagestiefs"). Genau solche Zeilen sind der Grund, warum der Abschnitt
existiert - und der Analyst hat sie nie gesehen. Jeder Vorschlag, der eine
davon wiederholt, kostet einen Versuch, und der Zaehler faellt nicht.

Die Grenze des Befundes
-----------------------
Der Abschnitt ist eine **Auskunft, keine Sperre**. Der Doppelgaengerfilter in
``parse_proposals`` vergleicht ``genome_id`` - einen Inhaltshash wie
``66e04da1281c8cd1`` -, das Verzeichnis fuehrt Kennungen wie "Enge vor
Bewegung". Einen Namen als Kennung im Sinne des Filters zu nehmen waere
geraten, und geraten wird hier nichts. Der Filter bleibt unberuehrt, und das
steht als Zusicherung unten.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.versuche import Versuch, Verzeichnis
from research.versuchsschau import HOECHSTENS, als_auftrag

WURZEL = Path(__file__).resolve().parents[1]


def _versuch(kennung: str, trades: int, sharpe: float | None, herkunft: str = "probe"):
    return Versuch(
        kennung=kennung,
        zeitpunkt="2026-01-01T00:00:00+00:00",
        trades=trades,
        sharpe_je_trade=sharpe,
        herkunft=herkunft,
    )


def _verzeichnis(eintraege: list[Versuch], grundstock: int = 192) -> Verzeichnis:
    return Verzeichnis(grundstock=grundstock, eintraege=tuple(eintraege))


class _Lage:
    """Nur so viel Lage, wie ``build_prompt`` braucht."""

    versuche = 203

    def als_auftrag(self) -> str:
        return ""


class TestDerAbschnittZeigtDieZahlen:
    def test_jede_regel_mit_trades_und_sharpe(self) -> None:
        text = als_auftrag(
            _verzeichnis(
                [
                    _versuch("Gute Regel", 150, 0.30),
                    _versuch("Schlechte Regel", 133, -0.1919),
                ]
            )
        )

        assert "Gute Regel" in text
        assert "150" in text
        assert "0.3000" in text
        assert "-0.1919" in text

    def test_nach_guete_sortiert(self) -> None:
        """Die beste oben, die schlechteste unten - damit die Raender
        zusammenstehen und nicht die Zeitreihenfolge."""
        text = als_auftrag(
            _verzeichnis(
                [
                    _versuch("mittel", 100, 0.10),
                    _versuch("beste", 100, 0.40),
                    _versuch("schlechteste", 100, -0.20),
                ]
            )
        )
        zeilen = [z for z in text.splitlines() if z.startswith("    ") and "0" in z]
        reihenfolge = [
            name
            for name in ("beste", "mittel", "schlechteste")
            if any(name in z for z in zeilen)
        ]

        assert reihenfolge == ["beste", "mittel", "schlechteste"], text

    def test_er_nennt_zaehler_und_grundstock(self) -> None:
        """**Die ehrliche Fassung des alten Satzes**: Nicht "liegen woanders",
        sondern 11 mit Zahlen und 192 ohne."""
        text = als_auftrag(
            _verzeichnis([_versuch("eine", 100, 0.2)], grundstock=192)
        )

        assert "193" in text, "Zaehler = Grundstock + Eintraege"
        assert "192" in text
        assert "**1**" in text

    def test_und_benennt_die_schlechteste_im_satz(self) -> None:
        """Eine Zahl in einer Tafel wird uebersehen; ein Satz nicht."""
        text = als_auftrag(
            _verzeichnis(
                [_versuch("Ueberverkauft ohne Trendfilter", 133, -0.1919)]
            )
        )

        assert "'Ueberverkauft ohne Trendfilter'" in text
        assert "erledigt" in text


class TestOhneZahlenBleibtErLeer:
    def test_ein_leeres_verzeichnis(self) -> None:
        """Ein Abschnitt mit Ueberschrift und ohne Zeilen sieht aus wie eine
        Auskunft und ist keine - dieselbe Haltung wie in ``auftragstakt``."""
        assert als_auftrag(_verzeichnis([])) == ""

    def test_und_eintraege_ohne_sharpe(self) -> None:
        """``None`` heisst "nicht erhoben" und nicht "kein Vorteil" - so eine
        Zeile gehoert nicht in eine Tafel, die nach Guete sortiert."""
        assert als_auftrag(_verzeichnis([_versuch("ohne Zahl", 100, None)])) == ""

    def test_aber_eine_mit_zahl_genuegt(self) -> None:
        """Gegenprobe: Sonst koennte die Regel darueber alles verschlucken."""
        text = als_auftrag(
            _verzeichnis([_versuch("ohne", 50, None), _versuch("mit", 60, 0.1)])
        )

        assert "mit" in text
        assert "ohne" not in text.split("Regel", 1)[-1].split("**")[0]


class TestBeiVielenZeigtErDieRaender:
    def test_die_mitte_faellt_heraus(self) -> None:
        viele = [_versuch(f"R{i:03d}", 100, i / 100) for i in range(HOECHSTENS + 10)]
        text = als_auftrag(_verzeichnis(viele))

        assert "R000" in text, "die schlechteste gehoert dazu"
        assert f"R{HOECHSTENS + 9:03d}" in text, "die beste auch"
        assert f"{len(viele)}" in text, "die Gesamtzahl wird genannt"

    def test_und_sagt_dass_er_kuerzt(self) -> None:
        viele = [_versuch(f"R{i:03d}", 100, i / 100) for i in range(HOECHSTENS + 10)]
        text = als_auftrag(_verzeichnis(viele))

        assert "schlechtesten von" in text

    def test_bei_wenigen_kuerzt_er_nicht(self) -> None:
        text = als_auftrag(_verzeichnis([_versuch("eine", 100, 0.2)]))

        assert "schlechtesten von" not in text


class TestDerAuftragTraegtIhn:
    def _prompt(self, **kw) -> str:
        from research.analyst import build_prompt
        from research.gates import GateThresholds

        return build_prompt(journal=[], thresholds=GateThresholds(), **kw)

    def test_mit_abschnitt_steht_er_darin(self) -> None:
        text = self._prompt(verbucht=als_auftrag(_verzeichnis([
            _versuch("Ueberverkauft ohne Trendfilter", 133, -0.1919)
        ])))

        assert "Was bereits gemessen wurde" in text
        assert "-0.1919" in text

    def test_ohne_abschnitt_bleibt_der_auftrag_der_alte(self) -> None:
        """Kein leerer Abschnitt und keine gesetzte Zahl: Wer das Verzeichnis
        nicht hat, bekommt den Satz von vorher."""

        text = self._prompt(lage=_Lage())

        assert "Was bereits gemessen wurde" not in text
        assert "Research-Journal ist leer" in text

    def test_der_falsche_satz_steht_nicht_mehr_darin(self) -> None:
        """"Die Nachweise liegen in einem anderen Verzeichnis" war in der
        Sache falsch - sie liegen in derselben Datei wie der Zaehler."""

        assert "in einem anderen Verzeichnis" not in self._prompt(lage=_Lage())


class TestDieBefehleReichenIhnDurch:
    """**Geprueft wird der Aufruf, nicht sein Wortlaut** (Befund 493/496):
    Drei Stellen bauen den Auftrag, und alle drei muessen den Abschnitt
    mitgeben - sonst sieht der Analyst die Zahlen an einer Stelle und an der
    anderen nicht."""

    def _aufrufe(self, namen: tuple[str, ...]) -> list[ast.Call]:
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        return [
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id in namen
        ]

    def test_jeder_auftragsbau_gibt_ihn_mit(self) -> None:
        aufrufe = self._aufrufe(("propose", "build_prompt"))
        ohne = [
            ast.unparse(k)[:60]
            for k in aufrufe
            if not any(w.arg == "verbucht" for w in k.keywords)
        ]

        assert len(aufrufe) == 3, len(aufrufe)
        assert ohne == [], (
            "baut den Auftrag ohne die gemessenen Versuche - dann sagt er nur, "
            f"wie viele es waren (Befund 497): {ohne}"
        )

    def test_der_helfer_liest_das_verzeichnis_und_nicht_die_datei_selbst(
        self,
    ) -> None:
        """Eine Wahrheit (Befund 234): ``versuche.laden`` kennt beide
        Dateiformate und wirft bei einem unlesbaren Verzeichnis - ein
        eigenes ``json.loads`` hier wuerde das umgehen."""
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        fn = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "_verbuchte_versuche"
        )
        # **Ohne den Docstring**: Der nennt 'trials.json' selbst, und die
        # Zusicherung waere an ihrem eigenen Text gescheitert - dieselbe
        # Selbstwiderlegung wie bei GELESEN in Befund 295.
        ohne_text = [
            k
            for k in fn.body
            if not (isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant))
        ]
        quelle = "\n".join(ast.unparse(k) for k in ohne_text)

        assert "laden(" in quelle
        assert "json.loads" not in quelle


class TestErIstKeineSperrliste:
    """Die Grenze des Befundes, als Zusicherung: Der Filter vergleicht
    Inhaltshashes, und ein Name ist keiner."""

    def test_eine_kennung_sperrt_keinen_vorschlag(self) -> None:
        from research.analyst import parse_proposals
        from research.seeds import load_seeds

        genom = load_seeds(5)[0]
        antwort = f"[{genom.model_dump_json()}]"

        # Der Name steht im "Verzeichnis", die Kennung ist der Hash.
        vorschlaege = parse_proposals(antwort, already_tried={genom.name})

        assert [p.accepted for p in vorschlaege] == [True], (
            "ein Name darf den Filter nicht ausloesen - er vergleicht "
            "genome_id"
        )

    def test_aber_die_kennung_sperrt_ihn(self) -> None:
        """Gegenprobe: Sonst pruefte die Regel darueber nichts."""
        from research.analyst import parse_proposals
        from research.seeds import load_seeds

        genom = load_seeds(5)[0]
        antwort = f"[{genom.model_dump_json()}]"

        vorschlaege = parse_proposals(antwort, already_tried={genom.genome_id})

        assert [p.accepted for p in vorschlaege] == [False]

    def test_und_der_abschnitt_sagt_das(self) -> None:
        """Wer die Tafel fuer eine Sperrliste haelt, wiederholt etwas und
        bezahlt es mit einem Versuch - das gehoert dazugesagt."""
        text = als_auftrag(_verzeichnis([_versuch("eine", 100, 0.2)]))

        assert "keine Sperrliste" in text


@pytest.mark.daten
class TestAmEchtenVerzeichnis:
    def test_die_elf_gemessenen_stehen_darin(self) -> None:
        """Rauchtest am echten Stand: 203 gezaehlt, 11 mit Zahlen."""
        from research.versuche import laden

        verzeichnis = laden(WURZEL / "state" / "trials.json")
        # **Leerheit, kein Zahlenvergleich** (Befund 470/497): 'belegt == 0'
        # waere die verbotene Bauart - ein Uebersprung, der an einer
        # eingetragenen Zahl haengt. Gemeint ist "nichts da zum Zeigen", und
        # genau das steht jetzt da.
        if not verzeichnis.eintraege:
            pytest.skip(
                "kein Versuchsverzeichnis in diesem Container - "
                "'state/trials.json' liegt nicht im Repository"
            )
        text = als_auftrag(verzeichnis)

        assert str(verzeichnis.anzahl) in text
        assert str(verzeichnis.belegt) in text
        for eintrag in verzeichnis.eintraege:
            if eintrag.sharpe_je_trade is not None:
                assert eintrag.kennung in text, eintrag.kennung
