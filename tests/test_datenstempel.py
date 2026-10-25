"""Drei Zahlen standen in der Prosa und als Behauptung im Test - Befund 408.

Befund 364 hat die Zulassungsreihe aus vier unabhaengigen Angaben
wiederhergestellt und drei Zahlen gefunden, die auf ihr nicht mehr
reproduzieren. Der Eintrag dort sagt, dass sie offen bleiben, und warum sie
nicht nachgezogen werden duerfen. Beides ist richtig - und die Tests, die
diese Zahlen zusichern, sind stehen geblieben. Von Befund 364 an war die
Auswahl ``-m "daten"`` rot, und weil die Suite als ``-m "not daten"`` laeuft,
hat es vierzehn Zyklen niemand gesehen: 3 von 116, gemessen in 35 Minuten.

Dieselbe Lehre wie Befund 394 (die elf Zeilen gab es in keiner Ausgabe) und
399 (eine Wache, die nur ihren eigenen Text prueft): Ein Satz in einem
Prosatext ist keine Zusicherung, und eine Zusicherung, die niemand ausfuehrt,
ist kein Schutz.
"""

from __future__ import annotations

import pandas as pd
import pytest

from research.datenstempel import (
    ALTZAHLEN,
    SERIE,
    Altzahl,
    Reihenstempel,
    altzahl,
    fingerabdruck,
    groesste_abweichung,
    stempel,
    warum,
)


def _rahmen(schluss: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2020-01-01", periods=len(schluss)),
            "open": schluss,
            "high": [x + 1 for x in schluss],
            "low": [x - 1 for x in schluss],
            "close": schluss,
            "volume": [10.0] * len(schluss),
        }
    )


class TestDerAbdruck:
    def test_gleiche_kerzen_gleicher_abdruck(self) -> None:
        assert fingerabdruck(_rahmen([1.0, 2.0])) == fingerabdruck(
            _rahmen([1.0, 2.0])
        )

    def test_eine_berichtigte_kerze_aendert_ihn(self) -> None:
        """Der Fall, den Befund 364 vermutet und nicht nachpruefen konnte."""
        assert fingerabdruck(_rahmen([1.0, 2.0])) != fingerabdruck(
            _rahmen([1.0, 2.0001])
        )

    def test_er_haengt_nicht_an_der_zeitachse(self) -> None:
        """Eine nachtraeglich berichtigte Kerze aendert Preise, nicht ihren
        Zeitstempel. Die Spanne steht in 'balken'/'von'/'bis' und braucht den
        Abdruck nicht."""
        a = _rahmen([1.0, 2.0])
        b = _rahmen([1.0, 2.0])
        b["open_time"] = pd.date_range("2021-06-01", periods=2)

        assert fingerabdruck(a) == fingerabdruck(b)

    def test_er_ist_kurz_und_hexadezimal(self) -> None:
        abdruck = fingerabdruck(_rahmen([1.0]))

        assert len(abdruck) == 16
        assert all(x in "0123456789abcdef" for x in abdruck)


class TestDerStempel:
    def test_er_nennt_form_und_inhalt(self) -> None:
        s = stempel({"X": _rahmen([1.0, 2.0, 3.0])})

        assert s.balken == 3
        assert s.von == "2020-01-01"
        assert s.bis == "2020-01-03"
        assert s.abdruecke == {"X": fingerabdruck(_rahmen([1.0, 2.0, 3.0]))}

    def test_unveraendert_keine_abweichung(self) -> None:
        rahmen = {"X": _rahmen([1.0, 2.0])}

        assert stempel(rahmen).passt(rahmen)

    def test_geaendert_wird_benannt(self) -> None:
        alt = stempel({"X": _rahmen([1.0, 2.0])})
        anders = alt.abweichungen({"X": _rahmen([1.0, 2.5])})

        assert len(anders) == 1
        assert anders[0].startswith("X ")
        assert "->" in anders[0]

    def test_ein_fehlendes_symbol_auch(self) -> None:
        alt = stempel({"X": _rahmen([1.0])})

        assert alt.abweichungen({}) == ("X fehlt",)

    def test_ein_zusaetzliches_symbol_ist_keine_drift(self) -> None:
        """Sonst meldete jeder zusaetzlich gemessene Markt eine Datenaenderung
        - und die Meldung waere nach dem ersten Mal nichts mehr wert."""
        alt = stempel({"X": _rahmen([1.0])})

        assert alt.passt({"X": _rahmen([1.0]), "Y": _rahmen([9.0])})


