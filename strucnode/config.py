"""Where Strucnode keeps its user data, and the persisted preferences."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

APP_DIR_NAME = ".strucnode"
LEGACY_PRESETS_DIR = Path.home() / ".file_explorer_presets"


def app_dir() -> Path:
    """Return (and create) the per-user data directory."""
    root = os.environ.get("STRUCNODE_HOME")
    path = Path(root) if root else Path.home() / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def presets_dir() -> Path:
    """Return (and create) the presets directory, migrating the legacy one once."""
    path = app_dir() / "presets"
    path.mkdir(parents=True, exist_ok=True)
    if LEGACY_PRESETS_DIR.is_dir() and not any(path.iterdir()):
        for item in LEGACY_PRESETS_DIR.glob("*"):
            try:
                item.replace(path / item.name)
            except OSError:
                log.warning("cannot migrate preset %s", item, exc_info=True)
    return path


def journal_dir() -> Path:
    """Return (and create) the directory holding operation journals."""
    path = app_dir() / "journal"
    path.mkdir(parents=True, exist_ok=True)
    return path


_SETTINGS_FILE = "settings.json"
_DEFAULTS: dict = {
    "locale": None,          # None -> detect from the system on first run
    "last_folder": "",
    "last_destination": "",
    "operation_mode": "copy",
    "duplicate_mode": "ask",
}


def load_settings() -> dict:
    """Return the persisted preferences merged over the defaults."""
    settings = dict(_DEFAULTS)
    path = app_dir() / _SETTINGS_FILE
    try:
        if path.is_file():
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                settings.update({k: v for k, v in stored.items() if k in _DEFAULTS})
    except (OSError, ValueError):
        log.warning("cannot read %s, using defaults", path, exc_info=True)
    return settings


def save_settings(settings: dict) -> None:
    """Persist the preferences, ignoring the keys we do not know about."""
    path = app_dir() / _SETTINGS_FILE
    payload = {k: v for k, v in settings.items() if k in _DEFAULTS}
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except OSError:
        log.warning("cannot write %s", path, exc_info=True)


def detect_locale(available: tuple[str, ...], default: str = "en") -> str:
    """Guess the UI language from the environment, falling back to *default*.

    ``locale.getdefaultlocale`` is deprecated, so this reads the POSIX
    environment first and only then asks the ``locale`` module, which on
    Windows answers with names such as ``French_France``.
    """
    import locale as _locale

    tag = ""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        if os.environ.get(var):
            tag = os.environ[var]
            break
    if not tag:
        try:
            tag = _locale.getlocale()[0] or ""
        except (ValueError, TypeError):
            tag = ""

    tag = tag.replace("-", "_").split(".")[0].split(":")[0]
    code = tag.split("_")[0].lower()
    if code in available:
        return code
    windows_names = {"french": "fr", "english": "en"}
    return windows_names.get(code, default) if windows_names.get(code) in available else default
