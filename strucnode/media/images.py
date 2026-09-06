"""Decoding still images: RAW thumbnails and panorama detection."""

from __future__ import annotations

import io
import logging
import subprocess

log = logging.getLogger(__name__)

PANORAMA_RATIO = (1.9, 2.1)
DCRAW_TIMEOUT = 15


def open_raw_thumbnail(path: str):
    """Return a PIL image for a RAW photo, or None if nothing can decode it.

    Tries the embedded thumbnail through ``rawpy`` first (fast), then a full
    half-size develop, then Pillow, then ``dcraw`` as a last resort. Every step
    is optional -- a missing library just moves to the next one.
    """
    try:
        import rawpy
        from PIL import Image

        with rawpy.imread(path) as raw:
            thumb = raw.extract_thumb()
            if thumb.format.name in ("JPEG", "PNG"):
                return Image.open(io.BytesIO(thumb.data))
            return Image.fromarray(raw.postprocess(use_camera_wb=True, half_size=True))
    except ImportError:
        pass
    except Exception:
        log.debug("rawpy failed on %r", path, exc_info=True)

    try:
        from PIL import Image

        img = Image.open(path)
        img.thumbnail((1920, 1920))
        return img
    except Exception:
        log.debug("Pillow failed on %r", path, exc_info=True)

    try:
        from PIL import Image

        proc = subprocess.run(["dcraw", "-e", "-c", path],
                              capture_output=True, timeout=DCRAW_TIMEOUT)
        if proc.returncode == 0 and proc.stdout:
            return Image.open(io.BytesIO(proc.stdout))
    except (OSError, subprocess.SubprocessError):
        log.debug("dcraw unavailable for %r", path, exc_info=True)
    return None


def is_360_image(path: str) -> bool:
    """Return True when the image looks like an equirectangular panorama."""
    try:
        from PIL import Image

        with Image.open(path) as img:
            width, height = img.size
            info = img.info
        if height and PANORAMA_RATIO[0] <= width / height <= PANORAMA_RATIO[1]:
            return True
        xmp = str(info.get("xmp", "") or info.get("XML:com.adobe.xmp", ""))
        return "equirectangular" in xmp.lower() or "ProjectionType" in xmp
    except Exception:
        log.debug("cannot inspect %r", path, exc_info=True)
        return False
