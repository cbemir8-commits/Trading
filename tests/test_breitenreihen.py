"""Der dokumentierte Weg liess eine Familie des Scans ausfallen - Befund 435.

``cli scan`` prueft vier Familien, und eine davon ist die **Marktbreite**: die
Spanne, geteilt nach dem Zustand der *uebrigen* Maerkte. Sie braucht zwei
andere Maerkte auf derselben Kerzenlaenge, also drei im Speicher.

``wiederherstellung`` holte zwei - BTC und ETH, die Maerkte, auf denen die
Zulassung steht. ``PAIRS`` fuehrt aber **vier** Forschungsmaerkte, und ohne
die anderen zwei meldet der Scan auf jeder Laenge *"Marktbreite: nicht
gemessen (1 andere Maerkte, noetig 2)"*. Die Schliessung aus Befund 272/276
war damit nicht nachpruefbar.

Nachgeladen reproduziert sie sich: Marktbreite auf BTC 1d bester t = **-3,73**
(dokumentiert -3,74), Verschiebungsprobe **3 von 584** (dokumentiert 2 von
584), und der Teiler wechselt auf 585 Beobachtungen nur **15-mal** seinen
Zustand - das ist der Grund, warum sie faellt.
"""

from __future__ import annotations

from datetime import date, timedelta

from research.datenstand import (
    BREITENANFANG,
    FEINANFANG,
    FEINENDE,
    REIHEN,
    SERIENENDE,
    breitenbefehle,
    breitenreihen,
    speicher_ist_gepinnt,
    wiederherstellung,
)


class TestDieBreitenreihenSindGerechnet:
    def test_sie_sind_pairs_ohne_die_zulassungsmaerkte(self) -> None:
        """Wer hier eine Liste pflegt, hat zwei Listen - und eine davon ist
        irgendwann falsch."""
        from data.reference import PAIRS

        zulassung = {r.symbol for r in REIHEN}

        assert set(breitenreihen()) == set(PAIRS) - zulassung

    def test_heute_sind_das_ltc_und_xrp(self) -> None:
        assert breitenreihen() == ("LTCUSD_BITSTAMP", "XRPUSD_BITSTAMP")

    def test_kein_zulassungsmarkt_ist_dabei(self) -> None:
        """Sonst wuerde der Weg eine Reihe zweimal holen - und die zweite
        Zeile mit anderem Anfang die erste verkuerzen."""
        for reihe in REIHEN:
            assert reihe.symbol not in breitenreihen()


class TestDieEndenSindDieDerZulassungsreihen:
    """Daran haengt das Tor aus Befund 430: ``speicher_ist_gepinnt`` prueft
    die Menge **aller** Endtermine im Speicher."""

    def test_die_tagesreihen_enden_auf_serienende(self) -> None:
        nach = (SERIENENDE + timedelta(days=1)).isoformat()
        zeilen = [z for z in breitenbefehle() if "-i D" in z]

        assert zeilen
        assert all(f"--bis {nach}" in z for z in zeilen), zeilen

    def test_die_feinreihen_enden_auf_feinende(self) -> None:
        zeilen = [z for z in breitenbefehle() if "-i 15" in z]

        assert zeilen
        assert all(f"--bis {FEINENDE.isoformat()}" in z for z in zeilen), zeilen

    def test_ein_anderes_ende_wuerde_das_tor_umwerfen(self) -> None:
        """Die Gegenprobe, ohne die der Absatz oben nur eine Behauptung ist."""
        gepinnt = {
            "BTC D": (date(2012, 1, 1), SERIENENDE, 5355),
            "LTC D": (BREITENANFANG, SERIENENDE, 3301),
        }
        verschoben = dict(gepinnt)
        verschoben["LTC D"] = (BREITENANFANG, SERIENENDE + timedelta(days=1), 3302)

        assert speicher_ist_gepinnt(gepinnt)
        assert not speicher_ist_gepinnt(verschoben)

    def test_der_anfang_ist_der_von_eth(self) -> None:
        """Frueher gibt Bitstamp fuer sie nichts her, und einen Vorlauf koennte
        der Korb ohnehin nicht nutzen (Befund 318)."""
        eth = next(r for r in REIHEN if r.symbol == "ETHUSD_BITSTAMP")

        assert eth.von == BREITENANFANG


class TestBeideIntervalleWerdenGeholt:
    def test_je_markt_eine_tages_und_eine_feinzeile(self) -> None:
        maerkte = breitenreihen()
        befehle = [z for z in breitenbefehle() if z.startswith("python")]

        assert len(befehle) == 2 * len(maerkte)
        for s in maerkte:
            assert sum(1 for z in befehle if f"--symbol {s} " in z) == 2, s

    def test_der_feinanfang_stimmt(self) -> None:
        for z in breitenbefehle():
            if "-i 15" in z:
                assert f"--von {FEINANFANG.isoformat()}" in z, z

    def test_vorher_wird_geraeumt(self) -> None:
        """Ein Speicher, der schon eine laengere Reihe haelt, wird durch ein
        Nachladen nicht kuerzer (Befund 429)."""
        erste = breitenbefehle()[0]

        assert erste.startswith("rm -rf ")
        for s in breitenreihen():
            assert f"candles/{s}/D" in erste
            assert f"candles/{s}/15" in erste


class TestDerWegDecktJetztAlleVierFamilien:
    def test_jeder_forschungsmarkt_kommt_vor(self) -> None:
        """Der Punkt des Befundes: Ohne das faellt eine von vier Familien
        aus, und zwar lautlos genug, dass es Befunde lang unbemerkt bleibt."""
        from data.reference import PAIRS

        text = "\n".join(wiederherstellung())

        for s in PAIRS:
            assert s in text, s

    def test_und_zwar_auf_beiden_kerzenlaengen(self) -> None:
        from data.reference import PAIRS

        zeilen = [z for z in wiederherstellung() if z.startswith("python")]

        for s in PAIRS:
            laengen = {
                "D" if "-i D" in z else "15" for z in zeilen if f"--symbol {s} " in z
            }
            assert laengen == {"D", "15"}, (s, laengen)

    def test_der_abschnitt_nennt_den_grund(self) -> None:
        text = "\n".join(wiederherstellung())

        assert "Marktbreite: nicht gemessen" in text
        assert "Befund 435" in text
