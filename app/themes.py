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
    "Solarized Light",
    "Obsidian Gold",
    "Oceanic",
    "Forest Canopy",
    "Amber Dusk",
    "Plum Night",
    "Cobalt",
    "Arctic Frost",
    "Paper & Ink",
    "Sandstone",
    "Meadow",
    "Rosewater",
    "Coffee & Cream",
    "High Contrast"
]

THEME_DESCRIPTIONS = {
    "Dark": "Cool charcoal surfaces with a clear blue action accent.",
    "Light": "A bright neutral workspace with a familiar blue accent.",
    "Midnight Navy": "Deep navy surfaces with a crisp blue focus accent.",
    "Nord": "Muted arctic blues with calm, low-glare contrast.",
    "Dracula": "A rich violet night palette with pink focus details.",
    "Emerald": "Deep green surfaces with a fresh mint action color.",
    "Monokai": "Warm editor-inspired charcoal with amber actions.",
    "Rose Pine": "Dusky plum surfaces with soft rose highlights.",
    "Solarized Dark": "Classic blue-green dark surfaces tuned for long sessions.",
    "Solarized Light": "Classic parchment surfaces with blue-green accents.",
    "Obsidian Gold": "Near-black surfaces with a warm brass action accent.",
    "Oceanic": "Deep teal surfaces with a clean sea-glass accent.",
    "Forest Canopy": "Pine-green surfaces with a calm botanical accent.",
    "Amber Dusk": "Warm charcoal surfaces with a copper sunset accent.",
    "Plum Night": "Velvet plum surfaces with a restrained berry accent.",
    "Cobalt": "Ink-blue surfaces with a bright, focused blue accent.",
    "Arctic Frost": "Cool white surfaces with an understated ocean-blue accent.",
    "Paper & Ink": "Soft paper surfaces with an editorial crimson accent.",
    "Sandstone": "Warm mineral surfaces with a grounded terracotta accent.",
    "Meadow": "Gentle green surfaces with a readable leaf accent.",
    "Rosewater": "A soft blush workspace with a confident berry accent.",
    "Coffee & Cream": "Creamy paper surfaces with a dark roast accent.",
    "High Contrast": "Black surfaces, white text, and yellow actions for maximum clarity."
}

_DARK = {
    "bg": "#0b0f19",
    "surface": "#141b2d",
    "surface_hover": "#1d2739",
    "surface_pressed": "#243149",
    "alt": "#101828",
    "border": "#2a3650",
    "control_border": "#5d6d8d",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "primary": "#0369a1",
    "primary_hover": "#075985",
    "primary_pressed": "#0c4a6e",
    "danger": "#f87171",
    "danger_border": "#7f2a2a",
    "danger_bg": "#2a1416",
    "focus": "#38bdf8",
    "grid": "#1c2540",
    "header_bg": "#10182b",
    "selection_bg": "#14395e",
    "scrollbar": "#334155",
    "progress_text": "#e2e8f0",
    "progress_chunk": "#0369a1",
}

_LIGHT = {
    "bg": "#f5f7fa",
    "surface": "#ffffff",
    "surface_hover": "#eceff1",
    "surface_pressed": "#cfd8dc",
    "alt": "#f0f3f7",
    "border": "#cfd8dc",
    "control_border": "#77716a",
    "text": "#37474f",
    "muted": "#536b76",
    "primary": "#1976d2",
    "primary_hover": "#1565c0",
    "primary_pressed": "#0d47a1",
    "danger": "#c62828",
    "danger_border": "#ef9a9a",
    "danger_bg": "#ffebee",
    "focus": "#1565c0",
    "grid": "#eceff1",
    "header_bg": "#f5f5f5",
    "selection_bg": "#e3f2fd",
    "scrollbar": "#b0bec5",
    "progress_text": "#1a237e",
    "progress_chunk": "#1976d2",
}

