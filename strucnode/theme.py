"""Colors, sizes and ttk styles shared by every view."""

from __future__ import annotations

BG = "#1c1b19"
SURFACE = "#201f1d"
SURFACE2 = "#2d2c2a"
BORDER = "#393836"
TEXT = "#cdccca"
MUTED = "#797876"
PRIMARY = "#4f98a3"
PRIMARY_H = "#227f8b"
SUCCESS = "#6daa45"
ORANGE = "#fdab43"
PURPLE = "#a86fdf"
DANGER = "#dd6974"
BLUE = "#5591c7"

#: One color per file category, used by the bars, the tree tags and the cards.
EXTENSION_COLORS = {
    "images": "#fdab43",
    "videos": "#dd6974",
    "audio": "#6daa45",
    "code": "#4f98a3",
    "docs": "#a86fdf",
    "data": "#5591c7",
    "archives": "#bb653b",
    "other": "#797876",
}

# Node editor
COLOR_ARGUMENT = "#4f98a3"
COLOR_LIANT = "#a86fdf"
COLOR_FOLDER = "#fdab43"

# Explorer preview area
PREVIEW_W = 280
PREVIEW_H = 210

FONT = "Segoe UI"


def apply_styles(root) -> None:
    """Install the dark ttk styles on *root*.

    Widget-specific styles that only one view uses (the preset combobox,
    the operations notebook, the fullscreen scales) stay next to that view.
    """
    from tkinter import ttk

    s = ttk.Style(root)
    s.theme_use("default")
    s.configure("Custom.Treeview",background=SURFACE,fieldbackground=SURFACE,foreground=TEXT,
                bordercolor=BORDER,rowheight=26,font=("Segoe UI",9))
    s.configure("Custom.Treeview.Heading",background=SURFACE2,foreground=MUTED,
                font=("Segoe UI",9,"bold"),relief="flat",borderwidth=0)
    s.map("Custom.Treeview",background=[("selected",PRIMARY_H)],foreground=[("selected","#0f3638")])
    s.configure("Custom.Horizontal.TProgressbar",troughcolor=SURFACE2,background=PRIMARY,bordercolor=BORDER)
    s.configure("Video.Horizontal.TScale",background=SURFACE2,troughcolor=BORDER,sliderlength=12,sliderrelief="flat")
    s.configure("Dark.Vertical.TScrollbar",
        background=SURFACE2, troughcolor=SURFACE,
        bordercolor=SURFACE, arrowcolor=MUTED,
        relief="flat", borderwidth=0)
    s.map("Dark.Vertical.TScrollbar",
        background=[("active", BORDER), ("pressed", PRIMARY_H)],
        arrowcolor=[("active", TEXT)])
    s.configure("Dark.Horizontal.TScrollbar",
        background=SURFACE2, troughcolor=SURFACE,
        bordercolor=SURFACE, arrowcolor=MUTED,
        relief="flat", borderwidth=0)
    s.map("Dark.Horizontal.TScrollbar",
        background=[("active", BORDER), ("pressed", PRIMARY_H)],
        arrowcolor=[("active", TEXT)])

