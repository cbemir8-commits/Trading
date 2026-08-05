# Stand der Strategiesuche

Diese Datei haelt fest, was gemessen wurde und welche Wege damit
ausgeschlossen sind. Sie ist kein Champion - `champion.json` entsteht nur,
wenn alle elf Gates bestanden sind.

**Stand: 9 von 11. Nach 71 gepruefen Hypothesen.**

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

## Was daraus folgt

Weitere Varianten derselben Idee helfen nicht - im Gegenteil. Jede gepruefte
Hypothese hebt die Huerde des Deflated Sharpe:

    bei  59 Versuchen   noetiger Sharpe je Trade  rund 1,19
    bei 100 Versuchen                             rund 1,25
    bei 200 Versuchen                             rund 1,33

Aktuell liegt er bei 1,09. Wer weitersucht, ohne etwas strukturell anderes
zu probieren, entfernt sich vom Ziel, statt sich ihm zu naehern.

Gebraucht wird eine Ertragsquelle, die **gleichmaessiger** liefert als
Trendfolge - nicht eine weitere Trendfolge-Variante.
