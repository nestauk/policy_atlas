import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App, { queryClient } from "./App";
import { AUTH_RETURN_TO_KEY } from "./auth/OidcAuthProvider";
import type { AuthApi, AuthStatus } from "./auth";
import { TASK } from "./lib/vocabulary";
import { installMockApi, MOCK_TASK_ID } from "./mock";
import { MOCK_PROJECT_ID } from "./mock/fixtures";
import { authenticatedRouter, publicRouter } from "./routes";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // The landing heading moved from "Projects" to "Tasks" with the 032
  // vocabulary split: a backend `task` row is a Task on screen. The
  // assertion reads the word from the shared vocabulary module rather than
  // repeating the literal, so it cannot drift from what the app renders.
  it("renders the tasks landing heading", () => {
    vi.stubEnv("VITE_DEV_TOKEN", "test-token");
    render(<App />);
    expect(screen.getByRole("heading", { name: TASK.many })).toBeInTheDocument();
  });

  // Review fix (task 037): the cache clear used to run in a passive effect,
  // AFTER the swapped router had already rendered — a frame where cached
  // private data could show up on a public Task's URL. Signing out is a
  // real settled-status change reachable through the UI (Account → Sign
  // out), so it exercises the render-time clear directly rather than the
  // internals.
  it("clears the query cache on a settled status change", async () => {
    vi.stubEnv("VITE_DEV_TOKEN", "test-token");
    const user = userEvent.setup();
    render(<App />);
    queryClient.setQueryData(["test-cache-probe"], "sensitive-cached-value");
    expect(queryClient.getQueryData(["test-cache-probe"])).toBe("sensitive-cached-value");

    await user.click(await screen.findByRole("button", { name: "Account" }));
    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(queryClient.getQueryData(["test-cache-probe"])).toBeUndefined();
  });
});

/**
 * Task 038 V11: after a sign-in round trip the app must land on the stashed
 * deep link, not the landing route.
 *
 * The three tests drive the real `App` and the real module-level routers
 * from `routes.tsx` — the singletons are the whole point of the defect, so
 * substituting a memory router would test something else. Auth status comes
 * through the production mock seam (`VITE_MOCK=1` +
 * `globalThis.__policyAtlasMockAuth`, installed by `installMockApi()`),
 * which lets a signed-out visit become a signed-in one between two renders
 * without touching the auth providers.
 */
describe("App lands on the stashed deep link after sign-in (task 038 V11)", () => {
  type GlobalWithMockAuth = typeof globalThis & { __policyAtlasMockAuth?: AuthApi };

  /** Swap the installed mock identity, as a completed sign-in would. */
  function setMockAuth(status: AuthStatus) {
    (globalThis as GlobalWithMockAuth).__policyAtlasMockAuth = {
      getAccessToken: async () => (status === "authenticated" ? "mock-access-token" : null),
      signIn: () => undefined,
      signOut: () => undefined,
      onUnauthenticated: () => undefined,
      user: status === "authenticated" ? { sub: "mock-policy-lead" } : null,
      status,
    };
  }

  /**
   * Exactly what `OidcAuthProvider.onSigninCallback` does on the way back
   * from Cognito: drain the stash and rewrite the address bar with
   * `history.replaceState` (which React Router does not observe). The
   * callback is inline JSX in the provider and stays untouched by this
   * slice, so the flow is reproduced here rather than imported.
   */
  function restoreStashAsSigninCallbackWould() {
    const returnTo = sessionStorage.getItem(AUTH_RETURN_TO_KEY);
    sessionStorage.removeItem(AUTH_RETURN_TO_KEY);
    window.history.replaceState({}, document.title, returnTo ?? window.location.pathname);
  }

  beforeAll(() => {
    installMockApi();
  });

  beforeEach(async () => {
    vi.stubEnv("VITE_MOCK", "1");
    sessionStorage.clear();
    queryClient.clear();
    // The routers are singletons shared by every test in this file: put both
    // of them, and the address bar, back at `/` before each case.
    window.history.replaceState({}, document.title, "/");
    await act(async () => {
      await publicRouter.navigate("/", { replace: true });
      await authenticatedRouter.navigate("/", { replace: true });
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    delete (globalThis as GlobalWithMockAuth).__policyAtlasMockAuth;
  });

  it("navigates once to the restored deep link when the router and the URL disagree", async () => {
    const deepLink = `/tasks/${MOCK_TASK_ID}/sources`;

    // The state a sign-in callback leaves behind: the address bar has been
    // rewritten to the stashed path with `replaceState`, while the
    // authenticated router — created and initialised at import time, before
    // the redirect — is still on the landing route.
    window.history.replaceState({}, document.title, deepLink);
    expect(authenticatedRouter.state.location.pathname).toBe("/");

    const navigate = vi.spyOn(authenticatedRouter, "navigate");
    setMockAuth("authenticated");
    await act(async () => {
      render(<App />);
    });

    expect(navigate.mock.calls).toEqual([[deepLink, { replace: true }]]);
    await waitFor(() => expect(authenticatedRouter.state.location.pathname).toBe(deepLink));
    expect(navigate.mock.calls).toEqual([[deepLink, { replace: true }]]);
  });

  it("does not navigate when the authenticated router already matches the URL", async () => {
    // The ordinary case: no round trip, so the router's location and the
    // address bar already agree and the seam must stay out of the way.
    expect(authenticatedRouter.state.location.pathname).toBe(window.location.pathname);

    const navigate = vi.spyOn(authenticatedRouter, "navigate");
    setMockAuth("authenticated");
    await act(async () => {
      render(<App />);
    });

    expect(navigate).not.toHaveBeenCalled();
    expect(authenticatedRouter.state.location.pathname).toBe("/");
  });

  it("carries a signed-out deep link through stash-and-splash, sign-in and back (task 036)", async () => {
    const deepLink = `/projects/${MOCK_PROJECT_ID}`;
    setMockAuth("unauthenticated");

    // A signed-out visitor opens an app-only deep link: the public router's
    // catch-all stashes it and replaces the URL with the splash home.
    await act(async () => {
      await publicRouter.navigate(deepLink, { replace: true });
    });
    const signedOut = render(<App />);
    await waitFor(() => expect(sessionStorage.getItem(AUTH_RETURN_TO_KEY)).toBe(deepLink));
    await waitFor(() => expect(publicRouter.state.location.pathname).toBe("/"));

    // Sign in: the redirect to the IdP tears the page down, and Cognito
    // returns to a fresh load whose callback drains the stash into the
    // address bar before the app decides which router to mount.
    signedOut.unmount();
    restoreStashAsSigninCallbackWould();
    expect(window.location.pathname).toBe(deepLink);
    expect(sessionStorage.getItem(AUTH_RETURN_TO_KEY)).toBeNull();

    setMockAuth("authenticated");
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => expect(authenticatedRouter.state.location.pathname).toBe(deepLink));
  });
});
