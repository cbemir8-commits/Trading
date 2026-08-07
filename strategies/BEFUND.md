# Stand der Strategiesuche

Diese Datei haelt fest, was gemessen wurde und welche Wege damit
ausgeschlossen sind. Sie ist kein Champion - `champion.json` entsteht nur,
wenn alle elf Gates bestanden sind.

**Stand: 8 von 11. Nach 93 gepruefen Hypothesen.**

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
und den Demobetrieb. Was dort noch lag, steht im achten Befund.

## Der achte Befund: Was eine Teilfuellung anrichtet

Der erste Fehler in der **Ausfuehrung**. Bei PostOnly-Limits sind
Teilfuellungen der **Normalfall**, nicht die Ausnahme - die Order liegt am
Rand des Buchs und wird abgearbeitet, soweit Gegenseite da ist.

**Zuerst eine Korrektur an meiner eigenen Darstellung.** Hier stand, die
halbe Position habe "ohne jede Absicherung" gelaufen. Das war fuer
Perpetuals **falsch**, und ich hatte es nicht geprueft, bevor ich es
aufschrieb: Bei Perpetuals haengt der Stop an der **Position**, nicht an
einer Menge (``set_position_stop``). Waechst die Position, waechst die
Deckung mit. Nachgemessen, je Marktart:

    PERPETUAL   Stop deckt die ganze Position - aber der Verlust am Stop
                waere **doppelt so hoch** wie geplant
    SPOT        Kein Positions-Stop moeglich; dort waere tatsaechlich die
                halbe Position ungeschuetzt gewesen

Gehandelt werden Perpetuals. Der Schaden war also nicht "ohne Stop", sondern
**doppeltes Risiko je Trade** - ernst genug, aber etwas anderes. Ich hatte
aus dem Testergebnis "Stop deckt 0,003" geschlossen, ohne nachzusehen, was
``set_position_stop`` bei Bybit bedeutet.

Der Ablauf, unveraendert richtig:

    Order platziert             0,006
    halb gefuellt, abgesichert  0,003    Risiko wie geplant
    Rest doch noch gefuellt     0,006    Risiko doppelt so hoch

**Und ein Folgefehler direkt dahinter.** Beim Bauen des Netzes dagegen fiel
auf, dass der Notausstieg die Lage nicht rettet: ``emergency_close`` schloss
``bracket.remaining_qty`` - also die **vermerkte** Menge, nicht die
tatsaechliche. Bei einer auf 0,012 gewachsenen Position schloss er 0,006 und
meldete Vollzug. Genau im einzigen Fall, in dem beide Zahlen auseinander-
laufen, tat der Notausstieg das Falsche.

Behoben in zwei Schichten, weil eine hier nicht reicht:

1. ``OrderRouter.protect`` nimmt den Rest der Einstiegsorder aus dem Markt,
   **bevor** der Stop gesetzt wird. Danach waere er schon zu klein.
2. ``LiveTrader._manage_open_position`` schliesst sofort, wenn die Position
   trotzdem groesser ist als abgesichert - mit der tatsaechlichen Menge.

Schicht 2 ist noetig, weil Schritt 1 fehlschlagen kann und der Ausfall
lautlos waere. Gegenprobe: Baut man beide Korrekturen zurueck, fallen zwei
der fuenf neuen Tests um.

**Warum das keiner der bisherigen Pruefungen aufgefallen ist.** ``cli
abgleich`` vergleicht Entscheidungen - Signal, Ausstieg, Kapitalanteil - und
ist damit blind fuer alles, was zwischen Entscheidung und Position passiert.
Der Backtest kennt keine Teilfuellungen: Dort fuellt eine Order ganz oder gar
nicht. Und im Demobetrieb waere es als "unerklaerlicher Verlust" erschienen,
nicht als Fehler.

## Der neunte Befund: Die Take-Profits waren doppelt so gross wie die Position

Beim Nachpruefen des achten Befunds gefunden - und dieser wirkt auch bei
Perpetuals, wo der Positions-Stop den anderen Fehler abgemildert hat.

