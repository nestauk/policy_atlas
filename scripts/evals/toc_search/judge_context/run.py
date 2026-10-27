"""Judge context experiment (task 054, lead). Variants of toc_judge on a labelled set."""
import json, re, sys, uuid, time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal
sys.path.insert(0, "scripts/evals/toc_search"); sys.path.insert(0, sys.argv[1])
import _route  # noqa
import harness as H
from labels import LABELS
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text as sql
from policy_atlas.theory_of_change import check, store
from policy_atlas.theory_of_change.draft import walk_toc_plan
from policy_atlas.theory_of_change.evidence import judge_prompt as JP
from policy_atlas.core.db import get_engine

OUTDIR = sys.argv[1]; VARIANTS = sys.argv[2].split(","); MODEL = sys.argv[3]; REPS = int(sys.argv[4])
PRICE = {"gpt-6.1-terra": (1.0, 0.05, 5.0), "gpt-5.6-terra": (2.0, 0.2, 12.0)}[MODEL]
docs = json.load(open(f"{OUTDIR}/docs.json"))
h = H.Harness(0.1, H.OUT / "judge_exp_cache.pkl")

def clean(s: str) -> str:
    s = re.sub(r"\b(If|for|then|because) (IF|FOR|THEN|BECAUSE) ", r"\1 ", s)
    return s.replace("..", ".").replace(" in England in England", " in England")

def context(link_id):
    l = h.load_link(uuid.UUID(H.DEFAULT_TASK), link_id)
    with get_engine().connect() as conn:
        graph, _ = store.load_graph(conn, l.task_id)
        run_id = conn.execute(sql("select run_id from runs where capability_run_id=:w limit 1"), {"w": l.walk_id}).scalar_one()
        plan = walk_toc_plan(conn, task_id=l.task_id, run_id=run_id, scope_id=l.walk_scope)
    chain = []
    for lid, lk in graph.links.items():
        mark = ">> THIS STEP: " if lid == link_id else "- "
        chain.append(mark + lk.sentence.strip())
    policy = "\n".join(f"{k}: {v}" for k, v in [("Intervention", plan.intervention), ("Intended change", plan.intended_change),
        ("Population", plan.target_population), ("Place", plan.where), ("Time horizon", plan.time_horizon)] if v)
    return l, policy, "\n".join(chain)

# ---- variant prompts ----------------------------------------------------------
BASE = JP.TOC_JUDGE_SYSTEM_PROMPT
TEST_RULES = """
## What tests this step

Judge the step itself, not the policy. Read <the_test>: a document answers
worked_elsewhere when it changes or compares the step's source (or a close,
named proxy for it) and measures the step's target (or a close proxy), in any
setting and for any reason. The policy does not need to appear.
For example, for "children consume less excess energy, so fewer children live
with obesity", a trial that cut sugary drinks and measured overweight answers
worked_elsewhere, though it is not about advertising.

A document that only asserts the step (a commentary, an editorial, an
introduction) without reporting data from a study or a review is not_about.
"""
HERE_RULES = """
## Holds here: decide what the step depends on

Before holds_here, decide from <the_test> whether the step depends on place.
- Depends on place: the step runs through rules, media, markets, services,
  platforms or firms (for example how much of children's ad exposure the
  covered placements carry). Only a study in the stated place, or a named
  setting the document shows to be like it, answers holds_here. A study from
  another country is not_about for holds_here, even when it answers
  worked_elsewhere.
- Does not depend on place: the step runs through biology or general human
  responses (energy balance, children's response to a food advert). Then
  holds_here is about the stated population: a study of a clearly similar
  population (children of similar age in a high-income country) answers
  holds_here the same way it answers worked_elsewhere.
"""
V3_FIELDS_NOTE = """
## Read the document first

Fill study_place, study_population, what_changed, what_measured and
step_depends_on_place before the stances, from the document text only. Use
them to decide the stances.
"""

