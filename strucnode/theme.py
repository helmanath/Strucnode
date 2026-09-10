"""The design system: color tokens, a type scale, and the small widget
helpers every view is built from.

Three rules keep the interface coherent as it grows:

* **no literal color in a view** -- a view names a token (``SURFACE``,
  ``ACCENT``), never ``"#2d2c2a"``, so the whole application can be recolored
  from this file alone;
* **no literal font tuple in a view** -- a view calls :func:`font`, which
  clamps every size to the readable range. The first version of the interface
  drifted down to 6 pt labels, which no longer read on a high-DPI screen;
* **every interactive widget says so** -- :func:`hover` gives a plain
  ``tk.Button`` the feedback ttk gives for free, and :class:`Tooltip` explains
  the icon-only ones.
"""

from __future__ import annotations

import logging
import tkinter as tk

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Surfaces -- four levels of elevation, darkest at the back.
# --------------------------------------------------------------------------- #
#: Application background: the plane every panel sits on.
BG = "#161513"
#: A panel or card raised off the background.
SURFACE = "#1f1e1c"
#: A control inside a panel: entries, buttons, table headers.
SURFACE2 = "#2b2a27"
#: The hover/active step above :data:`SURFACE2`.
SURFACE3 = "#3a3835"
#: The node editor work area, deliberately darker than :data:`BG`.
CANVAS_BG = "#121110"
#: Grid lines on the node canvas: a fine mesh and a stronger one every block.
CANVAS_GRID = "#1d1c1a"
CANVAS_GRID_MAJOR = "#262421"
#: A selected node card, one step warmer than an idle one.
NODE_SELECTED = "#2a2724"
#: The two passes of a node card's drop shadow, near then far.
NODE_SHADOW_NEAR = "#100f0e"
NODE_SHADOW_FAR = "#0a0908"

#: A visible separator between two regions.
BORDER = "#3a3835"
#: A separator that should be felt more than seen.
BORDER_SOFT = "#2a2926"

# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #
#: Primary reading color.
TEXT = "#e6e4e1"
#: Secondary text: values next to a label, inactive rows.
TEXT_DIM = "#aeaca8"
#: Section titles, hints, units -- present but never competing.
MUTED = "#8d8b87"
#: Text drawn *on* an accent fill; dark on purpose, accents are light.
ON_ACCENT = "#0c2529"

# --------------------------------------------------------------------------- #
# Accents
# --------------------------------------------------------------------------- #
PRIMARY = "#5cb3c0"
PRIMARY_H = "#7ccbd7"     # hover: accents brighten, they never darken
PRIMARY_D = "#2c7d89"     # pressed / muted variant
SUCCESS = "#7cbf51"
ORANGE = "#f2ab4b"
PURPLE = "#b482e8"
DANGER = "#e57683"
BLUE = "#63a0d6"

#: Kept for callers that still speak the old name.
ACCENT = PRIMARY

#: One color per file category, used by the bars, the tree tags and the cards.
EXTENSION_COLORS = {
    "images": ORANGE,
    "videos": DANGER,
    "audio": SUCCESS,
    "code": PRIMARY,
    "docs": PURPLE,
    "data": BLUE,
    "archives": "#cd7444",
    "other": MUTED,
}

# Node editor
COLOR_ARGUMENT = PRIMARY
COLOR_LIANT = PURPLE
COLOR_FOLDER = ORANGE

# Explorer preview area
PREVIEW_W = 280
PREVIEW_H = 210

# --------------------------------------------------------------------------- #
# Spacing -- a 4 px rhythm, so padding is chosen from a scale, not invented.
# --------------------------------------------------------------------------- #
SP_XS, SP_S, SP_M, SP_L, SP_XL = 2, 4, 8, 14, 20

# --------------------------------------------------------------------------- #
# Typography
# --------------------------------------------------------------------------- #
FONT = "Segoe UI"

#: Nothing is ever drawn smaller than this. Sizes below 8 pt were unreadable on
#: a 4K screen, which is where this application is actually used.
MIN_FONT_SIZE = 8

#: Named steps. Views ask for a role, not a number.
SIZE_TITLE = 14      # window / app title
SIZE_H1 = 11         # panel title
SIZE_H2 = 10         # section title
SIZE_BODY = 10       # tables, entries, buttons
SIZE_SMALL = 9       # secondary values, badges
SIZE_MICRO = 8       # hints, legends -- the floor


def font(size: int = SIZE_BODY, weight: str = "normal") -> tuple:
    """Return a Tk font tuple, never below :data:`MIN_FONT_SIZE`.

    Passing the size through here rather than writing the tuple inline is what
    guarantees the floor holds: a view cannot accidentally reintroduce a 6 pt
    label.
    """
    size = max(MIN_FONT_SIZE, int(size))
    return (FONT, size) if weight == "normal" else (FONT, size, weight)


# --------------------------------------------------------------------------- #
# Widget helpers
# --------------------------------------------------------------------------- #
def hover(widget, normal_bg, hover_bg, normal_fg=None, hover_fg=None):
    """Give *widget* a real hover state and return it.

    ``activebackground`` only applies while the mouse button is *down*, so a
    plain ``tk.Button`` looks inert under the cursor. Binding
    ``<Enter>``/``<Leave>`` is what makes a control read as clickable.
    """
    def enter(_event=None):
        try:
            widget.config(bg=hover_bg, **({"fg": hover_fg} if hover_fg else {}))
        except tk.TclError:
            pass

    def leave(_event=None):
        try:
            widget.config(bg=normal_bg, **({"fg": normal_fg} if normal_fg else {}))
        except tk.TclError:
            pass

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")
    return widget


