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
        "Quartal ist ein echtes Minimum - Halbjahr 0,921, Jahr 1,000; "
        "'am_rand' stellt die Frage jetzt von selbst",
        143,
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
        "Zensur (Befund 152) steht der Punkt bei 0,5881",
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
    Richtung(
        "Timing gegen Zufallseinstiege",
        "4 von 4 Maerkten ueber ihrer Null, aber nur ETH raeumt |z| = 2 - "
        "und die Ziehung hat keine Stops, also eine Obergrenze",
        175,
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
        "von 3,78 auf 5,72 Reststreuungen (179). Beide Tore sind dasselbe",
        178,
        179,
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
        "Punkt (ohne ihn t = -0,98)",
        179,
        183,
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
        "er mit 0,2137 je Trade schlechter als der Bestand und braeuchte 324",
        56,
        178,
    ),
    # Auf Tageskerzen beantwortet (Kippfaktor 56, Befund 187). Der
    # Kostenanteil lag dort bei hoechstens 0,0086 der Trade-Streuung - auf
    # Viertelstunden ist er das nicht mehr, und ein Urteil von einem
    # Betriebspunkt gilt am anderen nicht.
    # **Nicht zu schliessen, in keine Richtung.** Entscheiden liesse es sich
    # nur mit einer Messung der Slippage, und die steckt im
    # Ausfuehrungspreis - aus den Trades ist sie nicht zu trennen.
    Richtung(
        "Traegt die Reibung die Kopplung auf kurzen Kerzen?",
        "auf Tageskerzen nein (Kostenanteil 0,0013 bis 0,0086, Kippfaktor "
        "56). Auf Viertelstunden offen: Kostenanteil 0,0094 bis 0,1250 und "
        "Kippfaktor 2 - das schafft die Slippage allein",
        78,
        190,
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
    """
    if not 1 <= n <= 199:
        # Ueber 199 gaebe es "Zweihundert" und Aehnliches. Dieselbe Regel wie
        # vorher: erst bauen, wenn es soweit ist. Ein leerer String findet
        # keine Ueberschrift, und der Test schlaegt an.
        return ""
    if n >= 100:
        rest = zahlwort(n - 100)
        return f"Hundert{rest.lower()}" if rest else "Hundert"
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
    sondern schaedlich: Jeder Versuch hebt die Huerde des Deflated Sharpe um
    0,00021 fuer alle kuenftigen. Wer weitersucht, macht das Ziel schwerer,
    das er sucht.

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
    """Ein offener Punkt, der nicht bei mir liegt."""

    frage: str
    zahl: str
    warum: str


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
    ),
    Entscheidung(
        frage="Mindestrendite von 15 % im Jahr",
        zahl="Gemessen ueber zehn Stellungen des Groessenreglers: **keine** "
             "haelt beide Schwellen. Bei 20,5 bleibt der Rueckgang mit "
             "11,29 % unter der Grenze, die Rendite steht bei 14,11 % - es "
             "fehlen 0,89 Punkte. Eine Stufe weiter (21,0) reisst der "
             "Rueckgang mit 12,50 %, und die Rendite fehlt immer noch.",
        warum="Eine wirtschaftliche Schwelle, kein statistisches Kriterium - "
              "so steht es seit jeher in gates.py. Dass sie mit der "
              "Rueckgangsgrenze im Konflikt steht, war lange eine Behauptung "
              "und ist seit Befund 57 beziffert: `cli vereinbar` rechnet es "
              "jederzeit nach. Die Aufloesung ist eine Geschaeftsentscheidung "
              "- den Kandidaten dorthin zu stellen, wo mehr Gates bestehen, "
              "ist ausdruecklich keine.",
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
    ),
    Entscheidung(
        frage="Funding-Satz",
        zahl="Nie gemessen. `data_store/funding/` ist leer, und der Backtest "
             "setzt den Bybit-Basiswert von 0,01 % je Achtstundenperiode ein "
             "- rund 11 % im Jahr. Am Betriebspunkt sind das 63,79 Euro gegen "
             "7,17 Euro Handelsgebuehren, also das **8,9-fache**, und 8,2 % "
             "des Bruttogewinns. Die Bilanz reicht ueber die gemessene Leiter "
             "von 9 von 11 (bei 0 %) bis 3 von 11 (bei 55 %); bei 11 % steht "
             "sie auf 7. `cli finanzierung` rechnet es nach.",
        warum="Der groesste Kostenblock des Systems steht auf einem "
              "Vorgabewert. Zwei Gates kippen zwischen 5,5 % und 11 % - "
              "Schlechtestes Jahr und Parameter-Plateau. Und der Vorgabewert "
              "ist der **Basiswert**, nicht der Durchschnitt: Der Bestand ist "
              "eine Long-Trendfolge und im Markt, wenn der Trend steigt, also "
              "wenn Longs am meisten zahlen. Liegt die wahre Rate darueber, "
              "steht der Kandidat schlechter da als gemeldet. Echte Raten "
              "gibt es nur von Bybit, und die sind aus dem "
              "Entwicklungscontainer nicht erreichbar - das ist eine Sperre "
              "dieser Sandbox, keine des Systems. Auf dem eigenen Rechner: "
              "`python -m cli funding --von 2020-03-30`, sofern das Konto "
              "Perpetuals fuehrt.",
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
    ),
    Entscheidung(
        frage="Wochenverlustgrenze",
        zahl="Bei -7 % pausiert das System bis zur **manuellen** Freigabe.",
        warum="Richtig so gebaut, aber es wird im Betrieb Telegram-Meldungen "
              "geben, nach denen das System steht, bis jemand es freigibt. "
              "Ob das so bleiben soll, ist eine Betriebsentscheidung.",
    ),
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
    """

    frage: str
    stand: str
    befund: int = 0
    erledigt: bool = True

    def __post_init__(self) -> None:
        if self.erledigt and self.befund <= 0:
            raise ValueError(
                f"'{self.frage}' gilt als erledigt, hat aber keine Fundstelle "
                f"im BEFUND - das waere eine Behauptung."
            )

    def __str__(self) -> str:
        marke = f"Nr. {self.befund}" if self.befund else "offen"
        return f"{'OK' if self.erledigt else '--'} {self.frage:34} {self.stand}  ({marke})"


#: Die Punkte aus dem Auftrag, mit ihrem gemessenen Stand.
AUFTRAG: tuple[Auftragspunkt, ...] = (
    Auftragspunkt(
        frage="P7: News- und Termin-Overlay",
        stand="beides gebaut und gemessen; die Wirkung ist nicht belegt",
        befund=59,
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
              "Kriterien erfuellt haben und draussen durchgefallen sind",
        befund=196,
    ),
    Auftragspunkt(
        frage="Generation 6/7 auf 15-Minuten",
        stand="alle 14 gemessen: 1 von 9 Gates, -9 bis -44 % p.a.",
        befund=29,
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
        frage="backfill 15m + wettbewerb beim Nutzer",
        stand="15-Minuten-Forschungskerzen wieder da (225.000 je Markt, "
              "Bitstamp) und der Katalog darauf gemessen: 34 von 36 Regeln "
              "negativ, beste Guete 0,744 gegen 3,964. Fuer die Zulassung "
              "braucht es Bybit-Kerzen - und die nur beim Nutzer",
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
        "python -m cli abgleich",
        "Erzeugt der Livebetrieb dieselben Signale wie der Backtest? Vor "
        "jedem Livegang auszufuehren.",
    ),
    (
        "python -m cli backfill --von 2017-08-16",
        "Laedt Bybit-Kerzen. **Ohne sie kann nichts zugelassen werden** - "
        "jede Zahl dieses Projekts steht auf Bitstamp-Kassakursen, und die "
        "sind nicht das gehandelte Instrument. Seit Befund 102 sagt das "
        "System das auch: Ein Bericht auf Forschungskerzen gilt nie als "
        "zugelassen, egal wie viele Gates halten.",
    ),
    (
        "python -m cli wettbewerb",
        "Sucht auf den geladenen Kerzen einen Kandidaten. Bis Befund 167 "
        "stand dieser Schritt als ', dann wettbewerb' hinter dem Backfill in "
        "derselben Zeile - keine Befehlszeile, sondern Prosa: Wer sie "
        "kopierte, bekam 'Got unexpected extra argument(s)'. Er legt auch "
        "'state/leaderboard.json' neu an, die in diesem Behaelter fehlt "
        "(Befund 166).",
    ),
    (
        "python -m cli funding --von 2020-03-30",
        "Laedt die echten Funding-Raten. Bisher rechnet jede Zahl mit dem "
        "Vorgabewert, und der ist der groesste Kostenblock des Systems - das "
        "8,9-fache der Handelsgebuehren (Befund 100).",
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
            "  Gemessen wurde das in Befund 168, eingeschraenkt in 169 und",
            "  auf Viertelstunden geprueft in 171. **Das Ergebnis war nicht",
            "  beruhigend.** Nachrechnen mit `cli vorratsdecke`.",
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
        from research.referenz import AUSSICHT, AUSSICHT_VERBUND

        if self.zugelassen:
            return []
        zeilen = [
            "",
            "WIE WEIT ES NOCH IST",
            "-" * 72,
            f"  Bestand allein   {AUSSICHT.als_zeile()}",
            f"  bester Verbund   {AUSSICHT_VERBUND.als_zeile()}",
            "",
            "  Untergrenzen, keine Termine - die Sammelrate ist die des",
            "  laengsten gemessenen Fensters (siehe research/referenz.py).",
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

    def bericht(self) -> str:
        zeilen = [
            "STAND",
            "=" * 72,
            f"  Kandidat   {self.kandidat}",
            f"  Gemessen   {self.maerkte}",
            f"  Ergebnis   {self.trades} Trades{self._zensurhinweis()}, "
            f"{self.cagr_pct:.2f} % p.a., {self.rueckgang_pct:.2f} % Rueckgang",
            f"  Gates      {self.bestanden} von {self.gesamt}",
            f"  Versuche   {self.versuche}",
            f"  Suchbudget {BUDGET.zeile(self.versuche)}",
            "",
            self.urteil(),
            *self._aussichtszeilen(),
            *self._zweiter_weg(),
            "",
            "GEMESSEN UND GESCHLOSSEN",
            "-" * 72,
        ]
        zeilen.extend(f"  {r}" for r in GESCHLOSSEN)
        # **Getrennt, seit Befund 123.** Neun Werkzeugbefunde standen unter
        # den Suchrichtungen; wer die Liste las, fand zwischen "Mehr Maerkte"
        # auf einmal "README auf dem Stand vom 1. August". Beides Messungen
        # mit Fundstelle, aber zu verschiedenen Fragen - und nur die obere
        # sagt etwas ueber die Aussichten des Projekts.
        if BEHOBEN:
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
            zeilen += [f"  {e.frage}", f"    {e.zahl}", f"    {e.warum}", ""]
        zeilen += ["NUR AUF DEINEM RECHNER", "-" * 72]
        for befehl, warum in BEIM_NUTZER:
            # ``replace`` und nicht ``format``: Die uebrigen Texte duerfen
            # geschweifte Klammern enthalten, ohne dass hier etwas bricht.
            text = warum.replace("{vergleich}", self._vergleichssatz())
            zeilen += [f"  {befehl}", f"    {text}"]
        return "\n".join(zeilen)

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
            zusatz = (
                f" - die Messlatte um {luecke:.2f} Punkte"
                if any("Messlatte" in g for g in z.offen)
                else ""
            )
            satz += f" Offen bleiben dort {', '.join(z.offen)}{zusatz}."
        return satz
