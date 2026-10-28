import hashlib
import io
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
import zipfile
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

    def test_gui_checkbox_changes_are_written_before_close(self):
        application = QApplication.instance() or QApplication([])
        with project_temp_directory() as temp_dir:
            data_dir = Path(temp_dir) / "user data"
            with mock.patch("app.settings.get_data_dir", return_value=str(data_dir)), \
                    mock.patch("app.settings.get_install_dir", return_value=str(data_dir)), \
                    mock.patch("app.settings.migrate_legacy_data"):
                from app.gui import MainWindow

                window = MainWindow()
                try:
                    window.chk_auto_clear.setChecked(True)
                    window.chk_monitor_clip.setChecked(True)
                    window.chk_completion_sound.setChecked(False)
                    window.chk_batch_notify.setChecked(False)
                    window.chk_confirm_exit.setChecked(False)
                    window.chk_restore_links.setChecked(True)
                    window.chk_aria2.setChecked(True)
                    application.processEvents()

                    saved = json.loads(Path(window.settings.settings_file).read_text(encoding="utf-8"))
                    self.assertTrue(saved["auto_clear"])
                    self.assertTrue(saved["monitor_clipboard"])
                    self.assertFalse(saved["completion_sound"])
                    self.assertFalse(saved["batch_notifications"])
                    self.assertFalse(saved["confirm_exit_downloading"])
                    self.assertTrue(saved["restore_links"])
                    self.assertTrue(saved["use_aria2"])
                finally:
                    window.close()
                    window.deleteLater()
                    application.processEvents()

                reopened = Settings()
                for key in ("auto_clear", "monitor_clipboard", "restore_links", "use_aria2"):
                    self.assertTrue(reopened.get(key))
                for key in ("completion_sound", "batch_notifications", "confirm_exit_downloading"):
                    self.assertFalse(reopened.get(key))

    def test_gui_startup_does_not_overwrite_saved_checkboxes(self):
        from PySide6.QtTest import QTest

        application = QApplication.instance() or QApplication([])
        with project_temp_directory() as temp_dir:
            data_dir = Path(temp_dir) / "user data"
            with mock.patch("app.settings.get_data_dir", return_value=str(data_dir)), \
                    mock.patch("app.settings.get_install_dir", return_value=str(data_dir)), \
                    mock.patch("app.settings.migrate_legacy_data"):
                Settings().update({
                    "format": "MP3 Audio",
                    "audio_boost": "150% (+3.5 dB)",
                    "auto_clear": True,
                    "monitor_clipboard": True,
                    "completion_sound": False,
                    "batch_notifications": False,
                    "confirm_exit_downloading": False,
                    "restore_links": True,
                    "use_aria2": True,
                })

                from app.gui import MainWindow

                window = MainWindow()
                try:
                    QTest.qWait(400)
                    application.processEvents()
                    restored = Settings()
                    for key in ("auto_clear", "monitor_clipboard", "restore_links", "use_aria2"):
                        self.assertTrue(restored.get(key))
                    for key in ("completion_sound", "batch_notifications", "confirm_exit_downloading"):
                        self.assertFalse(restored.get(key))
                finally:
                    window.close()
                    window.deleteLater()
                    application.processEvents()

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

    def test_restart_launches_an_independent_source_or_packaged_app(self):
        from app.app_update import restart_application

        for frozen in (False, True):
            with self.subTest(frozen=frozen), mock.patch.object(sys, "frozen", frozen, create=True), \
                    mock.patch("app.app_update.subprocess.Popen") as launch, \
                    mock.patch.dict(os.environ, {"PYINSTALLER_RESET_ENVIRONMENT": "0"}):
                restart_application()
                command = launch.call_args.args[0]
                self.assertEqual(command[0], sys.executable)
                if frozen:
                    self.assertEqual(command, [sys.executable])
                else:
                    self.assertEqual(Path(command[1]), Path(__file__).resolve().parents[1] / "app" / "main.py")
                self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
                self.assertEqual(os.environ["PYINSTALLER_RESET_ENVIRONMENT"], "0")

    def test_ytdlp_restart_only_closes_after_a_successful_relaunch(self):
        from app.gui import MainWindow, QMessageBox

        for error in (None, OSError("relaunch failed")):
            window = SimpleNamespace(
                _pending_ytdlp_restart=True, _has_unfinished_tasks=lambda: False,
                close=mock.Mock(),
            )
            with self.subTest(error=error), \
                    mock.patch("app.gui.QMessageBox.question", return_value=QMessageBox.Yes), \
                    mock.patch("app.gui.restart_application", side_effect=error) as restart, \
                    mock.patch("app.gui.QApplication.quit") as quit_app, \
                    mock.patch("app.gui.QMessageBox.warning") as warning:
                MainWindow._ask_ytdlp_restart(window)
                restart.assert_called_once_with()
                if error:
                    window.close.assert_not_called()
                    quit_app.assert_not_called()
                    warning.assert_called_once()
                    self.assertTrue(window._pending_ytdlp_restart)
                else:
                    window.close.assert_called_once_with()
                    quit_app.assert_called_once_with()
                    warning.assert_not_called()
                    self.assertFalse(window._pending_ytdlp_restart)

    def test_ytdlp_restart_waits_for_downloads_and_respects_no(self):
        from app.gui import MainWindow, QMessageBox

        for unfinished in (True, False):
            window = SimpleNamespace(
                _pending_ytdlp_restart=True, _has_unfinished_tasks=lambda: unfinished,
                statusBar=mock.Mock(), close=mock.Mock(),
            )
            with self.subTest(unfinished=unfinished), \
                    mock.patch("app.gui.QMessageBox.question", return_value=QMessageBox.No) as question, \
                    mock.patch("app.gui.restart_application") as restart, \
                    mock.patch("app.gui.QApplication.quit") as quit_app:
                MainWindow._ask_ytdlp_restart(window)
                self.assertEqual(question.call_count, 0 if unfinished else 1)
                restart.assert_not_called()
                quit_app.assert_not_called()
                window.close.assert_not_called()
                self.assertTrue(window._pending_ytdlp_restart)


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

    def test_downloaded_update_is_active_after_a_cold_start(self):
        wheel = io.BytesIO()
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("yt_dlp/__init__.py", "from . import version\n")
            archive.writestr("yt_dlp/version.py", "__version__ = '2026.09.01'\n")
        wheel_bytes = wheel.getvalue()
        metadata = {
            "info": {"version": "2026.9.1"},
            "releases": {"2026.9.1": [{
                "packagetype": "bdist_wheel", "filename": "yt_dlp-2026.9.1-py3-none-any.whl",
                "digests": {"sha256": hashlib.sha256(wheel_bytes).hexdigest()},
                "url": "https://files.pythonhosted.org/yt_dlp.whl",
            }]},
        }
        with project_temp_directory() as temp_dir:
            with mock.patch.object(ytdlp_updater, "get_data_dir", return_value=temp_dir), \
                    mock.patch.object(ytdlp_updater.urllib.request, "urlopen", side_effect=[
                        io.BytesIO(json.dumps(metadata).encode("utf-8")), io.BytesIO(wheel_bytes),
                    ]):
                staged = ytdlp_updater.check_and_install_update()
            self.assertEqual(staged["state"], "restart_required")
            code = f'''
from unittest import mock
from app import ytdlp_updater as updater
updater.get_data_dir = lambda: {temp_dir!r}
updater.migrate_legacy_data = lambda: None
with mock.patch.object(updater.urllib.request, "urlopen", side_effect=AssertionError("unexpected network")):
    active = updater.bootstrap_ytdlp()
    assert active["active_version"] == "2026.09.01", active
    assert active["last_result"] == "yt-dlp 2026.09.01 is active", active
    cached = updater.check_and_install_update()
    assert cached["state"] == "not_due", cached
    assert cached["last_result"] == active["last_result"], cached
'''
            result = subprocess.run(
                [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

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
