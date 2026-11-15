"""Zwei Schreibweisen, eine Antwort - Befund 494.

Der Fund kam aus einer Inventur, nicht aus einem Unfall
-------------------------------------------------------
Befund 493 war mein Fehler: ``REIHENENDE`` ist auf den **Wert** der
Kerzenlaenge geschluesselt (``"D"``), neun Befehle uebergaben das **Etikett**
(``"1d"``), und der Reihenschnitt griff deshalb im Betrieb nie. Danach habe
ich gefragt, wo dieselbe Form noch steht - und nicht gewartet, bis es wieder
auffaellt.

Gezaehlt im Baum: **drei** Tafeln nach Kerzenlaenge, und sie sind nicht
einheitlich geschluesselt.

    research/datenstand.py  REIHENENDE   Wert     "D", "15"
    research/datenstand.py  REIHENNAME   Wert     "D", "15"
    research/laufkosten.py  MESSUNGEN    Etikett  "1d", "15m"

Und neun Zugriffe auf Tafeln dieser Art gehen ueber ``.get`` - ein Fehlgriff
faellt dort **still** in einen Ersatzzweig, der wie eine Antwort aussieht.
Gemessen vor dem Befund:

    dauer("1d", 30) == 180.0        dauer("D", 30) is None

Dieselbe Kerzenlaenge, zwei Antworten. Und die falsche klang nach Sorgfalt:
*"Laufzeit fuer 'D' nicht gemessen (bekannt: 15m, 1d) - hier wird nichts
hochgerechnet."* Ein Satz, der sich weigert zu schaetzen, wo eine Messung
daliegt.

Warum nicht eine Konvention erzwungen wurde
-------------------------------------------
``MESSUNGEN`` schluesselt mit Absicht auf das Etikett: Seine Schluessel
**stehen in der Auskunft**. "bekannt: 15m, 1d" liest sich, wie ein Mensch es
sagt; "bekannt: 15, D" nicht. Die Tafeln duerfen also ihre Schreibweise
behalten - was nicht bleiben darf, ist die Falle am Zugriff.

Deshalb steht die Deutung in ``Interval.gedeutet``, **neben** den beiden
Schreibweisen, und jede Tafel deutet erst und fragt dann in ihrer eigenen.

Und geprueft wird die Wirkung
-----------------------------
Das war die Lehre aus 493: Die Regel dort prueft die **Form** - niemand ruft
die Tagesfassung direkt -, und darunter tat der Verteiler nichts. Hier wird
deshalb gefragt, ob **dieselbe Antwort** herauskommt, egal wie die
Kerzenlaenge geschrieben war. Dazu eine Inventur, die die Tafeln im Baum
**findet** und nicht listet: Kommt eine vierte dazu, faellt sie auf.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.models import Interval

WURZEL = Path(__file__).resolve().parents[1]

#: Die Schreibweisen, die eine Kerzenlaenge im Baum annimmt.
ETIKETTEN = frozenset(m.label for m in Interval)
WERTE = frozenset(m.value for m in Interval)

#: Die gepflegten Kerzenlaengen - aus der Reihentafel, nicht gelistet.
GEPFLEGT: tuple[str, ...] = ("D", "15")


class TestDieDeutungKenntJedeSchreibweise:
    @pytest.mark.parametrize("mitglied", list(Interval), ids=lambda m: m.name)
    def test_wert_etikett_name_und_objekt(self, mitglied: Interval) -> None:
        for wie in (mitglied, mitglied.value, mitglied.label, mitglied.name):
            assert Interval.gedeutet(wie) is mitglied, wie

    def test_was_keine_kerzenlaenge_ist_gibt_keine(self) -> None:
        """``None`` und nicht geraten: Dann antwortet die Tafel "nicht
        gemessen", und das ist richtig (Befund 370)."""
        assert Interval.gedeutet("Quartal") is None
        assert Interval.gedeutet("") is None
        assert Interval.gedeutet(None) is None

    def test_die_beiden_schreibweisen_sind_wirklich_verschieden(self) -> None:
        """Die Messung, aus der beide Befunde kommen. Waeren Wert und Etikett
        gleich, waere keiner der beiden moeglich gewesen."""
        verschieden = [m.name for m in Interval if m.value != m.label]

        assert len(verschieden) == len(list(Interval)), verschieden


