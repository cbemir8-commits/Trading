"""Der Auftrag in Genom-Groessen - Befund 432.

Der Auftrag an die Research-KI nennt Trade-Zahl und Sharpe je Trade. **Beides
kann der Empfaenger nicht einstellen**: Er fuellt ``stop``, ``targets``,
``cooldown_bars`` und ``max_hold_bars`` aus. Nachgezaehlt im Auftragstext
standen 'Haltedauer', 'max_hold', 'Bruttobewegung' und 'Gebuehr' je **0x**.

Hier wird geprueft, dass die Umrechnung stimmt, dass sie im Auftrag landet und
dass sie die zwei Verwechslungen benennt, die moeglich sind: Partner gegen
Alleingang, und Takt gegen Haltedauer-Deckel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.auftragstakt import Takt, als_auftrag, rechne
from research.datenstand import GEMEINSAME_TAGE
from research.vorteilsscan import KOSTEN_MAKER_MAKER


def _reihe(n: int = 4000, sigma: float = 0.02) -> pd.DataFrame:
    schritt = np.random.default_rng(11).normal(0, sigma, n)
    close = np.exp(np.cumsum(schritt)) * 100
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2012-01-01", periods=n, freq="D", tz="UTC"),
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.ones(n),
            "turnover": np.ones(n),
        }
    )


class TestDerTaktKommtAusDenGemeinsamenTagen:
    def test_er_teilt_die_gemeinsamen_tage(self) -> None:
        """**Nicht die Reihenlaenge** (Befund 318): BTC reicht 2054 Tage
        weiter zurueck als ETH, und der Korb kann den Vorlauf nicht nutzen."""
        stufen = rechne(_reihe(), ziele=(161,), versuche=203)

        assert len(stufen) == 1
        assert stufen[0].takt_tage == pytest.approx(GEMEINSAME_TAGE / 161)

    def test_die_reihenlaenge_aendert_ihn_nicht(self) -> None:
        kurz = rechne(_reihe(1500), ziele=(161,), versuche=203)
        lang = rechne(_reihe(4000), ziele=(161,), versuche=203)

        assert kurz[0].takt_tage == lang[0].takt_tage

    def test_mehr_trades_heisst_dichterer_takt(self) -> None:
        stufen = rechne(_reihe(), ziele=(146, 161, 185), versuche=203)
        takte = [s.takt_tage for s in stufen]

        assert takte == sorted(takte, reverse=True)

    def test_unsinnige_ziele_fallen_weg(self) -> None:
        """Eine Trade-Zahl von null oder darunter ergibt keinen Takt - sie
        darf nicht als Stufe mitzaehlen."""
        stufen = rechne(_reihe(), ziele=(0, -5, 161), versuche=203)

        assert [s.trades for s in stufen] == [161]


class TestDieBruttobewegungIstGemessen:
    def test_sie_ist_streuung_mal_noetigem_sharpe(self) -> None:
        stufen = rechne(_reihe(), ziele=(161,), versuche=203)
        s = stufen[0]

        assert s.brutto_pct == pytest.approx(s.noetiger_sharpe * s.streuung_pct)

    def test_eine_unruhigere_reihe_verlangt_mehr_brutto(self) -> None:
        """Gegenprobe gegen eine hingeschriebene Zahl: Die Streuung wird aus
        den Kerzen gemessen, also muss sie mit ihnen wandern."""
        ruhig = rechne(_reihe(sigma=0.01), ziele=(161,), versuche=203)
        wild = rechne(_reihe(sigma=0.04), ziele=(161,), versuche=203)

        assert wild[0].streuung_pct > ruhig[0].streuung_pct
        assert wild[0].brutto_pct > ruhig[0].brutto_pct

    def test_mehr_versuche_heben_die_anforderung(self) -> None:
        """Jeder Versuch hebt die Latte (Befund 232) - auch diese."""
        wenig = rechne(_reihe(), ziele=(161,), versuche=203)
        viel = rechne(_reihe(), ziele=(161,), versuche=1000)

        assert viel[0].noetiger_sharpe > wenig[0].noetiger_sharpe


class TestDieGebuehrRedetHierNichtMit:
    def test_der_anteil_ist_kosten_durch_brutto(self) -> None:
        t = Takt(
            trades=161, takt_tage=20.5, streuung_pct=24.5,
            noetiger_sharpe=0.2911, brutto_pct=7.13,
        )

        assert t.gebuehr_anteil == pytest.approx(KOSTEN_MAKER_MAKER / 7.13)
        assert not t.gebuehr_traegt

    def test_bei_winziger_bewegung_redet_sie_mit(self) -> None:
        """Die Gegenprobe, ohne die 'kein Faktor' nichts behauptet: Auf
        Viertelstundenkerzen ist die verlangte Bewegung klein, und dort
        kippt das Urteil - genau die Kreuzung, die 'taktung' rechnet."""
        t = Takt(
            trades=10_000, takt_tage=0.33, streuung_pct=0.4,
            noetiger_sharpe=0.08, brutto_pct=0.032,
        )

        assert t.gebuehr_traegt

    def test_auf_der_echten_groessenordnung_traegt_sie_nicht(self) -> None:
        stufen = rechne(_reihe(), ziele=(146, 161, 185), versuche=203)

        assert all(not s.gebuehr_traegt for s in stufen), [
            s.gebuehr_anteil for s in stufen
        ]


class TestWasImAuftragLandet:
    def _text(self) -> str:
        stufen = rechne(_reihe(), ziele=(146, 161, 185), versuche=203)
        return als_auftrag(stufen, ziel_trades=161)

    def test_er_nennt_die_felder_die_der_empfaenger_setzt(self) -> None:
        """Der Punkt des Befundes: Trade-Zahl und Sharpe sind Ergebnisse."""
        text = self._text()

        for feld in ("stop", "targets", "cooldown_bars", "max_hold_bars"):
            assert feld in text, feld
        assert "Ergebnisse" in text

    def test_er_nennt_takt_und_bruttobewegung(self) -> None:
        text = self._text()

        assert "Takt: ein Trade alle" in text
        assert "Bruttobewegung: rund" in text

    def test_er_warnt_dass_ein_deckel_keine_trades_bringt(self) -> None:
        """Befund 416: Sechs Deckel, Trade-Zahl bleibt 156 bis 158. Ohne
        diese Warnung liest sich der Takt als Bauanleitung fuer
        'max_hold_bars'."""
        text = self._text()

        assert "bringt keine Trades" in text
        assert "156 und 158" in text
        assert "oefter ausloest" in text

    def test_er_trennt_partner_von_alleingang(self) -> None:
        """Die Verwechslung, die mir in diesem Befund selbst unterlaufen
        ist - sie macht den Partner rechnerisch zu leicht."""
        text = self._text()

        assert "allein" in text.lower()
        assert "Partner" in text
        assert "Verwechsle die beiden nicht" in text

    def test_ohne_stufen_bleibt_er_leer(self) -> None:
        """Ein Auftragsabschnitt ohne Zahlen sieht wie eine Anforderung aus
        und ist keine."""
        assert als_auftrag((), ziel_trades=161) == ""


class TestDerAuftragRuftIhnAuf:
    """Gebaut und nicht verdrahtet ist der Fehler, den dieses Register oft
    genug verzeichnet - hier gleich an drei Stellen."""

    def test_build_prompt_nimmt_ihn(self) -> None:
        import inspect

        from research.analyst import build_prompt

        quelle = inspect.getsource(build_prompt)

        assert "takt: str = \"\"" in quelle or "takt: str = ''" in quelle
        assert "parts.append(takt)" in quelle

    def test_propose_gibt_ihn_weiter(self) -> None:
        import inspect

        from research.analyst import propose

        assert "takt=takt," in inspect.getsource(propose)

    def test_und_die_cli_rechnet_ihn_an_jeder_stelle(self) -> None:
        """Drei Stellen, und '--auftrag' ist die wichtigste: Wer sich den
        Auftrag anzeigen laesst, muss den sehen, der gestellt wird."""
        from pathlib import Path

        quelle = Path("cli.py").read_text()

        assert quelle.count("takt=_auftragstakt(lage, settings)") == 3

    def test_ohne_speicher_bleibt_der_auftrag_der_alte(self) -> None:
        """Gesetzte Zahlen waeren schlechter als keine."""
        import inspect

        import cli

        quelle = inspect.getsource(cli._auftragstakt)

        assert 'return ""' in quelle
        assert "frame.empty" in quelle
