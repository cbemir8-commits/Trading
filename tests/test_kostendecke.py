"""Die Decke war auf alter Basis gerechnet - Befund 443.

``research/decke.py`` ist das Modul, das sagt, **wo noch Evidenz herkommen
kann und wo nicht mehr**. Sein Kopf trug eine Tafel auf ``n = 152`` und den
Satz:

    Es fehlen 0,0692 - und es gibt keine Kosten mehr, die man noch wegnehmen
    koennte. Was nach dem Funding noch im Topf war, sind 0,0168; die Luecke
    ist das Vierfache davon.

Das ist keine Aufzeichnung eines Laufs, sondern eine Aussage ueber den
**Jetzt**-Stand - und sie las um das Fuenffache zu guenstig. Der Befehl
selbst rechnet laengst richtig; die Stelle, die auf die alte Basis hinwies,
stand 170 Zeilen unter der Tafel.

**Gemessen, nicht geschaetzt**: Dieser Test faehrt ``cli decke`` und
``cli decke --anschlag``. Beide kosten keinen Versuch - dieselbe Strategie,
dieselben Daten, veraendert werden die Handelskosten.
"""

from __future__ import annotations

import re

import pytest

#: Die Kostenfamilie auf heutiger Basis: Name, DSR, bestandene Gates.
#:
#: **Gemessen** (Befund 443), nicht aus einer Ausgabe zurueckgerechnet - die
#: Lehre aus Befund 442. Der Datentest unten faehrt den Befehl und vergleicht.
HEUTE: tuple[tuple[str, float, int], ...] = (
    ("Perpetual wie gebaut", 0.4579, 7),
    ("Spot wie gebaut", 0.5826, 9),
    ("Spot ohne Slippage", 0.5889, 9),
    ("Spot ohne Gebuehren", 0.6015, 9),
    ("Spot voellig kostenfrei", 0.6079, 9),
)

#: Anschlag, Schwelle, fehlender Rest.
ANSCHLAG, SCHWELLE, LUECKE = 0.6079, 0.95, 0.3421

#: Die Stufen unterhalb der Kosten (``--anschlag``, Befund 127).
BREMSEN: tuple[tuple[str, float], ...] = (
    ("Spot wie gebaut", 0.5826),
    ("+ Kosten null (Befund 111)", 0.6079),
    ("+ ohne Terminkalender", 0.6301),
    ("+ Limits verfallen nie", 0.6301),
    ("+ ohne Risk-Officer", 0.6181),
)

#: In **jeder** Zeile dieselben zwei - das ist der tragende Befund.
OFFEN = "Messlatte, Deflated Sharpe"


def _glatt(text: str) -> str:
    """Ueber die Umbrueche hinweg (Befund 420/430).

    Die Konsole bricht Zeilen nach Terminalbreite, und eine Zeichenkette
    darueber zu pruefen bricht, sobald die Breite sich aendert.
    """
    return " ".join(text.split())


def _stufen(text: str, namen) -> dict[str, tuple[float, int]]:
    """DSR und bestandene Gates je benannter Stufe."""
    aus = {}
    for name in namen:
        treffer = re.search(
            re.escape(name) + r" DSR (\d\.\d+) Guete \d\.\d+ (\d+)/(\d+) Gates",
            text,
        )
        if treffer:
            aus[name] = (float(treffer.group(1)), int(treffer.group(2)))
    return aus


# **Fixtures auf Modulebene, nicht in der Klasse** (Befund 426/429): Eine
# Fixture mit eigenem Scope als Instanzmethode laeuft genau einmal pro Test
# und nicht einmal pro Modul - der Lauf wuerde sich vervielfachen.
def _fahre(*args: str) -> str:
    from typer.testing import CliRunner

    from cli import app

    ergebnis = CliRunner().invoke(app, ["decke", *args])
    if ergebnis.exit_code != 0:
        pytest.fail(f"'cli decke {' '.join(args)}' endete mit "
                    f"{ergebnis.exit_code}:\n{ergebnis.output[-2000:]}")
    return _glatt(ergebnis.output)


@pytest.fixture(scope="module")
def kostenlauf() -> str:
    return _fahre()


@pytest.fixture(scope="module")
def bremsenlauf() -> str:
    return _fahre("--anschlag")


