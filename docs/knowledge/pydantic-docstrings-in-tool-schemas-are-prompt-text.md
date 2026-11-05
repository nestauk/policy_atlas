---
type: Prompting
title: A pydantic class docstring in a tool schema is prompt text the model reads
description: Pydantic turns class and field docstrings into JSON-schema descriptions; a wire model used as a tool or structured-output schema is therefore prompt text and belongs under the prompt hash guard.
tags: [prompting, prompt-guard, pydantic, tools, "056"]
timestamp: 2026-11-02
---

# Rule

A pydantic model that is sent to the provider as a tool definition or a structured-output
schema is a prompt surface: its class docstring and `Field(description=...)` strings become
the JSON schema's `description` values, and the model reads them. Such models live in a
pinned prompt module (or are listed in `scripts/prompt_hash_guard.py`'s extra files), and a
docstring edit on one is a deliberate re-pin with its diff recorded, exactly like a prompt
edit. The same holds for any plain string the code hands the model as data (a retry reason,
a format hint): if the model reads it, it is pinned.

# Why

Task 056 moved the section writer's prompt text into `synthesis/section_prompt.py` (D11) and
found that the wire models for the five section tools, with their docstrings, were part of
what the writer saw; they moved with it. The review stack then found two retry sentences
(`SUMMARY_FORMAT_RETRY_REASON`) sent to the summariser as `previous_attempt.judge_reason` sitting
in the unpinned `synthesise.py`; they moved to `summary_prompts.py`. The test that proved it:
the extraction fingerprint (`test_call_site_kwargs.py`) embeds the schema, so a docstring edit
changes it.
