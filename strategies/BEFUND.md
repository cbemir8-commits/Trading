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
