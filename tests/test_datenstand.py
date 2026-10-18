"""Die Zulassungsreihe ist aufgeschrieben und haengt an ihren Zahlen - Befund 363.

Fuenfzehn Tests fielen, als der Speicher frisch nachgeladen wurde, und keiner
sagte "andere Reihe". Dieses Modul sorgt dafuer, dass einer es sagt.

Zwei Arten von Pruefung stehen hier, und sie sind absichtlich getrennt:

**Ohne Daten** - die Angaben in ``datenstand.py`` muessen untereinander und mit
den gepflegten Zahlen anderer Module aufgehen. Das laeuft in jedem Klon, auch im
frischen, und haelt die vier Quellen zusammen, aus denen die Reihe erschlossen
ist. Gehen sie auseinander, war eine davon falsch.

**Mit Daten** (``daten``-markiert) - der vorliegende Speicher gegen die Reihe.
Dieser Test faellt im frischen Klon, und er soll es: Seit Befund 151 gilt, dass
fehlende Daten auffallen muessen. Neu ist nur, dass er **sagt, was fehlt**,
statt eine Zahl zu nennen, die um eins abweicht.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from research.datenstand import (
    GEMEINSAME_TAGE,
    INTERVALL,
    REIHEN,
    SERIENENDE,
    VORLAUF_TAGE,
    aelteres_bein,
    befehle,
    fehlt,
    geschnitten,
    jueneres_bein,
)


class TestDieAngabenGehenUntereinanderAuf:
    """Die Reihe ist aus vier gepflegten Zahlen erschlossen. Hier wird
    geprueft, dass alle vier dieselbe Reihe beschreiben."""

    @pytest.mark.parametrize("reihe", REIHEN, ids=lambda r: r.symbol)
    def test_die_balkenzahl_folgt_aus_den_grenzen(self, reihe) -> None:
        assert reihe.laenge_stimmt(), (
            f"{reihe.symbol}: {reihe.balken} Balken passen nicht zu "
            f"{reihe.von}..{SERIENENDE}"
        )

    def test_die_gemeinsame_spanne_folgt_aus_dem_jueneren_bein(self) -> None:
        assert (SERIENENDE - jueneres_bein().von).days == GEMEINSAME_TAGE

    def test_der_vorlauf_ist_der_abstand_der_beiden_anfaenge(self) -> None:
        assert (jueneres_bein().von - aelteres_bein().von).days == VORLAUF_TAGE

    def test_eth_setzt_den_anfang_und_btc_reicht_weiter_zurueck(self) -> None:
        """Die Richtung, nicht nur der Betrag - ``test_datenbedarf.py`` prueft
        sie als ``gesetzt_von`` und wuerde es sonst allein tragen."""
        assert jueneres_bein().symbol == "ETHUSD_BITSTAMP"
        assert aelteres_bein().symbol == "BTCUSD_BITSTAMP"


class TestUndMitDenGepflegtenZahlenAnderswo:
    def test_die_spanne_ist_die_der_aussichtsrechnung(self) -> None:
        """``referenz.AUSSICHT.historie_tage`` ist dieselbe Groesse. Zwei
        Stellen, eine Zahl - und ohne diesen Test zwei, die auseinanderlaufen
        koennen (Befund 130)."""
        from research.referenz import AUSSICHT

        assert AUSSICHT.historie_tage == GEMEINSAME_TAGE

    def test_der_vorlauf_ist_der_aus_dem_datenbedarf(self) -> None:
        """2054 steht in ``test_datenbedarf.py`` als ``rueckwaerts_tage``. Von
        dort stammt der BTC-Anfang, also muss die Zahl hier dieselbe sein."""
        from pathlib import Path

        quelle = Path("tests/test_datenbedarf.py").read_text(encoding="utf-8")

        assert f"rueckwaerts_tage == {VORLAUF_TAGE}" in quelle

    def test_die_balkenzahl_ist_die_aus_dem_abgleich(self) -> None:
        """5355 Balken hat Befund 360 im Register gemeldet - die Gegenprobe von
        ausserhalb, aus einem Lauf, der nichts mit diesem Modul zu tun hat."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 360)

        assert "5355" in eintrag.ergebnis
        assert aelteres_bein().balken == 5355

    def test_zugelassen_wird_auf_tageskerzen(self) -> None:
        """Befund 213: Dort stehen alle elf Gates. Auf 15 Minuten nicht."""
        assert INTERVALL == "D"


