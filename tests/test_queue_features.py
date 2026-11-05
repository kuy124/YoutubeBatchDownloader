"""Queue-level tests for the playlist, retry, power-action, limiter, cookie,
subtitle, skip-existing and per-row-format features.

Run with:
    venv/Scripts/python.exe -m unittest discover -s tests -t . -v
"""

import gc
import os
import tempfile
import time
import unittest
from contextlib import ExitStack
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import yt_dlp
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QGridLayout

from tests.gui_env import isolated_settings

from app import downloader as downloader_module
from app.downloader import DownloadWorker, PlaylistExpandWorker, container_for_format
from app.gui import COL_STATUS, MainWindow
from app.utils import output_extension_for_format, sanitize_output_stem

BASE_OPTIONS = {
    "format": "MP4 Video",
    "quality": "Best",
    "audio_boost": "100% (Original)",
    "use_aria2": False,
}


class WindowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._stack = ExitStack()
        self.addCleanup(self._stack.close)
        self._stack.enter_context(isolated_settings())
        self.window = MainWindow()
        self.window._launch_download_worker = lambda *args: None
        self._temp_dir = tempfile.TemporaryDirectory()
        self.window.entry_path.setText(self._temp_dir.name)

    def tearDown(self):
        self.window.active_workers.clear()
        for task in self.window.task_data.values():
            task["state"] = "complete"
        self.window.close()
        self._temp_dir.cleanup()

    def add_ready_task(self, url="https://youtu.be/abc", title="Example", raw_title="Example"):
        options = dict(BASE_OPTIONS, download_path=self._temp_dir.name)
        before = set(self.window.task_data)
        self.window.add_task(url, options, title, raw_title=raw_title)
        added = set(self.window.task_data) - before
        self.assertEqual(len(added), 1, "add_task must create exactly one row")
        return added.pop()


class DownloadOptionsTests(WindowTestCase):
    def test_every_new_setting_reaches_the_worker(self):
        self.window.combo_speed_limit.setCurrentText("2 MB/s")
        self.window.combo_cookies_mode.setCurrentText("From browser")
        self.window.combo_cookies_browser.setCurrentText("firefox")
        self.window.entry_cookies_file.setText("  ")
        self.window.combo_subtitles.setCurrentText("Embed in video")
        self.window.entry_subtitle_langs.setText(" en, de ")
        self.window.chk_skip_existing.setChecked(False)

        options = self.window._download_options()
        self.assertEqual(options["speed_limit"], "2 MB/s")
        self.assertEqual(options["cookies_mode"], "From browser")
        self.assertEqual(options["cookies_browser"], "firefox")
        self.assertEqual(options["cookies_file"], "")
        self.assertEqual(options["subtitles"], "Embed in video")
        self.assertEqual(options["subtitle_langs"], "en, de")
        self.assertFalse(options["skip_existing"])

    def test_blank_subtitle_languages_fall_back_to_english(self):
        self.window.entry_subtitle_langs.setText("   ")
        self.assertEqual(self.window._download_options()["subtitle_langs"], "en")