@pytest.mark.daten
@pytest.mark.langsam
class TestDieKostenfamilieAufHeutigerBasis:
    def test_die_fuenf_stufen_treffen_den_modulkopf(self, kostenlauf) -> None:
        """Die Tafel im Kopf ist ein Abbild dieses Laufs, keine Abschrift."""
        gemessen = _stufen(kostenlauf, [n for n, _, _ in HEUTE])

        assert set(gemessen) == {n for n, _, _ in HEUTE}, sorted(gemessen)
        for name, dsr, gates in HEUTE:
            ist_dsr, ist_gates = gemessen[name]
            assert ist_dsr == pytest.approx(dsr, abs=0.001), name
            assert ist_gates == gates, name

    def test_jede_wegnahme_kann_nur_helfen(self, kostenlauf) -> None:
        """Eine Kostenstufe, die den Wert senkt, waere ein Rechenfehler -
        weniger Kosten koennen denselben Lauf nicht schlechter machen."""
        gemessen = _stufen(kostenlauf, [n for n, _, _ in HEUTE])
        reihe = [gemessen[n][0] for n, _, _ in HEUTE]

        assert reihe == sorted(reihe), reihe

    def test_der_anschlag_und_die_luecke_stehen_so_da(self, kostenlauf) -> None:
        treffer = re.search(
            r"Anschlag bei (\d\.\d+), Schwelle (\d\.\d+) - es fehlen (\d\.\d+)",
            kostenlauf,
        )

        assert treffer, kostenlauf[-600:]
        assert float(treffer.group(1)) == pytest.approx(ANSCHLAG, abs=0.001)
        assert float(treffer.group(2)) == pytest.approx(SCHWELLE, abs=1e-9)
        assert float(treffer.group(3)) == pytest.approx(LUECKE, abs=0.001)

    def test_die_luecke_ist_das_vierkommaneunfache_der_alten(self) -> None:
        """**Die Korrektur aus 443.** Der Kopf behauptete 0,0692."""
        verhaeltnis = LUECKE / 0.0692

        assert verhaeltnis == pytest.approx(4.9, abs=0.1)

    def test_und_das_dreizehnfache_des_topfes(self, kostenlauf) -> None:
        """Der Topf ist auch groesser geworden - die Luecke mehr."""
        gemessen = _stufen(kostenlauf, [n for n, _, _ in HEUTE])
        topf = gemessen["Spot voellig kostenfrei"][0] - gemessen["Spot wie gebaut"][0]

        assert topf == pytest.approx(0.0253, abs=0.001)
        assert LUECKE / topf > 13.0, LUECKE / topf


@pytest.mark.daten
@pytest.mark.langsam
class TestKostenAbschaltenKauftKeinGate:
    """**Der tragende Teil von Befund 443.**

    Die alte Tafel gewann bei null Gebuehren ein zehntes Gate (10/11). Heute
    stehen alle vier Spot-Zeilen auf 9/11 - "erschoepft" heisst jetzt
    *erschoepft, ohne dass ein einziges Gate kippt*.
    """

    def test_alle_spot_zeilen_stehen_auf_neun(self, kostenlauf) -> None:
        gemessen = _stufen(kostenlauf, [n for n, _, _ in HEUTE])
        spot = {n: g for n, (_, g) in gemessen.items() if n.startswith("Spot")}

        assert len(spot) == 4
        assert set(spot.values()) == {9}, spot

    def test_auch_ohne_jede_bremse_bleibt_es_bei_neun(self, bremsenlauf) -> None:
        """Ohne Kosten, ohne Terminkalender, ohne Verfallsfrist und ohne
        Risk-Officer - und es kippt nichts (Befund 127)."""
        for name, _ in BREMSEN:
            treffer = re.search(
                re.escape(name) + r" \d+ Trades Guete \d\.\d+ DSR (\d\.\d+) "
                r"(\d+)/(\d+) offen: (.{30})",
                bremsenlauf,
            )
            assert treffer, name
            assert int(treffer.group(2)) == 9, name
            assert treffer.group(4).startswith(OFFEN), (name, treffer.group(4))

    def test_der_hoechste_messwert_ueberhaupt_bleibt_weit_darunter(
        self, bremsenlauf
    ) -> None:
        """Mit **jeder** abschaltbaren Reibung ab ist 0,6301 das Beste, was
        gemessen wurde - gegen eine Schwelle von 0,95."""
        werte = []
        for name, _ in BREMSEN:
            treffer = re.search(
                re.escape(name) + r" \d+ Trades Guete \d\.\d+ DSR (\d\.\d+)",
                bremsenlauf,
            )
            assert treffer, name
            werte.append(float(treffer.group(1)))

        assert max(werte) == pytest.approx(0.6301, abs=0.001)
        assert max(werte) < SCHWELLE - 0.3

    def test_der_risk_officer_kostet_nichts(self, bremsenlauf) -> None:
        """Gegenprobe zur bequemen Lesart: Ihn abzuschalten macht es
        **schlechter**, also ist die Sicherheit nicht der Preis."""
        gemessen = {}
        for name, _ in BREMSEN:
            treffer = re.search(
                re.escape(name) + r" \d+ Trades Guete \d\.\d+ DSR (\d\.\d+)",
                bremsenlauf,
            )
            gemessen[name] = float(treffer.group(1))

        assert gemessen["+ ohne Risk-Officer"] < gemessen["+ Limits verfallen nie"]


