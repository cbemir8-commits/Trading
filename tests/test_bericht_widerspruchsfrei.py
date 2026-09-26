"""Nennt der Bericht dieselbe Groesse zweimal verschieden?

**Befund 231.** Befund 230 hat einen Widerspruch im eigenen Bericht gefunden:
Das Urteil nannte die zu schliessende Luecke mit +15,0 % (aus den eigenen
Zahlen, Erstpunkt), der Abschnitt "Wie weit es noch ist" mit +24,3 % (aus
``erfuellung``, Spot-Punkt). Eine Bildschirmseite auseinander, beide richtig,
keine erklaert.

Gefunden habe ich das durch Lesen. Diese Wache sucht danach.

Was sie kann und was nicht
--------------------------
Sie kann nicht wissen, welche Zahlen dieselbe Groesse meinen - dazu muesste
sie den Text verstehen. Sie prueft daher Dinge, die sich mechanisch sagen
lassen:

* Die Luecke steht **einmal**, und zwar mit dem Wert aus den eigenen Zahlen
  des Berichts. Das ist der Fall aus Befund 230, festgehalten.
* Jeder Prozentwert, der in mehr als einem Abschnitt auftaucht, steht in
  einer bekannten Liste. Kommt ein neuer dazu, faellt er auf und jemand sieht
  hin - so wie bei den ueberholten Kennzahlen seit Befund 156.

Nachgemessen bei ihrer Anlage: Der Bericht nennt 25 verschiedene
Prozentwerte, zwei davon in zwei Abschnitten, und beide zu Recht.

Die zweite Gestalt desselben Fehlers
------------------------------------
**Befund 317.** Die Wache oben sucht **Doppelgaenger**: dieselbe Groesse,
zwei Abschnitte, zwei Werte. Befund 316 hatte aber die andere Gestalt - eine
Groesse, die nur **einmal** dastand, und zwar mit dem Wert des anderen
Betriebspunkts:

    WIE WEIT ES NOCH IST
      Bestand allein   mindestens 2152 Tage (5.9 Jahre) ...

Das ist der Spot-Wert, unter einem Kopf, der seit Befund 311 'Perpetual'
sagt; am gemeldeten Punkt sind es 3042 Tage. Kein Doppelgaenger, keine
Prozentzahl - die Wache von 231 konnte es nicht sehen.

Deshalb hier eine zweite Regel, ebenso mechanisch: Wo eine **punktabhaengige**
Groesse im Bericht steht, muss sie ihren Punkt nennen. Punktabhaengig heisst,
dass ``SPOTPUNKT`` und ``PERPETUALPUNKT`` verschiedene Werte dafuer liefern -
das ist im Code nachzusehen und nicht zu deuten.
"""

from __future__ import annotations

import collections
import re

from research.stand import Lage


def _bericht() -> Lage:
    return Lage(
        kandidat="Trend 50 Tage mit Konfluenz",
        maerkte="BTC + ETH, Tageskerzen",
        trades=152, sharpe_je_trade=0.2597, noetiger_sharpe=0.2987,
        bestanden=7, gesamt=11, offen=("Messlatte", "Deflated Sharpe"),
        versuche=198, cagr_pct=13.47, rueckgang_pct=10.64,
    )


def _prozente_je_abschnitt(text: str) -> dict[str, set[str]]:
    """Welcher Prozentwert steht in welchen Abschnitten?"""
    aus: dict[str, set[str]] = collections.defaultdict(set)
    abschnitt = "KOPF"
    for zeile in text.splitlines():
        if zeile.isupper() and len(zeile.strip()) > 4:
            abschnitt = zeile.strip()
        for m in re.finditer(r"[+-]?\d+[.,]\d+\s?%", zeile):
            aus[m.group().replace(" ", "")].add(abschnitt)
    return aus


