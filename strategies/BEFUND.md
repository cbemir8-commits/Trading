# Stand der Strategiesuche

Diese Datei haelt fest, was gemessen wurde und welche Wege damit
ausgeschlossen sind. Sie ist kein Champion - `champion.json` entsteht nur,
wenn alle elf Gates bestanden sind.

**Stand: 9 von 11. Nach 76 gepruefen Hypothesen.**

**Wichtige Einschraenkung, gemessen am 05.08.2026:** Diese 9 von 11 gelten
fuer den Zeitraum ab August 2017. Laesst man die ersten zweieinhalb Jahre
weg, sind es 8 von 11 und 7,4 % im Jahr statt 11,2 %. Siehe
"Wie viel haengt am Zeitraum" weiter unten.

## Der beste Kandidat

    Trend-Beteiligung 50 Tage auf BTC + ETH

    Einstieg   Kurs kreuzt den 50-Tage-Schnitt von unten
    Ausstieg   Kurs faellt unter den 50-Tage-Schnitt
    Stop       4 % vom Einstieg
    Groesse    Vola-Ziel 17,3 %, Konviktions-Bonus 1,0
    Konfluenz  SMA50 > SMA200, ROC(90) > 0, RSI(14) > 50

Gemessen ueber August 2018 bis Mai 2026, Walk-Forward, nach Gebuehren:

    Rendite        +136,1 %      (11,7 % im Jahr)
    Rueckgang         8,72 %
    Sharpe             1,51
    Trades              156      davon 39 Gewinner

## Was noch fehlt

| Gate | Wert | Schwelle |
|---|---|---|
| Messlatte | 11,7 % p.a. | 15 % p.a. |
| Deflated Sharpe | 0,865 | 0,95 |

Monte-Carlo besteht seit der Gewichtungskorrektur (siehe unten) mit 8,51 %
gegen 15 %.

Die Messlatte selbst wird **vierfach uebertroffen** (136 % gegen 34 %). Sie
scheitert an der zweiten Bedingung, der Mindestjahresrendite - einer
wirtschaftlichen Entscheidung, keiner statistischen.

## Vier Wege, die ausgemessen und ausgeschlossen sind

**1. Mehr Einsatz.** Es gibt keine Hoehe, die alle drei offenen Gates
zugleich erfuellt:

    Vola-Ziel   p.a.    Rueckgang   Monte-Carlo
       17,29   11,7 %      8,72 %       15,70 %
       22,00   14,4 %     11,83 %       20,83 %
       26,00   17,5 %     14,06 %       23,61 %
       30,00   20,2 %     16,09 %       27,60 %

Wer die Jahresrendite erreicht, reisst Rueckgang und Monte-Carlo.

**2. Teilgewinne mitnehmen.** Senkt die Schiefe (3,74 -> 3,09) und den
Monte-Carlo (15,70 -> 11,73), kostet aber die Haelfte der Rendite
(11,7 -> 5,7 % p.a.). Das Verhaeltnis wird schlechter, nicht besser.

**3. Short-Seite.** Verdoppelt die Trades (156 -> 307), verbessert Rendite
(13,0 % p.a.), Rueckgang (7,76 %) und Deflated Sharpe (0,904). Aber der
Monte-Carlo steigt auf 19,52 % - das Verhaeltnis verschlechtert sich von
1,34 auf 1,50.

**4. Schwache Setups herausfiltern.** Die Diagnose widerlegt die Idee. Nach
Zahl erfuellter Zusatzbedingungen:

    0/3    14 Trades   -0,076 R
    1/3    82 Trades   +1,055 R
    2/3    47 Trades   +0,840 R
    3/3    68 Trades   +2,497 R

Die Reihenfolge ist **nicht monoton** - 1/3 schlaegt 2/3. Das Signal ist
schwach, und die schwachen Setups wegzulassen wuerde +85 R Gewinn loeschen.
Ein Filter darauf waere Anpassung an Rauschen.

**5. Parameter-Streuung.** Dieselbe Regel mit 30, 50 und 80 Tagen
gleichzeitig zu je einem Drittel. Kein Effekt auf das Verhaeltnis - dafuer
hat der Versuch einen Fehler im Portfolio-Walk-Forward sichtbar gemacht
(siehe unten).

**6. Sperrfrist nach dem Ausstieg.** Die Vermutung war, dass Fehlausbrueche
in Seitwaertsphasen das schlechteste Jahr treiben und Abwarten hilft. Das
Gegenteil, bei Vola-Ziel 19,3:

    Sperre   Trades   p.a.     schl. Jahr   Deflated Sharpe
        0      156    13,10 %     -9,41 %        0,849
        3      144    11,33 %     -9,79 %        0,804
        5      131     9,50 %     -9,47 %        0,684
       10      106     5,56 %     -7,97 %        0,180

