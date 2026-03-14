@echo off
setlocal

cd /d "%~dp0"
title Interview Review - Quick Start

set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Missing virtual environment Python: %PYTHON%
    echo Create .venv and install dependencies first.
    pause
    exit /b 1
)

if not exist ".env" if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [INFO] Created .env from .env.example
)

echo [1/2] Running self-check...
"%PYTHON%" -m scripts.self_check
if errorlevel 1 (
    echo [ERROR] Self-check failed. Fill in .env and retry.
    pause
    exit /b 1
)

if /I "%~1"=="--check" (
    echo [OK] Self-check passed.
    exit /b 0
)

echo [2/2] Starting Streamlit...
"%PYTHON%" -m streamlit run app.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Streamlit exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
