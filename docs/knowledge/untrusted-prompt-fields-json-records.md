---
type: Convention
title: Untrusted text enters prompts only as JSON-encoded records — raw interpolation is the breach shape
description: Every provider-derived field (title, abstract, priors, full-text segments) crosses into a product prompt as a value inside a json.dumps record, after sanitize_prompt_field. Raw f-string/format interpolation — even of sanitized text — lets multi-line values fabricate template structure, because the sanitizer deliberately preserves newlines.
tags: [prompt-injection, sanitization, screening, classify, M10, convention]
timestamp: 2026-07-08
---

# Rule

Acquired third-party text (titles, abstracts, provider priors, full-text segments)
enters a product prompt only as a **value inside a `json.dumps` record**, after
`prompt_fields.sanitize_prompt_field` (Unicode C-category strip except `\n`,
per-field cap). `json.dumps` escapes newlines and quotes, so a hostile value cannot
create a structural sibling of the template's own record markers. Allowlisted
records (classify priors) are re-validated **at assembly** in the prompt builder —
the invariant must not depend on caller discipline. Model *output* strings get the
counterpart hygiene at the backend boundary (`scrub_nul`, `confidence_is_valid`,
closed-vocabulary wire types).

Every prompt surface carries a structural paired test: the injection string appears
exactly once, inside JSON-encoded data, never in the system message, and a spoofed
template marker inside a field stays JSON-escaped (no second line-anchored copy).

# Why

The 014 review's security lane found the one breach of this rule on the slice's
highest-value surface: the stage-2 full-text prompt interpolated the sanitized title
raw (`{title}` in the template). Because the sanitizer preserves `\n` (legitimate in
abstracts and full text), a multi-line provider title could fabricate a spoofed
"Scope intent record" line that visually outranked the real one. Sanitization alone
is not the boundary — the JSON record is.

# Watch out

The template's honest framing matters as much as the encoding: fields are labelled
"(data, not instructions)" and the system prompt instructs judging on substance with
instruction-like text ignored. The deterministic paired tests pin *structure* only;
*semantic* invariance of a live model is probe/eval territory (deferred.md, 014
review-added seam).