class PlaylistLimitTests(WindowTestCase):
    def test_parses_the_displayed_cap(self):
        self.window.combo_playlist_limit.setCurrentText("50 videos")
        self.assertEqual(self.window._playlist_item_limit(), 50)

    def test_no_limit_means_unbounded(self):
        self.window.combo_playlist_limit.setCurrentText("No limit")
        self.assertEqual(self.window._playlist_item_limit(), 0)

    def test_playlist_links_expand_instead_of_queueing(self):
        self.window.chk_expand_playlists.setChecked(True)
        self.window.url_input.setPlainText("https://www.youtube.com/playlist?list=PL123")
        expanded = []
        self.window._start_playlist_expansion = lambda urls, options: expanded.append(urls)

        self.window.add_links_to_queue()

        self.assertEqual(expanded, [["https://www.youtube.com/playlist?list=PL123"]])
        self.assertEqual(self.window.task_data, {})

    def test_expansion_can_be_turned_off(self):
        self.window.chk_expand_playlists.setChecked(False)
        self.window.url_input.setPlainText("https://www.youtube.com/playlist?list=PL123")
        self.window._start_playlist_expansion = lambda *args: self.fail("should not expand")

        self.window.add_links_to_queue()

        self.assertEqual(len(self.window.task_data), 1)

    def test_expanded_entries_become_rows_with_raw_titles(self):
        entries = [
            ("https://youtu.be/one", "Channel - One", "One"),
            ("https://youtu.be/two", "Channel - Two", "Two"),
            ("https://youtu.be/one", "Channel - One", "One"),
        ]
        self.window._on_playlist_entries(
            "https://www.youtube.com/playlist?list=PL1", entries,
            dict(BASE_OPTIONS, download_path=self._temp_dir.name))

        self.assertEqual(len(self.window.task_data), 2)
        raw = {info["pre_data"]["raw_title"] for info in self.window.task_data.values()}
        self.assertEqual(raw, {"One", "Two"})

    def test_failed_expansion_clears_the_pending_flag(self):
        self.window._pending_playlists.add("https://www.youtube.com/playlist?list=PL1")
        self.window._on_playlist_failed("https://www.youtube.com/playlist?list=PL1", "private")
        self.assertEqual(self.window._pending_playlists, set())


class RetryFailedTests(WindowTestCase):
    def test_button_tracks_failed_rows(self):
        task_id = self.add_ready_task()
        self.window.refresh_aggregates()
        self.assertFalse(self.window.btn_retry_failed.isEnabled())

        self.window.task_data[task_id]["state"] = "failed"
        self.window.refresh_aggregates()
        self.assertTrue(self.window.btn_retry_failed.isEnabled())

    def test_retry_all_failed_requeues_only_failures(self):
        failed_id = self.add_ready_task("https://youtu.be/bad", "Bad")
        done_id = self.add_ready_task("https://youtu.be/good", "Good")
        self.window.task_data[failed_id]["state"] = "failed"
        self.window.task_data[done_id]["state"] = "complete"

        retried = []
        self.window.retry_task = lambda task_id: retried.append(task_id)
        self.window._batch_action_done = True
        self.window.retry_all_failed()

        self.assertEqual(retried, [failed_id])
        self.assertFalse(self.window._batch_action_done)


