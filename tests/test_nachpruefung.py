"""Der Katalog, nachgemessen - nachdem sich das Messgeraet geaendert hat.

Ein Urteil ueber eine Strategie ist nur so gut wie das Geraet, mit dem es
zustande kam. Zwei Fehler im Instrument sind gefunden worden (Nachlauf am
Fensterende, Aufwaermphase der Konfluenz), also ist der ganze Katalog neu zu
messen.

Zwei Tests tragen die Datei:

* ``test_rangfolge_geht_nach_gates_nicht_nach_rendite`` - die Reihenfolge ist
  eine Aussage. Nach Rendite zu sortieren hat in diesem Projekt schon zweimal
  einen Kandidaten nach oben getragen, der an einer Risikogrenze scheiterte.
* ``test_unbekannte_kandidaten_gelten_nicht_als_veraendert`` - wer nie gemessen
  wurde, hat sich nicht veraendert. Sonst faende jeder Lauf lauter
  "Verbesserungen", die nur fehlende Vergangenheit sind.
"""

from __future__ import annotations

from research.nachpruefung import Ergebnis, Nachpruefung


def _ergebnis(
    name: str,
    bestanden: int,
    *,
    kennung: str | None = None,
    dsr: float = 0.5,
    cagr: float = 10.0,
    gesamt: int = 11,
    offen: tuple[str, ...] = ("Deflated Sharpe",),
) -> Ergebnis:
    return Ergebnis(
        genome_id=kennung or name.lower().replace(" ", ""),
        name=name,
        generation=1,
        bestanden=bestanden,
        gesamt=gesamt,
        offen=offen if bestanden < gesamt else (),
        trades=150,
        cagr_pct=cagr,
        rueckgang_pct=9.0,
        dsr=dsr,
    )


class TestRangfolge:
    def test_rangfolge_geht_nach_gates_nicht_nach_rendite(self) -> None:
        """**Die Reihenfolge ist eine Aussage.**

        Der Kandidat mit der hoechsten Rendite steht hier hinten, weil er
        weniger Gates besteht. Nach Rendite zu sortieren hat in diesem Projekt
        schon zweimal einen Kandidaten nach oben getragen, der an einer
        Risikogrenze scheiterte.
        """
        lauf = Nachpruefung(
            [
                _ergebnis("Renditestark", 5, cagr=90.0),
                _ergebnis("Solide", 9, cagr=11.0),
                _ergebnis("Mittel", 7, cagr=40.0),
            ]
        )

        assert [e.name for e in lauf.rangfolge] == ["Solide", "Mittel", "Renditestark"]
        assert lauf.bester is not None and lauf.bester.name == "Solide"

    def test_bei_gleichstand_entscheidet_der_deflated_sharpe(self) -> None:
        lauf = Nachpruefung(
            [_ergebnis("A", 8, dsr=0.70), _ergebnis("B", 8, dsr=0.86)]
        )

        assert [e.name for e in lauf.rangfolge] == ["B", "A"]

    def test_ohne_ergebnisse(self) -> None:
        leer = Nachpruefung()

        assert leer.bester is None
        assert leer.rangfolge == []
        assert "Nichts gemessen" in leer.tabelle()
        assert "kein Urteil" in leer.urteil()


class TestZulassung:
    def test_alle_gates_bestanden(self) -> None:
        lauf = Nachpruefung([_ergebnis("Voll", 11), _ergebnis("Fast", 10)])

        assert [e.name for e in lauf.zugelassen] == ["Voll"]
        assert "bestehen alle Gates" in lauf.urteil()

    def test_urteil_bleibt_vorsichtig(self) -> None:
        """Wer hier weit kommt, ist damit **nicht** zugelassen - er ist einer
        aus 53, und genau dafuer steht die Huerde da, wo sie steht."""
        lauf = Nachpruefung([_ergebnis("Voll", 11)])

        assert "Zugelassen ist damit noch keiner" in lauf.urteil()

    def test_urteil_nennt_die_offenen_gates(self) -> None:
        lauf = Nachpruefung(
            [_ergebnis("Fast", 9, offen=("Messlatte", "Deflated Sharpe"))]
        )

        text = lauf.urteil()

        assert "Kein Kandidat besteht alle Gates" in text
        assert "Messlatte" in text and "Deflated Sharpe" in text

    def test_null_gates_zaehlt_nicht_als_zugelassen(self) -> None:
        """Ein Lauf ohne ausgewertete Gates ist kein bestandener Lauf."""
        leer = Ergebnis(
            genome_id="x", name="Leer", generation=1, bestanden=0, gesamt=0
        )

        assert not leer.zugelassen


