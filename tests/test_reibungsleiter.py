"""Der Kippfaktor, gemessen statt gerechnet.

**Befund 256.** ``Kostenfrage.kippfaktor`` sucht, ab welchem Faktor
``sharpe + f * anteil`` die Null erreicht - und haelt dabei die **Trades
fest**: dieselben Ein- und Ausstiege, nur andere Zahlen darunter.

Bei Faktor 1 ist das eine gute Naeherung. Auf Tageskerzen sagt das
Zurueckrechnen -0,374, gemessen sind es -0,370 (Befund 254). Bei Faktor 56
ist es keine mehr: Eine Gebuehr von 2,2 % je Roundtrip aenderte nicht die
Zahlen unter denselben Trades, sondern die Trades - Stops lieber,
Risikogrenzen frueher, viele Einstiege gar nicht.

``Reibungsleiter`` misst denselben Punkt durch Wiederholung: jede Sprosse ein
ganzer Lauf bei ``CostModel.scaled(k)``.

Was hier gehalten wird
----------------------
Dass das gemessene Paar ein **Paar** bleibt und keine interpolierte Zahl wird,
dass alle Sprossen dieselbe Regelmenge tragen muessen, und dass das Urteil es
sagt, wenn der gerechnete Punkt ausserhalb des gemessenen liegt - statt eine
der beiden Zahlen stillschweigend zu bevorzugen.
"""

from __future__ import annotations

import ast
from pathlib import Path

from research.kostenanteil import (
    Kostenfrage,
    Reibungsleiter,
    Reibungsprobe,
    Reibungssprosse,
    Taktpunkt,
)

TRADES = (10, 50, 100, 200)
NAMEN = ("a", "b", "c", "d")


def _frage(*sharpes: float, anteil: float = 0.0, namen=NAMEN) -> Kostenfrage:
    return Kostenfrage(
        punkte=[
            Taktpunkt(
                name=n, trades=t, sharpe_je_trade=s,
                haltedauer_tage=1.0, kostenanteil=anteil,
            )
            for n, t, s in zip(namen, TRADES, sharpes, strict=True)
        ]
    )


def _leiter(*paare: tuple[float, tuple[float, ...]]) -> Reibungsleiter:
    return Reibungsleiter(
        sprossen=tuple(
            Reibungssprosse(faktor=f, frage=_frage(*werte)) for f, werte in paare
        )
    )


#: Eine Leiter, deren Kopplung zwischen Faktor 5 und 10 die Null erreicht.
KIPPT_ZWISCHEN_5_UND_10 = (
    (0.0, (0.30, 0.12, 0.02, -0.05)),
    (1.0, (0.30, 0.10, 0.00, -0.10)),
    (5.0, (0.20, 0.12, 0.08, -0.02)),
    (10.0, (0.05, 0.10, 0.12, 0.20)),
)


class TestAufgeschlageneReibungIstNichtHerausgerechnete:
    """``Kostenfrage.kippfaktor`` rechnet Reibung **heraus**, die Leiter
    schlaegt sie **auf**. Beides ist interessant, beides ist etwas anderes -
    und die Leiter darf nicht so tun, als messe sie den Kippfaktor nach."""

    def test_er_nennt_die_beiden_faktoren(self) -> None:
        leiter = _leiter(*KIPPT_ZWISCHEN_5_UND_10)

        assert leiter.kippt_unter_aufschlag == (5.0, 10.0)

    def test_zwischen_ihnen_wird_nicht_interpoliert(self) -> None:
        """Was dazwischen liegt, wurde nicht gerechnet - also steht dort auch
        keine Zahl."""
        text = _leiter(*KIPPT_ZWISCHEN_5_UND_10).urteil()

        assert "zwischen Faktor 5 und 10" in text
        assert "7.5" not in text

    def test_kippt_sie_nie_sagt_das_urteil_bis_wohin_gemessen_wurde(self) -> None:
        leiter = _leiter(
            (0.0, (0.30, 0.12, 0.02, -0.05)),
            (1.0, (0.30, 0.10, 0.00, -0.10)),
            (56.0, (0.30, 0.10, 0.00, -0.12)),
        )

        assert leiter.kippt_unter_aufschlag is None
        assert "bis Faktor 56 nicht zur Null" in leiter.urteil()

    def test_die_sprossen_duerfen_ungeordnet_hereinkommen(self) -> None:
        verdreht = _leiter(*reversed(KIPPT_ZWISCHEN_5_UND_10))

        assert verdreht.kippt_unter_aufschlag == (5.0, 10.0)
        assert [s.faktor for s in verdreht.geordnet] == [0.0, 1.0, 5.0, 10.0]