class PostBatchActionTests(WindowTestCase):
    def setUp(self):
        super().setUp()
        self.requests = []
        self.window._request_suspend = lambda hibernate: self.requests.append(("suspend", hibernate))
        self.window._request_shutdown = lambda: self.requests.append(("shutdown",))
        self.window.open_downloads_folder = lambda: self.requests.append(("folder",))

    def settle(self):
        task_id = self.add_ready_task()
        self.window.task_data[task_id]["state"] = "complete"
        self.window._batch_action_done = False
        self.window._finish_batch_if_idle()
        return task_id

    def test_do_nothing_is_the_default(self):
        self.window.combo_post_batch.setCurrentText("Do nothing")
        self.settle()
        self.assertEqual(self.requests, [])

    def test_sleep_hibernate_and_shutdown(self):
        for label, expected in (
            ("Sleep", [("suspend", False)]),
            ("Hibernate", [("suspend", True)]),
            ("Shut down", [("shutdown",)]),
            ("Open download folder", [("folder",)]),
        ):
            with self.subTest(action=label):
                self.requests.clear()
                self.window.combo_post_batch.setCurrentText(label)
                self.settle()
                self.assertEqual(self.requests, expected)

    def test_the_action_fires_once_per_batch(self):
        self.window.combo_post_batch.setCurrentText("Sleep")
        self.settle()
        self.window._finish_batch_if_idle()
        self.window._finish_batch_if_idle()
        self.assertEqual(self.requests, [("suspend", False)])

    def test_a_running_download_blocks_the_action(self):
        task_id = self.settle()
        self.requests.clear()
        self.window._batch_action_done = False
        self.window.active_workers[task_id] = object()
        self.window._finish_batch_if_idle()
        self.assertEqual(self.requests, [])

    def test_a_queued_row_blocks_the_action(self):
        self.window.combo_post_batch.setCurrentText("Sleep")
        done_id = self.add_ready_task("https://youtu.be/done", "Done")
        queued_id = self.add_ready_task("https://youtu.be/waiting", "Waiting")
        self.window.task_data[done_id]["state"] = "complete"
        self.window._batch_action_done = False
        self.window._finish_batch_if_idle()

        self.assertEqual(self.requests, [])
        self.assertEqual(self.window.task_data[queued_id]["state"], "ready")

    def test_pending_playlist_expansion_blocks_the_action(self):
        self.window.combo_post_batch.setCurrentText("Sleep")
        self.settle()
        self.requests.clear()
        self.window._batch_action_done = False
        self.window._pending_playlists.add("https://www.youtube.com/playlist?list=PL1")
        self.window._finish_batch_if_idle()
        self.assertEqual(self.requests, [])

    def test_starting_a_new_queue_rearms_the_action(self):
        self.window.combo_post_batch.setCurrentText("Sleep")
        self.settle()
        self.assertEqual(self.requests, [("suspend", False)])
        self.window.url_input.setPlainText("https://youtu.be/new")
        self.window.add_links_to_queue()
        self.window.start_queue()
        self.assertFalse(self.window._batch_action_done)


class CookieWidgetTests(WindowTestCase):
    def test_only_the_relevant_row_is_shown(self):
        for mode, browser_visible, file_visible in (
            ("Disabled", False, False),
            ("From browser", True, False),
            ("cookies.txt file", False, True),
        ):
            with self.subTest(mode=mode):
                self.window.combo_cookies_mode.setCurrentText(mode)
                self.window._sync_cookies_widgets()
                self.assertEqual(
                    self.window.network_form.isRowVisible(self.window.combo_cookies_browser),
                    browser_visible)
                self.assertEqual(
                    self.window.network_form.isRowVisible(self.window.cookies_file_row),
                    file_visible)

    def test_mode_changes_are_persisted_immediately(self):
        self.window.combo_cookies_mode.setCurrentText("From browser")
        self.window._on_cookies_mode_changed("From browser")
        self.assertEqual(self.window.settings.get("cookies_mode"), "From browser")

    def test_extension_mode_is_not_offered(self):
        from app.gui import COOKIE_MODES
        self.assertEqual(COOKIE_MODES[0], "Disabled")
        self.assertNotIn("From extension", COOKIE_MODES)

    def test_other_cookie_modes_are_never_blocked_by_the_extension(self):
        self.window.combo_cookies_mode.setCurrentText("Disabled")
        self.assertIsNone(self.window._cookie_source_problem())
        self.window.combo_cookies_mode.setCurrentText("From browser")
        self.assertIsNone(self.window._cookie_source_problem())