#: Prozentwerte, die in zwei Abschnitten stehen duerfen - mit dem Grund.
MEHRFACH: dict[str, str] = {
    # Dieselbe Groesse, absichtlich zweimal: die Hebelnutzung aus Befund 106
    # steht im Register und in der Begruendung zu 'cli healthcheck'.
    "0,2%": "Hebelnutzung (Befund 106), Register und Nutzerbefehl",
    # Die Obergrenze der Preisspanne aus Befund 230 - im Abschnitt selbst
    # und im Registereintrag, der sie zitiert.
    "1,26%": "Preisspanne des Suchens (Befund 230), Abschnitt und Register",
    # Die beiden Kipppunkte aus Befund 250: einmal als Befund im Register,
    # einmal als das, wonach bei 'cli funding' zu schauen ist. Dieselbe
    # Messung, und genau die zwei Stellen, die sie brauchen - der dritte
    # Fundort ist mit ihr weggefallen, weil er noch das alte Sprossenpaar
    # trug.
    "6,0%": "Erster Kipppunkt, Schlechtestes Jahr (Befund 250)",
    "9,8%": "Zweiter Kipppunkt, Parameter-Plateau (Befund 250)",
    # Die Kennzahlen des Spot-Punkts selbst (Befund 281). Sie stehen in
    # mehreren Eintraegen, weil mehrere Befunde sie zitieren - 264 fuer den
    # Korb, 268 fuer die Aufstellung, 269 fuer das Skalieren - und seit 281
    # als **Gegenprobe** in der Reglertafel: Der Lauf muss bei 19,3 genau die
    # Zahlen liefern, die 'cli abstand --spot' unabhaengig meldet.
    #
    # Anders als bei den 3,36 % aus Befund 279, wo dieselbe Tafel zweimal
    # stand und die Wiederholung entfiel: Hier ist es **eine** Messung, die
    # verschiedene Befunde zu Recht nennen. Sie aus einem von ihnen zu
    # streichen machte den Eintrag vager, nicht kuerzer.
    "14,34%": "Jahresrendite am Spot-Punkt (Befund 108/281)",
    "9,87%": "Rueckgang am Spot-Punkt (Befund 108/281)",
    # Der Funding-Anteil auf gleichem Trade-Satz (Befund 339). Eine Messung,
    # zwei Eintraege, die sie brauchen: die offene Entscheidung zum
    # Stress-Umfang steht darauf, und der behobene Eintrag zu Befund 314
    # berichtigt mit ihr seine eigene Zahl. Aus einem von beiden gestrichen
    # waere der Eintrag vager, nicht kuerzer - derselbe Fall wie bei 14,34 %.
    "29,6%": "Funding-Anteil ohne Sperre (Befund 339), Entscheidung und Register",
}


class TestDerBerichtWidersprichtSichNicht:
    def test_die_luecke_steht_einmal_und_aus_den_eigenen_zahlen(self) -> None:
        """**Der Fall aus Befund 230**, festgehalten."""
        lage = _bericht()
        eigene = lage.noetiger_sharpe / lage.sharpe_je_trade - 1.0
        text = lage.bericht()

        assert f"{eigene:.0%}" in text
        assert "+24.3%" not in text, "Luecke vom anderen Betriebspunkt"

    def test_kein_unbekannter_wert_steht_in_zwei_abschnitten(self) -> None:
        """Ein neuer Doppelgaenger ist nicht automatisch falsch - er gehoert
        nur angesehen, wie die ueberholten Kennzahlen seit Befund 156."""
        gefunden = {
            wert: sorted(wo)
            for wert, wo in _prozente_je_abschnitt(_bericht().bericht()).items()
            if len(wo) > 1
        }

        assert set(gefunden) == set(MEHRFACH), (
            f"Prozentwert in zwei Abschnitten, ohne Eintrag in MEHRFACH: "
            f"{sorted(set(gefunden) - set(MEHRFACH))}"
        )

    def test_die_bekannten_doppelgaenger_haben_einen_grund(self) -> None:
        for wert, grund in MEHRFACH.items():
            assert grund, wert
            assert "Befund" in grund, wert

    def test_die_wache_sieht_ueberhaupt_etwas(self) -> None:
        """Sonst besteht der Test darueber, weil er nichts findet."""
        prozente = _prozente_je_abschnitt(_bericht().bericht())

        assert len(prozente) >= 20

    def test_die_regel_faende_den_stand_von_befund_230(self) -> None:
        """Gegenprobe: zwei Abschnitte, zwei verschiedene Luecken."""
        damals = (
            "URTEIL\n  um mindestens 15.0% steigen\n"
            "WIE WEIT ES NOCH IST\n  zu schliessende Luecke +24.3%\n"
        )
        gefunden = {
            wert for wert, wo in _prozente_je_abschnitt(damals).items() if len(wo) >= 1
        }

        assert "15.0%" in gefunden and "+24.3%" in gefunden
        assert "+24.3%" not in _bericht().bericht()


