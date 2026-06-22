# Policy Atlas v3.0 Evidence Base — agent handoff

**Status:** repo-safe pre-spec context  
**Audience:** Claude Code / coding agents producing implementation specs, rubrics, task contracts, acceptance checks, and verification plans  
**Pair with:** `policy_atlas_v3_0_evidence_base.html`, `nesta-brand-tokens.md`, and `hifi.css`  
**Do not treat this file as:** a product spec, backend schema, API contract, data model, stack decision, or implementation plan

## 1. Purpose

This handoff gives coding agents enough context to prepare the implementation artefacts for the Policy Atlas v3.0 Evidence Base workflow. The next agent pass should create specs, task contracts, rubrics, acceptance checks, and verification evidence expectations before implementation begins.

The wireframe and design assets are context for that process. They show product intent, visual direction, screen states, and interaction patterns. They should not be copied directly into production or allowed to define backend contracts.

## 2. Source order

Resolve conflicts in this order:

1. `Policy_Atlas_v3_Backend_Architecture.md` — canonical backend model, orchestration, trust/provenance, versions, collaboration, event log, and deferred seams.
2. `Policy_Atlas_v3_Backend_briefing.md` — concise product boundary and shared mental model.
3. `Policy_Atlas_v3_Evidence_Base_Capability_design.md` — canonical Evidence Base capability behaviour.
4. `policy_atlas_v3_0_evidence_base.html` — static UX reference for the v3.0 Evidence Base journey.
5. `nesta-brand-tokens.md` and `hifi.css` — design references for visual language and token cues.
6. This handoff — repo-safe constraints for spec/rubric/task-contract agents.

When there is any tension, prefer the backend architecture and Evidence Base capability design over visual shorthand in the wireframe.

## 3. Packet contents and repo role

| File | Repo role | How agents should use it | What it must not do |
|---|---|---|---|
| `Policy_Atlas_v3_0_Evidence_Base_Handoff.md` | Agent context | Use to produce specs, task contracts, rubrics, and verification plans. | Do not implement directly from it. |
| `policy_atlas_v3_0_evidence_base.html` | Static UX reference | Use for screens, layout, copy, state transitions, and product intent. | Do not ship the static HTML or infer backend schemas from it. |
| `nesta-brand-tokens.md` | Brand/design reference | Use for typography hierarchy, colour palette, buttons, navigation, icon/logo cautions, and accessibility reminders. | Do not treat as a complete design-system spec or a font/logo licence grant. |
| `hifi.css` | Static wireframe style reference | Mine CSS custom properties, button treatment, chips, nav states, spacing cues, and class names when drafting UI specs. | Do not blindly copy into production if the repo has its own token/theme/component architecture. |

### Font assets

A colleague supplied a `fonts/` folder separately. Font binaries are not included in this packet.

Do not commit, vendor, redistribute, or package font files unless the project owner has confirmed the relevant font licences, repository visibility, and deployment path. If licensing is not confirmed, implementation specs should use approved fallback font stacks and keep the UI functional without local font files.

Agents should not download replacement font files, recreate logos, or invent brand assets. Use official master artwork where required.

## 4. Workflow assumption

This handoff assumes the implementation team will use the full advanced agentic engineering workflow described in the project docs. This file does not define that workflow, prescribe repo structure, name task-contract files, or choose the order of implementation.

Use this document only as product, UX, design, and architecture context for the agents that will produce the actual specs, rubrics, task contracts, plans, and verification approach.

## 5. Product frame

Policy Atlas v3 is an evidence-led policy analysis workspace. The product is not chat and not an exported report. The product is an inspectable decision-support body: artefacts, evidence corpus, provenance, comments, versions, dependencies, and decision log.

For v3.0, the Evidence Base workflow demonstrates this loop:

```text
project landing
-> empty workspace
-> planning conversation
-> plan ready
-> build with check-in
-> Evidence Base artefact summary
-> progressive detail
-> evidence table stub
-> comments mode
-> rerun as new version
-> re-entry with catch-me-up
```

The conversation is the steering surface. The artefact and the evidence behind it are the work product.

## 6. UX surfaces covered by the wireframe

| Frame | Surface | Product purpose |
|---|---|---|
| 00 | Projects landing | Project cards, project status, paused state, create project action. |
| 01 | Empty workspace | Intent cards, composer, collapsed Library rail. |
| 02 | Planning conversation | Chat plus forming plan pane; Quick/Deep signal. |
| 03 | Plan ready | Editable plan, check-in frequency, build CTA. |
| 04 | Build + check-in | Streaming build state and thin-evidence pause. |
| 05 | Artefact summary | Evidence Base summary, factual coverage snapshot, findings, citations, gaps, references. |
| 05b | Progressive detail | Detail panels showing workings/audit trail. |
| 06 | Evidence table | Stub table showing included and screened-out evidence signals. |
| 07 | Comments mode | Anchored reactions and comments, not edits. |
08 | Rerun as new version | New immutable artefact version, change list, inline highlights, decision-log link.
| 09 | Re-entry | Library auto-open, catch-me-up, next-step suggestions. |

