@echo off
cd /d "%~dp0"
python viewer.py --vector-map
if errorlevel 1 pause
