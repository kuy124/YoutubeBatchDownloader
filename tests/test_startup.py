import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
import uuid
import shutil
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.startup import StartupClock
from app import ytdlp_updater
from app import utils
from app.settings import Settings
from app.qt_runtime import filter_untrusted_path_entries
from app.splash import LoadingSplash
from app.themes import THEMES


def project_temp_directory():
    path = Path(__file__).parent / "runtime_tmp" / ("startup-" + uuid.uuid4().hex)
    path.mkdir(parents=True, exist_ok=True)
    class _Temp:
        def __enter__(self):
            return str(path)
        def __exit__(self, *_):
            shutil.rmtree(path, ignore_errors=True)
    return _Temp()


class StartupInstrumentationTests(unittest.TestCase):
    def test_settings_create_file_and_persist_checkbox_values(self):
        with project_temp_directory() as temp_dir:
            data_dir = Path(temp_dir) / "user data"
            with mock.patch("app.settings.get_data_dir", return_value=str(data_dir)), \
                    mock.patch("app.settings.get_install_dir", return_value=str(data_dir)), \
                    mock.patch("app.settings.migrate_legacy_data"):
                first = Settings()
                self.assertTrue(Path(first.settings_file).is_file())
                first.update({
                    "auto_clear": True,
                    "monitor_clipboard": True,
                    "completion_sound": False,
                    "batch_notifications": False,
                    "confirm_exit_downloading": False,
                    "restore_links": True,
                    "use_aria2": True,
                })
                second = Settings()
            for key in (
                "auto_clear", "monitor_clipboard", "restore_links", "use_aria2",
            ):
                self.assertTrue(second.get(key))
            for key in ("completion_sound", "batch_notifications", "confirm_exit_downloading"):
                self.assertFalse(second.get(key))

    def test_splash_uses_saved_theme_with_a_functional_spinner(self):
        application = QApplication.instance() or QApplication([])
        splash = LoadingSplash("Nord")
        try:
            self.assertEqual(splash.windowTitle(), "YouTube Batch Downloader")
            self.assertIn("#2e3440", splash.styleSheet())
            self.assertEqual(splash._spinner._timer.interval(), 90)
            splash.start()
            self.assertTrue(splash._spinner._timer.isActive())
            splash.set_message("Preparing the download engine...")
            self.assertEqual(splash._message_label.text(), "Preparing the download engine...")
        finally:
            splash.finish()
            application.processEvents()

    def test_splash_accepts_every_shipped_theme(self):
        application = QApplication.instance() or QApplication([])
        for theme_name in THEMES:
            splash = LoadingSplash(theme_name)
            try:
                self.assertIn("startupDialog", splash.styleSheet())
            finally:
                splash.close()
        application.processEvents()

    def test_reparse_point_path_entries_are_not_inherited_by_child_tools(self):
        safe = r"C:\\Safe Tools"
        unsafe = r"C:\\Untrusted Junction"

        def fake_lstat(path):
            attributes = 0x0400 if path == unsafe else 0
            return SimpleNamespace(st_file_attributes=attributes)

        with mock.patch("app.qt_runtime.os.lstat", side_effect=fake_lstat):
            filtered = filter_untrusted_path_entries(os.pathsep.join((safe, unsafe, safe)))

        self.assertEqual(filtered, [safe])

    def test_frozen_build_separates_install_and_user_data(self):
        with project_temp_directory() as temp_dir:
            install_dir = Path(temp_dir) / "Installed App"
            local_app_data = Path(temp_dir) / "Local App Data"
            install_dir.mkdir()
            with mock.patch.object(utils.sys, "frozen", True, create=True), \
                    mock.patch.object(utils.sys, "executable", str(install_dir / "YouTubeBatchDownloader.exe")), \
                    mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}, clear=False):
                self.assertEqual(Path(utils.get_install_dir()), install_dir)
                self.assertEqual(Path(utils.get_data_dir()), local_app_data / "YouTubeBatchDownloader")

    def test_legacy_migration_does_not_overwrite_existing_data(self):
        with project_temp_directory() as temp_dir:
            install_dir = Path(temp_dir) / "Installed App"
            local_app_data = Path(temp_dir) / "Local App Data"
            install_dir.mkdir()
            (install_dir / "settings.json").write_text('{"theme":"Dark"}', encoding="utf-8")
            (install_dir / "runtime" / "yt-dlp").mkdir(parents=True)
            (install_dir / "runtime" / "yt-dlp" / "old.txt").write_text("old", encoding="utf-8")
            data_dir = local_app_data / "YouTubeBatchDownloader"
            (data_dir / "runtime" / "yt-dlp").mkdir(parents=True)
            (data_dir / "runtime" / "yt-dlp" / "old.txt").write_text("new", encoding="utf-8")
            with mock.patch.object(utils.sys, "frozen", True, create=True), \
                    mock.patch.object(utils.sys, "executable", str(install_dir / "YouTubeBatchDownloader.exe")), \
                    mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}, clear=False):
                self.assertTrue(utils.migrate_legacy_data())
            self.assertEqual((data_dir / "runtime" / "yt-dlp" / "old.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual((data_dir / "settings.json").read_text(encoding="utf-8"), '{"theme":"Dark"}')

    def test_marker_stages_are_monotonic_and_atomic(self):
        with project_temp_directory() as temp_dir:
            marker = Path(temp_dir) / "nested" / "startup.json"
            clock = StartupClock(str(marker))
            time.sleep(0.001)
            clock.mark("qt_ready")
            time.sleep(0.001)
            clock.mark("first_paint")
            clock.write({"active_ytdlp": "test"})
            payload = json.loads(marker.read_text(encoding="utf-8"))
            values = list(payload["stages_ms"].values())
            self.assertEqual(values, sorted(values))
            self.assertEqual(payload["active_ytdlp"], "test")

    def test_marker_path_with_spaces(self):
        with project_temp_directory() as temp_dir:
            marker = Path(temp_dir) / "folder with spaces" / "startup marker.json"
            clock = StartupClock(str(marker))
            clock.mark("first_paint")
            clock.write()
            self.assertTrue(marker.exists())

    def test_gui_import_does_not_load_heavy_download_modules(self):
        code = (
            "import sys; import app.gui; "
            "print(int('yt_dlp' in sys.modules), int('mutagen' in sys.modules), "
            "int('app.converter' in sys.modules))"
        )
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        self.assertEqual(result.stdout.strip(), "0 0 0")


class BackgroundYtDlpUpdateTests(unittest.TestCase):
    def setUp(self):
        self.status_patch = mock.patch.object(
            ytdlp_updater, "_STATUS",
            {"active_version": "2026.1.1", "runtime_version": "2026.1.1",
             "last_check": 0, "last_result": "Not checked yet"},
        )
        self.status_patch.start()
        self.addCleanup(self.status_patch.stop)

    def test_prepare_runtime_never_checks_network(self):
        with mock.patch.object(ytdlp_updater, "migrate_legacy_data") as migrate, \
                mock.patch.object(ytdlp_updater.urllib.request, "urlopen", side_effect=AssertionError):
            selection = ytdlp_updater.prepare_ytdlp_runtime()
        migrate.assert_called_once_with()
        self.assertIn("path", selection)

    def test_due_check_failure_preserves_active_runtime(self):
        with mock.patch.object(ytdlp_updater, "_read_state", return_value={
            "active_version": "2026.1.1", "runtime_version": "2026.1.1", "last_check": 0,
        }), mock.patch.object(ytdlp_updater, "_write_state") as write_state, mock.patch.object(
            ytdlp_updater, "_download_current_stable", side_effect=OSError("offline")
        ):
            result = ytdlp_updater.check_and_install_update()
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["active_version"], "2026.1.1")
        write_state.assert_called_once()

    def test_verified_new_runtime_requires_restart(self):
        with project_temp_directory() as temp_dir:
            runtime = Path(temp_dir) / "2026.9.1"
            runtime.mkdir()
            (runtime / ".verified").write_text("verified", encoding="utf-8")
            with mock.patch.object(ytdlp_updater, "_read_state", return_value={
                "active_version": "2026.1.1", "runtime_version": "2026.1.1", "last_check": 0,
            }), mock.patch.object(ytdlp_updater, "_write_state") as write_state, mock.patch.object(
                ytdlp_updater, "_download_current_stable", return_value=("2026.9.1", runtime)
            ):
                result = ytdlp_updater.check_and_install_update()
        self.assertEqual(result["state"], "restart_required")
        self.assertIn("restart required", result["last_result"])
        self.assertEqual(write_state.call_args.args[0]["active_version"], "2026.1.1")

    def test_recent_check_does_not_hit_network(self):
        with mock.patch.object(ytdlp_updater, "_read_state", return_value={
            "active_version": "2026.1.1", "last_check": int(time.time()),
        }), mock.patch.object(ytdlp_updater, "_download_current_stable", side_effect=AssertionError):
            result = ytdlp_updater.check_and_install_update()
        self.assertEqual(result["state"], "not_due")

    def test_corrupt_verified_runtime_falls_back_to_bundled_engine(self):
        bad_path = Path("runtime-corrupt")
        calls = []

        def fake_activate(path):
            calls.append(path)
            if path is bad_path:
                raise ImportError("corrupt runtime")
            return "2026.1.1"

        with mock.patch.object(ytdlp_updater, "_activate", side_effect=fake_activate), \
                mock.patch.object(ytdlp_updater, "_discard_failed_runtime") as discard, \
                mock.patch.object(ytdlp_updater, "_write_state"):
            result = ytdlp_updater.warm_ytdlp_runtime({"path": bad_path, "version": "2026.1.1"})
        self.assertEqual(calls, [bad_path, None])
        discard.assert_called_once_with(bad_path)
        self.assertEqual(result["active_version"], "2026.1.1")
        self.assertIn("bundled", result["last_result"])


if __name__ == "__main__":
    unittest.main()
