"""Build ``targets.json``: each screening question and its criteria, from published text.

No language model writes any of this. Every question and every criterion is
copied from the source, chosen by a fixed rule, and stored with where it came
from. Running the script again gives the same file.

Per question (one review or gap map):

- ``query`` is the published title, with a trailing review-type or map-type
  clause removed ("...: a systematic review", "...: an evidence gap map").
  This is the short, user-like scope intent.
- ``criteria`` is published text that says what the review includes:
  - CSMeD (Cochrane): the "Objectives" section of the review's abstract.
  - SYNERGY: the eligibility criteria that SYNERGY quotes from the paper,
    one criterion per line.
  - 3ie: the map's own top-level intervention and outcome groups. Two maps
    (climate, anaemia) are not on the 3ie portal's open map feed, so they
    have no criteria.

The criteria go through the product's own ``_compose_screen_intent``, which
adds them under the intent as "Additional screening criteria" and refuses a
result over 2,000 characters. When it refuses, the last criterion is dropped
until it fits, and the number dropped is recorded.

Sources are downloaded once into ``datasets/sources/`` (not in git):
SYNERGY's ``datasets.toml`` at a fixed commit, the review titles from OpenAlex
by DOI, and the 3ie map data. CSMeD's metadata is already in ``datasets/``.
OpenAlex and 3ie can change their records, so the build also writes
``targets_sources.json`` (in git): a SHA-256 fingerprint of every source file
it read. ``targets.json`` is the frozen question set; a rebuild that changes it
or its fingerprints shows that a source changed.

    uv run --project backend python scripts/evals/screening/build_targets.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from adapter import _title_key, datasets_dir
from policy_atlas.evidence_search.assess.screen import (
    CRITERIA_LIST_MAX,
    SCREENING_CRITERION_MAX,
    ScreenDirectiveError,
    _compose_screen_intent,
)
from targets import ALL_EVAL_TARGETS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "search"))
from evals_search_utils import openalex_get  # noqa: E402

ROOT = Path(__file__).resolve().parent
TARGETS_JSON = ROOT / "targets.json"
SOURCES_JSON = ROOT / "targets_sources.json"
# Every source file the build read, recorded with a fingerprint in
# targets_sources.json, so a rebuild on another machine can be checked.
_READ: set[Path] = set()
SOURCES = datasets_dir() / "sources"

SYNERGY_COMMIT = "dc2dadfdbb98eb1b4259604789abd640aa3b693e"
SYNERGY_TOML = (
    "https://raw.githubusercontent.com/asreview/synergy-dataset/"
    f"{SYNERGY_COMMIT}/datasets.toml"
)
THREE_IE_API = "https://api.developmentevidence.3ieimpact.org"
THREE_IE_PORTAL = "https://developmentevidence.3ieimpact.org/egm/"

# Which published map each local 3ie file is. Titles are copied exactly from
# the 3ie portal record (``slug`` maps) or the 3ie publication page (``url``
# maps). For portal maps the script also checks that the local file's studies
# are the map's studies.
THREE_IE_MAPS: dict[str, dict[str, str]] = {
    "3ie_EGM_Climate_2024": {
        "title": "Mapping the evidence of climate change and biodiversity interventions "
        "on environmental and human outcomes in low- and middle-income countries",
        "url": "https://www.3ieimpact.org/evidence-hub/publications/evidence-gap-maps/"
        "mapping-evidence-climate-change-and-biodiversity",
    },
    "3ie_EGM_Governance_2023": {
        "title": "Strengthening good governance through government effectiveness in "
        "low- and middle-income countries: an evidence gap map",
        "slug": "good-governance-through-government-effectiveness-evidence-gap-map",
    },
    "3ie_EGM_Migration_2023": {
        "title": "Addressing Root Causes and Drivers of Irregular Migration: "
        "An Evidence Gap Map",
        "slug": "addressing-root-causes-and-drivers-of-irregular-migration-an-evidence-gap-map",
    },
    "3ie_EGM_FoodSystems_2024": {
        "title": "The effects of food systems interventions on food security and "
        "nutrition outcomes in low- and middle- income countries: a living evidence "
        "gap map",
        "slug": "food-systems-and-nutrition-evidence-gap-map",
    },
    "3ie_EGM_SRHR_2024": {
        "title": "Sexual and Reproductive Health and Rights Evidence Gap Map",
        "slug": "sexual-reproductive-health-rights-in-low-and-middle-income-countries",
    },
    "3ie_EGM_WASH_2023": {
        "title": "Mapping water, sanitation and hygiene achievements to prosperity, "
        "stability and resilience: An outcome-to-outcome systematic map",
        "slug": "reaper-wash-evidence-gap-map",
    },
    "3ie_EGM_Anaemia_2024": {
        "title": "Interventions to reduce anaemia in low- and middle-income countries: "
        "An evidence gap map",
        "url": "https://3ieimpact.org/evidence-hub/publications/evidence-gap-map/"
        "interventions-reduce-anaemia-low-and-middle-income",
    },
    "3ie_EGM_Energy_2024": {
        "title": "Promoting Sustainable Energy Development through Access, Renewables "
        "and Efficient Technologies: An Evidence Gap Map",
        "slug": "sustainable-energy-evidence-gap-map",
    },
    "3ie_EGM_LandUse_2024": {
        "title": "Land-use change and forestry programmes in low- and middle-income "
        "countries: an evidence gap map update",
        "slug": "land-use-update",
    },
    "3ie_EGM_Resilience_2023": {
        "title": "Strengthening resilience against shocks, stressors and recurring "
        "crises in low- and middle-income countries: an evidence gap map",
        "slug": "building-resilient-societies-in-low-and-middle-income-countries-an-evidence-gap-map",
    },
}

# A trailing clause naming the kind of publication, after ":", "." or a dash.
_TYPE_WORDS = r"(?:review|meta.?analysis|gap map|systematic map|evidence map)"
_TAIL_AFTER_SEPARATOR = re.compile(
    rf"(?:[:.]|\s[–—-])\s+[^:.]*\b{_TYPE_WORDS}\b[^:.]*$", re.IGNORECASE
)
_TAIL_NO_SEPARATOR = re.compile(r"\s+evidence gap map(?:\s+update)?$", re.IGNORECASE)

# The overlap between a local 3ie file and the portal map it should be.
MIN_STUDY_OVERLAP = 0.9


def clean_title(title: str) -> str:
    """Remove a trailing publication-type clause and tidy the spaces.

    Args:
        title: A published review or map title.

    Returns:
        The title as a scope statement, or the title unchanged when no rule
        applies.
    """
    text = " ".join(title.split())
    text = _TAIL_AFTER_SEPARATOR.sub("", text)
    text = _TAIL_NO_SEPARATOR.sub("", text)
    return text.strip() or " ".join(title.split())


def fit_criteria(query: str, criteria: list[str]) -> tuple[list[str], int]:
    """Drop trailing criteria until the product accepts the composed intent.

    Args:
        query: The scope intent.
        criteria: Criteria in source order.

    Returns:
        The criteria that fit, and how many were dropped.

    Raises:
        ValueError: If a single criterion is longer than the product allows.
    """
    split: list[str] = []
    for criterion in criteria:
        # The product caps one criterion at SCREENING_CRITERION_MAX characters;
        # a longer paragraph becomes one criterion per sentence.
        parts = (
            re.split(r"(?<=[.;])\s+", criterion)
            if len(criterion) > SCREENING_CRITERION_MAX
            else [criterion]
        )
        for part in parts:
            if len(part) > SCREENING_CRITERION_MAX:
                raise ValueError(
                    f"Sentence over {SCREENING_CRITERION_MAX} chars: {part[:80]}"
                )
            split.append(part)
    criteria = split
    kept = criteria[:CRITERIA_LIST_MAX]
    while kept:
        try:
            _compose_screen_intent(query, kept)
            break
        except ScreenDirectiveError:
            kept = kept[:-1]
    return kept, len(criteria) - len(kept)


def _cached(path: Path, fetch: Any) -> Any:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fetch(), ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def csmed_entry(review_id: str) -> dict[str, Any]:
    """Title and Objectives of one Cochrane review, from the CSMeD metadata."""
    path = datasets_dir() / "CESMeD" / "CSMeD-FT-dev_reviews_metadata.json"
    _READ.add(path)
    review = json.loads(path.read_text(encoding="utf-8"))[review_id]
    match = re.search(
        r"Objectives\s+(.*?)\s+(?:Search methods|Selection criteria)",
        review["abstract"],
        re.S,
    )
    if match is None:
        raise ValueError(f"No Objectives section in {review_id}")
    return {
        "title": review["title"],
        "criteria": [" ".join(match.group(1).split())],
        "title_source": f"CSMeD-FT-dev_reviews_metadata.json [{review_id}].title",
        "criteria_source": f"CSMeD-FT-dev_reviews_metadata.json [{review_id}].abstract, "
        "Objectives section",
    }


def synergy_entry(key: str) -> dict[str, Any]:
    """Title (OpenAlex, by DOI) and quoted eligibility criteria of one SYNERGY review."""
    toml_path = SOURCES / "synergy" / f"datasets-{SYNERGY_COMMIT[:12]}.toml"
    if not toml_path.exists():
        toml_path.parent.mkdir(parents=True, exist_ok=True)
        response = httpx.get(SYNERGY_TOML, timeout=60.0)
        response.raise_for_status()
        toml_path.write_bytes(response.content)
    _READ.add(toml_path)
    datasets = tomllib.loads(toml_path.read_text(encoding="utf-8"))["datasets"]
    publication = next(item for item in datasets if item["key"] == key)["publication"]
    doi = publication["doi"]

    def fetch_work() -> dict[str, Any]:
        response = openalex_get(f"/works/doi:{doi}", select="id,doi,title")
        response.raise_for_status()
        return response.json()

    work = _cached(SOURCES / "openalex" / f"{key}.json", fetch_work)
    _READ.add(SOURCES / "openalex" / f"{key}.json")
    criteria = [
        re.sub(r"^[-•*]\s*", "", line).strip()
        for line in publication["eligibility_criteria"].splitlines()
    ]
    return {
        "title": work["title"],
        "criteria": [line for line in criteria if line],
        "title_source": f"OpenAlex {work['id']} (doi:{doi})",
        "criteria_source": f"SYNERGY datasets.toml @ {SYNERGY_COMMIT[:12]}, "
        f"[{key}].publication.eligibility_criteria",
    }


def _post(path: str, payload: dict[str, Any]) -> Any:
    response = httpx.post(f"{THREE_IE_API}{path}", json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()


def three_ie_entry(file_stem: str) -> dict[str, Any]:
    """Title and top-level framework groups of one 3ie gap map."""
    source = THREE_IE_MAPS[file_stem]
    if "slug" not in source:
        return {
            "title": source["title"],
            "criteria": [],
            "title_source": source["url"],
            "criteria_source": "none: the map is not on the 3ie portal's open map feed",
        }
    slug = source["slug"]

    def fetch_map() -> dict[str, Any]:
        project = _post("/api/project_details", {"url": slug})["data"]["project_id"]
        return _post("/api/get_map_data", {"project_id": project, "lang": "en"})

    data = _cached(SOURCES / "3ie" / f"{slug}.json", fetch_map)
    _READ.add(SOURCES / "3ie" / f"{slug}.json")
    map_titles = {
        _title_key(record.get("title")) for record in data["project_records"].values()
    }
    local = pd.read_csv(datasets_dir() / "Three_IE" / f"{file_stem}.csv")
    local_titles = set(local["Title"].map(_title_key))
    overlap = len(local_titles & map_titles) / len(local_titles)
    if overlap < MIN_STUDY_OVERLAP:
        raise ValueError(
            f"{file_stem} shares only {overlap:.0%} of studies with {slug}"
        )

    def groups(key: str) -> str:
        return "; ".join(
            " ".join(group["map_layout_group_title"].split()) for group in data[key]
        )

    return {
        "title": source["title"],
        "criteria": [
            f"Interventions: {groups('interventions')}",
            f"Outcomes: {groups('outcomes')}",
        ],
        "title_source": f"{THREE_IE_PORTAL}{slug}",
        "criteria_source": f"3ie get_map_data for {slug}: top-level intervention and "
        f"outcome groups ({overlap:.0%} of the local file's studies are on this map)",
    }


def build() -> list[dict[str, Any]]:
    """One entry per target, in catalogue order."""
    entries = []
    for target in ALL_EVAL_TARGETS:
        source = target["dataset_source"]
        if source == "CSMeD":
            found = csmed_entry(target["id"])
        elif source == "SYNERGY":
            found = synergy_entry(target["id"])
        else:
            found = three_ie_entry(target["id"])
        query = clean_title(found["title"])
        criteria, dropped = fit_criteria(query, found["criteria"])
        entries.append(
            {
                "name": target["name"],
                "id": target["id"],
                "dataset_source": source,
                "query": query,
                "criteria": criteria,
                "criteria_dropped": dropped,
                "published_title": found["title"],
                "title_source": found["title_source"],
                "criteria_source": found["criteria_source"],
            }
        )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args()
    entries = build()
    text = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
    TARGETS_JSON.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    sources = {
        path.relative_to(datasets_dir()).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(_READ)
    }
    SOURCES_JSON.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    for entry in entries:
        print(
            f"{entry['dataset_source']:8} {entry['name']:28} criteria={len(entry['criteria'])}"
            f" dropped={entry['criteria_dropped']}  {entry['query']}"
        )
    print(f"Wrote {TARGETS_JSON} (sha256 {digest}) and {SOURCES_JSON.name}")


if __name__ == "__main__":
    main()
