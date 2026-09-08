"""The node editor tab: palette, canvas, wiring, presets and structure preview."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ...core import fields
from ...core.tree import (
    arg_token,
    build_tree,
    count_files,
    dyn_arg_part,
    dyn_folder_token,
    dyn_literal_part,
    folder_token,
)
from ...i18n import set_raw, t, tr, tr_var
from ...theme import (
    BG,
    BORDER,
    COLOR_ARGUMENT,
    COLOR_FOLDER,
    COLOR_LIANT,
    MUTED,
    ORANGE,
    PRIMARY,
    PRIMARY_H,
    SUCCESS,
    SURFACE,
    SURFACE2,
    TEXT,
)
from .node import Node
from .presets import PresetStore

log = logging.getLogger(__name__)


class NodeEditorTab(tk.Frame):
    """Main node-editor workspace responsible for structure design, presets, and previews."""

    def __init__(self, parent, get_files_cb):
        super().__init__(parent, bg=BG)
        self._get_files      = get_files_cb
        self._nodes          = {}
        self._connections    = []
        self._next_id        = 0
        self._drag_node      = None
        self._drag_offset    = (0, 0)
        self._selected_nodes = set()
        self._rubber_start   = None   # (x, y) where the rubber band started
        self._rubber_rect    = None   # canvas id of the selection rectangle
        self._wire_src       = None   # (nid, port_type)  port_type = "chain"|"attr"
        self._wire_tmp       = None
        self._pan_start       = None
        self._shift_pan_start = None
        self._canvas_zoom     = 1.0
        self._rename_win     = None
        self._last_tree      = None
        self._last_labels    = []
        self._uv_cache       = {}
        self._preset_dirty = False
        self._preset_name_var = None  # created by _build_ui
        self._presets = PresetStore()
        self._build_ui()
        self.after(200, self._load_last_preset)
    def _build_ui(self):
        tb = tk.Frame(self, bg=SURFACE, pady=6, padx=10)
        tb.pack(fill="x")
        self._lbl_title = tr(tk.Label(tb, bg=SURFACE, fg=PRIMARY,
                 font=("Segoe UI", 9, "bold")), "node_editor_title")
        self._lbl_title.pack(side="left")
        self._lbl_hint = tr(tk.Label(tb,

            bg=SURFACE, fg=MUTED, font=("Segoe UI", 7)), "node_editor_hint")
        self._lbl_hint.pack(side="left", padx=(8,0))
        self._btn_clear = tr(tk.Button(tb, bg=SURFACE2, fg=MUTED,
                  relief="flat", font=("Segoe UI", 9), padx=8, pady=3,
                  cursor="hand2", command=self._clear_all), "clear_all")
        self._btn_clear.pack(side="right", padx=(6,0))
        self._btn_preview = tr(tk.Button(tb, bg=PRIMARY, fg="#0f3638",
                  activebackground=PRIMARY_H, activeforeground="#0f3638",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3,
                  cursor="hand2", command=self._show_preview), "click_preview")
        self._btn_preview.pack(side="right", padx=(6,0))
        self._btn_reset_view = tr(tk.Button(tb, bg=SURFACE2, fg=MUTED,
                  relief="flat", font=("Segoe UI", 9), padx=8, pady=3,
                  cursor="hand2", command=self._reset_view), "reset_view")
        self._btn_reset_view.pack(side="right", padx=(0,6))
        tk.Frame(tb, bg=BORDER, width=1).pack(side="right", fill="y", pady=4, padx=6)
        self._preset_name_var = tk.StringVar(value=t("no_files_indexed"))
        self._preset_dirty = False
        pbar = tk.Frame(tb, bg=SURFACE)
        pbar.pack(side="right", fill="y")

        def pbtn(text, fg, cmd, padx_in=8, bold=False):
            """Build one uniformly styled preset button in the preset bar."""
            f = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
            return tk.Button(pbar, text=text, bg=SURFACE2, fg=fg,
                             relief="flat", font=f,
                             padx=padx_in, pady=0,
                             cursor="hand2", command=cmd)
        self._btn_new_preset = tr(tk.Button(pbar, bg=SURFACE2, fg=SUCCESS,
                  relief="flat", font=("Segoe UI", 9),
                  padx=8, pady=0, cursor="hand2",
                  command=self._new_preset), "new_preset")
        self._btn_new_preset.pack(side="left", padx=(0, 6), fill="y")

        self._preset_del_btn = tk.Button(pbar, text="🗑", bg=SURFACE2, fg=MUTED,
                  relief="flat", font=("Segoe UI", 9),
                  padx=8, pady=0, cursor="hand2",
                  command=self._delete_current_preset)
        self._preset_del_btn.pack(side="left", padx=(0, 2), fill="y")

        self._btn_save_preset = tr(tk.Button(pbar, bg=SURFACE2, fg=TEXT,
                  relief="flat", font=("Segoe UI", 9),
                  padx=8, pady=0, cursor="hand2",
                  command=self._save_preset), "save_preset")
        self._btn_save_preset.pack(side="left", padx=(0, 6), fill="y")

        style_cb = ttk.Style()
        style_cb.configure("Preset.TCombobox",
            fieldbackground=SURFACE2, background=SURFACE2,
            foreground=TEXT, selectbackground=SURFACE2,
            selectforeground=TEXT, arrowcolor=PRIMARY,
            borderwidth=0, relief="flat")
        style_cb.map("Preset.TCombobox",
            fieldbackground=[(("readonly",), SURFACE2)],
            foreground=[(("readonly",), TEXT)])
        self._preset_combo_var = tk.StringVar(value="—")
        self._preset_combo = ttk.Combobox(
            pbar, textvariable=self._preset_combo_var,
            state="readonly", width=18,
            style="Preset.TCombobox",
            font=("Segoe UI", 9))
        self._preset_combo.pack(side="left", padx=(0, 4), fill="y")
        self._preset_combo.bind("<<ComboboxSelected>>", self._on_preset_combo_select)

        self._preset_dirty_lbl = tk.Label(pbar, text="", bg=SURFACE,
            fg=ORANGE, font=("Segoe UI", 10, "bold"), width=1)
        self._preset_dirty_lbl.pack(side="left", fill="y")

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)
        pal_outer = tk.Frame(main, bg=SURFACE, width=205)
        pal_outer.pack(side="left", fill="y")
        pal_outer.pack_propagate(False)
        self._lbl_palette = tr(tk.Label(pal_outer, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), pady=8), "palette")
        self._lbl_palette.pack(fill="x", padx=10)
        tk.Frame(pal_outer, bg=BORDER, height=1).pack(fill="x")

        _pc = tk.Canvas(pal_outer, bg=SURFACE, highlightthickness=0, bd=0)
        _pvsb = ttk.Scrollbar(pal_outer, orient="vertical", command=_pc.yview,
                              style="Dark.Vertical.TScrollbar")
        _pc.pack(side="left", fill="both", expand=True)
        _pc.configure(yscrollcommand=self._pal_yscroll_cb)

        pal = tk.Frame(_pc, bg=SURFACE)
        _pw = _pc.create_window((0,0), window=pal, anchor="nw")

        def _pal_update_scroll(e=None):
            _pc.configure(scrollregion=_pc.bbox("all"))
            content_h = pal.winfo_reqheight()
            canvas_h  = _pc.winfo_height()
            if content_h > canvas_h + 2:
                if not _pvsb.winfo_ismapped():
                    _pvsb.pack(side="right", fill="y", before=_pc)
            else:
                if _pvsb.winfo_ismapped():
                    _pvsb.pack_forget()
                    _pc.yview_moveto(0)

        pal.bind("<Configure>", _pal_update_scroll)
        _pc.bind("<Configure>", lambda e: (_pc.itemconfig(_pw, width=e.width),
                                            _pal_update_scroll()))

        def _pscroll(e): _pc.yview_scroll(int(-1*(e.delta/120)), "units")
        _pc.bind("<MouseWheel>", _pscroll)
        pal.bind("<MouseWheel>", _pscroll)

        self._pal_canvas    = _pc
        self._pal_scrollbar = _pvsb
        self._pal_scroll_fn = _pscroll
        self._pal_update_scroll = _pal_update_scroll
        pf = tk.Frame(pal, bg=SURFACE)
        pf.pack(fill="x", padx=8, pady=(8,4))
        self._lbl_how_to_build = tr(tk.Label(pf, bg=SURFACE, fg=PRIMARY,
                 font=("Segoe UI", 7, "bold")), "how_to_build")
        self._lbl_how_to_build.pack(anchor="w", pady=(0,4))
        self._lbl_how_to_build_txt = tr(tk.Label(pf,

            bg=SURFACE, fg=MUTED, font=("Segoe UI", 7),
            justify="left", wraplength=185), "how_to_build_txt")
        self._lbl_how_to_build_txt.pack(anchor="w", pady=(0,4))
        tk.Frame(pf, bg=BORDER, height=1).pack(fill="x")
        self._pal_meta_frame = tk.Frame(pal, bg=SURFACE)
        self._pal_meta_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self._build_palette_meta()
        self._pal_info = tk.Label(pal, text="", bg=SURFACE, fg=MUTED,
                                  font=("Segoe UI", 7), justify="center", pady=6)
        self._pal_info.pack(fill="x", padx=6)
        leg = tk.Frame(pal, bg=SURFACE)
        leg.pack(fill="x", padx=8, pady=(0,8))
        tk.Frame(leg, bg=BORDER, height=1).pack(fill="x", pady=4)
        for key, col in [("pal_legend_chain", TEXT),
                         ("pal_legend_meta", PRIMARY),
                         ("pal_legend_folder", ORANGE),
                         ("pal_legend_multisel", MUTED),
                         ("pal_legend_cut", MUTED)]:
            tr(tk.Label(leg, bg=SURFACE, fg=col, font=("Segoe UI", 7)), key).pack(anchor="w")
        cf = tk.Frame(main, bg=BG)
        cf.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(cf, bg="#171614", highlightthickness=0, cursor="crosshair")
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda e: self._draw_grid())
        self._bind_canvas_events()
        self._hint = self._lbl_drag_hint = tr(tk.Label(cf,

            bg="#171614", fg=MUTED, font=("Segoe UI", 10)), "drag_nodes_hint")
        self._hint.place(relx=0.5, rely=0.5, anchor="center")
        pv = tk.Frame(main, bg=SURFACE, width=285)
        pv.pack(side="right", fill="y")
        pv.pack_propagate(False)
        self._lbl_preview_struct = tr(tk.Label(pv, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), pady=8), "preview_structure")
        self._lbl_preview_struct.pack(fill="x", padx=8)
        tk.Frame(pv, bg=BORDER, height=1).pack(fill="x")
        self._chain_lbl = tr(tk.Label(pv,

            bg=SURFACE, fg=MUTED, font=("Segoe UI", 8),
            justify="center", pady=10, wraplength=265), "chain_click")
        self._chain_lbl.pack(fill="x", padx=6)
        tf = tk.Frame(pv, bg=SURFACE)
        tf.pack(fill="both", expand=True)
        self._prev_tree = ttk.Treeview(tf, show="tree headings",
                                       style="Custom.Treeview", selectmode="none")
        self._prev_tree["columns"] = ("count",)
        self._prev_tree.heading("#0",    text=t("folder_node"))
        self._prev_tree.heading("count", text=t("col_count"))
        self._prev_tree.column("#0",    width=195)
        self._prev_tree.column("count", width=60, anchor="center")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self._prev_tree.yview, style="Dark.Vertical.TScrollbar")
        self._prev_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._prev_tree.pack(fill="both", expand=True)

        self._status = tk.StringVar(value=t("canvas_empty"))
        tk.Label(self, textvariable=self._status, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8), anchor="w", padx=10, pady=4).pack(fill="x", side="bottom")
        self._nodal_prog_var = tk.IntVar(value=0)
        self._nodal_prog_frame = tk.Frame(self, bg=SURFACE, height=4)
        self._nodal_prog_frame.pack(fill="x", side="bottom")
        self._nodal_prog_frame.pack_propagate(False)
        self._nodal_prog_inner = tk.Frame(self._nodal_prog_frame, bg=PRIMARY, height=4)
        self._nodal_prog_inner.place(x=0, y=0, relwidth=0.0, height=4)
        self._nodal_prog_var.trace_add("write", self._update_nodal_prog_bar)
    def _pal_yscroll_cb(self, first, last):
        """yscrollcommand handler: forward to the scrollbar and hide it when unused."""
        if hasattr(self, "_pal_scrollbar"):
            self._pal_scrollbar.set(first, last)

    def _bind_pal_scroll(self, w):
        if hasattr(self, "_pal_scroll_fn"):
            w.bind("<MouseWheel>", self._pal_scroll_fn)
        for c in w.winfo_children():
            self._bind_pal_scroll(c)

    def _build_palette_meta(self):
        for w in self._pal_meta_frame.winfo_children():
            w.destroy()
        tr(tk.Label(self._pal_meta_frame, bg=SURFACE, fg=COLOR_FOLDER,
                 font=("Segoe UI", 7, "bold")), "structure_label").pack(anchor="w", pady=(4,2))
        btn_f = tr(tk.Button(self._pal_meta_frame,
            bg=SURFACE2, fg=COLOR_FOLDER, relief="flat", font=("Segoe UI", 8),
            padx=6, pady=3, cursor="hand2", anchor="w",
            activebackground=BORDER, activeforeground=COLOR_FOLDER,
            command=self._add_folder_node), "folder_node")
        btn_f.pack(fill="x", pady=1)
        self._bind_palette_dnd_folder(btn_f)
        tr(tk.Label(self._pal_meta_frame, bg=SURFACE, fg=COLOR_LIANT,
                 font=("Segoe UI", 7, "bold")), "connector_label").pack(anchor="w", pady=(6,2))
        btn_l = tr(tk.Button(self._pal_meta_frame,

            bg=SURFACE2, fg=COLOR_LIANT, relief="flat", font=("Segoe UI", 8),
            padx=6, pady=3, cursor="hand2", anchor="w",
            activebackground=BORDER, activeforeground=COLOR_LIANT,
            command=self._add_liant_node), "connector_btn")
        btn_l.pack(fill="x", pady=1)
        self._bind_palette_dnd_liant(btn_l)
        tr(tk.Label(self._pal_meta_frame, bg=SURFACE, fg=COLOR_ARGUMENT,
                 font=("Segoe UI", 7, "bold")), "arguments_label").pack(anchor="w", pady=(6,2))
        for section_key, keys in fields.PALETTE_SECTIONS:
            tk.Label(self._pal_meta_frame, text=t(section_key).upper(), bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 6, "bold"), pady=2).pack(anchor="w", fill="x")
            for k in keys:
                color = fields.color(k)
                badge = f"  ({self._uv_cache[k]})" if k in self._uv_cache else ""
                btn   = tk.Button(self._pal_meta_frame,
                                  text=f"📌  {fields.label(k)}{badge}",
                                  bg=SURFACE2, fg=color,
                                  relief="flat", font=("Segoe UI", 8), padx=6, pady=3,
                                  cursor="hand2", anchor="w",
                                  activebackground=BORDER, activeforeground=color,
                                  command=lambda key=k: self._add_argument_node(key))
                btn.pack(fill="x", pady=1)
                self._bind_palette_dnd(btn, k)
        self._bind_pal_scroll(self._pal_meta_frame)
        if hasattr(self, '_pal_update_scroll'): self._pal_update_scroll()

    def refresh_palette(self):
        files = self._get_files()
        if not files:
            self._build_palette_meta()
            tr(self._pal_info, "no_files_indexed")
            return
        tr(self._pal_info, "computing_n", n=len(files))
        self._build_palette_meta()
        def _compute():
            try:
                cache = {}
                for k, fld in fields.FIELDS.items():
                    try:
                        cache[k] = len({fields.resolve(f, fld.resolver) for f in files})
                    except Exception:
                        log.debug("cannot count values for field %r", k, exc_info=True)
                        cache[k] = 0
                self.after(0, lambda: self._apply_uv_cache(cache, len(files)))
            except Exception:
                log.warning("palette value count failed", exc_info=True)
        threading.Thread(target=_compute, daemon=True).start()

    def _bind_palette_dnd(self, btn, type_key):
        """Permet de drag un bouton argument de palette vers le canvas."""
        _state = {"dragging": False, "ghost": None}

        def on_press(e):
            _state["dragging"] = False; _state["ghost"] = None

        def on_motion(e):
            abs_x = btn.winfo_rootx() + e.x
            abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            on_canvas = 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height()
            if not _state["dragging"]:
                _state["dragging"] = True; btn.config(cursor="fleur")
            if on_canvas:
                self._canvas.config(cursor="fleur")
                ghost_color = fields.color(type_key)
                if _state["ghost"] is None:
                    _state["ghost"] = self._canvas.create_rectangle(
                        cx, cy, cx + Node.NW, cy + Node.NH,
                        outline=ghost_color, fill="#1c1b19", width=2, dash=(6,3), tags="pal_ghost")
                    _state["ghost_lbl"] = self._canvas.create_text(
                        cx + Node.NW//2, cy + Node.NH//2,
                        text=f"📌  {fields.label(type_key)}", fill=ghost_color,
                        font=("Segoe UI", 8), tags="pal_ghost")
                else:
                    self._canvas.coords(_state["ghost"], cx, cy, cx+Node.NW, cy+Node.NH)
                    self._canvas.coords(_state["ghost_lbl"], cx+Node.NW//2, cy+Node.NH//2)
            else:
                self._canvas.config(cursor="crosshair")
                if _state["ghost"] is not None:
                    self._canvas.delete("pal_ghost"); _state["ghost"] = None

        def on_release(e):
            btn.config(cursor="hand2"); self._canvas.config(cursor="crosshair")
            self._canvas.delete("pal_ghost"); _state["ghost"] = None
            if not _state["dragging"]: return
            _state["dragging"] = False
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            if 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height():
                if self._hint: self._hint.place_forget()
                nid = self._next_id; self._next_id += 1
                drop_x = max(10, cx - Node.NW//2); drop_y = max(10, cy - Node.NH//2)
                self._nodes[nid] = Node(self._canvas, nid, "argument", type_key, drop_x, drop_y)
                self._update_status()

        btn.bind("<ButtonPress-1>",   on_press,   add="+")
        btn.bind("<B1-Motion>",       on_motion)
        btn.bind("<ButtonRelease-1>", on_release, add="+")

    def _bind_palette_dnd_folder(self, btn):
        """Drag a folder node from the palette onto the canvas."""
        _state = {"dragging": False, "ghost": None}

        def on_press(e):
            _state["dragging"] = False; _state["ghost"] = None

        def on_motion(e):
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            on_canvas = 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height()
            if not _state["dragging"]:
                _state["dragging"] = True; btn.config(cursor="fleur")
            if on_canvas:
                self._canvas.config(cursor="fleur")
                if _state["ghost"] is None:
                    _state["ghost"] = self._canvas.create_rectangle(
                        cx, cy, cx+Node.NW, cy+Node.NH,
                        outline=COLOR_FOLDER, fill="#1c1b19", width=2, dash=(6,3), tags="pal_ghost")
                    _state["ghost_lbl"] = self._canvas.create_text(
                        cx+Node.NW//2, cy+Node.NH//2,
                        text=t("folder_node"), fill=COLOR_FOLDER,
                        font=("Segoe UI", 8), tags="pal_ghost")
                else:
                    self._canvas.coords(_state["ghost"], cx, cy, cx+Node.NW, cy+Node.NH)
                    self._canvas.coords(_state["ghost_lbl"], cx+Node.NW//2, cy+Node.NH//2)
            else:
                self._canvas.config(cursor="crosshair")
                if _state["ghost"] is not None:
                    self._canvas.delete("pal_ghost"); _state["ghost"] = None

        def on_release(e):
            btn.config(cursor="hand2"); self._canvas.config(cursor="crosshair")
            self._canvas.delete("pal_ghost"); _state["ghost"] = None
            if not _state["dragging"]: return
            _state["dragging"] = False
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            if 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height():
                if self._hint: self._hint.place_forget()
                nid = self._next_id; self._next_id += 1
                drop_x = max(10, cx - Node.NW//2); drop_y = max(10, cy - Node.NH//2)
                self._nodes[nid] = Node(self._canvas, nid, "folder", None, drop_x, drop_y)
                self._update_status()

        btn.bind("<ButtonPress-1>",   on_press,   add="+")
        btn.bind("<B1-Motion>",       on_motion)
        btn.bind("<ButtonRelease-1>", on_release, add="+")

    def _bind_palette_dnd_liant(self, btn):
        """Drag a connector node from the palette onto the canvas."""
        _state = {"dragging": False, "ghost": None}

        def on_press(e):
            _state["dragging"] = False; _state["ghost"] = None

        def on_motion(e):
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            on_canvas = 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height()
            if not _state["dragging"]:
                _state["dragging"] = True; btn.config(cursor="fleur")
            if on_canvas:
                self._canvas.config(cursor="fleur")
                if _state["ghost"] is None:
                    _state["ghost"] = self._canvas.create_rectangle(
                        cx, cy, cx+Node.NW, cy+Node.NH,
                        outline=COLOR_LIANT, fill="#1c1b19", width=2, dash=(6,3), tags="pal_ghost")
                    _state["ghost_lbl"] = self._canvas.create_text(
                        cx+Node.NW//2, cy+Node.NH//2,
                        text=t("connector_canvas"), fill=COLOR_LIANT,
                        font=("Segoe UI", 8), tags="pal_ghost")
                else:
                    self._canvas.coords(_state["ghost"], cx, cy, cx+Node.NW, cy+Node.NH)
                    self._canvas.coords(_state["ghost_lbl"], cx+Node.NW//2, cy+Node.NH//2)
            else:
                self._canvas.config(cursor="crosshair")
                if _state["ghost"] is not None:
                    self._canvas.delete("pal_ghost"); _state["ghost"] = None

        def on_release(e):
            btn.config(cursor="hand2"); self._canvas.config(cursor="crosshair")
            self._canvas.delete("pal_ghost"); _state["ghost"] = None
            if not _state["dragging"]: return
            _state["dragging"] = False
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            if 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height():
                if self._hint: self._hint.place_forget()
                nid = self._next_id; self._next_id += 1
                drop_x = max(10, cx - Node.NW//2); drop_y = max(10, cy - Node.NH//2)
                self._nodes[nid] = Node(self._canvas, nid, "liant", None, drop_x, drop_y)
                self._update_status()

        btn.bind("<ButtonPress-1>",   on_press,   add="+")
        btn.bind("<B1-Motion>",       on_motion)
        btn.bind("<ButtonRelease-1>", on_release, add="+")

    def _apply_uv_cache(self, cache, n):
        self._uv_cache = cache
        self._build_palette_meta()
        tr(self._pal_info, "files_indexed", n=n)
        if hasattr(self, '_pal_update_scroll'): self._pal_update_scroll()

    def _draw_grid(self):
        self._canvas.delete("grid")
        self.update_idletasks()
        w = self._canvas.winfo_width()  or 1200
        h = self._canvas.winfo_height() or 800
        for x in range(0, w, 40): self._canvas.create_line(x, 0, x, h, fill="#1e1d1b", tags="grid")
        for y in range(0, h, 40): self._canvas.create_line(0, y, w, y, fill="#1e1d1b", tags="grid")
        self._canvas.tag_lower("grid")

    def _reset_view(self):
        self._canvas_zoom = 1.0
        Node.NW = 200
        Node.NH = 90
        for n in self._nodes.values(): n.draw()
        self._redraw_wires()
        self._draw_grid()
        tr_var(self._status, "view_reset")
    def _next_pos(self):
        base_x, base_y = 120, 120
        offset = len(self._nodes) * 30
        return base_x + offset, base_y + offset

    def _add_folder_node(self, name=None):
        if self._hint: self._hint.place_forget()
        x, y = self._next_pos()
        nid = self._next_id; self._next_id += 1
        self._nodes[nid] = Node(self._canvas, nid, "folder", None, x, y,
                                label_override=name or None)
        self._update_status()

    def _add_argument_node(self, type_key):
        if self._hint: self._hint.place_forget()
        x, y = self._next_pos()
        nid = self._next_id; self._next_id += 1
        self._nodes[nid] = Node(self._canvas, nid, "argument", type_key, x, y)
        self._update_status()

    def _add_liant_node(self, label=None):
        if self._hint: self._hint.place_forget()
        x, y = self._next_pos()
        nid = self._next_id; self._next_id += 1
        self._nodes[nid] = Node(self._canvas, nid, "liant", None, x, y,
                                label_override=label or "-")
        self._update_status()
    def _delete_node(self, nid):
        if nid not in self._nodes: return
        for cid in self._nodes[nid].canvas_ids:
            self._canvas.delete(cid)
        del self._nodes[nid]
        to_remove = [c for c in self._connections if c["src"] == nid or c["dst"] == nid]
        for c in to_remove:
            self._canvas.delete(c.get("cid"))
# Node deletion must also remove all related graph connections to keep the canvas state coherent.
        self._connections = [c for c in self._connections if c["src"] != nid and c["dst"] != nid]
        self._selected_nodes.discard(nid)
        if self._selected_node_primary == nid:
            self._selected_node_primary = None
        self._update_status()
        cur = self._preset_name_var.get() if hasattr(self, '_preset_name_var') else ''
        if cur and cur != t("no_preset") and not self._preset_dirty:
            self._mark_dirty()

    @property
    def _selected_node_primary(self):
        return getattr(self, "_sel_primary", None)
    @_selected_node_primary.setter
    def _selected_node_primary(self, v):
        self._sel_primary = v

    def _delete_selected(self):
        for nid in list(self._selected_nodes):
            self._delete_node(nid)
        self._selected_nodes.clear()
        self._update_status()

    # Preset storage lives in presets.PresetStore; these thin wrappers keep the
    # call sites in this class readable.
    def _list_presets(self):
        return self._presets.names()

    def _get_last_preset_name(self):
        return self._presets.last_name()

    def _set_last_preset_name(self, name):
        self._presets.set_last_name(name)

    def _mark_dirty(self):
        """Mark the canvas as changed since the last load or save."""
        self._preset_dirty = True
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="✦")

    def _mark_clean(self, name):
        """Mark the canvas as clean: the preset was just saved or loaded."""
        self._preset_dirty = False
        set_raw(self._preset_name_var, name)
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="")
        self._refresh_preset_combo()
    def _preset_data(self):
        return {
            "nodes": [
                {"id": nid, "family": n.node_family, "type_key": n.type_key,
                 "label": n.label, "label_is_default": n.label_is_default,
                 "x": n.x, "y": n.y, "separator": n.separator}
                for nid, n in self._nodes.items()
            ],
            "connections": [
                {"src": c["src"], "dst": c["dst"], "ctype": c["ctype"]}
                for c in self._connections
            ],
            "next_id": self._next_id
        }

    def _apply_preset_data(self, data):
        """Rebuild the canvas from a preset dict. Does NOT mark it dirty."""
        self._canvas.delete("all")
        self._nodes.clear()
        self._connections.clear()
        self._selected_nodes.clear()
        self._draw_grid()
        for nd in data.get("nodes", []):
            nid = nd["id"]
            n = Node(self._canvas, nid, nd["family"],
                     nd.get("type_key") or nd.get("typekey"),
                     nd["x"], nd["y"], label_override=nd.get("label"))
            n.separator = nd.get("separator", "")
            n.label_is_default = nd.get("label_is_default", False)
            n.draw()
            self._nodes[nid] = n
        for cd in data.get("connections", []):
            if cd["src"] in self._nodes and cd["dst"] in self._nodes:
                self._connections.append({"src": cd["src"], "dst": cd["dst"],
                                          "ctype": cd["ctype"], "cid": None})
        self._next_id = data.get("next_id",
            max((nd["id"] for nd in data.get("nodes", [])), default=0) + 1)
        self._redraw_wires()
        if self._hint:
            self._hint.place_forget()
            self._hint = None
        self._update_status()
    def _save_preset(self):
        cur_name = self._preset_name_var.get().strip()
        is_new = (not cur_name or cur_name == t("no_preset"))

        if not is_new:
            try:
                self._presets.save(cur_name, self._preset_data())
                self._set_last_preset_name(cur_name)
                self._mark_clean(cur_name)
            except Exception as e:
                    messagebox.showerror(t("dlg_save_error"), str(e), parent=self)
            return
        win = tk.Toplevel(self)
        win.title(t("save_preset_title"))
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        tr(tk.Label(win, bg=BG, fg=TEXT,
                 font=("Segoe UI", 10)), "preset_name_lbl").pack(padx=20, pady=(16,4), anchor="w")
        var = tk.StringVar(value="")
        entry = tk.Entry(win, textvariable=var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat",
                         font=("Segoe UI", 11), width=28)
        entry.pack(padx=20, ipady=6, fill="x")
        entry.select_range(0, "end")
        entry.focus_set()

        presets = self._list_presets()
        if presets:
            tr(tk.Label(win, bg=BG, fg=MUTED,
                     font=("Segoe UI", 8)), "overwrite_lbl").pack(padx=20, pady=(8,2), anchor="w")
            lb_frame = tk.Frame(win, bg=SURFACE2)
            lb_frame.pack(padx=20, fill="x")
            lb = tk.Listbox(lb_frame, bg=SURFACE2, fg=TEXT,
                            selectbackground=PRIMARY_H, selectforeground="#0f3638",
                            relief="flat", font=("Segoe UI", 9),
                            height=min(5, len(presets)), activestyle="none")
            for p in presets:
                lb.insert("end", p)
            lb.pack(fill="x")
            lb.bind("<<ListboxSelect>>",
                lambda e: var.set(lb.get(lb.curselection()[0])) if lb.curselection() else None)

        err_lbl = tk.Label(win, text="", bg=BG, fg="#dd6974", font=("Segoe UI", 8))
        err_lbl.pack(padx=20, anchor="w")
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(padx=20, pady=(4,16), fill="x")

        def do_save():
            name = var.get().strip()
            if not name:
                tr(err_lbl, "err_empty_name")
                return
            if any(c in set(r'/\:*?"<>|') for c in name):
                tr(err_lbl, "err_bad_chars")
                return
            try:
                self._presets.save(name, self._preset_data())
                self._set_last_preset_name(name)
                self._mark_clean(name)
                win.destroy()
            except Exception as e:
                tr(err_lbl, "dlg_preset_err", e=e)

        entry.bind("<Return>", lambda e: do_save())
        tr(tk.Button(btn_row, bg=SURFACE2, fg=MUTED, relief="flat",
                  font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2",
                  command=win.destroy), "cancel").pack(side="right", padx=(6,0))
        tr(tk.Button(btn_row, bg=PRIMARY, fg="#0f3638", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=4, cursor="hand2",
                  command=do_save), "save_preset").pack(side="right")
        win.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width()//2 - win.winfo_width()//2
        py = self.winfo_rooty() + self.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{px}+{py}")
    def _refresh_preset_combo(self):
        """Resync the combobox with what is on disk and what is loaded.

        The combo variable always holds the raw preset name; the unsaved-changes
        star is shown by _preset_dirty_lbl, never folded into the name.
        """
        if not hasattr(self, "_preset_combo"):
            return
        presets = self._list_presets()
        if presets:
            self._preset_combo["values"] = presets
            self._preset_combo.config(state="readonly")
        else:
            self._preset_combo["values"] = []
            self._preset_combo.config(state="disabled")
            tr_var(self._preset_combo_var, "no_preset")
            if hasattr(self, "_preset_dirty_lbl"):
                self._preset_dirty_lbl.config(text="")
            return
        cur = self._preset_name_var.get().strip()
        if cur and cur != t("no_preset") and cur in presets:
            set_raw(self._preset_combo_var, cur)
        else:
            tr_var(self._preset_combo_var, "select_preset")
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="✦" if self._preset_dirty else "")

    def _on_preset_combo_select(self, event=None):
        """Load the preset selected in the combobox."""
        name = self._preset_combo_var.get().strip()
        if not name or name.startswith("—") or name == t("no_preset"):
            return
        if self._preset_dirty:
            cur = self._preset_name_var.get().strip()
            label = f'"{cur}"' if cur and cur != t("no_preset") else t("current_preset")
            rep = messagebox.askyesnocancel(
                t("load_preset_title"),
                t("save_before_load", label=label, name=name),
                parent=self)
            if rep is None:
                self._refresh_preset_combo()
                return
            if rep:
                self._save_preset()
        data = self._presets.load(name)
        if data is None:
            messagebox.showerror(t("dlg_not_found"),
                                 t("dlg_file_missing", path=self._presets.path_for(name)),
                                 parent=self)
            self._refresh_preset_combo()
            return
        try:
            self._apply_preset_data(data)
        except Exception as exc:
            log.warning("cannot apply preset %r", name, exc_info=True)
            messagebox.showerror(t("dlg_load_error"), str(exc), parent=self)
            self._refresh_preset_combo()
            return
        self._set_last_preset_name(name)
        self._mark_clean(name)
    def _delete_current_preset(self):
        """Delete the preset currently loaded, or the one picked in the combo."""
        name = self._preset_name_var.get().strip()
        if not name or name == t("no_preset"):
            name = self._preset_combo_var.get().strip()
        if not name or name.startswith("—") or name == t("no_preset"):
            return
        if not messagebox.askyesno(t("dlg_delete"),
                t("delete_preset_confirm", name=name), parent=self):
            return
        if not self._presets.exists(name):
            messagebox.showerror(t("dlg_not_found"),
                          t("dlg_file_missing2", path=self._presets.path_for(name)),
                          parent=self)
            self._refresh_preset_combo()
            return
        if not self._presets.delete(name):
            messagebox.showerror(t("dlg_delete_error"),
                          str(self._presets.path_for(name)), parent=self)
            return
        if self._preset_name_var.get().strip() == name:
            self._preset_dirty = False
            tr_var(self._preset_name_var, "no_preset")
            self._set_last_preset_name("")
            if hasattr(self, "_preset_dirty_lbl"):
                self._preset_dirty_lbl.config(text="")
        self._refresh_preset_combo()
    def _load_last_preset(self):
        """Reopen the preset that was loaded when the app last closed."""
        name = self._get_last_preset_name()
        data = self._presets.load(name) if name else None
        if data is None:
            self._refresh_preset_combo()
            return
        try:
            self._apply_preset_data(data)
            self._mark_clean(name)
        except Exception:
            log.warning("cannot restore preset %r", name, exc_info=True)
            self._refresh_preset_combo()
    def _new_preset(self):
        """Clear the canvas so the user can start a new preset."""
        if self._preset_dirty:
            cur = self._preset_name_var.get().strip()
            label = f'"{cur}"' if cur and cur != t("no_preset") else t("current_preset")
            rep = messagebox.askyesnocancel(
                t("new_preset"),
                t("save_before_new", label=label),
                parent=self)
            if rep is None:
                return
            if rep:
                self._save_preset()
        self._canvas.delete("all")
        self._nodes.clear()
        self._connections.clear()
        self._selected_nodes.clear()
        self._next_id = 1
        self._draw_grid()
        self._redraw_wires()
        self._preset_dirty = False
        tr_var(self._preset_name_var, "no_preset")
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="")
        self._refresh_preset_combo()
        self._update_status()

    def _clear_all(self):
        self._canvas.delete("all"); self._nodes.clear(); self._connections.clear()
        self._selected_nodes.clear(); self._wire_src = None; self._wire_tmp = None
        self._rubber_rect = None
        self._draw_grid()
        if self._hint: self._hint.place(relx=0.5, rely=0.5, anchor="center")
        self._prev_tree.delete(*self._prev_tree.get_children())
        tr(self._chain_lbl, "chain_click")
        self._last_tree = None; self._update_status()
    def _redraw_wires(self):
        for c in self._connections:
            self._canvas.delete(c.get("cid"))
        for c in self._connections:
            c["cid"] = self._draw_wire_conn(c)
        self._canvas.tag_lower("grid")


    def _draw_wire_conn(self, conn):
        sn = self._nodes.get(conn["src"]); dn = self._nodes.get(conn["dst"])
        if not sn or not dn: return None
        ct = conn["ctype"]
        if ct == "name_in":
            x1, y1 = sn.port_out_pos(); x2, y2 = dn.port_name_in_pos()
            col = COLOR_LIANT
        else:  # "chain"
            x1, y1 = sn.port_out_pos(); x2, y2 = dn.port_in_pos()
            col = sn.color
        cx = (x1 + x2) / 2
        cid = self._canvas.create_line(x1, y1, cx, y1, cx, y2, x2, y2,
            fill=col, width=2, smooth=True, splinesteps=32, tags="wire")
        self._canvas.tag_bind(cid, "<ButtonPress-1>",
            lambda e, c=conn: self._cut_wire(c))
        self._canvas.tag_bind(cid, "<Enter>",
            lambda e, cid2=cid: self._canvas.itemconfig(cid2, width=4, fill="#ff4444"))
        self._canvas.tag_bind(cid, "<Leave>",
            lambda e, cid2=cid, col2=col: self._canvas.itemconfig(cid2, width=2, fill=col2))
        return cid


    def _cut_wire(self, conn):
        self._canvas.delete(conn.get("cid"))
        self._connections = [c for c in self._connections
                             if not (c["src"] == conn["src"] and c["dst"] == conn["dst"]
                                     and c["ctype"] == conn["ctype"])]
        self._update_status()
    def _bind_canvas_events(self):
        c = self._canvas
        c.bind("<ButtonPress-1>",          self._on_press)
        c.bind("<B1-Motion>",              self._on_drag)
        c.bind("<ButtonRelease-1>",         self._on_release)
        c.bind("<ButtonPress-3>",          self._on_pan_start)
        c.bind("<B3-Motion>",              self._on_pan)
        c.bind("<ButtonRelease-3>",         lambda e: setattr(self, "_pan_start", None))
        c.bind("<ButtonPress-2>",          self._on_pan_start)
        c.bind("<B2-Motion>",              self._on_pan)
        c.bind("<ButtonRelease-2>",         lambda e: setattr(self, "_pan_start", None))
        c.bind("<Shift-ButtonPress-1>",    self._on_shift_pan_start)
        c.bind("<Shift-B1-Motion>",        self._on_shift_pan)
        c.bind("<Shift-ButtonRelease-1>",  self._on_shift_pan_end)
        c.bind("<MouseWheel>",             self._on_canvas_wheel)
        c.bind("<Button-4>",               lambda e: self._canvas_zoom_step(e, 1.1))
        c.bind("<Button-5>",               lambda e: self._canvas_zoom_step(e, 0.9))
        c.bind("<Double-Button-1>",         self._on_double_click)
        c.bind("<Delete>",                 lambda e: self._delete_selected())
        c.bind("<BackSpace>",              lambda e: self._delete_selected())
        c.bind("<FocusIn>",                lambda e: None)
        c.config(takefocus=True)
        c.bind("<ButtonPress-1>",          self._on_press, add="+")

    def _find_node_at(self, mx, my):
        for nid, n in reversed(list(self._nodes.items())):
            if n.hit_test(mx, my): return nid
        return None

    def _on_press(self, event):
        mx, my = event.x, event.y
        ctrl   = (event.state & 0x0004) != 0
        self._canvas.focus_set()
        for nid, n in self._nodes.items():
            if n.hit_port_name_in(mx, my):
                self._wire_src = (nid, "name_in"); return
        for nid, n in self._nodes.items():
            if n.hit_port_out(mx, my):
                self._wire_src = (nid, "chain"); return
        for nid, n in list(self._nodes.items()):
            if n.hit_delete(mx, my):
                self._delete_node(nid); return

        nid = self._find_node_at(mx, my)

        if nid is not None:
            if ctrl:
                if nid in self._selected_nodes:
                    self._selected_nodes.discard(nid)
                    self._nodes[nid].set_selected(False)
                else:
                    self._selected_nodes.add(nid)
                    self._nodes[nid].set_selected(True)
            else:
                if nid not in self._selected_nodes:
                    for sid in self._selected_nodes:
                        if sid in self._nodes: self._nodes[sid].set_selected(False)
                    self._selected_nodes = {nid}
                    self._nodes[nid].set_selected(True)
            self._drag_node   = nid
            self._drag_offset = (mx - self._nodes[nid].x, my - self._nodes[nid].y)
            for sid in self._selected_nodes:
                if sid in self._nodes:
                    for cid in self._nodes[sid].canvas_ids:
                        self._canvas.tag_raise(cid)
        else:
            if not ctrl:
                for sid in self._selected_nodes:
                    if sid in self._nodes: self._nodes[sid].set_selected(False)
                self._selected_nodes.clear()
            self._rubber_start = (mx, my)


    def _on_drag(self, event):
        mx, my = event.x, event.y
        if self._wire_src is not None:
            if self._wire_tmp: self._canvas.delete(self._wire_tmp)
            src_nid, ptype = self._wire_src
            sn = self._nodes.get(src_nid)
            if sn:
                if ptype == "chain":
                    x1, y1 = sn.port_out_pos(); col = sn.color
                else:
                    x1, y1 = sn.port_out_pos()  # compat; col = ORANGE
                cx = (x1 + mx) / 2
                self._wire_tmp = self._canvas.create_line(
                    x1, y1, cx, y1, cx, my, mx, my,
                    fill=col, width=2, dash=(6,3), smooth=True,
                    splinesteps=32, tags="wire_tmp")
            return
        if self._rubber_start is not None and self._drag_node is None:
            if self._rubber_rect: self._canvas.delete(self._rubber_rect)
            rx, ry = self._rubber_start
            self._rubber_rect = self._canvas.create_rectangle(
                rx, ry, mx, my,
                outline=PRIMARY, fill=PRIMARY, stipple="gray25", tags="rubber")
            return
        if self._drag_node is not None and self._drag_node in self._nodes:
            dn = self._nodes[self._drag_node]
            base_dx = mx - self._drag_offset[0] - dn.x
            base_dy = my - self._drag_offset[1] - dn.y
            for sid in self._selected_nodes:
                if sid in self._nodes:
                    self._nodes[sid].move(base_dx, base_dy)
            self._redraw_wires()

    def _on_release(self, event):
        mx, my = event.x, event.y

        if self._wire_src is not None:
            src_nid, ptype = self._wire_src
            src_n = self._nodes.get(src_nid)
            for nid, n in self._nodes.items():
                if nid == src_nid: continue

                if ptype == "chain":
                    if n.hit_port_in(mx, my):
                        if src_n and src_n.node_family in ("argument", "liant") and n.node_family == "folder":
                            messagebox.showwarning(t("dlg_invalid_conn"),
                                                   t("wrong_port_msg"), parent=self)
                            break
                        conn = {"src": src_nid, "dst": nid, "ctype": "chain", "cid": None}
                        if not any(c["src"] == src_nid and c["dst"] == nid and c["ctype"] == "chain"
                                   for c in self._connections):
                            self._connections.append(conn)
                        self._redraw_wires(); break
                    elif n.hit_port_name_in(mx, my):
                        if not src_n or src_n.node_family not in ("argument", "liant"):
                            messagebox.showwarning(t("dlg_invalid_conn"),
                                                   t("only_arg_liant_name"), parent=self)
                            break
                        conn = {"src": src_nid, "dst": nid, "ctype": "name_in", "cid": None}
                        if not any(c["ctype"] == "name_in" and c["dst"] == nid
                                   for c in self._connections):
                            self._connections.append(conn)
                        self._redraw_wires(); break

                elif ptype == "name_in" and n.hit_port_out(mx, my):
                    if n.node_family not in ("argument", "liant"):
                        break
                    conn = {"src": nid, "dst": src_nid, "ctype": "name_in", "cid": None}
                    if not any(c["ctype"] == "name_in" and c["dst"] == src_nid
                               for c in self._connections):
                        self._connections.append(conn)
                    self._redraw_wires(); break

            if self._wire_tmp:
                self._canvas.delete(self._wire_tmp); self._wire_tmp = None
            self._wire_src = None

        if self._rubber_rect:
            self._canvas.delete(self._rubber_rect); self._rubber_rect = None
        if self._rubber_start is not None:
            rx0, ry0 = self._rubber_start; rx1, ry1 = mx, my
            x0, x1 = min(rx0, rx1), max(rx0, rx1)
            y0, y1 = min(ry0, ry1), max(ry0, ry1)
            for nid, n in self._nodes.items():
                cx, cy = n.x + n.NW // 2, n.y + n.NH // 2
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    self._selected_nodes.add(nid)
                    n.set_selected(True)
            self._rubber_start = None

        self._drag_node = None
        self._update_status()
        cur = self._preset_name_var.get() if hasattr(self, "_preset_name_var") else ""
        if cur and cur != t("no_preset") and not self._preset_dirty:
            self._mark_dirty()


    def _on_pan_start(self, event): self._pan_start = (event.x, event.y)

    def _on_pan(self, event):
        if self._pan_start:
            dx = event.x - self._pan_start[0]; dy = event.y - self._pan_start[1]
            self._pan_start = (event.x, event.y)
            for n in self._nodes.values(): n.move(dx, dy)
            self._redraw_wires()

    def _on_shift_pan_start(self, event):
        self._shift_pan_start = (event.x, event.y)
        self._canvas.config(cursor="fleur")

    def _on_shift_pan(self, event):
        if self._shift_pan_start:
            dx = event.x - self._shift_pan_start[0]
            dy = event.y - self._shift_pan_start[1]
            self._shift_pan_start = (event.x, event.y)
            for n in self._nodes.values(): n.move(dx, dy)
            self._redraw_wires()

    def _on_shift_pan_end(self, event):
        self._shift_pan_start = None
        self._canvas.config(cursor="crosshair")

    def _on_canvas_wheel(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self._canvas_zoom_step(event, factor)

    def _canvas_zoom_step(self, event, factor):
        MIN_ZOOM, MAX_ZOOM = 0.2, 4.0
        new_zoom = max(MIN_ZOOM, min(self._canvas_zoom * factor, MAX_ZOOM))
        if new_zoom == self._canvas_zoom:
            return
        real_factor = new_zoom / self._canvas_zoom
        self._canvas_zoom = new_zoom
        cx, cy = event.x, event.y
        for n in self._nodes.values():
            new_x = cx + (n.x - cx) * real_factor
            new_y = cy + (n.y - cy) * real_factor
            n.move(new_x - n.x, new_y - n.y)
        Node.NW = max(100, min(300, int(200 * self._canvas_zoom)))
        Node.NH = max(45,  min(160, int(90  * self._canvas_zoom)))
        for n in self._nodes.values():
            n.draw()
        self._redraw_wires()
        self._draw_grid()
        set_raw(self._status, t("status_zoom", pct=int(self._canvas_zoom * 100)))

    def _on_double_click(self, event):
        nid = self._find_node_at(event.x, event.y)
        if nid is None: return
        n = self._nodes[nid]
        if n.node_family == "folder":
            self._open_rename_dialog(nid)
        elif n.node_family == "liant":
            self._open_liant_dialog(nid)
        elif n.node_family == "argument":
            self._open_separator_dialog(nid)

    def _open_rename_dialog(self, nid):
        if self._rename_win and self._rename_win.winfo_exists():
            self._rename_win.destroy()
        n = self._nodes[nid]
        win = tk.Toplevel(self); self._rename_win = win
        win.title(t("rename_folder_title")); win.configure(bg=SURFACE)
        win.resizable(False, False); win.geometry("320x120"); win.transient(self)
        tr(tk.Label(win, bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 10)), "folder_name_lbl").pack(padx=20, pady=(16,4), anchor="w")
        var = tk.StringVar(value=n.label)
        entry = tk.Entry(win, textvariable=var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        entry.pack(fill="x", padx=20, ipady=6); entry.select_range(0, "end"); entry.focus_set()
        def confirm(*_):
            v = var.get().strip()
            if v:
                self._mark_dirty()
                n.label = v
                n.label_is_default = False  # the user named this folder
            win.destroy()
        entry.bind("<Return>", confirm)
        tr(tk.Button(win, bg=PRIMARY, fg="#0f3638", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=20, pady=4,
                  cursor="hand2", command=confirm), "ok").pack(pady=10)

    def _open_liant_dialog(self, nid):
        """Dialog for editing the free text of a connector node."""
        if self._rename_win and self._rename_win.winfo_exists():
            self._rename_win.destroy()
        n = self._nodes[nid]
        win = tk.Toplevel(self); self._rename_win = win
        win.title(t("edit_liant_title")); win.configure(bg=SURFACE)
        win.resizable(False, False); win.geometry("340x160"); win.transient(self)
        tr(tk.Label(win, bg=SURFACE, fg=COLOR_LIANT,
                 font=("Segoe UI", 10, "bold")), "connector_text").pack(padx=20, pady=(16,2), anchor="w")
        tr(tk.Label(win,
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)), "connector_ex").pack(padx=20, anchor="w")
        presets_frame = tk.Frame(win, bg=SURFACE); presets_frame.pack(padx=20, pady=4, anchor="w")
        var = tk.StringVar(value=n.label)
        for lbl, val in [("-","-"),("_","_"),(" "," "),(".",".")]:
            tk.Button(presets_frame, text=repr(lbl), bg=SURFACE2, fg=COLOR_LIANT,
                      relief="flat", font=("Segoe UI", 8), padx=8, pady=2, cursor="hand2",
                      command=lambda v=val: var.set(v)).pack(side="left", padx=2)
        entry = tk.Entry(win, textvariable=var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 13))
        entry.pack(fill="x", padx=20, ipady=6)
        entry.select_range(0, "end"); entry.focus_set()
        def confirm(*_):
            v = var.get()
            self._mark_dirty(); n.label = v if v else "-"
            win.destroy()
        entry.bind("<Return>", confirm)
        tr(tk.Button(win, bg=COLOR_LIANT, fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=20, pady=4,
                  cursor="hand2", command=confirm), "ok").pack(pady=8)

    def _open_separator_dialog(self, nid):
        """Dialog for choosing the separator appended after an argument node."""
        if self._rename_win and self._rename_win.winfo_exists():
            self._rename_win.destroy()
        n = self._nodes[nid]
        win = tk.Toplevel(self); self._rename_win = win
        win.title(t("separator_title")); win.configure(bg=BG)
        win.resizable(False, False); win.transient(self)

        tk.Label(win, text=f"📌  {n.display_label}", bg=BG, fg=n.color,
                 font=("Segoe UI", 11, "bold"), pady=10, padx=16).pack(anchor="w")
        tr(tk.Label(win,

            bg=BG, fg=MUTED, font=("Segoe UI", 8), justify="left", padx=16), "separator_hint").pack(anchor="w")
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", pady=6)

        sep_var = tk.StringVar(value=n.separator)
        presets = [(t("sep_none"), ""), (t("sep_dash"), "-"), ("Underscore _", "_"),
                   (t("sep_space"), " "), (t("sep_dot"), ".")]
        tr(tk.Label(win, bg=BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold"), padx=16), "presets_lbl").pack(anchor="w")
        btn_row = tk.Frame(win, bg=BG); btn_row.pack(fill="x", padx=16, pady=4)
        for lbl, val in presets:
            tk.Button(btn_row, text=lbl, bg=SURFACE2, fg=TEXT, relief="flat",
                      font=("Segoe UI", 8), padx=8, pady=4, cursor="hand2",
                      command=lambda v=val: sep_var.set(v)).pack(side="left", padx=2)

        tr(tk.Label(win, bg=BG, fg=TEXT,
                 font=("Segoe UI", 9), padx=16), "custom_lbl").pack(anchor="w", pady=(8,2))
        ent_row = tk.Frame(win, bg=BG); ent_row.pack(fill="x", padx=16, pady=(0,8))
        entry = tk.Entry(ent_row, textvariable=sep_var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat",
                         font=("Segoe UI", 12), width=8)
        entry.pack(side="left", ipady=5)

        prev_frame = tk.Frame(win, bg=SURFACE, pady=6); prev_frame.pack(fill="x")
        prev_lbl = tk.Label(prev_frame, text="", bg=SURFACE, fg=PRIMARY,
                            font=("Segoe UI", 9, "bold"), padx=16)
        prev_lbl.pack(anchor="w")
        _examples = {
            "exif_annee":"2026", "exif_mois":"04", "exif_jour":"26",
            "exif_date_full":"2026-04-26", "annee_creation":"2026", "mois_creation":"04",
            "jour_creation":"26", "annee_modif":"2026", "mois_modif":"04", "jour_modif":"26",
            "nom_fichier":"DSC_0042", "extension":"JPG", "categorie":"Images", "taille":"1 Mo - 10 Mo",
        }
        def update_prev(*_):
            sep = sep_var.get()
            ex  = _examples.get(n.field, "valeur")
            tr(prev_lbl, "connector_preview", ex=ex, sep=sep)
        sep_var.trace_add("write", update_prev); update_prev()

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", pady=4)
        btn_f = tk.Frame(win, bg=BG); btn_f.pack(fill="x", padx=16, pady=(4,12))
        def apply():
            self._mark_dirty(); n.separator = sep_var.get()
            n.draw(); self._redraw_wires(); win.destroy()
        tr(tk.Button(btn_f, bg=SURFACE2, fg=MUTED, relief="flat",
                  font=("Segoe UI", 9), padx=10, pady=5, cursor="hand2",
                  command=win.destroy), "cancel").pack(side="right", padx=(6,0))
        tr(tk.Button(btn_f, bg=PRIMARY, fg="#0f3638", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=5, cursor="hand2",
                  command=apply), "apply_btn").pack(side="right")
        win.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width()//2 - win.winfo_width()//2
        py = self.winfo_rooty() + self.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{px}+{py}")
    def _update_status(self):
        folders  = sum(1 for n in self._nodes.values() if n.node_family == "folder")
        metadata = sum(1 for n in self._nodes.values() if n.node_family == "argument")
        nc       = len(self._connections)
        nsel     = len(self._selected_nodes)
        sel_txt  = t("node_sel_status", n=nsel) if nsel else ""
        set_raw(self._status,
                t("node_count_status", n=len(self._nodes), f=folders, m=metadata)
                + t("node_conn_status", nc=nc, sel=sel_txt))
    def _resolve_chain(self):
        """Return the ordered node ids of the main chain.

        Argument and connector nodes wired into a folder's NAME port belong to
        that folder's name, not to the chain, so they are excluded here.
        """
        if not self._nodes: return []
        name_chain_nodes = set()
        direct_name_srcs = set(c["src"] for c in self._connections if c["ctype"] == "name_in"
                               and c["src"] in self._nodes)
        arg_liant_chain = [c for c in self._connections if c["ctype"] == "chain"
                           and c["src"] in self._nodes and c["dst"] in self._nodes
                           and self._nodes[c["src"]].node_family in ("argument", "liant")
                           and self._nodes[c["dst"]].node_family in ("argument", "liant")]
        al_in_e = {nid: [] for nid in self._nodes}
        for c in arg_liant_chain:
            al_in_e[c["dst"]].append(c["src"])

        def collect_name_chain(nid):
            if nid in name_chain_nodes: return
            if nid not in self._nodes: return
            if self._nodes[nid].node_family not in ("argument", "liant"): return
            name_chain_nodes.add(nid)
            for src in al_in_e.get(nid, []):
                collect_name_chain(src)

        for s in direct_name_srcs:
            collect_name_chain(s)
        chain_conns = [c for c in self._connections if c["ctype"] == "chain"
                       and c["src"] in self._nodes and c["dst"] in self._nodes
                       and c["src"] not in name_chain_nodes
                       and c["dst"] not in name_chain_nodes]

        out_e = {nid: [] for nid in self._nodes}
        in_e  = {nid: [] for nid in self._nodes}
        for c in chain_conns:
            out_e[c["src"]].append(c["dst"])
            in_e[c["dst"]].append(c["src"])
        valid_nodes = [nid for nid in self._nodes if nid not in name_chain_nodes]
        if not valid_nodes: return []

        roots = [nid for nid in valid_nodes if not in_e[nid]]
        if not roots: roots = [valid_nodes[0]]

        visited = []
        def walk(nid):
            if nid in visited or nid in name_chain_nodes: return
            visited.append(nid)
            for dst in out_e.get(nid, []):
                walk(dst)
        for r in roots:
            walk(r)
        return visited


    def _get_name_chain_for_folder(self, folder_nid):
        """
        Return the ORDERED node ids wired into the folder's NAME port,
        following the chain links between those nodes.
        """
        name_in_srcs = [c["src"] for c in self._connections
                        if c["ctype"] == "name_in" and c["dst"] == folder_nid
                        and c["src"] in self._nodes]
        if not name_in_srcs: return []
        chain_conns = [c for c in self._connections if c["ctype"] == "chain"
                       and c["src"] in self._nodes and c["dst"] in self._nodes
                       and self._nodes[c["src"]].node_family in ("argument","liant")
                       and self._nodes[c["dst"]].node_family in ("argument","liant")]
        out_e = {nid: [] for nid in self._nodes}
        in_e  = {nid: [] for nid in self._nodes}
        for c in chain_conns:
            out_e[c["src"]].append(c["dst"]); in_e[c["dst"]].append(c["src"])
        all_in_chain = set()
        def collect_back(nid):
            if nid in all_in_chain: return
            if nid not in self._nodes: return
            if self._nodes[nid].node_family not in ("argument","liant"): return
            all_in_chain.add(nid)
            for src in in_e.get(nid, []): collect_back(src)
        for s in name_in_srcs: collect_back(s)
        roots = [n for n in all_in_chain if not any(s in all_in_chain for s in in_e.get(n, []))]
        if not roots: roots = list(name_in_srcs[:1])
        chain = []
        def walk_fwd(nid):
            if nid not in all_in_chain or nid in chain: return
            chain.append(nid)
            for dst in out_e.get(nid, []):
                if dst in all_in_chain: walk_fwd(dst)
        for r in roots: walk_fwd(r)
        return chain

    def get_structure(self):
        """Expose the resolved tree to the Organize tab."""
        files = self._get_files()
        if not files: return None
        return self.get_structure_for_files(files)

    def _chain_tokens(self):
        """Return ``(tokens, labels)`` for the current node chain, or ``None``.

        Both the preview and the Organize tab need this; they used to build it
        twice, with two slightly different copies of the same loop.
        """
        chain = self._resolve_chain()
        if not chain:
            return None
        tokens, labels = [], []
        for nid in chain:
            node = self._nodes[nid]
            if node.node_family == "argument":
                tokens.append(arg_token(node.field, node.separator))
                hint = f" [{node.separator!r}]" if node.separator else ""
                labels.append(node.display_label + hint)
            elif node.node_family == "folder":
                name_chain = self._get_name_chain_for_folder(nid)
                if name_chain:
                    parts = []
                    for aid in name_chain:
                        source = self._nodes[aid]
                        if source.node_family == "argument":
                            parts.append(dyn_arg_part(source.field, source.separator))
                        elif source.node_family == "liant":
                            parts.append(dyn_literal_part(source.label))
                    tokens.append(dyn_folder_token(parts))
                else:
                    tokens.append(folder_token(node.label))
                labels.append(f"📁 {node.display_label}")
        return (tokens, labels) if tokens else None

    def get_structure_for_files(self, files, progress_cb=None):
        """Build the folder tree for *files*, or None when nothing is wired up."""
        if not files:
            return None
        chain = self._chain_tokens()
        if not chain:
            return None
        tokens, labels = chain
        return build_tree(files, tokens, progress=progress_cb), labels, files

    def _update_nodal_prog_bar(self, *_):
        pct = self._nodal_prog_var.get() / 100.0
        self._nodal_prog_inner.place(x=0, y=0, relwidth=pct, height=4)
        if pct >= 1.0:
            self.after(600, lambda: self._nodal_prog_inner.place(
                x=0, y=0, relwidth=0.0, height=4))

    def _show_preview(self):
        files = self._get_files()
        if not files:
            messagebox.showinfo(t("apercu_title"), t("no_files_preview"), parent=self)
            return
        chain = self._chain_tokens()
        if chain is None:
            messagebox.showinfo(t("apercu_title"), t("no_nodes_canvas"), parent=self)
            return
        tokens, labels = chain
        if not tokens:
            messagebox.showinfo(t("apercu_title"), t("no_usable_node"), parent=self)
            return

        label_str = " → ".join(labels)
        n_files = len(files)
        tr(self._chain_lbl, "chain_computing", n=n_files)
        tr_var(self._status, "computing_progress", d=0, t=n_files, p=0)
        self._nodal_prog_var.set(0)

        def report(done, total):
            pct = int(done / total * 100) if total else 0
            self.after(0, lambda: (
                tr_var(self._status, "computing_progress", d=done, t=total, p=pct),
                self._nodal_prog_var.set(pct),
            ))

        def compute():
            try:
                tree = build_tree(files, tokens, progress=report)
            except Exception as exc:
                log.warning("structure computation failed", exc_info=True)
                self.after(0, lambda e=exc: (
                    tr_var(self._status, "err_compute", msg=str(e)),
                    tr(self._chain_lbl, "chain_error", msg=str(e)),
                ))
                return
            self.after(0, lambda: self._apply_preview(tree, labels, label_str, n_files))

        threading.Thread(target=compute, daemon=True).start()

    def _apply_preview(self, tree, labels, label_str, n_files):
        self._nodal_prog_var.set(100)  # termine la barre
        self._last_tree   = tree
        self._last_labels = labels
        tr(self._chain_lbl, "chain_result", label=label_str, n=n_files)
        self._prev_tree.delete(*self._prev_tree.get_children())
        self._populate_preview("", tree, 0)
        tr_var(self._status, "preview_ready", n=n_files, label=label_str)

    def _populate_preview(self, parent_iid, tree, depth):
        if isinstance(tree, list): return
        for key, val in sorted(tree.items()):
            if isinstance(val, list):
                self._prev_tree.insert(parent_iid, "end", text=f"  {key}",
                                       values=(len(val),), open=(depth == 0))
            else:
                total = count_files(val)
                iid   = self._prev_tree.insert(parent_iid, "end", text=f"  {key}",
                                               values=(total,), open=(depth == 0))
                self._populate_preview(iid, val, depth+1)


    def refresh_lang(self):
        """Re-render what a plain text binding cannot reach.

        Every label and button here is bound with ``tr()``, so the i18n
        registry has already refreshed them by the time this runs. What is left
        is the tree headings, the palette (its buttons are rebuilt from the
        field registry) and the nodes drawn on the canvas.
        """
        try:
            self._prev_tree.heading("#0", text=t("folder_node"))
            self._prev_tree.heading("count", text=t("col_count"))
        except tk.TclError:
            log.debug("preview tree gone", exc_info=True)
        self._build_palette_meta()
        self._update_status()
        for node in list(self._nodes.values()):
            try:
                node.draw()
            except tk.TclError:
                log.debug("node %r gone", node.id, exc_info=True)
