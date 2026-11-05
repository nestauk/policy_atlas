import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  PartCard,
  type PlanStep,
  type TaskAgentTurn,
  optionNeedsWords,
  planSteps,
  chipDisplayLabel,
  chipEditMessage,
  confirmMessage,
  confirmTarget,
  derivePartStates, settledSummary } from "./PartCard";

function turn(
  index: number,
  message: string,
  part: TaskAgentTurn["part"] = null,
): TaskAgentTurn {
  return {
    turn_index: index,
    client_turn_id: `00000000-0000-0000-0000-00000000000${index}`,
    user_message: message,
    reply: "Reply",
    suggestions: [],
    part,
    status: "completed",
    created_at: `2026-07-28T10:0${index}:00Z`,
    completed_at: `2026-07-28T10:0${index}:01Z`,
  };
}

function proposal(id: string, overrides: Partial<NonNullable<TaskAgentTurn["part"]>> = {}) {
  return {
    id,
    step_label: `Plan · ${id}`,
    title: `Proposal for ${id}`,
    body: null,
    chips: null,
    options: [
      { id: "confirm", label: "Looks right", sub: null, primary: true, reason: null },
      { id: "change", label: "Change it", sub: null, primary: false, reason: null },
    ],
    ...overrides,
  };
}

describe("confirm marker grammar", () => {
  it("round-trips through confirmMessage → confirmTarget", () => {
    const part = proposal("scope");
    const message = confirmMessage(part, part.options[0]);
    expect(confirmTarget(message)).toEqual({ partId: "scope", optionId: "confirm" });
  });

  it("ignores ordinary messages and mid-message markers", () => {
    expect(confirmTarget("make it UK only")).toBeNull();
    expect(confirmTarget("[confirm part=scope option=confirm]\nplus more text")).toBeNull();
  });
});

describe("derivePartStates (F34 rehydration rules)", () => {
  it("latest proposal per part id wins; confirms bind to the proposal current when sent", () => {
    const turns = [
      turn(1, "opening", proposal("question")),
      turn(2, "That's my question\n\n[confirm part=question option=confirm]", proposal("scope")),
      turn(3, "uk only please", proposal("scope")), // re-proposes scope
      turn(4, "Looks right\n\n[confirm part=scope option=confirm]"),
    ];
    const states = derivePartStates(turns);
    expect(states.get(1)).toEqual(expect.objectContaining({ live: true, confirmedOptionId: "confirm" }));
    // The superseded scope proposal is inert and holds no confirm.
    expect(states.get(2)).toEqual(expect.objectContaining({ live: false, confirmedOptionId: null }));
    // The re-proposal is live and took turn 4's confirm.
    expect(states.get(3)).toEqual(expect.objectContaining({ live: true, confirmedOptionId: "confirm" }));
  });

  it("a confirm referencing a part never proposed binds nothing", () => {
    const turns = [turn(1, "opening", proposal("question")), turn(2, "[confirm part=scope option=confirm]")];
    expect(derivePartStates(turns).get(1)).toEqual(expect.objectContaining({ live: true, confirmedOptionId: null }));
  });
});

describe("chipEditMessage", () => {
  it("batches staged edits into one plain-language turn", () => {
    expect(
      chipEditMessage([
        { kind: "change", label: "No date limit", detail: "from 2016-01-01, no upper date bound" },
        { kind: "remove", label: "Comparators: US" },
        { kind: "add", label: "exclude opinion pieces", detail: "exclude opinion pieces" },
      ]),
    ).toBe(
      "Update the scope:\n" +
        '- Change "No date limit" to: from 2016-01-01, no upper date bound.\n' +
        '- Remove "Comparators: US".\n' +
        "- Add: exclude opinion pieces.",
    );
  });
});

