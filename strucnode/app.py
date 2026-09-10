"""The main window: top bar, tab switching, language, scanning, status bar."""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import config, i18n
from .core.categories import fmt_size
from .core.scanner import scan
from .i18n import available_locales, set_raw, t, tr, tr_var
from .theme import (
    BG,
    BORDER,
    BORDER_SOFT,
    MUTED,
    ON_ACCENT,
    ORANGE,
    PRIMARY,
    SIZE_BODY,
    SIZE_MICRO,
    SIZE_SMALL,
    SIZE_TITLE,
    SP_M,
    SP_S,
    SURFACE,
    SURFACE2,
    SURFACE3,
    TEXT,
    TEXT_DIM,
    Tooltip,
    apply_styles,
    button,
    font,
)
from .ui.explorer_tab import ExplorerTab
from .ui.nodes.editor_tab import NodeEditorTab
from .ui.organize_tab import OrganizeTab

log = logging.getLogger(__name__)

#: Flag shown on each language button.
LANGUAGE_FLAGS = {"en": "🇬🇧", "fr": "🇫🇷"}

TABS = (("explorer", "tab_explorer"), ("nodal", "tab_nodal"),
        ("organize", "tab_organize"))
LOCKED_TABS = ("nodal", "organize")

#: Height of the strip that marks the active tab.
TAB_INDICATOR_H = 3


