@echo off
cd /d "%~dp0"
python viewer.py --grid-map
if errorlevel 1 pause