class TestVeraenderungen:
    def test_besser_und_schlechter_werden_erkannt(self) -> None:
        lauf = Nachpruefung(
            [
                _ergebnis("Steigt", 9, kennung="a"),
                _ergebnis("Faellt", 5, kennung="b"),
                _ergebnis("Gleich", 7, kennung="c"),
            ]
        )

        geaendert = lauf.veraenderungen({"a": 7, "b": 8, "c": 7})

        assert {v.ergebnis.name: v.richtung for v in geaendert} == {
            "Steigt": "besser",
            "Faellt": "schlechter",
        }

    def test_unbekannte_kandidaten_gelten_nicht_als_veraendert(self) -> None:
        """**Wer nie gemessen wurde, hat sich nicht veraendert.**

        Sonst faende jeder Lauf lauter "Verbesserungen", die nur fehlende
        Vergangenheit sind.
        """
        lauf = Nachpruefung([_ergebnis("Neu", 9, kennung="neu")])

        assert lauf.veraenderungen({}) == []
        assert lauf.veraenderungen({"anderer": 3}) == []

    def test_text_nennt_beide_zahlen(self) -> None:
        lauf = Nachpruefung([_ergebnis("Steigt", 9, kennung="a")])

        text = str(lauf.veraenderungen({"a": 7})[0])

        assert "7 -> 9" in text
        assert "besser" in text


class TestTabelle:
    def test_kopf_und_zeilen(self) -> None:
        lauf = Nachpruefung([_ergebnis("Einer", 8)])

        zeilen = lauf.tabelle().splitlines()

        assert "Gates" in zeilen[0] and "DSR" in zeilen[0]
        assert zeilen[2].startswith("Einer")
        assert "8/11" in zeilen[2]

    def test_lange_liste_wird_gekuerzt(self) -> None:
        lauf = Nachpruefung(
            [_ergebnis(f"K{i}", i % 11, kennung=f"k{i}") for i in range(30)]
        )

        text = lauf.tabelle(hoechstens=5)

        assert "und 25 weitere" in text


class TestGateZahlIstKeinAbstand:
    """**Die Zahl bestandener Gates ist ein schlechtes Mass fuer Naehe.**

    Gemessen am Katalog: Der Erste steht bei 8 von 11 mit einem Deflated
    Sharpe von 0,486, der Vierte bei 7 von 11 mit 0,864. Das haerteste Gate
    verlangt 0,95 - und es ist dasjenige, das sich mit keinem Regler bewegen
    laesst.
    """

    def test_urteil_nennt_den_besseren_deflated_sharpe(self) -> None:
        lauf = Nachpruefung(
            [
                _ergebnis("Viele Gates", 8, kennung="a", dsr=0.486),
                _ergebnis("Hoher DSR", 7, kennung="b", dsr=0.864),
            ]
        )

        text = lauf.urteil()

        assert "Viele Gates" in text
        assert "Hoher DSR" in text and "0.864" in text
        assert "sagt wenig darueber, wer naeher dran ist" in text

    def test_kein_zusatz_wenn_derselbe_vorn_steht(self) -> None:
        """Kein Hinweis, wo es nichts zu unterscheiden gibt."""
        lauf = Nachpruefung(
            [
                _ergebnis("Vorn", 9, kennung="a", dsr=0.9),
                _ergebnis("Hinten", 6, kennung="b", dsr=0.2),
            ]
        )

        assert "Den hoechsten Deflated Sharpe" not in lauf.urteil()


class TestVorauswahl:
    """**Eine Vorauswahl kann nichts zulassen.**

    ``--schnell`` laesst die teuren Gates aus - Parameter-Plateau und
    Kosten-Stress, also ausgerechnet die, die zusaetzliche Backtests brauchen.
    Wer dann neun von neun besteht, hat neun von elf bestanden.
    """

    def test_vollstaendige_neun_gelten_nicht_als_zugelassen(self) -> None:
        vorab = Ergebnis(
            genome_id="x", name="Schnell", generation=6,
            bestanden=9, gesamt=9, vorauswahl=True,
        )

        assert not vorab.zugelassen

    def test_ohne_vorauswahl_zaehlt_es(self) -> None:
        voll = Ergebnis(
            genome_id="x", name="Voll", generation=6, bestanden=11, gesamt=11
        )

        assert voll.zugelassen

    def test_urteil_meldet_keine_zulassung_aus_der_vorauswahl(self) -> None:
        lauf = Nachpruefung(
            [
                Ergebnis(
                    genome_id="x", name="Schnell", generation=6,
                    bestanden=9, gesamt=9, vorauswahl=True, dsr=0.9,
                )
            ]
        )

        assert lauf.zugelassen == []
        assert "Kein Kandidat besteht alle Gates" in lauf.urteil()
