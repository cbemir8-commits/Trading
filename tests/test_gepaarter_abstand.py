"""Was ein neuer Einfall schlagen muss - 1,25 und nicht 1,03. Befund 486.

``cli suchbudget`` sagt dem Nutzer, wie weit sein Bestand von der Grenzlinie
weg ist. Das ist die Zahl, gegen die seine **27 verbleibenden Versuche**
antreten, und sie stand zu niedrig da.

Die Schlagzahl war:

    Unter Spot-Bedingungen (0.2853 statt 0.2682, kein Funding) ist es
    Faktor mindestens 1.03

Gerechnet war das so::

    spotfaktor = nah.noetig / self.spotguete

``nah.noetig`` ist die Latte bei der **rohen** Trade-Zahl des
Bestenlisten-Eintrags (158 Trades, 0,2935). ``spotguete`` ist die Guete
desselben Bestands unter Kassa-Bedingungen, aus einem **anderen** Lauf
(0,2853). Zaehler und Nenner kommen damit aus zwei Messungen - genau der
Fehler aus Befund 428 und 242, nur diesmal in der folgenreichsten Zahl des
Befehls.

Gepaart gerechnet, alle vier Eingaben aus derselben Messung
-----------------------------------------------------------
    Latte bei 158 rohen Trades        0,2935
    Latte bei 115 effektiven          0,3374      (SPOTPUNKT.effektiv)

    Guete live (_spotguete)           0,2853  ->  roh 1,03   effektiv 1,18
    Guete gepflegt (SPOTPUNKT)        0,2708  ->  roh 1,08   effektiv 1,25

Die saubere Paarung ist die untere Zeile **durchgehend**: Stichprobe, Guete,
Schiefe und Woelbung aus ``research.referenz.SPOTPUNKT``. **Faktor 1,25.**

Und 1,03 liest sich anders als 1,25. Das ist dieselbe Lehre wie Befund 379 -
*"ohne die Groessenordnung liest sich das wie 'knapp verpasst'"* -, nur hier
an der Zahl, die bestimmt, worauf der Nutzer seine letzten Versuche richtet.

Der Satz daneben war auch falsch
--------------------------------
Dort stand: *"Die effektive Stichprobe dieses Kandidaten ist nicht
gemessen."* Fuer den Bestenlisten-Eintrag stimmt das. Es las sich aber wie
"das Projekt kennt sie nicht" - und ``research.referenz.SPOTPUNKT`` fuehrt
sie seit langem (156 Trades, 115 effektiv), **und derselbe Befehl benutzt sie
zehn Zeilen weiter** fuer die Tabelle "Was Weitersuchen an der Linie
verschiebt". Die Zahl lag in der Hand und ging nicht in die Schlagzahl ein.

Was hier **nicht** passiert
---------------------------
Keine Schwelle, kein Gate und keine Latte bewegt sich. Der Fund zeigt in die
**strenge** Richtung: Der Abstand ist groesser als gemeldet. Wer daraus eine
Lockerung machen wollte, muesste die Latte senken - und genau das ist der
Satz, der in diesem Projekt nicht verhandelbar ist.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from research.referenz import SPOTPUNKT
from research.suchbudget import Budget, Kandidat


@dataclass(frozen=True, slots=True)
class Punkt:
    """Ein gebauter Betriebspunkt - das Protokoll verlangt genau diese fuenf."""

    name: str
    effektiv: int
    guete: float
    schiefe: float
    woelbung: float


class TestDieGepaarteRechnung:
    def test_sie_nimmt_alle_vier_aus_einer_messung(self) -> None:
        budget = Budget(versuche=203)

        latte, faktor = budget.am_betriebspunkt(
            effektiv=SPOTPUNKT.effektiv,
            guete=SPOTPUNKT.guete,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )

        assert latte == pytest.approx(0.3374, abs=5e-4)
        assert faktor == pytest.approx(1.25, abs=5e-3)

    def test_und_sie_liegt_ueber_der_rohen_rechnung(self) -> None:
        """**Der Kern des Befundes.** Die rohe Trade-Zahl ergibt eine
        kleinere Latte, und geteilt durch eine fremde Guete einen Faktor, der
        wie "knapp daneben" aussieht."""
        budget = Budget(versuche=203)
        roh = budget.noetig_bei(
            158, schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung
        )
        _latte, gepaart = budget.am_betriebspunkt(
            effektiv=SPOTPUNKT.effektiv,
            guete=SPOTPUNKT.guete,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )

        assert roh / 0.2853 == pytest.approx(1.03, abs=5e-3)
        assert gepaart > roh / 0.2853
        assert gepaart - roh / 0.2853 > 0.15

    def test_ohne_guete_gibt_es_keine_zahl(self) -> None:
        """``None`` und nicht 0: Eine Guete von null ist keine Messung."""
        budget = Budget(versuche=203)

        assert (
            budget.am_betriebspunkt(
                effektiv=115, guete=0.0, schiefe=3.0, woelbung=15.0
            )
            is None
        )

    def test_eine_kleinere_stichprobe_hebt_die_latte(self) -> None:
        """Die Gegenprobe zur Richtung: Weniger unabhaengige Beobachtungen
        heissen mehr noetiger Sharpe (Befund 139)."""
        budget = Budget(versuche=203)
        gross = budget.am_betriebspunkt(
            effektiv=158, guete=0.2708, schiefe=3.46, woelbung=15.9
        )
        klein = budget.am_betriebspunkt(
            effektiv=115, guete=0.2708, schiefe=3.46, woelbung=15.9
        )

        assert klein[0] > gross[0]
        assert klein[1] > gross[1]

    def test_mehr_versuche_heben_sie_auch(self) -> None:
        budget = Budget(versuche=203)
        jetzt = budget.am_betriebspunkt(
            effektiv=115, guete=0.2708, schiefe=3.46, woelbung=15.9
        )
        spaeter = budget.am_betriebspunkt(
            effektiv=115, guete=0.2708, schiefe=3.46, woelbung=15.9, versuche=403
        )

        assert spaeter[0] > jetzt[0]


class TestDasUrteilNenntSie:
    def _budget(self, *, punkt: Punkt | None) -> Budget:
        kandidat = Kandidat(
            name="Bestand",
            trades=158,
            sharpe_je_trade=0.2682,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )
        return Budget(
            versuche=203,
            kandidaten=[kandidat],
            spotguete=0.2853,
            betriebspunkt=punkt,
        )

    def _punkt(self) -> Punkt:
        return Punkt(
            name="Spot wie gebaut",
            effektiv=SPOTPUNKT.effektiv,
            guete=SPOTPUNKT.guete,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )

    def test_mit_punkt_steht_die_gepaarte_zahl_da(self) -> None:
        text = self._budget(punkt=self._punkt()).urteil()

        assert "1.25" in text
        assert "Spot wie gebaut" in text
        assert "aus derselben" in text

    def test_ohne_punkt_bleibt_es_wie_zuvor(self) -> None:
        """``None`` heisst "nicht uebergeben" - dann wird nichts erfunden."""
        text = self._budget(punkt=None).urteil()

        assert "1.25" not in text
        assert "aus derselben" not in text

    def test_der_rohe_faktor_wird_als_untergrenze_benannt(self) -> None:
        """Er darf stehen bleiben - er ist nicht falsch, nur eine
        Untergrenze. Was fehlte, war der Zusatz."""
        text = self._budget(punkt=self._punkt()).urteil()

        assert "1.03" in text
        assert "rohe Trade-Zahl" in text
        assert "Untergrenzen" in text

    def test_der_alte_satz_behauptet_es_nicht_mehr_pauschal(self) -> None:
        """Er sagte "die effektive Stichprobe dieses Kandidaten ist nicht
        gemessen" - und klang damit, als kenne das Projekt sie nicht."""
        text = self._budget(punkt=self._punkt()).urteil()

        assert "dieses Bestenlisten-Eintrags" in text
        assert "486" in text