class TestDieseAntwortHaengtNichtAnDerSchreibweise:
    """**Die Wirkung, nicht die Form.** Jede Tafel wird in jeder Schreibweise
    gefragt, und es muss dasselbe herauskommen."""

    @pytest.mark.parametrize("schluessel", GEPFLEGT)
    def test_die_reihentafel(self, schluessel: str) -> None:
        from research.datenstand import letzter_tag

        iv = Interval(schluessel)
        antworten = {letzter_tag(w) for w in (iv, iv.value, iv.label, iv.name)}

        assert len(antworten) == 1, antworten
        assert None not in antworten

    @pytest.mark.parametrize("etikett", ["1d", "15m"])
    def test_die_kostentafel(self, etikett: str) -> None:
        """**Der Fund.** Vor 494 war 'D' hier ``None`` und '1d' 180 Sekunden."""
        from research.laufkosten import dauer

        iv = Interval.gedeutet(etikett)
        assert iv is not None
        antworten = {dauer(w, 30) for w in (iv, iv.value, iv.label, iv.name)}

        assert len(antworten) == 1, antworten
        assert None not in antworten

    def test_und_der_name_der_reihe_auch_nicht(self) -> None:
        import pandas as pd

        from research.datenstand import letzter_tag, reihenzeile

        zeilen = set()
        for wie in ("15", "15m", "M15", Interval("15")):
            rahmen = {
                "a": pd.DataFrame(
                    {
                        "open_time": pd.date_range(
                            "2021-01-01", str(letzter_tag("15")), freq="D", tz="UTC"
                        )
                    }
                )
            }
            zeilen.add(reihenzeile(rahmen, wie))

        assert len(zeilen) == 1, zeilen
        assert "keine gepflegte" not in zeilen.pop()

    def test_eine_ungemessene_kerzenlaenge_bleibt_ungemessen(self) -> None:
        """Die Gegenprobe: Deuten heisst nicht hochrechnen. Fuer 'W' gibt es
        keine Laufzeitmessung, und dabei bleibt es."""
        from research.laufkosten import dauer

        for wie in ("W", "1w", "W1", Interval("W")):
            assert dauer(wie, 30) is None, wie


class TestDieInventurFindetDieTafeln:
    """Gefunden und nicht gelistet (Befund 234/485): Kommt eine vierte Tafel
    nach Kerzenlaenge dazu, faellt sie hier auf - und dann gehoert sie an die
    Deutung."""

    def _tafeln(self) -> dict[str, tuple[str, str]]:
        """Jede Tafel im Baum, deren Schluessel Kerzenlaengen sind."""
        gefunden: dict[str, tuple[str, str]] = {}
        ordner = ("research", "core", "backtest", "data", "strategy", "execution")
        dateien = [WURZEL / "cli.py"]
        for name in ordner:
            dateien.extend(sorted((WURZEL / name).glob("*.py")))
        for pfad in dateien:
            if not pfad.exists():
                continue
            baum = ast.parse(pfad.read_text(encoding="utf-8"))
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.Dict) or not knoten.keys:
                    continue
                texte = {
                    s.value
                    for s in knoten.keys
                    if isinstance(s, ast.Constant) and isinstance(s.value, str)
                }
                if len(texte) < 2:
                    continue
                if texte <= WERTE:
                    art = "Wert"
                elif texte <= ETIKETTEN:
                    art = "Etikett"
                else:
                    continue
                gefunden[f"{pfad.name}:{knoten.lineno}"] = (art, pfad.name)
        return gefunden

    def test_es_sind_drei(self) -> None:
        """Zwei auf Werten (REIHENENDE, REIHENNAME), eine auf Etiketten
        (MESSUNGEN). Die Zahl ist gezaehlt, nicht geschaetzt."""
        tafeln = self._tafeln()

        assert len(tafeln) == 3, sorted(tafeln)

    def test_und_beide_konventionen_kommen_vor(self) -> None:
        """Die Begruendung des Befundes als Messung: Es ist wirklich keine
        einheitliche Schreibweise - sonst waere die Deutung Zierrat."""
        arten = {art for art, _ in self._tafeln().values()}

        assert arten == {"Wert", "Etikett"}, arten

    def test_jedes_modul_mit_einer_tafel_deutet_auch(self) -> None:
        """Wer eine solche Tafel haelt, muss die Kerzenlaenge deuten, bevor er
        sie fragt - sonst ist die Falle aus 493/494 wieder offen."""
        ohne = []
        for stelle, (_art, datei) in sorted(self._tafeln().items()):
            quelle = next(
                p for p in WURZEL.rglob(datei) if ".venv" not in str(p)
            ).read_text(encoding="utf-8")
            if "Interval.gedeutet" not in quelle and "kerzenschluessel" not in quelle:
                ohne.append(stelle)

        assert ohne == [], (
            "haelt eine Tafel nach Kerzenlaenge und deutet nicht - genau das "
            f"war Befund 493 und 494: {ohne}"
        )
