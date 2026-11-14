"""Traegt die Gebuehr die Kopplung - oder liegt sie an den Signalen?

Zwei Tests tragen diese Datei:

``test_die_gebuehr_traegt_die_kopplung_nicht`` - Die naheliegende Erklaerung
fuer Befund 75/77: Wer oefter handelt, haelt kuerzer, streut weniger je Trade,
und dieselbe Gebuehr frisst mehr. Waere das die Ursache, waere die Kopplung
verhandelbar. Sie ist es nicht - zurueckgerechnet aendert sich r um 0,010.

``test_der_mechanismus_ist_da_und_traegt_trotzdem_nichts`` - Der Unterschied
zwischen "es gibt den Zusammenhang" und "er erklaert das Ergebnis". Trades und
Kostenanteil korrelieren mit +0,83, und es macht keinen Unterschied.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from research.kostenanteil import ERREICHBAR, Kostenfrage, Taktpunkt

ANFANG = datetime(2024, 1, 1)


@dataclass(frozen=True)
class FakeTrade:
    """Nur die Felder, die ``Taktpunkt.aus_trades`` liest."""

    net_pnl: float
    fees: float
    entry_time: datetime
    exit_time: datetime

    @property
    def duration(self) -> timedelta:
        return self.exit_time - self.entry_time


def handel(
    werte: list[float], *, gebuehr: float = 0.0, stunden: float = 6.0
) -> list[FakeTrade]:
    """Trades mit vorgegebenem Netto-Ergebnis, Gebuehr und Haltedauer."""
    return [
        FakeTrade(
            net_pnl=w,
            fees=gebuehr,
            entry_time=ANFANG + timedelta(days=i),
            exit_time=ANFANG + timedelta(days=i, hours=stunden),
        )
        for i, w in enumerate(werte)
    ]

#: Zehn Regeln mit sehr verschiedener Taktung, wie in Befund 78 gemessen:
#: Name, Trades, Sharpe je Trade, Haltedauer in Tagen, Kostenanteil.
GEMESSEN: list[tuple[str, int, float, float, float]] = [
    ("Bestand", 154, 0.2591, 14.1, 0.0028),
    ("Trend-Beteiligung 200 Tage", 53, 0.3185, 33.5, 0.0023),
    ("Trend-Beteiligung 100 Tage", 109, 0.2231, 22.3, 0.0021),
    ("Trend-Beteiligung 50 Tage", 156, 0.1894, 16.9, 0.0019),
    ("Trend beide Richtungen", 106, 0.2160, 30.2, 0.0028),
    ("Donchian-Ausbruch 55/20", 58, 0.3074, 48.5, 0.0013),
    ("Enge vor Bewegung", 18, 0.3405, 13.8, 0.0051),
    ("Volumenschock mit Fortsetzung", 114, 0.1584, 6.2, 0.0051),
    ("Rueckkehr zum Volumenschwerpunkt", 92, -0.1201, 12.1, 0.0059),
    ("Abgriff des Vortagestiefs", 406, -0.1201, 0.3, 0.0170),
]


def frage() -> Kostenfrage:
    return Kostenfrage(
        punkte=[
            Taktpunkt(
                name=n, trades=t, sharpe_je_trade=s,
                haltedauer_tage=h, kostenanteil=k,
            )
            for n, t, s, h, k in GEMESSEN
        ]
    )


class TestMechanik:
    def test_der_mechanismus_ist_da_und_traegt_trotzdem_nichts(self) -> None:
        """**Der zweite tragende Test.**

        Mehr Trades heissen kuerzer halten und hoeheren Kostenanteil - das ist
        messbar und stark (+0,83). Trotzdem erklaert es die Kopplung nicht.
        Ein vorhandener Zusammenhang und ein tragender sind zweierlei.
        """
        f = frage()

        assert f.mechanik is not None and f.mechanik > 0.8
        assert f.netto is not None and f.brutto(1.0) is not None
        assert abs(f.brutto(1.0) - f.netto) < 0.02

    def test_kuerzere_haltedauer_bedeutet_hoeheren_kostenanteil(self) -> None:
        """Die Ursache der Mechanik, an den Daten sichtbar."""
        punkte = frage().punkte
        kurz = min(punkte, key=lambda p: p.haltedauer_tage)
        lang = max(punkte, key=lambda p: p.haltedauer_tage)

        assert kurz.kostenanteil > lang.kostenanteil

    def test_der_kostenanteil_ist_winzig_gegen_die_spanne(self) -> None:
        """Der eigentliche Grund, warum die Mechanik nichts traegt."""
        punkte = frage().punkte
        spanne = max(p.sharpe_je_trade for p in punkte) - min(
            p.sharpe_je_trade for p in punkte
        )
        groesster_anteil = max(p.kostenanteil for p in punkte)

        assert groesster_anteil < spanne / 20


class TestUrsache:
    def test_die_gebuehr_traegt_die_kopplung_nicht(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Waere die Kopplung kostenbedingt, waere sie verhandelbar: bessere
        Konditionen, Maker-Rebates, groesseres Konto. Zurueckgerechnet geht r
        von -0,673 auf -0,663.
        """
        f = frage()

        assert f.netto == pytest.approx(-0.673, abs=0.01)
        assert f.brutto(1.0) == pytest.approx(-0.663, abs=0.01)
        assert f.brutto(1.0) < 0, "Die Kopplung bleibt bestehen"

    def test_der_kippfaktor_liegt_ausserhalb_jeder_wirklichkeit(self) -> None:
        """Die ehrliche Form der Frage: Die Slippage steckt im
        Ausfuehrungspreis und laesst sich nicht trennen - also wird gefragt,
        wie gross die Kosten sein muessten, um etwas zu aendern."""
        kipp = frage().kippfaktor()

        assert kipp is not None
        assert kipp > 20, f"gemessen {kipp:.1f}"
        assert 0.04 * kipp > 0.5, "ueber ein halbes Prozent je Roundtrip"

    def test_hoehere_kosten_schwaechen_die_kopplung_monoton(self) -> None:
        f = frage()
        werte = [f.brutto(x) for x in (1, 5, 10, 25)]

        assert werte == sorted(werte), "Mehr Kosten heben die Korrelation"

    def test_das_urteil_nennt_ursache_und_folge(self) -> None:
        urteil = frage().urteil()

        assert "nicht an den Kosten" in urteil
        assert "Eigenschaft der **Signale**" in urteil
        assert "nicht wegverhandelbar" in urteil


