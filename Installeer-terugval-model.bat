@echo off
rem ============================================================
rem  Installeer-terugval-model.bat  (OPTIONEEL)
rem  Zet de offline TERUGVAL aan voor talen die Argos NIET kent
rem  (zoals Papiaments). Dit doet twee dingen, eenmalig:
rem    1) installeert llama-cpp-python (AVX2-wheel; past o.a. Ryzen 5 3600)
rem    2) zorgt voor een KLEIN lokaal model in DraveTranslate-data\model
rem       -> zo is de app SELF-CONTAINED en werkt het op elke pc.
rem  (Staat er al een DraveMind/DraveAI-model naast, dan kopieren we dat
rem   i.p.v. opnieuw downloaden.)
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist ".venv" (
  echo Maak eerst de omgeving met run.bat ^(start de app^) en probeer dan opnieuw.
  pause & exit /b 1
)
call ".venv\Scripts\activate.bat"

echo [1/2] llama-cpp-python installeren (kant-en-klare AVX2-wheel)...
python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2 llama-cpp-python
if errorlevel 1 (
  echo AVX2-wheel mislukt, ik probeer de standaard (basis)-wheel...
  python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/basic llama-cpp-python
)

set "MDIR=DraveTranslate-data\model"
if not exist "%MDIR%" mkdir "%MDIR%"

rem --- staat er al een model? ---
set FOUND=
for %%F in ("%MDIR%\*.gguf") do set FOUND=1
if defined FOUND ( echo Lokaal model al aanwezig. & goto done )

rem --- bestaand DraveMind/DraveAI-model hergebruiken (kopieren) ---
for %%S in ("..\DraveMind\DraveMind-data\model" "..\DraveAI\DraveMind-data\model") do (
  if not defined FOUND if exist "%%~S" (
    for %%F in ("%%~S\qwen2.5-3b-instruct*.gguf" "%%~S\qwen2.5-1.5b-instruct*.gguf") do (
      if not defined FOUND if exist "%%F" (
        echo Bestaand model gevonden - kopieren naar de app-map...
        copy "%%F" "%MDIR%\" >nul && set FOUND=1
      )
    )
  )
)
if defined FOUND ( goto done )

echo [2/2] Klein model downloaden (~1 GB, eenmalig)...
python -m pip install huggingface_hub
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Qwen/Qwen2.5-1.5B-Instruct-GGUF', filename='qwen2.5-1.5b-instruct-q4_k_m.gguf', local_dir='DraveTranslate-data/model')"

:done
echo.
echo Klaar. Start DraveTranslate opnieuw. Talen als Papiaments lopen nu via het
echo lokale model (kwaliteit is wisselend; de Argos-talen blijven het beste).
echo.
pause
endlocal
