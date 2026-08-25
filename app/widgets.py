from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect, QCheckBox
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QPoint
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QFontMetrics


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


class ThemedCheckBox(QCheckBox):
    """QCheckBox with a custom-painted indicator that reads theme tokens
    live from the active theme.  The tick mark is a crisp white QPainterPath
    over a primary-coloured rounded box — no image assets required."""

    INDICATOR_SIZE = 16
    INDICATOR_GAP = 6
    BOX_RADIUS = 4
    _CHECK_POINTS = [
        (0.21, 0.50), (0.40, 0.70), (0.79, 0.32),
    ]

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._tokens: dict = {}
        self.setCursor(Qt.PointingHandCursor)

    def set_tokens(self, tokens: dict):
        self._tokens = tokens
        self.update()

    def _t(self, key: str, fallback: str = "#888888") -> str:
        return self._tokens.get(key, fallback)

    # -- geometry helpers ---------------------------------------------------

    def _indicator_rect(self) -> "QRect":
        from PySide6.QtCore import QRect
        s = self.INDICATOR_SIZE
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self.text())
        total = self.INDICATOR_GAP + s + self.INDICATOR_GAP + text_w
        x = int((self.width() - total) / 2)
        y = int((self.height() - s) / 2)
        return QRect(x, y, s, s)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event):
        from PySide6.QtGui import QFontMetrics as FM
        from PySide6.QtWidgets import QStyleOptionButton
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        ir = self._indicator_rect()
        hovered = self.underMouse()
        checked = self.isChecked()
        enabled = self.isEnabled()

        if not enabled:
            bg = self._t("surface")
            border = self._t("border")
        elif hovered:
            bg = self._t("surface_hover")
            border = self._t("focus")
        else:
            bg = self._t("surface")
            border = self._t("border")

        # indicator box
        p.setPen(QPen(QColor(border), 1.5))
        p.setBrush(QColor(bg))
        p.drawRoundedRect(ir, self.BOX_RADIUS, self.BOX_RADIUS)

        # checked fill + white tick
        if checked:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self._t("primary")))
            p.drawRoundedRect(ir, self.BOX_RADIUS, self.BOX_RADIUS)
            pen = QPen(QColor("#ffffff"), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            path = QPainterPath()
            s = float(ir.width())
            path.moveTo(ir.x() + s * self._CHECK_POINTS[0][0],
                        ir.y() + s * self._CHECK_POINTS[0][1])
            for pt in self._CHECK_POINTS[1:]:
                path.lineTo(ir.x() + s * pt[0], ir.y() + s * pt[1])
            p.drawPath(path)

        p.end()

        # text — drawn by the native style so elide/alignment stays correct
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        self.style().drawControl(
            self.style().CE_CheckBoxLabel, opt, p, self)
