"""Was der Vorrat hergibt - und ob das je reichen kann.

Befund 75 hat die Kopplung zwischen Trade-Zahl und Qualitaet gemessen und als
Eigenschaft *des Vorrats* bezeichnet. Faellt die Qualitaet mit der Menge, hat
``SR * sqrt(n)`` ein Maximum. Neunzig Befunde lang hat niemand ausgerechnet,
wo es liegt.

Die Tests hier pruefen die Rechnung an Faellen, deren Antwort **vorher
feststeht** - eine gebaute Gerade, deren Scheitel sich von Hand ausrechnen
laesst -, und die drei Verweigerungen, ohne die das Modul eine Zahl liefern
wuerde, wo keine steht.
"""

from __future__ import annotations

import math

import pytest

from research.vorratsdecke import (
    MINDEST_T,
    Decke,
    Punkt,
    baue,
    familienurteil,
    traegt_eine_familie,
    urteil,
)


def gerade(a: float, b: float, ns: list[int], stoerung: float = 0.0) -> list[Punkt]:
    """Punkte exakt auf ``SR = a + b n``, wahlweise mit abwechselndem Versatz."""
    return [
        Punkt(f"R{i}", n, a + b * n + (stoerung if i % 2 else -stoerung))
        for i, n in enumerate(ns)
    ]


class TestDieGerade:
    def test_steigung_und_abschnitt_werden_wiedergefunden(self) -> None:
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100]))

        assert decke.achsenabschnitt == pytest.approx(0.40)
        assert decke.steigung == pytest.approx(-0.002)
        assert decke.r == pytest.approx(-1.0)

    def test_zwei_punkte_sind_zu_wenige(self) -> None:
        """Durch zwei Punkte geht immer eine Gerade - ihre Reststreuung ist
        null, und jede Einordnung daran waere erfunden."""
        with pytest.raises(ValueError, match="zu wenige"):
            baue(gerade(0.4, -0.002, [20, 40]))

    def test_ohne_streuung_in_der_stichprobe_keine_steigung(self) -> None:
        punkte = [Punkt("A", 50, 0.3), Punkt("B", 50, 0.2), Punkt("C", 50, 0.25)]

        with pytest.raises(ValueError, match="dieselbe Stichprobe"):
            baue(punkte)


class TestDerScheitel:
    def test_er_liegt_wo_die_ableitung_null_ist(self) -> None:
        """``(a + b n) sqrt(n)`` ist maximal bei ``n = -a / (3 b)``.

        Mit a = 0,40 und b = -0,002 sind das 66,67 - von Hand nachrechenbar,
        und deshalb steht die Zahl hier und nicht das Ergebnis des Codes.
        """
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.01))

        assert decke.scheitel_n == pytest.approx(0.40 / (3 * 0.002), rel=0.05)

    def test_der_scheitel_ist_wirklich_das_maximum(self) -> None:
        """Gegenprobe ohne Formel: links und rechts davon ist es schlechter."""
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.01))
        n = decke.scheitel_n
        hoehe = decke.scheitel_guete

        for daneben in (n - 15, n - 5, n + 5, n + 15):
            wert = (decke.achsenabschnitt + decke.steigung * daneben) * daneben**0.5
            assert wert < hoehe, daneben

    def test_ohne_fallende_qualitaet_gibt_es_keine_decke(self) -> None:
        """**Beide Ausgaenge sind Ergebnisse.** Steigt die Qualitaet mit der
        Menge, gibt es kein Maximum - dann wird keines behauptet."""
        decke = baue(gerade(0.10, +0.002, [20, 40, 60, 80, 100], stoerung=0.005))

        assert decke.steigung > 0
        assert not decke.tragfaehig
        assert decke.scheitel_n is None
        assert decke.scheitel_guete is None
        assert decke.nullstelle is None

    def test_ohne_deckung_wird_nichts_geschlossen(self) -> None:
        """**Die Lehre aus Befund 75.**

        Dort kam auf fuenf Punkten r = +0,359 heraus - das Gegenteil - und
        das Urteil zog trotzdem denselben Schluss. Eine Korrelation ohne
        Deckung darf nicht klingen wie eine mit.
        """
        punkte = [
            Punkt("A", 30, 0.30), Punkt("B", 60, 0.31), Punkt("C", 90, 0.28),
            Punkt("D", 120, 0.30),
        ]
        decke = baue(punkte)

        assert abs(decke.t) < MINDEST_T
        assert not decke.tragfaehig
        assert decke.scheitel_guete is None


