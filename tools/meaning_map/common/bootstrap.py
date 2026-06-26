"""Make ``common`` importable when a tool is run as a standalone script.

Each CLI starts with::

    from common.bootstrap import setup_path  # noqa
    setup_path()

so ``python tools/meaning_map/setup.py`` works from any cwd without
requiring the package to be installed.
"""

from __future__ import annotations

import sys
from pathlib import Path


def setup_path() -> None:
    pkg_root = Path(__file__).resolve().parent.parent  # tools/meaning_map
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))
