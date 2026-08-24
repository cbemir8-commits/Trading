"""Wo die fehlende Evidenz noch herkommen koennte - und wo nicht mehr.

Befund 110 liess eine Frage offen: Findet sich noch eine Bedingung, die wie
das Funding wirkt? Das Funding war kein Suchergebnis, sondern eine
Kostenannahme, die im Spot-Handel schlicht entfaellt - und sie hob den
Deflated Sharpe von 0,7641 auf 0,8640. Ein einziger Wegfall, mehr wert als
198 Versuche Suche.

Dieses Modul beantwortet die Frage, indem es die **Decke** jeder Familie von
Stellschrauben misst: den besten Wert, den sie ueberhaupt noch hergeben kann.
Liegt die Decke unter der Schwelle, ist die Familie erschoepft - dann ist
weiteres Drehen daran nicht optimistisch, sondern zwecklos.

Die vier Familien
-----------------
**Kosten.** Gebuehren, Slippage, Funding. Die Decke ist der Lauf, der gar
nichts kostet - tiefer geht es nicht.

    Perpetual wie gebaut      DSR 0,7641   7/11 Gates
    Spot wie gebaut           DSR 0,8640   9/11 Gates
    Spot ohne Slippage        DSR 0,8684   9/11 Gates
    Spot ohne Gebuehren       DSR 0,8766  10/11 Gates
    Spot voellig kostenfrei   DSR 0,8808  10/11 Gates   <- Decke

**Die Kostenfamilie ist erschoepft.** Bei Kosten null steht der Kandidat bei
0,8808, die Schwelle liegt bei 0,95. Es fehlen 0,0692 - und es gibt keine
Kosten mehr, die man noch wegnehmen koennte. Was nach dem Funding noch im
Topf war, sind 0,0168; die Luecke ist das Vierfache davon.

Zur Groessenordnung, auf derselben Skala:

    Funding (Perpetual -> Spot)   +0,0999
    Gebuehren auf null            +0,0126
    Slippage auf null             +0,0044
    ------------------------------------
    alles zusammen ohne Funding   +0,0168
    verbleibende Luecke           -0,0692

Die gewaehlte Slippage - ``slippage_bps = 1,0`` und ``stop_slippage_bps =
5,0``, beide nie gemessen - ist damit als Streitfall erledigt. Ihre ganze
plausible Spanne ist ein Sechzehntel der Luecke, und die Gates halten bis zum
Sechsfachen des angesetzten Werts:

    Einstieg  Stopp     DSR      Gates
      0,0      0,0    0,8684      9/11
      1,0      5,0    0,8640      9/11   <- wie gebaut
      2,0     10,0    0,8595      9/11
      4,0     20,0    0,8501      9/11
      6,0     30,0    0,8403      9/11
     10,0     50,0    0,8208      8/11

**Historie.** Mehr Jahre auf derselben Regel. Auf der Platte liegen 5331
BTC-Tageskerzen ab 2012, aber nur 3277 gemeinsame ab 2017-08-16 - der
Portfolio-Lauf schneidet auf den gemeinsamen Bereich zu. Naheliegender
Gedanke: Die weggeworfenen 5,6 Jahre liefern die fehlenden Beobachtungen.

Gemessen ist es das Gegenteil. Alle drei Fenster, wie vor dem Lauf
zugesagt - auch die, die schlechter dastehen:

    Fenster                       Zeitraum          Trades  Guete    DSR    Gates
    BTC + ETH, gemeinsam          2017-08..2026-08    152  0,2765  0,8640   9/11
    BTC allein, gemeinsam         2017-08..2026-08     72  0,2655  0,1761   8/11
    BTC allein, volle Historie    2012-01..2026-08    117  0,2652  0,4198   5/11

Die zusaetzlichen Jahre bringen 45 Trades und kosten drei Gates: Die Rendite
faellt von 14,61 % auf 11,04 %, der Rueckgang steigt von 10,71 % auf 17,58 %.
**Die Historienfamilie hat keine Decke ueber dem heutigen Stand** - ihr bester
gemessener Wert ist der, auf dem das Projekt bereits steht.

**Maerkte.** Die dritte Zeile derselben Tabelle verfuehrt zu einem Schluss,
den ich hier zuerst gezogen habe: BTC allein steht bei DSR 0,1761, BTC und ETH
zusammen bei 0,8640 - ein Markt mehr, und der Wert springt um 0,6879. Die
Guete bewegt sich dabei kaum (0,2655 gegen 0,2765); der Sprung kommt aus der
Zahl der Beobachtungen, 72 gegen 152. Also, so der Schluss, kommt n aus
Maerkten, und die Familie sei die letzte offene.

**Der Schluss war falsch, und zwar nachweislich seit Befund 27.** Dort ist
genau das gemessen worden, mit mehr Maerkten als hier:

    Kombination        roh   effektiv    ICC       p   Guete    DSR
    BTC+ETH            152        152  0,112   0,072  0,2597  0,864
    BTC+ETH+XRP        260        146  0,105   0,021  0,2006  0,422
    BTC+ETH+LTC+XRP    366        151  0,132   0,001  0,1757  0,275

**Die effektive Stichprobe bleibt bei rund 150, egal wie viele Maerkte
dazukommen.** Die rohe Zahl waechst um das Zweieinhalbfache, die Zahl
unabhaengiger Beobachtungen um nichts, und die Guete faellt von 0,26 auf 0,18.
Ein dritter Markt senkt die effektive Stichprobe sogar - von 152 auf 146.

Der Sprung von einem auf zwei Maerkte ist also kein Anfang einer Reihe,
sondern ihr einziges Glied. Auch die Maerktefamilie hat **keine Decke ueber
dem heutigen Stand**.

Wie dieser Irrtum zustande kam
------------------------------
``research/stand.py`` fuehrt seit Befund 90 eine Liste der geschlossenen
Richtungen, und ganz oben steht seit Befund 27:

    Richtung("Mehr Maerkte", "effektive Stichprobe bleibt bei 150", 27)

Die Datei war beim Schreiben dieses Befundes offen. Ich habe die Liste nicht
gelesen, den Schluss aus der eigenen frischen Messung gezogen und als
"naechste Messung" angekuendigt, was seit 84 Befunden gemessen ist. Genau
dagegen ist ``stand.py`` gebaut worden - der Nutzen eines solchen Registers
haengt daran, dass man hineinsieht, bevor man eine Richtung fuer offen
erklaert, nicht danach.

**Versuche.** Die vierte Familie, und die einzige, die sich bisher gegen das
Projekt bewegt hat. Der Deflated Sharpe haengt am Versuchszaehler, und der
kennt nur eine Richtung. Derselbe Perpetual-Lauf, dieselben 152 Trades,
dieselbe Guete 0,2597 - nur der Zaehler wandert:

    102 Versuche (Stand Befund 27)   DSR 0,8625
    198 Versuche (heute)             DSR 0,7632

**Die 96 Versuche seit Befund 27 haben 0,0993 am Deflated Sharpe gekostet -
fast genau so viel, wie der Wegfall des Fundings einbrachte (+0,0999).** Die
groesste Einzelmessung dieses Projekts hat gerade zurueckgeholt, was die Suche
seit Befund 27 ausgegeben hat.

Darin enthalten sind die 21 Versuche, die ich in Befund 104 mit einem
Rauchtest verbrannt habe. Am Spot-Betriebspunkt kostet das:

    177 Versuche (ohne meinen Fehler)   DSR 0,8777   178 Beobachtungen noetig
    198 Versuche (mit)                  DSR 0,8643   182 Beobachtungen noetig

0,0134 am Deflated Sharpe und vier zusaetzliche Beobachtungen. Der Zaehler
bleibt, wo er ist - ihn zurueckzudrehen hiesse, den eigenen Fehler aus der
Rechnung zu nehmen, und das waere dasselbe wie ein gelockertes Gate.

Wie viel n ueberhaupt fehlt
---------------------------
Bei unveraenderter Guete und 198 Versuchen:

    n = 152   DSR 0,8640   <- heute
    n = 182   DSR 0,9500   <- Schwelle haelt

**Dreissig unabhaengige Beobachtungen.** Das ist die ganze Luecke, in der
Waehrung ausgedrueckt, in der sie zu schliessen waere. Beim kostenfreien Lauf
(Guete 0,2798) sind es 177 - die Kostenfamilie verschiebt also auch hier nur
fuenf Beobachtungen.

Was der Deflated Sharpe misst - und was nicht
---------------------------------------------
Beim Schreiben der Tests stand hier zuerst die Annahme, ein zu kleiner Vorteil
sei durch keine Datenmenge zu retten. Der Test fiel durch, und die Annahme war
falsch. Der erwartete Maximalwert unter der Nullhypothese schrumpft mit
``1/sqrt(n)``, die Pruefgroesse waechst mit ``sqrt(n)``: Bei **jeder** echt
positiven Guete laeuft der Wert gegen 1. Eine Guete von 0,02 traegt die
Schwelle bei 47.335 Beobachtungen.

**Der Deflated Sharpe misst Evidenz, nicht Vorteilsgroesse.** Ein winziger
Vorteil besteht ihn, wenn nur genug Beobachtungen da sind. Gegen einen zu
kleinen Vorteil schuetzt allein die Messlatte - und die ist das zweite Gate,
das beim Bestand offen steht (14,83 % gegen 15 %). Die dreissig fehlenden
Beobachtungen schliessen also **eines von zwei** offenen Gates.

Genau genommen gilt auch das nur, wenn sich sonst nichts aendert - und das
wird es. Beobachtungen kommen nicht aus dem Nichts, sondern aus Maerkten oder
Jahren, und beide Quellen sind gemessen: Maerkte lassen die effektive
Stichprobe bei 150 (Befund 27), Jahre senken die Guete (Befund 14, hier
bestaetigt). Die dreissig sind deshalb die **untere** Schranke der Aufgabe,
nicht ihr Preis - und keine der beiden Quellen liefert sie.

Was am Ende steht
-----------------
Alle vier Familien sind gemessen, und keine traegt:

    Kosten     Anschlag 0,8808 bei Kosten null          es fehlen 0,0692
    Historie   kein Fenster ueber dem heutigen Stand    Befund 14, hier bestaetigt
    Maerkte    effektive Stichprobe bleibt bei 150      Befund 27
    Versuche   bewegt sich nur nach unten               -0,0993 seit Befund 27

Damit ist die Frage aus Befund 110 beantwortet: **Nein.** Es gibt keine zweite
Bedingung, die wie das Funding wirkt. Was fehlt, muss aus einer Regel kommen,
die **je Trade** besser ist - genau der Schluss, den Befund 27 schon gezogen
hat, jetzt auch von der Kostenseite her beziffert.

Warum es kein Fenster-Shopping ist
----------------------------------
Vor dem Lauf festgelegt und hier eingehalten: Berichtet werden alle drei
Fenster. Wer nach den Zahlen das guenstigste aussucht, betreibt dieselbe
Sache wie ein gelockertes Gate, nur unauffaelliger. ``Fensterlage`` haelt das
fest: Es gibt keine Methode, die das beste Fenster zurueckgibt.
``wechsel_begruendbar`` nennt nur Fenster, die das Referenzfenster in **jeder**
Hinsicht schlagen - hier keines.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.gates import deflated_sharpe_ratio

#: Schwelle des Deflated-Sharpe-Gates.
SCHWELLE = 0.95


@dataclass(frozen=True, slots=True)
class Deckenwert:
    """Was eine Familie von Stellschrauben hoechstens noch hergibt.

    ``heute`` ist der Stand des Betriebspunkts, ``decke`` der beste Wert, den
    die Familie erreichen kann, wenn man sie bis an ihren Anschlag dreht.

    ``gemessen`` ist die entscheidende Angabe. Eine Familie, deren Anschlag
    nicht gemessen wurde, darf nicht als Ausweg gelten - sonst steht am Ende
    eine Hoffnung da, wo eine Zahl stehen muesste.
    """

    name: str
    heute: float
    decke: float
    gemessen: bool = True
    anschlag: str = ""

    @property
    def spielraum(self) -> float:
        """Wie viel die Familie ueber den heutigen Stand hinaus hergibt."""
        return self.decke - self.heute

    def reicht(self, schwelle: float = SCHWELLE) -> bool:
        """Traegt die Familie bis ueber die Schwelle?

        Bei ungemessenem Anschlag immer ``False``: Nicht, weil sie es nicht
        koennte, sondern weil niemand es weiss.
        """
        return self.gemessen and self.decke >= schwelle

    def fehlt(self, schwelle: float = SCHWELLE) -> float:
        """Was auch am Anschlag noch fehlt. Null, wenn sie reicht."""
        if not self.gemessen:
            return float("nan")
        return max(0.0, schwelle - self.decke)

    def erschoepft(self, schwelle: float = SCHWELLE) -> bool:
        """Gemessen, und der Anschlag liegt unter der Schwelle."""
        return self.gemessen and self.decke < schwelle

    def als_text(self, schwelle: float = SCHWELLE) -> str:
        if not self.gemessen:
            return f"{self.name}: Anschlag ungemessen - kein Ausweg, den man beziffern kann."
        if self.reicht(schwelle):
            return (
                f"{self.name}: traegt bis {self.decke:.4f}, Schwelle {schwelle:.2f} - "
                f"Spielraum {self.spielraum:+.4f}."
            )
        return (
            f"{self.name}: Anschlag bei {self.decke:.4f}, Schwelle {schwelle:.2f} - "
            f"es fehlen {self.fehlt(schwelle):.4f}, und mehr gibt die Familie nicht her."
        )


@dataclass(frozen=True, slots=True)
class Decke:
    """Alle Familien nebeneinander.

    Die Frage, die dieses Objekt beantwortet, ist nicht "wo koennte noch etwas
    gehen", sondern "wo ist nachweislich nichts mehr zu holen". Das ist die
    nuetzlichere Haelfte: Sie spart die Arbeit, die ohnehin nicht traegt.
    """

    familien: tuple[Deckenwert, ...]
    schwelle: float = SCHWELLE

    def erschoepft(self) -> tuple[Deckenwert, ...]:
        """Familien, deren Anschlag gemessen unter der Schwelle liegt."""
        return tuple(f for f in self.familien if f.erschoepft(self.schwelle))

    def traegt(self) -> tuple[Deckenwert, ...]:
        """Familien, die gemessen bis ueber die Schwelle reichen.

        Ungemessene sind bewusst nicht dabei - siehe ``Deckenwert.reicht``.
        """
        return tuple(f for f in self.familien if f.reicht(self.schwelle))

    def ungemessen(self) -> tuple[Deckenwert, ...]:
        """Familien ohne gemessenen Anschlag."""
        return tuple(f for f in self.familien if not f.gemessen)

    @property
    def groesster_spielraum(self) -> Deckenwert | None:
        """Die gemessene Familie mit dem meisten Rest - nicht die beste Idee.

        Der Unterschied ist wichtig: Diese Familie gibt am meisten her, aber
        wenn ihr Anschlag trotzdem unter der Schwelle liegt, ist auch sie kein
        Weg. Deshalb heisst die Eigenschaft nach dem, was sie misst.
        """
        messbar = [f for f in self.familien if f.gemessen]
        if not messbar:
            return None
        return max(messbar, key=lambda f: f.spielraum)

    def alles_erschoepft(self) -> bool:
        """Jede gemessene Familie unter der Schwelle."""
        messbar = [f for f in self.familien if f.gemessen]
        return bool(messbar) and all(f.erschoepft(self.schwelle) for f in messbar)

    def urteil(self) -> str:
        if not self.familien:
            return "Keine Familie gemessen - dazu ist nichts zu sagen."
        traegt = self.traegt()
        if traegt:
            namen = ", ".join(f.name for f in traegt)
            return f"Es gibt einen gemessenen Weg ueber die Schwelle: {namen}."
        offen = self.ungemessen()
        erschoepft = self.erschoepft()
        teile = []
        if erschoepft:
            namen = ", ".join(f.name for f in erschoepft)
            teile.append(f"Erschoepft und gemessen: {namen}.")
        if offen:
            namen = ", ".join(f.name for f in offen)
            teile.append(
                f"Ungemessen und damit kein Ausweg, auf den man bauen darf: {namen}."
            )
        teile.append(
            "Keine gemessene Familie traegt ueber die Schwelle - was fehlt, "
            "muss aus der Sache selbst kommen, nicht aus den Annahmen."
        )
        return " ".join(teile)


def deflated_sharpe(
    *,
    guete: float,
    versuche: int,
    stichprobe: int,
    schiefe: float = 0.0,
    woelbung: float = 3.0,
) -> float:
    """Der Deflated Sharpe des Gates, in der Sprache dieses Moduls.

    **Bewusst nur weitergereicht, nicht nachgebaut.** Eine zweite Kopie der
    Formel waere derselbe Fehler, der in diesem Projekt schon dreimal
    aufgefallen ist (Befunde 101, 103, 109): eine feste Aussage neben einer
    gerechneten Zahl, die auseinanderlaufen kann, ohne dass es jemand merkt.
    Aendert ``research.gates`` die Formel, aendert sich diese hier mit.

    Gebraucht wird sie hier, weil dieses Modul die Groesse **umkehrt**: nicht
    "welcher Wert kommt bei n heraus", sondern "welches n traegt die
    Schwelle". Dafuer wird sie oft und ohne Trades ausgewertet.
    """
    return deflated_sharpe_ratio(
        observed_sharpe=guete,
        trials=max(versuche, 1),
        sample_size=stichprobe,
        skew=schiefe,
        kurtosis=woelbung,
    )


@dataclass(frozen=True, slots=True)
class Stichprobenbedarf:
    """Wie viele unabhaengige Beobachtungen die Schwelle braucht.

    Die Luecke am Deflated Sharpe laesst sich in zwei Waehrungen ausdruecken:
    in Guete (dann ist es eine Suchaufgabe, siehe ``research.wettrennen``) oder
    in Beobachtungen. Die zweite ist die nuetzlichere, weil sie sagt, wie viel
    Evidenz fehlt - und Evidenz kann man sammeln, ohne zu suchen.
    """

    guete: float
    versuche: int
    heute: int
    schiefe: float = 0.0
    woelbung: float = 3.0
    schwelle: float = SCHWELLE

    @property
    def stand(self) -> float:
        """Der Deflated Sharpe beim heutigen n."""
        return deflated_sharpe(
            guete=self.guete, versuche=self.versuche, stichprobe=self.heute,
            schiefe=self.schiefe, woelbung=self.woelbung,
        )

    def noetig(self, obergrenze: int = 1_000_000) -> int | None:
        """Kleinstes n, bei dem die Schwelle haelt. ``None``, wenn keines reicht.

        **``None`` kommt nur bei einer Guete von null oder darunter.** Das war
        hier zuerst anders angenommen - der Test dazu ist beim Schreiben
        durchgefallen, und die Annahme war falsch:

        Der erwartete Maximalwert unter der Nullhypothese schrumpft mit
        ``1/sqrt(n)``, die Pruefgroesse waechst mit ``sqrt(n)``. Bei **jeder**
        echt positiven Guete laeuft der Deflated Sharpe deshalb gegen 1. Eine
        Guete von 0,02 traegt die Schwelle bei 47.335 Beobachtungen - viel,
        aber endlich.

        Daraus folgt, was dieses Gate ist und was nicht: Der Deflated Sharpe
        misst **Evidenz, nicht Vorteilsgroesse.** Ein winziger Vorteil besteht
        ihn, wenn nur genug Beobachtungen da sind. Gegen einen zu kleinen
        Vorteil schuetzt allein die Messlatte - und genau die ist das zweite
        Gate, das beim Bestand noch offen steht. Die 30 fehlenden
        Beobachtungen schliessen eines der beiden, nicht beide.
        """
        if self.guete <= 0:
            return None
        if deflated_sharpe(
            guete=self.guete, versuche=self.versuche, stichprobe=obergrenze,
            schiefe=self.schiefe, woelbung=self.woelbung,
        ) < self.schwelle:
            return None

        tief, hoch = 3, obergrenze
        while tief < hoch:
            mitte = (tief + hoch) // 2
            if deflated_sharpe(
                guete=self.guete, versuche=self.versuche, stichprobe=mitte,
                schiefe=self.schiefe, woelbung=self.woelbung,
            ) >= self.schwelle:
                hoch = mitte
            else:
                tief = mitte + 1
        return tief

    def fehlende(self) -> int | None:
        """Wie viele Beobachtungen noch fehlen. Null, wenn es reicht."""
        noetig = self.noetig()
        if noetig is None:
            return None
        return max(0, noetig - self.heute)

    def faktor(self) -> float | None:
        """Das Wievielfache der heutigen Stichprobe noetig ist."""
        noetig = self.noetig()
        if noetig is None or self.heute <= 0:
            return None
        return noetig / self.heute

    def urteil(self) -> str:
        noetig = self.noetig()
        if noetig is None:
            return (
                f"Bei Guete {self.guete:.4f} traegt keine Stichprobengroesse ueber "
                f"{self.schwelle:.2f} - ohne positiven Vorteil je Trade hilft "
                "keine Menge an Evidenz."
            )
        fehlend = self.fehlende()
        if not fehlend:
            return (
                f"Die Schwelle haelt bereits: {self.heute} Beobachtungen, "
                f"noetig waeren {noetig}."
            )
        return (
            f"Es fehlen {fehlend} unabhaengige Beobachtungen: {self.heute} sind da, "
            f"{noetig} traegt die Schwelle ({self.faktor():.2f}-fach)."
        )


@dataclass(frozen=True, slots=True)
class Fenster:
    """Ein Datenfenster mit dem, was der Kandidat darin leistet."""

    name: str
    von: str
    bis: str
    trades: int
    guete: float
    dsr: float
    bestanden: int
    gesamt: int

    def schlaegt(self, andere: Fenster) -> bool:
        """Schlaegt dieses Fenster das andere in **jeder** Hinsicht?

        Alle drei Groessen zugleich - Gates, Deflated Sharpe, Trades. Ein
        Fenster, das nur an einer Stelle besser ist, hat den Vergleich nicht
        gewonnen, sondern nur eine Kennzahl.
        """
        return (
            self.bestanden > andere.bestanden
            and self.dsr > andere.dsr
            and self.trades >= andere.trades
        )


@dataclass(frozen=True, slots=True)
class Fensterlage:
    """Mehrere Datenfenster, mit dem Referenzfenster als Anker.

    **Es gibt hier absichtlich keine Methode, die das beste Fenster
    zurueckgibt.** Das Fenster nach den Ergebnissen auszusuchen ist dieselbe
    Sache wie ein gelockertes Gate: Man bekommt eine Zahl, die besteht, ohne
    dass sich an der Strategie etwas geaendert haette.

    Zulaessig ist nur der umgekehrte Weg: Das Referenzfenster steht vorher
    fest, alle gemessenen werden berichtet, und gewechselt wird nur, wenn ein
    anderes das Referenzfenster in jeder Hinsicht schlaegt.
    """

    referenz: Fenster
    weitere: tuple[Fenster, ...] = ()

    @property
    def alle(self) -> tuple[Fenster, ...]:
        """Jedes gemessene Fenster - das ist der Bericht, vollstaendig."""
        return (self.referenz, *self.weitere)

    def wechsel_begruendbar(self) -> tuple[Fenster, ...]:
        """Fenster, die das Referenzfenster in jeder Hinsicht schlagen."""
        return tuple(f for f in self.weitere if f.schlaegt(self.referenz))

    def abstand(self, fenster: Fenster) -> float:
        """Wie weit ein Fenster vom Referenzfenster abweicht (Deflated Sharpe)."""
        return fenster.dsr - self.referenz.dsr

    def urteil(self) -> str:
        begruendbar = self.wechsel_begruendbar()
        if begruendbar:
            namen = ", ".join(f.name for f in begruendbar)
            return (
                f"Ein Wechsel waere begruendbar: {namen} schlaegt "
                f"'{self.referenz.name}' in jeder Hinsicht."
            )
        return (
            f"Kein gemessenes Fenster schlaegt '{self.referenz.name}' in jeder "
            "Hinsicht - das Referenzfenster bleibt, und die anderen stehen "
            "trotzdem im Bericht."
        )


@dataclass(frozen=True, slots=True)
class Stufe:
    """Ein Lauf mit einer weiteren abgeschalteten Bremse."""

    name: str
    trades: int
    guete: float
    dsr: float
    bestanden: int
    gesamt: int
    offen: tuple[str, ...] = ()

    def als_zeile(self) -> str:
        return (
            f"{self.name:<28} {self.trades:>4} Trades  Guete {self.guete:.4f}  "
            f"DSR {self.dsr:.4f}  {self.bestanden}/{self.gesamt}"
            + (f"  offen: {', '.join(self.offen)}" if self.offen else "")
        )


@dataclass(frozen=True, slots=True)
class Reibungsprobe:
    """Liegt unterhalb von "Kosten null" noch etwas? - Befund 127.

    Die Frage
    ---------
    Befund 111 hat Gebuehren, Slippage und Funding auf null gesetzt und daraus
    geschlossen: *"Es gibt keine Kosten mehr, die man noch wegnehmen
    koennte."* Drei Bremsen blieben dabei an, und alle drei verhindern
    **Trades**:

        entry_expiry_bars = 3     PostOnly-Limits verfallen nach drei Balken
        enforce_risk_limits       der Risk-Officer sperrt Einstiege
        kalender                  das Termin-Overlay blockiert Signale

    Weniger Trades heisst kleineres n heisst niedrigerer Deflated Sharpe -
    wenn dort etwas liegt, ist die Kostendecke nicht der Anschlag, fuer den
    sie gehalten wird.

    Die Antwort
    -----------
    Sie liegt dort nicht. Gemessen:

        Spot wie gebaut              152 Trades  Guete 0,2765  DSR 0,8640   9/11
        + Kosten null                152 Trades  Guete 0,2798  DSR 0,8808  10/11
        + ohne Terminkalender        154 Trades  Guete 0,2770  DSR 0,8762   9/11
        + Limits verfallen nie       154 Trades  Guete 0,2770  DSR 0,8762   9/11
        + ohne Risk-Officer          156 Trades  Guete 0,2741  DSR 0,8710   9/11

    **Jede weitere Abschaltung macht es schlechter.** Die Bremsen sind keine
    Kosten, sondern Filter: Wer sie oeffnet, bekommt mehr Trades von
    schlechterer Qualitaet, und die Guete faellt schneller, als ``sqrt(n)``
    steigt. Dieselbe Kopplung wie in Befund 54, an einer anderen Stelle.

    Damit ist die Kostendecke bestaetigt - und zwar als das, was sie sein
    sollte: ein Anschlag, unter dem nichts mehr liegt.

    Ein Nebenbefund
    ---------------
    Der Terminkalender haelt am kostenfreien Anschlag die **Messlatte**: mit
    ihm 10 von 11, ohne ihn 9. Befund 12 hatte ihn als wirkungslos abgelegt -
    *"2 von 156 Signalen blockiert, kein Gate bewegt"*. Das war am
    Perpetual-Punkt mit Kosten gemessen und bleibt dort richtig; am
    kostenfreien Spot-Anschlag bewegt er eines.
    """

    stufen: tuple[Stufe, ...]

    @property
    def hoechster(self) -> Stufe | None:
        return max(self.stufen, key=lambda s: s.dsr) if self.stufen else None

    @property
    def kostenanschlag(self) -> Stufe | None:
        """Die Stufe, die Befund 111 als Anschlag ausweist."""
        for s in self.stufen:
            if "Kosten null" in s.name:
                return s
        return None

    @property
    def anschlag_haelt(self) -> bool:
        """Ist "Kosten null" der hoechste Wert der Reihe?

        Wenn ja, liegt unterhalb nichts, und Befund 111 steht. Wenn nein, gibt
        es eine Bremse, die mehr wert ist als alle Kosten zusammen - und dann
        war der Anschlag keiner.
        """
        anschlag, hoch = self.kostenanschlag, self.hoechster
        return anschlag is not None and hoch is not None and anschlag is hoch

    def gewinn_durch_oeffnen(self) -> float | None:
        """Was die zusaetzlichen Abschaltungen bringen. Negativ = sie kosten."""
        anschlag = self.kostenanschlag
        if anschlag is None or len(self.stufen) < 2:
            return None
        danach = [s for s in self.stufen if s.dsr != anschlag.dsr]
        spaeter = [s for s in self.stufen[self.stufen.index(anschlag) + 1 :]]
        if not spaeter and not danach:
            return None
        vergleich = spaeter or danach
        return max(s.dsr for s in vergleich) - anschlag.dsr

    def urteil(self) -> str:
        if not self.stufen:
            return "Keine Stufen gemessen - dazu ist nichts zu sagen."
        anschlag = self.kostenanschlag
        if anschlag is None:
            return "Kein Kostenanschlag in der Reihe - der Vergleich fehlt."
        if self.anschlag_haelt:
            gewinn = self.gewinn_durch_oeffnen()
            zusatz = (
                f" Die weiteren Abschaltungen bringen {gewinn:+.4f}."
                if gewinn is not None
                else ""
            )
            return (
                f"**Der Anschlag haelt.** 'Kosten null' ist mit "
                f"{anschlag.dsr:.4f} der hoechste Wert der Reihe; darunter "
                f"liegt nichts.{zusatz} Die Bremsen sind keine Kosten, sondern "
                f"Filter - wer sie oeffnet, bekommt mehr Trades von "
                f"schlechterer Qualitaet."
            )
        hoch = self.hoechster
        return (
            f"**Der Anschlag haelt nicht.** '{hoch.name}' kommt auf "
            f"{hoch.dsr:.4f} gegen {anschlag.dsr:.4f} bei 'Kosten null' - es "
            f"gibt eine Bremse, die mehr wert ist als alle Kosten zusammen. "
            f"Befund 111 gehoert entsprechend korrigiert."
        )
