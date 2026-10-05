@echo off
title Avatar Storyteller Engine - Standalone Executable Builder
color 0b

echo ================================================================
echo       AVATAR STORYTELLER ENGINE - STANDALONE EXE BUILDER
echo   Native Windows Desktop Studio (Full GPU Acceleration Enabled)
echo ================================================================
echo.

cd /d "%~dp0"

REM 1. Detect Python Interpreter
set "PY_EXE="
python --version >nul 2>&1 && set "PY_EXE=python"
if not defined PY_EXE (
    py --version >nul 2>&1 && set "PY_EXE=py"
)
if not defined PY_EXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
)

if not defined PY_EXE (
    echo [ERROR] Python was not detected on this system.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Using Python: %PY_EXE%
%PY_EXE% --version
echo.

REM 2. Check and Install PyInstaller and Dependencies
echo [1/6] Verifying PyInstaller and core libraries...
%PY_EXE% -c "import PyInstaller" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo       Installing PyInstaller...
    %PY_EXE% -m pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

%PY_EXE% -c "import fastapi, uvicorn, PIL, requests, webview, pythonnet" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo       Installing required dependencies and native GUI libraries...
    %PY_EXE% -m pip install fastapi uvicorn pillow requests python-multipart pywebview pythonnet
)

REM 3. Verify Portable FFmpeg in bin
echo.
echo [2/6] Checking portable FFmpeg binaries in bin...
if not exist "bin" mkdir "bin"

if not exist "bin\ffmpeg.exe" (
    echo       ffmpeg.exe not found in bin. Searching local paths...
    if exist "..\vg\bin\ffmpeg.exe" (
        copy /y "..\vg\bin\ffmpeg.exe" "bin\ffmpeg.exe" >nul
        copy /y "..\vg\bin\ffprobe.exe" "bin\ffprobe.exe" >nul
        echo       [OK] Borrowed portable FFmpeg from ..\vg\bin\
    ) else if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe" (
        copy /y "%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe" "bin\ffmpeg.exe" >nul
        copy /y "%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe" "bin\ffprobe.exe" >nul
        echo       [OK] Copied FFmpeg from WinGet package into bin\
    )
)

if not exist "bin\ffmpeg.exe" (
    echo [WARNING] bin\ffmpeg.exe is missing!
) else (
    echo       [OK] Portable FFmpeg ready in bin\
)

REM 4. Clean Previous Builds
echo.
echo [3/6] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist\ATSAuthor" rd /s /q "dist\ATSAuthor"
if exist "dist\ATSAuthor-Windows-Portable.zip" del /f /q "dist\ATSAuthor-Windows-Portable.zip" >nul 2>&1

REM 5. Run PyInstaller
echo.
echo [4/6] Compiling ATSAuthor.exe via PyInstaller (ats_author.spec)...
%PY_EXE% -m PyInstaller --clean ats_author.spec -y

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ================================================================
    echo [ERROR] PyInstaller compilation failed! Check error log above.
    echo ================================================================
    pause
    exit /b %ERRORLEVEL%
)

REM 6. Populate Standalone Release Folder
echo.
echo [5/6] Finalizing release package structure...

if not exist "dist\ATSAuthor\bin" mkdir "dist\ATSAuthor\bin"
if exist "bin\ffmpeg.exe" (
    copy /y "bin\ffmpeg.exe" "dist\ATSAuthor\bin\ffmpeg.exe" >nul
    copy /y "bin\ffprobe.exe" "dist\ATSAuthor\bin\ffprobe.exe" >nul
    echo       [+] Bundled portable FFmpeg and FFprobe into dist\ATSAuthor\bin\
)

if not exist "dist\ATSAuthor\data" mkdir "dist\ATSAuthor\data"
if not exist "dist\ATSAuthor\data\output" mkdir "dist\ATSAuthor\data\output"
if not exist "dist\ATSAuthor\data\avatars" mkdir "dist\ATSAuthor\data\avatars"
if not exist "dist\ATSAuthor\data\temp" mkdir "dist\ATSAuthor\data\temp"
if exist "data\settings.json" (
    copy /y "data\settings.json" "dist\ATSAuthor\data\settings.json" >nul
    echo       [+] Bundled data\settings.json
)

