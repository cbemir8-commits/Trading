"""Der Vorrat auf Viertelstunden, 13 von 39 Stuecken - Befund 449.

Der Nutzer sucht als naechstes auf Viertelstunden (Generation 6/7). Die
Messung, die sagt, **ob ein Vorrat je reichen kann**, ist 'cli vorratsdecke':
Faellt die Qualitaet je Trade mit der Menge, hat ``SR * sqrt(n)`` ein
Maximum - und liegt das unter der Latte, kann in diesem Vorrat nichts
bestehen.

Auf Tageskerzen ist sie **vollstaendig** gefahren (6 von 6 Stuecken) und
sagt:

    Beide Haelften gibt es - nur nie zusammen. Am wenigsten verlangt
    'Momentum Ruecksetzer' bei n_eff 254: 0,2641 je Trade, und sie selbst
    bringt -0,1358. Fuenf von 18 Regeln haben diese Qualitaet gezeigt - aber
    keine davon bei mehr als n_eff 58.

Auf Viertelstunden stand sie bei **einem** von 39 Stuecken. Dieser Befund
hat zwoelf weitere gefahren; ein Stueck kostet 5 Minuten 23, alle 39 also
rund dreieinhalb Stunden.

**Es ist eine Teilmessung, und sie bleibt eine**, bis die 39 durch sind. Was
sie schon hergibt, steht hier - und die Protokolle liegen im Repo, damit
dieser Test sie ohne Kerzenspeicher lesen kann.
"""

from __future__ import annotations

import glob

import pytest

#: Die Protokolle dieses Befundes - committet, damit sie pruefbar sind.
MUSTER = "reports/vorratsdecke/2026-11-01_*.jsonl"

#: Gemessen: Stuecke, Regeln mit Latte, Regeln ohne einen einzigen Trade.
STUECKE, MIT_LATTE, STUMM = 13, 12, 1

#: Die beste Regel und die zweite mit **positiver** Qualitaet je Trade.
#:
#: Es sind **zwei**, nicht eine: Ich hatte die Tabellenzeile 'Seltener
#: grosser Ausbruch' mit 0,0047 als Null gelesen, und dieser Test hat es
#: gefunden (Befund 449). Die Aussage bleibt - 0,0047 ist ein Zehntel der
#: besten und ein Zehntel der mildesten Anforderung.
BESTE, BESTE_SR, BESTE_GUETE, BESTE_LATTE = (
    "Trendbeteiligung mit Puffer",
    0.0336,
    0.815,
    3.889,
)
ZWEITE, ZWEITE_SR = "Seltener grosser Ausbruch", 0.0047

#: Die mildeste Anforderung des Vorrats - und wer sie stellt.
MILDESTE, MILDESTE_SR, MILDESTE_N = "Momentum Ruecksetzer", 0.0488, 8041


@pytest.fixture(scope="module")
def gelesen():
    import cli
    from core.models import Interval

    pfade = sorted(glob.glob(MUSTER))
    if len(pfade) != STUECKE:
        pytest.fail(f"{len(pfade)} Protokolle statt {STUECKE}: {pfade}")
    return cli._vorrat_aus_protokollen(
        ",".join(pfade), interval_obj=Interval.M15, versuche=203
    )


class TestDieTeilmessungStehtDa:
    def test_dreizehn_protokolle_zwoelf_regeln(self, gelesen) -> None:
        assert len(gelesen.punkte) == MIT_LATTE
        assert gelesen.stumm == STUMM

    def test_auf_dem_heutigen_versuchsstand(self, gelesen) -> None:
        """Eine Latte ohne ihren Stand ist eine Zahl ohne ihre Bedingung
        (Befund 281/448)."""
        assert gelesen.versuchsstand == 203

    def test_die_protokolle_liegen_im_repo(self) -> None:
        """Sonst waere dieser Test eine Abschrift (Befund 442)."""
        assert len(sorted(glob.glob(MUSTER))) == STUECKE


class TestGenauEineRegelHatPositiveQualitaet:
    """**Der Befund, der keine Gerade braucht.** Eine Decke laesst sich aus
    zwoelf Punkten nicht ablesen - diese Zahl schon."""

    def test_zwei_von_zwoelf(self, gelesen) -> None:
        positiv = sorted(
            (p for p in gelesen.punkte if p.sharpe_je_trade > 0),
            key=lambda p: -p.sharpe_je_trade,
        )

        assert [p.name for p in positiv] == [BESTE, ZWEITE]

    def test_die_zweite_ist_ein_zehntel_der_ersten(self, gelesen) -> None:
        """Und damit auch ein Zehntel der mildesten Anforderung."""
        zweite = next(p for p in gelesen.punkte if p.name == ZWEITE)

        assert zweite.sharpe_je_trade == pytest.approx(ZWEITE_SR, abs=0.0002)
        assert zweite.sharpe_je_trade < BESTE_SR / 5
        assert zweite.sharpe_je_trade < MILDESTE_SR / 5

    def test_und_sie_bringt_0_0336_je_trade(self, gelesen) -> None:
        beste = next(p for p in gelesen.punkte if p.name == BESTE)

        assert beste.sharpe_je_trade == pytest.approx(BESTE_SR, abs=0.0002)

    def test_ihre_guete_steht_gegen_das_knapp_fuenffache(self, gelesen) -> None:
        """0,815 gegen eine Latte von 3,889."""
        beste = next(p for p in gelesen.punkte if p.name == BESTE)
        guete = beste.sharpe_je_trade * beste.n_eff**0.5

        assert guete == pytest.approx(BESTE_GUETE, abs=0.005)
        assert BESTE_LATTE / guete > 4.5

    def test_die_uebrigen_zehn_sind_negativ(self, gelesen) -> None:
        andere = [p for p in gelesen.punkte if p.name not in {BESTE, ZWEITE}]

        assert len(andere) == 10
        for p in andere:
            assert p.sharpe_je_trade < 0, p.name


