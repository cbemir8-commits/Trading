# Stand der Strategiesuche

Diese Datei haelt fest, was gemessen wurde und welche Wege damit
ausgeschlossen sind. Sie ist kein Champion - `champion.json` entsteht nur,
wenn alle elf Gates bestanden sind.

**Stand: 8 von 11. Nach 81 gepruefen Hypothesen.**

Bis zum 06.08.2026 stand hier 9 von 11. Der Rueckschritt kommt nicht von
einer neuen Hypothese, sondern davon, dass der Backtest jetzt die
**Verlustgrenzen des Betriebs** durchsetzt (siehe unten). Er war vorher zu
optimistisch; die Zahl ist gefallen, weil die Messung ehrlicher wurde.

**Wichtige Einschraenkung, gemessen am 05.08.2026:** Diese Zahlen gelten
fuer den Zeitraum ab August 2017. Laesst man die ersten zweieinhalb Jahre
weg, faellt die Jahresrendite von 11,2 % auf 7,4 %. Siehe
"Wie viel haengt am Zeitraum" weiter unten.

## Drei Fehler, die den Backtest wertlos gemacht haetten

Gefunden am 05.08.2026, nachdem ich Backtest und Livebetrieb zum ersten Mal
**nebeneinandergelegt** habe (``backtest/replay.py``, ``cli abgleich``).
Beide waren im Backtest unsichtbar, weil der Backtest richtig rechnet - der
Betrieb rechnete anders.

**1. Die Positionsgroesse war im Betrieb rund zehnmal zu gross.**

Der Livebetrieb holte den Kapitalanteil ueber ``equity_fraction``. Das ist
bei Vola-Ziel-Genomen aber nicht der zu handelnde Anteil, sondern die
**Obergrenze** (``sizing.fraction`` = 3,0). Gemessen ueber 5301
BTC-Tageskerzen:

    Backtest, Median      0,264 vom Kapital
    Backtest, Hoechstwert 1,595
    Livebetrieb           3,0    - immer, auf jedem Balken

Die Obergrenze wird im Backtest **kein einziges Mal** erreicht. Bei 4 % Stop
und dreifachem Kapital genuegen wenige Prozent Gegenbewegung fuer den
15-%-Not-Aus; das Demokonto waere in Tagen erledigt gewesen, und die
Vola-Steuerung - der ganze Sinn des Betriebspunkts - war im Betrieb
wirkungslos.

**2. Die Sperrfrist lief im Betrieb nie ab.**

Sie rechnete mit dem Index im aktuellen Rahmen. Im Backtest waechst der von
0 bis ans Ende; im Betrieb sieht die Strategie nur die letzten 2000 Kerzen,
und sobald der Puffer voll ist, steht der Index fest. Ab dem ersten Trade
galt dort immer "null Kerzen vergangen". Gemessen mit Sperrfrist 5:

    Backtest      113 Signale
    Livebetrieb     4 Signale

Der Roboter haette nach seinem ersten Trade praktisch aufgehoert zu handeln.
Der Spitzenkandidat handelt ohne Sperrfrist und war nicht betroffen - das ist
Glueck, kein Verdienst.

**3. Die Ausstiegsbedingung wurde im Betrieb nie ausgewertet.**

Die Engine schliesst 38,5 % aller Trades ueber ``should_exit`` - "raus, wenn
der Kurs unter den Schnitt faellt". Im Livebetrieb kam dieser Aufruf
ueberhaupt nicht vor. Jede Position waere bis zum Stop oder ins Ziel gelaufen,
und aus "dem Trend folgen, raus wenn er bricht" wuerde "wetten und den Stop
abwarten". Derselbe Kandidat, einmal mit und einmal ohne:

                          Trades    p.a.      DD     Sharpe    DSR
    mit Ausstieg             156   11,22 %   9,74 %   1,50    0,820
    ohne (der Betrieb)       124    8,96 %  10,33 %   1,32    0,712

Der Anteil der Trades, die am Stop enden, steigt von 42,9 % auf 72,6 %.

**Warum das nicht durch Zuschauen aufgefallen waere.** Genau darauf hatte der
Abschnitt "Was Demo-Handel beweisen kann" schon hingewiesen: Bei 17 Trades im
Jahr bliebe selbst ein vollstaendiger Verlust des Vorteils drei Jahre lang
unentdeckt. Ein Zehnfaches an Positionsgroesse haette sich als
"aussergewoehnlich schlechte Phase" getarnt, nicht als Fehler - und ein
Fuenftel weniger Rendite erst recht.

Alle drei sind behoben, mit Tests, die sie beim Zurueckbauen wieder fangen
(gegengeprueft: 2 bzw. 4 Tests fallen um).

