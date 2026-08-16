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
