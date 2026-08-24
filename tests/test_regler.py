"""Tests fuer ``research.regler`` - Befunde 128 und 129.

Die beiden gemessenen Leitern (Vola-Ziel, BTC + ETH, Tageskerzen, 198
Versuche) stehen in ``perpetual()`` und ``spot()``. Sie sind die Vorlage fuer
die meisten Faelle hier; erfundene Leitern kommen nur dort vor, wo ein Zweig
sonst ungetestet bliebe.

``ARTEN`` und ``Reglerart`` kamen mit Befund 129 dazu - der zweite Regler, den
ein Befund schon einmal am Perpetual-Punkt abgefahren hat (Befund 46, das
Gewinnziel).
"""

from __future__ import annotations

import pytest

from research.regler import (
    ARTEN,
    Klaerungskosten,
    Konflikt,
    Reglerart,
    Reglerleiter,
    Reglervergleich,
    Stellung,
)
from research.seeds import spitzenkandidat

DSR = "Deflated Sharpe"
LATTE = "Messlatte"
JAHR = "Schlechtestes Jahr"
RUECK = "Drawdown"
PLATEAU = "Parameter-Plateau"
MC = "Monte-Carlo"
STRESS = "Kosten-Stress"


def perpetual() -> Reglerleiter:
    """Wie Befund 21 gemessen hat - am Perpetual-Punkt."""
    return Reglerleiter(
        "Vola-Ziel (Perpetual)",
        (
            Stellung(14.0, 149, 9.47, 7.75, 9, 11, (LATTE, DSR)),
            Stellung(16.0, 154, 10.98, 8.46, 9, 11, (LATTE, DSR)),
            Stellung(19.3, 152, 13.47, 10.64, 7, 11, (LATTE, JAHR, DSR, PLATEAU)),
            Stellung(22.0, 152, 15.16, 12.82, 7, 11, (RUECK, JAHR, DSR, PLATEAU)),
            Stellung(25.0, 152, 17.23, 14.78, 7, 11, (RUECK, JAHR, DSR, PLATEAU)),
            Stellung(28.0, 152, 19.05, 16.65, 7, 11, (RUECK, JAHR, DSR, PLATEAU)),
            Stellung(
                32.0, 152, 22.30, 18.18, 5, 11,
                (RUECK, JAHR, MC, DSR, STRESS, PLATEAU),
            ),
        ),
    )


def spot() -> Reglerleiter:
    """Derselbe Regler am Spot-Punkt - kein Funding, kein Hebel."""
    return Reglerleiter(
        "Vola-Ziel (Spot)",
        (
            Stellung(14.0, 149, 10.36, 7.17, 9, 11, (LATTE, DSR)),
            Stellung(16.0, 154, 12.05, 7.79, 9, 11, (LATTE, DSR)),
            Stellung(19.3, 152, 14.83, 9.87, 9, 11, (LATTE, DSR)),
            Stellung(22.0, 152, 16.73, 11.85, 9, 11, (JAHR, DSR)),
            Stellung(25.0, 152, 19.19, 13.74, 7, 11, (RUECK, JAHR, DSR, PLATEAU)),
            Stellung(28.0, 152, 21.10, 15.49, 7, 11, (RUECK, JAHR, DSR, PLATEAU)),
            Stellung(32.0, 152, 24.68, 16.89, 7, 11, (RUECK, JAHR, DSR, PLATEAU)),
        ),
    )


# --- Stellung ---------------------------------------------------------------


def test_stellung_haelt_was_nicht_offen_steht() -> None:
    s = Stellung(19.3, 152, 14.83, 9.87, 9, 11, (LATTE, DSR))
    assert not s.haelt(LATTE)
    assert not s.haelt(DSR)
    assert s.haelt(JAHR)
    assert s.haelt("irgendein Gate, das es gar nicht gibt")


def test_stellung_alles_haelt_nur_bei_voller_zahl() -> None:
    assert Stellung(19.3, 152, 14.83, 9.87, 11, 11).alles_haelt
    assert not Stellung(19.3, 152, 14.83, 9.87, 10, 11, (DSR,)).alles_haelt


