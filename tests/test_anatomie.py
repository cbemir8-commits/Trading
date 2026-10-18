"""Was traegt ein Bauteil des Kandidaten? - Befund 366.

Die Sperrprobe (58, 44, 271) fragt, ob eine **Trade-Entfernung** mehr leistet
als dieselbe Zahl beliebiger Entfernungen. Dem Spitzenkandidaten steht aber ein
Bauteil im Namen, das sie nicht beurteilen kann: *"Trend 50 Tage mit
Konfluenz"*. Seine drei Konfluenz-Bedingungen streichen **9 Signale** und
**keinen einzigen Trade** - die Balken, die sie treffen, trugen ohnehin keinen
Einstieg, weil dort schon eine Position offen war.

Die Null der Sperrprobe zieht aus den Signalen des Kandidaten, und die
gestrichenen liegen nicht darin. Gemessen, bevor dieses Modul entstand:

    ohne Konfluenz                            156 Trades, Guete 0,269308
    ohne Konfluenz + ihre 9 Signale gesperrt  156 Trades, Guete 0,269308

Bitgleich - eine Sperrprobe haette hier eine selbstbewusste Null gemeldet.

Die Ablation stattdessen, am Spot-Punkt:

    mit Konfluenz    156 Trades  Guete 0,2708  DSR 0,5826  9 von 11
    ohne Konfluenz   156 Trades  Guete 0,2720  DSR 0,5470  7 von 11

Das Bauteil **traegt** - und anders als erwartet: Die Guete je Trade wird ohne
es winzig besser. Was es haelt, ist das Risiko (Rueckgang 9,87 % statt 12,54 %)
und damit Drawdown, Schlechtestes Jahr und Parameter-Plateau.
"""

from __future__ import annotations

import pytest

from research.anatomie import (
    BAUTEILE,
    Anatomie,
    Lage,
    ohne_bauteil,
    traegt_das_bauteil,
    vergleiche,
)


def _lage(**kwargs) -> Lage:
    grund = {
        "trades": 156, "guete": 0.27, "dsr": 0.58, "rueckgang_pct": 9.9,
        "bestanden": 9, "gesamt": 11, "gefallen": ("Messlatte", "Deflated Sharpe"),
    }
    return Lage(**{**grund, **kwargs})


def _genom():
    from research.seeds import spitzenkandidat

    return spitzenkandidat()


class TestDasBauteilWirdWeggelassenUndSonstNichts:
    def test_die_konfluenz_verschwindet(self) -> None:
        genom = _genom()

        schlank = ohne_bauteil(genom, "konfluenz")

        assert genom.konfluenz, "Vorbedingung: der Kandidat hat Konfluenz"
        assert schlank.konfluenz == []

    def test_alles_andere_bleibt_bitgleich(self) -> None:
        """Sonst misst die Ablation zwei Unterschiede und schreibt sie einem
        zu."""
        genom = _genom()

        schlank = ohne_bauteil(genom, "konfluenz")
        a = genom.model_dump()
        b = schlank.model_dump()

        assert a.pop("konfluenz") != b.pop("konfluenz")
        assert a == b

    def test_ein_unbekanntes_bauteil_ist_ein_fehler(self) -> None:
        """Ein vertippter Name wuerde das Genom unveraendert lassen - die
        Ablation waere bitgleich, und das saehe aus wie 'traegt nichts'."""
        with pytest.raises(ValueError, match="Unbekanntes Bauteil"):
            ohne_bauteil(_genom(), "konfluens")

    @pytest.mark.parametrize("name", sorted(BAUTEILE))
    def test_jedes_bauteil_ist_ein_feld_des_genoms(self, name: str) -> None:
        genom = _genom()

        for feld in BAUTEILE[name]:
            assert hasattr(genom, feld), f"'{feld}' ist kein Feld des Genoms"

    def test_was_der_kandidat_nicht_hat_wird_erkannt(self) -> None:
        """Der Kandidat hat keine Filter - eine Ablation darauf waere ein
        Vergleich mit sich selbst."""
        genom = _genom()

        assert traegt_das_bauteil(genom, "konfluenz")
        assert not traegt_das_bauteil(genom, "filter")

    def test_und_zurueckgewiesen(self) -> None:
        with pytest.raises(ValueError, match="kein Bauteil"):
            vergleiche(_genom(), "filter", lambda g: _lage())


