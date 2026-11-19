---
paths:
  - "frontend/src/api/**"
  - "frontend/src/store/**"
---

# Frontend live stream: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- `narrowSseFrame` (`frontend/src/api/sseFrame.ts`) drops any frame whose type is not in
  the hand-kept `SSE_FRAME_TYPES` list, before the reducer sees it. The type check makes
  you add a reducer case for a new frame type but not a list entry, so a missing entry
  means the live view never updates while every test passes.
