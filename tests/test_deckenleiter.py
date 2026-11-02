"""Die Decke bei anderer Reibung - Befund 456.

``kostenanteil.Reibungsleiter`` berichtet die **Kopplung**. Auf Viertelstunden
ist das die tragende Zahl (453: die Reibung traegt 44 % davon), auf Tageskerzen
nicht: Dort haengt die Guete an der Kopplung nicht (rho +0,072, Befund 290),
und was entscheidet, ist der Abstand zur Latte.

Diese Tests halten fest, was ``Deckenleiter`` dazu sagt - und vor allem, was
es **nicht** sagt, wenn die Messung fehlt.
"""

from __future__ import annotations

import pytest

from research.deckenleiter import Deckenleiter, Deckensprosse, Luecke
from research.vorratsdecke import Punkt

#: Ein Versuchsstand, bei dem es fuer diese Stichproben eine Latte gibt.
VERSUCHE = 203


def _punkt(name: str, n_eff: int, sr: float) -> Punkt:
    # Schiefe und Woelbung gesetzt: Ohne sie stuende bei jeder Regel die Latte
    # einer neutralen Verteilung, und das ist eine andere (Befund 191).
    return Punkt(name, n_eff, sr, schiefe=2.65, woelbung=9.35)


class TestEineSprosseAlleinSagtNichts:
    def test_ohne_jede_decke_wird_es_gesagt(self) -> None:
        """Der Fall eines Protokolls von vor 456: Die Sprosse traegt den
        Sharpe je Trade, aber kein 'n_eff'."""
        leiter = Deckenleiter(
            sprossen=(Deckensprosse(faktor=0.0), Deckensprosse(faktor=1.0)),
            versuche=VERSUCHE,
        )

        text = leiter.urteil()

        assert not leiter.mit_decke
        assert "Keine Decke je Sprosse gemessen" in text
        assert "nicht die Trade-Zahl" in text

    def test_eine_einzige_decke_nennt_den_grund(self) -> None:
        """**Und nicht 'verschiedene Regeln'.** Genau das stand hier zuerst:
        ``gleiche_regeln`` ist bei einer Sprosse schon falsch, und die
        Meldung verdeckte damit den wahren Grund."""
        leiter = Deckenleiter(
            sprossen=(
                Deckensprosse(faktor=0.0),
                Deckensprosse(faktor=1.0, punkte=(_punkt("A", 58, 0.326),)),
            ),
            versuche=VERSUCHE,
        )

        text = " ".join(leiter.urteil().split())

        assert "Nur eine Sprosse mit Decke" in text
        assert "Faktor 0" in text
        assert "vor Befund 456" in text
        assert "verschiedene Regeln" not in text

    def test_die_tabelle_zeigt_die_leere_sprosse_als_strich(self) -> None:
        """Eine nicht gemessene Zeile als '0.000' waere eine gemessene
        Null."""
        leiter = Deckenleiter(
            sprossen=(
                Deckensprosse(faktor=0.0),
                Deckensprosse(faktor=1.0, punkte=(_punkt("A", 58, 0.326),)),
            ),
            versuche=VERSUCHE,
        )

        zeilen = leiter.tabelle().splitlines()

        assert zeilen[2].split() == ["0", "0", "-", "-", "-"]
        assert zeilen[3].split()[0] == "1"


