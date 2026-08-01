@echo off
REM ===================================================================
REM  Startet Handel und Website.
REM
REM  Doppelklick genuegt. Es oeffnen sich zwei Fenster:
REM    - eines fuer den Handel
REM    - eines fuer die Website
REM  Beide muessen offen bleiben. Zum Beenden die Fenster schliessen.
REM
REM  Faellt der Handel aus, startet er nach 30 Sekunden von selbst neu.
REM  Offene Positionen sind davon unberuehrt: Ihr Stop liegt bei Bybit
REM  und wirkt weiter, auch waehrend hier gar nichts laeuft.
REM ===================================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   Das System ist noch nicht eingerichtet.
    echo   Fuehre zuerst aus:   python install.py
    echo.
    pause
    exit /b 1
)

if not exist "strategies\champion.json" (
    echo.
    echo   Es gibt noch keine zugelassene Strategie.
    echo   Fuehre zuerst aus:   .venv\Scripts\python -m cli research
    echo.
    echo   Ohne gepruefte Strategie wird nicht gehandelt - das ist Absicht.
    echo.
    pause
    exit /b 1
)

echo Starte die Website in einem eigenen Fenster ...
start "Trading - Website" .venv\Scripts\python -m cli dashboard

echo.
echo ===================================================================
echo   Handel laeuft. Dieses Fenster offen lassen.
echo   Website:  http://localhost:8000
echo ===================================================================
echo.

set FEHLVERSUCHE=0

:schleife
.venv\Scripts\python -m cli trade

REM Beendet man mit Strg-C, ist das kein Absturz - dann nicht neu starten.
if %ERRORLEVEL% EQU 0 goto ende

set /a FEHLVERSUCHE+=1
echo.
echo   Der Handel wurde unerwartet beendet (Versuch %FEHLVERSUCHE% von 5).

REM Fuenfmal hintereinander heisst: echtes Problem. Dann ist Stillstand
REM besser als ein Roboter, der endlos neu startet.
if %FEHLVERSUCHE% GEQ 5 (
    echo.
    echo   Fuenf Fehlstarts hintereinander. Hier stimmt etwas nicht.
    echo   Schau in logs\bot.log - und schick mir, was dort am Ende steht.
    echo.
    pause
    exit /b 1
)

echo   Neustart in 30 Sekunden. Zum Abbrechen dieses Fenster schliessen.
timeout /t 30 /nobreak > nul
goto schleife

:ende
echo.
echo   Beendet. Offene Positionen behalten ihren Stop bei Bybit.
pause
