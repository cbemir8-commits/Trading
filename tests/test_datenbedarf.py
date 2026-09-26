"""Wie viel Historie dem Deflated Sharpe fehlt - Befund 344.

``cli abstand`` gibt seit Befund 139 zwei Zeilen aus: *"Mehr Daten kosten keinen
Versuch, eine neue Idee schon. Erst die Datenbasis ausschoepfen, dann suchen."*
Das liest sich wie eine Aufgabe, die man erledigen kann.

Gerechnet ist es eine Aussage darueber, ob das geht:

    wirksame Trades heute      115 von 156 rohen   73,7 %
    wirksame noetig            191
    rohe dafuer                260                 es fehlen 104
    Rate                       17,3 Trades im Jahr (156 auf 3300 Tagen)
    zusaetzliche Historie      2200 Tage           sechs Jahre

Und die Richtung zaehlt: Der gemeinsame Anfang liegt bei 2017-08-16 und ist von
ETH gesetzt. Die 2054 zusaetzlichen Tage von BTC kann ein Portfolio-Backtest
nicht nutzen, und BTC allein steht schlechter (Befund 318). Bleibt die Zeit nach
vorn.

**Damit ist "erst die Datenbasis ausschoepfen" erledigt und nicht offen.** Der
Weg zum Gate fuehrt ueber die Guete je Trade (0,337 noetig, 0,271 da) oder ueber
eine Geschaeftsentscheidung.
"""

from __future__ import annotations

from datetime import date

import pytest

from research.datenbedarf import Datenbedarf, bedarf

#: Der Stand am Spot-Punkt (Befund 344).
ROH = 156
EFFEKTIV = 115
NOETIG = 191
SPANNE = 3300
ANFAENGE = {
    "BTCUSD_BITSTAMP": date(2012, 1, 1),
    "ETHUSD_BITSTAMP": date(2017, 8, 16),
}


def _heute() -> Datenbedarf:
    return bedarf(
        roh=ROH,
        effektiv=EFFEKTIV,
        noetig_effektiv=NOETIG,
        spanne_tage=SPANNE,
        anfaenge=ANFAENGE,
    )


class TestDieRechnung:
    def test_das_verhaeltnis_ist_gemessen_und_nicht_gesetzt(self) -> None:
        assert _heute().verhaeltnis == pytest.approx(115 / 156, abs=1e-9)
        assert _heute().verhaeltnis == pytest.approx(0.737, abs=0.001)

    def test_die_rohen_trades_werden_aufgerundet(self) -> None:
        """Ein halber Trade ist keiner - und nach unten zu runden machte die
        Huerde kleiner, als sie ist."""
        lage = _heute()

        assert lage.noetig_roh == 260
        assert lage.fehlende_roh == 104

    def test_die_rate_kommt_aus_der_vorhandenen_reihe(self) -> None:
        lage = _heute()

        assert lage.rate_je_tag == pytest.approx(156 / 3300, abs=1e-9)
        assert lage.rate_je_jahr == pytest.approx(17.3, abs=0.05)

    def test_sechs_jahre(self) -> None:
        lage = _heute()

        assert lage.noetige_tage == 2200
        assert lage.noetige_jahre == pytest.approx(6.0, abs=0.05)

    def test_die_ungenutzten_tage_des_laengeren_beins(self) -> None:
        lage = _heute()

        assert lage.anfang == date(2017, 8, 16)
        assert lage.gesetzt_von == "ETHUSD_BITSTAMP"
        assert lage.rueckwaerts_tage == 2054

    def test_ohne_anfaenge_gibt_es_keine_richtung(self) -> None:
        """Keine erfundene Null: Ohne Anfangsdaten steht dazu nichts."""
        lage = bedarf(
            roh=ROH, effektiv=EFFEKTIV, noetig_effektiv=NOETIG, spanne_tage=SPANNE
        )

        assert lage.anfang is None
        assert lage.rueckwaerts_tage == 0
        assert "Rueckwaerts" not in lage.bericht()


