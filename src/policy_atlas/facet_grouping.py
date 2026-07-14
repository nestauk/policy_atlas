"""Shared facet-grouping bounds (task 012, narrowed in 022).

The ``group_facet_v1`` one-call partition prompt and its backends were retired
by 022's two-stage clustering engine (``group_clustering.py`` supersedes them;
the machinery was deleted by 022's review-stack simplification pass). What
remains here is the substrate the engine's group caller still shares: the
scale/length bounds and the forbidden-label set consumed by ``facet_values.py``
and ``group.py``.
"""

from __future__ import annotations

# Scale guard — fail closed (contract rev 1.3): above the cap the component
# fails structurally before any call; the large-corpus algorithm is a recorded
# eval-gated seam, never a degraded sample/assign pass grown here. Raised in
# 018's standard-depth regrade: demo-validated at 280 live distinct values;
# the eval slice owns final calibration.
FACET_VALUE_CAP = 400

# Per-string bound on prompt input (012 review, security lane): value surfaces
# and counterparts are unbounded upstream wire text — an oversize string fails
# the component closed before any call, mirroring the FACET_VALUE_CAP posture.
VALUE_SURFACE_MAX = 500

# Label/description bounds (deterministic output-checking beyond prompt rules —
# the 009 validate_themes precedent; enforced in group.py's clustering caller).
LABEL_MAX = 80
DESCRIPTION_MAX = 500

# Exact casefolded forbidden set: v2's "General Theme" collapse defect closed in
# code — a catch-all label rejects that group (members flow to the repair);
# the ungroupable path exists.
FORBIDDEN_GROUP_LABELS = frozenset(
    {"general", "miscellaneous", "other", "misc", "general theme",
     "uncategorised", "uncategorized"}
)
