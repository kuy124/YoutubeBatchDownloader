@echo off
TITLE Building YouTube Batch Downloader release
setlocal EnableExtensions

set "APP_VERSION=v1.9.2"
set "DIST_ROOT=dist"
set "STAGING=build\release\YoutubeBatchDownloader"
set "PORTABLE=%DIST_ROOT%\portable"
set "INSTALLER=%DIST_ROOT%\installer"
set "METADATA=%DIST_ROOT%\metadata"

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

:: The app-reported version and the release filename must agree. This prevents
:: a build from offering a release that is older than the executable itself.
set "SOURCE_APP_VERSION="
for /f "delims=" %%V in ('python -c "from app.updater import APP_VERSION; print(APP_VERSION)"') do set "SOURCE_APP_VERSION=%%V"
if not defined SOURCE_APP_VERSION (
    echo [ERROR] Could not read APP_VERSION from app\updater.py.
    exit /b 1
)
if /I not "%SOURCE_APP_VERSION%"=="%APP_VERSION%" (
    echo [ERROR] Release version mismatch: build.bat is %APP_VERSION%, app\updater.py is %SOURCE_APP_VERSION%.
    echo         Set both values to the same release version before building.
    exit /b 1
)

echo Cleaning previous builds...
if exist build rmdir /s /q build 2>nul
if exist dist rmdir /s /q dist 2>nul
if not exist tools mkdir tools 2>nul
mkdir "%STAGING%" "%PORTABLE%" "%INSTALLER%" "%METADATA%"

:: 3. Fast FFmpeg check
if exist tools\ffmpeg.exe goto ffmpeg_exists
echo [INFO] tools/ffmpeg.exe is missing. Downloading pinned FFmpeg Essentials 9.0.1...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/GyanD/codexffmpeg/releases/download/9.0.1/ffmpeg-9.0.1-essentials_build.zip' -OutFile 'ffmpeg.zip' -ErrorAction Stop; Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'temp_ffmpeg' -Force; $candidate = Get-ChildItem -Path 'temp_ffmpeg' -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1; if (-not $candidate) { throw 'FFmpeg executable missing from archive' }; Copy-Item $candidate.FullName -Destination 'tools\ffmpeg.exe'; Remove-Item 'ffmpeg.zip' -Force; Remove-Item 'temp_ffmpeg' -Recurse -Force"
:ffmpeg_exists
powershell -Command "$sha=[Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead('tools\ffmpeg.exe'); try {$hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLower()} finally {$stream.Dispose(); $sha.Dispose()}; if ($hash -ne '72a489eccd008c2ec2c0a5856c5c75bc3d8bbfa90166c4566865c246445e6aa3') { Write-Error ('Unexpected FFmpeg SHA-256: ' + $hash); exit 1 }"
if errorlevel 1 (
    echo [ERROR] FFmpeg payload failed the pinned SHA-256 check.
    exit /b 1
)

:: 3b. Fast aria2 check (bundled for optional multi-connection downloads)
if exist tools\aria2c.exe goto aria2_exists
echo [INFO] tools/aria2c.exe is missing. Downloading optional accelerator (~4MB)...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip' -OutFile 'aria2.zip' -ErrorAction Stop; Expand-Archive -Path 'aria2.zip' -DestinationPath 'temp_aria2' -Force; Copy-Item 'temp_aria2\aria2-1.37.0-win-64bit-build1\aria2c.exe' -Destination 'tools\aria2c.exe'; Remove-Item 'aria2.zip' -Force; Remove-Item 'temp_aria2' -Recurse -Force"
:aria2_exists

:: 4. Fast check for PyInstaller executable (Instant 0ms check)
if exist venv\Scripts\pyinstaller.exe goto pyinstaller_ok
echo [INFO] Installing PyInstaller in virtual environment...
pip install pyinstaller --no-cache-dir
:pyinstaller_ok

:: 5. Execute compilation with PyInstaller
echo Compiling lightweight standalone executable...

:: Qt 6 uses Windows' unversioned ICU API. Do not let PyInstaller resolve
:: icuuc.dll from an unrelated developer tool on the inherited PATH; those
:: copies commonly export version-suffixed ICU symbols and break Qt at launch.
set "PYI_ORIGINAL_PATH=%PATH%"
set "PATH=%CD%\venv\Scripts;%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\WindowsPowerShell\v1.0"

set PYI_FLAGS=--noconfirm --clean ^
    --workpath "build\pyinstaller" ^
    --distpath "%STAGING%"

pyinstaller %PYI_FLAGS% packaging\YouTubeBatchDownloader.spec
set "PYI_RESULT=%ERRORLEVEL%"
set "PATH=%PYI_ORIGINAL_PATH%"
if not "%PYI_RESULT%"=="0" exit /b %PYI_RESULT%

if not exist "%STAGING%\YouTubeBatchDownloader.exe" (
    echo [ERROR] Build did not produce the staged executable.
    exit /b 1
)