class TestDerBericht:
    def test_er_nennt_die_jahre_und_die_annahme(self) -> None:
        text = _heute().bericht()

        assert "2200 Tage, 6.0 Jahre" in text
        assert "unveraenderter Guete und stehendem Versuchszaehler" in text
        assert "Befund 327" in text

    def test_er_nennt_die_gesperrte_richtung(self) -> None:
        text = _heute().bericht()

        assert "Rueckwaerts ist sie nicht zu holen" in text
        assert "2054 Tage" in text
        assert "Befund 318" in text

    def test_bei_reichender_stichprobe_sagt_er_das(self) -> None:
        lage = bedarf(
            roh=300, effektiv=220, noetig_effektiv=191, spanne_tage=SPANNE,
            anfaenge=ANFAENGE,
        )

        assert lage.reicht
        assert "Die Stichprobe reicht" in lage.bericht()
        assert "Rueckwaerts" not in lage.bericht()

    def test_wenn_keine_zahl_genuegt_sagt_er_das_auch(self) -> None:
        """``noetige_trades`` gibt ``None``, wenn der Vorteil je Trade zu klein
        ist. Dann ist mehr Historie keine Antwort, und das gehoert gesagt."""
        lage = bedarf(
            roh=ROH, effektiv=EFFEKTIV, noetig_effektiv=None, spanne_tage=SPANNE,
            anfaenge=ANFAENGE,
        )

        assert lage.noetig_roh is None
        assert lage.noetige_tage is None
        assert "Keine Trade-Zahl genuegt" in lage.bericht()


class TestUnsinnWirdAbgewiesen:
    def test_mehr_wirksame_als_rohe_trades(self) -> None:
        """Die sichere Richtung: Ein Tippfehler in der Reihenfolge der
        Argumente wuerde sonst eine kleinere Huerde ausrechnen."""
        with pytest.raises(ValueError, match="unabhaengiger als einzeln"):
            Datenbedarf(
                roh=115, effektiv=156, noetig_effektiv=191, spanne_tage=SPANNE
            )

    def test_negative_zahlen(self) -> None:
        with pytest.raises(ValueError, match="nicht negativ"):
            Datenbedarf(roh=-1, effektiv=0, noetig_effektiv=None, spanne_tage=1)

    def test_negative_spanne(self) -> None:
        with pytest.raises(ValueError, match="nicht negativ"):
            Datenbedarf(roh=1, effektiv=1, noetig_effektiv=None, spanne_tage=-1)

    def test_ohne_trades_gibt_es_kein_verhaeltnis(self) -> None:
        lage = Datenbedarf(
            roh=0, effektiv=0, noetig_effektiv=191, spanne_tage=SPANNE
        )

        assert lage.verhaeltnis is None
        assert lage.noetig_roh is None
        assert lage.rate_je_tag == 0.0


class TestDerBefehlRechnetEsMit:
    """Befund 152, 154, 155, 160, 325, 330, 337, 338, 339 und 342 waren
    dieselbe Bauart: gebaut, gerechnet, nicht angeschlossen."""

    @staticmethod
    def _quelle(name: str) -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == name
        )

    def test_abstand_gibt_den_bedarf_aus(self) -> None:
        quelle = self._quelle("abstand")

        assert "from research.datenbedarf import bedarf" in quelle
        assert "lage_daten.bericht()" in quelle

    def test_er_nimmt_die_zahlen_des_gates(self) -> None:
        """``stichprobe.roh`` und ``n`` sind die, mit denen das Gate rechnet -
        eine eigene Zaehlung waere eine zweite Wahrheit (Befund 139)."""
        quelle = self._quelle("abstand")

        assert "roh=stichprobe.roh" in quelle
        assert "effektiv=n" in quelle
        assert "noetig_effektiv=ergebnis.trades_noetig" in quelle

    def test_die_anfaenge_kommen_vor_dem_schnitt(self) -> None:
        """``_korb_daten`` schneidet auf die gemeinsame Spanne - danach waere
        die Frage nach dem laengeren Bein nicht mehr zu stellen."""
        quelle = self._quelle("abstand")

        assert "_anfaenge(symbole, interval_obj, settings)" in quelle


