import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SplashView } from "./SplashView";

vi.mock("../../auth", () => ({
  useAuth: () => ({
    user: null,
    status: "unauthenticated",
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    getAccessToken: async () => null,
  }),
}));

vi.mock("../../auth/DevTokenAuthProvider", () => ({
  acceptDevToken: vi.fn(),
}));

describe("SplashView", () => {
  it("renders the hero and Request access / Sign in CTAs", () => {
    render(
      <MemoryRouter>
        <SplashView />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: /create policy plans you can trust/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /request access/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^request access$/i })).toBeInTheDocument();
    // Feature steps stay hidden until screenshots are ready.
    expect(screen.queryByText(/quickly become an expert/i)).not.toBeInTheDocument();
  });
});

describe("SplashView Request access", () => {
  const INVITE_LINE = "You are using an invite link.";

  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState(null, "", "/");
  });

  function renderSplash() {
    return render(
      <MemoryRouter>
        <SplashView />
      </MemoryRouter>,
    );
  }

  async function sendRequest(): Promise<Record<string, unknown>> {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ entry_id: "1", email: "ada@example.com", created_at: "x" }), {
        status: 201,
      }),
    );
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^email$/i), "ada@dhsc.example");
    await user.type(screen.getByLabelText(/^name$/i), "Ada");
    await user.type(screen.getByLabelText(/what would you like to use policy atlas for/i), "Research");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    return JSON.parse(fetchSpy.mock.calls[0][1]?.body as string) as Record<string, unknown>;
  }

  it("shows the intro and, once sent, the same success message to everyone", async () => {
    renderSplash();

    expect(
      screen.getByText(
        "Tell us a little about yourself. If your organisation already has access, we email " +
          "your sign-in details in a few minutes. If not, we review your request and get in touch.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(INVITE_LINE)).not.toBeInTheDocument();

    const body = await sendRequest();

    expect(body).not.toHaveProperty("invite_code");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Thanks. Check your email in a few minutes. If nothing arrives, we are reviewing your " +
        "request and will get in touch. Already have an account? Use Sign in.",
    );
  });

  it("with an invite link, says so, sends the code and clears it from the address", async () => {
    const scrollIntoView = vi.spyOn(HTMLElement.prototype, "scrollIntoView");
    // As pasted in a chat: lower case, with the sentence's full stop.
    window.history.replaceState(null, "", "/#invite=k7q2-m9xd-3fhp.");
    renderSplash();

    expect(screen.getByText(INVITE_LINE)).toBeInTheDocument();
    expect(window.location.hash).toBe("#access");
    expect(scrollIntoView).toHaveBeenCalled();

    const body = await sendRequest();

    expect(body.invite_code).toBe("K7Q2M9XD3FHP");
  });

  it("treats an address whose fragment is not a code as having none, and still clears it", async () => {
    window.history.replaceState(null, "", `/#invite=${"A".repeat(80)}`);
    renderSplash();

    expect(screen.queryByText(INVITE_LINE)).not.toBeInTheDocument();
    expect(window.location.hash).toBe("#access");

    const body = await sendRequest();

    expect(body).not.toHaveProperty("invite_code");
  });

  it("once sent, focuses the success message, whose Sign in starts the sign-in", async () => {
    renderSplash();
    await sendRequest();
    const success = await screen.findByRole("status");
    expect(success).toHaveFocus();
    await userEvent.setup().click(within(success).getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText(/paste a dev-issuer token/i)).toBeInTheDocument();
  });
});
