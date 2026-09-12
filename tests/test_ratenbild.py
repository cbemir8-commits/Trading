"""Reicht der Mittelwert? - und haelt der Vergleich, der das messen soll.

**Befund 266.** Die Kipppunkte aus Befund 250 (5,99 % fuer 'Schlechtestes
Jahr', 9,75 % fuer 'Parameter-Plateau') sind mit einem *flachen* Satz
gemessen. Echtes Funding schwankt, und die Haltezeit dieses Kandidaten
schwankt mit (Befund 251). Ob das Urteil davon abhaengt, laesst sich ohne
Bybit pruefen: gleicher Mittelwert, verschiedene Form.

Der ganze Befund haengt an einer Eigenschaft
--------------------------------------------
**Die Mittelwerte muessen exakt gleich sein.** Sonst misst der Vergleich
wieder die Hoehe - und die steht seit 250 fest. Ein Vergleich, der das
verletzt, faellt nicht auf: Er liefert Zahlen, die sich unterscheiden, und
sieht damit aus wie ein Befund. Diese Datei haelt die Eigenschaft an jedem
Aufbau einzeln fest, und am Vergleich selbst.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import fmean, pstdev

import pytest

from backtest.costs import FundingSchedule
from research.finanzierung import BASISSATZ, jahr_pct
from research.ratenbild import (
    MITTELFEINHEIT,
    Ratenbild,
    Ratenprobe,
    Ratenvergleich,
    flaches_bild,
    gekoppeltes_bild,
    richtungsfolge,
    vergleiche,
    wechselndes_bild,
    zentriert,
)

ZEITEN = [datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=8 * i) for i in range(90)]
#: Zwei Drittel oben, ein Drittel unten - ungleich, damit ein blosser
#: Vorzeichenwechsel den Mittelwert nicht von selbst trifft.
RICHTUNG = tuple(-1 if i % 3 == 0 else 1 for i in range(len(ZEITEN)))


def _probe(name: str, bild: Ratenbild, *, gefallen: tuple[str, ...], gezahlt: float):
    return Ratenprobe(
        bild=bild,
        bestanden=11 - len(gefallen),
        gesamt=11,
        gefallen=gefallen,
        cagr_pct=13.0,
        rueckgang_pct=10.0,
        gezahlt=gezahlt,
    )


class TestDerMittelwertIstDerVergleich:
    """Ohne diese Eigenschaft misst der ganze Befund etwas anderes."""

    def test_zentriert_trifft_das_ziel(self) -> None:
        assert fmean(zentriert([1.0, 2.0, 9.0], 4.0)) == pytest.approx(4.0)

    def test_zentriert_laesst_die_form_stehen(self) -> None:
        """Additiv und nicht multiplikativ - ein Faktor zoege die Streuung
        mit, und dann waere Form von Staerke nicht mehr zu trennen."""
        roh = [1.0, 2.0, 9.0]

        assert pstdev(zentriert(roh, 4.0)) == pytest.approx(pstdev(roh))

    def test_zentriert_haelt_die_leere_liste_aus(self) -> None:
        assert zentriert([], 4.0) == ()

    @pytest.mark.parametrize(
        "bild",
        [
            flaches_bild(ZEITEN, BASISSATZ),
            wechselndes_bild(ZEITEN, BASISSATZ, hub=0.5),
            gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5),
            gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=1.0),
        ],
        ids=["flach", "wechselnd", "gekoppelt_05", "gekoppelt_10"],
    )
    def test_jeder_aufbau_trifft_den_vorgabewert(self, bild: Ratenbild) -> None:
        assert bild.trifft(BASISSATZ)
        assert bild.mittel == pytest.approx(BASISSATZ, abs=MITTELFEINHEIT)

    def test_und_die_form_unterscheidet_sie_trotzdem(self) -> None:
        """Gleicher Mittelwert **und** verschiedene Streuung - sonst waere der
        Vergleich zwar gueltig, aber leer."""
        flach = flaches_bild(ZEITEN, BASISSATZ)
        gekoppelt = gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5)

        assert flach.streuung == 0
        assert gekoppelt.streuung > MITTELFEINHEIT

    def test_staerkere_kopplung_streut_weiter(self) -> None:
        schwach = gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5)
        stark = gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=1.0)

        assert stark.streuung > schwach.streuung

    def test_ein_verfehlter_mittelwert_faellt_auf(self) -> None:
        daneben = Ratenbild("schief", tuple(ZEITEN), tuple([BASISSATZ * 2] * len(ZEITEN)))

        assert not daneben.trifft(BASISSATZ)


class TestDasBildAlsKostenmodell:
    def test_jeder_zeitpunkt_traegt_seinen_satz(self) -> None:
        bild = gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5)
        plan = bild.zeitplan

        assert plan.rate_at(ZEITEN[0]) == Decimal(str(bild.saetze[0]))
        assert plan.rate_at(ZEITEN[7]) == Decimal(str(bild.saetze[7]))

    def test_ausserhalb_gilt_der_mittelwert_und_nicht_die_vorgabe(self) -> None:
        """Ein Zeitpunkt ausserhalb der Liste soll den Vergleich nicht
        verschieben. Mit dem Bybit-Vorgabewert als Rueckfall haette ein Bild
        auf anderer Hoehe dort heimlich die Vorgabe gezahlt."""
        bild = flaches_bild(ZEITEN, BASISSATZ * 3)

        weit_weg = ZEITEN[0] - timedelta(days=400)

        assert bild.zeitplan.rate_at(weit_weg) == Decimal(str(BASISSATZ * 3))
        assert FundingSchedule().default_rate == Decimal(str(BASISSATZ))

    def test_laenge_muss_zusammenpassen(self) -> None:
        with pytest.raises(ValueError, match="genau ein Satz"):
            Ratenbild("schief", tuple(ZEITEN), (BASISSATZ,))

    def test_die_kopplung_braucht_je_zeitpunkt_eine_richtung(self) -> None:
        with pytest.raises(ValueError, match="genau eine Richtung"):
            gekoppeltes_bild(ZEITEN, BASISSATZ, (1, -1), hub=0.5)

    def test_der_mittelwert_steht_auch_als_jahresprozent(self) -> None:
        """Die Einheit, in der die Kipppunkte aus 250 stehen."""
        bild = flaches_bild(ZEITEN, BASISSATZ)

        assert bild.mittel_pct == pytest.approx(jahr_pct(BASISSATZ))


class TestDieRichtungKommtAusDenKursen:
    def _kurse(self, werte: list[float]) -> list[tuple[datetime, float]]:
        start = ZEITEN[0] - timedelta(days=len(werte))
        return [(start + timedelta(days=i), w) for i, w in enumerate(werte)]

    def test_gestiegen_heisst_plus_eins(self) -> None:
        kurse = self._kurse([float(i) for i in range(1, 41)])

        folge = richtungsfolge(kurse, ZEITEN[:3], fenster=5)

        assert set(folge) == {1}

    def test_gefallen_heisst_minus_eins(self) -> None:
        kurse = self._kurse([float(40 - i) for i in range(40)])

        folge = richtungsfolge(kurse, ZEITEN[:3], fenster=5)

        assert set(folge) == {-1}

    def test_vor_dem_vollen_fenster_steht_minus_eins(self) -> None:
        """Und nicht null: Ein dritter Zustand waere fuer 'gekoppeltes_bild'
        eine halbe Kopplung, und das ist eine andere Form."""
        kurse = self._kurse([1.0, 2.0, 3.0])

        folge = richtungsfolge(kurse, ZEITEN[:2], fenster=30)

        assert set(folge) == {-1}

    def test_ohne_kurs_vor_dem_zeitpunkt_steht_minus_eins(self) -> None:
        spaeter = [(ZEITEN[-1] + timedelta(days=i), float(i)) for i in range(40)]

        folge = richtungsfolge(spaeter, ZEITEN[:2], fenster=5)

        assert set(folge) == {-1}

    def test_gelesen_wird_der_kurs_vor_dem_zeitpunkt(self) -> None:
        """Funding faellt auf das an, was bis dahin bekannt ist. Ein Sprung
        **auf** dem Zeitpunkt darf die Richtung nicht mehr drehen."""
        zeit = ZEITEN[0]
        kurse = [
            (zeit - timedelta(days=i), 100.0 - i) for i in range(1, 12)
        ] + [(zeit, 0.0)]

        assert richtungsfolge(kurse, [zeit], fenster=5) == (1,)

    def test_ein_fenster_unter_eins_ist_kein_fenster(self) -> None:
        with pytest.raises(ValueError, match="mindestens einen Kurs"):
            richtungsfolge(self._kurse([1.0, 2.0]), ZEITEN[:1], fenster=0)


class TestDerVergleichUrteilt:
    def _vergleich(self, *, gefallen_gekoppelt, gezahlt_gekoppelt=110.0):
        flach = _probe(
            "flach", flaches_bild(ZEITEN, BASISSATZ),
            gefallen=("Messlatte", "Deflated Sharpe"), gezahlt=100.0,
        )
        gekoppelt = _probe(
            "gekoppelt",
            gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5),
            gefallen=gefallen_gekoppelt,
            gezahlt=gezahlt_gekoppelt,
        )
        return Ratenvergleich(BASISSATZ, (flach, gekoppelt))

    def test_die_kontrolle_ist_die_flache(self) -> None:
        assert self._vergleich(gefallen_gekoppelt=("Messlatte",)).kontrolle.name == "flach"

    def test_gleiche_gates_heissen_der_mittelwert_reicht(self) -> None:
        gleich = self._vergleich(
            gefallen_gekoppelt=("Messlatte", "Deflated Sharpe")
        )

        assert not gleich.bewegt_die_gates
        assert "Mittelwert reicht" in gleich.urteil()

    def test_andere_gates_heissen_er_reicht_nicht(self) -> None:
        anders = self._vergleich(
            gefallen_gekoppelt=("Messlatte", "Deflated Sharpe", "Schlechtestes Jahr")
        )

        assert anders.bewegt_die_gates
        assert [p.name for p in anders.abweichende] == ["gekoppelt"]
        assert "traegt das Urteil nicht" in anders.urteil()

    def test_ohne_gleichen_mittelwert_gibt_es_kein_urteil(self) -> None:
        """Der wichtigste Fall: Zahlen, die sich unterscheiden, und ein
        Vergleich, der nichts ueber die Form sagt."""
        schief = Ratenvergleich(
            BASISSATZ,
            (
                _probe("flach", flaches_bild(ZEITEN, BASISSATZ),
                       gefallen=(), gezahlt=100.0),
                _probe("doppelt", flaches_bild(ZEITEN, BASISSATZ * 2),
                       gefallen=("Drawdown",), gezahlt=200.0),
            ),
        )

        assert not schief.gleicher_mittelwert
        assert "misst die Hoehe" in schief.urteil()

    def test_ohne_kontrolle_auch_nicht(self) -> None:
        ohne = Ratenvergleich(
            BASISSATZ,
            (
                _probe(
                    "gekoppelt",
                    gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5),
                    gefallen=(), gezahlt=100.0,
                ),
            ),
        )

        assert ohne.kontrolle is None
        assert not ohne.bewegt_die_gates
        assert "Ohne flache Kontrolle" in ohne.urteil()

    def test_die_mehrzahlung_ist_der_mechanismus(self) -> None:
        """Gezahlt wird nur waehrend der Haltezeit. Liegt sie dort, wo die
        Rate hoch ist, zahlt derselbe Mittelwert mehr."""
        v = self._vergleich(gefallen_gekoppelt=("Messlatte",), gezahlt_gekoppelt=115.0)

        assert v.mehrzahlung("gekoppelt") == pytest.approx(15.0)

    def test_eine_unbekannte_form_hat_keine_mehrzahlung(self) -> None:
        v = self._vergleich(gefallen_gekoppelt=("Messlatte",))

        assert v.mehrzahlung("gibtsnicht") is None

    def test_der_kipppunkt_rechnet_sich_nicht_aus_dem_aufschlag(self) -> None:
        """**Gemessen und verworfen.** Naheliegend waere: Zahlt eine Form
        21,8 % mehr, liegt ein flacher Kipppunkt von 5,99 % schon bei
        5,99/1,218 = 4,92 %. Fuer Kopplung 0,5 trifft das (faellt bei 5,90,
        haelt bei 4,90); fuer Kopplung 1,0 nicht - sie zahlt doppelt so viel
        mehr und kippt an derselben Stelle. Deshalb gibt es hier keine
        Umrechnung: Der Kipppunkt je Form ist zu messen.
        """
        v = self._vergleich(gefallen_gekoppelt=("Messlatte",), gezahlt_gekoppelt=125.0)

        assert not hasattr(v, "umgerechneter_kipppunkt")


class TestDieGegenprobeTrenntKopplungVomSchwanken:
    """Der Kern des Befunds: dieselbe Streuung, einmal mit Bezug zur
    Marktrichtung und einmal ohne."""

    def _dreierlei(self, *, wechselnd_faellt: bool) -> Ratenvergleich:
        steht = ("Messlatte", "Deflated Sharpe")
        faellt = (*steht, "Schlechtestes Jahr")
        return Ratenvergleich(
            BASISSATZ,
            (
                _probe("flach", flaches_bild(ZEITEN, BASISSATZ),
                       gefallen=steht, gezahlt=36.23),
                _probe(
                    "wechselnd", wechselndes_bild(ZEITEN, BASISSATZ, hub=0.5),
                    gefallen=faellt if wechselnd_faellt else steht, gezahlt=36.23,
                ),
                _probe(
                    "gekoppelt",
                    gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5),
                    gefallen=faellt, gezahlt=44.11,
                ),
            ),
        )

    def test_nur_die_kopplung_bewegt_etwas(self) -> None:
        v = self._dreierlei(wechselnd_faellt=False)

        assert v.liegt_an_der_kopplung
        assert "liegt an der Kopplung" in v.urteil()

    def test_wenn_auch_das_schwanken_bewegt_liegt_es_nicht_daran(self) -> None:
        v = self._dreierlei(wechselnd_faellt=True)

        assert v.bewegt_die_gates
        assert not v.liegt_an_der_kopplung
        assert "liegt an der Kopplung" not in v.urteil()

    def test_ohne_bewegung_gibt_es_nichts_zu_trennen(self) -> None:
        steht = ("Messlatte",)
        v = Ratenvergleich(
            BASISSATZ,
            (
                _probe("flach", flaches_bild(ZEITEN, BASISSATZ),
                       gefallen=steht, gezahlt=36.0),
                _probe(
                    "gekoppelt",
                    gekoppeltes_bild(ZEITEN, BASISSATZ, RICHTUNG, hub=0.5),
                    gefallen=steht, gezahlt=44.0,
                ),
            ),
        )

        assert not v.liegt_an_der_kopplung


class TestVergleicheFaehrtDieLaeufe:
    def test_jedes_bild_wird_genau_einmal_gerechnet(self) -> None:
        gesehen: list[str] = []

        def lauf(bild: Ratenbild) -> Ratenprobe:
            gesehen.append(bild.name)
            return _probe(bild.name, bild, gefallen=(), gezahlt=100.0)

        bilder = [
            flaches_bild(ZEITEN, BASISSATZ),
            wechselndes_bild(ZEITEN, BASISSATZ, hub=0.5),
        ]

        ergebnis = vergleiche(bilder, lauf, ziel=BASISSATZ)

        assert gesehen == ["flach", "wechselnd"]
        assert len(ergebnis.proben) == 2
        assert ergebnis.gleicher_mittelwert
