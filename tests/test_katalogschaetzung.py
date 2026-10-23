"""Die dritte Schaetzung entscheidet, und sie geht gegen meine zweite - 392.

Befund 391 liess zwei Lesarten offen:

- Entweder sind die 203 Versuche keine 203 unabhaengigen Ideenziehungen (192
  stehen ohne Herkunft im Grundstock, 234/282),
- oder die acht gebuchten Versuche sind nach Vielfalt ausgesucht.

Entschieden wird das vom **Vorratskatalog** - der Menge, die niemand nach
Vielfalt zusammengestellt hat. Und seine Protokolle tragen ``n_eff`` je Regel,
also die wirksame Stichprobe aus dem Gate selbst statt eines geschaetzten
Anteils.

Gemessen am Tageskatalog, Spot, Versuchsstand 203:

    Quelle                        Mittel   Ideenstreuung
    Rueckrechnung (390)                0*         0,0906
    acht gebuchte Versuche (391)  +0,0324         0,1669
    18 Katalogregeln              +0,1823         0,0670
    19 Regeln, sechs Stuecke      +0,1900         0,0589
    Nullstreuung                                  0,0913

(* eine Annahme, kein gemessenes Mittel.)

**Zwei von drei liegen unter der Null**, und die dritte ist die ausgesuchte:
hohes Mittel bei enger Streuung im Katalog, niedriges Mittel bei weiter
Streuung unter den gebuchten. Damit war meine Einschraenkung aus 391 zu
grosszuegig gegenueber der Suche.
"""

from __future__ import annotations

import inspect
import pathlib

import pytest

from research.wettrennen import aus_dem_katalog, nullstreuung
from research.zwischenstand import lies, zusammen

#: Gemessen, siehe Kopf.
EINE_DATEI = pathlib.Path("reports/vorratsdecke/2026-09-19_013439.jsonl")
NULL = nullstreuung(121)


def _stuecke() -> list[pathlib.Path]:
    """Die sechs Stuecke desselben Katalogs - am Kopf erkannt, nicht am Namen."""
    return sorted(
        p
        for p in pathlib.Path("reports/vorratsdecke").glob("*.jsonl")
        if str(lies(p)[0].get("stueck", "")).endswith("/6")
    )


class TestDieEineDatei:
    def test_achtzehn_regeln(self) -> None:
        _kopf, messungen = lies(EINE_DATEI)
        s = aus_dem_katalog(messungen)

        assert s is not None
        assert s.anzahl == 18
        assert s.mittel == pytest.approx(0.1823, abs=0.0005)
        assert s.streuung == pytest.approx(0.0670, abs=0.0005)

    def test_und_sie_liegt_unter_der_null(self) -> None:
        _kopf, messungen = lies(EINE_DATEI)
        s = aus_dem_katalog(messungen)

        assert s.streuung < NULL

    def test_der_kopf_nennt_seinen_betriebspunkt(self) -> None:
        """Ein Bericht ohne Betriebspunkt gilt nicht (Befund 242/309)."""
        kopf, _ = lies(EINE_DATEI)

        assert kopf["betriebspunkt"] == "Spot"
        assert kopf["intervall"] == "1d"
        assert kopf["versuchsstand"] == 203


class TestDieSechsStueckeZusammengelegt:
    def test_sie_gehoeren_zusammen(self) -> None:
        """``zusammen`` vergleicht die Koepfe Feld fuer Feld (Befund 300) -
        gleicher Katalog- und Codeabdruck, sonst wirft es ``Uneinig``."""
        kopf, _zeilen = zusammen(_stuecke())

        assert kopf["katalog"]
        assert kopf["code"]
        assert kopf["betriebspunkt"] == "Spot"

    def test_neunzehn_regeln_und_derselbe_schluss(self) -> None:
        _kopf, zeilen = zusammen(_stuecke())
        s = aus_dem_katalog(zeilen)

        assert s.anzahl == 19
        assert s.mittel == pytest.approx(0.1900, abs=0.0005)
        assert s.streuung == pytest.approx(0.0589, abs=0.0005)
        assert s.streuung < NULL

    def test_dieselben_regelnamen_wie_die_einzeldatei(self) -> None:
        _k, zeilen = zusammen(_stuecke())
        _k2, einzeln = lies(EINE_DATEI)

        assert sorted(z["regel"] for z in zeilen) == sorted(
            z["regel"] for z in einzeln
        )