# ---------------------------------------------------------------------------
#  Die zweite Gestalt: eine Zahl vom anderen Punkt - Befund 317
# ---------------------------------------------------------------------------

#: ``Aussicht``-Staende ohne Betriebspunkt, mit dem Grund.
#:
#: Dieselbe Bauart wie ``MEHRFACH``: Wer hier etwas eintraegt, behauptet,
#: dass die Angabe **nicht zu haben** ist - nicht, dass sie unwichtig waere.
OHNE_PUNKT: dict[str, str] = {
    "AUSSICHT_VERBUND": (
        "Der Betriebspunkt des Verbunds ist nirgends festgehalten (Befund "
        "158/159 nennen ihn nicht). Eine geratene Angabe waere schlimmer als "
        "keine - der Bericht stellt die Zeile deshalb neben die beiden "
        "beschrifteten und nicht an ihre Stelle."
    ),
}


def _aussichten() -> dict[str, object]:
    """Jeder ``Aussicht``-Stand des Projekts - aus dem Modul, nicht aus einer
    zweiten Liste, die danebenlaufen koennte."""
    from research import referenz
    from research.referenz import Aussicht

    return {
        name: wert
        for name in dir(referenz)
        if isinstance(wert := getattr(referenz, name), Aussicht)
    }


class TestPunktabhaengigeZahlenNennenIhrenPunkt:
    """**Befund 317**, die Wache zu Befund 316."""

    def test_es_gibt_ueberhaupt_aussichten(self) -> None:
        """Sonst liefen die Tests darunter leer."""
        assert len(_aussichten()) >= 2

    def test_jede_aussicht_nennt_ihren_punkt_oder_steht_in_der_liste(self) -> None:
        stumm = sorted(
            name
            for name, a in _aussichten().items()
            if not a.betriebspunkt and name not in OHNE_PUNKT
        )

        assert stumm == [], (
            f"Aussicht ohne Betriebspunkt und ohne Eintrag in OHNE_PUNKT: "
            f"{stumm}. Ihre Entfernung liest sich dann als Aussage ueber den "
            f"gemeldeten Punkt - das war Befund 316."
        )

    def test_die_ausnahmen_haben_einen_grund(self) -> None:
        for name, grund in OHNE_PUNKT.items():
            assert name in _aussichten(), f"{name} gibt es nicht mehr"
            assert "Befund" in grund, name

    def test_wer_einen_punkt_nennt_schreibt_ihn_auch_an(self) -> None:
        for name, a in _aussichten().items():
            if a.betriebspunkt:
                assert a.betriebspunkt in a.als_zeile(), name

    def test_beide_punkte_stehen_im_bericht(self) -> None:
        """**Der Kern von 316.** Stuende nur einer da, liesse sich die
        Entfernung nicht einordnen - und die guenstigere liest sich wie
        Fortschritt."""
        from research.referenz import AUSSICHT, AUSSICHT_ERSTPUNKT

        text = _bericht().bericht()

        assert AUSSICHT_ERSTPUNKT.als_zeile() in text
        assert AUSSICHT.als_zeile() in text

    def test_die_verlangte_evidenz_steht_fuer_beide_punkte_da(self) -> None:
        """Dieselbe Groesse, beide Punkte: 190 gegen 221 Beobachtungen."""
        from research.referenz import PERPETUALPUNKT, SPOTPUNKT

        text = _bericht().bericht()

        assert str(SPOTPUNKT.noetiges_n()) in text
        assert str(PERPETUALPUNKT.noetiges_n()) in text

    def test_die_regel_faende_den_stand_von_befund_316(self) -> None:
        """**Gegenprobe, damit die Wache Zaehne hat.**

        So sah die Aussicht vor 316 aus: gerechnet, getestet, richtig - und
        ohne ein Wort darueber, fuer welche Handelsbedingungen sie gilt.
        """
        from dataclasses import replace

        from research.referenz import AUSSICHT

        damals = replace(AUSSICHT, betriebspunkt="")

        assert not damals.betriebspunkt
        assert "Spot" not in damals.als_zeile()
        assert "Perpetual" not in damals.als_zeile()
        # Und die Zahl, die dann als einzige dastand, ist die guenstigere.
        from research.referenz import AUSSICHT_ERSTPUNKT

        assert damals.jahre < AUSSICHT_ERSTPUNKT.jahre
