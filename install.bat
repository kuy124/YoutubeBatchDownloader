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

:: Check for FFmpeg locally and globally
echo.
echo Checking for FFmpeg...
if exist tools\ffmpeg.exe (
    echo [OK] Local FFmpeg binary detected.
    goto ffmpeg_ok
)
where ffmpeg >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Global system FFmpeg detected on PATH.
    goto ffmpeg_ok
)

:: If FFmpeg is missing, attempt to download the lightweight build automatically
echo [INFO] FFmpeg not found. Downloading lightweight binary (37MB)...
powershell -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-win-64.zip' -OutFile 'ffmpeg.zip' -ErrorAction Stop; echo '[OK] Download complete. Extracting...'; Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'temp_ffmpeg' -Force; Copy-Item 'temp_ffmpeg\ffmpeg.exe' -Destination 'tools\ffmpeg.exe'; Remove-Item 'ffmpeg.zip' -Force; Remove-Item 'temp_ffmpeg' -Recurse -Force; echo '[OK] Lightweight FFmpeg successfully installed to tools!' } catch { echo '[ERROR] Failed to download FFmpeg automatically. Please install it manually as described in README.' }"

:ffmpeg_ok
echo.
echo ========================================================
echo Installation complete! 
echo You can now run the application using: run.bat
echo ========================================================
pause