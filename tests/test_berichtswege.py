"""Es gibt zwei Wege in den Berichtsverlauf, nicht einen - Befund 482.

``tests/test_berichtswache`` traegt seinen Anspruch in der ersten Zeile:
*"Wer nach ``reports/`` schreibt, geht durch ``write_report``."* Dahinter
stehen drei Zusagen, die Befund 244 einzeln benannt hat - die
Trockenlauf-Wache aus 116, ``scrub`` gegen Schluessel, die nicht in ein
oeffentliches Repository gehoeren, und der Schutz gegen zwei Laeufe in
derselben Sekunde.

**Der Satz stimmt nicht.** ``research/zwischenstand.py`` legt seine
Protokolle unter ``reports/<art>/<zeitpunkt>.jsonl`` ab - 168 Dateien im
Baum, 25 unter ``reibung`` und 143 unter ``vorratsdecke``, die neuesten von
heute. Es ging an der Wache vorbei und trug von den drei Zusagen **eine**:
den Namensschutz (es zaehlt bei Kollision hoch), nicht den Trockenlauf und
nicht ``scrub``.

Warum die Wache es nicht gesehen hat - zweimal zu eng
-----------------------------------------------------
1. Sie durchsucht **nur ``cli.py``** (``_befehle`` liest genau diese Datei).
   Ein Modul, das schreibt, ist unsichtbar.
2. Ihr Schreibmuster ist ``\\.write_text\\(|json\\.dump|mkdir``. Der
   Protokollweg schreibt mit ``pfad.open("a")`` und ``datei.write(...)`` -
   davon kommt keines im Muster vor.

Dieselbe Bauart wie Befund 479 und 481: Die Wache stand da, sah aber am
falschen Weg nach.

Und es ist eingetreten, zweimal
-------------------------------
Der Rauchtest aus Befund 473 lief mit ``TRADING_TROCKENLAUF=1``. Zurueck
blieben zwei Protokolle - ``reibung/2026-11-14_032322.jsonl`` (44 Messungen)
und ``vorratsdecke/2026-11-14_033354.jsonl`` (25) -, und ich habe sie in
``491688c`` mitcommittet. Das ist der dritte Lauf dieser Art in der
Projekthistorie: ``54770ec`` (Befund 117), ``e00ffb7`` (Befund 331), und
jetzt diese.

**Und sie sind nicht folgenlos geblieben**: Befund 475 und Befund 476 haben
ihre Zahlen aus genau diesen zwei Dateien genommen - *"Von den achtzehn
stehen dreizehn im heutigen Bericht"* und die vierzehn Taktpunkte in
``REIBUNG_476``. Die Zahlen halten: Beide Protokolle sind auf der gepinnten
Tagesreihe gerechnet (3301 Balken je Markt), und ``cli referenz`` hatte am
selben Morgen nur die Viertelstundenreihe verlaengert. Was fehlte, war die
**Herkunft**: Zwei Befunde standen auf Berichten, die niemand absichtlich
erzeugt hat, und das stand nirgends.

Deshalb werden die zwei Dateien **nicht entfernt**. Sie sind die
nachlesbare Grundlage zweier Befunde; sie zu loeschen waere das Gegenteil
eines Laborbuchs. Ihre Herkunft steht jetzt dort, wo ihre Zahlen stehen.

Was heute kein Schaden war, gemessen statt angenommen
-----------------------------------------------------
* **Kein verbotenes Feld**: 0 von 168 Protokollen tragen einen Schluessel
  aus ``core.report.VERBOTEN``.
* **Die Latte ist unberuehrt**: ``cli rennen`` nimmt alle
  ``reports/vorratsdecke/*.jsonl``, gruppiert nach (Betriebspunkt, Katalog,
  Codestand) und waehlt die groesste Gruppe als dritte Schaetzung der
  Ideenstreuung - die in den Deflated Sharpe eingeht. Mit und ohne das
  Rauchtest-Protokoll: **anzahl 19, Streuung 0,0589**. Es bildet eine eigene
  Gruppe von einem und verliert den Vergleich (13 Regeln, keine Streuung).
* **Latent war es trotzdem**: Sein Codestand ist der heutige. Der naechste
  absichtliche Lauf auf diesem Code waere mit ihm **verschmolzen** - und dann
  haette eine Rauchtest-Messung die Huerde des haertesten Gates mitbestimmt.

Die Regel, die hier steht
-------------------------
Nicht "geht durch ``write_report``" - das ist ein Funktionsname, und der Fund
zeigt, dass es einen zweiten Weg geben darf. Sondern: **Wer in den
Berichtsverlauf schreibt, traegt die Zusagen.** Gemessen sind das drei
Module, und zwei davon trugen sie schon.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]

#: Wo gesucht wird - der ganze Baum, nicht nur ``cli.py``. Das war die erste
#: der beiden Engen.
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

WURZELDATEIEN: tuple[str, ...] = ("cli.py", "install.py")

#: Der Ordner, um den es geht.
ORDNERNAME = "reports"

#: Woran erkannt wird, dass ein Modul einen Berichtspfad **bildet**.
#:
#: Nach dem Pfadteil in Anfuehrungszeichen, nicht nach dem Wort: ``reports``
#: kommt in diesem Baum in viel Prosa vor.
PFADBILDUNG = re.compile(r"""["']reports["']|["']reports/""")

#: Die Zusagen, die ein Berichtsweg tragen muss (Befund 244).
ZUSAGEN: tuple[str, ...] = ("trockenlauf", "scrub")


@dataclass(frozen=True, slots=True)
class Weg:
    datei: str
    bildet_pfad: bool
    schreibt: bool
    zusagen: tuple[str, ...]

    @property
    def ist_weg(self) -> bool:
        return self.bildet_pfad and self.schreibt

    @property
    def vollstaendig(self) -> bool:
        return set(self.zusagen) >= set(ZUSAGEN)


def schreibt(text: str) -> bool:
    """Legt dieses Modul eine Datei an - **auch durch Anhaengen**?

    Das war die zweite Enge. Die alte Fassung suchte nach
    ``write_text``/``json.dump``/``mkdir``; der Protokollweg schreibt mit
    ``pfad.open("a")`` und ``datei.write(...)``, und davon kam keines im
    Muster vor. Gesucht wird deshalb am Syntaxbaum nach dem **Modus**.
    """
    for knoten in ast.walk(ast.parse(text)):
        if not isinstance(knoten, ast.Call):
            continue
        f = knoten.func
        name = (
            f.attr
            if isinstance(f, ast.Attribute)
            else (f.id if isinstance(f, ast.Name) else None)
        )
        if name in {"write_text", "write_bytes", "write"}:
            return True
        if (
            name == "dump"
            and isinstance(f, ast.Attribute)
            and ast.unparse(f.value) in {"json", "_json"}
        ):
            return True
        if name == "open":
            modi = [a for a in knoten.args if isinstance(a, ast.Constant)]
            modi += [
                k.value
                for k in knoten.keywords
                if k.arg == "mode" and isinstance(k.value, ast.Constant)
            ]
            for m in modi:
                if isinstance(m.value, str) and set(m.value) & {"w", "a", "x"}:
                    return True
    return False


def _dateien() -> list[Path]:
    aus: list[Path] = [WURZEL / n for n in WURZELDATEIEN]
    for name in ORDNER:
        ordner = WURZEL / name
        if ordner.is_dir():
            aus += sorted(ordner.rglob("*.py"))
    return [p for p in aus if p.exists()]


def wege() -> tuple[Weg, ...]:
    aus: list[Weg] = []
    for pfad in _dateien():
        text = pfad.read_text(encoding="utf-8")
        if not PFADBILDUNG.search(text):
            continue
        aus.append(
            Weg(
                datei=str(pfad.relative_to(WURZEL)),
                bildet_pfad=True,
                schreibt=schreibt(text),
                zusagen=tuple(z for z in ZUSAGEN if z in text),
            )
        )
    return tuple(aus)


WEGE = wege()
SCHREIBENDE = tuple(w for w in WEGE if w.ist_weg)


class TestDerMelderTaugt:
    def test_er_findet_wege(self) -> None:
        """Die Nichtleere-Zusicherung aus Befund 479: Ein Melder, der nichts
        findet, prueft nichts und sagt es nicht."""
        assert SCHREIBENDE, WEGE

    def test_er_sieht_ein_anhaengen(self) -> None:
        """**Die Gegenprobe, die die alte Wache nicht hatte.** Genau so
        schreibt der Protokollweg."""
        assert schreibt('with pfad.open("a") as datei:\n    datei.write(satz)\n')

    def test_und_ein_schreiben_mit_mode(self) -> None:
        assert schreibt('open(pfad, mode="w")')

    def test_aber_ein_lesen_nicht(self) -> None:
        assert not schreibt('text = pfad.open("r").read()\nfor p in o.glob("*"):\n    pass\n')

    def test_und_ein_blosses_oeffnen_nicht(self) -> None:
        """``open(pfad)`` ohne Modus liest - das ist die Vorgabe."""
        assert not schreibt("daten = open(pfad).read()")

    def test_er_unterscheidet_pfadbildung_von_prosa(self) -> None:
        """``reports`` steht in diesem Baum in viel Text. Gemeint ist der
        Pfadteil."""
        assert PFADBILDUNG.search('ordner = wurzel / "reports" / art')
        assert PFADBILDUNG.search('Path("reports/vorratsdecke")')
        assert not PFADBILDUNG.search("Die reports liegen daneben.")


class TestJederWegTraegtDieZusagen:
    def test_alle(self) -> None:
        """**Die Regel.** Vor Befund 482 fiel hier
        ``research/zwischenstand.py`` durch - mit keiner der beiden
        Zusagen."""
        offen = [
            f"{w.datei} (hat: {', '.join(w.zusagen) or 'keine'})"
            for w in SCHREIBENDE
            if not w.vollstaendig
        ]

        assert offen == [], (
            "schreibt in den Berichtsverlauf, ohne die Zusagen aus Befund 244 "
            f"zu tragen: {offen}"
        )

    def test_und_es_sind_die_drei_gemessenen(self) -> None:
        """Gepflegt und geprueft. Ein vierter Weg faellt hier auf und muss
        sich entscheiden, ob er in den Verlauf gehoert."""
        assert {w.datei for w in SCHREIBENDE} == {
            "cli.py",
            "core/report.py",
            "research/zwischenstand.py",
        }

    def test_die_lesenden_wege_sind_nicht_gemeint(self) -> None:
        """Sonst waere die Regel eine ueber alles, was den Ordner erwaehnt -
        dieselbe Sorte Gespenst wie in Befund 243."""
        nur_lesend = {w.datei for w in WEGE} - {w.datei for w in SCHREIBENDE}

        assert nur_lesend, WEGE
        assert "research/berichtslage.py" in nur_lesend


class TestDerProtokollwegGehorchtJetzt:
    """Nicht der Quelltext, sondern der Lauf - die Lehre aus Befund 425."""

    def _stand(self, tmp_path: Path):
        from research.zwischenstand import neu

        return neu(wurzel=tmp_path, art="probe", intervall="1d", genome=1)

    def test_im_trockenlauf_entsteht_kein_protokoll(self, tmp_path, monkeypatch):
        from research.versuche import TROCKENLAUF

        monkeypatch.setenv(TROCKENLAUF, "1")
        stand = self._stand(tmp_path)
        stand.beginne()
        stand.halte_fest(regel="A", guete=1.0)

        assert list(tmp_path.rglob("*.jsonl")) == []

    def test_ohne_trockenlauf_entsteht_eines(self, tmp_path, monkeypatch):
        """Die Gegenprobe. Ohne sie koennte die Wache alles unterbinden und
        der Test waere gruen."""
        from research.versuche import TROCKENLAUF

        monkeypatch.delenv(TROCKENLAUF, raising=False)
        stand = self._stand(tmp_path)
        stand.beginne()
        stand.halte_fest(regel="A", guete=1.0)

        dateien = list(tmp_path.rglob("*.jsonl"))
        assert len(dateien) == 1
        assert len(dateien[0].read_text(encoding="utf-8").splitlines()) == 2

    def test_halte_fest_bricht_im_trockenlauf_nicht_ab(self, tmp_path, monkeypatch):
        """Ein dreistuendiger Lauf darf nicht an der Buchfuehrung scheitern -
        das ist der Satz, mit dem dieses Modul gebaut wurde."""
        from research.versuche import TROCKENLAUF

        monkeypatch.setenv(TROCKENLAUF, "1")
        stand = self._stand(tmp_path)
        stand.beginne()

        for i in range(5):
            stand.halte_fest(regel=f"R{i}", guete=float(i))

    def test_die_zeile_nennt_im_trockenlauf_keinen_pfad(self, tmp_path, monkeypatch):
        """Dieselbe Lehre wie *"Bericht: <Ordner>"* in Befund 244: Eine Zeile,
        die einen Pfad nennt, an dem nichts entsteht, ist eine
        Falschmeldung."""
        from research.versuche import TROCKENLAUF

        monkeypatch.setenv(TROCKENLAUF, "1")
        zeile = self._stand(tmp_path).zeile()

        assert str(tmp_path) not in zeile
        assert TROCKENLAUF in zeile

    def test_der_kopf_geht_durch_scrub(self, tmp_path, monkeypatch):
        import json

        from research.versuche import TROCKENLAUF
        from research.zwischenstand import neu

        monkeypatch.delenv(TROCKENLAUF, raising=False)
        stand = neu(wurzel=tmp_path, art="probe", intervall="1d", api_key="geheim")
        stand.beginne()
        kopf = json.loads(
            next(tmp_path.rglob("*.jsonl")).read_text(encoding="utf-8").splitlines()[0]
        )

        assert "api_key" not in kopf
        assert kopf["intervall"] == "1d"


#: Die zwei Protokolle, die der Rauchtest aus Befund 473 hinterlassen hat -
#: und auf denen Befund 475 und 476 stehen.
AUS_DEM_RAUCHTEST: tuple[str, ...] = (
    "reports/reibung/2026-11-14_032322.jsonl",
    "reports/vorratsdecke/2026-11-14_033354.jsonl",
)


class TestWasBisherKeinSchadenWar:
    """Nachgesehen statt angenommen - erst danach steht im Befund, was es
    gekostet hat."""

    def test_kein_protokoll_traegt_ein_verbotenes_feld(self) -> None:
        import json

        from core.report import VERBOTEN

        dateien = sorted((WURZEL / ORDNERNAME).rglob("*.jsonl"))
        if not dateien:
            pytest.skip("keine Protokolle im Baum")

        def schluessel(o, pfad=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield f"{pfad}{k}"
                    yield from schluessel(v, f"{pfad}{k}.")
            elif isinstance(o, list):
                for x in o[:3]:
                    yield from schluessel(x, pfad)

        for datei in dateien:
            alle: set[str] = set()
            for zeile in datei.read_text(encoding="utf-8").splitlines():
                if not zeile.strip():
                    continue
                try:
                    alle |= set(schluessel(json.loads(zeile)))
                except json.JSONDecodeError:
                    continue
            treffer = [k for k in alle if any(w in k.lower() for w in VERBOTEN)]

            assert treffer == [], f"{datei.name}: {treffer}"

    def test_die_zwei_aus_dem_rauchtest_liegen_noch_da(self) -> None:
        """**Absichtlich.** Sie sind die nachlesbare Grundlage von Befund 475
        und 476; sie zu loeschen waere das Gegenteil eines Laborbuchs. Diese
        Zusicherung haelt fest, dass das eine Entscheidung war und kein
        Versehen - und dass niemand sie spaeter stillschweigend aufraeumt.
        """
        for name in AUS_DEM_RAUCHTEST:
            assert (WURZEL / name).exists(), name

    def test_und_ihre_herkunft_steht_dort_wo_ihre_zahlen_stehen(self) -> None:
        """Was in Befund 482 gefehlt hat, war nicht die Zahl, sondern die
        Herkunft. Also muss sie an beiden Stellen stehen."""
        for datei in ("research/vorratsdecke.py", "tests/test_kostenanteil.py"):
            text = (WURZEL / datei).read_text(encoding="utf-8")

            assert "482" in text, datei
            assert "Rauchtest" in text, datei
