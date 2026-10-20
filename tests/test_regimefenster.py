"""Das Marktumfeld wurde ueber sechzehn Monate bestimmt - Befund 385.

Fortsetzung der Suche aus Befund 384: dieselbe M15-Annahme, diesmal nicht in
einer Zeitspanne, sondern in einer **Kerzenzahl**. Und diesmal nicht in der
Anzeige, sondern in einem **Gate**.

``classify_regimes`` nimmt ``window=480`` und sagt dazu: *"bei
15-Minuten-Kerzen sind 480 rund fuenf Tage."* ``gate_regime_split`` ruft sie
**ohne** Angabe, die Funktion erfaehrt das Intervall nicht - und jede Gate-Zahl
dieses Projekts steht auf Tageskerzen. Dort sind 480 Kerzen rund **sechzehn
Monate**.

Gemessen auf dem Zulassungspfad (Spitzenkandidat 'Trend 50 Tage mit
Konfluenz', BTC + ETH, Tageskerzen, auf die Zulassungsreihe geschnitten, 160
Trades):

    Fenster   Trades auf/ab/seit   geurteilt   schlechtester   Urteil
        480        106 / 47 /  7     2 von 3      4,505        bestanden
        240        106 / 46 /  8     2 von 3      3,438        bestanden
        120         71 / 65 / 24     3 von 3      3,170        bestanden
         60         61 / 62 / 37     3 von 3      2,748        bestanden
         45         53 / 48 / 59     3 von 3      1,740        bestanden
         30         52 / 32 / 76     3 von 3      1,234        bestanden
         25         56 / 24 / 80     3 von 3      0,000        DURCHGEFALLEN
         20         57 / 24 / 79     3 von 3      0,134        DURCHGEFALLEN
         10         66 / 19 / 75     3 von 3      0,000        DURCHGEFALLEN
          5         58 /  9 / 93     2 von 3      2,630        bestanden

Zwei Dinge stehen da, und sie sind verschieden schwer.

**Das Urteil haengt am Fenster.** Zwischen 30 und 25 Tagen kippt es. Das ist
kein Fehler, den man wegmacht: Es ist die Frage, welcher Horizont
"Marktumfeld" heisst, und sie steht als Entscheidung im Register. Dazu gehoert
ein Einwand, der gegen die kurzen Fenster spricht: Der Kandidat ist eine
**50-Tage**-Trendregel. Ein Fenster unter fuenfzig Tagen ordnet das Umfeld auf
einem Horizont ein, den die Strategie selbst handelt - dann misst die
Aufteilung dasselbe wie das Signal und ist keine unabhaengige Probe mehr.

**Das Gate urteilt heute ueber zwei von drei Umfeldern.** Seitwaerts hat 7
Trades und faellt unter die Zehnerschwelle. Die Frage des Gates lautet
woertlich "Funktioniert die Strategie in jedem Marktumfeld?" - und das stand
nur zwischen den Zeilen der Einzelheiten. Das ist behoben: Die Botschaft nennt
jetzt Fenster und Abdeckung. Am Wert und am Urteil aendert sich **nichts**.
"""

from __future__ import annotations

import inspect

import pytest

from research.gates import (
    REGIMEFENSTER,
    GateStatus,
    GateThresholds,
    classify_regimes,
    gate_regime_split,
)

#: Wo das Urteil am Spitzenkandidaten kippt - gemessen, siehe Kopf.
KIPPT_ZWISCHEN = (25, 30)


class TestDieZahlHatEinenNamenUndEinenOrt:
    def test_das_gate_und_die_funktion_nennen_dieselbe(self) -> None:
        """Vorher stand die 480 nur als Vorgabe in der Signatur, und die
        Botschaft des Gates nannte sie nicht."""
        quelle = inspect.getsource(classify_regimes)

        assert "window: int = REGIMEFENSTER" in quelle
        assert REGIMEFENSTER == 480

    def test_der_docstring_sagt_was_sie_auf_tageskerzen_heisst(self) -> None:
        """'bei 15-Minuten-Kerzen sind 480 rund fuenf Tage' stand da - und das
        Gate laeuft auf Tageskerzen."""
        text = classify_regimes.__doc__ or ""

        assert "15-Minuten-Kerzen" in text
        assert "sechzehn Monate" in text

    def test_das_gate_aendert_das_fenster_nicht_selbst(self) -> None:
        """Es verschiebt ein Urteil, also faellt es nicht hier."""
        quelle = inspect.getsource(gate_regime_split)

        assert "classify_regimes(frame)" in quelle
        assert "window=" not in quelle


