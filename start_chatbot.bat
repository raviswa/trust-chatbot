@echo off
setlocal enabledelayedexpansion
title Trust AI — Chatbot Server

:: ============================================================
::  TRUST AI — Chatbot Startup Script
::  Auto-starts Qdrant, then launches FastAPI on port 8001
:: ============================================================

:: Change to the folder where this BAT file lives
cd /d "%~dp0"

echo.
echo  ============================================================
echo   TRUST AI  ^|  Mental Health Chatbot Engine
echo   Folder: %~dp0
echo  ============================================================
echo.

:: ── 1. Check Python ──────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Python   : %%v

:: ── 2. Check required files ───────────────────────────────────
echo  Checking required files...

set MISSING=0
for %%f in (chatbot_engine.py conversational_intake.py rag_pipeline.py ethical_policy.py language_sanitiser.py db.py intents.json requirements.txt) do (
    if not exist "%%f" (
        echo  [ERROR] Missing file: %%f
        set MISSING=1
    )
)
if !MISSING! == 1 (
    echo.
    echo  One or more required files are missing.
    echo  Make sure all .py files are in the same folder as this BAT file.
    pause
    exit /b 1
)
echo  All required files found.

:: ── 3. Install / verify dependencies ─────────────────────────
echo.
echo  Checking dependencies (requirements.txt)...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check 2>nul
if errorlevel 1 (
    echo  [WARNING] Some packages may not have installed correctly.
    echo            The PostgreSQL TLS warning is safe to ignore.
) else (
    echo  Dependencies OK.
)

:: ── 4. Start Qdrant if not already running ────────────────────
echo.
echo  Checking Qdrant (vector store)...
curl -s http://localhost:6333/healthz >nul 2>&1
if errorlevel 1 (
    echo  Qdrant not running — starting from C:\Qdrant...
    if exist "C:\Qdrant\qdrant.exe" (
        start "Qdrant" /min "C:\Qdrant\qdrant.exe"
        echo  Waiting for Qdrant to initialise...
        timeout /t 5 /nobreak >nul
        :: Verify it started
        curl -s http://localhost:6333/healthz >nul 2>&1
        if errorlevel 1 (
            echo  [WARNING] Qdrant still not responding. RAG retrieval may not work.
            echo            Try starting C:\Qdrant\qdrant.exe manually first.
        ) else (
            echo  Qdrant     : Started successfully on port 6333
        )
    ) else (
        echo  [WARNING] C:\Qdrant\qdrant.exe not found.
        echo            Please check your Qdrant installation path.
    )
) else (
    echo  Qdrant     : Already running on port 6333
)

:: ── 5. Check Ollama is running ────────────────────────────────
echo.
echo  Checking Ollama (local LLM)...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] Ollama does not appear to be running on port 11434.
    echo            Start Ollama first: run 'ollama serve' in a separate terminal.
    echo            The chatbot will still start but LLM calls will fail.
) else (
    echo  Ollama     : Running on port 11434
)

:: ── 6. Check .env file ────────────────────────────────────────
if not exist ".env" (
    echo.
    echo  [WARNING] .env file not found. Database and API keys may not be configured.
)

:: ── 7. Quick Python import check ─────────────────────────────
echo.
echo  Verifying Python imports...
python -c "import fastapi, uvicorn, ollama, qdrant_client; print('  Core imports OK')" 2>nul
if errorlevel 1 (
    echo  [ERROR] One or more Python packages failed to import.
    echo          Try running: pip install -r requirements.txt
    echo          If psycopg2 fails on Python 3.14: pip install psycopg2-binary --pre
    pause
    exit /b 1
)

:: ── 8. Print endpoint summary ─────────────────────────────────
echo.
echo  ============================================================
echo   API ENDPOINTS  ^|  http://127.0.0.1:8001
echo  ============================================================
echo.
echo   CORE CHAT
echo   POST  /chat                           Send a message
echo   POST  /session/start                  Open app (triggers intake or check-in)
echo   POST  /session/clear                  Reset session
echo.
echo   INTAKE + CHECK-IN
echo   GET   /session/{id}/intake-profile    Full intake profile
echo   GET   /session/{id}/checkin-data      Today's check-in data
echo   GET   /session/{id}/summary           Session summary
echo   GET   /session/{id}/history           Full conversation history
echo.
echo   PATIENT
echo   GET   /patient/{code}                 Patient profile
echo   GET   /patient/{code}/sessions        All sessions
echo   GET   /patient/{code}/history         Full history
echo.
echo   ADMIN
echo   GET   /admin/sessions                 All sessions
echo   GET   /admin/crisis                   Crisis sessions
echo   GET   /admin/crisis/pending           Unreviewed crisis events
echo   GET   /admin/stats                    Conversation stats
echo   GET   /admin/intents                  Top intents
echo   GET   /admin/policy/violations        Policy violation log
echo.
echo   OTHER
echo   GET   /health                         Server health check
echo   GET   /policy                         Ethical policy summary
echo   GET   /documents                      Ingested PDF list
echo   Docs  /docs                           Swagger UI (auto-generated)
echo.
echo  ============================================================
echo   Starting server on http://127.0.0.1:8001 ... (Ctrl+C to stop)
echo  ============================================================
echo.

:: ── 9. Start FastAPI server ───────────────────────────────────
python -m uvicorn chatbot_engine:app --host 127.0.0.1 --port 8001 --reload

:: ── 10. On exit ───────────────────────────────────────────────
echo.
echo  Server stopped.
pause