class TestDasUrteilHaengtAnDenGatesUndNichtAnDerGuete:
    """**Der Kern des Befundes.** Wer nach der Guete urteilte, haette die
    Konfluenz gestrichen: Ohne sie ist die Guete je Trade besser."""

    @staticmethod
    def _anatomie(mit: Lage, ohne: Lage) -> Anatomie:
        return Anatomie(bauteil="konfluenz", mit=mit, ohne=ohne, signale={"x": 9})

    def test_bessere_guete_ohne_bauteil_und_es_traegt_trotzdem(self) -> None:
        lage = self._anatomie(
            _lage(guete=0.2708, bestanden=9),
            _lage(guete=0.2720, bestanden=7, gefallen=("Drawdown", "Messlatte")),
        )

        assert lage.guete_differenz < 0, "ohne Bauteil ist die Guete besser"
        assert lage.traegt, "es haelt trotzdem Gates"
        assert lage.gates_differenz == 2

    def test_das_urteil_nennt_die_gates_die_es_haelt(self) -> None:
        lage = self._anatomie(
            _lage(bestanden=9, gefallen=("Messlatte",)),
            _lage(bestanden=7, gefallen=("Messlatte", "Drawdown", "Schlechtestes Jahr")),
        )

        urteil = lage.urteil()

        assert "haelt" in urteil
        assert "Drawdown" in urteil
        assert "Schlechtestes Jahr" in urteil
        assert "Messlatte" not in urteil, (
            "ein Gate, das in beiden Faellen faellt, kippt nicht"
        )

    def test_ohne_unterschied_wird_auf_271_verwiesen(self) -> None:
        """Der Fall des Termin-Overlays: zu klein, um zu zaehlen."""
        lage = self._anatomie(_lage(bestanden=9), _lage(bestanden=9))

        urteil = lage.urteil()

        assert not lage.traegt
        assert "271" in urteil


    def test_ein_bauteil_kann_auch_kosten(self) -> None:
        """Die Aufstellung muss zu sich passen (berichtigt in Befund 367).

        Hier stand zweimal dieselbe Liste gefallener Gates bei
        verschiedenen Zahlen - 7 gegen 9, aber kein Gate, das kippt. Das
        beidseitige Urteil hat das aufgedeckt: Es nannte zu Recht "kein Gate
        kippt in eine der beiden Richtungen".
        """
        lage = self._anatomie(
            _lage(bestanden=7, gefallen=("Deflated Sharpe", "Messlatte", "Drawdown")),
            _lage(bestanden=9, gefallen=("Deflated Sharpe",)),
        )

        assert lage.gates_differenz == -2
        assert lage.gates_nur_mit == ("Messlatte", "Drawdown")
        assert lage.gates_nur_ohne == ()
        assert "kostet" in lage.urteil()
        assert not lage.tauscht

    def test_die_gestrichenen_signale_stehen_im_urteil(self) -> None:
        """Die Zahl, die zeigt, warum die Sperrprobe hier nichts ausrichtet."""
        lage = Anatomie(
            bauteil="konfluenz", mit=_lage(), ohne=_lage(bestanden=7),
            signale={"BTCUSD_BITSTAMP": 1, "ETHUSD_BITSTAMP": 8},
        )

        assert "9 Signale" in lage.urteil()


