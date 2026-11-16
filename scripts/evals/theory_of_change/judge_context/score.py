import json, sys, glob, collections
sys.path.insert(0, sys.argv[1]); from labels import LABELS
rows = []
for f in glob.glob(f"{sys.argv[1]}/res_*.json"):
    m = f.split("res_")[1].split("_")[0]
    for r in json.load(open(f)): r["m"] = m; rows.append(r)
g = collections.defaultdict(list)
for r in rows: g[(r["m"], r["v"])].append(r)
print("model | variant | elsewhere right | here right | both right | consistent (3/3 same) | unverified quotes | $ per 100 calls")
for k in sorted(g):
    rs = g[k]; n = len(rs)
    ok = lambda r, q, i: r[q].rstrip("*") in LABELS[r["link"]][r["doi"]][i] and not r[q].endswith("*")
    e = sum(ok(r, "e", 0) for r in rs); hh = sum(ok(r, "h", 1) for r in rs); b = sum(ok(r,"e",0) and ok(r,"h",1) for r in rs)
    grp = collections.defaultdict(set)
    for r in rs: grp[(r["link"], r["doi"])].add((r["e"], r["h"]))
    cons = sum(len(s) == 1 for s in grp.values())
    unv = sum(r["e"].endswith("*") + r["h"].endswith("*") for r in rs)
    print(f"{k[0]} | {k[1]} | {e}/{n} | {hh}/{n} | {b}/{n} | {cons}/{len(grp)} | {unv} | {100*sum(r['usd'] for r in rs)/n:.2f}")
if len(sys.argv) > 2:
    m, v = sys.argv[2].split(":")
    for r in sorted(g[(m, v)], key=lambda r: (r["link"], r["doi"], r["rep"])):
        L = LABELS[r["link"]][r["doi"]]
        if r["e"] not in L[0] or r["h"] not in L[1]:
            print(r["link"][:8], r["doi"], "rep", r["rep"], "got", r["e"], r["h"], "want", sorted(L[0]), sorted(L[1]), (r.get("reading") or ""))
