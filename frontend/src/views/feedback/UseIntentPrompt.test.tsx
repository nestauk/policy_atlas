import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { firstShownAt, markShown } from "../../lib/useIntent";
import { UseIntentPrompt } from "./UseIntentPrompt";

type Stored = { target_id: string; payload: { use_intent: string; change_reasons?: string[] } };
const state = vi.hoisted(() => ({
  records: [] as Stored[] | undefined,
  submit: vi.fn(),
}));
vi.mock("../../api/feedback", () => ({
  useFeedback: () => ({ data: state.records }),
  useSubmitFeedback: () => ({ mutate: state.submit, isPending: false, isError: false }),
}));
vi.mock("../../auth", () => ({ useAuth: () => ({ user: { sub: "ada" } }) }));

const BODY = {
  kind: "use_intent",
  surface: "report_key_findings",
  task_id: "task-1",
  artefact_id: "report-1",
};
const QUESTION = "Would you use this report in your work?";
const CORNER = "Would you use this report?";

/** The callbacks of the observers that the prompt made, in order. */
let observers: Array<(entries: Array<{ isIntersecting: boolean }>) => void> = [];

function renderPrompt() {
  return render(
    <>
      <section id="conclusions" />
      <UseIntentPrompt taskId="task-1" artefactId="report-1" triggerId="conclusions" />
    </>,
  );
}

/** The user scrolls down as far as the conclusions section. */
function reachConclusions() {
  act(() => observers[observers.length - 1]([{ isIntersecting: true }]));
}

beforeEach(() => {
  state.records = [];
  state.submit.mockReset();
  observers = [];
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: (entries: Array<{ isIntersecting: boolean }>) => void) {
        observers.push(callback);
      }
      observe() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UseIntentPrompt", () => {
  it("shows nothing before the user reaches the conclusions", () => {
    renderPrompt();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: CORNER })).not.toBeInTheDocument();
    expect(firstShownAt("ada", "report-1")).toBeNull();
  });

  it("opens in front of the report at the conclusions, and remembers the first show", () => {
    renderPrompt();

    reachConclusions();

    expect(screen.getByRole("dialog", { name: QUESTION })).toBeInTheDocument();
    expect(firstShownAt("ada", "report-1")).not.toBeNull();
  });

  it("opens again on a later visit when the question went unanswered", () => {
    markShown("ada", "report-1", new Date("2026-11-17T09:00:00Z"));
    renderPrompt();

    reachConclusions();

    expect(screen.getByRole("dialog", { name: QUESTION })).toBeInTheDocument();
    // The time of the first show does not move.
    expect(firstShownAt("ada", "report-1")).toBe("2026-11-17T09:00:00.000Z");
  });

  it("does nothing while the stored answer is still loading", () => {
    state.records = undefined;

    renderPrompt();

    expect(observers).toHaveLength(0);
    expect(screen.queryByRole("button", { name: CORNER })).not.toBeInTheDocument();
  });

  it("saves Yes, as it is at once, closes, and leaves the corner button", async () => {
    const user = userEvent.setup();
    renderPrompt();
    reachConclusions();

    await user.click(screen.getByRole("button", { name: "Yes, as it is" }));

    expect(state.submit).toHaveBeenCalledOnce();
    expect(state.submit).toHaveBeenCalledWith({
      ...BODY,
      use_intent: "as_is",
      shown_at: firstShownAt("ada", "report-1"),
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: CORNER })).toBeInTheDocument();
  });

  it("opens the optional follow-up after Yes, with edits, and sends the reasons", async () => {
    const user = userEvent.setup();
    renderPrompt();
    reachConclusions();

    await user.click(screen.getByRole("button", { name: "Yes, with edits" }));
    expect(state.submit).toHaveBeenCalledWith(expect.objectContaining({ use_intent: "with_edits" }));

    await user.click(screen.getByRole("button", { name: "Missing evidence" }));
    await user.click(screen.getByRole("button", { name: "Length" }));
    await user.type(screen.getByLabelText(/Anything else/), "Add the 2024 trial");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(state.submit).toHaveBeenLastCalledWith(
      expect.objectContaining({
        ...BODY,
        use_intent: "with_edits",
        change_reasons: ["missing_evidence", "length"],
        note: "Add the 2024 trial",
      }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the first answer when the follow-up is skipped or closed", async () => {
    const user = userEvent.setup();
    renderPrompt();
    reachConclusions();

    await user.click(screen.getByRole("button", { name: "No" }));
    await user.keyboard("{Escape}");

    expect(state.submit).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("records Not now as dismissed and minimises to the corner button, which opens it again", async () => {
    const user = userEvent.setup();
    renderPrompt();
    reachConclusions();

    await user.click(screen.getByRole("button", { name: "Not now" }));

    expect(state.submit).toHaveBeenCalledWith(expect.objectContaining({ use_intent: "dismissed" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: CORNER }));
    expect(screen.getByRole("dialog", { name: QUESTION })).toBeInTheDocument();

    // A second "Not now" has nothing new to record.
    await user.click(screen.getByRole("button", { name: "Not now" }));
    expect(state.submit).toHaveBeenCalledOnce();
  });

  it("treats Escape as Not now", async () => {
    const user = userEvent.setup();
    renderPrompt();
    reachConclusions();

    await user.keyboard("{Escape}");

    expect(state.submit).toHaveBeenCalledWith(expect.objectContaining({ use_intent: "dismissed" }));
    expect(screen.getByRole("button", { name: CORNER })).toBeInTheDocument();
  });

  it("does not open by itself after Not now on an earlier visit", () => {
    state.records = [{ target_id: "report-1", payload: { use_intent: "dismissed" } }];

    renderPrompt();

    expect(observers).toHaveLength(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: CORNER })).toBeInTheDocument();
  });

  it("shows a stored answer when it is opened again, and closing keeps it", async () => {
    state.records = [
      { target_id: "report-2", payload: { use_intent: "no" } },
      {
        target_id: "report-1",
        payload: { use_intent: "with_edits", change_reasons: ["missing_evidence"] },
      },
    ];
    const user = userEvent.setup();
    renderPrompt();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: CORNER }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "Recorded as “Yes, with edits · Missing evidence”.",
    );
    expect(screen.queryByRole("button", { name: "Not now" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(state.submit).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