def test_stellung_ohne_gates_ist_keine_messung() -> None:
    with pytest.raises(ValueError, match="keine Messung"):
        Stellung(19.3, 152, 14.83, 9.87, 0, 0)


def test_stellung_weist_unmoegliche_gatezahl_zurueck() -> None:
    with pytest.raises(ValueError, match="keinen Sinn"):
        Stellung(19.3, 152, 14.83, 9.87, 12, 11)
    with pytest.raises(ValueError, match="keinen Sinn"):
        Stellung(19.3, 152, 14.83, 9.87, -1, 11)


def test_stellung_weist_mehr_offene_gates_als_durchgefallene_zurueck() -> None:
    with pytest.raises(ValueError, match="passen nicht"):
        Stellung(19.3, 152, 14.83, 9.87, 10, 11, (LATTE, DSR))


def test_stellung_zeile_nennt_offene_gates() -> None:
    zeile = Stellung(19.3, 152, 14.83, 9.87, 9, 11, (LATTE, DSR)).als_zeile()
    assert "19.3" in zeile and "152" in zeile and "9/11" in zeile
    assert LATTE in zeile and DSR in zeile


def test_stellung_zeile_ohne_offene_gates_haengt_nichts_an() -> None:
    assert Stellung(19.3, 152, 14.83, 9.87, 11, 11).als_zeile().endswith("11/11")


# --- Reglerleiter: Grundzuege ----------------------------------------------


def test_leere_leiter_sagt_nichts() -> None:
    leer = Reglerleiter("nichts gemessen")
    assert leer.fenster() == ()
    assert leer.immer_offen() == ()
    assert leer.konflikte() == ()
    assert not leer.klaerung_lohnt()
    assert "nicht gemessen" in leer.urteil()


def test_sortiert_ordnet_nach_reglerwert() -> None:
    durcheinander = Reglerleiter(
        "unsortiert",
        (
            Stellung(25.0, 152, 19.19, 13.74, 7, 11, (DSR,)),
            Stellung(14.0, 149, 10.36, 7.17, 9, 11, (DSR,)),
            Stellung(19.3, 152, 14.83, 9.87, 9, 11, (DSR,)),
        ),
    )
    assert [s.wert for s in durcheinander.sortiert] == [14.0, 19.3, 25.0]


def test_je_offen_zaehlt_jedes_gate_einmal_in_reihenfolge() -> None:
    assert spot().je_offen() == (LATTE, DSR, JAHR, RUECK, PLATEAU)


def test_je_offen_uebergeht_gates_die_nie_gefallen_sind() -> None:
    """Monte-Carlo und Kosten-Stress fallen nur am Perpetual-Punkt, bei 32."""
    assert MC in perpetual().je_offen()
    assert MC not in spot().je_offen()


def test_immer_offen_ist_der_deflated_sharpe() -> None:
    assert spot().immer_offen() == (DSR,)
    assert perpetual().immer_offen() == (DSR,)


def test_kein_fenster_an_beiden_betriebspunkten() -> None:
    assert spot().fenster() == ()
    assert perpetual().fenster() == ()


def test_fenster_wird_gemeldet_wenn_es_eines_gibt() -> None:
    mit = Reglerleiter(
        "erfunden",
        (
            Stellung(14.0, 149, 10.36, 7.17, 9, 11, (LATTE, DSR)),
            Stellung(19.3, 152, 14.83, 9.87, 11, 11),
            Stellung(25.0, 152, 19.19, 13.74, 7, 11, (RUECK, JAHR, DSR, PLATEAU)),
        ),
    )
    assert [s.wert for s in mit.fenster()] == [19.3]
    assert "hat ein Fenster" in mit.urteil()
    assert "zu pruefen" in mit.urteil()
    assert not mit.klaerung_lohnt()


# --- Haltebereiche ----------------------------------------------------------


def test_haltebereich_am_spot_punkt() -> None:
    leiter = spot()
    assert leiter.haltebereich(JAHR) == (14.0, 19.3)
    assert leiter.haltebereich(LATTE) == (22.0, 32.0)
    assert leiter.haltebereich(RUECK) == (14.0, 22.0)


