"""Was ein Bein kostet, wenn man es wirklich zulaesst - Befund 318.

Befund 264 endet mit einer offenen Entscheidung: *"Korbhandel bauen oder je
Bein zulassen."* Daneben standen die Zahlen 9/11 fuer den Korb und 8/11 fuer
jedes Bein.

Die 8/11 messen den Korb, **auf ein Bein gekuerzt, auf demselben Zeitraum**.
Fuer die Frage, die 264 gestellt hat - "was liefe 'cli trade', und ist das,
was bestanden hat?" - ist das die richtige Zahl.

Fuer die Frage, mit der der Eintrag **endet**, ist es die falsche. Wer ein
Bein zulaesst, misst es auf seiner eigenen Reihe: BTC beginnt am 01.01.2012
und nicht am 16.08.2017, 5355 Balken gegen 3301. Dort steht es bei **5 von
11** - drei Gates mehr fallen, weil die Jahre 2012 bis 2017 den Absturz von
2014/15 tragen.

    Umfang                          Tage   Trades   n_eff   DSR      Gates
    Korb BTC+ETH, gemeinsam         3300      158     115   0,5826    9/11
    BTC allein, gemeinsam           3300       77      67   0,1077    8/11
    BTC allein, ganze Reihe         5354      117     107   0,4560    5/11

Die Gate-Zahlen standen schon in ``reports/marktkombinationen`` - ``cli
marktkombinationen`` faehrt jede Kombination auf ihrem **eigenen**
gemeinsamen Bereich. Neu ist ``n_eff``, das der Bericht nicht speichert, und
die Zuordnung zur Entscheidung.

Diese Tests rechnen nichts nach. Sie halten fest, dass der Eintrag beide
Umfaenge nennt und nicht den einen fuer den anderen ausgibt - und dass der
Bericht, auf den er sich beruft, die Zahl wirklich traegt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.stand import OFFEN

BERICHTE = Path("reports/marktkombinationen")


def _eintrag():
    return next(r for r in OFFEN if "Zugelassen ist der Korb" in r.name)


def _juengster_bericht() -> dict:
    dateien = sorted(BERICHTE.glob("*.json"))
    if not dateien:
        pytest.skip("keine Marktkombinationen im Berichtsordner")
    return json.loads(dateien[-1].read_text(encoding="utf-8"))


class TestDerEintragNenntBeideUmfaenge:
    def test_die_gekuerzte_zahl_steht_weiter_da(self) -> None:
        """8/11 bleibt - sie beantwortet die Frage aus 264 richtig."""
        assert "8/11" in _eintrag().ergebnis

    def test_die_zulassungszahl_steht_daneben(self) -> None:
        """**Der Kern.** Ohne sie liest sich 8/11 als Preis der zweiten
        Wahl, und der ist gemessen ein anderer."""
        text = _eintrag().ergebnis

        assert "5 von 11" in text
        assert "117 Trades" in text

    def test_der_eintrag_sagt_welche_zahl_zu_welcher_frage_gehoert(self) -> None:
        """Zwei Zahlen nebeneinander ohne Zuordnung waeren ein Widerspruch
        statt einer Auskunft - dieselbe Lehre wie in Befund 316."""
        text = _eintrag().ergebnis

        assert "demselben" in text, "der Zeitraum der 8/11 muss dastehen"
        assert "eigenen Reihe" in text, "der Zeitraum der 5/11 muss dastehen"

    def test_die_beobachtungen_stehen_beide_da(self) -> None:
        """67 auf 107 zeigt, dass die laengere Reihe wirkt; 115 zeigt, dass
        sie nicht reicht. Eine der drei allein sagt das Gegenteil."""
        text = _eintrag().ergebnis

        assert "67 auf 107" in text
        assert "115" in text

    def test_der_eintrag_nennt_seine_quelle(self) -> None:
        """Die Hausregel: Wer eine Zahl nennt, nennt den Weg dorthin - und
        hier ist es ein Bericht, der laengst im Ordner liegt."""
        assert "reports/marktkombinationen" in _eintrag().ergebnis


class TestDerBerichtTraegtDieZahlWirklich:
    """**Die Gegenprobe.** Ein Eintrag, der sich auf einen Bericht beruft,
    ist nur so viel wert wie der Bericht - sonst steht eine Behauptung mit
    einer Fundstelle davor."""

    def test_es_gibt_eine_zeile_fuer_btc_allein(self) -> None:
        bericht = _juengster_bericht()
        einzeln = [k for k in bericht["kombinationen"] if k["anzahl"] == 1]

        assert einzeln, "keine Einzelmarkt-Zeile im Bericht"
        assert any(k["maerkte"] == "BTC" for k in einzeln)

    def test_btc_allein_besteht_dort_fuenf_von_elf(self) -> None:
        bericht = _juengster_bericht()
        btc = next(
            k for k in bericht["kombinationen"]
            if k["anzahl"] == 1 and k["maerkte"] == "BTC"
        )

        assert btc["bestanden"] == 5
        assert btc["gesamt"] == 11
        assert btc["trades"] == 117

    def test_und_zwar_auf_der_laengeren_reihe(self) -> None:
        """**Woran das haengt.** Auf dem gemeinsamen Bereich handelt BTC 77
        Trades; die 117 des Berichts gibt es nur auf der ganzen Reihe. Liefe
        'marktkombinationen' kuenftig auf dem Korbbereich, stuende hier
        dieselbe Zahl wie in 264 - und der Eintrag verglichen zweimal
        dasselbe.
        """
        bericht = _juengster_bericht()
        btc = next(
            k for k in bericht["kombinationen"]
            if k["anzahl"] == 1 and k["maerkte"] == "BTC"
        )
        korb = next(
            k for k in bericht["kombinationen"] if k["maerkte"] == "BTC+ETH"
        )

        assert btc["trades"] > 77, "das waere der gemeinsame Bereich"
        assert btc["bestanden"] < korb["bestanden"]

    def test_der_korb_bleibt_die_beste_aufstellung(self) -> None:
        """Die Aussage, die der Eintrag traegt: Kein Einzelmarkt kommt an den
        Korb heran - auch nicht mit seiner ganzen Historie."""
        bericht = _juengster_bericht()
        bester_einzeln = max(
            (k for k in bericht["kombinationen"] if k["anzahl"] == 1),
            key=lambda k: k["bestanden"],
        )
        korb = next(
            k for k in bericht["kombinationen"] if k["maerkte"] == "BTC+ETH"
        )

        assert korb["bestanden"] > bester_einzeln["bestanden"]
