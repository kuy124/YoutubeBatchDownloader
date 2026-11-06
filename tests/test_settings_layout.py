import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.gui import COOKIE_MODES, MainWindow
from tests.gui_env import isolated_settings


class SettingsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_fit_without_sideways_scrolling(self):
        with isolated_settings():
            window = MainWindow()
            try:
                dialog = window.settings_dialog
                dialog.show()
                for point_size in (10, 14):
                    dialog.setFont(QFont("DejaVu Sans", point_size))
                    for width in (520, 640):
                        dialog.resize(width, 500)
                        for mode in COOKIE_MODES:
                            with self.subTest(font=point_size, width=width, cookies=mode):
                                window.combo_cookies_mode.setCurrentText(mode)
                                for _ in range(5):
                                    self.app.processEvents()
                                scroll = window.settings_scroll
                                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                                self.assertLessEqual(scroll.widget().width(), scroll.viewport().width())
                                self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
                checkbox = window.chk_aria2
                scroll.ensureWidgetVisible(checkbox)
                self.app.processEvents()
                label = checkbox.findChild(QLabel)
                self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
                checked = checkbox.isChecked()
                QTest.mouseClick(label, Qt.LeftButton)
                self.assertEqual(checkbox.isChecked(), not checked)
                QTest.keyClick(checkbox, Qt.Key_Space)
                self.assertEqual(checkbox.isChecked(), checked)
                self.assertEqual(checkbox.accessibleName(), label.text())
            finally:
                dialog.hide()
                window.tray_icon.hide()
                window.deleteLater()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
