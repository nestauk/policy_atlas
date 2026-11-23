# Radix primitives

The overlay and tab parts of the web app, built on Radix UI. Radix gives the keyboard, focus
and accessibility behaviour. The look is ours.

- `Popover.tsx`, `Sheet.tsx` (a slide-over panel, on the Radix Dialog), `Tabs.tsx`,
  `Toast.tsx`, `Tooltip.tsx`.
- `menu.ts`: the style of a menu row.
- `portal.ts`: where an overlay mounts. It mounts inside a full-screen element while one is
  open, and in the page body at other times.

## Rules

- Use these parts. Do not import `@radix-ui/*` in a view.
- Every sheet and popover closes on a press outside it (`outsidePress.test.tsx`).
- The look follows [DESIGN.md](../../../../DESIGN.md).

## Commands

From `frontend/`: `pnpm test` runs the unit tests.