class TestDieBefehleStellenGenauDieseReiheWiederHer:
    def test_je_bein_ein_befehl_und_einer_zum_raeumen(self) -> None:
        assert len(befehle()) == len(REIHEN) + 1

    def test_geraeumt_wird_zuerst(self) -> None:
        """Ein Nachladen macht eine zu lange Reihe nicht kuerzer. Stuende das
        Raeumen hinten, loeschte es das Geladene."""
        zeilen = befehle()

        assert zeilen[0].startswith("rm -rf ")
        assert all(r.symbol in zeilen[0] for r in REIHEN)

    @pytest.mark.parametrize("reihe", REIHEN, ids=lambda r: r.symbol)
    def test_der_befehl_nennt_beide_grenzen(self, reihe) -> None:
        """Ohne ``--bis`` laedt der Befehl bis heute, und heute ist jeden Tag
        ein anderer Tag - genau der Fehler, den dieses Modul behebt."""
        zeile = next(b for b in befehle() if reihe.symbol in b and "referenz" in b)

        assert f"--von {reihe.von.isoformat()}" in zeile
        assert "--bis " in zeile

    def test_die_obere_grenze_ist_ausschliessend(self) -> None:
        """**Gemessen, nicht aus der Signatur gelesen.** Mit ``--bis`` auf dem
        Serienende endet die Reihe einen Tag davor; der Befehl muss also einen
        Tag weiter zeigen. Ohne diese Zusicherung baut die Anleitung eine Reihe
        mit einem Balken zu wenig - und dann stimmt keine der Zahlen, um die es
        hier geht.
        """
        nach = (SERIENENDE + timedelta(days=1)).isoformat()

        for zeile in (b for b in befehle() if "referenz" in b):
            assert f"--bis {nach}" in zeile
            assert f"--bis {SERIENENDE.isoformat()}" not in zeile

    def test_es_ist_referenz_und_nicht_backfill(self) -> None:
        """``cli backfill`` holt bei Bybit, und Bybit ist hier gesperrt. Die
        Regionssperre wird nicht umgangen, sondern die Quelle benannt, die
        offen ist."""
        ladebefehle = [b for b in befehle() if b.startswith("python")]

        assert ladebefehle
        assert all("cli referenz" in b for b in ladebefehle)
        assert not any("cli backfill" in b for b in befehle())