Die Zielmengen stammen aus ``sized.take_profit_legs``, berechnet aus der
**bestellten** Groesse. Nach einer halben Fuellung standen dort Ziele ueber
0,006 bei einer Position von 0,003:

    Position                     0,003
    Ziel 1  0,003 @ 100395,5
    Ziel 2  0,001 @ 100992,5
    Ziel 3  0,002 @ 101888,0
    Summe                        0,006    - doppelte Ueberdeckung

Reduce-Only faengt den unmittelbaren Schaden ab: Eine ueberzaehlige Order
kann keine Gegenposition eroeffnen. Der Schaden kommt spaeter - die Orders
bleiben nach dem Schliessen im Buch liegen und wuerden den **naechsten**
Trade sofort anschneiden.

Behoben mit zwei Griffen, und die Unterscheidung ist wichtiger, als sie
aussieht:

* **Deckelung** auf die verbleibende Menge. Sie verhindert die
  Ueberdeckung - das ist die Sicherheitsgrenze.
* **Skalierung** mit dem Fuellungsanteil. Sie erhaelt die **Staffelung**.

Beim Testen fiel auf, dass die Deckelung allein schon "sicher" aussieht: Die
Summe stimmt dann. Aber das erste Bein verschluckt die ganze Position, aus
drei Zielen wird eines, und die gestaffelte Mitnahme faellt aus. Gemessen:

    nur gedeckelt   1 Ziel  ueber 0,003   - schliesst alles auf einmal
    skaliert        2 Ziele ueber je 0,001, Rest laeuft weiter

Der Spitzenkandidat hat nur ein Ziel bei 20R und war davon nicht betroffen.
Fuer jede Strategie mit gestaffelten Zielen macht es den Unterschied
zwischen "ein Drittel mitnehmen" und "alles schliessen". Der Test dafuer
prueft deshalb die **Verteilung**, nicht die Summe - eine Pruefung auf die
Summe waere gruen geblieben.

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

## Der fuenfte Befund: Das Plateau-Gate hatte selbst einen Fehler

Das Parameter-Plateau ist seit dem 06.08.2026 offen. Bevor ich daraus etwas
schliesse, habe ich das Gate selbst geprueft - und dort einen Fehler
gefunden.

**Die "Nachbarn" waren keine.** ``_vary_periods`` verschob nur
``entry_long``, ``entry_short`` und ``filters``. Beim Spitzenkandidaten -
Einstieg ueber dem 50-Tage-Schnitt, Ausstieg darunter - entstand daraus:

    Kandidat    ein SMA(50)   aus SMA(50)   Konfluenz 50/200/90/14
    Nachbar 1   ein SMA(40)   aus SMA(50)   Konfluenz 50/200/90/14
    Nachbar 2   ein SMA(60)   aus SMA(50)   Konfluenz 50/200/90/14

Eine Regel, die bei 40 einsteigt und bei 50 aussteigt, widerspricht sich
selbst - das ist kein Nachbar, sondern eine halb verstellte Strategie. Und
die Konfluenz, die beim Kandidaten die **Positionsgroesse** bestimmt, wurde
ueberhaupt nie variiert. Der Docstring behauptete die ganze Zeit "alle
Indikatorperioden".

Behoben: Alle Abschnitte werden mit demselben Faktor verschoben, das
Vola-Messfenster eingeschlossen. Die Nachbarn sehen jetzt so aus:

    Nachbar 1   ein SMA(40)   aus SMA(40)   Konfluenz 40/160/72/11   vol 24
    Nachbar 2   ein SMA(60)   aus SMA(60)   Konfluenz 60/240/100/17  vol 36

**Am Ergebnis aendert das nichts.** Weiterhin 1 von 2. Gemessen auf beiden
Maerkten, damit nicht der Einzelmarkt-Zuschnitt des Gates die Antwort gibt:

                   BTC allein   ETH allein        Korb
    Kandidat (50)     +109,62      +842,08     +475,85   profitabel
    Nachbar   (40)   +1138,08       -58,67     +539,70   profitabel
    Nachbar   (60)      -33,28       -76,58      -54,93   VERLUST

Der Befund des Gates steht also: **SMA 40 gewinnt, SMA 50 gewinnt, SMA 60
verliert.**

