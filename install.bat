@echo off
TITLE YouTube Batch Downloader - Installer
color 0A

echo ========================================================
echo       YouTube Batch Downloader - Installation Setup
echo ========================================================
echo.

:: Check for Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.11 or newer from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [OK] Python detected.

:: Create virtual environment
echo.
echo Creating Python Virtual Environment (venv)...
python -m venv venv
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

:: Activate and install dependencies
echo Activating venv and installing requirements...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

:: Create necessary directories
echo.
echo Creating standard directories...
mkdir downloads 2>nul
mkdir logs 2>nul
mkdir tools 2>nul

echo.
echo ========================================================
echo Installation complete! 
echo.
echo NOTE: For video/audio merging and best quality, please 
echo download FFmpeg (ffmpeg.exe) and place it in the 'tools' folder.
echo.
echo You can now run the application using: run.bat
echo ========================================================
pause