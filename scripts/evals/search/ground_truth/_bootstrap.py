"""Make the eval's shared modules importable when a script in this folder runs directly.

Python puts only the running script's own folder on the import path. The shared code
lives one level up (``evals_search_utils.py``) and in the sibling folders ``ground_truth/``
and ``measure/``, so every script below the root imports this module first. An identical
copy sits in each folder; whichever loads first does the work.
"""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = next(
    p for p in (_here, *_here.parents) if (p / "evals_search_utils.py").exists()
)
for _i, _folder in enumerate(
    (
        _root,
        _root / "ground_truth",
        _root / "ground_truth" / "getters",
        _root / "measure",
    ),
    start=1,
):
    if str(_folder) not in sys.path:
        sys.path.insert(_i, str(_folder))
