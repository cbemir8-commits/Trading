"""Wonach bei einem Partner zu suchen ist - und wonach eben nicht.

Zwei Tests tragen diese Datei:

``test_die_naeherung_trifft_die_gemessenen_verbunde`` - Die ganze Karte haengt
an einer Naeherung. Sie wird deshalb gegen die beiden Verbunde geprueft, die
tatsaechlich gerechnet wurden, und nicht bloss behauptet.

``test_menge_schlaegt_qualitaet`` - Der Befund selbst. Bei 53 Trades braeuchte
ein Partner 0,4237; bei 154 genuegen 0,2283 - weniger als der Bestand hat. Die
Auswahl in Befund 73 war nach dem falschen Merkmal getroffen.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from research.partnerkarte import (
    GEMESSENE_GRADE,
    Anwaerter,
    Partnerkarte,
    noetiges_sharpe,
    verbund_guete,
    verbund_sharpe,
)

#: Der Spitzenkandidat und die Schwelle bei 169 Versuchen.
BESTAND = {"n1": 154, "sr1": 0.2591}
ZIEL = 3.629

#: Die beiden Verbunde aus Befund 73, wie sie gemessen wurden.
GEMESSEN = [
    ("Trend-Beteiligung 200 Tage", 53, 0.3185, 0.2759, 0.720),
    ("Donchian-Ausbruch 55/20", 58, 0.3074, 0.2569, 0.500),
]


def karte() -> Partnerkarte:
    return Partnerkarte(**BESTAND, ziel=ZIEL)


class TestNaeherung:
    def test_die_naeherung_trifft_die_gemessenen_verbunde(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Ohne ihn waere die ganze Karte eine Formel ohne Deckung. Die
        Abweichung darf spuerbar sein - sie ist es beim zweiten Fall mit 6 %
        -, aber sie muss klein genug bleiben, dass die Groessenordnung traegt.
        """
        for name, n2, sr2, ist, _ in GEMESSEN:
            vorhergesagt = verbund_sharpe(**BESTAND, n2=n2, sr2=sr2)
            assert vorhergesagt == pytest.approx(ist, rel=0.07), name

    def test_die_naeherung_ist_die_freundliche_richtung(self) -> None:
        """Wo sie danebenliegt, liegt sie **zu hoch** - die Streuung der
        Mischung waechst, wenn die Verteilungen sich unterscheiden. Eine Karte,
        die zu viel verlangt, waere die gefaehrlichere."""
        abweichungen = [
            verbund_sharpe(**BESTAND, n2=n2, sr2=sr2) - ist
            for _, n2, sr2, ist, _ in GEMESSEN
        ]

        assert max(abweichungen) > 0, "Mindestens ein Fall zu freundlich"

    def test_ein_partner_ohne_trades_aendert_nichts(self) -> None:
        assert verbund_sharpe(**BESTAND, n2=0, sr2=0.9) == pytest.approx(0.2591)

    def test_die_guete_faellt_mit_der_abhaengigkeit(self) -> None:
        """``u`` trifft die ganze Stichprobe, nicht nur den Zusatz - so haben
        sich die gemessenen Faelle verhalten."""
        frei = verbund_guete(**BESTAND, n2=100, sr2=0.25, unabhaengigkeit=1.0)
        gebunden = verbund_guete(**BESTAND, n2=100, sr2=0.25, unabhaengigkeit=0.5)

        assert gebunden < frei
        assert gebunden == pytest.approx(frei * 0.5**0.5, rel=1e-9)


