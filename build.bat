@echo off
TITLE Building YouTube Batch Downloader...

:: 1. Force safety check for virtual environment to prevent silent load crashes
if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment 'venv' was not found!
    echo Please make sure to run 'install.bat' successfully first.
    echo.
    pause
    exit /b 1
)

:: 2. Activate virtual environment safely
call venv\Scripts\activate.bat

echo Cleaning previous builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

:: Ensure tools directory exists
mkdir tools 2>nul

:: 3. Download FFmpeg if missing (Flat block using GOTO to avoid CMD parenthesis bugs)
if exist tools\ffmpeg.exe goto ffmpeg_exists
echo [INFO] tools/ffmpeg.exe is missing. Downloading lightweight build (37MB) for compilation...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-win-64.zip' -OutFile 'ffmpeg.zip' -ErrorAction Stop; Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'temp_ffmpeg' -Force; Copy-Item 'temp_ffmpeg\ffmpeg.exe' -Destination 'tools\ffmpeg.exe'; Remove-Item 'ffmpeg.zip' -Force; Remove-Item 'temp_ffmpeg' -Recurse -Force"

if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Automatic FFmpeg download failed. The build will continue, but high-res merging and MP3 conversion will not work unless you manually place ffmpeg.exe in the 'tools/' folder.
) else (
    echo [OK] FFmpeg successfully prepared for compiler!
)
:ffmpeg_exists

:: 4. Verify PyInstaller installation (Flat block)
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% EQU 0 goto pyinstaller_ok
echo [INFO] Installing PyInstaller in virtual environment...
pip install pyinstaller
:pyinstaller_ok

:: Ensure icon.ico exists in workspace root before compiling
if exist icon.ico goto icon_ok
echo [WARNING] icon.ico not found in root. It is highly recommended to place an icon.ico in the root folder before compiling.
:icon_ok

:: 5. Execute compilation safely and bundle the icon asset as data
echo Compiling standalone executable with PyInstaller...
if exist icon.ico (
    pyinstaller --windowed --onefile --add-data "tools;tools" --add-data "icon.ico;." --collect-all yt_dlp --hidden-import=yt_dlp --exclude-module urllib3.contrib.emscripten --icon icon.ico --name "YouTubeBatchDownloader" app/main.py
) else (
    pyinstaller --windowed --onefile --add-data "tools;tools" --collect-all yt_dlp --hidden-import=yt_dlp --exclude-module urllib3.contrib.emscripten --name "YouTubeBatchDownloader" app/main.py
)

echo.
echo ========================================================
echo Build finished! Your standalone EXE is located in the 'dist' folder.
echo ========================================================
pause