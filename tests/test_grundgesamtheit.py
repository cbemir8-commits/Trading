"""Zwei Grundgesamtheiten in einer Rechnung - Befund 393.

Befund 392 schloss, alle drei Schaetzer der Ideenstreuung seien erst bei **4 bis
8** unabhaengigen Ziehungen mit dem Bestwert vereinbar und nicht bei 203 -
gelesen als Auskunft darueber, dass der Versuchszaehler fuer die Rueckrechnung
die falsche Zahl ist.

**Das war ein Kategorienfehler.**

Nachgemessen am Tageskatalog (19 Regeln, Spot, Versuchsstand 203):

    beobachteter Bestwert der Menge      +0,3274
    erwartet bei 19 Ziehungen            +0,3006     Unterschied 0,027
    Bestand (Spot, Reihe, je Trade)      +0,2708     -> **darunter**

Die Menge erklaert sich also selbst. Der Bestand liegt unter ihrem Bestwert, und
fuenf Katalogregeln sind besser - er ist keine Ziehung aus ihr. Einen Wert eine
Streuung ueber dem Mittel erklaeren naturgemaess wenige Ziehungen, und das ist
keine Neuigkeit ueber den Zaehler.

**Nebenbei beantwortet das eine Frage, die niemand aufgeschrieben hatte:** Warum
ist der Bestand der Kandidat, wenn fuenf Regeln mehr Guete je Trade haben?

    Regel                      je Trade   n_eff    Guete    Latte   raeumt
    Donchian-Ausbruch 55/20     +0,3262      58    2,484    3,564    0,697
    Grosser Trendausbruch       +0,3215      57    2,428    3,980    0,610
    Bestand (Spot, Reihe)       +0,2708     115    2,904    3,618    0,803

Weil die Latte an der **Guete** haengt, und die ist Sharpe mal Wurzel aus n_eff.
"""

from __future__ import annotations

import inspect
import pathlib

import pytest

from research.referenz import SPOTPUNKT
from research.verbund import noetige_guete
from research.wettrennen import Aktenschaetzung, aus_dem_katalog, extremwert
from research.zwischenstand import lies, zusammen

#: Gemessen, siehe Kopf.
KATALOG_BESTWERT = 0.3274
KATALOG_ERWARTET = 0.3006
BESTAND_RAEUMT = 0.803
DONCHIAN_RAEUMT = 0.697


def _katalog() -> Aktenschaetzung:
    stuecke = sorted(
        p
        for p in pathlib.Path("reports/vorratsdecke").glob("*.jsonl")
        if str(lies(p)[0].get("stueck", "")).endswith("/6")
    )
    _kopf, zeilen = zusammen(stuecke)
    return aus_dem_katalog(zeilen)


class TestDieMengeErklaertSichSelbst:
    def test_ihr_eigener_bestwert_steht_in_der_schaetzung(self) -> None:
        """Ohne ihn ist nicht zu sagen, ob eine Frage diese Menge betrifft -
        und genau daran ist der Schluss aus 392 gescheitert."""
        s = _katalog()

        assert s.hoechster == pytest.approx(KATALOG_BESTWERT, abs=0.0005)

    def test_und_passt_zu_mittel_und_streuung(self) -> None:
        s = _katalog()

        assert s.erwarteter_bestwert() == pytest.approx(
            KATALOG_ERWARTET, abs=0.001
        )
        assert s.erklaert_sich_selbst() is True

    def test_eine_menge_ohne_streuung_sagt_nichts_darueber(self) -> None:
        """``None`` heisst nicht nachweisbar - und dann ist auch die Probe
        nicht zu machen."""
        s = Aktenschaetzung(
            anzahl=3, mittel=0.1, beobachtet=0.02, rauschen=0.01,
            streuung=None, hoechster=0.12,
        )

        assert s.erwarteter_bestwert() is None
        assert s.erklaert_sich_selbst() is None


class TestDieWacheGegenMeinenFehler:
    def test_der_bestand_ist_fremd_in_dieser_menge(self) -> None:
        s = _katalog()

        assert s.fremd(SPOTPUNKT.guete) is True
        assert SPOTPUNKT.guete < s.hoechster

    def test_ein_wert_ueber_dem_bestwert_ist_es_nicht(self) -> None:
        s = _katalog()

        assert s.fremd(0.40) is False

    def test_die_zahl_selbst_bleibt_richtig_gerechnet(self) -> None:
        """``versoehnt_bei`` rechnet weiter - sie ist nicht falsch, sie
        beantwortet nur eine andere Frage. Deshalb wird sie nicht entfernt,
        sondern eingeordnet."""
        s = _katalog()

        assert s.versoehnt_bei(SPOTPUNKT.guete) is not None
        assert s.versoehnt_bei(SPOTPUNKT.guete) < 10

    def test_der_befehl_sagt_es_im_klartext(self) -> None:
        import cli

        quelle = inspect.getsource(cli.rennen)

        assert "akte.fremd(kandidat.sharpe_je_trade)" in quelle
        assert "keine Auskunft ueber den Zaehler" in quelle


