"""Build and rank the paper and policy-document pools before they are persisted.

The search loop supplies already-fetched provider records.  This module deliberately
does no fetching or database work so its ranking rules can be tested against the
recorded research fixtures.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from math import log2, log10
from typing import Any, cast

# QueryOrigin lives in search_loop.py, which imports this module.  Keep origins as
# strings here to avoid a circular import.
SEEDS = 200
KEYWORD_PER_CALL = 200
SEMANTIC_PER_CALL = 50
BACKWARD_EXPAND = 200
RESOLVE_BATCH = 50
FORWARD_TOP = 20
FORWARD_MAX_CITES = 300
FORWARD_IDS_PER_CALL = 100
FORWARD_PAGES = 10
FORWARD_KEEP = 200
OVERTON_DOCS = 400
OVERTON_LANDMARKS = 15
SEED_RANK_SENTINEL = 10**6
RRF_K = 60  # the usual constant for reciprocal rank fusion (Cormack, Clarke and Buettcher 2009)
NOVEL_YEARS = 5  # a paper counts as novel when it is at most this many years old
COUPLING_LISTS = 3  # how many query lists the "cites the seeds" order counts as in the fusion


def short_id(openalex_id: str | None) -> str | None:
    """Return the short OpenAlex work id so records compare consistently.

    Args:
        openalex_id: A full OpenAlex URL, a short work id, or no id.

    Returns:
        The final URL component, or ``None`` when no id was supplied.
    """
    return openalex_id.rsplit("/", 1)[-1] if openalex_id else None


def record_short_id(record: dict[str, Any]) -> str | None:
    """Read a record's OpenAlex id in its short form for graph comparisons.

    Args:
        record: An OpenAlex work record.

    Returns:
        The record's short work id, if it has one.
    """
    return short_id(record.get("id"))


@dataclass(frozen=True)
class PaperCandidate:
    """One paper and the graph signals used to decide its place in the pool."""

    record: dict[str, Any]
    origin: str
    seed_rank: int
    inset: int
    coupling: int
    wcoupling: float
    forward_rank: int
    cited_by_count: int
    specificity: float

    @property
    def openalex_id(self) -> str | None:
        """Return the candidate's short OpenAlex work id."""
        return record_short_id(self.record)

    @property
    def doi(self) -> str | None:
        """Return the provider DOI without changing its provider formatting."""
        return self.record.get("doi")


def interleave(
    lists: list[list[dict[str, Any]]], key: Callable[[dict[str, Any]], str | None]
) -> list[dict[str, Any]]:
    """Merge ranked result lists fairly, keeping the earliest copy of each record.

    Each provider list gets its first result before any gets its second result.  This
    keeps one query from taking all early positions while preserving provider rank.

    Args:
        lists: Result lists in query order.
        key: Function returning a record identity, or ``None`` for unusable records.

    Returns:
        Unique records in round-robin rank order.
    """
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position in range(max((len(records) for records in lists), default=0)):
        for records in lists:
            if position >= len(records):
                continue
            record = records[position]
            record_key = key(record)
            if record_key is not None and record_key not in seen:
                seen.add(record_key)
                result.append(record)
    return result


def count_references(seeds: list[dict[str, Any]]) -> Counter[str]:
    """Count how often seeds cite each work, retaining deterministic tie order.

    Repeated references within one seed count once.  ``dict.fromkeys`` preserves the
    source order, which makes equal-frequency targets reproducible across processes.

    Args:
        seeds: Seed works whose reference lists have already been fetched.

    Returns:
        Counts keyed by short OpenAlex work id.
    """
    counts: Counter[str] = Counter()
    for seed in seeds:
        for reference in dict.fromkeys(seed.get("referenced_works") or []):
            reference_id = short_id(reference)
            if reference_id:
                counts[reference_id] += 1
    return counts


