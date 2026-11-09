import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  AddReason,
  invitesReason,
  OptionActionButton,
  ShortlistToggle,
  TOGGLE_GLYPH_SIZE,
  type useOptionActions,
} from "./optionActions";

type Actions = ReturnType<typeof useOptionActions>;

function actions(patch: Partial<Actions> = {}): Actions {
  return {
    walkActive: false,
    notice: null,
    setNotice: vi.fn(),
    exclude: vi.fn(),
    include: vi.fn(),
    excludeGroup: vi.fn(),
    includeGroup: vi.fn(),
    shortlist: vi.fn(),
    unshortlist: vi.fn(),
    excludePending: false,
    includePending: false,
    ...patch,
  };
}

// Round 13 (owner): the shortlist is a bookmark icon toggle, Exclude a menu.
describe("ShortlistToggle (round 13)", () => {
  it("shows the filled circled check in Electric Blue on a place, named Remove from shortlist, pressed", async () => {
    const user = userEvent.setup();
    const done = actions();
    render(<ShortlistToggle actions={done} optionId="o1" shortlistState="proposed" excluded={false} />);
    const toggle = screen.getByRole("button", { name: "Remove from shortlist" });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle).toHaveClass("text-blue", "h-10", "w-10");
    expect(toggle.querySelector("circle")).toHaveAttribute("fill", "currentColor");
    expect(toggle.querySelector("path")).toHaveAttribute("stroke", "white");
    expect(toggle).not.toHaveTextContent(/\S/);
    await user.click(toggle);
    expect(done.unshortlist).toHaveBeenCalledWith("o1", expect.any(Function));
  });

  it("shows the outline circle in Grey without a place, named Add to shortlist, with its tooltip", async () => {
    const done = actions();
    render(<ShortlistToggle actions={done} optionId="o1" shortlistState={null} excluded={false} />);
    const toggle = screen.getByRole("button", { name: "Add to shortlist" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(toggle).toHaveClass("text-grey");
    expect(toggle.querySelector("circle")).toHaveAttribute("fill", "transparent");
    expect(toggle.querySelector("path")).toBeNull();
    act(() => toggle.focus());
    expect((await screen.findAllByText("Add to shortlist")).length).toBeGreaterThan(0);
    fireEvent.click(toggle);
    expect(done.shortlist).toHaveBeenCalledWith("o1", expect.any(Function));
  });

  it("is disabled while a walk runs, and absent for an excluded option without a place", () => {
    const { unmount } = render(
      <ShortlistToggle actions={actions({ walkActive: true })} optionId="o1" shortlistState="proposed" excluded={false} />,
    );
    expect(screen.getByRole("button", { name: "Remove from shortlist" })).toBeDisabled();
    unmount();
    render(<ShortlistToggle actions={actions()} optionId="o1" shortlistState={null} excluded />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

// Round 13 (owner): shortlisting one option flashed every marker. The
// pressed control changes at once and holds until the read agrees; a
// re-render with the same state changes nothing and remounts nothing.
describe("ShortlistToggle, one press (round 13)", () => {
  it("shows the new state at once, holds it until the read agrees, and drops it on a failure", async () => {
    const user = userEvent.setup();
    const done = actions();
    const toggle = (state: "proposed" | null) => (
      <ShortlistToggle actions={done} optionId="o1" shortlistState={state} excluded={false} />
    );
    const { rerender } = render(toggle(null));
    const button = screen.getByRole("button");
    const circle = button.querySelector("circle");
    await user.click(button);
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(button).not.toBeDisabled();
    // The refetch before the change lands: still pressed, same nodes.
    rerender(toggle(null));
    expect(screen.getByRole("button")).toBe(button);
    expect(button).toHaveAttribute("aria-pressed", "true");
    // The read agrees: the same nodes, the same classes, no replay.
    const classes = circle?.getAttribute("class");
    rerender(toggle("proposed"));
    rerender(toggle("proposed"));
    expect(button.querySelector("circle")).toBe(circle);
    expect(circle?.getAttribute("class")).toBe(classes);
    expect(button).toHaveAttribute("aria-pressed", "true");
    // A failed press goes back to what the read says.
    await user.click(button);
    expect(button).toHaveAttribute("aria-pressed", "false");
    const fail = vi.mocked(done.unshortlist).mock.calls[0][1] as () => void;
    act(() => fail());
    expect(button).toHaveAttribute("aria-pressed", "true");
  });
});

describe("OptionActionButton (round 13)", () => {
  // Round 13 (owner): Exclude acts at once, no reason asked first.
  it("is a quiet text control: Exclude acts at once with no reason", async () => {
    const user = userEvent.setup();
    const done = actions();
    render(<OptionActionButton actions={done} optionId="o1" excluded={false} />);
    const control = screen.getByRole("button", { name: "Exclude" });
    // The exclude glyph before its words, at the shortlist toggle's size (round 13, owner).
    expect(control.querySelector("svg circle")).not.toBeNull();
    expect(control.querySelector("svg")).toHaveAttribute("width", String(TOGGLE_GLYPH_SIZE));
    expect(control.firstElementChild?.tagName.toLowerCase()).toBe("svg");
    await user.click(control);
    expect(done.exclude).toHaveBeenCalledWith("o1", "");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("says Include again on an excluded option", async () => {
    const user = userEvent.setup();
    const done = actions();
    render(<OptionActionButton actions={done} optionId="o1" excluded />);
    const control = screen.getByRole("button", { name: "Include again" });
    // The undo glyph before its words.
    expect(control.querySelector("svg")).toHaveAttribute("width", String(TOGGLE_GLYPH_SIZE));
    expect(control.querySelector("svg circle")).toBeNull();
    await user.click(control);
    expect(done.include).toHaveBeenCalledWith("o1");
  });
});

// Round 13 (owner): the reason comes after the exclusion, if wanted.
describe("AddReason (round 13)", () => {
  it("opens the field and saves the reason, after the group's words when it went with one", async () => {
    const user = userEvent.setup();
    const done = actions();
    render(<AddReason actions={done} optionId="o1" current="with the theme Conditionality" />);
    await user.click(screen.getByRole("button", { name: "Add a reason" }));
    await user.type(screen.getByRole("textbox", { name: "Why exclude this option?" }), "Out of our remit");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(done.exclude).toHaveBeenCalledWith("o1", "with the theme Conditionality: Out of our remit");
    expect(screen.getByRole("button", { name: "Add a reason" })).toBeInTheDocument();
  });

  it("saves the reason alone on an exclusion with none, and Cancel closes the field", async () => {
    const user = userEvent.setup();
    const done = actions();
    render(<AddReason actions={done} optionId="o1" current="" />);
    await user.click(screen.getByRole("button", { name: "Add a reason" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(done.exclude).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Add a reason" }));
    await user.type(screen.getByRole("textbox"), "Too costly");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(done.exclude).toHaveBeenCalledWith("o1", "Too costly");
  });

  it("invites a reason only on the reader's own exclusion without one", () => {
    expect(invitesReason({ by: "user", reason: "" })).toBe(true);
    expect(invitesReason({ by: "user", reason: "with the lever Regulate" })).toBe(true);
    expect(invitesReason({ by: "user", reason: "with the lever Regulate: costly" })).toBe(false);
    expect(invitesReason({ by: "user", reason: "Too costly" })).toBe(false);
    expect(invitesReason({ by: "constrain", reason: "" })).toBe(false);
  });
});
