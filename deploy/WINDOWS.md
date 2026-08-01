# Auf dem eigenen Windows-Rechner

Ohne Fachwörter. Jeder Schritt einzeln. Nach jedem kurz schauen, ob etwas
Rotes im Fenster steht — wenn ja, aufhören und den Text schicken.

---

## Was du am Ende hast

Ein Programm, das auf deinem PC läuft und automatisch handelt, und eine
Website, die du im Browser und auf dem Handy aufrufen kannst.

Solange dein Rechner an ist, handelt es. Ist er aus, handelt es nicht — aber
**offene Positionen bleiben geschützt**, weil ihre Stops bei Bybit liegen und
nicht auf deinem Rechner.

---

## Schritt 1: Python installieren

Python ist die Sprache, in der das Programm geschrieben ist. Windows hat sie
nicht ab Werk.

1. Auf **python.org/downloads** gehen
2. Den großen gelben Knopf drücken (*Download Python 3.13.x*)
3. Die heruntergeladene Datei starten

**Ganz wichtig, im ersten Fenster des Installers:**

> ☑ **Add python.exe to PATH**

Das Häkchen ist unten und standardmäßig **aus**. Ohne es findet dein Rechner
Python später nicht, und nichts von dem hier funktioniert. Erst danach auf
*Install Now*.

---

## Schritt 2: Das Fenster öffnen, in das man tippt

Windows-Taste drücken, `powershell` tippen, Enter.

Es öffnet sich ein blaues oder schwarzes Fenster. Das ist die Kommandozeile.
Hier tippt man Befehle statt zu klicken.

Zum Prüfen, ob Schritt 1 geklappt hat, tippe:

```
python --version
```

Erscheint so etwas wie `Python 3.13.1`, ist alles gut.

Erscheint stattdessen eine Fehlermeldung oder öffnet sich der Microsoft Store,
dann wurde das Häkchen aus Schritt 1 vergessen. Python nochmal installieren,
diesmal mit Häkchen.

---

## Schritt 3: Das Programm herunterladen

Immer noch im selben Fenster:

```
cd $env:USERPROFILE\Documents
git clone https://github.com/DEINNAME/Trading.git
cd Trading
```

Falls dabei steht, dass `git` unbekannt ist: `git` von **git-scm.com**
installieren (alle Vorgaben einfach übernehmen), PowerShell schließen, neu
öffnen, und die drei Zeilen nochmal.

---

## Schritt 4: Einrichten

```
python install.py
```

Das dauert ein bis drei Minuten und lädt etwa 150 MB. Am Ende steht dort, wie
es weitergeht.

Kommt eine Fehlermeldung: Der Text im Fenster sagt, woran es lag. Schick ihn
mir, auch wenn er lang aussieht.

---

## Schritt 5: Bybit verbinden

Vorher auf Bybit einen **Demo**-Schlüssel anlegen:

- Profil oben rechts → **Demo Trading**
- Dort auf API → neuen Schlüssel erstellen
- **Read-Write** (nicht Read-Only — der kann keine Orders aufgeben)
- Nur *Unified Trading → Trade* anhaken
- **Withdrawal: niemals**
- IP-Whitelist: **leer lassen**

> Warum keine IP-Whitelist: Deine Internetadresse zu Hause wechselt meistens
> täglich. Ein Schlüssel, der auf eine feste Adresse festgelegt ist, wäre
> morgen gesperrt. Ohne Whitelist läuft er 90 Tage — für die Demo reicht das.
> Auf einem Server später tragen wir sie ein.

Dann im PowerShell-Fenster:

```
.venv\Scripts\python -m cli setup
```

Es fragt nach Schlüssel und Geheimnis. Das Geheimnis siehst du beim Tippen
nicht — das ist Absicht, nicht kaputt. Einfach einfügen und Enter.

Danach prüft es sofort die Verbindung. **Alles grün? Weiter.**
Steht dort etwas von „Region blockiert", hör auf und sag mir Bescheid.

---

## Schritt 6: Kursdaten laden

```
.venv\Scripts\python -m cli backfill
```

Rund 8 Minuten. Es lädt sechs Jahre Bitcoin-Kurse. Läuft ein Balken durch,
alles in Ordnung.

Dann prüfen, ob die Daten sauber sind:

```
.venv\Scripts\python -m cli quality
```

---

## Schritt 7: Strategie suchen

```
.venv\Scripts\python -m cli research
```

Dauert einige Minuten. Am Ende steht eine Tabelle.

**Wahrscheinlich steht dort, dass keine Strategie bestanden hat.** Das ist
kein Fehler, sondern der Sinn der Sache: Es wird nur gehandelt, was neun
Prüfungen übersteht. Darunter steht bei jeder Strategie, woran sie
gescheitert ist — daraus baue ich die nächste Generation.

---

## Schritt 8: Loslaufen lassen

Erst wenn Schritt 7 eine Strategie gefunden hat:

Doppelklick auf **`start.bat`** im Ordner.

Es öffnen sich zwei Fenster. Beide offen lassen. Im Browser
**http://localhost:8000** aufrufen — das ist deine Website.

Aufs Handy kommt sie später, wenn wir auf einen Server umziehen. Solange der
Rechner zu Hause steht, geht sie nur an diesem Rechner.

---

## Wenn Windows neu startet

Damit der Handel danach von selbst weiterläuft:

1. Rechtsklick auf `start.bat` → **Verknüpfung erstellen**
2. Windows-Taste + R drücken, `shell:startup` eingeben, Enter
3. Die Verknüpfung in den geöffneten Ordner ziehen

Ab jetzt startet es beim Hochfahren mit.

---

## Wenn etwas nicht läuft

Im Ordner `logs` liegt `bot.log`. Ganz unten steht, was zuletzt passiert ist.
Diesen letzten Teil schicken — daran lässt sich fast immer erkennen, woran es
liegt.

Und der Satz, der immer gilt: **Solange eine Position offen ist, hängt ihr
Stop bei Bybit.** Er wirkt weiter, auch wenn dein Rechner aus ist, das
Programm abgestürzt ist oder das Internet weg ist. Genau dafür wird er dort
gesetzt und nicht hier.
