"""Dieselbe Regel unter mehreren Namen - und was sie in einer Statistik anrichtet.

Zwei Tests tragen diese Datei:

``test_ein_duplikat_hebt_den_t_wert`` - Der Grund, warum das ueberhaupt ein
Modul ist. Ein Duplikat ist keine zweite Beobachtung; es senkt die Streuung
und hebt jeden t-Wert, also genau das, was ueber "nachweisbar" entscheidet.

``test_verglichen_werden_trades_und_nicht_kennzahlen`` - Zwei verschiedene
Regeln koennen zufaellig denselben Sharpe haben. Wer ueber Kennzahlen
entdoppelt, loescht eine echte Beobachtung.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from research.entdopplung import Entdoppelt, entdoppele, signatur

ANFANG = datetime(2018, 1, 1, tzinfo=UTC)


@dataclass
class FakeTrade:
    net_pnl: float
    entry_time: datetime
    exit_time: datetime
    symbol: str = "BTCUSDT"


def trades(werte, *, versatz: int = 0) -> list[FakeTrade]:
    return [
        FakeTrade(
            net_pnl=float(w),
            entry_time=ANFANG + timedelta(days=i * 5 + versatz),
            exit_time=ANFANG + timedelta(days=i * 5 + versatz + 1),
        )
        for i, w in enumerate(werte)
    ]


class TestSignatur:
    def test_gleiche_trades_gleiche_signatur(self) -> None:
        werte = [1.0, -0.5, 2.25]

        assert signatur(trades(werte)) == signatur(trades(werte))

    def test_verglichen_werden_trades_und_nicht_kennzahlen(self) -> None:
        """**Der Test, der die Wahl der Signatur begruendet.**

        Zwei verschiedene Regeln mit exakt demselben Mittelwert und derselben
        Streuung - nur andere Reihenfolge der Ergebnisse. Ueber Kennzahlen
        waeren sie ununterscheidbar, und eine echte Beobachtung ginge
        verloren. Ueber die Trades bleiben es zwei.
        """
        eins = trades([1.0, -1.0, 2.0, -2.0])
        zwei = trades([2.0, -2.0, 1.0, -1.0])
        werte_eins = np.array([t.net_pnl for t in eins])
        werte_zwei = np.array([t.net_pnl for t in zwei])

        assert werte_eins.mean() == werte_zwei.mean()
        assert werte_eins.std() == werte_zwei.std()
        assert signatur(eins) != signatur(zwei)
        assert len(entdoppele({"a": eins, "b": zwei}).laeufe) == 2

    def test_gleiche_werte_zu_anderen_zeiten_sind_verschieden(self) -> None:
        """Dieselben Ergebnisse, um einen Tag verschoben - das ist eine andere
        Regel, denn die Zeitachse entscheidet ueber Gleichzeitigkeit."""
        werte = [1.0, -0.5, 2.25]

        assert signatur(trades(werte)) != signatur(trades(werte, versatz=1))


class TestEntdopplung:
    def test_der_erste_name_bleibt(self) -> None:
        """Wer den Bestand zuerst uebergibt, behaelt seinen Namen - unter dem
        steht er in jedem anderen Bericht."""
        werte = [1.0, -0.5, 2.25]
        ergebnis = entdoppele(
            {"Bestand": trades(werte), "Klon A": trades(werte), "Klon B": trades(werte)}
        )

        assert list(ergebnis.laeufe) == ["Bestand"]
        assert ergebnis.entfernt == 2
        assert ergebnis.doppel == {"Klon A": "Bestand", "Klon B": "Bestand"}
        assert ergebnis.gruppen == {"Bestand": ["Klon A", "Klon B"]}

    def test_ohne_doppel_bleibt_alles(self) -> None:
        ergebnis = entdoppele(
            {"a": trades([1.0, 2.0]), "b": trades([3.0, 4.0])}
        )

        assert len(ergebnis.laeufe) == 2
        assert ergebnis.entfernt == 0
        assert ergebnis.hinweis() == ""

    def test_der_hinweis_nennt_ross_und_reiter(self) -> None:
        werte = [1.0, -0.5, 2.25]
        ergebnis = entdoppele(
            {"Bestand": trades(werte), "Klon": trades(werte), "andere": trades([9.0])}
        )
        hinweis = ergebnis.hinweis()

        assert "1 von 3" in hinweis
        assert "'Bestand' steht auch fuer 1 weitere" in hinweis

    def test_leere_eingabe_ist_kein_fehler(self) -> None:
        leer = entdoppele({})

        assert leer.laeufe == {}
        assert leer.entfernt == 0
        assert Entdoppelt().hinweis() == ""


class TestWirkung:
    def test_ein_duplikat_hebt_den_t_wert(self) -> None:
        """**Der Test, der erklaert, warum das ein Modul ist.**

        Sieben Kopien einer Regel in einem Feld von 21 - so lag der Katalog in
        Befund 86 und 87. Der t-Wert einer Korrelation steigt dadurch, ohne
        dass eine einzige neue Beobachtung dazugekommen waere. Genau daran ist
        dort ein Schluss gescheitert, der wie eine Aussage aussah.

        Geprueft wird die Falsch-Positiv-Rate ueber 400 Ziehungen, nicht ein
        Einzelfall: Bei **unkorrelierten** Groessen darf die Schwelle |t| = 2
        in rund 5 % der Faelle fallen. Mit sechs Kopien eines Punktes wird
        daraus ein Vielfaches - und genau das ist in Befund 86 und 87
        passiert.
        """

        def t_von(x, y) -> float:
            r = float(np.corrcoef(x, y)[0, 1])
            n = len(x)
            if abs(r) >= 1.0:
                return float("inf")
            return abs(r * ((n - 2) / (1 - r * r)) ** 0.5)

        wuerfel = np.random.default_rng(2026)
        sauber = doppelt = 0
        zuege = 400
        for _ in range(zuege):
            a = wuerfel.normal(0.0, 1.0, 15)
            b = wuerfel.normal(0.0, 1.0, 15)
            sauber += t_von(a, b) >= 2.0
            # Denselben Punkt sechsmal zusaetzlich einhaengen - keine neue
            # Information, nur mehr Zeilen.
            doppelt += (
                t_von(
                    np.concatenate([a, np.repeat(a[0], 6)]),
                    np.concatenate([b, np.repeat(b[0], 6)]),
                )
                >= 2.0
            )

        assert sauber / zuege < 0.10, f"ohne Duplikate {sauber / zuege:.1%}"
        assert doppelt > 2 * sauber, (
            f"ohne Duplikate {sauber / zuege:.1%}, mit {doppelt / zuege:.1%} - "
            "der Sprung ueber die Nachweisschwelle, um den es geht"
        )