def test_haltebereich_ist_none_wo_nichts_haelt() -> None:
    assert spot().haltebereich(DSR) is None


def test_durchgehend_gilt_fuer_die_gemessenen_gates() -> None:
    leiter = spot()
    assert leiter.haelt_durchgehend(JAHR)
    assert leiter.haelt_durchgehend(LATTE)
    assert not leiter.haelt_durchgehend(DSR)


def test_gate_mit_loch_gilt_nicht_als_durchgehend() -> None:
    loechrig = Reglerleiter(
        "mit Loch",
        (
            Stellung(14.0, 149, 10.36, 7.17, 10, 11, (DSR,)),
            Stellung(19.3, 152, 14.83, 9.87, 9, 11, (LATTE, DSR)),
            Stellung(25.0, 152, 19.19, 13.74, 10, 11, (DSR,)),
        ),
    )
    assert loechrig.haltebereich(LATTE) == (14.0, 25.0)
    assert not loechrig.haelt_durchgehend(LATTE)


def test_loechriges_gate_bleibt_aus_der_konfliktrechnung() -> None:
    """Seine Spanne wuerde mehr behaupten, als gemessen wurde."""
    loechrig = Reglerleiter(
        "mit Loch",
        (
            Stellung(14.0, 149, 10.36, 7.17, 10, 11, (JAHR,)),
            Stellung(19.3, 152, 14.83, 9.87, 9, 11, (LATTE, JAHR)),
            Stellung(25.0, 152, 19.19, 13.74, 10, 11, (JAHR,)),
        ),
    )
    assert loechrig.konflikte() == ()


# --- Konflikte --------------------------------------------------------------


def test_spot_hat_genau_einen_konflikt_zwischen_jahr_und_latte() -> None:
    streit = spot().konflikte()
    assert len(streit) == 1
    k = streit[0]
    assert (k.unten, k.oben) == (JAHR, LATTE)
    assert (k.letzte_unten, k.erste_oben) == (19.3, 22.0)


def test_spot_konflikt_hat_keine_gemessene_sprosse_dazwischen() -> None:
    k = spot().konflikte()[0]
    assert k.dazwischen == ()
    assert k.benachbart
    assert k.luecke == pytest.approx(2.7)
    assert "nichts gemessen" in k.als_zeile()


def test_perpetual_hat_eine_gemessene_sprosse_im_konflikt() -> None:
    """Bei 19,3 faellt am Perpetual-Punkt beides - das ist mehr als Nachbarschaft."""
    streit = [k for k in perpetual().konflikte() if (k.unten, k.oben) == (JAHR, LATTE)]
    assert len(streit) == 1
    k = streit[0]
    assert (k.letzte_unten, k.erste_oben) == (16.0, 22.0)
    assert k.dazwischen == (19.3,)
    assert not k.benachbart
    assert "dort faellt beides" in k.als_zeile()


def test_konflikt_ohne_ueberschneidung_wird_nicht_gemeldet() -> None:
    """Zwei Gates, die sich ueberlappen, sind kein Konflikt."""
    friedlich = Reglerleiter(
        "friedlich",
        (
            Stellung(14.0, 149, 10.36, 7.17, 10, 11, (LATTE,)),
            Stellung(19.3, 152, 14.83, 9.87, 11, 11),
            Stellung(25.0, 152, 19.19, 13.74, 10, 11, (JAHR,)),
        ),
    )
    assert friedlich.konflikte() == ()


def test_konflikt_mit_ueberlappenden_grenzen_hat_luecke_null() -> None:
    """Halten beide an derselben Sprosse, ist die Luecke null - kein Streit."""
    k = Konflikt(JAHR, LATTE, 22.0, 22.0)
    assert k.luecke == 0.0
    assert k.benachbart


def test_konflikt_wird_in_beiden_richtungen_gefunden() -> None:
    """Egal, welches Gate zuerst in ``je_offen`` steht."""
    umgekehrt = Reglerleiter(
        "umgekehrt",
        (
            Stellung(14.0, 149, 10.36, 7.17, 10, 11, (JAHR,)),
            Stellung(25.0, 152, 19.19, 13.74, 10, 11, (LATTE,)),
        ),
    )
    streit = umgekehrt.konflikte()
    assert len(streit) == 1
    assert (streit[0].unten, streit[0].oben) == (LATTE, JAHR)


