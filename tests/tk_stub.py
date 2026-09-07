"""A strict Tkinter stand-in so the UI can be built without a display.

Strict is the point. An earlier, permissive stub answered *any* attribute with
a dummy object, which hid a real crash: ``ExplorerTab._build_ui`` read
``self._video_player`` before ``__init__`` had assigned it, and only a run on a
real machine surfaced it.

So the rule here mirrors how the code is written: names starting with ``_`` are
the application's own state and must have been assigned, otherwise the lookup
raises ``AttributeError`` exactly as real Tk would. Public names are treated as
Tk API and answered with a no-op, since the widget toolkit itself is not what
these tests are checking.
"""

from __future__ import annotations

import sys
import types


class _Noop:
    """Callable, subscriptable, iterable stand-in for a Tk return value."""

    def __call__(self, *args, **kwargs):
        return _Noop()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Noop()

    def __getitem__(self, key):
        return _Noop()

    def __setitem__(self, key, value):
        pass

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __str__(self):
        return ""

    def __format__(self, spec):
        return format(0, spec) if spec else ""

    def __sub__(self, other):
        return 0

    def __rsub__(self, other):
        return 0

    def __lt__(self, other):
        return False

    def __gt__(self, other):
        return False


class _Widget:
    """Base for every stubbed widget.

    Missing ``_private`` attributes raise, missing public ones are Tk API.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}")
        return _Noop()

    def __setitem__(self, key, value):
        pass

    def __getitem__(self, key):
        return _Noop()

    # Geometry and configuration return None in Tk; keep that shape.
    def pack(self, *a, **k): pass
    def pack_forget(self, *a, **k): pass
    def grid(self, *a, **k): pass
    def place(self, *a, **k): pass
    def place_forget(self, *a, **k): pass
    def config(self, *a, **k): pass
    def configure(self, *a, **k): pass
    def bind(self, *a, **k): pass
    def bind_all(self, *a, **k): pass
    def destroy(self, *a, **k): pass
    def update_idletasks(self, *a, **k): pass
    def pack_propagate(self, *a, **k): pass
    def winfo_children(self): return []
    def winfo_width(self): return 800
    def winfo_height(self): return 600
    def winfo_reqheight(self): return 100
    def winfo_rootx(self): return 0
    def winfo_rooty(self): return 0
    def winfo_exists(self): return True
    def winfo_ismapped(self): return True
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def cget(self, key): return ""
    def after(self, delay, func=None, *args):
        return "after#0"
    def after_cancel(self, ident): pass


class _Variable:
    def __init__(self, master=None, value=None, name=None):
        self._value = value if value is not None else ""

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, mode, callback):
        return "trace#0"

    def trace_remove(self, mode, ident):
        pass


class _BooleanVar(_Variable):
    def __init__(self, master=None, value=False, name=None):
        super().__init__(value=bool(value))


class _NumberVar(_Variable):
    def __init__(self, master=None, value=0, name=None):
        super().__init__(value=value or 0)


class _Canvas(_Widget):
    def create_rectangle(self, *a, **k): return 1
    def create_oval(self, *a, **k): return 1
    def create_polygon(self, *a, **k): return 1
    def create_line(self, *a, **k): return 1
    def create_text(self, *a, **k): return 1
    def create_window(self, *a, **k): return 1
    def create_image(self, *a, **k): return 1
    def delete(self, *a, **k): pass
    def coords(self, *a, **k): return [0, 0, 0, 0]
    def itemconfig(self, *a, **k): pass
    def bbox(self, *a, **k): return (0, 0, 100, 100)
    def find_withtag(self, *a, **k): return ()
    def tag_raise(self, *a, **k): pass
    def yview(self, *a, **k): pass
    def yview_moveto(self, *a, **k): pass
    def yview_scroll(self, *a, **k): pass
    def xview_moveto(self, *a, **k): pass


class _Treeview(_Widget):
    def heading(self, *a, **k): pass
    def column(self, *a, **k): pass
    def insert(self, *a, **k): return "I001"
    def delete(self, *a, **k): pass
    def get_children(self, *a, **k): return ()
    def selection(self): return ()
    def tag_configure(self, *a, **k): pass
    def item(self, *a, **k): return {}


class _Notebook(_Widget):
    def add(self, *a, **k): pass
    def tab(self, *a, **k): pass


class _PanedWindow(_Widget):
    def add(self, *a, **k): pass


class _Combobox(_Widget):
    def __init__(self, *a, **k):
        self._index = 0

    def current(self, index=None):
        if index is None:
            return self._index
        self._index = index

    def set(self, value): pass


def install() -> None:
    """Register the stub under ``tkinter`` when the real one is unavailable."""
    try:
        import tkinter  # noqa: F401
        return
    except ImportError:
        pass

    tkinter = types.ModuleType("tkinter")
    for name in ("Tk", "Toplevel", "Frame", "Label", "Button", "Entry",
                 "Checkbutton", "Radiobutton", "Listbox", "LabelFrame",
                 "Menubutton", "Scale", "Text", "Widget", "Misc"):
        setattr(tkinter, name, type(name, (_Widget,), {}))
    tkinter.Canvas = type("Canvas", (_Canvas,), {})
    tkinter.PanedWindow = type("PanedWindow", (_PanedWindow,), {})
    tkinter.StringVar = type("StringVar", (_Variable,), {})
    tkinter.BooleanVar = type("BooleanVar", (_BooleanVar,), {})
    tkinter.IntVar = type("IntVar", (_NumberVar,), {})
    tkinter.DoubleVar = type("DoubleVar", (_NumberVar,), {})
    tkinter.Variable = _Variable
    tkinter.TclError = type("TclError", (Exception,), {})

    ttk = types.ModuleType("tkinter.ttk")
    for name in ("Scrollbar", "Progressbar", "Style", "Frame", "Label",
                 "Button", "Scale", "Separator"):
        setattr(ttk, name, type(name, (_Widget,), {}))
    ttk.Treeview = type("Treeview", (_Treeview,), {})
    ttk.Notebook = type("Notebook", (_Notebook,), {})
    ttk.Combobox = type("Combobox", (_Combobox,), {})

    for name in ("messagebox", "filedialog"):
        module = types.ModuleType(f"tkinter.{name}")
        for func in ("showinfo", "showerror", "showwarning", "askyesno",
                     "askyesnocancel", "askdirectory", "askopenfilename"):
            setattr(module, func, lambda *a, **k: None)
        setattr(tkinter, name, module)
        sys.modules[f"tkinter.{name}"] = module

    tkinter.ttk = ttk
    sys.modules["tkinter"] = tkinter
    sys.modules["tkinter.ttk"] = ttk
