import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OidcAuthProvider } from "./OidcAuthProvider";

// The adapter's contract with react-oidc-context, exercised per auth state.
const signinRedirect = vi.fn();
let oidcState: Record<string, unknown>;

vi.mock("react-oidc-context", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ signinRedirect, ...oidcState }),
}));

vi.stubEnv("VITE_OIDC_AUTHORITY", "https://issuer.test");
vi.stubEnv("VITE_OIDC_CLIENT_ID", "client-test");

describe("OidcAuthProvider cold-visit gating (026 live-check finding)", () => {
  beforeEach(() => {
    signinRedirect.mockReset();
    sessionStorage.clear();
  });

  it("redirects an unauthenticated cold visit to sign-in, preserving the route", async () => {
    oidcState = { isLoading: false, isAuthenticated: false, activeNavigator: undefined, error: undefined, user: null };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    await waitFor(() => expect(signinRedirect).toHaveBeenCalledOnce());
    expect(sessionStorage.getItem("policy-atlas.auth-return-to")).toBe("/");
    // The app shell must not mount while the redirect is in flight.
    expect(screen.queryByText("app")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/taking you to sign in/i);
  });

  it("does not redirect while the code exchange is loading", () => {
    oidcState = { isLoading: true, isAuthenticated: false, activeNavigator: undefined, error: undefined, user: null };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.queryByText("app")).not.toBeInTheDocument();
  });

  it("renders the app when authenticated, without redirecting", () => {
    oidcState = {
      isLoading: false,
      isAuthenticated: true,
      activeNavigator: undefined,
      error: undefined,
      user: { access_token: "t", profile: { sub: "user-1" } },
    };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.getByText("app")).toBeInTheDocument();
  });

  it("renders the app (not a redirect loop) when the OIDC layer errors", () => {
    oidcState = { isLoading: false, isAuthenticated: false, activeNavigator: undefined, error: new Error("idp down"), user: null };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.getByText("app")).toBeInTheDocument();
  });
});
