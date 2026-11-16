import json, os, networkx as nx
from collections import Counter
from gt_data import CASES

OUT = os.path.join(os.path.dirname(__file__), "..", "datasets")
os.makedirs(OUT, exist_ok=True)
LAYER_ORDER = ["context", "input", "activity", "output", "driver", "outcome_short", "outcome_long", "impact", "vision"]

def shape(c):
    nodes = {n[0]: n for n in c["nodes"]}
    groups = c["groups"]
    G = nx.DiGraph()
    for nid in nodes: G.add_node(nid)
    for gid in groups: G.add_node(gid)
    for nid, n in nodes.items():
        if n[2]: G.add_edge(nid, n[2], member=True)          # member -> container
    for s, t, bi, *_ in c["edges"]:
        G.add_edge(s, t)
        if bi: G.add_edge(t, s)
    # feedback loops: cycles of length > 2 that don't rely only on member edges
    # chain depth: contract containers into single units, drop lateral (bidirectional) links
    unit = {nid: (n[2] or nid) for nid, n in nodes.items()}
    for gid in groups: unit[gid] = gid
    D = nx.DiGraph()
    D.add_nodes_from(set(unit.values()))
    for s_, t_, bi, *_ in c["edges"]:
        a, b = unit[s_], unit[t_]
        rank = lambda u: LAYER_ORDER.index(groups[u][0] if u in groups else nodes[u][1])
        # two-way links count towards the chain only if they move up a layer
        if a != b and (not bi or rank(b) > rank(a)): D.add_edge(a, b)
    longest = nx.dag_longest_path(D) if nx.is_directed_acyclic_graph(D) else None
    loops = [cy for cy in nx.simple_cycles(D) if len(cy) > 1]
    layers = Counter(n[1] for n in nodes.values())
    status = Counter(e[3] for e in c["edges"])
    group_edges = sum(1 for e in c["edges"] if e[0] in groups or e[1] in groups)
    with_assump = sum(1 for e in c["edges"] if e[4])
    return dict(
        n_nodes=len(nodes), n_groups=len(groups), n_edges=len(c["edges"]),
        n_bidirectional=sum(1 for e in c["edges"] if e[2]),
        n_group_level_edges=group_edges,
        nodes_by_layer={l: layers[l] for l in LAYER_ORDER if layers[l]},
        edges_by_status=dict(status),
        edges_with_assumptions=with_assump,
        n_assumptions=len(c["assumptions"]),
        n_feedback_loops=len(loops),
        longest_directed_path=longest,
        longest_path_len=(len(longest) if longest else None),
        orphan_nodes=sorted(n for n in nodes if G.degree(n) == 0),
    )

def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
    return "\n".join(out)

