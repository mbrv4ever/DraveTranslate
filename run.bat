@echo off
rem === run.bat - start DraveTranslate (maakt eenmalig de omgeving aan) ===
setlocal
cd /d "%~dp0"

set PY=
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo Geen Python gevonden. Installeer Python 3.10-3.13 van python.org
  pause & exit /b 1
)

if not exist ".venv" (
  echo Eenmalige installatie van de omgeving...
  %PY% -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  rem terugval (voor niet-Argos-talen zoals Papiaments): llama-cpp AVX2-wheel
  python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2 llama-cpp-python
  if errorlevel 1 python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/basic llama-cpp-python
) else (
  call ".venv\Scripts\activate.bat"
)

start "" ".venv\Scripts\pythonw.exe" dravetranslate.py
endlocal