_MIDNIGHT_NAVY = {
    "bg": "#0a0f1d",
    "surface": "#121a2f",
    "surface_hover": "#1a2642",
    "surface_pressed": "#223156",
    "alt": "#0e1528",
    "border": "#203055",
    "control_border": "#5971a2",
    "text": "#e2e8f0",
    "muted": "#8fa2c2",
    "primary": "#1d4ed8",
    "primary_hover": "#2563eb",
    "primary_pressed": "#1e40af",
    "danger": "#ef4444",
    "danger_border": "#7f1d1d",
    "danger_bg": "#2a1215",
    "focus": "#60a5fa",
    "grid": "#172340",
    "header_bg": "#0e162c",
    "selection_bg": "#1e3a8a",
    "scrollbar": "#2d4374",
    "progress_text": "#ffffff",
    "progress_chunk": "#1d4ed8",
}

_NORD = {
    "bg": "#242933",
    "surface": "#2e3440",
    "surface_hover": "#3b4252",
    "surface_pressed": "#434c5e",
    "alt": "#2b303c",
    "border": "#4c566a",
    "control_border": "#8390a5",
    "text": "#eceff4",
    "muted": "#d8dee9",
    "primary": "#88c0d0",
    "primary_hover": "#8fbcbb",
    "primary_pressed": "#81a1c1",
    "danger": "#e58b91",
    "danger_border": "#80383f",
    "danger_bg": "#3d262a",
    "focus": "#88c0d0",
    "grid": "#3b4252",
    "header_bg": "#2a2f3a",
    "selection_bg": "#434c5e",
    "scrollbar": "#4c566a",
    "progress_text": "#eceff4",
    "progress_chunk": "#88c0d0",
    "primary_text": "#1b2a2f",
}

_DRACULA = {
    "bg": "#1e1f29",
    "surface": "#282a36",
    "surface_hover": "#343746",
    "surface_pressed": "#44475a",
    "alt": "#222430",
    "border": "#44475a",
    "control_border": "#7f7f93",
    "text": "#f8f8f2",
    "muted": "#8b9cc7",
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
    "progress_text": "#f8f8f2",
    "progress_chunk": "#bd93f9",
    "primary_text": "#21152d",
}

_EMERALD = {
    "bg": "#0d1712",
    "surface": "#14231b",
    "surface_hover": "#1b3126",
    "surface_pressed": "#233e31",
    "alt": "#101e17",
    "border": "#274939",
    "control_border": "#5f866e",
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
    "progress_text": "#e6f4ed",
    "progress_chunk": "#10b981",
    "primary_text": "#07180f",
}

_MONOKAI = {
    "bg": "#1d1e19",
    "surface": "#272822",
    "surface_hover": "#33342c",
    "surface_pressed": "#3e3f36",
    "alt": "#22231d",
    "border": "#49483e",
    "control_border": "#817d6a",
    "text": "#f8f8f2",
    "muted": "#9b967d",
    "primary": "#fd971f",
    "primary_hover": "#e68a19",
    "primary_pressed": "#cc750d",
    "danger": "#ff70a4",
    "danger_border": "#8c143e",
    "danger_bg": "#36141e",
    "focus": "#fd971f",
    "grid": "#383830",
    "header_bg": "#20211b",
    "selection_bg": "#49483e",
    "scrollbar": "#75715e",
    "progress_text": "#f8f8f2",
    "progress_chunk": "#fd971f",
    "primary_text": "#1d150b",
}

_ROSE_PINE = {
    "bg": "#191724",
    "surface": "#1f1d2e",
    "surface_hover": "#26233a",
    "surface_pressed": "#312d47",
    "alt": "#1b1929",
    "border": "#403d52",
    "control_border": "#6e6985",
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
    "progress_text": "#e0def4",
    "progress_chunk": "#eb6f92",
    "primary_text": "#261018",
}

_SOLARIZED_DARK = {
    "bg": "#00212b",
    "surface": "#073642",
    "surface_hover": "#0b4352",
    "surface_pressed": "#0f5263",
    "alt": "#002b36",
    "border": "#1d5361",
    "control_border": "#5a9ba6",
    "text": "#93a1a1",
    "muted": "#9bb0b0",
    "primary": "#268bd2",
    "primary_hover": "#389be0",
    "primary_pressed": "#1d76b5",
    "danger": "#ff6b66",
    "danger_border": "#7a1715",
    "danger_bg": "#291515",
    "focus": "#2aa198",
    "grid": "#0d4352",
    "header_bg": "#002833",
    "selection_bg": "#0e4f61",
    "scrollbar": "#2d6979",
    "progress_text": "#ffffff",
    "progress_chunk": "#268bd2",
    "primary_text": "#00161d",
    "selection_text": "#c3d1d0",
}

