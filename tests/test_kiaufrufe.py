"""Die KI wurde einmal zu oft gefragt - Befund 358.

``cli wettbewerb --ki`` fragt die Research-KI **nach** jeder Runde, damit sie im
Journal sieht, woran die letzten Kandidaten gescheitert sind. Der Vorschlag
landet in ``aktuell`` und wird in der naechsten Runde gemessen.

Nach der **letzten** Runde gibt es keine naechste. Gemessen mit ``--runden 1``
und einem Doppel an der Stelle der KI:

    KI-Aufrufe   2
    benutzt      1

Der zweite Vorschlag wird geholt, in ``aktuell`` gelegt - und dann endet die
Schleife. Ein Modellaufruf kostet echtes Geld aus dem Forschungsbudget, das
``budget.json`` fuehrt und begrenzt; dieser war jedes Mal umsonst.

Dasselbe gilt am Rand des Suchbudgets: Bricht die Schleife oben ab, weil die
Abmachung aus dem Plan aufgebraucht ist, war der Vorschlag von unten ebenso
vergeblich.

Wie es gefunden wurde
---------------------
Durch **Fahren**, nicht durch Lesen - wie Befund 357 einen Tag vorher. Der
Pfad ``--ki`` ist der einzige unter den Zeilen fuer den Nutzer, der eine
fremde Leitung braucht, und darum war er nie durchgelaufen.

Der erste Anlauf hat dabei nichts gefunden, weil das Doppel eine
Generation-5-Regel nur **umbenannt** hat: dieselbe ``genome_id``, also ein
Doppelgaenger, und die Abwehr aus Befund 258 hat ihn zu Recht verworfen. Die
Kennung ist der Hash ueber die Regeln, nicht ueber den Namen - erst eine
verschobene Periode macht einen neuen Kandidaten.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli import app
from research.leaderboard import Leaderboard
from research.seeds import GENERATIONS

#: Die Maerkte des Zulassungskorbs als Forschungskerzen.
MAERKTE = "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP"


def _neuer_kandidat():
    """Eine bekannte Regel mit verschobener Periode - also wirklich neu."""
    eintrag = GENERATIONS[5][0]
    genome = eintrag() if callable(eintrag) else eintrag
    daten = genome.model_dump()
    for seite in ("entry_long", "exit_long"):
        for bedingung in daten.get(seite) or ():
            for flanke in ("left", "right"):
                params = (bedingung.get(flanke) or {}).get("params") or {}
                if "period" in params:
                    params["period"] = int(params["period"]) + 13
    daten["name"] = "KI-Vorschlag Attrappe"
    neu = type(genome).model_validate(daten)
    assert neu.genome_id != genome.genome_id, "nur umbenannt ist kein Vorschlag"
    return neu


class Zaehlwerk:
    """Ein Doppel der KI, das mitzaehlt, wie oft es gefragt wurde."""

    def __init__(self) -> None:
        self.aufrufe = 0

    def propose(self, client, **_egal):
        self.aufrufe += 1
        kandidat = _neuer_kandidat()

        class Ergebnis:
            proposals: tuple = ()
            genomes: tuple = (kandidat,)

            def summary(self) -> str:
                return "Attrappe: 1 Vorschlag, 0 abgelehnt"

        return Ergebnis()


#: Wo die Berichte des Projekts liegen - relativ zum Arbeitsverzeichnis.
BERICHTE = Path("reports") / "zulassung"


def _berichte(wurzel: Path) -> int:
    ordner = wurzel / BERICHTE
    return len(list(ordner.glob("*.json"))) if ordner.exists() else 0


@dataclass
class Lauf:
    """Was ein Wettbewerbslauf hinterlassen hat."""

    ausgabe: str
    aufrufe: int
    zustand: Path
    vorher: int
    nachher: int
    berichte_vorher: int
    berichte_nachher: int
    eigene_berichte: int
    """Berichte im Wegwerf-Verzeichnis - die sollen entstehen."""


def _fahre(runden: int, tmp_path: Path) -> Lauf:
    """Einen Wettbewerb gegen das Doppel fahren, in einer Wegwerf-Ablage.

    Der Versuchszaehler wird ueber ``PATHS__STATE`` umgelenkt - derselbe Weg,
    den Befund 330 benutzt hat. Der echte Stand bleibt unberuehrt.

    **Und der Lauf arbeitet in einem anderen Verzeichnis** (Befund 358, zweiter
    Teil). ``write_report`` nimmt als Wurzel das **Arbeitsverzeichnis**, nicht
    eine Einstellung, und ``publish`` committet den Bericht danach und pusht
    ihn. Ohne ``TRADING_TROCKENLAUF`` - das dieser Test nicht setzen kann, weil
    er Bestenliste und Zaehler geschrieben sehen muss - landet jeder Lauf als
    Commit in der Projekthistorie. Genau das ist mir passiert: achtzehn
    Commits, zurueckgenommen in ``0989511``.

    Aus einem Wegwerf-Verzeichnis heraus gibt es kein ``.git``, und ``publish``
    meldet ``NO_REPO``. Der Kerzenspeicher braucht dafuer einen absoluten Pfad.
    """
    import research.analyst as analyst
    from core.config import get_settings

    wurzel = Path.cwd()
    zustand = tmp_path / "state"
    zustand.mkdir(parents=True, exist_ok=True)
    shutil.copy(wurzel / "state" / "trials.json", zustand / "trials.json")
    vorher = json.loads((zustand / "trials.json").read_text())["trials"]

    berichte_vorher = _berichte(wurzel)
    zaehlwerk = Zaehlwerk()
    with pytest.MonkeyPatch.context() as flicken:
        flicken.chdir(tmp_path)
        flicken.setenv("PATHS__STATE", str(zustand))
        flicken.setenv("PATHS__DATA_STORE", str(wurzel / "data_store"))
        flicken.setenv("PATHS__STRATEGIES", str(tmp_path / "strategies"))
        flicken.setenv("LLM__ANTHROPIC_API_KEY", "sk-attrappe")
        flicken.setattr(analyst, "AnthropicClient", lambda *a, **k: object())
        flicken.setattr(analyst, "propose", zaehlwerk.propose)
        get_settings.cache_clear()
        try:
            ergebnis = CliRunner().invoke(
                app,
                [
                    "wettbewerb", "-m", MAERKTE, "-i", "D", "--generation", "9",
                    "--varianten", "1", "--ki", "--runden", str(runden),
                ],
            )
        finally:
            get_settings.cache_clear()

    assert ergebnis.exit_code == 0, ergebnis.output
    return Lauf(
        ausgabe=ergebnis.output,
        aufrufe=zaehlwerk.aufrufe,
        zustand=zustand,
        vorher=vorher,
        nachher=json.loads((zustand / "trials.json").read_text())["trials"],
        berichte_vorher=berichte_vorher,
        berichte_nachher=_berichte(wurzel),
        eigene_berichte=_berichte(tmp_path),
    )


#: **Je Aufstellung ein Lauf und nicht je Zusicherung.** Ein Wettbewerb dauert
#: Minuten; fuenf Tests, die ihn je einmal fahren, kosten das Fuenffache fuer
#: dieselbe Messung.
@pytest.fixture(scope="module")
def eine_runde(tmp_path_factory) -> Lauf:
    return _fahre(1, tmp_path_factory.mktemp("eine"))


@pytest.fixture(scope="module")
def zwei_runden(tmp_path_factory) -> Lauf:
    return _fahre(2, tmp_path_factory.mktemp("zwei"))


@pytest.mark.langsam
class TestDieKiWirdNurGefragtWennEsNochWeitergeht:
    def test_eine_runde_ist_ein_aufruf(self, eine_runde: Lauf) -> None:
        """**Der Fund.** Vorher waren es zwei, und der zweite war umsonst."""
        assert eine_runde.aufrufe == 1

    def test_der_vorschlag_laeuft_wirklich_mit(self, eine_runde: Lauf) -> None:
        """Die Eigenschaft, die dabei nicht verloren gehen darf: Der eine
        Aufruf, der bleibt, wird auch benutzt."""
        namen = {
            e.name
            for e in Leaderboard(eine_runde.zustand / "leaderboard.json").ranked()
        }

        assert "von der KI" in eine_runde.ausgabe
        assert "KI-Vorschlag Attrappe" in namen

    def test_und_seine_herkunft_steht_in_der_liste(self, eine_runde: Lauf) -> None:
        """Ohne Herkunft waere er in der Liste ein Katalogeintrag - und die
        Frage, ob die KI etwas beitraegt, nicht mehr beantwortbar."""
        eintraege = Leaderboard(eine_runde.zustand / "leaderboard.json").ranked()

        ki = [e for e in eintraege if e.name == "KI-Vorschlag Attrappe"]
        assert ki, "der Vorschlag steht nicht in der Liste"
        assert "KI" in ki[0].herkunft

    def test_zwei_runden_sind_zwei_aufrufe(self, zwei_runden: Lauf) -> None:
        """Die Gegenprobe: Gekuerzt wird der **letzte** Aufruf, nicht der
        Lernmechanismus. Zwei Runden brauchen zwei Vorschlaege - einen fuer
        Runde zwei, und der nach Runde zwei entfaellt."""
        assert zwei_runden.aufrufe == 2

    def test_der_zaehler_zaehlt_den_vorschlag_mit(self, eine_runde: Lauf) -> None:
        """Ein Vorschlag ist ein Versuch wie jeder andere - sieben Regeln aus
        dem Katalog und einer von der KI sind acht."""
        assert eine_runde.nachher - eine_runde.vorher == 8


@pytest.mark.langsam
class TestDerLaufSchreibtNichtInsProjekt:
    """**Der zweite Teil von Befund 358, und er war mein Fehler.**

    ``write_report`` nimmt als Wurzel das **Arbeitsverzeichnis**, nicht eine
    Einstellung, und ``publish`` committet den Bericht danach und pusht ihn.
    Der Docstring von ``core.report.publish`` nennt das Befund 117 und sagt:
    *"Das ist die sichtbarste Schreibstelle von allen [...] und ein Rauchtest
    landet damit in der Projekthistorie, wo er wie ein Lauf aussieht."*

    Beim Pruefen des KI-Pfades ist mir genau das passiert - achtzehn Commits,
    zurueckgenommen in ``0989511``. ``TRADING_TROCKENLAUF`` waere die Wache
    gewesen; dieser Test kann sie nicht setzen, weil er Bestenliste und Zaehler
    geschrieben sehen muss. Also arbeitet er in einem anderen Verzeichnis.
    """

    def test_kein_bericht_landet_im_projekt(self, eine_runde: Lauf) -> None:
        assert eine_runde.berichte_nachher == eine_runde.berichte_vorher

    def test_der_bericht_entsteht_aber_wirklich(self, eine_runde: Lauf) -> None:
        """Die Gegenprobe: Nicht der Bericht ist abgeschaltet, nur sein Ort.
        Ein Test, der das Schreiben verhindert, prueft den Lauf nicht mehr."""
        assert eine_runde.eigene_berichte >= 1


class TestDerQuelltextFragtVorausschauend:
    """Ohne Lauf: Die Wache dagegen, dass der Aufruf wieder unbedingt wird."""

    @staticmethod
    def _quelle() -> str:
        import ast

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "wettbewerb":
                return ast.unparse(knoten)
        raise AssertionError("'wettbewerb' steht nicht mehr in cli.py")

    def test_der_aufruf_am_schleifenende_ist_bedingt(self) -> None:
        quelle = self._quelle()

        assert "_vorschlaege() if weitere_runde else []" in quelle

    def test_und_die_bedingung_kennt_beide_abbrueche(self) -> None:
        """Rundenzahl **und** Suchbudget: Beide beenden die Schleife, und
        hinter beiden ist ein Vorschlag vergeblich."""
        quelle = self._quelle()
        stelle = quelle.index("weitere_runde = ")
        bedingung = quelle[stelle : stelle + 220]

        assert "runde < runden" in bedingung
        assert "_noch_zu_holen" in bedingung

    def test_auch_der_aufruf_vor_der_schleife_ist_bedingt(self) -> None:
        """**Das andere Ende** (Befund 358). Steht der Zaehler schon ueber dem
        Suchbudget, bricht die Schleife sofort ab - der Vorschlag davor waere
        bezahlt und nie gemessen.
        """
        quelle = self._quelle()
        stelle = quelle.index("ki_ids: set[str] = set()")

        assert "if ki and _noch_zu_holen(" in quelle[stelle : stelle + 200]

    def test_und_das_budget_entscheidet_wirklich(self) -> None:
        """Nicht nur im Quelltext: Der Helfer sagt bei aufgebrauchtem Budget
        nein und bei '--ueber-das-budget' ja."""
        from cli import _noch_zu_holen
        from research.stand import BUDGET

        assert _noch_zu_holen(BUDGET.grenze - 1, ueber_budget=False)
        assert not _noch_zu_holen(BUDGET.grenze + 50, ueber_budget=False)
        assert _noch_zu_holen(BUDGET.grenze + 50, ueber_budget=True)

    def test_die_meldung_behauptet_keinen_vorschlag_der_ausblieb(self) -> None:
        """Wer nicht gefragt wurde, hat auch nichts vorgeschlagen."""
        quelle = self._quelle()

        assert "if ki and weitere_runde" in quelle
