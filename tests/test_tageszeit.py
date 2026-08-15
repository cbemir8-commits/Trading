"""Sagt die Uhrzeit etwas - und die Fallen beim Nachmessen.

Zwei Tests tragen diese Datei:

``test_je_tag_ein_wert_nicht_je_kerze`` - Innerhalb eines Tages sind die
Viertelstunden nicht unabhaengig. Wer sie einzeln zaehlt, bekommt einen t-Wert,
der um ein Vielfaches zu gross ist, und findet ueberall Vorteile. Das ist der
haeufigste Weg, sich einen herbeizurechnen.

``test_die_schwelle_gilt_fuer_alle_geprueften_fenster`` - Wer 24 Stunden prueft
und die beste nimmt, findet mit Sicherheit eine auffaellige. Die Schwelle muss
zur Zahl der geprueften Zellen gehoeren, nicht zu einer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.tageszeit import (
    MIND_TAGE,
    SITZUNGEN,
    Fenster,
    Stabilitaet,
    messe,
    pruefe_stabilitaet,
    scanne_sitzungen,
    scanne_stunden,
    urteil,
)
from research.vorteilsscan import schwelle_fuer


def reihe(tage: int = 600, *, bonus_stunde: int | None = None,
          bonus: float = 0.0, saat: int = 3) -> pd.DataFrame:
    """15-Minuten-Kerzen ueber ``tage`` Tage, optional mit gepflanzter Stunde."""
    n = tage * 96
    rng = np.random.default_rng(saat)
    schritt = rng.normal(0.0, 0.003, n)
    zeiten = pd.date_range("2020-03-30", periods=n, freq="15min", tz="UTC")
    if bonus_stunde is not None:
        schritt[zeiten.hour == bonus_stunde] += bonus
    close = 100 * np.exp(np.cumsum(schritt))
    return pd.DataFrame(
        {
            "open_time": zeiten,
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": np.full(n, 5.0),
        }
    )


class TestMessen:
    def test_je_tag_ein_wert_nicht_je_kerze(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Auf einer strukturlosen Reihe darf kein Fenster auffallen. Zaehlte die
        Messung jede Viertelstunde einzeln, waere der t-Wert um rund Wurzel(96)
        zu gross - und ein Rauschen von 0,5 saehe aus wie ein Fund von 5.
        """
        frame = reihe(600)

        werte = [abs(f.t_wert) for f in scanne_sitzungen(frame)]

        assert werte, "Es muss ueberhaupt etwas gemessen worden sein"
        assert max(werte) < 3.0, (
            f"Groesster t-Wert {max(werte):.2f} auf strukturlosen Daten - das "
            f"deutet auf abhaengige Beobachtungen"
        )

    def test_ein_gepflanzter_effekt_wird_gefunden(self) -> None:
        """Die Gegenprobe: Was da ist, muss auch auffallen."""
        frame = reihe(600, bonus_stunde=14, bonus=0.002)

        bestes = scanne_stunden(frame)[0]

        assert bestes.name == "14 Uhr"
        assert bestes.t_wert > 3.0
        assert bestes.spanne_pct > 0

    def test_ein_fenster_ueber_mitternacht_wird_richtig_geschnitten(self) -> None:
        frame = reihe(400, bonus_stunde=23, bonus=0.004)

        nacht = messe(frame, name="Nacht", von=22, bis=2)
        tag = messe(frame, name="Tag", von=10, bis=14)

        assert nacht is not None and tag is not None
        assert nacht.spanne_pct > tag.spanne_pct
        assert nacht.stunden == 4.0

    def test_zu_wenige_tage_liefern_nichts(self) -> None:
        assert messe(reihe(MIND_TAGE - 50), name="x", von=0, bis=6) is None

    def test_ein_fenster_ueber_den_ganzen_tag_liefert_nichts(self) -> None:
        """Ohne ein Aussen gibt es nichts zu vergleichen."""
        assert messe(reihe(400), name="alles", von=0, bis=0) is None


