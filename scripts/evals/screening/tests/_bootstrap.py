"""Make the screening eval's modules importable when a script in this folder runs.

Python puts only the running script's folder on the import path. The shared
code (``adapter.py``, ``targets.py``, ``vote.py``, ``metrics.py``) lives in
the parent folder, so every script below the root imports this module first.
"""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = next(
    parent
    for parent in (_here, *_here.parents)
    if (parent / "targets.py").is_file() and (parent / "adapter.py").is_file()
)
for _index, _folder in enumerate((_root, _root / "measure"), start=1):
    if str(_folder) not in sys.path:
        sys.path.insert(_index, str(_folder))
