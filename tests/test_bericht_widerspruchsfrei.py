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
sie den Text verstehen. Sie prueft daher zwei Dinge, die sich mechanisch
sagen lassen:

* Die Luecke steht **einmal**, und zwar mit dem Wert aus den eigenen Zahlen
  des Berichts. Das ist der Fall aus Befund 230, festgehalten.
* Jeder Prozentwert, der in mehr als einem Abschnitt auftaucht, steht in
  einer bekannten Liste. Kommt ein neuer dazu, faellt er auf und jemand sieht
  hin - so wie bei den ueberholten Kennzahlen seit Befund 156.

Nachgemessen bei ihrer Anlage: Der Bericht nennt 25 verschiedene
Prozentwerte, zwei davon in zwei Abschnitten, und beide zu Recht.
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
