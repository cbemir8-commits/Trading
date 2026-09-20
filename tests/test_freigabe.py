"""Der Not-Aus, den in einem durchgehenden Lauf niemand freigibt - Befund 313.

Die Engine begruendet ihren frischen ``RiskOfficer`` je Lauf selbst: Im
Walk-Forward startet jedes Fenster frei, *"was der Annahme entspricht, dass
der Nutzer einen ausgeloesten Not-Aus zwischen den Fenstern manuell
freigibt. Ohne diese Annahme bliebe jedes Fenster nach dem ersten Not-Aus
fuer immer stumm, und der Backtest waere in der anderen Richtung falsch."*

Zwei Gates rechnen aber keinen Walk-Forward, sondern einen **durchgehenden**
Backtest je Bein - das Plateau-Gate ueber zwoelf Nachbarn, der Kosten-Stress
ueber den Kandidaten. Ein durchgehender Lauf hat keine Fenstergrenze, also
nie eine Freigabe: genau die Lage, die der Satz oben falsch nennt.

Auf echten Tageskerzen gemessen (Perpetual, BTC + ETH):

    alle gemeinsam x1,2    durchgehend  -103,63    Walk-Forward  +233,04
    sma(period=50) x1,2    durchgehend  -103,90    Walk-Forward  +239,08

Beide sind die Nachbarn, an denen das Gate scheitert. Beide wurden
unterwegs gesperrt - das BTC-Bein vom Wochenlimit (letzter Trade
03.09.2020), das ETH-Bein vom Kill-Switch (11.05.2020 bzw. 30.06.2020) -
und haben die restlichen sechs Jahre der Reihe nicht mehr gehandelt.

**Gelockert wird hier nichts.** Wert und Urteil des Gates bleiben, wie sie
waren; geaendert ist nur, dass die Botschaft keine Form mehr behauptet, die
an so einem Punkt nicht gemessen wurde.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from research.freigabe import (
    STILLLEGEND,
    Freigabelage,
    Lauf,
    quoten_je_stellgroesse,
    sperrsatz,
    stillgelegt,
)


def lauf(
    stellgroesse: str = "alle gemeinsam",
    kennung: str = "*",
    faktor: float = 1.2,
    *,
    durchgehend: float = 1.0,
    walkforward: float = 1.0,
    gesperrt: int = 0,
    trades: int = 40,
) -> Lauf:
    return Lauf(
        stellgroesse=stellgroesse,
        kennung=kennung,
        faktor=faktor,
        durchgehend=durchgehend,
        walkforward=walkforward,
        gesperrt=gesperrt,
        trades=trades,
    )


# ---------------------------------------------------------------------------
#  Welche Sperre stilllegt - und welche nur wartet
# ---------------------------------------------------------------------------
class TestStillgelegt:
    """**Die Unterscheidung, an der alles haengt.**

    ``execution.risk`` kennt Sperren zweier Arten. Not-Aus, Wochenlimit und
    Nur-Schliessen setzen einen ``TradingState`` - den hebt nur ``resume``
    oder ``reset_kill_switch`` auf, und die ruft kein Backtest. Tageslimit
    (24 Stunden) und Termin-Blackout sind dagegen Uhren und laufen von
    selbst ab.

    Wer eine Uhr hier einsortiert, macht aus einer Pause von Stunden eine
    Stilllegung von Jahren; wer einen Zustand auslaesst, uebersieht sie.
    """

    def test_die_dauerhaften_zaehlen(self) -> None:
        assert stillgelegt({"kill_switch": 13}) == 13
        assert stillgelegt({"trading_paused": 48}) == 48
        assert stillgelegt({"close_only": 5}) == 5

    def test_die_uhren_zaehlen_nicht(self) -> None:
        assert stillgelegt({"daily_loss_limit": 9, "news_blackout": 4}) == 0

    def test_gemischt_wird_nur_das_dauerhafte_gezaehlt(self) -> None:
        vetos = {"news_blackout": 1, "trading_paused": 48, "daily_loss_limit": 9}
        assert stillgelegt(vetos) == 48

    def test_ohne_vetos_ist_null(self) -> None:
        assert stillgelegt({}) == 0

    def test_die_namen_sind_die_des_officers(self) -> None:
        """Zwei Listen derselben Namen laufen auseinander - in diesem Projekt
        schon mehrfach geschehen. Deshalb gegen die Quelle geprueft."""
        from execution.risk import VetoReason

        bekannt = {x.value for x in VetoReason}
        assert bekannt >= STILLLEGEND, sorted(STILLLEGEND - bekannt)

    def test_kein_zustand_fehlt(self) -> None:
        """**Die andere Richtung.** Jeder ``TradingState``, der Einstiege
        verhindert, muss hier stehen - sonst gilt ein stillgelegter Lauf als
        zu Ende gemessen.
        """
        from execution.risk import TradingState

        verhindernd = {
            TradingState.PAUSED: "trading_paused",
            TradingState.CLOSE_ONLY: "close_only",
            TradingState.KILLED: "kill_switch",
        }
        assert set(verhindernd.values()) == set(STILLLEGEND)
        assert TradingState.ACTIVE not in verhindernd


# ---------------------------------------------------------------------------
#  Die Lage
# ---------------------------------------------------------------------------
class TestLauf:
    def test_das_vorzeichen_entscheidet(self) -> None:
        assert lauf(durchgehend=0.01).traegt
        assert not lauf(durchgehend=0.0).traegt
        assert not lauf(durchgehend=-0.01).traegt

    def test_kippt_heisst_die_messarten_widersprechen_sich(self) -> None:
        assert lauf(durchgehend=-103.63, walkforward=233.04).kippt
        assert not lauf(durchgehend=1093.21, walkforward=659.10).kippt
        assert not lauf(durchgehend=-1.0, walkforward=-1.0).kippt

    def test_zu_ende_gemessen_heisst_keine_dauersperre(self) -> None:
        assert lauf(gesperrt=0).zu_ende_gemessen
        assert not lauf(gesperrt=1).zu_ende_gemessen


class TestQuote:
    """Gewertet wird das **Minimum** ueber die Stellgroessen, nicht der
    Durchschnitt - genau wie im Gate.

    Stuende hier ein Durchschnitt, sagte dieser Befehl etwas anderes als das
    Gate, das er erklaeren soll; und ein Durchschnitt ueber viele
    wirkungslose Regler laesst jede Nadel wie ein Plateau aussehen.
    """

    def _gemischt(self) -> tuple[Lauf, ...]:
        return (
            lauf("alle gemeinsam", "*", 0.8, durchgehend=1.0, walkforward=1.0),
            lauf("alle gemeinsam", "*", 1.2, durchgehend=-1.0, walkforward=1.0),
            lauf("rsi(period=14)", "rsi", 0.8, durchgehend=1.0, walkforward=1.0),
            lauf("rsi(period=14)", "rsi", 1.2, durchgehend=1.0, walkforward=1.0),
        )

    def test_die_schwaechste_richtung_zaehlt(self) -> None:
        lage = Freigabelage(self._gemischt())

        assert lage.quote() == 0.5
        assert lage.schwaechste() == "alle gemeinsam"

    def test_der_walkforward_wird_getrennt_gerechnet(self) -> None:
        lage = Freigabelage(self._gemischt())

        assert lage.quote(walkforward=True) == 1.0

    def test_je_stellgroesse_nicht_je_nachbar(self) -> None:
        quoten = quoten_je_stellgroesse(self._gemischt())

        assert quoten == {"*": 0.5, "rsi": 1.0}

    def test_ohne_nachbarn_keine_quote(self) -> None:
        lage = Freigabelage(())

        assert lage.quote() == 0.0
        assert lage.schwaechste() == ""


class TestUrteil:
    def test_ohne_sperren_sagt_es_das(self) -> None:
        lage = Freigabelage((lauf(gesperrt=0), lauf("rsi", "rsi", gesperrt=0)))

        assert "Kein Nachbar wurde unterwegs abgeschaltet" in lage.urteil()

    def test_mit_sperren_steht_die_zahl_da(self) -> None:
        lage = Freigabelage((lauf(gesperrt=110), lauf("rsi", "rsi", gesperrt=75)))
        text = lage.urteil()

        assert "185 Einstiege" in text
        assert "2 von 2" in text

    def test_gleiches_urteil_beider_messarten_wird_gesagt(self) -> None:
        """Die Lage am Spot-Punkt: gesperrt wurde, aber das Gate faellt so
        oder so auf dieselbe Seite."""
        lage = Freigabelage(
            (
                lauf(durchgehend=1.0, walkforward=1.0, gesperrt=62),
                lauf("rsi", "rsi", durchgehend=1.0, walkforward=1.0, gesperrt=62),
            )
        )

        assert "aendert das hier nichts" in lage.urteil()

    def test_verschiedenes_urteil_wird_dem_nutzer_vorgelegt(self) -> None:
        """Die Lage am Perpetual-Punkt - und die Stelle, an der dieses Modul
        **nicht** selbst entscheidet."""
        lage = Freigabelage(
            (
                lauf("alle gemeinsam", "*", 0.8, durchgehend=1.0, walkforward=1.0),
                lauf(
                    "alle gemeinsam", "*", 1.2,
                    durchgehend=-103.63, walkforward=233.04, gesperrt=110,
                ),
            )
        )
        text = lage.urteil()

        assert "haengt das Urteil des Gates an der Messart" in text
        assert "Geaendert wird deshalb nichts" in text
        assert "gehoert zum Nutzer" in text

    def test_die_kipper_werden_benannt(self) -> None:
        lage = Freigabelage(
            (
                lauf("sma(period=50)", "sma50", 1.2,
                     durchgehend=-103.9, walkforward=239.08, gesperrt=109),
                lauf("sma(period=50)", "sma50", 0.8, gesperrt=79),
            )
        )

        assert "sma(period=50) x1.2" in lage.urteil()

    def test_ohne_nachbarn_keine_aussage(self) -> None:
        assert Freigabelage(()).urteil() == "Keine Nachbarn - keine Aussage."


class TestTabelle:
    def test_beide_spalten_und_die_sperren_stehen_da(self) -> None:
        lage = Freigabelage(
            (lauf(durchgehend=-103.63, walkforward=233.04, gesperrt=110),)
        )
        text = lage.tabelle()

        assert "-103.63" in text
        assert "+233.04" in text
        assert "110" in text

    def test_ein_widerspruch_wird_markiert(self) -> None:
        einig = Freigabelage((lauf(durchgehend=1.0, walkforward=1.0),))
        uneinig = Freigabelage((lauf(durchgehend=-1.0, walkforward=1.0),))

        assert "verschieden" not in einig.tabelle()
        assert "verschieden" in uneinig.tabelle()


# ---------------------------------------------------------------------------
#  Was statt einer Randlage dasteht
# ---------------------------------------------------------------------------
class TestSperrsatz:
    def test_die_zahl_der_gesperrten_einstiege_steht_darin(self) -> None:
        assert "110" in sperrsatz(110)

    def test_er_behauptet_keine_form(self) -> None:
        """**Der Kern.** Eine Randlage liest aus zwei Punkten die Form eines
        Gebiets. Ein Punkt, an dem ab 2020 nicht mehr gehandelt wurde, ist
        keine Messung der Form.
        """
        text = sperrsatz(110)

        assert "Nadelspitze" not in text
        assert "Kante" not in text
        assert "sagt diese Messung nicht" in text

    def test_er_nennt_den_befehl_zum_nachrechnen(self) -> None:
        """Die Hausregel des Registers: Wer eine Zahl nennt, nennt den Weg
        dorthin."""
        assert "cli freigabe" in sperrsatz(110)


# ---------------------------------------------------------------------------
#  Die Verdrahtung - dass das Gate es wirklich benutzt
# ---------------------------------------------------------------------------
class TestDasGateBenutztEs:
    def test_das_plateau_gate_zaehlt_die_sperren(self) -> None:
        from research import gates

        quelle = inspect.getsource(gates.gate_parameter_plateau)

        assert "stillgelegt(" in quelle
        assert "sperrsatz(" in quelle

    def test_die_randlage_bleibt_fuer_zu_ende_gemessene_laeufe(self) -> None:
        """**Die Gegenrichtung.** ``sperrsatz`` ersetzt die Randlage nur
        dort, wo gesperrt wurde - sonst waere die Unterscheidung aus Befund
        163 stillschweigend verschwunden.
        """
        from research import gates

        quelle = inspect.getsource(gates.gate_parameter_plateau)

        assert "_RANDSATZ[randlage(" in quelle

    def test_nur_die_gefallenen_nachbarn_zaehlen(self) -> None:
        """Ein tragender Nachbar, der unterwegs gesperrt wurde, ist kein
        Grund, die Form nicht zu nennen - er ist ja nicht durchgefallen."""
        from research import gates

        quelle = inspect.getsource(gates.gate_parameter_plateau)

        assert "if not ok" in quelle

    def test_die_summe_bleibt_in_decimal(self) -> None:
        """**Das Vorzeichen ist alles, was dieses Gate benutzt.** Ueber
        ``float`` gerechnet koennte eine Summe, die sich genau aufhebt, knapp
        neben der Null landen.
        """
        from research import gates

        baum = ast.parse(inspect.getsource(gates.gate_parameter_plateau))
        zuweisungen = [
            ast.unparse(n.value)
            for n in ast.walk(baum)
            if isinstance(n, ast.Assign)
            and any(
                isinstance(z, ast.Name) and z.id == "gewinn" for z in n.targets
            )
        ]

        assert zuweisungen == ["Decimal(0)"], zuweisungen


@pytest.fixture(scope="module")
def quelle() -> str:
    """Der Quelltext von ``cli freigabe`` - ohne den Befehl auszufuehren."""
    baum = ast.parse(Path("cli.py").read_text())
    treffer = [
        ast.unparse(n)
        for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef) and n.name == "freigabe"
    ]
    assert treffer, "'cli freigabe' gibt es nicht"
    return treffer[0]


class TestDerBefehlGibtEsUndErErklaertSich:
    def test_er_misst_beide_messarten(self, quelle: str) -> None:
        assert "run_portfolio_walkforward" in quelle
        assert "Backtester(cfg).run" in quelle

    def test_er_sagt_dass_er_nichts_aendert(self, quelle: str) -> None:
        """Ein Befehl, der ein Gate erklaert, muss sagen, dass er es nicht
        verstellt - sonst liest ihn irgendwann jemand als Angebot."""
        assert "Aendert nichts" in quelle

    def test_er_kostet_keinen_versuch(self, quelle: str) -> None:
        """Er variiert die Parameter eines vorhandenen Kandidaten - das tut
        das Gate ohnehin. Wuerde er zaehlen, hoebe das Erklaeren eines Gates
        die Latte eines anderen.

        Die Begruendung steht in ``tests/test_zusicherungen.py`` unter
        ``BEGRUENDET``; der Test darunter prueft ihre Voraussetzung.
        """
        assert "Kostet keinen Versuch" in quelle
        assert "save_trials" not in quelle

    def test_aus_ihm_kann_kein_kandidat_hervorgehen(self, quelle: str) -> None:
        """**Die Voraussetzung der Zusicherung, geprueft statt behauptet.**

        Dass er keinen Versuch kostet, steht und faellt damit, dass er
        nichts auswaehlt. Wer hier eine Bestenliste einbaut - sortieren,
        das Maximum nehmen, den besten Nachbarn nennen -, macht aus einer
        Erklaerung eine Suche, und dann muss sie zaehlen.
        """
        for auswahl in ("sorted(", "max(", "min(", ".sort("):
            assert auswahl not in quelle, auswahl
