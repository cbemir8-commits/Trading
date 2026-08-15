"""Schockerkennung - und die eine Eigenschaft, ohne die sie wertlos waere.

``test_die_norm_kennt_die_kerze_nicht`` traegt diese Datei. Eine Norm, die die
aktuelle Kerze mitzaehlt, kennt den Schock bereits; ein zentriertes Fenster
kennt die Zukunft. Beides laeuft anstandslos durch und liefert bessere Zahlen,
als der Betrieb je erreichen kann - die teuerste Sorte Fehler, weil sie wie
ein Erfolg aussieht.

``test_kein_vorlauf`` ist der zweite: Ein Schock darf die Kerzen **davor**
nicht sperren. Genau das waere die Hellsicht, gegen die das ganze Modul
gebaut ist.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.schock import (
    Auszaehlung,
    gesperrt,
    schocks,
    wahre_spanne,
)


def reihe(spannen: list[float], *, start: float = 100.0) -> pd.DataFrame:
    """Kerzen mit vorgegebener Tagesspanne, Schluss jeweils in der Mitte."""
    schluss = np.full(len(spannen), start)
    halbe = np.array(spannen) / 2
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2021-01-01", periods=len(spannen), freq="D"),
            "open": schluss,
            "high": schluss + halbe,
            "low": schluss - halbe,
            "close": schluss,
            "volume": np.full(len(spannen), 10.0),
        }
    )


class TestWahreSpanne:
    def test_eine_luecke_zaehlt_mit(self) -> None:
        """Eine Kerze, die zehn Prozent tiefer eroeffnet und sich dann kaum
        bewegt, ist keine ruhige Kerze."""
        frame = pd.DataFrame(
            {
                "open_time": pd.date_range("2021-01-01", periods=2, freq="D"),
                "open": [100.0, 90.0],
                "high": [101.0, 90.5],
                "low": [99.0, 89.5],
                "close": [100.0, 90.0],
            }
        )

        spanne = wahre_spanne(frame)

        assert spanne[0] == 2.0
        assert spanne[1] == 10.5, "Luecke von 100 auf 90.5 statt nur 1.0 Spanne"


class TestSchocks:
    def test_die_norm_kennt_die_kerze_nicht(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Eine einzelne riesige Kerze in einer ruhigen Reihe muss als Schock
        gelten. Zaehlte die Norm sie mit, zoege sie den Median hoch und der
        Schock faende sich selbst nicht mehr - bei genug Schocks in Folge
        verschwaende die Erkennung ganz.
        """
        spannen = [1.0] * 40
        spannen[35] = 10.0
        treffer = schocks(reihe(spannen), fenster=30, faktor=3.0)

        assert treffer[35], "Zehnfache Spanne muss ein Schock sein"
        assert treffer.sum() == 1

    def test_die_norm_kennt_die_zukunft_nicht(self) -> None:
        """Ein Schock am Ende der Reihe wird genauso erkannt wie einer in der
        Mitte. Bei einem zentrierten Fenster waere er es nicht - und genau
        daran erkennt man, dass keines benutzt wird."""
        spannen = [1.0] * 40
        spannen[-1] = 10.0

        assert schocks(reihe(spannen), fenster=30, faktor=3.0)[-1]

    def test_die_aufwaermphase_zaehlt_nie_als_schock(self) -> None:
        """Wo keine Norm ist, ist auch kein Vielfaches davon."""
        spannen = [50.0] + [1.0] * 39

        assert not schocks(reihe(spannen), fenster=30, faktor=3.0)[:30].any()

    def test_eine_ruhige_reihe_hat_keine_schocks(self) -> None:
        assert not schocks(reihe([1.0] * 60)).any()

    def test_eine_durchgehend_wilde_reihe_auch_nicht(self) -> None:
        """Ein Schock ist ein Ausreisser gegen die eigene Norm, kein hohes
        Niveau. Wer bei Dauerbewegung dauernd sperrt, sperrt nichts."""
        assert not schocks(reihe([20.0] * 60)).any()

    def test_eine_zu_kurze_reihe_kippt_nicht(self) -> None:
        assert not schocks(reihe([1.0] * 5), fenster=30).any()


