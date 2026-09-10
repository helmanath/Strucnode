"""The Organize tab: load a structure, review the plan, run it."""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from collections import defaultdict
from tkinter import filedialog, messagebox, ttk

from ..core import executor
from ..core.categories import fmt_size, get_category
from ..core.planner import build_plan, destination_is_inside, free_space
from ..i18n import set_raw, t, tr, tr_var
from ..theme import (
    BG,
    BLUE,
    BORDER,
    BORDER_SOFT,
    EXTENSION_COLORS,
    MUTED,
    ON_ACCENT,
    ORANGE,
    PRIMARY,
    PURPLE,
    SIZE_BODY,
    SIZE_H2,
    SIZE_MICRO,
    SIZE_SMALL,
    SP_M,
    SP_S,
    SP_XS,
    SUCCESS,
    SURFACE,
    SURFACE2,
    SURFACE3,
    TEXT,
    TEXT_DIM,
    Tooltip,
    button,
    font,
    hover,
)

log = logging.getLogger(__name__)


class OrganizeTab(tk.Frame):

    def __init__(self, parent, get_nodal_editor_cb):
        super().__init__(parent, bg=BG)
        self._get_editor = get_nodal_editor_cb
        self._plan = None
        self._ops = []
        self._tree = None
        self._full_tree = None        # full tree, before the extension filter
        self._all_files_ref = []      # every indexed file, before the filter
        self._op_mode = tk.StringVar(value=executor.COPY)
        self._dest_var = tk.StringVar(value="")
        self._ext_filter_vars = {}    # {extension: BooleanVar}
        self._cancel = threading.Event()
        self._build_ui()

    def _build_ui(self):
        tb = tk.Frame(self, bg=SURFACE, pady=SP_M, padx=SP_M + SP_S)
        tb.pack(fill="x")
        tk.Frame(self, bg=BORDER_SOFT, height=1).pack(fill="x")
        self._lbl_org_title = tr(tk.Label(tb, bg=SURFACE, fg=PRIMARY,
                 font=font(SIZE_H2, "bold")), "organize_title")
        self._lbl_org_title.pack(side="left")
        self._lbl_org_hint = tr(tk.Label(tb, bg=SURFACE, fg=MUTED,
                 font=font(SIZE_MICRO)), "organize_hint")
        self._lbl_org_hint.pack(side="left", padx=(SP_M + 2, 0))

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=10)
        left_outer = tk.Frame(main, bg=SURFACE, width=360)
        left_outer.pack(side="left", fill="y", padx=(0,12))
        left_outer.pack_propagate(False)

        _lc = tk.Canvas(left_outer, bg=SURFACE, highlightthickness=0, bd=0)
        _lvsb = ttk.Scrollbar(left_outer, orient="vertical", command=_lc.yview,
                               style="Dark.Vertical.TScrollbar")
        _lc.pack(side="left", fill="both", expand=True)
        _lc.configure(yscrollcommand=_lvsb.set)

        left = tk.Frame(_lc, bg=SURFACE)
        _lw = _lc.create_window((0, 0), window=left, anchor="nw")

        def _left_update_scroll(e=None):
            _lc.configure(scrollregion=_lc.bbox("all"))
            ch = _lc.winfo_height()
            if left.winfo_reqheight() > ch + 2:
                if not _lvsb.winfo_ismapped():
                    _lvsb.pack(side="right", fill="y", before=_lc)
            else:
                if _lvsb.winfo_ismapped():
                    _lvsb.pack_forget()
                    _lc.yview_moveto(0)

        left.bind("<Configure>", _left_update_scroll)
        _lc.bind("<Configure>", lambda e: (_lc.itemconfig(_lw, width=e.width),
                                            _left_update_scroll()))

        def _lscroll(e): _lc.yview_scroll(int(-1*(e.delta/120)), "units")
        _lc.bind("<MouseWheel>", _lscroll)
        left.bind("<MouseWheel>", _lscroll)

        #: Numbered, because the left rail is a sequence: pick a structure,
        #: then what to include, then what to do, then where. Without the
        #: numbers the four blocks read as four independent settings.
        self._section_index = 0

        def section(parent, key):
            """A numbered, titled block; the title stays bound to *key*."""
            self._section_index += 1
            f = tk.Frame(parent, bg=SURFACE)
            f.pack(fill="x", padx=SP_M + SP_S, pady=(SP_M + SP_S, 0))
            f.bind("<MouseWheel>", _lscroll)
            head = tk.Frame(f, bg=SURFACE)
            head.pack(fill="x")
            tk.Label(head, text=str(self._section_index), bg=SURFACE2, fg=PRIMARY,
                     font=font(SIZE_MICRO, "bold"), width=2,
                     pady=1).pack(side="left", padx=(0, SP_M))
            tr(tk.Label(head, bg=SURFACE, fg=MUTED,
                        font=font(SIZE_MICRO, "bold")), key).pack(side="left")
            tk.Frame(f, bg=BORDER_SOFT, height=1).pack(fill="x", pady=(SP_M, SP_S))
            return f
        self._s_struct = s1 = section(left, "nodal_structure")
        self._struct_lbl = tr(tk.Label(s1,

            bg=SURFACE, fg=MUTED, font=font(SIZE_MICRO), justify="left", wraplength=320), "no_structure")
        self._struct_lbl.pack(anchor="w", pady=4)
        self._load_btn = tr(button(s1, variant="ghost", size=SIZE_SMALL,
                  fg=PRIMARY, padx=SP_M, pady=SP_M,
                  command=self._load_structure), "load_structure")
        self._load_btn.pack(fill="x", pady=(SP_S, 0))
        Tooltip(self._load_btn, lambda: t("tip_load_structure"))
        self._s_ext = s_ext = section(left, "sect_ext")
        self._ext_filter_frame = tk.Frame(s_ext, bg=SURFACE)
        self._ext_filter_frame.pack(fill="x", pady=(2,0))
        self._ext_filter_empty_lbl = self._lbl_load_ext = tr(tk.Label(s_ext,

            bg=SURFACE, fg=MUTED, font=font(SIZE_MICRO), justify="left", wraplength=320), "load_ext_hint")
        self._ext_filter_empty_lbl.pack(anchor="w", pady=4)
        ext_btn_row = tk.Frame(s_ext, bg=SURFACE)
        ext_btn_row.pack(fill="x", pady=(4,0))
        self._btn_check_all = tr(button(ext_btn_row, variant="ghost",
                  size=SIZE_MICRO, fg=SUCCESS, padx=SP_M, pady=SP_S,
                  command=lambda: self._select_all_exts(True)), "check_all")
        self._btn_check_all.pack(side="left", padx=(0, SP_S))
        self._btn_check_none = tr(button(ext_btn_row, variant="ghost",
                  size=SIZE_MICRO, fg=MUTED, padx=SP_M, pady=SP_S,
                  command=lambda: self._select_all_exts(False)), "check_none")
        self._btn_check_none.pack(side="left")
        s2 = section(left, "op_section"); self._s_op_section = s2
        for val, key, col in [
            (executor.COPY, "sect_mode_copy", SUCCESS),
            (executor.MOVE, "sect_mode_move", ORANGE),
        ]:
            rb = tr(tk.Radiobutton(s2, variable=self._op_mode, value=val,
                              bg=SURFACE, fg=col, selectcolor=SURFACE2,
                              activebackground=SURFACE, activeforeground=col,
                              font=font(SIZE_SMALL), highlightthickness=0,
                              bd=0, cursor="hand2",
                              command=self._update_summary), key)
            rb.pack(anchor="w", pady=SP_XS)
            hover(rb, SURFACE, SURFACE2)
        self._s_dup = section(left, "dup_section")
        self._dup_mode = tk.StringVar(value=executor.ASK)
        for val, key, col in [
            (executor.ASK, "dup_ask", TEXT),
            (executor.SKIP, "dup_skip", MUTED),
            (executor.REPLACE, "dup_replace_auto", ORANGE),
            (executor.RENAME, "dup_rename_auto", PRIMARY),
            (executor.COMPARE_META, "dup_meta", BLUE),
            (executor.COMPARE_FULL, "dup_full_cmp", PURPLE),
        ]:
            rb = tr(tk.Radiobutton(self._s_dup, variable=self._dup_mode, value=val,
                              bg=SURFACE, fg=col, selectcolor=SURFACE2,
                              activebackground=SURFACE, activeforeground=col,
                              font=font(SIZE_SMALL), highlightthickness=0,
                              bd=0, cursor="hand2"), key)
            rb.pack(anchor="w", pady=1)
            hover(rb, SURFACE, SURFACE2)
        s3 = section(left, "sect_dest"); self._s_dest = s3
        dr = tk.Frame(s3, bg=SURFACE); dr.pack(fill="x")
        dest_entry = tk.Entry(dr, textvariable=self._dest_var, bg=SURFACE2,
                 fg=TEXT, insertbackground=PRIMARY, relief="flat",
                 highlightthickness=0, font=font(SIZE_SMALL))
        dest_entry.pack(side="left", fill="x", expand=True, ipady=SP_M)
        # Typing a destination has to arm the button just as browsing to one
        # does; before this, a hand-typed path left the button disabled.
        self._dest_var.trace_add("write", lambda *_: self._on_dest_typed())
        self._btn_browse = tr(button(dr, variant="ghost", size=SIZE_SMALL,
                  padx=SP_M, pady=SP_M,
                  command=self._pick_dest), "browse")
        self._btn_browse.pack(side="left", padx=(SP_M, 0))
        s4 = section(left, "summary_section"); self._s_summary_section = s4
        self._summary_lbl = tk.Label(s4, text="—", bg=SURFACE, fg=TEXT_DIM,
                                     font=font(SIZE_MICRO), justify="left",
                                     wraplength=320)
        self._summary_lbl.pack(anchor="w", pady=SP_S)
        s5 = tk.Frame(left, bg=SURFACE)
        s5.pack(fill="x", padx=SP_M + SP_S, pady=(SP_M * 2, SP_M + SP_S))

        btn_row = tk.Frame(s5, bg=SURFACE)
        btn_row.pack(fill="x")
        self._run_btn = tr(button(btn_row, variant="primary", size=SIZE_BODY,
                                  bold=True, padx=SP_M + SP_S, pady=SP_M + 2,
                                  command=self._run, state="disabled"),
                           "apply_structure")
        self._run_btn.pack(side="left", fill="x", expand=True)
        self._stop_btn = button(btn_row, text="\u23f9", variant="danger",
                                size=SIZE_H2, bold=True,
                                padx=SP_M + 2, pady=SP_M + 2,
                                command=self._request_cancel)
        Tooltip(self._stop_btn, lambda: t("tip_stop"))
        # A greyed-out button that never says why is the most common way to
        # lose someone here, so the reason it is disabled is always on screen.
        self._blocked_lbl = tk.Label(s5, text="", bg=SURFACE, fg=ORANGE,
                                     font=font(SIZE_MICRO), justify="left",
                                     wraplength=320)
        self._blocked_lbl.pack(anchor="w", pady=(SP_M, 0))
        self._progress = ttk.Progressbar(s5, mode="determinate",
                                         style="Custom.Horizontal.TProgressbar")
        self._progress.pack(fill="x", pady=(SP_M, 0))
        self._prog_lbl = tk.Label(s5, text="", bg=SURFACE, fg=MUTED,
                                  font=font(SIZE_MICRO))
        self._prog_lbl.pack(anchor="w")
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(right, bg=SURFACE, pady=SP_M, padx=SP_M + SP_S)
        hdr.pack(fill="x")
        self._lbl_ops_preview = tr(tk.Label(hdr, bg=SURFACE, fg=MUTED,
                 font=font(SIZE_MICRO, "bold")), "ops_preview")
        self._lbl_ops_preview.pack(side="left")
        self._ops_count_lbl = tk.Label(hdr, text="", bg=SURFACE, fg=PRIMARY,
                                       font=font(SIZE_MICRO, "bold"))
        self._ops_count_lbl.pack(side="left", padx=SP_M + SP_S)
        self._nomatch_count_lbl = tk.Label(hdr, text="", bg=SURFACE, fg=ORANGE,
                                           font=font(SIZE_MICRO))
        self._nomatch_count_lbl.pack(side="left", padx=SP_S)
        style = ttk.Style()
        style.configure("Ops.TNotebook", background=BG, borderwidth=0, tabmargins=0)
        style.configure("Ops.TNotebook.Tab",
            background=SURFACE2, foreground=MUTED, borderwidth=0,
            font=font(SIZE_MICRO), padding=(SP_M + SP_S, SP_M))
        style.map("Ops.TNotebook.Tab",
            background=[("selected", BG), ("active", SURFACE3)],
            foreground=[("selected", PRIMARY), ("active", TEXT)])

        self._ops_notebook = ttk.Notebook(right, style="Ops.TNotebook")
        self._ops_notebook.pack(fill="both", expand=True)
        tab_all = tk.Frame(self._ops_notebook, bg=BG)
        self._ops_notebook.add(tab_all, text=t("tab_all_ops"))
        cols = ("src", "dst")
        tv_fr = tk.Frame(tab_all, bg=BG)
        tv_fr.pack(fill="both", expand=True)
        self._ops_tree = ttk.Treeview(tv_fr, columns=cols,
                                      show="headings", style="Custom.Treeview")
        self._ops_tree.heading("src", text=t("col_src"))
        self._ops_tree.heading("dst", text=t("col_dst"))
        self._ops_tree.column("src", width=300, anchor="w")
        self._ops_tree.column("dst", width=520, anchor="w")
        vsb = ttk.Scrollbar(tv_fr, orient="vertical",   command=self._ops_tree.yview, style="Dark.Vertical.TScrollbar")
        hsb = ttk.Scrollbar(tv_fr, orient="horizontal", command=self._ops_tree.xview, style="Dark.Horizontal.TScrollbar")
        self._ops_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x"); vsb.pack(side="right", fill="y")
        self._ops_tree.pack(fill="both", expand=True)
        tab_nm = tk.Frame(self._ops_notebook, bg=BG)
        self._ops_notebook.add(tab_nm, text=t("tab_unmatched"))
        nm_fr = tk.Frame(tab_nm, bg=BG)
        nm_fr.pack(fill="both", expand=True)
        self._nomatch_tree = ttk.Treeview(nm_fr, columns=("file", "reason"),
                                          show="headings", style="Custom.Treeview")
        self._nomatch_tree.heading("file",   text=t("col_file"))
        self._nomatch_tree.heading("reason", text=t("col_reason"))
        self._nomatch_tree.column("file",   width=300, anchor="w")
        self._nomatch_tree.column("reason", width=520, anchor="w")
        self._nomatch_tree.tag_configure("nm", foreground=ORANGE)
        vsb2 = ttk.Scrollbar(nm_fr, orient="vertical",   command=self._nomatch_tree.yview, style="Dark.Vertical.TScrollbar")
        hsb2 = ttk.Scrollbar(nm_fr, orient="horizontal", command=self._nomatch_tree.xview, style="Dark.Horizontal.TScrollbar")
        self._nomatch_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        hsb2.pack(side="bottom", fill="x"); vsb2.pack(side="right", fill="y")
        self._nomatch_tree.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value=t("start_status"))
        tk.Label(self, textvariable=self._status_var, bg=SURFACE, fg=TEXT_DIM,
                 font=font(SIZE_MICRO), anchor="w", padx=SP_M + SP_S,
                 pady=SP_S + 1).pack(fill="x", side="bottom")
        self._prog_bar_var = tk.IntVar(value=0)
        self._prog_bar_frame = tk.Frame(self, bg=SURFACE, height=4)
        self._prog_bar_frame.pack(fill="x", side="bottom")
        self._prog_bar_frame.pack_propagate(False)
        self._prog_bar_inner = tk.Frame(self._prog_bar_frame, bg=PRIMARY, height=4)
        self._prog_bar_inner.place(x=0, y=0, relwidth=0.0, height=4)
        self._prog_bar_var.trace_add("write", self._update_prog_bar)
    def _update_prog_bar(self, *_):
        pct = self._prog_bar_var.get() / 100.0
        self._prog_bar_inner.place(x=0, y=0, relwidth=pct, height=4)
        if pct >= 1.0:
            self.after(600, lambda: self._prog_bar_inner.place(
                x=0, y=0, relwidth=0.0, height=4))

    def _load_structure(self):
        """Pull the structure from the node editor and compute it for every file."""
        editor = self._get_editor()
        if editor is None:
            messagebox.showinfo(t("structure_info"), t("editor_not_ready"), parent=self)
            return
        raw = editor.get_structure()
        if raw is None:
            messagebox.showinfo(t("structure_info"), t("no_structure_msg"), parent=self)
            return

        _tree, labels, files = raw
        label_str = " → ".join(labels)
        tr_var(self._status_var, "chain_computing", n=len(files))
        tr(self._struct_lbl, "chain_computing", n=0)
        self._load_btn.config(state="disabled")
        self._all_files_ref = files

        def report(done, total):
            pct = int(done / total * 100) if total else 0
            self.after(0, lambda: (
                tr_var(self._status_var, "computing_progress", d=done, t=total, p=pct),
                self._prog_bar_var.set(pct),
            ))

        def worker():
            result = editor.get_structure_for_files(files, progress_cb=report)
            self.after(0, lambda: self._on_structure_ready(result, label_str, files))

        threading.Thread(target=worker, daemon=True).start()

    def _on_structure_ready(self, result, label_str, files):
        self._prog_bar_var.set(100)
        self._load_btn.config(state="normal")
        if result is None:
            tr_var(self._status_var, "chain_click")
            return
        tree, labels, result_files = result
        self._full_tree = tree
        self._tree      = tree
        tr(self._struct_lbl, "chain_result", label=label_str, n=len(files))
        self._build_ext_filter(files)
        dest = self._dest_var.get().strip()
        self._refresh_ops(tree, dest or "/destination/")
        self._update_summary()
        self._check_ready()
        tr_var(self._status_var, "chain_result", label=label_str, n=len(files))

    def _build_ext_filter(self, files):
        """Rebuild the per-extension checkboxes from the indexed file list."""
        for w in self._ext_filter_frame.winfo_children():
            w.destroy()
        self._ext_filter_vars.clear()
        cat_exts = defaultdict(set)
        for f in files:
            cat_exts[get_category(f["ext"])].add(f["ext"].lower())
        self._ext_filter_empty_lbl.pack_forget()
        row = None
        col_idx = 0
        for cat in sorted(cat_exts.keys()):
            color = EXTENSION_COLORS.get(cat, MUTED)
            cat_head = tk.Frame(self._ext_filter_frame, bg=SURFACE)
            cat_head.pack(anchor="w", fill="x", padx=SP_S, pady=(SP_M, SP_XS))
            tk.Label(cat_head, text="\u25cf", bg=SURFACE, fg=color,
                     font=font(SIZE_MICRO)).pack(side="left")
            cat_lbl = tr(tk.Label(cat_head, bg=SURFACE, fg=color,
                                  font=font(SIZE_MICRO, "bold")), f"cat_{cat}")
            cat_lbl.pack(side="left", padx=(SP_S, 0))
            row = tk.Frame(self._ext_filter_frame, bg=SURFACE)
            row.pack(fill="x", padx=SP_S)
            for col_idx, ext in enumerate(sorted(cat_exts[cat])):
                var = tk.BooleanVar(value=True)
                self._ext_filter_vars[ext] = var
                cb = tk.Checkbutton(row, text=ext.lstrip(".").upper() or "—",
                                    variable=var, bg=SURFACE, fg=TEXT_DIM,
                                    selectcolor=SURFACE2, activebackground=SURFACE,
                                    activeforeground=TEXT, font=font(SIZE_MICRO),
                                    highlightthickness=0, bd=0, cursor="hand2",
                                    command=self._on_ext_filter_change)
                cb.grid(row=col_idx // 3, column=col_idx % 3, sticky="w",
                        padx=SP_XS, pady=1)
                hover(cb, SURFACE, SURFACE2, TEXT_DIM, TEXT)

    def _select_all_exts(self, value):
        for var in self._ext_filter_vars.values():
            var.set(value)
        self._on_ext_filter_change()

    def _on_ext_filter_change(self):
        """Recompute the operations for the checked extensions, debounced."""
        if hasattr(self, "_ext_debounce_id") and self._ext_debounce_id:
            self.after_cancel(self._ext_debounce_id)
        self._ext_debounce_id = self.after(120, self._do_ext_filter_change)

    def _do_ext_filter_change(self):
        self._ext_debounce_id = None
        if self._full_tree is None or not self._all_files_ref:
            return
        selected_exts = {ext for ext, var in self._ext_filter_vars.items() if var.get()}
