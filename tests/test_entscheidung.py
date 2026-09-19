"""Die Entscheidungen des Nutzers haben jetzt eine Fundstelle - Befund 305.

``Richtung`` traegt seit Befund 130 eine, ``Auftragspunkt`` seit 304. Das
Register, das den Nutzer um eine Entscheidung bittet, hatte gar keine: drei
freie Textfelder, und die Befundnummern standen als Prosa mitten im Satz.

Das ist nicht Ordnungsliebe. Der Eintrag zur Research-KI nannte als
Anforderung "120 Trades bei Guete ueber 0,23" aus Befund 74/75 - waehrend 291
und 292 laengst 0,2641 je Trade bei n_eff 254 gemessen hatten. Wer danach
entscheidet, entscheidet auf einer Latte von vor zweihundert Befunden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.nachmessung import abschnitte
from research.stand import ENTSCHEIDUNGEN, Entscheidung

BEFUND = Path("strategies/BEFUND.md")


@pytest.fixture(scope="module")
def laborbuch() -> str:
    return BEFUND.read_text(encoding="utf-8")


def _eine(**felder) -> Entscheidung:
    return Entscheidung(frage="F", zahl="Z", warum="W", **felder)


class TestDieFundstelle:
    def test_ohne_messung_steht_das_auch_da(self) -> None:
        """Nicht jede Entscheidung steht auf einer Messung - die
        Wochenverlustgrenze ist eine Betriebsfrage. Eine erfundene
        Fundstelle waere schlimmer als keine."""
        assert _eine().stelle == "ohne Messung"
        assert _eine().massgeblich == 0

    def test_eine_messung_steht_da(self) -> None:
        assert _eine(befund=162).stelle == "Nr. 162"
        assert _eine(befund=162).massgeblich == 162

    def test_eine_nachmessung_gilt_vor_der_erstmessung(self) -> None:
        e = _eine(befund=57, zuletzt=281)
        assert e.massgeblich == 281
        assert e.stelle == "Nr. 281, zuerst 57"

    def test_keine_geschachtelte_klammer(self) -> None:
        """'Nr. 281 (zuerst 57)' stuende im Bericht in einer weiteren
        Klammer - Befund 293 hat das an derselben Stelle abgestellt."""
        assert "(" not in _eine(befund=57, zuletzt=281).stelle

    def test_eine_nachmessung_muss_spaeter_liegen(self) -> None:
        with pytest.raises(ValueError, match="keine Nachmessung"):
            _eine(befund=100, zuletzt=99)

    def test_eine_nachmessung_ohne_erstmessung_ist_keine(self) -> None:
        with pytest.raises(ValueError, match="ohne Erstmessung"):
            _eine(zuletzt=281)


class TestDasEchteRegister:
    def test_jede_fundstelle_gibt_es_im_laborbuch(self, laborbuch: str) -> None:
        """Dieselbe Wache wie fuer ``GESCHLOSSEN`` (130) und ``AUFTRAG``
        (304)."""
        vorhanden = {a.nummer for a in abschnitte(laborbuch)}
        fehlend = [
            e.frage
            for e in ENTSCHEIDUNGEN
            if e.befund and e.massgeblich not in vorhanden
        ]
        assert not fehlend, f"Fundstelle zeigt ins Leere: {fehlend}"

    def test_die_fundstelle_steht_auch_im_text(self) -> None:
        """Ein Eintrag, dessen Marke auf einen Befund zeigt, der im Text
        nicht vorkommt, waere zwei Behauptungen statt einer."""
        for e in ENTSCHEIDUNGEN:
            if e.befund:
                text = f"{e.zahl} {e.warum}"
                assert str(e.massgeblich) in text, e.frage

    def test_nur_eine_steht_ohne_messung_da(self) -> None:
        """Ausgeschrieben, damit eine weitere eine bewusste Entscheidung
        ist. Die Wochenverlustgrenze ist eine Bauentscheidung ohne Messung
        dahinter - alles andere hier steht auf Zahlen."""
        ohne = [e.frage for e in ENTSCHEIDUNGEN if not e.befund]
        assert ohne == ["Wochenverlustgrenze"]

    def test_die_ki_entscheidung_nennt_die_heutige_latte(self) -> None:
        """**Der Fund, der diesen Befund ausgeloest hat.** Der Eintrag
        nannte die Anforderung aus Befund 74/75; gemessen ist sie seit 291."""
        ki = next(e for e in ENTSCHEIDUNGEN if "Research-KI" in e.frage)
        assert "0,2641" in ki.zahl
        assert "254" in ki.zahl
        assert ki.massgeblich == 292

    def test_der_strukturelle_bruch_steht_unter_den_entscheidungen(self) -> None:
        """Seit Befund 283 nennt das Register 'Einstieg, der nicht am
        Rauschen haengt' als die wichtigste offene Richtung und sagt, dass
        sie einen Versuch kostet - unter den **Richtungen**.

        Eine Entscheidung, die nirgends unter den Entscheidungen steht, wird
        nicht getroffen, sondern vertagt.
        """
        bruch = next(
            (e for e in ENTSCHEIDUNGEN if "Neues Hoch im Takt" in e.frage), None
        )
        assert bruch is not None
        assert "einen Versuch" in bruch.zahl or "ein Versuch" in bruch.frage
        assert bruch.massgeblich == 283

    def test_jede_entscheidung_traegt_alle_drei_texte(self) -> None:
        for e in ENTSCHEIDUNGEN:
            assert e.frage.strip()
            assert e.zahl.strip(), e.frage
            assert e.warum.strip(), e.frage


class TestImBericht:
    def _bericht(self) -> str:
        from research.stand import Lage

        return Lage(
            kandidat="Trend 50 Tage mit Konfluenz",
            maerkte="BTC + ETH, Tageskerzen",
            trades=152,
            sharpe_je_trade=0.2597,
            noetiger_sharpe=0.2857,
            bestanden=7,
            gesamt=11,
            offen=("Messlatte", "Deflated Sharpe"),
            versuche=203,
            cagr_pct=13.47,
            rueckgang_pct=10.64,
        ).bericht()

    def test_die_marke_steht_neben_jeder_frage(self) -> None:
        """Im Bericht und nicht nur im Objekt - sonst steht die Fundstelle
        da, wo sie niemand liest."""
        text = self._bericht()
        for e in ENTSCHEIDUNGEN:
            assert f"{e.frage}  ({e.stelle})" in text, e.frage

    def test_auch_die_neue_entscheidung_steht_drin(self) -> None:
        assert "Neues Hoch im Takt" in self._bericht()
