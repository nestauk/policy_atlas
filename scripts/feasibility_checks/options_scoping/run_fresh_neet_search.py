"""Run 7 (approximation) — one fresh rapid Evidence search on the NEET question through the
sanctioned live-check vehicle (the runtime agent CLI), with a scripted console, timing the whole
path. Also gives check 3 a real NEET corpus (the machinery half of run 1).

    uv run --project backend --env-file backend/.env python \
        scripts/feasibility_checks/options_scoping/run_fresh_neet_search.py --data <dir>

Substrate discipline (docs/knowledge/run-component-driver-for-scoped-live-checks.md): the dev
database only; DATABASE_URL is forced after the env file loads. This is an approximation of a
scoping rapid path: the Evidence search's synthesise stands in for synthesise(profile), asked at
plan time for profile-shaped sections. It is labelled as such wherever its numbers are used.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ["DATABASE_URL"] = "postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas"

from policy_atlas.runtime import agent as agent_mod  # noqa: E402

INTENT = (
    "A rapid evidence search: what interventions reduce the number of young people aged 16 to 24 who are "
    "not in education, employment or training (NEET) in England? Rapid depth. Steering mode: unattended — "
    "proceed with your defaults at every check-in. Shape the synthesis like an option profile with these "
    "sections: how the main interventions work and their main failure modes; what the interventions are made "
    "of; evidence for and against; how they vary in practice; case studies; what it would take to implement; "
    "what was searched and not searched."
)


class ScriptedConsole:
    """Answers the planning conversation deterministically and records every exchange with timestamps."""

    def __init__(self, log: list[dict]):
        self.log = log; self.turns = 0

    def prompt(self, message: str) -> str:
        self.turns += 1
        low = message.lower()
        if "describe the evidence review" in low:
            reply = INTENT
        elif "approve" in low and "abandon" in low:
            reply = "approve"
        elif self.turns > 14:
            reply = "abandon"
        else:
            reply = ("Proceed with your proposal as drafted: rapid depth, unattended steering with your defaults, "
                     "the profile-shaped sections I listed. No further changes.")
        self.log.append({"t": time.time(), "prompt": message[:300], "reply": reply[:200]})
        print(f"[console] {message[:120]!r} -> {reply[:60]!r}", flush=True)
        return reply

    def print(self, message: str) -> None:
        self.log.append({"t": time.time(), "print": message[:400]})
        print(f"[agent] {message[:160]}", flush=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); a = ap.parse_args()
    out = Path(a.data) / "out"; out.mkdir(exist_ok=True)
    log: list[dict] = []
    t0 = time.time()
    result = agent_mod.main(console=ScriptedConsole(log))
    t1 = time.time()
    rec = {"label": "run 7 approximation — fresh rapid Evidence search on the NEET question via the agent CLI; synthesise stands in for synthesise(profile)",
           "exit_code": result.exit_code, "task_id": str(result.task_id) if result.task_id else None, "evidence_scope_id": str(result.evidence_scope_id) if result.evidence_scope_id else None,
           "status": getattr(result.outcome, "status", None), "artefact_present": result.artefact_present, "wall_s_total": round(t1 - t0, 1),
           "plan_approved_at_s": round(next((e["t"] for e in log if e.get("reply") == "approve"), t0) - t0, 1), "console_turns": len([e for e in log if "prompt" in e]), "log": log}
    json.dump(rec, open(out / "run7_neet.json", "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in rec.items() if k != "log"}, indent=1, default=str))


if __name__ == "__main__":
    main()