Alles wird schlechter, das schlechteste Jahr kaum besser. Die Trades direkt
nach einem Ausstieg sind nicht systematisch schlecht - wer wartet, verpasst
die Wiedereinstiege in weiterlaufende Trends.

## Ein Fehler in meinem eigenen Code - und was er verdeckt hat

Die vier obigen Messungen liefen alle mit einem Fehler im
Portfolio-Walk-Forward: Jedes Bein laeuft mit dem **vollen** Startkapital,
hat im Portfolio aber nur seinen Anteil. Die Trades trugen damit ein
Vielfaches ihres wirklichen Gewichts - bei zwei Beinen das Doppelte.

Die Kapitalkurve war richtig gewichtet, die Trades nicht. Und die
Monte-Carlo-Simulation liest die Trades. Sie meldete 15,70 % Rueckgang,
waehrend die Kurve aus denselben Fenstern 8,72 % zeigte.

Aufgefallen ist es erst bei einem Versuch mit sechs Beinen: Dort meldete sie
62 % - eine Zahl, die nicht sein kann. Nach der Korrektur:

    Monte-Carlo   15,70 %  ->  8,51 %      Gate besteht
    Stand         8 von 11  ->  9 von 11

**Die Korrektur macht ein Gate milder.** Die Probe dafuer, dass sie sauber
ist: Das R-Vielfache bleibt unveraendert, weil Gewinn und Menge mit
demselben Faktor skaliert werden und sich der Faktor herauskuerzt. Vier
Tests halten das fest.

## Die verbleibende Luecke

Mit korrigierter Gewichtung sind nur noch zwei Bedingungen im Konflikt:

    Jahresrendite >= 15 %      braucht Vola-Ziel >= 22,1
    Schlechtestes Jahr >= -10 %  erlaubt Vola-Ziel <= 20,5

Das sind **8 % Abstand** - vorher waren es 34 %. Gemessen:

    Vola-Ziel   p.a.    DD       Monte-Carlo   fehlt
       17,29   11,7 %   8,72 %       8,51 %    Messlatte, Deflated Sharpe
       23,00   15,6 %  11,95 %      11,51 %    Schlechtestes Jahr, DSR

Beide Male 9 von 11 - nur mit unterschiedlichen offenen Gates. Es haengt allein daran, wie
gleichmaessig die Ergebnisse ausfallen: Schiefe +3,7, Woelbung 17,4. Wenige
Riesengewinner tragen alles, und in einer unguenstigen Reihenfolge liegen
die vielen kleinen Verluste beieinander.

## Woran der Deflated Sharpe wirklich haengt

Bisher stand hier, gebraucht werde eine **gleichmaessigere** Ertragsquelle.
Das war falsch, und zwar nachrechenbar. Die Formel lautet

    Statistik = (SR - erwartetes Maximum) * sqrt(n-1) / sqrt(1 - Schiefe*SR + (Woelbung-1)/4 * SR^2)

Die Schiefe steht mit **negativem** Vorzeichen im Nenner. Positive Schiefe
macht den Nenner kleiner und den Wert damit **groesser**. Die hohe Schiefe der
Trendfolge ist also kein Nachteil, sondern hilft. Jede Zeile hier ist
gerechnet, alles andere unveraendert bei 156 Trades:

    Schiefe   0,0  ->  DSR 0,704
    Schiefe  +3,74 ->  DSR 0,848   (der Ist-Zustand)
    Schiefe  +6,0  ->  DSR 1,000

Was den Wert wirklich traegt, ist die **Zahl der Trades**:

    n=156   DSR 0,848
    n=180   DSR 0,922
    n=200   DSR 0,957   bestanden
    n=312   DSR 0,999

**Es fehlen rund 44 Trades**, nicht eine andere Art von Strategie. Damit ist
die Aufgabe erstmals scharf gestellt: 44 weitere Trades derselben Qualitaet,
oder ein Sharpe je Trade von 0,27 statt 0,242.

Der Preis jeder weiteren Hypothese bleibt:

    bei  76 Versuchen   DSR 0,841
    bei 120 Versuchen   DSR 0,765
    bei 400 Versuchen   DSR 0,519

## Drei Wege zu mehr Trades - alle gemessen, alle teurer als sie bringen

Der gemeinsame Befund: Mehr Trades sind zu haben, aber **nie zum gleichen
Preis je Trade**. Der Gewinn aus ``sqrt(n)`` wird jedes Mal vom Verlust an
Qualitaet ueberholt.

