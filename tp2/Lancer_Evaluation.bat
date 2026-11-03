@echo off
cd /d "%~dp0\.."
python tp2/evaluer.py
if errorlevel 1 goto erreur
python tp2/creer_rapport.py
if errorlevel 1 goto erreur
echo Evaluation terminee. Pour mettre a jour le PDF, compiler tp2\rapport_tp2.tex.
exit /b 0
:erreur
echo Erreur pendant l'evaluation TP2.
pause
exit /b 1