def system(v):
    if v == "V0": return BASE
    if v == "V1": return BASE
    if v in ("V2", "V4"): return BASE + TEST_RULES + HERE_RULES
    if v == "V3": return BASE + TEST_RULES + HERE_RULES + V3_FIELDS_NOTE

class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    study_place: str | None
    study_population: str | None
    what_changed: str = Field(description="What the study changed or compared, in at most 15 words.")
    what_measured: str = Field(description="The outcome it measured, in at most 15 words.")
    step_depends_on_place: bool

class V3Response(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reading: Reading
    worked_elsewhere: JP.StanceWire
    holds_here: JP.StanceWire
    condition: str | None
    case_study: JP.CaseStudyWire | None
    indicator: JP.IndicatorWire | None
    robust_model: bool | None

def the_test(l):
    lines = clean(l.item_text).splitlines()
    src = next((x[6:] for x in lines if x.startswith("From: ")), "")
    tgt = next((x[4:] for x in lines if x.startswith("To: ")), "")
    return f"Source (what changes first): {src}\nTarget (what should follow): {tgt}"

def messages(v, l, policy, chain, doc):
    if v == "V0":
        return JP.build_judge_messages(item_text=l.item_text, population=l.population, place=l.place, document_id="d",
            title=doc["title"], year=doc["year"], text=doc["abstract"], neighbours=l.neighbours)
    msgs = JP.build_judge_messages(item_text=clean(l.item_text), population=l.population, place=l.place, document_id="d",
        title=doc["title"], year=doc["year"], text=doc["abstract"], neighbours=l.neighbours)
    extra = "" if v == "V4" else f"<policy>\n{policy}\n</policy>\n<whole_theory>\n{chain}\n</whole_theory>\n"
    if v in ("V2", "V3", "V4"):
        extra += f"<the_test>\n{the_test(l)}\n</the_test>\n"
    msgs[0] = {"role": "system", "content": system(v)}
    msgs[1] = {"role": "user", "content": extra + msgs[1]["content"]}
    return msgs

def call(v, l, policy, chain, doc):
    schema = V3Response if v == "V3" else JP.JudgeResponse
    t = time.time()
    r = h.client.chat.completions.parse(model=MODEL, messages=messages(v, l, policy, chain, doc), response_format=schema,
        max_completion_tokens=4000, reasoning_effort="none")
    p = r.choices[0].message.parsed; u = r.usage
    cached = (u.prompt_tokens_details.cached_tokens or 0) if u.prompt_tokens_details else 0
    usd = ((u.prompt_tokens - cached) * PRICE[0] + cached * PRICE[1] + u.completion_tokens * PRICE[2]) / 1e6
    out = {"usd": usd, "s": time.time() - t, "reading": p.reading.model_dump() if v == "V3" else None}
    for name, w in (("e", p.worked_elsewhere), ("h", p.holds_here)):
        st = w.stance
        if st != "not_about" and not check.quote_found(doc["abstract"], w.quote): st = "not_about*"
        out[name] = st; out[name + "_q"] = w.quote
    return out

jobs = []
ctx = {lid: context(lid) for lid in LABELS}
for v in VARIANTS:
    for lid, labs in LABELS.items():
        for doi in labs:
            for rep in range(REPS):
                jobs.append((v, lid, doi, rep))
def run(j):
    v, lid, doi, rep = j
    l, policy, chain = ctx[lid]
    try: return j, call(v, l, policy, chain, docs[doi])
    except Exception as e: return j, {"error": repr(e)[:300]}
with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(run, jobs))
json.dump([{"v": j[0], "link": j[1], "doi": j[2], "rep": j[3], **o} for j, o in res],
          open(f"{OUTDIR}/res_{MODEL}_{'-'.join(VARIANTS)}.json", "w"), indent=1)
print("cost", round(sum(o.get("usd", 0) for _, o in res), 3), "errors", sum("error" in o for _, o in res))
if VARIANTS == ["V1"]: print(ctx[next(iter(LABELS))][1]); print(ctx[next(iter(LABELS))][2])
