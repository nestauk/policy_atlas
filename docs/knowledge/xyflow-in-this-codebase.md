---
type: Integration quirk
title: xyflow (React Flow) in this codebase: scope edge styles under .react-flow, stub DOMMatrix for vitest, and put keyboard handling on the flow, not the node
description: xyflow's own stylesheet overrides edge stroke rules unless ours are scoped under .react-flow; jsdom lacks DOMMatrix so the vitest setup stubs it; the focusable element is xyflow's wrapper around a node, so Enter and Space are handled by a keydown on ReactFlow reading the focused element's data-id.
tags: [frontend, xyflow, canvas, accessibility, vitest, task-054]
timestamp: 2026-11-05
---

# Facts

- **Edge styles.** `@xyflow/react`'s stylesheet sets edge stroke properties; a rule in
  `index.css` wins only when scoped under `.react-flow` (for example `.react-flow .toc-edge--…`).
- **Tests.** jsdom has no `DOMMatrix`; `frontend/src/test/setup.ts` stubs it, or every canvas
  test fails at mount.
- **Keyboard.** A node's focusable element is xyflow's wrapper, not the component inside it, so
  a key handler on the node component never fires. Handle `keydown` on `<ReactFlow>` and read
  the focused element's `data-id`; make edges `focusable` and give each an `aria-label`.
- No layout library: the canvas computes its own columns and right-angled connections
  (`frontend/src/views/toc/tocModel.ts`).

# Citations

- `frontend/src/views/toc/TocCanvas.tsx`; `frontend/src/index.css` (`.toc-edge--*`);
  `frontend/src/test/setup.ts`
- [054 verification § Review handoff](../tasks/054-toc-integration/verification.md) and
  § Review findings (the design lane, 2026-11-05)
