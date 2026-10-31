"""Die Haelften-Huerde des Scans ist eine Muenze - Befund 431.

``cli scan`` entscheidet, **ob sich Versuche lohnen**, und das ist die
teuerste Entscheidung des Projekts: Jede geprueffte Hypothese hebt die Huerde
des Deflated-Sharpe-Gates dauerhaft. Eine seiner Huerden lautet "in beiden
Haelften dasselbe Vorzeichen".

``haelften`` teilt bei ``laenge // 2``. Die Mitte haengt damit an **beiden**
Enden der Reihe - wandert ein Ende, wandert die Mitte, und die Huerde prueft
etwas anderes.

Gemessen auf der Zelle, die auf Viertelstundenkerzen den Fund trug (BTC, L16,
H16): Die erste Haelfte ruehrt sich nicht, die zweite dreht das Vorzeichen,
und das Urteil haelt nur in **5 von 11** Raendern.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.vorteilsscan import (
    KOSTEN_MAKER_MAKER,
    RANDSCHRITTE,
    Randprobe,
    pruefe_rand,
    pruefe_stabilitaet,
    urteil,
)


def _randprobe(*haelt: bool) -> Randprobe:
    return Randprobe(
        haelt_bei=tuple((f"rand {i}", x) for i, x in enumerate(haelt))
    )


class TestDieProbeZaehltRichtig:
    def test_alles_gehalten_traegt(self) -> None:
        probe = _randprobe(True, True, True)

        assert probe.traegt()
        assert (probe.gehalten, probe.geprueft) == (3, 3)
        assert "allen 3" in probe.beschreibe()

    def test_ein_kipper_genuegt(self) -> None:
        """Einstimmigkeit, und zwar mit Grund: Die Huerde ist binaer. Kippt
        ihr Urteil, hat sie nichts festgestellt."""
        probe = _randprobe(True, True, False)

        assert not probe.traegt()
        assert "2 von 3" in probe.beschreibe()
        assert "rand 2" in probe.beschreibe()

    def test_sie_nennt_die_gekippten(self) -> None:
        """Ein Anteil ohne die Stellen laesst den Leser nicht nachsehen."""
        probe = _randprobe(False, True, False)

        assert "rand 0" in probe.beschreibe()
        assert "rand 2" in probe.beschreibe()
        assert "rand 1" not in probe.beschreibe()

    def test_ohne_raender_traegt_nichts(self) -> None:
        """Gegenprobe gegen die stille Zustimmung: Eine Probe ohne Sprossen
        darf nicht als bestanden gelten."""
        assert not Randprobe(haelt_bei=()).traegt()


class TestDieLeiterGehtNachBeidenSeiten:
    def _reihe(self, n: int = 40_000) -> np.ndarray:
        schritt = np.random.default_rng(7).normal(0, 0.001, n)
        return np.exp(np.cumsum(schritt)) * 100

    def test_sie_prueft_voll_und_beide_enden(self) -> None:
        probe = pruefe_rand(self._reihe(), 16, 16, schritte=(5_000, 10_000))
        namen = [name for name, _ in probe.haelt_bei]

        assert namen[0] == "voll"
        assert "hinten 5k" in namen and "vorne 5k" in namen
        assert "hinten 10k" in namen and "vorne 10k" in namen
        assert len(namen) == 5

    def test_zu_grosse_schritte_fallen_weg(self) -> None:
        """Eine Sprosse, die mehr als die halbe Reihe wegnimmt, prueft
        nichts - sie darf nicht als gehalten mitzaehlen."""
        probe = pruefe_rand(self._reihe(2_000), 16, 16, schritte=(10_000,))

        assert [name for name, _ in probe.haelt_bei] == ["voll"]

    def test_die_vorgabe_geht_bis_fuenfzigtausend(self) -> None:
        assert RANDSCHRITTE == (10_000, 20_000, 30_000, 40_000, 50_000)


class TestDasUrteilNimmtSichZurueck:
    """Der Punkt des Befundes: Der Scan darf nicht zu Versuchen raten, wenn
    die Huerde am Rand kippt."""

    def _zelle(self, t: float, spanne: float):
        from research.vorteilsscan import Zelle

        return Zelle(
            rueckblick=16, halten=16, beobachtungen=14_356,
            spanne_pct=spanne, t_wert=t,
        )

    def _stabil_haelt(self):
        werte = np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.001, 20_000)))
        return pruefe_stabilitaet(werte, 16, 16)

    def test_ohne_randprobe_bleibt_es_wie_bisher(self) -> None:
        """Nicht geprueft ist etwas anderes als bestanden - aber das Urteil
        aendert sich dadurch nicht rueckwirkend."""
        from research.vorteilsscan import Stabilitaet

        zelle = self._zelle(-5.0, -0.0824)
        haelt = Stabilitaet(
            erste=self._zelle(-4.0, -0.08), zweite=self._zelle(-4.0, -0.08)
        )

        text = urteil(zelle, haelt, KOSTEN_MAKER_MAKER, gepruefte_zellen=1)

        # **Die Marke, nicht das Wort** (Befund 431): Der Verwerfungssatz
        # enthaelt "kein Fund", also trifft 'Fund' in text beide Faelle -
        # dieselbe Bruechigkeit, die 420 und 430 verzeichnet haben.
        assert text.startswith("Fund: t =")

    def test_mit_gekippter_randprobe_kein_fund(self) -> None:
        from research.vorteilsscan import Stabilitaet

        zelle = self._zelle(-5.0, -0.0824)
        haelt = Stabilitaet(
            erste=self._zelle(-4.0, -0.08), zweite=self._zelle(-4.0, -0.08)
        )

        text = urteil(
            zelle, haelt, KOSTEN_MAKER_MAKER,
            gepruefte_zellen=1, rand=_randprobe(True, False, True),
        )

        assert not text.startswith("Fund: t =")
        assert "haelt nicht am Rand" in text
        assert "Randeffekt, kein Fund" in text
        assert "Befund 431" in text

    def test_und_raet_nicht_zu_versuchen(self) -> None:
        """Der Satz, auf den es ankommt - er stand vorher unter dem Fund."""
        from research.vorteilsscan import Stabilitaet

        zelle = self._zelle(-5.0, -0.0824)
        haelt = Stabilitaet(
            erste=self._zelle(-4.0, -0.08), zweite=self._zelle(-4.0, -0.08)
        )

        text = urteil(
            zelle, haelt, KOSTEN_MAKER_MAKER,
            gepruefte_zellen=1, rand=_randprobe(False),
        )

        assert "Hier lohnen sich Versuche" not in text
        assert "auf das Ende der Reihe zu wetten" in text

    def test_mit_haltender_randprobe_bleibt_der_fund(self) -> None:
        """Gegenprobe: Die Probe verwirft nicht pauschal - dieselbe Regel,
        die 'Rotationsprobe' fuer sich festhaelt."""
        from research.vorteilsscan import Stabilitaet

        zelle = self._zelle(-5.0, -0.0824)
        haelt = Stabilitaet(
            erste=self._zelle(-4.0, -0.08), zweite=self._zelle(-4.0, -0.08)
        )

        text = urteil(
            zelle, haelt, KOSTEN_MAKER_MAKER,
            gepruefte_zellen=1, rand=_randprobe(True, True),
        )

        assert text.startswith("Fund: t =")
        assert "allen 2" in text


class TestDerScanRuftSieAuf:
    """Gebaut und nicht verdrahtet ist der Fehler, den dieses Register oft
    genug verzeichnet."""

    def _quelle(self) -> str:
        import inspect

        import cli

        return inspect.getsource(cli.scan)

    def test_er_rechnet_die_randprobe(self) -> None:
        assert "pruefe_rand(close, beste.rueckblick, beste.halten)" in self._quelle()

    def test_und_gibt_sie_ins_urteil(self) -> None:
        assert "rand=rand," in self._quelle()

    def test_nur_wenn_die_haelften_halten(self) -> None:
        """Vorher ist sie gegenstandslos und kostet elf Rechnungen ueber die
        ganze Reihe."""
        quelle = self._quelle()

        assert "if stabil.haelt" in quelle
        assert "else None" in quelle


# **Auf Modulebene, nicht in der Klasse** (Befund 426/428/429): Eine Fixture
# mit eigenem Scope als Instanzmethode ist ein Fehler, kein Warnhinweis - die
# Tests daran laufen dann nicht. Der Wächter aus 429 hat genau das hier
# gefangen, bevor es gepusht war; das vierte Mal, und das erste mechanisch.
@pytest.fixture(scope="module")
def btc_fein():
    from core.config import get_settings
    from core.models import Interval
    from data.store import CandleStore

    speicher = CandleStore(get_settings().paths.data_store)
    rahmen = speicher.read("BTCUSD_BITSTAMP", Interval("15"))
    if rahmen is None or rahmen.empty:
        pytest.skip("keine Viertelstundenkerzen im Speicher")
    return rahmen["close"].to_numpy(dtype=float)


@pytest.mark.daten
class TestAnDerZelleDieDenFundTrug:
    """Ohne diese Messung waere die Huerde eine Vermutung ueber einen Fall,
    der nie eingetreten ist."""

    def test_die_huerde_haelt_nicht_an_allen_raendern(self, btc_fein) -> None:
        probe = pruefe_rand(btc_fein, 16, 16)

        assert not probe.traegt()
        assert probe.geprueft == 11
        assert 3 <= probe.gehalten <= 8, probe.beschreibe()

    def test_die_erste_haelfte_ruehrt_sich_nicht(self, btc_fein) -> None:
        """Die Trennung, die den Befund traegt: Nicht die Zelle ist unruhig,
        sondern die zweite Haelfte."""
        erste = [
            pruefe_stabilitaet(btc_fein[:n], 16, 16).erste.t_wert
            for n in (len(btc_fein), 220_000, 219_728)
        ]

        assert max(erste) - min(erste) < 0.2, erste

    def test_waehrend_die_zweite_das_vorzeichen_dreht(self, btc_fein) -> None:
        """272 Balken Unterschied - knapp drei Tage - und das Urteil kippt."""
        lang = pruefe_stabilitaet(btc_fein[:220_000], 16, 16)
        kurz = pruefe_stabilitaet(btc_fein[:219_728], 16, 16)

        assert lang.zweite.t_wert < -2.0
        assert kurz.zweite.t_wert > 0.0
        assert lang.haelt and not kurz.haelt


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_den_umschlag(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 431)

        assert "5 von 11" in eintrag.ergebnis
        assert "272 Balken" in eintrag.ergebnis

    def test_und_dass_es_kein_handelbarer_fund_ist(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 431)

        assert "0,0012" in eintrag.ergebnis
        assert "kein handelbarer Fund" in eintrag.ergebnis

    def test_und_430_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 430).zuletzt == 431
