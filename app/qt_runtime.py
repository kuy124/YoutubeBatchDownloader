"""Keep Qt's native DLL dependencies on one matching PySide6 installation."""

from __future__ import annotations

import os
import sys
import ctypes
from pathlib import Path


_DLL_DIRECTORY_HANDLES = []
_NATIVE_DLL_HANDLES = []
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def filter_untrusted_path_entries(path_value: str) -> list[str]:
    """Returns inherited PATH entries that Windows can traverse safely.

    Some desktop hosts add junctions to PATH.  Recent Windows security checks
    reject those untrusted mount points when a child tool is launched, causing
    yt-dlp or FFmpeg to fail before a download begins.  The app always invokes
    its bundled tools by absolute path, so omitting these ambient entries is
    both safe and more deterministic.
    """
    accepted = []
    seen = set()
    for raw_entry in (path_value or "").split(os.pathsep):
        entry = os.path.expandvars(raw_entry.strip().strip('"'))
        if not entry:
            continue
        key = os.path.normcase(os.path.normpath(entry))
        if key in seen:
            continue
        seen.add(key)
        try:
            attributes = getattr(os.lstat(entry), "st_file_attributes", 0)
        except OSError:
            # A malformed or inaccessible PATH entry cannot be a dependency
            # of the bundled application and should not reach child tools.
            continue
        if attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            continue
        accepted.append(entry)
    return accepted


def _load_matching_qt_dlls(valid: list[str]) -> None:
    """Load Qt's native libraries from the selected PySide6 tree.

    Windows resolves DLLs by filename.  If another Qt installation appears in
    the process search path, importing ``QtWidgets.pyd`` can otherwise bind to
    a different ``Qt6Core.dll``/``Qt6Gui.dll`` and fail with the rather opaque
    "specified procedure could not be found" error.  Loading the exact files
    first pins the module names to the matching PySide6 build.
    """
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        return

    # Keep dependencies in load order.  The files live directly in PySide6 or
    # shiboken6 in both source environments and PyInstaller's collected bundle.
    names = (
        "shiboken6.abi3.dll",
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Widgets.dll",
        "pyside6.abi3.dll",
    )
    for name in names:
        path = next((Path(directory) / name for directory in valid
                     if (Path(directory) / name).is_file()), None)
        if path is None:
            continue
        try:
            # LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR (0x100) makes this DLL's
            # sibling dependencies resolvable; the default search flags
            # include directories registered with add_dll_directory.
            handle = ctypes.WinDLL(str(path), winmode=0x1100)
        except (OSError, TypeError):
            continue
        _NATIVE_DLL_HANDLES.append(handle)


def prepare_qt_dll_search() -> None:
    """Prefer the bundled/active PySide6 DLL directory before importing Qt."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.extend((bundle_root / "PySide6", bundle_root / "shiboken6", bundle_root))
    else:
        site_packages = Path(sys.prefix) / "Lib" / "site-packages"
        candidates.extend((site_packages / "PySide6", site_packages / "shiboken6"))

    seen: set[str] = set()
    valid = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        normalized = os.path.normcase(str(candidate.resolve()))
        if normalized in seen:
            continue
        seen.add(normalized)
        valid.append(str(candidate))
        if hasattr(os, "add_dll_directory"):
            try:
                _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(candidate)))
            except OSError:
                pass

    if valid:
        if os.name == "nt":
            try:
                # Exclude the ambient working directory/PATH from dependency
                # resolution while retaining system and registered user dirs.
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.SetDefaultDllDirectories(0x1000 | 0x400)
            except (AttributeError, OSError):
                pass
        _load_matching_qt_dlls(valid)
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(
            valid + filter_untrusted_path_entries(current_path))

        # Qt plugin discovery must use the same installation as the native
        # libraries.  This avoids an external Qt platform plugin being loaded
        # after the import succeeds.
        plugin_dir = Path(valid[0]) / "plugins"
        if plugin_dir.is_dir():
            os.environ["QT_PLUGIN_PATH"] = str(plugin_dir)
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_dir / "platforms")
