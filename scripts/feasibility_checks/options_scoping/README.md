# Feasibility-check runners — options scoping (task 035)

These scripts are the reproducible method behind the feasibility-check reports in
`docs/tasks/035-options-scoping/checks/`. They are **not product code**: they run from the command
line against corpora exported to a local data folder, call the model provider directly, and write
nothing to the product schema. The two `draft_*.py` files hold the draft extraction profiles and
prompts the checks used (lead-authored); tasks 2 and 3 build the product versions from them.

| file | what it does |
|---|---|
| `draft_profiles.py` | draft abstract profile (`os_abstract_v0`), light full-text profile (`os_light_v0`), option-grain clustering and lever-typing prompts |
| `draft_transferability.py` | draft transferability-working prompts (factor extraction, context fill) and the code-side verdict rules |
| `run_checks_2_3.py` | check 2 (abstract and light profiles, attribution trace) and check 3 (options, stability) |
| `run_checks_4_5.py` | check 4 (paired context cases) and check 5 (staging timings, reading caps) |
| `run_extra_checks.py` | after the pass-4 review: pinned light run, independence cases, no-document suggestions, grain on equal inputs, contrary evidence |
| `run_extra_check_4.py` | after the pass-4 review: a second transferability option with a real blocker, chat-to-context promotion |
| `run_fresh_neet_search.py` | a fresh rapid Evidence search on the NEET question through the agent CLI, timed end to end |

Run with the backend environment, for example:

```
uv run --project backend --env-file backend/.env python \
    scripts/feasibility_checks/options_scoping/run_checks_2_3.py abstract <corpus> --data <dir>
```

The data folder holds corpora exported read-only from staging; it carries staging document text
and stays outside the repository. Model-judged results are labelled as such in every output.
