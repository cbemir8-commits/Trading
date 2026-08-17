"""Stimmt die Formel, mit der seit Befund 74 Partner bewertet werden?

Vier Tests tragen diese Datei:

``test_beide_achsen_treffen_sich_bei_unabhaengigen_trades`` - Die Kontrolle,
ohne die alles Weitere wertlos waere. Waeren Trade- und Wochenachse schon fuer
ein einzelnes Bein verschieden, waere jeder Unterschied beim Verbund ein
Artefakt der Aggregation.

``test_die_karte_ueberschaetzt_gleichlaeufige_beine`` und
``test_die_karte_unterschaetzt_gegenlaeufige_beine`` - Das Herz der Sache, an
gebauten Reihen mit **bekannter** Wahrheit statt an gemessenen mit
vermuteter.

``test_die_nullprobe_faengt_ab_was_die_faustformel_durchliess`` - Die
Faustformel aus Befund 71 haette 3,585 gegen 3,549 zu einem Fund gemacht. Ein
Abstand von vier Hundertstel Standardabweichungen ist keiner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from research.verbundmodell import (
    Modellpruefung,
    Paar,
    periodenkanten,
    periodenreihe,
    pruefe,
    t_wert,
)

ANFANG = datetime(2018, 1, 1, tzinfo=UTC)


@dataclass
class FakeTrade:
    net_pnl: float
    entry_time: datetime
    exit_time: datetime
    symbol: str = "BTCUSDT"


def trades_aus(werte, *, tag_je_trade: int = 3, versatz: int = 0) -> list[FakeTrade]:
    """Eine Trade-Liste mit vorgegebenen Ergebnissen, zeitlich gleichverteilt."""
    return [
        FakeTrade(
            net_pnl=float(w),
            entry_time=ANFANG + timedelta(days=i * tag_je_trade + versatz),
            exit_time=ANFANG + timedelta(days=i * tag_je_trade + versatz + 1),
        )
        for i, w in enumerate(werte)
    ]


def aus_wochenreihe(reihe, *, versatz_tage: int = 0) -> list[FakeTrade]:
    """Ein Trade je Woche mit vorgegebenem Ergebnis.

    So laesst sich eine Wochenreihe exakt vorgeben - und damit auch die
    Korrelation zweier Beine, statt sie zu hoffen.
    """
    return [
        FakeTrade(
            net_pnl=float(w),
            entry_time=ANFANG + timedelta(days=i * 7 + versatz_tage),
            exit_time=ANFANG + timedelta(days=i * 7 + versatz_tage + 1),
        )
        for i, w in enumerate(reihe)
    ]


class TestKontrolle:
    def test_beide_achsen_treffen_sich_bei_unabhaengigen_trades(self) -> None:
        """**Die Kontrolle, die das ganze Modul traegt.**

        ``SR/Trade * sqrt(n)`` und ``SR/Woche * sqrt(Wochen)`` sind derselbe
        t-Wert, wenn die Trades unabhaengig ueber die Zeit liegen. Das ist
        keine Annahme, sondern nachrechenbar: Verteilt man n Trades auf W
        Wochen, sinkt der Mittelwert um n/W und die Streuung um sqrt(n/W).

        Ohne diesen Test koennte jeder Unterschied beim Verbund genauso gut
        von der Aggregation kommen.
        """
        wuerfel = np.random.default_rng(4711)
        werte = wuerfel.normal(0.35, 1.0, 300)
        trades = trades_aus(werte)

        kanten = periodenkanten(trades)
        auf_trades = float(werte.mean() / werte.std(ddof=1) * len(werte) ** 0.5)
        auf_wochen = t_wert(periodenreihe(trades, kanten))

        assert auf_wochen is not None
        assert auf_wochen == pytest.approx(auf_trades, abs=0.35)

    def test_leere_perioden_bleiben_in_der_reihe(self) -> None:
        """Wochen ohne Trade stehen mit null darin. Wer sie herauswirft,
        bekommt einen zu hohen t-Wert - die Reihe hat dann weniger
        Beobachtungen bei gleichem Mittelwert."""
        trades = trades_aus([1.0, 1.0], tag_je_trade=70)
        reihe = periodenreihe(trades, periodenkanten(trades))

        assert len(reihe) == 11
        assert float(reihe.sum()) == pytest.approx(2.0)
        assert (reihe == 0).sum() == 9

    def test_die_kontrolle_schlaegt_an_wenn_die_achsen_auseinanderlaufen(self) -> None:
        """Gegenprobe: Bei erfundenen Einzelwerten faellt das Urteil durch,
        statt den Paarvergleich trotzdem auszurechnen."""
        pruefung = Modellpruefung(
            paare=[
                Paar(a=f"a{i}", b=f"b{i}", korrelation=0.0, karte=1.0, topf=1.0, echt=1.0)
                for i in range(30)
            ],
            einzeln={"a": (3.0, 1.0)},
        )

        assert not pruefung.achsen_stimmen_ueberein
        assert "Kontrolle faellt durch" in pruefung.urteil()


class TestModellfehler:
    def test_die_karte_ueberschaetzt_gleichlaeufige_beine(self) -> None:
        """**Der Kern, an gebauten Reihen mit bekannter Wahrheit.**

        Zwei Beine, die in denselben Wochen verdienen. Auf der Trade-Achse
        ist das nicht zu sehen - dort liegen bloss doppelt so viele Trades im
        Topf. Die Wochenreihe sieht es: Die Streuung der Summe waechst
        staerker als ihr Mittelwert, der t-Wert steigt kaum.
        """
        wuerfel = np.random.default_rng(2026)
        gemeinsam = wuerfel.normal(0.3, 1.0, 240)
        laeufe = {
            "A": aus_wochenreihe(gemeinsam),
            "B": aus_wochenreihe(gemeinsam * 0.9 + 0.03),
        }

        ergebnis = pruefe(laeufe)
        paar = ergebnis.paare[0]

        assert paar.korrelation > 0.9
        assert paar.kartenfehler > 0.5, "die Karte muss hier zu hoch liegen"
        assert not paar.karte_unterschaetzt

    def test_die_karte_unterschaetzt_gegenlaeufige_beine(self) -> None:
        """**Der Verdacht aus Befund 85 - hier mit bekannter Wahrheit.**

        Ein Bein mit **negativem** Sharpe, das genau dann verdient, wenn das
        andere verliert. Die Karte mittelt die beiden Sharpes und wirft es
        weg; als Portfolio-Bein glaettet es die Kurve und hebt den t-Wert.
        """
        wuerfel = np.random.default_rng(99)
        rausch = wuerfel.normal(0.0, 1.0, 240)
        gut = rausch + 0.30
        gegen = -rausch - 0.05  # negativer Sharpe, perfekt gegenlaeufig
        laeufe = {"gut": aus_wochenreihe(gut), "gegen": aus_wochenreihe(gegen)}

        ergebnis = pruefe(laeufe)
        paar = ergebnis.paare[0]

        assert paar.korrelation < -0.9
        assert paar.karte < paar.echt, "die Karte darf hier nicht zu hoch liegen"
        assert paar.karte_unterschaetzt
        assert paar.kartenfehler < -1.0

    def test_der_fehler_faehrt_auf_der_korrelation(self) -> None:
        """Ueber ein Feld gemischter Paare haengt der Kartenfehler an der
        Korrelation - genau die Groesse, die ein gewichteter Schnitt nicht
        kennt. Auf echten Daten sind es +0,752 ueber 210 Paare.

        Alle Beine werden hier auf denselben Mittelwert und dieselbe Streuung
        normiert. Damit ist die Karte fuer jedes Paar dieselbe Zahl, und was
        von Paar zu Paar variiert, ist allein die Korrelation - der Test misst
        die Mechanik statt die Schaetzstreuung der Einzel-Sharpes.

        Der Korrelationsbereich bleibt bei rund -0,6 bis +0,8, wie er auf den
        echten Daten gemessen wurde (-0,39 bis +1,00). Das ist kein
        Zurechtlegen, sondern noetig: Der Zusammenhang ist hyperbolisch, denn
        der t-Wert der Summe faehrt mit ``1/sqrt(2 + 2*rho)``. Nahe rho = -1
        hat er einen Pol, ein einziges Paar dort erzeugt einen riesigen Fehler
        und Pearson bricht auf 0,31 ein, obwohl der Zusammenhang exakt ist.
        Solche Paare gibt es in den Daten nicht - wer sie in den Test baut,
        prueft den Pol und nicht das Modell.
        """
        wuerfel = np.random.default_rng(7)
        grund = wuerfel.normal(0.0, 1.0, 300)
        anteile = (-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 0.95)
        laeufe = {}
        for i, anteil in enumerate(anteile):
            eigen = wuerfel.normal(0.0, 1.0, 300)
            reihe = anteil * grund + (1 - abs(anteil)) ** 0.5 * eigen
            reihe = (reihe - reihe.mean()) / reihe.std(ddof=1) + 0.2
            laeufe[f"regel{i}"] = aus_wochenreihe(reihe)

        ergebnis = pruefe(laeufe)

        assert ergebnis.genug
        karten = {round(p.karte, 6) for p in ergebnis.paare}
        assert len(karten) == 1, "normiert muss die Karte fuer alle Paare gleich sein"

        wert = ergebnis.fehler_faehrt_auf_korrelation
        assert wert is not None
        assert wert > 0.9, f"gemessen {wert:.3f}"
        steigung, _, null = ergebnis.gerade
        assert steigung > 0
        assert abs(null) < 0.35, "die Karte muss nahe der Unabhaengigkeit stimmen"


class TestAuswahl:
    def test_die_nullprobe_faengt_ab_was_die_faustformel_durchliess(self) -> None:
        """**Der Test gegen den eigenen Fehler.**

        Auf echten Daten erreicht das beste von 210 Paaren 3,585, die
        konservative Faustformel liegt bei 3,549 - und das Urteil sagte
        prompt "schlaegt die Auswahl". Der Abstand betraegt vier Hundertstel
        Standardabweichungen. Die Schranke ist der **Erwartungswert** des
        Maximums; die Haelfte aller Rauschziehungen liegt darueber.

        Geprueft wird die Kalibrierung, nicht ein Einzelfall: Ueber zwanzig
        unabhaengige Rauschfelder darf das beste Paar das 95. Perzentil in
        hoechstens einem Viertel der Faelle schlagen. Ein einzelner Durchlauf
        waere dafuer untauglich - der erste Anlauf zu diesem Test traf mit
        4,7093 gegen 4,7089 genau das Perzentil und schlug fehl, obwohl der
        Code richtig rechnete. Ein 5-%-Ereignis darf man nicht per Saat
        ausschliessen.
        """
        treffer = 0
        felder = 20
        for saat in range(felder):
            wuerfel = np.random.default_rng(20260817 + saat)
            laeufe = {
                f"regel{i}": aus_wochenreihe(wuerfel.normal(0.12, 1.0, 300))
                for i in range(9)
            }
            ergebnis = pruefe(laeufe)
            bestes = ergebnis.bestes
            null = ergebnis.nullprobe(durchlaeufe=60, saat=saat)
            assert bestes is not None and null is not None
            if bestes.echt > null[1]:
                treffer += 1

        assert treffer <= felder // 4, (
            f"reines Rauschen schlug die Null in {treffer} von {felder} Feldern"
        )

    def test_echtes_zusammenspiel_schlaegt_die_nullprobe(self) -> None:
        """Gegenprobe: Die Nullprobe verwirft nicht alles.

        Ein Paar, das **nur** gemeinsam funktioniert - zwei gegenlaeufige
        Beine, die sich gegenseitig glaetten. Verschiebt man sie
        gegeneinander, faellt der Vorteil weg. Genau das soll die Null
        messen, und hier muss sie anschlagen.
        """
        wuerfel = np.random.default_rng(31337)
        rausch = wuerfel.normal(0.0, 1.0, 300)
        laeufe = {
            "auf": aus_wochenreihe(rausch + 0.22),
            "ab": aus_wochenreihe(-rausch + 0.22),
        }
        for i in range(6):
            laeufe[f"fuellung{i}"] = aus_wochenreihe(wuerfel.normal(0.05, 1.0, 300))

        ergebnis = pruefe(laeufe)
        bestes = ergebnis.bestes
        null = ergebnis.nullprobe(durchlaeufe=150)

        assert bestes is not None and null is not None
        assert {bestes.a, bestes.b} == {"auf", "ab"}
        assert bestes.echt > null[1], "echtes Zusammenspiel muss durchkommen"
        assert ergebnis.schlaegt_die_auswahl

    def test_die_faustformel_bleibt_als_rueckfall(self) -> None:
        """Ohne Reihen gibt es keine Nullprobe - dann zaehlt die konservative
        Schranke, die nur die Regeln als unabhaengige Ziehungen nimmt."""
        wuerfel = np.random.default_rng(5)
        werte = wuerfel.normal(1.8, 0.9, 210)
        pruefung = Modellpruefung(
            paare=[
                Paar(
                    a=f"a{i // 20}", b=f"b{i % 20}", korrelation=0.0,
                    karte=float(w), topf=float(w), echt=float(w),
                )
                for i, w in enumerate(werte)
            ]
        )

        assert pruefung.nullprobe() is None
        roh = pruefung.schranke()
        konservativ = pruefung.schranke(konservativ=True)
        assert roh is not None and konservativ is not None
        assert konservativ < roh, "weniger Ziehungen, haertere Schranke"


class TestGrenzen:
    def test_zu_wenige_paare_liefern_nichts(self) -> None:
        duenn = Modellpruefung(
            paare=[Paar(a="a", b="b", korrelation=0.1, karte=2.0, topf=2.0, echt=1.8)]
        )

        assert not duenn.genug
        assert duenn.fehler_faehrt_auf_korrelation is None
        assert duenn.gerade is None
        assert duenn.schranke() is None
        assert "nichts sagen" in duenn.urteil()

    def test_ohne_trades_bleibt_die_reihe_leer(self) -> None:
        assert len(periodenkanten([])) == 0
        assert len(periodenreihe([], np.array([]))) == 0
        assert t_wert([1.0]) is None
        assert t_wert([2.0, 2.0, 2.0]) is None, "ohne Streuung kein t-Wert"
