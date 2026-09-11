"""Zwei Gates koennen sich einen Sprossenabstand teilen.

**Befund 250.** Die Funding-Leiter aus Befund 100 hat sechs Sprossen, und ihre
Auskunft lautete:

    *"Zwischen 5,5 % und 11 % kippen zwei Gates (Schlechtestes Jahr,
    Parameter-Plateau)."*

Der Satz ist wahr. Er verbirgt trotzdem das Wesentliche, denn die beiden kippen
nicht zusammen - fein nachgemessen liegen gut drei Prozentpunkte dazwischen:

    Schlechtestes Jahr     zwischen 5,48 % und 6,57 %
    Parameter-Plateau      zwischen 8,80 % und 9,86 %

Wer das Paar der Leiter als Spielraum liest, haelt ihn fuer 11 % - er ist halb
so gross. Der Abstand zweier Sprossen ist eine Eigenschaft der Leiter und keine
des Kandidaten; hier war er zur Aussage geworden.

Was hier gehalten wird
----------------------
Nicht die gemessenen Zahlen - die haengen am Kandidaten und duerfen sich mit
ihm aendern. Sondern die Bauart der Suche: dass sie **je Gate** halbiert und
nicht je Sprossenzahl, dass sie ihre eigene Voraussetzung nachprueft, und dass
sie jeden Satz hoechstens einmal misst (jeder ist ein voller Walk-Forward).

Die Messungen kommen aus einer gestellten Welt, nicht aus dem Backtest: Was
hier geprueft wird, ist die Suche, nicht der Kandidat.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

from research.finanzierung import (
    BASISSATZ,
    FEINHEIT,
    PERIODEN_JE_JAHR,
    Finanzierung,
    Kippbild,
    Kipppunkt,
    Stufe,
    jahr_pct,
    kipppunkte_suchen,
)

#: Die beiden gemessenen Kipppunkte, als Satz je Achtstundenperiode. Sie
#: stehen hier als Schauplatz fuer die gestellte Welt - nicht als Zusicherung
#: ueber den Kandidaten.
SCHLECHTESTES_JAHR = 0.000055
PARAMETER_PLATEAU = 0.000088


def _welt(
    kippt_bei: dict[str, float], *, immer_offen: tuple[str, ...] = ()
) -> Callable[[float], list[str]]:
    """Eine Welt, in der jedes Gate genau einmal wechselt."""

    def messe(satz: float) -> list[str]:
        gefallen = [g for g, grenze in kippt_bei.items() if satz > grenze]
        return sorted([*gefallen, *immer_offen])

    return messe


def _zaehlend(messe: Callable[[float], list[str]]) -> tuple[Callable, list[float]]:
    """Dieselbe Welt, aber sie schreibt mit, wonach gefragt wurde."""
    gefragt: list[float] = []

    def gezaehlt(satz: float) -> list[str]:
        gefragt.append(satz)
        return messe(satz)

    return gezaehlt, gefragt


class TestDerFundDerDazuGefuehrtHat:
    """Die Leiter meldet ein Paar, die Suche zwei Punkte - am selben Fall."""

    LEITER = (0.0, 0.00005, 0.0001, 0.0002)

    def _leiter(self) -> Finanzierung:
        messe = _welt(
            {
                "Schlechtestes Jahr": SCHLECHTESTES_JAHR,
                "Parameter-Plateau": PARAMETER_PLATEAU,
            },
            immer_offen=("Messlatte", "Deflated Sharpe"),
        )
        return Finanzierung(
            stufen=[
                Stufe(
                    satz=satz,
                    cagr=0.0,
                    rueckgang=0.0,
                    bestanden=11 - len(messe(satz)),
                    gesamt=11,
                    gescheitert=tuple(messe(satz)),
                )
                for satz in self.LEITER
            ]
        )

    def test_die_leiter_meldet_ein_einziges_paar(self) -> None:
        """Beide Gates fallen im selben Sprossenabstand - die Leiter kann sie
        nicht auseinanderhalten und behauptet das auch nicht."""
        paare = self._leiter().kipppunkte

        assert len(paare) == 1
        links, rechts = paare[0]
        assert (links.satz, rechts.satz) == (0.00005, 0.0001)
        assert rechts.bestanden == links.bestanden - 2

    def test_die_suche_findet_beide_getrennt(self) -> None:
        bild = kipppunkte_suchen(
            _welt(
                {
                    "Schlechtestes Jahr": SCHLECHTESTES_JAHR,
                    "Parameter-Plateau": PARAMETER_PLATEAU,
                },
                immer_offen=("Messlatte", "Deflated Sharpe"),
            )
        )

        assert [p.gate for p in bild.geordnet] == [
            "Schlechtestes Jahr",
            "Parameter-Plateau",
        ]

    def test_der_spielraum_ist_der_erste_punkt_und_nicht_die_vorgabe(self) -> None:
        """Der Kern des Befunds: Wer das Leiterpaar als Spielraum liest, liegt
        um den ganzen Abstand zwischen den beiden Punkten daneben."""
        bild = kipppunkte_suchen(
            _welt(
                {
                    "Schlechtestes Jahr": SCHLECHTESTES_JAHR,
                    "Parameter-Plateau": PARAMETER_PLATEAU,
                }
            )
        )

        assert bild.spielraum == pytest.approx(SCHLECHTESTES_JAHR, abs=FEINHEIT)
        assert bild.anteil_der_vorgabe < 0.6

    def test_das_urteil_sagt_dass_sie_nicht_zusammen_kippen(self) -> None:
        text = kipppunkte_suchen(
            _welt(
                {
                    "Schlechtestes Jahr": SCHLECHTESTES_JAHR,
                    "Parameter-Plateau": PARAMETER_PLATEAU,
                }
            )
        ).urteil()

        assert "nicht zusammen" in text
        assert "Schlechtestes Jahr" in text


class TestDieSucheTrifft:
    @pytest.mark.parametrize(
        "wahr", [0.000001, 0.00002, 0.000055, 0.00009, 0.000099]
    )
    def test_der_punkt_liegt_im_gemeldeten_paar(self, wahr: float) -> None:
        punkt = kipppunkte_suchen(_welt({"G": wahr})).geordnet[0]

        assert punkt.haelt_bis <= wahr < punkt.faellt_ab

    def test_das_paar_ist_hoechstens_so_breit_wie_die_toleranz(self) -> None:
        punkt = kipppunkte_suchen(_welt({"G": 0.000055})).geordnet[0]

        assert punkt.breite <= FEINHEIT

    def test_feiner_suchen_engt_weiter_ein(self) -> None:
        grob = kipppunkte_suchen(_welt({"G": 0.000055}), toleranz=1e-5)
        fein = kipppunkte_suchen(_welt({"G": 0.000055}), toleranz=1e-7)

        assert fein.geordnet[0].breite < grob.geordnet[0].breite
        assert fein.messungen > grob.messungen


class TestJederSatzWirdHoechstensEinmalGemessen:
    """Jeder Aufruf ist ein voller Walk-Forward - der Bestand wird geteilt."""

    def test_kein_satz_zweimal(self) -> None:
        messe, gefragt = _zaehlend(
            _welt({"A": 0.00002, "B": 0.00008, "C": 0.00005})
        )
        kipppunkte_suchen(messe)

        assert len(gefragt) == len(set(gefragt))

    def test_drei_gates_kosten_weniger_als_drei_einzelsuchen(self) -> None:
        welt = {"A": 0.00002, "B": 0.00008, "C": 0.00005}
        gemeinsam, zusammen = _zaehlend(_welt(welt))
        kipppunkte_suchen(gemeinsam)

        einzeln = 0
        for gate, grenze in welt.items():
            messe, gefragt = _zaehlend(_welt({gate: grenze}))
            kipppunkte_suchen(messe)
            einzeln += len(gefragt)

        assert len(zusammen) < einzeln

    def test_die_zahl_der_messungen_steht_im_bild(self) -> None:
        messe, gefragt = _zaehlend(_welt({"A": 0.00002}))
        bild = kipppunkte_suchen(messe)

        assert bild.messungen == len(gefragt)


class TestWasNichtKippt:
    def test_ein_gate_das_ueberall_faellt_steht_als_immer_offen(self) -> None:
        bild = kipppunkte_suchen(
            _welt({"A": 0.00002}, immer_offen=("Messlatte",))
        )

        assert bild.immer_offen == ("Messlatte",)
        assert "Messlatte" not in [p.gate for p in bild.punkte]

    def test_das_urteil_nennt_sie(self) -> None:
        text = kipppunkte_suchen(
            _welt({"A": 0.00002}, immer_offen=("Messlatte", "Deflated Sharpe"))
        ).urteil()

        assert "haengt nicht alles" in text
        assert "Messlatte" in text and "Deflated Sharpe" in text

    def test_ein_gate_das_ueberall_haelt_taucht_nirgends_auf(self) -> None:
        bild = kipppunkte_suchen(_welt({"A": 0.00002}))

        assert bild.immer_offen == ()
        assert bild.verkehrt == ()
        assert [p.gate for p in bild.punkte] == ["A"]

    def test_ohne_jeden_kipppunkt_sagt_das_urteil_genau_das(self) -> None:
        bild = kipppunkte_suchen(lambda _satz: ())

        assert bild.punkte == ()
        assert bild.erster is None
        assert bild.spielraum == BASISSATZ
        assert "Kein Gate kippt" in bild.urteil()
        assert "Kein Gate kippt" in bild.tabelle()


class TestDieSucheHaeltIhreEigeneVoraussetzungNach:
    """Halbieren setzt einen einzigen Wechsel voraus. Das ist eine Annahme
    ueber den Kandidaten und keine Eigenschaft der Methode."""

    def test_verkehrte_richtung_wird_gemeldet_und_nicht_gesucht(self) -> None:
        def messe(satz: float) -> list[str]:
            return ["Rueckwaerts"] if satz < 0.00005 else []

        bild = kipppunkte_suchen(messe)

        assert bild.verkehrt == ("Rueckwaerts",)
        assert bild.punkte == ()
        assert "andere Richtung" in bild.urteil()

    @staticmethod
    def _zackig(satz: float) -> bool:
        """Faellt, erholt sich, faellt wieder - zwei Wechsel statt einem."""
        return 0.00002 < satz < 0.00004 or satz > 0.00008

    def test_allein_sieht_die_pruefung_das_zweite_band_nicht(self) -> None:
        """Die Grenze der Pruefung, als Test und nicht als Fussnote.

        Die Halbierung misst nur innerhalb ihres schrumpfenden Paares. Sie
        findet den oberen Wechsel, betritt das untere Band nie - und keine
        ihrer Messungen widerspricht danach einem einzigen Wechsel. ``True``
        heisst hier "kein Widerspruch gefunden", nicht "es gibt keinen".
        """
        bild = kipppunkte_suchen(
            lambda satz: ["Zackig"] if self._zackig(satz) else []
        )

        punkt = bild.geordnet[0]
        assert punkt.einheitlich
        assert punkt.haelt_bis > 0.00004

    def test_ein_zweites_gate_bringt_das_band_ans_licht(self) -> None:
        """Und hier bekommt sie Zaehne: Die Halbierung eines **anderen** Gates
        streut Messungen ueber den ganzen Bereich, und die werden mitgeprueft.
        'B' kippt bei 0,000025 und misst dabei mitten in das Band hinein."""

        def messe(satz: float) -> list[str]:
            offen = ["Zackig"] if self._zackig(satz) else []
            if satz > 0.000025:
                offen.append("B")
            return sorted(offen)

        bild = kipppunkte_suchen(messe)
        zackig = next(p for p in bild.punkte if p.gate == "Zackig")

        assert not zackig.einheitlich
        assert not bild.einheitlich
        assert "mehr als einmal" in bild.urteil()

    def test_eine_saubere_welt_meldet_einheitlich(self) -> None:
        bild = kipppunkte_suchen(_welt({"A": 0.00002, "B": 0.00008}))

        assert bild.einheitlich
        assert all(p.einheitlich for p in bild.punkte)
        assert "mehr als einmal" not in bild.urteil()


class TestDieGrenzenDerSuche:
    def test_oben_muss_ueber_unten_liegen(self) -> None:
        with pytest.raises(ValueError, match="oben"):
            kipppunkte_suchen(_welt({"A": 0.00002}), unten=0.0001, oben=0.0001)

    def test_die_toleranz_muss_positiv_sein(self) -> None:
        with pytest.raises(ValueError, match="Toleranz"):
            kipppunkte_suchen(_welt({"A": 0.00002}), toleranz=0.0)

    def test_ein_punkt_ausserhalb_des_bereichs_wird_nicht_erfunden(self) -> None:
        """Kippt das Gate erst oberhalb von 'oben', ist es hier kein
        Kipppunkt - und darf auch nicht als einer dastehen."""
        bild = kipppunkte_suchen(_welt({"A": 0.0005}), oben=0.0001)

        assert bild.punkte == ()
        assert bild.spielraum == 0.0001


class TestDieUmrechnung:
    def test_der_vorgabewert_sind_rund_elf_prozent(self) -> None:
        assert jahr_pct(BASISSATZ) == pytest.approx(10.95, abs=0.01)

    def test_die_stufe_rechnet_nicht_selbst(self) -> None:
        """Zwei Kopien derselben Formel laufen auseinander, ohne dass man es
        sieht - deshalb rechnet 'Stufe' mit derselben Funktion."""
        stufe = Stufe(satz=0.00007, cagr=0.0, rueckgang=0.0, bestanden=8, gesamt=11)

        assert stufe.jahr_pct == jahr_pct(0.00007)

    def test_die_periodenzahl_steht_fuer_alle_acht_stunden(self) -> None:
        assert PERIODEN_JE_JAHR == 3 * 365


class TestDasBildRechnetRichtig:
    def test_breite_und_prozente(self) -> None:
        punkt = Kipppunkt(gate="G", haelt_bis=0.00005, faellt_ab=0.00006)

        assert punkt.breite == pytest.approx(0.00001)
        assert punkt.haelt_bis_pct == pytest.approx(jahr_pct(0.00005))
        assert punkt.faellt_ab_pct == pytest.approx(jahr_pct(0.00006))

    def test_erster_ist_der_mit_dem_niedrigsten_durchfall(self) -> None:
        bild = Kippbild(
            punkte=(
                Kipppunkt(gate="spaet", haelt_bis=0.00008, faellt_ab=0.00009),
                Kipppunkt(gate="frueh", haelt_bis=0.00005, faellt_ab=0.00006),
            )
        )

        assert bild.erster is not None and bild.erster.gate == "frueh"
        assert bild.spielraum == 0.00005

    def test_der_anteil_misst_gegen_den_vorgabewert(self) -> None:
        bild = Kippbild(
            punkte=(Kipppunkt(gate="G", haelt_bis=BASISSATZ / 2, faellt_ab=BASISSATZ),)
        )

        assert bild.anteil_der_vorgabe == pytest.approx(0.5)

    def test_die_tabelle_nennt_jedes_gate_mit_beiden_raendern(self) -> None:
        text = kipppunkte_suchen(
            _welt({"A": 0.00002, "B": 0.00008})
        ).tabelle()

        assert "A" in text and "B" in text
        assert text.index("A") < text.index("B")

    def test_ein_uneinheitliches_gate_ist_in_der_tabelle_markiert(self) -> None:
        text = Kippbild(
            punkte=(
                Kipppunkt(
                    gate="G", haelt_bis=0.00005, faellt_ab=0.00006, einheitlich=False
                ),
            )
        ).tabelle()

        assert "nicht einheitlich" in text


class TestDasUrteilBleibtEhrlich:
    def test_es_sagt_dass_kein_versuch_faellig_wird(self) -> None:
        assert (
            "kostet keinen Versuch"
            in kipppunkte_suchen(_welt({"A": 0.00002})).urteil()
        )

    def test_es_stellt_den_satz_nicht_auf_den_spielraum(self) -> None:
        """Der Grundsatz aus Befund 100, hier noch einmal: Die Grenze zu
        kennen ist nicht dasselbe, wie sie einzusetzen."""
        text = kipppunkte_suchen(_welt({"A": 0.00002})).urteil()

        assert "nicht ein Vorschlag" in text


class TestLeiterUndSucheMessenAnDerselbenStelle:
    """Zwei Kopien der Konfiguration wuerden auseinanderlaufen, und der
    Unterschied waere an den Zahlen nicht zu sehen."""

    @staticmethod
    def _quelle() -> ast.FunctionDef:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "finanzierung"
        )

    def test_der_walkforward_wird_nur_einmal_aufgebaut(self) -> None:
        quelle = ast.unparse(self._quelle())

        assert quelle.count("run_portfolio_walkforward(") == 1

    def test_beide_zweige_rufen_denselben_lauf(self) -> None:
        quelle = ast.unparse(self._quelle())

        assert quelle.count("lauf(satz)") == 2

    def test_ein_satz_ohne_fenster_bricht_die_suche_statt_zu_schweigen(self) -> None:
        """"Nichts faellt durch" waere hier die falsche Auskunft - die Suche
        hielte den Satz fuer unbedenklich."""
        quelle = ast.unparse(self._quelle())

        assert "keine Fenster - die Suche kann daraus" in quelle


class TestDieKipppunkteSindFlacheSaetze:
    """**Befund 253.** Zwei Lesarten liegen einen Schritt daneben, und beide
    sind teuer.

    Erstens: Ein flacher Satz ist nur fuer ein rein langes Buch zugleich der
    tatsaechliche - bei Short-Anteil zahlen Longs und Shorts bekommen, und
    uebrig bleibt das Uebergewicht. Die Zahl laesst sich also nicht auf eine
    andere Regel uebertragen.

    Zweitens: Der Spielraum ist der Satz, den **dieser Kandidat** traegt. Weil
    seine Haltezeit in den steilsten Stuecken liegt (Befund 251), gehoert
    dazu ein Marktdurchschnitt darunter.
    """

    @staticmethod
    def _urteil() -> str:
        return kipppunkte_suchen(_welt({"Schlechtestes Jahr": 0.000055})).urteil()

    def test_das_urteil_nennt_sie_flach(self) -> None:
        assert "*flache* Saetze" in self._urteil()

    def test_es_sagt_warum_das_beim_bestand_zusammenfaellt(self) -> None:
        text = self._urteil()

        assert "rein long" in text
        assert "Short-Anteil" in text

    def test_es_warnt_vor_der_verwechslung_mit_dem_marktdurchschnitt(self) -> None:
        text = self._urteil()

        assert "nicht der Marktdurchschnitt" in text
        assert "darunter" in text

    def test_ohne_kipppunkt_steht_der_absatz_nicht_da(self) -> None:
        """Er haengt an einer Zahl - ohne die gibt es nichts zu lesen."""
        assert "*flache* Saetze" not in kipppunkte_suchen(lambda _s: ()).urteil()