class TestAlleSprossenTragenDieselbenRegeln:
    """Mit mehr Reibung faellt eine Regel irgendwann unter die Schwelle fuer
    einen Taktpunkt - dann verglichen sich verschiedene Populationen."""

    def test_gleiche_namen_sind_vergleichbar(self) -> None:
        assert _leiter(*KIPPT_ZWISCHEN_5_UND_10).gleiche_regeln

    def test_eine_verschwundene_regel_faellt_auf(self) -> None:
        leiter = Reibungsleiter(
            sprossen=(
                Reibungssprosse(faktor=1.0, frage=_frage(0.3, 0.1, 0.0, -0.1)),
                Reibungssprosse(
                    faktor=25.0,
                    frage=_frage(
                        0.3, 0.1, 0.0, -0.1, namen=("a", "b", "c", "z")
                    ),
                ),
            )
        )

        assert not leiter.gleiche_regeln
        assert not leiter.belastbar
        assert "Nicht vergleichbar" in leiter.urteil()
        assert "zwei Populationen" in leiter.urteil()

    def test_eine_leere_sprosse_stoert_den_vergleich_nicht(self) -> None:
        """Sie traegt keine Regelmenge - sie wird beim Vergleich ausgelassen
        und faellt ueber ``genug`` heraus."""
        leiter = Reibungsleiter(
            sprossen=(
                Reibungssprosse(faktor=1.0, frage=_frage(0.3, 0.1, 0.0, -0.1)),
                Reibungssprosse(faktor=99.0, frage=Kostenfrage()),
            )
        )

        assert leiter.gleiche_regeln
        assert not leiter.belastbar
        assert "Zu wenig gemessen" in leiter.urteil()

    def test_eine_einzige_sprosse_traegt_nichts(self) -> None:
        leiter = Reibungsleiter(
            sprossen=(Reibungssprosse(faktor=1.0, frage=_frage(0.3, 0.1, 0.0, -0.1)),)
        )

        assert not leiter.belastbar


