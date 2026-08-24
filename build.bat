@echo off
TITLE Building YouTube Batch Downloader...

:: 1. Force safety check for virtual environment
if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment 'venv' was not found!
    echo Please make sure to run 'install.bat' successfully first.
    echo.
    pause
    exit /b 1
)

:: 2. Activate virtual environment
call venv\Scripts\activate.bat

echo Cleaning previous builds...
if exist build rmdir /s /q build 2>nul
if exist dist rmdir /s /q dist 2>nul
if not exist tools mkdir tools 2>nul

:: 3. Fast FFmpeg check
if exist tools\ffmpeg.exe goto ffmpeg_exists
echo [INFO] tools/ffmpeg.exe is missing. Downloading lightweight build (37MB)...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-win-64.zip' -OutFile 'ffmpeg.zip' -ErrorAction Stop; Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'temp_ffmpeg' -Force; Copy-Item 'temp_ffmpeg\ffmpeg.exe' -Destination 'tools\ffmpeg.exe'; Remove-Item 'ffmpeg.zip' -Force; Remove-Item 'temp_ffmpeg' -Recurse -Force"
:ffmpeg_exists

:: 4. Fast check for PyInstaller executable (Instant 0ms check)
if exist venv\Scripts\pyinstaller.exe goto pyinstaller_ok
echo [INFO] Installing PyInstaller in virtual environment...
pip install pyinstaller --no-cache-dir
:pyinstaller_ok

:: 5. Execute compilation with PyInstaller
echo Compiling lightweight standalone executable...

set PYI_FLAGS=--noconfirm --windowed --onefile ^
    --add-data "tools;tools" ^
    --collect-data yt_dlp ^
    --hidden-import=yt_dlp ^
    --hidden-import=mutagen ^
    --exclude-module av ^
    --exclude-module tkinter ^
    --exclude-module unittest ^
    --exclude-module pydoc ^
    --exclude-module urllib3.contrib.emscripten ^
    --exclude-module PyQt5 ^
    --exclude-module PyQt6 ^
    --exclude-module PySide2 ^
    --exclude-module numpy ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module matplotlib ^
    --exclude-module PIL ^
    --exclude-module IPython ^
    --exclude-module jupyter ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuick ^
    --exclude-module PySide6.QtQuick3D ^
    --exclude-module PySide6.QtPdf ^
    --exclude-module PySide6.QtPdfWidgets ^
    --exclude-module PySide6.QtOpenGL ^
    --exclude-module PySide6.Qt3D ^
    --exclude-module PySide6.QtSvg ^
    --exclude-module PySide6.QtSql ^
    --exclude-module PySide6.QtTest ^
    --exclude-module PySide6.QtWebEngine ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.QtXml ^
    --exclude-module PySide6.QtMultimedia ^
    --exclude-module PySide6.QtMultimediaWidgets ^
    --exclude-module PySide6.QtPositioning ^
    --exclude-module PySide6.QtLocation ^
    --exclude-module PySide6.QtSensors ^
    --exclude-module PySide6.QtSerialPort ^
    --exclude-module PySide6.QtBluetooth ^
    --exclude-module PySide6.QtNfc ^
    --exclude-module PySide6.QtCharts ^
    --exclude-module PySide6.QtDataVisualization ^
    --exclude-module PySide6.QtRemoteObjects ^
    --exclude-module PySide6.QtScxml ^
    --exclude-module PySide6.QtTextToSpeech ^
    --exclude-module PySide6.QtWebChannel ^
    --exclude-module PySide6.QtWebSockets ^
    --exclude-module PySide6.QtNetworkAuth ^
    --exclude-module PySide6.QtPrintSupport ^
    --exclude-module PySide6.QtHelp ^
    --exclude-module PySide6.QtDesigner ^
    --exclude-module PySide6.QtWinExtras

if exist icon.ico (
    pyinstaller %PYI_FLAGS% --add-data "icon.ico;." --icon icon.ico --name "YouTubeBatchDownloader" app/main.py
) else (
    pyinstaller %PYI_FLAGS% --name "YouTubeBatchDownloader" app/main.py
)

echo.
echo ========================================================
echo Build finished! Your lightweight EXE is in the 'dist' folder.
echo ========================================================
pause