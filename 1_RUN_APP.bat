@echo off
title Avatar Storyteller Engine - GPU Turbo
color 0b
cls

echo ================================================================
echo    AVATAR STORYTELLER VIDEO ENGINE
echo    Ultra-Fast Single-Pass GPU Faceless Video Generator
echo ================================================================
echo.

cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

:: 1. Register portable FFmpeg if present in bin folder
if exist "%~dp0bin\ffmpeg.exe" (
    set "PATH=%~dp0bin;%PATH%"
)

:: 2. Detect working Python interpreter
set "PY_EXE="

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_EXE=python"
    goto :FOUND_PYTHON
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_EXE=py"
    goto :FOUND_PYTHON
)

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    goto :FOUND_PYTHON
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto :FOUND_PYTHON
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :FOUND_PYTHON
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :FOUND_PYTHON
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto :FOUND_PYTHON
)

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
    goto :FOUND_PYTHON
)

echo [ERROR] Python was not detected on your system.
echo Please install Python 3.10+ from https://www.python.org/
echo (Be sure to check 'Add Python to PATH' during installation)
echo.
pause
exit /b 1

:FOUND_PYTHON
echo [OK] Python detected:
%PY_EXE% --version
echo.

:: 3. Check and install dependencies if needed
%PY_EXE% -c "import fastapi, uvicorn, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [Setup] Installing required dependencies from requirements.txt...
    %PY_EXE% -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Check requirements.txt and your internet connection.
        pause
        exit /b 1
    )
    echo [Setup] Dependencies installed successfully!
    echo.
)

echo [Info] Starting Avatar Storyteller Engine...
echo [Info] App will open in Edge/Browser automatically at http://127.0.0.1:8766
echo [Info] Press Ctrl+C or close this window to stop the server.
echo.

%PY_EXE% desktop_launcher.py

if %errorlevel% neq 0 (
    echo.
    echo ================================================================
    echo [ERROR] Application exited with error code: %errorlevel%
    echo ================================================================
    pause
)