class TestGeprueftWirdEnthaltenUndNichtGleichen:
    """**Die Berichtigung.** Zuerst forderte dieses Modul, der Speicher *sei*
    die Zulassungsreihe. Darauf festgenagelt fielen drei Tests, die vorher
    liefen: ``gegenprobe`` und ``randschnitt`` pruefen am Datenrand und
    verlangen eine angefangene letzte Tageskerze, also einen Speicher bis
    heute. Beides zugleich geht nicht - also wird hier nur geprueft, ob sich
    die Reihe aus dem Speicher **schneiden** laesst.
    """

    def test_genau_die_reihe_genuegt(self) -> None:
        vorhanden = {r.symbol: (r.von, SERIENENDE, r.balken) for r in REIHEN}

        assert fehlt(vorhanden) == ()

    def test_ein_laengerer_speicher_genuegt_auch(self) -> None:
        """Der Normalfall auf einer Maschine, die handelt: Die Reihe laeuft
        weiter, und die Zahlen des Katalogs sind trotzdem nachrechenbar."""
        vorhanden = {
            r.symbol: (date(2011, 8, 18), date(2026, 10, 18), r.balken + 200)
            for r in REIHEN
        }

        assert fehlt(vorhanden) == ()

    def test_ein_fehlendes_bein_wird_gesagt(self) -> None:
        vorhanden = {REIHEN[0].symbol: (REIHEN[0].von, SERIENENDE, REIHEN[0].balken)}

        saetze = fehlt(vorhanden)

        assert len(saetze) == 1
        assert "fehlt im Speicher" in saetze[0]

    def test_ein_zu_spaeter_anfang_wird_gesagt(self) -> None:
        """Der Fall aus dem ersten Anlauf dieses Containers: nachgeladen ab
        2020-03-30, und damit 107 statt 156 Trades."""
        vorhanden = {
            r.symbol: (date(2020, 3, 30), SERIENENDE, r.balken) for r in REIHEN
        }

        saetze = fehlt(vorhanden)

        assert len(saetze) == 2
        assert all("beginnt erst 2020-03-30" in s for s in saetze)

    def test_ein_zu_frueher_schluss_wird_gesagt(self) -> None:
        vorhanden = {
            r.symbol: (r.von, date(2026, 6, 30), r.balken) for r in REIHEN
        }

        saetze = fehlt(vorhanden)

        assert all("endet schon 2026-06-30" in s for s in saetze)
        assert all("gebraucht bis 2026-08-29" in s for s in saetze)

    def test_eine_luecke_faellt_nur_bei_genauen_grenzen_auf(self) -> None:
        """Laeuft der Speicher weiter, sagt die Balkenzahl nichts ueber
        Luecken im Inneren - zwei Meldungen fuer eine Ursache schicken den
        Leser auf die falsche Suche."""
        genau = {r.symbol: (r.von, SERIENENDE, r.balken - 3) for r in REIHEN}
        laenger = {
            r.symbol: (r.von, date(2026, 10, 18), r.balken - 3) for r in REIHEN
        }

        assert all("Luecke" in s for s in fehlt(genau))
        assert fehlt(laenger) == ()


class TestDerSchnittMachtDieZahlenNachrechenbar:
    """Der eine Handgriff: Wer eine gepflegte Zahl prueft, nimmt die Reihe, auf
    der sie gemessen ist - nicht den Speicherstand von heute."""

    @staticmethod
    def _rahmen(von: str, bis: str):
        import pandas as pd

        return pd.DataFrame(
            {"open_time": pd.date_range(von, bis, freq="1D", tz="UTC")}
        )

    def test_was_darueber_liegt_faellt_weg(self) -> None:
        rahmen = self._rahmen("2017-08-16", "2026-10-18")

        gekuerzt = geschnitten(rahmen)

        assert gekuerzt["open_time"].max().date() == SERIENENDE
        assert len(gekuerzt) == len(rahmen) - 50

    def test_die_spanne_ist_danach_genau_die_gepflegte(self) -> None:
        """Nicht "etwa 3300" - genau. Die Toleranz von 40 Tagen in
        ``test_referenzdaten.py`` hat den Unterschied knapp nicht mehr
        gefangen."""
        gekuerzt = geschnitten(self._rahmen("2017-08-16", "2026-10-18"))
        zeiten = gekuerzt["open_time"]

        assert (zeiten.iloc[-1] - zeiten.iloc[0]).days == GEMEINSAME_TAGE

    def test_am_anfang_wird_nicht_geschnitten(self) -> None:
        """Den gemeinsamen Anfang setzt ``common_range``. Hier zu schneiden
        wuerde eine zu kurze Reihe stillschweigend durchlassen - melden soll
        das ``fehlt``."""
        rahmen = self._rahmen("2020-03-30", "2026-08-29")

        assert geschnitten(rahmen)["open_time"].min().date() == date(2020, 3, 30)

    def test_eine_kuerzere_reihe_bleibt_wie_sie_ist(self) -> None:
        rahmen = self._rahmen("2017-08-16", "2026-06-30")

        assert len(geschnitten(rahmen)) == len(rahmen)

    def test_ein_leerer_rahmen_bleibt_leer(self) -> None:
        import pandas as pd

        assert geschnitten(pd.DataFrame()).empty

    def test_der_musterfall_ruft_ihn_wirklich(self) -> None:
        """Ein Bauteil, das niemand ruft, ist in diesem Projekt schon mehrfach
        aufgefallen (Befund 240)."""
        from pathlib import Path

        quelle = Path("tests/test_referenzdaten.py").read_text(encoding="utf-8")

        assert "geschnitten(f)" in quelle