@pytest.mark.daten
@pytest.mark.langsam
class TestZweiWegeZumselbenPunkt:
    def test_die_spot_zeile_trifft_den_massgeblichen_punkt(
        self, kostenlauf
    ) -> None:
        """**Und das ist kein Identitaetsanspruch** (Befund 428).

        'cli decke' meldet fuer 'Spot wie gebaut' eine Guete von 0,2853 ueber
        158 Trades; 'referenz.SPOTPUNKT' fuehrt 0,2708 ueber 156 gehandelte
        bei 115 wirksamen Beobachtungen. Das sind **zwei Groessen**, nicht
        eine - sie landen im Deflated Sharpe nur nahe beieinander. Geprueft
        wird deshalb Naehe, nicht Gleichheit.
        """
        from research.referenz import SPOTPUNKT

        gemessen = _stufen(kostenlauf, ["Spot wie gebaut"])["Spot wie gebaut"]

        assert gemessen[0] == pytest.approx(SPOTPUNKT.dsr, abs=0.001)
        assert gemessen[1] == SPOTPUNKT.bestanden


class TestDerModulkopfNenntDieHeutigeBasis:
    """Ohne Speicher pruefbar: Steht die Korrektur ueberhaupt im Kopf, und
    steht sie **vor** dem Hinweis, den sie ersetzt?"""

    def test_die_heutige_tafel_steht_im_kopf(self) -> None:
        from research import decke

        doc = _glatt(decke.__doc__ or "")

        assert "Nachgemessen auf heutiger Basis" in doc
        for name, dsr, _ in HEUTE:
            assert f"{name} DSR {dsr:.4f}".replace(".", ",") in doc, name

    def test_und_benennt_die_alte_zahl_als_korrigiert(self) -> None:
        from research import decke

        doc = _glatt(decke.__doc__ or "")

        assert "nicht 0,0692, sondern **0,3421**" in doc
        assert "kauft kein Gate mehr" in doc

    def test_die_alte_tafel_bleibt_als_aufzeichnung_stehen(self) -> None:
        """Geschichte wird nicht umgeschrieben - sie wird datiert."""
        from research import decke

        doc = _glatt(decke.__doc__ or "")

        assert "DSR 0,8640" in doc
        assert "rechnet mit n = 152" in doc


