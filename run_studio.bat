@echo off
chcp 65001 >nul
title ThaiFNV Translation Studio Web App
echo ========================================================
echo  Starting ThaiFNV Translation Studio Web App...
echo  Opening browser at http://127.0.0.1:8765
echo ========================================================
start http://127.0.0.1:8765
python pipeline/local_web_app.py
pause
