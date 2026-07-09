"""Demo analysis driver: walks the EB chain live, streaming progress to the bus.

The fixed driver executes the compiled plan (execution-orchestration spec: plan-time
authority); the orchestrator LLM narrates stage completions and mediates check-ins
into the same thread that planned the analysis. One transaction per stage so read
models see committed state as each stage lands.

ponytail: module-level bus/stage globals — one live analysis at a time. Per-project
buses if the demo ever runs two analyses concurrently.
"""

import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from demo.server import orchestrator
from demo.server.bus import EventBus
from demo.server.fetcher import DemoLiveFetcher
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events, search_generation, search_live, search_loop, tracing
from policy_atlas.acquire import SearchBackend
from policy_atlas.classification_backend import OpenAIClassificationBackend
from policy_atlas.db import get_engine
from policy_atlas.embeddings import OpenAIEmbeddingBackend
from policy_atlas.extraction_backend import OpenAIExtractionBackend
from policy_atlas.facet_grouping import OpenAIFacetGroupingBackend
from policy_atlas.grounding_judge import OpenAIGroundingJudgeBackend
from policy_atlas.grouping import OpenAIThemeGroupingBackend
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest_full_text import candidate_urls
from policy_atlas.plan import Plan
from policy_atlas.plan import compile as compile_plan
from policy_atlas.ranking import OpenAIRankingBackend
from policy_atlas.schema import (
    evidence_scope,
    project,
    project_source_snapshot,
    runs,
    source_snapshot,
)
from policy_atlas.screening_backend import OpenAIScreeningBackend
from policy_atlas.synthesis_backend import OpenAISynthesisBackend

log = structlog.get_logger()

# ponytail: demo-branch model upgrade — the artefact is the demo's closing shot, so
# the model writing the blocks runs judgment-class instead of mini (user call:
# judge + extraction stay mini). Module-constant patch, so src/ stays untouched;
# the real change belongs to the eval slice's model-routing calibration.
import policy_atlas.facet_grouping as _facet_mod  # noqa: E402
import policy_atlas.group as _group_mod  # noqa: E402
import policy_atlas.synthesis_backend as _synth_mod  # noqa: E402

_synth_mod.SYNTHESIS_MODEL = "gpt-5.5"
# Observed live (finance-ministries run): 25 docs → 427 findings → 280 distinct
# facet values, over the fail-closed 150 cap pinned on fixture corpora. Raised
# for the demo only; the real ceiling belongs to the large-corpus grouping seam
# (docs/deferred.md) and its eval calibration. group.py binds the constant by
# value at import, so patch BOTH modules.
_facet_mod.FACET_VALUE_CAP = 400
_group_mod.FACET_VALUE_CAP = 400

# --- structlog → bus bridge (installed once at app startup) ---

_BUS: EventBus | None = None
_STAGE: str | None = None

# The activity feed is user-facing: ALLOWLIST only. Telemetry (token usage,
# budgets, tracing, internals) never reaches the browser — a curated set of
# log events translates to plain English; everything else is dropped.
_NOTE_EVENTS: dict[str, str] = {
    "screen.call_budget": "Screening the found sources for relevance",
    "screen.profile": "Screening pass starting",
    "search.rapid_thin_escalation": "First pass looks thin — searching deeper",
    "ingest.parse_started": "Reading fetched documents",
    "extract.window": "Reading closely and pulling out findings",
    "extract.doc_started": "Extracting findings from the next document",
    "group.discovery": "Looking for groups across the findings",
    "synthesise.section_started": "Drafting the next section",
}