class TestSperre:
    def test_kein_vorlauf(self) -> None:
        """**Der zweite tragende Test.**

        Vor dem Schock war er nicht bekannt. So zu tun, als waere er es
        gewesen, ist genau die Hellsicht, gegen die dieses Modul gebaut ist -
        und sie wuerde den Backtest verbessern, ohne im Betrieb zu wirken.
        """
        spannen = [1.0] * 40
        spannen[35] = 10.0
        sperre = gesperrt(reihe(spannen), fenster=30, faktor=3.0, nachlauf=2)

        assert not sperre[:35].any(), "Vor dem Schock darf nichts gesperrt sein"

    def test_die_schockkerze_und_der_nachlauf_sind_gesperrt(self) -> None:
        spannen = [1.0] * 40
        spannen[35] = 10.0
        sperre = gesperrt(reihe(spannen), fenster=30, faktor=3.0, nachlauf=2)

        assert list(np.flatnonzero(sperre)) == [35, 36, 37]

    def test_ohne_nachlauf_bleibt_nur_die_kerze_selbst(self) -> None:
        spannen = [1.0] * 40
        spannen[35] = 10.0
        sperre = gesperrt(reihe(spannen), fenster=30, faktor=3.0, nachlauf=0)

        assert list(np.flatnonzero(sperre)) == [35]

    def test_die_sperre_laeuft_nicht_ueber_das_ende_hinaus(self) -> None:
        spannen = [1.0] * 40
        spannen[-1] = 10.0
        sperre = gesperrt(reihe(spannen), fenster=30, faktor=3.0, nachlauf=5)

        assert len(sperre) == 40
        assert sperre[-1]


class TestAuszaehlung:
    def test_unter_der_schwelle_unterbleibt_die_messung(self) -> None:
        """Der erwartete Fall - und die Schwelle stand vorher fest.

        Ein Versuch hebt die Huerde des Deflated Sharpe fuer alle kuenftigen
        Kandidaten. Ihn fuer eine Wirkung auszugeben, die zwei von hundert
        Signalen betrifft, waere teuer und absehbar folgenlos.
        """
        a = Auszaehlung(
            kerzen=3300, schocks=40, gesperrte_kerzen=110,
            signale=154, betroffene_signale=3,
        )

        assert not a.lohnt_messung
        assert "unter der vorab gesetzten Schwelle" in a.bericht()
        assert "Befund 12" in a.bericht()

    def test_ueber_der_schwelle_lohnt_sie(self) -> None:
        a = Auszaehlung(
            kerzen=3300, schocks=200, gesperrte_kerzen=560,
            signale=154, betroffene_signale=20,
        )

        assert a.lohnt_messung
        assert "den Versuch wert" in a.bericht()

    def test_ohne_signale_wird_nicht_durch_null_geteilt(self) -> None:
        a = Auszaehlung(
            kerzen=100, schocks=0, gesperrte_kerzen=0,
            signale=0, betroffene_signale=0,
        )

        assert a.anteil == 0.0
        assert not a.lohnt_messung


