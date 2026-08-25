import os
import uuid
import time
import webbrowser
import winsound  # Standard library module to trigger clean system chimes
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QTextEdit, QPushButton, QComboBox, QCheckBox,
                               QLineEdit, QFileDialog, QTableWidget, QTableWidgetItem,
                               QHeaderView, QProgressBar, QMessageBox, QApplication, QScrollBar,
                               QGridLayout, QMenu, QSystemTrayIcon, QStyle, QDialog, QFormLayout)
from PySide6.QtCore import QThreadPool, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QIcon, QTextCharFormat, QTextCursor,
                           QKeySequence, QShortcut)

# Initial extraction overhead guess per task until real measurements arrive
DEFAULT_EXTRACTION_SECONDS = 2.5
# Rolling window size of measured extraction durations kept for averaging
EXTRACTION_SAMPLE_WINDOW = 20
# Simultaneous video downloads. Each progressive download is one HTTP
# connection (~5-8 MB/s each), so this cap directly bounds aggregate
# bandwidth; 8 lets fast lines saturate without spamming YouTube
MAX_VIDEO_DOWNLOADS = 8
# Audio tracks are tiny on bandwidth but each spawns a one-core FFmpeg MP3
# conversion, so a wide pool converts whole batches across every CPU core
MAX_AUDIO_DOWNLOADS = min(max(os.cpu_count() or 4, 4), 16)

