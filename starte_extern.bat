@echo off
rem Gibt den Reisebot fuer Tester frei (Details siehe starte_extern.py und README.md).
rem Doppelklick genuegt; das Fenster muss waehrend der Tests geoeffnet bleiben.
chcp 65001 >nul
cd /d "%~dp0"
python starte_extern.py
echo.
pause