class TestBedarf:
    def test_mehr_trades_senken_die_anforderung(self) -> None:
        k = karte()

        assert k.bedarf(400, 0.72) < k.bedarf(154, 0.72) < k.bedarf(50, 0.72)

    def test_mehr_abhaengigkeit_hebt_die_anforderung(self) -> None:
        k = karte()

        assert k.bedarf(154, 0.50) > k.bedarf(154, 0.72) > k.bedarf(154, 1.00)

    def test_menge_schlaegt_qualitaet(self) -> None:
        """**Der zweite tragende Test - der Befund selbst.**

        Der gewaehlte Partner hatte 0,3185 je Trade, eine der besten Zahlen
        des Projekts, und lag bei 53 Trades trotzdem weit weg. Bei 154 Trades
        haette ein Partner genuegt, der **schlechter** ist als der Bestand.
        """
        k = karte()
        wenige = k.bedarf(53, 0.72)
        viele = k.bedarf(154, 0.72)

        assert wenige is not None and viele is not None
        assert wenige > 0.40, f"gemessen {wenige:.4f}"
        assert viele < BESTAND["sr1"], (
            f"{viele:.4f} muesste unter dem Bestand {BESTAND['sr1']} liegen"
        )

    def test_der_gewaehlte_partner_reicht_nicht(self) -> None:
        """Gegenprobe an der Wirklichkeit: Genau dieser Verbund kam auf 3,368
        statt 3,629."""
        k = karte()
        partner = Anwaerter(
            name="Trend-Beteiligung 200 Tage",
            trades=53,
            sharpe_je_trade=0.3185,
            unabhaengigkeit=0.72,
        )

        assert not k.reicht(partner, 0.72)

    def test_unerreichbares_wird_als_solches_gemeldet(self) -> None:
        """Bei sehr wenigen Trades genuegt **kein** Sharpe - das ist eine
        andere Aussage als 'sehr viel noetig'."""
        k = karte()

        assert k.bedarf(1, 0.05) is None


class TestWende:
    def test_die_wende_liegt_in_erreichbarer_naehe(self) -> None:
        """Die Zahl, die die Suchrichtung dreht: Ab wie vielen Trades genuegt
        ein Partner mit der Qualitaet des Bestands?"""
        wende = karte().wende

        assert wende is not None
        assert 100 <= wende <= 300, f"gemessen {wende}"

    def test_ohne_erreichbare_wende_wird_es_gesagt(self) -> None:
        """Bei einer unerreichbar hohen Schwelle fuehrt ueber den Verbund kein
        Weg - und das darf nicht wie eine Zahl aussehen."""
        streng = Partnerkarte(**BESTAND, ziel=999.0)

        assert streng.wende is None
        assert "Kein Partner" in streng.urteil()

    def test_das_urteil_dreht_die_suchrichtung(self) -> None:
        urteil = karte().urteil()

        assert "genug handelt und anders ist" in urteil
        assert "freundliche Richtung" in urteil


class TestDarstellung:
    def test_die_tabelle_zeigt_alle_grade(self) -> None:
        text = karte().tabelle()

        for u in GEMESSENE_GRADE:
            assert f"u={u:.2f}" in text

    def test_die_einordnung_nennt_die_luecke(self) -> None:
        text = karte().einordnung(
            [
                Anwaerter(name=n, trades=t, sharpe_je_trade=s, unabhaengigkeit=u)
                for n, t, s, _, u in GEMESSEN
            ]
        )

        assert "Trend-Beteiligung" in text
        assert "+" in text, "Die Luecke muss mit Vorzeichen dastehen"

    def test_ein_ausreichender_anwaerter_hat_keine_luecke(self) -> None:
        k = karte()
        stark = Anwaerter(name="stark", trades=400, sharpe_je_trade=0.30)

        assert k.reicht(stark, 0.72)
        assert "-0." in k.einordnung([stark]), "Negative Luecke heisst: reicht"


class TestBaustein:
    def test_noetiges_sharpe_ist_die_umkehrung_der_guete(self) -> None:
        """Gegenprobe: Der zurueckgerechnete Wert muss die Zielguete genau
        treffen."""
        noetig = noetiges_sharpe(
            **BESTAND, n2=154, unabhaengigkeit=0.72, ziel=ZIEL
        )

        assert noetig is not None
        erreicht = verbund_guete(
            **BESTAND, n2=154, sr2=noetig, unabhaengigkeit=0.72
        )
        assert erreicht == pytest.approx(ZIEL, abs=1e-6)


