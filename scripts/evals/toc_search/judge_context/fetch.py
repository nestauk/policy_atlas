import sys, json, uuid
sys.path.insert(0, "scripts/evals/toc_search")
import _route  # noqa
import harness as H
h = H.Harness(0.5, H.OUT / "judge_exp_cache.pkl")
m = H.Meter() if hasattr(H, "Meter") else None
dois = """10.1136/bmj.38077.458438.ee 10.1542/peds.2005-0983 10.1016/s2213-8587(13)70051-2 10.1371/journal.pmed.1003212
10.1056/nejmoa1203034 10.1136/bmj.39342.571806.55 10.1056/nejmoa1203388 10.1136/bmj.e7492 10.1136/bmj.320.7244.1240
10.3945/ajcn.115.120022 10.1111/obr.12812 10.1017/s1368980007001231 10.1542/peds.2018-2554 10.1001/jamapediatrics.2022.1037
10.1111/ijpo.12735 10.1371/journal.pone.0031578 10.1017/s1368980019003355 10.1111/obr.13447 10.1186/s13690-025-01774-2
10.1371/journal.pmed.1003915 10.1016/j.tjnut.2022.09.002""".split()
recs = h.openalex_dois(m, dois)
titles = ["School randomised trial on prevention of excessive weight gain by discouraging students from drinking sodas",
          "Challenges in obesity epidemiology", "Obesity in children and young people: a crisis in public health"]
for t in titles:
    recs += h.openalex_search(m, t, 1)
out = {}
for r in recs:
    d = H.from_openalex(r, "openalex")
    if d: out[d.doi or d.key] = {"key": d.key, "title": d.title, "year": d.year, "abstract": d.abstract, "doi": d.doi,
        "venue": d.metadata.get("venue") or d.metadata.get("journal"), "meta_keys": list(d.metadata)}
json.dump(out, open(sys.argv[-1], "w"), indent=1)
for k, v in out.items(): print(k, v["year"], len(v["abstract"]), v["title"][:80])
print(out[next(iter(out))]["meta_keys"])