**7. Mehr Maerkte.** Dieselbe Regel zusaetzlich auf LTC und XRP, Tageskerzen,
gleiches Gewicht je Bein:

    Maerkte  Trades    p.a.       DD   Sharpe    DSR      Gates
       2       156   11,22 %   9,74 %   1,50    0,836     9/11
       3       265    8,93 %  11,15 %   1,22    0,890     7/11
       4       374    7,68 %  10,71 %   1,11    0,896     8/11

Der DSR steigt tatsaechlich - aber nur von 0,836 auf 0,896, weil die Erwartung
je Trade von 1,043 R auf 0,578 R faellt. LTC und XRP liefern einzeln Sharpe
0,42 und 0,38 bei 21 % Rueckgang. Die Jahresrendite verliert ein Drittel.

**8. Feinere Kerzen.** Dieselbe Regel, in Zeit konstant gehalten (50 Tage
bleiben 50 Tage, also 100 Kerzen auf 12 Stunden). Beide Laeufe ab 2020-03:

    Kerze   Trades    p.a.      DD    Sharpe   SR je Trade    DSR
    Tag       104    7,34 %   9,40 %   1,02       0,225      0,411
    12 h      138    6,57 %   8,84 %   0,92       0,176      0,299

Feiner **erzeugt** mehr Trades - ein Drittel mehr -, aber es sind schlechtere:
Rund um den Durchschnitt entstehen Fehlausbrueche, die die Tageskerze
verschluckt. Der DSR faellt, obwohl n steigt.

**9. Rueckkehr zum Mittelwert, 15 Minuten.** Bollinger-Unterband kreuzen,
raus ueber dem SMA20, Stop 1,5 %. 3796 Trades - und **kein Vorteil**:

    mit Gebuehren    Erwartung -0,0767 R    -32,98 % p.a.   Sharpe -4,01
    ohne Gebuehren   Erwartung -0,0132 R     -9,35 % p.a.   Sharpe -0,98

Auch ohne jede Gebuehr negativ. Die Idee scheitert nicht an den Kosten,
sondern hat gar keinen Rohvorteil. Der Grund, aus dem ich sie geprueft habe -
sie erzeuge die "richtige" negative Schiefe -, war ohnehin verkehrt herum
gedacht (siehe oben).

## Wie viel haengt am Zeitraum

Die wichtigste Zahl dieses Durchlaufs. Dieselbe Regel, dieselben zwei
Maerkte, nur ein spaeterer Start:

    Zeitraum              Trades    p.a.       DD     Sharpe    DSR     Gates
    2017-08 .. 2026-08      156   11,22 %   9,74 %    1,50    0,834     9/11
    2020-03 .. 2026-08      104    7,41 %   9,03 %    1,06    0,405     8/11

Ueber die letzten sechseinhalb Jahre allein waere der Kandidat **nicht** bei
9 von 11, sondern bei 8 - und die Jahresrendite laege bei 7,4 %, also weit
unter der Messlatte. Ein Drittel des Ergebnisses stammt aus 2017 bis 2020.

Das ist kein Fehler im Code, aber es ist eine Warnung: Die Kennzahlen oben
sind kein Naturgesetz, sie sind die Messung eines Zeitraums, der eine
Vervierzigfachung von BTC und den Absturz 2018 enthaelt.

Gegenprobe, dass es am Zeitraum liegt und nicht an den Daten: Dieselbe Regel
auf Tageskerzen, die aus Viertelstunden gebaut wurden, ergibt 7,42 % gegen
7,41 % auf den geholten Tageskerzen - identisch bis auf die zweite
Nachkommastelle.

## Was daraus folgt

Drei Quellen fuer mehr Trades sind gemessen und alle drei kosten mehr
Qualitaet, als sie an Zahl bringen. Was **nicht** geprueft ist:

* mehr Historie auf den guten Maerkten - BTC-Tageskerzen reichen bis 2012
  zurueck, genutzt wird erst ab 2017, weil ETH nicht frueher beginnt. Ein
  Portfolio, dessen Beine zu verschiedenen Zeiten dazukommen, waere zulaessig
  und wuerde rund 40 % mehr Historie auf dem besten Markt erschliessen.
* ein hoeherer Sharpe je Trade statt mehr Trades - 0,27 statt 0,242 wuerde
  reichen. Das ist eine Verbesserung von 12 %, nicht von 100 %.

Der zweite Weg ist der ehrlichere: Er verlangt eine bessere Regel, keinen
groesseren Datensatz.
