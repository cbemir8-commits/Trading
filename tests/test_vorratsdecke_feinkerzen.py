"""Der Vorrat auf Viertelstunden, vollstaendig - Befund 449/450.

Der Nutzer sucht als naechstes auf Viertelstunden (Generation 6/7). Die
Messung, die sagt, **ob ein Vorrat je reichen kann**, ist 'cli vorratsdecke':
Faellt die Qualitaet je Trade mit der Menge, hat ``SR * sqrt(n)`` ein
Maximum - und liegt das unter der Latte, kann darin nichts bestehen.

Auf Tageskerzen war sie vollstaendig, auf Viertelstunden stand sie bei
**einem von 39** Stuecken. Befund 449 hat zwoelf weitere gefahren, Befund 450
die restlichen - alle 39 auf **einem** Code-Stand, und das ist der Haken:

    Zwei Stuecke unter verschiedenen Bedingungen sind zwei Messungen, keine.

Die ersten dreizehn Stuecke sind mit Befund 449 committet worden, und der
Commit hat den Code-Abdruck geaendert. Sie liessen sich danach nicht mehr mit
den neuen zusammenlegen; der Befehl hat das gemeldet, und die dreizehn sind
neu gefahren. **Eine stueckweise Messung gehoert auf einen Stand, ohne
Commit dazwischen.**

Dieser Test liest die 39 Protokolle des vollstaendigen Laufs. Sie liegen im
Repo, damit das ohne Kerzenspeicher geht (die Lehre aus Befund 442).
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

#: Die Protokolle des **vollstaendigen** Laufs - ein Code-Abdruck, 39 Stuecke.
MUSTER = "reports/vorratsdecke/2026-11-01_1[678]*.jsonl"

#: Die dreizehn aus Befund 449, die der Commit abgeschnitten hat.
ALTE = "reports/vorratsdecke/2026-11-01_1[45]*.jsonl"

STUECKE, MIT_LATTE, STUMM = 39, 36, 3

#: Die beiden einzigen Regeln mit **positiver** Qualitaet je Trade.
POSITIV: tuple[tuple[str, float], ...] = (
    ("Trendbeteiligung mit Puffer", 0.0336),
    ("Seltener grosser Ausbruch", 0.0047),
)

#: Die naechstliegende Regel: Guete, Latte, Luecke.
NAECHSTE, NAECHSTE_GUETE, NAECHSTE_LATTE, NAECHSTE_LUECKE = (
    "Trendbeteiligung mit Puffer",
    0.815,
    3.889,
    3.074,
)

#: Streuung des Vorrats und Median aller 36 Luecken, in Guetepunkten.
STREUUNG, MEDIANLUECKE = 4.777, 11.437

#: Wie viele Regeln auf den Momenten des Bestands zu milde dastuenden - und
#: um wie viel die schlimmste (Befund 448, hier ueber den ganzen Katalog).
ZU_MILDE, SCHLIMMSTE = 33, 0.547


def _pfade(muster: str = MUSTER) -> list[str]:
    return sorted(glob.glob(muster))


@pytest.fixture(scope="module")
def gelesen():
    import cli
    from core.models import Interval

    pfade = _pfade()
    if len(pfade) != STUECKE:
        pytest.fail(f"{len(pfade)} Protokolle statt {STUECKE}")
    return cli._vorrat_aus_protokollen(
        ",".join(pfade), interval_obj=Interval.M15, versuche=203
    )


@pytest.fixture(scope="module")
def urteil() -> str:
    from typer.testing import CliRunner

    from cli import app

    ergebnis = CliRunner().invoke(
        app, ["vorratsdecke", "-i", "15", "--aus", ",".join(_pfade())]
    )
    assert ergebnis.exit_code == 0, ergebnis.output[-1500:]
    return " ".join(ergebnis.output.split())


class TestDieMessungIstVollstaendigUndAufEinemStand:
    def test_neununddreissig_stuecke(self, gelesen) -> None:
        assert len(_pfade()) == STUECKE
        assert len(gelesen.punkte) == MIT_LATTE
        assert gelesen.stumm == STUMM

    def test_alle_tragen_denselben_code_abdruck(self) -> None:
        """Sonst waeren es zwei Messungen und keine."""
        abdruecke = {
            json.loads(Path(p).read_text().splitlines()[0]).get("code")
            for p in _pfade()
        }

        assert len(abdruecke) == 1, abdruecke

    def test_die_dreizehn_aus_449_tragen_einen_anderen(self) -> None:
        """**Der Fehler, den der Befehl gefunden hat** (Befund 450): Der
        Commit von 449 hat den Abdruck geaendert, und damit waren die
        dreizehn nicht mehr anschlussfaehig. Sie bleiben als Aufzeichnung
        liegen - zusammenlegen laesst sie sich nicht."""
        alt = {
            json.loads(Path(p).read_text().splitlines()[0]).get("code")
            for p in _pfade(ALTE)
        }
        neu = {
            json.loads(Path(p).read_text().splitlines()[0]).get("code")
            for p in _pfade()
        }

        assert len(_pfade(ALTE)) == 13
        assert alt.isdisjoint(neu)

    def test_auf_dem_heutigen_versuchsstand(self, gelesen) -> None:
        assert gelesen.versuchsstand == 203


class TestZweiVonSechsunddreissig:
    def test_nur_zwei_regeln_sind_positiv(self, gelesen) -> None:
        positiv = sorted(
            (p for p in gelesen.punkte if p.sharpe_je_trade > 0),
            key=lambda p: -p.sharpe_je_trade,
        )

        assert [p.name for p in positiv] == [n for n, _ in POSITIV]

    def test_und_zwar_mit_diesen_werten(self, gelesen) -> None:
        for name, sr in POSITIV:
            punkt = next(p for p in gelesen.punkte if p.name == name)

            assert punkt.sharpe_je_trade == pytest.approx(sr, abs=0.0002), name

    def test_die_uebrigen_vierunddreissig_sind_negativ(self, gelesen) -> None:
        namen = {n for n, _ in POSITIV}
        andere = [p for p in gelesen.punkte if p.name not in namen]

        assert len(andere) == MIT_LATTE - len(POSITIV)
        for p in andere:
            assert p.sharpe_je_trade < 0, p.name


class TestKeineRegelHaetteJeGeraeumt:
    """**Der tragende Satz.** Nicht "bei diesem Versuchsstand nicht", sondern
    bei **keinem** - auch nicht beim ersten Versuch. Damit ist der
    Versuchszaehler hier nicht die Ursache, und Suchdisziplin nicht das
    Thema."""

    def test_das_urteil_sagt_es(self, urteil) -> None:
        assert (
            "Keine einzige Regel dieses Vorrats haette die Schwelle bei "
            "irgendeinem Versuchsstand geraeumt" in urteil
        )
        assert "Auch beim ersten Versuch nicht" in urteil

    def test_die_spalte_bis_ist_leer(self, urteil) -> None:
        """'bis' nennt den hoechsten Versuchsstand, bei dem eine Regel noch
        geraeumt haette - fuer alle 36 steht dort ein Strich."""
        assert "'bis' = hoechster Versuchsstand" in urteil

    def test_die_naechstliegende_fehlt_um_mehr_als_das_dreifache(
        self, gelesen
    ) -> None:
        punkt = next(p for p in gelesen.punkte if p.name == NAECHSTE)
        guete = punkt.sharpe_je_trade * punkt.n_eff**0.5

        assert guete == pytest.approx(NAECHSTE_GUETE, abs=0.005)
        assert NAECHSTE_LATTE - guete == pytest.approx(NAECHSTE_LUECKE, abs=0.01)
        assert NAECHSTE_LATTE / guete > 4.5

    def test_und_das_ist_der_beste_von_sechsunddreissig(self, urteil) -> None:
        """0,64 Streuungen dieses Vorrats - der Median aller Luecken liegt
        bei 11,4 Guetepunkten, also dem Vierfachen."""
        assert f"es fehlen {NAECHSTE_LUECKE:.3f}" in urteil
        assert f"{MEDIANLUECKE:.3f}" in urteil
        assert MEDIANLUECKE / NAECHSTE_LUECKE > 3.5


class TestDieMethodeWeigertSichZuRecht:
    """Eine Decke laesst sich aus diesen 36 Punkten nicht lesen - und das
    Modul nimmt die guenstige Auslassung **nicht**, obwohl sie dastuende."""

    def test_keine_decke_ablesbar(self, urteil) -> None:
        assert "Keine Decke ablesbar" in urteil
        assert "|t| = 1.89 liegt unter 2" in urteil

    def test_die_gerade_haengt_an_einer_regel(self, urteil) -> None:
        assert "haengt an einer einzigen Regel" in urteil
        assert "Ohne 'Trendbeteiligung mit Puffer' steht t = -1.42" in urteil

    def test_und_die_guenstige_auslassung_wird_nicht_genommen(
        self, urteil
    ) -> None:
        """**Der Punkt, an dem sich Disziplin zeigt.** Ohne 'Mean Reversion
        Uebertreibung' waere die Gerade mit -2.41 signifikant - das Modul
        sagt es und benutzt es nicht."""
        assert "Ohne 'Mean Reversion Uebertreibung' waere sie mit -2.41" in urteil
        assert "Eine Decke, die ein Punkt loeschen kann, ist keine" in urteil

    def test_auch_kein_schnitt_hat_es_bestaetigt(self, urteil) -> None:
        """Und eine zu kleine Aussenmenge zaehlt **nicht** als
        Bestaetigung - sonst wuerde der Befund umso sicherer, je feiner man
        schneidet."""
        assert "Keiner der 3 Schnitte hat es geprueft" in urteil
        assert "zaehlt hier **nicht** als Bestaetigung" in urteil
        assert "je feiner man schneidet" in urteil


class TestDieFremdenMomenteUeberDenGanzenKatalog:
    """**Befund 448 ueber 36 Regeln statt ueber drei.** Dort stand, die
    Latten der Erfuellungstafel seien mit den Momenten des Bestands
    gerechnet; hier misst der Befehl, wie weit das traegt."""

    def test_dreiunddreissig_von_sechsunddreissig_stuenden_zu_milde(
        self, urteil
    ) -> None:
        assert f"stuenden {ZU_MILDE} von {MIT_LATTE} Regeln zu milde da" in urteil

    def test_die_schlimmste_um_ein_halbes_guetepunkt(self, urteil) -> None:
        assert f"+{SCHLIMMSTE:.3f}" in urteil

    def test_jede_regel_hat_ihre_eigene_form(self, gelesen) -> None:
        formen = {(p.schiefe, p.woelbung) for p in gelesen.punkte}

        assert len(formen) == MIT_LATTE


class TestDieKostenfrageIstHierOffen:
    """**Neu und nicht entschieden.** Auf Tageskerzen war die Kopplung keine
    Reibungsfrage (Kippfaktor 29). Hier verschwindet sie bei doppelter
    Gebuehr - rund 0,1 % je Roundtrip, und das liegt in der Reichweite der
    Slippage allein, die im Ausfuehrungspreis steckt und sich aus den Trades
    nicht abziehen laesst."""

    def test_der_befehl_sagt_dass_es_die_kosten_sein_koennten(
        self, urteil
    ) -> None:
        assert "Hier koennten es die Kosten sein" in urteil
        assert "Bei **2-facher Gebuehr** verschwindet sie" in urteil

    def test_und_dass_es_nicht_entschieden_ist(self, urteil) -> None:
        assert "nicht entschieden" in urteil
        assert "das Urteil von dort gilt hier nicht" in urteil

    def test_die_beiden_korrelationen_sind_nicht_dasselbe_mass(
        self, urteil
    ) -> None:
        """Die Kostenkorrelation laeuft ueber die **rohe** Trade-Zahl, die
        Decke ueber n_eff - sie gegeneinander zu lesen waere Befund 139."""
        assert "nicht dasselbe Mass" in urteil
        assert "Befund 139" in urteil
