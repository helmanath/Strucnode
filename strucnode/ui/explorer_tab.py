"""The Explorer tab: folder statistics, file table, preview and metadata."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import messagebox, ttk

from ..core.categories import (
    IMAGE_EXTS,
    RAW_EXTS,
    VIDEO_EXTS,
    category_label,
    fmt_size,
    get_category,
)
from ..core.metadata import FIELD_LABELS, FILTER_FIELDS, read_exif
from ..core.scanner import format_mtime
from ..i18n import t, tr
from ..media.images import is_360_image, open_raw_thumbnail
from ..media.system import open_file
from ..media.video import VideoPlayer
from ..theme import (
    BG,
    BLUE,
    BORDER,
    BORDER_SOFT,
    DANGER,
    EXTENSION_COLORS,
    MUTED,
    ORANGE,
    PREVIEW_H,
    PREVIEW_W,
    PRIMARY,
    PURPLE,
    SIZE_H1,
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
    font,
    hover,
)
from .viewers import FullscreenVideoPlayer, FullscreenViewer, Viewer360

log = logging.getLogger(__name__)

#: Index of the "all values" entry, always first in every filter combo.
ALL_INDEX = 0

#: EXIF reads are I/O bound, so a few threads help; more only thrash the disk.
EXIF_WORKERS = 8

#: Hover shade of the play button. It is the only control coloured by state
#: rather than by role, so it does not come from the shared button palette.
PLAY_BTN_HOVER = "#c05663"

#: EXIF filter field -> i18n key for its inline label.
EXIF_FILTER_LABELS = {
    "iso": "filter_iso",
    "focal_length": "filter_focal",
    "model": "filter_device",
    "aperture": "filter_aperture",
}


class ExplorerTab(tk.Frame):
    """Folder statistics on the left, file table and preview on the right."""

    def __init__(self, parent, on_scan_done=None):
        super().__init__(parent, bg=BG)
        self.on_scan_done = on_scan_done
        self._cat_files: dict[str, list] = {}
        self._all_files: list = []
        self._active_cat = None
        self._active_ext_filter = None
        self._file_rows: list = []
        self._file_sort_col = "name"
        self._file_sort_rev = False
        self._filter_widgets: dict = {}
        self._all_ext_rows: list = []
        self._ext_sort_col = "count"
        self._ext_sort_rev = True
        self._summary_card_data: list = []
        self._scan_result = None
        self._category_data: list = []
        self._current_preview_path = None
        self._current_is_360 = False
        self._current_is_video = False
        self._current_is_raw = False
        self._preview_img = None
        self._muted = False
        # Declared before _build_ui(): it wires callbacks such as
        # _update_seek_bar that read the player before it can exist.
        self._video_player = None
        self._build_ui()
        self._video_player = VideoPlayer(self.preview_canvas, PREVIEW_W, PREVIEW_H)

    @property
    def files(self) -> list:
        """Every indexed file, flat -- what the node editor consumes."""
        return self._all_files

    def stop_playback(self):
        """Stop the preview player, e.g. before a rescan or on close."""
        if self._video_player:
            self._video_player.stop()

    def _build_ui(self):
        body=tk.Frame(self,bg=BG); body.pack(fill="both",expand=True,padx=14,pady=10)
        self.left=tk.Frame(body,bg=BG,width=268); self.left.pack(side="left",fill="y",padx=(0,SP_M+SP_S))
        self.left.pack_propagate(False)
        self._lbl_summary=tk.Label(self.left,text=t("resume"),bg=BG,fg=MUTED,
                                   font=font(SIZE_MICRO,"bold"))
        self._lbl_summary.pack(anchor="w",pady=(0,SP_M))
        self.summary_frame=tk.Frame(self.left,bg=BG); self.summary_frame.pack(fill="x")
        self._lbl_by_cat=tk.Label(self.left,text=t("by_category"),bg=BG,fg=MUTED,
                                  font=font(SIZE_MICRO,"bold"))
        self._lbl_by_cat.pack(anchor="w",pady=(SP_M+SP_M,SP_XS))
        self._lbl_click_filter=tk.Label(self.left,text=t("click_filter"),bg=BG,fg=MUTED,
                                        font=font(SIZE_MICRO))
        self._lbl_click_filter.pack(anchor="w",pady=(0,SP_M))
        self.cat_frame=tk.Frame(self.left,bg=BG); self.cat_frame.pack(fill="x")
        center=tk.Frame(body,bg=BG); center.pack(side="left",fill="both",expand=True,padx=(0,10))
        self.paned=tk.PanedWindow(center,orient="vertical",bg=BG,sashwidth=6,sashrelief="flat")
        self.paned.pack(fill="both",expand=True)
        top_fr=tk.Frame(self.paned,bg=BG); self.paned.add(top_fr,minsize=120)
        hdr=tk.Frame(top_fr,bg=BG); hdr.pack(fill="x",pady=(0,SP_M))
        self._lbl_detail_ext=tk.Label(hdr,text=t("detail_ext"),bg=BG,fg=MUTED,
                                      font=font(SIZE_MICRO,"bold"))
        self._lbl_detail_ext.pack(side="left")
        self.ext_filter_var=tk.StringVar()
        self.ext_filter_var.trace_add("write",lambda *_:self._apply_ext_filter())
        search=tk.Frame(hdr,bg=SURFACE2); search.pack(side="right")
        tk.Label(search,text="\U0001f50d",bg=SURFACE2,fg=MUTED,
                 font=font(SIZE_SMALL)).pack(side="left",padx=(SP_M,0))
        tk.Entry(search,textvariable=self.ext_filter_var,bg=SURFACE2,fg=TEXT,
                 insertbackground=PRIMARY,relief="flat",highlightthickness=0,
                 font=font(SIZE_SMALL),width=20).pack(side="left",ipady=SP_S,
                                                      padx=(SP_S,SP_M))
        ext_tree_fr=tk.Frame(top_fr,bg=SURFACE); ext_tree_fr.pack(fill="both",expand=True)
        cols=("extension","category","count","size","percent")
        self.ext_tree=ttk.Treeview(ext_tree_fr,columns=cols,show="headings",
                                    selectmode="browse",style="Custom.Treeview",cursor="hand2")
        for c,lbl,w in [("extension",t("col_extension"),110),("category",t("col_category"),110),
                         ("count",t("col_files"),80),("size",t("col_total_size"),140),("percent",t("col_percent"),80)]:
            self.ext_tree.heading(c,text=lbl,command=lambda _c=c:self._sort_ext_by(_c))
            self.ext_tree.column(c,width=w,anchor="center" if c in ("count","percent") else "w")
        vsb_e=ttk.Scrollbar(ext_tree_fr,orient="vertical",command=self.ext_tree.yview,style="Dark.Vertical.TScrollbar")
        self.ext_tree.configure(yscrollcommand=vsb_e.set)
        vsb_e.pack(side="right",fill="y"); self.ext_tree.pack(fill="both",expand=True)
        self.ext_tree.bind("<<TreeviewSelect>>",self._on_ext_row_click)

        bot_fr=tk.Frame(self.paned,bg=BG); self.paned.add(bot_fr,minsize=160)
        file_hdr=tk.Frame(bot_fr,bg=BG); file_hdr.pack(fill="x",pady=(6,0))
        self.file_section_lbl=tk.Label(file_hdr,
            text=t("files_select"),
            bg=BG,fg=MUTED,font=font(SIZE_MICRO,"bold"))
        self.file_section_lbl.pack(side="left")
        self.file_count_lbl=tk.Label(file_hdr,text="",bg=BG,fg=TEXT_DIM,
                                     font=font(SIZE_MICRO))
        self.file_count_lbl.pack(side="right")
        self.filter_bar=tk.Frame(bot_fr,bg=SURFACE,padx=SP_M+SP_S,pady=SP_M)
        self.filter_bar.pack(fill="x",pady=(SP_S,0))
        self._build_filter_bar_base()
        file_tree_fr=tk.Frame(bot_fr,bg=SURFACE)
        file_tree_fr.pack(fill="both",expand=True,pady=(3,0))
        self._file_cols_base=("name","ext","size","mtime")
        self._file_cols_exif=("iso","focal_length","model","make","aperture","exposure")
        self._file_cols=self._file_cols_base
        self.file_tree=ttk.Treeview(file_tree_fr,columns=self._file_cols,
                                     show="headings",selectmode="browse",style="Custom.Treeview")
        self._setup_file_tree_cols(self._file_cols)
        vsb_f=ttk.Scrollbar(file_tree_fr,orient="vertical",command=self.file_tree.yview,style="Dark.Vertical.TScrollbar")
        hsb_f=ttk.Scrollbar(file_tree_fr,orient="horizontal",command=self.file_tree.xview,style="Dark.Horizontal.TScrollbar")
        self.file_tree.configure(yscrollcommand=vsb_f.set,xscrollcommand=hsb_f.set)
        vsb_f.pack(side="right",fill="y"); hsb_f.pack(side="bottom",fill="x")
        self.file_tree.pack(fill="both",expand=True)
        self.file_tree.bind("<<TreeviewSelect>>",self._on_file_select)
        self.file_tree.bind("<Double-1>",self._open_selected_file)
        self.path_lbl=tk.Label(bot_fr,text="",bg=SURFACE2,fg=TEXT_DIM,
                               font=font(SIZE_MICRO),anchor="w",padx=SP_M,pady=SP_S)
        preview_col=tk.Frame(body,bg=BG,width=306)
        preview_col.pack(side="left",fill="y"); preview_col.pack_propagate(False)
        self._lbl_preview=tk.Label(preview_col,text=t("preview"),bg=BG,fg=MUTED,
                                   font=font(SIZE_MICRO,"bold"))
        self._lbl_preview.pack(anchor="w",pady=(0,SP_S+2))
        self._badge_360=tk.Label(preview_col,text="  360\u00b0  ",bg=ORANGE,fg=BG,
                                 font=font(SIZE_MICRO,"bold"),pady=1)
        self._badge_raw=tk.Label(preview_col,text="  RAW  ",bg=BLUE,fg=BG,
                                 font=font(SIZE_MICRO,"bold"),pady=1)
        self.preview_frame=tk.Frame(preview_col,bg=SURFACE,width=PREVIEW_W,height=PREVIEW_H)
        self.preview_frame.pack(fill="x"); self.preview_frame.pack_propagate(False)
        self.preview_canvas=tk.Canvas(self.preview_frame,bg=SURFACE,highlightthickness=0,
                                       width=PREVIEW_W,height=PREVIEW_H)
        self.preview_canvas.pack(fill="both",expand=True)
        self._draw_preview_placeholder()
        self._video_ctrl_frame=tk.Frame(preview_col,bg=SURFACE2)
        self._seek_var=tk.DoubleVar(value=0.0)
        ttk.Scale(self._video_ctrl_frame,from_=0,to=1,orient="horizontal",variable=self._seek_var,
                  command=self._on_seek,style="Video.Horizontal.TScale").pack(fill="x",padx=8,pady=(4,2))
        ctrl_row=tk.Frame(self._video_ctrl_frame,bg=SURFACE2); ctrl_row.pack(fill="x",padx=8,pady=(0,4))
        self._play_btn=tk.Button(ctrl_row,text="\u25b6",bg=DANGER,fg="white",
                                  relief="flat",bd=0,highlightthickness=0,
                                  font=font(SIZE_H1,"bold"),width=3,cursor="hand2",
                                  activebackground=PLAY_BTN_HOVER,
                                  activeforeground="white",
                                  command=self._toggle_play)
        self._play_btn.pack(side="left",padx=(0,SP_S+2))
        Tooltip(self._play_btn, lambda: t("tip_play_pause"))
        self._mute_btn=tk.Button(ctrl_row,text="\U0001f50a",bg=SURFACE2,fg=TEXT,
                                  relief="flat",bd=0,highlightthickness=0,
                                  font=font(SIZE_H1),cursor="hand2",
                                  activebackground=SURFACE3,
                                  activeforeground=TEXT,command=self._toggle_mute)
        self._mute_btn.pack(side="left",padx=(0,SP_XS))
        hover(self._mute_btn, SURFACE2, SURFACE3)
        self._vol_var=tk.DoubleVar(value=1.0)
        ttk.Scale(ctrl_row,from_=0,to=1,orient="horizontal",variable=self._vol_var,
                  command=self._on_volume,style="Video.Horizontal.TScale",length=52).pack(side="left",padx=(0,6))
        self._time_lbl=tk.Label(ctrl_row,text="0:00 / 0:00",bg=SURFACE2,fg=MUTED,font=font(SIZE_MICRO))
        self._time_lbl.pack(side="left")
        _fs_btn=tk.Button(ctrl_row,text="\u26f6",bg=SURFACE2,fg=TEXT,relief="flat",
                  bd=0,highlightthickness=0,font=font(SIZE_H1),
                  padx=SP_S,cursor="hand2",activebackground=SURFACE3,
                  command=self._open_video_fullscreen)
        _fs_btn.pack(side="right")
        hover(_fs_btn, SURFACE2, SURFACE3)
        Tooltip(_fs_btn, lambda: t("tip_fullscreen"))
        self._update_seek_bar()

        self._lbl_click_enlarge=tk.Label(preview_col,text=t("click_enlarge"),bg=BG,
                                         fg=MUTED,font=font(SIZE_MICRO))
        self.preview_canvas.bind("<Button-1>",self._on_preview_click)

        self._lbl_metadata=tk.Label(preview_col,text=t("metadata"),bg=BG,fg=MUTED,
                                    font=font(SIZE_MICRO,"bold"))
        self._lbl_metadata.pack(anchor="w",pady=(SP_M+2,SP_S+2))
        meta_wrap=tk.Frame(preview_col,bg=SURFACE); meta_wrap.pack(fill="both",expand=True)
        mc=tk.Canvas(meta_wrap,bg=SURFACE,highlightthickness=0)
        ms=ttk.Scrollbar(meta_wrap,orient="vertical",command=mc.yview,style="Dark.Vertical.TScrollbar")
        self.meta_inner=tk.Frame(mc,bg=SURFACE)
        self.meta_inner.bind("<Configure>",lambda e:mc.configure(scrollregion=mc.bbox("all")))
        mc.create_window((0,0),window=self.meta_inner,anchor="nw"); mc.configure(yscrollcommand=ms.set)
        ms.pack(side="right",fill="y"); mc.pack(side="left",fill="both",expand=True)
        self._show_meta([])
    def _toggle_play(self):
        if self._video_player: self._video_player.toggle()

    def _toggle_mute(self):
        self._muted = not self._muted
        if self._video_player: self._video_player.set_muted(self._muted)
        self._mute_btn.config(text="\U0001f507" if self._muted else "\U0001f50a",
                              fg=DANGER if self._muted else TEXT)

    def _on_volume(self, val):
        v = float(val)
        if self._video_player: self._video_player.set_volume(v)
        if v == 0: self._muted=True; self._mute_btn.config(text="\U0001f507",fg=DANGER)
        elif self._muted:
            self._muted=False
            if self._video_player: self._video_player.set_muted(False)
            self._mute_btn.config(text="\U0001f50a",fg=TEXT)

    def _on_video_state(self, playing):
        self._play_btn.config(text="\u23f8" if playing else "\u25b6",
                              bg=SUCCESS if playing else DANGER)

    def _on_seek(self, val):
        if self._video_player: self._video_player.seek(float(val))

    def _update_seek_bar(self):
        if self._video_player and self._current_is_video:
            try:
                self._seek_var.set(self._video_player.progress)
                self._time_lbl.config(text=self._video_player.time_str)
            except Exception: pass
        self.after(200, self._update_seek_bar)

    def _open_video_fullscreen(self):
        if not self._current_preview_path: return
        if self._video_player: self._video_player.pause()
        FullscreenVideoPlayer(self, self._current_preview_path)
    def _draw_preview_placeholder(self):
        """The empty preview says what to do, not merely that it is empty."""
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(PREVIEW_W//2, PREVIEW_H//2 - 16,
            text="\U0001f5bc", fill=BORDER, font=font(30))
        self.preview_canvas.create_text(PREVIEW_W//2, PREVIEW_H//2 + 24,
            text=t("select_file"), fill=MUTED, font=font(SIZE_SMALL),
            justify="center")

    def _show_preview(self, filepath):
        if self._video_player: self._video_player.stop()
        ext=Path(filepath).suffix.lower()
        self.preview_canvas.delete("all")
        self._badge_360.pack_forget(); self._badge_raw.pack_forget()
        self._lbl_click_enlarge.pack_forget(); self._video_ctrl_frame.pack_forget()
        self._current_is_360=False; self._current_is_video=False; self._current_is_raw=False

        if ext in RAW_EXTS:
            self._current_is_raw=True
            self._badge_raw.pack(anchor="center",pady=(0,2))
            self._lbl_click_enlarge.pack(anchor="center",pady=(0,4))
            self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2-15,text="\u23f3",fill=MUTED,font=font(26))
            self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2+25,text=t("decoding_raw"),fill=MUTED,font=font(SIZE_SMALL))
            threading.Thread(target=self._load_raw_preview,args=(filepath,),daemon=True).start()
            return

        if ext in IMAGE_EXTS:
            try:
                from PIL import Image, ImageTk
                img=Image.open(filepath); self._current_is_360=is_360_image(filepath)
                img.thumbnail((PREVIEW_W-4,PREVIEW_H-4),Image.LANCZOS)
                self._preview_img=ImageTk.PhotoImage(img); tw,th=img.size
                self.preview_canvas.create_image((PREVIEW_W-tw)//2,(PREVIEW_H-th)//2,anchor="nw",image=self._preview_img)
                if self._current_is_360: self._badge_360.pack(anchor="center",pady=(0,2))
                self._lbl_click_enlarge.pack(anchor="center",pady=(0,4)); return
            except Exception: pass

        if ext in VIDEO_EXTS:
            self._current_is_video=True
            self._video_ctrl_frame.pack(fill="x",pady=(0,4))
            self._play_btn.config(text="\u25b6",bg=DANGER)
            self._seek_var.set(0.0); self._time_lbl.config(text="0:00 / 0:00")
            self._muted=False; self._mute_btn.config(text="\U0001f50a",fg=TEXT); self._vol_var.set(1.0)
            self._video_player.load(filepath,on_state_change=self._on_video_state)
            return

        # The icon says what kind of file it is; the colour is taken from the
        # category palette so it matches the bars and the table on the left.
        icons={"audio":"\U0001f3b5","code":"\u2328","docs":"\U0001f4c4",
               "data":"\U0001f4ca","archives":"\U0001f4e6","other":"\U0001f4ce"}
        cat=get_category(ext)
        icon=icons.get(cat,"\U0001f4c4"); color=EXTENSION_COLORS.get(cat,MUTED)
        self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2-20,text=icon,fill=color,font=font(46))
        self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2+30,text=ext.upper() if ext else "?",fill=color,font=font(SIZE_TITLE, "bold"))

    def _load_raw_preview(self, filepath):
        img = open_raw_thumbnail(filepath)
        if img:
            from PIL import ImageTk
            img.thumbnail((PREVIEW_W-4,PREVIEW_H-4))
            tk_img = ImageTk.PhotoImage(img)
            def show():
                self._preview_img=tk_img; self.preview_canvas.delete("all")
                tw,th=img.size; self.preview_canvas.create_image((PREVIEW_W-tw)//2,(PREVIEW_H-th)//2,anchor="nw",image=self._preview_img)
            self.after(0,show)
        else:
            def show_err():
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2-15,text="\U0001f39e",fill=BLUE,font=font(28))
                self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2+20,
                    text=t("rawpy_required"),fill=MUTED,font=font(SIZE_MICRO),justify="center")
            self.after(0,show_err)

    def _on_preview_click(self, event=None):
        path=self._current_preview_path
        if not path: return
        ext=Path(path).suffix.lower()
        if ext in RAW_EXTS or ext in IMAGE_EXTS:
            if self._current_is_360: Viewer360(self,path)
            else: FullscreenViewer(self,path)
        elif ext in VIDEO_EXTS:
            self._toggle_play()

    def _show_meta(self, rows):
        """Render the metadata panel from ``(i18n key, value)`` pairs."""
        for w in self.meta_inner.winfo_children():
            w.destroy()
        if not rows:
            tr(tk.Label(self.meta_inner, bg=SURFACE, fg=MUTED,
                        font=font(SIZE_MICRO)),
               "no_metadata").pack(anchor="w", padx=8, pady=4)
            return
        for key, value in rows:
            row = tk.Frame(self.meta_inner, bg=SURFACE)
            row.pack(fill="x", padx=6, pady=1)
            tr(tk.Label(row, bg=SURFACE, fg=MUTED, font=font(SIZE_MICRO),
                        width=14, anchor="w"), key).pack(side="left")
            tk.Label(row, text=str(value), bg=SURFACE, fg=TEXT,
                     font=font(SIZE_MICRO), anchor="w",
                     wraplength=155).pack(side="left", fill="x", expand=True)

    #: Column id -> (i18n key, width). Ids are stable; only the labels change.
    COLUMNS = {
        "name": ("col_name", 250),
        "ext": ("col_extension", 75),
        "size": ("col_size", 85),
        "mtime": ("col_date", 125),
        "iso": ("col_iso", 60),
        "focal_length": ("col_focal", 80),
        "model": ("col_device", 140),
        "make": ("col_brand", 100),
        "aperture": ("col_aperture", 75),
        "exposure": ("col_exposure", 85),
    }

    def _setup_file_tree_cols(self, cols):
        """Install *cols* on the file tree, with translated headings.

        This runs again on every category change, so the headings must come
        from the catalog: hardcoding them here is what made the table flip back
        to French after switching to English.
        """
        self.file_tree.configure(columns=cols)
        for col in cols:
            key, width = self.COLUMNS.get(col, (col, 100))
            self.file_tree.heading(col, text=t(key),
                                   command=lambda c=col: self._sort_files_by(c))
            self.file_tree.column(col, width=width,
                                  anchor="w" if col == "name" else "center")

    #: ttk style shared by every filter dropdown in the bar.
    FILTER_COMBO_STYLE = "Filter.TCombobox"

    def _install_filter_combo_style(self):
        """Dark styling for the filter dropdowns.

        A ttk Combobox ignores ``bg``/``fg``, so left alone it renders in the
        platform's light theme -- three white boxes in the middle of a dark
        toolbar, which is how it looked before.
        """
        st = ttk.Style()
        st.configure(self.FILTER_COMBO_STYLE,
                     fieldbackground=SURFACE2, background=SURFACE2,
                     foreground=TEXT, selectbackground=SURFACE2,
                     selectforeground=TEXT, arrowcolor=PRIMARY,
                     borderwidth=0, relief="flat", padding=(6, 3))
        st.map(self.FILTER_COMBO_STYLE,
               fieldbackground=[(("readonly",), SURFACE2)],
               background=[(("active",), SURFACE3)],
               foreground=[(("readonly",), TEXT)])

    def _filter_combo(self, value, values, width=11):
        """One dropdown in the filter bar, already styled and wired."""
        var = tk.StringVar(value=value)
        combo = ttk.Combobox(self.filter_bar, textvariable=var, values=values,
                             width=width, state="readonly",
                             style=self.FILTER_COMBO_STYLE, font=font(SIZE_SMALL))
        combo.pack(side="left", padx=(SP_S, SP_M + SP_S))
        combo.bind("<<ComboboxSelected>>", lambda *_: self._apply_file_filter())
        return var, combo

    def _build_filter_bar_base(self):
        for w in self.filter_bar.winfo_children(): w.destroy()
        self._install_filter_combo_style()
        self._filter_widgets={}
        self._lbl_filter_name=tk.Label(self.filter_bar,text=t("filter_name"),
                                       bg=SURFACE,fg=MUTED,font=font(SIZE_MICRO))
        self._lbl_filter_name.pack(side="left")
        v=tk.StringVar(); v.trace_add("write",lambda *_:self._apply_file_filter())
        tk.Entry(self.filter_bar,textvariable=v,bg=SURFACE2,fg=TEXT,
                 insertbackground=PRIMARY,relief="flat",highlightthickness=0,
                 font=font(SIZE_SMALL),width=15).pack(side="left",ipady=SP_S,
                                                      padx=(SP_S,SP_M+SP_S))
        self._filter_widgets["name"]=(v,None)
        self._lbl_filter_ext=tk.Label(self.filter_bar,text=t("filter_ext"),
                                      bg=SURFACE,fg=MUTED,font=font(SIZE_MICRO))
        self._lbl_filter_ext.pack(side="left")
        self._filter_widgets["ext"]=self._filter_combo(t("filter_all"),
                                                       [t("filter_all")], width=10)
        self._exif_lbl=tk.Label(self.filter_bar,text="",bg=SURFACE,fg=ORANGE,
                                font=font(SIZE_MICRO))
        self._exif_lbl.pack(side="right",padx=(0,SP_M))
        self._btn_reset_filter=tk.Button(self.filter_bar,text=t("reset"),bg=SURFACE2,
                  fg=MUTED,relief="flat",bd=0,highlightthickness=0,
                  font=font(SIZE_MICRO),padx=SP_M,pady=SP_S,cursor="hand2",
                  command=self._reset_file_filters)
        self._btn_reset_filter.pack(side="right")
        hover(self._btn_reset_filter, SURFACE2, SURFACE3, MUTED, TEXT)
        Tooltip(self._btn_reset_filter, lambda: t("tip_reset_filters"))

    def _add_exif_filters(self):
        """Add the per-EXIF-field combos shown for image categories."""
        for field in FILTER_FIELDS:
            tr(tk.Label(self.filter_bar, bg=SURFACE, fg=MUTED,
                        font=font(SIZE_MICRO)),
               EXIF_FILTER_LABELS[field]).pack(side="left")
            self._filter_widgets[field] = self._filter_combo(
                t("filter_all2"), [t("filter_all2")], width=10)

    def _populate_exif_combos(self):
        for field in FILTER_FIELDS:
            if field not in self._filter_widgets:
                continue
            var, combo = self._filter_widgets[field]
            values = sorted({f["meta"][field] for f in self._file_rows
                             if f.get("meta", {}).get(field)})
            combo["values"] = [t("filter_all2")] + values
            combo.current(ALL_INDEX)

    def _reset_file_filters(self):
        for _key, (var, combo) in self._filter_widgets.items():
            if combo is None:
                var.set("")
            else:
                combo.current(ALL_INDEX)
        self._apply_file_filter()

    def show_results(self, result):
        """Render a :class:`~strucnode.core.scanner.ScanResult`.

        The raw numbers are kept on the instance so the cards, bars and status
        line can be re-rendered in another language without rescanning.
        """
        self._scan_result = result
        self._cat_files = result.by_category
        self._all_files = result.files
        self._active_cat = None
        self._active_ext_filter = None

        self._summary_card_data = [
            ("card_files", f"{result.total_files:,}", PRIMARY),
            ("card_subfolders", f"{result.total_dirs:,}", ORANGE),
            ("card_total_size", None, SUCCESS),      # None -> formatted below
            ("card_extensions", f"{len(result.ext_count):,}", PURPLE),
        ]
        counts, sizes = defaultdict(int), defaultdict(int)
        for ext, count in result.ext_count.items():
            cat = get_category(ext)
            counts[cat] += count
            sizes[cat] += result.ext_size[ext]
        self._category_data = [
            (cat, count, result.total_files, EXTENSION_COLORS.get(cat, MUTED), sizes[cat])
            for cat, count in sorted(counts.items(), key=lambda kv: -kv[1])
        ]
        self._all_ext_rows = [
            (ext, get_category(ext), count, result.ext_size[ext],
             (count / result.total_files * 100) if result.total_files else 0)
            for ext, count in result.ext_count.items()
        ]

        self._render_summary()
        self._render_categories()
        self._apply_ext_filter()
        if self.on_scan_done:
            self.on_scan_done(result)

    def _render_summary(self):
        """(Re)draw the summary cards in the active language."""
        for w in self.summary_frame.winfo_children():
            w.destroy()
        total_size = self._scan_result.total_size if self._scan_result else 0
        for key, value, color in self._summary_card_data:
            self._card(self.summary_frame, t(key),
                       fmt_size(total_size) if value is None else value, color)

    def _render_categories(self):
        """(Re)draw the per-category bars in the active language."""
        for w in self.cat_frame.winfo_children():
            w.destroy()
        for cat, count, total, color, size in self._category_data:
            self._cat_bar(self.cat_frame, cat, count, total, color, size)

    def _card(self,parent,label,value,color):
        """One statistic, with the colour of its metric carried by an edge bar.

        The four cards used to differ only by the colour of their number,
        which made the column read as one block of text. A coloured edge gives
        each card an outline the eye can land on before reading anything.
        """
        outer=tk.Frame(parent,bg=SURFACE); outer.pack(fill="x",pady=(0,SP_S+2))
        tk.Frame(outer,bg=color,width=3).pack(side="left",fill="y")
        f=tk.Frame(outer,bg=SURFACE,pady=SP_M,padx=SP_M+2)
        f.pack(side="left",fill="both",expand=True)
        tk.Label(f,text=label,bg=SURFACE,fg=MUTED,
                 font=font(SIZE_MICRO)).pack(anchor="w")
        tk.Label(f,text=value,bg=SURFACE,fg=color,
                 font=font(SIZE_H1+4,"bold")).pack(anchor="w",pady=(1,0))

    #: Height of the share-of-total bar under each category row.
    CAT_BAR_H = 4

    def _cat_bar(self,parent,cat,count,total,color,cat_size=0):
        """A clickable category row: name, count, and its share of the scan."""
        active = (cat == self._active_cat)
        base = SURFACE2 if active else SURFACE
        f=tk.Frame(parent,bg=base,pady=SP_S+2,padx=SP_M,cursor="hand2")
        f.pack(fill="x",pady=(0,SP_S))
        row=tk.Frame(f,bg=base); row.pack(fill="x")
        dot=tk.Label(row,text="\u25cf",bg=base,fg=color,font=font(SIZE_SMALL))
        dot.pack(side="left")
        lbl=tk.Label(row,text=f"  {category_label(cat)}",bg=base,fg=TEXT,
                     font=font(SIZE_SMALL,"bold" if active else "normal"))
        lbl.pack(side="left")
        cnt_lbl=tk.Label(row,text=f"{count:,}  \u2022  {fmt_size(cat_size)}",bg=base,
                         fg=color,font=font(SIZE_SMALL,"bold"))
        cnt_lbl.pack(side="right")
        bar_bg=tk.Frame(f,bg=BORDER_SOFT,height=self.CAT_BAR_H)
        bar_bg.pack(fill="x",pady=(SP_S,0))
        share = (count / total) if total else 0
        # The bar is placed by ratio rather than by pixel width: measuring the
        # parent here returned a stale width on the first render, which made
        # every category look the same size until the window was resized.
        tk.Frame(bar_bg,bg=color,height=self.CAT_BAR_H).place(
            x=0,y=0,relwidth=max(0.015,share),relheight=1.0)
        widgets=(f,row,bar_bg,dot,lbl,cnt_lbl)

        def repaint(bg):
            for w in widgets:
                try:
                    w.configure(bg=bg)
                except tk.TclError:
                    pass

        def on_enter(_e): repaint(SURFACE3 if active else SURFACE2)
        def on_leave(_e): repaint(base)
        for w in widgets:
            w.bind("<Enter>",on_enter); w.bind("<Leave>",on_leave)
            w.bind("<Button-1>",lambda e,c=cat:self._load_category(c,ext_filter=None))
        Tooltip(f, lambda c=cat, n=count, sh=share:
                t("tip_category", cat=category_label(c), n=n, pct=round(sh*100, 1)))

    def _on_ext_row_click(self,event):
        sel=self.ext_tree.selection()
        if not sel: return
        vals=self.ext_tree.item(sel[0],"values")
        if vals: self._load_category(get_category(vals[0]),ext_filter=vals[0])

    def _load_category(self,cat,ext_filter=None):
        self._active_cat=cat; self._active_ext_filter=ext_filter
        self._render_categories()
        files=self._cat_files.get(cat,[]); self._file_rows=files
        color=EXTENSION_COLORS.get(cat,MUTED)
        label=category_label(cat)+(f"  /  {ext_filter}" if ext_filter else "")
        tr(self.file_section_lbl, "files_section", label=label)
        self.file_section_lbl.config(fg=color)
        is_img=(cat=="images")
        new_cols=self._file_cols_base+(self._file_cols_exif if is_img else ())
        self._file_cols=new_cols; self._setup_file_tree_cols(new_cols)
        self._build_filter_bar_base()
        if is_img: self._add_exif_filters()
        exts=sorted({f["ext"] for f in files})
        var,combo=self._filter_widgets["ext"]; combo["values"]=[t("filter_all")]+exts
        if ext_filter and ext_filter in exts:
            combo.current(exts.index(ext_filter) + 1)
        else:
            combo.current(ALL_INDEX)
        self._apply_file_filter()
        if is_img:
            self._exif_lbl.config(text=t("reading_exif"))
            threading.Thread(target=self._load_exif_bg,daemon=True).start()

    def _load_exif_bg(self):
        """Read EXIF for the visible rows. Runs on a worker thread.

        The work is I/O bound, so a small pool beats reading one file at a
        time; the rows are mutated in place and the table is refreshed once.
        """
        pending = [f for f in self._file_rows if not f["meta"]]
        if pending:
            with ThreadPoolExecutor(max_workers=EXIF_WORKERS) as pool:
                metas = pool.map(read_exif, [f["path"] for f in pending])
                for info, meta in zip(pending, metas, strict=False):
                    info["meta"] = meta
        self.after(0, self._on_exif_loaded)

    def _on_exif_loaded(self): self._exif_lbl.config(text=""); self._populate_exif_combos(); self._apply_file_filter()


    def _clear_file_panel(self):
        self.file_section_lbl.config(text=t("files_select"),fg=MUTED)
        self.file_count_lbl.config(text=""); self.file_tree.delete(*self.file_tree.get_children())
        self.path_lbl.pack_forget(); self._draw_preview_placeholder(); self._show_meta([])
        self._badge_360.pack_forget(); self._badge_raw.pack_forget()
        self._lbl_click_enlarge.pack_forget(); self._video_ctrl_frame.pack_forget(); self._current_preview_path=None

    def _selected_filter(self, key):
        """Return the value picked in filter *key*, or None for "all".

        The choice is read from the combo's *index*, so it never depends on how
        the "all" entry happens to be spelled in the active language.
        """
        entry = self._filter_widgets.get(key)
        if entry is None:
            return None
        var, combo = entry
        if combo is None:
            return var.get() or None
        return None if combo.current() <= ALL_INDEX else var.get()

    def _apply_file_filter(self):
        """Re-render the file table for the current filters and sort order.

        The "all values" choice is detected by combo index, never by comparing
        the widget's text to a translation: comparing against "Toutes" while
        the combo displayed "All" silently emptied the table in English.
        """
        widgets = self._filter_widgets
        name_q = widgets["name"][0].get().lower().strip() if "name" in widgets else ""
        ext_q = self._selected_filter("ext")
        exif_q = {f: self._selected_filter(f) for f in FILTER_FIELDS if f in widgets}
        exif_q = {f: v for f, v in exif_q.items() if v is not None}

        rows = []
        for info in self._file_rows:
            if name_q and name_q not in info["name"].lower():
                continue
            if ext_q is not None and info["ext"] != ext_q:
                continue
            meta = info.get("meta", {})
            if any(meta.get(field, "") != value for field, value in exif_q.items()):
                continue
            rows.append(info)

        col, reverse = self._file_sort_col, self._file_sort_rev
        if col == "size":
            rows.sort(key=lambda x: x["size_bytes"], reverse=reverse)
        elif col == "mtime":
            rows.sort(key=lambda x: x["mtime_ts"], reverse=reverse)
        elif col in FILTER_FIELDS or col in FIELD_LABELS:
            rows.sort(key=lambda x: x.get("meta", {}).get(col, ""), reverse=reverse)
        else:
            rows.sort(key=lambda x: str(x.get(col, "")).lower(), reverse=reverse)

        self.file_tree.delete(*self.file_tree.get_children())
        for info in rows:
            meta = info.get("meta", {})
            values = (info["name"], info["ext"], fmt_size(info["size_bytes"]),
                      format_mtime(info["mtime_ts"]))
            if self._active_cat == "images":
                values += tuple(meta.get(f, "") for f in self._file_cols_exif)
            self.file_tree.insert("", "end", iid=info["path"], values=values)

        shown, total = len(rows), len(self._file_rows)
        color = EXTENSION_COLORS.get(self._active_cat, MUTED)
        tr(self.file_count_lbl, "files_count", n=shown, t=total)
        self.file_count_lbl.config(fg=color if shown < total else MUTED)

    def _sort_files_by(self,col):
        self._file_sort_rev=not self._file_sort_rev if self._file_sort_col==col else False
        self._file_sort_col=col; self._apply_file_filter()

    def _apply_ext_filter(self):
        q=self.ext_filter_var.get().lower().strip()
        rows=[r for r in self._all_ext_rows if not q or q in r[0].lower() or q in r[1].lower()]
        ci={"extension":0,"category":1,"count":2,"size":3,"percent":4}
        rows.sort(key=lambda r:r[ci[self._ext_sort_col]],reverse=self._ext_sort_rev)
        self.ext_tree.delete(*self.ext_tree.get_children())
        for ext,cat,cnt,sz,pct in rows:
            tag=f"c_{cat}"
            self.ext_tree.insert("","end",iid=f"{ext}||{cat}",
                values=(ext,category_label(cat),f"{cnt:,}",fmt_size(sz),f"{pct:.1f}%"),tags=(tag,))
            self.ext_tree.tag_configure(tag,foreground=EXTENSION_COLORS.get(cat,MUTED))

    def _sort_ext_by(self,col):
        self._ext_sort_rev=not self._ext_sort_rev if self._ext_sort_col==col else True
        self._ext_sort_col=col; self._apply_ext_filter()

    def _on_file_select(self, event):
        """Show the preview and metadata panel for the selected row."""
        selection = self.file_tree.selection()
        if not selection:
            return
        path = selection[0]
        self._current_preview_path = path
        self.path_lbl.config(text=f"  {path}")
        self.path_lbl.pack(fill="x", side="bottom")
        self._show_preview(path)

        info = next((f for f in self._file_rows if f["path"] == path), None)
        if info is None:
            return
        # Keys are i18n keys, resolved by _show_meta, so the panel follows the
        # language instead of being stuck in the one used when it was built.
        rows = [("meta_name", info["name"]),
                ("meta_size", fmt_size(info["size_bytes"])),
                ("meta_modified", format_mtime(info["mtime_ts"])),
                ("meta_type", info["ext"].upper())]
        if self._current_is_360:
            rows.append(("meta_360", t("meta_360_yes")))
        if self._current_is_raw:
            rows.append(("meta_format", "RAW"))
        meta = info.get("meta", {}) or {}
        rows += [(FIELD_LABELS[field], meta[field])
                 for field in FIELD_LABELS if meta.get(field)]
        self._show_meta(rows)

    def _open_selected_file(self, event):
        selection = self.file_tree.selection()
        if selection:
            error = open_file(selection[0])
            if error:
                messagebox.showerror(t("error"), error, parent=self)

    def refresh_lang(self):
        """Re-render what a plain text binding cannot reach."""
        try:
            for col, (key, _width) in self.COLUMNS.items():
                if col in self._file_cols:
                    self.file_tree.heading(col, text=t(key))
            for col, key in [("extension", "col_extension"), ("category", "col_category"),
                             ("count", "col_files"), ("size", "col_total_size"),
                             ("percent", "col_percent")]:
                self.ext_tree.heading(col, text=t(key))
        except tk.TclError:
            log.debug("explorer trees gone", exc_info=True)
        if self._scan_result is not None:
            self._render_summary()
            self._render_categories()
            self._apply_ext_filter()
        if self._active_cat:
            self._load_category(self._active_cat, self._active_ext_filter)
