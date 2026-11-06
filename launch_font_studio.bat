@echo off
chcp 65001 > nul
title FNV Thai Font Tuning Studio
echo ========================================================
echo   FNV Thai Font Tuning Studio (Fallout: New Vegas)
echo   Live Preview and In-Game Font Tuning Tool
echo ========================================================
echo.
echo Starting web server at http://localhost:8766 ...
echo Press Ctrl+C in this terminal when you want to stop.
echo.
start "" http://localhost:8766
python "%~dp0pipeline\font_studio.py"
pause