Wireframe content is illustrative. Do not treat example source names, source counts, findings, or R&D tax-credit details as real evidence.

## 7. Locked product decisions for spec agents

### 7.1 Quick / Deep remains in the UX

Keep the Quick search / Deep search choice. It gives the orchestrator a user-intent signal about search breadth, effort appetite, and likely scoping burden.

Spec guidance:

- Treat Quick/Deep as a search-breadth and effort signal, not as a hard backend execution mode.
- The orchestrator still infers concrete depth from user intent, evidence question, emerging plan, corpus breadth, cost/time signals, and Evidence Base capability needs.
- The compiled plan remains the execution contract.
- Check-in frequency remains a separate control.

Suggested field names for specs: `search_effort_signal`, `search_breadth_signal`, or similar. Avoid names that imply a hard public depth ladder.

### 7.2 Confidence badge and aggregate roll-ups are deferred

Do not implement an artefact-level confidence badge in v3.0. Do not add `ArtefactVersion.confidence` or any equivalent aggregate confidence field.

Use factual snapshot metadata instead:

- source count;
- study types;
- geography/date coverage;
- included and screened-out counts;
- coverage descriptors the backend can support;
- descriptive finding-strength language where backed by the annotation layer.

Allowed v3.0 wording includes stronger, thinner, contested, consistent, mixed, evidence gap, source appraisal, and coverage profile. Avoid wording that implies a calibrated cross-source confidence score.

### 7.3 Share/export is deferred

Do not implement share CTAs, export flows, read-only share links, public links, or version-pinned external export links in this v3.0 task set unless the product owner explicitly re-scopes them.

Version history, in-tool navigation, decision-log projections, and rerun version comparison remain valid areas for specification.

### 7.4 Re-entry uses shared project history, not shared transcript truth

Catch-me-up should be a projection over shared project history: uploads, comments, check-ins, version changes, reruns, locks, supersessions, and decision-log entries.

Per-user copilot continuity can appear in the UX, but the project transcript must not become the canonical shared project state. The canonical shared state is the structured project body: plan, artefacts, sources, annotations, comments, versions, and event log.

### 7.5 Detail panels are provenance/workings, not generic expansion

Collapsed content is the director's read. Expanded Detail is the analyst/audit read.

Detail panels should be grounded in provenance and synthesis state produced with the artefact: weighting decisions, disagreements, set-aside evidence, exclusion reasons, evidence gaps, contributing studies, source appraisal, and descriptive strength rationales.

Do not implement Detail as a generic LLM expansion of already-written summary prose.

### 7.6 Evidence table is a stub, but evidence states are real

The wireframe does not specify a full table UX. Do not overbuild sorting, filtering, row expansion, bulk actions, or complex exclusion views until a spec explicitly brings them into scope.

The spec should still preserve evidence states and reasons. At minimum, distinguish concepts such as:

- found/acquired;
- screen failed;
- screened out with reason;
- screened in but not selected;
- selected;
- extracted;
- cited/contributing;
- unavailable or abstract-only where relevant;
- non-evidence or unknown labels where relevant.

### 7.7 Comments are reactions, not edits

v3.0 comments mode supports anchored reactions, challenges, questions, and rerun input. It is not track changes, clearance, sign-off, or a collaborative document editor.

Rerun with comments produces a new immutable artefact version with a computed change list, inline highlights, and a decision-log entry. It must not silently mutate the prior version.

### 7.8 Library is a UI projection

The Library rail is a UI projection over the project corpus and artefact list. Do not introduce a v3.0 backend `Library` class unless a generated spec explicitly justifies it against the backend architecture.

### 7.9 Options Assessment is only a suggested next step

The re-entry screen may suggest starting an Options Assessment. That is a planning suggestion, not a hidden Options Assessment artefact and not extra Evidence Base machinery.

Evidence Base may answer broader questions through grounded narrative synthesis over its existing findings, but it must not add new schemas, structured computations, or tools that belong to future capabilities.

## 8. Backend-alignment guardrails

Specs should preserve these architectural commitments:

- projects are policy workstreams;
- artefacts are visible units of value;
- blocks are units of storage, versioning, commenting, and regeneration;
- addressable units anchor citations, claims, gaps, comments, and later eval;
- evidence sits in a shared information layer;
- citations resolve to source spans, quotes, or honest placeholders during UI prototyping;
- provenance is generated with claims, not attached after prose is written;
- catch-me-up is a projection over project events and version history;
- UI projections such as Library, evidence table rows, status cards, and version diffs are read models unless the architecture defines them as canonical objects.

## 9. Handoff boundary

This document should stop at context and constraints. It should not decide:

- implementation sequence;
- repo scaffold or directory structure;
- task-contract names;
- test strategy;
- component decomposition;
- API, schema, state-management, or event contracts;
- review or merge mechanics.

Those belong to the agentic engineering harness and the specs, rubrics, and task contracts generated from the canonical architecture and Evidence Base design.
