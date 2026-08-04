import os
import uuid
import json
import urllib.request
import re
import webbrowser
import winsound  # Standard library module to trigger clean system chimes
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QTextEdit, QPushButton, QComboBox, QCheckBox, 
                               QLineEdit, QFileDialog, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QProgressBar, QMessageBox, QApplication, QScrollBar, QGridLayout)
from PySide6.QtCore import QThreadPool, Qt, QTimer, QRunnable, QObject, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QTextCharFormat, QTextCursor

APP_VERSION = "v1.6.1"

def parse_version(ver_str: str) -> tuple:
    cleaned = re.sub(r'[^0-9.]', '', ver_str)
    return tuple(map(int, cleaned.split('.'))) if cleaned else (0,)

class UpdateSignals(QObject):
    update_available = Signal(str, str)
    no_update = Signal(bool)
    error = Signal(str)

class UpdateWorker(QRunnable):
    def __init__(self, current_version: str, manual: bool = False):
        super().__init__()
        self.current_version = current_version
        self.manual = manual
        self.signals = UpdateSignals()

    def run(self):
        url = "https://api.github.com/repos/kuy124/YoutubeBatchDownloader/releases/latest"
        req = urllib.request.Request(url, headers={'User-Agent': 'YouTubeBatchDownloader-App'})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    tag_name = data.get('tag_name', '')
                    html_url = data.get('html_url', 'https://github.com/kuy124/YoutubeBatchDownloader/releases')
                    
                    if parse_version(tag_name) > parse_version(self.current_version):
                        self.signals.update_available.emit(tag_name, html_url)
                    else:
                        self.signals.no_update.emit(self.manual)
        except Exception as e:
            if self.manual:
                self.signals.error.emit(str(e))