class TestDieAltzahlen:
    def test_es_sind_sechs(self) -> None:
        """Vier aus dem Eintrag von 364, plus zwei, die in keiner Liste
        standen: der zweite Kapitalendstand ohne Officer und der zweite
        Streuungswert. Beide kamen erst zum Vorschein, als die Zusicherung
        davor nicht mehr vorher abbrach."""
        assert len(ALTZAHLEN) == 6

    def test_jede_nennt_ihren_befund_und_die_fundstelle(self) -> None:
        for zahl in ALTZAHLEN:
            assert zahl.befund in (339, 340, 356)
            assert zahl.verzeichnet == 364
            assert zahl.gemessen == 408

    def test_der_abstand_hat_ein_vorzeichen(self) -> None:
        hoch = Altzahl(name="x", gepflegt=100.0, heute=101.0, befund=1)
        tief = Altzahl(name="y", gepflegt=100.0, heute=99.0, befund=1)

        assert hoch.prozent == pytest.approx(1.0)
        assert tief.prozent == pytest.approx(-1.0)

    def test_beide_richtungen_kommen_vor(self) -> None:
        """Zwei Zahlen sind gestiegen, zwei gefallen. Eine Drift in **eine**
        Richtung waere ein Rechenfehler; so sieht eine Datenberichtigung aus.
        """
        zeichen = {x.abstand > 0 for x in ALTZAHLEN}

        assert zeichen == {True, False}

    def test_die_spanne_ist_die_gemessene(self) -> None:
        """Die pruefbare Behauptung - und zwar die gemessene Spanne selbst,
        nicht eine Schwelle, die bequem darueber liegt. Befund 364 nennt 0,2
        bis 0,6 Prozent; mit allen sechs Zahlen sind es 0,23 bis 1,18.
        """
        spanne = sorted(abs(x.prozent) for x in ALTZAHLEN)

        assert spanne[0] == pytest.approx(0.23, abs=0.01)
        assert spanne[-1] == pytest.approx(1.20, abs=0.01)
        assert groesste_abweichung() == pytest.approx(0.0120, abs=1e-4)

    def test_nachschlagen_per_name(self) -> None:
        assert altzahl("Schiefe ueber alle Trades").gepflegt == 3.376

    def test_ein_unbekannter_name_ist_ein_fehler(self) -> None:
        """Ein Test, der seine Altzahl nicht findet, darf nicht
        stillschweigend durchlaufen."""
        with pytest.raises(KeyError):
            altzahl("gibt es nicht")

    def test_gepflegt_und_heute_sind_verschieden(self) -> None:
        """Eine Altzahl, die wieder stimmt, gehoert aus der Liste - nicht
        angepasst."""
        for zahl in ALTZAHLEN:
            assert zahl.gepflegt != zahl.heute


class TestDieMeldung:
    """Beide Zweige, ohne echte Daten - darum nimmt 'warum' einen Stempel."""

    def test_unveraendert_sagt_es_kommt_nicht_aus_den_daten(self) -> None:
        """Die Auskunft, die Befund 364 nicht mehr bekommen konnte."""
        rahmen = {"X": _rahmen([1.0, 2.0])}
        meldung = warum(rahmen, gegen=stempel(rahmen))

        assert "unveraendert" in meldung
        assert "nicht aus den Daten" in meldung

    def test_geaendert_nennt_symbol_und_beide_abdruecke(self) -> None:
        rahmen = {"X": _rahmen([1.0, 2.0])}
        alt = Reihenstempel(
            balken=2,
            von="2020-01-01",
            bis="2020-01-02",
            abdruecke={"X": "deadbeefdeadbeef"},
        )
        meldung = warum(rahmen, gegen=alt)

        assert "geaendert" in meldung
        assert "X deadbeef -> " in meldung
        assert fingerabdruck(rahmen["X"])[:8] in meldung

    def test_und_sagt_warum_der_speicher_wechseln_kann(self) -> None:
        """Der Grund, warum ein Abdruck ueberhaupt noetig ist: Der Speicher
        steht in .gitignore, also holt ihn jeder Container neu."""
        alt = Reihenstempel(
            balken=1,
            von="2020-01-01",
            bis="2020-01-01",
            abdruecke={"X": "deadbeefdeadbeef"},
        )
        meldung = warum({"X": _rahmen([1.0])}, gegen=alt)

        assert ".gitignore" in meldung
        assert "Erst den Stempel nachziehen, dann die Zahl" in meldung

    def test_ohne_stempel_nimmt_sie_die_verzeichnete_reihe(self) -> None:
        """Der Normalfall in den Tests: ein Argument, nicht zwei."""
        meldung = warum({})

        assert "geaendert" in meldung
        for symbol in SERIE.abdruecke:
            assert f"{symbol} fehlt" in meldung


