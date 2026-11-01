"""Die Zulassung verlangte keine vollstaendige Pruefung - Befund 445.

``GateReport.passed`` ist die Eigenschaft, auf der ``Candidate.admitted`` und
``pick_champion`` stehen - also die, die entscheidet, was in
``champion.json`` landet. Ihr Docstring sagt seit jeher:

    Zugelassen - und zwar nur nach einer **vollstaendigen** Pruefung auf den
    Daten der Boerse, auf der gehandelt wird.

Gerechnet wurden die Datenquelle und das Fehlen eines ``FAIL``. Weil
``GateResult.passed`` "nicht durchgefallen" heisst, steckte ein
**ausgesetztes** Gate darin - und ``all(...)`` ueber eine leere Liste ist
wahr.

**Das ist nicht neu, nur war es nie hier behoben.** Befund 321/322 hat
dieselbe Verwechslung an zwei Stellen gefunden, 332 ein Verzeichnis der
betroffenen Typen angelegt, 338/346/347/349 fuenf nachgezogen, 350 einen
Mechanismus daraus gemacht. Und ``nachpruefung.Ergebnis.zugelassen`` -
der **Berichts**typ - verlangt seit 322 genau die drei fehlenden
Bedingungen und nennt ihr Fehlen:

    genau die Sorte stiller Aufwertung, gegen die die ganze
    Zulassungsstrecke gebaut ist

Der Berichtstyp war streng, die Zulassung selbst nicht.
"""

from __future__ import annotations

from itertools import product

from research.admission import Candidate
from research.gates import GateReport, GateResult, GateStatus


def _r(name: str, status: GateStatus) -> GateResult:
    return GateResult(name, status, 1.0, 1.0, "Grund")


def _bericht(*stati: GateStatus, **kw) -> GateReport:
    namen = ("Messlatte", "Deflated Sharpe", "Regime-Aufteilung", "Drawdown")
    return GateReport(
        genome_id="x",
        results=[_r(namen[i], s) for i, s in enumerate(stati)],
        **kw,
    )


class TestEinGateOhneUrteilIstKeineZulassung:
    def test_ein_uebersprungenes_gate_blockiert(self) -> None:
        bericht = _bericht(GateStatus.PASS, GateStatus.SKIP)

        assert not bericht.passed
        assert bericht.uebersprungen == ["Deflated Sharpe"]

    def test_der_kandidat_ist_damit_nicht_zugelassen(self) -> None:
        """Die Eigenschaft, an der ``champion.json`` haengt."""
        bericht = _bericht(GateStatus.PASS, GateStatus.SKIP)
        kandidat = Candidate(genome=None, walkforward=None, gates=bericht)

        assert not kandidat.admitted

    def test_alles_wirklich_bestanden_bleibt_zugelassen(self) -> None:
        """Gegenprobe - die Verschaerfung darf nichts Richtiges abweisen."""
        bericht = _bericht(GateStatus.PASS, GateStatus.PASS, GateStatus.PASS)

        assert bericht.passed

    def test_ein_leerer_bericht_laesst_nichts_zu(self) -> None:
        """``all(...)`` ueber nichts ist wahr - und hiess damit 'bestanden'."""
        assert not GateReport(genome_id="x", results=[]).passed

    def test_ein_durchgefallenes_gate_blockiert_weiterhin(self) -> None:
        assert not _bericht(GateStatus.PASS, GateStatus.FAIL).passed

    def test_vorauswahl_und_forschungskerzen_blockieren_weiterhin(self) -> None:
        assert not _bericht(GateStatus.PASS, vorauswahl=True).passed
        assert not _bericht(GateStatus.PASS, referenzdaten=True).passed


class TestDasTrifftAusgerechnetDieHaertestenGates:
    """**Warum es mehr ist als ein Randfall.**

    Unter 30 Trades setzen Regime-Aufteilung und Deflated Sharpe aus, unter
    20 auch Monte-Carlo. Der Deflated Sharpe ist das Gate, an dem dieses
    Projekt steht - und der billigste Weg, es zu bestehen, war, zu wenig zu
    handeln. Genau so hiess Befund 322: *"Nicht zu handeln war die beste Art,
    Gates zu bestehen."*
    """

    def test_die_aussetzschwellen_betreffen_die_zwei_offenen_gates(self) -> None:
        from research.aussetzer import SCHWELLEN

        assert SCHWELLEN["Deflated Sharpe"] == 30
        assert SCHWELLEN["Regime-Aufteilung"] == 30
        assert SCHWELLEN["Monte-Carlo"] == 20

    def test_ein_duenner_kandidat_kommt_nicht_mehr_durch(self) -> None:
        """Die Lage, die vorher eine Zulassung war: Nichts durchgefallen,
        aber die beiden haertesten Gates haben nie geurteilt."""
        bericht = _bericht(
            GateStatus.PASS, GateStatus.SKIP, GateStatus.SKIP, GateStatus.PASS
        )

        assert not bericht.passed
        assert bericht.uebersprungen == ["Deflated Sharpe", "Regime-Aufteilung"]


