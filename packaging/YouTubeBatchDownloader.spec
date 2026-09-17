# -*- mode: python ; coding: utf-8 -*-
"""Deterministic one-file release definition for YouTube Batch Downloader."""

from pathlib import Path

from PyInstaller.building.datastruct import TOC
from PyInstaller.utils.hooks import collect_data_files


PROJECT_ROOT = Path(SPECPATH).resolve().parent
APP_ENTRY = PROJECT_ROOT / "app" / "main.py"
ICON_FILE = PROJECT_ROOT / "icon.ico"


datas = [(str(PROJECT_ROOT / "tools"), "tools")]
if ICON_FILE.is_file():
    datas.append((str(ICON_FILE), "."))
datas += collect_data_files("yt_dlp")


a = Analysis(
    [str(APP_ENTRY)],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["yt_dlp", "mutagen"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "av", "tkinter", "unittest", "pydoc", "urllib3.contrib.emscripten",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtOpenGL",
        "PySide6.Qt3D", "PySide6.QtSvg", "PySide6.QtSql", "PySide6.QtTest",
        "PySide6.QtWebEngine", "PySide6.QtXml", "PySide6.QtMultimedia",
        "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtPrintSupport",
    ],
    noarchive=False,
    optimize=2,
)

# Qt 6 on supported Windows versions uses the OS ICU API.  PyInstaller can
# otherwise collect a same-named ICU DLL from unrelated software on PATH; that
# DLL may expose version-suffixed symbols and prevents Qt6Core from loading.
forbidden_icu_dlls = {"icuuc.dll", "icudt78.dll", "icuin78.dll"}
a.binaries = TOC(
    entry for entry in a.binaries
    if Path(entry[0]).name.lower() not in forbidden_icu_dlls
)


pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [("O", None, "OPTION"), ("O", None, "OPTION")],
    name="YouTubeBatchDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ICON_FILE)] if ICON_FILE.is_file() else None,
)
