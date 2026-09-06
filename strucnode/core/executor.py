"""Executing a plan: copying or moving files, with a journal and cancellation."""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import threading
from dataclasses import dataclass, field

from . import dedupe
from .. import config

log = logging.getLogger(__name__)

COPY = "copy"
MOVE = "move"

# Duplicate strategies.
SKIP = "skip"
REPLACE = "replace"
RENAME = "rename"
COMPARE_META = "compare_meta"
COMPARE_FULL = "compare_full"
ASK = "ask"


@dataclass
class Result:
    """Outcome of a run."""

    done: int = 0
    skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)
    cancelled: bool = False
    journal_path: str | None = None


def _unique_destination(dst: str, suffix: str) -> str:
    """Return a free path next to *dst* by appending *suffix* (then a counter)."""
    base, ext = os.path.splitext(dst)
    candidate = f"{base}{suffix}{ext}"
    counter = 1
    while os.path.exists(candidate):
        candidate = f"{base}{suffix}{counter}{ext}"
        counter += 1
    return candidate


def _resolve_collision(src: str, dst: str, strategy: str, suffix: str) -> str | None:
    """Return the path to write to, or None when the file should be skipped.

    The comparison strategies keep both files when they differ. The previous
    version fell through to an unconditional overwrite, which silently
    destroyed the destination whenever two different photos shared a name --
    the common case once a camera counter wraps around.
    """
    if strategy == SKIP:
        return None
    if strategy == COMPARE_META:
        return None if dedupe.equal_meta(src, dst) else _unique_destination(dst, suffix)
    if strategy == COMPARE_FULL:
        return None if dedupe.equal_full(src, dst) else _unique_destination(dst, suffix)
    if strategy == RENAME:
        return _unique_destination(dst, suffix)
    return dst  # REPLACE


def _copy_atomic(src: str, dst: str) -> None:
    """Copy *src* to *dst* through a temporary file, then rename it into place.

    Closing the application mid-copy then leaves the previous file intact
    instead of a truncated one bearing the final name.
    """
    tmp = f"{dst}.strucnode-part"
    try:
        shutil.copyfile(src, tmp)
        shutil.copystat(src, tmp, follow_symlinks=True)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def run(operations, mode: str, strategy: str = REPLACE, *,
        cancel: threading.Event | None = None,
        progress=None, suffix: str = "-copy", journal: bool = True) -> Result:
    """Execute *operations*, reporting through *progress* as ``(done, total)``.

    Every successful operation is appended to a JSON journal under
    ``~/.strucnode/journal`` so a move can be traced back and undone.
    """
    result = Result()
    total = len(operations)
    entries: list[dict] = []

    for src, dst in operations:
        if cancel is not None and cancel.is_set():
            result.cancelled = True
            break
        try:
            target: str | None = dst
            if os.path.exists(dst):
                target = _resolve_collision(src, dst, strategy, suffix)
            if target is None:
                result.skipped += 1
                result.done += 1
            else:
                os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
                if mode == COPY:
                    _copy_atomic(src, target)
                else:
                    shutil.move(src, target)
                result.done += 1
                entries.append({"src": src, "dst": target, "mode": mode})
        except Exception as exc:
            result.errors += 1
            result.error_messages.append(f"{os.path.basename(src)}: {exc}")
            log.warning("operation failed: %s -> %s", src, dst, exc_info=True)
        if progress is not None:
            progress(result.done, total)

    if journal and entries:
        result.journal_path = _write_journal(entries, mode, result)
    return result


def _write_journal(entries: list[dict], mode: str, result: Result) -> str | None:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = config.journal_dir() / f"{stamp}-{mode}.json"
    payload = {
        "timestamp": stamp,
        "mode": mode,
        "done": result.done,
        "errors": result.errors,
        "cancelled": result.cancelled,
        "operations": entries,
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        return str(path)
    except OSError:
        log.warning("cannot write journal %s", path, exc_info=True)
        return None
