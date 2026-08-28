"""Was muesste ein neuer Einfall koennen - und ist je etwas so weit gekommen?

Die gemessene Lage der Spitzengruppe:

    Kandidat                            Trades   Sharpe je Trade
    Trend-Beteiligung (fair gerechnet)      46            0,3583
    Trend mit Vola-Ziel 22 %                51            0,3559
    Trend 50 Tage mit Konfluenz            152            0,2597   <- Kandidat

Der Spitzenkandidat hat die schlechteste Qualitaet je Trade und kommt trotzdem
am weitesten, weil er dreimal so oft handelt. Genau deshalb ist weder die
Trade-Zahl noch der Sharpe allein ein Massstab - nur die Linie aus beiden.

Zwei Tests tragen die Datei:

* ``test_naechster_geht_nach_faktor_nicht_nach_differenz`` - eine Luecke von
  0,05 wiegt bei einem Sharpe von 0,25 schwerer als bei 0,8.
* ``test_zu_wenige_trades_sind_unerreichbar`` - bei kleinen Stichproben
  genuegt **kein** Sharpe. Das als "sehr grosse Luecke" auszuweisen waere
  falsch; es ist eine andere Aussage.
"""

from __future__ import annotations

import pytest

from research.suchbudget import Budget, Kandidat


def _budget(*kandidaten: Kandidat, versuche: int = 112) -> Budget:
    return Budget(versuche=versuche, kandidaten=list(kandidaten))


class TestLinie:
    def test_mehr_trades_verlangen_weniger_qualitaet(self) -> None:
        b = _budget()

        werte = [w for _, w in b.linie((50, 100, 200, 400)) if w is not None]

        assert len(werte) >= 3
        assert werte == sorted(werte, reverse=True)

    def test_mehr_versuche_heben_die_linie(self) -> None:
        """**Der Kern der ganzen Rechnung.**

        Gesucht wird gegen ein Ziel, das sich beim Suchen entfernt.
        """
        b = _budget()

        jetzt = b.noetig_bei(152)
        spaeter = b.noetig_bei(152, versuche=b.versuche + 100)

        assert jetzt is not None and spaeter is not None
        assert spaeter > jetzt

    def test_preis_eines_einfalls_ist_positiv(self) -> None:
        b = _budget()

        preis = b.kosten_je_versuch(152)

        assert preis is not None and preis > 0

    def test_tabelle_nennt_unerreichbares_als_solches(self) -> None:
        b = _budget()

        text = b.tabelle(trades=(3, 152))

        assert "unerreichbar" in text
        assert "152" in text


class TestAbstand:
    def test_gemessene_lage_des_spitzenkandidaten(self) -> None:
        """152 Trades zu je 0,2597 - noetig sind rund 0,28."""
        b = _budget(Kandidat("Trend 50 Tage mit Konfluenz", 152, 0.2597))

        (a,) = b.abstaende()

        assert a.erreichbar
        assert a.noetig is not None
        assert 0.26 < a.noetig < 0.31, f"gemessen {a.noetig}"
        assert a.luecke is not None and a.luecke > 0
        assert a.faktor is not None and 1.0 < a.faktor < 1.3

    def test_naechster_geht_nach_faktor_nicht_nach_differenz(self) -> None:
        """**Eine Luecke von 0,05 wiegt nicht ueberall gleich.**

        Der Kandidat mit der kleineren absoluten Luecke ist nicht der naehere,
        wenn seine Qualitaet je Trade viel niedriger liegt.
        """
        b = _budget(
            Kandidat("Wenig Trades, hoher Sharpe", 50, 0.60),
            Kandidat("Viele Trades, mittlerer Sharpe", 152, 0.2597),
        )

        nah = b.naechster

        assert nah is not None
        # Welcher gewinnt, entscheidet der Faktor - und der wird hier geprueft,
        # nicht behauptet.
        faktoren = {a.kandidat.name: a.faktor for a in b.abstaende()}
        bester = min(
            (n for n, f in faktoren.items() if f is not None),
            key=lambda n: faktoren[n],
        )
        assert nah.kandidat.name == bester

    def test_zu_wenige_trades_sind_unerreichbar(self) -> None:
        """Bei kleinen Stichproben genuegt **kein** Sharpe - das ist eine
        andere Aussage als 'sehr weit weg'."""
        b = _budget(Kandidat("Fast nie", 4, 0.9))

        (a,) = b.abstaende()

        assert not a.erreichbar
        assert a.luecke is None
        assert a.faktor is None

    def test_urteil_nennt_die_unerreichbaren(self) -> None:
        b = _budget(
            Kandidat("Fast nie", 4, 0.9),
            Kandidat("Kandidat", 152, 0.2597),
        )

        text = b.urteil()

        assert "kein** Sharpe genuegen" in text
        assert "Kandidat" in text

    def test_urteil_nennt_den_preis_des_suchens(self) -> None:
        b = _budget(Kandidat("Kandidat", 152, 0.2597))

        assert "entfernt" in b.urteil()

    def test_ohne_kandidaten(self) -> None:
        assert "kein Urteil" in Budget(versuche=112).urteil()

    def test_alle_unerreichbar(self) -> None:
        b = _budget(Kandidat("a", 3, 0.5), Kandidat("b", 4, 0.5))

        assert b.naechster is None
        assert "ueberhaupt erreichbar" in b.urteil()


