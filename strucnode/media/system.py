"""Handing a file over to the operating system."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def open_file(path: str) -> str | None:
    """Open *path* with the default application.

    Returns ``None`` on success, or the error message so the caller can decide
    how to surface it.
    """
    try:
        if sys.platform == "win32":
            os.startfile(str(Path(path)))  # noqa: S606 - documented Windows API
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("cannot open %r", path, exc_info=True)
        return str(exc)
    return None
