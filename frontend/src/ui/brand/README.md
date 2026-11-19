# Brand

The shared design pieces of the web app: buttons, cards, selects, the icons, the fold mark,
list frames, labels, and the shared words and tones for evidence strength, Task status and
references.

## Rules

- Define a shared piece once, here, and import it. A view must not make its own copy of a tone,
  a label or an icon. [DESIGN.md](../../../../DESIGN.md) § Components, "Defined once", lists
  which file owns what.
- The design tokens (colours, type sizes, spacing) are in `src/index.css`. Use the named tokens,
  not your own values.
- `cn.ts` joins class names. Use it, so that Tailwind type sizes and colours do not cancel each
  other.

## Commands

From `frontend/`: `pnpm test` runs the unit tests, which include the tests in this folder.
