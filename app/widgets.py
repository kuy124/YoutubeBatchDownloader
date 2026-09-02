from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QPoint
from PySide6.QtGui import QColor, QGuiApplication


class DesktopToast(QWidget):
    """Ultra-clean, minimalist floating card with glowing accents and smooth physics animations."""
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool | 
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Main wrapper layout with padding for shadow
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(16, 16, 16, 16)

        # Sleek Minimalist Container Card
        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background-color: #0b0f19;
                border: 1.5px solid #0284c7;
                border-radius: 12px;
            }
        """)

        # Deep ambient drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 220))
        self.card.setGraphicsEffect(shadow)

        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(12)

        # Text Section
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.lbl_title = QLabel("Link Captured")
        self.lbl_title.setStyleSheet("""
            QLabel {
                color: #38bdf8;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.3px;
                border: none;
                background: transparent;
            }
        """)

        self.lbl_body = QLabel()
        self.lbl_body.setStyleSheet("""
            QLabel {
                color: #94a3b8;
                font-size: 11px;
                font-weight: 500;
                border: none;
                background: transparent;
            }
        """)
        self.lbl_body.setMaximumWidth(280)

        text_layout.addWidget(self.lbl_title)
        text_layout.addWidget(self.lbl_body)
        card_layout.addLayout(text_layout)

        wrapper.addWidget(self.card)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)
        self.anim_group = None

    def show_notification(self, title: str, body: str, duration_ms: int = 2800):
        self.lbl_title.setText(title)
        self.lbl_body.setText(body)
        self.adjustSize()

        screen = QGuiApplication.primaryScreen().availableGeometry()
        target_x = screen.right() - self.width() - 10
        target_y = screen.bottom() - self.height() - 10
        start_y = target_y + 18  # Starts slightly lower for upward slide

        self.move(target_x, start_y)
        self.setWindowOpacity(0.0)
        self.show()

        # Smooth Slide-Up + Fade-In animation
        anim_pos = QPropertyAnimation(self, b"pos")
        anim_pos.setDuration(260)
        anim_pos.setStartValue(QPoint(target_x, start_y))
        anim_pos.setEndValue(QPoint(target_x, target_y))
        anim_pos.setEasingCurve(QEasingCurve.OutCubic)

        anim_op = QPropertyAnimation(self, b"windowOpacity")
        anim_op.setDuration(240)
        anim_op.setStartValue(0.0)
        anim_op.setEndValue(1.0)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(anim_pos)
        self.anim_group.addAnimation(anim_op)
        self.anim_group.start()

        self.timer.start(duration_ms)

    def fade_out(self):
        curr_x = self.x()
        curr_y = self.y()
        end_y = curr_y + 12

        # Smooth Slide-Down + Fade-Out
        anim_pos = QPropertyAnimation(self, b"pos")
        anim_pos.setDuration(220)
        anim_pos.setStartValue(QPoint(curr_x, curr_y))
        anim_pos.setEndValue(QPoint(curr_x, end_y))
        anim_pos.setEasingCurve(QEasingCurve.InCubic)

        anim_op = QPropertyAnimation(self, b"windowOpacity")
        anim_op.setDuration(200)
        anim_op.setStartValue(self.windowOpacity())
        anim_op.setEndValue(0.0)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(anim_pos)
        self.anim_group.addAnimation(anim_op)
        self.anim_group.finished.connect(self.hide)
        self.anim_group.start()

    def mousePressEvent(self, event):
        self.fade_out()
