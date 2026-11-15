"""Welche Frage braucht die Reihe, welche den Speicher - Befund 490.

Die offene Richtung zu Befund 387 stellt die Frage ausdruecklich:

    Offen ist die Regel: Welche Frage braucht die Reihe, welche den
    Speicher, und woran erkennt man das vor dem Lauf? Bis die Regel steht,
    wird nichts umgestellt - 35 Befehle blind zu schneiden waere dieselbe
    Blindheit, nur in die andere Richtung.

Hier steht die Regel, und sie ist gerechnet.

Was der Schnitt wirklich tut
----------------------------
``datenstand.geschnitten`` kuerzt **nur am oberen Ende** auf ``SERIENENDE``.
Der Anfang kommt nicht von dort: Den besorgt ``common_range`` im
Portfolio-Walk-Forward, und zwar aus dem juengeren Bein. Das steht im
Docstring von ``geschnitten`` und war der erste Irrtum dieses Befundes - ich
hatte ein festes Datumsfenster angenommen und es am laufenden Code widerlegt.

Damit zerfaellt die Frage in zwei:

* **Der Anfang** ist immer geschnitten, wenn der Lauf ueber mehrere Beine
  geht - ``run_portfolio_walkforward`` ruft ``common_range`` als erste
  Handlung. Beim Zulassungskorb (BTC + ETH, Tageskerzen) ergibt das genau die
  Zulassungsreihe: BTC 5355 Balken ab 2012-01-01 werden zu 3301 ab
  2017-08-16, dem Anfang des juengeren Beins.
* **Das obere Ende** schneidet nur, wer ``alle_geschnitten`` ruft.

Woran man es vor dem Lauf erkennt
---------------------------------
**Nicht am Befehl, sondern am Datenstand.** Heute endet der Tagesspeicher
genau auf ``SERIENENDE`` (2026-08-29) und der Feinspeicher vor ``FEINENDE``.
Der Schnitt am oberen Ende ist deshalb **heute an jedem der 41
Walk-Forward-Befehle wirkungslos** - gemessen, nicht vermutet:

    Vorgabekorb   common_range(alle_geschnitten(x)) == common_range(x)
    ein Markt     alle_geschnitten(x) == x          (5355 bleibt 5355)

Damit ist die Liste der 34 Befehle ohne Schnitt keine Liste von 34 Fehlern,
und das ist jetzt gerechnet statt begruendet.

**Wirksam wird er beim naechsten Laden.** Der Backfill, den die Empfehlung
nennt, laedt bis heute. Danach liegt das Speicherende ueber ``SERIENENDE``,
und ein Befehl ohne Schnitt rechnet auf einer laengeren Reihe als die
gepflegten Zahlen, gegen die er verglichen wird. Das ist die Lage aus Befund
474, nur am anderen Ende.

Wo es teuer ist
---------------
Die offene Richtung nennt den Anhaltspunkt selbst: *"Teuer wird es da, wo
eine gepflegte Zahl aus ``referenz.py`` danebensteht oder eine
unwiderrufliche Entscheidung daran haengt."*

Unwiderruflich ist genau eines: **eine Versuchsbuchung.** Der Zaehler faellt
nicht, und der gebuchte Sharpe je Trade geht in das Verzeichnis, aus dem
``research/streuung.py`` die Streuung ueber die Versuche schaetzt. Deshalb
schneiden seit 490 die vier buchenden Walk-Forward-Befehle - ``korb``,
``machbarkeit``, ``adaptiv``, ``verbund`` -, und das ist heute ein
wirkungsloser Handgriff und nach dem naechsten Backfill ein entscheidender.

**Umgestellt wurde nur das.** Der erste Versuch ersetzte alle 24 Stellen auf
einmal; das ist genau die Blindheit, vor der die offene Richtung warnt, und
wurde zurueckgenommen.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.datenstand import SERIENENDE
from tests.schnittwege import schneidet
from tests.zaehlerwege import zaehlende_befehle

WURZEL = Path(__file__).resolve().parents[1]

#: Die Aufrufe, die einen Walk-Forward starten.
WALKFORWARD: tuple[str, ...] = ("run_portfolio_walkforward", "run_walkforward")


def _befehle() -> dict[str, str]:
    baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
    return {
        n.name: ast.unparse(n)
        for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef)
        and any("app.command" in ast.unparse(d) for d in n.decorator_list)
    }


def walkforwardbefehle() -> dict[str, str]:
    return {
        name: q
        for name, q in _befehle().items()
        if any(w in q for w in WALKFORWARD)
    }


class TestDerMelderTaugt:
    def test_es_gibt_walkforwardbefehle(self) -> None:
        """Nichtleere-Zusicherung (Befund 479)."""
        assert len(walkforwardbefehle()) >= 30, sorted(walkforwardbefehle())

    def test_und_buchende_darunter(self) -> None:
        bucht = zaehlende_befehle()
        wf = set(walkforwardbefehle())

        assert bucht & wf, (bucht, sorted(wf))


class TestJederBuchendeLaufSchneidet:
    """**Die Regel.** Kein Befehl, der einen Versuch bucht, rechnet am oberen
    Ende auf mehr als der Zulassungsreihe."""

    def test_alle(self) -> None:
        """**Geprueft wird der Schnitt, nicht ein Funktionsname** (Befund
        491). Diese Regel suchte ``alle_geschnitten`` und fiel, als die
        Schneider auf ``nach_intervall`` umgestellt wurden - dieselbe Bauart,
        gegen die sie selbst gebaut ist.
        """
        wf = walkforwardbefehle()
        offen = [
            name
            for name in sorted(zaehlende_befehle() & set(wf))
            if not schneidet(wf[name])
        ]

        assert offen == [], (
            "bucht einen Versuch und schneidet nicht auf die Zulassungsreihe - "
            f"die Buchung ist unwiderruflich (Befund 490): {offen}"
        )

    def test_und_es_sind_die_vier_gemessenen(self) -> None:
        """Gepflegt und geprueft: Kommt ein fuenfter buchender Lauf dazu,
        faellt er in der Regel darueber auf."""
        wf = walkforwardbefehle()

        assert zaehlende_befehle() & set(wf) == {
            "adaptiv",
            "korb",
            "machbarkeit",
            "verbund",
        }

    def test_die_regel_leitet_ihre_grundgesamtheit_ab(self) -> None:
        """Der Unterschied zu Befund 484 und 485: keine gepflegte Liste von
        Ausnahmen, die verstummen koennte - die Menge kommt aus
        ``zaehlende_befehle()``.

        **Nicht an der Datei gesucht.** Der erste Entwurf pruefte, dass das
        Wort "Ausnahme" in dieser Datei nicht vorkommt - und ist an seiner
        eigenen Zusicherung gescheitert, weil das Wort dort steht. Dieselbe
        Selbstwiderlegung wie bei GELESEN in Befund 295.
        """
        baum = ast.parse((WURZEL / "tests/test_reihenschnitt.py").read_text("utf-8"))
        regel = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "test_alle"
        )

        assert "zaehlende_befehle()" in regel
        assert "korb" not in regel, "die Regel nennt keinen Befehl beim Namen"


class TestDerSchnittKuerztNurAmOberenEnde:
    """Der erste Irrtum dieses Befundes, als Zusicherung."""

    def _rahmen(self, bis: str):
        import pandas as pd

        zeiten = pd.date_range("2016-01-01", bis, freq="D", tz="UTC")
        return pd.DataFrame({"open_time": zeiten, "close": range(len(zeiten))})

    def test_der_anfang_bleibt_stehen(self) -> None:
        """``geschnitten`` holt den Anfang **nicht** - der kommt aus dem
        juengeren Bein ueber ``common_range``. Wer hier ein festes Fenster
        erwartet, irrt sich (und das habe ich getan)."""
        from research.datenstand import geschnitten

        rahmen = self._rahmen("2016-06-30")
        kurz = geschnitten(rahmen)

        assert kurz["open_time"].min().date().isoformat() == "2016-01-01"
        assert len(kurz) == len(rahmen)

    def test_das_ende_wird_gekuerzt(self) -> None:
        from research.datenstand import geschnitten

        spaeter = self._rahmen("2027-06-30")
        kurz = geschnitten(spaeter)

        assert len(kurz) < len(spaeter)
        assert kurz["open_time"].max().date() <= SERIENENDE

    def test_und_zweimal_schneiden_ist_dasselbe(self) -> None:
        """Der Docstring von ``alle_geschnitten`` sagt es - hier steht es als
        Messung."""
        from research.datenstand import geschnitten

        spaeter = self._rahmen("2027-06-30")

        assert len(geschnitten(geschnitten(spaeter))) == len(geschnitten(spaeter))


class TestDieEngineSchneidetDenAnfangSelbst:
    def test_common_range_steht_im_walkforward(self) -> None:
        """Deshalb ist der Anfang beim Korb immer die Zulassungsreihe - und
        deshalb war an den 34 Befehlen nichts zu reparieren."""
        quelle = (
            WURZEL / "backtest/portfolio_walkforward.py"
        ).read_text(encoding="utf-8")
        baum = ast.parse(quelle)
        fn = next(
            n
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
            and n.name == "run_portfolio_walkforward"
        )

        assert "common_range(frames)" in ast.unparse(fn)

    def test_und_kuerzt_das_aeltere_bein(self) -> None:
        import pandas as pd

        from backtest.portfolio_walkforward import common_range

        alt = pd.DataFrame(
            {"open_time": pd.date_range("2012-01-01", "2020-12-31", freq="D", tz="UTC")}
        )
        jung = pd.DataFrame(
            {"open_time": pd.date_range("2017-08-16", "2020-12-31", freq="D", tz="UTC")}
        )
        aus = common_range({"alt": alt, "jung": jung})

        assert len(aus["alt"]) == len(aus["jung"]) == len(jung)
        assert aus["alt"]["open_time"].min().date().isoformat() == "2017-08-16"


@pytest.mark.daten
class TestHeuteIstDerSchnittWirkungslos:
    """Am echten Speicher gemessen - das ist die Zahl, auf der die Regel
    steht."""

    def _korb(self):
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore

        store = CandleStore(get_settings().paths.data_store)
        korb = {
            x: store.read(x, Interval("D"))
            for x in ("BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP")
        }
        if any(v.empty for v in korb.values()):
            pytest.skip("Tagesreihen fehlen")
        return korb

    def test_der_tagesspeicher_endet_auf_serienende(self) -> None:
        """Kippt das, wird der Schnitt wirksam - und dieser Test rot, damit
        jemand hinsieht, statt es beim naechsten Lauf zu merken."""
        korb = self._korb()

        for name, rahmen in korb.items():
            assert rahmen["open_time"].max().date() <= SERIENENDE, name

    def test_beim_vorgabekorb_ist_er_wirkungslos(self) -> None:
        from backtest.portfolio_walkforward import common_range
        from research.datenstand import alle_geschnitten

        korb = self._korb()
        ohne = common_range(korb)
        mit = common_range(alle_geschnitten(korb))

        assert {k: len(v) for k, v in ohne.items()} == {
            k: len(v) for k, v in mit.items()
        }

    def test_und_die_engine_macht_aus_5355_balken_3301(self) -> None:
        """Der Anfang kommt aus dem juengeren Bein - gemessen am Bestand."""
        from backtest.portfolio_walkforward import common_range

        korb = self._korb()
        roh = {k: len(v) for k, v in korb.items()}
        zu = {k: len(v) for k, v in common_range(korb).items()}

        assert roh["BTCUSD_BITSTAMP"] > zu["BTCUSD_BITSTAMP"]
        assert len(set(zu.values())) == 1