**Was ich daraus geschlossen habe, war falsch.** Hier stand: "Das ist kein
Plateau, das ist ein Abhang. Die Regelfamilie ist gegen ihre eigene
Periodenwahl nicht robust." Das war aus **zwei** Messpunkten geschlossen -
genau die Art Verallgemeinerung, die ich an anderer Stelle in diesem
Dokument kritisiere. Die Karte im naechsten Abschnitt zeigt etwas anderes.

Auffaellig bleibt die Streuung von Nachbar 1: zehnfacher Gewinn auf BTC,
Verlust auf ETH.

## Der sechste Befund: Es ist ein Plateau - der Kandidat sitzt am Rand

Zwei Messpunkte koennen nicht unterscheiden, ob jemand auf einer Nadelspitze
sitzt oder am Rand einer breiten Hochebene. ``cli landschaft`` tastet die
Periode vom halben bis zum doppelten Wert ab. Auf BTC + ETH, August 2017 bis
August 2026:

    Faktor  Leitperiode  Trades      Gewinn
      0,50          100     103      377,94  +
      0,60          120     168      844,11  +
      0,70          140     128      589,66  +
      0,80          160     121      539,70  +
      0,90          180      98      539,68  +
      1,00          200      93      475,85  +   <== Kandidat
      1,10          220      84      219,12  +
      1,25          250      45      -46,59  -
      1,40          280      41       -5,38  -
      1,60          320      80       -4,79  -
      1,80          360      77      +16,81  +
      2,00          400      71      -19,15  -

**Sieben zusammenhaengende profitable Punkte**, und der Kandidat liegt
darin. Die Regelfamilie traegt also ueber einen breiten Bereich - von
halber bis leicht ueber voller Periodenlaenge. Das ist das Gegenteil dessen,
was ich einen Durchlauf zuvor behauptet hatte.

Der Kandidat sitzt allerdings am **rechten Rand** dieser Hochebene: rechts
von ihm liegt nur noch ein profitabler Punkt, links sechs. Genau das
berichtet das Gate mit seinem "1 von 2" - es prueft plus/minus 20 %, und die
Seite nach oben faellt schon ab.

Der Ausreisser bei Faktor 1,80 ist keine zweite Hochebene, sondern Rauschen:
ein einzelner Punkt mit +16,81 zwischen lauter Verlusten.

