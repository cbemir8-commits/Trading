# Beantwortete Auftraege des Analysten

Hier liegen die Antworten, die ``python -m cli vorschlag --datei <datei>``
gemessen hat. Eine Datei ist genau das, was ein Sprachmodell auf den Auftrag
aus ``build_prompt`` geantwortet haette - ein JSON-Array von Genom-Vorschlaegen.

Den Auftrag selbst zeigt:

    python -m cli vorschlag --auftrag

Warum das aufgehoben wird: Der Versuchszaehler steigt mit jedem gemessenen
Vorschlag, und damit die Huerde des Deflated Sharpe fuer alle kuenftigen
Kandidaten. Was einmal gekostet hat, soll nachlesbar sein - **einschliesslich
der Frage, wer geantwortet hat.**

| Datei | Herkunft | Befund |
|---|---|---|
| `2026-08-14-struktur.json` | Von mir beantwortet, nicht aus einem Modellaufruf | Nr. 53 |
| `2026-08-14-einstiegstakt.json` | Von mir beantwortet, aus der Vorgabe von Befund 55 | Nr. 56 |

> Ein Vorschlag von Hand ist keinen Deut glaubwuerdiger als einer aus einem
> Modell. Er geht durch dieselbe Pruefung, durch dieselben elf Gates, und er
> kostet denselben Versuch. Der einzige Unterschied ist, dass er nichts kostet
> und dass dransteht, woher er kommt.

**Erneutes Messen zaehlt erneut.** Wer eine dieser Dateien noch einmal durch
``cli vorschlag`` schickt, verbraucht die Versuche ein zweites Mal - die
Ergebnisse stehen im BEFUND, dafuer muss nichts wiederholt werden.
