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
    MINDESTZEITEN,
    STUNDEN_JE_JAHR,
    Familienbild,
    Haltezeit,
    Marktverdichtung,
    Regelverdichtung,
    Verdichtungsbild,
    aus_bild,
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
        assert "ineinander" in text, "der Grund fehlt"

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
        assert "lauf(BASISSATZ, regel)" in self._quelle()

    def test_bestand_und_katalog_messen_durch_dieselbe_stelle(self) -> None:
        """Sonst waere der Bestand im Katalog eine andere Messung als der
        Bestand allein - und der Vergleich, um den es in 252 geht, waere
        keiner."""
        quelle = self._quelle()

        assert quelle.count("def vermesse(") == 1
        assert "ganz = vermesse(genome)" in quelle
        assert "einzeln = vermesse(regel)" in quelle


class TestEineShortHaltezeitKipptDieDeutung:
    """**Befund 252.** Die Rechnung zaehlt Drift und Stunden, egal wer sie
    traegt. Ihre *Deutung* kippt aber: Auf einem Perpetual zahlt die
    Long-Seite bei positiver Rate, die Short-Seite bekommt. Fuer eine
    zweiseitige Regel heisst "der Markt ist gestiegen" also nicht mehr "sie
    hat mehr gezahlt".

    Gefunden beim Katalogdurchlauf: 'Trend beide Richtungen' (42 Buy, 42
    Sell) verdichtet als einzige Regel nicht - und war damit fast das
    Gegenbeispiel zur Familienaussage, obwohl das Mass auf sie gar nicht
    passt.
    """

    def test_long_ist_die_vorgabe(self) -> None:
        assert _halt(0, 1, faktor=1.5).long

    def test_eine_short_haltezeit_macht_den_markt_unbelastbar(self) -> None:
        lang = _halt(0, 10, faktor=2.0)
        kurz = Haltezeit(
            beginn=START + 20 * TAG, ende=START + 30 * TAG,
            kurs_beginn=100.0, kurs_ende=200.0, long=False,
        )
        bild = messe("M", [lang, kurz], stunden_gesamt=2400.0, drift_gesamt=log(2.0))

        assert bild.nicht_long == 1
        assert not bild.belastbar
        assert "nicht long" in bild.grund

    def test_reine_long_zeiten_bleiben_belastbar(self) -> None:
        bild = messe(
            "M", [_halt(0, 10, faktor=2.0), _halt(20, 30, faktor=2.0)],
            stunden_gesamt=2400.0, drift_gesamt=log(2.0),
        )

        assert bild.nicht_long == 0 and bild.belastbar


class TestDerGrundStehtDaUndNichtNurEinNein:
    @pytest.mark.parametrize(
        "bild,erwartet",
        [
            (
                Marktverdichtung(
                    symbol="M", stunden_gesamt=2400.0, stunden_im_markt=240.0,
                    drift_gesamt=1.0, drift_im_markt=0.25, ueberlappende=3,
                ),
                "ineinander",
            ),
            (
                Marktverdichtung(
                    symbol="M", stunden_gesamt=2400.0, stunden_im_markt=240.0,
                    drift_gesamt=1.0, drift_im_markt=0.25, nicht_long=2,
                ),
                "nicht long",
            ),
            (
                Marktverdichtung(
                    symbol="M", stunden_gesamt=2400.0, stunden_im_markt=240.0,
                    drift_gesamt=-1.0, drift_im_markt=0.25,
                ),
                "nicht gestiegen",
            ),
        ],
    )
    def test_jeder_grund_wird_benannt(
        self, bild: Marktverdichtung, erwartet: str
    ) -> None:
        assert erwartet in bild.grund
        assert not bild.belastbar

    def test_ein_tragender_markt_hat_keinen_grund(self) -> None:
        bild = Marktverdichtung(
            symbol="M", stunden_gesamt=2400.0, stunden_im_markt=240.0,
            drift_gesamt=1.0, drift_im_markt=0.25,
        )

        assert bild.grund == "" and bild.belastbar

    def test_die_zeile_zeigt_den_grund_statt_nur_unbelastbar(self) -> None:
        zeile = Marktverdichtung(
            symbol="M", stunden_gesamt=2400.0, stunden_im_markt=240.0,
            drift_gesamt=1.0, drift_im_markt=0.25, ueberlappende=3,
        ).zeile()

        assert "ineinander" in zeile