from .settings import Settings
from .downloader import DownloadWorker, TitlePreviewWorker
from .logger import log
from .themes import THEMES, build_theme
from .updater import APP_VERSION, UpdateWorker
from .utils import extract_http_links, format_elapsed_words, format_hms, get_icon_path, is_youtube_url
from .widgets import DesktopToast
from .win_taskbar import WinTaskbarProgress

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Batch Downloader")
        self.resize(950, 600)
        self.settings = Settings()
        
        # Load and set Window Icon
        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        
        self.threadpool = QThreadPool()
        # Max out parallel thread pool across all CPU logical cores
        max_threads = max(12, (os.cpu_count() or 4) * 2)
        self.threadpool.setMaxThreadCount(max_threads)

        # Dedicated pools: videos share limited bandwidth so stay tightly capped,
        # while audio tasks parallelize their CPU-bound conversions across cores
        self.video_pool = QThreadPool()
        self.video_pool.setMaxThreadCount(MAX_VIDEO_DOWNLOADS)
        self.audio_pool = QThreadPool()
        self.audio_pool.setMaxThreadCount(MAX_AUDIO_DOWNLOADS)
        
        self.active_workers = {}
        self.row_mapping = {}
        self.task_data = {}        # Tracks URL and configurations for manual retry loops
        self.completed_paths = {}  # Caches output filepaths for instant double-click playback
        self.active_metrics = {}    # Tracks realtime speed, bytes left, and ETA per worker
        self.extraction_samples = []  # Rolling window of measured extraction durations
        self.batch_start_time = None

        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.fetch_title_previews)

        # Coalesces O(all-rows) aggregate recalcs (status bar, global %) into one tick
        self.ui_refresh_timer = QTimer()
        self.ui_refresh_timer.setSingleShot(True)
        self.ui_refresh_timer.setInterval(250)
        self.ui_refresh_timer.timeout.connect(self.refresh_aggregates)

        # Remembers the last text previews were fetched for, to skip redundant refetches
        self._last_preview_text = ""

        self.setup_ui()
        self.desktop_toast = DesktopToast()
        self.apply_settings()

        # Windows taskbar progress overlay + completion tray notifications
        self.taskbar = WinTaskbarProgress()
        self.taskbar.attach(self)
        tray_icon_source = self.windowIcon()
        if tray_icon_source.isNull():
            tray_icon_source = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon = QSystemTrayIcon(tray_icon_source, self)

        # Debounced clipboard monitor: coalesces rapid copies into one quiet batch add
        self.clipboard_timer = QTimer()
        self.clipboard_timer.setSingleShot(True)
        self.clipboard_timer.setInterval(400)
        self.clipboard_timer.timeout.connect(self.process_clipboard_batch)
        self._last_clipboard_text = None

        # Connect the OS clipboard monitor signal
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)
        self.chk_monitor_clip.toggled.connect(self.on_monitor_toggled)

        # Trigger silent update check on startup
        QTimer.singleShot(1000, lambda: self.check_for_updates(manual=False))

        # Pre-fill any YouTube links already sitting on the clipboard; deferred so
        # the window paints instantly instead of waiting on a possibly slow/locked
        # OS clipboard read during startup.
        QTimer.singleShot(150, self.prefill_from_clipboard)

    def on_monitor_toggled(self, checked: bool):
        if checked:
            self.desktop_toast.show_notification(
                "✓ Clipboard Monitor Active",
                "Any copied YouTube links will automatically be added to your queue.",
                2500
            )
        self.save_current_settings()

    def closeEvent(self, event):
        """Drains background pools so interpreter shutdown never races live worker
        threads (prevents 'can't register atexit after shutdown' tracebacks)."""
        self.preview_timer.stop()
        self.clipboard_timer.stop()
        self.ui_refresh_timer.stop()
        self.threadpool.clear()
        self.video_pool.clear()
        self.audio_pool.clear()
        self.threadpool.waitForDone(2000)
        self.video_pool.waitForDone(2000)
        self.audio_pool.waitForDone(2000)
        super().closeEvent(event)

    def check_for_updates(self, manual: bool = False):
        worker = UpdateWorker(APP_VERSION, manual=manual)
        worker.signals.update_available.connect(self.on_update_available)
        worker.signals.no_update.connect(self.on_no_update)
        worker.signals.error.connect(self.on_update_error)
        self.threadpool.start(worker)

    def on_update_available(self, latest_ver: str, url: str):
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"A new version ({latest_ver}) of YouTube Batch Downloader is available!\n\n"
            f"Would you like to open GitHub to download the update?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            webbrowser.open(url)

    def on_no_update(self, manual: bool):
        if manual:
            QMessageBox.information(self, "No Updates", f"You are using the latest version ({APP_VERSION}).")

    def on_update_error(self, err_msg: str):
        QMessageBox.warning(self, "Update Check Failed", f"Could not check for updates:\n{err_msg}")

    @staticmethod
    def _mirror_scrollbar_range(source, mirror):
        """Mirrors a scrollbar's range and page step onto a standalone scrollbar."""
        def sync_range(min_val, max_val):
            mirror.setRange(min_val, max_val)
            mirror.setPageStep(source.pageStep())
        source.rangeChanged.connect(sync_range)

    def _bind_standalone_scrollbar(self, editor_sb, standalone_sb):
        """Two-way binding between an editor scrollbar and its dedicated standalone bar."""
        self._mirror_scrollbar_range(editor_sb, standalone_sb)
        standalone_sb.valueChanged.connect(editor_sb.setValue)
        editor_sb.valueChanged.connect(standalone_sb.setValue)

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Accept URL/text drops anywhere on the window
        self.setAcceptDrops(True)

        # ---------------- URL Input & Title Preview Area ----------------
        input_grid = QGridLayout()
        
        # Row 0: Headers
        self.lbl_url_header = QLabel("<b>URLs (One per line) [0 links]:</b>")
        input_grid.addWidget(self.lbl_url_header, 0, 0)
        
        lbl_preview_header = QLabel("<b>Title Preview:</b>")
        input_grid.addWidget(lbl_preview_header, 0, 1)
        
        # Row 1: TextBoxes & Vertical Scrollbar
        self.url_input = QTextEdit()
        self.url_input.setLineWrapMode(QTextEdit.NoWrap)
        self.url_input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.url_input.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.url_input.setPlaceholderText(
            "https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...\n\n"
            "Tip: Drop or paste links anywhere, then press Ctrl+Enter."
        )
        self.url_input.textChanged.connect(self.on_url_input_changed)
        input_grid.addWidget(self.url_input, 1, 0)
        
        self.preview_input = QTextEdit()
        self.preview_input.setLineWrapMode(QTextEdit.NoWrap)
        self.preview_input.setReadOnly(True)
        self.preview_input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.preview_input.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.preview_input.setPlaceholderText("Title previews will automatically appear here...")
        input_grid.addWidget(self.preview_input, 1, 1)
        
        self.sync_v_scrollbar = QScrollBar(Qt.Vertical)
        input_grid.addWidget(self.sync_v_scrollbar, 1, 2)
        
        # Row 2: Horizontal Scrollbars
        self.url_h_scrollbar = QScrollBar(Qt.Horizontal)
        input_grid.addWidget(self.url_h_scrollbar, 2, 0)
        
        self.preview_h_scrollbar = QScrollBar(Qt.Horizontal)
        input_grid.addWidget(self.preview_h_scrollbar, 2, 1)
        
        layout.addLayout(input_grid)

        # Standardize fonts, document margins, and paddings for exact pixel line alignment
        font = self.url_input.font()
        self.preview_input.setFont(font)
        self.url_input.document().setDocumentMargin(4)
        self.preview_input.document().setDocumentMargin(4)

        # --- Synchronize Scrollbars ---
        url_v_sb = self.url_input.verticalScrollBar()
        preview_v_sb = self.preview_input.verticalScrollBar()
        url_h_sb = self.url_input.horizontalScrollBar()
        preview_h_sb = self.preview_input.horizontalScrollBar()

        # Shared vertical bar acts as the hub driving both text editors
        self._mirror_scrollbar_range(url_v_sb, self.sync_v_scrollbar)
        self.sync_v_scrollbar.valueChanged.connect(url_v_sb.setValue)
        self.sync_v_scrollbar.valueChanged.connect(preview_v_sb.setValue)
        url_v_sb.valueChanged.connect(self.sync_v_scrollbar.setValue)
        preview_v_sb.valueChanged.connect(self.sync_v_scrollbar.setValue)

        self._bind_standalone_scrollbar(url_h_sb, self.url_h_scrollbar)
        self._bind_standalone_scrollbar(preview_h_sb, self.preview_h_scrollbar)

        # --- Force Initial State Synchronization ---
        # Prevents the scrollbars from starting with a default 0-99 range (tiny thumb)
        for source, mirror in [
            (url_v_sb, self.sync_v_scrollbar),
            (url_h_sb, self.url_h_scrollbar),
            (preview_h_sb, self.preview_h_scrollbar),
        ]:
            mirror.setRange(source.minimum(), source.maximum())
            mirror.setPageStep(source.pageStep())

        url_btn_layout = QHBoxLayout()
        btn_paste = QPushButton("Paste Clipboard")
        btn_paste.clicked.connect(self.url_input.paste)
        btn_clear = QPushButton("Clear URLs")
        btn_clear.clicked.connect(self.url_input.clear)
        url_btn_layout.addWidget(btn_paste)
        url_btn_layout.addWidget(btn_clear)
        url_btn_layout.addStretch()

        # Compact "find inside pasted list" moved onto this row to save a full row
        url_btn_layout.addWidget(QLabel("Find:"))
        self.search_url_input = QLineEdit()
        self.search_url_input.setPlaceholderText("Highlight in URLs...")
        self.search_url_input.setMaximumWidth(220)
        self.search_url_input.textChanged.connect(self.search_input_textboxes)
        url_btn_layout.addWidget(self.search_url_input)

        self.lbl_url_matches = QLabel("")
        url_btn_layout.addWidget(self.lbl_url_matches)
        layout.addLayout(url_btn_layout)

        # ---------------- Download Options Dialog ----------------
        # Every conversion choice lives behind one compact chip on the main page
        self.video_qualities = ["Best", "4K (2160p)", "1440p (2K)", "1080p", "720p", "480p"]
        self.audio_qualities = [
            "320 kbps (Extreme)",
            "256 kbps (Very High)",
            "192 kbps (High / Standard)",
            "128 kbps (Medium)",
            "96 kbps (Low / Small Size)"
        ]

        self.options_dialog = QDialog(self)
        self.options_dialog.setWindowTitle("Download Options")
        options_form = QFormLayout(self.options_dialog)
        options_form.setLabelAlignment(Qt.AlignRight)
        options_form.setHorizontalSpacing(14)

        # Formats
        self.combo_format = QComboBox()
        self.combo_format.addItems([
            "Best Quality (MKV)",
            "MP4 Video",
            "WEBM Video",
            "AVI Video",
            "MOV Video",
            "MP3 Audio",
            "M4A Audio",
            "WAV Audio",
            "FLAC Audio",
            "AAC Audio",
            "OPUS Audio"
        ])
        options_form.addRow("Format:", self.combo_format)

        # Quality (Dynamic Label & Items)
        quality_row = QWidget()
        quality_lay = QHBoxLayout(quality_row)
        quality_lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_quality = QLabel("Max Resolution:")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(self.video_qualities)
        quality_lay.addWidget(self.lbl_quality)
        quality_lay.addWidget(self.combo_quality)
        quality_lay.addStretch()
        options_form.addRow("Quality:", quality_row)

        # Switch quality options dynamically when format changes
        self.combo_format.currentTextChanged.connect(self.on_format_changed)
        self.combo_quality.currentTextChanged.connect(lambda: self.save_current_settings())

        # Audio Boost
        self.combo_boost = QComboBox()
        self.combo_boost.addItems([
            "100% (Original)",
            "125% (+2 dB)",
            "150% (+3.5 dB)",
            "175% (+5 dB)",
            "200% (+6 dB)",
            "250% (+8 dB)",
            "300% (+9.5 dB)"
        ])
        options_form.addRow("Audio Boost:", self.combo_boost)

        # Behavior toggles
        options_form.addRow(QLabel("<b>Behavior</b>"))
        self.chk_auto_clear = QCheckBox("Automatically clear completed downloads (after 2 seconds)")
        self.chk_monitor_clip = QCheckBox("Auto-Add links from Clipboard (Real-time Monitor)")
        options_form.addRow(self.chk_auto_clear)
        options_form.addRow(self.chk_monitor_clip)

        # Footer: theme switcher + update check live here instead of the main page
        footer_row = QWidget()
        footer_lay = QHBoxLayout(footer_row)
        footer_lay.setContentsMargins(0, 0, 0, 0)
        footer_lay.addWidget(QLabel("Theme:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(THEMES)
        saved_theme = self.settings.get("theme", "Dark")
        theme_idx = self.combo_theme.findText(saved_theme if saved_theme in THEMES else "Dark")
        self.combo_theme.setCurrentIndex(theme_idx if theme_idx != -1 else 0)
        self.combo_theme.currentTextChanged.connect(self._change_theme)
        footer_lay.addWidget(self.combo_theme)
        footer_lay.addStretch()
        btn_check_update = QPushButton("Check for Updates")
        btn_check_update.clicked.connect(lambda: self.check_for_updates(manual=True))
        btn_close_options = QPushButton("Close")
        btn_close_options.clicked.connect(self.options_dialog.close)
        footer_lay.addWidget(btn_check_update)
        footer_lay.addWidget(btn_close_options)
        options_form.addRow(footer_row)

        # Keep the main-page chip in sync with every option change
        self.combo_format.currentTextChanged.connect(lambda _: self._update_options_chip_text())
        self.combo_quality.currentTextChanged.connect(lambda _: self._update_options_chip_text())
        self.combo_boost.currentTextChanged.connect(lambda _: self._update_options_chip_text())

        # ---------------- Download Path ----------------
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Download Folder:"))
        self.entry_path = QLineEdit()
        self.entry_path.setReadOnly(True)
        path_layout.addWidget(self.entry_path)
        
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.browse_folder)
        path_layout.addWidget(btn_browse)

        btn_open_folder = QPushButton("Open Folder")
        btn_open_folder.clicked.connect(self.open_downloads_folder)
        path_layout.addWidget(btn_open_folder)
        
        layout.addLayout(path_layout)

        # ---------------- Main Action Bar ----------------
        action_layout = QHBoxLayout()

        # Single compact chip summarizing current conversion choices
        self.btn_options = QPushButton()
        self.btn_options.setProperty("variant", "chip")
        self.btn_options.setCursor(Qt.PointingHandCursor)
        self.btn_options.clicked.connect(self.open_download_options)
        self._update_options_chip_text()
        action_layout.addWidget(self.btn_options)

        action_layout.addStretch()

        btn_download = QPushButton("Add to Queue and Download")
        btn_download.setProperty("variant", "primary")
        btn_download.clicked.connect(self.start_downloads)
        action_layout.addWidget(btn_download)

        btn_cancel_all = QPushButton("Cancel All")
        btn_cancel_all.setProperty("variant", "danger")
        btn_cancel_all.clicked.connect(self.cancel_all_tasks)
        action_layout.addWidget(btn_cancel_all)

        btn_clear_completed = QPushButton("Clear Completed")
        btn_clear_completed.clicked.connect(self.clear_completed_tasks)
        action_layout.addWidget(btn_clear_completed)

        layout.addLayout(action_layout)

        # Keyboard shortcut: Ctrl+Enter / Ctrl+Return starts the queue instantly
        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            start_shortcut = QShortcut(QKeySequence(seq), self)
            start_shortcut.activated.connect(self.start_downloads)

        # ---------------- Search Bar & Queue Table ----------------
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter Queue:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search queue by video title or URL...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Video Title", "Status", "Progress", "Speed", "ETA", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Connect double-click on cells to run instant playback
        self.table.cellDoubleClicked.connect(self.on_table_double_clicked)

        # Right-click context menu per row (retry, copy URL, open folder, remove...)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_row_context_menu)

        layout.addWidget(self.table)

        # ---------------- Universal Loading Bar ----------------
        self.global_progress = QProgressBar()
        self.global_progress.setObjectName("globalProgress")
        self.global_progress.setValue(0)
        self.global_progress.setFixedHeight(20)
        self.global_progress.setFormat("No active tasks")
        self.global_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.global_progress)

        # ---------------- Bottom Status Bar ----------------
        self._apply_theme()
        self.statusBar = self.statusBar()
        self.update_status_summary()

    def _apply_theme(self):
        """Applies the persisted theme (Dark default) as QSS + application palette."""
        theme_name = self.settings.get("theme", "Dark")
        qss, palette = build_theme(theme_name)
        QApplication.instance().setPalette(palette)
        self.setStyleSheet(qss)
        self._current_theme = "Light" if isinstance(theme_name, str) and theme_name.strip().lower() == "light" else "Dark"

    def _change_theme(self, display_name: str):
        """Persists and live-applies a theme chosen in the options dialog."""
        self.settings.set("theme", display_name)
        self._apply_theme()

    def on_format_changed(self, format_name: str):
        """Dynamically toggles quality dropdown between Video Resolutions and Audio Bitrates."""
        self.combo_quality.blockSignals(True)
        self.combo_quality.clear()
        
        if "Audio" in format_name:
            self.lbl_quality.setText("Audio Quality:")
            self.combo_quality.addItems(self.audio_qualities)
            saved_audio_q = self.settings.get("audio_quality", "192 kbps (High / Standard)")
            idx = self.combo_quality.findText(saved_audio_q)
            self.combo_quality.setCurrentIndex(idx if idx != -1 else 0)
        else:
            self.lbl_quality.setText("Max Resolution:")
            self.combo_quality.addItems(self.video_qualities)
            saved_video_q = self.settings.get("video_quality", "Best")
            idx = self.combo_quality.findText(saved_video_q)
            self.combo_quality.setCurrentIndex(idx if idx != -1 else 0)

        self.combo_quality.blockSignals(False)
        # Quality label + items just changed; refresh the main-page chip too
        self._update_options_chip_text()

    def open_download_options(self):
        """Shows the consolidated download options dialog."""
        self.options_dialog.exec()

    def _update_options_chip_text(self):
        """Summarizes the current conversion choices onto the main-page chip."""
        fmt = self.combo_format.currentText()
        qual = self.combo_quality.currentText()
        boost_pct = self.combo_boost.currentText().split(' ')[0]

        short_fmt = fmt.replace(' Video', '').replace(' Audio', '')
        text = f"⚙  {short_fmt} · {qual}"
        if not boost_pct.startswith('100'):
            text += f" · Boost {boost_pct}"
        self.btn_options.setText(text)
        self.btn_options.setToolTip(
            f"Format: {fmt}\nQuality: {qual}\nAudio Boost: {self.combo_boost.currentText()}\n\n"
            f"Click to change download options"
        )

    def apply_settings(self):
        self.entry_path.setText(self.settings.get("download_path"))
        saved_format = self.settings.get("format", "MP4 Video")
        self.combo_format.setCurrentText(saved_format)
        self.on_format_changed(saved_format)
        self.combo_boost.setCurrentText(self.settings.get("audio_boost", "100% (Original)"))
        # blockSignals prevents the "Monitor Active" toast + settings save from
        # firing as a spurious side effect of restoring checkboxes at startup
        for chk, value in ((self.chk_auto_clear, self.settings.get("auto_clear")),
                           (self.chk_monitor_clip, self.settings.get("monitor_clipboard"))):
            chk.blockSignals(True)
            chk.setChecked(value)
            chk.blockSignals(False)

    def save_current_settings(self):
        fmt = self.combo_format.currentText()
        current_q = self.combo_quality.currentText()
        self.settings.set("download_path", self.entry_path.text())
        self.settings.set("format", fmt)
        self.settings.set("quality", current_q)
        
        if "Audio" in fmt:
            self.settings.set("audio_quality", current_q)
        else:
            self.settings.set("video_quality", current_q)
            
        self.settings.set("audio_boost", self.combo_boost.currentText())
        self.settings.set("auto_clear", self.chk_auto_clear.isChecked())
        self.settings.set("monitor_clipboard", self.chk_monitor_clip.isChecked())

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.entry_path.text())
        if folder:
            self.entry_path.setText(folder)
            self.save_current_settings()

    def open_downloads_folder(self):
        folder = self.entry_path.text()
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def open_file(self, file_path):
        if file_path and os.path.exists(file_path):
            try:
                os.startfile(file_path)
            except Exception as e:
                log.error(f"Failed to play file {file_path}: {e}")
                self.open_downloads_folder()
        else:
            self.open_downloads_folder()

    def play_finished_sound(self):
        """Triggers a gentle asynchronous system notification sound."""
        try:
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    def on_clipboard_changed(self):
        """Debounce trigger: batches rapid clipboard copies into a single add."""
        if not self.chk_monitor_clip.isChecked():
            return
        self.clipboard_timer.start()

    def process_clipboard_batch(self):
        """Adds any NEW YouTube links found on the clipboard in one quiet batch."""
        if not self.chk_monitor_clip.isChecked():
            return
        try:
            text = self.clipboard.text() or ""
        except Exception:
            # Clipboard momentarily locked by another app; skip this tick silently
            return

        if not text or text == self._last_clipboard_text:
            return
        self._last_clipboard_text = text

        links = [l for l in extract_http_links(text) if is_youtube_url(l)]
        current_lines = [l.strip() for l in self.url_input.toPlainText().split('\n') if l.strip()]
        known = set(current_lines)
        added = []
        for link in links:
            if link not in known:
                known.add(link)
                added.append(link)

        if not added:
            return

        self.url_input.setPlainText("\n".join(current_lines + added))
        log.info(f"Clipboard Monitor batch-added {len(added)} link(s)")

        display = added[0] if len(added) == 1 else f"{added[0][:42]}..."
        self.desktop_toast.show_notification(
            "✓ YouTube Link Added to Queue" if len(added) == 1 else f"✓ {len(added)} Links Added",
            display,
            2800
        )

    def prefill_from_clipboard(self):
        """Loads any YouTube links already on the clipboard straight into the input."""
        if self.url_input.toPlainText().strip():
            return
        try:
            text = self.clipboard.text() or ""
        except Exception:
            return
        # Remember it so the live monitor never re-adds/re-toasts this same text
        self._last_clipboard_text = text
        links = [l for l in extract_http_links(text) if is_youtube_url(l)]
        links = list(dict.fromkeys(links))
        if not links:
            return
        self.url_input.setPlainText("\n".join(links))
        self.desktop_toast.show_notification(
            "✓ Clipboard Loaded",
            f"{len(links)} YouTube link{'s' if len(links) != 1 else ''} ready — Ctrl+Enter to download",
            3200
        )

    def on_table_double_clicked(self, row, column):
        """Allows double-clicking any complete row to play the downloaded file."""
        task_id = self._row_to_task_id(row)
        
        if task_id:
            file_path = self.completed_paths.get(task_id)
            if file_path:
                self.open_file(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        """Accepts dropped text or URL objects and appends new links to the input."""
        mime = event.mimeData()
        candidates = []
        if mime.hasUrls():
            candidates.extend(url.toString() for url in mime.urls())
        if mime.hasText():
            candidates.append(mime.text())

        links = extract_http_links("\n".join(candidates))

        current_lines = [l.strip() for l in self.url_input.toPlainText().split('\n') if l.strip()]
        known = set(current_lines)
        added = []
        for link in links:
            if link not in known:
                known.add(link)
                added.append(link)

        if added:
            self.url_input.setPlainText("\n".join(current_lines + added))
            self.desktop_toast.show_notification(
                "✓ Links Added",
                f"{len(added)} link{'s' if len(added) != 1 else ''} appended — press Ctrl+Enter to download",
                2800
            )
        event.acceptProposedAction()

    def show_row_context_menu(self, pos):
        """Right-click menu for queue rows: open, copy URL, retry, cancel, remove."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        task_id = self._row_to_task_id(row)
        if not task_id:
            return

        status_item = self.table.item(row, 1)
        status_text = status_item.text() if status_item else ""
        file_path = self.completed_paths.get(task_id)

        menu = QMenu(self)
        act_open = act_folder = None
        if file_path and os.path.exists(file_path):
            act_open = menu.addAction("Open File")
            act_folder = menu.addAction("Open Containing Folder")
            menu.addSeparator()

        act_copy = menu.addAction("Copy URL")
        act_retry = act_cancel = None
        if status_text == "Complete":
            pass
        elif "Failed" in status_text:
            act_retry = menu.addAction("Retry Download")
        else:
            act_cancel = menu.addAction("Cancel Download")
        menu.addSeparator()
        act_remove = menu.addAction("Remove From List")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_open:
            self.open_file(file_path)
        elif chosen == act_folder:
            folder = os.path.dirname(file_path)
            if os.path.isdir(folder):
                os.startfile(folder)
        elif chosen == act_copy:
            url = self.task_data.get(task_id, {}).get('url', '')
            QApplication.clipboard().setText(url)
        elif chosen == act_retry:
            self.retry_task(task_id)
        elif chosen == act_cancel:
            self.cancel_task(task_id)
        elif chosen == act_remove:
            worker = self.active_workers.get(task_id)
            if worker:
                worker.cancel()
            self.remove_task_row(task_id)

    def update_global_progress(self):
        """Calculates and updates the average progress across the entire active queue."""
        total_rows = self.table.rowCount()
        if total_rows == 0:
            self.global_progress.setValue(0)
            self.global_progress.setFormat("No active tasks")
            return

        total_percentage = 0
        for row in range(total_rows):
            progress_widget = self.table.cellWidget(row, 2)
            if isinstance(progress_widget, QProgressBar):
                total_percentage += progress_widget.value()

        avg_progress = int(total_percentage / total_rows)
        self.global_progress.setValue(avg_progress)
        self.global_progress.setFormat(f"Overall Progress: {avg_progress}%")

    def on_url_input_changed(self):
        """Updates total link counter and triggers a debounced timer to fetch title previews."""
        raw_lines = self.url_input.toPlainText().split('\n')
        valid_links = [line for line in raw_lines if line.strip()]
        self.lbl_url_header.setText(f"<b>URLs (One per line) [{len(valid_links)} links]:</b>")
        self.preview_timer.start(350)

    def filter_table(self, query: str):
        """Filters queue table rows dynamically matching title or URL."""
        query = query.strip().lower()
        for row in range(self.table.rowCount()):
            task_id = self._row_to_task_id(row)
            
            title = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            url = self.task_data.get(task_id, {}).get('url', '') if task_id else ""
            
            if not query or query in title.lower() or query in url.lower():
                self.table.setRowHidden(row, False)
            else:
                self.table.setRowHidden(row, True)

    def fetch_title_previews(self):
        text = self.url_input.toPlainText()
        if not text.strip():
            self._last_preview_text = ""
            self.preview_input.clear()
            return

        # Skip the network roundtrip entirely when the input hasn't changed
        if text == self._last_preview_text:
            return
        self._last_preview_text = text

        worker = TitlePreviewWorker(text.split('\n'))
        worker.signals.fetched.connect(self.update_title_previews)
        self.threadpool.start(worker)

    def update_title_previews(self, previews: list):
        self.preview_input.setPlainText("\n".join(previews))
        self.search_input_textboxes()

    def search_input_textboxes(self, query: str = None):
        """Highlights matching URLs or titles in real-time and displays match counts."""
        if query is None:
            query = self.search_url_input.text()
            
        query = query.strip().lower()
        
        self.url_input.setExtraSelections([])
        self.preview_input.setExtraSelections([])
        
        if not query:
            self.lbl_url_matches.setText("")
            return

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#fff176"))  # Soft yellow highlight
        fmt.setForeground(QColor("#000000"))  # Dark text

        url_selections = []
        preview_selections = []
        match_count = 0
        first_match_block = -1

        url_lines = self.url_input.toPlainText().split('\n')
        preview_lines = self.preview_input.toPlainText().split('\n')

        max_len = max(len(url_lines), len(preview_lines))
        for idx in range(max_len):
            u_line = url_lines[idx] if idx < len(url_lines) else ""
            p_line = preview_lines[idx] if idx < len(preview_lines) else ""

            if (u_line and query in u_line.lower()) or (p_line and query in p_line.lower()):
                match_count += 1
                if first_match_block == -1:
                    first_match_block = idx

                # Highlight line in url_input
                block_u = self.url_input.document().findBlockByLineNumber(idx)
                if block_u.isValid():
                    cursor_u = QTextCursor(block_u)
                    cursor_u.select(QTextCursor.SelectionType.LineUnderCursor)
                    sel_u = QTextEdit.ExtraSelection()
                    sel_u.cursor = cursor_u
                    sel_u.format = fmt
                    url_selections.append(sel_u)

                # Highlight line in preview_input
                block_p = self.preview_input.document().findBlockByLineNumber(idx)
                if block_p.isValid():
                    cursor_p = QTextCursor(block_p)
                    cursor_p.select(QTextCursor.SelectionType.LineUnderCursor)
                    sel_p = QTextEdit.ExtraSelection()
                    sel_p.cursor = cursor_p
                    sel_p.format = fmt
                    preview_selections.append(sel_p)

        self.url_input.setExtraSelections(url_selections)
        self.preview_input.setExtraSelections(preview_selections)

        if match_count > 0:
            self.lbl_url_matches.setText(f"<font color='#2e7d32'><b>{match_count} match{'es' if match_count != 1 else ''} found</b></font>")
            if first_match_block != -1:
                block = self.url_input.document().findBlockByLineNumber(first_match_block)
                if block.isValid():
                    cursor = QTextCursor(block)
                    self.url_input.setTextCursor(cursor)
        else:
            self.lbl_url_matches.setText("<font color='#d32f2f'><b>No matches found</b></font>")

    def cancel_all_tasks(self):
        """Smart cancel handler checking for completed tasks and active queue state."""
        total_rows = len(self.row_mapping)
        if total_rows == 0:
            QMessageBox.information(self, "Cancel All", "No downloads in queue.")
            return

        completed_ids = [
            tid for tid, row in list(self.row_mapping.items())
            if self.table.item(row, 1) and self.table.item(row, 1).text() == "Complete"
        ]
        
        active_or_queued_ids = [
            tid for tid in list(self.row_mapping.keys())
            if tid not in completed_ids
        ]

        # Case 1: Completed songs exist
        if completed_ids:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Cancel All Tasks")
            msg_box.setText("Do you want to delete completed songs/files too?")
            
            btn_yes = msg_box.addButton("Yes", QMessageBox.YesRole)
            btn_no = msg_box.addButton("No (Cancel Active Only)", QMessageBox.NoRole)
            btn_cancel = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            
            msg_box.exec()
            clicked = msg_box.clickedButton()
            
            if clicked == btn_cancel:
                return

            if clicked == btn_yes:
                for tid in completed_ids:
                    file_path = self.completed_paths.get(tid)
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            log.info(f"Deleted completed file: {file_path}")
                        except Exception as e:
                            log.error(f"Failed to delete file {file_path}: {e}")
                    self.remove_task_row(tid)

            # Cancel running/queued tasks for both 'Yes' and 'No'
            for task_id in active_or_queued_ids:
                self.cancel_task(task_id)

        # Case 2: No completed songs exist, but running/queued downloads exist
        elif active_or_queued_ids:
            reply = QMessageBox.question(
                self,
                "Cancel Running Downloads",
                "Are you sure you want to cancel the running downloads?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                for task_id in active_or_queued_ids:
                    self.cancel_task(task_id)

    def update_status_summary(self):
        """Calculates size-based and bandwidth-aware Total ETA including extraction overhead."""
        total = self.table.rowCount()
        # Only workers actually running inside the pools count as Active; the
        # remainder are still waiting in queue for a free download slot.
        pool_running = self.video_pool.activeThreadCount() + self.audio_pool.activeThreadCount()
        active = min(len(self.active_workers), max(pool_running, 0))

        completed = 0
        failed = 0
        for row in range(total):
            item = self.table.item(row, 1)
            if item:
                status = item.text()
                if status == "Complete":
                    completed += 1
                elif "Failed" in status:
                    failed += 1

        queued = max(0, total - completed - failed - active)

        # Advanced Speed + File Size + Extraction Overhead Calculation
        eta_str = "-"
        if active > 0 or queued > 0:
            total_active_speed = 0
            active_bytes_remaining = 0
            
            for tid, metrics in list(self.active_metrics.items()):
                speed = metrics.get('speed_bytes', 0) or 0
                total_b = metrics.get('total_bytes', 0) or 0
                done_b = metrics.get('downloaded_bytes', 0) or 0
                
                total_active_speed += speed
                if total_b > done_b:
                    active_bytes_remaining += (total_b - done_b)

            # Format-based size estimation for queued items (MP3 ~8MB, Video ~40MB)
            fmt_choice = self.combo_format.currentText()
            est_size_per_queued = 8 * 1024 * 1024 if fmt_choice == "MP3 Audio" else 40 * 1024 * 1024
            queued_bytes_remaining = queued * est_size_per_queued
            
            total_bytes_remaining = active_bytes_remaining + queued_bytes_remaining
            
            # Estimate download time
            download_time_sec = 0
            if total_active_speed > 0:
                download_time_sec = total_bytes_remaining / total_active_speed
            else:
                # Fallback to sum of active ETAs if speed metric isn't directly available yet
                active_etas = [m.get('eta_seconds', 0) for m in self.active_metrics.values() if m.get('eta_seconds')]
                download_time_sec = max(active_etas) if active_etas else 0

            # Measured API handshake + FFmpeg extraction overhead: rolling session
            # average of real durations, falling back to the initial estimate first
            if self.extraction_samples:
                extraction_per_task = sum(self.extraction_samples) / len(self.extraction_samples)
            else:
                extraction_per_task = DEFAULT_EXTRACTION_SECONDS
            total_extraction_time = (active + queued) * extraction_per_task
            
            total_estimated_seconds = int(download_time_sec + total_extraction_time)
            
            if total_estimated_seconds > 0:
                eta_str = format_hms(total_estimated_seconds)

        self.statusBar.showMessage(f"Total Tasks: {total}  |  Active: {active}  |  Queued: {queued}  |  Completed: {completed}  |  Failed: {failed}  |  Total ETA: {eta_str}")

    def queue_ui_refresh(self):
        """Coalesces expensive all-rows recalcs into a single timer tick."""
        if not self.ui_refresh_timer.isActive():
            self.ui_refresh_timer.start()

    def refresh_aggregates(self):
        """One-shot refresh of every aggregate indicator plus the taskbar overlay."""
        self.update_global_progress()
        self.update_status_summary()
        self.sync_taskbar_progress()

    def sync_taskbar_progress(self):
        """Mirrors overall batch progress onto the Windows taskbar button."""
        if len(self.active_workers) > 0 and self.table.rowCount() > 0:
            self.taskbar.set_progress(self.global_progress.value(), 100)
        else:
            self.taskbar.clear()

    def notify_batch_done(self, completion_msg: str = ""):
        """Fires a tray notification and flashes the window when a whole batch ends."""
        completed = failed = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if not item:
                continue
            status_text = item.text()
            if status_text == "Complete":
                completed += 1
            elif "Failed" in status_text:
                failed += 1

        if failed > 0:
            tray_title = f"Batch Finished — {failed} Failed"
            tray_body = f"{completed} downloaded successfully, {failed} failed."
            tray_icon = QSystemTrayIcon.Warning
        else:
            tray_title = "Downloads Complete"
            tray_body = completion_msg or f"{completed} file{'s' if completed != 1 else ''} downloaded successfully."
            tray_icon = QSystemTrayIcon.Information
        self.tray_icon.showMessage(tray_title, tray_body, tray_icon, 4000)

        # Flash the taskbar entry to pull attention when the window is in background
        if not self.isActiveWindow():
            QApplication.alert(self, 2000)

    def start_downloads(self):
        raw_url_lines = self.url_input.toPlainText().split('\n')
        raw_preview_lines = self.preview_input.toPlainText().split('\n')

        # Pair every non-empty URL line with its aligned preview title
        entries = []
        for i, line in enumerate(raw_url_lines):
            u = line.strip()
            if not u:
                continue
            p = raw_preview_lines[i].strip() if i < len(raw_preview_lines) else ""
            if not p or p in ["Failed to load title", "Invalid URL"]:
                p = None
            entries.append((u, p))

        if not entries:
            QMessageBox.warning(self, "Input Error", "Please provide at least one valid URL.")
            return

        # Duplicate guard: skip links repeated in the input or already queued this session
        known_urls = {info.get('url') for info in self.task_data.values()}
        unique_entries = []
        skipped_dupes = 0
        for url, preview in entries:
            if url in known_urls:
                skipped_dupes += 1
                continue
            known_urls.add(url)
            unique_entries.append((url, preview))

        if not unique_entries:
            QMessageBox.information(self, "Nothing New", "All links are already in the download queue.")
            return

        if skipped_dupes:
            self.desktop_toast.show_notification(
                "✓ Duplicates Skipped",
                f"{skipped_dupes} duplicate link{'s' if skipped_dupes != 1 else ''} ignored.",
                2600
            )

        self.batch_start_time = time.time()
        os.makedirs(self.entry_path.text(), exist_ok=True)
        self.save_current_settings()

        options = {
            'download_path': self.entry_path.text(),
            'format': self.combo_format.currentText(),
            'quality': self.combo_quality.currentText(),
            'audio_boost': self.combo_boost.currentText(),
            'use_aria2': bool(self.settings.get("use_aria2", False)),
            'queued_time': self.batch_start_time
        }

        for url, cached_title in unique_entries:
            self.add_task(url, options, title=cached_title)

    def _make_cancel_button(self, task_id: str) -> QPushButton:
        """Builds a Cancel button wired to the given task id."""
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("variant", "cell")
        btn_cancel.clicked.connect(lambda _, tid=task_id: self.cancel_task(tid))
        return btn_cancel

    def _pool_for_format(self, fmt) -> QThreadPool:
        """Audio tasks use the wide conversion pool; video stays bandwidth-capped."""
        return self.audio_pool if "Audio" in (fmt or "") else self.video_pool

    def _launch_download_worker(self, task_id: str, url: str, options: dict, pre_data: dict = None):
        """Builds, wires and queues a DownloadWorker for the given task."""
        worker = DownloadWorker(task_id, url, options, pre_data)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.task_finished)
        worker.signals.error.connect(self.task_error)

        self.active_workers[task_id] = worker
        # Pool choice enforces the per-format concurrency cap; excess tasks queue
        self._pool_for_format(options.get('format')).start(worker)

    def _row_to_task_id(self, row: int):
        """Reverse lookup returning the task id mapped to a table row, or None."""
        for tid, r_idx in self.row_mapping.items():
            if r_idx == row:
                return tid
        return None

    def add_task(self, url, options, title=None):
        task_id = str(uuid.uuid4())
        
        self.task_data[task_id] = {
            'url': url,
            'options': options
        }

        # Add Row to UI Table
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        
        display_title = title if title else f"Extracting: {url}"
        status_text = "Waiting in Queue..." if title else "Extracting Metadata..."
        status_color = "#2e7d32" if title else "#1565c0"

        title_item = QTableWidgetItem(display_title)
        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(QBrush(QColor(status_color)))
        speed_item = QTableWidgetItem("-")
        eta_item = QTableWidgetItem("-")
        
        progress_bar = QProgressBar()
        progress_bar.setValue(0)
        
        btn_cancel = self._make_cancel_button(task_id)
        
        self.table.setItem(row_idx, 0, title_item)
        self.table.setItem(row_idx, 1, status_item)
        self.table.setCellWidget(row_idx, 2, progress_bar)
        self.table.setItem(row_idx, 3, speed_item)
        self.table.setItem(row_idx, 4, eta_item)
        self.table.setCellWidget(row_idx, 5, btn_cancel)
        
        self.row_mapping[task_id] = row_idx

        # INSTANT 0ms LAUNCH: Bypasses double-pass network roundtrips
        pre_title = title if title else f"Downloading..."
        pre_data = {'title': pre_title}
        self.task_data[task_id]['pre_data'] = pre_data

        self._launch_download_worker(task_id, url, options, pre_data)

        self.filter_table(self.search_input.text())
        self.refresh_aggregates()

    def cancel_task(self, task_id):
        worker = self.active_workers.get(task_id)
        if worker:
            worker.cancel()
            
        # INSTANT TRASH OPTIMIZATION: Discard the UI row from the table immediately 
        # when clicking "Cancel". Background thread handles file deletion safely.
        self.remove_task_row(task_id)

    def retry_task(self, task_id):
        row = self.row_mapping.get(task_id)
        if row is None or task_id not in self.task_data:
            return
            
        task_info = self.task_data[task_id]
        url = task_info['url']
        options = task_info['options']
        
        # Reset row aesthetics to standard active download state
        self.table.item(row, 1).setText("Waiting...")
        self.table.item(row, 1).setForeground(QBrush())  # Reset foreground brush to default
        self.table.cellWidget(row, 2).setValue(0)
        self.table.item(row, 3).setText("-")
        self.table.item(row, 4).setText("-")
        
        # Recreate and assign the Cancel button for the active process
        self.table.setCellWidget(row, 5, self._make_cancel_button(task_id))
        
        # Build and queue the new worker instance
        self._launch_download_worker(task_id, url, options)
        self.refresh_aggregates()

    def remove_task_row(self, task_id):
        row = self.row_mapping.get(task_id)
        if row is None:
            return
            
        self.table.removeRow(row)
        
        # Delete internal state mappings safely
        if task_id in self.row_mapping:
            del self.row_mapping[task_id]
        if task_id in self.task_data:
            del self.task_data[task_id]
        if task_id in self.active_workers:
            del self.active_workers[task_id]
        if task_id in self.completed_paths:
            del self.completed_paths[task_id]
        if task_id in self.active_metrics:
            del self.active_metrics[task_id]
            
        # Shift all succeeding task indices down by 1 in mapping dictionary
        for tid, r_idx in list(self.row_mapping.items()):
            if r_idx > row:
                self.row_mapping[tid] = r_idx - 1

        self.refresh_aggregates()

    def clear_completed_tasks(self):
        completed_ids = []
        for tid, row in list(self.row_mapping.items()):
            item = self.table.item(row, 1)
            if item and item.text() == "Complete":
                completed_ids.append(tid)
                
        for tid in completed_ids:
            self.remove_task_row(tid)

    def update_progress(self, task_id, data):
        row = self.row_mapping.get(task_id)
        if row is None: return

        if 'title' in data:
            self.table.item(row, 0).setText(data['title'])
            
        if 'status_text' in data:
            status = data['status_text']
            self.table.item(row, 1).setText(status)
            
            # Dynamic loading status text color indicators
            if "Analyzing" in status or "Extracting" in status or "Converting" in status or "Merging" in status or "Embedding" in status:
                self.table.item(row, 1).setForeground(QBrush(QColor("#8e24aa")))  # Extraction Purple
            elif "Retrying" in status:
                self.table.item(row, 1).setForeground(QBrush(QColor("#ef6c00")))  # Warning Orange
            elif "Downloading" in status or "Extracted" in status:
                self.table.item(row, 1).setForeground(QBrush(QColor("#2e7d32")))  # Progress Green

        # Switch progress bar between Download % and Animated Extraction Pulse
        progress_bar = self.table.cellWidget(row, 2)
        if isinstance(progress_bar, QProgressBar):
            if data.get('is_postprocessing'):
                progress_bar.setRange(0, 0)  # Indeterminate animated pulse mode
                progress_bar.setFormat("Extracting...")
            else:
                progress_bar.setRange(0, 100)
                if 'percent' in data:
                    perc_str = data['percent'].replace('%', '')
                    try:
                        perc = float(perc_str)
                        progress_bar.setValue(int(perc))
                        progress_bar.setFormat("%p%")
                    except ValueError:
                        pass
            
        if 'speed' in data:
            self.table.item(row, 3).setText(data['speed'])
        if 'eta' in data:
            self.table.item(row, 4).setText(data['eta'])

        # Collect real extraction durations reported by workers for future ETA estimates
        if 'extraction_time' in data:
            self.extraction_samples.append(data['extraction_time'])
            if len(self.extraction_samples) > EXTRACTION_SAMPLE_WINDOW:
                self.extraction_samples.pop(0)

        if not data.get('is_postprocessing'):
            self.active_metrics[task_id] = {
                'speed_bytes': data.get('speed_bytes', 0),
                'downloaded_bytes': data.get('downloaded_bytes', 0),
                'total_bytes': data.get('total_bytes', 0),
                'eta_seconds': data.get('eta_seconds', 0)
            }
        # High-frequency path: aggregate recalcs are coalesced onto a 250ms timer
        self.queue_ui_refresh()

    def task_finished(self, task_id, file_path, completion_msg="", elapsed_str=""):
        row = self.row_mapping.get(task_id)
        if row is None: return  # Safe exit if row was already removed/cancelled

        self.table.item(row, 1).setText("Complete")
        self.table.item(row, 1).setForeground(QBrush(QColor("#2e7d32")))  # Solid Success Green
        
        # Reset progress bar to standard 100% format
        progress_bar = self.table.cellWidget(row, 2)
        if isinstance(progress_bar, QProgressBar):
            progress_bar.setRange(0, 100)
            progress_bar.setValue(100)
            progress_bar.setFormat("100%")

        self.table.item(row, 3).setText("-")
        if elapsed_str:
            self.table.item(row, 4).setText(f"Done in {elapsed_str}")
        else:
            self.table.item(row, 4).setText("-")
        
        # Cache file path for double-click playback functionality
        self.completed_paths[task_id] = file_path
        
        # Replace actions column button with instant play button
        btn_open = QPushButton("Open File")
        btn_open.setProperty("variant", "cell-primary")
        btn_open.clicked.connect(lambda _, fp=file_path: self.open_file(fp))
        self.table.setCellWidget(row, 5, btn_open)
        
        self.refresh_aggregates()

        # Automatically clear completed row after 2 seconds if checked
        if self.chk_auto_clear.isChecked():
            QTimer.singleShot(2000, lambda: self.remove_task_row(task_id))

        self._cleanup_worker(task_id)

        # Play system sound notification and show total batch duration when all tasks finish
        if len(self.active_workers) == 0:
            if self.batch_start_time:
                batch_sec = int(time.time() - self.batch_start_time)
                completion_msg = f"Your download completed in {format_elapsed_words(batch_sec)}"

            self.play_finished_sound()
            self.notify_batch_done(completion_msg)

        if completion_msg:
            self.statusBar.showMessage(completion_msg, 10000)
            
        log.info(f"Task {task_id} completed: {completion_msg}. Path: {file_path}")

    def task_error(self, task_id, error_msg):
        row = self.row_mapping.get(task_id)
        if row is None: return  # Safe exit if row was already removed/cancelled

        self.table.item(row, 1).setText(error_msg)
        self.table.item(row, 1).setForeground(QBrush(QColor("#d32f2f")))  # Soft red for error text
        
        # Replace the Cancel button with a highly visible "Retry" button
        btn_retry = QPushButton("Retry")
        btn_retry.setProperty("variant", "cell-danger")
        btn_retry.clicked.connect(lambda _, tid=task_id: self.retry_task(tid))
        self.table.setCellWidget(row, 5, btn_retry)
            
        self.refresh_aggregates()
        self._cleanup_worker(task_id)

        # Play system sound notification if all active processing is finished (even on fail)
        if len(self.active_workers) == 0:
            self.play_finished_sound()

    def _cleanup_worker(self, task_id):
        if task_id in self.active_workers:
            del self.active_workers[task_id]