class TestSpitzengruppe:
    def test_wenige_gute_trades_reichen_nicht_gegen_viele_mittlere(self) -> None:
        """**Die Form des Befunds.**

        0,3583 bei 46 Trades ist je Trade klar besser als 0,2597 bei 152 - und
        trotzdem weiter vom Gate entfernt.
        """
        b = _budget(
            Kandidat("Trend-Beteiligung (fair gerechnet)", 46, 0.3583),
            Kandidat("Trend 50 Tage mit Konfluenz", 152, 0.2597),
        )

        nach_name = {a.kandidat.name: a for a in b.abstaende()}
        wenige = nach_name["Trend-Beteiligung (fair gerechnet)"]
        viele = nach_name["Trend 50 Tage mit Konfluenz"]

        assert wenige.kandidat.sharpe_je_trade > viele.kandidat.sharpe_je_trade
        if wenige.faktor is not None and viele.faktor is not None:
            assert viele.faktor < wenige.faktor
        else:
            assert wenige.faktor is None  # noch schlimmer: gar nicht erreichbar

    def test_schiefe_und_woelbung_gehen_ein(self) -> None:
        """Eine Normalverteilung anzunehmen waere hier deutlich zu freundlich."""
        normal = Budget(versuche=112, schiefe=0.0, woelbung=3.0)
        echt = Budget(versuche=112)

        a = normal.noetig_bei(152)
        b = echt.noetig_bei(152)

        assert a is not None and b is not None
        assert a != pytest.approx(b)


# ---------------------------------------------------------------------------
#  Die Form der Verteilung
# ---------------------------------------------------------------------------
class FakeTrade:
    def __init__(self, pnl: float) -> None:
        self.net_pnl = pnl


class TestEigeneForm:
    """**Jeder Kandidat wird an seiner eigenen Verteilung gemessen.**

    Schiefe und Woelbung gehen in den Deflated Sharpe ein, und zwar kraeftig:
    Beim Spitzenkandidaten steht im Nenner der Formel 0,597 statt der 1,016
    einer Normalverteilung. Bis hierher galten seine Werte fuer **alle** -
    eine Regel mit anderer Form bekam damit die Anforderung eines fremden
    Genoms genannt.
    """

    def _trades(self, werte: list[float]) -> list[FakeTrade]:
        return [FakeTrade(w) for w in werte]

    def test_aus_trades_misst_alle_vier_groessen(self) -> None:
        from research.suchbudget import Kandidat

        # Wenige grosse Gewinner, viele kleine Verluste - die Form des
        # Spitzenkandidaten im Kleinen.
        eintrag = Kandidat.aus_trades("Probe", self._trades([-1.0] * 18 + [20.0, 15.0]))

        assert eintrag is not None
        assert eintrag.trades == 20
        assert eintrag.schiefe > 1.0
        assert eintrag.woelbung > 3.0

    def test_zu_duenne_liste_gibt_nichts(self) -> None:
        from research.suchbudget import Kandidat

        assert Kandidat.aus_trades("Wenig", self._trades([1.0, 2.0])) is None

    def test_ohne_streuung_gibt_nichts(self) -> None:
        """Ein Sharpe ohne Streuung im Nenner waere unendlich - und die
        Grenzlinie behauptete dann, jeder Kandidat sei zugelassen."""
        from research.suchbudget import Kandidat

        assert Kandidat.aus_trades("Flach", self._trades([1.0] * 10)) is None

    def test_die_form_veraendert_die_anforderung(self) -> None:
        """**Der entscheidende Test.**

        Zwei Kandidaten, gleiche Trade-Zahl, gleiche Qualitaet je Trade - nur
        andere Verteilungsform. Wuerde die Form ignoriert, saehen beide
        dieselbe Anforderung. Sie tun es nicht, und der Unterschied ist gross.
        """
        from research.suchbudget import Budget, Kandidat

        schief = Kandidat("Schief", 150, 0.26, schiefe=3.5, woelbung=16.0)
        normal = Kandidat("Normal", 150, 0.26, schiefe=0.0, woelbung=3.0)
        budget = Budget(versuche=151, kandidaten=[schief, normal])

        a, b = budget.abstaende()

        assert a.noetig is not None and b.noetig is not None
        assert a.noetig < b.noetig, (
            "Ein langes rechtes Ende senkt die Huerde - sonst wirkt die Form "
            "nicht"
        )

    def test_ohne_angabe_gilt_die_voreinstellung(self) -> None:
        """Ein Kandidat ohne gemessene Form faellt auf die Voreinstellung
        zurueck - das ist eine Naeherung, aber eine benannte."""
        from research.suchbudget import SCHIEFE, WOELBUNG, Budget, Kandidat

        ohne = Kandidat("Ohne Form", 150, 0.26)
        mit = Kandidat("Mit Form", 150, 0.26, schiefe=SCHIEFE, woelbung=WOELBUNG)
        budget = Budget(versuche=151, kandidaten=[ohne, mit])

        a, b = budget.abstaende()

        assert a.noetig == pytest.approx(b.noetig)


