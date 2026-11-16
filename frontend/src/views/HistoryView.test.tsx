import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { HistoryView } from "./HistoryView";

const TASK_ID = "11111111-1111-1111-1111-111111111111";

vi.mock("../api/queries", () => ({
  useTask: vi.fn(),
  useDecisions: vi.fn(),
  useTaskAgentTurns: vi.fn(),
  useToc: vi.fn(() => ({ data: null })),
  useTocHistory: vi.fn(() => ({ data: [] })),
}));

vi.mock("../api/mutations", () => ({
  useTocEdit: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));

type Read = { data?: unknown; isPending?: boolean; isError?: boolean; error?: unknown; refetch?: () => void };

function read({ data, isPending = false, isError = false, error = null, refetch = vi.fn() }: Read) {
  return { data: data === undefined ? undefined : { data }, isPending, isError, error, refetch };
}

function mockReads(decisions: Read, turns: Read, task: Record<string, unknown> = {}) {
  vi.mocked(queries.useTask).mockReturnValue({
    data: { task_id: TASK_ID, name: "A task", is_owner: true, owner_display: "Ada Lovelace", capability: "evidence_search", ...task },
  } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useDecisions).mockReturnValue(read(decisions) as unknown as ReturnType<typeof queries.useDecisions>);
  vi.mocked(queries.useTaskAgentTurns).mockReturnValue(
    read(turns) as unknown as ReturnType<typeof queries.useTaskAgentTurns>,
  );
}

function renderHistory() {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/history`]}>
      <Routes>
        <Route path="/tasks/:taskId/history" element={<HistoryView />} />
      </Routes>
    </MemoryRouter>,
  );
}

const RUN = "70000000-0000-4000-8000-000000000001";
const runEvent = (sequence: number, at: string, kind: string, summary: string, detail: Record<string, unknown> = {}) => ({
  sequence,
  occurred_at: at,
  kind,
  summary,
  detail,
  capability_run_id: RUN,
});


describe("HistoryView — readable with the Task, not scoped to the caller (task 033 phase 10b, rubric 39)", () => {
  it("renders decisions and task_agent turns for a caller who does not own the Task, naming the owner", () => {
    // The contract struck rev 2.0's "scopes to the caller": any caller who
    // can read the task sees its decisions and task_agent turns, not just
    // its owner. Round 10 (H6): the colleague reads the owner's name, in
    // the server's sentence and in the turns.
    mockReads(
      {
        data: [
          {
            sequence: 1,
            occurred_at: "2026-07-21T09:31:10Z",
            kind: "plan.approved",
            summary: "Ada Lovelace approved the plan.",
            decided_by: "user",
            detail: { actor: "owner-1" },
          },
        ],
      },
      { data: [{ turn_index: 0, created_at: "2026-07-21T09:30:00Z", user_message: "What works?", status: "completed" }] },
      { is_owner: false },
    );

    renderHistory();

    expect(screen.getByText("Ada Lovelace approved the plan.")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace asked: “What works?”")).toBeInTheDocument();
    expect(screen.queryByText(/^You /)).not.toBeInTheDocument();
    expect(screen.queryByText(/couldn't be loaded/)).not.toBeInTheDocument();
  });
});

describe("HistoryView — round 10", () => {
  it("names the page for a screen reader and groups rows under a day heading with absolute times", () => {
    mockReads({ data: [] }, { data: [{ turn_index: 0, created_at: "2026-11-03T09:02:00Z", user_message: "Q?", status: "completed" }] });
    renderHistory();
    expect(screen.getByRole("heading", { level: 1, name: "History" })).toBeInTheDocument();
    const list = screen.getByRole("list", { name: /2026|Today|Yesterday/ });
    const time = within(list).getByText(/^\d\d:\d\d$/);
    expect(time).toHaveAttribute("datetime", "2026-11-03T09:02:00Z");
    // No category chips (H5): the row is the time and the sentence.
    expect(within(list).getByRole("listitem")).toHaveTextContent(/^\d\d:\d\dYou asked: “Q\?”$/);
  });

  it("shows only the skeleton while either read is pending, never half a list (H8)", () => {
    mockReads({ isPending: true }, { data: [{ turn_index: 0, created_at: "2026-11-03T09:02:00Z", user_message: "Q?", status: "completed" }] });
    renderHistory();
    expect(screen.getByLabelText("Loading the history")).toBeInTheDocument();
    expect(screen.queryByText(/You asked/)).not.toBeInTheDocument();
  });

  it("shows only the error in the list's frame with Try again when a read fails (H8)", async () => {
    const refetch = vi.fn();
    mockReads(
      { isError: true, error: { error: { code: "internal" } }, refetch },
      { data: [{ turn_index: 0, created_at: "2026-11-03T09:02:00Z", user_message: "Q?", status: "completed" }], refetch },
    );
    renderHistory();
    expect(screen.getByRole("alert")).toHaveTextContent("The history couldn't be loaded.");
    expect(screen.queryByText(/You asked/)).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(refetch).toHaveBeenCalledTimes(2);
  });

  it("shows the empty state in the list's frame", () => {
    mockReads({ data: [] }, { data: [] });
    renderHistory();
    expect(screen.getByRole("status")).toHaveTextContent("Nothing yet.Your question and what follows will be listed here.");
  });

  it("makes only rows with details disclosures; the rest are plain list items, not disabled buttons (H9)", async () => {
    mockReads(
      { data: [] },
      {
        data: [
          { turn_index: 0, created_at: "2026-11-03T09:02:00Z", user_message: "Q?", reply: "Here is how I read it.", status: "completed" },
          { turn_index: 1, created_at: "2026-11-03T09:03:00Z", user_message: "Thanks", status: "completed" },
        ],
      },
    );
    renderHistory();
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveAttribute("aria-expanded", "false");
    expect(buttons[0]).not.toBeDisabled();
    expect(screen.getByText("You wrote: “Thanks”").closest("button")).toBeNull();
    await userEvent.setup().click(buttons[0]);
    expect(buttons[0]).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Here is how I read it.")).toBeInTheDocument();
  });

  it("folds a run to its outcome line behind Show steps / Hide steps (H7)", async () => {
    mockReads(
      {
        data: [
          runEvent(1, "2026-11-03T09:12:00Z", "run.opened", "Opened an evidence-search run."),
          runEvent(2, "2026-11-03T09:19:00Z", "component.completed", "Completed screening: 118 of 312 relevant."),
          runEvent(3, "2026-11-03T09:48:00Z", "run.finished", "Finished the run."),
        ],
      },
      { data: [] },
    );
    renderHistory();
    expect(screen.getByText("Ran the evidence search · 36 min")).toBeInTheDocument();
    expect(screen.queryByText("Completed screening: 118 of 312 relevant.")).not.toBeInTheDocument();
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", { name: "Show steps" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAccessibleName("Hide steps");
    expect(within(screen.getByRole("list", { name: "Run steps" })).getAllByRole("listitem")).toHaveLength(3);
    await user.click(toggle);
    expect(screen.queryByText("Completed screening: 118 of 312 relevant.")).not.toBeInTheDocument();
  });

  it("puts the red mark before a failure, beside its words (H5)", () => {
    mockReads({ data: [] }, { data: [{ turn_index: 1, created_at: "2026-11-03T09:02:00Z", user_message: "Why?", status: "failed" }] });
    const { container } = renderHistory();
    expect(screen.getByText(/This didn't send\./)).toBeInTheDocument();
    expect(container.querySelector('[data-tone="failed"]')).not.toBeNull();
  });
});
