"""Make the eval's shared modules importable when a script in this folder runs directly.

Python puts only the running script's folder on the import path. ``utils.py`` lives at
the eval root; the search eval's ``evals_search_utils.py`` and the screening eval's
``metrics.py`` (price table) live one folder over. Every script here imports this
module first. The copy in ``tests/`` is identical.
"""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = next(p for p in (_here, *_here.parents) if (p / "utils.py").is_file())
_evals = _root.parent
for _i, _folder in enumerate((_root, _evals / "search", _evals / "screening"), start=1):
    if str(_folder) not in sys.path:
        sys.path.insert(_i, str(_folder))