# --- Was Nachmessen noch bringen kann ---------------------------------------


def test_klaerung_lohnt_nicht_wenn_ein_gate_ueberall_offen_steht() -> None:
    assert not spot().klaerung_lohnt()
    assert not perpetual().klaerung_lohnt()


def test_klaerung_lohnt_wenn_jedes_gate_irgendwo_haelt() -> None:
    ohne_sperre = Reglerleiter(
        "ohne Sperre",
        (
            Stellung(14.0, 149, 10.36, 7.17, 10, 11, (LATTE,)),
            Stellung(25.0, 152, 19.19, 13.74, 10, 11, (JAHR,)),
        ),
    )
    assert ohne_sperre.klaerung_lohnt()
    assert "ist ungeklaert" in ohne_sperre.urteil()


def test_selbstsperrend_nennt_den_deflated_sharpe() -> None:
    assert spot().selbstsperrend() == (DSR,)


def test_selbstsperrend_nennt_kein_gate_ohne_zaehlerbezug() -> None:
    nur_latte = Reglerleiter(
        "nur Messlatte",
        (
            Stellung(14.0, 149, 10.36, 7.17, 10, 11, (LATTE,)),
            Stellung(25.0, 152, 19.19, 13.74, 10, 11, (LATTE,)),
        ),
    )
    assert nur_latte.immer_offen() == (LATTE,)
    assert nur_latte.selbstsperrend() == ()
    assert "Versuchszaehler" not in nur_latte.urteil()


def test_drawdown_und_messlatte_ueberschneiden_sich_bei_22() -> None:
    """Am Spot-Punkt halten beide bei 22,0 - das ist kein Konflikt."""
    leiter = spot()
    assert leiter.haltebereich(RUECK) == (14.0, 22.0)
    assert leiter.haltebereich(LATTE) == (22.0, 32.0)
    assert not [k for k in leiter.konflikte() if {k.unten, k.oben} == {RUECK, LATTE}]


def test_perpetual_hat_drei_konflikte() -> None:
    paare = {(k.unten, k.oben) for k in perpetual().konflikte()}
    assert paare == {(JAHR, LATTE), (PLATEAU, LATTE), (RUECK, LATTE)}


def test_urteil_am_spot_punkt_nennt_sperre_und_zaehler() -> None:
    text = spot().urteil()
    assert "ist zu" in text
    assert DSR in text
    assert "Versuchszaehler" in text
    assert "Zwischenstellung" in text


def test_urteil_ohne_fenster_und_ohne_konflikt_nennt_die_luecke() -> None:
    unvollstaendig = Reglerleiter(
        "unvollstaendig",
        (
            Stellung(14.0, 149, 10.36, 7.17, 10, 11, (LATTE,)),
            Stellung(19.3, 152, 14.83, 9.87, 10, 11, (JAHR,)),
            Stellung(25.0, 152, 19.19, 13.74, 10, 11, (LATTE,)),
        ),
    )
    assert unvollstaendig.fenster() == ()
    assert unvollstaendig.immer_offen() == ()
    assert unvollstaendig.konflikte() == ()
    assert "unvollstaendige Messung" in unvollstaendig.urteil()


# --- Klaerungskosten --------------------------------------------------------


def test_klaerungskosten_sind_negativ() -> None:
    """Gemessen: fuenf Halbschritte kosten 0,0031 am Deflated Sharpe."""
    k = Klaerungskosten(
        stellungen=5, versuche_jetzt=198, dsr_jetzt=0.8640, dsr_danach=0.8609
    )
    assert k.versuche_danach == 203
    assert k.preis == pytest.approx(-0.0031, abs=1e-6)
    assert k.luecke_danach == pytest.approx(0.0891, abs=1e-6)


def test_klaerungskosten_bis_zum_budgetende() -> None:
    k = Klaerungskosten(
        stellungen=32, versuche_jetzt=198, dsr_jetzt=0.8640, dsr_danach=0.8448
    )
    assert k.versuche_danach == 230
    assert k.preis < 0
    assert k.luecke_danach > 0.95 - 0.8640


