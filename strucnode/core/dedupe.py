"""Comparing a source file with an existing destination file."""

from __future__ import annotations

import os

_BUFFER = 1 << 18  # 256 KB


def equal_meta(src: str, dst: str) -> bool:
    """Same size and same mtime (within 2 s). Fast: never reads the contents."""
    try:
        ss, ds = os.stat(src), os.stat(dst)
    except OSError:
        return False
    return ss.st_size == ds.st_size and abs(ss.st_mtime - ds.st_mtime) <= 2.0


def equal_full(src: str, dst: str) -> bool:
    """Byte-for-byte comparison, read in 256 KB blocks."""
    try:
        if os.stat(src).st_size != os.stat(dst).st_size:
            return False
        with open(src, "rb") as fs, open(dst, "rb") as fd:
            while True:
                bs, bd = fs.read(_BUFFER), fd.read(_BUFFER)
                if bs != bd:
                    return False
                if not bs:
                    return True
    except OSError:
        return False
