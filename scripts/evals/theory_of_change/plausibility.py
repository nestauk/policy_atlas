"""Experiment (task 054, red team, 2026-11-03): can a judge tell a theory that cannot work?

Two judges, tested on cases we already have, before anything is built:

- **Sense check** (plan stage, before drafting): is there a credible way the
  intervention could cause the goal? Run on the plan alone (``prior``) and with
  a quick OpenAlex search on the whole intervention (``searched``), so a
  rejection never rests on the model's prior only.
- **Theory verdict** (after the evidence check): one overall verdict for the
  checked theory, and a plain headline sentence for the top of the report.

Cases: plans of real theories (MUP, food advertising, EPPS, Changing Futures),
plausible plans we wrote, and nonsense plans (three already run as red-team
tasks, three more written here). Each case carries the label we expect.

Run from the repo root (reads the task plans and theories from the local API on
port 8001; never calls Consensus)::

    uv run --project backend --env-file backend/.env python \\
        scripts/evals/theory_of_change/plausibility.py --token-file <path>

Writes ``out/plausibility.json`` and prints a table.
"""

from __future__ import annotations

import _route  # noqa: F401  (must load before policy_atlas: pins the OpenAI route)

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import resolve_openai_client, traced_parse
from policy_atlas.evidence_search.sourcing.acquire import _reconstruct_abstract
from policy_atlas.evidence_search.sourcing.search_live import OpenAlexLiveBackend
from policy_atlas.theory_of_change.plausibility_prompt import (
    SenseCheckResponse as SenseCheck,
)
from policy_atlas.theory_of_change.plausibility_prompt import (
    TheoryVerdictResponse as TheoryVerdictOut,
)
from policy_atlas.theory_of_change.plausibility_prompt import (
    build_sense_check_messages,
    build_verdict_messages,
)

OUT = Path(__file__).parent / "out"
API = "http://localhost:8001/api/v1"
MODEL_STEP = "toc_review"  # the frontier tier


# --- cases -------------------------------------------------------------------

#: Real theories with a finished check: (task id, expected plan rating, expected theory verdict).
TASKS = {
    "mup": ("b6005bbf-a09e-4ca4-bdac-665270c631a1", "plausible+", "supported"),
    "mup_first": ("20335939-b35c-4fe5-adf6-aa3a46041fbc", "plausible+", "supported"),
    "food_ads": ("f7bb283e-b339-461e-a120-372c124b23ae", "plausible+", "supported|plausible_untested"),
    "epps": ("c2f13482-55a4-457c-8f40-7615f5d0cabd", "plausible+", "plausible_untested"),
    "cf_individual": ("ceb2fcf3-f681-4d4a-a0fa-d3823d834803", "plausible+", "plausible_untested|supported"),
    "cf_system": ("b5b93d8d-f5d5-42ce-8a5d-37a2edbe313f", "plausible+", "plausible_untested"),
    "red_blue_doors": ("893affb8-0679-43c1-95a6-db9a3b762caf", "implausible", "implausible"),
    "red_homeopathy": ("e3f2084c-250d-4230-a671-304986fff61d", "implausible", "implausible"),
    "red_north_doors": ("82b20d4b-b2bd-4d8d-a871-b8822524dd1a", "implausible", "implausible"),
    # Borderline: sensible-sounding programmes whose evaluations found no effect or harm.
    "bl_scared": ("8c3845e7-18d5-4698-8a17-08c613d83d42", "flag", "doubtful|implausible"),
    "bl_dare": ("8f4687ef-e885-494e-8616-7f835828bdf3", "flag", "doubtful|implausible"),
}

