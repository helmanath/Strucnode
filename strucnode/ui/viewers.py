"""Fullscreen viewers: video, still image, and 360 degree panorama."""

from __future__ import annotations

import logging
import math
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..core.categories import RAW_EXTS
from ..i18n import t
from ..media.images import open_raw_thumbnail
from ..media.video import VideoPlayer
from ..theme import BORDER, MUTED, ORANGE, SUCCESS, SURFACE2, TEXT

log = logging.getLogger(__name__)


class FullscreenVideoPlayer(tk.Toplevel):
    """Fullscreen window that wraps `VideoPlayer` with transport and audio controls."""

    def __init__(self, parent, filepath):
        super().__init__(parent)
        self.title(Path(filepath).name)
        self.configure(bg="black"); self.attributes("-fullscreen", True)
        self._seek_var = tk.DoubleVar(value=0.0); self._muted = False

        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        bar = tk.Frame(self, bg="#0e0e0e"); bar.pack(side="bottom", fill="x")
        s = ttk.Style(self)
        s.configure("FS.Horizontal.TScale", background="#0e0e0e",
                    troughcolor="#393836", sliderlength=14, sliderrelief="flat")
        ttk.Scale(bar, from_=0, to=1, orient="horizontal", variable=self._seek_var,
                  command=self._on_seek, style="FS.Horizontal.TScale").pack(fill="x", padx=12, pady=(6,2))
        btn_row = tk.Frame(bar, bg="#0e0e0e"); btn_row.pack(fill="x", padx=12, pady=(0,8))
        self._play_btn = tk.Button(btn_row, text="\u23f8", fg=SUCCESS, bg="#0e0e0e",
            relief="flat", font=("Segoe UI",13,"bold"), width=3,
            cursor="hand2", activebackground="#0e0e0e", command=self._toggle_play)
        self._play_btn.pack(side="left", padx=(0,8))
        self._time_lbl = tk.Label(btn_row, text="0:00 / 0:00", bg="#0e0e0e", fg=MUTED, font=("Segoe UI",10))
        self._time_lbl.pack(side="left", padx=(0,16))
        self._mute_btn = tk.Button(btn_row, text="\U0001f50a", fg=TEXT, bg="#0e0e0e", relief="flat",
            font=("Segoe UI",12), cursor="hand2",
            activebackground="#0e0e0e", command=self._toggle_mute)
        self._mute_btn.pack(side="left")
        self._vol_var = tk.DoubleVar(value=1.0)
        ttk.Scale(btn_row, from_=0, to=1, orient="horizontal", variable=self._vol_var,
                  command=self._on_volume, style="FS.Horizontal.TScale", length=90).pack(side="left", padx=(4,16))
        tk.Button(btn_row, text=t("close_btn"), bg="#3a2020", fg="#dd6974", relief="flat",
            font=("Segoe UI",10), padx=12, pady=2, cursor="hand2",
            command=self._close).pack(side="right")
        tk.Label(btn_row, text=t("video_hint"),
            bg="#0e0e0e", fg=MUTED, font=("Segoe UI",8)).pack(side="right", padx=12)

        self.bind("<Escape>", lambda e: self._close())
        self.bind("<space>", lambda e: self._toggle_play())
        self.canvas.bind("<Escape>", lambda e: self._close())
        self.canvas.bind("<space>", lambda e: self._toggle_play())
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        self.canvas.focus_set()  # make sure the canvas has focus on startup

        self.update_idletasks()
        cw = self.winfo_screenwidth(); ch = self.winfo_screenheight() - 80
        self._player = VideoPlayer(self.canvas, cw, ch)
        self._player.load(filepath, on_state_change=self._on_state)
        self.after(700, self._auto_play)
        self._update_bar()

    def _auto_play(self):
        try:
            if not self.winfo_exists(): return
            self._player.play()
            self._play_btn.config(text="\u23f8", fg=SUCCESS)
        except Exception:
            pass

    def _on_state(self, playing):
        try:
            if not self.winfo_exists(): return
            self._play_btn.config(text="\u23f8" if playing else "\u25b6", fg=SUCCESS if playing else "#dd6974")
        except Exception:
            pass

    def _toggle_play(self): self._player.toggle()
    def _on_seek(self, val): self._player.seek(float(val))

    def _toggle_mute(self):
        self._muted = not self._muted
        self._player.set_muted(self._muted)
        self._mute_btn.config(text="\U0001f507" if self._muted else "\U0001f50a",
                              fg="#dd6974" if self._muted else TEXT)

    def _on_volume(self, val):
        v = float(val); self._player.set_volume(v)
        if v == 0: self._muted=True; self._mute_btn.config(text="\U0001f507",fg="#dd6974")
        elif self._muted:
            self._muted=False; self._player.set_muted(False); self._mute_btn.config(text="\U0001f50a",fg=TEXT)

    def _update_bar(self):
        try:
            if not self.winfo_exists(): return
            self._seek_var.set(self._player.progress)
            self._time_lbl.config(text=self._player.time_str)
            self.after(150, self._update_bar)
        except Exception:
            pass

    def _close(self):
        self._player.stop(); self.destroy()
