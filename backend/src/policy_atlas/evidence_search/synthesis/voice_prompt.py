"""Shared report-voice principles (task 034 S7).

One block, rendered into the section writer, the key-findings pass and the
summariser. P9 (short titles) lives only on the sections proposer. Cite
principles by number so a refine-replay can tag them; do not restate a
principle on a surface that already includes this block.

This module's filename contains ``prompt`` so ``scripts/prompt_hash_guard.py``
pins it.
"""

VOICE_PRINCIPLES = """\
Voice (P1–P8, P10) — one register for every report surface:
- P1 Claim, then warrant. Lead with the finding; number, population and
  source follow. Do not open on a count or a certainty band.
- P2 Name the world, not the reading of the files. Write about programmes,
  populations and outcomes. Never tour the corpus. Banned phrases include
  "a high-level reading of the documents", "in the material read here",
  "this body of work", "Across the documents", "Inference:".
- P3 One idea per sentence. A second fact gets a second sentence.
- P4 Contrast is the argument. Structure by what differs (who, where,
  compared with what), not by cataloguing settings.
- P6 Numbers do work. One figure, where it decides something. Counts and
  certainty bands are never the paragraph's spine.
- P7 Caveats attach to the claim; they do not replace it. "The mechanism
  is settled; the outcome is not" is the shape.
- P8 Still descriptive. Never "so adopt X". The reader judges.
- P10 Expand acronyms at first use ("short-term rental accommodation
  (STRA)"); the abbreviation may stand alone after that.
"""
