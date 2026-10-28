import sys, json, uuid, collections
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "scripts/evals/theory_of_change"); sys.path.insert(0, sys.argv[1])
import _route  # noqa
import harness as H
import judge_v7 as V7
from policy_atlas.theory_of_change.evidence import judge_prompt as V6
from policy_atlas.theory_of_change import check
from policy_atlas.core.db import get_engine
from sqlalchemy import text as sql
TASK = uuid.UUID(sys.argv[2])
h = H.Harness(0.6, H.OUT / "rejudge_epps.pkl")
with get_engine().connect() as c:
    rows = c.execute(sql("""select e.link_id::text, e.task_source_snapshot_id::text, ss.metadata->>'title' t, coalesce(ss.metadata->>'abstract','') a, ss.metadata->>'year' y
      from toc_item_evidence e join task_source_snapshot tss using (task_source_snapshot_id) join source_snapshot ss on ss.source_snapshot_id=tss.source_snapshot_id
      where e.task_id=:t"""), {"t": TASK}).all()
links = {}
for lid in {r[0] for r in rows}:
    try: links[lid] = h.load_link(TASK, lid)
    except Exception as ex: print("skip link", lid, type(ex).__name__)
def judge(mod, r):
    l = links[r[0]]; text = (r[2] or "") + "\n" + r[3]
    msgs = mod.build_judge_messages(item_text=l.item_text, population=l.population, place=l.place, document_id="d", title=r[2] or "", year=int(r[4]) if (r[4] or "").isdigit() else None, text=text, neighbours=l.neighbours)
    resp = h.client.chat.completions.parse(model="gpt-6.1-terra", messages=msgs, response_format=mod.JudgeResponse, max_completion_tokens=4000, reasoning_effort="none")
    p = resp.choices[0].message.parsed; sup = p.support
    if sup != "not_about" and not check.quote_found(text, p.quote): sup = "not_about"
    return sup, (p.relevance if sup != "not_about" else 0), p.relevance_reason
jobs = [r for r in rows if r[0] in links]
with ThreadPoolExecutor(12) as ex:
    a = list(ex.map(lambda r: judge(V6, r), jobs)); b = list(ex.map(lambda r: judge(V7, r), jobs))
SUP = {"strong": 2, "weak": 1, "mixed": 0, "refutes": -2}
def verdicts(res):
    per = collections.defaultdict(list)
    for r, (s, rel, _) in zip(jobs, res):
        if s != "not_about": per[r[0]].append((s, rel))
    out = {}
    for lid in links:
        W = sum(1 * rel / 9 for s, rel in per[lid]); S = (sum(rel / 9 * SUP[s] for s, rel in per[lid]) / W) if W else 0
        out[lid] = ("insufficient" if W < 1 else "confident" if S >= 1 else "not_confident" if S <= -0.5 else "mixed", round(W, 2), len(per[lid]))
    return out
va, vb = verdicts(a), verdicts(b)
print("pairs", len(jobs), "| on-topic v6", sum(s != "not_about" for s, _, _ in a), "| on-topic v7", sum(s != "not_about" for s, _, _ in b))
print("relevance v7 of on-topic", collections.Counter(rel for s, rel, _ in b if s != "not_about"))
print("verdicts v6", collections.Counter(v[0] for v in va.values()), "| v7", collections.Counter(v[0] for v in vb.values()))
print("links with any on-topic doc: v6", sum(v[2] > 0 for v in va.values()), "v7", sum(v[2] > 0 for v in vb.values()), "of", len(links))
print("\nNEWLY ON-TOPIC under v7:")
for r, x, y in zip(jobs, a, b):
    if x[0] == "not_about" and y[0] != "not_about":
        print(f"  {links[r[0]].item_text.splitlines()[0][:60]} || {(r[2] or '')[:70]} ({r[4]}) -> {y[0]} R{y[1]} | {(y[2] or '')[:70]}")
print("\nLOST under v7:", sum(1 for x, y in zip(a, b) if x[0] != "not_about" and y[0] == "not_about"))