class FullscreenViewer(tk.Toplevel):
    """Fullscreen still-image viewer with zoom, pan, rotation, and mirroring tools."""

    def __init__(self, parent, filepath):
        super().__init__(parent)
        self.title(Path(filepath).name); self.configure(bg="black"); self.attributes("-fullscreen", True)
        self.filepath = filepath
        self._zoom=1.0; self._offset=[0,0]; self._drag_start=None
        self._orig=None; self._rotation=0; self._flip_h=False; self._flip_v=False; self._tk_img=None
        self._is_raw = Path(filepath).suffix.lower() in RAW_EXTS
        self._build_ui()
        threading.Thread(target=self._load_image, daemon=True).start()

    def _build_ui(self):
        bar=tk.Frame(self,bg="#111110",pady=8,padx=10); bar.pack(side="bottom",fill="x")
        self.canvas=tk.Canvas(self,bg="black",highlightthickness=0); self.canvas.pack(fill="both",expand=True)
        bc=dict(bg=SURFACE2,fg=TEXT,relief="flat",font=("Segoe UI",10),padx=10,pady=4,cursor="hand2",activebackground=BORDER,activeforeground=TEXT)
        def sep(): tk.Label(bar,text="|",bg="#111110",fg=BORDER,font=("Segoe UI",12)).pack(side="left",padx=3)
        tk.Button(bar,text=t("close_btn"),bg="#3a2020",fg="#dd6974",relief="flat",font=("Segoe UI",10),padx=12,pady=4,cursor="hand2",command=self.destroy).pack(side="right",padx=(6,0))
        tk.Label(bar,text=t("viewer_hint"),bg="#111110",fg=MUTED,font=("Segoe UI",8)).pack(side="right",padx=12)
        self._rot_lbl=tk.Label(bar,text="0\u00b0",bg="#111110",fg=ORANGE,font=("Segoe UI",11,"bold"),width=8); self._rot_lbl.pack(side="left",padx=(0,8))
        tk.Button(bar,text="\u21ba 90\u00b0",**bc,command=lambda:self._rotate(-90)).pack(side="left",padx=2)
        tk.Button(bar,text="\u21bb 90\u00b0",**bc,command=lambda:self._rotate(90)).pack(side="left",padx=2)
        tk.Button(bar,text="\u21d5 180\u00b0",**bc,command=lambda:self._rotate(180)).pack(side="left",padx=2)
        sep()
        tk.Button(bar,text="\u21d4 H",**bc,command=self._flip_horizontal).pack(side="left",padx=2)
        tk.Button(bar,text="\u21d5 V",**bc,command=self._flip_vertical).pack(side="left",padx=2)
        sep()
        tk.Button(bar,text="\u21ba Reset",bg=SURFACE2,fg=ORANGE,relief="flat",font=("Segoe UI",10),padx=10,pady=4,cursor="hand2",activebackground=BORDER,command=self._reset).pack(side="left",padx=2)
        if self._is_raw: tk.Label(bar,text="RAW",bg=ORANGE,fg="#1c1b19",font=("Segoe UI",8,"bold"),padx=6,pady=2).pack(side="left",padx=6)
        self.bind("<Escape>",lambda e:self.destroy())
        self.canvas.bind("<ButtonPress-1>",self._drag_start_cb)
        self.canvas.bind("<B1-Motion>",self._drag_move_cb)
        self.canvas.bind("<ButtonRelease-1>",self._drag_end_cb)
        self.canvas.bind("<MouseWheel>",lambda e:self._zoom_step(1.1 if e.delta>0 else 0.9))

    # RAW files need a separate loading path because Pillow alone cannot decode many camera formats.
    def _load_image(self):
        try:
            if self._is_raw:
                img = open_raw_thumbnail(self.filepath)
                if img is None: raise RuntimeError(t("raw_decode_failed"))
            else:
                from PIL import Image
                img = Image.open(self.filepath)
            self._orig = img; self.after(0, self._fit_and_draw)
        except Exception as exc: self.after(0, lambda e=exc: messagebox.showerror(t("error"), str(e), parent=self))

    # Transformations are applied on a copy to preserve the original image as the single source of truth.
    def _get_transformed(self):
        from PIL import Image
        img = self._orig.copy()
        if self._flip_h: img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if self._flip_v: img = img.transpose(Image.FLIP_TOP_BOTTOM)
        if self._rotation: img = img.rotate(-self._rotation, expand=True)
        return img

    def _fit_and_draw(self):
        if not self._orig: return
        self.update_idletasks()
        cw,ch = self.canvas.winfo_width(),self.canvas.winfo_height()
        img = self._get_transformed()
        self._zoom=min(cw/img.width,ch/img.height); self._offset=[0,0]; self._draw()

    # Rendering is recomputed on every zoom, pan, rotation, or flip event for simplicity and correctness.
    def _draw(self):
        if not self._orig: return
        from PIL import Image, ImageTk
        self.update_idletasks()
        cw,ch = self.canvas.winfo_width(),self.canvas.winfo_height()
        img = self._get_transformed()
        nw,nh = max(1,int(img.width*self._zoom)),max(1,int(img.height*self._zoom))
        self._tk_img = ImageTk.PhotoImage(img.resize((nw,nh),Image.LANCZOS))
        self.canvas.delete("all"); self.canvas.create_image(cw//2+self._offset[0],ch//2+self._offset[1],anchor="center",image=self._tk_img)

    def _rotate(self,d): self._rotation=(self._rotation+d)%360; self._rot_lbl.config(text=f"{self._rotation}\u00b0"); self._fit_and_draw()
    def _flip_horizontal(self): self._flip_h=not self._flip_h; self._draw()
    def _flip_vertical(self): self._flip_v=not self._flip_v; self._draw()
    def _reset(self): self._rotation=0; self._flip_h=False; self._flip_v=False; self._rot_lbl.config(text="0\u00b0"); self._offset=[0,0]; self._fit_and_draw()
    def _zoom_step(self,f): self._zoom=max(0.05,min(self._zoom*f,20)); self._draw()
    def _drag_start_cb(self,e): self._drag_start=(e.x,e.y)
    def _drag_move_cb(self,e):
        if self._drag_start:
            self._offset[0]+=e.x-self._drag_start[0]; self._offset[1]+=e.y-self._drag_start[1]
            self._drag_start=(e.x,e.y); self._draw()
    def _drag_end_cb(self,e): self._drag_start=None
class Viewer360(tk.Toplevel):
    """Fullscreen 360° panorama viewer rendered from an equirectangular source image."""

    FOV=90; SPEED=0.3
    def __init__(self,parent,filepath):
        super().__init__(parent); self.title(f"360\u00b0 \u2014 {Path(filepath).name}")
        self.configure(bg="black"); self.attributes("-fullscreen",True)
        self.filepath=filepath; self._yaw=0.0; self._pitch=0.0; self._fov=self.FOV; self._roll=0
        self._drag_start=None; self._pano=None; self._tk_img=None; self._rendering=False; self._pending=False
        bar=tk.Frame(self,bg="#111110",pady=7,padx=8); bar.pack(side="bottom",fill="x")
        self.canvas=tk.Canvas(self,bg="black",highlightthickness=0); self.canvas.pack(fill="both",expand=True)
        bc=dict(bg=SURFACE2,fg=TEXT,relief="flat",font=("Segoe UI",10),padx=9,pady=3,cursor="hand2",activebackground=BORDER,activeforeground=TEXT)
        def sep(): tk.Label(bar,text="|",bg="#111110",fg=BORDER,font=("Segoe UI",12)).pack(side="left",padx=3)
        tk.Label(bar,text="\U0001f310 360\u00b0",bg="#111110",fg=ORANGE,font=("Segoe UI",10,"bold")).pack(side="left",padx=(0,6)); sep()
        tk.Button(bar,text="\u21ba \u221290\u00b0",**bc,command=lambda:self._add_roll(-90)).pack(side="left",padx=2)
        tk.Button(bar,text="\u21bb +90\u00b0",**bc,command=lambda:self._add_roll(90)).pack(side="left",padx=2)
        self._roll_lbl=tk.Label(bar,text="0\u00b0",bg="#111110",fg=ORANGE,font=("Segoe UI",10,"bold"),width=5); self._roll_lbl.pack(side="left",padx=(2,4)); sep()
        tk.Button(bar,text="\u2b06",**bc,command=lambda:self._set_pitch(85)).pack(side="left",padx=2)
        tk.Button(bar,text="\u27a1",**bc,command=lambda:self._set_pitch(0)).pack(side="left",padx=2)
        tk.Button(bar,text="\u2b07",**bc,command=lambda:self._set_pitch(-85)).pack(side="left",padx=2); sep()
        tk.Button(bar,text="\u21ba Reset",bg=SURFACE2,fg=ORANGE,relief="flat",font=("Segoe UI",10),padx=9,pady=3,cursor="hand2",activebackground=BORDER,command=self._reset_view).pack(side="left",padx=2); sep()
        tk.Button(bar,text=t("close_btn"),bg="#3a2020",fg="#dd6974",relief="flat",font=("Segoe UI",10),padx=12,pady=3,cursor="hand2",command=self.destroy).pack(side="right",padx=(6,0))
        self._info_lbl=tk.Label(bar,text=t("loading"),bg="#111110",fg=MUTED,font=("Segoe UI",8)); self._info_lbl.pack(side="right",padx=8)
        self.bind("<Escape>",lambda e:self.destroy())
        self.bind("<Left>",lambda e:self._add_yaw(-15)); self.bind("<Right>",lambda e:self._add_yaw(15))
        self.bind("<Up>",lambda e:self._add_pitch(10)); self.bind("<Down>",lambda e:self._add_pitch(-10))
        self.canvas.bind("<ButtonPress-1>",lambda e:setattr(self,"_drag_start",(e.x,e.y)))
        self.canvas.bind("<B1-Motion>",self._drag_move)
        self.canvas.bind("<ButtonRelease-1>",lambda e:setattr(self,"_drag_start",None))
        self.canvas.bind("<MouseWheel>",self._scroll)
        self.canvas.bind("<Configure>",lambda e:self._request_render())
        threading.Thread(target=self._load,daemon=True).start()

    def _load(self):
        try:
            from PIL import Image
            img=Image.open(self.filepath).convert("RGB")
            if img.width>4096: img=img.resize((4096,2048),Image.LANCZOS)
            self._pano=img; self.after(0,self._request_render)
        except Exception as exc: self.after(0,lambda e=exc:messagebox.showerror(t("error"),str(e),parent=self))

    # Rendering is throttled through a pending flag so repeated user input does not spawn unlimited threads.
    def _request_render(self):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        if not self._rendering: self._pending=False; self._rendering=True; threading.Thread(target=self._render,daemon=True).start()
        else: self._pending=True

    # The panorama is sampled by projecting screen rays into spherical coordinates and remapping them into the source image.
    def _render(self):
        if not self._pano: self._rendering=False; return
        try:
            import numpy as np
            from PIL import Image
            self.update_idletasks(); cw,ch=self.canvas.winfo_width(),self.canvas.winfo_height()
            if cw<2 or ch<2: self._rendering=False; return
            rw=min(cw,1280); rh=int(rw*ch/cw); pano=self._pano; pw,ph=pano.size; pa=np.array(pano)
            fov=math.radians(self._fov); yaw=math.radians(self._yaw); pit=math.radians(max(-85,min(85,self._pitch)))
            xs=np.linspace(-1,1,rw); ys=np.linspace(1,-1,rh); xg,yg=np.meshgrid(xs,ys)
            f=1.0/math.tan(fov/2); asp=rw/rh; dx=xg*asp; dy=yg; dz=np.full_like(dx,f)
            if self._roll!=0:
                rl=math.radians(self._roll); cr,sr=math.cos(rl),math.sin(rl); dx,dy=dx*cr-dy*sr,dx*sr+dy*cr
            cp,sp=math.cos(pit),math.sin(pit); dy2=dy*cp-dz*sp; dz2=dy*sp+dz*cp
            cy2,sy2=math.cos(yaw),math.sin(yaw); dx3=dx*cy2+dz2*sy2; dz3=-dx*sy2+dz2*cy2; dy3=dy2
            nm=np.sqrt(dx3**2+dy3**2+dz3**2); dx3/=nm; dy3/=nm; dz3/=nm
            lon=np.arctan2(dx3,dz3); lat=np.arcsin(np.clip(dy3,-1,1))
            u=((lon/(2*math.pi))+0.5)%1.0; v=(lat/math.pi)+0.5
            px=np.clip((u*pw).astype(int),0,pw-1); py_=np.clip((v*ph).astype(int),0,ph-1)
            out=Image.fromarray(pa[py_,px].astype("uint8"),"RGB")
            if rw!=cw or rh!=ch: out=out.resize((cw,ch),Image.NEAREST)
            try:
                if self.winfo_exists():
                    self.after(0,lambda i=out:self._show(i))
                else:
                    self._rendering=False
            except Exception:
                self._rendering=False
        except Exception:
            log.warning("360 render failed", exc_info=True)
            self._rendering=False

    def _show(self,img):
        from PIL import ImageTk
        try:
            if not self.winfo_exists(): self._rendering=False; return
            if not self.canvas.winfo_exists(): self._rendering=False; return
        except Exception: self._rendering=False; return
        self._tk_img=ImageTk.PhotoImage(img); self.canvas.delete("all")
        self.canvas.create_image(0,0,anchor="nw",image=self._tk_img)
        self._info_lbl.config(text=f"Yaw:{self._yaw:.0f}\u00b0 Pitch:{self._pitch:.0f}\u00b0 Roll:{self._roll}\u00b0 FOV:{self._fov}\u00b0")
        self._rendering=False
        if self._pending: self._request_render()

    # Mouse drag updates yaw and pitch only; actual drawing stays delegated to the render request pipeline.
    def _drag_move(self,event):
        if self._drag_start:
            self._yaw=(self._yaw-(event.x-self._drag_start[0])*self.SPEED)%360
            self._pitch=max(-85,min(85,self._pitch-(event.y-self._drag_start[1])*self.SPEED))
            self._drag_start=(event.x,event.y); self._request_render()

    def _scroll(self,e): self._fov_step(-5 if e.delta>0 else 5)
    def _fov_step(self,d): self._fov=max(20,min(130,self._fov+d)); self._request_render()
    def _add_yaw(self,d): self._yaw=(self._yaw+d)%360; self._request_render()
    def _add_pitch(self,d): self._pitch=max(-85,min(85,self._pitch+d)); self._request_render()
    def _set_pitch(self,v): self._pitch=v; self._request_render()
    def _add_roll(self,d): self._roll=(self._roll+d)%360; self._roll_lbl.config(text=f"{self._roll}\u00b0"); self._request_render()
    def _reset_view(self): self._yaw=0.0; self._pitch=0.0; self._fov=self.FOV; self._roll=0; self._roll_lbl.config(text="0\u00b0"); self._request_render()


