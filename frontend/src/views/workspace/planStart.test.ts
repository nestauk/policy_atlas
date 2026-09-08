import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as mutations from "../../api/mutations";
import * as queries from "../../api/queries";
import { usePlanStart } from "./planStart";

vi.mock("../../api/queries", () => ({ usePlan: vi.fn() }));
vi.mock("../../api/mutations", () => ({ useStartRun: vi.fn(), usePatchPlan: vi.fn() }));

type MutationStub = { mutate: ReturnType<typeof vi.fn>; isPending: boolean };

function mockPlan() {
  vi.mocked(queries.usePlan).mockReturnValue({
    data: { plan: { question: "What works?" }, status: "approved", version: 1 },
  } as unknown as ReturnType<typeof queries.usePlan>);
}

function mockMutations(patchPlan: MutationStub, startRun: MutationStub = { mutate: vi.fn(), isPending: false }) {
  vi.mocked(mutations.useStartRun).mockReturnValue(startRun as unknown as ReturnType<typeof mutations.useStartRun>);
  vi.mocked(mutations.usePatchPlan).mockReturnValue(patchPlan as unknown as ReturnType<typeof mutations.usePatchPlan>);
  return { patchPlan, startRun };
}

// A stable reference (as `WorkspaceView`'s `useState<PlanOverlay>` gives the
// real hook) — an inline object literal in the `renderHook` callback would be
// a fresh reference every render, which the render-phase "clear the notice
// once the overlay changes" check would (correctly) treat as a new edit.
const DIRTY_OVERLAY = { geography: "Nowhereland" };

describe("usePlanStart — apply-failure copy", () => {
  it("prefers the API's error message over generic copy", () => {
    mockPlan();
    const { startRun } = mockMutations({
      mutate: vi.fn((_body, handlers) =>
        handlers.onError(Object.assign(new Error("Geography must be a known ISO country."), { code: "internal" })),
      ),
      isPending: false,
    });

    const { result } = renderHook(() =>
      usePlanStart({ taskId: "t1", overlay: DIRTY_OVERLAY, runActive: false }),
    );
    act(() => result.current.start());

    expect(result.current.startNotice).toBe(
      "Those plan edits couldn't be saved: Geography must be a known ISO country.",
    );
    expect(startRun.mutate).not.toHaveBeenCalled();
  });

  it("falls back to generic copy with no message, and never claims a start-without-them path", () => {
    mockPlan();
    mockMutations({
      mutate: vi.fn((_body, handlers) => handlers.onError(Object.assign(new Error(""), { code: "internal" }))),
      isPending: false,
    });

    const { result } = renderHook(() =>
      usePlanStart({ taskId: "t1", overlay: DIRTY_OVERLAY, runActive: false }),
    );
    act(() => result.current.start());

    expect(result.current.startNotice).toBe("The plan edits couldn't be applied. Try again.");
    expect(result.current.startNotice).not.toMatch(/start without/i);
  });
});

describe("usePlanStart — Discard edits and start", () => {
  it("clears the overlay and starts against the last saved plan without a PATCH", () => {
    mockPlan();
    const { patchPlan, startRun } = mockMutations({ mutate: vi.fn(), isPending: false });
    const onDiscardOverlay = vi.fn();

    const { result } = renderHook(() =>
      usePlanStart({
        taskId: "t1",
        overlay: DIRTY_OVERLAY,
        runActive: false,
        onDiscardOverlay,
      }),
    );
    act(() => result.current.discardAndStart());

    expect(onDiscardOverlay).toHaveBeenCalledTimes(1);
    expect(patchPlan.mutate).not.toHaveBeenCalled();
    expect(startRun.mutate).toHaveBeenCalledTimes(1);
  });
});

describe("usePlanStart — the notice clears when the overlay changes", () => {
  it("drops a stale failure notice once the overlay is edited", () => {
    mockPlan();
    mockMutations({
      mutate: vi.fn((_body, handlers) => handlers.onError(Object.assign(new Error("Bad geography."), { code: "internal" }))),
      isPending: false,
    });

    const { result, rerender } = renderHook(
      ({ overlay }) => usePlanStart({ taskId: "t1", overlay, runActive: false }),
      { initialProps: { overlay: DIRTY_OVERLAY } },
    );
    act(() => result.current.start());
    expect(result.current.startNotice).not.toBeNull();

    rerender({ overlay: { geography: "UK" } });
    expect(result.current.startNotice).toBeNull();
  });
});
