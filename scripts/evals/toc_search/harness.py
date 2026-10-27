"""Offline evaluation of per-link evidence search for the theory of change (task 054).

What this does, in plain terms: for one link of a saved theory of change (one step,
"X leads to Y"), it finds documents three different ways (the **arms**), asks the
repo's judge whether each document supports or challenges the step, grades the step
with the repo's grade rule, and checks how many of a hand-picked list of decisive
studies (the **gold** list) each arm reached. Design and plan:
``docs/tasks/054-toc-integration/agentic-search.md``.

The three arms:

- **A, as run.** Reads the judgements the real check walk saved in the local database
  and regrades them. Makes no new calls.
- **B, cheap fixes.** Rebuilds the link's search exactly as it ran (the same queries,
  the repo's search code), keeps 40 records instead of 20, screens each against the
  link's own question instead of the whole theory, then classifies, reranks to 8,
  judges and grades with the repo's own steps.
- **C, agentic.** A planner call (``plan_prompt.py``) decides which kinds of study
  would test the step and writes small searches for OpenAlex (papers), Overton (policy
  documents), the web (OpenAI's hosted web search) and System (a graph of findings
  from health papers). The results go through the same screen, classify, rerank and
  judge. From the first good hit it follows citations, and runs a second round only
  for a question that is still thin. At most two rounds.

Every model and search call is cached on disk (``out/cache.pkl``), so a rerun costs
nothing and money is only counted the first time. A hard spending cap (``--budget``,
in US dollars, new calls only) stops the run before it is exceeded. Outputs go to
``out/`` (ignored by git; they hold document text).

Run from the repo root:

    uv run --project backend --env-file backend/.env python \\
        scripts/evals/toc_search/harness.py --link 2018a1e8-af22-4dc5-8056-6d73a01d6f62 \\
        --gold scripts/evals/toc_search/gold.json --arms A B C

Never calls the Consensus API.
"""

from __future__ import annotations

import _route  # noqa: F401  (must load before policy_atlas: pins the OpenAI route)

import argparse
import hashlib
import json
import os
import pickle
import re
import sys
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy import text as sql

from plan_prompt import (
    DESIGN_TERMS,
    ROUND_TWO_BLOCK,
    SEARCH_PLAN_SYSTEM_PROMPT,
    SEARCH_PLAN_USER_TEMPLATE,
    PlannedSearch,
    SearchPlan,
)
from policy_atlas.core.db import get_engine
from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import (
    openai_kwargs,
    parse_structured,
    resolve_openai_client,
)
from policy_atlas.core.usage import TokenUsage, UsageAccumulator
from policy_atlas.evidence_search.assess.appraise import DEFAULT_RUBRIC
from policy_atlas.evidence_search.assess.classification_backend import (
    OpenAIClassificationBackend,
)
from policy_atlas.evidence_search.assess.classify_prompt import (
    ClassifyEnvelopePayload,
    provider_priors,
)
from policy_atlas.evidence_search.assess.screen import decide_stage1
from policy_atlas.evidence_search.assess.screen_prompt import ScreenEnvelopePayload
from policy_atlas.evidence_search.assess.screening_backend import OpenAIScreeningBackend
from policy_atlas.evidence_search.corpus.ranking import OpenAIRankingBackend
from policy_atlas.evidence_search.sourcing import acquire
from policy_atlas.evidence_search.sourcing import search_loop as sl
from policy_atlas.evidence_search.sourcing.fetch_live import LiveDocumentFetcher
from policy_atlas.evidence_search.sourcing.search_live import (
    OpenAlexLiveBackend,
    OvertonLiveBackend,
)
from policy_atlas.theory_of_change import check, store
from policy_atlas.theory_of_change.draft import walk_toc_plan
from policy_atlas.theory_of_change.evidence.grade import (
    ROBUST_MODEL_SCORE,
    STRONG_SCORE,
    DocAppraisal,
    GradeResult,
    Judgement,
    counted_score,
    grade,
)
from policy_atlas.theory_of_change.graph import item_hash, item_text

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DEFAULT_TASK = "07e278fe-6c68-42bc-b8dc-d5ee7b4d7b37"

# --- money ----------------------------------------------------------------------

#: US dollars per million tokens: (input, cached input, output). Luna: list price checked
#: 2026-10-08 (docs/knowledge/eval-cost-figures-name-their-unit.md). Terra: a third-party
#: price page (anotherwrapper.com, 2026-08-25); its cached price is assumed at 10%.
PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.6-terra": (2.00, 0.20, 12.00),
}
#: OpenAI's hosted web search tool fee per call (assumed $10 per 1,000 calls).
WEB_SEARCH_USD_PER_CALL = 0.01
#: OpenAlex with a key: $0.0001 per request (meta.cost_usd). Overton and System: no per-call price.
OPENALEX_USD_PER_CALL = 0.0001

# --- knobs ----------------------------------------------------------------------

B_CAP = 40
FIRST_N = 20
PER_QUERY = 10
WEB_URLS_PER_CALL = 5
WEB_TEXT_CHARS = 4000
SYSTEM_STUDIES_MAX = 20
CHASE_KEEP = 20
CHASE_FETCH = 100
MAX_ROUNDS = 2
WORKERS = 8

#: Web pages whose appraisal counts like a paper's (owner ruling 2026-10-27). A host
#: matches a domain when it equals it or ends with "." + domain. Edit freely.
TRUSTED_WEB_DOMAINS: tuple[str, ...] = (
    "gov.uk",  # every subdomain: ons.gov.uk, the Evaluation Task Force registry, ...
    "nao.org.uk",
    "nhs.uk",  # includes england.nhs.uk
    "ofcom.org.uk",
    "asa.org.uk",
    "whatworksnetwork.org.uk",
    "eif.org.uk",
    "educationendowmentfoundation.org.uk",
    "youthendowmentfund.org.uk",
    "whatworkswellbeing.org",
    "wwcsc.org.uk",
    "cfe.org.uk",
    "whatworksgrowth.org",
    "college.police.uk",
    "ageing-better.org.uk",
    "taso.org.uk",
    "homelessnessimpact.org",
    "youthfuturesfoundation.org",
    "nice.org.uk",
    "who.int",
    "oecd.org",
    "ac.uk",
    "doi.org",
)

DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s?#&]+)", re.I)


class BudgetExceeded(RuntimeError):
    """The new-call spend reached the cap."""


# --- cost meter and cache -------------------------------------------------------


@dataclass
class Cost:
    """What one call cost: calls, tokens and money."""

    step: str
    calls: int = 1
    prompt: int = 0
    completion: int = 0
    cached: int = 0
    usd: float = 0.0