class TestVerglichenWirdNurBeiGleicherRegelmenge:
    def test_verschiedene_regeln_sind_zwei_populationen(self) -> None:
        """Befund 301. Ohne Reibung fallen Fuellungen anders aus, und eine
        Regel kann im einen Lauf genug Trades haben und im anderen nicht."""
        leiter = Deckenleiter(
            sprossen=(
                Deckensprosse(
                    faktor=0.0,
                    punkte=(_punkt("A", 58, 0.33), _punkt("B", 60, 0.30)),
                ),
                Deckensprosse(faktor=1.0, punkte=(_punkt("A", 58, 0.326),)),
            ),
            versuche=VERSUCHE,
        )

        text = " ".join(leiter.urteil().split())

        assert not leiter.gleiche_regeln
        assert not leiter.belastbar
        assert "Nicht vergleichbar" in text
        assert "1 nur in einem Teil" in text

    def test_eine_sprosse_ganz_ohne_latte_wird_benannt(self) -> None:
        """Wo das Gate bei dieser Stichprobe nicht urteilt, gibt es keine
        Latte - und eine Luecke zu einer Latte, die es nicht gibt, ist keine
        Zahl. Gemeldet wird, **welche** Sprosse es trifft."""
        leiter = Deckenleiter(
            sprossen=(
                Deckensprosse(
                    faktor=0.0,
                    punkte=(Punkt("A", 3, 0.33, schiefe=0.0, woelbung=3.0),),
                ),
                Deckensprosse(
                    faktor=1.0,
                    punkte=(Punkt("A", 3, 0.32, schiefe=0.0, woelbung=3.0),),
                ),
            ),
            versuche=VERSUCHE,
        )

        text = " ".join(leiter.urteil().split())

        assert leiter.gleiche_regeln
        assert not leiter.belastbar
        assert "Keine Latte auf Faktor 0, 1" in text

    def test_gleiche_namen_genuegen(self) -> None:
        leiter = Deckenleiter(
            sprossen=(
                Deckensprosse(faktor=0.0, punkte=(_punkt("A", 58, 0.33),)),
                Deckensprosse(faktor=1.0, punkte=(_punkt("A", 58, 0.326),)),
            ),
            versuche=VERSUCHE,
        )

        assert leiter.gleiche_regeln
        assert leiter.belastbar


class TestWasDieReibungAnDerLueckeAendert:
    def _leiter(self, sr_frei: float, sr_betrieb: float) -> Deckenleiter:
        return Deckenleiter(
            sprossen=(
                Deckensprosse(faktor=0.0, punkte=(_punkt("A", 58, sr_frei),)),
                Deckensprosse(faktor=1.0, punkte=(_punkt("A", 58, sr_betrieb),)),
            ),
            versuche=VERSUCHE,
        )

    def test_die_luecke_ist_latte_minus_guete(self) -> None:
        stueck = Luecke(punkt=_punkt("A", 58, 0.326), latte=3.564)

        assert stueck.punkt.guete == pytest.approx(0.326 * 58**0.5)
        assert stueck.fehlt == pytest.approx(3.564 - 0.326 * 58**0.5)

    @pytest.mark.parametrize(
        ("latte", "abstand", "wort"),
        [
            (3.564, "es fehlen 1.080", "einer Luecke von 1.080"),
            (2.400, "sie raeumt ihre Latte um 0.084", "0.084 Luft ueber ihrer Latte"),
        ],
    )
    def test_beide_formulierungen_kommen_ohne_vorzeichen_aus(
        self, latte: float, abstand: str, wort: str
    ) -> None:
        """**Kein 'es fehlen -0,084'.** Wer eine Regel meldet, die ihre Latte
        raeumt, soll nicht erst ein Vorzeichen deuten muessen."""
        stueck = Luecke(punkt=_punkt("A", 58, 0.32616), latte=latte)

        assert stueck.als_abstand() == abstand
        assert stueck.als_wort() == wort
        assert "-" not in stueck.als_abstand()

    def test_traegt_die_reibung_fast_nichts_steht_es_so_da(self) -> None:
        """Der gemessene Fall auf Tageskerzen."""
        leiter = self._leiter(0.32761, 0.32616)

        anteil = leiter.anteil_an_der_luecke
        text = " ".join(leiter.urteil().split())

        assert anteil is not None
        assert anteil < 0.02
        assert "Die Reibung traegt die Luecke nicht" in text
        assert "was fehlt, fehlt an den Signalen" in text

    def test_waere_die_luecke_ohne_reibung_zu_steht_es_ohne_vorzeichen_da(
        self,
    ) -> None:
        """**Der folgenreichste Satz des Berichts** - er meldet eine Regel,
        die ihre Latte raeumt. Hier stand zuerst 'es fehlen -0.012' und ein
        Anteil von '101.1% des Weges': beides arithmetisch richtig und beides
        wie ein Rechenfehler zu lesen.

        Und er sagt dazu, was er **nicht** heisst: Gehandelt wird mit
        Reibung."""
        leiter = self._leiter(0.47, 0.32616)

        anteil = leiter.anteil_an_der_luecke
        text = " ".join(leiter.urteil().split())

        assert anteil is not None and anteil > 1.0
        assert "Ohne Reibung ist die Luecke zu" in text
        assert "raeumt dort ihre Latte um 0.012" in text
        assert "Das ist keine Zulassung" in text
        assert "-0.012" not in text
        assert "101.1%" not in text

    def test_fast_ganz_reibung_ist_ein_eigener_fall(self) -> None:
        """Knapp unter der Null: Die Luecke bleibt offen, und der Anteil
        traegt die Aussage."""
        leiter = self._leiter(0.4675, 0.32616)

        anteil = leiter.anteil_an_der_luecke
        text = " ".join(leiter.urteil().split())

        assert anteil is not None and 0.98 <= anteil <= 1.0
        assert "fast ganz Reibung" in text

    def test_und_dazwischen_heisst_es_teils(self) -> None:
        leiter = self._leiter(0.40, 0.32616)

        anteil = leiter.anteil_an_der_luecke
        text = " ".join(leiter.urteil().split())

        assert anteil is not None and 0.02 < anteil < 0.98
        assert "**Teils.**" in text

    def test_ohne_betriebspunkt_kein_anteil(self) -> None:
        """Ein Anteil misst den Weg **vom Betriebspunkt** zur Null. Ohne
        Faktor 1 waere er eine Zahl ohne Bezug."""
        leiter = Deckenleiter(
            sprossen=(
                Deckensprosse(faktor=0.0, punkte=(_punkt("A", 58, 0.33),)),
                Deckensprosse(faktor=2.0, punkte=(_punkt("A", 58, 0.32),)),
            ),
            versuche=VERSUCHE,
        )

        assert leiter.belastbar
        assert leiter.anteil_an_der_luecke is None
        assert "Kein Anteil ablesbar" in " ".join(leiter.urteil().split())