def backward_targets(counts: Counter[str], seed_ids: set[str], n: int) -> list[str]:
    """Choose the most frequently cited non-seed works for backward chasing.

    Args:
        counts: In-set citation counts in deterministic occurrence order.
        seed_ids: Work ids already in the seed pool.
        n: Maximum number of targets to choose.

    Returns:
        Target ids in descending count order, stable when counts tie.
    """
    return [work_id for work_id, _ in counts.most_common() if work_id not in seed_ids][:n]


def forward_seeds(
    seeds: list[dict[str, Any]], counts: Counter[str], *, top: int, max_cites: int
) -> list[str]:
    """Choose well-connected, not overly-global seeds for forward citation chasing.

    Args:
        seeds: Seed works in their established rank order.
        counts: In-set citation counts.
        top: Maximum number of eligible seeds to choose.
        max_cites: Exclude seeds cited more often than this global ceiling.

    Returns:
        Short ids for the selected seeds, ordered by in-set citations.
    """
    eligible = [
        (seed_id, seed)
        for seed in seeds
        if (seed_id := record_short_id(seed)) is not None
        and int(seed.get("cited_by_count") or 0) <= max_cites
    ]
    return [seed_id for seed_id, _ in sorted(eligible, key=lambda item: -counts[item[0]])[:top]]


def _seed_signals(
    record: dict[str, Any], seed_ids: set[str], counts: Counter[str]
) -> tuple[int, float]:
    """Return unweighted and weighted links from a record to the seed set."""
    cited_seeds: set[str] = set()
    for reference in record.get("referenced_works") or []:
        reference_id = short_id(reference)
        if reference_id in seed_ids:
            cited_seeds.add(reference_id)
    return len(cited_seeds), round(sum(log2(1 + counts[seed]) for seed in cited_seeds), 3)


def _specificity(inset: int, coupling: int, cited_by_count: int) -> float:
    """Dampen local graph signals when a work is globally cited everywhere."""
    return round((inset + coupling) / log10(cited_by_count + 10), 3)


