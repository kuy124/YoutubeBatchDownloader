"""Theme definitions: tokenized QSS + matching QPalette for full-surface coverage.

The palette matters as much as the stylesheet: table viewports, status bar,
dropdown popups and message boxes fall back to it wherever QSS does not reach.
"""
from string import Template

from PySide6.QtGui import QColor, QPalette

THEMES = [
    "Dark",
    "Light",
    "Midnight Navy",
    "Nord",
    "Dracula",
    "Emerald",
    "Monokai",
    "Rose Pine",
    "Solarized Dark",
    "Solarized Light"
]

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

_MIDNIGHT_NAVY = {
    "bg": "#0a0f1d",
    "surface": "#121a2f",
    "surface_hover": "#1a2642",
    "surface_pressed": "#223156",
    "alt": "#0e1528",
    "border": "#203055",
    "text": "#e2e8f0",
    "muted": "#8fa2c2",
    "primary": "#2563eb",
    "primary_hover": "#3b82f6",
    "primary_pressed": "#1d4ed8",
    "danger": "#ef4444",
    "danger_border": "#7f1d1d",
    "danger_bg": "#2a1215",
    "focus": "#60a5fa",
    "grid": "#172340",
    "header_bg": "#0e162c",
    "selection_bg": "#1e3a8a",
    "scrollbar": "#2d4374",
    "progress_text": "#ffffff",
    "progress_chunk": "#2563eb",
}

_NORD = {
    "bg": "#242933",
    "surface": "#2e3440",
    "surface_hover": "#3b4252",
    "surface_pressed": "#434c5e",
    "alt": "#2b303c",
    "border": "#4c566a",
    "text": "#eceff4",
    "muted": "#d8dee9",
    "primary": "#88c0d0",
    "primary_hover": "#8fbcbb",
    "primary_pressed": "#81a1c1",
    "danger": "#bf616a",
    "danger_border": "#80383f",
    "danger_bg": "#3d262a",
    "focus": "#88c0d0",
    "grid": "#3b4252",
    "header_bg": "#2a2f3a",
    "selection_bg": "#434c5e",
    "scrollbar": "#4c566a",
    "progress_text": "#ffffff",
    "progress_chunk": "#88c0d0",
}

_DRACULA = {
    "bg": "#1e1f29",
    "surface": "#282a36",
    "surface_hover": "#343746",
    "surface_pressed": "#44475a",
    "alt": "#222430",
    "border": "#44475a",
    "text": "#f8f8f2",
    "muted": "#6272a4",
    "primary": "#bd93f9",
    "primary_hover": "#caa6f7",
    "primary_pressed": "#a777ea",
    "danger": "#ff5555",
    "danger_border": "#852222",
    "danger_bg": "#351c20",
    "focus": "#bd93f9",
    "grid": "#343746",
    "header_bg": "#21222c",
    "selection_bg": "#44475a",
    "scrollbar": "#6272a4",
    "progress_text": "#ffffff",
    "progress_chunk": "#bd93f9",
}

_EMERALD = {
    "bg": "#0d1712",
    "surface": "#14231b",
    "surface_hover": "#1b3126",
    "surface_pressed": "#233e31",
    "alt": "#101e17",
    "border": "#274939",
    "text": "#e6f4ed",
    "muted": "#86a997",
    "primary": "#10b981",
    "primary_hover": "#34d399",
    "primary_pressed": "#059669",
    "danger": "#f87171",
    "danger_border": "#7f2a2a",
    "danger_bg": "#2a1416",
    "focus": "#34d399",
    "grid": "#1b3327",
    "header_bg": "#101c15",
    "selection_bg": "#134e38",
    "scrollbar": "#2d5c46",
    "progress_text": "#ffffff",
    "progress_chunk": "#10b981",
}

_MONOKAI = {
    "bg": "#1d1e19",
    "surface": "#272822",
    "surface_hover": "#33342c",
    "surface_pressed": "#3e3f36",
    "alt": "#22231d",
    "border": "#49483e",
    "text": "#f8f8f2",
    "muted": "#75715e",
    "primary": "#fd971f",
    "primary_hover": "#e68a19",
    "primary_pressed": "#cc750d",
    "danger": "#f92672",
    "danger_border": "#8c143e",
    "danger_bg": "#36141e",
    "focus": "#fd971f",
    "grid": "#383830",
    "header_bg": "#20211b",
    "selection_bg": "#49483e",
    "scrollbar": "#75715e",
    "progress_text": "#ffffff",
    "progress_chunk": "#fd971f",
}