class TestDieAblationRechnetInBeideRichtungen:
    """**Befund 367, und es war meine Luecke von gestern.** Das Urteil nannte
    nur die gehaltenen Gates. Dieselbe Messung zeigt aber, dass die Messlatte
    umgekehrt kippt: Sie faellt **nur mit** der Konfluenz. Wer das Urteil las,
    hielt das Bauteil fuer umsonst zu haben.
    """

    @staticmethod
    def _tausch() -> Anatomie:
        return Anatomie(
            bauteil="konfluenz",
            mit=_lage(bestanden=9, gefallen=("Messlatte", "Deflated Sharpe")),
            ohne=_lage(
                bestanden=7,
                gefallen=(
                    "Drawdown", "Schlechtestes Jahr", "Deflated Sharpe",
                    "Parameter-Plateau",
                ),
            ),
            signale={"BTCUSD_BITSTAMP": 1, "ETHUSD_BITSTAMP": 8},
        )

    def test_was_das_bauteil_kostet_wird_genannt(self) -> None:
        lage = self._tausch()

        assert lage.gates_nur_mit == ("Messlatte",)

    def test_und_was_es_haelt(self) -> None:
        lage = self._tausch()

        assert set(lage.gates_nur_ohne) == {
            "Drawdown", "Schlechtestes Jahr", "Parameter-Plateau"
        }

    def test_ein_gate_das_immer_faellt_kippt_nicht(self) -> None:
        """Der Deflated Sharpe faellt in beiden Faellen - er gehoert in keine
        der beiden Listen."""
        lage = self._tausch()

        assert "Deflated Sharpe" not in lage.gates_nur_mit
        assert "Deflated Sharpe" not in lage.gates_nur_ohne

    def test_das_urteil_nennt_beide_richtungen(self) -> None:
        urteil = self._tausch().urteil()

        assert "haelt" in urteil
        assert "kostet" in urteil
        assert "Messlatte" in urteil
        assert "Drawdown" in urteil

    def test_und_sagt_dass_getauscht_wird(self) -> None:
        """Die Netto-Zahl sagt nicht, woraus sie besteht."""
        lage = self._tausch()

        assert lage.tauscht
        assert "tauscht" in lage.urteil()
        assert "3 gehalten gegen 1 gekostet" in lage.urteil()
        assert lage.gates_differenz == 2

    def test_ein_bauteil_das_nur_haelt_tauscht_nicht(self) -> None:
        lage = Anatomie(
            bauteil="konfluenz",
            mit=_lage(bestanden=9, gefallen=()),
            ohne=_lage(bestanden=8, gefallen=("Drawdown",)),
        )

        assert not lage.tauscht
        assert "kostet" not in lage.urteil()

    def test_der_befehl_zeigt_die_kippenden_mit_zahlen(self) -> None:
        """Ein Gate, das kippt, ist ohne Wert und Schwelle nur ein Name."""
        quelle = TestDerBefehlMisstDenZulassungspunkt._quelle()

        assert "gates_nur_mit" in quelle
        assert "kostet es" in quelle

    def test_und_warnt_vor_dem_vergleich_der_spalten(self) -> None:
        """Bei der Messlatte meldet 'value' entweder die Rendite gegen die
        heruntergefahrene Messlatte oder die Jahresrendite gegen die
        Betriebsschwelle (Befund 267) - die beiden Spalten koennen also
        verschiedene Bedingungen zeigen."""
        quelle = TestDerBefehlMisstDenZulassungspunkt._quelle()

        assert "Befund 267" in quelle
        assert "nicht\ngegeneinander zu lesen" in quelle or (
            "nicht " in quelle and "gegeneinander zu lesen" in quelle
        )


class TestBeideLaeufeKommenAusDemselbenMessaufbau:
    def test_vergleiche_ruft_zweimal(self) -> None:
        gerufen = []

        def messe(g) -> Lage:
            gerufen.append(g)
            return _lage()

        vergleiche(_genom(), "konfluenz", messe)

        assert len(gerufen) == 2
        assert gerufen[0].konfluenz
        assert gerufen[1].konfluenz == []

    def test_die_signale_werden_uebernommen(self) -> None:
        lage = vergleiche(
            _genom(), "konfluenz", lambda g: _lage(), signale={"a": 3, "b": 4}
        )

        assert sum(lage.signale.values()) == 7


class TestDerBefehlMisstDenZulassungspunkt:
    """Eine Ablation auf einem anderen Punkt als dem dokumentierten ist eine
    Aussage ueber irgendeinen Lauf. Der erste Anlauf dieses Befehls nahm die
    Rohdaten und die Standardbedingungen und kam auf 159 Trades, Guete 0,2580
    und 7 von 11."""

    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "anatomie":
                return ast.unparse(knoten)
        raise AssertionError("'anatomie' steht nicht mehr in cli.py")

    def test_die_reihe_wird_geschnitten(self) -> None:
        assert "alle_geschnitten(frames)" in self._quelle()

    def test_die_spot_bedingungen_werden_genommen(self) -> None:
        assert "_spotconfigs(symbole, settings)" in self._quelle()

    def test_der_hebel_wird_gedeckelt(self) -> None:
        assert "_ohne_hebel(spitzenkandidat())" in self._quelle()

    def test_die_gegenprobe_gegen_den_spotpunkt_steht_drin(self) -> None:
        """Trifft 'mit' den dokumentierten Punkt nicht, ist auch 'ohne' nichts
        wert - und dann muss es dastehen."""
        quelle = self._quelle()

        assert "SPOTPUNKT.trades" in quelle
        assert "SPOTPUNKT.guete" in quelle
        assert "SPOTPUNKT.bestanden" in quelle
        assert "trifft den Spot-Punkt nicht" in quelle

    def test_und_nennt_die_haeufigste_ursache(self) -> None:
        assert "Zulassungsreihe" in self._quelle()

    def test_kein_versuch_wird_gebucht(self) -> None:
        """Gemessen wird ein Bauteil, das der Kandidat schon hat."""
        quelle = self._quelle()

        assert "load_trials" in quelle
        assert "save_trials" not in quelle
        assert "nicht erhoeht" in quelle


