"""Wer eine Gate-Zahl traegt, muss sagen koennen, ob sie geurteilt hat.

Befund 332.

Befund 321 hat gefunden, dass ``GateResult.passed`` wahr ist, sobald der Status
nicht ``FAIL`` lautet - ein **uebersprungenes** Gate zaehlt damit als bestanden.
321 hat das fuer ``teststaerke.Stufe`` behoben, 322 fuer
``nachpruefung.Ergebnis``: beide tragen seither ``uebersprungen`` und rechnen
``bestanden_echt`` / ``geurteilt`` daraus.

Dieser Lauf hat nachgesehen, wo dieselbe Zahl sonst noch steht.

**Neun Anzeigestellen in ``cli.py``** geben ein rohes ``bestanden/gesamt``
aus, und **einundzwanzig Datentypen** in ``research/`` tragen ein Feld
``bestanden``. Drei wissen von Uebersprungenem, eines behandelt es eine Schicht
vorher, zwei halten verzeichnete Staende - bei fuenfzehn ist die Frage offen.

Der erste Treffer war handfest: ``cli nachpruefung`` zeigte in seiner
Fortschrittszeile ``5/9`` fuer eine Regel ohne einen einzigen Trade und sieben
Zeilen weiter in der Tabelle ``2/6`` - dieselbe Regel, zwei Nenner. Befund 322
hatte Tabelle, Rangfolge und Urteil verdrahtet und die Zeile stehen gelassen.
Die erste Zahl liest man zuerst. Behoben und auf echten Daten nachgemessen.

**Was dieser Befund nicht behauptet.** Dass die uebrigen Anzeigen heute falsche
Zahlen zeigen, ist **nicht** gemessen. Ein Uebersprungenes entsteht nur unter
Bedingungen - zu wenige Trades, keine variierbaren Perioden, ``run_expensive``
aus -, und ob die in einem gegebenen Lauf auftreten, haengt an seinen Eingaben.
``cli decke`` etwa fuehrt seine Leiter mit derselben Strategie und aehnlicher
Trade-Zahl; dort ist kein Uebersprungenes aufgetreten.

Deshalb ist dies ein **Verzeichnis** und keine Reparatur: Es haelt fest, welcher
Typ die Frage beantworten kann und welcher nicht, und es zwingt jeden neuen dazu,
sich einzuordnen. Dieselbe Bauart wie ``WIRKT_NACH_AUSSEN`` in
``test_rauchtest.py`` - unbekannt ist ein Fehler, nicht stillschweigend in
Ordnung.
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil

import pytest

import research

#: Typen, die ``uebersprungen`` tragen und ``bestanden_echt`` daraus rechnen.
MIT_SKIPINFO: frozenset[str] = frozenset({
    # Befund 337: nachgetragen, weil diese Leiter die Strategie absichtlich
    # verschlechtert - dort waere ein Aussetzer am ehesten zu erwarten.
    # Gemessen setzt auf keiner der sechs Sprossen ein Gate aus.
    "research.finanzierung.Stufe",
    "research.machbarkeit.Stand",
    "research.nachpruefung.Ergebnis",
    "research.teststaerke.Stufe",
})

#: Typen, die **verzeichnete** Staende halten und keinen Gate-Lauf ausfuehren.
#:
#: Ihre Zahlen sind von Hand eingetragene Messwerte mit Fundstelle, kein
#: Ergebnis einer Auswertung - dort gibt es nichts zu ueberspringen.
VERZEICHNET: dict[str, str] = {
    "research.referenz.Referenzpunkt": "feste Referenzstaende mit Befundnummer",
    "research.historie.Historienstufe": "gemessene Fenster aus Befund 133",
}

#: Typen, deren **Modul** das Aussetzen behandelt, bevor die Zahl entsteht.
#:
#: **Die Berichtigung an Befund 332** (Befund 333). Das Verzeichnis hat nach dem
#: Feldnamen ``uebersprungen`` auf der Datenklasse eingeteilt - ein Stellvertreter
#: fuer die Faehigkeit, nicht die Faehigkeit. ``gatemuster`` behandelt das
#: Aussetzen in ``lade``, also **eine Schicht vorher**:
#:
#:     gemessen = {name: bool(stand.get("bestanden"))
#:                 for name, stand in gates.items()
#:                 if isinstance(stand, dict) and not stand.get("uebersprungen")}
#:
#: Ein ausgesetztes Gate fehlt damit am Messpunkt, ``Gatemuster.namen`` liefert
#: nur die auf **allen** Punkten beurteilten, und das Wort "beurteilt" im
#: Bericht stimmt. Die Datenklasse braucht das Feld nicht - und stand trotzdem
#: unter den offenen Faellen.
#:
#: Genau die Falle, die Befund 332 im eigenen Laborbuch beschrieben hat: Ein
#: Test, der aus derselben Annahme stammt wie die Behebung, kann die
#: uebersehene Stelle nicht finden.
VORGELAGERT: dict[str, str] = {
    "research.gatemuster.Gatelage": "lade() laesst uebersprungene Gates weg",
}

#: Typen, bei denen die Frage **offen** ist - aufgelistet, nicht geprueft.
#:
#: **Bewusst als Liste und nicht als "alles Uebrige".** Sonst waere das
#: Verzeichnis per Konstruktion vollstaendig, dieser Test tautologisch, und ein
#: neuer Typ faende sich stillschweigend auf der harmlosen Seite wieder.
#:
#: Was hier steht, heisst: Der Typ traegt eine Gate-Zahl, kann aber nicht sagen,
#: ob jedes Gate geurteilt hat. Ob ihn das heute trifft, ist nicht gemessen.
#: **Gemessen (333): heute setzt bei diesem Kandidaten kein Gate aus.** Der
#: Spitzenkandidat liefert am Spot-Punkt 158 Trades, und alle elf Gates faellen
#: ein Urteil - null Aussetzer. Die rohen Paare dieser Typen sind damit
#: **richtig**, solange sie denselben Kandidaten auf der ganzen Reihe fahren.
#:
#: Offen bleibt eine **Bedingung**, nicht ein Verdacht: Ein Aussetzen braucht
#: weniger als 30 Trades (20 fuer Monte-Carlo). Eine Leiter, die die Trade-Zahl
#: darunter drueckt, bekaeme hier eine geschenkte Zahl - und keiner dieser Typen
#: koennte es sagen. 'cli koernung' gemessen: 152 bis 158 Trades ueber vierzehn
#: Sprossen, also weit darueber.
OFFEN: frozenset[str] = frozenset({
    "research.admission.Zulassungsbedingungen",
    "research.aufloesung.Messung",
    "research.aufstellung.Marktsatz",
    "research.betriebspunkt.Betriebspunkt",
    "research.decke.Fenster",
    "research.decke.Stufe",
    "research.instrument.Gebuehrenstufe",
    "research.instrument.Lauf",
    "research.koernung.Gatewert",
    "research.ratenbild.Ratenprobe",
    "research.regler.Stellung",
    "research.sperrprobe.Ergebnis",
    "research.stand.Lage",
    "research.ziehung.Ziehung",
})


def _traeger() -> dict[str, frozenset[str]]:
    """Jeder Datentyp in ``research/`` mit einem Feld ``bestanden``."""
    gefunden: dict[str, frozenset[str]] = {}
    for modul in pkgutil.iter_modules(research.__path__):
        vollname = f"research.{modul.name}"
        try:
            geladen = importlib.import_module(vollname)
        except Exception:
            # Ein unimportierbares Modul ist nicht die Frage dieses Tests -
            # dafuer gibt es die Suite.
            continue
        for name in dir(geladen):
            obj = getattr(geladen, name)
            if not (dataclasses.is_dataclass(obj) and isinstance(obj, type)):
                continue
            if getattr(obj, "__module__", "") != vollname:
                continue
            felder = frozenset(f.name for f in dataclasses.fields(obj))
            if "bestanden" in felder:
                gefunden[f"{vollname}.{name}"] = felder
    return gefunden


class TestDasVerzeichnisIstVollstaendig:
    def test_jeder_traeger_ist_eingeordnet(self) -> None:
        """**Die Wache.** Ein neuer Typ mit einer Gate-Zahl zwingt zur Frage.

        Sie faellt in der sicheren Richtung aus: Unbekannt ist ein Fehler, nicht
        stillschweigend in Ordnung.
        """
        bekannt = MIT_SKIPINFO | set(VERZEICHNET) | set(VORGELAGERT) | OFFEN

        unbekannt = sorted(set(_traeger()) - bekannt)

        assert unbekannt == [], (
            f"nicht eingeordnet: {unbekannt} - kann der Typ sagen, ob jedes "
            f"Gate geurteilt hat? Dann MIT_SKIPINFO. Haelt er einen "
            f"verzeichneten Stand? Dann VERZEICHNET. Sonst OFFEN."
        )

    def test_das_verzeichnis_nennt_keine_typen_die_es_nicht_gibt(self) -> None:
        bekannt = MIT_SKIPINFO | set(VERZEICHNET) | set(VORGELAGERT) | OFFEN

        verwaist = sorted(bekannt - set(_traeger()))

        assert verwaist == []

    def test_keine_doppelte_einordnung(self) -> None:
        felder = (MIT_SKIPINFO, frozenset(VERZEICHNET), frozenset(VORGELAGERT), OFFEN)
        for i, a in enumerate(felder):
            for b in felder[i + 1 :]:
                assert not a & b


class TestDieEinordnungStimmtMitDemQuelltext:
    def test_wer_in_mit_skipinfo_steht_traegt_das_feld(self) -> None:
        traeger = _traeger()

        for name in MIT_SKIPINFO:
            assert "uebersprungen" in traeger[name], name

    def test_wer_in_offen_steht_traegt_es_nicht(self) -> None:
        """Sonst waere er behoben und nur nicht umgetragen."""
        traeger = _traeger()

        for name in OFFEN:
            assert "uebersprungen" not in traeger[name], (
                f"{name} traegt 'uebersprungen' - gehoert nach MIT_SKIPINFO"
            )

    def test_die_verzeichneten_halten_feste_werte(self) -> None:
        """Beide werden mit Literalen gebaut - kein Gate-Lauf, kein
        Uebersprungenes."""
        from research.historie import GEMESSEN
        from research.referenz import SPOTPUNKT

        assert SPOTPUNKT.bestanden == 9
        assert SPOTPUNKT.gesamt == 11
        assert GEMESSEN.referenz.bestanden == 9


class TestDieFortschrittszeileDerNachpruefung:
    """**Der eine Fall, der gemessen ist.**"""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "nachpruefung"
        )

    def test_sie_zeigt_die_ehrliche_zahl(self) -> None:
        quelle = self._quelle()

        assert "ergebnis.bestanden_echt" in quelle
        assert "ergebnis.geurteilt" in quelle

    def test_und_nennt_die_uebersprungenen(self) -> None:
        assert "nicht jedes Gate geurteilt" in self._quelle()

    def test_das_rohe_paar_steht_nicht_mehr_in_der_zeile(self) -> None:
        """Es bleibt im Bericht und in der Rechnung - nur nicht als Anzeige."""
        quelle = self._quelle()

        assert "{ergebnis.bestanden:" not in quelle
        assert "bestanden=sum(" in quelle, "die Rechnung bleibt"


def test_die_zahl_der_offenen_faelle_steht_fest() -> None:
    """Damit ein spaeterer Lauf sich daran messen kann - und damit das
    Verzeichnis nicht unbemerkt waechst."""
    assert len(OFFEN) == 14
    assert len(MIT_SKIPINFO) == 4
    assert len(VORGELAGERT) == 1
    assert len(_traeger()) == 21


# **Die Messung, die Befund 332 offen gelassen hat** (Befund 333).
#
# 332 hat sechzehn Typen aufgelistet, die eine Gate-Zahl tragen und nicht sagen
# koennen, ob jedes Gate geurteilt hat - und ausdruecklich offen gelassen, ob das
# heute etwas trifft. Die drei Tests unten beantworten es fuer den Fall, an dem
# die meisten davon haengen.
#
# Gemessen: Spot-Betriebspunkt, Portfolio-Walk-Forward BTC + ETH auf
# Tageskerzen, 158 Trades - **alle elf Gates faellen ein Urteil, null
# Aussetzer**. Die rohen Paare sind damit richtig, und 'cli stand' zaehlt mit
# seinen "9 von 11" keine geschenkte Zahl mit.
#
# Sie sind die Wache dazu: Sinkt die Trade-Zahl unter 30 - oder kommt eine neue
# Aussetz-Bedingung dazu -, dann werden die rohen Paare falsch, und das faellt
# hier auf und nicht in einem Bericht.


@pytest.fixture(scope="module")
def gates():
    """Die elf Gates am Spitzenkandidaten, wie die Zulassung sie rechnet.

    Modulweit und nicht klassenweit: Eine klassenweite Fixture stolpert hier in
    ``_pytest.fixtures`` (``assert not self._finalizers``).
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import (
        common_range,
        run_portfolio_walkforward,
    )
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.admission import load_trials
    from research.gates import GateThresholds, evaluate_gates
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    frames = common_range(
        {x: CandleStore(e.paths.data_store).read(x, Interval("D")) for x in symbole}
    )
    configs = cli._spotconfigs(symbole, e)
    genom = cli._ohne_hebel(spitzenkandidat())
    lauf = run_portfolio_walkforward(
        frames, lambda g=genom: compile_genome(g), configs
    )
    return evaluate_gates(
        genom,
        lauf,
        frames[symbole[0]],
        configs[symbole[0]],
        trials_so_far=load_trials(Path(e.paths.state) / "trials.json"),
        thresholds=GateThresholds(),
        frames=frames,
        configs=configs,
    )

