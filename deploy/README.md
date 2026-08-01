# Einrichtung auf dem Server

Von einem leeren Server bis zum laufenden Demo-Handel. Rechne mit 30 Minuten,
davon 10 Minuten Warten auf den Backfill.

Jeder Block ist zum Kopieren. Wo `DEINSERVER` oder `DEINNAME` steht, setzt du
deins ein.

---

## 0. Anbieter und Standort

**Hetzner Cloud CX22** — 2 vCPU, 4 GB RAM, 40 GB SSD, **~4,51 €/Monat**.
Reichlich für diese Aufgabe; der Bot braucht im Betrieb unter 300 MB.

**Standort: Nürnberg oder Falkenstein.** Also Deutschland — dort, wo du bist.

Das ist bewusst so und nicht verhandelbar: Ein Server im Ausland, nur damit
Bybit die Verbindung durchlässt, wäre ein Umgehen der Regionssperre. Das
verstößt gegen Bybits Nutzungsbedingungen und kostet im Zweifel das Konto —
mitsamt dem Geld darauf. Wenn Bybit deine Region für Derivate nicht bedient,
ist die richtige Antwort, das System auf Spot umzubauen oder zu einer in der
EU lizenzierten Börse zu wechseln. Nicht, drumherum zu routen.

**Betriebssystem: Ubuntu 24.04 LTS.**

### Zuerst: SSH-Schlüssel auf deinem eigenen Rechner

**Vor** dem Anlegen des Servers, nicht danach. Wer den Schritt überspringt,
bekommt ein Root-Passwort per E-Mail — und ein Passwort, das per E-Mail
verschickt wurde, gehört nicht auf eine Maschine mit einem API-Schlüssel
darauf.

Terminal öffnen (macOS: *Terminal*, Windows: *PowerShell*, Linux: was du hast):

```bash
ssh-keygen -t ed25519 -C "trading"
```

Dreimal Enter — Standardpfad, kein Passwort auf dem Schlüssel (oder eins, wenn
du magst). Dann den **öffentlichen** Teil anzeigen:

```bash
cat ~/.ssh/id_ed25519.pub          # macOS / Linux
type $env:USERPROFILE\.ssh\id_ed25519.pub    # Windows PowerShell
```

Die Ausgabe beginnt mit `ssh-ed25519 AAAA…` und endet mit `trading`. Das ist
die Zeile, die gleich bei Hetzner eingefügt wird. Sie ist **öffentlich** und
darf gezeigt werden — anders als die Datei ohne `.pub` daneben, die niemals
irgendwohin kopiert wird.

### Server anlegen

1. Konto anlegen auf **console.hetzner.cloud** (Ausweis wird geprüft, dauert
   meist wenige Minuten).
2. **Neues Projekt** anlegen, z. B. „Trading".
3. **Server erstellen**, dann:

| Feld | Auswahl |
|---|---|
| Standort | **Nürnberg** oder **Falkenstein** |
| Image | **Ubuntu 24.04** |
| Typ | Shared vCPU → x86 → **CX22** |
| Netzwerk | IPv4 anlassen |
| SSH-Key | **Hinzufügen** → die `ssh-ed25519 …`-Zeile einfügen |
| Backups | optional, +20 % — kann man später zuschalten |
| Name | z. B. `trading` |

4. **Erstellen & kaufen.** Nach etwa 30 Sekunden steht die IPv4-Adresse oben
   im Server-Übersichtsfenster. Das ist dein `DEINSERVER`.

Abgerechnet wird stundenweise. Löschst du den Server nach einer Woche wieder,
kostet er auch nur diese Woche.

---

## 1. Erste Verbindung und Grundabsicherung

Auf diesem Server liegt gleich ein API-Schlüssel. Die zehn Minuten hier sind
gut angelegt.

```bash
ssh root@DEINSERVER
```

