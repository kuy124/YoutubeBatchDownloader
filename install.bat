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
echo [INFO] FFmpeg not found. Downloading pinned FFmpeg Essentials 9.0.1...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/GyanD/codexffmpeg/releases/download/9.0.1/ffmpeg-9.0.1-essentials_build.zip' -OutFile 'ffmpeg.zip' -ErrorAction Stop; Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'temp_ffmpeg' -Force; $candidate = Get-ChildItem -Path 'temp_ffmpeg' -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1; if (-not $candidate) { throw 'FFmpeg executable missing from archive' }; Copy-Item $candidate.FullName -Destination 'tools\ffmpeg.exe'; Remove-Item 'ffmpeg.zip' -Force; Remove-Item 'temp_ffmpeg' -Recurse -Force; $sha=[Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead('tools\ffmpeg.exe'); try {$hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLower()} finally {$stream.Dispose(); $sha.Dispose()}; if ($hash -ne '72a489eccd008c2ec2c0a5856c5c75bc3d8bbfa90166c4566865c246445e6aa3') { throw 'Downloaded FFmpeg failed the pinned SHA-256 check' }; echo '[OK] Pinned FFmpeg successfully installed to tools!' } catch { echo '[ERROR] Failed to download or verify FFmpeg automatically. Please install it manually as described in README.' }"

:ffmpeg_ok

:: Check for aria2 locally (optional multi-connection accelerator)
echo.
echo Checking for aria2...
if exist tools\aria2c.exe (
    echo [OK] Local aria2 binary detected.
    goto aria2_ok
)

echo [INFO] aria2 not found. Downloading optional accelerator (~4MB)...
powershell -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip' -OutFile 'aria2.zip' -ErrorAction Stop; Expand-Archive -Path 'aria2.zip' -DestinationPath 'temp_aria2' -Force; Copy-Item 'temp_aria2\aria2-1.37.0-win-64bit-build1\aria2c.exe' -Destination 'tools\aria2c.exe'; Remove-Item 'aria2.zip' -Force; Remove-Item 'temp_aria2' -Recurse -Force; echo '[OK] aria2 installed to tools!' } catch { echo '[WARN] aria2 download failed (optional component, app works without it).' }"

:aria2_ok
echo.
echo ========================================================
echo Installation complete! 
echo You can now run the application using: run.bat
echo ========================================================
pause
