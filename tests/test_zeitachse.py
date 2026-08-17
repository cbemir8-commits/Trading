"""Kuerzt das Gate genug - oder nur dort, wo es ohnehin nicht wehtut?

Vier Tests tragen diese Datei:

``test_gleichlauf_im_klumpen_kostet`` - Der Kern, an gebauten Trades mit
bekannter Wahrheit: Drei Trades derselben Woche, die gemeinsam gewinnen, sind
eine Beobachtung. Nur die Zeitachse sieht das.

``test_klumpung_allein_kostet_nichts`` - Das Gegenstueck, und es hat den
ersten Entwurf widerlegt: Drei **unabhaengige** Trades in derselben Woche
kosten gar nichts. Es ist nicht die Haeufung, sondern die Haeufung plus
Gleichlauf.

``test_die_nullprobe_landet_an_der_trade_achse`` - Die Kontrolle, ohne die der
ganze Vergleich wertlos waere. Zufaellig verteilte Trades muessen den t-Wert
der Trade-Achse reproduzieren.

``test_ein_stimmender_mittelwert_verdeckt_die_stelle_nicht`` - Ein Gate kann im
Schnitt richtig kuerzen und in jeder Zeile danebenliegen. Der erste Entwurf
meldete dann nur "haelt mit".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from research.zeitachse import SPUERBAR, Zeitbild, Zeitpruefung, messe

ANFANG = datetime(2018, 1, 1, tzinfo=UTC)


@dataclass
class FakeTrade:
    net_pnl: float
    entry_time: datetime
    exit_time: datetime
    symbol: str = "BTCUSDT"


def trades_an_tagen(werte, tage) -> list[FakeTrade]:
    """Trade-Ergebnisse an vorgegebenen Tagen - damit laesst sich die
    Zeitverteilung exakt setzen statt hoffen."""
    return [
        FakeTrade(
            net_pnl=float(w),
            entry_time=ANFANG + timedelta(days=int(t)),
            exit_time=ANFANG + timedelta(days=int(t) + 1),
        )
        for w, t in zip(werte, tage, strict=True)
    ]


def bild(
    *, name: str = "x", trades: int = 100, roh: float = 2.0,
    gate: float = 2.0, woche: float = 1.6, null: float = 2.0,
) -> Zeitbild:
    return Zeitbild(
        name=name, trades=trades, t_roh=roh, t_gate=gate,
        t_woche=woche, t_null=null,
    )


class TestMechanik:
    def test_klumpung_allein_kostet_nichts(self) -> None:
        """**Die Praezisierung, die der erste Testentwurf erzwungen hat.**

        Der erste Anlauf verlangte, dass Dreierklumpen in derselben Woche die
        Stichprobe um ein Drittel kuerzen. Er scheiterte mit 7 % - zu Recht:
        Drei **unabhaengige** Trades aufsummiert ergeben einen Wert mit
        dreifachem Mittel und wurzel-dreifacher Streuung. Der t-Wert bleibt
        erhalten, und zwar exakt.

        Klumpung allein kostet also nichts. Das gehoert festgehalten, weil es
        die Deutung des ganzen Moduls praezisiert.
        """
        wuerfel = np.random.default_rng(2026)
        werte = wuerfel.normal(0.30, 1.0, 120)

        gleichmaessig = trades_an_tagen(werte, np.arange(120) * 9)
        klumpen = trades_an_tagen(
            werte, [(i // 3) * 27 + (i % 3) for i in range(120)]
        )

        ergebnis = messe(
            {"gleich": gleichmaessig, "klumpen": klumpen},
            {"gleich": 0.0, "klumpen": 0.0},
            durchlaeufe=200,
        )
        je = {b.name: b for b in ergebnis.bilder}

        assert je["gleich"].t_roh == pytest.approx(je["klumpen"].t_roh)
        assert je["klumpen"].kuerzung_zeit < 0.15, "unabhaengig kostet nichts"

    def test_gleichlauf_im_klumpen_kostet(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Dieselbe Klumpung, aber die drei Trades einer Woche gewinnen oder
        verlieren nun **gemeinsam**. Erst das kostet: Aus drei Beobachtungen
        wird eine. Die Trade-Achse sieht davon nichts, die Wochenachse alles.
        """
        wuerfel = np.random.default_rng(2026)
        klumpenwert = wuerfel.normal(0.30, 1.0, 40)
        # Jeder Dreierklumpen traegt dreimal denselben Wert - der Extremfall
        # von Gleichlauf, und damit die Obergrenze dessen, was Zeitstruktur
        # kosten kann.
        werte = np.repeat(klumpenwert, 3)
        gekoppelt = trades_an_tagen(
            werte, [(i // 3) * 27 + (i % 3) for i in range(120)]
        )
        verteilt = trades_an_tagen(werte, np.arange(120) * 9)

        ergebnis = messe(
            {"gekoppelt": gekoppelt, "verteilt": verteilt},
            {"gekoppelt": 0.0, "verteilt": 0.0},
            durchlaeufe=200,
        )
        je = {b.name: b for b in ergebnis.bilder}

        assert je["gekoppelt"].t_roh == pytest.approx(je["verteilt"].t_roh)
        assert je["gekoppelt"].t_woche < je["verteilt"].t_woche
        assert je["gekoppelt"].kuerzung_zeit > 0.5, "aus drei wird eine"
        assert je["gekoppelt"].effektiv_nach_zeit < 60

    def test_die_nullprobe_landet_an_der_trade_achse(self) -> None:
        """**Die Kontrolle.**

        Zufaellig ueber die Wochen verteilte Trades muessen den t-Wert der
        Trade-Achse reproduzieren - sonst misst der ganze Vergleich die
        Aggregation statt der Zeitstruktur.
        """
        wuerfel = np.random.default_rng(77)
        werte = wuerfel.normal(0.25, 1.0, 200)
        laeufe = {"a": trades_an_tagen(werte, np.arange(200) * 6)}

        ergebnis = messe(laeufe, {"a": 0.0}, durchlaeufe=300)
        eins = ergebnis.bilder[0]

        assert eins.t_null == pytest.approx(eins.t_roh, abs=0.25)
        assert eins.nullprobe_traegt

    def test_die_kuerzung_rechnet_ueber_das_quadrat(self) -> None:
        """``t = SR * sqrt(n)``, also entspricht ein t-Verhaeltnis dem Quadrat
        in der Stichprobe. Ohne diese Umrechnung waere die Zeitkuerzung nicht
        mit der Blockkuerzung des Gates vergleichbar."""
        halbiert = bild(trades=100, roh=2.0, gate=2.0, woche=1.0, null=2.0)

        assert halbiert.kuerzung_zeit == pytest.approx(0.75)
        assert halbiert.effektiv_nach_zeit == 25
        assert halbiert.kuerzung_gate == pytest.approx(0.0)
        assert halbiert.luecke == pytest.approx(0.75)


class TestUrteil:
    def test_eine_grosse_luecke_wird_benannt(self) -> None:
        pruefung = Zeitpruefung(
            bilder=[
                bild(name=f"r{i}", roh=2.0, gate=2.0, woche=1.5, null=2.0)
                for i in range(8)
            ]
        )

        assert pruefung.genug
        assert pruefung.nullprobe_traegt
        assert not pruefung.gate_kuerzt_genug
        urteil = pruefung.urteil()
        assert "kuerzt zu wenig" in urteil
        assert "keine Lockerung und kein neues Gate" in urteil

    def test_ein_mithaltendes_gate_wird_auch_so_benannt(self) -> None:
        """Gegenprobe: Der Test verwirft nicht jedes Gate. Kuerzt die
        Blockrechnung so viel wie die Zeitachse verlangt, sagt das Urteil
        das."""
        pruefung = Zeitpruefung(
            bilder=[
                bild(name=f"r{i}", roh=2.0, gate=1.6, woche=1.6, null=2.0)
                for i in range(8)
            ]
        )

        assert pruefung.gate_kuerzt_genug
        assert pruefung.mittlere_luecke == pytest.approx(0.0, abs=1e-9)
        assert "haelt im Schnitt mit" in pruefung.urteil()

    def test_die_kontrolle_schlaegt_an_wenn_die_nullprobe_danebenliegt(self) -> None:
        """Landet die Nullprobe nicht an der Trade-Achse, wird nichts
        geschlossen - statt das Ergebnis trotzdem auszurechnen."""
        pruefung = Zeitpruefung(
            bilder=[
                bild(name=f"r{i}", roh=2.0, gate=2.0, woche=1.5, null=1.0)
                for i in range(8)
            ]
        )

        assert not pruefung.nullprobe_traegt
        assert "Kontrolle faellt durch" in pruefung.urteil()

    def test_gegenlaeufige_kuerzung_wird_benannt(self) -> None:
        """Kuerzt das Gate dort viel, wo die Zeitachse wenig verlangt, ist es
        nicht bloss zu schwach eingestellt - dann misst es etwas anderes, und
        Hochskalieren hilft nicht."""
        stark = [
            bild(name=f"hoch{i}", roh=2.0, gate=1.7, woche=1.98, null=2.0)
            for i in range(5)
        ]
        schwach = [
            bild(name=f"tief{i}", roh=2.0, gate=2.0, woche=1.0, null=2.0)
            for i in range(5)
        ]
        pruefung = Zeitpruefung(bilder=stark + schwach)

        wert = pruefung.kuerzt_an_der_richtigen_stelle
        assert wert is not None
        assert wert < -0.8
        assert not pruefung.gate_kuerzt_genug
        assert "gegenlaeufig" in pruefung.urteil()
        assert "hochskalieren" in pruefung.urteil()

    def test_ein_stimmender_mittelwert_verdeckt_die_stelle_nicht(self) -> None:
        """**Der zweite Mangel, den die Tests aufgedeckt haben.**

        Ein Gate kann im Schnitt genau richtig kuerzen und trotzdem in jeder
        einzelnen Zeile danebenliegen - der gefaehrlichere Fall, weil er wie
        Ordnung aussieht. Der erste Entwurf meldete dann nur "haelt mit" und
        verschwieg die Stellenfrage.
        """
        stark = [
            bild(name=f"hoch{i}", roh=2.0, gate=1.5, woche=2.0, null=2.0)
            for i in range(5)
        ]
        schwach = [
            bild(name=f"tief{i}", roh=2.0, gate=2.0, woche=1.5, null=2.0)
            for i in range(5)
        ]
        pruefung = Zeitpruefung(bilder=stark + schwach)

        assert pruefung.gate_kuerzt_genug, "im Mittel gleicht es sich aus"
        urteil = pruefung.urteil()
        assert "haelt im Schnitt mit" in urteil
        assert "nicht an der richtigen Stelle" in urteil
        assert "Der Mittelwert stimmt, die einzelnen Zeilen nicht" in urteil


class TestGrenzen:
    def test_verlierende_regeln_zaehlen_nicht_mit(self) -> None:
        """**Die Falle, die beim ersten Anlauf sichtbar wurde.**

        Bei negativem t-Wert bedeutet ein kleinerer Betrag eine Verbesserung.
        'VWAP-Rueckkehr short' zeigt eine Luecke von +17 %, aber dort heisst
        das Gegenteil. Wer solche Zeilen mitmittelt, addiert Zahlen mit
        entgegengesetzter Bedeutung.
        """
        verlierer = bild(name="verlierer", roh=-1.5, gate=-1.3, woche=-1.1, null=-1.5)
        gewinner = [
            bild(name=f"r{i}", roh=2.0, gate=2.0, woche=1.5, null=2.0)
            for i in range(7)
        ]
        pruefung = Zeitpruefung(bilder=[verlierer, *gewinner])

        assert not verlierer.beurteilbar
        assert len(pruefung.bilder) == 8
        assert len(pruefung.beurteilbare) == 7
        assert "verlierende Regel" in pruefung.tabelle()
        assert "*verlierer" in pruefung.tabelle()

    def test_zu_wenige_regeln_liefern_nichts(self) -> None:
        duenn = Zeitpruefung(bilder=[bild()])

        assert not duenn.genug
        assert duenn.kuerzt_an_der_richtigen_stelle is None
        assert "nichts sagen" in duenn.urteil()

    def test_die_schwelle_steht_an_einer_stelle(self) -> None:
        """Genau auf der Schwelle gilt das Gate noch als mithaltend - sonst
        haenge das Urteil an einem Rundungsfehler."""
        grenzfall = Zeitpruefung(
            bilder=[
                Zeitbild(
                    name=f"r{i}", trades=100, t_roh=1.0, t_gate=1.0,
                    t_woche=(1.0 - SPUERBAR) ** 0.5, t_null=1.0,
                )
                for i in range(8)
            ]
        )

        assert grenzfall.mittlere_luecke == pytest.approx(SPUERBAR)
        assert grenzfall.gate_kuerzt_genug


class TestNachweisschwelle:
    """Die Korrektur aus Befund 88.

    Die erste Fassung schloss aus r = -0,470 ueber 18 Regeln, das Gate kuerze
    gegenlaeufig. Entdoppelt sind es -0,261 ueber 12 Regeln, also t = -0,86 -
    nicht nachweisbar. Dieselbe Schranke wie in ``partnerkarte.urteil`` seit
    Befund 75: unter |t| = 2 wird nichts geschlossen.
    """

    def test_ein_schwacher_zusammenhang_traegt_keinen_schluss(self) -> None:
        wuerfel = np.random.default_rng(88)
        bilder = []
        for i in range(12):
            # Unabhaengig gezogen, damit die Korrelation schwach bleibt - und
            # mit genug Abstand, damit der Zweig greift, der auf den echten
            # Daten greift (Luecke 11,7 % ueber der Schwelle von 10 %).
            gate = float(wuerfel.uniform(0.0, 0.20))
            zeit = float(wuerfel.uniform(0.10, 0.60))
            bilder.append(
                Zeitbild(
                    name=f"r{i}", trades=100, t_roh=2.0,
                    t_gate=2.0 * (1 - gate) ** 0.5,
                    t_woche=2.0 * (1 - zeit) ** 0.5, t_null=2.0,
                )
            )
        pruefung = Zeitpruefung(bilder=bilder)

        r = pruefung.kuerzt_an_der_richtigen_stelle
        assert r is not None and abs(r) < 0.5
        assert not pruefung.stelle_ist_belegt
        urteil = pruefung.urteil()
        assert "bleibt offen" in urteil
        assert "nicht nachweisbar" in urteil
        assert "gegenlaeufig" not in urteil

    def test_ein_starker_zusammenhang_traegt_ihn_doch(self) -> None:
        """Gegenprobe: Die Schranke blockiert nicht alles. Bei klarer
        Gegenlaeufigkeit ueber genug Regeln faellt der Schluss."""
        stark = [
            bild(name=f"hoch{i}", roh=2.0, gate=1.7, woche=1.98, null=2.0)
            for i in range(7)
        ]
        schwach = [
            bild(name=f"tief{i}", roh=2.0, gate=2.0, woche=1.0, null=2.0)
            for i in range(7)
        ]
        pruefung = Zeitpruefung(bilder=stark + schwach)

        assert pruefung.stelle_ist_belegt
        assert "gegenlaeufig" in pruefung.urteil()