describe("PartCard (task 058, N18; annex scene 11)", () => {
  function renderPart(
    part: NonNullable<TaskAgentTurn["part"]>,
    state = { live: true, answered: false, answer: null, confirmedOptionId: null as string | null },
    onSend = vi.fn(),
    extra: { partName?: string; steps?: PlanStep[] } = {},
  ) {
    render(<PartCard part={part} state={state} disabled={false} onSend={onSend} {...extra} />);
    return onSend;
  }

  it("is a radio list in the planner's order, each option with its one sentence, nothing chosen, no Recommended", () => {
    renderPart(
      proposal("question", {
        options: [
          { id: "refine", label: "Narrow it", sub: "Tell me what to add or leave out.", primary: false, reason: null },
          { id: "confirm", label: "That's my question", sub: null, primary: true, reason: "It names the outcome, the group and the setting." },
        ],
      }),
    );
    const radios = screen.getAllByRole("radio");
    // The planner's order stands (owner, polish round 3: fastest to slowest
    // for thoroughness); the primary is not moved first and its reason is
    // not shown.
    expect(radios.map((radio) => radio.getAttribute("data-option-id"))).toEqual(["refine", "confirm"]);
    expect(radios[1]).toHaveTextContent("That's my question");
    expect(radios[1]).not.toHaveTextContent("It names the outcome, the group and the setting.");
    expect(radios[0]).toHaveTextContent("Tell me what to add or leave out.");
    expect(radios.every((radio) => radio.getAttribute("aria-checked") === "false")).toBe(true);
    expect(screen.queryByText(/Recommended/)).toBeNull();
  });

  it("sends the canned confirm for a choice", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(proposal("scope"));
    await user.click(screen.getByRole("radio", { name: /Looks right/ }));
    expect(onSend).toHaveBeenCalledWith("Looks right\n\n[confirm part=scope option=confirm]");
  });

  it("an option that needs words opens an input in the card with its own Send, never the composer", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(proposal("scope"));
    await user.click(screen.getByRole("radio", { name: /Change it/ }));
    expect(onSend).not.toHaveBeenCalled();
    const input = screen.getByRole("textbox", { name: "Change it" });
    expect(input).toHaveFocus();
    expect(input).toHaveAttribute("placeholder", "What should change?");
    await user.type(input, "Exclude pre-2010 studies");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("Change it: Exclude pre-2010 studies");
    // The line closes once sent.
    expect(screen.queryByRole("textbox", { name: "Change it" })).toBeNull();
  });

  it("renders every option as a choice when none is primary (task 044: scoping depth has no default, ruling 25)", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(
      proposal("depth", {
        options: [
          { id: "rapid", label: "Rapid scoping", sub: null, primary: false, reason: null },
          { id: "standard", label: "Standard scoping", sub: null, primary: false, reason: null },
        ],
      }),
    );
    expect(screen.getByRole("radio", { name: /Rapid scoping/ }).dataset.partOption).toBe("secondary");
    expect(screen.getByRole("radio", { name: /Standard scoping/ }).dataset.partOption).toBe("secondary");
    await user.click(screen.getByRole("radio", { name: /Standard scoping/ }));
    expect(onSend).toHaveBeenCalledWith("Standard scoping\n\n[confirm part=depth option=standard]");
  });

  it("presets send directly and show their own sub text, band included", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(
      proposal("thoroughness", {
        options: [
          { id: "standard_review", label: "Standard report", sub: "Reads the strongest sources in full. · ~20 to 40 min", primary: true, reason: null },
          { id: "quick_look", label: "Rapid overview", sub: "Abstracts only. · ~10 to 15 min", primary: false, reason: null },
        ],
      }),
    );
    expect(screen.getByText("Abstracts only. · ~10 to 15 min")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Rapid overview/ }));
    expect(onSend).toHaveBeenCalledWith("Rapid overview\n\n[confirm part=thoroughness option=quick_look]");
    expect(screen.getByRole("radio", { name: /Rapid overview/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: /Standard report/ })).toHaveAttribute("aria-checked", "false");
  });

  it("a confirmed part collapses to <Part> · <choice> · Change, and Change opens a line in place", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(proposal("scope"), { live: true, answered: false, answer: null, confirmedOptionId: "confirm" }, vi.fn(), {
      partName: "Scope",
    });
    expect(screen.getByTestId("part-settled")).toHaveTextContent(/^Scope · Looks right · Change$/);
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByText(/Confirmed/)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Change" }));
    await user.type(screen.getByRole("textbox", { name: "Change Scope" }), "UK only");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("Change this part: UK only");
  });

  it("a superseded proposal collapses to <Part> · answered (owner, polish round 2)", () => {
    renderPart(proposal("scope"), { live: false, answered: true, answer: null, confirmedOptionId: null }, vi.fn(), { partName: "Scope" });
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.getByTestId("part-settled")).toHaveTextContent(/^Scope · answered$/);
  });

  it("stages chip edits and applies them as one batched turn", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(
      proposal("scope", { chips: [{ label: "UK primary", kind: "text", value: "UK as the primary study setting" }] }),
    );
    await user.click(screen.getByRole("button", { name: "Remove Screen: UK primary" }));
    await user.click(screen.getByRole("button", { name: "Apply changes" }));
    expect(onSend).toHaveBeenCalledWith('Update the scope:\n- Remove "UK primary".');
  });

  it("prefixes chips from kind and does not double-prefix", () => {
    expect(chipDisplayLabel({ kind: "text", label: "UK primary" })).toBe("Screen: UK primary");
    expect(chipDisplayLabel({ kind: "date_range", label: "Since 2016" })).toBe("Search: Since 2016");
    expect(chipDisplayLabel({ kind: "country_list", label: "UK" })).toBe("Search: UK");
    expect(chipDisplayLabel({ kind: "text", label: "Screen: already" })).toBe("Screen: already");
  });

  it("labels the chip-edit commit Save, not Stage", async () => {
    const user = userEvent.setup();
    renderPart(proposal("scope", { chips: [{ label: "UK primary", kind: "text", value: "UK as the primary study setting" }] }));
    expect(screen.getByText("Screen: UK primary")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit Screen: UK primary" }));
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stage" })).toBeNull();
  });

  it("shows the part's body under its title, with no Notes label", () => {
    renderPart(proposal("question", { title: "Your question", body: "What works to raise take-up?" }));
    expect(screen.queryByText("Notes")).toBeNull();
    expect(screen.getByTestId("part-card")).toHaveTextContent("What works to raise take-up?");
  });

  it("puts the stepper above the active card only", () => {
    const steps: PlanStep[] = [
      { id: "question", name: "Question", settled: true },
      { id: "scope", name: "Scope", settled: false },
      { id: "thoroughness", name: "Thoroughness", settled: false },
    ];
    const { unmount } = render(
      <PartCard part={proposal("scope")} state={{ live: true, answered: false, answer: null, confirmedOptionId: null }} disabled={false} onSend={vi.fn()} steps={steps} />,
    );
    expect(screen.getByTestId("plan-stepper")).toHaveTextContent(/^Question ✓, done\s*Plan · step 2 of 3 · Scope$/);
    unmount();
    render(
      <PartCard part={proposal("scope")} state={{ live: false, answered: true, answer: null, confirmedOptionId: null }} disabled={false} onSend={vi.fn()} steps={steps} />,
    );
    expect(screen.queryByTestId("plan-stepper")).toBeNull();
  });
});

