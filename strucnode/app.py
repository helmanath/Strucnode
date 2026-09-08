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
from .theme import BG, MUTED, PRIMARY, PRIMARY_H, SURFACE, SURFACE2, TEXT, apply_styles
from .ui.explorer_tab import ExplorerTab
from .ui.nodes.editor_tab import NodeEditorTab
from .ui.organize_tab import OrganizeTab

log = logging.getLogger(__name__)

#: Flag shown on each language button.
LANGUAGE_FLAGS = {"en": "🇬🇧", "fr": "🇫🇷"}

TABS = (("explorer", "tab_explorer"), ("nodal", "tab_nodal"),
        ("organize", "tab_organize"))
LOCKED_TABS = ("nodal", "organize")


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
        self._tab_frames: dict[str, tk.Frame] = {}

        self._build_ui()
        i18n.on_change(self._refresh_lang)
        self._refresh_lang()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        apply_styles(self)

        topbar = tk.Frame(self, bg=SURFACE, pady=8, padx=16)
        topbar.pack(fill="x")
        tk.Label(topbar, text="📁", bg=SURFACE, fg=PRIMARY,
                 font=("Segoe UI", 18)).pack(side="left")
        tr(tk.Label(topbar, bg=SURFACE, fg=TEXT, font=("Segoe UI", 13, "bold")),
           "app_title").pack(side="left", padx=(6, 20))

        self.path_var = tk.StringVar()
        if self._folder:
            set_raw(self.path_var, self._folder)
        else:
            tr_var(self.path_var, "no_folder")
        # The entry is editable, so a typed path must become the chosen folder
        # and must stop being overwritten by the placeholder on a locale change.
        self.path_var.trace_add("write", self._on_path_edited)
        tk.Entry(topbar, textvariable=self.path_var, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 10)
                 ).pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

        tr(tk.Button(topbar, bg=PRIMARY, fg="#0f3638", activebackground=PRIMARY_H,
                     activeforeground="#0f3638", relief="flat",
                     font=("Segoe UI", 10, "bold"), padx=12, pady=5,
                     cursor="hand2", command=self._pick_folder),
           "choose_folder").pack(side="left")
        self.scan_btn = tr(tk.Button(topbar, bg=SURFACE2, fg=TEXT, relief="flat",
                                     font=("Segoe UI", 10), padx=12, pady=5,
                                     cursor="hand2", command=self._scan),
                           "analyze")
        self.scan_btn.pack(side="left", padx=(8, 0))

        lang_frame = tk.Frame(topbar, bg=SURFACE)
        lang_frame.pack(side="right", padx=(4, 8))
        for code in reversed(available_locales()):
            btn = tk.Button(lang_frame, text=LANGUAGE_FLAGS.get(code, code.upper()),
                            bg=SURFACE, fg=TEXT, relief="flat",
                            font=("Segoe UI", 15), cursor="hand2", bd=0,
                            activebackground=SURFACE2,
                            command=lambda c=code: self._set_language(c))
            btn.pack(side="right", padx=2)
            self._lang_buttons[code] = btn

        tab_bar = tk.Frame(self, bg=SURFACE2)
        tab_bar.pack(fill="x")
        for key, label_key in TABS:
            btn = tr(tk.Button(tab_bar, bg=SURFACE2, fg=MUTED, relief="flat",
                               font=("Segoe UI", 10), padx=12, pady=8,
                               cursor="hand2", activebackground=BG,
                               activeforeground=TEXT,
                               command=lambda k=key: self._switch_tab(k)), label_key)
            btn.pack(side="left")
            self._tab_btns[key] = btn
        self._lock_lbl = tr(tk.Label(tab_bar, bg=SURFACE2, fg=MUTED,
                                     font=("Segoe UI", 8)), "available_after")
        self._lock_lbl.pack(side="left")

        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True)
        self.explorer = ExplorerTab(self._content, on_scan_done=self._on_scan_done)
        self._tab_frames["explorer"] = self.explorer
        for key in LOCKED_TABS:
            self._tab_frames[key] = tk.Frame(self._content, bg=BG)

        self.status_var = tk.StringVar()
        tr_var(self.status_var, "status_ready")
        self.progress = ttk.Progressbar(self, mode="indeterminate",
                                        style="Custom.Horizontal.TProgressbar")
        status_bar = tk.Frame(self, bg=SURFACE, pady=4, padx=14)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self.status_var, bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")

        self._switch_tab("explorer")

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
            btn.config(relief="sunken" if code == active else "flat",
                       bg=SURFACE2 if code == active else SURFACE)
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
        for key, btn in self._tab_btns.items():
            active = key == self._current_tab
            btn.config(bg=BG if active else SURFACE2,
                       fg=PRIMARY if active else MUTED,
                       font=("Segoe UI", 10, "bold" if active else "normal"))

    def _lock_tabs(self):
        self._indexed = False
        self._lock_lbl.config(text=t("indexing"))
        for key in LOCKED_TABS:
            self._tab_btns[key].config(fg=MUTED)
        if self._current_tab in LOCKED_TABS:
            self._switch_tab("explorer")

    def _unlock_tabs(self):
        self._indexed = True
        self._lock_lbl.config(text="")
        for key in LOCKED_TABS:
            self._tab_btns[key].config(fg=TEXT)
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
