import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as queries from "./api/queries";
import { AUTH_RETURN_TO_KEY } from "./auth/OidcAuthProvider";
import { StashAndSplashRedirect } from "./routes/StashAndSplashRedirect";
import { RedirectToPath } from "./views/LifecycleRoute";
import { PublicTaskShell } from "./views/PublicTaskShell";

vi.mock("./api/queries", () => ({ useTask: vi.fn() }));
vi.mock("./auth", () => ({
  useAuth: () => ({
    user: null,
    status: "unauthenticated",
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    getAccessToken: async () => null,
  }),
}));
vi.mock("./api/sse", () => ({ connectEventStream: () => ({ close: vi.fn() }) }));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

const PUBLIC_TASK = {
  task_id: TASK_ID,
  name: "Shared evidence review",
  access: "public",
  is_owner: false,
  latest_run: null,
};

/** The same shape as `publicRouter`'s `/tasks/:taskId` block in
 *  `routes.tsx`, with lightweight leaf elements — this test is about the
 *  wildcard redirect and the stash-and-splash fallback, not the real views. */
function buildPublicRouter(initialPath: string) {
  return createMemoryRouter(
    [
      { path: "/", element: <div>splash probe</div> },
      {
        path: "/tasks/:taskId",
        element: <PublicTaskShell />,
        children: [
          { index: true, element: <RedirectToPath suffix="/results" /> },
          { path: "results", element: <div>results probe</div> },
          { path: "sources", element: <div>sources probe</div> },
          { path: "*", element: <RedirectToPath suffix="/results" preserveOriginal /> },
        ],
      },
      { path: "*", element: <StashAndSplashRedirect /> },
    ],
    { initialEntries: [initialPath] },
  );
}

describe("publicRouter's wildcard redirect must not rewrite the stashed return URL (task 037 review fix)", () => {
  // The failure needs two steps that a single render cannot span (a
  // `useTask` refetch settling is a plain re-render, and React Router
  // memoises matched route elements), so the property is pinned in halves:
  // the wildcard redirect carries the original path in router state, and
  // the stash prefers that state over the rewritten URL.
  it("the wildcard redirect carries the original deep link in router state", async () => {
    // Stale-but-still-public cached data (a task that WAS public and got
    // unshared) resolves the query immediately with `access: "public"` —
    // Outlet renders, the wildcard child matches `/share` and fires its
    // client-side redirect to `/results`, carrying the original path.
    vi.mocked(queries.useTask).mockReturnValue({
      isPending: false,
      data: PUBLIC_TASK,
    } as unknown as ReturnType<typeof queries.useTask>);

    const router = buildPublicRouter(`/tasks/${TASK_ID}/share`);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("results probe")).toBeInTheDocument());
    expect(router.state.location.pathname).toBe(`/tasks/${TASK_ID}/results`);
    expect(router.state.location.state).toEqual({ from: `/tasks/${TASK_ID}/share` });
  });

  it("the stash prefers the preserved original over the rewritten URL", () => {
    sessionStorage.clear();
    const router = createMemoryRouter([{ path: "*", element: <StashAndSplashRedirect /> }], {
      initialEntries: [
        {
          pathname: `/tasks/${TASK_ID}/results`,
          state: { from: `/tasks/${TASK_ID}/share` },
        },
      ],
    });
    render(<RouterProvider router={router} />);
    expect(sessionStorage.getItem(AUTH_RETURN_TO_KEY)).toBe(`/tasks/${TASK_ID}/share`);
  });

  it("still stashes the plain current URL when there is no preserved original (unaffected paths)", () => {
    sessionStorage.clear();
    vi.mocked(queries.useTask).mockReturnValue({
      isPending: false,
      data: undefined,
    } as unknown as ReturnType<typeof queries.useTask>);

    const router = buildPublicRouter(`/tasks/${TASK_ID}/results`);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(sessionStorage.getItem(AUTH_RETURN_TO_KEY)).toBe(`/tasks/${TASK_ID}/results`);
  });
});