class TestDerKopfVonDatenstandIstBerichtigt:
    """Der Eintrag, der die Drift verzeichnet, hat sie unterzaehlt - und er
    ist die Stelle, an der jemand nachsieht. Dann muss die Berichtigung dort
    stehen und nicht nur im Register."""

    def _kopf(self) -> str:
        import research.datenstand

        return research.datenstand.__doc__ or ""

    def test_er_nennt_sechs_statt_drei(self) -> None:
        kopf = self._kopf()

        assert "Es sind **sechs**, nicht drei" in kopf
        assert "0,23 bis 1,20 Prozent" in kopf

    def test_er_nennt_den_grund_fuer_die_unterzaehlung(self) -> None:
        kopf = self._kopf()

        assert "ein ``assert`` den Test beendet" in kopf
        assert "zwoelf von fuenfzehn" in kopf

    def test_er_nennt_die_rote_auswahl(self) -> None:
        kopf = self._kopf()

        assert 'Auswahl ``-m "daten"`` rot' in kopf
        assert "vierzehn Zyklen" in kopf

    def test_und_dass_sein_eigener_satz_gehalten_hat(self) -> None:
        """Die Gegenprobe zur Selbstkritik: Der Eintrag hat seinen Zweck
        erfuellt - er hat mich abgefangen."""
        kopf = self._kopf()

        assert "abgefangen hat es dieser" in kopf

    def test_die_alten_zahlen_stehen_unveraendert(self) -> None:
        """Der Beleg bleibt. Angepasst wird nichts."""
        kopf = self._kopf()

        for alt in ("2318,32", "0,5958", "3,376"):
            assert alt in kopf


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_rote_auswahl(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 408)

        assert "3 von 116" in eintrag.ergebnis
        assert "vierzehn" in eintrag.ergebnis.lower()

    def test_und_den_eigenen_fehlgriff(self) -> None:
        """Mein erster Reflex war, die Zahl nachzuziehen - genau das, was 364
        verbietet. Das gehoert in den Eintrag."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 408)

        assert "Reflex war, sie nachzuziehen" in eintrag.ergebnis
        assert "364 hat es abgefangen, nicht ich" in eintrag.ergebnis

    def test_und_was_widerlegt_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 408)

        assert "ungeschnitten" in eintrag.ergebnis

    def test_und_407_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 407).zuletzt == 408


@pytest.mark.daten
@pytest.mark.langsam
class TestAnDenEchtenDatenGemessen:
    def test_die_reihe_traegt_den_verzeichneten_abdruck(self) -> None:
        """Der Stempel selbst unter Test. Faellt er, hat sich der Speicher
        bewegt - und dann sagt jede andere abweichende Zahl, woran es liegt.
        """
        from backtest.portfolio_walkforward import common_range
        from core.config import get_settings
        from core.models import Interval
        from data.store import CandleStore
        from research.datenstand import alle_geschnitten

        e = get_settings()
        speicher = CandleStore(e.paths.data_store)
        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        frames = alle_geschnitten(
            common_range({x: speicher.read(x, Interval("D")) for x in symbole})
        )
        ist = stempel(frames)

        assert ist.balken == SERIE.balken
        assert ist.von == SERIE.von
        assert ist.bis == SERIE.bis
        assert SERIE.abweichungen(frames) == (), warum(frames)
