"""Das Termin-Overlay: Wann wird nicht eingestiegen?

Zwei Tests tragen den Rest:

* ``test_eine_zeile_ohne_datum_verschiebt_nichts`` - der Fehler, der mir beim
  Bauen fast passiert waere. Monate und Daten als zwei getrennte Listen zu
  lesen, laeuft auf echten Daten auseinander, und zwar lautlos.
* ``TestSperre.test_termin_in_der_kerze_sperrt`` - die Regel, die das Overlay
  ohne eine einzige einstellbare Zahl fuer jedes Intervall richtig macht.

Der HTML-Ausschnitt in ``tests/fixtures/fomc_kalender.html`` stammt
unveraendert von federalreserve.gov. Ein selbst erfundenes Beispiel haette
genau die Eigenheit nicht gehabt, um die es geht.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from core.config import RiskSettings
from core.models import Instrument
from data.termine import (
    Termin,
    Terminart,
    Terminkalender,
    fomc_angekuendigt_aus_html,
    fomc_aus_html,
    fomc_besondere_tage,
    halbierung_aus_bloecken,
    hole_termine,
    planmaessig,
)
from execution.risk import RiskOfficer, Vetoed, VetoReason
from tests.factories import make_signal

FIXTURE = Path(__file__).parent / "fixtures" / "fomc_kalender.html"


@pytest.fixture
def fed_html() -> str:
    return FIXTURE.read_text()


# ---------------------------------------------------------------------------
#  Die Fed-Seite lesen
# ---------------------------------------------------------------------------
class TestFedSeite:
    def test_pressemitteilungen_ergeben_entscheidungstage(self, fed_html: str) -> None:
        """Der Dateiname der Erklaerung ist der Tag der Veroeffentlichung.

        Genauer als die Sitzungsangabe im Text, die nur einen Bereich nennt.
        """
        zeiten = fomc_aus_html(fed_html)

        assert zeiten
        assert all(z.tzinfo is not None for z in zeiten)
        assert zeiten == sorted(zeiten)

    def test_sommerzeit_wird_beruecksichtigt(self, fed_html: str) -> None:
        """14:00 New York sind je nach Jahreszeit 18:00 oder 19:00 UTC.

        Eine feste Umrechnung waere die Haelfte des Jahres um eine Stunde
        daneben - bei einer 15-Minuten-Strategie sind das vier Kerzen.
        """
        zeiten, _ = fomc_angekuendigt_aus_html(fed_html)
        winter = [z for z in zeiten if z.month in (1, 2, 12)]
        sommer = [z for z in zeiten if z.month in (6, 7, 8)]

        assert winter and sommer
        assert all(z.hour == 19 for z in winter)
        assert all(z.hour == 18 for z in sommer)

    def test_eine_zeile_ohne_datum_verschiebt_nichts(self, fed_html: str) -> None:
        """**Der wichtigste Test dieser Datei.**

        Das Jahr 2025 hat auf der Fed-Seite eine August-Zeile ohne
        Datumsangabe. Wer Monate und Daten als zwei parallele Listen liest,
        bekommt neun Monate und acht Daten - und ab August ist alles um einen
        Termin verschoben: September haette den Oktobertermin bekommen.

        So sah es aus, bevor ich nachgezaehlt habe:

            naiv        September 2025 -> 28./29.
            zeilenweise September 2025 -> 16./17.

        Ein Fehler, der nirgends auffaellt und jeden Termin um Wochen
        verschiebt. Gefunden nur, weil die Zahlen nicht zusammenpassten.
        """
        zeiten, uebersprungen = fomc_angekuendigt_aus_html(fed_html)

        assert uebersprungen == 1, "Die Zeile ohne Datum muss zaehlbar sein"
        september = [z for z in zeiten if z.year == 2025 and z.month == 9]
        assert september, "September 2025 fehlt"
        assert september[0].day == 17, (
            "Sitzung 16.-17. September, Entscheidung am 17. - nicht der "
            "Oktobertermin"
        )

    def test_monatswechsel_landet_im_zweiten_monat(self, fed_html: str) -> None:
        """'Jan/Feb 31-1' heisst: Entscheidung am 1. Februar."""
        zeiten, _ = fomc_angekuendigt_aus_html(fed_html)

        februar = [z for z in zeiten if z.year == 2023 and z.month == 2]
        assert februar and februar[0].day == 1

    def test_leeres_html_wirft_nicht(self) -> None:
        assert fomc_aus_html("") == []
        assert fomc_angekuendigt_aus_html("") == ([], 0)


class TestPlanmaessig:
    """Was ausserplanmaessig war, sagt die Quelle - nicht meine Formel.

    Hier stand zuerst eine Schaetzung: weniger als drei Wochen Abstand zum
    vorigen Termin heisst kurzfristig einberufen. Der Test unten ist damit
    durchgefallen, und zwar zu Recht - der 3. Maerz 2020 liegt 34 Tage nach
    dem 29. Januar und war trotzdem eine Notfallsitzung. Die Fed-Seite schreibt
    ``(unscheduled)`` daneben; genau das wird jetzt gelesen.
    """

    def test_gekennzeichnete_tage_gelten_als_ausserplanmaessig(self) -> None:
        """Im Maerz 2020 gab es vier Fed-Mitteilungen in einem Monat.

        Genau die waren die Tage mit den groessten Ausschlaegen - sie duerfen
        nicht fehlen, nur weil sie nicht im Sitzungskalender standen.
        """
        zeiten = [
            datetime(2020, 1, 29, 19, tzinfo=UTC),
            datetime(2020, 3, 3, 19, tzinfo=UTC),
            datetime(2020, 3, 15, 18, tzinfo=UTC),
            datetime(2020, 4, 29, 18, tzinfo=UTC),
        ]
        # So steht es auf der Fed-Seite: "March 2 (unscheduled) Meeting",
        # "March 15 (unscheduled) Meeting". Die Erklaerung zur Sitzung vom
        # 2. Maerz erschien am 3.
        besondere = {date(2020, 3, 2), date(2020, 3, 15)}

        ergebnis = planmaessig(zeiten, besondere)

        assert ergebnis[zeiten[0]] is True
        assert ergebnis[zeiten[1]] is False, "Erklaerung am Tag nach der Sitzung"
        assert ergebnis[zeiten[2]] is False
        assert ergebnis[zeiten[3]] is True

    def test_ohne_kennzeichnung_gilt_planmaessig(self) -> None:
        """Die vorsichtige Richtung: Die Angabe steht nur in der Beschreibung,
        gesperrt wird jeder Termin gleich."""
        z = datetime(2020, 3, 3, 19, tzinfo=UTC)

        assert planmaessig([z]) == {z: True}

    def test_markierungen_werden_aus_der_seite_gelesen(self) -> None:
        html = (
            '<a href="/monetarypolicy/fomchistorical2020.htm">x</a>'
            "<h5>March 15 (unscheduled) Meeting - 2020</h5>"
            "<h5>April 28-29 Meeting - 2020</h5>"
            "<h5>August 27 (notation vote) - 2020</h5>"
        )

        tage = fomc_besondere_tage(html)

        assert date(2020, 3, 15) in tage
        assert date(2020, 8, 27) in tage
        assert date(2020, 4, 29) not in tage, "Eine normale Sitzung ist nicht besonders"

    def test_leere_liste(self) -> None:
        assert planmaessig([]) == {}


class TestHalbierung:
    def test_blockzeit_wird_gelesen(self) -> None:
        bloecke = [{"height": 840000, "timestamp": 1713571767}]

        assert halbierung_aus_bloecken(bloecke, 840000) == datetime(
            2024, 4, 20, 0, 9, 27, tzinfo=UTC
        )

    def test_fehlender_block_wirft(self) -> None:
        with pytest.raises(ValueError, match="nicht in der Antwort"):
            halbierung_aus_bloecken([{"height": 1}], 840000)


# ---------------------------------------------------------------------------
#  Die Sperrregel
# ---------------------------------------------------------------------------
def kalender(*zeitpunkte: datetime) -> Terminkalender:
    return Terminkalender(
        [Termin(zeitpunkt=z, art=Terminart.FOMC, beschreibung="Test") for z in zeitpunkte]
    )


class TestSperre:
    """Eine Regel fuer alle Intervalle - ohne einstellbare Zahl je Intervall.

    Gesperrt wird, wenn ein Termin im Fenster
    ``[jetzt - Kerzenlaenge - Vorlauf, jetzt + Nachlauf]`` liegt.
    """

    def test_termin_in_der_kerze_sperrt(self) -> None:
        """Faellt der Termin in die Kerze, auf die gehandelt wird: nicht handeln.

        Der Teil, ohne den das Overlay auf Tageskerzen **nichts** taete: Eine
        Fed-Entscheidung um 18:00 UTC liegt sechs Stunden vor dem
        Mitternachtsschluss - mit 60 Minuten Vorlauf allein wuerde sie nie
        greifen.
        """
        fed = datetime(2026, 3, 18, 18, tzinfo=UTC)
        schluss = datetime(2026, 3, 19, tzinfo=UTC)  # Tagesschluss danach

        treffer = kalender(fed).sperre(schluss, spanne=timedelta(days=1))

        assert treffer is not None

    def test_ohne_kerzenlaenge_greift_nur_der_vorlauf(self) -> None:
        """Zum Gegenbeweis: dieselbe Lage, aber ohne die Kerzenregel."""
        fed = datetime(2026, 3, 18, 18, tzinfo=UTC)
        schluss = datetime(2026, 3, 19, tzinfo=UTC)

        assert kalender(fed).sperre(schluss, spanne=timedelta(0)) is None

    def test_vorlauf_sperrt(self) -> None:
        fed = datetime(2026, 3, 18, 18, tzinfo=UTC)
        vorher = datetime(2026, 3, 18, 17, 15, tzinfo=UTC)

        assert kalender(fed).sperre(vorher, spanne=timedelta(minutes=15)) is not None

    def test_nachlauf_sperrt(self) -> None:
        fed = datetime(2026, 3, 18, 18, tzinfo=UTC)
        danach = datetime(2026, 3, 18, 17, 15, tzinfo=UTC)

        assert kalender(fed).sperre(danach, spanne=timedelta(minutes=15)) is not None

    def test_weit_weg_sperrt_nicht(self) -> None:
        fed = datetime(2026, 3, 18, 18, tzinfo=UTC)
        spaeter = datetime(2026, 3, 20, 12, tzinfo=UTC)

        assert kalender(fed).sperre(spaeter, spanne=timedelta(minutes=15)) is None

    def test_leerer_kalender_sperrt_nie(self) -> None:
        assert Terminkalender().sperre(datetime.now(UTC)) is None

    def test_naechster_termin(self) -> None:
        a = datetime(2026, 3, 18, 18, tzinfo=UTC)
        b = datetime(2026, 4, 29, 18, tzinfo=UTC)

        k = kalender(b, a)  # absichtlich unsortiert hereingegeben

        assert k.naechster(datetime(2026, 3, 1, tzinfo=UTC)) == k.termine[0]
        assert k.naechster(datetime(2026, 4, 1, tzinfo=UTC)).zeitpunkt == b
        assert k.naechster(datetime(2027, 1, 1, tzinfo=UTC)) is None


class TestDatei:
    def test_speichern_und_laden(self, tmp_path: Path) -> None:
        original = Terminkalender(
            [
                Termin(
                    zeitpunkt=datetime(2026, 3, 18, 18, tzinfo=UTC),
                    art=Terminart.FOMC,
                    beschreibung="FOMC-Entscheidung",
                    geplant=True,
                )
            ],
            quelle="test",
        )
        original.speichern(tmp_path / "termine.json")

        geladen = Terminkalender.laden(tmp_path / "termine.json")

        assert len(geladen) == 1
        assert geladen.termine[0] == original.termine[0]
        assert geladen.quelle == "test"

    def test_fehlende_datei_ergibt_leeren_kalender(self, tmp_path: Path) -> None:
        """Ein Overlay ist eine Verbesserung, keine Voraussetzung.

        Wer hier wirft, legt den Handel lahm, weil eine Datei fehlt.
        """
        assert len(Terminkalender.laden(tmp_path / "gibtsnicht.json")) == 0

    def test_kaputte_datei_ergibt_leeren_kalender(self, tmp_path: Path) -> None:
        datei = tmp_path / "termine.json"
        datei.write_text("{kaputt")

        assert len(Terminkalender.laden(datei)) == 0

    def test_bericht_ohne_termine_behauptet_nichts(self) -> None:
        assert "Kein Terminkalender" in Terminkalender().bericht()


class TestAbruf:
    """Der Zusammenbau - ohne Netz, mit vorgegebenen Antworten."""

    def test_beide_quellen_werden_zusammengefuehrt(self, fed_html: str) -> None:
        def text(url: str) -> str:
            if "fomccalendars" in url:
                return fed_html
            raise RuntimeError("keine Historie in diesem Test")

        def js(url: str):
            return [{"height": 840000, "timestamp": 1713571767}]

        k = hole_termine(text, js, von_jahr=2025, bis_jahr=2025)

        arten = {t.art for t in k.termine}
        assert Terminart.FOMC in arten
        assert Terminart.HALBIERUNG in arten

    def test_ausfall_einer_quelle_leert_den_kalender_nicht(self, fed_html: str) -> None:
        """Ein halber Kalender sperrt weniger als ein voller, aber mehr als keiner."""

        def text(url: str) -> str:
            if "fomccalendars" in url:
                return fed_html
            raise RuntimeError("weg")

        def js(url: str):
            raise RuntimeError("auch weg")

        k = hole_termine(text, js, von_jahr=2025, bis_jahr=2025)

        assert k
        assert all(t.art is Terminart.FOMC for t in k.termine)

    def test_pressemitteilung_schlaegt_ankuendigung(self, fed_html: str) -> None:
        """Fuer denselben Tag darf nicht zweimal derselbe Termin entstehen."""

        def text(url: str) -> str:
            if "fomccalendars" in url:
                return fed_html
            raise RuntimeError("weg")

        k = hole_termine(text, lambda url: [], von_jahr=2025, bis_jahr=2025)

        tage = [t.zeitpunkt.date() for t in k.termine]
        assert len(tage) == len(set(tage))


# ---------------------------------------------------------------------------
#  Der Weg in den Handel
# ---------------------------------------------------------------------------
class TestRiskOfficer:
    """Der Kalender geht durch ``blockade`` - dieselbe Stelle wie im Backtest.

    Ein Overlay, das nur im Betrieb sperrt, waere eine weitere Abweichung
    zwischen Backtest und Handel. Fuenf davon sind in diesem Projekt bereits
    gefunden worden, alle aus zwei Umsetzungen derselben Sache.
    """

    @pytest.fixture
    def officer(self, btcusdt: Instrument, risk: RiskSettings) -> RiskOfficer:
        fed = datetime(2026, 3, 18, 18, tzinfo=UTC)
        return RiskOfficer(
            risk,
            btcusdt,
            clock=lambda: datetime(2026, 3, 18, 17, 30, tzinfo=UTC),
            kalender=kalender(fed),
            kerzenspanne=timedelta(minutes=15),
        )

    def test_veto_kurz_vor_dem_termin(self, officer: RiskOfficer) -> None:
        entscheidung = officer.blockade()

        assert isinstance(entscheidung, Vetoed)
        assert entscheidung.reason is VetoReason.NEWS_BLACKOUT

    def test_signal_wird_abgelehnt(self, officer: RiskOfficer) -> None:
        entscheidung = officer.evaluate(make_signal(), equity=Decimal("500"))

        assert isinstance(entscheidung, Vetoed)
        assert entscheidung.reason is VetoReason.NEWS_BLACKOUT

    def test_ohne_kalender_kein_veto(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        officer = RiskOfficer(
            risk, btcusdt, clock=lambda: datetime(2026, 3, 18, 17, 30, tzinfo=UTC)
        )

        assert officer.blockade() is None

    def test_ausserhalb_des_fensters_kein_veto(
        self, btcusdt: Instrument, risk: RiskSettings
    ) -> None:
        officer = RiskOfficer(
            risk,
            btcusdt,
            clock=lambda: datetime(2026, 3, 20, 12, tzinfo=UTC),
            kalender=kalender(datetime(2026, 3, 18, 18, tzinfo=UTC)),
            kerzenspanne=timedelta(minutes=15),
        )

        assert officer.blockade() is None

    def test_fenster_kommt_aus_den_einstellungen(self, btcusdt: Instrument) -> None:
        """Die Vorlaufzeit ist eine Einstellung, keine Zahl im Code."""
        eng = RiskSettings(news_blackout_before_min=5, news_blackout_after_min=5)
        officer = RiskOfficer(
            eng,
            btcusdt,
            clock=lambda: datetime(2026, 3, 18, 17, 30, tzinfo=UTC),
            kalender=kalender(datetime(2026, 3, 18, 18, tzinfo=UTC)),
            kerzenspanne=timedelta(minutes=15),
        )

        assert officer.blockade() is None, "5 Minuten Vorlauf reichen nicht bis 18:00"


def test_termindatei_liegt_im_repo() -> None:
    """Der geholte Kalender ist eingecheckt - und zwar unter ``referenz/``,
    nicht unter ``state/``.

    ``state/`` ist nicht im Repository, weil der Betriebszustand
    maschinenspezifisch ist. Ein Terminkalender dort haette geheissen: Dieser
    Rechner sperrt 80 Termine, der des Nutzers keinen - und der Backtest
    lieferte auf beiden ein anderes Ergebnis."""
    datei = Path(__file__).parent.parent / "referenz" / "termine.json"
    if not datei.exists():
        pytest.skip("noch nicht geholt - 'python -m cli termine' ausfuehren")

    daten = json.loads(datei.read_text())

    assert daten["termine"], "Leerer Kalender waere schlimmer als keiner"
    assert daten["quelle"], "Ohne Herkunft ist eine Datei mit Terminen nur eine Behauptung"