class TestDieRueckmeldungIstNieLeer:
    """Sie steuert den Suchlauf - eine leere Antwort ist die schlechteste."""

    def test_bei_vorauswahl_sagt_sie_was_fehlt(self) -> None:
        text = _bericht(GateStatus.PASS, vorauswahl=True).feedback_for_ai()

        assert "Vorauswahl" in text
        assert "keine Zulassung" in text

    def test_bei_forschungskerzen_auch(self) -> None:
        text = _bericht(GateStatus.PASS, referenzdaten=True).feedback_for_ai()

        assert "Boerse" in text

    def test_bei_uebersprungenen_nennt_sie_die_namen(self) -> None:
        text = _bericht(GateStatus.PASS, GateStatus.SKIP).feedback_for_ai()

        assert "Deflated Sharpe" in text
        assert "nicht geurteilt hat, ist nicht bestanden" in text

    def test_ohne_jedes_gate_sagt_sie_das(self) -> None:
        text = GateReport(genome_id="x", results=[]).feedback_for_ai()

        assert "Kein Gate ist gelaufen" in text

    def test_in_keiner_lage_bleibt_sie_leer(self) -> None:
        """**Die eigentliche Zusicherung**, ueber alle Kombinationen statt
        ueber die Faelle, an die ich gedacht habe."""
        stati = (GateStatus.PASS, GateStatus.FAIL, GateStatus.SKIP)
        for erst, zweit, vor, ref in product(stati, stati, (False, True), (False, True)):
            bericht = _bericht(erst, zweit, vorauswahl=vor, referenzdaten=ref)
            text = bericht.feedback_for_ai()

            assert text.strip(), (erst, zweit, vor, ref)
            if not bericht.passed:
                assert text != "Alle Gates bestanden.", (erst, zweit, vor, ref)

    def test_und_bestanden_heisst_bestanden(self) -> None:
        text = _bericht(GateStatus.PASS, GateStatus.PASS).feedback_for_ai()

        assert text == "Alle Gates bestanden."


class TestDerBerichtssatzNenntDenGrund:
    def test_uebersprungene_stehen_mit_namen_darin(self) -> None:
        satz = _bericht(GateStatus.PASS, GateStatus.SKIP).summary()

        assert "1 von 2 Gates geurteilt und bestanden" in satz
        assert "Deflated Sharpe" in satz
        assert "keine Zulassung" in satz

    def test_nicht_mehr_alle_bestanden(self) -> None:
        """Der alte Satz - *'alle 2 Gates bestanden'* - war die stille
        Aufwertung in Worten."""
        satz = _bericht(GateStatus.PASS, GateStatus.SKIP).summary()

        assert "alle 2 Gates bestanden" not in satz

    def test_ohne_gates_behauptet_er_nichts(self) -> None:
        satz = GateReport(genome_id="x", results=[]).summary()

        assert "kein Gate gelaufen" in satz
        assert "bestanden" not in satz


class TestDieBeidenZulassungenSagenDasselbe:
    """**Die Asymmetrie, die den Befund ausmacht.**

    ``nachpruefung.Ergebnis.zugelassen`` verlangt seit Befund 322 alle drei
    Bedingungen. ``GateReport.passed`` verlangte keine davon. Zwei Stellen,
    die dieselbe Frage beantworten, sollen dieselbe Antwort geben.
    """

    @staticmethod
    def _ergebnis(*, uebersprungen=(), bestanden=2, gesamt=2, vorauswahl=False):
        from research.nachpruefung import Ergebnis

        return Ergebnis(
            genome_id="x",
            name="x",
            generation=1,
            bestanden=bestanden,
            gesamt=gesamt,
            uebersprungen=tuple(uebersprungen),
            vorauswahl=vorauswahl,
        )

    def test_beide_weisen_ein_uebersprungenes_gate_ab(self) -> None:
        assert not self._ergebnis(uebersprungen=("Deflated Sharpe",)).zugelassen
        assert not _bericht(GateStatus.PASS, GateStatus.SKIP).passed

    def test_beide_weisen_den_leeren_fall_ab(self) -> None:
        assert not self._ergebnis(bestanden=0, gesamt=0).zugelassen
        assert not GateReport(genome_id="x", results=[]).passed

    def test_beide_weisen_die_vorauswahl_ab(self) -> None:
        assert not self._ergebnis(vorauswahl=True).zugelassen
        assert not _bericht(GateStatus.PASS, vorauswahl=True).passed

    def test_und_beide_lassen_den_vollstaendigen_fall_zu(self) -> None:
        assert self._ergebnis().zugelassen
        assert _bericht(GateStatus.PASS, GateStatus.PASS).passed