class TestDerVergleichWirdGerechnet:
    """**Der Satz, der eine Messung vortaeuschte** (Befund 443).

    ``urteil()`` schloss aus "'Kosten null' ist nicht das Maximum" auf *"es
    gibt eine Bremse, die mehr wert ist als alle Kosten zusammen"*. Das ist
    keine Folgerung, sondern eine zweite Behauptung - und auf den heutigen
    Zahlen eine falsche: Die Bremse traegt +0,0222, die Kosten zusammen
    +0,0253.

    Dass der Anschlag **nicht** haelt, bleibt richtig. Nur die Groesse war
    erfunden.
    """

    @staticmethod
    def _heute():
        from research.decke import Reibungsprobe, Stufe

        zwei = ("Messlatte", "Deflated Sharpe")
        return Reibungsprobe(
            stufen=(
                Stufe("Spot wie gebaut", 158, 0.2853, 0.5826, 9, 11, zwei),
                Stufe("+ Kosten null (Befund 111)", 158, 0.2887, 0.6079, 9, 11, zwei),
                Stufe("+ ohne Terminkalender", 160, 0.2859, 0.6301, 9, 11, zwei),
                Stufe("+ Limits verfallen nie", 160, 0.2859, 0.6301, 9, 11, zwei),
                Stufe("+ ohne Risk-Officer", 162, 0.2831, 0.6181, 9, 11, zwei),
            )
        )

    def test_der_anschlag_haelt_heute_nicht_mehr(self) -> None:
        """Befund 127 hat das Gegenteil gemessen: *"Jede weitere Abschaltung
        macht es schlechter."* Auf heutiger Basis kehrt es sich um."""
        probe = self._heute()

        assert not probe.anschlag_haelt
        assert probe.hoechster.name == "+ ohne Terminkalender"

    def test_die_bremse_ist_weniger_wert_als_alle_kosten(self) -> None:
        """Die Zahl, die der alte Satz behauptet hat - jetzt gerechnet."""
        probe = self._heute()

        assert probe.gewinn_durch_oeffnen() == pytest.approx(0.0222, abs=0.0001)
        assert probe.kostenwert() == pytest.approx(0.0253, abs=0.0001)
        assert probe.gewinn_durch_oeffnen() < probe.kostenwert()

    def test_und_das_urteil_sagt_es_so(self) -> None:
        text = self._heute().urteil()

        assert "Anschlag haelt nicht" in text
        assert "weniger wert als alle Kosten zusammen" in text
        assert "+0.0222" in text and "+0.0253" in text

    def test_der_alte_satz_steht_nicht_mehr_drin(self) -> None:
        """Er war nicht nur ungemessen, er war falsch - und ein ungemessener
        Satz, der zufaellig stimmt, bliebe trotzdem ungemessen."""
        text = self._heute().urteil()

        assert "mehr wert ist als alle Kosten zusammen" not in text

    def test_bei_einer_wirklich_groesseren_bremse_sagt_es_mehr(self) -> None:
        """Gegenprobe: Der Vergleich kennt beide Richtungen."""
        from research.decke import Reibungsprobe, Stufe

        probe = Reibungsprobe(
            stufen=(
                Stufe("Spot wie gebaut", 158, 0.2853, 0.5826, 9, 11),
                Stufe("+ Kosten null (Befund 111)", 158, 0.2887, 0.6079, 9, 11),
                Stufe("+ ohne Terminkalender", 200, 0.3000, 0.7000, 9, 11),
            )
        )

        assert "mehr wert als alle Kosten zusammen" in probe.urteil()

    def test_ohne_zeile_vor_dem_anschlag_wird_nichts_verglichen(self) -> None:
        """Keine Vergleichsgroesse heisst kein Vergleich - nicht eine
        geschaetzte."""
        from research.decke import Reibungsprobe, Stufe

        probe = Reibungsprobe(
            stufen=(
                Stufe("+ Kosten null (Befund 111)", 152, 0.2798, 0.8808, 10, 11),
                Stufe("+ ohne Risk-Officer", 200, 0.2900, 0.9400, 10, 11),
            )
        )

        assert probe.kostenwert() is None
        assert "wert als alle Kosten" not in probe.urteil()
        assert "gehoert entsprechend korrigiert" in probe.urteil()

    def test_an_den_zahlen_von_127_haelt_er_noch(self) -> None:
        """Und die Reihe von damals bleibt richtig gelesen - der Befund hat
        sich geaendert, nicht die Rechnung."""
        from research.decke import Reibungsprobe, Stufe

        probe = Reibungsprobe(
            stufen=(
                Stufe("Spot wie gebaut", 152, 0.2765, 0.8640, 9, 11),
                Stufe("+ Kosten null (Befund 111)", 152, 0.2798, 0.8808, 10, 11),
                Stufe("+ ohne Terminkalender", 154, 0.2770, 0.8762, 9, 11),
            )
        )

        assert probe.anschlag_haelt
        assert probe.gewinn_durch_oeffnen() < 0


@pytest.mark.daten
@pytest.mark.langsam
class TestAmEchtenLaufSagtDasUrteilDasselbe:
    def test_der_befehl_nennt_beide_groessen(self, bremsenlauf) -> None:
        """Der Beleg, dass die Korrektur nicht nur im Doppel steht."""
        assert "Anschlag haelt nicht" in bremsenlauf
        assert "weniger wert als alle Kosten zusammen" in bremsenlauf
        assert "mehr wert ist als alle Kosten zusammen" not in bremsenlauf

    def test_und_befund_127_hat_sich_umgekehrt(self, bremsenlauf) -> None:
        """Damals hielt der Anschlag und der Terminkalender hielt die
        Messlatte. Heute keines von beidem."""
        treffer = re.search(
            r"\+ ohne Terminkalender \d+ Trades Guete \d\.\d+ DSR (\d\.\d+) "
            r"(\d+)/(\d+) offen: (.{30})",
            bremsenlauf,
        )

        assert treffer, bremsenlauf[-800:]
        assert float(treffer.group(1)) > ANSCHLAG
        assert int(treffer.group(2)) == 9
        assert treffer.group(4).startswith(OFFEN)
