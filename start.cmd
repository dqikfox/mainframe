@echo off
REM THRONE Mainframe launcher
REM Installs + starts health daemon and registers Ollama as Windows Service

setlocal
set HERMES=%LOCALAPPDATA%\hermes
set SCRIPTS=%HERMES%\scripts

REM 1. Health daemon (proxy to Ollama + host stats)
echo Starting THRONE health daemon on :11435...
start "THRONE-Health" /B python "%SCRIPTS%\ollama-server.py"

REM 2. Confirm Ollama is reachable
echo Probing Ollama :11434...
curl -s -o nul -w "  ollama HTTP %{http_code}\n" http://127.0.0.1:11434/api/tags

REM 3. Register Ollama as Windows Service (idempotent)
sc.exe query Ollama >nul 2>&1
if errorlevel 1 (
    echo Registering Ollama Windows Service...
    sc.exe create Ollama binPath= "\"C:\Users\KING\AppData\Local\Programs\Ollama\ollama.exe\" serve" start= auto
    sc.exe description Ollama "Local Ollama LLM server (auto-start)"
)

REM 4. Probe health daemon
echo Probing THRONE health daemon...
curl -s -o nul -w "  THRONE HTTP %{http_code}\n" http://127.0.0.1:11435/health

REM 5. Run throttle audit
echo Running throttle audit...
python "%SCRIPTS%\throttle-audit.py" --log

echo.
echo THRONE Mainframe started.
echo   Ollama:        http://127.0.0.1:11434
echo   THRONE health: http://127.0.0.1:11435
endlocal