"""The few places where Windows and Linux actually differ.

Every platform-specific path in the app goes through this module so the rest of
the code base stays free of ``os.name`` checks.  Stdlib only, on purpose: the
native messaging bridge is built from this package too.
"""

from __future__ import annotations

import os
import subprocess
import sys

IS_WINDOWS = os.name == "nt"
APP_DIR_NAME = "YouTubeBatchDownloader"


def tool_name(name: str) -> str:
    """Bundled tool filename: ffmpeg stays ffmpeg, ffmpeg.exe on Windows."""
    return f"{name}.exe" if IS_WINDOWS else name


def executable_name(name: str) -> str:
    """Packaged application filename: YouTubeBatchDownloader(.exe)."""
    return tool_name(name)


def user_data_root() -> str:
    """Base directory that holds the app's per-user data directory."""
    if IS_WINDOWS:
        return os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
    return os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")


def user_data_dir() -> str:
    """Writable per-user directory for settings, logs and runtime files."""
    return os.path.join(user_data_root(), APP_DIR_NAME)


def open_path(path: str) -> None:
    """Opens a file or folder with the desktop's default handler."""
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(
            ["xdg-open", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
