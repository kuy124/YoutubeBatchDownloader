import hashlib
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
import uuid
import zipfile
from pathlib import PurePosixPath

from PySide6.QtCore import QObject, QRunnable, Signal


USER_AGENT = "YouTubeBatchDownloader-Updater"


def safe_zip_member(member_name: str) -> bool:
    normalized = member_name.replace('\\', '/')
    path = PurePosixPath(normalized)
    has_drive = bool(path.parts and ':' in path.parts[0])
    return not path.is_absolute() and not has_drive and ".." not in path.parts


def extract_release_executable(zip_path: str, destination: str) -> None:
    """Extracts the sole application EXE without trusting archive paths."""
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if any(not safe_zip_member(member.filename) for member in members):
            raise ValueError("The downloaded update contains an unsafe archive path.")
        executables = [
            member for member in members
            if not member.is_dir()
            and PurePosixPath(member.filename.replace('\\', '/')).parts
            and PurePosixPath(member.filename.replace('\\', '/')).name.lower() == "youtubebatchdownloader.exe"
            and len(PurePosixPath(member.filename.replace('\\', '/')).parts) == 2
            and PurePosixPath(member.filename.replace('\\', '/')).parts[0].lower() == "youtubebatchdownloader"
        ]
        if len(executables) != 1:
            raise ValueError(
                "The downloaded update must contain exactly one executable at "
                "YoutubeBatchDownloader/YouTubeBatchDownloader.exe."
            )
        with archive.open(executables[0]) as source, open(destination, "wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)


class UpdateDownloadSignals(QObject):
    progress = Signal(int, int)
    staged = Signal(str, str)
    cancelled = Signal()
    error = Signal(str)


class AppUpdateDownloadWorker(QRunnable):
    def __init__(self, release: dict, target_executable: str):
        super().__init__()
        self.release = release
        self.target_executable = os.path.abspath(target_executable)
        self.signals = UpdateDownloadSignals()
        self._cancelled = threading.Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        download_path = self.target_executable + ".update-download"
        staged_path = self.target_executable + ".update-new"
        partial_path = staged_path + ".part"
        for path in (download_path, partial_path):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

        try:
            request = urllib.request.Request(
                self.release["download_url"], headers={"User-Agent": USER_AGENT})
            received = 0
            hasher = hashlib.sha256()
            with urllib.request.urlopen(request, timeout=30) as response, open(download_path, "wb") as output:
                total = int(response.headers.get("Content-Length") or self.release.get("size") or 0)
                while chunk := response.read(1024 * 1024):
                    if self._cancelled.is_set():
                        raise InterruptedError
                    output.write(chunk)
                    hasher.update(chunk)
                    received += len(chunk)
                    self.signals.progress.emit(received, total)

            if hasher.hexdigest().lower() != self.release["sha256"].lower():
                raise ValueError("The downloaded update failed SHA-256 verification.")
            if self._cancelled.is_set():
                raise InterruptedError

            if self.release["asset_name"].lower().endswith(".zip"):
                extract_release_executable(download_path, partial_path)
            else:
                os.replace(download_path, partial_path)
            os.replace(partial_path, staged_path)
            self.signals.staged.emit(staged_path, self.release["version"])
        except InterruptedError:
            self.signals.cancelled.emit()
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            for path in (download_path, partial_path):
                try:
                    os.remove(path)
                except (FileNotFoundError, OSError):
                    pass


_REPLACEMENT_SCRIPT = r'''param(
    [int]$OldPid,
    [string]$NewPath,
    [string]$TargetPath,
    [string]$BackupPath,
    [string]$MarkerPath
)
$ErrorActionPreference = 'Stop'
$newProcess = $null
try {
    # PyInstaller one-file apps have a bootloader parent and a Python child.
    # Waiting only for the child leaves the EXE locked by the parent and can
    # trigger Windows' parent-executable security validation.
    $targetFullPath = [System.IO.Path]::GetFullPath($TargetPath)
    do {
        $oldProcess = Get-Process -Id $OldPid -ErrorAction SilentlyContinue
        $targetProcesses = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
            try { $_.Path -and ([System.IO.Path]::GetFullPath($_.Path) -ieq $targetFullPath) }
            catch { $false }
        })
        if ($oldProcess -or $targetProcesses.Count -gt 0) {
            Start-Sleep -Milliseconds 250
        }
    } while ($oldProcess -or $targetProcesses.Count -gt 0)
    Start-Sleep -Milliseconds 500
    if (-not (Test-Path -LiteralPath $NewPath -PathType Leaf)) {
        throw 'The verified update file is missing.'
    }
    # The running one-file app exports these markers for its own bootloader
    # child. Do not pass them to the replacement, or it will treat PowerShell
    # as its parent bootloader and fail PyInstaller's security validation.
    Get-ChildItem Env: | Where-Object { $_.Name -like '_PYI_*' } | ForEach-Object {
        Remove-Item -LiteralPath ("Env:" + $_.Name) -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $BackupPath) {
        Remove-Item -LiteralPath $BackupPath -Force
    }
    Move-Item -LiteralPath $TargetPath -Destination $BackupPath -Force
    Move-Item -LiteralPath $NewPath -Destination $TargetPath -Force
    $markerArg = '"' + $MarkerPath + '"'
    $backupArg = '"' + $BackupPath + '"'
    $newProcess = Start-Process -FilePath $TargetPath -ArgumentList @('--update-marker', $markerArg, '--update-backup', $backupArg) -PassThru
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $MarkerPath) {
            Remove-Item -LiteralPath $MarkerPath -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
            exit 0
        }
        if ($newProcess.HasExited) {
            throw 'The updated application exited before startup completed.'
        }
        Start-Sleep -Milliseconds 250
        $newProcess.Refresh()
    }
    throw 'The updated application did not confirm startup within 60 seconds.'
} catch {
    if ($newProcess -and -not $newProcess.HasExited) {
        Stop-Process -Id $newProcess.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
    }
    if (Test-Path -LiteralPath $BackupPath) {
        Remove-Item -LiteralPath $TargetPath -Force -ErrorAction SilentlyContinue
        Move-Item -LiteralPath $BackupPath -Destination $TargetPath -Force
        Start-Process -FilePath $TargetPath
    }
    Set-Content -LiteralPath ($MarkerPath + '.error') -Value $_.Exception.Message -Encoding UTF8 -ErrorAction SilentlyContinue
    exit 1
} finally {
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''


def launch_replacement(staged_path: str, version: str) -> None:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Automatic application installation is available only in the packaged EXE.")
    target_path = os.path.abspath(sys.executable)
    if not os.path.isfile(staged_path):
        raise RuntimeError("The verified update file is no longer available.")
    if os.path.normcase(os.path.dirname(os.path.abspath(staged_path))) != os.path.normcase(os.path.dirname(target_path)):
        raise RuntimeError("The verified update must be staged beside the current application.")
    safe_version = re.sub(r'[^0-9A-Za-z.-]+', '_', version or "previous")
    backup_path = f"{target_path}.backup-{safe_version}"
    marker_path = os.path.join(tempfile.gettempdir(), f"ybd-update-{uuid.uuid4().hex}.ready")
    script_path = os.path.join(tempfile.gettempdir(), f"ybd-update-{uuid.uuid4().hex}.ps1")
    with open(script_path, "w", encoding="utf-8-sig") as script:
        script.write(_REPLACEMENT_SCRIPT)

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    subprocess.Popen([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", script_path,
        "-OldPid", str(os.getpid()),
        "-NewPath", os.path.abspath(staged_path),
        "-TargetPath", target_path,
        "-BackupPath", backup_path,
        "-MarkerPath", marker_path,
    ], close_fds=True, creationflags=creation_flags)


def acknowledge_updated_startup(argv: list[str]) -> None:
    """Writes the marker used by the replacement helper after the GUI is visible."""
    try:
        index = argv.index("--update-marker")
        marker_path = argv[index + 1]
    except (ValueError, IndexError):
        return
    try:
        with open(marker_path, "w", encoding="utf-8") as marker:
            marker.write("ready")
    except OSError:
        pass
