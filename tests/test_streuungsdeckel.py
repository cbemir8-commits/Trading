"""Die geratene Eingabe im Deflated Sharpe - Befund 340.

Fuenfter und letzter Verdachtsfall der Wache von Befund 335, und der mit dem
hoechsten Einsatz: Der Eintrag steht auf dem Gate, das die Zulassung allein
blockiert.

Der Eintrag las sich seit Befund 69 wie ein Weg durch die Wand:

    "Aus den 28 Versuchen, die ihren Sharpe je Trade mittragen, kaemen
     0,0608 - und damit 0,97 statt 0,79."

**Heute ist es umgekehrt.** Gemessen:

    Annahme im Gate            0,0909
    Streuung der 61 Punkte     0,1072     breiter, nicht enger
    DSR mit der Annahme        0,5958
    DSR mit der Messung        0,2761     tiefer durchgefallen
    Kippunkt                   0,0636     Annahme 43 % darueber

Die gemessene Streuung wuerde die Huerde also **heben**. Damit ist die
Entscheidung kleiner als sie aussah: Sie ist nicht "Messung statt Annahme",
sondern nur, ob das Verzeichnis kuenftig jeden Versuch mitschreibt.

Was stimmt, ist der Deckel. Der Eintrag sagte "hoechstens 40 %" als Prosa;
gerechnet sind es 38 %, denn jeder kuenftige Versuch kann einen Punkt
beitragen und kein vergangener mehr: 61 + 27 von 230.
"""

from __future__ import annotations

import pytest

from research.streuung import MINDESTABDECKUNG, Empfindlichkeit, Streuung, Versuchspunkt

#: Die Zahlen von 'cli streuung' am heutigen Stand (Befund 340).
ANNAHME = 0.0909
GEMESSEN = 0.1072
KIPPUNKT = 0.0636
DSR_ANNAHME = 0.5958
DSR_GEMESSEN = 0.2761


def _punkte(werte: list[float], quelle: str = "Berichte") -> list[Versuchspunkt]:
    return [
        Versuchspunkt(quelle=quelle, kennung=f"{quelle} {i}", sharpe_je_trade=w)
        for i, w in enumerate(werte)
    ]


class TestDerDeckelIstGerechnet:
    """**Befund 340.** "Auf hoechstens 40 % gedeckelt" stand als Prosa im
    Eintrag - ungerechnet, und damit genau die Bauart, die Befund 212 an der
    Historienkurve abgestellt hat."""

    def test_die_obergrenze_zaehlt_nur_kuenftige_versuche(self) -> None:
        """61 Punkte, 203 Versuche, Abbruch bei 230: Die 27 offenen koennen je
        einen Punkt bringen, die 142 fehlenden nie mehr einen."""
        lage = Streuung(punkte=_punkte([0.1] * 61), versuche=203, grenze=230)

        assert lage.deckel == pytest.approx(88 / 230, abs=1e-9)
        assert lage.deckel == pytest.approx(0.38, abs=0.005)

    def test_und_damit_ist_die_schwelle_nicht_erreichbar(self) -> None:
        lage = Streuung(punkte=_punkte([0.1] * 61), versuche=203, grenze=230)

        assert not lage.erreichbar
        assert MINDESTABDECKUNG == 0.9

    def test_ohne_budget_gibt_es_keine_obergrenze(self) -> None:
        """``None`` und nicht 1,0: Eine Obergrenze ohne Budget waere eine
        erfundene Zahl."""
        lage = Streuung(punkte=_punkte([0.1] * 61), versuche=203)

        assert lage.deckel is None
        assert not lage.erreichbar

    def test_die_obergrenze_kann_erreichbar_sein(self) -> None:
        """Die Gegenprobe: Der Deckel ist kein fest verdrahtetes 'nein'.
        Waere der Grundstock belegt, ginge es."""
        lage = Streuung(punkte=_punkte([0.1] * 200), versuche=203, grenze=230)

        assert lage.deckel == pytest.approx(227 / 230, abs=1e-9)
        assert lage.erreichbar

    def test_sie_bleibt_bei_hundert_prozent_stehen(self) -> None:
        """Mehr Punkte als Versuche sind moeglich - eine Quelle kann denselben
        Versuch zweimal nennen -, eine Abdeckung ueber 100 % nicht."""
        lage = Streuung(punkte=_punkte([0.1] * 400), versuche=203, grenze=230)

        assert lage.deckel == 1.0

    def test_das_urteil_nennt_die_obergrenze(self) -> None:
        lage = Streuung(
            punkte=_punkte([0.1, 0.2, 0.3] * 20 + [0.15]), versuche=203, grenze=230
        )
        urteil = lage.urteil()

        assert "nicht mehr zu holen" in urteil
        assert "von 230 Punkten" in urteil
        assert "gegen die verlangten 90%" in urteil

    def test_der_grund_steht_dabei(self) -> None:
        """Nicht "geht nicht", sondern warum: Der Grundstock hat keine
        Einzelnachweise, und nachtraegliche Berichte waeren erfunden."""
        lage = Streuung(punkte=_punkte([0.1, 0.2] * 30), versuche=203, grenze=230)

        assert "nachtraegliche Berichte waeren erfunden" in lage.urteil()

    def test_ohne_budget_bleibt_der_satz_weg(self) -> None:
        """Ein Satz, der immer dasteht, wird nicht gelesen."""
        lage = Streuung(punkte=_punkte([0.1, 0.2] * 30), versuche=203)

        assert "nicht mehr zu holen" not in lage.urteil()

    def test_und_bei_erreichbarer_schwelle_auch(self) -> None:
        lage = Streuung(punkte=_punkte([0.1, 0.2] * 100), versuche=203, grenze=230)

        assert lage.erreichbar
        assert "nicht mehr zu holen" not in lage.urteil()


