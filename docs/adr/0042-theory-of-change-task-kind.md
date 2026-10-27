# ADR 0042 — A third task kind: theory of change

- **Status:** Accepted — 2026-10-26 (Karlis Kanders, owner, task 054 plan gate: "Approve!").
- **Date:** 2026-10-26
- **Task:** [054-toc-integration](../tasks/054-toc-integration/contract.md)
- **Builds on:** [ADR 0037](0037-options-scoping-task-kind-links-and-baseline-gate.md) (a task
  kind, its links and the capability registry) ·
  [ADR 0039](0039-options-scoping-longlist-option-searches-and-option-records.md) (searches as
  child walks) · [ADR 0041](0041-bedrock-inference-route-and-model-route-file.md) (the model
  route file).

## Context

Policy teams use theories of change to say how an intervention is meant to bring about a change
and what that depends on. HM Treasury's Magenta Book treats one as the first step of any
evaluation. Building one by hand is slow, and users asked for two things a tool could give them:
evidence they can audit, and a clear difference between a step with no evidence and a step with
evidence against it.

Policy Atlas already has most of what such a tool needs: a Task Agent, the Evidence search
spine (search, screen, classify, appraise), the option-search child walks of Options scoping,
a quote verifier and a rerank backend. It has nothing that drafts a causal graph, judges a
document against one causal step, or chooses between pathways. The capability spec
(`docs/specs/capabilities/theory-of-change/`) holds the product design and every owner ruling;
the task 054 contract fixes the build. This record keeps the consequential decisions.

## Decisions

1. **A third task kind, `theory_of_change`, through the capability registry** (contract C1, C3,
   C12). One theory per task, edited in place; every change is a History event. Two walks: a
   draft walk (draft or import) and a check walk (item searches, then screen, classify,
   appraise, discover, merge, judge, choose, summarise). The check starts when the draft lands.
   The steering lattice is empty. A new scope purpose `toc` marks the main walk; item searches
   reuse the `targeted` scope with `acquire_only`, on their own pool, through a
   capability-neutral child search kept inside `runtime/option_search.py` (C2).
2. **Links carry the evidence; boxes are described** (C4, C5, W4, W14). Only links are searched
   and graded. Each link answers two questions, *did it work where it was tried* and *will it
   hold here*, each with its own grade; its conditions hold the Magenta Book's assumptions.
   Boxes show a description, result criteria, case studies and indicators. This follows
   theory-based evaluation (White 2009; Mayne 2015, 2017) and the distinction between "it
   worked there" and "it will work here" (Cartwright and Hardie 2012).
3. **The grade is a banding, on purpose** (C4). Strong, medium, weak or no evidence found, from
   one pure function over appraisal scores, computed on read and never stored. Options scoping
   does not band evidence in v1 without its own eval; theory of change does, because users need
   a per-step reading, and tunes the rule with evals E2, E2b and E7. Web pages never raise a
   grade above weak. A modelling study the judge marks robust counts as score 3, enough for
   medium, never strong; the shared appraisal rubric is unchanged.
4. **Generated sentences are checked** (C20). Evidence sentences and box descriptions may cite
   only their own item's judged documents with verified quotes, or a box's case studies. Code
   replaces any sentence that fails.
5. **Web search opens the open-web seam, for this capability only** (C7). OpenAI's hosted web
   search tool, through a typed `web_search` table per route with an address allow-list and no
   fallback. On the Bedrock route, Bedrock's `bedrock-runtime` endpoint does not offer hosted
   tools, so **only the web search calls** go to Bedrock's `bedrock-mantle` endpoint in
   us-east-1; every other call stays in London. Cited pages are fetched with the hardened live
   fetcher, frozen as untrusted text, capped in number per call and per walk, and reach prompts
   only through the field sanitiser and a fence. The seam stays deferred for every other
   capability.
6. **A private uploads bucket** (C8). Imported theory files go to a new private, encrypted,
   TLS-only S3 bucket, retained by policy, readable only through the task's own authenticated
   routes. Objects are removed only by the operator script that hard-deletes tasks; a retention
   rule is a deferred seam.
7. **Policy Atlas may change user work, but flags it, and edits never trigger checks** (T1, C6,
   C9, C19). Merge and choose may merge, reword or set aside user work; each change keeps the
   user's prior version, and the Task Agent offers Undo per change and Undo all. A user edit
   only marks a link *check pending*; the user keeps the evidence or asks for a minimal check
   (a same-meaning call, then a re-judge of the documents already found). Every writer uses row
   revisions and compare-and-apply, so a background step never overwrites a newer user edit.
8. **A link from an option to a theory** (C13, C14). `task_link.source_option_id`, with a
   composite foreign key to the source task's option, accepted only when the target is a theory
   of change. The option's documents are shared, not copied.
9. **A server setting guards creation** (C15). `POLICY_ATLAS_THEORY_OF_CHANGE=1` must be on for
   the backend to create the task kind, so a merge to `dev` exposes nothing by API alone. It is
   off in both environments. `DELETE` joins the API's allowed CORS methods for the graph edit
   routes.
10. **An iterative build with a lighter review stack** (C18; owner: "implement a simple version
    … then iterate a bit, and then build from there"). A simple core first, tried and tuned on
    real topics, then six increments. Fast checks on every commit; the full suite at build open,
    at each migration and at each increment's end; `/code-review` and the security lane on each
    increment; the contract verifier, a Codex adversarial pass and `/simplify` once before the
    merge to `dev`. Three schema revisions, one per increment that needs one.

## Amendment, 2026-10-27: web pages by publisher

Decision 3's blanket rule ("web pages never raise a grade above weak") is replaced (owner: "If it
comes from Eval Task Force, for example, it could be quite strong"). Every web page is classified
and appraised like any document. A page from a trusted publisher (a configured list: government,
the Evaluation Task Force, regulators, statistics and audit bodies, What Works Centres,
universities, journals) counts by its appraisal score; any other page keeps the old cap. Task 054
contract C23.

## Consequences

- Positive: a policy team gets a Magenta Book theory of change whose every step shows, in
  plain sentences with sources, whether it worked elsewhere and whether it is likely to hold
  here. Most of the machinery is reused, and Evidence search and Options scoping behaviour is
  unchanged.
- Cost: web search is billed per call and needs a long-term Bedrock key valid in us-east-1 on
  the Bedrock route. The banding rule is a judgement that the evals must keep testing.
- Risk: a US endpoint for web search calls on the Bedrock route; untrusted page text in prompts
  (fenced and sanitised); user files in a new bucket (private, access-checked); a lighter review
  stack (offset by a full review before the merge to `dev`).

## Rollback

Turn the server setting off, so no new theories can be created. Each schema revision's
downgrade refuses only while its own data exists: the option link column while any link uses
it, the uploads table while any upload exists, and the core tables while any theory-of-change
task or run exists. The remedy is the operator script that hard-deletes those tasks, their walks
and their bucket objects; the downgrades then drop what they added and narrow the four widened
constraints. The bucket is retained by policy and emptied by the same script; deleting it is a
separate infrastructure change. Deploy the previous image.