# Extension filters are applied on the cached file list so the structure can be recomputed without rescanning the disk.
        filtered_files = [f for f in self._all_files_ref
                          if f["ext"].lower() in selected_exts]
        editor = self._get_editor()
        if editor is None:
            return
        n_sel = len(selected_exts)
        n_filt = len(filtered_files)
        n_all  = len(self._all_files_ref)
        tr_var(self._status_var, "ops_recalc", n=n_filt)

        def report(done, total):
            pct = int(done / total * 100) if total else 0
            self.after(0, lambda: (
                tr_var(self._status_var, "computing_progress", d=done, t=total, p=pct),
                self._prog_bar_var.set(pct),
            ))

        def worker():
            result = editor.get_structure_for_files(filtered_files, progress_cb=report)
            self.after(0, lambda: self._on_ext_filter_ready(
                result, filtered_files, n_sel, n_filt, n_all))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ext_filter_ready(self, result, filtered_files, n_sel, n_filt, n_all):
        self._prog_bar_var.set(100)
        if result is None:
            self._ops = []
            self._ops_tree.delete(*self._ops_tree.get_children())
            self._nomatch_tree.delete(*self._nomatch_tree.get_children())
            tr(self._ops_count_lbl, "zero_files")
            self._update_summary()
            self._check_ready()
            return
        tree, labels, result_files = result
        self._tree = tree
        dest = self._dest_var.get().strip()
        self._refresh_ops(tree, dest or "/destination/")
        self._update_summary()
        self._check_ready()
        tr_var(self._status_var, "ops_selected", n=n_filt, t=n_all, e=n_sel)

    def _refresh_ops(self, tree, dest_base):
        """Build the plan for *tree* and render both operation tabs."""
        self._plan = build_plan(tree, dest_base)
        self._ops = self._plan.operations

        self._ops_tree.delete(*self._ops_tree.get_children())
        unmatched = set(self._plan.unmatched)
        for src, dst in self._plan.all_operations:
            tag = "nomatch" if (src, dst) in unmatched else ""
            self._ops_tree.insert("", "end",
                                  values=(os.path.basename(src), dst), tags=(tag,))
        self._ops_tree.tag_configure("nomatch", foreground=ORANGE)
        tr(self._ops_count_lbl, "ops_count", n=len(self._plan.all_operations))

        self._nomatch_tree.delete(*self._nomatch_tree.get_children())
        for src, dst in self._plan.unmatched:
            self._nomatch_tree.insert("", "end",
                                      values=(os.path.basename(src), dst), tags=("nm",))
        self._ops_notebook.tab(
            1, text=(t("ops_unmatched_tab", n=len(self._plan.unmatched))
                     if self._plan.unmatched else t("tab_unmatched")))
        if self._plan.unmatched:
            tr(self._nomatch_count_lbl, "ops_unmatched", n=len(self._plan.unmatched))
        else:
            self._nomatch_count_lbl.config(text="")

    def _update_summary(self):
        mode_str = t("copy_mode") if self._op_mode.get() == "copy" else t("move_mode")
        dest = self._dest_var.get().strip() or t("dest_undefined")
        tr(self._summary_lbl, "summary_template", n=len(self._ops), mode=mode_str, dest=dest)

    def _pick_dest(self):
        folder = filedialog.askdirectory(title=t("dlg_choose_dest"), parent=self)
        if folder:
            self._dest_var.set(folder)
            if self._tree is not None:
                self._refresh_ops(self._tree, folder)
            self._update_summary()
            self._check_ready()

    def _on_dest_typed(self):
        """React to the destination being typed rather than browsed to."""
        if self._tree is not None:
            self._refresh_ops(self._tree, self._dest_var.get().strip()
                              or "/destination/")
        self._update_summary()
        self._check_ready()

    def _check_ready(self):
        """Arm the run button, and say out loud what is still missing.

        The button is the whole point of this tab, so leaving it grey without
        a reason is what makes the tab feel broken rather than incomplete.
        """
        has_dest = bool(self._dest_var.get().strip())
        has_ops = bool(self._ops)
        ok = has_dest and has_ops
        self._run_btn.config(state="normal" if ok else "disabled",
                             bg=PRIMARY if ok else SURFACE2,
                             fg=ON_ACCENT if ok else MUTED,
                             cursor="hand2" if ok else "arrow")
        if ok:
            self._blocked_lbl.config(text="")
        elif not has_ops:
            self._blocked_lbl.config(text=t("blocked_no_structure"))
        else:
            self._blocked_lbl.config(text=t("blocked_no_dest"))

    def _run(self):
        dest = self._dest_var.get().strip()
        if not dest or not self._ops:
            return
        if not self._confirm_run(dest):
            return

        strategy = self._collision_strategy()
        if strategy is None:
            return

        self._cancel.clear()
        self._run_btn.config(state="disabled")
        self._stop_btn.pack(in_=self._run_btn.master, side="left", padx=(6, 0))
        self._progress.config(maximum=len(self._ops), value=0)
        threading.Thread(target=self._do_run,
                         args=(list(self._ops), self._op_mode.get(), strategy),
                         daemon=True).start()

    def _confirm_run(self, dest: str) -> bool:
        """Show everything that could go wrong, then ask for confirmation."""
        sources = [src for src, _ in self._ops]
        if destination_is_inside(sources, dest):
            messagebox.showerror(t("error"), t("dest_inside_src"), parent=self)
            return False

        mode = self._op_mode.get()
        if mode == executor.COPY and self._plan is not None:
            available = free_space(dest)
            if available is not None and available < self._plan.total_bytes:
                messagebox.showerror(
                    t("error"),
                    t("not_enough_space", need=fmt_size(self._plan.total_bytes),
                      free=fmt_size(available)),
                    parent=self)
                return False

        verb = t("verb_copy") if mode == executor.COPY else t("verb_move")
        message = (t("ops_confirm", verb=verb, n=len(self._ops))
                   + t("dest_label", dest=dest))
        if self._plan is not None and self._plan.unmatched:
            message += t("skipped_unmatched", n=len(self._plan.unmatched))
        if self._plan is not None and self._plan.internal_collisions:
            message += "\n" + t("collision_internal",
                                n=len(self._plan.internal_collisions))
        if mode == executor.MOVE:
            message += "\n" + t("warn_move")
        return bool(messagebox.askyesno(t("dlg_confirm"), message, parent=self))

    def _collision_strategy(self):
        """Return the duplicate strategy to run with, or None if cancelled.

        Two sources landing on the same destination count as a collision too:
        neither file exists yet, so checking the disk alone used to miss them
        and the second copy silently overwrote the first.
        """
        collisions = self._plan.collisions if self._plan is not None else []
        if not collisions:
            return executor.REPLACE
        chosen = self._dup_mode.get()
        if chosen == executor.ASK:
            return self._ask_collision_action(collisions)
        return chosen

    def _ask_collision_action(self, collisions):
        """Ask what to do about colliding destinations.

        Returns one of the executor strategies, or None when cancelled.
        """
        win = tk.Toplevel(self)
        win.title(t("collision_title"))
        win.configure(bg=SURFACE)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        tr(tk.Label(win,

                 bg=SURFACE, fg=ORANGE, font=font(SIZE_BODY, "bold"),
                 pady=10, padx=16), "ops_collision", n=len(collisions)).pack(anchor="w")

        lf = tk.Frame(win, bg=SURFACE2, padx=12, pady=8)
        lf.pack(fill="x", padx=16, pady=(0, 8))
        for _src, dst in collisions[:8]:
            tk.Label(lf, text=f"• {os.path.basename(dst)}",
                     bg=SURFACE2, fg=MUTED, font=font(SIZE_MICRO),
                     anchor="w").pack(fill="x")
        if len(collisions) > 8:
            tr(tk.Label(lf,
                     bg=SURFACE2, fg=MUTED, font=font(SIZE_MICRO, "italic"),
                     anchor="w"), "n_others", n=len(collisions)-8).pack(fill="x")

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", pady=(4, 8))
        tr(tk.Label(win,
                 bg=SURFACE, fg=TEXT, font=font(SIZE_SMALL),
                 padx=16), "duplicates_q").pack(anchor="w", pady=(0, 6))

        chosen = tk.StringVar(value="")

        btn_frame = tk.Frame(win, bg=SURFACE)
        btn_frame.pack(fill="x", padx=16, pady=(0, 14))

        def pick(val):
            chosen.set(val)
            win.destroy()

        tr(tk.Button(btn_frame,
                  bg=SURFACE2, fg=MUTED, relief="flat",
                  font=font(SIZE_SMALL), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick(executor.SKIP)), "dup_ignore").pack(side="left", padx=(0, 6))
        tr(tk.Button(btn_frame,
                  bg=ORANGE, fg="white", relief="flat",
                  font=font(SIZE_SMALL, "bold"), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick(executor.REPLACE)), "dup_replace").pack(side="left", padx=(0, 6))
        tr(tk.Button(btn_frame,
                  bg=PRIMARY, fg=ON_ACCENT, relief="flat",
                  font=font(SIZE_SMALL, "bold"), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick(executor.RENAME)), "dup_rename").pack(side="left", padx=(0, 6))
        tr(tk.Button(btn_frame,
                  bg=SURFACE2, fg=TEXT, relief="flat",
                  font=font(SIZE_SMALL), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick("")), "cancel").pack(side="right")

        win.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width()//2 - win.winfo_width()//2
        py = self.winfo_rooty() + self.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{px}+{py}")
        win.wait_window()

        val = chosen.get()
        return val if val else None

    def _request_cancel(self):
        """Ask the running batch to stop at the next file."""
        self._cancel.set()
        self._stop_btn.config(state="disabled", text="⏳")
        tr(self._prog_lbl, "cancelling")

    def _do_run(self, ops, mode, strategy):
        """Run the batch on a worker thread and hand the result back to Tk."""
        total = len(ops)
        errors = [0]

        def report(done, _total):
            self.after(0, self._update_progress, done, total, errors[0])

        result = executor.run(ops, mode, strategy, cancel=self._cancel,
                              progress=report, suffix=t("dup_suffix"))
        errors[0] = result.errors
        self.after(0, self._finish, result)

    def _update_progress(self, done, total, errors):
        self._progress["value"] = done
        self._prog_lbl.config(
            text=t("ops_progress", done=done, total=total)
                 + (t("ops_errors", n=errors) if errors else ""))

    def _finish(self, result):
        """Report the outcome of a run and reset the controls."""
        self._stop_btn.pack_forget()
        self._stop_btn.config(state="normal", text="⏹")
        self._cancel.clear()
        self._run_btn.config(state="normal")

        verb = (t("verb_copied") if self._op_mode.get() == executor.COPY
                else t("verb_moved"))
        errors = result.errors
        if result.cancelled:
            message = t("ops_cancelled", done=result.done, verb=verb)
            if errors:
                message += t("ops_cancelled_err", n=errors)
            messagebox.showwarning(t("dlg_cancelled"), message, parent=self)
            tr_var(self._status_var, "ops_status_cancel", done=result.done, verb=verb)
        else:
            message = t("ops_done_msg", done=result.done, verb=verb)
            if errors:
                message += t("ops_done_err", n=errors) + "\n".join(
                    result.error_messages[:10])
                if len(result.error_messages) > 10:
                    message += t("n_others", n=len(result.error_messages) - 10)
            messagebox.showinfo(t("dlg_done"), message, parent=self)
            tr_var(self._status_var, "ops_status_done", done=result.done, verb=verb)
        if errors:
            set_raw(self._status_var,
                    self._status_var.get() + t("n_errors_status", n=errors))
        if result.journal_path:
            log.info("operation journal written to %s", result.journal_path)

    def refresh_lang(self):
        """Re-render the tree headings and notebook tabs.

        Every label, button and radio here is bound with ``tr()``, so the i18n
        registry has already refreshed them.
        """
        try:
            self._ops_tree.heading("src", text=t("col_src"))
            self._ops_tree.heading("dst", text=t("col_dst"))
            self._nomatch_tree.heading("file", text=t("col_file"))
            self._nomatch_tree.heading("reason", text=t("col_reason"))
            self._ops_notebook.tab(0, text=t("tab_all_ops"))
            self._ops_notebook.tab(
                1, text=(t("ops_unmatched_tab", n=len(self._plan.unmatched))
                         if self._plan and self._plan.unmatched
                         else t("tab_unmatched")))
        except tk.TclError:
            log.debug("organize widgets gone", exc_info=True)
        self._update_summary()
