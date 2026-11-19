import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProfileForm } from "./ProfileForm";

const saveState = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false }));
vi.mock("../../api/feedback", () => ({ useSaveProfile: () => saveState }));

beforeEach(() => {
  saveState.mutate.mockReset();
  saveState.isError = false;
});

describe("ProfileForm", () => {
  it("requires the first three questions and saves nothing without them", async () => {
    const user = userEvent.setup();
    render(<ProfileForm submitLabel="Continue" />);

    await user.type(screen.getByLabelText("Where do you work?"), "   ");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(screen.getByText("Enter where you work.")).toBeInTheDocument();
    expect(screen.getByText("Enter your role.")).toBeInTheDocument();
    expect(screen.getByText("Choose one use or more.")).toBeInTheDocument();
    expect(saveState.mutate).not.toHaveBeenCalled();
  });

  it("saves the typed answers and each use that is picked", async () => {
    const user = userEvent.setup();
    render(<ProfileForm submitLabel="Continue" />);

    await user.type(screen.getByLabelText("Where do you work?"), " Nesta ");
    await user.type(screen.getByLabelText("What is your role?"), "Data scientist");
    await user.click(screen.getByRole("checkbox", { name: "Test claims in a policy proposal" }));
    await user.click(screen.getByRole("checkbox", { name: "Something else" }));
    await user.click(screen.getByRole("checkbox", { name: "Build or defend a spending bid" }));
    // A second click removes a use.
    await user.click(screen.getByRole("checkbox", { name: "Something else" }));
    await user.click(screen.getByRole("button", { name: "Yes, contact me" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(saveState.mutate.mock.calls[0][0]).toEqual({
      department: "Nesta",
      role: "Data scientist",
      jobs: ["j3", "j1"],
      panel_opt_in: true,
    });
  });

  it("asks to contact the user for a research session, and the answer is optional", async () => {
    const user = userEvent.setup();
    render(<ProfileForm submitLabel="Continue" />);

    expect(
      screen.getByRole("group", {
        name: /Can we contact you to take part in a 30 minute user research session\?/,
      }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText("Where do you work?"), "HM Treasury");
    await user.type(screen.getByLabelText("What is your role?"), "Economist");
    await user.click(screen.getByRole("checkbox", { name: "Something else" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(saveState.mutate.mock.calls[0][0]).toMatchObject({ panel_opt_in: null });
  });

  it("offers Skip for now only when a skip is allowed", async () => {
    const onSkip = vi.fn();
    const user = userEvent.setup();
    const { unmount } = render(<ProfileForm submitLabel="Continue" onSkip={onSkip} />);

    await user.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(onSkip).toHaveBeenCalledOnce();

    unmount();
    render(<ProfileForm submitLabel="Continue" />);
    expect(screen.queryByRole("button", { name: "Skip for now" })).not.toBeInTheDocument();
  });

  it("fills the form from a completed profile for an edit", () => {
    render(
      <ProfileForm
        submitLabel="Save"
        profile={{
          department: "HM Treasury",
          role: "Economist",
          jobs: ["j2", "j4"],
          panel_opt_in: false,
          completed_at: "2026-11-18T09:05:00Z",
        }}
      />,
    );

    expect(screen.getByLabelText("Where do you work?")).toHaveValue("HM Treasury");
    expect(screen.getByLabelText("What is your role?")).toHaveValue("Economist");
    expect(
      screen.getAllByRole("checkbox", { checked: true }).map((box) => box.parentElement?.textContent),
    ).toEqual(["Pressure-test someone else's bid or numbers", "Turn evidence into briefing, fast"]);
    expect(screen.getByRole("button", { name: "Not now" })).toHaveAttribute("aria-pressed", "true");
  });
});
