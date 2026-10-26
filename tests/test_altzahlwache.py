"""Wer eine Altzahl nennt, sagt es dazu - Befund 422.

Befund 408 hat sechs gepflegte Zahlen als nicht reproduzierbar verzeichnet und
in ``datenstempel.ALTZAHLEN`` gefuehrt. Drei Tests und drei Modulkoepfe wurden
damals in Ordnung gebracht. Nicht in Ordnung gebracht wurden die Stellen, an
denen dieselben Zahlen als **Prosa** stehen - darunter zwei Entscheidungen, also
genau die Texte, aus denen der Nutzer entscheidet.

Dieselbe Bauart wie die Wache in ``test_referenz`` fuer ueberholte
Referenzwerte (Befund 130/140), nur fuer die Altzahlen. Und derselbe Unterschied
wie dort: Geprueft wird **ortsnah**, nicht je Datei. Eine Pruefung je Datei
waere gruen geblieben - 'research/stand.py' nennt Befund 408 an anderer Stelle,
und die Entscheidungsvorlage daneben log trotzdem.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.datenstempel import ALTZAHLEN
from research.stand import BEHOBEN, ENTSCHEIDUNGEN, GESCHLOSSEN, OFFEN

#: Was als Hinweis gilt. Der Vorwaertszeiger eines Eintrags zaehlt auch -
#: er ist der Weg, den dieses Register fuer veraltete Zahlen vorsieht.
HINWEISE = ("408", "364", "datenstempel", "ALTZAHLEN")

#: Ab diesem Befund sind die Altzahlen verzeichnet. Ein Eintrag, dessen
#: massgebliche Fundstelle davor liegt, kann sie nicht kennen - also muss er
#: sie im Text nennen.
SEIT = 408

#: Module, die die Zeilenpruefung nicht nimmt - mit Grund, denn eine Ausnahme
#: ohne Grund ist eine Luecke.
#:
#: * ``datenstempel`` fuehrt die Zahlen selbst.
#: * ``datenstand`` ist der Eintrag, der die Drift verzeichnet.
#: * ``stand`` traegt jede Altzahl **innerhalb** eines Register- oder
#:   Entscheidungstexts, und die prueft 'TestKeinEintragNenntEineAltzahlOhne-
#:   Hinweis' genau - je Eintrag statt je Zeilenfenster. Die groebere Pruefung
#:   hat dort nur falsche Treffer geliefert: Der Eintrag von Befund 364 nennt
#:   alte und neue Zahl nebeneinander, aber sein Hinweis steht mehr als
#:   fuenfundzwanzig Quellzeilen entfernt, weil der Eintrag lang ist. Eine
#:   schwaechere Pruefung neben eine praezisere zu stellen bringt Rauschen,
#:   nicht Deckung.
AUSGENOMMEN = frozenset({"datenstempel.py", "datenstand.py", "stand.py"})


def _werte() -> set[str]:
    """Die gepflegten Werte in der Schreibweise der Prosa."""
    formen = set()
    for z in ALTZAHLEN:
        for roh in (f"{z.gepflegt:g}", f"{z.gepflegt:.4f}"):
            formen.add(roh.replace(".", ","))
            formen.add(roh)
    return formen


def _fehlt_der_hinweis(text: str, massgeblich: int) -> list[str]:
    genannt = sorted(w for w in _werte() if w in text)
    if not genannt:
        return []
    if any(h in text for h in HINWEISE) or massgeblich >= SEIT:
        return []
    return genannt


class TestDieWacheLoestUeberhauptAus:
    """Ohne diesen Test waere die naechste Pruefung leer und wertlos."""

    def test_es_gibt_eintraege_die_altzahlen_nennen(self) -> None:
        treffer = [
            r.befund
            for r in (*BEHOBEN, *OFFEN, *GESCHLOSSEN)
            if any(w in r.ergebnis for w in _werte())
        ]

        assert treffer, "keine Altzahl im Register - die Pruefung liefe leer"

    def test_und_entscheidungen_die_es_tun(self) -> None:
        treffer = [
            e.befund
            for e in ENTSCHEIDUNGEN
            if any(w in e.zahl + e.warum for w in _werte())
        ]

        assert treffer


class TestKeinEintragNenntEineAltzahlOhneHinweis:
    def test_die_richtungen(self) -> None:
        offen = {
            r.befund: _fehlt_der_hinweis(r.ergebnis, r.massgeblich)
            for r in (*BEHOBEN, *OFFEN, *GESCHLOSSEN)
        }
        schuldig = {b: w for b, w in offen.items() if w}

        assert schuldig == {}, (
            f"Altzahl ohne Hinweis auf Befund {SEIT}: {schuldig} - entweder "
            f"den Vermerk in den Text, oder 'zuletzt' nachziehen."
        )

    def test_die_entscheidungen(self) -> None:
        schuldig = {}
        for e in ENTSCHEIDUNGEN:
            for feld in ("zahl", "warum"):
                fehlt = _fehlt_der_hinweis(getattr(e, feld), e.massgeblich)
                if fehlt:
                    schuldig[(e.befund, feld)] = fehlt

        assert schuldig == {}, (
            f"Eine Entscheidungsvorlage nennt eine Altzahl ohne Vermerk: "
            f"{schuldig}"
        )


class TestAuchDieModulprosa:
    """Die vierte Stelle war ein Docstring - 'gate_cost_stress' nannte die
    beiden Betraege ohne jeden Hinweis."""

    @staticmethod
    def _module() -> list[Path]:
        return [
            p
            for p in sorted(Path("research").rglob("*.py"))
            if p.name not in AUSGENOMMEN
        ]

    def test_jede_altzahl_hat_ihren_hinweis_in_der_naehe(self) -> None:
        fenster = 25
        schuldig: dict[str, list[str]] = {}
        for pfad in self._module():
            zeilen = pfad.read_text(encoding="utf-8").splitlines()
            for i, zeile in enumerate(zeilen):
                genannt = sorted(w for w in _werte() if w in zeile)
                if not genannt:
                    continue
                umfeld = "\n".join(
                    zeilen[max(0, i - fenster) : i + fenster]
                )
                if not any(h in umfeld for h in HINWEISE):
                    schuldig.setdefault(pfad.name, []).extend(genannt)

        assert schuldig == {}, (
            f"Altzahl ohne Hinweis im Umfeld von {fenster} Zeilen: {schuldig}"
        )

    def test_die_ausnahmen_sind_begruendet(self) -> None:
        """Drei Module, drei Gruende - und 'stand.py' ist durch die
        praezisere Pruefung gedeckt, nicht ausgenommen."""
        from pathlib import Path as _Path

        quelle = _Path("tests/test_altzahlwache.py").read_text(
            encoding="utf-8"
        )

        assert len(AUSGENOMMEN) == 3
        for name in AUSGENOMMEN:
            assert f"``{name.removesuffix('.py')}``" in quelle, name

    def test_und_die_pruefung_sieht_ueberhaupt_etwas(self) -> None:
        gesehen = [
            p.name
            for p in self._module()
            if any(w in p.read_text(encoding="utf-8") for w in _werte())
        ]

        assert gesehen, "kein Modul nennt eine Altzahl - die Pruefung liefe leer"


class TestWarumOrtsnahUndNichtJeDatei:
    """Der Punkt, an dem eine einfachere Wache versagt haette."""

    def test_stand_py_nennt_den_hinweis_irgendwo(self) -> None:
        text = Path("research/stand.py").read_text(encoding="utf-8")

        assert "Befund 408" in text

    def test_und_trug_die_altzahl_trotzdem_ohne_vermerk(self) -> None:
        """Belegt am Eintrag selbst: Die Entscheidung 96 nennt die Betraege,
        und ihre massgebliche Fundstelle ist 339 - sie kann 408 nicht
        kennen. Ohne den Vermerk im Text waere sie durchgefallen."""
        e = next(x for x in ENTSCHEIDUNGEN if x.befund == 96)

        assert e.massgeblich < SEIT
        assert "2318,32" in e.zahl
        assert "Altzahlen" in e.zahl

    def test_die_zweite_entscheidung_genauso(self) -> None:
        e = next(x for x in ENTSCHEIDUNGEN if x.befund == 69)

        assert e.massgeblich < SEIT
        assert "0,5958" in e.zahl
        assert "0,5994" in e.zahl

    def test_und_der_eintrag_der_sie_gepflegt_hat_zeigt_nach_vorn(self) -> None:
        """356 hat die Momente festgeschrieben, 408 hat sie nachgemessen -
        der Zeiger hat gefehlt."""
        r = next(x for x in BEHOBEN if x.befund == 356)

        assert r.zuletzt == 408


class TestDerVermerkSagtWasSichAendert:
    """Ein Vorbehalt, der nur 'veraltet' sagt, laesst den Leser ratlos."""

    def test_bei_96_aendert_sich_die_entscheidung_nicht(self) -> None:
        e = next(x for x in ENTSCHEIDUNGEN if x.befund == 96)

        assert "nicht beruehrt" in e.zahl
        assert "steht also unveraendert" in e.zahl

    def test_bei_69_auch_nicht(self) -> None:
        e = next(x for x in ENTSCHEIDUNGEN if x.befund == 69)

        assert "aendert das nichts" in e.zahl

    def test_und_das_gate_nennt_die_heutigen_zahlen(self) -> None:
        from research.gates import gate_cost_stress

        text = gate_cost_stress.__doc__ or ""

        assert "2331,38" in text
        assert "1643,22" in text
        assert "nicht im Versionsstand" in text


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_vier_stellen(self) -> None:
        eintrag = next(r for r in BEHOBEN if r.befund == 422)

        assert "vier Stellen" in eintrag.ergebnis
        assert "zwei davon" in eintrag.ergebnis

    def test_und_warum_je_datei_nicht_genuegt(self) -> None:
        eintrag = next(r for r in BEHOBEN if r.befund == 422)

        assert "je Datei" in eintrag.ergebnis

    def test_und_421_zeigt_nach_vorn(self) -> None:
        assert next(r for r in BEHOBEN if r.befund == 421).zuletzt == 422


@pytest.mark.parametrize("zahl", ALTZAHLEN, ids=lambda z: z.name[:28])
def test_jede_altzahl_ist_in_der_prosa_auffindbar(zahl) -> None:
    """Die Gegenprobe zur Wache: Wenn eine Altzahl in keiner Schreibweise
    gesucht wird, prueft die Wache sie nicht."""
    formen = {f"{zahl.gepflegt:g}", f"{zahl.gepflegt:g}".replace(".", ",")}

    assert formen & _werte()