class TestDieLatteGehoertDerRegel:
    def test_zwei_regeln_mit_derselben_guete_haben_verschiedene_latten(
        self,
    ) -> None:
        """Befund 191 - und der Grund, warum die **kleinste Luecke** gemeldet
        wird und nicht die hoechste Guete."""
        schief = Punkt("schief", 58, 0.33, schiefe=3.46, woelbung=15.92)
        neutral = Punkt("neutral", 58, 0.33, schiefe=0.0, woelbung=3.0)
        sprosse = Deckensprosse(faktor=1.0, punkte=(schief, neutral))

        latten = {x.punkt.name: x.latte for x in sprosse.luecken(VERSUCHE)}

        assert schief.guete == pytest.approx(neutral.guete)
        assert latten["schief"] != latten["neutral"]

    def test_gemeldet_wird_die_kleinste_luecke(self) -> None:
        hoch = Punkt("hohe Guete", 250, 0.30, schiefe=0.0, woelbung=3.0)
        nah = Punkt("nah an ihrer Latte", 58, 0.33, schiefe=3.46, woelbung=15.92)
        sprosse = Deckensprosse(faktor=1.0, punkte=(hoch, nah))

        luecken = {x.punkt.name: x.fehlt for x in sprosse.luecken(VERSUCHE)}
        naechste = sprosse.naechste(VERSUCHE)

        assert hoch.guete > nah.guete
        assert naechste is not None
        assert naechste.fehlt == min(luecken.values())

    def test_regeln_ohne_latte_fallen_heraus_und_nicht_auf_null(self) -> None:
        """Wo das Gate bei dieser Stichprobe nicht urteilt, gibt es keine
        Latte - und eine Luecke zu einer Latte, die es nicht gibt, ist keine
        Zahl."""
        winzig = Punkt("zu klein", 3, 0.33, schiefe=0.0, woelbung=3.0)
        sprosse = Deckensprosse(faktor=1.0, punkte=(winzig,))

        assert sprosse.luecken(VERSUCHE) == ()
        assert sprosse.naechste(VERSUCHE) is None