all_shapes = {}
for key, c in CASES.items():
    s = shape(c); all_shapes[key] = s
    nodes = {n[0]: n for n in c["nodes"]}
    lbl = lambda i: (nodes[i][3] if i in nodes else c["groups"][i][1])
    L = []
    L.append(f"# Ground truth: {c['title']}\n")
    L.append(f"- **Case ID:** `{key}`\n- **Level:** {c['level']}\n- **Source:** {c['source']}\n- **URL:** {c['url']}\n- **Evidence basis in source:** {c['evidence_basis']}\n- **Evidence/rating scheme in source:** {c['rating_scale']}\n")
    L.append("## Task briefs for Policy Atlas\n\nUse these as the *only* input to Policy Atlas. Do not give it any other text from the source.\n")
    L.append(f"**Outcome-first brief**\n\n> {c['brief_outcome_first']}\n\n**Intervention-first brief**\n\n> {c['brief_intervention_first']}\n")
    L.append("## Shape summary\n")
    L.append(md_table(["Metric", "Value"], [
        ["Nodes", s["n_nodes"]], ["Containers (groups)", s["n_groups"]],
        ["Nodes by layer", ", ".join(f"{k}: {v}" for k, v in s["nodes_by_layer"].items())],
        ["Edges (as drawn)", s["n_edges"]], ["of which bidirectional", s["n_bidirectional"]],
        ["of which group-level (to/from a container)", s["n_group_level_edges"]],
        ["Edges by evidence status", ", ".join(f"{k}: {v}" for k, v in s["edges_by_status"].items())],
        ["Edges carrying located assumptions", s["edges_with_assumptions"]],
        ["Assumptions / risks listed", s["n_assumptions"]],
        ["Feedback loops (directed cycles, containers contracted, two-way links excluded)", s["n_feedback_loops"]],
        ["Longest causal chain (units, containers contracted)", s["longest_path_len"] if s["longest_path_len"] else "n/a (cyclic)"],
        ["Unconnected nodes", ", ".join(s["orphan_nodes"]) or "none"],
    ]))
    if s["longest_directed_path"]:
        L.append("\nLongest chain (containers contracted): " + " → ".join(f"`{p}`" for p in s["longest_directed_path"]) + "\n")
    if c["groups"]:
        L.append("\n## Containers\n")
        L.append(md_table(["ID", "Layer", "Label", "Members"], [
            [g, v[0], v[1], ", ".join(n for n in nodes if nodes[n][2] == g)] for g, v in c["groups"].items()]))
    L.append("\n## Nodes\n")
    L.append(md_table(["ID", "Layer", "Container", "Label (as in source)"], [[n[0], n[1], n[2] or "", n[3]] for n in c["nodes"]]))
    L.append("\n## Edges\n\n`status`: evidence judgement shown in the source. `confidence`: our confidence in the transcription of the arrow.\n")
    L.append(md_table(["#", "From", "To", "Dir", "Status", "Assumptions on link", "Confidence", "Note"], [
        [i + 1, e[0], e[1], "↔" if e[2] else "→", e[3], ", ".join(e[4]), e[5], e[6]] for i, e in enumerate(c["edges"])]))
    if c["assumptions"]:
        L.append("\n## Assumptions and risks\n")
        L.append(md_table(["ID", "Statement", "Location in chain", "Rating in source", "Justification"], [list(a) for a in c["assumptions"]]))
    if c["context_factors"]:
        L.append("\n## Context factors\n\n" + "\n".join(f"- {x}" for x in c["context_factors"]))
    if c["measures"]:
        L.append("\n## Indicators linked to the ToC\n")
        L.append(md_table(["Indicator", "Direct link to relative low income", "Direct link to deep material poverty"], [list(m) for m in c["measures"]]))
    if c["gaps"]:
        L.append("\n## Known gaps in this dataset\n\n" + "\n".join(f"- {g}" for g in c["gaps"]))
    payload = dict(case=key, title=c["title"], nodes=[dict(id=n[0], layer=n[1], group=n[2], label=n[3]) for n in c["nodes"]],
                   groups=[dict(id=g, layer=v[0], label=v[1]) for g, v in c["groups"].items()],
                   edges=[dict(source=e[0], target=e[1], bidirectional=e[2], status=e[3], assumptions=e[4], confidence=e[5]) for e in c["edges"]],
                   assumptions=[dict(id=a[0], text=a[1], location=a[2], rating=a[3]) for a in c["assumptions"]],
                   shape=s)
    L.append("\n## Machine-readable\n\n```json\n" + json.dumps(payload, indent=1, ensure_ascii=False) + "\n```\n")
    with open(f"{OUT}/gt_{key}.md", "w") as f: f.write("\n".join(L))

# cross-case shape table
rows = []
for k, s in all_shapes.items():
    rows.append([k, s["n_nodes"], s["n_groups"], s["n_edges"], s["n_group_level_edges"], s["n_assumptions"], s["n_feedback_loops"], s["longest_path_len"] or "cyclic",
                 ", ".join(f"{a}:{b}" for a, b in s["nodes_by_layer"].items())])
with open(os.path.join(os.path.dirname(__file__), "shape_table.md"), "w") as f:
    f.write(md_table(["Case", "Nodes", "Containers", "Edges", "Group-level edges", "Assumptions/risks", "Loops", "Longest chain", "Nodes by layer"], rows))
print(open(os.path.join(os.path.dirname(__file__), "shape_table.md")).read())
