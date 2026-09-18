[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host $Message
}

function Remove-PathIfPresent([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Get-Sha256([string]$Path) {
    $sha256 = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $stream.Dispose()
        $sha256.Dispose()
    }
}

function Invoke-Checked([string]$FilePath, [string[]]$Arguments) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath"
    }
}

function Get-SourceVersion([string]$PythonPath) {
    $output = & $PythonPath "-c" "from app.updater import APP_VERSION; print(APP_VERSION)"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read APP_VERSION from app/updater.py."
    }
    $version = (($output | Select-Object -Last 1).ToString()).Trim()
    if ($version -notmatch "^[vV]?\d+\.\d+\.\d+(?:[.-][0-9A-Za-z]+)*$") {
        throw "APP_VERSION is not a supported release version: $version"
    }
    return $version
}

function Write-Utf8NoBom([string]$Path, [string]$Contents) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $Contents, $encoding)
}

try {
    $venvRoot = Join-Path $projectRoot "venv"
    $python = Join-Path $venvRoot "Scripts\python.exe"
    $pyinstaller = Join-Path $venvRoot "Scripts\pyinstaller.exe"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "Virtual environment 'venv' was not found. Run install.bat first."
    }

    $sourceVersion = Get-SourceVersion $python
    $versionNumber = $sourceVersion -replace "^[vV]", ""
    $releaseTag = "v$versionNumber"
    $env:APP_VERSION = $releaseTag

    $buildRoot = Join-Path $projectRoot "build"
    $distRoot = Join-Path $projectRoot "dist"
    $staging = Join-Path $buildRoot "release\YoutubeBatchDownloader"
    $portableRoot = Join-Path $distRoot "portable"
    $installerRoot = Join-Path $distRoot "installer"
    $metadataRoot = Join-Path $distRoot "metadata"
    $stagedExe = Join-Path $staging "YouTubeBatchDownloader.exe"
    $portableZip = Join-Path $portableRoot "YoutubeBatchDownloader-$releaseTag.zip"
    $installerPath = Join-Path $installerRoot "YouTubeBatchDownloader-$releaseTag-Setup.exe"

    Write-Step "Cleaning previous builds..."
    Remove-PathIfPresent $buildRoot
    Remove-PathIfPresent $distRoot
    New-Item -ItemType Directory -Force -Path $staging, $portableRoot, $installerRoot, $metadataRoot | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "tools") | Out-Null

    $ffmpegPath = Join-Path $projectRoot "tools\ffmpeg.exe"
    $ffmpegHashExpected = "72a489eccd008c2ec2c0a5856c5c75bc3d8bbfa90166c4566865c246445e6aa3"
    if (-not (Test-Path -LiteralPath $ffmpegPath -PathType Leaf)) {
        Write-Host "[INFO] tools/ffmpeg.exe is missing. Downloading pinned FFmpeg Essentials 9.0.1..."
        $archivePath = Join-Path $projectRoot "ffmpeg.zip"
        $extractPath = Join-Path $projectRoot "temp_ffmpeg"
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri "https://github.com/GyanD/codexffmpeg/releases/download/9.0.1/ffmpeg-9.0.1-essentials_build.zip" -OutFile $archivePath
            Remove-PathIfPresent $extractPath
            Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force
            $candidate = Get-ChildItem -LiteralPath $extractPath -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
            if (-not $candidate) {
                throw "FFmpeg executable was missing from the downloaded archive."
            }
            Copy-Item -LiteralPath $candidate.FullName -Destination $ffmpegPath -Force
        }
        finally {
            Remove-PathIfPresent $archivePath
            Remove-PathIfPresent $extractPath
        }
    }
    $ffmpegHash = Get-Sha256 $ffmpegPath
    if ($ffmpegHash -ne $ffmpegHashExpected) {
        throw "FFmpeg failed the pinned SHA-256 check: $ffmpegHash"
    }

    $aria2Path = Join-Path $projectRoot "tools\aria2c.exe"
    if (-not (Test-Path -LiteralPath $aria2Path -PathType Leaf)) {
        Write-Host "[INFO] tools/aria2c.exe is missing. Downloading optional accelerator..."
        $archivePath = Join-Path $projectRoot "aria2.zip"
        $extractPath = Join-Path $projectRoot "temp_aria2"
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip" -OutFile $archivePath
            Remove-PathIfPresent $extractPath
            Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force
            $candidate = Get-ChildItem -LiteralPath $extractPath -Recurse -Filter "aria2c.exe" | Select-Object -First 1
            if (-not $candidate) {
                throw "aria2c.exe was missing from the downloaded archive."
            }
            Copy-Item -LiteralPath $candidate.FullName -Destination $aria2Path -Force
        }
        catch {
            Write-Warning "aria2 could not be downloaded. The app will use its standard downloader. $($_.Exception.Message)"
        }
        finally {
            Remove-PathIfPresent $archivePath
            Remove-PathIfPresent $extractPath
        }
    }

    if (-not (Test-Path -LiteralPath $pyinstaller -PathType Leaf)) {
        Write-Host "[INFO] PyInstaller is missing. Installing it in the virtual environment..."
        Invoke-Checked $python @("-m", "pip", "install", "pyinstaller", "--no-cache-dir")
    }

    Write-Step "Compiling lightweight standalone executable..."
    $originalPath = $env:PATH
    try {
        $env:PATH = "$($venvRoot)\Scripts;$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
        $pyinstallerArgs = @(
            "--noconfirm",
            "--clean",
            "--workpath", (Join-Path $buildRoot "pyinstaller"),
            "--distpath", $staging,
            (Join-Path $projectRoot "packaging\YouTubeBatchDownloader.spec")
        )
        Invoke-Checked $pyinstaller $pyinstallerArgs
    }
    finally {
        $env:PATH = $originalPath
    }

    if (-not (Test-Path -LiteralPath $stagedExe -PathType Leaf)) {
        throw "PyInstaller did not produce the staged executable."
    }

    Write-Step "Verifying Qt ICU dependencies..."
    $env:BUILD_EXE_PATH = $stagedExe
    try {
        $icuCheck = @'
import os
from pathlib import Path
import pefile
from PyInstaller.archive.readers import CArchiveReader

system_icu = Path(os.environ['SystemRoot']) / 'System32' / 'icuuc.dll'
exports = {
    item.name.decode(errors='replace')
    for item in pefile.PE(str(system_icu)).DIRECTORY_ENTRY_EXPORT.symbols
    if item.name
}
assert 'ucnv_open' in exports, 'Windows ICU does not export ucnv_open'
archive = CArchiveReader(Path(os.environ['BUILD_EXE_PATH']))
foreign = [
    name for name in archive.toc
    if Path(name).name.lower().startswith('icu') and Path(name).suffix.lower() == '.dll'
]
assert not foreign, 'Foreign ICU DLLs were bundled: ' + ', '.join(foreign)
'@
        Invoke-Checked $python @("-c", $icuCheck)
    }
    finally {
        Remove-Item -LiteralPath "Env:BUILD_EXE_PATH" -ErrorAction SilentlyContinue
    }

    Write-Step "Creating updater-compatible portable ZIP..."
    Compress-Archive -LiteralPath $staging -DestinationPath $portableZip -CompressionLevel Optimal -Force

    Write-Step "Writing release metadata..."
    $exeHash = Get-Sha256 $stagedExe
    Set-Content -LiteralPath (Join-Path $metadataRoot "ffmpeg.sha256.txt") -Value $ffmpegHash -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $metadataRoot "YouTubeBatchDownloader.exe.sha256.txt") -Value $exeHash -Encoding ASCII
    $manifest = [ordered]@{
        version = $releaseTag
        executable = "YouTubeBatchDownloader.exe"
        executable_sha256 = $exeHash
        ffmpeg_sha256 = $ffmpegHash
        portable_zip = "YoutubeBatchDownloader-$releaseTag.zip"
        portable_layout = "YoutubeBatchDownloader/YouTubeBatchDownloader.exe"
        installer = "YouTubeBatchDownloader-$releaseTag-Setup.exe"
    }
    Write-Utf8NoBom (Join-Path $metadataRoot "release-manifest.json") ($manifest | ConvertTo-Json)

    $isccPath = $env:ISCC_PATH
    $isccCandidates = @((Join-Path $projectRoot "tools\installer\ISCC.exe"))
    if ($env:ProgramFiles) { $isccCandidates += Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe" }
    if (${env:ProgramFiles(x86)}) { $isccCandidates += Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe" }
    if ($env:LOCALAPPDATA) { $isccCandidates += Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe" }
    if (-not $isccPath) {
        $isccPath = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    }
    if (-not $isccPath -or -not (Test-Path -LiteralPath $isccPath -PathType Leaf)) {
        throw "Inno Setup 6 compiler not found. Install ISCC.exe or set ISCC_PATH."
    }
    $isccPath = (Resolve-Path -LiteralPath $isccPath).Path
    $isccHashExpected = "0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7"
    $isccHash = Get-Sha256 $isccPath
    if ($isccHash -ne $isccHashExpected) {
        throw "The Inno Setup compiler does not match packaging/toolchain.json: $isccHash"
    }

    Write-Step "Building per-user installer for $releaseTag..."
    $installerScript = Join-Path $projectRoot "packaging\installer.iss"
    Invoke-Checked $isccPath @("/DAppVersion=$versionNumber", $installerScript)
    if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
        throw "Installer output was not created: $installerPath"
    }

    Write-Step "Verifying portable ZIP layout..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($portableZip)
    try {
        $names = @($archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/").TrimEnd("/") })
        if ($names.Count -ne 1 -or $names[0] -ne "YoutubeBatchDownloader/YouTubeBatchDownloader.exe") {
            throw "Unexpected ZIP contents: $($names -join ', ')"
        }
    }
    finally {
        $archive.Dispose()
    }

    Remove-PathIfPresent (Join-Path $buildRoot "release")
    Write-Host ""
    Write-Host "Release ready: installer, updater ZIP, and metadata are under 'dist'."
    exit 0
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
