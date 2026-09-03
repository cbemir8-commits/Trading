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
    UNGEPRUEFT,
    Decke,
    Einteilung,
    Punkt,
    baue,
    familienurteil,
    preisurteil,
    stabilitaetsurteil,
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


class TestWasDieMengeKostet:
    """**Befund 179.** Befund 178 hat das Mengentor geoeffnet - dieselbe
    Qualitaet bei groesserer Stichprobe genuegt ebenso wie bessere Qualitaet
    bei gleicher.

    Es steht dort unter *"bei unveraenderter Qualitaet"*. In einem Vorrat mit
    Kopplung ist das keine freie Wahl: Wer mehr handelt, handelt schlechter.
    Diese Tests halten fest, was daraus wird.
    """

    #: Die Gerade aus Befund 168, aus Scheitel (n_eff 69, Guete 1,931) und
    #: Nullstelle (n_eff 208) zurueckgerechnet.
    B = -0.23246 / 139
    A = -208 * B

    def decke(self) -> Decke:
        """**Die gemessene Lage selbst**, nicht eine nachgebaute.

        Ueber ``baue`` liesse sie sich nur annaehern: Reststreuung und
        Korrelation haengen dann an der gewaehlten Stoerung, und der Preis
        skaliert direkt mit der Reststreuung. Hier stehen die vier Zahlen aus
        Befund 168 - 14 Regeln, r = -0,714, t = -3,53, Reststreuung 0,0479 -
        und der Test misst an ihnen.
        """
        return Decke(
            punkte=tuple(gerade(self.A, self.B, [27, 55, 70, 90, 115, 121])),
            achsenabschnitt=self.A,
            steigung=self.B,
            r=-0.714,
            t=-3.53,
            reststreuung=0.04783,
        )

    def latte(self, versuche: int = 198):
        from research.suchbudget import Budget

        return Budget(versuche=versuche).noetig_bei

    def test_der_noetige_abstand_hat_ein_minimum(self) -> None:
        """**Der Kern.** Waere er monoton fallend, waere "mehr handeln" ein
        Weg. Er faellt und steigt wieder - es gibt eine guenstigste Stelle."""
        d = self.decke()
        treffer = d.noetiger_abstand(self.latte())

        assert treffer is not None
        n, abstand = treffer
        davor = (self.latte()(n - 20) - d.vorhersage(n - 20)) / d.reststreuung
        danach = (self.latte()(n + 20) - d.vorhersage(n + 20)) / d.reststreuung
        assert abstand < davor and abstand < danach

    def test_mehr_trades_machen_es_teurer_nicht_billiger(self) -> None:
        """Die Latte je Trade faellt mit der Stichprobe - die Gerade faellt
        schneller. Das ist die ganze Aussage von Befund 179."""
        d = self.decke()
        latte = self.latte()
        preise = [
            (latte(n) - d.vorhersage(n)) / d.reststreuung for n in (120, 160, 200, 240)
        ]

        assert preise == sorted(preise), f"muesste steigen, ist {preise}"

    def test_ohne_tragfaehige_decke_gibt_es_keinen_preis(self) -> None:
        """Eine steigende Gerade hat kein Maximum, und eine ohne Deckung sagt
        nichts - in beiden Faellen waere eine Zahl erfunden."""
        steigend = baue(gerade(0.1, +0.001, [30, 60, 90, 120], 0.02))

        assert steigend.noetiger_abstand(self.latte()) is None
        assert "Kein Preis ablesbar" in preisurteil(
            steigend, self.latte(), versuche=198
        )

    def test_das_urteil_nennt_die_stelle_und_den_vergleich(self) -> None:
        text = preisurteil(self.decke(), self.latte(), versuche=198, bestand=2.41)

        assert "guenstigste Stelle" in text
        assert "Reststreuungen ueber der Geraden" in text
        assert "198 Ziehungen" in text
        assert "nicht die billigere Haelfte" in text

    def test_ein_bestand_unter_seiner_geraden_wird_nicht_schoengerechnet(
        self,
    ) -> None:
        """Sonst staende dort ein negativer Faktor - eine Zahl, die aussieht
        wie eine Auskunft und keine ist."""
        text = preisurteil(self.decke(), self.latte(), versuche=198, bestand=-0.4)

        assert "unter seiner" in text
        assert "-fache" not in text

    def test_die_gemessene_lage_wird_getroffen(self) -> None:
        """**Die Zahl aus Befund 179**, an der zurueckgerechneten Geraden:
        rund 3,7 Reststreuungen, und die guenstigste Stelle liegt dort, wo
        der Bestand ohnehin schon steht (n_eff 115).
        """
        treffer = self.decke().noetiger_abstand(self.latte())

        assert treffer is not None
        n, abstand = treffer
        assert abstand == pytest.approx(3.70, abs=0.15)
        assert 80 <= n <= 130, f"guenstigste Stelle bei n_eff {n}"


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


