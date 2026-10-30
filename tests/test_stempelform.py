"""Der Stempel meldete Drift, wo nur anders geschnitten war - Befund 428.

``Reihenstempel`` heisst "Form und Inhalt der Reihe" und traegt
``balken``/``von``/``bis``. ``abweichungen`` hat die drei nie angesehen und
allein die Abdruecke verglichen. Ein Rahmen mit den **richtigen Kerzen im
falschen Fenster** wurde deshalb als Datenaenderung gemeldet.

Gemessen an genau dem Fall, der es ausgeloest hat: Nach dem Wiederaufbau des
Containers habe ich die Zulassungsreihe neu geholt und mit
``alle_geschnitten`` geprueft - das kuerzt **nur am oberen Ende** (so steht es
in seinem Docstring). BTC kam damit mit 5355 statt 3301 Balken, der Abdruck
wich ab, und ich habe eine Datendrift berichtet, die es nicht gab.

Scharf wird es durch ``warum``: Es riet *"Erst den Stempel nachziehen"* - also
den korrekten Pin mit dem Abdruck des falschen Fensters zu ueberschreiben. Das
haette den einzigen Beleg der Reihe geloescht, auf der die Zahlen stehen
(Befund 364).
"""

from __future__ import annotations

import pandas as pd
import pytest

from research.datenstempel import (
    NICHT_GESCHNITTEN,
    SERIE,
    Reihenstempel,
    fingerabdruck,
    stempel,
    warum,
)


def _reihe(
    schluss: list[float], *, von: str = "2020-01-01"
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.date_range(von, periods=len(schluss), tz="UTC"),
            "open": schluss,
            "high": [x + 1 for x in schluss],
            "low": [x - 1 for x in schluss],
            "close": schluss,
            "volume": [10.0] * len(schluss),
        }
    )


@pytest.fixture
def drei() -> Reihenstempel:
    """Ein Stempel auf drei Balken ab 2020-01-01."""
    return stempel({"X": _reihe([1.0, 2.0, 3.0])})


class TestDieFormKommtVorDemAbdruck:
    def test_gleiche_form_leere_meldung(self, drei) -> None:
        """``""`` heisst hier **vergleichbar**, nicht unbekannt."""
        assert drei.form(_reihe([1.0, 2.0, 3.0])) == ""

    def test_mehr_balken_wird_als_schnitt_gemeldet(self, drei) -> None:
        meldung = drei.form(_reihe([1.0, 2.0, 3.0, 4.0]))

        assert NICHT_GESCHNITTEN in meldung
        assert "4 Balken" in meldung and "Stempel 3" in meldung

    def test_anderer_anfang_auch(self, drei) -> None:
        """Der Fall aus dem Befund: gleiche Zahl, anderes Fenster."""
        meldung = drei.form(_reihe([1.0, 2.0, 3.0], von="2019-01-01"))

        assert NICHT_GESCHNITTEN in meldung
        assert "2019-01-01" in meldung

    def test_ohne_kerzen_sagt_es(self, drei) -> None:
        assert drei.form(pd.DataFrame(columns=["open_time"])) == "ohne Kerzen"
        assert drei.form(pd.DataFrame({"close": [1.0]})) == "ohne Kerzen"
        assert drei.form(None) == "ohne Kerzen"

    def test_bei_falscher_form_kein_abdruckpfeil(self, drei) -> None:
        """Der Kern. Der Abdruck eines anderen Fensters ist kein Beleg ueber
        die Daten - also wird er nicht verglichen und nicht gezeigt."""
        anders = drei.abweichungen({"X": _reihe([1.0, 2.0, 3.0, 4.0])})

        assert len(anders) == 1
        assert NICHT_GESCHNITTEN in anders[0]
        assert "->" not in anders[0]


class TestEchteDriftWirdWeiterGemeldet:
    """Die Gegenprobe. Eine Formpruefung, die Drift verschluckt, waere
    schlimmer als keine."""

    def test_gleiche_form_andere_zahlen(self, drei) -> None:
        anders = drei.abweichungen({"X": _reihe([1.0, 2.0, 3.5])})

        assert len(anders) == 1
        assert "->" in anders[0]
        assert NICHT_GESCHNITTEN not in anders[0]

    def test_und_das_ist_kein_schnittfehler(self, drei) -> None:
        assert not drei.nur_anders_geschnitten({"X": _reihe([1.0, 2.0, 3.5])})

    def test_ein_fehlendes_symbol_bleibt_ein_fehlendes(self, drei) -> None:
        assert drei.abweichungen({}) == ("X fehlt",)
        assert not drei.nur_anders_geschnitten({})

    def test_ein_zusaetzliches_symbol_ist_weiter_keine_drift(self, drei) -> None:
        passend = {"X": _reihe([1.0, 2.0, 3.0]), "Y": _reihe([9.0])}

        assert drei.passt(passend)