@pytest.mark.daten
@pytest.mark.langsam
def test_alle_elf_faellen_ein_urteil(gates) -> None:
        from research.gates import GateStatus

        ausgesetzt = [
            r.name for r in gates.results if r.status is GateStatus.SKIP
        ]

        assert len(gates.results) == 11
        assert ausgesetzt == [], (
            f"Diese Gates setzen aus: {ausgesetzt}. Damit sind die rohen Paare "
            f"aus OFFEN geschenkte Zahlen - siehe Befund 332/333."
        )

@pytest.mark.daten
@pytest.mark.langsam
def test_die_neun_bestandenen_sind_echt_bestanden(gates) -> None:
        """Ohne Aussetzer ist 'passed' dasselbe wie 'PASS' - genau das macht
        die Kopfzahl von 'cli stand' belastbar."""
        from research.gates import GateStatus

        echt = sum(1 for r in gates.results if r.status is GateStatus.PASS)

        assert sum(1 for r in gates.results if r.passed) == echt == 9

@pytest.mark.daten
@pytest.mark.langsam
def test_die_trade_zahl_liegt_ueber_jeder_aussetzschwelle(gates) -> None:
        """Die Bedingung, an der es haengt: 20 fuer Monte-Carlo, 30 fuer
        Regime-Aufteilung und Deflated Sharpe."""
        stichprobe = next(
            r for r in gates.results if r.name == "Stichprobengroesse"
        )

        assert stichprobe.value >= 30
