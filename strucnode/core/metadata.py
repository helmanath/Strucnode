"""EXIF extraction.

A single parse per file feeds both the metadata panel and the date fields used
by the organizer -- the two used to be separate implementations that opened and
decoded every photo twice.

Keys are stable English identifiers, never translated strings: they are used as
tree column ids, filter keys and dict keys. Their display names come from
:data:`FIELD_LABELS` and are resolved at render time.
"""

from __future__ import annotations

import datetime
import logging
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from .categories import IMAGE_EXTS, RAW_EXTS

log = logging.getLogger(__name__)

#: Metadata key -> i18n key, in display order.
FIELD_LABELS: dict[str, str] = {
    "iso": "col_iso",
    "focal_length": "col_focal",
    "model": "col_device",
    "make": "col_brand",
    "aperture": "col_aperture",
    "exposure": "col_exposure",
    "date": "meta_date",
}

#: Fields offered as explorer filter combos.
FILTER_FIELDS: tuple[str, ...] = ("iso", "focal_length", "model", "aperture")

_MAX_CACHE = 20_000
_cache: "OrderedDict[tuple, ExifData]" = OrderedDict()

_DATE_TAGS_EXIFREAD = ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime")
_DATE_TAGS_PIL = ("DateTimeOriginal", "DateTimeDigitized", "DateTime")


@dataclass
class ExifData:
    """Reduced EXIF payload for one file."""

    values: dict[str, str] = field(default_factory=dict)
    datetime: datetime.datetime | None = None

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key, default)

    def __bool__(self) -> bool:
        return bool(self.values)


def _parse_dt(raw: str) -> datetime.datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _ratio(raw: str) -> float | None:
    """Parse an EXIF rational such as ``"50/1"`` into a float."""
    try:
        if "/" in raw:
            num, den = raw.split("/", 1)
            den_f = float(den)
            return float(num) / den_f if den_f else None
        return float(raw)
    except ValueError:
        return None


def _cache_key(path: str) -> tuple:
    try:
        st = os.stat(path)
        return (path, st.st_mtime_ns, st.st_size)
    except OSError:
        return (path, 0, 0)


def _read_with_exifread(path: str, out: ExifData) -> None:
    import exifread

    with open(path, "rb") as fh:
        tags = exifread.process_file(fh, stop_tag="UNDEF", details=False, debug=False)

    def raw(key: str) -> str | None:
        val = tags.get(key)
        return str(val).strip() if val else None

    if v := raw("EXIF ISOSpeedRatings"):
        out.values["iso"] = v
    if v := raw("EXIF FocalLength"):
        mm = _ratio(v)
        out.values["focal_length"] = f"{mm:.0f} mm" if mm else v
    if v := raw("Image Make"):
        out.values["make"] = v
    if v := raw("Image Model"):
        out.values["model"] = v
    if v := raw("EXIF ExposureTime"):
        out.values["exposure"] = f"{v} s"
    if v := raw("EXIF FNumber"):
        f_num = _ratio(v)
        out.values["aperture"] = f"f/{f_num:.1f}" if f_num else v
    for tag in _DATE_TAGS_EXIFREAD:
        if v := raw(tag):
            out.datetime = out.datetime or _parse_dt(v)
            if out.datetime:
                out.values.setdefault("date", v)
                break


def _read_with_pillow(path: str, out: ExifData) -> None:
    from PIL import ExifTags, Image

    with Image.open(path) as img:
        exif = getattr(img, "_getexif", lambda: None)()
    if not exif:
        return
    named = {ExifTags.TAGS.get(tag_id, tag_id): val for tag_id, val in exif.items()}

    def num(val) -> float | None:
        try:
            return float(val[0]) / float(val[1]) if isinstance(val, tuple) else float(val)
        except (TypeError, ValueError, ZeroDivisionError, IndexError):
            return None

    if "ISOSpeedRatings" in named:
        out.values.setdefault("iso", str(named["ISOSpeedRatings"]))
    if (val := named.get("FocalLength")) is not None:
        mm = num(val)
        out.values.setdefault("focal_length", f"{mm:.0f} mm" if mm else str(val))
    if val := named.get("Make"):
        out.values.setdefault("make", str(val).strip())
    if val := named.get("Model"):
        out.values.setdefault("model", str(val).strip())
    if (val := named.get("ExposureTime")) is not None:
        secs = num(val)
        if secs and secs < 1:
            out.values.setdefault("exposure", f"1/{round(1 / secs)} s")
        elif secs:
            out.values.setdefault("exposure", f"{secs:g} s")
    if (val := named.get("FNumber")) is not None:
        f_num = num(val)
        out.values.setdefault("aperture", f"f/{f_num:.1f}" if f_num else str(val))
    for tag in _DATE_TAGS_PIL:
        if val := named.get(tag):
            out.datetime = out.datetime or _parse_dt(str(val))
            if out.datetime:
                out.values.setdefault("date", str(val).strip())
                break


def read_metadata(path: str) -> ExifData:
    """Return the EXIF payload of *path*, cached on (path, mtime, size).

    RAW files are read with ``exifread`` first because Pillow cannot decode most
    of them; standard images go through Pillow first and fall back to
    ``exifread``. Both libraries are optional: a missing one simply yields less
    metadata, never an error.
    """
    key = _cache_key(path)
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached

    out = ExifData()
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXTS or ext in RAW_EXTS:
        readers = ([_read_with_exifread, _read_with_pillow] if ext in RAW_EXTS
                   else [_read_with_pillow, _read_with_exifread])
        for reader in readers:
            try:
                reader(path, out)
            except ImportError:
                continue
            except Exception:
                log.debug("EXIF read failed for %r via %s", path, reader.__name__,
                          exc_info=True)
            if out.values and out.datetime:
                break

    _cache[key] = out
    if len(_cache) > _MAX_CACHE:
        _cache.popitem(last=False)
    return out


def read_exif(path: str) -> dict[str, str]:
    """Return the EXIF values of *path* as a plain dict of stable keys."""
    return dict(read_metadata(path).values)


def exif_datetime(path: str) -> datetime.datetime | None:
    """Return the capture date of *path*, or ``None`` when unavailable."""
    return read_metadata(path).datetime


def clear_cache() -> None:
    """Drop the metadata cache (used by tests and after a rescan)."""
    _cache.clear()