class TestWarumDerBestandDerKandidatIst:
    """Die Frage, die niemand aufgeschrieben hatte."""

    @staticmethod
    def _bewertet(z: dict) -> tuple[float, float, float]:
        guete = z["sr_je_trade"] * z["n_eff"] ** 0.5
        latte = noetige_guete(
            z["n_eff"], 203, schiefe=z.get("schiefe"), woelbung=z.get("woelbung")
        )
        return guete, latte, guete / latte

    def test_sechs_regeln_haben_mehr_guete_je_trade(self) -> None:
        """**Sechs von 19** - und fuenf von 18 in der Einzeldatei, denn die
        neunzehnte Regel ('Nur mit der Drift', +0,2716) ist genau eine von
        ihnen. Mein erster Entwurf schrieb "fuenf" aus der Top-5-Ausgabe der
        Einzeldatei ab, und der Test hat es gefunden: dieselbe Lehre wie der
        ganze Befund - sagen, welche Menge gemeint ist.
        """
        stuecke = sorted(
            p
            for p in pathlib.Path("reports/vorratsdecke").glob("*.jsonl")
            if str(lies(p)[0].get("stueck", "")).endswith("/6")
        )
        _k, zeilen = zusammen(stuecke)
        besser = [
            z
            for z in zeilen
            if z.get("ergebnis") == "gemessen"
            and z["sr_je_trade"] > SPOTPUNKT.guete
        ]

        assert len(besser) == 6

    def test_aber_keine_mehr_guete(self) -> None:
        stuecke = sorted(
            p
            for p in pathlib.Path("reports/vorratsdecke").glob("*.jsonl")
            if str(lies(p)[0].get("stueck", "")).endswith("/6")
        )
        _k, zeilen = zusammen(stuecke)
        gemessen = [z for z in zeilen if z.get("ergebnis") == "gemessen"]
        beste = max(self._bewertet(z)[0] for z in gemessen)
        bestand = SPOTPUNKT.guete * SPOTPUNKT.effektiv**0.5

        assert beste == pytest.approx(2.484, abs=0.005)
        assert bestand == pytest.approx(2.904, abs=0.005)
        assert bestand > beste

    def test_und_keine_raeumt_so_viel_ihrer_latte(self) -> None:
        stuecke = sorted(
            p
            for p in pathlib.Path("reports/vorratsdecke").glob("*.jsonl")
            if str(lies(p)[0].get("stueck", "")).endswith("/6")
        )
        _k, zeilen = zusammen(stuecke)
        gemessen = [z for z in zeilen if z.get("ergebnis") == "gemessen"]
        quoten = [self._bewertet(z)[2] for z in gemessen]
        latte = noetige_guete(
            SPOTPUNKT.effektiv, SPOTPUNKT.versuche,
            schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung,
        )
        bestand = SPOTPUNKT.guete * SPOTPUNKT.effektiv**0.5 / latte

        assert max(quoten) == pytest.approx(DONCHIAN_RAEUMT, abs=0.005)
        assert bestand == pytest.approx(BESTAND_RAEUMT, abs=0.005)
        assert bestand > max(quoten)


class TestWasImRegisterSteht:
    def test_der_eintrag_benennt_den_kategorienfehler(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 393)

        assert "Kategorienfehler" in eintrag.ergebnis
        assert "0,3274" in eintrag.ergebnis
        assert "0,3006" in eintrag.ergebnis

    def test_und_haelt_den_rest_von_392_aufrecht(self) -> None:
        """Nicht der Befund war falsch, nur ein Schluss daraus. Ein Eintrag,
        der jetzt 'alles anders' sagte, waere die Gegenuebertreibung."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 393)

        assert "Der Rest von 392 steht unveraendert" in eintrag.ergebnis
        assert "unter der Nullstreuung" in eintrag.ergebnis

    def test_und_die_guetetafel(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 393)

        for zahl in ("2,484", "2,904", "0,697", "0,803"):
            assert zahl in eintrag.ergebnis, zahl

    def test_und_392_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 392).zuletzt == 393

    def test_das_budget_nimmt_die_vier_bis_acht_zurueck(self) -> None:
        from research.stand import Suchbudget

        text = Suchbudget.__doc__ or ""

        assert "keine Auskunft ueber den Zaehler" in text
        assert "4 bis 8" in text, "die ueberholte Lesart bleibt als Vermerk"
        assert "bleibt richtig" in text, (
            "dass der Zaehler Hypothesen zaehlt, stimmt weiter - es war nur "
            "nicht hiermit gezeigt"
        )

    def test_der_statusschirm_erklaert_jetzt_den_kandidaten(self) -> None:
        from research.stand import Lage

        quelle = inspect.getsource(Lage)

        assert "0,803" in quelle
        assert "warum er der Kandidat ist" in quelle
        assert "nicht bei 203" not in quelle, "die 392er Fassung ist ersetzt"


def test_der_erwartete_bestwert_waechst_mit_den_ziehungen() -> None:
    """Die Rechnung dahinter, an einer Stelle gepruefte: mehr Ziehungen, mehr
    erwartetes Maximum - und zwar mit ``c(N)``."""
    s = _katalog()

    assert s.erwarteter_bestwert(5) < s.erwarteter_bestwert(50)
    assert s.erwarteter_bestwert(19) == pytest.approx(
        s.mittel + s.streuung * extremwert(19), abs=1e-9
    )