class TestDasUrteil:
    @staticmethod
    def latte(n: int) -> float:
        return 3.5

    def test_es_nennt_decke_latte_und_luecke(self) -> None:
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.01))
        text = urteil(decke, self.latte)

        assert f"{decke.scheitel_guete:.3f}" in text
        assert "3.500" in text
        assert "Stichproben von 20 bis 100" in text

    def test_es_sagt_dazu_worueber_es_nicht_spricht(self) -> None:
        """Ohne diesen Satz liest sich die Decke als Aussage ueber alle
        Strategien - und waere damit ein Argument fuers Aufgeben."""
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.01))
        text = urteil(decke, self.latte)

        assert "nicht ueber den Raum aller Strategien" in text
        assert "kein Grund, eine Latte zu senken" in text

    def test_ohne_tragfaehigkeit_steht_dort_keine_zahl(self) -> None:
        decke = baue(gerade(0.10, +0.002, [20, 40, 60, 80, 100], stoerung=0.005))
        text = urteil(decke, self.latte)

        assert "Keine Decke ablesbar" in text
        assert "Diese Punkte sagen darueber nichts" in text


class TestDieEinordnung:
    """Wo eine Regel in ihrem eigenen Vorrat steht - und was das heisst."""

    def test_der_rest_wird_in_reststreuungen_gemessen(self) -> None:
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.02))
        # Genau eine Reststreuung ueber der Geraden.
        darueber = decke.vorhersage(70) + decke.reststreuung

        assert decke.rest(70, darueber) == pytest.approx(1.0)

    def test_auf_der_geraden_ist_der_rest_null(self) -> None:
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.02))

        assert decke.rest(70, decke.vorhersage(70)) == pytest.approx(0.0, abs=1e-9)

    def test_ohne_reststreuung_wird_die_einordnung_verweigert(self) -> None:
        """Liegen alle Punkte exakt auf der Geraden, ist "wie viele
        Reststreuungen" keine Frage mit Antwort."""
        decke = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100]))

        assert decke.r == pytest.approx(-1.0)
        with pytest.raises(ValueError, match="Reststreuung null"):
            decke.rest(70, 0.3)

    def test_das_erwartete_maximum_waechst_mit_den_ziehungen(self) -> None:
        """``sqrt(2 ln k)``: Wer oefter zieht, findet allein dadurch mehr.

        Die drei Zahlen sind von Hand nachrechenbar und stehen deshalb hier.
        """
        assert Decke.erwartetes_maximum(14) == pytest.approx(math.sqrt(2 * math.log(14)))
        assert Decke.erwartetes_maximum(198) == pytest.approx(math.sqrt(2 * math.log(198)))
        assert Decke.erwartetes_maximum(2) < Decke.erwartetes_maximum(198)

    def test_unter_zwei_ziehungen_gibt_es_kein_maximum(self) -> None:
        with pytest.raises(ValueError, match="zwei Ziehungen"):
            Decke.erwartetes_maximum(1)


class TestDerBestandInSeinemVorrat:
    """Der gemessene Fall aus Befund 168, als Zahlen festgehalten.

    Gerade ``SR(n) = a + b n`` ueber 14 Regeln, n_eff 27 bis 121, r = -0,714.
    Der Bestand steht bei n_eff 115 mit SR 0,2708; die Gerade sagt dort
    0,1554. Sein Vorsprung betraegt +2,41 Reststreuungen - **weniger** als
    die 3,25, die reine Auswahl aus 198 Versuchen erzeugt.
    """

    def test_ein_vorsprung_unter_dem_erwarteten_maximum_ist_keiner(self) -> None:
        assert Decke.erwartetes_maximum(198) > 2.41

    def test_und_bei_wenigen_versuchen_waere_er_einer(self) -> None:
        """Die Aussage haengt am Versuchsstand, nicht am Kandidaten - genau
        deshalb steht sie neben dem Deflated Sharpe und nicht statt seiner."""
        assert Decke.erwartetes_maximum(13) < 2.41