_ROSE_PINE = {
    "bg": "#191724",
    "surface": "#1f1d2e",
    "surface_hover": "#26233a",
    "surface_pressed": "#312d47",
    "alt": "#1b1929",
    "border": "#403d52",
    "text": "#e0def4",
    "muted": "#908caa",
    "primary": "#eb6f92",
    "primary_hover": "#f083a2",
    "primary_pressed": "#d9587c",
    "danger": "#eb6f92",
    "danger_border": "#78273d",
    "danger_bg": "#2d1721",
    "focus": "#eb6f92",
    "grid": "#26233a",
    "header_bg": "#181622",
    "selection_bg": "#3e3759",
    "scrollbar": "#524f67",
    "progress_text": "#ffffff",
    "progress_chunk": "#eb6f92",
}

_SOLARIZED_DARK = {
    "bg": "#00212b",
    "surface": "#073642",
    "surface_hover": "#0b4352",
    "surface_pressed": "#0f5263",
    "alt": "#002b36",
    "border": "#1d5361",
    "text": "#93a1a1",
    "muted": "#657b83",
    "primary": "#268bd2",
    "primary_hover": "#389be0",
    "primary_pressed": "#1d76b5",
    "danger": "#dc322f",
    "danger_border": "#7a1715",
    "danger_bg": "#291515",
    "focus": "#2aa198",
    "grid": "#0d4352",
    "header_bg": "#002833",
    "selection_bg": "#0e4f61",
    "scrollbar": "#2d6979",
    "progress_text": "#ffffff",
    "progress_chunk": "#268bd2",
}

_SOLARIZED_LIGHT = {
    "bg": "#fdf6e3",
    "surface": "#eee8d5",
    "surface_hover": "#e4ddc8",
    "surface_pressed": "#d8d0b9",
    "alt": "#f5eed9",
    "border": "#d3cbb7",
    "text": "#586e75",
    "muted": "#839496",
    "primary": "#268bd2",
    "primary_hover": "#1f7cb8",
    "primary_pressed": "#18699d",
    "danger": "#dc322f",
    "danger_border": "#f09a98",
    "danger_bg": "#fce4e4",
    "focus": "#2aa198",
    "grid": "#dfd8c4",
    "header_bg": "#e6dfca",
    "selection_bg": "#d5e4ec",
    "scrollbar": "#b4ab95",
    "progress_text": "#002b36",
    "progress_chunk": "#268bd2",
}

_THEME_MAP = {
    "dark": _DARK,
    "light": _LIGHT,
    "midnight navy": _MIDNIGHT_NAVY,
    "nord": _NORD,
    "dracula": _DRACULA,
    "emerald": _EMERALD,
    "monokai": _MONOKAI,
    "rose pine": _ROSE_PINE,
    "solarized dark": _SOLARIZED_DARK,
    "solarized light": _SOLARIZED_LIGHT,
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
    padding: 5px 12px;
    color: ${text};
    font-weight: 500;
}
QPushButton:hover { background-color: ${surface_hover}; }
QPushButton:pressed { background-color: ${surface_pressed}; }
QPushButton:focus { border-color: ${focus}; }

QPushButton[variant="primary"] {
    background-color: ${primary}; color: #ffffff;
    border: 1px solid ${primary}; padding: 5px 14px; font-weight: 600;
}
QPushButton[variant="primary"]:hover { background-color: ${primary_hover}; }
QPushButton[variant="primary"]:pressed { background-color: ${primary_pressed}; }

QPushButton[variant="danger"] {
    background-color: ${surface}; color: ${danger};
    border: 1px solid ${danger_border}; padding: 5px 12px; font-weight: 600;
}
QPushButton[variant="danger"]:hover { background-color: ${danger_bg}; }

QPushButton[variant="chip"] {
    background-color: ${surface}; color: ${text};
    border: 1px solid ${border}; padding: 5px 12px; font-weight: 500;
}

QPushButton[variant="cell"] {
    padding: 2px 8px; font-weight: 500; border-radius: 3px;
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

QLineEdit, QComboBox, QTextEdit {
    background-color: ${surface};
    border: 1px solid ${border};
    border-radius: 4px;
    padding: 4px 8px;
    color: ${text};
    selection-background-color: ${selection_bg};
    selection-color: ${text};
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border-color: ${focus}; }

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

QScrollArea {
    border: none;
    background: transparent;
}

QGroupBox {
    color: ${text};
    font-weight: 600;
    border: 1px solid ${border};
    border-radius: 6px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}

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
    """Returns (stylesheet, palette) for the specified theme name (case-insensitive).

    Unknown names fall back to Dark so a corrupted settings value can never
    produce an unreadable half-styled window.
    """
    key = str(name).strip().lower() if name else "dark"
    tokens = _THEME_MAP.get(key, _DARK)
    return _QSS_TEMPLATE.safe_substitute(tokens), _build_palette(tokens)
