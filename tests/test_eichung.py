"""Was bedeutet die Latte des haertesten Gates?

**Befund 278.** Befund 276 und 277 haben dieselbe Frage an die beiden Scans
gestellt: Steht die Latte da, wo ihr Name behauptet? Im Vorteilsscan nein, im
Tageszeit-Scan ja. Dieselbe Frage gehoert an das Gate, das die Zulassung
blockiert - und dort stand die Antwort nirgends.

Was hier gehalten wird
----------------------
**Die Null kommt aus den eigenen Trades.** Auf Mittelwert null geschoben:
dieselbe Schiefe, dieselbe Woelbung, derselbe Schwanz - nur kein Vorteil. Ein
Ersatz aus der Normalverteilung haette andere Schwaenze, und gerade die gehen
ueber Schiefe und Woelbung in die Formel ein.

**Gerechnet wird wie im Gate.** Populationsmomente auf der mit ``np.std``
normierten Reihe, effektive Stichprobe an die Formel, rohe Trade-Zahl fuer
den Sharpe. Wer hier anders rechnet, eicht eine Formel, die es nicht gibt.

**Und die Latte bleibt stehen.** Diese Tests halten fest, dass die Messung
eine Messung ist und kein Vorschlag: ``latte_fuer_fuenf_prozent`` heisst so,
weil es ein Vergleichswert ist, und die Schwelle im Gate ruehrt sie nicht an.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from research.eichung import LAEUFE, Nullverteilung, nullverteilung
from research.gates import GateThresholds, deflated_sharpe_ratio


def _handelsartig(n: int = 156, saat: int = 278) -> np.ndarray:
    """Trade-Ergebnisse mit der Form des Bestands: rechtsschief, dicker Rand.

    Der Bestand traegt Schiefe 3,49 und Woelbung 16,19 - viele kleine
    Verluste, wenige grosse Gewinne. Eine Normalverteilung waere hier der
    falsche Ersatz.
    """
    rng = np.random.default_rng(saat)
    treffer = rng.random(n) < 0.26
    return np.where(treffer, rng.standard_exponential(n) * 3.0, -1.0)


class TestDieNullKommtAusDenEigenenTrades:
    def test_die_form_bleibt_erhalten(self) -> None:
        """Verschoben wird der Mittelwert, sonst nichts."""
        werte = _handelsartig()
        verschoben = werte - werte.mean()

        assert np.std(verschoben) == pytest.approx(np.std(werte))
        z_alt = (werte - werte.mean()) / np.std(werte)
        z_neu = (verschoben - verschoben.mean()) / np.std(verschoben)
        assert np.mean(z_neu**3) == pytest.approx(np.mean(z_alt**3))

    def test_zu_wenige_trades_sind_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="Zu wenige Trades"):
            nullverteilung([1.0, 2.0], versuche=10, stichprobe=115)

    def test_unsinnige_angaben_sind_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="sinnvoll"):
            nullverteilung(_handelsartig(), versuche=0, stichprobe=115)
        with pytest.raises(ValueError, match="sinnvoll"):
            nullverteilung(_handelsartig(), versuche=10, stichprobe=2)


class TestBeiEinemVersuchStimmtDieFormel:
    """Der Kontrollfall: Ohne Deflation tut sie, was ihr Name sagt."""

    def test_die_latte_liegt_dann_bei_etwa_null_komma_neun_fuenf(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=1, stichprobe=115, laeufe=3000
        )

        assert abs(null.latte_fuer_fuenf_prozent - 0.95) < 0.06

    def test_und_der_fehlalarm_bei_etwa_fuenf_prozent(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=1, stichprobe=115, laeufe=3000
        )

        assert 0.01 < null.fehlalarm < 0.09


class TestMitVielenVersuchenWirdSieStrenger:
    """Der Befund von 278."""

    def test_die_nullverteilung_rutscht_nach_unten(self) -> None:
        wenig = nullverteilung(
            _handelsartig(), versuche=1, stichprobe=115, laeufe=2000
        )
        viel = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=2000
        )

        assert viel.latte_fuer_fuenf_prozent < wenig.latte_fuer_fuenf_prozent
        assert viel.perzentil(99) < wenig.perzentil(99)

    def test_der_median_taugt_dafuer_nicht(self) -> None:
        """Ein Fehlschlag beim Bauen, festgehalten: Bei **einem** Versuch ist
        der gezogene Sharpe in rund der Haelfte der Laeufe negativ, und
        ``deflated_sharpe_ratio`` liefert dann glatt 0. Die Nullverteilung
        hat dort einen Klumpen auf der Null, ihr Median ist 0 - und damit
        kleiner als der bei 198 Versuchen. Verglichen wird deshalb der
        obere Rand, nicht die Mitte."""
        wenig = nullverteilung(
            _handelsartig(), versuche=1, stichprobe=115, laeufe=1500
        )

        assert wenig.perzentil(50) == 0.0

    def test_und_der_fehlalarm_faellt_weit_unter_fuenf_prozent(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=2000
        )

        assert null.fehlalarm < 0.005

    def test_das_gilt_monoton_ueber_die_versuchsstaende(self) -> None:
        vorher = 1.0
        for versuche in (1, 10, 50, 198):
            null = nullverteilung(
                _handelsartig(), versuche=versuche, stichprobe=115, laeufe=1200
            )
            assert null.latte_fuer_fuenf_prozent <= vorher
            vorher = null.latte_fuer_fuenf_prozent


class TestSieRechnetWieDasGate:
    def test_dieselbe_funktion_wird_aufgerufen(self) -> None:
        """Eine zweite Fassung der Formel liefe frueher oder spaeter
        auseinander - dann eicht die Probe eine andere Latte als die gilt."""
        import inspect

        from research import eichung

        assert "deflated_sharpe_ratio(" in inspect.getsource(eichung._wie_das_gate)

    def test_populationsmomente_wie_im_gate(self) -> None:
        """Das Gate normiert mit ``np.std`` ohne Freiheitsgradkorrektur und
        nimmt rohe vierte Momente - nicht die Ueberschusswoelbung."""
        import inspect

        quelle = inspect.getsource(
            __import__("research.eichung", fromlist=["_wie_das_gate"])._wie_das_gate
        )

        assert "np.std(" in quelle
        assert "**4" in quelle
        assert "ddof" not in quelle

    def test_eine_reihe_ohne_streuung_gibt_null(self) -> None:
        from research.eichung import _wie_das_gate

        assert _wie_das_gate(np.zeros(50), 0.0, 10, 40) == 0.0


class TestWasDieProbeNichtKann:
    def test_die_aufloesung_haengt_an_den_laeufen(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=1000
        )

        assert null.aufloesung == pytest.approx(1 / 1001)

    def test_kein_einziger_lauf_wird_als_schranke_gemeldet(self) -> None:
        """"Null von 5.000" heisst hoechstens 1 von 5.001 - und das gehoert
        so dazustehen, nicht als glatte Null."""
        null = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=1000
        )

        if null.fehlalarm == 0:
            assert "unter" in null.beschreibe()
            assert "kein einziger Lauf" in null.beschreibe()

    def test_die_laeufe_sind_gezaehlt(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=10, stichprobe=115, laeufe=700
        )

        assert null.laeufe == 700
        assert LAEUFE > 700


class TestDieLageDesBestands:
    """Der rohe DSR faellt mit jedem Versuch - die Null faellt mit.

    **Befund 279.** Ohne die zweite Haelfte liest sich der erste Teil wie ein
    Verfall: 0,5881 auf 0,5551, wenn der Rest des Suchbudgets ausgegeben
    wird. Gemessen bleibt die **Lage** dabei fast stehen, weil sich die
    Nullverteilung mitbewegt.
    """

    def test_das_perzentil_liegt_zwischen_null_und_hundert(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=1000
        )

        assert 0.0 <= null.lage(0.5) <= 100.0

    def test_ein_wert_ueber_allem_steht_bei_hundert(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=1000
        )

        assert null.lage(1.01) == 100.0

    def test_ein_wert_unter_allem_steht_bei_null(self) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=1000
        )

        assert null.lage(-1.0) == 0.0

    def test_das_perzentil_des_fuenf_prozent_punktes_ist_fuenfundneunzig(
        self,
    ) -> None:
        null = nullverteilung(
            _handelsartig(), versuche=198, stichprobe=115, laeufe=2000
        )

        assert null.lage(null.latte_fuer_fuenf_prozent) == pytest.approx(95.0, abs=0.2)

    def test_mehr_versuche_senken_den_wert_und_die_null_zugleich(self) -> None:
        """Der Punkt: Beide Seiten bewegen sich, also sagt der rohe Wert
        allein nichts darueber, ob die Evidenz schwaecher geworden ist."""
        from research.gates import deflated_sharpe_ratio

        # Dieselbe Form, aber mit dem Vorsprung des Bestands (0,27 je Trade).
        # Ohne ihn liefert die Formel bei beiden Versuchsstaenden glatt 0,
        # und der Vergleich saehe nach Gleichstand aus.
        roh = _handelsartig()
        werte = roh - roh.mean() + 0.27 * float(np.std(roh, ddof=1))
        streuung = float(np.std(werte, ddof=1))
        sharpe = float(np.mean(werte)) / streuung
        z = (werte - werte.mean()) / streuung
        schiefe, woelbung = float(np.mean(z**3)), float(np.mean(z**4))

        lagen = []
        for versuche in (198, 400):
            dsr = deflated_sharpe_ratio(
                observed_sharpe=sharpe,
                trials=versuche,
                sample_size=115,
                skew=schiefe,
                kurtosis=woelbung,
            )
            null = nullverteilung(
                werte, versuche=versuche, stichprobe=115, laeufe=2000
            )
            lagen.append((dsr, null.latte_fuer_fuenf_prozent, null.lage(dsr)))

        # Roher Wert faellt, Latte der Null faellt - die Lage bleibt nahe.
        assert lagen[1][0] < lagen[0][0]
        assert lagen[1][1] < lagen[0][1]
        assert abs(lagen[1][2] - lagen[0][2]) < 5.0


class TestDieLatteBleibtStehen:
    """Der Grundsatz, gegen den diese Messung am ehesten missbraucht wuerde."""

    def test_die_schwelle_im_gate_ist_unveraendert(self) -> None:
        assert GateThresholds().min_deflated_sharpe == 0.95

    def test_das_modul_sagt_dass_es_kein_vorschlag_ist(self) -> None:
        from research import eichung

        assert "nicht gelockert" in eichung.__doc__
        assert "Kein Grund, die Latte zu senken" in eichung.__doc__

    def test_der_vergleichswert_heisst_nach_seinem_zweck(self) -> None:
        """``latte_fuer_fuenf_prozent`` ist ein Vergleich, kein Ersatz - und
        sein Docstring muss das sagen."""
        assert (
            "kein Vorschlag"
            in Nullverteilung.latte_fuer_fuenf_prozent.__doc__
        )

    def test_die_frage_steht_beim_nutzer(self) -> None:
        """**Befund 279.** Gemessen und berichtet reicht nicht: Ob die Latte
        so stehen bleiben soll, ist eine Geschaeftsentscheidung, und die
        gehoert in die Liste, die der Nutzer liest."""
        from research.stand import ENTSCHEIDUNGEN

        eintrag = next(
            (e for e in ENTSCHEIDUNGEN if "Latte des Deflated Sharpe" in e.frage),
            None,
        )

        assert eintrag is not None
        assert "0,9305" in eintrag.zahl
        assert "0,3059" in eintrag.zahl
        assert "Geaendert wurde nichts" in eintrag.warum
        assert "faellt nicht hier" in eintrag.warum

    def test_und_sie_nennt_ihre_einschraenkungen(self) -> None:
        from research.stand import ENTSCHEIDUNGEN

        eintrag = next(
            e for e in ENTSCHEIDUNGEN if "Latte des Deflated Sharpe" in e.frage
        )

        assert "korreliert" in eintrag.warum
        assert "kein einziger" in eintrag.warum

    def test_der_befehl_sagt_es_auch(self) -> None:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "abstand"
        )
        quelle = ast.unparse(knoten)

        assert "Keine Aufforderung, die Latte zu senken" in quelle

    def test_die_gate_botschaft_behauptet_keine_wahrscheinlichkeit(self) -> None:
        """Hier stand 'Wahrscheinlichkeit 46,3 %, dass der Vorteil echt ist'.
        Gemessen ist die Zahl das nicht."""
        import inspect

        from research import gates

        quelle = inspect.getsource(gates.gate_deflated_sharpe)

        assert "Wahrscheinlichkeit {dsr" not in quelle
        assert "keine Wahrscheinlichkeit" in quelle


class TestDerBefehlKenntDieEichung:
    def test_es_gibt_ein_flag(self) -> None:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "abstand"
        )

        assert "eichung" in {a.arg for a in knoten.args.args}

    def test_es_steht_in_der_hilfe(self) -> None:
        from typer.testing import CliRunner

        from cli import app

        assert "--eichung" in CliRunner().invoke(app, ["abstand", "--help"]).output

    def test_die_eichung_nimmt_dieselbe_stichprobe_wie_das_gate(self) -> None:
        """Der Fehler aus Befund 135/139: rohe statt effektiver Stichprobe."""
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "abstand"
        )
        aufrufe = [
            k
            for k in ast.walk(knoten)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id == "nullverteilung"
        ]

        assert aufrufe
        for aufruf in aufrufe:
            namen = {s.arg for s in aufruf.keywords}
            assert "stichprobe" in namen
            stichprobe = next(s for s in aufruf.keywords if s.arg == "stichprobe")
            assert ast.unparse(stichprobe.value) == "n"

    def test_die_tafel_reicht_bis_zur_budgetgrenze(self) -> None:
        """**Befund 279.** Was der Rest der erlaubten Suche an der Lage des
        Bestands aendert, gehoert in dieselbe Tafel - sonst liest man den
        Verfall des rohen Wertes und nicht seine Bedeutung."""
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "abstand"
        )
        quelle = ast.unparse(knoten)

        assert "BUDGET.grenze" in quelle
        assert "sein Perzentil" in quelle

    def test_alle_zeilen_haben_dieselbe_aufloesung(self) -> None:
        """Eine Zeile aus 1.250 Laeufen neben einer aus 5.000 saehe genauso
        aus und meinte etwas anderes - und das Register zitiert sie."""
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "abstand"
        )
        for aufruf in ast.walk(knoten):
            if (
                isinstance(aufruf, ast.Call)
                and isinstance(aufruf.func, ast.Name)
                and aufruf.func.id == "nullverteilung"
            ):
                laeufe = next(
                    (s for s in aufruf.keywords if s.arg == "laeufe"), None
                )
                if laeufe is not None:
                    assert ast.unparse(laeufe.value) == "null.laeufe"


def test_die_formel_ist_bei_einem_versuch_nicht_deflationiert() -> None:
    """Warum der Kontrollfall oben ueberhaupt einer ist."""
    ohne = deflated_sharpe_ratio(
        observed_sharpe=0.2, trials=1, sample_size=115, skew=0.0, kurtosis=3.0
    )
    mit = deflated_sharpe_ratio(
        observed_sharpe=0.2, trials=198, sample_size=115, skew=0.0, kurtosis=3.0
    )

    assert ohne > mit
