"""Was muesste ein neuer Einfall koennen - und ist je etwas so weit gekommen?

Die gemessene Lage der Spitzengruppe:

    Kandidat                            Trades   Sharpe je Trade
    Trend-Beteiligung (fair gerechnet)      46            0,3583
    Trend mit Vola-Ziel 22 %                51            0,3559
    Trend 50 Tage mit Konfluenz            152            0,2597   <- Kandidat

Der Spitzenkandidat hat die schlechteste Qualitaet je Trade und kommt trotzdem
am weitesten, weil er dreimal so oft handelt. Genau deshalb ist weder die
Trade-Zahl noch der Sharpe allein ein Massstab - nur die Linie aus beiden.

Zwei Tests tragen die Datei:

* ``test_naechster_geht_nach_faktor_nicht_nach_differenz`` - eine Luecke von
  0,05 wiegt bei einem Sharpe von 0,25 schwerer als bei 0,8.
* ``test_zu_wenige_trades_sind_unerreichbar`` - bei kleinen Stichproben
  genuegt **kein** Sharpe. Das als "sehr grosse Luecke" auszuweisen waere
  falsch; es ist eine andere Aussage.
"""

from __future__ import annotations

import pytest

from research.suchbudget import Budget, Kandidat


def _budget(*kandidaten: Kandidat, versuche: int = 112) -> Budget:
    return Budget(versuche=versuche, kandidaten=list(kandidaten))


class TestLinie:
    def test_mehr_trades_verlangen_weniger_qualitaet(self) -> None:
        b = _budget()

        werte = [w for _, w in b.linie((50, 100, 200, 400)) if w is not None]

        assert len(werte) >= 3
        assert werte == sorted(werte, reverse=True)

    def test_mehr_versuche_heben_die_linie(self) -> None:
        """**Der Kern der ganzen Rechnung.**

        Gesucht wird gegen ein Ziel, das sich beim Suchen entfernt.
        """
        b = _budget()

        jetzt = b.noetig_bei(152)
        spaeter = b.noetig_bei(152, versuche=b.versuche + 100)

        assert jetzt is not None and spaeter is not None
        assert spaeter > jetzt

    def test_preis_eines_einfalls_ist_positiv(self) -> None:
        b = _budget()

        preis = b.kosten_je_versuch(152)

        assert preis is not None and preis > 0

    def test_tabelle_nennt_unerreichbares_als_solches(self) -> None:
        b = _budget()

        text = b.tabelle(trades=(3, 152))

        assert "unerreichbar" in text
        assert "152" in text


class TestAbstand:
    def test_gemessene_lage_des_spitzenkandidaten(self) -> None:
        """152 Trades zu je 0,2597 - noetig sind rund 0,28."""
        b = _budget(Kandidat("Trend 50 Tage mit Konfluenz", 152, 0.2597))

        (a,) = b.abstaende()

        assert a.erreichbar
        assert a.noetig is not None
        assert 0.26 < a.noetig < 0.31, f"gemessen {a.noetig}"
        assert a.luecke is not None and a.luecke > 0
        assert a.faktor is not None and 1.0 < a.faktor < 1.3

    def test_naechster_geht_nach_faktor_nicht_nach_differenz(self) -> None:
        """**Eine Luecke von 0,05 wiegt nicht ueberall gleich.**

        Der Kandidat mit der kleineren absoluten Luecke ist nicht der naehere,
        wenn seine Qualitaet je Trade viel niedriger liegt.
        """
        b = _budget(
            Kandidat("Wenig Trades, hoher Sharpe", 50, 0.60),
            Kandidat("Viele Trades, mittlerer Sharpe", 152, 0.2597),
        )

        nah = b.naechster

        assert nah is not None
        # Welcher gewinnt, entscheidet der Faktor - und der wird hier geprueft,
        # nicht behauptet.
        faktoren = {a.kandidat.name: a.faktor for a in b.abstaende()}
        bester = min(
            (n for n, f in faktoren.items() if f is not None),
            key=lambda n: faktoren[n],
        )
        assert nah.kandidat.name == bester

    def test_zu_wenige_trades_sind_unerreichbar(self) -> None:
        """Bei kleinen Stichproben genuegt **kein** Sharpe - das ist eine
        andere Aussage als 'sehr weit weg'."""
        b = _budget(Kandidat("Fast nie", 4, 0.9))

        (a,) = b.abstaende()

        assert not a.erreichbar
        assert a.luecke is None
        assert a.faktor is None

    def test_urteil_nennt_die_unerreichbaren(self) -> None:
        b = _budget(
            Kandidat("Fast nie", 4, 0.9),
            Kandidat("Kandidat", 152, 0.2597),
        )

        text = b.urteil()

        assert "kein** Sharpe genuegen" in text
        assert "Kandidat" in text

    def test_urteil_nennt_den_preis_des_suchens(self) -> None:
        b = _budget(Kandidat("Kandidat", 152, 0.2597))

        assert "entfernt" in b.urteil()

    def test_ohne_kandidaten(self) -> None:
        assert "kein Urteil" in Budget(versuche=112).urteil()

    def test_alle_unerreichbar(self) -> None:
        b = _budget(Kandidat("a", 3, 0.5), Kandidat("b", 4, 0.5))

        assert b.naechster is None
        assert "ueberhaupt erreichbar" in b.urteil()


class TestSpitzengruppe:
    def test_wenige_gute_trades_reichen_nicht_gegen_viele_mittlere(self) -> None:
        """**Die Form des Befunds.**

        0,3583 bei 46 Trades ist je Trade klar besser als 0,2597 bei 152 - und
        trotzdem weiter vom Gate entfernt.
        """
        b = _budget(
            Kandidat("Trend-Beteiligung (fair gerechnet)", 46, 0.3583),
            Kandidat("Trend 50 Tage mit Konfluenz", 152, 0.2597),
        )

        nach_name = {a.kandidat.name: a for a in b.abstaende()}
        wenige = nach_name["Trend-Beteiligung (fair gerechnet)"]
        viele = nach_name["Trend 50 Tage mit Konfluenz"]

        assert wenige.kandidat.sharpe_je_trade > viele.kandidat.sharpe_je_trade
        if wenige.faktor is not None and viele.faktor is not None:
            assert viele.faktor < wenige.faktor
        else:
            assert wenige.faktor is None  # noch schlimmer: gar nicht erreichbar

    def test_schiefe_und_woelbung_gehen_ein(self) -> None:
        """Eine Normalverteilung anzunehmen waere hier deutlich zu freundlich."""
        normal = Budget(versuche=112, schiefe=0.0, woelbung=3.0)
        echt = Budget(versuche=112)

        a = normal.noetig_bei(152)
        b = echt.noetig_bei(152)

        assert a is not None and b is not None
        assert a != pytest.approx(b)