class TestGrenzen:
    def test_zu_wenige_punkte_liefern_nichts(self) -> None:
        duenn = Kostenfrage(
            punkte=[Taktpunkt("a", 100, 0.2, 10.0, 0.003)]
        )

        assert not duenn.genug
        assert duenn.netto is None
        assert duenn.kippfaktor() is None
        assert "nichts sagen" in duenn.urteil()

    def test_ohne_kopplung_gibt_es_keinen_kippfaktor(self) -> None:
        """Wo nichts zu erklaeren ist, wird nichts erklaert."""
        ohne = Kostenfrage(
            punkte=[
                Taktpunkt(f"k{i}", t, 0.2, 10.0, 0.003)
                for i, t in enumerate((50, 100, 200, 400))
            ]
        )

        assert ohne.kippfaktor() is None


class TestDasUrteilKenntNurEinenBetriebspunkt:
    """**Der Test zu Befund 187.**

    ``urteil`` begann mit *"Die Kopplung liegt nicht an den Kosten"* - ohne
    Bedingung, sobald genug Punkte da waren. Auf Tageskerzen ist das die
    gemessene Antwort (Kippfaktor 29). Bei einem Kippfaktor von 1,5 haette
    derselbe Satz dagestanden, unmittelbar gefolgt von der Zahl, die ihm
    widerspricht.

    Ein an einem Betriebspunkt gemessenes Ergebnis war als Gesetz eingebaut -
    dieselbe Sorte Fehler wie in Befund 56, 182 und 184.
    """

    def kippt_frueh(self) -> Kostenfrage:
        """Kopplung, die schon bei kleiner Kostenerhoehung verschwindet.

        Gebaut, nicht gemessen: Der Kostenanteil steigt mit der Trade-Zahl
        stark genug an, dass wenige Vielfache der Gebuehr die Korrelation
        aufheben.
        """
        return Kostenfrage(
            punkte=[
                Taktpunkt(f"k{i}", t, s, 1.0, k)
                for i, (t, s, k) in enumerate(
                    [
                        (50, 0.30, 0.012),
                        (100, 0.21, 0.050),
                        (200, 0.13, 0.100),
                        (400, 0.01, 0.155),
                    ]
                )
            ]
        )

    def test_ein_frueher_kippfaktor_wird_nicht_wegbehauptet(self) -> None:
        f = self.kippt_frueh()
        kipp = f.kippfaktor()

        assert kipp is not None and kipp <= ERREICHBAR, f"gemessen {kipp}"
        assert "nicht an den Kosten" not in f.urteil()
        assert "koennten es die Kosten sein" in f.urteil()

    def test_das_offene_urteil_sagt_dass_es_offen_ist(self) -> None:
        urteil = self.kippt_frueh().urteil()

        assert "nicht entschieden" in urteil
        assert "Slippage" in urteil
        assert "gilt hier nicht" in urteil

    def test_der_tagesbefund_bleibt_wie_er_war(self) -> None:
        """Die Verzweigung darf das gemessene Ergebnis nicht umdrehen."""
        urteil = frage().urteil()

        assert "nicht an den Kosten" in urteil
        assert "Eigenschaft der **Signale**" in urteil


