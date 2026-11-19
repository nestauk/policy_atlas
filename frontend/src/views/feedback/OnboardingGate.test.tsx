import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { markSkipped } from "../../lib/profileGate";
import { OnboardingGate } from "./OnboardingGate";

const NEW = { completed_at: null, skipped_once_at: null };
const SKIPPED = { completed_at: null, skipped_once_at: "2026-11-17T09:00:00Z" };

const state = vi.hoisted(() => ({
  profile: undefined as { completed_at: string | null; skipped_once_at: string | null } | undefined,
  useProfile: vi.fn(),
  skip: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("../../api/feedback", () => ({
  useProfile: () => {
    state.useProfile();
    return { data: state.profile };
  },
  useSkipProfile: () => ({ mutate: state.skip, isPending: false }),
  useSaveProfile: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));
vi.mock("../../auth", () => ({
  useAuth: () => ({ user: { sub: "ada" }, signOut: state.signOut }),
}));

function renderGate(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <OnboardingGate>
        <p>The app</p>
      </OnboardingGate>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.stubEnv("VITE_FEEDBACK", "onboarding");
  state.profile = NEW;
  state.useProfile.mockReset();
  state.skip.mockReset();
});
afterEach(() => vi.unstubAllEnvs());

describe("OnboardingGate", () => {
  it("with the flag off shows the app and does not read the profile", () => {
    vi.stubEnv("VITE_FEEDBACK", "citation_flag");

    renderGate();

    expect(screen.getByText("The app")).toBeInTheDocument();
    expect(state.useProfile).not.toHaveBeenCalled();
  });

  it("at first access shows the form in place of the app, with one skip", () => {
    renderGate();

    expect(screen.queryByText("The app")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Before you start" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skip for now" })).toBeInTheDocument();
  });

  it("lets the user through after Skip for now is recorded", async () => {
    state.skip.mockImplementation((_input, options) => {
      state.profile = SKIPPED;
      options.onSuccess();
    });
    const user = userEvent.setup();
    renderGate();

    await user.click(screen.getByRole("button", { name: "Skip for now" }));

    expect(screen.getByText("The app")).toBeInTheDocument();
  });

  it("at the next login shows the form again with no skip", () => {
    state.profile = SKIPPED;

    renderGate();

    expect(screen.getByRole("heading", { name: "Before you start" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Skip for now" })).not.toBeInTheDocument();
  });

  it("does not ask again in the login in which the user skipped", () => {
    state.profile = SKIPPED;
    markSkipped("ada");

    renderGate();

    expect(screen.getByText("The app")).toBeInTheDocument();
  });

  it("shows the app when the profile is completed", () => {
    state.profile = { completed_at: "2026-11-18T09:05:00Z", skipped_once_at: null };

    renderGate();

    expect(screen.getByText("The app")).toBeInTheDocument();
  });

  it("leaves the privacy notice readable before the form is answered", () => {
    renderGate("/privacy");

    expect(screen.getByText("The app")).toBeInTheDocument();
  });
});