class TestHebel:
    """Woran das haerteste Gate haengt - je Eingang einzeln."""

    def _kandidat(self):
        from research.suchbudget import Kandidat

        return Kandidat("Spitze", 154, 0.2569, schiefe=3.466, woelbung=15.962)

    def test_alle_vier_eingaenge_kommen_vor(self) -> None:
        from research.suchbudget import Budget

        namen = [h.name for h in Budget(versuche=151).hebel(self._kandidat())]

        assert namen == [
            "Qualitaet je Trade",
            "unabhaengige Trades",
            "Schiefe",
            "Woelbung",
        ]

    def test_die_woelbung_allein_reicht_nicht(self) -> None:
        """**Sie kann nicht unter 1 - das ist keine Meinung, sondern die
        untere Schranke jeder Verteilung.** Ein Weg, der dort endet, ist
        geschlossen, und das muss dranstehen statt einer Zahl."""
        from research.suchbudget import Budget

        woelbung = next(
            h for h in Budget(versuche=151).hebel(self._kandidat())
            if h.name == "Woelbung"
        )

        assert not woelbung.moeglich
        assert "unerreichbar" in str(woelbung)

    def test_die_offenen_wege_tragen_eine_zahl(self) -> None:
        """**Frueher waren es drei.** Der dritte war die Schiefe.

        Die Rechnung loest je Groesse einzeln, *alles andere unveraendert* -
        und genau das geht bei Schiefe und Woelbung nicht: Fuer jede
        Verteilung gilt ``Woelbung >= Schiefe^2 + 1``. Der so gefundene
        Schiefe-Zielpunkt verlangt eine Woelbung ueber 20 bei festgehaltenen
        15,7; diese Form gibt es nicht (Befund 70).
        """
        from research.suchbudget import Budget

        offen = [h for h in Budget(versuche=151).hebel(self._kandidat()) if h.moeglich]

        assert [h.name for h in offen] == ["Qualitaet je Trade", "unabhaengige Trades"]
        for h in offen:
            assert h.noetig > h.jetzt
            assert h.veraenderung > 0

    def test_die_schiefe_meldet_ihren_grund_statt_einer_zahl(self) -> None:
        """Ein Weg, den es nicht gibt, muss als solcher dastehen - sonst
        sucht jemand danach. Und zwar mit dem Grund, nicht nur mit einem
        Vermerk."""
        from research.formgrenze import mindestwoelbung
        from research.suchbudget import WOELBUNG, Budget

        schiefe = next(
            h for h in Budget(versuche=151).hebel(self._kandidat())
            if h.name == "Schiefe"
        )

        assert schiefe.noetig is not None
        assert mindestwoelbung(schiefe.noetig) > WOELBUNG, "Sonst waere er moeglich"
        assert not schiefe.moeglich
        assert "braucht Woelbung" in str(schiefe)

    def test_mehr_versuche_verlangen_mehr(self) -> None:
        """Der Preis des Suchens, an derselben Stelle sichtbar."""
        from research.suchbudget import Budget

        def qualitaet(versuche: int) -> float:
            return next(
                h.noetig for h in Budget(versuche=versuche).hebel(self._kandidat())
                if h.name == "Qualitaet je Trade"
            )

        assert qualitaet(300) > qualitaet(151)