class StrucnodeApp(tk.Tk):
    """Root window. Owns the folder scan and hands the result to the tabs."""

    def __init__(self):
        super().__init__()
        self.settings = config.load_settings()
        i18n.set_locale(self.settings.get("locale")
                        or config.detect_locale(available_locales()))

        self.geometry("1500x900")
        self.minsize(1100, 660)
        self.configure(bg=BG)

        self._indexed = False
        self._folder = self.settings.get("last_folder") or None
        self._scan_result = None
        self._scan_cancel = threading.Event()
        self._current_tab = "explorer"
        self._nodal_editor = None
        self._organize_tab = None
        self._lang_buttons: dict[str, tk.Button] = {}
        self._tab_btns: dict[str, tk.Button] = {}
        self._tab_indicators: dict[str, tk.Frame] = {}
        self._tab_frames: dict[str, tk.Frame] = {}

        self._build_ui()
        i18n.on_change(self._refresh_lang)
        self._refresh_lang()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        apply_styles(self)
        self._build_topbar()
        self._build_tab_bar()

        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True)
        self.explorer = ExplorerTab(self._content, on_scan_done=self._on_scan_done)
        self._tab_frames["explorer"] = self.explorer
        for key in LOCKED_TABS:
            self._tab_frames[key] = tk.Frame(self._content, bg=BG)

        self._build_status_bar()
        self._switch_tab("explorer")

    def _build_topbar(self):
        """Brand, the folder being worked on, and the two actions on it."""
        topbar = tk.Frame(self, bg=SURFACE, pady=SP_M, padx=SP_M + SP_S)
        topbar.pack(fill="x")
        tk.Frame(self, bg=BORDER_SOFT, height=1).pack(fill="x")

        tk.Label(topbar, text="📁", bg=SURFACE, fg=PRIMARY,
                 font=font(18)).pack(side="left")
        tr(tk.Label(topbar, bg=SURFACE, fg=TEXT, font=font(SIZE_TITLE, "bold")),
           "app_title").pack(side="left", padx=(SP_S + 2, SP_M * 2))

        self.path_var = tk.StringVar()
        if self._folder:
            set_raw(self.path_var, self._folder)
        else:
            tr_var(self.path_var, "no_folder")
        # The entry is editable, so a typed path must become the chosen folder
        # and must stop being overwritten by the placeholder on a locale change.
        self.path_var.trace_add("write", self._on_path_edited)

        # A one-pixel frame around the entry gives the field a visible outline
        # that lights up on focus; a flat tk.Entry alone reads as a plain label.
        field = tk.Frame(topbar, bg=BORDER)
        field.pack(side="left", fill="x", expand=True, padx=(0, SP_M))
        inner = tk.Frame(field, bg=SURFACE2)
        inner.pack(fill="x", padx=1, pady=1)
        tk.Label(inner, text="🗀", bg=SURFACE2, fg=MUTED,
                 font=font(SIZE_BODY)).pack(side="left", padx=(SP_M, 0))
        entry = tk.Entry(inner, textvariable=self.path_var, bg=SURFACE2, fg=TEXT,
                         insertbackground=PRIMARY, relief="flat",
                         highlightthickness=0, font=font(SIZE_BODY))
        entry.pack(side="left", fill="x", expand=True, ipady=6, padx=SP_M)
        entry.bind("<Return>", lambda _e: self._scan())
        entry.bind("<FocusIn>", lambda _e: field.config(bg=PRIMARY))
        entry.bind("<FocusOut>", lambda _e: field.config(bg=BORDER))

        self.scan_btn = tr(button(topbar, variant="primary", size=SIZE_BODY,
                                  bold=True, padx=SP_M + 2, pady=6,
                                  command=self._scan), "analyze")
        self.scan_btn.pack(side="right")
        Tooltip(self.scan_btn, lambda: t("tip_analyze"))
        self._choose_btn = tr(button(topbar, variant="ghost", size=SIZE_BODY,
                                     padx=SP_M + 2, pady=6,
                                     command=self._pick_folder), "choose_folder")
        self._choose_btn.pack(side="right", padx=(0, SP_M))

        lang_frame = tk.Frame(topbar, bg=SURFACE2)
        lang_frame.pack(side="right", padx=(0, SP_M * 2))
        for code in reversed(available_locales()):
            btn = tk.Button(lang_frame, text=LANGUAGE_FLAGS.get(code, code.upper()),
                            bg=SURFACE2, fg=TEXT, relief="flat",
                            font=font(13), cursor="hand2", bd=0,
                            highlightthickness=0, padx=SP_S, pady=SP_S,
                            activebackground=SURFACE3,
                            command=lambda c=code: self._set_language(c))
            btn.pack(side="right")
            self._lang_buttons[code] = btn
            Tooltip(btn, lambda c=code: t("tip_language", lang=c.upper()))

    def _build_tab_bar(self):
        """One button per tab, each with the strip that marks it as active."""
        tab_bar = tk.Frame(self, bg=SURFACE2)
        tab_bar.pack(fill="x")
        tk.Frame(self, bg=BORDER_SOFT, height=1).pack(fill="x")

        for key, label_key in TABS:
            holder = tk.Frame(tab_bar, bg=SURFACE2)
            holder.pack(side="left")
            btn = tr(tk.Button(holder, bg=SURFACE2, fg=MUTED, relief="flat",
                               bd=0, highlightthickness=0, font=font(SIZE_BODY),
                               padx=SP_M + 4, pady=SP_M + 1, cursor="hand2",
                               activebackground=BG, activeforeground=TEXT,
                               command=lambda k=key: self._switch_tab(k)), label_key)
            btn.pack(fill="x")
            indicator = tk.Frame(holder, bg=SURFACE2, height=TAB_INDICATOR_H)
            indicator.pack(fill="x")
            self._tab_btns[key] = btn
            self._tab_indicators[key] = indicator
            if key in LOCKED_TABS:
                Tooltip(btn, lambda k=key: None if self._indexed
                        else t("tab_locked_tip"))

        self._lock_lbl = tr(tk.Label(tab_bar, bg=SURFACE2, fg=MUTED,
                                     font=font(SIZE_MICRO)), "available_after")
        self._lock_lbl.pack(side="left", padx=SP_M)

    def _build_status_bar(self):
        """The bottom strip: scan progress, then the result of the scan."""
        self.status_var = tk.StringVar()
        tr_var(self.status_var, "status_ready")
        self.progress = ttk.Progressbar(self, mode="indeterminate",
                                        style="Custom.Horizontal.TProgressbar")
        status_bar = tk.Frame(self, bg=SURFACE, pady=SP_S + 1, padx=SP_M)
        status_bar.pack(fill="x", side="bottom")
        tk.Frame(self, bg=BORDER_SOFT, height=1).pack(fill="x", side="bottom")
        self._status_dot = tk.Label(status_bar, text="●", bg=SURFACE, fg=MUTED,
                                    font=font(SIZE_MICRO))
        self._status_dot.pack(side="left", padx=(0, SP_S + 2))
        tk.Label(status_bar, textvariable=self.status_var, bg=SURFACE,
                 fg=TEXT_DIM, font=font(SIZE_SMALL)).pack(side="left")

    # ------------------------------------------------------------ language --
    def _set_language(self, code: str):
        """Switch the UI language and remember the choice."""
        i18n.set_locale(code)
        self.settings["locale"] = i18n.get_locale()
        config.save_settings(self.settings)

    def _refresh_lang(self):
        """Called by the i18n registry after every locale change."""
        active = i18n.get_locale()
        for code, btn in self._lang_buttons.items():
            btn.config(bg=PRIMARY if code == active else SURFACE2,
                       fg=ON_ACCENT if code == active else MUTED)
        self.title(t("window_title_main"))
        self._lock_lbl.config(text="" if self._indexed else t("available_after"))
        self._render_scan_status()
        for tab in (self.explorer, self._nodal_editor, self._organize_tab):
            if tab is not None:
                try:
                    tab.refresh_lang()
                except Exception:
                    log.warning("cannot refresh %r", tab, exc_info=True)
        self._highlight_active_tab()

    # ---------------------------------------------------------------- tabs --
    def _switch_tab(self, key: str):
        if key in LOCKED_TABS and not self._indexed:
            return
        self._current_tab = key
        for frame in self._tab_frames.values():
            frame.pack_forget()
        self._tab_frames[key].pack(fill="both", expand=True)
        self._highlight_active_tab()

        if key == "nodal" and self._nodal_editor is None:
            self._nodal_editor = NodeEditorTab(self._tab_frames["nodal"],
                                               lambda: self.explorer.files)
            self._nodal_editor.pack(fill="both", expand=True)
            self._nodal_editor.refresh_palette()
        if key == "organize" and self._organize_tab is None:
            self._organize_tab = OrganizeTab(self._tab_frames["organize"],
                                             lambda: self._nodal_editor)
            self._organize_tab.pack(fill="both", expand=True)

    def _highlight_active_tab(self):
        """Colour, weight *and* an underline: three cues rather than one.

        Colour alone was the only marker, which left the active tab hard to
        pick out at a glance -- and invisible to anyone reading the interface
        in greyscale.
        """
        for key, btn in self._tab_btns.items():
            active = key == self._current_tab
            locked = key in LOCKED_TABS and not self._indexed
            btn.config(bg=BG if active else SURFACE2,
                       fg=PRIMARY if active else (BORDER if locked else MUTED),
                       cursor="arrow" if locked else "hand2",
                       font=font(SIZE_BODY, "bold" if active else "normal"))
            self._tab_indicators[key].config(bg=PRIMARY if active else SURFACE2)

    def _lock_tabs(self):
        self._indexed = False
        self._lock_lbl.config(text=t("indexing"))
        self._highlight_active_tab()
        if self._current_tab in LOCKED_TABS:
            self._switch_tab("explorer")

    def _unlock_tabs(self):
        self._indexed = True
        self._lock_lbl.config(text="")
        self._highlight_active_tab()
        if self._nodal_editor is not None:
            self._nodal_editor.refresh_palette()

    # ---------------------------------------------------------------- scan --
    def _on_path_edited(self, *_args):
        value = self.path_var.get()
        if value and not (i18n.is_bound(self.path_var) and value == t("no_folder")):
            i18n.untr(self.path_var)
            self._folder = value
        elif not value:
            self._folder = None

    def _pick_folder(self):
        folder = filedialog.askdirectory(title=t("choose_folder"))
        if folder:
            self._folder = folder
            set_raw(self.path_var, folder)
            self.settings["last_folder"] = folder
            config.save_settings(self.settings)
            self._lock_tabs()
            self._scan()

    def _scan(self):
        # The chosen folder is tracked as state; the entry may be showing the
        # translated placeholder, and comparing against it would break as soon
        # as the language changed.
        folder = self._folder
        if not folder:
            messagebox.showwarning(t("dlg_warning"), t("need_folder"))
            return
        if not os.path.isdir(folder):
            messagebox.showerror(t("error"),
                                 t("dlg_folder_missing", folder=folder))
            return

        self.explorer.stop_playback()
        self.scan_btn.config(state="disabled")
        self._status_dot.config(fg=PRIMARY)
        self.progress.pack(fill="x", side="bottom", before=self.winfo_children()[-1])
        self.progress.start(10)
        tr_var(self.status_var, "scan_starting")
        self._scan_cancel.clear()

        def report(files, size):
            self.after(0, lambda: tr_var(self.status_var, "status_files",
                                         f=files, size=fmt_size(size)))

        def worker():
            result = scan(folder, progress=report, cancel=self._scan_cancel)
            self.after(0, lambda: self.explorer.show_results(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self, result):
        """Called by the Explorer tab once a scan has been rendered."""
        self.progress.stop()
        self.progress.pack_forget()
        self.scan_btn.config(state="normal")
        self._scan_result = result
        self._render_scan_status()
        self._unlock_tabs()

    def _render_scan_status(self):
        """Render the post-scan status line in the active language.

        The result is kept as data and re-rendered, rather than stored as an
        already-formatted string that a language change could not update.
        """
        result = self._scan_result
        if result is None:
            return
        message = t("status_scan", files=result.total_files,
                    dirs=result.total_dirs, size=fmt_size(result.total_size))
        if result.errors:
            message += t("status_errors", n=result.errors)
        set_raw(self.status_var, message)
        self._status_dot.config(fg=ORANGE if result.errors else PRIMARY)

    def _on_close(self):
        self._scan_cancel.set()
        self.explorer.stop_playback()
        config.save_settings(self.settings)
        self.destroy()


def main() -> None:
    """Entry point for ``python -m strucnode`` and the ``strucnode`` command."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s")
    StrucnodeApp().mainloop()
