@echo off
title Avatar Storyteller Engine - Standalone Executable Builder
color 0b

echo ================================================================
echo       AVATAR STORYTELLER ENGINE - STANDALONE EXE BUILDER
echo   Creates a 100%% Portable Zero-Setup Package for Friends/Clients
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

%PY_EXE% -c "import fastapi, uvicorn, PIL" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo       Installing required dependencies from requirements.txt...
    %PY_EXE% -m pip install -r requirements.txt
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

echo @echo off > "dist\ATSAuthor\Launch-ATSAuthor.bat"
echo title Avatar Storyteller Engine >> "dist\ATSAuthor\Launch-ATSAuthor.bat"
echo cd /d "%%~dp0" >> "dist\ATSAuthor\Launch-ATSAuthor.bat"
echo start "" "ATSAuthor.exe" >> "dist\ATSAuthor\Launch-ATSAuthor.bat"

echo ====================================================================== > "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo    AVATAR STORYTELLER ENGINE - 100%% STANDALONE PORTABLE EDITION >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo ====================================================================== >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo HOW TO RUN: >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   1. Extract the entire ZIP folder to anywhere on your computer. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   2. Double-click "ATSAuthor.exe" or "Launch-ATSAuthor.bat". >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   3. The app starts automatically in an ultra-clean desktop window. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo ZERO SETUP REQUIRED: >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - No Python installation needed (built-in). >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - No FFmpeg installation needed (bundled in bin\). >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - All fonts, templates, and UI are fully included. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo OUTPUT LOCATION: >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - All rendered videos are saved in the "data\output\" folder. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo   - When a video finishes rendering, Windows Explorer will automatically >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo     open and highlight your new video file! >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo. >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"
echo Enjoy creating high-retention faceless storyteller videos! >> "dist\ATSAuthor\README_HOW_TO_RUN.txt"

REM 7. Create Portable ZIP Archive
echo.
echo [6/6] Creating portable ZIP archive: dist\ATSAuthor-Windows-Portable.zip ...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\ATSAuthor\*' -DestinationPath 'dist\ATSAuthor-Windows-Portable.zip' -Force"

echo.
echo ================================================================
echo [SUCCESS] 100%% Standalone Portable Build Completed!
echo ================================================================
echo.
echo Release Folder:   %~dp0dist\ATSAuthor\
echo Main Executable:  %~dp0dist\ATSAuthor\ATSAuthor.exe
echo Quick Launcher:   %~dp0dist\ATSAuthor\Launch-ATSAuthor.bat
echo Ready-to-Share:   %~dp0dist\ATSAuthor-Windows-Portable.zip
echo.
echo You can now send "ATSAuthor-Windows-Portable.zip" to your friend!
echo They just extract the zip and double-click "ATSAuthor.exe".
echo They do NOT need to install Python, FFmpeg, or anything else.
echo ================================================================
echo.
pause
