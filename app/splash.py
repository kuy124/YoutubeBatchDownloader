"""A compact, theme-aware startup status dialog."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .themes import build_theme, theme_tokens


class LoadingSpinner(QWidget):
    """A small activity indicator used only while startup work is in progress."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self._step = 0
        self._color = QColor("#6b7280")
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._advance)

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _advance(self):
        self._step = (self._step + 1) % 10
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        for index in range(10):
            distance = (index - self._step) % 10
            color = QColor(self._color)
            color.setAlpha(55 + int((9 - distance) * 22))
            painter.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap))
            painter.save()
            painter.rotate(index * 36)
            painter.drawLine(0, -8, 0, -4)
            painter.restore()


class LoadingSplash(QDialog):
    """Shows a short, themed progress message while the local engine warms up."""

    def __init__(self, theme_name: str = "Dark"):
        super().__init__(None, Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("YouTube Batch Downloader")
        self.setModal(False)
        self.setObjectName("startupDialog")
        self.setFixedWidth(405)

        content = QWidget(self)
        content.setObjectName("startupContent")
        layout = QHBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(13)

        self._spinner = LoadingSpinner(content)
        layout.addWidget(self._spinner, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title = QLabel("Starting YouTube Batch Downloader")
        title.setObjectName("startupTitle")
        title_font = title.font()
        title_font.setBold(True)
        title.setFont(title_font)
        text_layout.addWidget(title)

        self._message_label = QLabel("Starting...")
        self._message_label.setObjectName("startupMessage")
        self._message_label.setWordWrap(True)
        text_layout.addWidget(self._message_label)
        layout.addLayout(text_layout, 1)

        container = QVBoxLayout(self)
        container.setContentsMargins(0, 0, 0, 0)
        container.addWidget(content)
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name: str):
        """Keeps the startup dialog in step with the user's saved app theme."""
        tokens = theme_tokens(theme_name)
        _, palette = build_theme(theme_name)
        self.setPalette(palette)
        self._spinner.set_color(tokens["primary"])
        self.setStyleSheet(f"""
            QDialog#startupDialog {{ background-color: {tokens['bg']}; }}
            QWidget#startupContent {{ background-color: {tokens['surface']}; }}
            QLabel#startupTitle {{ color: {tokens['text']}; font-size: 11pt; }}
            QLabel#startupMessage {{ color: {tokens['muted']}; }}
        """)

    def set_message(self, text: str):
        self._message_label.setText(text or "Starting...")

    def start(self):
        self._spinner.start()

    def finish(self):
        self._spinner.stop()
        self.close()
