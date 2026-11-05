import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as queries from "../../api/queries";
import * as store from "../../store";
import { createInitialRunStreamState } from "../../store";
import { LonglistBuilding } from "./LonglistView";

vi.mock("../../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof queries>();
  return { ...actual, useTask: vi.fn(), useOptions: vi.fn(), useLonglist: vi.fn(), usePlan: vi.fn() };
});
vi.mock("../../store", async (importOriginal) => {
  const actual = await importOriginal<typeof store>();
  return { ...actual, useRunStream: vi.fn() };
});

const TASK = "11111111-1111-1111-1111-111111111111";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

function renderBuilding(rows: unknown[], stage: { key: string; label: string; activity?: string } | null) {
  vi.mocked(queries.useTask).mockReturnValue({
    data: { capability: "options_scoping", active_run: { stage: stage?.key ?? null, stage_label: stage?.label ?? null } },
  } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useOptions).mockReturnValue({ data: { options: rows } } as unknown as ReturnType<typeof queries.useOptions>);
  vi.mocked(queries.useLonglist).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.useLonglist>);
  const state = createInitialRunStreamState();
  if (stage !== null) {
    state.run = { id: "w", status: "running", startedAt: "2026-11-05T10:00:00Z" };
    state.stages = [{ stage: stage.key as never, label: stage.label, status: "started", startedAt: "2026-11-05T10:00:00Z" }];
    if (stage.activity) {
      state.liveness = { [stage.key]: { activity: stage.activity, heartbeat: false, dropped: 0, occurredAt: new Date().toISOString() } };
    }
  }
  vi.mocked(store.useRunStream).mockReturnValue(state);
  return render(
    <MemoryRouter>
      <LonglistBuilding taskId={TASK} />
    </MemoryRouter>,
  );
}

const row = (n: number, patch: Record<string, unknown> = {}) => ({
  option_id: id(n),
  name: `Option ${n}`,
  description: "",
  origin: "suggested",
  state: "included",
  merged_into_option_id: null,
  search_status: "queued",
  found: null,
  ...patch,
});

describe("LonglistBuilding (task 058, N24)", () => {
  it("titles the page Longlist with the stage line and per-row searches", () => {
    renderBuilding(
      [row(1, { search_status: "searched", found: 312, origin: "from_evidence_search" }), row(2, { search_status: "searching" }), row(3, { origin: "added_by_you" })],
      { key: "option_searches", label: "Searching for each option", activity: "1 of 3 searches done · 312 sources so far" },
    );
    const { container } = { container: document.body };
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/^Longlist$/);
    expect(container.textContent).toContain("Searching for each option · 1 of 3 searches done · 312 sources so far");
    expect(container.textContent).toContain("Searched · 312 found");
    expect(screen.getByText("Searching")).toBeInTheDocument();
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByText("from your report")).toBeInTheDocument();
    expect(screen.getByText("added by you")).toBeInTheDocument();
  });

  it("shows the fold note while clustering and a folded row under its parent", () => {
    renderBuilding([row(1), row(2, { merged_into_option_id: id(1) }), row(3, { origin: "clustered" })], {
      key: "longlist",
      label: "Clustering into options",
      activity: "options may be folded together or added",
    });
    expect(screen.getByText("Clustering into options · options may be folded together or added")).toBeInTheDocument();
    expect(screen.getByText("Folded into Option 1")).toBeInTheDocument();
    expect(screen.getByText("found in the evidence")).toBeInTheDocument();
  });

  it("has no stage line once the walk has no stage, and no qualifier word anywhere", () => {
    const { container } = renderBuilding([row(1)], null);
    expect(container.textContent).not.toMatch(/provisional|draft|preliminary|tentative/i);
    expect(screen.queryByText(/·/)).toBeNull();
  });
});
