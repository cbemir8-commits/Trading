"""Der Scan, der vor jeder Suche laeuft - und selbst geprueft werden muss.

Ein Scan, der nichts findet, kann zwei Dinge heissen: Es ist nichts da, oder
er ist kaputt. Deshalb steht hier beides:

* ``test_findet_einen_eingebauten_vorteil`` - eine Reihe mit bekanntem Trend.
  Findet er ihn nicht, taugt kein einziges seiner Ergebnisse.
* ``test_zufallsreihe_gibt_nichts_her`` - eine Irrfahrt. Findet er dort etwas,
  findet er ueberall etwas.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.vorteilsscan import (
    KOSTEN_MAKER_MAKER,
    MIND_T,
    Stabilitaet,
    Zelle,
    pruefe_stabilitaet,
    scanne,
    schwelle_fuer,
    spanne,
    urteil,
)


def trendreihe(n: int = 4000, staerke: float = 0.4, saat: int = 1) -> np.ndarray:
    """Eine Reihe mit eingebautem Momentum: Die Rendite folgt der vorigen."""
    rng = np.random.default_rng(saat)
    schritte = np.zeros(n)
    for i in range(1, n):
        schritte[i] = staerke * schritte[i - 1] + rng.normal(0, 0.01)
    return 100.0 * np.exp(np.cumsum(schritte))


def irrfahrt(n: int = 4000, saat: int = 2, drift: float = 0.0) -> np.ndarray:
    rng = np.random.default_rng(saat)
    return 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))


class TestKalibrierung:
    def test_findet_einen_eingebauten_vorteil(self) -> None:
        """Ohne diesen Test sagt kein Ergebnis des Scans etwas aus."""
        zellen = scanne(trendreihe(), [4, 8, 16], [4, 8, 16])

        assert zellen
        assert zellen[0].auffaellig
        assert zellen[0].spanne_pct > 0, "Momentum muss eine positive Spanne geben"

    def test_zufallsreihe_gibt_nichts_her(self) -> None:
        """Eine Irrfahrt hat keine Struktur. Wer hier etwas findet, findet
        ueberall etwas."""
        auffaellige = [z for z in scanne(irrfahrt(), [4, 8, 16, 32], [4, 8, 16, 32])
                       if z.auffaellig]

        assert len(auffaellige) <= 1, (
            f"Bei 16 Zellen und 5 % Irrtumswahrscheinlichkeit ist hoechstens "
            f"eine zufaellig auffaellig - gefunden: {len(auffaellige)}"
        )

    def test_der_grundtrend_allein_erzeugt_keine_spanne(self) -> None:
        """**Der Fehler aus dem ersten Anlauf.**

        Gemessen wurde zuerst die bedingte Rendite statt der Differenz. Bei
        einem Markt mit starkem Aufwaertsdrift sah das ueberall nach Vorteil
        aus - es war der Drift.
        """
        mit_drift = irrfahrt(n=6000, saat=5, drift=0.002)

        auffaellige = [z for z in scanne(mit_drift, [8, 16, 32], [8, 16, 32])
                       if z.auffaellig]

        assert not auffaellige, "Reiner Drift ist kein Vorhersagevorteil"


class TestSpanne:
    def test_ueberlappende_fenster_werden_vermieden(self) -> None:
        """Alle ``halten`` Balken eine Beobachtung - sonst waere der t-Wert
        um Wurzel(halten) zu gross."""
        reihe = np.log(irrfahrt(n=1000))

        z = spanne(reihe, 10, 10)

        assert z is not None
        assert z.beobachtungen == pytest.approx(1000 / 10, rel=0.1)

    def test_zu_kurze_reihe(self) -> None:
        assert spanne(np.log(irrfahrt(n=50)), 20, 40) is None

    def test_unsinnige_parameter(self) -> None:
        reihe = np.log(irrfahrt(n=1000))
        assert spanne(reihe, 0, 10) is None
        assert spanne(reihe, 10, 0) is None


class TestKosten:
    def test_netto_rechnet_mit_der_halben_spanne(self) -> None:
        """Eine Regel handelt eine Seite, nicht beide. Wer mit der ganzen
        Spanne rechnet, verdoppelt seinen Vorteil auf dem Papier."""
        z = Zelle(rueckblick=16, halten=16, beobachtungen=1000,
                  spanne_pct=0.10, t_wert=3.0)

        assert z.netto_pct(kosten=0.04) == pytest.approx(0.01)
        assert z.kosten_vielfaches(kosten=0.04) == pytest.approx(2.5)

    def test_vorzeichen_ist_egal_fuer_die_groesse(self) -> None:
        """Gegenbewegung ist genauso handelbar wie Trendfolge - wenn sie
        gross genug ist."""
        auf = Zelle(16, 16, 1000, 0.10, 3.0)
        ab = Zelle(16, 16, 1000, -0.10, -3.0)

        assert auf.netto_pct() == ab.netto_pct()


class TestStabilitaet:
    def test_nur_erste_haelfte_haelt_nicht(self) -> None:
        """**Der Fall, an dem der 15-Minuten-Fund gescheitert ist.**

        Marktuebergreifend bestaetigt, statistisch klar - und in der zweiten
        Haelfte des Zeitraums vollstaendig verschwunden.
        """
        s = Stabilitaet(
            erste=Zelle(16, 16, 7000, -0.104, -2.90),
            zweite=Zelle(16, 16, 7000, 0.007, 0.29),
        )

        assert not s.haelt

    def test_vorzeichenwechsel_haelt_nicht(self) -> None:
        s = Stabilitaet(
            erste=Zelle(16, 16, 7000, -0.10, -3.0),
            zweite=Zelle(16, 16, 7000, 0.10, 3.0),
        )

        assert not s.haelt

    def test_beide_haelften_gleich_haelt(self) -> None:
        s = Stabilitaet(
            erste=Zelle(16, 16, 7000, 0.10, 3.0),
            zweite=Zelle(16, 16, 7000, 0.09, 2.5),
        )

        assert s.haelt

    def test_fehlende_haelfte_haelt_nicht(self) -> None:
        assert not Stabilitaet(erste=Zelle(16, 16, 7000, 0.1, 3.0), zweite=None).haelt
        assert not Stabilitaet(erste=None, zweite=None).haelt

    def test_pruefung_teilt_die_reihe(self) -> None:
        """Ein echter Vorteil steht in beiden Haelften.

        Die Reihe ist bewusst lang (20.000 Balken): Bei 6.000 blieben je
        Haelfte nur 373 Beobachtungen, und derselbe eingebaute Vorteil kam
        einmal auf t = 1,05 und einmal auf t = 2,30 - also einmal
        "gefunden", einmal "nicht gefunden".

        Das ist kein Fehler der Pruefung, sondern ihre Kehrseite: Sie
        verlangt in **jeder** Haelfte genug Beobachtungen. Wer zu kurze
        Reihen halbiert, verwirft echte Vorteile. Bei den 15-Minuten-Daten
        stehen je Haelfte 7.000 Beobachtungen - dort traegt die Pruefung.
        """
        s = pruefe_stabilitaet(trendreihe(n=20_000), 8, 8)

        assert s.erste is not None and s.zweite is not None
        assert s.haelt, "Ein echter Vorteil muss in beiden Haelften stehen"

    def test_zu_kurze_reihe_kann_echtes_verwerfen(self) -> None:
        """Die Kehrseite, festgehalten statt uebersehen.

        Derselbe eingebaute Vorteil, nur ein Drittel der Laenge - und die
        Pruefung faellt. Das ist die richtige Richtung (im Zweifel nichts
        behaupten), muss aber bekannt sein, damit niemand aus einem
        gescheiterten Test auf einen fehlenden Vorteil schliesst.
        """
        assert not pruefe_stabilitaet(trendreihe(n=6000), 8, 8).haelt


class TestUrteil:
    def test_unauffaellig(self) -> None:
        z = Zelle(16, 16, 1000, 0.01, 0.5)

        text = urteil(z, Stabilitaet(None, None))

        assert "Nicht auffaellig" in text
        assert "Huerde zu heben" in text

    def test_auffaellig_aber_unstabil(self) -> None:
        z = Zelle(16, 16, 14000, -0.0883, -4.11)
        s = Stabilitaet(Zelle(16, 16, 7000, -0.104, -2.90),
                        Zelle(16, 16, 7000, 0.007, 0.29))

        text = urteil(z, s)

        assert "nicht stabil" in text
        assert "wegarbitriert" in text

    def test_stabil_aber_zu_klein(self) -> None:
        z = Zelle(16, 16, 14000, 0.05, 3.0)
        s = Stabilitaet(Zelle(16, 16, 7000, 0.05, 2.5),
                        Zelle(16, 16, 7000, 0.05, 2.5))

        text = urteil(z, s, kosten=KOSTEN_MAKER_MAKER)

        assert "zu klein" in text
        assert "Gebuehren fressen" in text

    def test_echter_fund(self) -> None:
        z = Zelle(16, 16, 14000, 0.50, 5.0)
        s = Stabilitaet(Zelle(16, 16, 7000, 0.5, 3.5),
                        Zelle(16, 16, 7000, 0.5, 3.5))

        text = urteil(z, s)

        assert "Fund:" in text
        assert "lohnen sich Versuche" in text


def test_schwelle_ist_zwei_sigma() -> None:
    """Festgehalten, damit sie nicht unbemerkt weicher wird."""
    assert MIND_T == 2.0


class TestMehrfachtestung:
    """Der Scan prueft 81 Zellen je Markt. Bei |t| >= 2 sind vier davon rein
    zufaellig auffaellig - wer die beste nimmt, misst seine Zahl der Versuche.

    Derselbe Fehler, gegen den das Deflated-Sharpe-Gate schuetzt, nur eine
    Ebene tiefer. Und hier besonders bitter: Der Scan wurde gebaut, um
    Versuche zu sparen.
    """

    def test_mehr_zellen_heben_die_schwelle(self) -> None:
        from research.vorteilsscan import schwelle_fuer

        assert schwelle_fuer(1) == MIND_T
        assert schwelle_fuer(81) > schwelle_fuer(9) > schwelle_fuer(1)
        assert schwelle_fuer(81) == pytest.approx(3.42, abs=0.02)

    def test_ein_grenzwertiger_treffer_zaehlt_nicht_mehr(self) -> None:
        """ETH lag bei t = +3,04 - als einzelne Zelle auffaellig, unter 81
        geprueften nicht mehr."""
        z = Zelle(48, 4, 55662, 0.0221, 3.04)

        assert z.auffaellig
        assert not z.ueber_schwelle(schwelle_fuer(81))

    def test_urteil_nennt_die_schwelle(self) -> None:
        z = Zelle(48, 4, 55662, 0.0221, 3.04)
        s = Stabilitaet(Zelle(48, 4, 27000, 0.02, 2.2), Zelle(48, 4, 27000, 0.02, 2.1))

        text = urteil(z, s, gepruefte_zellen=81)

        assert "81 geprueften Zellen" in text
        assert "3.42" in text

    def test_ein_starker_treffer_haelt_auch_korrigiert(self) -> None:
        """BTC lag bei t = -4,11 - das ueberlebt die Korrektur.

        Gescheitert ist es an der Stabilitaet, nicht an der Signifikanz. Die
        beiden Huerden sind unabhaengig und beide noetig.
        """
        z = Zelle(16, 16, 13917, -0.0883, -4.11)

        assert z.ueber_schwelle(schwelle_fuer(81))
