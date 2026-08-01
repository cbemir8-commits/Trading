#!/usr/bin/env bash
# Startet Handel und Website auf macOS oder Linux.
#
# Auf einem Server benutzt man stattdessen die systemd-Dienste aus deploy/ -
# die ueberleben auch einen Neustart der Maschine.
set -u
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "Das System ist noch nicht eingerichtet. Zuerst:  python3 install.py"
    exit 1
fi

if [ ! -f strategies/champion.json ]; then
    echo "Es gibt noch keine zugelassene Strategie."
    echo "Zuerst:  .venv/bin/python -m cli research"
    echo
    echo "Ohne geprueffte Strategie wird nicht gehandelt - das ist Absicht."
    exit 1
fi

.venv/bin/python -m cli dashboard &
DASHBOARD=$!
trap 'kill $DASHBOARD 2>/dev/null' EXIT

echo "Website: http://localhost:8000"
echo

versuche=0
while true; do
    .venv/bin/python -m cli trade && break

    versuche=$((versuche + 1))
    if [ "$versuche" -ge 5 ]; then
        echo "Fuenf Fehlstarts hintereinander. Siehe logs/bot.log."
        exit 1
    fi
    echo "Unerwartet beendet (Versuch $versuche von 5). Neustart in 30 s."
    sleep 30
done

echo "Beendet. Offene Positionen behalten ihren Stop bei Bybit."
