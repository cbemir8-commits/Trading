"""Die sechste Eingabe des Deflated Sharpe - die einzige, die geraten wird.

Zwei Tests tragen diese Datei:

``test_die_gemessene_streuung_wird_nicht_eingesetzt`` - Die Zahl aus den
eigenen Berichten wuerde das strengste Gate des Projekts von durchgefallen auf
bestanden drehen. Genau deshalb steht hier ein Test, der verlangt, dass das
Gate sie **nicht** benutzt. Eine Auswahl der eigenen Versuche darf die Huerde
nicht senken.

``test_der_kippunkt_liegt_zwischen_den_schaetzungen`` - Warum die Sache
ueberhaupt zaehlt: Zwischen der Annahme und dem, was aus den Berichten
herauskaeme, liegt das Urteil. Waere der Abstand gross, waere die Annahme
unkritisch; er ist klein.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.gates import GateStatus, GateThresholds, deflated_sharpe_ratio
from research.streuung import (
    MINDESTABDECKUNG,
    Empfindlichkeit,
    Streuung,
    Versuchspunkt,
    aus_berichten,
    aus_bestenliste,
    aus_verzeichnis,
    sammle,
)
from research.versuche import Versuch, Verzeichnis, speichern
from tests.test_gates import make_trade

#: Der Spitzenkandidat, wie er in ``reports/machbarkeit`` steht.
SPITZE = {"sharpe": 0.2618, "stichprobe": 152, "versuche": 166}
FORM = {"schiefe": 3.3981, "woelbung": 15.4821}


def bericht(ordner: Path, *, regler: str, sharpes: list[float], name: str) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / name
    datei.write_text(
        json.dumps(
            {
                "regler": regler,
                "punkte": [
                    {
                        "stellung": float(i),
                        "kennzahlen": {"trades": 152.0, "sharpe_je_trade": s},
                    }
                    for i, s in enumerate(sharpes)
                ],
            }
        )
    )
    return datei


def bestenliste(pfad: Path, sharpes: list[float | None]) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(
            {
                "eintraege": [
                    {"name": f"Kandidat {i}", "sharpe_je_trade": s}
                    for i, s in enumerate(sharpes)
                ]
            }
        )
    )
    return pfad


def punkte(*werte: float, quelle: str = "Berichte") -> list[Versuchspunkt]:
    return [
        Versuchspunkt(quelle=quelle, kennung=f"p{i}", sharpe_je_trade=w)
        for i, w in enumerate(werte)
    ]


class TestSammeln:
    def test_punkte_aus_unterordnern_werden_gefunden(self, tmp_path: Path) -> None:
        """Die Berichtsarten liegen in Unterordnern. Sie hier aufzuzaehlen
        hiesse, jede neue Sorte zu vergessen."""
        bericht(tmp_path / "machbarkeit", regler="Stop", sharpes=[0.2], name="a.json")
        bericht(
            tmp_path / "marktkombinationen", regler="Koerbe", sharpes=[0.1],
            name="b.json",
        )

        assert len(aus_berichten(tmp_path)) == 2

    def test_punkte_ohne_sharpe_werden_uebersprungen(self, tmp_path: Path) -> None:
        ordner = tmp_path / "machbarkeit"
        datei = bericht(ordner, regler="Stop", sharpes=[0.2], name="a.json")
        daten = json.loads(datei.read_text())
        daten["punkte"].append({"stellung": 9.0, "kennzahlen": {"trades": 100.0}})
        datei.write_text(json.dumps(daten))

        assert len(aus_berichten(tmp_path)) == 1

    def test_die_kennung_nennt_regler_und_stellung(self, tmp_path: Path) -> None:
        bericht(tmp_path, regler="Vola-Ziel", sharpes=[0.2], name="a.json")

        assert aus_berichten(tmp_path)[0].kennung == "Vola-Ziel 0"

    def test_kaputte_datei_kippt_nicht_den_lauf(self, tmp_path: Path) -> None:
        (tmp_path / "kaputt.json").write_text("{kein JSON")
        bericht(tmp_path, regler="Stop", sharpes=[0.2], name="gut.json")

        assert len(aus_berichten(tmp_path)) == 1

    def test_fehlender_ordner_gibt_nichts(self, tmp_path: Path) -> None:
        assert aus_berichten(tmp_path / "gibt-es-nicht") == []
        assert aus_bestenliste(tmp_path / "gibt-es-nicht.json") == []

    def test_eintraege_ohne_erhobenen_sharpe_bleiben_draussen(
        self, tmp_path: Path
    ) -> None:
        """``0.0`` heisst in der Bestenliste "nicht erhoben" und nicht "kein
        Vorteil". Es mitzuzaehlen wuerde die Streuung genau dort faelschen, wo
        sie am meisten weh tut."""
        bestenliste(tmp_path / "leaderboard.json", [0.25, 0.0, None, 0.03])

        werte = [p.sharpe_je_trade for p in aus_bestenliste(tmp_path / "leaderboard.json")]
        assert werte == [0.25, 0.03]

    def test_beide_quellen_werden_zusammengelegt(self, tmp_path: Path) -> None:
        bericht(tmp_path / "r", regler="Stop", sharpes=[0.2], name="a.json")
        bestenliste(tmp_path / "leaderboard.json", [0.03])

        gesammelt = sammle(
            berichte=tmp_path / "r", bestenliste=tmp_path / "leaderboard.json"
        )
        assert {p.quelle for p in gesammelt} == {"Berichte", "Bestenliste"}

    def test_das_verzeichnis_kommt_dazu(self, tmp_path: Path) -> None:
        """Die einzige Quelle, die vollstaendig werden **kann**: Sie bekommt
        jeden geprueften Kandidaten, auch den, der nichts taugte."""
        speichern(
            tmp_path / "trials.json",
            Verzeichnis(
                grundstock=166,
                eintraege=[
                    Versuch("A", sharpe_je_trade=0.21),
                    Versuch("B", sharpe_je_trade=None),
                ],
            ),
        )

        gefunden = aus_verzeichnis(tmp_path / "trials.json")
        assert [p.kennung for p in gefunden] == ["A"]
        assert gefunden[0].quelle == "Verzeichnis"

    def test_der_grundstock_liefert_keine_punkte(self, tmp_path: Path) -> None:
        """166 Versuche ohne Einzelnachweis bleiben ohne Einzelnachweis -
        Platzhalter wuerden die Luecke unsichtbar machen."""
        (tmp_path / "trials.json").write_text(json.dumps({"trials": 166}))

        assert aus_verzeichnis(tmp_path / "trials.json") == []

    def test_ein_unlesbares_verzeichnis_kippt_die_auswertung_nicht(
        self, tmp_path: Path
    ) -> None:
        """Hier ist ein Ausfall harmlos: Fehlende Punkte machen die Schaetzung
        schmaler, und schmaler heisst hier "wird nicht verwendet". Im Gate
        waere dieselbe Toleranz falsch - dort bricht der Lauf ab."""
        (tmp_path / "trials.json").write_text("{kaputt")

        assert aus_verzeichnis(tmp_path / "trials.json") == []


class TestStreuung:
    def test_die_annahme_ist_die_wurzel_aus_eins_durch_n_minus_eins(self) -> None:
        """Genau der Wert, der in ``gates.py`` als Ersatz einspringt - eine
        zweite Rechnung waere eine zweite Meinung darueber, wogegen hier
        verglichen wird."""
        s = Streuung(punkte=punkte(0.1, 0.3), versuche=10, stichprobe=152)

        assert s.angenommen == pytest.approx((1 / 151) ** 0.5)

    def test_ohne_stichprobe_gibt_es_keine_annahme(self) -> None:
        assert Streuung(punkte=punkte(0.1, 0.3), versuche=10).angenommen is None

    def test_ein_einzelner_punkt_hat_keine_streuung(self) -> None:
        assert Streuung(punkte=punkte(0.2), versuche=10).gemessen is None

    def test_abdeckung_und_fehlende_haengen_am_versuchszaehler(self) -> None:
        s = Streuung(punkte=punkte(0.1, 0.2, 0.3), versuche=30)

        assert s.abdeckung == pytest.approx(0.1)
        assert s.fehlend == 27

    def test_mehrfach_gezaehlte_mitte_wird_benannt(self) -> None:
        """Jeder Reglerscan misst auf seiner neutralen Stellung den Bestand.
        In den echten Berichten steht 0,2597 dreimal."""
        s = Streuung(punkte=punkte(0.26, 0.26, 0.26, 0.13), versuche=100)

        assert s.mehrfach == 2

    def test_die_streuung_bleibt_unbereinigt(self) -> None:
        """Die Mehrfachnennungen zu entfernen wuerde die Schaetzung **nach
        oben** ziehen, also in die Richtung, die dem eigenen Argument nutzt.
        Der ungebeugte Wert traegt es auch."""
        mit_doppelten = Streuung(punkte=punkte(0.26, 0.26, 0.26, 0.13), versuche=100)
        ohne = Streuung(punkte=punkte(0.26, 0.13), versuche=100)

        assert mit_doppelten.gemessen is not None and ohne.gemessen is not None
        assert mit_doppelten.gemessen < ohne.gemessen


class TestVerwendbarkeit:
    def test_eine_auswahl_ist_keine_streuung_ueber_die_versuche(self) -> None:
        s = Streuung(punkte=punkte(0.1, 0.2, 0.3), versuche=166, stichprobe=152)

        assert s.abdeckung < MINDESTABDECKUNG
        assert not s.verwendbar

    def test_bei_voller_abdeckung_waere_sie_es(self) -> None:
        """Die Schwelle ist kein Riegel fuer immer. Wer die Versuche
        aufschreibt, macht die Groesse messbar - erst dann ist die Frage, ob
        das Gate sie benutzen soll, ueberhaupt eine Frage."""
        s = Streuung(punkte=punkte(*[0.1 * i for i in range(10)]), versuche=10)

        assert s.verwendbar

    def test_das_urteil_nennt_richtung_und_grund(self) -> None:
        s = Streuung(punkte=punkte(0.24, 0.25, 0.26), versuche=166, stichprobe=152)
        urteil = s.urteil()

        assert "Nicht verwendbar" in urteil
        assert "zu klein" in urteil
        assert "strengere Richtung" in urteil
        assert "trials.json" in urteil

    def test_auch_ein_verwendbarer_wert_ist_keine_freigabe(self) -> None:
        """Die Annahme durch die Messung zu ersetzen senkt eine Huerde. Diese
        Entscheidung faellt nicht in einer Auswertung."""
        s = Streuung(punkte=punkte(*[0.1 * i for i in range(10)]), versuche=10,
                     stichprobe=152)

        assert "keine Freigabe" in s.urteil()

    def test_ohne_punkte_wird_nichts_behauptet(self) -> None:
        assert "nichts sagen" in Streuung(versuche=166).urteil()


class TestJeQuelle:
    def test_reglerscans_streuen_enger_als_der_rest(self) -> None:
        """**Das Argument als Messung.** Punkte um den Bestand herum liegen
        naturgemaess eng beieinander; strukturell andere Familien nicht. Wer
        nur die eine Sorte hat, misst die Enge seiner Auswahl."""
        s = Streuung(
            punkte=punkte(0.24, 0.25, 0.26, quelle="Berichte")
            + punkte(0.03, 0.05, 0.25, quelle="Bestenliste"),
            versuche=166,
        )
        je = s.je_quelle()

        assert je["Berichte"][1] < je["Bestenliste"][1]

    def test_mehr_quellen_heben_die_schaetzung(self) -> None:
        nur_scans = Streuung(punkte=punkte(0.24, 0.25, 0.26), versuche=166)
        mit_rest = Streuung(
            punkte=punkte(0.24, 0.25, 0.26) + punkte(0.03, 0.05, quelle="Bestenliste"),
            versuche=166,
        )

        assert nur_scans.gemessen is not None and mit_rest.gemessen is not None
        assert mit_rest.gemessen > nur_scans.gemessen

    def test_eine_breitere_einzelquelle_widerlegt_die_zusammenlegung(self) -> None:
        """**Das staerkste Einzelargument.**

        Streut schon eine einzelne Quelle breiter als die Annahme, ist nicht
        die Annahme zu hoch, sondern die Zusammenlegung zu schmal - die engste
        Quelle stellt die meisten Punkte. In den echten Daten ist es so: die
        Bestenliste kommt auf 0,1030, die Annahme auf 0,0808.
        """
        s = Streuung(
            punkte=punkte(0.24, 0.25, 0.26)
            + punkte(0.03, 0.05, 0.25, quelle="Bestenliste"),
            versuche=166,
            stichprobe=152,
        )
        breiteste = s.breiteste

        assert breiteste is not None
        assert breiteste[0] == "Bestenliste"
        assert s.angenommen is not None and breiteste[1] > s.angenommen
        assert "breiter als die Annahme" in s.urteil()

    def test_ohne_breitere_quelle_bleibt_der_satz_weg(self) -> None:
        """Er ist ein Befund, kein Ausschmueckung - ohne Deckung faellt er
        weg."""
        s = Streuung(punkte=punkte(0.25, 0.26), versuche=166, stichprobe=152)

        assert "breiter als die Annahme" not in s.urteil()

    def test_die_tabelle_zeigt_jede_quelle_und_die_summe(self) -> None:
        s = Streuung(
            punkte=punkte(0.24, 0.26) + punkte(0.03, 0.05, quelle="Bestenliste"),
            versuche=166,
        )
        text = s.tabelle()

        assert "Berichte" in text
        assert "Bestenliste" in text
        assert "zusammen" in text


class TestEmpfindlichkeit:
    def empfindlichkeit(self) -> Empfindlichkeit:
        return Empfindlichkeit(**SPITZE, **FORM)

    def test_mehr_streuung_senkt_den_deflated_sharpe(self) -> None:
        e = self.empfindlichkeit()

        assert e.bei(0.12) < e.bei(0.04)

    def test_der_kippunkt_liegt_zwischen_den_schaetzungen(self) -> None:
        """**Der Test, der diese Datei traegt.**

        Die Annahme im Gate ist 0,0814, aus den Berichten kaeme etwa 0,043.
        Laege der Kippunkt ausserhalb dieser Spanne, waere die ungemessene
        Eingabe eine Randnotiz. Er liegt dazwischen - deshalb ist sie es
        nicht.
        """
        e = self.empfindlichkeit()
        kipp = e.kippunkt()

        assert kipp is not None
        assert 0.043 < kipp < (1 / 151) ** 0.5
        assert e.bei(kipp * 0.99) >= e.ziel
        assert e.bei(kipp * 1.01) < e.ziel

    def test_ohne_umschlag_gibt_es_keinen_kippunkt(self) -> None:
        """Ein Kandidat, der auch bei winziger Streuung durchfaellt, hat
        keinen Kippunkt - und darf keinen vorgetaeuscht bekommen."""
        schwach = Empfindlichkeit(sharpe=0.02, stichprobe=152, versuche=166)

        assert schwach.kippunkt() is None

    def test_das_urteil_nennt_kippunkt_und_abstand(self) -> None:
        e = self.empfindlichkeit()
        urteil = e.urteil((1 / 151) ** 0.5)

        assert "kippt bei" in urteil
        assert "durchgefallen" in urteil
        assert "nie gemessen" in urteil

    def test_die_tabelle_stellt_die_schaetzungen_nebeneinander(self) -> None:
        e = self.empfindlichkeit()
        text = e.tabelle({"angenommen": 0.0814, "aus Berichten": 0.0428})

        assert "durchgefallen" in text
        assert "bestanden" in text


class TestDasGateBleibtStreng:
    def test_die_gemessene_streuung_wird_nicht_eingesetzt(self) -> None:
        """**Der Test, der dieses Modul absichert.**

        Die Streuung aus den eigenen Berichten wuerde den Spitzenkandidaten
        von 0,80 auf 0,99 heben und damit das Gate drehen, an dem das Projekt
        seit Wochen haengt. Das Gate rechnet weiter mit der Ersatzannahme -
        und dieser Test verlangt es, damit die Versuchung nicht eines Tages
        als Verbesserung durchgeht.
        """
        aus_berichten_geschaetzt = 0.0428
        eingaben = {
            "observed_sharpe": SPITZE["sharpe"],
            "trials": SPITZE["versuche"],
            "sample_size": SPITZE["stichprobe"],
            "skew": FORM["schiefe"],
            "kurtosis": FORM["woelbung"],
        }
        mit_annahme = deflated_sharpe_ratio(**eingaben)
        mit_auswahl = deflated_sharpe_ratio(
            **eingaben, sharpe_variance=aus_berichten_geschaetzt**2
        )
        schwelle = GateThresholds().min_deflated_sharpe

        assert mit_annahme < schwelle, "Sonst prueft der Test nichts"
        assert mit_auswahl > schwelle, "Sonst waere die Versuchung keine"

    def test_das_gate_reicht_keine_streuung_herein(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nicht die Formel wird geprueft, sondern der **Aufruf**.

        Geprueft wird hier und nicht in ``test_gates``, weil die Versuchung
        hier steht: Wer das Modul nebenan liest, sieht eine gemessene Zahl und
        eine Formel, die sie annimmt. Der Test faengt genau den Handgriff ab,
        der beides verbindet.
        """
        from research import gates

        gesehen: dict[str, object] = {}
        echt = gates.deflated_sharpe_ratio

        def merken(**kwargs):
            gesehen.update(kwargs)
            return echt(**kwargs)

        monkeypatch.setattr(gates, "deflated_sharpe_ratio", merken)
        trades = [
            make_trade("3.0" if i % 3 == 0 else "-1.0", hours_offset=i * 24, index=i)
            for i in range(60)
        ]
        ergebnis = gates.gate_deflated_sharpe(trades, 166, GateThresholds())

        assert ergebnis.status is not GateStatus.SKIP, "Sonst prueft der Test nichts"
        assert gesehen, "Das Gate hat die Formel gar nicht aufgerufen"
        assert gesehen.get("sharpe_variance") is None
