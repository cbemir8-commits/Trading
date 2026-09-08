"""Was den Datenrand aus der Statistik haelt - und was nicht.

**Befund 241.** Befund 239 hat die angefangene Randkerze gefunden und
gemessen, dass sie nichts kostet. Die Begruendung dort lautete: *"Der Nachlauf
aus Befund 151 und der Randschnitt aus Befund 152 halten den Datenrand aus der
Statistik heraus."* Beides stimmt, aber es teilt die Arbeit gleichmaessig auf
zwei Schichten auf, und so ist es nicht.

Gemessen am Bestand:

    letztes Testfenster endet    2026-08-19
    Datenrand                    2026-08-29        Abstand 10 Tage
    letzter Trade endet          2026-08-29        Abstand  0 Tage

Der Nachlauf haelt die **Fenster** zehn Tage vom Rand weg. Die **Trades** haelt
er nicht: Zwei laufen bis genau dorthin, und ohne den Randschnitt stuenden sie
in der Statistik. Was die halbe Kerze dann kostet, ist messbar:

    Guete mit zensierten Trades    0,284810 -> 0,285295   (+0,000486)
    Guete ohne zensierte Trades    0,270779 -> 0,270779   (+0,000000)

Klein, aber nach **oben** - eine halbe Kerze schmeichelt. Tragend ist also der
Randschnitt allein.

Warum das aufgeschrieben gehoert
--------------------------------
Weil die Zusicherung aus Befund 239 sonst an der falschen Stelle haengt. Wer
den Nachlauf fuer den Schutz haelt, koennte den Randschnitt lockern und
glauben, es bleibe ein Puffer von zehn Tagen. Den gibt es fuer Trades nicht.
"""

from __future__ import annotations

import pytest

from core.models import Interval


def _spotlauf(frames_roh):
    import cli
    from backtest.portfolio_walkforward import common_range, run_portfolio_walkforward
    from core.config import get_settings
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    einstellungen = get_settings()
    symbole = list(frames_roh)
    frames = common_range(frames_roh)
    genom = cli._ohne_hebel(spitzenkandidat())
    return frames, run_portfolio_walkforward(
        frames,
        lambda: compile_genome(genom),
        cli._spotconfigs(symbole, einstellungen),
    )


def _tagesreihen():
    from core.config import get_settings
    from data.store import CandleStore

    speicher = CandleStore(get_settings().paths.data_store)
    return {
        x: speicher.read(x, Interval("D"))
        for x in ("BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP")
    }


class TestWoDieSchichtenGreifen:
    @pytest.mark.langsam
    def test_der_nachlauf_haelt_die_fenster_vom_rand_weg(self) -> None:
        roh = _tagesreihen()
        if any(f.empty for f in roh.values()):
            pytest.skip("keine Kerzen im Speicher")

        frames, bericht = _spotlauf(roh)
        rand = max(f["open_time"].iloc[-1] for f in frames.values())
        ende = max(w.window.test_end for w in bericht.windows if w.window)

        assert (rand - ende).days >= 5, (
            "Das letzte Testfenster reicht bis an den Datenrand - der Nachlauf "
            "aus Befund 151 greift nicht mehr."
        )

    @pytest.mark.langsam
    def test_die_trades_haelt_er_nicht(self) -> None:
        """**Der Kern des Befundes.** Der Puffer gilt fuer Fenster, nicht fuer
        Positionen: Eine im letzten Fenster eroeffnete Position laeuft weiter,
        bis die Daten enden."""
        from research.randschnitt import randtrades

        roh = _tagesreihen()
        if any(f.empty for f in roh.values()):
            pytest.skip("keine Kerzen im Speicher")

        frames, bericht = _spotlauf(roh)
        rand = max(f["open_time"].iloc[-1] for f in frames.values())
        zensiert = randtrades(bericht.all_trades)

        assert zensiert, "kein Trade am Datenende - dann traegt der Nachlauf doch"
        assert min((rand - t.exit_time).days for t in zensiert) == 0

    @pytest.mark.langsam
    def test_der_randschnitt_ist_die_tragende_schicht(self) -> None:
        """Mit den zensierten Trades bewegt die halbe Randkerze die Guete,
        ohne sie nicht. Das ist die ganze Aussage von Befund 241."""
        import pandas as pd

        from core.config import get_settings
        from data.resample import resample
        from data.store import CandleStore
        from research.randschnitt import ohne_zensierte
        from research.suchbudget import Kandidat

        speicher = CandleStore(get_settings().paths.data_store)
        roh = _tagesreihen()
        if any(f.empty for f in roh.values()):
            pytest.skip("keine Kerzen im Speicher")

        ganz = {}
        for x, grob in roh.items():
            fein = speicher.read(x, Interval("15"))
            if fein.empty:
                pytest.skip("keine feinen Kerzen im Speicher")
            abgeleitet = resample(fein, Interval("15"), Interval.D1)
            rand = grob["open_time"].iloc[-1]
            ersatz = abgeleitet[abgeleitet["open_time"] == rand][grob.columns]
            ganz[x] = pd.concat(
                [grob[grob["open_time"] < rand], ersatz], ignore_index=True
            )

        werte = {}
        for name, quelle in (("halb", roh), ("ganz", ganz)):
            _, b = _spotlauf(quelle)
            werte[name] = (
                Kandidat.aus_trades("x", b.all_trades).sharpe_je_trade,
                Kandidat.aus_trades("x", ohne_zensierte(b).all_trades).sharpe_je_trade,
            )

        mit_halb, ohne_halb = werte["halb"]
        mit_ganz, ohne_ganz = werte["ganz"]

        assert ohne_halb == pytest.approx(ohne_ganz, abs=1e-9), (
            "Ohne die zensierten Trades darf die Randkerze nichts aendern."
        )
        assert mit_halb != pytest.approx(mit_ganz, abs=1e-6), (
            "Mit ihnen muss sie etwas aendern - sonst ist der Befund falsch."
        )
        assert mit_ganz > mit_halb, "Die halbe Kerze schmeichelt nach unten?"


def test_der_randgrund_ist_das_einzige_kriterium() -> None:
    """``randtrades`` erkennt zensierte Trades an ihrem Ausstiegsgrund.

    Kein Zeitfenster, keine Naehe zum Rand - der Grund selbst. Das ist der
    Grund, warum die Schicht traegt: Sie haengt nicht daran, wie weit der
    Nachlauf reicht.
    """
    import inspect

    from research import randschnitt

    quelle = inspect.getsource(randschnitt.randtrades)

    assert "exit_reason" in quelle
    assert "RANDGRUND" in quelle
