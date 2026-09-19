"""Die Gates laufen auf dem Korb, gehandelt wird ein Bein.

**Befund 264.** Befund 263 hat benannt, dass der Zulassungsnachweis kein
Symbol kennt - nur ``perpetual``/``spot`` und die Kerzenlaenge - und die Luecke
bewusst offengelassen: *"ein Portfoliokandidat traegt mehrere Symbole, und was
'passt zu' dann heisst, ist eine Entscheidung und keine Zeile Code."*

Nachgemessen, was die Entscheidung kostet. Dieselbe Strategie, derselbe
Zeitraum, nur der Umfang geaendert:

    Korb (zugelassen)   158 Trades   14,34 % p.a.    9,87 % Rueckgang   9/11
    nur BTC              77 Trades   13,87 %        10,71 %             8/11
    nur ETH              81 Trades   14,13 %        12,17 %             8/11

**Jedes Bein verliert ein Gate, das der Korb haelt - und ein anderes.** BTC
faellt an "Schlechtestes Jahr", ETH am "Drawdown". Der Korb zieht den
Rueckgang unter den jedes einzelnen Beins, weil die beiden nicht gleichzeitig
fallen; wer ein Bein handelt, gibt das auf.

``LiveTrader`` handelt genau ein ``instrument.symbol``. Was ``cli trade``
laufen liesse, ist also nicht das, was bestanden hat.

Was hier gehalten wird
----------------------
Dass der Umfang aufgezeichnet wird, dass die Unterdeckung auffaellt, und dass
sie **nicht** gesperrt wird - eine Sperre naehme dem Projekt den einzigen
Handelsweg. Was fehlt, ist eine Entscheidung, und die faellt nicht in einer
Fehlermeldung.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from research.admission import Zulassungsbedingungen, lade_bedingungen

KORB = "BTCUSD_BITSTAMP,ETHUSD_BITSTAMP"


def _quelle(name: str) -> str:
    baum = ast.parse(Path("cli.py").read_text(encoding="utf-8"))
    knoten = next(
        k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == name
    )
    return ast.unparse(knoten)


class TestDerUmfangStehtImNachweis:
    def test_die_beine_kommen_einzeln_heraus(self) -> None:
        b = Zulassungsbedingungen(maerkte=KORB)

        assert b.beine == ("BTCUSD_BITSTAMP", "ETHUSD_BITSTAMP")

    def test_leerraum_und_leere_eintraege_stoeren_nicht(self) -> None:
        b = Zulassungsbedingungen(maerkte=" BTC , , ETH ")

        assert b.beine == ("BTC", "ETH")

    def test_ohne_aufzeichnung_gibt_es_keine_beine(self) -> None:
        assert Zulassungsbedingungen().beine == ()

    def test_der_lauf_schreibt_sie_mit(self) -> None:
        """Aus den Konfigurationen gelesen wie alles im Nachweis."""
        quelle = _quelle("_bedingungen")

        assert "maerkte=" in quelle
        assert "join(configs)" in quelle

    def test_der_text_nennt_sie(self) -> None:
        text = Zulassungsbedingungen(markt="spot", maerkte=KORB).als_text()

        assert "2 Bein(e)" in text
        assert KORB in text


class TestDeckungIstNichtVermutung:
    def test_derselbe_korb_ist_gedeckt(self) -> None:
        b = Zulassungsbedingungen(maerkte=KORB)

        assert b.deckt_ab(["ETHUSD_BITSTAMP", "BTCUSD_BITSTAMP"])

    def test_ein_einzelnes_bein_ist_es_nicht(self) -> None:
        assert not Zulassungsbedingungen(maerkte=KORB).deckt_ab(["BTCUSD_BITSTAMP"])

    def test_ein_fremder_markt_erst_recht_nicht(self) -> None:
        assert not Zulassungsbedingungen(maerkte=KORB).deckt_ab(["XRPUSD_BITSTAMP"])

    def test_ohne_aufzeichnung_heisst_es_unbekannt(self) -> None:
        """Wie bei ``passt_zu`` und ``passt_zur_kerzenlaenge``: Ein leeres
        Feld ist keine Freigabe."""
        assert not Zulassungsbedingungen().deckt_ab(["BTCUSD_BITSTAMP"])


class TestDerLivebetriebSagtEsUndSperrtNicht:
    """**Befund 308: am Verhalten geprueft, nicht am Quelltext.**

    Bis hierher lasen diese Tests ``cli.py`` als Zeichenkette und suchten
    'deckt_ab(', 'yellow' und 'Befund 264'. Das haelt, solange niemand den
    Code anfasst - und es haelt auch dann noch, wenn die Warnung hinter einer
    Bedingung verschwindet, die nie zutrifft. Genau dagegen steht sonst
    ueberall in diesem Projekt der Satz, dass eine Wache auf einen Satz auch
    einen falschen haelt.

    Der Text steht deshalb in ``Zulassungsbedingungen.unterdeckung`` und wird
    hier aufgerufen.
    """

    def test_ein_bein_aus_einem_korb_wird_gemeldet(self) -> None:
        text = Zulassungsbedingungen(maerkte=KORB).unterdeckung("BTCUSD_BITSTAMP")

        assert text is not None
        assert "2 Beinen" in text
        assert "BTCUSD_BITSTAMP allein" in text

    def test_die_meldung_nennt_was_es_kostet(self) -> None:
        """Ohne die Begruendung liest sie sich wie eine Formalie."""
        text = Zulassungsbedingungen(maerkte=KORB).unterdeckung("BTCUSD_BITSTAMP")

        assert "nicht gleichzeitig fallen" in text
        assert "Befund 264" in text

    def test_ein_fremdes_symbol_ebenso(self) -> None:
        text = Zulassungsbedingungen(maerkte=KORB).unterdeckung("XRPUSD_BITSTAMP")

        assert text is not None and "XRPUSD_BITSTAMP allein" in text

    def test_der_gedeckte_korb_schweigt(self) -> None:
        """Handelbar ist er nicht - aber das ist nicht die Frage dieser
        Zeile, und eine Warnung ohne Anlass wird ueberlesen."""
        b = Zulassungsbedingungen(maerkte="BTCUSD_BITSTAMP")

        assert b.unterdeckung("BTCUSD_BITSTAMP") is None

    def test_ein_einzelnes_bein_im_nachweis_schweigt_auch(self) -> None:
        """Wurde auf einem Markt zugelassen und laeuft auf ihm, gibt es
        nichts zu melden."""
        b = Zulassungsbedingungen(maerkte="BTCUSD_BITSTAMP")

        assert b.unterdeckung("ETHUSD_BITSTAMP") is None, (
            "ein Nachweis ueber ein Bein sagt nichts ueber ein anderes - "
            "das ist Sache von 'passt_zu', nicht dieser Zeile"
        )

    def test_ohne_aufzeichnung_schweigt_er(self) -> None:
        """Darueber spricht die eigene Zeile zum fehlenden Nachweis."""
        assert Zulassungsbedingungen().unterdeckung("BTCUSD_BITSTAMP") is None

    def test_der_befehl_ruft_sie_auf_und_bricht_nicht_ab(self) -> None:
        """Was sich am Text noch pruefen laesst, ist die **Verdrahtung**:
        dass der Befehl die Meldung holt und dass an dieser Stelle kein
        Abbruch steht. Eine Sperre naehme dem Projekt den einzigen
        Handelsweg, den es hat.
        """
        quelle = _quelle("trade")
        stelle = quelle.index("unterdeckung(")
        danach = quelle[stelle : stelle + 400]

        assert "typer.Exit" not in danach


class TestAlteDateienBleibenLesbar:
    def test_ein_nachweis_ohne_maerkte_laedt(self, tmp_path: Path) -> None:
        pfad = tmp_path / "champion.json"
        pfad.write_text(
            json.dumps({"genom": {}, "zulassung": {"markt": "spot", "gesamt": 11}})
        )

        b = lade_bedingungen(pfad)

        assert b.markt == "spot"
        assert b.maerkte == ""
        assert b.beine == ()

    def test_ein_nachweis_mit_maerkten_auch(self, tmp_path: Path) -> None:
        pfad = tmp_path / "champion.json"
        pfad.write_text(
            json.dumps(
                {
                    "genom": {},
                    "zulassung": {"markt": "spot", "gesamt": 11, "maerkte": KORB},
                }
            )
        )

        assert lade_bedingungen(pfad).beine == (
            "BTCUSD_BITSTAMP",
            "ETHUSD_BITSTAMP",
        )
