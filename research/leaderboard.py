"""Die Bestenliste - jede je gepruefte Strategie, ueber alle Laeufe hinweg.

Warum es sie gibt
-----------------
Bisher war jeder Zulassungslauf für sich: eine Tabelle im Terminal, danach
weg. Wer nach zwanzig Laeufen wissen wollte, welche Idee am weitesten kam,
musste Bildschirmfotos vergleichen.

Die Bestenliste haelt fest, was ein Lauf herausgefunden hat: je Genom das
**beste je erreichte** Ergebnis, wie oft es geprueft wurde, und woran es zuletzt
scheiterte. Sie wird fortgeschrieben, nie ueberschrieben.

Warum kein einzelner Punktwert
------------------------------
Eine einzige Zahl waere bequem und falsch. Zwei Strategien mit derselben
Punktzahl koennen voellig verschiedene Dinge sein - die eine hat sechs Gates
bestanden und ist an der Bestaendigkeit gescheitert, die andere hat drei
bestanden und einen hohen Erwartungswert aus zwoelf Trades.

Sortiert wird deshalb der Reihe nach: erst danach, ob zugelassen; dann nach
der Zahl bestandener Gates; dann nach dem Erwartungswert je Trade. Jede Stufe
ist fuer sich verstaendlich, und die Tabelle zeigt alle drei.

Was ein hoher Platz nicht bedeutet
----------------------------------
Platz 1 heisst "kam am weitesten", nicht "ist profitabel". Solange die
Spalte ``zugelassen`` leer bleibt, hat **keine** Strategie die Pruefung
bestanden - egal wie die Rangfolge darunter aussieht. Diese Unterscheidung ist
der Grund, warum die Zulassung nicht am Platz haengt.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

#: Aktuelle Fassung des Dateiformats. Wird sie erhoeht, faengt die Liste neu an,
#: statt alte Eintraege falsch zu deuten.
FORMAT = 2


@dataclass(slots=True)
class Entry:
    """Eine Strategie in der Bestenliste."""

    genome_id: str
    name: str
    generation: int

    intervall: str = ""
    """Auf welcher Kerzenlaenge dieses Ergebnis gemessen wurde.

    **Es fehlte, und das war eine stille Kollision.** Die Liste ist nach
    ``genome_id`` geschluesselt, und dieselbe Regel auf Tageskerzen und auf
    Viertelstunden hat dieselbe ID. Zwei solche Ergebnisse konkurrierten
    deshalb um denselben Platz, und das schlechtere verschwand - obwohl es
    gar nicht dasselbe gemessen hatte.

    Leer heisst: aus einem Lauf, der es noch nicht mitgeschrieben hat.
    """

    kapital: float = 0.0
    """Mit welchem Startkapital dieses Ergebnis gemessen wurde.

    **Dieselbe stille Kollision wie beim Intervall, nur teurer.** Befund 96
    hat gemessen, dass zwei der elf Gates ihr Urteil aendern, wenn allein der
    Kontostand sich aendert: Rueckgang und schlechtestes Jahr. Derselbe
    Kandidat steht bei 500 EUR auf 7 von 11 und ab 1500 EUR auf 6 - die
    ``genome_id`` ist in beiden Faellen dieselbe.

    Ohne dieses Feld konkurrieren beide um denselben Platz, das
    schmeichelhaftere gewinnt, und in der Liste steht danach eine Zahl, deren
    Herkunft niemand mehr nachvollziehen kann. Genau das ist beim Intervall
    schon einmal passiert.

    Die Ursache ist Bybits Mengenschritt: Bei kleinem Konto wird die
    berechnete Menge merklich abgerundet, und das schoent ausgerechnet die
    Risikomasse (Befund 95). ``cli koernung`` rechnet es nach.

    0.0 heisst: aus einem Lauf, der es noch nicht mitgeschrieben hat.
    """

    referenzdaten: bool = False
    """Lief das Ergebnis auf Forschungskerzen statt auf Boersendaten?

    Die dritte Bedingung nach Intervall und Kontostand, und die schwerste:
    Bitstamp-Kassakurse sind nicht Bybit-Perpetuals - anderes Instrument,
    andere Boerse, keine Funding-Zahlungen. Zwei Ergebnisse darueber hinweg zu
    vergleichen hiesse, zwei verschiedene Maerkte in einen Rang zu stellen.

    ``False`` heisst hier "nicht als Forschungsmaterial erkannt", nicht
    "geprueft und in Ordnung".
    """

    herkunft: str = "Katalog"
    """Woher der Kandidat stammt: Katalog, Variante oder KI-Vorschlag."""

    geprueft: int = 0
    zuerst: str = ""
    zuletzt: str = ""

    zugelassen: bool = False
    gates_bestanden: int = 0
    gates_gesamt: int = 0
    gescheitert_an: list[str] = field(default_factory=list)

    trades: int = 0
    erwartung_r: float = 0.0
    sharpe: float = 0.0
    rendite_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    fenster_profitabel: float = 0.0
    hypothese: str = ""

    deflated_sharpe: float = 0.0
    """Wie sicher der Vorteil echt ist, nach Korrektur fuer die Zahl der
    Versuche. Die einzige Kennzahl hier, die sich nicht schoenrechnen laesst,
    indem man weniger riskiert."""

    versuche: int = 0
    """Der Versuchsstand, bei dem ``deflated_sharpe`` gemessen wurde.

    **Ohne diese Zahl vergleicht die Liste Werte gegen verschiedene Huerden.**
    Der Deflated Sharpe faellt mit jedem weiteren Versuch, auch wenn sich an
    der Regel nichts aendert - derselbe Kandidat steht in drei Abtastungen bei
    0,851 / 0,813 / 0,808, allein deshalb. Wer zwei Eintraege aus
    verschiedenen Wochen nebeneinanderlegt, vergleicht den aelteren mit einem
    Vorteil, den er nicht verdient hat.

    Null heisst: vor dieser Aenderung eingetragen, Huerde unbekannt.
    """

    sharpe_je_trade: float = 0.0
    schiefe: float = 0.0
    woelbung: float = 0.0
    """Die Eingaenge des Deflated Sharpe - damit er sich auf einen anderen
    Versuchsstand umrechnen laesst, statt nur verglichen zu werden."""

    genom: dict | None = None
    """Die Regeln selbst - damit ein gemessener Kandidat wieder rechenbar ist.

    **Sie fehlten, und das ist teurer geworden als es aussah.** Die Liste hielt
    ``genome_id``, Name und Kennzahlen fest, aber nicht die Regeln. Wer einen
    Kandidaten spaeter noch einmal rechnen wollte, brauchte die Datei, aus der
    er stammte - und die Vorschlagsdateien des Analysten (``vorschlaege.json``,
    ``sieger.json``) sind nie versioniert worden.

    Aufgefallen ist es in Befund 74: Die Partnerkarte weist 'Neues Hoch im
    Takt' als aussichtsreichsten Verbund-Partner aus, und genau der ist nicht
    mehr rechenbar. Ein Kandidat, der einmal gemessen wurde, war danach
    verloren.

    ``None`` heisst: aus einem Lauf vor dieser Aenderung. Die 45 vorhandenen
    Eintraege bleiben so - nachtraeglich erfundene Regeln waeren schlimmer als
    eine sichtbare Luecke.
    """

    @property
    def vergleichbar(self) -> bool:
        """Laesst sich der Wert auf einen anderen Versuchsstand umrechnen?"""
        return bool(self.versuche and self.sharpe_je_trade > 0 and self.trades >= 3)

    def dsr_bei(self, versuche: int) -> float:
        """Der Deflated Sharpe, wie er bei diesem Versuchsstand aussaehe.

        Ohne die noetigen Eingaenge bleibt der gespeicherte Wert stehen - eine
        Umrechnung zu erfinden waere schlimmer als eine ehrliche Luecke. Solche
        Eintraege sind ueber ``vergleichbar`` erkennbar.
        """
        if not self.vergleichbar:
            return self.deflated_sharpe
        from research.gates import deflated_sharpe_ratio

        return deflated_sharpe_ratio(
            observed_sharpe=self.sharpe_je_trade,
            trials=max(versuche, 1),
            sample_size=self.trades,
            skew=self.schiefe,
            kurtosis=self.woelbung,
        )

    @property
    def rang_schluessel(self) -> tuple:
        """Reihenfolge der Bestenliste - absteigend zu lesen.

        Bewusst mehrstufig statt als Punktwert: Jede Stufe ist fuer sich
        begruendbar, und die Tabelle kann alle zeigen.

        **Warum die Zahl bestandener Gates nicht mehr an zweiter Stelle
        steht.** Sie ist eine irrefuehrende Rangfolge, und der Fall ist
        gemessen: Derselbe Kandidat mit engerem Stop bestand 9 von 11 Gates
        statt 8 - aber nur, weil er schlicht weniger riskierte. Rueckgang,
        schlechtestes Jahr und Monte-Carlo bestanden dort durch kleinere
        Positionen, waehrend der Deflated Sharpe von 0,901 auf 0,619 fiel.

        Nach der alten Reihenfolge waere die schlechtere Strategie auf Platz
        eins gelandet, und die Bestenliste haette den Rueckschritt als
        Fortschritt ausgewiesen.

        Der Deflated Sharpe steht deshalb vor der Gate-Zahl: Er misst, wie
        sicher der Vorteil ueberhaupt echt ist, und er laesst sich **nicht**
        durch kleinere Positionen verbessern - er ist skaleninvariant. Wer
        weniger riskiert, verbessert seinen Rang damit nicht mehr.

        Die Gate-Zahl bleibt im Schluessel, aber dahinter: Zwischen zwei
        Kandidaten mit gleich belastbarem Vorteil ist der weiter, der mehr
        Pruefungen besteht.
        """
        return (
            self.zugelassen,
            round(self.deflated_sharpe, 3),
            self.gates_bestanden,
            self.erwartung_r,
            self.sharpe,
        )

    def besser_als(self, andere: Entry) -> bool:
        """Ist dieses Ergebnis besser - und ueberhaupt vergleichbar?

        Zwei Ergebnisse auf verschiedenen Kerzenlaengen sind **nicht**
        vergleichbar. Sie gegeneinander zu stellen hiesse, Regeln zu
        vergleichen, die verschiedene Zeitraeume meinen, obwohl dieselben
        Zahlen darin stehen. Fuer verschiedene Kontostaende gilt seit Befund
        96 dasselbe.
        """
        if self.vergleichbar_mit(andere):
            return self.rang_schluessel > andere.rang_schluessel
        return False

    def vergleichbar_mit(self, andere: Entry) -> bool:
        """Wurden beide unter denselben Bedingungen gemessen?

        Zwei davon zaehlen: die Kerzenlaenge und der Kontostand. Beide
        veraendern die Gate-Zahlen, ohne dass sich an der Strategie etwas
        aendert, und beide teilen sich denselben Schluessel - die
        ``genome_id``.

        Ein leerer Wert stammt aus einem Lauf vor dieser Unterscheidung. Er
        gilt als vergleichbar - sonst wuerde ein alter Eintrag von einem neuen
        nie mehr abgeloest, und die Liste fror an dieser Stelle ein.
        """
        gleiches_intervall = not self.intervall or not andere.intervall or (
            self.intervall == andere.intervall
        )
        gleiches_konto = not self.kapital or not andere.kapital or (
            self.kapital == andere.kapital
        )
        # Hier gibt es keinen Ausweg fuer alte Eintraege: ``False`` heisst
        # "nicht erkannt", und zwei nicht erkannte Eintraege stammen aus
        # derselben Zeit. Ein Eintrag auf Forschungskerzen gehoert dagegen nie
        # in denselben Rang wie einer von der Boerse.
        gleiche_quelle = self.referenzdaten == andere.referenzdaten
        return gleiches_intervall and gleiches_konto and gleiche_quelle


def _jetzt() -> str:
    return datetime.now(UTC).isoformat()


class Leaderboard:
    """Bestenliste auf der Platte, fortgeschrieben ueber alle Laeufe."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.entries: dict[str, Entry] = {}
        self.laeufe: int = 0
        self._load()

    # -- Zustand -------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            roh = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            log.error("bestenliste.unlesbar", pfad=str(self.path))
            return

        if roh.get("format") != FORMAT:
            # Lieber neu anfangen als alte Felder falsch deuten. Die Liste ist
            # eine Auswertung, keine Buchhaltung - sie laesst sich nachrechnen.
            log.warning("bestenliste.format_veraltet", gefunden=roh.get("format"))
            return

        self.laeufe = int(roh.get("laeufe", 0))
        for daten in roh.get("eintraege", []):
            try:
                self.entries[daten["genome_id"]] = Entry(**daten)
            except TypeError:
                log.warning("bestenliste.eintrag_uebersprungen", daten=daten.get("name"))

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "format": FORMAT,
                    "stand": _jetzt(),
                    "laeufe": self.laeufe,
                    "eintraege": [asdict(e) for e in self.ranked()],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return self.path

    # -- Fortschreiben -------------------------------------------------------
    def record(
        self,
        candidates,
        *,
        generation: int,
        herkunft: str = "Katalog",
        versuche: int = 0,
        intervall: str = "",
        kapital: float = 0.0,
    ) -> int:
        """Ein Laufergebnis eintragen. Gibt zurueck, wie viele sich verbessert haben.

        Ein schlechteres Ergebnis ueberschreibt kein besseres. Sonst wuerde
        eine Strategie, die einmal gut und einmal schlecht abschnitt, je nach
        Reihenfolge der Laeufe verschieden dastehen - und die Liste haette
        keinen Wert.
        """
        self.laeufe += 1
        verbessert = 0

        for candidate in candidates:
            neu = _aus_kandidat(
                candidate, generation=generation, herkunft=herkunft,
                versuche=versuche, intervall=intervall, kapital=kapital,
            )
            alt = self.entries.get(neu.genome_id)

            if alt is None:
                neu.geprueft = 1
                neu.zuerst = neu.zuletzt = _jetzt()
                self.entries[neu.genome_id] = neu
                verbessert += 1
                continue

            alt.geprueft += 1
            alt.zuletzt = _jetzt()
            if neu.besser_als(alt):
                neu.geprueft = alt.geprueft
                neu.zuerst = alt.zuerst
                neu.zuletzt = alt.zuletzt
                self.entries[neu.genome_id] = neu
                verbessert += 1

        return verbessert

    # -- Abfragen ------------------------------------------------------------
    def ranked(self, *, versuche: int | None = None) -> list[Entry]:
        """Die Liste, absteigend.

        Mit ``versuche`` wird der Deflated Sharpe jedes Eintrags auf **diesen**
        Versuchsstand umgerechnet, bevor verglichen wird. Ohne das vergleicht
        die Liste Werte, die gegen verschiedene Huerden gemessen wurden - und
        der aeltere Eintrag gewinnt mit einem Vorteil, den er nicht verdient
        hat. Eintraege ohne die noetigen Eingaenge behalten ihren Wert; sie
        sind ueber ``vergleichbar`` erkennbar.
        """
        if versuche is None:
            return sorted(
                self.entries.values(), key=lambda e: e.rang_schluessel, reverse=True
            )
        return sorted(
            self.entries.values(),
            key=lambda e: (
                e.zugelassen,
                round(e.dsr_bei(versuche), 3),
                e.gates_bestanden,
                e.erwartung_r,
                e.sharpe,
            ),
            reverse=True,
        )

    def best(self, count: int = 5, *, versuche: int | None = None) -> list[Entry]:
        return self.ranked(versuche=versuche)[:count]

    @property
    def unvergleichbar(self) -> list[Entry]:
        """Eintraege, deren Huerde unbekannt ist - vor dieser Aenderung
        eingetragen. Ihre Zahl steht, aber sie gehoert nicht in denselben
        Vergleich."""
        return [e for e in self.entries.values() if not e.vergleichbar]

    @property
    def admitted(self) -> list[Entry]:
        return [e for e in self.entries.values() if e.zugelassen]

    @property
    def kontostaende(self) -> list[float]:
        """Die verschiedenen Startkapitalien in der Liste, aufsteigend.

        Mehr als eines heisst: Hier stehen Ergebnisse nebeneinander, deren
        Risikogates gegen verschiedene Bedingungen gemessen wurden. Das ist
        nicht falsch - aber es gehoert sichtbar, weil zwei der elf Gates ihr
        Urteil daran aendern (Befund 96). Die 0.0 der alten Eintraege zaehlt
        nicht mit; sie heisst "unbekannt", nicht "null Euro".
        """
        return sorted({e.kapital for e in self.entries.values() if e.kapital})

    def summary(self) -> str:
        if not self.entries:
            return "Noch nichts geprueft."
        spitze = self.ranked()[0]
        return (
            f"{len(self.entries)} Strategien in {self.laeufe} Laeufen geprueft, "
            f"{len(self.admitted)} zugelassen. "
            f"Vorn: {spitze.name} ({spitze.gates_bestanden}/{spitze.gates_gesamt} Gates, "
            f"Erwartung {spitze.erwartung_r:+.3f} R)"
        )