class TestWiederverwendbarkeit:
    """Ein Kandidat, den man nicht mehr rechnen kann, ist kein Anwaerter."""

    def test_die_bestenliste_haelt_die_regeln_fest(self) -> None:
        """**Der Mangel, den diese Karte aufgedeckt hat.**

        'Neues Hoch im Takt' ist der aussichtsreichste bekannte Partner - 123
        Trades, nur 0,0406 unter seiner Anforderung. Er stammt aus einer
        Vorschlagsdatei des Analysten, die nie versioniert wurde, und die
        Bestenliste hielt nur ``genome_id`` und Kennzahlen fest.

        Der Eintrag ist damit eine Zahl ohne Regeln: nachweisbar gemessen,
        nicht mehr nachrechenbar.
        """
        from research.leaderboard import Entry

        assert "genom" in {f.name for f in __import__("dataclasses").fields(Entry)}
        assert Entry(genome_id="x", name="y", generation=0).genom is None, (
            "Alte Eintraege bleiben ohne Regeln - erfundene waeren schlimmer"
        )


class TestKatalogkopplung:
    """Gilt die Kopplung aus Befund 54 auch **ueber** die Regeln hinweg?"""

    #: Die 14 verschiedenen Genome der Tageskerzen-Generationen, wie sie in
    #: Befund 75 vermessen wurden.
    KATALOG: ClassVar[list[tuple[str, int, float]]] = [
        ("Luecke wird geschlossen", 258, -0.0368),
        ("VWAP-Rueckkehr short", 185, -0.1113),
        ("Trend-Beteiligung 50 Tage", 156, 0.1894),
        ("Abfolge ohne Strukturbruch", 124, -0.0469),
        ("Trend-Beteiligung 100 Tage", 109, 0.2231),
        ("Trend beide Richtungen", 106, 0.2160),
        ("Momentum-Beteiligung 90 Tage", 101, 0.1649),
        ("Abfolge-Modell short", 67, 0.0833),
        ("Donchian-Ausbruch 55/20", 58, 0.3074),
        ("Abfolge-Modell", 56, 0.1067),
        ("Vola-Ziel, langes Messfenster", 53, 0.3185),
        ("Grosse Kerze mit Volumen short", 51, 0.1342),
        ("Abfolge ohne Luecke", 50, 0.1377),
        ("Bollinger-Ruecksetzer short", 36, 0.0576),
    ]

    #: Die vier eigens gebauten Regeln aus Befund 77. Zusammen mit dem
    #: Katalog sind es die 18 Punkte, ueber die die Kopplung gemessen wird.
    NEU: ClassVar[list[tuple[str, int, float]]] = [
        ("Enge vor Bewegung", 18, 0.340522),
        ("Volumenschock mit Fortsetzung", 114, 0.158416),
        ("Rueckkehr zum Volumenschwerpunkt", 92, -0.120133),
        ("Abgriff des Vortagestiefs", 406, -0.120146),
    ]

    def kopplung(self, *, vollstaendig: bool = False):
        from research.partnerkarte import Katalogkopplung

        rows = [*self.KATALOG, *self.NEU] if vollstaendig else self.KATALOG
        return Katalogkopplung(
            anwaerter=[
                Anwaerter(name=n, trades=t, sharpe_je_trade=s) for n, t, s in rows
            ]
        )

    def test_wer_viel_handelt_handelt_schlechter(self) -> None:
        """**Der Befund von Lauf 75.**

        Befund 54 hat die Kopplung an **einem** Kandidaten gemessen - durch
        Verstellen seiner Regler. Ueber 14 verschiedene Genome gemessen gilt
        sie auch: r = -0,533. Sie ist damit eine Eigenschaft des Vorrats und
        nicht jener Regel.
        """
        k = self.kopplung()

        assert k.korrelation == pytest.approx(-0.533, abs=0.01)
        assert k.t_wert == pytest.approx(-2.18, abs=0.05)
        assert k.auffaellig

    def test_kein_einziger_anwaerter_taugt(self) -> None:
        """Das Ergebnis der Bestandsaufnahme, und der Grund dafuer: Die Karte
        verlangt Menge **und** Qualitaet, der Katalog liefert immer nur
        eines."""
        karte_ = karte()
        tauglich = [
            a
            for a in self.kopplung().anwaerter
            if karte_.reicht(a, 0.72)
        ]

        assert tauglich == []

    def test_zu_wenige_anwaerter_liefern_nichts(self) -> None:
        from research.partnerkarte import Katalogkopplung

        duenn = Katalogkopplung(
            anwaerter=[Anwaerter(name="a", trades=100, sharpe_je_trade=0.2)]
        )

        assert not duenn.genug
        assert duenn.korrelation is None
        assert "nichts sagen" in duenn.urteil()

    def test_das_urteil_nennt_richtung_und_staerke(self) -> None:
        urteil = self.kopplung().urteil()

        assert "Wer viel handelt, handelt schlechter" in urteil
        assert "nicht eine Eigenschaft jener Regel" in urteil or "des Vorrats" in urteil

    def test_ohne_auffaelligkeit_keine_schlussfolgerung(self) -> None:
        """**Ein Scheinbefund, der im ersten Anlauf drinstand.**

        ``cli partner`` liest nur die fuenf Bestenlisten-Eintraege und kam
        damit auf r = +0,359 bei t = +0,67 - das **Gegenteil** des Befunds
        ueber 14 Genome. Das Urteil zog trotzdem denselben Schluss.
        """
        from research.partnerkarte import Katalogkopplung

        schwach = Katalogkopplung(
            anwaerter=[
                Anwaerter(name=n, trades=t, sharpe_je_trade=s)
                for n, t, s in [
                    ("a", 123, 0.2137), ("b", 118, 0.0483), ("c", 89, 0.2136),
                    ("d", 68, 0.2482), ("e", 8, 0.0300),
                ]
            ]
        )

        assert not schwach.auffaellig
        urteil = schwach.urteil()
        assert "sagen diese 5 Anwaerter nichts" in urteil
        assert "Eigenschaft des Vorrats" not in urteil
        assert "dreht ein einzelner" in urteil

    def test_vier_neue_regeln_bestaetigen_die_kopplung(self) -> None:
        """**Gegenprobe an Regeln, die es vorher nicht gab.**

        Befund 75 mass die Kopplung ueber den Katalog - also ueber Regeln, die
        jemand einmal ausgewaehlt hatte. Das ist eine Auswahl, und eine
        Korrelation darueber koennte ihr Artefakt sein.

        Die vier Vorschlaege aus Befund 77 wurden **eigens gegen die
        Spezifikation gebaut**, nicht ausgewaehlt. Sie zeigen dasselbe: r
        faellt von -0,533 auf -0,602, t von -2,18 auf -3,02.
        """
        from research.partnerkarte import Katalogkopplung

        neu = [
            ("Enge vor Bewegung", 18, 0.340522),
            ("Volumenschock mit Fortsetzung", 114, 0.158416),
            ("Rueckkehr zum Volumenschwerpunkt", 92, -0.120133),
            ("Abgriff des Vortagestiefs", 406, -0.120146),
        ]
        zusammen = Katalogkopplung(
            anwaerter=[
                Anwaerter(name=n, trades=t, sharpe_je_trade=s)
                for n, t, s in [*self.KATALOG, *neu]
            ]
        )

        assert zusammen.korrelation == pytest.approx(-0.602, abs=0.01)
        assert zusammen.t_wert == pytest.approx(-3.02, abs=0.05)
        assert zusammen.auffaellig
        assert abs(zusammen.t_wert) > 2.18, "Der Beleg ist staerker geworden"

    def test_reines_rauschen_erzeugt_die_kopplung_nicht(self) -> None:
        """**Die Alternativerklaerung, die zuerst zu widerlegen war.**

        Der Sharpe je Trade ist selbst geschaetzt, mit ``1/sqrt(n-1)`` je
        Regel. Bei Trade-Zahlen von 18 bis 406 streuen die seltenen Regeln
        viermal so breit wie die haeufigen - daraus kann eine Korrelation
        entstehen, ohne dass ein Zusammenhang da waere.

        Gegen eine bekannte Null gezogen liegt die Verteilung bei
        0,00 +- 0,19. Der beobachtete Wert von -0,602 ist mehr als drei
        Streuungen davon entfernt.
        """
        k = self.kopplung(vollstaendig=True)
        mittel, streuung = k.nullprobe(durchlaeufe=5_000)

        assert abs(mittel) < 0.05, "Die Null muss um null liegen"
        assert 0.1 < streuung < 0.3, f"gemessen {streuung:.3f}"
        assert k.ueber_dem_rauschen

    def test_eine_schwache_kopplung_bliebe_im_rauschen(self) -> None:
        """Gegenprobe: Bei r um -0,3 waere nichts zu sagen - die
        Nullverteilung reicht bis dorthin."""
        from research.partnerkarte import Katalogkopplung

        schwach = Katalogkopplung(
            anwaerter=[
                Anwaerter(name=f"k{i}", trades=t, sharpe_je_trade=s)
                for i, (t, s) in enumerate(
                    [(20, 0.20), (50, 0.18), (100, 0.19), (200, 0.15), (400, 0.14)]
                )
            ]
        )

        assert not schwach.ueber_dem_rauschen

    def test_der_beste_einzelpunkt_ist_selbst_rauschen(self) -> None:
        """**Was ich in Befund 77 falsch gewichtet habe.**

        Dort stand: "die seltenste Regel hat die beste Qualitaet (18 Trades,
        0,3405)" - als Beleg fuer die Kopplung. Bei 18 Trades betraegt das
        Messrauschen aber 0,2425, der Wert liegt also 1,4 Standardfehler ueber
        null. Er belegt gar nichts.

        Die Kopplung traegt als **Muster** ueber 18 Punkte, nicht ueber
        einzelne davon.
        """
        from research.aussagekraft import messrauschen

        assert 0.3405 / messrauschen(18) < 2.0
        assert 0.2591 / messrauschen(154) > 3.0, "Der Bestand dagegen schon"

    def test_die_gerade_sagt_die_erwartung_voraus(self) -> None:
        steigung, abschnitt, rest = self.kopplung(vollstaendig=True).gerade()

        assert steigung < 0
        assert steigung * 120 + abschnitt == pytest.approx(0.105, abs=0.01)
        assert rest > 0

    def test_gemessene_treffer_sind_haeufiger_als_echte(self) -> None:
        """Der Winner's Curse in einer Zahl: Die Reststreuung um die Gerade
        enthaelt das Messrauschen mit, und bei 120 Trades sind das 56 % der
        Varianz."""
        gemessen, echt = self.kopplung(vollstaendig=True).trefferquote(
            trades=120, ziel=0.2652
        )

        assert gemessen == pytest.approx(0.095, abs=0.01)
        assert echt == pytest.approx(0.024, abs=0.01)
        assert echt < gemessen / 2

    def test_die_kopplung_deckelt_die_guete(self) -> None:
        """**Die ernuechterndste Zahl des Projekts.**

        ``(a + b*n) * sqrt(n)`` hat ein Maximum: Mehr Trades helfen nur,
        solange der Qualitaetsverlust langsamer waechst als die Wurzel. Das
        Maximum liegt bei 1,281 - das Gate verlangt 3,629.

        Eine durchschnittliche Regel erreicht es also nicht annaehernd. Jeder
        Kandidat, der es schafft, ist ein Ausreisser.
        """
        deckel = self.kopplung(vollstaendig=True).guetedeckel

        assert deckel is not None
        takt, wert = deckel
        assert 60 <= takt <= 100, f"gemessen {takt}"
        assert wert == pytest.approx(1.28, abs=0.05)
        assert wert < 3.629 / 2, "Weniger als die Haelfte des Noetigen"

    def test_der_bestand_ist_bereits_ein_ausreisser(self) -> None:
        """Er liegt 1,52 Reststreuungen ueber der Geraden - und reicht
        trotzdem nicht."""
        k = self.kopplung(vollstaendig=True)
        steigung, abschnitt, rest = k.gerade()
        z = (0.2591 - (abschnitt + steigung * 154)) / rest

        assert z == pytest.approx(1.52, abs=0.05)
        assert k.noetiger_ausreisser(trades=154, ziel=3.629) > z

    def test_das_echte_optimum_liegt_anderswo_als_das_gemessene(self) -> None:
        """**Ein feiner, entscheidender Unterschied.**

        Gemessen ist 153 Trades die beste Trade-Zahl - und der Bestand hat
        154, sitzt also im Optimum. Rechnet man das Messrauschen heraus,
        verschiebt es sich auf 197: Dort ist weniger von der Reststreuung
        Rauschen, ein Treffer also haeufiger echt.
        """
        k = self.kopplung(vollstaendig=True)
        gemessen = k.bester_takt(ziel=3.629, echt=False)
        echt = k.bester_takt(ziel=3.629, echt=True)

        assert gemessen is not None and echt is not None
        assert echt[0] > gemessen[0], "Das echte Optimum liegt bei mehr Trades"
        assert echt[1] < gemessen[1], "Und bei kleinerer Wahrscheinlichkeit"
        assert gemessen[0] == pytest.approx(153, abs=10)

    def test_der_verbund_ist_wirksamer_als_ein_einzelkandidat(self) -> None:
        """Die Entscheidung zwischen den beiden Wegen, beziffert: 1,12 %
        gegen 2,40 % echte Trefferquote je Versuch."""
        k = self.kopplung(vollstaendig=True)
        einzeln = k.bester_takt(ziel=3.629)
        _, verbund = k.trefferquote(trades=120, ziel=0.2652)

        assert einzeln is not None
        assert verbund > einzeln[1], "Der Verbund muss besser sein"
        assert verbund / einzeln[1] > 1.5

    def test_das_optimum_ist_robust_die_trefferquote_nicht(self) -> None:
        """**Die Korrektur an Befund 79 und 80.**

        Dort stand die Trefferquote fuer einen Verbund-Partner mit 2,40 % -
        gerechnet bei 120 Trades, weil ich die **Mindest**-Trade-Zahl aus der
        Partnerkarte fuer das Optimum gehalten hatte. Es liegt bei rund 164.

        Wichtiger: Die Reststreuung ist selbst aus 18 Punkten geschaetzt. Ueber
        ihren Vertrauensbereich schwankt die Trefferquote um Faktor 48, das
        Optimum dagegen nur zwischen 142 und 202 Trades. Die eine Aussage
        traegt, die andere nicht.
        """
        k = self.kopplung(vollstaendig=True)
        lage = k.takt_bereich(ziel=3.629, karte=karte())

        assert lage is not None
        von, bis = lage["takt_spanne"]
        assert 130 <= von <= bis <= 220, f"gemessen {von}..{bis}"
        assert lage["gemessen"][0] > 140, "Nicht 120, wie in Befund 79 gerechnet"

        q_von, q_bis = lage["quoten_spanne"]
        assert q_bis / q_von > 10, "Die Quote ist um Groessenordnungen unsicher"

    def test_die_reststreuung_hat_einen_eigenen_vertrauensbereich(self) -> None:
        """18 Punkte, zwei Parameter - 16 Freiheitsgrade. Der Bereich reicht
        von 0,096 bis 0,174, und daran haengt alles Weitere."""
        bereich = self.kopplung(vollstaendig=True).rest_bereich()

        assert bereich is not None
        unten, oben = bereich
        assert unten == pytest.approx(0.096, abs=0.005)
        assert oben == pytest.approx(0.174, abs=0.005)
        assert oben / unten > 1.7

    def test_das_urteil_nennt_beides_getrennt(self) -> None:
        urteil = self.kopplung(vollstaendig=True).urteil_takt(
            ziel=3.629, karte=karte()
        )

        assert "robust" in urteil
        assert "ist es nicht" in urteil
        assert "mehr als er weiss" in urteil
