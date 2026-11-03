@echo off
cd /d "%~dp0\.."
python tp2/evaluer.py
if errorlevel 1 pause
