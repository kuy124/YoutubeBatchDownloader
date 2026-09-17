import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from unittest import mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.app_update import (
    AppUpdateDownloadWorker,
    acknowledge_updated_startup,
    extract_release_executable,
    launch_replacement,
    safe_zip_member,
    _REPLACEMENT_SCRIPT,
)
from app.downloader import build_output_template
from app.gui import COL_OUTPUT_NAME, MainWindow
from app.themes import THEMES, build_theme
from app.updater import parse_version, select_windows_asset
from app.utils import output_extension_for_format, sanitize_output_stem
from app import ytdlp_updater
from app.ytdlp_updater import install_verified_wheel, version_tuple


@contextmanager
def workspace_temp_directory():
    path = Path(__file__).parent / "runtime_tmp" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class FilenameTests(unittest.TestCase):
    def test_sanitizes_windows_names_and_selected_extension(self):
        self.assertEqual(sanitize_output_stem("CON", "MP4 Video"), "CON_")
        self.assertEqual(sanitize_output_stem("CON.notes", "MP4 Video"), "CON.notes_")
        self.assertEqual(sanitize_output_stem("my:video?.mp4", "MP4 Video"), "my_video_")
        self.assertEqual(sanitize_output_stem("ending.  ", "MP4 Video"), "ending")

    def test_keeps_percent_visible_but_escapes_template(self):
        template = build_output_template("C:\\Downloads", "100% ready", "MP4 Video")
        self.assertTrue(template.endswith("100%% ready.%(ext)s"))

    def test_all_formats_have_expected_extensions(self):
        expected = {
            "Best Quality (MKV)": ".mkv", "MP4 Video": ".mp4",
            "WEBM Video": ".webm", "AVI Video": ".avi", "MOV Video": ".mov",
            "MP3 Audio": ".mp3", "M4A Audio": ".m4a", "WAV Audio": ".wav",
            "FLAC Audio": ".flac", "AAC Audio": ".aac", "OPUS Audio": ".opus",
        }
        for format_name, extension in expected.items():
            self.assertEqual(output_extension_for_format(format_name), extension)