def _regel(
    name: str, wert: float, *, zeiten: int = 50, bestand: bool = False,
    belastbar: bool = True,
) -> Regelverdichtung:
    return Regelverdichtung(
        name=name, verdichtung=wert, zeiten=zeiten, belastbar=belastbar,
        grund="" if belastbar else "erfunden", ist_bestand=bestand,
    )


class TestIstEsDerBestandOderDieBauart:
    """Die Frage, die entscheidet, was Befund 251 wert ist."""

    def test_liegt_der_bestand_mitten_drin_ist_es_die_bauart(self) -> None:
        familie = Familienbild(
            regeln=(
                _regel("Bestand", 2.52, bestand=True),
                _regel("a", 1.62),
                _regel("b", 2.67),
            )
        )

        assert familie.bestand_liegt_drin
        assert "keine Eigenschaft dieses Kandidaten" in familie.urteil()
        assert "kann die Suche" in familie.urteil()

    def test_liegt_er_ausserhalb_ist_es_seine_eigenschaft(self) -> None:
        familie = Familienbild(
            regeln=(
                _regel("Bestand", 9.0, bestand=True),
                _regel("a", 1.6),
                _regel("b", 2.0),
            )
        )

        assert not familie.bestand_liegt_drin
        assert "ausserhalb der Spanne" in familie.urteil()
        assert "eine andere Regel traegt weniger" in familie.urteil()

    def test_ohne_andere_regeln_wird_nichts_behauptet(self) -> None:
        familie = Familienbild(regeln=(_regel("Bestand", 2.5, bestand=True),))

        assert not familie.bestand_liegt_drin
        assert "Zu wenige brauchbare Regeln" in familie.urteil()


class TestDieGegenbeispieleStehenImUrteil:
    def test_eine_regel_unter_eins_wird_genannt(self) -> None:
        familie = Familienbild(
            regeln=(
                _regel("Bestand", 2.5, bestand=True),
                _regel("bleibt drunter", 0.74),
                _regel("b", 2.0),
            )
        )

        assert [r.name for r in familie.ausnahmen] == ["bleibt drunter"]
        assert "bleibt drunter" in familie.urteil()
        assert "Fussnote" in familie.urteil()

    def test_ohne_ausnahmen_steht_der_satz_nicht_da(self) -> None:
        familie = Familienbild(
            regeln=(_regel("Bestand", 2.5, bestand=True), _regel("b", 2.0))
        )

        assert familie.ausnahmen == ()
        assert "Fussnote" not in familie.urteil()

    def test_die_spanne_zaehlt_nur_brauchbare(self) -> None:
        familie = Familienbild(
            regeln=(
                _regel("gut", 2.0),
                _regel("gut2", 3.0),
                _regel("kaputt", 99.0, belastbar=False),
                _regel("knapp", 0.1, zeiten=2),
            )
        )

        assert familie.spanne == (2.0, 3.0)
        assert len(familie.brauchbare) == 2