def _translate(event_dict: dict[str, Any]) -> dict[str, Any] | None:
    name = str(event_dict.get("event", ""))
    if not name:
        return None
    fields = {
        k: v
        for k, v in event_dict.items()
        if k not in ("event", "timestamp", "level", "logger")
        and isinstance(v, (int, float, str, bool))
        and len(str(v)) <= 200
    }
    out: dict[str, Any] = {"stage": _STAGE, "kind": "tick"}
    if "query" in fields:
        out.update(kind="search_query", backend=fields.get("backend", ""),
                   query=str(fields["query"])[:160])
        return out
    if "deep_round" in name or name == "search.deep_round_summary":
        round_fields = {k: fields[k] for k in fields if "round" in k or "relevant" in k}
        out.update(kind="round", **round_fields)
        return out
    if name.startswith("search.") and "count" in fields:
        out.update(kind="results", backend=fields.get("backend", ""), count=fields["count"])
        return out
    if name in _NOTE_EVENTS:
        out.update(note=_NOTE_EVENTS[name])
        return out
    # per-call/per-doc liveness: these fire in real time from worker threads,
    # so a generic plain-English tick per event keeps long stages visibly alive
    # (the frontend collapses consecutive duplicates into a counter)
    live_ticks = {
        "screening.screen.usage": "Screening sources against your question",
        "classification.classify.usage": "Labelling evidence types",
        "extraction.extract.usage": "Reading closely and pulling out findings",
        "fulltext.ingested": "Read a document in full",
        "fulltext.failed": "A document couldn't be fetched — recorded",
        "grouping.discover.usage": "Looking for themes across the sources",
    }
    if name in live_ticks:
        out.update(note=live_ticks[name])
        return out
    return None  # everything else is telemetry — not for the user