class TestDasRegisterHaeltDenFund:
    def test_er_steht_unter_behoben(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 366)

        assert "9 von 11" in eintrag.ergebnis or "9/11" in eintrag.ergebnis
        assert "271" in eintrag.ergebnis, "der Unterschied zum Kalender gehoert dazu"


@pytest.mark.langsam
@pytest.mark.daten
def test_die_ablation_am_spotpunkt_stimmt_mit_dem_lauf_ueberein() -> None:
    """Die gemessenen Zahlen, gegen den Lauf gehalten.

    Die Zeile "mit" ist dabei die Gegenprobe: Sie muss den dokumentierten
    Spot-Punkt wiederholen, sonst misst dieser Test eine Ablation auf einem
    anderen Punkt - genau der Fehler aus dem ersten Anlauf des Befehls.
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.admission import load_trials
    from research.datenstand import alle_geschnitten
    from research.gates import GateStatus, evaluate_gates
    from research.randschnitt import fertige
    from research.referenz import SPOTPUNKT
    from research.seeds import spitzenkandidat
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    e = get_settings()
    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    frames, _, _ = cli._korb_daten(symbole, Interval("D"), e)
    frames = alle_geschnitten(frames)
    if any(f.empty for f in frames.values()):
        pytest.skip("keine Kerzen im Speicher")
    configs = cli._spotconfigs(symbole, e)
    versuche = load_trials(Path(e.paths.state) / "trials.json")

    def messe(genom) -> Lage:
        bericht = run_portfolio_walkforward(
            frames, lambda g=genom: compile_genome(g), configs
        )
        gates = evaluate_gates(
            genom, bericht, next(iter(frames.values())), configs[symbole[0]],
            trials_so_far=versuche, frames=frames, configs=configs,
        )
        gehandelt = fertige(bericht.all_trades)
        form = Kandidat.aus_trades("", gehandelt)
        return Lage(
            trades=len(gehandelt),
            guete=form.sharpe_je_trade if form else 0.0,
            dsr=float(
                next(
                    (r.value for r in gates.results if r.name == "Deflated Sharpe"),
                    0.0,
                )
            ),
            rueckgang_pct=(
                bericht.combined.max_drawdown_pct if bericht.combined else 0.0
            ),
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
            gefallen=tuple(r.name for r in gates.results if not r.passed),
            uebersprungen=sum(
                1 for r in gates.results if r.status is GateStatus.SKIP
            ),
        )

    lage = vergleiche(cli._ohne_hebel(spitzenkandidat()), "konfluenz", messe)

    # Die Gegenprobe zuerst.
    assert lage.mit.trades == SPOTPUNKT.trades
    assert lage.mit.guete == pytest.approx(SPOTPUNKT.guete, abs=5e-4)
    assert lage.mit.bestanden == SPOTPUNKT.bestanden

    # Und dann der Fund: Die Guete wird ohne das Bauteil besser, die Gates
    # werden weniger.
    assert lage.ohne.trades == 156
    assert lage.ohne.guete == pytest.approx(0.2720, abs=5e-4)
    assert lage.ohne.guete > lage.mit.guete, "ohne Bauteil ist die Guete besser"
    assert lage.ohne.dsr == pytest.approx(0.5470, abs=5e-4)
    assert lage.ohne.bestanden == 7
    assert lage.traegt
    assert set(lage.gates_nur_ohne) == {
        "Drawdown", "Schlechtestes Jahr", "Parameter-Plateau"
    }
    # Das Risiko ist es, nicht die Qualitaet.
    assert lage.ohne.rueckgang_pct > lage.mit.rueckgang_pct

    # Und keine der beiden Neunen enthaelt ein geschenktes Urteil: 156 Trades
    # liegen weit ueber jeder Aussetzschwelle (Befunde 321/322).
    assert not lage.uebersprungen_irgendwo


class TestDasGitterFaehrtAlleTeilmengen:
    """**Befund 368.** Die Ablation kennt zwei Punkte - mit Bauteil und ohne.
    Bei drei Bedingungen liegen dazwischen sechs weitere Fassungen, und erst
    sie sagen, ob der Tausch aus Befund 367 unvermeidlich ist oder nur die
    eine Kante trifft, die zufaellig gemessen wurde.
    """

    def test_acht_fassungen_bei_drei_bedingungen(self) -> None:
        from research.anatomie import teilmengen

        fassungen = teilmengen(_genom(), "konfluenz")

        assert len(fassungen) == 8

    def test_der_bestand_steht_oben(self) -> None:
        """Damit die Gegenprobe gegen den dokumentierten Punkt die erste
        Zeile ist."""
        from research.anatomie import teilmengen

        erste, _ = teilmengen(_genom(), "konfluenz")[0]

        assert erste == (0, 1, 2)

    def test_jede_fassung_kommt_genau_einmal(self) -> None:
        from research.anatomie import teilmengen

        behalten = [b for b, _ in teilmengen(_genom(), "konfluenz")]

        assert len(set(behalten)) == len(behalten)

    def test_die_bedingungen_werden_wirklich_gesetzt(self) -> None:
        from research.anatomie import teilmengen

        genom = _genom()
        for behalten, fassung in teilmengen(genom, "konfluenz"):
            assert len(fassung.konfluenz) == len(behalten)
            for platz, bedingung in zip(behalten, fassung.konfluenz, strict=True):
                assert bedingung == genom.konfluenz[platz]

    def test_ein_zu_grosses_gitter_wird_abgelehnt(self) -> None:
        """Zwei hoch sechs sind vierundsechzig Laeufe - eine halbe Stunde, die
        niemand aus Versehen starten soll."""
        from research.anatomie import GITTERGRENZE, teilmengen

        genom = _genom()
        viele = genom.model_copy(
            update={"konfluenz": list(genom.konfluenz) * 3}
        )

        assert len(viele.konfluenz) > GITTERGRENZE
        with pytest.raises(ValueError, match="Grenze"):
            teilmengen(viele, "konfluenz")


class TestDasGitterUrteiltVorsichtig:
    @staticmethod
    def _gitter(*paare):
        from research.anatomie import Gitter, Sprosse

        return Gitter(
            bauteil="konfluenz",
            sprossen=[
                Sprosse(behalten=b, lage=_lage(bestanden=n)) for b, n in paare
            ],
        )

    def test_der_bestand_ist_die_fassung_mit_allen_bedingungen(self) -> None:
        gitter = self._gitter(((0, 1, 2), 9), ((0,), 8), ((), 7))

        assert gitter.bestand.behalten == (0, 1, 2)

    def test_nichts_zu_holen_wird_gesagt(self) -> None:
        """Der gemessene Fall: keine der acht Fassungen kommt ueber neun."""
        gitter = self._gitter(((0, 1, 2), 9), ((1, 2), 9), ((2,), 7), ((), 7))

        urteil = gitter.urteil()

        assert gitter.besser_als_der_bestand == []
        assert "nichts zu holen" in urteil
        assert "wechseln nur die Identitaet" in urteil

    def test_eine_bessere_fassung_ist_ein_vorschlag_und_kein_ergebnis(self) -> None:
        """**Die Warnung steht in 'konfluenzwirkung.py', und dort zuerst**:
        Die beste Fassung zu nehmen ist die Auswahl des besten Eimers nach
        Ansicht der Daten.
        """
        gitter = self._gitter(((0, 1, 2), 9), ((1, 2), 10), ((), 7))

        urteil = gitter.urteil()

        assert [s.name for s in gitter.besser_als_der_bestand] == ["2+3"]
        assert "kein Ergebnis" in urteil
        assert "besten Eimers" in urteil
        assert "kostet einen Versuch" in urteil

    def test_mehrere_beste_werden_alle_genannt(self) -> None:
        gitter = self._gitter(((0, 1, 2), 9), ((1, 2), 9), ((0,), 9), ((), 7))

        assert len(gitter.beste) == 3

    def test_die_namen_zaehlen_ab_eins(self) -> None:
        """Im Bericht stehen die Bedingungen als 1, 2, 3 - nicht als 0, 1, 2."""
        gitter = self._gitter(((0, 2), 9))

        assert gitter.sprossen[0].name == "1+3"

    def test_die_leere_fassung_heisst_keine(self) -> None:
        gitter = self._gitter(((), 7))

        assert gitter.sprossen[0].name == "keine"


class TestDieBedingungenStehenLesbarDa:
    def test_ein_indikatorvergleich(self) -> None:
        from research.anatomie import bedingungstext

        genom = _genom()

        assert bedingungstext(genom.konfluenz[0]) == (
            "sma(period=50) gt sma(period=200)"
        )

    def test_eine_konstante_ohne_nachkommanullen(self) -> None:
        """``0.0`` liest sich als Rauschen, ``0`` als Schwelle."""
        from research.anatomie import bedingungstext

        texte = [bedingungstext(b) for b in _genom().konfluenz]

        assert "roc(period=90) gt 0" in texte
        assert not any(".0 " in t or t.endswith(".0") for t in texte)

    def test_der_befehl_zeigt_sie_an(self) -> None:
        quelle = TestDerBefehlMisstDenZulassungspunkt._quelle()

        assert "bedingungstext(bed)" in quelle
        assert "--einzeln" in quelle


@pytest.mark.langsam
@pytest.mark.daten
def test_die_fassung_die_die_messlatte_haelt_kommt_trotzdem_nicht_weiter() -> None:
    """Der Kern von Befund 368, auf zwei Laeufe eingekocht.

    Das ganze Gitter faehrt ``cli anatomie --bauteil konfluenz --einzeln``
    (acht Laeufe, rund vier Minuten). Hier stehen die zwei, auf die es
    ankommt: der Bestand als Gegenprobe und ``2+3`` - die einzige Fassung, die
    die **Messlatte** haelt. Sie kommt trotzdem nicht ueber neun von elf, weil
    dort das **Schlechteste Jahr** faellt.

    Das ist die Form der Wand: Jede Fassung unter 15 % Jahresrendite verliert
    die Messlatte, jede darueber ein Risiko-Gate.
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.admission import load_trials
    from research.datenstand import alle_geschnitten
    from research.gates import GateStatus, evaluate_gates
    from research.randschnitt import fertige
    from research.referenz import SPOTPUNKT
    from research.seeds import spitzenkandidat
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    e = get_settings()
    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    frames, _, _ = cli._korb_daten(symbole, Interval("D"), e)
    frames = alle_geschnitten(frames)
    if any(f.empty for f in frames.values()):
        pytest.skip("keine Kerzen im Speicher")
    configs = cli._spotconfigs(symbole, e)
    versuche = load_trials(Path(e.paths.state) / "trials.json")
    basis = cli._ohne_hebel(spitzenkandidat())

    def messe(genom):
        bericht = run_portfolio_walkforward(
            frames, lambda g=genom: compile_genome(g), configs
        )
        gates = evaluate_gates(
            genom, bericht, next(iter(frames.values())), configs[symbole[0]],
            trials_so_far=versuche, frames=frames, configs=configs,
        )
        gehandelt = fertige(bericht.all_trades)
        form = Kandidat.aus_trades("", gehandelt)
        lage = Lage(
            trades=len(gehandelt),
            guete=form.sharpe_je_trade if form else 0.0,
            dsr=0.0,
            rueckgang_pct=(
                bericht.combined.max_drawdown_pct if bericht.combined else 0.0
            ),
            bestanden=sum(1 for r in gates.results if r.passed),
            gesamt=len(gates.results),
            gefallen=tuple(r.name for r in gates.results if not r.passed),
            uebersprungen=sum(
                1 for r in gates.results if r.status is GateStatus.SKIP
            ),
        )
        return lage, bericht.combined.cagr_pct

    bestand, cagr_bestand = messe(basis)
    zwei_drei, cagr_zwei_drei = messe(
        basis.model_copy(update={"konfluenz": list(basis.konfluenz)[1:]})
    )

    # Die Gegenprobe zuerst.
    assert bestand.trades == SPOTPUNKT.trades
    assert bestand.bestanden == SPOTPUNKT.bestanden
    assert "Messlatte" in bestand.gefallen
    assert cagr_bestand == pytest.approx(14.34, abs=0.05)

    # Und der Fund: Die Messlatte haelt, das Schlechteste Jahr faellt, die
    # Gate-Zahl bleibt.
    assert cagr_zwei_drei > 15.0, "ueber der Betriebsschwelle"
    assert "Messlatte" not in zwei_drei.gefallen
    assert "Schlechtestes Jahr" in zwei_drei.gefallen
    assert zwei_drei.bestanden == bestand.bestanden == 9
    assert zwei_drei.rueckgang_pct > bestand.rueckgang_pct
    assert not zwei_drei.uebersprungen