def test_klaerungskosten_zeile_nennt_beide_zahlen() -> None:
    zeile = Klaerungskosten(
        stellungen=5, versuche_jetzt=198, dsr_jetzt=0.8640, dsr_danach=0.8609
    ).als_zeile()
    assert "198 -> 203" in zeile
    assert "0.8640" in zeile and "0.8609" in zeile
    assert "-0.0031" in zeile


# --- Der Vergleich der Betriebspunkte ---------------------------------------


def test_vergleich_haelt_den_schluss_aus_befund_21() -> None:
    v = Reglervergleich(alt=perpetual(), neu=spot())
    assert v.schluss_haelt()
    assert "Der Schluss haelt" in v.urteil()
    assert "keins" in v.urteil()


def test_vergleich_nennt_die_verschobenen_stellungen() -> None:
    v = Reglervergleich(alt=perpetual(), neu=spot())
    assert v.verschoben() == ((19.3, 7, 9), (22.0, 7, 9), (32.0, 5, 7))
    assert "3 von 7 Stellungen" in v.urteil()


def test_vergleich_meldet_gebrochenen_schluss() -> None:
    besser = Reglerleiter(
        "Vola-Ziel (erfunden)",
        (
            Stellung(14.0, 149, 10.36, 7.17, 9, 11, (LATTE, DSR)),
            Stellung(19.3, 152, 14.83, 9.87, 11, 11),
        ),
    )
    v = Reglervergleich(alt=perpetual(), neu=besser)
    assert not v.schluss_haelt()
    assert "haelt nicht" in v.urteil()
    assert "korrigiert" in v.urteil()


def test_vergleich_ohne_zweite_leiter_sagt_das() -> None:
    v = Reglervergleich(alt=perpetual(), neu=Reglerleiter("nichts"))
    assert "Vergleich fehlt" in v.urteil()


def test_vergleich_ohne_verschiebung_sagt_das_auch() -> None:
    v = Reglervergleich(alt=perpetual(), neu=perpetual())
    assert v.verschoben() == ()
    assert "keine Stellung steht anders da" in v.urteil()


# --- Die Regler, die schon einmal abgefahren wurden --------------------------


def test_arten_kennt_beide_befunde() -> None:
    assert ARTEN["vola"].befund == 21
    assert ARTEN["ziel"].befund == 46


def test_leiter_aus_befund_21_hat_sieben_stellungen() -> None:
    assert ARTEN["vola"].stellungen() == (14.0, 16.0, 19.3, 22.0, 25.0, 28.0, 32.0)


def test_leiter_aus_befund_46_hat_sechs_stellungen() -> None:
    assert ARTEN["ziel"].stellungen() == (10.0, 20.0, 30.0, 50.0, 100.0, 200.0)


def test_vola_regler_setzt_das_vola_ziel() -> None:
    genom = spitzenkandidat()
    gedreht = ARTEN["vola"].setzen(genom, 25.0)
    assert gedreht.sizing.target_vol_pct == 25.0
    assert genom.sizing.target_vol_pct != 25.0, "das Original bleibt unberuehrt"


def test_ziel_regler_setzt_das_gewinnziel() -> None:
    genom = spitzenkandidat()
    gedreht = ARTEN["ziel"].setzen(genom, 50.0)
    assert gedreht.targets[0].rr == 50.0
    assert gedreht.targets[0].portion == genom.targets[0].portion
    assert genom.targets[0].rr != 50.0, "das Original bleibt unberuehrt"


def test_ziel_regler_laesst_weitere_stufen_stehen() -> None:
    """Gedreht wird die erste Stufe; was dahinter steht, bleibt."""
    genom = spitzenkandidat()
    zwei = genom.model_copy(
        update={
            "targets": [
                genom.targets[0].model_copy(update={"rr": 5.0, "portion": 0.5}),
                genom.targets[0].model_copy(update={"rr": 9.0, "portion": 0.5}),
            ]
        }
    )
    gedreht = ARTEN["ziel"].setzen(zwei, 7.0)
    assert [t.rr for t in gedreht.targets] == [7.0, 9.0]