describe("planSteps (task 058, N18)", () => {
  it("counts the Evidence search parts and marks the settled ones", () => {
    const turns = [
      turn(1, "opening", proposal("question")),
      turn(2, "That's my question\n\n[confirm part=question option=confirm]", proposal("scope")),
    ];
    expect(planSteps("evidence_search", turns, derivePartStates(turns))).toEqual([
      { id: "question", name: "Question", settled: true },
      { id: "scope", name: "Scope", settled: false },
      { id: "thoroughness", name: "Thoroughness", settled: false },
    ]);
  });

  it("counts the scoping parts, adding Who can act and Your options only once proposed", () => {
    const before = planSteps("options_scoping", [turn(1, "opening", proposal("question"))], new Map());
    expect(before.map((step) => step.name)).toEqual(["Question", "Settings", "Constraints", "Depth", "Risk appetite"]);
    const turns = [turn(1, "opening", proposal("question")), turn(2, "next", proposal("who_can_act")), turn(3, "next", proposal("your_options"))];
    const after = planSteps("options_scoping", turns, derivePartStates(turns));
    expect(after.map((step) => step.name)).toEqual([
      "Question",
      "Settings",
      "Constraints",
      "Who can act",
      "Your options",
      "Depth",
      "Risk appetite",
    ]);
  });

  it("renders the two scoping parts the planner proposes, by their names", () => {
    const turns = [turn(1, "opening", proposal("who_can_act")), turn(2, "next", proposal("your_options"))];
    const steps = planSteps("options_scoping", turns, derivePartStates(turns));
    render(
      <PartCard
        part={proposal("your_options", {
          title: "Options you already have in mind",
          options: [
            { id: "none_yet", label: "None yet", sub: null, primary: true, reason: null },
            { id: "i_have_some", label: "I have some", sub: null, primary: false, reason: null },
          ],
        })}
        state={{ live: true, answered: false, answer: null, confirmedOptionId: null }}
        disabled={false}
        onSend={vi.fn()}
        steps={steps}
      />,
    );
    expect(screen.getByTestId("plan-stepper")).toHaveTextContent("Plan · step 5 of 7 · Your options");
    expect(screen.getByRole("radio", { name: /I have some/ })).toBeInTheDocument();
  });

  it("asks for words only on the planners' words options", () => {
    expect(optionNeedsWords({ id: "refine", label: "Refine it", primary: false })).toBe(true);
    expect(optionNeedsWords({ id: "change", label: "Change", primary: false })).toBe(true);
    expect(optionNeedsWords({ id: "i_have_some", label: "I have some", primary: false })).toBe(true);
    expect(optionNeedsWords({ id: "national_too", label: "Also national", primary: false })).toBe(false);
    expect(optionNeedsWords({ id: "confirm", label: "Looks right", primary: true })).toBe(false);
  });
});