class TestWelcheZeilenZaehlen:
    """Vier Ergebnisse im Protokoll, und nur eines ist eine Ideenziehung."""

    def test_nur_gemessene(self) -> None:
        import collections

        _kopf, messungen = lies(EINE_DATEI)
        arten = collections.Counter(z.get("ergebnis") for z in messungen)

        assert arten["gemessen"] == 18
        assert arten["identisch"] == 6
        assert arten["kein Kandidat"] == 5
        assert arten["keine Latte"] == 1

    def test_doppelgaenger_sind_keine_zweite_ziehung(self) -> None:
        s = aus_dem_katalog(
            [
                {"ergebnis": "identisch", "regel": "a"},
                {"ergebnis": "identisch", "regel": "a"},
            ]
        )

        assert s is None

    def test_mit_den_fehlschlaegen_als_null_verschwindet_die_zahl(self) -> None:
        """Die Gegenprobe: Nimmt man die fuenf Zeilen ohne Kandidat als Guete 0
        dazu, ist die Streuung **nicht mehr nachweisbar**. Die Richtung bleibt,
        nur die Zahl verschwindet - und 'nicht nachweisbar' ist etwas anderes
        als 'null'."""
        from research.wettrennen import aus_der_akte

        _kopf, messungen = lies(EINE_DATEI)
        gemessen = [z for z in messungen if z["ergebnis"] == "gemessen"]
        ohne = [z for z in messungen if z["ergebnis"] == "kein Kandidat"]
        klein = min(z["n_eff"] for z in gemessen)
        punkte = [(z["sr_je_trade"], z["n_eff"]) for z in gemessen]
        punkte += [(0.0, klein)] * len(ohne)

        s = aus_der_akte(punkte)

        assert s is not None
        assert s.anzahl == 23
        assert s.streuung is None

    def test_eine_zeile_ohne_n_eff_fliegt_heraus(self) -> None:
        s = aus_dem_katalog(
            [
                {"ergebnis": "gemessen", "sr_je_trade": 0.2, "n_eff": 100},
                {"ergebnis": "gemessen", "sr_je_trade": 0.1},
                {"ergebnis": "gemessen", "sr_je_trade": 0.3, "n_eff": 120},
            ]
        )

        assert s.anzahl == 2


class TestDieDreiSchaetzerStehenNebeneinander:
    """Die Lehre aus 351 - und sie war in fuenf Durchgaengen hintereinander
    der Fund."""

    def test_rennen_ruft_die_katalogschaetzung(self) -> None:
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "aus_dem_katalog(zeilen)" in quelle
        assert "protokoll_zusammen" in quelle

    def test_es_nennt_die_quelldateien(self) -> None:
        """Ohne sie waere die Zahl nicht nachzuschlagen."""
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "Quelle: " in quelle

    def test_und_laesst_berichte_ohne_betriebspunkt_aus(self) -> None:
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert 'kopf_p.get("betriebspunkt")' in quelle
        assert "242/309" in quelle

    def test_der_schluss_nennt_meinen_eigenen_fehler(self) -> None:
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "zu grosszuegig" in quelle
        assert "Befund 392" in quelle


class TestWasImRegisterSteht:
    def test_der_eintrag_traegt_alle_vier_zahlen(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 392)

        for zahl in ("0,0906", "0,1669", "0,0670", "0,0589", "0,0913"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_benennt_die_eigene_korrektur(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 392)

        assert "zu grosszuegig" in eintrag.ergebnis
        assert "391" in eintrag.ergebnis

    def test_und_die_gegenprobe(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 392)

        assert "nicht mehr nachweisbar" in eintrag.ergebnis
        assert "Doppelgaenger" in eintrag.ergebnis

    def test_und_das_offene(self) -> None:
        """Alle drei Schaetzer sind erst bei 4 bis 8 Ziehungen mit dem
        Bestwert vereinbar - das bleibt ungeklaert."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 392)

        assert "4 bis " in eintrag.ergebnis
        assert "nicht bei 203" in eintrag.ergebnis

    def test_und_391_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 391).zuletzt == 392

    def test_das_budget_nennt_die_dreierzahl(self) -> None:
        from research.stand import Suchbudget

        text = Suchbudget.__doc__ or ""

        assert "0,0589" in text
        assert "0,1669" in text
        assert "ausgesuchte Menge" in text

    def test_der_statusschirm_auch(self) -> None:
        from research.stand import Lage

        quelle = inspect.getsource(Lage)

        assert "0,0589" in quelle
        assert "zieht nicht nach" in quelle
        assert "ist strittig" not in quelle, "die 391er Fassung ist ersetzt"
