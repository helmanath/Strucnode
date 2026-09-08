"""Reading and writing node editor presets.

Storage lives under ``~/.strucnode/presets`` (the legacy
``~/.file_explorer_presets`` folder is migrated on first use). Preset names come
from a text field, so they are sanitized before touching the filesystem -- the
previous version joined the raw name onto the presets directory, which let a
name containing ``..`` write anywhere.
"""

from __future__ import annotations

import json
import logging
import unicodedata

from ... import config
from ...core.tree import sanitize_component

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
LAST_PRESET_FILE = "_last.txt"


class PresetStore:
    """File-backed collection of node editor presets."""

    def directory(self):
        """Return the directory holding the presets."""
        return config.presets_dir()

    def path_for(self, name: str):
        """Return the JSON path for the preset *name*."""
        return self.directory() / (sanitize_component(name) + ".json")

    def names(self) -> list[str]:
        """Return the available preset names, NFC-normalized and sorted."""
        try:
            return sorted(unicodedata.normalize("NFC", p.stem)
                          for p in self.directory().glob("*.json")
                          if not p.name.startswith("_"))
        except OSError:
            log.warning("cannot list presets", exc_info=True)
            return []

    def exists(self, name: str) -> bool:
        return self.path_for(name).is_file()

    def save(self, name: str, data: dict) -> None:
        """Write *data* under *name*, stamping the schema version."""
        payload = dict(data, version=SCHEMA_VERSION)
        self.path_for(name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, name: str) -> dict | None:
        """Return the preset *name*, or None when it is missing or invalid."""
        try:
            data = json.loads(self.path_for(name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("cannot read preset %r", name, exc_info=True)
            return None
        return data if isinstance(data, dict) else None

    def delete(self, name: str) -> bool:
        """Remove the preset *name*. Returns True when a file was removed."""
        try:
            self.path_for(name).unlink()
            return True
        except OSError:
            log.warning("cannot delete preset %r", name, exc_info=True)
            return False

    # -- last opened preset ------------------------------------------------- #
    def last_name(self) -> str | None:
        path = self.directory() / LAST_PRESET_FILE
        try:
            return path.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def set_last_name(self, name: str) -> None:
        path = self.directory() / LAST_PRESET_FILE
        try:
            path.write_text(name, encoding="utf-8")
        except OSError:
            log.warning("cannot record last preset", exc_info=True)
