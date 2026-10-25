"""Was eine gepflegte Zahl von dem Speicher weiss, auf dem sie gemessen wurde.

Befund 364 hat die Zulassungsreihe aus vier unabhaengig gepflegten Angaben
wiederhergestellt und dabei drei Zahlen gefunden, die auf ihr **nicht** mehr
reproduzieren. Der Eintrag dort nennt die wahrscheinliche Ursache und sagt im
selben Satz, warum sie offen bleiben muss:

    Bleibt als Erklaerung, dass Bitstamp einzelne alte Kerzen nachtraeglich
    berichtigt hat - nachzupruefen ist das **nicht**, denn den damaligen
    Speicher gibt es nicht mehr.

Das ist der Punkt, an dem dieses Modul ansetzt. Es macht die Drift von damals
nicht nachpruefbar - das ist vorbei. Es sorgt dafuer, dass die naechste sich
benennen laesst, statt als unerklaerter Testausfall dazustehen.

``data_store/`` steht in ``.gitignore`` (Zeile 24). Jeder Container holt ihn
neu, und keine gepflegte Zahl hat bisher verzeichnet, auf welchem Stand sie
gemessen wurde. Vierzehn Zyklen lang ist das nicht aufgefallen, weil die Suite
als ``-m "not daten"`` laeuft und die Datenauswahl ab Befund 364 rot war
(Befund 408: 3 von 116, in 35 Minuten).

Wofuer das **nicht** da ist
---------------------------
Nicht, um eine gepflegte Zahl nachzuziehen, bis sie zur Messung passt. Befund
364 nennt das "die Umkehrung des Verfahrens", und der Satz gilt. Darum steht
in ``Altzahl`` **beides**: ``gepflegt`` ist der Wert von damals und wird nie
angefasst, ``heute`` ist der Wert auf dieser Reihe. Was der Test prueft, ist
die Zahl von heute **und den Abstand zwischen beiden** - damit die
Unreproduzierbarkeit selbst unter Test steht, statt nur in einem Prosatext.

Nicht als Gate. Keine dieser Zahlen entscheidet eine Zulassung. Die tragenden
Zahlen reproduzieren exakt und bleiben hart festgenagelt: 156 rohe und 115
effektive Trades, Deflated Sharpe 0,5826, neun von elf Gates.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field

__all__ = [
    "ALTZAHLEN",
    "SERIE",
    "Altzahl",
    "Reihenstempel",
    "altzahl",
    "fingerabdruck",
    "groesste_abweichung",
    "stempel",
    "warum",
]

#: Die Spalten, die in den Abdruck eingehen. Nicht ``open_time``: Die Spanne
#: steht ohnehin in ``balken``/``von``/``bis``, und eine nachtraeglich
#: berichtigte Kerze aendert Preise, nicht ihren Zeitstempel.
SPALTEN = ("open", "high", "low", "close", "volume")


def fingerabdruck(frame) -> str:
    """Ein kurzer Abdruck der Kerzen eines Rahmens.

    Bewusst ohne ``pandas.util.hash_pandas_object``: Dessen Ergebnis haengt an
    der pandas-Fassung, und ein Abdruck, der sich mit einem Abhaengigkeits-
    Update aendert, meldet eine Datenaenderung, die keine ist. Darum eine
    ausgeschriebene Dezimaldarstellung, die nur von den Zahlen abhaengt.
    """
    zeilen = (
        "|".join(f"{float(frame[s].iloc[i]):.8f}" for s in SPALTEN)
        for i in range(len(frame))
    )
    roh = "\n".join(zeilen).encode()
    return hashlib.sha256(roh).hexdigest()[:16]


@dataclass(frozen=True)
class Reihenstempel:
    """Form und Inhalt der Reihe, auf der die Zahlen von heute stehen."""

    balken: int
    von: str
    bis: str
    abdruecke: Mapping[str, str] = field(default_factory=dict)

    def abweichungen(self, frames) -> tuple[str, ...]:
        """Welche Symbole nicht mehr die Kerzen von damals haben.

        Ein Symbol, das der Stempel nicht kennt, gilt **nicht** als Abweichung
        - sonst meldete jeder zusaetzlich gemessene Markt eine Datendrift.
        """
        anders = []
        for name, erwartet in sorted(self.abdruecke.items()):
            if name not in frames:
                anders.append(f"{name} fehlt")
                continue
            ist = fingerabdruck(frames[name])
            if ist != erwartet:
                anders.append(f"{name} {erwartet[:8]} -> {ist[:8]}")
        return tuple(anders)

    def passt(self, frames) -> bool:
        return not self.abweichungen(frames)


def stempel(frames) -> Reihenstempel:
    """Nimmt den Stempel der uebergebenen Rahmen ab."""
    erster = frames[sorted(frames)[0]]
    return Reihenstempel(
        balken=len(erster),
        von=str(erster["open_time"].iloc[0])[:10],
        bis=str(erster["open_time"].iloc[-1])[:10],
        abdruecke={x: fingerabdruck(frames[x]) for x in sorted(frames)},
    )


#: Die Zulassungsreihe, auf der die ``heute``-Werte unten gemessen sind
#: (Befund 408). ``balken``/``von``/``bis`` sind formgleich mit dem, was
#: Befund 364 verzeichnet - was sich geaendert hat, sind einzelne Kerzen, und
#: genau dafuer stehen die Abdruecke.
SERIE = Reihenstempel(
    balken=3301,
    von="2017-08-16",
    bis="2026-08-29",
    abdruecke={
        "BTCUSD_BITSTAMP": "5cda943508eecc9d",
        "ETHUSD_BITSTAMP": "3141cefdf649ffc2",
    },
)


@dataclass(frozen=True)
class Altzahl:
    """Eine gepflegte Zahl, die auf dieser Reihe nicht mehr reproduziert.

    ``gepflegt`` wird nicht angefasst. Wer sie aendert, loescht den einzigen
    Beleg dafuer, dass hier etwas gedriftet ist.
    """

    name: str
    gepflegt: float
    heute: float
    befund: int
    #: Wo die Unreproduzierbarkeit verzeichnet ist - und wo sie unter Test
    #: gestellt wurde.
    verzeichnet: int = 364
    gemessen: int = 408

    @property
    def abstand(self) -> float:
        """Der relative Abstand, mit Vorzeichen: heute gegen damals."""
        return (self.heute - self.gepflegt) / abs(self.gepflegt)

    @property
    def prozent(self) -> float:
        return 100.0 * self.abstand


#: Die Zahlen aus Befund 364 ("**Drei nicht**, und sie bleiben offen"), als
#: Daten statt als Prosa. Es sind **sechs** Eintraege, nicht drei, und der
#: Unterschied ist nachgemessen (Befund 408):
#:
#: * Schiefe und Woelbung ueber alle Trades sind zwei Zahlen, die der Eintrag
#:   von 364 als eine fuehrt.
#: * Der zweite Kapitalendstand ohne Officer ("mit Funding") und der zweite
#:   Streuungswert ("DSR mit der Messung") standen in keiner der beiden
#:   Listen. Beide kamen erst zum Vorschein, als die Zusicherung **davor**
#:   nicht mehr vorher abbrach - ein ``assert`` beendet den Test, und was
#:   danach steht, wird nie gemessen.
#:
#: Das heisst auch: "zwoelf von fuenfzehn stimmen wieder exakt" (364) hat die
#: Zaehlung zu guenstig angesetzt. Gezaehlt werden konnte nur bis zum ersten
#: Ausfall je Test.
#:
#: Und die Spanne ist weiter als die Prosa sagt. 364 nennt "zwischen 0,2 und
#: 0,6 Prozent"; gemessen sind es **0,23 bis 1,20 Prozent**.
ALTZAHLEN: tuple[Altzahl, ...] = (
    Altzahl(
        name="Kapitalendstand, wie gebaut, ohne Officer",
        gepflegt=2318.32,
        heute=2331.38,
        befund=339,
    ),
    Altzahl(
        name="Kapitalendstand, mit Funding, ohne Officer",
        gepflegt=1632.86,
        heute=1643.22,
        befund=339,
    ),
    Altzahl(
        name="Streuungswert, DSR mit der Annahme",
        gepflegt=0.5958,
        heute=0.5994,
        befund=340,
    ),
    Altzahl(
        name="Streuungswert, DSR mit der Messung",
        gepflegt=0.2761,
        heute=0.2794,
        befund=340,
    ),
    Altzahl(
        name="Schiefe ueber alle Trades",
        gepflegt=3.376,
        heute=3.3683,
        befund=356,
    ),
    Altzahl(
        name="Woelbung ueber alle Trades",
        gepflegt=15.415,
        heute=15.3571,
        befund=356,
    ),
)


def altzahl(name: str) -> Altzahl:
    """Die Altzahl mit diesem Namen.

    Ein unbekannter Name ist ein Fehler und kein ``None``: Ein Test, der seine
    Altzahl nicht findet, soll nicht stillschweigend durchlaufen.
    """
    for eintrag in ALTZAHLEN:
        if eintrag.name == name:
            return eintrag
    raise KeyError(f"keine Altzahl mit dem Namen {name!r}")


def groesste_abweichung() -> float:
    """Der groesste relative Abstand ueber alle Altzahlen.

    Die pruefbare Behauptung dazu steht im Test, und sie ist die gemessene
    Spanne selbst (0,23 bis 1,20 Prozent), nicht eine Schwelle, die bequem
    darueber liegt. Eine Schwelle, die man anhebt, bis es passt, waere genau
    das, was Befund 364 "die Umkehrung des Verfahrens" nennt.

    Wofuer die Spanne zaehlt: Sechs Abweichungen zwischen einem Viertel und
    einem Prozent, in **beide** Richtungen, sehen nach berichtigten Kerzen
    aus. Ein Rechenfehler zoege alle in dieselbe Richtung.
    """
    return max(abs(x.abstand) for x in ALTZAHLEN)


def warum(frames, gegen: Reihenstempel | None = None) -> str:
    """Sagt, ob die Reihe noch die ist, auf der ``heute`` gemessen wurde.

    Gehoert als Meldung an jede Zusicherung, die auf einer ``Altzahl`` steht.
    Dann sagt ein Ausfall, **ob** die Daten sich bewegt haben, statt nur, dass
    eine Zahl nicht stimmt - die Auskunft, die Befund 364 nicht mehr bekommen
    konnte.

    ``gegen`` gibt es, damit beide Zweige ohne echte Daten pruefbar sind. Ohne
    das Argument waere der Zweig "unveraendert" nur mit dem Speicher dieses
    Containers zu erreichen, und ein Zweig ohne Test ist kein Zweig.
    """
    anders = (gegen or SERIE).abweichungen(frames)
    if not anders:
        return (
            "Die Reihe ist unveraendert (Abdruck wie Befund 408) - eine "
            "abweichende Zahl kommt dann nicht aus den Daten."
        )
    return (
        "Die Reihe hat sich geaendert: "
        + "; ".join(anders)
        + " - der Speicher steht in .gitignore, also nachgeladen und "
        "nicht derselbe. Erst den Stempel nachziehen, dann die Zahl."
    )
