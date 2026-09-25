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
``bestanden``. Drei davon wissen von Uebersprungenem. Achtzehn nicht.

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

import research

#: Typen, die ``uebersprungen`` tragen und ``bestanden_echt`` daraus rechnen.
MIT_SKIPINFO: frozenset[str] = frozenset({
    "research.machbarkeit.Stand",
    "research.nachpruefung.Ergebnis",
    "research.teststaerke.Stufe",
})

#: Typen, die **verzeichnete** Staende halten und keinen Gate-Lauf ausfuehren.
#:
#: Ihre Zahlen sind von Hand eingetragene Messwerte mit Fundstelle, kein
#: Ergebnis einer Auswertung - dort gibt es nichts zu ueberspringen. Das ist
#: der einzige Grund, den dieser Lauf **belegen** kann.
VERZEICHNET: dict[str, str] = {
    "research.referenz.Referenzpunkt": "feste Referenzstaende mit Befundnummer",
    "research.historie.Historienstufe": "gemessene Fenster aus Befund 133",
}

#: Typen, bei denen die Frage **offen** ist - aufgelistet, nicht geprueft.
#:
#: **Bewusst als Liste und nicht als "alles Uebrige".** Sonst waere das
#: Verzeichnis per Konstruktion vollstaendig, dieser Test tautologisch, und ein
#: neuer Typ faende sich stillschweigend auf der harmlosen Seite wieder.
#:
#: Was hier steht, heisst: Der Typ traegt eine Gate-Zahl, kann aber nicht sagen,
#: ob jedes Gate geurteilt hat. Ob ihn das heute trifft, ist nicht gemessen.
OFFEN: frozenset[str] = frozenset({
    "research.admission.Zulassungsbedingungen",
    "research.aufloesung.Messung",
    "research.aufstellung.Marktsatz",
    "research.betriebspunkt.Betriebspunkt",
    "research.decke.Fenster",
    "research.decke.Stufe",
    "research.finanzierung.Stufe",
    "research.gatemuster.Gatelage",
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
        bekannt = MIT_SKIPINFO | set(VERZEICHNET) | OFFEN

        unbekannt = sorted(set(_traeger()) - bekannt)

        assert unbekannt == [], (
            f"nicht eingeordnet: {unbekannt} - kann der Typ sagen, ob jedes "
            f"Gate geurteilt hat? Dann MIT_SKIPINFO. Haelt er einen "
            f"verzeichneten Stand? Dann VERZEICHNET. Sonst OFFEN."
        )

    def test_das_verzeichnis_nennt_keine_typen_die_es_nicht_gibt(self) -> None:
        bekannt = MIT_SKIPINFO | set(VERZEICHNET) | OFFEN

        verwaist = sorted(bekannt - set(_traeger()))

        assert verwaist == []

    def test_keine_doppelte_einordnung(self) -> None:
        assert not MIT_SKIPINFO & OFFEN
        assert not MIT_SKIPINFO & set(VERZEICHNET)
        assert not OFFEN & set(VERZEICHNET)


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
    assert len(OFFEN) == 16
    assert len(MIT_SKIPINFO) == 3
    assert len(_traeger()) == 21