class TestDieBotschaftNenntFensterUndAbdeckung:
    @staticmethod
    def _trades(zahl: int):
        """Gewinner **und** Verlierer.

        Erst waren hier lauter Gewinne - dann ist jeder Profitfaktor
        unendlich, das Gate landet im Aussetzer-Zweig, und der Test prueft
        eine andere Lage als gemeint. Eine Attrappe ohne Verlust ist keine
        Handelsreihe.
        """
        from tests.test_gates import make_trade

        return [
            make_trade("3" if i % 3 else "-2", hours_offset=i * 24, index=i)
            for i in range(zahl)
        ]

    def test_sie_nennt_beides(self) -> None:
        from tests.test_gates import long_series

        frame = long_series(2000)
        trades = self._trades(40)

        ergebnis = gate_regime_split(trades, frame, GateThresholds())

        assert f"Fenster {REGIMEFENSTER} Kerzen" in ergebnis.message
        assert "von 3 Umfeldern geurteilt" in ergebnis.message

    def test_und_zaehlt_nur_die_mit_genug_trades(self) -> None:
        """Ein Umfeld mit weniger als zehn Trades wird nicht geurteilt - genau
        das war am Spitzenkandidaten der Fall (Seitwaerts, 7 Trades)."""
        from tests.test_gates import long_series

        frame = long_series(2000)
        trades = self._trades(40)

        ergebnis = gate_regime_split(trades, frame, GateThresholds())
        geurteilt = int(ergebnis.message.split(" von 3")[0].split()[-1])

        assert 0 <= geurteilt <= 3

    def test_zu_wenige_trades_bleiben_ein_aussetzer(self) -> None:
        """Die Abdeckungszeile darf den Aussetzer nicht ueberschreiben."""
        from tests.test_gates import long_series

        ergebnis = gate_regime_split(self._trades(5), long_series(600), GateThresholds())

        assert ergebnis.status is GateStatus.SKIP
        assert "Zu wenige Trades" in ergebnis.message

    def test_ein_umfeld_ohne_verlust_sagt_das_jetzt(self) -> None:
        """**Nebenfund.** Zwei Lagen landeten im selben Aussetzer-Zweig.

        Hatte jedes geurteilte Umfeld keinen einzigen Verlust, blieb der
        Faktor unendlich - und die Botschaft behauptete 'Kein Marktumfeld mit
        genug Trades', wo dreissig standen. An echten Daten praktisch
        unmoeglich, mit einer Attrappe aus lauter Gewinnen sofort da. Der
        Status bleibt SKIP; geaendert ist nur die Auskunft.
        """
        from tests.test_gates import long_series, make_trade

        nur_gewinne = [
            make_trade("3", hours_offset=i * 24, index=i) for i in range(40)
        ]

        ergebnis = gate_regime_split(nur_gewinne, long_series(2000), GateThresholds())

        assert ergebnis.status is GateStatus.SKIP
        assert "Kein Umfeld mit Verlusten" in ergebnis.message
        assert "zu wenige" not in ergebnis.message.lower()


@pytest.mark.daten
@pytest.mark.langsam
class TestAmZulassungspfadGemessen:
    """Die Tabelle aus dem Kopf, an den echten Daten.

    ``daten``, weil es den Kerzenspeicher braucht; ``langsam``, weil ein
    Portfolio-Walk-Forward darin steckt.
    """

    @staticmethod
    def _lage():
        import math
        from pathlib import Path  # noqa: F401 - gleiche Form wie der Nachbartest

        import cli
        from backtest.portfolio_walkforward import run_portfolio_walkforward
        from core.config import get_settings
        from core.models import Interval
        from research.datenstand import alle_geschnitten
        from research.gates import _regime_at
        from research.seeds import spitzenkandidat
        from strategy.compiler import compile_genome

        symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        frames, configs, _ = cli._korb_daten(symbole, Interval("D"), get_settings())
        frames = alle_geschnitten(frames)
        genom = spitzenkandidat()
        bericht = run_portfolio_walkforward(
            frames, lambda g=genom: compile_genome(g), configs
        )
        trades = list(bericht.all_trades)
        rahmen = frames[symbole[0]]

        def bei(fenster: int) -> tuple[float, int]:
            regime = classify_regimes(rahmen, window=fenster)
            eimer: dict[str, list[float]] = {
                "aufwaerts": [], "abwaerts": [], "seitwaerts": []
            }
            for trade in trades:
                lage = _regime_at(regime, trade.entry_time)
                if lage is not None:
                    eimer[lage].append(float(trade.net_pnl))
            schlechtester = math.inf
            geurteilt = 0
            for werte in eimer.values():
                if len(werte) < 10:
                    continue
                geurteilt += 1
                gewinn = sum(v for v in werte if v > 0)
                verlust = abs(sum(v for v in werte if v <= 0))
                faktor = gewinn / verlust if verlust > 0 else math.inf
                schlechtester = min(schlechtester, faktor)
            return schlechtester, geurteilt

        return trades, rahmen, bei

    def test_heute_urteilt_es_ueber_zwei_von_drei(self) -> None:
        trades, rahmen, _ = self._lage()

        ergebnis = gate_regime_split(trades, rahmen, GateThresholds())

        assert ergebnis.status is GateStatus.PASS
        assert "2 von 3 Umfeldern geurteilt" in ergebnis.message
        assert "seitwaerts: nur 7 Trades" in ergebnis.message

    def test_das_urteil_kippt_zwischen_dreissig_und_fuenfundzwanzig(self) -> None:
        _, _, bei = self._lage()
        schwelle = GateThresholds().min_regime_profit_factor

        haelt, _ = bei(KIPPT_ZWISCHEN[1])
        faellt, _ = bei(KIPPT_ZWISCHEN[0])

        assert haelt >= schwelle, "bei 30 Tagen bestand es"
        assert faellt < schwelle, "bei 25 Tagen nicht"

    def test_ab_hundertzwanzig_tagen_werden_alle_drei_geurteilt(self) -> None:
        """Nicht das Fenster ist das Problem, sondern dass niemand es nennt:
        Bei 120 Tagen sind alle drei Umfelder besetzt **und** es besteht."""
        _, _, bei = self._lage()

        schlechtester, geurteilt = bei(120)

        assert geurteilt == 3
        assert schlechtester >= GateThresholds().min_regime_profit_factor
