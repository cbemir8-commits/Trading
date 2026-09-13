"""Die vierte Familie - und die Huerde, die sie sichtbar gemacht hat.

**Befund 276.** Befund 274 hat drei Familien gemessen und eine Luecke
benannt: *"Marktbreite ueber mehr als zwei Maerkte"*. Vier Maerkte liegen im
Speicher, also ist sie messbar - und sie hat als erste Familie dieser Reihe
eine Zelle ueber die Schwelle gebracht.

Was hier gehalten wird
----------------------
**Die Breite zaehlt die anderen Maerkte, nicht den eigenen.** Zaehlte sie ihn
mit, steckte ein Teil des eigenen Rueckblicks in der Kennzahl, und ein Fund
liesse sich nicht mehr zuordnen: eigener Trend oder fremde Bestaetigung.

**Der Vorrat ist eine Liste im Code, keine Option.** Wer die Nachbarmaerkte
aussuchen darf, sucht so lange, bis eine Zelle auffaellt.

**Ein t-Wert wird gegen die Traegheit seines eigenen Teilers gehalten.** Das
ist die Huerde, die dieser Befund gebaut hat: Die Latte aus ``schwelle_fuer``
unterstellt, dass jede Beobachtung neu gewuerfelt wird. Ein Rueckblick ueber
960 Balken haelt seinen Zustand jahrelang - 585 Beobachtungen, fuenfzehn
Wechsel. Gegen verschobene Teiler gehalten erreichen 2 von 584 Verschiebungen
denselben Wert, gefordert waren 0,029 %.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from research.vorteilsscan import (
    MIND_ANDERE,
    MIND_BEOBACHTUNGEN,
    Stabilitaet,
    Zelle,
    paar_nach_breite,
    rotationsprobe,
    schwelle_fuer,
    spanne_nach_breite,
    stabilitaet_nach_breite,
    urteil,
    zweiteilung,
)


def _scan_quelle() -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == "scan"
    )
    return ast.unparse(knoten)


def _reihe(n: int, saat: int) -> np.ndarray:
    """Ein Log-Kursverlauf ohne Vorhersagbarkeit."""
    rng = np.random.default_rng(saat)
    return np.cumsum(rng.normal(0, 0.02, n))


class TestDieBreiteZaehltDieAnderen:
    def test_der_eigene_markt_geht_nicht_in_den_teiler(self) -> None:
        """Zwei verschiedene Ziele, dieselben Nachbarn, derselbe Teiler.

        Steckte der eigene Rueckblick mit in der Kennzahl, muesste sich der
        Teiler mit dem Ziel aendern - und ein Fund waere nicht mehr
        zuzuordnen.
        """
        nachbarn = [_reihe(600, 1), _reihe(600, 2), _reihe(600, 3)]

        eines = paar_nach_breite(_reihe(600, 10), nachbarn, 16, 4)
        anderes = paar_nach_breite(_reihe(600, 11), nachbarn, 16, 4)

        assert eines is not None and anderes is not None
        assert np.array_equal(eines[1], anderes[1])

    def test_zu_wenige_nachbarn_geben_nichts(self) -> None:
        """Mit einem Partner ist es keine Breite, sondern ein Paarvergleich."""
        ziel = _reihe(600, 10)
        nachbarn = [_reihe(600, 1)] * (MIND_ANDERE - 1)

        assert spanne_nach_breite(ziel, nachbarn, 16, 4) is None

    def test_ungleiche_laengen_sind_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="denselben Zeitstempeln"):
            spanne_nach_breite(
                _reihe(600, 10), [_reihe(600, 1), _reihe(599, 2)], 16, 4
            )

    def test_zu_wenig_daten_geben_nichts(self) -> None:
        kurz = _reihe(20, 10)

        assert spanne_nach_breite(kurz, [kurz, kurz], 16, 4) is None


class TestDasPattFaelltHeraus:
    """Bei gerader Nachbarzahl gibt es einen dritten Zustand."""

    def test_genau_die_haelfte_ist_keiner_der_beiden(self) -> None:
        ziel = _reihe(900, 10)
        zwei = [_reihe(900, 1), _reihe(900, 2)]

        reihen = paar_nach_breite(ziel, zwei, 16, 4)

        assert reihen is not None
        # Kein einziger Teiler steht auf null: Was dort stuende, waere ein
        # Patt und wuerde einen dritten Zustand in einen der beiden mischen.
        assert not np.any(reihen[1] == 0)

    def test_bei_ungerader_nachbarzahl_faellt_nichts_heraus(self) -> None:
        """Drei Nachbarn koennen sich nicht teilen - es bleibt alles da."""
        ziel = _reihe(900, 10)
        drei = [_reihe(900, 1), _reihe(900, 2), _reihe(900, 3)]

        reihen = paar_nach_breite(ziel, drei, 16, 4)

        assert reihen is not None
        assert len(reihen[0]) == len(range(0, 900 - 16 - 4, 4))

    def test_ausgeduennt_wird_vor_dem_aussortieren(self) -> None:
        """Die Unabhaengigkeit haengt am gleichen Abstand von ``halten``.

        Faellt das Patt zuerst aus der vollen Reihe, ruecken die Nachbarn
        zusammen und der Abstand ist keiner mehr. Gemessen wird das an der
        Zahl: Sie kann nur so gross sein wie die ausgeduennte Reihe.
        """
        ziel = _reihe(900, 10)
        zwei = [_reihe(900, 1), _reihe(900, 2)]

        reihen = paar_nach_breite(ziel, zwei, 16, 4)

        assert reihen is not None
        assert len(reihen[0]) <= len(range(0, 900 - 16 - 4, 4))


class TestDieVerschiebungsprobe:
    """Haelt der t-Wert, wenn man ihn gegen die Traegheit des Teilers haelt?"""

    def _echt(self, n: int = 600) -> tuple[np.ndarray, np.ndarray]:
        """Ein Teiler, der wirklich vorhersagt und schnell wechselt."""
        rng = np.random.default_rng(276)
        teiler = rng.normal(0, 1.0, n)
        vorwaerts = np.sign(teiler) * 0.01 + rng.normal(0, 0.004, n)
        return vorwaerts, teiler

    def test_ein_echter_vorteil_haelt(self) -> None:
        vorwaerts, teiler = self._echt()

        probe = rotationsprobe(vorwaerts, teiler, rueckblick=16, halten=4)

        assert probe is not None
        assert probe.haeufiger == 0
        assert probe.bloecke > len(vorwaerts) // 3

    def test_die_probe_kann_nicht_feiner_als_ihre_verschiebungen(self) -> None:
        vorwaerts, teiler = self._echt()

        probe = rotationsprobe(vorwaerts, teiler, rueckblick=16, halten=4)

        assert probe is not None
        assert probe.aufloesung == pytest.approx(1 / (probe.rotationen + 1))
        # Keine einzige Verschiebung heisst "hoechstens eine von n+1" - und
        # nicht "keine".
        assert probe.anteil == 0.0
        assert probe.aufloesung > 0

    def test_der_vorbehalt_steht_am_bestandenen_fall(self) -> None:
        """"Keine von 584" belegt keine 0,030 % - das gehoert dazugesagt."""
        vorwaerts, teiler = self._echt()
        probe = rotationsprobe(vorwaerts, teiler, rueckblick=16, halten=4)

        assert probe is not None
        assert probe.traegt(0.05 / 164)
        assert probe.aufloesung > 0.05 / 164
        assert "nicht von 'nicht da' zu trennen" in probe.beschreibe(0.05 / 164)

    def test_und_nicht_am_gerissenen(self) -> None:
        """Dort ist der gemessene Anteil schon groesser als das Geforderte -
        feiner messen zu koennen aenderte daran nichts."""
        rng = np.random.default_rng(7)
        vorwaerts = rng.normal(0, 0.02, 600)
        teiler = rng.normal(0, 1.0, 600)
        probe = rotationsprobe(vorwaerts, teiler, rueckblick=16, halten=4)

        assert probe is not None
        assert not probe.traegt(0.05 / 164)
        assert "nicht von 'nicht da' zu trennen" not in probe.beschreibe(
            0.05 / 164
        )

    def test_bei_genug_verschiebungen_faellt_der_vorbehalt_weg(self) -> None:
        vorwaerts, teiler = self._echt(4000)
        probe = rotationsprobe(vorwaerts, teiler, rueckblick=16, halten=4)

        assert probe is not None
        assert probe.aufloesung <= 0.05
        assert "nicht von 'nicht da' zu trennen" not in probe.beschreibe(0.05)

    def test_die_zahl_der_verschiebungen_ist_gedeckelt(self) -> None:
        """Sonst waere die Probe auf 15-Minuten-Kerzen quadratisch teuer."""
        vorwaerts, teiler = self._echt(4000)

        probe = rotationsprobe(
            vorwaerts, teiler, rueckblick=16, halten=4, hoechstens=200
        )

        assert probe is not None
        assert probe.rotationen <= 200

    def test_ungleiche_laengen_sind_ein_fehler(self) -> None:
        with pytest.raises(ValueError, match="genau ein Teiler"):
            rotationsprobe(np.zeros(80), np.zeros(79), rueckblick=4, halten=2)

    def test_ohne_genug_beobachtungen_gibt_es_keine_probe(self) -> None:
        n = MIND_BEOBACHTUNGEN - 1
        vorwaerts = np.concatenate([np.ones(n), np.zeros(n)])
        teiler = np.concatenate([np.ones(n), -np.ones(n)])

        assert rotationsprobe(vorwaerts, teiler, rueckblick=4, halten=2) is None


class TestTraegheitHebtDenTWert:
    """Warum es diese Huerde ueberhaupt gibt - gemessen auf reinem Rauschen.

    ``schwelle_fuer(164)`` soll fuenf Prozent Irrtum auf 164 Zellen
    aufteilen, also rund 0,030 % je Zelle. Das gilt, wenn die Zuordnung zu
    den beiden Zustaenden von Beobachtung zu Beobachtung neu faellt. Faellt
    sie nur alle paar Jahre neu, gilt es nicht mehr - und zwar um
    Groessenordnungen.
    """

    LATTE = schwelle_fuer(164)
    ZUEGE = 300

    def _zug(
        self, saat: int, *, traege: bool, n: int = 600
    ) -> tuple[np.ndarray, np.ndarray]:
        """Renditen ohne jeden Zusammenhang zum Teiler."""
        rng = np.random.default_rng(saat)
        vorwaerts = rng.normal(0, 0.02, n)
        if not traege:
            return vorwaerts, rng.normal(0, 1.0, n)
        # Das Vorzeichen eines langen Rueckblicks auf einem fremden Irrweg -
        # die Form der Marktbreite, ohne ihren Inhalt.
        fremd = np.cumsum(rng.normal(0, 0.02, n + 200))
        return vorwaerts, fremd[200:] - fremd[:-200]

    def _ueber_der_latte(self, *, traege: bool) -> int:
        gezaehlt = 0
        for saat in range(self.ZUEGE):
            vorwaerts, teiler = self._zug(saat, traege=traege)
            z = zweiteilung(vorwaerts, teiler, rueckblick=16, halten=4)
            if z is not None and abs(z.t_wert) >= self.LATTE:
                gezaehlt += 1
        return gezaehlt

    def test_ein_traeger_teiler_kommt_ueber_die_latte(self) -> None:
        assert self._ueber_der_latte(traege=True) > 0

    def test_ein_flinker_nicht(self) -> None:
        """Dieselbe Latte, dieselben Renditen, nur ein Teiler ohne Gedaechtnis."""
        assert self._ueber_der_latte(traege=False) == 0

    def test_und_die_probe_faengt_ihn(self) -> None:
        """Der Fall, um dessentwillen die Huerde gebaut wurde."""
        gefunden = None
        for saat in range(self.ZUEGE):
            vorwaerts, teiler = self._zug(saat, traege=True)
            z = zweiteilung(vorwaerts, teiler, rueckblick=16, halten=4)
            if z is not None and abs(z.t_wert) >= self.LATTE:
                gefunden = (vorwaerts, teiler)
                break

        assert gefunden is not None
        probe = rotationsprobe(*gefunden, rueckblick=16, halten=4)

        assert probe is not None
        assert not probe.traegt(0.05 / 164)
        assert probe.traegt(1.0)


class TestDasUrteilKenntDieProbe:
    def _zelle(self, t: float = 4.0) -> Zelle:
        return Zelle(
            rueckblick=960,
            halten=4,
            beobachtungen=585,
            spanne_pct=-1.88,
            t_wert=t,
        )

    def _haelt(self) -> Stabilitaet:
        return Stabilitaet(erste=self._zelle(3.0), zweite=self._zelle(3.0))

    def test_ohne_probe_bleibt_alles_wie_vorher(self) -> None:
        """Aeltere Aufrufer sollen nicht stillschweigend ein anderes Urteil
        bekommen - die Probe ist etwas, das man mitgibt."""
        satz = urteil(self._zelle(), self._haelt(), gepruefte_zellen=1)

        assert satz.startswith("Fund:")

    def test_eine_probe_die_nicht_traegt_verhindert_den_fund(self) -> None:
        vorwaerts = np.linspace(-0.02, 0.02, 600)
        teiler = np.where(np.arange(600) < 300, 1.0, -1.0)
        probe = rotationsprobe(vorwaerts, teiler, rueckblick=16, halten=4)

        satz = urteil(
            self._zelle(), self._haelt(), gepruefte_zellen=164, probe=probe
        )

        assert "Fund" not in satz
        assert "Verschiebungsprobe" in satz

    def test_sie_steht_vor_der_stabilitaet(self) -> None:
        """Haelt die Probe nicht, war schon der Schwellenvergleich keiner -
        dann ueber die Haelften zu reden hiesse, eine Zahl zu deuten, die
        nichts bedeutet."""
        vorwaerts = np.linspace(-0.02, 0.02, 600)
        teiler = np.where(np.arange(600) < 300, 1.0, -1.0)
        probe = rotationsprobe(vorwaerts, teiler, rueckblick=16, halten=4)
        zerfallen = Stabilitaet(erste=self._zelle(3.0), zweite=self._zelle(-0.2))

        satz = urteil(self._zelle(), zerfallen, gepruefte_zellen=164, probe=probe)

        assert "Verschiebungsprobe" in satz

    def test_unter_der_schwelle_bleibt_die_schwelle_der_grund(self) -> None:
        satz = urteil(
            self._zelle(1.0), self._haelt(), gepruefte_zellen=164, probe=None
        )

        assert "Nicht auffaellig genug" in satz


class TestDieHaelftenTeilenAnEinerStelle:
    def test_die_nachbarn_werden_mitgeschnitten(self) -> None:
        """Blieben sie ungeschnitten, stuende eine Breite aus der ersten
        Haelfte neben einer Rendite aus der zweiten - und weil die Laengen
        dann nicht mehr passen, faellt es als ``ValueError`` auf."""
        ziel = _reihe(900, 10)
        nachbarn = [_reihe(900, 1), _reihe(900, 2), _reihe(900, 3)]

        stabil = stabilitaet_nach_breite(ziel, nachbarn, 16, 4)

        assert stabil.erste is not None
        assert stabil.zweite is not None

    def test_alle_familien_teilen_nach_derselben_regel(self) -> None:
        """Eine Familie mit eigener Vorstellung von der Mitte waere mit den
        anderen nicht mehr vergleichbar."""
        import inspect

        from research import vorteilsscan

        for fn in (
            vorteilsscan.pruefe_stabilitaet,
            vorteilsscan.stabilitaet_nach_kennzahl,
            vorteilsscan.stabilitaet_nach_breite,
        ):
            assert "haelften(" in inspect.getsource(fn)


class TestDerBefehlLaesstNichtsAus:
    def test_der_vorrat_ist_keine_option(self) -> None:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "scan"
        )
        namen = {a.arg for a in knoten.args.args}

        assert "breite" not in namen
        assert "nachbarn" not in namen
        assert "vorrat" not in namen

    def test_er_kommt_aus_der_liste_der_forschungsmaerkte(self) -> None:
        assert "PAIRS" in _scan_quelle()

    def test_die_breite_zaehlt_in_die_gemeinsame_schwelle(self) -> None:
        """Geankert auf der Anforderung: Was die Breite liefert, landet in
        ``nebenfamilien`` - und von dort in ``gesamt``."""
        quelle = _scan_quelle()
        zuweisung = next(
            z for z in quelle.splitlines() if z.strip().startswith("gesamt =")
        )

        assert "nebenfamilien" in zuweisung
        assert "Marktbreite" in quelle

    def test_jedes_urteil_bekommt_seine_probe(self) -> None:
        """Nicht nur die Hauptfamilie: Eine Nebenfamilie, die ueber die
        Schwelle kommt, muss dieselben Huerden nehmen."""
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "scan"
        )
        aufrufe = [
            k
            for k in ast.walk(knoten)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id == "urteil"
        ]

        assert aufrufe
        for aufruf in aufrufe:
            assert "probe" in {s.arg for s in aufruf.keywords}

    def test_eine_fehlende_breite_wird_gemeldet(self) -> None:
        """Ein Lauf ohne Marktbreite darf nicht aussehen wie einer, in dem
        sie nichts ergeben hat."""
        assert "nicht gemessen" in _scan_quelle()


class TestDerBefehlLaeuft:
    """Nicht nur die Quelle - der Befehl auf einem kleinen Speicher.

    Die echten Kerzen sind fuer einen Test zu gross: Der gleitende Median
    laeuft ueber 225.000 Balken je Zelle. Hier steht ein Speicher mit ein
    paar hundert Tagen, und geprueft wird, welchen der beiden Wege der
    Befehl nimmt.
    """

    def _speicher(self, ordner: Path, symbole: list[str], n: int = 420) -> None:
        import pandas as pd

        from core.models import Interval
        from data.store import CandleStore

        store = CandleStore(ordner)
        zeit = pd.date_range("2019-01-01", periods=n, freq="D", tz="UTC")
        for i, symbol in enumerate(symbole):
            kurs = 100 * np.exp(_reihe(n, 100 + i))
            store.write_frame(
                symbol,
                Interval("D"),
                pd.DataFrame(
                    {
                        "open_time": zeit,
                        "open": kurs,
                        "high": kurs * 1.01,
                        "low": kurs * 0.99,
                        "close": kurs,
                        "volume": np.linspace(10.0, 20.0, n),
                        "turnover": np.linspace(10.0, 20.0, n) * kurs,
                    }
                ),
            )

    def _lauf(
        self, ordner: Path, monkeypatch, symbol: str = "BTCUSD_BITSTAMP"
    ) -> str:
        from typer.testing import CliRunner

        from cli import app
        from core.config import get_settings

        monkeypatch.setenv("PATHS__DATA_STORE", str(ordner))
        get_settings.cache_clear()
        try:
            ergebnis = CliRunner().invoke(
                app, ["scan", "--intervall", "D", "--maerkte", symbol]
            )
        finally:
            get_settings.cache_clear()
        assert ergebnis.exit_code == 0, ergebnis.output
        return ergebnis.output

    def test_mit_vier_maerkten_wird_die_breite_gemessen(
        self, tmp_path, monkeypatch
    ) -> None:
        from data.reference import PAIRS

        self._speicher(tmp_path / "vier", list(PAIRS))

        ausgabe = self._lauf(tmp_path / "vier", monkeypatch)

        assert "Marktbreite" in ausgabe
        assert "nicht gemessen" not in ausgabe

    def test_mit_zweien_wird_sie_als_fehlend_gemeldet(
        self, tmp_path, monkeypatch
    ) -> None:
        self._speicher(
            tmp_path / "zwei", ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
        )

        ausgabe = self._lauf(tmp_path / "zwei", monkeypatch)

        assert "nicht gemessen" in ausgabe

    def test_ein_boersensymbol_bekommt_keine_forschungsnachbarn(
        self, tmp_path, monkeypatch
    ) -> None:
        """Sonst bekaeme 'BTCUSDT' das 'BTCUSD_BITSTAMP' desselben Wertes als
        Nachbarn - der eigene Rueckblick unter fremdem Namen.

        Der Fall kommt, sobald Bybit-Kerzen im Speicher liegen.
        """
        from data.reference import PAIRS

        ordner = tmp_path / "boerse"
        self._speicher(ordner, [*PAIRS, "BTCUSDT"])

        ausgabe = self._lauf(ordner, monkeypatch, symbol="BTCUSDT")

        assert "nicht gemessen" in ausgabe
        assert "Forschungsmaerkte" in ausgabe
