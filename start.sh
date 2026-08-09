#!/usr/bin/env bash
# Startet Handel und Website auf macOS oder Linux.
#
# Auf einem Server benutzt man stattdessen die systemd-Dienste aus deploy/ -
# die ueberleben auch einen Neustart der Maschine.
set -u
cd "$(dirname "$0")"

# --anlagentest faehrt den **Technik-Test** auf Demo: einen Kandidaten, der
# die Gates noch nicht bestanden hat. Absichtlich ein eigener Schalter und
# kein stiller Rueckfall - wer ihn tippt, weiss, dass hier die Klempnerei
# geprueft wird und nicht die Strategie. Echtes Geld bleibt darauf gesperrt;
# das erzwingt "cli trade" selbst ueber die Kennung.
STRATEGIE=""
if [ "${1:-}" = "--anlagentest" ]; then
    STRATEGIE="strategies/anlagentest.json"
fi

if [ ! -x .venv/bin/python ]; then
    echo "Das System ist noch nicht eingerichtet. Zuerst:  python3 install.py"
    exit 1
fi

if [ -n "$STRATEGIE" ]; then
    if [ ! -f "$STRATEGIE" ]; then
        echo "Es gibt noch keine Anlagentest-Datei."
        echo "Zuerst:  .venv/bin/python -m cli anlagentest"
        exit 1
    fi
    echo "ANLAGENTEST - nicht zugelassene Strategie, nur Technik."
    echo "Die dreissig Tage Demo aus dem Plan beginnen hiermit nicht."
    echo
elif [ ! -f strategies/champion.json ]; then
    echo "Es gibt noch keine zugelassene Strategie."
    echo "Zuerst:  .venv/bin/python -m cli research"
    echo
    echo "Ohne geprueffte Strategie wird nicht gehandelt - das ist Absicht."
    echo "Nur die Technik pruefen:  ./start.sh --anlagentest"
    exit 1
fi

.venv/bin/python -m cli dashboard &
DASHBOARD=$!
trap 'kill $DASHBOARD 2>/dev/null' EXIT

echo "Website: http://localhost:8000"
echo

versuche=0
while true; do
    if [ -n "$STRATEGIE" ]; then
        .venv/bin/python -m cli trade --strategie "$STRATEGIE" && break
    else
        .venv/bin/python -m cli trade && break
    fi

    versuche=$((versuche + 1))
    if [ "$versuche" -ge 5 ]; then
        echo "Fuenf Fehlstarts hintereinander. Siehe logs/bot.log."
        exit 1
    fi
    echo "Unerwartet beendet (Versuch $versuche von 5). Neustart in 30 s."
    sleep 30
done

echo "Beendet. Offene Positionen behalten ihren Stop bei Bybit."
