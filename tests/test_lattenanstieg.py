"""Was ein Versuch die **Suche** kostet, nicht einen fixen Kandidaten - 423.

``research/erreichbarkeit.py`` beantwortet seit Befund 327 die Frage, was ein
weiterer Versuch den **vorhandenen** Kandidaten kostet: 0,0011 DSR-Punkte, und
der Schluss "Versuchsdisziplin haelt den Abstand, sie schliesst ihn nicht".

Die Gegenfrage fehlte: Wie hoch steigt die Latte fuer einen **kuenftigen**
Fund? Gemessen ist sie fast flach - das ganze restliche Budget hebt sie um ein
Prozent. Beide Lesarten sind wahr, die zweite ist die planungsrelevante.
"""

from __future__ import annotations

import inspect

import pytest

from research.erreichbarkeit import STAENDE, latte_je_stand, lattenanstieg
from research.referenz import SPOTPUNKT


class TestDieGemesseneLatte:
    def test_die_staende_decken_den_stand_und_die_budgetgrenze(self) -> None:
        assert SPOTPUNKT.versuche in STAENDE
        assert 230 in STAENDE

    def test_die_tafel_beginnt_am_gemeldeten_punkt(self) -> None:
        """Gegenprobe: Bei unveraendertem Versuchsstand muss die Tafel die
        Zahl des Punktes selbst liefern, nicht eine neue."""
        stand, noetig, faktor = latte_je_stand()[0]

        assert stand == SPOTPUNKT.versuche == 203
        assert noetig == pytest.approx(SPOTPUNKT.noetige_guete())
        assert noetig == pytest.approx(0.3374, abs=5e-5)
        assert faktor == pytest.approx(1.25, abs=0.005)

    def test_sie_steigt_monoton(self) -> None:
        werte = [noetig for _, noetig, _ in latte_je_stand()]

        assert werte == sorted(werte)
        assert len(set(werte)) == len(werte)

    def test_und_zwar_flach(self) -> None:
        tafel = {stand: noetig for stand, noetig, _ in latte_je_stand()}

        assert tafel[230] == pytest.approx(0.3407, abs=5e-5)
        assert tafel[1000] == pytest.approx(0.3777, abs=5e-5)

    def test_das_ganze_restbudget_hebt_sie_um_ein_prozent(self) -> None:
        """Die Zahl, die den Befund traegt."""
        assert lattenanstieg(203, 230) == pytest.approx(0.0098, abs=5e-4)
        assert lattenanstieg(203, 230) < 0.015

    def test_selbst_das_zweieinhalbfache_bleibt_unter_zehn_prozent(self) -> None:
        assert lattenanstieg(203, 500) == pytest.approx(0.069, abs=0.002)
        assert lattenanstieg(203, 500) < 0.10

    def test_ohne_latte_kein_anstieg(self) -> None:
        import dataclasses

        ohne = dataclasses.replace(SPOTPUNKT, schiefe=None, woelbung=None)

        assert ohne.noetige_guete() is None
        assert latte_je_stand(ohne) == ()
        with pytest.raises(ValueError, match="ohne Latte"):
            lattenanstieg(punkt=ohne)


class TestDieZahlenSindGerechnet:
    """Der Befund darf nicht als gepflegte Tafel enden - genau das hat 408
    sechsmal als nicht reproduzierbar verzeichnet."""

    def test_die_tafel_fragt_das_werkzeug(self) -> None:
        quelle = inspect.getsource(latte_je_stand)

        assert "noetige_guete(versuche=stand)" in quelle

    def test_und_haelt_keine_eigene_schwelle(self) -> None:
        """Kein Zahlenliteral in der Rechnung ausser dem Vergleich auf Null."""
        quelle = inspect.getsource(latte_je_stand)
        zeilen = [z for z in quelle.splitlines() if "0.3" in z or "0.4" in z]

        assert zeilen == []

    def test_der_anstieg_rechnet_aus_derselben_quelle(self) -> None:
        """Die Gegenprobe gegen eine zweite, abweichende Rechnung."""
        tafel = {stand: noetig for stand, noetig, _ in latte_je_stand()}

        assert lattenanstieg(203, 230) == pytest.approx(tafel[230] / tafel[203] - 1.0)