**Was ich daraus fuer das Werkzeug gelernt habe.** Der erste Abgleich verglich
nur das **Einstiegssignal**. Von den drei Fehlern haette er damit nur einen
gefunden - die beiden anderen fielen bei der Handpruefung auf, und darauf ist
kein Verlass. ``cli abgleich`` vergleicht jetzt die ganze
Entscheidungsflaeche: Signal, Ausstiegsbedingung und Kapitalanteil, auf jedem
Balken.

Beim Umbau meldete er prompt eine vierte Abweichung - die dann in ihm selbst
sass: Er begann einen Balken spaeter als die Engine
(``i <= warmup_bars`` statt ``i < max(warmup_bars, 1)``). Ein Pruefwerkzeug,
das die Grenze anders zieht als das Gepruefte, findet Fehler, die keine sind,
und verdeckt die echten dahinter. Auch das ist behoben.

**Was der Abgleich nicht prueft:** die Ausfuehrung selbst - Fills, Stops an
der Boerse, Neustart mitten in einer Position. Dafuer gibt es die Testsuite
und den Demobetrieb.

## Der vierte Befund: Der Backtest kannte die Verlustgrenzen nicht

Anders als die drei vorigen war das kein Codefehler, sondern eine **fehlende
Modellierung**. Im Betrieb sperrt der Risk-Officer

    nach  3 % Tagesverlust    fuer 24 Stunden
    nach  7 % Wochenverlust   bis zur manuellen Freigabe
    bei  15 % Rueckgang       Not-Aus, alles glatt

Die Engine kannte keine dieser Grenzen - der Name ``RiskOfficer`` kam in
``backtest/engine.py`` kein einziges Mal vor. Sie mass damit eine Strategie,
die es so nicht geben kann.

Gemessen, je Testfenster einzeln gerechnet:

    schlimmster Tag                     -3,25 %
    Fenster mit einem Tag unter -3 %     1 von 31
    Wochenlimit ausgeloest in            3 Fenstern
    Not-Aus ausgeloest                   nie

**Auf den Spitzenkandidaten selbst wirkt sich das nicht aus.** Keines seiner
156 Signale fiel in eine Sperrzeit; Rendite, Rueckgang und Sharpe sind auf
zwei Nachkommastellen dieselben. Was sich aendert, ist das Gate
**Parameter-Plateau**: Ein Nachbarparameter, der ohne Grenzen profitabel war,
ist es mit ihnen nicht mehr. Damit steht der Kandidat bei

    ohne Grenzen   9 von 11    Messlatte, Deflated Sharpe offen
    mit Grenzen    8 von 11    zusaetzlich Parameter-Plateau

Das Gate misst, ob die Strategie auf einem Plateau steht oder auf einer
Kante. Mit den Grenzen zeigt sich: auf einer schmaleren Kante als gedacht.
Das ist ein echter Befund und kein Messfehler - die Nachbarn muessen die
Grenzen ebenso einhalten wie der Kandidat.

**Ein Fehler in meiner eigenen Messung, bevor ich sie richtig gemacht habe.**
Zuerst hatte ich den schlimmsten Tag mit **-17,98 %** gemessen und daraus
geschlossen, der Not-Aus haette allein davon ausgeloest. Das war falsch: Ich
hatte die 31 Fensterkurven aneinandergehaengt, und jede beginnt wieder bei
500. Der Sprung am Fensterwechsel sah wie ein Tagesverlust aus. Je Fenster
einzeln gerechnet sind es -3,25 %.

**Wie es gebaut ist.** Die Engine benutzt den **echten** ``RiskOfficer``, nicht
eine Nachbildung seiner Regeln - genau aus dieser Doppelung sind die drei
vorigen Abweichungen entstanden. Dafuer wurde die Zustandspruefung aus
``evaluate`` in eine eigene Methode ``blockade()`` gezogen, die beide
aufrufen: der Betrieb und der Backtest. Eine Umsetzung, zwei Aufrufer.

Die Uhr des Officers zeigt dabei auf die verarbeitete Kerze. Zeigte sie auf
die Wirklichkeit, laegen alle 2830 Kerzen an einem Tag und die Tagesgrenze
griffe nie.

## Der beste Kandidat

    Trend-Beteiligung 50 Tage auf BTC + ETH

    Einstieg   Kurs kreuzt den 50-Tage-Schnitt von unten
    Ausstieg   Kurs faellt unter den 50-Tage-Schnitt
    Stop       4 % vom Einstieg
    Groesse    Vola-Ziel 19,3 %, Konviktions-Bonus 1,0
    Konfluenz  SMA50 > SMA200, ROC(90) > 0, RSI(14) > 50

Gemessen ueber August 2017 bis August 2026, Walk-Forward, nach Gebuehren.
Alle Zahlen in diesem Dokument stammen aus dem Lauf vom 05.08.2026, damit
nicht zwei Staende nebeneinander stehen:

    Rendite        +159,5 %      (11,22 % im Jahr)
    Rueckgang         9,74 %
    Sharpe             1,50
    Trades              156      Erwartung +1,043 R je Trade

