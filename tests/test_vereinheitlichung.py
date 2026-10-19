"""Die Einzeiländerung, die das haerteste Gate kippen wuerde - Befund 374.

``deflated_sharpe_ratio`` rechnet zweimal mit der Streuung des
Sharpe-Schaetzers, und zwar in zwei verschiedenen Formen:

* im **Nenner** der Teststatistik steht die verteilungsbewusste Form nach
  Mertens und Lo, ``1 - Schiefe*SR + (Woelbung-1)/4 * SR^2``;
* in ``V``, der Streuung ueber die Versuche, steht ``1/(n-1)`` - dieselbe
  Groesse unter Normalverteilung.

Das sieht wie ein Versehen aus. Die Klammer aus dem Nenner auch in ``V``
einzusetzen waere **eine Zeile**, waere mit Literatur belegbar, und am
Spot-Punkt gemessen:

    angenommen  1/(n-1)      sqrt(V) 0,0937   DSR 0,5827   durchgefallen
    vereinheitlicht           sqrt(V) 0,0542   DSR 0,9869   BESTANDEN

Das blockierende Gate des Projekts, gekippt von einer Zeile, die wie eine
Fehlerbehebung aussieht. Diese Datei haelt fest, dass sie nicht gemacht wird,
und warum - damit der naechste Durchgang nicht dasselbe Argument findet und
es fuer neu haelt.

Der Grund in einem Satz: ``V`` ist eine Eigenschaft der **Suche**, nicht des
Gewinners. Der Beleg steht in der Formel selbst - ab Schiefe 4,70 wird die
Klammer negativ, dann gibt es gar keine Huerde mehr.
"""

from __future__ import annotations

import inspect

import pytest

from research.gates import deflated_sharpe_ratio
from research.referenz import SPOTPUNKT
from research.streuung import Vereinheitlichung


@pytest.fixture
def lage() -> Vereinheitlichung:
    """Der verzeichnete Spot-Punkt, nicht erfundene Zahlen."""
    return Vereinheitlichung(
        sharpe=SPOTPUNKT.guete,
        stichprobe=SPOTPUNKT.effektiv,
        versuche=SPOTPUNKT.versuche,
        schiefe=SPOTPUNKT.schiefe,
        woelbung=SPOTPUNKT.woelbung,
    )


class TestDieVerlockungIstEcht:
    """Erst der Nachweis, dass es etwas zu widerstehen gibt.

    Ohne diese Zahlen waere die Ablehnung eine Meinung.
    """

    def test_heute_faellt_das_gate(self, lage: Vereinheitlichung) -> None:
        assert lage.dsr_angenommen() == pytest.approx(SPOTPUNKT.dsr, abs=5e-5)
        assert lage.dsr_angenommen() < 0.95

    def test_vereinheitlicht_bestuende_es(self, lage: Vereinheitlichung) -> None:
        assert lage.dsr_vereinheitlicht() == pytest.approx(0.9869, abs=5e-4)
        assert lage.dsr_vereinheitlicht() >= 0.95

    def test_das_urteil_kippt(self, lage: Vereinheitlichung) -> None:
        assert lage.kippt() is True

    def test_die_streuung_waere_42_prozent_kleiner(
        self, lage: Vereinheitlichung
    ) -> None:
        assert lage.angenommen() == pytest.approx(0.0937, abs=5e-5)
        assert lage.vereinheitlicht() == pytest.approx(0.0542, abs=5e-5)
        geschrumpft = 1 - lage.vereinheitlicht() / lage.angenommen()
        assert geschrumpft == pytest.approx(0.421, abs=0.002)

    def test_und_die_klammer_ist_dieselbe_wie_im_nenner(
        self, lage: Vereinheitlichung
    ) -> None:
        """Kein Zufall und keine zweite Formel: wortgleich aus dem Gate.

        Steht die Klammer im Gate einmal anders, soll dieser Test fallen -
        sonst widerlegt diese Datei eine Aenderung, die es nicht mehr gibt.
        """
        quelle = inspect.getsource(deflated_sharpe_ratio)
        assert "1 - skew * observed_sharpe + (kurtosis - 1) / 4 * observed_sharpe**2" in quelle


