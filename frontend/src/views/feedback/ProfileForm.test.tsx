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
  it("requires the first two questions and saves nothing without them", async () => {
    const user = userEvent.setup();
    render(<ProfileForm submitLabel="Continue" />);

    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(screen.getByText("Choose your department and your team type.")).toBeInTheDocument();
    expect(screen.getByText("Choose your main use.")).toBeInTheDocument();
    expect(saveState.mutate).not.toHaveBeenCalled();
  });

  it("prefills the department from the email domain and saves the answers", async () => {
    const user = userEvent.setup();
    render(<ProfileForm email="ada@education.gov.uk" submitLabel="Continue" />);

    expect(screen.getByRole("combobox", { name: "Department" })).toHaveTextContent(
      "Department for Education",
    );
    await user.click(screen.getByRole("button", { name: "Analysis / evidence" }));
    await user.click(screen.getByRole("radio", { name: "Test claims in a policy proposal" }));
    await user.click(screen.getByRole("button", { name: "Yes, contact me" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(screen.getByRole("button", { name: "Analysis / evidence" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(saveState.mutate.mock.calls[0][0]).toEqual({
      department: "dfe",
      department_other: null,
      team_type: "analysis_evidence",
      primary_job: "j3",
      secondary_job: null,
      panel_opt_in: true,
    });
  });

  it("defaults an unknown domain to Other and takes the typed department", async () => {
    const user = userEvent.setup();
    render(<ProfileForm email="ada@nesta.org.uk" submitLabel="Continue" />);

    await user.type(screen.getByLabelText(/Department or organisation/), " Nesta ");
    await user.click(screen.getByRole("button", { name: "Policy" }));
    await user.click(screen.getByRole("radio", { name: "Something else" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(saveState.mutate.mock.calls[0][0]).toMatchObject({
      department: "other",
      department_other: "Nesta",
      panel_opt_in: null,
    });
  });

  it("offers a second use that is not the main use", async () => {
    const user = userEvent.setup();
    render(<ProfileForm email="ada@dwp.gov.uk" submitLabel="Continue" />);

    await user.click(screen.getByRole("button", { name: "Policy" }));
    await user.click(screen.getByRole("radio", { name: "Build or defend a spending bid" }));
    await user.click(screen.getByRole("button", { name: "+ add a second use" }));
    await user.click(screen.getByRole("combobox", { name: "Second use" }));

    expect(
      screen.queryByRole("option", { name: "Build or defend a spending bid" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "Get up to speed on a new policy area" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(saveState.mutate.mock.calls[0][0]).toMatchObject({
      primary_job: "j1",
      secondary_job: "j7",
    });
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
          department: "hmt",
          team_type: "strategy_finance",
          primary_job: "j2",
          secondary_job: "j4",
          panel_opt_in: false,
          completed_at: "2026-11-18T09:05:00Z",
        }}
      />,
    );

    expect(screen.getByRole("combobox", { name: "Department" })).toHaveTextContent("HM Treasury");
    expect(
      screen.getByRole("radio", { name: "Pressure-test someone else's bid or numbers" }),
    ).toBeChecked();
    expect(screen.getByRole("combobox", { name: "Second use" })).toHaveTextContent(
      "Turn evidence into briefing, fast",
    );
    expect(screen.getByRole("button", { name: "Not now" })).toHaveAttribute("aria-pressed", "true");
  });
});
