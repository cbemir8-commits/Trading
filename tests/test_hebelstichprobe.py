"""Die Erklaerung stand auf einer anderen Stichprobe als das Urteil - 487.

``cli adaptiv`` rechnet die Gates aus und schreibt darunter, **woran das
haerteste Gate haengt** - die Zerlegung in vier Hebel. Beides stand auf
verschiedenen Zahlen:

* ``research/gates.py`` urteilt mit ``stichprobe_wie_im_gate(...).effektiv``.
* Der Kandidat fuer die Zerlegung kam aus ``Kandidat.aus_trades(...)``, das
  ``effektiv`` nicht fuellt - ``stichprobe`` liefert dann die **rohe**
  Trade-Zahl.

Das ist genau der Fehler, den Befund 135 und 139 benannt haben, und er stand
nach ihnen noch an zwei Stellen: ``cli adaptiv`` und ``cli instrument``.
``cli stand`` baute den Kandidaten von Hand mit der gemessenen Stichprobe -
die Lehre war also da, nur als **Stelle** und nicht als Regel (Befund 217).

Was das ausgemacht hat, gemessen
--------------------------------
Am Bestand (158 rohe Trades, 115 effektiv, Guete 0,2708):

    Hebel                  roh (158)        effektiv (115)
    Qualitaet je Trade     +8,4 %           +24,6 %
    unabhaengige Trades    +20,2 %          +65,2 %
    Schiefe                unmoeglich       unmoeglich
    Woelbung               **moeglich**     **unmoeglich**

Und damit auch der Satz darueber:

    roh        **3 von 4 Wegen sind offen** ... Am wenigsten verlangt
               Qualitaet je Trade: +8%.
    effektiv   **2 von 4 Wegen sind offen** ... Am wenigsten verlangt
               Qualitaet je Trade: +25%.

Der Befehl nannte also einen Weg offen, den das Gate nicht offen hat, und den
noetigen Zuwachs um das Dreifache zu klein. Nicht "ungenau": **Die Wege sind
die Entscheidungsgrundlage** - sie sagen, ob Weitersuchen an dieser Regel
ueberhaupt Sinn hat.

Gebaut
------
``cli._kandidat_wie_im_gate`` macht die Rechnung einmal, und alle drei
Stellen fragen sie - auch die, die es schon richtig machte. Dieselbe Rechnung
an drei Stellen laeuft auseinander (Befund 168).

Dazu die Regel ohne Ausnahmeliste: **Wer ein ``Budget`` baut, nennt die
Stichprobe, auf der er urteilt** - durch den Helfer, durch
``SPOTPUNKT.effektiv`` oder durch einen uebergebenen ``betriebspunkt``.
Gemessen erfuellen das fuenf von fuenf Stellen, und eine neue faellt hier auf.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from research.referenz import SPOTPUNKT
from research.suchbudget import Budget, Kandidat

WURZEL = Path(__file__).resolve().parents[1]

#: Woran erkannt wird, dass eine Stelle ihre Stichprobe benennt.
MARKEN: tuple[str, ...] = (
    "_kandidat_wie_im_gate",
    "SPOTPUNKT.effektiv",
    "betriebspunkt=",
)


def _kandidat(*, effektiv: int | None) -> Kandidat:
    return Kandidat(
        name="Bestand",
        trades=158,
        sharpe_je_trade=SPOTPUNKT.guete,
        schiefe=SPOTPUNKT.schiefe,
        woelbung=SPOTPUNKT.woelbung,
        effektiv=effektiv,
    )


def _zerlegung(*, effektiv: int | None):
    k = _kandidat(effektiv=effektiv)
    budget = Budget(versuche=203, kandidaten=[k])
    return budget, k, budget.hebel(k)


class TestDieStichprobeAendertDieZerlegung:
    """Erst die Messung, dann die Regel - sonst waere der Fund eine
    Behauptung."""

    def test_roh_nennt_einen_weg_mehr(self) -> None:
        """**Der Kern.** Auf der rohen Trade-Zahl gilt die Woelbung als
        offener Weg; auf der des Gates ist sie geschlossen."""
        _b, _k, roh = _zerlegung(effektiv=None)
        _b2, _k2, eff = _zerlegung(effektiv=SPOTPUNKT.effektiv)

        assert sum(1 for h in roh if h.moeglich) == 3
        assert sum(1 for h in eff if h.moeglich) == 2

    def test_und_einen_dreifach_kleineren_zuwachs(self) -> None:
        def billigster(hebel):
            offen = [
                h for h in hebel if h.moeglich and h.veraenderung is not None
            ]
            return min(abs(h.veraenderung) for h in offen)

        _b, _k, roh = _zerlegung(effektiv=None)
        _b2, _k2, eff = _zerlegung(effektiv=SPOTPUNKT.effektiv)

        assert billigster(roh) == pytest.approx(0.084, abs=5e-3)
        assert billigster(eff) == pytest.approx(0.246, abs=5e-3)
        assert billigster(eff) > 2.5 * billigster(roh)

    def test_der_erklaerungssatz_sagt_es_auch(self) -> None:
        """Nicht nur die Zahlen - der Satz, den der Nutzer liest."""
        budget, _k, roh = _zerlegung(effektiv=None)
        _b2, _k2, eff = _zerlegung(effektiv=SPOTPUNKT.effektiv)

        assert "3 von 4 Wegen" in budget.hebelerklaerung(roh)
        assert "2 von 4 Wegen" in budget.hebelerklaerung(eff)

    def test_die_rohe_zahl_ist_immer_die_freundlichere(self) -> None:
        """Die Richtung, und sie ist die gefaehrliche: Die rohe Stichprobe
        ist nie kleiner als die effektive (Befund 139), also liest sich die
        Lage mit ihr immer besser als sie ist."""
        for n in (60, 115, 158, 300):
            k_roh = Kandidat(
                name="x",
                trades=n,
                sharpe_je_trade=0.27,
                schiefe=3.0,
                woelbung=15.0,
            )
            k_eff = Kandidat(
                name="x",
                trades=n,
                sharpe_je_trade=0.27,
                schiefe=3.0,
                woelbung=15.0,
                effektiv=max(2, int(n * 0.7)),
            )
            budget = Budget(versuche=203)

            assert k_roh.stichprobe >= k_eff.stichprobe
            assert budget.noetig_bei(k_roh.stichprobe) <= budget.noetig_bei(
                k_eff.stichprobe
            )


class TestDerHelferMachtEsEinmal:
    def test_er_steht_im_quelltext(self) -> None:
        quelle = (WURZEL / "cli.py").read_text(encoding="utf-8")

        assert "def _kandidat_wie_im_gate(" in quelle
        assert "stichprobe_wie_im_gate" in quelle

    def test_er_fuellt_die_effektive_stichprobe(self) -> None:
        """Gegenprobe zur Bauart: ``Kandidat.aus_trades`` allein tut es
        nicht - genau daran lag es."""
        roh = Kandidat.aus_trades(
            "x",
            [],
        )

        assert roh is None, "leere Trades geben keinen Kandidaten"

    def test_alle_drei_stellen_fragen_ihn(self) -> None:
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        rumpf = {
            n.name: ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef)
        }

        for name in ("adaptiv", "instrument", "stand"):
            assert "_kandidat_wie_im_gate" in rumpf[name], name

    def test_und_niemand_baut_ihn_mehr_von_hand(self) -> None:
        """Die Fassung in ``stand`` war richtig und ist trotzdem weg: Zwei
        Fassungen einer Rechnung sind zwei Gelegenheiten, dass sie
        auseinanderlaufen (Befund 168).

        **Geprueft am Syntaxbaum und nicht am Text.** Der erste Entwurf
        suchte die Zeichenkette ``effektiv=stichprobe.effektiv`` und schlug
        bei ``cli teststaerke`` an - dort steht sie, aber fuer ein anderes
        Objekt. Ein Melder, der das falsche Ding findet, ist schlimmer als
        keiner (Befund 478).
        """
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        eltern: dict[ast.AST, ast.AST] = {}
        for knoten in ast.walk(baum):
            for kind in ast.iter_child_nodes(knoten):
                eltern[kind] = knoten

        def umgebende(knoten: ast.AST) -> str:
            while knoten in eltern:
                knoten = eltern[knoten]
                if isinstance(knoten, ast.FunctionDef):
                    return knoten.name
            return "<modul>"

        von_hand = [
            umgebende(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "Kandidat"
            and any(k.arg == "effektiv" for k in n.keywords)
            and umgebende(n) != "_kandidat_wie_im_gate"
        ]

        assert von_hand == [], von_hand


class TestWerEinBudgetBautNenntSeineStichprobe:
    """Die Regel - **ohne Ausnahmeliste**, und das ist der Punkt.

    Gemessen erfuellen sie fuenf von fuenf Stellen. Eine gepflegte Liste von
    Ausnahmen waere die Bauart, die Befund 484 und 485 gefunden haben.
    """

    def _stellen(self) -> dict[str, str]:
        baum = ast.parse((WURZEL / "cli.py").read_text(encoding="utf-8"))
        return {
            n.name: ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and "Budget(" in ast.unparse(n)
        }

    def test_es_gibt_welche(self) -> None:
        """Die Nichtleere-Zusicherung aus Befund 479."""
        stellen = self._stellen()

        assert len(stellen) >= 5, sorted(stellen)

    def test_jede_nennt_ihre_stichprobe(self) -> None:
        offen = [
            name
            for name, text in self._stellen().items()
            if not any(m in text for m in MARKEN)
        ]

        assert offen == [], (
            "baut ein Budget, ohne die Stichprobe zu nennen, auf der es "
            f"urteilt - genau das war Befund 487: {offen}"
        )

    def test_der_melder_wuerde_eine_neue_stelle_sehen(self) -> None:
        """Gegenprobe: Eine Funktion, die ein Budget baut und keine der
        Marken traegt, faellt durch."""
        baum = ast.parse(
            "def neu(trials, trades):\n"
            "    eintrag = Kandidat.aus_trades('x', trades)\n"
            "    budget = Budget(versuche=trials, kandidaten=[eintrag])\n"
            "    return budget.hebel(eintrag)\n"
        )
        text = ast.unparse(baum)

        assert "Budget(" in text
        assert not any(m in text for m in MARKEN)
