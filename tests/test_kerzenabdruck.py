"""Die Herkunft war hohl, und sechs teure Laeufe schwiegen - Befund 495.

Teil eins: der Abdruck trug Zeilennummern
-----------------------------------------
``cli._kerzenabdruck`` schreibt in jeden Protokollkopf, worauf gerechnet
wurde. Sein Docstring nennt den Zweck: *"Befund 102 haelt fest, dass Kerzen
ohne Herkunft Zahlen ohne Bedeutung sind. Zwei Stuecke auf verschieden langen
Reihen waeren zwei Messungen."*

Darin stand:

    {'zeilen': '3301', 'von': '0', 'bis': '3300'}

``rahmen.index`` ist bei diesen Rahmen ein Zaehler von 0 - die Zeit steht in
``open_time``. Gemessen trugen **167 von 169** Protokollen im Baum diese Form;
die zwei anderen sind aelter als das Feld. Es war also nie etwas anderes
darin.

Damit war die Zusage des Docstrings **umgekehrt falsch**: Zwei Stuecke auf
verschieden langen Reihen bekamen denselben Abdruck, solange sie gleich viele
Zeilen hatten. Die Wache gegen zwei Messungen in einem Lauf verglich eine Zahl
mit sich selbst.

Gelesen hat das Feld niemand - es ist Herkunft fuer einen spaeteren Leser, und
fuer 167 Protokolle ist sie unbrauchbar. Die Nachbarfelder sind in Ordnung:
``_katalogabdruck`` und ``_codeabdruck`` hashen wirklich Inhalt.

Teil zwei: wo das Schweigen teuer ist
-------------------------------------
Die offene Richtung zu Befund 387 nennt ihr Kriterium selbst: *"Teuer wird es
da, wo eine gepflegte Zahl aus ``referenz.py`` danebensteht oder eine
unwiderrufliche Entscheidung daran haengt."* Danach gefiltert, statt alle 41
Walk-Forward-Befehle in einen Topf zu werfen:

    Walk-Forward-Befehle                                41
    davon mit einer gepflegten Zahl daneben              9
    davon stumm                                          6

Die sechs sind ``decke``, ``koernung``, ``nachpruefung``, ``regler``,
``suchbudget`` und ``vorratsdecke``. Sie nennen jetzt ihre Reihe - geschnitten
wird nichts, denn auf allem zu rechnen, was da ist, ist richtig; es muss nur
dastehen (Befund 370).

Geprueft wird die Wirkung
-------------------------
Die Lehre aus 493: Eine Regel auf die Form haette hier nichts gemerkt - das
Feld **war** da, es stand nur Unsinn darin. Deshalb prueft die Regel unten,
dass zwei verschiedene Reihen auch verschiedene Abdruecke ergeben, und die
Regel darunter leitet ihre Grundgesamtheit aus dem Baum ab.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

import cli
from tests.schnittwege import nennt, schneidet

WURZEL = Path(__file__).resolve().parents[1]

#: Woran man eine gepflegte Zahl im Quelltext eines Befehls erkennt.
GEPFLEGTE_ZAHL: tuple[str, ...] = (
    "referenz",
    "SPOTPUNKT",
    "PERPETUALPUNKT",
    "KONTOPUNKT",
)


def _rahmen(von: str, bis: str) -> pd.DataFrame:
    zeiten = pd.date_range(von, bis, freq="1D", tz="UTC")
    return pd.DataFrame({"open_time": zeiten, "close": range(len(zeiten))})


class TestDerAbdruckNenntDieZeit:
    def test_von_und_bis_sind_kerzenzeiten(self) -> None:
        abdruck = cli._kerzenabdruck({"x": _rahmen("2017-08-16", "2026-08-29")})

        assert abdruck["x"]["von"].startswith("2017-08-16")
        assert abdruck["x"]["bis"].startswith("2026-08-29")

    def test_und_keine_zeilennummern(self) -> None:
        """**Der Fund.** Vorher stand hier ``von='0'`` und
        ``bis='<zeilen-1>'`` - dieselbe Zahl dreimal."""
        rahmen = _rahmen("2017-08-16", "2026-08-29")
        abdruck = cli._kerzenabdruck({"x": rahmen})

        assert abdruck["x"]["von"] != "0"
        assert abdruck["x"]["bis"] != str(len(rahmen) - 1)
        assert not abdruck["x"]["von"].isdigit()

    def test_die_zeilenzahl_bleibt_dabei(self) -> None:
        rahmen = _rahmen("2017-08-16", "2026-08-29")
        abdruck = cli._kerzenabdruck({"x": rahmen})

        assert abdruck["x"]["zeilen"] == str(len(rahmen))

    def test_je_markt_ein_eintrag(self) -> None:
        abdruck = cli._kerzenabdruck(
            {
                "btc": _rahmen("2012-01-01", "2026-08-29"),
                "eth": _rahmen("2017-08-16", "2026-08-29"),
            }
        )

        assert set(abdruck) == {"btc", "eth"}
        assert abdruck["btc"]["von"] != abdruck["eth"]["von"]


class TestDieFormDieWirklichHereinkommt:
    """**Warum es niemand gemerkt hat.** Die Wache aus Befund 300
    (``test_abdruck``) prueft mit einem Rahmen, dessen **Index** die Zeit
    traegt - und fuer diese Form war der alte Griff auf ``rahmen.index``
    richtig. Nur erzeugt sie **kein Aufrufer**: Die Rahmen kommen aus
    ``common_range`` und haben einen Zaehler als Index.

    Gemessen wurde also die Funktion, nicht der Aufruf - dieselbe Luecke wie
    in Befund 493. Deshalb geht dieser Test durch ``common_range`` selbst,
    statt einen Rahmen nachzubauen.
    """

    def test_durch_common_range_gereicht(self) -> None:
        from backtest.portfolio_walkforward import common_range

        frames = common_range(
            {
                "btc": _rahmen("2012-01-01", "2026-08-29"),
                "eth": _rahmen("2017-08-16", "2026-08-29"),
            }
        )
        abdruck = cli._kerzenabdruck(frames)

        for markt, eintrag in abdruck.items():
            assert eintrag["von"].startswith("2017-08-16"), (markt, eintrag)
            assert not eintrag["von"].isdigit(), (markt, eintrag)

    def test_und_diese_rahmen_haben_einen_zaehler_als_index(self) -> None:
        """Die Messung, aus der der Befund kommt: Haetten sie einen Zeitindex,
        waere der alte Griff richtig gewesen."""
        import pandas as pd

        from backtest.portfolio_walkforward import common_range

        frames = common_range({"x": _rahmen("2017-08-16", "2026-08-29")})

        assert not isinstance(frames["x"].index, pd.DatetimeIndex)
        assert frames["x"].index[0] == 0

    def test_beide_formen_werden_bedient(self) -> None:
        """Der Zeitindex bleibt gueltig - ``test_abdruck`` steht auf ihm, und
        seine Zusicherungen sind richtig, nur nicht die, die der Betrieb
        braucht."""
        import pandas as pd

        zeiten = pd.date_range("2020-01-01", periods=10, freq="D", tz="UTC")
        mit_index = pd.DataFrame({"close": range(10)}, index=zeiten)
        mit_spalte = pd.DataFrame({"open_time": zeiten, "close": range(10)})

        a = cli._kerzenabdruck({"x": mit_index})["x"]
        b = cli._kerzenabdruck({"x": mit_spalte})["x"]

        assert a["von"].startswith("2020-01-01")
        assert a == b, (a, b)


class TestZweiReihenZweiAbdruecke:
    """**Die Zusage des Docstrings, und vor 495 war sie umgekehrt falsch.**"""

    def test_gleich_lang_aber_verschoben_ist_nicht_dasselbe(self) -> None:
        """Zwei Rahmen mit **derselben Zeilenzahl** und verschiedenen Spannen.
        Vorher waren ihre Abdruecke gleich - die Wache gegen zwei Messungen in
        einem Lauf verglich eine Zahl mit sich selbst.
        """
        frueh = _rahmen("2017-01-01", "2017-12-31")
        spaet = _rahmen("2019-01-01", "2019-12-31")
        # **Zwei Nicht-Schaltjahre**, und das ist kein Zierrat: Der erste
        # Entwurf nahm 2017 und 2020, und 2020 hat 366 Tage - die Zeilenzahl
        # unterschied sich, also haette der Test auch mit dem alten Abdruck
        # bestanden. Mein Pruefaufbau, nicht der Code.
        assert len(frueh) == len(spaet), "sonst prueft der Test das Falsche"

        assert cli._kerzenabdruck({"x": frueh}) != cli._kerzenabdruck({"x": spaet})

    def test_und_die_zeilenzahl_allein_haette_es_nicht_gemerkt(self) -> None:
        """Die Gegenprobe zur Messung oben: Genau deshalb reicht ``zeilen``
        nicht, und genau deshalb stand das Feld ueberhaupt da."""
        frueh = _rahmen("2017-01-01", "2017-12-31")
        spaet = _rahmen("2019-01-01", "2019-12-31")

        a, b = cli._kerzenabdruck({"x": frueh}), cli._kerzenabdruck({"x": spaet})

        assert a["x"]["zeilen"] == b["x"]["zeilen"]
        assert (a["x"]["von"], a["x"]["bis"]) != (b["x"]["von"], b["x"]["bis"])

    def test_derselbe_rahmen_ergibt_denselben_abdruck(self) -> None:
        """Sonst traennte der Abdruck jedes Stueck vom naechsten - derselbe
        Grund, aus dem ``_codeabdruck`` nicht ueber HEAD hasht."""
        rahmen = _rahmen("2017-08-16", "2026-08-29")

        assert cli._kerzenabdruck({"x": rahmen}) == cli._kerzenabdruck({"x": rahmen})


class TestEinLeererRahmenBrichtNichts:
    """Ein dreistuendiger Lauf darf nicht an der Buchfuehrung scheitern, die
    ihn retten soll - dieselbe Haltung wie ``default=str`` in
    ``zwischenstand.halte_fest``."""

    def test_leer(self) -> None:
        abdruck = cli._kerzenabdruck({"x": pd.DataFrame()})

        assert abdruck["x"]["zeilen"] == "0"
        assert abdruck["x"]["von"] == ""

    def test_ohne_zeitspalte(self) -> None:
        abdruck = cli._kerzenabdruck({"x": pd.DataFrame({"close": [1, 2, 3]})})

        assert abdruck["x"]["zeilen"] == "3"
        assert abdruck["x"]["von"] == ""


class TestWerEineGepflegteZahlNennt:
    """Die Regel, und sie **leitet ihre Grundgesamtheit ab** (Befund 485):
    Kommt ein Befehl dazu, der eine gepflegte Zahl neben seine stellt, faellt
    er hier auf."""

    def _walkforward(self) -> dict[str, str]:
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        befehle = {
            n.name: ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
            and any("app.command" in ast.unparse(d) for d in n.decorator_list)
        }
        return {
            n: q
            for n, q in befehle.items()
            if "run_portfolio_walkforward" in q or "run_walkforward" in q
        }

    def _teuer(self) -> dict[str, str]:
        return {
            n: q
            for n, q in self._walkforward().items()
            if any(r in q for r in GEPFLEGTE_ZAHL)
        }

    def test_es_gibt_solche_befehle(self) -> None:
        """Nichtleere-Zusicherung (Befund 479)."""
        assert self._teuer(), sorted(self._walkforward())

    def test_jeder_nennt_seine_reihe(self) -> None:
        stumm = sorted(
            n for n, q in self._teuer().items() if not (nennt(q) or schneidet(q))
        )

        assert stumm == [], (
            "setzt eine gepflegte Zahl aus 'referenz.py' neben seine eigene "
            f"und sagt nicht, auf welcher Reihe er rechnet (Befund 370): {stumm}"
        )

    def test_der_filter_laesst_wirklich_etwas_aus(self) -> None:
        """Die Gegenprobe: Wuerde der Filter alle 41 greifen, waere die Regel
        darueber keine Auswahl, sondern eine Behauptung ueber den ganzen
        Baum - und 32 davon haben keine gepflegte Zahl daneben."""
        alle, teuer = len(self._walkforward()), len(self._teuer())

        assert 0 < teuer < alle, (teuer, alle)

    def test_die_sechs_aus_dem_befund_sind_dabei(self) -> None:
        """Gepflegt und geprueft: Faellt einer heraus, hat er seine gepflegte
        Zahl verloren - und das gehoert gesehen."""
        teuer = set(self._teuer())

        assert {
            "decke",
            "koernung",
            "nachpruefung",
            "regler",
            "suchbudget",
            "vorratsdecke",
        } <= teuer, sorted(teuer)


class TestDieAltenProtokolleBleibenGezaehlt:
    """**167 Protokolle tragen die hohle Form**, und das ist kein Mangel mehr,
    sondern eine Zahl: Die alten werden nicht umgeschrieben - das waere eine
    Messung nachtraeglich veraendern -, aber sie werden gezaehlt. Wird es
    mehr, schreibt wieder jemand Zeilennummern, und dieser Test ist rot.

    Dieselbe Haltung wie bei den 554 alten Berichten in OFFEN 332: Der
    Bestand bleibt, wie er ist, und seine Groesse steht da.
    """

    def _hohl_und_echt(self) -> tuple[int, int]:
        import json

        hohl = echt = 0
        for datei in sorted((WURZEL / "reports").rglob("*.jsonl")):
            zeilen = datei.read_text(encoding="utf-8").splitlines()
            if not zeilen:
                continue
            try:
                kopf = json.loads(zeilen[0])
            except ValueError:
                continue
            abdruck = kopf.get("kerzen")
            if not isinstance(abdruck, dict):
                continue
            for eintrag in abdruck.values():
                if not isinstance(eintrag, dict):
                    continue
                if str(eintrag.get("von", "")).isdigit():
                    hohl += 1
                else:
                    echt += 1
                break
        return hohl, echt

    def test_nicht_mehr_als_die_gezaehlten(self) -> None:
        hohl, _echt = self._hohl_und_echt()

        assert hohl <= 167, (
            f"{hohl} Protokolle mit Zeilennummern statt Kerzenzeiten - "
            "waren 167 bei Befund 495, also schreibt wieder jemand den "
            "Zaehler statt der Zeit"
        )

    def test_und_es_gibt_schon_echte(self) -> None:
        """Nichtleere-Zusicherung (Befund 479): Ohne ein Protokoll in der
        neuen Form waere die Regel darueber nur eine Behauptung.

        Das erste davon ist ``reports/reibung/2026-11-15_210256.jsonl`` - der
        Rauchtest zu diesem Befund, und zwar **ohne** Trockenlauf gefahren,
        weil genau das Protokoll der Beleg ist.
        """
        _hohl, echt = self._hohl_und_echt()

        assert echt >= 1


@pytest.mark.daten
class TestAmEchtenSpeicher:
    def test_der_abdruck_nennt_die_zulassungsreihe(self) -> None:
        """Rauchtest auf echten Daten: BTC ab 2012, ETH ab 2017 - und der
        Abdruck sagt es, statt 0 und 3300 zu melden."""
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore

        store = CandleStore(get_settings().paths.data_store)
        frames = {
            s: store.read(s, Interval("D"))
            for s in ("BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP")
        }
        if any(f.empty for f in frames.values()):
            pytest.skip(
                "keine Tageskerzen im Speicher dieses Containers - "
                "mit 'cli backfill' zu holen"
            )

        abdruck = cli._kerzenabdruck(frames)

        assert abdruck["BTCUSD_BITSTAMP"]["von"].startswith("2012-")
        assert abdruck["ETHUSD_BITSTAMP"]["von"].startswith("2017-")
        for eintrag in abdruck.values():
            assert not eintrag["von"].isdigit(), eintrag
