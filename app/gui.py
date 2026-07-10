import os
import uuid
import winsound  # Standard library module to trigger clean system chimes
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QTextEdit, QPushButton, QComboBox, QCheckBox, 
                               QLineEdit, QFileDialog, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QProgressBar, QMessageBox, QApplication)
from PySide6.QtCore import QThreadPool, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon

from .settings import Settings
from .downloader import DownloadWorker
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

        self.setup_ui()
        self.apply_settings()

        # Connect the OS clipboard monitor signal
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # ---------------- URL Input Area ----------------
        layout.addWidget(QLabel("<b>URLs (One per line):</b>"))
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...")
        layout.addWidget(self.url_input)

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
        self.combo_format.addItems(["Best Quality", "MP4 Video", "MP3 Audio"])
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

        btn_open_folder = QPushButton("📁 Open Folder")
        btn_open_folder.clicked.connect(self.open_downloads_folder)
        path_layout.addWidget(btn_open_folder)
        
        layout.addLayout(path_layout)

        # ---------------- Action Buttons ----------------
        action_layout = QHBoxLayout()
        btn_download = QPushButton("▶ Add to Queue and Download")
        btn_download.setMinimumHeight(40)
        btn_download.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        btn_download.clicked.connect(self.start_downloads)
        action_layout.addWidget(btn_download)

        btn_clear_completed = QPushButton("🧹 Clear Completed")
        btn_clear_completed.setMinimumHeight(40)
        btn_clear_completed.clicked.connect(self.clear_completed_tasks)
        action_layout.addWidget(btn_clear_completed)
        
        layout.addLayout(action_layout)

        # ---------------- Queue Table ----------------
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

    def update_status_summary(self):
        """Updates the bottom application status bar metrics."""
        total = self.table.rowCount()
        active = len(self.active_workers)
        
        completed = 0
        failed = 0
        for row in range(total):
            item = self.table.item(row, 1)
            if item:
                if item.text() == "Complete":
                    completed += 1
                elif "Failed" in item.text():
                    failed += 1
                    
        self.statusBar.showMessage(f"Total Tasks: {total}  |  Active: {active}  |  Completed: {completed}  |  Failed: {failed}")

    def start_downloads(self):
        urls = [url.strip() for url in self.url_input.toPlainText().split('\n') if url.strip()]
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

        for url in urls:
            self.add_task(url, options)

    def add_task(self, url, options):
        task_id = str(uuid.uuid4())
        
        self.task_data[task_id] = {
            'url': url,
            'options': options
        }

        # Add Row to UI Table
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        
        title_item = QTableWidgetItem(f"Queueing: {url}")
        status_item = QTableWidgetItem("Waiting...")
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

        # Initialize and start background worker
        worker = DownloadWorker(task_id, url, options)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.task_finished)
        worker.signals.error.connect(self.task_error)
        
        self.active_workers[task_id] = worker
        self.threadpool.start(worker)
        self.update_status_summary()
        self.update_global_progress()

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
            if "Analyzing" in status:
                self.table.item(row, 1).setForeground(QBrush(QColor("#1565c0")))  # High-visibility Blue
            elif "Retrying" in status:
                self.table.item(row, 1).setForeground(QBrush(QColor("#ef6c00")))  # Warning Orange
            elif "Downloading" in status:
                self.table.item(row, 1).setForeground(QBrush(QColor("#2e7d32")))  # Progress Green
            
        if 'percent' in data:
            perc_str = data['percent'].replace('%', '')
            try:
                perc = float(perc_str)
                self.table.cellWidget(row, 2).setValue(int(perc))
                self.update_global_progress()  # Recalculate global average on every chunk download
            except ValueError:
                pass
            
            self.table.item(row, 1).setText("Downloading")
            self.table.item(row, 1).setForeground(QBrush(QColor("#2e7d32")))  # Green
            self.table.item(row, 3).setText(data.get('speed', '-'))
            self.table.item(row, 4).setText(data.get('eta', '-'))

    def task_finished(self, task_id, file_path):
        row = self.row_mapping.get(task_id)
        if row is None: return  # Safe exit if row was already removed/cancelled

        self.table.item(row, 1).setText("Complete")
        self.table.item(row, 1).setForeground(QBrush(QColor("#2e7d32")))  # Solid Success Green
        self.table.cellWidget(row, 2).setValue(100)
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