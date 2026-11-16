import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { setPlanEdits, usePlanEdits } from "./planEdits";

describe("plan edits in the store (task 058, N20)", () => {
  it("keeps a task's edits when the view that made them unmounts and mounts again", () => {
    const first = renderHook(() => usePlanEdits("task-a"));
    act(() => first.result.current[1]({ search_effort: "deep" }));
    expect(first.result.current[0]).toEqual({ search_effort: "deep" });
    // Leaving the Agent tab unmounts the view; coming back mounts a new one.
    first.unmount();
    const again = renderHook(() => usePlanEdits("task-a"));
    expect(again.result.current[0]).toEqual({ search_effort: "deep" });
    act(() => again.result.current[1]({}));
    expect(again.result.current[0]).toEqual({});
  });

  it("keeps each task's edits apart", () => {
    setPlanEdits("task-b", { geography: "UK" });
    const other = renderHook(() => usePlanEdits("task-c"));
    expect(other.result.current[0]).toEqual({});
    setPlanEdits("task-b", {});
  });
});