_SOLARIZED_LIGHT = {
    "bg": "#fdf6e3",
    "surface": "#eee8d5",
    "surface_hover": "#e4ddc8",
    "surface_pressed": "#d8d0b9",
    "alt": "#f5eed9",
    "border": "#d3cbb7",
    "control_border": "#777a6f",
    "text": "#465b62",
    "muted": "#536a6e",
    "primary": "#1f6f9f",
    "primary_hover": "#1a5f8a",
    "primary_pressed": "#154f73",
    "danger": "#b52d30",
    "danger_border": "#f09a98",
    "danger_bg": "#fce4e4",
    "focus": "#147d74",
    "grid": "#dfd8c4",
    "header_bg": "#e6dfca",
    "selection_bg": "#d5e4ec",
    "scrollbar": "#b4ab95",
    "progress_text": "#002b36",
    "progress_chunk": "#1f6f9f",
    "primary_text": "#ffffff",
    "selection_text": "#002b36",
}

_OBSIDIAN_GOLD = {
    "bg": "#12100d",
    "surface": "#1e1a16",
    "surface_hover": "#2a241f",
    "surface_pressed": "#342d26",
    "alt": "#181511",
    "border": "#4a4035",
    "control_border": "#806d58",
    "text": "#f3ece2",
    "muted": "#c2b3a0",
    "primary": "#c8873d",
    "primary_hover": "#d7a261",
    "primary_pressed": "#a76b2b",
    "primary_text": "#1a130d",
    "danger": "#f07c77",
    "danger_border": "#823f3c",
    "danger_bg": "#351b19",
    "focus": "#e8b76d",
    "grid": "#2e261f",
    "header_bg": "#191511",
    "selection_bg": "#563e25",
    "scrollbar": "#665644",
    "progress_text": "#f3ece2",
    "progress_chunk": "#c8873d",
}

_OCEANIC = {
    "bg": "#0b1517",
    "surface": "#10262b",
    "surface_hover": "#17363c",
    "surface_pressed": "#1e454c",
    "alt": "#0d1e22",
    "border": "#2f5961",
    "control_border": "#56858b",
    "text": "#e7f5f4",
    "muted": "#b3ced2",
    "primary": "#43b6b0",
    "primary_hover": "#6acbc3",
    "primary_pressed": "#2d9691",
    "primary_text": "#05272a",
    "danger": "#f1847d",
    "danger_border": "#813c3c",
    "danger_bg": "#351b1e",
    "focus": "#79e0d3",
    "grid": "#1b3b41",
    "header_bg": "#0e2024",
    "selection_bg": "#18515a",
    "scrollbar": "#47727a",
    "progress_text": "#e7f5f4",
    "progress_chunk": "#43b6b0",
}

_FOREST_CANOPY = {
    "bg": "#0e1511",
    "surface": "#15231a",
    "surface_hover": "#1d3225",
    "surface_pressed": "#284131",
    "alt": "#101d16",
    "border": "#365840",
    "control_border": "#5c896a",
    "text": "#edf6ef",
    "muted": "#b2cbb9",
    "primary": "#4bbf88",
    "primary_hover": "#70d8a4",
    "primary_pressed": "#329b6b",
    "primary_text": "#082016",
    "danger": "#f3817a",
    "danger_border": "#7d3b38",
    "danger_bg": "#321a19",
    "focus": "#7ae0ac",
    "grid": "#21402d",
    "header_bg": "#111e16",
    "selection_bg": "#195238",
    "scrollbar": "#4e765c",
    "progress_text": "#edf6ef",
    "progress_chunk": "#4bbf88",
}

