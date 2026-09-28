import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as mutations from "../../api/mutations";
import * as queries from "../../api/queries";
import { scopingStatusLine, usePlanStart, useScopingPlanStart } from "./planStart";

vi.mock("../../api/queries", () => ({
  usePlan: vi.fn(),
  useRuns: vi.fn(),
  useTask: vi.fn(() => ({ data: undefined })),
  useLonglist: vi.fn(() => ({ data: undefined })),
}));
vi.mock("../../api/mutations", () => ({
  useStartRun: vi.fn(),
  usePatchPlan: vi.fn(),
  useConfirmBaseline: vi.fn(),
}));

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

describe("usePlanStart — the overlay clears as soon as the PATCH lands", () => {
  it("clears on PATCH success even when the run start then fails", () => {
    mockPlan();
    const { startRun } = mockMutations(
      { mutate: vi.fn((_body, handlers) => handlers.onSuccess()), isPending: false },
      {
        mutate: vi.fn((_body, handlers) =>
          handlers.onError(Object.assign(new Error("capacity"), { code: "internal" })),
        ),
        isPending: false,
      },
    );
    const onOverlayApplied = vi.fn();

    const { result } = renderHook(() =>
      usePlanStart({ taskId: "t1", overlay: DIRTY_OVERLAY, runActive: false, onOverlayApplied }),
    );
    act(() => result.current.start());

    expect(onOverlayApplied).toHaveBeenCalledTimes(1);
    expect(startRun.mutate).toHaveBeenCalledTimes(1);
    expect(result.current.startNotice).toBe("The search couldn't start. Try again.");
  });

  it("skips the PATCH and clears stale keys when the pruned body is empty", () => {
    mockPlan();
    const { patchPlan, startRun } = mockMutations({ mutate: vi.fn(), isPending: false });
    const onOverlayApplied = vi.fn();

    const { result } = renderHook(() =>
      usePlanStart({
        taskId: "t1",
        // Dirty by key count, but equal to the server plan's own value — a
        // chat turn applied the same edit meanwhile.
        overlay: { question: "What works?" },
        runActive: false,
        onOverlayApplied,
      }),
    );
    act(() => result.current.start());

    expect(patchPlan.mutate).not.toHaveBeenCalled();
    expect(startRun.mutate).toHaveBeenCalledTimes(1);
    expect(onOverlayApplied).toHaveBeenCalledTimes(1);
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

describe("useScopingPlanStart — the five start states (task 044, contract deliverable 5; owner correction 2026-09-09)", () => {
  function mockScopingPlan(overrides: { version?: number; timeBand?: string | null; baselineConfirmed?: { artefact_id: string; plan_version: number } | null } = {}) {
    vi.mocked(queries.usePlan).mockReturnValue({
      data: {
        capability: "options_scoping",
        plan: null,
        scoping: {
          ready: true,
          time_band: overrides.timeBand ?? "10-15 minutes",
          baseline_confirmed: overrides.baselineConfirmed ?? null,
          steps: [],
        },
        status: "approved",
        version: overrides.version ?? 1,
      },
    } as unknown as ReturnType<typeof queries.usePlan>);
  }

  function mockRuns(runs: unknown[]) {
    vi.mocked(queries.useRuns).mockReturnValue({ data: { data: runs } } as unknown as ReturnType<
      typeof queries.useRuns
    >);
  }

  function run(overrides: {
    status: string;
    plan_version: number;
    started_at?: string;
    artefact_id?: string | null;
  }) {
    return {
      capability_run_id: "run-1",
      started_at: overrides.started_at ?? "2026-09-01T00:00:00Z",
      artefact_id: overrides.artefact_id ?? null,
      ...overrides,
    };
  }

  function mockScopingMutations(startRun: MutationStub = { mutate: vi.fn(), isPending: false }, confirmBaseline: MutationStub = { mutate: vi.fn(), isPending: false }) {
    vi.mocked(mutations.useStartRun).mockReturnValue(startRun as unknown as ReturnType<typeof mutations.useStartRun>);
    vi.mocked(mutations.useConfirmBaseline).mockReturnValue(
      confirmBaseline as unknown as ReturnType<typeof mutations.useConfirmBaseline>,
    );
    return { startRun, confirmBaseline };
  }

  it("no baseline walk yet: one build action, with the time band", () => {
    mockScopingPlan({ timeBand: "10-15 minutes" });
    mockRuns([]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("build");
    if (result.current.kind === "build") {
      expect(result.current.timeBand).toBe("10-15 minutes");
      expect(result.current.label).toBe("Confirm and build baseline");
    }
  });

  it.each(["running", "paused"])(
    "the latest walk %s: no start actions — the gate's card and chat own the decision",
    (status) => {
      mockScopingPlan({ version: 1 });
      // Realistic per state: synthesise (and the artefact it writes) has
      // already happened by the time the walk parks on the gate; it has not
      // while still running.
      mockRuns([run({ status, plan_version: 1, artefact_id: status === "paused" ? "artefact-1" : null })]);
      mockScopingMutations();

      const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: true }));
      expect(result.current).toEqual({ kind: "none", buildingLonglist: false });
    },
  );

  it("baseline_confirmed names the current plan version: confirmed", () => {
    mockScopingPlan({ version: 1, baselineConfirmed: { artefact_id: "artefact-1", plan_version: 1 } });
    mockRuns([run({ status: "succeeded", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("confirmed");
  });

  it("the latest walk succeeded and the plan hasn't moved since: confirmed, even with no baseline_confirmed record yet (it can only have finished through the gate's Confirm, or the unattended standing default)", () => {
    mockScopingPlan({ version: 1, baselineConfirmed: null });
    mockRuns([run({ status: "succeeded", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("confirmed");
  });

  it("a degraded walk still counts as having produced a baseline for the same-version confirm", () => {
    mockScopingPlan({ version: 1 });
    mockRuns([run({ status: "degraded", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("confirmed");
  });

  it("the latest walk finished and the plan has since moved to a later version: rebuild or confirm", () => {
    mockScopingPlan({ version: 2 });
    mockRuns([run({ status: "succeeded", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("rebuild_or_confirm");
    if (result.current.kind === "rebuild_or_confirm") {
      expect(result.current.rebuild.label).toBe("Rebuild baseline");
      expect(result.current.confirm.label).toBe("Confirm plan and build longlist");
    }
  });

  it("an aborted walk (Change the plan) plus a later plan version: also rebuild or confirm", () => {
    mockScopingPlan({ version: 2 });
    mockRuns([run({ status: "aborted", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("rebuild_or_confirm");
  });

  it("an aborted walk (Change the plan) with the plan still at that version: also rebuild or confirm", () => {
    mockScopingPlan({ version: 1 });
    mockRuns([run({ status: "aborted", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("rebuild_or_confirm");
  });

  // Task 044 Phase 5.5: the state the plan document lands in straight after
  // "Change the plan" — the walk ended `aborted` and the plan is untouched,
  // so both doors are open by name.
  it("offers Rebuild baseline and Confirm plan and build longlist after Change the plan", () => {
    mockScopingPlan({ version: 1 });
    mockRuns([run({ status: "aborted", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("rebuild_or_confirm");
    if (result.current.kind === "rebuild_or_confirm") {
      expect(result.current.rebuild.label).toBe("Rebuild baseline");
      expect(result.current.rebuild.disabled).toBe(false);
      expect(result.current.confirm.label).toBe("Confirm plan and build longlist");
      expect(result.current.confirm.disabled).toBe(false);
    }
  });

  it("baseline_confirmed for a stale version does not suppress a fresh rebuild-or-confirm", () => {
    mockScopingPlan({ version: 2, baselineConfirmed: { artefact_id: "artefact-1", plan_version: 1 } });
    mockRuns([run({ status: "succeeded", plan_version: 1, artefact_id: "artefact-1" })]);
    mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("rebuild_or_confirm");
  });

  it.each(["failed", "interrupted"])(
    "a %s walk produced nothing usable: falls back to the fresh build action",
    (status) => {
      mockScopingPlan({ version: 1 });
      mockRuns([run({ status, plan_version: 1, artefact_id: null })]);
      mockScopingMutations();

      const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
      expect(result.current.kind).toBe("build");
    },
  );

  // Task 044 review, C6: a rebuild that aborted before writing must not hide
  // the earlier walk's baseline — it is still the one worth confirming.
  it("a rebuild that aborted with no artefact of its own: rebuild or confirm off the earlier baseline, and the band names its version", () => {
    mockScopingPlan({ version: 2 });
    mockRuns([
      run({ status: "succeeded", plan_version: 1, started_at: "2026-09-01T00:00:00Z", artefact_id: "artefact-X" }),
      run({ status: "aborted", plan_version: 2, started_at: "2026-09-02T00:00:00Z", artefact_id: null }),
    ]);
    const { confirmBaseline } = mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    expect(result.current.kind).toBe("rebuild_or_confirm");
    if (result.current.kind !== "rebuild_or_confirm") throw new Error("expected rebuild_or_confirm");
    expect(result.current.confirm.disabled).toBe(false);
    act(() => result.current.kind === "rebuild_or_confirm" && result.current.confirm.onConfirm());

    expect(confirmBaseline.mutate).toHaveBeenCalledWith(
      { artefact_id: "artefact-X", plan_version: 2 },
      expect.anything(),
    );
  });

  it("confirm-and-build-longlist calls confirm-baseline with the artefact id and the current plan version", () => {
    mockScopingPlan({ version: 3 });
    mockRuns([run({ status: "succeeded", plan_version: 2, artefact_id: "artefact-9" })]);
    const { confirmBaseline } = mockScopingMutations();

    const { result } = renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
    if (result.current.kind !== "rebuild_or_confirm") throw new Error("expected rebuild_or_confirm");
    act(() => result.current.kind === "rebuild_or_confirm" && result.current.confirm.onConfirm());

    expect(confirmBaseline.mutate).toHaveBeenCalledWith(
      { artefact_id: "artefact-9", plan_version: 3 },
      expect.anything(),
    );
  });
});

describe("useScopingPlanStart — the longlist's states (task 045, S13/S15)", () => {
  const confirmedAt = (version: number) => ({ artefact_id: "artefact-1", plan_version: version });

  function setup({
    version,
    baselineConfirmed = null,
    runs,
    task = {},
    longlist = null,
    longlistError = false,
    confirmBaseline = { mutate: vi.fn(), isPending: false },
  }: {
    version: number;
    baselineConfirmed?: { artefact_id: string; plan_version: number } | null;
    runs: unknown[];
    task?: { has_longlist?: boolean; active_run?: unknown };
    longlist?: { plan_version: number; options: number } | null;
    longlistError?: boolean;
    confirmBaseline?: MutationStub;
  }) {
    vi.mocked(queries.usePlan).mockReturnValue({
      data: {
        capability: "options_scoping",
        plan: null,
        scoping: { ready: true, time_band: null, baseline_confirmed: baselineConfirmed, steps: [] },
        status: "approved",
        version,
      },
    } as unknown as ReturnType<typeof queries.usePlan>);
    vi.mocked(queries.useRuns).mockReturnValue({ data: { data: runs } } as unknown as ReturnType<
      typeof queries.useRuns
    >);
    vi.mocked(queries.useTask).mockReturnValue({
      data: { capability: "options_scoping", has_longlist: false, active_run: null, ...task },
    } as unknown as ReturnType<typeof queries.useTask>);
    vi.mocked(queries.useLonglist).mockReturnValue({
      data:
        longlist === null ? null : { plan_version: longlist.plan_version, counts: { options: longlist.options } },
      isError: longlistError,
    } as unknown as ReturnType<typeof queries.useLonglist>);
    vi.mocked(mutations.useStartRun).mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<
      typeof mutations.useStartRun
    >);
    vi.mocked(mutations.useConfirmBaseline).mockReturnValue(
      confirmBaseline as unknown as ReturnType<typeof mutations.useConfirmBaseline>,
    );
    return renderHook(() => useScopingPlanStart({ taskId: "t1", runActive: false }));
  }

  const baseline = {
    capability_run_id: "run-baseline",
    status: "succeeded",
    plan_version: 1,
    started_at: "2026-09-01T00:00:00Z",
    artefact_id: "artefact-1",
  };
  const longlistWalk = {
    capability_run_id: "run-longlist",
    status: "succeeded",
    plan_version: 2,
    started_at: "2026-09-02T00:00:00Z",
    artefact_id: null,
  };
  const child = {
    capability_run_id: "run-child",
    status: "running",
    plan_version: 2,
    started_at: "2026-09-03T00:00:00Z",
    artefact_id: null,
  };

  it("longlist_built is dispatched before confirmed: a longlist for the version on screen", () => {
    const { result } = setup({
      version: 2,
      baselineConfirmed: confirmedAt(2),
      runs: [longlistWalk, baseline],
      task: { has_longlist: true },
      longlist: { plan_version: 2, options: 14 },
    });
    expect(result.current).toEqual({ kind: "longlist_built", options: 14 });
    expect(scopingStatusLine(result.current)).toBe("Longlist built · 14 options");
  });

  it("rebuild_longlist is dispatched before confirmed and rebuild_or_confirm: the plan moved on since the longlist", () => {
    const confirmBaseline = { mutate: vi.fn(), isPending: false };
    const { result } = setup({
      version: 3,
      baselineConfirmed: confirmedAt(2),
      runs: [longlistWalk, baseline],
      task: { has_longlist: true },
      longlist: { plan_version: 2, options: 14 },
      confirmBaseline,
    });
    if (result.current.kind !== "rebuild_longlist") throw new Error(`got ${result.current.kind}`);
    expect(result.current.builtFrom).toBe(2);
    expect(result.current.rebuild.label).toBe("Rebuild longlist");
    expect(scopingStatusLine(result.current)).toBe(
      "Longlist built from plan version 2 · the plan has changed",
    );
    // Rebuild longlist posts to confirm-baseline on the NEW version (P12).
    act(() => result.current.kind === "rebuild_longlist" && result.current.rebuild.onConfirm());
    expect(confirmBaseline.mutate).toHaveBeenCalledWith(
      { artefact_id: "artefact-1", plan_version: 3 },
      expect.anything(),
    );
  });

  // A13: the baseline is found among the task's own walks, never paged out
  // by option searches.
  it("reads the walks with the parentless filter", () => {
    setup({ version: 1, runs: [baseline] });
    expect(queries.useRuns).toHaveBeenLastCalledWith("t1", expect.objectContaining({ parentless: true }));
  });

  // L6: a longlist that exists but could not be read still offers Rebuild.
  it("falls back to Rebuild longlist with a notice when the longlist read fails", () => {
    const { result } = setup({
      version: 2,
      baselineConfirmed: confirmedAt(2),
      runs: [longlistWalk, baseline],
      task: { has_longlist: true },
      longlistError: true,
    });
    if (result.current.kind !== "rebuild_longlist") throw new Error(`got ${result.current.kind}`);
    expect(result.current.builtFrom).toBeNull();
    expect(result.current.notice).toBe("The longlist couldn't be loaded.");
    expect(scopingStatusLine(result.current)).toBeNull();
  });

  it("confirmed with no longlist and nothing running (a refused or failed open): Build longlist", () => {
    const { result } = setup({
      version: 2,
      baselineConfirmed: confirmedAt(2),
      runs: [{ ...longlistWalk, status: "failed" }, baseline],
    });
    if (result.current.kind !== "confirmed") throw new Error(`got ${result.current.kind}`);
    expect(result.current.build.label).toBe("Build longlist");
    expect(scopingStatusLine(result.current)).toBe("Plan confirmed · no longlist yet");
  });

  it("the longlist walk running (active_run): none, saying the longlist is being built", () => {
    const { result } = setup({
      version: 2,
      baselineConfirmed: confirmedAt(2),
      runs: [{ ...longlistWalk, status: "running" }, baseline],
      task: { active_run: { ...longlistWalk, status: "running" } },
    });
    expect(result.current).toEqual({ kind: "none", buildingLonglist: true });
    expect(scopingStatusLine(result.current)).toBe("Building the longlist");
  });

  it("a running child walk disables the start actions even when the plan moved on", () => {
    const { result } = setup({
      version: 3,
      baselineConfirmed: confirmedAt(2),
      runs: [child, longlistWalk, baseline],
      task: { has_longlist: true, active_run: child },
      longlist: { plan_version: 2, options: 14 },
    });
    expect(result.current.kind).toBe("none");
  });

  it("the baseline walk running before any confirm: none, and says nothing (the gate owns it)", () => {
    const running = { ...baseline, status: "running", artefact_id: null };
    const { result } = setup({ version: 1, runs: [running], task: { active_run: running } });
    expect(result.current).toEqual({ kind: "none", buildingLonglist: false });
    expect(scopingStatusLine(result.current)).toBeNull();
  });

  it("post-baseline, pre-longlist after a plan change stays rebuild_or_confirm", () => {
    const { result } = setup({ version: 2, runs: [baseline] });
    expect(result.current.kind).toBe("rebuild_or_confirm");
  });

  it("the line counts one option in the singular", () => {
    expect(scopingStatusLine({ kind: "longlist_built", options: 1 })).toBe("Longlist built · 1 option");
  });
});