class TestDerRegistereintrag:
    @staticmethod
    def _eintrag():
        from research.stand import GESCHLOSSEN

        return next(r for r in GESCHLOSSEN if r.name == "Mehr Historie")

    def test_die_zahl_steht_jetzt_drin(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "104 rohe Trades fehlen" in ergebnis
        assert "sechs Jahre" in ergebnis

    def test_die_gesperrte_richtung_steht_drin(self) -> None:
        ergebnis = self._eintrag().ergebnis

        assert "rueckwaerts nichts zu holen" in ergebnis
        assert "ETH setzt den Anfang" in ergebnis

    def test_der_schluss_steht_drin(self) -> None:
        """Der Punkt, um den es geht: 'Erst die Datenbasis ausschoepfen' ist
        keine offene Aufgabe mehr."""
        ergebnis = self._eintrag().ergebnis

        assert "Die Datenseite ist damit ausgeschoepft" in ergebnis

    def test_der_eintrag_bleibt_eine_zeile(self) -> None:
        """**Die Lehre aus dem ersten Anlauf.** Diesen Befund hatte ich als
        872 Zeichen in 'GESCHLOSSEN' geschrieben - eine Liste, deren Median bei
        48 liegt und die Befund 274 gegen genau das abgesichert hat. Die
        Ausfuehrung gehoert ins Laborbuch, hier steht das Stichwort mit seiner
        Zahl."""
        assert len(self._eintrag().ergebnis) <= 300

    def test_der_alte_befund_bleibt_stehen(self) -> None:
        """Die Erstmessung wird nicht ueberschrieben - sie ist der Grund,
        warum die Richtung geschlossen ist."""
        ergebnis = self._eintrag().ergebnis

        assert ergebnis.startswith("Guete flach ueber sechs Fenster")

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 14
        assert eintrag.massgeblich == 344


@pytest.mark.daten
@pytest.mark.langsam
def test_die_zahlen_stimmen_am_spot_punkt() -> None:
    """**Die Bindung.** Sechs Jahre sind eine Aussage ueber das Projekt, und
    sie steht auf drei gemessenen Groessen. Bewegt sich eine davon, soll dieser
    Test es sagen und nicht der Registereintrag stillschweigend veralten.
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.admission import load_trials
    from research.erreichbarkeit import bewerte, kennzahlen_aus_pnl
    from research.gates import stichprobe_wie_im_gate
    from research.randschnitt import ohne_zensierte
    from research.seeds import spitzenkandidat
    from strategy.compiler import compile_genome

    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    e = get_settings()
    versuche = load_trials(Path(e.paths.state) / "trials.json")
    frames, _, _ = cli._korb_daten(symbole, Interval("D"), e)
    configs = cli._spotconfigs(symbole, e)
    genom = cli._ohne_hebel(spitzenkandidat())
    bericht = run_portfolio_walkforward(
        frames, lambda g=genom: compile_genome(g), configs
    )
    gehandelt = ohne_zensierte(bericht)
    _, sharpe, schiefe, woelbung = kennzahlen_aus_pnl(
        [t.net_pnl for t in gehandelt.all_trades]
    )
    stichprobe = stichprobe_wie_im_gate(
        gehandelt.all_trades,
        beine=getattr(bericht, "beine", None),
        bloecke=[[float(x.net_pnl) for x in w.trades] for w in gehandelt.windows],
    )
    lage = bewerte(
        trades=stichprobe.effektiv,
        sharpe=sharpe,
        trials=versuche,
        skew=schiefe,
        kurtosis=woelbung,
    )
    gemeinsam = next(iter(frames.values()))
    gemessen = bedarf(
        roh=stichprobe.roh,
        effektiv=stichprobe.effektiv,
        noetig_effektiv=lage.trades_noetig,
        spanne_tage=(
            gemeinsam["open_time"].max() - gemeinsam["open_time"].min()
        ).days,
        anfaenge=cli._anfaenge(symbole, Interval("D"), e),
    )

    assert gemessen.roh == ROH
    assert gemessen.effektiv == EFFEKTIV
    assert gemessen.noetig_effektiv == NOETIG
    assert gemessen.spanne_tage == SPANNE
    assert gemessen.fehlende_roh == 104
    assert gemessen.noetige_jahre == pytest.approx(6.0, abs=0.1)

    # Und die Richtung: ETH setzt den Anfang, BTC reicht weiter zurueck.
    assert gemessen.gesetzt_von == "ETHUSD_BITSTAMP"
    assert gemessen.rueckwaerts_tage == 2054
    assert not gemessen.reicht
