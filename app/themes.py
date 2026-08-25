"""Theme definitions: tokenized QSS + matching QPalette for full-surface coverage.

The palette matters as much as the stylesheet: table viewports, status bar,
dropdown popups and message boxes fall back to it wherever QSS does not reach.
"""
from string import Template

from PySide6.QtGui import QColor, QPalette

THEMES = ["Dark", "Light"]

_DARK = {
    "bg": "#0b0f19",
    "surface": "#141b2d",
    "surface_hover": "#1d2739",
    "surface_pressed": "#243149",
    "alt": "#101828",
    "border": "#2a3650",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "primary": "#0284c7",
    "primary_hover": "#0ea5e9",
    "primary_pressed": "#0369a1",
    "danger": "#f87171",
    "danger_border": "#7f2a2a",
    "danger_bg": "#2a1416",
    "focus": "#38bdf8",
    "grid": "#1c2540",
    "header_bg": "#10182b",
    "selection_bg": "#14395e",
    "scrollbar": "#334155",
    "progress_text": "#e2e8f0",
    "progress_chunk": "#0288d1",
}

_LIGHT = {
    "bg": "#f5f7fa",
    "surface": "#ffffff",
    "surface_hover": "#eceff1",
    "surface_pressed": "#cfd8dc",
    "alt": "#f0f3f7",
    "border": "#cfd8dc",
    "text": "#37474f",
    "muted": "#607d8b",
    "primary": "#1976d2",
    "primary_hover": "#1565c0",
    "primary_pressed": "#0d47a1",
    "danger": "#c62828",
    "danger_border": "#ef9a9a",
    "danger_bg": "#ffebee",
    "focus": "#64b5f6",
    "grid": "#eceff1",
    "header_bg": "#f5f5f5",
    "selection_bg": "#e3f2fd",
    "scrollbar": "#b0bec5",
    "progress_text": "#1a237e",
    "progress_chunk": "#0288d1",
}

_QSS_TEMPLATE = Template("""
MainWindow, QDialog {
    background-color: ${bg};
}
QLabel { color: ${text}; }
QStatusBar { background-color: ${bg}; color: ${muted}; }
QToolTip {
    background-color: ${surface}; color: ${text};
    border: 1px solid ${border}; padding: 3px;
}

QPushButton {
    background-color: ${surface};
    border: 1px solid ${border};
    border-radius: 4px;
    padding: 7px 16px;
    color: ${text};
    font-weight: 600;
}
QPushButton:hover { background-color: ${surface_hover}; }
QPushButton:pressed { background-color: ${surface_pressed}; }
QPushButton:focus { border-color: ${focus}; }

QPushButton[variant="primary"] {
    background-color: ${primary}; color: #ffffff;
    border: 1px solid ${primary}; padding: 9px 20px; font-weight: 700;
}
QPushButton[variant="primary"]:hover { background-color: ${primary_hover}; }
QPushButton[variant="primary"]:pressed { background-color: ${primary_pressed}; }

QPushButton[variant="danger"] {
    background-color: ${surface}; color: ${danger};
    border: 1px solid ${danger_border}; padding: 9px 16px; font-weight: 700;
}
QPushButton[variant="danger"]:hover { background-color: ${danger_bg}; }

QPushButton[variant="chip"] {
    background-color: ${surface}; color: ${text};
    border: 1px solid ${border}; padding: 9px 16px; font-weight: 700;
}

QPushButton[variant="cell"] {
    padding: 3px 12px; font-weight: 500; border-radius: 3px;
}
QPushButton[variant="cell-primary"] {
    background-color: ${progress_chunk}; color: #ffffff;
    border: 1px solid ${progress_chunk}; padding: 4px 14px; font-weight: 600; border-radius: 3px;
}
QPushButton[variant="cell-primary"]:hover { background-color: ${primary_hover}; }
QPushButton[variant="cell-danger"] {
    background-color: ${surface}; color: ${danger};
    border: 1px solid ${danger_border}; padding: 4px 14px; font-weight: 600; border-radius: 3px;
}
QPushButton[variant="cell-danger"]:hover { background-color: ${danger_bg}; }

QLineEdit, QComboBox {
    background-color: ${surface};
    border: 1px solid ${border};
    border-radius: 4px;
    padding: 5px 8px;
    color: ${text};
    selection-background-color: ${selection_bg};
    selection-color: ${text};
}
QLineEdit:focus, QComboBox:focus { border-color: ${focus}; }

QComboBox QAbstractItemView {
    background-color: ${surface};
    color: ${text};
    border: 1px solid ${border};
    selection-background-color: ${surface_hover};
    selection-color: ${text};
}

QTableWidget {
    background-color: ${surface};
    alternate-background-color: ${alt};
    gridline-color: ${grid};
    color: ${text};
    selection-background-color: ${selection_bg};
    selection-color: ${text};
}
QHeaderView::section {
    background-color: ${header_bg};
    border: none;
    border-bottom: 1px solid ${border};
    padding: 6px 8px;
    color: ${muted};
    font-weight: 600;
}

QCheckBox { color: ${text}; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid ${border}; border-radius: 3px;
    background-color: ${surface};
}
QCheckBox::indicator:hover { border-color: ${focus}; }
QCheckBox::indicator:checked { background-color: ${primary}; border-color: ${primary}; }

#globalProgress {
    border: 1px solid ${border};
    border-radius: 4px;
    text-align: center;
    font-weight: bold;
    background-color: ${surface};
    color: ${progress_text};
}
#globalProgress::chunk { background-color: ${progress_chunk}; border-radius: 3px; }

QMenu {
    background-color: ${surface};
    color: ${text};
    border: 1px solid ${border};
}
QMenu::item { padding: 5px 22px; }
QMenu::item:selected { background-color: ${surface_hover}; }
QMenu::separator { height: 1px; background-color: ${border}; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: ${scrollbar}; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: ${muted}; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: ${scrollbar}; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: ${muted}; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
""")


def _build_palette(t: dict) -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(t["bg"]))
    pal.setColor(QPalette.WindowText, QColor(t["text"]))
    pal.setColor(QPalette.Base, QColor(t["surface"]))
    pal.setColor(QPalette.AlternateBase, QColor(t["alt"]))
    pal.setColor(QPalette.Text, QColor(t["text"]))
    pal.setColor(QPalette.Button, QColor(t["surface"]))
    pal.setColor(QPalette.ButtonText, QColor(t["text"]))
    pal.setColor(QPalette.Highlight, QColor(t["primary"]))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor(t["surface"]))
    pal.setColor(QPalette.ToolTipText, QColor(t["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(t["muted"]))
    return pal


def build_theme(name: str):
    """Returns (stylesheet, palette) for 'Dark' or 'Light' (case-insensitive).

    Unknown names fall back to Dark so a corrupted settings value can never
    produce an unreadable half-styled window.
    """
    if isinstance(name, str) and name.strip().lower() == "light":
        tokens = _LIGHT
    else:
        tokens = _DARK
    return _QSS_TEMPLATE.safe_substitute(tokens), _build_palette(tokens)
