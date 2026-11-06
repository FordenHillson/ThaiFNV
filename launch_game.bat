@echo off
cd /d "d:\SteamLibrary\steamapps\common\Fallout New Vegas"
if exist "nvse_loader.exe" (
    start "" "nvse_loader.exe"
) else (
    start "" "FalloutNV.exe"
)