```bash
# Aktualisieren
apt update && apt upgrade -y

# Eigenes Konto statt root
adduser --disabled-password --gecos "" trading
usermod -aG sudo trading
rsync --archive --chown=trading:trading ~/.ssh /home/trading

# Passwort-Anmeldung abschalten - nur noch Schlüssel
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh

# Firewall: nur SSH von außen. Das Dashboard bleibt lokal und kommt
# später per SSH-Tunnel aufs Handy.
ufw allow OpenSSH && ufw --force enable

# Sicherheitsupdates automatisch einspielen
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

**Jetzt in einem zweiten Terminal prüfen, dass du noch reinkommst**, bevor du
das erste schließt:

```bash
ssh trading@DEINSERVER
```

---

## 2. Projekt einrichten

Als Benutzer `trading`:

```bash
sudo apt install -y python3.12-venv git
git clone https://github.com/DEINNAME/Trading.git
cd Trading
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev,api,research]"
mkdir -p logs state
```

---

## 3. Zugangsdaten

Auf Bybit einen **neuen** Demo-Key anlegen — Profil → *Demo Trading* → API.

- **Read-Write** (Read-Only kann keine Order platzieren)
- nur *Unified Trading → Trade*
- **Withdrawal: niemals**
- IP-Whitelist auf die IP dieses Servers

Dann auf dem Server:

```bash
.venv/bin/python -m cli setup
```

Der Schlüssel wird abgefragt, nicht als Argument übergeben — ein Argument
stünde in der Prozessliste und in der Shell-History.

---

## 4. Der Moment der Wahrheit

```bash
.venv/bin/python -m cli healthcheck
```

**Grün?** Weiter mit Schritt 5.

**„Bybit blockt Anfragen aus der Region dieses Hosts"?** Dann bedient Bybit
deinen Standort nicht. Hör hier auf und melde dich — wir bauen dann auf Spot
um oder suchen eine in der EU lizenzierte Börse. Nicht weitermachen und nicht
umgehen.

---

## 5. Daten und Strategie

```bash
.venv/bin/python -m cli backfill        # ~8 Minuten, resumierbar
.venv/bin/python -m cli quality         # Lücken, Duplikate, Ausreißer
.venv/bin/python -m cli research        # Walk-Forward + neun Gates
```

`research` läuft einige Minuten. Wahrscheinlich besteht **kein** Kandidat —
das ist ein Ergebnis, kein Fehler. Die Begründungen stehen darunter und sind
die Grundlage für die nächste Generation.

Erst wenn `strategies/champion.json` existiert, kann gehandelt werden.

---

## 6. Als Dienst einrichten

Damit der Bot einen Neustart des Servers überlebt:

```bash
sudo cp deploy/trading-bot.service deploy/trading-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot trading-dashboard
```

Nachsehen, ob beide laufen:

```bash
systemctl status trading-bot trading-dashboard
tail -f logs/bot.log
```

---

## 7. Dashboard aufs iPhone

Das Dashboard hört nur lokal. Von außen kommst du per SSH-Tunnel dran — auf
dem iPhone mit einer SSH-App wie *Termius* oder *Blink*:

```bash
ssh -L 8000:localhost:8000 trading@DEINSERVER
```

Dann im Browser `http://localhost:8000` öffnen, *Teilen → Zum Home-Bildschirm*.
Ab da verhält es sich wie eine App.

Für die Steuerung (Pause, Glattstellen, Not-Aus) muss ein Passwort gesetzt
sein — sonst startet nur der Nur-Lese-Betrieb:

```bash
nano .env        # WEB__PASSWORD=... eintragen
sudo systemctl restart trading-dashboard
```

---

## 8. Der Härtetest

Der wichtigste Schritt der ganzen Einrichtung. Sobald der Bot die erste
Position offen hat:

```bash
sudo systemctl kill -s SIGKILL trading-bot
```

Dann **bei Bybit im Browser nachsehen**: Hängt der Stop noch an der Position?

Er muss. Genau dafür wird er dort gesetzt und nicht im Arbeitsspeicher
gehalten. `systemd` startet den Prozess nach 30 Sekunden neu, er findet die
Position, prüft ihren Stop und übernimmt sie.

Wenn dieser Test durchgeht, ist das System betriebsfähig. Wenn nicht, ist alles
andere egal.

---

## Danach

```bash
.venv/bin/python -m cli review      # einmal pro Woche, nicht täglich
```

Läuft die Strategie noch wie im Backtest? In welcher Marktphase funktioniert
sie? Sitzen Stop und Ziele richtig? Wer täglich draufschaut, reagiert auf
Rauschen.

Nach 30 Tagen Demo entscheiden wir über echtes Geld — anhand der Kriterien,
nicht des Kalenders.
