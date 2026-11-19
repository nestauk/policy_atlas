import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { firstShownAt, markShown } from "../../lib/useIntent";
import { UseIntentCard } from "./UseIntentCard";

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

function renderCard() {
  return render(<UseIntentCard taskId="task-1" artefactId="report-1" />);
}

beforeEach(() => {
  state.records = [];
  state.submit.mockReset();
});

describe("UseIntentCard", () => {
  it("asks on the first open and remembers that it was shown", () => {
    renderCard();

    expect(screen.getByText("Would you use this report in your work?")).toBeInTheDocument();
    expect(firstShownAt("ada", "report-1")).not.toBeNull();
  });

  it("does not ask on a later open when the question went unanswered", () => {
    markShown("ada", "report-1", new Date("2026-11-17T09:00:00Z"));

    const view = renderCard();

    expect(view.container).toBeEmptyDOMElement();
  });

  it("shows nothing while the stored answer is still loading", () => {
    state.records = undefined;

    const view = renderCard();

    expect(view.container).toBeEmptyDOMElement();
    expect(firstShownAt("ada", "report-1")).toBeNull();
  });

  it("saves Yes, as it is at once, with the time of the first show", async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole("button", { name: "Yes, as it is" }));

    expect(state.submit).toHaveBeenCalledWith({
      ...BODY,
      use_intent: "as_is",
      shown_at: firstShownAt("ada", "report-1"),
    });
    expect(screen.queryByText(/What would need to change/)).not.toBeInTheDocument();
  });

  it("opens the optional follow-up after Yes, with edits, and sends the reasons", async () => {
    const user = userEvent.setup();
    renderCard();

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
  });

  it("keeps the first answer when the follow-up is skipped", async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole("button", { name: "No" }));
    await user.click(screen.getByRole("button", { name: "Skip" }));

    expect(state.submit).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Skip" })).not.toBeInTheDocument();
  });

  it("records Not now as dismissed, and a dismissed report shows nothing", async () => {
    const user = userEvent.setup();
    const view = renderCard();

    await user.click(screen.getByRole("button", { name: "Not now" }));
    expect(state.submit).toHaveBeenCalledWith(expect.objectContaining({ use_intent: "dismissed" }));

    view.unmount();
    state.records = [{ target_id: "report-1", payload: { use_intent: "dismissed" } }];
    expect(renderCard().container).toBeEmptyDOMElement();
  });

  it("collapses an answer to one line, which change reopens", async () => {
    state.records = [
      { target_id: "report-2", payload: { use_intent: "no" } },
      {
        target_id: "report-1",
        payload: { use_intent: "with_edits", change_reasons: ["missing_evidence"] },
      },
    ];
    const user = userEvent.setup();
    renderCard();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Thanks — recorded as “Yes, with edits · Missing evidence”.",
    );
    await user.click(screen.getByRole("button", { name: "change" }));

    expect(screen.getByRole("button", { name: "Yes, as it is" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Not now" })).not.toBeInTheDocument();
  });
});