class TestEineUmsetzung:
    def test_die_schwelle_kommt_aus_der_gate_definition(self) -> None:
        """Nicht danebengeschrieben: Wer sie in ``gates.py`` aendert, aendert
        sie hier mit."""
        from research.gates import GateThresholds
        from research.suchbudget import ZIEL

        assert GateThresholds().min_deflated_sharpe == ZIEL

    def test_die_cli_hilfsfunktion_rechnet_nicht_selbst(self) -> None:
        """Dieselbe Groesse stand an drei Stellen. Jetzt an einer, und der
        Rest reicht durch."""
        from cli import _sharpe_je_trade
        from research.suchbudget import Kandidat

        trades = [FakeTrade(w) for w in [-1.0] * 18 + [20.0, 15.0]]
        eintrag = Kandidat.aus_trades("Probe", trades)

        assert eintrag is not None
        assert _sharpe_je_trade(trades) == pytest.approx(eintrag.sharpe_je_trade)


class TestHebelerklaerung:
    """Der Satz neben der Rechnung - abgeleitet statt festgeschrieben.

    In ``cli stand`` stand bis Befund 109 fest verdrahtet:

        *"Die Woelbung kann nicht unter 1 fallen. Damit bleibt von den vier
        Wegen einer: die Qualitaet je Trade."*

    Er war schon vor Befund 108 falsch - die Zahl der offenen Wege war zwei,
    nicht einer -, und mit dem Wegfall des Funding wurde er zusaetzlich
    veraltet. Ein fester Satz neben einer gerechneten Zahl, dieselbe Drift wie
    beim Standardintervall (Befund 103) und beim Gate-Docstring (Befund 101).
    """

    def hebel(self, **abweichung):
        from research.suchbudget import Hebel

        daten = {
            "qualitaet": Hebel("Qualitaet je Trade", 0.2765, 0.2987),
            "trades": Hebel("unabhaengige Trades", 152.0, 181.4),
            "schiefe": Hebel(
                "Schiefe", 3.409, 4.079,
                unmoeglich_weil="braucht Woelbung >= 17.6, hier 15.5",
            ),
            "woelbung": Hebel("Woelbung", 15.478, 5.791, kleiner_ist_besser=True),
        }
        daten.update(abweichung)
        return list(daten.values())

    def test_die_zahl_der_offenen_wege_kommt_aus_der_zerlegung(self) -> None:
        """**Der Test dieser Klasse.**

        Unter Spot sind drei Wege offen, nicht einer. Der feste Satz haette
        weiter "einer" behauptet.
        """
        from research.suchbudget import Budget

        text = Budget.hebelerklaerung(self.hebel())

        assert "3 von 4 Wegen sind offen" in text
        assert "Qualitaet je Trade" in text
        assert "Woelbung" in text

    def test_der_leichteste_weg_wird_benannt(self) -> None:
        from research.suchbudget import Budget

        text = Budget.hebelerklaerung(self.hebel())

        assert "Am wenigsten verlangt Qualitaet je Trade: +8%" in text

    def test_ein_unmoeglicher_weg_traegt_seinen_grund(self) -> None:
        """Ein Weg, den es nicht gibt, muss als solcher dastehen - sonst sucht
        jemand danach."""
        from research.suchbudget import Budget

        text = Budget.hebelerklaerung(self.hebel())

        assert "Schiefe: braucht Woelbung >= 17.6, hier 15.5" in text

    def test_ein_unerreichbarer_weg_ohne_grund_bekommt_einen(self) -> None:
        from research.suchbudget import Budget, Hebel

        text = Budget.hebelerklaerung(
            self.hebel(woelbung=Hebel("Woelbung", 15.7, None, kleiner_ist_besser=True))
        )

        assert "2 von 4 Wegen sind offen" in text
        assert "Woelbung: kein Wert dieser Groesse laesst das Gate halten" in text

    def test_wenn_nichts_offen_ist_wird_das_gesagt(self) -> None:
        from research.suchbudget import Budget, Hebel

        text = Budget.hebelerklaerung(
            [Hebel("A", 1.0, None), Hebel("B", 1.0, None)]
        )

        assert "Keiner der vier Wege ist offen" in text

    def test_ohne_zerlegung_wird_nichts_behauptet(self) -> None:
        from research.suchbudget import Budget

        assert "nichts zu erklaeren" in Budget.hebelerklaerung([])

    def test_der_fuenfte_eingang_bleibt_benannt(self) -> None:
        """Die geratene Streuung ist kein Weg - sie zu bewegen hiesse, die
        Huerde zu verstellen statt den Kandidaten."""
        from research.suchbudget import Budget

        text = Budget.hebelerklaerung(self.hebel())

        assert "vier von fuenf" in text
        assert "Huerde zu verstellen statt den Kandidaten" in text

    def test_cli_stand_schreibt_den_satz_nicht_mehr_selbst(self) -> None:
        """Die Ursache, nicht das Symptom."""
        from pathlib import Path

        import cli

        quelle = Path(cli.__file__).read_text()

        assert "hebelerklaerung(" in quelle
        assert "bleibt von den vier Wegen" not in quelle