class TestDieRichtungImEmpfindlichkeitssatz:
    """Die Richtung wurde eine Zeile ueber dem Satz gerechnet und im Satz
    selbst festgeschrieben: 'darueber', immer."""

    @staticmethod
    def _messung(sharpe: float) -> Empfindlichkeit:
        return Empfindlichkeit(
            sharpe=sharpe, stichprobe=122, versuche=203, schiefe=3.43, woelbung=15.88
        )

    def test_eine_annahme_oberhalb_liegt_darueber(self) -> None:
        messung = self._messung(0.2649)
        kipp = messung.kippunkt()

        assert kipp is not None
        assert "darueber" in messung.urteil(kipp * 1.4)

    def test_eine_annahme_unterhalb_liegt_darunter(self) -> None:
        """**Der Fall, den der feste Text falsch beschriftet hat.**"""
        messung = self._messung(0.2649)
        kipp = messung.kippunkt()

        assert kipp is not None
        urteil = messung.urteil(kipp * 0.6)

        assert "darunter" in urteil
        assert "darueber" not in urteil

    def test_und_die_zweite_haelfte_zeigt_dieselbe_richtung(self) -> None:
        """Beide Saetze standen auf derselben Rechnung und sollen sich nicht
        widersprechen."""
        messung = self._messung(0.2649)
        kipp = messung.kippunkt()

        assert kipp is not None
        oben, unten = messung.urteil(kipp * 1.4), messung.urteil(kipp * 0.6)

        assert "Jede Schaetzung unter" in oben and "darueber" in oben
        assert "Jede Schaetzung ueber" in unten and "darunter" in unten


class TestDerBefehlFuelltEsAn:
    @staticmethod
    def _quelle() -> str:
        import ast
        from pathlib import Path

        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        return next(
            ast.unparse(n)
            for n in ast.walk(baum)
            if isinstance(n, ast.FunctionDef) and n.name == "streuung"
        )

    def test_die_grenze_kommt_aus_dem_budget(self) -> None:
        quelle = self._quelle()

        assert "grenze=BUDGET.grenze" in quelle

    def test_und_nicht_als_zahl_danebengeschrieben(self) -> None:
        """Das Budget ist eine Abmachung an einer Stelle - eine 230 hier waere
        eine zweite, die auseinanderlaufen kann."""
        quelle = self._quelle()

        assert "grenze=230" not in quelle


class TestDerEintragIstNachgemessen:
    @staticmethod
    def _eintrag():
        from research.stand import ENTSCHEIDUNGEN

        return next(
            e for e in ENTSCHEIDUNGEN
            if e.frage == "Die geratene Eingabe im Deflated Sharpe"
        )

    def test_die_gedrehte_richtung_ist_benannt(self) -> None:
        """Der wichtigste Satz des Eintrags: Messen wuerde das Gate **nicht**
        bestehen lassen."""
        zahl = self._eintrag().zahl

        assert "die Richtung hat sich gedreht" in zahl
        assert "0,2761" in zahl and "0,5958" in zahl
        assert "breiter" in zahl

    def test_die_heutigen_zahlen_stehen_da(self) -> None:
        zahl = self._eintrag().zahl

        assert "0,0909" in zahl
        assert "0,1072" in zahl
        assert "0,0636" in zahl
        assert "61" in zahl and "203" in zahl

    def test_das_nicht_nachmessbare_ist_als_solches_benannt(self) -> None:
        """Die Bestenliste liegt nicht im Klon - "weder bestaetigt noch
        widerlegt" ist die ehrliche Auskunft, nicht "falsch"."""
        zahl = self._eintrag().zahl

        assert "weder bestaetigt noch widerlegt" in zahl

    def test_was_stimmt_steht_auch_da(self) -> None:
        zahl = self._eintrag().zahl

        assert "Was stimmt" in zahl
        assert "38 %" in zahl

    def test_die_abwaegung_ist_kleiner_geworden(self) -> None:
        warum = self._eintrag().warum

        assert "Streuung.deckel" in warum
        assert "nicht senken, sondern" in warum

    def test_die_fundstelle_ist_nachgezogen(self) -> None:
        eintrag = self._eintrag()

        assert eintrag.befund == 69
        assert eintrag.massgeblich == 340


