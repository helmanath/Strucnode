"""File extension categories and human-readable sizes."""

from __future__ import annotations

from pathlib import Path

from ..i18n import t

EXT_CATEGORIES: dict[str, set[str]] = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico",
               ".tiff", ".heic", ".raw", ".cr2", ".nef", ".arw", ".dng", ".orf",
               ".rw2", ".pef", ".srw", ".x3f"},
    "videos": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h",
             ".go", ".rs", ".php", ".rb", ".sh", ".json", ".xml", ".yaml",
             ".yml", ".toml"},
    "docs": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
             ".md", ".odt", ".rtf"},
    "data": {".csv", ".sql", ".db", ".sqlite", ".parquet", ".feather"},
    "archives": {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz"},
}

#: Categories in the order they are offered to the user.
CATEGORIES = tuple(EXT_CATEGORIES) + ("other",)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic"}
RAW_EXTS = {".arw", ".raw", ".cr2", ".nef", ".dng", ".orf", ".rw2", ".pef",
            ".srw", ".x3f"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"}

_EXT_TO_CATEGORY = {ext: cat for cat, exts in EXT_CATEGORIES.items() for ext in exts}


def get_category(ext: str) -> str:
    """Map a file extension to its coarse category, ``"other"`` if unknown."""
    return _EXT_TO_CATEGORY.get(ext.lower(), "other")


def category_label(cat: str) -> str:
    """Return the translated display name of a category."""
    return t(f"cat_{cat}")


def suffix_of(name: str) -> str:
    """Return the lowercase extension of *name*, or the ``no_extension`` label."""
    return Path(name).suffix.lower() or t("no_extension")


def fmt_size(n: float) -> str:
    """Format a byte count using the units of the active locale."""
    units = t("size_units").split(",")
    for unit in units[:-1]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} {units[-1]}"