class RowFormatTests(WindowTestCase):
    def setUp(self):
        super().setUp()
        self.window.combo_format.setCurrentText("MP4 Video")
        self.window.on_format_changed("MP4 Video")

    def test_override_is_recorded_and_shown_on_the_row(self):
        task_id = self.add_ready_task()
        quality = self.window.audio_qualities[0]
        self.window._apply_row_format(task_id, "MP3 Audio", quality, True)

        info = self.window.task_data[task_id]
        self.assertTrue(info["format_override"])
        self.assertEqual(info["options"]["format"], "MP3 Audio")
        status = self.window.table.item(self.window.row_mapping[task_id], COL_STATUS).text()
        self.assertEqual(status, f"Ready (MP3 - {quality})")

    def test_matching_the_global_setting_is_not_an_override(self):
        task_id = self.add_ready_task()
        self.window._apply_row_format(
            task_id, self.window.combo_format.currentText(),
            self.window.combo_quality.currentText(), True)

        info = self.window.task_data[task_id]
        self.assertFalse(info["format_override"])
        self.assertEqual(
            self.window.table.item(self.window.row_mapping[task_id], COL_STATUS).text(), "Ready")

    def test_reverting_to_global_clears_the_label(self):
        task_id = self.add_ready_task()
        self.window._apply_row_format(task_id, "MP3 Audio", self.window.audio_qualities[0], True)
        self.window._apply_row_format(
            task_id, self.window.combo_format.currentText(),
            self.window.combo_quality.currentText(), False)

        self.assertFalse(self.window.task_data[task_id]["format_override"])
        self.assertEqual(
            self.window.table.item(self.window.row_mapping[task_id], COL_STATUS).text(), "Ready")

    def test_only_ready_rows_can_be_changed(self):
        task_id = self.add_ready_task()
        self.window.task_data[task_id]["state"] = "complete"
        self.window._apply_row_format(task_id, "MP3 Audio", "320 kbps", True)
        self.assertFalse(self.window.task_data[task_id].get("format_override"))