from .settings import Settings
from .downloader import DownloadWorker, MetadataWorker, TitlePreviewWorker
from .logger import log
from .utils import get_icon_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Batch Downloader")
        self.resize(950, 640)
        self.settings = Settings()
        
        # Load and set Window Icon
        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(self.settings.get("threads"))
        
        self.active_workers = {}
        self.row_mapping = {}
        self.task_data = {}        # Tracks URL and configurations for manual retry loops
        self.completed_paths = {}  # Caches output filepaths for instant double-click playback
        self.active_metrics = {}    # Tracks realtime speed, bytes left, and ETA per worker

        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.fetch_title_previews)

        self.setup_ui()
        self.apply_settings()

        # Connect the OS clipboard monitor signal
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)

        # Trigger silent update check on startup
        QTimer.singleShot(1000, lambda: self.check_for_updates(manual=False))

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

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # ---------------- URL Input Search & Title Preview Area ----------------
        input_search_layout = QHBoxLayout()
        input_search_layout.addWidget(QLabel("Search Input:"))
        self.search_url_input = QLineEdit()
        self.search_url_input.setPlaceholderText("Filter pasted URLs or titles...")
        self.search_url_input.textChanged.connect(self.search_input_textboxes)
        input_search_layout.addWidget(self.search_url_input)

        self.lbl_url_matches = QLabel("")
        input_search_layout.addWidget(self.lbl_url_matches)
        layout.addLayout(input_search_layout)

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
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...")
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

        # --- Synchronize Shared Vertical Scrollbar ---
        def sync_v_scrollbar_range(min_val, max_val):
            self.sync_v_scrollbar.setRange(min_val, max_val)
            self.sync_v_scrollbar.setPageStep(self.url_input.verticalScrollBar().pageStep())
            
        self.url_input.verticalScrollBar().rangeChanged.connect(sync_v_scrollbar_range)
        self.sync_v_scrollbar.valueChanged.connect(self.url_input.verticalScrollBar().setValue)
        self.sync_v_scrollbar.valueChanged.connect(self.preview_input.verticalScrollBar().setValue)
        self.url_input.verticalScrollBar().valueChanged.connect(self.sync_v_scrollbar.setValue)
        self.preview_input.verticalScrollBar().valueChanged.connect(self.sync_v_scrollbar.setValue)
        
        # --- Synchronize URL Horizontal Scrollbar ---
        def sync_url_h_scrollbar_range(min_val, max_val):
            self.url_h_scrollbar.setRange(min_val, max_val)
            self.url_h_scrollbar.setPageStep(self.url_input.horizontalScrollBar().pageStep())
            
        self.url_input.horizontalScrollBar().rangeChanged.connect(sync_url_h_scrollbar_range)
        self.url_h_scrollbar.valueChanged.connect(self.url_input.horizontalScrollBar().setValue)
        self.url_input.horizontalScrollBar().valueChanged.connect(self.url_h_scrollbar.setValue)
        
        # --- Synchronize Preview Horizontal Scrollbar ---
        def sync_preview_h_scrollbar_range(min_val, max_val):
            self.preview_h_scrollbar.setRange(min_val, max_val)
            self.preview_h_scrollbar.setPageStep(self.preview_input.horizontalScrollBar().pageStep())
            
        self.preview_input.horizontalScrollBar().rangeChanged.connect(sync_preview_h_scrollbar_range)
        self.preview_h_scrollbar.valueChanged.connect(self.preview_input.horizontalScrollBar().setValue)
        self.preview_input.horizontalScrollBar().valueChanged.connect(self.preview_h_scrollbar.setValue)

        # --- Force Initial State Synchronization ---
        # Prevents the scrollbars from starting with a default 0-99 range (tiny thumb)
        sync_v_scrollbar_range(self.url_input.verticalScrollBar().minimum(), self.url_input.verticalScrollBar().maximum())
        sync_url_h_scrollbar_range(self.url_input.horizontalScrollBar().minimum(), self.url_input.horizontalScrollBar().maximum())
        sync_preview_h_scrollbar_range(self.preview_input.horizontalScrollBar().minimum(), self.preview_input.horizontalScrollBar().maximum())

        url_btn_layout = QHBoxLayout()
        btn_paste = QPushButton("Paste Clipboard")
        btn_paste.clicked.connect(self.url_input.paste)
        btn_clear = QPushButton("Clear URLs")
        btn_clear.clicked.connect(self.url_input.clear)
        url_btn_layout.addWidget(btn_paste)
        url_btn_layout.addWidget(btn_clear)
        url_btn_layout.addStretch()
        layout.addLayout(url_btn_layout)

        # ---------------- Options Area ----------------
        options_layout = QHBoxLayout()
        
        # Formats
        opt_v_layout = QVBoxLayout()
        opt_v_layout.addWidget(QLabel("Format:"))
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
        opt_v_layout.addWidget(self.combo_format)
        options_layout.addLayout(opt_v_layout)

        # Quality
        opt_q_layout = QVBoxLayout()
        opt_q_layout.addWidget(QLabel("Max Quality:"))
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["Best", "1080p", "720p", "480p"])
        opt_q_layout.addWidget(self.combo_quality)
        options_layout.addLayout(opt_q_layout)

        # Checkboxes Settings Block
        check_layout = QVBoxLayout()
        self.chk_auto_clear = QCheckBox("Automatically clear completed downloads (after 2 seconds)")
        self.chk_monitor_clip = QCheckBox("Auto-Add links from Clipboard (Real-time Monitor)")
        check_layout.addWidget(self.chk_auto_clear)
        check_layout.addWidget(self.chk_monitor_clip)
        options_layout.addLayout(check_layout)
        
        layout.addLayout(options_layout)

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

        # ---------------- Action Buttons ----------------
        action_layout = QHBoxLayout()
        btn_download = QPushButton("Add to Queue and Download")
        btn_download.setMinimumHeight(38)
        btn_download.setStyleSheet("background-color: #1976d2; color: white; font-weight: bold; border-radius: 3px;")
        btn_download.clicked.connect(self.start_downloads)
        action_layout.addWidget(btn_download)

        btn_cancel_all = QPushButton("Cancel All")
        btn_cancel_all.setMinimumHeight(38)
        btn_cancel_all.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; border-radius: 3px;")
        btn_cancel_all.clicked.connect(self.cancel_all_tasks)
        action_layout.addWidget(btn_cancel_all)

        btn_clear_completed = QPushButton("Clear Completed")
        btn_clear_completed.setMinimumHeight(38)
        btn_clear_completed.clicked.connect(self.clear_completed_tasks)
        action_layout.addWidget(btn_clear_completed)

        btn_check_update = QPushButton("Check Updates")
        btn_check_update.setMinimumHeight(38)
        btn_check_update.clicked.connect(lambda: self.check_for_updates(manual=True))
        action_layout.addWidget(btn_check_update)
        
        layout.addLayout(action_layout)

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
        layout.addWidget(self.table)

        # ---------------- Universal Loading Bar ----------------
        self.global_progress = QProgressBar()
        self.global_progress.setValue(0)
        self.global_progress.setFixedHeight(20)
        self.global_progress.setFormat("No active tasks")
        self.global_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.global_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                background-color: #f5f5f5;
                color: #1a237e; /* Royal Indigo Loading Text Color */
            }
            QProgressBar::chunk {
                background-color: #0288d1;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.global_progress)

        # ---------------- Bottom Status Bar ----------------
        self.statusBar = self.statusBar()
        self.update_status_summary()

    def apply_settings(self):
        self.entry_path.setText(self.settings.get("download_path"))
        self.combo_format.setCurrentText(self.settings.get("format"))
        self.combo_quality.setCurrentText(self.settings.get("quality"))
        self.chk_auto_clear.setChecked(self.settings.get("auto_clear"))
        self.chk_monitor_clip.setChecked(self.settings.get("monitor_clipboard"))

    def save_current_settings(self):
        self.settings.set("download_path", self.entry_path.text())
        self.settings.set("format", self.combo_format.currentText())
        self.settings.set("quality", self.combo_quality.currentText())
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
        """Appends copied YouTube links directly to textbox if monitor is checked."""
        if not self.chk_monitor_clip.isChecked():
            return
        text = self.clipboard.text().strip()
        if "youtube.com/" in text or "youtu.be/" in text:
            current_text = self.url_input.toPlainText()
            # Ensure we do not add duplicate spam links already sitting in the box
            if text not in current_text:
                if current_text:
                    self.url_input.append(text)
                else:
                    self.url_input.setPlainText(text)
                log.info(f"Clipboard Monitor dynamically added link: {text}")

    def on_table_double_clicked(self, row, column):
        """Allows double-clicking any complete row to play the downloaded file."""
        task_id = None
        for tid, r_idx in list(self.row_mapping.items()):
            if r_idx == row:
                task_id = tid
                break
        
        if task_id:
            file_path = self.completed_paths.get(task_id)
            if file_path:
                self.open_file(file_path)

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
        self.preview_timer.start(600)

    def filter_table(self, query: str):
        """Filters queue table rows dynamically matching title or URL."""
        query = query.strip().lower()
        for row in range(self.table.rowCount()):
            task_id = None
            for tid, r_idx in self.row_mapping.items():
                if r_idx == row:
                    task_id = tid
                    break
            
            title = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            url = self.task_data.get(task_id, {}).get('url', '') if task_id else ""
            
            if not query or query in title.lower() or query in url.lower():
                self.table.setRowHidden(row, False)
            else:
                self.table.setRowHidden(row, True)

    def fetch_title_previews(self):
        raw_lines = self.url_input.toPlainText().split('\n')
        if not any(line.strip() for line in raw_lines):
            self.preview_input.clear()
            return

        worker = TitlePreviewWorker(raw_lines)
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
        active = len(self.active_workers)
        
        completed = 0
        failed = 0
        queued = 0
        for row in range(total):
            item = self.table.item(row, 1)
            if item:
                status = item.text()
                if status == "Complete":
                    completed += 1
                elif "Failed" in status:
                    failed += 1
                elif status in ["Waiting...", "Analyzing Link..."]:
                    queued += 1

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

            # Estimate API handshake + FFmpeg metadata extraction overhead (~2.5s per video)
            EXTRACTION_OVERHEAD_PER_TASK = 2.5
            total_extraction_time = (active + queued) * EXTRACTION_OVERHEAD_PER_TASK
            
            total_estimated_seconds = int(download_time_sec + total_extraction_time)
            
            if total_estimated_seconds > 0:
                mins, secs = divmod(total_estimated_seconds, 60)
                hours, mins = divmod(mins, 60)
                if hours > 0:
                    eta_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
                else:
                    eta_str = f"{mins:02d}:{secs:02d}"

        self.statusBar.showMessage(f"Total Tasks: {total}  |  Active: {active}  |  Completed: {completed}  |  Failed: {failed}  |  Total ETA: {eta_str}")

    def start_downloads(self):
        raw_url_lines = self.url_input.toPlainText().split('\n')
        raw_preview_lines = self.preview_input.toPlainText().split('\n')
        
        urls = []
        previews = []
        for i, line in enumerate(raw_url_lines):
            u = line.strip()
            if u:
                urls.append(u)
                p = raw_preview_lines[i].strip() if i < len(raw_preview_lines) else ""
                if p and p not in ["Failed to load title", "Invalid URL"]:
                    previews.append(p)
                else:
                    previews.append(None)

        if not urls:
            QMessageBox.warning(self, "Input Error", "Please provide at least one valid URL.")
            return

        os.makedirs(self.entry_path.text(), exist_ok=True)
        self.save_current_settings()

        options = {
            'download_path': self.entry_path.text(),
            'format': self.combo_format.currentText(),
            'quality': self.combo_quality.currentText()
        }

        for idx, url in enumerate(urls):
            cached_title = previews[idx]
            self.add_task(url, options, title=cached_title)

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
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(lambda _, tid=task_id: self.cancel_task(tid))
        
        self.table.setItem(row_idx, 0, title_item)
        self.table.setItem(row_idx, 1, status_item)
        self.table.setCellWidget(row_idx, 2, progress_bar)
        self.table.setItem(row_idx, 3, speed_item)
        self.table.setItem(row_idx, 4, eta_item)
        self.table.setCellWidget(row_idx, 5, btn_cancel)
        
        self.row_mapping[task_id] = row_idx

        if title:
            # Instant start: use pre-fetched title preview directly
            pre_data = {'title': title}
            self.task_data[task_id]['pre_data'] = pre_data
            worker = DownloadWorker(task_id, url, options, pre_data)
            worker.signals.progress.connect(self.update_progress)
            worker.signals.finished.connect(self.task_finished)
            worker.signals.error.connect(self.task_error)
            
            self.active_workers[task_id] = worker
            self.threadpool.start(worker)
        else:
            # Step 1: Pre-extract metadata first across queue
            meta_worker = MetadataWorker(task_id, url)
            meta_worker.signals.finished.connect(self.on_metadata_extracted)
            meta_worker.signals.error.connect(lambda tid, err: self.task_error(tid, err))
            self.threadpool.start(meta_worker)

        self.filter_table(self.search_input.text())
        self.update_status_summary()
        self.update_global_progress()

    def on_metadata_extracted(self, task_id, pre_data):
        """Called when a task's metadata pre-extraction phase completes."""
        row = self.row_mapping.get(task_id)
        if row is not None:
            self.table.item(row, 0).setText(pre_data['title'])
            self.table.item(row, 1).setText("Waiting in Queue...")
            self.table.item(row, 1).setForeground(QBrush(QColor("#2e7d32")))
            
            ext_time = pre_data.get('extraction_time', 0.0)
            self.table.item(row, 4).setText(f"{ext_time:.1f}s extract")

        if task_id in self.task_data:
            self.task_data[task_id]['pre_data'] = pre_data
            url = self.task_data[task_id]['url']
            options = self.task_data[task_id]['options']

            # Step 2: Initialize and launch actual download worker
            worker = DownloadWorker(task_id, url, options, pre_data)
            worker.signals.progress.connect(self.update_progress)
            worker.signals.finished.connect(self.task_finished)
            worker.signals.error.connect(self.task_error)
            
            self.active_workers[task_id] = worker
            self.threadpool.start(worker)
            self.update_status_summary()

    def cancel_task(self, task_id):
        worker = self.active_workers.get(task_id)
        if worker:
            worker.is_cancelled = True
            
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
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(lambda _, tid=task_id: self.cancel_task(tid))
        self.table.setCellWidget(row, 5, btn_cancel)
        
        # Build and queue the new worker instance
        worker = DownloadWorker(task_id, url, options)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.task_finished)
        worker.signals.error.connect(self.task_error)
        
        self.active_workers[task_id] = worker
        self.threadpool.start(worker)
        self.update_status_summary()
        self.update_global_progress()

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
                
        self.update_status_summary()
        self.update_global_progress()

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
                        self.update_global_progress()
                    except ValueError:
                        pass
            
        if 'speed' in data:
            self.table.item(row, 3).setText(data['speed'])
        if 'eta' in data:
            self.table.item(row, 4).setText(data['eta'])
        
        if not data.get('is_postprocessing'):
            self.active_metrics[task_id] = {
                'speed_bytes': data.get('speed_bytes', 0),
                'downloaded_bytes': data.get('downloaded_bytes', 0),
                'total_bytes': data.get('total_bytes', 0),
                'eta_seconds': data.get('eta_seconds', 0)
            }
        self.update_status_summary()

    def task_finished(self, task_id, file_path):
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
        self.table.item(row, 4).setText("-")
        
        # Cache file path for double-click playback functionality
        self.completed_paths[task_id] = file_path
        
        # Replace actions column button with instant play button
        btn_open = QPushButton("Open File")
        btn_open.setStyleSheet("background-color: #0288d1; color: white; font-weight: bold;")
        btn_open.clicked.connect(lambda _, fp=file_path: self.open_file(fp))
        self.table.setCellWidget(row, 5, btn_open)
        
        self.update_global_progress()  # Recalculate global average on success

        # Automatically clear completed row after 2 seconds if checked
        if self.chk_auto_clear.isChecked():
            QTimer.singleShot(2000, lambda: self.remove_task_row(task_id))
                
        self._cleanup_worker(task_id)
        self.update_status_summary()
        
        # Play system sound notification if all tasks in active queue are complete
        if len(self.active_workers) == 0:
            self.play_finished_sound()
            
        log.info(f"Task {task_id} completed successfully. Local path: {file_path}")

    def task_error(self, task_id, error_msg):
        row = self.row_mapping.get(task_id)
        if row is None: return  # Safe exit if row was already removed/cancelled

        self.table.item(row, 1).setText(error_msg)
        self.table.item(row, 1).setForeground(QBrush(QColor("#d32f2f")))  # Soft red for error text
        
        # Replace the Cancel button with a highly visible "Retry" button
        btn_retry = QPushButton("Retry")
        btn_retry.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        btn_retry.clicked.connect(lambda _, tid=task_id: self.retry_task(tid))
        self.table.setCellWidget(row, 5, btn_retry)
            
        self.update_global_progress()  # Recalculate global average on failure
        self._cleanup_worker(task_id)
        self.update_status_summary()
        
        # Play system sound notification if all active processing is finished (even on fail)
        if len(self.active_workers) == 0:
            self.play_finished_sound()

    def _cleanup_worker(self, task_id):
        if task_id in self.active_workers:
            del self.active_workers[task_id]