class TestDieEmpfehlungHaengtDaran:
    """Der gefaehrliche Teil: 'warum' riet zum Nachziehen des Stempels."""

    def test_beim_schnittfehler_nicht_nachziehen(self, drei) -> None:
        text = warum({"X": _reihe([1.0, 2.0, 3.0, 4.0])}, gegen=drei)

        assert "anders **geschnitten**, nicht anders" in text
        assert "common_range" in text
        assert "Den Stempel hier nachzuziehen waere falsch" in text

    def test_und_nicht_behaupten_die_reihe_habe_sich_geaendert(self, drei) -> None:
        text = warum({"X": _reihe([1.0, 2.0, 3.0, 4.0])}, gegen=drei)

        assert "Die Reihe hat sich geaendert" not in text

    def test_bei_echter_drift_weiter_nachziehen(self, drei) -> None:
        """Dort ist die alte Empfehlung richtig und bleibt."""
        text = warum({"X": _reihe([1.0, 2.0, 3.5])}, gegen=drei)

        assert "Die Reihe hat sich geaendert" in text
        assert "Erst den Stempel nachziehen" in text

    def test_unveraendert_bleibt_unveraendert(self, drei) -> None:
        text = warum({"X": _reihe([1.0, 2.0, 3.0])}, gegen=drei)

        assert "unveraendert" in text


class TestDerStempelDerZulassungsreihe:
    def test_er_beschreibt_die_gemeinsame_spanne(self) -> None:
        """Woran mein Fehlgriff haengt: 3301 ist die Laenge des **juengeren**
        Beins, nicht die von BTC."""
        from research.datenstand import jueneres_bein

        assert SERIE.balken == 3301 == jueneres_bein().balken
        assert SERIE.von == jueneres_bein().von.isoformat()

    def test_und_btc_ist_ungeschnitten_laenger(self) -> None:
        from research.datenstand import aelteres_bein

        assert aelteres_bein().balken == 5355
        assert aelteres_bein().balken > SERIE.balken


@pytest.fixture(scope="module")
def rohreihen():
    """Die echt geholten Tageskerzen, ungeschnitten.

    Auf Modulebene und nicht in der Klasse: Eine klassengebundene Fixture als
    Instanzmethode ist in diesem Projekt ein **Fehler**, nicht nur eine
    Warnung - dasselbe hat Befund 426 schon gekostet, und ich habe es hier
    wiederholt.
    """
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore
    from research.datenstand import REIHEN

    speicher = CandleStore(get_settings().paths.data_store)
    roh = {r.symbol: speicher.read(r.symbol, Interval("D")) for r in REIHEN}
    if any(x is None or x.empty for x in roh.values()):
        pytest.skip("keine Tageskerzen im Speicher")
    return roh


@pytest.mark.daten
class TestAnDenEchtGeholtenKerzen:
    """Die Messung, die den Befund traegt. Ohne sie waere die Formpruefung
    eine Vermutung ueber einen Fall, der nie eingetreten ist."""

    def test_nur_oben_geschnitten_ist_ein_schnittfehler(self, rohreihen) -> None:
        """Genau mein Fehlgriff: 'alle_geschnitten' allein."""
        from research.datenstand import alle_geschnitten

        falsch = alle_geschnitten(rohreihen)

        assert SERIE.nur_anders_geschnitten(falsch)
        assert "5355" in " ".join(SERIE.abweichungen(falsch))

    def test_und_die_meldung_raet_nicht_zum_nachziehen(self, rohreihen) -> None:
        from research.datenstand import alle_geschnitten

        text = warum(alle_geschnitten(rohreihen))

        assert "nachzuziehen waere falsch" in text
        assert "Erst den Stempel nachziehen" not in text

    def test_richtig_geschnitten_passt_der_stempel(self, rohreihen) -> None:
        """Und damit ist belegt, dass es **keine** Datendrift gab."""
        from backtest.portfolio_walkforward import common_range
        from research.datenstand import alle_geschnitten

        richtig = alle_geschnitten(common_range(rohreihen))

        assert SERIE.abweichungen(richtig) == ()
        assert SERIE.passt(richtig)

    def test_die_abdruecke_sind_die_verzeichneten(self, rohreihen) -> None:
        from backtest.portfolio_walkforward import common_range
        from research.datenstand import alle_geschnitten

        richtig = alle_geschnitten(common_range(rohreihen))

        assert fingerabdruck(richtig["BTCUSD_BITSTAMP"]) == "5cda943508eecc9d"
        assert fingerabdruck(richtig["ETHUSD_BITSTAMP"]) == "3141cefdf649ffc2"


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_den_falschen_befund(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 428)

        assert "5355" in eintrag.ergebnis and "3301" in eintrag.ergebnis
        assert "keine Datendrift" in eintrag.ergebnis

    def test_und_die_gefaehrliche_empfehlung(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 428)

        assert "nachziehen" in eintrag.ergebnis
        assert "364" in eintrag.ergebnis

    def test_und_427_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 427).zuletzt == 428
