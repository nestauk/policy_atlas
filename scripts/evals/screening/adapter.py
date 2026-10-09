"""Load the three screening ground-truth sources into one table shape.

Each row is one document: an id, a title, an abstract, and
``ground_truth_relevant`` (1 = a human included it, 0 = a human excluded it).
3ie files list included studies only, so the negatives are drawn from the
other 3ie files.

Every source then goes through the same seeded sample, in one of two sizes
(``SIZES``). ``mini`` is about 300 documents across all 30 questions and is
the set for trying settings cheaply. ``full`` is about 3,000. The same seed
draws both, so every ``mini`` document is also in ``full``.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Written into the table when a source row has no abstract. The runner treats
# this sentence as "no abstract" when it builds the model payload.
MISSING_ABSTRACT = "No abstract available"
MISSING_TITLE = "No title"

COLUMNS = ["doc_id", "title", "abstract_or_summary", "ground_truth_relevant"]

# Size of the 3ie negative pool for one question, split evenly across the
# other maps. ``sample_data`` then draws from this pool.
THREE_IE_NEGATIVE_POOL = 200

# Per question: (most included documents, most excluded documents). Excluded
# documents are also capped at NEGATIVES_PER_POSITIVE per included one.
SIZES: dict[str, tuple[int, int]] = {"mini": (5, 5), "full": (50, 100)}
NEGATIVES_PER_POSITIVE = 3


def datasets_dir() -> Path:
    """Return the on-disk folder ``sync_s3.py download`` fills.

    Returns:
        ``datasets/`` next to this file.
    """
    return Path(__file__).resolve().parent / "datasets"


def load_and_adapt_dataset(
    target: dict[str, str],
    datasets_root: Path | None = None,
    size: str = "full",
) -> pd.DataFrame:
    """Load one target and apply the sample for ``size``.

    Args:
        target: One entry from ``targets.py`` (``id``, ``dataset_source``).
        datasets_root: Folder holding ``CESMeD``, ``SYNERGY`` and ``Three_IE``.
            Defaults to ``datasets_dir()``.
        size: A key of ``SIZES``: ``mini`` or ``full``.

    Returns:
        Columns ``doc_id``, ``title``, ``abstract_or_summary``,
        ``ground_truth_relevant``.

    Raises:
        ValueError: If ``dataset_source`` is not one of the three known sources.
        FileNotFoundError: If the source file is not on disk.
    """
    root = datasets_root or datasets_dir()
    source = target["dataset_source"]
    if source == "CSMeD":
        frame = load_csmed(target["id"], root)
    elif source == "SYNERGY":
        frame = load_synergy(target["id"], root)
    elif source == "3ie":
        frame = load_three_ie(target["id"], root)
    else:
        raise ValueError(f"Unknown source: {source}")

    frame["abstract_or_summary"] = frame["abstract_or_summary"].fillna(MISSING_ABSTRACT)
    frame["title"] = frame["title"].fillna(MISSING_TITLE)
    return sample_data(frame, size)


def load_csmed(review_id: str, datasets_root: Path | None = None) -> pd.DataFrame:
    """Load one Cochrane review from the CSMeD full-text development file.

    Args:
        review_id: Cochrane id, for example ``CD010254``.
        datasets_root: Folder holding ``CESMeD/``. Defaults to ``datasets_dir()``.

    Returns:
        The review's documents, labelled from the ``decision`` column
        (``included`` is relevant).

    Raises:
        FileNotFoundError: If ``CESMeD/CSMeD-FT-dev.csv`` is missing.
    """
    root = datasets_root or datasets_dir()
    path = root / "CESMeD" / "CSMeD-FT-dev.csv"
    if not path.exists():
        raise FileNotFoundError(f"CSMeD dataset not found at {path}")

    frame = pd.read_csv(path)
    frame = frame[frame["review_id"] == review_id].copy()
    if frame.empty:
        logger.warning("No documents found for CSMeD review_id: %s", review_id)
        return pd.DataFrame(columns=COLUMNS)

    frame["ground_truth_relevant"] = frame["decision"].apply(
        lambda value: 1 if str(value).strip().lower() == "included" else 0
    )
    frame = frame.rename(columns={"abstract": "abstract_or_summary"})
    frame["doc_id"] = "CSMeD_" + frame["document_id"].astype(str)
    return frame[COLUMNS]


def load_synergy(dataset_id: str, datasets_root: Path | None = None) -> pd.DataFrame:
    """Load one SYNERGY review CSV.

    Args:
        dataset_id: File stem, for example ``van_Dis_2020``.
        datasets_root: Folder holding ``SYNERGY/``. Defaults to ``datasets_dir()``.

    Returns:
        The review's documents. ``label_included`` is the label. The document
        id is the row number, because these files have no stable id column.

    Raises:
        FileNotFoundError: If ``SYNERGY/{dataset_id}.csv`` is missing.
        ValueError: If the file has no ``label_included`` column.
    """
    root = datasets_root or datasets_dir()
    path = root / "SYNERGY" / f"{dataset_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Could not find SYNERGY dataset: {path}")

    frame = pd.read_csv(path)
    if "label_included" not in frame.columns:
        raise ValueError(f"Column 'label_included' not found in {dataset_id}.csv")
    frame["ground_truth_relevant"] = frame["label_included"].astype(int)
    frame = frame.rename(columns={"abstract": "abstract_or_summary"})
    frame["doc_id"] = f"SYNERGY_{dataset_id}_" + frame.index.astype(str)
    return frame[COLUMNS]


def load_three_ie(dataset_id: str, datasets_root: Path | None = None) -> pd.DataFrame:
    """Load one 3ie gap map as positives and sample other maps as negatives.

    Args:
        dataset_id: File stem, for example ``3ie_EGM_Climate_2024``.
        datasets_root: Folder holding ``Three_IE/``. Defaults to ``datasets_dir()``.

    Returns:
        Every study in the named file, labelled relevant, plus a pool of
        about ``THREE_IE_NEGATIVE_POOL`` studies from the other files,
        labelled not relevant. The pool takes the same number from each other
        map, so a large map does not dominate it. A study whose title is also
        on the named map is left out of the pool: the maps overlap, and 3ie's
        own coders count that study as relevant. A study on two other maps
        enters the pool once. The draw uses ``random_state=42``.

    Raises:
        FileNotFoundError: If the folder or the named file is missing.
        ValueError: If no other file can supply negatives.
    """
    root = (datasets_root or datasets_dir()) / "Three_IE"
    if not root.exists():
        raise FileNotFoundError(f"3ie directory not found at {root}")

    positive_path = root / f"{dataset_id}.csv"
    if not positive_path.exists():
        raise FileNotFoundError(f"3ie dataset not found at {positive_path}")

    positives = _standardize_three_ie_frame(
        pd.read_csv(positive_path), dataset_id, label_value=1
    )
    on_target_map = set(positives["title"].map(_title_key))
    other_maps: list[pd.DataFrame] = []
    for csv_file in sorted(root.glob("*.csv")):
        if csv_file.name == positive_path.name:
            continue
        try:
            frame = _standardize_three_ie_frame(
                pd.read_csv(csv_file), csv_file.stem, label_value=0
            )
        except Exception as exc:
            logger.warning(
                "Failed to load 3ie negative sample from %s: %s", csv_file, exc
            )
            continue
        other_maps.append(frame[~frame["title"].map(_title_key).isin(on_target_map)])

    if not other_maps:
        raise ValueError("No negative pools available for 3ie sampling.")

    per_map = THREE_IE_NEGATIVE_POOL // len(other_maps)
    negatives = pd.concat(
        [
            frame.sample(n=min(per_map, len(frame)), random_state=42)
            for frame in other_maps
        ],
        ignore_index=True,
    )
    negatives = negatives[~negatives["title"].map(_title_key).duplicated()]

    combined = pd.concat([positives, negatives], ignore_index=True)
    return combined.sample(frac=1, random_state=42).reset_index(drop=True)


def _standardize_three_ie_frame(
    frame: pd.DataFrame, dataset_label: str, label_value: int
) -> pd.DataFrame:
    """Map a 3ie export onto the shared four columns.

    Args:
        frame: One gap-map export.
        dataset_label: Used in ``doc_id``.
        label_value: 1 for the target map, 0 for a map used as negatives.

    Returns:
        The shared four-column table.

    Raises:
        ValueError: If no title column is present.
    """
    title_col = _match_column(frame, ["title"])
    abstract_col = _match_column(frame, ["abstract", "abstract_text", "summary"])
    if title_col is None:
        raise ValueError(
            f"Could not find a title column in 3ie dataset {dataset_label}"
        )
    if abstract_col is None:
        logger.warning(
            "No abstract column detected for %s; defaulting to the title.",
            dataset_label,
        )
        abstracts = frame[title_col]
    else:
        abstracts = frame[abstract_col]
    return pd.DataFrame(
        {
            "doc_id": frame.index.map(lambda idx: f"3IE_{dataset_label}_{idx}"),
            "title": frame[title_col],
            "abstract_or_summary": abstracts,
            "ground_truth_relevant": int(label_value),
        }
    )


def _title_key(title: object) -> str:
    """Lower-case a title and collapse punctuation, to spot the same study twice."""
    return re.sub(r"\W+", " ", str(title).lower()).strip()


def dataset_manifest(datasets_root: Path | None = None) -> dict[str, str]:
    """Fingerprint every downloaded dataset file, so two runs can be matched.

    ``sync_s3.py download`` does not delete local files that were removed on
    S3, and the 3ie loader reads every file in its folder. Two machines can
    therefore build different samples from the same command. Each run stores
    this manifest; equal manifests mean equal inputs.

    Args:
        datasets_root: The datasets folder. Defaults to ``datasets_dir()``.

    Returns:
        Relative path to SHA-256 hash (a fingerprint of the file's content),
        sorted by path.
    """
    root = datasets_root or datasets_dir()
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.name.startswith(".")
    }


def _match_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column whose lower-case name is in ``candidates``."""
    lower_map = {column.strip().lower(): column for column in frame.columns}
    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


def sample_data(frame: pd.DataFrame, size: str = "full") -> pd.DataFrame:
    """Keep a seeded sample of included and excluded documents.

    Included documents are capped at the first number in ``SIZES[size]``.
    Excluded documents are capped at the second number and at three per
    included document kept. A question with no included documents keeps up to
    the second number of excluded ones. ``random_state=42`` makes the draw the
    same on every run. A smaller draw from the same pool with the same seed is
    the start of a larger one, so ``mini`` is a subset of ``full``.

    Args:
        frame: A labelled table with ``ground_truth_relevant``.
        size: A key of ``SIZES``.

    Returns:
        The sampled table, shuffled.

    Raises:
        KeyError: If ``size`` is not in ``SIZES``.
    """
    max_positives, max_negatives = SIZES[size]
    if frame.empty:
        return frame

    positives = frame[frame["ground_truth_relevant"] == 1]
    negatives = frame[frame["ground_truth_relevant"] == 0]
    n_pos = min(len(positives), max_positives)
    n_neg = min(len(negatives), max_negatives)
    if n_pos:
        n_neg = min(n_neg, n_pos * NEGATIVES_PER_POSITIVE)

    sampled_positives = positives.sample(n=n_pos, random_state=42)
    sampled_negatives = negatives.sample(n=n_neg, random_state=42)
    combined = pd.concat([sampled_positives, sampled_negatives])
    combined = combined.sample(frac=1, random_state=42).reset_index(drop=True)
    logger.info(
        "Sampled %s positives and %s negatives. Total: %s",
        len(sampled_positives),
        len(sampled_negatives),
        len(combined),
    )
    return combined