class TestDieWacheHatZurueckgemeldet:
    """Der Abschnitt zu 340 nennt Reglerscans, und der offene Punkt 'Zaehlt
    ein Sweep am Bestand als Versuch?' war bis 330 durchgesehen. Gelesen,
    abgegrenzt, eingetragen - sonst stuende er beim naechsten Lauf wieder als
    neu da."""

    def test_der_eintrag_ist_nachgezogen(self) -> None:
        """Nicht auf 340 festgenagelt, sondern "mindestens": Jeder spaetere
        Befund, der Reglerscans erwaehnt, zieht den Stand weiter - und ein Test,
        der die Zahl festhaelt, faellt dann fuer nichts."""
        from research.nachmessung import GELESEN

        assert GELESEN["Zaehlt ein Sweep am Bestand als Versuch?"] >= 340

    def test_beide_lesarten_verfehlen_die_schwelle(self) -> None:
        """Die Abgrenzung ist gerechnet und nicht behauptet: 61 von 203 gegen
        11 von 203, und beide Deckel unter 90 %."""
        mit = Streuung(punkte=_punkte([0.1] * 61), versuche=203, grenze=230)
        ohne = Streuung(punkte=_punkte([0.1] * 11), versuche=203, grenze=230)

        assert mit.deckel == pytest.approx(0.38, abs=0.005)
        assert ohne.deckel == pytest.approx(0.17, abs=0.005)
        assert not mit.erreichbar and not ohne.erreichbar

    def test_kein_versuch_mit_herkunft_kommt_aus_einem_reglerscan(self) -> None:
        """Die Aussage des Eintrags, an der Quelle geprueft."""
        from pathlib import Path

        from core.config import get_settings
        from research.versuche import laden

        verzeichnis = laden(Path(get_settings().paths.state) / "trials.json")
        herkunft = {v.herkunft for v in verzeichnis.eintraege}

        assert herkunft == {"verbund", "gen11 partnersuche", "gen12 kalibriert"}
        assert not any("reglerscan" in h.lower() for h in herkunft)


@pytest.mark.daten
@pytest.mark.langsam
def test_die_zahlen_des_befehls_stimmen() -> None:
    """**Die Bindung.** Der Eintrag trug 271 Befunde lang eine Zahl, die das
    Gegenteil dessen sagte, was heute gemessen wird. Ein Test haette das
    gefunden.
    """
    from pathlib import Path

    import cli
    from backtest.portfolio_walkforward import run_portfolio_walkforward
    from core.config import get_settings
    from core.models import Interval
    from research.admission import load_trials
    from research.gates import stichprobe_wie_im_gate
    from research.seeds import spitzenkandidat
    from research.stand import BUDGET
    from research.streuung import sammle
    from research.suchbudget import Kandidat
    from strategy.compiler import compile_genome

    e = get_settings()
    zustand = Path(e.paths.state)
    versuche = load_trials(zustand / "trials.json")
    symbole = ["BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP"]
    frames, configs, _ = cli._korb_daten(symbole, Interval("D"), e)
    genom = spitzenkandidat()
    bericht = run_portfolio_walkforward(
        frames, lambda g=genom: compile_genome(g), configs
    )
    trades = list(bericht.all_trades)
    kandidat = Kandidat.aus_trades(genom.name, trades)

    assert kandidat is not None

    bloecke = [[float(t.net_pnl) for t in f.trades] for f in bericht.windows]
    stichprobe = stichprobe_wie_im_gate(
        trades, beine=getattr(bericht, "beine", None), bloecke=bloecke
    )
    lage = Streuung(
        punkte=sammle(
            berichte=Path.cwd() / "reports",
            bestenliste=zustand / "leaderboard.json",
            verzeichnis=zustand / "trials.json",
        ),
        versuche=versuche,
        stichprobe=stichprobe.effektiv,
        grenze=BUDGET.grenze,
    )
    messung = Empfindlichkeit(
        sharpe=kandidat.sharpe_je_trade,
        stichprobe=stichprobe.effektiv,
        versuche=versuche,
        schiefe=kandidat.schiefe or 0.0,
        woelbung=kandidat.woelbung or 3.0,
    )

    # Die Annahme ist enger als die Messung - genau umgekehrt zum Eintrag von
    # Befund 69, und das ist der Fund.
    assert lage.angenommen == pytest.approx(ANNAHME, abs=0.0002)
    assert lage.gemessen == pytest.approx(GEMESSEN, abs=0.0002)
    assert lage.gemessen > lage.angenommen

    assert messung.bei(lage.angenommen) == pytest.approx(DSR_ANNAHME, abs=0.002)
    assert messung.bei(lage.gemessen) == pytest.approx(DSR_GEMESSEN, abs=0.002)
    assert messung.bei(lage.gemessen) < messung.bei(lage.angenommen), (
        "die gemessene Streuung senkt den Deflated Sharpe - sie ist kein Weg "
        "durch das Gate, sondern tiefer hinein"
    )
    assert messung.kippunkt() == pytest.approx(KIPPUNKT, abs=0.0005)

    # Und der Deckel, gerechnet statt geschaetzt.
    assert not lage.verwendbar
    assert not lage.erreichbar
    assert lage.deckel == pytest.approx(0.38, abs=0.01)
    assert lage.abdeckung == pytest.approx(0.30, abs=0.01)
