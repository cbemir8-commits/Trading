"""Welche Generationen es gibt - und was in ihnen steht (Befund 459).

Der Anlass
----------
``cli wettbewerb`` waehlt seinen Startkatalog mit ``--generation``, und die
Hilfe dazu lautete:

    Startkatalog. 7 = Scalp-Setups, 8 = Abfolge-Modell und Short-Seite.

Zehn Generationen gibt es, zwei nennt dieser Satz, und die Vorgabe steht auf
**8**. Dass seither 9 und 10 dazugekommen sind - beide fuer **Tageskerzen**,
also fuer die Kerzenlaenge, auf der der Spitzenkandidat steht -, erfaehrt
niemand. Wer eine daily-Runde fahren will, muss ``seeds.py`` lesen.

Dieselbe Bauart wie in Befund 454: eine handgeschriebene Liste, die ab dem
Tag veraltet, an dem sie geschrieben wird, und niemand merkt es, weil sie
plausibel bleibt.

Zwei Begriffe von "Katalog"
---------------------------
Hier ist eine Unterscheidung wichtig, die leicht untergeht:

* ``cli wettbewerb -g N`` faehrt **genau** Generation N. Das ist Absicht -
  ``load_seeds`` sagt es im Docstring: *"Was widerlegt ist, muss nicht erneut
  geprueft werden"*, und jeder Wiederholungsversuch hebt die Huerde des
  Deflated Sharpe fuer alle folgenden.
* ``cli vorratsdecke -i D`` faehrt **alle** Generationen, die zu dieser
  Kerzenlaenge passen - 25 Genome auf Tageskerzen, 39 auf Viertelstunden.
  Das kostet keinen Versuch, weil nichts ausgewaehlt wird.

Beide Zahlen sind richtig, und beide heissen "der Katalog". Diese Uebersicht
nennt deshalb immer die Generation **und** ihre Kerzenlaenge.

Was gemessen ist
----------------
Die Finanzierungsabhaengigkeit sitzt in **zwei** Generationen: 4 (alle drei
Regeln) und 5 (zwei von drei). Die Generationen, die man heute faehrt - 8 auf
Viertelstunden, 9 und 10 auf Tageskerzen -, brauchen keine. Ohne
Finanzierungsdaten im Speicher fallen jene fuenf Regeln still heraus, und
genau das stand in einem Probelauf: *"Runde 1 - 1 Kandidaten (Katalog)"* bei
drei Genomen in Generation 5.

Gezaehlt wird mit ``kennzahlen.gebrauchte_kennzahlen`` und nicht mit einer
eigenen Suche - eine zweite Herleitung waere der Fehler aus Befund 439.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Generationsbild", "bericht", "uebersicht"]

#: Woran eine Regel erkennbar Finanzierungsdaten braucht.
#:
#: Als Praefix und nicht als Liste von Kennzahlen: ``funding_avg``,
#: ``funding_zscore`` und was noch dazukommt, teilen ihn. Eine Liste waere
#: dasselbe Veralten eine Ebene tiefer.
FINANZIERUNG = "funding"


@dataclass(frozen=True, slots=True)
class Generationsbild:
    """Eine Generation: Nummer, vorgesehene Kerzenlaenge, Inhalt."""

    nummer: int
    intervall: str | None
    """``None`` heisst "nicht festgelegt" - dann passt sie zu jeder
    Kerzenlaenge (``seeds.passt_zum_intervall``)."""

    namen: tuple[str, ...]
    finanzierung: tuple[str, ...]
    """Die Regeln dieser Generation, die Finanzierungsdaten brauchen."""

    @property
    def genome(self) -> int:
        return len(self.namen)

    def zeile(self) -> str:
        wohin = self.intervall or "frei"
        hinweis = (
            f"  {len(self.finanzierung)} brauchen Finanzierungsdaten"
            if self.finanzierung
            else ""
        )
        return f"  {self.nummer:>2}  {wohin:>4}  {self.genome:>2} Genome{hinweis}"


def uebersicht() -> tuple[Generationsbild, ...]:
    """Alle Generationen, geordnet - abgeleitet und nicht gepflegt."""
    from research.kennzahlen import gebrauchte_kennzahlen
    from research.seeds import GENERATIONS, VORGESEHEN, load_seeds

    aus: list[Generationsbild] = []
    for nummer in sorted(GENERATIONS):
        genome = load_seeds(nummer)
        aus.append(
            Generationsbild(
                nummer=nummer,
                intervall=VORGESEHEN.get(nummer),
                namen=tuple(g.name for g in genome),
                finanzierung=tuple(
                    g.name
                    for g in genome
                    if any(
                        FINANZIERUNG in k for k in gebrauchte_kennzahlen(g)
                    )
                ),
            )
        )
    return tuple(aus)


def bericht(*, intervall: str | None = None) -> str:
    """Die Uebersicht als Text - fuer ``cli generationen``.

    ``intervall`` hebt die Generationen hervor, die zu dieser Kerzenlaenge
    passen, und nennt ihre Summe. Das ist die Zahl, die ``vorratsdecke``
    faehrt, und sie ist eine andere als die einer einzelnen Generation -
    siehe den Modulkopf.
    """
    from research.seeds import passt_zum_intervall

    bilder = uebersicht()
    zeilen = [
        "Generationen - Nummer, vorgesehene Kerzenlaenge, Inhalt",
        "",
        "  Gen  Int  Inhalt",
        "  " + "-" * 50,
    ]
    for b in bilder:
        marke = ""
        if intervall is not None:
            marke = "->" if passt_zum_intervall(b.nummer, intervall) else "  "
        zeilen.append(marke + b.zeile())

    neueste = bilder[-1]
    zeilen += [
        "",
        f"**Die neueste ist {neueste.nummer}** "
        f"({neueste.intervall or 'frei'}, {neueste.genome} Genome). "
        f"'cli wettbewerb' faehrt genau **eine** Generation, nicht alle - "
        f"was widerlegt ist, muss nicht erneut geprueft werden, und jeder "
        f"Wiederholungsversuch hebt die Huerde fuer alle folgenden.",
    ]
    if intervall is not None:
        passend = [b for b in bilder if passt_zum_intervall(b.nummer, intervall)]
        summe = sum(b.genome for b in passend)
        zeilen.append(
            f"Auf '{intervall}' passen {len(passend)} Generationen mit "
            f"{summe} Genomen zusammen - das ist die Zahl, die "
            f"'cli vorratsdecke -i {intervall}' faehrt, und sie kostet "
            f"keinen Versuch."
        )

    mit = [b for b in bilder if b.finanzierung]
    if mit:
        zeilen.append(
            "Finanzierungsdaten brauchen nur die Generationen "
            + ", ".join(f"{b.nummer} ({len(b.finanzierung)})" for b in mit)
            + ". Ohne sie im Speicher fallen diese Regeln still heraus - "
            "'cli funding' laedt sie nach."
        )
    return "\n".join(zeilen)