class TestSitzungen:
    def test_sie_stehen_vorab_fest(self) -> None:
        """**Sie kommen aus der Marktstruktur, nicht aus den Daten.**

        Bei 96 Viertelstunden gaebe es rund 4600 moegliche Fenster. Wer die
        alle prueft und das beste nimmt, hat die Zahl seiner Versuche gemessen.
        """
        assert len(SITZUNGEN) == 7
        namen = {name for name, _, _ in SITZUNGEN}
        assert {"Asien", "Europa", "Nordamerika"} <= namen

    def test_alle_sitzungen_werden_gemessen(self) -> None:
        gefunden = scanne_sitzungen(reihe(400))

        assert len(gefunden) == len(SITZUNGEN)
        assert [abs(f.t_wert) for f in gefunden] == sorted(
            (abs(f.t_wert) for f in gefunden), reverse=True
        )


class TestUrteil:
    def fenster(self, *, t: float, spanne: float = 0.2) -> Fenster:
        return Fenster(
            name="Europa", von=7, bis=16, tage=2300,
            spanne_pct=spanne, t_wert=t,
        )

    def test_die_schwelle_gilt_fuer_alle_geprueften_fenster(self) -> None:
        """**Der zweite tragende Test.**

        Ein t-Wert von 2,5 ist fuer eine einzelne Zelle auffaellig und fuer
        24 gepruefte nicht. Wer das verwechselt, produziert genau die
        Scheinfunde, gegen die dieser Scan gebaut ist.
        """
        knapp = self.fenster(t=2.5)

        assert knapp.ueber_schwelle(2.0), "Als einzelne Zelle waere es auffaellig"
        assert not knapp.ueber_schwelle(schwelle_fuer(24))
        assert "Nicht auffaellig genug" in urteil(knapp, None, geprueft=24)
        assert "nicht bei 2.00" in urteil(knapp, None, geprueft=24)

    def test_ein_instabiler_fund_wird_abgewiesen(self) -> None:
        stark = self.fenster(t=5.0)
        wackelig = Stabilitaet(
            erste=self.fenster(t=4.0), zweite=self.fenster(t=0.3, spanne=-0.01)
        )

        text = urteil(stark, wackelig, geprueft=7)
        assert "aber nicht stabil" in text
        assert "steht morgen nicht zur Verfuegung" in text

    def test_was_die_gebuehr_frisst_ist_kein_fund(self) -> None:
        klein = self.fenster(t=5.0, spanne=0.03)
        stabil = Stabilitaet(erste=self.fenster(t=4.0), zweite=self.fenster(t=3.0))

        assert "nach Gebuehren bleibt nichts" in urteil(klein, stabil, geprueft=7)

    def test_alle_drei_huerden_gehalten_heisst_fund(self) -> None:
        gross = self.fenster(t=5.0, spanne=0.2)
        stabil = Stabilitaet(erste=self.fenster(t=4.0), zweite=self.fenster(t=3.0))

        text = urteil(gross, stabil, geprueft=7)
        assert "**Fund:" in text
        assert "Alle drei Huerden gehalten" in text

    def test_ohne_fenster_wird_nichts_behauptet(self) -> None:
        assert "nichts zu beurteilen" in urteil(None, None, geprueft=7)


class TestStabilitaet:
    def test_beide_haelften_brauchen_dasselbe_vorzeichen(self) -> None:
        auf = Fenster(name="x", von=0, bis=6, tage=1000, spanne_pct=0.2, t_wert=4.0)
        ab = Fenster(name="x", von=0, bis=6, tage=1000, spanne_pct=-0.2, t_wert=-4.0)

        assert not Stabilitaet(erste=auf, zweite=ab).haelt
        assert Stabilitaet(erste=auf, zweite=auf).haelt

    def test_eine_fehlende_haelfte_gilt_nicht_als_stabil(self) -> None:
        auf = Fenster(name="x", von=0, bis=6, tage=1000, spanne_pct=0.2, t_wert=4.0)

        assert not Stabilitaet(erste=auf, zweite=None).haelt
        assert "Zu wenig Daten" in Stabilitaet(erste=None, zweite=auf).beschreibe()

    def test_sie_teilt_die_reihe_in_der_mitte(self) -> None:
        frame = reihe(600, bonus_stunde=14, bonus=0.002)
        bestes = scanne_stunden(frame)[0]

        stabil = pruefe_stabilitaet(frame, bestes)

        assert stabil.erste is not None and stabil.zweite is not None
        assert stabil.haelt, "Ein durchgehend gepflanzter Effekt muss halten"