def test_die_kostenfrage_wird_auch_gestellt() -> None:
    """**Befund 187.** Ein Modul ohne Aufrufer beantwortet die Frage von damals.

    ``Kostenfrage`` war gebaut, dokumentiert und mit neun Tests belegt - und
    stand in ``cli.py`` kein einziges Mal. Die Antwort aus Befund 78 galt
    damit fuer den Vorrat von Befund 78, und niemand haette gemerkt, wenn sie
    fuer den heutigen nicht mehr gilt.

    Dasselbe Muster wie bei der Research-KI: gebaut, gemessen, nicht
    angeschlossen. Dieser Test haelt den Anschluss fest.
    """
    from pathlib import Path

    quelle = (Path(__file__).resolve().parents[1] / "cli.py").read_text()

    assert "Kostenfrage" in quelle, "die Kostenfrage hat wieder keinen Aufrufer"
    assert "Taktpunkt.aus_trades" in quelle, (
        "die Taktpunkte werden nicht mehr aus den Trades gefuellt"
    )


class TestVonTradesZumTaktpunkt:
    """Der Weg, den es nicht gab: Trades rein, Taktpunkt raus."""

    def test_die_vier_groessen_kommen_aus_der_liste(self) -> None:
        t = Taktpunkt.aus_trades("probe", handel([3.0, -1.0, 2.0, -2.0, 1.0], gebuehr=0.5))

        assert t is not None
        assert t.trades == 5
        assert t.haltedauer_tage == pytest.approx(0.25)
        # Streuung der Netto-Werte, Gebuehr in denselben Einheiten.
        assert t.kostenanteil == pytest.approx(0.5 / statistics.stdev(
            [3.0, -1.0, 2.0, -2.0, 1.0]
        ))

    def test_dieselbe_zahl_wie_der_kandidat(self) -> None:
        """**Der tragende Test.**

        ``Kandidat.aus_trades`` und ``Taktpunkt.aus_trades`` lesen dieselbe
        Liste. Laufen ihre Sharpe-Werte auseinander, misst die Kostenfrage
        einen anderen Vorrat als die Vorratsdecke - und genau daran ist
        dieses Projekt laut ``Kandidat.aus_trades`` schon viermal gescheitert.
        """
        from research.suchbudget import Kandidat

        werte = [3.0, -1.0, 2.0, -2.0, 1.0, 0.5, -0.25]
        trades = handel(werte, gebuehr=0.5)

        takt = Taktpunkt.aus_trades("probe", trades)
        kandidat = Kandidat.aus_trades("probe", trades)

        assert takt is not None and kandidat is not None
        assert takt.sharpe_je_trade == pytest.approx(kandidat.sharpe_je_trade)
        assert takt.trades == kandidat.trades

    def test_zu_duenn_und_ohne_streuung_liefern_nichts(self) -> None:
        assert Taktpunkt.aus_trades("kurz", handel([1.0, 2.0, 3.0, 4.0])) is None
        assert Taktpunkt.aus_trades("flach", handel([2.0] * 8)) is None

    def test_die_gebuehr_laesst_sich_zurueckrechnen(self) -> None:
        """Der Kostenanteil ist in Einheiten der Streuung - deshalb addierbar."""
        werte = [3.0, -1.0, 2.0, -2.0, 1.0, 0.5, -0.25]
        t = Taktpunkt.aus_trades("probe", handel(werte, gebuehr=0.5))

        assert t is not None
        streuung = statistics.stdev(werte)
        brutto_mittel = (statistics.fmean(werte) + 0.5) / streuung
        assert t.brutto(1.0) == pytest.approx(brutto_mittel)