def _bridge_processor(logger: Any, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    if _BUS is not None and _STAGE is not None:
        try:
            translated = _translate(dict(event_dict))
            if translated is not None:
                _BUS.emit("stage.progress", translated)
        except Exception:  # noqa: BLE001 — the bridge must never break a component
            pass
    return event_dict


def install_log_bridge() -> None:
    """Prepend the bus bridge to the already-configured structlog processor chain."""
    config = structlog.get_config()
    processors = list(config["processors"])
    if _bridge_processor not in processors:
        structlog.configure(processors=[_bridge_processor] + processors)


# --- stage vocabulary (user-facing labels; component names never reach the UI) ---

STAGES: dict[str, tuple[str, str]] = {
    "acquire": ("Searching sources", "Queries out to academic and policy databases"),
    "screen": ("Screening for relevance", "Every title and abstract, against your question"),
    "classify": ("Sorting by evidence type", "Trial, review, evaluation — each source labelled"),
    "appraise": ("Appraising quality", "How much weight each source can bear"),
    "ingest_full_text": ("Reading in full", "Fetching the documents; paywalls noted, not hidden"),
    "characterise": ("Mapping the landscape", "What the evidence covers, and where it's thin"),
    "select": ("Shortlisting", "The strongest, most varied set for close reading"),
    "extract": ("Extracting findings", "Each claim pulled out with its exact quote"),
    "group": ("Grouping findings", "Findings that answer the same question, together"),
    "synthesise": ("Writing the evidence base", "Cited, checked, ready to challenge"),
}

_SUMMARY_DROP = ("docs", "selected", "excluded", "groups", "themes", "distributions", "rounds")


def _summarise(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Counts-only trim of a component.completed payload for SSE / narration.

    User-facing: numbers read as progress; strings (ids, versions, vocab
    values) read as internals — numbers only, capped, one level deep.
    """
    if not payload:
        return {}
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SUMMARY_DROP:
            out[key + "_count"] = len(value) if isinstance(value, (list, dict)) else value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = value
        elif isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and len(out) < 8:
                    out[k] = v
    return {k: v for k, v in list(out.items())[:8]}


class AnalysisDriver:
    """Runs one live analysis for one project, in a background thread."""

    def __init__(
        self,
        project_id: uuid.UUID,
        plan: dict[str, Any],
        bus: EventBus,
        create_project_row: bool = False,
    ) -> None:
        self.project_id = project_id
        self.plan = plan
        self.bus = bus
        self.create_project_row = create_project_row
        self.scope_id: uuid.UUID | None = None
        self.thread: threading.Thread | None = None
        self.failed: str | None = None
        self.done = False
        self._checkin_replies: dict[str, str] = {}
        self._checkin_event = threading.Event()

    # -- public --

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def answer_checkin(self, checkin_id: str, reply: str) -> None:
        self._checkin_replies[checkin_id] = reply
        self._checkin_event.set()

    # -- internals --

    def _run(self) -> None:
        global _BUS
        _BUS = self.bus
        try:
            self.bus.emit("analysis.started", {})
            self._walk_chain()
            self.bus.emit("analysis.completed", {})
        except Exception as exc:  # noqa: BLE001 — surface honestly, never hang the stream
            log.exception("demo.analysis_failed")
            self.failed = f"{type(exc).__name__}: {exc}"
            self.bus.emit("analysis.failed", {"stage": _STAGE, "message": self.failed})
        finally:
            self.done = True
            _set_stage(None)
            _BUS = None

    def _walk_chain(self) -> None:
        question = self.plan["question"]
        engine = get_engine()
        langfuse_client = tracing.get_langfuse()
        backends = {
            "embedding_backend": tracing.TracedEmbeddingBackend(
                OpenAIEmbeddingBackend(), langfuse_client
            ) if langfuse_client else OpenAIEmbeddingBackend(),
            "theme_grouping_backend": tracing.TracedThemeGroupingBackend(
                OpenAIThemeGroupingBackend(), langfuse_client
            ) if langfuse_client else OpenAIThemeGroupingBackend(),
            "screening_backend": OpenAIScreeningBackend(langfuse_client=langfuse_client),
            "classification_backend": OpenAIClassificationBackend(langfuse_client=langfuse_client),
            "ranking_backend": OpenAIRankingBackend(langfuse_client=langfuse_client),
            "extraction_backend": OpenAIExtractionBackend(langfuse_client=langfuse_client),
            "facet_grouping_backend": OpenAIFacetGroupingBackend(langfuse_client=langfuse_client),
            "synthesis_backend": OpenAISynthesisBackend(langfuse_client=langfuse_client),
            "grounding_judge_backend": OpenAIGroundingJudgeBackend(langfuse_client=langfuse_client),
            "search_backends": cast(
                "list[SearchBackend]", search_live.live_search_backends()
            ),
            "search_generation_backend": search_generation.OpenAISearchGenerationBackend(
                langfuse_client=langfuse_client
            ),
        }
        self._langfuse = langfuse_client
        self._backends = backends

        # Scope (and project row for seed runs) — searches always start rapid; the
        # deep leg runs as acquire↔screen rounds after the first sift.
        with engine.begin() as conn:
            if self.create_project_row:
                conn.execute(project.insert().values(
                    project_id=self.project_id, created_at=datetime.now(UTC),
                ))
            self.scope_id = uuid.uuid4()
            conn.execute(evidence_scope.insert().values(
                evidence_scope_id=self.scope_id,
                project_id=self.project_id,
                intent=question,
                context={"search": {"depth": "rapid"}, "focus": self.plan.get("focus", [])},
                created_at=datetime.now(UTC),
            ))

        # 1. Search + sift (rapid leg)
        self._stage(engine, "acquire")
        screen_summary = self._stage(engine, "screen")

        # 2. Deep leg: user asked for deep, or the rapid pass came back thin
        with engine.connect() as conn:
            escalate = search_loop.should_escalate(
                conn, project_id=self.project_id, scope_id=self.scope_id
            )
        if self.plan.get("search_depth") == "deep" or escalate:
            if escalate and self.plan.get("search_depth") != "deep":
                self._checkin("thin_evidence", question, screen_summary,
                              ["Search deeper", "Continue with what we have"])
            self._deep_episode(engine)

        # 3. Quality-check + read. Quick runs stay light: no full-document
        # fetching, close reading or findings extraction — the write-up works
        # from titles and abstracts, and the plan says so.
        quick = self.plan.get("search_depth") == "quick"
        self._stage(engine, "classify")
        self._stage(engine, "appraise")
        if not quick:
            self._prefetch(engine)
            self._stage(engine, "ingest_full_text")

        # 4. Landscape + check-in (the frame-04 moment). Discovery is the known
        # live wobbler (invalid-output rejections) — one full stage retry before
        # accepting the failure.
        landscape = self._stage(engine, "characterise", narrate=True)
        if "characterise" not in self._run_ids:
            self.bus.emit("narration", {
                "text": "The landscape mapping stumbled — running it once more.",
            })
            landscape = self._stage(engine, "characterise", narrate=True)
        if self.plan.get("check_in", "moderate") != "minimal":
            self._checkin("landscape", question, landscape,
                          ["Continue as planned", "Adjust the focus"])

        # 5. Deep read + findings + the artefact (deep runs only). Each stage
        # chains only off a SUCCESSFUL predecessor; synthesise runs on the
        # deepest reference that exists (its refs are optional by design).
        if not quick and "characterise" in self._run_ids:
            select_summary = self._stage(
                engine, "select", characterisation_run_id=self._run_ids["characterise"],
            )
            if self.plan.get("check_in") == "frequent" and "select" in self._run_ids:
                self._checkin("selection", question, select_summary,
                              ["Continue", "Change the shortlist"])
        if not quick and "select" in self._run_ids:
            self._stage(engine, "extract", selection_run_id=self._run_ids["select"])
        if not quick and "extract" in self._run_ids:
            self._stage(engine, "group", extraction_run_id=self._run_ids["extract"])
        synth_ref: dict[str, uuid.UUID] = {}
        for stage_name, ref_key in (
            ("group", "grouping_run_id"), ("extract", "extraction_run_id"),
            ("select", "selection_run_id"), ("characterise", "characterisation_run_id"),
        ):
            if stage_name in self._run_ids:
                synth_ref = {ref_key: self._run_ids[stage_name]}
                break
        if not synth_ref:
            # zero substrate is a guaranteed structural refusal — say so instead
            self.bus.emit("narration", {
                "text": "There isn't enough mapped evidence to write from — the "
                "landscape step failed twice, so no evidence base was produced "
                "this run. Everything found and screened is saved; running the "
                "analysis again will pick it up.",
            })
            return
        self._stage(engine, "synthesise", narrate=True, **synth_ref)

    _run_ids: dict[str, uuid.UUID]

    def _stage(
        self,
        engine: Any,
        component: str,
        narrate: bool = False,
        **plan_refs: uuid.UUID,
    ) -> dict[str, Any]:
        if not hasattr(self, "_run_ids"):
            self._run_ids = {}
        label, blurb = STAGES[component]
        _set_stage(component)
        self.bus.emit("stage.started", {"stage": component, "stage_label": label,
                                        "stage_blurb": blurb})
        started = time.monotonic()
        with engine.begin() as conn:
            run_id, payload, failure = self._execute(conn, component, **plan_refs)
        if failure is not None:
            # honest, visible, non-fatal: the chain continues on the deepest
            # successful reference; the failed stage never enters _run_ids
            self.bus.emit("stage.failed", {"stage": component, "stage_label": label,
                                           "reason": failure})
            self.bus.emit("narration", {
                "text": f"{label} hit a limit and stopped: {failure}. Recorded — "
                "carrying on with what the analysis has.",
            })
            return {}
        self._run_ids[component] = run_id
        summary = _summarise(payload)
        summary["seconds"] = round(time.monotonic() - started, 1)
        self.bus.emit("stage.completed", {"stage": component, "stage_label": label,
                                          "summary": summary})
        if narrate:
            self._narrate(label, summary)
        return summary

    def _execute(
        self, conn: Connection, component: str, **plan_refs: uuid.UUID
    ) -> tuple[uuid.UUID, dict[str, Any] | None]:
        """One run: run row + plan.compiled + harness execution (skeleton recipe)."""
        run_id = uuid.uuid4()
        conn.execute(runs.insert().values(
            run_id=run_id, project_id=self.project_id, status="running",
            started_at=datetime.now(UTC),
        ))
        events.append(conn, project_id=self.project_id, run_id=run_id,
                      event_type="run.started", payload={})
        config = compile_plan(Plan(
            component=component,
            evidence_scope_id=self.scope_id,
            search_backend_scope=self.plan.get("evidence_sources", "both"),
            **plan_refs,
        ))
        events.append(conn, project_id=self.project_id, run_id=run_id,
                      event_type="plan.compiled",
                      payload={"component": component,
                               "evidence_scope_id": str(self.scope_id),
                               **{k: str(v) for k, v in plan_refs.items()}})
        with tracing.component_span(
            self._langfuse, run_id=run_id, project_id=self.project_id, component=component
        ):
            run_harness(
                conn, config=config, project_id=self.project_id, run_id=run_id,
                provider=StubEchoProvider(),
                document_fetcher=getattr(self, "_fetcher", None),
                **self._backends,
            )
        log_entries = events.read(conn, self.project_id)
        payload = next(
            (e["payload"] for e in reversed(log_entries)
             if e["event_type"] == "component.completed"
             and e["payload"].get("component") == component and e["run_id"] == run_id),
            None,
        )
        failure: str | None = None
        if payload is None:
            failure_payload = next(
                (e["payload"] for e in reversed(log_entries)
                 if e["event_type"] == "component.failed"
                 and e["payload"].get("component") == component and e["run_id"] == run_id),
                None,
            )
            if failure_payload is not None:
                failure = str(failure_payload.get("error", "unknown"))
        return run_id, payload, failure

    def _deep_episode(self, engine: Any) -> None:
        """The acquire↔screen deep rounds, one transaction (loop state spans rounds)."""
        label = "Searching deeper"
        self.bus.emit("stage.started", {"stage": "deep_search", "stage_label": label,
                                        "stage_blurb": "Reformulating from what the first "
                                        "pass taught; following citation trails"})
        with engine.begin() as conn:
            context = dict(conn.execute(
                select(evidence_scope.c.context)
                .where(evidence_scope.c.evidence_scope_id == self.scope_id)
            ).scalar_one())
            context["search"] = {**context.get("search", {}), "depth": "deep"}
            conn.execute(evidence_scope.update()
                         .where(evidence_scope.c.evidence_scope_id == self.scope_id)
                         .values(context=context))

            def acquire_round() -> dict[str, Any]:
                _set_stage("acquire")
                run_id, payload, _failure = self._execute(conn, "acquire")
                self._run_ids["acquire"] = run_id
                return payload or {}

            def screen_round() -> dict[str, Any]:
                _set_stage("screen")
                run_id, payload, _failure = self._execute(conn, "screen")
                self._run_ids["screen"] = run_id
                return payload or {}

            deep_summary = search_loop.run_deep_rounds(
                conn, project_id=self.project_id, scope_id=self.scope_id,
                acquire_round=acquire_round, screen_round=screen_round, start_round=2,
            )
        _set_stage(None)
        self.bus.emit("stage.completed", {
            "stage": "deep_search", "stage_label": label,
            "summary": {
                "rounds": len(deep_summary["rounds"]),
                "stop_condition": deep_summary["stop_condition"],
                "confident_relevant": deep_summary["confident_relevant"],
                "seconds": round(deep_summary["wall_clock_s"], 1),
            },
        })
        self._narrate(label, _summarise({
            "confident_relevant": deep_summary["confident_relevant"],
            "rounds": deep_summary["rounds"],
            "stop_condition": deep_summary["stop_condition"],
        }))

    def _prefetch(self, engine: Any) -> None:
        """Warm the fetch cache in parallel before the serial ingest walk."""
        self._fetcher = DemoLiveFetcher()
        with engine.connect() as conn:
            rows = conn.execute(
                select(source_snapshot.c.metadata)
                .select_from(project_source_snapshot.join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                ))
                .where(project_source_snapshot.c.project_id == self.project_id,
                       project_source_snapshot.c.origin == "acquired",
                       project_source_snapshot.c.full_text_status == "not_attempted")
            ).fetchall()
        # first two candidates per doc cover the cascade's common path; misses
        # fall back to inline fetch during ingest
        urls = [u for row in rows for u in candidate_urls(row.metadata)[:2]]
        _set_stage("ingest_full_text")

        def on_progress(done: int, ok: int, failed: int, total: int) -> None:
            if done % 5 == 0 or done == total:
                self.bus.emit("stage.progress", {"stage": "ingest_full_text",
                                                 "kind": "fetch", "ok": ok,
                                                 "failed": failed, "total": total})

        self._fetcher.prefetch(urls, on_progress=on_progress)

    def _narrate(self, label: str, summary: dict[str, Any]) -> None:
        try:
            text = orchestrator.narrate(label, self.plan["question"], summary)
            self.bus.emit("narration", {"text": text})
        except Exception:  # noqa: BLE001 — narration is garnish, never fatal
            log.exception("demo.narration_failed")

    def _checkin(
        self, kind: str, question: str, summary: dict[str, Any], options: list[str]
    ) -> None:
        checkin_id = str(uuid.uuid4())
        try:
            text = orchestrator.checkin(kind, question, summary)
        except Exception:  # noqa: BLE001
            text = "Pausing to check in — happy for me to continue?"
        self._checkin_event.clear()
        self.bus.emit("checkin", {"checkin_id": checkin_id, "text": text,
                                  "options": options})
        # ponytail: 30-min wait then continue-as-planned, so an unattended run
        # never hangs forever
        self._checkin_event.wait(timeout=1800)
        reply = self._checkin_replies.get(checkin_id, options[0])
        self.bus.emit("narration", {"text": f"Noted — {reply.lower()}. Carrying on."})


def _set_stage(stage: str | None) -> None:
    global _STAGE
    _STAGE = stage
