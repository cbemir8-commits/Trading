"""Eine Behauptung mit zwei Haelften - und nur eine braucht Bybit.

**Befund 251.** ``research.finanzierung`` haelt seit Befund 100 fest, dass der
Bestand eine Long-Trendfolge ist und deshalb dann zahlt, wenn Longs am meisten
zahlen - und schreibt gleich dazu:

    *"Das ist hier nicht gemessen, sondern die Aussage des Engine-Docstrings.
    Nachpruefen laesst es sich nur mit echten Bybit-Raten."*

Der zweite Satz stimmt fuer die **Rate** und nicht fuer die **Belastung**. Die
Behauptung zerfaellt in zwei Haelften:

    1. Liegen die Funding-Stunden in Aufwaertsphasen?   <- eigenes Handelsbuch
    2. Sind die Raten dort hoeher?                      <- braucht Bybit

Haelfte 1 stand die ganze Zeit im eigenen Kursspeicher. Gemessen:
BTC 2,52-fache Drift waehrend der Haltezeit, ETH 6,57-fache; 62 % des Fundings
faellt in Haltezeiten, in denen der Markt gestiegen ist.

Was hier gehalten wird
----------------------
Nicht die Zahlen - die haengen am Kandidaten. Sondern die Rechnung und vor
allem ihre **Grenzen**: dass Ueberlappungen gezaehlt statt angenommen werden,
dass ein gefallener Markt kein Verdichtungsmass hergibt, und dass das Urteil
den Schritt zur Rate nicht mitgeht.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from math import log
from pathlib import Path

import pytest

from research.verdichtung import (
    STUNDEN_JE_JAHR,
    Haltezeit,
    Marktverdichtung,
    Verdichtungsbild,
    messe,
)

TAG = timedelta(days=1)
START = datetime(2020, 1, 1, tzinfo=UTC)


def _halt(
    von_tag: int, bis_tag: int, *, faktor: float, funding: float = 1.0
) -> Haltezeit:
    """Eine Haltezeit, in der der Markt um ``faktor`` steht."""
    return Haltezeit(
        beginn=START + von_tag * TAG,
        ende=START + bis_tag * TAG,
        kurs_beginn=100.0,
        kurs_ende=100.0 * faktor,
        funding=funding,
    )


class TestDieHaltezeitRechnetRichtig:
    def test_stunden(self) -> None:
        assert _halt(0, 10, faktor=1.0).stunden == pytest.approx(240.0)

    def test_drift_ist_die_log_rendite(self) -> None:
        assert _halt(0, 1, faktor=2.0).drift == pytest.approx(log(2.0))

    def test_ein_flacher_markt_driftet_nicht(self) -> None:
        assert _halt(0, 1, faktor=1.0).drift == 0.0

    @pytest.mark.parametrize("anfang,ende", [(0.0, 100.0), (100.0, 0.0), (0.0, 0.0)])
    def test_ein_kurs_von_null_gibt_keine_drift_statt_zu_werfen(
        self, anfang: float, ende: float
    ) -> None:
        """Ein Loch im Kursspeicher darf den Lauf nicht abbrechen - es darf
        nur nichts beitragen."""
        zeit = Haltezeit(
            beginn=START, ende=START + TAG, kurs_beginn=anfang, kurs_ende=ende
        )

        assert zeit.drift == 0.0


class TestDieVerdichtung:
    def test_eine_beliebige_haltezeit_verdichtet_nicht(self) -> None:
        """Der Nullfall: Wer einen Ausschnitt haelt, der so steil ist wie das
        Ganze, hat eine Verdichtung von eins."""
        gesamt = log(4.0)
        bild = messe(
            "M",
            [_halt(0, 100, faktor=2.0)],
            stunden_gesamt=200 * 24.0,
            drift_gesamt=gesamt,
        )

        assert bild.verdichtung == pytest.approx(1.0)

    def test_wer_nur_die_steilen_stuecke_haelt_verdichtet(self) -> None:
        bild = messe(
            "M",
            [_halt(0, 10, faktor=2.0)],
            stunden_gesamt=100 * 24.0,
            drift_gesamt=log(2.0),
        )

        assert bild.verdichtung == pytest.approx(10.0)
        assert bild.anteil_zeit == pytest.approx(0.1)
        assert bild.anteil_drift == pytest.approx(1.0)

    def test_der_anteil_an_der_drift_darf_ueber_eins_gehen(self) -> None:
        """Wer die Rueckgaenge aussitzt, faengt mehr Anstieg ein, als am Ende
        netto uebrig ist - genau der gemessene Fall bei ETH (205 %)."""
        bild = messe(
            "M",
            [_halt(0, 10, faktor=4.0)],
            stunden_gesamt=100 * 24.0,
            drift_gesamt=log(2.0),
        )

        assert bild.anteil_drift > 1.0

    def test_drift_je_jahr_rechnet_auf_dieselbe_einheit(self) -> None:
        bild = messe(
            "M",
            [_halt(0, 365, faktor=2.0)],
            stunden_gesamt=STUNDEN_JE_JAHR,
            drift_gesamt=log(2.0),
        )

        assert bild.drift_je_jahr_gesamt == pytest.approx(log(2.0))
        assert bild.drift_je_jahr_im_markt == pytest.approx(log(2.0))


class TestDasFundingWirdAufgeteiltUndNichtModelliert:
    def test_jede_haltezeit_landet_in_genau_einem_topf(self) -> None:
        bild = messe(
            "M",
            [
                _halt(0, 1, faktor=1.5, funding=10.0),
                _halt(2, 3, faktor=0.5, funding=4.0),
                _halt(4, 5, faktor=1.0, funding=1.0),
            ],
            stunden_gesamt=100 * 24.0,
            drift_gesamt=log(2.0),
        )

        assert (bild.funding_auf, bild.funding_ab, bild.funding_flach) == (
            10.0, 4.0, 1.0,
        )
        assert bild.funding_gesamt == 15.0

    def test_der_anteil_zaehlt_den_flachen_topf_in_den_nenner(self) -> None:
        """Sonst waere er zu gross: Ein flaches Stueck ist kein steigendes."""
        bild = messe(
            "M",
            [
                _halt(0, 1, faktor=1.5, funding=1.0),
                _halt(2, 3, faktor=1.0, funding=1.0),
            ],
            stunden_gesamt=100 * 24.0,
            drift_gesamt=log(2.0),
        )

        assert bild.anteil_funding_auf == pytest.approx(0.5)

    def test_ohne_funding_ist_der_anteil_null_und_kein_fehler(self) -> None:
        bild = messe(
            "M", [_halt(0, 1, faktor=1.5, funding=0.0)],
            stunden_gesamt=24.0, drift_gesamt=log(2.0),
        )

        assert bild.anteil_funding_auf == 0.0


class TestWasDieRechnungNichtTraegt:
    """Die Summen zaehlen ueber Haltezeiten. Zwei Annahmen stecken darin, und
    beide werden geprueft statt geglaubt."""

    def test_ueberlappende_haltezeiten_werden_gezaehlt(self) -> None:
        bild = messe(
            "M",
            [_halt(0, 10, faktor=2.0), _halt(5, 15, faktor=2.0)],
            stunden_gesamt=100 * 24.0,
            drift_gesamt=log(2.0),
        )

        assert bild.ueberlappende == 1
        assert not bild.belastbar

    def test_die_zaehlung_haengt_nicht_an_der_reihenfolge(self) -> None:
        vorwaerts = messe(
            "M", [_halt(0, 10, faktor=2.0), _halt(5, 15, faktor=2.0)],
            stunden_gesamt=2400.0, drift_gesamt=log(2.0),
        )
        rueckwaerts = messe(
            "M", [_halt(5, 15, faktor=2.0), _halt(0, 10, faktor=2.0)],
            stunden_gesamt=2400.0, drift_gesamt=log(2.0),
        )

        assert vorwaerts.ueberlappende == rueckwaerts.ueberlappende == 1

    def test_luecken_zwischen_haltezeiten_sind_keine_ueberlappung(self) -> None:
        bild = messe(
            "M",
            [_halt(0, 10, faktor=2.0), _halt(20, 30, faktor=2.0)],
            stunden_gesamt=100 * 24.0,
            drift_gesamt=log(2.0),
        )

        assert bild.ueberlappende == 0
        assert bild.belastbar

    def test_beruehrende_haltezeiten_ueberlappen_nicht(self) -> None:
        """Ausstieg und Wiedereinstieg im selben Moment - lueckenlos, aber
        nicht doppelt."""
        bild = messe(
            "M",
            [_halt(0, 10, faktor=2.0), _halt(10, 20, faktor=2.0)],
            stunden_gesamt=100 * 24.0,
            drift_gesamt=log(2.0),
        )

        assert bild.ueberlappende == 0

    @pytest.mark.parametrize("gesamt", [-0.5, 0.0])
    def test_ein_gefallener_markt_traegt_kein_verdichtungsmass(
        self, gesamt: float
    ) -> None:
        """Das Verhaeltnis zweier Driften misst dann kein 'steiler', sondern
        ein Vorzeichen."""
        bild = messe(
            "M", [_halt(0, 10, faktor=2.0)],
            stunden_gesamt=2400.0, drift_gesamt=gesamt,
        )

        assert not bild.belastbar

    def test_ohne_haltezeiten_bleibt_alles_null_statt_zu_werfen(self) -> None:
        bild = messe("M", [], stunden_gesamt=2400.0, drift_gesamt=log(2.0))

        assert bild.anteil_zeit == 0.0
        assert bild.verdichtung == 0.0
        assert bild.drift_je_jahr_im_markt == 0.0


class TestDasBildBerichtetVorsichtig:
    @staticmethod
    def _markt(name: str, *, verdichtet: float, belastbar: bool = True) -> Marktverdichtung:
        return Marktverdichtung(
            symbol=name,
            stunden_gesamt=2400.0,
            stunden_im_markt=240.0,
            drift_gesamt=1.0,
            drift_im_markt=verdichtet / 10.0,
            funding_auf=6.0,
            funding_ab=4.0,
            ueberlappende=0 if belastbar else 1,
        )

    def test_berichtet_wird_der_schwaechste_markt(self) -> None:
        """Nicht der Durchschnitt und nicht der beste: der, der die Aussage
        gerade noch traegt."""
        bild = Verdichtungsbild(
            maerkte=(
                self._markt("stark", verdichtet=6.6),
                self._markt("schwach", verdichtet=2.5),
            )
        )

        assert bild.schwaechste is not None
        assert bild.schwaechste.symbol == "schwach"
        assert "schwach" in bild.urteil()

    def test_ein_nicht_belastbarer_markt_kommt_nicht_ins_urteil(self) -> None:
        bild = Verdichtungsbild(
            maerkte=(
                self._markt("gut", verdichtet=2.5),
                self._markt("kaputt", verdichtet=0.1, belastbar=False),
            )
        )

        assert bild.schwaechste is not None
        assert bild.schwaechste.symbol == "gut"
        assert "Nicht belastbar" in bild.urteil()
        assert "kaputt" in bild.urteil()

    def test_ohne_belastbaren_markt_gibt_es_kein_urteil(self) -> None:
        bild = Verdichtungsbild(
            maerkte=(self._markt("kaputt", verdichtet=3.0, belastbar=False),)
        )

        assert bild.schwaechste is None
        assert "Kein Markt traegt hier eine Aussage" in bild.urteil()

    def test_einig_verlangt_dass_alle_ueber_eins_liegen(self) -> None:
        einig = Verdichtungsbild(
            maerkte=(
                self._markt("a", verdichtet=2.5),
                self._markt("b", verdichtet=6.6),
            )
        )
        uneinig = Verdichtungsbild(
            maerkte=(
                self._markt("a", verdichtet=2.5),
                self._markt("b", verdichtet=0.4),
            )
        )

        assert einig.einig and not uneinig.einig

    def test_das_funding_wird_ueber_alle_maerkte_zusammengezaehlt(self) -> None:
        bild = Verdichtungsbild(
            maerkte=(
                self._markt("a", verdichtet=2.5),
                self._markt("b", verdichtet=6.6),
            )
        )

        assert bild.funding_gesamt == 20.0
        assert bild.anteil_funding_auf == pytest.approx(0.6)

    def test_die_tabelle_nennt_jeden_markt(self) -> None:
        text = Verdichtungsbild(
            maerkte=(
                self._markt("AAA", verdichtet=2.5),
                self._markt("BBB", verdichtet=6.6, belastbar=False),
            )
        ).tabelle()

        assert "AAA" in text and "BBB" in text
        assert "nicht belastbar" in text

    def test_ohne_maerkte_sagt_die_tabelle_das(self) -> None:
        assert "Keine Maerkte" in Verdichtungsbild().tabelle()


class TestDasUrteilGehtDenSchrittZurRateNichtMit:
    """Die Grenze ist der Punkt des ganzen Befunds - gemessen ist der Hebel,
    nicht der Ausschlag."""

    @staticmethod
    def _urteil() -> str:
        return Verdichtungsbild(
            maerkte=(
                Marktverdichtung(
                    symbol="M", stunden_gesamt=2400.0, stunden_im_markt=240.0,
                    drift_gesamt=1.0, drift_im_markt=0.25,
                    funding_auf=6.0, funding_ab=4.0,
                ),
            )
        ).urteil()

    def test_es_nennt_die_bedingung_fuer_den_schluss(self) -> None:
        assert "Wenn das stimmt" in self._urteil()

    def test_es_sagt_dass_das_wieviel_offen_bleibt(self) -> None:
        text = self._urteil()

        assert "Um wie viel" in text
        assert "Hebel, nicht der Ausschlag" in text

    def test_es_vergleicht_nicht_gegen_den_vorgabewert(self) -> None:
        """Der Vorgabewert ist ein Basiswert, kein Durchschnitt - der
        Vergleich hier geht gegen den Marktdurchschnitt."""
        assert "Basiswert und kein Durchschnitt" in self._urteil()

    def test_es_sagt_dass_kein_versuch_faellig_wird(self) -> None:
        assert "Kostet keinen Versuch" in self._urteil()


class TestDerBefehlMisstDenMarktUndNichtDenTrade:
    """Die Kurse fuer die Drift kommen aus dem Kursspeicher, nicht aus
    ``entry_price``/``exit_price``: Gefragt ist, was der Markt getan hat."""

    @staticmethod
    def _quelle() -> str:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "finanzierung"
        )
        return ast.unparse(knoten)

    def test_die_kurse_kommen_aus_dem_kursspeicher(self) -> None:
        quelle = self._quelle()

        assert "kurs.asof(t.entry_time)" in quelle
        assert "kurs.asof(t.exit_time)" in quelle

    def test_die_ein_und_ausstiegskurse_des_trades_werden_nicht_benutzt(self) -> None:
        quelle = self._quelle()

        assert "t.entry_price" not in quelle
        assert "t.exit_price" not in quelle

    def test_gemessen_wird_am_vorgabewert(self) -> None:
        """Das Handelsbuch soll das sein, ueber das der Bericht redet - nicht
        eines aus einem erfundenen Satz."""
        assert "lauf(BASISSATZ)" in self._quelle()
