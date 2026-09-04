import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "./AuthContext";
import { OidcAuthProvider } from "./OidcAuthProvider";

// The adapter's contract with react-oidc-context, exercised per auth state.
const signinRedirect = vi.fn();
const signoutRedirect = vi.fn();
let oidcState: Record<string, unknown>;

vi.mock("react-oidc-context", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ signinRedirect, signoutRedirect, ...oidcState }),
}));

vi.stubEnv("VITE_OIDC_AUTHORITY", "https://issuer.test");
vi.stubEnv("VITE_OIDC_CLIENT_ID", "client-test");

describe("OidcAuthProvider cold-visit gating (026 live-check finding)", () => {
  beforeEach(() => {
    signinRedirect.mockReset();
    signoutRedirect.mockReset();
    sessionStorage.clear();
    window.history.replaceState({}, "", "/");
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

  it("renders a manual sign-in retry — not the shell, not a redirect loop — when the OIDC layer errors", () => {
    // A restored/back-navigated callback URL: consumed code/state params plus
    // a legitimate query param and hash that must survive the retry.
    window.history.replaceState({}, "", "/projects/1?code=stale&state=stale&tab=runs#top");
    oidcState = {
      isLoading: false,
      isAuthenticated: false,
      activeNavigator: undefined,
      error: new Error("No matching state found in storage"),
      user: null,
    };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    // No auto-redirect (loop guard) and no tokenless shell (026 live incident).
    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.queryByText("app")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/no matching state/i);

    fireEvent.click(screen.getByRole("button", { name: /sign in again/i }));
    expect(signinRedirect).toHaveBeenCalledOnce();
    // code/state stripped so the retry can't restore the poisoned callback URL.
    expect(sessionStorage.getItem("policy-atlas.auth-return-to")).toBe("/projects/1?tab=runs#top");
  });

  it("signs out through Cognito's logout_uri params, not OIDC RP-initiated logout", () => {
    oidcState = {
      isLoading: false,
      isAuthenticated: true,
      activeNavigator: undefined,
      error: undefined,
      user: { access_token: "t", profile: { sub: "user-1" } },
    };
    function SignOutControl() {
      const auth = useAuth();
      return (
        <button type="button" onClick={() => auth.signOut()}>
          Sign out
        </button>
      );
    }
    render(
      <OidcAuthProvider>
        <SignOutControl />
      </OidcAuthProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(signoutRedirect).toHaveBeenCalledOnce();
    expect(signoutRedirect).toHaveBeenCalledWith({
      extraQueryParams: {
        client_id: "client-test",
        logout_uri: window.location.origin,
      },
    });
  });
});