class TestWasDerKopfSagt:
    def _kopf(self) -> str:
        import research.erreichbarkeit as e

        return e.__doc__ or ""

    def test_er_nennt_beide_lesarten(self) -> None:
        kopf = self._kopf()

        assert "Fuer den **vorhandenen** Kandidaten" in kopf
        assert "Fuer einen **kuenftigen**" in kopf

    def test_und_welche_planungsrelevant_ist(self) -> None:
        kopf = self._kopf()

        assert "Die zweite ist die planungsrelevante" in kopf

    def test_und_was_nicht_folgt(self) -> None:
        """Ohne diesen Absatz liest sich der Befund als Freibrief fuer
        beliebig viele Versuche - und das waere falsch."""
        kopf = self._kopf()

        assert "**Was daraus nicht folgt**" in kopf
        assert "zaehlt jeder weitere gegen ihn" in kopf

    def test_der_alte_schluss_bleibt_stehen(self) -> None:
        """Zurueckgenommen wird nichts: Der Satz aus 327 gilt weiter, er
        beantwortet nur eine andere Frage."""
        kopf = self._kopf()

        assert "Versuchsdisziplin **haelt** den Abstand" in kopf

    def test_und_die_vier_fragen_stehen_im_kopf(self) -> None:
        kopf = self._kopf()

        assert "beantwortet vier Fragen" in kopf
        assert "fuer einen **kuenftigen** Kandidaten" in kopf

    def test_der_kopf_schreibt_sich_nichts_davon_selbst_zu(self) -> None:
        """Die DSR-Tafel und die Grenzkosten standen vorher da (327), und die
        Gegenrichtung ebenfalls (221).

        Diese Zusicherung hat in der Fassung von 423 auf dem Abschnittstitel
        gestanden und fiel, als 424 ihn richtigstellte. Sie prueft jetzt die
        **Absicht** statt der Ueberschrift, und sie ist dadurch strenger: Der
        Kopf muss beide Vorbefunde nennen, nicht nur den Zuschnitt des
        eigenen.
        """
        kopf = self._kopf()

        assert "Alles oben rechnet mit **diesem** Kandidaten" in kopf
        assert "**Beantwortet hat das Befund 221**" in kopf
        assert "Befund 423 hat dieselbe Groesse" in kopf
        assert "als neu berichtet" in kopf


class TestWasImRegisterSteht:
    def test_der_eintrag_nennt_die_tragende_zahl(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 423)

        assert "ein Prozent" in eintrag.ergebnis
        assert "0,3374" in eintrag.ergebnis and "0,3407" in eintrag.ergebnis

    def test_und_sagt_was_die_suche_wirklich_blockiert(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 423)

        assert "blockiert die Suche nicht" in eintrag.ergebnis

    def test_und_nennt_meine_zwei_fehlgriffe(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 423)

        assert "nachgebaut, statt vorher nachzusehen" in eintrag.ergebnis
        assert "Bisektion" in eintrag.ergebnis
        assert "zum zehnten mal" in eintrag.ergebnis.lower()

    def test_und_422_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 422).zuletzt == 423


class TestDerWarnhinweisStandSchonDa:
    """Der haertere Teil des Eingestaendnisses: Der Docstring der Funktion,
    die ich umgangen habe, warnt genau vor dem, was ich getan habe."""

    def test_noetige_guete_nimmt_den_versuchsstand_als_argument(self) -> None:
        unterschrift = inspect.signature(SPOTPUNKT.noetige_guete.__func__)

        assert "versuche" in unterschrift.parameters

    def test_und_ihr_docstring_warnt_vor_der_handrechnung(self) -> None:
        text = SPOTPUNKT.noetige_guete.__doc__ or ""

        assert "von Hand gerechnet" in text
        assert "355" in text


