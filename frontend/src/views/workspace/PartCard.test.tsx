import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  PartCard,
  type PlanningTurn,
  chipEditMessage,
  confirmMessage,
  confirmTarget,
  derivePartStates,
} from "./PartCard";

function turn(
  index: number,
  message: string,
  part: PlanningTurn["part"] = null,
): PlanningTurn {
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

function proposal(id: string, overrides: Partial<NonNullable<PlanningTurn["part"]>> = {}) {
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
    expect(states.get(1)).toEqual({ live: true, confirmedOptionId: "confirm" });
    // The superseded scope proposal is inert and holds no confirm.
    expect(states.get(2)).toEqual({ live: false, confirmedOptionId: null });
    // The re-proposal is live and took turn 4's confirm.
    expect(states.get(3)).toEqual({ live: true, confirmedOptionId: "confirm" });
  });

  it("a confirm referencing a part never proposed binds nothing", () => {
    const turns = [turn(1, "opening", proposal("question")), turn(2, "[confirm part=scope option=confirm]")];
    expect(derivePartStates(turns).get(1)).toEqual({ live: true, confirmedOptionId: null });
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

describe("PartCard", () => {
  it("sends the canned confirm for the primary; bare secondary options prefill", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onPrefill = vi.fn();
    render(
      <PartCard
        part={proposal("scope")}
        state={{ live: true, confirmedOptionId: null }}
        disabled={false}
        onSend={onSend}
        onPrefill={onPrefill}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Looks right/ }));
    expect(onSend).toHaveBeenCalledWith("Looks right\n\n[confirm part=scope option=confirm]");
    await user.click(screen.getByRole("button", { name: /Change it/ }));
    expect(onPrefill).toHaveBeenCalledWith("Change it: ");
  });

  it("options carrying a sub line (presets) send directly even when secondary", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const part = proposal("thoroughness", {
      options: [
        { id: "standard_review", label: "Standard review", sub: "a full cited report · ~10-20 min", primary: true, reason: null },
        { id: "quick_look", label: "Quick look", sub: "a short cited overview · ~5-10 min", primary: false, reason: null },
      ],
    });
    render(
      <PartCard
        part={part}
        state={{ live: true, confirmedOptionId: null }}
        disabled={false}
        onSend={onSend}
        onPrefill={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Quick look/ }));
    expect(onSend).toHaveBeenCalledWith(
      "Quick look\n\n[confirm part=thoroughness option=quick_look]",
    );
  });

  it("renders ✓ with the confirmed option label instead of buttons", () => {
    render(
      <PartCard
        part={proposal("question")}
        state={{ live: true, confirmedOptionId: "confirm" }}
        disabled={false}
        onSend={vi.fn()}
        onPrefill={vi.fn()}
      />,
    );
    expect(screen.getByText(/✓ Confirmed — Looks right/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Change it/ })).toBeNull();
  });

  it("a superseded proposal renders inert with its history note", () => {
    render(
      <PartCard
        part={proposal("scope")}
        state={{ live: false, confirmedOptionId: null }}
        disabled={false}
        onSend={vi.fn()}
        onPrefill={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /Looks right/ })).toBeDisabled();
    expect(screen.getByText(/kept for the record/)).toBeInTheDocument();
  });

  it("stages chip edits and applies them as one batched turn", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const part = proposal("scope", {
      chips: [{ label: "UK primary", kind: "text", value: "UK as the primary study setting" }],
    });
    render(
      <PartCard
        part={part}
        state={{ live: true, confirmedOptionId: null }}
        disabled={false}
        onSend={onSend}
        onPrefill={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Remove UK primary" }));
    await user.click(screen.getByRole("button", { name: "Apply changes" }));
    expect(onSend).toHaveBeenCalledWith('Update the scope:\n- Remove "UK primary".');
  });
});