def _aus_kandidat(
    candidate, *, generation: int, herkunft: str, versuche: int = 0,
    intervall: str = "", kapital: float = 0.0,
) -> Entry:
    combined = candidate.walkforward.combined
    return Entry(
        genome_id=candidate.genome.genome_id,
        name=candidate.genome.name,
        generation=generation,
        intervall=intervall,
        kapital=kapital,
        # Aus dem Gate-Bericht gelesen und nicht als weiterer Parameter
        # durchgereicht: Dort wird es ohnehin erkannt, und zwei Quellen fuer
        # dieselbe Bedingung laufen frueher oder spaeter auseinander.
        referenzdaten=bool(getattr(candidate.gates, "referenzdaten", False)),
        herkunft=herkunft,
        zugelassen=candidate.admitted,
        gates_bestanden=sum(1 for r in candidate.gates.results if r.passed),
        gates_gesamt=len(candidate.gates.results),
        gescheitert_an=[r.name for r in candidate.gates.failures],
        trades=candidate.trades,
        erwartung_r=round(combined.expectancy_r, 4) if combined else 0.0,
        sharpe=round(candidate.sharpe, 3),
        rendite_pct=round(combined.total_return_pct, 2) if combined else 0.0,
        max_drawdown_pct=round(combined.max_drawdown_pct, 2) if combined else 0.0,
        fenster_profitabel=round(candidate.consistency, 3),
        deflated_sharpe=_deflated_sharpe(candidate),
        hypothese=candidate.genome.rationale,
        versuche=versuche,
        genom=candidate.genome.model_dump(mode="json"),
        **_form(candidate),
    )


