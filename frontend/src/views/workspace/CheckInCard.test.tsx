import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import type { CheckInOut, StageEntry } from "../../store/types";
import { ToastProvider } from "../../ui/radix/Toast";
import { CheckInCard } from "./CheckInCard";
import { presentCheckInRender } from "./checkInPresentation";

type CheckInOption = components["schemas"]["CheckInOption"];

const mutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useAnswerCheckIn: () => ({ mutate, isPending: false }),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";
const CHECK_IN_ID = "22222222-2222-2222-2222-222222222222";

function baseCheckIn(overrides: Partial<CheckInOut> = {}): CheckInOut {
  return {
    boundary: "after_component",
    check_in_id: CHECK_IN_ID,
    component: "screen",
    created_at: "2026-07-21T10:00:00Z",
    kind: "pause",
    options: [],
    render: "Screening paused for review.",
    rerun_component: null,
    segment_reentry_allowed: false,
    sequence: 3,
    stage: "screen",
    status: "pending",
    triggers: [],
    bundle: null,
    ...overrides,
  };
}

function option(overrides: Partial<CheckInOption> = {}): CheckInOption {
  return {
    id: "some-option",
    label: "Some option",
    description: "",
    requires_user_input: false,
    suggested: false,
    why: null,
    endorsement: null,
    ...overrides,
  };
}

function renderCard(checkIn: CheckInOut, stages: StageEntry[] = [], isOwner = true, compact = false) {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <CheckInCard taskId={TASK_ID} checkIn={checkIn} stages={stages} isOwner={isOwner} compact={compact} />
      </ToastProvider>
    </MemoryRouter>,
  );
}

/** The search review check-in after searching and screening (annex scene 12). */
function searchReview(overrides: Partial<CheckInOut> = {}): CheckInOut {
  return baseCheckIn({
    kind: "steer_point",
    stage: "acquire",
    component: "acquire",
    render: "Does this look right before I assess the sources?\n312 sources · 118 relevant",
    options: [
      option({ id: "deepen_search", label: "Search deeper", description: "One more search on the thin themes." }),
      option({
        id: "continue",
        label: "Looks right, assess these",
        description: "Screening starts on what came back.",
        suggested: true,
        why: "Coverage matches the plan.",
      }),
      option({ id: "rescope_filters", label: "Change the search scope", description: "Opens a line to say what to change.", requires_user_input: true }),
      option({ id: "abort", label: "Stop the run", description: "Abort the remaining walk." }),
    ],
    ...overrides,
  });
}