class TestDerZweiteBetriebspunkt:
    """Befund 126 - die Kandidaten tragen Perpetual-Zahlen.

    Die Bestenliste kennt nur einen Betriebspunkt. Seit Befund 108 ist Spot
    der bessere gemessene, und ohne ihn steht im Urteil ein Faktor, der eine
    Kostenannahme mittraegt: **1,15 statt 1,08.**
    """

    def _budget(self, **kw) -> Budget:
        werte = dict(
            versuche=198,
            kandidaten=[
                Kandidat(
                    name="Trend 50 Tage mit Konfluenz",
                    trades=152,
                    sharpe_je_trade=0.2597,
                    schiefe=3.47,
                    woelbung=15.95,
                )
            ],
        )
        werte.update(kw)
        return Budget(**werte)

    def test_ohne_spotguete_bleibt_das_urteil_wie_zuvor(self) -> None:
        """``None`` heisst "nicht gemessen", nicht "kein Unterschied"."""
        text = self._budget().urteil()

        assert "Am naechsten kam" in text
        assert "Spot-Bedingungen" not in text

    def test_mit_spotguete_steht_der_zweite_faktor_daneben(self) -> None:
        text = self._budget(spotguete=0.2765).urteil()

        assert "Spot-Bedingungen" in text
        assert "0.2765" in text
        assert "Kostenannahme" in text

    def test_der_spotfaktor_ist_kleiner(self) -> None:
        """Das ist der ganze Punkt - die Aufgabe ist dort kleiner."""
        import re

        text = self._budget(spotguete=0.2765).urteil()
        faktoren = [
            float(x) for x in re.findall(r"Faktor (?:mindestens )?(\d\.\d\d)", text)
        ]

        assert len(faktoren) == 2
        assert faktoren[1] < faktoren[0]
        assert faktoren == [pytest.approx(1.15, abs=0.01), pytest.approx(1.08, abs=0.01)]

    def test_ohne_gemessene_stichprobe_heisst_es_mindestens(self) -> None:
        """Der Kandidat oben traegt nur die rohe Trade-Zahl (Befund 139).

        Dann ist die Latte eine Untergrenze, und **beide** Faktoren sind es
        auch - der zweite teilt durch dieselbe Latte.
        """
        text = self._budget(spotguete=0.2765).urteil()

        assert text.count("Faktor mindestens") == 2
        assert "nicht gemessen" in text

    def test_mit_gemessener_stichprobe_faellt_das_mindestens_weg(self) -> None:
        """Und die Latte liegt dann hoeher - das ist der ganze Unterschied."""
        gemessen = Budget(
            versuche=198,
            kandidaten=[
                Kandidat(
                    name="Trend 50 Tage mit Konfluenz", trades=152,
                    sharpe_je_trade=0.2597, schiefe=3.47, woelbung=15.95,
                    effektiv=112,
                )
            ],
        )
        text = gemessen.urteil()

        assert "mindestens" not in text
        assert "112 Beobachtungen" in text
        # Die eigentliche Zahl: Auf 152 rohen Trades stuende hier 1,15.
        assert "Faktor 1.31" in text

    def test_eine_schlechtere_spotguete_wird_nicht_gezeigt(self) -> None:
        """Der Zusatz sagt "dort ist es leichter". Waere es das nicht, waere
        er eine Behauptung ueber einen Punkt, den niemand handeln will."""
        text = self._budget(spotguete=0.20).urteil()

        assert "Spot-Bedingungen" not in text

    def test_gleiche_guete_gibt_keinen_zusatz(self) -> None:
        text = self._budget(spotguete=0.2597).urteil()

        assert "Spot-Bedingungen" not in text