def llm_cost(
    step: str, model: str, usage: TokenUsage | None, *, extra_usd: float = 0.0
) -> Cost:
    """Price one model call from its tokens (unknown model: tokens only, $0)."""
    p = (usage.prompt or 0) if usage else 0
    c = (usage.completion or 0) if usage else 0
    k = (usage.cached or 0) if usage else 0
    price = PRICES.get(
        model.rsplit(".", 1)[-1] if model.startswith("global.") else model
    )
    usd = extra_usd
    if price:
        usd += ((p - k) * price[0] + k * price[1] + c * price[2]) / 1e6
    return Cost(step, 1, p, c, k, usd)


class Meter:
    """Per-arm totals; thread-safe."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls: Counter[str] = Counter()
        self.tokens: dict[str, list[int]] = {}
        self.usd = 0.0
        self.started = time.monotonic()

    def add(self, cost: Cost) -> None:
        with self.lock:
            self.calls[cost.step] += cost.calls
            t = self.tokens.setdefault(cost.step, [0, 0, 0])
            t[0] += cost.prompt
            t[1] += cost.completion
            t[2] += cost.cached
            self.usd += cost.usd

    def payload(self) -> dict[str, Any]:
        return {
            "calls": dict(self.calls),
            "tokens": {
                k: {"prompt": v[0], "completion": v[1], "cached": v[2]}
                for k, v in self.tokens.items()
            },
            "usd": round(self.usd, 4),
            "wall_s": round(time.monotonic() - self.started, 1),
        }


class Cache:
    """One pickle file of call results; money counts only for new (uncached) calls.

    The budget caps the total new spend over every run that used this cache file.
    """

    def __init__(self, path: Path, budget: float) -> None:
        self.path = path
        self.budget = budget
        self.lock = threading.Lock()
        self.data: dict[str, Any] = (
            pickle.loads(path.read_bytes()) if path.exists() else {}
        )
        self.spent = 0.0  # this run
        self.total = float(
            self.data.get("__total_spent__", 0.0)
        )  # every run on this cache

    def call(
        self, meter: Meter, key: Any, fn: Callable[[], tuple[Any, list[Cost]]]
    ) -> Any:
        """Return ``fn()``'s value, cached by ``key``; costs go to the meter either way."""
        digest = hashlib.sha256(
            json.dumps(key, sort_keys=True, default=str).encode()
        ).hexdigest()
        with self.lock:
            hit = self.data.get(digest)
        if hit is None:
            if self.total >= self.budget:
                raise BudgetExceeded(
                    f"spent ${self.total:.3f} of ${self.budget:.2f} (all runs)"
                )
            hit = fn()
            with self.lock:
                self.data[digest] = hit
                usd = sum(c.usd for c in hit[1])
                self.spent += usd
                self.total += usd
                self.data["__total_spent__"] = self.total
        for cost in hit[1]:
            meter.add(cost)
        return hit[0]

    def save(self) -> None:
        with self.lock:
            self.path.write_bytes(pickle.dumps(self.data))


# --- documents ------------------------------------------------------------------


def norm_doi(value: Any) -> str | None:
    """Lowercase bare DOI, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    m = DOI_RE.search(value)
    return m.group(1).lower().rstrip(".") if m else None


def norm_title(value: str | None) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (value or "").lower()).split())


def short_oa(value: Any) -> str | None:
    return value.rsplit("/", 1)[-1] if isinstance(value, str) and value else None


def host_of(url: str | None) -> str:
    return (urlsplit(url).hostname or "").lower() if url else ""


def trusted(host: str) -> bool:
    """Whether a web page's host is on the trusted publisher list."""
    return any(host == d or host.endswith("." + d) for d in TRUSTED_WEB_DOMAINS)


@dataclass
class Doc:
    """One document as the harness passes it between steps."""

    key: str
    title: str
    abstract: str
    year: int | None
    source: str
    doi: str | None = None
    url: str | None = None
    openalex_id: str | None = None
    referenced: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    labels: list[dict[str, str]] = field(default_factory=list)
    web_rule: str = (
        "paper"  # paper | trusted | capped (web pages only use the last two)
    )
    evidence_type: str | None = None
    score: int | None = None

    @property
    def text(self) -> str:
        return "\n".join(p for p in (self.title.strip(), self.abstract.strip()) if p)

    @property
    def ids(self) -> set[str]:
        return {
            i
            for i in (
                self.doi and "doi:" + self.doi,
                self.openalex_id and "oa:" + self.openalex_id,
                self.url and "url:" + self.url,
            )
            if i
        }

    def appraisal(self) -> DocAppraisal:
        return DocAppraisal(
            score=self.score,
            web=self.web_rule == "capped",
            modelling=self.evidence_type == check.MODELLING_TYPE,
        )


def from_openalex(record: dict[str, Any], source: str) -> Doc | None:
    """A Doc from a raw OpenAlex work, through acquire's own mapping."""
    mapped = acquire._map_openalex_work(record)
    if mapped is None:
        return None
    env = mapped["envelope"]
    oa = short_oa(record.get("id"))
    return Doc(
        key="oa:" + str(oa),
        title=env["title"],
        abstract=env.get("abstract") or "",
        year=env.get("year"),
        source=source,
        doi=norm_doi(env.get("doi")),
        url=None,
        openalex_id=oa,
        referenced=[short_oa(r) or "" for r in record.get("referenced_works") or []],
        metadata={
            **{k: v for k, v in env.items() if v is not None},
            "abstract_source": mapped["abstract_source"],
            "provider_fields": mapped["provider_fields"],
        },
        labels=[
            {"tag": t, "asserted_by": a, "tag_type": tt}
            for t, a, tt in acquire._provider_tags("openalex", record)
        ],
    )


def from_overton(record: dict[str, Any], source: str) -> Doc | None:
    """A Doc from a raw Overton policy document, through acquire's own mapping."""
    mapped = acquire._map_overton_document(record)
    if mapped is None:
        return None
    env = mapped["envelope"]
    return Doc(
        key="overton:" + str(env.get("backend_record_id")),
        title=env["title"],
        abstract=env.get("abstract") or "",
        year=env.get("year"),
        source=source,
        doi=norm_doi(env.get("doi")),
        url=mapped["source_locator"],
        metadata={
            **{k: v for k, v in env.items() if v is not None},
            "abstract_source": mapped["abstract_source"],
            "title_source": mapped["title_source"],
            "provider_fields": mapped["provider_fields"],
        },
        labels=[
            {"tag": t, "asserted_by": a, "tag_type": tt}
            for t, a, tt in acquire._provider_tags("overton", record)
        ],
    )


class Pool:
    """Documents seen so far, de-duplicated by DOI, OpenAlex id or URL (and, when
    ``by_title``, by a long normalised title: OpenAlex lists some works twice)."""

    def __init__(self, by_title: bool = False) -> None:
        self.docs: list[Doc] = []
        self.seen: set[str] = set()
        self.by_title = by_title

    def add(self, docs: Iterable[Doc | None]) -> list[Doc]:
        new = []
        for doc in docs:
            if doc is None:
                continue
            title = norm_title(doc.title)
            ids = doc.ids | (
                {"title:" + title} if self.by_title and len(title) > 30 else set()
            )
            if ids & self.seen:
                continue
            self.seen |= ids
            self.docs.append(doc)
            new.append(doc)
        return new