class TestDieSchwelleEntscheidetNichtAllein:
    """``MINDESTZEITEN`` ist gesetzt und nicht gemessen. Wenn die Aussage an
    ihr haengt, muss das dastehen."""

    def test_sie_haengt_daran_wenn_eine_knappe_regel_das_bild_dreht(self) -> None:
        familie = Familienbild(
            regeln=(
                _regel("Bestand", 2.5, bestand=True),
                _regel("b", 2.0),
                _regel("knapp und anders", 0.5, zeiten=3),
            )
        )

        assert familie.haengt_an_der_schwelle
        assert "Ohne die Schwelle" in familie.urteil()

    def test_sie_haengt_nicht_daran_wenn_alle_dasselbe_sagen(self) -> None:
        familie = Familienbild(
            regeln=(
                _regel("Bestand", 2.5, bestand=True),
                _regel("b", 2.0),
                _regel("knapp, aber gleich", 1.9, zeiten=3),
            )
        )

        assert not familie.haengt_an_der_schwelle
        assert "haengt nicht an der Schwelle" in familie.urteil()

    def test_genug_richtet_sich_nach_der_konstanten(self) -> None:
        knapp = _regel("x", 2.0, zeiten=MINDESTZEITEN - 1)
        gerade = _regel("y", 2.0, zeiten=MINDESTZEITEN)

        assert not knapp.genug and gerade.genug


class TestAusBildMachtEineZeile:
    @staticmethod
    def _markt(name: str, wert: float, *, zeiten: int, kaputt: bool = False):
        return Marktverdichtung(
            symbol=name, stunden_gesamt=2400.0, stunden_im_markt=240.0,
            drift_gesamt=1.0, drift_im_markt=wert / 10.0, zeiten=zeiten,
            ueberlappende=4 if kaputt else 0,
        )

    def test_genommen_wird_der_schwaechste_markt(self) -> None:
        zeile = aus_bild(
            "R",
            Verdichtungsbild(
                maerkte=(
                    self._markt("a", 6.0, zeiten=30),
                    self._markt("b", 2.0, zeiten=20),
                )
            ),
        )

        assert zeile.verdichtung == pytest.approx(2.0)
        assert zeile.zeiten == 50

    def test_ohne_belastbaren_markt_traegt_die_zeile_den_grund(self) -> None:
        zeile = aus_bild(
            "R",
            Verdichtungsbild(
                maerkte=(self._markt("a", 6.0, zeiten=30, kaputt=True),)
            ),
        )

        assert not zeile.belastbar
        assert "ineinander" in zeile.grund
        assert "ineinander" in zeile.zeile()

    def test_der_bestand_ist_in_der_tabelle_markiert(self) -> None:
        text = Familienbild(
            regeln=(_regel("Bestand", 2.5, bestand=True), _regel("b", 2.0))
        ).tabelle()

        assert "<- Bestand" in text

    def test_ohne_regeln_sagt_die_tabelle_das(self) -> None:
        assert "Keine Regeln" in Familienbild().tabelle()

    def test_das_urteil_sagt_dass_kein_versuch_faellig_wird(self) -> None:
        text = Familienbild(
            regeln=(_regel("Bestand", 2.5, bestand=True), _regel("b", 2.0))
        ).urteil()

        assert "Kostet keinen Versuch" in text
        assert "waren gezaehlt, als sie entstanden" in text


class TestKeinTradeIstNichtDasselbeWieWenigeTrades:
    """Elf der 31 Katalogregeln handeln auf diesen Daten ueberhaupt nicht.
    "unter 20 Haltezeiten" liest sich dort wie "hat wenig gehandelt" - und
    das waere die falsche Auskunft."""

    def test_eine_regel_ohne_trades_sagt_das(self) -> None:
        zeile = _regel("stumm", 0.0, zeiten=0).zeile()

        assert "kein einziger Trade" in zeile
        assert "unter" not in zeile

    def test_eine_regel_mit_wenigen_trades_sagt_etwas_anderes(self) -> None:
        zeile = _regel("knapp", 2.0, zeiten=3).zeile()

        assert f"unter {MINDESTZEITEN}" in zeile
        assert "kein einziger Trade" not in zeile

    def test_beide_zaehlen_nicht_als_brauchbar(self) -> None:
        assert not _regel("stumm", 0.0, zeiten=0).brauchbar
        assert not _regel("knapp", 2.0, zeiten=3).brauchbar
