"""Wo steht das Projekt - auf einem Bildschirm statt in 2400 Zeilen.

Warum es das gibt
-----------------
``strategies/BEFUND.md`` ist ein Laborbuch: chronologisch, vollstaendig, und
fuer jemanden, der wissen will *wo wir stehen*, unbrauchbar. Wer entscheiden
soll, braucht drei Dinge - was gemessen ist, was daraus folgt, und was von ihm
selbst abhaengt.

Was hier steht und was nicht
----------------------------
Die Zahlen werden **gemessen**, nicht gepflegt: Der Kandidat laeuft durch die
Gates, der Abstand kommt aus der Grenzlinie, der Versuchszaehler aus dem
Zustand. Nichts davon ist abgeschrieben, und nichts kann veralten, ohne dass
es auffaellt.

Die Liste der geschlossenen Richtungen ist dagegen **gepflegt** - sie muss es
sein, denn eine Messung, die einmal gelaufen ist, steht nirgends als Zahl
herum. Damit sie nicht zur Behauptung verkommt, traegt jeder Eintrag die
Nummer im BEFUND, unter der die Messung nachzulesen ist. Ein Eintrag ohne
Fundstelle wird abgewiesen.

**Was hier nicht steht: eine Empfehlung.** Zwei der offenen Punkte sind
wirtschaftliche Entscheidungen des Nutzers, keine statistischen. Sie werden
benannt und beziffert, nicht beantwortet.

**Und nicht der Stand des Kandidaten.** Wo hier eine Kennzahl vorkommt, ist
sie Teil eines Registereintrags und gehoert zu dessen Fundstelle - der
massgebliche Punkt steht in ``research/referenz.py``. Ein Eintrag wie *"21
Stellen auf 0,8640"* nennt die Zahl als Geschichte, nicht als Stand; seit
Befund 135 sind es 0,6026 bei n = 112.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Richtung:
    """Eine untersuchte Richtung und ihr gemessenes Ergebnis.

    ``befund`` ist die Stelle, an der die Richtung **zuerst** gemessen wurde.
    ``zuletzt`` ist die Stelle, an der sie **zuletzt** gemessen wurde - und
    genau darauf kommt es an, wenn jemand die Zahlen nachschlaegt.

    Das ist Befund 130, und es korrigiert einen Fehler, den dieses Register
    ermoeglicht hat: Der Eintrag *"Vola-Ziel ... Befund 21"* zeigte auf eine
    Tabelle, die Befund 23 zwei Befunde spaeter ersetzt hatte. Zwei Laeufe
    haben dort nachgeschlagen, die alte Tabelle gefunden und den Unterschied
    zum heutigen Stand falschen Ursachen zugeschrieben.

    Wer eine Fundstelle nennt, muss die **letzte** nennen. Die erste ist
    Geschichte, nicht Stand.
    """

    name: str
    ergebnis: str
    befund: int
    zuletzt: int | None = None

    def __post_init__(self) -> None:
        if self.befund <= 0:
            raise ValueError(
                f"'{self.name}' ohne Fundstelle im BEFUND - eine geschlossene "
                f"Richtung ohne nachlesbare Messung ist eine Behauptung."
            )
        if self.zuletzt is not None and self.zuletzt <= self.befund:
            raise ValueError(
                f"'{self.name}': Nachmessung in Befund {self.zuletzt} liegt "
                f"nicht nach der Erstmessung in {self.befund} - dann ist es "
                f"keine Nachmessung."
            )

    @property
    def massgeblich(self) -> int:
        """Die Fundstelle, in der die gueltigen Zahlen stehen."""
        return self.zuletzt or self.befund

    def __str__(self) -> str:
        stelle = (
            f"Nr. {self.befund}"
            if self.zuletzt is None
            else f"Nr. {self.zuletzt} (zuerst {self.befund})"
        )
        return f"{self.name:22} {self.ergebnis:40} {stelle}"


#: Die Richtungen, die gemessen und abgeschlossen sind.
#:
#: Reihenfolge: wie sie untersucht wurden. Jede Zeile ist eine Messung, keine
#: Einschaetzung - die Nummer verweist auf die Stelle im BEFUND, an der die
#: Zahlen stehen.
GESCHLOSSEN: tuple[Richtung, ...] = (
    # Befund 27 hat den Weg geschlossen, Befund 133 ihn nachgemessen und die
    # Begruendung korrigiert: Die Stichprobe waechst sehr wohl (152 -> 229),
    # nur faellt die Guete schneller, als sqrt(n) steigt.
    Richtung(
        "Mehr Maerkte",
        "Stichprobe waechst auf 229, Evidenz faellt 3,409 -> 2,917",
        27,
        zuletzt=133,
    ),
    Richtung(
        "Mehr Historie",
        "Guete flach ueber sechs Fenster, DSR haengt an n",
        14,
        zuletzt=132,
    ),
    # Befund 145 hat dasselbe noch einmal gemessen - mit der Einteilung des
    # Gates (135), am Spot-Punkt (108) und mit der Zerlegung in brutto und
    # netto. Ergebnis unveraendert, Zahlen neu.
    #
    # Befund 188 hat es auf dem nach 182/184 berichtigten Vorrat wiederholt.
    # Zwei Dinge aendern sich gegen 171: Die Kopplung ist jetzt da (t = -2,19
    # statt -0,26), und die Aussage wird haerter - der Achsenabschnitt ist
    # negativ, es gibt also **keine** Stichprobengroesse mit Vorteil je
    # Trade, nicht nur keine, die reicht. Dieselben zwei Regeln sind positiv.
    # **Der Eintrag, der sich selbst widersprochen hat** (Befund 302).
    #
    # 255 hat es auf Viertelstunden gemessen: -0,267 auf -0,186, die Reibung
    # traegt 30 %. 256 hat im selben Eintrag festgehalten, dass der
    # **gerechnete** Kippfaktor keine Messung ist. 297 hat die Richtung
    # trotzdem wieder aufgemacht - mit genau diesem Kippfaktor (2), und der
    # Eintrag stand danach auf 'unentschieden', obwohl die Messung drei
    # Saetze weiter oben stand.
    #
    # 302 hat sie auf einem zweiten, unabhaengig gebauten Weg wiederholt
    # ('cli reibung', ohne Gates, in 13 Stuecken) und ist bei denselben
    # Zahlen herausgekommen: -0,267 und -0,186 ueber 36 Regeln. Das ist eine
    # Bestaetigung und war trotzdem 106 Minuten fuer etwas, das schon
    # dastand. Wer hier etwas anfuegt, sagt dazu, was mit dem Frueheren ist.
    Richtung(
        "Traegt die Reibung die Kopplung auf kurzen Kerzen?",
        "Sie traegt einen Teil und nicht alles: 2 % des Weges zur Null auf "
        "Tageskerzen, 30 % auf Viertelstunden (-0,267 auf -0,186 ueber 36 "
        "Regeln). Ohne jede Reibung bleibt die Kopplung negativ - sie "
        "gehoert den Signalen",
        78,
        zuletzt=302,
    ),
    Richtung(
        "15-Minuten-Kerzen",
        "36 Regeln auf 225.000 Kerzen: 34 negativ; die Gerade beginnt schon "
        "bei -0,0882 und faellt (t = -2,19) - keine Stichprobe traegt dort "
        "einen Vorteil je Trade",
        29,
        zuletzt=188,
    ),
    # Befund 21 hat diese Richtung eroeffnet, Befund 23 hat sie nach zwei
    # behobenen Messfehlern neu vermessen (die Leiter rutschte um eine Stufe),
    # Befund 129 am Spot-Punkt bestaetigt. Wer 21 nachschlaegt, findet eine
    # ueberholte Tabelle - genau das ist zweimal passiert (Befund 130).
    Richtung("Vola-Ziel", "Hub 0,009 bei einer Luecke von 0,077", 21, zuletzt=129),
    Richtung("Stop-Weite", "4 % ist das Maximum, beide Seiten schlechter", 28),
    Richtung("Konviktions-Bonus", "Risikoregler, kein Qualitaetsregler", 30),
    Richtung(
        "Perioden-Faktor",
        "mehr Trades, aber Qualitaet faellt schneller",
        32,
        zuletzt=49,
    ),
    Richtung(
        "Termin-Overlay",
        "wirkungslos mit Kosten - haelt am kostenfreien Anschlag ein Gate",
        12,
        zuletzt=127,
    ),
    Richtung("Shorts", "kein Vorteil in der Gegenrichtung", 13),
    Richtung("Perioden-Ensemble", "mehr Zeilen, keine neue Information", 17),
    Richtung("Abkuehlung", "zwei Gates - aber nur durch Streichen", 60),
    Richtung("Trades streichen", "reicht fuer zwei Gates, egal welche", 60),
    Richtung(
        "Gewinnziel",
        "Hub 0,818 - aber nur nach unten, Hoechstwert besetzt",
        46,
        zuletzt=129,
    ),
    Richtung("Adaptive Periode", "mehr Trades, aber einander aehnlicher", 48),
    Richtung("Kanalausbruch", "strukturell neu, 5 von 11, Faktor 1,74", 53),
    Richtung("Umsatzfilter", "neue Informationsquelle, DSR 0,162", 53),
    Richtung("Rueckkehr zum Mittel", "Gegenthese gemessen: 1 von 11", 53),
    # Ab hier die Wege, die seit Befund 70 geschlossen wurden. Sie fehlten
    # bis Befund 90 vollstaendig - und damit sah ein Lauf, der hier nachsah,
    # nur den Stand von vor zwanzig Befunden.
    Richtung(
        "Schiefe erhoehen",
        "am Spot-Punkt bleibt eine Reserve von 0,0079",
        70,
        zuletzt=125,
    ),
    Richtung("Woelbung senken", "unter 1 mathematisch unmoeglich", 70),
    # Befund 168 hat die Kopplung zu Ende gerechnet, Befund 169 nachgesehen,
    # wer sie traegt: neun der vierzehn Regeln sind derselbe Einstieg.
    Richtung(
        "Trade-Zahl heben",
        "Guete deckelt bei 1,931 gegen noetige 3,522; die Kopplung (-0,71) "
        "traegt aber nur innerhalb der SMA-Familie, ausserhalb t = -1,13",
        75,
        zuletzt=169,
    ),
    Richtung("Katalog als Partner", "0 von 15 Genomen taugen", 74),
    Richtung("Eigenbau-Partner", "8 Regeln aus Befund 77 und 83 gescheitert", 83),
    Richtung("Familie Rueckkehr", "alle 5 unter der Geraden, Permutation haelt", 84),
    Richtung("Phasen-Partner", "6 von 22 gegenlaeufig, 5 davon insgesamt wertlos", 85),
    # Befund 86 hat 210 Paare auf der Wochenachse gegen eine Permutationsnull
    # gestellt. Befund 141 misst enger und strenger nach: nur die 14 Paare mit
    # dem Bestand, dafuer mit der Einteilung des Gates selbst. Befund 151 hat
    # alle 14 noch einmal gefahren, nachdem der Nachlauf verlaengert war -
    # das Ergebnis steht, die Zahlen sind neu.
    Richtung(
        "Verbund aus dem Katalog",
        "bestes Paar 3,585 unter Nullmedian 3,683; nachgemessen 3,030 "
        "gegen eine Latte von 3,644 - 0 von 14",
        86,
        zuletzt=151,
    ),
    Richtung("Sperrfrist", "Folgetrades schlechter, aber kein t-Wert ueber 2", 88),
    Richtung("Verbund fuer die Risikogates", "231 Kombinationen, kein Treffer", 94),
    Richtung(
        "Groessenregler zum Rechteck",
        "ohne Mengenrundung glatt und monoton, Verhaeltnis 1,07 gegen 1,25",
        95,
    ),
    Richtung(
        "Koernung zum Deflated Sharpe",
        "bewegt ihn ueber die ganze Kontoleiter um 0,014",
        96,
    ),
    Richtung(
        "Feinere Kerzen im Fuellmodell",
        "80,8 % der Balken aufgeloest, Ergebnis bitgleich",
        99,
    ),
    Richtung(
        "Zulassung auf Referenzkerzen",
        "Kassamarkt statt Perpetual, kein Funding - keine Zulassung",
        102,
    ),
    Richtung(
        "Hebel als Reserve",
        "an 0,2 % der Balken genutzt, Deckel auf 1,0 bitgleich",
        106,
    ),
    Richtung(
        "Kostenannahmen",
        "bei Kosten null fehlen 0,0692 - Anschlag nachgeprueft",
        111,
        zuletzt=127,
    ),
    Richtung(
        "Schwacher Vorteil (5 %)",
        "|t| = 0,74 ueber acht Saaten - keine Delle, nur Rauschen",
        113,
    ),
    Richtung(
        "Belege als Kalibrierung",
        "8 % Abdeckung, sagen 0,4130 voraus statt 0,2956 - untauglich",
        119,
    ),
    Richtung(
        "Schnittpunkt als Prognose",
        "Fehlerbalken 14,3 %; am Spot-Punkt 4.712 statt 764.635",
        124,
        zuletzt=126,
    ),
    # Der Verbund ist der einzige gemessene Hebel, der die effektive
    # Stichprobe **hebt** statt sie umzuverteilen. Naheliegend also, es mit
    # drei Beinen zu versuchen - Befund 153 hat alle 91 gemessen. Derselbe
    # Befund hat dabei den Deckel auf die Beinsumme eingezogen, ohne den die
    # Spitze der Rangliste ein Artefakt gewesen waere.
    Richtung(
        "Dreierverbund",
        "0 von 91; bester fehlt 0,542 gegen 0,632 beim besten Paar - nur 2 "
        "von 91 ueberhaupt besser als ein Paar. Deckel auf die Beinsumme",
        153,
    ),
    # Die naheliegende Hoffnung nach 198 Versuchen - "haetten wir sparsamer
    # gesucht, staende hier etwas" - ist damit gemessen und nicht mehr offen.
    # Sie ist ausdruecklich kein Grund, den Zaehler zu senken.
    # Die Katalogzahl stand zuerst bei 10 und war mit den Momenten des
    # Bestands gerechnet (Befund 191); mit denen jeder Regel sind es 8.
    #
    # **Und der Verbundweg fehlte** (Befund 194). Dort liegt die Grenze bei
    # 137 gegen einen Zaehler von 198 - der einzige gemessene Weg, auf dem
    # der Versuchsstand tatsaechlich entschieden hat. Geschlossen bleibt die
    # Richtung trotzdem: Befund 186 hat alle sieben Bestplatzierten im
    # Holdout durchfallen lassen, was bei 119 bestanden haette, waere also
    # aller Wahrscheinlichkeit nach ein Fehlalarm gewesen.
    Richtung(
        "Suchdisziplin als Weg",
        "Bestand allein bis 21 Versuche, beste Katalogregel bis 8, bestes "
        "Paar bis 137 (vor der Auswahl 119) gegen einen Zaehler von 198. Nur "
        "auf dem Verbundweg war der Stand ueberhaupt entscheidend - und dort "
        "haben Gate und Holdout dasselbe gesagt",
        189,
        zuletzt=194,
    ),
    # Der Schritt, den 270 verlangt hat - und die Antwort darauf.
    Richtung(
        "Einstiegsseite",
        "vier Familien, zwei Maerkte, zwei Kerzenlaengen: kein Fund haelt. Die "
        "Marktbreite kam als erste ueber die Schwelle (-3,74 gegen 3,62) und "
        "faellt an der Verschiebungsprobe - 2 von 584",
        272,
        zuletzt=276,
    ),
)


#: Behobene Fehler in den Werkzeugen - **nicht** geschlossene Suchrichtungen.
#:
#: Die Trennung ist Befund 123, und sie korrigiert meine eigene Arbeit: Ich
#: habe neun Werkzeugbefunde in ``GESCHLOSSEN`` eingetragen, die dort nichts
#: verloren haben. Die Liste beantwortet die Frage *"welche Suchwege sind
#: gemessen zu"* - und wer sie las, fand zwischen "Mehr Maerkte: effektive
#: Stichprobe bleibt bei 150" auf einmal "README auf dem Stand vom 1. August".
#:
#: Beides sind Messungen mit Fundstelle, aber sie beantworten verschiedene
#: Fragen. Ein geschlossener Suchweg heisst: dort ist nichts zu holen. Ein
#: behobener Werkzeugfehler heisst: etwas war kaputt und ist repariert - das
#: sagt ueber die Aussichten des Projekts gar nichts.
#:
#: Reihenfolge: aufsteigend nach Fundstelle.
BEHOBEN: tuple[Richtung, ...] = (
    # Befund 92 hat die Botschaft als falsch nachgewiesen und nicht geaendert.
    # Siebzig Befunde spaeter stand sie noch da - deshalb ist die Fundstelle
    # 92 und die letzte Messung 163.
    Richtung(
        "Plateau-Gate meldete die falsche Form",
        "'Nadelspitze' fuer jeden Fehlschlag, auch fuer die einseitigen - der "
        "Faktor des gescheiterten Nachbarn unterscheidet es, das Gate hatte "
        "ihn und warf ihn weg; Urteil unveraendert 0,500 gegen 0,600",
        92,
        163,
    ),
    Richtung(
        "Stand auf einem Betriebspunkt",
        "zwei Gates hingen an einer ungeklaerten Tatsache",
        112,
    ),
    Richtung(
        "Arbeit vor den Boersendaten",
        "elf Befunde hinter einer Sperre, die keine Messung aufhebt",
        114,
    ),
    Richtung(
        "Uebergang auf Boersendaten",
        "Sperre haengt am Namen und loest sich - Weg geprueft",
        115,
    ),
    Richtung(
        "Trockenlauf nur fuer den Zaehler",
        "Rauchtest schrieb die Bestenliste fort - Schutz erweitert",
        116,
    ),
    Richtung(
        "git status als Pruefmass",
        "misst den Befehl, nicht den Zustand - der Commit-Zeiger tut es",
        117,
    ),
    Richtung(
        "README auf dem Stand vom 1. August",
        "57 Befunde alt - verweist jetzt auf 'cli stand' statt zu pflegen",
        118,
    ),
    Richtung(
        "Textsuche nach zaehlenden Befehlen",
        "findet 'korb' nicht - nur der Trockenlauf gibt Auskunft",
        120,
    ),
    Richtung(
        "Gate-Zahl abschreiben",
        "vier Stellen, drei Fassungen - jetzt aus evaluate_gates abgeleitet",
        121,
    ),
    Richtung(
        "Regelliste neben dem Verzeichnis",
        "acht statt elf - die drei Verbuende fehlten dem Analysten",
        122,
    ),
    Richtung(
        "Werkzeugbefunde unter den Richtungen",
        "neun Eintraege in der falschen Liste, Reihenfolge zerfallen",
        123,
    ),
    Richtung(
        "Schiefe-Weg am Perpetual-Punkt",
        "Reserve 0,0079 statt 0,1086 - cli form zeigt jetzt beide",
        125,
    ),
    Richtung(
        "Betriebspunkt in Erreichbarkeitsaussagen",
        "vier Stellen: stand, form, rennen, suchbudget - alle behoben",
        126,
    ),
    Richtung(
        "Bremsen unterhalb der Kostendecke",
        "Kalender, Verfallsfrist, Risk-Officer - oeffnen kostet -0,0046",
        127,
    ),
    Richtung(
        "Alte Tabelle als Vergleichspunkt",
        "15 Commits verschieben Befund 21 - beide Punkte neu gemessen",
        128,
    ),
    Richtung(
        "'Regler traegt nicht weit genug'",
        "gilt fuers Vola-Ziel, nicht fuers Gewinnziel - Hub 0,0091 gegen 0,8178",
        129,
    ),
    # Der Eintrag nannte zwanzig Befunde lang "die Luecke ist 0,0860" - eine
    # Zahl aus einem Betriebspunkt, den schon Befund 135 ueberholt hatte.
    # Nachgemessen in Befund 156, auf denselben Sprossen.
    Richtung(
        "Stichprobe ohne Fehlerbalken",
        "Kalibrierung bewegt 0,2628 bei einer Luecke von 0,5048 - also 0,52x "
        "statt 3,78x; beim veroeffentlichten Paar weiter 1,21x",
        134,
        zuletzt=156,
    ),
    Richtung(
        "Einteilung ohne Quartale",
        "Gate sah die Abhaengigkeit nicht - n 152 auf 112, DSR auf 0,6026",
        135,
    ),
    Richtung(
        "Ueberholte Kennzahl im Modulkopf",
        "21 Stellen auf 0,8640 - Pruefung verlangt jetzt den Hinweis",
        136,
    ),
    Richtung(
        "Gate-Aenderung an einem Kandidaten",
        "Quartale ueber sieben Stellungen: Bruch 0,028 - Kurve, kein Schalter",
        137,
    ),
    Richtung(
        "Zeit bis zur Schwelle veraltet",
        "1,8 Jahre galten fuer n = 152; jetzt mindestens 5,6",
        138,
    ),
    Richtung(
        "Latte auf roher Trade-Zahl",
        "6 Aufrufe uebergaben 152 statt 112 - Latte 14 % zu tief, "
        "Auftrag an die KI 47 % zu leicht",
        139,
    ),
    Richtung(
        "Einteilung des Gates achtmal nachgebaut",
        "5 Kommentare versprachen 'genau wie im Gate', keiner stimmte noch",
        139,
    ),
    Richtung(
        "Verbund auf alter Einteilung",
        "Befund 73 neu gerechnet: Guete 3,368 auf 3,073, Luecke 0,298 auf 0,552 - "
        "der Beitrag des Partners waechst dabei von +0,152 auf +0,343",
        140,
    ),
    Richtung(
        "Wettrennen auf roher Trade-Zahl",
        "Nullstreuung 0,0808 statt 0,0925 - Vorsprung der Suche von "
        "+15 % auf +0,6 %; bestimmt war das Vorzeichen nie",
        142,
    ),
    Richtung(
        "Vermuteter Abschlag auf Feinkerzen",
        "gemessen 0,92 statt der vermuteten Verschlechterung; die Zeitskala "
        "haengt an der Handelsdichte, nicht an der Kerzenlaenge",
        143,
    ),
    Richtung(
        "Strengste Einteilung ungeprueft am Rand",
        "auf Tageskerzen ist das Quartal ein echtes Minimum - Halbjahr "
        "0,921, Jahr 1,000. 'am_rand' hatte dafuer bis 218 keinen Aufrufer, "
        "die Frage war also gebaut und ungestellt; jetzt beide Leitern als "
        "Daten und beantwortet",
        143,
        zuletzt=218,
    ),
    Richtung(
        "Verteilungsform in taktung stillschweigend normal",
        "0,3655 gegen 0,2978 bei n = 150; Wahl bleibt, steht jetzt aber da - "
        "und schrumpft auf -3 % bei 10.000 Trades",
        144,
    ),
    Richtung(
        "Research-KI nicht am Wettbewerb",
        "hing nur an 'cli research'; der Wettbewerb konnte nur Varianten "
        "bilden - jetzt 'cli wettbewerb --ki', Herkunft getrennt gefuehrt",
        146,
    ),
    Richtung(
        "Auftrag an die KI auf widerlegtem Kriterium",
        "Punkt 3 nannte die Fensterkorrelation (+0,04 Rangkorrelation, "
        "Befund 141); jetzt steht dort, was Signal traegt",
        147,
    ),
    Richtung(
        "'cli stand' auf roher Trade-Zahl",
        "siebte Aufrufstelle nach Befund 139: 15 % statt 31 % noetiger "
        "Zuwachs - 0,2984 bei 152 roh gegen 0,3412 bei 112 effektiv",
        148,
    ),
    Richtung(
        "Latte ohne ihre Lesart formatiert",
        "achte und neunte Stelle, beide in front.py; 'als_zahl'/'als_faktor' "
        "tragen 'mindestens' jetzt mit - wo es nicht rechenbar ist, steht es da",
        149,
    ),
    Richtung(
        "Mehrfach gemessene Reglerstellungen doppelt gezaehlt",
        "44 Punkte fuer 30 Stellungen; Kennzahlen identisch, also keine "
        "Auswahl - aber 24 von 30 waren in der Tabelle unsichtbar",
        150,
    ),
    Richtung(
        "Nachlauf an einer Regel kalibriert",
        "12 von 24 Katalogregeln endeten am Kalender, 103 Trades; auf vier "
        "Fensterlaengen verlaengert - bester Verbund 3,073 -> 3,030",
        151,
    ),
    Richtung(
        "Vier Tests brauchten den Kerzenspeicher",
        "in einem frischen Klon rot, ohne dass etwas kaputt war - drei "
        "pruefen jetzt vor dem Laden, einer traegt die Marke 'daten'",
        151,
    ),
    Richtung(
        "Frischer Datenabzug hob den Referenzpunkt",
        "DSR 0,6026 -> 0,7255 durch zwei Trades am Serienende; nach der "
        "Zensur (Befund 152) stand der Punkt bei 0,5881 - damals, bei 198 "
        "Versuchen",
        151,
        zuletzt=152,
    ),
    Richtung(
        "Serienende gekuerzt statt zensiert",
        "der Puffer warf vier fertig gehandelte Trades mit weg und lag "
        "deshalb ueber der strengen Behandlung: DSR 0,4707 statt 0,4452",
        152,
    ),
    Richtung(
        "Zensierte Trades in der Gate-Statistik",
        "'cli stand' rechnete sie mit - noetiger Zuwachs 24 % statt 33 %; "
        "jetzt nur noch in Rendite und Rueckgang",
        152,
    ),
    Richtung(
        "Zeitskala im Gate",
        "nur das Kalenderquartal war verdrahtet; es bindet bei 2 von 15 "
        "Genomen, bei 6 von 15 rechnete das Gate zu gross - ganze Leiter",
        154,
    ),
    Richtung(
        "Fensterprobe nur im Modulkopf",
        "groesste Aggregatbehauptung nie fensterweise geprueft: 5 besser, "
        "10 schlechter, p = 0,94 - der Gewinn ist Stichprobe, nicht Qualitaet",
        155,
    ),
    Richtung(
        "Suchbudget als Bremse",
        "die restlichen 32 Versuche kosten +0,042 Guete - die Luecke ist "
        "0,659; der Zaehler ist in keiner Richtung das Hindernis",
        157,
    ),
    Richtung(
        "Auftragspunkt behauptete geloeschte Daten",
        "'Daten liegen hier vor' galt fuenf Befunde nach dem "
        "Behaelterwechsel weiter - 'cli stand' misst den Bestand jetzt",
        157,
    ),
    Richtung(
        "Halbe Rechnung nachgezogen",
        "Befund 152 hob 'heute' und liess 'noetig' stehen, obwohl dieselbe "
        "Korrektur die Guete senkte - 5,4 statt 6,0 Jahre, sechs Befunde lang",
        158,
    ),
    Richtung(
        "Entfernung galt dem falschen Kandidaten",
        "AUSSICHT beschreibt den Bestand, der beste gemessene Kandidat ist "
        "der Verbund - jetzt beide da, und die Jahre stehen nur noch dort",
        158,
    ),
    Richtung(
        "Dritte Zahl derselben Rechnung",
        "Befund 158 zog 'noetig' nach und liess die Sammelrate auf 34,2 - "
        "bei 115 auf 3300 Tagen sind es 34,8; jetzt eine Rechnung",
        159,
    ),
    Richtung(
        "Entfernung nirgends angezeigt",
        "AUSSICHT rechnet sie seit Befund 132 und stand in keinem Bericht - "
        "'cli stand' zeigt sie jetzt, fuer beide Kandidaten",
        160,
    ),
    # Befund 160 hat die Einordnung als Ueberlegung in den Bericht
    # geschrieben. Befund 161 hat sie gemessen - und sie faellt schaerfer aus.
    Richtung(
        "Warten hilft nur einem Gate",
        "'Schlechtestes Jahr' riss die Schwelle bei 2547 Tagen und steht "
        "seither bei -10,3 gegen -10,00 - ein Minimum kehrt nicht zurueck",
        161,
    ),
    # Der zweite Betriebspunkt stand seit Befund 112 im Bericht - nur nicht
    # in der Aufgabenliste drei Zeilen darunter.
    Richtung(
        "Aufgabenliste nur vom schlechteren Punkt",
        "beide genannten Aufgaben bestehen unter Spot (9/11 gegen 7/11); "
        "'cli stand' sagt jetzt dazu, was an der offenen Voraussetzung haengt",
        164,
    ),
    # Die Gate-Zahlen des Eintrags stimmten - deshalb hat niemand die
    # Prozente daneben nachgerechnet.
    Richtung(
        "Betriebspunkte zweimal im Bericht",
        "Auftragstext trug 14,83/13,47 und 0,17 Punkte, gemessen sind "
        "14,34/12,95 und 0,66 - jetzt gerechnet statt gepflegt",
        165,
    ),
    # Drei 'except'-Zweige kannten den Unterschied und keiner reichte ihn
    # weiter - dieselbe Form wie die Nadelspitze in Befund 163.
    Richtung(
        "Fehlende Bestenliste als fehlendes Feld gemeldet",
        "'cli partner' verwies auf Befund 69, waehrend die ganze Datei fehlte; "
        "ein Leser statt drei, und die Botschaft trifft jetzt den Fall",
        166,
    ),
    # Die README hat diese Wache seit Befund 118 - die Anleitung, der der
    # Nutzer wirklich folgt, hatte sie nicht.
    Richtung(
        "Nutzerbefehle nur auf Form geprueft",
        "'backfill --von ..., dann wettbewerb' war keine Befehlszeile; jetzt "
        "fuenf einzeln einlesbare Zeilen, von Click geprueft",
        167,
    ),
    Richtung(
        "Spot-Punkt zweimal wortgleich in cli.py",
        "_spotguete und _spotpunkt trugen denselben Block; 'fraction' wurde "
        "gesetzt statt gedeckelt und blies Genome unter 1,0 auf",
        168,
    ),
    # Meine eigene Verallgemeinerung aus dem Lauf davor, nach einem Lauf
    # nachgeprueft und eingeschraenkt.
    Richtung(
        "Kopplung als Eigenschaft 'des Vorrats' gelesen",
        "9 der 14 Regeln sind derselbe Einstiegsindikator; ohne sie bleibt "
        "t = -1,13 - die Decke beschreibt eine Familie, nicht den Vorrat",
        169,
    ),
    # Die Zuordnung war eine gepflegte Tabelle ohne Messung - die fuenfte
    # Stelle dieser Art nach 158, 159, 165, 166.
    Richtung(
        "Generation 8 auf der falschen Kerzenlaenge",
        "Luecken-, VWAP- und Eroeffnungsregeln standen auf Tageskerzen, wo "
        "keine davon ausloest; jetzt auf 15 Minuten, mit Pruefung",
        170,
        171,
    ),
    # Dieselbe Bauart wie Befund 160, nur mit dem folgenreicheren Ergebnis.
    Richtung(
        "Zweiter Weg nur im Fachbefehl",
        "die Einordnung des Bestands in seinen eigenen Katalog stand nur in "
        "'cli vorratsdecke'; 'cli stand' nennt sie jetzt - ohne Zahl",
        172,
    ),
    # Meine eigene Fehlzuschreibung aus Befund 170, drei Laeufe spaeter an
    # der Rechnung aufgefallen.
    Richtung(
        "Wache auf dem teuren Weg, aus falschem Grund",
        "nicht die Config und nicht die Fenster - die Marktzahl; zwei "
        "Maerkte ohne Walk-Forward urteilen gleich, 265s gegen 65s",
        173,
    ),
    # Der sechste Ort derselben Verwechslung von roher und effektiver
    # Stichprobe - Befund 139 hatte fuenf behoben.
    Richtung(
        "Teststaerke-Guete auf roher Trade-Zahl",
        "sechste Stelle nach Befund 139, dazu ein Feld namens 'guete', das "
        "den Sharpe je Trade trug und bis in Befund 113 gewandert ist",
        176,
    ),
    # Meine eigene Erklaerung aus dem Lauf davor - eine Geschichte, keine
    # Messung, und einen Lauf spaeter widerlegt.
    Richtung(
        "Verfall der Stichprobe falsch erklaert",
        "nicht laengere Haltedauer (Median bleibt 3-4 Tage), sondern "
        "wegbleibende Einstiege: 158 auf 16, Zeit im Markt 34,1 auf 2,8 %",
        177,
    ),
    # Ein Name, der als Schluessel diente und als Beschriftung gekuerzt wurde.
    Richtung(
        "Gekuerzte Regelnamen im Urteil",
        "'cli._familie' schnitt auf 14 Zeichen; das Urteil meldete 'Neues "
        "Hoch im ' - gekuerzt wird jetzt die Spalte, nicht der Name",
        178,
    ),
    # Eine Einschraenkung, die im Register stand und nicht ankam - das
    # Gegenstueck zu Befund 178, wo eine Richtung fehlte und zweimal gegangen
    # wurde.
    Richtung(
        "Auftrag an die Research-KI auf Befund 75",
        "Kopplung -0,533 statt der nachgemessenen -0,714, und als Eigenschaft "
        "des Vorrats statt einer Familie (169) - elf Befunde lang; jetzt samt "
        "Familienzaehlung und dem Preis aus 179",
        180,
    ),
    # Derselbe Fehler wie in Befund 56, an der zweiten Stelle - und er
    # filtert die Grundgesamtheit der Befunde 168, 169, 179, 180 und 181.
    Richtung(
        "Katalog nach Groessenlogik gefiltert",
        "9 von 30 Tagesgenomen lieferten null Trades, weil ihre "
        "'risiko'-Logik weite Stops ablehnt - mit der Logik des Bestands "
        "handeln sie 138, 103, 71 Mal; Signal und Betriebspunkt "
        "ausgeschlossen (182 Kreuzungen)",
        182,
    ),
    # Dieselbe Bauart, dritte Wiederholung - und sie sass in der
    # folgenreichsten Vorauswahl des Projekts.
    Richtung(
        "Nachgebaute Intervallpruefung an sechs Stellen",
        "'iv == interval_obj.value' statt passt_zum_intervall schloss die "
        "vier nicht festgelegten Generationen aus; 'cli paare' hat alle "
        "Donchian-Ausbrueche nie gesehen",
        184,
    ),
    # Vierter Ort desselben Filters aus Befund 182.
    Richtung(
        "Groessenlogik-Filter auch in 'cli holdout'",
        "erster Lauf mit --regel lieferte null Trades in allen vier "
        "Maerkten; jetzt auf der Logik des Bestands, wie in paare und "
        "vorratsdecke",
        185,
    ),
    # Ein an einem Betriebspunkt gemessenes Ergebnis als Gesetz eingebaut -
    # dieselbe Bauart wie 56/182/184, vierte Wiederholung.
    Richtung(
        "Kostenurteil sprach die Antwort von Tageskerzen",
        "'Die Kopplung liegt nicht an den Kosten' stand unbedingt im "
        "Urteil und haette auch bei Kippfaktor 2 dort gestanden; "
        "verzweigt jetzt an ERREICHBAR = 5 (Slippage steckt im "
        "Ausfuehrungspreis und laesst sich nicht abziehen)",
        187,
    ),
    Richtung(
        "Kostenfrage hatte seit Befund 78 keinen Aufrufer",
        "gebaut, mit neun Tests belegt, in cli.py kein einziges Mal - "
        "Taktpunkt.aus_trades faellt jetzt aus derselben Trade-Liste wie "
        "Kandidat.aus_trades, und 'cli vorratsdecke' rechnet sie mit",
        187,
    ),
    # Fuenfte Wiederholung derselben Bauart: an einem Vorrat gebaut, dessen
    # Gerade positiv beginnt, und diese Eigenschaft als gegeben genommen.
    Richtung(
        "Scheitelformel lieferte eine negative Stichprobe",
        "bei negativem Achsenabschnitt ergibt -a/(3b) ein n < 0 (auf "
        "Viertelstunden -2085); 'urteil' hat es formatiert und ist nach "
        "zweieinhalb Stunden Rechnen mit TypeError abgebrochen. scheitel_n "
        "und nullstelle liefern dort jetzt nichts, durchweg_ohne_vorteil "
        "benennt den Fall",
        188,
    ),
    # Sechste Wiederholung - und die einzige, die als **gute** Nachricht
    # herauskam. Ein Absturz meldet sich, eine gruene Zahl nicht.
    Richtung(
        "Der Bestand stand auf jeder Geraden",
        "Referenzpunkt hatte kein Feld fuer die Kerzenlaenge; auf "
        "Viertelstunden meldete der Lauf +5,64 Reststreuungen Vorsprung "
        "gegen 3,25 aus reiner Auswahl - ein Tageskandidat an einer Geraden "
        "aus 36 Regeln, die er nie gehandelt hat. Der Block wird jetzt "
        "uebersprungen, wenn die Kerzenlaengen nicht passen",
        190,
    ),
    # Siebte Wiederholung - und die erste, die durch Suchen statt durch
    # Zufall aufgefallen ist. Sie sass in jeder Katalogtabelle des Projekts.
    Richtung(
        "Jede Regel an der Verteilung des Bestands gemessen",
        "noetige_guete reichte Schiefe und Woelbung nie durch und rechnete "
        "mit den Vorgaben (3,473/15,951 - den Momenten des Bestands), "
        "waehrend das Gate die der Regel nimmt; 10 von 18 Tagesregeln "
        "standen dadurch zu milde da, am weitesten die EMA-Kreuzung mit "
        "0,643 Guetepunkten",
        191,
    ),
    # Achte Wiederholung. Elf Latten-Aufrufstellen nachgesehen: vier waren
    # richtig, drei auf der Vorgabe, drei haben keinen Kandidaten und
    # duerfen es sein. Der Kandidatenpfad ueber Budget.abstaende war immer
    # richtig - falsch waren die Stellen, die mit einer Stichprobe statt mit
    # einem Kandidatenobjekt rechnen.
    Richtung(
        "Auch die Wettrennen-Huerde stand auf der Vorgabe",
        "Rennen.huerde rechnete ohne Momente; bei n_eff 152 liegt der "
        "Schnittpunkt damit bei 8.041 Versuchen, mit neutraler Verteilung "
        "jenseits von 1e9. Ob die Suche je aufholt, aendert sich nicht - das "
        "haengt an Ideen- und Nullstreuung. Dazu die Linie am Spot-Punkt in "
        "'cli suchbudget' (0,3367 statt 0,3364)",
        192,
    ),
    # **Die Suche aus Befund 192 war selbst unvollstaendig.** Sie hat nach
    # noetig_bei und noetiger_sharpe gegriffen; die Schicht darueber hat
    # vierzehn eigene Aufrufer. Dieselbe Bauart wie der gesuchte Fehler.
    Richtung(
        "Sechs weitere Latten standen auf der Vorgabe",
        "darunter die Latte jedes Paares: Die Luecke aus Befund 184 ist 0,108 "
        "statt 0,064, und die Spitze wechselt von 'Grosser Trendausbruch' zu "
        "'Trendfolge Ausbruch'. Ein zaehlender Test laesst nur noch drei "
        "namentlich genannte Ausnahmen zu",
        193,
    ),
    # Kein behobener Fehler, sondern eine Rechnung, die nur als Prosa
    # existierte - dieselbe Lage wie bei 'kostenanteil' in Befund 187.
    Richtung(
        "Die Rangtreue stand seit Befund 186 nur im Laborbuch",
        "research/rangtreue.py rechnet sie jetzt nach und verweigert unter "
        "|t| = 2 die Aussage; der tragende Test reproduziert die "
        "veroeffentlichten +0,214 und +0,571",
        195,
    ),
    # Dritter Fehler im selben Artefakt (nach 180 und 183) - und der
    # folgenreichste: Er haette Versuche gekostet, nicht nur Zahlen.
    Richtung(
        "Der Auftrag verschwieg das Holdout-Ergebnis",
        "er nennt drei Kriterien fuer einen Partner und sagte nicht, dass "
        "sieben Partner sie erfuellt haben und alle sieben draussen "
        "durchgefallen sind; das Wort 'Holdout' kam im ganzen Text nicht vor",
        196,
    ),
    # Dieselbe Bauart wie Befund 157, diesmal im Bericht statt im Auftrag.
    Richtung(
        "Der Stand nannte drei ueberholte Fundstellen",
        "'Ob der Vorsprung echt ist' verwies auf 168, 169 und 171 - zwei "
        "davon in Befund 183 zurueckgenommen, die dritte in 188 ersetzt; "
        "ein Test verlangt jetzt, dass die berichtigenden Befunde dabeistehen",
        197,
    ),
    # Zweites Artefakt mit derselben Luecke wie der Auftrag in Befund 196.
    Richtung(
        "Der Wettbewerb stand ohne seinen Preis da",
        "BEIM_NUTZER sagte, wie man ihn startet, und nicht, dass jeder "
        "gepruefte Kandidat die Latte fuer alle folgenden hebt; der Satz "
        "wird jetzt aus dem Versuchsstand gerechnet und verbietet nichts",
        198,
    ),
    # Die in Befund 196 aufgeschobene Neurechnung - und sie faellt anders
    # aus als erwartet: Die Zahl traegt nicht mehr, also faellt die
    # Behauptung, nicht nur die Zahl.
    Richtung(
        "Der Auftrag nannte eine Vorhersage ohne Deckung",
        "'die eigene Qualitaet je Trade ordnet die Luecke' stand auf 14 "
        "Paaren mit rho = -0,53; ueber alle 18 sind es -0,410 bei t = -1,80. "
        "Punkt 2 ist jetzt als Herleitung ausgewiesen, nicht als Vorhersage",
        199,
    ),
    # Meine eigene Erklaerung zu Befund 200 war die halbe Wahrheit, und die
    # andere Haelfte dreht sie um - gefangen von einem Test aus derselben
    # Runde.
    Richtung(
        "Monotonie des z als Mechanik behauptet",
        "ein weiterer Stop wird seltener gerissen, kostet aber jedes Mal "
        "mehr; was ueberwiegt, haengt an der Reihe. Der Test prueft jetzt "
        "die garantierte Haelfte, der Modulkopf nennt die Monotonie eine "
        "Beobachtung",
        201,
    ),
    # Beide in derselben Runde entstanden und gefunden - dieselbe Bauart wie
    # Befund 190: eine Groesse, an einer Stelle gemessen, an einer anderen
    # verwendet.
    Richtung(
        "Der Stopabstand des ersten Marktes galt fuer alle",
        "der gemessene Abstand wurde in den Befehlszeilenparameter "
        "zurueckgeschrieben; bei volatilitaetsskalierten Stops (4,6 bis "
        "6,8 % ueber vier Maerkte) sind das andere Zahlen. Dazu ein "
        "TypeError, wo keine Trades am Ziel endeten",
        202,
    ),
    # Die zweite Haelfte hat sich **nicht** gemeldet: Eine Long-Null gegen
    # Short-Trades liefert Zahlen, nur keine richtigen.
    Richtung(
        "Die Zufallsprobe ist long, zwei Regeln nicht",
        "'EMA-Kreuzung (Messlatte)' und 'Volatilitaets-Ausbruch' handeln "
        "short; die Ziehung rechnet immer eine Long-Rendite. Beide Zeilen "
        "sind zurueckgezogen, solche Regeln werden jetzt abgewiesen statt "
        "falsch gemessen. Dazu: ein fehlendes Ziel kostet keinen Markt mehr",
        203,
    ),
    # Die andere Haelfte von Befund 203: abweisen war richtig, koennen ist
    # besser. Die Berichtigung dreht eine Zelle von +4,15 auf -2,31.
    Richtung(
        "Die Zufallsprobe kann jetzt short",
        "beide Ziehungen spiegeln die Seite jedes Trades - Stop ueber dem "
        "Einstieg, vom Hoch gerissen, Ziel darunter. Die zwei "
        "zurueckgezogenen Zeilen stehen neu; bei 'EMA-Kreuzung' auf XRP "
        "wird aus +4,15 ein -2,31",
        204,
    ),
    # Fuenf Befunde lang ein positives Ergebnis ohne die Frage, die dieses
    # Projekt an jede andere Zahl stellt. Die Lehre stand seit Befund 190
    # aufgeschrieben.
    Richtung(
        "Die Zufallsprobe rechnete die Suche nicht mit",
        "z = 2,00 ohne Korrektur, obwohl der Kandidat aus 198 Versuchen "
        "stammt; Bonferroni verlangt 3,48. Gedeckelt raeumen dann 2 von 4 "
        "statt 4 von 4, ungedeckelt keiner. Beide Zahlen stehen jetzt "
        "nebeneinander",
        205,
    ),
    # Der Kreis aus 202 bis 205, geschlossen im Artefakt, das kuenftige
    # Versuche steuert - und das erste Kriterium dort, das **vor** einem
    # Versuch greift.
    Richtung(
        "Der Auftrag nannte das Vorfilter nicht",
        "'woran es bei allen sieben lag' stand nirgends; jetzt nennt er die "
        "Zufallsprobe samt Befehl, das Ergebnis ueber zehn Partner und die "
        "Schwellenkorrektur aus 205. Die Sweep-Gegenprobe: von drei Modulen "
        "mit Signifikanzschwelle war nur zufallseinstieg betroffen",
        206,
    ),
    # Die Korrektur aus 205 im Code richtig, im Satz darueber fallen
    # gelassen - einen Befund spaeter.
    Richtung(
        "Das Vorfilter stand ohne seine Schwelle da",
        "'alle zehn Partner waeren haengengeblieben' gilt bei z = 3,48, "
        "nicht bei 2,00 - dort kommen zwei durch, und es sind acht von "
        "zehn. Auftrag und Befund nennen die Schwelle jetzt in derselben "
        "Zeile wie das Kriterium",
        207,
    ),
    # Befund 160 noch einmal - nur war AUSSICHT wenigstens getestet.
    Richtung(
        "Das offene Register stand in keinem Bericht",
        "OFFEN hatte im ganzen Projekt genau eine Fundstelle: seine "
        "Definition. Elf Eintraege, ueber Dutzende Befunde gepflegt, in "
        "keinem Bericht und in keinem Test. Jetzt als 'GEMESSEN UND OFFEN' "
        "zwischen den geschlossenen Richtungen und den Werkzeugbefunden, "
        "mit den Pruefungen, die GESCHLOSSEN seit Befund 90 hat",
        208,
    ),
    # Aus der Korrektur von 208 eine Regel gemacht - und die Suche nach
    # weiteren Faellen kam leer zurueck.
    Richtung(
        "Register wurden von Hand geprueft",
        "jedes Register hatte einen Test, der es beim Namen nennt - ein "
        "siebtes bekaeme keinen. Der Test sucht sie jetzt selbst und "
        "verlangt jeden Feldtext im Bericht, mit Gegenprobe. Die Suche nach "
        "weiterem Ungenutzten fand nichts: 75 von 79 research-Modulen "
        "haengen an Produktionscode, keines an gar nichts",
        209,
    ),
    # Die Sweep-Gegenprobe aus 209 konnte das nicht finden: Der Import war
    # da, der Test war da - nur die Vorgabe des Schalters stand auf aus.
    Richtung(
        "Behoben laut Register, unerreichbar in der Anleitung",
        "146 hat die KI an den Wettbewerb gehaengt und das Register auf "
        "behoben gesetzt; '--ki' steht seither auf aus, und die Zeile, der "
        "der Nutzer folgt, hat den Schalter nie genannt. Jetzt beide Wege "
        "als Befehlszeile, mit der Entscheidung samt Preis daneben",
        210,
    ),
    # Die fuenfte Fassung derselben Zahl - 121 hat vier gefunden und das
    # Feld fuer abgeraeumt gehalten.
    Richtung(
        "Neun Gates im Docstring des Analysten",
        "die Zahl, die in Befund 104 einundzwanzig Versuche gekostet hat, "
        "stand in '_ask_the_analyst' neunzig Befunde nach ihrer Berichtigung "
        "noch da. Die Ableitung aus 121 gilt weiter - sie erreicht nur "
        "keinen Docstring. Jetzt elf, mit Wache und Gegenprobe",
        210,
    ),
    # Mein eigener Fehler aus 210, einen Befund spaeter - und dieselbe
    # Bauart, vor der ich dort gewarnt habe.
    Richtung(
        "Aus fehlender Herkunft auf fehlende Quelle geschlossen",
        "210 behauptete, was die KI nach der Auftragskorrektur brachte, sei "
        "nirgends verzeichnet. Es steht in Befund 77 mit Tabelle, im "
        "AUFTRAG-Register und in trials.json - dort unter 'gen11 "
        "partnersuche', weil die Herkunft nach Lauf trennt und nicht nach "
        "Quelle. Bilanz berichtigt: neun Vorschlaege, keiner geraeumt",
        211,
    ),
    # Ein Startdatum fuer alle Kerzenlaengen - und fuer die eine, auf der
    # alle elf Gates stehen, war es das falsche.
    Richtung(
        "Der Ladehinweis schickte Tageskerzen auf 2320 Tage",
        "'--von 2020-03-30' stand als Vorgabe und im Hinweis bei zu kurzer "
        "Historie, auch fuer '-i D'. Gemessen ist das die zweitschlechteste "
        "der sechs Stufen: DSR 0,2969 statt 0,8640, acht Gates statt neun. "
        "Jetzt nach Intervall - D auf 2017-08-16, Feinkerzen unveraendert, "
        "weil dort die Reihe endet",
        212,
    ),
    # Die Tabelle aus 133 stand nur im Kopf des Moduls.
    Richtung(
        "Die Historienkurve war Prosa",
        "sechs gemessene Fenster im Docstring, nirgends nachrechenbar - wie "
        "kostenanteil (187) und die Rangkorrelation (195). Jetzt als "
        "'historie.GEMESSEN': Sammelrate 44,7 je 1000 Tage, 29 fehlende "
        "Beobachtungen, 649 Tage - alle drei aus den Daten gerechnet",
        212,
    ),
    # Und die andere Haelfte derselben Vorgabe, einen Befund spaeter.
    Richtung(
        "Der Ladebefehl holte nie Tageskerzen",
        "'backfill' laedt ohne '-i' die Vorgabe 1m/15m/1h/4h - **kein D**, "
        "und der Speicher fasst nicht selbst zusammen. Die Zeile fuer den "
        "Nutzer sagte '--von 2017-08-16' ohne Intervall, holte also vier "
        "Intraday-Reihen und keine der Kerzen, auf denen alle elf Gates "
        "stehen. Sechs solcher halben Hinweise gefunden und berichtigt, mit "
        "Wache gegen den siebten",
        213,
    ),
    # Die Pruefung aus 64 sass im Katalogzweig - und --von-spitze geht am
    # Katalog vorbei.
    Richtung(
        "--von-spitze umging die Intervallpruefung",
        "das Intervall stand dann auf dem der Vorgabegeneration, und die ist "
        "ein Viertelstunden-Katalog: Varianten von 'Trend 50 Tage' auf "
        "15-Minuten-Kerzen, wo 50 Balken zwoelfeinhalb Stunden sind. Jetzt "
        "'_pruefe_spitze' gegen SPOTPUNKT.intervall, abgebrochen statt "
        "gewarnt - so ein Lauf kostet Versuche",
        214,
    ),
    # Meine eigene Aenderung aus 213, einen Befund spaeter nachgezogen.
    Richtung(
        "Laden und Suchen liefen auf verschiedenen Kerzen",
        "213 stellte die Ladezeile auf '-i D'; der Schritt danach lief "
        "weiter auf Vorgabegeneration 8, also Viertelstunden, und waere am "
        "leeren Speicher abgebrochen. Jetzt '--generation 9', dazu eine "
        "Wache, die beide Zeilen gegeneinander prueft",
        214,
    ),
    # 214 hat das Register geradegezogen und die README nicht angesehen -
    # dabei steht dort dasselbe Paar, und es wird zuerst gelesen.
    Richtung(
        "Dieselbe Fehlpaarung in der README",
        "drei Bloecke: der Schnelleinstieg lud D und suchte mit Vorgabe 8 "
        "auf Viertelstunden, die Windows-Kurzfassung lud 1m/15m/1h/4h und "
        "suchte mit 'research' auf Tageskerzen. Beide berichtigt; die Wache "
        "aus 214 prueft jetzt auch die Codebloecke der Anleitung",
        215,
    ),
    # Der Docstring sagte "endlich im System statt nur im Text" - und es
    # stand nur im Text.
    Richtung(
        "Das Suchbudget brach nichts ab",
        "BUDGET kam nur in 'rennen' und 'suchbudget' vor, beides berichtende "
        "Befehle; der Wettbewerb las es nie und laeuft mit '--runden 0' bis "
        "Strg-C. Die Berichtszeile versprach 'Abbruch bei 230', abgebrochen "
        "hat nichts. Jetzt greift die Grenze vor jeder Runde, mit "
        "'--ueber-das-budget' als bewusstem Weg darueber hinaus",
        216,
    ),
    # Die Frage aus 214 - und wo noch? - hat einen ganzen Befehl gefunden.
    Richtung(
        "Die Nachpruefung mass 23 von 53 Genomen falsch",
        "'cli nachpruefung' nimmt Generation und Intervall und rief keine "
        "der beiden Wachen; ohne Argumente sind das alle Generationen auf "
        "'-i D', darunter 23 Genome aus Viertelstunden-Katalogen. Kostet "
        "keinen Versuch, faellt aber ein Urteil. Fremde Generationen werden "
        "jetzt uebersprungen und benannt; eine Wache zaehlt alle Befehle "
        "auf, die beides annehmen",
        217,
    ),
    # Die Frage war gebaut und nie gestellt - und die Antwort ist fuer den
    # einen Betriebspunkt unbequem.
    Richtung(
        "Die Randfrage der Skalenleiter blieb ungestellt",
        "'am_rand' hatte ausserhalb der Tests keinen Aufrufer, das Register "
        "behauptete aber, es stelle die Frage von selbst. Beide Leitern aus "
        "143 liegen jetzt als 'zeitskala.GEMESSEN' vor und sind gefragt: "
        "Tageskerzen nein (Quartal, n_eff 112), Viertelstunden **ja** "
        "(Gleichzeitigkeit, erste Sprosse)",
        218,
        zuletzt=219,
    ),
    # Meine eigene Warnung aus 218 zurueckgenommen: Sie fragte nach beiden
    # Enden der Leiter, und nur eines ist eine Luecke.
    Richtung(
        "Die Randwarnung traf das falsche Ende",
        "'am_rand' meldet beide Enden. Am groben gibt es weitere Sprossen, "
        "die nur niemand gemessen hat; am feinen gibt es keine - unter der "
        "Gleichzeitigkeit muesste man zusammen offene Positionen trennen, "
        "und 'designeffekt' gibt fuer Bloecke der Groesse eins ohnehin None. "
        "'am_groben_rand' trennt das jetzt; die Viertelstunden-Leiter ist "
        "damit **keine** offene Frage, wie 218 gemeldet hatte",
        219,
    ),
    # Beide Punkte lange gemessen, der Vergleich nie gezogen - weil er
    # direkt nicht geht.
    Richtung(
        "Welcher Betriebspunkt naeher am Ziel steht, war unbeziffert",
        "Guete gegen fremde Latte zu halten ist der Fehler aus 190; das "
        "Verhaeltnis je Punkt fuer sich ist es nicht. Gerechnet: Tageskerzen "
        "0,804 der eigenen Latte, beste Viertelstundenregel 0,188 - das "
        "4,3-fache. Die feine Kerze senkt die Latte je Trade (0,164 gegen "
        "0,337) und nicht insgesamt",
        220,
    ),
    # Die eigene Signatur des Projekts: eine Groesse von einem Betriebspunkt
    # an einem anderen benutzt - diesmal in der Warnung vor dem Suchen.
    Richtung(
        "0,00021 je Versuch war der Wert von 130",
        "an vier Stellen als Konstante zitiert; gemessen faellt der Anstieg "
        "mit dem Zaehler - 0,000212 bei 130, 0,000135 bei 198, 0,000115 bei "
        "230. Der Rest des Budgets kostet 1,18 % gegen eine Luecke von "
        "24,3 %. 'versuchskosten' rechnet es jetzt, die Wache prueft mit dem "
        "Tokenizer, dass niemand wieder mit der festen Zahl rechnet",
        221,
    ),
    # Zehnter Fall - und der erste, der in die andere Richtung irrt.
    Richtung(
        "Der letzte offene Weg stand mit +13 % da",
        "Befund 70 hat ihn so beziffert, bei Guete 0,260 und n_eff 152. Am "
        "heutigen Punkt sind es +24,3 % - fast das Doppelte, und die Zahl "
        "stand im Kopf von 'wettrennen' und im Docstring von 'cli rennen', "
        "also dort, wo ueber Weitersuchen entschieden wird. Jetzt "
        "'erfuellung.Betriebspunkt.luecke'",
        222,
    ),
    # Gesucht statt gelesen - und der erste Treffer war mein eigener, drei
    # Befunde alt, im Modul gegen genau diesen Fehler.
    Richtung(
        "Der Kopf von erfuellung mischte drei Betriebspunkte",
        "'0,0968 je Trade statt 0,3406' - 0,0968 gilt bei n_eff 1830, der "
        "ganzen Leiter statt der Regel (584), 0,3406 bei n_eff 112, dem vor "
        "152 ueberholten Punkt. Die Daten des Moduls sagen 0,1640 und "
        "0,3367. Die Wache haelt den Kopf jetzt an den Daten fest",
        223,
    ),
    # Die Wache aus 223 stand an einem Modul; drei weitere haben dieselbe
    # Bauart, und das vierte hat der Abdeckungstest selbst gefunden.
    Richtung(
        "Nur ein Modulkopf war an seine Daten gebunden",
        "historie (seit 212), zeitskala (218) und koernung tragen ihre "
        "Messung ebenfalls zweimal. Nachgemessen: alle drei stimmen, sie "
        "standen nur ungeprueft. Die Wache deckt jetzt alle vier ab und "
        "verlangt von jedem neuen Modul mit 'GEMESSEN', dass es dazukommt - "
        "so ist koernung aufgefallen. Dabei ein Namensdrift in erfuellung "
        "berichtigt: Kopf 'Bestand (Befund 152)', Daten 'Spot wie gebaut'",
        224,
    ),
    # Der Schluss haelt, die Zahlen nicht - und der Weg ist heute weiter zu,
    # nicht weniger.
    Richtung(
        "Der Schiefe-Weg stand mit den Zahlen von Befund 70 da",
        "'ab 5,54 (+60 %)' und 'Max DSR 0,8724' im Kopf von formgrenze; am "
        "heutigen Punkt sind es +96 % und 0,6212. Der Schluss - ueber die "
        "Schiefe nie erreichbar - ist unveraendert und deutlicher. Die Linie "
        "aus 70 laesst sich jetzt aus ihren Koeffizienten rekonstruieren, "
        "'am_punkt' rechnet die drei Wege, und die Kopfwache deckt das Modul "
        "mit ab",
        225,
    ),
    # Befund 221 hat den Satz geschrieben und ihn selbst nicht befolgt.
    Richtung(
        "Die zwei Zahlen der Entscheidung standen auseinander",
        "221 schloss, Preis des Suchens und Luecke gehoerten in denselben "
        "Satz - und legte die Luecke ins Urteil, den Preis unter 'Nur auf "
        "deinem Rechner'. Jetzt beide unter 'Wie weit es noch ist': +24,3 % "
        "zu schliessen, +1,18 % kostet der ganze Rest des Budgets, also ein "
        "Zwanzigstel - mit dem Gegengewicht aus Befund 71 daneben",
        226,
    ),
    # 220 hat Kerzenlaengen verglichen und den einzigen gemessenen Hebel
    # ausgelassen.
    Richtung(
        "Der Verbund fehlte im Erfuellungsvergleich",
        "im selben Lauf (155) raeumt der Verbund 0,819 seiner Latte, die "
        "Regel allein 0,745 - der Zugewinn ist aber Stichprobe (n_eff 114 "
        "auf 136) und nicht Qualitaet (0,2520 auf 0,2560; Vorzeichentest "
        "p = 0,94). Beide Zeilen tragen jetzt ihren Lauf, und verglichen "
        "wird nur innerhalb eines Laufes",
        227,
    ),
    # Zwei von drei Dimensionen des Betriebspunkts standen im Bericht.
    Richtung(
        "Berichte vermerkten das Instrument nicht",
        "Intervall steht seit 190 im Bericht, Versuche seit jeher, das "
        "Instrument nirgends - '_betriebspunkt' liest es jetzt an Genom und "
        "Konfiguration ab. Die Begruendung in 228 war falsch und ist in 229 "
        "berichtigt: Der Bericht widersprach 'cli stand' nicht. 228 hat es "
        "fuer eine von fuenf Berichtsarten eingebaut; seit 242 fuehren alle "
        "fuenf das Feld - machbarkeit, nachpruefung, teststaerke und der "
        "Zulassungsbericht aus 'cli research' dazu. Dort ist es der Punkt "
        "des Champions und ohne Champion leer, weil ein Lauf mehrere Genome "
        "prueft und der Hebel im Genom steht",
        228,
        zuletzt=242,
    ),
    # Mein Fehler aus 228, einen Befund spaeter.
    Richtung(
        "Zweitpunkt fuer Erstpunkt gehalten",
        "228 las 'cli stand sagt 9 von 11' aus SPOTPUNKT ab - das ist der "
        "**zweite** Punkt. Primaer rechnet 'stand' auf Perpetual, und die "
        "7 von 11 des Berichts stimmen damit ueberein. Beide Punkte sind "
        "gepflegt (108); getrennt sind Anzeige (Perpetual zuerst) und "
        "Analysebezug (SPOTPUNKT) - und genau das gehoert vermerkt",
        229,
    ),
    # Und derselbe Riss lief durch den Bericht - eingebaut von mir in 226.
    Richtung(
        "Zwei Luecken in einem Bericht",
        "das Urteil rechnete sie aus den eigenen Zahlen (+15,0 % am "
        "Erstpunkt), der Abschnitt 'Wie weit es noch ist' aus SPOTPUNKT "
        "(+24,3 %) - eine Seite auseinander, ohne Hinweis. Jetzt beide aus "
        "den eigenen Zahlen; der Preis des Suchens bleibt daneben stehen "
        "und ist nachgemessen fast punktunabhaengig (1,11 bis 1,26 % ueber "
        "n_eff 80 bis 584)",
        230,
    ),
    # Und danach gesucht statt gelesen - diesmal ohne zweiten Fund.
    Richtung(
        "Der Bericht war sonst widerspruchsfrei",
        "25 Prozentwerte, zwei davon in zwei Abschnitten, beide zu Recht "
        "(Hebelnutzung 0,2 % aus 106; die Preisobergrenze 1,26 % aus 230 im "
        "Abschnitt und im Register). Kein zweiter Fall von 230. Die Wache "
        "haelt den Stand fest und meldet jeden neuen Doppelgaenger",
        231,
    ),
    # Nicht mehr am Bericht, sondern am Lauf, der die Versuche ausgibt.
    Richtung(
        "Der Wettbewerb sagte nicht, was er gekostet hat",
        "die Schlusszeile nannte gepruefte Strategien, nicht ausgegebene "
        "Versuche - und die sind die knappe Groesse. Jetzt '_laufbilanz': "
        "wieviele der Lauf gekostet hat, was vom Budget bleibt, und wo Preis "
        "und Luecke stehen. Bei null Versuchen steht dort nichts von Kosten",
        232,
    ),
    # Meine Behauptung aus 216 war falsch: Es ist nicht ein Befehl, es sind
    # fuenf.
    Richtung(
        "Die Budgetgrenze galt fuer einen von fuenf",
        "216 nannte den Wettbewerb 'den einzigen Befehl, der Versuche in "
        "einer Schleife ausgibt'. Fuenf schreiben den Zaehler fort; "
        "'research' prueft einen ganzen Katalog auf einmal und sah die "
        "Grenze nie an, 'landschaft' zaehlte stumm. Beides behoben, die "
        "beiden Sweeps melden ihre Kosten von selbst",
        233,
    ),
    # Die zweiundzwanzigste Stelle aus dem Kopf von 'referenz.py' - und die
    # eine, die der Bericht als naechsten Schritt hervorhebt.
    Richtung(
        "Die Handlungsliste stand auf dem Stand von Befund 108",
        "'WAS DEN ZUSTAND AENDERN KANN' trug feste Zahlen aus einer Zeit mit "
        "effektiver Stichprobe 152 - die Guete-Luecke stand dort auf einem "
        "Drittel des gemessenen Werts, und der Punktschaetzer des Wettrennens "
        "aus Befund 110 ist gekippt, weil die Nullstreuung ueber die "
        "Ideenstreuung gestiegen ist (die Spanne dazu in 236). Beide "
        "Bedingungen werden jetzt gerufen statt geschrieben; die Zahlen "
        "stehen im Bericht, nicht hier. Dafuer "
        "steht 'PERPETUALPUNKT' neben 'SPOTPUNKT', weil 'Rennen.bester' das "
        "braucht, was die Suche hervorgebracht hat",
        235,
        zuletzt=236,
    ),
    # Ein Modulkopf, der eine Datenlage behauptet, die es nicht mehr gibt.
    Richtung(
        "'Mehr gibt es nicht' galt seit Befund 83 nicht mehr",
        "'wettrennen.py' nannte den Bestwert die einzige Beobachtung ihrer "
        "Art und kalibrierte die Ideenstreuung aus diesem einen Wert. Im "
        "Verzeichnis liegen acht gegen die Spezifikation **gebaute** Regeln "
        "(Befunde 77 und 83), samt und sonders gemessen, also Ziehungen und "
        "keine Ueberlebenden. 'research.ideenstreuung' schaetzt daraus direkt "
        "und zieht die Schaetzfehler ab - noetig, weil der Standardfehler bei "
        "18 Trades groesser ist als die gesuchte Groesse. Die zweite Zahl "
        "liegt hoeher als die Rueckrechnung; entschieden ist damit nichts, "
        "denn kein Sprachmodell hat diese Regeln vorgeschlagen und keine "
        "davon taugte",
        237,
        zuletzt=238,
    ),
    # Der Fund aus 239 und die Wache dagegen aus 240 - zusammen, weil das eine
    # ohne das andere genau die Sorte Bauteil waere, die 213 gefunden hat.
    Richtung(
        "Die letzte Tageskerze war ein halber Tag",
        "der Backfill schrieb sie mittags und zog sie nie nach: 52 % des "
        "Volumens, 'high' und 'close' um 0,48 % und 0,76 % zu tief, und in "
        "der Reihe stand sie wie eine volle. Gemessen kostet sie nichts - mit "
        "und ohne sie sind alle Zahlen des Bestands gleich. Tragend ist dabei "
        "allein der Randschnitt (152): Der Nachlauf haelt die Fenster zehn "
        "Tage vom Rand weg, die Trades nicht - zwei laufen bis genau dorthin, "
        "und mit ihnen bewegt die halbe Kerze die Guete um 0,0005 nach oben. "
        "'cli quality' prueft es jetzt gegen die feinste teilbare Reihe im "
        "Speicher, als Warnung und nicht als Fehler",
        239,
        zuletzt=241,
    ),
    # Der zweite Fall derselben Bauart wie 241: Es traegt etwas, nur nicht
    # das Bauteil, dem man es zuschreiben wuerde.
    Richtung(
        "'suchbudget' rechnete jeden Katalog auf jeder Kerzenlaenge",
        "es sammelte ueber alle Generationen - auf Tageskerzen 23 von 53 "
        "Regeln aus den Viertelstunden-Katalogen. Verfaelscht hat das nichts: "
        "Keine davon kommt in die Rangliste, sie fallen vorher an der "
        "Trade-Zahl heraus, und die Ausgabe ist vor und nach der Wache "
        "zeichengleich. Der Schutz war also ein Filter und keine Absicht. "
        "Gekostet hat es Rechenzeit (54 Kandidaten in 78 s gegen 31 in 48 s). "
        "Die Abdeckung ist jetzt vollstaendig und wird geprueft - nach "
        "beiden Wachen, denn acht Befehle nutzen 'passt_zum_intervall' "
        "direkt und waren im ersten Durchgang falsch als Luecke gemeldet",
        243,
    ),
    # Dieselbe Frage fuer die naechste Wache - und derselbe erste Fehlgriff.
    Richtung(
        "'teststaerke' schrieb an der Berichtswache vorbei",
        "es baute Ordner, Zeitstempel und Datei von Hand und ging damit an "
        "drei Dingen vorbei, die in 'write_report' stecken: der "
        "Trockenlauf-Wache aus 116, 'scrub' gegen Felder fuer ein "
        "oeffentliches Repository, und dem Schutz gegen zwei Laeufe in "
        "derselben Sekunde. Gemessen: Ein Lauf mit gesetztem Trockenlauf "
        "legte trotzdem eine Datei ab, waehrend der Versuchszaehler korrekt "
        "stehenblieb. Gekostet hat es nichts - die vorhandenen Berichte "
        "stammen aus echten Laeufen und tragen kein verbotenes Feld. Jetzt "
        "ueber 'write_report', und eine Wache prueft, wer sonst noch nach "
        "'reports' schreibt",
        244,
    ),
    # Die Fehlerart hinter dem gefallenen Test aus 244, einmal durchgesucht.
    Richtung(
        "Ein Test hielt einen Mangel fest statt einer Zusicherung",
        "242 schrieb 'assert write_report not in quelle' - gemeint war 'sie "
        "zaehlt mit', dagestanden hat 'sie schreibt selbst, und dabei bleibt "
        "es'. Solche Tests sind gruen, bis jemand das Richtige tut. Alle "
        "sechzehn Wachennamen durchsucht: ein weiterer Treffer, und der ist "
        "richtig - die Sweeps brechen bewusst nicht am Budget ab, weil das "
        "die offene Frage aus 233/234 im Vorbeigehen beantworten wuerde. Eine "
        "Wache verlangt jetzt fuer jede solche Zusicherung einen Eintrag mit "
        "Grund und Fundstelle; falsche Werte findet sie nicht, dagegen hilft "
        "nur die Bindung an eine Messung",
        245,
        zuletzt=246,
    ),
    # Die Grenze aus 245, nachgesehen: Es gab einen solchen Fall.
    Richtung(
        "Ein Testkopf nannte einen ueberholten Punkt 'den' Betriebspunkt",
        "'test_wettrennen' baute seine Faelle mit der Stichprobe vor Befund "
        "152 und dem Spot-Wert in 'bester', wo der Suchwert hingehoert - und "
        "der Kopf nannte das den geltenden Punkt. Die Tests selbst waren "
        "richtig: Sie zeigen, dass die Momente Huerde und Schnittpunkt "
        "verschieben, und das laesst sich nur an einem festen Punkt zeigen - "
        "am heutigen gibt es keinen Schnittpunkt mehr. Der Punkt heisst jetzt "
        "nach seinem Befund, daneben stehen vier Tests ohne eine einzige Zahl "
        "im Quelltext, und vier Stellen in 'test_auftragslage' sind an "
        "SPOTPUNKT gebunden",
        246,
    ),
    # Kein Fund, sondern eine Bestaetigung - und das Wissen, das der Lauf
    # vorher gebraucht hat.
    Richtung(
        "Der Rauchtest aus 104 war nie wiederholt worden",
        "52 Befehle mit ihren Voreinstellungen unter Trockenlauf: kein "
        "Traceback, Zaehler vor und nach dem Lauf 198. Die drei mit Exit "
        "ungleich null lehnen sauber ab und sagen, was fehlt - die Lehre aus "
        "103 haelt, und 'sperrprobe' nennt seine Laufzeit von selbst (105). "
        "Geblieben ist die Einteilung, die der Lauf vorher brauchte: "
        "siebzehn Befehle wirken nach aussen, 52 nicht, beide Seiten einzeln "
        "aufgezaehlt. Der erste Entwurf rechnete die harmlosen als Differenz "
        "und war damit tautologisch - ein neuer Befehl waere stillschweigend "
        "als harmlos durchgegangen",
        247,
    ),
    # Die Klage aus 114, eine Ebene hoeher - diesmal am eigenen Bericht.
    Richtung(
        "Der Bericht stellte 750 Zeilen vor die erste Aufgabe",
        "'cli stand' war auf 1.053 Zeilen gewachsen; die drei Abschnitte, die "
        "etwas von ihrem Leser verlangen, begannen bei Zeile 754 - davor die "
        "beiden Archive. '--kurz' laesst genau die weg und sonst nichts: 563 "
        "Zeilen, erste Aufgabe bei 264. Der Schnitt steht nicht nach Gefuehl, "
        "sondern nach dem, was die Register selbst sagen ('sagt nichts ueber "
        "die Aussichten'). Gerechnet wird unveraendert dasselbe - ein Test "
        "haelt fest, dass das Kuerzen erst nach dem Walk-Forward greift",
        248,
    ),
    # Beim Lesen des gekuerzten Berichts aufgefallen - 248 hat es sichtbar
    # gemacht.
    Richtung(
        "Die Befehle fuer den Nutzer standen nicht in ihrer Folge",
        "'abgleich' stand an zweiter Stelle, obwohl sein Text 'Vor jedem "
        "Livegang auszufuehren' sagt, und 'funding' an letzter, obwohl bis "
        "dahin jede Zahl mit dem Vorgabewert fuer den groessten Kostenblock "
        "rechnet - wer so sucht, zahlt Versuche fuer Ergebnisse auf "
        "geschaetzten Kosten. Jetzt: klaeren, laden, suchen, abgleichen. Von "
        "den vier Bedingungen war eine schon geprueft ('erst laden, dann "
        "suchen'); die drei ungeprueften waren genau die, die danebengingen",
        249,
    ),
    # 249 hat den Funding-Eintrag nach vorn geholt, weil an ihm Versuche
    # haengen. Beim Nachlesen, wie viel genau: Die Zahl stand nur als
    # Sprossenpaar da.
    Richtung(
        "Der Spielraum beim Funding war doppelt so gross notiert",
        "Die Leiter aus Befund 100 meldete 'zwischen 5,5 % und 11 % kippen "
        "zwei Gates' - wahr, aber es ist **ein Abstand der Leiter und keiner "
        "des Kandidaten**. Je Gate nachgemessen: 'Schlechtestes Jahr' faellt "
        "bei 6,0 % im Jahr, 'Parameter-Plateau' erst bei 9,8 % - 3,7 Punkte "
        "dazwischen. Der Spielraum bis zum ersten Durchfaller ist also 6,0 % "
        "und nicht 11 %, gut die Haelfte des Vorgabewerts, mit dem gerechnet "
        "wird. 'cli finanzierung --kipppunkt' sucht ihn je Gate auf 0,11 "
        "Punkte genau und kostet keinen Versuch",
        250,
    ),
    # Beim Nachsehen, ob die wichtigste offene Richtung ueberhaupt zu
    # verfolgen ist (256 hatte sie dazu gemacht).
    Richtung(
        "Die Bestenliste kannte nur die kleinere ihrer zwei Luecken",
        "'vergleichbar' meldet mit '?', dass die Huerde zu einer Zahl fehlt - "
        "dann steht die Zahl wenigstens noch da. Fehlen die **Regeln**, ist "
        "der Kandidat weg, und dafuer gab es kein Zeichen, keine Zaehlung und "
        "keine Zeile. Genau so ging 'Neues Hoch im Takt' verloren, die "
        "einzige gemessene Regel, die die Kopplung bricht (Befund 74). Jetzt "
        "stehen beide getrennt: '?' fuer die fehlende Huerde, '*' fuer den "
        "fehlenden Kandidaten - und die teurere nicht als Fussnote. Der "
        "Registereintrag dazu hielt die Richtung fuer messbar und sagt jetzt, "
        "dass die Regel neu zu bauen waere",
        257,
    ),
    # Beim Weiterlesen: Wer soll die Regel neu bauen? Der Analyst - und der
    # bekam im Wettbewerb gar nicht zu wissen, was es schon gibt.
    Richtung(
        "Die KI bekam im Wettbewerb keine Ausschlussliste",
        "'parse_proposals' lehnt einen Doppelgaenger ab und sagt dabei, was er "
        "kostet, wenn er **nicht** abgefangen wird: 'admission' zaehlt jedes "
        "Genom, das es erreicht (259). Damit das greift, muss 'already_tried' "
        "stimmen - "
        "und es kam allein aus 'state/journal.json'. Das schreibt nur 'cli "
        "research'; 'cli wettbewerb' nicht. Auf dem Weg, den der Nutzer gehen "
        "soll ('wettbewerb --ki'), war die Liste also **leer**, waehrend die "
        "Bestenliste mit ihren gemessenen Regeln danebenlag - 'cli vorschlag' "
        "hat sie die ganze Zeit richtig gelesen. Jetzt liest '_ask_the_analyst' "
        "sie selbst und vereinigt beide Quellen; die Zahl steht im Lauf, weil "
        "eine stille Liste von einer leeren nicht zu unterscheiden ist",
        258,
    ),
    # Beim Nachlesen des Satzes, auf den sich 258 gestuetzt hat.
    Richtung(
        "Der Ablehnungstext sagte das Gegenteil dessen, was er tat",
        "'parse_proposals' meldete einen abgefangenen Doppelgaenger mit "
        "'zaehlt trotzdem als Versuch'. Der Satz stammt aus dem Modulkopf, "
        "wo er stimmt - **ungefiltert** wird ein Doppelgaenger getestet, und "
        "'admission' zaehlt jedes Genom, das es erreicht. An der "
        "Ablehnungsstelle ist er aber gerade abgefangen worden und erreicht "
        "'admission' nie: Dort kostet er null. Der Nutzer las im Moment der "
        "guten Nachricht, er habe etwas verloren - und Befund 258 hat den "
        "Satz als Begruendung zitiert. Die Kette ist jetzt festgehalten: "
        "'genomes' filtert auf 'accepted', nur 'genomes' geht weiter, und "
        "'admission' zaehlt, was ankommt",
        259,
    ),
    # Am anderen Ende derselben Schleife nachgesehen: Wer schreibt eigentlich
    # das Journal, aus dem 258 mitliest?
    Richtung(
        "Der Lernmechanismus war an einem Ende angeschlossen",
        "Am Ende jeder Wettbewerbsrunde steht: *'Die KI wird nach der Runde "
        "gefragt, nicht davor: Damit sieht sie im Journal, woran die letzten "
        "Kandidaten gescheitert sind.'* Der Aufruf steht richtig - nur "
        "schreibt das Journal dort niemand, 'write_journal' haengt allein an "
        "'cli research'. Jede Runde fragte die KI also, damit sie sieht, was "
        "gerade gescheitert ist, und sie sah eine Datei, die es nicht gibt. "
        "Jetzt schreibt der Wettbewerb sie, je Runde und vor dem Fragen. "
        "Dabei nachgetragen: 'write_journal' war die einzige der drei "
        "schreibenden Stellen ohne Trockenlauf-Wache (Befund 116)",
        260,
    ),
    Richtung(
        "Die Lernschleife war nur an ihren Enden geprueft",
        "Schreiber und Leser des Journals hatten je ein eigenes Pruefstueck - "
        "'write_journal' gegen einen erfundenen Bericht, 'build_prompt' gegen "
        "ein von Hand gebautes Journal. Laufen die Schluessel auseinander, "
        "bleiben beide gruen und die Schleife liefe leer weiter; dieselbe "
        "Bauart wie 168, 250, 258. Jetzt faehrt ein Test die Strecke am "
        "Stueck: echter Bericht, auf die Platte, zurueck, und beides geprueft, "
        "was der Wettbewerb daraus zieht - Kennung und Rueckmeldung. Nebenbei "
        "festgehalten: 'journal[-6:]' meinte bis 260 sechs Laeufe und meint "
        "jetzt sechs Runden, also eine engere und staerker korrelierte "
        "Scheibe. Die Zahl bleibt, weil jede andere geraten waere",
        261,
    ),
    # Weiter auf dem Weg des Nutzers: nach 'wettbewerb' kommt 'abgleich'.
    Richtung(
        "Der letzte Schritt vor dem Geld prueft die falsche Strategie",
        "'cli abgleich' traegt im Kopf 'Vor jedem Livegang auszufuehren' - "
        "gehandelt wird aber von 'cli trade', und das laeuft ausschliesslich "
        "auf 'strategies/champion.json'; ohne die Datei verweigert es den "
        "Dienst. 'abgleich' nahm 'spitzenkandidat()', den fest verdrahteten "
        "Saatkandidaten. Ohne zugelassenen Champion faellt das zusammen - "
        "deshalb ist es nie aufgefallen; **sobald einer da ist, und das ist "
        "das Ziel, prueft der letzte Schritt vor dem Geld etwas anderes als "
        "das, was gleich handelt.** Jetzt laedt 'abgleich' dieselbe Datei wie "
        "'trade', faellt nur ohne sie auf den Saatkandidaten zurueck und sagt "
        "in beiden Faellen, welches Genom es geprueft hat",
        262,
    ),
    # Die offene Stelle aus 262, nachgesehen - und sie war groesser.
    Richtung(
        "Die Kerzenlaenge stand im Nachweis und wurde nie verglichen",
        "'Zulassungsbedingungen' haelt seit Befund 106 fest, unter welchen "
        "Bedingungen ein Champion bestanden hat, und 'cli trade' prueft davon "
        "**eines**: das Instrument. 'intervall' steht im selben Nachweis, "
        "'_bedingungen' schreibt es bei jedem Lauf mit - verglichen hat es "
        "niemand. Dabei gilt die Begruendung wortgleich: Die elf Gates sind "
        "auf einer Kerzenlaenge gemessen; auf Tageskerzen stehen alle elf "
        "(213), auf Viertelstunden raeumt der beste Fund 0,188 seiner Latte "
        "(190). 'cli trade --intervall 15' haette mit einem Tageskerzen-"
        "Champion gehandelt, ohne ein Wort. Jetzt bricht 'trade' dort ab wie "
        "beim Instrument, und 'abgleich' warnt - dort laeuft kein Geld, aber "
        "eine Freigabe ist es auch nicht. **Weiter nicht aufgezeichnet ist "
        "der Markt selbst**: Der Nachweis kennt 'perpetual/spot' und die "
        "Kerzenlaenge, aber kein Symbol",
        263,
    ),
    # Nach dem Nachweis die Rechnung selbst: Was 264 als Umfang aufschrieb,
    # kostet Funding - und dem wurde nachgegangen.
    Richtung(
        "Die geladenen Funding-Raten wurden gesehen und nie gezahlt",
        "Zwei Stellen, dieselbe Folge. **Erstens der Schluessel**: 'cli "
        "funding' schreibt unter dem Kontrakt ('BTCUSDT'), 'cli wettbewerb' "
        "las unter dem Kursdatensymbol ('BTCUSD_BITSTAMP') - nachgemessen 0 "
        "gegen 30 Zeilen, und 'attach_funding' setzt daraufhin ueberall NaN - "
        "die Funding-Indikatoren waeren im Wettbewerb **auch mit vollem "
        "Speicher** NaN geblieben, und anders als 'cli research' warnt er "
        "nicht davor. "
        "**Zweitens die Rechnung**: 'attach_funding' schreibt an die Kerzen, "
        "gezahlt wird aber ueber 'BacktestConfig.funding' - und 'rates=' kam "
        "in der ganzen Anwendung kein einziges Mal vor, nur in einem Test. "
        "Wer 'cli funding' laufen liess, aenderte damit, was die Strategie "
        "**sieht**, nie, was sie **zahlt**; gezahlt wurde ausnahmslos der "
        "Vorgabewert. Der Funding-Block ist rund das Neunfache der Gebuehren "
        "(100), und der Bericht verspricht dem Nutzer genau diesen "
        "Unterschied. Jetzt baut 'schedule_from_frame' aus den geladenen "
        "Raten das Kostenmodell - je Bein die eigenen, Luecken behalten den "
        "Vorgabewert -, der Wettbewerb sagt vor der Suche, wie viele geladen "
        "sind, und 'funding_raten' steht im Zulassungsnachweis: Ohne "
        "die Zahl sagt 'funding_satz' ab hier nicht mehr die Wahrheit",
        265,
    ),
    # Nachgesehen am Gate, das dem Bestehen am naechsten steht - und dort war
    # viererlei zu finden, alles derselben Sorte.
    Richtung(
        "Das Messlatten-Gate faellt nicht an der Messlatte",
        "'gate_benchmark' prueft zweierlei: risikobereinigt besser als Halten, "
        "und eine Jahresrendite ueber der Betriebsschwelle von 15 %. Der "
        "Bestand ist an der **ersten** nicht knapp, sondern beim Fuenffachen "
        "(192,01 % gegen eine heruntergefahrene Latte von 38,03 %); offen ist "
        "die zweite, und dort fehlen 0,66 Punkte. Gemeldet wurden trotzdem "
        "Rendite und Latte - also die Bedingung, die **bestanden** ist: Wert "
        "192,012 gegen Schwelle 38,031 bei Status DURCHGEFALLEN, und das an "
        "zehn Ausgabestellen samt Bestenliste und Journal. Jetzt meldet das "
        "Gate die bindende Bedingung; bestandene Eintraege aendern sich "
        "nicht. **Daneben drei stehengebliebene Zahlen**: 'stand.py' rechnete "
        "die Luecke richtig und nannte sie 'die Messlatte'; 'finanzierung.py' "
        "fuehrte zweimal '0,17 Punkte' - die Zahl, die Befund 165 in "
        "'stand.py' laengst zurueckgenommen hatte, hier von einem Test am "
        "Leben gehalten, einmal davon in einem **erzeugten** Bericht; und die "
        "Leiter im Modulkopf trug durchgehend die Renditen eines alten Laufs, "
        "jede rund einen halben Punkt zu hoch (14,83 gegen gemessene 14,34), "
        "die unterste Zeile bei 3 statt 2 von 11. Die Rueckgaenge stimmten "
        "exakt - dieselbe Haelfte-richtig-Falle wie in 165. **Nullbefund "
        "dazu**: Die Messlatte auf einem Bein statt auf dem Korb zu messen "
        "bewegt sie um 1,6 Punkte (38,03 auf 39,63) und kein Gate - der "
        "Kommentar 'das ist richtig so' ist damit erstmals gemessen",
        267,
    ),
    # Nach der Diagnose am Kandidaten die Frage, ob die **Aufstellung** noch
    # etwas hergibt - der einzige Hebel, der keine Versuche kostet.
    Richtung(
        "Die Aufstellung wurde am ungehandelten Punkt gewaehlt",
        "'cli marktkombinationen' faehrt alle fuenfzehn Kombinationen aus vier "
        "Maerkten durch die Zulassungsstrecke - und rechnete nur den "
        "Perpetual-Punkt. Sein eigener Docstring nennt die Frage, um die es "
        "geht ('beide Gates zugleich zu halten'), und stellt sie damit dort, "
        "wo vier Gates offen sind statt zwei. Am Spot-Punkt nachgemessen "
        "verschiebt sich die Rangfolge erheblich: BTC+ETH 7 auf 9 von 11, "
        "BTC+ETH+XRP 7 auf 9, BTC+ETH+LTC+XRP **5 auf 9**, ETH+XRP **4 auf "
        "9**. Drei Aufstellungen sahen am ungehandelten Punkt erledigt aus "
        "und stehen am gehandelten gleichauf mit dem Bestand. '--spot' "
        "rechnet ihn jetzt, der Betriebspunkt stand schon im Bericht. "
        "**Fuer das Ziel ist es ein Nullbefund**: Keine der fuenfzehn besteht "
        "alle Gates, BTC+ETH bleibt vorn (14,34 % p.a., DSR 0,588), und jede "
        "Verbreiterung kostet Rendite und Deflated Sharpe, ohne den Rueckgang "
        "genug zu senken - BTC+ETH+XRP senkt ihn um 0,03 Punkte und kostet "
        "3,0 Punkte Rendite. Die 41 % Vorteil je Trade aus 174/175 sind damit "
        "auf Portfolioebene beziffert",
        268,
    ),
    # Die Frage, die seit Befund 104 im Raum steht und die nach 268 die
    # einzige verbliebene ist.
    Richtung(
        "Die beiden offenen Gates ziehen nicht gegeneinander",
        "Seit Befund 104 stand die Sorge im Docstring von "
        "'marktkombinationen': *'Steigt der Deflated Sharpe ueber die "
        "Schwelle, faellt womoeglich die Messlatte darunter.'* Sie fordern "
        "Verschiedenes von denselben Trades - die Betriebsschwelle eine "
        "**Summe**, der Deflated Sharpe ein **Verhaeltnis**. Gemessen (269) "
        "haengt alles daran, **wie** der Ertrag steigt: Groessere Positionen "
        "heben Summe und Streuung gleich, lassen den Sharpe je Trade bei "
        "0,2708 und den DSR bei 0,588 - und treiben den Rueckgang von 9,87 "
        "auf 12,42 %, also ueber die Grenze. Skalieren loest kein Gate und "
        "reisst ein drittes. Mehr Ertrag je Trade bei gleicher Streuung "
        "loest **beide**: +25,9 % heben den Sharpe je Trade auf 0,3408 gegen "
        "noetige 0,3387, der DSR stuende bei 0,9595, der Rueckgang bliebe. "
        "**Gesucht wird Ertrag je Trade, nicht Ruhe** - an der Streuung ist "
        "der Bestand nicht knapp. Daraus folgt die Zahl, die das Budget "
        "begrenzt: Das Fenster schliesst sich bei **231 Versuchen**, der "
        "Plan sieht 230 vor - kein Puffer. Die Stelle ist empfindlich (mit "
        "anderen Momenten 214), die Groessenordnung nicht. Wenn es eng wird, "
        "hilft nicht mehr Suche, sondern mehr effektive Stichprobe: Die "
        "Latte haengt an ihr",
        269,
    ),
    # Die Anschlussfrage aus 269: Woher kaeme der Ertrag?
    Richtung(
        "Am Ausstieg ist nichts zu holen - das Werkzeug lief nur nie",
        "'research.exits' beantwortet aus MAE und MFE, ob Stop und Ziele "
        "Spielraum lassen. Aufgerufen wurde es allein in 'cli review', und "
        "das laedt **Live-Trades** - die es nicht gibt. Dieselbe Bauart wie "
        "262 und 265: richtig gebaut, an einer leeren Quelle. Auf dem "
        "Backtest-Buch angewandt (270) sagt es nein: Der Gegenlauf der "
        "Gewinner liegt im Median bei 0,36 R und bei 90 % unter 0,82 R - ein "
        "Stop bei 1,0 R schneidet also fast keinen Gewinner ab, enger zu "
        "gehen kostete welche. Realisiert werden 58 % des Moeglichen. Das "
        "Urteil des Werkzeugs: *'eine Verbesserung muesste an den "
        "Einstiegen ansetzen, nicht an den Ausstiegen'*. **Die Zerlegung "
        "stuetzt es**: Zehn 'take_profit'-Trades tragen 81 % des Ertrags, 68 "
        "Stops kosten 18 % bei einer Streuung von 1,14 - sie greifen, wo sie "
        "sollen. Und der Zuwachs aus 269 entspricht **103,7 % der gesamten "
        "Verlustsumme**: Selbst jeder Verlust auf null gesetzt traegt ihn "
        "nicht. Die naheliegendste Idee - engerer Stop, weiteres Ziel - ist "
        "damit gemessen erledigt, ohne einen Versuch",
        270,
    ),
    # Der Anschluss an 270 ("ueber die Einstiege") - und dabei der aelteste
    # offene Auftragspunkt des Registers.
    Richtung(
        "Die Sperren kosten keine Einstiege, sie sparen schlechte",
        "270 endet bei den Einstiegen, und die Engine sperrt welche: nach 3 % "
        "Tagesverlust, 7 % Wochenverlust, bei 15 % Rueckgang der Kill-Switch, "
        "dazu der Terminkalender. Gemessen (271), diesmal richtig verglichen "
        "- 'enforce_risk_limits' hat den Default True, mein Vergleich in 269 "
        "hat deshalb zweimal denselben Lauf gemessen: Mit allen Sperren 158 "
        "Trades und 14,3391 % p.a., nur mit den Verlustgrenzen 160 und "
        "14,2697 %, ohne beides 162 und 14,1915 %. Die vier zusaetzlichen "
        "Trades bringen zusammen **-5,12 EUR**, der Sharpe je Trade faellt "
        "von 0,2708 auf 0,2652, und der Rueckgang ist in allen drei Faellen "
        "bitgleich 9,8687 % - der Kill-Switch greift nie. **Die Sperren sind "
        "kein Kostenfaktor, sondern ein kleiner Gewinn**; sie abzuschalten "
        "verschlechterte beide offenen Gates. Damit ist auch der aelteste "
        "Auftragspunkt geschlossen: Das Termin-Overlay (P7, seit Befund 59 "
        "als 'Wirkung nicht belegt' gefuehrt) sperrt in acht Jahren sechs "
        "Einstiege, und in der Sperrprobe halten **100 % der zufaelligen "
        "Sperren derselben Groesse genauso viele Gates**. Es war nicht die "
        "Auswahl, sondern das Streichen. 'cli sperrprobe --massnahme "
        "kalender' prueft das jetzt mit derselben Strenge wie Schock und "
        "Abkuehlung",
        271,
    ),
    # Die Wache aus 272 mit sieben Befunden Vorlauf - also jetzt.
    Richtung(
        "Das Laborbuch waechst schneller als seine Benennung",
        "Befund 272 hat gefunden, dass 'nachmessung.abschnitte' bei 199 "
        "aufhoerte und damit dreiundsiebzig Abschnitte nicht sah; die neue "
        "Wache meldete daraufhin nur noch **sieben** Befunde Vorlauf bis zur "
        "naechsten Grenze. 'zahlwort' reichte bis 299, weil Hundert und "
        "Zweihundert als je eigener 'if'-Zweig gebaut waren - nach der Regel "
        "'erst bauen, wenn es soweit ist'. Beim dritten Mal ist das keine "
        "Sparsamkeit mehr, sondern eine Stelle, die alle hundert Befunde "
        "angefasst werden muss, und beim letzten Mal kam die Pflege um "
        "siebzig Befunde zu spaet. Jetzt traegt eine Hundertertabelle alle "
        "bis **999** - die natuerliche Grenze des Musters, denn darueber "
        "braucht es 'Tausend'. Die Regel gilt weiter, nur eine Ebene hoeher. "
        "Der Vorlauf steigt damit von sieben auf 707 Befunde, und keine "
        "bestehende Ueberschrift aendert sich - eine Aenderung daran machte "
        "jede Fundstelle im Laborbuch unauffindbar",
        273,
    ),
    # Beim Lesen des Berichts nach 274 aufgefallen.
    Richtung(
        "Ein Listeneintrag war als Akte geschrieben",
        "'GESCHLOSSEN' beantwortet die Frage *welche Suchwege sind gemessen "
        "zu* - eine Liste zum Ueberfliegen, Median 48 Zeichen. 'OFFEN' und "
        "'BEHOBEN' sind Akten (Median 356 und 203), weil ein offener Weg "
        "seinen Stand und ein behobener Fehler seine Begruendung braucht. Der "
        "Unterschied stand im Registerkopf und nirgends im Code: Mein Eintrag "
        "zu 272/274 trug **1455 Zeichen** - das Dreissigfache des Medians, "
        "das Sechsfache des zweitlaengsten - und hat die Liste im Bericht "
        "erschlagen. Gekuerzt auf 145; die Ausfuehrung steht im Laborbuch. "
        "Eine Wache haelt 'GESCHLOSSEN' jetzt unter 300 Zeichen (abgeleitet "
        "aus dem Bestand: der zweitlaengste traegt 239), eine zweite haelt "
        "fest, dass 'BEHOBEN' laenger sein **darf**. **Eine dritte ist "
        "entfallen**: Sie forderte in jedem Eintrag eine Ziffer - gemessen "
        "nennen zehn ihre Zahl als Wort, und die Wache haette erzwungen, "
        "dort eine Ziffer hineinzuschreiben, damit ein Test gruen wird",
        275,
    ),
    # Gefunden, weil die vierte Familie zum ersten Mal etwas ueber die Latte
    # gebracht hat - und die Latte der Pruefung nicht standhielt.
    Richtung(
        "Die Latte des Scans stand auf einer Normalverteilung",
        "'schwelle_fuer' teilt fuenf Prozent Irrtum auf die geprueften Zellen "
        "auf. Das setzt voraus, dass jede Beobachtung ihren Zustand neu "
        "wuerfelt - **keine der vier Familien tut das**: Ein Rueckblick ueber "
        "960 Balken haelt seinen Zustand jahrelang. Auf reinem Rauschen "
        "gemessen kommt ein traeger Teiler in 2 von 300 Zuegen ueber die "
        "Latte eines Laufs dieser Groesse (3,61 bei 164 Zellen), ein Teiler ohne Gedaechtnis in 0 von 300 - "
        "zwanzigmal so oft, wie die Latte zusichert. Die Verschiebungsprobe "
        "haelt den t-Wert jetzt gegen den Teiler in seiner eigenen Ordnung "
        "und trifft beides: die Marktbreite (2 von 584) und die "
        "Preisrueckblick-Spitze aus 272 (23 von 1325). **Kein frueheres "
        "Ergebnis dreht sich** - was an der Latte scheiterte, scheitert "
        "jetzt frueher. Was die Probe nicht kann, steht dabei: Feiner als "
        "1 von 585 wird sie nicht, verlangt sind 0,029 % - auf dieser "
        "Stichprobe ist 'nicht belegbar' nicht von 'nicht da' zu trennen. "
        "**Warum die Latte danebenlag, stand zuerst falsch da** (277): nicht "
        "'die Form der Renditen', sondern die Bauart - Teiler und "
        "Folgerendite aus derselben wandernden Reihe. Zerlegt: verschoben "
        "auf echten Renditen 4,14, gewuerfelt auf echten 2,80, verschoben "
        "auf gemischten 2,33. Ein reiner Irrweg reicht, um es zu erzeugen",
        276,
        zuletzt=277,
    ),
    # Die Frage, die 276 offengelassen hat - und die Luecke, die dabei
    # auffiel.
    Richtung(
        "Die Eichung der Latte lief nur bei einem Treffer",
        "Befund 276 hat die Latte des Vorteilsscans als zu niedrig "
        "nachgewiesen. Dieselbe 'schwelle_fuer' traegt den Tageszeit-Scan, "
        "und ob der Befund dorthin traegt, war offen. **Gemessen: nein.** "
        "Dort ist der Vergleich gepaart - innen gegen aussen am selben Tag -, "
        "also wird nicht ein Teiler verschoben, sondern die Richtung jedes "
        "Tagesunterschieds gewuerfelt. Das 99. Perzentil dieser Nullverteilung "
        "liegt bei 2,57 bis 2,58 gegen 2,576 der Normalverteilung, und die "
        "Tage haengen mit -0,12 bis +0,01 kaum zusammen. Die Latte haelt. "
        "**Aufgefallen ist dabei die eigentliche Luecke**: Beide Scans "
        "rechneten ihre Eichung nur, wenn eine Zelle anschlug - wer sie nur "
        "dann rechnet, erfaehrt nie, ob die Latte ueberhaupt richtig steht. "
        "Sie steht jetzt in jedem Lauf, in beiden Befehlen",
        277,
    ),
    # Dieselbe Frage am Gate, das die Zulassung blockiert.
    Richtung(
        "Der Deflated Sharpe meldete eine Wahrscheinlichkeit, die er nicht ist",
        "Das Gate schrieb *'Wahrscheinlichkeit 46,3 %, dass der Vorteil echt "
        "ist'*. Gemessen mit den Trades des Bestands als Form und ohne jeden "
        "Vorteil darin (5.000 ganze Suchlaeufe): Bei **einem** Versuch stimmt "
        "die Formel, bei 198 liegt das 95. Perzentil der Null bei **0,3070**, "
        "und kein einziger von 5.000 Nulldurchlaeufen erreicht 0,95. Die "
        "ganze Tafel steht unter den offenen Entscheidungen, weil dort die "
        "Frage haengt. Die Deflation zieht den erwarteten "
        "Bestwert ab, teilt aber durch den Fehler eines **einzelnen** Sharpe, "
        "und der ist groesser als die Streuung des Maximums. **Die Latte "
        "bleibt stehen**: Gates werden nicht gelockert, damit etwas besteht, "
        "und am wenigsten, wenn man weiss, wo der eigene Kandidat liegt. "
        "Geaendert wurde die Botschaft, nicht die Schwelle. Der Bestand liegt "
        "mit 0,463 am 99,24. Perzentil dieser Null; nachzurechnen mit "
        "'cli abstand --eichung'",
        278,
        zuletzt=279,
    ),
    # Der Schritt, den 278 schuldig geblieben ist.
    Richtung(
        "Der Verfall des DSR stand ohne sein Gegenstueck da",
        "'cli abstand' meldet, was das Suchen kostet - von 198 auf die "
        "Budgetgrenze 230 faellt der Wert am Spot-Punkt von 0,5881 auf "
        "0,5551. Das liest sich als Zerfall der Evidenz. Gemessen (279) "
        "bewegt sich die **Null mit**: Ihr 95. Perzentil faellt im selben "
        "Schritt von 0,3075 auf 0,2949, und die Lage des Bestands geht von "
        "99,88 auf **99,86** - zwei Hundertstel eines Perzentils fuer den "
        "ganzen Rest des erlaubten Budgets. Beides gilt: Die **noetige "
        "Guete** steigt mit jedem Versuch (31/221, unveraendert), die **Lage "
        "der vorhandenen Evidenz** kaum. Die Tafel traegt jetzt beide "
        "Spalten, reicht bis zur Budgetgrenze und rechnet alle Zeilen mit "
        "derselben Zahl Laeufe",
        279,
    ),
    # Beim Nachsehen aufgefallen, ob der Reglerleiter ein Betriebspunkt fehlt.
    Richtung(
        "Die Reglerleiter kannte keinen Betriebspunkt",
        "'cli vereinbar' faellt ein Ja-Nein-Urteil - *'Rendite >= 15 und "
        "Rueckgang <= 12 sind nicht zugleich erfuellbar'* - und nannte nicht, "
        "unter welchen Handelsbedingungen es gilt. Befund 112 hat gemessen, "
        "dass genau die entscheiden. Die zwoelf gespeicherten "
        "Machbarkeitsberichte tragen alle 'betriebspunkt: None'; sie stammen "
        "aus der Zeit vor Befund 242, der das Feld eingefuehrt hat. Der "
        "Lader legte sie stumm zu einer Leiter zusammen, und bei gleicher "
        "Stellung haette ein Spot-Punkt einen Perpetual-Punkt ueberschrieben "
        "- dieselbe Falle, vor der sein eigener Docstring seit jeher fuer die "
        "Messstaende warnt. Jetzt waehlt 'lade' nach Punkt aus, meldet was "
        "dabei wegfaellt, und das Urteil nennt seinen Punkt oder sagt, dass "
        "keiner vermerkt ist. **Und die Leiter ist am Spot-Punkt erstmals "
        "messbar**: 'cli machbarkeit --spot'. Gemessen ist sie dort noch "
        "nicht - 'cli vereinbar --spot' meldet null Stellungen, und das "
        "Messen kostet Versuche",
        280,
        zuletzt=281,
    ),
    # Beim Nachsehen gefunden, wie die Zulassung eigentlich umschaltet.
    Richtung(
        "Ohne Herkunft galt der Bericht als zulassungsfaehig",
        "'evaluate_gates' erkennt aus den Beinen, ob auf Forschungskerzen "
        "gerechnet wurde: 'any(ist_referenz(name) for name in frames or ())'. "
        "**Ohne 'frames' war das 'any(())', also False** - die Vorgabe fuer "
        "den unbekannten Fall war damit die erlaubende: Wer das Argument "
        "vergisst, bekommt einen zulassungsfaehigen Bericht auf Kerzen, deren "
        "Herkunft niemand geprueft hat. Genau dagegen steht Befund 102. "
        "**Gemessen war es kein Fehler**: Von 23 Aufrufen geben 22 die "
        "Herkunft mit, der eine ist 'cli sperrprobe' und laeuft als "
        "Vorauswahl, die nie zur Zulassung wird. Ein Fall, den es nicht gibt, "
        "wird trotzdem irgendwann gebaut - eine vollstaendige Pruefung ohne "
        "Herkunftsangabe bricht jetzt ab, eine Vorauswahl darf es weiter. "
        "Dazu eine Wache ueber alle Aufrufe, damit ein neuer nicht erst im "
        "Lauf auffaellt",
        283,
    ),
    # Die Gegenprobe zu 283: Auch der Erfolgsfall war nie gefahren worden.
    Richtung(
        "Der Erfolgsweg der Zulassung war nie gelaufen",
        "Seit Befund 102 sperrt 'passed' Forschungskerzen, und geprueft war "
        "seither die **Sperre**. Der Erfolgsfall - Boersenkerzen, "
        "'referenzdaten=False', Zulassung - stand in einem **von Hand "
        "gebauten** 'GateReport'; 'tests/test_uebergang.py' verwies im "
        "Docstring ausdruecklich dorthin, statt ihn zu fahren. Zwischen dem "
        "Namen im Kerzenspeicher und dem Schalter im Bericht liegen zwei "
        "Uebergaben, und keine hatte eine Wache - dieselbe Klasse wie 265, "
        "wo Funding unter dem falschen Schluessel lautlos zu NaN wurde. "
        "'tests/test_zulassungsweg.py' faehrt die Strecke jetzt zweimal auf "
        "denselben zwei Zufallsreihen ueber 900 Tage, einmal unter Boersen- "
        "und einmal unter Forschungsnamen: 5 Fenster, 33 Trades, Zeichen fuer "
        "Zeichen dieselben Gate-Werte, und genau ein Feld unterscheidet die "
        "Berichte. Beide Richtungen der Erkennung sind durch Mutation "
        "geprueft. **Was weiter aussteht**: Dass elf von elf aus einem echten "
        "Lauf kommen - dafuer braucht es eine Strategie, die besteht, und "
        "keine erfundene Reihe",
        284,
    ),
    # Derselbe Griff wie 284, eine Ebene weiter: eine Messung, die im
    # Modulkopf stand und nichts steuerte.
    Richtung(
        "Der Preis stand auf einer Geraden, die ein Punkt loescht",
        "Befund 183 hat gemessen, dass die Kopplung des Vorrats ohne "
        "'Momentum Ruecksetzer' von t = -2,59 auf -0,97 faellt, und den Satz "
        "*'Eine Decke, die ein Punkt loeschen kann, ist keine'* in den "
        "Modulkopf geschrieben. Gesteuert hat er nichts: 'urteil' und "
        "'preisurteil' rechneten weiter, und 'cli vorratsdecke' nannte "
        "**1,68 Reststreuungen bei n_eff 101** als Preis einer neuen Idee - "
        "eine Entscheidungsregel, die aussah wie eine Messung. "
        "'einflussprobe' laesst jetzt jede Regel einmal weg und laeuft immer "
        "mit; der Bericht nennt das Ergebnis, und der Preis wird verweigert, "
        "wenn eine einzelne Regel ihn traegt. Gemessen (285): 17 der 18 "
        "Auslassungen lassen die Gerade stehen, eine loescht sie, und ohne "
        "'Starker Trend, Momentum' waere sie mit t = -5,75 deutlich staerker "
        "als mit allen. Die Handmessung von 183 ist damit reproduziert und "
        "als Wache festgehalten",
        285,
    ),
    # Die Frage, die 285 selbst aufgemacht hat - und ihre Antwort.
    Richtung(
        "Ein Abstand, der keine Gerade braucht",
        "Befund 285 hat den Preis in Reststreuungen verweigert und damit das "
        "Werkzeug mitgenommen, an dem 'lohnt sich ein Versuch?' haengt. "
        "'research/vorratslage.py' antwortet ohne Anpassung: Jede Regel hat "
        "eine gemessene Guete und die Latte, die bei **ihrer** Stichprobe "
        "und **ihrer** Verteilungsform gilt - der Unterschied ist eine "
        "Beobachtung. Gemessen (286): Am naechsten kommt "
        "'Donchian-Ausbruch 55/20' mit 2,484 gegen 3,564, es fehlen 1,080 - "
        "**0,83 Streuungen dieses Vorrats**, Median aller 18 Luecken 2,080. "
        "Und statt 'keine von 18, also gibt es nichts' steht dort eine Zahl: "
        "Null Treffer aus 18 sind kein Beleg fuer null - bei einer wahren "
        "Quote von 10 % waeren sie zu 15 % genau das, was man sieht. **Die "
        "Obergrenze selbst war zu eng** und ist seit 287 eine Spanne",
        286,
        zuletzt=287,
    ),
    # Der Fehler lag bei mir, einen Lauf zuvor.
    Richtung(
        "Achtzehn Regeln sind keine achtzehn Einfaelle",
        "Die Obergrenze aus 286 stand auf '1 - 0,05^(1/n)' mit n = Zahl der "
        "**Regeln** - das unterstellt, dass jede ein eigener Einfall ist. "
        "Nach Regellogik heissen **zwoelf von achtzehn 'Trend'**, "
        "strukturell nach Einstiegsindikator zerfallen sie in acht Gruppen, "
        "grob in sechs: 15,3 % bei 18 Ziehungen, 31,2 % bei 8, 39,3 % bei 6. "
        "Beziffern laesst sich die Abhaengigkeit nicht - die "
        "Intraklassenkorrelation der Luecken ueber die acht Gruppen betraegt "
        "**+0,49**, die Permutationsnull weist sie mit p = 0,0885 nicht "
        "nach, und die groebere Einteilung hat mit sechs Bloecken zu wenige "
        "('MIND_BLOECKE' ist 8). Der Bericht nennt deshalb eine Spanne, und "
        "ohne Gruppenangabe steht die Bedingung im Satz. **Die Begruendung "
        "dazu war in 287 verkehrt herum und ist in 289 berichtigt**",
        287,
        zuletzt=289,
    ),
    # Dieselbe Frage an die zweite Gerade des Projekts - und sie haelt.
    Richtung(
        "Die Gerade im Auftrag nannte die falsche Zahl und traegt trotzdem",
        "Der Auftrag an die Research-KI nennt eine Trefferquote von 0,5 bis "
        "12 % und sagt dazu, woher sie kommt: *'eine Geraden durch 18 "
        "Punkte'*. **Die Liste hat 22** - seit Befund 83, der vier "
        "kalibrierte Regeln hinzugefuegt hat; ein Test in derselben "
        "Testdatei nennt beide Staende im Kommentar. Die Zahl stand als Wort "
        "im Text und ist jetzt gezaehlt, ebenso die Zielspanne (146 bis 185 "
        "statt 142 bis 202) und der Streufaktor (22 statt 48). **Und die "
        "Gegenprobe mit dem Werkzeug aus 285 faellt hier anders aus**: Keine "
        "der 22 Auslassungen bringt die Kopplung unter die Schwelle, die "
        "schwaechste laesst t = -2,53 stehen (mit allen -2,89). Die Quote "
        "bleibt deshalb im Auftrag - anders als der Preis des Tageskatalogs, "
        "und der Auftragstext sagt jetzt beides",
        288,
    ),
    # Wieder mein Fehler, und diesmal in der Begruendung selbst.
    Richtung(
        "Nicht zu kuerzen macht das Gate leichter, nicht strenger",
        "Befund 287 hat begruendet, warum eine ungekuerzte Stichprobe bei "
        "Trades die vorsichtige Seite sei: *'Wer die Stichprobe nicht "
        "kuerzt, macht das Gate strenger.'* **Verkehrt herum.** Die Guete "
        "waechst mit der Wurzel der Stichprobe, die Latte nur langsam - "
        "derselbe Bestand (SR 0,2708) scheitert bei n_eff 115 mit 2,904 "
        "gegen 3,618 und bestuende bei n_eff 200 mit 3,830 gegen 3,745. So "
        "steht es auch im Docstring von 'effektive_stichprobe': *'Das kann "
        "die Zulassung nur erschweren, nie erleichtern.'* **Die Aussage wird "
        "dadurch schaerfer**: Nicht zu kuerzen laesst beim Gate den Bestand "
        "besser aussehen und bei der Trefferquote die Suche aussichtsloser - "
        "zweimal dieselbe Richtung, zugunsten des Vorhandenen. In die Irre "
        "gefuehrt hat mich die Kopfzeile von 'designeffekt', die noch "
        "'gekuerzt nur bei nachgewiesener Abhaengigkeit' sagte, obwohl die "
        "Kuerzung laengst stetig ist; sie ist mitberichtigt",
        289,
    ),
    # Was 285 verworfen hat, war das Werkzeug - nicht die Sache.
    Richtung(
        "Die Kopplung ist echt, sie sitzt nur nicht in der Guete",
        "Befund 285 hat die Gerade durch den Vorrat verworfen, weil ein "
        "Punkt sie loescht - und damit stand auch die Kopplung aus 168/169 "
        "in Frage, auf der das Mengentor geschlossen wurde. Ueber **Raenge** "
        "gemessen (290), die diese Schwaeche nicht haben: Die Qualitaet je "
        "Trade faellt mit der Menge, rho = -0,679 bei t = -3,70, und "
        "**jede** der 18 Auslassungen bleibt ueber |t| = 2 (schwaechste "
        "-3,11). Die Sache ist also belegt, verworfen war nur das Werkzeug. "
        "**Auf der Guete ist davon nichts uebrig**: rho = +0,072 bei "
        "t = +0,29, und **keine** Auslassung raeumt die Schwelle - die "
        "Wurzel aus der Stichprobe nimmt zurueck, was die Qualitaet je Trade "
        "verliert. Das Mengentor bleibt damit zu, aber wegen der langsam "
        "steigenden Latte und nicht wegen zusammenbrechender Qualitaet",
        290,
    ),
    # Und was die Luecke heisst, wenn man sie je Trade liest.
    Richtung(
        "Beide Haelften gibt es - nur nie zusammen",
        "Eine Luecke von 1,080 Guetepunkten sagt nicht, ob das viel ist. "
        "Geteilt durch die Wurzel der Stichprobe wird daraus eine "
        "Anforderung an die Qualitaet je Trade, und die faellt steil: von "
        "0,9443 bei n_eff 16 auf **0,2641 bei n_eff 254**. Die hoechste je "
        "gemessene Qualitaet des Vorrats ist 0,3274. Damit liegt die "
        "billigste Anforderung **innerhalb** dessen, was fuenf der achtzehn "
        "Regeln gezeigt haben - **aber keine davon oberhalb von n_eff 58**. "
        "Was fehlt, ist keine unerreichte Groesse, sondern eine unerreichte "
        "Verbindung: viel Qualitaet je Trade und viele Trades zugleich. "
        "Genau die schliesst die rangfeste Kopplung aus 290 aus, und genau "
        "sie waere der Unterschied, den der Auftrag an die Research-KI "
        "verlangt",
        291,
        zuletzt=292,
    ),
    # Und damit steht der Unterschied endlich im Auftrag selbst.
    Richtung(
        "Der Auftrag verlangte einen Unterschied und nannte ihn nicht",
        "Seit Befund 196 steht im Auftrag an die Research-KI: *'Was einen "
        "Vorschlag von den bisherigen unterscheidet, gehoert in seine "
        "Begruendung.'* **Worin** er bestehen soll, konnte er nicht sagen - "
        "bis 291 die Zahl dazu gemessen hat. Der Auftrag nennt sie jetzt: "
        "hoechste je gemessene Qualitaet 0,3274 bei n_eff 29, billigste "
        "Anforderung 0,2641 bei n_eff 254, gezeigt von 5 der 18 Regeln, "
        "keine davon oberhalb n_eff 58. Gerechnet wird sie aus dem Katalog, "
        "nicht hineingeschrieben. **Dabei fiel eine zweite Fassung auf**: "
        "Die gemessene Tabelle stand in zwei Testdateien nebeneinander, "
        "einmal mit und einmal ohne Lattenspalte; sie liegt jetzt in "
        "'research/referenz.py', und eine Wache prueft, dass keine dritte "
        "entsteht. Der Abschnitt faellt weg, sobald eine Regel ihre Latte "
        "raeumt - dann gibt es beide Haelften sehr wohl zusammen",
        292,
    ),
    # Der meistgelesene Bericht zeigte auf den Stand von vor 200 Befunden.
    Richtung(
        "Der Stand nannte die erste Fundstelle statt der letzten",
        "'cli stand' fuehrt den Deflated Sharpe als durchgemessen und nannte "
        "dazu **Befund 89** - rund zweihundert Befunde alt und seither "
        "mehrfach ueberholt (286 bis 291). Wer nachschlug, fand den Stand von "
        "damals; genau die Falle aus Befund 130, und 'Richtung' sagt seit "
        "damals: *'Wer eine Fundstelle nennt, muss die letzte nennen.'* "
        "'research/nachmessung.py' fuehrt beide Zahlen seit jeher, "
        "'gatelage' tat es nicht - jetzt steht dort 'Nr. 291, zuerst 89'. "
        "**Und die zweite Haelfte des Satzes war zu stark**: *'Weitere "
        "Laeufe daran kosten Zeit ohne offene Frage'* las sich als 'hier ist "
        "nichts mehr zu holen'. Gemeint sind Laeufe **am Gate**; was offen "
        "bleibt, ist ein Kandidat und keine Rechnung - Befund 291 hat "
        "gemessen, dass die noetige Qualitaet je Trade innerhalb dessen "
        "liegt, was der Katalog gezeigt hat",
        293,
    ),
    # Die Wache gegen genau diesen Fehler sah ein Fuenftel des Registers an.
    Richtung(
        "Die Wache gegen alte Fundstellen sah nur ein Fuenftel an",
        "Befund 293 hat eine veraltete Fundstelle im meistgelesenen Bericht "
        "gefunden - und dafuer gibt es seit Befund 130 ein Werkzeug: "
        "'cli register' sucht, wo eine Richtung **nach** ihrer massgeblichen "
        "Stelle noch erwaehnt wird. Nachgesehen, was es ansieht: **39 von 208 "
        "Registereintraegen.** 'BEGRIFFE' deckte genau die geschlossenen "
        "Richtungen ab, und der Befehl lief nur ueber 'GESCHLOSSEN' - die "
        "sechzehn **offenen** Richtungen, nach denen gearbeitet wird, waren "
        "nicht dabei. Keine Fehlfunktion: 'spuren' meldet seit jeher, wo es "
        "keine Begriffe gibt; gefragt hat nur niemand. Jetzt laeuft die Suche "
        "ueber 55 Eintraege, sieben der offenen Richtungen haben spaetere "
        "Erwaehnungen, und der Bericht nennt zum Schluss, was er **nicht** "
        "ansieht (die 153 behobenen). Eine Wache prueft, dass jede neue "
        "offene Richtung Begriffe bekommt",
        294,
    ),
    # Die sieben Verdachtsfaelle aus 294 - gelesen statt gesammelt.
    Richtung(
        "Sieben Verdachtsfaelle, gelesen und entschieden",
        "Befund 294 hat sieben offene Richtungen mit spaeteren Erwaehnungen "
        "gemeldet; das Modul besteht darauf, dass ein Mensch sie liest. "
        "Getan: **Drei waren Nachmessungen** und sind nachgezogen - 'Zaehlt "
        "ein Sweep als Versuch?' auf 282 (dort wird die Frage ausdruecklich "
        "offengehalten und um die Unterscheidung Suchlauf/Sweep geschaerft), "
        "'Der Preis in Reststreuungen' auf 290 (die Gerade darunter neu "
        "beurteilt), 'Einstieg, der nicht am Rauschen haengt' auf 283 (dort "
        "gepruefte, was von der Beschreibung uebrig ist). **Vier waren blosse "
        "Erwaehnungen** - Regelnamen in Katalogtabellen, ein Werkzeughinweis, "
        "ein Registerabdruck. Genau das Verhaeltnis, vor dem der Modulkopf "
        "warnt. Die Vermutung, Registerzitate seien die Hauptquelle der "
        "Fehlalarme, ist **gemessen und widerlegt**: 11 von 684 Treffern "
        "stehen in Zitatzeilen, 2 %. Neu ist ein Gedaechtnis ('GELESEN'): Der "
        "Bericht trennt ungelesene von entschiedenen Erwaehnungen, sonst "
        "meldet jeder Lauf dieselben dreiundvierzig",
        295,
    ),
    # Zweimal geschaetzt, wo zu messen gewesen waere - beide Male daneben.
    Richtung(
        "Die Laufzeit war geschaetzt, nicht gemessen",
        "Ob ein Katalogdurchlauf in einen Arbeitsschritt passt, entscheidet, "
        "ob eine Messung gemacht wird. Diese Entscheidung ist zweimal "
        "**geschaetzt** worden: erst *'225.000 Kerzen sind 68-mal so viele, "
        "das dauert Stunden'* - daraufhin blieb der 15-Minuten-Katalog zwei "
        "Laeufe lang unangesehen -, dann *'39 Genome mal 61 s, also 40 "
        "Minuten'*. Gemessen: ein Walk-Forward kostet 61 s, ein **Genom** "
        "aber 226 s im Median, weil die Gates ein Vielfaches des "
        "Walk-Forward kosten. Beide Schaetzungen lagen daneben, in "
        "entgegengesetzte Richtungen. 'research/laufkosten.py' haelt jetzt "
        "die gemessenen Zahlen (1d: 6 s je Genom auf 3.277 Kerzen, 15m: "
        "226 s auf 225.341), 'cli vorratsdecke' nennt sie **vor** dem Lauf, "
        "und fuer eine ungemessene Kerzenlaenge gibt es keine Hochrechnung, "
        "sondern die Aufforderung zu messen - zwei Punkte legen eine Gerade "
        "fest, und die ist hier kein Argument",
        296,
    ),
    # Derselbe Apparat auf einem zweiten Vorrat - fast alles faellt anders aus.
    Richtung(
        "Der 15-Minuten-Katalog hat keinen Boden",
        "Die Werkzeuge aus 285 bis 291 zum ersten Mal auf den zweiten Vorrat "
        "angesetzt (36 Regeln, 225.341 Kerzen, 2,4 Stunden). **Ein Bild, das "
        "dem Tageskatalog fast ueberall widerspricht**: nur **1 von 36** "
        "Regeln hat positive Guete (beste 0,703 gegen Latte 3,854; auf 1d "
        "waren es 16 von 18). Die Rangkopplung dreht sich um - auf 1d sitzt "
        "sie in der Qualitaet je Trade (rho -0,679) und nicht in der Guete "
        "(+0,072), hier umgekehrt (-0,260 gegen **-0,701**): Wo die Qualitaet "
        "negativ ist, vervielfacht mehr Handeln den Verlust. Die Zielmarke "
        "faellt in den anderen Zweig: Die billigste Anforderung (0,0494 je "
        "Trade) liegt **ueber** der hoechsten je gemessenen Qualitaet "
        "(0,0304) - hier fehlt nicht die Verbindung, sondern die Qualitaet "
        "selbst. Trefferquote hoechstens 8,0 bis 13,9 %. Die Einflussprobe "
        "schlaegt auch hier an (ohne 'Trendbeteiligung mit Puffer' t = -1,73 "
        "statt -2,19), und kein Familienschnitt konnte pruefen - jede "
        "Aussenmenge zu klein",
        297,
    ),
    # Derselbe Fehler wie 296, eine Ebene tiefer - diesmal vor dem Lauf bemerkt.
    Richtung(
        "Eine Sprosse kostet einen Walk-Forward, kein Genom",
        "Befund 297 hat die Reibungsfrage auf Viertelstunden offengelassen: "
        "Kippfaktor 2, in Reichweite der Slippage - und die laesst sich aus "
        "vorhandenen Trades nicht abziehen. Messen laesst sie sich trotzdem, "
        "denn die **Reibungsleiter** rechnet ganze Durchlaeufe mit anderer "
        "Gebuehr, statt zurueckzurechnen (Befund 254). Was das kostet, war "
        "wieder nicht gemessen: Der naheliegende Ansatz - je Sprosse ein "
        "voller Genompreis - haette auf 15 Minuten 4,8 Stunden ergeben. "
        "Gemessen ist der Walk-Forward allein (1d **2,2 s**, 15m **61,4 s**), "
        "denn eine Sprosse rechnet keine Gates; der Lauf kostet damit 3,1 "
        "statt 4,8 Stunden. 'laufkosten' fuehrt den Sprossenpreis mit eigener "
        "Fundstelle - zwei Messungen, zwei Fundstellen -, und ohne gemessenen "
        "Sprossenpreis gibt es fuer Sprossen keine Zahl",
        298,
    ),
    # Kein Messbefund, sondern ein Werkzeugfehler - bemerkt, als er zuschlug.
    Richtung(
        "Drei Stunden Messung, nichts auf der Platte",
        "Der 15-Minuten-Lauf aus Befund 298 ist nach drei von 39 Genomen an "
        "einem Neustart gestorben, und uebrig blieb nichts: zwoelf Minuten "
        "Rechenzeit, kein Byte. Das ist kein Sonderfall - **jede** lange "
        "Messung hier sammelt im Arbeitsspeicher und schreibt am Ende, und "
        "bei 3,1 Stunden faengt man irgendwann gar nicht erst an. "
        "'zwischenstand' schreibt jetzt eine Zeile je Messung, sofort und "
        "mit 'flush'; 'vorratsdecke' legt sie unter 'reports/vorratsdecke/' "
        "ab und nennt den Pfad vor dem Lauf. Der Kopf steht **zuerst** und "
        "traegt die Bedingungen samt erwarteter Genomzahl - daran sieht man "
        "einem abgebrochenen Protokoll an, wo es aufhoerte; eine Schlusszeile "
        "koennte das nicht, denn genau der abbrechende Lauf schreibt sie nie. "
        "**Kein Wiederaufsetzen**: Ein Lauf, der an Genom 18 anschliesst, "
        "muesste behaupten, die ersten 17 seien unter denselben Bedingungen "
        "gemessen - das ist ein Protokoll, kein Sicherungspunkt",
        299,
    ),
    # Die Ablehnung aus 299 bleibt - beantwortet wird sie trotzdem.
    Richtung(
        "Ein Lauf, der laenger dauert als ein Arbeitszug",
        "Der neu gestartete 15-Minuten-Lauf endete nach **einem** Genom. "
        "Beide Abbrueche kamen wenige Minuten nach dem Ende meines "
        "Arbeitszugs (12 Minuten beim ersten Mal, knapp 6 beim zweiten): Die "
        "Maschine wird eingezogen, sobald die Sitzung still ist. Ein "
        "dreistuendiger Lauf im Hintergrund ist hier damit nicht riskant, "
        "sondern **unmoeglich** - er muss in Stuecke. 'vorratsdecke --stueck "
        "2/5' misst einen Teil, '--aus a,b,c' urteilt ueber die "
        "zusammengelegten Protokolle. Zusammengelegt wird nur, was "
        "zusammengehoert: 'zusammen' vergleicht die Koepfe Feld fuer Feld und "
        "nennt jeden Unterschied - das ist die Antwort auf 299, wo dieselbe "
        "Gleichheit nur **behauptet** worden waere. Dafuer traegt der Kopf "
        "jetzt einen Abdruck von Kerzen, Katalog und rechnendem Code; der "
        "Codeabdruck steht auf dem **Inhalt** von backtest/strategy/research/"
        "cli.py und nicht auf 'git HEAD', sonst trennte jeder Commit zwischen "
        "zwei Stuecken den Lauf. Gegenprobe gemessen: sechs Stuecke des "
        "Tageskatalogs, zusammengelegt, ergeben Tabelle und Urteile Zeichen "
        "fuer Zeichen wie der Lauf am Stueck - nachdem ein Fehler behoben "
        "war, den die Gegenprobe zeigte: Die Pruefung auf Doppelgaenger sah "
        "nur innerhalb eines Prozesses, und zwei identische Regeln in "
        "verschiedenen Stuecken ergaben 19 Belege statt 18",
        300,
    ),
    # Derselbe Massstabsfehler wie 296 und 298 - diesmal vermieden, bevor er
    # eine Messung verhindert hat.
    Richtung(
        "Die Reibungsfrage braucht die Gates nicht",
        "Der 15-Minuten-Katalog mit einer Reibungssprosse kostet gemessene "
        "3,8 Stunden - und davon sind zwei Drittel Gates, die die Frage gar "
        "nicht braucht: 'Kostenfrage' steht auf Taktpunkten (Trades, Sharpe "
        "je Trade, Haltedauer, Kostenanteil), nicht auf effektiver "
        "Stichprobe, Latte oder Decke. 'cli reibung' rechnet nur die "
        "Walk-Forwards, mit '--stueck' und '--aus' wie in 300: 123 s je "
        "Genom statt 287, der Katalog in rund 80 Minuten statt 3,8 Stunden. "
        "Die Gegenprobe auf Tageskerzen ergab Urteil und Zahlen Zeichen fuer "
        "Zeichen gleich, ob am Stueck oder aus sechs Stuecken gelesen - und "
        "reproduziert Befund 78: r -0,056 am Betriebspunkt gegen -0,052 ohne "
        "jede Reibung, 7 % des Weges zur Null, die Kopplung gehoert den "
        "Signalen. Zwei Fehler hat die Stueckelung dabei ans Licht gebracht: "
        "'Reibungsleiter.urteil' und 'Reibungsprobe.urteil' stuerzten ab, "
        "wenn eine Sprosse genug Regeln, aber keine Streuung hatte (vier "
        "Abwandlungen derselben Vola-Ziel-Regel, alle mit derselben "
        "Trade-Zahl - r ist dann None); und der erste Wurf von 'cli reibung' "
        "zaehlte Doppelgaenger mit, 25 Regeln statt 19",
        301,
    ),
    # Der Werkzeugfehler hinter Befund 302 - nicht im Code, im Ablauf.
    Richtung(
        "Das Register wusste es, gefragt hat es niemand",
        "Befund 302 hat 106 Minuten gemessen, um eine Zahl zu bestaetigen, "
        "die seit 255 im Register stand. Der Eintrag war da und lesbar; das "
        "Nachsehen war ein Vorsatz und keine Zeile im Ablauf. "
        "'research/vorwissen.py' sucht die Registereintraege zu den "
        "Stichworten eines Laufs - in GESCHLOSSEN, OFFEN **und** BEHOBEN, in "
        "Name und Text - und 'cli reibung' wie 'cli vorratsdecke' schreiben "
        "sie hin, bevor sie messen, mit der gemessenen Laufzeit daneben: "
        "Lesen kostet eine Minute, der Lauf 106. Die Stichworte stehen in "
        "'STICHWORTE' und nicht in 'cli.py', sonst haenge die Wache an einer "
        "zweiten Fassung (130, 286, 292). **Aufgehalten wird nichts**: Eine "
        "Messung zu wiederholen ist oft richtig - 302 hat 255 auf einem "
        "unabhaengig gebauten Weg bestaetigt. Falsch war nicht der Lauf, "
        "falsch war, ihn ohne die Antwort zu starten. Ein Test haelt fest, "
        "dass die Reibungsfrage mit den Stichworten von 'cli reibung' an "
        "**erster** Stelle gefunden wird",
        303,
    ),
    # Dieselbe Lehre wie 130, 174 Befunde spaeter und im falschesten Register.
    Richtung(
        "Der Auftragspunkt kannte keine Nachmessung",
        "'Richtung' traegt seit Befund 130 ein 'zuletzt', weil eine erste "
        "Fundstelle Geschichte ist und kein Stand. 'Auftragspunkt' hatte "
        "keines - und das ausgerechnet im einzigen Register, das die Punkte "
        "des Auftraggebers beantwortet. Der Punkt 'Generation 6/7 auf "
        "15-Minuten' zeigte auf Befund 29 mit 14 Regeln, waehrend 297 "
        "denselben Vorrat mit **36** gemessen hatte; 'Research-KI im "
        "Wettbewerb nutzen' zeigte auf 196, obwohl 292 dem Auftrag an die KI "
        "gesagt hat, worin der Unterschied bestehen muss. Beide nachgezogen, "
        "'Generation 5 auf Tageskerzen' ausdruecklich **nicht** - dass es "
        "dazu Spaeteres gibt, ist plausibel und war nicht geprueft. Die Wache "
        "aus 130 gilt jetzt auch hier: Jede massgebliche Fundstelle muss es "
        "im Laborbuch geben, und die nachgezogenen stehen ausgeschrieben da",
        304,
    ),
    # Dasselbe noch einmal, ein Register weiter - und dort ohne jede Marke.
    Richtung(
        "Die Entscheidungen des Nutzers standen ohne Fundstelle da",
        "'Entscheidung' hatte drei freie Textfelder und keine Fundstelle; die "
        "Befundnummern standen als Prosa mitten im Satz, ungeprueft - die "
        "Bauart, die 212 an der Historienkurve abgestellt hat. Das Register, "
        "das den Nutzer um eine Entscheidung bittet, war damit das einzige "
        "ohne Marke. Und es war veraltet: Der Eintrag zur Research-KI nannte "
        "als Anforderung '120 Trades bei Guete ueber 0,23' aus Befund 74/75, "
        "waehrend 291/292 laengst **0,2641 je Trade bei n_eff 254** gemessen "
        "hatten - wer danach entscheidet, entscheidet auf einer Latte von vor "
        "zweihundert Befunden. Neun von zehn Eintraegen tragen jetzt ihre "
        "Fundstelle, aus ihrem **eigenen** Text gelesen; die "
        "Wochenverlustgrenze bleibt ohne, weil sie auf keiner Messung steht. "
        "Dazu kommt die Entscheidung, die seit 283 nur unter den Richtungen "
        "stand: 'Neues Hoch im Takt' neu bauen, ein Versuch von 27 bis zur "
        "Abbruchmarke - eine Entscheidung, die nirgends unter den "
        "Entscheidungen steht, wird nicht getroffen, sondern vertagt",
        305,
    ),
    # Der Fehler aus 305, einen Befund spaeter bemerkt - von mir, nicht von
    # einem Test.
    Richtung(
        "Eine Entscheidung gestellt, die 283 schon beantwortet hatte",
        "305 hat \"'Neues Hoch im Takt' neu bauen - ein Versuch\" unter die "
        "ENTSCHEIDUNGEN gesetzt und dabei die 70 %/19 % und die 0,2137 "
        "zitiert, als braechte ein Nachbau sie mit. Befund 283 hatte genau "
        "das nachgesehen: Von der Beschreibung sind ein Name, eine "
        "Eigenschaft und zwei Kennzahlen da - **keine Regel**; ein Nachbau "
        "waere Erfinden, und gegen frische Vermutungen auf der Einstiegsseite "
        "steht ein gemessener Vorwert (272/274/276: vier Familien, zwei "
        "Maerkte, zwei Kerzenlaengen, nichts hat die eigene Nullverteilung "
        "ueberlebt). Ursache: Ich habe die **Zusammenfassung** der offenen "
        "Richtung gelesen und nicht den Befund, auf den sie zeigt - dieselbe "
        "Bauart wie in 302, und diesmal mit nur einem Befund Abstand. Die "
        "Entscheidung ist zurueckgenommen, und der Eintrag traegt die "
        "Schlussfolgerung von 283 jetzt selbst",
        306,
    ),
    # Die Zeilen, die jemand auf seinem eigenen Rechner einfuegt - bisher von
    # keinem Test angesehen.
    Richtung(
        "Die Befehle fuer den Nutzer waren nie gegen die Kommandozeile geprueft",
        "'BEIM_NUTZER' ist die einzige Stelle, an der dieses Projekt jemanden "
        "bittet, etwas auf seinem Rechner zu tun, und zweimal ist genau daran "
        "etwas schiefgegangen: 167 (Prosa statt Befehlszeile, "
        "'Got unexpected extra argument(s)') und 214 (ohne '--generation' "
        "gilt die Vorgabe 8, ein Viertelstunden-Katalog - nach einem "
        "Tages-Backfill braeche der Lauf ab). Die sechs Zeilen werden jetzt "
        "gegen die echte Befehlsstruktur **geparst** - Befehl, Optionen, "
        "Typen -, ohne Boerse und ohne Daten, und zwei Querpruefungen "
        "kommen dazu: Der Backfill muss Tageskerzen laden (213: alle elf "
        "Gates stehen darauf), und die im Wettbewerb genannte Generation muss "
        "laut 'VORGESEHEN' zu genau dieser Kerzenlaenge gehoeren - das ist "
        "214 als Rechnung statt als Erinnerung. Dabei fiel auf, dass der "
        "offene Auftragspunkt 'backfill 15m + wettbewerb' hiess, waehrend "
        "sein eigener Text und alle Befehle Bybit-**Tages**kerzen verlangen; "
        "der Titel ist berichtigt",
        307,
    ),
    # Die Wache vor dem echten Geld hing an einer Zeichenkette.
    Richtung(
        "Die Warnung vor dem Handel war am Quelltext geprueft",
        "Befund 264 hat 'cli trade' warnen lassen, wenn ein einzelnes Bein "
        "gehandelt wird, waehrend der Korb zugelassen wurde - gemessen kostet "
        "das ein Gate (Korb 9/11, nur BTC 8/11, nur ETH 8/11). Geprueft war "
        "die Warnung, indem der Test 'cli.py' als Zeichenkette las und "
        "'deckt_ab(', 'yellow' und 'Befund 264' darin suchte. Das haelt auch "
        "dann noch, wenn die Warnung hinter eine Bedingung rutscht, die nie "
        "zutrifft - eine Wache auf einen Satz haelt auch einen falschen "
        "(289). Der Text steht jetzt in "
        "'Zulassungsbedingungen.unterdeckung(symbol)' und wird im Test "
        "**aufgerufen**: Korb gegen ein Bein meldet, gedeckter Korb schweigt, "
        "ein Nachweis ohne Aufzeichnung schweigt. Am Quelltext bleibt nur die "
        "Verdrahtung - dass der Befehl sie holt und dort nicht abbricht. "
        "Gemessen, wie verbreitet die Bauart ist: 37 von 179 Testdateien "
        "lesen Quelltext; umgebaut wurde die eine, die vor echtem Geld steht",
        308,
    ),
    # Diesmal in die verbietende Richtung: Der unbekannte Fall bekam ein Nein.
    Richtung(
        "Ein fehlender Wert wurde als gerissene Schwelle gemeldet",
        "'cli vereinbar --spot --mit-jahr' meldete an **allen sechs** "
        "Stellungen 'Schlechtestes Jahr fehlt' und schloss daraus, die drei "
        "Schwellen seien 'nicht zugleich erfuellbar'. Keiner der sechs "
        "Berichte traegt diesen Wert: Die Kapitalkurven sind zu kurz fuer ein "
        "Jahresfenster, und 'kennzahlen_der_kurve' laesst den Schluessel dann "
        "weg. 'erfuellt(None)' ist False - richtig, ein Wert, den es nicht "
        "gibt, erfuellt nichts -, aber daraus 'gerissen' zu machen ist eine "
        "Aussage ueber den Kandidaten, wo nur eine ueber die Akte zu haben "
        "war. Dieselbe Bauart wie 283, nur in die andere Richtung: Dort war "
        "die Vorgabe fuer den unbekannten Fall die erlaubende, hier die "
        "verbietende. 'Schwelle.beurteile' trennt beides, und das Urteil "
        "verweigert sich ueber eine Schwelle, zu der kein Punkt einen Wert "
        "traegt - sagt aber weiter, was messbar ist (Rendite und Rueckgang "
        "sind vereinbar, 3 von 6 Stellungen). Dabei gemessen: '--perpetual' "
        "findet **null** Stellungen, weil die aelteren Berichte keinen "
        "Betriebspunkt tragen; die Entscheidung 'Mindestrendite' versprach, "
        "beide Seiten liessen sich jederzeit nachrechnen",
        309,
    ),
    # Die Ursache aus 309 war geraten. Nachgesehen: Der Wert stand die ganze
    # Zeit in derselben Datei.
    Richtung(
        "Die Ursache des fehlenden Werts war geraten",
        "309 hat 'nan' richtig als 'nicht gemessen' gemeldet und die Ursache "
        "aus dem Code **abgelesen statt nachgesehen**: die Kapitalkurve sei "
        "zu kurz fuer ein Jahresfenster. Sie ist es nicht. Der Bericht traegt "
        "das schlechteste Jahr im Gate-Eintrag - mit Schwelle und Urteil "
        "daneben -, waehrend 'vereinbar' nur 'kennzahlen' liest, und dort "
        "steht es nicht. 'lade' nimmt es jetzt aus beiden Stellen; "
        "'AUS_DEM_GATE' nennt die eine Kennzahl, um die es geht, damit aus "
        "zwei Quellen keine Mischung wird. **Damit ist die Frage beantwortet, "
        "die 309 offenlassen musste**: Rendite, Rueckgang und schlechtestes "
        "Jahr sind am Spot-Punkt nicht zugleich erfuellbar; der Uebergang "
        "liegt zwischen 20,5 und 21, und bei 20,5 fehlen zusammen 0,20 "
        "Punkte - 0,01 an der Rendite, 0,19 am schlechtesten Jahr. Gelesen "
        "wurden vorhandene Berichte, das kostet keinen Versuch",
        310,
    ),
    # Die Lehre aus 187/190/280, nur auf der Titelseite - dort hat sie am
    # laengsten gefehlt.
    Richtung(
        "Der Stand nannte seinen Betriebspunkt nicht",
        "Die Kopfzeilen von 'cli stand' nannten Kandidat, Maerkte, "
        "Kerzenlaenge, Trades, Rendite, Rueckgang, Gates und Versuche - und "
        "nicht den Punkt, an dem das alles gemessen ist. Dabei entscheidet er "
        "mit, welche Gates halten: Derselbe Kandidat steht am Perpetual-Punkt "
        "bei 7 von 11 und am Spot-Punkt bei 9 von 11 (106), und die offenen "
        "Gates sind andere. Der zweite Punkt wurde im selben Lauf **gemessen** "
        "und nur fuer einen Auftragstext benutzt. Jetzt steht er im Kopf: "
        "'Auch gemessen  Spot: 9 von 11, offen: Messlatte, Deflated Sharpe' - "
        "eine Zahl und kein Rat, denn den Kandidaten dorthin zu stellen, wo "
        "mehr Gates bestehen, ist die Anpassung, gegen die die "
        "Zulassungsstrecke gebaut ist. Fehlt die Angabe, steht "
        "'Betriebspunkt nicht angegeben' da; eine stille Luecke waere der "
        "Zustand von vorher",
        311,
    ),
    # Die Wache aus 308 fehlte dort, wo derselbe Satz genauso gilt.
    Richtung(
        "Der Abgleich sah die Kerzenlaenge an, den Umfang nie",
        "'cli abgleich' traegt im Kopf 'Vor jedem Livegang auszufuehren' und "
        "prueft seit Befund 263, ob die Kerzenlaenge die zugelassene ist - "
        "den **Umfang** hat er nie angesehen. Ein gruenes 'einig ueber 5355 "
        "Balken' konnte damit auf einem Bein stehen, waehrend die elf Gates "
        "auf dem Korb gemessen sind; gemessen kostet das ein Gate (264: Korb "
        "9/11, nur BTC 8/11 an 'Schlechtestes Jahr', nur ETH 8/11 am "
        "Drawdown). 'cli trade' warnt seit 264 davor, der letzte Schritt "
        "davor nicht. Jetzt ruft auch er 'unterdeckung' auf - **denselben** "
        "Text aus derselben Quelle (308), gewarnt und nicht abgebrochen, wie "
        "bei der Kerzenlaenge: Ein Abgleich auf einem Bein prueft die Engine "
        "und ist keine Freigabe. Ein Test haelt fest, dass der Satz in "
        "keinem der beiden Befehle noch einmal ausgeschrieben steht",
        312,
    ),
    # Derselbe Riss wie in 882 von gates.py - eine Achse weiter. Dort war es
    # der Markt, hier ist es die Sperrlage.
    Richtung(
        "Das Plateau-Gate las eine Form aus Laeufen, die abgeschaltet waren",
        "Die Engine legt je Lauf einen frischen Risk-Officer an und "
        "begruendet das selbst: Im Walk-Forward startet jedes Fenster frei, "
        "*'was der Annahme entspricht, dass der Nutzer einen ausgeloesten "
        "Not-Aus zwischen den Fenstern manuell freigibt. Ohne diese Annahme "
        "bliebe jedes Fenster nach dem ersten Not-Aus fuer immer stumm, und "
        "der Backtest waere in der anderen Richtung falsch.'* Genau diesen "
        "Lauf rechnen zwei Gates: Plateau und Kosten-Stress fahren "
        "**durchgehende** Backtests je Bein, acht Jahre ohne Fenstergrenze "
        "und damit ohne Freigabe. Not-Aus und Wochenlimit sind Zustaende und "
        "keine Uhren - nur 'resume' und 'reset_kill_switch' heben sie auf, "
        "und die ruft kein Backtest. Gemessen (313, Perpetual): **12 von 12 "
        "Nachbarn** wurden nicht zu Ende gemessen, zusammen 1020 verhinderte "
        "Einstiege. Bei zweien entscheidet das ueber das Vorzeichen - und es "
        "sind genau die beiden, an denen das Gate scheitert: 'alle "
        "gemeinsam' x1,2 mit -103,63 durchgehend gegen +233,04 im "
        "Walk-Forward, 'sma(period=50)' x1,2 mit -103,90 gegen +239,08. Ihr "
        "BTC-Bein hielt das Wochenlimit am 03.09.2020 an, ihr ETH-Bein der "
        "Kill-Switch am 11.05. bzw. 30.06.2020; die restlichen sechs Jahre "
        "handelten sie nicht mehr. **Was das Gate dort sah, war der "
        "Zeitpunkt der Sperre und nicht die Form des Gebiets** - und seine "
        "Botschaft nannte es 'die Kante eines Gebiets'. Behoben ist die "
        "Botschaft: Wo die gescheiterten Nachbarn gesperrt wurden, steht "
        "jetzt das und keine Randlage - derselbe Verzicht, den 'randlage' "
        "fuer die fehlende Seite schon leistet ('einseitig gemessen'). "
        "**Gerechnet wird unveraendert durchgehend**, Wert und Urteil des "
        "Gates sind dieselben; 'cli freigabe' misst beide Messarten "
        "nebeneinander. Die Gegenprobe gehoert dazu: Am Spot-Punkt besteht "
        "das Gate so oder so (1,000 gegen 1,000), und der Kosten-Stress "
        "bleibt mit +945,06 gegen +2316,29 in beiden Faellen bestanden - "
        "der Riss faellt also nicht dorthin, wo er dem eigenen Kandidaten "
        "nuetzt. Auch die Tests aus 163 standen auf gesperrten Laeufen; sie "
        "messen die Form jetzt ohne Verlustgrenzen",
        313,
    ),
    # 313 hat zwei Gates geprueft. Dieselbe Bauart steht an drei weiteren
    # Stellen - darunter genau die, auf die das Gate verweist.
    Richtung(
        "Die Karte, die das Gate als Aufloesung anbietet, hatte denselben Riss",
        "Das Plateau-Gate nennt die Breite des Gebiets nicht und verweist "
        "dafuer auf 'cli plateaubild'. Ausserhalb des Walk-Forward rechnen "
        "genau fuenf Stellen einen durchgehenden Backtest; 313 hat die zwei "
        "Gates geprueft, hier sind die drei uebrigen. **Die Karte misst "
        "denselben Artefakt**: Von zwoelf Faktoren auf sechs Stellgroessen "
        "sind **72 von 72 Punkten** gesperrt, zusammen 5800 verhinderte "
        "Einstiege. Zu Ende gemessen ist die engste Achse 0,60 breit und "
        "traegt von 0,70 bis 1,30; so wie der Befehl misst, sind es 0,45 "
        "und 0,70 bis 1,15 - die Karte meldet das Gebiet **25 % schmaler**, "
        "und ihre obere Kante liegt bei 1,15 statt 1,30. Betroffen sind "
        "dieselben zwei Achsen wie beim Gate ('alle gemeinsam', "
        "'sma(period=50)'); die vier wirkungslosen aendern sich nicht. "
        "'cli finanzierung --stress' ist die dritte Stelle: 245 verhinderte "
        "Einstiege, die Einbusse durch den Gebuehren-Stress steigt zu Ende "
        "gemessen von 1,3 % auf 3,0 % - das Urteil (bleibt im Plus) kippt "
        "nicht, und die 942,87 / 625,80 / 34 % aus dem Eintrag zum "
        "Stress-Umfang sind unveraendert. **Gerechnet wird ueberall weiter "
        "durchgehend**, keine Zahl ist angefasst: Beide Karten und die "
        "Stresslage sagen jetzt, wie viele ihrer Punkte nicht zu Ende "
        "gemessen wurden, und dass ihre Breite damit eine Untergrenze ist. "
        "'cli landschaft' ist die vierte Stelle und ebenso umgebaut, aber "
        "**nicht gemessen**: Der Befehl bucht seit 282 Versuche, ihn zum "
        "Nachsehen zu starten hoebe die Latte des Deflated Sharpe",
        314,
    ),
    # Nachgesehen, weil 313/314 dieselbe Bauart zeigten - diesmal war nichts
    # kaputt. Der Eintrag steht trotzdem hier: Die Wache ist neu.
    Richtung(
        "Die Naht zwischen zwei Fenstern war zu - nur ungesichert",
        "Drei Gates lesen die verkettete Kapitalkurve (Drawdown, "
        "Schlechtestes Jahr, Monte-Carlo), und '_combine' normierte jedes "
        "Fenster auf das **Anfangskapital**, obwohl es die Kurve erst ab "
        "'test_start' anschneidet. Haette waehrend der Aufwaermphase etwas "
        "gehandelt, saesse an **jeder** Fenstergrenze ein Sprung, den alle "
        "drei als Kursbewegung laesen - und ein Drawdown ist keine "
        "Fehlermeldung. **Gemessen: Der Verdacht war falsch.** Alle 32 "
        "Fenster beginnen exakt bei 500,0000, und zwar nicht zufaellig: "
        "'_run_window' setzt 'run_start = test_start - warmup_bars * "
        "bar_step', die Engine beginnt bei Zeile 'max(warmup_bars, 1)' - "
        "der erste handelbare Balken **ist** 'test_start'. Die Zusage steht "
        "aber in zwei Dateien, die dieselbe Aufwaermphase gleich meinen "
        "muessen, und nichts prueft sie; Luecken in der Reihe verschieben "
        "in die harmlose Richtung, mehr Zeilen als erwartet in die andere. "
        "Seit 315 normiert '_combine' auf den **eigenen** Startwert des "
        "Fensters - die Kette ist dann stetig, ohne die Zusage zu brauchen. "
        "**Keine Zahl bewegt sich**: Rendite, CAGR, Rueckgang, Sharpe, "
        "Nettogewinn und alle elf Gatewerte sind vorher wie nachher "
        "bitgleich, gegengerechnet auf den echten Tageskerzen. Vier Tests "
        "halten die Zusage fest, einer weist nach, dass die alte Formel an "
        "derselben Stelle auf 672 statt 600 gesprungen waere",
        315,
    ),
    # Befund 311 hat den Kopf beschriftet. Zwei Abschnitte tiefer stand
    # weiter eine Zahl vom anderen Punkt.
    Richtung(
        "Die Entfernung zum Ziel galt fuer den anderen Betriebspunkt",
        "'WIE WEIT ES NOCH IST' ist der Abschnitt, in dem dieser Bericht "
        "sagt, wie lang der Weg noch ist - und er nannte **2152 Tage (5,9 "
        "Jahre)** unter einem Kopf, der seit Befund 311 ausdruecklich "
        "'Perpetual' sagt. Die Zahl kommt aus 'AUSSICHT', und die ist am "
        "**Spot**-Punkt gerechnet; ein Test bindet sie seit Befund 235 an "
        "'SPOTPUNKT.noetiges_n()'. Beides war fuer sich richtig, und genau "
        "deshalb ist es keinem aufgefallen. Die noetige Evidenz haengt aber "
        "an der Guete je Trade und die am Funding: **190 Beobachtungen am "
        "Spot-Punkt gegen 221 am Erstpunkt**, also 75 fehlende gegen 106 - "
        "und bei derselben Sammelrate 5,9 Jahre gegen **8,3**. Der Bericht "
        "hat das Projekt um zweieinhalb Jahre naeher am Ziel gezeigt, als "
        "es an dem Punkt ist, den er meldet. Behoben ist die Anzeige: "
        "'Aussicht' traegt jetzt ihren Betriebspunkt, 'AUSSICHT_ERSTPUNKT' "
        "rechnet dieselbe Entfernung am gemeldeten Punkt, und der Abschnitt "
        "stellt sie voran und sagt, worin sich die beiden unterscheiden. "
        "**Gerechnet ist nichts neu** - beide Zahlen standen schon vorher "
        "in 'referenz.py', nur eine davon war sichtbar. Der Verbund bekommt "
        "keine Angabe: Sein Punkt ist nirgends festgehalten, und eine "
        "geratene waere schlimmer als keine",
        316,
    ),
    # Die Wache zu 316 - und danach gesucht statt gelesen, diesmal ohne
    # zweiten Fund. Dieselbe Reihenfolge wie 230/231.
    Richtung(
        "Die Wache von 231 sah nur die eine Gestalt des Fehlers",
        "231 sucht **Doppelgaenger**: dieselbe Groesse, zwei Abschnitte, "
        "zwei Prozentwerte. Befund 316 hatte die andere Gestalt - eine "
        "Groesse, die nur **einmal** dastand, und zwar mit dem Wert des "
        "anderen Betriebspunkts. Kein Doppelgaenger, keine Prozentzahl; die "
        "Wache konnte es nicht sehen. Dazu kommt jetzt eine zweite Regel, "
        "ebenso mechanisch: Jeder 'Aussicht'-Stand muss seinen "
        "Betriebspunkt nennen oder mit Grund in 'OHNE_PUNKT' stehen - die "
        "Bauart von 'MEHRFACH'. Eine Gegenprobe nimmt das Etikett wieder "
        "weg und sieht die Wache fallen. **Gesucht und nichts gefunden**: "
        "Von den Feldern, in denen sich die beiden Punkte unterscheiden "
        "(Guete, DSR, Schiefe, Woelbung, bestandene Gates, Fundstelle, "
        "noetiges n), steht die verlangte Evidenz fuer **beide** Punkte da "
        "(190 und 221); die vier Kommazahlen kommen im Bericht nicht in "
        "ihrer Rohform vor, und die uebrigen sind einstellige oder "
        "dreistellige Ganzzahlen, die sich mechanisch nicht zuordnen "
        "lassen - '7' steht in jedem zweiten Satz. Die Wache deckt damit "
        "die Groessen ab, die ein eigenes Objekt tragen, und nicht jede "
        "Zahl; das ist ihre Grenze und steht als solche da",
        317,
    ),
)

#: Wege, die geoeffnet und noch nicht zu Ende gemessen sind.
#:
#: Getrennt von ``GESCHLOSSEN``, weil "gemessen und offen" etwas anderes ist
#: als "gemessen und zu". Ein Eintrag hier ist eine Zusage, keine Ablage.
OFFEN: tuple[Richtung, ...] = (
    Richtung(
        "Holdout auf fremden Maerkten",
        "LTC und XRP halten 41 % des Vorteils je Trade; die Marktrichtung "
        "ist seit 175 herausgerechnet, die Korrelation von 0,685 bleibt",
        174,
        175,
    ),
    # Die "Obergrenze" aus 175 war eine Ueberlegung und ging in die falsche
    # Richtung: Mit denselben Deckeln faellt die Null, weil ein zufaelliger
    # Einstieg oefter am Stop endet (54,2 % gegen 41,9 %). Offen bleibt es
    # trotzdem - vier korrelierte Maerkte sind keine vier Belege.
    Richtung(
        "Timing gegen Zufallseinstiege",
        "ohne Deckel raeumt nur ETH |z| = 2, mit denselben Deckeln wie die "
        "Regel alle vier (2,71 bis 6,34). Der ungedeckelte Vergleich ist "
        "eine Untergrenze, keine Obergrenze - aber die Maerkte korrelieren "
        "mit 0,695, also keine vier unabhaengigen Bestaetigungen. Der "
        "Bestand raeumt auf 4 von 4 Maerkten und ist die einzige Regel, die "
        "auf allen vieren genug handelt; von zehn geprueften Partnern kommt "
        "keiner ueber 2 von 4 - eine Erklaerung fuer Befund 186. Rechnet man "
        "die 198 Versuche mit (z = 3,48), sind es 2 von 4, und beide "
        "Holdout-Maerkte fallen heraus",
        175,
        205,
    ),
    Richtung(
        "Zertifizierbarkeit der Bauart",
        "keine gepflanzte Sprosse besteht - das gilt aber nur entlang dieser "
        "Achse: Pflanzen nimmt die Stichprobe mit, und die Latte ist ein Tal "
        "mit Boden bei n_eff 60, kein Hang",
        176,
        178,
    ),
    Richtung(
        "Gedeckelter Ausstieg",
        "vier Deckel von 10 bis 40 Kerzen, keiner entkoppelt (beste Steigung "
        "0,36 gegen 0,5) - der Deckel bindet, aendert die Trade-Zahl aber nicht",
        177,
    ),
    Richtung(
        "Menge statt Qualitaet",
        "220 wirksame Beobachtungen statt 115 - aber nur bei unveraenderter "
        "Qualitaet, und die haelt in diesem Vorrat nicht: Der Preis steigt "
        "von 3,78 auf 5,72 Reststreuungen (179). **Der Beleg dafuer stand "
        "auf der Geraden, die 285 verworfen hat**; ueber Raenge gemessen "
        "(290) faellt zwar die Qualitaet je Trade mit der Menge "
        "(rho -0,679, jede der 18 Auslassungen haelt), auf der **Guete** "
        "aber ist davon nichts uebrig (rho +0,072, keine Auslassung haelt). "
        "Das Tor bleibt zu, aber nur wegen der langsam steigenden Latte "
        "(+0,28 Guetepunkte von n_eff 60 auf 260) - gegen eine Luecke von "
        "1,080 ist das kein Weg. Was fehlt, fehlt an der Guete",
        178,
        290,
    ),
    # **Der Eintrag, dessen Fehlen einen Lauf gekostet hat.** Befund 177 hat
    # die Richtung als neue formuliert, 122 Befunde nach ihrer Messung. Eine
    # Richtung, die nicht im Register steht, wird ein zweites Mal gegangen.
    #
    # Er steht hier und nicht in ``GESCHLOSSEN``: Gemessen ist **ein**
    # Kandidat dieser Bauart, und er hat verloren - die Bauart selbst ist
    # damit nicht erledigt. Ein zweiter kostet einen Versuch.
    # Der Preis, den die Decke verlangt - und die Richtung, die daraus folgt.
    # **Der beste gemessene Stand des Projekts** - und ausdruecklich nicht
    # bestanden.
    # **Der Name dieses Eintrags stimmt seit Befund 193 nicht mehr.** Mit der
    # Latte jedes Paares statt der des Bestands faellt 'Grosser
    # Trendausbruch' von 0,064 auf 0,212 und von Platz 1 auf Platz 2; vorn
    # steht 'Trendfolge Ausbruch' mit 0,108. Der Eintrag behaelt den Namen,
    # unter dem die Messungen 184 bis 186 gelaufen sind - umbenennen wuerde
    # die Fundstellen unauffindbar machen.
    Richtung(
        "Bestand + 'Grosser Trendausbruch'",
        "berichtigt (193): bester Stand ist 'Trendfolge Ausbruch' mit 0,108 "
        "bei n_eff 251; 'Grosser Trendausbruch' fehlt 0,212 statt 0,064. "
        "0 von 18 ueber der Latte, und **keiner der sieben** haelt im "
        "Holdout mehr als der Bestand allein (bester 30 % gegen 41 %)",
        184,
        193,
    ),
    Richtung(
        "Der Preis in Reststreuungen",
        "auf dem berichtigten Vorrat 1,67 bei n_eff 101 statt 3,70 bei 97, "
        "Bestand +1,18 statt +2,41 - und die Gerade selbst haelt an einem "
        "Punkt (ohne ihn t = -0,97). Seit 285 wird deshalb **kein Preis mehr "
        "genannt**: 17 der 18 Auslassungen lassen die Gerade stehen, eine "
        "loescht sie. Seit 286 steht an seiner Stelle die Luecke jeder Regel "
        "zu ihrer eigenen Latte: beste 1,080 (0,83 Streuungen des Vorrats), "
        "Median 2,080, Trefferquote hoechstens 15,3 %. Offen bleibt, ob sich "
        "aus der Kopplung ueberhaupt noch etwas lesen laesst",
        179,
        290,
    ),
    # **Die Gegenprobe zu 169/179 - und sie war nicht durchfuehrbar.**
    Richtung(
        "Haengt die Familienaussage am Schnitt?",
        "auf dem berichtigten Vorrat (18 Regeln) hat unter keiner "
        "Indikator-Einteilung eine Familie mehr die Mehrheit; nach Regellogik "
        "traegt 'Trend' 12/18 selbst nicht (t = -1,77). Kein pruefbarer "
        "Schnitt stuetzt die Familienaussage",
        181,
        183,
    ),
    Richtung(
        "Einstieg, der nicht am Rauschen haengt",
        "der wiederholbare Ausbruch entkoppelt (haelt 70 % seiner Trades "
        "statt 19 %) und raeumt jede gepflanzte Latte; auf echten Daten war "
        "er mit 0,2137 je Trade schlechter als der Bestand und braeuchte 324. "
        "**Diese Regel ist nicht mehr rechenbar** (257): Sie stammt aus einer "
        "Vorschlagsdatei, die nie versioniert wurde, und die Bestenliste hielt "
        "damals keine Regeln (Befund 74). Seit 256 ist sie trotzdem die "
        "wichtigste: Die Kopplung ist als Eigenschaft der Signale gemessen, "
        "ein struktureller Bruch ist der einzige bekannte Weg heraus. "
        "**Was von der Beschreibung da ist, hat 283 nachgesehen**: ein Name, "
        "eine Eigenschaft und zwei Kennzahlen - **keine Regel**. Sie daraus "
        "neu zu bauen waere kein Rekonstruieren, sondern Erfinden, und das "
        "Ergebnis traegt die gemessenen 0,2137 nicht mit. Fuer frische "
        "Vermutungen auf der Einstiegsseite gibt es einen gemessenen Vorwert "
        "(272/274/276: vier Familien, zwei Maerkte, zwei Kerzenlaengen, "
        "nichts hat die eigene Nullverteilung ueberlebt) - dafuer Versuche "
        "auszugeben, waere gegen die eigenen Messungen gehandelt. Die "
        "Richtung bleibt offen, ein Weg dorthin ist sie nicht",
        56,
        283,
    ),
    # **Acht Punkte reichen dafuer nicht**, und mehr gibt es nicht: Jeder
    # weitere Holdout-Punkt setzt ein Paar voraus, das geprueft werden
    # sollte. Die Richtung bleibt offen, nicht weil sie ungemessen waere,
    # sondern weil die Messung nichts entscheidet.
    Richtung(
        "Ordnet die Luecke das Verhalten im Holdout?",
        "vier Rechnungen ueber acht Paare, alle unter |t| = 2: alte "
        "Rangfolge +0,214 / +0,571, berichtigte -0,024 / +0,464. Die "
        "Berichtigung sagt schwaecher voraus - was sie nicht falsch macht. "
        "Die Reihenfolge taugt zum Priorisieren, nicht zum Verzichten",
        186,
        195,
    ),
    # Gemessen beantwortet in 239 - aber nicht in beide Richtungen: Dass die
    # Wege uebereinstimmen, heisst nicht, dass 'CandleStore.read' ableiten
    # soll. Der Vorrat ist geprueft, die Bauentscheidung steht offen.
    Richtung(
        "Tageskerzen ableiten statt laden?",
        "beide Wege stimmen ueberein: von 2.344 gemeinsamen Tagen weichen "
        "zwei ab, und 'low' auf keinem einzigen. Die eine ist der Fund - die "
        "letzte gespeicherte Tageskerze traegt rund die Haelfte des Volumens "
        "ihres Tages und steht wie eine volle da; 'data.gegenprobe' findet "
        "sie. Sie kostet nichts, Nachlauf und Randschnitt halten den Rand aus "
        "der Statistik. Ob 'read' kuenftig ableiten soll, ist damit keine "
        "Frage der Richtigkeit mehr, sondern der Herkunft - und offen",
        213,
        zuletzt=239,
    ),
    # Aufgeworfen von 233; 234 misst, warum die Akte sie nicht beantwortet.
    Richtung(
        "Zaehlt ein Sweep am Bestand als Versuch?",
        "'landschaft' und 'machbarkeit' vermessen die Umgebung des "
        "vorhandenen Kandidaten und schreiben dabei den Zaehler fort - "
        "'machbarkeit' um eine ganze Vola-Leiter. Ob das Hypothesen ueber "
        "den Markt sind oder Messungen am Bestand, entscheidet, ob die "
        "Budgetgrenze fuer sie gilt. Sie bricht dort bewusst nicht ab. Aus "
        "der Akte ist die Frage nicht zu beantworten: Was sie melden, bucht "
        "'save_trials' in den Grundstock - 187 der 198 Versuche stehen dort "
        "ohne Herkunft, als waeren sie Vorgeschichte",
        233,
        zuletzt=282,
    ),
    # Gemessen in 234, absichtlich nicht angefasst.
    Richtung(
        "Der Grundstock nimmt auch das Neue auf",
        "'save_trials' setzt 'grundstock = trials - len(eintraege)', bucht "
        "gemeldete Versuche also in das Feld, dessen Kopf 'von vor der "
        "Einfuehrung des Verzeichnisses' sagt. Auf einer Kopie gemessen: 5 "
        "gemeldet, Grundstock +5, Einzelnachweise +0. Belegt auch am "
        "Verlauf - 166 auf 187 bei unveraendert 11 Eintraegen, die 21 aus "
        "Befund 104. **Die Begruendung, es nicht umzubauen, war falsch** "
        "(282): Sie lautete, die fuenf Befehle liefen hier nicht, weil sie "
        "Kerzen brauchen. In Befund 281 lief 'cli machbarkeit --spot' genau "
        "hier und buchte fuenf Stellungen stumm in den Grundstock, 187 auf "
        "192. Umgebaut sind jetzt die beiden Befehle, die 234 namentlich "
        "nennt: 'landschaft' und 'machbarkeit' schreiben Einzelnachweise mit "
        "Herkunft. Drei buchen weiter in den Grundstock ('adaptiv', "
        "'research', 'wettbewerb') - Suchlaeufe und keine Sweeps am Bestand, "
        "bei ihnen war nie strittig, ob sie zaehlen. **Offen bleibt die Frage "
        "selbst**, ob ein Sweep zaehlen soll; beantwortbar wird sie erst mit "
        "den Laeufen, die von jetzt an sichtbar sind. Die 192 im Grundstock "
        "bleiben ohne Herkunft - sie nachtraeglich zu benennen waere eine "
        "Umbuchung",
        234,
        zuletzt=282,
    ),
    # Halb gemessen in 251. Die andere Haelfte braucht Bybit - deshalb steht
    # der Eintrag hier und nicht bei den geschlossenen.
    Richtung(
        "Zugelassen ist der Korb, handelbar ist ein Bein",
        "Die elf Gates laufen auf dem Korb aus BTC und ETH; 'LiveTrader' "
        "handelt genau ein 'instrument.symbol'. Gemessen, was das kostet "
        "(264): Korb 158 Trades, 9,87 % Rueckgang, **9 von 11**; nur BTC 77 "
        "Trades, 10,71 %, 8/11 (Schlechtestes Jahr faellt); nur ETH 81 "
        "Trades, 12,17 %, 8/11 (Drawdown faellt). Jedes Bein verliert ein "
        "Gate, und ein anderes - der Korb zieht den Rueckgang unter den jedes "
        "Beins, weil die beiden nicht gleichzeitig fallen. **Was 'cli trade' "
        "liefe, ist damit nicht das, was bestanden hat.** Der Umfang steht "
        "jetzt im Nachweis und die Unterdeckung wird gemeldet; gesperrt wird "
        "sie nicht, das naehme dem Projekt den einzigen Handelsweg. Zu "
        "entscheiden: Korbhandel bauen oder je Bein zulassen - beides kostet, "
        "und beides faellt nicht in einer Fehlermeldung",
        263,
        264,
    ),
    Richtung(
        "Zahlt der Bestand dann, wenn Longs am meisten zahlen?",
        "Seit Befund 100 stand das als Aussage des Engine-Docstrings da, mit "
        "dem Zusatz, es sei nur mit echten Bybit-Raten nachpruefbar. Das "
        "stimmt fuer die **Rate** und nicht fuer die **Belastung**: Ob die "
        "Haltezeit im Aufwaerts liegt, steht im eigenen Handelsbuch. "
        "Gemessen (251): Der Kandidat ist auf BTC 37 % der Zeit im Markt und "
        "faengt dabei 93 % des gesamten Anstiegs ein - die Drift waehrend "
        "der Haltezeit ist das 2,5-fache der Spanne, auf ETH das 6,6-fache; "
        "62 % des Fundings faellt in steigende Phasen. Ein flacher Satz auf "
        "den Marktdurchschnitt setzt diesen Kandidaten also zu niedrig an. "
        "**Um wie viel, bleibt offen** - das ist die Haelfte, die Bybit "
        "braucht. Gemessen ist der Hebel, nicht der Ausschlag. Und es ist "
        "nicht seine Eigenschaft, sondern die der Bauart (252): Von 13 "
        "brauchbaren Katalogregeln verdichten 12, der Bestand liegt mit "
        "seinem Wert auf Platz 4 mitten im Feld. Die Suche kann in diesem "
        "Katalog nicht herauswaehlen, was alle tragen. **Der zweiseitige "
        "Ausweg ist von hier aus nicht zu pruefen** (253): Bei flachem Satz "
        "haengt das Funding einer Regel nur an ihrer vorzeichenbehafteten "
        "Haltezeit - gemessen ueber vier Regeln und zwei Saetze ist "
        "'Funding je signierter Wertstunde' derselbe Wert und verdoppelt "
        "sich mit dem Satz. Dass ein ausgeglichenes Buch fast nichts zahlt, "
        "ist damit Arithmetik der Annahme und kein Befund ueber die Welt. "
        "**Was eine Kopplung am Urteil aendert, ist gemessen** (266): Auf "
        "exakt gleichem Mittelwert zahlt ein Zeitplan, der der Marktrichtung "
        "folgt, 21,8 % mehr (Kopplung 0,5) und 43,5 % (1,0); dieselbe "
        "Streuung ohne Bezug zum Markt kostet -0,01 %. Es liegt also am "
        "Zusammenfallen von Rate und Haltezeit, nicht am Schwanken. Am Gate "
        "kommt davon wenig an - 'Schlechtestes Jahr' verschiebt sich um 0,02 "
        "und 0,04 Punkte, weil das zusaetzliche Funding in die Aufwaertsjahre "
        "faellt und das schlechteste ein Abwaertsjahr ist. An der Schwelle "
        "entscheidet es trotzdem: Der Kipppunkt liegt flach bei 5,99 bis "
        "6,07 % (250, hier unabhaengig bestaetigt), unter Kopplung 0,5 bei "
        "5,70 bis 5,80 % und unter 1,0 bei 4,90 bis 5,70 %. **Wie stark "
        "echtes Funding koppelt, bleibt offen** - weiter die Haelfte, die "
        "Bybit braucht",
        100,
        zuletzt=266,
    ),
)



#: Die deutschen Zahlwoerter, mit denen die Abschnitte im Laborbuch
#: ueberschrieben sind ("## Fuenfundachtzig. ..."). Ohne sie laesst sich eine
#: Fundstelle nicht maschinell nachschlagen - und eine Liste geschlossener
#: Wege, deren Verweise niemand prueft, driftet still von der Wirklichkeit ab.
_EINER = (
    "", "Ein", "Zwei", "Drei", "Vier", "Fuenf", "Sechs", "Sieben", "Acht", "Neun",
)
_ZEHNER = (
    "", "Zehn", "Zwanzig", "Dreissig", "Vierzig", "Fuenfzig", "Sechzig",
    "Siebzig", "Achtzig", "Neunzig",
)
#: Die Hunderter als **Tabelle** statt als Kette von Sonderfaellen.
#:
#: Hundert und Zweihundert standen einzeln da, jeder mit einem eigenen
#: ``if``-Zweig und einem eigenen Absatz im Docstring - gebaut, als er
#: gebraucht wurde. Beim dritten Mal ist das keine Sparsamkeit mehr, sondern
#: eine Stelle, die alle hundert Befunde angefasst werden muss (Befund 273).
#:
#: Die Tabelle reicht bis 999, also bis an die natuerliche Grenze des Musters:
#: Darueber braucht es "Tausend", und das ist eine andere Ebene. Die Regel
#: "erst bauen, wenn es soweit ist" bleibt damit gewahrt - nur gilt sie jetzt
#: fuer die Ebene und nicht fuer jeden einzelnen Hunderter.
_HUNDERTER = (
    "", "Hundert", "Zweihundert", "Dreihundert", "Vierhundert", "Fuenfhundert",
    "Sechshundert", "Siebenhundert", "Achthundert", "Neunhundert",
)
#: Zahlen, die nicht nach dem Muster gebildet werden. Die Teens (13 bis 19)
#: heissen "dreizehn" und nicht "dreiundzehn"; bei den Zwanzigern heisst die
#: Eins "ein" und nicht "eins".
_SONDER = {
    1: "Eins", 11: "Elf", 12: "Zwoelf", 13: "Dreizehn", 14: "Vierzehn",
    15: "Fuenfzehn", 16: "Sechzehn", 17: "Siebzehn", 18: "Achtzehn",
    19: "Neunzehn",
}


def zahlwort(n: int) -> str:
    """Die Ueberschrift, unter der Befund ``n`` im Laborbuch steht.

    Gebraucht wird das nur zum Nachschlagen: Ein Test prueft damit, dass jede
    Fundstelle in ``GESCHLOSSEN`` auf einen Abschnitt zeigt, den es wirklich
    gibt. Der erste Anlauf zu diesem Modul hat eine 15-Minuten-Messung
    wiederholt, die in Befund 29 laengst stand - die Liste war richtig, nur
    ungeprueft und unvollstaendig.

    **Der Hunderterbereich kam mit Befund 100 dazu, nicht vorher.** Hier stand
    bis dahin ausdruecklich, dass er gebaut wird, wenn er gebraucht wird - und
    dass die Suche bis dahin sichtbar ausfaellt statt still das Falsche zu
    liefern. Jetzt wird er gebraucht.

    **Und der Zweihunderterbereich mit Befund 200**, aus demselben Grund und
    nach derselben Regel.

    **Beim dritten Mal ist es das Muster, nicht der Bereich** (Befund 273).
    Hundert und Zweihundert standen als je eigener ``if``-Zweig da; ein
    dritter waere eine Stelle gewesen, die alle hundert Befunde angefasst
    werden muss. Jetzt traegt ``_HUNDERTER`` sie alle bis 999 - die
    natuerliche Grenze des Musters, denn darueber braucht es "Tausend".

    Die Regel "erst bauen, wenn es soweit ist" gilt weiter, nur eine Ebene
    hoeher: Ueber 999 faellt die Suche sichtbar aus, und
    ``test_nachmessung`` schlaegt zwanzig Befunde vorher an.
    """
    if not 1 <= n <= 999:
        # Dieselbe Regel wie bei 99, 199 und 299: erst bauen, wenn es soweit
        # ist. Ein leerer String findet keine Ueberschrift, und der Test
        # schlaegt an, statt still das Falsche zu liefern.
        return ""
    if n >= 100:
        hundert, rest_n = divmod(n, 100)
        rest = zahlwort(rest_n) if rest_n else ""
        kopf = _HUNDERTER[hundert]
        return f"{kopf}{rest.lower()}" if rest else kopf
    if n in _SONDER:
        return _SONDER[n]
    if n < 10:
        return _EINER[n]
    zehner, einer = divmod(n, 10)
    if einer == 0:
        return _ZEHNER[zehner]
    return f"{_EINER[einer]}und{_ZEHNER[zehner].lower()}"


@dataclass(frozen=True, slots=True)
class Suchbudget:
    """Das Abbruchkriterium aus dem Plan - endlich im System statt nur im Text.

    Der Plan vom 9. August legt es fest: *"Erreicht nach 100 weiteren Versuchen
    kein Kandidat 11 von 11, lautet die Antwort 'diese Regelfamilie traegt
    nicht'. Das ist ein Ergebnis, kein Scheitern."*

    **Warum das ueberhaupt aufgeschrieben gehoert.** Eine Suche ohne Ende ist
    keine Suche, sondern Warten - und sie ist hier nicht nur unproduktiv,
    sondern schaedlich: Jeder Versuch hebt die Huerde des Deflated Sharpe
    fuer alle kuenftigen. Wer weitersucht, macht das Ziel schwerer, das er
    sucht.

    **Wie viel das ist, haengt vom Zaehlerstand ab** (Befund 221). Hier stand
    lange "0,00021 je Versuch" - der Wert aus Befund 31, gemessen als der
    Zaehler bei 130 stand. Bei 198 sind es 0,000135, und der ganze Rest des
    Budgets kostet 1,18 % mehr geforderte Qualitaet gegen eine Luecke von
    24,3 %. ``verbund.versuchskosten`` rechnet es nach.

    Der Preis des Suchens ist damit nicht das, was die Suche aussichtsarm
    macht - das sagt schon Befund 31 in seinem letzten Absatz, und zitiert
    worden ist seither die abschreckende Zahl und nicht der Schluss.

    **Warum eine Zahl und keine Bedingung.** Ein Kriterium wie "abbrechen, wenn
    sich nichts mehr verbessert" laesst sich nachtraeglich zurechtlegen - man
    findet immer eine Kennzahl, die noch Hoffnung macht. Eine vorab genannte
    Zahl kann das nicht. Sie ist grob, und das ist ihr Vorzug.

    **Und seit Befund 71 ist der Umfang auch beziffert.** Huerde und bester Fund
    wachsen beide mit derselben Extremwertkonstante; es entscheidet allein, ob
    die Streuung echter Regelideen ueber der des reinen Zufalls liegt. Aus dem
    eigenen Verlauf kalibriert sind es 0,0950 gegen 0,0808 - genug, um
    aufzuholen, aber erst bei rund 56.000 Versuchen. Bis zum Abbruch bei 230
    schliesst sich der Abstand von 0,0351 auf 0,0324. **Das Budget ist damit
    nicht zu knapp bemessen, sondern die Groessenordnung, in der Suchen ueber-
    haupt noch etwas aendert.** ``cli rennen`` rechnet es nach.

    Der Zaehler selbst steht in ``state/trials.json`` und wird hier nur
    eingeordnet. Beides auseinanderzuhalten ist Absicht: Das Budget ist eine
    Abmachung, der Zaehler eine Messung.
    """

    beginn: int = 130
    """Der Versuchsstand, als der Plan geschrieben wurde."""

    umfang: int = 100

    @property
    def grenze(self) -> int:
        return self.beginn + self.umfang

    def verbraucht(self, versuche: int) -> int:
        return max(0, versuche - self.beginn)

    def rest(self, versuche: int) -> int:
        return max(0, self.grenze - versuche)

    def erschoepft(self, versuche: int) -> bool:
        return versuche >= self.grenze

    def zeile(self, versuche: int) -> str:
        if self.erschoepft(versuche):
            return (
                f"{self.verbraucht(versuche)} von {self.umfang} - **aufgebraucht**. "
                f"Damit gilt die Antwort aus dem Plan: Diese Regelfamilie traegt "
                f"nicht. Das ist ein Ergebnis, kein Scheitern."
            )
        return (
            f"{self.verbraucht(versuche)} von {self.umfang} verbraucht, "
            f"{self.rest(versuche)} bleiben (Abbruch bei {self.grenze})."
        )


#: Das im Plan festgelegte Budget. Eine Abmachung, keine Messung.
BUDGET = Suchbudget()


@dataclass(frozen=True, slots=True)
class Entscheidung:
    """Ein offener Punkt, der nicht bei mir liegt.

    **Mit Fundstelle seit Befund 305.** ``Richtung`` traegt seit 130 eine,
    ``Auftragspunkt`` seit 304 - und ausgerechnet das Register, das den
    Nutzer um eine Entscheidung bittet, hatte gar keine. Die Nummern standen
    als Prosa im Text, ungeprueft; genau die Bauart, die Befund 212 an der
    Historienkurve abgestellt hat.

    Das ist hier nicht Ordnungsliebe: Wer eine dieser Fragen entscheidet,
    soll nachschlagen koennen, worauf die Zahl steht - und sehen, ob sie noch
    die neueste ist. Der Eintrag zur Research-KI nannte als Anforderung "120
    Trades bei Guete ueber 0,23" aus Befund 74/75, waehrend 291 und 292
    laengst 0,2641 je Trade bei n_eff 254 gemessen hatten.

    ``befund`` bleibt freiwillig: Nicht jede Entscheidung steht auf einer
    Messung. Die Wochenverlustgrenze ist eine Betriebsfrage, und eine
    erfundene Fundstelle waere schlimmer als keine.
    """

    frage: str
    zahl: str
    warum: str
    befund: int = 0
    zuletzt: int | None = None

    def __post_init__(self) -> None:
        if self.zuletzt is not None and self.befund <= 0:
            raise ValueError(
                f"'{self.frage}': eine Nachmessung ohne Erstmessung - dann "
                f"ist nicht zu sagen, was sie nachgemessen hat."
            )
        if self.zuletzt is not None and self.zuletzt <= self.befund:
            raise ValueError(
                f"'{self.frage}': Nachmessung in Befund {self.zuletzt} liegt "
                f"nicht nach der Erstmessung in {self.befund} - dann ist es "
                f"keine Nachmessung."
            )

    @property
    def massgeblich(self) -> int:
        """Die Fundstelle, in der die gueltigen Zahlen stehen."""
        return self.zuletzt or self.befund

    @property
    def stelle(self) -> str:
        """Wie die Fundstelle im Bericht dasteht."""
        if not self.befund:
            return "ohne Messung"
        if self.zuletzt is None:
            return f"Nr. {self.befund}"
        # Komma statt zweiter Klammer - Befund 293.
        return f"Nr. {self.zuletzt}, zuerst {self.befund}"


#: Was der Nutzer entscheiden muss - benannt und beziffert, nicht beantwortet.
ENTSCHEIDUNGEN: tuple[Entscheidung, ...] = (
    Entscheidung(
        frage="Feste Schwellen auf laufenden Extrema",
        zahl="Drei der elf Gates messen ein Extrem ueber die ganze Historie, "
             "und alle drei werden mit mehr Daten schlechter (Befund 162, "
             "gemessen ueber sechs Historienlaengen von 1451 bis 3300 Tagen):"
             "\n      Drawdown            8,29 -> 10,64   Schwelle 12,00"
             "\n      Schlechtestes Jahr  5,97 -> -10,32   Schwelle -10,00"
             "\n      Monte-Carlo         7,83 ->   9,69   Schwelle 15,00"
             "\n    'Schlechtestes Jahr' ist bei 2547 Tagen gerissen. Der "
             "Rueckgang ist bereits um 2,35 Punkte gewachsen und hat noch "
             "1,36 Reserve - eine Wiederholung des bereits Gemessenen "
             "genuegt, um auch ihn zu reissen.",
        warum="Ein Maximum kann nicht fallen und ein Minimum nicht steigen. "
              "Wer laenger misst, misst zwangslaeufig ein groesseres Extrem - "
              "unabhaengig davon, ob die Strategie besser oder schlechter "
              "geworden ist. Gleichzeitig braucht der Deflated Sharpe mehr "
              "Historie: Er steht bei 0,46 und verlangt 0,95. **Die Gates "
              "ziehen also gegeneinander**, und Warten ist kein Weg, der sie "
              "alle erreicht.\n    Zu entscheiden ist, ob eine feste Schwelle "
              "auf einem laufenden Extrem gemeint ist - dann ist das kein "
              "Fehler, sondern die Aussage 'so viel Verlust nie, egal wie "
              "lange wir zusehen'. Die Alternative waere eine Schwelle, die "
              "sich auf einen festen Zeitraum bezieht. Beides ist "
              "vertretbar; das eine zu waehlen, ist eine Geschaeftsfrage und "
              "faellt nicht hier. **Gelockert wird nichts**, solange sie "
              "nicht gefallen ist.",
        befund=162,
    ),
    Entscheidung(
        frage="Mindestrendite von 15 % im Jahr",
        zahl="**Es haengt am Betriebspunkt** (Befund 281). Am "
             "Perpetual-Punkt haelt ueber zehn Stellungen des Groessenreglers "
             "keine beide Schwellen: Bei 20,5 bleibt der Rueckgang mit "
             "11,29 % unter der Grenze, die Rendite steht bei 14,11 % - es "
             "fehlen 0,89 Punkte; eine Stufe weiter (21,0) reisst der "
             "Rueckgang mit 12,50 %, und die Rendite fehlt immer noch."
             "\n    Am **Spot**-Punkt, wo das Funding wegfaellt, halten "
             "**drei von sechs** gemessenen Stellungen beide zugleich:"
             "\n      Stellung   Rendite   Rueckgang   Gates"
             "\n          19,3    14,34 %      9,87 %    9/11"
             "\n          20,5    14,99 %     10,47 %    8/11"
             "\n            21    15,30 %     11,66 %    9/11"
             "\n          21,5    15,65 %     11,87 %    9/11"
             "\n            22    16,17 %     11,85 %    9/11"
             "\n            25    18,54 %     13,74 %    7/11"
             "\n    Der behauptete Konflikt der beiden Schwellen ist damit "
             "eine Eigenschaft des Fundings, nicht der Strategie. **Geloest "
             "ist nichts**: Er verschiebt sich nur - 'Schlechtestes Jahr' "
             "haelt bis 19,3, die Messlatte erst ab 21, dazwischen keines von "
             "beiden. Keine Stellung kommt ueber 9 von 11, und der Deflated "
             "Sharpe liegt ausser Reichweite des Reglers (er bewegt ihn um "
             "0,028, es fehlen 0,353).",
        warum="Eine wirtschaftliche Schwelle, kein statistisches Kriterium - "
              "so steht es seit jeher in gates.py. Dass sie mit der "
              "Rueckgangsgrenze im Konflikt steht, war lange eine Behauptung, "
              "ist seit Befund 57 beziffert und seit 281 **auf den "
              "Perpetual-Punkt eingegrenzt**. Nachrechnen laesst sich heute "
              "nur die eine Seite: `cli vereinbar --spot` liest sechs "
              "Stellungen, `--perpetual` meldet **null** - die aelteren "
              "Berichte tragen keinen Betriebspunkt und werden seit 242/280 "
              "ausgelassen, weil eine Vorgabe keine Messung ist (Befund 309). "
              "**Mit der dritten Schwelle gemessen** (310): Rendite >= 15, "
              "Rueckgang <= 12 und Schlechtestes Jahr >= -10 sind auf diesem "
              "Regler nicht zugleich erfuellbar; der Uebergang liegt zwischen "
              "20,5 und 21, und am wenigsten fehlt bei 20,5 - zusammen **0,20 "
              "Punkte** (Rendite 14,99 %, also 0,01 zu wenig, und "
              "Schlechtestes Jahr -10,19 %, also 0,19 zu weit). "
              "Die Aufloesung ist eine Geschaeftsentscheidung "
              "- den Kandidaten dorthin zu stellen, wo mehr Gates bestehen, "
              "ist ausdruecklich keine.",
        befund=57,
        zuletzt=281,
    ),
    Entscheidung(
        frage="Die geratene Eingabe im Deflated Sharpe",
        zahl="Das Gate braucht die Streuung der Sharpe-Schaetzer ueber die "
             "Versuche. Gemessen wird sie nicht - es springt die "
             "Ersatzannahme 1/(n-1) ein, hier sqrt(V) = 0,0808. Das Urteil "
             "kippt bei 0,0657, also **23 % darunter**. Aus den 28 Versuchen, "
             "die ihren Sharpe je Trade mittragen, kaemen 0,0608 - und damit "
             "0,97 statt 0,79. `cli streuung` rechnet es nach.",
        warum="Die 0,0608 werden nicht eingesetzt, und zwar nicht aus "
              "Vorsicht: Von 166 Versuchen liegen 28 vor, und was fehlt, "
              "fehlt am unteren Ende - Berichte entstehen ueber Reglerscans "
              "um den Bestand herum, die Verlierer bekommen keinen. Die "
              "Bestenliste allein streut schon mit 0,1030, also breiter als "
              "die Annahme. Aufgeschrieben wird seit Befund 69 jeder neue "
              "Versuch mit seinem Sharpe je Trade; der Grundstock von 166 "
              "bleibt ohne Einzelnachweis. Damit ist die Abdeckung bis zum "
              "Abbruch des Suchbudgets bei 230 Versuchen auf hoechstens 40 % "
              "gedeckelt - ``streuung.MINDESTABDECKUNG`` verlangt 90. Die "
              "Annahme bleibt also stehen, und zwar auf absehbare Zeit. Zu "
              "entscheiden bleibt nur, ob das je anders sein soll.",
        befund=69,
    ),
    Entscheidung(
        frage="Was die Latte des Deflated Sharpe bedeutet",
        zahl="Gemessen in Befund 278 - mit den Trades des Bestands als Form "
             "und ohne jeden Vorteil darin, 5.000 ganze Suchlaeufe je Zeile:"
             "\n      Versuche   95. Perzentil der Null   Fehlalarm bei 0,95"
             "\n             1                   0,9305               3,36 %"
             "\n            10                   0,6275               0,02 %"
             "\n           203                   0,3059   kein Lauf von 5.000"
             "\n    Bei **einem** Versuch ist 0,95 eine 5-%-Schranke, wie der "
             "Name sagt. Beim heutigen Stand ist sie strenger als alles, was "
             "diese Messung aufloesen kann. Am Spot-Punkt steht der Bestand "
             "mit 0,5826 am **99,86. Perzentil** dieser Null, und der Rest "
             "des Suchbudgets aendert daran nichts: 203 auf 230 Versuche "
             "laesst sein Perzentil bei 99,86, waehrend der rohe Wert von "
             "0,5826 auf 0,5551 faellt. `cli abstand --spot --eichung` "
             "rechnet es nach.",
        warum="Das Gate ist am Spot-Punkt eines von nur zwei offenen - das "
              "andere ist die Messlatte, eine Geschaeftsschwelle. Damit "
              "haengt die Zulassung praktisch an dieser einen Zahl, und was "
              "sie bedeutet, war bis Befund 278 nicht gemessen.\n    "
              "**Geaendert wurde nichts.** Die Schwelle steht unveraendert "
              "bei 0,95, und sie wird nicht gesenkt, damit etwas besteht - "
              "am wenigsten, wenn die Messung entsteht, waehrend der eigene "
              "Kandidat dicht an der Frage steht. Zu entscheiden ist, ob die "
              "Latte weiter auf einer Zahl stehen soll, die bei diesem "
              "Versuchsstand etwas anderes bedeutet als ihr Name - oder auf "
              "einem gemessenen Fehlalarmniveau. Beides ist vertretbar; die "
              "Wahl ist eine Geschaeftsentscheidung und faellt nicht hier."
              "\n    Zwei Einschraenkungen gehoeren dazu: Die gezogenen "
              "Versuche sind unabhaengig, die echten korreliert - "
              "korrelierte liefern ein kleineres Maximum und damit noch "
              "weniger Fehlalarme, das Gemessene ist also die guenstigste "
              "Lesart fuer die Latte. Und 5.000 Laeufe koennen hoechstens "
              "'kein einziger' sagen, also unter 0,02 %.",
        befund=278,
    ),
    Entscheidung(
        frage="Womit das Plateau-Gate seine Nachbarn misst",
        zahl="Das Gate faehrt seine zwoelf Nachbarn als **durchgehenden** "
             "Backtest je Bein - acht Jahre, ein Risk-Officer, keine "
             "Fenstergrenze. Die Engine rechnet im Walk-Forward "
             "ausdruecklich damit, dass ein ausgeloester Not-Aus zwischen "
             "den Fenstern freigegeben wird, und nennt einen Lauf ohne diese "
             "Annahme *'in der anderen Richtung falsch'*. Gemessen (313, "
             "Perpetual, BTC + ETH):"
             "\n      Nachbar                durchgehend   Walk-Forward"
             "\n      alle gemeinsam x1,2       -103,63        +233,04"
             "\n      sma(period=50) x1,2       -103,90        +239,08"
             "\n      Gate-Wert                   0,500          1,000"
             "\n    12 von 12 Nachbarn wurden nicht zu Ende gemessen, "
             "zusammen 1020 verhinderte Einstiege; die beiden oben haben ab "
             "Mai bzw. September 2020 nicht mehr gehandelt. `cli freigabe` "
             "rechnet es nach.",
        warum="**Geaendert wurde nichts.** Gerechnet wird weiter "
              "durchgehend, Wert und Urteil des Gates stehen unveraendert - "
              "geaendert ist nur, dass die Botschaft keine Form mehr "
              "behauptet, die an einem abgeschalteten Lauf nicht gemessen "
              "wurde.\n    Zu entscheiden ist, welche der beiden Messarten "
              "das Gate meint. Fuer den durchgehenden Lauf spricht, dass er "
              "die Verlustgrenzen ernst nimmt, wie sie im Betrieb gelten: "
              "Wer nicht freigibt, handelt nicht mehr. Fuer den "
              "Walk-Forward spricht, dass jede andere Zahl dieses Projekts "
              "so entsteht - und dass ein Gate, das ueber die Form eines "
              "Parametergebiets urteilt, den Zeitpunkt einer Sperre nicht "
              "als Form lesen sollte.\n    Es ist eine "
              "Geschaeftsentscheidung, weil sie ein Gate von "
              "'durchgefallen' auf 'bestanden' verschoebe - am "
              "Perpetual-Punkt von 7 auf 8 von 11 -, und weil sie entsteht, "
              "waehrend der eigene Kandidat genau daran haengt. Dieselbe "
              "Lage wie in Befund 278, und dieselbe Antwort: messen, "
              "hinschreiben, nicht selbst entscheiden.\n    Die Gegenprobe "
              "gehoert dazu, damit der Befund nicht nur dort geprueft ist, "
              "wo er nuetzt: Am **Spot**-Punkt besteht das Gate unter beiden "
              "Messarten (1,000 gegen 1,000), und das Kosten-Stress-Gate, "
              "das denselben durchgehenden Lauf benutzt, bleibt mit +945,06 "
              "gegen +2316,29 in beiden Faellen bestanden.",
        befund=313,
    ),
    Entscheidung(
        frage="Funding-Satz",
        zahl="Nie gemessen. `data_store/funding/` ist leer, und der Backtest "
             "setzt den Bybit-Basiswert von 0,01 % je Achtstundenperiode ein "
             "- rund 11 % im Jahr. Am Betriebspunkt sind das 67,24 Euro gegen "
             "7,60 Euro Handelsgebuehren, also rund das **Neunfache**, und 8,2 % "
             "des Bruttogewinns. Die Bilanz reicht ueber die gemessene Leiter "
             "von 9 von 11 (bei 0 %) bis 3 von 11 (bei 55 %); bei 11 % steht "
             "sie auf 7. `cli finanzierung` rechnet es nach.",
        warum="Der groesste Kostenblock des Systems steht auf einem "
              "Vorgabewert - und **beide** Gates, die am Funding haengen "
              "(Schlechtestes Jahr, Parameter-Plateau), kippen unterhalb von "
              "ihm; wo genau, steht je Gate bei 'cli funding' (Befund 250). "
              "Was gemeldet wird, ist also der Zustand nach dem Kippen. Und "
              "der Vorgabewert "
              "ist der **Basiswert**, nicht der Durchschnitt: Der Bestand ist "
              "eine Long-Trendfolge und im Markt, wenn der Trend steigt, also "
              "wenn Longs am meisten zahlen. Liegt die wahre Rate darueber, "
              "steht der Kandidat schlechter da als gemeldet. Echte Raten "
              "gibt es nur von Bybit, und die sind aus dem "
              "Entwicklungscontainer nicht erreichbar - das ist eine Sperre "
              "dieser Sandbox, keine des Systems. Auf dem eigenen Rechner: "
              "`python -m cli funding --von 2020-03-30`, sofern das Konto "
              "Perpetuals fuehrt.",
        befund=250,
    ),
    Entscheidung(
        frage="Umfang des Kosten-Stress-Tests",
        zahl="Das Gate verdoppelt Gebuehren und Slippage und laesst das "
             "Funding unveraendert - also den kleineren Posten. Mit "
             "mitverdoppeltem Funding faellt die Marge von 942,87 auf 625,80 "
             "Euro, das sind **34 %**. Das Urteil kippt dabei nicht: Der "
             "Bestand bleibt auch dann im Plus. `cli finanzierung --stress` "
             "rechnet es nach.",
        warum="Betroffen ist die Aussagekraft des Gates, nicht sein Ergebnis "
              "hier - deshalb ist es keine dringende Korrektur, sondern eine "
              "Abwaegung. Dagegen spricht die Vergleichbarkeit: Alle 45 "
              "Eintraege der Bestenliste sind unter dem schwaecheren Stress "
              "gemessen, und eine Verschaerfung macht kuenftige Laeufe mit "
              "ihnen unvergleichbar - dieselbe Kollision wie beim Kontostand "
              "in Befund 96. Dafuer spricht, dass ein Gate messen sollte, was "
              "es zu messen behauptet. Der Standard wurde nicht angefasst; "
              "die Entscheidung liegt beim Nutzer.",
        befund=96,
    ),
    Entscheidung(
        frage="Kontogroesse",
        zahl="Bei 500 Euro laufen 51 % aller Trades auf der Mindestmenge der "
             "Boerse. Ab rund 2000 Euro verschwindet die Beschraenkung. Und "
             "seit Befund 95 ist beziffert, was daran haengt: Der Rueckgang "
             "des Bestands steigt mit dem Konto von 9,92 % (300 Euro) auf "
             "12,95 % (100.000 Euro) - **dieselbe Strategie**. Das "
             "Rueckgang-Gate haelt nur unterhalb von rund 1150 Euro. Ursache "
             "ist die Mengenrundung, belegt durch zwei unabhaengige "
             "Gegenproben; `cli koernung` rechnet es nach. Befund 96 hat alle "
             "elf Gates ueber dieselbe Leiter gefahren: **Genau zwei wandern** "
             "- Rueckgang und schlechtestes Jahr, beides Risikomasse auf der "
             "Kapitalkurve. Neun stehen still, darunter der Deflated Sharpe "
             "(0,772 bis 0,786 ueber den ganzen Bereich). Die Bilanz laeuft "
             "von 8 von 11 bei 300 Euro auf **6 von 11** ab 1500 Euro; die "
             "hier gemeldeten 7 von 11 gelten fuer 500 Euro.",
        warum="Dort bestimmt nicht mehr die Strategie die Positionsgroesse, "
              "sondern die Boerse - die Risikosteuerung greift bei der Haelfte "
              "der Trades nicht. Es ist damit auch keine reine "
              "Betriebsentscheidung mehr: Eines der acht bestandenen Gates "
              "haelt nur, solange das Konto klein bleibt. Wer auf 2000 Euro "
              "aufstockt, aendert an der Strategie nichts und reisst es "
              "trotzdem.",
        befund=95,
        zuletzt=96,
    ),
    Entscheidung(
        frage="Wochenverlustgrenze",
        zahl="Bei -7 % pausiert das System bis zur **manuellen** Freigabe.",
        warum="Richtig so gebaut, aber es wird im Betrieb Telegram-Meldungen "
              "geben, nach denen das System steht, bis jemand es freigibt. "
              "Ob das so bleiben soll, ist eine Betriebsentscheidung.",
    ),
    Entscheidung(
        frage="Soll die Research-KI mitlaufen",
        zahl="**Verlangt ist heute etwas anderes als damals** (291/292): "
             "0,2641 je Trade bei n_eff 254 - und der Tageskatalog hat beide "
             "Haelften gezeigt, nie zusammen. Fuenf von 18 Regeln haben diese "
             "Qualitaet je Trade erreicht, keine davon ueber n_eff 58. Wer "
             "die Zahlen unten liest, liest die Latte von damals.\n    "
             "Neun gemessene Vorschlaege, keiner hat die Latte geraeumt "
             "(gebraucht war damals: 120 Trades bei Guete ueber 0,23, "
             "Befund 74/75)."
             "\n    Fuenf aus Befund 76, noch unter dem alten Auftrag, der "
             "den Deflated Sharpe nicht nannte und auf 100 Trades zielte: "
             "vier mit 68 bis 123 Trades, keiner ueber 0,25."
             "\n    Vier aus Befund 77, eigens gegen den **berichtigten** "
             "Auftrag gebaut:"
             "\n      Enge vor Bewegung              18 Trades  0,3405 "
             "(noetig 0,9047)"
             "\n      Volumenschock mit Fortsetzung 114 Trades  0,1584 "
             "(noetig 0,2652)"
             "\n      Rueckkehr zum Schwerpunkt      92 Trades -0,1201 "
             "(noetig 0,2967)"
             "\n      Abgriff des Vortagestiefs     406 Trades -0,1201 "
             "(noetig 0,1514)"
             "\n    Diese vier haben trotzdem etwas erbracht, nur keinen "
             "Kandidaten: Ihre Fensterkorrelation lag bei +0,06 bis +0,42 "
             "gegen eine Schwelle von 0,8 - Unabhaengigkeit ist **leicht**. "
             "Das Nadeloehr ist die Kopplung von Haeufigkeit und Guete, und "
             "sie haben Befund 75 von n = 14 (r = -0,533) auf n = 18 "
             "(r = -0,602, t = -3,02) gehoben.",
        warum="Nach Befund 145 sind alle gemessenen Richtungen leer, und was "
              "fehlt, ist eine Regel, die es noch nicht gibt. Der Katalog "
              "kann sie nicht liefern (Befund 75), 'breed' bildet nur "
              "Abwandlungen - die KI ist das einzige gebaute Bauteil, das "
              "eine vorschlagen kann.\n    Dagegen steht der Preis, und er "
              "ist keine Kleinigkeit: **Jeder Vorschlag zaehlt als Versuch "
              "und hebt die Huerde des Deflated Sharpe fuer alle folgenden** "
              "(Befund 71), dazu kommen Modellkosten gegen das Monatsbudget. "
              "Eine Serie erfolgloser Vorschlaege macht den Bestand also "
              "messbar schlechter."
              "\n    Zu entscheiden ist damit, ob neun erfolglose Versuche "
              "gegen diese Quelle sprechen oder ob sie zu wenige sind, um "
              "etwas zu sagen. Beides ist vertretbar: Neun Nieten sind kein "
              "Beweis, dass die zehnte auch eine ist - und sie sind auch "
              "kein Grund, mit der zehnten zu rechnen. Was die vier aus "
              "Befund 77 gebracht haben, war Methodenwissen und kein "
              "Kandidat; ob das den Aufschlag wert ist, ist eine "
              "Geschaeftsfrage und faellt nicht hier. Beide Wege stehen als "
              "Befehlszeile unter 'Nur auf deinem Rechner'.",
        befund=74,
        # 292 hat dem Auftrag an die KI gesagt, worin der Unterschied
        # bestehen muss. Wer sie heute laufen laesst, stellt eine andere
        # Frage als bei 74/77 - das gehoert in die Entscheidung.
        zuletzt=292,
    ),
    # **Hier stand in Befund 305 eine zehnte Entscheidung, und sie war
    # falsch gestellt** (Befund 306). "'Neues Hoch im Takt' neu bauen - ein
    # Versuch" las sich wie eine offene Abwaegung und zitierte die 70 %/19 %
    # und die 0,2137, als brachte ein Nachbau sie mit.
    #
    # Befund 283 hatte genau das schon nachgesehen und verneint: Von der
    # Beschreibung sind ein Name, eine Eigenschaft und zwei Kennzahlen da -
    # keine Regel. Ein Nachbau waere Erfinden, und fuer frische Vermutungen
    # auf der Einstiegsseite steht ein gemessener Vorwert dagegen (272, 274,
    # 276). Die Richtung bleibt offen; ein Weg dorthin ist sie nicht, und
    # eine Entscheidung ist sie damit auch nicht.
    #
    # Entstanden ist der Fehler daraus, dass ich die Zusammenfassung der
    # offenen Richtung gelesen habe und nicht den Befund, auf den sie zeigt -
    # dieselbe Bauart wie in 302. Der Eintrag traegt die Schlussfolgerung
    # von 283 jetzt selbst.
)


@dataclass(frozen=True, slots=True)
class Auftragspunkt:
    """Ein Punkt aus dem Auftrag und sein gemessener Stand.

    **Warum es das braucht.** Der Auftrag listet in jeder Runde dieselben
    offenen Punkte. Zwei davon waren zu diesem Zeitpunkt laengst abgearbeitet -
    die 15-Minuten-Generationen seit Befund 29, das Termin-Overlay seit Nummer
    zwoelf -, aber es gab keine Stelle, an der das nachzulesen war. Also
    standen sie weiter da, und ich habe sie weiter als offen gelesen.

    Das ist nicht nur unordentlich, es ist **teuer**: Beinahe waeren vierzehn
    Versuche fuer eine Messung ausgegeben worden, die es schon gab. Genau
    davor warnt ``load_seeds`` seit jeher - jeder Wiederholungsversuch hebt die
    Huerde des Deflated Sharpe fuer alle folgenden, ohne etwas beizutragen.

    ``befund`` ist Pflicht, sobald ein Punkt als erledigt gilt: Erledigt ohne
    Fundstelle ist eine Behauptung.

    ``zuletzt`` seit Befund 304 - und es ist derselbe Mangel, den ``Richtung``
    in Befund 130 abgelegt hat, hier nur 174 Befunde spaeter bemerkt. Der
    Punkt "Generation 6/7 auf 15-Minuten" zeigte auf Befund 29 ("alle 14
    gemessen, 1 von 9 Gates"), waehrend Befund 297 denselben Vorrat mit 36
    Regeln nachgemessen hat. Wer eine Fundstelle nennt, muss die **letzte**
    nennen; die erste ist Geschichte, nicht Stand.

    Dass ausgerechnet dieses Register veraltet, ist das Teure daran: Es ist
    das einzige, das die Punkte des Auftraggebers beantwortet.
    """

    frage: str
    stand: str
    befund: int = 0
    erledigt: bool = True
    zuletzt: int | None = None

    def __post_init__(self) -> None:
        if self.erledigt and self.befund <= 0:
            raise ValueError(
                f"'{self.frage}' gilt als erledigt, hat aber keine Fundstelle "
                f"im BEFUND - das waere eine Behauptung."
            )
        if self.zuletzt is not None and self.zuletzt <= self.befund:
            raise ValueError(
                f"'{self.frage}': Nachmessung in Befund {self.zuletzt} liegt "
                f"nicht nach der Erstmessung in {self.befund} - dann ist es "
                f"keine Nachmessung."
            )

    @property
    def massgeblich(self) -> int:
        """Die Fundstelle, in der der gueltige Stand steht."""
        return self.zuletzt or self.befund

    def __str__(self) -> str:
        if not self.befund:
            marke = "offen"
        elif self.zuletzt is None:
            marke = f"Nr. {self.befund}"
        else:
            # Komma und keine zweite Klammer: 'Nr. 297 (zuerst 29)' stuende
            # hier in einer Klammer und ergaebe eine geschachtelte - genau
            # das hat Befund 293 an derselben Stelle abgestellt.
            marke = f"Nr. {self.zuletzt}, zuerst {self.befund}"
        return f"{'OK' if self.erledigt else '--'} {self.frage:34} {self.stand}  ({marke})"


#: Die Punkte aus dem Auftrag, mit ihrem gemessenen Stand.
AUFTRAG: tuple[Auftragspunkt, ...] = (
    # Seit Befund 59 offen, in 271 mit derselben Gegenprobe geschlossen, die
    # fuer Schock (58) und Abkuehlung (44) gilt.
    Auftragspunkt(
        frage="P7: News- und Termin-Overlay",
        stand="gebaut, gemessen und geprueft (271): Der Kalender traegt 138 "
              "Termine und sperrt in acht Jahren **sechs** Einstiege. Fuer "
              "sich genommen bringt das +2,47 EUR auf 766 und hebt den Sharpe "
              "je Trade von 0,2680 auf 0,2708. In der Sperrprobe haelt der "
              "Effekt nicht stand: **100 % der zufaelligen Sperren derselben "
              "Groesse halten genauso viele Gates.** Es war nicht die "
              "Auswahl, sondern das Streichen. Das Overlay schadet nicht und "
              "ist zu klein, um zu zaehlen - gegen den Zuwachs, den Befund 269 "
              "verlangt, faellt es nicht ins Gewicht",
        befund=271,
        erledigt=True,
    ),
    # Der Punkt ist erledigt, sein **Auftrag** war es nicht: Befund 180 fand
    # ihn drei Befunde stale, 183 nahm vier Zahlen zurueck, 193 hat sein Ziel
    # neu gerechnet, und 196 hat gefunden, dass er das Holdout-Ergebnis
    # verschwieg. Wer die KI erneut laufen laesst, bekommt jetzt einen
    # anderen Auftrag als beim letzten Mal.
    Auftragspunkt(
        frage="Research-KI im Wettbewerb nutzen",
        stand="genutzt, vier Vorschlaege gemessen - alle schlechter; der "
              "Auftrag nennt seit 196 auch, dass sieben Partner die "
              "Kriterien erfuellt haben und draussen durchgefallen sind. "
              "Seit 292 nennt er ausserdem, **worin** der Unterschied "
              "bestehen muss: viel Qualitaet je Trade **und** viele Trades - "
              "beide Haelften gibt es im Katalog, nie zusammen",
        befund=196,
        zuletzt=292,
    ),
    # **Nachgezogen in Befund 304.** Der Stand zeigte auf Nummer 29 und nannte
    # 14 Regeln; Befund 297 hat denselben Vorrat mit **36** gemessen, und das
    # Ergebnis ist haerter, nicht milder.
    Auftragspunkt(
        frage="Generation 6/7 auf 15-Minuten",
        stand="der ganze 15-Minuten-Vorrat nachgemessen (297): 1 von 36 "
              "Regeln hat positive Guete, der Median der Luecken liegt bei "
              "11,3 Guetepunkten gegen 2,1 auf Tageskerzen - dieser Vorrat "
              "hat keine Decke, er hat keinen Boden",
        befund=29,
        zuletzt=297,
    ),
    Auftragspunkt(
        frage="Generation 5 auf Tageskerzen",
        stand="Zuordnung liegt jetzt als Daten vor, Fehlpaarung wird gesperrt",
        befund=64,
    ),
    # **Der Satz stimmte, bis der Behaelter zurueckgesetzt wurde** (Befund
    # 151). ``data_store`` liegt nicht im Repository; die 15-Minuten-Kerzen
    # waren danach weg, und dieser Eintrag behauptete sie fuenf Befunde lang
    # weiter. Was hier steht, ist gepflegte Prosa - was wirklich im Speicher
    # liegt, zeigt ``cli stand`` gemessen (Befund 157).
    #
    # Befund 171 hat sie ueber ``cli referenz`` neu geholt - Bitstamp, nicht
    # Bybit. Damit ist die Forschung wieder moeglich; die Zulassung bleibt an
    # den Boersendaten und die an der Regionssperre.
    Auftragspunkt(
        frage="backfill Bybit-TAGESkerzen beim Nutzer",
        stand="**Nicht 15 Minuten** (Befund 307): Die 15-Minuten-Kerzen sind "
              "da (225.000 je Markt, Bitstamp) und der Katalog darauf "
              "gemessen - 34 von 36 Regeln negativ, beste Guete 0,744 gegen "
              "3,964, und 297 hat das auf 36 Regeln bestaetigt. Offen ist "
              "etwas anderes: Alle elf Gates stehen auf **Tageskerzen** "
              "(213), und jede Zahl dieses Projekts steht auf "
              "Bitstamp-Kassakursen. Gebraucht werden Bybit-Tageskerzen, und "
              "die gibt es nur beim Nutzer - die Zeilen dafuer stehen unter "
              "'Nur auf deinem Rechner'",
        befund=171,
        erledigt=False,
    ),
)


#: Was nur auf dem Rechner des Nutzers laufen kann.
#:
#: Der Entwicklungscontainer ist von Bybit aus Regionsgruenden gesperrt. Das
#: ist eine Eigenschaft dieser Sandbox, keine von Bybit und keine des Systems.
#:
#: ``{vergleich}`` wird von ``Lage`` durch den **gemessenen** Vergleich beider
#: Betriebspunkte ersetzt. Bis Befund 165 standen die Zahlen dort als Prosa -
#: eine zweite Kopie neben der Gegenueberstellung im selben Bericht, und sie
#: ist stehengeblieben, waehrend die Messung weiterlief:
#:
#:     behauptet   14,83 % statt 13,47 %, Messlatte 0,17 Punkte
#:     gemessen    14,34 % statt 12,95 %, Messlatte 0,66 Punkte
#:
#: Die Gate-Zahlen (9 von 11 statt 7) stimmten noch. Das ist der Grund, warum
#: der Eintrag nicht auffiel: Die Haelfte, die man prueft, war richtig.
#: **Die Reihenfolge ist die Reihenfolge** (Befund 249). Bis hierher stand
#: ``abgleich`` an zweiter Stelle, obwohl sein eigener Text sagt *"Vor jedem
#: Livegang auszufuehren"*, und ``funding`` an letzter, obwohl bis dahin jede
#: Zahl mit dem Vorgabewert rechnet. Wer eine Liste von Befehlen sieht, liest
#: sie als Folge - das war schon der Kern von Befund 167, dort als Prosa
#: gegen Befehlszeile.
#:
#: Geordnet nach dem, was die Eintraege selbst sagen: klaeren, laden, suchen,
#: und zuletzt der Abgleich vor dem Livegang. Ein Test haelt jede der vier
#: Bedingungen einzeln fest.
BEIM_NUTZER: tuple[tuple[str, str], ...] = (
    (
        "python -m cli healthcheck",
        "Bietet das Konto Perpetuals an? Seit der MiCA-Migration womoeglich "
        "nur noch Spot. **Und das waere kein Rueckschritt:** Befund 106 hat "
        "gemessen, dass der Kandidat seinen Hebel an 0,2 % der Balken nutzt "
        "und long-only ist - der Deckel auf 1,0 aendert die Zahlen bitgleich "
        "nicht. Was sich aendert, ist das Funding. {vergleich} "
        "`cli instrument` rechnet es nach.",
    ),
    (
        "python -m cli backfill --intervall D --von 2017-08-16",
        "Laedt Bybit-Kerzen. **Ohne sie kann nichts zugelassen werden** - "
        "jede Zahl dieses Projekts steht auf Bitstamp-Kassakursen, und die "
        "sind nicht das gehandelte Instrument. Seit Befund 102 sagt das "
        "System das auch: Ein Bericht auf Forschungskerzen gilt nie als "
        "zugelassen, egal wie viele Gates halten. **Das Intervall gehoert "
        "dazu**: Ohne '-i' laedt der Befehl 1m/15m/1h/4h und **keine** "
        "Tageskerzen - und auf denen stehen alle elf Gates (Befund 213).",
    ),
    (
        "python -m cli funding --von 2020-03-30",
        "Laedt die echten Funding-Raten. Bisher rechnet jede Zahl mit dem "
        "Vorgabewert, und der ist der groesste Kostenblock des Systems - das "
        "Neunfache der Handelsgebuehren (Befund 100). **Wonach zu schauen "
        "ist, steht seit Befund 250 fest:** Der Kandidat vertraegt bis "
        "6,0 % im Jahr, dann faellt 'Schlechtestes Jahr'; bei 9,8 % faellt "
        "'Parameter-Plateau'. Der Vorgabewert steht bei 10,9 % - also "
        "jenseits von beiden. Liegt die wahre Rate darunter, gewinnt der "
        "Kandidat Gates zurueck, ohne dass sich an ihm etwas aendert. "
        "**Gebraucht wird dafuer die Reihe und nicht ihr Mittelwert** "
        "(266): Folgt die Rate der Marktrichtung, faellt 'Schlechtestes "
        "Jahr' schon unterhalb von 5,8 % - gleicher Mittelwert, ein Gate "
        "weniger. "
        "**Und seit Befund 265 kommt das auch an:** Bis dahin gingen die "
        "geladenen Raten allein an die Kerzen - die Strategie sah sie, "
        "gezahlt wurde weiter der Vorgabewert, und dieser Satz hier "
        "versprach etwas, das kein Lauf eingeloest haette.",
    ),
    (
        "python -m cli wettbewerb --generation 9",
        "Sucht auf den geladenen Kerzen einen Kandidaten. Bis Befund 167 "
        "stand dieser Schritt als ', dann wettbewerb' hinter dem Backfill in "
        "derselben Zeile - keine Befehlszeile, sondern Prosa: Wer sie "
        "kopierte, bekam 'Got unexpected extra argument(s)'. Er legt auch "
        "'state/leaderboard.json' neu an, die in diesem Behaelter fehlt "
        "(Befund 166). **Die Generation gehoert dazu**: Die Vorgabe ist 8, ein Viertelstunden-Katalog, und der Backfill darueber laedt Tageskerzen - der Lauf braeche mit leerem Speicher ab (Befund 214). Neun ist der Tageskerzen-Katalog mit den meisten Regeln. So aufgerufen laeuft er **ohne** die Research-KI und "
        "bildet nur Abwandlungen dessen, was der Katalog schon kennt - die "
        "Zeile darunter ist der andere Weg, und welcher richtig ist, steht "
        "unter 'Was nicht bei mir liegt'. **Vorher lesen, was Befund 272 "
        "gemessen hat:** 'cli scan' findet auf BTC und ETH, auf Tages- wie "
        "Viertelstundenkerzen, keinen belastbaren Vorteil in der Familie, aus "
        "der der Bestand stammt - wo etwas auffaellt, ist es in der zweiten "
        "Haelfte des Zeitraums verschwunden. Versuche hier auszugeben hebt "
        "die Huerde, ohne dass etwas zu holen waere. Das gilt fuer diese "
        "Daten; mit Bybit-Kerzen ist es neu zu messen. {versuchskosten}",
    ),
    (
        "python -m cli wettbewerb --generation 9 --ki",
        "Dasselbe, aber die Research-KI schlaegt je Runde zusaetzlich neue "
        "Kandidaten vor. Das ist das einzige gebaute Bauteil, das eine Regel "
        "vorschlagen kann, die es noch nicht gibt - und nach Befund 145 ist "
        "genau das die Luecke, denn alle gemessenen Richtungen sind leer. "
        "Ohne LLM__ANTHROPIC_API_KEY sagt der Befehl das und laeuft normal "
        "weiter, kaputt geht dabei nichts. Was es kostet und was dagegen "
        "spricht, steht unter 'Was nicht bei mir liegt' - es ist eine "
        "Entscheidung und keine Empfehlung.",
    ),
    (
        "python -m cli abgleich",
        "Erzeugt der Livebetrieb dieselben Signale wie der Backtest? Vor "
        "jedem Livegang auszufuehren.",
    ),
)


@dataclass(slots=True)
class Lage:
    """Der gemessene Stand - alles daran kommt aus einer Messung."""

    kandidat: str
    maerkte: str
    trades: int
    sharpe_je_trade: float
    noetiger_sharpe: float | None
    bestanden: int
    gesamt: int
    offen: tuple[str, ...]
    versuche: int
    cagr_pct: float = 0.0
    rueckgang_pct: float = 0.0

    effektiv: int | None = None
    """Die **effektive** Stichprobe, auf die sich ``noetiger_sharpe`` bezieht.

    ``trades`` ist die rohe Zahl. Das Gate urteilt seit Befund 135 ueber die
    effektive, und die ist kleiner. Fehlt dieses Feld, steht in ``urteil``
    eine Untergrenze - so, wie ``suchbudget`` es seit Befund 139 haelt
    (Befund 148).
    """

    betriebspunkt: str = ""
    """Unter welchen Handelsbedingungen **diese** Zahlen gemessen sind.

    **Befund 311.** Die Kopfzeilen nannten Kandidat, Maerkte, Kerzenlaenge,
    Trades, Rendite, Rueckgang, Gates und Versuche - und nicht den Punkt.
    Dabei entscheidet er mit, welche Gates halten: Derselbe Kandidat steht am
    Perpetual-Punkt bei 7 von 11 und am Spot-Punkt bei 9 von 11 (Befund 106),
    und die offenen Gates sind andere. Wer die Uebersicht liest, bekam eine
    von zwei Zahlen ohne den Hinweis, dass es zwei gibt.

    Dieselbe Lehre wie in 187 (das Kostenurteil sprach die Antwort von
    Tageskerzen), 190 (ein Vorrat gehoert an seine Kerzenlaenge) und 280
    (ohne Betriebspunkt ist das Urteil unvollstaendig) - nur auf der
    Titelseite, wo sie am laengsten gefehlt hat.

    Leer heisst "nicht angegeben" und wird als solches gedruckt.
    """

    zweitpunkt: object | None = None
    """Der andere Betriebspunkt, gemessen - oder ``None``.

    Ein ``research.betriebspunkt.Betriebspunkt``; nur als ``object``
    annotiert, damit dieses Modul keine Abhaengigkeit auf die Messung
    bekommt, die es beschreibt. Gebraucht wird er fuer ``{vergleich}`` in
    ``BEIM_NUTZER`` (Befund 165).
    """

    kerzenbestand: str = ""
    """Was **wirklich** im Kerzenspeicher liegt, je Symbol und Intervall.

    Gemessen und nicht gepflegt (Befund 157): Ein Auftragspunkt behauptete
    fuenf Befunde lang, die 15-Minuten-Daten laegen vor - sie waren beim
    Behaelterwechsel in Befund 151 verschwunden. Prosa kann veralten, diese
    Zeile nicht.
    """

    zensiert: int = 0
    """Trades, die das Datenende glattgestellt hat statt der Regel.

    Sie stecken in Rendite und Rueckgang - dort ist die offene Position zum
    letzten Kurs bewertet und damit der Kontostand. In ``trades``,
    ``sharpe_je_trade`` und ``effektiv`` stecken sie **nicht**: Eine nicht zu
    Ende gehandelte Position ist keine fertige Beobachtung (Befund 152).

    Wird die Zahl groesser als eine Handvoll, ist der Nachlauf zu kurz -
    ``backtest.walkforward.nachlauf_fuer`` und ``research.randschnitt``.
    """

    @property
    def zugelassen(self) -> bool:
        return self.gesamt > 0 and self.bestanden == self.gesamt

    @property
    def faktor(self) -> float | None:
        """Um welchen Faktor die Qualitaet je Trade steigen muesste."""
        if self.noetiger_sharpe is None or self.sharpe_je_trade <= 0:
            return None
        return self.noetiger_sharpe / self.sharpe_je_trade

    @property
    def menge(self) -> int | None:
        """Wie viele wirksame Beobachtungen **dieselbe** Qualitaet braeuchte.

        **Das zweite Tor, und bis Befund 178 stand hier nur das erste.** Der
        Bericht nannte einen noetigen Zuwachs an Qualitaet je Trade und liess
        offen, dass die Latte oberhalb von rund 60 wirksamen Beobachtungen
        viel langsamer steigt als die Wurzel. Wer nur die Qualitaetszahl
        liest, sucht nach einer besseren Regel - und der gemessene Wert ist
        das Beste, was 198 Versuche hergegeben haben.

        ``None``, wenn die effektive Stichprobe fehlt (dann gaebe es nichts
        zu vergleichen) oder wenn diese Qualitaet auch bei sehr vielen
        Beobachtungen nicht genuegt.

        **Und es ist kein billigeres Tor** (Befund 179). Der erste Anlauf hat
        es so gelesen; gemessen an der Geraden des Vorrats kostet der Weg
        dorthin mehr Vorsprung, als die fallende Latte spart. Die Zahl bleibt
        richtig - was sie wert ist, entscheidet die Kopplung.
        """
        from research.verbund import noetige_stichprobe

        if self.effektiv is None or self.sharpe_je_trade <= 0:
            return None
        return noetige_stichprobe(self.sharpe_je_trade, self.versuche)

    def urteil(self) -> str:
        if self.zugelassen:
            return (
                f"'{self.kandidat}' besteht alle {self.gesamt} Gates. Damit ist "
                f"er zugelassen - was noch nicht heisst, dass Geld darauf "
                f"gehoert: Es folgen dreissig Tage Demo."
            )
        fehlend = ", ".join(self.offen) if self.offen else "-"
        text = (
            f"Kein zugelassener Kandidat. '{self.kandidat}' steht bei "
            f"{self.bestanden} von {self.gesamt}; offen: {fehlend}."
        )
        if self.faktor is not None:
            # **Als Zuwachs formuliert, nicht als Verhaeltnis.** Der erste
            # Anlauf schrieb "es fehlen 110 %" fuer einen Faktor von 1,10 -
            # das liest sich, als fehle mehr als alles Vorhandene. Gemeint
            # sind zehn Prozent mehr.
            #
            # **Und die Stichprobe gehoert dazu.** Die Latte haengt an ihr;
            # ohne die Zahl daneben liest sich der Zuwachs, als gaebe es nur
            # einen (Befund 148).
            wie = "mindestens " if self.effektiv is None else ""
            bezug = (
                f" bei {self.effektiv} unabhaengigen Beobachtungen"
                if self.effektiv is not None
                else f" bei {self.trades} rohen Trades"
            )
            text += (
                f" Dafuer muesste die Qualitaet je Trade um {wie}"
                f"{self.faktor - 1:.0%} steigen: {self.sharpe_je_trade:.4f} "
                f"auf {wie}{self.noetiger_sharpe:.4f}{bezug}."
            )
            if self.effektiv is None:
                text += (
                    " Die effektive Stichprobe ist hier nicht gemessen; das "
                    "Gate rechnet mit ihr, und sie ist kleiner - die "
                    "wirkliche Latte liegt also hoeher."
                )
            text += self._mengentor()
        return text

    def _mengentor(self) -> str:
        """Dasselbe Ziel ueber die Menge - der zweite Weg zur selben Schwelle.

        Er gehoert neben den ersten, weil er ein anderes Verlangen stellt:
        Der eine will eine **bessere** Regel, der andere dieselbe **oefter**.
        Nach 198 Versuchen ist das nicht dasselbe Angebot.
        """
        if self.effektiv is None:
            return ""
        ziel = self.menge
        if ziel is None:
            return (
                " Ueber die Menge ist es nicht zu holen: Bei dieser Qualitaet "
                "je Trade genuegt auch eine sehr grosse Stichprobe nicht."
            )
        if ziel <= self.effektiv:
            return ""
        return (
            f" **Oder ueber die Menge:** {ziel} wirksame Beobachtungen, "
            f"Faktor {ziel / self.effektiv:.2f} - aber nur **bei "
            f"unveraenderter Qualitaet**, und die haelt in diesem Vorrat "
            f"nicht: Qualitaet und Menge sind gekoppelt, der Weg dorthin "
            f"kostet mehr Vorsprung als er spart (Befund 179). Beide Tore "
            f"verlangen dasselbe."
        )

    def _zensurhinweis(self) -> str:
        """**Nicht in einer Fussnote.** Wer die Trade-Zahl liest, muss sehen,
        dass eine zweite daneben steht - sonst sucht er spaeter den
        Unterschied zwischen dieser Zeile und dem Log des Backtests."""
        if not self.zensiert:
            return ""
        return (
            f" (+{self.zensiert} am Datenende glattgestellt, in der Statistik "
            f"nicht gezaehlt)"
        )

    def _zweiter_weg(self) -> list[str]:
        """Der zweite, unabhaengige Weg zum selben Urteil - und wo er steht.

        Befund 168 hat den Bestand in seine eigene Grundgesamtheit
        eingeordnet: Sein Vorsprung vor der Geraden durch den Katalog ist
        **kleiner** als das, was Auswahl bei diesem Versuchsstand ohnehin
        erzeugt. Das ist dieselbe Aussage wie der Deflated Sharpe, auf einem
        Weg, der nichts von ihm weiss - der eine sieht die Verteilung der
        Trades, der andere die Lage des Kandidaten unter seinesgleichen.

        Bis Befund 172 stand das ausschliesslich in ``cli vorratsdecke``,
        einem Befehl, den niemand von sich aus aufruft. Wer ``cli stand``
        liest, sah "es fehlen 0,66 Guete" und hielt das fuer knapp.

        **Hier steht bewusst keine Zahl.** Sie wird gerechnet, nicht
        gepflegt; vier Befunde dieses Projekts handeln von Zahlen, die an
        zwei Stellen standen und auseinanderliefen (158, 159, 165, 166). Was
        hier steht, ist der Weg dorthin.
        """
        if self.zugelassen:
            return []
        return [
            "",
            "OB DER VORSPRUNG ECHT IST",
            "-" * 72,
            "  Der Deflated Sharpe fragt, ob die Trades des Kandidaten fuer",
            "  seinen Vorteil reichen. Eine zweite Frage steht daneben: Wie",
            "  weit liegt er ueber dem **Katalog, aus dem er ausgewaehlt**",
            "  wurde? Reine Auswahl erzeugt einen Vorsprung ganz von selbst.",
            "",
            "  Gemessen in Befund 168, eingeschraenkt in 169, auf",
            "  Viertelstunden geprueft in 171 - und dann **neu gemessen in",
            "  183**, weil der Katalog dieser drei nach der Groessenlogik",
            "  gefiltert war (Befund 182). 183 hat 168 und 169",
            "  zurueckgenommen, 188 die Viertelstunden ersetzt.",
            "",
            "  **Das Ergebnis war auch danach nicht beruhigend**, und der",
            "  Vorsprung des Bestands blieb kleiner als das, was Auswahl bei",
            "  diesem Versuchsstand ohnehin erzeugt.",
            "",
            "  Die Zahlen stehen hier absichtlich nicht: Nachrechnen mit",
            "  `cli vorratsdecke`.",
        ]

    def _aussichtszeilen(self) -> list[str]:
        """Wie weit es noch ist - **und was die Zeit ueberhaupt loest.**

        ``research.referenz.AUSSICHT`` rechnet die Entfernung seit Befund 132
        und ist bis Befund 160 an **keiner** Stelle angezeigt worden. Die
        meistzitierte vorausschauende Zahl des Projekts stand gepflegt,
        getestet und unsichtbar im Modul.

        Dazu gehoert die unbequeme Haelfte: Von den offenen Gates haengt
        **eines** an der Stichprobe. Wer wartet, loest dieses eine - und
        verliert ein anderes. 'Schlechtestes Jahr' ist ein Minimum ueber
        Zwoelfmonatsfenster und hat die Schwelle bei 2547 Tagen Historie
        gerissen; seither steht es bei -10,3 gegen -10,00 (Befund 161).
        """
        from research.referenz import (
            AUSSICHT,
            AUSSICHT_ERSTPUNKT,
            AUSSICHT_VERBUND,
            SPOTPUNKT,
        )

        if self.zugelassen:
            return []
        # **Die Entfernung haengt am Betriebspunkt** (Befund 316). ``AUSSICHT``
        # ist auf dem Spot-Punkt gerechnet - ein Test bindet sie daran -, und
        # bis hierher stand sie unter einem Kopf, der seit Befund 311
        # 'Perpetual' sagt. Der Unterschied ist keine Feinheit: 75 fehlende
        # Beobachtungen gegen 106, 5,9 Jahre gegen 8,3. Wer nur die erste
        # Zeile liest, haelt das Projekt fuer zweieinhalb Jahre naeher am
        # Ziel, als es an dem Punkt ist, den der Bericht meldet.
        zeilen = [
            "",
            "WIE WEIT ES NOCH IST",
            "-" * 72,
            f"  Bestand allein   {AUSSICHT_ERSTPUNKT.als_zeile()}",
            f"  derselbe am Spot {AUSSICHT.als_zeile()}",
            f"  bester Verbund   {AUSSICHT_VERBUND.als_zeile()}",
            "",
            f"  **Berichtet wird {AUSSICHT_ERSTPUNKT.betriebspunkt}** - die "
            f"erste Zeile gilt. Ohne Funding",
            "  ist die Guete je Trade hoeher und die Schwelle verlangt weniger",
            f"  Evidenz: {AUSSICHT.noetig} Beobachtungen statt "
            f"{AUSSICHT_ERSTPUNKT.noetig}, also "
            f"{AUSSICHT_ERSTPUNKT.jahre - AUSSICHT.jahre:.1f} Jahre weniger.",
            "  Derselbe Kandidat, dieselben Kerzen - nur der andere Punkt.",
            "",
            "  Untergrenzen, keine Termine - die Sammelrate ist die des",
            "  laengsten gemessenen Fensters (siehe research/referenz.py).",
        ]
        # **Auf welchem Betriebspunkt lohnt die Suche?** (Befund 220.) Die
        # Frage stand nirgends beziffert, obwohl beide Punkte gemessen sind.
        # Verglichen werden Verhaeltnisse, jedes auf seiner eigenen
        # Stichprobe - nicht Guete gegen fremde Latte (Befund 190).
        from research.erfuellung import bester_je_intervall
        from research.erfuellung import urteil as erfuellungsurteil

        beste = bester_je_intervall()
        if len(beste) >= 2:
            zeilen += ["", "  Wovon der beste Fund je Kerzenlaenge steht:"]
            zeilen += [
                f"     {p.intervall:>3}  {p.regel:30} {p.anteil:+.3f} der Latte"
                for p in sorted(beste.values(), key=lambda x: -(x.anteil or 0))
            ]
            zeilen += ["", "  " + erfuellungsurteil()]

        # **Der Verbund ist der einzige gemessene Hebel** (Befund 140), und
        # er stand in diesem Vergleich nicht (Befund 227).
        from research.erfuellung import vergleich_im_lauf

        verbundsatz = vergleich_im_lauf("Verbund 155")
        if "kein Vergleich" not in verbundsatz:
            zeilen += ["", "  " + verbundsatz]

        # **Der Preis des Suchens gehoert neben die Luecke** (Befund 226).
        # Befund 221 hat beide Zahlen gemessen und geschlossen, sie
        # gehoerten in denselben Satz - und hat sie dann in zwei Abschnitte
        # gelegt: die Luecke ins Urteil, den Preis unter 'Nur auf deinem
        # Rechner'. Wer nur eine liest, bekommt eine Stimmung statt einer
        # Messung.
        from research.verbund import noetige_guete

        # **Die Luecke aus den eigenen Zahlen** (Befund 230). Bis dahin kam
        # sie aus ``erfuellung`` und damit vom Spot-Punkt, waehrend der Kopf
        # dieses Berichts den Erstpunkt zeigt: Das Urteil sagte +15 %, dieser
        # Abschnitt +24,3 %, und nichts sagte, dass es zwei Punkte sind.
        heute = noetige_guete(
            SPOTPUNKT.effektiv, self.versuche,
            schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung,
        )
        spaeter = noetige_guete(
            SPOTPUNKT.effektiv, BUDGET.grenze,
            schiefe=SPOTPUNKT.schiefe, woelbung=SPOTPUNKT.woelbung,
        )
        luecke = (
            self.noetiger_sharpe / self.sharpe_je_trade - 1.0
            if self.noetiger_sharpe and self.sharpe_je_trade > 0
            else None
        )
        if luecke and heute and spaeter:
            preis = spaeter / heute - 1.0
            zeilen += [
                "",
                "  Was das Suchen selbst kostet:",
                f"     zu schliessende Luecke        {luecke:+7.1%}"
                f"   (dieser Betriebspunkt)",
                f"     Rest des Suchbudgets kostet   {preis:+7.2%}"
                f"   (fast punktunabhaengig)",
                "",
                f"  Der ganze Rest des Budgets hebt die Latte um "
                f"{preis / luecke:.0%} dessen, was",
                "  zu schliessen waere. Der Aufschlag liegt ueber die",
                "  gemessenen Stichproben von 80 bis 584 zwischen 1,11 % und",
                "  1,26 % - er haengt kaum am Betriebspunkt, die Luecke sehr",
                "  wohl. **Nicht der Aufschlag macht die Suche aussichtsarm,",
                "  sondern die Trefferquote** (Befund 31/221) - und wie",
                "  langsam der beste Fund nachzieht, rechnet 'cli rennen'",
                "  (Befund 71).",
            ]
        # Befund 160 hat das hier als **Ueberlegung** hingeschrieben. Befund
        # 161 hat es gemessen, und es ist schlimmer als die Ueberlegung.
        if self.offen:
            zeitgates = [g for g in self.offen if "Deflated Sharpe" in g]
            andere = [g for g in self.offen if g not in zeitgates]
            if zeitgates and andere:
                zeilen += [
                    "",
                    f"  **Die Zeit loest {len(zeitgates)} von {len(self.offen)} "
                    f"offenen Gates** - und bricht ein weiteres.",
                    "  Nur der Deflated Sharpe ist eine Funktion der Stichprobe.",
                    "  Offen bleiben: " + ", ".join(andere) + ".",
                ]
                if any("Schlechtestes Jahr" in g for g in andere):
                    zeilen += [
                        "",
                        "  Gemessen ueber sechs Historienlaengen (Befund 161):",
                        "     1451 d  +5,97    2547 d  -10,30  <- ab hier "
                        "durchgefallen",
                        "     1816 d  +5,44    2912 d  -10,30",
                        "     2320 d  -8,82    3300 d  -10,32   (Schwelle -10,00)",
                        "",
                        "  'Schlechtestes Jahr' nimmt das **Minimum** ueber alle",
                        "  Zwoelfmonatsfenster. Ein schlechtes Jahr, das einmal in",
                        "  der Reihe steht, geht nicht wieder heraus. Warten kann",
                        "  dieses Gate also nicht zurueckgewinnen.",
                    ]
        return zeilen

    def _zweitzeile(self) -> list[str]:
        """Der andere gemessene Punkt, in einer Zeile (Befund 311).

        Er steht im Kopf und nicht weiter unten, weil er dieselbe Frage
        anders beantwortet: Am Spot-Punkt haelt derselbe Kandidat mehr Gates,
        und welche offen bleiben, ist eine andere Liste.

        **Keine Empfehlung.** Den Kandidaten dorthin zu stellen, wo mehr
        Gates bestehen, ist genau die Anpassung, gegen die die
        Zulassungsstrecke gebaut ist - deshalb steht hier eine Zahl und kein
        Rat.
        """
        punkt = self.zweitpunkt
        if punkt is None:
            return []
        bestanden = getattr(punkt, "bestanden", None)
        gesamt = getattr(punkt, "gesamt", None)
        if bestanden is None or not gesamt:
            return []
        offen = ", ".join(getattr(punkt, "offen", ()) or ()) or "keines"
        return [
            f"  Auch gemessen  {getattr(punkt, 'name', '?')}: "
            f"{bestanden} von {gesamt}, offen: {offen}"
        ]

    def bericht(self, *, kurz: bool = False) -> str:
        """Der Stand als Text - vollstaendig oder auf das Handelnde gekuerzt.

        **Warum es die Kuerzung gibt** (Befund 248). Der volle Bericht ist auf
        1.053 Zeilen gewachsen, und die drei Abschnitte, die etwas von seinem
        Leser verlangen - was nicht bei ihm liegt, was nur auf seinem Rechner
        laeuft, was den Zustand aendert -, beginnen bei Zeile 754. Davor
        stehen ueber fuenfhundert Zeilen abgeschlossener Wege.

        Das ist die Klage aus Befund 114, eine Ebene hoeher: *"Das Wissen
        liegt im System, aber nicht dort, wo es die Arbeit steuern wuerde."*

        Gekuerzt wird genau um die beiden **Archive** - ``GESCHLOSSEN`` und
        ``BEHOBEN``. Der Schnitt ist nicht nach Gefuehl gewaehlt: Die
        Ueberschrift des zweiten sagt schon selbst *"sagt nichts ueber die
        Aussichten"*, und der Kopf von ``OFFEN`` nennt den Unterschied zu
        ``GESCHLOSSEN`` *"der wichtigere von beiden"*.

        Was bleibt, ist alles Gemessene ueber den **heutigen** Stand: Zahlen,
        Urteil, Aussichten, was offen ist, der Auftrag, die Entscheidungen und
        die Befehle fuer den Rechner des Nutzers. Gerechnet wird in beiden
        Faellen dasselbe - gekuerzt wird die Ausgabe, nicht die Messung.
        """
        zeilen = [
            "STAND",
            "=" * 72,
            f"  Kandidat   {self.kandidat}",
            # **Der Punkt gehoert in den Kopf** (Befund 311). Ohne ihn liest
            # sich '7 von 11' wie der Stand des Kandidaten; er ist der Stand
            # an **einem** von zwei gemessenen Punkten.
            f"  Gemessen   {self.maerkte}, "
            f"{self.betriebspunkt or 'Betriebspunkt nicht angegeben'}",
            *self._zweitzeile(),
            f"  Ergebnis   {self.trades} Trades{self._zensurhinweis()}, "
            f"{self.cagr_pct:.2f} % p.a., {self.rueckgang_pct:.2f} % Rueckgang",
            f"  Gates      {self.bestanden} von {self.gesamt}",
            f"  Versuche   {self.versuche}",
            f"  Suchbudget {BUDGET.zeile(self.versuche)}",
            "",
            self.urteil(),
            *self._aussichtszeilen(),
            *self._zweiter_weg(),
        ]
        if not kurz:
            zeilen += ["", "GEMESSEN UND GESCHLOSSEN", "-" * 72]
            zeilen.extend(f"  {r}" for r in GESCHLOSSEN)
        # **Und was noch offen ist** (Befund 208). ``OFFEN`` stand seit
        # seiner Anlage in diesem Modul und war an **keiner** Stelle
        # angezeigt - elf Eintraege, gepflegt ueber Dutzende Befunde,
        # unsichtbar. Dieselbe Bauart wie Befund 160, wo ``AUSSICHT`` die
        # meistzitierte vorausschauende Zahl des Projekts war und in keinem
        # Bericht stand.
        #
        # Der Unterschied zu GESCHLOSSEN ist der wichtigere von beiden: Wer
        # wissen will, was als naechstes zu tun ist, liest diese Liste und
        # nicht die der zugemachten Wege.
        if OFFEN:
            zeilen += [
                "",
                "GEMESSEN UND OFFEN (hier liegt die Arbeit)",
                "-" * 72,
            ]
            zeilen.extend(f"  {r}" for r in OFFEN)
        # **Getrennt, seit Befund 123.** Neun Werkzeugbefunde standen unter
        # den Suchrichtungen; wer die Liste las, fand zwischen "Mehr Maerkte"
        # auf einmal "README auf dem Stand vom 1. August". Beides Messungen
        # mit Fundstelle, aber zu verschiedenen Fragen - und nur die obere
        # sagt etwas ueber die Aussichten des Projekts.
        if BEHOBEN and not kurz:
            zeilen += [
                "",
                "BEHOBEN AN DEN WERKZEUGEN (sagt nichts ueber die Aussichten)",
                "-" * 72,
            ]
            zeilen.extend(f"  {r}" for r in BEHOBEN)
        zeilen += ["", "PUNKTE AUS DEM AUFTRAG", "-" * 72]
        zeilen.extend(f"  {p}" for p in AUFTRAG)
        if self.kerzenbestand:
            # **Gemessen, nicht gepflegt** (Befund 157). Der Punkt oben sagte
            # fuenf Befunde lang "Daten liegen hier vor", nachdem sie ein
            # Behaelterwechsel geloescht hatte. Diese Zeile kann das nicht.
            zeilen += ["", f"  Im Speicher: {self.kerzenbestand}"]
        offen = [p for p in AUFTRAG if not p.erledigt]
        zeilen.append(
            f"  -> {len(AUFTRAG) - len(offen)} von {len(AUFTRAG)} abgearbeitet."
            + (
                "  Wer einen davon erneut misst, zahlt Versuche fuer ein "
                "Ergebnis, das schon dasteht."
                if len(offen) < len(AUFTRAG)
                else ""
            )
        )
        zeilen += ["", "WAS NICHT BEI MIR LIEGT", "-" * 72]
        for e in ENTSCHEIDUNGEN:
            # **Die Fundstelle daneben** (Befund 305). Wer entscheidet, soll
            # nachschlagen koennen, worauf die Zahl steht - und sehen, ob sie
            # die neueste ist.
            zeilen += [f"  {e.frage}  ({e.stelle})", f"    {e.zahl}", f"    {e.warum}", ""]
        zeilen += ["NUR AUF DEINEM RECHNER", "-" * 72]
        for befehl, warum in BEIM_NUTZER:
            # ``replace`` und nicht ``format``: Die uebrigen Texte duerfen
            # geschweifte Klammern enthalten, ohne dass hier etwas bricht.
            text = warum.replace("{vergleich}", self._vergleichssatz())
            text = text.replace("{versuchskosten}", self._kostensatz())
            zeilen += [f"  {befehl}", f"    {text}"]
        return "\n".join(zeilen)

    def _kostensatz(self) -> str:
        """Was ein weiterer Kandidat kostet - **bevor** einer gesucht wird.

        Befund 196 hat gefunden, dass der Auftrag an die Research-KI die drei
        Kriterien nannte und verschwieg, wie es den sieben Vorgaengern ergangen
        ist. ``BEIM_NUTZER`` ist das **zweite** Artefakt, das kuenftige
        Versuche steuert, und es hatte dieselbe Luecke: Es sagt, wie man den
        Wettbewerb startet, und sagte nicht, dass jeder gepruefte Kandidat die
        Huerde fuer alle folgenden hebt - dauerhaft (Befund 198).

        Die Zahl wird **gerechnet**, nicht gepflegt. Vier Befunde dieses
        Projekts handeln von Zahlen, die an zwei Stellen standen und
        auseinanderliefen (158, 159, 165, 166).
        """
        return (
            f"**Jeder gepruefte Kandidat kostet einen Versuch, und der "
            f"Versuchsstand steht bei {self.versuche}.** Die Latte des "
            f"Deflated Sharpe waechst mit ihm, fuer alle folgenden und "
            f"dauerhaft. Gemessen (Befund 194): Das beste je gefundene Paar "
            f"haette bis zu einem Stand von 137 bestanden - vor der Auswahl "
            f"119 -, und sieben Partner, die alle Kriterien erfuellten, sind "
            f"draussen durchgefallen (Befund 186). Das ist kein Grund, es "
            f"nicht zu tun; es ist der Preis, der vorher dastehen sollte."
            f"\n    {BUDGET.zeile(self.versuche)} Seit Befund 216 haelt der "
            f"Wettbewerb diese Grenze auch ein: Er bricht dort ab und laeuft "
            f"nicht mehr bis Strg-C weiter. Wer darueber hinaus will, setzt "
            f"'--ueber-das-budget'."
        )

    def _vergleichssatz(self) -> str:
        """Der gemessene Vergleich beider Betriebspunkte, als ein Satz.

        Ohne Messung wird **kein Ersatz erfunden**, sondern auf die Stelle
        verwiesen, an der die Zahlen stehen. Eine Prosa-Naeherung waere genau
        die Kopie, die dieser Absatz abschafft.
        """
        z = self.zweitpunkt
        if z is None:
            return (
                "Wieviel das ausmacht, misst dieser Bericht weiter unten "
                "unter 'DIE BEIDEN BETRIEBSPUNKTE'."
            )
        from research.gates import GateThresholds

        satz = (
            f"Ohne Funding steht er bei {z.cagr_pct:.2f} % statt "
            f"{self.cagr_pct:.2f} % und besteht {z.bestanden} von {z.gesamt} "
            f"Gates statt {self.bestanden}."
        )
        if z.offen:
            luecke = GateThresholds().min_cagr_pct - z.cagr_pct
            # **Nicht die Messlatte** (Befund 267). Das Gate heisst so, aber
            # die Luecke wird hier gegen ``min_cagr_pct`` gerechnet - seine
            # zweite Bedingung. An der Messlatte selbst ist der Kandidat
            # nicht knapp, sondern beim Fuenffachen. Die Zahl war richtig und
            # ihr Name falsch; wer das las, suchte die Luecke an der falschen
            # Stelle.
            zusatz = (
                f" - beim Messlatten-Gate fehlen {luecke:.2f} Punkte "
                "Jahresrendite an der Betriebsschwelle, nicht an der "
                "Messlatte"
                if any("Messlatte" in g for g in z.offen)
                else ""
            )
            satz += f" Offen bleiben dort {', '.join(z.offen)}{zusatz}."
        return satz
