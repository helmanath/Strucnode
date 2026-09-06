"""In-canvas video playback.

Frames come from ffmpeg when it is available (widest format support) and from
OpenCV otherwise; audio goes through sounddevice, with moviepy as a fallback
for extraction. Every backend is optional: without any of them the canvas
shows an explanatory placeholder instead of failing.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time

from ..i18n import t
from ..theme import DANGER, MUTED

log = logging.getLogger(__name__)


class VideoPlayer:
    """Low-level embedded video player used by preview canvases and fullscreen playback windows."""

    # Internal state groups playback state, decoding backends, audio buffers, and canvas sizing.
    def __init__(self, canvas, w, h):
        self.canvas = canvas; self.w = w; self.h = h
        self._cap = None
        self._playing = False
        self._muted = False
        self._volume = 1.0
        self._thread = None
        self._tk_img = None
        self._fps = 25.0
        self._frame_idx = 0
        self._total_frames = 0
        self._lock = threading.Lock()
        self._on_state_change = None
        self._audio_frames = None
        self._frame_queue  = None  # initialized in play()
        self._audio_pos = 0
        self._audio_sr = 44100
        self._audio_stream = None
        self._has_audio = False
        self._ffmpeg_proc        = None
        self._ffmpeg_first_frame = None
        self._use_ffmpeg         = False
        self._src_path           = None
        self._out_w              = w
        self._out_h              = h

    def _fire_state(self, playing):
        """Calls _on_state_change safely from any thread."""
        cb = self._on_state_change
        if not cb: return
        try:
            self.canvas.after(0, lambda: cb(playing) if self._on_state_change else None)
        except Exception:
            pass

    # Loading is asynchronous so heavy video probing does not freeze the Tkinter event loop.
    def load(self, path, on_state_change=None):
        self.stop()
        self._on_state_change = on_state_change
        threading.Thread(target=self._do_load, args=(path,), daemon=True).start()

    # Playback starts two loops: a decoding thread and a Tk-side display loop.
    def play(self):
        if not self._cap and not self._use_ffmpeg: return
        import queue as _q
        self._frame_queue = _q.Queue(maxsize=2)
        self._playing = True
        self._fire_state(True)
        threading.Thread(target=self._play_loop, daemon=True).start()
        self._tick()  # Start the display loop in the Tkinter thread
        if self._has_audio and not self._muted:
            self._start_audio()

    # Tkinter UI updates must stay on the main thread, so frames are consumed here from a queue.
    def _tick(self):
        """Display loop on the Tkinter thread: consumes _frame_queue."""
        if not self._playing:
            return
        try:
            img = self._frame_queue.get_nowait()
            self._put_frame(img)
        except Exception:
            pass  # Queue is empty during this cycle
        delay_ms = max(8, int(1000.0 / min(self._fps or 25.0, 60.0)))
        try:
            self.canvas.after(delay_ms, self._tick)
        except Exception:
            pass  # Canvas was destroyed

    def pause(self):
        self._playing = False
        self._stop_audio()
        self._fire_state(False)

    def toggle(self):
        if self._playing: self.pause()
        else: self.play()

    def stop(self):
        self._playing = False
        self._stop_audio()
        with self._lock:
            if self._cap: self._cap.release(); self._cap = None
        self._close_ffmpeg()
        self._use_ffmpeg   = False
        self._audio_frames = None; self._has_audio = False

    # Seeking reopens the FFmpeg pipe when needed because rawvideo pipes are forward-only.
    def seek(self, ratio):
        target = int(ratio * self._total_frames)
# FFmpeg streams cannot seek backwards cheaply, so the pipe is recreated at the target position.
        if self._use_ffmpeg and self._src_path:
            was_playing = self._playing
            self._playing = False
            time.sleep(0.05)
            self._frame_idx = target
            self._open_ffmpeg(self._src_path, self._out_w, self._out_h, start_frame=target)
            if was_playing:
                self._playing = True
                import queue as _q
                self._frame_queue = _q.Queue(maxsize=2)
                threading.Thread(target=self._play_loop, daemon=True).start()
                try: self.canvas.after(0, self._tick)
                except Exception: pass
            else:
                self._show_single_frame()
        else:
            with self._lock:
                if self._cap: self._cap.set(1, target); self._frame_idx = target
            if not self._playing: self._show_single_frame()
        if self._has_audio and self._audio_frames is not None:
            self._audio_pos = int(ratio * len(self._audio_frames))

    def set_muted(self, muted):
        self._muted = muted
        if muted: self._stop_audio()
        elif self._playing and self._has_audio: self._start_audio()

    def set_volume(self, vol):
        self._volume = max(0.0, min(1.0, float(vol)))

    @property
    def is_playing(self): return self._playing

    @property
    def progress(self):
        return (self._frame_idx / self._total_frames) if self._total_frames else 0.0

    @property
    def time_str(self):
        fps = self._fps or 25
        def fmt(s): return f"{int(s)//60}:{int(s)%60:02d}"
        return f"{fmt(self._frame_idx/fps)} / {fmt(self._total_frames/fps)}"

    # Prefer ffprobe for accurate metadata, then fall back to OpenCV when FFmpeg tools are unavailable.
    def _probe_video(self, path):
        """Returns (fps, total_frames, vw, vh) using ffprobe or cv2."""
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-select_streams", "v:0", path],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                import json as _json
                info = _json.loads(r.stdout)
                st   = info["streams"][0]
                vw   = int(st.get("width", 0))
                vh   = int(st.get("height", 0))
                nb   = int(st.get("nb_frames", 0) or 0)
                fr   = st.get("r_frame_rate", "25/1")
                try:
                    n, d = fr.split("/"); fps = float(n) / float(d)
                except Exception:
                    fps = 25.0
                return fps, nb, vw, vh
        except Exception:
            pass
        try:
            import cv2
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                fps   = cap.get(5) or 25.0
                total = int(cap.get(7))
                vw    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                vh    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                return fps, total, vw, vh
        except Exception:
            pass
        return 25.0, 0, self.w, self.h

    # FFmpeg is used as the fast path for resizing and decoding large or complex videos.
    def _open_ffmpeg(self, path, out_w, out_h, start_frame=0):
        """Opens a resized FFmpeg pipe. Returns True on success."""
        self._close_ffmpeg()
        try:
            seek_args = []
            if start_frame > 0 and self._fps:
                seek_seconds = start_frame / self._fps
                seek_args = ["-ss", f"{seek_seconds:.3f}"]
            cmd = [
                "ffmpeg",
                "-hwaccel", "auto",
                *seek_args,
                "-i", path,
                "-vf", f"scale={out_w}:{out_h}",
                "-pix_fmt", "rgb24",
                "-f", "rawvideo",
                "-an",
                "-loglevel", "quiet",
                "pipe:1"
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL,
                                    bufsize=out_w * out_h * 3 * 8)
            frame_bytes = out_w * out_h * 3
            import queue as _tq
            q = _tq.Queue()
            def _read():
                try: q.put(proc.stdout.read(frame_bytes))
                except Exception: q.put(b"")
            t = threading.Thread(target=_read, daemon=True); t.start()
            try:
                test = q.get(timeout=10)  # 10s max to start
            except _tq.Empty:
                test = b""
            if len(test) == frame_bytes:
                self._ffmpeg_proc        = proc
                self._ffmpeg_first_frame = test
                return True
            proc.kill(); proc.wait()
        except FileNotFoundError:
            pass  # FFmpeg not installed -> OpenCV fallback
        except Exception:
            pass
        return False

    def _close_ffmpeg(self):
        p = self._ffmpeg_proc
        self._ffmpeg_proc        = None
        self._ffmpeg_first_frame = None
        if p:
            try: p.kill(); p.wait(timeout=2)
            except Exception: pass

    # Backend selection happens here: FFmpeg first, OpenCV fallback second.
    def _do_load(self, path):
        self._src_path = path
        fps, total, vw, vh = self._probe_video(path)
        scale  = min(self.w / max(vw, 1), self.h / max(vh, 1))
        out_w  = max(2, int(vw * scale) & ~1)
        out_h  = max(2, int(vh * scale) & ~1)
        self._fps          = fps
        self._total_frames = total
        self._frame_idx    = 0
        self._out_w        = out_w
        self._out_h        = out_h
        if self._open_ffmpeg(path, out_w, out_h):
            self._use_ffmpeg = True
            with self._lock:
                self._cap = None
        else:
            self._use_ffmpeg = False
            try:
                import cv2
                cap = cv2.VideoCapture(path)
                if not cap.isOpened():
                    raise RuntimeError("Unable to open the video")
                with self._lock:
                    self._cap = cap
            except ImportError:
                self.canvas.after(0, self._show_no_cv2); return
            except Exception as exc:
                # Bind by value: `exc` is unbound once the except block ends,
                # and this lambda runs later on the Tk thread.
                self.canvas.after(0, lambda e=exc: self._show_error(str(e))); return

        self._show_single_frame()
        threading.Thread(target=self._load_audio, args=(path,), daemon=True).start()

    def _raw_to_tk(self, raw_bytes, w, h):
        import numpy as np
        from PIL import Image, ImageTk
        arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w, 3))
        return ImageTk.PhotoImage(Image.fromarray(arr))

    def _show_single_frame(self):
        if self._use_ffmpeg:
            raw = self._ffmpeg_first_frame
            if raw:
                img = self._raw_to_tk(raw, self._out_w, self._out_h)
                try: self.canvas.after(0, self._put_frame, img)
                except Exception: pass
            return
        with self._lock:
            if not self._cap: return
            ret, frame = self._cap.read()
            if ret:
                self._frame_idx = int(self._cap.get(1))
                img = self._cv2_to_tk(frame)
                try: self.canvas.after(0, self._put_frame, img)
                except Exception: pass

    # Decoding is intentionally decoupled from drawing to keep UI responsiveness stable.
    def _play_loop(self):
        """Decoding thread: fills self._frame_queue at the source FPS rate."""
        src_fps   = self._fps or 25.0
        src_delay = 1.0 / src_fps
        t_start   = time.monotonic()
        frames_read = 0

        if self._use_ffmpeg:
            proc       = self._ffmpeg_proc
            frame_size = self._out_w * self._out_h * 3
            out_w, out_h = self._out_w, self._out_h
            first = self._ffmpeg_first_frame
            if first:
                img = self._raw_to_tk(first, out_w, out_h)
                try: self._frame_queue.put(img, timeout=0.5)
                except Exception: pass
                frames_read += 1

            while self._playing:
                raw = proc.stdout.read(frame_size)
                if len(raw) < frame_size:
                    self._playing = False
                    self._stop_audio()
                    self._fire_state(False)
                    break
                frames_read    += 1
                self._frame_idx = frames_read
                img = self._raw_to_tk(raw, out_w, out_h)
                try:
                    self._frame_queue.put(img, timeout=0.5)
                except Exception:
                    pass
                next_t  = t_start + frames_read * src_delay
                sleep_t = next_t - time.monotonic()
                if sleep_t > 0.001:
                    time.sleep(sleep_t)
        else:
            RENDER_MAX  = 60.0
            step        = max(1, round(src_fps / RENDER_MAX))

            while self._playing:
                with self._lock:
                    if not self._cap:
                        break
                    display_frame = None
                    for _ in range(step):
                        ret, frame = self._cap.read()
                        if not ret:
                            self._cap.set(1, 0)
                            self._frame_idx = 0
                            self._audio_pos = 0
                            self._playing   = False
                            self._stop_audio()
                            self._fire_state(False)
                            break
                        frames_read    += 1
                        self._frame_idx = int(self._cap.get(1))
                        display_frame   = frame
                    if display_frame is None:
                        break

                img = self._cv2_to_tk(display_frame)
                try:
                    self._frame_queue.put(img, timeout=0.5)
                except Exception:
                    pass
                next_t  = t_start + frames_read * src_delay
                sleep_t = next_t - time.monotonic()
                if sleep_t > 0.001:
                    time.sleep(sleep_t)

    def _cv2_to_tk(self, frame):
        import cv2
        from PIL import Image, ImageTk
        fh, fw = frame.shape[:2]
        scale = min(self.w / fw, self.h / fh)
        nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
        if nw != fw or nh != fh:
            frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return ImageTk.PhotoImage(Image.fromarray(rgb))

    def _put_frame(self, tk_img):
        try:
            self._tk_img = tk_img
            self.canvas.delete("video_frame")
            tw = tk_img.width(); th = tk_img.height()
            self.canvas.create_image((self.w-tw)//2, (self.h-th)//2,
                                      anchor="nw", image=tk_img, tags="video_frame")
        except Exception:
            pass  # canvas destroyed: the window closed during playback

    # Audio extraction also uses a layered fallback strategy: MoviePy first, FFmpeg pipe second.
    def _load_audio(self, path):
        try:
            import numpy as np
            try:
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(path)
                if clip.audio is None: clip.close(); return
                sr = 44100
                arr = clip.audio.to_soundarray(fps=sr, nbytes=2); clip.close()
                if arr.ndim == 1: arr = np.column_stack([arr, arr])
                arr = np.clip(arr, -1.0, 1.0)
                self._audio_frames = (arr * 32767).astype(np.int16)
                self._audio_sr = sr; self._has_audio = True; return
            except ImportError: pass
            except Exception: pass
            cmd = ["ffmpeg","-i",path,"-vn","-acodec","pcm_s16le",
                   "-ar","44100","-ac","2","-f","s16le","pipe:1","-loglevel","quiet"]
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            if r.returncode == 0 and r.stdout:
                data = np.frombuffer(r.stdout, dtype=np.int16)
                if data.size % 2: data = data[:-1]
                self._audio_frames = data.reshape(-1, 2)
                self._audio_sr = 44100; self._has_audio = True
        except Exception: pass

    # Audio playback is optional and should fail silently when dependencies are missing.
    def _start_audio(self):
        if not self._has_audio or self._muted or self._audio_frames is None: return
        self._stop_audio()
        try:
            import numpy as np
            import sounddevice as sd
            frames = self._audio_frames; sr = self._audio_sr; player = self
            def callback(outdata, frame_count, time_info, status):
                pos = player._audio_pos; end = pos + frame_count
                chunk = frames[pos:end]
                if len(chunk) < frame_count:
                    pad = np.zeros((frame_count - len(chunk), 2), dtype=np.int16)
                    chunk = np.vstack([chunk, pad]) if len(chunk) else pad
                player._audio_pos = end
                vol = player._volume
                out = (chunk.astype(np.float32) * vol).astype(np.int16)
                outdata[:] = out.reshape(outdata.shape)
            self._audio_stream = sd.RawOutputStream(
                samplerate=sr, channels=2, dtype="int16",
                blocksize=2048, callback=callback)
            self._audio_stream.start()
        except ImportError: pass
        except Exception: pass

    def _stop_audio(self):
        try:
            if self._audio_stream:
                self._audio_stream.stop(); self._audio_stream.close()
                self._audio_stream = None
        except Exception: pass

    def _show_no_cv2(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0,0,self.w,self.h, fill="#1a0a0c", outline="")
        self.canvas.create_text(self.w//2, self.h//2-20, text="🎬", fill=DANGER, font=("Segoe UI",36))
        self.canvas.create_text(self.w//2, self.h//2+20,
            text=t("opencv_required"), fill=MUTED, font=("Segoe UI",8), justify="center")

    def _show_error(self, msg):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0,0,self.w,self.h, fill="#1a0a0c", outline="")
        self.canvas.create_text(self.w//2, self.h//2, text=t("video_error", msg=msg),
            fill="#dd6974", font=("Segoe UI",8), justify="center", width=self.w-20)
