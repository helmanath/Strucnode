"""Walking a folder tree and indexing what is inside it."""

from __future__ import annotations

import datetime
import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import t
from .categories import get_category

log = logging.getLogger(__name__)

PROGRESS_EVERY = 200


@dataclass
class ScanResult:
    """What one folder analysis produced."""

    files: list[dict] = field(default_factory=list)
    by_category: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))
    ext_count: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    ext_size: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_files: int = 0
    total_dirs: int = 0
    total_size: int = 0
    errors: int = 0
    cancelled: bool = False


def format_mtime(timestamp: float) -> str:
    """Render a modification timestamp using the active locale's format."""
    if not timestamp:
        return ""
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime(t("datetime_format"))
    except (OSError, OverflowError, ValueError):
        return ""


def scan(folder: str, *, progress=None, cancel: threading.Event | None = None) -> ScanResult:
    """Index every file under *folder*.

    Entries hold raw values only (``size_bytes``, ``mtime_ts``); formatting
    happens at render time so sizes and dates follow the language the user is
    currently looking at.

    *progress* is called as ``(files_seen, bytes_seen)`` every
    :data:`PROGRESS_EVERY` files. *cancel* stops the walk at the next file.
    """
    result = ScanResult()
    last_reported = 0
    no_ext = t("no_extension")

    for root, dirs, names in os.walk(folder):
        if cancel is not None and cancel.is_set():
            result.cancelled = True
            return result
        result.total_dirs += len(dirs)
        for name in names:
            path = os.path.join(root, name)
            ext = Path(name).suffix.lower() or no_ext
            try:
                st = os.stat(path)
                size, mtime = st.st_size, st.st_mtime
            except OSError as exc:
                result.errors += 1
                size, mtime = 0, 0.0
                log.debug("cannot stat %r: %s", path, exc)

            result.ext_count[ext] += 1
            result.ext_size[ext] += size
            result.total_files += 1
            result.total_size += size

            info = {"path": path, "name": name, "ext": ext,
                    "size_bytes": size, "mtime_ts": mtime, "meta": {}}
            result.files.append(info)
            result.by_category[get_category(ext)].append(info)

            if progress and result.total_files - last_reported >= PROGRESS_EVERY:
                last_reported = result.total_files
                progress(result.total_files, result.total_size)

    if progress:
        progress(result.total_files, result.total_size)
    return result