class TestSchocksperre:
    """Die Sperre am selben Ort wie der Terminkalender - nicht daneben.

    In ``RiskOfficer.blockade`` steht der teuerste Satz dieses Projekts:
    *"Jede Regel, die es zweimal gibt, laeuft irgendwann auseinander."* Eine
    Schocksperre, die nur im Backtest greift oder nur im Betrieb, waere genau
    so eine Regel.
    """

    def test_sie_kennt_genau_die_gesperrten_kerzen(self) -> None:
        from research.schock import Schocksperre

        spannen = [1.0] * 40
        spannen[35] = 10.0
        frame = reihe(spannen)
        sperre = Schocksperre.aus_kerzen(frame, fenster=30, faktor=3.0, nachlauf=2)

        zeiten = frame["open_time"]
        assert len(sperre) == 3
        assert sperre.gilt(zeiten[35]) and sperre.gilt(zeiten[37])
        assert not sperre.gilt(zeiten[34])
        assert not sperre.gilt(zeiten[38])

    def test_sie_sperrt_ueber_den_risk_officer(self) -> None:
        """**Der Test, auf den es ankommt.** Nicht "die Sperre kennt die
        Kerze", sondern "der Officer verweigert den Einstieg" - denn genau
        diese Stelle sehen Backtest und Betrieb gemeinsam."""
        from datetime import UTC, datetime

        from core.config import RiskSettings
        from execution.risk import RiskOfficer, VetoReason
        from research.schock import Schocksperre
        from tests.factories import make_instrument

        gesperrt_am = datetime(2021, 3, 12, tzinfo=UTC)
        sperre = Schocksperre(zeitpunkte=frozenset({pd.Timestamp(gesperrt_am)}))

        jetzt = gesperrt_am
        officer = RiskOfficer(
            RiskSettings(), make_instrument(), state_path=None,
            clock=lambda: jetzt, schocksperre=sperre,
        )

        veto = officer.blockade()
        assert veto is not None
        assert veto.reason is VetoReason.NEWS_BLACKOUT
        assert "Marktschock" in veto.detail

    def test_ohne_sperre_bleibt_alles_wie_zuvor(self) -> None:
        from datetime import UTC, datetime

        from core.config import RiskSettings
        from execution.risk import RiskOfficer
        from tests.factories import make_instrument

        officer = RiskOfficer(
            RiskSettings(), make_instrument(), state_path=None,
            clock=lambda: datetime(2021, 3, 12, tzinfo=UTC),
        )

        assert officer.blockade() is None

    def test_zeitzonen_werden_nicht_zur_stillen_luecke(self) -> None:
        """Ein naiver Zeitstempel gegen zeitzonenbehaftete Marken faende nie
        einen Treffer - die Sperre waere lautlos wirkungslos."""
        from research.schock import Schocksperre

        marke = pd.Timestamp("2021-03-12", tz="UTC")
        sperre = Schocksperre(zeitpunkte=frozenset({marke}))

        assert sperre.gilt(pd.Timestamp("2021-03-12"))
        assert sperre.gilt(marke)


class TestKeinLookaheadDurchVorabrechnung:
    """Vorab ueber den ganzen Rahmen gerechnet - ist das schon Lookahead?

    Der Backtest bekommt die Sperre fertig, berechnet ueber **alle** Kerzen
    einschliesslich der Testfenster. Das sieht nach Zukunftswissen aus, und
    der Verdacht gehoert ausgeraeumt statt weggeredet: Er waere begruendet,
    wenn ein spaeterer Wert einen frueheren aendern koennte.

    Geprueft wird deshalb an der Sache selbst - die Sperre wird Kerze fuer
    Kerze aus einem wachsenden Ausschnitt neu berechnet, so wie sie im Betrieb
    entstuende, und muss **Zeichen fuer Zeichen** dasselbe ergeben.
    """

    def test_stueckweise_gerechnet_kommt_dasselbe_heraus(self) -> None:
        rng = np.random.default_rng(11)
        spannen = list(rng.uniform(0.8, 1.2, 200))
        for stelle in (60, 95, 96, 140, 199):
            spannen[stelle] = 8.0
        frame = reihe(spannen)

        vorab = gesperrt(frame, fenster=30, faktor=3.0, nachlauf=2)

        # Wie im Betrieb: An jeder Kerze nur das, was bis dahin bekannt war.
        laufend = np.zeros(len(frame), dtype=bool)
        for i in range(len(frame)):
            bis_hier = gesperrt(
                frame.iloc[: i + 1], fenster=30, faktor=3.0, nachlauf=2
            )
            laufend[i] = bis_hier[i]

        assert np.array_equal(vorab, laufend), (
            "Vorab und laufend berechnet unterscheiden sich - dann haengt ein "
            "frueherer Wert an spaeteren Kerzen, und das waere Lookahead"
        )

    def test_eine_spaetere_kerze_aendert_keine_fruehere(self) -> None:
        """Die Gegenprobe: Wer das Ende der Reihe umschreibt, darf am Anfang
        nichts bewegen."""
        spannen = [1.0] * 120
        spannen[60] = 8.0
        frame = reihe(spannen)

        vorher = gesperrt(frame, fenster=30, faktor=3.0, nachlauf=2)

        veraendert = list(spannen)
        veraendert[100] = 40.0
        nachher = gesperrt(reihe(veraendert), fenster=30, faktor=3.0, nachlauf=2)

        assert np.array_equal(vorher[:100], nachher[:100])
