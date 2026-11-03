@echo off
cd /d "%~dp0"
python viewer.py --multicolor
if errorlevel 1 pause