if not exist "dist\ATSAuthor\backend\assets\fonts" mkdir "dist\ATSAuthor\backend\assets\fonts"
if exist "backend\assets\fonts" (
    xcopy /e /i /y "backend\assets\fonts" "dist\ATSAuthor\backend\assets\fonts" >nul
    echo       [+] Bundled local viral fonts into dist\ATSAuthor\backend\assets\fonts\
)

if not exist "dist\ATSAuthor\frontend" mkdir "dist\ATSAuthor\frontend"
if exist "frontend" (
    xcopy /e /i /y "frontend" "dist\ATSAuthor\frontend" >nul
    echo       [+] Bundled frontend UI into dist\ATSAuthor\frontend\
)

if exist "documentation.html" (
    copy /y "documentation.html" "dist\ATSAuthor\documentation.html" >nul
    echo       [+] Bundled offline documentation.html
)
if exist "brain.md" (
    copy /y "brain.md" "dist\ATSAuthor\brain.md" >nul
    echo       [+] Bundled brain.md
)

REM Create Quick Launchers
echo @echo off > "dist\ATSAuthor\Launch-ATSAuthor.bat"
echo title Avatar Storyteller Engine >> "dist\ATSAuthor\Launch-ATSAuthor.bat"
echo cd /d "%%~dp0" >> "dist\ATSAuthor\Launch-ATSAuthor.bat"
echo start "" "ATSAuthor.exe" >> "dist\ATSAuthor\Launch-ATSAuthor.bat"

echo @echo off > "dist\ATSAuthor\Launch-Headless-Server.bat"
echo title ATS Author Headless Server (Zero-Window Mode) >> "dist\ATSAuthor\Launch-Headless-Server.bat"
echo cd /d "%%~dp0" >> "dist\ATSAuthor\Launch-Headless-Server.bat"
echo "ATSAuthor.exe" --no-window >> "dist\ATSAuthor\Launch-Headless-Server.bat"

echo ====================================================================== > "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo    AVATAR STORYTELLER ENGINE - 100%% STANDALONE PORTABLE EDITION >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo ====================================================================== >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo HOW TO RUN: >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   Option A (Recommended): Double-click "Launch-ATSAuthor.bat" or "ATSAuthor.exe". >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo     - Opens in a Native Windows Desktop GUI window (WebView2 Runtime). >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo     - Full GPU Hardware Acceleration is ACTIVE for silky 60fps UI and playback. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo     - Not an external browser: Runs as a true native desktop application. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   Option B (Pure Headless): Double-click "Launch-Headless-Server.bat". >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo     - Spawns zero browser window. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo     - Access from any device via: http://127.0.0.1:8766 >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo ZERO SETUP REQUIRED: >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - No Python installation needed (embedded in executable). >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - No FFmpeg installation needed (bundled in bin\). >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - 2-Hour long voiceovers supported with smart parallel chunking. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo OUTPUT LOCATION: >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - Rendered videos are automatically saved in "data\output\". >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - Windows Explorer will automatically open and highlight your video file! >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo ====================================================================== >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"

REM 7. Create Portable ZIP Archive via Fast Python Zip Engine (No PowerShell Resource Leak)
echo.
echo [6/6] Creating portable ZIP archive: dist\ATSAuthor-Windows-Portable.zip ...
%PY_EXE% -c "import zipfile, os; zf = zipfile.ZipFile(r'dist\ATSAuthor-Windows-Portable.zip', 'w', zipfile.ZIP_DEFLATED); [zf.write(os.path.join(r, f), os.path.relpath(os.path.join(r, f), r'dist\ATSAuthor')) for r, d, fs in os.walk(r'dist\ATSAuthor') for f in fs]; zf.close()"

echo.
echo ================================================================
echo [SUCCESS] 100%% Standalone Portable Build Completed!
echo ================================================================
echo.
echo Release Folder:   %~dp0dist\ATSAuthor\
echo Main Executable:  %~dp0dist\ATSAuthor\ATSAuthor.exe
echo Quick Launcher:   %~dp0dist\ATSAuthor\Launch-ATSAuthor.bat
echo Headless Server:  %~dp0dist\ATSAuthor\Launch-Headless-Server.bat
echo Ready-to-Share:   %~dp0dist\ATSAuthor-Windows-Portable.zip
echo.
echo You can now send "ATSAuthor-Windows-Portable.zip" to anyone!
echo They just extract the zip and double-click "ATSAuthor.exe".
echo They do NOT need to install Python, FFmpeg, or anything else.
echo ================================================================
echo.
pause