class SkipExistingWorkerTests(unittest.TestCase):
    def make_worker(self, temp_dir, raw_title, fmt="MP4 Video", skip=True):
        path = os.path.join(temp_dir, sanitize_output_stem(raw_title, fmt)
                            + output_extension_for_format(fmt))
        with open(path, "wb") as handle:
            handle.write(b"already here")
        options = dict(BASE_OPTIONS, download_path=temp_dir, format=fmt, skip_existing=skip)
        return DownloadWorker("task-1", "https://youtu.be/abc", options,
                              {"title": raw_title, "raw_title": raw_title}), path

    def test_existing_file_finishes_the_task_without_downloading(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker, path = self.make_worker(temp_dir, "Some Video")
            results = []
            worker.signals.finished.connect(lambda *args: results.append(args))
            created = []

            def fake_ydl(_opts):
                created.append(_opts)
                raise AssertionError("yt-dlp must not run for a skipped task")

            with mock.patch.object(yt_dlp, "YoutubeDL", fake_ydl):
                worker.run()

            self.assertEqual(created, [])
            self.assertEqual(len(results), 1)
            task_id, final_path, message, _elapsed = results[0]
            self.assertEqual(task_id, "task-1")
            self.assertEqual(final_path, path)
            self.assertIn("skipped", message.lower())

    def test_disabled_check_still_reaches_yt_dlp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker, _path = self.make_worker(temp_dir, "Some Video", skip=False)
            results = []
            worker.signals.finished.connect(lambda *args: results.append(args))
            created = []

            def fake_ydl(opts):
                created.append(opts)
                raise RuntimeError("stop before any network call")

            with mock.patch.object(yt_dlp, "YoutubeDL", fake_ydl):
                worker.run()

            self.assertGreaterEqual(len(created), 1)
            self.assertEqual(results, [])

    def test_container_lookup_for_subtitles(self):
        self.assertEqual(container_for_format("MP4 Video"), "mp4")
        self.assertEqual(container_for_format("Best Quality (MKV)"), "mkv")
        self.assertEqual(container_for_format("MP3 Audio"), "")
        self.assertEqual(downloader_module.container_for_format("Nonsense"), "mkv")


class PlaylistExpandWorkerTests(unittest.TestCase):
    """Expansion must survive an unavailable anchor video on a watch+list link."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def expand(self, url, info=None, watch_error=False, error=None):
        seen = {}

        class FakeYoutubeDL:
            def __init__(self, opts):
                seen["opts"] = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, target, download=False):
                seen["url"] = target
                if error is not None:
                    raise error
                if watch_error and "watch?v=" in target:
                    raise yt_dlp.utils.DownloadError("Video unavailable")
                return info

        worker = PlaylistExpandWorker([url])
        entries, failures = [], []
        worker.signals.entries.connect(lambda src, items: entries.append((src, items)))
        worker.signals.failed.connect(lambda src, msg: failures.append((src, msg)))
        with mock.patch.object(yt_dlp, "YoutubeDL", FakeYoutubeDL):
            worker.run()
        return seen, entries, failures

    def test_the_watch_page_is_never_fetched(self):
        seen, entries, failures = self.expand(
            "https://www.youtube.com/watch?v=hWJ5FnqQM1Q&list=PL1",
            info={"entries": [{"url": "https://youtu.be/one", "title": "One"}]},
            watch_error=True)

        self.assertEqual(seen["url"], "https://www.youtube.com/playlist?list=PL1")
        self.assertEqual(failures, [])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1][0][0], "https://youtu.be/one")

    def test_channel_links_keep_their_own_url(self):
        seen, _entries, _failures = self.expand(
            "https://www.youtube.com/@SomeChannel/videos", info={"entries": []})
        self.assertEqual(seen["url"], "https://www.youtube.com/@SomeChannel/videos")

    def test_the_item_cap_is_passed_to_yt_dlp(self):
        seen, _entries, _failures = self.expand(
            "https://www.youtube.com/playlist?list=PL1", info={"entries": []})
        self.assertNotIn("playlistend", seen["opts"])

        worker = PlaylistExpandWorker(["https://www.youtube.com/playlist?list=PL1"], {}, 50)
        self.assertEqual(worker.item_limit, 50)

    def test_broken_entries_are_skipped_not_fatal(self):
        _seen, entries, failures = self.expand(
            "https://www.youtube.com/playlist?list=PL1",
            info={"entries": [
                None,
                {},
                {"title": "No id at all"},
                {"id": "good1", "title": "Good"},
                {"url": "https://youtu.be/good2", "title": "Also Good", "uploader": "Chan"},
            ]})

        self.assertEqual(failures, [])
        queued = entries[0][1]
        self.assertEqual([item[0] for item in queued],
                         ["https://www.youtube.com/watch?v=good1", "https://youtu.be/good2"])
        self.assertEqual(queued[1][1], "Chan - Also Good")

    def test_app_bound_encryption_surfaces_guidance_not_jargon(self):
        _seen, entries, failures = self.expand(
            "https://www.youtube.com/playlist?list=PL1",
            error=yt_dlp.utils.DownloadError(
                "ERROR: Failed to decrypt with DPAPI. See  "
                "https://github.com/yt-dlp/yt-dlp/issues/10927  for more info"))

        self.assertEqual(entries, [])
        self.assertEqual(len(failures), 1)
        self.assertIn("App-Bound Encryption", failures[0][1])
        self.assertIn("Firefox", failures[0][1])
        self.assertNotIn("DPAPI", failures[0][1])

    def test_a_locked_cookie_database_is_explained(self):
        _seen, _entries, failures = self.expand(
            "https://www.youtube.com/playlist?list=PL1",
            error=yt_dlp.utils.DownloadError(
                "Could not copy Chrome cookie database. See "
                "https://github.com/yt-dlp/yt-dlp/issues/7271 for more info"))

        self.assertIn("Close it completely", failures[0][1])

    def test_other_expansion_errors_still_reach_the_status_bar(self):
        _seen, _entries, failures = self.expand(
            "https://www.youtube.com/playlist?list=PL1",
            error=yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot"))

        self.assertIn("not a bot", failures[0][1])

    def test_a_dead_playlist_reports_one_failure(self):
        _seen, entries, failures = self.expand(
            "https://www.youtube.com/watch?v=abc&list=PLgone", info=None)
        self.assertEqual(entries, [])
        self.assertEqual(len(failures), 1)
        self.assertIn("No videos were found", failures[0][1])


class BackgroundWorkerDeliveryTests(WindowTestCase):
    """Workers started from the GUI must outlive the method that started them.

    PySide6 drops a QRunnable's Python-side signal connections once the last
    reference goes away, so a worker kept only in a local variable expands the
    playlist on a background thread and emits into nothing: the queue stays
    empty with no error anywhere. The synchronous tests above cannot see this
    because they call run() on the testing thread.
    """

    def pump_until(self, condition, seconds=15.0):
        deadline = time.time() + seconds
        while time.time() < deadline and not condition():
            QCoreApplication.processEvents()
            time.sleep(0.01)
        return condition()

    def test_playlist_rows_arrive_even_after_the_worker_is_collected(self):
        entries = [
            ("https://youtu.be/one", "Artist - One", "One"),
            ("https://youtu.be/two", "Artist - Two", "Two"),
        ]
        self._stack.enter_context(mock.patch.object(
            PlaylistExpandWorker, "_expand_one", lambda self, url: list(entries)))
        options = dict(BASE_OPTIONS, download_path=self._temp_dir.name)

        self.window._start_playlist_expansion(["https://www.youtube.com/playlist?list=PL1"], options)
        gc.collect()

        self.assertTrue(self.pump_until(lambda: not self.window._pending_playlists),
                        "the expansion never reported back to the GUI thread")
        self.assertEqual(len(self.window.task_data), 2)
        self.assertEqual(self.window.table.rowCount(), 2)

    def test_a_failed_expansion_reaches_the_status_bar_after_collection(self):
        def boom(self, url):
            raise RuntimeError("network went away")

        self._stack.enter_context(mock.patch.object(PlaylistExpandWorker, "_expand_one", boom))
        options = dict(BASE_OPTIONS, download_path=self._temp_dir.name)

        self.window._start_playlist_expansion(["https://www.youtube.com/playlist?list=PL1"], options)
        gc.collect()

        self.assertTrue(self.pump_until(lambda: not self.window._pending_playlists),
                        "the failure never reported back to the GUI thread")
        self.assertIn("Could not expand a playlist", self.window.statusBar.currentMessage())

    def test_title_previews_arrive_even_after_the_worker_is_collected(self):
        self._stack.enter_context(mock.patch.object(
            downloader_module.TitlePreviewWorker, "_fetch_single_title",
            lambda self, line: ("Preview Title", "Raw Title")))
        self.window.url_input.setPlainText("https://youtu.be/abc")

        self.window.fetch_title_previews()
        gc.collect()

        self.assertTrue(self.pump_until(lambda: self.window.preview_input.toPlainText().strip()),
                        "the title preview never reported back to the GUI thread")
        self.assertIn("Preview Title", self.window.preview_input.toPlainText())


class CookieFileIsolationTests(unittest.TestCase):
    """yt-dlp dumps its jar back into 'cookiefile' (YoutubeDL.close -> save_cookies).

    Handing every parallel task the same managed file let one task's rotated
    __Secure-1PSIDTS poison every later task, which YouTube then rejects.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.shared = os.path.join(self.folder.name, "cookies.txt")
        with open(self.shared, "w", encoding="utf-8") as handle:
            handle.write("# Netscape HTTP Cookie File\n")
        with open(self.shared, "rb") as handle:
            self.before = handle.read()
        self.handed_over = []

    def fake_engine(self, info=None, error=None):
        handed_over = self.handed_over

        class FakeYoutubeDL:
            def __init__(self, opts):
                self.path = opts.get("cookiefile")
                handed_over.append(self.path)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                if self.path:
                    with open(self.path, "w", encoding="utf-8") as handle:
                        handle.write("# rotated session token\n")
                return False

            def extract_info(self, target, download=False):
                if error is not None:
                    raise error
                return info

        return FakeYoutubeDL

    def assert_the_shared_file_stayed_read_only(self):
        self.assertTrue(self.handed_over, "yt-dlp was never started")
        self.assertNotIn(self.shared, self.handed_over)
        with open(self.shared, "rb") as handle:
            self.assertEqual(handle.read(), self.before)
        for path in self.handed_over:
            self.assertFalse(os.path.exists(path), "a private copy was left behind")

    def test_playlist_expansion_never_hands_over_the_shared_file(self):
        worker = PlaylistExpandWorker(
            ["https://www.youtube.com/playlist?list=PL1"], {"cookiefile": self.shared})
        with mock.patch.object(yt_dlp, "YoutubeDL", self.fake_engine(info={"entries": []})):
            worker.run()
        self.assert_the_shared_file_stayed_read_only()

    def test_every_download_attempt_gets_a_fresh_copy(self):
        options = {
            "download_path": self.folder.name,
            "format": "MP3 Audio",
            "quality": "320 kbps (Extreme)",
            "audio_boost": "100% (Original)",
            "use_aria2": False,
            "cookies_mode": "cookies.txt file",
            "cookies_file": self.shared,
            "skip_existing": False,
        }
        worker = DownloadWorker("task-1", "https://youtu.be/abc", options)
        errors = []
        worker.signals.error.connect(lambda _task_id, message: errors.append(message))
        with mock.patch.object(yt_dlp, "YoutubeDL", self.fake_engine(
                    error=yt_dlp.utils.DownloadError("boom"))), \
                mock.patch.object(downloader_module.time, "sleep"):
            worker.run()

        self.assertEqual(len(errors), 1)
        self.assertEqual(len(self.handed_over), 4, "expected one attempt per retry")
        self.assertEqual(len(set(self.handed_over)), 4, "an attempt replayed a poisoned copy")
        self.assert_the_shared_file_stayed_read_only()


class JsRuntimeWiringTests(unittest.TestCase):
    """yt-dlp solves YouTube's signature challenge in an external JS runtime.

    It enables only Deno by default, so on a machine with Node the challenge goes
    unsolved, YouTube answers with storyboard images only, and the MP3 selector
    reports "Requested format is not available" for videos that play fine in a
    browser.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def options(self, folder):
        return {
            "download_path": folder,
            "format": "MP3 Audio",
            "quality": "320 kbps (Extreme)",
            "audio_boost": "100% (Original)",
            "use_aria2": False,
            "cookies_mode": "Disabled",
            "skip_existing": False,
        }

    def run_worker(self, engine, seen):
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker("task-js", "https://youtu.be/abc", self.options(folder))
            worker.signals.error.connect(lambda _task_id, _message: None)
            with mock.patch.object(yt_dlp, "YoutubeDL", engine), \
                    mock.patch.object(downloader_module.time, "sleep"):
                worker.run()
        return seen

    def test_every_attempt_is_offered_a_javascript_runtime(self):
        seen = []

        class FakeYoutubeDL:
            def __init__(self, opts):
                seen.append(set((opts.get("js_runtimes") or {}).keys()))

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, target, download=False):
                raise yt_dlp.utils.DownloadError("boom")

        self.run_worker(FakeYoutubeDL, seen)
        self.assertTrue(seen, "yt-dlp was never started")
        for runtimes in seen:
            self.assertEqual(runtimes, {"deno", "node", "bun", "quickjs"})

    def test_yt_dlp_dropping_a_runtime_does_not_leak_into_the_next_attempt(self):
        seen = []

        class PickyYoutubeDL:
            def __init__(self, opts):
                runtimes = opts.get("js_runtimes") or {}
                seen.append(set(runtimes))
                # yt-dlp's _clean_js_runtimes pops unsupported names in place.
                runtimes.pop("bun", None)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, target, download=False):
                raise yt_dlp.utils.DownloadError("boom")

        self.run_worker(PickyYoutubeDL, seen)
        self.assertEqual(len(seen), 4)
        for runtimes in seen:
            self.assertIn("bun", runtimes)


if __name__ == "__main__":
    unittest.main()