#: Plans with no theory yet: (intervention, goal, population, place, expected rating).
PLANS = {
    "bus_travel": (
        "Free bus travel for 16 to 21 year olds",
        "More young people in work or training within three years",
        "People aged 16 to 21",
        "England",
        "plausible+",
    ),
    "phone_ban": (
        "A ban on mobile phones during the school day",
        "Better wellbeing among secondary pupils within two years",
        "Secondary school pupils",
        "England",
        "plausible+",
    ),
    "sugar_levy": (
        "A tiered levy on soft drinks by sugar content, paid by producers",
        "Lower obesity prevalence among children within five years",
        "Children aged 4 to 11",
        "England",
        "plausible+",
    ),
    "street_trees": (
        "Plant 50,000 street trees in the most heat-exposed neighbourhoods",
        "Fewer heat-related deaths among older people within ten years",
        "People aged 65 and over",
        "London",
        "plausible+",
    ),
    "red_rename_nhs": (
        "Rename the NHS the National Wellness Service",
        "Lower adult obesity prevalence within five years",
        "Adults",
        "England",
        "implausible",
    ),
    "red_crystals": (
        "Weekly crystal healing sessions for every prisoner",
        "Lower reoffending within two years of release",
        "Adult prisoners",
        "England and Wales",
        "implausible",
    ),
    "bl_boot_camps": (
        "Military-style boot camps for young offenders instead of custody",
        "Lower reoffending among 15 to 17 year olds within two years",
        "Young offenders aged 15 to 17",
        "England",
        "flag",
    ),
    "bl_abstinence": (
        "Abstinence-only sex education in all secondary schools",
        "Fewer teenage pregnancies within five years",
        "Pupils aged 11 to 16",
        "England",
        "flag",
    ),
    "red_mozart": (
        "Play ten minutes of Mozart daily to babies in every nursery",
        "Higher GCSE maths results when those children sit their GCSEs",
        "Children under two in nurseries",
        "England",
        "implausible",
    ),
}

# --- the judges: the product's own prompts (``plausibility_prompt``) -----------------


def sense_messages(plan: dict[str, Any], docs: list[dict[str, str]] | None) -> list[Any]:
    return build_sense_check_messages(plan, docs or [])


