import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RunStreamState } from "../../store/types";
import { RunPane } from "./RunPane";

// `RunPane` is not currently mounted by any route (`JourneyPane` renders
// directly wherever the live analysis pane lives) — this test exists so the
// task 033 phase 10c / rubric 37 owner gate on its two "Start a fresh run"
// triggers is exercised component-by-component regardless, as a defensive
// gate for whenever it (or its `terminal` section) is wired back in.
const mutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useStartRun: () => ({ mutate, isPending: false }),
}));
vi.mock("../../api/queries", () => ({
  usePlan: () => ({ data: undefined }),
  useFunnel: () => ({ data: undefined }),
  useCoverage: () => ({ data: undefined }),
  useGroups: () => ({ data: undefined }),
  useLandscape: () => ({ data: undefined }),
}));
// `JourneyPane` is a heavy read pane unrelated to this gate — stubbed to
// just render the `terminal` slot RunPane builds and owns.
vi.mock("./journey/JourneyPane", () => ({
  JourneyPane: ({ terminal }: { terminal?: React.ReactNode }) => <div>{terminal}</div>,
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function baseStream(status: "interrupted" | "failed"): RunStreamState {
  return {
    connectionStatus: "connected",
    lastSequence: 0,
    appliedTypesAtLastSequence: [],
    run: {
      id: "run-1",
      status: status as never,
      startedAt: "2026-07-28T10:00:00Z",
      endedAt: "2026-07-28T10:10:00Z",
    },
    runs: {},
    stages: [],
    pendingCheckIn: null,
    decisions: [],
    plan: null,
    project: {},
    liveSections: {},
    liveness: {},
  } as unknown as RunStreamState;
}

describe("RunPane — non-owner read-only (task 033 phase 10c, contract § 11 / rubric 37)", () => {
  it("owner: shows Start a fresh run after an interruption", () => {
    render(<RunPane projectId={PROJECT_ID} stream={baseStream("interrupted")} isOwner />);
    expect(screen.getByRole("button", { name: "Start a fresh run" })).toBeInTheDocument();
  });

  it("non-owner: hides Start a fresh run after an interruption", () => {
    render(<RunPane projectId={PROJECT_ID} stream={baseStream("interrupted")} isOwner={false} />);
    expect(screen.queryByRole("button", { name: "Start a fresh run" })).not.toBeInTheDocument();
  });

  it("owner: shows Start a fresh run after a failure", () => {
    render(<RunPane projectId={PROJECT_ID} stream={baseStream("failed")} isOwner />);
    expect(screen.getByRole("button", { name: "Start a fresh run" })).toBeInTheDocument();
    expect(screen.getByText(/You can start a fresh run\./)).toBeInTheDocument();
  });

  it("non-owner: hides Start a fresh run after a failure, without inviting a click that would 403", () => {
    render(<RunPane projectId={PROJECT_ID} stream={baseStream("failed")} isOwner={false} />);
    expect(screen.queryByRole("button", { name: "Start a fresh run" })).not.toBeInTheDocument();
    expect(screen.queryByText(/You can start a fresh run\./)).not.toBeInTheDocument();
    expect(screen.getByText(/Whatever completed is kept and readable\./)).toBeInTheDocument();
  });
});
