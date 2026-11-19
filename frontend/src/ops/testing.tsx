import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { AuthContext } from "../auth/AuthContext";
import type { AuthApi } from "../auth/types";
import { ToastProvider } from "../ui/radix/Toast";
import { mockOpsAuth, opsMockFetch, resetOpsMock } from "./mock";
import { opsRoutes } from "./routes";

/* Test helpers for the ops pages: the mock routes at `fetch`, and the
   whole app (shell and router) at one address. */

/** Answer `fetch` from the ops mock in every test of the file. */
export function withOpsMock() {
  beforeEach(() => {
    resetOpsMock();
    vi.stubGlobal("fetch", opsMockFetch);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });
}

/** Render the ops pages at `path`, signed in as the mock's ops person unless `auth` says otherwise. */
export function renderOps(path: string, auth: AuthApi = mockOpsAuth) {
  const router = createMemoryRouter(opsRoutes, { initialEntries: [path] });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false } } });
  render(
    <AuthContext.Provider value={auth}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
  return router;
}

/** Choose `option` in the dropdown named `label`. */
export async function pick(user: UserEvent, label: string, option: string) {
  await user.click(screen.getByRole("combobox", { name: label }));
  await user.click(await screen.findByRole("option", { name: option }));
}
