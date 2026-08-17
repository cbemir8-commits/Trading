"""Das schlechteste Jahr - ein Ausreisser oder eine Marktphase?

Drei Tests tragen diese Datei:

``test_ueberlappende_fenster_sind_keine_stichprobe`` - Der Kern. "Nur 2 von
2465 Fenstern liegen darunter" klingt nach einem Ausreisser; die Fenster
ueberlappen sich aber fast vollstaendig, und in 93 Testmonaten stecken 7,7
unabhaengige Jahresperioden. Derselbe Fehler wie die siebenfach gezaehlte
Regel in Befund 88.

``test_die_daempfung_entlastet_nicht`` - Im schlechtesten Fenster verlor der
Markt 72 %, die Strategie 10,3 %. Das ist Faktor sieben und trotzdem kein
Argument gegen das Gate: Ob sie besser war als der Markt, fragt die
Messlatte.

``test_eine_streuende_duerre_wird_nicht_als_ereignis_gemeldet`` - Liegen die
schlechten Fenster verteilt statt zusammen, ist es keine Phase, und das
Urteil behauptet auch keine.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.duerre import FENSTERMONATE, Duerre, baue


def kurve_mit_einbruch(
    *, punkte: int = 2830, beginn: int = 1177, tiefe: float = 0.12
) -> np.ndarray:
    """Eine flache Kurve mit genau einer zwoelfmonatigen Duerre.

    Flach und nicht steigend: Der erste Entwurf legte den Einbruch auf eine
    von 1,0 auf 3,0 steigende Gerade, und der Anstieg ueber ein Jahr (+14 %)
    hat ihn vollstaendig aufgezehrt - die Kurve hatte gar keine Duerre. Das
    fiel erst im Test auf.
    """
    werte = np.ones(punkte)
    spanne = int(punkte * FENSTERMONATE / 93.0)
    for i in range(spanne):
        werte[beginn + i :] *= 1 - tiefe / spanne
    return werte


def bild(**abweichung) -> Duerre:
    daten = {
        "schlechteste_pct": -10.32, "grenze_pct": -10.0, "fenster": 2465,
        "testmonate": 93.0, "beginn": "2021-11-08", "ende": "2022-11-08",
        "zone_von": "2021-10-14", "zone_bis": "2022-01-08",
        "markt": {"BTC": -72.5, "ETH": -72.3}, "unter_grenze": 2,
        "perzentil_1": -6.54, "median": 11.51,
    }
    daten.update(abweichung)
    return Duerre(**daten)


class TestStichprobe:
    def test_ueberlappende_fenster_sind_keine_stichprobe(self) -> None:
        """**Der Test, der diese Datei traegt.**

        2465 rollierende Zwoelfmonatsfenster auf 93 Testmonaten ueberlappen
        sich zu 99,7 %. Sie als Stichprobe zu lesen ist derselbe Fehler wie
        in Befund 88, wo eine Regel siebenfach zaehlte und daraus ein
        Zusammenhang wurde, den es nicht gab.
        """
        d = bild()

        assert d.fenster == 2465
        assert d.unabhaengige_perioden == pytest.approx(7.75, abs=0.01)
        assert d.anteil_unter_grenze < 0.002, "sieht nach Ausreisser aus"
        urteil = d.urteil()
        assert "ist aber keiner" in urteil
        assert "unabhaengige Jahresperioden" in urteil
        assert "Betroffen ist eine davon" in urteil

    def test_die_zone_zeigt_ein_ereignis(self) -> None:
        """Alle schlechten Fenster starten binnen drei Monaten - das ist eine
        Phase, keine Streuung."""
        urteil = bild().urteil()

        assert "keine Streuung" in urteil
        assert "2021-10-14" in urteil and "2022-01-08" in urteil

    def test_eine_streuende_duerre_wird_nicht_als_ereignis_gemeldet(self) -> None:
        """Gegenprobe: Ohne zusammenhaengende Zone behauptet das Urteil
        keine."""
        verteilt = bild(zone_von="", zone_bis="")

        assert "keine Streuung" not in verteilt.urteil()


class TestDaempfung:
    def test_die_daempfung_entlastet_nicht(self) -> None:
        """**Der zweite tragende Test.**

        Faktor sieben klingt nach einem guten Argument. Es ist keins: Ob die
        Strategie besser war als der Markt, prueft die Messlatte - dieses
        Gate fragt, ob jemand das Jahr durchgehalten haette.
        """
        d = bild()

        assert d.daempfung == pytest.approx(72.5 / 10.32, abs=0.05)
        urteil = d.urteil()
        assert "Faktor 7.0" in urteil
        assert "entlastet sie nicht" in urteil
        assert "fragt die Messlatte" in urteil

    def test_ohne_markteinbruch_gibt_es_keine_daempfung(self) -> None:
        """Hat der Markt im selben Fenster gewonnen, gibt es nichts zu
        daempfen - und die Zahl waere eine Ausrede."""
        gestiegen = bild(markt={"BTC": 30.0})

        assert gestiegen.daempfung is None
        assert "gedaempft" not in gestiegen.urteil()

    def test_ohne_marktzahlen_bleibt_der_absatz_weg(self) -> None:
        assert bild(markt={}).daempfung is None


class TestUrteil:
    def test_ein_bestandenes_gate_wird_knapp_gemeldet(self) -> None:
        """Gegenprobe: Liegt das schlechteste Jahr innerhalb der Grenze, gibt
        es nichts einzuordnen."""
        gut = bild(schlechteste_pct=-7.5)

        assert gut.besteht
        assert "innerhalb der Grenze" in gut.urteil()
        assert "Ausreisser" not in gut.urteil()

    def test_der_fehlbetrag_wird_genannt(self) -> None:
        d = bild()

        assert d.fehlt == pytest.approx(0.32, abs=0.001)
        assert "0.32 Punkte ueber der Grenze" in d.urteil()

    def test_die_tabelle_nennt_beide_zahlen_nebeneinander(self) -> None:
        text = bild().tabelle()

        assert "rollierende Fenster" in text
        assert "unabhaengige Perioden" in text
        assert "2465" in text
        # Nicht gegen die formatierte Zahl pruefen: 93/12 = 7,75 rundet je
        # nach Testmonaten auf 7,7 oder 7,8, und der Test haenge dann an
        # einer Rundung statt an der Aussage.
        assert f"{bild().unabhaengige_perioden:.1f}" in text


class TestBaue:
    def test_sie_findet_die_duerre_in_einer_kurve(self) -> None:
        gebaut = baue(kurve_mit_einbruch(), testmonate=93.0, grenze_pct=-10.0)

        assert gebaut is not None
        assert gebaut.schlechteste_pct < -10.0
        assert not gebaut.besteht
        assert gebaut.unabhaengige_perioden == pytest.approx(7.75, abs=0.01)

    def test_eine_stetig_steigende_kurve_hat_keine_duerre(self) -> None:
        gebaut = baue(
            np.linspace(1.0, 3.0, 2830), testmonate=93.0, grenze_pct=-10.0
        )

        assert gebaut is not None
        assert gebaut.schlechteste_pct > 0
        assert gebaut.besteht
        assert gebaut.unter_grenze == 0

    def test_ein_zu_kurzer_zeitraum_liefert_nichts(self) -> None:
        """Weniger als zwoelf Testmonate - eine Zahl waere dort geraten."""
        assert baue(np.linspace(1.0, 2.0, 300), testmonate=8.0, grenze_pct=-10.0) is None
        assert baue(np.array([1.0, 2.0]), testmonate=93.0, grenze_pct=-10.0) is None

    def test_die_zone_nimmt_die_halbe_grenze(self) -> None:
        """Ueber die Grenze selbst bestuende die Zone oft aus einem Punkt und
        sagte nichts darueber, ob es ein Ereignis war."""
        zeiten = [f"2020-{1 + i // 300:02d}-01" for i in range(2830)]
        gebaut = baue(
            kurve_mit_einbruch(), testmonate=93.0, grenze_pct=-10.0, zeiten=zeiten
        )

        assert gebaut is not None
        assert gebaut.zone_von and gebaut.zone_bis

    def test_ohne_zeitstempel_bleiben_die_zahlen_richtig(self) -> None:
        gebaut = baue(kurve_mit_einbruch(), testmonate=93.0, grenze_pct=-10.0)

        assert gebaut is not None
        assert gebaut.beginn == "" and gebaut.ende == ""
        assert gebaut.fenster > 0
        assert "Es laeuft vom" not in gebaut.urteil()

    def test_die_fenstermonate_stimmen_mit_dem_gate_ueberein(self) -> None:
        """Eine andere Periode als das Gate zu betrachten hiesse, etwas
        anderes einzuordnen als das, was scheitert."""
        from research.gates import GateThresholds

        assert FENSTERMONATE == 12
        assert GateThresholds().worst_year_pct == -10.0