def _form(candidate) -> dict[str, float]:
    """Die Eingaenge des Deflated Sharpe - ueber **eine** Umsetzung.

    ``Kandidat.aus_trades`` rechnet sie ohnehin; sie hier noch einmal
    aufzuschreiben waere die sechste Stelle mit derselben Formel.
    """
    from research.suchbudget import Kandidat

    trades = getattr(candidate.walkforward, "all_trades", None) or []
    eintrag = Kandidat.aus_trades("", trades)
    if eintrag is None:
        return {}
    return {
        "sharpe_je_trade": round(eintrag.sharpe_je_trade, 6),
        "schiefe": round(eintrag.schiefe or 0.0, 4),
        "woelbung": round(eintrag.woelbung or 0.0, 4),
    }


def _deflated_sharpe(candidate) -> float:
    """Den Deflated Sharpe aus den Gate-Ergebnissen holen.

    Er wird dort ohnehin berechnet - ihn hier ein zweites Mal zu rechnen
    hiesse, zwei Quellen fuer dieselbe Zahl zu haben, die auseinanderlaufen
    koennen.

    Wurde das Gate uebersprungen (zu wenige Trades), bleibt der Wert null.
    Das ist die richtige Richtung: Ein Kandidat, ueber dessen Belastbarkeit
    sich nichts sagen laesst, steht nicht vor einem, ueber den etwas bekannt
    ist.
    """
    for ergebnis in candidate.gates.results:
        if ergebnis.name == "Deflated Sharpe":
            return round(float(ergebnis.value), 4)
    return 0.0