class TestWoraufDieKopplungSteht:
    """Traegt eine Familie die Auffaelligkeit - oder der ganze Vorrat?

    Der Unterschied entscheidet, worueber die Decke spricht. Befund 54 hat
    die Kopplung an **einem** Kandidaten durch Verstellen seiner Regler
    gemessen; Befund 75 nannte sie eine Eigenschaft *des Vorrats* und grenzte
    sich damit ausdruecklich davon ab. Traegt eine Familie alles, sind beide
    Aussagen wieder dieselbe.

    Gemessen (Befund 169): ganzer Vorrat r = -0,714 bei t = -3,53, nur 'sma'
    (9 von 14) r = -0,778 bei t = -3,28, ohne 'sma' r = -0,547 bei t = -1,13.
    """

    def test_ohne_mehrheitsfamilie_stellt_sich_die_frage_nicht(self) -> None:
        aufteilung = {
            "a": gerade(0.4, -0.002, [20, 40, 60]),
            "b": gerade(0.4, -0.002, [30, 50, 70]),
        }

        assert traegt_eine_familie(aufteilung) is None

    def test_leerer_vorrat_ergibt_nichts(self) -> None:
        assert traegt_eine_familie({}) is None

    def test_die_mehrheitsfamilie_wird_benannt(self) -> None:
        aufteilung = {
            "sma": gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.01),
            "roc": gerade(0.30, -0.001, [30, 70]),
        }
        name, drin, ohne = traegt_eine_familie(aufteilung)

        assert name == "sma"
        assert drin is not None and len(drin.punkte) == 5
        assert ohne is None, "zwei Punkte sind keine Gerade"

    def test_traegt_die_familie_alles_sagt_das_urteil_es(self) -> None:
        """**Der Fall, den es hier wirklich gibt.**

        Innerhalb der Familie ein klarer Abfall, ausserhalb Rauschen - dann
        beschreibt die Decke die Familie und nicht den Vorrat.
        """
        aufteilung = {
            "sma": gerade(0.40, -0.002, [20, 40, 60, 80, 100], stoerung=0.01),
            "rest": [
                Punkt("A", 30, 0.30), Punkt("B", 60, 0.31),
                Punkt("C", 90, 0.28), Punkt("D", 120, 0.30),
            ],
        }
        text = familienurteil(traegt_eine_familie(aufteilung))

        assert "sagt nichts" in text
        assert "innerhalb einer Familie" in text
        assert "fuer den Vorrat als Ganzes reicht es nicht" in text

    def test_haelt_die_kopplung_auch_ausserhalb_wird_nichts_eingeschraenkt(
        self,
    ) -> None:
        """**Beide Ausgaenge sind Ergebnisse.** Faellt die Qualitaet auch in
        den uebrigen Familien, ist die Decke keine Familieneigenschaft - und
        der einschraenkende Satz darf dann nicht dastehen."""
        aufteilung = {
            "sma": gerade(
                0.40, -0.002, [20, 30, 40, 60, 80, 100], stoerung=0.01
            ),
            "rest": gerade(0.38, -0.002, [25, 45, 65, 85, 105], stoerung=0.01),
        }
        aufgeteilt = traegt_eine_familie(aufteilung)

        assert aufgeteilt is not None, "ohne Mehrheit prueft der Test nichts"
        name, drin, ohne = aufgeteilt
        text = familienurteil((name, drin, ohne))

        assert ohne is not None and ohne.tragfaehig
        assert "sagt nichts" not in text
        assert "fuer den Vorrat als Ganzes reicht es nicht" not in text

    def test_knapp_verfehlt_zaehlt_nicht_als_erreicht(self) -> None:
        """Die Familienmediane kamen auf t = -1,93 gegen eine Schwelle von 2.

        Genau dieser Fehler steht in Befund 75 als Scheinbefund: Eine
        Korrelation ohne Deckung darf nicht klingen wie eine mit.
        """
        knapp = Decke(
            punkte=(), achsenabschnitt=0.4, steigung=-0.002,
            r=-0.744, t=-1.93, reststreuung=0.02,
        )

        assert not knapp.tragfaehig
        assert knapp.scheitel_guete is None
