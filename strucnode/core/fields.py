"""The metadata fields a node can expose, and how to resolve them for a file.

``FIELDS`` replaces the old ``NODE_TYPES`` global, which stored *translated*
labels and had to be rebuilt on every language change. Here a field stores its
i18n *key*; the label is resolved at draw time, so a node placed in French and
a preset saved in French both display correctly in English.

The ``key`` of each field is persisted in presets and must stay stable.
"""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .categories import IMAGE_EXTS, RAW_EXTS, get_category
from .metadata import exif_datetime

log = logging.getLogger(__name__)

UNRESOLVED = "?"
"""Value returned when a field cannot be resolved for a file."""


@dataclass(frozen=True)
class Field:
    """One draggable metadata field in the node palette."""

    key: str          # stable id, persisted in presets
    label_key: str    # i18n key for the display name
    color: str
    resolver: str     # id understood by resolve()


_ARG = "#4f98a3"
_MOD = "#fdab43"
_MISC = "#a86fdf"
_SIZE = "#6daa45"
_NAME = "#dd6974"
_EXIF = "#5591c7"

FIELDS: dict[str, Field] = {f.key: f for f in (
    Field("annee_creation", "nt_annee_creation", _ARG, "year_ctime"),
    Field("mois_creation", "nt_mois_creation", _ARG, "month_ctime"),
    Field("jour_creation", "nt_jour_creation", _ARG, "day_ctime"),
    Field("annee_modif", "nt_annee_modif", _MOD, "year_mtime"),
    Field("mois_modif", "nt_mois_modif", _MOD, "month_mtime"),
    Field("jour_modif", "nt_jour_modif", _MOD, "day_mtime"),
    Field("extension", "nt_extension", _MISC, "ext"),
    Field("categorie", "nt_categorie", _MISC, "category"),
    Field("taille", "nt_taille", _SIZE, "size_range"),
    Field("premiere_lettre", "nt_premiere_lettre", _NAME, "first_letter"),
    Field("exif_annee", "nt_exif_annee", _EXIF, "exif_year"),
    Field("exif_mois", "nt_exif_mois", _EXIF, "exif_month"),
    Field("exif_jour", "nt_exif_jour", _EXIF, "exif_day"),
    Field("exif_date_full", "nt_exif_date_full", _EXIF, "exif_date_full"),
    Field("nom_fichier", "nt_nom_fichier", _NAME, "filename_noext"),
)}

#: Palette layout: (section i18n key, field keys).
PALETTE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pal_sect_exif", ("exif_annee", "exif_mois", "exif_jour", "exif_date_full")),
    ("pal_sect_created", ("annee_creation", "mois_creation", "jour_creation")),
    ("pal_sect_modif", ("annee_modif", "mois_modif", "jour_modif")),
    ("pal_sect_file", ("nom_fichier", "extension", "categorie", "taille",
                       "premiere_lettre")),
)

# Windows forbids < and > in path components, so the buckets that end up as
# folder names use plain ASCII ranges instead of the old "< 100 Ko" labels.
_SIZE_BUCKETS: tuple[tuple[int, str], ...] = (
    (100 * 1024, "0-100KB"),
    (1024 * 1024, "100KB-1MB"),
    (10 * 1024 * 1024, "1MB-10MB"),
    (100 * 1024 * 1024, "10MB-100MB"),
)
_SIZE_LAST = "100MB+"


def label(key: str) -> str:
    """Return the translated display name of the field *key*."""
    from ..i18n import t
    fld = FIELDS.get(key)
    return t(fld.label_key) if fld else key


def color(key: str) -> str:
    """Return the palette color of the field *key*."""
    fld = FIELDS.get(key)
    return fld.color if fld else _ARG


def resolver_of(key: str) -> str:
    """Return the resolver id of the field *key*."""
    fld = FIELDS.get(key)
    return fld.resolver if fld else ""


def _timestamps(info: dict) -> tuple[datetime.datetime, datetime.datetime]:
    """Return (mtime, ctime) for *info*, reading and caching them on first use."""
    if "_mtime" not in info:
        now = datetime.datetime.now()
        try:
            st = os.stat(info["path"])
            for attr, stamp in (("_mtime", st.st_mtime), ("_ctime", st.st_ctime)):
                try:
                    info[attr] = datetime.datetime.fromtimestamp(stamp)
                except (OSError, OverflowError, ValueError):
                    info[attr] = now
        except OSError:
            info["_mtime"] = info["_ctime"] = now
    return info["_mtime"], info["_ctime"]


def resolve(info: dict, resolver: str) -> str:
    """Resolve one metadata field for an indexed file.

    Returns :data:`UNRESOLVED` when the field has no meaning for that file, so
    the planner can keep those operations out of the run.
    """
    mtime, ctime = _timestamps(info)

    if resolver == "year_ctime":
        return str(ctime.year)
    if resolver == "month_ctime":
        return f"{ctime.month:02d}"
    if resolver == "day_ctime":
        return f"{ctime.day:02d}"
    if resolver == "year_mtime":
        return str(mtime.year)
    if resolver == "month_mtime":
        return f"{mtime.month:02d}"
    if resolver == "day_mtime":
        return f"{mtime.day:02d}"
    if resolver == "ext":
        return info["ext"].lstrip(".").upper() or "SANS_EXT"
    if resolver == "category":
        return get_category(info["ext"]).capitalize()
    if resolver == "size_range":
        size = info["size_bytes"]
        for limit, name in _SIZE_BUCKETS:
            if size < limit:
                return name
        return _SIZE_LAST
    if resolver == "first_letter":
        name = info["name"]
        return name[0].upper() if name else "#"
    if resolver == "filename_noext":
        return Path(info["name"]).stem
    if resolver in ("exif_year", "exif_month", "exif_day", "exif_date_full"):
        if "_exif_dt" not in info:
            ext = info.get("ext", "").lower()
            info["_exif_dt"] = (exif_datetime(info["path"])
                                if ext in IMAGE_EXTS or ext in RAW_EXTS else None)
        # A missing capture date falls back to the modification time so the
        # structure stays deterministic instead of dropping the file.
        when = info["_exif_dt"] or mtime
        if resolver == "exif_year":
            return str(when.year)
        if resolver == "exif_month":
            return f"{when.month:02d}"
        if resolver == "exif_day":
            return f"{when.day:02d}"
        return when.strftime("%Y-%m-%d")
    return UNRESOLVED