# --- gold -----------------------------------------------------------------------


def gold_match(entry: dict[str, Any], doc: Doc) -> bool:
    """Whether a document is this gold entry (DOI, URL, or title)."""
    if entry.get("doi") and norm_doi(entry["doi"]) == doc.doi:
        return True
    if entry.get("url") and doc.url and entry["url"].rstrip("/") == doc.url.rstrip("/"):
        return True
    if entry.get("title"):
        a, b = norm_title(entry["title"]), norm_title(doc.title)
        if not (a and b):
            return False
        return (
            a == b
            or (min(len(a), len(b)) > 30 and (a in b or b in a))
            or SequenceMatcher(None, a, b).ratio() >= 0.85
        )
    return False


def gold_found(gold: list[dict[str, Any]], docs: Iterable[Doc]) -> list[int]:
    """Indices of the gold entries found among the documents."""
    docs = list(docs)
    return [i for i, g in enumerate(gold) if any(gold_match(g, d) for d in docs)]


def gold_label(entry: dict[str, Any]) -> str:
    return entry.get("doi") or entry.get("url") or entry.get("title") or "?"


# --- adequacy (pure; unit-tested) -------------------------------------------------


def is_decisive(
    judgement: Judgement, appraisal: DocAppraisal | None, question: str
) -> bool:
    """A judged document settles a question: it supports or challenges the step and
    counts at score 4 or 5, or is a modelling study the judge marked robust."""
    stance = (
        judgement.stance_elsewhere if question == "elsewhere" else judgement.stance_here
    )
    if stance not in ("supports", "challenges"):
        return False
    score = counted_score(judgement, appraisal)
    robust = (
        score == ROBUST_MODEL_SCORE
        and appraisal is not None
        and appraisal.modelling
        and bool(judgement.robust_model)
    )
    return score >= STRONG_SCORE or robust


def stop_reason(
    decisive: bool, round_no: int, new_screened: int, max_rounds: int = MAX_ROUNDS
) -> str | None:
    """Why a question stops after a round, or None to search again."""
    if decisive:
        return "decisive"
    if new_screened == 0:
        return "saturated"
    if round_no >= max_rounds:
        return "budget"
    return None


# --- System (findings graph) client ----------------------------------------------


def split_cause_effect(query: str) -> tuple[str, str] | None:
    """'CAUSE -> EFFECT' into its two terms, or None."""
    parts = re.split(r"\s*(?:->|→)\s*", query.strip(), maxsplit=1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0].strip().strip('"'), parts[1].strip().strip('"')


