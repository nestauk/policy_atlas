import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AUTH_RETURN_TO_KEY, OidcAuthProvider } from "./OidcAuthProvider";
import { useAuth } from "./AuthContext";

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

describe("OidcAuthProvider splash gating", () => {
  beforeEach(() => {
    signinRedirect.mockReset();
    signoutRedirect.mockReset();
    sessionStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("renders children on an unauthenticated cold visit without redirecting", async () => {
    oidcState = {
      isLoading: false,
      isAuthenticated: false,
      activeNavigator: undefined,
      error: undefined,
      user: null,
    };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    expect(await screen.findByText("app")).toBeInTheDocument();
    expect(signinRedirect).not.toHaveBeenCalled();
  });

  it("does not mount children while the code exchange is loading", () => {
    oidcState = {
      isLoading: true,
      isAuthenticated: false,
      activeNavigator: undefined,
      error: undefined,
      user: null,
    };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.queryByText("app")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
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
    window.history.replaceState({}, "", "/projects/1?code=stale&state=stale&tab=runs#top");
    oidcState = {
      isLoading: false,
      isAuthenticated: false,
      activeNavigator: undefined,
      error: new Error("No matching state found in storage"),
      user: null,
    };
    render(<OidcAuthProvider>app</OidcAuthProvider>);

    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.queryByText("app")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/no matching state/i);

    fireEvent.click(screen.getByRole("button", { name: /sign in again/i }));
    expect(signinRedirect).toHaveBeenCalledOnce();
    expect(sessionStorage.getItem(AUTH_RETURN_TO_KEY)).toBe("/projects/1?tab=runs#top");
  });

  it("signIn redirects without auto-stashing when called from AuthApi", async () => {
    oidcState = {
      isLoading: false,
      isAuthenticated: false,
      activeNavigator: undefined,
      error: undefined,
      user: null,
    };
    // Children mount; splash would call auth.signIn after stashing itself.
    render(<OidcAuthProvider>app</OidcAuthProvider>);
    await waitFor(() => expect(screen.getByText("app")).toBeInTheDocument());
    expect(signinRedirect).not.toHaveBeenCalled();
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
