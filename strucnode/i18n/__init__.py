"""Localization layer.

Translations live in ``locales/<lang>.json`` next to this module, not in the
Python sources.

The important part is :func:`tr`: instead of injecting a translated string into
a widget at construction time and hoping something re-applies it later, a widget
is *bound* to its translation key once and for all::

    self._title = tr(tk.Label(parent, bg=BG, fg=TEXT), "explorer.summary")

:func:`set_locale` then walks the registry and refreshes every bound widget, so
a widget can never be forgotten when the language changes. Widgets that are not
a simple ``text=`` (tree headings, notebook tabs, window titles) register a
callback with :func:`on_change` instead.

Two rules keep this honest, and both are enforced by ``tests/test_i18n.py``:

* a translated string is never used as data or as an identifier -- comparing a
  widget's current text against an expected translation is what made the
  previous implementation fail as soon as the locale changed;
* dynamic text is stored as ``(key, params)`` and re-rendered, never as an
  already-formatted string.
"""

from __future__ import annotations

import json
import logging
import weakref
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_LOCALE = "en"
LOCALES_DIR = Path(__file__).parent / "locales"

_catalogs: dict[str, dict[str, str]] = {}
_locale = DEFAULT_LOCALE
_missing: set[str] = set()

# Bound widgets and variables, held weakly so destroying a tab does not leak
# them. Keyed by id() rather than by the object: tkinter.Variable defines
# __eq__ without __hash__, which makes it unhashable and rules out a
# WeakKeyDictionary. The weakref callback drops the entry when the object dies,
# so an id can never be reused while its entry is still live.
_bindings: dict[int, tuple] = {}
_callbacks: list = []


# --------------------------------------------------------------------------- #
# Catalogs
# --------------------------------------------------------------------------- #
def available_locales() -> tuple[str, ...]:
    """Return the language codes shipped in ``locales/``, sorted."""
    return tuple(sorted(p.stem for p in LOCALES_DIR.glob("*.json")))


def catalog(lang: str) -> dict[str, str]:
    """Return the catalog for *lang*, loading it from disk on first use."""
    if lang not in _catalogs:
        path = LOCALES_DIR / f"{lang}.json"
        try:
            _catalogs[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.exception("cannot load locale %r from %s", lang, path)
            _catalogs[lang] = {}
    return _catalogs[lang]


def get_locale() -> str:
    """Return the active language code."""
    return _locale


# --------------------------------------------------------------------------- #
# Translation
# --------------------------------------------------------------------------- #
def t(key: str, **params) -> str:
    """Translate *key* in the active locale and format it with *params*.

    Falls back to the default locale, then to the key itself. A key missing
    from every catalog is logged once so it shows up during development instead
    of failing silently.
    """
    text = catalog(_locale).get(key)
    if text is None:
        text = catalog(DEFAULT_LOCALE).get(key)
    if text is None:
        if key not in _missing:
            _missing.add(key)
            log.warning("missing translation key: %r", key)
        return key
    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        log.warning("cannot format %r with %r", key, params)
        return text


def binding_count() -> int:
    """Number of live bindings (used by tests)."""
    return sum(1 for ref, _, _ in _bindings.values() if ref() is not None)


def missing_keys() -> set[str]:
    """Keys requested at runtime that no catalog defines (development aid)."""
    return set(_missing)


# --------------------------------------------------------------------------- #
# Binding
# --------------------------------------------------------------------------- #
def _register(obj, key: str, params: dict) -> None:
    ident = id(obj)

    def _drop(_ref, ident=ident):
        _bindings.pop(ident, None)

    try:
        ref = weakref.ref(obj, _drop)
    except TypeError:                    # object does not support weak refs
        return
    _bindings[ident] = (ref, key, params)


def tr(widget, key: str, **params):
    """Bind *widget*'s text to *key*, apply it now, and return *widget*.

    Calling it again on the same widget replaces the binding, which is how a
    label whose content depends on data is updated::

        tr(self._status, "organize.progress", done=done, total=total)
    """
    _register(widget, key, params)
    _apply(widget, key, params)
    return widget


def tr_var(var, key: str, **params):
    """Bind a Tk variable to *key*, apply it now, and return *var*."""
    _register(var, key, params)
    _apply(var, key, params)
    return var


def is_bound(obj) -> bool:
    """True while *obj* still shows a translation rather than real data."""
    entry = _bindings.get(id(obj))
    return entry is not None and entry[0]() is obj


def set_raw(var, value: str) -> None:
    """Put a non-translatable value into *var*, dropping any binding it had.

    Use this whenever a bound variable receives real data (a preset name, a
    path): without it the next locale change would overwrite that data with the
    translation the variable was last bound to.
    """
    untr(var)
    var.set(value)


def untr(obj) -> None:
    """Drop *obj*'s binding so it keeps whatever text it currently holds."""
    _bindings.pop(id(obj), None)


def on_change(callback):
    """Register *callback*, called after every locale change. Returns it."""
    _callbacks.append(callback)
    return callback


def _apply(obj, key: str, params: dict) -> None:
    text = t(key, **params)
    try:
        if hasattr(obj, "set"):          # Tk variable
            obj.set(text)
        else:                            # Tk widget
            obj.configure(text=text)
    except Exception:                    # destroyed widget, or no text option
        log.debug("cannot apply %r to %r", key, obj, exc_info=True)


def set_locale(lang: str) -> None:
    """Switch the active language and refresh everything bound to it."""
    global _locale
    if lang not in available_locales():
        lang = DEFAULT_LOCALE
    if lang == _locale:
        return
    _locale = lang
    retranslate()


def retranslate() -> None:
    """Re-apply the active locale to every bound object and callback."""
    for ref, key, params in list(_bindings.values()):
        obj = ref()
        if obj is not None:
            _apply(obj, key, params)
    for callback in list(_callbacks):
        try:
            callback()
        except Exception:
            log.exception("locale change callback failed: %r", callback)