describe("CheckInCard — the card's shape (task 058, N19; annex scene 12)", () => {
  it("titles the card with the question, then one facts line, and no eyebrow or chip", () => {
    renderCard(searchReview(), [{ stage: "acquire", label: "Searching and screening", status: "completed" }] as StageEntry[]);
    expect(screen.getByRole("heading", { name: "Does this look right before I assess the sources?" })).toBeInTheDocument();
    expect(screen.getByTestId("check-in-facts")).toHaveTextContent("312 sources · 118 relevant · Sources →");
    expect(screen.getByRole("link", { name: "Sources →" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources`);
    expect(screen.queryByText("Waiting on your input")).toBeNull();
    expect(screen.queryByText("Searching and screening")).toBeNull();
  });

  it("is a radio list with the suggested option first, its why under it, nothing chosen", () => {
    renderCard(searchReview());
    const radios = screen.getAllByRole("radio");
    expect(radios.map((radio) => radio.getAttribute("data-option-id"))).toEqual([
      "continue",
      "deepen_search",
      "rescope_filters",
    ]);
    expect(radios[0]).toHaveTextContent("Coverage matches the plan.");
    expect(radios[1]).not.toHaveTextContent("Coverage matches the plan.");
    expect(radios.every((radio) => radio.getAttribute("aria-checked") === "false")).toBe(true);
    expect(screen.queryByText(/Recommended/)).toBeNull();
  });

  it("has one stop: the Stop the run link, not a duplicate option", async () => {
    mutate.mockClear();
    const user = userEvent.setup();
    renderCard(searchReview());
    expect(screen.getAllByText("Stop the run")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Stop the run" }));
    expect(mutate.mock.calls[0][0]).toEqual({ checkInId: CHECK_IN_ID, body: { kind: "abort" } });
  });

  it("keeps Or steer in your own words as a closed disclosure", () => {
    renderCard(searchReview());
    const disclosure = screen.getByText("Or steer in your own words", { selector: "summary" }).closest("details");
    expect(disclosure).not.toBeNull();
    expect(disclosure).not.toHaveAttribute("open");
  });

  it("sends a choice at once", async () => {
    mutate.mockClear();
    const user = userEvent.setup();
    renderCard(searchReview());
    await user.click(screen.getByRole("radio", { name: /Looks right, assess these/ }));
    expect(mutate.mock.calls[0][0]).toEqual({
      checkInId: CHECK_IN_ID,
      body: { kind: "option", option_id: "continue", params: null },
    });
  });

  it("glows once, in orange, as it arrives (D15)", () => {
    const { rerender } = renderCard(searchReview());
    const card = screen.getByTestId("check-in-card");
    expect(card.className).toContain("anim-glow");
    expect(card.className).toContain("border-l-orange");
    rerender(
      <MemoryRouter>
        <ToastProvider>
          <CheckInCard taskId={TASK_ID} checkIn={searchReview()} stages={[]} isOwner />
        </ToastProvider>
      </MemoryRouter>,
    );
    // The same element: a re-render does not remount it, so the one-shot
    // animation does not play again.
    expect(screen.getByTestId("check-in-card")).toBe(card);
  });

  it("drops the facts line at the sidebar's compact width", () => {
    renderCard(searchReview(), [], true, true);
    expect(screen.queryByTestId("check-in-facts")).toBeNull();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
  });
});

describe("CheckInCard — option parameters", () => {
  it("submits change_mode with new_mode from the mode select, not a made-up { value }", async () => {
    mutate.mockClear();
    const user = userEvent.setup();
    renderCard(
      baseCheckIn({
        options: [
          option({
            id: "change_mode",
            label: "Change how often I check in",
            description: "Pick a new steering cadence.",
            requires_user_input: true,
          }),
        ],
      }),
    );

    await user.click(screen.getByRole("radio", { name: /Change how often I check in/ }));
    await user.selectOptions(screen.getByLabelText("New steering mode"), "minimal");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(mutate).toHaveBeenCalledOnce();
    expect(mutate.mock.calls[0][0]).toMatchObject({
      checkInId: CHECK_IN_ID,
      body: { kind: "option", option_id: "change_mode", params: { new_mode: "minimal" } },
    });
  });

  it("an option that needs words opens a line inside the card that compiles like free text", async () => {
    mutate.mockClear();
    const user = userEvent.setup();
    renderCard(
      baseCheckIn({
        options: [
          option({
            id: "add-local-context",
            label: "Add local context",
            description: "Tell us which local programme to prioritise.",
            requires_user_input: true,
          }),
        ],
      }),
    );

    await user.click(screen.getByRole("radio", { name: /Add local context/ }));
    expect(mutate).not.toHaveBeenCalled();
    const line = screen.getByRole("textbox", { name: "Add local context" });
    expect(line).toHaveFocus();
    await user.type(line, "Tower Hamlets family hubs");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(mutate.mock.calls[0][0]).toEqual({
      checkInId: CHECK_IN_ID,
      body: { kind: "free_text", text: "Add local context: Tower Hamlets family hubs" },
    });
  });
});

describe("CheckInCard — deterministic completion render", () => {
  it("presents a machine completion render with locked labels and keeps its raw record disclosed", () => {
    const render = "characterise: succeeded | wall_clock=12.7s | counts: appraised=12, skipped=2, internal=9";
    // The label is the stage frame's, in the server's words (task 058, N17).
    const stages: StageEntry[] = [{ stage: "characterise", label: "Mapping", status: "completed", startedAt: "" }];
    expect(presentCheckInRender(render, "characterise", [])).toBeNull();
    const presented = presentCheckInRender(render, "characterise", stages);

    expect(presented).toEqual({
      stageLabel: "Mapping",
      status: "completed",
      seconds: "12.7",
      counts: [
        { label: "Sources quality-appraised", value: "12" },
        { label: "Skipped", value: "2" },
      ],
      question: null,
    });
    // Task 058 (N19): a render whose first line is the question titles the card with it.
    const asked = presentCheckInRender(`Does the map look right before I shortlist?\n${render}`, "characterise", stages);
    expect(asked?.question).toBe("Does the map look right before I shortlist?");
    expect(asked?.counts).toHaveLength(2);
    renderCard(baseCheckIn({ render, stage: "characterise" }), stages);
    // No question on a machine render: the stage label is the title and the
    // counts are the facts line.
    expect(screen.getByRole("heading", { name: "Mapping" })).toBeInTheDocument();
    expect(screen.queryByText(/Completed in/)).toBeNull();
    expect(screen.getByTestId("check-in-facts")).toHaveTextContent("Sources quality-appraised 12 · Skipped 2");
    expect(screen.queryByText(/Internal/)).toBeNull();
    expect(screen.queryByText("Technical detail")).toBeNull();
  });

  it("keeps a non-machine render as scrubbed prose", () => {
    const render = "Review the evidence base before deciding.";
    expect(presentCheckInRender(render, "screen", [])).toBeNull();
    renderCard(baseCheckIn({ render }));
    expect(screen.getByText(render)).toBeInTheDocument();
    expect(screen.queryByText("Technical detail")).toBeNull();
  });
});

describe("CheckInCard — toast on failure (027 strand 14)", () => {
  it("shows an error toast alongside the inline notice when the answer mutation errors", async () => {
    mutate.mockReset();
    mutate.mockImplementation(
      (_vars: unknown, options?: { onError?: (error: unknown) => void }) => {
        options?.onError?.({ code: "already_answered" });
      },
    );
    const user = userEvent.setup();
    renderCard(baseCheckIn());

    await user.click(screen.getByRole("button", { name: "Stop the run" }));

    // Toast complements the inline notice — both carry the same message,
    // rendered in two places (the toast surfaces even off-screen).
    expect(await screen.findByText("Check-in update failed")).toBeInTheDocument();
    const messages = screen.getAllByText(
      "This check-in has already been answered. Refresh to see the recorded decision.",
    );
    expect(messages).toHaveLength(2);
    expect(screen.getByRole("alert")).toHaveTextContent("already been answered");
  });
});

describe("CheckInCard — non-owner read-only (task 033 phase 10c, contract § 11 / rubric 37)", () => {
  it("renders nothing for a non-owner — steering stays owner-scoped, the same invariant as the check-in banner", () => {
    // `ToastProvider`'s own portal region is the only thing in the tree —
    // the card itself renders null, not an empty wrapper.
    renderCard(
      baseCheckIn({
        options: [option({ id: "continue", label: "Continue" })],
      }),
      [],
      false,
    );
    expect(screen.queryByRole("radio", { name: /Continue/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop the run" })).not.toBeInTheDocument();
  });
});

/** Task 044 Phase 5.5: the options-scoping baseline gate's card (D12). */
describe("CheckInCard — the baseline gate", () => {
  function gateCheckIn(bundle: Record<string, unknown> | null) {
    return baseCheckIn({
      kind: "baseline_confirm",
      stage: "synthesise",
      component: "synthesise",
      render: "Confirm the plan against the baseline",
      bundle,
      options: [
        option({
          id: "confirm_plan",
          label: "Confirm plan and build longlist",
          description: "Accept the plan as it stands and go on to the longlist.",
        }),
        option({
          id: "change_plan",
          label: "Change the plan",
          description: "Stop here and edit the plan; the baseline you have read is kept.",
        }),
      ],
    });
  }

  const bundle = {
    key_assumption: "Careers advice reaches those still in school, not those who have left.",
    settings: {
      target_unit: "16-24 year-olds at risk of becoming NEET",
      where: "United Kingdom",
      outcomes: ["NEET rate at 6 months", "Sustained employment at 12 months"],
      depth: "standard",
      risk_appetite: "Proven options only",
    },
  };

  it("quotes the key assumption and the plan settings under the gate heading", () => {
    renderCard(gateCheckIn(bundle));

    expect(
      screen.getByRole("heading", { name: "Confirm the plan against the baseline" }),
    ).toBeInTheDocument();
    expect(screen.getByText(bundle.key_assumption)).toBeInTheDocument();
    expect(screen.getByText("Who or what should change")).toBeInTheDocument();
    expect(screen.getByText("16-24 year-olds at risk of becoming NEET")).toBeInTheDocument();
    expect(screen.getByText("United Kingdom")).toBeInTheDocument();
    expect(
      screen.getByText("NEET rate at 6 months · Sustained employment at 12 months"),
    ).toBeInTheDocument();
    expect(screen.getByText("Standard scoping")).toBeInTheDocument();
    // The baseline gate's facts include the plan's risk appetite (N19).
    expect(screen.getByText("Risk appetite")).toBeInTheDocument();
    expect(screen.getByText("Proven options only")).toBeInTheDocument();
  });

  it("offers exactly the two server-supplied options and nothing else", () => {
    renderCard(gateCheckIn(bundle));

    expect(screen.getAllByRole("radio").map((radio) => radio.getAttribute("data-option-id"))).toEqual([
      "confirm_plan",
      "change_plan",
    ]);
    // The gate is a decision, not a steer: no free-text compile, no abort.
    expect(screen.queryByRole("button", { name: "Compile" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop the run" })).not.toBeInTheDocument();
    expect(screen.getByTestId("check-in-card").className).toContain("anim-glow");
  });

  it("posts Change the plan as an ordinary card option", async () => {
    mutate.mockClear();
    const user = userEvent.setup();
    renderCard(gateCheckIn(bundle));

    await user.click(screen.getByRole("radio", { name: /Change the plan/ }));

    expect(mutate.mock.calls[0][0]).toEqual({
      checkInId: CHECK_IN_ID,
      body: { kind: "option", option_id: "change_plan", params: null },
    });
  });

  it("states an absent key assumption rather than quoting nothing", () => {
    renderCard(gateCheckIn({ key_assumption: "   ", settings: {} }));

    expect(screen.getByText("The baseline records no key assumption.")).toBeInTheDocument();
  });
});
