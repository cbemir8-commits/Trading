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

## Dreizehn. Die Gegenrichtung traegt nicht - und ich haette es fast anders gemeldet

Der Kandidat ist **long-only**: ``entry_short`` ist leer. Da der Deflated
Sharpe dominant an ``sqrt(n-1)`` haengt und 156 Trades zu wenig sind (fuer 0,95
braeuchte es rund 220 bei gleicher Qualitaet), war die Short-Seite der einzige
ungemessene Hebel, der die Zahl verdoppeln koennte, ohne die Datenbasis zu
verwaessern.

Die Spiegelung ist woertlich: Einstieg, wenn der Kurs unter den SMA(50) faellt,
Ausstieg, wenn er darueber zurueckkehrt. Kein neuer Indikator, kein neuer
Parameter.

### Das Ergebnis sah nach Fortschritt aus

    Variante          Trades   Short    p.a.      DD      SR/Trade   DSR    Gates
    long-only            154       0   11,28 %   9,74 %    0,242    0,804   8/11
    long + short         302     148   12,50 %   8,74 %    0,160    0,852   9/11

Mehr Rendite, weniger Rueckgang, ein Gate mehr - **auf jeder Achse besser.**
Ich war eine Zeile davon entfernt, "9 von 11" zu melden.

### Drei Gegenproben, und alle drei sagen nein

**Erstens: die Short-Seite allein.** 148 Trades, Erwartungswert **-0,002 R**,
Trefferquote 21,6 %. Kein Vorteil, sondern eine Null.

**Zweitens: haette Rauschen dasselbe gebracht?** Im echten Lauf wurden nur die
Short-Trades durch Zufallszahlen mit demselben Mittelwert und derselben
Streuung ersetzt - alles andere blieb, dieselben Long-Trades, dieselbe
Rechnung, dieselbe Versuchszahl. Gerechnet auf ``net_pnl`` in Euro und mit
denselben Momenten wie im Gate:

    500 Rausch-Ziehungen: DSR im Mittel 0,821, Spanne 0,458 bis 0,998
    echte Shorts:         DSR 0,852
    Anteil der Ziehungen, die mindestens so gut sind: 46,4 %

**Fast die Haelfte reinen Rauschens schneidet mindestens so gut ab.** Der
DSR-Gewinn von 0,841 auf 0,852 ist kein Nachweis, sondern eine Zahl aus dem
Rauschband.

Beruhigend ist dabei ein Nebenbefund: Blosses Anhaengen nutzloser Trades
*verschlechtert* den DSR normalerweise deutlich (154 Trades mit SR 0,242 plus
148 Nulltrades gleicher Streuung ergibt DSR 0,31). Das Gate ist also nicht
beliebig aufblasbar - es ist nur unempfindlich gegen ein **leises** Nullbein,
weil das den Mittelwert verduennt und die Streuung zugleich senkt.

**Drittens - und das ist die Gegenprobe, die auch die Wirtschaftlichkeit
kippt: fensterweise statt im Aggregat.**

    31 Fenster: 12 besser, 18 schlechter, 1 unveraendert
    geringerer Rueckgang in nur 5 von 31 Fenstern
    mittlere Differenz +1,33 EUR je Fenster bei einer Streuung von 9,91
    Vorzeichentest: p = 0,90

Die **Mehrzahl der Fenster wird schlechter.** Die besseren Aggregatzahlen
kommen aus wenigen guenstigen Fenstern - genau die Pfadabhaengigkeit, gegen die
der Walk-Forward gebaut ist und die im Gesamtergebnis trotzdem verschwindet,
weil ein starkes Fenster achtzehn schwache ueberdecken kann.

Versuchszaehler: **95**. Achte gemessene und widerlegte Richtung.

### Was bleibt: ein Werkzeug gegen genau diesen Fehler

``research/fenstervergleich.py``. Zwei Laeufe fensterweise gegeneinander,
Vorzeichentest, und ein Urteil, das sich weigert, eine Verbesserung
auszurufen, wenn nur das Aggregat besser ist:

    Urteil: NICHT belastbar - die Mehrzahl der Fenster wird SCHLECHTER.

Der Vorzeichentest ist absichtlich das schwaechste denkbare Verfahren: Er
benutzt nur die Richtung, nicht die Groesse. Damit kann ein einzelnes
Ausreisserfenster das Urteil nicht kippen - und genau darum ging es hier.

**Die Regel, die ab jetzt gilt:** Eine Verbesserung, die sich nicht in der
Mehrzahl der Fenster zeigt, ist keine. Das Aggregat darf sie bestaetigen, aber
nicht begruenden. Ich haette diese Regel frueher gebraucht.

### Was daraus fuer die Gates folgt

Der Stand bleibt **8 von 11**. Offen sind unveraendert Messlatte (11,28 % gegen
15 %), Deflated Sharpe (0,804 gegen 0,95) und Parameter-Plateau (0,50 gegen
0,60).

## Vierzehn. Der Tageskerzen-Weg ist ausgereizt - gerechnet, nicht vermutet

Bisher hiess es "der Deflated Sharpe fehlt noch". Wie viel genau, stand
nirgends. Jetzt schon (``cli abstand``):

    Deflated Sharpe 0,802 (noetig 0,95) bei 154 Trades, Sharpe je Trade 0,244
    Bei gleicher Qualitaet je Trade: 207 Trades noetig - es fehlen 53.
    Bei gleicher Trade-Zahl:         Sharpe je Trade 0,278 noetig (Faktor 1,14)

Der Abstand ist also **klein**: 53 Trades oder 14 % mehr Qualitaet je Trade.
Das klang nach einer loesbaren Aufgabe. Zwei Messungen sagen etwas anderes.

### Die weggeschnittene Historie reicht nicht

BTC liegt seit **2012** im Speicher, 5331 Tageskerzen. Der Portfoliolauf
schneidet auf den gemeinsamen Bereich mit ETH zu und beginnt deshalb erst
2017-08 - 5,6 Jahre BTC werden weggeworfen. Das ist keine Hypothese, sondern
eine Abschneidung; sie auszuschoepfen kostet **keinen Versuch**.

    Datenbasis                       n    SR/Trade    DSR
    gemeinsamer Bereich ab 2017    154      0,244    0,802
    BTC voll allein (ab 2012)      117      0,207    0,319
    ETH voll allein (ab 2017)       80      0,248    0,303
    BTC voll + ETH voll            197      0,224    0,852

197 statt 154 Trades - fast die noetigen 207. Aber die aeltere BTC-Historie ist
fuer diese Regel schwaecher (0,207 gegen 0,248), der Sharpe je Trade faellt auf
0,224, **und damit steigt die Anforderung auf 245 Trades.** Der Abstand wird
groesser, nicht kleiner. Mehr Vergangenheit hilft hier nicht.

### Keine Marktkombination besteht

Alle fuenfzehn Kombinationen der vier vorhandenen Maerkte, echte
Portfoliolaeufe, dieselben Gates:

    Kombination           n      p.a.       DD      DSR    Gates
    ETH                  80    11,08 %   11,51 %   0,303    8/11
    BTC+ETH             154    11,28 %    9,74 %   0,802    8/11
    BTC+ETH+LTC         260     9,03 %   11,15 %   0,873    6/11
    BTC+ETH+XRP         262     8,79 %   10,03 %   0,794    8/11
    BTC+ETH+LTC+XRP     368     7,73 %   10,71 %   0,875    7/11

**Keine einzige besteht.** Und die Zahlen zeigen, warum: Die beiden offenen
Gates ziehen gegeneinander. Mehr Maerkte bringen Trades (DSR steigt auf 0,875)
und kosten Rendite (7,73 % gegen die 15 % der Messlatte). Weniger Maerkte
bringen Rendite (11,28 %) und kosten Trades (DSR faellt auf 0,80). Das Optimum
der einen Achse ist das Minimum der anderen.

Mit diesem Genom, auf Tageskerzen, mit diesen Maerkten ist **kein Punkt
erreichbar, an dem alle elf Gates halten.** Das ist kein Zwischenstand, sondern
ein Ergebnis.

### Was jeder weitere Einfall kostet

Die unangenehmste Zahl des Projekts steht in derselben Rechnung:

    Versuche      DSR    noetige Trades
        10      0,992         112
        50      0,893         180
        95      0,802         207   <- heute
       200      0,666         237
       500      0,481         275

Derselbe Kandidat, dieselben Daten, dieselbe Rechnung. Nur die Suche davor war
laenger. **Die Huerde waechst mit jedem getesteten Einfall** - die Zahl der
Versuche steht in der Huerde selbst, nicht bloss in der Buchhaltung. Bei zehn
Versuchen haette dieser Kandidat mit 112 Trades bestanden; heute braeuchte er
207.

Ein weiterer Versuch kostet zurzeit 0,0017 DSR-Punkte, zehn kosten 0,0167. Wer
zwanzig Einfaelle durchprobiert, um den Sharpe je Trade um 3 % zu heben, hat
danach weniger als vorher. Das laesst sich **vorher** ausrechnen, und ab jetzt
wird es das: ``research/erreichbarkeit.py`` und ``cli abstand``.

Die Reihenfolge, die daraus folgt: **Erst die Datenbasis ausschoepfen, dann
suchen.** Mehr Daten kosten keinen Versuch, eine neue Idee schon.

### Was daraus fuer den Plan folgt

Der einzige Hebel, der Trades bringt, **ohne** die Rendite je Trade zu
verwaessern, ist eine hoehere Handelsfrequenz - nicht mehr Maerkte und nicht
mehr Vergangenheit. Damit ist der naechste Schritt der, der ohnehin auf der
Liste steht und den ich nicht selbst gehen kann:

    python -m cli backfill --intervall 15 --von 2020-03-30
    python -m cli wettbewerb -i 15

Auf 15-Minuten-Kerzen liegen in denselben sechs Jahren rund hundertmal so viele
Kerzen. Ob dort ein Vorteil steckt, ist offen - die Messung im Maerz
(Mean-Reversion auf 15 Minuten, kein Bruttovorteil) spricht dagegen, betraf
aber eine andere Regelfamilie. Was feststeht: Auf Tageskerzen ist der Weg zu
Ende gerechnet.

## Fuenfzehn. Auf 15 Minuten ist nichts zu holen - und eine Korrektur an mir

**Zuerst der Fehler.** Im vorigen Abschnitt steht, der naechste Schritt sei der,
"den ich nicht selbst gehen kann": 15-Minuten-Kerzen holen. Das war falsch.
Die Daten liegen seit einem frueheren Lauf im Speicher - **222.700 Kerzen** je
Markt fuer BTC und ETH, 2020-03-30 bis 2026-08-05. Ich habe sie selbst geholt
und es dann vergessen.

Dasselbe Muster steht schon einmal weiter oben ("Selbst auferlegte Blockade").
Zweimal derselbe Fehler: eine Aufgabe an den Nutzer weiterreichen, die ich
haette erledigen koennen. Der Nutzer braucht den Backfill weiterhin auf seinem
Rechner, um ``cli wettbewerb`` dort laufen zu lassen - fuer die **Messung**
brauchte ich ihn nicht.

### Der Scan, der keinen Versuch kostet

Bevor Versuche in 15-Minuten-Regeln fliessen, die Frage davor: Steckt dort
ueberhaupt etwas? Das laesst sich messen, ohne eine handelbare Regel zu pruefen
- und kostet deshalb keinen Versuch (``research/vorteilsscan.py``, ``cli scan``).

Gemessen wird die **Spanne**: mittlere Vorwaertsrendite nach steigendem
Rueckblick minus nach fallendem. Benchmarkfrei, denn der Grundtrend steht in
beiden Zustaenden und faellt heraus. Der erste Anlauf mass die bedingte
Rendite selbst und fand ueberall grosse Zahlen - das war der Drift eines
Marktes, der sich vervielfacht hat, und kein Vorteil.

Beobachtet wird nur alle ``Halten`` Balken einmal. Ueberlappende Fenster waeren
nicht unabhaengig, und der t-Wert daraus um den Faktor Wurzel(Halten) zu gross
- der bequemste Weg, sich einen Vorteil herbeizurechnen.

### Das Ergebnis

    BTC 15m   bester Treffer  Rueckblick 4 h / Halten 4 h
              Spanne -0,0883 %   t = -4,11   bei 13.917 Beobachtungen
    ETH 15m   dieselbe Zelle
              Spanne -0,0778 %   t = -2,75

Eine kurzfristige **Gegenbewegung**, marktuebergreifend bestaetigt. Das sah
nach einem Fund aus. Drei Gegenproben:

**Zeitlich.** Erste Haelfte t = -2,90, zweite Haelfte **t = +0,29**. Nach
Jahren: 2021 und 2024 tragen alles (t = -2,76 und -3,08), 2020, 2022, 2023,
2025 und 2026 zeigen nichts. Der Effekt ist in der juengeren Haelfte des
Zeitraums vollstaendig verschwunden - wegarbitriert oder nie da gewesen.

**Wirtschaftlich.** Die Spanne ist der Unterschied zwischen zwei Zustaenden;
eine Regel handelt eine Seite und erntet grob die Haelfte:

    halbe Spanne              0,0441 %
    Kosten Maker/Maker        0,0400 %   -> netto +0,0041 %
    Kosten Maker/Taker        0,0750 %   -> netto -0,0309 %

Vier Tausendstel Prozent je Trade im **guenstigsten** Fall, in dem beide Seiten
als Limit-Order fuellen. Ein einziger Ausstieg zum Marktpreis kippt es.

**Mehrfachtestung - und hier hatte ich denselben Fehler eingebaut, gegen den
das Werkzeug schuetzen soll.** Der Scan prueft 81 Zellen je Markt. Bei ``|t| >= 2``
sind darunter rein zufaellig vier auffaellige zu erwarten. Wer die beste nimmt
und fuer einen Fund haelt, misst nur die Zahl seiner Versuche - dasselbe
Problem wie beim Deflated Sharpe, eine Ebene tiefer. Korrigiert nach Bonferroni
liegt die Schwelle bei 81 Zellen nicht bei 2,00, sondern bei **3,42**.

Damit faellt ETHs bester 15-Minuten-Treffer (t = +3,04) durch. BTCs -4,11
haelt der Korrektur stand und scheitert an der Stabilitaet. Beide Huerden sind
noetig, und sie sind unabhaengig.

### Die Kontrolle - und was sie ueber den Kandidaten sagt

Ein Scan, der nirgends etwas findet, koennte auch schlicht kaputt sein. Deshalb
laufen die Tageskerzen als Kontrolle mit, wo ein Vorteil bekannt ist:

    BTC Tageskerzen   bester Treffer  t = +3,64,  Spanne +1,54 %,  38x Kosten
    ETH Tageskerzen   bester Treffer  t = +2,80,  Spanne +1,73 %,  43x Kosten

Der Scan findet den Tagesvorteil, und er ist um Groessenordnungen groesser als
die Kosten - anders als auf 15 Minuten. Das Werkzeug funktioniert.

Zwei Dinge daran sind unbequem und gehoeren gesagt:

* **ETH faellt durch die Mehrfachtestungs-Korrektur** (t = +2,80 gegen eine
  Schwelle von 3,23 bei 40 Zellen).
* **BTC ist in der zweiten Haelfte schwaecher**: erste Haelfte t = +3,26,
  zweite Haelfte t = +1,40.

Beides ist ein Warnzeichen, aber **kein Beweis**. Die Tagesreihe hat 5331
Balken; halbiert bleiben 2665, und die Trennschaerfe ist dort gering - ein
eigener Test haelt genau das fest (derselbe eingebaute Vorteil wird bei 6000
Balken verworfen und bei 20.000 gefunden). Ausserdem misst der Scan ein grobes
Vorzeichen-Signal, nicht den Kandidaten mit seinen drei Konfluenzbedingungen
und der Vola-Zielgroesse. Der Walk-Forward misst den Kandidaten selbst, und der
liefert 11,28 % im Jahr ausserhalb der Stichprobe.

Die vorsichtige Lesart: Der Vorteil auf Tageskerzen ist echt, aber **duenn und
moeglicherweise abnehmend**. Das passt zu einem Deflated Sharpe, der bei 0,80
haengenbleibt.

### Was daraus folgt

Der Versuchszaehler bleibt bei **95**. Es wurde keine Regel geprueft, sondern
die Struktur des Marktes - genau dafuer ist der Scan da.

Und die Reihenfolge steht jetzt fest: **erst scannen, dann Versuche ausgeben.**
Waere der Scan vor den acht widerlegten Richtungen dagewesen, haetten mehrere
davon nie einen Versuch gekostet. Fuer 15 Minuten ist die Antwort damit
gegeben, ohne einen einzigen Versuch verbraucht zu haben: **Dort ist nach
Kosten nichts zu holen.**

## Sechzehn. Zwoelf Scans, null Funde - und die Grenze ist immer dieselbe Zahl

Der Scan aus dem vorigen Abschnitt kostet keinen Versuch. Also wurde er auf
alles angewandt, was da ist: vier Maerkte, vier Intervalle. Die
Zwischenintervalle entstehen durch Verdichten der 15-Minuten-Kerzen
(``data/resample.py``), decken also 2020-03-30 bis 2026-08-05 ab.

    Markt   Iv    Kerzen   Zelle    Spanne      t   Schwelle    netto   Urteil
    BTC    15m    222700   16/16   -0,0883%  -4,11    3,42    +0,0041%  verschwunden
    BTC     1h     55675    960/8  +0,1131%  +2,68    3,39    +0,0165%  unauffaellig
    BTC     4h     13918    192/8  +0,4331%  +2,48    3,33    +0,1765%  unauffaellig
    ETH    15m    222700    8/96   -0,4167%  -2,48    3,42    +0,1684%  unauffaellig
    ETH     1h     55675   96/192  +3,4574%  +2,62    3,39    +1,6887%  unauffaellig
    ETH     4h     13918    192/4  +0,3320%  +2,98    3,34    +0,1260%  unauffaellig
    BTC     1d      5331     48/4  +1,5432%  +3,64    3,23    +0,7316%  verschwunden
    ETH     1d      3277     32/4  +1,7330%  +2,80    3,23    +0,8265%  unauffaellig
    LTC     1d      3338   480/32 -11,3068%  -2,37    3,23    +5,6134%  unauffaellig
    XRP     1d      3504      4/8  +5,1543%  +2,86    3,24    +2,5372%  unauffaellig

**Zwoelf Kombinationen, kein einziger Fund.** Zehn liegen unter ihrer
mehrfachtestungs-korrigierten Schwelle. Die zwei, die sie schaffen, sind beide
in der zweiten Haelfte des Zeitraums verschwunden.

### Was "verschwunden" jetzt bedeutet - und eine Korrektur an mir

Im vorigen Abschnitt steht, der schwaechere zweite Teil der Tagesreihe sei ein
"Warnzeichen, aber kein Beweis", weil bei 2665 Balken je Haelfte "die
Trennschaerfe gering" sei. **Das war eine Vermutung, und sie ist falsch.**

Nachgerechnet (``erkennbare_spanne``): Der Standardfehler der zweiten Haelfte
betraegt 0,50 %; erkennbar waere mit vier Fuenftel Wahrscheinlichkeit ein
Effekt ab 1,40 %. Die erste Haelfte zeigte 1,54 %. **Die Trennschaerfe
reichte** - knapp, aber sie reichte. Die zweite Haelfte haette den Effekt also
mit rund 80 % Wahrscheinlichkeit gesehen und hat ihn nicht gesehen.

Das macht den Befund unangenehmer, nicht harmloser. Und es ist genau der
Fehler, den der Scan verhindern soll, nur von der anderen Seite: Ich hatte aus
"nicht stabil" auf "zu wenig Daten" geschlossen, ohne nachzurechnen. Der
Unterschied steht jetzt im Werkzeug (``Stabilitaet.aussagekraeftig``) und wird
im Urteil ausgesprochen - "verschwunden" oder "nicht entscheidbar" sind zwei
verschiedene Aussagen.

### Der Kandidat selbst - und warum darueber nichts zu erfahren ist

Der Scan misst ein grobes Vorzeichen-Signal, nicht den Kandidaten mit seinen
drei Konfluenzbedingungen. Also direkt gefragt: die 31 Testfenster halbiert.

    Haelfte             Zeitraum                Trades   Mittel     SR/Trade    t
    erste     2018-08 bis 2022-05                  75   +4,30 EUR    0,268   +2,32
    zweite    2022-05 bis 2026-05                  79   +2,47 EUR    0,221   +1,97
    gesamt    2018-08 bis 2026-05                 154   +3,36 EUR    0,244   +3,03

Der Vorteil ist in der zweiten Haelfte kleiner - und der Unterschied ist
**nicht nachweisbar** (t = -0,82).

Der entscheidende Satz steht daneben: Bei 79 Trades waere erst ein Rueckgang um
**111 %** erkennbar gewesen (``research/live_evidenz.py``, mit der gemessenen
Schiefe simuliert). Also mehr als der vollstaendige Verlust des Vorteils. Die
Messung sagt nicht "kein Abfall", sie sagt "hier ist nichts zu erfahren".

    beobachtete Trades    erkennbarer Rueckgang
                    14           245 %   (30 Tage Demo)
                    79           111 %   (zweite Haelfte)
                   154            80 %
                   600            41 %
                  2500            21 %

### Die Grenze ist immer dieselbe Zahl

Drei Fragen, drei Male dieselbe Antwort:

* **Besteht die Strategie das DSR-Gate?** Nein - es fehlen 53 Trades.
* **Laesst der Vorteil nach?** Unbekannt - bei 79 Trades je Haelfte waere erst
  ein Totalverlust sichtbar.
* **Beweist der Demobetrieb etwas?** Nein - bei 14 Trades braeuchte es 245 %.

Die Zahl der Trades begrenzt nicht nur die **Zulassung**, sondern auch das
**Wissen**. 154 Trades in acht Jahren sind zu wenig, um zu bestehen, und zu
wenig, um zu wissen, ob es noch funktioniert. Das sind nicht zwei Probleme,
sondern eines.

Und dieses eine Problem ist jetzt an drei Stellen unabhaengig gemessen und an
allen dreien gleich beantwortet: Mehr Maerkte verwaessern, mehr Vergangenheit
verwaessert, hoehere Frequenz traegt nach Kosten nicht. Der Versuchszaehler
bleibt bei **95** - keine dieser Messungen hat eine Regel geprueft.

## Siebzehn. Ein Loch im haertesten Gate - gefunden beim Versuch, es zu nutzen

Die Engine kann dieselbe Regel mit mehreren Perioden gleichzeitig handeln, je
Bein ein Anteil. Der Zweck steht seit dem ersten Tag im Docstring: "Wer eine
Trendfolge mit 30, 50 und 80 Tagen gleichzeitig handelt, bekommt drei leicht
verschobene Einstiegszeitpunkte statt eines einzigen. Genau daran haengt, wie
stark das Gesamtergebnis von wenigen Trades abhaengt."

Das ist die bindende Grenze des Projekts. Also gemessen, mit **vorab
festgelegten** Faktoren 0,7 / 1,0 / 1,3 - symmetrisch um den Kandidaten, gleich
gewichtet. Der Faktor 1,3 liegt ausserhalb des gemessenen Plateaus; das macht
die Probe strenger, nicht milder.

    Lauf                   Trades    p.a.      DD     SR/Trade    DSR (roh)
    einzeln (1,0)             154   11,28 %   9,74 %   0,244        0,802
    Ensemble 0,7/1,0/1,3      481    8,86 %   8,37 %   0,211        0,999

**Das Gate waere bestanden gewesen.** 0,999 gegen eine Huerde von 0,95, mit
einer Regel, die nichts Neues kann.

### Warum das nicht stimmen konnte

Die Formel von Bailey und Lopez de Prado setzt **unabhaengige** Beobachtungen
voraus. Das Gate zaehlte rohe Trades. Nachgemessen an den Fenstergewinnen:

    BTC@0,7 / BTC@1,0    Korrelation 0,069
    BTC@1,0 / BTC@1,3    Korrelation 0,007
    ETH@0,7 / ETH@1,0    Korrelation 0,884
    ETH@0,7 / ETH@1,3    Korrelation 0,585

Auf BTC liefern verschiedene Perioden tatsaechlich verschiedene Trades. Auf ETH
sind es fast dieselben. Damit liesse sich das haerteste Gate des Systems
umgehen, ohne die Strategie zu verbessern: Position dritteln, dreimal zaehlen.
Wer die Perioden enger waehlt (0,9 / 1,0 / 1,1), treibt die Zahl weiter hoch und
den Informationsgehalt gegen null.

Ich habe es nicht ausgenutzt, sondern geschlossen
(``research/unabhaengigkeit.py``).

### Die Korrektur wurde gemessen, nicht behauptet

Zuerst stand dort eine Formel: Bei ``k`` Beinen mit Korrelation ``rho``
entsprechen sie ``k / (1 + (k-1) * rho)`` unabhaengigen. Eine Formel ist aber
eine Annahme, und diese Korrektur aendert **jede Zahl im Projekt**. Also
gegengemessen mit einem Block-Bootstrap ueber die Fenster - der setzt nichts
voraus:

    Streuung des Mittelwerts, Trades einzeln gezogen:  1,1118
    Streuung des Mittelwerts, Fenster gezogen:         1,2782
    effektive Stichprobe (Bootstrap):  117 von 154  (76 %)
    effektive Stichprobe (Formel):     107 von 154  (69 %)

Beide nah beieinander, die Formel leicht konservativer. Das Gate benutzt jetzt
den **Bootstrap**, wo Fensterdaten vorliegen, und faellt sonst auf die Formel
zurueck. Negative Korrelation gibt keinen Bonus - die Korrektur darf nur
strenger machen, nie milder.

### Was das kostet - und es ist viel

    Kandidat, roher Trade-Zaehlung       DSR 0,802
    Kandidat, effektive Stichprobe       DSR 0,534

**Der Deflated Sharpe des Spitzenkandidaten war die ganze Zeit ueberschaetzt.**
Nicht weil jemand getrickst haette, sondern weil 154 Trades auf zwei Maerkten,
die mit 0,440 gleichlaufen, keine 154 unabhaengigen Belege sind.

Der Abstand zum Gate ist damit deutlich groesser als die "53 fehlenden Trades"
aus Abschnitt vierzehn.

> **Nachtrag vom Folgetag: Dieser Absatz war falsch.** Die Kuerzung auf 0,534
> hielt der Gegenprobe nicht stand - siehe Abschnitt achtzehn. Der Wert des
> Kandidaten steht wieder bei 0,802, und die 53 fehlenden Trades gelten.

### Und das Ensemble? Widerlegt, dreifach

    fensterweise      12 Fenster besser, 19 schlechter, Vorzeichentest p = 0,925
    Rendite           11,28 % -> 8,86 %, die Messlatte rueckt weiter weg
    Gates             8 von 11 -> 7 von 11 (Regime-Aufteilung faellt zusaetzlich)
    DSR korrigiert    0,566 statt 0,999

Neunte gemessene und widerlegte Richtung. Versuchszaehler: **96**.

### Was bleibt

Ein Gate, das sich nicht mehr durch Zerlegen einer Position ueberlisten laesst
- und eine ehrlichere Zahl fuer den Kandidaten. Beides macht die Lage
schlechter und die Messung besser. In dieser Reihenfolge gehoert es berichtet.

## Achtzehn. Die Korrektur an der Korrektur - meine gestrige Zahl war falsch

Gestern habe ich die wichtigste Zahl des Projekts geaendert: Der Deflated
Sharpe des Spitzenkandidaten fiel von 0,802 auf 0,534, weil das Gate nicht mehr
rohe Trades zaehlte, sondern eine per Block-Bootstrap geschaetzte effektive
Stichprobe (111 von 154).

**Diese Zahl hielt der Gegenprobe nicht stand.**

Der Test, den ich haette zuerst machen muessen: dieselbe Rechnung auf Daten, bei
denen die Antwort feststeht. Also die echten Trade-Ergebnisse durchmischen -
damit ist jede Abhaengigkeit zerstoert - und in Bloecke **derselben
Groessenverteilung** legen wie die echten Fenster.

    echte Messung                     n_eff = 106 von 154
    Null, unabhaengige Werte   Mittel n_eff = 143, Spanne 78 bis 154
    Anteil der Null unter 106                  6,0 %

Zwei Dinge stehen darin. Erstens: Das Verfahren kuerzt schon **ohne jede
Abhaengigkeit** auf 93 % - allein weil die Fenster zwischen 1 und 12 Trades
enthalten. Zweitens, und schlimmer: Bei dreissig Bloecken streut der Schaetzer
so stark, dass er auf unabhaengigen Daten bis auf 78 faellt. Der beobachtete
Wert liegt im sechsten Perzentil dieser Null - **nicht von Zufall zu
unterscheiden.**

Ich hatte eine Muenze geworfen und das Ergebnis als Messung ins Gate geschrieben.

### Was jetzt dort steht

Der verrauschte Bootstrap ist raus. An seiner Stelle steht der uebliche Weg der
Stichprobentheorie - der Designeffekt ueber die Intraklassen-Korrelation, in
geschlossener Form und damit bei jedem Aufruf identisch:

    m0    = (N - sum(n_i^2)/N) / (k-1)
    ICC   = (MSB - MSW) / (MSB + (m0-1) * MSW)
    deff  = 1 + (N/k - 1) * ICC

Und davor die Regel, die gestern fehlte: **Gekuerzt wird nur bei nachgewiesener
Abhaengigkeit.** Der Designeffekt wird gegen dieselbe Permutationsnull
gehalten; erst wenn hoechstens 5 % der Ziehungen mindestens so abhaengig
aussehen, greift die Korrektur - und dann gegen den Median der Null kalibriert,
damit der Anteil aus den ungleichen Blockgroessen herausfaellt.

Das Ergebnis trennt genau die beiden Faelle, um die es geht:

    Kandidat (2 Maerkte, 154 Trades)   ICC 0,111, p = 0,06   keine Kuerzung
    Ensemble (6 Beine, 481 Trades)     deutlich, p < 0,05    Kuerzung greift

    Kandidat   DSR 0,802  (gestern faelschlich 0,534)
    Ensemble   DSR 0,626  (roh gezaehlt waeren es 0,999)

Das Loch ist geschlossen, wo es echt ist. Der Kandidat wird nicht mehr fuer
Rauschen bestraft. **Die 53 fehlenden Trades aus Abschnitt vierzehn gelten
wieder.**

### Ein zweiter Fehler, den ein Test aufgedeckt hat

Die Funktion ersetzte die Trade-Zahl durch die **Summe der Bloecke**. Decken die
Bloecke nur einen Teil der Trades ab - etwa weil ein Trade ausserhalb aller
Fenster liegt -, schoebe das still eine ganz andere Stichprobengroesse ins
Gate. Uebernommen wird jetzt der Faktor, nicht die Summe.

### Was ich daraus mitnehme

Die Regel gegen Ueberanpassung gilt auch fuer die Werkzeuge, die vor
Ueberanpassung schuetzen sollen. Ein Schaetzer, der ueber Zulassung
mitentscheidet, gehoert gegen eine bekannte Null gehalten, **bevor** er
eingebaut wird - nicht am Tag danach.

Dass die Korrektur in die mildere Richtung geht, aendert daran nichts. Eine
Strafe, die reines Rauschen in sechs von hundert Faellen erzeugt, ist keine
Strenge, sondern eine Muenze; wer sie einbaut, misst nicht mehr die Strategie.

Versuchszaehler unveraendert bei **96** - geprueft wurde ein Werkzeug, keine
Regel.

## Neunzehn. Die Frage unter allen anderen: Erzeugt die Maschine selbst den Vorteil?

Neun Richtungen sind gemessen und widerlegt, der Deflated Sharpe haengt bei
0,80, und **alle diese Zahlen kommen aus derselben Zulassungsstrecke**. Wenn
die selbst einen Vorteil erzeugt - durch Lookahead, durch einen Fehler in der
Fensterlogik, durch eine Kerze zu frueh -, ist jede Messung der letzten Wochen
wertlos. Und zwar ohne dass irgendetwas nach einem Fehler aussieht.

Diese Frage war nie beantwortet. Es gab einen Test, der prueft, dass die
**Gates** auf einem Zufallspfad niemanden zulassen - aber keinen, der prueft,
ob der **Walk-Forward** auf strukturlosen Daten einen Ertrag ausweist. Das sind
zwei verschiedene Dinge: Ein Lookahead koennte einen fetten Ertrag erzeugen,
den die Gates aus einem ganz anderen Grund ablehnen. Der Test bliebe gruen.

### Das Verfahren: Renditen mischen

Aus den echten Tagesrenditen wird eine neue Preisreihe gebaut, in der die
Reihenfolge zerstoert ist. Erhalten bleibt alles, was nichts mit
Vorhersagbarkeit zu tun hat - Verteilung, Schwankungsbreite, Groessenordnung,
sogar der Drift. Weg ist jede Struktur, auf die eine Trendfolge angewiesen ist.

Auf so einer Reihe **muss** eine Trendfolge verlieren. Tut sie es nicht, liegt
es an der Maschine. Kostet keinen Versuch: Geprueft wird die Maschine, keine
Regel.

### Das Ergebnis

    echte Reihe                154 Trades,  +160,7 % Ertrag
    40 gemischte Reihen        158 Trades im Mittel
                               Ertrag im Median -22,0 %
                               Spanne -43,6 % bis +14,2 %
    gemischte Laeufe mindestens so gut wie die echte:  0 von 40

Beide noetigen Antworten sind da:

* **Die Maschine ist sauber.** Auf strukturlosen Daten verliert die Strategie
  im Median 22 % - genau das, was eine Trendfolge ohne Trend tun muss: Stops
  bezahlen und Gebuehren. Es gibt keinen Lookahead, der aus dem Nichts Ertrag
  macht.
* **Die echte Reihe hebt sich ab.** Kein einziger von vierzig Zufallslaeufen
  kommt an +160,7 % heran, bei praktisch identischer Trade-Zahl (154 gegen 158
  im Mittel). Der Unterschied kommt also nicht daher, dass mehr oder weniger
  gehandelt wird, sondern **wann**.

Das ist die erste Aussage ueber den Vorteil, die **ohne die
Deflated-Sharpe-Formel** auskommt - kein E[maxSR], keine Schiefekorrektur,
keine Versuchszahl. Nur: Was die Strategie auf echten Daten leistet, leistet
sie auf gemischten nicht.

### Und wieder ein Fehler in meiner eigenen Kennzahl

Der erste Anlauf verglich nicht den Ertrag, sondern den **Abstand zu
Kaufen-und-Halten** - und meldete prompt einen Maschinenfehler:

    WARNUNG: Auf strukturlosen Daten entsteht im Mittel ein Vorteil.

Falscher Alarm, und die Ursache ist eine Eigenschaft, die ich haette kennen
muessen: **Das Mischen erhaelt die Gesamtrendite exakt.** Das Produkt der
Renditen haengt nicht von ihrer Reihenfolge ab. Kaufen-und-Halten betraegt auf
jeder gemischten Reihe dieselben +945,8 % - eine Konstante, keine Verteilung.
Ein Abstand dazu misst nur noch, wie viel Zeit die Strategie im Markt
verbringt, und ist als Vergleichsgroesse wertlos.

Das ist innerhalb von drei Tagen der dritte Fall, in dem eine Kennzahl von mir
selbst das Falsche gemessen hat - nach dem Bootstrap-Rauschen und der
Blocksummen-Verwechslung. Alle drei fielen auf, weil die Zahl gegen etwas
gehalten wurde, dessen Antwort feststand. Ohne diese Gegenproben waeren alle
drei durchgegangen.

Die Eigenschaft steht jetzt als Test fest
(``test_mischen_erhaelt_die_gesamtrendite``), damit sie niemandem noch einmal
als Vergleichsgroesse durchgeht.

### Was das aendert

Am Stand nichts: weiterhin **8 von 11**, weiterhin 53 fehlende Trades. Was sich
aendert, ist das Vertrauen in alles Vorherige. Die neun widerlegten Richtungen
sind widerlegt, nicht wegdefiniert; die 11,28 % im Jahr sind gemessen, nicht
erzeugt. Das war bis heute nicht belegt.

Zu pruefen mit ``cli nullprobe``. Versuchszaehler unveraendert bei **96**.

## Zwanzig. Die 500 Euro sind das Nadeloehr - nicht die Strategie

Eine Frage war nie gestellt worden: **Sind die 154 Trades auf einem echten
500-Euro-Konto ueberhaupt handelbar?**

Der Portfoliolauf rechnet jedes Bein mit dem **vollen** Startkapital und
gewichtet erst das Ergebnis. Fuer Gewinne ist das richtig - sie kuerzen sich
heraus. Fuer die **Mindestmenge der Boerse** ist es falsch, denn die laesst
sich nicht halbieren. Ein echtes Konto mit 500 Euro auf zwei Maerkten hat je
Markt 250, und Bybits Mindestmenge von 0,001 BTC entspricht bei 100.000 Dollar
schon 100 Dollar Nominalwert.

Gemessen, gemeinsamer Zeitraum, durch den Produktivpfad
(``kapital_teilen=True``):

    Lauf                      Trades  auf Minimum   p.a.      DD      DSR
    je Bein 500 EUR (bisher)     154       49      11,28 %  9,74 %   0,801
    je Bein 250 EUR (echt)       136       70      10,33 %  7,88 %   0,770

**18 Trades fallen ganz weg** - die Boerse laesst sie nicht zu. Von den
verbleibenden 136 laufen **70, also die Haelfte, auf der Mindestmenge**: Die
Groessenlogik wollte weniger, kleiner geht es nicht. Dort ist das Risiko je
Trade nicht mehr steuerbar, sondern von der Boerse vorgegeben.

Die Kennzahl bestaetigt sich auf zwei unabhaengigen Wegen: einmal ueber den
Portfoliopfad (10,33 %), einmal ueber zwei getrennt gerechnete Beine, deren
Kurven addiert werden (10,11 %). Der Unterschied ist gemeinsames gegen
getrenntes Aufzinsen.

### Ab wann verschwindet die Beschraenkung?

    Startkapital   je Markt   Trades   auf Minimum   Anteil    p.a.
        500 EUR     250 EUR      136        70        51 %   10,33 %
       1000 EUR     500 EUR      154        49        32 %   11,28 %
       2000 EUR    1000 EUR      152         7         5 %   11,33 %
       5000 EUR    2500 EUR      152         0         0 %   11,48 %
      10000 EUR    5000 EUR      152         0         0 %   11,56 %

Ab rund **2000 Euro** ist die Mindestmenge praktisch kein Thema mehr, und die
Rendite laeuft in ihre Saettigung. Zwischen 2000 und 10000 Euro liegen noch
0,23 Prozentpunkte - das ist Rauschen.

### Was daran wichtig ist

**Das ist kein Strategieproblem, sondern ein Kontogroessenproblem.** Die Regel
ist dieselbe; sie laesst sich mit 500 Euro nur nicht sauber ausdruecken. Der
Unterschied von 11,28 % zu 10,33 % ist nicht der Preis einer schlechteren
Strategie, sondern der Preis der Stueckelung.

Und er faellt nicht dorthin, wo man ihn erwartet: Der **Rueckgang** wird sogar
besser (9,74 % auf 7,88 %), weil die erzwungen kleineren Positionen weniger
Schaden anrichten. Was schlechter wird, ist die Zahl der Trades - und damit
ausgerechnet das, woran das Deflated-Sharpe-Gate haengt (0,801 auf 0,770).

**Der Vorgabewert bleibt unveraendert.** ``kapital_teilen`` ist ein Schalter,
kein neuer Standard. Zwei Gruende: Die Gates sollen die **Strategie** messen,
nicht die Kontogroesse - und die Kontogroesse ist eine Entscheidung des
Nutzers, keine Messgroesse. Was ihm zusteht, ist die Zahl, nicht meine
Auslegung davon.

Am Stand aendert sich nichts: **8 von 11** in beiden Faellen, dieselben drei
offenen Gates. Versuchszaehler unveraendert bei **96** - gemessen wurde
dieselbe Regel unter ehrlicheren Annahmen, keine neue.

### Eine Entscheidung, die beim Nutzer liegt

Zu den 15 % Mindestrendite kommt damit eine zweite Zahl auf den Tisch: **Mit
500 Euro laeuft die Haelfte aller Trades auf einer Groesse, die nicht die
Strategie gewaehlt hat, sondern die Boerse.** Wer das nicht will, braucht rund
2000 Euro - oder muss akzeptieren, dass die Risikosteuerung bei der Haelfte der
Trades nicht greift.

Beides ist vertretbar. Nur unbemerkt bleiben darf es nicht.

---

## Einundzwanzig. Der letzte freie Regler enthaelt keine Loesung

Nach zwanzig gemessenen und widerlegten Richtungen hatte der Spitzenkandidat
noch genau eine freie Stellschraube: das **Vola-Ziel**. Statt weiter daran zu
drehen, ist diesmal die Frage eine Stufe darueber gestellt worden - und sie ist
billiger zu beantworten als jede einzelne Drehung:

> **Gibt es ueberhaupt eine Stellung, bei der alle elf Gates zugleich halten?**

Gemessen wurde in einem Zug: sieben Stellungen von 14 bis 32 %, je mit
**vollstaendiger** Gate-Auswertung. BTC + ETH, Tageskerzen, Walk-Forward, nach
Gebuehren, Risikolimits scharf, Terminkalender aktiv.

    Vola-Ziel                 14      16    19.3      22      25      28      32
    ----------------------------------------------------------------------------
    Stichprobengroesse         +       +       +       +       +       +       +
    Messlatte                  -       -       -       -       +       +       +
    Out-of-Sample-Sharpe       +       +       +       +       +       +       +
    Drawdown                   +       +       +       +       -       -       -
    Schlechtestes Jahr         +       +       +       -       -       -       -
    Bestaendigkeit             +       +       +       +       +       +       +
    Monte-Carlo                +       +       +       +       +       +       -
    Regime-Aufteilung          +       +       +       +       +       +       +
    Deflated Sharpe            -       -       -       -       -       -       -
    Kosten-Stress              +       +       +       +       +       +       -
    Parameter-Plateau          -       -       -       -       -       -       -
    ----------------------------------------------------------------------------
    bestanden               8/11    8/11    8/11    7/11    7/11    7/11    5/11

**Die Antwort ist nein, und zwar aus zwei voneinander unabhaengigen Gruenden.**

### Grund eins: Der Deflated Sharpe folgt dem Regler nicht

    Vola-Ziel    14     16    19.3     22     25     28     32
    DSR       0,767  0,783  0,791  0,780  0,784  0,771  0,791

Ueber den ganzen Regelweg - Rendite von 9,1 auf 21,7 % p.a., Rueckgang von 6,7
auf 17,1 % - bewegt sich der Deflated Sharpe um **0,024**. Zur Schwelle von
0,95 fehlen an der besten Stelle **0,159**.

Das ist keine knappe Sache, sondern eine Schranke: Der Regler muesste den Wert
siebenmal weiter bewegen, als er ihn ueberhaupt bewegt. Feiner abzutasten
aendert daran nichts - und wuerde die Lage sogar verschlechtern, weil jede
zusaetzliche Stufe als Versuch zaehlt und die Huerde weiter hebt.

Der Grund dahinter ist einfach, sobald man ihn sieht: Das Vola-Ziel skaliert
**jede** Position mit demselben Faktor. Rendite und Schwankung wachsen
gemeinsam, das Verhaeltnis bleibt. Ein Hebel veraendert nicht, wie gut die
Regel den Markt trifft.

### Grund zwei: Rendite und Rueckgang schliessen sich hier aus

Selbst wenn der Deflated Sharpe nicht im Weg staende, ist das Fenster leer:

    Gate                  haelt bei        Grenze
    Schlechtestes Jahr    bis 19,3         -9,41 % bei 19,3, -11,45 % bei 22
    Drawdown              bis 22           11,83 % bei 22, 12,93 % bei 25
    Messlatte             ab 25            14,52 % p.a. bei 22, 16,77 % bei 25

Die Messlatte verlangt nach oben, die beiden Rueckgangs-Gates nach unten. Es
gibt keine Stellung dazwischen, die beides erfuellt.

### Wobei die Messlatte durchfaellt - und wobei nicht

Das ist der Punkt, an dem ich beim ersten Durchgang zu schnell war. Die
Messlatte prueft **zwei** Bedingungen, und die Zeichen in der Tabelle sagen
nicht, welche gerissen ist. Nachgemessen:

    Vola-Ziel   Ertrag   Messlatte   risikobereinigt   p.a.    >= 15 %
        14       95,8       25,4            ja        9,06 %    nein
      19,3      160,7       39,3            ja       13,17 %    nein
        22      185,8       49,6            ja       14,52 %    nein
        25      232,2       55,3            ja       16,77 %      ja

**Risikobereinigt schlaegt die Strategie das Halten an jeder einzelnen
Stellung** - um das Drei- bis Vierfache. Durchgefallen ist die Messlatte
ausschliesslich an der zweiten Bedingung: den **15 % Mindestrendite**.

Und die sind, wie in ``gates.py`` seit jeher vermerkt, **kein statistisches
Kriterium, sondern eine wirtschaftliche Entscheidung**. Der gemessene Konflikt
lautet damit genauer:

> 15 % Mindestrendite gegen 12 % Rueckgangsgrenze und -10 % schlechtestes Jahr.

Drei Zahlen, die ein Mensch gesetzt hat, und die zusammen kein Fenster lassen.
Das ist etwas grundlegend anderes als eine Strategie, die nicht funktioniert -
und es gehoert dem Nutzer auf den Tisch, nicht in eine stille Anpassung.

**Gelockert wird nichts.** Das bleibt die Regel. Aber wer eine Schwelle setzt,
soll wissen, was sie ausschliesst.

### Das Parameter-Plateau wird nach oben schlechter, nicht besser

    Vola-Ziel      14     16   19.3     22     25     28     32
    Plateau      0,50   0,50   0,50   0,50   0,00   0,00   0,00
                 (Schwelle 0,60 - also muessen beide Nachbarn halten)

Von den zwei geprueften Nachbarn haelt unten einer, oben keiner. Auch dieses
Gate laesst sich mit dem Regler nicht einsammeln; es bewegt sich, aber in die
falsche Richtung.

### Was gemessen ist und was nicht

Eine Abtastung misst Punkte, keine Strecken. Zwischen 22 und 25 liegt ein
ungeprueftes Stueck von 3 Prozentpunkten, in dem theoretisch ein schmales
Fenster fuer Rendite und Drawdown stecken koennte - fuer das schlechteste Jahr
nicht, das ist bei 22 bereits mit -11,45 % gerissen.

**Gemessen wird es trotzdem nicht,** und das ist eine bewusste Entscheidung:
Der Deflated Sharpe ist nachweislich ausser Reichweite, ein Fenster kann es
also ohnehin nicht geben. Zwei weitere Stufen zu rechnen kostete zwei Versuche
und haette die Huerde fuer alles Kuenftige gehoben, ohne die Antwort zu
aendern. Das Werkzeug sagt das von sich aus - siehe unten.

### Das Werkzeug: ``cli machbarkeit``

Der Befund ist nicht als Notiz abgelegt, sondern als pruefbares Werkzeug
(``research/machbarkeit.py``). Es unterscheidet drei Ausgaenge, die sehr
verschieden viel bedeuten:

* **Fenster** - es gibt Stellungen, an denen alles haelt.
* **Konflikt** - jedes Gate haelt irgendwo, nie zwei zugleich. Das ist ein
  Beweis, dass diese Achse keine Loesung enthaelt, kein "knapp daneben".
* **Ausser Reichweite** - ein Gate haelt nirgends, und die Spanne, ueber die
  der Regler es bewegt, ist kleiner als der Abstand zur Schwelle.

Dazu die Ehrlichkeitsschranke: Das Urteil nennt die ungeprueften
Zwischenraeume und die Stellungen, mit denen man sie schliesst - und es sagt
"feiner messen hilft nicht", wenn eine harte Schranke die Frage bereits
entschieden hat. Ein "nicht machbar" traegt genau so weit, wie die Aufloesung
reicht, und die Aufloesung steht im Urteil.

**Ein Fehler im ersten Bericht, gleich mitkorrigiert:** ``Stichprobengroesse``
wurde als "ausser Reichweite" ausgewiesen - ein Gate, das an jeder Stellung mit
grossem Abstand bestand. Die Bedingung ``Spanne < Abstand`` allein unterscheidet
nicht, auf welcher Seite der Schwelle man steht. Wer irgendwo haelt, ist nie
ausser Reichweite; der Test dazu haelt es fest.

### Was daraus folgt

Der Spitzenkandidat ist nicht "nah dran". Er ist auf seiner einzigen freien
Achse **nachweislich nicht zulassungsfaehig**, und zwar doppelt abgesichert.
Damit ist auch die einundzwanzigste Richtung geschlossen - die letzte, die sich
ohne neue Regel haette gehen lassen.

Was bleibt, ist keine Stellschraube, sondern eine andere Regel: eine, die den
Sharpe je Trade hebt statt die Positionsgroesse. Der Regler war die billige
Hoffnung, und sie ist jetzt ausgeraeumt statt weiter mitgeschleppt.

Versuchszaehler **96 -> 102** (sechs neue Stellungen; 19,3 war bereits
gezaehlt). Die zweite Messung derselben sieben Stufen zaehlt nicht mit - es
wurde nichts Neues gesehen, nur festgehalten, was hinter den Zeichen stand
(``reports/machbarkeit/``).

---

## Zweiundzwanzig. Ein Sechstel der Trades wurde vom Kalender beendet

Der Befund davor sagte: Was fehlt, ist Qualitaet je Trade, und kein Regler
liefert sie. Auf der Suche danach habe ich zuerst nachgesehen, wo der
Sharpe je Trade eigentlich herkommt - und bin auf einen Fehler in der
**Messung** gestossen, nicht in der Strategie.

### Der Befund

Der Backtest lief in jedem Walk-Forward-Fenster exakt bis zum Fensterende.
Eine dort noch offene Position wurde zwangsweise glattgestellt
(``END_OF_DATA``). Aufgeschluesselt nach Ausstiegsgrund:

    Grund             Trades   Anteil   Ergebnis im Mittel   Haltedauer
    stop_loss             67    43,5 %        -2,11 EUR         6 Tage
    signal_exit           58    37,7 %        -0,59 EUR         6 Tage
    end_of_data           25    16,2 %       +19,62 EUR        26 Tage
    take_profit            4     2,6 %       +50,56 EUR

**Die 25 kalenderbeendeten Trades trugen den gesamten Vorteil.** Ohne sie
faellt der Sharpe je Trade von 0,244 auf **0,021** - die Strategie waere
nichts weiter als Rauschen.

Damit wurde zu einem Sechstel der Kalender gemessen, und zwar genau an der
Stelle, an der eine Trendfolge ihr Geld verdient: beim Ausstieg aus den
Gewinnern. Im Betrieb gibt es keinen Kalender, der eine Position schliesst.

### Die Korrektur

Jedes Fenster bekommt einen **Nachlauf**: Der Backtest laeuft ueber das
Fensterende hinaus, bis die im Fenster eroeffneten Trades ihren Ausstieg
**nach Regel** gefunden haben. Gezaehlt werden weiterhin nur Trades, die im
Testfenster eroeffnet wurden.

Wie lang der Nachlauf sein muss, ist gemessen und nicht gewaehlt:

    Nachlauf     Trades   SR/Trade   Ergebnis   am Kalender beendet
         0 Tage     154     0,2444    1034 EUR    25 (16,2 %)
        30 Tage     154     0,2495    1232 EUR    12 ( 7,8 %)
        90 Tage     154     0,2584    1388 EUR     0 ( 0,0 %)
       180 Tage     154     0,2584    1388 EUR     0 ( 0,0 %)
       365 Tage     154     0,2584    1388 EUR     0 ( 0,0 %)

Ab einer Testfensterlaenge aendert sich **nichts mehr** - die Signatur einer
Groesse, die lang genug ist. Gebunden wird der Nachlauf deshalb an die
Fensterlaenge, nicht an feste Tage: Auf 15-Minuten-Kerzen waeren drei Monate
je Fenster ein Vielfaches der Testdaten selbst.

Und die Trade-Zahl bleibt ueber den ganzen Bereich bei 154. Das ist kein
Nebenbefund, sondern der Beleg, dass hier nicht in die Zukunft gesehen wird:
**Der Nachlauf verschiebt keinen einzigen Einstieg.** Er liegt hinter dem
Testfenster, also erst recht hinter dem Training, und die Regel entscheidet
auf jeder Kerze ohnehin nur aus der Vergangenheit. Ein Test haelt das fest.

### Was sich dadurch aendert

    Kennzahl                      vorher     nachher
    Sharpe je Trade                0,244       0,258
    Deflated Sharpe                0,791       0,869
    fehlende Trades zum Gate          56          32
    noetiger Faktor auf SR/Trade    1,14        1,08
    Jahresrendite                 13,17 %     13,17 %
    Rueckgang                      9,74 %      9,74 %
    Gates                           8/11        8/11

Der Abstand zum haertesten Gate hat sich **halbiert**. Rendite und Rueckgang
bleiben unveraendert, und das ist beabsichtigt: Die Kapitalkurve bleibt auf
das Fenster begrenzt. Sonst ueberlappten sich die Kurven benachbarter Fenster,
und die Verkettung zaehlte dieselbe Bewegung zweimal. Am Fensterende steht dort
weiterhin der Marktwert einer womoeglich offenen Position - genau das, was ein
Kontoauszug an dem Tag zeigte.

### Der Interessenkonflikt, ausgesprochen

**Diese Korrektur macht den Kandidaten besser, und ich habe sie gefunden,
waehrend ich nach etwas suchte, das ihn besser macht.** Das ist genau die Lage,
in der man sich selbst nicht glauben soll. Deshalb steht sie hier mit allem,
was gegen sie sprechen koennte:

* Sie wurde nicht behauptet, sondern durchgerechnet - fuenf Nachlauflaengen,
  mit Konvergenz.
* Sie aendert keinen Einstieg. Wenn sie es taete, waere sie ein Blick nach
  vorn; ein Test vergleicht alle Einstiegszeitpunkte und -preise.
* Sie kostet **keinen Versuch**. Es ist dieselbe Regel auf denselben Daten,
  nur ohne den Messfehler. Der Zaehler bleibt bei 102.
* Ein Umkehr-Nachweis faellt um, sobald jemand den Nachlauf wieder entfernt.

Und die unangenehme Seite gleich dazu: Dass ein Sechstel der Trades vom
Kalender beendet wurde, stand seit dem ersten Walk-Forward in den Daten. Es ist
niemandem aufgefallen, mir am wenigsten - in **zweiundzwanzig** Untersuchungen
nicht, von denen mehrere den Sharpe je Trade zum Gegenstand hatten. Gefunden
wurde es erst, als ich die Ausstiegsgruende einzeln ausgezaehlt habe.

Damit das nicht wieder passiert, zaehlt der Bericht die kalenderbeendeten
Trades ab jetzt selbst und nennt sie in seiner Zusammenfassung. Eine Annahme
haette genau den Fehler wieder eingebaut, den der Nachlauf behebt.

### Was das nicht loest

**8 von 11 bleiben 8 von 11.** Offen sind dieselben drei: Messlatte, Deflated
Sharpe, Parameter-Plateau. Der Deflated Sharpe ist von 0,791 auf 0,869
gestiegen und braucht 0,95 - es fehlen jetzt 32 Trades statt 56, oder 8 %
mehr Qualitaet je Trade statt 14 %.

Naeher, aber nicht da. Und der Befund davor gilt unveraendert: Der Vola-Regler
liefert diese 8 % nicht.

### Eine zweite Korrektur an meinem eigenen Werkzeug

Beim Nachmessen mit einer einzigen Reglerstellung meldete ``cli machbarkeit``
prompt drei Gates als "ausser Reichweite des Reglers". Bei einem Messpunkt ist
die Spanne aber null, und damit ist die Bedingung ``Spanne < Abstand``
automatisch erfuellt - eine Aussage ueber einen Regler, an dem nie gedreht
wurde. Das Werkzeug verlangt jetzt mindestens zwei Stellungen, bevor es eine
Schranke behauptet.

Zwei falsche Berichte aus demselben Werkzeug in zwei Tagen. Beide sind es wert,
festgehalten zu werden: Ein Werkzeug, das Schranken ableitet, muss zuerst
wissen, wann seine Datenlage fuer eine Schranke nicht reicht.

### Und ein zweiter Fehler, den erst die Korrektur sichtbar gemacht hat

Nach dem Nachlauf habe ich den Vola-Regler neu vermessen - und das Werkzeug
widersprach dem Befund von gestern: Der Deflated Sharpe sei **nicht** ausser
Reichweite. Die Spanne, ueber die der Regler ihn bewegt, war ploetzlich 0,343
statt 0,024.

Der Grund stand in einer einzigen Zeile:

    Vola-Ziel      14     16    19.3     22     25     28     32
    DSR         0,863  0,528  0,869  0,863  0,870  0,860  0,871

Ein Ausreisser bei 16, und die ganze Schranke haengt daran. Nachgemessen, wo er
herkommt - die Trade-Verteilungen sind an allen Stufen praktisch gleich
(Sharpe je Trade 0,258 bis 0,263, Schiefe 3,5, Woelbung 17). Der Sprung kam
nicht von den Trades, sondern aus der **Effektivstichprobe**:

    Vola-Ziel    ICC       p     Stichprobe
         14    0,123   0,085     148 (ungekuerzt)
         16    0,128   0,030     153 -> 100   <- gekuerzt
       19,3    0,121   0,060     154 (ungekuerzt)
         22    0,124   0,075     152 (ungekuerzt)

**Die Abhaengigkeit selbst ist ueber den ganzen Regler konstant** - der ICC
schwankt um 0,008. Nur der p-Wert des Permutationstests wandert, und bei einer
Stufe faellt er unter 0,05. Dort wird die Stichprobe um ein Drittel gekuerzt
und der Deflated Sharpe stuerzt von 0,87 auf 0,53.

Bei 200 Permutationen betraegt der Standardfehler des p-Werts nahe 5 % rund
0,015 - die Schwelle liegt innerhalb eines einzigen davon. Die Entscheidung
war ein **Muenzwurf**. Mit 2000 Ziehungen:

    Vola-Ziel     14     16    19.3     22     25     28     32
    p          0,065  0,051  0,066  0,058  0,065  0,059  0,061

Der Ausreisser ist weg, alle Stufen bleiben ungekuerzt, und die Spanne des
Reglers faellt auf 0,011. **Der Befund von gestern steht damit wieder - jetzt
auf Zahlen ohne Rauschen.**

### Die unangenehme Zahl daran

Alle sieben p-Werte liegen zwischen 0,051 und 0,066. **Jeder einzelne liegt
dicht an der Schwelle.** Der Deflated Sharpe von 0,869 beruht also auf einer
Entscheidung - die Stichprobe nicht zu kuerzen -, die um Haaresbreite anders
ausfallen koennte. Bei Vola-Ziel 16 steht sie auf 0,051.

Das ist keine Zahl, die man wegdiskutiert, und sie wird auch nicht in die eine
oder andere Richtung gedreht. Sie wird **angesagt**: ``Effektivwert.knapp``
meldet jede Entscheidung im Bereich 0,025 bis 0,10 als das, was sie ist, und
``cli abstand`` zeigt den Hinweis jetzt auch dann, wenn **nicht** gekuerzt
wurde. Vorher lief es genau andersherum - gemeldet wurde nur die vollzogene
Kuerzung, also alles ausser dem Fall, in dem die Zahl am wenigsten belastbar
ist.

Damit ist dies die **dritte** Schwaeche in ``research/unabhaengigkeit.py``,
nach dem zu verrauschten Block-Bootstrap und der vertauschten Blocksumme. Alle
drei hatten dieselbe Form: eine Zahl, die entschieden hat, ohne dass ihre
eigene Unsicherheit mitgerechnet wurde. Was bleibt, ist eine harte Schwelle auf
einer stetigen Groesse - eine Klippe, die reproduzierbar geworden ist, aber
keine Klippe weniger. Eine stetige Kuerzung waere der richtige Weg; sie gehoert
gebaut, wenn sie durchgerechnet ist, nicht wenn sie plausibel klingt.

### Stand nach beiden Korrekturen

    Vola-Ziel  Trades     p.a.       DD     DSR   Gates
        14       148    9,06 %   6,67 %   0,863    8/11
        16       153   10,59 %   7,17 %   0,868    8/11
      19,3       154   13,17 %   9,74 %   0,869    8/11   <- Kandidat
        22       152   14,52 %  11,83 %   0,863    7/11
        25       152   16,77 %  12,93 %   0,870    7/11
        28       152   18,51 %  15,02 %   0,860    7/11
        32       152   21,70 %  17,06 %   0,871    5/11

Versuchszaehler unveraendert bei **102**: Beide Korrekturen sind Fehlerbehebung
an der Messung, keine neuen Einfaelle. Es ist dieselbe Regel auf denselben
Daten - nur richtig gemessen.

---

## Dreiundzwanzig. Die Konfluenz war an der Haelfte aller Testtage blind

Der Nachlauf-Befund hat gezeigt, dass am Messinstrument mehr zu holen ist als
an der Strategie. Also weiter dort gesucht - und diesmal ist der Fund
unangenehm.

### Zuerst eine widerlegte Vermutung

Verdacht war, dass ``chained_curve`` die Aufwaermphase mitzaehlt, waehrend
``_combine`` sie abschneidet - zwei Funktionen, dieselbe Kurve, verschiedene
Grenzen. Gemessen: **2830 von 2830 Punkten liegen im Testfenster, 100 %.** Die
Engine schreibt die Kapitalkurve erst ab dem ersten handelbaren Balken. Kein
Fehler. Zwei Minuten, sauber widerlegt.

### Der eigentliche Fund

``_estimate_warmup`` im Compiler leitet die Aufwaermphase aus den verwendeten
Indikatorperioden ab. Sie sah an:

    filters, entry_long, entry_short

Nicht angesehen hat sie ``konfluenz`` - und die kam erst spaeter dazu. Beim
Spitzenkandidaten steht der laengste Indikator genau dort:

    entry_long    sma(50)     gezaehlt
    exit_long     sma(50)     nicht gezaehlt
    konfluenz     sma(200)    nicht gezaehlt
    konfluenz     roc(90)     nicht gezaehlt

Ergebnis: 150 Kerzen Vorlauf, gebraucht wurden 200. Der sma(200) war damit an
**56,2 % aller Testtage undefiniert** - in jedem einzelnen Fenster die ersten
50 von 89 Tagen. Der Compiler wertet ``nan`` sicherheitshalber als "Bedingung
nicht erfuellt", also galt ``sma50 > sma200`` dort still als falsch, und die
Konviktion dimensionierte jede Position kleiner, als die Regel es verlangt.

Der Docstring dieser Funktion warnt woertlich vor genau diesem Fall: "Zu kurz
angesetzt entscheidet die Strategie auf nan-Werten ... und im Walk-Forward, wo
jedes Fenster neu anfaengt, faellt das nicht auf." Er hat recht behalten, an
sich selbst.

### Die Korrektur, und warum sie den Zuschlag differenziert

Gezaehlt werden jetzt alle Bedingungen, auch Konfluenz und Ausstieg. Dazu ein
zweiter Punkt, der aus der Mathematik kommt und nicht aus der Bequemlichkeit:

    rolling(period, min_periods=period)   nach period Kerzen exakt
    ewm(adjust=False)                     traegt den Startwert unbegrenzt mit

Der pauschale Zuschlag von 3x war fuer die zweite Gruppe gedacht - EMA, RSI,
ATR, ADX. Auf einen gleitenden Durchschnitt angewandt verlangte er 600 Kerzen
fuer einen sma(200): mehr, als vor dem ersten Testfenster ueberhaupt vorhanden
sind. Der Zuschlag gilt jetzt nur noch fuer die rekursiven Glaettungen.

Nach der Korrektur: **0,0 % blinde Testtage.**

### Was das kostet - und es kostet

    Kennzahl                vorher     nachher
    Trades                     154         152
    Jahresrendite          13,17 %     13,47 %
    Rueckgang               9,74 %     10,64 %
    Schlechtestes Jahr      -9,41 %    -10,32 %   <- Schwelle -10 %
    Deflated Sharpe          0,869       0,863
    Gates                     8/11        7/11

**Der Kandidat faellt von 8 auf 7 von 11.** Die Konfluenz feuert jetzt
richtig, die Konviktion vergroessert die Positionen bei steigendem
Langfristtrend - das bringt Rendite (13,17 auf 13,47 %) und kostet Rueckgang
(9,74 auf 10,64 %). Das schlechteste Jahr reisst mit -10,32 % gegen -10 %.

Damit steht die unangenehme Erkenntnis: **Ein Teil der scheinbaren
Risikokontrolle des Kandidaten kam aus einem Messfehler, nicht aus der Regel.**
Er sah ruhiger aus, als er ist, weil eine kaputte Aufwaermphase seine
Positionen verkleinert hat.

### Was nicht getan wird

Bei Vola-Ziel 16 stuenden wieder 8 von 11. Die 19,3 dorthin zu senken waere
eine Anpassung an die Gates - genau die Sorte Entscheidung, gegen die die ganze
Zulassungsstrecke gebaut ist. **Der Wert bleibt, der Stand ist 7 von 11.**

Der Docstring des Kandidaten behauptete, die 19,3 sei "der Punkt, an dem
Rueckgang und schlechtestes Jahr gerade noch innerhalb der Grenzen liegen".
Das war unter dem Messfehler gewaehlt und stimmt nicht mehr; es steht jetzt
richtig dort.

### Der Regler nach der Korrektur

    Vola-Ziel  Trades     p.a.       DD    schlecht. Jahr    DSR   Gates
        14       149    9,47 %   7,75 %       -7,50 %      0,870   8/11
        16       154   10,98 %   8,46 %       -8,18 %      0,866   8/11
      19,3       152   13,47 %  10,64 %      -10,32 %      0,863   7/11  <- Kandidat
        22       152   15,16 %  12,82 %      -12,44 %      0,870   7/11
        25       152   17,23 %  14,78 %      -14,37 %      0,867   7/11
        28       152   19,05 %  16,65 %      -16,20 %      0,861   7/11
        32       152   22,30 %  18,18 %      -17,67 %      0,866   5/11

Der Befund aus Nummer einundzwanzig **haelt**, er ist nur eine Reglerstufe
nach unten gerutscht: Der Deflated Sharpe liegt ueber den ganzen Regler
zwischen 0,861 und 0,870 - eine Spanne von 0,009 bei einer Luecke von 0,080.
Ausser Reichweite. Und Messlatte gegen Rueckgangsgrenzen bleibt ein Konflikt
ohne Fenster, jetzt zwischen 16 und 22 statt zwischen 19,3 und 25.

### Bilanz der drei Messfehler

    Fund                          Wirkung auf den Kandidaten
    Nachlauf am Fensterende       DSR 0,791 -> 0,869   besser
    Aufwaermphase der Konfluenz   8/11 -> 7/11         schlechter
    verkettete Kurve              kein Fehler          --

Zwei echte Fehler in zwei Laeufen, einer zu meinen Gunsten, einer zu meinen
Ungunsten. Das ist der Grund, warum das Instrument vor der Strategie geprueft
gehoert: Beide waren seit Monaten drin, beide haben jede Zahl dieses Projekts
verschoben, und keiner von beiden war an einem auffaelligen Ergebnis zu
erkennen - nur daran, dass man nachsieht, wie die Zahlen entstehen.

Versuchszaehler unveraendert bei **102**: Fehlerbehebung an der Messung, kein
neuer Einfall.

---

## Vierundzwanzig. Der Backtest hat den Not-Aus alle drei Monate zurueckgesetzt

Der angekuendigte Umbau: ein **durchgehender** Lauf ueber die ganze
Teststrecke statt eines Backtests je Fenster. Anlass war die Messung aus
Nummer dreiundzwanzig - die Haelfte aller Fenster beginnt mitten im Trend,
flach, und wartet auf ein Kreuzen, das nicht mehr kommt (26,3 % der Testtage).

Der Umbau hat etwas ganz anderes freigelegt, und es ist der schwerste Befund
dieses Projekts.

### Die Zahlen

    Lauf            Trades   SR/Trade    p.a.       DD     DSR   Gates
    fensterweise       152     0,2597  13,47 %  10,64 %   0,863    7/11
    durchgehend         86     0,2339   8,40 %   8,24 %   0,296    7/11

**Der Deflated Sharpe faellt von 0,863 auf 0,296.** Nicht wegen des
Umbaus - sondern weil der Umbau zeigt, was ohne ihn nie sichtbar war.

### Die Ursache: der Risk-Officer wurde 31-mal neu geboren

Erste Vermutung war der Mechanismus selbst. Die Gegenprobe widerlegt sie:

    Lauf                        Trades
    fensterweise, Limits an        152
    durchgehend,  Limits an         86
    fensterweise, Limits aus       156
    durchgehend,  Limits aus       156   <- identisch

**Ohne Risikolimits liefern beide Wege exakt dieselben 156 Trades.** Der
ganze Unterschied kommt vom Risk-Officer. Und die Vetos sagen, wie gross er
ist:

    fensterweise:  trading_paused     6
    durchgehend:   trading_paused  1891

Jedes Fenster war ein eigener Backtest mit **eigenem, frischem
Risikozustand**. Verlustgrenzen, Hoechststand, Pausen - alles auf null, 31
Mal hintereinander. Der Backtest hat damit genau die Sicherung, die im
Betrieb ueber dem Konto haengt, viermal im Jahr entschaerft.

### Was durchgehend passiert

    Trades je Jahr
    fensterweise   2018: 7  2019: 20  2020: 18  2021: 21  2022: 20
                   2023: 19  2024: 22  2025: 17  2026: 8
    durchgehend    2018: 7  2019: 20  2020: 17  2021: 13  2022: 8
                   2023: 12  2024: 9   2025: 0   2026: 0

**Der Handel endet 2024 und kommt nicht wieder.** Ueber den ganzen Lauf feuert
das Wochenlimit einmal und der Kill-Switch einmal. Beide sind so gebaut, dass
sie **nicht von selbst aufgehen**:

    Wochenlimit (-7 %)   paused_until = None   "bis zur manuellen Freigabe"
    Kill-Switch (15 %)   TradingState.KILLED   nur mit ausdruecklicher
                                               Bestaetigung rueckholbar

Das ist genau so gewollt und richtig - ein Mensch soll nachsehen, bevor es
weitergeht. Nur hat der Backtest es nie gezeigt, weil das naechste Fenster den
Zustand wegwarf.

### Was das bedeutet

Die Zahl, die zaehlt, ist nicht 0,863, sondern **0,296**. Alles, was in diesem
Dokument ueber den Abstand zum Deflated-Sharpe-Gate steht - 32 fehlende Trades,
Faktor 1,08 auf die Qualitaet -, galt fuer einen Lauf, der die Sicherung
regelmaessig zurueckgesetzt hat.

Und die praktische Seite ist noch wichtiger als die statistische: **Waere
dieses System die letzten Jahre gelaufen, stuende es heute still** und wartete
auf eine Freigabe. Der Backtest hat davon nichts gesagt.

### Was nicht getan wird

Das Wochenlimit automatisch auslaufen zu lassen waere die naheliegende
Reparatur - und genau die Sorte Aenderung, die dieses Projekt nicht macht. Es
ist eine **Sicherheitsgrenze**, kein Messparameter. Sie zu lockern, damit die
Zahlen besser aussehen, waere das Gegenteil dessen, wofuer sie da ist.

Ob eine Pause nach einer Verlustwoche von Hand freigegeben werden soll oder
nach einer festen Frist von selbst aufgeht, ist eine **Betriebsentscheidung**
und gehoert dem Nutzer, nicht mir. Beides ist vertretbar; unbemerkt bleiben
darf keines von beiden. Fuer den Betrieb heisst es konkret: Es wird
Telegram-Meldungen geben, nach denen das System steht, bis jemand es wieder
freigibt.

### Zum Umbau selbst

``durchgehend=True`` laeuft einen Backtest ueber die ganze Teststrecke; die
Fenster ordnen nur noch zu, welcher Trade zu welchem Abschnitt gehoert. Vor
dem ersten Testfenster wird nicht gehandelt. Nicht kombinierbar mit
``strategie_je_fenster`` - eine Position ueber die Grenze zu tragen hiesse,
sie unter einer Regel zu eroeffnen und unter einer anderen zu schliessen; der
Aufruf wird abgelehnt statt still umgangen.

Erreichbar ueber ``cli machbarkeit --durchgehend``.

Zwei Entwurfsfehler beim Bauen, beide von Tests gefangen:

* Der Fenstergewinn wurde gegen das **Startkapital** gerechnet statt gegen den
  Kontostand bei Fensterbeginn. Im fensterweisen Lauf ist das richtig, hier
  haette es jedem Fenster den gesamten bisher aufgelaufenen Gewinn noch einmal
  gutgeschrieben.
* Die erste Testreihe war eine Zufallsreihe, in der gar keine Position eine
  Fenstergrenze ueberspannte - beide Wege lieferten dasselbe, und der Test war
  gruen und wertlos. Jetzt steht eine deterministische Trendreihe daneben.

Versuchszaehler unveraendert bei **102**: Fehlerbehebung an der Messung, kein
neuer Einfall.

---

## Fuenfundzwanzig. Zwei Korrekturen an meinem eigenen Bericht von gestern

Der Befund aus Nummer vierundzwanzig - "der Backtest hat den Not-Aus alle drei
Monate zurueckgesetzt", Deflated Sharpe in Wahrheit 0,296 statt 0,863 - war in
der Richtung richtig und in zwei Punkten falsch. Beide gehoeren hierher.

### Erstens: Es war keine uebersehene Luecke, sondern eine dokumentierte Annahme

Ich habe den Reset je Fenster als unbemerkten Fehler dargestellt. Er steht seit
jeher im Docstring von ``Backtester._officer``, mit Begruendung:

> Kein ``state_path``: Jeder Lauf beginnt frei. Im Walk-Forward heisst das,
> dass jedes Testfenster mit einem frischen Officer startet - was der Annahme
> entspricht, dass der Nutzer einen ausgeloesten Not-Aus zwischen den Fenstern
> manuell freigibt. Ohne diese Annahme bliebe jedes Fenster nach dem ersten
> Not-Aus fuer immer stumm, und der Backtest waere in der anderen Richtung
> falsch.

Das ist eine bewusste Entscheidung mit einem echten Argument dahinter. Wertvoll
bleibt die **Messung**, wie stark diese Annahme wiegt - nicht die Behauptung,
sie sei niemandem aufgefallen. Sie war aufgeschrieben; ich hatte sie nicht
gelesen.

### Zweitens: Die 0,296 stammen aus einem Modellfehler, nicht aus der Wirklichkeit

Der durchgehende Lauf meldete 8,24 % Rueckgang - und gleichzeitig feuerte der
Kill-Switch, der bei 15 % greift. Beides kann nicht stimmen. Nachgemessen, je
Bein 250 EUR (was ein 500-EUR-Konto auf zwei Maerkten wirklich hat):

    Bein                      Trades   Rueckgang   erstes Ereignis
    BTC                           18     12,74 %   pausiert 03.09.2020
    ETH                           80     14,90 %   nie
    KONTO (beide, 500 EUR)         --     10,72 %   **nichts**

**Das Konto haette nichts ausgeloest.** Weder Kill-Switch noch Wochenlimit.
Ohne Limits gerechnet liegt der Kontorueckgang bei 13,03 % - immer noch unter
15 %.

Der Grund ist ein Modellfehler, und er ist meiner: Der Portfolio-Walk-Forward
laesst jedes Bein als **eigenen Backtest** laufen. Jedes bekommt damit ein
eigenes Konto *und einen eigenen Risk-Officer* - bei zwei Maerkten also zwei
Kill-Switches auf je halber Kapitalbasis. Die loesen aus, wo ein einziges Konto
nichts gemerkt haette.

Die Sperre des BTC-Beins am 03.09.2020 kostet **58 von 76 Trades**. Sie
beschreibt zwei getrennte 250-EUR-Konten, nicht das eine 500-EUR-Konto, das es
gibt.

Damit ist die gestrige Schlagzeile - "waere dieses System die letzten Jahre
gelaufen, stuende es heute still" - **nicht belegt**. Auf Kontoebene bindet
keine einzige Grenze. Was bleibt, ist die schwaechere und immer noch wichtige
Aussage: Der fensterweise Lauf setzt den Risikozustand regelmaessig zurueck,
und wie stark das wiegt, war bis jetzt ungemessen.

### Was gebaut wurde

``research/kontorisiko.py`` legt die Kapitalkurven aller Beine zu **einer**
Kontokurve zusammen und fuehrt den **echten** ``RiskOfficer`` darueber - Kerze
fuer Kerze, mit der Kerzenuhr. Keine Nachbildung seiner Regeln: Zwei
Umsetzungen derselben Sache laufen auseinander, und genau das ist in diesem
Projekt schon fuenfmal passiert.

Erreichbar ueber ``cli kontorisiko``. Kostet keinen Versuch - geprueft wird die
Kontofuehrung, keine Regel.

Zwei Grenzen des Werkzeugs, ausgesprochen:

* Es rechnet den Backtest **nicht** neu. Wo das Konto frueher gebremst haette,
  haetten die Beine danach anders gehandelt; diese Rueckwirkung fehlt. Dafuer
  braeuchte es einen Backtest, der alle Maerkte im Gleichschritt durchlaeuft,
  mit einem Konto und einem Officer.
* Es beantwortet deshalb genau eine Frage: **Haette das Konto ueberhaupt
  ausgeloest?** Lautet die Antwort nein - wie hier -, sind alle Sperren
  einzelner Beine Artefakte, und mehr muss man nicht wissen.

Dazu meldet ``run_portfolio_walkforward`` ab jetzt im Protokoll, wenn es die
Grenzen bei mehreren Beinen je Bein erzwingt. Ein Kommentar im Quelltext hat
nicht gereicht - ich habe die Zahlen selbst falsch gelesen.

### Wo der Kandidat damit steht

Unveraendert bei **7 von 11** aus Nummer dreiundzwanzig: Messlatte,
Schlechtestes Jahr, Deflated Sharpe, Parameter-Plateau. Die 0,296 aus gestern
sind zurueckzunehmen; die belastbare Zahl bleibt die aus dem fensterweisen Lauf
mit korrekter Aufwaermphase, **0,863**.

Was offen bleibt und ehrlich offen bleiben muss: Ein Backtest, der mehrere
Maerkte auf **einem** Konto mit **einem** Risk-Officer im Gleichschritt
durchlaeuft, gibt es noch nicht. Bis dahin sind Mehrmarkt-Laeufe mit
erzwungenen Grenzen mit Vorsicht zu lesen - und ``cli kontorisiko`` sagt, wie
viel Vorsicht noetig ist.

Versuchszaehler unveraendert bei **102**.

---

## Sechsundzwanzig. Der ganze Katalog, noch einmal gemessen

Zwei Fehler im Messinstrument sind gefunden worden - der Nachlauf am
Fensterende und die Aufwaermphase der Konfluenz. Der Leaderboard traegt aber
Stand vom 05.08.2026 und zaehlt noch **zehn** Gates. Jedes Urteil ueber jeden
Kandidaten stammt also aus einem Geraet, das seither zweimal repariert wurde.

**Ein Urteil ist nur so gut wie das Geraet, mit dem es zustande kam.** Also
alle 54 Kandidaten noch einmal durch die volle Zulassungsstrecke -
``cli nachpruefung``, ohne einen einzigen neuen Versuch.

### Zuerst eine Vermutung, gemessen und widerlegt

Erwartet hatte ich, dass die Aufwaermphasen-Korrektur viele Kandidaten
betrifft. Nachgerechnet, alter gegen neuer Schaetzer:

    54 Kandidaten geprueft
    15 bekamen zu wenig Aufwaermkerzen - davon 14 um genau **eine** Kerze
     1 wirklich betroffen: der Spitzenkandidat (150 statt 201)

Nur er traegt seinen laengsten Indikator in der Konfluenz. Die Vermutung
"viele Kandidaten falsch bewertet" ist damit erledigt, und zwar in fuenf
Minuten statt in einer Behauptung. Der **Nachlauf** dagegen trifft jeden.

### Das Ergebnis

    Kandidat                                Gates  Trades     p.a.      DD     DSR
    Trend mit Vola-Ziel 22 %                 8/11      51    6,67 %   8,83 %  0,486
    Vola-Ziel, kurzes Messfenster            8/11      51    5,75 %   7,78 %  0,476
    Trend mit Vola-Ziel 20 %                 8/11      51    5,61 %   8,03 %  0,422
    Trend 50 Tage mit Konfluenz              7/11     152   13,47 %  10,64 %  0,864
    Vola-Ziel, langes Messfenster            7/11      51    4,79 %   6,97 %  0,322
    Donchian-Ausbruch 55/20                  6/11      55   16,38 %  19,45 %  0,118

**Kein Kandidat besteht alle Gates.** Drei kommen auf 8 von 11 und damit ein
Gate weiter als der bisherige Spitzenkandidat.

### Warum das trotzdem kein Fortschritt ist

Die drei Achtel-Kandidaten haben 51 Trades und einen Deflated Sharpe zwischen
0,42 und 0,49. Der Spitzenkandidat hat 152 Trades und **0,864**. Gefordert
sind 0,95.

    Kandidat                     Gates    Abstand zum DSR-Gate
    Trend mit Vola-Ziel 22 %      8/11    0,464
    Trend 50 Tage mit Konfluenz   7/11    0,086

**Die Zahl bestandener Gates ist ein schlechtes Mass fuer Naehe.** Wer nach
ihr liest, haelt den Aussichtsreicheren fuer den Schwaecheren - der Erste ist
fuenfmal so weit vom haertesten Gate entfernt wie der Vierte. Und das
haerteste Gate ist genau dasjenige, das sich mit keinem Regler bewegen laesst
(Nummer einundzwanzig).

Dagegen hilft **keine** zusammengesetzte Kennzahl. Die waere nur ein neuer
Ersatzmassstab, an dem man sich wieder vorbeioptimiert. Genannt wird deshalb
beides, und das Urteil sagt es von sich aus, wenn Gate-Zahl und Deflated
Sharpe auf verschiedene Kandidaten zeigen.

### Was noch auffiel

33 der 54 Kandidaten liefern auf BTC + ETH Tageskerzen **keinen einzigen
Trade**. Verteilt auf die Generationen:

    Generation      1    2    4    6    7    8    9   10
    ohne Trades     4    5    3    3    8    8    0    0

Das ist kein Befund, sondern die bekannte Zuordnung: Die Generationen 6 und 7
gehoeren auf 15-Minuten-Kerzen, und die fruehen Generationen waren
kurzfristige Ideen. Die neuesten - 9 und 10 - handeln alle. Festgehalten,
damit niemand die Zahl fuer einen Fehler haelt.

### Was daraus folgt

Der Spitzenkandidat bleibt der weiteste, und zwar deutlich - auf dem einzigen
Gate, an dem es haengt. Am Stand aendert die Nachpruefung nichts: **7 von 11**,
offen bleiben Messlatte, Schlechtestes Jahr, Deflated Sharpe und
Parameter-Plateau.

Was sie bringt, ist etwas anderes: Ab jetzt gibt es einen Befehl, der nach
jeder Aenderung am Messgeraet den ganzen Katalog neu bewertet. Beide
Instrumentenfehler dieser Woche haetten die Rangfolge verschieben koennen, und
niemand haette es gemerkt.

Versuchszaehler unveraendert bei **102**: Dieselben Regeln auf denselben Daten.
Der Deflated Sharpe korrigiert dafuer, dass man bei genug **Einfaellen** etwas
findet - nicht dafuer, dass man einen alten Einfall richtiger misst.

---

## Siebenundzwanzig. Mehr Maerkte bringen Trades, aber keine Information

Die Marktkombinationen standen schon einmal in diesem Dokument - gemessen mit
einem Backtest, der offene Positionen am Fensterende glattstellte, und **bevor
es die Korrektur fuer abhaengige Beobachtungen gab.** Beides ist seither
behoben, also gehoerte die Tabelle neu gemessen. Sie kostet keinen Versuch:
Mehr Maerkte sind mehr *Daten*, nicht mehr Einfaelle.

### Erwartung und Ergebnis

Erwartet hatte ich einen Anstieg. Die alte Tabelle zeigte den Deflated Sharpe
bei vier Maerkten auf 0,875, also keine 0,08 unter der Schwelle - und genau um
diese Groessenordnung hatte der Nachlauf-Fehler die Zahl gedrueckt.

Gemessen kam das Gegenteil heraus:

    Kombination         Gates  Trades      p.a.       DD     DSR
    BTC+ETH              7/11     152   13,47 %  10,64 %   0,864
    ETH+LTC              5/11     186    9,15 %  16,22 %   0,515
    ETH+XRP              4/11     188    8,84 %  12,53 %   0,458
    ETH                  7/11      80   13,33 %  13,15 %   0,455
    BTC+ETH+XRP          7/11     260   10,43 %  10,63 %   0,422
    BTC+ETH+LTC          6/11     258   10,64 %  12,00 %   0,393
    BTC+ETH+LTC+XRP      5/11     366    9,07 %  12,51 %   0,275
    BTC                  5/11     117    9,35 %  19,96 %   0,190
    BTC+LTC              4/11     180    9,64 %  13,52 %   0,080
    LTC+XRP              3/11     214    6,77 %  20,35 %   0,016

**Zweieinhalbmal so viele Trades, und der Deflated Sharpe faellt von 0,864 auf
0,275.** Keine einzige Kombination schlaegt BTC + ETH.

### Warum - nachgemessen statt vermutet

    Kombination        roh   effektiv    ICC       p   SR/Trade
    BTC+ETH            152        152  0,112   0,072     0,2597
    BTC+ETH+XRP        260        146  0,105   0,021     0,2006
    BTC+ETH+LTC+XRP    366        151  0,132   0,001     0,1757

**Die effektive Stichprobe bleibt bei rund 150 - egal wie viele Maerkte
dazukommen.** Die rohe Zahl waechst um das Zweieinhalbfache, die Zahl
unabhaengiger Beobachtungen um nichts. Gleichzeitig faellt die Qualitaet je
Trade von 0,26 auf 0,18, weil die zusaetzlichen Maerkte schlechter sind.

Dieselbe Information, schlechtere Qualitaet - deshalb der Absturz.

Bemerkenswert ist auch die dritte Spalte: Der p-Wert faellt von 0,072 ueber
0,021 auf 0,001. Mit jedem Bein wird die Abhaengigkeit **eindeutiger**. Bei
zwei Maerkten ist sie ein Grenzfall (und wird als solcher angesagt), bei vier
ist sie kein Grenzfall mehr.

### Was das ueber den alten Befund sagt

Die alte Tabelle - "mehr Maerkte bringen Trades, DSR steigt auf 0,875" - war
**der Ensemble-Schlupfloch in anderer Gestalt.** Sie zaehlte rohe Trades und
hielt vier korrelierte Kryptomaerkte fuer vier unabhaengige Informationsquellen.
Genau dafuer ist ``research/unabhaengigkeit.py`` gebaut worden; dass es
inzwischen greift, sieht man hier zum ersten Mal an echten Daten und nicht an
einem konstruierten Beispiel.

Damit ist die Richtung "mehr Maerkte" nicht nur widerlegt, sondern **umgekehrt
belegt**: Sie schadet. Und zwar nicht, weil die Maerkte schlecht waeren,
sondern weil sie dasselbe sagen.

### Was daraus folgt

Der Abstand zum Deflated-Sharpe-Gate ist damit haerter als gedacht. Er laesst
sich **nicht** durch Verbreitern schliessen - nicht ueber Maerkte, nicht ueber
Perioden-Ensembles, nicht ueber feinere Kerzen. Alles, was mehr Zeilen
erzeugt, ohne mehr zu wissen, wird von der Korrektur wieder eingesammelt, und
das ist richtig so.

Was bleibt, ist die schwierige Richtung: eine Regel, die **je Trade** besser
ist. Nicht mehr Trades - bessere.

Stand unveraendert: **BTC + ETH, 7 von 11**, Deflated Sharpe 0,864 gegen 0,95.
Versuchszaehler unveraendert bei **102**.

---

## Achtundzwanzig. Der Stop steht richtig - meine Vermutung war falsch

Nach Nummer siebenundzwanzig ist klar: Mehr Zeilen helfen nicht, nur bessere.
Der erste Verdacht fiel auf den **Stop**, und er kam aus dem Quelltext selbst.
``StopSpec.percent`` sagt ueber investierte Strategien:

> Fuer eine investierte Strategie ist der Stop **Notbremse und nicht
> Ausstieg**: Ausgestiegen wird ueber eine Bedingung, der Stop faengt nur den
> Fall ab, in dem der Markt ohne Zwischenschritt wegbricht. Er gehoert dann
> weit genug hinaus, dass normales Rauschen ihn nicht erreicht.

Der Spitzenkandidat steht auf 4 % - und dieser Stop beendet **44,7 % aller
Trades**. Nach der eigenen Beschreibung des Codes ist er damit kein Notausgang,
sondern der Ausstieg. Die Vermutung lag also nahe: zu eng, und deshalb bleibt
Qualitaet je Trade liegen.

**Gemessen ist das Gegenteil richtig.**

    Stop  Trades     p.a.       DD     schl. Jahr    DSR   Plateau  Gates
     2 %     152    7,23 %   6,55 %      -4,33 %   0,553    0,50     8/11
     3 %     152   10,33 %   9,15 %      -8,82 %   0,670    0,50     8/11
     4 %     152   13,47 %  10,64 %     -10,32 %   0,863    0,50     7/11  <- Kandidat
     6 %     154   12,93 %  13,07 %     -12,76 %   0,201    1,00     7/11
     8 %     154   12,11 %  14,11 %     -13,81 %   0,057    1,00     7/11
    12 %     154   11,67 %  15,65 %     -15,35 %   0,008    1,00     7/11
    16 %     154   11,86 %  14,18 %     -13,88 %   0,011    1,00     7/11

Die 4 % sind ein **Maximum**, kein Versehen. Enger ist schlechter, weiter ist
vernichtend.

### Warum - und es ist kein Kippschalter

Ein Sturz von 0,863 auf 0,201 bei einer einzigen Stufe sieht nach dem
Kippschalter aus, den ich in Nummer vierundzwanzig gefunden habe. Ist es aber
nicht:

    Stop   roh   effektiv       p   SR/Trade   Schiefe   Woelbung   Stop-Ausstiege
     2 %   152        152   0,128     0,2138     3,197     12,670       73,7 %
     3 %   152        152   0,239     0,2295     3,323     13,725       58,6 %
     4 %   152        152   0,072     0,2597     3,473     15,951       44,7 %
     6 %   154         87   0,025     0,2231     4,764     30,637       27,9 %
     8 %   154         80   0,021     0,1960     6,275     50,761       16,9 %
    12 %   154         73   0,016     0,1730     7,643     69,971        5,8 %

Der p-Wert faellt **monoton** von 0,072 auf 0,016 - ein Trend, kein Muenzwurf.
Und beide Groessen gehen gleichzeitig in die falsche Richtung:

* **Die Qualitaet je Trade hat bei 4 % ein echtes Maximum** (0,2597), auf
  beiden Seiten faellt sie ab.
* **Die effektive Stichprobe bricht bei weitem Stop ein** (152 auf 73). Der
  Grund ist einsichtig, sobald man ihn sieht: Wo der Stop nicht mehr
  dazwischengeht, laufen die Trades eines Fensters gemeinsam durch dieselbe
  Marktbewegung. Aus vielen Beobachtungen wird eine.
* Die Woelbung steigt von 16 auf 70, die Schiefe von 3,5 auf 7,6: Wenige
  riesige Gewinner tragen alles - genau die Verteilung, bei der ein Sharpe
  wenig aussagt und der Deflated Sharpe das auch sagt.

### Was der Code an sich selbst lernt

Der Docstring von ``StopSpec`` beschreibt ein Ideal - Stop als Notbremse -,
das **fuer diese Regel nachweislich schlechter ist**. Bei 12 % beendet der
Stop nur noch 5,8 % der Trades, ist also genau die Notbremse, die dort
gefordert wird, und liefert einen Deflated Sharpe von 0,008.

Das Ideal ist damit nicht falsch, aber es ist keine Regel: Es gilt fuer
Strategien, deren Ausstiegsbedingung schnell genug greift. Der 50-Tage-Schnitt
tut das nicht - bis er reisst, ist der Verlust groesser als der Stop erlaubt.
Bei dieser Regel **ist** der Stop ein Teil des Ausstiegs, und das ist nicht zu
beheben, sondern hinzunehmen.

### Was noch auffiel

Das **Parameter-Plateau** wird ab 6 % Stop bestanden (1,00 statt 0,50). Es ist
also erreichbar - nur an Stellen, an denen der Deflated Sharpe bei 0,2 liegt.
Wieder zwei Gates, die gegeneinander ziehen: Drawdown haelt bis 4 %,
Parameter-Plateau erst ab 6 %.

### Gebaut

``cli machbarkeit`` tastet jetzt **jeden** hinterlegten Regler ab, nicht nur
das Vola-Ziel: ``--regler vola|stop|konviktion``. Die Stufen stehen bei der
Stellschraube und nicht im Aufruf - solange jede Abtastung ihre eigenen
Messpunkte mitbringt, misst jede etwas anderes, und wer die Punkte waehlt,
waehlt am Ende das Ergebnis.

Versuchszaehler **102 -> 108**: sechs neue Stopstufen, ehrlich gezaehlt. Der
Ausgangswert von 4 % war bereits drin. Das hebt die Huerde um 0,007 Punkte -
der Preis dafuer, eine Vermutung ausgeraeumt statt mitgeschleppt zu haben.

Stand unveraendert: **7 von 11**, Deflated Sharpe 0,863 gegen 0,95.

---

## Neunundzwanzig. Generation 6 und 7 auf 15 Minuten - alle vierzehn tot

Ein Punkt stand seit Wochen offen: *"Generation 6/7 gehoeren auf
15-Minuten-Kerzen."* Sie wurden dort nie gemessen. In der Nachpruefung von
Nummer sechsundzwanzig lieferten sie auf Tageskerzen fast keinen Trade - was
niemanden ueberraschte, denn dafuer waren sie nie gedacht.

Die Daten liegen laengst im Speicher: **222.700 Fuenfzehnminutenkerzen** je
Markt fuer BTC und ETH, ab dem 30.03.2020. Also gemessen.

### Das Ergebnis

Alle vierzehn Kandidaten der Generationen 6 und 7, Walk-Forward auf BTC + ETH,
15 Minuten:

    Kandidat                          Trades      p.a.        DD   Gates
    Bollinger-Ruecksetzer im Trend      1969   -24,5 %    81,2 %    1/9
    Ausbruch nach Volatilitaetsenge     1447   -38,6 %    92,4 %    1/9
    VWAP-Rueckkehr                      2940   -39,2 %    92,8 %    1/9
    Liquiditaets-Abgriff                2682   -39,5 %    93,0 %    1/9
    Keltner-Enge mit Ausbruch           2601   -43,6 %    95,2 %    1/9
    Stochastik-Ruecksetzer im Trend     3068   -32,7 %    88,2 %    1/9
    MACD-Beschleunigung                 3047   -33,7 %    88,8 %    1/9
    ... alle uebrigen ebenso            233-3068  -9 bis -44 %      1/9

**Vierzehn von vierzehn: 1 von 9 Gates.** Jahresrenditen zwischen -9 % und
-44 %, Rueckgaenge zwischen 68 % und 95 %.

Und es ist ausdruecklich **kein** Stichprobenproblem: Diese Regeln liefern
zwischen 233 und 3068 Trades - das Zwanzigfache des Spitzenkandidaten. Von
Trades allein wird nichts besser.

### Es liegt nicht an den Gebuehren

Der naheliegende Verdacht bei 15 Minuten sind die Kosten. Aufgeschluesselt:

    Kandidat                          Trades    brutto   Gebuehren   Funding    netto
    Bollinger-Ruecksetzer im Trend      1969   -347,0     -434,3    -341,0   -1122,3
    Grosse Kerze mit Volumen            2307    -26,3     -396,6    -277,5    -700,4
    Stochastik-Ruecksetzer im Trend     3068   -232,4     -496,3    -248,0    -976,7
    Keltner-Enge mit Ausbruch           2601   -672,3     -563,7    -160,6   -1396,6
    VWAP-Rueckkehr                      2940   -669,6     -387,2    -168,8   -1225,6

**Alle vierzehn verlieren schon brutto.** Bei Gebuehren von null und Funding
von null bliebe jede einzelne Regel im Minus. Die Kosten machen es schlimmer -
sie verdoppeln bis verzwanzigfachen den Verlust -, aber sie sind nicht die
Ursache.

Damit ist die Aussage schaerfer als die uebliche: Es ist nicht so, dass hier
ein Vorteil von den Kosten aufgefressen wuerde. **Es ist keiner da.**

(Zum Funding: Es wird nach Perpetual-Bedingungen modelliert, weil dort
gehandelt wuerde - die Bitstamp-Kerzen selbst sind Kassamarkt und kennen
keines. Das ist die richtige Annahme fuer den Zielmarkt, aber es ist eine
Annahme, und auf 15 Minuten faellt sie ins Gewicht.)

### Was damit erledigt ist

Die Fuenfzehnminuten-Richtung war zweimal offen: einmal fuer den
Spitzenkandidaten (gemessen in Nummer fuenfzehn, nichts zu holen), einmal fuer
die Generationen, die eigens dafuer entworfen wurden. **Beide sind jetzt
gemessen und beide sind tot.** Der Punkt kann von der Liste.

Kostet keinen Versuch: dieselben Regeln auf anderen Daten, und ausgewaehlt
wurde nichts - es gab nichts auszuwaehlen.

### Ein Fehler in der eigenen Erweiterung, vor dem Ausliefern gefangen

Fuer diesen Lauf hat ``cli nachpruefung`` zwei Schalter bekommen: mehrere
Generationen auf einmal und ``--schnell``, das die beiden teuren Gates
(Parameter-Plateau, Kosten-Stress) auslaesst - 33 Sekunden je Kandidat statt
Minuten.

Dabei waere fast etwas durchgerutscht: ``Ergebnis.zugelassen`` prueft
``bestanden == gesamt``. Mit ``--schnell`` ist ``gesamt`` neun, also haette ein
Kandidat mit 9 von 9 im Bericht als **"alle Gates bestanden"** gestanden -
waehrend zwei Gates gar nicht gelaufen sind. Genau die Sorte stiller
Aufwertung, gegen die die ganze Zulassungsstrecke gebaut ist.

Eine Vorauswahl kann jetzt nichts zulassen, und ein Test haelt es fest.

Stand unveraendert: **BTC + ETH auf Tageskerzen, 7 von 11**, Deflated Sharpe
0,863 gegen 0,95. Versuchszaehler unveraendert bei **108**.

---

## Dreissig. Alle drei Groessenregler gemessen - und warum keiner hilft

Der Konviktions-Bonus war der letzte hinterlegte Regler, der nie abgetastet
wurde. Damit sind es jetzt alle drei:

    Regler         Spanne des Deflated Sharpe   Abstand zur Schwelle
    Vola-Ziel                        0,011                  0,080
    Stop                             0,855*                 0,087
    Konviktion                       0,017                  0,088

    * die Spanne beim Stop entsteht durch den Absturz nach oben, nicht durch
      eine Verbesserung - das Maximum liegt beim Ausgangswert (Nummer
      achtundzwanzig).

**Kein Groessenregler bewegt das harte Gate.** Bei Vola-Ziel und Stop ist das
einsichtig, sobald man es sieht: Sie skalieren jede Position mit demselben
Faktor, und ein Verhaeltnis aendert sich davon nicht.

### Die Konviktion tut etwas - nur nicht das

    Bonus  Trades      p.a.       DD   schl. Jahr     DSR   Messlatte  Gates
      0       152   16,20 %  13,72 %    -13,15 %    0,862       +       7/11
    0,5       152   14,23 %  11,77 %    -11,36 %    0,862       -       7/11
    1,0       152   13,47 %  10,64 %    -10,32 %    0,856       -       7/11
    1,5       152   13,08 %  10,10 %     -9,81 %    0,853       -       8/11
    2,0       151   12,65 %   9,58 %     -9,34 %    0,845       -       8/11

Die Konviktion ist ein **Risikoregler**: Je staerker sie spreizt, desto
niedriger Rendite *und* Rueckgang. Bei 1,5 und 2,0 halten Drawdown und
schlechtestes Jahr, dafuer reisst die Messlatte. Bei 0 - Konfluenz komplett
aus - haelt die Messlatte mit 16,20 %, dafuer reissen die Rueckgangsgrenzen.

Wieder derselbe Konflikt, dieselbe leere Menge. Und der Deflated Sharpe bleibt
bei 0,845 bis 0,862.

Nebenbei bestaetigt das die alte Messung, statt ihr zu widersprechen: Je
Einheit Rueckgang bringt die Konfluenz 1,27 gegen 1,18 ohne sie. Sie ist also
nicht wirkungslos - der Deflated Sharpe fragt nur nach etwas anderem.

### Die Frage, die daraus folgte

Die Konviktion skaliert **nicht** gleichmaessig. Sie verschiebt Gewichte
zwischen Trades. Dass auch sie den Deflated Sharpe nicht bewegt, muss also
einen anderen Grund haben - und der liegt in der Annahme, auf der sie ruht:
*Je mehr Zusatzbedingungen erfuellt sind, desto besser der Trade.*

**Diese Annahme ist nie geprueft worden.** Gemessen wurde immer nur die
Wirkung der Groessenlogik auf das Gesamtergebnis, nie die Ordnung, nach der
sie verteilt. Also gemessen, an den 152 Trades des Kandidaten selbst:

    erfuellte Bedingungen   Trades   Mittel R   Median R   Trefferquote
                        0       14      0,194     -1,030        14,3 %
                        1       60      1,534     -0,969        21,7 %
                        2       27     -0,427     -1,030         3,7 %
                        3       51      2,688     -0,383        35,3 %

    Rangkorrelation rho = +0,150, p = 0,062 (Permutationsnull, 2000 Ziehungen)

Drei Dinge stehen da, und alle drei zaehlen:

* **Die volle Konfluenz traegt.** 3 von 3 liefert +2,688 R im Mittel bei 35 %
  Trefferquote - deutlich das beste Feld.
* **Die Reihenfolge stimmt nicht.** Zwei erfuellte Bedingungen sind das
  *schlechteste* Feld ueberhaupt (-0,427 R, 3,7 % Treffer) - schlechter als
  eine, schlechter als keine. Die Groessenlogik verteilt den Einsatz entlang
  einer Ordnung, die so nicht gilt.
* **Belegt ist der Zusammenhang nicht.** p = 0,062 gegen die Permutationsnull.
  Er kann da sein; aus 152 Trades laesst er sich nicht von Zufall
  unterscheiden.

Damit ist erklaert, warum der Konviktions-Regler nichts bewegt: Er spreizt den
Einsatz nach einem Signal, das den Ausgang nur schwach und nicht der Reihe nach
vorhersagt.

### Was daraus ausdruecklich nicht folgt

"Handle nur bei voller Konfluenz" waere **keine** Schlussfolgerung, sondern die
Auswahl des besten Eimers nach Ansicht der Daten - genau die Ueberanpassung,
gegen die die ganze Strecke gebaut ist. Dazu kommt: Der Bestaetigungsfilter ist
fuer diese Regelfamilie bereits gemessen und widerlegt (Generation 2), und die
kleinen Felder (14 und 27 Trades) tragen ohnehin kein Urteil.

Festgehalten wird die Messung trotzdem - als ``research/konfluenzwirkung.py``
und ``cli konfluenz``, mit derselben Bedingungsauswertung, die auch der
Backtest fuer die Groesse benutzt. Wer die Annahme spaeter fuer eine andere
Regel braucht, misst sie, statt sie zu glauben.

### Stand

    Versuchszaehler   108 -> 112   (vier neue Konviktionsstufen)
    Kandidat          BTC + ETH, Tageskerzen, 7 von 11
    Deflated Sharpe   0,863 gegen 0,95

Alle Groessenregler sind ausgemessen. Was den Deflated Sharpe bewegen kann,
sind nur noch die **Entscheidungen** - wann ein- und ausgestiegen wird -, nicht
wie viel dabei auf dem Tisch liegt.

---

## Einunddreissig. Wohin ein neuer Einfall muesste - und was Suchen kostet

Alle Groessenregler sind ausgemessen. Was bleibt, sind neue **Regeln**, und
jede kostet einen Versuch, der die Huerde fuer alle hebt. Bevor man so etwas
budgetiert, gehoert ausgerechnet, worauf man eigentlich zielt.

### Die Grenzlinie

Der Deflated Sharpe haengt an zwei Groessen: Zahl unabhaengiger Trades und
Qualitaet je Trade. Zu jeder Trade-Zahl gehoert deshalb ein noetiger Sharpe je
Trade - und **diese Linie** ist der Massstab, nicht eine der beiden Zahlen
allein. Bei 112 Versuchen, mit der Schiefe und Woelbung des Kandidaten:

    Trades    noetiger Sharpe je Trade
        50                      0,4705
       100                      0,3410
       152                      0,2843
       200                      0,2523
       300                      0,2112
       500                      0,1682

### Wo die Kandidaten stehen

    Kandidat                            Trades      hat    noetig   Faktor
    Trend 50 Tage mit Konfluenz            152   0,2597    0,2843     1,09
    Trend mit Vola-Ziel 22 %                51   0,3559    0,4657     1,31
    Vola-Ziel, kurzes Messfenster           51   0,3535    0,4657     1,32
    Trend mit Vola-Ziel 20 %                51   0,3417    0,4657     1,36
    Trend-Beteiligung (fair gerechnet)      46   0,3583    0,4917     1,37
    Trend-Beteiligung 50 Tage              142   0,2005    0,2928     1,46
    Trendbeteiligung mit Puffer            302   0,1409    0,2106     1,49
    Momentum-Beteiligung                    99   0,2262    0,3425     1,51
    Donchian-Ausbruch 55/20                 55   0,2372    0,4484     1,89

**Der Spitzenkandidat hat die schlechteste Qualitaet je Trade der
Spitzengruppe** - 0,2597 gegen 0,3583 - und ist trotzdem mit Abstand am
naechsten dran. Er handelt dreimal so oft, und die Wurzel aus der Stichprobe
schlaegt den Unterschied in der Qualitaet.

Das ist die eigentliche Lehre der Tabelle: Wenige gute Trades reichen nicht
gegen viele mittlere. Wer 46 Trades zu je 0,3583 hat, braeuchte 0,4917 - er
ist **weiter** weg als jemand mit 152 zu je 0,2597.

### Was das als Ziel bedeutet

Zwei Wege fuehren ueber die Linie, und sie sind sehr verschieden schwer:

* **152 Trades mit Sharpe 0,2843** - neun Prozent mehr Qualitaet bei
  gleicher Frequenz.
* **300 Trades mit Sharpe 0,2112** - das kann der Kandidat je Trade
  **heute schon** (0,2597). Es fehlt allein die Frequenz.

Der zweite Weg sieht leichter aus und ist es nicht: Mehr Trades muessen
**unabhaengige** Trades sein. Mehr Maerkte liefern sie nicht (Nummer
siebenundzwanzig: die effektive Stichprobe bleibt bei 150, egal wie viele
Maerkte dazukommen), feinere Kerzen auch nicht (Nummer neunundzwanzig).
Sie muessten aus mehr **Entscheidungen auf demselben Markt** kommen, ohne dass
die Qualitaet faellt.

### Was Suchen kostet - und dass es sich trotzdem lohnt

    Versuche   noetiger Sharpe bei 152 Trades
         112                           0,2843
         152                           0,2916
         202                           0,2982
         302                           0,3073
         502                           0,3185

Jeder weitere Einfall hebt die Linie um **0,00021**. Hundert weitere Versuche
kosten also rund 5 % mehr geforderte Qualitaet - waehrend die heutige Luecke
9 % betraegt.

**Damit ist die Suche nicht selbstzerstoererisch, sondern nur teuer.** Das ist
ein Ergebnis, das ich anders erwartet hatte: Die Sorge, dass sich das Ziel beim
Suchen schneller entfernt, als man aufholt, laesst sich ausrechnen - und sie
trifft nicht zu. Bei diesen Groessenordnungen darf weiter gesucht werden.

Was dagegen steht, ist eine andere Zahl: **In 53 gemessenen Einfaellen ist
keiner naeher gekommen als der Spitzenkandidat.** Nicht die Huerde macht die
Suche aussichtsarm, sondern die bisherige Trefferquote.

### Gebaut

``research/suchbudget.py`` und ``cli suchbudget``. Der Befehl misst alle
Kandidaten des Katalogs ohne Gates - schnell genug fuer einen Lauf zwischendurch
- und stellt sie an die Linie. Verglichen wird der **Faktor**, nicht die
Differenz: Eine Luecke von 0,05 wiegt bei einem Sharpe von 0,25 schwerer als
bei 0,8. Kandidaten mit zu kleiner Stichprobe werden als *unerreichbar*
ausgewiesen und nicht als "sehr weit weg" - das ist eine andere Aussage.

Kostet keinen Versuch: gemessen werden bereits gerechnete Regeln, ohne Gates,
und ausgewaehlt wird nichts.

Stand unveraendert: **7 von 11**, Versuchszaehler **112**.

---

## Zweiunddreissig. Die letzte offene Richtung: schneller handeln

Nummer einunddreissig hatte zwei Wege ueber die Grenzlinie benannt. Der eine -
mehr Qualitaet bei gleicher Frequenz - ist die schwere Richtung. Der andere sah
leichter aus:

> 300 Trades mit Sharpe 0,2112 - das kann der Kandidat je Trade heute schon
> (0,2597). Es fehlt allein die Frequenz.

Mehr Maerkte und feinere Kerzen liefern diese Trades nicht (Nummern
siebenundzwanzig und neunundzwanzig). Bleibt: **mehr Entscheidungen auf
demselben Markt** - ein schnellerer Schnitt kreuzt oefter. Dafuer bekam
``cli machbarkeit`` einen Perioden-Regler, der **alle** Perioden zugleich
skaliert: Einstieg, Ausstieg, Konfluenz und das Messfenster der
Vola-Steuerung. Nur eine davon zu verschieben ergaebe eine Regel, die bei 40
einsteigt und bei 50 aussteigt - der Fehler, den das Plateau-Gate schon einmal
gemacht hat.

### Das Ergebnis

    Faktor  Trades   SR/Trade   noetig   Faktor    p.a.       DD     Gates
       0,4     305     0,1774   0,2108     1,19  18,94 %  14,85 %    6/11
       0,5     265     0,1803   0,2242     1,24  15,17 %  16,85 %    7/11
       0,6     226     0,2053   0,2404     1,17  13,80 %  13,56 %    6/11
       0,8     175     0,2169   0,2688     1,24  10,30 %  10,31 %    8/11
       1,0     152     0,2597   0,2857     1,10  13,47 %  10,64 %    7/11  <-
      1,25     132     0,1703   0,3038     1,78   6,21 %   9,56 %    6/11
       1,6     113     0,1400   0,3250     2,32   3,69 %   9,98 %    5/11
       2,0     106     0,1326   0,3342     2,52   2,79 %   8,95 %    4/11

**Der Mechanismus funktioniert genau wie vorhergesagt - und hilft trotzdem
nicht.** Ein doppelt so schneller Schnitt liefert doppelt so viele Trades (305
gegen 152), und die geforderte Qualitaet faellt entsprechend von 0,286 auf
0,211. Nur faellt die **erreichte** Qualitaet schneller: von 0,2597 auf 0,1774.

Der Abstand zur Linie waechst dadurch von 1,10 auf 1,19. Und nach oben ist es
noch klarer: Bei Faktor 2 steht der Abstand bei 2,52.

**Der Perioden-Wert des Kandidaten ist also auch auf dieser Achse das
Optimum** - der dritte Regler in Folge, bei dem das so ist (Stop, Konviktion,
Periode). Das ist bemerkenswert und verdient eine nuechterne Einordnung: Es
spricht dafuer, dass die 50 Tage kein Zufallstreffer sind. Es heisst aber
nicht, dass sie gut genug waeren - sie sind nur das Beste in einer Familie, die
nicht reicht.

### Und ein Befund ueber das Messwerkzeug

Die Deflated-Sharpe-Werte entlang dieses Reglers springen wild: 0,795 - 0,703 -
0,467 - 0,344 - **0,851** - 0,071 - 0,018 - 0,006. Ein Wert von 0,851 zwischen
0,344 und 0,071 ist keine Kurve, das ist ein Schalter. Nachgemessen:

    Faktor   roh   effektiv    ICC       p    knapp
       0,4   305        305  0,053   0,054     ja
       0,5   265        265  0,059   0,059     ja
       0,6   226        151  0,079   0,040     ja   <- gekuerzt
       0,8   175        115  0,109   0,049     ja   <- gekuerzt
       1,0   152        152  0,112   0,072     ja
      1,25   132         81  0,187   0,040     ja   <- gekuerzt
       1,6   113         53  0,375   0,009     nein
       2,0   106         36  0,629   0,001     nein

**Sechs von acht Stellungen liegen im Grenzbereich**, und drei davon fallen
knapp unter 0,05 - dort wird die Stichprobe um ein Drittel gekuerzt, bei
p-Werten, die sich von den Nachbarn um Hundertstel unterscheiden. Das ist die
Klippe aus Nummer vierundzwanzig, diesmal nicht als einzelner Ausreisser,
sondern ueber einen ganzen Regler sichtbar.

Darunter liegt aber ein echter, sauberer Trend: **Der ICC steigt monoton von
0,053 auf 0,629.** Je langsamer die Regel, desto staerker haengen ihre Trades
zusammen - was einleuchtet, weil weniger Trades laenger durch dieselbe
Marktbewegung laufen.

Daraus folgt eine Leseregel, die ab jetzt gilt: **Entlang eines Reglers ist der
Abstand zur Grenzlinie die verlaesslichere Rangfolge als der Deflated Sharpe.**
Er rechnet mit rohen Trades und der Qualitaet je Trade - beide stetig - statt
mit einer Zahl, die an einer harten Schwelle haengt.

Der Preis dieser Leseregel gehoert dazu: Weil sie mit rohen Trades rechnet, ist
sie dort **zu freundlich**, wo die Abhaengigkeit stark ist. Bei Faktor 1,6 und
2,0 mit einem ICC von 0,375 und 0,629 ist der wahre Abstand groesser als 2,32
und 2,52. Beide Lesarten fuehren hier zum selben Schluss - nur ist die eine
stabil und die andere nicht.

### Stand

    Versuchszaehler   112 -> 119   (sieben neue Perioden-Stufen)
    Kandidat          BTC + ETH, Tageskerzen, 7 von 11
    Abstand zur Linie 1,10 - naeher als alles andere Gemessene

Damit sind beide Wege aus Nummer einunddreissig begangen. Die Frequenz ist es
nicht. Was bleibt, ist die schwere Richtung: eine Regel, die **je Trade**
besser ist als 0,26 - und keine der 61 gemessenen ist es.

---

## Dreiunddreissig. Die Klippe im haertesten Gate ist weg

Dreimal ist derselbe Fehler aufgetreten, und zweimal habe ich geschrieben, die
richtige Loesung waere eine stetige Kuerzung - "gehoert gebaut, wenn sie
durchgerechnet ist, nicht wenn sie plausibel klingt". Jetzt ist sie
durchgerechnet.

### Was kaputt war

Die effektive Stichprobe wurde gekuerzt, sobald der Permutationstest
``p <= 0,05`` meldete, und sonst gar nicht. Eine **harte Schwelle auf einer
stetigen Groesse**. Zuletzt sichtbar ueber einen ganzen Regler (Nummer
zweiunddreissig):

    Faktor   roh   effektiv    ICC       p    Deflated Sharpe
       0,6   226        151  0,079   0,040              0,467
       0,8   175        115  0,109   0,049              0,344
       1,0   152        152  0,112   0,072              0,851
      1,25   132         81  0,187   0,040              0,071

Der ICC - die **eigentliche** Abhaengigkeit - steigt glatt an. Nur der p-Wert
wandert ueber die Schwelle, und wo er knapp darunter faellt, verschwindet ein
Drittel der Stichprobe. Ein Deflated Sharpe von 0,851 zwischen 0,344 und 0,071
ist keine Kurve, sondern ein Schalter.

### Die Korrektur, und warum genau so

Gekuerzt wird jetzt **immer** - aber kalibriert am **95. Perzentil** der
Permutationsnull statt an ihrem Median. Der Unterschied ist die ganze Sache:

* Am **Median** liegt auf unabhaengigen Daten die Haelfte aller Ziehungen
  darueber. Unbedingt angewandt bestrafte das die Haelfte aller sauberen
  Messungen - deshalb brauchte die alte Fassung eine Schwelle davor, und mit
  ihr die Klippe.
* Am **95. Perzentil** liegt nur jede zwanzigste saubere Ziehung darueber, und
  dann knapp. Die Kuerzung geht dort von selbst gegen null - ganz ohne ``if``.

Damit verschwindet die Schwelle, ohne dass Rauschen bestraft wird. Das war die
Bedingung, an der die erste Fassung gescheitert war.

### Gegengeprueft, in beide Richtungen

**An bekannter Null** (unabhaengige Bloecke ungleicher Groesse, vierzig
Ziehungen): 95 % bleiben ungekuerzt, im Mittel bleiben 99,5 % der Stichprobe,
im schlimmsten Fall 86,5 %. Genau die Zusage des 95. Perzentils.

**An echten Daten**, dieselben Reglerstufen wie oben:

    Faktor    ICC    vorher       jetzt
       0,4  0,053   305/305     305/305
       0,5  0,059   265/265     265/265
       0,6  0,079   151/226     221/226
       0,8  0,109   115/175     175/175
       1,0  0,112   152/152     152/152
      1,25  0,187    81/132     128/132
       1,6  0,375    53/113      90/113
       2,0  0,629    36/106      72/106

Die Kuerzung folgt jetzt dem ICC statt dem Zufall: unter 0,12 praktisch keine,
bei 0,375 ein Fuenftel, bei 0,629 ein Drittel. Monoton, ohne Sprung.

### Was es den Kandidaten kostet

    vorher    Deflated Sharpe 0,863   fehlende Trades 32
    jetzt     Deflated Sharpe 0,843   fehlende Trades 39

**Der Kandidat wird schlechter**, und das aus zwei Gruenden: Der
Versuchszaehler ist inzwischen bei 119 statt 112, und die neue Kuerzung greift
auch bei ihm ein wenig. Seine effektive Stichprobe bleibt zwar bei 152 von
152 - die Verschlechterung kommt allein vom Zaehler.

Das ist die richtige Richtung fuer eine Aenderung, die ich selbst vorgeschlagen
habe: Sie haette dem Kandidaten helfen koennen (drei Reglerstufen gewinnen
deutlich), aber ausgerechnet er gewinnt nichts.

### Was bleibt

``Effektivwert.knapp`` gibt es weiter, aber mit anderer Bedeutung. Frueher
sagte es an, dass eine **Entscheidung** auf der Kippe stand. Heute gibt es
keine Entscheidung mehr - es sagt an, dass die **Datenlage** keine Aussage
hergibt, und dass die Kuerzung deshalb klein ausfaellt.

Ein Umkehr-Nachweis haelt fest, dass die Schwelle nicht zurueckkommt: Er sucht
im Quelltext nach ``if nachgewiesen`` und faellt um, sobald es wieder dasteht.

Stand: **7 von 11**, Deflated Sharpe 0,843 gegen 0,95, Versuchszaehler **119**
unveraendert - eine Korrektur am Messgeraet ist kein Versuch.

---

## Vierunddreissig. Der Katalog nach der stetigen Kuerzung - und ein Bericht,
## der auf einen Bildschirm passt

### Die Nachpruefung, weil sich das Messgeraet geaendert hat

Nummer dreiunddreissig hat die Klippe im Deflated-Sharpe-Gate beseitigt. Damit
gilt dieselbe Regel wie nach jeder Aenderung am Instrument: **Der ganze Katalog
gehoert neu gemessen** - dafuer gibt es ``cli nachpruefung``, und es kostet
keinen Versuch.

Alle 54 Kandidaten, BTC + ETH, Tageskerzen:

    Kandidat                          Gates   DSR vorher   DSR jetzt
    Trend mit Vola-Ziel 22 %           8/11        0,486       0,452
    Vola-Ziel, kurzes Messfenster      8/11        0,476       0,443
    Trend 50 Tage mit Konfluenz        7/11        0,864       0,843
    Momentum-Beteiligung               5/11        0,106       0,248   <-
    Trend-Beteiligung 50 Tage          5/11        0,086       0,223   <-

**Kein Kandidat wechselt den Rang, keiner besteht.** Die meisten Werte fallen
leicht - das ist der Versuchszaehler, der von 102 auf 119 gestiegen ist.

Interessant sind die drei, die um mehr als 0,05 **steigen**: Es sind genau die
mit starker Abhaengigkeit, die die alte Klippe hart bestraft hat. Sie bekommen
jetzt eine Kuerzung nach Mass statt einer nach Schwellenwert. Das ist die
Bestaetigung der Korrektur an 54 Kandidaten statt an einem Regler - und sie
faellt in die richtige Richtung: Der Spitzenkandidat gewinnt nichts, die
vorher ueberstraften gewinnen.

### Und ein Bericht, der nicht 2400 Zeilen lang ist

Dieses Dokument ist ein Laborbuch: chronologisch, vollstaendig, und fuer die
Frage *wo stehen wir* unbrauchbar. Wer entscheiden soll, braucht drei Dinge -
was gemessen ist, was daraus folgt, und was von ihm selbst abhaengt.

``cli stand`` beantwortet das in vier Teilen:

1. **Der gemessene Stand.** Kandidat, Gates, Abstand zur Grenzlinie,
   Versuchszaehler - alles gerechnet, nichts gepflegt. Es kann nicht veralten,
   ohne dass es auffaellt.
2. **Was untersucht und geschlossen ist.** Zehn Richtungen, jede mit ihrem
   gemessenen Ergebnis und der Nummer im BEFUND. Ein Eintrag ohne Fundstelle
   wird vom Datentyp abgewiesen - sonst wuerde aus einer Messung mit der Zeit
   eine Erzaehlung.
3. **Was nicht bei mir liegt.** Drei Punkte, benannt und beziffert, nicht
   beantwortet: die 15 % Mindestrendite, die Kontogroesse, die
   Wochenverlustgrenze mit ihrer manuellen Freigabe. Ein Test prueft, dass in
   diesen Texten keine Empfehlung steht.
4. **Was nur auf dem Rechner des Nutzers laufen kann** - der Healthcheck und
   der Abgleich, beide durch die Regionssperre dieses Containers blockiert.

### Ein Fehler in der ersten Fassung, vor dem Ausliefern gefangen

Der Bericht schrieb zunaechst: *"Zum haertesten Gate fehlen 110 % der
bisherigen Qualitaet je Trade."* Der Faktor ist 1,10 - gemeint sind **zehn
Prozent mehr**, nicht hundertzehn. So formuliert liest es sich, als fehle mehr
als alles Vorhandene, und in einem Bericht, dessen einziger Zweck eine klare
Lage ist, waere das die schlimmste Sorte Fehler.

Jetzt steht dort: *"Dafuer muesste die Qualitaet je Trade um 10 % steigen:
0,2597 auf 0,2857."* Ein Test haelt die Formulierung fest.

### Stand

    Kandidat          Trend 50 Tage mit Konfluenz, BTC + ETH, Tageskerzen
    Ergebnis          152 Trades, 13,47 % p.a., 10,64 % Rueckgang
    Gates             7 von 11
    Offen             Messlatte, Schlechtestes Jahr, Deflated Sharpe,
                      Parameter-Plateau
    Abstand           10 % mehr Qualitaet je Trade
    Versuche          119 - unveraendert, Nachmessen ist kein Versuch

---

## Fuenfunddreissig. Die Suchmaschine hat die Haelfte ihrer Versuche verschwendet

Alle Regler sind ausgemessen, alle Richtungen geschlossen. Was bleibt, ist die
Suche selbst - also habe ich zum ersten Mal nachgesehen, **was der Wettbewerb
eigentlich variiert**.

### Was er kann, und was nicht

``research/mutation.py`` wandelt immer nur eine Sache auf einmal ab: eine
Periode, eine Schwelle, die Stopweite, ein Ziel. Er erfindet **keine neue
Regel** - kein neuer Indikator, keine neue Bedingung. Er verschiebt Zahlen.

Damit ist eine unangenehme Sache gesagt: Genau diese Zahlen habe ich in den
Nummern einundzwanzig bis zweiunddreissig als Regler ausgemessen, und bei
dreien davon ist der Wert des Kandidaten **das Optimum**. Der Wettbewerb
durchsucht einen Raum, dessen bester Punkt bereits bekannt ist.

Die Research-KI koennte strukturell Neues vorschlagen. Sie bleibt ohne
API-Schluessel unpruefbar - erneut nachgesehen, weiterhin keiner gesetzt.

### Und dann der Befund

Beim Nachsehen fiel etwas auf, das schwerer wiegt. ``mutate`` variiert
``entry`` **oder** ``exit``, jeweils einzeln. Beim Spitzenkandidaten stehen
beide auf demselben SMA(50):

    Original     Einstieg SMA(50)   Ausstieg SMA(50)
    Variante     Einstieg SMA(40)   Ausstieg SMA(50)

Eine Regel, die bei 40 einsteigt und bei 50 aussteigt, widerspricht sich
selbst. Gemessen an 300 Varianten des Spitzenkandidaten:

    300 Varianten, davon 150 mit Einstieg != Ausstieg   (50 %)

**Die Haelfte aller je erzeugten Varianten war eine Regel, die niemand handeln
wuerde** - und jede hat einen Versuch gekostet und die Zulassungshuerde fuer
alle gehoben.

Genau dieser Fehler steckte einmal in den Nachbarn des Plateau-Gates und ist
dort seit langem behoben (Nummer fuenf). In der Mutation stand er noch.

### Dazu die dritte Stelle mit demselben Muster

``SCHRAUBEN`` kannte ``entry``, ``filter``, ``exit``, ``stop``, ``targets``,
``cooldown``, ``hold`` - aber **kein** ``konfluenz``. Sie kam spaeter dazu und
wurde nirgends nachgetragen. Beim Spitzenkandidaten steuert sie die
Positionsgroesse und war damit **ueber die gesamte Suche eingefroren**.

Das ist die dritte Stelle mit derselben Ursache: vorher in
``_estimate_warmup`` (Nummer dreiundzwanzig) und in den Plateau-Nachbarn
(Nummer fuenf). Eine Erweiterung, die an drei Stellen haette nachgetragen
werden muessen, wurde an keiner nachgetragen.

### Behoben

* Wird ein Operand variiert, der auf der **Gegenseite identisch** vorkommt,
  wandert er dort mit. Kein Widerspruch mehr - gemessen: 0 von 300.
* Wo Einstieg und Ausstieg **verschiedene** Groessen meinen, bleibt die
  Asymmetrie erhalten. Ein Test haelt beide Richtungen fest; die Korrektur
  darf nicht zu weit greifen.
* ``konfluenz`` steht in den Schrauben. Von 300 Varianten betreffen jetzt 55
  die Konfluenz.

    vorher   stop 85, entry 77, exit 73, targets 34, cooldown 31
    jetzt    stop 72, entry 67, konfluenz 55, exit 53, cooldown 28, targets 25

### Was das erklaert und was nicht

Es erklaert einen Teil der Trefferquote von 0 aus 53: Ein erheblicher Anteil
der Versuche ging an Regeln, die sich selbst widersprachen. Es erklaert
**nicht**, warum kein Kandidat naeher kam - dafuer ist der Raum, den die
Mutation absucht, schlicht zu klein.

Der Versuchszaehler bleibt bei **119**. Die verschwendeten Versuche sind
verschwendet; sie nachtraeglich abzuziehen waere genau die Sorte Buchhaltung,
die der Deflated Sharpe verhindern soll. Was sie gekostet haben, steht damit
weiter in der Huerde - und das ist richtig so.

Stand unveraendert: **7 von 11**, Deflated Sharpe 0,843 gegen 0,95.

## Sechsunddreissig. Die Suche bestieg einen anderen Berg als die Pruefung

Der Wettbewerb - der Dauerlauf, der Varianten bildet und prueft - lief auf
**einem** Markt. Jede Zulassungszahl dieses Projekts stammt dagegen aus dem
Portfolio BTC + ETH. Beide Zahlen stimmten fuer sich; zusammen ergaben sie
eine Suche, die am Ziel vorbei optimierte.

Wie weit die beiden auseinanderliegen, an demselben Kandidaten gemessen:

    Spitzenkandidat auf BTC allein      5 von 11, Deflated Sharpe 0,190
    Spitzenkandidat auf BTC + ETH       7 von 11, Deflated Sharpe 0,843

Das ist kein Feinschliff. Wer auf BTC allein sucht, waehlt Varianten danach
aus, wie sie sich dort schlagen - und misst sie dann an einer Aufstellung, in
der die Haelfte der Trades von einem Markt kommt, der bei der Auswahl keine
Rolle spielte.

### Und dieselbe Verwechslung eine Ebene tiefer

Neun der elf Gates lesen nur den Walk-Forward. Der bildete das Portfolio
laengst ab, also sahen sie es automatisch. Die beiden **teuren** Gates rechnen
selbst nach - und rechneten weiter auf dem Referenzmarkt allein.

Am Spitzenkandidaten, BTC + ETH, Tageskerzen, nach Gebuehren:

    Kosten-Stress   vorher  +109,64        (nur BTC)
                    jetzt   +942,87        (+109,64 BTC, +833,23 ETH)

ETH trug 88 % des Gewinns unter doppelten Kosten - und war fuer das Gate
unsichtbar. Das Gate bestand vorher wie nachher; die Zahl daneben war um den
Faktor 8,6 falsch.

### Behoben

* ``run_admission`` nimmt ``frames``/``configs`` und laeuft dann ueber das
  Portfolio - im Walk-Forward **und** in den beiden Gates, die nachrechnen.
* ``evaluate_gates`` reicht die Beine an Kosten-Stress und Plateau durch.
  ``frame`` bleibt die Messlatte fuer Buy-and-Hold und Regime-Einteilung; das
  sind Fragen an *einen* Markt, und das ist richtig so.
* Beide Gates urteilen ueber die **Summe** der Beine, nicht ueber jedes
  einzeln. Gehandelt wird die Summe. Ein Test rechnet beide Lesarten aus und
  verlangt, dass sie sich unterscheiden - sonst pruefte er nichts.
* ``cli wettbewerb --maerkte BTCUSD_BITSTAMP,ETHUSD_BITSTAMP`` stellt die Suche
  auf dieselben Beine. Ohne die Option bleibt alles wie bisher.
* Alle fuenf weiteren Stellen, die ein Portfolio berechnen und dann Gates
  darauf werfen (``machbarkeit``, ``nachpruefung``, ``marktkombinationen``,
  ``suchbudget``, der Vola-Abgleich), reichen die Beine jetzt mit durch.

### Was sich am Stand aendert: nichts

    Stichprobengroesse    pass       Monte-Carlo           pass
    Messlatte             fail       Regime-Aufteilung     pass
    Out-of-Sample-Sharpe  pass       Deflated Sharpe       fail   0,8373
    Drawdown              pass       Kosten-Stress         pass   +942,87
    Schlechtestes Jahr    fail       Parameter-Plateau     fail   0,500
    Bestaendigkeit        pass

**7 von 11, unveraendert.** Die Korrektur hat die Buchhaltung geradegezogen,
nicht das Urteil. Das gehoert genauso berichtet wie ein Erfolg - ein Fehler in
der Messung ist auch dann einer, wenn er zufaellig folgenlos blieb.

### Nebenbefund, unbehandelt

``_vary_periods`` erzeugt fuer diesen Kandidaten genau **zwei** Nachbarn. Das
Plateau-Gate kann damit nur 0,0, 0,5 oder 1,0 zurueckgeben - bei einer Schwelle
von 0,6 heisst das: beide Nachbarn muessen profitabel sein, sonst nichts. Ein
Gate mit drei moeglichen Werten ist kein Plateau-Test, sondern ein Muenzwurf
mit zwei Wuerfen. Gemessen an den Beinen:

    Nachbar 1   BTC +1142,14   ETH  -58,67   Summe +1083,47   profitabel
    Nachbar 2   BTC   -29,68   ETH  -75,00   Summe  -104,68   nicht

Das ist der naechste Schritt: die Aufloesung des Gates, nicht seine Schwelle.

## Siebenunddreissig. Das Plateau-Gate stand selbst auf einer Nadel

Das Gate fragt, ob eine Strategie auf einem Plateau steht oder auf einer
Nadelspitze. Seine eigene Begruendung nennt das Beispiel: *"EMA(47) gewinnt,
EMA(46) und EMA(48) verlieren."* Gemessen hat es genau das nie.

Es kannte **zwei** Nachbarn: alle Perioden um 20 % kuerzer, alle um 20 %
laenger. Das ist eine Gerade durch den Parameterraum, mit zwei Punkten darauf.
Zwei Folgen:

* Der Anteil konnte nur 0, 0,5 oder 1 sein. Bei einer Schwelle von 0,6 hiess
  das in Wahrheit **beide muessen halten** - eine 100-%-Regel, die so nirgends
  aufgeschrieben stand.
* Eine Nadel in *einer* Dimension war unsichtbar, weil nie eine Periode allein
  bewegt wurde. Der Namensgeber des Gates war sein blinder Fleck.

### Warum es nicht einfach mehr Nachbarn sein durften

Der naheliegende Schritt - jede Periode einzeln verschieben - haette einen
Fehler wiederholt, der hier schon einmal stand: Der Spitzenkandidat steigt
ueber ``sma(50)`` ein und darunter aus. Wer nur den Einstieg auf 40 zieht, baut
eine Regel, die sich selbst widerspricht.

Die Einheit ist deshalb der **Operand**, nicht die Zahl: ``sma(50)`` kommt
dreimal vor - Einstieg, Ausstieg, Konfluenz - und wandert als eines. Zwei
*verschiedene* Operanden duerfen dagegen einzeln wandern; ``sma(50) > sma(160)``
statt ``> sma(200)`` ist ein voellig normaler Trendfilter, und die Frage, ob
die 200 eine Zauberzahl ist, laesst sich anders gar nicht stellen.

Aus 2 Nachbarn werden so 12: fuenf Stellgroessen mal zwei Richtungen, plus die
gemeinsame Verschiebung.

### Und warum der Durchschnitt daraus die falsche Zahl ist

Der Spitzenkandidat auf BTC + ETH, Tageskerzen, 12 Nachbarn:

    alle gemeinsam    1 von 2      sma(200)         2 von 2
    sma(50)           1 von 2      roc(90)          2 von 2
    rsi(14)           2 von 2      Vola-Fenster     2 von 2

Zehn von zwoelf profitabel - **0,833, das Gate haette bestanden.** Nur heisst
das nichts: Ob ``rsi(14)`` auf 11 oder 17 steht, aendert das Ergebnis um
weniger als ein Prozent. Vier wirkungslose Regler haetten die eine Dimension
niedergestimmt, an der die Strategie haengt. Je mehr belanglose Zahlen ein
Genom traegt, desto leichter waere das Gate geworden.

Gewertet wird deshalb die **schwaechste Richtung**, nicht der Durchschnitt. Ein
Plateau ist man in jeder Richtung oder gar nicht.

Das hat eine Eigenschaft, auf die es hier ankommt: Die gemeinsame Verschiebung
- der komplette alte Test - ist eine der Stellgroessen. Ein Minimum ueber eine
Menge, die sie enthaelt, liegt nie ueber ihr. **Das Gate kann durch den
groesseren Bereich nirgends milder werden, nur strenger.** Ein Test haelt das
an drei Datensaetzen fest; ein zweiter zeigt einen Fall, in dem der alte Test
bestanden haette und der neue durchfaellt.

### Ergebnis

    Parameter-Plateau   vorher  0,500  fail
                        jetzt   0,500  fail

Dasselbe Urteil, dieselbe Zahl - aber jetzt mit einer Adresse:

    alle gemeinsam 1/2, sma(period=50) 1/2, Vola-Fenster 2/2,
    roc(period=90) 2/2, rsi(period=14) 2/2, sma(period=200) 2/2

**Der gesamte Vorteil des Kandidaten haengt an der 50, und nur nach einer
Seite.** Auf 40 verkuerzt bleibt er profitabel (+838 gegen +930 im Original),
auf 60 verlaengert kippt er ins Minus (-106). Die anderen vier Perioden sind
austauschbar. Das ist kein Plateau, das ist eine Kante - und es ist die erste
konkrete Auskunft darueber, *woran* dieser Kandidat haengt.

Stand unveraendert: **7 von 11**, Versuchszaehler 119.

## Achtunddreissig. Vier von fuenf Perioden bewirken nichts

Die vorige Messung hatte den Kandidaten auf eine Dimension eingegrenzt: Der
Vorteil haengt am 50-Tage-Schnitt, und nur nach einer Seite. Offen blieb die
Frage, die die Landschaftskarte in ihrer eigenen Einleitung stellt:

* Nur 50 funktioniert, 40 und 60 nicht - dann war der Treffer Zufall.
* 30 bis 55 funktionieren, ab 60 nicht mehr - dann gibt es einen echten
  Bereich, und die 50 sitzt nur unguenstig an dessen Kante.

Die Karte konnte das nicht beantworten, weil sie **alle** Perioden zugleich
verschob. Jetzt kann sie eine einzelne abtasten (``cli landschaft --regler``).
BTC + ETH, Tageskerzen, halber bis doppelter Wert:

    sma(50)      25   30   35   40   45   50   55   62   70   80   90  100
                +294 +730 +524 +419 +486 +478 +228  -47   +5   -8   -9  -36
                  +    +    +    +    +    +    +    -    +    -    -    -
                                      ^Kandidat

**Es ist der zweite Fall.** Von 25 bis 55 traegt die Regel durchgehend - sieben
Punkte am Stueck, der Kandidat mittendrin. Ab 62 kippt sie. Die 50 sitzt am
**oberen Rand** ihres eigenen Plateaus, und deshalb faellt der Nachbar bei
+20 % durch, waehrend der bei -20 % haelt.

### Der eigentliche Befund: die Konfluenz ist Zierat

Dieselbe Karte fuer die vier uebrigen Stellgroessen, jeweils ueber den halben
bis doppelten Wert:

    sma(200)     100 bis 400      +461 bis +478      12 von 12 profitabel
    roc(90)       45 bis 100      +459 bis +479       8 von 8
    rsi(14)        7 bis  28      +455 bis +513      12 von 12
    Vola-Fenster  15 bis  60      +338 bis +738      12 von 12

Ueber den **vierfachen** Wertebereich aendert sich beim 200er-Schnitt das
Ergebnis um 3 %, beim ROC um 4 %, beim RSI um 12 %. Die Trade-Zahl bleibt bei
allen dreien praktisch konstant (93 gegen 86). Diese drei Bedingungen bilden
zusammen die Konfluenz, die die Positionsgroesse steuern soll - und sie
steuern nichts. Sie sind offenbar fast immer erfuellt, der Konviktions-Bonus
liegt praktisch dauerhaft an.

Der Kandidat hat also nicht fuenf Parameter, sondern **einen**: die 50. Die
uebrigen vier sind Verzierung. Das ist keine gute Nachricht und keine
schlechte, sondern eine Auskunft darueber, was hier eigentlich gemessen wird -
eine einzelne Trendfolge, kein Zusammenspiel.

### Ein Fehler, gefunden beim Bauen

Die Karte unterschied ihre Punkte an der **Leitperiode**, der laengsten
Periode im Genom. Beim Abtasten einer einzelnen Stellgroesse bleibt die
konstant: Wer nur die 50 verschiebt, laesst die 200 stehen. Jeder Punkt ausser
dem ersten waere als Duplikat verworfen worden, und die Karte haette aus genau
einem Punkt bestanden - ohne Fehlermeldung, ohne dass es aufgefallen waere.
Unterschieden wird jetzt am Genom selbst. Ein Test haelt es fest.

Dazu ein zweiter, kleinerer: Die Beschriftung suchte den Operanden in der
**Variante** statt im Original. Dort heisst er laengst ``sma(period=25)`` und
passt auf nichts mehr - die Tabelle zeigte fuer jeden Punkt ausser dem
Kandidaten die 200. Beim ersten Durchlauf auf echten Daten sofort sichtbar.

### Was daraus nicht folgt

Der beste Punkt der Karte liegt bei 30 (+730 gegen +478). Ihn zum neuen
Kandidaten zu erklaeren waere genau die Ueberanpassung, gegen die das
Plateau-Gate gebaut ist - mit dem Zusatz, dass die Karte selbst elf Versuche
gekostet hat und die Huerde entsprechend hoeher liegt.

Versuchszaehler **119 -> 130**: die elf Punkte der ersten Karte. Die
Wiederholungen fuer die Fehlersuche liefen ausserhalb des Zaehlers - dieselben
Punkte zweimal zu rechnen ist keine zweite Hypothese.

Stand unveraendert: **7 von 11**.

## Neununddreissig. Ich haette hier fast einen Befund berichtet, den es nicht gibt

Zwei Messungen zuvor stand die Vermutung, die Konfluenz des Kandidaten sei
"fast immer erfuellt". **Das war falsch**, und ``cli konfluenz`` sagt es
deutlich:

    0 Bedingungen   14 Trades   +0,194 R
    1 Bedingung     60 Trades   +1,534 R
    2 Bedingungen   27 Trades   -0,427 R
    3 Bedingungen   51 Trades   +2,688 R    rho +0,150, p = 0,062

Die Bedingungen wechseln also durchaus. Sie sind nur nicht **der Reihe nach**
besser, und der Zusammenhang ist nicht belegt. Der Grund, warum das Verstellen
ihrer Perioden nichts bewirkt, ist damit ein anderer als vermutet: nicht "immer
an", sondern "an in einem Muster, das nichts bedeutet". Die
Konviktions-Groessenlogik verteilt den Einsatz entlang einer Ordnung, die es
nicht gibt.

### Also gesucht: gibt es irgendeine Ordnung?

Der Mechanismus ist gebaut und wirkungslos, weil er an den falschen
Bedingungen haengt. Neu ist deshalb ``cli trennschaerfe``: zwoelf **vorab
festgelegte** Merkmale, je Trade am Einstiegsbalken ausgewertet, verglichen
ueber Wilcoxon-Rangsummen statt Mittelwerte - bei R-Verteilungen mit einzelnen
+20-R-Treffern sagt ein Mittelwertvergleich mehr ueber den groessten Gewinner
als ueber die Trennung.

Das Ergebnis auf BTC + ETH, 152 Trades:

    Bollinger-Breite hoch     59 / 93    +0,167 gegen +2,263    z = -2,91
    Umsatz hoch               75 / 77    +0,916 gegen +1,970    z = -1,73
    Volatilitaet hoch         64 / 88    +0,455 gegen +2,174    z = -1,73
    ADX(14) ueber 25          38 / 114   +0,975 gegen +1,608    z = -1,56
    Realisierte Vola hoch     70 / 82    +1,002 gegen +1,832    z = -1,52

Fuenf Volatilitaetsmasse, alle in dieselbe Richtung: Wer in bereits weite
Baender hinein einsteigt, faehrt schlechter. Wirtschaftlich einleuchtend - ein
Ausbruch nach einer Ruhephase ist der klassische Aufbau, einer in schon hohe
Bewegung hinein ist spaet.

**Die freie Permutationsnull haette das durchgewinkt:** Schranke fuer das Beste
aus zwoelf bei 2,80, beobachtet 2,91. Belegt, haette dort gestanden.

### Warum es trotzdem nichts ist

Die Merkmale sind ueber die Zeit nicht gleichmaessig verteilt. "Bollinger-
Breite hoch" faellt 2021 auf 18 von 21 Trades und 2025 auf 2 von 17:

    Jahr    breit  eng    R breit   R eng
    2018      4     4      -1,08    -0,81
    2019      9    11      -0,76    +2,81
    2020      4    14      +6,03    +4,87
    2021     18     3      +0,15   +12,77
    2022     14     6      -0,89    -0,79
    2023      3    16      +1,52    +2,37
    2024      5    18      -1,07    +1,67
    2025      2    15      +3,79    +1,12

In 6 von 8 Jahren zeigt es in dieselbe Richtung - das spricht gegen einen
reinen Kalendereffekt. Aber ein Merkmal, das ueberwiegend **schlechte Jahre
markiert**, sieht in einer freien Permutation aus wie eine Trennung, ohne eine
zu sein.

Gemischt wird deshalb **innerhalb der Jahre**: Die Zusammensetzung jedes Jahres
bleibt, nur die Zuordnung Ergebnis-zu-Trade faellt weg. Wer damit noch trennt,
trennt innerhalb der Jahre.

    Schranke frei gemischt        2,80      beobachtet 2,91  -> belegt
    Schranke blockweise           3,83      beobachtet 2,91  -> nicht belegt

**Nicht belegt.** Der Unterschied zwischen den beiden Zahlen ist genau das,
was die Jahre erklaeren.

### Was das heisst

Kein Merkmal aus diesem Katalog trennt die Trades dieses Kandidaten, sobald man
beides beruecksichtigt: dass zwoelf geprueft wurden und dass sie sich in den
Jahren zusammenballen. Die Konviktions-Groessenlogik hat nichts, woran sie sich
halten koennte - nicht, weil nicht gesucht wurde.

Und der eigentliche Ertrag dieses Abschnitts ist unangenehmer: Ohne die
Blockvariante haette hier ein Befund gestanden, und der naechste Schritt waere
gewesen, einen Kandidaten darauf zu bauen. Der Test, der das festhaelt, steht in
``tests/test_trennschaerfe.py`` und verlangt ausdruecklich, dass die freie Null
das erfundene Jahres-Merkmal durchwinkt und die blockweise es ablehnt. Faellt
die Blockvariante je weg, faellt dieser Test.

Der Versuchszaehler bleibt bei **130**: Hier wurde kein Backtest gerechnet,
sondern eine vorhandene Trade-Liste geteilt. Stand unveraendert: **7 von 11**.

## Vierzig. Der Weg zum Demo-Handel - und eine Fehlermeldung, die im Kreis schickte

Der Nutzer will anfangen zu handeln. Nachgesehen statt geschaetzt: Die Website
laeuft (HTTP 200, die API antwortet mit ``"alive": false, "status_text": "nie
gestartet"``), aber ``strategies/`` enthaelt nur dieses Laborbuch. ``start.sh``
bricht ab, mit gutem Grund.

### Zwei Dinge heissen "Demo" und pruefen Verschiedenes

    Anlagentest    Orders, Stops, Neustart mitten in einer Position,
                   Telegram, Not-Aus            ->  prueft die **Technik**
    Dreissig Tage  Live-Kennzahlen gegen die Backtest-Erwartung
                                                ->  prueft die **Strategie**

Der Anlagentest geht heute und ist genau das, was von hier aus nicht geht -
der Entwicklungscontainer ist regionsgesperrt. Die dreissig Tage gehen nicht:
Sie vergleichen eine zugelassene Strategie mit dem, was der Backtest
versprochen hat, und es gibt keine zugelassene.

``cli anlagentest`` legt den Spitzenkandidaten als Datei ab. Der Hinweis steht
**im Namen** der Strategie, nicht in einem Kommentar:

    NICHT ZUGELASSEN (Anlagentest) - Trend 50 Tage mit Konfluenz

Damit taucht er ueberall auf, wo die Strategie genannt wird - Dashboard,
Telegram-Meldungen, Journal. Die Kennung bleibt unveraendert bei
``111cc2ecd5d53968``: ``name`` und ``rationale`` fliessen nicht in den Hash
ein, und das ist hier keine Kleinigkeit, sondern die Voraussetzung dafuer,
dass alle bisherigen Messungen weiter zu dieser Datei gehoeren.

### Die Sperre, die dieser Bequemlichkeit vorausgehen muss

Bisher pruefte ``cli trade`` beim Echtgeld nur die **Umgebung** - steht
``BYBIT__ENVIRONMENT`` auf mainnet, dann bitte ``--echtgeld`` dazu. Welche
*Strategie* dabei laeuft, war egal: ``--strategie`` nahm jede Datei. Solange
es keinen einfachen Weg gab, ein nicht zugelassenes Genom abzulegen, fiel das
nicht auf. Mit ``cli anlagentest`` gibt es ihn.

Deshalb zuerst die Bremse, dann die Bequemlichkeit:

    Echtgeld gibt es nur, wenn die genome_id mit champion.json uebereinstimmt.

Verglichen wird die **Kennung**, nicht der Dateiname. Eine Datei laesst sich
umbenennen und an die richtige Stelle legen, der Hash ueber die Regeln nicht.
Ein Test schiebt genau das unter und verlangt den Abbruch; ein zweiter prueft
die Gegenrichtung, denn eine Sperre, die auch den Champion aufhaelt, waere ein
Fehler und keine Sperre.

Auf Demo laeuft das Genom - mit einem Banner, das sagt, was gerade geprueft
wird und was nicht.

### Und der Fehler, der schon laenger dalag

Das Dashboard meldet ohne Passwort: *"Kein WEB__PASSWORD_HASH gesetzt -
Steuerung ist gesperrt."* Der Schluessel heisst aber **WEB__PASSWORD**. Ein
Hash waere hier ohnehin Sicherheitstheater - wer die ``.env`` lesen kann, hat
die API-Zugangsdaten, und die sind mehr wert; so steht es auch in
``core/config.py``.

Wer der Meldung folgte, trug den falschen Namen ein, startete neu und bekam
dieselbe Meldung wieder. Auf genau diesem Weg liegt der **Not-Aus**: Ohne
Passwort bleibt die Ansicht, aber Pause, Glattstellen und Not-Aus sind
gesperrt. Zwei Zeichenketten, und sie standen zwischen dem Nutzer und dem
Knopf, den er im Ernstfall braucht.

Der Test dazu prueft nicht den Quelltext, sondern die Antwort, die der Nutzer
bekommt - HTTP 403 mit dem Namen der Einstellung, und der Name kommt aus dem
Einstellungsmodell statt danebengeschrieben.

### Was der Nutzer jetzt tun kann

    1  python -m cli healthcheck    bietet das Konto ueberhaupt Perpetuals?
    2  python -m cli backfill --intervall 15
    3  ./start.sh --anlagentest     Website und Handel zusammen

``--anlagentest`` ist ein eigener Schalter und kein stiller Rueckfall: Wer ihn
tippt, weiss, dass die Klempnerei geprueft wird. Der eigentliche Test ist
unbequem und zaehlt am meisten - den Prozess mitten in einer offenen Position
hart abschiessen und bei Bybit nachsehen, ob der Stop noch an der Position
haengt.

Versuchszaehler unveraendert bei **130** - hier wurde nichts gemessen, was
eine Strategie betrifft. Stand: **7 von 11**.

## Einundvierzig. Ein Champion haette aus neun Gates entstehen koennen

Beim Durchgehen des Plans, kurz vor dem ersten Wettbewerbslauf, an der Stelle
nachgesehen, an der es zaehlt. Der Hilfetext von ``cli wettbewerb`` sagt:

    --schnell/--vollstaendig
    "Vorauswahl mit 7 Gates. Die Zulassung laeuft am Ende mit allen."

**Es lief nie etwas mit allen.** Die Schleife reicht ``run_expensive=not
schnell`` in jede Runde durch, und danach kommt nichts mehr. Im Standardfall -
und das ist der Fall, in dem dieser Befehl benutzt wird - laufen Kosten-Stress
und Parameter-Plateau kein einziges Mal.

Der Rest ergab sich aus einer einzigen Zeile:

    GateReport.passed = all(r.passed for r in self.results)

Bei neun Ergebnissen heisst das neun von neun. Ein Kandidat, der die neun
schnellen Gates besteht, galt damit als zugelassen, wurde Champion und landete
in ``champion.json`` - ohne die beiden teuersten Gates je gesehen zu haben.

An genau dieser Datei haengt seit dem vorigen Abschnitt das **echte Geld**:
``cli trade`` gibt Mainnet nur frei, wenn die Kennung mit ``champion.json``
uebereinstimmt. Eine Sperre, die eine Datei schuetzt, welche selbst nicht
vollstaendig geprueft wurde, schuetzt nichts. Die beiden Fehler zusammen waren
gefaehrlicher als jeder fuer sich.

### Behoben

* ``GateReport`` weiss jetzt, ob es eine Vorauswahl war. ``passed`` verlangt
  eine **vollstaendige** Pruefung; fuer die schwaechere Frage gibt es
  ``geprueftes_bestanden``.
* Wer die Vorauswahl besteht, bekommt in ``run_admission`` sofort den
  Nachschlag mit allen elf. Das kostet nur fuer die wenigen Kandidaten
  Rechenzeit, die so weit kommen - und **nicht** einen zweiten Versuch:
  Dasselbe Genom genauer zu messen ist keine zweite Hypothese.
* Der Hilfetext sagt jetzt, was passiert.

Dieselbe Luecke war in ``cli nachpruefung`` schon einmal aufgetreten und dort
mit ``Ergebnis.vorauswahl`` geschlossen worden (Abschnitt vierundzwanzig). Sie
im Wettbewerb stehenzulassen, war ein halber Fix - und der gefaehrlichere
Zweig war der, der uebrig blieb.

## Zweiundvierzig. Sechzehn Versuche, kein Fortschritt - und was das kostet

Der Plan sieht vor, den Wettbewerb auf **derselben Aufstellung** laufen zu
lassen, auf der geprueft wird. Das ist seit Abschnitt sechsunddreissig
moeglich und war nie gelaufen.

Dazu ein zweiter Startpunkt: ``--von-spitze`` beginnt mit Varianten des besten
bekannten Kandidaten statt mit einem Katalog. Aus einem Katalog heraus
verbringt die Suche die ersten Runden damit, sich an ein Niveau
heranzuarbeiten, das laengst bekannt ist - und jeder dieser Versuche hebt die
Huerde fuer alle spaeteren. Der Spitzenkandidat selbst wird dabei nicht noch
einmal geprueft; sein Ergebnis steht.

    cli wettbewerb -i D -m BTCUSD_BITSTAMP,ETHUSD_BITSTAMP --von-spitze
                   --runden 2 --varianten 8

Sechzehn Varianten, BTC + ETH, Tageskerzen. Ergebnis, nach Deflated Sharpe:

       DSR  Gates  Trades   Erw. R   offen
     0,829   6/9     152    +1,450   Messlatte, Schlechtestes Jahr, DSR
     0,824   6/9     152    +1,232   Messlatte, Schlechtestes Jahr, DSR
     0,787   7/9     136    +1,517   Messlatte, DSR
     0,761   7/9     136    +1,517   Messlatte, DSR

**Kein Kandidat besser als der Ausgangspunkt.** Der Spitzenkandidat stand bei
0,830; die beste Variante erreicht 0,829.

Zwei Beobachtungen sind trotzdem etwas wert:

* Es **gibt** Varianten, die das Gate "Schlechtestes Jahr" bestehen - der
  Spitzenkandidat scheitert daran. Sie erkaufen es mit 136 statt 152 Trades,
  und weniger Trades heissen niedrigeren Deflated Sharpe. Die beiden Gates
  ziehen gegeneinander.
* Die Varianten, die nur die **Konfluenz** aendern, kommen auf exakt dieselben
  152 Trades und praktisch denselben Wert. Das ist Abschnitt achtunddreissig
  aus einer unabhaengigen Richtung bestaetigt: Die Konfluenz bewirkt nichts.

### Was der Lauf gekostet hat

Versuchszaehler **130 -> 146**. Sechzehn Versuche heben die noetige Qualitaet
je Trade um 16 x 0,00021 = 0,0034. Der Lauf hat also nichts gefunden und das
Ziel ein Stueck weiter weggeschoben.

Das ist kein Argument gegen Suchen - es ist das Argument dafuer, **gezielt** zu
suchen. Die Mutation variiert Zahlen, und die Zahlen-Richtungen sind
ausgemessen. Was fehlt, ist eine Regel mit anderer Struktur, und dafuer gibt es
genau ein Werkzeug im Haus: ``research/analyst.py``. Sie braucht einen
API-Schluessel, der nicht gesetzt ist.

Stand unveraendert: **7 von 11**, jetzt bei 146 Versuchen.

## Dreiundvierzig. Das schlechteste Jahr ist ein einziges Jahr

Von den vier Gates, an denen der Spitzenkandidat scheitert, ist dieses der
schmalste Fehlschlag im System: **-10,32 % gegen -10,00 %**. Zweiunddreissig
Hundertstel. Bei so einem Abstand ist die Frage, woraus die Zahl besteht, mehr
wert als jeder weitere Suchlauf - und sie kostet keinen Versuch, weil nichts
Neues gerechnet wird.

Das Gate gibt nur das Minimum ueber alle rollierenden Zwoelfmonatsfenster
zurueck. Damit sehen zwei sehr verschiedene Lagen gleich aus: ein einzelnes
unguenstig ausgerichtetes Fenster, oder ein Viertel aller Fenster.

``cli jahresbild``, BTC + ETH, Tageskerzen:

    Fenster gesamt             2465
    davon unter Schwelle          2   (0,1 %)

    schlechtestes            -10,32 %
    zweitschlechtestes*        +0,76 %      * ohne Ueberlappung
    Median                   +11,51 %
    bestes                   +69,10 %

    schlechtestes Jahr     2021-11-08 bis 2022-11-08

**Zwei von 2465.** Es ist eine Spitze, keine Hochebene - und zwar genau das
Jahr vom Hoch 2021 bis zum Tief 2022. Das zweitschlechteste Fenster, das sich
damit nicht ueberschneidet, steht bei **+0,76 %**. Ausserhalb dieses einen
Jahres gibt es keinen einzigen Zwoelfmonatszeitraum, in dem man Geld verloren
haette.

### Woraus dieses Jahr besteht

    24 Trades zusammen   -21,45 R
    groesster Einzelverlust  -1,45 R  (ETH, 26.10.2022)

**Kein Ausreisser, ein Zermuerben.** Vierundzwanzig Trades, keiner davon eine
Katastrophe, zusammen minus einundzwanzig R. Das ist die Signatur einer
Trendfolge in einem anhaltenden Abwaertsmarkt: Sie steigt ein, wird
ausgestoppt, steigt wieder ein. Kein engerer Stop und keine bessere
Ausfuehrung aendern daran etwas - das ist, was diese Regelfamilie in so einem
Jahr tut.

### Was daraus ausdruecklich nicht folgt

"Die Schwelle ist zu streng, es sind ja nur zwei von 2465." Das waere ein
Missverstaendnis des Gates. Es fragt nach dem **unguenstigsten** Einstieg, und
dessen Seltenheit ist kein Einwand, sondern seine Definition. Wer 2021 am Hoch
angefangen haette, stuende ein Jahr spaeter bei -10,3 %, und das ist der
Zeitpunkt, an dem Leute aufhoeren. Die Schwelle bleibt, wo sie ist.

### Was daraus folgt: warum zwei Gates gegeneinander ziehen

Der Wettbewerbslauf davor hatte gezeigt, dass es Varianten gibt, die
"Schlechtestes Jahr" bestehen - mit 136 statt 152 Trades, und damit
schlechterem Deflated Sharpe. Jetzt ist klar, warum: Beide Gates urteilen ueber
**dasselbe Jahr**. Wer 2021/22 weniger handelt, besteht das eine und verliert
am anderen. Die beiden Fehlschlaege sind nicht zwei Probleme, sondern eines,
von zwei Seiten betrachtet.

### Die Rechnung des Gates selbst - geprueft und in Ordnung

``worst_rolling_return`` schaetzt die Fensterbreite ueber Indizes:
``spanne = len(kurve) * 12 / gesamtmonate``. Das setzt gleichmaessig verteilte
Kurvenpunkte voraus, und bei einem Fehlschlag um 0,32 Punkte waere eine
Naeherung eine mogliche Ursache. Also am Kalender nachgerechnet:

    ueber Indizes    -10,32 %
    am Kalender      -10,32 %      Unterschied -0,00 Punkte

**Kein Messfehler.** Die Naeherung haelt, weil die Testfenster lueckenlos
aneinanderstossen und Tageskerzen gleichmaessig dicht liegen. Das ist ein
Ergebnis, auch wenn nichts zu reparieren war - und die Richtung, in der ein
Fehler bequem gewesen waere, macht es wichtiger, dass es dasteht.

Zwei Umsetzungen derselben Kapitalkurve gibt es damit jetzt: die des Gates und
die mit Zeitstempeln. Ein Test haelt sie Wert fuer Wert aneinander - das
Auseinanderlaufen zweier Umsetzungen derselben Groesse ist in diesem Projekt
schon viermal passiert.

Versuchszaehler unveraendert bei **146**. Stand: **7 von 11**.

## Vierundvierzig. Neun von elf - und weiter weg als vorher

Aus der Zerlegung des schlechtesten Jahres kam ein Verdacht mit einem Namen:
Die 24 Verlusttrades dort sind kein Ausreisser, sondern eine Trendfolge, die im
Abwaertsmarkt einsteigt, ausgestoppt wird und sofort wieder einsteigt. Die
**Abkuehlung** (``cooldown_bars``) ist die einzige Stellschraube, die genau
daran ansetzt - und sie stand beim Spitzenkandidaten auf null, ungemessen.

Als Regler in die Machbarkeitsliste aufgenommen und abgetastet, BTC + ETH,
Tageskerzen:

    Kerzen  Trades   CAGR   SR/Trade    DSR   Schl.Jahr  Plateau  Gates
         0     152  13,47 %   0,2597  0,813    -10,32     0,50     7/11
         3     140  11,60 %   0,2599  0,750     -9,79     1,00     9/11
         5     128   9,52 %   0,2529  0,626     -9,47     1,00     9/11
        10     104   5,56 %   0,1652  0,055     -7,97     0,50     6/11
        20      92   6,44 %   0,2097  0,132     -6,06     0,50     7/11
        40      75   4,07 %   0,2066  0,064     -6,73     0,00     6/11

**Neun von elf.** Die beste Gate-Zahl, die dieses Projekt je gesehen hat. Bei
drei Kerzen Abkuehlung bestehen *Schlechtestes Jahr* **und** *Parameter-Plateau*
- zwei der vier offenen Gates auf einmal.

### Und trotzdem ist es ein Rueckschritt

    Deflated Sharpe    0,813  ->  0,750     Ziel 0,95
    Messlatte (CAGR)  13,47 % -> 11,60 %    Ziel 15 %

Die beiden Gates, die uebrig bleiben, sind **weiter weg als vorher**. Neun von
elf klingt nach Fortschritt und ist an dieser Stelle das Gegenteil.

Genau davor warnt der Sortierschluessel der Bestenliste seit Abschnitt
neunzehn: *"Die Zahl bestandener Gates ist eine irrefuehrende Rangfolge"* - wer
weniger riskiert, besteht die Risiko-Gates und verliert am Deflated Sharpe.
Hier steht derselbe Mechanismus noch einmal, auf einem neuen Regler und mit
einer Zahl, die zum Selbstbetrug einlaedt. Der Deflated Sharpe steht im
Schluessel deshalb **vor** der Gate-Zahl, und das war richtig so.

### Warum eine Verfeinerung nichts brachte - ohne sie zu messen

Die naheliegende Fortsetzung waere, den ungemessenen Zwischenraum zwischen 0
und 3 abzutasten: Vielleicht liegt dort eine Stellung, die das schlechteste
Jahr repariert, ohne so viele Trades zu kosten.

Sie liegt dort nicht, und das folgt aus den gemessenen Punkten. Der Deflated
Sharpe ist bei **null** am hoechsten (0,813) und faellt von dort monoton. Kein
Zwischenwert kann ueber 0,813 liegen, das Ziel sind 0,95. Der Regler kann die
Zulassung nicht herstellen - **egal, wie fein man ihn abtastet.**

Das ist der Punkt, an dem eine Verfeinerung nur Versuche kosten und die Huerde
weiter anheben wuerde. Sie unterbleibt.

### Was jetzt fuenffach gemessen ist

    Regler              bester SR/Trade    beim Kandidaten
    Vola-Ziel                    0,2597           0,2597
    Stop-Weite                   0,2597           0,2597
    Perioden-Faktor              0,2597           0,2597
    Konviktions-Bonus            0,2597           0,2597
    Abkuehlung                   0,2599           0,2597

**Fuenf Regler, und keiner hebt die Qualitaet je Trade.** Der beste Wert liegt
bei allen fuenf beim Kandidaten selbst oder um 0,0002 daneben. Alles, was ein
Regler bewegt, ist die **Menge** - Positionsgroesse, Trade-Zahl, Rueckgang. Die
Guete einer einzelnen Entscheidung ist eine Eigenschaft der Regel, nicht ihrer
Zahlen.

Und genau diese Guete verlangt der Deflated Sharpe: 0,2597 muessten 0,2879
werden, elf Prozent mehr. Von den fuenf Reglern kann das keiner liefern, und
sie sind jetzt alle gemessen.

Zwoelfte geschlossene Richtung. Versuchszaehler **146 -> 151**. Stand:
**7 von 11** - der Kandidat bleibt, wo er war, denn die beste Stufe
herauszupicken waere die Ueberanpassung, gegen die die ganze Strecke gebaut
ist.

## Fuenfundvierzig. Vier Eingaenge, drei Wege, einer davon nie betreten

Nach zwoelf geschlossenen Richtungen war die Frage nicht mehr "was probiere
ich als naechstes", sondern "**woran haengt das haerteste Gate eigentlich**".
Der Deflated Sharpe hat vier gemessene Eingaenge, und die Grenzlinie zeigte
bisher nur einen davon.

Also alle vier einzeln geloest - wo muesste jeder stehen, damit das Gate
haelt, alles andere unveraendert? Spitzenkandidat, BTC + ETH, Tageskerzen,
151 Versuche:

    Qualitaet je Trade        0,260  ->    0,292     (+12 %)
    unabhaengige Trades         152  ->      199     (+31 %)
    Schiefe                   3,438  ->    4,424     (+29 %)
    Woelbung                 15,742       unerreichbar

**Die Woelbung ist keine Option**, und zwar nicht knapp: Unter 1 liegt keine
Verteilung, und selbst bei 1 haelt das Gate nicht. Der Weg ist zu, nicht eng.

**Die Schiefe hat noch nie jemand gemessen.** Alle bisherigen Richtungen
zielten auf die ersten beiden Eingaenge - mehr Qualitaet oder mehr Trades. Die
Form der Verteilung ist der dritte, und er stand nie auf der Liste.

Was dabei sichtbar wird: Die schiefe Verteilung des Kandidaten **hilft ihm
bereits erheblich**. Im Nenner der Formel steht 0,597 statt der 1,016 einer
Normalverteilung - sein langes rechtes Ende senkt die Huerde um rund dreissig
Prozent. Ohne diesen Vorteil stuende der Deflated Sharpe deutlich tiefer.

### Ein Fehler, der dabei auffiel

``research/suchbudget.py`` rechnete die Grenzlinie mit **festen** Konstanten:

    SCHIEFE = 3.473
    WOELBUNG = 15.951

Das sind die Werte des Spitzenkandidaten. Sie galten damit fuer **jeden**
Kandidaten, der an der Linie gemessen wurde. Fuer eine Regel mit anderer Form
- etwa eine, die haeufiger und kleiner gewinnt - war die genannte Anforderung
schlicht die eines fremden Genoms.

Wie viel das ausmacht, zeigt derselbe Nenner: 0,597 gegen 1,016 sind siebzig
Prozent Unterschied in dem, was verlangt wird. ``Kandidat`` traegt seine Form
jetzt selbst; wo sie fehlt, gilt die Voreinstellung weiter, aber als benannte
Naeherung.

### Und eine dritte Umsetzung derselben Groesse

"Sharpe je Trade" wurde an **drei** Stellen gerechnet: zweimal in ``cli.py``
und einmal als ``_sharpe_je_trade``. Jetzt an einer - ``Kandidat.aus_trades``
liefert alle vier Groessen zusammen, und der Rest reicht durch. Ein Test haelt
fest, dass die Hilfsfunktion nicht mehr selbst rechnet.

Das Auseinanderlaufen zweier Umsetzungen derselben Groesse ist in diesem
Projekt fuenfmal aufgetreten. Diesmal ist es aufgefallen, bevor die Zahlen
auseinandergingen.

### Wohin das zeigt

Von den drei offenen Wegen sind zwei ausgemessen: Qualitaet je Trade bewegt
kein Regler (fuenffach belegt, Nummer vierundvierzig), und mehr unabhaengige
Trades bringen weder mehr Maerkte noch mehr Historie noch feinere Kerzen noch
Ensembles (Nummern 14, 17, 27, 29).

Bleibt die **Form**. Sie haengt nicht an den Groessenreglern, sondern an
Ausstieg und Zielen - dem einzigen Teil des Genoms, der nie abgetastet wurde.
Ob dort etwas liegt, ist offen; dass es der letzte unbetretene Weg innerhalb
dieser Regelfamilie ist, steht jetzt fest.

Versuchszaehler unveraendert bei **151** - diese Messung hat keinen Backtest
gerechnet, sondern eine Formel aufgeloest. Stand: **7 von 11**.

## Sechsundvierzig. Der letzte Weg war zu - und meine Begruendung war falsch

Nummer fuenfundvierzig hatte drei offene Wege gelassen und einen davon als den
einzigen unbetretenen benannt: die **Schiefe**. Bevor man sie abtastet, gehoert
gemessen, woran sie ueberhaupt haengt. Also erst die Ausstiege gezaehlt:

    signal_exit    76  (49,4 %)   Mittel  +1,288 R   max  +12,07
    stop_loss      68  (44,2 %)   Mittel  -1,090 R   max   -1,03
    take_profit    10  ( 6,5 %)   Mittel +19,588 R   max  +19,81

**Der rechte Rand ist nicht gewachsen, er ist abgeschnitten.** Die fuenf
groessten Ergebnisse des ganzen Laufs liegen bei 19,69 / 19,70 / 19,72 / 19,77
/ 19,81 R - alle am selben Deckel.

### Ein Limit, das nie jemand begruendet hatte

``TargetSpec.rr`` war auf ``le=20.0`` gesetzt, ohne Begruendung, und der
Spitzenkandidat sass genau darauf. Eine Trendfolge **ohne** Gewinnziel -
Ausstieg nur nach Regel oder Stop, die uebliche Bauform dieser Familie - war
damit gar nicht ausdrueckbar.

Das anzuheben lockert kein Gate. Gates sind Zulassungsschwellen; dies ist der
Wortschatz, in dem Strategien formuliert werden. Die Grenze steht jetzt bei
200 - bei einem Vier-Prozent-Stop entspraeche das einer Bewegung von 800 %,
also praktisch "kein Ziel".

### Die Messung, und sie sagt Nein

Gewinnziel als Regler, BTC + ETH, Tageskerzen. **Die Trade-Zahl bleibt bei
allen Stufen 152** - der erste Regler, der die Einstiege nicht antastet:

    Ziel   Trades    CAGR   SR/Trade     DSR   Schl.Jahr   Gates
      10      152   10,16 %   0,2640   0,736     -7,18      8/11
      20      152   13,47 %   0,2597   0,808    -10,32      7/11
      30      152   13,77 %   0,2349   0,557    -10,32      7/11
      50      152   13,27 %   0,1946   0,186    -10,32      7/11
     100      152   13,27 %   0,1863   0,048    -10,32      7/11
     200      152   13,27 %   0,1851   0,047    -10,32      7/11

**Den Deckel zu oeffnen zerstoert den Deflated Sharpe: 0,808 auf 0,047.**

### Warum meine Begruendung falsch war

Ich hatte argumentiert: Die Schiefe senkt den Nenner der DSR-Formel, also
hilft ein laengeres rechtes Ende. Das stimmt - und ist trotzdem der falsche
Schluss, weil es nur die eine Haelfte ist.

Ein laengeres rechtes Ende erhoeht auch die **Streuung** der Ergebnisse, und
der Sharpe je Trade ist ein Verhaeltnis aus Mittelwert und Streuung. Gemessen
faellt er von 0,2597 auf 0,1851, waehrend die Rendite sogar leicht sinkt: Die
zehn Trades, die bei 20 R ausstiegen, geben ohne Deckel wieder ab, bevor der
Ausstieg nach Regel greift. Der Gewinn am Nenner der Formel ist weit kleiner
als der Verlust am Zaehler.

Die Kappung bei 20 R **half** dem Kandidaten also, statt ihm zu schaden - und
dass ausgerechnet die unbegruendete Schema-Grenze an der guenstigsten Stelle
sass, ist Zufall und kein Verdienst.

Dreizehnte geschlossene Richtung, und es war die letzte innerhalb dieser
Regelfamilie, die noch niemand betreten hatte.

### Zwei Fehler, gefunden auf dem Weg dorthin

* ``research/mutation.py`` schnitt Ziele bei ``0.3, 20.0`` ab - **dieselben
  Zahlen wie im Schema, nur an einer zweiten Stelle.** Nach dem Anheben haette
  die Mutation weiter bei 20 gedeckelt und still eine andere Regel befolgt als
  die Validierung. Sie holt die Grenzen jetzt aus dem Schema.
* ``_feldgrenzen`` rundete die ausgelesenen Schranken mit ``int()`` ab. Bei
  Indikatorperioden faellt das nicht auf; beim ersten Feld mit gebrochener
  Schranke - ``rr`` mit ``ge=0.3`` - waere daraus eine 0 geworden, und die
  Mutation haette Ziele erzeugt, die das Schema anschliessend ablehnt.

Versuchszaehler **151 -> 156**. Stand: **7 von 11**.

## Siebenundvierzig. Ein Verdacht gegen das eigene Gate - und er war unbegruendet

Nach dreizehn geschlossenen Richtungen war der naechste Schritt keine neue
Idee, sondern eine Pruefung der Zahl, an der alles haengt. Aufgefallen war
beim Zerlegen des Deflated Sharpe, dass die effektive Stichprobe **154 von
154** betraegt - gar keine Kuerzung, obwohl BTC und ETH bekanntlich zusammen
laufen.

Gemessen, in der unbequemen Richtung: Wenn die Korrektur zu milde ist, steht
der Kandidat schlechter da als berichtet.

    Fenstergewinne BTC gegen ETH        Korrelation +0,405
    Trades in gleichzeitigen Gruppen    80 von 154 (52 %)
    ICC ueber Kalenderfenster           +0,1111   p 0,066
    Kuerzung daraus                     keine

**Der Verdacht war unbegruendet.** Die Kuerzung ist stetig und kalibriert am
95. Perzentil der Permutationsnull - sie schaltet nicht bei p = 0,05 ab,
sondern findet schlicht, dass ein ICC von 0,111 bei dreissig Bloecken
ungleicher Groesse innerhalb dessen liegt, was unabhaengige Daten selbst
erzeugen. Kein Fehler, keine Klippe. Das gehoert genauso berichtet wie ein
Fund.

### Was dabei trotzdem auffiel

Die Korrektur teilt die Trades nach **Kalenderfenstern** ein. Das ist eine
zulaessige Vorstellung von Abhaengigkeit - und nicht die einzige. Positionen,
die **zugleich** offen waren, sind die andere, und das Monte-Carlo-Gate haelt
genau die schon lange zusammen:

    "Zwei Positionen, die gleichzeitig offen sind, sind keine zwei
     unabhaengigen Beobachtungen. Faellt der Markt, treffen sie das Konto
     zusammen."

Zwei Vorstellungen von derselben Sache im selben Gate-System, und welche der
Deflated Sharpe benutzt, stand nirgends begruendet. Es zaehlt jetzt die
**strengere**: gewaehlt wird die Einteilung mit der kleinsten Stichprobe.
Verglichen wird der Faktor, nicht die Summe - zwei Einteilungen koennen
verschieden viele Trades abdecken, und dann waere die kleinere Zahl kein
Zeichen groesserer Strenge, sondern eine kuerzere Liste.

Das kann die Zulassung nur erschweren, nie erleichtern. Das ist die einzige
Richtung, in die eine solche Entscheidung fallen darf, wenn man sie selbst
trifft.

### Und am Kandidaten aendert es nichts

    nach Kalenderfenstern      ICC +0,1111   p 0,066   effektiv 154
    nach Gleichzeitigkeit      ICC +0,0000   p 1,000   effektiv 154
    Deflated Sharpe                                       0,7965

Gleichzeitige Trades auf BTC und ETH aehneln sich **nicht** staerker als
zufaellig gezogene Paare - der ICC ist an der unteren Klemme. Dass die
Fenstergewinne der beiden Beine mit 0,405 korrelieren, heisst also nicht, dass
die einzelnen Trades es tun: Die Ein- und Ausstiege liegen verschieden, jeder
Markt hat seinen eigenen Schnitt.

Der Zaehler bleibt bei **156** - hier wurde kein Backtest gerechnet, sondern
eine vorhandene Trade-Liste anders gruppiert. Stand: **7 von 11**, Deflated
Sharpe 0,7965.

## Achtundvierzig. Acht von elf - und der Grund, warum es trotzdem schlechter ist

``research/adaptiv.py`` war gebaut, getestet, gruendlich begruendet - und stand
in keinem Befehl. Es taucht im ganzen BEFUND nicht auf. **Es war nie
gemessen.** Damit war es die letzte fertige Idee im Haus, die noch nie eine
Zahl gesehen hatte.

Die Idee ist methodisch die sauberste des Projekts: Die Periode wird in
**jedem Trainingsfenster neu** bestimmt und im Testfenster verwendet. Die Wahl
kennt die Testdaten nicht. Gewaehlt wird die **Mitte des laengsten
zusammenhaengenden profitablen Bereichs** - nicht der beste Punkt, und die
Regel steht vor der Messung fest. Genau das greift auch das Plateau-Gate an,
an dem der Spitzenkandidat scheitert, weil er am Rand seines eigenen Bereichs
sitzt.

Verdrahtet als ``cli adaptiv``, BTC + ETH, Tageskerzen, **ein** Versuch:

                          fest        adaptiv
    Trades                 152            163
    Rendite p. a.       13,47 %        13,96 %
    Rueckgang           10,64 %         9,33 %
    Schlechtestes Jahr  -10,32  fail    -8,05  bestanden
    Bestaendigkeit       0,533          0,600
    Gates                 7/11           8/11
    Deflated Sharpe      0,797          0,469

Mehr Trades, mehr Rendite, weniger Rueckgang, ein Gate mehr - und der Deflated
Sharpe faellt um ein Drittel. **Acht von elf, und weiter weg als vorher.** Zum
zweiten Mal nach der Abkuehlung, und diesmal war die Zahl so gut, dass sie
schwer zu glauben war.

### Nachgerechnet, weil es nicht zusammenpasste

Aus den berichteten Eingaengen - Sharpe je Trade 0,253, 163 Trades, Schiefe
3,46, Woelbung 16,04, 157 Versuche - ergibt die Formel **0,812**, nicht 0,469.
Also aufgeloest, welche Stichprobe zu 0,469 gehoert: **110 von 163, also 67
Prozent.** Das Gate hatte gekuerzt.

Und dann die Frage, wer kuerzt:

    Kalenderfenster    31 Bloecke   ICC +0,3252   p 0,0015   107 von 162 (66 %)
    Gleichzeitigkeit  105 Bloecke   ICC +0,0222   p 0,4860   162 von 162

**Es war die Fenster-Einteilung, nicht die Gleichzeitigkeit**, die ich im
Abschnitt davor ergaenzt habe. Fast haette ich mir das gutgeschrieben; die
Messung sagt etwas anderes.

### Der Mechanismus, und er steckt in der Bauart

Der ICC springt von +0,111 (fest) auf **+0,325** (adaptiv). Das ist kein
Zufall, sondern die Konstruktion: Alle Trades eines Fensters teilen sich
**denselben** gewaehlten Faktor. Passt er zum Markt dieses Quartals, laufen sie
gemeinsam gut, sonst gemeinsam schlecht.

Die adaptive Wahl erzeugt also genau die Abhaengigkeit, die sie bezahlt. Die
elf zusaetzlichen Trades sind da - aber sie sind einander aehnlicher, und
unterm Strich bleiben **107 unabhaengige statt der 154 des festen
Kandidaten**. Mehr Trades, weniger Information.

Damit ist auch das Muster benannt, das sich jetzt viermal wiederholt hat:

    Abkuehlung        weniger handeln  -> Risiko-Gates ja, DSR nein
    Gewinnziel        laenger laufen   -> Streuung waechst, DSR nein
    Adaptive Periode  oefter handeln   -> Aehnlichkeit waechst, DSR nein
    Alle Groessenregler                -> Qualitaet je Trade unveraendert

Jeder Weg, der eine Kennzahl verbessert, verschlechtert den Deflated Sharpe
ueber einen anderen Kanal. Vierzehnte geschlossene Richtung.

### Was bleibt

Der Befehl bleibt, samt Ergebnis - eine gebaute und gemessene Idee ist mehr
wert als eine gebaute. Drei Tests halten den Mechanismus fest: Ein gemeinsamer
Anteil je Fenster kuerzt die Stichprobe, ohne ihn wird nicht gekuerzt, und ein
groesserer Lauf mit aehnlicheren Trades kann weniger wert sein als ein
kleinerer mit unabhaengigen.

Versuchszaehler **156 -> 157**. Stand: **7 von 11** - der Spitzenkandidat
bleibt der Spitzenkandidat, denn 8 von 11 bei einem Deflated Sharpe von 0,469
ist die schlechtere Lage.

## Neunundvierzig. Zwanzig Punkte, eine Linie, kein Treffer

Vierzehn geschlossene Richtungen sind vierzehn Einzelfaelle. Vier davon zeigen
dasselbe Muster - jeder Weg, der eine Kennzahl verbessert, verschlechtert den
Deflated Sharpe ueber einen anderen Kanal -, aber vier Faelle sind ein
Verdacht, keine Aussage.

Die Aussage waere: **Kein Punkt dieser Regelfamilie erreicht die Schwelle.**
Und sie steht laengst da: In ``reports/machbarkeit/`` liegen acht Abtastungen
mit 52 Reglerstellungen, jede mit vollem Gate-Ergebnis. Sie mussten nur einmal
zusammengelegt werden - ohne einen einzigen neuen Backtest.

``cli front``, zwanzig einordenbare Punkte aus drei Reglern, 157 Versuche:

    Punkt                  Trades      hat    noetig   Faktor     DSR
    Gewinnziel 10             152   0,2640    0,2924     1,11    0,736
    Perioden-Faktor 1         152   0,2597    0,2924     1,13    0,851
    Abkuehlung 0              152   0,2597    0,2924     1,13    0,813
    Gewinnziel 20             152   0,2597    0,2924     1,13    0,808
    Abkuehlung 3              140   0,2599    0,3030     1,17    0,750
    Perioden-Faktor 0,6       226   0,2053    0,2459     1,20    0,467
    Perioden-Faktor 0,4       305   0,1774    0,2155     1,21    0,795
    Gewinnziel 30             152   0,2349    0,2924     1,24    0,557
    Abkuehlung 5              128   0,2529    0,3151     1,25    0,626
    Perioden-Faktor 0,8       175   0,2169    0,2750     1,27    0,344
    Perioden-Faktor 0,5       265   0,1803    0,2293     1,27    0,703
    Gewinnziel 50             152   0,1946    0,2924     1,50    0,186

**Kein einziger Punkt erreicht 0,95.** Der hoechste je gemessene Deflated
Sharpe der ganzen Familie liegt bei **0,851**.

### Was die Tabelle zeigt und eine Liste geschlossener Richtungen nicht

Die Trade-Zahl laeuft von 128 bis 305, also um mehr als das Doppelte. Die
noetige Qualitaet faellt entsprechend, von 0,3151 auf 0,2155 - und die
vorhandene faellt **mit**, von 0,2529 auf 0,1774. Der Faktor bleibt dabei
zwischen 1,11 und 1,27.

Die Familie bewegt sich also auf einer Kurve, die neben der Grenzlinie
herlaeuft und sie nirgends schneidet. Das ist etwas anderes als "vierzehn
Versuche sind gescheitert": Es ist die Form des Scheiterns, und sie sagt, dass
Weitersuchen entlang derselben Regler nichts findet.

### Zwei Zahlen je Punkt, und nur eine ist das Urteil

Der **gemessene** Deflated Sharpe stammt aus dem Gate, das mit der wirklichen
Verteilung des Punktes gerechnet hat - er ist exakt. Die Grenzlinie daneben
uebersetzt den Abstand in Sharpe-Einheiten und braucht dafuer Schiefe und
Woelbung; die aelteren Berichte tragen sie nicht mit, dort gilt die Form des
Spitzenkandidaten. Diese Punkte sind mit ``~`` markiert.

Ein Test haelt den Unterschied fest: Ein Punkt, den die Linie durchwinken
wuerde, dessen gemessener Wert aber unter der Schwelle liegt, gilt **nicht**
als bestanden. Das Gate hat recht, nicht die Uebersetzung.

Kuenftige Abtastungen schreiben Schiefe und Woelbung mit; die Naeherung
verschwindet damit von selbst.

### Eine Nebenbeobachtung, die zur Sache gehoert

Derselbe Kandidat steht in drei Scans mit drei verschiedenen Werten: 0,851 /
0,813 / 0,808. Die Regel hat sich nicht geaendert - die **Huerde** ist
gestiegen, weil zwischen den Laeufen Versuche dazukamen. Der Preis des Suchens,
an einer Stelle sichtbar, an der man ihn nicht sucht.

Versuchszaehler unveraendert bei **157** - es wurde nichts gerechnet, was nicht
schon gerechnet war. Stand: **7 von 11**.

## Fuenfzig. Die Bestenliste verglich gegen verschiedene Huerden

Im Abschnitt davor stand eine Nebenbeobachtung: Derselbe Kandidat taucht in
drei Abtastungen mit **0,851 / 0,813 / 0,808** auf. Die Regel hat sich nicht
geaendert - die Huerde ist gestiegen, weil zwischen den Laeufen Versuche
dazukamen.

Diesmal die Frage, was das anderswo anrichtet. Und es richtet etwas an:

    Entry.deflated_sharpe   der gemessene Wert
    Entry.versuche          gab es nicht

Die Bestenliste sortiert **primaer** nach dem Deflated Sharpe - so begruendet
in Abschnitt neunzehn, und die Begruendung stimmt. Nur speicherte sie nicht,
gegen welche Huerde der Wert gemessen wurde. Ein Eintrag aus der Vorwoche stand
damit mit einem Vorteil da, den er nicht verdient hatte.

**Und das ist nicht nur eine Anzeige.** ``breed`` nimmt ``board.best(5)`` als
Eltern der naechsten Runde. Eine verzerrte Rangfolge zuechtet aus den falschen
Eltern - und jeder dieser Versuche hebt die Huerde fuer alle weiteren.

### Wie gross die Verzerrung ist

Von 40 Eintraegen stammen 24 vom 4. und 5. August, 16 vom 9. Zwischen diesen
Zeitpunkten stieg der Zaehler um rund 45. Gerechnet an einem konstruierten,
aber realistischen Paar:

    Eintrag   gemessen bei   gespeichert   auf 157 Versuche
    alt          50 Versuche      0,9346             0,7990
    neu         157 Versuche      0,9017             0,9017

Der **schlechtere** Eintrag steht mit 0,9346 oben, der bessere mit 0,9017
darunter - allein, weil der eine frueher gemessen wurde. Auf gemeinsamer
Huerde dreht sich die Reihenfolge um. Ein Test haelt beide Richtungen fest:
erst dass die Verdrehung ohne Umrechnung eintritt, dann dass sie mit ihr
verschwindet.

Im Augenblick sitzt kein alter Eintrag in den oberen fuenf - der Fehler war
also latent, nicht wirksam. Das macht ihn nicht kleiner, sondern nur schwerer
zu bemerken.

### Behoben

* ``Entry`` traegt jetzt ``versuche`` sowie ``sharpe_je_trade``, ``schiefe``
  und ``woelbung`` - die Eingaenge, aus denen sich der Wert auf einen anderen
  Versuchsstand **umrechnen** laesst, statt ihn nur zu vergleichen.
* ``ranked(versuche=...)`` und ``best(versuche=...)`` rechnen jeden Eintrag auf
  denselben Stand, bevor sie sortieren. Der Wettbewerb ruft sie so - fuer die
  Anzeige, fuer das Tradelog und fuer die Elternwahl.
* Die Kennzahlen kommen aus ``Kandidat.aus_trades``, also aus derselben
  Umsetzung wie ueberall sonst. Es waere die sechste Stelle mit derselben
  Formel gewesen.

### Was ausdruecklich nicht passiert ist

Die 40 vorhandenen Eintraege wurden **nicht** nachtraeglich umgerechnet. Ihre
Eingaenge fehlen, und eine Umrechnung zu erfinden waere schlimmer als eine
ehrliche Luecke. Sie behalten ihren Wert und tragen in der Tabelle ein ``?``:

    ? bei 40 von 40 Eintraegen: vor dieser Aenderung gemessen, Huerde
      unbekannt. Ihr Wert steht, aber er gehoert nicht in denselben Vergleich.

Mit jedem kuenftigen Lauf verschwindet das Fragezeichen von selbst.

Versuchszaehler unveraendert bei **157** - es wurde nichts gerechnet, was eine
Strategie betrifft. Stand: **7 von 11**.

## Einundfuenfzig. Das Abbruchkriterium stand nur im Plan

Der Plan vom 9. August legt fest: *"Erreicht nach 100 weiteren Versuchen kein
Kandidat 11 von 11, lautet die Antwort 'diese Regelfamilie traegt nicht'."*
Geschrieben bei Versuchsstand 130, Abbruch also bei 230.

Nur wusste das System nichts davon. Der Zaehler lief, das Kriterium stand in
einem Dokument daneben, und niemand haette bemerkt, wenn er die Grenze
ueberschritten haette. Ein Abbruchkriterium, das nicht mitgezaehlt wird, ist
eine Absichtserklaerung.

``cli stand`` zeigt es jetzt in derselben Uebersicht wie den Rest:

    Versuche   157
    Suchbudget 27 von 100 verbraucht, 73 bleiben (Abbruch bei 230).

### Warum eine Zahl und keine Bedingung

Ein Kriterium wie "abbrechen, wenn sich nichts mehr verbessert" laesst sich
nachtraeglich zurechtlegen - es findet sich immer eine Kennzahl, die noch
Hoffnung macht. Eine vorab genannte Zahl kann das nicht. Sie ist grob, und das
ist ihr Vorzug.

Ein Test haelt fest, dass die Grenze **auf** 230 greift und nicht erst darueber
- sonst waere sie eine Verhandlungssache.

### Was der Zaehler seit dem Plan gekostet hat

    130 -> 157    27 Versuche
                  davon 16 Wettbewerb, 5 Abkuehlung, 5 Gewinnziel,
                  1 adaptive Periode

Diese 27 haben die noetige Qualitaet je Trade um 27 x 0,00021 = **0,0057**
angehoben. Gefunden haben sie nichts: Der hoechste gemessene Deflated Sharpe
der Familie steht weiter bei 0,851, und die Frontanalyse zeigt eine Kurve, die
neben der Grenzlinie herlaeuft.

Das ist kein Argument, das Budget vorzeitig zu beenden - es ist eine Abmachung,
und sie laeuft bis 230. Es ist ein Argument, die verbleibenden 73 nicht wieder
in dieselbe Regelfamilie zu stecken.

Versuchszaehler unveraendert bei **157**. Stand: **7 von 11**.

## Zweiundfuenfzig. Eine Naeherung im Fundament - und sie kostet nichts

Der Backtest kennt eine Unschaerfe, die in seinem eigenen Modulkopf steht:
Liegen in einer Kerze **sowohl Stop als auch Take-Profit**, verraet OHLC nicht,
was zuerst kam. Ohne feinere Kerzen nimmt die Engine den schlechteren Fall -
richtig fuer eine Naeherung, aber eine Naeherung.

Der Einzelmarkt-Weg konnte sie schon lange aufloesen; ``run_walkforward`` nimmt
seit jeher ein ``sub_frame``. Der **Portfolioweg nicht** - und gemessen wird
das Portfolio. Damit lief jede Zulassungszahl dieses Projekts auf der
pessimistischen Annahme, obwohl 445 400 Fuenfzehnminutenkerzen fuer BTC und ETH
im Speicher liegen.

Also durchgereicht und gemessen, derselbe Kandidat, BTC + ETH, Tageskerzen:

    ohne Feinkerzen   154 Trades  13,40 % p.a.  DD 10,64 %  SR 0,2569  DSR 0,7954  7/11
    mit Feinkerzen    154 Trades  13,40 % p.a.  DD 10,64 %  SR 0,2569  DSR 0,7954  7/11

**Bit fuer Bit dasselbe.** Auch die Ausstiegsgruende: 76 nach Regel, 68 am
Stop, 10 am Ziel.

### Und dann die Frage, ob die Daten ueberhaupt angefasst wurden

Ein identisches Ergebnis hat zwei moegliche Ursachen, und die zweite waere ein
Fehler: Vielleicht wurde die Feinreihe stillschweigend ignoriert. Die Engine
warnt selbst davor - *"ein Fehler ohne Fehlermeldung, der den Backtest nur
schlechter aussehen laesst"*.

Nachgezaehlt, im Lauf mitgeschrieben:

    Sub-Index gebaut        62      (31 Fenster x 2 Beine)
    between() gerufen    11 300
    davon mit Daten       9 128      (81 %)

Die Feinkerzen wurden also benutzt. Das Ergebnis bleibt trotzdem gleich, und
der Grund ist strukturell: Bei **4 % Stop und einem Ziel bei 20 R** - also rund
80 % Kursbewegung - koennen beide unmoeglich in derselben Tageskerze liegen.
Die Mehrdeutigkeit, die feinere Kerzen aufloesen, tritt bei diesem Kandidaten
gar nicht auf.

### Warum die Aenderung trotzdem bleibt

Sie entfernt eine Naeherung aus **jeder kuenftigen** Messung. Fuer einen
Kandidaten mit engerem Ziel - wo Stop und Ziel sehr wohl in einer Kerze liegen
- waere der Unterschied da, und dann waere es zu spaet, ihn erst zu bemerken.

Drei Tests halten die Verdrahtung fest: dass jedes Bein **seine eigenen**
Feinkerzen bekommt und nicht die des anderen, dass ein Bein ohne sie auf die
Annahme zurueckfaellt, und dass ohne Angabe alles bleibt, wie es war. Die
Aufloesung selbst war schon getestet - was fehlte, war der Weg dorthin.

Beim Schreiben des ersten Tests ein eigener Fehler: Ich unterschied die Beine
an der Kerzenzahl. ``common_range`` schneidet sie aber auf denselben Zeitraum,
danach sind sie gleich lang - der Test sah nur ein Bein und schlug fehl. Jetzt
laeuft die Unterscheidung ueber das Instrument.

Versuchszaehler unveraendert bei **157** - dasselbe Genom genauer zu messen ist
keine zweite Hypothese. Stand: **7 von 11**.

## Dreiundfuenfzig. Die Research-KI hat zum ersten Mal etwas vorgeschlagen

Zwei fertige Haelften ohne Verbindung: ``research/analyst.py`` kann strukturell
neue Regeln vorschlagen und war seit P6 gebaut und getestet - benutzt wurde er
nie. Der Wettbewerb erzeugt neue Kandidaten durch **Mutation**, und die
variiert Zahlen. Eine Schnittkreuzung mit anderen Perioden ist dieselbe Regel
mit anderen Perioden; nach fuenfzig Befunden waren die Zahlenwege ausgemessen,
die Strukturwege dagegen unberuehrt.

Der Grund, warum er nie lief, war banal: Er braucht einen bezahlten
API-Schluessel, den dieses Projekt nicht gesetzt hat.

### Der Weg dorthin - und was er ausdruecklich nicht ist

``LLMClient`` ist ein **Protokoll**, also eine vorgesehene Erweiterungsstelle.
Wer den Auftrag aus ``build_prompt`` beantworten kann, darf antworten. Neu ist
deshalb ein ``DateiClient``, der die Antwort aus einer Datei liest, und ein
Befehl, der den Rest des Weges geht:

    python -m cli vorschlag --auftrag              # zeigt, was zu beantworten ist
    python -m cli vorschlag --datei antwort.json   # misst die Antwort

**In dieser Runde habe ich den Auftrag selbst beantwortet.** Das gehoert
dransteht, und es steht dran - die Bestenliste vermerkt als Herkunft
``Vorschlag (vorschlaege.json)`` statt ``Analyst``. Ein Vorschlag von Hand ist
keinen Deut glaubwuerdiger als einer aus einem Modell: Er geht durch dasselbe
``parse_proposals``, das ihn ablehnt statt repariert, durch dieselben elf
Gates, und er kostet **denselben Versuch**. Der Zaehler stand bei 157 und steht
jetzt bei 161.

### Vier Thesen, jede widerlegbar formuliert

Keine Zahlenvariante war dabei; alle vier tragen denselben 4-%-Stop und
dasselbe Ziel, damit sich nur die **Struktur** unterscheidet.

1. **Donchian-Ausbruch 50/25** - reagiert auf ein Kursniveau statt auf einen
   geglaetteten Mittelwert. Die Einstiege liegen dadurch an anderen Tagen.
2. **Ausbruch mit Beteiligung** - derselbe Ausbruch, aber nur bei erhoehtem
   Umsatz. Bisher wurde ausschliesslich Preis verwendet, nie Beteiligung.
3. **Rueckkehr vom unteren Band** - die Gegenthese zur Trendfolge.
4. **Rueckschlag im Aufwaertstrend** - Einstieg auf Schwaeche statt auf
   Staerke, genau umgekehrt zur bisherigen Familie.

### Gemessen, BTC + ETH, Tageskerzen, alle elf Gates

    Vorschlag                     Gates  Trades  Sharpe    DSR
    Donchian-Ausbruch 50/25        5/11      89    0,86  0,157
    Ausbruch mit Beteiligung       5/11      68    0,92  0,162
    Rueckkehr vom unteren Band     1/11     118    0,19  0,014
    Rueckschlag im Aufwaertstrend  5/11       8    0,03  0,000

    Bestand (Spitzenkandidat)      7/11     152    1,05  0,797

**Alle vier sind deutlich schlechter als das, was schon da war.** An der
Grenzlinie abgelesen, wo der Abstand vergleichbar wird:

    Kandidat                     Trades      hat   noetig   Faktor
    Ausbruch mit Beteiligung         68   0,2482   0,4192     1,69
    Donchian-Ausbruch 50/25          89   0,2136   0,3706     1,74
    Rueckkehr vom unteren Band      118   0,0483   0,3272     6,77
    Spitzenkandidat                 152   0,2597   0,2929     1,13

Der Bestand liegt naeher an der Linie als jeder Vorschlag - und er lag schon
vorher dort.

### Was das heisst und was nicht

Drei Einzelaussagen sind sauber gemessen und schliessen ihre Richtung:

* **Kanalausbruch statt Kreuzung**: strukturell anders, DSR 0,157. Die
  Ausbruchsregel handelt weniger und schlechter.
* **Umsatz als Filter**: die einzige bisher ungenutzte Informationsquelle. Sie
  hebt den Sharpe je Trade auf 0,2482 - nah am Bestand -, kostet dafuer aber
  ein Viertel der Trades. Netto DSR 0,162. Ein weiteres Beispiel fuer das
  Muster aus Befund 49: Was die Qualitaet hebt, senkt die Zahl staerker.
* **Rueckkehr zum Mittel**: die Gegenthese ist gemessen statt vermutet und
  faellt mit 1 von 11 klar durch. Sharpe 0,19.

Was hier **nicht** steht: "die KI taugt nichts". Vier Vorschlaege sind vier
Vorschlaege. Der Befund ist enger und dafuer belastbar - *diese* vier
Strukturen sind schlechter als die vorhandene, und der Weg dorthin steht jetzt
und kostet nichts mehr.

Ehrlich dazugehoert auch: Ich habe vier Versuche ausgegeben und die Huerde
damit fuer alle kuenftigen Kandidaten um 0,00084 angehoben, ohne etwas
Besseres zu finden. Das Suchbudget steht bei 31 von 100.

### Zwei Kleinigkeiten am Rande

Der Vierzigzeiler, der den Korb laedt, stand in ``korb`` und haette fuer den
neuen Befehl kopiert werden muessen - damit haette es zwei Stellen gegeben, an
denen steht, was "der Korb" ist. Er liegt jetzt in ``_korb_daten``.

Und der Adapter zur Bestenliste war im ersten Anlauf mit falschen Feldnamen
geschrieben (``report=``/``trades=`` statt ``walkforward=``). Er lief bis zum
ersten echten Lauf. Dafuer gibt es jetzt ``tests/test_vorschlag.py``.

## Vierundfuenfzig. Die Gegenfrage zur Nullprobe - und drei eigene Fehler dabei

Die Nullprobe (Befund 33) beantwortet eine Haelfte: *Findet die Maschine einen
Vorteil, wo garantiert keiner ist?* Nein. Die andere Haelfte stand nie da:
**Erkennt sie einen, der wirklich da ist?**

Nach 161 Versuchen und sechzehn geschlossenen Richtungen passen zwei
Erklaerungen gleich gut auf alles Gemessene - die Regelfamilie traegt nicht,
oder die Huerde ist bei so vielen Versuchen unerreichbar geworden. Von innen
sehen beide identisch aus, und die Antwort entscheidet, ob die restlichen 69
Versuche des Suchbudgets sinnvoll ausgegeben werden koennen.

### Das Verfahren: einen Trend pflanzen

Nicht auf einer erfundenen Preisreihe, sondern **in der echten**: Zu jeder
Tagesrendite kommt ein Regime-Anteil, der ueber Wochen dasselbe Vorzeichen
behaelt. Der Regler ist der Anteil der Tagesvarianz, der zum Regime gehoert.
Bei 0 bleibt die Reihe unveraendert - dort muss das bekannte Ergebnis
herauskommen, sonst misst die Leiter ihre eigene Erzeugung.

    python -m cli teststaerke --stufen 0,0.1,0.2,0.35,0.5 --dauer 60

Kostet keinen Versuch: Geprueft wird die Strecke, kein Kandidat.

### Drei Fehler in meinem eigenen Aufbau

Sie gehoeren hierher, weil zwei davon die Zahlen bereits verzerrt hatten und
ich sie erst beim Nachrechnen gefunden habe.

**Erstens: die Groessenlogik.** Ich hatte aus ``korb`` die Normalisierung auf
ein gemeinsames Vola-Ziel uebernommen. Dort ist sie richtig, weil ein ganzer
Katalog verglichen wird - hier gibt es nur ein Genom, und sie verschob still
den Ankerpunkt: Die 0-%-Sprosse kam auf 143 Trades und 5 von 11 statt auf die
bekannten 154 und 7 von 11.

**Zweitens: der Drift.** Ich hatte ``sqrt(1-a) * r`` gerechnet, also die
Renditen skaliert, ohne den Mittelwert herauszunehmen - und damit den Drift des
Marktes gleich mitgedaempft. Kaufen-und-Halten fiel bei Anteil 0,5 von +1195 %
auf +110 %. Jede gepflanzte Stufe war so zugleich ein **schwaecherer Markt**,
und am staerksten traf das ausgerechnet das Gate mit der Mindestrendite. Der
gepflanzte Vorteil sah aus, als koste er Rendite, obwohl ihn nur meine eigene
Rechnung wegskaliert hatte. Richtig ist
``r' = m + sqrt(1-a)*(r-m) + sqrt(a)*sigma*regime``.

**Drittens: der abgeschnittene Regime-Ausschnitt.** Eine Reihe mit n Kerzen hat
n-1 Renditen; das eine fehlende Element machte die mittelwertfreie Folge wieder
mittelwertbehaftet, und ein kleiner Drift sickerte ein. Gefunden hat ihn der
Test, der prueft, dass Kaufen-und-Halten unveraendert bleibt - mit einer
Toleranz von 2 % waere er durchgerutscht.

### Was die korrigierte Leiter zeigt

BTC + ETH, Tageskerzen, Regime im Mittel 60 Kerzen, Huerde bei 161 Versuchen:

    gepflanzt  Trades  je Trade   Guete     DSR   Gates
           0%     154    0,2569    3,19   0,791   7/11
          10%      48    0,5593    3,88   0,761   9/11
          20%      29    0,5661    3,05   0,000  10/11
          35%      17    0,7913    3,26   0,000   8/11
          50%      12    1,2734    4,41   0,000   9/11

Die 0-%-Sprosse trifft die Wirklichkeit (154 Trades, 7 von 11); der Anker
stimmt.

**Der Vorteil je Trade verfuenffacht sich - und der Deflated Sharpe faellt.**
Der Grund steht in der Trade-Spalte: Ein Trend, der ueber Wochen haelt, laesst
eine Trendfolge *seltener* handeln. Sie steigt ein und bleibt drin, statt in
Seitwaertsphasen hin- und hergeworfen zu werden.

Die Spalte ``Guete`` ist ``Vorteil je Trade * sqrt(Trades)`` - im Kern die
Groesse, gegen die der Deflated Sharpe seine Huerde legt. Sie geht von 3,19 auf
4,41, waehrend der Vorteil je Trade von 0,26 auf 1,27 springt. Fuenffacher
Vorteil, ein Drittel mehr Guete.

### Was daraus folgt und was nicht

**Nicht** folgt: "die Gates sind zu streng". Die Messlatte-Zeilen taugen ohnehin
nicht als Befund - sie vergleicht mit Kaufen-und-Halten ueber Dreimonats-
fenster, und ein 60-Kerzen-Regime liegt in derselben Groessenordnung. Dann
faellt ein ganzes Fenster in ein Regime, und der Vergleichsmassstab schwankt
staerker als das Gemessene (Halten zwischen +1195 % und +5346 % ueber dieselben
Fenster). Das steht im Modulkopf, damit es niemand als Ergebnis liest.

**Es folgt** etwas ueber die Lage, und es ist die belastbarste Aussage, die
dieses Projekt bisher ueber sich selbst hat: **Qualitaet und Menge sind
gekoppelt.** Nicht bei den Regeln, die wir zufaellig probiert haben - hier war
der Vorteil per Konstruktion echt, sauber und beliebig gross einstellbar, und
die Kopplung blieb. Ein groesserer Trend heisst laengeres Halten heisst weniger
Trades. Auf rund 3300 Tagen je Bein gibt es keine Einstellung, bei der beides
zugleich reicht.

Das trifft sich mit Befund 49 (zwanzig Punkte, eine Linie, kein Treffer) und
erklaert ihn: Die Kurve lief parallel zur Grenzlinie, weil sie parallel laufen
**muss**. Und es trifft sich mit Befund 14 - mehr Historie ist die eine
Richtung, die das aufloesen wuerde, und die ist mit fallendem Sharpe je Trade
geschlossen.

Damit steht die Frage aus dem Plan schaerfer als vorher: Nicht "finden wir noch
eine bessere Regel", sondern "traegt Trendfolge auf Tageskerzen ueber diese
Historie ueberhaupt genug Ereignisse". Die Leiter sagt: nein.

## Fuenfundfuenfzig. Ein totes Feld - gefunden, weil der Regler nichts tat

Aus Befund 54 folgt eine pruefbare Gegenthese. Die Kopplung dort lautete: Ein
staerkerer Trend heisst laengeres Halten heisst weniger Trades. Wer die
Haltedauer **deckelt**, muesste sie brechen - dann liefert ein laengerer Trend
mehr Trades statt weniger.

Also drei Deckel nebeneinander durch dieselben gepflanzten Reihen. Ergebnis des
ersten Laufs:

     gepflanzt      unbegrenzt       30 Kerzen       60 Kerzen
           0%      3.19 (154)      3.19 (154)      3.19 (154)
          10%      3.88 ( 48)      3.88 ( 48)      3.88 ( 48)
          35%      3.26 ( 17)      3.26 ( 17)      3.26 ( 17)

Drei identische Spalten. Ein Ergebnis, das sich nicht bewegt, wenn man am
Regler dreht, ist keines.

### Der Befund: `Genome.max_hold_bars` hat nie etwas getan

Das Feld gibt es seit P3: im Schema, mit Grenzen von 0 bis 2000 validiert, von
``describe()`` ausgegeben, vom Analysten vorschlagbar. Die Engine hat es **nie
gelesen**. Ihr Deckel sass ausschliesslich auf ``BacktestConfig.max_hold_bars``,
und niemand reichte den einen Wert an die andere Stelle weiter.

Das ist die unangenehmste Sorte Fehler. Ein fehlender Zwangsausstieg wirft
keine Ausnahme und schreibt keine Warnung - er erzeugt nur andere Trades. Jedes
Genom mit einer Haltedauer wurde ohne sie gerechnet, und jede Zahl daraus galt
fuer eine Regel, die so nie aufgeschrieben worden war. Betroffen sind unter
anderem die vier Analysten-Vorschlaege aus Befund 53, soweit sie das Feld
gesetzt haetten.

**Der Weg der Korrektur stand schon im selben Modul.** Zur Groessenlogik steht
in ``engine.run`` seit jeher: *"Die Betriebsart der Positionsgroesse gehoert zur
Strategie, nicht zur Konfiguration."* Fuer die Haltedauer gilt dasselbe - wie
lange man zu halten bereit ist, gehoert zur Idee, nicht zum Maschinenaufbau.
Neu ist deshalb ``strategy.base.hold_limit``: Die Strategie hat Vorrang, die
Konfiguration bleibt der Rueckfall, und wer nichts mitbringt, verhaelt sich
unveraendert. Die ganze bestehende Suite blieb gruen - niemand hatte sich
darauf verlassen, dass das Feld ignoriert wird.

Belegt in ``tests/test_haltedauer.py``, unter anderem mit dem Test, der den
Fehler ueberhaupt sichtbar gemacht haette: *verschiedene Deckel liefern
verschiedene Ergebnisse*.

Auch die Testreihe dafuer war im ersten Anlauf falsch: ein nur steigender
Markt kreuzt seinen Schnitt genau einmal, es gibt eine einzige Position, und an
einem Trade laesst sich kein Deckel ablesen. Erst mit Schwingung wird die Frage
"handelt ein kuerzerer Deckel oefter" ueberhaupt eine Frage.

### Und dann die eigentliche Messung

Mit wirkendem Regler, dieselben gepflanzten Reihen:

     gepflanzt      unbegrenzt       20 Kerzen       40 Kerzen
           0%      3.19 (154)      2.79 (154)      3.40 (154)
          10%      3.88 ( 48)      3.75 ( 48)      4.06 ( 48)
          35%      3.26 ( 17)      3.40 ( 17)      3.26 ( 17)
      Steigung          -0.30            1.15           -0.93

**Die Gegenthese ist widerlegt, und zwar schaerfer als erwartet.** Die
Trade-Zahlen sind ueber alle Deckel hinweg *identisch* - 154, 48, 17. Der
Deckel veraendert, was die Trades einbringen, aber nicht, wie viele es sind.

Der Grund liegt an der anderen Seite der Regel: Der Einstieg verlangt eine
Kreuzung von unten. Wer mitten im Trend zwangsweise aussteigt, bekommt keine
neue Kreuzung geschenkt - der Kurs liegt ja weiter ueber seinem Schnitt. Am
Ausstieg zu drehen kann die Zahl der Gelegenheiten nicht erhoehen, weil sie am
**Einstieg** haengt.

Damit ist die Kopplung aus Befund 54 nicht nur bestaetigt, sondern genauer
verortet: Sie sitzt nicht in der Haltedauer, sondern in der Haeufigkeit der
Einstiegsbedingung. Und die wird in einem starken Trend seltener, nicht
haeufiger - der Kurs hoert auf, unter seinen Schnitt zu fallen.

Die Steigung von 1,15 bei '20 Kerzen' ist ausdruecklich **kein** Treffer: Sie
kommt bei 11 % der Trades der untersten Sprosse zustande. Das Kriterium
verlangt beides, und der Urteilstext sagt jetzt auch, welche Haelfte gerissen
ist - der erste Anlauf meldete "1,15 gegen die geforderten 0,5" und daneben
"keine Variante entkoppelt", was sich wie ein Widerspruch las.

### Was daraus fuer die Suche folgt

Wer die Kopplung brechen will, muss an der **Einstiegsbedingung** ansetzen, und
zwar an einer, die in starken Trends *haeufiger* ausloest statt seltener. Das
ist eine engere und damit brauchbarere Vorgabe als "irgendeine bessere Regel" -
und es ist eine, an der die Vorschlaege aus Befund 53 alle vorbeigingen.

## Sechsundfuenfzig. Vorauswahl, die nichts kostet - und was sie nicht kann

Befund 55 endete mit einer Vorgabe: Die Kopplung sitzt in der **Haeufigkeit der
Einstiegsbedingung**, also braucht es eine, die in starken Trends haeufiger
ausloest statt seltener. Welche das tut, laesst sich auf gepflanzten Reihen
pruefen, bevor es Versuche kostet.

    python -m cli teststaerke --regeln <datei.json> --stufen 0.1,0.35

### Die Absicherung, ohne die das eine Umgehung waere

Die 0-%-Sprosse der Leiter ist nicht *fast* die echte Reihe, sie **ist** sie -
``pflanze_trend`` gibt den Rahmen bei Anteil 0 unveraendert zurueck. Wer Regeln
danach auswaehlt, hat auf echten Daten getestet, und genau das zaehlt die
Mehrfachtest-Korrektur. Eine Vorauswahl, die sie mitnaehme und trotzdem
"kostet keinen Versuch" meldete, waere eine stille Umgehung des Zaehlers.

Deshalb faellt die 0-%-Sprosse weg, sobald Regeln verglichen werden. Das steht
nicht nur im Text, es ist erzwungen und getestet
(``tests/test_vorauswahl.py``). Damit sieht die Vorauswahl die unveraenderte
Wirklichkeit nie und kann sich nicht an ihr ueberanpassen.

### Ein Fehler vorweg: null Trades in jeder Spalte

Der erste Lauf lieferte ueberall Nullen - auch beim Bestand, der dort 48 Trades
haben muss. Grund: Vorschlaege kommen mit ``risiko``-Groessenlogik, die am
Stop-Abstand bemisst und einen 4-%-Stop als **zu weit ablehnt**. Verglichen
wurden Groessenlogiken, nicht Einstiegsstrukturen.

Dass hier gleichgestellt wird und in Befund 54 nicht, ist kein Widerspruch:
Dort lief ein einziges Genom durch die Leiter, und das Gleichstellen verschob
bloss den Ankerpunkt. Hier laufen mehrere verschiedene Genome gegeneinander -
genau der Fall, fuer den ``korb`` die Normalisierung eingefuehrt hat.

### Die Vorauswahl, gepflanzte Reihen, Regime 60 Kerzen

     gepflanzt  Kurzer Rueckke  Neues Hoch im   Trendfolge 50
          10%      2.32 ( 99)      5.38 (122)      4.03 ( 48)
          35%      2.93 ( 19)      8.13 ( 86)      3.73 ( 17)
      Steigung            2.46           10.99           -1.23

Das Kriterium stand vorher fest: Steigung mindestens 0,5 **und** Stichprobe
nicht unter die Haelfte. Genau eine Regel besteht es - der wiederholbare
Ausbruch (neues 20-Tage-Hoch, Filter auf den 100er-Schnitt, Deckel 15 Kerzen).
Er haelt 70 % seiner Trades, waehrend die anderen beiden auf 19 bzw. 35 %
einbrechen.

Der Bestand verhaelt sich exakt so, wie Befund 55 es vorhergesagt hat:
Steigung **negativ**, Trades 48 auf 17. Und der kurze Rueckkehrtakt bricht
mit ein - auch ein 10-Tage-Schnitt wird in einem starken Trend irgendwann
nicht mehr von unten gekreuzt. Nur der Ausbruch skaliert, weil ein Trend
laufend neue Hochs erzeugt.

### Und dann der Test, der zaehlt

Ein Versuch, auf echten Daten, alle elf Gates (161 -> 162):

    Neues Hoch im Takt   123 Trades  SR/Trade 0,2137  Guete 2,37  DSR 0,331  5/11
    Bestand              154 Trades  SR/Trade 0,2569  Guete 3,19  DSR 0,791  7/11

**Schlechter als der Bestand, und zwar deutlich.** Er besteht zwar zum ersten
Mal die Messlatte - 16,5 % im Jahr gegen die geforderten 15 %, was dem
Spitzenkandidaten nie gelang -, erkauft das aber mit 21,8 % Rueckgang gegen
10,6 %. Monte-Carlo reisst bei 28,5 %.

### Was das ueber das Werkzeug sagt

Die Vorauswahl hat gehalten, was sie versprochen hat, und nicht mehr. Der
Modulkopf sagt es fuer die Leiter, und es gilt hier genauso: *Kommt etwas
durch, heisst das nur, dass es nicht an den Gates liegt - nicht, dass ein
solcher Vorteil existiert.* Uebertragen: Eine Struktur, die einen
**gepflanzten** Vorteil in Guete umsetzt, kann das - sie sagt nichts darueber,
ob der Markt einen anbietet. Auf echten Daten faellt der Sharpe je Trade von
0,2137 gegenueber 0,2569 des Bestands ab; die Mehrzahl an Gelegenheiten war da,
die Qualitaet nicht.

Damit ist die Vorgabe aus Befund 55 abgearbeitet und ihr Ergebnis unangenehm
klar: Die Kopplung laesst sich brechen - der wiederholbare Ausbruch tut es
nachweislich -, und es hilft trotzdem nicht, weil die zusaetzlichen
Gelegenheiten schlechter sind als die wenigen des Bestands. Beides zugleich
hat in dieser Historie bisher nichts geliefert.

Der Versuchsstand liegt bei 162, das Suchbudget bei 32 von 100.

## Siebenundfuenfzig. Eine Behauptung im eigenen System, nie gemessen

In ``research/stand.py`` stand seit Monaten ein Satz ueber die Mindestrendite
von 15 % im Jahr:

    "Sie steht im Konflikt mit der Rueckgangsgrenze: Was die eine verlangt,
    reisst die andere."

Das ist eine **Behauptung**. Sie klingt plausibel - und genau deshalb ist sie
nie jemandem aufgefallen, mir am wenigsten. Einer der vier Grundsaetze dieses
Projekts lautet, dass jede Behauptung gemessen wird und nicht geschaetzt. Diese
hier stand ungeprueft in der Datei, die den Nutzern sagt, was sie entscheiden
sollen.

Befund 56 hatte sie zufaellig gestreift: Der Ausbruch besteht erstmals die
Messlatte mit 16,5 % im Jahr - und reisst dabei den Rueckgang mit 21,8 %. Der
Spitzenkandidat macht es umgekehrt: 13,5 % bei 10,6 %. Zwei Punkte sind aber
kein Beleg, sondern zwei Punkte.

### Warum der Groessenregler die saubere Achse ist

Er skaliert jede Position mit demselben Faktor und laesst die Qualitaet je
Trade unveraendert (Befund 30). Rendite und Rueckgang wachsen also **beide**
mit ihm, und die Frage wird geometrisch: Geht die Kurve durch das erlaubte
Rechteck - mindestens 15 % Rendite bei hoechstens 12 % Rueckgang - oder laeuft
sie daran vorbei?

Die vorhandenen Berichte gaben die Antwort fast. Zwischen 19,3 (13,47 % bei
10,64 %) und 22,0 (15,16 % bei 12,82 %) lag ein ungemessener Sprung, und genau
dort wechselt die Kurve von "Rendite fehlt" zu "Rueckgang reisst".

Beim Zusammenlegen der Berichte fiel noch etwas auf: Fuer dieselbe Stellung
19,3 stehen in zwei Berichten verschiedene Zahlen (13,17/9,74 gegen
13,47/10,64). Der aeltere stammt aus der Zeit vor der Aufwaermphasen-Korrektur.
Stumpf zusammenzulegen ergaebe eine Kurve aus zwei Messstaenden - ``lade``
nimmt deshalb je Stellung den juengsten Bericht.

### Die Luecke gemessen - und was sie kostet

Drei neue Stellungen, ehrlich gezaehlt: **162 -> 165**. Sie stehen jetzt in
``REGLER["vola"].stufen`` und nicht im Aufruf, damit die Skala festliegt statt
je Auswertung neu gewaehlt zu werden - der Kommentar dort warnt seit jeher
genau davor.

     Stellung   Rendite  Rueckgang   Urteil
         19,3    13,47 %    10,64 %  Rendite fehlt
         20,5    14,11 %    11,29 %  Rendite fehlt
         21,0    14,39 %    12,50 %  Rendite fehlt, Rueckgang reisst
         21,5    14,69 %    12,76 %  Rendite fehlt, Rueckgang reisst
         22,0    15,16 %    12,82 %  Rueckgang reisst

**Die Kurve geht nicht durch das Rechteck.** Der letzte Punkt, der den
Rueckgang haelt, ist 20,5 - dort fehlen 0,89 Renditepunkte. Eine halbe Stufe
weiter reisst der Rueckgang bereits, und die Rendite fehlt immer noch. Es gibt
kein Dazwischen: Zwischen 20,5 und 21,0 springt der Rueckgang um 1,21 Punkte,
waehrend die Rendite um 0,28 zulegt.

    python -m cli vereinbar

rechnet das jederzeit nach und liest dafuer nur vorhandene Berichte - kostet
also nichts. Die Zahlen in ``stand.py`` sind entsprechend ersetzt: aus der
Behauptung ist eine Messung geworden.

### Was ausdruecklich nicht passiert ist

Bei 20,5 stuende der Kandidat besser da als bei 19,3. **Der Wert wird nicht
nachgezogen.** ``research/seeds.py`` haelt zu genau dieser Stellschraube fest,
dass ein Nachziehen "eine Anpassung an die Gates waere - und genau die Sorte
Entscheidung, gegen die die ganze Zulassungsstrecke gebaut ist". Der Befehl
gibt deshalb auch bei einem Treffer nie einen Betriebspunkt aus, und ein Test
haelt das fest (``test_ein_treffer_ist_keine_empfehlung``).

Nebenbei bestaetigt der Lauf, was ohnehin galt: Der Regler erreicht Messlatte,
Deflated Sharpe und Parameter-Plateau gar nicht - er bewegt den DSR um 0,012,
und es fehlen 0,142. Wer an der Groesse dreht, aendert am harten Problem
nichts.

### Der Stand

Die Frage aus ``stand.py`` ist beantwortet: **Nein, mit dieser Strategie sind
15 % Rendite und 12 % Rueckgang nicht zugleich zu haben.** Was daraus folgt -
Schwelle senken, Rueckgangsgrenze anheben, oder beides so lassen und weiter
suchen -, ist eine Geschaeftsentscheidung und liegt beim Nutzer.

Versuchsstand 165, Suchbudget 35 von 100.

## Achtundfuenfzig. P7, ehrlich gebaut - und zwei Gates mehr

P7 stand seit dem ersten Tag auf der Liste und ist nie angefasst worden. Die
planbare Haelfte gab es laengst: ``data/termine.py`` holt FOMC-Entscheidungen
und Halbierungen, der Risk-Officer kennt das Veto, Befund 12 hat es gemessen
(2 von 156 Signalen, kein Gate bewegt). Offen war der Nachrichten-Teil.

### Warum es kein Nachrichten-Overlay geworden ist

Nachrichten haben eine Eigenschaft, die sie von Terminen grundsaetzlich
trennt: **Man weiss sie erst, wenn sie da sind.** Ein Overlay, das die
Schlagzeile vom 12. Maerz 2020 kennt und deshalb am 11. nicht einsteigt, misst
Hellsicht statt Vorsicht - es verbessert den Backtest und leistet im Betrieb
nichts. Das ist die teuerste Sorte Fehler, weil sie wie ein Erfolg aussieht.

Gebaut ist deshalb, was davon kausal zulaessig bleibt: die Reaktion auf den
**Abdruck** eines Schocks in bereits abgeschlossenen Kerzen. Eine Kerze gilt
als Schock, wenn ihre wahre Spanne den Median der dreissig Kerzen davor um das
Dreifache uebersteigt. Median statt Mittelwert, weil ein Mass, das der Schock
mitverschiebt, den naechsten schlechter erkennt. Gesperrt wird die Schockkerze
und die zwei danach - **kein Vorlauf**, denn vorher war nichts bekannt.

Schwelle und Nachlauf standen vor der ersten Messung fest.

### Erst auszaehlen, dann messen

Ein Gate-Lauf kostet einen Versuch und hebt die Huerde fuer alle kuenftigen
Kandidaten. Ob er sich lohnt, entschied eine vorab gesetzte Schwelle: fuenf
Prozent betroffene Einstiege.

    python -m cli schock          # kostet nichts, bewertet keinen Kandidaten

    Kerzen           6554
    Schockkerzen      217 (3,31 % der Reihe)
    gesperrte Kerzen  510
    Einstiegssignale  165
    davon gesperrt     13 (7,9 %)

7,9 % - sechsmal so viel wie beim Termin-Overlay und ueber der Schwelle. Also
gemessen.

### Das Ergebnis

Ein Versuch, BTC + ETH, Tageskerzen, alle elf Gates (165 -> 166):

                    Trades   CAGR   Rueckgang  SR/Trade    DSR   Gates
    ohne Overlay       154  13,47 %    10,64 %   0,2569  0,791    7/11
    mit Overlay        143  13,32 %     9,66 %   0,2659  0,782    9/11

**Neun von elf - der beste Stand, den dieses Projekt je hatte.** Elf Einstiege
weniger, die Rendite praktisch unveraendert, der Rueckgang von 10,64 auf
9,66 % gefallen und der Sharpe je Trade von 0,2569 auf 0,2659 gestiegen. Neu
bestanden: **Schlechtestes Jahr** und **Parameter-Plateau**.

Das Plateau ist dabei das aussagekraeftigere von beiden. Es misst, ob die
Strategie auf einer Kante steht; dass sie es ohne die Schock-Einstiege nicht
mehr tut, heisst, dass ein Teil ihrer Empfindlichkeit an genau diesen
Einstiegen hing.

### Was sich damit nicht geloest hat

Der Deflated Sharpe ist **gefallen** - 0,791 auf 0,782 -, obwohl der Sharpe je
Trade gestiegen ist. Das ist die Kopplung aus Befund 54, ein weiteres Mal:
bessere Trades, aber elf weniger davon, und ein Versuch mehr im Zaehler. Die
harte Huerde bleibt unberuehrt, und die Messlatte ebenfalls.

### Der Verdacht, der ausgeraeumt gehoerte

Die Sperre wird vorab ueber den ganzen Rahmen gerechnet, Testfenster
eingeschlossen. Das sieht nach Zukunftswissen aus. Der Verdacht waere
begruendet, wenn eine spaetere Kerze eine fruehere aendern koennte - also
wurde genau das geprueft: Die Sperre wird Kerze fuer Kerze aus einem
wachsenden Ausschnitt neu berechnet, so wie sie im Betrieb entstuende, und
ergibt **Zeichen fuer Zeichen dasselbe**. Dazu die Gegenprobe: Das Ende der
Reihe umschreiben bewegt am Anfang nichts.

Die Sperre haengt ausserdem an derselben Stelle wie der Terminkalender - in
``RiskOfficer.blockade``, nicht in der Live-Schleife. Der Grund steht dort seit
jeher: *"Jede Regel, die es zweimal gibt, laeuft irgendwann auseinander."*
Backtest und Betrieb sehen dieselbe Pruefung; nur die Erzeugung unterscheidet
sich (vorab aus der Datei, im Betrieb aus dem Puffer).

### Ein Nachsatz, der einen eigenen Lauf verdient

Befund 57 hat gemessen, dass 15 % Rendite und 12 % Rueckgang auf dem
Groessenregler unvereinbar sind - bei 20,5 fehlten 0,89 Renditepunkte. Der
Rueckgang liegt jetzt um knapp einen Punkt niedriger, also hat sich die Kurve
verschoben. Ob sie damit durch das Rechteck geht, ist eine **neue Messung**
und keine Schlussfolgerung. Der Betriebspunkt wird bis dahin nicht angefasst.

Versuchsstand 166, Suchbudget 36 von 100.

## Neunundfuenfzig. Neun von elf haben einen Tag gehalten

Befund 58 endete mit dem besten Stand, den dieses Projekt je hatte: Das
Schock-Overlay sperrt 13 von 165 Einstiegen, und zwei Gates kippen um - von 7
auf 9 von 11. Ich habe das berichtet, ohne die naheliegendste Gegenprobe
gemacht zu haben. Sie fehlte, und sie kippt das Ergebnis.

### Die zweite Erklaerung, die dieselben Zahlen erzeugt

**Weniger Trades sind manchmal einfach besser.** Wer aus 165 Einstiegen
irgendwelche 13 streicht, veraendert Rueckgang, schlechtestes Jahr und Sharpe
je Trade. Bei genug Auswahlmoeglichkeiten findet man immer eine, die gut
aussieht. Die Frage ist also nicht "hilft das Overlay", sondern **"hilft die
Auswahl der gesperrten Einstiege oder nur ihre Anzahl"**.

Die Null dazu: zweihundert Mal genauso viele Einstiegssignale zufaellig
ziehen und sperren - je Bein einzeln, weil das Overlay ungleich trifft (6 in
BTC, 7 in ETH). Eine Null mit anderer Verteilung misst die Verteilung mit.

    python -m cli sperrprobe --ziehungen 200      # kostet keinen Versuch

Entschieden wird an der Zahl bestandener Gates, und das Kriterium stand vor
der Messung fest: hoechstens fuenf Prozent der Ziehungen duerfen mithalten.
Ausdruecklich **nicht** "irgendeine von vier Kennzahlen ist auffaellig" - wer
vier prueft und die beste nimmt, findet fast immer eine.

### Das Ergebnis

    Kennzahl               gemessen            Zufall (Median, Spanne)   Anteil
    ---------------------------------------------------------------------------
    Gates bestanden            7/9             7.000 [5.000 bis 7.000]   66.5 %
    Rueckgang %                9.66          10.134 [8.021 bis 11.936]   26.0 %
    Schlechtestes Jahr        -9.34        -9.830 [-10.630 bis -7.180]   25.5 %
    Sharpe je Trade          0.2659            0.258 [0.213 bis 0.281]   28.0 %

**Zwei Drittel der zufaelligen Sperren halten genauso viele Gates.** Keine der
vier Kennzahlen kommt auch nur in die Naehe der fuenf Prozent. Der Gewinn kam
nicht daher, dass die *richtigen* Einstiege gesperrt wurden, sondern daher,
dass ueberhaupt welche gesperrt wurden.

Damit ist das Schock-Overlay als Verbesserung **nicht belegt**. Der Code
bleibt - er ist richtig, getestet, ohne Lookahead und geht denselben Weg wie
der Terminkalender -, aber der Stand des Kandidaten bleibt bei **7 von 11**.

### Was ich falsch gemacht habe

Ich habe im letzten Befund "der beste Stand, den dieses Projekt je hatte"
geschrieben und dabei genau die Pruefung ausgelassen, die dieses Projekt sonst
an jede Zahl anlegt. Der Fehler ist nicht das Overlay - das ist sauber gebaut.
Der Fehler ist, dass ich ein Ergebnis gemeldet habe, dessen naheliegendste
Alternativerklaerung ich nicht ausgeschlossen hatte.

Auffaellig hin oder her: Zwei gekippte Gates aus dreizehn entfernten Trades
war von Anfang an zu gut, um es ungeprueft zu glauben.

### Was bleibt

Ein Werkzeug, das beim ersten Einsatz einen eigenen Fehlschluss gefunden hat.
Es gilt ab jetzt fuer **jede** Massnahme, die Trades entfernt statt sie besser
zu machen - und davon gab es mehrere: Die Abkuehlung aus Befund 44 gehoert
genauso geprueft, und ihr Ergebnis steht bisher ungeprueft in der Liste der
geschlossenen Richtungen.

Ein Vorbehalt gehoert dazu: Die Kontrolle laesst Kosten-Stress und
Parameter-Plateau aus, weil zweihundert Ziehungen davon Stunden dauerten. Das
Parameter-Plateau ist eines der beiden Gates, die umgekippt sind, und ist
damit **nicht** einzeln abgesichert. An der Gesamtaussage aendert das nichts:
Schon ueber die neun guenstigen Gates halten zwei Drittel der Ziehungen mit.

Versuchsstand 166 unveraendert - eine Kontrollrechnung ueber die eigene
Messung ist keine Hypothese ueber den Markt.

## Sechzig. Zwei Wege, dieselben zwei Gates - und beide sind Zufall

Befund 59 endete mit einer Ansage: Die Sperrprobe gilt fuer **jede** Massnahme,
die Trades entfernt statt sie besser zu machen, und die Abkuehlung aus Befund
44 steht ungeprueft in der Liste der geschlossenen Richtungen.

Beim Nachlesen faellt auf, wie genau die beiden Faelle einander gleichen:

    Massnahme          Trades   Gates   neu bestanden
    Abkuehlung 3        152 -> 140   9/11   Schlechtestes Jahr, Parameter-Plateau
    Schock-Overlay      154 -> 143   9/11   Schlechtestes Jahr, Parameter-Plateau

Zwei voellig verschiedene Eingriffe - eine Sperrfrist nach jedem Trade, eine
Reaktion auf Volatilitaetsschocks -, ungefaehr gleich viele Trades weniger, und
**dieselben zwei Gates** kippen. Das ist kein Zufall zweier Zufaelle, das ist
ein Muster.

### Beide durch dieselbe Mechanik

Die Abkuehlung wirkt im Betrieb ueber ``cooldown_bars``, das Overlay ueber eine
Sperre. Fuer die Kontrolle wird die Abkuehlung deshalb **als Sperre
nachgebildet** - genau die Signale, die sie blockiert haette. Sonst
unterschieden sich echter Fall und Ziehung nicht nur in der Auswahl, sondern
auch im Weg dorthin.

    python -m cli sperrprobe --massnahme abkuehlung --kerzen 3 -n 150

Gesperrt werden dabei 3 Einstiege in BTC und 9 in ETH.

### Das Ergebnis

    Kennzahl               gemessen            Zufall (Median, Spanne)   Anteil
    ---------------------------------------------------------------------------
    Gates bestanden            7/9             7.000 [5.000 bis 7.000]   70,0 %
    Rueckgang %               10.11          10.069 [8.195 bis 12.160]   53,3 %
    Schlechtestes Jahr        -9.79        -9.750 [-10.620 bis -7.430]   53,3 %
    Sharpe je Trade          0.2568            0.257 [0.214 bis 0.280]   50,0 %

**Die Abkuehlung liegt in jeder einzelnen Kennzahl auf dem Median.** Nicht
knapp daneben - auf dem Median. Sie leistet exakt so viel wie das Streichen
derselben Anzahl beliebiger Einstiege, und keinen Deut mehr. Beim
Schock-Overlay lagen die Anteile noch bei 26 bis 28 %; hier sind es 50 bis 53.

### Der allgemeine Befund

Damit ist etwas belegt, das ueber beide Einzelfaelle hinausgeht: **Zwei der elf
Gates - Schlechtestes Jahr und Parameter-Plateau - reagieren auf die Anzahl der
Trades, nicht auf ihre Auswahl.** Wer irgendwelche zwoelf von hundertvierzig
Einstiegen streicht, besteht sie mit ordentlicher Wahrscheinlichkeit.

Befund 44 hatte das halb gesehen und aus dem falschen Grund richtig
geschlossen. Dort stand: *"Neun von elf klingt nach Fortschritt und ist an
dieser Stelle das Gegenteil"* - begruendet damit, dass Deflated Sharpe und
Messlatte sich verschlechtern. Das stimmte. Was dort fehlte, ist der schaerfere
Punkt: Die zwei reparierten Gates waren gar keine Reparatur.

Die Liste der geschlossenen Richtungen ist entsprechend berichtigt. "Abkuehlung
repariert zwei Gates" stand seit Wochen falsch darin.

### Was das fuer die Suche heisst

Die Gate-Zahl taugt noch weniger als Fortschrittsmass, als Abschnitt neunzehn
schon festhielt. Dort ging es um die Rangfolge zwischen Risiko-Gates und
Deflated Sharpe; hier kommt ein zweiter Grund dazu, und er ist unangenehmer:
Zwei Gates lassen sich durch blosses Weglassen erreichen, ohne dass irgendetwas
besser geworden waere.

Praktisch folgt daraus eine Regel, die ab sofort gilt: **Jede Massnahme, die
Trades entfernt, ist erst dann ein Ergebnis, wenn sie die Sperrprobe
bestanden hat.** Bisher hat das keine getan.

Versuchsstand 166 unveraendert - Kontrollrechnungen ueber die eigene Messung
sind keine Hypothesen ueber den Markt.

## Einundsechzig. Elf Gates, aber nicht elf Fragen

Aus Befund 60 folgt eine unangenehmere Frage, als dort gestellt wurde. Wenn
zwei Massnahmen dieselben zwei Gates kippen und beide Male nur gestrichen
haben - messen diese Gates dann ueberhaupt Verschiedenes? "Sieben von elf"
liest sich wie sieben von elf unabhaengigen Huerden. Ob es das ist, stand nie
fest.

    python -m cli gatemuster      # liest nur Berichte, kostet keinen Versuch

Gerechnet ueber 56 Messpunkte aus ``reports/`` - Reglerfahrten und gepflanzte
Reihen -, je Paar die Korrelation zweier Ja-Nein-Groessen (Phi). Bewusst Phi
und nicht die Uebereinstimmung: Zwei Gates, die praktisch immer bestehen,
stimmen zu 100 % ueberein, ohne etwas miteinander zu tun zu haben.

### Zwei Gates sagen ueber alle 56 Punkte dasselbe

Und sie bedeuten das **Gegenteil** voneinander:

* **Stichprobengroesse: 56 von 56.** Nie gerissen. Das Gate hat seine Arbeit
  getan, indem es die schlechteren Kandidaten frueher aussortiert hat - die
  tauchen in dieser Wolke gar nicht mehr auf.
* **Deflated Sharpe: 0 von 56.** Ueber alle Messpunkte hinweg ist kein
  einziger daran vorbeigekommen. Das ist keine Huerde mehr, an der sich
  Fortschritt ablesen liesse - das ist die Wand.

Mein erster Anlauf warf beide in einen Satz und erklaerte sie gemeinsam damit,
die Vorauswahl habe schon gewirkt. Fuer ein nie bestandenes Gate ist das genau
falsch herum, und der Fehler waere in der Zusammenfassung stehen geblieben,
wenn ich die Zahlen nicht einzeln angesehen haette.

### Was zusammenlaeuft

    Paar                                       Phi   gleich
    Bestaendigkeit / Out-of-Sample-Sharpe     +0,90     98 %
    Drawdown / Messlatte                      -0,74     12 %
    Monte-Carlo / Regime-Aufteilung           +0,64     93 %
    Drawdown / Schlechtestes Jahr             +0,49     71 %
    Parameter-Plateau / Regime-Aufteilung     -0,48     14 %

**Bestaendigkeit und Out-of-Sample-Sharpe sind praktisch ein Gate.** In 98 %
der Punkte fallen sie gleich aus. Wer eines von beiden bewegt, bewegt das
andere mit - zwei Zeilen in der Gate-Liste, eine Anstrengung.

**Drawdown und Messlatte laufen gegeneinander** (Phi -0,74, nur 12 % gleich).
Das ist Befund 57 aus voellig anderen Daten: Dort wurde auf dem Groessenregler
gemessen, dass 15 % Rendite und 12 % Rueckgang unvereinbar sind. Hier faellt
dasselbe ueber 56 Punkte aus acht Reglerfahrten heraus, ohne dass danach
gesucht wurde.

### Was daraus folgt - und was ausdruecklich nicht

**Nicht:** ein Gate zu streichen, weil es "ohnehin dasselbe misst". Das waere
die eleganteste Art, die Latte zu senken, und der Grundsatz dagegen ist
eindeutig. Das Urteil des Befehls sagt es an jeder Stelle selbst mit.

**Wohl aber** eine schaerfere Sicht auf den eigenen Stand. Von den vier offenen
Gates des Kandidaten sind nach den Befunden 57, 60 und diesem:

    Schlechtestes Jahr   durch blosses Streichen erreichbar        (Befund 60)
    Parameter-Plateau    durch blosses Streichen erreichbar        (Befund 60)
    Messlatte            laeuft gegen den Drawdown, Nutzerfrage    (Befund 57, 61)
    Deflated Sharpe      0 von 56 - die Wand                       (Befund 61)

Von vier offenen Gates ist genau **eines** ein ungeloestes Qualitaetsproblem.
Zwei sind Zaehlartefakte, eines ist eine Geschaeftsentscheidung. Wer "sieben
von elf" liest und daraus vier Baustellen ableitet, hat drei davon zu viel.

Das aendert nichts an der Lage - es benennt sie genauer. Die verbleibenden 64
Versuche des Suchbudgets haben genau ein Ziel, und es heisst Deflated Sharpe.

Versuchsstand 166 unveraendert.

## Zweiundsechzig. Die Huerde in Prozent - und wo die Gebuehr sie einholt

Befund 61 hat den Stand zugespitzt: genau ein ungeloestes Qualitaetsproblem,
und es heisst Deflated Sharpe. Befund 54 hat gezeigt, warum es auf Tageskerzen
nicht loesbar ist - Qualitaet und Menge sind gekoppelt, weil die Historie nur
rund 3300 Tage hergibt.

Damit liegt die naheliegende Hoffnung auf der Hand, und sie ist rechenbar. Der
noetige Sharpe je Trade faellt mit ``1/sqrt(N)``:

    150 Trades  ->  0,3606        2000 Trades  ->  0,0974
    500 Trades  ->  0,1954       10000 Trades  ->  0,0435

Zweitausend Trades zu je 0,097 ergeben dieselbe Guete wie hundertfuenfzig zu je
0,36. Auf Fuenfzehnminutenkerzen liegen **222 700** Kerzen je Markt - der Platz
waere da.

**Der Haken ist ebenfalls rechenbar:** Der noetige Vorteil faellt mit der
Wurzel, die **Gebuehr je Trade bleibt konstant** bei 0,04 % vom Nominalwert.
Irgendwo schneiden sich die Linien.

### Die Umrechnung

Ein Sharpe je Trade ist ein Vielfaches der Streuung. Wer 0,36 braucht und
dessen Trades um 1,24 % streuen, braucht 0,45 % Bruttobewegung - plus Gebuehr.
Die Streuung wird dabei **gemessen**, nicht mit der Wurzel der Zeit
hochgerechnet: Diese Abkuerzung setzt Unabhaengigkeit voraus, die es bei Kursen
nicht gibt, und liefert fuer kurze Haltedauern zu kleine Zahlen - also eine zu
optimistische Rechnung.

    python -m cli taktung        # kostet keinen Versuch

### 15 Minuten, vier Stunden Haltedauer (Streuung 1,24 %)

      Trades  noetiger SR   brutto %  mit Kosten %  davon Gebuehr  passt
         150       0,3606     0,4483        0,4883             8 %  ja
        1000       0,1378     0,1714        0,2114            19 %  ja
        2000       0,0974     0,1210        0,1610            25 %  ja
       10000       0,0435     0,0541        0,0941            43 %  ja

**Arithmetisch tragfaehig bis 10 000 Trades.** Bei Tageskerzen dagegen passt
keine einzige Stufe: 5331 Kerzen bei 40 Tagen Haltedauer ergeben hoechstens 133
Trades je Markt, und die Streuung ueber 40 Tage betraegt 47,6 %.

### Und jetzt die unangenehme Zusammenfuehrung

Der noetige Bruttovorteil bei 10 000 Trades ist **0,094 % je Trade**. Der
Vorteilsscan hat auf denselben Kerzen gemessen, was tatsaechlich da ist - die
staerkste Zelle bei BTC (16 Kerzen Rueckblick, 16 halten) hat eine Spanne von
**0,088 %**, und eine Regel erntet davon grob die Haelfte.

Das ist dieselbe Groessenordnung. Und genau diese Zelle ist die, an der der
Scan gescheitert ist: erste Haelfte t = -2,90, zweite Haelfte t = +0,29 -
vollstaendig verschwunden, obwohl die zweite Haelfte einen Effekt dieser
Groesse gesehen haette.

**Die Rechnung schliesst den Weg also nicht aus - sie zeigt, dass der noetige
Vorteil genau in der Groessenordnung dessen liegt, was auf diesen Daten
nachweislich instabiles Rauschen ist.** Wer dort sucht, sucht etwas, das von
einem Artefakt nicht zu unterscheiden waere, und muesste 43 % davon an die
Boerse abgeben.

### Zwei eigene Fehler auf dem Weg

**Erstens** waehlte meine Auswertung die Stufe mit dem *kleinsten*
Kostenanteil - und das ist immer die mit den wenigsten Trades, weil dort der
noetige Vorteil am groessten ist. Damit meldete die Rechnung ausgerechnet den
Punkt, um den es nicht geht: Der ganze Sinn ist zu pruefen, ob **viele** Trades
tragen. Gemeldet wird jetzt die groesste tragfaehige Stufe.

**Zweitens** gilt ``hoechstens_trades`` fuer *einen* Markt bei durchgehendem
Halten. Der gemessene Kandidat handelt einen Korb aus zwei Beinen und kommt
deshalb auf 154 Trades, obwohl die Schranke fuer BTC allein bei 133 liegt. Der
Vorbehalt steht jetzt im Kopf jeder Ausgabe.

### Was daraus folgt

Der Nutzer hat in jedem Auftrag ``cli backfill --intervall 15`` als offenen
Punkt gefuehrt. **Die Daten liegen hier bereits**: 222 700 Kerzen je Markt vom
30.03.2020 bis 05.08.2026. Der Backfill auf seinem Rechner bleibt noetig, wenn
er selbst rechnen will - fuer diese Frage war er es nicht.

Und die Frage ist beantwortet, ohne einen Versuch auszugeben: Fuenfzehn Minuten
sind arithmetisch nicht ausgeschlossen, aber der Vorteil, den es dort braeuchte,
ist so klein wie das, was der Scan bereits als verschwunden gemessen hat. Das
ist kein Verbot, dort zu suchen - es ist der Preis, den man vorher kennen
sollte.

Versuchsstand 166 unveraendert.

## Dreiundsechzig. Die Uhrzeit - die Quelle, die Tageskerzen nicht kennen

Befund 62 hat gerechnet, dass Fuenfzehnminutenkerzen den Deflated Sharpe
arithmetisch tragen koennen. Was fehlt, ist ein Vorteil dieser Groesse.
``cli scan`` hat dort gesucht und nichts Stabiles gefunden - aber er prueft
**eine** Art Signal: Sagt die Richtung der letzten N Kerzen etwas ueber die
naechsten M? Das ist Momentum, in beide Richtungen gelesen.

Die Uhrzeit ist eine andere Quelle, und sie hat eine Eigenschaft, die keine
andere hat: **Auf Tageskerzen ist sie prinzipiell unsichtbar.** Jede Tageskerze
ist ein Tag; es gibt nichts, woran sich eine Stunde ablesen liesse. Alle 62
bisherigen Befunde konnten diese Frage nicht beantworten - sie haben sie nie
gestellt.

### Warum feste Fenster

Bei 96 Viertelstunden gaebe es rund 4600 moegliche Zeitfenster. Wer die alle
prueft und das beste nimmt, hat die Zahl seiner Versuche gemessen und sonst
nichts. Geprueft werden deshalb sieben **vorab festgelegte** Fenster aus der
Marktstruktur - die drei Handelssitzungen, ihre zwei Ueberschneidungen, Abend
und Nacht. Sie standen fest, bevor eine Zahl gerechnet war.

    python -m cli tageszeit            # kostet keinen Versuch

### Zwei Konstruktionsfehler, beide vom Test gefunden

**Erstens** verglich meine Messung die *Summe* im Fenster mit der Summe
ausserhalb - also eine Stunde gegen dreiundzwanzig. Die Differenz misst dann
ueberwiegend die Fensterlaenge. Der Test mit einem gepflanzten Effekt bei
14 Uhr fand prompt nicht die 14, sondern eine erfundene 21. Verglichen wird
jetzt der Durchschnitt **je Kerze**.

**Zweitens** waere der naheliegende Test "Fensterrendite gegen null" bei einem
Markt, der sich vervielfacht hat, ueberwiegend eine Messung des Grundtrends -
genau davor warnt der Kopf des Vorteilsscans. Verglichen wird deshalb gegen das
Aussen, gepaart je Tag: Beide Seiten tragen denselben Marktzustand, und er
faellt in der Differenz heraus.

### Das Ergebnis: kein Fund

    BTC     Fenster          UTC    je Tag       t      netto
            Asien          00-06  -0,0794 %   -2,25   +0,0394 %
            Abend          21-24  +0,0464 %   +2,01   +0,0064 %
            Europa         07-16  +0,0296 %   +0,62   -0,0104 %

    ETH     Abend          21-24  +0,0632 %   +2,09   +0,0232 %
            Asien          00-06  -0,0735 %   -1,56   +0,0335 %

Bei sieben geprueften Fenstern liegt die Schwelle bei **2,69**, nicht bei 2,00.
Kein Markt erreicht sie. Auch die Landkarte der 24 Einzelstunden aendert daran
nichts: Die staerkste ist 21 Uhr mit t = +2,90 - bei dann 31 geprueften
Fenstern liegt die Schwelle bei 3,15.

### Was auffaellt und trotzdem nichts beweist

Beide Maerkte zeigen dasselbe Vorzeichenmuster: Asien negativ (-0,079 % und
-0,074 %), Abend positiv (+0,046 % und +0,063 %). Das sieht nach einer
marktuebergreifenden Bestaetigung aus und ist keine - **BTC und ETH laufen im
Gleichschritt.** Zwei hochkorrelierte Maerkte sind ein Markt mit zwei Namen,
und ihre Uebereinstimmung ist keine zweite Beobachtung.

Die Schwelle nachtraeglich zu senken, weil das Muster huebsch aussieht, waere
genau der Selbstbetrug, gegen den der Scan gebaut ist. Sie stand vorher fest,
und sie ist gerissen.

### Der Stand

Damit ist die letzte Informationsquelle geprueft, die auf Tageskerzen
prinzipiell nicht zugaenglich war. Sie liefert nichts, was die Kosten traegt.
Zusammen mit Befund 62 heisst das: Fuenfzehn Minuten sind arithmetisch offen,
aber weder Momentum noch Uhrzeit liefern dort einen Vorteil, der die drei
Huerden haelt.

Versuchsstand 166 unveraendert - 36 von 100 des Suchbudgets verbraucht, und
keiner davon in diesem Lauf.

## Vierundsechzig. Ein Satz aus dem Auftrag, der nirgends im Code stand

Der Nutzer nennt ihn seit dem ersten Tag: *"Generation 5 gehoert auf
Tageskerzen (-i D), Generation 6/7 auf 15-Minuten-Kerzen."* Ich habe ihn
vierundsechzig Befunde lang als Randnotiz gelesen. Er ist keine.

Im Katalog steht die Zuordnung sehr wohl - aber nur als Kommentar:

    #: Sechste Generation: schnelles Handeln auf 15-Minuten-Kerzen, mit Hebel.
    #: Siebte Generation: der Katalog der bekannten Scalp-Setups.

**Nichts hinderte daran, sie auf Tageskerzen zu fahren.** Dieselben
Periodenzahlen bedeuten dort sechsundneunzigmal laengere Zeitraeume: eine
voellig andere Regel unter demselben Namen. Und so ein Lauf ist nicht nur
sinnlos, er ist teuer - jeder Versuch hebt die Huerde des Deflated Sharpe
dauerhaft fuer alle folgenden.

### Die stillere Haelfte, und sie ist schlimmer

Die Bestenliste ist nach ``genome_id`` geschluesselt. Dieselbe Regel hat auf
Tageskerzen und auf Viertelstunden **dieselbe ID** - das Genom ist ja
identisch, nur die Kerzen darunter sind andere. Zwei solche Ergebnisse
konkurrierten deshalb um denselben Platz, und ``record`` behaelt das bessere.

Das heisst: Ein 15-Minuten-Ergebnis haette ein Tageskerzen-Ergebnis
verdraengen koennen, ohne dass irgendwo steht, dass beide gar nicht dasselbe
gemessen haben. Der Eintrag trug die Generation mit, das Intervall nicht.

### Ist es passiert?

**Das laesst sich nicht mehr feststellen, und genau das ist der Punkt.** Im
Leaderboard stehen Generationen 0, 5, 8 und 9; die 15-Minuten-Kataloge 6 und 7
tauchen nicht auf. Auf welchem Intervall die vorhandenen Eintraege gemessen
wurden, steht nirgends - die Information wurde nie mitgeschrieben.

Ein Mangel, der sich nicht nachweisen laesst, ist trotzdem einer. Er ist nur
schlechter zu beziffern.

### Was gebaut wurde

``research/seeds.VORGESEHEN`` haelt die Zuordnung jetzt als Daten statt als
Kommentar, und ein Test besteht darauf, dass **jede** Generation dort einen
Eintrag hat - eine neue ohne Eintrag liefe sonst stillschweigend ueberall, und
genau diese Stille war der Fehler.

``_pruefe_generation`` sitzt an allen drei Stellen, die einen Katalog laden
(``wettbewerb``, ``research``, ``korb``). Sie **bricht ab** statt zu warnen:

    Generation 6 ist fuer 15-Kerzen gedacht, nicht fuer 1d.
    Dieselben Periodenzahlen bedeuten hier andere Zeitraeume [...] und sie
    wuerde Versuche kosten.

Und ``Entry`` traegt jetzt das Intervall. Zwei Ergebnisse verschiedener
Kerzenlaengen gelten als nicht vergleichbar und verdraengen einander nicht
mehr. Alte Eintraege ohne Intervall bleiben ausdruecklich vergleichbar - sonst
wuerden sie nie mehr abgeloest, und die Liste friere an dieser Stelle ein.

Nebenbei berichtigt: Der Docstring von ``load_seeds`` behauptete "Standard ist
die neueste" bei einem Standard von 5. Das war spaetestens falsch, als
Generation 6 dazukam.

### Ein eigener Fehler beim Pruefen

Fuer die Gegenprobe - laeuft die *richtige* Paarung ungehindert durch? - habe
ich ``korb --generation 6 --intervall 15`` gestartet. Das ist ein voller
Walk-Forward ueber 445 400 Kerzen und haette **Versuche gekostet**, fuer eine
Frage, die der Unit-Test ``test_die_richtige_paarung_laeuft_durch`` kostenlos
beantwortet. Abgebrochen, bevor der Zaehler geschrieben wurde; er steht
unveraendert bei 166.

Das ist derselbe Fehler in klein, gegen den dieser ganze Befund gebaut ist:
einen Lauf starten, ohne vorher zu rechnen, was er kostet.

Versuchsstand 166 unveraendert.

## Fuenfundsechzig. Fast vierzehn Versuche fuer ein Ergebnis, das schon dastand

Nach Befund 64 war der Weg frei fuer den einen Auftragspunkt, der nie
ausgefuehrt schien: Generation 6 und 7 auf 15-Minuten-Kerzen. Die Sperre steht,
die Daten liegen vor, im Leaderboard tauchen beide Generationen nicht auf.

Vor dem Lauf der Preis: Generation 6 hat vier Kandidaten, Generation 7 hat
zehn. **Vierzehn zusammen** - und genau diese Zahl steht in Befund 29:

    ## Neunundzwanzig. Generation 6 und 7 auf 15 Minuten - alle vierzehn tot

Alles war schon gemessen. 1 von 9 Gates bei jedem einzelnen, Jahresrenditen
zwischen -9 % und -44 %, Rueckgaenge bis 95 %, und sie verlieren **brutto** -
vor jeder Gebuehr. Der Punkt stand seit Befund 29 erledigt da, und ich war
dabei, vierzehn Versuche auszugeben, um ihn ein zweites Mal zu beantworten.

### Warum das passieren konnte

Der Auftrag listet in jeder Runde dieselben vier offenen Punkte. Zwei davon
waren laengst abgearbeitet - die 15-Minuten-Generationen seit Nummer 29, das
Termin-Overlay seit Nummer zwoelf. Es gab nur keine Stelle, an der das
nachzulesen war.

``research/stand.py`` fuehrt die geschlossenen **Richtungen**, die
**Entscheidungen** des Nutzers und was nur auf **seinem Rechner** laeuft. Was
fehlte, war der Stand der Punkte aus dem Auftrag selbst. Sie standen nur im
Auftrag, und der ist keine Datei, die man nachschlagen kann.

### Was gebaut wurde

``Auftragspunkt`` mit derselben Regel wie ``Richtung``: **Erledigt ohne
Fundstelle wird abgewiesen.** Ein Punkt, der als abgearbeitet gilt, ohne dass
irgendwo die Messung steht, ist eine Behauptung - und genau die Sorte
Behauptung hat mich hier fast vierzehn Versuche gekostet.

    PUNKTE AUS DEM AUFTRAG
    OK P7: News- und Termin-Overlay    beides gebaut und gemessen;
                                       die Wirkung ist nicht belegt   (Nr. 59)
    OK Research-KI im Wettbewerb       vier Vorschlaege gemessen -
                                       alle schlechter                (Nr. 53)
    OK Generation 6/7 auf 15-Minuten   alle 14: 1 von 9 Gates,
                                       -9 bis -44 % p.a.              (Nr. 29)
    OK Generation 5 auf Tageskerzen    Zuordnung liegt als Daten vor,
                                       Fehlpaarung wird gesperrt      (Nr. 64)
    -- backfill 15m beim Nutzer        Daten liegen hier vor; auf dem
                                       eigenen Rechner weiter noetig  (Nr. 62)

    -> 4 von 5 abgearbeitet. Wer einen davon erneut misst, zahlt Versuche
       fuer ein Ergebnis, das schon dasteht.

### Was ehrlich dazugehoert

Der Stand ist **gepflegt**, nicht gemessen - genauso wie die Liste der
geschlossenen Richtungen. Er kann veralten, und er kann falsch sein. Dagegen
hilft nur die Fundstellenpflicht: Jede Zeile laesst sich in einer Minute
nachpruefen, und wer eine nicht nachpruefen kann, soll ihr nicht glauben.

Und ein Punkt bleibt ausdruecklich offen: Der Backfill auf dem Rechner des
Nutzers. Hier liegen die Daten (Befund 62), dort noch nicht - wer selbst
rechnen will, braucht ihn.

Beinahe waeren 14 von 64 verbliebenen Versuchen fuer nichts draufgegangen.
Versuchsstand 166 unveraendert, Suchbudget 36 von 100.

## Sechsundsechzig. Die Huerde, die nur fuer die anderen galt

``research/vorteilsscan.py`` verlangt von **jedem neuen Fund** drei Dinge, und
das zweite lautet: in beiden Haelften des Zeitraums dasselbe Vorzeichen. Der
Kopf dort begruendet es scharf:

    "Ein Vorteil, den es nur in der ersten Haelfte gab, ist entweder
    wegarbitriert oder war nie da. Beides heisst, dass er morgen nicht zur
    Verfuegung steht."

An dieser Huerde ist der erste 15-Minuten-Fund gescheitert und in Befund 63
die Tageszeit. **Der Spitzenkandidat ist nie daran gemessen worden.**

Das ist die gefaehrlichere Richtung der Ungleichbehandlung: Ein neuer Fund, der
die Huerde reisst, wird verworfen und kostet nichts weiter. Ein Bestand, der
sie reissen wuerde, steht seit Wochen im Mittelpunkt jeder Messung - und die
gesamte Diagnose aus Befund 61 haengt daran, dass ueberhaupt ein Vorteil da
ist, der bloss zu klein ist.

    python -m cli haelften        # kostet keinen Versuch

### Das Ergebnis

    Haelfte   Trades   Mittel R   Streuung   SR/Trade      t
    erste         77     1,8483     6,3754     0,2899   2,54
    zweite        77     1,0039     4,2947     0,2338   2,05

**Der Vorteil haelt.** Beide Haelften positiv, die zweite mit t = +2,05 fuer
sich genommen auffaellig - genau der Massstab, den der Scan an jeden neuen Fund
anlegt. Die Diagnose aus Befund 61 bleibt damit stehen: Es fehlt Groesse, nicht
Gegenwart.

### Was ehrlich dazugehoert

**Erstens: t = 2,05 ist knapp.** Die Schwelle ist 2,0. Ein Zehntel weniger, und
dieser Befund haette anders gelautet.

**Zweitens: Der Vorteil schwaecht sich ab.** Der Sharpe je Trade faellt von
0,2899 auf 0,2338, also um 19 %. Ob dieser Abfall selbst mehr ist als
Rauschen, habe ich gemessen statt vermutet: **t = 0,96.** Er ist nicht
auffaellig - zwei Haelften zu je 77 Trades koennen so weit auseinanderliegen,
ohne dass sich etwas geaendert haette.

**Drittens, und das ist die unangenehmste Zahl:** Bei 154 Trades verlangt die
Grenzlinie 0,3557 Sharpe je Trade. Bei 77 sind es **0,5108**. Wer also nur die
zweite Haelfte haette, braeuchte mehr als das Doppelte dessen, was dort steht.
Das ist keine neue Erkenntnis, sondern dieselbe Kopplung aus Befund 54 - hier
noch einmal von der Zeitachse aus gesehen.

### Die Falle, die eingebaut werden musste

"Nicht stabil" heisst zweierlei: der Vorteil ist weg, oder man haette ihn hier
gar nicht sehen koennen. Bei 77 Trades je Haelfte ist die zweite Deutung der
wahrscheinlichere Fall, nicht die Ausnahme. Das Modul rechnet deshalb - wie
``vorteilsscan.erkennbare_spanne`` - mit, welcher Unterschied in der zweiten
Haelfte ueberhaupt haette auffallen koennen, und meldet ein **Unentschieden**
statt eines Scheiterns, wenn er zu gross ist.

Hier war die Auskunft nicht noetig, weil der Test bestanden wurde. Sie waere
es gewesen, wenn er knapp gescheitert waere - und dann haette die
Unterscheidung ueber die ganze Diagnose entschieden.

Versuchsstand 166 unveraendert, Suchbudget 36 von 100.

## Siebenundsechzig. Derselbe Fehler, eine Ebene tiefer

Beim Nachsehen, ob "mehr Maerkte" wirklich geschlossen ist, fiel eine Zeile im
Bericht auf: ``'versuche': 102``. Er stammt vom 8. August. Die DSR-Werte darin
sind gegen **102** Versuche gerechnet, heute stehen wir bei 166.

Das ist kein Detail. Der Deflated Sharpe faellt mit jedem Versuch, und zwar
spuerbar. An einem Punkt gemessen, der die noetigen Angaben mitbringt -
dieselben Trades, nur ein anderer Versuchsstand:

    Vola-Ziel 20,5    bei 112 Versuchen   0,8600
                      bei 146 Versuchen   0,8235
                      bei 166 Versuchen   0,8042

**0,056 Unterschied, ohne dass sich an der Strategie irgendetwas geaendert
haette.** Und ``cli front`` hat genau solche Werte nebeneinandergelegt: 23
Punkte aus Berichten zwischen 102 und 162 Versuchen, verglichen, als stuenden
sie gegen dieselbe Schwelle. Die aelteren sehen dabei systematisch besser aus.

### Warum das besonders aergerlich ist

Genau dieser Fehler wurde schon einmal behoben - **Befund 50: "Die Bestenliste
verglich gegen verschiedene Huerden."** Dort bekam ``Entry`` das Feld
``versuche`` und eine Methode ``dsr_bei``. In den Berichten steckte er weiter,
und die Auswertung, die sie zusammenlegt, hat ihn geerbt.

Eine Ebene tiefer, dieselbe Ursache: Eine Zahl wird gespeichert, ohne die
Bedingung, unter der sie gilt.

### Was gebaut wurde

``Messpunkt`` traegt jetzt den Versuchsstand seines Berichts und rechnet auf
Wunsch um - dieselbe Umrechnung wie in der Bestenliste, aus derselben Quelle.
``Front.bestanden``, ``bester`` und die Tabelle nutzen den umgerechneten Wert.

Ein Test haelt die Richtung fest: Ein Punkt, der bei 20 Versuchen 0,97 hatte,
gilt bei 5000 nicht mehr als bestanden.

### Die Luecke, die bleibt - und sie ist groesser als die Korrektur

Umrechnen braucht die **Form** der Verteilung. Nur drei der 23 Punkte tragen
sie mit; sie stammen aus dem einzigen Bericht nach Einfuehrung von
``_formkennzahlen``. Die anderen zwanzig behalten den Wert ihres Laufs und sind
in der Tabelle mit ``!`` markiert.

Darunter ist ausgerechnet der hoechste: **'Perioden-Faktor 1' mit 0,851 stammt
von 112 Versuchen.** Die Zahl, die seit Befund 49 als "hoechster Deflated
Sharpe der ganzen Familie" durch alle Berichte laeuft, ist damit zu
optimistisch - um wie viel, laesst sich nicht sagen, weil die Form fehlt. Die
Groessenordnung ist am Vola-Ziel-Punkt oben ablesbar.

Eine Umrechnung zu erfinden waere schlimmer als die Luecke. Sie ist jetzt
wenigstens sichtbar statt unsichtbar.

### Was sich am Ergebnis nicht aendert

Kein Punkt erreicht die Schwelle - vorher nicht und nachher nicht, und die
Korrektur schiebt alle Werte in dieselbe Richtung. Die Aussage aus Befund 49
steht; nur die Zahl daneben war freundlicher, als sie sein durfte.

Nebenbei bestaetigt: "Mehr Maerkte" ist gruendlich geschlossen. Alle 15
Kombinationen sind gemessen, und mehr Beine machen es **schlechter** -
BTC+ETH+XRP bringt 260 Trades statt 152 und faellt dabei von 0,86 auf 0,42.

Versuchsstand 166 unveraendert.

## Achtundsechzig. Die sechste Eingabe - die einzige, die geraten wird

Der Deflated Sharpe entscheidet seit Wochen ueber dieses Projekt. Seine Formel
hat sechs Eingaben. Fuenf davon werden gemessen: Sharpe je Trade, Stichprobe,
Schiefe, Woelbung, Versuchszahl. Die sechste steht als Kommentar in
``research/gates.py``:

    Ist ``sharpe_variance`` nicht bekannt, wird die asymptotische Varianz
    des Sharpe-Schaetzers ``1/(n-1)`` verwendet.

``V`` ist bei Bailey und Lopez de Prado die **Streuung der Sharpe-Schaetzer
ueber die Versuche**. Sie laesst sich erheben, wenn man aufschreibt, was man
probiert hat. Dieses Projekt hat sie nie erhoben - und die Zerlegung in
``cli stand`` nennt seit jeher "vier Groessen", als gaebe es die fuenfte nicht.

### Wie viel daran haengt

Am Spitzenkandidaten gemessen, alle anderen Eingaben unveraendert:

    sqrt(V) = 0,0808   angenommen (Gate)   DSR 0,7865   durchgefallen
    sqrt(V) = 0,0657   Kippunkt            DSR 0,9500   Grenze
    sqrt(V) = 0,0608   aus 28 Versuchen    DSR 0,9725   bestanden

**Die Annahme liegt 23 % ueber dem Kippunkt.** Das Gate, an dem seit Befund 61
alles haengt, entscheidet sich an einer Zahl, die niemand gemessen hat - und
die naechstliegende Schaetzung faellt auf die andere Seite.

### Warum die gemessene Zahl trotzdem nicht eingesetzt wird

Das waere ein Einzeiler gewesen, mit einer Literaturstelle als Deckung. Er
haette das strengste Gate des Projekts umgedreht. Er ist trotzdem falsch:

Von 166 Versuchen liegen 28 mit ihrem Sharpe je Trade vor, 17 %. Und was
fehlt, fehlt nicht zufaellig. Berichte entstehen ueber **Reglerscans**, und ein
Reglerscan variiert einen Knopf um den Bestand herum; die 23 Punkte aus den
Berichten spannen 0,133 bis 0,264. Die Verlierer bekommen keinen Bericht - die
vierzehn 15-Minuten-Kandidaten aus Befund 29 mit -9 bis -44 % im Jahr haben
einen negativen Sharpe je Trade, der nirgends steht. Dazu zaehlt der Bestand
mehrfach: Jeder Scan misst auf seiner neutralen Stellung denselben Punkt.

Der Beleg ist keine Ueberlegung, sondern eine Messung. Nach Quelle getrennt:

    Berichte        23 Punkte   Streuung 0,0428   0,133 bis 0,264
    Bestenliste      5 Punkte   Streuung 0,1030   0,030 bis 0,248

**Die fuenf Eintraege aus der Bestenliste streuen fuer sich genommen breiter
als die Annahme.** Es sind die strukturell anderen Familien - Ausbrueche,
Rueckkehr zum Mittel -, und sie stehen nur deshalb dort, weil das Feld
``sharpe_je_trade`` in der Bestenliste jung ist. Nicht die Annahme ist zu hoch;
die Zusammenlegung ist zu schmal, weil die engste Quelle die meisten Punkte
stellt. Ein Sechstel mehr Abdeckung hat die Schaetzung schon von 0,0428 auf
0,0608 gehoben, und die fehlenden 138 sind systematisch die schlechteren.

Eine Huerde mit einem Wert zu senken, von dem man weiss, dass er zu niedrig
ist, ist das Gegenteil von Messen. Die Annahme bleibt stehen - sie ist die
strengere Richtung.

### Was gebaut wurde

``research/streuung.py`` sammelt die bekannten Versuchs-Sharpes aus Berichten
und Bestenliste, rechnet ihre Streuung je Quelle aus und beziffert den
Kippunkt. ``cli streuung`` zeigt beides nebeneinander; die Empfindlichkeit wird
mit genau den Argumenten gerechnet, mit denen ``run_admission`` das Gate
aufruft, und weicht das Ergebnis vom Gate ab, sagt der Befehl es.

Zwei Tests tragen die Datei. Einer verlangt, dass das Gate **keine** gemessene
Streuung hereinreicht - damit die Versuchung nicht eines Tages als Verbesserung
durchgeht. Der andere haelt fest, dass der Kippunkt zwischen Annahme und
Schaetzung liegt; laege er ausserhalb, waere die ganze Sache eine Randnotiz.

``Streuung.verwendbar`` ist kein Riegel fuer immer, sondern eine Bedingung:
90 % Abdeckung. Wer die Versuche aufschreibt, macht die Groesse messbar - und
erst dann ist die Frage, ob das Gate sie benutzen soll, ueberhaupt eine Frage.
Sie steht jetzt als Entscheidung in ``cli stand``, weil sie nicht mir gehoert.

### Was sich am Ergebnis nicht aendert

7 von 11 Gates, Versuchsstand 166, Suchbudget 36 von 100. Der Deflated Sharpe
bleibt durchgefallen, und die noetigen 13 % mehr Qualitaet je Trade bleiben
stehen. Was sich aendert, ist die Auskunft ueber diese Zahl: Sie ist nicht so
fest, wie sie aussah.

## Neunundsechzig. Ein Zaehler, der fallen konnte

Befund 68 endete mit einem Satz ueber ``state/trials.json``: *"haelt eine
einzige Zahl fest."* Beim Anfassen dieser Datei kam heraus, dass sie nicht nur
duenn ist, sondern **verlierbar**.

``load_trials`` gab bei einer unlesbaren Datei 0 zurueck. Der Kommentar daneben
benannte die Gefahr selbst - *"ein zu niedriger Zaehler macht die Deflated
Sharpe Ratio milder"* - und der Test dazu hiess
``test_corrupt_file_starts_at_zero``. Erkannt, benannt, mit einem
Protokolleintrag versehen und so gelassen.

Ein Protokolleintrag haelt nichts auf. Der Lauf rechnet weiter, prueft alle
Gates gegen den falschen Stand und schreibt ihn danach fest. Am
Spitzenkandidaten gemessen:

    166 Versuche   DSR 0,7865   durchgefallen
     45 Versuche   DSR 0,9430   durchgefallen
     22 Versuche   DSR 0,9809   **bestanden**
     11 Versuche   DSR 0,9955   **bestanden**

**Ein Dateifehler, gefolgt von einem Wettbewerb mit elf Genomen, haette das
strengste Gate des Projekts umgedreht.** Ohne Absicht, ohne dass jemand etwas
gelockert haette, sichtbar nur in einer Logzeile, die niemand liest. Das ist
dieselbe Groessenordnung wie in Befund 68 - aber dort ging es um eine
Modellannahme, hier um einen Weg, auf dem sich das Projekt selbst betruegt.

### Die Regel

Der Zaehler faellt nicht.

* Datei **fehlt** -> 0. Das ist der erste Lauf, da stimmt die 0.
* Datei **kaputt** -> Abbruch mit ``ZaehlerUnlesbarError``. Lieber steht das
  Projekt, als dass es stillschweigend milder wird.
* Ein **kleinerer** Wert wird nicht geschrieben, sondern protokolliert.

Der alte Test ist nicht geloescht, sondern umgeschrieben: Er haelt jetzt fest,
warum der Lauf stehenbleiben muss, samt der Zahlen von oben.

### Und das Verzeichnis dahinter

Wenn die Datei ohnehin angefasst wird, kann sie auch tragen, was Befund 68
gefehlt hat. ``research/versuche.py`` macht aus der nackten Zahl ein
Verzeichnis: Zu jedem neuen Versuch stehen Kennung, Zeitpunkt, Trade-Zahl,
Herkunft und **Sharpe je Trade** darin. ``cli wettbewerb`` und ``cli
vorschlag`` schreiben ihn mit, ``cli streuung`` liest ihn als dritte Quelle -
und als einzige, die vollstaendig werden **kann**: Sie bekommt jeden
geprueften Kandidaten, auch den, der nichts taugte. Berichte und Bestenliste
sammeln beide nur, was jemand aufschreiben wollte.

Das alte Format wird weiter gelesen; die 166 werden zum ``grundstock``,
ausdruecklich **ohne** Einzelnachweis. Sie nachtraeglich zu erfinden waere eine
Zahl ohne Messung an genau der Stelle, an der es um Messbarkeit geht.

### Was das nicht loest, und das gehoert dazu

Die Streuung wird dadurch **nicht** messbar. Das Suchbudget bricht bei 230
Versuchen ab; selbst wenn ab jetzt jeder einzelne belegt wird, endet die
Abdeckung bei rund 40 %, und ``streuung.MINDESTABDECKUNG`` verlangt 90. Die
Ersatzannahme im Gate bleibt also stehen - auf absehbare Zeit fuer immer.

Was sich aendert, ist etwas anderes: Der Versuchszaehler war bisher eine
Behauptung ohne Beleg. 166 stand da, und niemand haette gemerkt, wenn es 154
oder 11 gewesen waeren. Ab jetzt traegt jede neue Zahl ihre Herkunft mit, und
der lokale Zaehler eines Laufs wird gegen das Verzeichnis geprueft - zwei Wege
zur selben Zahl, die in diesem Projekt schon mehrfach auseinandergelaufen sind.

Versuchsstand 166 unveraendert, Suchbudget 36 von 100. 1563 Tests gruen.

## Siebzig. Der letzte offene Weg war keiner

Seit Befund 61 heisst die Diagnose: genau ein ungeloestes Problem, und es
heisst Deflated Sharpe. ``cli stand`` zerlegt das Gate in vier Groessen und
fragt fuer jede: *Wo muesste sie stehen - alles andere unveraendert?*

    Qualitaet je Trade         0.260 ->     0.294   (+13%)
    unabhaengige Trades      152.000 ->   202.334   (+33%)
    Schiefe                    3.473 ->     4.530   (+30%)
    Woelbung                  15.951   unerreichbar

Darunter stand wochenlang: *"Die Schiefe ist der einzige der vier Wege, den
noch nie jemand gemessen hat."* Qualitaet und Trade-Zahl sind durch die
Kopplung aus Befund 54 blockiert, die Woelbung kann nicht unter 1. Die Schiefe
war der letzte offene Weg - und niemand hat ihn angefasst, weil unklar war,
woran man dafuer dreht.

### Woran die Zerlegung scheitert

**"Alles andere unveraendert" geht bei diesen beiden nicht.** Fuer jede
Verteilung gilt

    Woelbung >= Schiefe^2 + 1

Das ist Cauchy-Schwarz auf ``Cov(X, X^2)`` einer standardisierten Groesse,
kein Erfahrungswert; Gleichheit erreichen nur Zweipunktverteilungen. Der Test
dazu behauptet die Ungleichung nicht, sondern rechnet sie an gezogenen
Stichproben nach - normal, lognormal, exponential, Pareto, gleichverteilt und
einer nachgebauten Trade-Verteilung.

Der ausgewiesene Zielpunkt verlangt bei Schiefe 4,53 eine Woelbung von
mindestens 21,0. Festgehalten wurden 15,7. **Es gibt keine Verteilung dieser
Form.** Die Zerlegung hat monatelang einen Punkt als Weg ausgewiesen, den es
nicht gibt.

### Was stattdessen gilt

Acht Kandidaten dieses Projekts tragen beide Formzahlen mit, aus fuenf
Regelfamilien - von der Rueckkehr zum Mittel bis zum Donchian-Ausbruch. Sie
liegen auf einer Geraden in ``Schiefe^2``:

    Woelbung = 1,194 * Schiefe^2 + 1,691       (r = 0,9963, n = 8)

Derselbe Weg, dreimal gerechnet:

    Woelbung festgehalten          Max DSR 1,0000 bei 4,84   ab 4,53  (+31 %)
    entlang der harten Schranke    Max DSR 1,0000 bei 7,34   ab 5,54  (+60 %)
    entlang der gemessenen Linie   Max DSR 0,8724 bei 6,52   nie erreicht

Selbst im mathematischen Optimum - einer Verteilung, die es praktisch nicht
gibt - verdoppelt sich die Anforderung von +30 % auf +60 %. Auf der Linie, auf
der alle bisherigen Kandidaten tatsaechlich lagen, **ist das Gate ueber die
Schiefe gar nicht erreichbar**: Ab Schiefe 6,52 waechst die Woelbung schneller
als der Vorteil, und der Wert faellt wieder.

### Der Fehler, der mir dabei selbst passiert ist

Der erste Anlauf suchte die noetige Schiefe mit einer Bisektion und meldete
"unerreichbar" - fuer *beide* gekoppelten Wege. Das war falsch: ``DSR(Schiefe)``
ist **nicht monoton**. Der Nenner lautet entlang der Schranke
``(1 - Schiefe*SR/2)^2 + Ueberschuss*SR^2/4`` und hat sein Minimum bei
``Schiefe = 2/SR``, hier 7,79. Die Bisektion hatte nur den Endpunkt geprueft,
dort war die Kurve laengst wieder gefallen, und sie schloss auf "geht nie".

Haette ich das nicht bemerkt, staende hier ein schaerferer Befund als der
richtige - die harte Schranke ist erreichbar, mit +60 %. Das Modul tastet die
Kurve deshalb ab und weist ihr Maximum aus; ein Test haelt die
Nicht-Monotonie fest.

### Was gebaut wurde

``research/formgrenze.py`` mit der Schranke, der gemessenen Linie und den drei
Wegen; ``cli form`` rechnet es auf echten Daten nach. ``suchbudget.Hebel``
traegt jetzt ein Feld ``unmoeglich_weil``, und der Schiefe-Hebel prueft seinen
eigenen Zielpunkt gegen die Schranke. In ``cli stand`` steht statt der Zahl
jetzt: *"braucht Woelbung >= 21.0, hier 15.7"*.

### Was das fuer den Stand heisst

Von den vier Wegen zum haertesten Gate sind jetzt drei geschlossen: Woelbung
(unter 1 gibt es nichts), Schiefe (dieser Befund), Trade-Zahl (Kopplung,
Befund 54). **Es bleibt genau einer: die Qualitaet je Trade, +13 %.** Und
alle Regler, die daran drehen, sind ausgemessen und geschlossen.

Das ist kein Fortschritt Richtung Zulassung, sondern das Gegenteil - eine
Moeglichkeit weniger. Aber es ist eine, die es nie gab, und sie stand als
letzte Hoffnung in der Uebersicht.

Versuchsstand 166 unveraendert, Suchbudget 36 von 100.

## Einundsiebzig. Das Wettrennen mit der eigenen Huerde

Nach Befund 70 ist von vier Wegen zum haertesten Gate einer uebrig - die
Qualitaet je Trade, +13 % -, und alle Regler daran sind ausgemessen. Bleibt:
weitersuchen. Nur hebt jeder Versuch die Latte mit, und wie sich das ausgeht,
war nie gerechnet.

### Zwei Groessen, dieselbe Formel

Beide wachsen ueber dieselbe Extremwertkonstante ``c(N)`` aus
Bailey/Lopez de Prado:

    Huerde       ~ A + 1/sqrt(n-1) * c(N)     was Zufall hergibt
    bester Fund  ~ Mittel + Streuung * c(N)   was Suchen hergibt

Damit ist es keine Frage des Fleisses, sondern ein Vergleich zweier
Vorfaktoren:

    **Die Suche gewinnt genau dann, wenn die Streuung echter Regelideen
    groesser ist als 1/sqrt(n-1) - die Streuung des reinen Zufalls.**

Bei 154 Trades sind das 0,0808. Das ist kein Zufall und kein Mangel: Genau
dafuer ist das Gate gebaut. Es neutralisiert die Zufallssuche exakt.

### Der Fehler, der zuerst herauskam

Der erste Anlauf schaetzte Mittel und Streuung aus den sechs Regelfamilien der
Bestenliste: Mittel 0,1685, Streuung 0,1019. Ergebnis: Schon zehn weitere
Versuche bringen 0,329 gegen eine Huerde von 0,293 - **Suchen lohnt sich
sofort.**

Die Schaetzung widerlegt sich selbst. Mit ihr waere der beste aus 166 Versuchen
bei **0,4440** zu erwarten gewesen; tatsaechlich sind es 0,2569. Die sechs sind
die Ueberlebenden aus 166 Versuchen, nicht sechs Ziehungen - ihre Streuung ist
die der Elite, ihr Mittel viel zu hoch. Haette ich das nicht gemerkt, staende
hier eine Aufforderung zum Weitersuchen, gestuetzt auf eine Zahl, die den
eigenen Verlauf nicht erklaert.

Ein Test haelt das jetzt fest: ``erklaert_den_verlauf`` verwirft jede
Schaetzung, die den bisherigen Bestwert nicht hervorbringt.

### Was stattdessen gilt

Kalibriert am eigenen Verlauf - welche Streuung muss es gewesen sein, damit 166
Versuche genau 0,2569 hervorbringen?

    weitere    Stand    Huerde   erwartet   Abstand
         0      166    0.2920     0.2569   -0.0351
        64      230    0.2995     0.2671   -0.0324
       834     1000    0.3310     0.3093   -0.0217
      9834    10000    0.3750     0.3668   -0.0081

**Die Suche gewinnt - bei rund 56.000 Versuchen.** Das Suchbudget bricht bei
230 ab; bis dahin schliesst sich der Abstand von 0,0351 auf 0,0324. In 64
weiteren Versuchen also 0,0027.

Die Ideenstreuung liegt mit 0,0950 nur 18 % ueber dem Zufall, und weil beide
mit ``sqrt(ln N)`` wachsen, dauert ein Vorsprung von 18 % entsprechend lange.

### Wie stark das an der Annahme haengt

Das Mittel einer typischen neuen Regelidee ist eine Annahme, keine Messung.
Deshalb steht es als Schalter da:

      Mittel   Streuung  ueber Zufall  Suche holt auf
       -0.05     0.1135         +40%  2.739 Versuche
       -0.02     0.1024         +27%  9.377 Versuche
       +0.00     0.0950         +18%  55.891 Versuche
       +0.02     0.0876          +8%  jenseits von 1e+09
       +0.05     0.0765          -5%  nie

Ein **niedrigeres** Mittel ist die guenstigere Annahme - es verlangt eine
groessere Streuung, um denselben Bestwert zu erklaeren. Selbst im guenstigsten
gerechneten Fall braeuchte es 2.739 Versuche.

Auch hier war die erste Fassung zu scharf: Sie schrieb bei +0,02 "nie", obwohl
die Streuung dort ueber dem Zufall liegt - die Suche kommt an, nur spaeter als
bis 10^9 gerechnet. "Jenseits der gerechneten Grenze" ist etwas anderes als
"nie", und ein eigener Test haelt den Unterschied fest.

### Was daraus folgt

**Mehr Versuche sind der schwache Hebel.** Der Gewinn ist logarithmisch, der
Preis linear. Was zaehlt, ist die Guete der Ideen, nicht ihre Zahl - ein
besserer Ausgangspunkt wirkt sofort, mehr Ziehungen wirken mit ``sqrt(ln N)``.

Das Suchbudget aus dem Plan ist damit zum ersten Mal quantitativ begruendet:
Es ist nicht zu knapp bemessen, sondern genau die Groessenordnung, in der
Suchen ueberhaupt noch etwas aendert.

### Was das Modell nicht kann

Es setzt **unabhaengige Ziehungen** voraus. Die meisten Versuche dieses
Projekts waren Reglerscans - Varianten des Bestands, die in derselben
Nachbarschaft nachsehen. Der echte Fortschritt ist also langsamer als hier
gerechnet, nicht schneller. Und kalibriert wird an genau **einem** Punkt; mehr
gibt es nicht.

Versuchsstand 166 unveraendert, Suchbudget 36 von 100. 1603 Tests gruen.

## Zweiundsiebzig. Wer Ideenquellen misst, misst zuerst sein eigenes Rauschen

Befund 71 hat den einzigen verbliebenen Hebel benannt: **die Guete der Ideen,
nicht ihre Zahl.** Damit wurde eine Frage stellbar, die dieses Projekt nie
gestellt hat - nicht "war dieser Vorschlag gut", sondern: **Taugt die Quelle?**

Und es gibt Daten dazu. Von 45 Bestenlisten-Eintraegen tragen fuenf ihren
Sharpe je Trade, und alle fuenf stammen aus derselben Herkunft: den
Analyst-Vorschlaegen aus Befund 53.

### Die Zwischenfolgerung, die falsch war

Ihre Streuung liegt bei **0,1031**, die Nullstreuung bei 154 Trades bei
**0,0808**. Also 27 % breiter als der Zufall - nach Befund 71 genau das
Kriterium, das eine Quelle erfuellen muss. Der naheliegende Schluss: Der
Analyst taugt, und 15 weitere Vorschlaege wuerden es absichern.

Der Schluss ist falsch, und zwar aus einem Grund, den man sofort sieht, wenn
man hinschaut. **Der Sharpe je Trade ist selbst geschaetzt**, mit einer
Varianz von rund ``1/(n-1)`` je Kandidat:

    Neues Hoch im Takt              123 Trades -> Rauschen 0,0905
    Ausbruch mit Beteiligung         68 Trades -> Rauschen 0,1222
    Donchian-Ausbruch                89 Trades -> Rauschen 0,1066
    Rueckkehr vom unteren Band      118 Trades -> Rauschen 0,0925
    Rueckschlag im Aufwaertstrend     8 Trades -> Rauschen 0,3780

Wer die Streuung ueber Kandidaten misst, misst beides auf einmal:

    beobachtet^2 = Ideenstreuung^2 + Messrauschen^2

Erwartetes Messrauschen ueber die fuenf: **0,1928**. Beobachtet: **0,1031**.
Die beobachtete Streuung liegt damit **unter** dem Rauschen - **es ist keine
Ideenstreuung nachweisbar.** Die fuenf Vorschlaege sind vollstaendig damit
vertraeglich, dass sie alle gleich gut sind und der Unterschied zwischen ihnen
reine Messungenauigkeit ist.

Auch ohne den 8-Trade-Fall bleibt es dabei: 0,0899 gegen 0,1037.

Das heisst **nicht**, dass der Analyst nichts taugt. Es heisst, dass fuenf
Punkte es nicht zeigen koennen - dieselbe Unterscheidung, die der
Vorteilsscan und ``haelften`` schon fuer Mittelwerte machen, jetzt fuer
Streuungen. Der 90-Prozent-Bereich reicht von 0,0670 bis 0,2480 und enthaelt
die Nullstreuung. Es braeuchte rund **18 Belege statt fuenf**.

### Der Versuch, der nichts beweisen konnte

"Rueckschlag im Aufwaertstrend" hat **8 Trades**. Sein Sharpe je Trade traegt
ein Rauschen von 0,378 - das Siebenfache des Abstands, um den es beim Gate
geht. Unter 30 Trades ueberspringt ``gate_deflated_sharpe`` die Korrektur:
Der Kandidat kann weder bestehen noch durchfallen. **Der Versuchszaehler ging
trotzdem hoch.**

Er hat die Huerde fuer jeden anderen Kandidaten gehoben, ohne selbst je eine
Chance gehabt zu haben. Gezaehlt gehoert er trotzdem - **am Zaehler wird nicht
gedreht.** Er ist die Kernabsicherung gegen Selbstbetrug, und wer anfaengt,
Versuche nachtraeglich nicht zu zaehlen, oeffnet genau die Tuer, die der
Zaehler zuhalten soll. Was gebaut wurde, ist die Auskunft, nicht der Eingriff.

### Was das fuer Befund 71 heisst

Dort wurde die Ideenstreuung aus dem beobachteten Bestwert kalibriert: 0,0950.
Auch darin steckt das Messrauschen. Zerlegt:

    beobachtet   0,0950
    Rauschen     0,0808    72 % der Varianz
    Ideen        0,0499

Das widerspricht Befund 71 nicht - die beobachtete Streuung liegt immer ueber
dem Rauschen, solange ueberhaupt eine Ideenstreuung da ist, und der dortige
Schluss "die Suche holt sehr spaet auf" bleibt. Aber die Zahl, die zaehlt, wenn
man fragt *"wie gut ist der wahre beste Fund"*, ist 0,0499 und nicht 0,0950.
**Knapp drei Viertel dessen, was wie ein Vorsprung der Suche aussah, ist
Messrauschen.**

### Was gebaut wurde

``research/aussagekraft.py`` mit ``messrauschen``, ``Beleg``, ``Ideenquelle``
und der Zerlegung; ``cli quelle`` liest die Herkuenfte aus Bestenliste und
Versuchsverzeichnis. Das Chi-Quadrat-Quantil kommt ohne ``scipy`` aus (Wilson-
Hilferty), und ein Test misst die Genauigkeit gegen Tabellenwerte statt sie
anzunehmen.

Die Herkunft trennt nach **Datei**, nicht nach Quelle - ``vorschlaege.json``
und ``sieger.json`` kommen beide vom Analysten. Beide Sichten stehen deshalb
nebeneinander; wer sie zusammenlegt, trifft eine Annahme, und die gehoert
sichtbar dazu.

### Was daraus folgt

Die Frage "welche Ideenquelle taugt" ist mit den vorhandenen Daten **nicht
beantwortbar**, und sie war es nie - man haette es nur nachrechnen muessen.
Sie zu beantworten kostet rund 13 weitere Vorschlaege. Das Suchbudget hat noch
64. Es waere die erste Ausgabe, die Befund 71 rechtfertigt: nicht breiter
suchen, sondern herausfinden, ob eine Quelle ueberhaupt besser als Zufall ist.

Ob das die Versuche wert ist, ist eine Entscheidung und keine Rechnung.

Versuchsstand 166 unveraendert, Suchbudget 36 von 100. 1622 Tests gruen.

## Dreiundsiebzig. Verbund verschiedener Regeln - der groesste Sprung, und er reicht nicht

Sechs Laeufe in Folge waren Auswertung. Dieser misst wieder.

Nach Befund 70 fuehrt genau ein Weg zum haertesten Gate: mehr **Guete**, also
``SR/Trade * sqrt(n_eff)``. Alle Regler daran sind ausgemessen, und Befund 54
hat die Kopplung gezeigt - wer denselben Kandidaten oefter handeln laesst,
verliert an Qualitaet, was er an Menge gewinnt.

Aber es gibt Kandidaten mit **hoeherer** Qualitaet je Trade, die nur zu selten
handeln:

    Spitzenkandidat              0,2591 je Trade   154 Trades   Guete 3,216
    Trend-Beteiligung 200 Tage   0,3185 je Trade    53 Trades   Guete 2,318
    Donchian-Ausbruch 55/20      0,3074 je Trade    58 Trades   Guete 2,341

19 bis 23 % ueber dem Spitzenkandidaten - mehr als die noetigen 13 %. Was
fehlt, ist Menge. Zwei verschiedene Regeln zusammen zu handeln ist nicht
dieselbe Kopplung: Die Trades kaemen aus verschiedenen Regeln, nicht aus einer
haeufiger ausgeloesten.

### Der Fehler, der im ersten Anlauf herauskam

Die erste Probe legte nur die Trades zusammen und liess die **Fensterbloecke**
weg. Ergebnis: 207 Trades, keine Kuerzung, Guete **3,970** gegen die noetigen
3,616. Das Gate waere bestanden gewesen.

Das ist exakt das Loch aus Befund 27, nur eine Regel weiter. Dort machte
dieselbe Regel mit drei Perioden aus 154 Trades 481 und aus DSR 0,802 einen von
0,999 - dreimal dasselbe Signal, dreimal gezaehlt. Hier: zwei korrelierte
Ertragsstroeme addiert, ohne die Korrelation zu messen.

Mit Bloecken, so wie das Gate rechnet, bleiben von 207 rohen Trades **149
unabhaengige** - 28 % gekuerzt.

### Was tatsaechlich uebrig bleibt

    Spitze allein                      Guete 3,216   DSR 0,7964
    + Trend-Beteiligung 200 Tage       Guete 3,368   DSR 0,8602
    + Donchian-Ausbruch 55/20          Guete 2,645   DSR 0,4490

**Der erste Verbund ist der groesste Sprung, den in diesem Projekt je etwas
gebracht hat.** Die ganze Reglerlandschaft aus 23 Messpunkten lag zwischen
0,42 und 0,86, und jeder Regler bewegte den Wert um Hundertstel. Hier sind es
0,064 auf einmal.

Er reicht trotzdem nicht. Noetig sind 0,95; es fehlen 0,253 an Guete.

### Und er hilft nicht von selbst

Der zweite Fall ist der lehrreichere. Beide Partner haben praktisch dieselbe
Einzelguete - 2,318 und 2,341. Der eine hebt den Verbund auf 0,8602, der andere
drueckt ihn auf 0,4490. Die Fensterkorrelation zum Spitzenkandidaten ist in
beiden Faellen aehnlich (0,555 und 0,534); den Unterschied macht die
Blockkuerzung: 207 -> 149 gegen 212 -> 106.

**Es entscheidet nicht die Qualitaet des Partners, sondern die Unabhaengigkeit
seiner Ertraege.** Das ist eine andere Suchrichtung als alles bisherige: Nicht
"welche Regel ist besser", sondern "welche Regel ist anders".

### Was das gekostet hat

Drei Verbunde gerechnet, den besten hervorgehoben - das ist eine Auswahl ueber
drei Hypothesen, und sie gehoert gezaehlt. **Versuchsstand 166 -> 169**, und es
sind die ersten drei Eintraege mit Einzelnachweis im Verzeichnis aus Befund 69.
Der Verbund verliert dadurch selbst etwas: Die noetige Guete steigt von 3,616
auf 3,621.

``cli verbund`` zaehlt kuenftig von selbst mit; ``--nicht-zaehlen`` gibt es,
aber dann ist das Ergebnis auch keine Grundlage fuer eine Auswahl.

### Was nicht geprueft ist

**Die uebrigen zehn Gates.** Zwei Regeln parallel teilen das Kapital; auf den
Deflated Sharpe wirkt das nicht (Befund 30), auf Rendite und Rueckgang sehr
wohl. Ein Verbund, der den DSR bestuende, koennte an der Messlatte oder der
Rueckgangsgrenze scheitern - und beide sind schon heute offen.

Die Richtung ist damit **nicht** geschlossen, sondern zum ersten Mal seit
Wochen wieder offen. Sie verlangt aber etwas, das dieses Projekt bisher nicht
gesucht hat: Regeln, die **anders** sind, nicht Regeln, die besser sind.

Versuchsstand 169, Suchbudget 39 von 100. 1637 Tests gruen.

### Nachtrag: Der Zaehler lag ungesichert

Beim Buchen der drei Versuche fiel auf, dass ``state/`` vollstaendig in
``.gitignore`` steht. **Der Versuchszaehler wurde nie versioniert.**

Der Container wird nach Inaktivitaet abgeraeumt. Ein Neustart haette
``state/trials.json`` verschwinden lassen - und eine **fehlende** Datei ist
laut Befund 69 der erste Lauf, also 0. Exakt der Reset, den jener Befund
verhindern sollte, nur ueber einen anderen Weg: nicht durch eine kaputte
Datei, sondern durch gar keine.

Die Regel dort unterscheidet zu Recht zwischen "fehlt" und "kaputt". Nur war
"fehlt" hier nicht der erste Lauf, sondern Datenverlust - und das war von
aussen nicht zu unterscheiden. Deshalb wird die Datei jetzt mitversioniert
(``state/*`` statt ``state/``, mit ``!state/trials.json``); die Bestenliste
und die Trade-Mitschnitte bleiben draussen, denn die sind Ausgaben und keine
Abmachung.

## Vierundsiebzig. Die Partnerkarte - und ein Merkmal, nach dem falsch ausgewaehlt wurde

Befund 73 hat den Verbund geoeffnet: DSR von 0,796 auf 0,860, es fehlen 0,26 an
Guete. Der naechste Schritt waere, weitere Partner zu messen - und jeder kostet
einen Versuch. Diese Karte rechnet vorher aus, welcher ueberhaupt reichen
koennte.

### Was dabei herauskam

    Noetiges SR/Trade des Partners fuer Guete 3,629 (bei 169 Versuchen)

    Trades       u=0,50    u=0,72    u=0,85    u=1,00
    ------------------------------------------------
    50           0,6679    0,4236    0,3263    0,2386
    100          0,4189    0,2826    0,2283    0,1793
    154          0,3257    0,2283    0,1894    0,1544
    250          0,2530    0,1842    0,1568    0,1321
    400          0,2022    0,1519    0,1319    0,1138

Bei 53 Trades und dem gemessenen Unabhaengigkeitsgrad von 0,72 haette der
Partner **0,4236** gebraucht. Er hatte 0,3185 - eine der besten Zahlen des
Projekts, und trotzdem weit weg.

Bei 154 Trades haetten **0,2283** genuegt, also **weniger als der
Spitzenkandidat selbst hat**. Die Wende liegt bei 120 Trades.

### Der Satz aus Befund 73, der falsch war

Dort stand der Gedanke, der zur Auswahl gefuehrt hat:

    *"Es gibt Kandidaten mit hoeherer Qualitaet je Trade, die nur zu selten
    handeln. Was fehlt, ist Menge."*

Der erste Teil stimmt, der Schluss daraus nicht. Ich habe die **hochwertigsten
seltenen** Kandidaten gewaehlt - und die Karte zeigt, dass Seltenheit das
bindende Merkmal ist, nicht Qualitaet. Ein Partner muss nicht besser sein als
der Bestand. Er muss **genug handeln und anders sein**.

Die Zahlen dafuer standen die ganze Zeit in derselben Tabelle. Ich habe die
falsche Spalte gelesen.

### Was das fuer die Suche heisst

Alle fuenf bekannten Anwaerter mit belegtem Sharpe je Trade, gegen ihre eigene
Anforderung bei u = 0,72:

    Neues Hoch im Takt              123   0,2137   noetig 0,2543   fehlt +0,0406
    Rueckkehr vom unteren Band      118   0,0483   noetig 0,2596   fehlt +0,2112
    Donchian-Ausbruch 50/25          89   0,2136   noetig 0,3007   fehlt +0,0871
    Ausbruch mit Beteiligung         68   0,2482   noetig 0,3503   fehlt +0,1021
    Rueckschlag im Aufwaertstrend     8   0,0300   noetig 1,8163   fehlt +1,7863

**Alle handeln zu selten.** Der naechste ist 'Neues Hoch im Takt' mit 123
Trades und nur 0,0406 Abstand - und er wurde in Befund 73 nicht probiert, weil
seine Qualitaet unter dem Bestand liegt. Bei einem Unabhaengigkeitsgrad von
0,85 statt 0,72 wuerde er reichen.

### Und warum das nicht zu messen war

'Neues Hoch im Takt' **ist nicht mehr rechenbar.** Er stammt aus
``sieger.json``, einer Vorschlagsdatei des Analysten, die nie versioniert
wurde. Die Bestenliste haelt ``genome_id``, Name und Kennzahlen fest - aber
nicht die Regeln.

Ein Kandidat, der einmal gemessen wurde, war danach verloren. Das faellt erst
auf, wenn man ihn wieder braucht, und genau jetzt ist der Fall eingetreten:
Der aussichtsreichste Partner der Karte existiert nur noch als Zahl.

``Entry`` traegt jetzt ein Feld ``genom``. Die 45 vorhandenen Eintraege bleiben
ohne Regeln - nachtraeglich erfundene waeren schlimmer als eine sichtbare
Luecke, dieselbe Regel wie beim ``grundstock`` in Befund 69.

### Wonach jetzt zu suchen waere

Nicht nach einer besseren Regel, sondern nach einer mit **mindestens 120
Trades und moeglichst wenig Fensterkorrelation** zum Bestand. Das ist eine
andere Suche als alles bisherige - und mit ``cli partner`` laesst sich vor
jedem Versuch pruefen, ob ein Anwaerter ueberhaupt in Frage kommt.

Die Naeherung ist dabei die freundliche Richtung: An den beiden gemessenen
Faellen liegt sie einmal 0,6 % daneben und einmal 6 % zu hoch. Wo sich die
Verteilungen unterscheiden, waechst die Streuung der Mischung - die Karte
nennt also eher zu niedrige Anforderungen.

Versuchsstand 169 unveraendert, Suchbudget 39 von 100. 1654 Tests gruen.

## Fuenfundsiebzig. Der Katalog ist als Partnerquelle erschoepft

Befund 74 hat die Anforderung an einen Verbund-Partner beziffert: mindestens
rund 120 Trades, moeglichst wenig Fensterkorrelation zum Bestand. Dieser Lauf
haelt den ganzen Katalog dagegen.

Vermessen wurden alle Genome der Tageskerzen-Generationen (5, 8, 9, 10) -
20 Laeufe, 14 verschiedene Regeln, weil mehrere Generationen dasselbe Genom
unter anderem Namen fuehren.

    Anwaerter                        Trades       SR   noetig    fehlt     rho
    ---------------------------------------------------------------------------
    Luecke wird geschlossen             258  -0,0368   0,1818  +0,2186   -0,597
    VWAP-Rueckkehr short                185  -0,1113   0,2099  +0,3212   -0,536
    Trend-Beteiligung 50 Tage           156   0,1894   0,2269  +0,0375   +0,813
    Abfolge ohne Strukturbruch          124  -0,0469   0,2532  +0,3002   +0,456
    Trend-Beteiligung 100 Tage          109   0,2231   0,2702  +0,0471   +0,787
    Trend beide Richtungen              106   0,2160   0,2741  +0,0581   +0,473
    Momentum-Beteiligung 90 Tage        101   0,1649   0,2810  +0,1162   +0,712
    Donchian-Ausbruch 55/20              58   0,3074   0,3855  +0,0781   +0,534
    Vola-Ziel, langes Messfenster        53   0,3185   0,4080  +0,0895   +0,555
    ... und fuenf weitere, alle weiter weg

**Tauglich: 0 von 14.**

### Warum, und das ist der eigentliche Befund

Die Anwaerter, die **genug handeln**, sind genau die mit negativem oder
schwachem Sharpe. Die mit **guter Qualitaet** handeln zu selten. Und die
beiden mit der besten Unabhaengigkeit - 'Luecke wird geschlossen' mit
rho = -0,597 und 258 Trades, 'VWAP-Rueckkehr short' mit -0,536 und 185 - haben
beide einen **negativen** Sharpe je Trade. Sie haetten genau die Eigenschaft,
auf die es ankommt, und nichts, was sich damit verbinden liesse.

Ueber die 14 Genome gemessen: **r = -0,533 zwischen Trade-Zahl und Qualitaet
je Trade** (t = -2,18).

Befund 54 hatte diese Kopplung an **einem** Kandidaten gemessen, durch
Verstellen seiner Regler. Sie ist damit keine Eigenschaft jener Regel, sondern
**des Vorrats**. Das erklaert die leere Partnerkarte vollstaendig: Sie verlangt
Menge und Qualitaet zugleich, und der Katalog liefert immer nur eines.

Mit t = -2,18 liegt der Wert knapp ueber der Schwelle, ab der dieses Projekt
von einem Befund spricht. Knapp heisst knapp - bei 14 Punkten haette ein
einzelnes anderes Genom die Auffaelligkeit gekippt, wenn auch nicht das
Vorzeichen.

### Der Scheinbefund, der dabei fast entstanden waere

Der erste Anlauf haengte die Kopplungsrechnung an ``cli partner``, und der
liest nur die fuenf Bestenlisten-Eintraege. Dort kommt **r = +0,359** heraus -
das Gegenteil - bei t = +0,67. Das Urteil zog trotzdem denselben Schluss:
*"Sie ist damit keine Eigenschaft jener Regel, sondern des Vorrats."*

Eine Korrelation ohne Deckung darf nicht klingen wie eine mit. ``urteil()``
liefert unterhalb von |t| = 2 jetzt gar keine Schlussfolgerung mehr, sondern
die Auskunft, dass diese Punkte nichts sagen. Ein Test haelt es fest.

### Was das kostet und was nicht

**Keinen Versuch.** Gemessen wurden Trade-Zahl, Qualitaet und Korrelation -
keine Gates, kein Deflated Sharpe, keine Auswahl. Es gibt keinen ausgewaehlten
Kandidaten, fuer den zu korrigieren waere.

Das gilt aber nur, solange keiner dieser Anwaerter tatsaechlich als Verbund
geprueft wird. Wer das tut, hat eine Auswahl ueber 14 Hypothesen getroffen und
muss sie mitzaehlen. Der Hinweis steht im Befehl.

### Wonach jetzt zu suchen waere

Nach einer Regel, die es im Katalog nicht gibt: **mindestens 120 Trades,
positiver Sharpe ueber 0,23, und moeglichst unabhaengig vom Trendfolge-Signal.**
Die Kopplung sagt, dass so etwas im vorhandenen Vorrat nicht vorkommt - sie
sagt nicht, dass es das nicht gibt.

Die einzige gebaute Quelle fuer neue Regeln ist ``research/analyst.py``. Nach
Befund 72 laesst sich mit fuenf Vorschlaegen nicht beurteilen, ob sie taugt;
noetig waeren rund 18. Das Suchbudget hat 61 Versuche uebrig.

Versuchsstand 169 unveraendert, Suchbudget 39 von 100. 1659 Tests gruen.

## Sechsundsiebzig. Der Analyst hat auf das falsche Ziel optimiert

Befund 75 endet mit einer Spezifikation: Gesucht wird eine Regel mit
**mindestens 120 Trades, Sharpe je Trade ueber 0,23, unabhaengig vom
Trendfolge-Signal**. Der Katalog hat so etwas nicht. Die einzige gebaute
Quelle fuer neue Regeln ist ``research/analyst.py``.

Beim Nachsehen, was der Analyst eigentlich als Auftrag bekommt, kam heraus,
warum seine bisherigen Vorschlaege danebenlagen.

### Was im Auftrag stand - und was nicht

``build_prompt`` nennt die erlaubten Indikatoren, das Journal der
gescheiterten Versuche und fuenf Zulassungsschwellen:

    - mindestens 100 Out-of-Sample-Trades
    - Sharpe mindestens ...
    - Drawdown hoechstens ...
    - mindestens ... profitable Fenster
    - ueberlebt ...-fache Gebuehren

**Der Deflated Sharpe kommt darin nicht vor.** Das ist das Gate, an dem seit
Befund 61 alles haengt, und das einzige von elf, das noch wirklich ungeloest
ist. Der Analyst hat nie erfahren, dass es existiert - und auch nicht, dass
die Huerde mit jedem seiner eigenen Vorschlaege steigt.

Er zielt deshalb auf **100 Trades**, weil das die einzige Trade-Zahl im
Auftrag ist. Gebraucht werden 120, und darunter genuegt selbst ein sehr hoher
Sharpe je Trade nicht. Von fuenf belegten Analyst-Kandidaten haben vier
zwischen 68 und 123 Trades, keiner einen Sharpe je Trade ueber 0,25 - genau
das Profil, das der alte Auftrag verlangt und das fuer die eigentliche Luecke
wertlos ist.

Das ist derselbe Fehler wie meiner in Befund 73, eine Ebene hoeher: Nicht die
Auswahl war nach dem falschen Merkmal getroffen, sondern der **Auftrag**.

### Was jetzt dazukommt

``research/auftragslage.py`` baut aus den vorhandenen Messungen einen
Abschnitt, der vor dem eigentlichen Auftrag steht:

* die Groesse, an der das Gate haengt - Guete = Sharpe je Trade mal Wurzel aus
  den unabhaengigen Trades -, mit dem Stand des Bestands (3,215), dem noetigen
  Wert (3,629) und der Luecke (0,413);
* die drei Punkte, die ein brauchbarer Vorschlag erfuellen muss, mit Zahlen
  statt Adjektiven: mindestens 120 Trades, Sharpe je Trade ueber 0,26 bei
  dieser Zahl (bei 240 Trades genuegen 0,19), Fensterkorrelation unter 0,8;
* die Kopplung aus Befund 75 (r = -0,533) als Erklaerung, warum das schwer
  ist: Jede Regel im Vorrat erfuellt Punkt 1 **oder** Punkt 2, keine beide;
* der Preis eines Versuchs - 0,00013 mehr noetige Qualitaet je Trade, fuer
  alle folgenden, dauerhaft.

**Kein gelockertes Kriterium, sondern ein schaerferes.** Die Trade-Anforderung
steigt von 100 auf 120, und es kommt eine Bedingung dazu, die es vorher gar
nicht gab.

Nichts davon wird hier zweitgerechnet: Alle Zahlen kommen aus
``verbund.noetige_guete``, ``partnerkarte`` und ``suchbudget``. Wer die
Schwelle in ``gates.py`` aendert, aendert diesen Auftragstext mit; ein Test
haelt das fest.

### Die Zeile, die zuerst falsch war

Der erste Entwurf schrieb zu Punkt 2: *"Sharpe je Trade ueber 0,26. Das ist
weniger als der Bestand hat - Menge schlaegt hier Qualitaet."* Der Bestand hat
0,2591. An der Wende ist die Anforderung **per Definition gleich** der des
Bestands, nie darunter - der Satz war schlicht falsch.

Der Hebel ist trotzdem da, nur eine Stuetzstelle weiter: bei 240 Trades
genuegen 0,19. Der Text nennt jetzt beide Punkte, und ein Test verlangt, dass
die falsche Behauptung nicht wiederkommt.

### Was das nicht ist

Ein Vorschlag ist damit nicht besser, nur besser beauftragt. Ob der Analyst
etwas findet, das 120 Trades **und** Qualitaet **und** Unabhaengigkeit
mitbringt, ist offen - Befund 75 sagt nur, dass es im vorhandenen Vorrat nicht
vorkommt, nicht dass es das nicht gibt.

Und der Auftrag laesst sich ohne Sprachmodell nutzen: ``cli vorschlag
--auftrag`` gibt ihn aus, ``DateiClient`` liest eine von Hand geschriebene
Antwort. In diesem Container ist kein Modell verdrahtet.

Versuchsstand 169 unveraendert, Suchbudget 39 von 100. 1672 Tests gruen.

## Siebenundsiebzig. Vier Regeln gegen die Spezifikation - und das Nadeloehr

Befund 76 hat den Auftrag an den Analysten geschaerft. In diesem Container ist
kein Sprachmodell verdrahtet, aber ``DateiClient`` ist ausdruecklich dafuer
da, dass der Auftrag von Hand beantwortet wird. Also habe ich ihn beantwortet.

Vier Vorschlaege, jeder mit einer **anderen Ursache als Trend** und darauf
angelegt, oft auszuloesen:

* **Enge vor Bewegung** - Volatilitaetszyklus: Nach ruhigen Phasen folgen
  grosse Bewegungen.
* **Volumenschock mit Fortsetzung** - Informationsereignis: Ein Tag mit
  weit ueberdurchschnittlichem Volumen braucht mehrere Tage zur Einpreisung.
* **Rueckkehr zum Volumenschwerpunkt** - Preisfindung: Der Kurs kehrt zum
  volumengewichteten Durchschnitt zurueck.
* **Abgriff des Vortagestiefs** - Liquiditaet: Nach abgeraeumten Stopps ist
  die Gegenseite ausgeduennt.

### Was dabei herauskam

    Vorschlag                         Trades  SR/Trade    noetig      rho
    ----------------------------------------------------------------------
    Enge vor Bewegung                     18    0,3405    0,9047   +0,417
    Volumenschock mit Fortsetzung        114    0,1584    0,2652   +0,396
    Rueckkehr zum Volumenschwerpunkt      92   -0,1201    0,2967   +0,063
    Abgriff des Vortagestiefs            406   -0,1201    0,1514   +0,129

**Keiner taugt.** Aber das Muster ist deutlicher als bei jeder bisherigen
Messung - und es steht quer zu dem, was ich erwartet hatte.

### Die Unabhaengigkeit war nie das Problem

Alle vier liegen bei einer Fensterkorrelation zwischen **+0,06 und +0,42**,
weit unter der Schwelle von 0,8. Punkt 3 der Spezifikation - "ein anderes
Marktverhalten als Trendfolge" - ist **leicht** zu erfuellen. Wer nach einer
anderen Ursache baut, bekommt auch ein anderes Ertragsmuster.

Das Nadeloehr sind Punkt 1 und 2 **zusammen**. Die seltenste Regel hat die
beste Qualitaet (18 Trades, 0,3405), die haeufigste die schlechteste (406
Trades, -0,1201). Genau die Kopplung.

### Der Beleg ist staerker geworden

Befund 75 hat die Kopplung ueber den **Katalog** gemessen: r = -0,533 bei
n = 14. Das ist eine Auswahl - jemand hat diese Regeln einmal ausgesucht, und
die Korrelation koennte ein Artefakt davon sein.

Die vier hier wurden **eigens gegen die Spezifikation gebaut**, nicht
ausgesucht. Sie sind der unabhaengige Gegentest, und sie zeigen dasselbe:

    nur Katalog        n=14   r = -0,533   t = -2,18
    nur die vier neuen n= 4   r = -0,660   t = -1,24
    zusammen           n=18   r = -0,602   t = -3,02

Aus einem Befund am Rand ist damit ein deutlicher geworden. Die Kopplung ist
keine Eigenschaft der Auswahl, sondern der Sache.

### Was ich zuerst fuer einen Fehler hielt

Zwei voellig verschiedene Regeln zeigten in der Ausgabe denselben Sharpe je
Trade: -0,1201 und -0,1201. Bei 92 und 406 Trades ist das praktisch
unmoeglich, also habe ich nachgesehen, bevor ich irgendetwas berichtet habe.
Bei voller Genauigkeit sind es **-0,120133 und -0,120146** - verschiedene
Werte, und nur die Rundung auf vier Stellen taeuschte.

### Was das gekostet hat

**Vier Versuche, 169 -> 173.** Neue Genome zu messen ist ein Versuch, auch
ohne Gate-Aufruf: Der Deflated Sharpe korrigiert fuer die Zahl **getesteter
Hypothesen**, nicht fuer die Zahl der Gate-Aufrufe. Alle vier stehen mit
ihrem Sharpe je Trade im Verzeichnis; die Regeln selbst liegen in
``strategies/vorschlaege/gen11_partner.json`` und sind damit - anders als
'Neues Hoch im Takt' aus Befund 74 - wieder rechenbar.

Suchbudget 43 von 100.

### Wonach jetzt zu suchen waere

Die Spezifikation steht, und zwei ihrer drei Punkte sind einzeln leicht zu
treffen. Gebraucht wird eine Regel, die **oft ausloest und dabei Vorteil
behaelt** - und die Kopplung sagt, dass genau das der schwierige Teil ist,
inzwischen ueber 18 Punkte belegt.

Das ist kein Grund aufzuhoeren, aber ein Grund, die Erwartung zu senken: Von
18 gemessenen Regeln hat keine einzige beides. Wer weitersucht, sucht nach
einer Ausnahme von einem Muster, das mit jedem Datenpunkt klarer wird.

## Achtundsiebzig. Die Kopplung liegt nicht an den Kosten

Ueber 18 gemessene Regeln steht die Kopplung mit r = -0,602: Wer oefter
handelt, handelt schlechter. Sie erklaert die leere Partnerkarte und ist der
Grund, warum das haerteste Gate nicht faellt. **Warum sie gilt, war nie
untersucht.**

Dafuer gibt es eine mechanische Erklaerung, und sie klingt zwingend: Die
Gebuehr ist ein fester Betrag je Trade, aber die Streuung eines Trades waechst
mit seiner Haltedauer. Wer oefter handelt, haelt kuerzer, streut weniger - und
derselbe Betrag frisst einen groesseren Anteil.

Waere das die Ursache, haette es eine Folge: **Die Kopplung waere
verhandelbar.** Bessere Konditionen, Maker-Rebates, ein groesseres Konto -
alles wuerde helfen.

### Gemessen an zehn Regeln sehr verschiedener Taktung

    Regel                            Trades  SR/Trade  Halte-d  Kosten/Str
    -------------------------------------------------------------------
    Donchian-Ausbruch 55/20              58    0,3074     48,5      0,0013
    Trend-Beteiligung 200 Tage           53    0,3185     33,5      0,0023
    Bestand                             154    0,2591     14,1      0,0028
    Volumenschock mit Fortsetzung       114    0,1584      6,2      0,0051
    Rueckkehr zum Volumenschwerpunkt     92   -0,1201     12,1      0,0059
    Abgriff des Vortagestiefs           406   -0,1201      0,3      0,0170

    Trades <-> Kostenanteil     +0,831
    Kostenanteil <-> Qualitaet  -0,738

**Der Mechanismus ist da**, und zwar deutlich. Nur traegt er nichts. Rechnet
man die Gebuehr zurueck:

    netto    r = -0,673
    brutto   r = -0,663

**Zehn Tausendstel.** Die Hypothese ist widerlegt.

Der Grund steht in derselben Tabelle: Der Kostenanteil reicht von 0,0013 bis
0,0170 der Trade-Streuung, waehrend die Qualitaeten von +0,34 bis -0,12
spannen. Er ist zwei Groessenordnungen zu klein, um irgendetwas zu erklaeren.

### Was an der Rechnung unvollstaendig war

``net_pnl = gross_pnl - fees - funding``, und die **Slippage steckt im
Ausfuehrungspreis** - also schon in ``gross_pnl``, nicht in ``fees``. Was ich
zurueckgerechnet hatte, war die Gebuehr allein. Die wahren Handelskosten
liegen hoeher, und um wie viel, laesst sich aus den Trades nicht trennen.

Das ist mir beim Nachsehen aufgefallen, nachdem die erste Zahl schon dastand.
Also wurde die Frage andersherum gestellt, und das ist ihre ehrliche Form:
**Bei welchem Kostenfaktor wuerde die Kopplung kippen?**

    Faktor  1    r = -0,663    (die tatsaechliche Gebuehr, 0,04 %)
    Faktor  5    r = -0,618
    Faktor 10    r = -0,542
    Faktor 25    r = -0,144
    Faktor 50    r = +0,511

Der Kippunkt liegt bei **29-facher Gebuehr** - 1,2 % je Roundtrip. Das
verlangt kein Handelsplatz. Selbst wenn die Slippage die Kosten verdoppelte
oder verfuenffachte, bliebe die Kopplung stehen.

### Was daraus folgt

Die Kopplung ist eine Eigenschaft der **Signale**, nicht einer Reibung:
Haeufigere Ausloeser tragen tatsaechlich weniger Vorteil je Ausloesung. Keine
Konditionen, kein groesseres Konto, keine bessere Ausfuehrung aendert daran
etwas.

Das ist die unangenehmste Sorte Befund - er schliesst nicht eine Richtung,
sondern eine **Hoffnung**. Die Vorstellung, das Projekt scheitere an einer
Reibung, die sich wegoptimieren liesse, ist damit erledigt.

Fuer die Suche bleibt: Wer eine Regel sucht, die oft ausloest und dabei
Vorteil behaelt, sucht nach einer Ausnahme von einem Muster, das jetzt auch
ursaechlich eingegrenzt ist. Es gibt sie vielleicht - aber nicht dort, wo man
an Gebuehren dreht.

Versuchsstand 173 unveraendert, Suchbudget 43 von 100. 1682 Tests gruen.

## Neunundsiebzig. Die Kopplung haelt der Nullprobe stand - und ein Satz aus Befund 77 nicht

Vier Befunde stuetzen sich inzwischen auf dieselbe Zahl: r = -0,602 zwischen
Trade-Zahl und Qualitaet je Trade. Befund 78 hat ihre Ursache eingegrenzt
(nicht die Kosten). **Eine Alternativerklaerung war nie geprueft**, und sie
haette alle vier umgeworfen.

### Die Erklaerung, die zuerst zu widerlegen war

Der Sharpe je Trade ist selbst geschaetzt, mit einer Streuung von
``1/sqrt(n-1)``. Bei Trade-Zahlen von 18 bis 406 streuen die seltenen Regeln
**viermal so breit** wie die haeufigen:

    Enge vor Bewegung      18 Trades   SR 0,3405   Rauschen 0,2425   t = 1,40
    Bollinger short        36 Trades   SR 0,0576   Rauschen 0,1690   t = 0,34
    Donchian 55            58 Trades   SR 0,3074   Rauschen 0,1325   t = 2,32
    Bestand               154 Trades   SR 0,2591   Rauschen 0,0808   t = 3,20
    Abgriff               406 Trades   SR -0,1201  Rauschen 0,0497   t = -2,42

Bei so ungleichen Trade-Zahlen kann eine Korrelation entstehen, **ohne dass
irgendein Zusammenhang da waere** - allein weil die Punkte am linken Rand
weiter ausschlagen.

### Die Nullprobe

Dieselben 18 Trade-Zahlen, jede Regel mit wahrem Vorteil **null**, nur ihr
eigenes Messrauschen. 200.000 Durchlaeufe:

    Nullverteilung   Mittel  -0,000   Streuung  0,193
    5. bis 95. Perzentil     -0,317 bis +0,316
    beobachtet               -0,602
    Anteil der Null darunter  0,02 %

**Die Kopplung haelt.** Sie liegt mehr als drei Streuungen ausserhalb dessen,
was Rauschen hergibt. Bemerkenswert ist dabei die Breite der Nullverteilung:
Ein r von -0,3 waere **nicht** aussagekraeftig gewesen - und genau in dieser
Groessenordnung liegen viele Korrelationen, die man ohne Gegenprobe fuer
Befunde haelt.

### Der Satz aus Befund 77, der nicht haelt

Dort stand als Beleg fuer die Kopplung: *"die seltenste Regel hat die beste
Qualitaet (18 Trades, 0,3405), die haeufigste die schlechteste"*.

Die zweite Haelfte traegt (t = -2,42). Die erste nicht: Bei 18 Trades betraegt
das Messrauschen 0,2425, der Wert liegt **1,4 Standardfehler** ueber null. Er
belegt gar nichts - und ich habe ihn als Beleg verwendet.

Die Kopplung traegt als **Muster ueber 18 Punkte**, nicht ueber einzelne
davon. Das ist ein Unterschied, den Befund 72 fuer Ideenquellen schon
festgehalten hat, und ich bin ihm hier trotzdem aufgesessen.

### Was die Kopplung jetzt vorhersagen kann

Wenn sie echt ist, ist sie eine Vorhersage. Die Gerade durch die 18 Punkte:

    SR je Trade = -0,000957 * Trades + 0,2197      Reststreuung 0,1225

    bei 120 Trades erwartet   +0,105
    bei 154 Trades erwartet   +0,072
    bei 406 Trades erwartet   -0,169

Die Spezifikation aus Befund 76 verlangt bei 120 Trades **0,265**. Das liegt
1,31 Reststreuungen ueber der Erwartung - **9,5 % der Regeln wuerden es
erreichen.**

Bei 57 verbleibenden Versuchen waeren das 5,4 erwartete Treffer. Das klingt
gut, und es ist zu gut.

### Der Winner's Curse, beziffert

Die Reststreuung von 0,1225 enthaelt das Messrauschen mit. Bei 120 Trades sind
das 0,0917 - **56 % der Restvarianz**. Die echte Streuung der Regelguete
betraegt nur 0,0813.

    gemessen   z = 1,31   ->  9,5 %   ->  5,4 Treffer in 57 Versuchen
    echt       z = 1,97   ->  2,4 %   ->  1,4 Treffer in 57 Versuchen

Eine Regel, die die Anforderung **gemessen** erfuellt, hat sie zu mehr als der
Haelfte zufaellig erfuellt. Genau dafuer ist der Deflated Sharpe da, und genau
deshalb wuerde ein solcher Treffer im Verbund oft nicht halten.

### Was daraus folgt

Die Suche ist nicht aussichtslos, aber die Erwartung ist zu beziffern: **rund
1,4 echte Treffer im verbleibenden Budget**, und jeder gemessene Treffer ist
zu drei Vierteln Rauschen, bis er sich im Verbund bestaetigt.

Das ist kein Grund aufzuhoeren. Es ist ein Grund, jeden Treffer als Verdacht
zu behandeln und nicht als Fund - und die 2,4 % stehen jetzt als Zahl da,
statt als Gefuehl.

Versuchsstand 173 unveraendert, Suchbudget 43 von 100. 1687 Tests gruen.

## Achtzig. Die Kopplung deckelt die Guete - und sagt, welcher Weg der bessere ist

Befund 79 hat die Kopplung als Vorhersage nutzbar gemacht:

    SR je Trade = -0,000957 * Trades + 0,2197      Reststreuung 0,1225

Eine Folge daraus war noch nicht gezogen, und sie ist die haerteste bisher.
Die Groesse, an der das Gate haengt, ist nicht der Sharpe je Trade, sondern
die **Guete** - und die laesst sich entlang der Geraden ausrechnen:

    Guete(n) = (a + b*n) * sqrt(n)

### Die ernuechterndste Zahl des Projekts

    20 Trades  -> Guete 0,897
    50 Trades  -> Guete 1,215
    77 Trades  -> Guete 1,281     <- Maximum
   100 Trades  -> Guete 1,240
   154 Trades  -> Guete 0,897
   406 Trades  -> Guete -3,402

**Das Maximum liegt bei 1,281. Das Gate verlangt 3,629.**

Die Kurve hat ein Maximum, weil mehr Trades nur helfen, solange der
Qualitaetsverlust langsamer waechst als die Wurzel. Ab 77 Trades ueberholt
der Verlust den Gewinn.

Eine **durchschnittliche** Regel erreicht das Gate damit nicht annaehernd -
sie liegt um den Faktor 2,8 daneben. Jeder Kandidat, der es schaffen soll,
muss ein Ausreisser sein. Das war vorher eine Vermutung; jetzt steht die Zahl
daneben.

### Der Bestand ist bereits einer

Bei 154 Trades sagt die Gerade einen Sharpe je Trade von 0,0723 voraus. Der
Bestand hat **0,2591** - das sind 1,52 Reststreuungen darueber. Er ist kein
Durchschnitt, sondern der groesste Ausreisser der Sammlung.

Noetig waeren 1,80. Es fehlen 0,28 Reststreuungen, und das ist der ganze
Abstand zum Gate - in einer Zahl, die nichts mit Reglern zu tun hat.

### Wo ein Einzelkandidat die beste Chance hat

    Trades   z gemessen   Anteil   z echt   Anteil echt
    ----------------------------------------------------
       100      1,95      2,56 %    3,41     0,03 %
       153      1,80      3,62 %    2,40     0,83 %
       197      1,82      3,44 %    2,29     1,12 %
       400      2,81      0,25 %    3,08     0,10 %

Gemessen liegt das Optimum bei **153 Trades** - und der Bestand hat 154. Er
sitzt nicht zufaellig dort, wo er sitzt.

Rechnet man das Messrauschen heraus, verschiebt sich das Optimum auf **197**:
Dort ist weniger von der Reststreuung Rauschen, ein Treffer also haeufiger
echt. Das ist ein feiner Unterschied mit praktischer Folge - wer nach
Einzelkandidaten sucht, sollte etwas haeufiger handelnde Regeln bauen als die
gemessene Bestenliste nahelegt.

### Welcher Weg der bessere ist, beziffert

    Einzelkandidat, optimal getaktet   1,12 % je Versuch   0,6 Treffer in 57
    Verbund-Partner bei 120 Trades     2,40 % je Versuch   1,4 Treffer in 57

**Der Verbund ist um Faktor 2,2 wirksamer.** Das ist die erste Zahl, die die
beiden Wege gegeneinander stellt - bisher war der Verbund eine Richtung, die
sich gut anfuehlte.

Der Grund ist einfach: Ein Verbund muss die Guete nicht allein tragen. Der
Bestand bringt 3,215 mit, der Partner muss nur den Rest liefern.

### Was daraus folgt

Das verbleibende Suchbudget von 57 Versuchen gehoert in **Verbund-Partner**,
nicht in Einzelkandidaten. Erwartungswert: 1,4 echte Treffer. Das ist wenig,
aber es ist mehr als null - und es ist doppelt so viel wie der andere Weg.

Und die Erwartung bleibt, was sie ist: Eine durchschnittliche Regel schafft
Guete 1,28 gegen noetige 3,63. Wer weitersucht, sucht nach einem Ausreisser,
und die Zahl daneben ist 2,4 %.

Versuchsstand 173 unveraendert, Suchbudget 43 von 100. 1691 Tests gruen.

## Einundachtzig. Zwei Korrekturen an meinen eigenen letzten Befunden

Befund 80 hat entschieden, wohin das Restbudget gehoert: in Verbund-Partner,
mit 2,40 % echter Trefferquote je Versuch und 1,4 erwarteten Treffern. Beim
Nachrechnen, auf welche **Trade-Zahl** ein Vorschlag zielen soll, sind an
dieser Aussage zwei Dinge kaputtgegangen.

### Erstens: die falsche Trade-Zahl

Die 2,40 % waren bei **120 Trades** gerechnet. Das ist die *Wende* aus der
Partnerkarte - die Zahl, ab der ein Partner mit der Qualitaet des Bestands
genuegt. Ich hatte sie fuer das Optimum gehalten. Sie ist eine Untergrenze.

Die Trefferquote als Funktion der Trade-Zahl:

    Trades   noetig   erwartet   p gemessen   p echt
    ------------------------------------------------
       100   0,2826    0,1240        9,77 %   1,18 %
       120   0,2574    0,1049       10,65 %   3,02 %
       154   0,2283    0,0723       10,15 %   4,51 %
       200   0,2028    0,0283        7,71 %   4,03 %
       300   0,1708   -0,0674        2,59 %   1,37 %

Das Optimum liegt bei rund **164 Trades**, nicht bei 120. Zwei gegenlaeufige
Kurven treffen sich dort: Die Anforderung faellt mit der Wurzel, die Erwartung
faellt linear - dazwischen ist der Abstand am kleinsten.

### Zweitens, und schwerer: die Zahl selbst traegt nicht

Die ganze Rechnung haengt an der Reststreuung von 0,1225. Die ist aus **18
Punkten** geschaetzt, bei zwei Parametern fuer die Gerade - 16
Freiheitsgrade. Ihr 90-Prozent-Bereich reicht von **0,096 bis 0,174**.

Was das mit der Trefferquote bei 154 Trades macht:

    Reststreuung 0,096   ->   0,11 %
    Reststreuung 0,123   ->   4,51 %
    Reststreuung 0,174   ->  15,52 %

**Ein Faktor 140.** Die Trefferquote ist damit praktisch unbestimmt, und
"2,40 %" oder "4,51 %" sind beides Zahlen mit zwei Stellen, wo keine einzige
gesichert ist. Genauso "1,4 erwartete Treffer in 57 Versuchen" - der ehrliche
Bereich reicht von 0,06 bis 8,8.

Das habe ich in Befund 79 und 80 behauptet, ohne den Vorbehalt zu rechnen.
Der Grundsatz lautet, dass jede Behauptung gemessen wird - ich hatte
geschaetzt und es wie eine Messung aussehen lassen.

### Was trotzdem traegt

Das **Optimum** ist robust. Ueber den ganzen Vertrauensbereich der
Reststreuung:

    untere Grenze   ->  202 Trades
    gemessen        ->  164 Trades
    obere Grenze    ->  142 Trades

Immer zwischen 142 und 202, nie bei 120. Die Aussage "ein Verbund-Partner
sollte rund 150 bis 200 Trades bringen" haelt, obwohl die Trefferquote
daneben um Groessenordnungen schwankt.

Das ist der brauchbare Teil: **Wohin zu zielen ist, steht fest. Wie oft man
trifft, nicht.**

### Warum die beiden sich so verschieden verhalten

Das Optimum ist die Stelle, an der eine Kurve ihr Maximum hat - Maxima sind
gegen eine gemeinsame Skalierung unempfindlich. Die Trefferquote ist ein
Schwanzintegral der Normalverteilung, und Schwanzintegrale reagieren
exponentiell auf die Streuung.

Dieselbe Unsicherheit trifft beide, und sie trifft sie voellig
unterschiedlich. Das ist kein Sonderfall, sondern der Regelfall - und ein
Grund, Aussagen ueber Lagen von Aussagen ueber Wahrscheinlichkeiten zu
trennen.

### Was gebaut wurde

``Katalogkopplung.rest_bereich`` liefert den Vertrauensbereich der
Reststreuung, ``takt_bereich`` das Optimum samt beider Raender, und
``urteil_takt`` nennt beides getrennt. Ein Test haelt fest, dass das Optimum
robust ist und die Quote nicht.

Fuer den naechsten Vorschlagszyklus heisst das: **Ziel sind 150 bis 200
Trades** - nicht die 120, die in ``auftragslage`` stehen. Die Anpassung dort
ist der naechste Schritt.

Versuchsstand 173 unveraendert, Suchbudget 43 von 100. 1694 Tests gruen.

## Zweiundachtzig. Der Auftrag zielte auf die Untergrenze

Befund 81 hat das Optimum fuer einen Verbund-Partner gemessen: rund 165
Trades, robust ueber den ganzen Vertrauensbereich zwischen 142 und 202. Im
Auftrag an den Analysten stand weiter die **Wende** aus der Partnerkarte -
120 Trades.

Das ist keine Kleinigkeit. Die Wende ist die Zahl, ab der ein Partner mit der
Qualitaet des Bestands ueberhaupt genuegt: eine **Untergrenze**. Der Auftrag
hat sie als Ziel genannt, und mein eigener Vorschlagszyklus in Befund 77 hat
danach gezielt - vier Regeln mit 18, 92, 114 und 406 Trades. **Keine einzige
in der Naehe des Optimums.**

Damit ist es derselbe Fehler wie in Befund 76, nur eine Runde spaeter: Der
Auftrag nannte eine Zahl, die zwar stimmt, aber nicht die ist, auf die es
ankommt.

### Was der Auftrag jetzt sagt

    1. Mindestens 120 Trades im selben Zeitraum, am besten rund 165.
       Darunter genuegt selbst ein sehr hoher Sharpe je Trade nicht;
       darueber faellt die Erwartung schneller, als die Anforderung nachgibt.
    2. Sharpe je Trade ueber 0,22 bei der Zahl aus Punkt 1.
       An der Untergrenze von 120 waeren es 0,26, bei 240 nur noch 0,19 -
       mehr Trades sind der wirksamere Hebel als mehr Qualitaet, aber nur
       bis zum Optimum.

Der zweite Punkt musste mitwandern: Er nannte die Anforderung an der Wende,
waehrend der erste inzwischen das Optimum nennt. Zwei Zahlen aus zwei
verschiedenen Trade-Zahlen nebeneinander lesen sich wie ein Widerspruch.

### Und die Unsicherheit steht jetzt drin

Neu ist ein Abschnitt, den es vorher nicht gab:

    ## Wie oft so ein Vorschlag trifft

    Zwischen 0,3 % und 15,5 % - und das ist die ehrliche Auskunft. Die
    Erwartung stammt aus einer Geraden durch 18 Punkte, und ihre
    Reststreuung ist selbst unsicher; ueber deren Vertrauensbereich
    schwankt die Quote um Faktor 49.

    Robust ist dagegen, wohin zu zielen ist: Das Optimum liegt ueber
    denselben Bereich zwischen 143 und 203 Trades.

    Praktisch heisst das: Ein Vorschlag, der die drei Punkte erfuellt, ist
    ein Verdacht und kein Fund. Erst der gerechnete Verbund entscheidet.

Das ist der Kern von Befund 81, in die Form gebracht, in der ein
Vorschlagender ihn braucht. Ohne diese Auskunft haelt er den ersten Treffer
fuer einen Fund - und bei einer Quote, die zu drei Vierteln Rauschen ist,
waere das der teuerste Irrtum, den dieses Projekt noch machen kann.

### Wo die 18 Punkte stehen

Fest verdrahtet in ``auftragslage._optimum``, mit einer Begruendung im
Docstring: Sie sind eine **Messung** und keine Konfiguration. Wer sie aendert,
aendert einen Befund und soll das an dieser Stelle merken. Faellt die Rechnung
aus, bleibt es beim alten Verhalten - dann nennt der Auftrag nur die
Untergrenze, was schlechter ist, aber nicht falsch.

Versuchsstand 173 unveraendert, Suchbudget 43 von 100. 1699 Tests gruen.

## Dreiundachtzig. Vier kalibrierte Regeln - die Methode traegt, die Regeln nicht

Befund 82 hat den Auftrag auf das Optimum umgestellt: rund 165 Trades statt
der Untergrenze von 120. Dieser Lauf beantwortet ihn.

### Wie die Schwellen gewaehlt wurden

Befund 77 hatte vier Regeln gebaut und landete bei 18, 92, 114 und 406
Trades - keine in der Naehe des Ziels. Die Trade-Zahl ergab sich, statt
gewaehlt zu werden.

Diesmal wurde sie **vorher kalibriert**, und zwar ueber die reine
**Signalhaeufigkeit** auf den Kursdaten: Wie oft trifft die Bedingung zu?
Das ist eine Indikatorrechnung ohne Backtest, ohne PnL, ohne Gate - die
Schwelle wird also nach einem Strukturmerkmal gewaehlt und nicht nach dem
Ergebnis. Auszuege:

    volume_zscore(60) > 1,2 + body_pct > 1,0    247 Flanken
    vwap_distance_pct(30) < -5                  263 Flanken
    rsi(14) < 40                                257 Flanken
    bollinger_width(20,2) < 15                  126 Flanken

### Was dabei herauskam

    Vorschlag                            Trades  SR/Trade   noetig      rho
    ------------------------------------------------------------------------
    Volumenschock breit                     145    0,1387   0,2366   +0,587
    Rueckkehr zum Volumenschwerpunkt        130   -0,1704   0,2494   +0,311
    Ueberverkauft ohne Trendfilter          133   -0,1919   0,2467   +0,375
    Enge vor Bewegung breit                  61    0,2238   0,3776   +0,437

**Drei von vier trafen den Zielbereich** (145, 130, 133 gegen 142 bis 202).
Die Methode traegt - das ist der eigentliche Fortschritt dieses Laufs.

**Keiner taugt.** Alle drei, die genug handeln, liegen bei der Qualitaet weit
darunter.

### Wo die Kalibrierung danebenlag, und warum

'Enge vor Bewegung breit' sollte den Zielbereich treffen und kam auf 61
Trades. Der Grund ist ein Denkfehler in meiner Zaehlung: ``bollinger_width <
15`` ist ein **Filter**, kein Einstiegssignal. Gezaehlt wurden 126 Flanken
der Filterbedingung - eingestiegen wird aber nur, wenn **zusaetzlich** der
Kurs das Band nach oben kreuzt. Die Schnittmenge ist viel kleiner.

Die Zaehlung muss also das ganze Signal abbilden und nicht einen Teil davon.
Fuer die drei anderen stimmte sie, weil dort die Einstiegsbedingung selbst
gezaehlt wurde.

### Was die vier mit der Kopplung machen

    18 Punkte (Befund 79)   r = -0,602   t = -3,02   Rest 0,1225
    22 Punkte (mit diesen)  r = -0,543   t = -2,89   Rest 0,1396

Sie **schwaechen** sie leicht und erhoehen die Reststreuung. Das ist ehrlich
zu vermerken: Der Beleg ist etwas duenner geworden, nicht dicker.

Einzeln gegen die alte Gerade gerechnet:

    145 Trades   z = +0,47      im Rahmen
    130 Trades   z = -2,17      deutlich darunter
    133 Trades   z = -2,32      deutlich darunter
     61 Trades   z = +0,51      im Rahmen

Die beiden Mean-Reversion-Regeln liegen weit unter der Erwartung. Sie sind
nicht nur schwach, sie sind schwaecher als die Kopplung vorhersagt - ein
Hinweis, dass Rueckkehr zum Mittel auf Tageskerzen ueber diesen Zeitraum
schlicht nicht traegt, unabhaengig von der Taktung.

### Was das gekostet hat

**Vier Versuche, 173 -> 177.** Suchbudget 47 von 100. Die vier Punkte sind
in ``auftragslage._optimum`` eingeflossen; das Optimum verschiebt sich damit
von 165 auf **151 Trades** (Spanne 137 bis 175), die Trefferquote auf 1,0 bis
14,9 %.

Der Test dazu haelt jetzt einen **Bereich** fest und nicht die Zahl: Sie
wandert mit jeder Messung, und ein Test, der nach jedem Zyklus nachgezogen
werden muss, sagt nichts mehr.

Versuchsstand 177, Suchbudget 47 von 100. 1699 Tests gruen.

## Vierundachtzig. Familien trennen - und Unabhaengigkeit kostet Qualitaet

Befund 83 endete mit einem Verdacht: Die beiden Mean-Reversion-Regeln lagen
mit z = -2,17 und -2,32 deutlich unter der Kopplungsgeraden. Nicht die
Taktung, sondern die **Familie**?

Ueber alle 22 gemessenen Regeln, nach Regellogik gruppiert:

    Familie      n   Mittel z   Spanne
    -------------------------------------------
    Ausbruch     3     +0,93    +0,56 .. +1,14
    Trend        5     +0,87    +0,43 .. +1,18
    Volumen      3     +0,30    -0,16 .. +0,57
    Struktur     6     -0,16    -0,91 .. +0,64
    Rueckkehr    5     -1,41    -1,89 .. -0,81

**Alle fuenf Rueckkehr-Regeln liegen unter der Geraden, alle acht aus Trend
und Ausbruch darueber.** Kein Ueberschneidungsfall.

### Die Gegenprobe, die das braucht

Die Familien habe ich zugeordnet, **nachdem** ich die Werte kannte. Das ist
der klassische Weg, ein Muster in Rauschen zu finden - man gruppiert, bis die
Gruppen sich unterscheiden. Dass die Zuordnung der Regellogik folgt und nicht
den Zahlen, behauptet sich leicht und prueft sich schwer.

Permutation, dieselben Labels zufaellig verteilt:

    Spannweite beobachtet          2,34
    Nullverteilung, Mittel         1,14
    Nullverteilung, 95. Perzentil  1,79
    Anteil der Null darueber       0,20 %

Die Trennung haelt. Bemerkenswert ist wieder die Breite der Null: Eine
Spannweite von 1,1 faellt bei fuenf Familien und 22 Punkten **rein
zufaellig** an. Wer ohne diese Gegenprobe gruppiert, findet immer etwas.

### Und jetzt die unangenehme Haelfte

Ueber die zwanzig Regeln mit gemessener Fensterkorrelation zum Bestand:

    Residuum z gegen |rho|:  r = +0,480   (n = 20, t = 2,32)

**Je aehnlicher eine Regel dem Trendfolge-Signal des Bestands, desto besser
ihre Qualitaet.** Genau die Familien ueber der Geraden - Trend und Ausbruch -
sind die, die dem Bestand am naechsten stehen.

Der Auftrag aus Befund 76 verlangt **beides**: Qualitaet und Unabhaengigkeit.
Punkt 2 und Punkt 3 ziehen gegeneinander, und das stand bisher nirgends.

Damit erklaert sich auch, warum die vier Vorschlaege aus Befund 83 so
ausgingen: Sie waren mit rho zwischen +0,31 und +0,59 die unabhaengigsten,
die das Projekt je gemessen hat - und drei von vier lagen bei der Qualitaet
unter der Erwartung.

### Was das nicht beweist

Es muss keine Eigenschaft der Aehnlichkeit sein. Naheliegender: Der Markt ist
ueber diesen Zeitraum massiv gestiegen. Alles, was dem Trend folgt, hat davon
profitiert; alles, was dagegen laeuft, verloren. Dann misst ``rho`` nur, wie
long-lastig eine Regel war, und der Zusammenhang gehoerte dem **Zeitraum** und
nicht den Regeln.

Beide Deutungen fuehren praktisch zum selben Schluss - die Suche nach
"unabhaengig **und** gut" laeuft gegen die Daten. Aber sie sind nicht
dasselbe, und welche stimmt, ist hier nicht entschieden. Ein Zeitraum mit
anderer Marktrichtung wuerde es entscheiden; den gibt es in diesen Daten
nicht.

### Was daraus folgt

Zwei Dinge, und beide sind unbequem:

1. **Rueckkehr zum Mittel ist als Familie erledigt** - nicht wegen einer
   einzelnen Messung, sondern weil alle fuenf geschlossen unter der Geraden
   liegen und die Trennung der Permutation standhaelt.
2. **Der Auftrag verlangt etwas, das die Daten nicht hergeben.** Die
   verbleibenden 53 Versuche in Regeln zu stecken, die gleichzeitig
   unabhaengig und gut sind, heisst gegen einen gemessenen Zusammenhang zu
   suchen - nicht gegen Zufall.

Das ist kein Grund aufzuhoeren, aber es aendert, was ein Treffer bedeuten
wuerde: Er waere nicht bloss selten, sondern eine Ausnahme von einem Muster,
das inzwischen zweifach belegt ist.

Versuchsstand 177 unveraendert, Suchbudget 47 von 100. 1706 Tests gruen.

## Fuenfundachtzig. Vier fallende Jahre, die ich fuer nicht vorhanden erklaert hatte

Befund 84 endete mit einem Vorbehalt und einem Satz, der falsch war. Der
Vorbehalt: Die gemessene Kopplung zwischen Aehnlichkeit zum Bestand und
Qualitaet (r = +0,480) koennte eine Eigenschaft des **Zeitraums** sein statt
der Regeln, weil der Markt ueber diese Jahre stark gestiegen ist. Der falsche
Satz: "Ein Zeitraum mit anderer Marktrichtung wuerde es entscheiden; den gibt
es in diesen Daten nicht."

Den gibt es. Die Jahresrenditen von BTC in den vorhandenen Daten:

    2018  -73,4 %      2022  -64,2 %
    2019  +94,1 %      2023 +155,7 %
    2020 +304,5 %      2024 +121,0 %
    2021  +59,4 %      2025   -6,3 %
                       2026  -26,5 %

Vier fallende Jahre von neun, darunter zwei mit ueber 60 % Verlust. Ich habe
eine Frage fuer unentscheidbar erklaert, ohne nachzusehen, ob sie es ist. Die
Daten lagen die ganze Zeit auf der Platte.

### Die Antwort auf die offene Frage

``research/phasen.py`` und ``cli phasen`` trennen die Trades jeder Regel nach
dem Jahr des Ausstiegs. Ueber 22 Regeln auf Tageskerzen:

    rho <-> Sharpe in Aufwaertsjahren   +0,404   (t = 1,93)
    rho <-> Sharpe in Abwaertsjahren    +0,075   (t = 0,33)

Der Zusammenhang faellt auf ein Fuenftel und ist im Abwaertsmarkt nicht mehr
nachweisbar. Er kehrt sich aber nicht um. Das spricht eher fuer die
Zeitraum-Deutung als fuer die Regel-Deutung - entscheidet es bei 21 Punkten
mit rho aber nicht. Wer aus t = 0,33 "kein Zusammenhang" liest, macht denselben
Fehler wie ich in Befund 77.

### Der Fehler in meiner eigenen ersten Messung

Der erste Durchlauf sah **14** Regeln und fand **eine** gegenlaeufige. Er kam
zu diesen 14, indem er den Katalog nach Namen filterte: Trend, Momentum,
Donchian. Damit waren genau die Regeln ausgeschlossen, die die Frage
beantworten - die short-faehigen.

Ueber den vollen Katalog sind es **sechs von 22**, und alle sechs sind short
oder beidseitig. Eine Auswahl nach Namen ist eine Auswahl, und diese hat die
Antwort weggeschnitten, statt sie zu finden. Das ist derselbe Mechanismus wie
in Befund 83, wo ich Filterkanten als Einstiegssignale gezaehlt hatte: eine
Vorverarbeitung, die das Ergebnis erzeugt.

### Was die Fensterkorrelation nicht misst - und das ist die Nachricht

Die Partnersuche siebt seit Befund 73 nach kleiner Fensterkorrelation. Ueber
dieselben Regeln gemessen:

    rho <-> (Sharpe auf - Sharpe ab)   +0,097   (t = 0,43)

Praktisch null. Die Fensterkorrelation misst, ob zwei Regeln **gleichzeitig**
verdienen; sie sagt nichts darueber, ob die eine gerade dann verdient, wenn
die andere verliert. Zwei Regeln koennen bei rho = 0 beide in denselben Jahren
schwach sein - und in diesen Daten sind sie es meistens: 16 von 22 Regeln sind
im Abwaertsmarkt schlechter, im Median um 0,37 Sharpe je Trade.

Wer nach kleinem rho siebt, siebt an der Phaseneigenschaft systematisch
vorbei. Das ist kein Fehler der Fensterkorrelation, sondern eine Grenze, die
bisher nicht benannt war.

### Was die sechs kosten

Sie verdienen im Abwaertsmarkt und bezahlen dafuer im Aufwaertsmarkt:

    Regel                          SR auf    SR ab   insgesamt
    VWAP-Rueckkehr short          -0,2261  +0,3188    -0,1230
    Luecke wird geschlossen       -0,1820  +0,2593    -0,0434
    Bollinger-Ruecksetzer short   -0,2452  +0,2062    +0,0432
    Abfolge-Modell short          -0,0915  +0,3332    +0,0797
    Grosse Kerze m. Volumen short -0,1561  +0,3685    +0,1216
    Trend beide Richtungen        +0,1794  +0,3430    +0,2334

Die Verbund-Guete rechnet ueber die **ganze** Stichprobe. Eine Regel, die nur
in einer Phase verdient, zieht den Schnitt genau so weit herunter, wie sie ihn
in der anderen hebt. Die staerkste Gegenlaeufigkeit - VWAP-Rueckkehr short,
Unterschied 0,54 - ist zugleich die schlechteste Regel des Feldes. Wer nur
nach Gegenlaeufigkeit siebt, findet zuerst die Regeln, die im Aufwaertsmarkt
am meisten verlieren.

Bleibt eine: 'Trend beide Richtungen', 0,3430 abwaerts gegen 0,1794 aufwaerts,
insgesamt +0,2334. Und auch die ist kein Fund: Von ihren 106 Trades fallen 35
in die Abwaertsjahre, das Messrauschen dort betraegt 0,17, der Phasenunter-
schied 0,16. Er liegt **darunter**. Dazu kommt die Auswahl ueber 22
Hypothesen. Eine Ablesung, keine Aussage.

Zum Vergleich der Bestand: 0,3473 aufwaerts, **-0,0450 abwaerts**, insgesamt
0,2123. Er hat im Abwaertsmarkt nichts. Das ist die Zahl, die den ganzen
Verbund-Auftrag begruendet.

### Was daraus folgt

1. **Der Vorbehalt aus Befund 84 ist geprueft, nicht ausgeraeumt.** Die
   Kopplung faellt im Abwaertsmarkt deutlich - ein Hinweis auf die
   Zeitraum-Deutung, kein Beweis.
2. **Die Partnersuche hat eine blinde Achse.** Kleines rho und
   Phasenkomplementaritaet sind in diesen Daten unkorreliert. Wer das eine
   sucht, findet das andere nicht.
3. **Phasenkomplementaritaet allein reicht nicht.** Sie ist reichlich
   vorhanden und fast immer wertlos, weil sie in der anderen Phase bezahlt
   wird.

### Was offen bleibt - und messbar ist

``verbund_guete`` nimmt an, dass Unabhaengigkeit nur die effektive Stichprobe
verkleinert. Sie senkt dort nicht die Streuung. Bei wirklich gegenlaeufigen
Beinen tut sie das aber - eine kombinierte Kurve aus zwei antikorrelierten
Beinen kann einen hoeheren Sharpe haben als der gewichtete Schnitt der beiden
Einzel-Sharpes. Ob das Modell den Wert eines gegenlaeufigen Partners deshalb
**unterschaetzt**, ist nicht gemessen. Das ist der naechste Schritt, und er
ist eine Pruefung der eigenen Formel, keine Kandidatensuche.

Versuchsstand 177 unveraendert - zerlegt wurden Trades, die ohnehin gerechnet
waren. Suchbudget 47 von 100. 1719 Tests gruen.

## Sechsundachtzig. Die Formel, an der acht Regeln gemessen und verworfen wurden

Befund 85 endete mit einer offenen Frage: ``verbund_guete`` nimmt an, dass
Unabhaengigkeit nur die effektive Stichprobe verkleinert, nicht die Streuung -
bei gegenlaeufigen Beinen tut sie das aber. Ob das Modell den Wert eines
solchen Partners unterschaetzt, war nicht gemessen.

Es gehoert geprueft, weil viel daran haengt. Der Auftrag aus Befund 76 - "ein
Partner braucht rund 0,26 Sharpe je Trade bei 120 Trades" - steht ganz auf
``partnerkarte.verbund_sharpe``. Acht selbstgebaute Regeln aus Befund 77 und
83 wurden daran gemessen und verworfen. Ist die Formel schief, waren alle acht
an der falschen Latte gemessen.

### Zwei Formeln fuer dieselbe Groesse

Beim Nachsehen kamen gleich zwei zum Vorschein, die nebeneinander leben:

``partnerkarte.verbund_sharpe`` bildet den trade-gewichteten Schnitt der
beiden Sharpes - damit rechnet die Karte, die den Auftrag stellt.
``Verbund.kandidat`` nimmt den Sharpe der **zusammengeworfenen** Trade-Liste -
damit rechnet der Verbund, der den Auftrag einloest. Bei ungleichen
Mittelwerten oder Streuungen ist das nicht dieselbe Zahl. Genau davor warnt
der Kommentar in ``Kandidat.aus_trades``, und genau das war wieder passiert.

Beide arbeiten auf der Trade-Ebene, und dort gibt es keine Zeitachse.

### Die Vergleichsgroesse und ihre Kontrolle

``research/verbundmodell.py`` und ``cli verbundmodell`` legen beide Beine auf
ein gemeinsames Wochenraster, addieren die Ertraege je Woche und nehmen davon
den t-Wert. ``Guete = SR/Trade * sqrt(n)`` ist ein t-Wert, und
``SR/Woche * sqrt(Wochen)`` ist derselbe t-Wert auf anderer Achse - bei
unabhaengigen Trades sind sie identisch, und das ist nachrechenbar und nicht
behauptet.

Die Kontrolle steht deshalb im Bericht: Fuer einzelne Beine muessen beide
Achsen uebereinstimmen. Sie tun es (Bestand 3,216 gegen 3,102; groesste
Abweichung ueber 21 Regeln 0,54). Ohne diese Kontrolle waere jeder Unterschied
beim Verbund genauso gut ein Artefakt der Aggregation.

### Was ueber 210 Paare herauskam

                         Mittel   Median
    Karte                 2,022    2,326
    zusammengeworfen      2,271    2,433
    Wochen (echt)         1,784    1,867

    Karte  - echt         +0,238   zu hoch in 71 % der Paare
    Topf   - echt         +0,487   zu hoch in 93 % der Paare

Beide Trade-Formeln sind im Schnitt zu optimistisch. Der Auftrag aus Befund 76
war also zu **milde** gestellt, nicht zu streng - die Richtung, die zaehlt.

Der Fehler ist aber nicht konstant, sondern faehrt auf der Fensterkorrelation:

    Fehler der Karte = 1,595 * rho - 0,076     r = +0,752, t = 16,45

    rho -0,39 bis -0,01   Fehler -0,274   (Karte zu niedrig)
    rho -0,01 bis +0,16   Fehler +0,085
    rho +0,16 bis +1,00   Fehler +1,000   (Karte zu hoch)

Die Karte stimmt bei rho = +0,05 und sonst nirgends. Das ist kein Zufall,
sondern genau die Annahme, die in ihr steckt: Ein gewichteter Schnitt kennt
keine Korrelation.

### Der Verdacht aus Befund 85 ist bestaetigt

In 60 von 210 Paaren **unterschaetzt** die Karte, und zwar dort, wo die Beine
gegenlaeufig sind:

    VWAP-Rueckkehr short + Donchian 55/20      Karte -0,177   echt 1,730
    Luecke geschlossen   + Donchian 55/20      Karte +0,469   echt 1,935
    VWAP-Rueckkehr short + Trend 100 Tage      Karte +0,217   echt 1,595

'VWAP-Rueckkehr short' hat -0,123 Sharpe je Trade. Die Karte wirft sie sofort
weg. Als Portfolio-Bein hebt sie einen Verbund auf 1,73. Das ist der
Hedge-Wert, den eine Rechnung ohne Zeitachse nicht sehen kann - und der Grund,
warum die Partnersuche nach der falschen Groesse sortiert.

### Der Fehler, den ich dabei fast gemacht haette

Das beste Paar von 210 erreicht 3,585. Die Faustformel aus Befund 71 gibt bei
21 unabhaengigen Ziehungen eine Schranke von 3,549 - **darunter**, und das
Urteil sagte prompt "schlaegt die eigene Auswahl. Das gehoert gerechnet."

Der Abstand betraegt 0,036 bei einer Streuung von 0,918: vier Hundertstel
Standardabweichungen. Es ist derselbe Fehler wie in Befund 71, nur andersherum:
Die Schranke ist der **Erwartungswert** des Maximums, und die Haelfte aller
reinen Rauschziehungen liegt darueber. Ein Maximum knapp daneben ist der
Normalfall.

Die richtige Null hat dieselbe Struktur wie die Messung. Jede Wochenreihe wird
zyklisch verschoben - Mittelwert, Streuung und Eigenkorrelation jeder Regel
bleiben exakt erhalten, zerstoert wird nur, **wann** die Regeln zusammen
verdienen:

    gemessen                    3,585
    Nullprobe, Median           3,682
    Nullprobe, 95. Perzentil    3,731

Der gemessene Wert liegt nicht bloss unter dem Perzentil, sondern unter dem
**Median**. Zufaellig gegeneinander verschobene Regeln ergeben im Schnitt ein
besseres bestes Paar als die echten: Das Zusammenspiel dieser 21 Regeln ist
nicht neutral, sondern leicht schaedlich. Sie verdienen zu gleichzeitig.

### Was daraus folgt

1. **Die Partnerkarte sortiert nach der falschen Groesse.** Sie ist nur bei
   Unabhaengigkeit richtig, ueberschaetzt bei Gleichlauf und uebersieht
   Hedge-Partner vollstaendig.
2. **Der Auftrag war zu milde, nicht zu streng.** Die acht verworfenen Regeln
   aus Befund 77 und 83 waeren an der richtigen Latte nicht besser
   weggekommen, sondern schlechter.
3. **Es oeffnet trotzdem keinen Weg.** Unter den Partnern, die die Karte
   uebersieht, ist keiner, der reicht. Die Korrektur aendert das Bild, nicht
   den Stand.

### Was das nicht zeigt

Der Wochen-t-Wert ist **roh**. Die noetige Guete von 3,629 ist nach
Blockkuerzung definiert; ein roher Wert von 3,585 waere danach kleiner. Wer
beide Zahlen nebeneinanderstellt, vergleicht eine Obergrenze mit einer
Anforderung - hier steht die Nullprobe fuer die Aussage, nicht der Vergleich
mit 3,629.

Versuchsstand 177 unveraendert - neu aggregiert wurden Trades, die ohnehin
gerechnet waren. Suchbudget 47 von 100. 1730 Tests gruen.

## Siebenundachtzig. Das Gate kuerzt - aber nicht dort, wo es muesste

Befund 86 hat gemessen, dass die Trade-Achse systematisch zu optimistisch ist.
Dort ging es um Verbuende. Es betrifft aber genauso einzelne Kandidaten - und
**das Zulassungs-Gate rechnet auf der Trade-Achse.**

Das Gate kuerzt bereits: ``effektive_stichprobe`` misst die Korrelation
zwischen Walk-Forward-Fenstern und fasst gleichzeitig offene Positionen
zusammen. Ob das reicht, war nie geprueft. Und wenn es nicht reicht, faellt
der Fehler zugunsten des Kandidaten aus - genau die Richtung, die der oberste
Grundsatz verbietet.

### Drei Achsen fuer dieselbe Regel

``research/zeitachse.py`` und ``cli zeitachse`` rechnen je Regel drei t-Werte,
ueber 21 Regeln auf Tageskerzen:

                            Mittel
    t roh (alle Trades)      1,500
    t nach Gate-Kuerzung     1,489
    t auf der Wochenachse    1,275

Die Kuerzung des Gates holt elf Tausendstel von den 225, die die Zeitachse
sieht. Sie deckt **15 %** dessen ab, was noetig waere.

Dass es Zeitstruktur ist und kein Rechenartefakt, sagt die Nullprobe je Regel:
dieselben Trade-Ergebnisse zufaellig ueber dieselben Wochen verteilt. Sie
landet jeweils dicht an der Trade-Achse - genau wie es sein muss. Der echte
Wert liegt darunter.

### Was die Tests an meiner Deutung korrigiert haben

Ich hatte geschrieben, die Trades "klumpen zeitlich". Der erste Testentwurf
verlangte daraufhin, dass Dreierklumpen in derselben Woche die Stichprobe um
ein Drittel kuerzen - und scheiterte mit 7 %. Zu Recht: Drei **unabhaengige**
Trades aufsummiert ergeben einen Wert mit dreifachem Mittel und
wurzel-dreifacher Streuung. Der t-Wert bleibt exakt erhalten.

Klumpung allein kostet also gar nichts. Es kostet erst, wenn die Trades
innerhalb eines Klumpens **gemeinsam** gewinnen oder verlieren. Beide Faelle
stehen jetzt als Tests da, und die Beschreibung im Modul ist entsprechend
praeziser.

### Wo es wehtut

Am staerksten trifft es die Regeln mit wenigen, guten Trades - also genau die
Verbund-Anwaerter aus Befund 73:

    Regel                        Trades   Gate kuerzt   Zeit verlangt
    Trend-Beteiligung 200 Tage       53           0 %          37,2 %
    Trend beide Richtungen          106           0 %          36,3 %
    Trend-Beteiligung 100 Tage      109         8,3 %          15,9 %
    Trend 50 Tage mit Konfluenz     154           0 %           3,9 %
    Trend-Beteiligung 50 Tage       156        21,2 %           2,3 %

In Befund 73 stand, der Verbund aus Spitze und 'Trend-Beteiligung 200 Tage'
hebe die Guete auf 3,368 und den Deflated Sharpe auf 0,8602 - "der groesste
Sprung, den in diesem Projekt je etwas gebracht hat". Fuer dieses Bein beruht
die Zahl auf einer Achse, die es um ein Fuenftel zu gut bewertet.

Der Bestand selbst ist kaum betroffen: 154 Trades, nach Zeitachse 148. Sein
t-Wert faellt von 3,216 auf 3,102. Noetig sind 3,629 - der Abstand waechst von
0,41 auf 0,53.

### Die schaerfere Aussage

"Kuerzt zu wenig" waere reparierbar: Man koennte die Blockkuerzung staerker
einstellen. Die Messung sagt aber etwas anderes:

    Zusammenhang zwischen Gate-Kuerzung und Zeit-Kuerzung:  r = -0,47

**Gegenlaeufig.** Das Gate kuerzt tendenziell dort, wo es nicht noetig ist, und
laesst ungekuerzt, wo es noetig waere - siehe die letzten beiden Zeilen der
Tabelle oben. Hochskalieren hilft dagegen nicht, denn es misst etwas anderes:
die Korrelation zwischen Walk-Forward-Fenstern liegt auf Jahresskala, die
Klumpung sitzt auf Wochenskala.

Ein zweiter Mangel kam aus den Tests: Der erste Entwurf meldete bei
ausgeglichenem Mittelwert nur "haelt mit" und verschwieg die Stellenfrage. Ein
Gate kann im Schnitt richtig kuerzen und in jeder einzelnen Zeile
danebenliegen - der gefaehrlichere Fall, weil er wie Ordnung aussieht. Das
Urteil sagt es jetzt in beiden Zweigen.

### Was das ist und was nicht

**Kein neues Gate und keine Aenderung an einem bestehenden.** Es ist eine
Messung: Eine vorhandene Kuerzung tut weniger als gedacht, und der Fehler
zeigt zugunsten des Kandidaten. Wer daraus ein Gate machen will, muss zuerst
zeigen, dass die Wochenlaenge der richtige Massstab ist - hier steht nur, dass
Trade- und Zeitachse auseinanderlaufen und um wieviel.

Bei verlierenden Regeln dreht sich die Deutung um: Dort ist ein kleinerer
Betrag eine Verbesserung. Sie stehen in der Tabelle gezeichnet und zaehlen in
keiner Auswertung mit.

Versuchsstand 177 unveraendert - neu aggregiert wurden Trades, die ohnehin
gerechnet waren. Suchbudget 47 von 100. 1742 Tests gruen.

## Achtundachtzig. Sieben Namen fuer eine Regel - und zwei eigene Befunde, die daran haengen

Dieser Lauf begann mit einer Idee und endete mit einer Korrektur an mir selbst.

### Die Idee, und warum sie fallengelassen wurde

Aus Befund 87 folgte eine naheliegende Vermutung: Wenn Trades kosten, weil sie
gehaeuft und gleichlaeufig anfallen, dann sind die Folgetrades eines Klumpens
Redundanz. Eine Sperrfrist (``cooldown_bars`` gibt es im Genom bereits)
muesste dann die Qualitaet heben, ohne die Stichprobe wirklich zu verkleinern.

Gemessen auf vorhandenen Trades, ohne einen Versuch auszugeben - erster Trade
eines Klumpens gegen die Folgetrades, ueber sechs Sperrfristen:

    Sperrfrist   n   SR erste   SR folge     Diff       t
       3 Tage    5    +0,2203    -0,2402   +0,4605   +1,24
       5 Tage    6    +0,2402    +0,0877   +0,1524   +1,29
       7 Tage    7    +0,1901    +0,1504   +0,0397   +0,58
      10 Tage    9    +0,1291    +0,0363   +0,0928   +1,00
      14 Tage    9    +0,1436    +0,0639   +0,0797   +1,15
      21 Tage   10    +0,1425    +0,1091   +0,0334   +0,68

Die Richtung stimmt durchgehend - Folgetrades sind tendenziell schlechter -,
aber **kein einziger t-Wert erreicht 2**. Fuer eine Sperrfrist wird kein
Versuch ausgegeben.

Der erste Durchlauf derselben Messung sah bei 14 Tagen t = +3,04 und damit
einen klaren Befund. Nach Entdopplung sind es +1,15. Das war der Hinweis.

### Sieben Namen, eine Regel

Der Katalog auf Tageskerzen enthaelt 21 Genome, von denen sechs **identische
Trades** liefern:

    Trend-Beteiligung 200 Tage        Trend mit Vola-Ziel 20 %
    Trend-Beteiligung voller Einsatz  Trend mit Vola-Ziel 22 %
    Vola-Ziel, kurzes Messfenster     Vola-Ziel, langes Messfenster

Zusammen mit 'Trend-Beteiligung (fair gerechnet)' sind das sieben Namen fuer
eine Regel mit 53 Trades. Sie unterscheiden sich in Feldern, die auf diesen
Daten nichts aendern - etwa einem Vola-Messfenster, das bei dieser
Signalhaeufigkeit nie greift.

``anwaerter`` und ``phasen`` entdoppeln laengst, jeweils mit eigener
handgeschriebener Logik. Genau daran ist es gescheitert: Ich habe zwei neue
Befehle gebaut, und in beiden fehlte die Entdopplung, weil sie nirgends als
Baustein stand. Jetzt steht sie in ``research/entdopplung.py`` und wird
benutzt.

### Was das an Befund 86 und 87 aendert

**Befund 87, Zeitachse:**

                              erste Fassung   entdoppelt
    mittlere Luecke                  20,2 %       11,7 %
    Deckung durch das Gate             15 %         32 %
    r(Gate-Kuerzung, Zeit-Kuerzung)  -0,470       -0,261
    betroffene Regeln                 11/18         5/12

Die Kernaussage von Befund 87 war: "Das Gate kuerzt gegenlaeufig - es kuerzt
dort, wo es nicht noetig ist." **Diese Aussage faellt.** Entdoppelt ist
r = -0,261 bei zwoelf Regeln, also t = -0,86. Nicht nachweisbar.

Und die Zahl kam nicht bloss verstaerkt zustande, sondern erzeugt: Die
siebenfach gezaehlte Regel ist ausgerechnet die mit 37 % Zeit-Luecke und ohne
jede Gate-Kuerzung.

Was von Befund 87 haelt: Das Gate kuerzt weiterhin zu wenig (11,7 % gegen eine
Schwelle von 10 %, knapp). Die Nullprobe-Kontrolle traegt. Fuenf von zwoelf
Regeln liegen ueber der Schwelle, am staerksten die mit 53 Trades. Der Bestand
ist mit 3,9 % kaum betroffen.

**Befund 86, Verbundmodell:**

                              erste Fassung   entdoppelt
    Kartenfehler                    +0,238       -0,029
    Topffehler                      +0,487       +0,221
    r(rho, Kartenfehler)            +0,752       +0,440  (t = +4,97)
    Paare                              210          105

Die Ueberschrift "Beide Trade-Formeln sind zu optimistisch" ist fuer die
**Karte falsch** - sie liegt im Mittel richtig. Damit faellt auch der Satz
"der Auftrag aus Befund 76 war zu milde gestellt". Er stand in Befund 86 und
war nicht belegt.

Was haelt, und das ist die eigentliche Aussage jenes Befundes: Der Fehler der
Karte faehrt auf der Fensterkorrelation (r = +0,440 ueber 105 Paare, t = 4,97),
sie stimmt nur bei Unabhaengigkeit, und sie uebersieht Hedge-Partner - 42 von
105 Paaren werden zu schlecht bewertet. Auch der zusammengeworfene Topf, mit
dem ``Verbund.kandidat`` rechnet, bleibt zu optimistisch (+0,221, zu hoch in
87 %). Und die Nullprobe bleibt unveraendert: Das beste Paar erreicht 3,585
gegen einen Nullmedian von 3,683 - es schlaegt die eigene Auswahl nicht.

### Was daraus fuer die Arbeitsweise folgt

1. **Entdopplung ist Pflicht, nicht Feinschliff.** Ein Duplikat ist keine
   zweite Beobachtung: Es senkt die Streuung und hebt jeden t-Wert, also genau
   das, was ueber "nachweisbar" entscheidet. Als Test steht das jetzt als
   Falsch-Positiv-Rate ueber 400 Ziehungen da.
2. **Die |t|-Schranke gehoert in jedes Urteil.** ``partnerkarte`` hat sie seit
   Befund 75, weil dort derselbe Fehler passiert war. ``zeitachse`` und
   ``verbundmodell`` hatten sie nicht - jetzt schon, und beide sagen bei
   schwachem Zusammenhang "bleibt offen" statt einen Schluss zu ziehen.
3. **Die Ueberschrift muss den Zahlen folgen.** Das Urteil im Verbundmodell
   behauptete "beide Formeln sind zu optimistisch" und druckte daneben -0,029.
   Der Satz war aus der ersten Messung stehengeblieben, als die Zahl kippte.

Kein Ergebnis dieses Laufs bewegt den Stand Richtung Gates. Zwei Befunde sind
jetzt kleiner, als sie waren, und einer davon in seiner Hauptaussage
hinfaellig.

Versuchsstand 177 unveraendert. Suchbudget 47 von 100. 1752 Tests gruen.

## Neunundachtzig. Der Analyst wusste nicht, was schon zu ist

Vier Laeufe hintereinander waren Diagnose oder Korrektur. Die Instrumente sind
jetzt gut, und sie sagen alle dasselbe: Im vorhandenen Regelvorrat gibt es
keinen Weg. Der Katalog ist als Partnerquelle durch (0 von 15), acht
selbstgebaute Regeln sind gescheitert, alle Regler sind ausgemessen.

Damit bleibt genau eine Quelle fuer neue Hypothesen: die Research-KI. Sie ist
seit Phase 6 gebaut und laeuft in ``cli research`` - aber sie bekam einen
Auftrag, der die Haelfte des Wissens nicht enthielt.

### Zwei Punkte von der offenen Liste, ehrlich geklaert

**P7 ist gebaut.** ``data/termine.py`` (21 kB), ``cli termine`` holt die
FOMC-Historie ab 2012, und ``_terminkalender`` haengt denselben Kalender an
Backtest **und** Handel. Der Punkt steht seit Laeufen auf der Liste und ist
erledigt; ich habe ihn nicht neu gebaut, sondern nachgesehen.

**Die Research-KI wird im Wettbewerb nicht genutzt - das stimmt.**
``cli research`` ruft sie, ``cli wettbewerb`` nicht. Das ist aber nicht der
Engpass: Ein zweiter Aufrufpfad wuerde dieselben untauglichen Vorschlaege
erzeugen wie in Befund 83. Der Engpass ist der Auftrag.

Dazu die harte Grenze dieses Containers: **ANTHROPIC_API_KEY ist nicht
gesetzt.** Ich kann die KI hier nicht laufen lassen, nur den Auftrag bauen und
ohne Netz pruefen.

### Was dem Auftrag fehlte

``build_prompt`` gab bisher: erlaubte Indikatoren, fuenf Zulassungsschwellen,
die letzten sechs Journaleintraege und - seit einem frueheren Lauf - den
gemessenen Auftrag aus ``auftragslage``. Es fehlte die andere Haelfte: **was
gemessen und geschlossen ist.**

Genau daran ist Befund 83 gescheitert. Zwei meiner vier eigenen Vorschlaege
kamen aus der Rueckkehr-zum-Mittel-Familie - die Befund 84 dann geschlossen
hat. Derselbe Weg stand dem Analysten offen, und nichts hielt ihn davon ab.

``research/ausschluss.py`` traegt jetzt drei Dinge in den Auftrag:

1. **Geschlossene Familien.** Auf den Messwerten ist genau eine zu:
   Rueckkehr, fuenf Regeln, auch die beste liegt 0,815 unter der Geraden.
   Struktur, Trend, Ausbruch und Volumen bleiben offen, weil dort jeweils
   mindestens eine Regel darueber liegt.
2. **Die acht selbstgebauten Fehlschlaege** aus Befund 77 und 83. Sie stehen
   nicht im Journal, weil sie ausserhalb des Research-Loops entstanden sind -
   dem Analysten fehlten sie deshalb vollstaendig.
3. **Den Zielkonflikt.** Der Auftrag verlangt Qualitaet je Trade **und**
   Unabhaengigkeit vom Bestand; ueber 22 Regeln laufen die beiden mit +0,480
   gegeneinander.

### Zwei Entscheidungen, die die Ausschluesse eng halten

**Massgeblich ist die beste Regel einer Familie, nicht ihr Mittel.** Sonst
schliesst ein Ausreisser nach unten eine Familie zu, in der etwas Brauchbares
steht. Deshalb sind nur Familien zu, in denen **keine** Regel ueber der
Geraden liegt.

**Ohne bestandene Permutationsprobe wird gar nichts ausgeschlossen.** Ein
falscher Ausschluss ist teurer als ein fehlender: Er schliesst einen Weg zu,
den danach niemand mehr prueft. Haelt die Gruppierung dem Zufall nicht stand,
darf sie keine Vorschlaege verhindern - auch wenn einzelne Familien
geschlossen aussehen.

Und der Zielkonflikt steht als **Begruendung, nicht als Verbot**: "Ein
Vorschlag, der beides erfuellt, waere eine Ausnahme von einem gemessenen
Muster - und genau danach wird gesucht." Wer das weiss, sucht anders als wer
es nicht weiss.

### Eine Wahrheit statt zwei

Die Familienzuordnung lebte bisher nur in ``tests/test_familien.py``. Der
Auftrag braucht sie im Produktivcode - und wenn beide auseinanderlaufen, sagt
der Befund etwas anderes als der Auftrag. ``familien.familie_von`` ordnet
jetzt ueber Schluesselwoerter zu, und ein Test verlangt, dass sie die
handgeschriebene Zuordnung fuer alle 22 Regeln exakt trifft. Sie tut es.

Regeln ohne Zuordnung fallen **heraus** statt in einen Topf "Sonstige" - das
waere eine Familie, die keine ist, und ueber die dann eine Spannweite
gerechnet wuerde. Betroffen sind zwei Katalogregeln.

### Was das bringt und was nicht

Der Prompt waechst um rund 1,5 kB. Ob die Vorschlaege dadurch besser werden,
ist **nicht gemessen und hier nicht messbar** - dazu braeuchte es einen
Modellaufruf, und der Schluessel fehlt in diesem Container. Was gemessen ist:
Der Auftrag enthaelt jetzt, was er vorher nicht enthielt, in der richtigen
Reihenfolge, und ohne Ausschluesse ist der Prompt zeichengleich mit vorher.

Das verschiebt keine Schwelle und bewegt den Stand nicht. Es raeumt eine
Ursache aus, die in Befund 83 nachweislich Versuche gekostet hat.

Versuchsstand 177 unveraendert. Suchbudget 47 von 100. 1767 Tests gruen.

## Neunzig. Ich habe eine beantwortete Frage neu gestellt

Dieser Lauf begann mit einer Beobachtung, die richtig war, und einem Schluss,
der falsch war.

Richtig: Befund 54 bis 89 laufen ausnahmslos auf Tageskerzen, der Katalog
enthaelt zwei Generationen fuer 15-Minuten-Kerzen, und die Daten liegen im
Speicher - 222.700 Kerzen je Markt. Falsch: dass daraus eine offene Frage
folgt.

**Sie ist in Befund 15 und 16 beantwortet.** Zwoelf Scans ueber vier Maerkte
und vier Intervalle, null Funde; auf 15 Minuten ist nach Kosten nichts zu
holen. Und in Befund 29 stehen die 14 Kandidaten, die dort brutto verlieren.

### Wie weit ich gekommen bin, bevor es auffiel

Ich habe die Daten geprueft, einen Lauf getimt, alle 14 Genome im Hintergrund
messen lassen - und dabei ``research/taktung.py`` und
``tests/test_taktung.py`` **ueberschrieben**, ohne sie vorher zu lesen. Beide
existierten seit Befund 61 und beantworten genau dieselbe Frage: welche
Kerzenlaenge den Deflated Sharpe arithmetisch tragen kann.

Aufgefallen ist es erst, als ``ruff`` einen doppelten Befehlsnamen meldete.
Beide Dateien sind aus ``git`` wiederhergestellt, die Messung wurde
abgebrochen. Verbraucht wurden Rechenzeit und ein Lauf - keine Versuche, denn
gemessen wurde nie ein Kandidat unter Gates.

### Das Werkzeug, das mich gestoppt haette, gibt es

``cli stand`` braucht **zehn Sekunden** und enthaelt seit Befund 62 die Zeile

    15-Minuten-Kerzen      alle 14 Kandidaten verlieren brutto      Nr. 29

und darunter woertlich: "Wer einen davon erneut misst, zahlt Versuche fuer ein
Ergebnis, das schon dasteht."

Ich habe in Schritt 1 des Ablaufs die Commits und den Versuchszaehler
angesehen und ``cli stand`` nicht ausgefuehrt. Das ist kein Werkzeugproblem.

### Was am Werkzeug trotzdem fehlte

Beim Nachsehen zeigte sich ein echter Mangel: **Die Liste endete bei Befund
60.** Alles, was seit Befund 70 geschlossen wurde, stand nicht darin - ein
Lauf, der dort nachschlug, sah den Stand von vor dreissig Befunden. Neun
Eintraege ergaenzt:

    Schiefe erhoehen        Pearson-Grenze: Woelbung >= Schiefe^2 + 1   Nr. 70
    Woelbung senken         unter 1 mathematisch unmoeglich             Nr. 70
    Trade-Zahl heben        Kopplung -0,53 ueber 22 Regeln              Nr. 75
    Katalog als Partner     0 von 15 Genomen taugen                     Nr. 74
    Eigenbau-Partner        8 Regeln aus Befund 77 und 83 gescheitert   Nr. 83
    Familie Rueckkehr       alle 5 unter der Geraden, Permutation haelt Nr. 84
    Phasen-Partner          6 von 22 gegenlaeufig, 5 insgesamt wertlos  Nr. 85
    Verbund aus dem Katalog bestes Paar 3,585 unter Nullmedian 3,683    Nr. 86
    Sperrfrist              Folgetrades schlechter, kein t-Wert ueber 2 Nr. 88

Damit stehen 26 geschlossene Wege da statt 17.

### Und die Verweise werden jetzt geprueft

Jeder Eintrag behauptet eine Fundstelle. Zeigt eine Nummer ins Leere, ist der
Eintrag eine Behauptung - und genau darauf verlaesst sich ein Lauf, der wissen
will, ob eine Frage schon beantwortet ist.

``stand.zahlwort`` bildet die Befundnummer auf die Ueberschrift im Laborbuch
ab ("## Neunundzwanzig."), und zwei Tests pruefen: **jede** der 22
Fundstellen existiert, und die juengste liegt hoechstens sechs Befunde hinter
dem Laborbuch. Die zweite Schranke ist die wichtigere - sie schlaegt an, sobald
die Liste wieder hinterherhaengt.

Der erste Anlauf der Zahlwortfunktion bildete "Dreiundzehn" statt "Dreizehn"
und fand drei Fundstellen nicht, die es gibt. Die Teens stehen jetzt als
Sonderfaelle da, und ueber 99 faellt die Suche sichtbar aus statt still.

### Was daraus folgt

1. **Schritt 1 des Ablaufs heisst ``cli stand``**, nicht nur ``git log``. Zehn
   Sekunden gegen einen verlorenen Lauf.
2. **Vor dem Schreiben lesen.** Ich habe zwei Dateien ueberschrieben, weil ich
   ihre Namen fuer frei hielt. Das Schreibwerkzeug hat "updated" gemeldet, nicht
   "created" - der Hinweis stand da.
3. Der Stand bewegt sich durch diesen Lauf **nicht**. Er raeumt eine Ursache
   aus, die ihn heute einen Lauf gekostet hat.

Versuchsstand 177 unveraendert - es wurde kein Kandidat unter Gates gemessen.
Suchbudget 47 von 100. 1774 Tests gruen.

## Einundneunzig. Die eigene Tabelle zeigte in die falsche Richtung

Dieser Lauf begann, wie der vorige geendet hat: mit ``cli stand``. Zehn
Sekunden, und der Blick faellt zuerst auf die vier offenen Gates.

    - Messlatte                   166.143 gegen     43.639
    - Schlechtestes Jahr          -10.320 gegen    -10.000
    - Deflated Sharpe               0.783 gegen      0.950
    - Parameter-Plateau             0.500 gegen      0.600

Mein erster Schluss daraus: Die Messlatte ist mit Faktor 3,8 das am weitesten
entfernte Gate und gehoert zuerst angesehen. **Das war falsch, und zwar genau
verkehrt herum.**

### Was die Zeile wirklich sagt

Bei diesem Gate ist ``value`` die Rendite der Strategie (+166,1 %) und
``threshold`` die des auf ihren Rueckgang heruntergefahrenen Haltens
(+43,6 %). Risikobereinigt ist das Gate also um das **3,8-fache
uebererfuellt**. Es faellt an einer zweiten Bedingung durch, die im
Zahlenpaar gar nicht vorkommt:

    Strategie +166,1 % bei 10,6 % Rueckgang (+13,5 % p.a.), Halten +1195,4 %
    bei 76,1 % - risikobereinigt besser, aber nur 13,5 % im Jahr. Unter 15 %
    lohnt der Betrieb nicht.

Die Erklaerung stand die ganze Zeit in ``GateResult.message``. Sie wurde nur
nie angezeigt. Ein Gate mit zwei Bedingungen laesst sich nicht auf ein
Zahlenpaar zusammenziehen - und eine Zeile, die plausibel aussieht und in die
falsche Richtung zeigt, ist schlimmer als gar keine, weil niemand nachfragt.

``cli stand`` zeigt die Botschaft jetzt unter jeder nicht bestandenen Zeile.

### Die zweite Sache, die dabei auffiel

Beim Nachlesen der uebrigen drei Botschaften zeigte sich, dass die vier
offenen Gates **nicht vier gleichartige Aufgaben** sind:

    Messlatte           gesetzte Schwelle - Geschaeftsentscheidung, nicht meine
    Deflated Sharpe     durchgemessen, Befund 54 bis 89, alle Wege zu
    Schlechtestes Jahr  nie untersucht - fehlen 0,32 Punkte
    Parameter-Plateau   nie untersucht - 1 von 2 Nachbarn in zwei Richtungen

**Fuenfzehn Laeufe gingen an den Deflated Sharpe.** Zwei Gates daneben sind in
dieser Zeit kein einziges Mal angesehen worden, und eines liegt ueberhaupt
nicht in meiner Hand. Der Abstand in der Tabelle sagt darueber nichts: 0,32
Punkte beim Schlechtesten Jahr sind eine Eigenschaft der Kapitalkurve, 1,5
Punkte Jahresrendite sind eine Setzung, und beide stehen in derselben Spalte.

``research/gatelage.py`` ordnet die Hindernisse jetzt nach Art statt nach
Abstand, und ``cli stand`` schliesst mit "WORAN DIE ARBEIT LIEGT".

### Was an den beiden ungeprueften Gates steht

**Schlechtestes Jahr**: Wer zum unguenstigsten Zeitpunkt eingestiegen waere,
stuende nach zwoelf Monaten bei -10,3 % gegen erlaubte -10,0 %. Das ist eine
Eigenschaft der Kapitalkurve und keine Frage der Signalqualitaet.

**Parameter-Plateau**: Von sechs geprueften Richtungen tragen vier voll
(2 von 2 Nachbarn). Schwach sind genau zwei - "alle gemeinsam" und
``sma(period=50)``, jeweils 1 von 2. Beide betreffen dasselbe: das
50-Tage-Kernsignal. Bei zwei Nachbarn je Richtung ist "1 von 2" allerdings
eine sehr duenne Grundlage; ob dort wirklich eine Nadelspitze steht oder die
Aufloesung zu grob ist, ist offen.

### Was das nicht ist

Kein Fortschritt an einem Gate. Die Zahlen sind unveraendert, und keine
Schwelle wurde angefasst. Was sich geaendert hat, ist, dass die naechsten
Laeufe an der richtigen Stelle ansetzen koennen - und dass eine Tabelle, die
mich heute in die Irre gefuehrt hat, das nicht wieder tut.

Versuchsstand 177 unveraendert. Suchbudget 47 von 100. 1785 Tests gruen.

## Zweiundneunzig. Keine Nadelspitze, sondern eine Flanke

Befund 91 hat die vier offenen Gates sortiert und zwei benannt, an denen
Arbeit liegt: Schlechtestes Jahr und Parameter-Plateau. Beide sind in
fuenfzehn Laeufen nie angesehen worden. Dieser Lauf nimmt das Plateau.

### Warum das Gate nicht sagen kann, was es sieht

``gate_parameter_plateau`` variiert jede Stellgroesse um plus/minus 20 % und
wertet das **Minimum** ueber alle Richtungen - "ein Plateau ist man in jeder
Richtung oder gar nicht". Das ist richtig so.

Bei zwei Nachbarn je Richtung kann das Minimum aber nur 0, 0,5 oder 1,0
annehmen. Die Schwelle von 0,6 heisst damit faktisch: **alle zwoelf Nachbarn
muessen tragen.** Es gibt keine Zwischenstufe - und aus dem gemeldeten Wert
0,500 ist nicht ablesbar, ob dort eine Nadel steht oder eine Kante.

### Was die feinere Messung zeigt

Zwoelf Faktoren von 0,70 bis 1,30, Gewinn in Konto-Einheiten (Basis 958):

    Faktor            0,70  0,75  0,80  0,85  0,90  0,95  1,05  1,10  1,15  1,20
    alle gemeinsam    1216  1226  1093  1638   799  1041   591   445   229  -104
    sma(period=50)    1070   961   868  1473   788   989   575   422   260  -104
    sma(period=200)    933   932   932   932   936   955   956   956   939   939
    roc(period=90)     963   948   957   926   953   955   962   958   957   957
    rsi(period=14)     964   964   964   964   962   962  1028  1028  1028  1025
    Vola-Fenster       772   796   802   877   681  1094  1020  1034   991   964

**Es ist keine Nadelspitze.** Die Strategie ist von 0,70 bis 1,15 durchgehend
profitabel - Perioden von 35 bis 57 Tagen, ein Bereich von 45 Prozentpunkten.
Was das Gate trifft, ist eine **Kante bei +20 %**, hinter der es ins Negative
faellt.

Und nur eine Stellgroesse wirkt: ``sma(period=50)``. "Alle gemeinsam" hat
praktisch denselben Verlauf; die uebrigen vier aendern den Gewinn um 3 bis
7 %. Dass die Strategie gegen sie unempfindlich ist, sagt nichts ueber ihre
Robustheit - diese Regler sind schlicht nicht angeschlossen. Genau deshalb
wertet das Gate das Minimum, und genau deshalb ist das richtig.

### Die unangenehme Haelfte, und warum daraus nichts folgt

Der Bestand sitzt nicht auf dem Gipfel, sondern auf der abfallenden Flanke:
Bei Faktor 0,85 steht der Gewinn bei 1638 gegen 958 bei 1,00. Das sind 680
mehr - es sieht aus, als waere ``sma(42)`` der bessere Parameter.

**Er ist es nicht, jedenfalls nicht belegt.** Gegen die Trendlinie gerechnet
liegt der Punkt +2,39 Reststreuungen darueber; bei zwoelf gemessenen Punkten
erwartet man ohnehin 1,67, und der Abstand entspricht z = 1,21. Dieselbe Lage
wie das beste Paar in Befund 86 (3,585 gegen 3,549): Ein Maximum knapp ueber
dem Erwartungswert ist der Normalfall, kein Fund.

Dazu kaeme, dass zwoelf Werte durchzuprobieren und den besten zu nehmen genau
die Ueberanpassung ist, gegen die dieses Gate schuetzt.

### Zwei eigene Fehlversuche auf dem Weg dorthin

Die Pruefung "ist der beste Punkt belegt?" habe ich dreimal geschrieben. Der
erste Anlauf verglich ihn mit dem **mittleren Nachbarsprung** (267) - zu
schwach, und er haette den Punkt durchgewinkt. Der zweite addierte einen
erfundenen Sicherheitsabstand von einer halben Reststreuung, damit das
Ergebnis passt; das ist genau die Willkuer, die hier nichts zu suchen hat.

Der dritte rechnet den Abstand in Einheiten der **Streuung des Maximums**,
und die laesst sich aus der Zahl der Punkte bestimmen. Kein Regler, keine
Wahl.

### Was daraus folgt

1. **Das Gate scheitert zu Recht.** Bei +20 % kippt der Kandidat ins Negative,
   und Robustheit in beide Richtungen ist die Anforderung. Nichts an dieser
   Schwelle wurde angefasst.
2. **Die Botschaft "Nadelspitze" ist trotzdem falsch** und fuehrt in dieselbe
   Richtung wie die Messlatte-Zeile aus Befund 91: Sie klingt nach einer
   Diagnose und ist eine Fehldeutung. Der Kandidat steht am Rand eines
   breiten Gebiets, nicht auf einem Zufallstreffer.
3. **Aus der Landschaft ist kein Parameter abzulesen.** Wer es doch tut, zahlt
   Versuche fuer ein Rauschen.

``research/plateaubild.py`` und ``cli plateaubild`` rechnen das jederzeit
nach. Ein Kandidat, dessen Parameter alle wirkungslos sind, wird dabei
ausdruecklich **nicht** als robust gemeldet - das waere die gefaehrlichste
Verwechslung dieses Tests.

Versuchsstand 177 unveraendert - variiert wurden die Parameter eines
vorhandenen Kandidaten, nichts ausgewaehlt und nichts verstellt. Suchbudget
47 von 100. 1800 Tests gruen.

## Dreiundneunzig. Das schlechteste Jahr ist der Baerenmarkt 2022

Befund 91 hat zwei Gates benannt, an denen Arbeit liegt. Befund 92 nahm das
Parameter-Plateau, dieser Lauf nimmt das zweite: **Schlechtestes Jahr**,
-10,32 % gegen eine Grenze von -10,00 %.

### Der Fehlschluss, den ich zuerst hatte

Die Zahl ist das Minimum ueber alle rollierenden Zwoelfmonatsfenster - auf 93
Testmonaten sind das 2465 Stueck. Die Verteilung:

    Minimum        -10,32 %      Median         +11,51 %
    1. Perzentil    -6,54 %      Maximum        +69,10 %

**Nur 2 von 2465 Fenstern liegen unter -10 %** (0,1 %). Meine erste Lesart
war entsprechend: ein Ausreisser, den man nicht ueberbewerten sollte.

Das ist falsch, und zwar aus demselben Grund wie in Befund 88. Die 2465
Fenster sind keine 2465 Beobachtungen - sie ueberlappen sich zu 99,7 %. In 93
Testmonaten stecken **7,7 unabhaengige Jahresperioden**. Betroffen ist eine
von acht, nicht eine von 2465.

Dass es ein Ereignis ist und keine Streuung, zeigt die Lage: Alle Fenster
unter -5 % starten zwischen dem 14.10.2021 und dem 08.01.2022 - ein
zusammenhaengender Block von knapp drei Monaten.

### Was dort wirklich steht

Das schlechteste Fenster laeuft vom **08.11.2021 bis 08.11.2022** - vom
Allzeithoch bis nach dem FTX-Zusammenbruch. Im selben Fenster:

    Bestand      -10,3 %
    BTC halten   -72,5 %
    ETH halten   -72,3 %

Faktor sieben Daempfung. Das klingt nach einem Argument gegen das Gate und
ist keins: Ob die Strategie besser war als der Markt, prueft die **Messlatte**
- dort ist sie um das 3,8-fache besser (Befund 91). Dieses Gate fragt etwas
anderes: ob jemand das Jahr durchgehalten haette. Wer nach zwoelf Monaten
zweistellig im Minus steht, hoert auf, unabhaengig davon, wie der Markt lief.

Die Grenze von -10 % liegt bewusst innerhalb des Kill-Switch von 15 %.

### Der Kreis schliesst sich zu Befund 85

Dort wurde gemessen, dass der Bestand im Abwaertsmarkt nichts verdient:
Sharpe je Trade **-0,0450** gegen +0,3473 im Aufwaertsmarkt. Hier steht
dieselbe Eigenschaft in einer anderen Einheit.

Das schlechteste Jahr ist damit kein statistisches Artefakt, sondern die
Kehrseite dessen, was der Kandidat ist: **eine Aufwaertsmarkt-Strategie.**
Der naechste Zyklus bringt dieselbe Phase wieder, und dann wieder rund -10 %.

Damit haengen zwei der vier offenen Gates am selben Befund. Der Deflated
Sharpe fehlt, weil die Guete nicht reicht - und der Weg dorthin waere ein
zweites, gegenlaeufiges Bein (Befund 73 bis 86). Das schlechteste Jahr fehlt,
weil es im Abwaertsmarkt keinen Ertrag gibt. **Es ist dieselbe Luecke.**

### Ein eigener Fehler beim Testschreiben

Die Testkurve fuer die Duerre legte den Einbruch zuerst auf eine von 1,0 auf
3,0 steigende Gerade. Der Anstieg ueber ein Jahr betraegt dort +14 % und hat
den Einbruch von 12 % vollstaendig aufgezehrt - die Kurve hatte gar keine
Duerre, und der Test schlug fehl. Jetzt liegt der Einbruch auf einer flachen
Kurve, und der Grund steht im Docstring.

### Was das ist und was nicht

**Keine Lockerung.** Die Grenze wurde nicht angefasst, und die Daempfung ist
ausdruecklich kein Argument. ``research/duerre.py`` und ``cli duerre`` ordnen
die Zahl ein - mehr nicht.

Was sich geaendert hat: Die zwei verbleibenden Gates in meiner Hand sind
nicht zwei Probleme, sondern eines. Wer den Abwaertsmarkt loest, loest beide.

Versuchsstand 177 unveraendert - zerlegt wurde eine Kapitalkurve, die ohnehin
gerechnet wird. Suchbudget 47 von 100. 1815 Tests gruen.

## Vierundneunzig. Kein Verbund trifft das Rechteck - 231 Kombinationen geprueft

Befund 93 endete mit einem Schluss: Der Deflated Sharpe und das schlechteste
Jahr haengen am selben Befund - der Bestand verdient im Abwaertsmarkt nichts.
Daraus folgt eine Frage, die nie gestellt wurde: **Welche vorhandene Regel
wuerde das schlechteste Jahr retten, und rettet dieselbe auch den Rest?**

### Der erste Blick, und warum er nicht reicht

Verbund aus Bestand und Partner, halbes Gewicht, schlechtestes Jahr der
gemeinsamen Kurve. **Zehn von dreizehn Regeln heben es ueber -10 %.** Das
sieht nach einem Durchbruch aus.

Er ist keiner, und der Grund steht in derselben Rechnung: Halbes Gewicht
halbiert auch die Rendite. Und die Rendite ist bereits das Problem - der
Bestand steht bei 13,47 % gegen geforderte 15 %.

    Partner (halbes Gewicht)         schl.Jahr    CAGR   Rueckgang
    Donchian-Ausbruch 55/20             -10,77   15,30       12,59
    Trend beide Richtungen               -5,08    9,52        8,93
    Trend-Beteiligung (fair ger.)        -6,50   10,25        7,32
    Vola-Ziel, kurzes Messfenster        -6,98    9,63        7,14
    Trend-Beteiligung voller Einsatz     -7,79   10,77        9,75
    Momentum-Beteiligung 90 Tage        -14,65    9,39       14,81
    Trend-Beteiligung 50 Tage           -19,91   14,84       20,27

Das Muster ist eindeutig: **Sechs Partner retten Risiko und drueecken die
Rendite auf 9 bis 11 %. Der einzige, der die Rendite hebt, reisst beide
Risikoschwellen.** Alle drei zugleich: null von elf.

### Die Gewichtung als Ausweg - auch nicht

Halbes Gewicht ist eine Wahl. Also alle Gewichte von 0,00 bis 1,00 in
Schritten von 0,05, fuer jeden Partner:

    11 Partner x 21 Gewichte = 231 Kombinationen, **kein einziger Treffer.**

Am naechsten kommt der Donchian-Verbund: Rendite 15,30 %, Rueckgang 12,59 %,
schlechtestes Jahr -10,77 % - zusammen **1,37 Punkte** zu wenig ueber die drei
Grenzen.

### Was das erweitert

``cli vereinbar`` misst diesen Konflikt seit Befund 57 entlang eines
**Groessenreglers**: Geht die Kurve durch das erlaubte Rechteck? Zehn
Stellungen, kein Treffer, am naechsten 0,82 Punkte.

Jetzt kommt eine zweite Achse dazu, und sie fuehrt zum selben Ergebnis. Der
Konflikt ist damit nicht mehr eine Eigenschaft **einer** Kurve, sondern des
ganzen vorhandenen Materials: weder durch Skalieren noch durch Mischen
erreichbar.

``research/vereinbar.py`` traegt deshalb jetzt beides. Erweitert wurde das
vorhandene Modul und kein zweites gebaut - der Reglerfall und der Mischfall
haetten sonst zwei Umsetzungen derselben drei Kennzahlen, und genau das ist
in diesem Projekt schon fuenfmal auseinandergelaufen.

### Warum die dritte Schwelle dazugehoert

Mit zwei Schwellen ist die Lage nicht zu beurteilen. Bei Gewicht 0,5 mit
'Trend beide Richtungen' sind Rueckgang **und** schlechtestes Jahr erfuellt -
wer nur diese beiden prueft, sieht einen Treffer. Erst die Rendite zeigt, dass
dort 9,52 % stehen.

Eine Beimischung senkt Rendite und Risiko zugleich. Ob dabei etwas uebrig
bleibt, entscheidet sich an allen drei Grenzen, nicht an zweien.

### Zwei Dinge, die beim Messen fast schiefgegangen waeren

**Die Groessenlogik.** Der erste Durchlauf normalisierte alle Beine auf
``vola_ziel 19.3`` - richtig fuer den Vergleich zwischen Partnern, aber der
Bestand stand dann bei -13,15 % statt der -10,32 % des Gates. Die
Verbundzahlen waeren gegen einen anderen Bestand gerechnet gewesen als den,
um den es geht. Der zweite Durchlauf laesst jedem Genom seine eigene
Groessenlogik, und der Bestand trifft das Gate auf die zweite Stelle.

**Das Mischen.** Gemischt werden die Periodenrenditen, nicht die Kurven. Zwei
Kapitalkurven zu mitteln zaehlt den Zinseszins zweimal; ein Portfolio verteilt
das Kapital und teilt sich die Renditen. Als Test steht die Probe da: Zwei
identische Beine muessen in jeder Mischung dieselbe Kurve ergeben.

### Was daraus folgt

1. **Der Verbundweg ist auch fuer die Risikogates zu.** Befund 86 hatte ihn
   fuer den Deflated Sharpe geschlossen (bestes Paar unter dem Nullmedian),
   jetzt gilt dasselbe fuer Rendite, Rueckgang und schlechtestes Jahr
   zusammen.
2. **Der Konflikt liegt an den Schwellen, nicht an der Strategie.** Weder
   Skalieren noch Mischen erreicht das Rechteck. Die Aufloesung ist eine
   wirtschaftliche Entscheidung und liegt beim Nutzer - so steht es seit
   jeher in ``gates.py``.
3. Ein Treffer waere auch kein Betriebspunkt gewesen. 231 Kombinationen
   durchzuprobieren und die beste zu nehmen ist genau die Anpassung, gegen
   die die Zulassungsstrecke gebaut ist.

Versuchsstand 177 unveraendert - gemischt wurden Kapitalkurven, die schon
gerechnet waren, und kein Kandidat ausgewaehlt. Suchbudget 47 von 100. 1824
Tests gruen.

## Fuenfundneunzig. Ein bestandenes Gate, das am Kontostand haengt

Befund 94 legte eine Reglertabelle vor. Beim Nachrechnen fiel etwas auf, das
nie jemand benannt hatte: Das Verhaeltnis Rendite/Rueckgang **ruckelt**.

    Vola-Ziel   Rendite   Rueckgang   Verhaeltnis
        14        9,47       7,75        1,223
        16       10,98       8,46        1,298
        19,3     13,47      10,64        1,266
        20,5     14,11      11,29        1,250
        21       14,39      12,50        1,152
        22       15,16      12,82        1,183
        32       22,30      18,18        1,227

Ein Groessenregler skaliert jede Position mit demselben Faktor. Rendite und
Rueckgang muessen also beide mit ihm wachsen, und ihr Verhaeltnis darf sich
glatt bewegen - nicht sprunghaft. Zwischen 20,5 und 21 faellt es um 0,098,
zwischen 21 und 22 steigt es wieder. Das ist kein Verlauf, das ist ein Zaun.

### Der erste Vergleich: gemessen gegen gestreckt

Die Gegenrechnung dazu braucht keinen neuen Backtest. Die Kapitalkurve bei
19,3 liefert Periodenrenditen; mit dem Faktor k = Stellung/19,3
multipliziert entsteht die Kurve, die ein **wirklich proportionaler** Regler
ergaebe.

    Stellung      k    Rueckgang gemessen   gestreckt   Verhaeltnis ist / soll
        19,3   1,000        10,64             10,64          1,266 / 1,266
        20,5   1,062        11,29             11,27          1,250 / 1,272
        21     1,088        12,50             11,53          1,152 / 1,274
        25     1,295        14,78             13,61          1,166 / 1,294
        32     1,658        18,18             17,15          1,227 / 1,329

Zwei Dinge stehen da. Erstens: Unter reiner Streckung **steigt** das
Verhaeltnis mit der Groesse, es faellt nicht. Die Vorstellung, hoher Hebel
zahle sich wegen Volatilitaets-Drag nicht aus, trifft auf diese Groessen-
ordnung nicht zu - gerechnet, nicht vermutet. Zweitens: Die Abweichung sitzt
**ausschliesslich im Rueckgang**. Die Rendite folgt der Streckung auf 0,3
Punkte genau, der Rueckgang laeuft ihr um bis zu 1,5 Punkte davon.

Der Einbruch ist dabei immer derselbe: Gipfel bei Index 1177, Tal bei 1600 -
der Baerenmarkt aus Befund 93. Es wechselt also nicht die Episode, sondern es
passiert innerhalb derselben etwas anderes als eine Streckung.

### Zwei Verdaechtige, beide entlastet

**Die Verlustgrenzen des Risiko-Offiziers.** Im Protokoll haeuften sich
``risk.wochenlimit``-Meldungen, und zwar mehr bei groesserer Stellung. Der
Verdacht lag nahe: Die Grenze feuert im Einbruch, nimmt die Strategie aus den
Gewinnern, die den Fall abgefedert haetten, und vertieft ihn dadurch.

Gegenprobe: derselbe Lauf mit ``enforce_risk_limits=False``. Die Rueckgaenge
sind **auf die zweite Stelle identisch** - 7,75 / 8,46 / 10,64 / 11,29 /
12,50 / 12,76 / 12,82 / 14,78 / 16,65 / 18,18. Die Grenzen kosten Rendite
(13,31 % statt 13,47 %) und bewegen den Rueckgang nicht. Verdacht erledigt.

**Der Deckel in der Groessensteuerung.** ``_compute_fractions`` schliesst mit
``np.clip(anteil, 0.0, sizing.fraction)``, und der Bestand hat
``fraction = 3.0``. Griffe der Deckel in ruhigen Phasen, ginge jede Erhoehung
des Vola-Ziels ueberproportional in die stuermischen - genau die Asymmetrie,
die hier zu sehen ist.

Gegenprobe: Anteil an allen Balken nachgerechnet. **Der Deckel greift an
0,0 % der Balken.** Der mittlere Anteil waechst mit exakt 0,0196 je Punkt
Vola-Ziel, ueber alle zehn Stufen gleich. Auch erledigt.

### Die Ursache: Bybits Mengenschritt

Bybit handelt BTC in Schritten von **0,001** und ETH in Schritten von
**0,01**, und ``sizing.py`` rundet die berechnete Menge darauf **ab**. Bei
500 Euro Konto und rund 38 % Kapitalanteil steht auf BTC eine Position von
etwa 190 Euro - bei 60.000 USD je BTC sind das drei Mengenschritte.

**Der Groessenregler hat dort eine Aufloesung von einem Drittel der
Position.** Das ist kein Regler mehr, das ist eine Treppe.

Was davon uebrig bleibt, laesst sich ohne Backtest beziffern - gerundete
Menge geteilt durch berechnete, gemittelt ueber alle Balken:

    BTC bei    500 Euro    0,893      ruhige Haelfte 0,900   Sturm 0,885
    BTC bei 100.000 Euro   0,999      ruhige Haelfte 0,999   Sturm 0,999
    ETH bei    500 Euro    0,936      ruhige Haelfte 0,943   Sturm 0,930
    ETH bei 100.000 Euro   1,000      ruhige Haelfte 1,000   Sturm 1,000

Elf Prozent der geplanten BTC-Position kommen bei 500 Euro gar nicht
zustande. Und die Verstuemmelung ist **schief**: Das Vola-Ziel macht die
Position im Sturm klein, und kleine Positionen trifft das Abrunden am
haertesten. Das kleine Konto bekommt damit einen zweiten, unbeabsichtigten
Vola-Filter geschenkt - und der wirkt genau im Baerenmarkt 2022.

### Was das mit dem Gate macht

Betriebspunkt des Bestands, sonst nichts veraendert, nur der Kontostand:

    Konto        Rendite   Rueckgang   Verhaeltnis   Gate (<= 12 %)
       300 EUR    12,61 %      9,92 %       1,271    haelt
       400 EUR    13,21 %     10,29 %       1,284    haelt
       500 EUR    13,47 %     10,64 %       1,266    haelt
       750 EUR    13,78 %     11,61 %       1,186    haelt
     1.000 EUR    13,50 %     11,84 %       1,140    haelt
     1.500 EUR    13,79 %     12,36 %       1,116    **reisst**
     5.000 EUR    13,81 %     12,70 %       1,087    reisst
    50.000 EUR    13,88 %     12,94 %       1,073    reisst
   100.000 EUR    13,89 %     12,95 %       1,072    reisst

Der Rueckgang waechst mit **jeder** Sprosse - kein Rauschen, ein Verlauf. Er
wandert 3,03 Punkte, die Rendite nur 1,27. Es ist also nicht "kleines Konto,
kleine Zahlen": Die Rundung trifft den Rueckgang und die Rendite fast nicht.

**Das Rueckgang-Gate haelt nur unterhalb von rund 1.150 Euro.**

### Der Beleg, dass es wirklich die Rundung ist

Zwei Eingriffe, die nichts miteinander gemein haben ausser dem, was sie
beseitigen:

1. **Feiner Mengenschritt** - dieselben 500 Euro, aber 1e-8 statt 0,001 BTC.
2. **Grosses Konto** - Bybits echter Schritt, aber 100.000 Euro.

Ergebnis **12,96 %** und **12,95 %**. Zwei unabhaengige Wege, 0,01 Punkte
auseinander, und beide 2,3 Punkte von der Ausgangsmessung entfernt. Der
erklaerte Anteil betraegt 100 %. Damit ist die Mengenrundung nicht eine
plausible Erklaerung, sondern die gemessene.

### Und was das fuer Befund 94 bedeutet

Ohne die Rundung ist die Reglerkurve glatt, und das Verhaeltnis steigt
monoton - so, wie es soll:

    Vola-Ziel   Rendite   Rueckgang   Verhaeltnis
        14       10,15       9,62        1,055
        19,3     13,89      12,96        1,072
        21       15,07      14,00        1,077
        22       15,77      14,60        1,080
        32       22,60      20,35        1,110

Das Ruckeln aus Befund 94 war die Treppe, kein Marktbefund. Der **Schluss**
von Befund 94 bleibt aber stehen, und zwar haerter als vorher: Das
Verhaeltnis liegt jetzt sauber bei 1,07 bis 1,11 - gefordert sind 15/12 =
**1,250**. Zwischen 16 und 19,3 interpoliert liegt die Grenze des
Rueckgang-Gates bei Vola-Ziel 17,8, und dort stehen rund **12,8 % Rendite**.
Die Decke ist damit beziffert: 12,8 % gegen geforderte 15 %.

Vorher liess die zackige Tabelle offen, ob zwischen zwei Stufen noch ein
Punkt liegt, der beide Schwellen haelt. Jetzt nicht mehr: Die Kurve ist
glatt, monoton, und sie laeuft am Rechteck vorbei.

### Was daraus folgt

1. **Eines der acht bestandenen Gates haelt nur, solange das Konto klein
   bleibt.** Wer von 500 auf 2.000 Euro aufstockt, aendert an der Strategie
   nichts und reisst es trotzdem. Das gehoert in die Bilanz des Kandidaten,
   nicht in eine Fussnote.
2. **Das ist keine Empfehlung, klein zu bleiben, damit das Gate haelt.** Das
   waere dieselbe Sorte Anpassung, gegen die die ganze Zulassungsstrecke
   gebaut ist. Der Betriebspunkt wird nicht nachgezogen, und die 500 Euro
   werden nicht zur Begruendung umgedeutet.
3. **Der Groessenregler ist als Weg zum Rechteck endgueltig zu.** Nicht
   knapp daneben, sondern um den Faktor 1,17 im Verhaeltnis.
4. Der Punkt "Kontogroesse" stand in ``stand.py`` schon als offene
   Entscheidung - mit der Mindestmenge als Begruendung, 51 % der Trades
   betroffen. Er ist jetzt beziffert und um die Folge fuer das Gate
   ergaenzt, statt einen zweiten Eintrag daneben zu setzen.

### Was gebaut wurde

``research/koernung.py`` mit ``Kontostufe`` und ``Koernung``. Die
entscheidenden Stellen:

* ``gegenstueck`` - die Feinmessung wird gegen die Sprosse mit **demselben**
  Kontostand gerechnet, nicht gegen die kleinste. Sonst stuende im Zaehler
  zusaetzlich der Kontounterschied.
* ``koernung_erklaert_es`` - wahr nur, wenn beide Gegenproben einander naeher
  treffen als ``UNERHEBLICH`` = 0,05 Punkte. Die Zahl ist nicht gegriffen:
  Die Gates entscheiden gegen runde Grenzen und werden auf zwei Stellen
  berichtet, darunter kann kein Urteil kippen.
* ``umsetzung`` - beziffert die Rundung ohne Backtest.
* ``steigt_durchgehend`` - Monotonie als Gegenprobe gegen Rauschen.

``cli koernung`` faehrt die Leiter, die Gegenprobe und die Umsetzungszahlen.
17 Tests in ``tests/test_koernung.py``; der tragende ist
``test_beide_gegenproben_treffen_einander``, weil daran haengt, ob die
Ursache belegt oder nur plausibel ist.

Versuchsstand 177 unveraendert. Der Zaehler korrigiert das Testen vieler
**Strategie**-Hypothesen; hier ist die Strategie in jeder Zeile dieselbe, und
ausgewaehlt wurde nichts. Suchbudget 47 von 100. 1841 Tests gruen.

## Sechsundneunzig. Zwei Gates wandern, neun stehen still

Befund 95 hat zwei Kennzahlen ueber die Kontoleiter gefahren - Rendite und
Rueckgang - und die uebrigen neun Gates nicht angesehen. Dass sie unberuehrt
bleiben, waere eine Annahme gewesen. Der Deflated Sharpe haengt am Sharpe je
Trade, und die Mengenrundung veraendert **jede einzelne** Trade-Rendite.

Also alle elf, ueber dieselbe Leiter, mit demselben Versuchsstand (177) in
jeder Zeile - sonst verglichen die Spalten zwei verschiedene Huerden:

    Gate                      300      500    1.000    1.500    2.000  100.000
    Stichprobengroesse     + 2097   + 2163   + 2163   + 2163   + 2163   + 2163
    Messlatte              -150,9   -166,1   -166,6   -172,1   -171,2   -173,8
    Out-of-Sample-Sharpe   + 1,454  + 1,473  + 1,440  + 1,441  + 1,437  + 1,426
    Drawdown               + 9,92   + 10,64  + 11,84  - 12,36  - 12,56  - 12,95
    Schlechtestes Jahr     - 9,60   - 10,32  - 11,51  - 12,03  - 12,23  - 12,61
    Bestaendigkeit         + 0,533  + 0,533  + 0,533  + 0,533  + 0,533  + 0,533
    Monte-Carlo            + 9,91   + 10,27  + 10,79  + 10,95  + 10,97  + 11,34
    Regime-Aufteilung      + 3,975  + 4,152  + 3,965  + 3,903  + 3,903  + 3,886
    Deflated Sharpe        - 0,772  - 0,783  - 0,775  - 0,786  - 0,782  - 0,778
    Kosten-Stress          + 579    + 943    + 1483   + 2245   + 2990   +151511
    Parameter-Plateau      - 0,500  - 0,500  - 0,500  - 0,500  - 0,500  - 0,500
    ------------------------------------------------------------------------
    bestanden                 8/11     7/11     7/11     6/11     6/11     6/11

### Was da steht

**Genau zwei Gates aendern ihr Urteil**, und es ist kein Zufallspaar: Es sind
die beiden Risikomasse auf der Kapitalkurve. Beide messen dieselbe Groesse in
verschiedenen Einheiten - den Verlust in einem zusammenhaengenden Fenster -
und beide werden von der Mengenrundung geschoent, solange das Konto klein ist.

**Neun stehen still.** Zwei davon wandern zwar im Wert, ohne zu kippen:
Monte-Carlo laeuft von 9,91 auf 11,34 gegen eine Schwelle von 15, und
Kosten-Stress ist eine absolute Eurogroesse und skaliert deshalb trivial mit
dem Konto. Die uebrigen sieben ruehren sich kaum.

### Das wichtigste Nein

**Der Deflated Sharpe bewegt sich um 0,014** - von 0,772 auf 0,786 und zurueck
auf 0,778. Die Huerde liegt 0,167 entfernt. Waere er betroffen gewesen, gaebe
es dort einen Weg: sauberere Trade-Renditen, weniger Rundungsrauschen, hoehere
Guete je Trade. Es gibt ihn nicht. **Die Koernung ist kein Weg zum haertesten
Gate**, und das ist ein Ergebnis, kein Scheitern - es erspart die naechste
Runde daran.

### Die Falle, die dieser Befund aufstellt

Bei 300 Euro halten **8 von 11** - mehr als irgendwo sonst auf der Leiter, und
mehr als die 7, die ``cli stand`` meldet. Das sieht aus wie ein Fortschritt.

Es ist keiner. Es ist dieselbe Strategie mit einer groeberen Treppe. Einen
Kontostand danach auszuwaehlen, wie viele Gates dort halten, ist genau
dieselbe Anpassung wie das Nachziehen eines Betriebspunktes - nur an einer
Stelle, an der bisher niemand nachgesehen hat, weil das Konto nicht wie eine
Stellschraube der Strategie aussieht.

Deshalb heisst die Eigenschaft im Modul ``hoechster_stand`` und nicht
``bester``: Sie ist eine Warnung, kein Ziel.

**Die Zahl, die nicht am Kontostand haengt, steht am oberen Ende: 6 von 11.**

### Was daraus folgt

1. **Die Bilanz des Bestands ist 6 von 11, nicht 7.** Die 7 gelten fuer 500
   Euro und nur dort. Beide offenen Risikogates - Rueckgang und schlechtestes
   Jahr - fallen bei jedem Konto ueber rund 1.150 Euro durch.
2. **Befund 93 bleibt richtig, wird aber schaerfer.** Dort stand, das
   schlechteste Jahr sei die Kehrseite einer Aufwaertsmarkt-Strategie und
   fehle um 0,32 Punkte. Ohne den Rundungseffekt fehlen **2,61 Punkte**
   (-12,61 gegen -10,00). Die Deutung stimmt, die Groessenordnung war zu
   milde.
3. **Der Deflated Sharpe ist auch von hier aus nicht erreichbar.** Ein
   weiterer geschlossener Weg, gemessen statt vermutet.
4. Was gemessen wurde, ist eine Eigenschaft der **Messung**, nicht der
   Strategie. Die Gates werden nicht geaendert - weder gelockert noch
   verschaerft. Aufgeschrieben wird, dass zwei von ihnen eine Zahl mitmessen,
   die mit der Strategie nichts zu tun hat.

### Was gebaut wurde

``research/koernung.py`` um ``Gatewert``, ``Gatelauf`` und ``Gateleiter``
erweitert - **erweitert und nicht danebengestellt**, weil es dieselbe Frage
in derselben Sache ist. Die tragenden Stellen:

* ``namen`` nimmt nur Gates, die auf **jeder** Sprosse gelaufen sind. Sonst
  ginge ein Gate, das nur einmal lief, als "fest" durch - eine Aussage ueber
  eine einzige Messung.
* ``hoechster_stand`` ist als Warnung dokumentiert, nicht als Betriebspunkt.
* ``spanne(name)`` misst die Wanderung des **Werts**, auch ohne Urteilswechsel
  - sonst waere "Deflated Sharpe steht still" nur eine Aussage ueber ein
  Vorzeichen.

``cli koernung --gates`` faehrt die Leiter mit allen elf Gates; ohne die Flagge
bleibt es beim schnellen Lauf. Acht neue Tests, tragend ist
``test_genau_zwei_gates_wandern``; die Gegenprobe dazu ist
``test_das_haerteste_gate_steht_still``.

Versuchsstand 177 unveraendert und in jeder Spalte derselbe. Suchbudget 47 von
100. 1849 Tests gruen.

## Siebenundneunzig. Dieselbe Kollision wie beim Intervall, nur teurer

Befund 96 hat gemessen, dass zwei der elf Gates ihr Urteil aendern, wenn
allein der Kontostand sich aendert. Damit steht in ``state/leaderboard.json``
seit dem 14. August eine Zahl, deren Herkunft niemand mehr nachvollziehen
kann:

    "genome_id": "68cfe95c9a365ef2",
    "gates_bestanden": 6,
    "max_drawdown_pct": 10.64,

Die 10,64 gelten fuer 500 EUR. Bei 2.000 EUR waeren es 12,56 - und
``gates_bestanden`` waere eins niedriger. In der Datei steht nicht, welches
von beidem gemeint ist.

### Warum das genau der Fehler von damals ist

``Entry.intervall`` traegt seinen eigenen Grund im Docstring:

    *"Es fehlte, und das war eine stille Kollision. Die Liste ist nach
    genome_id geschluesselt, und dieselbe Regel auf Tageskerzen und auf
    Viertelstunden hat dieselbe ID. Zwei solche Ergebnisse konkurrierten
    deshalb um denselben Platz, und das schlechtere verschwand - obwohl es
    gar nicht dasselbe gemessen hatte."*

Wort fuer Wort dieselbe Lage. Der Kontostand ist kein Feld des Genoms, taucht
in der ``genome_id`` nicht auf, und veraendert trotzdem zwei Gate-Urteile. Ein
Lauf mit 2.000 EUR und ein Lauf mit 500 EUR konkurrieren um denselben Platz -
und das schmeichelhaftere gewinnt, weil ``besser_als`` mehr bestandene Gates
sieht und sonst nichts.

**Der Unterschied zum Intervall:** Beim Intervall faellt die Verwechslung
frueher oder spaeter auf, weil die Zahlen wild auseinanderliegen. Hier sind es
ein Gate und knapp zwei Punkte Rueckgang. Das sieht wie Rauschen aus und ist
keins.

### Was gebaut wurde

``Entry.kapital``, nach demselben Muster wie ``intervall``:

* ``vergleichbar_mit`` verlangt jetzt **beides** - gleiche Kerzenlaenge und
  gleiches Konto. Ein Test sichert ab, dass die zweite Bedingung die erste
  nicht aufweicht.
* ``0.0`` heisst "unbekannt", nicht "null Euro". Ohne diese Ausnahme wuerde
  kein Eintrag aus der Zeit davor je wieder abgeloest, und die Liste fror an
  dieser Stelle ein - derselbe Ausweg, den das Intervall mit dem leeren String
  nimmt.
* ``Leaderboard.kontostaende`` nennt die verschiedenen Staende. Sind es mehr
  als einer, warnt die Tabelle: Die Gate-Spalten stehen dann nebeneinander,
  meinen aber nicht dasselbe.
* Die Konto-Spalte erscheint erst, wenn ein Eintrag sie mitbringt. Sonst
  stuende in einer Liste aus Laeufen vor Befund 96 eine Spalte voller Striche.

``_startkapital(configs)`` liest die Zahl **aus den Konfigurationen des
Laufs**, statt sie neben dem Aufruf noch einmal hinzuschreiben. Eine zweite
Quelle waere genau die Stelle, an der Eintrag und Lauf auseinanderlaufen - in
diesem Projekt schon fuenfmal geschehen. Kommt je Bein ein anderes Kapital
heraus, gibt es keine Zahl fuer die Liste, und dann steht dort 0.0 statt der
ersten, die passt.

### Was das nicht ist

**Keine Aenderung an den Gates.** Keine Schwelle wurde angefasst, kein Urteil
gedreht, kein Eintrag nachtraeglich korrigiert. Die 40 Eintraege ohne
Kontoangabe behalten ihre Zahlen; sie tragen jetzt nur ein "?" statt eines
stillen Anspruchs auf Vergleichbarkeit.

**Und keine Entscheidung darueber, welches Konto das richtige ist.** Ob die
Zulassung kuenftig auf 500 EUR oder auf einem Konto ohne Rundungseffekt laufen
soll, ist eine Frage mit Folgen fuer jeden Vergleich zur Vergangenheit. Sie
steht als Punkt "Kontogroesse" in ``stand.py`` und gehoert dem Nutzer.

Versuchsstand 177 unveraendert - es wurde nichts gemessen, sondern etwas
aufgeschrieben, das schon gemessen war. Suchbudget 47 von 100. 1858 Tests
gruen.

## Achtundneunzig. Die Rangfolge haelt - und eine geratene Erklaerung war falsch

Nach Befund 97 blieb eine Frage offen, die schlimmer ist als alles, was die
drei Befunde davor gefunden haben: **Jeder der 45 Eintraege in der Bestenliste
ist bei 500 EUR gemessen, also durch den Rundungsfilter hindurch.** Der Filter
ist nicht neutral - er schneidet kleine Positionen staerker ab als grosse, und
wie gross die Positionen sind, ist eine Eigenschaft des Genoms.

Haengt die Rangfolge davon ab, hat die Suche nach einem verfaelschten Signal
gesteuert, und jeder Vergleich zweier Kandidaten stand auf Sand.

### Die Antwort

**Sie haengt nicht davon ab.** Alle 23 Tageskerzen-Genome des Katalogs
zweimal gemessen - Bybits Mengenschritt gegen einen feinen, sonst alles
gleich, Versuchsstand 177 in beiden Spalten:

    Genom                              Trades    grob    fein  Luecke  Gates
    Momentum-Beteiligung 90 Tage           94   25,56   27,77   +2,20   2->2
    Trend-Beteiligung 100 Tage            101   18,40   19,91   +1,51   2->2
    Trend-Beteiligung 50 Tage             142   29,16   30,03   +0,87   5->5
    Donchian-Ausbruch 55/20                55   19,45   20,27   +0,82   6->6
    Vola-Ziel, langes Messfenster          51    6,97    7,46   +0,49   7->7
    Trend-Beteiligung voller Einsatz       43   27,67   28,12   +0,46   3->3
    Trend mit Vola-Ziel 20 %               51    8,03    8,18   +0,15   8->8
    Vola-Ziel, kurzes Messfenster          51    7,78    7,90   +0,12   8->8
    Trend-Beteiligung (fair gerechnet)     46   13,54   13,65   +0,11   5->5
    Trend-Beteiligung 200 Tage             46   13,54   13,65   +0,11   5->5
    Trend mit Vola-Ziel 22 %               51    8,83    8,91   +0,08   8->8
    Bollinger-Ruecksetzer short             1    0,35    0,39   +0,04   5->5
    Trend beide Richtungen                 84   27,76   27,43   -0,32   3->3

**Von 13 handelnden Genomen aendert keines seine Zahl bestandener Gates.**

Zehn weitere Genome stehen nicht in der Tabelle: Sie handeln auf diesen Daten
gar nicht und bestehen trotzdem fuenf Gates, weil nichts schiefgehen kann, wo
nichts passiert. Sie mitzuzaehlen haette die Stabilitaetsquote von 13 auf 23
gehoben, ohne dass etwas gemessen waere - Stillstand als Stabilitaet.

### Warum der Bestand trotzdem kippt

Sein Sprung von **+2,32** Punkten ist kein Ausreisser; das groesste
Katalog-Genom liegt bei +2,20. Er ist der einzige Kandidat, dessen Rueckgang
**nahe an seiner Schwelle** steht: 10,64 % gegen 12 %. Ueberall sonst
verschiebt dieselbe Rundung eine Zahl, die weit von ihrer Grenze entfernt
liegt.

Das ist die Lehre in einem Satz: **Die Koernung dreht kein Urteil, ausser die
Zahl liegt ohnehin dicht an der Schwelle. Dort dreht sie es zuverlaessig.**

### Eine Erklaerung, die ich geraten und widerlegt habe

Mein Verdacht war der Konviktions-Faktor des Bestands. Er laeuft von
1/(1+Bonus) bis 1,0, halbiert also die Position in schwachen Setups, und
kleine Positionen trifft das Abrunden am haertesten. Das klang zwingend.

Gegenprobe mit Bonus 0, sonst unveraendert:

    mittlerer Kapitalanteil   0,165 -> 0,330   (Position verdoppelt)
    Luecke im Rueckgang       +2,32 -> +2,22   (praktisch unveraendert)

**Falsch geraten.** Die doppelte Position aendert an der Luecke nichts. Der
Verdacht steht hier, weil er sonst beim naechsten Mal wieder auftaucht.

### Und die Stelle, an der ich die eigene Lehre fast vergessen haette

Die Luecken streuen von -0,32 bis +2,20. Drei Erklaerungen dafuer geprueft,
ueber die 13 handelnden Genome:

    Hoehe des Rueckgangs   r = +0,413   t = +1,51
    Zahl der Trades        r = +0,543   t = +2,14
    Sharpe                 r = +0,115   t = +0,38

Die mittlere reisst die uebliche Schwelle |t| >= 2. Ich war einen Satz davon
entfernt, "mehr Trades, mehr Rundungen, groessere Luecke" aufzuschreiben.

**Es ist kein Beleg.** Bei drei Pruefungen reisst eine von sieben rein
zufaellig die 2,00; die Schranke liegt nach Bonferroni bei **2,39**. Genau
diese Korrektur ist das Thema des ganzen Projekts - der Versuchszaehler tut
nichts anderes, nur eine Ebene tiefer. Sie in der eigenen Auswertung zu
vergessen waere die peinlichste Stelle, an der man sie vergessen kann.

Die Zahl steht im Modul, damit jemand sie mit mehr Genomen nachpruefen kann.
Behauptet wird sie nicht.

### Was gebaut wurde

``research/rangprobe.py``:

* ``schranke(hypothesen)`` - die Bonferroni-korrigierte Schwelle. Bei einer
  Pruefung bleibt es bei 2,0, bei drei sind es 2,39, bei zehn 2,81. Sie
  waechst also, ohne ins Unerreichbare zu laufen.
* ``Zusammenhang`` traegt seine Schranke mit sich. Ein t ohne die Zahl der
  geprueften Hypothesen ist die Zahl, die zur Fehldeutung einlaedt - deshalb
  steht sie in ``__str__`` daneben.
* ``Doppel.handelt`` schliesst die stummen Genome aus.
* ``Rangprobe.spitze_wechselt`` fragt eigens nach dem ersten Platz.
  Uebereinstimmung im Mittelfeld nuetzt nichts, wenn oben ein anderer steht -
  die Liste ist dafuer da, den besten zu finden.

``cli rangprobe`` faehrt beide Laeufe und prueft die drei Erklaerungen mit der
richtigen Schranke. 15 Tests; tragend sind ``test_die_rangfolge_haelt`` und
``test_drei_hypothesen_heben_die_schranke``.

### Was daraus folgt

1. **Die Bestenliste steht nicht auf Sand.** Die Sorge aus Befund 97 ist
   gemessen und erledigt - das ist ein Ergebnis, kein Nicht-Ergebnis.
2. Der Kontostand bleibt trotzdem eine Bedingung der Messung, und
   ``Entry.kapital`` bleibt richtig. Dass die Rundung heute keine Rangfolge
   dreht, heisst nicht, dass sie es bei einem Kandidaten mit Rueckgang nahe
   12 % nicht taete - beim Bestand tut sie es ja.
3. Der Bestand ist in dieser Hinsicht kein Sonderfall, sondern ein Grenzfall.

Versuchsstand 177 unveraendert: Jedes Genom ist in beiden Spalten dasselbe,
veraendert wird der Mengenschritt, ausgewaehlt wird nichts. Suchbudget 47 von
100. 1873 Tests gruen.

## Neunundneunzig. Die pessimistische Annahme kostet nichts - gemessen, nicht gehofft

``backtest/engine.py`` sagt es im eigenen Docstring:

    *"Beruehrt eine Kerze sowohl Stop als auch Take-Profit, verraet OHLC
    nicht, was zuerst kam. Mit 1-Minuten-Daten wird die Reihenfolge exakt
    aufgeloest. Ohne sie gilt die pessimistische Annahme: erst Liquidation,
    dann Stop, dann Take-Profit."*

``cli wettbewerb`` sucht nach Minutenkerzen. Die gibt es in diesem Projekt
nicht. Vorhanden sind **Fuenfzehnminutenkerzen ab 2020-03-30** - 222.700 je
Markt, seit dem Backfill ungenutzt fuer diesen Zweck.

**Damit ist jede Zahl dieses Projekts unter der pessimistischen Annahme
entstanden, und was sie kostet, stand nirgends.**

### Das Ergebnis

Derselbe Kandidat, dieselben Daten, zweimal gerechnet:

    Lauf              Trades   Rendite  Rueckgang   Sharpe   Gates
    pessimistisch        152   13,47 %    10,64 %    1,473    7/11
    aufgeloest           152   13,47 %    10,64 %    1,473    7/11

**Bitgleich.** Nicht "fast", nicht "innerhalb der Toleranz" - identisch bis auf
die letzte gemeldete Stelle. Die Annahme kostet nichts.

### Warum das kein Messfehler ist

Genau hier liegt die Falle, und die Engine warnt selbst davor:

    *"Ohne as_unit('ns') liegen beide Seiten um Faktor 1000 auseinander -
    searchsorted findet dann nie etwas, und die Engine faellt still auf die
    pessimistische Annahme zurueck. Ein Fehler ohne Fehlermeldung."*

"Kein Unterschied" haette also auch heissen koennen: *die Feinkerzen sind nie
angekommen*. Eine Aussage ueber die Datenpipeline, verkleidet als Aussage
ueber die Strategie.

Nachgezaehlt wurde deshalb, wie oft die Engine wirklich zerlegt hat -
``Backtester._segments`` mitgezaehlt, waehrend der Lauf lief:

    Segmentaufrufe   11.300
    davon fein        9.128   (80,8 %)

Ein fein aufgeloester Tag zerfaellt in 96 Abschnitte statt in einen. Die
uebrigen 19,2 % sind Balken vor 2020-03-30, fuer die es keine Feinkerzen gibt;
dort greift die pessimistische Annahme weiter, und das ist richtig so.

### Und es gab etwas zu ordnen

Die zweite Art, wie ein Nullergebnis trivial werden kann: Haette der Bestand
gar keine Take-Profits, koennte keine Kerze beide Marken zugleich beruehren,
und Gleichheit waere eine Selbstverstaendlichkeit. Die Ausstiege verteilen
sich auf:

    signal_exit    74
    stop_loss      68
    take_profit    10

Beide mehrdeutigen Arten kommen reichlich vor. Das Ergebnis ist damit
informativ: **In neun Jahren hat keine einzige Tageskerze zugleich Stop und
Take-Profit beruehrt, waehrend eine Position offen war.**

Der Grund ist die Geometrie des Kandidaten: 4 % Stop unter dem Einstieg, die
Ziele darueber. Ein Tag, der beides schafft, muesste eine Spanne haben, die in
neun Jahren nie mit einer offenen Position zusammenfiel.

### Warum der Standard trotzdem pessimistisch bleibt

Die Verlockung waere, die Feinkerzen kuenftig immer zu nutzen. Zwei Gruende
dagegen, und beide sind Lehren aus den letzten Befunden:

1. **Vergleichbarkeit.** Alle 45 Eintraege der Bestenliste sind pessimistisch
   gerechnet. Den Fuellmodus mitten im Projekt zu wechseln erzeugt genau die
   Kollision, die Befund 97 fuer den Kontostand behoben hat - nur waere sie
   diesmal an gar keinem Feld ablesbar.
2. **Richtung.** Die pessimistische Annahme kann ein Ergebnis nur schlechter
   aussehen lassen, nie besser. Ein Haus, das lieber keine Strategie hat als
   eine, die nur im Backtest funktioniert, laesst die konservative Annahme
   stehen, solange sie nichts kostet. Und sie kostet nichts.

### Was daraus folgt

1. **Ein Verdacht weniger.** Die 10,64 % Rueckgang und die 13,47 % Rendite
   sind nicht durch eine Fuellannahme geschoent oder verschlechtert. Nach
   Befund 95, wo eine Messbedingung die Zahlen um 2,3 Punkte bewegte, war das
   nicht selbstverstaendlich.
2. **Es ist eine Probe, keine einmalige Feststellung.** Ein Kandidat mit engem
   Stop und nahem Ziel wuerde beides oft in derselben Kerze beruehren. Wer
   einen neuen ernst nimmt, faehrt ``cli aufloesung`` fuer ihn.
3. Der Weg "mit feineren Daten sieht es besser aus" ist damit zu - gemessen,
   nicht vermutet.

### Was gebaut wurde

``research/aufloesung.py`` mit zwei Wachen, ohne die ein Nullergebnis
wertlos waere:

* ``abdeckung_reicht`` - wurden die Feinkerzen ueberhaupt benutzt? Unter
  ``MINDESTQUOTE`` = 0,5 sagt die Probe nichts. Die Grenze ist gesetzt und
  nicht hergeleitet; sie steht im Modul, damit die Willkuer sichtbar ist
  statt im Code zu verschwinden.
* ``gibt_es_zu_ordnen`` - kommen zwei mehrdeutige Ausstiegsarten vor?
* ``haengt_an_der_annahme`` prueft **streng gegen null**. Eine Toleranz waere
  die falsche Frage: Es geht nicht darum, ob der Unterschied gross ist,
  sondern ob es einen gibt.

``cli aufloesung`` faehrt beide Laeufe und zaehlt die Segmentaufrufe mit. 10
Tests; tragend ist ``test_das_ergebnis_haengt_nicht_an_der_annahme``, und die
beiden Wachen haben je einen eigenen.

Versuchsstand 177 unveraendert: derselbe Kandidat, dieselben Daten, zweimal
gerechnet. Suchbudget 47 von 100. 1883 Tests gruen.

## Hundert. Der groesste Kostenblock steht auf einem Vorgabewert

Fuenf Befunde hintereinander haben Messbedingungen geprueft: die Koernung der
Mengen, alle elf Gates darueber, die Aufzeichnung, die Rangfolge, das
Fuellmodell. Vier davon endeten sauber. Dieser hier nicht.

**``data_store/funding/`` ist leer.**

### Was das heisst

Der Backtest belastet Perpetual-Positionen alle acht Stunden mit Funding, auf
den Nominalwert. Die Rate kommt aus ``FundingSchedule``, und ohne historische
Daten setzt sie ``default_rate = 0,0001`` ein - den Bybit-Basiswert, rund 11 %
im Jahr fuer eine dauerhaft gehaltene Long-Position.

Es gibt keine historischen Daten. **Jede Zahl dieses Projekts rechnet mit dem
Vorgabewert**, seit dem ersten Backtest.

### Die Zahl, die es einordnet

Am Betriebspunkt des Bestands, ueber neun Jahre:

    Handelsgebuehren     7,17 EUR
    Funding             63,79 EUR

**Das 8,9-fache.** Und 8,2 % des Bruttogewinns von 776,97 EUR.

Dieses Projekt hat ein Kosten-Stress-Gate, ein Modul ``kostenanteil.py``,
einen Befund ueber Maker- gegen Taker-Gebuehren und mehrere ueber
Ausfuehrungsqualitaet. Der groessere Kostenblock stand die ganze Zeit daneben
und wurde nie angesehen.

### Wie viel daran haengt

Derselbe Kandidat ueber eine Leiter von Saetzen, sonst alles gleich:

    Satz p.a.   Funding    Anteil   Rendite   Rueckgang   Gates
     0,0 %       0,00 EUR    0,0 %   14,83 %      9,87 %    9/11
     5,5 %      31,90 EUR    4,1 %   14,15 %     10,25 %    9/11
    11,0 %      63,79 EUR    8,2 %   13,47 %     10,64 %    7/11   <- Vorgabe
    21,9 %     127,57 EUR   16,4 %   12,13 %     11,41 %    7/11
    32,9 %     191,35 EUR   24,6 %   10,80 %     12,17 %    6/11
    54,8 %     318,46 EUR   40,9 %    8,22 %     13,68 %    3/11

Zwischen 5,5 % und 11 % kippen **zwei Gates**: Schlechtestes Jahr und
Parameter-Plateau. Zwischen 21,9 % und 32,9 % ein drittes: Drawdown. Der
Vorgabewert liegt genau am oberen Rand des ersten Sprungs.

### In welche Richtung der Fehler zeigt

``FundingSchedule`` sagt es im eigenen Docstring:

    *"Eine Strategie, die Funding ignoriert, ueberschaetzt ihre Rendite
    systematisch, und zwar besonders in Bullenmaerkten, wo die Rate meist
    positiv ist und Longs zahlen."*

Der Bestand ist eine **Long-Trendfolge**. Er ist im Markt, wenn der Trend
steigt - also genau dann, wenn Longs am meisten zahlen. Und der Vorgabewert
ist der **Basiswert**, nicht der Durchschnitt.

**Gemessen ist diese Richtung hier nicht.** Sie steht so im Docstring der
Engine, und nachpruefen liesse sie sich nur mit echten Bybit-Raten, die aus
diesem Container nicht erreichbar sind. Deshalb steht hier keine Korrektur,
sondern eine Groessenordnung: **Liegt die wahre Rate ueber der Vorgabe, steht
der Bestand schlechter da als 7 von 11 - nicht besser.**

### Die Falle, und warum sie ausdruecklich benannt gehoert

Bei 0 % stuende der Bestand auf **9 von 11**. Nur Messlatte und Deflated
Sharpe faellen dann noch durch. Das ist die beste Bilanz, die dieser Kandidat
je gezeigt hat.

Sie ist eine **Empfindlichkeit, kein Szenario.** Funding entfaellt nur im
Spot-Handel, und dort entfaellt auch der Hebel: Die Position waere durch das
Kapital gedeckelt, und die gemessenen Groessen kaemen gar nicht zustande. Die
Zeile sagt, wie viel die Annahme wiegt - nicht, was erreichbar waere.

Der Satz wird deshalb nicht auf den Wert gestellt, bei dem mehr Gates halten.
Das steht so im Modul und im Urteil, weil es sonst beim naechsten Lesen
verlockend aussieht.

### Was daraus folgt

1. **Ein neuer Punkt fuer den Nutzer**, und zwar ein grosser: ``python -m cli
   funding --von 2020-03-30`` laedt die echten Raten. Der Befehl existiert
   seit Generation vier und ist fuer diesen Zweck nie gelaufen. Er steht jetzt
   in ``stand.py`` unter BEIM_NUTZER und als eigene Entscheidung.
2. **Die 7 von 11 sind keine feste Zahl.** Sie stehen auf einer Kostenannahme,
   die um den Faktor zwei bis fuenf danebenliegen kann - in beide Richtungen,
   mit einem Docstring, der die teurere fuer wahrscheinlicher haelt.
3. Die Reihe der Messbedingungen ist damit nicht abgeschlossen, sondern hat
   den bisher groessten Fund geliefert - nach vier Befunden, die sauber
   ausgingen.

### Was gebaut wurde

``research/finanzierung.py``. Die Stellen, an denen es hart bleibt:

* ``vielfaches_der_gebuehren`` - die Zahl, die die Groessenordnung sofort
  klarmacht. 8,9 sagt mehr als "63,79 EUR".
* ``historie_vorhanden`` - ohne echte Raten ist die ganze Leiter eine Annahme,
  und das steht im **ersten Satz** des Urteils, nicht in einer Fussnote.
* Das Urteil nennt die Nullzeile ausdruecklich als Falle und schreibt dazu,
  dass der Satz nicht auf den guenstigen Wert gestellt wird.
* Die Richtung des Fehlers wird als **nicht gemessen** ausgewiesen, mit
  Quelle. Sie zu behaupten waere bequem und falsch.

``cli finanzierung`` faehrt die Leiter. 13 Tests; tragend sind
``test_funding_ist_der_groesste_kostenblock`` und
``test_die_nullzeile_wird_nicht_als_hoffnung_verkauft``.

Nebenbei: ``zahlwort`` kann jetzt bis 199. Bis eben fiel die Suche ueber 99
ausdruecklich aus, mit dem Hinweis, den Hunderterbereich zu bauen, wenn er
gebraucht wird. Er wird gebraucht.

Versuchsstand 177 unveraendert: derselbe Kandidat auf jeder Sprosse,
veraendert wird eine Kostenannahme. Suchbudget 47 von 100. 1897 Tests gruen.

## Hunderteins. Der Kosten-Stress-Test stresst den kleineren Posten

Befund 100 hat gemessen, dass Funding das 8,9-fache der Handelsgebuehren ist.
Daraus folgt sofort eine Frage an ein Gate, das seit Generation drei besteht:
**Was stresst der Kosten-Stress-Test eigentlich?**

``gate_cost_stress`` baut seine Konfiguration so:

    costs=cfg.costs.scaled(Decimal(str(t.cost_stress_factor))),
    funding=cfg.funding,

Gebuehren und Slippage werden verdoppelt. Das Funding wird **unveraendert
durchgereicht**. Und sein Docstring sagte dazu:

    *"Gebuehren und Slippage sind die einzigen Groessen im Backtest, die man
    garantiert unterschaetzt."*

Seit Befund 100 ist dieser Satz widerlegt - und stand trotzdem noch da.

### Was die Luecke wiegt

Derselbe Stresslauf mit Faktor 2, dreimal:

    ohne Stress    955,76 EUR Nettogewinn
    wie gebaut     942,87 EUR   Gebuehren und Slippage verdoppelt
    mit Funding    625,80 EUR   zusaetzlich das Funding verdoppelt

**317,06 EUR oder 34 % der Marge** fasst der Test nicht an. Der Grund ist
dieselbe Groessenordnung wie in Befund 100: Verdoppelte Gebuehren kosten rund
15 Euro, verdoppeltes Funding rund 200.

Nebenbei zeigt der Lauf noch etwas: Mit doppeltem Funding sinken auch die
Gebuehren (14,96 statt 29,06 EUR), weil das Konto langsamer waechst und die
Positionen kleiner ausfallen. Kosten wirken ueber neun Jahre auf sich selbst
zurueck.

### Was der Befund nicht ist

**Das Urteil kippt nicht.** Der Bestand bleibt auch unter dem strengeren
Stress mit 625,80 EUR deutlich im Plus, und das Gate verlangt nur einen Gewinn
ueber null. Betroffen ist die **Aussagekraft** des Gates, nicht sein Ergebnis
ueber diesen Kandidaten.

Das gehoert genannt, weil eine Luecke in einem Gate sich sonst wie ein
Durchfaller liest. ``Stresslage.urteil_kippt`` trennt beides, und beide Faelle
haben einen eigenen Test.

### Warum der Standard trotzdem steht

Die Versuchung ist gross, das Gate einfach zu verschaerfen - es waere die
sichere Richtung, und der Kandidat besteht ohnehin. Zwei Gruende dagegen, und
es sind dieselben wie in Befund 99:

1. **Vergleichbarkeit.** Alle 45 Eintraege der Bestenliste sind unter dem
   schwaecheren Stress gemessen. Eine Verschaerfung macht kuenftige Laeufe mit
   ihnen unvergleichbar - dieselbe Kollision wie beim Kontostand.
2. **Es ist eine Entscheidung, keine Messung.** Ob ein Gate mehr verlangen
   soll, faellt nicht beim Messen an. Sie steht jetzt in ``stand.py`` unter
   ENTSCHEIDUNGEN, beziffert, und gehoert dem Nutzer.

Geaendert wurde nur eines: der **Docstring**. Eine widerlegte Behauptung
weiterzutragen ist schlimmer als gar keine Erklaerung - wer das Gate liest,
soll wissen, was es auslaesst. Ein Test haelt fest, dass der alte Satz nicht
zurueckkommt.

### Was gebaut wurde

``research/finanzierung.py`` um ``Stresslage`` erweitert - **erweitert und
nicht danebengestellt**, weil es die direkte Folge derselben Messung ist. Die
Stellen, an denen es hart bleibt:

* ``urteil_kippt`` trennt "das Gate misst nicht, was es behauptet" von "der
  Kandidat faellt durch". Ohne diese Trennung waere der Befund alarmistisch.
* ``anteil_uebersehen`` beziffert die Luecke statt sie zu beschreiben.
* Das Urteil sagt in jedem Fall dazu, dass der Standard nicht angefasst wurde.

``cli finanzierung --stress`` faehrt die drei Laeufe. 6 neue Tests, darunter
einer, der den widerlegten Satz im Gate-Docstring fernhaelt.

Versuchsstand 177 unveraendert: derselbe Kandidat dreimal, veraendert wird
eine Kostenannahme. Suchbudget 47 von 100. 1903 Tests gruen.
