"""Was heisst die Latte des haertesten Gates - gemessen statt geglaubt.

Die Frage, die Befund 276 und 277 eine Ebene tiefer gestellt haben
--------------------------------------------------------------------
Befund 276 hat im Vorteilsscan gefunden, dass ``schwelle_fuer`` zu niedrig
steht, weil sie eine Normalverteilung unterstellt, die die Daten nicht haben.
Befund 277 hat dieselbe Frage am zweiten Scan gestellt - dort haelt sie.

Dieselbe Frage gehoert an das Gate, das die Zulassung blockiert. ``cli stand``
schreibt seit jeher *"Wahrscheinlichkeit 46,3 %, dass der Vorteil echt ist"*.
Ob die Zahl das ist, stand nirgends - sie kam aus einer Formel und nicht aus
einer Messung.

Wie hier gemessen wird
----------------------
**Aus den eigenen Trades.** Ihre Ergebnisse werden auf den Mittelwert null
verschoben - dieselbe Form, derselbe Schwanz, dieselbe Schiefe, nur kein
Vorteil mehr - und daraus wird ein ganzer Suchlauf gezogen: ``versuche``
Kandidaten, jeder mit ``roh`` Trades, davon der beste genommen und durch
dieselbe Gate-Rechnung geschickt. Das ist die Nullhypothese des Gates,
ausgespielt statt angenommen.

Keine Verteilungsannahme: Gezogen wird mit Zuruecklegen aus dem, was da ist.
Eine Normalverteilung, eine Exponentialverteilung oder sonst ein Ersatz haette
andere Schwaenze als der Bestand, und gerade die Schwaenze gehen ueber Schiefe
und Woelbung in die Formel ein.

Was die Messung **nicht** ist
-----------------------------
**Kein Grund, die Latte zu senken.** Die Regel dieses Projekts lautet: Gates
werden nicht gelockert, damit etwas besteht. Sie gilt hier besonders, weil der
Bestand dicht an der Frage steht - eine Schwelle zu aendern, waehrend man
weiss, wo der eigene Kandidat liegt, ist genau der Vorgang, gegen den die
Regel geschrieben ist. Gemessen wird, **was die Zahl bedeutet**, nicht wo sie
stehen soll.

**Und eine obere Schranke, keine Punktschaetzung.** Die gezogenen Versuche
sind unabhaengig; die echten sind Varianten derselben Regel auf derselben
Historie und damit hoch korreliert. Korrelierte Versuche liefern ein
**kleineres** Maximum, also noch weniger Fehlalarme. Was hier steht, ist
deshalb die guenstigste Lesart fuer die Latte: So oft schlaegt sie
hoechstens faelschlich an.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from research.gates import deflated_sharpe_ratio

#: Wie viele ganze Suchlaeufe gezogen werden.
#:
#: Die Zahl bestimmt die Aufloesung: Bei 5.000 Laeufen heisst das schaerfste
#: Ergebnis "kein einziger", und das ist eine Aussage ueber 1 von 5.001 -
#: nicht ueber weniger. Feiner wird es nur mit mehr Laeufen, nicht mit einer
#: anderen Rechnung.
LAEUFE = 5_000

#: Feste Saat. Eine Eichung, deren Ergebnis vom Tag abhaengt, ist keine.
SAAT = 278


@dataclass(frozen=True, slots=True)
class Nullverteilung:
    """Wo der Deflated Sharpe landet, wenn gar kein Vorteil da ist."""

    werte: np.ndarray
    versuche: int
    stichprobe: int
    """Die **effektive** Stichprobe, die das Gate der Formel uebergibt."""

    roh: int
    """So viele Trades zieht jeder Versuch - wie beim Bestand."""

    latte: float

    @property
    def laeufe(self) -> int:
        return len(self.werte)

    @property
    def fehlalarm(self) -> float:
        """Anteil der Suchlaeufe ohne Vorteil, die die Latte trotzdem nehmen."""
        return float(np.mean(self.werte >= self.latte))

    @property
    def aufloesung(self) -> float:
        return 1 / (self.laeufe + 1)

    def perzentil(self, p: float) -> float:
        return float(np.percentile(self.werte, p))

    @property
    def latte_fuer_fuenf_prozent(self) -> float:
        """Wo eine Latte stuende, die tatsaechlich fuenf Prozent zulaesst.

        **Zum Vergleich, nicht zum Einsetzen.** Die Zahl sagt, wie weit die
        gesetzte Latte von dem entfernt ist, was ihr Name nahelegt - sie ist
        kein Vorschlag.
        """
        return self.perzentil(95)

    def lage(self, wert: float) -> float:
        """Das Perzentil, an dem ein beobachteter Wert in dieser Null steht.

        Die Zahl, die der rohe DSR nicht sagt: Ob 0,59 viel ist, haengt am
        Versuchsstand, und die Null verschiebt sich mit ihm. Das Perzentil
        vergleicht beide auf demselben Stand.
        """
        return 100.0 * (1.0 - float(np.mean(self.werte >= wert)))

    def beschreibe(self) -> str:
        if self.fehlalarm > 0:
            haeufigkeit = f"{self.fehlalarm:.3%}"
        else:
            haeufigkeit = f"unter {self.aufloesung:.3%} (kein einziger Lauf)"
        return (
            f"Bei {self.versuche} Versuchen und {self.stichprobe} wirksamen "
            f"Beobachtungen erreicht ein Suchlauf **ohne jeden Vorteil** die "
            f"Latte von {self.latte:.2f} in {haeufigkeit} der Faelle. Das 95. "
            f"Perzentil dieser Nullverteilung liegt bei "
            f"{self.latte_fuer_fuenf_prozent:.4f}, der Median bei "
            f"{self.perzentil(50):.4f}.\n{self.grundlagensatz()}"
        )

    def grundlagensatz(self) -> str:
        """Woraus gezogen wurde - und wie viel Genauigkeit das hergibt.

        **Befund 343.** Die Saat ist fest, damit die Eichung nicht vom Tag
        abhaengt. Sie haengt dafuer von der **Trade-Liste** ab, aus der gezogen
        wird, und die wandert mit dem Kandidaten und den Daten. Genau daran
        sind die Zahlen aus Befund 278 nicht mehr zu reproduzieren: Der Eintrag
        nennt 0,9305 und 3,36 %, heute kommen 0,9307 und 3,200 % heraus - kein
        Zufall, sondern eine andere Grundlage.

        Gemessen (343, je ein Trade weniger, zehn Proben): Das 95. Perzentil
        wandert um 0,0058, der Fehlalarm um 0,78 Punkte - **ein Viertel seines
        eigenen Werts**. Die Zeilen mit "kein einziger Lauf" bleiben dagegen in
        jeder Probe stehen; sie sind grob und deshalb belastbar.

        Deshalb steht die Zahl hier mit ihrer Grundlage daneben. Vier Stellen
        ohne sie sind eine Genauigkeit, die es nicht gibt.
        """
        if self.fehlalarm > 0:
            genauigkeit = (
                " Ein Trade mehr oder weniger in dieser Liste verschiebt den "
                "Fehlalarm um rund ein Viertel seines Werts (Befund 343) - die "
                "Stellen hinter dem Komma sind Grundlage und nicht Praezision."
            )
        else:
            genauigkeit = (
                " 'Kein einziger Lauf' haelt dieser Verschiebung stand: Die "
                "Aussage ist grob und deshalb belastbar (Befund 343)."
            )
        return (
            f"Gezogen aus {self.roh} Trades des Bestands, mit fester Saat "
            f"({self.laeufe} Laeufe).{genauigkeit}"
        )


def nullverteilung(
    pnls: list[float] | np.ndarray,
    *,
    versuche: int,
    stichprobe: int,
    latte: float = 0.95,
    laeufe: int = LAEUFE,
    saat: int = SAAT,
) -> Nullverteilung:
    """Ganze Suchlaeufe unter der Nullhypothese des Gates.

    ``pnls`` sind die Ergebnisse der tatsaechlich gehandelten Trades,
    ``stichprobe`` die effektive Zahl, die das Gate der Formel uebergibt
    (``stichprobe_wie_im_gate``). Beides muss aus derselben Kette stammen wie
    im Gate - sonst misst diese Eichung eine andere Latte als die, die gilt
    (Befund 135/139).
    """
    ergebnisse = np.asarray(pnls, dtype=float)
    if len(ergebnisse) < 3:
        raise ValueError("Zu wenige Trades fuer eine Eichung.")
    if versuche < 1 or stichprobe < 3:
        raise ValueError("Versuche und Stichprobe muessen sinnvoll sein.")

    ohne_vorteil = ergebnisse - float(np.mean(ergebnisse))
    roh = len(ergebnisse)
    rng = np.random.default_rng(saat)

    werte = np.empty(laeufe)
    for i in range(laeufe):
        proben = rng.choice(ohne_vorteil, size=(versuche, roh), replace=True)
        streuung = proben.std(axis=1)
        sharpe = np.divide(
            proben.mean(axis=1),
            streuung,
            out=np.zeros(versuche),
            where=streuung > 0,
        )
        beste = int(np.argmax(sharpe))
        werte[i] = _wie_das_gate(proben[beste], float(sharpe[beste]), versuche, stichprobe)

    return Nullverteilung(
        werte=werte,
        versuche=versuche,
        stichprobe=stichprobe,
        roh=roh,
        latte=latte,
    )


def _wie_das_gate(
    ergebnisse: np.ndarray, sharpe: float, versuche: int, stichprobe: int
) -> float:
    """Schiefe und Woelbung genau wie in ``gate_deflated_sharpe``.

    Dort stehen Populationsmomente auf der mit ``np.std`` normierten Reihe -
    nicht die korrigierten Schaetzer. Wer hier anders rechnet, eicht eine
    Formel, die es nicht gibt.
    """
    streuung = float(np.std(ergebnisse))
    if streuung <= 0:
        return 0.0
    zentriert = (ergebnisse - float(np.mean(ergebnisse))) / streuung
    return deflated_sharpe_ratio(
        observed_sharpe=sharpe,
        trials=versuche,
        sample_size=stichprobe,
        skew=float(np.mean(zentriert**3)),
        kurtosis=float(np.mean(zentriert**4)),
    )
