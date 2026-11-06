import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ArrivalProvider } from "../../ui/motion/arrivals";

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

/** A card's state: an open card on the newest proposal, unless overridden. */
const OPEN = {
  live: true,
  answered: false,
  answer: null as string | null,
  confirmedOptionId: null as string | null,
  confirmedMessage: null as string | null,
  pending: false,
};

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
    state = OPEN,
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
    const onSend = renderPart(proposal("question"));
    await user.click(screen.getByRole("radio", { name: /Looks right/ }));
    expect(onSend).toHaveBeenCalledWith("Looks right\n\n[confirm part=question option=confirm]");
  });

  it("an option that needs words opens an input in the card with its own Send, never the composer", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(proposal("question"));
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
    const onSend = renderPart(proposal("scope"), { ...OPEN, confirmedOptionId: "confirm" }, vi.fn(), {
      partName: "Scope",
    });
    expect(screen.getByTestId("part-settled")).toHaveTextContent(/Scope.*Looks right.*Change/);
    // No tick (owner, 2026-11-05): the green rule and the green words say it.
    expect(screen.getByTestId("part-settled")).not.toHaveTextContent("✓");
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByText(/Confirmed/)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Change" }));
    await user.type(screen.getByRole("textbox", { name: "Change Scope" }), "UK only");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("Change this part: UK only");
  });

  it("a superseded proposal collapses to <Part> · answered (owner, polish round 2)", () => {
    renderPart(proposal("scope"), { ...OPEN, live: false, answered: true }, vi.fn(), { partName: "Scope" });
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.getByTestId("part-settled")).toHaveTextContent(/Scope.*Answered/);
  });

  it("sits on the user's side: the bubble's left indent and the green rule on its right edge", () => {
    renderPart(proposal("question"), { ...OPEN, confirmedOptionId: "confirm" }, vi.fn(), { partName: "Question" });
    const block = screen.getByTestId("part-settled");
    expect(block).toHaveClass("border-r-2", "border-r-green");
    expect(block.className).not.toMatch(/border-l/);
    expect(block.parentElement).toHaveClass("ml-8");
    expect(block.parentElement?.className).not.toMatch(/\bmr-8\b/);
  });

  // Owner, round 6: a settled part reads as the user's (the user bubble's
  // surface) and as a decision (the green rule, the deep green words and
  // the part's name as a small grey label).
  it("takes the user bubble's surface, with the part's name as a small grey label", () => {
    renderPart(proposal("question"), { ...OPEN, confirmedOptionId: "confirm" }, vi.fn(), { partName: "Question" });
    const block = screen.getByTestId("part-settled");
    expect(block).toHaveClass("border", "border-blue-tint", "bg-blue-tint-2");
    expect(block.firstElementChild).toHaveClass("px-3.5", "py-2.5");
    const name = screen.getByText("Question");
    expect(name).toHaveClass("uppercase", "text-meta", "text-grey");
    expect(name).not.toHaveClass("text-navy");
    expect(screen.getByText("Looks right")).toHaveClass("text-[#0c6b5a]");
  });

  // Owner, round 8: "Change" takes its own line under the green words, as a
  // quiet control at Caption size, never inline with the words.
  it("puts Change on its own line under the green words, a quiet grey control at Caption size", () => {
    renderPart(proposal("question"), { ...OPEN, confirmedOptionId: "confirm" }, vi.fn(), { partName: "Question" });
    const change = screen.getByRole("button", { name: "Change" });
    const words = screen.getByText("Looks right");
    expect(words).not.toContainElement(change);
    expect(change).toHaveClass("block", "text-caption", "text-grey", "underline", "hover:text-navy");
    expect(change.className).not.toMatch(/\btext-body\b|\bml-2\b/);
  });

  // Owner, round 8: one container across the two states. The box keeps its
  // element as the card settles; its surface and rule ease to the settled
  // look; the open form fades out over the settled words, inert, and goes.
  describe("the settle (owner, round 8)", () => {
    function rerenderable(state: typeof OPEN) {
      const part = proposal("question");
      const ui = (next: typeof OPEN) => (
        <PartCard part={part} partName="Question" state={next} disabled={false} onSend={vi.fn()} steps={[{ id: "question", name: "Question", settled: false }]} />
      );
      const view = render(ui(state));
      return { ...view, settle: () => view.rerender(ui({ ...OPEN, confirmedOptionId: "confirm" })) };
    }

    it("keeps one box: the open card's element becomes the settled block, its colours easing", () => {
      vi.useFakeTimers();
      const view = rerenderable(OPEN);
      const box = screen.getByTestId("part-card");
      expect(box).toHaveClass("transition-[background-color,border-color]", "duration-300", "overflow-hidden");
      view.settle();
      expect(screen.getByTestId("part-settled")).toBe(box);
      expect(box.parentElement).toHaveClass("ml-8");
      vi.useRealTimers();
    });

    it("fades the open form out over the settled words, inert and hidden, then removes it", () => {
      vi.useFakeTimers();
      const view = rerenderable(OPEN);
      view.settle();
      const leaving = screen.getByTestId("part-settled").querySelector(".anim-fade-out") as HTMLElement;
      expect(leaving).toHaveAttribute("aria-hidden", "true");
      expect(leaving).toHaveAttribute("inert");
      expect(leaving).toHaveClass("absolute", "pointer-events-none");
      expect(screen.queryByRole("radio")).toBeNull();
      // The settled words rise in.
      expect(screen.getByTestId("part-settled").firstElementChild).toHaveClass("anim-rise");
      act(() => vi.advanceTimersByTime(200));
      expect(screen.getByTestId("part-settled").querySelector(".anim-fade-out")).toBeNull();
      vi.useRealTimers();
    });

    it("folds the stepper line away rather than dropping it", () => {
      const view = rerenderable(OPEN);
      const stepper = screen.getByText(/Plan · step 1 of 1/).closest(".grid") as HTMLElement;
      expect(stepper).toHaveClass("grid-rows-[1fr]");
      view.settle();
      expect(stepper).toHaveClass("grid-rows-[0fr]", "opacity-0");
    });

    it("is a cut under reduced motion: no fading form, no rise", () => {
      vi.stubGlobal("matchMedia", (query: string) => ({
        matches: query.includes("reduce"),
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }));
      const view = rerenderable(OPEN);
      view.settle();
      expect(screen.getByTestId("part-settled").querySelector(".anim-fade-out")).toBeNull();
      expect(screen.getByTestId("part-settled").firstElementChild).not.toHaveClass("anim-rise");
      vi.unstubAllGlobals();
    });

    it("holds still when it mounts settled (the history)", () => {
      rerenderable({ ...OPEN, confirmedOptionId: "confirm" });
      expect(screen.getByTestId("part-settled").firstElementChild).not.toHaveClass("anim-rise");
      expect(screen.queryByText(/Plan · step/)).toBeNull();
    });
  });

  it("the scope card's one choice is a secondary Looks right button, with no words option", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(
      proposal("scope", {
        options: [
          { id: "confirm", label: "Looks right", sub: null, primary: true, reason: null },
          { id: "change", label: "Add or change a constraint", sub: "Opens a line to type the change.", primary: false, reason: null },
        ],
      }),
    );
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByText("Add or change a constraint")).toBeNull();
    const button = screen.getByRole("button", { name: "Looks right" });
    // Secondary: the plan card's green Start stays the one filled action.
    expect(button.className).not.toMatch(/\bcutout|bg-blue/);
    await user.click(button);
    expect(onSend).toHaveBeenCalledWith("Looks right\n\n[confirm part=scope option=confirm]");
  });

  it("sends the staged chip edits with Looks right, as one turn that records the primary option", async () => {
    const user = userEvent.setup();
    const onSend = renderPart(
      proposal("scope", { chips: [{ label: "UK primary", kind: "text", value: "UK as the primary study setting" }] }),
    );
    await user.click(screen.getByRole("button", { name: "Remove Screen: UK primary" }));
    // The edits go with the one choice; there is no second commit.
    expect(screen.queryByRole("button", { name: "Apply changes" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Looks right" }));
    const message = 'Update the scope:\n- Remove "UK primary".\n\n[confirm part=scope option=confirm]';
    expect(onSend).toHaveBeenCalledWith(message);
    expect(confirmTarget(message)).toEqual({ partId: "scope", optionId: "confirm" });
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
    expect(screen.getByText("UK primary")).toBeInTheDocument();
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
      <PartCard part={proposal("scope")} state={OPEN} disabled={false} onSend={vi.fn()} steps={steps} />,
    );
    expect(screen.getByTestId("plan-stepper")).toHaveTextContent(/^Question ✓, done\s*Plan · step 2 of 3 · Scope$/);
    unmount();
    render(
      <PartCard part={proposal("scope")} state={{ ...OPEN, live: false, answered: true }} disabled={false} onSend={vi.fn()} steps={steps} />,
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
        state={OPEN}
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
    expect(optionNeedsWords({ id: "my_own_words", label: "Something else", primary: false })).toBe(true);
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
        state={{ ...OPEN, answered: true, answer: "Please go ahead with your recommended choices." }}
        disabled={false}
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("part-settled")).toHaveTextContent("Please go ahead with your recommended choices.");
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
  const answered = { ...OPEN, answered: true, answer: "Please go ahead with your recommended choices." };
  it("names the thoroughness preset and its band from the plan", () => {
    const part = proposal("thoroughness", {
      options: [
        { id: "quick_look", label: "Rapid overview", sub: null, primary: false },
        { id: "standard_review", label: "Standard report", sub: null, primary: true },
        { id: "deep_analysis", label: "Detailed report", sub: null, primary: false },
      ],
    });
    const plan = { search_effort: "standard", analysis_depth: "standard", time_band: "~10-20 min" } as never;
    expect(settledSummary(part, answered, plan, null)).toEqual([{ label: null, text: "Standard report · ~10-20 min" }]);
  });
  it("names the scope's chips and the question's text; a recorded choice names itself", () => {
    const scope = proposal("scope", { chips: [{ label: "Since 2010", kind: "text" }, { label: "UK", kind: "text" }] as never });
    // Plain text chips are screening criteria by kind (`chipDisplayLabel`).
    expect(settledSummary(scope, answered, null, null)).toEqual([{ label: "Screening criteria", text: "Since 2010 · UK" }]);
    expect(settledSummary(proposal("question"), answered, { question: "What works?" } as never, null)).toEqual([
      { label: null, text: "What works?" },
    ]);
    expect(settledSummary(proposal("question"), { ...answered, confirmedOptionId: "confirm" }, null, null)).toEqual([
      { label: null, text: "Looks right" },
    ]);
  });
  it("falls back to the user's words when the plan names nothing", () => {
    expect(settledSummary(proposal("settings"), answered, null, null)).toEqual([
      { label: null, text: "Please go ahead with your recommended choices." },
    ]);
  });
});

describe("scope chips grouped by what they constrain (owner, 2026-11-05)", () => {
  it("renders screening criteria and source filters under their own headings, prefixes dropped", () => {
    const part = proposal("scope", {
      chips: [
        { label: "Screen: Zonal electricity pricing", kind: "text" },
        { label: "Search: OECD source origins", kind: "text" },
        { label: "Screen: Bills or energy security", kind: "text" },
      ] as never,
    });
    render(<PartCard part={part} state={OPEN} disabled={false} onSend={vi.fn()} />);
    expect(screen.getByText("Screening criteria")).toBeInTheDocument();
    expect(screen.getByText("Source filters")).toBeInTheDocument();
    expect(screen.getByText("Zonal electricity pricing")).toBeInTheDocument();
    expect(screen.queryByText(/^Screen: /)).toBeNull();
  });
  it("names the settled scope one group a line, each under its label", () => {
    const part = proposal("scope", {
      chips: [{ label: "Screen: Bills", kind: "text" }, { label: "Search: OECD", kind: "text" }] as never,
    });
    const state = { ...OPEN, answered: true };
    const lines = settledSummary(part, state, null, null);
    expect(lines).toEqual([
      { label: "Screening criteria", text: "Bills" },
      { label: "Source filters", text: "OECD" },
    ]);
    render(<PartCard part={part} state={state} summary={lines} disabled={false} onSend={vi.fn()} />);
    const settled = screen.getByTestId("part-settled");
    expect(settled).toHaveTextContent(/Screening criteria.*Bills.*Source filters.*OECD/);
    // The label is grey; the words are the deep green (#0c6b5a, the green
    // tint's text, lead 2026-11-05): two colours, two roles.
    expect(screen.getByText("Source filters").className).toContain("text-grey");
    // The group labels a step smaller than the part's name (lead, round 6).
    expect(screen.getByText("Source filters")).toHaveClass("text-caption", "uppercase");
    expect(screen.getByText("Source filters")).not.toHaveClass("text-meta");
    expect(screen.getByText("OECD")).toHaveClass("text-[#0c6b5a]");
    expect(screen.getByText("OECD").className).not.toMatch(/(^|\s)text-green(\s|$)/);
  });
});


describe("a part card settles on the choice (owner, 2026-11-05)", () => {
  const scope = proposal("scope");

  it("settles the newest card on a turn still on its way, before the reply lands", () => {
    const turns = [turn(1, "opening", proposal("question"))];
    // Nothing sent yet: the card is open.
    expect(derivePartStates(turns).get(1)).toEqual(expect.objectContaining({ answered: false, pending: false }));
    // A choice on its way: settled at once, on that choice.
    const chose = derivePartStates(turns, ["Looks right\n\n[confirm part=question option=confirm]"]).get(1);
    expect(chose).toEqual(expect.objectContaining({ answered: true, confirmedOptionId: "confirm", pending: true }));
    // Words on their way: settled on the words.
    const wrote = derivePartStates(turns, ["Only rural areas"]).get(1);
    expect(wrote).toEqual(expect.objectContaining({ answered: true, answer: "Only rural areas", pending: true }));
  });

  it("is no longer pending once the durable turn has landed", () => {
    const turns = [turn(1, "opening", proposal("question")), turn(2, "Looks right\n\n[confirm part=question option=confirm]")];
    expect(derivePartStates(turns).get(1)).toEqual(expect.objectContaining({ confirmedOptionId: "confirm", pending: false }));
  });

  it("names the user's words, or a choice other than the planner's, until the plan catches up", () => {
    const plan = { question: "What works to raise take-up?" } as never;
    const question = proposal("question");
    // Words on their way: the words, not the old question.
    expect(settledSummary(question, { ...OPEN, answered: true, answer: "Only rural areas", pending: true }, plan, null)).toEqual([
      { label: null, text: "Only rural areas" },
    ]);
    // The planner's own option keeps the draft: its outcome reads at once.
    expect(settledSummary(question, { ...OPEN, answered: true, confirmedOptionId: "confirm", pending: true }, plan, null)).toEqual([
      { label: null, text: "What works to raise take-up?" },
    ]);
    // Another option: its label, until the plan says what it became.
    const thoroughness = proposal("thoroughness", {
      options: [
        { id: "standard_review", label: "Standard report", sub: null, primary: true },
        { id: "quick_look", label: "Rapid overview", sub: null, primary: false },
      ],
    });
    const drafted = { search_effort: "standard", analysis_depth: "standard", time_band: "~20 min" } as never;
    expect(settledSummary(thoroughness, { ...OPEN, answered: true, confirmedOptionId: "quick_look", pending: true }, drafted, null)).toEqual([
      { label: null, text: "Rapid overview" },
    ]);
  });

  it("a scope settled with chip edits lists the chips as edited", () => {
    const part = proposal("scope", {
      chips: [
        { label: "UK primary", kind: "text", value: "" },
        { label: "Adults", kind: "text", value: "" },
        { label: "Since 2010", kind: "date_range", value: "" },
      ],
    });
    const message = chipEditMessage([
      { kind: "remove", label: "UK primary" },
      { kind: "change", label: "Adults", detail: "Older adults" },
      { kind: "add", label: "exclude opinion pieces", detail: "exclude opinion pieces" },
    ]);
    const state = {
      ...OPEN,
      answered: true,
      confirmedOptionId: "confirm",
      confirmedMessage: `${message}\n\n[confirm part=scope option=confirm]`,
      pending: true,
    };
    expect(settledSummary(part, state, null, null)).toEqual([
      { label: null, text: "exclude opinion pieces" },
      { label: "Screening criteria", text: "Older adults" },
      { label: "Source filters", text: "Since 2010" },
    ]);
    // Without edits the proposal's chips stand.
    expect(settledSummary(scope, { ...OPEN, answered: true, confirmedOptionId: "confirm" }, null, null)).toEqual([
      { label: null, text: "Looks right" },
    ]);
  });
});

// Round 9 (the animation sweep's entries 2 and 5): a card that arrives after
// the thread's first paint rises and lays its rows out in turn; the history
// holds still.
describe("PartCard — arrival (round 9)", () => {
  it("rises and cascades its radio rows when it arrives into the thread", () => {
    const part = proposal("question");
    render(
      <ArrivalProvider settled scopeKey="t1">
        <PartCard part={part} arrivalId="part:new" state={OPEN} disabled={false} onSend={vi.fn()} />
      </ArrivalProvider>,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBeGreaterThan(0);
    const rows = radios.map((radio) => radio.closest(".anim-cascade") as HTMLElement | null);
    expect(rows.every((row) => row !== null)).toBe(true);
    expect(rows.map((row) => row?.style.getPropertyValue("--i"))).toEqual(rows.map((_, index) => String(index)));
    expect(screen.getByTestId("part-card").closest(".anim-rise")).not.toBeNull();
  });

  it("holds still in the history", () => {
    render(<PartCard part={proposal("question")} state={OPEN} disabled={false} onSend={vi.fn()} />);
    expect(document.querySelector(".anim-cascade")).toBeNull();
    expect(document.querySelector(".anim-rise")).toBeNull();
  });
});
