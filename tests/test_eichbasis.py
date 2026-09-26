"""Woran die Eichung der Latte haengt - Befund 343.

Achter und letzter Verdachtsfall aus der Wache von Befund 335: **'Was die Latte
des Deflated Sharpe bedeutet'**, Fundstelle Befund 278 - die einzige
Entscheidung, die seit ihrer Erstmessung nie wieder angesehen worden war. Und
sie steht auf dem Gate, das die Zulassung allein blockiert.

**Der Schluss haelt.** Die tragenden Zeilen kommen auf die Stelle wieder:

    Versuche   95. Perzentil   Fehlalarm bei 0,95   DSR Bestand   Perzentil
         203          0,3059   kein Lauf von 5000        0,5826       99,86
         230          0,2949   kein Lauf von 5000        0,5551       99,86

**Zwei Stellen nicht.** Die Einzelversuchszeile liefert heute 0,9307 und 3,200 %
statt 0,9305 und 3,36 %; bei zehn Versuchen 0,6262 statt 0,6275. Die Saat ist
**fest** - also ist das kein Zufall. Gezogen wird aus den Trades des Bestands,
und die Liste hat sich bewegt.

Gemessen (je ein Trade weniger, zehn Proben, feste Saat):

    95. Perzentil   0,9270 bis 0,9328   Spanne 0,0058
    Fehlalarm       2,880 bis 3,660 %   Spanne 0,78 Punkte = 24 % des Werts

Bei 203 und 230 Versuchen bleibt in **jeder** Probe "kein einziger Lauf" stehen.
Die groben Aussagen sind belastbar, die feinen sind Grundlage und nicht
Praezision.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.eichung import LAEUFE, SAAT, Nullverteilung, nullverteilung

#: Was 'cli abstand --spot --eichung' heute liefert (156 Trades, n_eff 115).
HEUTE: dict[int, tuple[float, bool]] = {
    # Versuche: 95. Perzentil, Fehlalarm > 0
    1: (0.9307, True),
    10: (0.6262, True),
    50: (0.4303, False),
    203: (0.3059, False),
    230: (0.2949, False),
}

#: Die Spanne, wenn ein Trade fehlt (Befund 343, zehn Proben).
SPANNE_PERZENTIL = 0.0058
SPANNE_FEHLALARM = 0.0078


def _null(werte: list[float], **rest) -> Nullverteilung:
    return Nullverteilung(
        werte=np.asarray(werte, dtype=float),
        versuche=rest.get("versuche", 203),
        stichprobe=rest.get("stichprobe", 115),
        roh=rest.get("roh", 156),
        latte=rest.get("latte", 0.95),
    )


class TestDieGrundlageStehtJetztDabei:
    """**Der Fund.** Die Saat ist fest, die Trade-Liste nicht - und sie stand
    nirgends."""

    def test_die_trade_zahl_wird_genannt(self) -> None:
        satz = _null([0.1, 0.2, 0.3], roh=156).grundlagensatz()

        assert "Gezogen aus 156 Trades des Bestands" in satz
        assert "fester Saat" in satz

    def test_bei_treffern_steht_die_genauigkeit_dabei(self) -> None:
        """Ein Fehlalarm ueber null ist die feine Zahl - und die wandert."""
        satz = _null([0.1, 0.96, 0.97], latte=0.95).grundlagensatz()

        assert "ein Viertel seines Werts" in satz
        assert "nicht Praezision" in satz

    def test_ohne_treffer_steht_die_belastbarkeit_dabei(self) -> None:
        """Die Gegenprobe: 'Kein einziger Lauf' haelt der Verschiebung stand,
        und das gehoert genauso gesagt."""
        satz = _null([0.1, 0.2, 0.3], latte=0.95).grundlagensatz()

        assert "grob und deshalb belastbar" in satz
        assert "ein Viertel" not in satz

    def test_beschreibe_traegt_den_satz_mit(self) -> None:
        """Gebaut, gerechnet, angeschlossen - die Bauart aus Befund 152 und
        Folgenden."""
        text = _null([0.1, 0.2, 0.3]).beschreibe()

        assert "Gezogen aus 156 Trades" in text
        assert "95. Perzentil dieser Nullverteilung" in text

    def test_die_saat_ist_fest_und_benannt(self) -> None:
        """Wenn die Saat wandert, ist jede Abweichung erklaerbar und keine
        Auskunft mehr."""
        assert SAAT == 278
        assert LAEUFE == 5_000


class TestDieZahlenHaengenAnDerListe:
    """Nicht behauptet: Dieselbe Saat, dieselbe Laufzahl, eine andere Liste."""

    @staticmethod
    def _basis(n: int = 60) -> list[float]:
        streuung = np.random.default_rng(7).normal(0.0, 1.0, n)
        return [float(x) for x in streuung]

    def test_ein_trade_weniger_verschiebt_das_perzentil(self) -> None:
        basis = self._basis()
        voll = nullverteilung(basis, versuche=1, stichprobe=40, laeufe=400)
        ohne = nullverteilung(basis[:-1], versuche=1, stichprobe=40, laeufe=400)

        assert voll.roh == 60 and ohne.roh == 59
        assert voll.latte_fuer_fuenf_prozent != ohne.latte_fuer_fuenf_prozent

    def test_dieselbe_liste_gibt_dieselbe_zahl(self) -> None:
        """Die andere Haelfte der Aussage: Es ist die Liste und nicht der
        Zufall."""
        basis = self._basis()
        eins = nullverteilung(basis, versuche=1, stichprobe=40, laeufe=400)
        zwei = nullverteilung(basis, versuche=1, stichprobe=40, laeufe=400)

        assert eins.latte_fuer_fuenf_prozent == zwei.latte_fuer_fuenf_prozent
        assert eins.fehlalarm == zwei.fehlalarm

    def test_die_aufloesung_haengt_an_der_laufzahl(self) -> None:
        basis = self._basis()
        null = nullverteilung(basis, versuche=203, stichprobe=40, laeufe=400)

        assert null.aufloesung == pytest.approx(1 / 401)
        assert null.laeufe == 400

    def test_zu_wenige_trades_werden_abgewiesen(self) -> None:
        with pytest.raises(ValueError, match="Zu wenige Trades"):
            nullverteilung([0.1, 0.2], versuche=1, stichprobe=40)


class TestDerEintragIstNachgemessen:
    @staticmethod
    def _eintrag():
        from research.stand import ENTSCHEIDUNGEN

        return next(
            e for e in ENTSCHEIDUNGEN
            if e.frage == "Was die Latte des Deflated Sharpe bedeutet"
        )

    def test_der_schluss_ist_als_bestaetigt_benannt(self) -> None:
        """Gepruefte Zahlen, die stimmen, gehoeren genauso berichtet wie die,
        die nicht stimmten."""
        zahl = self._eintrag().zahl

        assert "Der Schluss haelt" in zahl
        assert "kein Lauf von 5.000" in zahl

    def test_die_zwei_abweichenden_stellen_stehen_da(self) -> None:
        zahl = self._eintrag().zahl

        assert "0,9307 und 3,200 %" in zahl
        assert "0,6262 statt 0,6275" in zahl

    def test_der_grund_ist_die_grundlage_und_nicht_der_zufall(self) -> None:
        zahl = self._eintrag().zahl

        assert "Saat ist fest" in zahl
        assert "kein Zufall" in zahl

    def test_die_gemessene_spanne_steht_dabei(self) -> None:
        zahl = self._eintrag().zahl

        assert "0,0058" in zahl
        assert "ein Viertel seines" in zahl

    def test_die_dritte_einschraenkung_ist_eingetragen(self) -> None:
        """Die Eichung ist eine Messung **an diesem Kandidaten** und keine
        Eigenschaft der Schwelle - das gehoert zu den Einschraenkungen."""
        warum = self._eintrag().warum

        assert "Eine dritte seit 343" in warum
        assert "keine Eigenschaft der Schwelle" in warum

    def test_die_entscheidung_bleibt_unberuehrt(self) -> None:
        warum = self._eintrag().warum

        assert "Geaendert wurde nichts" in warum
        assert "jede Probe\n              ueberlebt" in warum or (
            "jede Probe ueberlebt" in warum
        )

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 278
        assert eintrag.massgeblich == 343


class TestDieWacheAusBefund335IstDurch:
    """**Acht Nachmessungen, 336 bis 343.** Alle neun Entscheidungen mit
    Fundstelle tragen jetzt eine Messung von 330 oder spaeter."""

    @staticmethod
    def _mit_fundstelle():
        from research.stand import ENTSCHEIDUNGEN

        return [e for e in ENTSCHEIDUNGEN if e.befund]

    def test_keine_entscheidung_steht_mehr_auf_einer_alten_messung(self) -> None:
        """**Und das ist die Wache fuer kuenftige Eintraege**: Wer eine
        Entscheidung auf eine Messung von vor 330 stellt, misst sie nach oder
        sagt hier, warum nicht."""
        alt = sorted(
            (e.frage, e.massgeblich)
            for e in self._mit_fundstelle()
            if e.massgeblich < 330
        )

        assert alt == [], f"Entscheidung auf alter Messung: {alt}"

    def test_es_sind_neun(self) -> None:
        assert len(self._mit_fundstelle()) == 9

    def test_die_ohne_fundstelle_bleibt_draussen(self) -> None:
        from research.stand import ENTSCHEIDUNGEN

        ohne = [e.frage for e in ENTSCHEIDUNGEN if not e.befund]

        assert ohne == ["Wochenverlustgrenze"]


@pytest.mark.daten
@pytest.mark.langsam
def test_die_eichtafel_stimmt_und_ihre_feinen_stellen_wandern() -> None:
    """**Die Bindung.** Die Tafel stand in einem Registereintrag und nirgends
    in einem Test. Zwischen Befund 278 und heute haben sich zwei ihrer Zahlen
    bewegt, und niemand hat es gemerkt - obwohl die Saat fest ist.
    """
    import cli
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.gates import GateThresholds
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    frames, _, _ = cli._korb_daten(symbole, Interval("D"), e)
    configs = cli._spotconfigs(symbole, e)
    genom = cli._ohne_hebel(spitzenkandidat())
    bericht = run_portfolio_walkforward(
        frames, lambda g=genom: compile_genome(g), configs
    )
    # Der Befehl zieht aus den **gewerteten** Trades; zwei am Datenende
    # zaehlen in der Statistik nicht mit.
    grundlage = [float(t.net_pnl) for t in bericht.all_trades][:-2]
    latte = GateThresholds().min_deflated_sharpe

    assert len(grundlage) == 156

    for versuche, (perzentil, trifft) in HEUTE.items():
        null = nullverteilung(
            grundlage, versuche=versuche, stichprobe=115, latte=latte
        )

        assert null.roh == 156
        assert null.latte_fuer_fuenf_prozent == pytest.approx(
            perzentil, abs=0.0005
        ), versuche
        assert (null.fehlalarm > 0) is trifft, versuche

    # Und die Empfindlichkeit: ein Trade weniger, feste Saat.
    proben = [
        nullverteilung(
            grundlage[:i] + grundlage[i + 1 :],
            versuche=1,
            stichprobe=115,
            latte=latte,
        )
        for i in (0, 1, len(grundlage) - 2, len(grundlage) - 1)
    ]
    perzentile = [p.latte_fuer_fuenf_prozent for p in proben]
    fehlalarme = [p.fehlalarm for p in proben]
    voll = nullverteilung(grundlage, versuche=1, stichprobe=115, latte=latte)

    assert max(perzentile) - min(perzentile) > 0.001, (
        "die feinen Stellen sollen wandern - sonst waere der Befund falsch"
    )
    assert max(perzentile) - min(perzentile) <= SPANNE_PERZENTIL + 0.002
    assert (max(fehlalarme) - min(fehlalarme)) / voll.fehlalarm > 0.05
    assert max(fehlalarme) - min(fehlalarme) <= SPANNE_FEHLALARM + 0.002

    # Die tragende Zeile haelt jeder Probe stand.
    for i in (0, len(grundlage) - 1):
        null = nullverteilung(
            grundlage[:i] + grundlage[i + 1 :],
            versuche=203,
            stichprobe=115,
            latte=latte,
        )

        assert null.fehlalarm == 0.0, "'kein einziger Lauf' soll stehenbleiben"