def test_ziel_regler_ohne_gewinnziel_sagt_das() -> None:
    genom = spitzenkandidat().model_copy(update={"targets": []})
    with pytest.raises(ValueError, match="kein Gewinnziel"):
        ARTEN["ziel"].setzen(genom, 50.0)


def test_unbekannter_regler_wird_zurueckgewiesen() -> None:
    erfunden = Reglerart("stopweite", "Stop-Weite", "%", "2,4,6", 28)
    with pytest.raises(ValueError, match="Unbekannter Regler"):
        erfunden.setzen(spitzenkandidat(), 4.0)


# --- Was der Regler ueberhaupt bewegt (Befund 129) ---------------------------


def mit_dsr(*paare: tuple[float, float, int, tuple[str, ...]]) -> Reglerleiter:
    """Eine Leiter, bei der jede Sprosse ihren Deflated Sharpe mitbringt."""
    return Reglerleiter(
        "mit Werten",
        tuple(
            Stellung(w, 152, 14.0, 10.0, b, 11, offen, dsr=d)
            for w, d, b, offen in paare
        ),
    )


def test_hub_ist_die_spanne_ueber_die_ganze_leiter() -> None:
    leiter = mit_dsr(
        (10.0, 0.7360, 8, (DSR,)),
        (20.0, 0.8080, 7, (DSR,)),
        (200.0, 0.0470, 7, (DSR,)),
    )
    assert leiter.hub() == pytest.approx(0.8080 - 0.0470)


def test_hub_braucht_zwei_gemessene_sprossen() -> None:
    assert mit_dsr((10.0, 0.7360, 8, (DSR,))).hub() is None
    assert spot().hub() is None, "die Leitern aus Befund 128 tragen keine Werte"


def test_reserve_misst_zur_schwelle_und_waehlt_nichts_aus() -> None:
    leiter = mit_dsr((10.0, 0.7360, 8, (DSR,)), (20.0, 0.8080, 7, (DSR,)))
    assert leiter.reserve() == pytest.approx(0.95 - 0.8080)
    assert leiter.reserve(schwelle=0.80) == pytest.approx(-0.0080)


def test_reserve_ohne_werte_ist_none() -> None:
    assert spot().reserve() is None


def test_regler_traegt_nicht_wenn_der_hub_kleiner_ist_als_die_reserve() -> None:
    """Der Fall aus Befund 21: bewegt 0,024, es fehlen 0,159."""
    schmal = mit_dsr((14.0, 0.7670, 9, (DSR,)), (32.0, 0.7910, 5, (DSR,)))
    assert schmal.hub() == pytest.approx(0.0240)
    assert schmal.reserve() == pytest.approx(0.1590)
    assert schmal.traegt_der_regler() is False


def test_regler_traegt_wenn_der_hub_reicht() -> None:
    weit = mit_dsr((10.0, 0.8080, 8, (DSR,)), (200.0, 0.0470, 7, (DSR,)))
    assert weit.traegt_der_regler() is True


def test_traegt_ohne_messung_ist_none() -> None:
    assert spot().traegt_der_regler() is None


def test_urteil_nennt_hub_und_reserve_wenn_der_regler_nicht_traegt() -> None:
    schmal = mit_dsr((14.0, 0.7670, 9, (DSR,)), (32.0, 0.7910, 5, (DSR,)))
    text = schmal.urteil()
    assert "traegt nicht so weit" in text
    assert "0.0240" in text and "0.1590" in text


def test_urteil_ohne_werte_bleibt_beim_alten_wortlaut() -> None:
    text = spot().urteil()
    assert "ist zu" in text
    assert "traegt nicht" not in text


def test_zeile_zeigt_den_dsr_wenn_er_gemessen_ist() -> None:
    mit = Stellung(30.0, 152, 15.15, 9.87, 9, 11, (DSR,), dsr=0.8712)
    assert "0.8712" in mit.als_zeile()
    ohne = Stellung(30.0, 152, 15.15, 9.87, 9, 11, (DSR,))
    assert "0.8712" not in ohne.als_zeile()
    assert "9/11" in ohne.als_zeile()