_AMBER_DUSK = {
    "bg": "#1a1210",
    "surface": "#291b17",
    "surface_hover": "#3a251e",
    "surface_pressed": "#4b3027",
    "alt": "#211613",
    "border": "#664239",
    "control_border": "#8f6251",
    "text": "#fff0ea",
    "muted": "#d5b1a5",
    "primary": "#e37b52",
    "primary_hover": "#f29a73",
    "primary_pressed": "#ba5837",
    "primary_text": "#2a110a",
    "danger": "#ff8f86",
    "danger_border": "#8b403b",
    "danger_bg": "#411d1b",
    "focus": "#ffb199",
    "grid": "#4a2d24",
    "header_bg": "#241815",
    "selection_bg": "#62362b",
    "scrollbar": "#805546",
    "progress_text": "#fff0ea",
    "progress_chunk": "#e37b52",
}

_PLUM_NIGHT = {
    "bg": "#17121d",
    "surface": "#241a2c",
    "surface_hover": "#32233d",
    "surface_pressed": "#412d4e",
    "alt": "#1d1624",
    "border": "#594567",
    "control_border": "#7e638a",
    "text": "#f6eef8",
    "muted": "#c4afcf",
    "primary": "#d889b2",
    "primary_hover": "#e7a5c6",
    "primary_pressed": "#b96893",
    "primary_text": "#301525",
    "danger": "#ff858e",
    "danger_border": "#853b4b",
    "danger_bg": "#3d1c27",
    "focus": "#f3a8c8",
    "grid": "#382742",
    "header_bg": "#1f1728",
    "selection_bg": "#563d62",
    "scrollbar": "#765f83",
    "progress_text": "#f6eef8",
    "progress_chunk": "#d889b2",
}

_COBALT = {
    "bg": "#0d1322",
    "surface": "#15233b",
    "surface_hover": "#1d3150",
    "surface_pressed": "#274165",
    "alt": "#101b2e",
    "border": "#365681",
    "control_border": "#5d7ba5",
    "text": "#e8f0fc",
    "muted": "#a9b9d4",
    "primary": "#5e9bff",
    "primary_hover": "#83b2ff",
    "primary_pressed": "#3f7cda",
    "primary_text": "#0a1730",
    "danger": "#f47d83",
    "danger_border": "#813a43",
    "danger_bg": "#361b22",
    "focus": "#89b7ff",
    "grid": "#213a60",
    "header_bg": "#101c31",
    "selection_bg": "#234e91",
    "scrollbar": "#4a6b9b",
    "progress_text": "#e8f0fc",
    "progress_chunk": "#5e9bff",
}

_ARCTIC_FROST = {
    "bg": "#f1f6f8",
    "surface": "#ffffff",
    "surface_hover": "#e7eff3",
    "surface_pressed": "#d5e2e8",
    "alt": "#edf3f6",
    "border": "#b4c7d1",
    "control_border": "#6d8894",
    "text": "#1c2e38",
    "muted": "#46606c",
    "primary": "#2b6f8a",
    "primary_hover": "#1f5a73",
    "primary_pressed": "#18465a",
    "primary_text": "#ffffff",
    "danger": "#b52f38",
    "danger_border": "#d48187",
    "danger_bg": "#f8e6e8",
    "focus": "#1b8a9d",
    "grid": "#d9e6eb",
    "header_bg": "#e6eef2",
    "selection_bg": "#d4ebf0",
    "scrollbar": "#83a2b0",
    "progress_text": "#1c2e38",
    "progress_chunk": "#2b6f8a",
}

_PAPER_INK = {
    "bg": "#f8f6f2",
    "surface": "#fffefb",
    "surface_hover": "#f0ede8",
    "surface_pressed": "#e2ded7",
    "alt": "#f4f1eb",
    "border": "#b8b1a6",
    "control_border": "#77716a",
    "text": "#1f2528",
    "muted": "#535b5e",
    "primary": "#a13a40",
    "primary_hover": "#8d2e35",
    "primary_pressed": "#722229",
    "primary_text": "#ffffff",
    "danger": "#b3262f",
    "danger_border": "#d68d91",
    "danger_bg": "#f9e7e8",
    "focus": "#8f2b31",
    "grid": "#e3dfd7",
    "header_bg": "#eeebe5",
    "selection_bg": "#f0d5d5",
    "scrollbar": "#8f8a80",
    "progress_text": "#1f2528",
    "progress_chunk": "#a13a40",
}