def best_concept(term: str, concepts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The concept whose label best matches the term: exact label, exact alias, then the
    closest label containing (or contained in) the term, else None."""
    t = term.lower().strip()
    for c in concepts:
        if (c.get("wikidata_label") or "").lower() == t:
            return c
    for c in concepts:
        if t in [a.lower() for a in c.get("wikidata_aliases") or []]:
            return c
    near = [
        c
        for c in concepts
        if (lab := (c.get("wikidata_label") or "").lower()) and (t in lab or lab in t)
    ]
    return (
        min(near, key=lambda c: abs(len(c["wikidata_label"]) - len(t)))
        if near
        else None
    )


def study_dois(payload: dict[str, Any]) -> list[str]:
    """Bare DOIs of a studies list, in order, without duplicates."""
    out: list[str] = []
    for s in payload.get("data") or []:
        d = norm_doi(s.get("doi"))
        if d and d not in out:
            out.append(d)
    return out


class SystemClient:
    """Minimal client for the System public API (https://public-api.system.com/v1).

    System warns that about 20% of its extracted associations are inaccurate; the
    harness only uses it to find studies, which then go through the normal pipeline.
    """

    base = "https://public-api.system.com/v1"

    def __init__(self, api_key: str) -> None:
        self.http = httpx.Client(headers={"x-api-key": api_key}, timeout=30)
        self.calls = 0

    def get(self, path: str, **params: Any) -> dict[str, Any] | None:
        self.calls += 1
        r = self.http.get(self.base + path, params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def concept(self, term: str) -> dict[str, Any] | None:
        data = self.get("/concepts", search=f"wikidata_label:{term}", limit=20) or {}
        return best_concept(term, data.get("data") or [])

    def studies(self, query: str) -> tuple[list[str], dict[str, Any]]:
        """DOIs of the studies behind 'CAUSE -> EFFECT', with a log of what matched."""
        terms = split_cause_effect(query)
        if terms is None:
            return [], {"error": "query is not 'CAUSE -> EFFECT'"}
        src, tgt = self.concept(terms[0]), self.concept(terms[1])
        log: dict[str, Any] = {
            "cause": src and src.get("wikidata_label"),
            "effect": tgt and tgt.get("wikidata_label"),
        }
        if src is None:
            return [], {**log, "error": "no cause concept"}
        rel_id = None
        if tgt is not None and self.get(
            f"/relationships/{src['system_id']}%7C{tgt['system_id']}"
        ):
            rel_id = f"{src['system_id']}%7C{tgt['system_id']}"
        if (
            rel_id is None
        ):  # list the cause's relationships and pick the effect by label
            listed = (
                self.get(
                    "/relationships",
                    filter=f"source_concept.system_id:{src['system_id']}",
                    search=f"target_concept.wikidata_label:{terms[1]}",
                    limit=20,
                )
                or {}
            )
            targets = [r.get("target_concept") or {} for r in listed.get("data") or []]
            pick = best_concept(terms[1], targets)
            if pick is None:
                return [], {**log, "error": "no relationship"}
            log["effect"] = pick.get("wikidata_label")
            rel_id = f"{src['system_id']}%7C{pick['system_id']}"
        data = (
            self.get(f"/relationships/{rel_id}/studies", limit=SYSTEM_STUDIES_MAX) or {}
        )
        dois = study_dois(data)
        return dois, {
            **log,
            "relationship": rel_id.replace("%7C", "|"),
            "studies": len(dois),
        }


# --- web search client ------------------------------------------------------------


def clean_url(url: str) -> str:
    """Drop utm_* tracking parameters and the fragment."""
    parts = urlsplit(url)
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def page_text(body: bytes, content_type: str) -> str:
    """Readable text of a fetched page: trafilatura for HTML, PyMuPDF for PDF."""
    if content_type == "application/pdf":
        import pymupdf

        with pymupdf.open(stream=body, filetype="pdf") as pdf:
            return "\n".join(pdf[i].get_text() for i in range(min(5, pdf.page_count)))
    if content_type == "text/html":
        import trafilatura

        return (
            trafilatura.extract(body, include_comments=False, include_tables=True) or ""
        )
    return body.decode("utf-8", errors="replace")


# --- the harness ------------------------------------------------------------------


@dataclass
class Link:
    """What every arm needs to know about one link."""

    task_id: uuid.UUID
    link_id: str
    item_text: str
    population: str
    place: str
    neighbours: str
    walk_id: uuid.UUID
    walk_scope: uuid.UUID
    search_run: uuid.UUID | None
    hash_matches: bool


class Harness:
    """Shared clients, the cache, and the repo's pipeline steps."""

    def __init__(self, budget: float) -> None:
        OUT.mkdir(exist_ok=True)
        (OUT / ".gitignore").write_text("*\n")
        self.cache = Cache(OUT / "cache.pkl", budget)
        self.openalex = OpenAlexLiveBackend(
            os.environ["OPENALEX_API_KEY"], email=os.environ.get("OPENALEX_EMAIL")
        )
        self.overton = OvertonLiveBackend(os.environ["OVERTON_API_KEY"])
        self.system = SystemClient(os.environ["SYSTEM_API_KEY"])
        self.screener = OpenAIScreeningBackend()
        self.classifier = OpenAIClassificationBackend()
        self.ranker = OpenAIRankingBackend()
        self.toc = check_backend()
        self.client = resolve_openai_client(
            None, backend_name="toc_search_eval", timeout=300.0, max_retries=2
        )
        self.fetcher = LiveDocumentFetcher()
        self.r = route()
        self.standard = self.r.tiers["standard"]
        self.stored = self._stored_labels()

    # -- database reads --

    def _stored_labels(self) -> dict[str, str]:
        """Evidence types classify already gave documents in the task, by DOI and OpenAlex id."""
        q = sql(
            """select ss.metadata->>'doi' as doi, ss.metadata->>'backend_record_id' as rid,
                      scr.primary_evidence_type as etype
               from source_classification_result scr
               join task_source_snapshot tss on tss.task_source_snapshot_id = scr.task_source_snapshot_id
               join source_snapshot ss on ss.source_snapshot_id = tss.source_snapshot_id
               where scr.task_id = :t"""
        )
        out: dict[str, str] = {}
        with get_engine().connect() as conn:
            for row in conn.execute(q, {"t": DEFAULT_TASK}):
                for k in (
                    norm_doi(row.doi) and "doi:" + norm_doi(row.doi),
                    short_oa(row.rid) and "oa:" + short_oa(row.rid),
                ):
                    if k:
                        out[k] = row.etype
        return out

    def load_link(self, task_id: uuid.UUID, link_id: str) -> Link:
        with get_engine().connect() as conn:
            graph, _ = store.load_graph(conn, task_id)
            link = graph.links[link_id]
            counted = conn.execute(
                sql("select counted_hash from toc_link where link_id = :l"),
                {"l": link_id},
            ).scalar_one()
            walk_id = conn.execute(
                sql(
                    """select capability_run_id from toc_item_evidence
                       where link_id = :l and item_hash = :h limit 1"""
                ),
                {"l": link_id, "h": counted},
            ).scalar_one()
            walk_scope, run_id = conn.execute(
                sql(
                    """select c.evidence_scope_id, r.run_id from capability_run c
                       join runs r on r.capability_run_id = c.capability_run_id
                       where c.capability_run_id = :w limit 1"""
                ),
                {"w": walk_id},
            ).one()
            plan = walk_toc_plan(
                conn, task_id=task_id, run_id=run_id, scope_id=walk_scope
            )
            search_run = conn.execute(
                sql(
                    """select r.run_id from capability_run c
                       join evidence_scope e on e.evidence_scope_id = c.evidence_scope_id
                       join runs r on r.capability_run_id = c.capability_run_id
                       where c.parent_capability_run_id = :w and e.context->>'link_id' = :l limit 1"""
                ),
                {"w": walk_id, "l": link_id},
            ).scalar_one_or_none()
        src, tgt = graph.boxes[link.source].text, graph.boxes[link.target].text
        return Link(
            task_id=task_id,
            link_id=link_id,
            item_text=item_text(
                link,
                source_text=src,
                target_text=tgt,
                population=plan.target_population,
                place=plan.where,
            ),
            population=plan.target_population,
            place=plan.where or "not stated",
            neighbours=check.neighbour_lines(graph, link_id),
            walk_id=walk_id,
            walk_scope=walk_scope,
            search_run=search_run,
            hash_matches=item_hash(link, src, tgt) == counted,
        )

    # -- pipeline steps (each one call per document, cached) --

    def screen(self, meter: Meter, doc: Doc, intent: str) -> bool:
        """Stage-1 screen as production: a second rep only after a not-relevant first."""
        payload = ScreenEnvelopePayload(
            tss_id=doc.key,
            title=doc.title,
            abstract=doc.abstract or None,
            abstract_source=doc.metadata.get("abstract_source"),
            title_source=doc.metadata.get("title_source"),
            intent=intent,
        )

        def rep(i: int) -> Any:
            def run() -> tuple[Any, list[Cost]]:
                for attempt in range(2):  # SCREEN_RETRY_CAP = 1
                    try:
                        wire, usage = self.screener.screen_envelope(
                            payload, rep_index=i
                        )
                        return wire, [
                            llm_cost("screen", self.r.model_for("screen"), usage)
                        ]
                    except Exception:  # noqa: BLE001 - a failed rep counts as failed
                        if attempt:
                            return None, [Cost("screen")]
                return None, []

            return self.cache.call(meter, ("screen", i, doc.key, doc.text, intent), run)

        first = rep(0)
        second = (
            rep(1) if first is not None and first.decision == "not_relevant" else None
        )
        return decide_stage1(first, second).status == "relevant"

    def classify(self, meter: Meter, doc: Doc) -> None:
        """Evidence type (stored label when the task already has one) and appraisal score."""
        if doc.evidence_type is None:
            doc.evidence_type = next(
                (self.stored[i] for i in doc.ids if i in self.stored), None
            )
            if doc.evidence_type is not None:
                meter.add(Cost("classify_reused", calls=1))
        if doc.evidence_type is None:
            payload = ClassifyEnvelopePayload(
                tss_id=doc.key,
                title=doc.title,
                abstract=doc.abstract or None,
                priors=provider_priors(doc.metadata, doc.labels),
                metadata=doc.metadata,
            )

            def run() -> tuple[Any, list[Cost]]:
                wire, usage = self.classifier.classify(payload)
                return wire.primary_evidence_type, [
                    llm_cost("classify", self.r.model_for("classify"), usage)
                ]

            doc.evidence_type = self.cache.call(
                meter, ("classify", doc.key, doc.text), run
            )
        doc.score = DEFAULT_RUBRIC.get(doc.evidence_type or "")

    def rerank(self, meter: Meter, docs: list[Doc], intent: str) -> list[Doc]:
        """The repo's rerank (``check.rerank``) against the link's text."""
        if len(docs) <= check.JUDGE_TOP_K:
            return docs
        by_id = {uuid.uuid5(uuid.NAMESPACE_URL, d.key): d for d in docs}
        cands = [
            check.Document(
                tss_id=k,
                title=d.title,
                year=d.year,
                abstract=d.abstract,
                evidence_type=d.evidence_type,
                score=d.score,
            )
            for k, d in by_id.items()
        ]

        def run() -> tuple[Any, list[Cost]]:
            acc = UsageAccumulator()
            order = [
                str(d.tss_id)
                for d in check.rerank(self.ranker, cands, intent=intent, usage=acc)
            ]
            usage = TokenUsage(acc.prompt, acc.completion, acc.total, acc.cached)
            cost = llm_cost("rerank", self.r.model_for("rerank"), usage)
            cost.calls = -(-len(cands) // 25)
            return order, [cost]

        order = self.cache.call(
            meter, ("rerank", intent, sorted(d.key for d in docs)), run
        )
        return [by_id[uuid.UUID(k)] for k in order]

    def judge(self, meter: Meter, link: Link, doc: Doc) -> dict[str, Any]:
        """One judge call (toc_judge_v3); a stance whose quote is not in the text is dropped."""
        modelling = doc.evidence_type == check.MODELLING_TYPE

        def run() -> tuple[Any, list[Cost]]:
            resp, usage = self.toc.judge(
                item_text=link.item_text,
                population=link.population,
                place=link.place,
                document_id=doc.key,
                title=doc.title,
                year=doc.year,
                text=doc.text,
                modelling=modelling,
                neighbours=link.neighbours,
            )
            out: dict[str, Any] = {
                "robust_model": resp.robust_model if modelling else None,
                "unverified": 0,
            }
            for name, wire in (
                ("elsewhere", resp.worked_elsewhere),
                ("here", resp.holds_here),
            ):
                if wire.stance != "not_about" and not check.quote_found(
                    doc.text, wire.quote
                ):
                    out["unverified"] += 1
                    out[name], out[name + "_quote"] = "not_about", None
                else:
                    out[name], out[name + "_quote"] = (
                        wire.stance,
                        wire.quote if wire.stance != "not_about" else None,
                    )
            return out, [llm_cost("judge", self.r.model_for("toc_judge"), usage)]

        return self.cache.call(
            meter,
            (
                "judge",
                link.item_text,
                link.neighbours,
                doc.key,
                doc.text,
                doc.year,
                modelling,
            ),
            run,
        )

    def parallel(self, fn: Callable[[Any], Any], items: list[Any]) -> list[Any]:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            return list(ex.map(fn, items))

    def assess(self, meter: Meter, link: Link, docs: list[Doc]) -> list[Doc]:
        """Screen against the link's question; classify and appraise the screened-in."""
        keep = self.parallel(lambda d: self.screen(meter, d, link.item_text), docs)
        screened = [d for d, k in zip(docs, keep, strict=True) if k]
        self.parallel(lambda d: self.classify(meter, d), screened)
        return screened

    def judge_top(
        self,
        meter: Meter,
        link: Link,
        candidates: list[Doc],
        judged: dict[str, tuple[Doc, dict]],
    ) -> list[Doc]:
        top = self.rerank(
            meter, [d for d in candidates if d.key not in judged], link.item_text
        )[: check.JUDGE_TOP_K]
        for doc, verdict in zip(
            top, self.parallel(lambda d: self.judge(meter, link, d), top), strict=True
        ):
            judged[doc.key] = (doc, verdict)
        return top

    # -- searches --

    def openalex_search(
        self, meter: Meter, query: str, n: int = PER_QUERY
    ) -> list[dict[str, Any]]:
        return self.cache.call(
            meter,
            ("openalex", query, n),
            lambda: (
                self.openalex.search(query, max_results=n),
                [Cost("search_openalex", usd=OPENALEX_USD_PER_CALL)],
            ),
        )

    def openalex_dois(self, meter: Meter, dois: list[str]) -> list[dict[str, Any]]:
        if not dois:
            return []
        return self.cache.call(
            meter,
            ("openalex_dois", dois),
            lambda: (
                self.openalex.lookup_dois(dois),
                [
                    Cost(
                        "lookup_openalex",
                        calls=-(-len(dois) // 50),
                        usd=OPENALEX_USD_PER_CALL,
                    )
                ],
            ),
        )

    def overton_search(self, meter: Meter, query: str) -> list[dict[str, Any]]:
        return self.cache.call(
            meter,
            ("overton", query, PER_QUERY),
            lambda: (
                self.overton.search(query, max_results=PER_QUERY),
                [Cost("search_overton")],
            ),
        )

    def system_search(
        self, meter: Meter, query: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        def run() -> tuple[Any, list[Cost]]:
            before = self.system.calls
            dois, log = self.system.studies(query)
            return (dois, log), [Cost("system", calls=self.system.calls - before)]

        dois, log = self.cache.call(meter, ("system", query), run)
        return self.openalex_dois(meter, dois), log

    def web_search(self, meter: Meter, query: str) -> tuple[list[Doc], dict[str, Any]]:
        """Hosted web search, then fetch and extract each cited page (max 5)."""

        def run() -> tuple[Any, list[Cost]]:
            resp = self.client.responses.create(
                model=self.standard,
                tools=[{"type": "web_search"}],
                input=f"Search the web for: {query}\nList the most relevant pages you found, one per line.",
            )
            tool_calls = sum(
                1 for item in resp.output if item.type == "web_search_call"
            )
            urls: list[tuple[str, str]] = []
            for item in resp.output:
                for part in getattr(item, "content", None) or []:
                    for ann in getattr(part, "annotations", None) or []:
                        if ann.type == "url_citation":
                            u = clean_url(ann.url)
                            if u not in [x for x, _ in urls]:
                                urls.append((u, ann.title or ""))
            u = resp.usage
            usage = TokenUsage(
                u.input_tokens,
                u.output_tokens,
                u.total_tokens,
                u.input_tokens_details.cached_tokens,
            )
            costs = [
                llm_cost(
                    "web",
                    self.standard,
                    usage,
                    extra_usd=tool_calls * WEB_SEARCH_USD_PER_CALL,
                ),
                Cost("web_tool_calls", calls=tool_calls),
            ]
            return urls[:WEB_URLS_PER_CALL], costs

        urls = self.cache.call(meter, ("web", self.standard, query), run)
        docs: list[Doc] = []
        log: dict[str, Any] = {
            "urls": [u for u, _ in urls],
            "fetch_failed": 0,
            "doi_to_paper": 0,
        }
        for url, title in urls:
            doc = self.web_doc(meter, url, title)
            if doc is None:
                log["fetch_failed"] += 1
                continue
            log["doi_to_paper"] += doc.source == "web_doi"
            docs.append(doc)
        return docs, log

    def web_doc(self, meter: Meter, url: str, title: str) -> Doc | None:
        """A web page as a document; a page carrying a DOI known to OpenAlex becomes that paper."""
        doi = norm_doi(url)
        if doi:
            recs = self.openalex_dois(meter, [doi])
            if recs and (d := from_openalex(recs[0], "web_doi")):
                return d

        def run() -> tuple[Any, list[Cost]]:
            res = self.fetcher.fetch(url)
            if res.status != "ok" or not res.body:
                return None, [Cost("web_fetch")]
            try:
                body_text = page_text(res.body, res.content_type or "")
            except Exception:  # noqa: BLE001 - an unreadable page is just skipped
                body_text = ""
            finally:
                self.fetcher.release_body(len(res.body))
            return body_text, [Cost("web_fetch")]

        body = self.cache.call(meter, ("fetch", url), run)
        if not body or not body.strip():
            return None
        host = host_of(url)
        return Doc(
            key="url:" + url,
            title=title or host,
            abstract=" ".join(body.split())[:WEB_TEXT_CHARS],
            year=None,
            source="web",
            url=url,
            metadata={
                "title": title,
                "abstract_source": "web_page",
                "record_type": "web page",
                "publisher_org": host,
            },
            web_rule="trusted" if trusted(host) else "capped",
        )

    def run_planned(
        self, meter: Meter, s: PlannedSearch
    ) -> tuple[list[Doc], dict[str, Any]]:
        """Execute one planned search; errors are recorded, never raised."""
        log: dict[str, Any] = {
            "source": s.source,
            "question": s.question,
            "type": s.evidence_type,
            "query": s.query,
        }
        try:
            if s.source == "openalex":
                terms = DESIGN_TERMS.get(s.evidence_type)
                q = f"({s.query}) AND ({terms})" if terms else s.query
                log["sent"] = q
                docs = [
                    from_openalex(r, "openalex") for r in self.openalex_search(meter, q)
                ]
            elif s.source == "overton":
                docs = [
                    from_overton(r, "overton")
                    for r in self.overton_search(meter, s.query)
                ]
            elif s.source == "system":
                recs, extra = self.system_search(meter, s.query)
                log.update(extra)
                docs = [from_openalex(r, "system") for r in recs]
            else:
                docs, extra = self.web_search(meter, s.query)
                log.update(extra)
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - a failed search is reported
            log["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            docs = []
        found = [d for d in docs if d is not None]
        log["hits"] = len(found)
        return found, log

    def plan(self, meter: Meter, link: Link, summary: str | None) -> SearchPlan:
        user = SEARCH_PLAN_USER_TEMPLATE.format(
            item_text=link.item_text,
            population=link.population,
            place=link.place,
            round_block=ROUND_TWO_BLOCK.format(summary=summary) if summary else "",
        )
        messages = [
            {"role": "system", "content": SEARCH_PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

        def run() -> tuple[Any, list[Cost]]:
            parsed, usage = parse_structured(
                self.client,
                messages=messages,
                response_format=SearchPlan,
                usage_event="toc_search_plan.usage",
                label="toc_search_plan",
                max_completion_tokens=4000,
                **openai_kwargs(
                    self.standard,
                    reasoning_effort=self.r.reasoning_effort_for(self.standard),
                ),
            )
            return parsed, [llm_cost("planner", self.standard, usage)]

        return self.cache.call(meter, ("plan", self.standard, messages), run)

    def chase(self, meter: Meter, link: Link, hit: Doc) -> list[Doc]:
        """References and citing works of a good hit, each list reranked, top 20 each."""
        out: list[Doc] = []
        if not hit.openalex_id:
            return out
        refs = [r for r in hit.referenced if r][:CHASE_FETCH]
        lists = [
            self.cache.call(
                meter,
                ("refs", refs),
                lambda: (
                    self.openalex.lookup_ids(refs) if refs else [],
                    [Cost("chase_openalex", usd=OPENALEX_USD_PER_CALL)],
                ),
            ),
            self.cache.call(
                meter,
                ("citing", hit.openalex_id, CHASE_FETCH),
                lambda: (
                    self.openalex.fetch_citing(
                        [hit.openalex_id], max_results=CHASE_FETCH
                    ),
                    [Cost("chase_openalex", usd=OPENALEX_USD_PER_CALL)],
                ),
            ),
        ]
        for records in lists:
            docs = [d for r in records if (d := from_openalex(r, "chase"))]
            out.extend(self.rerank(meter, docs, link.item_text)[:CHASE_KEEP])
        return out


def check_backend() -> Any:
    from policy_atlas.theory_of_change.backend import OpenAITocBackend

    return OpenAITocBackend()


# --- grading and metrics ------------------------------------------------------------


def grades(judged: dict[str, tuple[Doc, dict]]) -> tuple[GradeResult, GradeResult]:
    js = [
        Judgement(k, v["elsewhere"], v["here"], v.get("robust_model"))
        for k, (_, v) in judged.items()
    ]
    aps = {k: d.appraisal() for k, (d, _) in judged.items()}
    return grade(js, aps, "elsewhere"), grade(js, aps, "here")


def decisive_now(judged: dict[str, tuple[Doc, dict]], question: str) -> list[Doc]:
    return [
        d
        for k, (d, v) in judged.items()
        if is_decisive(
            Judgement(k, v["elsewhere"], v["here"], v.get("robust_model")),
            d.appraisal(),
            question,
        )
    ]


def in_band(grade_name: str, band: str | None) -> bool | None:
    return None if not band else grade_name in band.split("-")


def metrics(
    arm: str,
    link: Link,
    gold: dict[str, Any],
    *,
    first20: list[Doc] | None,
    pool: list[Doc],
    screened: list[Doc],
    judged: dict[str, tuple[Doc, dict]],
    meter: Meter | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entries = gold.get("gold", [])
    expected = gold.get("expected", {})
    ge, gh = grades(judged)
    verdicts = []
    for i, g in enumerate(entries):
        hit = next(((d, v) for d, v in judged.values() if gold_match(g, d)), None)
        verdicts.append(
            {
                "gold": gold_label(g),
                "judged": hit is not None,
                "elsewhere": hit and hit[1]["elsewhere"],
                "here": hit and hit[1]["here"],
                "score": hit and hit[0].score,
            }
        )
    supports45 = {
        q: sum(
            1
            for k, (d, v) in judged.items()
            if v[q] == "supports"
            and counted_score(
                Judgement(k, v["elsewhere"], v["here"], v.get("robust_model")),
                d.appraisal(),
            )
            >= STRONG_SCORE
        )
        for q in ("elsewhere", "here")
    }
    web = [d for d, _ in judged.values() if d.source == "web"]
    return {
        "link": link.link_id,
        "arm": arm,
        "gold_total": len(entries),
        "gold_first20": None if first20 is None else len(gold_found(entries, first20)),
        "gold_pool": len(gold_found(entries, pool)),
        "gold_screened": len(gold_found(entries, screened)),
        "gold_judged": len(gold_found(entries, [d for d, _ in judged.values()])),
        "pool": len(pool),
        "screened": len(screened),
        "judged": len(judged),
        "grade_elsewhere": ge.grade,
        "grade_here": gh.grade,
        "expected": expected,
        "in_band_elsewhere": in_band(ge.grade, expected.get("elsewhere")),
        "in_band_here": in_band(gh.grade, expected.get("here")),
        "supports_4_5": supports45,
        "against": {"elsewhere": ge.against, "here": gh.against},
        "gold_verdicts": verdicts,
        "web_rules_judged": dict(Counter(d.web_rule for d in web)),
        "judged_docs": [
            {
                "title": d.title[:160],
                "source": d.source,
                "type": d.evidence_type,
                "score": d.score,
                "web_rule": d.web_rule,
                "elsewhere": v["elsewhere"],
                "here": v["here"],
                "robust_model": v.get("robust_model"),
            }
            for d, v in judged.values()
        ],
        "cost": meter.payload() if meter else None,
        **(extra or {}),
    }


# --- arms ---------------------------------------------------------------------------


def arm_a(h: Harness, link: Link, gold: dict[str, Any]) -> dict[str, Any]:
    """As run: the persisted judgements and the link's own 20 records, regraded."""
    with get_engine().connect() as conn:
        rows = check.counted_judgements(conn, task_id=link.task_id).get(
            link.link_id, []
        )
        appraisals = check.appraisals_for(
            conn, task_id=link.task_id, evidence_rows=rows
        )
        own = check._own_search_documents(
            conn, task_id=link.task_id, walk_id=link.walk_id
        ).get(link.link_id, set())
        screened_ids = {
            d.tss_id
            for d in check.screened_documents(
                conn, task_id=link.task_id, scope_id=link.walk_scope
            )
        }
        tss = list(own | {r.task_source_snapshot_id for r in rows})
        meta = {
            r.tss: r.metadata
            for r in conn.execute(
                sql(
                    """select tss.task_source_snapshot_id as tss, ss.metadata from task_source_snapshot tss
                       join source_snapshot ss on ss.source_snapshot_id = tss.source_snapshot_id
                       where tss.task_source_snapshot_id = any(:ids)"""
                ),
                {"ids": tss},
            )
        }
    docs: dict[uuid.UUID, Doc] = {}
    for t, m in meta.items():
        docs[t] = Doc(
            key=str(t),
            title=m.get("title") or "",
            abstract=m.get("abstract") or "",
            year=m.get("year"),
            source=m.get("backend") or "?",
            doi=norm_doi(m.get("doi")),
            openalex_id=short_oa(m.get("backend_record_id")),
        )
    judged: dict[str, tuple[Doc, dict]] = {}
    for r in rows:
        d = docs[r.task_source_snapshot_id]
        a = appraisals.get(str(r.task_source_snapshot_id))
        d.score = a.score if a else None
        d.evidence_type = next((h.stored[i] for i in d.ids if i in h.stored), None)
        judged[d.key] = (
            d,
            {
                "elsewhere": r.stance_elsewhere,
                "here": r.stance_here,
                "robust_model": r.robust_model,
            },
        )
    ge, gh = check.link_grades(rows, appraisals)
    out = metrics(
        "A",
        link,
        gold,
        first20=[docs[t] for t in own],
        pool=[docs[t] for t in own],
        screened=[docs[t] for t in own if t in screened_ids],
        judged=judged,
        meter=None,
        extra={
            "repo_grades": [ge.grade, gh.grade],
            "item_hash_matches": link.hash_matches,
        },
    )
    return out


def as_run_queries(link: Link) -> tuple[str, list[str], list[str]]:
    """The intent, generated queries and paraphrases the link's item search ran."""
    with get_engine().connect() as conn:
        events = [
            r.payload
            for r in conn.execute(
                sql(
                    "select payload from event_log where run_id = :r and event_type = 'search.executed' order by sequence"
                ),
                {"r": link.search_run},
            )
        ]
    generated = list(
        dict.fromkeys(
            e["query"]
            for e in events
            if e.get("query_origin") == "generated" and e.get("backend") == "openalex"
        )
    )
    semantic = [
        e["query"]
        for e in events
        if e.get("verb") == "search_semantic" and e.get("backend") == "openalex"
    ]
    intent = semantic[0]
    paras = [q for q in semantic[1:] if q not in generated]
    return intent, generated, paras


def arm_b(h: Harness, link: Link, gold: dict[str, Any]) -> dict[str, Any]:
    """Cheap fixes: the as-run OpenAlex search, cap 40, screen against the link."""
    meter = Meter()
    intent, queries, paras = as_run_queries(link)

    def run() -> tuple[Any, list[Cost]]:
        sl.N_QUERIES = max(sl.N_QUERIES, len(queries))
        validated = sl.validate_scope_filters(None, backend_names=["openalex"])
        variants = sl._filter_variants("openalex", validated["openalex"])
        wires = [sl.to_wire_params("openalex", v) for v in variants]
        p = sl._Pass(sl.DEPTH_CONSTANTS["rapid"], {"openalex": len(variants)})
        entries, _, _ = sl._openalex_leg(
            p,
            h.openalex,
            intent=intent,
            queries=queries,
            paraphrases=paras,
            variants=variants,
            wires=wires,
        )
        ranked = [r for r, *_ in entries[: p.ranked_count["openalex"]]]
        n = len(p.executed)
        return ranked[: B_CAP * 2], [
            Cost("search_openalex", calls=n, usd=n * OPENALEX_USD_PER_CALL)
        ]

    ranked = h.cache.call(
        meter, ("repro_openalex_leg", link.link_id, intent, queries, paras), run
    )
    pool = Pool()
    pool.add(from_openalex(r, "openalex") for r in ranked)
    pool.docs = pool.docs[:B_CAP]
    judged: dict[str, tuple[Doc, dict]] = {}
    screened = h.assess(meter, link, pool.docs)
    h.judge_top(meter, link, screened, judged)
    return metrics(
        "B",
        link,
        gold,
        first20=pool.docs[:FIRST_N],
        pool=pool.docs,
        screened=screened,
        judged=judged,
        meter=meter,
        extra={"queries": queries},
    )


def round_summary(
    judged: dict[str, tuple[Doc, dict]], stops: dict[str, str | None], hit: Doc | None
) -> str:
    lines = [
        "Documents judged in round 1 (title | design | score | worked_elsewhere | holds_here):"
    ]
    for d, v in judged.values():
        lines.append(
            f"- {d.title[:150]} | {d.evidence_type} | {d.score} | {v['elsewhere']} | {v['here']}"
        )
    if hit is not None:
        lines.append(f"Good hit (citations followed): {hit.title[:200]}")
    thin = [q for q, s in stops.items() if s is None]
    names = {"elsewhere": "worked_elsewhere", "here": "holds_here"}
    lines.append(
        "Still thin: "
        + ", ".join(
            f"{names[q]} (no study scored 4-5 or robust model supports or challenges it yet)"
            for q in thin
        )
    )
    return "\n".join(lines)


def arm_c(h: Harness, link: Link, gold: dict[str, Any]) -> dict[str, Any]:
    """Agentic: plan by evidence type, search four sources, chase, at most two rounds."""
    meter = Meter()
    pool = Pool(by_title=True)
    judged: dict[str, tuple[Doc, dict]] = {}
    screened: list[Doc] = []
    stops: dict[str, str | None] = {"elsewhere": None, "here": None}
    stop_round: dict[str, int] = {}
    rounds: list[dict[str, Any]] = []
    chased: list[Doc] = []
    hit: Doc | None = None
    summary: str | None = None
    for round_no in range(1, MAX_ROUNDS + 1):
        plan = h.plan(meter, link, summary)
        searches = plan.searches[: 6 if round_no == 1 else 4]
        results = h.parallel(lambda s: h.run_planned(meter, s), searches)
        logs = []
        new_all: list[Doc] = []
        for docs, log in results:
            new = pool.add(docs)
            log["new"] = len(new)
            log["new_keys"] = [d.key for d in new]
            logs.append(log)
            new_all.extend(new)
        chase_new = pool.add(chased)
        new_all.extend(chase_new)
        new_screened = h.assess(meter, link, new_all)
        screened.extend(new_screened)
        top = h.judge_top(meter, link, screened, judged)
        keys_in = {d.key for d in new_screened}
        judged_keys = {d.key for d in top}
        for log in logs:
            log["screened_in"] = sum(k in keys_in for k in log["new_keys"])
            log["judged"] = sum(k in judged_keys for k in log["new_keys"])
            log["supports"] = sum(
                k in judged_keys
                and "supports" in (judged[k][1]["elsewhere"], judged[k][1]["here"])
                for k in log["new_keys"]
            )
            log["gold"] = [
                gold_label(gold.get("gold", [])[i])
                for i in gold_found(
                    gold.get("gold", []),
                    [d for d in pool.docs if d.key in log["new_keys"]],
                )
            ]
            del log["new_keys"]
        for q in stops:
            if stops[q] is None:
                stops[q] = stop_reason(
                    bool(decisive_now(judged, q)), round_no, len(new_screened)
                )
                if stops[q]:
                    stop_round[q] = round_no
        rounds.append(
            {
                "round": round_no,
                "link_type": plan.link_type,
                "target_elsewhere": plan.target_types_elsewhere,
                "target_here": plan.target_types_here,
                "descriptive_note": plan.descriptive_note,
                "searches": logs,
                "chased_in": len(chase_new),
                "chased_screened_in": sum(d.key in keys_in for d in chase_new),
                "new_screened": len(new_screened),
                "judged_this_round": [d.title[:120] for d in top],
                "stops": dict(stops),
            }
        )
        if all(stops.values()):
            break
        if hit is None:
            good = [
                d
                for d in decisive_now(judged, "elsewhere")
                + decisive_now(judged, "here")
                if d.openalex_id
            ]
            hit = good[0] if good else None
            if hit is not None:
                chased = h.chase(meter, link, hit)
                rounds[-1]["chase_from"] = hit.title[:200]
                rounds[-1]["chase_gold"] = [
                    gold_label(gold.get("gold", [])[i])
                    for i in gold_found(gold.get("gold", []), chased)
                ]
        summary = round_summary(judged, stops, hit)
    return metrics(
        "C",
        link,
        gold,
        first20=None,
        pool=pool.docs,
        screened=screened,
        judged=judged,
        meter=meter,
        extra={"stops": stops, "stop_round": stop_round, "rounds": rounds},
    )


# --- report -------------------------------------------------------------------------


def report(rows: list[dict[str, Any]]) -> str:
    head = (
        "| link | arm | gold first 20 | gold pool | gold screened | gold judged (top 8) | elsewhere | here | "
        "expected | supports 4-5 (e/h) | stop (e/h) | calls | tokens in/out | est. $ | wall s |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    out = []
    for r in rows:
        c = r.get("cost") or {}
        tok = c.get("tokens", {})
        tin = sum(v["prompt"] for v in tok.values())
        tout = sum(v["completion"] for v in tok.values())
        calls = ", ".join(f"{k} {v}" for k, v in sorted(c.get("calls", {}).items()))
        stops = r.get("stops")
        stop = (
            f"{stops['elsewhere']} r{r['stop_round'].get('elsewhere', '-')} / {stops['here']} r{r['stop_round'].get('here', '-')}"
            if stops
            else "-"
        )
        exp = r["expected"]
        out.append(
            f"| {r['link'][:8]} | {r['arm']} | {r['gold_first20'] if r['gold_first20'] is not None else '-'}/{r['gold_total']} | "
            f"{r['gold_pool']}/{r['gold_total']} ({r['pool']}) | {r['gold_screened']}/{r['gold_total']} ({r['screened']}) | "
            f"{r['gold_judged']}/{r['gold_total']} ({r['judged']}) | {r['grade_elsewhere']} | {r['grade_here']} | "
            f"{exp.get('elsewhere', '-')} / {exp.get('here', '-')} | {r['supports_4_5']['elsewhere']}/{r['supports_4_5']['here']} | "
            f"{stop} | {calls or '-'} | {tin}/{tout} | {c.get('usd', 0):.3f} | {c.get('wall_s', '-')} |"
        )
    return "# Agentic search eval (task 054)\n\n" + head + "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--task", default=DEFAULT_TASK)
    ap.add_argument("--link", action="append", required=True)
    ap.add_argument("--gold", type=Path, default=HERE / "gold.json")
    ap.add_argument("--arms", nargs="+", default=["A", "B", "C"])
    ap.add_argument(
        "--budget",
        type=float,
        default=2.9,
        help="US dollars of new calls, all runs on this cache",
    )
    args = ap.parse_args()
    gold_all = json.loads(args.gold.read_text())
    h = Harness(args.budget)
    print(
        "route",
        h.r.name,
        "standard",
        h.standard,
        "screen",
        h.r.model_for("screen"),
        file=sys.stderr,
    )
    results_path = OUT / "results.json"
    existing = json.loads(results_path.read_text()) if results_path.exists() else []
    arms = {"A": arm_a, "B": arm_b, "C": arm_c}
    try:
        for link_id in args.link:
            link = h.load_link(uuid.UUID(args.task), link_id)
            if not link.hash_matches:
                print(
                    f"warning: {link_id} wording changed since it was judged",
                    file=sys.stderr,
                )
            for arm in args.arms:
                row = arms[arm](h, link, gold_all.get(link_id, {}))
                existing = [
                    r for r in existing if (r["link"], r["arm"]) != (link_id, arm)
                ] + [row]
                h.cache.save()
                results_path.write_text(json.dumps(existing, indent=1, default=str))
                print(
                    f"{link_id[:8]} {arm} done; spend this run ${h.cache.spent:.3f}, all runs ${h.cache.total:.3f}",
                    file=sys.stderr,
                )
    finally:
        h.cache.save()
        h.fetcher.close()
        print(f"new spend this run: ${h.cache.spent:.3f}", file=sys.stderr)
    (OUT / "report.md").write_text(report(existing))
    print((OUT / "report.md").read_text())


if __name__ == "__main__":
    main()