#: Der heutige Reibungsvorrat - Befund 476.
#:
#: (Name, Trades, Haltedauer in Tagen, Kostenanteil) aus
#: ``reports/reibung``: 1d, Spot-Punkt, 25 Genome, davon 14 mit Zahlen.
#: Zahlen eines Tages, keine Zusicherung ueber den heutigen Katalog - wie
#: ``VORRAT_285`` in ``test_vorratsdecke``.
#:
#: **Die Qualitaet je Trade steht hier nicht.** Dreizehn der vierzehn Regeln
#: fuehrt ``research.referenz`` schon, mit identischem Wert; sie hier
#: abzuschreiben waere eine zweite Fassung, und die Wache
#: ``test_die_zahlen_stehen_nur_an_dieser_einen_stelle`` hat genau das
#: gemeldet - zu Recht. Geholt wird sie deshalb aus dem Katalog.
REIBUNG_476: tuple[tuple[str, int, float, float], ...] = (
    ("Mean Reversion Uebertreibung", 7, 12.1429, 0.0108),
    ("Trend-Beteiligung (fair gerechnet)", 51, 46.6078, 0.0014),
    ("Donchian-Ausbruch 55/20", 58, 49.4483, 0.0013),
    ("Trendbeteiligung EMA200", 66, 16.0000, 0.0030),
    ("EMA-Kreuzung (Messlatte)", 71, 35.9718, 0.0043),
    ("Momentum-Beteiligung", 101, 12.0495, 0.0037),
    ("Trend beide Richtungen", 101, 44.3069, 0.0018),
    ("Momentum-Beteiligung 90 Tage", 101, 21.7525, 0.0017),
    ("Volatilitaets-Ausbruch", 103, 26.4369, 0.0053),
    ("Trend-Beteiligung 100 Tage", 108, 24.0556, 0.0020),
    ("Trendfolge Ausbruch", 138, 13.9928, 0.0055),
    ("Trend-Beteiligung 50 Tage", 158, 17.2025, 0.0018),
    ("Momentum Ruecksetzer", 264, 10.0265, 0.0086),
    ("Trendbeteiligung mit Puffer", 308, 13.0065, 0.0033),
)

#: Die eine Regel, die der Zulassungskatalog **nicht** fuehrt - und die das
#: ganze Urteil entscheidet. Ihre Qualitaet steht deshalb hier.
AUSSERHALB_476: tuple[str, float] = ("Mean Reversion Uebertreibung", -0.4724)


def _qualitaeten() -> dict[str, float]:
    """Qualitaet je Trade je Regel - aus der einen Quelle."""
    from research.referenz import VORRAT_TAGESKERZEN

    aus = {p.name: p.je_trade for p in VORRAT_TAGESKERZEN}
    aus[AUSSERHALB_476[0]] = AUSSERHALB_476[1]
    return aus


def _frage_476(*, ohne: str | None = None) -> Kostenfrage:
    qualitaet = _qualitaeten()
    return Kostenfrage(
        punkte=[
            Taktpunkt(n, t, qualitaet[n], h, k)
            for n, t, h, k in REIBUNG_476
            if n != ohne
        ]
    )