class TestHaengtEsAmSchnitt:
    """**Befund 181, und es ist eine Gegenprobe zu meiner eigenen Arbeit.**

    Befund 169 hat nach dem Einstiegsindikator eingeteilt - strukturell aus
    dem Genom gelesen und insofern keine Meinung. Aber es ist **eine**
    Einteilung unter mehreren, und auf ihr stehen zwei Befunde: dass die
    Kopplung eine Familieneigenschaft ist (169) und was sie kostet (179).

    Wer denselben Punkten einen anderen Schnitt gibt und dasselbe herausholt,
    hat einen Befund. Wer etwas anderes herausholt, hat einen Schnitt.
    """

    def traegt(self) -> Einteilung:
        return Einteilung(
            "Indikator",
            traegt_eine_familie(
                {
                    "sma": gerade(0.40, -0.002, [20, 40, 60, 80, 100], 0.01),
                    "rest": [
                        Punkt("A", 30, 0.30), Punkt("B", 60, 0.31),
                        Punkt("C", 90, 0.28), Punkt("D", 120, 0.30),
                    ],
                }
            ),
        )

    def traegt_nicht(self) -> Einteilung:
        return Einteilung(
            "gleitende zusammen",
            traegt_eine_familie(
                {
                    "gleitend": gerade(0.40, -0.002, [20, 30, 40, 60, 80, 100], 0.01),
                    "rest": gerade(0.38, -0.002, [25, 45, 65, 85, 105], 0.01),
                }
            ),
        )

    def test_einigkeit_wird_als_solche_gemeldet(self) -> None:
        text = stabilitaetsurteil([self.traegt(), self.traegt()])

        assert "2 von 2 pruefbaren Schnitten sagen dasselbe" in text

    def test_uneinigkeit_macht_die_aussage_bedingt(self) -> None:
        """**Der Fall, um den es geht.** Zwei Schnitte, zwei Antworten - dann
        gehoert der Schnitt in jede Zitierung."""
        text = stabilitaetsurteil([self.traegt(), self.traegt_nicht()])

        assert "1 von 2 pruefbaren Schnitten stuetzen es" in text
        assert "am Schnitt" in text

    def test_wo_keiner_stuetzt_wird_es_deutlich_gesagt(self) -> None:
        text = stabilitaetsurteil([self.traegt_nicht(), self.traegt_nicht()])

        assert "Kein pruefbarer Schnitt stuetzt es" in text
        assert "gehoert dann nicht in einen Befund" in text

    def test_eine_einteilung_ohne_mehrheit_zaehlt_nicht_als_bestaetigung(
        self,
    ) -> None:
        """**Der Fehler aus dem ersten Anlauf.** Sie zaehlte als "traegt
        allein" - und damit war die fehlende Aussenmenge ein Beleg."""
        ohne = Einteilung("Regellogik", None)

        assert ohne.befund == UNGEPRUEFT
        assert not ohne.traegt_allein
        text = stabilitaetsurteil([self.traegt(), ohne])
        assert "keine Mehrheitsfamilie" in text
        assert "1 von 1 pruefbaren" in text
        assert "1 konnten es nicht pruefen" in text

    def test_ohne_einteilungen_wird_nichts_behauptet(self) -> None:
        assert "Keine Einteilung" in stabilitaetsurteil([])

    def test_die_zahlen_je_schnitt_stehen_dabei(self) -> None:
        """Ein blosses Ja/Nein liesse nicht erkennen, ob ein Schnitt knapp
        oder deutlich entscheidet."""
        text = stabilitaetsurteil([self.traegt()])

        assert "drin 5/t=" in text
        assert "ohne" in text

    def test_eine_zu_kleine_aussenmenge_ist_kein_beleg(self) -> None:
        """**Der gemessene Fall, der den ersten Anlauf widerlegt hat.**

        Legt man die gleitenden Durchschnitte zusammen, stehen drinnen 11
        Regeln mit r = -0,817 und draussen drei. Eine Kopplung dieser Staerke
        braeuchte draussen vier, um sich zu zeigen - der Schnitt hat also
        nichts gefunden, weil er nichts finden konnte.

        Der erste Anlauf meldete hier "traegt allein" und kam damit auf
        "alle 3 Schnitte sagen dasselbe".
        """
        # Die gemessene Lage selbst: 11 Regeln, r = -0,817 (aus t = -4,25).
        drin = Decke(
            punkte=tuple(gerade(0.40, -0.002, list(range(20, 130, 10)))),
            achsenabschnitt=0.40, steigung=-0.002,
            r=-0.817, t=-4.25, reststreuung=0.02,
        )
        assert drin.tragfaehig
        assert drin.noetige_regeln() == 4

        klein = Einteilung(
            "gleitende zusammen",
            (
                "gleitend",
                drin,
                baue([Punkt("A", 30, 0.30), Punkt("B", 60, 0.34), Punkt("C", 90, 0.29)]),
            ),
        )

        assert klein.befund == UNGEPRUEFT
        assert "nicht geprueft" in stabilitaetsurteil([klein])

    def test_die_noetige_menge_folgt_aus_der_staerke(self) -> None:
        """Je schwaecher die Kopplung drinnen, desto mehr Regeln braucht es
        draussen, um ihr Fehlen zu belegen."""
        stark = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], 0.005))
        schwach = baue(gerade(0.40, -0.002, [20, 40, 60, 80, 100], 0.05))

        assert abs(stark.r) > abs(schwach.r)
        assert stark.noetige_regeln() < schwach.noetige_regeln()

    def test_ein_einzelner_pruefbarer_schnitt_bekommt_den_singular(self) -> None:
        """Die gemessene Lage aus Befund 181: einer von drei konnte pruefen.
        "1 von 1 pruefbaren Schnitten sagen dasselbe" stand da zuerst."""
        text = stabilitaetsurteil(
            [self.traegt(), Einteilung("A", None), Einteilung("B", None)]
        )

        assert "1 von 1 pruefbaren Schnitten sagt dasselbe" in text
        assert "2 konnten es nicht pruefen" in text


def test_der_modulkopf_warnt_vor_seinen_eigenen_zahlen() -> None:
    """**Befund 182.** Die Zahlen im Kopf stehen auf einem Vorrat, der nach
    der Groessenlogik gefiltert war - neun Regeln fehlten, und der Grund hat
    mit ihrem Einstieg nichts zu tun.

    Sie hier stehen zu lassen, ohne das dazuzusagen, ist genau der Fehler,
    den Befund 130 an einer veralteten Fundstelle gefunden hat: Zwei Laeufe
    haben dort nachgeschlagen und den Unterschied falschen Ursachen
    zugeschrieben.
    """
    import research.vorratsdecke as modul

    kopf = modul.__doc__ or ""
    assert "ACHTUNG" in kopf
    assert "Befund 182" in kopf
    assert "gefilterten Vorrat" in kopf
    # Die betroffenen Befunde beim Namen - sonst sucht sie niemand.
    for nummer in ("168", "169", "179", "181"):
        assert nummer in kopf