describe("PartCard — an answered card settles (owner, polish round 2)", () => {
  it("renders one settled line with the user's own answer and no radios once a later turn exists", () => {
    render(
      <PartCard
        part={proposal("scope")}
        partName="Scope"
        state={{ live: true, answered: true, answer: "Please go ahead with your recommended choices.", confirmedOptionId: null }}
        disabled={false}
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("part-settled")).toHaveTextContent("Scope · Please go ahead with your recommended choices.");
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "Change" })).toBeNull();
  });

  it("derivePartStates marks every card but the last turn's as answered", () => {
    const turns = [turn(1, "What works?", proposal("question")), turn(2, "Narrow it to England.", proposal("scope"))];
    const states = derivePartStates(turns);
    expect(states.get(1)?.answered).toBe(true);
    expect(states.get(1)?.answer).toBe("Narrow it to England.");
    expect(states.get(2)?.answered).toBe(false);
    expect(states.get(2)?.answer).toBeNull();
  });
});

describe("settledSummary — a settled part names the plan's outcome (owner, polish round 2)", () => {
  const answered = { live: true, answered: true, answer: "Please go ahead with your recommended choices.", confirmedOptionId: null };
  it("names the thoroughness preset and its band from the plan", () => {
    const part = proposal("thoroughness", {
      options: [
        { id: "quick_look", label: "Rapid overview", sub: null, primary: false },
        { id: "standard_review", label: "Standard report", sub: null, primary: true },
        { id: "deep_analysis", label: "Detailed report", sub: null, primary: false },
      ],
    });
    const plan = { search_effort: "standard", analysis_depth: "standard", time_band: "~10-20 min" } as never;
    expect(settledSummary(part, answered, plan, null)).toBe("Standard report · ~10-20 min");
  });
  it("names the scope's chips and the question's text; a recorded choice names itself", () => {
    const scope = proposal("scope", { chips: [{ label: "Since 2010", kind: "text" }, { label: "UK", kind: "text" }] as never });
    expect(settledSummary(scope, answered, null, null)).toBe("Since 2010 · UK");
    expect(settledSummary(proposal("question"), answered, { question: "What works?" } as never, null)).toBe("What works?");
    expect(settledSummary(proposal("question"), { ...answered, confirmedOptionId: "confirm" }, null, null)).toBe("Looks right");
  });
  it("falls back to the user's words when the plan names nothing", () => {
    expect(settledSummary(proposal("settings"), answered, null, null)).toBe("Please go ahead with your recommended choices.");
  });
});

