from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont


class LoadingSplash(QWidget):
    """Frameless animated loading card shown instantly while heavy libraries import.

    Appears before the main window so startup never looks frozen, even on slow
    disks or cold PyInstaller extraction.
    """

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(440, 190)

        self._message = "Starting..."
        self._phase = 0.0

        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._tick)

    def _tick(self):
        self._phase = (self._phase + 0.018) % 1.0
        self.update()

    def set_message(self, text: str):
        self._message = text
        self.update()

    def start(self):
        self._anim.start()

    def finish(self):
        self._anim.stop()
        self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        card = QRectF(8, 8, self.width() - 16, self.height() - 16)
        p.setPen(QPen(QColor("#0284c7"), 1.5))
        p.setBrush(QColor("#0b0f19"))
        p.drawRoundedRect(card, 14, 14)

        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor("#38bdf8"))
        p.drawText(card.adjusted(28, 28, -28, 0), Qt.AlignLeft, "YouTube Batch Downloader")

        msg_font = QFont()
        msg_font.setPointSize(10)
        p.setFont(msg_font)
        p.setPen(QColor("#94a3b8"))
        p.drawText(card.adjusted(28, 74, -28, -60),
                   Qt.AlignLeft | Qt.TextWordWrap, self._message)

        # Sweeping indeterminate progress bar
        bar_rect = QRectF(card.left() + 28, card.bottom() - 44, card.width() - 56, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1e293b"))
        p.drawRoundedRect(bar_rect, 3, 3)

        seg_w = bar_rect.width() * 0.28
        travel = bar_rect.width() - seg_w
        seg_x = bar_rect.left() + (travel * self._phase)
        p.setBrush(QColor("#0284c7"))
        p.drawRoundedRect(QRectF(seg_x, bar_rect.top(), seg_w, 6), 3, 3)