class TestEinPunktEntschiedDasGanzeUrteil:
    """**Befund 476.** Der Reibungsbericht von heute hat vierzehn Regeln, eine
    mehr als der Vorratsbericht - und diese eine kippt alles.

    'Mean Reversion Uebertreibung' hat **sieben** Trades und Qualitaet
    -0,4724: wenige Ausloesungen *und* das schlechteste Ergebnis, also genau
    die Gegenrichtung zu "wer oefter handelt, handelt schlechter".
    """

    def test_mit_allen_vierzehn_gibt_es_keine_kopplung(self) -> None:
        f = _frage_476()

        assert f.netto == pytest.approx(0.013, abs=0.002)
        assert f.mechanik == pytest.approx(0.062, abs=0.004)

    def test_ohne_den_einen_punkt_ist_sie_wieder_da(self) -> None:
        """Und zwar in der Groesse, die der Modulkopf nennt (r = -0,602 aus
        Befund 75/77)."""
        f = _frage_476(ohne="Mean Reversion Uebertreibung")

        assert f.netto == pytest.approx(-0.614, abs=0.003)
        assert f.mechanik == pytest.approx(0.501, abs=0.004)

    def test_die_probe_nennt_genau_diesen_punkt(self) -> None:
        probe = _frage_476().einflussprobe()

        assert probe is not None
        assert not probe.haelt
        name, wert = probe.staerkster
        assert name == "Mean Reversion Uebertreibung"
        assert wert == pytest.approx(-0.614, abs=0.003)
        assert probe.spanne == pytest.approx(0.627, abs=0.003)

    def test_und_das_urteil_erklaert_nichts_weg(self) -> None:
        """**Der Kern des Befundes.** Vorher stand hier "Die Kopplung liegt
        nicht an den Kosten. Auch bei tausendfacher Gebuehr verschwindet sie
        nicht." - bei einer Korrelation von +0,013.
        """
        urteil = _frage_476().urteil()

        assert "keine Kopplung zu erklaeren" in urteil
        assert "nicht an den Kosten" not in urteil
        assert "tausendfacher" not in urteil
        assert "haengt an einem Punkt" in urteil
        assert "Mean Reversion Uebertreibung" in urteil

    def test_der_kippfaktor_war_schon_vorher_ehrlich(self) -> None:
        """Er gab ``None`` zurueck - nur hat das Urteil es als "kein Faktor
        hebt sie auf" gelesen statt als "es gibt nichts aufzuheben"."""
        f = _frage_476()

        assert f.netto is not None and f.netto >= 0
        assert f.kippfaktor() is None


class TestDieProbeHaeltAuchDieGegenrichtung:
    def test_ein_breit_gestreuter_vorrat_haengt_an_keinem_punkt(self) -> None:
        """Die Gegenprobe: Ohne sie koennte ``haelt`` immer falsch sein."""
        f = _frage_476(ohne="Mean Reversion Uebertreibung")
        probe = f.einflussprobe()

        assert probe is not None
        assert probe.haelt, probe.satz()
        assert "keinem einzelnen Punkt" in probe.satz()
        assert "das Vorzeichen bleibt" in probe.satz()

    def test_zu_wenige_punkte_geben_keine_probe(self) -> None:
        """Vier Punkte genuegen fuer ``genug``, aber nicht fuer eine
        Auslassung - dann ist ``None`` die ehrliche Antwort."""
        klein = Kostenfrage(
            punkte=[Taktpunkt(f"k{i}", t, 0.3 - i * 0.05, 1.0, 0.002)
                    for i, t in enumerate((50, 100, 200, 400))]
        )

        assert klein.genug
        assert klein.einflussprobe() is None

    def test_das_urteil_traegt_den_satz_in_jedem_zweig(self) -> None:
        """Sonst stuende die Einschraenkung nur in einem von drei Faellen."""
        from tests.quelltext import rumpf

        code = rumpf(Kostenfrage.urteil)

        assert code.count("{zusatz}") >= 4, code
        assert "einflussprobe()" in code