class TestDerBefehlUebergibtIhn:
    def test_suchbudget_nennt_den_kassa_punkt(self) -> None:
        """Die Zahl lag zehn Zeilen weiter schon in der Hand - das war der
        Grund, warum dieser Befund ueberhaupt einer ist."""
        import ast
        from pathlib import Path

        wurzel = Path(__file__).resolve().parents[1]
        baum = ast.parse((wurzel / "cli.py").read_text(encoding="utf-8"))
        quelle = next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "suchbudget"
        )

        assert "betriebspunkt=SPOTPUNKT" in quelle
        assert "SPOTPUNKT.effektiv" in quelle

    def test_und_importiert_ihn_nur_einmal(self) -> None:
        """Vorher stand der Import mitten in der Funktion, fuer die Tabelle
        allein. Zwei Importe derselben Sache sind zwei Gelegenheiten,
        verschiedene Punkte zu nehmen (Befund 234)."""
        import ast
        from pathlib import Path

        wurzel = Path(__file__).resolve().parents[1]
        baum = ast.parse((wurzel / "cli.py").read_text(encoding="utf-8"))
        fn = next(
            n
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "suchbudget"
        )
        importe = [
            k
            for k in ast.walk(fn)
            if isinstance(k, ast.ImportFrom) and k.module == "research.referenz"
        ]

        assert len(importe) == 1, [ast.unparse(i) for i in importe]


class TestAmGateAendertSichNichts:
    """Die Zusicherung, die aus einem Fund keine Lockerung werden laesst."""

    def test_die_latte_selbst_bleibt_unberuehrt(self) -> None:
        """``am_betriebspunkt`` rechnet mit ``noetig_bei`` und sonst nichts -
        es gibt keine zweite Formel und keinen Abschlag."""
        budget = Budget(versuche=203)
        ueber_latte = budget.noetig_bei(115, schiefe=3.46, woelbung=15.9)
        ueber_punkt = budget.am_betriebspunkt(
            effektiv=115, guete=0.2708, schiefe=3.46, woelbung=15.9
        )

        assert ueber_punkt[0] == ueber_latte

    def test_der_fund_zeigt_nach_oben(self) -> None:
        """Gemeldet war 1,03, gemessen sind es 1,25 - der Abstand ist
        **groesser** als gedacht. Ein Fund, der eine Huerde senkt, waere in
        diesem Projekt erklaerungsbeduerftig; dieser hebt sie nicht einmal,
        er nennt sie nur richtig."""
        budget = Budget(versuche=203)
        _l, gepaart = budget.am_betriebspunkt(
            effektiv=SPOTPUNKT.effektiv,
            guete=SPOTPUNKT.guete,
            schiefe=SPOTPUNKT.schiefe,
            woelbung=SPOTPUNKT.woelbung,
        )

        assert gepaart > 1.0
        assert gepaart > 1.03
