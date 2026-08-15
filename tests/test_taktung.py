"""Die Huerde in Bruttobewegung je Trade - und wo die Gebuehr sie einholt.

Zwei Tests tragen diese Datei:

``test_die_streuung_wird_gemessen_nicht_hochgerechnet`` - Die uebliche
Abkuerzung waere, die Tagesstreuung mit der Wurzel der Zeit zu skalieren. Das
setzt Unabhaengigkeit voraus, die bei Kursen nicht gegeben ist, und liefert
fuer kurze Haltedauern zu kleine Zahlen - also eine zu optimistische Rechnung.

``test_die_gebuehr_holt_den_vorteil_ein`` - Der eigentliche Punkt des Moduls.
Der noetige Vorteil faellt mit ``1/sqrt(N)``, die Gebuehr bleibt konstant.
Wenn der Kostenanteil mit der Trade-Zahl nicht steigt, misst dieses Modul
nichts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.taktung import KOSTEN_PCT, Stufe, Taktung, rechne, streuung_je_trade


def reihe(n: int, *, schritt: float = 0.01, saat: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(saat)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0, schritt, n)))
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2020-03-30", periods=n, freq="15min"),
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": np.full(n, 5.0),
        }
    )


class TestStreuung:
    def test_die_streuung_wird_gemessen_nicht_hochgerechnet(self) -> None:
        """**Der Test, der die Rechnung ehrlich haelt.**

        Bei einer Reihe ohne Struktur waechst die Streuung mit der Wurzel der
        Haltedauer - das ist der Fall, in dem die Abkuerzung stimmt. Sie muss
        also aus der Messung *herauskommen*, statt hineingesteckt zu werden;
        bei echten Kursen weicht sie dann davon ab, und genau das soll sie.
        """
        frame = reihe(20_000)

        eins = streuung_je_trade(frame, kerzen=1)
        vier = streuung_je_trade(frame, kerzen=4)

        assert vier == np.float64(vier)
        assert 1.7 * eins < vier < 2.3 * eins, (
            f"Ueber vier Kerzen erwartet man rund das Doppelte: {vier:.3f} "
            f"gegen {eins:.3f}"
        )

    def test_eine_zu_kurze_reihe_gibt_null(self) -> None:
        assert streuung_je_trade(reihe(10), kerzen=50) == 0.0

    def test_null_kerzen_kippen_nicht(self) -> None:
        assert streuung_je_trade(reihe(100), kerzen=0) == 0.0


class TestStufe:
    def test_der_noetige_vorteil_ist_ein_vielfaches_der_streuung(self) -> None:
        stufe = Stufe(trades=150, noetiger_sharpe=0.3, streuung_pct=3.0)

        assert stufe.noetig_brutto_pct == 0.8999999999999999
        assert stufe.noetig_mit_kosten_pct == 0.8999999999999999 + KOSTEN_PCT

    def test_die_gebuehr_holt_den_vorteil_ein(self) -> None:
        """**Der Test, um den es in diesem Modul geht.**

        Der noetige Vorteil faellt mit der Wurzel der Trade-Zahl, die Gebuehr
        bleibt gleich. Der Kostenanteil muss deshalb mit mehr Trades steigen -
        wenn nicht, misst das Modul nichts.
        """
        wenige = Stufe(trades=150, noetiger_sharpe=0.36, streuung_pct=0.8)
        viele = Stufe(trades=10_000, noetiger_sharpe=0.043, streuung_pct=0.8)

        assert wenige.kostenanteil < viele.kostenanteil
        assert wenige.traegt, "0,29 % noetig gegen 0,04 % Gebuehr - reichlich Luft"
        assert not viele.traegt, (
            "0,034 % noetig gegen 0,04 % Gebuehr - die Boerse bekommt die "
            "Mehrheit"
        )

    def test_ein_unerreichbarer_sharpe_liefert_keine_zahlen(self) -> None:
        stufe = Stufe(trades=10, noetiger_sharpe=None, streuung_pct=3.0)

        assert stufe.noetig_brutto_pct is None
        assert stufe.kostenanteil is None
        assert not stufe.traegt


class TestTaktung:
    def taktung(self, *, kerzen: int, haltedauer: int, streuung: float) -> Taktung:
        return Taktung(
            name="Test",
            kerzen_gesamt=kerzen,
            haltedauer=haltedauer,
            streuung_pct=streuung,
            versuche=166,
            stufen=[
                Stufe(trades=150, noetiger_sharpe=0.3606, streuung_pct=streuung),
                Stufe(trades=10_000, noetiger_sharpe=0.0435, streuung_pct=streuung),
            ],
        )

    def test_was_nicht_in_die_historie_passt_zaehlt_nicht(self) -> None:
        """Eine Trade-Zahl, die mehr Kerzen braucht als vorhanden sind, ist
        keine Option - auch wenn ihre Arithmetik guenstig aussaehe."""
        eng = self.taktung(kerzen=3000, haltedauer=40, streuung=3.0)

        assert eng.hoechstens_trades == 75
        assert eng.machbar == []
        assert "Keine Stufe passt" in eng.urteil()

    def test_gemeldet_wird_die_groesste_tragfaehige_stufe(self) -> None:
        """**Nicht die bequemste.**

        Der erste Anlauf nahm die Stufe mit dem kleinsten Kostenanteil - und
        das ist immer die mit den wenigsten Trades. Damit meldete die Rechnung
        ausgerechnet den Punkt, um den es nicht geht: Der Sinn ist zu pruefen,
        ob **viele** Trades tragen, denn dort ist der noetige Vorteil je Trade
        am kleinsten.
        """
        weit = self.taktung(kerzen=222_700, haltedauer=16, streuung=1.2)

        assert weit.bestes is not None
        assert weit.bestes.trades == 10_000, "Die groesste, nicht die kleinste"
        urteil = weit.urteil()
        assert "tragfaehig bis 10000 Trades" in urteil
        assert "nicht, dass dieser Vorteil existiert" in urteil
        assert "ein Korb bringt mehr mit" in urteil

    def test_wenn_die_gebuehr_frisst_steht_es_da(self) -> None:
        """Bei winziger Streuung wird der noetige Vorteil so klein, dass die
        feste Gebuehr ihn ueberwiegt."""
        duenn = self.taktung(kerzen=222_700, haltedauer=16, streuung=0.05)

        assert duenn.bestes is None, "Keine Stufe traegt - also gibt es keine beste"
        assert duenn.machbar, "Passen tun sie trotzdem, sie lohnen nur nicht"
        urteil = duenn.urteil()
        assert "Gebuehr frisst den Vorteil" in urteil
        assert "auf die Boerse zu wetten" in urteil
        assert "guenstigsten passenden Stelle" in urteil

    def test_die_tabelle_zeigt_was_hineinpasst(self) -> None:
        eng = self.taktung(kerzen=3000, haltedauer=40, streuung=3.0)
        text = eng.tabelle()

        assert "nein" in text
        assert "10000" in text


class TestRechne:
    def test_sie_setzt_alles_zusammen(self) -> None:
        taktung = rechne(
            reihe(50_000), name="15m", haltedauer=16, versuche=166,
            trade_zahlen=(150, 2000),
        )

        assert taktung.kerzen_gesamt == 50_000
        assert taktung.streuung_pct > 0
        assert [s.trades for s in taktung.stufen] == [150, 2000]
        assert all(s.streuung_pct == taktung.streuung_pct for s in taktung.stufen)

    def test_ohne_stufen_wird_nichts_behauptet(self) -> None:
        leer = rechne(
            reihe(1000), name="x", haltedauer=4, versuche=166, trade_zahlen=()
        )

        assert "Keine Stufen gerechnet" in leer.urteil()