def button(parent, *, variant="ghost", size=SIZE_BODY, bold=False, **kwargs):
    """Build a themed ``tk.Button`` with its hover state already wired.

    ``variant`` picks the role rather than the colors: ``primary`` for the one
    action a view exists for, ``ghost`` for everything else, ``danger`` for a
    destructive one, ``quiet`` for an icon in a toolbar.
    """
    fg = kwargs.pop("fg", None)
    palette = {
        "primary": (PRIMARY, PRIMARY_H, ON_ACCENT, ON_ACCENT),
        "ghost": (SURFACE2, SURFACE3, fg or TEXT, fg or TEXT),
        "quiet": (SURFACE, SURFACE2, fg or MUTED, fg or TEXT),
        "danger": (DANGER, "#f08f9a", "#3d1116", "#3d1116"),
    }
    bg, bg_h, color, color_h = palette.get(variant, palette["ghost"])
    btn = tk.Button(parent, bg=bg, fg=color, activebackground=bg_h,
                    activeforeground=color_h, relief="flat", bd=0,
                    highlightthickness=0, cursor="hand2",
                    font=font(size, "bold" if bold else "normal"), **kwargs)
    return hover(btn, bg, bg_h, color, color_h)


def divider(parent, bg=BORDER_SOFT, pady=SP_S):
    """A one-pixel horizontal rule, packed and returned."""
    line = tk.Frame(parent, bg=bg, height=1)
    line.pack(fill="x", pady=pady)
    return line


def section_title(parent, bg=SURFACE, fg=MUTED):
    """An unpacked, unbound section heading; the caller binds it to a key."""
    return tk.Label(parent, bg=bg, fg=fg, font=font(SIZE_MICRO, "bold"))


class Tooltip:
    """A dark tooltip shown after a short delay under *widget*.

    Icon-only controls (the bin, the stop button, the fullscreen toggle) carry
    no label, so without this the only way to learn what they do is to press
    them -- which for some of them is exactly what one should not do to find
    out.

    *text* may be a callable, so a tooltip can describe a state that changes
    (a tab that is locked until a folder has been analyzed, for instance).
    """

    DELAY_MS = 450

    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._window = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self._widget.after(self.DELAY_MS, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self):
        text = self._text() if callable(self._text) else self._text
        if not text or self._window is not None:
            return
        try:
            x = self._widget.winfo_rootx() + 12
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
            win = tk.Toplevel(self._widget)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            win.configure(bg=BORDER)
            tk.Label(win, text=text, bg=SURFACE2, fg=TEXT, justify="left",
                     font=font(SIZE_MICRO), padx=8, pady=5).pack(padx=1, pady=1)
            self._window = win
        except tk.TclError:
            self._window = None

    def _hide(self, _event=None):
        self._cancel()
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None


def rounded_rect(canvas, x1, y1, x2, y2, radius=10, **kwargs):
    """Draw a rounded rectangle on *canvas* and return its item id.

    Tk has no rounded rectangle. A smoothed polygon whose corner points are
    doubled gives one that is indistinguishable from a real one at the sizes
    the node editor uses, and it stays a single canvas item -- which matters,
    because a node is redrawn on every move.
    """
    radius = max(0, min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2))
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=12, **kwargs)


def apply_styles(root) -> None:
    """Install the dark ttk styles on *root*.

    Widget-specific styles that only one view uses (the preset combobox,
    the operations notebook, the fullscreen scales) stay next to that view.
    """
    from tkinter import ttk

    s = ttk.Style(root)
    s.theme_use("default")
    s.configure("Custom.Treeview", background=SURFACE, fieldbackground=SURFACE,
                foreground=TEXT, bordercolor=BORDER, borderwidth=0,
                rowheight=28, font=font(SIZE_SMALL))
    s.configure("Custom.Treeview.Heading", background=SURFACE2, foreground=MUTED,
                font=font(SIZE_SMALL, "bold"), relief="flat", borderwidth=0,
                padding=(6, 6))
    s.map("Custom.Treeview.Heading",
          background=[("active", SURFACE3)], foreground=[("active", TEXT)])
    s.map("Custom.Treeview",
          background=[("selected", PRIMARY_D)],
          foreground=[("selected", "#eaf7f9")])
    # The default layout wraps the rows in a sunken 3D field; dropping it is
    # what lets a table sit flush inside its panel.
    try:
        s.layout("Custom.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    except Exception:  # pragma: no cover - depends on the ttk theme in use
        log.debug("cannot flatten the Treeview layout", exc_info=True)
    s.configure("Custom.Horizontal.TProgressbar", troughcolor=SURFACE2,
                background=PRIMARY, bordercolor=SURFACE2, lightcolor=PRIMARY,
                darkcolor=PRIMARY, borderwidth=0, thickness=6)
    s.configure("Video.Horizontal.TScale", background=SURFACE2,
                troughcolor=BORDER, sliderlength=14, sliderrelief="flat")
    for orient in ("Vertical", "Horizontal"):
        s.configure(f"Dark.{orient}.TScrollbar",
                    background=SURFACE2, troughcolor=SURFACE,
                    bordercolor=SURFACE, arrowcolor=MUTED,
                    relief="flat", borderwidth=0, width=11)
        s.map(f"Dark.{orient}.TScrollbar",
              background=[("active", SURFACE3), ("pressed", PRIMARY_D)],
              arrowcolor=[("active", TEXT)])