## Was noch fehlt

| Gate | Wert | Schwelle |
|---|---|---|
| Messlatte | 11,22 % p.a. | 15 % p.a. |
| Deflated Sharpe | 0,820 | 0,95 |
| Parameter-Plateau | 0,500 | 0,600 |

Das Parameter-Plateau ist seit dem 06.08.2026 offen - nicht weil sich die
Strategie geaendert haette, sondern weil der Backtest jetzt die
Verlustgrenzen des Betriebs durchsetzt.

Monte-Carlo besteht seit der Gewichtungskorrektur (siehe unten) mit 9,72 %
gegen 15 %.

Die Messlatte selbst wird **vierfach uebertroffen** (159 % gegen 34 %). Sie
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

    bei  81 Versuchen   DSR 0,835
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

## Haelt der Vorteil ueber vierzehn Jahre?

Ja. Das ist der belastbarste Befund im ganzen Dokument. BTC allein,
dieselbe Regel, zehn verschiedene Startpunkte:

    ab        Jahre  Trades    p.a.       DD    R je Trade   SR je Trade
    2012       14,6    121    8,60 %   14,68 %     0,729        0,215
    2014       12,6    104    8,83 %   14,68 %     0,718        0,214
    2016       10,6     87    8,38 %   13,04 %     0,775        0,212
    2018        8,6     73   10,52 %   13,04 %     0,826        0,239
    2020        6,3     56    6,29 %   13,23 %     0,464        0,196
    2021        5,6     49    7,00 %    7,87 %     0,499        0,215

Der Sharpe je Trade liegt in **jedem** Fenster zwischen 0,196 und 0,242. Der
Vorteil ist nicht in 2017 entstanden und 2021 verschwunden - er ist ueber
vierzehn Jahre da, in derselben Groesse. Was schwankt, ist nur, wie stark
sich das im Jahresergebnis niederschlaegt.

Damit ist auch klar, warum die Zahlen weiter oben am Zeitraum haengen: nicht
weil der Vorteil kaeme und ginge, sondern weil sich in guten Jahren mehr
daraus machen laesst.

Und es zeigt die eigentliche Grenze: **Vierzehn Jahre BTC ergeben 121
Trades.** Die Regel feuert rund achtmal im Jahr. Es gibt keinen Datensatz,
der daraus 200 Trades macht.

## Zehn. Der Stop als Massstab statt als Notbremse

Die letzte Idee mit Aussicht: Wenn nicht mehr Trades, dann bessere. Noetig
waren 0,27 statt 0,242 Sharpe je Trade - 12 %, keine Verdopplung. Der feste
4-%-Stop misst das Risiko in ruhigen und wilden Phasen verschieden; ein Stop
in ATR haette ueberall dieselbe Bedeutung.

    Stop               Trades    p.a.       DD     R je Trade  SR je Trade    DSR
    4 % fest             156   11,22 %    9,74 %     1,043       0,242      0,830
    2,0 x ATR(14)        154   10,23 %   11,93 %     0,548       0,228      0,717
    3,0 x ATR(14)        145   10,44 %   13,31 %     0,398       0,239      0,744
    4,0 x ATR(14)        125    9,19 %   10,89 %     0,309       0,237      0,606
    5,0 x ATR(20)         86    9,12 %    8,07 %     0,320       0,293      0,642

Widerlegt - aber die letzte Zeile erklaert, **warum** alles bisher
Gemessene scheitert. Der weite ATR-Stop erreicht tatsaechlich 0,293 Sharpe je
Trade, mehr als die noetigen 0,27. Nur bleiben davon 86 Trades uebrig statt
156, und der Deflated Sharpe faellt trotzdem.

Der Deflated Sharpe haengt naeherungsweise am **Produkt** aus beidem:

    4 % fest         0,242 x sqrt(155) = 3,01
    2,0 x ATR(14)    0,228 x sqrt(153) = 2,82
    5,0 x ATR(20)    0,293 x sqrt( 85) = 2,70

Der bisherige Kandidat steht auf dem hoechsten Wert. Jede Richtung, in die
gemessen wurde - mehr Maerkte, feinere Kerzen, engere oder weitere Stops,
mehr Historie -, senkt das Produkt. Qualitaet je Trade und Zahl der Trades
gehen gegeneinander, und zwar staerker als sqrt.

## Was daraus folgt

**Diese Regel ist ausgemessen.** Zehn Richtungen, alle gemessen, keine
naeher am Ziel. Der Kandidat sitzt auf einem lokalen Hoechstwert, und die
Luecke im Deflated Sharpe - 0,83 gegen 0,95 - ist durch Nachstellen an
dieser Regel nicht zu schliessen.