def theory_payload(plan: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    code = {b["box_id"]: b["code"] for b in graph["boxes"]}
    text = {b["box_id"]: b["text"] for b in graph["boxes"]}
    kept = [p for p in graph["pathways"] if p.get("status") == "kept"]
    on = {
        link_id: sum(1 for p in kept if p["kind"] == "success" and link_id in p.get("link_ids", []))
        for link_id in (link["link_id"] for link in graph["links"])
    }
    return {
        "plan": plan,
        "boxes": [{"code": b["code"], "layer": b["layer"], "text": b["text"]} for b in graph["boxes"]],
        "connections": [
            {
                "code": link["code"],
                "from": f"{code[link['source_box_id']]}: {text[link['source_box_id']]}",
                "to": f"{code[link['target_box_id']]}: {text[link['target_box_id']]}",
                "verdict": link.get("verdict"),
                "evidence": link.get("evidence_sentence"),
                "success_pathways": on[link["link_id"]],
            }
            for link in graph["links"]
        ],
        "pathways": [{"label": p["label"], "kind": p["kind"]} for p in kept],
    }


# --- running -------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--models", default="56")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--only", default="", help="Comma-separated case names.")
    args = parser.parse_args()
    http = httpx.Client(
        headers={"Authorization": f"Bearer {Path(args.token_file).read_text().strip()}"}, timeout=60
    )
    client = resolve_openai_client(None, backend_name="plausibility", timeout=300.0, max_retries=2)
    model = route().model_for(MODEL_STEP)
    openalex = OpenAlexLiveBackend(os.environ["OPENALEX_API_KEY"], email=os.environ.get("OPENALEX_EMAIL"))

    def ask(messages: list[Any], fmt: type[BaseModel], label: str) -> Any:
        return traced_parse(
            client,
            None,
            messages=messages,
            response_format=fmt,
            model=model,
            reasoning_effort=route().reasoning_effort_for(model),
            max_output_tokens=4000,
            usage_event="plausibility.usage",
            label=label,
            name=f"plausibility:{label}",
            prompt_version="plausibility_exp3",
        )[0]

    def search(plan: dict[str, Any]) -> list[dict[str, str]]:
        docs: dict[str, dict[str, str]] = {}
        for text in (
            f"{plan['intervention']} effect on {plan['intended_change']}",
            f"effectiveness of {plan['intervention']}",
        ):
            for work in openalex.search_semantic(text, max_results=6):
                abstract = _reconstruct_abstract(work.get("abstract_inverted_index")) or ""
                key = str(work.get("id", "")).rsplit("/", 1)[-1]
                title = str(work.get("title") or work.get("display_name") or "")
                docs.setdefault(key, {"id": key, "title": title, "abstract": abstract[:1200]})
        return list(docs.values())

    cases: dict[str, dict[str, Any]] = {}
    for name, (task_id, expect_plan, expect_theory) in TASKS.items():
        if args.only and name not in args.only.split(","):
            continue
        plan = http.get(f"{API}/tasks/{task_id}/plan").json()["toc"]
        graph = http.get(f"{API}/tasks/{task_id}/toc").json()
        cases[name] = {"plan": plan, "graph": graph, "expect_plan": expect_plan, "expect_theory": expect_theory}
    for name, (intervention, goal, population, place, expect) in PLANS.items():
        plan = {"intervention": intervention, "intended_change": goal, "target_population": population, "where": place}
        cases[name] = {"plan": plan, "graph": None, "expect_plan": expect, "expect_theory": None}

    def keep(plan: dict[str, Any]) -> dict[str, Any]:
        wanted = ("intervention", "intended_change", "target_population", "where", "time_horizon", "dosage")
        return {k: plan.get(k) for k in wanted if plan.get(k)}

    def run(name: str) -> tuple[str, dict[str, Any]]:
        case = cases[name]
        plan = keep(case["plan"])
        docs = search(plan)
        n = args.repeats
        result: dict[str, Any] = {
            "expect_plan": case["expect_plan"],
            "expect_theory": case["expect_theory"],
            "prior": [ask(sense_messages(plan, None), SenseCheck, "sense_prior").model_dump() for _ in range(n)],
            "searched": [ask(sense_messages(plan, docs), SenseCheck, "sense_searched").model_dump() for _ in range(n)],
            "docs": [d["title"] for d in docs],
        }
        if case["graph"] is not None:
            payload = theory_payload(plan, case["graph"])
            # The sense check with search, as the product stores it for the verdict.
            first = result["searched"][0]
            found = {"rating": first["rating"], "reason": first["reason"]}
            messages = build_verdict_messages(payload, found)
            result["theory"] = [ask(messages, TheoryVerdictOut, "theory_verdict").model_dump() for _ in range(n)]
            result["report_summary"] = (case["graph"].get("report") or {}).get("summary_text")
        return name, result

    if args.only:
        cases = {k: v for k, v in cases.items() if k in args.only.split(",")}
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(pool.map(run, cases))
    OUT.mkdir(exist_ok=True)
    (OUT / "plausibility.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))

    def ok(got: str, expect: str | None) -> bool:
        if expect == "plausible+":
            return got in ("established", "plausible")
        if expect == "flag":
            return got in ("doubtful", "implausible")
        return got in (expect or "").split("|")

    def cell(runs: list[dict[str, Any]], key: str, expect: str | None) -> str:
        got = [run[key] for run in runs]
        hits = sum(ok(g, expect) for g in got)
        return f"{'/'.join(g[:5] for g in got):20} {hits}/{len(got)}"

    print(f"{'case':16} {'expect':12} {'prior':26} {'searched':26} {'expect theory':22} theory")
    for name, r in results.items():
        theory = cell(r["theory"], "verdict", r["expect_theory"]) if "theory" in r else ""
        print(
            f"{name:16} {r['expect_plan']:12} {cell(r['prior'], 'rating', r['expect_plan']):26} "
            f"{cell(r['searched'], 'rating', r['expect_plan']):26} {(r['expect_theory'] or ''):22} {theory}"
        )


if __name__ == "__main__":
    main()