class TestDieBesteQualitaetBleibtUnterDerMildestenAnforderung:
    """Auf Tageskerzen fehlt die **Verbindung** aus Qualitaet und Menge -
    beide Haelften gibt es. Auf Viertelstunden fehlt die Qualitaet selbst."""

    def test_die_mildeste_anforderung_steht_bei_0_0488(self, gelesen) -> None:
        from research.erreichbarkeit import noetiger_sharpe

        noetig = {}
        for p in gelesen.punkte:
            wert = noetiger_sharpe(
                effektiv=p.n_eff,
                trials=gelesen.versuchsstand,
                skew=p.schiefe,
                kurtosis=p.woelbung,
            )
            if wert is not None:
                noetig[p.name] = wert

        mildeste = min(noetig, key=lambda k: noetig[k])

        assert mildeste == MILDESTE
        assert noetig[mildeste] == pytest.approx(MILDESTE_SR, abs=0.0005)

    def test_und_die_beste_qualitaet_liegt_darunter(self, gelesen) -> None:
        """**Was fehlt, fehlt nicht an der Kombination, sondern an der
        Qualitaet selbst.** Die beste je gemessene Qualitaet dieses Vorrats
        ist 31 % unter seiner mildesten Anforderung."""
        beste = max(p.sharpe_je_trade for p in gelesen.punkte)

        assert beste == pytest.approx(BESTE_SR, abs=0.0002)
        assert beste < MILDESTE_SR
        assert 1 - beste / MILDESTE_SR == pytest.approx(0.31, abs=0.02)

    def test_die_mildeste_steht_bei_der_groessten_stichprobe(self, gelesen) -> None:
        """Die Latte je Trade faellt mit der Wurzel aus n - die mildeste
        Anforderung gehoert deshalb der Regel mit den meisten wirksamen
        Beobachtungen, und das ist keine Eigenschaft ihrer Qualitaet."""
        milde = next(p for p in gelesen.punkte if p.name == MILDESTE)

        assert milde.n_eff == MILDESTE_N
        assert milde.n_eff == max(p.n_eff for p in gelesen.punkte)
        assert milde.sharpe_je_trade < 0


class TestKeineDeckeAblesbar:
    """**Die Methode weigert sich, und das ist richtig.** Zwoelf Punkte mit
    |t| = 1,42 tragen keine Gerade, und ohne eine einzige Regel bleibt
    t = 0,00 stehen - eine Decke, die ein Punkt loeschen kann, ist keine."""

    def test_das_urteil_sagt_es_in_worten(self, gelesen) -> None:
        """Gefahren wird der echte Befehl, nicht ein Nachbau."""
        from typer.testing import CliRunner

        from cli import app

        pfade = ",".join(sorted(glob.glob(MUSTER)))
        ergebnis = CliRunner().invoke(
            app, ["vorratsdecke", "-i", "15", "--aus", pfade]
        )
        text = " ".join(ergebnis.output.split())

        assert ergebnis.exit_code == 0, ergebnis.output[-1500:]
        assert "Keine Decke ablesbar" in text
        assert "haengt an einer einzigen Regel" in text
        assert "Eine Decke, die ein Punkt loeschen kann, ist keine" in text


class TestDieFremdenMomenteKostenEtwas:
    """**Befund 448 von der anderen Seite.** Dort stand, die Latten der
    Erfuellungstafel seien mit den Momenten des Bestands gerechnet. Hier
    misst der Befehl, was das ausmacht."""

    def test_der_befehl_beziffert_es(self, gelesen) -> None:
        from typer.testing import CliRunner

        from cli import app

        pfade = ",".join(sorted(glob.glob(MUSTER)))
        text = " ".join(
            CliRunner()
            .invoke(app, ["vorratsdecke", "-i", "15", "--aus", pfade])
            .output.split()
        )

        assert "Mit den Momenten des Bestands gerechnet stuenden 9 von 12" in text
        assert "+0.508" in text

    def test_und_die_latte_gehoert_der_regel(self, gelesen) -> None:
        """Jede Regel hat ihre eigene Schiefe und Woelbung - deshalb ist die
        Latte je Regel verschieden (Befund 191)."""
        formen = {(p.schiefe, p.woelbung) for p in gelesen.punkte}

        assert len(formen) == MIT_LATTE
