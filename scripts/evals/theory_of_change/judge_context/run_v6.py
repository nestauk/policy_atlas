import json, sys, uuid, collections
from concurrent.futures import ThreadPoolExecutor
D = sys.argv[1]; sys.path.insert(0, "scripts/evals/theory_of_change"); sys.path.insert(0, D)
import _route  # noqa
import harness as H
import judge_v6 as JP
from labels import LABELS
from policy_atlas.theory_of_change import check
docs = json.load(open(f"{D}/docs.json"))
h = H.Harness(0.3, H.OUT / "judge_v6.pkl")
links = {lid: h.load_link(uuid.UUID(H.DEFAULT_TASK), lid) for lid in LABELS}
def one(job):
    lid, doi, rep = job; l = links[lid]; d = docs[doi]
    msgs = JP.build_judge_messages(item_text=l.item_text, population=l.population, place=l.place, document_id="d", title=d["title"], year=d["year"], text=d["abstract"], neighbours=l.neighbours)
    r = h.client.chat.completions.parse(model="gpt-6.1-terra", messages=msgs, response_format=JP.JudgeResponse, max_completion_tokens=4000, reasoning_effort="none")
    p = r.choices[0].message.parsed
    sup = p.support
    if sup != "not_about" and not check.quote_found(d["abstract"], p.quote): sup = "not_about*"
    u = r.usage; return dict(lid=lid, doi=doi, rep=rep, support=sup, rel=p.relevance, why=p.relevance_reason, usd=(u.prompt_tokens*1.0+u.completion_tokens*5.0)/1e6)
jobs = [(l, d, r) for l, labs in LABELS.items() for d in labs for r in range(3)]
with ThreadPoolExecutor(8) as ex: res = list(ex.map(one, jobs))
json.dump(res, open(f"{D}/res_v6.json", "w"), indent=1)
MAP = {"supports": {"strong", "weak"}, "challenges": {"refutes", "mixed"}, "not_about": {"not_about"}}
ok = 0; g = collections.defaultdict(set); relc = collections.Counter()
for r in res:
    want = set().union(*[MAP[x] for x in LABELS[r["lid"]][r["doi"]][0]])
    ok += r["support"] in want; g[(r["lid"], r["doi"])].add((r["support"], r["rel"]))
    if r["support"] != "not_about": relc[r["rel"]] += 1
print("support right", ok, "/", len(res), "| consistent (support+rel same 3/3)", sum(len(v) == 1 for v in g.values()), "/", len(g),
      "| consistent support only", sum(len({x[0] for x in v}) == 1 for v in g.values()), "| cost", round(sum(r["usd"] for r in res), 3))
print("relevance of non-not_about answers", dict(relc))
for r in sorted(res, key=lambda r: (r["lid"], r["doi"], r["rep"])):
    want = set().union(*[MAP[x] for x in LABELS[r["lid"]][r["doi"]][0]])
    if r["support"] not in want or r["rep"] == 0:
        print(("   " if r["support"] in want else "XX "), r["lid"][:8], docs[r["doi"]]["title"][:55], "|", r["support"], r["rel"], "|", (r["why"] or "")[:70])
