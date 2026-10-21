@echo off
rem === herstel.bat - ruimt de omgeving + build-mappen op ===
cd /d "%~dp0"
echo Dit verwijdert .venv, build en dist (de app/code blijft staan).
pause
rmdir /s /q .venv 2>nul
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
echo Klaar.
pause