class ArchiveTests(unittest.TestCase):
    def test_replacement_clears_inherited_pyinstaller_markers(self):
        self.assertIn("Where-Object { $_.Name -like '_PYI_*' }", _REPLACEMENT_SCRIPT)
        self.assertIn("Remove-Item -LiteralPath (\"Env:\" + $_.Name)", _REPLACEMENT_SCRIPT)

    def test_replacement_accepts_a_stable_visible_window_when_marker_is_unsupported(self):
        self.assertIn("function Get-ProcessesAtPath", _REPLACEMENT_SCRIPT)
        self.assertIn("MainWindowHandle -ne 0", _REPLACEMENT_SCRIPT)
        self.assertIn("$visibleSince.AddSeconds(3)", _REPLACEMENT_SCRIPT)

    def test_updated_startup_acknowledges_marker_with_a_path_containing_spaces(self):
        with workspace_temp_directory() as temp_dir:
            marker = Path(temp_dir) / "folder with spaces" / "update ready.marker"
            marker.parent.mkdir(parents=True)
            acknowledge_updated_startup(["YouTubeBatchDownloader.exe", "--update-marker", str(marker)])
            self.assertEqual(marker.read_text(encoding="utf-8"), "ready")

    def test_replacement_helper_receives_clean_environment_and_space_paths(self):
        with workspace_temp_directory() as temp_dir:
            target = Path(temp_dir) / "folder with spaces" / "YouTubeBatchDownloader.exe"
            staged = Path(temp_dir) / "folder with spaces" / "YouTubeBatchDownloader.exe.update-new"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"old")
            staged.write_bytes(b"new")
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "executable", str(target)), \
                    mock.patch.object(tempfile, "gettempdir", return_value=temp_dir), \
                    mock.patch.object(subprocess, "Popen") as popen, \
                    mock.patch.dict(os.environ, {"_PYI_TEST": "inherited", "PATH": os.environ.get("PATH", "")}, clear=True):
                launch_replacement(str(staged), "1.2.3")
            env = popen.call_args.kwargs["env"]
            self.assertNotIn("_PYI_TEST", env)

    def test_rejects_unsafe_archive_member(self):
        self.assertFalse(safe_zip_member("../YouTubeBatchDownloader.exe"))
        self.assertFalse(safe_zip_member("C:/YouTubeBatchDownloader.exe"))

    def test_extracts_exact_application_executable(self):
        with workspace_temp_directory() as temp_dir:
            archive_path = Path(temp_dir) / "release.zip"
            output_path = Path(temp_dir) / "new.exe"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("YoutubeBatchDownloader/YouTubeBatchDownloader.exe", b"binary")
            extract_release_executable(str(archive_path), str(output_path))
            self.assertEqual(output_path.read_bytes(), b"binary")

    def test_extracts_exact_application_executable_with_windows_separators(self):
        with workspace_temp_directory() as temp_dir:
            archive_path = Path(temp_dir) / "release.zip"
            output_path = Path(temp_dir) / "new.exe"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("YoutubeBatchDownloader\\YouTubeBatchDownloader.exe", b"binary")

            extract_release_executable(str(archive_path), str(output_path))

            self.assertEqual(output_path.read_bytes(), b"binary")

    def test_rejects_multiple_application_executables(self):
        with workspace_temp_directory() as temp_dir:
            archive_path = Path(temp_dir) / "release.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("YoutubeBatchDownloader/YouTubeBatchDownloader.exe", b"one")
                archive.writestr("YoutubeBatchDownloader/YouTubeBatchDownloader.exe", b"two")
            with self.assertRaises(ValueError):
                extract_release_executable(str(archive_path), str(Path(temp_dir) / "new.exe"))

    def test_requires_published_top_level_folder_layout(self):
        with workspace_temp_directory() as temp_dir:
            archive_path = Path(temp_dir) / "release.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("other/YouTubeBatchDownloader.exe", b"wrong folder")
            with self.assertRaises(ValueError):
                extract_release_executable(str(archive_path), str(Path(temp_dir) / "new.exe"))

    def test_installs_safe_ytdlp_wheel_atomically(self):
        with workspace_temp_directory() as temp_dir:
            wheel_path = Path(temp_dir) / "yt_dlp.whl"
            destination = Path(temp_dir) / "runtime"
            with zipfile.ZipFile(wheel_path, "w") as wheel:
                wheel.writestr("yt_dlp/__init__.py", "")
                wheel.writestr("yt_dlp/version.py", "__version__ = '1.0'")
            install_verified_wheel(wheel_path, destination)
            self.assertTrue((destination / "yt_dlp" / "__init__.py").exists())
            self.assertTrue((destination / ".verified").exists())

    def test_ytdlp_runtime_keeps_current_and_previous_versions(self):
        with workspace_temp_directory() as temp_dir:
            runtime_root = Path(temp_dir) / "yt-dlp"
            for version in ("2026.1.1", "2026.2.1", "2026.3.1"):
                version_path = runtime_root / version
                version_path.mkdir(parents=True)
                (version_path / ".verified").write_text("verified", encoding="utf-8")
            with mock.patch("app.ytdlp_updater._runtime_root", return_value=runtime_root):
                ytdlp_updater._prune_verified_versions()
            self.assertFalse((runtime_root / "2026.1.1").exists())
            self.assertTrue((runtime_root / "2026.2.1").exists())
            self.assertTrue((runtime_root / "2026.3.1").exists())


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class UpdateDownloadTests(unittest.TestCase):
    @staticmethod
    def release_for(payload: bytes) -> dict:
        return {
            "download_url": "https://example.invalid/release.zip",
            "asset_name": "YoutubeBatchDownloader.zip",
            "version": "2.0.0",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    def test_verified_download_is_staged(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("YoutubeBatchDownloader/YouTubeBatchDownloader.exe", b"new binary")
        payload = archive_bytes.getvalue()
        with workspace_temp_directory() as temp_dir:
            target = str(Path(temp_dir) / "Current Name.exe")
            staged = []
            worker = AppUpdateDownloadWorker(self.release_for(payload), target)
            worker.signals.staged.connect(lambda path, version: staged.append((path, version)))
            with mock.patch("app.app_update.urllib.request.urlopen", return_value=FakeResponse(payload)):
                worker.run()
            self.assertEqual(staged[0][1], "2.0.0")
            self.assertEqual(Path(staged[0][0]).read_bytes(), b"new binary")

    def test_checksum_failure_never_stages(self):
        payload = b"not a valid release"
        with workspace_temp_directory() as temp_dir:
            release = self.release_for(payload)
            release["sha256"] = "0" * 64
            errors = []
            worker = AppUpdateDownloadWorker(release, str(Path(temp_dir) / "Current.exe"))
            worker.signals.error.connect(errors.append)
            with mock.patch("app.app_update.urllib.request.urlopen", return_value=FakeResponse(payload)):
                worker.run()
            self.assertTrue(any("SHA-256" in error for error in errors))
            self.assertFalse((Path(temp_dir) / "Current.exe.update-new").exists())

    def test_cancelled_download_never_stages(self):
        payload = b"cancel me"
        with workspace_temp_directory() as temp_dir:
            cancelled = []
            worker = AppUpdateDownloadWorker(
                self.release_for(payload), str(Path(temp_dir) / "Current.exe"))
            worker.signals.cancelled.connect(lambda: cancelled.append(True))
            worker.cancel()
            with mock.patch("app.app_update.urllib.request.urlopen", return_value=FakeResponse(payload)):
                worker.run()
            self.assertEqual(cancelled, [True])


class ReleaseTests(unittest.TestCase):
    def test_version_ordering(self):
        self.assertGreater(parse_version("v1.10.0"), parse_version("1.9.9"))
        self.assertGreater(version_tuple("2026.10.1"), version_tuple("2026.8.19"))

    def test_zip_asset_is_preferred(self):
        assets = [
            {"name": "YouTubeBatchDownloader.exe", "browser_download_url": "exe"},
            {"name": "YoutubeBatchDownloader.2.0.zip", "browser_download_url": "zip"},
        ]
        self.assertEqual(select_windows_asset(assets)["browser_download_url"], "zip")


class QueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.active_workers.clear()
        for task in self.window.task_data.values():
            task["state"] = "complete"
        self.window.close()

    def test_add_task_stays_ready_until_start(self):
        launched = []
        self.window._launch_download_worker = lambda *args: launched.append(args)
        options = {
            "download_path": tempfile.gettempdir(),
            "format": "MP4 Video",
            "quality": "Best",
            "audio_boost": "100% (Original)",
            "use_aria2": False,
        }
        self.window.add_task("https://youtu.be/example", options, "Example")
        task_id = next(iter(self.window.task_data))
        self.assertEqual(self.window.task_data[task_id]["state"], "ready")
        self.assertEqual(launched, [])

        self.window.table.item(0, COL_OUTPUT_NAME).setText("Renamed")
        self.assertEqual(self.window.task_data[task_id]["output_name"], "Renamed")
        self.window.start_queue()
        self.assertEqual(self.window.task_data[task_id]["state"], "running")
        self.assertEqual(self.window.task_data[task_id]["options"]["output_name"], "Renamed")
        self.assertEqual(len(launched), 1)

    def test_custom_name_conflicts_are_detected(self):
        with workspace_temp_directory() as temp_dir:
            options = {
                "download_path": temp_dir,
                "format": "MP3 Audio",
                "quality": "192 kbps",
                "audio_boost": "100% (Original)",
                "use_aria2": False,
            }
            self.window.add_task("https://youtu.be/one", options, "One")
            self.window.add_task("https://youtu.be/two", options, "Two")
            ids = list(self.window.task_data)
            for task_id in ids:
                self.window.task_data[task_id]["output_name"] = "same"
            conflicts = self.window._custom_output_conflicts(ids)
            self.assertTrue(any("more than one" in message for message in conflicts))

    def test_running_item_reserves_its_custom_output_path(self):
        with workspace_temp_directory() as temp_dir:
            options = {
                "download_path": temp_dir,
                "format": "MP4 Video",
                "quality": "Best",
                "audio_boost": "100% (Original)",
                "use_aria2": False,
            }
            self.window.add_task("https://youtu.be/running", options, "Running")
            self.window.add_task("https://youtu.be/ready", options, "Ready")
            running_id, ready_id = list(self.window.task_data)
            self.window.task_data[running_id]["state"] = "running"
            self.window.task_data[running_id]["output_name"] = "same"
            self.window.task_data[ready_id]["output_name"] = "same"
            conflicts = self.window._custom_output_conflicts([ready_id])
            self.assertTrue(any("more than one" in message for message in conflicts))

    def test_every_shipped_theme_applies_to_queue_controls(self):
        self.window.add_task(
            "https://youtu.be/theme",
            {
                "download_path": tempfile.gettempdir(),
                "format": "MP4 Video",
                "quality": "Best",
                "audio_boost": "100% (Original)",
                "use_aria2": False,
            },
            "Theme Preview",
        )
        for theme_name in THEMES:
            stylesheet, palette = build_theme(theme_name)
            self.window.setStyleSheet(stylesheet)
            self.app.setPalette(palette)
            self.app.processEvents()
            visible_actions = {
                button.text() for button in self.window.findChildren(QPushButton)
                if button.isVisibleTo(self.window)
            }
            self.assertIn("Add to Queue", visible_actions)
            self.assertIn("Start Queue", visible_actions)


if __name__ == "__main__":
    unittest.main()
