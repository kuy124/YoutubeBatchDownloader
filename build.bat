@echo off
TITLE Building YouTube Batch Downloader...

call venv\Scripts\activate.bat

echo Cleaning previous builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo Compiling executable with PyInstaller...
:: Build as a standalone executable
pyinstaller ^
    --windowed ^
    --onefile ^
    --icon icon.ico ^
    --name "YouTubeBatchDownloader" ^
    app/main.py

echo.
echo Build finished! Check the 'dist' folder for your .exe file.
pause