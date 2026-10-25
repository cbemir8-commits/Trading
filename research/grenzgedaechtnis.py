"""Die Risikogrenzen verlieren je Fenster ihre Vorgeschichte.

Woher die Frage kommt
---------------------
Befund 400 hat gemessen, dass der durchgehende Modus 98 fertige Trades hat und
der Modus der Zulassung 156, und daraus eine Erklaerung **geschlossen**: Rund
58 seien Grenzartefakte, Positionen, die am Fensterende geschlossen und danach
neu eroeffnet werden. Befund 403 hat diese Erklaerung nachgemessen, und sie ist
falsch:

* **Kein einziger** Trade steigt an einem Fensterende aus. Die Austrittsgruende
  der 158 rohen Trades sind ``signal_exit`` 78, ``stop_loss`` 68,
  ``take_profit`` 10, ``end_of_data`` 2 - einen Grund "Fensterende" gibt es
  nicht.
* **Null** zerschnittene Paare: kein Austritt an einer Fenstergrenze mit
  Wiedereinstieg binnen zwei Tagen.
* Die Einstiege haeufen sich an **keinem** Fensteranfang: am ersten Tag eines
  Fensters beginnt in beiden Modi kein Trade, 150 der 158 beginnen am sechsten
  Tag oder spaeter.
* Und die Differenz ist **nicht grenzlokal, sondern kumulativ**: Die Fenster 0
  bis 7 liefern in beiden Modi genau dieselben Trade-Zahlen (4, 8, 1, 2, 12, 3,
  3, 8), ab Fenster 8 laeuft es auseinander, und im letzten Fenster stehen 6
  gegen 1.

Was es wirklich ist
-------------------
Ohne Risikogrenzen geben **beide Modi dieselbe Zahl**:

    Lauf                        Trades    CAGR   Rueckgang
    je Fenster, mit Limits         158  14,3391      9,869
    durchgehend, mit Limits         99  11,6275      7,504
    durchgehend, ohne Limits       162  19,0053     11,216
    je Fenster, ohne Limits        162  14,1915      9,869

Die ganze Differenz sind die **Risikogrenzen**. Im durchgehenden Modus
unterdruecken sie 63 der 162 Trades, im Modus der Zulassung **vier**. Der
Grund steht in den Logzeilen des Laufs: ``risk.ohne_vorgeschichte_simuliert
kapital=500``. Jedes Fenster ist ein eigener Backtest, der bei der
Anfangseinlage und **ohne Equity-Vorgeschichte** beginnt - und Kill-Switch und
Wochenverlustgrenze brauchen eine Vorgeschichte, um zu greifen. In einem
Dreimonatsfenster kommt sie kaum zustande.

Was das heisst
--------------
**Die Zulassungsstrecke misst einen Kandidaten, dessen Risikogrenzen praktisch
nicht greifen.** ``enforce_risk_limits=True`` steht in der Konfiguration, und
es ist nicht falsch - es wirkt nur fast nicht. Das ist eine Eigenschaft des
Messaufbaus, nicht der Strategie.

Und die Richtung ist unangenehm: Es **schmeichelt** dem Kandidaten. Mit
greifenden Grenzen steht die Jahresrendite bei 11,6275 statt 14,3391 und der
Deflated Sharpe bei 0,3185 statt 0,5826.

Zwei Wirkungen, getrennt
------------------------
* **Die Trade-Zahl** haengt allein an den Grenzen: ohne sie 162 in beiden Modi.
* **Die Rendite bei gleicher Trade-Zahl** haengt an der Aufteilung: ohne
  Grenzen 14,1915 je Fenster gegen 19,0053 durchgehend. Jedes Fenster startet
  bei der Anfangseinlage, also verzinst sich nichts ueber die Grenze hinweg.

Das Kreuz je Gate (Befund 404)
------------------------------
Dieselben vier Laeufe, aber Gate fuer Gate. ``f`` ist je Fenster, ``d``
durchgehend, ``+L`` mit Risikogrenzen, ``-L`` ohne:

    Gate                         f+L       f-L       d+L       d-L
    Stichprobengroesse     + 2250,000 + 2256,000 + 1297,000 + 2256,000
    Messlatte              -   14,339 -   14,192 -   11,627 +  302,090
    Out-of-Sample-Sharpe   +    1,576 +    1,561 +    1,408 +    1,529
    Drawdown               +    9,869 +    9,869 +    7,504 +   11,216
    Schlechtestes Jahr     +   -9,610 +   -9,610 +   -5,580 -  -10,940
    Bestaendigkeit         +    0,581 +    0,581 +    0,645 +    0,581
    Monte-Carlo            +    8,326 +    8,621 -   15,536 -   22,816
    Regime-Aufteilung      +    5,275 +    5,130 +    3,026 +    3,946
    Deflated Sharpe        -    0,583 -    0,592 -    0,318 -    0,685
    Kosten-Stress          + 1863,726 + 1863,726 + 1863,726 + 1863,726
    Parameter-Plateau      +    1,000 +    1,000 +    1,000 +    1,000
    bestanden                      9         9         8         8
    fertige Trades               156       160        98       160

**Je Fenster aendern die Grenzen am Gate-Bild nichts.** Dieselben neun
bestandenen, dieselbe Fehlliste, dieselbe Rueckgangszahl auf drei Stellen -
die Inertheit aus diesem Befund, von der Gate-Seite bestaetigt.

**Durchgehend aendern sie viel.** Ohne Grenzen faellt 'Schlechtestes Jahr' auf
-10,940 statt -5,580 und der Rueckgang steigt von 7,504 auf 11,216: Die
Grenzen schuetzen messbar - wenn sie greifen koennen.

**Acht der elf Urteile sind in allen vier Zellen dieselben**, drei wechseln
(Messlatte, Schlechtestes Jahr, Monte-Carlo). Und der **Deflated Sharpe faellt
in allen vier** - 0,583 / 0,592 / 0,318 / 0,685, in der guenstigsten Zelle
fehlen noch 0,265. Mit den Befunden 401 und 402 zusammen: Der Hauptblocker
haengt weder an der Aufteilung noch am Messaufbau.

Was nicht folgt
---------------
**Nicht**, dass der Modus zu wechseln ist. Welcher Modus die Zulassung tragen
soll, aendert jede Zahl dieses Projekts und ist eine Entscheidung des Nutzers
(so steht es seit Befund 400). Dieser Befund aendert nur den Grund, aus dem die
Frage gestellt wird: Es geht nicht um zwei gleichberechtigte Messweisen,
sondern darum, dass in der einen eine eingebaute Schutzvorrichtung fast nie
anspricht.

**Nicht**, dass die Grenzen falsch gebaut sind. Sie brauchen eine
Vorgeschichte, und das ist richtig - ein Kill-Switch ohne Historie waere
willkuerlich. Fehlt die Historie, ist das eine Aussage ueber den Aufbau, der
sie nicht liefert.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "FENSTERPROBEN",
    "GEMESSEN",
    "LEITER",
    "MASSFAKTOREN",
    "QUARTALSPROBE",
    "R_PROBE",
    "SKALENPROBE",
    "Fensterprobe",
    "Grenzlauf",
    "Grenzvergleich",
    "Massfaktor",
    "Quartalsprobe",
    "bindend",
    "erfuellung_je_mass",
    "vorsprung_je_mass",
]


@dataclass(frozen=True, slots=True)
class Grenzlauf:
    """Ein Lauf mit oder ohne Risikogrenzen, je Fenster oder durchgehend."""

    durchgehend: bool
    limits: bool
    trades: int
    cagr_pct: float
    rueckgang_pct: float

    @property
    def name(self) -> str:
        return (
            f"{'durchgehend' if self.durchgehend else 'je Fenster'}, "
            f"{'mit' if self.limits else 'ohne'} Limits"
        )


@dataclass(frozen=True, slots=True)
class Grenzvergleich:
    """Vier Laeufe - und was sich zwischen ihnen zeigt."""

    laeufe: tuple[Grenzlauf, ...]

    def hole(self, *, durchgehend: bool, limits: bool) -> Grenzlauf:
        for lauf in self.laeufe:
            if lauf.durchgehend == durchgehend and lauf.limits == limits:
                return lauf
        raise KeyError(
            f"kein Lauf mit durchgehend={durchgehend}, limits={limits}"
        )

    def unterdrueckt(self, *, durchgehend: bool) -> int:
        """Wie viele Trades die Grenzen in diesem Modus unterdruecken."""
        return self.hole(durchgehend=durchgehend, limits=False).trades - self.hole(
            durchgehend=durchgehend, limits=True
        ).trades

    @property
    def greifen_je_fenster(self) -> bool:
        """Greifen die Grenzen im Modus der Zulassung ueberhaupt?

        Gemessen vier gegen 63 Trades - die Antwort ist "kaum", und die
        Schwelle dafuer ist bewusst grosszuegig: Ein Zehntel dessen, was sie
        durchgehend unterdruecken, waere noch Wirkung.
        """
        return self.unterdrueckt(durchgehend=False) >= (
            self.unterdrueckt(durchgehend=True) / 10
        )

    @property
    def renditeunterschied_ohne_limits(self) -> float:
        """Was die Aufteilung allein macht - bei gleicher Trade-Zahl."""
        return (
            self.hole(durchgehend=True, limits=False).cagr_pct
            - self.hole(durchgehend=False, limits=False).cagr_pct
        )


#: Die vier Laeufe aus Befund 403. Spot-Punkt, Zulassungsreihe, 32 Fenster.
GEMESSEN: Grenzvergleich = Grenzvergleich(
    laeufe=(
        Grenzlauf(
            durchgehend=False, limits=True, trades=158,
            cagr_pct=14.3391, rueckgang_pct=9.869,
        ),
        Grenzlauf(
            durchgehend=True, limits=True, trades=99,
            cagr_pct=11.6275, rueckgang_pct=7.504,
        ),
        Grenzlauf(
            durchgehend=True, limits=False, trades=162,
            cagr_pct=19.0053, rueckgang_pct=11.216,
        ),
        Grenzlauf(
            durchgehend=False, limits=False, trades=162,
            cagr_pct=14.1915, rueckgang_pct=9.869,
        ),
    )
)


#: Die Gate-Zahlen derselben vier Laeufe - Befund 404.
#:
#: **Achtung, zwei Trade-Zahlen.** ``GEMESSEN`` zaehlt die **rohen** Trades
#: (158 / 162 / 99 / 162), diese Tafel die **fertigen** nach Randschnitt
#: (156 / 160 / 98 / 160). Beide sind richtig, und sie zu verwechseln ist der
#: Fehler aus Befund 371.
GATEKREUZ: dict[tuple[bool, bool], tuple[str, ...]] = {
    # (durchgehend, limits) -> gefallene Gates
    (False, True): ("Messlatte", "Deflated Sharpe"),
    (False, False): ("Messlatte", "Deflated Sharpe"),
    (True, True): ("Messlatte", "Monte-Carlo", "Deflated Sharpe"),
    (True, False): ("Schlechtestes Jahr", "Monte-Carlo", "Deflated Sharpe"),
}

#: Die Gates, deren Urteil in **allen vier** Zellen dasselbe ist.
STANDHAFT: tuple[str, ...] = (
    "Stichprobengroesse",
    "Out-of-Sample-Sharpe",
    "Drawdown",
    "Bestaendigkeit",
    "Regime-Aufteilung",
    "Deflated Sharpe",
    "Kosten-Stress",
    "Parameter-Plateau",
)

#: Die Gates, deren Urteil am Messaufbau haengt.
WACKELIG: tuple[str, ...] = (
    "Messlatte",
    "Schlechtestes Jahr",
    "Monte-Carlo",
)


def haengt_am_aufbau(gate: str) -> bool:
    """Haengt das Urteil dieses Gates am Messaufbau (Modus x Grenzen)?

    Gemessen ueber das Kreuz aus Befund 404: **Acht** der elf Urteile sind in
    allen vier Zellen dieselben, **drei** wechseln.

    * ``Messlatte`` faellt in drei Zellen und besteht in der vierten
      (durchgehend ohne Grenzen) - dort meldet sie 302,090 gegen 61,470, also
      die Gesamtrendite gegen die heruntergefahrene Messlatte (Befund 395).
    * ``Schlechtestes Jahr`` besteht in drei Zellen und faellt durchgehend
      ohne Grenzen mit -10,940. **Das ist die Schutzwirkung der Grenzen,
      sichtbar gemacht**: Mit ihnen -5,580, ohne sie -10,940.
    * ``Monte-Carlo`` besteht in beiden Fenster-Zellen (8,326 / 8,621) und
      faellt in beiden durchgehenden (15,536 / 22,816, Schwelle 15). Dieses
      Urteil haengt also an der **Aufteilung**, nicht an den Grenzen.

    Und der **Deflated Sharpe faellt in allen vier Zellen** - 0,583, 0,592,
    0,318, 0,685. Selbst in der guenstigsten fehlen 0,265. Zusammen mit den
    Befunden 401 und 402 heisst das: Der Hauptblocker haengt weder an der
    Aufteilung noch am Messaufbau.
    """
    return gate in WACKELIG


@dataclass(frozen=True, slots=True)
class Kontoprobe:
    """Haette das **Konto** ausgeloest - auf einer Kurve ohne gebremste Beine?

    **Befund 406, und er korrigiert die Lesart von 403 bis 405.**

    ``research/kontorisiko.py`` hat laengst gemessen, dass die Verlustgrenzen
    je **Bein** auf eigener Kapitalbasis greifen und ein Konto mit beiden
    Maerkten nichts ausgeloest haette. Es nennt dazu selbst einen Vorbehalt:
    Die Kontokurve entsteht aus Beinen, die ihre eigenen Limits gesehen haben -
    wo das Konto frueher gebremst haette, haetten die Beine danach anders
    gehandelt.

    Mit ``enforce_risk_limits=False`` je Bein entfaellt der Vorbehalt: Dann
    bremst kein Bein, und die Kontokurve ist die, die ein Aufbau mit
    **Kontogrenze statt Beingrenze** tatsaechlich erzeugt. Gemessen am
    Spot-Punkt, durchgehend, 500 EUR auf zwei Beine:

        Beine        BTC         ETH    Summe   Kontokurve   Officer
        gebremst   18 Tr.      81 Tr.      99      10,00 %   loest nichts aus
        frei       81 Tr.      81 Tr.     162      10,77 %   loest nichts aus

    Der Kill-Switch liegt bei 15 %, das Drawdown-Gate bei 12 %. **Auf keiner
    der beiden Kurven haette das Konto etwas ausgeloest**, und auf der freien
    Kurve ist das eine Aussage ohne Vorbehalt.

    Was daraus folgt
    ----------------
    Die **63** Trades, die Befund 403 im durchgehenden Modus als unterdrueckt
    gemessen hat, sind von einer Sperre unterdrueckt, die ein Konto nie
    gesehen haette - genau das Artefakt, das ``kontorisiko`` beschreibt (dort
    am Perpetual-Punkt mit 58 von 76 Trades, hier am Spot-Punkt mit 63 von
    162). Die Zelle "durchgehend, mit Limits" aus Befund 404 - 99 Trades, 8
    von 11, DSR 0,3185 - beschreibt deshalb **zwei getrennte Konten**, nicht
    das eine, das es gibt.

    Der betriebsnahe Punkt **mit Kontogrenze** ist damit die Zelle
    "durchgehend, ohne Beingrenzen": 162 Trades, Jahresrendite 19,0053,
    Rueckgang 11,216, **8 von 11** Gates, DSR 0,685 - gefallen sind
    'Schlechtestes Jahr' (-10,940), 'Monte-Carlo' (22,816) und der Deflated
    Sharpe.

    Was das **nicht** heisst
    ------------------------
    Nicht, dass der Kandidat besser dasteht als gemeldet. Es sind weiter 8
    von 11, der Deflated Sharpe fehlt weiter um 0,265, und 'Schlechtestes
    Jahr' faellt hier zusaetzlich. Die Korrektur verschiebt **welche** Gates
    offen sind, nicht ob genug offen ist.

    Und nicht, dass die Beingrenzen abzuschalten waeren. Gemessen ist, dass
    sie an dieser Stelle das Risiko zweier Konten beschreiben; was im Betrieb
    gelten soll, ist eine Entscheidung des Nutzers - so wie die Modusfrage aus
    Befund 400.
    """

    beine_gebremst: bool
    trades: int
    kontorueckgang_pct: float
    haette_ausgeloest: bool

    @property
    def unter_dem_killswitch(self) -> bool:
        """Liegt der Kontorueckgang unter der Kill-Switch-Grenze von 15 %?"""
        return self.kontorueckgang_pct < 15.0

    @property
    def unter_dem_gate(self) -> bool:
        """Und unter der Drawdown-Schwelle des Gates von 12 %?"""
        return self.kontorueckgang_pct < 12.0


#: Die beiden Kontoproben aus Befund 406.
KONTOPROBEN: tuple[Kontoprobe, ...] = (
    Kontoprobe(
        beine_gebremst=True, trades=99, kontorueckgang_pct=10.00,
        haette_ausgeloest=False,
    ),
    Kontoprobe(
        beine_gebremst=False, trades=162, kontorueckgang_pct=10.77,
        haette_ausgeloest=False,
    ),
)


@dataclass(frozen=True, slots=True)
class Reichweite:
    """Wie weit es an **diesem** Punkt noch ist - Befund 407.

    Die Planungszahl des Projekts ("190 Beobachtungen, 5,89 Jahre") steht auf
    dem gemeldeten Punkt. Befund 406 hat einen zweiten benannt: den mit
    Kontogrenze statt Beingrenze. Gerechnet mit den Werkzeugen des Projekts -
    ``gates.stichprobe_wie_im_gate``, ``erreichbarkeit`` und ``erfuellung``:

        Groesse                     gemeldet   kontogeschuetzt
        fertige Trades                   156               160
        n_eff                            115               159
        Designfaktor                  0,7372            0,9938
        Guete je Trade                0,2708            0,2444
        Deflated Sharpe               0,5826            0,6846
        Luecke zum Gate               0,3674            0,2654
        noetige wirksame Trades          191               244
        davon fehlen                      76                85
        noetige Guete                 0,3374            0,2945
        Erfuellungsgrad               0,8026            0,8299

    **Der Designeffekt verschwindet fast.** 159 von 160 statt 115 von 156: Im
    gemeldeten Modus werden 27 % der Trades als abhaengig abgeschrieben, im
    durchgehenden unter 1 %. Positionen ueberleben dort die Fenstergrenze, also
    finden die Einteilungen nach Fenstern und nach Gleichzeitigkeit viel
    weniger Abhaengigkeit. Umgekehrt gelesen: Die hoehere Guete des gemeldeten
    Punkts (0,2708 gegen 0,2444) ist mit einem viel groesseren
    Abhaengigkeitsabschlag bezahlt.

    **Verglichen wird der Erfuellungsgrad**, nicht die Guete. Eine Guete von
    hier gegen eine Latte von dort zu halten ist der Fehler aus Befund 190;
    das Verhaeltnis je Punkt ist dimensionslos und darf nebeneinanderstehen
    (``research/erfuellung.py``). Es sind 0,8026 gegen 0,8299 - der
    kontogeschuetzte Punkt ist seiner eigenen Latte um 2,7 Punkte naeher.

    **Dieser Vorsprung ist weniger wert, als er aussieht** (Befund 411). Er
    steht auf dem n_eff von 159 aus 160, und das haengt am **Mass**: Auf
    R-Vielfache normiert zeigt dieselbe Zelle auf der Quartalsstufe ICC
    0,2550 bei p 0,0020 - so viel wie der gemeldete Punkt. Der fast
    verschwundene Designeffekt ist also kein Nachweis von Unabhaengigkeit,
    sondern eine Eigenschaft des Waehrungsmasses auf einem durchverzinsten
    Konto. Siehe ``QUARTALSPROBE``.

    **Nachgerechnet kippt der Vorsprung** (Befund 414). Im skalenfreien Mass
    bindet dort nicht der Kalendertag (Faktor 0,9938), sondern wieder das
    Quartal (0,7500): n_eff 120 statt 159, fehlend 124 statt 85, noetige
    Guete 0,3331 statt 0,2945 - und der Erfuellungsgrad 0,7336 statt 0,8298.
    Aus plus 2,7 Punkten werden **minus 6,9**. Der gemeldete Punkt ist
    dagegen massinvariant: dasselbe bindende Quartal, derselbe Faktor
    0,7372, dieselben 115. Dieser Vergleich kann die Modusfrage aus Befund
    400 also nicht tragen - er wechselt das Vorzeichen mit dem Mass. Siehe
    ``erfuellung_je_mass``.

    **Was nicht folgt**: dass der Kandidat nah ist. 83 % der Latte sind nicht
    die Latte; an diesem Punkt sind **drei** Gates offen statt zwei
    (Schlechtestes Jahr, Monte-Carlo, Deflated Sharpe), und es fehlen dort
    **85** wirksame Beobachtungen statt 76. Welcher Punkt die Zulassung
    traegt, ist die Entscheidung aus Befund 400.
    """

    name: str
    fertig: int
    effektiv: int
    guete: float
    dsr: float
    noetige_trades: int
    noetige_guete: float
    #: **Woran der Designeffekt haengt** (Befund 410). Acht Einteilungen
    #: laufen mit, es zaehlt die strengste - und welche das ist, war bis
    #: Befund 410 nirgends verzeichnet. Sie ist je Punkt eine andere, und
    #: das ist die halbe Antwort auf die Frage, die Befund 407 offen liess:
    #: warum der Designeffekt am kontogeschuetzten Punkt fast verschwindet.
    einteilung: str = ""
    icc: float = 0.0
    p_wert: float = 1.0

    @property
    def designfaktor(self) -> float:
        return self.effektiv / self.fertig

    @property
    def luecke(self) -> float:
        return 0.95 - self.dsr

    @property
    def fehlende_trades(self) -> int:
        return self.noetige_trades - self.effektiv

    @property
    def erfuellungsgrad(self) -> float:
        """Erreichte durch noetige Guete - die einzige Zahl, die zwischen
        zwei Punkten verglichen werden darf (Befund 190)."""
        return self.guete / self.noetige_guete


#: Die beiden Punkte aus Befund 407, mit der bindenden Einteilung aus 410.
REICHWEITEN: tuple[Reichweite, ...] = (
    Reichweite(
        name="gemeldet", fertig=156, effektiv=115, guete=0.2708, dsr=0.5826,
        noetige_trades=191, noetige_guete=0.3374,
        einteilung="Kalenderquartal", icc=0.2580, p_wert=0.0050,
    ),
    Reichweite(
        name="kontogeschuetzt", fertig=160, effektiv=159, guete=0.2444,
        dsr=0.6846, noetige_trades=244, noetige_guete=0.2945,
        einteilung="Kalendertag", icc=0.9767, p_wert=0.0065,
    ),
)

#: Die ganze Leiter je Zelle - acht Einteilungen, drei Messaufbauten
#: (Befund 410). Gemessen mit den Werkzeugen des Projekts
#: ('gates.stichprobe_wie_im_gate', 'unabhaengigkeit.designeffekt'), und
#: gegengeprueft gegen ``research.referenz``: Die erste Zelle gibt dessen
#: ``SPOTPUNKT`` (156/115), die dritte dessen ``KONTOPUNKT`` (160/159). Wer
#: einen Kennwert braucht, nimmt ihn von dort und nicht aus dieser Tabelle -
#: hier stehen Messgroessen der Unabhaengigkeitsrechnung, und eine davon
#: (0,0860, der p-Wert der Kalenderwoche kontogeschuetzt) trifft zufaellig
#: eine Zahl, die als Kennwert laengst ueberholt ist.
#:
#: Zu lesen ist sie **nach dem Faktor, nicht nach dem ICC**. Der Kalendertag
#: fuehrt die ICC-Spalte zweimal (0,9548 und 0,9767) und kuerzt fast nichts:
#: 143 bzw. 147 Bloecke auf 156 bzw. 160 Trades sind nahezu Einzelstuecke,
#: und der Designeffekt einer Einteilung aus Einzelstuecken ist eins.
#:
#: Was die Zellen unterscheidet, ist die **Signifikanz auf der Quartalsstufe**:
#: gemeldet ICC 0,2580 bei p 0,0050, kontogeschuetzt ICC 0,0904 bei p 0,0895.
#: Dort faellt die Quartalskorrelation unter die Schranke und kuerzt nicht
#: mehr. **Warum sie faellt, ist nicht gemessen** - und genau dort liegen die
#: 40 Beobachtungen Unterschied.
LEITER: dict[str, tuple[tuple[str, int, float, float, float, int], ...]] = {
    # Name -> (Einteilung, Bloecke, ICC, p, Faktor, n_eff)
    "gemeldet": (
        ("Walk-Forward-Fenster", 31, 0.1097, 0.0645, 1.0000, 156),
        ("Gleichzeitigkeit", 107, 0.0000, 1.0000, 1.0000, 156),
        ("Kalendertag", 143, 0.9548, 0.0325, 1.0000, 156),
        ("Kalenderwoche", 114, 0.7118, 0.0095, 0.9615, 150),
        ("Kalendermonat", 65, 0.5134, 0.0015, 0.8077, 126),
        ("Kalenderquartal", 33, 0.2580, 0.0050, 0.7372, 115),
        ("Halbjahr", 17, 0.0857, 0.0320, 0.9359, 146),
        ("Kalenderjahr", 9, 0.0567, 0.0460, 0.9744, 152),
    ),
    "durchgehend mit Beingrenzen": (
        ("Walk-Forward-Fenster", 30, 0.0573, 0.2775, 1.0000, 98),
        ("Gleichzeitigkeit", 85, 0.5169, 0.3135, 1.0000, 98),
        ("Kalendertag", 97, 1.0000, 0.0020, 1.0000, 98),
        ("Kalenderwoche", 83, 0.9779, 0.0025, 0.9796, 96),
        ("Kalendermonat", 53, 0.6051, 0.0130, 0.9388, 92),
        ("Kalenderquartal", 32, 0.1542, 0.1495, 1.0000, 98),
        ("Halbjahr", 16, 0.0401, 0.2325, 1.0000, 98),
        ("Kalenderjahr", 9, 0.0090, 0.3415, 1.0000, 98),
    ),
    "kontogeschuetzt": (
        ("Walk-Forward-Fenster", 31, 0.0946, 0.0855, 1.0000, 160),
        ("Gleichzeitigkeit", 111, 0.0000, 1.0000, 1.0000, 160),
        ("Kalendertag", 147, 0.9767, 0.0065, 0.9938, 159),
        ("Kalenderwoche", 117, 0.4519, 0.0860, 1.0000, 160),
        ("Kalendermonat", 67, 0.2030, 0.1030, 1.0000, 160),
        ("Kalenderquartal", 33, 0.0904, 0.0895, 1.0000, 160),
        ("Halbjahr", 17, 0.0267, 0.2185, 1.0000, 160),
        ("Kalenderjahr", 9, 0.0323, 0.1195, 1.0000, 160),
    ),
}


def bindend(name: str) -> tuple[str, int, float, float, float, int]:
    """Die Sprosse, die in dieser Zelle bindet - die mit dem kleinsten Faktor.

    Gerechnet, nicht gepflegt: Wer die Tabelle oben aendert, aendert damit
    auch diese Auskunft. Eine zweite, von Hand gefuehrte Liste waere genau
    die gepflegte Zahl, die wegdriftet (Befund 408).
    """
    return min(LEITER[name], key=lambda zeile: zeile[4])


@dataclass(frozen=True, slots=True)
class Quartalsprobe:
    """Die Quartalssprosse einer Zelle, in Waehrung und auf R-Vielfache.

    Befund 410 hat die bindende Einteilung je Zelle gemessen und eine Frage
    offen gelassen: Warum faellt die Quartalskorrelation zwischen den Modi?
    Dort liegen 40 Beobachtungen. Befund 411 hat nachgemessen, und zwar
    **alle vier** Zellen - der Vergleich in 410 lief ueber zwei Zellen, die
    sich in zwei Dingen zugleich unterscheiden, und war damit verwechselt.
    """

    zelle: str
    durchgehend: bool
    limits: bool
    roh: int
    n_eff: int
    bindend: str
    icc_waehrung: float
    p_waehrung: float
    icc_r: float
    p_r: float

    @property
    def kuerzt_in_waehrung(self) -> bool:
        """Schlaegt die Quartalssprosse im Waehrungsmass an?"""
        return self.p_waehrung < 0.05

    @property
    def kuerzt_im_r_mass(self) -> bool:
        return self.p_r < 0.05


#: Alle vier Zellen, Quartalssprosse, zwei Masse (Befund 411). Gemessen mit
#: 'unabhaengigkeit.designeffekt' auf denselben Quartalseimern wie das Gate
#: ('zeitskala.nach_kalender', gebuendelt nach dem Ausstieg); das R-Mass
#: teilt jedes Ergebnis durch das gewagte Geld (Stopabstand mal Menge). Kein
#: Trade war ohne Stop, es ist also keiner ausgelassen. Gegengeprueft gegen
#: ``research.referenz``: Zelle 1 gibt dessen SPOTPUNKT (156/115), Zelle 4
#: dessen KONTOPUNKT (160/159).
#:
#: **Erstens: Es ist der Fensterschnitt, nicht die Beingrenze.** Beide
#: geschnittenen Zellen zeigen ICC um 0,25 bei p von hoechstens 0,005 und kuerzen
#: (115 von 156, 121 von 160); beide durchgehenden liegen bei p ueber 0,08
#: und kuerzen nicht. Die Beingrenzen aendern die Trade-Zahl, nicht die
#: Quartalsabhaengigkeit. Damit ist der verwechselte Vergleich aus 410
#: aufgeloest.
#:
#: **Zweitens: Meine Erklaerung dafuer war falsch.** Die Vermutung war der
#: Kapital-Neustart je Fenster (Befund 403, "ohne Equity-Vorgeschichte"):
#: Positionsgroesse haengt am Kapital, ein Fenster ist mit 106 Tagen fast
#: ein Quartal, also muesste die Abhaengigkeit verschwinden, sobald man die
#: Groessenwirkung herausnimmt. Sie verschwindet **nicht** - im R-Mass steht
#: dieselbe Zelle bei ICC 0,2561 und p 0,0005. Die Quartalsabhaengigkeit im
#: geschnittenen Modus ist kein Groessenartefakt.
#:
#: **Drittens, ungesucht: Im durchgehenden Modus verdeckt das Waehrungsmass
#: eine Abhaengigkeit, die das R-Mass zeigt.** Kontogeschuetzt steigt der
#: ICC von 0,0904 (p 0,0895, kuerzt nicht) auf 0,2550 (p 0,0020) - so hoch
#: wie am gemeldeten Punkt. Auf einem durchverzinsten Konto streuen die
#: Waehrungsbetraege so weit, dass die Korrelation innerhalb eines Quartals
#: untergeht.
#:
#: **Was daraus folgt, und was nicht.** Der fast verschwundene Designeffekt
#: des kontogeschuetzten Punkts (159 von 160) ist damit **kein Nachweis von
#: Unabhaengigkeit**; er haengt am Mass. Der Erfuellungsvorsprung aus Befund
#: 407 (0,8299 gegen 0,8026) steht auf diesem n_eff und ist entsprechend
#: weniger wert. Das macht den Ausfall des Deflated Sharpe **robuster**,
#: nicht schwaecher - die einzige Richtung, in die ein solcher Fund fallen
#: darf.
#:
#: **Nicht** folgt, dass das Gate das Mass wechseln soll. Es rechnet in
#: Waehrung, und so bleibt es: Wer das Mass sucht, in dem eine Abhaengigkeit
#: guenstig ausfaellt, lockert das Gate. Hier faellt das R-Mass ohnehin
#: strenger aus, und auch das ist kein Grund - ein Mass wird nicht danach
#: gewaehlt, wie das Ergebnis aussieht.
#:
#: **Offen bleibt**, warum der Fensterschnitt die Quartalsabhaengigkeit
#: ueberhaupt erzeugt. Gemessen ist, dass er es tut und dass es nicht an der
#: Positionsgroesse liegt.
QUARTALSPROBE: tuple[Quartalsprobe, ...] = (
    Quartalsprobe(
        zelle="Fenster + Beingrenzen (gemeldet)",
        durchgehend=False, limits=True, roh=156, n_eff=115,
        bindend="Kalenderquartal",
        icc_waehrung=0.2580, p_waehrung=0.0050,
        icc_r=0.2561, p_r=0.0005,
    ),
    Quartalsprobe(
        zelle="Fenster, ohne Beingrenzen",
        durchgehend=False, limits=False, roh=160, n_eff=121,
        bindend="Kalenderquartal",
        icc_waehrung=0.2516, p_waehrung=0.0040,
        icc_r=0.2550, p_r=0.0020,
    ),
    Quartalsprobe(
        zelle="Durchgehend + Beingrenzen",
        durchgehend=True, limits=True, roh=98, n_eff=92,
        bindend="Kalendermonat",
        icc_waehrung=0.1542, p_waehrung=0.1495,
        icc_r=0.3104, p_r=0.0170,
    ),
    Quartalsprobe(
        zelle="Durchgehend, ohne Beingrenzen (kontogeschuetzt)",
        durchgehend=True, limits=False, roh=160, n_eff=159,
        bindend="Kalendertag",
        icc_waehrung=0.0904, p_waehrung=0.0895,
        icc_r=0.2550, p_r=0.0020,
    ),
)


@dataclass(frozen=True, slots=True)
class Fensterprobe:
    """Eine Erklaerung fuer die Quartalsabhaengigkeit, und was sie gemessen
    wert ist."""

    name: str
    vermutung: str
    gemessen: str
    traegt: bool


#: Der Testabschnitt des Walk-Forward, nachgemessen (Befund 412). Nicht aus
#: den Trade-Zeiten, sondern aus ``window.test_start``/``test_end``.
ABSCHNITTE = 32
ABSCHNITT_TAGE = (89, 92)
ABSCHNITT_MITTEL = 91.3
ABSCHNITT_UEBERLAPPUNGEN = 0

#: Drei Erklaerungen fuer die Frage, die Befund 411 offen liess - warum der
#: Fensterschnitt die Quartalsabhaengigkeit erzeugt. **Alle drei widerlegt**
#: (Befund 412).
#:
#: Und damit kehrt sich die Lesart um. Befund 411 hat gemessen, dass im
#: **R-Mass** beide Modi dieselbe Quartalsabhaengigkeit zeigen (0,2561
#: geschnitten gegen 0,2550 kontogeschuetzt). Zusammen mit diesen drei
#: Widerlegungen heisst das: Der Fensterschnitt **erzeugt** die
#: Abhaengigkeit nicht. Er aendert nur, ob das Waehrungsmass sie sehen kann.
#: Die Schlagzeile von 411, "es ist der Fensterschnitt", gilt fuer die
#: **Kuerzung**, nicht fuer die Abhaengigkeit - das ist eine Berichtigung an
#: meinem eigenen Eintrag von einem Lauf vorher.
#:
#: Was von der Frage bleibt: Warum das Waehrungsmass im durchgehenden Modus
#: blind wird, ist mit "die Betraege streuen auf einem durchverzinsten Konto
#: zu weit" benannt und nicht gemessen.
FENSTERPROBEN: tuple[Fensterprobe, ...] = (
    Fensterprobe(
        name="Ueberlappende Abschnitte",
        vermutung=(
            "Wenn die Testabschnitte sich ueberschneiden, steht derselbe "
            "Marktzug in zwei Bloecken - das waere Abhaengigkeit aus dem "
            "Messaufbau."
        ),
        gemessen=(
            "32 Abschnitte, 89 bis 92 Tage, **null** ueberlappende Paare, "
            "und kein Trade liegt ausserhalb seines Abschnitts."
        ),
        traegt=False,
    ),
    Fensterprobe(
        name="Doppelt gezaehlte Trades",
        vermutung=(
            "45 der 156 Trade-Kennungen kommen mehrfach vor - dann waeren "
            "einige Beobachtungen derselbe Trade."
        ),
        gemessen=(
            "Ein Namensartefakt. 'trade_id' ist 'strategy_id-entry_index', "
            "und 'entry_index' zaehlt je Fenster neu; die fuenf Trades unter "
            "'...-211' haben fuenf verschiedene (Symbol, Ein, Aus). Die "
            "Summe der Fenster ist 156 wie 'all_trades'. **Nichts im "
            "Projekt verschluesselt auf 'trade_id'**, die Uneindeutigkeit "
            "ist latent - aber sie ist da."
        ),
        traegt=False,
    ),
    Fensterprobe(
        name="Einstiege sammeln sich im Abschnitt",
        vermutung=(
            "Wenn jedes Fenster mit Vorlauf beginnt, koennten die Einstiege "
            "im hinteren oder vorderen Teil liegen; Trades eines Quartals "
            "kaemen dann aus einem engeren Zeitraum."
        ),
        gemessen=(
            "Gleichmaessig. Mittel 0,5262, Median 0,5326, Drittel 40/66/50 "
            "von 156, keiner ausserhalb. **Meine erste Messung sagte 0,3205 "
            "und 96/28/31** - sie normierte auf die Trade-Zeiten des "
            "Fensters, womit der erste Einstieg je Fenster per Definition "
            "auf 0 liegt. Gemessen wird gegen 'window.test_start/test_end'."
        ),
        traegt=False,
    ),
)


def traegt_eine_erklaerung() -> bool:
    """Traegt eine der gemessenen Erklaerungen? Gerechnet, nicht gepflegt."""
    return any(p.traegt for p in FENSTERPROBEN)


#: **Die kontrollierte Gegenprobe** (Befund 413). Ohne Beingrenzen sind die
#: geschnittene und die durchgehende Zelle **dieselben 160 Trades**: alle 160
#: (Symbol, Einstieg, Ausstieg) stimmen ueberein, und die R-Werte auf
#: 3,55e-15. Nur der Waehrungsgewinn unterscheidet sich, je Trade um den
#: Faktor 0,947 bis 6,000 (Median 2,774) - der Kapitalpfad, nichts weiter.
#:
#: Damit ist die Frage beantwortet, die Befund 412 offen liess. Mit festem
#: Trade-Satz, festem Kalender und festen Quartalen faellt der
#: Waehrungs-ICC der Quartalsstufe von 0,2516 auf 0,0904 und die Kuerzung
#: von 121 auf keine. Es ist ein **reiner Groesseneffekt**.
#:
#: Warum ein Groesseneffekt den ICC ueberhaupt bewegen kann - ein
#: gleichmaessiger kuerzt sich heraus, MSB und MSW skalieren beide mit c^2 -
#: zeigt die Zerlegung: Der Faktor **waechst ueber den Lauf**, also bekommen
#: spaete Quartale groessere Mittelwertsabstaende *und* groessere Streuung
#: innen, und das Innere waechst schneller.
#:
#:     Zelle                       MSB      MSW   MSB/MSW     ICC
#:     Fenster, ohne Beingrenzen  636,1    242,6     2,622  0,2516
#:     Durchgehend, ohne         1857,8   1255,6     1,480  0,0904
#:
#: MSW mal 5,2, MSB mal 2,9. **Meine Formulierung in 412 war unpraezise**:
#: Nicht "die Betraege streuen zu weit", sondern die Streuung *innerhalb*
#: eines Quartals waechst schneller als die *zwischen* den Quartalen.
#:
#: **Und eine schaerfere Vermutung ist widerlegt**: Ungleiche Blockvarianzen
#: erklaeren es nicht - ihre log-Streuung ordnet nicht mit dem ICC (3,775 bei
#: ICC 0,1542 gegen 3,289 bei 0,0904).
SKALENPROBE: dict[str, float] = {
    "gemeinsame_trades": 160,
    "faktor_min": 0.947,
    "faktor_max": 6.000,
    "faktor_median": 2.774,
    "r_abweichung": 3.55e-15,
    "msb_geschnitten": 636.0925,
    "msw_geschnitten": 242.6061,
    "msb_durchgehend": 1857.7981,
    "msw_durchgehend": 1255.5850,
}

#: Wie belastbar das R-Mass ist, auf das 411 und 412 sich stuetzen
#: (Befund 413). Die Verteilung ist die eines Trendfolgers: Ein Viertel der
#: Trades verliert glatt den Stop (-1,030 R), der Median liegt bei -0,555,
#: und das 95. Hundertstel bei 19,986.
#:
#: **Die Abhaengigkeit ueberlebt das Trimmen.** 13 der 160 Trades haben
#: |R| > 10; ohne sie steht die Quartalsstufe bei ICC 0,2266 und p 0,0085
#: statt 0,2550 und 0,0020. Kleiner, und weiter nachgewiesen - der R-Befund
#: aus 411 haengt nicht an Ausreissern.
#:
#: Die absurd anmutende Spanne der R-Blockvarianzen (Verhaeltnis um 1e31)
#: kommt **nicht** von Ausreissern, sondern von Bloecken aus lauter
#: ausgestoppten Trades: Die liegen alle bei -1,030, und ihre Varianz ist
#: fast null. Harmlos, aber beim Lesen leicht zu verwechseln.
R_PROBE: dict[str, float] = {
    "trades": 160,
    "min": -1.030,
    "median": -0.555,
    "p95": 19.986,
    "max": 19.986,
    "ueber_zehn": 13,
    "icc_voll": 0.2550,
    "p_voll": 0.0020,
    "icc_getrimmt": 0.2266,
    "p_getrimmt": 0.0085,
}


@dataclass(frozen=True, slots=True)
class Massfaktor:
    """Der Designfaktor eines Punktes in beiden Massen (Befund 414).

    ``faktor_waehrung`` ist das Minimum ueber die acht Einteilungen auf den
    Waehrungsgewinnen - genau das, was das Gate rechnet. ``faktor_r`` ist
    dasselbe Minimum auf R-Vielfachen, also auf dem gewagten Geld normiert.
    """

    punkt: str
    roh: int
    faktor_waehrung: float
    bindend_waehrung: str
    faktor_r: float
    bindend_r: str

    @property
    def n_waehrung(self) -> int:
        return max(1, min(self.roh, round(self.roh * self.faktor_waehrung)))

    @property
    def n_r(self) -> int:
        return max(1, min(self.roh, round(self.roh * self.faktor_r)))

    @property
    def massinvariant(self) -> bool:
        """Sagen beide Masse dasselbe? Beim gemeldeten Punkt ja."""
        return self.n_waehrung == self.n_r


#: Gemessen ueber die **ganze** Leiter, nicht nur die Quartalssprosse
#: (Befund 414; mit dem Quartal allein kaeme eine obere Schranke heraus).
#: Gegengeprueft: Die Waehrungsspalte gibt ``research.referenz``.SPOTPUNKT
#: (115) und KONTOPUNKT (159).
MASSFAKTOREN: tuple[Massfaktor, ...] = (
    Massfaktor(
        punkt="gemeldet", roh=156,
        faktor_waehrung=0.7372, bindend_waehrung="Kalenderquartal",
        faktor_r=0.7372, bindend_r="Kalenderquartal",
    ),
    Massfaktor(
        punkt="kontogeschuetzt", roh=160,
        faktor_waehrung=0.9938, bindend_waehrung="Kalendertag",
        faktor_r=0.7500, bindend_r="Kalenderquartal",
    ),
)


def erfuellung_je_mass() -> tuple[tuple[str, str, int, int, int, float, float], ...]:
    """Was der Plan des Projekts aus beiden Massen macht - **gerechnet**.

    (Punkt, Mass, n_eff, noetig, fehlend, noetige Guete, Erfuellungsgrad).
    Gerechnet aus ``research.referenz`` mit den Werkzeugen des Projekts, nicht
    von Hand gefuehrt: Eine zweite gepflegte Liste zur selben Sache laeuft
    auseinander (Befund 408).

    **Der Befund steht in der letzten Spalte.** Der Erfuellungsvorsprung, den
    Befund 407 dem kontogeschuetzten Punkt zuschreibt - 0,8298 gegen 0,8027,
    plus 2,7 Punkte -, **kippt** im skalenfreien Mass auf minus 6,9 (0,7336
    gegen 0,8027). Der gemeldete Punkt ist massinvariant: dieselbe bindende
    Einteilung, derselbe Faktor, dieselbe Zahl.

    **Was das heisst**: Dieser Vergleich kann die Modusfrage aus Befund 400
    nicht tragen. Er wechselt das Vorzeichen mit dem Mass.
    **Was es nicht heisst**: dass das R-Mass das richtige ist. Das Gate
    rechnet in Waehrung, und dabei bleibt es (Befund 411). Ein Mass wird
    nicht danach gewaehlt, wie das Ergebnis aussieht - und hier faellt es
    gegen den Punkt aus, der im anderen Mass vorn liegt.
    """
    from dataclasses import replace

    from research.referenz import KONTOPUNKT, SPOTPUNKT

    punkte = {"gemeldet": SPOTPUNKT, "kontogeschuetzt": KONTOPUNKT}
    zeilen = []
    for f in MASSFAKTOREN:
        for mass, n in (("Waehrung", f.n_waehrung), ("R-Mass", f.n_r)):
            q = replace(punkte[f.punkt], effektiv=n)
            noetig = q.noetiges_n()
            ng = q.noetige_guete()
            zeilen.append(
                (f.punkt, mass, n, noetig, noetig - n, ng, q.guete / ng)
            )
    return tuple(zeilen)


def vorsprung_je_mass() -> dict[str, float]:
    """Der Abstand der Erfuellungsgrade, je Mass - positiv heisst: der
    kontogeschuetzte Punkt liegt vorn."""
    je = {(p, m): e for p, m, *_rest, e in erfuellung_je_mass()}
    return {
        mass: je[("kontogeschuetzt", mass)] - je[("gemeldet", mass)]
        for mass in ("Waehrung", "R-Mass")
    }