class TestDieWacheGegenDenDrittenFehlgriff:
    """Dreimal derselbe Reflex (420, zweimal hier) - ein Registereintrag hat
    ihn nicht verhindert, also prueft es jetzt eine Wache."""

    def test_sie_steht_bei_den_zusicherungen(self) -> None:
        from tests.test_zusicherungen import _nie_wahre_zusicherungen

        assert _nie_wahre_zusicherungen() == {}

    def test_der_eintrag_nennt_sie_als_folge_des_fehlgriffs(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 423)

        assert "beide unhaltbaren Zusicherungen aus 420 wieder" in eintrag.ergebnis
        assert "Ein Registereintrag hat das" in eintrag.ergebnis


class TestDieGroesseIstNichtNeu:
    """Befund 424. 423 hat sie als neu berichtet; gemessen hat sie Befund 221
    an zwei Stellen. Was bleibt, ist die Gegenprobe - und die steht hier."""

    def test_zweihunderteinundzwanzigs_funktion_gibt_dasselbe(self) -> None:
        """Der Kern der Richtigstellung: zwei unabhaengige Wege, eine Zahl."""
        from research.verbund import noetige_guete as verbund_guete

        n = SPOTPUNKT.effektiv
        ueber_verbund = (
            verbund_guete(n, 203, schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung) / n**0.5
        )

        assert ueber_verbund == pytest.approx(SPOTPUNKT.noetige_guete(versuche=203), abs=5e-5)
        assert ueber_verbund == pytest.approx(0.3374, abs=5e-5)

    def test_und_derselbe_anstieg(self) -> None:
        from research.verbund import noetige_guete as verbund_guete

        n = SPOTPUNKT.effektiv
        a, b = (
            verbund_guete(n, v, schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung)
            for v in (203, 230)
        )

        assert b / a - 1.0 == pytest.approx(lattenanstieg(203, 230), abs=1e-4)

    def test_und_reproduziert_221s_eigene_zahl(self) -> None:
        """221s Text nennt 1,18 % von 198 aus. Steht die Zahl noch?"""
        from research.verbund import noetige_guete as verbund_guete

        n = SPOTPUNKT.effektiv
        a, b = (
            verbund_guete(n, v, schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung)
            for v in (198, 230)
        )

        assert (b / a - 1.0) * 100 == pytest.approx(1.18, abs=0.01)

    def test_die_grenzkosten_aus_221_stehen_auch_noch(self) -> None:
        from research.verbund import versuchskosten

        n = SPOTPUNKT.effektiv
        gemessen = {
            v: versuchskosten(n, v, schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung)
            for v in (130, 198, 230, 1000)
        }

        assert gemessen[130] == pytest.approx(0.000212, abs=1e-6)
        assert gemessen[198] == pytest.approx(0.000135, abs=1e-6)
        assert gemessen[230] == pytest.approx(0.000115, abs=1e-6)
        assert gemessen[1000] == pytest.approx(0.000024, abs=1e-6)

    def test_der_kopf_nennt_221_als_quelle(self) -> None:
        import research.erreichbarkeit as e

        kopf = e.__doc__ or ""

        assert "**Beantwortet hat das Befund 221**" in kopf
        assert "verbund.versuchskosten" in kopf
        assert "Befund 424 hat es richtiggestellt" in kopf

    def test_und_die_funktion_selbst_auch(self) -> None:
        text = latte_je_stand.__doc__ or ""

        assert "**Die Groesse ist nicht neu**" in text
        assert "Befund 221" in text

    def test_der_eintrag_nennt_den_vierten_fehlgriff(self) -> None:
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 424)

        assert "vierte Fehlgriff derselben Art" in eintrag.ergebnis
        assert "der Schluss selbst" in eintrag.ergebnis

    def test_und_wo_ich_nicht_nachgesehen_habe(self) -> None:
        """Der verwertbare Teil des Eingestaendnisses: nicht 'ich war
        unachtsam', sondern **welche Module** ich nicht gelesen habe."""
        from research.stand import BEHOBEN

        eintrag = next(r for r in BEHOBEN if r.befund == 424)

        assert "nicht in 'verbund' und 'stand'" in eintrag.ergebnis

    def test_und_423_zeigt_nach_vorn(self) -> None:
        from research.stand import BEHOBEN

        assert next(r for r in BEHOBEN if r.befund == 423).zuletzt == 424