class TestDieReibungsloseWeltIstEineEinzige:
    """**Der Kern von Befund 256.** ``brutto(f)`` ist die Kopplung, *wenn* die
    wahre Reibung das f-fache waere und man sie herausrechnete - gemeint ist
    dabei immer dieselbe reibungslose Welt. Die bewegt sich nicht, wenn man
    die Annahme aendert; ``brutto(f)`` schon.

    Gemessen auf Tageskerzen: Die reibungslose Welt steht bei -0,370.
    ``brutto(1)`` sagt -0,374, ``brutto(56)`` sagt 0,000. Der Kippfaktor ist
    damit die Reichweite der Rechnung und nicht die der Reibung.
    """

    @staticmethod
    def _mit_steigendem_anteil() -> Reibungsleiter:
        """Der Kostenanteil steigt mit der Trade-Zahl - der Mechanismus aus
        Befund 78. Ohne das gaebe es ueberhaupt keinen Kippfaktor."""
        betriebspunkt = Kostenfrage(
            punkte=[
                Taktpunkt(
                    name=n, trades=t, sharpe_je_trade=s,
                    haltedauer_tage=1.0, kostenanteil=a,
                )
                for n, t, s, a in zip(
                    NAMEN, TRADES, (0.30, 0.10, 0.00, -0.10),
                    (0.01, 0.05, 0.10, 0.20), strict=True,
                )
            ]
        )
        return Reibungsleiter(
            sprossen=(
                Reibungssprosse(faktor=0.0, frage=_frage(0.30, 0.12, 0.02, -0.05)),
                Reibungssprosse(faktor=1.0, frage=betriebspunkt),
                Reibungssprosse(faktor=5.0, frage=_frage(0.28, 0.08, -0.02, -0.15)),
            )
        )

    def test_die_reibungslose_welt_ist_die_nullsprosse(self) -> None:
        leiter = self._mit_steigendem_anteil()
        null = leiter.bei(0.0)

        assert null is not None
        assert leiter.reibungslos == null.r

    def test_der_fehler_der_naeherung_waechst_mit_dem_faktor(self) -> None:
        fehler = self._mit_steigendem_anteil().naeherungsfehler()
        abstaende = [a for _f, _b, a in fehler]

        assert len(fehler) == 3
        assert abstaende == sorted(abstaende), abstaende

    def test_bei_faktor_eins_ist_die_naeherung_gut(self) -> None:
        """Dort rechnet sie genau eine Gebuehr heraus - das ist fast die
        reibungslose Welt. Gemessen auf Tageskerzen: 0,004 daneben."""
        fehler = self._mit_steigendem_anteil().naeherungsfehler()
        bei_eins = next(a for f, _b, a in fehler if f == 1.0)
        bei_fuenf = next(a for f, _b, a in fehler if f == 5.0)

        assert bei_eins < bei_fuenf

    def test_das_urteil_nennt_den_groessten_abstand(self) -> None:
        text = self._mit_steigendem_anteil().urteil()

        assert "reibungslose Welt ist eine einzige" in text
        assert "daneben" in text

    def test_das_urteil_entwertet_den_kippfaktor_ausdruecklich(self) -> None:
        leiter = self._mit_steigendem_anteil()
        text = leiter.urteil()

        assert leiter.gerechneter_kipppunkt is not None
        assert "Kippfaktor keine Messung" in text
        assert "Reichweite der Rechnung" in text

    def test_ohne_nullsprosse_gibt_es_keinen_fehler_zu_nennen(self) -> None:
        """Ohne gemessene reibungslose Welt fehlt der Bezugspunkt - dann wird
        auch nichts behauptet."""
        leiter = _leiter(
            (1.0, (0.30, 0.10, 0.00, -0.10)),
            (5.0, (0.20, 0.12, 0.08, -0.02)),
        )

        assert leiter.reibungslos is None
        assert leiter.naeherungsfehler() == []
        assert "reibungslose Welt ist eine einzige" not in leiter.urteil()


class TestMehrReibungKannDieKopplungAuchStaerken:
    """Was auf Tageskerzen gemessen wurde: -0,370 bei Faktor 0 bis -0,557 bei
    Faktor 56. Mehr Reibung trifft die haeufig handelnden Regeln haerter - und
    genau das *ist* die Kopplung."""

    @staticmethod
    def _staerker() -> Reibungsleiter:
        return _leiter(
            (0.0, (0.30, 0.12, 0.02, -0.05)),
            (1.0, (0.30, 0.10, 0.00, -0.10)),
            (56.0, (0.34, 0.08, -0.06, -0.22)),
        )

    def test_kein_kipppunkt(self) -> None:
        assert self._staerker().kippt_unter_aufschlag is None

    def test_das_urteil_sagt_staerker_und_warum(self) -> None:
        text = self._staerker().urteil()

        assert "nicht schwaecher, sondern **staerker**" in text
        assert "haeufig handelnden Regeln haerter" in text

    def test_bei_gleichbleibender_kopplung_steht_der_satz_nicht_da(self) -> None:
        gleich = _leiter(
            (0.0, (0.30, 0.10, 0.00, -0.10)),
            (56.0, (0.30, 0.10, 0.00, -0.10)),
        )

        assert "staerker" not in gleich.urteil()