**Was auffaellt und nicht genutzt wird.** Die schnelleren Punkte liefern
deutlich mehr Trades - 168 bei Faktor 0,60 gegen 93 beim Kandidaten - und
sind zugleich profitabler. Mehr Trades derselben Guete waeren genau das, was
dem Deflated Sharpe fehlt (siehe "Woran der Deflated Sharpe wirklich
haengt").

Trotzdem wird der Parameter **nicht** verschoben. Den besten Punkt aus einer
Karte zu waehlen, die auf denselben Daten entstanden ist, ist Ueberanpassung
mit mehr Nachkommastellen. Der legitime Weg waere, die Periode **innerhalb**
des Walk-Forward je Trainingsfenster neu zu bestimmen und im Testfenster zu
verwenden - dann waere sie out-of-sample gewaehlt. Das ist eine eigene
Hypothese und eine eigene Baustelle.

Die zwoelf Punkte sind in den Versuchszaehler eingegangen: 81 -> 92. Der
Deflated Sharpe faellt dadurch von 0,820 auf 0,800. Wer eine Landschaft
ansieht, hat sie gesehen - auch wenn er nichts daraus auswaehlt.

**Was ich nicht getan habe.** Naheliegend waere, das Gate mit mehr
Stuetzpunkten zu rechnen - bei nur zwei Nachbarn ist die Schwelle 0,6
faktisch binaer, denn 1 von 2 ergibt 0,5 und es gibt keinen Mittelwert
dazwischen. Naehere Nachbarn (plus/minus 10 %) wuerden die Quote
systematisch heben und der Kandidat bestuende. Das waere eine Lockerung mit
Begruendung hinterher, und danach misst das System nur noch sich selbst.

Ebenso wenig habe ich SMA 40 zum neuen Kandidaten erklaert, obwohl er auf
dem Korb besser abschneidet. Den besten Nachbarn zu nehmen ist genau die
Ueberanpassung, gegen die das Gate gebaut wurde.

## Der siebte Befund: Die Periode im Training zu waehlen hilft nicht

Das war die letzte substanzielle Idee, die ich hatte, und sie ist widerlegt.

Der Gedanke war sauber: Die Landschaftskarte zeigt, dass schnellere Perioden
mehr Trades bei hoeherem Gewinn liefern - genau das, was dem Deflated Sharpe
fehlt. Den besten Punkt aus der Karte zu nehmen waere Ueberanpassung, weil
sie auf denselben Daten entstand. Also: die Periode in **jedem
Trainingsfenster neu bestimmen** und im Testfenster verwenden. Dann kennt die
Wahl die Testdaten nicht.

Die Auswahlregel stand **vor** der Messung fest, damit ich hinterher nicht
diejenige nehme, die am besten aussieht: gewaehlt wird die **Mitte des
laengsten zusammenhaengenden profitablen Bereichs**, nicht der Punkt mit dem
hoechsten Gewinn. Begruendung: Der Spitzenwert wandert von Fenster zu
Fenster, der tragfaehige Bereich nicht.

Gemessen auf denselben 31 Fenstern, BTC + ETH:

                          Trades    p.a.       DD     Sharpe     DSR   Gates
    fester Parameter (50)    156   11,22 %   9,74 %    1,50    0,800   8/11
    im Training gewaehlt     166   10,06 %  10,72 %    1,28    0,624   7/11

**Schlechter in jeder Hinsicht ausser der Trade-Zahl.** Die Diagnose zeigt,
warum:

    fester Parameter      156 Trades   Erwartung +1,043 R   Sharpe/Trade 0,242
    im Training gewaehlt  166 Trades   Erwartung +0,850 R   Sharpe/Trade 0,211

Sechs Prozent mehr Trades, aber achtzehn Prozent weniger Erwartung je Trade.
Das Produkt, an dem der Deflated Sharpe haengt, faellt von 3,01 auf 2,71.

Der Grund steht in der Wahltabelle: Ueber 31 Fenster wurden **sechs
verschiedene Faktoren** gewaehlt, Spanne 0,60 bis 1,10, und in vier Fenstern
fand sich im Training gar kein tragfaehiger Bereich. Die Periode springt
also, und bei jedem Sprung entstehen Ein- und Ausstiege, die keinen Vorteil
tragen.

Damit ist auch die allgemeinere Frage beantwortet: **Der beste Bereich im
Trainingsfenster sagt zu wenig ueber das Testfenster.** Das ist kein
Umsetzungsfehler, sondern eine Eigenschaft dieser Daten - und es erklaert
nebenbei, warum die Landschaftskarte so flach ist: Wo 0,60 bis 1,10 alle
aehnlich gut sind, ist auch im Training kaum zu erkennen, welcher gewinnt.

Was ich **nicht** getan habe: die Auswahlregel gewechselt, bis eine
funktioniert ("nimm den besten statt der Mitte", "glaette ueber mehrere
Fenster"). Die Regel stand vorab fest, das Ergebnis ist negativ, und das
Nachreichen einer besseren Regel waere dieselbe Ueberanpassung eine Ebene
hoeher.

Der Versuchszaehler steigt um **eins**, nicht um zwoelf: Die einzelnen
Faktoren wurden nur im Training angesehen und nie am Testergebnis gemessen -
die Auswahl ist Teil der Strategie geworden. Genau darin lag der methodische
Vorteil, auch wenn er sich nicht ausgezahlt hat.

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
| Deflated Sharpe | 0,800 | 0,95 |
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

    bei  92 Versuchen   DSR 0,800
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

## Elf. Acht Ausfuehrungsfehler, die nicht durch Nachdenken gefunden wurden

Die bisherigen Funde zur Ausfuehrung sind mir eingefallen. Das ist kein
Verfahren, und beim vorletzten Mal steckte hinter dem geratenen Fehler ein
anderer, den ich erst beim Nachpruefen sah. Wer so sucht, findet, woran er
gerade denkt.

Deshalb die Umkehrung: nicht mehr jeden Ablauf einzeln pruefen, sondern
**sieben Aussagen** formulieren, die in jedem Zustand gelten muessen
(``execution/invarianten.py``), und zufaellige Ereignisfolgen dagegen laufen
lassen (``tests/test_fuzz_ausfuehrung.py``). Teilfuellungen, Nachfuellungen,
Zielausfuehrungen, Stops an der Boerse, Preisspruenge, abgelehnte Orders,
Verbindungsabbrueche, Neustart mitten in einer Position, Kill-Switch - in
zufaelliger Reihenfolge, mit fester Saat, also wiederholbar.

Ergebnis: **acht Fehler, alle in Pfaden, die als getestet galten.** Jeder
hat jetzt einen eigenen Test, der faellt, wenn man die Korrektur zuruecknimmt
(``tests/test_ausfuehrung_robustheit.py``) - einzeln nachgeprueft, nachdem
frueher in diesem Projekt ein Test beim Zuruecknehmen der Korrektur gruen
blieb und damit nichts bewiesen hatte.

### 1. Der Not-Aus verstummte, wenn das Stornieren fehlschlug

``close_all`` rief ``cancel_all`` ungeschuetzt auf. Ein Verbindungsfehler
genuegte, und die Ausnahme flog durch ``_handle_kill_switch`` hindurch:
**keine Nachricht aufs Telefon, kein ``stop()``.** Der Kill-Switch hatte
ausgeloest, und der Nutzer erfuhr es nicht.

``emergency_close`` machte es an derselben Stelle laengst richtig - dieselbe
Sache, zwei Umsetzungen, eine davon falsch. Inzwischen das haeufigste
Fehlermuster in diesem Projekt.

Dazu kam eine falsche Diagnose: ``KlineStream.run`` faengt alles aus dem
Kerzen-Handler als ``ws.verbindung_verloren`` und baut die Verbindung neu
auf. Ein fehlgeschlagener Orderaufruf sah damit aus wie ein Netzproblem - und
waehrend des Backoffs fehlen Kerzen.

### 2. Der ernsteste: Der Not-Aus uebersah eine gerade gefuellte Position

Fuellt die Einstiegsorder, waehrend das Bracket noch auf sie wartet, ist die
Position da - aber ``bracket.is_open`` ist ``False``. Der Not-Aus fragte das
Bracket, nicht die Boerse. Er stornierte die Orders, meldete "alles
glattgestellt" und **liess die Position stehen**.

Das heisst: System aus, Position laeuft weiter, Meldung sagt das Gegenteil.
Dasselbe galt fuer eine nach einem Neustart uebernommene Position, die gar
kein Bracket hat.

Gefragt wird jetzt die Boerse (``OrderRouter.flatten``).

### 3. Ein abgelehntes Ziel riss das ganze Bracket mit

Laeuft der Kurs zwischen Order und Fill am ersten Ziel vorbei, ist dieses
Ziel sofort ausfuehrbar - und Bybit lehnt PostOnly genau dafuer ab. Der
haeufigste denkbare Fall, kein Randfall.

Der Fehler flog bis in ``LiveTrader._protect``, wo ein Kommentar behauptete,
``protect`` habe die Position bereits geschlossen. Sie war es nicht: Der Stop
stand, die Position lief, das Bracket wurde weggeworfen. Danach gab es keine
Ziele mehr, keinen Nachzug auf Einstand und **keine Ausstiegsbedingung** -
und ueber die enden 38,5 % aller Trades.

Ein einzelnes Ziel weniger kostet Ertrag. Ein verlorenes Bracket kostet die
Kontrolle.

### 4. Nach fehlgeschlagener Absicherung wurde die Position vergessen

Derselbe Kommentar, dieselbe Annahme. Jetzt wird nachgesehen statt
angenommen: Ist die Position noch da, wird sie geschlossen; geht auch das
nicht, bleibt das Bracket **stehen**, damit ueberhaupt noch jemand hinsieht,
und die Meldung geht als "DRINGEND" raus.

### 5. Restziele blieben nach dem Schliessen im Buch liegen

Greift der Stop an der Boerse oder faellt das erste Ziel, ist die Position
weg - die uebrigen Reduce-Only-Limits nicht. Gemessen in einer Zufallsfolge:
0,002 an Zielen im Buch bei 0 Position.

Reduce-Only verhindert eine Gegenposition. Es verhindert nicht, dass die
alten Verkaufslimits den **naechsten** Long sofort anschneiden - der Backtest
kennt so etwas nicht, die Abweichung waere als schwaechere Rendite erschienen,
nicht als Fehler.

Ob Bybit solche Orders von selbst raeumt, laesst sich aus diesem Container
nicht pruefen. Die simulierte Boerse ist deshalb absichtlich die
unfreundlichere Variante: Dort verschwinden sie nicht.

### 6. Ein misslungenes Aufraeumen bekam nie eine zweite Gelegenheit

Schlaegt das Storno beim Abschluss eines Trades fehl, blieben die Restziele
liegen, und niemand kam darauf zurueck. Jetzt wird es vermerkt, bei der
naechsten Kerze wiederholt - und solange es offen ist, **kein neuer Einstieg**.
Ein verpasster Einstieg kostet eine Gelegenheit, ein Einstieg in ein
unaufgeraeumtes Buch kostet Geld.

Beim Not-Aus geht das nicht, denn danach haelt der Prozess an. Dort wird
sofort dreimal versucht.

### 7. Nach einem Neustart lief die Position ohne jede Verwaltung weiter

Diesen hat **nicht der Fuzzer** gefunden, sondern die Invariante selbst: Sie
fing an, eine uebernommene Position dauerhaft als "unbeaufsichtigt" zu melden.
Zu Recht.

``_reconcile`` uebernahm eine offene Position beim Start - protokollierte sie,
meldete sie, und legte **kein Bracket** an. Damit stieg ``_manage_open_position``
bei jeder Kerze sofort wieder aus, und ``_check_signal_exit`` ebenso. Die
Ausstiegsbedingung, ueber die 38,5 % aller Trades enden, galt fuer diese
Position nicht mehr. Sie lief bis zum Stop.

Der Neustart mitten in einer Position steht als **Pflichttest im Plan** - und
genau dieser Test haette die Luecke nicht gezeigt: Der Stop haengt an der
Position und ueberlebt, es sieht also alles richtig aus. Der Schaden ist
still: ein Trade, der schlechter ausgeht, als er muesste.

Jetzt wird ein Bracket aus der Position gebaut (``_bracket_aus_position``):
Seite, Groesse, Einstieg und Stop kommen von der Boerse. **Die Ziele lassen
sich nicht wiederherstellen** - welche Stufen das urspruengliche Signal hatte,
steht nirgends mehr. Das wird gemeldet, nicht verschwiegen: Die Position laeuft
bis zum Stop oder bis die Ausstiegsbedingung greift.

Ein Detail, das ohne Test durchgerutscht waere: Nach einem Nachzug auf Einstand
liegt der Stop **auf** dem Einstiegspreis. Der Signal-Bauplan verlangt ihn echt
darunter - die Uebernahme haette also ausgerechnet bei einem Trade geworfen, der
schon im Gewinn lag.

### 8. Der Start scheiterte an seiner gefaehrlichsten Stelle

Findet der Abgleich beim Start eine Position **ohne Stop**, schliesst er sie -
richtig so, ihre Begruendung ist nach einem Neustart nicht mehr bekannt.
Schlug der Marktausstieg fehl, flog die Ausnahme aber aus ``start()`` heraus:
**Der Prozess startete nicht und liess die ungeschuetzte Position stehen.**

Schlechter geht es kaum. Der gefaehrlichste Zustand ueberhaupt, kombiniert mit
einem System, das nicht mehr hinsieht - und der Ausloeser ist ein einzelner
fehlgeschlagener Aufruf.

Jetzt gibt es eine Reihenfolge: schliessen; wenn das nicht geht, wenigstens
einen Stop im maximal zulaessigen Abstand setzen; wenn auch das nicht geht, die
Position trotzdem uebernehmen. Ein Bracket ohne Stop ist ein schlechter
Zustand, aber ein **gesehener**: Die Ausstiegsbedingung greift, der Not-Aus
greift, und die Invariantenpruefung meldet ihn bei jeder Kerze aufs Telefon.

### Eine Praezisierung, die nach dem ersten grossen Lauf noetig war

Bei 400 Zufallsfolgen fielen drei. Zwei davon waren Befund 8 - ein echter
Fehler. Die dritte meldete eine gewachsene Position, die im Bracket nicht
vermerkt war; die Meldung stimmte, aber die Ursache war nicht die, die sie
nahelegte: Der Marktausstieg der Wachstumspruefung war auf einen simulierten
Ausfall gelaufen, und der Abgleich brach ab, **bevor er fertig war**.

Der Unterschied war nicht offensichtlich - ich habe erst alle drei einzeln
nachgestellt, statt vom ersten auf die anderen zu schliessen. Haette ich es
nicht getan, waeren zwei echte Fehler als Messartefakt durchgegangen.

Die Invarianten gelten nach dem Abgleich, nicht waehrend eines abgebrochenen.
Der Fuzzer prueft deshalb nur noch Kerzen, die durchgelaufen sind. Das ist
keine gelockerte Huerde: Der Anspruch bleibt, dass die naechste
**vollstaendige** Kerze den Zustand geradezieht, und die Schleife laeuft
weiter - eine Verletzung, die bestehen bleibt, faellt beim naechsten sauberen
Durchlauf auf. Dazu kommen zwei Bedingungen, die eine leere Runde verhindern:
Mindestens die Haelfte der Kerzen muss durchgelaufen sein, und **jede Ausnahme,
die kein simulierter Boersenausfall ist** - ein ``AttributeError`` etwa - laesst
den Lauf fallen.

Die Erholung selbst ist nicht behauptet, sondern gemessen: Ein eigener Test
laesst die Position auf 0,004 wachsen, den Notausstieg scheitern, und prueft,
dass die Folgekerze schliesst.

### Was das gekostet und was es gebracht hat

Der Fuzzer ist keine Strategiehypothese: **Der Versuchszaehler bleibt bei 93.**
Er darf deshalb beliebig oft laufen. In der Suite laufen 25 Folgen, fuer eine
gruendliche Runde ``FUZZ_SAATEN=600 pytest tests/test_fuzz_ausfuehrung.py``.

Dieselben sieben Aussagen laufen jetzt **im Betrieb** mit, einmal je Kerze
(``LiveTrader._pruefe_invarianten``). Sie melden, sie greifen nicht ein: Eine
Pruefung, die im Betrieb noch nie angeschlagen hat, automatisch Positionen
schliessen zu lassen, hiesse einem Fehlalarm Geld anzuvertrauen. Verletzungen
und Verarbeitungsfehler stehen im Dashboard und gehen einmalig aufs Telefon.

### Was er nicht kann

Er prueft die Ausfuehrung gegen eine **simulierte** Boerse. Ob Bybit sich so
verhaelt wie ``FakeExchange``, prueft er nicht - das kann nur der Demobetrieb.
Der Fuzzer verschiebt die Frage also von "ist der Code richtig" zu "ist die
Simulation richtig". Das ist ein Fortschritt, aber kein Beweis.

Die Reihenfolge bleibt damit unveraendert: Erst ``cli healthcheck`` auf dem
Rechner des Nutzers - er entscheidet, ob Perpetuals auf dem Konto ueberhaupt
verfuegbar sind -, dann Demobetrieb, dann echtes Geld.

## Zwoelf. Das Termin-Overlay - gebaut, gemessen, und es bewegt nichts

Phase 7 war nie gebaut worden. Der Risk-Officer kannte das Veto
``NEWS_BLACKOUT`` und die Methode ``set_news_blackout`` von Anfang an; was
fehlte, war die Quelle.

**Was jetzt drinsteht** (``data/termine.py``, geholt mit ``cli termine``):

    138 Termine, 2012-01-25 bis 2027-12-08
    134 FOMC-Entscheidungen, 4 Bitcoin-Halbierungen
    davon 5 ausserplanmaessig

Nur Nachpruefbares. Die FOMC-Termine kommen von federalreserve.gov - gelesen
wird der Dateiname der Erklaerungs-Pressemitteilung, nicht die Sitzungsangabe
im Text. Das ist der Tag der Veroeffentlichung und damit der Moment, an dem
sich der Kurs bewegt. Die Halbierungen sind die **Blockzeit** von
mempool.space, kein Schaetzwert.

**Was fehlt:** CPI-Termine. bls.gov antwortet diesem Container mit 403. Ein
geschaetztes Datum waere schlimmer als keines - es wuerde den falschen Tag
sperren und den echten offenlassen. Vom Rechner des Nutzers aus ist die Seite
erreichbar; ``cli termine`` laeuft dort und kann die Luecke schliessen.

### Die Regel, bevor gemessen wurde

    60 Minuten Vorlauf, 60 Minuten Nachlauf
    plus: die Kerze, in die der Termin faellt

Der zweite Teil ist der wichtige und der einzige, der ohne Einstellung
auskommt. Eine Fed-Entscheidung um 18:00 UTC liegt sechs Stunden vor dem
Tagesschluss - mit 60 Minuten Vorlauf allein wuerde sie auf Tageskerzen
**nie** greifen. Mit der Kerzenregel sperrt sie den Einstieg am naechsten
Mitternachtsschluss, auf 15-Minuten-Kerzen die Stunde davor und danach.
Dieselbe Regel, jedes Intervall, keine Zahl, die sich passend drehen laesst.

### Das Ergebnis

BTC + ETH, Tageskerzen, Walk-Forward, nach Gebuehren:

    Lauf                 Trades    p.a.      DD      Sharpe   DSR     Gates
    ohne Termin-Sperre      156   11,22 %   9,74 %    1,50   0,798    8/11
    mit Termin-Sperre       154   11,28 %   9,74 %    1,51   0,804    8/11

    Signale wegen Termin abgelehnt: 2 von 156

**Zwei Einstiege in neun Jahren.** Das ist Rauschen, kein Effekt. Kein Gate
bewegt sich, und das war vorher absehbar: Der Kandidat haelt eine Position im
Schnitt sechs Wochen. Ein Overlay hindert am *Einstieg*, nicht am Halten - eine
laufende Position wird nicht wegen einer Fed-Sitzung geschlossen. Bei acht bis
zwoelf Terminen im Jahr und acht Einstiegen je Markt und Jahr treffen sich die
beiden schlicht fast nie.

Gebraucht wird es fuer die **15-Minuten-Generationen**: Dort wuerde eine
Position auch mal zwei Stunden vor einer Fed-Entscheidung eroeffnet, und dort
ist der Ausschlag nicht mehr im Rauschen.

Der Versuchszaehler steht damit auf **94**. Die Messung war eine Hypothese auf
denselben Daten, also zaehlt sie - auch wenn das Ergebnis "kein Unterschied"
lautet und die Sperre aus Risikogruenden bleibt, nicht wegen der Zahlen. Wer
nur die Versuche zaehlt, die etwas gebracht haben, rechnet sich die Huerde
klein.

### Zwei Fehler beim Bauen, beide beim Nachzaehlen gefunden

**Der Kalender endete bei Juli 2026.** Der erste Abruf las nur die
Pressemitteilungen - und eine Sitzung, die noch nicht stattgefunden hat, hat
keine. Ein Termin-Overlay, das nur vergangene Termine kennt, sperrt im Betrieb
**nie**. Im Backtest waere es nicht aufgefallen, dort ist alles Vergangenheit.
Jetzt werden beide Lesarten derselben Seite zusammengefuehrt.

**Der Parser haette jeden Termin ab August 2025 um Wochen verschoben.** Monate
und Datumsangaben als zwei parallele Listen zu lesen ist naheliegend und auf
echten Daten falsch: Das Jahr 2025 hat eine August-Zeile **ohne** Datum. Neun
Monate, acht Daten - ab dort bekam September den Oktobertermin.

    naiv        September 2025 -> 28./29.
    zeilenweise September 2025 -> 16./17.

Gefunden nur, weil die Zahlen nicht zusammenpassten. Der Test dazu benutzt
einen unveraenderten Ausschnitt der echten Fed-Seite - ein selbst erfundenes
Beispiel haette genau die Eigenheit nicht gehabt, um die es geht.

Dazu eine dritte Korrektur an mir: Ob eine Sitzung ausserplanmaessig war,
hatte ich geschaetzt (weniger als drei Wochen Abstand zur vorigen). Der Test
fiel durch, und zu Recht - der 3. Maerz 2020 liegt 34 Tage nach dem 29. Januar
und war trotzdem eine Notfallsitzung. Die Fed-Seite schreibt ``(unscheduled)``
daneben. Jetzt wird das gelesen statt gerechnet.
