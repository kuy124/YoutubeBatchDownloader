import os
import uuid
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QTextEdit, QPushButton, QComboBox, QCheckBox, 
                               QLineEdit, QFileDialog, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QProgressBar, QMessageBox)
from PySide6.QtCore import QThreadPool, Qt

from .settings import Settings
from .downloader import DownloadWorker
from .logger import log

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Batch Downloader")
        self.resize(950, 600)
        self.settings = Settings()
        
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(self.settings.get("threads"))
        
        self.active_workers = {}
        self.row_mapping = {}

        self.setup_ui()
        self.apply_settings()

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

        # Checkboxes (Strictly Single Video focus)
        check_layout = QVBoxLayout()
        self.chk_merge = QCheckBox("Merge Video/Audio (Needs FFmpeg)")
        self.chk_thumb = QCheckBox("Embed Thumbnail (Needs FFmpeg)")
        self.chk_meta = QCheckBox("Embed Metadata (Needs FFmpeg)")
        check_layout.addWidget(self.chk_merge)
        check_layout.addWidget(self.chk_thumb)
        check_layout.addWidget(self.chk_meta)
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
        
        layout.addLayout(path_layout)

        # ---------------- Action Buttons ----------------
        action_layout = QHBoxLayout()
        btn_download = QPushButton("▶ Add to Queue and Download")
        btn_download.setMinimumHeight(40)
        btn_download.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        btn_download.clicked.connect(self.start_downloads)
        action_layout.addWidget(btn_download)
        layout.addLayout(action_layout)

        # ---------------- Queue Table ----------------
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Video Title", "Status", "Progress", "Speed", "ETA", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def apply_settings(self):
        self.entry_path.setText(self.settings.get("download_path"))
        self.combo_format.setCurrentText(self.settings.get("format"))
        self.combo_quality.setCurrentText(self.settings.get("quality"))
        self.chk_merge.setChecked(self.settings.get("merge_auto"))
        self.chk_thumb.setChecked(self.settings.get("embed_thumbnail"))
        self.chk_meta.setChecked(self.settings.get("embed_metadata"))

    def save_current_settings(self):
        self.settings.set("download_path", self.entry_path.text())
        self.settings.set("format", self.combo_format.currentText())
        self.settings.set("quality", self.combo_quality.currentText())
        self.settings.set("merge_auto", self.chk_merge.isChecked())
        self.settings.set("embed_thumbnail", self.chk_thumb.isChecked())
        self.settings.set("embed_metadata", self.chk_meta.isChecked())

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.entry_path.text())
        if folder:
            self.entry_path.setText(folder)
            self.save_current_settings()

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
            'quality': self.combo_quality.currentText(),
            'merge_auto': self.chk_merge.isChecked(),
            'embed_thumbnail': self.chk_thumb.isChecked(),
            'embed_metadata': self.chk_meta.isChecked()
        }

        for url in urls:
            self.add_task(url, options)
            
        self.url_input.clear()

    def add_task(self, url, options):
        task_id = str(uuid.uuid4())
        
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

    def cancel_task(self, task_id):
        worker = self.active_workers.get(task_id)
        if worker:
            worker.is_cancelled = True
            row = self.row_mapping.get(task_id)
            if row is not None:
                self.table.item(row, 1).setText("Cancelling...")
                self.table.cellWidget(row, 5).setEnabled(False)

    def update_progress(self, task_id, data):
        row = self.row_mapping.get(task_id)
        if row is None: return

        if 'title' in data:
            self.table.item(row, 0).setText(data['title'])
        if 'status_text' in data:
            self.table.item(row, 1).setText(data['status_text'])
            
        if 'percent' in data:
            perc_str = data['percent'].replace('%', '')
            try:
                perc = float(perc_str)
                self.table.cellWidget(row, 2).setValue(int(perc))
            except ValueError:
                pass
            
            self.table.item(row, 1).setText("Downloading")
            self.table.item(row, 3).setText(data.get('speed', '-'))
            self.table.item(row, 4).setText(data.get('eta', '-'))

    def task_finished(self, task_id):
        row = self.row_mapping.get(task_id)
        if row is not None:
            self.table.item(row, 1).setText("Complete")
            self.table.cellWidget(row, 2).setValue(100)
            self.table.item(row, 3).setText("-")
            self.table.item(row, 4).setText("-")
            btn = self.table.cellWidget(row, 5)
            btn.setText("Done")
            btn.setEnabled(False)
        self._cleanup_worker(task_id)
        log.info(f"Task {task_id} completed successfully.")

    def task_error(self, task_id, error_msg):
        row = self.row_mapping.get(task_id)
        if row is not None:
            self.table.item(row, 1).setText(error_msg)
            self.table.item(row, 1).setForeground(Qt.red)
            btn = self.table.cellWidget(row, 5)
            btn.setText("Failed")
            btn.setEnabled(False)
        self._cleanup_worker(task_id)

    def _cleanup_worker(self, task_id):
        if task_id in self.active_workers:
            del self.active_workers[task_id]