Was der Deflated Sharpe eigentlich verlangt, in Worten: "Sei dir nach 81
Versuchen zu 95 % sicher, dass das kein Zufall war." Fuer eine Regel mit
17 Trades im Jahr braucht das rund zwoelf Jahre auf zwei Maerkten. Es gibt
neun.

Der Vorteil ist also wahrscheinlich echt - vierzehn Jahre stabiler Sharpe je
Trade sind ein starkes Argument -, nur ist er zu **selten**, um ihn auf
diesem Niveau zu beweisen. Das ist etwas anderes als "funktioniert nicht",
und die Unterscheidung gehoert dem Nutzer gesagt, nicht weggerundet.

Drei Wege, und nur zwei davon sind ehrlich:

1. **Weitersuchen** nach einer Ertragsquelle mit mehr Gelegenheiten. Kostet
   Versuche, und jeder hebt die Huerde weiter.
2. **Demo handeln.** Die Gates schuetzen echtes Geld. Ein Demokonto kostet
   keines, und jeder Trade dort ist echte Evidenz ausserhalb der Stichprobe.
   Was das wirklich leistet, steht im naechsten Abschnitt - deutlich weniger,
   als ich zunaechst behauptet hatte.
3. Die Schwelle senken. **Kommt nicht in Frage** - dann misst das ganze
   System nur noch sich selbst.

## Was Demo-Handel beweisen kann - und was nicht

Ich hatte den Demobetrieb als "den einzigen Weg, n zu erhoehen, ohne
Qualitaet einzutauschen" bezeichnet. Das stimmt, taugt aber viel weniger als
es klingt. Ausgerechnet, nicht geschaetzt (``cli evidenz``):

    Zeitraum        Trades    Was unentdeckt bliebe
    ein Monat          1,4    alles
    ein Quartal        4,3    alles
    ein Jahr          17,4    alles
    drei Jahre        52,1    alles
    zehn Jahre       173,8    77 % des Vorteils

"alles" heisst: Selbst wenn der Vorteil vollstaendig verschwunden waere,
wuerde man es an so wenigen Trades nicht bemerken.

Die beiden Zahlen, um die es geht:

    Damit der Deflated Sharpe reicht         70 Trades  =  4 Jahre
    Damit eine Halbierung auffiele          417 Trades  = 24 Jahre
    Damit ein Viertel weniger auffiele     1704 Trades  = 98 Jahre

Das ist der unangenehme Kern: Der Demobetrieb wuerde die Huerde in vier
Jahren **rechnerisch** nehmen, ohne in derselben Zeit ausschliessen zu
koennen, dass die Strategie inzwischen die Haelfte ihres Vorteils verloren
hat. Beides zugleich geht bei 17 Trades im Jahr nicht.

### Der Fehler, der dabei fast passiert waere

Die erste Fassung von ``research/live_evidenz.py`` pruefte, ob der
Livebetrieb **signifikant** schlechter laeuft, und rechnete sonst zusammen.
Gemessen an der echten Verteilung, mit 40 Live-Trades:

    Live-Ergebnis      Deflated Sharpe naiv    Drift erkannt?
    unveraendert            0,824 -> 0,937          -
    33 % schlechter         0,824 -> 0,931         nein
    71 % schlechter         0,824 -> 0,896         nein
   100 % schlechter         0,824 -> 0,820          ja

Ein Livebetrieb, der **zwei Drittel** des Vorteils verliert, haette den Wert
also gehoben - weil sqrt(n) schneller waechst, als der Mittelwert faellt -
und der Test haette geschwiegen. Nicht weil alles in Ordnung war, sondern
weil er bei 40 Beobachtungen dieser Verteilung fast nichts sehen kann.

Die Beweislast stand verkehrt herum. Jetzt steht dort eine zweite
Bedingung: **Waere die Verschlechterung ueberhaupt aufgefallen?** Ist der
blinde Fleck groesser als ein Viertel des Vorteils, wird nicht
zusammengerechnet - egal wie unauffaellig der Test ausfaellt.

Nicht "ich habe nichts Schlimmes gefunden", sondern "ich haette es
gefunden, wenn es da waere".

### Was daraus fuer den Plan folgt

Die 30 Tage Demo bleiben richtig und noetig - sie pruefen, ob Orders
ankommen, ob der Stop an der Position haengt, ob der Not-Aus wirkt, ob der
Prozess einen Neustart mitten in einer Position uebersteht. Das sind
Ja-Nein-Fragen, und die beantwortet ein Monat.

Sie beantworten nur nicht die Frage, ob der Vorteil echt ist. Wer nach 30
Tagen Demo echtes Geld einsetzt, tut das auf Grundlage des **Backtests** -
der Demobetrieb hat daran nichts hinzugefuegt. Das ist vertretbar, solange
man es weiss.
