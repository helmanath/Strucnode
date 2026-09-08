#!/usr/bin/env python3
"""Launcher kept so ``python strucnode.py`` still works.

The application now lives in the ``strucnode`` package; prefer
``python -m strucnode`` or the ``strucnode`` command installed by pip.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strucnode.app import main  # noqa: E402

if __name__ == "__main__":
    main()