_SANDSTONE = {
    "bg": "#f5efe6",
    "surface": "#fff9f0",
    "surface_hover": "#efe2d1",
    "surface_pressed": "#e3d3c0",
    "alt": "#f2e9dd",
    "border": "#c7b5a0",
    "control_border": "#817364",
    "text": "#332a24",
    "muted": "#65554a",
    "primary": "#9c522e",
    "primary_hover": "#844225",
    "primary_pressed": "#69331e",
    "primary_text": "#ffffff",
    "danger": "#b43d35",
    "danger_border": "#d28d85",
    "danger_bg": "#fae6e1",
    "focus": "#b65f37",
    "grid": "#e5d8c9",
    "header_bg": "#ede3d5",
    "selection_bg": "#f0d7c2",
    "scrollbar": "#9b8570",
    "progress_text": "#332a24",
    "progress_chunk": "#9c522e",
}

_MEADOW = {
    "bg": "#f2f7f0",
    "surface": "#fcfffa",
    "surface_hover": "#e6f0e3",
    "surface_pressed": "#d3e3cf",
    "alt": "#edf5ea",
    "border": "#aac0a5",
    "control_border": "#6e826b",
    "text": "#203126",
    "muted": "#4c6250",
    "primary": "#2e6b45",
    "primary_hover": "#245738",
    "primary_pressed": "#1a432a",
    "primary_text": "#ffffff",
    "danger": "#b43b43",
    "danger_border": "#d68c91",
    "danger_bg": "#f9e6e8",
    "focus": "#3c8557",
    "grid": "#dbe9d7",
    "header_bg": "#e6f0e2",
    "selection_bg": "#d9ebdd",
    "scrollbar": "#789876",
    "progress_text": "#203126",
    "progress_chunk": "#2e6b45",
}

_ROSEWATER = {
    "bg": "#fcf3f5",
    "surface": "#fffbfc",
    "surface_hover": "#f5e4e9",
    "surface_pressed": "#eacfd8",
    "alt": "#faedf0",
    "border": "#d6aebb",
    "control_border": "#906f7b",
    "text": "#3c2730",
    "muted": "#6c4c58",
    "primary": "#963d64",
    "primary_hover": "#7d2f52",
    "primary_pressed": "#61233e",
    "primary_text": "#ffffff",
    "danger": "#b9364c",
    "danger_border": "#d88a99",
    "danger_bg": "#fae5ea",
    "focus": "#b64977",
    "grid": "#efdbe1",
    "header_bg": "#f5e8ec",
    "selection_bg": "#f1d2de",
    "scrollbar": "#b68799",
    "progress_text": "#3c2730",
    "progress_chunk": "#963d64",
}

_COFFEE_CREAM = {
    "bg": "#f7f1e8",
    "surface": "#fffdf8",
    "surface_hover": "#efe6d7",
    "surface_pressed": "#e0d4c1",
    "alt": "#f3ece1",
    "border": "#c4b29b",
    "control_border": "#7b6651",
    "text": "#2b241f",
    "muted": "#625448",
    "primary": "#6a4630",
    "primary_hover": "#583824",
    "primary_pressed": "#452b1b",
    "primary_text": "#ffffff",
    "danger": "#ae3c36",
    "danger_border": "#d18d84",
    "danger_bg": "#fae5e0",
    "focus": "#875c40",
    "grid": "#e5d9c7",
    "header_bg": "#f0e8dc",
    "selection_bg": "#eadbc9",
    "scrollbar": "#9e856a",
    "progress_text": "#2b241f",
    "progress_chunk": "#6a4630",
}

