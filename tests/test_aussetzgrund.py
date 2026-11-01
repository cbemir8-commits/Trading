"""Nicht jeder Aussetzer hat denselben Grund - Befund 446.

Befund 445 hat ``GateReport.passed`` verschaerft: Ein Gate ohne Urteil ist
keine Zulassung. Das ist richtig und bleibt - **offen gelassen hat es die
Frage, ob eine Zulassung spaeter noch moeglich ist.** Denn die Aussetzer sind
von zwei Arten:

**Stichprobe.** Mehr Trades oder mehr Historie, und das Gate urteilt. Wer
daran scheitert, kann wiederkommen.

**Struktur.** Keine Datenmenge hilft. Das Genom hat keinen variierbaren
Regler ("Genom hat keine variierbaren Perioden"), oder das Ergebnis ist
entartet - kein einziger Verlust in einem Umfeld, keine Streuung in den
Ergebnissen. Ein solcher Kandidat kann **nie** zugelassen werden, solange ein
Aussetzer blockiert.

Das ist eine Nebenwirkung meiner eigenen Verschaerfung von gestern, und sie
gehoert gemessen statt vermutet: **0 von 54** Genomen des Katalogs haben
keine variierbare Periode. Heute kostet die Verschaerfung also keinen
Kandidaten. Ob sie einen kuenftigen kosten darf, ist eine Entscheidung ueber
die Zulassung und keine statistische - sie steht in ``OFFEN`` und wird hier
nicht getroffen.
"""

from __future__ import annotations

import inspect

from research.aussetzer import (
    AUSSETZSTELLEN,
    SCHWELLEN,
    STRUKTURELL,
    STRUKTURMARKEN,
    aussetzbar,
    aussetzstellen,
)

#: Genome im Katalog - gemessen (Befund 446).
KATALOG = 54


def _katalog():
    from research import seeds
    from strategy.genome import Genome

    gefunden = {}
    for name in dir(seeds):
        if name.startswith("_"):
            continue
        obj = getattr(seeds, name)
        if not callable(obj) or isinstance(obj, type):
            continue
        try:
            if inspect.signature(obj).parameters:
                continue
            genom = obj()
        except Exception:
            continue
        if isinstance(genom, Genome):
            gefunden[name] = genom
    return gefunden


class TestJedeAussetzstelleIstVerzeichnet:
    """Gerechnet aus dem Quelltext, nicht gepflegt - sonst waere die Liste
    die zweite Quelle (Befund 439)."""

    def test_die_gemessene_menge_ist_die_verzeichnete(self) -> None:
        gemessen = aussetzstellen()

        assert gemessen == AUSSETZSTELLEN, (
            sorted(set(gemessen) ^ set(AUSSETZSTELLEN)),
            {k: (gemessen.get(k), AUSSETZSTELLEN.get(k)) for k in set(gemessen) | set(AUSSETZSTELLEN) if gemessen.get(k) != AUSSETZSTELLEN.get(k)},
        )

    def test_es_sind_neun_stellen_in_sechs_gates(self) -> None:
        assert sum(AUSSETZSTELLEN.values()) == 9
        assert len(AUSSETZSTELLEN) == 6

    def test_ein_vergleich_ist_keine_aussetzstelle(self) -> None:
        """``if GateStatus.SKIP in (a.status, b.status)`` steht in
        ``vergleichbar`` und erzeugt keinen Aussetzer - eine Textsuche nach
        'GateStatus.SKIP' haette es mitgezaehlt."""
        assert "vergleichbar" not in AUSSETZSTELLEN
        assert "uebersprungen" not in AUSSETZSTELLEN

    def test_die_aussetzbaren_sind_geordnet(self) -> None:
        assert list(aussetzbar()) == sorted(AUSSETZSTELLEN)


