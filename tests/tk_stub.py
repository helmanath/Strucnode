"""A Tkinter stand-in so the UI modules can be imported without a display.

It is deliberately dumb: it only needs to make ``import tkinter`` succeed and
provide subclassable widget classes, which is enough to catch missing imports,
typos and undefined names at module import time.
"""

from __future__ import annotations

import sys
import types


class _Widget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Widget()

    def __call__(self, *args, **kwargs):
        return _Widget()

    def __setitem__(self, key, value):
        pass

    def __getitem__(self, key):
        return _Widget()


class _Variable(_Widget):
    def get(self):
        return ""

    def set(self, value):
        pass


def install() -> None:
    """Register the stub under ``tkinter`` if the real one is unavailable."""
    try:
        import tkinter  # noqa: F401
        return
    except ImportError:
        pass

    tkinter = types.ModuleType("tkinter")
    for name in ("Tk", "Toplevel", "Frame", "Label", "Button", "Entry", "Canvas",
                 "Checkbutton", "Radiobutton", "Listbox", "PanedWindow",
                 "LabelFrame", "Menubutton", "Scale", "Text", "Widget", "Misc"):
        setattr(tkinter, name, type(name, (_Widget,), {}))
    for name in ("StringVar", "IntVar", "DoubleVar", "BooleanVar", "Variable"):
        setattr(tkinter, name, type(name, (_Variable,), {}))
    tkinter.TclError = type("TclError", (Exception,), {})

    ttk = types.ModuleType("tkinter.ttk")
    for name in ("Treeview", "Scrollbar", "Combobox", "Progressbar", "Notebook",
                 "Style", "Frame", "Label", "Button", "Scale"):
        setattr(ttk, name, type(name, (_Widget,), {}))

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
