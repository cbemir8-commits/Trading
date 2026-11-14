"""Was "hinterlaesst nichts" wirklich deckte - Befund 481.

``tests/test_trockenlauf_deckt_alles`` traegt seinen Anspruch im Namen, und
der Kopf sagt es noch einmal: *"Der Trockenlauf deckt alle Schreibstellen."*
Die Datei prueft die Variable, die Sendestelle und warum ``PATHS__STATE``
nicht genuegt. **Was sie nie tut: die Schreibstellen aufzaehlen.** Der
Anspruch stand als Wort da, nicht als Messung.

Gemessen deckte der Trockenlauf vier Stellen - Zaehler, Bestenliste, Bericht,
Senden - und die **Datenspeicher** waren nie darunter:

    data/store.py:158    CandleStore.write_frame    fragt_trockenlauf=False
    data/funding.py:108  FundingStore.write         fragt_trockenlauf=False

Das ist nicht theoretisch aufgefallen. Der Rauchtest aus Befund 473 lief
ausdruecklich mit ``TRADING_TROCKENLAUF=1``, und 'cli referenz' hat den
gepinnten Kerzenspeicher trotzdem um 2.606 Balken verlaengert: Befund 474.
Weg waren damit ``speicher_ist_gepinnt`` und ``erwartete_ausfaelle`` - also
die Grundlage des Commit-Gates -, und die Wiederherstellung ging von Hand.

**Befund 474 hat die Einteilung geheilt, nicht das Werkzeug.** Seitdem nimmt
kein Befehl unter ``HARMLOS`` einen schreibenden Einstiegspunkt. Das ist die
richtige Wache an der richtigen Stelle - sie schuetzt den Rauchtest. Sie
schuetzt nicht die Zusage des Werkzeugs, und die galt weiter fuer mehr, als
es konnte. Wer ``TRADING_TROCKENLAUF`` setzt und etwas laufen laesst, das
laedt, hat genau einmal den Vorfall von 474.

Seit 481 fragen beide Ablagen. Diese Datei haelt nicht das Ergebnis fest,
sondern die **Abdeckung**: Wer eine neue Stelle baut, die eine Tabelle
dauerhaft ablegt, faellt hier auf, statt es beim naechsten Lauf zu merken.

Die Grenze steht als Liste mit Gruenden
---------------------------------------
"Alle" war das falsche Wort, und es durch ein anderes Wort zu ersetzen waere
dieselbe Bauart. Gedeckt sind die Stellen, die beim **Messen** schreiben.
Journal, Zugangsdatei, Zwischenstand und Sperrdatei gehoeren zum
Handelsbetrieb und zum Einrichten; die deckt der Trockenlauf absichtlich
nicht, und sie stehen unten mit Grund.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import Candle, Interval
from research.versuche import TROCKENLAUF

WURZEL = Path(__file__).resolve().parents[1]

#: Wo gesucht wird. ``tests`` bleibt draussen: Ein Test darf ablegen.
#:
#: **Diese Liste war erst zu kurz, und zwar in meinem eigenen Melder.** Der
#: erste Entwurf nahm sieben Ordner und ``cli.py`` - ``scripts``,
#: ``strategy`` (Einzahl, neben ``strategies``!) und ``install.py`` fehlten.
#: Dort liegen gemessen null Ablagen, aber das war **angenommen** und nicht
#: geprueft. Unten haelt eine Zusicherung nach, dass kein Modul des Baums
#: ungesehen bleibt - sonst ist die Wache enger als das, was sie bewacht.
ORDNER: tuple[str, ...] = (
    "backtest",
    "core",
    "data",
    "execution",
    "research",
    "scripts",
    "strategies",
    "strategy",
    "web",
)

#: Module, die in keinem Ordner liegen.
WURZELDATEIEN: tuple[str, ...] = ("cli.py", "install.py")

#: Was beim Durchsuchen des Baums nicht mitzaehlt.
DRAUSSEN: frozenset[str] = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "tests",
    }
)

#: Was "eine Tabelle dauerhaft ablegen" heisst.
#:
#: Absichtlich eng. Ein Melder auf *jede* Schreibstelle findet 89 Treffer -
#: ``mkdir``, ``unlink``, jedes ``json.dump`` in einen Bericht -, und eine
#: Regel ueber 89 Stellen mit 78 Ausnahmen ist keine Regel. Dauerhafte
#: Tabellen sind die **Messgrundlage**: Auf ihnen stehen die gepinnten
#: Zahlen, und genau dort hat Befund 474 wehgetan.
ABLAGE: frozenset[str] = frozenset({"to_parquet", "to_csv"})

#: Die Stellen, die der Trockenlauf deckt - gepflegt, und unten gegen den
#: Quelltext geprueft.
GEDECKT: tuple[str, ...] = (
    "data/funding.py",
    "data/store.py",
    "research/versuche.py",
)

#: Dauerhafte Ablagen, die der Trockenlauf **nicht** deckt - mit Grund.
#:
#: Sie schreiben nicht beim Messen. Ein Rauchtest darf die Befehle dahinter
#: gar nicht starten, und die Wache dafuer steht in ``test_rauchtest`` unter
#: ``WIRKT_NACH_AUSSEN``. Zwei Wachen fuer zwei verschiedene Fragen.
AUSSERHALB: dict[str, str] = {
    "web/journal.py": "Journal des Handelsbetriebs",
    "core/envfile.py": "Zugangsdaten, von 'cli setup' geschrieben",
    "research/zwischenstand.py": "Zwischenstand eines abgebrochenen Laufs",
    "execution/einzelbetrieb.py": "Sperrdatei gegen den zweiten Handelslauf",
}


@dataclass(frozen=True, slots=True)
class Stelle:
    datei: str
    zeile: int
    funktion: str
    fragt: bool
    """``True``, wenn die umgebende Funktion ``trockenlauf()`` fragt."""


def ablagestellen(text: str, datei: str) -> tuple[Stelle, ...]:
    """Jede Funktion, die eine Tabelle dauerhaft ablegt.

    Gesucht wird am Syntaxbaum und ueber die **umgebende Funktion**: Die
    Wache muss in derselben Funktion stehen wie der Schreibvorgang. Stuende
    sie beim Aufrufer, waere sie eine Vereinbarung und keine Wache - das ist
    die Lehre, die ``test_trockenlauf_deckt_alles`` selbst zieht.
    """
    baum = ast.parse(text)
    eltern: dict[ast.AST, ast.AST] = {}
    for knoten in ast.walk(baum):
        for kind in ast.iter_child_nodes(knoten):
            eltern[kind] = knoten

    gefunden: list[Stelle] = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        if not isinstance(knoten.func, ast.Attribute):
            continue
        if knoten.func.attr not in ABLAGE:
            continue
        hoch: ast.AST = knoten
        umgebend: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        while hoch in eltern:
            hoch = eltern[hoch]
            if isinstance(hoch, ast.FunctionDef | ast.AsyncFunctionDef):
                umgebend = hoch
                break
        gefunden.append(
            Stelle(
                datei=datei,
                zeile=knoten.lineno,
                funktion=umgebend.name if umgebend else "<modul>",
                fragt=bool(umgebend) and "trockenlauf()" in ast.unparse(umgebend),
            )
        )
    return tuple(gefunden)


def _dateien() -> list[Path]:
    aus: list[Path] = [WURZEL / name for name in WURZELDATEIEN]
    for name in ORDNER:
        ordner = WURZEL / name
        if ordner.is_dir():
            aus += sorted(ordner.rglob("*.py"))
    return [p for p in aus if p.exists()]


def _module_des_baums() -> set[Path]:
    """Jedes Modul, das zum Projekt gehoert - unabhaengig von ``ORDNER``."""
    return {
        p.resolve()
        for p in WURZEL.rglob("*.py")
        if not (DRAUSSEN & set(p.relative_to(WURZEL).parts))
    }


def _alle() -> tuple[Stelle, ...]:
    aus: list[Stelle] = []
    for pfad in _dateien():
        aus += ablagestellen(
            pfad.read_text(encoding="utf-8"), str(pfad.relative_to(WURZEL))
        )
    return tuple(aus)


ABLAGEN = _alle()


class TestDerMelderTaugt:
    """Vor der Regel der Melder. In dieser Sitzung war das siebzehn Mal
    noetig, und einmal hat ein Melder das falsche Ding gefunden (478)."""

    def test_er_findet_ueberhaupt_etwas(self) -> None:
        """Die Zusicherung, die in Befund 479 gefehlt hat: Ein Melder, der
        die leere Menge findet, prueft nichts und sagt es nicht."""
        assert ABLAGEN, "keine Ablage gefunden - dann prueft alles darunter nichts"

    def test_er_sieht_eine_ungedeckte_stelle(self) -> None:
        stellen = ablagestellen(
            "def schreib(frame, pfad):\n    frame.to_parquet(pfad)\n", "probe"
        )

        assert len(stellen) == 1
        assert stellen[0].funktion == "schreib"
        assert not stellen[0].fragt

    def test_und_eine_gedeckte(self) -> None:
        stellen = ablagestellen(
            "def schreib(frame, pfad):\n"
            "    if trockenlauf():\n"
            "        return 0\n"
            "    frame.to_parquet(pfad)\n",
            "probe",
        )

        assert stellen[0].fragt

    def test_eine_wache_beim_aufrufer_zaehlt_nicht(self) -> None:
        """**Die entscheidende Gegenprobe.** Genau so sah die Luecke aus, die
        Befund 331 gekostet hat: Der Schutz lag in der Aufrufstelle."""
        stellen = ablagestellen(
            "def aufrufer(frame, pfad):\n"
            "    if trockenlauf():\n"
            "        return 0\n"
            "    return schreib(frame, pfad)\n"
            "\n"
            "def schreib(frame, pfad):\n"
            "    frame.to_parquet(pfad)\n",
            "probe",
        )

        assert len(stellen) == 1
        assert not stellen[0].fragt

    def test_er_sieht_den_ganzen_baum(self) -> None:
        """**Meine eigene Luecke, als Zusicherung.** Der erste Entwurf dieses
        Melders durchsuchte sieben Ordner und ``cli.py``; ``scripts``,
        ``strategy`` und ``install.py`` lagen daneben. Eine Wache, die enger
        sucht als der Baum, meldet die naechste Ablage nicht - und das ist
        genau die Bauart, die dieser Befund behebt.
        """
        ungesehen = _module_des_baums() - {p.resolve() for p in _dateien()}

        assert ungesehen == set(), (
            "Modul des Baums, das dieser Melder nicht durchsucht - ORDNER "
            f"oder WURZELDATEIEN ergaenzen: {sorted(str(p) for p in ungesehen)}"
        )

    def test_ein_bericht_ist_keine_tabellenablage(self) -> None:
        """Die Grenze des Melders, als Messung: ``json.dump`` schlaegt nicht
        an. Sonst waere die Regel ueber 89 Stellen mit 78 Ausnahmen."""
        assert ablagestellen("def f(d, h):\n    json.dump(d, h)\n", "probe") == ()


class TestJedeTabellenablageFragt:
    def test_alle(self) -> None:
        """**Die Regel.** Vor Befund 481 waren hier zwei von zwei rot."""
        offen = [f"{s.datei}:{s.zeile} {s.funktion}" for s in ABLAGEN if not s.fragt]

        assert offen == [], (
            "legt eine Tabelle dauerhaft ab, ohne den Trockenlauf zu fragen - "
            f"genau diese Bauart ist Befund 474: {offen}"
        )

    def test_und_es_sind_die_zwei_gemessenen(self) -> None:
        """Gepflegt und geprueft. Kommt eine dritte Ablage dazu, faellt sie
        hier auf und muss sich entscheiden, ob sie beim Messen schreibt."""
        assert {s.datei for s in ABLAGEN} == {"data/store.py", "data/funding.py"}

    def test_die_gedeckten_dateien_fragen_wirklich(self) -> None:
        for datei in GEDECKT:
            quelle = (WURZEL / datei).read_text(encoding="utf-8")

            assert "trockenlauf()" in quelle, datei


class TestDieGrenzeStehtMitGrund:
    """"Alle" war das falsche Wort. Ein anderes Wort waere dieselbe Bauart."""

    def test_die_genannten_stellen_schreiben_wirklich(self) -> None:
        """Sonst waere die Liste eine Erzaehlung. Gemessen schreibt jede."""
        for datei in AUSSERHALB:
            quelle = (WURZEL / datei).read_text(encoding="utf-8")

            assert any(
                wort in quelle
                for wort in ("write_text", "write_bytes", ".write(", "dump(")
            ), datei

    def test_und_keine_davon_ist_eine_tabellenablage(self) -> None:
        """Der Grund, warum sie ausserhalb stehen duerfen: Sie beruehren die
        Messgrundlage nicht."""
        assert set(AUSSERHALB) & {s.datei for s in ABLAGEN} == set()

    def test_jede_hat_einen_grund(self) -> None:
        assert all(len(grund) > 10 for grund in AUSSERHALB.values())


def _kerze(t0, *, hoch: str = "40100") -> Candle:
    return Candle(
        open_time=t0,
        open=Decimal("40000"),
        high=Decimal(hoch),
        low=Decimal("39900"),
        close=Decimal("40050"),
        volume=Decimal("1.5"),
        turnover=Decimal("60000"),
    )


@pytest.fixture
def t0():
    from datetime import UTC, datetime

    return datetime(2024, 1, 1, tzinfo=UTC)


class TestDerKerzenspeicherGehorcht:
    """Nicht der Quelltext, sondern der Lauf - die Lehre aus Befund 425."""

    def test_mit_variable_bleibt_die_platte_leer(self, tmp_path, monkeypatch, t0):
        from data.store import CandleStore

        monkeypatch.setenv(TROCKENLAUF, "1")
        store = CandleStore(tmp_path / "data_store")

        neu = store.write("BTCUSDT", Interval.M15, [_kerze(t0)])

        assert neu == 0
        assert list(tmp_path.rglob("*.parquet")) == []

    def test_ohne_variable_schreibt_er(self, tmp_path, monkeypatch, t0):
        """Die Gegenprobe. Ohne sie koennte die Wache alles blockieren und
        der Test waere gruen."""
        from data.store import CandleStore

        monkeypatch.delenv(TROCKENLAUF, raising=False)
        store = CandleStore(tmp_path / "data_store")

        neu = store.write("BTCUSDT", Interval.M15, [_kerze(t0)])

        assert neu == 1
        assert list(tmp_path.rglob("*.parquet"))

    def test_der_vorfall_aus_474_in_klein(self, tmp_path, monkeypatch, t0):
        """**Der Vorfall selbst, nachgestellt.** Ein Speicher mit Stand, ein
        Lauf mit gesetzter Variable - und der Stand muss derselbe bleiben.
        Genau das hat 2.606 Balken lang nicht gegolten."""
        from datetime import timedelta

        from data.store import CandleStore

        monkeypatch.delenv(TROCKENLAUF, raising=False)
        store = CandleStore(tmp_path / "data_store")
        store.write("BTCUSDT", Interval.M15, [_kerze(t0)])
        vorher = len(store.read("BTCUSDT", Interval.M15))

        monkeypatch.setenv(TROCKENLAUF, "1")
        store.write("BTCUSDT", Interval.M15, [_kerze(t0 + timedelta(minutes=15))])

        assert len(store.read("BTCUSDT", Interval.M15)) == vorher


class TestDieFundingablageGehorcht:
    def _rate(self, t0):
        from data.funding import FundingRate

        return FundingRate(
            symbol="BTCUSDT", funding_time=t0, funding_rate=Decimal("0.0001")
        )

    def test_mit_variable_bleibt_die_platte_leer(self, tmp_path, monkeypatch, t0):
        from data.funding import FundingStore

        monkeypatch.setenv(TROCKENLAUF, "1")
        store = FundingStore(tmp_path / "data_store")

        neu = store.write("BTCUSDT", [self._rate(t0)])

        assert neu == 0
        assert list(tmp_path.rglob("*.parquet")) == []

    def test_ohne_variable_schreibt_sie(self, tmp_path, monkeypatch, t0):
        from data.funding import FundingStore

        monkeypatch.delenv(TROCKENLAUF, raising=False)
        store = FundingStore(tmp_path / "data_store")

        neu = store.write("BTCUSDT", [self._rate(t0)])

        assert neu == 1
        assert list(tmp_path.rglob("*.parquet"))


def test_der_kopf_der_anderen_datei_behauptet_es_nicht_mehr_pauschal() -> None:
    """Dieselbe Lehre wie in Befund 478: Ein Kopf, der mehr behauptet als
    gemessen ist, ist die Luecke - nicht der fehlende Test."""
    kopf = (WURZEL / "tests/test_trockenlauf_deckt_alles.py").read_text(
        encoding="utf-8"
    )

    assert "481" in kopf
    assert "test_trockenlaufdeckung" in kopf
