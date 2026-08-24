import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SENSITIVE_INFO_BANNER_KEY, SensitiveInfoBanner } from "./SensitiveInfoBanner";

const authState = vi.hoisted(() => ({ user: { sub: "policy-lead" } as { sub: string } | null }));

vi.mock("../auth", () => ({
  useAuth: () => ({
    user: authState.user,
    status: authState.user === null ? "unauthenticated" : "authenticated",
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    getAccessToken: async () => "token",
  }),
}));

describe("SensitiveInfoBanner", () => {
  beforeEach(() => {
    sessionStorage.clear();
    authState.user = { sub: "policy-lead" };
  });

  it("shows on authenticated pages and dismisses for the session", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<SensitiveInfoBanner />);
    expect(
      screen.getByText("Do not enter sensitive or confidential information."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss warning" }));
    expect(
      screen.queryByText("Do not enter sensitive or confidential information."),
    ).toBeNull();
    expect(sessionStorage.getItem(SENSITIVE_INFO_BANNER_KEY)).toBe("1");
    unmount();
    render(<SensitiveInfoBanner />);
    expect(
      screen.queryByText("Do not enter sensitive or confidential information."),
    ).toBeNull();
  });

  it("does not show when signed out", () => {
    authState.user = null;
    render(<SensitiveInfoBanner />);
    expect(
      screen.queryByText("Do not enter sensitive or confidential information."),
    ).toBeNull();
  });
});
