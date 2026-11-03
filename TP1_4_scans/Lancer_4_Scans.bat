@echo off
cd /d "%~dp0"
python ../LD06_Atelier/viewer.py data/scan1.csv data/scan2.csv data/scan3.csv data/scan4.csv --poses poses.json 
if errorlevel 1 pause
