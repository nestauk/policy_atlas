---
type: Testing rule
title: Vitest fake timers with `userEvent` hang unless the clock also advances on its own
description: '`vi.useFakeTimers()` stops the real `setTimeout(0)` that testing-library''s `userEvent` waits on, so the test never returns; `vi.useFakeTimers({ shouldAdvanceTime: true })` with `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })` lets typing proceed while a long wait (the 10-second script timeout) is still advanced by hand.'
tags: [vitest, testing-library, user-event, fake-timers, frontend, testing]
generated:
  by: process:okf-migrate
  at: 2026-11-17
sources:
  - resource: "frontend/src/views/splash/WaitlistForm.test.tsx"
    title: "`frontend/src/views/splash/WaitlistForm.test.tsx` (\"says so when the script does not load, and recovers when it does\")."
  - resource: "../tasks/064b-waf-captcha/verification.md"
    title: "[task 064b verification](../tasks/064b-waf-captcha/verification.md) \u00a7 Diff summary, deviation 6."
---

# Rule

A frontend test that needs "nothing arrives for N seconds" (the waitlist form's
CAPTCHA script timeout, 064b) and also types into fields with `userEvent` cannot use
plain `vi.useFakeTimers()`: testing-library drains its event queue with a real
`setTimeout(0)` that the fake clock never fires, and `await user.type(...)` hangs.

The working combination is

```ts
vi.useFakeTimers({ shouldAdvanceTime: true });
const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
// … type, focus …
act(() => vi.advanceTimersByTime(10_000));
```

Real time still trickles through for the small waits, the long one is advanced by hand
inside `act`, and `vi.useRealTimers()` in `afterEach` restores the clock. The test still
proves the N-second branch and the recovery after it.