class TestDieBeidenArtenSindGetrennt:
    def test_die_strukturellen_sind_eine_teilmenge(self) -> None:
        strukturell = set(STRUKTURELL)

        assert strukturell <= set(AUSSETZSTELLEN)

    def test_es_sind_genau_drei_gates(self) -> None:
        strukturell = set(STRUKTURELL)

        assert strukturell == {
            "gate_parameter_plateau",
            "gate_regime_split",
            "gate_deflated_sharpe",
        }

    def test_jedes_gate_mit_schwelle_kann_an_der_stichprobe_aussetzen(self) -> None:
        """``SCHWELLEN`` nennt drei Gates mit einer Mindest-Trade-Zahl - jedes
        davon muss eine Aussetzstelle haben, sonst waere die Schwelle ohne
        Wirkung verzeichnet."""
        namen = {
            "Deflated Sharpe": "gate_deflated_sharpe",
            "Regime-Aufteilung": "gate_regime_split",
            "Monte-Carlo": "gate_monte_carlo",
        }

        for gate, fn in namen.items():
            assert gate in SCHWELLEN, gate
            assert fn in AUSSETZSTELLEN, fn

    def test_zwei_gates_koennen_aus_beiden_gruenden_aussetzen(self) -> None:
        """Dieselbe Funktion hat beide Arten: 'Zu wenige Trades' und
        'Keine Streuung in den Ergebnissen' stehen beide in
        ``gate_deflated_sharpe``."""
        for fn in ("gate_deflated_sharpe", "gate_regime_split"):
            assert AUSSETZSTELLEN[fn] == 2, fn
            assert fn in STRUKTURELL, fn

        # Und die Gegenprobe: 'gate_parameter_plateau' kann **nur**
        # strukturell aussetzen - eine Stelle, und die ist es.
        assert AUSSETZSTELLEN["gate_parameter_plateau"] == 1
        assert "gate_parameter_plateau" in STRUKTURELL

    def test_die_marken_stehen_wirklich_im_quelltext(self) -> None:
        """Als Fundstelle, nicht als Schalter - aber eine Fundstelle, die
        nicht trifft, ist keine."""
        from research import gates

        quelle = inspect.getsource(gates)

        for marke in STRUKTURMARKEN:
            assert marke in quelle, marke


class TestHeuteKostetDieVerschaerfungNichts:
    """**Die Messung, die 445 traegt.** Ohne sie waere die Verschaerfung eine
    Hoffnung."""

    def test_der_katalog_hat_vierundfuenfzig_genome(self) -> None:
        assert len(_katalog()) == KATALOG, len(_katalog())

    def test_keines_davon_ist_ohne_variierbare_periode(self) -> None:
        from research.gates import nachbarschaft

        ohne = [
            name
            for name, genom in _katalog().items()
            if not list(nachbarschaft(genom, 0.2))
        ]

        assert ohne == [], ohne

    def test_der_spitzenkandidat_hat_nachbarn(self) -> None:
        """Die Gegenprobe am massgeblichen Genom."""
        from research.gates import nachbarschaft
        from research.seeds import spitzenkandidat

        assert list(nachbarschaft(spitzenkandidat(), 0.2))


class TestDieEntscheidungWirdNichtHierGetroffen:
    def test_ein_struktureller_aussetzer_blockiert_weiterhin(self) -> None:
        """**Die sichere Richtung bleibt stehen.** Ein Aussetzer als
        bestanden zu zaehlen waere die stille Aufwertung aus Befund 322;
        ihn durchzulassen, weil er strukturell ist, waere eine
        Zulassungsentscheidung - und die liegt beim Nutzer."""
        from research.gates import GateReport, GateResult, GateStatus

        bericht = GateReport(
            genome_id="x",
            results=[
                GateResult("Messlatte", GateStatus.PASS, 1.0, 1.0, ""),
                GateResult(
                    "Parameter-Plateau",
                    GateStatus.SKIP,
                    0.0,
                    0.6,
                    "Genom hat keine variierbaren Perioden",
                ),
            ],
        )

        assert not bericht.passed
        assert bericht.uebersprungen == ["Parameter-Plateau"]

    def test_und_die_rueckmeldung_sagt_warum(self) -> None:
        from research.gates import GateReport, GateResult, GateStatus

        bericht = GateReport(
            genome_id="x",
            results=[
                GateResult("Messlatte", GateStatus.PASS, 1.0, 1.0, ""),
                GateResult(
                    "Parameter-Plateau",
                    GateStatus.SKIP,
                    0.0,
                    0.6,
                    "Genom hat keine variierbaren Perioden",
                ),
            ],
        )

        text = bericht.feedback_for_ai()

        assert "Parameter-Plateau" in text
        assert "nicht geurteilt hat, ist nicht bestanden" in text

    def test_die_frage_steht_im_offenen_register(self) -> None:
        from research.stand import OFFEN

        namen = [r.name for r in OFFEN]

        assert any("strukturell" in n.lower() for n in namen), namen