class TestDerBerichtskopfSagtEsAuch:
    """Die Bestandszeile sagte, **wie viel** da ist. Eine gleich lange, anders
    begrenzte Reihe sah darin genauso aus - und genau daran sind fuenfzehn
    Tests gefallen."""

    class _Speicher:
        """Ein Speicher-Doppel, das genau die uebergebenen Grenzen liefert."""

        def __init__(self, stand: dict) -> None:
            self.stand = stand

        def read(self, symbol: str, intervall):
            import pandas as pd

            grenzen = self.stand.get(symbol)
            if grenzen is None or intervall.value != INTERVALL:
                return pd.DataFrame()
            von, bis, balken = grenzen
            zeiten = [pd.Timestamp(von, tz="UTC")] * (balken - 1)
            zeiten.append(pd.Timestamp(bis, tz="UTC"))
            return pd.DataFrame({"open_time": zeiten})

    def test_eine_reihe_die_sie_enthaelt_wird_benannt(self) -> None:
        from cli import _kerzenbestand

        speicher = self._Speicher(
            {r.symbol: (r.von, date(2026, 10, 18), r.balken) for r in REIHEN}
        )

        assert "enthaelt die Zulassungsreihe" in _kerzenbestand(speicher)

    def test_eine_zu_kurze_reihe_wird_als_solche_benannt(self) -> None:
        from cli import _kerzenbestand

        speicher = self._Speicher(
            {r.symbol: (date(2020, 3, 30), SERIENENDE, r.balken) for r in REIHEN}
        )

        zeile = _kerzenbestand(speicher)

        assert "ohne die Zulassungsreihe" in zeile
        assert "beginnt erst 2020-03-30" in zeile

    def test_ohne_kerzen_bleibt_es_bei_dem_alten_satz(self) -> None:
        """``test_referenzdaten.py`` prueft gegen genau diese Zeichenkette."""
        from cli import _kerzenbestand

        assert _kerzenbestand(self._Speicher({})) == "keine Kerzen"


@pytest.mark.daten
def test_der_speicher_enthaelt_die_zulassungsreihe() -> None:
    """Der eine Test, der im frischen Klon sagt, **was** fehlt.

    Er faellt dort, und das ist die Absicht (Befund 151): Ohne Kerzen gibt es
    keine Messung, und das soll auffallen. Vorher fiel es als "157 statt 156"
    auf, in fuenfzehn Tests gleichzeitig.
    """
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore

    speicher = CandleStore(get_settings().paths.data_store)
    vorhanden = {}
    for reihe in REIHEN:
        rahmen = speicher.read(reihe.symbol, Interval(INTERVALL))
        if rahmen is None or rahmen.empty:
            continue
        zeiten = rahmen["open_time"]
        vorhanden[reihe.symbol] = (
            zeiten.min().date(), zeiten.max().date(), len(rahmen),
        )

    saetze = fehlt(vorhanden)
    assert not saetze, (
        "Aus diesem Speicher laesst sich die Reihe nicht schneiden, auf der "
        "die Zahlen dieses Projekts gemessen sind:\n  " + "\n  ".join(saetze)
        + "\n\nNachladen mit:\n  " + "\n  ".join(befehle())
    )