_HIGH_CONTRAST = {
    "bg": "#000000",
    "surface": "#111111",
    "surface_hover": "#242424",
    "surface_pressed": "#333333",
    "alt": "#0a0a0a",
    "border": "#a6a6a6",
    "text": "#ffffff",
    "muted": "#e6e6e6",
    "primary": "#ffd400",
    "primary_hover": "#ffe566",
    "primary_pressed": "#d9b500",
    "primary_text": "#000000",
    "danger": "#ff6b6b",
    "danger_border": "#ff9a9a",
    "danger_bg": "#3a0000",
    "focus": "#00ffff",
    "grid": "#333333",
    "header_bg": "#111111",
    "selection_bg": "#0066ff",
    "selection_text": "#ffffff",
    "scrollbar": "#bfbfbf",
    "progress_text": "#ffffff",
    "progress_chunk": "#ffd400",
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
    "obsidian gold": _OBSIDIAN_GOLD,
    "oceanic": _OCEANIC,
    "forest canopy": _FOREST_CANOPY,
    "amber dusk": _AMBER_DUSK,
    "plum night": _PLUM_NIGHT,
    "cobalt": _COBALT,
    "arctic frost": _ARCTIC_FROST,
    "paper & ink": _PAPER_INK,
    "sandstone": _SANDSTONE,
    "meadow": _MEADOW,
    "rosewater": _ROSEWATER,
    "coffee & cream": _COFFEE_CREAM,
    "high contrast": _HIGH_CONTRAST,
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
    border: 1px solid ${control_border};
    border-radius: 4px;
    padding: 5px 12px;
    color: ${text};
    font-weight: 500;
}
QPushButton:hover { background-color: ${surface_hover}; }
QPushButton:pressed { background-color: ${surface_pressed}; }
QPushButton:focus { border-color: ${focus}; }

QPushButton[variant="primary"] {
    background-color: ${primary}; color: ${primary_text};
    border: 1px solid ${primary}; padding: 5px 14px; font-weight: 600;
}
QPushButton[variant="primary"]:hover { background-color: ${primary_hover}; }
QPushButton[variant="primary"]:pressed { background-color: ${primary_pressed}; }

QPushButton[variant="danger"] {
    background-color: ${surface}; color: ${danger};
    border: 1px solid ${danger}; padding: 5px 12px; font-weight: 600;
}
QPushButton[variant="danger"]:hover { background-color: ${danger_bg}; }

QPushButton[variant="chip"] {
    background-color: ${surface}; color: ${text};
    border: 1px solid ${control_border}; padding: 5px 12px; font-weight: 500;
}

QPushButton[variant="cell"] {
    border: 1px solid ${control_border}; padding: 2px 8px; font-weight: 500; border-radius: 3px;
}
QPushButton[variant="cell-primary"] {
    background-color: ${progress_chunk}; color: ${primary_text};
    border: 1px solid ${progress_chunk}; padding: 4px 14px; font-weight: 600; border-radius: 3px;
}
QPushButton[variant="cell-primary"]:hover { background-color: ${primary_hover}; }
QPushButton[variant="cell-danger"] {
    background-color: ${surface}; color: ${danger};
    border: 1px solid ${danger}; padding: 4px 14px; font-weight: 600; border-radius: 3px;
}
QPushButton[variant="cell-danger"]:hover { background-color: ${danger_bg}; }

QLineEdit, QComboBox, QTextEdit {
    background-color: ${surface};
    border: 1px solid ${control_border};
    border-radius: 4px;
    padding: 4px 8px;
    color: ${text};
    selection-background-color: ${selection_bg};
    selection-color: ${selection_text};
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border-color: ${focus}; }

QComboBox QAbstractItemView {
    background-color: ${surface};
    color: ${text};
    border: 1px solid ${control_border};
    selection-background-color: ${surface_hover};
    selection-color: ${selection_text};
}

QTableWidget {
    background-color: ${surface};
    alternate-background-color: ${alt};
    gridline-color: ${grid};
    color: ${text};
    selection-background-color: ${selection_bg};
    selection-color: ${selection_text};
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
    border: 1px solid ${control_border}; border-radius: 3px;
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
    border: 1px solid ${control_border};
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
    border: 1px solid ${control_border};
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
    border: 1px solid ${control_border};
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
    pal.setColor(QPalette.Highlight, QColor(t["selection_bg"]))
    pal.setColor(QPalette.HighlightedText, QColor(t["selection_text"]))
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
    tokens = dict(_THEME_MAP.get(key, _DARK))
    tokens.setdefault("primary_text", "#ffffff")
    tokens.setdefault("selection_text", tokens["text"])
    tokens.setdefault("control_border", tokens["border"])
    return _QSS_TEMPLATE.safe_substitute(tokens), _build_palette(tokens)
