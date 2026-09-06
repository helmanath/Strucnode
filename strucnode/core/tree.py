"""Turning a chain of nodes into a folder tree, then into copy/move operations.

Folder names come from EXIF values, file names and free text typed into a
connector node, so every component goes through :func:`sanitize_component`
before it reaches the filesystem. Without it a camera model containing ``/``
silently creates an extra level, a Windows-reserved character makes the whole
operation fail, and a connector containing ``..`` escapes the destination
folder entirely.
"""

from __future__ import annotations

import os
import re
from pathlib import PurePath

from .fields import UNRESOLVED, resolve

# Tokens exchanged between the node editor and the tree builder.
FOLDER_PREFIX = "__folder__"
DYN_FOLDER_PREFIX = "__folder_dyn__||"
ARG_PREFIX = "arg::"
LIT_PREFIX = "lit::"

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}
FALLBACK_NAME = "_"


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def arg_token(resolver: str, separator: str = "") -> str:
    """Token for an argument node used as a tree level."""
    return f"{resolver}::{separator}"


def folder_token(name: str) -> str:
    """Token for a folder node with a fixed name."""
    return f"{FOLDER_PREFIX}{name}"


def dyn_folder_token(parts: list[str]) -> str:
    """Token for a folder node whose name is built from a chain of parts."""
    return DYN_FOLDER_PREFIX + "|".join(parts)


def dyn_arg_part(resolver: str, separator: str = "") -> str:
    """One dynamic part of a folder name, taken from a metadata field."""
    return f"{ARG_PREFIX}{resolver}::{separator}"


def dyn_literal_part(text: str) -> str:
    """One dynamic part of a folder name, taken from a connector node."""
    return f"{LIT_PREFIX}{text}"


def decode_field_token(token: str) -> tuple[str, str]:
    """Split ``"resolver::separator"`` into its two halves."""
    if "::" in token and not token.startswith("__"):
        resolver, separator = token.split("::", 1)
        return resolver, separator
    return token, ""


# --------------------------------------------------------------------------- #
# Name safety
# --------------------------------------------------------------------------- #
def sanitize_component(name: str, fallback: str = FALLBACK_NAME) -> str:
    """Make *name* usable as a single path component on every platform.

    Replaces the characters Windows forbids, drops the trailing dots and spaces
    it silently strips, neutralizes ``.``/``..`` and the reserved device names,
    and caps the length so long EXIF values cannot blow past ``NAME_MAX``.
    """
    cleaned = _INVALID.sub("_", str(name)).strip().rstrip(". ")
    if not cleaned or cleaned in (".", ".."):
        return fallback
    if cleaned.upper().split(".")[0] in _RESERVED:
        cleaned = "_" + cleaned
    return cleaned[:120]


def is_within(base: str, path: str) -> bool:
    """Return True when *path* stays inside *base* once both are resolved."""
    try:
        base_r = os.path.realpath(base)
        path_r = os.path.realpath(path)
        return os.path.commonpath([base_r, path_r]) == base_r
    except (ValueError, OSError):
        return False


# --------------------------------------------------------------------------- #
# Tree building
# --------------------------------------------------------------------------- #
def resolve_folder_name(info: dict, parts: list[str]) -> str | None:
    """Build one folder name for *info* from a chain of dynamic parts.

    Returns ``None`` when any metadata part is unresolved: half a folder name
    is worse than none, and the caller turns it into an unmatched entry the
    user can review instead of a folder called ``2024-`` or ``_``.
    """
    out = []
    for part in parts:
        if part.startswith(ARG_PREFIX):
            resolver, separator = decode_field_token(part[len(ARG_PREFIX):])
            value = resolve(info, resolver)
            if value == UNRESOLVED:
                return None
            out.append(value + separator)
        elif part.startswith(LIT_PREFIX):
            out.append(part[len(LIT_PREFIX):])
    return "".join(out).strip()


def build_tree(files: list[dict], tokens: list[str], progress=None, _level: int = 0):
    """Group *files* into a nested dict following *tokens*.

    Leaves are lists of file dicts. *progress* is called as ``(done, total)``
    while the first level is grouped, which is the only one that walks the whole
    list at once.
    """
    if not tokens:
        return {"(racine)": files}

    token, rest = tokens[0], tokens[1:]

    if token.startswith(FOLDER_PREFIX) and not token.startswith(DYN_FOLDER_PREFIX):
        name = sanitize_component(token[len(FOLDER_PREFIX):])
        return {name: build_tree(files, rest, _level=_level + 1)}

    tree: dict[str, list] = {}
    total = len(files)
    if token.startswith(DYN_FOLDER_PREFIX):
        spec = token[len(DYN_FOLDER_PREFIX):]
        parts = spec.split("|") if spec else []
        for i, info in enumerate(files):
            name = resolve_folder_name(info, parts)
            key = (UNRESOLVED if name is None
                   else sanitize_component(name, fallback="Dossier"))
            tree.setdefault(key, []).append(info)
            if _level == 0 and progress and (i % 50 == 0 or i == total - 1):
                progress(i + 1, total)
    else:
        resolver, separator = decode_field_token(token)
        for i, info in enumerate(files):
            raw = resolve(info, resolver)
            key = raw if raw == UNRESOLVED else sanitize_component(raw + separator)
            tree.setdefault(key, []).append(info)
            if _level == 0 and progress and (i % 50 == 0 or i == total - 1):
                progress(i + 1, total)

    if not rest:
        return tree
    return {k: build_tree(v, rest, _level=_level + 1) for k, v in tree.items()}


def count_files(tree) -> int:
    """Total number of files under *tree*."""
    if isinstance(tree, list):
        return len(tree)
    return sum(count_files(v) for v in tree.values())


def flatten_to_operations(tree, base_path: str, current: str = "") -> list[tuple[str, str]]:
    """Walk *tree* and return the ``(source, destination)`` pairs it implies."""
    ops: list[tuple[str, str]] = []
    if isinstance(tree, list):
        dest_dir = os.path.join(base_path, current) if current else base_path
        for info in tree:
            ops.append((info["path"],
                        os.path.join(dest_dir, sanitize_component(info["name"]))))
    else:
        for key, sub in tree.items():
            child = os.path.join(current, key) if current else key
            ops.extend(flatten_to_operations(sub, base_path, child))
    return ops


def is_unresolved(destination: str) -> bool:
    """Return True when *destination* contains an unresolved field placeholder."""
    return UNRESOLVED in PurePath(destination).parts