def score_forward(
    citing: list[dict[str, Any]],
    seed_ids: set[str],
    counts: Counter[str],
    *,
    excluded_ids: set[str],
) -> list[PaperCandidate]:
    """Score papers that cite seeds before they join the paper candidate pool.

    Weighted coupling rewards citations to seed papers the seed set itself repeatedly
    cites.  Scores are rounded to three decimals to match the experiment, so close
    results deliberately tie and use the next ranking key.

    Args:
        citing: Works returned by the forward citation calls.
        seed_ids: Short ids already used as seeds.
        counts: In-set citation counts for the seeds.
        excluded_ids: Backward targets, which must not appear twice.

    Returns:
        Unique forward candidates ordered by their forward graph score.
    """
    candidates: list[PaperCandidate] = []
    seen: set[str] = set()
    for record in citing:
        work_id = record_short_id(record)
        if work_id is None or work_id in seen:
            continue
        seen.add(work_id)
        if work_id in seed_ids or work_id in excluded_ids:
            continue
        coupling, wcoupling = _seed_signals(record, seed_ids, counts)
        cited_by_count = int(record.get("cited_by_count") or 0)
        candidates.append(
            PaperCandidate(
                record=record,
                origin="snowball_forward",
                seed_rank=SEED_RANK_SENTINEL,
                inset=counts.get(work_id, 0),
                coupling=coupling,
                wcoupling=wcoupling,
                forward_rank=len(candidates),
                cited_by_count=cited_by_count,
                specificity=_specificity(counts.get(work_id, 0), coupling, cited_by_count),
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (-candidate.wcoupling, -candidate.coupling, candidate.forward_rank),
    )


def paper_candidates(
    seeds: list[tuple[dict[str, Any], str]],
    backward: list[dict[str, Any]],
    forward: list[PaperCandidate],
    counts: Counter[str],
) -> list[PaperCandidate]:
    """Combine fetched paper sources into comparable candidates for the final cut.

    The three-decimal scores intentionally mirror the experiment: near-equal scores
    tie, then the later ranking keys make the outcome stable and explainable.

    Args:
        seeds: Seed records paired with their query origin.
        backward: Resolved works cited by many seeds.
        forward: Already-scored papers that cite the seeds.
        counts: In-set citation counts from the seed references.

    Returns:
        Candidates from all three paths with the signals needed for ranking.
    """
    seed_ids = {work_id for record, _ in seeds if (work_id := record_short_id(record)) is not None}
    candidates: list[PaperCandidate] = []
    for seed_rank, (record, origin) in enumerate(seeds):
        work_id = record_short_id(record)
        coupling, wcoupling = _seed_signals(record, seed_ids, counts)
        inset = counts.get(work_id, 0) if work_id else 0
        cited_by_count = int(record.get("cited_by_count") or 0)
        candidates.append(
            PaperCandidate(
                record,
                origin,
                seed_rank,
                inset,
                coupling,
                wcoupling,
                SEED_RANK_SENTINEL,
                cited_by_count,
                _specificity(inset, coupling, cited_by_count),
            )
        )
    for record in backward:
        work_id = record_short_id(record)
        inset = counts.get(work_id, 0) if work_id else 0
        cited_by_count = int(record.get("cited_by_count") or 0)
        candidates.append(
            PaperCandidate(
                record,
                "snowball_backward",
                SEED_RANK_SENTINEL,
                inset,
                0,
                0.0,
                SEED_RANK_SENTINEL,
                cited_by_count,
                _specificity(inset, 0, cited_by_count),
            )
        )
    return candidates + forward


def rank_papers(cands: list[PaperCandidate]) -> list[PaperCandidate]:
    """Rank paper candidates by topic specificity, preserving meaningful ties.

    Args:
        cands: Candidates with graph signals already calculated.

    Returns:
        Candidates from highest to lowest final paper-pool priority.
    """
    return sorted(
        cands,
        key=lambda candidate: (
            -candidate.specificity,
            -candidate.wcoupling,
            -candidate.inset,
            candidate.seed_rank,
        ),
    )


def paper_key(record: dict[str, Any]) -> str:
    """Identity for duplicate detection: the exact normalised title plus the author names.

    OpenAlex often holds a preprint and the journal copy of one paper.  Two records
    are the same paper only when the title and the full author list match; a shared
    title with other authors (a common review title, say) stays two papers.

    Args:
        record: An OpenAlex work record.

    Returns:
        A comparison key, or the work id when the record has no title.
    """
    title = normalised_title(record.get("display_name"))
    if not title:
        return record_short_id(record) or ""
    authors = sorted(
        normalised_title((authorship.get("author") or {}).get("display_name"))
        for authorship in record.get("authorships") or []
    )
    return title + "|" + ",".join(authors)


def dedupe_papers(cands: list[PaperCandidate]) -> list[PaperCandidate]:
    """Keep one copy per paper: the most cited, then the earliest seed, in input order.

    Args:
        cands: Candidates from every path, possibly holding the same paper twice.

    Returns:
        The candidates with the lesser copies removed, original order preserved.
    """
    best: dict[str, PaperCandidate] = {}
    for candidate in sorted(cands, key=lambda c: (-c.cited_by_count, c.seed_rank)):
        best.setdefault(paper_key(candidate.record), candidate)
    kept = {id(candidate) for candidate in best.values()}
    return [candidate for candidate in cands if id(candidate) in kept]


def query_fusion(lists: list[list[dict[str, Any]]]) -> dict[str, float]:
    """Score each work by reciprocal rank fusion over every query's result list.

    A work returned near the top of many queries scores high; one returned once,
    low down, scores little.  Works no query returned are absent.

    Args:
        lists: Keyword and semantic result lists in rank order.

    Returns:
        Fusion scores keyed by short OpenAlex work id.
    """
    scores: dict[str, float] = {}
    for records in lists:
        for rank, record in enumerate(records):
            work_id = record_short_id(record)
            if work_id:
                scores[work_id] = scores.get(work_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def mix_strata(
    cands: list[PaperCandidate],
    lists: list[list[dict[str, Any]]],
    *,
    novel_from_year: int,
    coupling_lists: int = COUPLING_LISTS,
) -> tuple[list[PaperCandidate], list[PaperCandidate], list[PaperCandidate]]:
    """Build the three ordered strata the mix draws from.

    * relevant: papers with a fusion score, highest first.  The fusion runs over every
      query's result list plus the pool ordered by weighted coupling ("cites the
      seeds"), that order counted ``coupling_lists`` times, so a paper that cites
      many seeds ranks as if a few queries had returned it;
    * seminal: papers the seed set cites most, then the most cited globally;
    * novel: papers from ``novel_from_year`` on, fused ones first, then the rest in
      specificity order.

    Args:
        cands: De-duplicated candidates with graph signals.
        lists: Every keyword and semantic result list.
        novel_from_year: First publication year that counts as novel.
        coupling_lists: Weight of the coupling order in the fusion; 0 leaves it out.

    Returns:
        The relevant, seminal and novel strata, each in its own order.
    """
    coupling_order = [
        c.record for c in sorted(cands, key=lambda c: -c.wcoupling) if c.wcoupling > 0
    ]
    fusion = query_fusion([*lists, *([coupling_order] * coupling_lists)])
    baseline = rank_papers(cands)

    def score(candidate: PaperCandidate) -> float:
        return fusion.get(candidate.openalex_id or "", 0.0)

    def year(candidate: PaperCandidate) -> int:
        return int(candidate.record.get("publication_year") or 0)

    relevant = sorted((c for c in baseline if score(c) > 0), key=lambda c: -score(c))
    seminal = sorted(baseline, key=lambda c: (-c.inset, -c.cited_by_count))
    novel = [c for c in relevant if year(c) >= novel_from_year] + [
        c for c in baseline if year(c) >= novel_from_year and score(c) == 0
    ]
    return relevant, seminal, novel


def rank_mix(
    cands: list[PaperCandidate],
    lists: list[list[dict[str, Any]]],
    *,
    novel_from_year: int,
    coupling_lists: int = COUPLING_LISTS,
) -> list[PaperCandidate]:
    """Order the pool so every cut holds relevant, seminal and novel papers.

    The three strata of :func:`mix_strata` are read round-robin, one paper from each
    in turn, skipping a paper already placed.  Papers left when the strata run dry
    follow in specificity order.

    Args:
        cands: De-duplicated candidates with graph signals.
        lists: Every keyword and semantic result list, for the fusion score.
        novel_from_year: First publication year that counts as novel.
        coupling_lists: Weight of the "cites the seeds" order in the fusion.

    Returns:
        The full pool in its final order.
    """
    strata = mix_strata(
        cands, lists, novel_from_year=novel_from_year, coupling_lists=coupling_lists
    )
    out: list[PaperCandidate] = []
    seen: set[int] = set()
    cursors = [iter(stratum) for stratum in strata]
    while cursors:
        for cursor in list(cursors):
            for candidate in cursor:
                if id(candidate) not in seen:
                    seen.add(id(candidate))
                    out.append(candidate)
                    break
            else:
                cursors.remove(cursor)
    return out + [c for c in rank_papers(cands) if id(c) not in seen]


def country_predicate(record: dict[str, Any], countries: set[str]) -> bool:
    """Keep a paper only when its authorship affiliations match a requested country.

    Missing affiliations fail closed: citation-found papers with unknown provenance do
    not silently evade a country directive.

    Args:
        record: An OpenAlex work record.
        countries: Accepted two-letter country codes.

    Returns:
        Whether any authorship reports an accepted country, case-insensitively.
    """
    accepted = {country.upper() for country in countries}
    return any(
        country.upper() in accepted
        for authorship in record.get("authorships") or []
        for country in authorship.get("countries") or []
    )


def normalised_title(text: str | None) -> str:
    """Make titles comparable despite case, punctuation, and whitespace changes.

    Args:
        text: A title supplied by Overton, possibly absent.

    Returns:
        A lower-case, space-separated comparison title.
    """
    return re.sub(r"[^0-9a-z]+", " ", (text or "").lower()).strip()


def policy_key(record: dict[str, Any]) -> str:
    """Choose the title identity for a policy record, preserving titleless records.

    Args:
        record: A raw Overton policy document.

    Returns:
        Its normalised translated-or-native title, or its provider id when titleless.
    """
    title = normalised_title(record.get("translated_title") or record.get("title"))
    return title or record["policy_document_id"]


def dedupe_policy(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first policy record for each title identity in ranked input order.

    Args:
        records: Interleaved policy search records.

    Returns:
        Records with equivalent titles removed after their best-ranked copy.
    """
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        key = policy_key(record)
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


def count_policy_cites(results: list[dict[str, Any]]) -> Counter[str]:
    """Count how often returned policy documents cite each policy document.

    Args:
        results: De-duplicated policy search results.

    Returns:
        In-set citation counts in first-appearance tie order.
    """
    counts: Counter[str] = Counter()
    for record in results:
        cites = (record.get("cites") or {}).get("policy") or []
        for cited in dict.fromkeys(item.get("overton_id") for item in cites):
            if cited:
                counts[cited] += 1
    return counts


def landmark_targets(counts: Counter[str], result_ids: set[str], n: int) -> list[str]:
    """Choose frequently cited policy documents not already returned by search.

    Args:
        counts: In-set policy citation counts.
        result_ids: Provider ids already in the result pool.
        n: Maximum number of landmarks to fetch.

    Returns:
        Landmark ids in stable count order.
    """
    return [policy_id for policy_id, _ in counts.most_common() if policy_id not in result_ids][:n]


@dataclass(frozen=True)
class PolicyCandidate:
    """One policy document and the signals used to rank the policy pool."""

    record: dict[str, Any]
    origin: str
    position: int
    inset: int
    citation_count: int
    specificity: float

    @property
    def policy_document_id(self) -> str:
        """Return Overton's provider id for the candidate."""
        return cast(str, self.record["policy_document_id"])


def rank_policy(
    results: list[tuple[dict[str, Any], str]], landmarks: list[dict[str, Any]], counts: Counter[str]
) -> list[PolicyCandidate]:
    """Score and rank searched policy documents with their citation landmarks.

    The rounded specificity score reproduces the experiment, letting close scores tie
    before in-set citations and original position decide their final order.

    Args:
        results: Search results with their query origin, in final result order.
        landmarks: Citation-found documents in landmark-target order.
        counts: In-set policy citation counts.

    Returns:
        Results and landmarks ordered by policy-topic specificity.
    """
    candidates: list[PolicyCandidate] = []
    for position, (record, origin) in enumerate(results, start=1):
        policy_id = record["policy_document_id"]
        inset = counts.get(policy_id, 0)
        citation_count = int(record.get("citation_count") or 0)
        candidates.append(
            PolicyCandidate(
                record,
                origin,
                position,
                inset,
                citation_count,
                round(inset / log10(citation_count + 10), 3),
            )
        )
    for record in landmarks:
        policy_id = record["policy_document_id"]
        inset = counts.get(policy_id, 0)
        citation_count = int(record.get("citation_count") or 0)
        candidates.append(
            PolicyCandidate(
                record,
                "landmark",
                SEED_RANK_SENTINEL,
                inset,
                citation_count,
                round(inset / log10(citation_count + 10), 3),
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (-candidate.specificity, -candidate.inset, candidate.position),
    )
