"""Trennt irgendetwas die guten Trades von den schlechten?

Die Messung ist einfach - Trades aufteilen, Raenge vergleichen. Alles, was
hier schwierig ist, steckt in der **Null**, und deshalb steht sie im
Mittelpunkt dieser Tests:

* ``test_ein_merkmal_das_nur_schlechte_jahre_markiert_gilt_nicht`` - der
  entscheidende. Merkmale sind ueber die Jahre ungleich verteilt; wer frei
  mischt, haelt jede Jahres-Konjunktur fuer eine Trennung. Der Test baut genau
  so ein Merkmal und verlangt, dass die freie Null es durchwinkt und die
  blockweise es ablehnt. Faellt die blockweise weg, faellt dieser Test.
* ``test_mehr_merkmale_heben_die_schranke`` - wer zwoelf prueft, findet immer
  eines. Die Schranke muss mit der Familie wachsen.

Beim ersten Lauf auf echten Daten hat genau dieser Unterschied das Ergebnis
gedreht: Das beste Merkmal kam auf z = -2,91, die freie Schranke lag bei 2,80,
die blockweise bei 3,83. Ohne den Blockmischer waere ein Befund berichtet
worden, den es nicht gibt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from research.trennschaerfe import (
    KATALOG,
    MIND_TRADES,
    Merkmal,
    Trennung,
    messe,
    rangsumme,
)


@dataclass(frozen=True)
class FakeTrade:
    """Nur das, was ``messe`` liest - kein Backtest noetig."""

    entry_time: datetime
    r_multiple: float | None


def welt(
    *, jahre: int = 6, je_jahr: int = 30, saat: int = 5
) -> tuple[list[FakeTrade], list[pd.Timestamp]]:
    """Trades gleichmaessig ueber mehrere Jahre, mit Zeitstempeln."""
    zeiten = [
        pd.Timestamp(datetime(2018 + j, 1 + (i % 12), 1 + (i % 27), tzinfo=UTC))
        for j in range(jahre)
        for i in range(je_jahr)
    ]
    rng = np.random.default_rng(saat)
    trades = [
        FakeTrade(entry_time=z.to_pydatetime(), r_multiple=float(w))
        for z, w in zip(zeiten, rng.normal(0.5, 2.0, len(zeiten)), strict=True)
    ]
    return trades, zeiten


def reihen(zeiten, marken: dict[str, list[bool]]) -> dict[str, dict[str, pd.Series]]:
    """Merkmalsreihen in der Form, die ``messe`` erwartet."""
    index = pd.DatetimeIndex(zeiten)
    return {"M": {name: pd.Series(werte, index=index) for name, werte in marken.items()}}


class TestRangsumme:
    def test_gleiche_verteilungen_geben_null(self) -> None:
        werte = np.arange(100, dtype=float)

        assert abs(rangsumme(werte[::2], werte[1::2])) < 1.0

    def test_klare_trennung_gibt_einen_grossen_wert(self) -> None:
        assert rangsumme(np.arange(50, 100.0), np.arange(0, 50.0)) > 5.0

    def test_ein_ausreisser_kippt_sie_nicht(self) -> None:
        """**Der Grund, warum hier Raenge stehen und keine Mittelwerte.**

        Ein einziger +200-R-Trade macht aus einer nicht vorhandenen Trennung
        einen riesigen Mittelwertunterschied. Die Rangsumme sieht ihn als
        einen von fuenfzig.
        """
        a = np.array([*np.zeros(49), 200.0])
        b = np.zeros(50)

        assert abs(np.mean(a) - np.mean(b)) == pytest.approx(4.0)
        assert abs(rangsumme(a, b)) < 2.0

    def test_leere_seite_gibt_null(self) -> None:
        assert rangsumme(np.array([]), np.arange(10.0)) == 0.0


class TestMerkmal:
    def test_entweder_schwelle_oder_median(self) -> None:
        with pytest.raises(ValueError, match="entweder"):
            Merkmal("Beides nicht")

    def test_der_katalog_steht_fest_und_ist_eindeutig(self) -> None:
        """**Ein Katalog, der nach jeder Messung waechst, macht die Korrektur
        wertlos.** Dann ist die Zahl der Versuche unbekannt, und "das Beste aus
        zwoelf" ist in Wahrheit das Beste aus beliebig vielen.
        """
        namen = [m.name for m in KATALOG]

        assert len(namen) == len(set(namen))
        assert len(KATALOG) >= 8


class TestFamilie:
    def test_zu_kleine_eimer_zaehlen_nicht_mit(self) -> None:
        """Ein Merkmal, das drei Trades abtrennt, kann nichts zeigen - und
        darf die Schranke fuer die anderen nicht mit hochtreiben."""
        trades, zeiten = welt()
        klein = [i < 3 for i in range(len(zeiten))]
        gross = [i % 2 == 0 for i in range(len(zeiten))]

        ergebnis = messe(
            trades,
            reihen(zeiten, {KATALOG[0].name: klein, KATALOG[1].name: gross}),
            permutationen=200,
        )

        namen = [t.name for t in ergebnis.familie]
        assert KATALOG[1].name in namen
        assert KATALOG[0].name not in namen
        # Gezeigt wird es trotzdem - verschweigen waere das Gegenteil.
        assert KATALOG[0].name in ergebnis.tabelle()
        assert "zu wenige" in ergebnis.tabelle()

    def test_mehr_merkmale_heben_die_schranke(self) -> None:
        """**Wer zwoelf prueft, findet immer eines.**

        Dieselben Trades, einmal mit einem Merkmal geprueft und einmal mit
        sechs: Die Schranke fuer das Beste muss im zweiten Fall hoeher liegen,
        sonst korrigiert sie nichts.
        """
        trades, zeiten = welt()
        rng = np.random.default_rng(3)
        rauschen = {
            m.name: list(rng.random(len(zeiten)) > 0.5) for m in KATALOG[:6]
        }

        eines = messe(
            trades,
            reihen(zeiten, {KATALOG[0].name: rauschen[KATALOG[0].name]}),
            permutationen=400,
        )
        sechs = messe(trades, reihen(zeiten, rauschen), permutationen=400)

        assert len(eines.familie) == 1
        assert len(sechs.familie) == 6
        assert sechs.schranke > eines.schranke


class TestBlockNull:
    def test_ein_merkmal_das_nur_schlechte_jahre_markiert_gilt_nicht(self) -> None:
        """**Der Test, der diese Messung ehrlich haelt.**

        Gebaut wird ein Merkmal, das mit dem einzelnen Trade nichts zu tun hat:
        Es ist in zwei Jahren durchgehend wahr und sonst falsch - und ausgerechnet
        diese beiden Jahre liefen schlecht. Frei gemischt sieht das aus wie eine
        Trennung. Innerhalb der Jahre gemischt bleibt nichts davon uebrig, denn
        dort trennt es gar nichts.

        Genau dieser Unterschied hat beim ersten Lauf auf echten Daten das
        Ergebnis gedreht.
        """
        jahre, je_jahr = 6, 30
        _, zeiten = welt(jahre=jahre, je_jahr=je_jahr)
        rng = np.random.default_rng(11)
        schlecht = {2018, 2019}
        trades = [
            FakeTrade(
                entry_time=z.to_pydatetime(),
                r_multiple=float(
                    rng.normal(-1.0 if z.year in schlecht else 1.0, 1.0)
                ),
            )
            for z in zeiten
        ]
        marke = [z.year in schlecht for z in zeiten]

        ergebnis = messe(
            trades, reihen(zeiten, {KATALOG[0].name: marke}), permutationen=600
        )
        beste = ergebnis.beste

        assert beste is not None
        assert abs(beste.z) > ergebnis.schranke_frei, (
            "Frei gemischt muesste dieses Merkmal als Trennung durchgehen - "
            "sonst zeigt der Test nicht, wovor die Blockvariante schuetzt"
        )
        assert not ergebnis.belegt
        assert ergebnis.schranke > ergebnis.schranke_frei

    def test_eine_echte_trennung_ueberlebt_die_bloecke(self) -> None:
        """Die Gegenprobe. Eine Blockvariante, die **alles** ablehnt, waere
        kein strenger Test, sondern ein kaputter."""
        _, zeiten = welt(jahre=6, je_jahr=30)
        rng = np.random.default_rng(17)
        marke = [i % 2 == 0 for i in range(len(zeiten))]
        trades = [
            FakeTrade(
                entry_time=z.to_pydatetime(),
                r_multiple=float(rng.normal(2.0 if m else -2.0, 1.0)),
            )
            for z, m in zip(zeiten, marke, strict=True)
        ]

        ergebnis = messe(
            trades, reihen(zeiten, {KATALOG[0].name: marke}), permutationen=600
        )

        assert ergebnis.belegt
        assert ergebnis.bloecke == 6


class TestBericht:
    def test_ohne_deutbare_merkmale_folgt_nichts(self) -> None:
        trades, zeiten = welt(jahre=2, je_jahr=5)

        ergebnis = messe(
            trades,
            reihen(zeiten, {KATALOG[0].name: [True] * len(zeiten)}),
            permutationen=50,
        )

        assert ergebnis.beste is None
        assert not ergebnis.belegt
        assert "folgt nichts" in ergebnis.urteil()

    def test_das_urteil_nennt_beide_schranken(self) -> None:
        """Die blockweise ist verbindlich, die freie steht daneben - wer nur
        eine Zahl sieht, kann nicht erkennen, woran es lag."""
        trades, zeiten = welt()
        marke = [i % 2 == 0 for i in range(len(zeiten))]

        ergebnis = messe(
            trades, reihen(zeiten, {KATALOG[0].name: marke}), permutationen=200
        )

        assert "blockweise" in ergebnis.urteil()
        assert "frei gemischt" in ergebnis.urteil()

    def test_ein_befund_ist_keine_strategie(self) -> None:
        """Der Satz muss dranstehen: Wer ein Merkmal einbaut, hat einen neuen
        Kandidaten gebaut - ein Versuch mehr, und durch alle elf Gates."""
        bericht = messe([], {}, permutationen=10)
        bericht.trennungen = [
            Trennung(name="X", wahr=tuple(range(30)), falsch=tuple(range(30, 60)), z=9.9)
        ]
        bericht.schranke = 1.0

        assert bericht.belegt
        assert "elf Gates" in bericht.urteil()

    def test_mindestgroesse_ist_eine_zahl_und_kein_gefuehl(self) -> None:
        assert MIND_TRADES >= 20