echo Verifying Qt uses Windows ICU and no foreign ICU DLL was bundled...
venv\Scripts\python.exe -c "import os, pefile; from pathlib import Path; from PyInstaller.archive.readers import CArchiveReader; system_icu=Path(os.environ['SystemRoot']) / 'System32' / 'icuuc.dll'; exports={item.name.decode(errors='replace') for item in pefile.PE(str(system_icu)).DIRECTORY_ENTRY_EXPORT.symbols if item.name}; assert 'ucnv_open' in exports, 'Windows ICU does not export ucnv_open'; archive=CArchiveReader(Path(r'%STAGING%\YouTubeBatchDownloader.exe')); foreign=[name for name in archive.toc if Path(name).name.lower().startswith('icu') and Path(name).suffix.lower()=='.dll']; assert not foreign, 'Foreign ICU DLLs were bundled: ' + ', '.join(foreign)"
if errorlevel 1 (
    echo [ERROR] Qt ICU validation failed. Refusing to publish this build.
    exit /b 1
)

echo Creating updater-compatible portable ZIP...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$source = 'build\release\YoutubeBatchDownloader'; $zip = 'dist\portable\YoutubeBatchDownloader-' + $env:APP_VERSION + '.zip'; Compress-Archive -Path $source -DestinationPath $zip -CompressionLevel Optimal -Force"
if errorlevel 1 exit /b 1

echo Writing release metadata...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$sha=[Security.Cryptography.SHA256]::Create(); $ffmpegStream=[IO.File]::OpenRead('tools\ffmpeg.exe'); try {$ffmpeg=([BitConverter]::ToString($sha.ComputeHash($ffmpegStream))).Replace('-','').ToLower()} finally {$ffmpegStream.Dispose()}; $exeStream=[IO.File]::OpenRead('build\release\YoutubeBatchDownloader\YouTubeBatchDownloader.exe'); try {$exe=([BitConverter]::ToString($sha.ComputeHash($exeStream))).Replace('-','').ToLower()} finally {$exeStream.Dispose(); $sha.Dispose()}; Set-Content -LiteralPath 'dist\metadata\ffmpeg.sha256.txt' -Value $ffmpeg -Encoding ASCII; Set-Content -LiteralPath 'dist\metadata\YouTubeBatchDownloader.exe.sha256.txt' -Value $exe -Encoding ASCII; $manifest = [ordered]@{ version = $env:APP_VERSION; executable = 'YouTubeBatchDownloader.exe'; executable_sha256 = $exe; ffmpeg_sha256 = $ffmpeg; portable_zip = ('YoutubeBatchDownloader-' + $env:APP_VERSION + '.zip'); portable_layout = 'YoutubeBatchDownloader/YouTubeBatchDownloader.exe'; installer = ('YouTubeBatchDownloader-' + $env:APP_VERSION + '-Setup.exe') }; $utf8 = New-Object System.Text.UTF8Encoding($false); [IO.File]::WriteAllText('dist\metadata\release-manifest.json', ($manifest | ConvertTo-Json), $utf8)"
if errorlevel 1 exit /b 1

set "ISCC_PATH=%ISCC_PATH%"
if not defined ISCC_PATH if exist "tools\installer\ISCC.exe" set "ISCC_PATH=tools\installer\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH (
    echo [ERROR] Inno Setup 6 compiler not found.
    echo         Install ISCC.exe or set ISCC_PATH before running build.bat.
    exit /b 1
)
powershell -NoProfile -Command "$sha=[Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead('%ISCC_PATH%'); try {$hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLower()} finally {$stream.Dispose(); $sha.Dispose()}; if ($hash -ne '0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7') { Write-Error ('Unexpected Inno Setup compiler SHA-256: ' + $hash); exit 1 }"
if errorlevel 1 (
    echo [ERROR] The Inno Setup compiler does not match packaging/toolchain.json.
    exit /b 1
)

echo Building per-user installer...
"%ISCC_PATH%" packaging\installer.iss
if errorlevel 1 exit /b 1
if not exist "%INSTALLER%\YouTubeBatchDownloader-%APP_VERSION%-Setup.exe" (
    echo [ERROR] Installer output was not created.
    exit /b 1
)

echo Verifying portable ZIP layout...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$zip = 'dist\portable\YoutubeBatchDownloader-' + $env:APP_VERSION + '.zip'; Add-Type -AssemblyName System.IO.Compression.FileSystem; $archive = [IO.Compression.ZipFile]::OpenRead((Resolve-Path $zip)); try { $names = @($archive.Entries | ForEach-Object { $_.FullName.Replace('\', '/').TrimEnd('/') }); if ($names.Count -ne 1 -or $names[0] -ne 'YoutubeBatchDownloader/YouTubeBatchDownloader.exe') { throw ('Unexpected ZIP contents: ' + ($names -join ', ')) } } finally { $archive.Dispose() }"
if errorlevel 1 exit /b 1
if exist "build\release" rmdir /s /q "build\release"

echo.
echo ========================================================
echo Release ready: installer, updater ZIP, and metadata are under 'dist'.
echo ========================================================
exit /b 0