class TestDieZweiPunktFrageFaelltAusDenselbenSprossen:
    """Sonst stuende sie ein zweites Mal gerechnet da."""

    def test_null_und_eins_ergeben_die_probe(self) -> None:
        probe = _leiter(*KIPPT_ZWISCHEN_5_UND_10).probe

        assert isinstance(probe, Reibungsprobe)
        assert probe.belastbar

    def test_ohne_nullsprosse_gibt_es_keine_probe(self) -> None:
        assert _leiter(
            (1.0, (0.30, 0.10, 0.00, -0.10)),
            (5.0, (0.20, 0.12, 0.08, -0.02)),
        ).probe is None

    def test_ohne_betriebspunkt_ebenso(self) -> None:
        assert _leiter(
            (0.0, (0.30, 0.12, 0.02, -0.05)),
            (5.0, (0.20, 0.12, 0.08, -0.02)),
        ).probe is None


class TestDieTabelle:
    def test_sie_zeigt_jede_sprosse_geordnet(self) -> None:
        zeilen = _leiter(*KIPPT_ZWISCHEN_5_UND_10).tabelle().splitlines()

        assert len(zeilen) == 2 + 4
        assert zeilen[2].split()[0] == "0"
        assert zeilen[-1].split()[0] == "10"

    def test_die_trennlinie_passt_zur_ueberschrift(self) -> None:
        zeilen = _leiter(*KIPPT_ZWISCHEN_5_UND_10).tabelle().splitlines()

        assert len(zeilen[1]) == len(zeilen[0])

    def test_eine_leere_sprosse_steht_als_strich(self) -> None:
        text = Reibungsleiter(
            sprossen=(
                Reibungssprosse(faktor=1.0, frage=_frage(0.3, 0.1, 0.0, -0.1)),
                Reibungssprosse(faktor=9.0, frage=Kostenfrage()),
            )
        ).tabelle()

        assert "-" in text.splitlines()[-1]

    def test_ohne_sprossen_sagt_sie_das(self) -> None:
        assert "Keine Sprossen" in Reibungsleiter().tabelle()


class TestDerBefehlHatNurEinenWegInDieRechnung:
    """``--reibungslos`` ist genau ``--reibungsleiter 0``. Zwei Wege in
    denselben Code, nicht zwei Rechnungen."""

    @staticmethod
    def _quelle() -> str:
        baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
        knoten = next(
            k
            for k in ast.walk(baum)
            if isinstance(k, ast.FunctionDef) and k.name == "vorratsdecke"
        )
        return ast.unparse(knoten)

    def test_reibungslos_setzt_nur_die_nullsprosse(self) -> None:
        quelle = self._quelle()

        assert "if reibungslos and 0.0 not in faktoren:" in quelle
        assert "faktoren.insert(0, 0.0)" in quelle

    def test_es_gibt_genau_einen_skalierten_kostensatz(self) -> None:
        quelle = self._quelle()

        assert quelle.count("costs.scaled(") == 1
        assert "def _skaliert(" in quelle

    def test_der_betriebspunkt_steht_als_eigene_sprosse(self) -> None:
        """Sonst faehrt die Leiter an der Stelle vorbei, an der alle uebrigen
        Zahlen des Projekts stehen."""
        quelle = self._quelle()

        assert "Reibungssprosse(faktor=1.0, frage=frage)" in quelle

    def test_der_walkforward_wird_je_sprosse_gefahren(self) -> None:
        quelle = self._quelle()

        assert "for faktor in faktoren:" in quelle
        assert "sprossenkosten[faktor]" in quelle
