---
name: policy-options
description: >
  Generate policy options (strategic directions + concrete interventions) from a Policy
  Atlas project's evidence base. Trigger when the user says "policy options for <project>",
  "draft policy options", "what could we do about <topic>" and a matching project exists,
  or "/policy-options". Reads findings, citations and sources from the local Postgres via
  the postgres-local MCP; writes a single markdown file with inline evidence citations
  and source URLs. Read-only against the DB. Not for exploratory chat — for producing a
  cited artefact from a specific project's existing evidence.
---

# Policy options from a project's evidence base

One skill, one artefact: a markdown file of policy directions and interventions
grounded in the findings already extracted for a named project.

## Prerequisites

Requires the `postgres-local` MCP server registered against the local Policy Atlas
database. One-off setup lives in
[`docs/agentic-ops/environment.md`](../../../docs/agentic-ops/environment.md) → *Claude
Code MCP (optional)*. If the MCP is missing the skill will fail on its first query.

## Inputs

- **Project name** (substring, case-insensitive). If ambiguous, list matches and ask.
- Optional: **focus** (a sub-question or population/setting filter). If not given, use the project's `question`.

## Output

Single file: `.outputs/policy-options/<project-slug>-<YYYY-MM-DD>.md`

`.outputs/` is gitignored — these artefacts are local, not versioned.

Slug: lowercased project name, non-alphanumerics → `-`, truncated to 60 chars.
Date: today, from the current-date context, not from the DB.

Never overwrite. If the file exists, append `-v2`, `-v3`, ….

## Read-only rule

Only `SELECT` queries. No `INSERT`/`UPDATE`/`DELETE`/`ALTER`/`CREATE`/`DROP`/`TRUNCATE`.
The MCP role has write privileges — the discipline is on this skill.

## Procedure

1. **Resolve project.** `SELECT project_id, name, question FROM project WHERE name ILIKE '%<term>%' AND archived_at IS NULL ORDER BY updated_at DESC;`  If >1 match, list them and ask which. If 0, stop and say so.

2. **Check prior synthesis.** `SELECT synthesis_result_id, blocks, counts, created_at FROM synthesis_result WHERE project_id = :pid ORDER BY created_at DESC LIMIT 1;`  If present, read `blocks` as prior art — do not paraphrase it wholesale; use it to steer which directions are already well-supported vs. under-explored.

3. **Pull findings.**
   - IOFs (what works): `SELECT finding_id, intervention, outcome, population, comparator, effect_direction, estimate_level, study_design, causality_by_design, statistics, setting, study_geography, grounding FROM intervention_outcome_finding WHERE project_id = :pid AND is_primary = TRUE;`
   - ICFs (how to do it): `SELECT finding_id, context_type, claim, intervention, population, setting, level, resource_requirements, workforce_requirements, claim_level, claim_basis, study_design, grounding FROM implementation_context_finding WHERE project_id = :pid;`

4. **Resolve evidence to URLs.** For each finding used, pick one `grounding[].chunk_id`, then:
   `SELECT s.source_locator, s.metadata->>'title' AS title, s.metadata->>'year' AS year FROM chunk c JOIN source_snapshot s ON s.source_snapshot_id = c.source_snapshot_id WHERE c.chunk_id = :cid;`
   Cache the mapping — many findings will share a source.

5. **Draft the markdown** using the template below. Weave IOFs (effect) with ICFs (implementation) where they share `intervention`. Prefer findings with stronger `causality_by_design` / `estimate_level`; downweight prevalence-only.

6. **Show a preview** of directions + intervention titles to the user before writing to disk. On approval, write the file and report the path.

## Voice and style

- Write in British English.
- Clear, direct, accessible. Familiar language, short to medium sentences, logical structure.
- Prefer concrete wording over jargon, abstraction or institutional language. Explain technical terms when they are necessary. Do not assume specialist knowledge unless the audience is described as expert.
- Concise, but preserve important meaning, evidence, qualifications and uncertainty. Cut repetition and filler, not useful detail. Do not make claims sound more certain than the source supports.
- Confident, calm, human tone. Avoid bureaucratic, academic, promotional or overly enthusiastic phrasing.
- Be specific about people, organisations, places and policies rather than using vague references.
- Inclusive; avoid idioms, acronyms or cultural shorthand that may be unclear internationally. Spell out acronyms on first use.
- Restrained formatting. Paragraphs by default; lists only when they make information easier to understand. Sentence case, minimal capitalisation, light punctuation. No unnecessary headings, emphasis or rhetorical questions.
- Use bold selectively to aid scanning — typically a short lead-in phrase at the start of a bullet, or a key term the reader is looking for. One bold per bullet, none in body paragraphs unless a single term genuinely needs to stand out.
- Answer directly. No long introduction, no repetition of the question, no explanation of the writing process. Match length to the task.

## Evidence discipline (borrowed from the codebase)

- Reuse existing strength labels verbatim — `causality_by_design`, `estimate_level`, `claim_level`, `study_design`. Do not invent new ratings.
- One quoted phrase per intervention max — pull from `finding.grounding[].quote` when it clarifies. No paraphrase-quoting.
- Never assert an effect direction the finding doesn't state. If `effect_direction` is null or mixed, say "mixed" and cite both sides.
- ICF `level` (individual/organisational/system) belongs in the implementation note, not the effect line.
- Gaps section is required even if short. "Evidence not found for X" is a first-class output.

## Template

```markdown
# Policy options — <project name>

_Question:_ <project.question>
_Focus:_ <focus or "all">
_Evidence base:_ <N> intervention–outcome findings, <M> implementation-context findings, <K> sources. Generated <YYYY-MM-DD>.

## Directions

### D1. <short title>
<2–3 sentences: the strategic thrust and why the evidence points here.> [F1] [F4] [F7]

### D2. …

## Interventions

### I1. <intervention name>
- **Effect:** <effect_direction> on <outcome> in <population/setting>. Evidence: <study_design>, <causality_by_design>, <estimate_level>. [F2]
- **Implementation:** <one line from the matching ICF — resources, workforce, level>. [F9]
- **Caveats:** <any statistics gaps, single-study, geography mismatch>.

### I2. …

## Gaps

- <what the evidence base does not cover — geography, population, outcome, design>

## References

- **F1.** <intervention/claim text, trimmed> — [<title, year>](<source_locator>)
- **F2.** …
```

## Failure modes to avoid

- **Silent overreach.** If the project has <5 findings total, say so and stop; do not fabricate directions.
- **Wrong project.** Always echo the resolved project name + id in the preview before writing.
- **Broken links.** If `source_locator` is null, mark the reference `[no URL — source_snapshot_id: <uuid>]` rather than dropping the citation.
- **Non-English quotes.** Grounding quotes can be in the source's original language. Keep them verbatim; add a short English gloss in brackets if needed.

## Not in scope (v1)

- Persisting policy options back to the DB — this is a markdown-only artefact.
- Cross-project synthesis.
- Cost/feasibility estimates beyond what findings explicitly state.
- Any write to the DB.