class TestWarumSieTrotzdemFalschIst:
    """Der Kreisbezug, gemessen und nicht behauptet."""

    def test_die_klammer_faellt_mit_der_schiefe_des_gewinners(
        self, lage: Vereinheitlichung
    ) -> None:
        werte = [lage.klammer(sk) for sk in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)]
        assert werte == sorted(werte, reverse=True)
        assert werte[0] > 1.0  # symmetrisch: strenger als die Annahme
        assert werte[-1] < 0.0  # schief genug: gar keine Huerde

    def test_fuer_eine_symmetrische_strategie_waere_es_strenger(
        self, lage: Vereinheitlichung
    ) -> None:
        """Dieselbe Aenderung, andere Richtung - das ist der ganze Einwand.

        Eine Regel, die ihre Huerde senkt, waere eine Regel. Eine Regel, die
        sie je nach Form des Gewinners senkt oder hebt, ist keine.
        """
        assert lage.dsr_vereinheitlicht(0.0) < lage._lage(0.0).bei(lage.angenommen())
        assert lage.dsr_vereinheitlicht() > lage.dsr_angenommen()

    def test_ab_einer_schiefe_verschwindet_die_huerde_ganz(
        self, lage: Vereinheitlichung
    ) -> None:
        grenze = lage.huerde_verschwindet_ab()
        assert grenze is not None
        assert grenze == pytest.approx(4.7027, abs=1e-3)
        assert lage.klammer(grenze + 0.1) < 0
        assert lage.vereinheitlicht(grenze + 0.1) == 0.0

    def test_die_grenze_wird_gerechnet_und_nicht_gepflegt(
        self, lage: Vereinheitlichung
    ) -> None:
        """Keine Konstante neben der Formel.

        Erst stand hier 5,0 als 'SCHIEFEGRENZE'; gemessen sind es 4,7027. Drei
        gepflegte Zahlen stehen im Register als nicht mehr reproduzierbar - das
        war beinahe die vierte.
        """
        import research.streuung as modul

        assert not hasattr(modul, "SCHIEFEGRENZE")
        andere = Vereinheitlichung(
            sharpe=0.1, stichprobe=200, versuche=50, schiefe=1.0, woelbung=6.0
        )
        assert andere.huerde_verschwindet_ab() != lage.huerde_verschwindet_ab()

    def test_sie_landet_in_der_verworfenen_messung(
        self, lage: Vereinheitlichung
    ) -> None:
        """0,0542 liegt mitten in 0,0428 bis 0,0608 (Befund 68).

        Das ist kein unabhaengiger Beleg, sondern dieselbe Untertreibung auf
        einem anderen Weg: Jener Bereich stammt aus einer Auswahl, in der die
        Verlierer fehlen, und wird genau deshalb nicht eingesetzt.
        """
        assert 0.0428 < lage.vereinheitlicht() < 0.0608


class TestDasGateNimmtSieNicht:
    """**Die Festnagelung.** Der Rest dieser Datei ist Begruendung."""

    def test_ohne_angabe_rechnet_das_gate_mit_1_durch_n_minus_1(
        self, lage: Vereinheitlichung
    ) -> None:
        ohne = deflated_sharpe_ratio(
            observed_sharpe=lage.sharpe,
            trials=lage.versuche,
            sample_size=lage.stichprobe,
            skew=lage.schiefe,
            kurtosis=lage.woelbung,
        )
        assert ohne == pytest.approx(lage.dsr_angenommen(), abs=1e-12)
        assert ohne != pytest.approx(lage.dsr_vereinheitlicht(), abs=1e-3)

    def test_die_vorgabe_steht_so_im_quelltext(self) -> None:
        """Gegen eine stille Aenderung, nicht gegen eine offene.

        Wer die Zeile aendert, soll diesen Test sehen und den Befund lesen
        muessen - nicht, weil die Aenderung undenkbar ist, sondern weil sie
        das blockierende Gate kippt und das keine Nebenwirkung sein darf.
        """
        quelle = inspect.getsource(deflated_sharpe_ratio)
        assert "else 1.0 / (sample_size - 1)" in quelle

    def test_niemand_uebergibt_die_vereinheitlichte_streuung(self) -> None:
        """Die Klasse rechnet und handelt nicht.

        'research/streuung.py' selbst ist ausgenommen - dort **soll** der Wert
        ausgerechnet und als DSR gezeigt werden, das ist die Messung. Was nicht
        passieren darf, ist ein Zulassungspfad, der ihn als Eingabe nimmt:
        'cli', 'research/gates.py', der Wettbewerb. Erst war dieser Waechter
        grober und traf das eigene Modul - ein Waechter, der die erlaubte
        Stelle anzeigt, nennt nicht die Hintertuer.
        """
        import re
        from pathlib import Path

        muster = re.compile(r"sharpe_variance\s*=[^)\n]*vereinheitlicht")
        verdacht = [
            str(datei)
            for datei in Path(".").glob("**/*.py")
            if ".venv" not in datei.parts
            and datei != Path("research/streuung.py")
            and muster.search(datei.read_text(encoding="utf-8"))
        ]
        assert verdacht == []

    def test_das_urteil_sagt_beides(self, lage: Vereinheitlichung) -> None:
        """Die Zahl **und** die Ablehnung. Eine Zahl ohne Urteil waere eine
        Einladung."""
        text = lage.urteil()
        assert "0.9869" in text
        assert "kippt" in text
        assert "Eigenschaft der Suche" in text
        assert "4.70" in text
